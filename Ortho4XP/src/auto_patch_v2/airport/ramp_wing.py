"""A WALL IN CONTACT TAKES ITS NEIGHBOUR'S SEAT: THE RAMP WING (#2099 G4 Part S;
spec ``docs/specs/2099-G4.md`` §2 S; RULINGS 2026-11-16b, 16i (4)).

A pack may author a walled ramp's walls as ONE placement at its own anchor,
its zero NOT the mouth group's (measured CYYZ: zero at the upper ground),
butting the far end of a wing already in a mouth's group
(``airport/mouth_group``).  Read alone it is no wing -- its top stands under
``shell_floor_min_m`` over its own zero and nothing of it is within
``contact_epsilon_m`` of the group -- and seated at its own anchor its walls
are buried under the wing they continue.

A piece is a RAMP WING of a group (:func:`ramp_wings`) when it

* is no mouth, no wing and not taken (the caller's ``closed``);
* is all walls (``mouth_group._wall_refusal``, W1);
* has two FACING wall lines no farther apart than ``[tunnel]
  dual_carriageway_max_separation_m`` with a mapped road between them
  (:func:`_facing_road`);
* comes within ``[tunnel.object] wall_face_max_thickness_m`` of a joined
  wing's LAST station (the wing's end away from its mouth).

Its OFFSET Δ is the joined wing's top less its own at their nearest station
pair: its zero is the mouth's zero + the mouth's floor y + Δ
(``MouthGroup.offsets``).  It is REFUSED where its foot at the end nearest
its road's junction, so seated, stands more than ``[design]
frontage_step_max_m`` from the joined wing's foot.  One hop: a ramp wing
joins a wing, never another ramp wing.  Nothing here names a pack, a
resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

import shapely
from shapely.geometry import LineString, MultiLineString, Point

__all__ = ["RampJoin", "ramp_wings", "mapped_roads", "ramp_road"]

XY = tuple[float, float]


class RampJoin(_t.NamedTuple):
    """One ramp wing's join: the ``mouth`` whose group it joins, the ``wing``
    it butts and its ``offset`` Δ (metres; its zero over the wing's)."""

    mouth: str
    wing: str
    offset: float


def mapped_roads(airport) -> tuple[tuple[XY, ...], ...]:
    """The airport's mapped roads (``highway`` ways), polylines in frame
    metres -- the roads a ramp wing's walls line."""
    return tuple(tuple(tuple(p) for p in w.points)
                 for w in getattr(airport, "osm_ways", None) or ()
                 if len(w.points) >= 2 and (w.tags or {}).get("highway"))


def _junctions(road: LineString, roads: _t.Sequence[LineString], tol: float) -> list[Point]:
    """The ends of ``road`` that meet another mapped road within ``tol``."""
    ends = [Point(road.coords[0]), Point(road.coords[-1])]
    return [p for p in ends if any(r is not road and r.distance(p) <= tol for r in roads)]


def _majority_side(road: LineString, pts: _t.Sequence[XY]) -> float:
    """``+1`` / ``-1``: the side of ``road`` most of ``pts`` stand on."""
    from .mouth_group import _side
    vote = sum(math.copysign(1.0, _side(road, Point(x, y))) for x, y in pts)
    return 1.0 if vote >= 0.0 else -1.0


def _facing_road(lines, roads: _t.Sequence[LineString], sep: float
                 ) -> "tuple[LineString, int, int] | None":
    """``(road, i, j)``: two of the wall ``lines`` (``wall_line_feet``) no
    farther apart than ``sep`` with a mapped road between them -- the road
    running farthest inside the pair's hull with the two lines on its two
    sides -- or ``None``."""
    best = None
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            a = [(s[0], s[1]) for s in lines[i][1]]
            b = [(s[0], s[1]) for s in lines[j][1]]
            if len(a) < 2 or len(b) < 2 or LineString(a).distance(LineString(b)) > sep:
                continue
            hull = MultiLineString([a, b]).convex_hull
            for r in roads:
                inside = r.intersection(hull).length
                if inside <= 1.0 or _majority_side(r, a) == _majority_side(r, b):
                    continue
                if best is None or inside > best[0]:
                    best = (inside, r, i, j)
    return None if best is None else best[1:]


def ramp_road(lines, roads: _t.Sequence[LineString], sep: float) -> "LineString | None":
    """The mapped road between a ramp wing's two facing wall ``lines``
    (:func:`_facing_road`), or ``None`` -- the road its walled ramp's floor
    runs along (``planar/wing_cut``, #2099 G4 W)."""
    got = _facing_road(lines, roads, sep)
    return None if got is None else got[0]


def _nearest_pair(wing_lines, lines) -> tuple[tuple, tuple]:
    """The nearest ``(wing station, own station)`` pair."""
    ws = [s for _ln, st in wing_lines for s in st]
    os_ = [s for _ln, st in lines for s in st]
    return min(((w, o) for w in ws for o in os_),
               key=lambda p: (p[0][0] - p[1][0]) ** 2 + (p[0][1] - p[1][1]) ** 2)


def _junction_end(lines, junctions: _t.Sequence[Point]) -> "tuple | None":
    """The end station of ``lines`` nearest a junction, or ``None``."""
    ends = [s for _ln, st in lines if st for s in (st[0], st[-1])]
    if not ends or not junctions:
        return None
    return min(ends, key=lambda s: min(j.distance(Point(s[0], s[1])) for j in junctions))


def _join_refusal(read, lines, wing_lines, roads, law) -> "tuple[float, str | None]":
    """``(Δ, why not)`` for the piece read ``read`` (``_solids``) with wall
    ``lines`` against the joined wing's ``wing_lines`` (module doc)."""
    from .mouth_group import _wall_refusal
    tn = law.tables.structures.tunnel
    why = _wall_refusal(read, law)
    if why is not None:
        return 0.0, why
    face = _facing_road(lines, roads, float(tn.dual_carriageway_max_separation_m))
    if face is None:
        return 0.0, (f"no two facing wall lines within {tn.dual_carriageway_max_separation_m:g} m "
                     f"with a mapped road between")
    w, o = _nearest_pair(wing_lines, lines)
    delta = float(w[7]) - float(o[7])
    end = _junction_end(lines, _junctions(face[0], roads,
                                          float(law.tables.emit.identity.min_distinct_spacing_m)))
    if end is None:
        return delta, "its road meets no other mapped road"
    step = float(end[6]) + delta - float(w[6])
    if abs(step) > float(law.tables.emit.design.frontage_step_max_m):
        return delta, (f"its foot at the road's junction stands {step:+.2f} m from the wing's "
                       f"foot, over frontage_step_max_m")
    return delta, None


def ramp_wings(found, objects, cache, law, closed: _t.AbstractSet[str],
               roads: _t.Sequence[_t.Sequence[XY]] = ()
               ) -> tuple[dict[str, RampJoin], list[str]]:
    """``({ramp wing id: its join}, notes)`` over the mouth groups ``found``
    (``(Mouth, mouth read, wing ids)`` each, ``mouth_group.mouth_groups``):
    the module doc's rule, one note per join and per refusal.  ``roads``:
    the mapped roads (polylines, frame metres)."""
    from .mouth_group import _solids
    from .wall_lines import wall_line_feet
    if not found or not roads:
        return {}, []
    thick = float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    lines_of_road = [LineString(r) for r in roads if len(r) >= 2]
    by_id = {str(o.id): o for o in objects}
    boxes = [(str(o.id), o.plan_bbox) for o in objects
             if str(o.id) not in closed and getattr(o, "plan_bbox", None) is not None
             and not o.plan_bbox.is_empty]
    if not boxes:
        return {}, []
    tree = shapely.STRtree([b for _i, b in boxes])
    out: dict[str, RampJoin] = {}
    notes: list[str] = []
    asked: set[str] = set()
    for m, mread, wings in found:
        for wid in list(wings):
            wing_lines = wall_line_feet(by_id[wid], cache, law, mread[0], floor_y=None)
            for oid, gap in _butting(wing_lines, tree, boxes, by_id, cache, law, thick):
                if oid in asked or oid in wings:
                    continue
                asked.add(oid)
                read = _solids(by_id[oid], cache, law)
                lines = wall_line_feet(by_id[oid], cache, law, mread[0], floor_y=None)
                delta, why = _join_refusal(read, lines, wing_lines, lines_of_road, law)
                head = f"{oid} {by_id[oid].path}: butts wing {wid} of mouth {m.object_id}"
                if why is not None:
                    notes.append(f"{head}, no ramp wing ({why})")
                    continue
                out[oid] = RampJoin(m.object_id, wid, round(delta, 3))
                notes.append(f"{head} {gap:.2f} m from its end -- a ramp wing, its zero "
                             f"{delta:+.2f} m over the wing's (#2099 G4 S)")
    return out, notes


def _butting(wing_lines, tree, boxes, by_id, cache, law, thick: float
             ) -> list[tuple[str, float]]:
    """``[(placement id, gap)]``: every placement whose plan comes within
    ``thick`` of a wing line's LAST station, nearest first."""
    from .mouth_group import _solids
    got: dict[str, float] = {}
    for _ln, st in wing_lines:
        if not st:
            continue
        last = Point(st[-1][0], st[-1][1])
        for k in tree.query(last, predicate="dwithin", distance=thick):
            oid = boxes[int(k)][0]
            read = _solids(by_id[oid], cache, law)
            if read is not None and (d := read[0].distance(last)) <= thick:
                got[oid] = min(got.get(oid, d), d)
    return sorted(got.items(), key=lambda kv: (kv[1], kv[0]))
