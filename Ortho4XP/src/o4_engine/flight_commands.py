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

The flight's own commands (``flight_create`` ... ``flight_end``) join this
module with the flight manager (lane F1b).
"""

from __future__ import annotations

from typing import Any, Callable, Dict

import O4_Flight_Plan as FP

__all__ = ["flight_plans_list", "flight_plan_read", "plan_wire",
           "flight_plan_handlers"]


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
        "route_km": FP.route_length_km(plan.points()),
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
