"""``aircraft_watch {on}`` (spec flight-manager-and-world-20261110 §5.2,
#2001; capability ``aircraft_position``): while on, X-Plane's aircraft is
read from its Web API once a second and published as
:class:`~o4_engine.events.AircraftPosition` -- the Fly map's aircraft and
track.  One watch per engine; ``on: false`` stops it.  Nothing is sent
while X-Plane does not answer.

Track and groundspeed come from position deltas
(:class:`O4_Imagery_Follow_Motion.MotionTracker`, the follow job's rule:
a sim-rate multiplier is measured, not trusted); a standing aircraft keeps
its heading.  The reader is the follow job's
(:class:`O4_XPlane_WebAPI.PositionReader`); lane W1's ``position_feed``
folds the two readers into one.

A command module, not a session method (the reason given in
``imagery_commands``).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

from O4_Imagery_Follow_Motion import MotionTracker

from .events import AircraftPosition

# The command itself is reached through the command table only.
__all__ = ["ON_GROUND_AGL_M", "PERIOD_S", "aircraft_watch_handlers"]

#: Seconds between two reads.
PERIOD_S = 1.0
#: Height above the ground under which the aircraft is on the ground.
ON_GROUND_AGL_M = 3.0

_WATCH: Dict[str, Any] = {"thread": None, "stop": None}
_GUARD = threading.Lock()


def aircraft_position(rec: Dict[str, Any], motion) -> AircraftPosition:
    """One ``pos`` record (``O4_XPlane_WebAPI.read_position``) and the
    motion it implies, as the event.  Pure."""
    agl = rec.get("agl_m")
    moving = motion is not None and motion.groundspeed_ms > 0.5
    track = motion.track_deg if moving else float(rec.get("hdg") or 0.0)
    return AircraftPosition(
        lat=float(rec["lat"]), lon=float(rec["lon"]),
        alt_m=float(rec.get("elev_m") or 0.0),
        track_deg=round(track % 360.0, 1),
        speed_ms=round(motion.groundspeed_ms, 2) if motion is not None else 0.0,
        on_ground=agl is not None and float(agl) < ON_GROUND_AGL_M,
        paused=bool(rec.get("paused")))


def _run(emit: Callable, reader, stop: threading.Event, period_s: float,
         clock: Callable[[], float]) -> None:
    tracker = MotionTracker()
    while not stop.is_set():
        try:
            rec = reader.read()
            if rec is not None:
                if reader.resolved:
                    tracker.restart()    # a flight load: not a flight on
                motion = tracker.add(clock(), rec["lat"], rec["lon"],
                                     float(rec.get("elev_m") or 0.0))
                emit(aircraft_position(rec, motion))
        except (TypeError, ValueError, KeyError):
            pass    # one bad record (a flight loading) never ends the watch
        stop.wait(period_s)


def watching() -> bool:
    """Is the watch on?"""
    thread = _WATCH["thread"]
    return thread is not None and thread.is_alive()


def aircraft_watch(emit: Callable, on: bool = True, port: Optional[int] = None,
                   reader=None, period_s: float = PERIOD_S,
                   clock: Callable[[], float] = time.monotonic) -> Dict[str, Any]:
    """Start (``on``) or stop the watch; replies ``{"watching": bool}``.
    ``reader`` (anything with ``read()`` and ``resolved``) replaces X-Plane
    in tests."""
    with _GUARD:
        if not on:
            if _WATCH["stop"] is not None:
                _WATCH["stop"].set()
            _WATCH["thread"] = _WATCH["stop"] = None
            return {"watching": False}
        if watching():
            return {"watching": True}
        if reader is None:
            import O4_XPlane_WebAPI as API

            from .imagery_commands import follow_settings
            reader = API.PositionReader(API.base_url(
                int(port or follow_settings()["port"])))
        stop = threading.Event()
        thread = threading.Thread(
            target=_run, args=(emit, reader, stop, period_s, clock),
            daemon=True, name="o4-aircraft-watch")
        _WATCH["thread"], _WATCH["stop"] = thread, stop
        thread.start()
        return {"watching": True}


def aircraft_watch_handlers(emit: Callable) -> Dict[str, Callable]:
    """This module's entry for the command table."""
    return {"aircraft_watch": lambda **kw: aircraft_watch(emit, **kw)}
