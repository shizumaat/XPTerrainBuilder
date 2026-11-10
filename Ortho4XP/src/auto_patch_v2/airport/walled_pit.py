"""A WALLED PIT UNDER A SHARED DATUM (#1949; owner 2026-11-10T14:33Z: "I
believe the pack author just expects the whole area to be cut out and the
objects sit in the trench").

``airport/object_floor`` reads a trench object's floor where the floor hangs
``shell_floor_min_m`` under its OWN zero.  A pack that hangs a whole sunken
area off ONE shared datum authors the floor AT the zero and the ground at the
top of the walls: a floor plate object at y ~ 0, a co-placed retaining-wall
object rising from that floor to its rim (curved or straight — the walls are
read face by face), every object of the area standing in the pit.  Its zero
is no witness (owner RULINGS 2026-11-07b (1)), so the zero test never sees
the floor.  THIS reader reads the same floor/cover pair against the walls'
own RIM:

1. THE FLOOR — a plate object (near-horizontal faces carry
   ``floor_object_min_share`` of its surface) whose lowest plate's worth of
   faces stands at ``floor_y``.
2. THE WALLS — a co-placed placement that is no plate, whose wall faces
   reach down to the floor (within ``cover_flush_m``) and stand on at least
   ``floor_walled_min_share`` of the floor's outline ("walls end on it").
3. THE RIM — the top of those walls along the outline (the median of the
   highest wall top within ``wall_face_max_thickness_m`` of each outline
   sample): the author's ground meets the walls there.  The pit is
   ``rim - floor`` deep; at least ``floor_sunken_min_m`` or no pit.
4. OPEN TOP — the frame's solids at or above the rim cover less than
   ``basin.basement_cover_min`` of the floor: a floor under its own roof is
   a building's (the basement test of ``planar/basins`` rule 4).
5. THE SEAT — the rim lands on the ground around the pit (the author's
   plates near the design ground, else the DEM; ``below_grade_witness
   .around``, the frame's own faces left out).  A rim standing 0 ..
   ``authored_crest_max_m`` over that ground keeps the authored seat
   (object-placement spec §18 (3)); any other rim re-seats the WHOLE FRAME
   by ``lift = ground - rim`` (the frame is one rigid world: every
   co-placed placement, and every other floor read in it, moves with it).

The floor's surface is its near-horizontal faces standing under the rim
(the floor, the decks and ramps inside the walls), placed at ``zero +
lift`` — one :class:`object_floor.ObjectFloor` that every consumer of an
object floor reads unchanged (cells, pins, portals, seats).

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import types as _types

import numpy as np
import shapely
from shapely import STRtree
from shapely.ops import unary_union

from . import frame_entry as _frame_entry
from . import obj8 as _obj8
from .below_grade_witness import around as _around_ids
from .below_grade_witness import placed_all as _placed_all
from .below_grade_witness import zero_of as _zero
from .object_cut import _base, _face_normals_y, valid_polygon

__all__ = ["read_walled_pit", "share_lift", "Walls"]

def _floor_level(v: np.ndarray, hz: np.ndarray, min_area: float) -> "float | None":
    """The lowest level carrying a plate's worth (``min_area``) of the
    near-horizontal faces ``hz``: the mean height of the face at which the
    plan area, counted from the bottom, reaches ``min_area``."""
    F = v[hz]
    a = 0.5 * np.abs((F[:, 1, 0] - F[:, 0, 0]) * (F[:, 2, 2] - F[:, 0, 2])
                     - (F[:, 2, 0] - F[:, 0, 0]) * (F[:, 1, 2] - F[:, 0, 2]))
    y = F[:, :, 1].mean(axis=1)
    k = np.argsort(y)
    c = np.cumsum(a[k])
    if not len(c) or c[-1] < min_area:
        return None
    return float(y[k][int(np.searchsorted(c, min_area))])


class Walls:
    """Every placement's wall faces (not near-horizontal) as frame plan
    segments with their bottom and top y (OBJ), read once per placement for
    one floor read: :meth:`reaching` hands the ones whose bottom reaches a
    floor (a shared-datum frame offers every plate candidate the same
    mates)."""

    def __init__(self, cache, law):
        self.cache, self.law, self._by_id = cache, law, {}

    def _read(self, p):
        ob = self.law.tables.structures.tunnel.object
        g = self.cache.geometry(p.resolved)
        if g is None or not len(g.solid):
            return None
        v, t = g.vertices, g.solid
        w = t[_face_normals_y(v, t) < ob.plate_normal_y_min]
        if not len(w):
            return None
        P = v[w]
        xz = P[:, :, [0, 2]]
        pairs = ((0, 1), (1, 2), (2, 0))
        d = np.stack([np.hypot(*(xz[:, i] - xz[:, j]).T) for i, j in pairs], axis=1)
        k = d.argmax(axis=1)
        a = np.array([pairs[q][0] for q in k])
        b = np.array([pairs[q][1] for q in k])
        n = np.arange(len(w))
        ok = d[n, k] >= 0.02
        if not ok.any():
            return None
        seg = np.stack([xz[n, a], xz[n, b]], axis=1)[ok]
        lines = _frame_entry.transform(shapely.linestrings(seg),
                                       _obj8.placement_affine(p.xy, p.heading_deg))
        return STRtree(lines), lines, P[:, :, 1].min(axis=1)[ok], P[:, :, 1].max(axis=1)[ok]

    def reaching(self, p, reach_y: float, top_y: float, near):
        """``(tree, tops)`` of ``p``'s wall faces whose bottom reaches
        ``reach_y`` and whose top stands at ``top_y`` or over it, within
        the plan box ``near`` — or ``None``."""
        if p.id not in self._by_id:
            self._by_id[p.id] = self._read(p)
        got = self._by_id[p.id]
        if got is None:
            return None
        tree, lines, lo, hi = got
        k = tree.query(near)
        k = k[(lo[k] <= reach_y) & (hi[k] >= top_y)]
        if not len(k):
            return None
        return STRtree(lines[k]), hi[k]


def _on_ring(foot, walls, tk: float, step: float) -> tuple[float, "float | None"]:
    """``(share, rim_y)``: the share of ``foot``'s outline samples within
    ``tk`` of a wall, and the median over those samples of the highest wall
    top there."""
    tree, tops = walls
    ring = foot.boundary
    L = ring.length
    if L <= 0.0:
        return 0.0, None
    n = max(1, int(math.ceil(L / step)))
    pts = shapely.line_interpolate_point(ring, (np.arange(n) + 0.5) * (L / n))
    si, wi = tree.query(pts, predicate="dwithin", distance=tk)
    if not len(si):
        return 0.0, None
    best = np.full(n, -np.inf)
    np.maximum.at(best, si, tops[wi])
    hit = np.isfinite(best)
    return float(hit.mean()), float(np.median(best[hit]))


def _placed_plan(o, faces_obj: np.ndarray, scale) -> np.ndarray:
    """``faces_obj`` (OBJ metres) as frame plan triangles (shapely)."""
    from .below_grade_witness import xp
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = xp(a * faces_obj[:, :, 0] + b * faces_obj[:, :, 2] + xo,
                d * faces_obj[:, :, 0] + e * faces_obj[:, :, 2] + yo, o, scale)
    return px, py


def _covered(floor_foot, frame, cache, law, msl, rim_abs: float, scale) -> float:
    """The share of ``floor_foot`` under near-horizontal solids of the
    ``frame`` standing at or above the rim (absolute), read on a grid of at
    most :data:`_COVER_SAMPLES` points."""
    ob = law.tables.structures.tunnel.object
    x0, y0, x1, y1 = floor_foot.bounds
    step = max(1.0, math.sqrt(floor_foot.area / _COVER_SAMPLES))
    gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
    pts = shapely.points(gx.ravel(), gy.ravel())
    pts = pts[shapely.contains(floor_foot, pts)]
    if not len(pts):
        return 0.0
    box = shapely.box(x0, y0, x1, y1)
    hit = np.zeros(len(pts), bool)
    for p in frame:
        g = cache.geometry(p.resolved)
        if g is None or not len(g.solid):
            continue
        bb = getattr(p, "plan_bbox", None)
        if bb is not None and not bb.intersects(box):
            continue
        zero = _zero(p, msl)
        t = g.solid[_face_normals_y(g.vertices, g.solid) >= ob.plate_normal_y_min]
        t = t[g.vertices[t][:, :, 1].min(axis=1) >= rim_abs - zero - ob.cover_flush_m]
        if not len(t):
            continue
        F = _placed_all(p, _types.SimpleNamespace(vertices=g.vertices, solid=t), zero, scale)
        if not len(F):
            continue
        tris = shapely.polygons(F[:, :, :2])
        tris = tris[(shapely.area(tris) > 1e-6) & shapely.intersects(tris, box)]
        if len(tris):
            hit[np.unique(STRtree(tris).query(pts, predicate="intersects")[0])] = True
    return float(hit.mean())


#: the open-top read's sample budget per floor
_COVER_SAMPLES = 20000


def read_walled_pit(o, g, mates, cache, law, msl, ag, ground, scale, walls: Walls,
                    mate_share, notes: list[str]):
    """``o``'s walled pit as an ``object_floor.ObjectFloor`` (module doc),
    or ``None``; a candidate that has walls but fails a test is noted.
    ``mate_share(p)`` is the plate share of ``p``'s resource; ``walls`` the
    read's :class:`Walls`."""
    from .object_floor import FLOOR_REF, ObjectFloor
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    hz = t[_face_normals_y(v, t) >= ob.plate_normal_y_min]
    floor_y = _floor_level(v, hz, ob.plate_min_area_m2) if len(hz) else None
    if floor_y is None:
        return None
    px, py = _placed_plan(o, v[hz], (1.0, 1.0))
    tris = shapely.polygons(np.stack([px, py], axis=2))
    outline = valid_polygon(unary_union(tris[shapely.area(tris) > 1e-6]))
    if outline is None or outline.area < ob.plate_min_area_m2:
        return None
    tk = float(ob.wall_face_max_thickness_m)
    box = shapely.box(*outline.bounds).buffer(tk)
    covers, rims = [], []
    for p in mates:
        y0, y1 = cache.y_range(p.resolved)[:2]
        bb = getattr(p, "plan_bbox", None)
        if y0 > floor_y + ob.cover_flush_m or y1 < floor_y + ob.floor_sunken_min_m \
                or (bb is not None and not bb.intersects(box)) \
                or mate_share(p) >= ob.floor_object_min_share:
            continue
        w = walls.reaching(p, floor_y + ob.cover_flush_m, floor_y + ob.floor_sunken_min_m, box)
        if w is None:
            continue
        share, rim_y = _on_ring(outline, w, tk, float(ob.wall_sample_m))
        if share >= ob.floor_walled_min_share and rim_y is not None:
            covers.append(p)
            rims.append((share, rim_y))
    if not covers:
        return None
    rim_y = float(max(rims)[1])
    what = f"{o.id} {_base(o.path)}"
    if rim_y - floor_y < ob.floor_sunken_min_m:
        notes.append(f"{what}: walls {rim_y - floor_y:.2f} m over its floor < "
                     f"{ob.floor_sunken_min_m:g}: no walled pit")
        return None
    zero = _zero(o, msl)
    frame = (o, *mates)
    low = hz[v[hz][:, :, 1].mean(axis=1) <= floor_y + ob.cover_flush_m]
    fx, fy = _placed_plan(o, v[low], scale)
    ft = shapely.polygons(np.stack([fx, fy], axis=2))
    floor_foot = valid_polygon(unary_union(ft[shapely.area(ft) > 1e-6]))
    if floor_foot is None:
        return None
    roofed = _covered(floor_foot, frame, cache, law, msl, zero + rim_y, scale)
    if roofed >= law.tables.structures.basin.basement_cover_min:
        notes.append(f"{what}: walls round its floor, but {100 * roofed:.0f} % of it lies "
                     f"under the frame's solids at its rim: a building, not a pit")
        return None
    under = hz[v[hz][:, :, 1].min(axis=1) < rim_y - ob.cover_flush_m]
    F = _placed_all(o, _types.SimpleNamespace(vertices=v, solid=under), zero, scale)
    pt = shapely.polygons(F[:, :, :2])
    foot = valid_polygon(unary_union(pt[shapely.area(pt) > 1e-6]))
    if foot is None or foot.area < ob.plate_min_area_m2:
        return None
    r = _around_ids(foot, {p.id for p in frame}, ag, ground, law)
    if r.source == "none":
        notes.append(f"{what}: a walled pit with no ground read around it")
        return None
    proud = zero + rim_y - r.z
    lift = 0.0 if 0.0 <= proud <= ob.authored_crest_max_m else -proud
    faces = F.copy()
    faces[:, :, 2] += lift
    fz = float(faces[:, :, 2].min())
    inside = [p for p in mates if p not in covers and _in_pit(p, foot, cache, tk)]
    k = sum(1 for n in notes if n.startswith(f"object floor walled pit {_base(o.path)}@"))
    note = (f"object floor walled pit {_base(o.path)}@{k}: floor y {floor_y:.2f}, "
            f"rim y {rim_y:.2f} "
            f"(walls of " + ", ".join(_base(p.path) for p in covers) + f"; "
            f"{100 * max(rims)[0]:.0f} % of its outline), open {100 * (1 - roofed):.0f} %; "
            f"rim {zero + rim_y:.2f} stands {proud:+.2f} m over the ground around it ("
            + ("its plates" if r.source == "plates" else "NO PLATES: the DEM")
            + f" {r.z:.2f}) -> frame lift {lift:+.2f}; floor {fz:.2f}, "
            f"{len(faces)} faces over {foot.area:.0f} m2; the frame's "
            f"{len(covers) + len(inside) + 1} placements standing in it move with it")
    notes.append(note)
    seats = tuple((p.id, p.path, _zero(p, msl) + lift) for p in (o, *covers, *inside))
    return ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@pit{k}", o.id, o.path,
                       tuple(p.id for p in covers), zero + lift, fz, foot, faces, (note,),
                       seats, rim_z=zero + rim_y + lift, lift=lift)


def _in_pit(p, foot, cache, tk: float) -> bool:
    """Does ``p``'s authored plan box stand mostly (half its area) in the
    pit's footprint (widened by a wall's thickness)?  The frame's
    placements elsewhere (a shared datum hangs a whole airport off one
    origin) keep their own seats."""
    y0, _y1, x0, x1, z0, z1 = cache.y_range(p.resolved)
    if not y0 < math.inf:
        # no vertices: a lights-only object is where its lights stand
        x0, x1, z0, z1 = _light_box(p.resolved)
    if not (x1 > x0 and z1 > z0):
        return False
    a, b, d, e, xo, yo = _obj8.placement_affine(p.xy, p.heading_deg)
    box = shapely.Polygon([(a * x + b * z + xo, d * x + e * z + yo)
                           for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))])
    return box.area > 0.0 and box.intersection(foot.buffer(tk)).area >= 0.5 * box.area


def _light_box(path: str) -> tuple[float, float, float, float]:
    """``(min_x, max_x, min_z, max_z)`` of an OBJ's positional light rows
    (``obj8_split._POSITIONAL``), or an empty box."""
    from .obj8_split import _POSITIONAL
    xs, zs = [], []
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            for ln in fh:
                tok = ln.split()
                k = _POSITIONAL.get(tok[0]) if tok else None
                if k is not None and len(tok) >= k + 3:
                    try:
                        xs.append(float(tok[k]))
                        zs.append(float(tok[k + 2]))
                    except ValueError:
                        continue
    except OSError:
        pass
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), max(xs), min(zs), max(zs)


def share_lift(floors: list, notes: list[str]) -> list:
    """Every floor read in a lifted frame (one sharing a seat with a floor
    whose ``lift`` is not 0) moves with it: its faces, zero and seats by the
    same lift — the frame is one rigid world."""
    lifted = [f for f in floors if getattr(f, "lift", 0.0)]
    if not lifted:
        return floors
    out = []
    for f in floors:
        if f.lift:
            out.append(f)
            continue
        ids = {pid for pid, _r, _z in f.seats}
        src = next((h for h in lifted if ids & {pid for pid, _r, _z in h.seats}), None)
        if src is None:
            out.append(f)
            continue
        d = src.lift
        faces = f.faces.copy()
        faces[:, :, 2] += d
        notes.append(f"object floor {f.id}: read in the frame of {src.id} -> lifted {d:+.2f}")
        out.append(_dc.replace(
            f, faces=faces, zero_z=f.zero_z + d, floor_z=f.floor_z + d, lift=d,
            rim_z=None if f.rim_z is None else f.rim_z + d,
            seats=tuple((pid, res, z + d) for pid, res, z in f.seats)))
    return out
