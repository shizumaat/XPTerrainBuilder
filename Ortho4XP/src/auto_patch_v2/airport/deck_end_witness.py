"""THE GEOMETRY OF A UNIT DECK'S ENDS (#2129; spec
``docs/specs/2129-deck-ends-spec.md`` R2-R4, R8) — shape only, read off the
deck's own authored mesh in plan metres; ``planar/deck_end_fill`` reads the
state and mints the landing.

* :func:`partition_prints` — every deck's model footprint of a partition
  (``bridge_family.deck_prints``), parsed ONCE per partition object for the
  pack stage and the planar stage alike (issue #1706's memo).
* R2 :func:`driven_surface` — the plan union of the near-horizontal
  up-faces (``bridge_witness.up_faces``) at any ``y``.
* R3 :func:`end_edges` — a straight run of the outline, one lane to
  ``2 x free_route_half_width_m`` long, whose neighbours turn back by at
  least 60 degrees and run at least its length behind it (a ribbon's
  tip); :func:`edge_top`, :func:`is_joint`, :func:`on_abutment`.
* R4 :func:`carried_ways` — the mapped routes on the deck crossing an edge.
* R8 :func:`route_end_cuts` — at the pack stage, each carried way's
  stretch inside ``S`` behind an elevated ROUTE end, for the ONE way
  rewrite (``airport/deck_stack._rewrite_ways``).
"""
from __future__ import annotations

import math
import typing as _t
import weakref

import numpy as np
from shapely.geometry import LineString, Point, Polygon

__all__ = ["partition_prints", "xy_faces", "member_faces", "driven_surface", "end_edges",
           "edge_top", "is_joint", "on_abutment", "carried_ways", "offset_finding",
           "part_meets", "route_end_cuts"]

XY = tuple[float, float]
#: a neighbour of an end edge turns back by at least this (degrees)
_TURN_DEG = 60.0
#: along a side, consecutive outline runs within this turn are one run
_SIDE_DEG = 30.0
#: an end edge's tops are read this often along it (m)
_SAMPLE_M = 1.0
#: a mapped way this near a stub's ray and this parallel is a mapping
#: offset (R4): reported, never adopted
_OFFSET_DEG = 30.0

#: issue #1706: ``id(partition) -> (weak reference, its prints)``: one
#: build's stages read the SAME partition object, so its deck prints (and
#: the memos they carry) are derived once per partition
_PRINTS: dict[int, tuple] = {}


def partition_prints(part) -> list:
    """The deck model footprints of the pack partition (``bridge_family.
    deck_prints``, each deck parsed once), held while the partition lives."""
    held = _PRINTS.get(id(part))
    if held is not None and held[0]() is part:
        return held[1]
    prints = _derive_prints(part)
    try:
        ref = weakref.ref(part, _forget)
    except TypeError:                         # not weakly referable: not held
        return prints
    _PRINTS[id(part)] = (ref, prints)
    return prints


def _forget(ref) -> None:
    """A held partition died: drop its prints (only its own entry)."""
    for k, held in list(_PRINTS.items()):
        if held[0] is ref:
            del _PRINTS[k]


def _cutter(part, ui: int, m):
    from .placement_cut import _LineCutter
    u = part.units[ui]
    return _LineCutter(m, 0.0, 0, 0.0, 0.0, 0.0, float(u.anchor[0]), float(u.anchor[1]))


def _derive_prints(part) -> list:
    from . import bridge_family as _bf
    return _bf.deck_prints(part, lambda ui, _mi, m: _cutter(part, ui, m))


def xy_faces(p, to_xy) -> np.ndarray:
    """``(n, 3, 3)`` plan faces ``(x, y, authored y)`` of a deck print."""
    if not p.tris or len(p.ys) != len(p.tris):
        return np.zeros((0, 3, 3))
    out = np.empty((len(p.tris), 3, 3))
    for k, (t, ys) in enumerate(zip(p.tris, p.ys, strict=True)):
        for i in range(3):
            x, y = to_xy(t[i][1], t[i][0])
            out[k, i] = (x, y, ys[i])
    return out


def member_faces(part, ui: int, mi: int, to_xy) -> np.ndarray:
    """Every authored face of partition member ``(ui, mi)`` in plan metres
    (the read ``planar/landing._derive_prints`` makes of a deck)."""
    from .bridge_family import _latlon
    m = part.units[ui].members[mi]
    cut = _cutter(part, ui, m)
    if not cut._read():                                   # noqa: SLF001
        return np.zeros((0, 3, 3))
    v = cut._geom.vertices                                # noqa: SLF001
    tl = [c.tris for c in cut._comps if len(c.tris)]      # noqa: SLF001
    if not tl:
        return np.zeros((0, 3, 3))
    tris = np.concatenate(tl)
    tris = tris[(tris < v.shape[0]).all(axis=1)]
    out = np.empty((len(tris), 3, 3))
    for k, row in enumerate(tris.tolist()):
        for i, q in enumerate(row):
            la, lo = _latlon(float(v[q, 0]), float(v[q, 2]), cut.lat, cut.lon, m.heading_deg)
            out[k, i] = (*to_xy(lo, la), float(v[q, 1]))
    return out


def driven_surface(up: np.ndarray):
    """R2: the plan union of the up-faces."""
    import shapely
    polys = shapely.polygons(up[:, :, :2])
    polys = polys[shapely.area(polys) > 1e-6]
    return shapely.union_all(polys, grid_size=0.001) if len(polys) else Polygon()


def _ang(d1: XY, d2: XY) -> float:
    """The turn from heading ``d1`` to ``d2`` (degrees, signed: + left)."""
    return math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0],
                                   d1[0] * d2[0] + d1[1] * d2[1]))


def end_edges(S, flush: float, cap: float, least: float) -> list[tuple[XY, XY, XY, float]]:
    """R3's pure geometry: ``(a, b, outward normal, L)`` per end edge of
    ``S``'s outer rings (counter-clockwise; a tip's corners turn left), at
    least ``least`` long (one lane: a narrower tip carries no road)."""
    from shapely.geometry.polygon import orient
    got = []
    for poly in getattr(S, "geoms", [S]):
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        ring = orient(Polygon(poly.exterior), 1.0).exterior.simplify(flush)
        pts = [tuple(map(float, c)) for c in ring.coords][:-1]
        n = len(pts)
        if n < 3:
            continue
        segs = []
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            L = math.dist(a, b)
            segs.append((a, b, ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 0 else (0.0, 0.0), L))

        def _run(i: int, step: int) -> float:
            """The side's length from segment ``i`` on (``step`` +-1) while
            it turns less than ``_SIDE_DEG`` at each corner."""
            tot, j = segs[i][3], i
            for _k in range(n - 1):
                nj = (j + step) % n
                t = _ang(segs[j][2], segs[nj][2]) if step > 0 else _ang(segs[nj][2], segs[j][2])
                if abs(t) > _SIDE_DEG:
                    break
                tot += segs[nj][3]
                j = nj
            return tot
        for i, (a, b, d, L) in enumerate(segs):
            if L < least or L > cap:
                continue
            ip, inx = (i - 1) % n, (i + 1) % n
            if _ang(segs[ip][2], d) < _TURN_DEG or _ang(d, segs[inx][2]) < _TURN_DEG:
                continue
            if _run(ip, -1) < L or _run(inx, +1) < L:
                continue
            got.append((a, b, (d[1], -d[0]), L))
    return got


def _samples(a: XY, b: XY) -> tuple[np.ndarray, np.ndarray]:
    L = math.dist(a, b)
    k = max(3, int(math.ceil(L / _SAMPLE_M)) + 1)
    f = np.linspace(0.05, 0.95, k)
    return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])


def edge_top(up: np.ndarray, a: XY, b: XY) -> float:
    """``S``'s top on the edge: the median over its samples of the highest
    up-face there (``geom/lowest_face.every_z_at``)."""
    from ..geom.lowest_face import every_z_at
    xs, ys = _samples(a, b)
    tops = [float(z.max()) for z in every_z_at(up, xs, ys, edge_m=0.3) if len(z)]
    return float(np.median(tops)) if tops else math.nan


def is_joint(frame_up: np.ndarray, a: XY, b: XY, out: XY, y_e: float, step: float,
           tol: float) -> bool:
    """R3 (a): an up-face of the frame stands within ``step`` outward of
    the edge at ``y_e`` +- ``tol`` (W7's JOINT)."""
    from ..geom.lowest_face import every_z_at
    xs, ys = _samples(a, b)
    for off in (0.5, 0.5 * step, step):
        for z in every_z_at(frame_up, xs + out[0] * off, ys + out[1] * off):
            if len(z) and bool((np.abs(z - y_e) <= tol).any()):
                return True
    return False


def on_abutment(walls: np.ndarray, a: XY, b: XY, floor_y: float, law) -> bool:
    """R3 (b): a STANDING face of the frame under the edge reaching down to
    the ground band (``bridge_end_state.standing_plan``'s walls)."""
    from .bridge_end_state import standing_plan
    if not len(walls):
        return False
    br = law.tables.structures.bridge
    edge = LineString([a, b]).buffer(1.0)
    x0, y0, x1, y1 = edge.bounds
    lo, hi = walls[:, :, :2].min(axis=1), walls[:, :, :2].max(axis=1)
    near = walls[(hi[:, 0] >= x0) & (lo[:, 0] <= x1) & (hi[:, 1] >= y0) & (lo[:, 1] <= y1)
                 & (walls[:, :, 2].min(axis=1) <= floor_y)]
    plan = standing_plan(near, float(br.end_solid_min_height_m),
                         float(br.end_solid_min_area_m2))
    return plan is not None and plan.intersects(edge)


def carried_ways(ways, S, a: XY, b: XY) -> tuple[int, ...]:
    """R4: the mapped route ways on the deck (``layer >= 1`` or ``bridge !=
    no``, no tunnel) inside ``S`` that cross the edge."""
    edge = LineString([a, b]).buffer(0.5)
    got = []
    for w in ways:
        t = w.tags or {}
        if len(w.points) < 2 or not ("highway" in t or "railway" in t):
            continue
        if t.get("tunnel", "no") not in ("", "no"):
            continue
        try:
            layer = int(str(t.get("layer", "0")).strip() or 0)
        except ValueError:
            layer = 0
        if layer < 1 and t.get("bridge", "no") in ("", "no"):
            continue
        line = LineString(w.points)
        if line.intersects(edge) and line.intersection(S).length > 1.0:
            got.append(int(w.id))
    return tuple(sorted(got))


def offset_finding(ways, mid: XY, out: XY, L: float, run: float) -> str:
    """R4: a mapped route lying within ``L/2`` of a stub's ray and within 30
    degrees of it for the whole run — a mapping offset, reported only."""
    ray = LineString([mid, (mid[0] + out[0] * run, mid[1] + out[1] * run)])
    pts = [ray.interpolate(f, normalized=True) for f in np.linspace(0.0, 1.0, 6)]
    best = None
    for w in ways:
        t = w.tags or {}
        if len(w.points) < 2 or "highway" not in t:
            continue
        line = LineString(w.points)
        d = max(line.distance(p) for p in pts)
        if d > 0.5 * L:
            continue
        s = line.project(Point(mid))
        p0, p1 = line.interpolate(max(0.0, s - 2.0)), line.interpolate(s + 2.0)
        h = (p1.x - p0.x, p1.y - p0.y)
        if math.hypot(*h) < 1e-6:
            continue
        if abs(math.degrees(math.acos(min(1.0, abs(h[0] * out[0] + h[1] * out[1])
                                          / math.hypot(*h))))) > _OFFSET_DEG:
            continue
        if best is None or d < best[0]:
            best = (d, int(w.id))
    return "" if best is None else f"mapping offset: way {best[1]} within {best[0]:.1f} m of the stub ray"


def part_meets(box, xy_box, to_xy) -> bool:
    """A part's lat/lon ``box`` meets the plan box ``xy_box``."""
    x0, y0 = to_xy(box[1], box[0])
    x1, y1 = to_xy(box[3], box[2])
    return not (max(x0, x1) < xy_box[0] or min(x0, x1) > xy_box[2]
                or max(y0, y1) < xy_box[1] or min(y0, y1) > xy_box[3])




def route_end_cuts(airport, law, band_m: float) -> dict[int, list[tuple[str, Polygon]]]:
    """R8 at the pack stage: ``way id -> [(deck key, S piece)]`` for every
    mapped route carried across an ELEVATED end edge (its top over the
    deck's lowest ``y`` + ``band_m``: else 10-03e's landing) of a deck of
    a partition unit (``bridge_family.viaduct_units``, keyed by the unit) —
    the stretch inside ``S`` the way rewrite makes a bridge marked
    ``deck_carry.END_TAG`` (no ribbon, no #1935 bridge-ground run)."""
    from . import bridge_family as _bf
    from .bridge_witness import up_faces
    part, frame = getattr(airport, "partition", None), getattr(airport, "frame", None)
    if part is None or frame is None or not any(
            getattr(m, "deck_kind", "") in ("flag", "signature")
            for u in part.units for m in u.members):
        return {}
    prints = partition_prints(part)
    if not prints:
        return {}
    unit_of = {id(q): str(ui) for ui, u in enumerate(part.units)
               for m in u.members for q in m.parts}
    vias = _bf.viaduct_units(prints, part, lambda q: unit_of.get(id(q), ""))
    br = law.tables.structures.bridge
    flush, nmin = float(br.deck_flush_m), float(br.deck_plate_normal_y_min)
    cap = 2.0 * float(br.free_route_half_width_m)
    least = float(law.tables.structures.tunnel.lane_width_m)
    ways = list(getattr(airport, "osm_ways_mapped", None) or airport.osm_ways)
    to_xy = frame.entry()
    cuts: dict[int, list[tuple[str, Polygon]]] = {}
    for key, (_u, _v, _fr, p) in sorted(vias.items()):
        f = xy_faces(p, to_xy)
        up = up_faces(f, nmin) if len(f) else f
        if not len(up):
            continue
        S = driven_surface(up)
        y_low = float(f[:, :, 2].min())
        for a, b, _out, _L in end_edges(S, flush, cap, least):
            if edge_top(up, a, b) <= y_low + band_m:
                continue
            piece = next((q for q in getattr(S, "geoms", [S])
                          if q.distance(Point(0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))) < 0.01),
                         S)
            for wid in carried_ways(ways, S, a, b):
                cuts.setdefault(int(wid), []).append((key, piece))
    return cuts
