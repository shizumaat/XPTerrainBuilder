"""Secret-store brokerage: route platform-secret operations to the front
end that owns this engine process.

Why this exists (2026-07-23): the packaged macOS application runs the
engine as a separate, ad-hoc-signed binary.  When THAT process talks to
the Keychain through the ``keyring`` package, the user-visible permission
prompt is attributed to "Ortho4XP" instead of the application — and the
ad-hoc code signature changes on every rebuild, so previously granted
Keychain access is lost each time.  The fix is to let the FRONT END hold
the secrets: while a JSON-lines transport is serving this engine, secret
operations become :class:`o4_engine.events.SecretRequest` events on the
protocol stream, and the front end answers each with a
``secret_response`` command serviced from its own secret store (the
signed application bundle's Keychain, whose prompt and access-control
list are stable).

Only the transport activates a broker (``jsonl.serve`` sets
``O4_UI_Utils.secret_broker`` for its lifetime).  Standalone runs — the
command line, the Tkinter and Qt applications with their in-process
sessions — keep using ``keyring`` directly through the unchanged
``O4_Authenticated_Sessions`` code paths.  Parallel-build worker
children run the transport too, so their requests reach the parent
driver (``o4_engine.parallel``), which services them with ITS routing:
forwarded on to the application when the parent is itself brokered,
``keyring`` in the parent process otherwise.

Threading contract: :meth:`SecretBroker.request` BLOCKS its calling
thread (bounded by a timeout) until :meth:`SecretBroker.deliver` is
called with the matching ``request_id``.  Requests therefore must come
from worker threads — the transport's read loop is the thread that
delivers responses, so a request made ON that thread could never be
answered; the broker detects this and fails fast instead of deadlocking.
Concurrent outstanding requests are supported (parallel children).
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional, Tuple

from .events import SecretRequest

# How long a secret operation may wait for the front end's answer.  The
# front end services requests from its own local secret store, so real
# answers arrive in milliseconds; the cap only bounds a wedged or
# unresponsive front end.  Overridable for the test suite.
DEFAULT_TIMEOUT_SECONDS = 60.0
TIMEOUT_ENVIRONMENT_KEY = "O4_SECRET_BROKER_TIMEOUT_SECONDS"


def _timeout_seconds() -> float:
    value = os.environ.get(TIMEOUT_ENVIRONMENT_KEY)
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_SECONDS


class SecretBroker:
    """One front end's secret-store service, seen from the engine side.

    ``send_request`` writes a :class:`SecretRequest` event to the front
    end (the transport passes its serialized protocol write).
    ``service_thread`` is the thread that will call :meth:`deliver` (the
    transport's read loop); a request made from that same thread is
    refused immediately rather than left to dead-block.
    """

    def __init__(
        self,
        send_request: Callable[[SecretRequest], None],
        service_thread: Optional[threading.Thread] = None,
    ):
        self._send_request = send_request
        self._service_thread = service_thread
        self._lock = threading.Lock()
        self._next_request_id = 0
        # request_id -> [threading.Event, response dict or None]
        self._pending = {}
        self._shut_down = False

    # -- engine side (worker threads) ----------------------------------
    def request(
        self, operation: str, session_name: str, account: str,
        secret: str = "",
    ) -> Tuple[bool, Optional[str], str]:
        """Perform one brokered operation; block until answered.

        Returns ``(ok, secret, error)``: ``ok`` False means the front
        end reported a store failure, never answered in time, or the
        broker is unusable — ``error`` says which.  For a successful
        "get", ``secret`` is the stored value or None when no entry
        exists.
        """
        if self._service_thread is not None and (
                threading.current_thread() is self._service_thread):
            # The thread that would deliver the response is the one
            # asking; waiting would deadlock the whole transport.
            return (False, None,
                    "secret operation attempted on the transport's own "
                    "read thread")
        ready = threading.Event()
        entry = [ready, None]
        with self._lock:
            if self._shut_down:
                return (False, None, "the front-end session has ended")
            self._next_request_id += 1
            request_id = self._next_request_id
            self._pending[request_id] = entry
        try:
            self._send_request(SecretRequest(
                request_id=request_id, operation=operation,
                session_name=session_name, account=account, secret=secret))
        except Exception as error:
            with self._lock:
                self._pending.pop(request_id, None)
            return (False, None,
                    "could not reach the front end: %s" % error)
        if not ready.wait(_timeout_seconds()):
            with self._lock:
                self._pending.pop(request_id, None)
            return (False, None,
                    "the front end did not answer the secret request "
                    "in time")
        response = entry[1] or {}
        if not response.get("ok"):
            return (False, None,
                    str(response.get("error")
                        or "the front end reported a secret-store error"))
        secret_value = response.get("secret")
        if secret_value is not None:
            secret_value = str(secret_value)
        return (True, secret_value, "")

    # -- transport side (read loop) ------------------------------------
    def deliver(self, request_id, ok=False, secret=None, error=None):
        """Route one ``secret_response`` command to its waiting request.

        Unknown ``request_id`` values (a timed-out request already gave
        up) are ignored.  Returns True so the transport's uniform
        command-reply framing has a result to report.
        """
        with self._lock:
            entry = self._pending.pop(int(request_id), None)
        if entry is not None:
            entry[1] = {"ok": bool(ok), "secret": secret, "error": error}
            entry[0].set()
        return True

    def shutdown(self):
        """Fail every outstanding request; refuse new ones (serve ended)."""
        with self._lock:
            self._shut_down = True
            pending = list(self._pending.values())
            self._pending.clear()
        for entry in pending:
            entry[1] = {"ok": False,
                        "error": "the front-end session has ended"}
            entry[0].set()
