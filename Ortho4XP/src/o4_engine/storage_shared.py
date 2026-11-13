"""ONE storage scan, measured in the background and shared (#2029, owner
2026-11-12T23:56Z: "I thought the storage process would run in the
background so opening the settings and going to storage after the app
has been running should have everything already populated").

* :func:`watch` -- at the engine session's start: one scan
  :data:`STARTUP_DELAY_S` after it (low priority: never while a build
  runs, it waits for the run to end), and again after each build run.
* :func:`remember` -- every ``storage.storage_scan`` result (the apps'
  own Refresh, the scan after a clear or the automatic cleanup) is the
  shared one.
* :func:`storage_scan_cached` -- ENGINE COMMAND: the shared result at
  once (``scan`` None before the first), its age and whether a refresh
  is running; Settings ▸ Storage shows it immediately, with a quiet
  "Updating…" while a refresh runs (both apps).

No tile or airport is named here.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

__all__ = ["STARTUP_DELAY_S", "remember", "refresh", "watch",
           "storage_scan_cached"]

#: The first scan waits this long after the session starts (the app's
#: own start work goes first).
STARTUP_DELAY_S = 20.0
#: How often a refresh waiting for a build to end looks again.
_BUSY_POLL_S = 5.0
#: A refresh waits at most this long for a build (then it runs anyway:
#: a scan only reads).
_BUSY_WAIT_S = 6 * 3600.0
_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {"scan": None, "at": 0.0, "running": False}


def remember(scan: dict) -> None:
    """``scan`` (a ``storage_scan`` result) is the shared one now."""
    with _LOCK:
        _STATE["scan"], _STATE["at"] = scan, time.time()


def _work(busy: Optional[Callable[[], bool]], delay_s: float) -> None:
    from . import storage as STORAGE
    try:
        time.sleep(max(0.0, delay_s))
        waited = 0.0
        while busy is not None and busy() and waited < _BUSY_WAIT_S:
            time.sleep(_BUSY_POLL_S)
            waited += _BUSY_POLL_S
        STORAGE.storage_scan()          # remembers its own result
    except Exception:                   # a background scan never fails the app
        pass
    finally:
        with _LOCK:
            _STATE["running"] = False


def refresh(busy: Optional[Callable[[], bool]] = None,
            delay_s: float = 0.0) -> bool:
    """Start a background scan unless one is running; True when started."""
    with _LOCK:
        if _STATE["running"]:
            return False
        _STATE["running"] = True
    threading.Thread(target=_work, args=(busy, delay_s), daemon=True,
                     name="o4-storage-shared").start()
    return True


def watch(session: Any, delay_s: float = STARTUP_DELAY_S) -> None:
    """The first scan ``delay_s`` after the session starts, then one after
    each build run (``RunDone``); never while a build runs."""
    def busy() -> bool:
        return bool(getattr(session, "_building", False))

    def on_event(event) -> None:
        if type(event).__name__ == "RunDone":
            refresh(busy)
    session.subscribe(on_event)
    refresh(busy, delay_s)


def storage_scan_cached(**_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``storage_scan_cached``: ``{"scan" (the shared
    ``storage_scan`` result, None before the first), "age_s" (None
    before), "updating"}``; a scan is started when there is none."""
    with _LOCK:
        scan, at, running = _STATE["scan"], _STATE["at"], _STATE["running"]
    if scan is None and not running:
        running = refresh()
    return {"scan": scan, "age_s": (time.time() - at) if scan else None,
            "updating": bool(running)}
