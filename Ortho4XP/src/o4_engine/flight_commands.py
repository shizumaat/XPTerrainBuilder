"""The ``flight_*`` engine commands (spec flight-manager-and-world-20261110
§5.2), registered in ``jsonl.py``'s table through
:func:`flight_plan_handlers`; the in-process Qt session calls the same
handlers.

Plan reading (lane F1a), both synchronous file reads:

* ``flight_plans_list {xplane_dir}`` -- X-Plane's ``Output/FMS plans/``,
  newest first: ``{"plans": [{path, name, origin, destination,
  modified_at}]}`` (owner RULINGS 2026-11-10g: read automatically).
* ``flight_plan_read {path}`` -- one plan file (``.fms``, ``.lnmpln``, a
  saved SimBrief answer): :func:`plan_wire`.

The flight's own commands (lane F1b, capability ``flight_manager``;
:func:`flight_handlers`):

* ``flight_plan_simbrief {user}`` -- ``{"status": "started"}``, then
  ``FlightReady`` with the latest SimBrief plan (:func:`plan_wire`).
* ``flight_create {plan | path | dep + arr, build_alternate?: false,
  cruise_kt?, corridor_km?}`` -- a plan as ``flight_plan_read`` gives it
  (``.fms``, ``.lnmpln``, SimBrief), a plan file, or a departure and an
  arrival ``{ident, lat, lon}``; the record is written and its job starts
  (``world_job_start {mode: "flight"}``); ``{"flight": id}``.
  ``FlightStatus`` events follow.  One flight is active at a time.
* ``flight_status {flight?}`` -- the ``FlightStatus`` fields now.
* ``flight_update {flight, build_alternate?, cruise_kt?, corridor_km?,
  waive_offline?}`` -- the flight card's choices; the jobs are planned
  again.  ``waive_offline``: "Fly with X-Plane's own scenery there" for
  the en-route tiles that need the internet (RULINGS 2026-11-10k Q3).
* ``flight_end {flight}`` -- the flight closes; build-ahead's track mode,
  which ran beside it (#2019), runs on.  ``flight_end {if_prepared:
  true}`` (both apps, on "No plan: follow the aircraft") closes the active
  flight only while it is still preparing or ready, so a stale prepared
  record never owns build-ahead; a flight in the air is left as it is.
  ``flight_list`` -- the records, newest first.

Lane F2 (capability ``flight_notices``):

* ``flight_divert {flight, to}`` -- ``to`` is ``"alternate"``, an airport
  ``{ident, lat, lon}`` (the apps' airport search), ``[lat, lon]`` or an
  ident (the engine's airport index); the destination is replaced and
  its tile built ``full`` first (spec §8.6).  ``{"flight", "diverted_to"}``.
* ``flight_reload {flight}`` -- the pilot's "Reload scenery now" for the
  offered reload (rule S6 (a) on the ground, (b) in the air): the only
  way a flight's reload is sent (owner 2026-11-12T14:34Z).
* ``FlightNotice`` events: one per notice (``flight_notices``).
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import O4_Flight_Plan as FP

from . import flight_job_run as FLIGHT
from . import flight_record as RECORD
from . import world_commands as WORLD

__all__ = ["flight_plans_list", "flight_plan_read", "plan_wire",
           "flight_plan_handlers", "flight_handlers"]


def _place(w) -> Dict[str, Any]:
    return {"ident": w.ident, "lat": w.lat, "lon": w.lon,
            "alt_ft": w.alt_ft, "t_s": w.t_s}


def plan_wire(plan: "FP.FlightPlan") -> Dict[str, Any]:
    """A plan as JSON: ``source``, ``origin``, ``destination`` (idents),
    ``waypoints`` and ``alternate`` (``{ident, lat, lon, alt_ft, t_s}``,
    None where the plan does not say), ``ete_s``, ``cruise_ms``,
    ``cruise_alt_ft``, ``route_km``."""
    return {
        "source": plan.source, "origin": plan.origin,
        "destination": plan.destination,
        "waypoints": [_place(w) for w in plan.waypoints],
        "alternate": None if plan.alternate is None else _place(plan.alternate),
        "ete_s": plan.ete_s, "cruise_ms": plan.cruise_ms,
        "cruise_alt_ft": plan.cruise_alt_ft,
        "route_km": round(FP.route_length_km(plan.points()), 6),  # libm-stable digits
    }


def flight_plans_list(xplane_dir: str = "") -> Dict[str, Any]:
    """X-Plane's saved FMS plans, newest first (none without a folder)."""
    if not xplane_dir:
        return {"plans": []}
    return {"plans": FP.list_fms_plans(FP.fms_plans_dir(xplane_dir))}


def flight_plan_read(path: str = "") -> Dict[str, Any]:
    """One plan file as :func:`plan_wire`; an unreadable plan raises
    ``FlightPlanError`` (a ValueError: the transport answers ok=false with
    its sentence)."""
    return plan_wire(FP.read_plan_file(path))


def flight_plan_handlers() -> Dict[str, Callable]:
    """This module's entries for the command table."""
    return {"flight_plans_list": flight_plans_list,
            "flight_plan_read": flight_plan_read}


# ===========================================================================
# The flight (lane F1b)
# ===========================================================================
def _wire_point(row: Optional[Dict[str, Any]]) -> Optional["FP.Waypoint"]:
    if not row:
        return None
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("A waypoint of this plan has no position.") from error
    return FP.Waypoint(str(row.get("ident") or ""), lat, lon,
                       row.get("alt_ft"), row.get("t_s"))


def plan_from_wire(doc: Dict[str, Any]) -> "FP.FlightPlan":
    """:func:`plan_wire`'s shape (what the apps send back) as a plan."""
    points = [_wire_point(w) for w in (doc or {}).get("waypoints") or ()]
    if len(points) < 2:
        raise ValueError("This plan has no route: it needs a departure and "
                         "a destination.")
    return FP.FlightPlan(points, source=str(doc.get("source") or ""),
                         alternate=_wire_point(doc.get("alternate")),
                         ete_s=doc.get("ete_s"), cruise_ms=doc.get("cruise_ms"),
                         cruise_alt_ft=doc.get("cruise_alt_ft"))


def _source_kind(name: str) -> str:
    """``O4_Flight_Record.SOURCE_KINDS`` of a plan's ``source``."""
    lowered = (name or "").lower()
    if lowered.startswith("simbrief"):
        return "simbrief"
    for kind in ("fms", "lnmpln"):
        if lowered.endswith("." + kind):
            return kind
    return "none"


def _plan_of(plan, path: str, dep, arr) -> "FP.FlightPlan":
    if plan:
        return plan_from_wire(plan)
    if path:
        return FP.read_plan_file(path)
    if dep and arr:
        ends = [_wire_point(dep), _wire_point(arr)]
        return FP.FlightPlan([w._replace(ident=w.ident.upper()) for w in ends],
                             source="quick")
    raise ValueError("Name a flight: a plan, a plan file, or a departure "
                     "and an arrival.")


def _number(value, default: Optional[float]) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def flight_create(session, emit=None, plan=None, path: str = "", dep=None,
                  arr=None, build_alternate: bool = False, cruise_kt=None,
                  corridor_km=None, scenery_dir: str = "", port=None,
                  **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_create`` (see the module)."""
    from . import world_job_run as WORLD_JOB
    flight_plan = _plan_of(plan, path, dep, arr)
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not WORLD.managed(scenery_dir):
        raise ValueError("Install the World pack first (XPTerrainBuilder makes it when it starts): "
                         "a flight's tiles go into it.")
    running = FLIGHT.current()
    if running is not None:
        raise ValueError("A flight is already active (%s): end it first."
                         % running.manager.record.id)
    settings = FLIGHT._settings()
    corridor = _number(corridor_km, _number(settings.get("fly_corridor_km"),
                                            RECORD.DEFAULT_CORRIDOR_KM))
    record = RECORD.from_plan(
        flight_plan, _source_kind(flight_plan.source), datetime.now(timezone.utc),
        build_alternate=bool(build_alternate),
        cruise_kt=_number(cruise_kt, None), corridor_km=corridor)
    RECORD.save(record, RECORD.flights_dir())
    WORLD_JOB.world_job_start(session, emit, mode="flight", flight=record.id,
                              scenery_dir=scenery_dir, port=port)
    return {"flight": record.id}


def _record(flight: str = "") -> Optional["RECORD.FlightRecord"]:
    folder = RECORD.flights_dir()
    if not flight:
        return RECORD.active_flight(folder)
    try:
        return RECORD.load(os.path.join(folder, flight + ".json"))
    except (OSError, ValueError):
        return None


def _runner_for(flight: str = ""):
    runner = FLIGHT.current()
    if runner is not None and flight in ("", runner.manager.record.id):
        return runner
    return None


def flight_status(flight: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_status``: the ``FlightStatus`` fields of
    the running flight (or of the record, when it no longer runs);
    ``{"flight": None}`` when there is none."""
    runner = _runner_for(flight)
    if runner is not None:
        return runner.status()
    record = _record(flight)
    if record is None:
        return {"flight": None}
    return {"flight": record.id, "state": record.state, "phase": record.phase,
            "ready": record.state in ("ready", "flying", "arrived"),
            "countdown_s": None, "reason": "", "items": [],
            "jobs": [[t.tile, t.role, t.kind, t.state, 0.0, None]
                     for t in record.tiles],
            "late": [], "shed": [], "reload": "", "diverted_to": "",
            "waivable": []}


def flight_update(flight: str = "", build_alternate=None, cruise_kt=None,
                  corridor_km=None, waive_offline=None, **_ignored
                  ) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_update``: the flight card's choices."""
    import O4_Flight_Schedule as SCHEDULE
    runner = _runner_for(flight)
    if runner is None:
        raise ValueError("That flight is not active.")
    with runner.lock:
        record = runner.manager.record
        if build_alternate is not None:
            record.build_alternate = bool(build_alternate)
        speed = _number(cruise_kt, None)
        if speed is not None:
            record.profile.update(cruise_ms=speed * SCHEDULE.KT_TO_MS,
                                  basis="pilot")
        corridor = _number(corridor_km, None)
        if corridor is not None:
            record.corridor_km = corridor
        runner.manager.replan()
        if waive_offline:
            runner.manager.waive()
    RECORD.save(record, RECORD.flights_dir())
    return {"flight": record.id}


#: The states ``flight_end {if_prepared: true}`` closes (not yet flown).
_PREPARED = ("preparing", "ready")


def flight_end(session=None, flight: str = "", if_prepared: bool = False,
               **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_end``: the flight closes (its record keeps
    what was built); build-ahead's track mode runs on (started here when
    it was not running).  ``if_prepared``: only a flight not yet flown
    (:data:`_PREPARED`); otherwise ``{"flight": None}`` and nothing
    changes."""
    from . import world_job_run as WORLD_JOB
    runner = _runner_for(flight)
    if if_prepared:
        active = runner.manager.record if runner is not None else _record(flight)
        if active is None or active.state not in _PREPARED:
            return {"flight": None}
    record = FLIGHT.stop() if runner is not None else _record(flight)
    if record is None:
        raise ValueError("No such flight.")
    record.state = "closed"
    RECORD.save(record, RECORD.flights_dir())
    if session is not None:
        WORLD_JOB.autostart(session)
    return {"flight": record.id, "state": record.state}


def flight_list(**_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_list``: the records, newest first."""
    return {"flights": [
        {"flight": r.id, "state": r.state, "created_at": r.created_at,
         "origin": (r.origin or {}).get("ident", ""),
         "destination": (r.destination or {}).get("ident", "")}
        for r in RECORD.list_flights(RECORD.flights_dir())]}


def _airport_lookup(ident: str):
    """``(lat, lon)`` of an ident in the engine's airport index (built by
    ``airport_index``); None when the index is missing or lacks it."""
    try:
        import O4_Airport_Index as INDEX
        import O4_File_Names as FNAMES
        for entry in INDEX.load_index(FNAMES.airport_index_cache()):
            if entry.code.upper() == ident:
                return entry.lat, entry.lon
    except Exception:                       # no index: the app sends a place
        return None
    return None


def flight_divert(flight: str = "", to: Any = "alternate", **_ignored
                  ) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_divert`` (see the module)."""
    from .flight_divert import divert_target
    runner = _runner_for(flight)
    if runner is None:
        raise ValueError("That flight is not active.")
    with runner.lock:
        manager = runner.manager
        target, is_alternate = divert_target(to, manager.plan, _airport_lookup)
        name = manager.divert(runner.now(), target, is_alternate,
                              cancel=runner.cancel)
        record = manager.record
    RECORD.save(record, RECORD.flights_dir())
    return {"flight": record.id, "diverted_to": name}


def flight_reload(flight: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_reload`` (see the module): the pilot's
    "Reload scenery now", the only way a flight's reload is sent.
    ``{"flight", "reload"}``."""
    runner = _runner_for(flight)
    if runner is None:
        raise ValueError("That flight is not active.")
    with runner.lock:
        manager = runner.manager
        done = manager.reload_now(runner.now())
        state = (manager.reload if manager.takeoff_at is None
                 else manager.air.state)
    if not done:
        raise ValueError("No scenery reload is waiting.")
    return {"flight": manager.record.id, "reload": state}


def start_flight_plan_simbrief(emit: Callable[[Any], None], request: Any = None,
                               user: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``flight_plan_simbrief``: ``{"status": "started"}``,
    then ``FlightReady`` with the plan (``request`` = this command's id)."""
    from .events import FlightReady
    user = (user or "").strip()
    if not user:
        raise ValueError("Enter your SimBrief username or pilot ID.")

    def work() -> None:
        try:
            result = plan_wire(FP.fetch_simbrief(user))
        except Exception as error:          # the sentence goes to the app
            emit(FlightReady(request=request, error=str(error) or repr(error)))
            return
        emit(FlightReady(request=request, result=result))
    threading.Thread(target=work, daemon=True, name="o4-simbrief").start()
    return {"status": "started"}


def flight_handlers(session) -> Dict[str, Callable]:
    """The flight's entries for the command table (capability
    ``flight_manager``)."""
    emit = session._emit
    return {
        "flight_plan_simbrief": lambda **kw: start_flight_plan_simbrief(
            emit, **kw),
        "flight_create": lambda **kw: flight_create(session, emit, **kw),
        "flight_status": flight_status,
        "flight_update": flight_update,
        "flight_end": lambda **kw: flight_end(session, **kw),
        "flight_list": flight_list,
        "flight_divert": flight_divert,
        "flight_reload": flight_reload,
    }
