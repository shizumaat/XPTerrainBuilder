"""A WALLED TRENCH UNDER AIRSIDE PAVEMENT IS CUT TO ITS WALLS (#2099 Part
F2; owner RULINGS 2026-11-15j "should be cut based on the walls", 2026-10-19p
"a pack-stated tunnel/wall object keeps cutting the pavement inside its own
walls"; spec ``docs/specs/2099-F.md``).

A pack may model a sunken road by its two WALLS alone -- no floor plate, no
roof -- running through an apron (MEASURED CYYZ ``Tx_A``: two walls 8.0 m
under the zero, 330 m long, 15-30 m apart, a service road and the apron
drawn over the 4,587 m2 between them, a mapped tunnel ending at a notch in
one wall).  The mapped mouth's opening read 0.39 m there and its ramp
stopped at the apron (#971), so the trench was buried.

THE WITNESS (geometry, never a name).  A trench object (``trench_objects``:
walls ``shell_floor_min_m`` or more under its zero, no storey over it, at a
mapped road's end), no hard deck, whose mapped mouth the entrance reader
could not read (its opening under one road lane: RULINGS 2026-11-16a, the
pin's ``opening_misread``) and whose deep walls stand on BOTH sides of an
open floor: the plan between them -- the hull of its deep walls less the
walls -- is lined by them over ``floor_walled_min_share`` of its ring, and
no stretch of that ring no wall lines is longer than the floor is wide (the
largest circle inside it): a trench's open ends, never the chord across a
single retaining wall's bend.  The floor is cut out of every cell drawn over it, the airside
pavement included (19p), never the runway family (``object_floor_cells``).

THE FLOOR.  The walls state it with their feet (``clearance_m = 0``, as a
deck stack's walls), read as SECTIONS (#2099 F2 P2): each wall line of the
object (``airport/wall_lines.wall_line_feet``, no clamp on the foot; a
station whose section is wider than twice ``wall_face_max_thickness_m`` --
a corner, a headwall's junction -- is not read, :func:`_wall_lines`) faces
the floor, and each
corner of the floor's triangulation (its ring densified every
``wall_sample_m``) stands at the zero plus the foot along the wall line it
faces, linear between stations and linear across two facing lines
(``model/wing_cut.wing_floor_y``), never outside the walls' lowest and
highest foot.  MEASURED CYYZ ``Tx_A`` (lcyyzF): the lowest y of any deep
triangle within 2 m put a plinth's 162.0-162.3 on one side and 159.31 on
the other, and the west wall's floor was not level.  THE SEAT: the walls' top
along the floor's ring lands on the ground the walls retain (the median,
over the walled ring, of the highest DEM within twice ``bore_end_tolerance_m``
-- the entrance reader's own reach, ``trench_objects._ground_max``): ``zero
= ground - top``.  The result is one :class:`object_floor.ObjectFloor` that every
consumer of an object floor reads unchanged (cells cut out of the pavement,
pins, portals, seats).

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.ops import unary_union

from . import obj8 as _obj8
from .trench_objects import _ground_max

__all__ = ["walled_trench_floors"]

#: the ring's sampling step (metres) for the feet, the tops and the ground
_STEP_M = 1.0
#: the ground is read at every this-many walled ring samples
_GROUND_EVERY = 5


def _all_solids(o, g):
    """``(placed xy (n, 3, 2), y (n, 3))`` of every solid triangle of ``o``."""
    v, t = g.vertices, g.solid
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    return np.stack([px[t], py[t]], axis=-1), v[t, 1]


def _deep_solids(o, g, law):
    """``(placed xy (n, 3, 2), y (n, 3))`` of ``o``'s solid triangles hanging
    ``shell_floor_min_m`` or more under its zero, or ``None``."""
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    if t is None or not len(t):
        return None
    t = t[v[t, 1].min(axis=1) <= -float(ob.shell_floor_min_m)]
    if not len(t):
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    return np.stack([px[t], py[t]], axis=-1), v[t, 1]


def _between(xy, law):
    """The plan between the deep walls: their hull less their plan, the
    largest part (``None`` where none), its ring simplified within a tenth
    of the margin it keeps off the walls (#2237: the ring traced every wall
    triangle's buffered corner -- MEASURED CYYZ ``Tx_A`` 179 points, 42 so,
    1.2 m2 off its 4,587)."""
    tk = float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    tris = shapely.polygons(xy)
    segs = shapely.linestrings(np.concatenate([xy, xy[:, :1]], axis=1))
    walls = unary_union([g for g in (*tris[shapely.area(tris) > 1e-6], *segs)
                         if not g.is_empty]).buffer(0.25 * tk)
    rest = walls.convex_hull.difference(walls)
    parts = [p for p in getattr(rest, "geoms", [rest])
             if p.geom_type == "Polygon" and not p.is_empty]
    if not parts:
        return None
    best = max(parts, key=lambda p: p.area)
    thin = best.simplify(0.025 * tk)
    return thin if thin.is_valid and thin.geom_type == "Polygon" and not thin.is_empty else best


def _ring_samples(poly) -> np.ndarray:
    """Points every :data:`_STEP_M` round ``poly``'s exterior."""
    ring = poly.exterior
    n = max(8, int(math.ceil(ring.length / _STEP_M)))
    pts = shapely.line_interpolate_point(ring, (np.arange(n) + 0.5) * (ring.length / n))
    return np.array([(p.x, p.y) for p in pts])


def _walled(samples: np.ndarray, xy, tk: float) -> np.ndarray:
    """Which of ``samples`` stand within ``tk`` of a deep wall triangle."""
    tree = shapely.STRtree(shapely.polygons(xy).tolist())
    hit = tree.query(shapely.points(samples), predicate="dwithin", distance=tk)[0]
    out = np.zeros(len(samples), bool)
    out[np.unique(hit)] = True
    return out


def _foot_top(samples: np.ndarray, xy, y, tk: float) -> tuple[np.ndarray, np.ndarray]:
    """Per sample: the lowest and the highest y of the deep wall triangles
    within ``tk`` of it (``nan`` where none)."""
    tree = shapely.STRtree(shapely.polygons(xy).tolist())
    feet = np.full(len(samples), np.nan)
    tops = np.full(len(samples), np.nan)
    pi, ti = tree.query(shapely.points(samples), predicate="dwithin", distance=tk)
    for k in np.unique(pi):
        sel = ti[pi == k]
        feet[k] = float(y[sel].min())
        tops[k] = float(y[sel].max())
    return feet, tops


def _wall_lines(o, cache, law, floor) -> list:
    """``model/wing_cut.WallLine`` per wall line of ``o`` (module doc),
    its face toward ``floor``.  A station whose section is wider than
    TWICE ``wall_face_max_thickness_m`` is not read: a section across a
    corner or a junction (MEASURED CYYZ ``Tx_A``: 26-105 m), never a wall
    and its footing (the east wall's sections 1.93-2.73 m: at the face's
    own 2.0 m, 167 of its 169 stations went unread and its floor took the
    west wall's feet, up to 1.1 m off)."""
    from .wall_lines import wall_line, wall_line_feet
    wide = 2.0 * float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    out = []
    for k, (_ln, st) in enumerate(wall_line_feet(o, cache, law, floor, floor_y=None)):
        st = [s for s in st if s[5] - s[4] <= wide]
        if st:
            out.append(wall_line(f"{o.id}#{k}", st, _floor_side(floor, st)))
    return out


def _floor_side(floor, st) -> float:
    """``+1`` where ``floor`` lies on the stations' ``+n`` side (by
    majority: its ring's nearest point to each station), else ``-1``."""
    from shapely.geometry import Point
    ring, vote = floor.exterior, 0.0
    for x, y, nx, ny, *_r in st:
        q = ring.interpolate(ring.project(Point(x, y)))
        vote += math.copysign(1.0, (q.x - x) * nx + (q.y - y) * ny)
    return 1.0 if vote >= 0.0 else -1.0


def _feet_z(lines: list, zero: float) -> "_t.Callable | None":
    """``(x, y) -> zero + the foot`` along the wall line it faces
    (``model/wing_cut.wing_floor_y``), within the walls' lowest and highest
    foot; ``None`` with no wall line."""
    from ..model.wing_cut import WingCut, wing_floor_y
    feet = [f for ln in lines for f in ln.foot]
    if not feet:
        return None
    lo, hi = min(feet), max(feet)
    cut = WingCut("", "", (), lines=tuple(lines))
    return lambda x, y: zero + min(hi, max(lo, wing_floor_y(cut, (float(x), float(y)))))


def _faces(poly, feet_z: "_t.Callable | None", step: float, ramps: _t.Sequence = ()
           ) -> np.ndarray:
    """The floor's triangulation (its ring densified every ``step``), each
    corner at the walls' foot it faces (:func:`_feet_z`) -- or on the ramp
    up to an open end (:func:`_ramps`), where that stands higher."""
    if feet_z is None:
        return np.zeros((0, 3, 3))
    tri = shapely.constrained_delaunay_triangles(shapely.segmentize(poly, step))
    out = []
    for q in getattr(tri, "geoms", [tri]):
        cs = np.asarray(q.exterior.coords)[:3]
        out.append(np.c_[cs, [max(feet_z(x, y), _ramp_z(ramps, float(x), float(y)))
                              for x, y in cs]])
    return np.asarray(out, float)


def _ramp_z(ramps: _t.Sequence, x: float, y: float) -> float:
    """The highest ramp level at ``(x, y)`` (``-inf`` with no ramp): each
    ramp's top less its grade times the distance in from its opening's
    line -- a plane per ramp."""
    z = -math.inf
    for (px, py), (nx, ny), top, grade in ramps:
        z = max(z, top - grade * max(0.0, (x - px) * nx + (y - py) * ny))
    return z


def _runs(walled: np.ndarray) -> list[np.ndarray]:
    """The cyclic runs of ring samples no wall lines (index arrays)."""
    if walled.all() or not walled.any():
        return []
    k = int(np.flatnonzero(walled)[0])
    order = np.roll(np.arange(len(walled)), -k)
    out, cur = [], []
    for i in order:
        if walled[i]:
            if cur:
                out.append(np.asarray(cur))
            cur = []
        else:
            cur.append(i)
    if cur:
        out.append(np.asarray(cur))
    return out


def _ramps(floor, samples: np.ndarray, walled: np.ndarray, tops: np.ndarray, zero: float,
           faces_z, ways, law) -> tuple[list, list[str]]:
    """THE RAMPS UP TO A WALLED TRENCH'S OPEN ENDS (#2237; RULINGS
    2026-10-08c/d, the ramp law; structures ``ramp_end = "wall_end"``: the
    ramp reaches ground at the far end of the wall): the walls state no floor
    where a mapped road leaves the trench at grade -- they run on to their
    ends at full depth, the road's own ground hiding their foot (MEASURED
    CYYZ ``Tx_A``: walls 8.0 m deep along all 340 m, the floor cut flat at
    their feet, and the service road through it stepped 8 m at both ends).
    Each OPEN stretch of the floor's ring (no wall lines it) that an
    at-grade mapped road crosses -- no bore (``deck_signature.is_tunnel_way``)
    ends within ``wall_face_max_thickness_m`` of it -- is a ramp's top: the
    plane through its chord at the walls' top beside it (the ground they
    retain), falling in from it at ``ramp_grade``, steeper only where a bore's
    end on the floor (the mouth, whose floor is the walls' feet) would stand
    over that plane -- the smallest grade that reaches it, never over
    ``ramp_max_grade``.  ``(ramps, notes)``: each ``(point, inward normal,
    top, grade)``."""
    from shapely.geometry import LineString, Point

    from .deck_signature import is_tunnel_way
    tn = law.tables.structures.tunnel
    tk = float(tn.object.wall_face_max_thickness_m)
    lines, bores = [], []
    for w in ways or ():
        tags = w.tags or {}
        if len(w.points) < 2 or not (tags.get("highway") or tags.get("railway")):
            continue
        if is_tunnel_way(tags, tn.admitted_values):
            bores += [Point(w.points[0]), Point(w.points[-1])]
        else:
            lines.append(LineString(w.points))
    anchors = [(b, faces_z(q.x, q.y)) for b in bores if floor.distance(b) <= tk
               for q in (floor.exterior.interpolate(floor.exterior.project(b)),)]
    inner = floor.representative_point()
    out, notes = [], []
    for run in _runs(walled):
        if len(run) < 2:
            continue
        chord = LineString(samples[run])
        if any(b.distance(chord) <= tk for b, _z in anchors) or not any(
                ln.intersects(chord.buffer(0.5 * tk)) for ln in lines):
            continue
        near = [i for i in (run[0] - 1, run[-1] + 1) if math.isfinite(tops[i % len(tops)])]
        if not near:
            continue
        top = zero + float(np.median([tops[i % len(tops)] for i in near]))
        (ax, ay), (bx, by) = samples[run[0]], samples[run[-1]]
        L = math.hypot(bx - ax, by - ay) or 1.0
        nx, ny = -(by - ay) / L, (bx - ax) / L
        if (inner.x - ax) * nx + (inner.y - ay) * ny < 0.0:
            nx, ny = -nx, -ny
        grade = float(tn.ramp_grade)
        for b, z in anchors:
            run_m = (b.x - ax) * nx + (b.y - ay) * ny
            if run_m > 0.0 and math.isfinite(z):
                grade = max(grade, (top - z) / run_m)
        grade = min(grade, float(tn.ramp_max_grade))
        out.append(((float(ax), float(ay)), (nx, ny), top, grade))
        notes.append(f"a ramp up to its open end at {0.5 * (ax + bx):.0f},{0.5 * (ay + by):.0f} "
                     f"(top {top:.2f}, grade {grade:.3f})")
    return out, notes


def _reach_road_ends(floor, ends, tk: float):
    """THE FLOOR MEETS A ROAD ENTERING IT AT ITS RING (#2099 F2, lcyyzP5):
    ``floor`` grown to every mapped road end of the trench (``ends``,
    ``TrenchObject.ends``: ``(xy, way id)``) standing outside it within
    ``tk`` (a wall's plan thickness: the end stands in the wall's opening,
    never past the wall) -- a strip from the ring's nearest point to the end
    ``0.25 * tk`` either side (the margin :func:`_between` keeps off the
    walls), so the road's last vertex stands on the floor and not on the
    wall face falling to it.  MEASURED CYYZ ``Tx_A``: the bore end of
    the tunnel and of the road continuing it stood 0.1 m outside the
    floor's ring, in the headwall's face -- the drawn road stepped 162.47 to
    the floor's 161.45 in its first metre."""
    from shapely.geometry import LineString, Point
    from shapely.ops import nearest_points
    grow = []
    for xy, _wid in ends or ():
        e = Point(xy)
        d = floor.distance(e)
        if 0.0 < d <= tk:
            q = nearest_points(floor.exterior, e)[0]
            grow.append(LineString([(q.x, q.y), (e.x, e.y)]).buffer(0.25 * tk))
    if not grow:
        return floor
    got = unary_union([floor, *grow])
    return got if got.geom_type == "Polygon" else floor


def _longest_open(walled: np.ndarray, step: float) -> float:
    """The longest run of ring samples no wall lines (metres, cyclic)."""
    if walled.all():
        return 0.0
    k = int(np.flatnonzero(walled)[0]) if walled.any() else 0
    run = best = 0
    for w in np.roll(walled, -k):
        run = 0 if w else run + 1
        best = max(best, run)
    return best * step


def walled_trench_floors(trenches: _t.Sequence, objects: _t.Sequence[_obj8.PlacedObject],
                         cache: _obj8.ResourceCache, law, misread: _t.AbstractSet[str], dem_z,
                         taken: _t.AbstractSet[str] = frozenset(), ways: _t.Sequence = ()
                         ) -> tuple[list, list[str]]:
    """``(ObjectFloor per walled trench, notes)`` (module doc) for the
    trench objects in ``misread`` (placement ids whose entrance opening was
    a misread); ``taken`` the placements an earlier floor reader claimed;
    ``ways`` the mapped ways (``Airport.osm_ways``) whose at-grade roads
    ramp its open ends (:func:`_ramps`)."""
    from .object_floor import FLOOR_REF, ObjectFloor
    ob = law.tables.structures.tunnel.object
    tk = float(ob.wall_face_max_thickness_m)
    by_id = {o.id: o for o in objects}
    out, notes = [], []
    for t in trenches:
        o = by_id.get(t.object_id)
        if o is None or o.id in taken or o.id not in misread:
            continue
        g = cache.geometry(o.resolved)
        got = None if g is None or bool((g.hardness == _obj8.HARD_DECK).any()) \
            else _deep_solids(o, g, law)
        if got is None:
            continue
        xy, y = got
        floor = _between(xy, law)
        name = f"{o.id} {os.path.basename(o.path)}"
        if floor is None or floor.area < float(ob.plate_min_area_m2):
            notes.append(f"{name}: no open floor between its walls -- no walled trench")
            continue
        samples = _ring_samples(floor)
        walled = _walled(samples, xy, tk)
        share = float(walled.mean())
        wide = 2.0 * float(shapely.maximum_inscribed_circle(floor).length)
        gap = _longest_open(walled, floor.exterior.length / len(samples))
        if share < float(ob.floor_walled_min_share) or gap > wide:
            notes.append(f"{name}: walls line {100 * share:.0f} % of the floor between them, "
                         f"its longest open stretch {gap:.0f} m against {wide:.0f} m across "
                         "-- no walled trench")
            continue
        # the walls' top along the ring seats the zero; their feet are read
        # as sections (:func:`_wall_lines`)
        floor = _reach_road_ends(floor, t.ends, tk)
        feet, _t = _foot_top(samples, xy, y, tk)
        _f, tops = _foot_top(samples, *_all_solids(o, g), tk)
        ok = np.isfinite(feet) & np.isfinite(tops)
        reach = 2.0 * float(ob.bore_end_tolerance_m)
        zs = [_ground_max(dem_z, (float(px), float(py)), reach)
              for px, py in samples[ok][::_GROUND_EVERY]]
        zs = [z for z in zs if math.isfinite(z)]
        if ok.sum() < 3 or not zs:
            continue
        top, ground = float(np.median(tops[ok])), float(np.median(zs))
        zero = ground - top
        feet_z = _feet_z(_wall_lines(o, cache, law, floor), zero)
        ramps, r_notes = ([], []) if feet_z is None else _ramps(
            floor, samples, walled, tops, zero, feet_z, ways, law)
        faces = _faces(floor, feet_z, float(ob.wall_sample_m), ramps)
        if not len(faces):
            continue
        fz = float(faces[:, :, 2].min())
        note = (f"{name}: a walled trench cut to its walls (#2099 F2, 15j / 19p): floor "
                f"{floor.area:.0f} m2 between its walls (walled {100 * share:.0f} % of its "
                f"ring, open {gap:.0f} m at most, {wide:.0f} m across); walls' top "
                f"{top:+.2f} on the ground {ground:.2f} beside them -> zero {zero:.2f}, "
                f"floor {fz:.2f}..{float(faces[:, :, 2].max()):.2f} (read zero "
                f"{float(o.anchor_z + o.agl_m):.2f})" + "".join(f"; {n}" for n in r_notes))
        notes.append(f"object floor {note}")
        out.append(ObjectFloor(f"{FLOOR_REF}{os.path.basename(o.path)}@trench", o.id, o.path,
                               (), zero, fz, floor, faces, (note,), ((o.id, o.path, zero),),
                               kind="floor", clearance_m=0.0))
    return out, notes
