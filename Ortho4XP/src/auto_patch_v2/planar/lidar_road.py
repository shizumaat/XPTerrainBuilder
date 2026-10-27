"""THE LIDAR READS THE ROAD UNDER THE COVER (#1280; lane ``ltramp``,
``docs/findings/tunnel-ramps-ltramp.md``) — a mapped bore's mouth where a
credible survey shows the road itself builds no ramp.

A mouth's floor is the ground over the mouth less ``mouth_depth_m``
(owner RULINGS 2026-10-14f) — the DEFAULT for a survey that reads the
COVER over the bore.  A lidar terrain model drops the structure over a
road as it drops a bridge deck: where a bore passes under a taxiway carried
on a berm or a bridge, the survey reads a NOTCH along the bore — the road at
its own level, the cover standing to both sides of it.  There the DEM at
the mouth is the road, and ``mouth_depth_m`` below it digs a ramp under a
road the survey already shows.  MEASURED (dry structure replay, main
59fa7241d): LFPG ``tunnel:-300@0`` (the owner's #1280 site) was floored at
94.81 m under a lidar road reading 101.65 m at its portal and an
intersection at 102.2 m, the berm at 106.7 m; 13 of LFPG's 61 built mouths
read the notch, KCLT's #807 north underpass one, KDEN none.

THE WITNESS IS §45's OWN (``channel_geometry._lidar_cut``, ratified as the
credible-lidar cut reading by owner RULINGS 2026-09-16g): on a CREDIBLE
inset, ground standing ``[channel] object_min_depth_m`` over the lidar floor
on BOTH sides, at a majority of the stations — here along the bore itself,
the ground looked for within the reach the approach's ground is read over
(four ``mouth_depth_m``, §33 (3)). BOTH SIDES is what tells a road under a
cover from a road on a hillside. The stations run the WHOLE bore, end to
end, so a bore's two mouths take one verdict (read from each portal over its
first 30 m, KCLT's underpass of way -31625 under taxiway bridge -71 split:
one mouth built, the other refused); a real tunnel, whose survey reads its
cover over most of its length, never fires. Where it fires, the mouth is
REFUSED by name: the survey is the road from under the cover out along its
approach, so a ramp floored at it carves nothing (it meets the DEM at its
first station) and the ``mouth_depth_m`` default digs 7.5 m under a road
that is already there. The floor reported is the lidar floor at the portal's
first station across the carriageway (``_lidar_floor``). Where the witness
does not fire, nothing changes: ``mouth_depth_m`` under the ground stands.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.frame import XY
from .channel_geometry import _lidar_cut, _lidar_floor

__all__ = ["lidar_road_floor", "lidar_road_refusal"]

#: the station step along the bore (the §45 cut reading's own lateral step)
_STEP_M = 5.0
#: a long bore is read at this many stations spread over its length
_MAX_STATIONS = 200


def _bore_fn(points: _t.Sequence[XY], portal: XY):
    """The bore's line as ``s -> xy`` from its end at ``portal`` inward."""
    from shapely.geometry import LineString, Point
    ln = LineString(points)
    head = Point(points[0]).distance(Point(portal)) <= Point(points[-1]).distance(Point(portal))
    length = ln.length

    def fn(s: float) -> XY:
        q = ln.interpolate(max(0.0, min(length, s if head else length - s)))
        return (q.x, q.y)
    return fn, length


def _stations(length: float, start_m: float) -> list[float]:
    """The bore's stations, end to end (``start_m`` in from each mouth),
    every ``_STEP_M`` or as many as ``_MAX_STATIONS`` spread over it: the
    WHOLE bore is read, so its two mouths take one verdict."""
    lo, hi = min(start_m, length / 2.0), max(length - start_m, length / 2.0)
    n = max(1, min(_MAX_STATIONS, int((hi - lo) // _STEP_M) + 1))
    return [lo + (hi - lo) * k / max(1, n - 1) for k in range(n)] if n > 1 else [lo]


def lidar_road_floor(airport, law: Law, members: _t.Sequence, credible: bool,
                     start_m: float) -> float | None:
    """The lidar's road at the group's mapped portal, or ``None`` where the
    survey does not read it (module doc).  ``members`` are the group's
    ``Mouth``s; EVERY member's bore must read the cut, and the floor is the
    deepest member's (one ramp spans them).  ``start_m`` is the first
    station inside the portal (the rim stand-off, where the build reads the
    mouth's DEM)."""
    if not credible or not members:
        return None
    tn = law.tables.structures.tunnel
    reach = 4.0 * float(tn.mouth_depth_m)
    floors: list[float] = []
    for m in members:
        bore = getattr(m, "bore", None)
        if bore is None or len(bore.points) < 2:
            return None
        fn, length = _bore_fn(bore.points, m.xy)
        ss = _stations(length, start_m)
        if not _lidar_cut(airport, law, fn, ss, reach):
            return None
        f = _lidar_floor(airport, fn, ss[0], max(float(m.width_m), 1.0))
        if f != f:                                   # nan: no DEM
            return None
        floors.append(f)
    return min(floors)


def lidar_road_refusal(floor: float) -> str:
    """The refusal line of a mouth whose road the survey reads (module doc)."""
    return (f"the credible lidar reads the road UNDER the cover (a cut along the bore, the "
            f"§45 witness), {floor:.2f} m at the mapped portal: the survey carries the road "
            f"through at its own level and nothing is cut below it — no ramp, no trench "
            f"(#1280)")
