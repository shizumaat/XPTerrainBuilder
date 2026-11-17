"""THE CLEARANCE UNDER A GENERATED ROAD BRIDGE (#2141 item 5; owner sim read
2026-11-17 "There's a long road bridge crossing 4 roads here ... that we are
not adding, and should be"; owner 16:50Z "might also be raising the road
embankments on either side for that bridge, not just cutting"; RULINGS
2026-11-16s/t: the OSM bridge tag and the roads it crosses are the
witness, 16y (3): the ends stand on their embankments).

``planar/road_bridge_gen`` asked the survey for a finished cutting: a lower
road ``[bridge] clearance_minimum_m`` under the bridge's lower end.  A
bare-earth survey reads an embankment's crest short of the mapped end and
the bridge's span gone, so a real bridge read as 2.3 m (ESSA ``-55``, a
129 m service bridge over two roads, its east approach climbing 5.2 m in
20 m to the plateau).  The clearance now comes from BOTH sides, split as
the survey shows it:

* THE ENDS STAND ON THE EMBANKMENTS THE SURVEY SHOWS (:func:`_end_level`):
  along each road leaving an end (or the bridge's axis run on) out to
  ``approach_probe_m``, the end stands as high as the survey there less the
  road's grade cap back to the end -- ``max(z(t) - cap * t)`` -- so an
  approach climbing at a lawful grade lifts nothing and an embankment's
  crest beyond a mapped end lifts the end to it.  The X-Plane chain runs on
  along the approach to that crest (:func:`_chain`): its level-0 junction
  drapes on the embankment the survey already carries -- no fill is
  invented (the span is a hole the base mesh fills from the survey).
* THE DECK runs straight between the two end levels (:func:`_deck_at`); the
  X-Plane chain's level-1 junctions ride over it.
* THE LOWER ROADS ARE CUT by what is still short: at each crossing the
  deficit ``clearance_minimum_m - (deck - survey)`` is cut out of the lower
  road under the span, ramped back at ``[tunnel] ramp_grade``.
* WITNESS (16s/16t, :func:`witnessed`): the survey must show at least
  ``witness_share`` of the clearance at some crossing once the ends stand
  on their embankments -- a terminal ramp the survey carries at grade over
  an at-grade road (19 of them at ESSA, spec 2123 Part B note 7) shows
  nothing and is not generated; a crossing showing less is never cut, and
  an end the survey reads rising more than the clearance itself is no
  embankment (a structure or terrace: EDDF's terminal ramps read 8-15 m)
  and stays at its own survey.

The plan is plain data (``ground``: ribbons in frame xy, each an axis, a
half width, a ``(station, level)`` profile and its kind, ``cut``),
read by ``airport/road_bridge_ground`` at the planar and road-profile sites.
Nothing here names an airport.  Build-time impact: a few hundred DEM reads
per bridge candidate, milliseconds.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from shapely.geometry import LineString, Point
from shapely.ops import substring

from ..law.tables import role_cap
from .structure_approach import carriageway_width_m

__all__ = ["ClearancePlan", "clearance_plan", "witnessed"]

#: the spacing of the approach probe (metres)
_PROBE_STEP_M = 2.0
#: an end within this of a road's end is that road's end (metres)
_JOIN_M = 0.5


@_dc.dataclass(frozen=True)
class ClearancePlan:
    """A bridge's ends, its witnessed clearance and the ground it reshapes."""

    ends: tuple[float, float]             # surveyed z at the mapped ends
    levels: tuple[float, float]           # the ends on their embankments
    witnessed: float                      # the best crossing's survey clearance
    crossings: tuple[tuple[str, float, float, float], ...]   # (way, s, survey z, deficit)
    ground: tuple[dict, ...]              # ribbons (module doc)
    chain: "LineString | None" = None     # the axis run on to the crests

    def note(self) -> str:
        cr = ", ".join(f"{w} short {max(0.0, d):.1f} m" for w, _s, _z, d in self.crossings)
        return (f"ends {self.ends[0]:.1f}/{self.ends[1]:.1f} m stand on their embankments "
                f"at {self.levels[0]:.1f}/{self.levels[1]:.1f} m, survey clearance "
                f"{self.witnessed:.1f} m; {cr}")


def _dem(dem, x: float, y: float) -> "float | None":
    z = float(dem.z(float(x), float(y)))
    return z if math.isfinite(z) else None


def _outward(ln: LineString, end) -> LineString:
    """``ln`` oriented to leave the point ``end``."""
    return ln if Point(ln.coords[0]).distance(end) <= Point(ln.coords[-1]).distance(end) \
        else LineString(ln.coords[::-1])


def _approaches(line: LineString, k: int, roads, reach: float) -> list[LineString]:
    """The roads leaving end ``k`` (0 or -1) of ``line`` -- each mapped
    road whose end meets it, its first ``reach`` metres -- or, with none,
    the bridge's own axis run on ``reach`` past it."""
    end = Point(line.coords[k])
    out = []
    for r in roads:
        if r.equals(line) or min(Point(r.coords[0]).distance(end),
                                 Point(r.coords[-1]).distance(end)) > _JOIN_M:
            continue
        r = _outward(r, end)
        out.append(substring(r, 0.0, min(reach, r.length)))
    if out:
        return out
    (x0, y0), (x1, y1) = (line.coords[1], line.coords[0]) if k == 0 \
        else (line.coords[-2], line.coords[-1])
    n = math.hypot(x1 - x0, y1 - y0) or 1.0
    return [LineString([(x1, y1), (x1 + (x1 - x0) / n * reach, y1 + (y1 - y0) / n * reach)])]


def _end_level(dem, approaches, cap: float) -> tuple[float, "LineString | None", float]:
    """``(level, approach, knee station)``: the end on its embankment (module
    doc) -- ``max(z(t) - cap * t)`` over every approach's probe stations
    (``t`` = 0 the mapped end) -- and the approach and station it is read
    at (``None``, 0 where the end's own survey stands)."""
    z0 = None
    best: tuple = (-math.inf, None, 0.0)
    for ap in approaches:
        t = 0.0
        while t <= ap.length + 1e-9:
            p = ap.interpolate(t)
            z = _dem(dem, p.x, p.y)
            if z is not None:
                if t == 0.0 and z0 is None:
                    z0 = z
                if z - cap * t > best[0]:
                    best = (z - cap * t, ap, t)
            t += _PROBE_STEP_M
    if best[1] is None or (z0 is not None and best[0] <= z0 + 1e-6):
        return (z0 if z0 is not None else best[0]), None, 0.0
    return best


def _deck_at(levels: tuple[float, float], length: float, s: float) -> float:
    """The deck's level ``s`` along a bridge ``length`` long, straight
    between its two end levels."""
    w = 0.0 if length <= 1e-9 else min(1.0, max(0.0, s / length))
    return levels[0] + w * (levels[1] - levels[0])


def _ribbon(kind: str, axis: LineString, half: float, prof) -> dict:
    return {"kind": kind, "axis": [[round(x, 3), round(y, 3)] for x, y in axis.coords],
            "half": round(float(half), 3),
            "prof": [[round(float(s), 3), round(float(z), 4)] for s, z in prof]}


def _chain(line: LineString, reach: list) -> LineString:
    """The bridge's axis run on along each approach to its crest
    (``reach[k]``: the approach from end ``k`` out to its knee, ``None``
    where the end stands on its own survey) -- the X-Plane chain's line,
    its level-0 junctions on the embankments the survey shows."""
    pts = list(line.coords)
    if reach[0] is not None:
        pts = list(reach[0].coords)[::-1][:-1] + pts
    if reach[1] is not None:
        pts = pts + list(reach[1].coords)[1:]
    return LineString(pts)


def _cut_ribbon(road: LineString, q: Point, floor: float, survey: float, flat: float,
                half: float, grade: float) -> dict:
    """The lower road cut to ``floor`` for ``flat`` metres each side of the
    crossing ``q``, ramped back to its survey at ``grade``."""
    s = road.project(q)
    run = max(0.0, survey - floor) / grade
    a, b = max(0.0, s - flat - run), min(road.length, s + flat + run)
    axis = substring(road, a, b)
    s -= a
    return _ribbon("cut", axis, half, [(s - flat - run, survey), (s - flat, floor),
                                       (s + flat, floor), (s + flat + run, survey)])


def clearance_plan(airport, law, w, line: LineString, lower) -> "ClearancePlan | None":
    """The plan for the bridge ``w`` (axis ``line``) over ``lower`` --
    ``[(way id, way line, crossing point, way tags)]`` (module doc);
    ``None`` where the survey reads nothing there."""
    dem = getattr(airport, "dem", None)
    if dem is None or not lower:
        return None
    rg = law.tables.structures.road_gen
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    cap = float(role_cap(law, "service_road").longitudinal)
    shoulder = float(law.tables.structures.deck_gen.shoulder_m)
    half = carriageway_width_m(w.tags, law) / 2.0 + shoulder
    roads = [LineString(o.points) for o in getattr(airport, "osm_ways", ()) or ()
             if len(o.points) >= 2 and (o.tags or {}).get("highway")]
    ends, levels, ribbons, reach = [], [], [], []
    for k in (0, -1):
        raw = _dem(dem, *line.coords[k])
        if raw is None:
            return None
        aps = _approaches(line, k, roads, float(rg.approach_probe_m))
        level, ap, knee = _end_level(dem, aps, cap)
        if ap is None or level - raw > clear:
            # a rise past the clearance it would serve is no embankment: a
            # structure or a terrace the survey carries (MEASURED EDDF: the
            # terminal ramps' approaches read 8-15 m up within 30 m)
            level, ap = raw, None
        ends.append(raw)
        levels.append(level)
        reach.append(substring(ap, 0.0, knee) if ap is not None and knee > 0.0 else None)
    crossings, best = [], -math.inf
    flat = half + float(rg.span_margin_m)
    for wid, oline, q, otags in lower:
        zq = _dem(dem, q.x, q.y)
        if zq is None:
            continue
        s = line.project(q)
        deck = _deck_at((levels[0], levels[1]), line.length, s)
        best = max(best, deck - zq)
        crossings.append((wid, s, zq, clear - (deck - zq)))
        if 0.0 < clear - (deck - zq) <= (1.0 - float(rg.witness_share)) * clear:
            # a crossing the survey shows under the deck takes the rest as a
            # cut; one it does not (an at-grade road, a lower tag the survey
            # contradicts) is never cut deeper than the witness allows
            oh = carriageway_width_m(otags, law) / 2.0 + shoulder
            ribbons.append(_cut_ribbon(oline, q, deck - clear, zq, flat, oh,
                                       float(law.tables.structures.tunnel.ramp_grade)))
    if not crossings:
        return None
    return ClearancePlan((ends[0], ends[1]), (levels[0], levels[1]), best,
                         tuple(crossings), tuple(ribbons), _chain(line, reach))


def witnessed(plan: "ClearancePlan | None", law) -> bool:
    """The survey shows the grade separation (module doc, WITNESS)."""
    if plan is None:
        return False
    rg = law.tables.structures.road_gen
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    return plan.witnessed >= float(rg.witness_share) * clear
