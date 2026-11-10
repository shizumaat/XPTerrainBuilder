"""A flight's diversion (spec flight-manager-and-world-20261110 §4.3 step
8, §8.6; lane F2): where to, and the leg the flight now flies.

* :func:`divert_target` -- the pilot's choice (``flight_divert {to}``) as
  a waypoint: ``"alternate"`` (the plan's), an airport ``{ident, lat,
  lon}`` from the app's airport search, ``[lat, lon]``, or a bare ident
  resolved through ``lookup`` (the engine's airport index).
* :func:`divert_leg` -- the leg to the new airport: from the aircraft
  when it has taken off (its deadlines counted on from the time flown),
  else from the departure (the destination simply changes before
  takeoff).  The diversion airport's tile is built ``full`` in class P0
  (§8.6).
* :func:`merge_after_divert` -- the new leg's jobs with what the old route
  had under way: a tile built, staged or building keeps its state; the
  old destination's build stops (``cancel``) unless the new leg still
  needs its tile (it is the alternate); queued tiles the new leg does not
  need are shed.

Pure: no files, no clock.  No airport is named here.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterable, List, NamedTuple, Optional, Tuple

import O4_Flight_Plan as FP

__all__ = ["Leg", "divert_target", "divert_leg", "merge_after_divert"]

Tile = Tuple[int, int]
#: States the old route's jobs keep when the new leg does not list them.
_KEPT = frozenset({"building", "staged", "swapped", "external", "failed"})


class Leg(NamedTuple):
    """The leg the flight flies after a diversion.  ``start_s`` seconds
    after takeoff it starts; ``airborne`` = from the aircraft (no
    departure role, no first window to build before the flight loads)."""
    start_s: float = 0.0
    airborne: bool = False
    diverted: bool = False


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("That airport has no position.") from error


def divert_target(to: Any, plan: "FP.FlightPlan",
                  lookup: Optional[Callable[[str], Optional[Tuple[float, float]]]]
                  = None) -> Tuple["FP.Waypoint", bool]:
    """``(waypoint, is_alternate)`` of the pilot's choice (see the
    module); a choice that names no place raises ``ValueError`` with the
    sentence for the user."""
    alternate = plan.alternate
    if to in (None, "", "alternate"):
        if alternate is None:
            raise ValueError("This flight has no alternate: choose an airport.")
        return alternate, True
    if isinstance(to, dict):
        point = FP.Waypoint(str(to.get("ident") or "").upper(),
                            _number(to.get("lat")), _number(to.get("lon")))
    elif isinstance(to, (list, tuple)) and len(to) == 2:
        point = FP.Waypoint("", _number(to[0]), _number(to[1]))
    else:
        ident = str(to).strip().upper()
        found = lookup(ident) if lookup is not None else None
        if not found:
            raise ValueError("No airport %s in X-Plane's airport list." % ident)
        point = FP.Waypoint(ident, float(found[0]), float(found[1]))
    if not (-90 <= point.lat <= 90 and -180 <= point.lon <= 180):
        raise ValueError("That airport has no position.")
    same = alternate is not None and (
        (bool(point.ident) and point.ident == alternate.ident)
        or abs(point.lat - alternate.lat) + abs(point.lon - alternate.lon) < 1e-4)
    return point, bool(same)


def divert_leg(plan: "FP.FlightPlan", target: "FP.Waypoint",
               position: Optional[Tuple[float, float]],
               flown_s: Optional[float], is_alternate: bool
               ) -> Tuple["FP.FlightPlan", Leg]:
    """The plan of the leg to ``target`` and its :class:`Leg` (see the
    module).  ``flown_s`` is None before takeoff.  The plan keeps its
    alternate unless the flight diverts to it."""
    alternate = None if is_alternate else plan.alternate
    keep = dict(source=plan.source, alternate=alternate,
                cruise_ms=plan.cruise_ms, cruise_alt_ft=plan.cruise_alt_ft)
    if flown_s is not None and position is not None:
        start = FP.Waypoint("", float(position[0]), float(position[1]))
        return (FP.FlightPlan([start, target], **keep),
                Leg(start_s=max(0.0, float(flown_s)), airborne=True,
                    diverted=True))
    return (FP.FlightPlan([plan.waypoints[0], target], **keep),
            Leg(diverted=True))


def merge_after_divert(old: Iterable[Any], new: Iterable[Any],
                       old_destination: Tile,
                       cancel: Callable[[Tile], Any]) -> List[Any]:
    """The jobs after a diversion (see the module): ``new`` with the old
    jobs' progress; ``cancel(tile)`` stops the old destination's build at
    its next step boundary."""
    old = {j.tile: j for j in old}
    merged = []
    for job in new:
        prior = old.pop(job.tile, None)
        if prior is not None and prior.state in _KEPT and (
                prior.kind == job.kind or prior.kind == "full"):
            # built or under way: kept (a full tile stays full; an
            # intermediate one under the new destination is built full)
            job = replace(job, kind=prior.kind, state=prior.state,
                          est_s=prior.est_s)
        merged.append(job)
    for tile, prior in sorted(old.items()):
        if prior.role == "destination":     # one destination: the new one
            prior = replace(prior, role="enroute")
        if tile == tuple(old_destination):
            if prior.state == "building":
                cancel(tile)
            if prior.state in ("queued", "building", "late"):
                prior = replace(prior, state="shed")
        elif prior.state not in _KEPT:
            prior = replace(prior, state="shed")
        merged.append(prior)
    return merged
