"""Tests for the front-end secret broker (o4_engine.secret_broker) and
its routing through :mod:`O4_Authenticated_Sessions` and the JSON-lines
transport.

All headless: the "front end" is a fake transport (or the test itself
answering protocol lines over a pipe), and keyring is either absent or a
booby-trapped fake proving the brokered paths never touch it.
"""

import json
import os
import sys
import threading
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Authenticated_Sessions as SESSIONS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine.events import SecretRequest  # noqa: E402
from o4_engine.secret_broker import SecretBroker  # noqa: E402

from test_engine_jsonl import _CaptureStream, _is_event  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures and fakes
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.secret_broker = None
    UI.engine_session = None
    UI.red_flag = False


@pytest.fixture
def sessions_directory(monkeypatch, tmp_path) -> str:
    directory = str(tmp_path / "Sessions")
    monkeypatch.setattr(SESSIONS, "sessions_directory", lambda: directory)
    return directory


@pytest.fixture
def booby_trapped_keyring(monkeypatch):
    """A fake keyring whose every function fails the test: proof that a
    brokered code path never falls back to the platform store."""
    fake_keyring = types.ModuleType("keyring")
    fake_errors = types.ModuleType("keyring.errors")

    def _forbidden(*_args, **_kwargs):
        raise AssertionError(
            "keyring must not be touched while a secret broker is active")

    fake_keyring.get_keyring = _forbidden
    fake_keyring.set_password = _forbidden
    fake_keyring.get_password = _forbidden
    fake_keyring.delete_password = _forbidden
    fake_keyring.errors = fake_errors
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setitem(sys.modules, "keyring.errors", fake_errors)


class _FakeBroker:
    """Records every request; answers from a scripted response list
    (default: success with a fixed secret for gets)."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def request(self, operation, session_name, account, secret=""):
        self.calls.append((operation, session_name, account, secret))
        if self.responses:
            return self.responses.pop(0)
        return (True, "stored-secret", "")


def _write_username_sidecar(directory, session_name, username):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, session_name + ".account.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"username": username}, handle)


# ---------------------------------------------------------------------------
# SecretBroker unit behavior
# ---------------------------------------------------------------------------
def test_broker_round_trip_from_worker_thread():
    sent = []
    broker = SecretBroker(send_request=sent.append)
    result = {}

    def worker():
        result["value"] = broker.request("get", "dgterritorio", "user")

    thread = threading.Thread(target=worker)
    thread.start()
    # The request event appears (with its stamped id) before delivery.
    deadline = threading.Event()
    for _ in range(200):
        if sent:
            break
        deadline.wait(0.01)
    assert sent, "no SecretRequest was sent"
    request = sent[0]
    assert isinstance(request, SecretRequest)
    assert (request.operation, request.session_name, request.account) == (
        "get", "dgterritorio", "user")
    broker.deliver(request.request_id, ok=True, secret="hunter2")
    thread.join(5)
    assert result["value"] == (True, "hunter2", "")


def test_broker_get_miss_and_front_end_error():
    sent = []
    broker = SecretBroker(send_request=sent.append)

    threads = []
    results = {}

    def ask(name):
        results[name] = broker.request("get", "s", name)

    for name in ("missing", "failing"):
        thread = threading.Thread(target=ask, args=(name,))
        thread.start()
        threads.append(thread)
    for _ in range(500):
        if len(sent) == 2:
            break
        threading.Event().wait(0.01)
    by_account = {event.account: event for event in sent}
    # A found-nothing answer is ok=True with a null secret.
    broker.deliver(by_account["missing"].request_id, ok=True, secret=None)
    broker.deliver(by_account["failing"].request_id, ok=False,
                   error="Keychain said no")
    for thread in threads:
        thread.join(5)
    assert results["missing"] == (True, None, "")
    (ok, secret, error) = results["failing"]
    assert (ok, secret) == (False, None)
    assert "Keychain said no" in error


def test_broker_timeout(monkeypatch):
    monkeypatch.setenv("O4_SECRET_BROKER_TIMEOUT_SECONDS", "0.05")
    broker = SecretBroker(send_request=lambda event: None)
    (ok, secret, error) = broker.request("get", "s", "u")
    assert (ok, secret) == (False, None)
    assert "did not answer" in error


def test_broker_refuses_service_thread_request():
    broker = SecretBroker(send_request=lambda event: None,
                          service_thread=threading.current_thread())
    (ok, _secret, error) = broker.request("get", "s", "u")
    assert ok is False
    assert "read thread" in error


def test_broker_shutdown_fails_pending_and_future_requests():
    broker = SecretBroker(send_request=lambda event: None)
    result = {}

    def worker():
        result["value"] = broker.request("get", "s", "u")

    thread = threading.Thread(target=worker)
    thread.start()
    for _ in range(200):
        if broker._pending:
            break
        threading.Event().wait(0.01)
    broker.shutdown()
    thread.join(5)
    assert result["value"][0] is False
    assert broker.request("get", "s", "u")[0] is False


def test_deliver_unknown_request_id_is_ignored():
    broker = SecretBroker(send_request=lambda event: None)
    assert broker.deliver(12345, ok=True, secret="x") is True


# ---------------------------------------------------------------------------
# O4_Authenticated_Sessions routing (fake broker; keyring booby-trapped)
# ---------------------------------------------------------------------------
def test_store_and_load_credentials_route_to_broker(
        monkeypatch, sessions_directory, booby_trapped_keyring):
    broker = _FakeBroker(responses=[(True, None, "")])
    monkeypatch.setattr(UI, "secret_broker", broker)

    assert SESSIONS.credential_store_available() is True
    SESSIONS.store_credentials("dgterritorio", "user@example.org", "pw")
    assert broker.calls == [
        ("set", "dgterritorio", "user@example.org", "pw")]
    # The username sidecar is still written locally (it is not a secret).
    with open(os.path.join(sessions_directory,
                           "dgterritorio.account.json")) as handle:
        assert json.load(handle) == {"username": "user@example.org"}

    broker.responses = [(True, "pw", "")]
    assert SESSIONS.load_credentials("dgterritorio") == (
        "user@example.org", "pw")
    assert broker.calls[-1] == ("get", "dgterritorio", "user@example.org", "")


def test_delete_credentials_routes_to_broker(
        monkeypatch, sessions_directory, booby_trapped_keyring):
    broker = _FakeBroker(responses=[(True, None, "")])
    monkeypatch.setattr(UI, "secret_broker", broker)
    SESSIONS.store_credentials("svc", "user", "pw")
    broker.responses = [(True, "pw", ""), (True, None, "")]
    SESSIONS.delete_credentials("svc")
    assert broker.calls[-1] == ("delete", "svc", "user", "")
    assert not os.path.exists(
        os.path.join(sessions_directory, "svc.account.json"))


def test_api_key_routes_to_broker(monkeypatch, booby_trapped_keyring):
    broker = _FakeBroker(responses=[(True, None, "")])
    monkeypatch.setattr(UI, "secret_broker", broker)
    SESSIONS.store_api_key("opentopo", "KEY123")
    assert broker.calls == [("set", "opentopo", "api-key", "KEY123")]
    broker.responses = [(True, "KEY123", "")]
    assert SESSIONS.load_api_key("opentopo") == "KEY123"
    broker.responses = [(True, None, "")]
    SESSIONS.delete_api_key("opentopo")
    assert broker.calls[-1] == ("delete", "opentopo", "api-key", "")


def test_broker_set_failure_raises_store_unavailable(
        monkeypatch, sessions_directory, booby_trapped_keyring):
    broker = _FakeBroker(responses=[(False, None, "Keychain refused")])
    monkeypatch.setattr(UI, "secret_broker", broker)
    with pytest.raises(SESSIONS.CredentialStoreUnavailable) as excinfo:
        SESSIONS.store_credentials("svc", "user", "pw")
    assert "Keychain refused" in str(excinfo.value)


def test_broker_get_failure_reads_as_no_credentials(
        monkeypatch, sessions_directory, booby_trapped_keyring):
    _write_username_sidecar(sessions_directory, "svc", "user")
    broker = _FakeBroker(responses=[(False, None, "front end gone")])
    monkeypatch.setattr(UI, "secret_broker", broker)
    assert SESSIONS.load_credentials("svc") is None
    broker.responses = [(False, None, "front end gone")]
    assert SESSIONS.load_api_key("svc") is None


def test_no_broker_keeps_keyring_path(monkeypatch, sessions_directory):
    """Without a broker the historic keyring routing is unchanged."""
    store = {}
    fake_keyring = types.ModuleType("keyring")
    fake_errors = types.ModuleType("keyring.errors")

    class _Backend:
        pass

    _Backend.__module__ = "tests.fake_backend"
    fake_keyring.get_keyring = lambda: _Backend()
    fake_keyring.set_password = (
        lambda service, account, secret: store.__setitem__(
            (service, account), secret))
    fake_keyring.get_password = (
        lambda service, account: store.get((service, account)))
    fake_keyring.delete_password = (
        lambda service, account: store.pop((service, account), None))
    fake_keyring.errors = fake_errors
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    monkeypatch.setitem(sys.modules, "keyring.errors", fake_errors)
    monkeypatch.setattr(UI, "secret_broker", None)

    SESSIONS.store_credentials("svc", "user", "pw")
    assert store == {("Ortho4XP session svc", "user"): "pw"}
    assert SESSIONS.load_credentials("svc") == ("user", "pw")


# ---------------------------------------------------------------------------
# End to end through the JSON-lines transport
# ---------------------------------------------------------------------------
def test_transport_brokers_credential_load(monkeypatch, tmp_path):
    """serve() activates the broker: a load_credentials on a worker
    thread becomes a SecretRequest protocol line, and the front end's
    secret_response command completes it."""
    directory = str(tmp_path / "Sessions")
    monkeypatch.setattr(SESSIONS, "sessions_directory", lambda: directory)
    _write_username_sidecar(directory, "dgterritorio", "user@example.org")
    # The real imagery-registry initialization drags pyproj in, whose
    # PROJ library registers a pthread_atfork handler that SEGFAULTS any
    # later fork in this test process (the documented crash in
    # O4_UI_Utils.external_tool_keyword_arguments) — which breaks the
    # parallel-build suites when they share a pytest worker.  This test
    # needs no providers.
    monkeypatch.setattr(jsonl, "_initialize_pipeline_registries",
                        lambda: None)

    read_fd, write_fd = os.pipe()
    stdin = os.fdopen(read_fd, "r")
    writer = os.fdopen(write_fd, "w")
    capture = _CaptureStream()
    serve_thread = threading.Thread(target=jsonl.serve,
                                    args=(stdin, capture))
    serve_thread.start()
    result = {}
    try:
        assert capture.wait_for(lambda l: _is_event(l, "EngineHello"))
        hello = capture.objects()[0]
        assert "secrets" in hello["capabilities"]

        def worker():
            result["credentials"] = SESSIONS.load_credentials("dgterritorio")

        load_thread = threading.Thread(target=worker)
        load_thread.start()
        assert capture.wait_for(lambda l: _is_event(l, "SecretRequest")), \
            "no SecretRequest reached the protocol stream"
        request = next(o for o in capture.objects()
                       if o.get("event") == "SecretRequest")
        assert request["operation"] == "get"
        assert request["session_name"] == "dgterritorio"
        assert request["account"] == "user@example.org"
        assert request["secret"] == ""
        writer.write(json.dumps({
            "cmd": "secret_response", "id": 7,
            "request_id": request["request_id"],
            "ok": True, "secret": "hunter2"}) + "\n")
        writer.flush()
        load_thread.join(10)
        assert not load_thread.is_alive()
        # The response command got the uniform reply framing too.
        assert capture.wait_for(
            lambda l: '"reply": 7' in l or '"reply":7' in l)
        writer.write(json.dumps({"cmd": "shutdown", "id": 8}) + "\n")
        writer.flush()
        serve_thread.join(30)
        assert not serve_thread.is_alive()
    finally:
        writer.close()
        stdin.close()
    assert result["credentials"] == ("user@example.org", "hunter2")
    # serve() cleaned its routing attribute up on the way out.
    assert UI.secret_broker is None


# ---------------------------------------------------------------------------
# Parallel parent driver: servicing a worker child's request
# ---------------------------------------------------------------------------
class _FakeChild:
    def __init__(self):
        self.sent = []

    def send(self, command):
        self.sent.append(command)
        return True


def _bare_parallel_run():
    from o4_engine import parallel
    return parallel.ParallelBuildRun.__new__(parallel.ParallelBuildRun)


def test_parent_services_child_get(monkeypatch):
    monkeypatch.setattr(SESSIONS, "secret_get",
                        lambda session_name, account: "pw")
    child = _FakeChild()
    _bare_parallel_run()._service_child_secret_request(child, {
        "event": "SecretRequest", "request_id": 3, "operation": "get",
        "session_name": "svc", "account": "user", "secret": ""})
    assert child.sent == [{
        "cmd": "secret_response", "request_id": 3, "ok": True,
        "secret": "pw"}]


def test_parent_services_child_set_and_delete(monkeypatch):
    calls = []
    monkeypatch.setattr(
        SESSIONS, "secret_set",
        lambda session_name, account, secret: calls.append(
            ("set", session_name, account, secret)))
    monkeypatch.setattr(
        SESSIONS, "secret_delete",
        lambda session_name, account: calls.append(
            ("delete", session_name, account)))
    child = _FakeChild()
    run = _bare_parallel_run()
    run._service_child_secret_request(child, {
        "request_id": 1, "operation": "set", "session_name": "svc",
        "account": "user", "secret": "pw"})
    run._service_child_secret_request(child, {
        "request_id": 2, "operation": "delete", "session_name": "svc",
        "account": "user"})
    assert calls == [("set", "svc", "user", "pw"), ("delete", "svc", "user")]
    assert [c["ok"] for c in child.sent] == [True, True]


def test_parent_reports_child_request_failures(monkeypatch):
    def boom(session_name, account):
        raise RuntimeError("store exploded")

    monkeypatch.setattr(SESSIONS, "secret_get", boom)
    child = _FakeChild()
    run = _bare_parallel_run()
    run._service_child_secret_request(child, {
        "request_id": 5, "operation": "get", "session_name": "svc",
        "account": "user"})
    run._service_child_secret_request(child, {
        "request_id": 6, "operation": "frobnicate", "session_name": "svc",
        "account": "user"})
    assert child.sent[0]["ok"] is False
    assert "store exploded" in child.sent[0]["error"]
    assert child.sent[1]["ok"] is False
    assert "frobnicate" in child.sent[1]["error"]


def test_child_reader_routes_secret_request_off_thread(monkeypatch):
    """_on_child_event hands SecretRequest to a service thread and
    answers over the child's stdin."""
    monkeypatch.setattr(SESSIONS, "secret_get",
                        lambda session_name, account: "pw")
    child = _FakeChild()
    run = _bare_parallel_run()
    run._on_child_event(child, {
        "event": "SecretRequest", "request_id": 9, "operation": "get",
        "session_name": "svc", "account": "user", "secret": "",
        "seq": 1, "ts": 0.0})
    for _ in range(500):
        if child.sent:
            break
        threading.Event().wait(0.01)
    assert child.sent == [{
        "cmd": "secret_response", "request_id": 9, "ok": True,
        "secret": "pw"}]
