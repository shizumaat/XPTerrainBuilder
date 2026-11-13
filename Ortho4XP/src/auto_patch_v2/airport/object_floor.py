"""A TRENCH OBJECT'S OWN FLOOR IS THE CUT (owner 2026-11-06T00:07Z, #1903):
"they have their own ramps so it should be a simple continuous trench
tracing the whole object for each of the tunnels".

THE RULE.  A pack trench, tunnel or underpass object that carries its own
floor and ramps defines the cut: the ground inside the object's footprint
is the object's own floor geometry — its floor plates and ramps, per
triangle, at the object's seat — projected over the whole footprint end to
end, including the ramps beyond its walls to the lips.  It is not a
profile along an axis that stops at the portals.  Mouths seat at that
floor; walls end on it.

THE WITNESS (geometry, never a name).  A FLOOR OBJECT is a placement whose
solid states a floor (``hanging_objects._has_floor``: a plate's worth of
near-horizontal faces ``shell_floor_min_m`` under its zero) and is a floor
rather than a structure — near-horizontal faces carry at least
``floor_object_min_share`` of its solid plan area — standing CO-PLACED
with the tunnel's cover (another placement within ``cover_placement_tol_m``,
same heading, whose solids reach ``shell_floor_min_m`` under its zero and
which is not itself a floor: the walls and roof the floor belongs to; EGLL
``Na.obj`` beside ``N.obj``).  The cover is the evidence that the floor is
a tunnel's, not a sea barrier's or a basement's.  And the floor stands SUNKEN:
``floor_sunken_min_m`` or more under the AUTHOR'S ground around it
(``geom/author_ground``: the pack's own plates, the DEM only where it laid
none; :func:`_sunken`) — the zero is no witness, a shared-datum pack hangs
every object off one datum and an at-grade tile reads metres "under its
zero" (KMCI, owner 2026-11-07 "No tunnel here"); an at-grade plate is
pavement, never a floor under itself.  A concave shell's rim is read
against the same ground (A7).

THE SURFACE.  The floor's near-horizontal faces that reach under
``cover_flush_m`` below the object's zero, placed in the airport frame with
absolute z (the placement's zero + authored y); where two faces overlap in
plan the LOWEST is the floor (:func:`floor_z_at`).  The footprint is their
plan union.  ``planar/object_floor_cells`` cuts it into the map and
``constraints/object_floor`` pins every vertex of it to the surface.

THE CONCAVE CUT SHELL (#1883 round 3, #1914; spec lgav-corridor-cut-and-
deck-ends-20261106 A1-A4, A7).  A §33 (6) B shell (``object_cut``: walls
and floor in one object, over a cover) that is no floor object but an
OPEN-TOP HOLLOW standing under its own zero (``_has_floor``) — its top
surface ``hollow_m`` or more under its own rim over
``shell_hollow_min_share`` of its inner plan (``geom/shape_class``, the
classification ``tools/drawn_site`` shares) — is the pack's own
ground: its surface is ALL its solid faces (banks included), its footprint
the plan of the faces standing under its rim, and its frame every
placement co-placed with it.  Where several floors and shells stand over
one point the ground is the LOWEST: a shallower one inside a deeper one
owns no ground there (a bridge liner inside the corridor shell).  A shell
that is the deepest surface with its rim at the ground (``shell_rim_ground_m``
over ``shell_rim_ground_share`` of its outline) is HIDDEN when
``hide_concave_shells`` (owner 2026-11-06T16:13Z): its row is left out of
the written DSF — and it leaves the terrain solve (2026-11-06d (1)): it owns
no ground and pins nothing (:func:`owns_ground`), the cut it stood for is
graded by the map's own laws (channel, road profiles, banks); its footprint
stays a witness of the cut's extent (:func:`has_footprint`: the deck pieces
over it, the cut ring they are seated by; A4's withdrawal of the shallower
shells inside it).

THE FRAME'S ONE ZERO (B1).  Every placement of a floor's frame is written
whole at the zero the floor was read at — the pack's shared datum — except
a hard-deck piece the airport's pavement drives across
(``planar/object_floor_cells.floor_decks``), which is seated flush with its
taxiway at both end lines.

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely import STRtree
from shapely.ops import unary_union

from ..geom import author_ground as _ag
from ..geom import shape_class as _shape
from ..geom.lowest_face import floor_z_at  # noqa: F401  (re-exported)
from ..model import structures as _ms
from . import floor_rim as _floor_rim
from . import frame_entry as _frame_entry
from . import obj8 as _obj8
from . import pit_frame as _pf
from . import terrain_shaped as _ts
from . import walled_pit as _wp
from .below_grade_witness import around as _around_ids
from .below_grade_witness import author_ground as _author_ground_of
from .below_grade_witness import floor_share as _floor_share
from .below_grade_witness import placed_all as _placed_all
from .below_grade_witness import xp as _xp
from .below_grade_witness import zero_of as _zero
from .hanging_objects import _co_placed, _has_floor
from .object_cut import _base, _face_normals_y, _plan_segments, placement_order, valid_polygon
from .walled_pit import share_lift as _share_lift

__all__ = ["ObjectFloor", "FloorDeck", "read_object_floors", "floor_z_at", "seat_records",
           "floor_portals", "owns_ground", "has_footprint", "FLOOR_REF", "FLOOR_WALL_REF", "SHELL",
           "HIDDEN_SEAT", "FRAME_SEAT"]

#: :attr:`ObjectFloor.kind` of a concave cut shell (else ``"floor"``)
SHELL = "shell"
#: the seat record's ``seat`` of a hidden shell's row (A7): the row is
#: dropped from the written DSF (``terrain_shaped.row_seats``)
HIDDEN_SEAT = _ts.HIDDEN_SEAT
#: the seat record's ``seat`` of a deck placement of a floor's frame (B1/B2)
FRAME_SEAT = _ts.FRAME_SEAT

#: The planar ref of a floor's cut face (``FLOOR_REF + id``) and of the
#: void band around it (``FLOOR_WALL_REF + id``): ``model.structures``'.
FLOOR_REF = _ms.OBJECT_FLOOR_REF
FLOOR_WALL_REF = _ms.OBJECT_FLOOR_WALL_REF


@_dc.dataclass(frozen=True)
class ObjectFloor:
    """One trench object's floor in the AIRPORT frame: ``faces`` the
    ``(n, 3, 3)`` placed ``(x, y, z)`` corners of its below-grade floor
    faces (z absolute), ``footprint`` their plan union (Polygon or
    MultiPolygon), ``covers`` the co-placed placement ids it floors."""

    id: str
    object_id: str
    resource: str
    covers: tuple[str, ...]
    zero_z: float
    floor_z: float
    footprint: object
    faces: np.ndarray = _dc.field(repr=False, compare=False)
    notes: tuple[str, ...] = ()
    #: ``(placement id, resource, zero)`` of the floor and every placement
    #: of its frame: the rows written WHOLE at their read zero
    #: (:func:`seat_records`) — the cut is that zero's floor, so the
    #: authored seat is the one that lands on it (B1)
    seats: tuple[tuple[str, str, float], ...] = ()
    #: ``"floor"`` (a floor object or a §33 (6) B shell's plates) or
    #: :data:`SHELL` (a concave cut shell, its whole surface)
    kind: str = "floor"
    #: a shell's own rim (absolute z)
    rim_z: "float | None" = None
    #: A7: the shell's row is left out of the written DSF
    hidden: bool = False
    #: B2: the hard-deck pieces of its frame the pavement drives across
    decks: tuple = ()
    #: #1949: the metres its whole frame was moved so a walled pit's rim
    #: lands on the ground around it (``airport/walled_pit``); 0 = authored
    lift: float = 0.0
    #: #1949 (RULINGS 2026-11-11f): a walled pit's AUTHORED zeros --
    #: ``(placement id, zero as authored)`` of the floor and every placement
    #: co-placed with it (one authored frame) -- and how far its rim stands
    #: over the ground around it as seated: what the rail group meeting it
    #: is read against (``airport/pit_frame``); ``()`` for every other floor
    authored: tuple[tuple[str, float], ...] = ()
    rim_proud_m: float = 0.0
    #: #1921 / #1936 (RULINGS 2026-11-06d (5)): ``((x, y, dz), ...)`` the
    #: frame's top along the cut's rim, metres over ``zero_z``
    #: (``airport/floor_rim``): where the ground and the pavement meet it
    rim_tops: tuple = ()
    #: #1971 (spec interchange-levels v2 §3.1): how far the cut stands under
    #: this floor; ``None`` is the law's ``[tunnel.object] floor_clearance_m``
    #: (a floor plate kept clear, 2026-11-06d (4)); a deck stack's walls have
    #: no plate and state the floor with their feet: ``0.0``
    clearance_m: "float | None" = None

    def cut_clearance(self, law_clearance: float) -> float:
        """How far the cut stands under this floor: its own
        :attr:`clearance_m`, else the law's (``law_clearance``)."""
        return float(law_clearance) if self.clearance_m is None else float(self.clearance_m)


@_dc.dataclass(frozen=True)
class FloorDeck:
    """B2: one hard-deck piece of a floor's frame the airport's pavement
    drives across (``planar/object_floor_cells.floor_decks``): ``ring`` its
    plan (frame xy), ``seats_a`` / ``seats_b`` its two END LINES' stations
    and ``top_a`` / ``top_b`` the authored deck top (y) there.  The solve
    holds the pavement at both end lines flush with ONE zero of this piece
    (``constraints/edge_deck``); the object stage seats the piece there."""

    id: str
    object_id: str
    resource: str
    ring: tuple
    seats_a: tuple
    seats_b: tuple
    top_a: float
    top_b: float


def owns_ground(f: "ObjectFloor") -> bool:
    """Does ``f`` own any ground — cut cells, pins, portal and mouth seats
    (A4: a shallower surface inside a deeper one owns none; 2026-11-06d (1):
    a HIDDEN shell owns none, it leaves the terrain solve)?"""
    return not f.hidden and has_footprint(f)


def has_footprint(f: "ObjectFloor") -> bool:
    """Does ``f`` state a cut's extent — its footprint, read as a WITNESS
    even when hidden (2026-11-06d (1): the deck pieces over it, the cut ring
    the object stage seats them by)?"""
    fp = f.footprint
    return fp is not None and not fp.is_empty and fp.area > 0.0


#: the ring's sampling step for :func:`_walled_share` (metres): the share
#: is the fraction of ring samples within the wall thickness of a deep
#: wall, so it reads to ~one step per wall end against a 0.5 threshold
_RING_STEP_M = 0.25


def _deep_walls(p: _obj8.PlacedObject, cache: _obj8.ResourceCache, law):
    """``p``'s deep wall faces (reaching ``shell_floor_min_m`` under its
    zero) as an STRtree of plan segments in the frame, or ``None`` when
    it stands none.  It reads ``p`` alone: a floor asks it of every
    co-placed mate, so :class:`_WallBands` keeps one per placement (a
    shared-datum pack co-places every object — KMCI/LFLL buffered a whole
    terminal's walls per floor x mate and sat an hour in step 21, lane
    slowstep 2026-11-06)."""
    ob = law.tables.structures.tunnel.object
    g = cache.geometry(p.resolved)
    if g is None or not len(g.solid):
        return None
    v, t = g.vertices, g.solid
    w = t[_face_normals_y(v, t) < ob.plate_normal_y_min]
    if len(w):
        w = w[v[w][:, :, 1].min(axis=1) <= -ob.shell_floor_min_m]
    segs = _plan_segments(v, w) if len(w) else []
    if not segs:
        return None
    mat = _obj8.placement_affine(p.xy, p.heading_deg)
    return STRtree([_frame_entry.transform(sg, mat) for sg in segs])


class _WallBands:
    """One :func:`_deep_walls` per placement for one read."""

    def __init__(self, cache: _obj8.ResourceCache, law):
        self.cache, self.law, self._by_id = cache, law, {}

    def __call__(self, p: _obj8.PlacedObject):
        if p.id not in self._by_id:
            self._by_id[p.id] = _deep_walls(p, self.cache, self.law)
        return self._by_id[p.id]


def _walled_share(foot, p: _obj8.PlacedObject, cache: _obj8.ResourceCache, law,
                  bands: "_WallBands | None" = None) -> float:
    """The share of the floor footprint's ring (frame) within
    ``wall_face_max_thickness_m`` of ``p``'s wall faces reaching
    ``shell_floor_min_m`` under its zero — the cover's walls standing on
    the floor's edges ("walls end on it") — read as the fraction of ring
    samples every :data:`_RING_STEP_M` within that distance of a wall
    segment (an indexed distance query: no buffer of the cover's walls,
    which per floor x mate was the step-21 stall)."""
    tree = (bands or _WallBands(cache, law))(p)
    if tree is None:
        return 0.0
    ring = foot.boundary
    L = ring.length
    if L <= 0.0:
        return 0.0
    n = max(1, int(math.ceil(L / _RING_STEP_M)))
    pts = shapely.line_interpolate_point(ring, (np.arange(n) + 0.5) * (L / n))
    tk = law.tables.structures.tunnel.object.wall_face_max_thickness_m
    hit = tree.query(pts, predicate="dwithin", distance=tk)[0]
    return float(len(np.unique(hit))) / n


def _ground_at(ag: "_ag.AuthorGround", oid: str, ground):
    """``(xs, ys) -> z``: the author's ground under each point, the design
    ground where no plate stands (``oid``'s own faces left out)."""
    def at(xs, ys):
        z = ag.at(xs, ys, exclude={oid})
        if ground is None:
            return z
        return np.where(np.isfinite(z), z, np.asarray(ground(xs, ys), float).ravel())
    return at


def _sunken(o, g, msl, ag, ground, law, scale, notes: list[str]) -> tuple[bool, str]:
    """``(sunken, why)``: does floor object ``o`` stand SUNKEN — its floor's
    median height ``floor_sunken_min_m`` or more under the AUTHOR'S ground
    around it (``below_grade.around``; the DEM only where the author laid no
    plates, and ``why`` says so)?  Never its zero: a shared-datum pack hangs
    every object off one datum (KMCI 310.70, its at-grade tiles 8 m "under"
    it).  A refusal is noted."""
    ob = law.tables.structures.tunnel.object
    got = _placed_floor(o, g, _zero(o, msl), law, scale)
    if got is None:
        return True, ""
    faces, foot = got
    r = _around_ids(foot, {o.id}, ag, ground, law)
    if r.source == "none":
        return True, "no ground reads around it"
    depth = r.z - _median_z(faces)
    why = (f"{depth:.2f} m under the author's ground around it ("
           + ("its plates" if r.source == "plates" else "NO PLATES: the DEM")
           + f" {r.z:.2f}, plates over {100 * r.share:.0f} % of the ring)")
    if depth >= ob.floor_sunken_min_m:
        return True, why
    notes.append(f"{o.id} {_base(o.path)}: its floor stands {why} < "
                 f"{ob.floor_sunken_min_m:g}: an at-grade plate, pavement — not a sunken floor")
    return False, why


def _median_z(faces: np.ndarray) -> float:
    """The plan-area-weighted median height of placed faces."""
    P = faces
    a = 0.5 * np.abs((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
                     - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
    z = P[:, :, 2].mean(axis=1)
    k = np.argsort(z)
    c = np.cumsum(a[k])
    if c[-1] <= 0.0:
        return float(np.median(z))
    return float(z[k][min(len(k) - 1, int(np.searchsorted(c, 0.5 * c[-1])))])


def _mate_share(p: _obj8.PlacedObject, cache: _obj8.ResourceCache, law,
                shares: dict[str, float]) -> float:
    """:func:`_floor_share` of ``p``'s resource, read once per resource."""
    if p.resolved not in shares:
        shares[p.resolved] = _floor_share(cache.geometry(p.resolved), law)
    return shares[p.resolved]


def _placed_floor(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, zero: float, law,
                  scale=(1.0, 1.0)):
    """``(faces, footprint)`` of the floor's below-grade faces in the frame,
    or ``None`` when they carry less than a plate's worth."""
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    hz = t[_face_normals_y(v, t) >= ob.plate_normal_y_min]
    if len(hz):
        hz = hz[v[hz][:, :, 1].min(axis=1) < -ob.cover_flush_m]
    if not len(hz):
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    F = v[hz]
    px, py = _xp(a * F[:, :, 0] + b * F[:, :, 2] + xo, d * F[:, :, 0] + e * F[:, :, 2] + yo,
                 o, scale)
    faces = np.stack([px, py, zero + F[:, :, 1]], axis=2)
    tris = shapely.polygons(np.stack([px, py], axis=2))
    tris = tris[shapely.area(tris) > 1e-6]
    foot = valid_polygon(unary_union(tris)) if len(tris) else None
    if foot is None or foot.area < ob.plate_min_area_m2:
        return None
    return faces, foot


def _shell_candidate(g: "_obj8.ObjGeometry | None", law) -> bool:
    """A cheap pre-read: the plan of the faces standing ``shell_floor_min_m``
    under the zero carries ``shell_hollow_min_share`` of the solid's plan
    (a building over a basement carries its roofs and floors above)."""
    ob = law.tables.structures.tunnel.object
    if g is None or not len(g.solid):
        return False
    P = g.vertices[g.solid]
    plan = 0.5 * np.abs((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 2] - P[:, 0, 2])
                        - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 2] - P[:, 0, 2]))
    tot = float(plan.sum())
    deep = P[:, :, 1].mean(axis=1) <= -ob.shell_floor_min_m
    return tot > 0.0 and float(plan[deep].sum()) >= ob.shell_hollow_min_share * tot


def _shape_of(faces: np.ndarray, law) -> tuple[dict, "_shape.Raster | None"]:
    """``(shape reading, raster)`` of placed faces (``geom/shape_class``)."""
    ob = law.tables.structures.tunnel.object
    r = _shape.rasterise(faces, int(ob.shell_raster_cells))
    return _shape.shape_of(r, faces.reshape(-1, 3), band_m=ob.shell_rim_band_m,
                           reach_m=ob.wall_face_max_thickness_m, hollow_m=ob.hollow_m,
                           stacked_m=ob.shell_stacked_m, flat_m=ob.shell_flat_m,
                           min_share=ob.shell_hollow_min_share), r


def _under_rim(faces: np.ndarray, rim: float, law):
    """A3: the plan union of the shell's faces standing under its own rim
    (the hollow, banks and lips; never the crest above it), or ``None``
    short of a plate's worth.  MEASURED LGAV ``Trench_06``: the pack's floor
    stands up to 8 m OVER the DEM along the south-west kilometre (its
    plateau is the pack's, the DEM's ground falls away), so the design
    ground cannot bound it — the shell's own rim does."""
    ob = law.tables.structures.tunnel.object
    tris = shapely.polygons(faces[:, :, :2])
    keep = (shapely.area(tris) > 1e-6) & (faces[:, :, 2].mean(axis=1) <= rim)
    foot = valid_polygon(unary_union(tris[keep])) if keep.any() else None
    if foot is None or foot.area < ob.plate_min_area_m2:
        return None
    return foot


def _rim_at_ground(r: "_shape.Raster | None", ground, foot, law) -> float:
    """A7: the share of the shell's outline band whose own top stands
    within ``shell_rim_ground_m`` of the DESIGN ground there — the shell's
    own surface where its footprint owns the ground (A3: the cut is cut to
    it), else ``ground`` (the DEM).  MEASURED LGAV ``Trench_06``: against
    the DEM alone 15 % (its south-west kilometre stands on a plateau the DEM
    does not have); the terrain there is the shell's own once it is cut."""
    ob = law.tables.structures.tunnel.object
    if r is None or ground is None:
        return 0.0
    band, _inner = _shape.outline_band(r, ob.shell_rim_band_m)
    ij = np.argwhere(band)
    if not len(ij):
        return 0.0
    e, n = r.centres(ij)
    top = r.top[band]
    owned = shapely.contains_xy(foot.buffer(ob.shell_rim_ground_m), e, n)
    gz = np.where(owned, top, np.asarray(ground(e, n), float))
    ok = np.isfinite(gz)
    if not ok.any():
        return 0.0
    return float((np.abs(top[ok] - gz[ok]) <= ob.shell_rim_ground_m).mean())


def _deepest(floors: list["ObjectFloor"], law, notes: list[str]) -> list["ObjectFloor"]:
    """A4: the ground under several floors is the LOWEST — each floor less
    the plan of every other floor standing deeper over their overlap (a
    bridge liner inside the corridor shell owns no ground there)."""
    ob = law.tables.structures.tunnel.object
    out = []
    for f in floors:
        fp = f.footprint
        for g in floors:
            if g is f or fp is None or fp.is_empty or not fp.intersects(g.footprint):
                continue
            ov = fp.intersection(g.footprint)
            if ov.area < ob.plate_min_area_m2:
                continue
            q = [p.representative_point() for p in getattr(ov, "geoms", [ov])
                 if p.area >= 1.0]
            xs, ys = [p.x for p in q], [p.y for p in q]
            zf = floor_z_at(f.faces, xs, ys, edge_m=0.5)
            zg = floor_z_at(g.faces, xs, ys, edge_m=0.5)
            if np.isfinite(zf).any() and np.isfinite(zg).any() and \
                    float(np.nanmedian(zg)) < float(np.nanmedian(zf)) - ob.hollow_m:
                fp = fp.difference(g.footprint)
        if fp is not f.footprint:
            # a shallower shell INSIDE a deeper one (most of it) owns none
            inside = f.footprint.area - fp.area >= 0.5 * f.footprint.area
            fp = fp if fp.area >= ob.plate_min_area_m2 and not inside else shapely.Polygon()
            notes.append(f"{f.id}: a deeper surface owns its ground — "
                         f"{f.footprint.area - fp.area:.0f} m2 withdrawn, "
                         f"{fp.area:.0f} m2 left (A4)")
            f = _dc.replace(f, footprint=fp, hidden=False)
        out.append(f)
    return out


def read_object_floors(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                       law, msl: _t.Mapping[str, float],
                       taken: _t.AbstractSet[str] = frozenset(),
                       shells: _t.Mapping[str, str] | None = None,
                       ground: "_t.Callable | None" = None,
                       scale: tuple[float, float] = (1.0, 1.0)
                       ) -> tuple[list[ObjectFloor], list[str]]:
    """Every FLOOR OBJECT (module doc) as an :class:`ObjectFloor`, and one
    note per floor read or refused.  ``taken`` are placement ids another
    reader already cuts by their own floor (an object is read once);
    ``shells`` maps each placement ``object_cut`` admitted as a §33 (6) B
    shell (walls and floor in one object) to ``(its cover's placement id,
    the region between its walls)`` — only those are read as floors
    without being floor objects, and only that cover is theirs; a CONCAVE
    SHELL (module doc) is read whole, its frame every co-placed placement.
    ``ground(xs, ys)`` is the design ground (the DEM) A7 reads the rim
    against; ``scale`` the frame's metres per OBJ metre
    (``model.frame.xplane_metre_scale``).  A
    shared-datum pack co-places everything (LGAV ``Trench_0x``, one
    anchor), so co-placement alone is no tunnel
    evidence: a floor object's cover must also stand its walls ON the
    floor's edges — at least ``floor_walled_min_share`` of the footprint's
    ring within ``wall_face_max_thickness_m`` of the cover's deep wall
    faces (EGLL 82-99 %; LGAV's stack and KBNA ``Metropolitan-part7``
    0-2 %)."""
    ob = law.tables.structures.tunnel.object
    placed = [o for o in placement_order(objects)
              if o.resolved is not None and not _obj8.is_stock_library_resource(o.path)]
    out: list[ObjectFloor] = []
    notes: list[str] = []
    k_by_res: dict[str, int] = {}
    bands = _WallBands(cache, law)
    shares: dict[str, float] = {}
    ag = _author_ground_of(placed, cache, law, msl, scale, shares, ground)
    near = _CoPlaced(placed, ob.cover_placement_tol_m)
    pit_walls = _wp.Walls(cache, law)
    floored = {o.id for o in placed if o.id not in taken and _has_floor(cache, o, law)}
    for o in placed:
        if o.id in taken or o.id in floored:
            continue
        # #1949: a floor AT a shared datum, walled to a rim over it
        got = _walled_pit(o, cache, law, msl, ag, ground, scale, shares, near, pit_walls,
                          notes)
        if got is not None:
            out.append(got)
    # a walled pit's frame stands under its rim: none of it is the author's
    # ground any other floor is read against (#1949: hamnen's floor, 0.31
    # over a 1.70 DEM, was the "ground" duong_ray_FACE stood 11.43 m over)
    ag = ag.without({pid for f in out for pid, _r, _z in f.seats})
    for o in placed:
        if o.id not in floored:
            continue
        g = cache.geometry(o.resolved)
        share = _floor_share(g, law)
        mates = near(o)
        shells = shells or {}
        sunk = ""
        if share >= ob.floor_object_min_share:
            ok, sunk = _sunken(o, g, msl, ag, ground, law, scale, notes)
            if not ok:
                continue
            # a FLOOR object: its cover is a co-placed structure hanging
            # under its zero whose walls stand on the floor's edges
            covers = [p for p in mates
                      if cache.y_range(p.resolved)[0] <= -ob.shell_floor_min_m
                      and _mate_share(p, cache, law, shares)
                      < ob.floor_object_min_share]
            placed_floor = _placed_floor(o, g, 0.0, law)
            covers = [p for p in covers if placed_floor is not None
                      and _walled_share(placed_floor[1], p, cache, law, bands)
                      >= ob.floor_walled_min_share]
        elif o.id in shells:
            # a SHELL (its own walls and floor, §33 (6) B): a CONCAVE CUT
            # SHELL (#1883 r3 A1) is the pack's own ground, its frame every
            # co-placed placement; else its cover is the one object_cut
            # paired it with
            got = _concave(o, g, msl, law, mates,
                           _ground_at(ag, o.id, ground) if ground is not None else None,
                           notes, scale) \
                if _shell_candidate(g, law) else None
            if got is not None:
                out.append(got)
                continue
            covers = [p for p in mates if p.id == shells[o.id][0]]
        else:
            continue
        if not covers:
            notes.append(f"{o.id} {_base(o.path)}: a floor ({share:.0%} near-horizontal) with "
                         f"no co-placed cover (walls under its zero, or a flush hard deck "
                         f"over its own walls): not a tunnel's floor")
            continue
        zero = _zero(o, msl)
        got = _placed_floor(o, g, zero, law, scale)
        if got is None:
            notes.append(f"{o.id} {_base(o.path)}: no below-grade floor face of a plate's worth")
            continue
        faces, foot = got
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        fz = float(faces[:, :, 2].min())
        note = (f"object floor {_base(o.path)}@{k}: {len(faces)} faces over {foot.area:.0f} m2, "
                f"floor {fz:.2f} (zero {zero:.2f}), the floor of "
                + ", ".join(_base(p.path) for p in covers)
                + (f"; sunk {sunk}" if sunk else ""))
        notes.append(note)
        # B1: the frame's every placement at the zero the floor was read at
        frame = (o, *covers, *(p for p in mates if p not in covers))
        seats = tuple((p.id, p.path, _zero(p, msl)) for p in frame)
        band = 0.5 * float(ob.wall_face_max_thickness_m)
        tops = _floor_rim.rim_tops(foot.buffer(band, join_style="mitre"),
                                   [(p, _zero(p, msl)) for p in frame], cache, law, scale, zero)
        out.append(ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@{k}", o.id, o.path,
                               tuple(p.id for p in covers), zero, fz, foot, faces, (note,),
                               seats, rim_tops=tops))
    out = _deepest(_share_lift(out, notes), law, notes)
    return out, notes


class _CoPlaced:
    """The co-placed mates of a placement (``hanging_objects._co_placed``),
    looked up in a plan grid ``tol`` wide rather than over every placement
    (the walled-pit read asks it of every plate object)."""

    def __init__(self, placed, tol: float):
        self.tol, self.cells = tol, {}
        for p in placed:
            self.cells.setdefault(self._key(p.xy), []).append(p)

    def _key(self, xy):
        return (int(math.floor(xy[0] / self.tol)), int(math.floor(xy[1] / self.tol)))

    def __call__(self, o):
        i, j = self._key(o.xy)
        return [p for di in (-1, 0, 1) for dj in (-1, 0, 1)
                for p in self.cells.get((i + di, j + dj), ())
                if p.id != o.id and _co_placed(o, p, self.tol)]


def _walled_pit(o, cache, law, msl, ag, ground, scale, shares, near, walls, notes):
    """#1949 (``airport/walled_pit``): ``o`` read as a walled pit's floor
    when it is a plate object with a co-placed mate that is not."""
    ob = law.tables.structures.tunnel.object
    g = cache.geometry(o.resolved)
    if g is None or not len(g.solid) or _mate_share(o, cache, law, shares) \
            < ob.floor_object_min_share:
        return None
    mates = near(o)
    if not any(_mate_share(p, cache, law, shares) < ob.floor_object_min_share for p in mates):
        return None
    return _wp.read_walled_pit(o, g, mates, cache, law, msl, ag, ground, scale, walls,
                               lambda p: _mate_share(p, cache, law, shares), notes)


def _concave(o, g, msl, law, mates, ground, notes: list[str],
             scale=(1.0, 1.0)) -> "ObjectFloor | None":
    """A concave cut shell's :class:`ObjectFloor`, or ``None`` (a note
    says why) — A1-A3, A7's hiding read here."""
    ob = law.tables.structures.tunnel.object
    zero = _zero(o, msl)
    faces = _placed_all(o, g, zero, scale)
    sh, r = _shape_of(faces, law)
    if sh["class"] != _shape.CONCAVE:
        return None
    foot = _under_rim(faces, float(sh["rim"]), law)
    if foot is None:
        notes.append(f"{o.id} {_base(o.path)}: a concave shell with no plate's worth under "
                     f"its rim")
        return None
    at_ground = _rim_at_ground(r, ground, foot, law)
    hidden = bool(ob.hide_concave_shells) and at_ground >= ob.shell_rim_ground_share
    fz = float(faces[:, :, 2].min())
    note = (f"concave shell {_base(o.path)}: {len(faces)} faces, hollow "
            f"{100 * sh['hollow']:.1f} %, rim {sh['rim']:.2f}, footprint {foot.area:.0f} m2 "
            f"under it, lowest {fz:.2f} (zero {zero:.2f}); rim at the ground over "
            f"{100 * at_ground:.0f} % of its outline -> "
            + ("HIDDEN (A7)" if hidden else "drawn") + "; frame "
            + ", ".join(_base(p.path) for p in mates))
    notes.append(note)
    seats = tuple((p.id, p.path, _zero(p, msl)) for p in (o, *mates))
    return ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@shell", o.id, o.path,
                       tuple(p.id for p in mates), zero, fz, foot, faces, (note,), seats,
                       kind=SHELL, rim_z=float(sh["rim"]), hidden=hidden)


def seat_records(floors: _t.Iterable[ObjectFloor], to_ll=None) -> list[dict[str, _t.Any]]:
    """One seat record per placement of every object floor's frame: written
    WHOLE as ``OBJECT_MSL`` at the zero the cut was read from ("mouths seat
    at that floor; walls end on it") — never split and re-seated on feet
    that stand in its own cut — each placement once; a HIDDEN shell's own
    row :data:`HIDDEN_SEAT` (A7).  With ``to_ll`` a floor owning ground
    carries its footprint's ring (``cut_deck_seat.CUT_RING``): the pack cut a
    deck of its frame is seated over (B2)."""
    from .cut_deck_seat import CUT_RING
    floors = list(floors)
    # ONE record per placement, whichever floor's frame names it first: a
    # hidden shell's row is dropped, a deck of any frame is planned
    hidden = {f.object_id for f in floors if f.hidden}
    decks = {d.object_id: (d.resource, f.zero_z) for f in floors for d in f.decks}
    rings = {}
    for f in floors:
        if to_ll is not None and f.decks and has_footprint(f):
            part = max(getattr(f.footprint, "geoms", [f.footprint]), key=lambda q: q.area)
            rings[f.object_id] = [[round(la, 9), round(lo, 9)] for la, lo in
                                  (to_ll(x, y) for x, y in part.exterior.coords)]
    out: list[dict[str, _t.Any]] = []
    seen: set[str] = set()
    for f in floors:
        for pid, res, z in f.seats:
            if pid in seen or pid in decks:
                continue
            seen.add(pid)
            rec = {"id": pid, "resource": res, "datum": "object_floor",
                   "seat": HIDDEN_SEAT if pid in hidden else _ts.OBJECT_FLOOR_SEAT,
                   "elevation": round(float(z), 3)}
            if pid in rings:
                rec[CUT_RING] = rings[pid]
            if f.authored:
                _pf.stamp(rec, f, to_ll if pid == f.object_id else None)
            out.append(rec)
    for pid, (res, z) in sorted(decks.items()):
        out.append({"id": pid, "resource": res, "datum": "object_floor", "seat": FRAME_SEAT,
                    "elevation": round(float(z), 3)})
    return out


def floor_portals(portals: _t.Sequence, floors: _t.Sequence[ObjectFloor]) -> tuple:
    """The pack portals with every pin a trench object's floor states read
    off THAT floor (#1903, owner 2026-11-06 "mouths seat at that floor"): a
    portal on the floor object or one of its covers takes the floor's own
    height at the footprint point nearest its bore end — never the floor's
    deepest level, nor a face bottom the object stage would re-seat (EGLL
    11 west mouth: the portal pinned 16.14, 11b's lowest plate, where the
    floor stands 17.16 at that end).  A portal off every floor is unchanged."""
    by_id = {pid: f for f in floors if owns_ground(f) for pid, _r, _z in f.seats}
    if not by_id:
        return tuple(portals)
    out = []
    for p in portals:
        f = by_id.get(p.object_id)
        if f is None:
            out.append(p)
            continue
        from shapely.geometry import Point
        from shapely.ops import nearest_points
        q = nearest_points(f.footprint, Point(p.end_xy))[0]
        z = floor_z_at(f.faces, [q.x], [q.y], edge_m=0.5)[0]
        if z != z:
            out.append(p)
            continue
        out.append(_dc.replace(p, floor_z=float(z), bottom_y=None))
    return tuple(out)
