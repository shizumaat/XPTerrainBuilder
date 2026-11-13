"""FLOOR-DATUM WALLS: a trench the author built UP from its zero (#1971;
spec ``interchange-levels-20261113.md`` §3.2, §3.3).

Every other trench reader measures a wall DOWN from the placement's zero
(``tunnel_objects``, ``trench_objects``, ``object_floor``).  A pack may
instead stand a trench's walls ON its floor: vertical faces rising from the
object's feet to a crest, no floor face of its own (KDEN ``Train_Walls``:
two walls 3.5 m high, cap strips at their top).  This module reads such a
placement (:func:`read_stack_walls`) and casts the floor between its walls
along the route that runs in it (:func:`floor_between`).  Whether it is a
stack's level 0 — a hard deck spans it — is ``airport/deck_stack``'s
question, never this module's.

THE WITNESS (geometry, never a name):

0. the walls stand ON the placement's zero: the lowest genuine solid
   (``feet_y``) within ``plate_bin_m`` of it (§0: "walls that stand on
   their own zero"; a trench hanging under its zero — LGAV's ``Trench_*``
   — is the other readers');
1. walls rising from the feet: genuine vertical faces (``|n_y| <
   [tunnel.object] plate_normal_y_min``) starting within ``plate_bin_m`` of
   the lowest genuine solid (``feet_y``) and rising at least
   ``edge_wall_min_skirt_m``;
2. a crest: the top of the LARGEST-AREA ``plate_bin_m`` bin of the
   near-horizontal faces above the feet (each face within one bin), holding ``plate_min_area_m2`` —
   never the topmost bin (a pier rising through the crest is not the wall);
3. a trench's depth: ``crest_y - feet_y >= floor_sunken_min_m``;
4. no floor of its own: under ``plate_min_area_m2`` of near-horizontal
   faces within ``plate_bin_m`` of the feet.

THE FLOOR CAST (§3.3): stations every ``wall_sample_m`` along the
under-way; at each the perpendicular is cast both ways to the nearest wall
face.  The hit is a side of the corridor only where the wall there is the
TRENCH's wall — its top the crest: a crest plate stands within
``wall_face_max_thickness_m`` of the hit (§3.2 (2), the walls' top).  A
wing wall splaying away at the trench's end tapers under its crest (KDEN:
3.5 m to 0 over 65 m) and is no side of the corridor.  A station with a
wall on one side only takes the previous half-width on the other; the
floor ends at the last station with a wall on either side.  Never the
walls' convex hull (MEASURED KDEN: it flares to 69 m at the south end).
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import math

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon

from . import obj8 as _obj8

__all__ = ["StackWalls", "FloorCast", "read_stack_walls", "floor_between", "wall_hull",
           "run_beside"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class StackWalls:
    """A placement's floor-datum walls (module doc): its feet and crest
    (authored y), the plan segments of its wall faces in the AIRPORT frame
    (``(k, 2, 2)``), and the plan polygons of its crest plates."""

    object_id: str
    feet_y: float
    crest_y: float
    segs: np.ndarray = _dc.field(repr=False, compare=False)
    #: the crest plates' triangles in the frame, ``(n, 3, 2)``
    crest_tris: np.ndarray = _dc.field(repr=False, compare=False, default=None)

    @functools.cached_property
    def plan(self):
        """The crest plates' plan (frame)."""
        import shapely
        polys = shapely.polygons(self.crest_tris)
        return shapely.union_all(polys[shapely.area(polys) > 1e-6])

    @functools.cached_property
    def hull(self) -> Polygon:
        """The plan hull of the wall faces (the under-way's search region)."""
        return MultiPoint(self.segs.reshape(-1, 2).tolist()).convex_hull

    def crest_zone(self, reach: float):
        """The crest plates grown by ``reach``, prepared (the cast's test)."""
        got = self.__dict__.setdefault("_zones", {})
        if reach not in got:
            from shapely.prepared import prep
            got[reach] = prep(self.plan.buffer(reach))
        return got[reach]


@_dc.dataclass(frozen=True)
class FloorCast:
    """The floor between the walls (§3.3): ``left`` / ``right`` the hit
    points per station (frame), ``walled`` per station which sides a wall
    face stands on, ``polygon`` the floor, ``length`` along the route of
    the stations with walls on BOTH sides."""

    left: tuple[XY, ...]
    right: tuple[XY, ...]
    walled: tuple[tuple[bool, bool], ...]
    polygon: Polygon
    length: float
    s0: float
    s1: float

    def ring(self) -> tuple[XY, ...]:
        """``[left_0 .. left_n, right_n .. right_0]`` (``DeckStack.floor``)."""
        return tuple(self.left) + tuple(reversed(self.right))

    def rim(self) -> tuple[tuple[XY, ...], ...]:
        """The wall lines: runs of consecutive stations a wall face stands
        on, per side."""
        out: list[tuple[XY, ...]] = []
        for side, pts in ((0, self.left), (1, self.right)):
            run: list[XY] = []
            for p, w in zip(pts, self.walled, strict=True):
                if w[side]:
                    run.append(p)
                elif run:
                    out.append(tuple(run))
                    run = []
            if run:
                out.append(tuple(run))
        return tuple(r for r in out if len(r) >= 2)

    def end_width(self, end: int) -> tuple[XY, XY]:
        """``(left, right)`` at the first (``end`` 0) or last (1) station."""
        k = 0 if end == 0 else -1
        return self.left[k], self.right[k]


#: authored-frame reading per resource (the walls' faces, before placing)
_READ: dict[str, "tuple | str"] = {}


def _normals(v: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(|n_y|, plan area)`` per triangle."""
    a, b, c = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ny = np.abs(n[:, 1]) / np.maximum(ln, 1e-12)
    return ny, 0.5 * np.abs(n[:, 1])


def _authored(g: _obj8.ObjGeometry, comps, law) -> "tuple | str":
    """``(feet_y, crest_y, wall tris, crest tris)`` in the authored frame,
    or why the resource states no floor-datum walls."""
    ob = law.tables.structures.tunnel.object
    if not comps:
        return "no genuine solid"
    feet = float(min(c.min_y for c in comps))
    bin_m = float(ob.plate_bin_m)
    if abs(feet) > bin_m:
        # a floor-datum wall stands ON its zero; one hanging under it (or
        # lifted over it) is the other trench readers' (they measure down)
        return f"its feet stand {feet:+.2f} m off its zero"
    tris = np.concatenate([c.tris for c in comps])
    v = np.asarray(g.vertices[:, :3], float)
    ny, plan = _normals(v, tris)
    ys = v[tris][:, :, 1]
    lo, hi = ys.min(axis=1), ys.max(axis=1)
    vert = (ny < float(ob.plate_normal_y_min)) & (lo <= feet + bin_m) \
        & (hi - lo >= float(ob.edge_wall_min_skirt_m))
    if not vert.any():
        return "no wall rises from its feet"
    flat = ny >= float(ob.plate_normal_y_min)
    floor_area = float(plan[flat & (hi <= feet + bin_m)].sum())
    if floor_area >= float(ob.plate_min_area_m2):
        return f"a floor of its own ({floor_area:.0f} m2 at its feet): the floor readers'"
    # a crest face lies WITHIN one bin (a slope through it is no plate)
    k_hi = np.ceil(hi / bin_m - 1e-6).astype(int)
    up = flat & (hi > feet + bin_m) & (np.ceil(lo / bin_m - 1e-6).astype(int) == k_hi)
    if not up.any():
        return "no crest"
    keys = k_hi[up]
    areas: dict[int, float] = {}
    for k, a in zip(keys.tolist(), plan[up].tolist(), strict=True):
        areas[k] = areas.get(k, 0.0) + a
    k_best, a_best = max(areas.items(), key=lambda t: (t[1], -t[0]))
    if a_best < float(ob.plate_min_area_m2):
        return f"no crest plate ({a_best:.0f} m2 < plate_min_area_m2)"
    crest = float(hi[up][keys == k_best].max())
    if crest - feet < float(ob.floor_sunken_min_m):
        return (f"its crest {crest:.2f} stands {crest - feet:.2f} m over its feet "
                f"< floor_sunken_min_m {float(ob.floor_sunken_min_m):g}")
    return feet, crest, tris[vert], tris[up][keys == k_best]


def read_stack_walls(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, law
                     ) -> "StackWalls | str":
    """``o``'s floor-datum walls (module doc, witness 1-4), or why not."""
    if not o.resolved:
        return "unresolved"
    got = _READ.get(o.resolved)
    if got is None:
        g = cache.geometry(o.resolved)
        got = "no geometry" if g is None else _authored(g, cache.genuine(o.resolved), law)
        _READ[o.resolved] = got
    if isinstance(got, str):
        return got
    feet, crest, wall, top = got
    g = cache.geometry(o.resolved)
    aff = _obj8.placement_affine(o.xy, o.heading_deg)
    v = np.asarray(g.vertices[:, :3], float)
    fx = aff[0] * v[:, 0] + aff[1] * v[:, 2] + aff[4]
    fy = aff[2] * v[:, 0] + aff[3] * v[:, 2] + aff[5]
    # each wall face's plan segment: its two plan-farthest corners
    p = np.stack([fx[wall], fy[wall]], axis=-1)                     # (k, 3, 2)
    d = np.stack([np.hypot(*(p[:, a] - p[:, b]).T) for a, b in ((0, 1), (1, 2), (0, 2))], axis=1)
    pick = np.array(((0, 1), (1, 2), (0, 2)))[np.argmax(d, axis=1)]
    rows = np.arange(len(p))
    segs = np.stack([p[rows, pick[:, 0]], p[rows, pick[:, 1]]], axis=1)
    segs = segs[d.max(axis=1) > 0.02]
    if not len(segs):
        return "no wall face stands in plan"
    return StackWalls(str(o.id), feet, crest, segs,
                      np.stack([fx[top], fy[top]], axis=-1))


def wall_hull(walls: StackWalls) -> Polygon:
    """The plan hull of the wall faces (the under-way's search region)."""
    return walls.hull


def _tangent(route: LineString, s: float) -> XY:
    a = route.interpolate(max(0.0, s - 0.5))
    b = route.interpolate(min(route.length, s + 0.5))
    d = math.hypot(b.x - a.x, b.y - a.y)
    return ((b.x - a.x) / d, (b.y - a.y) / d) if d > 1e-9 else (1.0, 0.0)


def _cast(p: XY, n: XY, segs: np.ndarray) -> tuple[float, XY]:
    """``(distance, hit point)`` along ``n`` from ``p`` to the nearest
    segment of ``segs``; ``(inf, p)`` for none."""
    a, b = segs[:, 0], segs[:, 1]
    e = b - a
    den = n[0] * e[:, 1] - n[1] * e[:, 0]
    w = a - np.asarray(p)
    good = np.abs(den) > 1e-12
    safe = np.where(good, den, 1.0)
    u = np.where(good, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / safe, -1.0)
    t = np.where(good, (w[:, 0] * n[1] - w[:, 1] * n[0]) / safe, -1.0)
    hit = good & (u > 1e-6) & (t >= -1e-9) & (t <= 1.0 + 1e-9)
    if not hit.any():
        return math.inf, p
    d = float(u[hit].min())
    return d, (p[0] + n[0] * d, p[1] + n[1] * d)


def floor_between(walls: StackWalls, route: LineString, law) -> "FloorCast | str":
    """The floor between ``walls`` along ``route`` (module doc), or why
    none."""
    ob = law.tables.structures.tunnel.object
    step = float(ob.wall_sample_m)
    segs = walls.segs
    ends = segs.reshape(-1, 2)
    ss = [route.project(Point(float(p[0]), float(p[1]))) for p in ends]
    s0, s1 = max(0.0, min(ss)), min(route.length, max(ss))
    if s1 - s0 < float(ob.hull_min_length_m):
        return f"the route runs {s1 - s0:.1f} m beside the walls < hull_min_length_m"
    crest = walls.crest_zone(float(ob.wall_face_max_thickness_m))
    n_st = max(1, int(math.floor((s1 - s0) / step)))
    stations = [s0 + k * (s1 - s0) / n_st for k in range(n_st + 1)]
    rows: list[tuple[float, XY, XY, float, float]] = []
    for s in stations:
        q = route.interpolate(s)
        t = _tangent(route, s)
        nl = (-t[1], t[0])
        dl, hl = _cast((q.x, q.y), nl, segs)
        dr, hr = _cast((q.x, q.y), (-nl[0], -nl[1]), segs)
        # a side of the corridor only where the wall's top is the crest
        dl = dl if math.isfinite(dl) and crest.contains(Point(hl)) else math.inf
        dr = dr if math.isfinite(dr) and crest.contains(Point(hr)) else math.inf
        rows.append((s, (q.x, q.y), nl, dl, dr))
    walled = [(math.isfinite(r[3]), math.isfinite(r[4])) for r in rows]
    have = [k for k, w in enumerate(walled) if w[0] or w[1]]
    if not have:
        return "no wall face flanks the route"
    rows, walled = rows[have[0]:have[-1] + 1], walled[have[0]:have[-1] + 1]
    both = [k for k, w in enumerate(walled) if w[0] and w[1]]
    if not both:
        return "no station has a wall on both sides"
    widths = [[r[3], r[4]] for r in rows]
    for side in (0, 1):
        # a side with no wall takes the previous half-width (then, before
        # the first wall, the next one's)
        last = None
        for w in widths:
            if math.isfinite(w[side]):
                last = w[side]
            elif last is not None:
                w[side] = last
        last = None
        for w in reversed(widths):
            if math.isfinite(w[side]):
                last = w[side]
            elif last is not None:
                w[side] = last
    left = tuple((p[0] + n[0] * w[0], p[1] + n[1] * w[0])
                 for (_s, p, n, _a, _b), w in zip(rows, widths, strict=True))
    right = tuple((p[0] - n[0] * w[1], p[1] - n[1] * w[1])
                  for (_s, p, n, _a, _b), w in zip(rows, widths, strict=True))
    poly = Polygon(list(left) + list(reversed(right)))
    if not poly.is_valid:
        poly = poly.buffer(0.0)
    if poly.is_empty:
        return "the cast floor is empty"
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    length = sum(step for w in walled if w[0] and w[1])
    if length < float(ob.hull_min_length_m):
        return f"walls on both sides for {length:.0f} m < hull_min_length_m"
    return FloorCast(left, right, tuple(walled), poly, float(length), rows[0][0], rows[-1][0])


def run_beside(route: LineString, walls: StackWalls) -> float:
    """How far ``route`` runs inside the walls' hull (the under-way pick)."""
    return float(route.intersection(wall_hull(walls)).length)

