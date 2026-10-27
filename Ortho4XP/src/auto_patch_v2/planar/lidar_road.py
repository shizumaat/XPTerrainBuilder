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
cover over most of its length, never fires. Where it fires (owner RULINGS
2026-10-27g, amending 14f for surveyed
underpasses: "As long as the depth is at least 5m below the taxiway/bridge
deck, then we can leave, it otherwise a gentle blended additional cut can be
added, but not 7m in addition to the existing cut"): the DECK is the cover's
top at the crossing — the highest lower-side ground the reading found along
the bore — and the road the survey floor under it. A road standing
``[tunnel] clearance_m`` or more under its deck is KEPT: the mouth is
refused by name, nothing is cut. A shallower one is cut by only the depth
owed: the mouth's floor is the surveyed road at the portal less that
extra, and the ramp climbs from it at the design grade (``ramp_grade``,
the road's own ramp law) to the ground — never ``mouth_depth_m`` under the
surveyed road. Where the witness does not fire, nothing changes:
``mouth_depth_m`` under the ground stands.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..model.frame import XY
from .channel_geometry import _lidar_cut, _lidar_floor

__all__ = ["lidar_road", "lidar_road_refusal", "lidar_road_note"]

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


@_dc.dataclass(frozen=True)
class LidarRoad:
    """The survey's reading of a road under its cover (module doc):
    ``floor`` the road at the group's mapped portal; ``deck`` the cover's
    top at the crossing (the highest lower-side ground along the bore) and
    ``road`` the road under it; ``clearance`` their difference; ``extra``
    the depth still owed to ``[tunnel] clearance_m`` (0 = the road is
    kept)."""
    floor: float
    deck: float
    road: float
    clearance: float
    extra: float

    @property
    def mouth_floor(self) -> float:
        """The floor a blended cut builds the mouth at."""
        return self.floor - self.extra


def lidar_road(airport, law: Law, members: _t.Sequence, credible: bool,
               start_m: float) -> LidarRoad | None:
    """The survey's reading of the group's road under its cover, or
    ``None`` where the survey does not read it (module doc).  ``members``
    are the group's ``Mouth``s; EVERY member's bore must read the cut; one
    ramp spans them, so the floor is the deepest member's and the depth
    owed the largest.  ``start_m`` is the first station inside the portal
    (the rim stand-off, where the build reads the mouth's DEM)."""
    if not credible or not members:
        return None
    tn = law.tables.structures.tunnel
    reach = 4.0 * float(tn.mouth_depth_m)
    depth = float(law.tables.structures.channel.object_min_depth_m)
    got: list[LidarRoad] = []
    for m in members:
        bore = getattr(m, "bore", None)
        if bore is None or len(bore.points) < 2:
            return None
        fn, length = _bore_fn(bore.points, m.xy)
        ss = _stations(length, start_m)
        rows: list = []
        if not _lidar_cut(airport, law, fn, ss, reach, rows):
            return None
        f = _lidar_floor(airport, fn, ss[0], max(float(m.width_m), 1.0))
        cut = [r for r in rows if r[2] - r[1] >= depth]
        if f != f or not cut:                        # nan: no DEM
            return None
        _s, road, deck = max(cut, key=lambda r: r[2])
        clear = deck - road
        got.append(LidarRoad(f, deck, road, clear, max(0.0, float(tn.clearance_m) - clear)))
    worst = max(got, key=lambda r: r.extra)
    return _dc.replace(worst, floor=min(r.floor for r in got))


def lidar_road_refusal(rd: LidarRoad) -> str:
    """The refusal line of a mouth whose road the survey keeps."""
    return (f"the credible lidar reads the road UNDER the cover (a cut along the bore, the "
            f"§45 witness), {rd.floor:.2f} m at the mapped portal, {rd.clearance:.2f} m under "
            f"the cover's top {rd.deck:.2f} at the crossing (>= clearance_m): the survey "
            f"carries the road through at its own level and nothing is cut — no ramp, no "
            f"trench (#1280, RULINGS 2026-10-27g)")


def lidar_road_note(rd: LidarRoad) -> str:
    """The tunnel note of a mouth whose surveyed road is blend-cut."""
    return (f"surveyed road {rd.road:.2f} stands {rd.clearance:.2f} m under the cover's top "
            f"{rd.deck:.2f} (< clearance_m): only the {rd.extra:.2f} m owed is cut — floor "
            f"{rd.mouth_floor:.2f} at the mouth, climbing at the design grade (RULINGS "
            f"2026-10-27g; never mouth_depth_m under the surveyed road)")
