"""The World job's background work yields to the owner (owner
2026-11-17T23:45Z (b), RULINGS 2026-11-17v): the spawn-window pre-drape
(``world_spawn_window``: after a tile publishes, and the backfill at app
start) PAUSES while the app builds tiles or X-Plane runs, and resumes
after.  The World job's own flight-follow drapes (``world_job``, while
flying) are not paused: they keep their priority.

* :func:`watch` -- the app's engine session (``world_job_run.autostart``);
  its build run (``session.building_tiles``) is "an app build".
* :func:`reason` -- "app build", "X-Plane" (``xplane_root.xplane_running``,
  read at most every :data:`XPLANE_EVERY_S`) or "" (free).
* :func:`wait` -- blocks the calling worker while :func:`reason` holds,
  logging the pause and the resume once each.

An app build is read from THIS engine session (the app's builds run in
it) and from the machine memory ledger (``O4_Machine_Memory``): another
session holding an ``app`` reservation, or an app step waiting (its WANT
mark), is an app build too.  This session's own records are not read
there: the World job's drapes reserve in it as well.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

__all__ = ["POLL_S", "XPLANE_EVERY_S", "watch", "reason", "wait"]

#: Seconds between looks while paused.
POLL_S = 15.0
#: Seconds one X-Plane process reading serves.
XPLANE_EVERY_S = 10.0

_LOCK = threading.Lock()
_SESSION: list = []
_XPLANE: list = [-1e18, False]           # [monotonic read at, running]


def watch(session) -> None:
    """The engine session whose build run pauses the work."""
    with _LOCK:
        _SESSION[:] = [session] if session is not None else []


def _app_building() -> bool:
    with _LOCK:
        session = _SESSION[0] if _SESSION else None
    if session is None:
        return False
    try:
        return bool(session.building_tiles())
    except Exception:                       # a session mid-teardown
        return False


def _ledger_app_building() -> bool:
    """Another engine session's app build holds or wants memory."""
    try:
        import O4_Machine_Memory as MEMORY
        snap = MEMORY.snapshot()
        mine = MEMORY.session_id()
    except Exception:                       # an unreadable ledger: no one
        return False
    return any(row.get("role") == "app" and sid != mine
               for sid, row in snap.sessions.items()) or any(
        w.get("session") != mine for w in snap.wants)


def _xplane() -> bool:
    now = time.monotonic()
    with _LOCK:
        if now - _XPLANE[0] < XPLANE_EVERY_S:
            return _XPLANE[1]
    from .xplane_root import xplane_running
    running = bool(xplane_running())
    with _LOCK:
        _XPLANE[:] = [now, running]
    return running


def reason() -> str:
    """Why the work waits now: "app build", "X-Plane", or "" (go)."""
    if _app_building() or _ledger_app_building():
        return "app build"
    if _xplane():
        return "X-Plane"
    return ""


def wait(log: Callable[[dict], None] = lambda r: None, *,
         why: Callable[[], str] = reason,
         sleep: Callable[[float], None] = time.sleep,
         stop: Optional[Callable[[], bool]] = None,
         poll_s: float = POLL_S, what: str = "spawn_window") -> float:
    """Block while ``why()`` names a reason (``stop()`` true ends it
    early); seconds waited.  One log line when the work pauses and one
    when it resumes."""
    held = why()
    if not held:
        return 0.0
    log({what: "paused", "reason": held})
    t0 = time.monotonic()
    while held and not (stop is not None and stop()):
        sleep(poll_s)
        held = why()
    waited = time.monotonic() - t0
    log({what: "resumed", "waited_s": round(waited, 1)})
    return waited
