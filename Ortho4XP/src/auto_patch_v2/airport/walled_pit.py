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
5. SUNKEN — the floor, as authored, stands under the ground around it
   (the author's plates near the design ground, else the DEM): a floor
   over that ground is a roof or a deck in a building's frame (#2005).
   And the pit is sunken AS A WHOLE: ``pit_sunken_min_share`` of the plan
   under its rim stands under that ground — a road ramp that dips under
   its datum at one end and climbs to a viaduct between its parapets is
   no pit (#2091, OTHH TerminalRoads_03_002).
6. THE SEAT — the rim lands on the ground around the pit (the author's
   plates near the design ground, else the DEM; ``below_grade_witness
   .around``, the frame's own faces left out).  A rim standing 0 ..
   ``authored_crest_max_m`` over that ground keeps the authored seat
   (object-placement spec §18 (3)); any other rim re-seats the WHOLE FRAME
   by ``lift = ground - rim`` (the frame is one rigid world: every
   co-placed placement, and every other floor read in it, moves with it).
7. OPEN TRENCH (#1949 R2/R3, owner RULINGS 2026-11-17 (a)) -- only a pit
   whose floor lies under no roof brings the ground down to a wall lower
   than it (its open edges, ``planar/pit_bank``): the frame's solids at its
   rim cover less than ``trench_roof_max_share`` of the floor (a building's
   lower storey, a covered approach), and its walls do not hang under its
   plate (a plate on walls hanging under it is a roof object's low roof,
   :func:`_open_trench`).  Any other pit keeps its rim on the ground.

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

from ..geom.plane_groups import plane_groups as _plane_groups
from . import frame_entry as _frame_entry
from . import obj8 as _obj8
from .below_grade_witness import around as _around_ids
from .below_grade_witness import placed_all as _placed_all
from .below_grade_witness import zero_of as _zero
from .object_cut import _base, _face_normals_y, valid_polygon

__all__ = ["read_walled_pit", "share_lift", "Walls", "hard_deck_share", "wall_caps"]

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


def _plates_over(law, rim_abs: float):
    """:func:`_covered`'s face filter for the OPEN-TOP test (rule 4): a
    placement's near-horizontal solids standing at or above the rim
    (absolute, less ``cover_flush_m``)."""
    ob = law.tables.structures.tunnel.object

    def pick(p, g, zero: float) -> np.ndarray:
        t = g.solid[_face_normals_y(g.vertices, g.solid) >= ob.plate_normal_y_min]
        return t[g.vertices[t][:, :, 1].min(axis=1) >= rim_abs - zero - ob.cover_flush_m]
    return pick


def _decks_over(law, over_abs: float):
    """:func:`_covered`'s face filter for the HARD-DECK guard: the hard-deck
    faces (``ObjGeometry.hard_deck``) of a ``flag`` / ``signature`` deck --
    a signature deck's plate is its near-horizontal solids -- whose LOWEST
    vertex stands at or over ``over_abs`` (absolute)."""
    ob = law.tables.structures.tunnel.object

    def pick(p, g, zero: float) -> np.ndarray:
        kind = str(getattr(p, "deck_kind", "") or "")
        if kind not in ("flag", "signature"):
            return g.solid[:0]
        t = g.hard_deck
        if not len(t) and kind == "signature":
            t = g.solid[_face_normals_y(g.vertices, g.solid) >= ob.plate_normal_y_min]
        return t[g.vertices[t][:, :, 1].min(axis=1) >= over_abs - zero] if len(t) else t
    return pick


def _covered(floor_foot, frame, cache, zero_of, scale, faces) -> float:
    """The share of ``floor_foot`` under the faces ``faces(p, g, zero)``
    picks of each placement ``p`` of the ``frame`` (its zero
    ``zero_of(p)``; :func:`_plates_over`, :func:`_decks_over`), read on a
    grid of at most :data:`_COVER_SAMPLES` points."""
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
        g = cache.geometry(p.resolved) if p.resolved else None
        if g is None or not len(g.solid):
            continue
        bb = getattr(p, "plan_bbox", None)
        if bb is not None and not bb.intersects(box):
            continue
        zero = zero_of(p)
        t = faces(p, g, zero)
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
                    mate_share, notes: list[str], own_walls: bool = False):
    """``o``'s walled pit as an ``object_floor.ObjectFloor`` (module doc),
    or ``None``; a candidate that has walls but fails a test is noted.
    ``mate_share(p)`` is the plate share of ``p``'s resource; ``walls`` the
    read's :class:`Walls`; ``own_walls`` says ``o`` is an open hollow
    carrying its own walls (#1949 R1: their caps are no floor,
    :func:`wall_caps`)."""
    from .object_floor import FLOOR_REF, ObjectFloor
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    hz = t[_face_normals_y(v, t) >= ob.plate_normal_y_min]
    floor_y = _floor_level(v, hz, ob.plate_min_area_m2) if len(hz) else None
    if floor_y is None:
        return None
    px, py = _placed_plan(o, v[hz], (1.0, 1.0))
    tris = shapely.polygons(np.stack([px, py], axis=2))
    # LAW B (``frame_entry.union``): an open hollow's faces (#1949) can make
    # the exact overlay throw (LFMN, lane lomdb census)
    outline = valid_polygon(_frame_entry.union(tris[shapely.area(tris) > 1e-6],
                                               "walled_pit.outline"))
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
    floor_foot = valid_polygon(_frame_entry.union(ft[shapely.area(ft) > 1e-6], "walled_pit.floor"))
    if floor_foot is None:
        return None
    zero_of = lambda p: _zero(p, msl)  # noqa: E731
    decked = hard_deck_share(floor_foot, frame, cache, law, zero_of, zero + floor_y, scale)
    if decked >= law.tables.structures.deck.on_fraction:
        # a floor under a HARD DECK of its own frame -- one a road passes
        # under, ``bridge.clearance_minimum_m`` over the floor -- is the road
        # under a hard-deck bridge, read by ``planar/deck_bridge`` (class A,
        # 22n): read as a pit too, the frame took a second zero (KBNA taxiway
        # L: the deck seated 0.3 m proud of its taxiway, the trench floors
        # 1.1-4.5 m off the bridge's own).  A pit whose OWN floor is hard deck
        # is still a pit (#1689 R2 F8: OTHH TerminalRoads_02_000)
        notes.append(f"{what}: walls round its floor, but {100 * decked:.0f} % of it lies "
                     f"under a hard deck of its frame standing a road's clearance over it: "
                     f"a hard-deck bridge's road, not a pit")
        return None
    roofed = _covered(floor_foot, frame, cache, zero_of, scale, _plates_over(law, zero + rim_y))
    if roofed >= law.tables.structures.basin.basement_cover_min:
        notes.append(f"{what}: walls round its floor, but {100 * roofed:.0f} % of it lies "
                     f"under the frame's solids at its rim: a building, not a pit")
        return None
    under = hz[v[hz][:, :, 1].min(axis=1) < rim_y - ob.cover_flush_m]
    F = _placed_all(o, _types.SimpleNamespace(vertices=v, solid=under), zero, scale)
    pt = shapely.polygons(F[:, :, :2])
    plan = valid_polygon(_frame_entry.union(pt[shapely.area(pt) > 1e-6], "walled_pit.foot"))
    if plan is None or plan.area < ob.plate_min_area_m2:
        return None
    r = _around_ids(plan, {p.id for p in frame}, ag, ground, law)
    if r.source == "none":
        notes.append(f"{what}: a walled pit with no ground read around it")
        return None
    # A PIT IS SUNKEN: its floor, as authored, stands under the ground
    # around it.  A floor standing over that ground is a roof or a deck
    # inside a building, its "rim" a parapet or the storey above (#2005
    # KMCI: ten plates of the rigid terminal group, 2.1-9.7 m OVER the
    # ground around them, read as pits and sunk 7-13 m; OMDB's pit floor
    # stands 1.6 m under the DEM around it)
    if zero + floor_y >= r.z:
        notes.append(f"{what}: walls round its floor, but the floor {zero + floor_y:.2f} "
                     f"stands {zero + floor_y - r.z:+.2f} m over the ground around it ("
                     + ("its plates" if r.source == "plates" else "NO PLATES: the DEM")
                     + f" {r.z:.2f}): a roof or deck in its frame, not a pit")
        return None
    # ... and AS A WHOLE (#2091)
    sunk = _sunken_share(F, r.z)
    if sunk < ob.pit_sunken_min_share:
        notes.append(f"{what}: walls round its floor, but {100 * sunk:.0f} % of the plan "
                     f"under its rim stands under the ground around it ({r.z:.2f}; < "
                     f"{100 * ob.pit_sunken_min_share:.0f} %): a ramp climbing out of the "
                     f"ground between its parapets, not a pit")
        return None
    proud = zero + rim_y - r.z
    lift = 0.0 if 0.0 <= proud <= ob.authored_crest_max_m else -proud
    # the pit's plan (its walls' tops among it) seats the frame; the floor
    # is what the cut follows (#1949 R1: an open hollow's own wall caps are
    # no floor)
    foot = plan
    if own_walls and (cap := wall_caps(F, law)).any():
        notes.append(f"{what}: {int(cap.sum())} face(s) under its rim are the tops of its "
                     f"own walls, not its floor")
        F = F[~cap]
        pt = shapely.polygons(F[:, :, :2])
        foot = valid_polygon(_frame_entry.union(pt[shapely.area(pt) > 1e-6], "walled_pit.foot"))
        if foot is None:
            return None
    faces = F.copy()
    faces[:, :, 2] += lift
    fz = float(faces[:, :, 2].min())
    # rule 7 (owner RULINGS 2026-11-17 (a)): only an OPEN TRENCH banks its open
    # edges -- its floor under no roof
    hung = _hung(outline, (o, *covers), walls, floor_y, law)
    trench = _open_trench(roofed, hung, law)
    inside = [p for p in mates if p not in covers and _in_pit(p, plan, cache, tk)]
    k = sum(1 for n in notes if n.startswith(f"object floor walled pit {_base(o.path)}@"))
    note = (f"object floor walled pit {_base(o.path)}@{k}: floor y {floor_y:.2f}, "
            f"rim y {rim_y:.2f} "
            f"(walls of " + ", ".join(_base(p.path) for p in covers) + f"; "
            f"{100 * max(rims)[0]:.0f} % of its outline), open {100 * (1 - roofed):.0f} %; "
            f"rim {zero + rim_y:.2f} stands {proud:+.2f} m over the ground around it ("
            + ("its plates" if r.source == "plates" else "NO PLATES: the DEM")
            + f" {r.z:.2f}) -> frame lift {lift:+.2f}; floor {fz:.2f}, "
            f"{len(faces)} faces over {foot.area:.0f} m2; the frame's "
            f"{len(covers) + len(inside) + 1} placements standing in it move with it; "
            f"{100 * hung:.0f} % of its outline hangs walls under it: "
            + ("an open trench, its open edges banked" if trench
               else "no open trench, its rim stays on the ground"))
    notes.append(note)
    seats = tuple((p.id, p.path, _zero(p, msl) + lift) for p in (o, *covers, *inside))
    tops = _open_edges(foot, frame, cache, law, msl, scale, zero, zero + rim_y, lift, ground,
                       faces, fz) if trench else ()
    return ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@pit{k}", o.id, o.path,
                       tuple(p.id for p in covers), zero + lift, fz, foot, faces, (note,),
                       seats, rim_z=zero + rim_y + lift, lift=lift,
                       authored=tuple((p.id, _zero(p, msl)) for p in frame),
                       rim_proud_m=proud + lift, rim_tops=tops, rim_banks=bool(tops))


def _hung(outline, frame, walls: Walls, floor_y: float, law) -> float:
    """Rule 7 (a): the share of ``outline`` (every ``wall_sample_m``) along
    which a wall of ``frame`` (the floor object and the pit's walls) hangs
    more than ``cover_flush_m`` UNDER the floor and rises to it: the plate
    stands on its walls -- a roof, the floor the walls stand on under it."""
    ob = law.tables.structures.tunnel.object
    tk = float(ob.wall_face_max_thickness_m)
    box = shapely.box(*outline.bounds).buffer(tk)
    best = 0.0
    for p in frame:
        w = walls.reaching(p, floor_y - ob.cover_flush_m, floor_y - ob.cover_flush_m, box)
        if w is not None:
            best = max(best, _on_ring(outline, w, tk, float(ob.wall_sample_m))[0])
    return best


def _open_trench(roofed: float, hung: float, law) -> bool:
    """Rule 7 (owner RULINGS 2026-11-17 (a): "an object whose floor stands
    below the surrounding ground and which has NO ROOF over that floor"): is
    a walled pit an OPEN TRENCH?  Not when its frame's near-horizontal solids
    at its rim (rule 4's read) cover ``trench_roof_max_share`` of its floor
    or more -- a building's lower storey, a covered approach -- nor when its
    plate stands on walls hanging under it along ``floor_walled_min_share``
    of its outline (``hung``, :func:`_hung`): the plate is a roof, the floor
    the walls stand on lies under it.  Only an open trench brings the ground
    down to its walls (:func:`_open_edges`, ``planar/pit_bank``)."""
    ob = law.tables.structures.tunnel.object
    return roofed < float(ob.trench_roof_max_share) and hung < float(ob.floor_walled_min_share)


def _open_edges(foot, frame, cache, law, msl, scale, zero: float, rim_abs: float, lift: float,
                ground, faces: np.ndarray, fz: float) -> tuple:
    """#1949 R2: the pit's ``rim_tops`` on its OPEN EDGES
    (``floor_rim.open_edge_tops``) along the cut's rim (the footprint grown
    by half a wall, ``planar/object_floor_cells``' void band), the frame
    capped at its rim; the floor beside a rim point is the pit's floor there
    (within a wall's thickness), else its lowest ``fz``."""
    from ..geom.lowest_face import floor_z_at
    from .floor_rim import open_edge_tops
    if ground is None:
        return ()
    tk = float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)

    def floor(xs, ys):
        z = floor_z_at(faces, xs, ys, edge_m=tk)
        return np.where(np.isfinite(z), z, fz)
    return open_edge_tops(foot.buffer(0.5 * tk, join_style="mitre"),
                          [(p, _zero(p, msl)) for p in frame], cache, law, scale, zero,
                          rim_abs, lift, ground, floor)


def wall_caps(faces: np.ndarray, law) -> np.ndarray:
    """#1949 R1: which of an open hollow's under-rim ``faces`` (``(n, 3,
    3)`` placed, z absolute) are the TOPS OF ITS OWN WALLS -- a plane
    (``geom/plane_groups`` at ``crease_deg`` / ``hollow_m``) nowhere wider
    than ``wall_face_max_thickness_m`` (eroding it by half that leaves
    nothing) whose top stands more than ``hollow_m`` over the lowest face
    beside it (within that thickness), or beside none; or one that meets
    such a cap and stands no lower than it (one wall's top in two planes).
    A tapered wall's cap rises from under a metre over the floor at its
    nose (OMDB ``duong_2``'s gore: a flat 0.98 m nose, then the rise to the
    rim).  A plate pit's walls are another object: its read never asks."""
    ob = law.tables.structures.tunnel.object
    tk, step = float(ob.wall_face_max_thickness_m), float(ob.hollow_m)
    cap = np.zeros(len(faces), bool)
    if not len(faces):
        return cap
    tris = shapely.polygons(faces[:, :, :2])
    live = shapely.area(tris) > 1e-6
    tree = STRtree(tris)
    low, high = faces[:, :, 2].min(axis=1), faces[:, :, 2].max(axis=1)
    narrow = []
    for grp in _plane_groups(faces, float(ob.crease_deg), step):
        grp = grp[live[grp]]
        if not len(grp):
            continue
        poly = shapely.union_all(tris[grp])
        if not poly.buffer(-0.5 * tk).is_empty:
            continue
        near = tree.query(poly, predicate="dwithin", distance=tk)
        near = np.setdiff1d(near[live[near]], grp)
        if not len(near) or float(high[grp].max()) > float(low[near].min()) + step:
            cap[grp] = True
        else:
            narrow.append((grp, poly))
    grew = True
    while grew and narrow:
        grew, rest = False, []
        for grp, poly in narrow:
            touch = tree.query(poly, predicate="dwithin", distance=_TOUCH_M)
            touch = touch[cap[touch]]
            if len(touch) and float(high[grp].max()) >= float(low[touch].min()):
                cap[grp], grew = True, True
            else:
                rest.append((grp, poly))
        narrow = rest
    return cap


#: two planes of one wall's top meet within this (plan metres)
_TOUCH_M = 0.01


def _sunken_share(faces: np.ndarray, ground: float) -> float:
    """The share of ``faces``' plan area (frame metres, absolute z as
    authored) whose mean height stands under ``ground`` (#2091: a pit is
    sunken as a whole; rule 5 tests only its lowest plate)."""
    a = 0.5 * np.abs((faces[:, 1, 0] - faces[:, 0, 0]) * (faces[:, 2, 1] - faces[:, 0, 1])
                     - (faces[:, 2, 0] - faces[:, 0, 0]) * (faces[:, 1, 1] - faces[:, 0, 1]))
    tot = float(a.sum())
    if tot <= 0.0:
        return 0.0
    return float(a[faces[:, :, 2].mean(axis=1) < ground].sum()) / tot


def hard_deck_share(foot, frame, cache, law, zero_of, floor_abs: float,
                    scale=(1.0, 1.0)) -> float:
    """The share of plan ``foot`` (a floor at ``floor_abs``) lying under the
    HARD-DECK faces of a ``flag`` / ``signature`` deck of ``frame``
    (:func:`_decks_over`; each placement at ``zero_of(p)``) whose lowest
    vertex stands ``bridge.clearance_minimum_m`` or more over the floor: a
    road passes under that deck.  A floor that IS hard deck (OTHH
    ``TerminalRoads_02_000``, its own ``ATTR_hard_deck`` from y -1.75) is
    no road under one (#1689 R2 F8); 0.0 with no such deck."""
    if foot is None or foot.is_empty or not foot.area > 0.0:
        return 0.0
    over = floor_abs + float(law.tables.structures.bridge.clearance_minimum_m)
    return _covered(foot, frame, cache, zero_of, scale, _decks_over(law, over))


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
