"""THE DOOR-LINE PAD: a building on a sloping apron (owner 2026-10-20
01:15Z / 01:17Z; RULINGS 2026-10-19ak / 19w; issue #798).

Owner: "When you have a hangar on a slope, we're concerned with aircraft
being able to taxi in and out of the hangar door ... the slope of the apron
to the center of the door that the aircraft would follow needs to stay
within grade limits, but laterally either edge of the building away from
that center line can carry the extra slope to blend back into the apron,
so the majority of the apron stays within grade, but with small steeper
ramps at the building high and low side, smoother in the middle."  And the
blend "like a tunnel ramp, let's allow up to 10%, with the goal being the
smallest possible"; the same rule for a building with no aircraft door.

THE WITNESS (:func:`door_pads`).  A building pad (``building`` faces of one
ref) under ``[placement] cluster_pad_min_m2`` whose ring runs at least
``[placement] apron_shelf_min_share`` along the apron (23a welds it there)
and whose seat would float more than ``[placement] slope_pad_float_m`` on
the ground under it (``geom/slope_pad`` — the 19w reading).

THE RULE.
* ONE LEVEL: every vertex of the pad is one ``Flat`` group
  (:func:`door_pad_level`), as §42 (1b)'s hard plane is — the vertices it
  shares with the runway or taxi family are left out, the weld being
  carried by the ordinary rows across that edge.  Its level is the solve's:
  the apron's rows choose it.
* THE DOOR LINE: the door wall is the pad's hull edge nearest the taxi
  family (no open-side reading yet: the pack's wall geometry is not read
  here); the corridor is the line from that wall's centre to the nearest
  taxi-family point, ``[placement] door_corridor_share`` of the wall wide.
  Its apron rows keep their cap.
* THE BLEND: the apron's HARD cap rows with one end ON THE PAD'S RIM
  outside the corridor are raised to ``[tunnel] ramp_max_grade``
  (:func:`relax_apron_caps`): the ramps run from the pad's edge, and the
  apron away from the pad keeps its own cap between its own vertices.
  MEASURED (KASE replay): relaxing every apron vertex within a reach of the
  pad let the apron's outer edge east of Hangar1 hump 0.5 m (a +2.8 / -8.9 %
  grade break, the §1.2 rate read 11.7 %).  The apron's preference and
  trend rows are untouched, so the ramps stay as gentle as the levels
  allow.  Taxi and runway rows are never relaxed.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

from ..geom.slope_pad import seat_float_m
from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Diff, Flat, Row, Source
from ..model.planar import PlanarMap

__all__ = ["DoorPad", "door_pads", "door_pad_level", "relax_apron_caps", "GEN"]

GEN = "door_pad_level"
RULING = ("a sloping building's pad is ONE level, the apron keeping its cap "
          "along the door line and blending elsewhere (owner 2026-10-20)")

STATS: dict[str, _t.Any] = {}
#: the last map's door-line pad refs, for the report
REFS: list[str] = []


@_dc.dataclass(frozen=True)
class DoorPad:
    ref: str
    group: tuple[int, ...]
    blend: frozenset[int]
    door: tuple[float, float]
    #: the door line: the pad vertex at the door's centre, the taxi-family
    #: vertex it leads to, their distance and the apron cap it keeps
    door_v: int = -1
    taxi_v: int = -1
    door_m: float = 0.0
    door_cap: float = 0.0


_MEMO: list[tuple[int, _t.Any, list]] = []


def _poly(planar: PlanarMap, ring) -> Polygon:
    g = Polygon([planar.vertices[v].xy for v in planar.ring_vertices(ring)])
    return g if g.is_valid else g.buffer(0.0)


def door_pads(planar: PlanarMap, law: Law, airport: Airport) -> list[DoorPad]:
    """The door-line pads of the map (module docstring), memoised per map."""
    for k, pm, got in _MEMO:
        if k == id(planar) and pm is planar:
            return got
    got = _derive(planar, law, airport)
    _MEMO.append((id(planar), planar, got))
    del _MEMO[:-2]
    return got


def _derive(planar: PlanarMap, law: Law, airport: Airport) -> list[DoorPad]:
    st = law.tables.structures.placement
    share_c = float(getattr(st, "door_corridor_share", 0.0) or 0.0)
    t = float(getattr(st, "slope_pad_float_m", 0.0) or 0.0)
    min_m2 = float(st.cluster_pad_min_m2)
    share = float(getattr(st, "apron_shelf_min_share", 0.0) or 0.0)
    dem = getattr(airport, "dem", None) if airport is not None else None
    STATS[GEN] = {"pads": 0}
    if share_c <= 0.0 or t <= 0.0 or min_m2 <= 0.0 or dem is None:
        return []
    p = law.tables.precedence
    king = set(p.runway_family.members) | set(p.taxi_family.members)
    pads: dict[str, list] = {}
    apron_v: set[int] = set()
    apron_g, king_g, king_v = [], [], set()
    for f in planar.faces.values():
        vs = set(planar.ring_vertices(f.ring))
        for h in f.holes:
            vs.update(planar.ring_vertices(h))
        if f.role == "building":
            pads.setdefault(str(f.ref), []).append(f)
        elif f.role == "apron":
            apron_v.update(vs)
            apron_g.append(_poly(planar, f.ring))
        elif f.role in king:
            king_v.update(vs)
            king_g.append(_poly(planar, f.ring))
    if not pads or not apron_v or not king_g:
        return []
    king_u = unary_union(king_g)
    out: list[DoorPad] = []
    for ref, fs in sorted(pads.items()):
        P = unary_union([_poly(planar, f.ring) for f in fs])
        if P.is_empty or P.area >= min_m2:
            continue
        rim = set()
        for f in fs:
            rim.update(planar.ring_vertices(f.ring))
        on = sum(1 for v in rim if v in apron_v)
        if not rim or on < share * len(rim):
            continue
        if seat_float_m(P, dem.z) <= t:
            continue
        hull = P.convex_hull
        cs = list(hull.exterior.coords)[:-1]
        walls = [LineString([cs[i], cs[(i + 1) % len(cs)]]) for i in range(len(cs))]
        door = min(walls, key=lambda w: w.interpolate(0.5, normalized=True)
                   .distance(king_u))
        mid = door.interpolate(0.5, normalized=True)
        tp = nearest_points(mid, king_u)[1]
        line = LineString([hull.centroid, mid, tp]) if mid.distance(tp) > 0 else \
            LineString([hull.centroid, mid])
        corridor = line.buffer(0.5 * share_c * door.length)
        blend = {v for v in rim
                 if not corridor.contains(Point(planar.vertices[v].xy))}
        # EVERY vertex of the pad, the ones it shares with a taxiway too:
        # the tower's door wall IS a junction's edge, and a pad left uneven
        # along it is no level pad (measured, KASE replay: 0.39 m)
        group = tuple(sorted(v for f in fs for v in _face_vertices(planar, f)))
        if len(group) < 2:
            continue
        door_v = min(group, key=lambda v: mid.distance(Point(planar.vertices[v].xy)))
        taxi_v = min(king_v, key=lambda v: tp.distance(Point(planar.vertices[v].xy)))
        # the pad is ONE level, so its value at the door's centre is the
        # door vertex's: the line is priced over the CENTRE's own distance
        dxy = mid.distance(Point(planar.vertices[taxi_v].xy))
        out.append(DoorPad(ref, group, frozenset(blend), (mid.x, mid.y),
                           door_v, taxi_v, float(dxy), _door_cap(planar, law, mid)))
    STATS[GEN] = {"pads": len(out),
                  "blend_vertices": sum(len(d.blend) for d in out)}
    REFS[:] = [d.ref for d in out]
    return out


def _door_cap(planar: PlanarMap, law: Law, at: Point) -> float:
    """The apron cap the door line keeps: the hard longitudinal cap of the
    apron face nearest the door (its yielded cap where its runway yielded,
    §50.1 (4) — ``precedence.view``'s own reading)."""
    from .precedence import view
    vw = view(planar, law)
    best, cap = None, 0.0
    for f in planar.faces.values():
        if f.role != "apron" or vw.caps.get(f.id) is None:
            continue
        d = _poly(planar, f.ring).distance(at)
        if best is None or d < best:
            best, cap = d, float(vw.caps[f.id][0])
    return cap


def _face_vertices(planar: PlanarMap, f) -> set[int]:
    vs = set(planar.ring_vertices(f.ring))
    for h in f.holes:
        vs.update(planar.ring_vertices(h))
    return vs


def door_pad_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ONE ``Flat`` per door-line pad, and its DOOR LINE: the pad at the
    door's centre within the apron cap of the taxi-family vertex the line
    leads to — HARD, so the pad's level is chosen where an aircraft can
    still taxi in (module docstring)."""
    rows: list[Row] = []
    for d in door_pads(planar, law, airport):
        rows.append(Flat(d.group, Source(GEN, RULING, (d.ref, f"vertices:{len(d.group)}"))))
        if d.door_v >= 0 and d.taxi_v >= 0 and d.door_v != d.taxi_v \
                and d.door_m > 0.0 and d.door_cap > 0.0:
            rows.append(Diff(d.door_v, d.taxi_v, d.door_cap, d.door_m,
                             Source(GEN, RULING + " (the door line)",
                                    (d.ref, f"door:{d.door_v}", f"taxi:{d.taxi_v}"))))
    return rows


def relax_apron_caps(rows: list[Row], planar: PlanarMap, law: Law,
                     airport: Airport, counts: dict | None = None) -> list[Row]:
    """The APRON generator's HARD cap rows (``constraints/apron``) with a
    foot in a door pad's blend raised to ``[tunnel] ramp_max_grade``
    (module docstring); every other row as is."""
    from .apron import GEN as APRON_GEN
    pads = door_pads(planar, law, airport)
    if not pads:
        return rows
    blend = frozenset().union(*(d.blend for d in pads))
    top = float(law.tables.structures.tunnel.ramp_max_grade)
    out: list[Row] = []
    n = 0
    for r in rows:
        if (isinstance(r, Diff) and r.soft is None and r.cap < top
                and r.source.generator == APRON_GEN
                and (r.a in blend or r.b in blend)):
            out.append(_dc.replace(r, cap=top))
            n += 1
        else:
            out.append(r)
    if counts is not None:
        counts[f"{GEN}.apron_rows_relaxed"] = n
    return out
