"""THE PACK'S OWN CROSSING OVER A COVERED ROAD (spec ``docs/specs/2123.md``
A1 (2) "the pack always wins"; owner 2026-11-17: "We should only be adding
our bridges when the pack does not provide an object").

A generated deck (``planar/deck_generated``) stands only where the pack
does not model the crossing itself.  Two readings of the pack, each a
refusal of the deck piece:

(a) a HARD DECK -- an ``ATTR_hard_deck`` placement or a signature deck
    (``PlacedObject.hard_deck``) -- overlapping the piece, whether or not
    ``deck_bridges`` admitted it as a bridge (a co-placed bridge + tunnel
    pair the walled-trench branch refuses is still the pack's deck);
(b) a MODELLED CROSSING: a pack STRUCTURE -- a placement whose geometry
    reaches more than ``[deck_gen] pack_structure_depth_m`` under its own
    ground, its deep vertices' hull overlapping the piece by
    ``min_area_m2`` -- AND a TOP over the road: the up-facing
    near-horizontal faces of any placement (solid or draped) within
    ``pack_structure_depth_m`` of its ground running over at least
    ``pack_cover_share`` of the covered roads' axis inside the piece.

(c) THE PACK'S DECK BESIDE IT (owner RULINGS 2026-11-17n: "When an
    installed pack has an object that models the deck, generate NOTHING
    there"): a pack HARD DECK (a: the flag -- an invisible landable plane
    is one -- or a signature deck, ``airport/deck_signature``) that ABUTS
    the piece: within
    ``[deck_gen] bearing_m + edge_margin_m`` of it (the ring's own growth
    past the pavement over the cut: a pack deck there touches the ring),
    or standing over the covered road itself within the cut's approach
    run of the piece (``reach``: the floor's depth over ``[tunnel]
    ramp_grade``, the stretch the road runs in the generated cut past the
    ring) -- the road the generated deck would span runs on under the
    pack's own deck, one crossing the pack models.  MEASURED LPMA
    (ldeck3): ``runway23_area.obj``'s hard deck stands 11.45 m beside the
    generated piece over trunk ``-44`` / ``-23``, and ``-23``'s mapped way
    runs 203 m under it.

Neither half of (b) refuses alone (owner 2026-11-17 14:48Z): a pack CUT
with no top over the road (a pit, ramps, walls) supplies the trench and
the deck is still ours, seated to the cut; pavement the pack drapes over
the road with no structure under it is the "drawn only as pavement" case
the deck exists for.  A face drawn BEFORE the terrain mesh
(``ATTR_layer_group terrain`` at a negative offset, ``ObjGeometry.
under_terrain``: a depth punch, a near-invisible quad the mesh drops out
under over a pit drawn beneath it) is never a top.  A pit's floor is
deeper than ``pack_structure_depth_m`` and never reads as a top.

A FAKED CUT (owner 2026-11-17 14:50Z, KPHX; 14:51Z, KJFK): placements
EVERY solid face of which is drawn under the terrain, over a generated
deck, one of them reaching below its ground -- a pit, and the depth punch
(in the same object or its own) the mesh drops out under -- are replaced
by the real cut and the deck: :func:`faked_cuts` names every one of them
and the pack copy hides them (``airport/generated_pack``).

Nothing here names an airport, a pack or a resource; the faces are read
only for placements whose plan box reaches a deck piece.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t
import weakref

import numpy as np
import shapely
from shapely.geometry import Polygon

from ..airport import frame_entry as _fe
from ..airport import obj8 as _obj8
from ..airport.object_cut import _face_normals_y

__all__ = ["hidden_cells_off", "pack_decks_near", "pack_refusal", "faked_cuts", "overhead_decks"]

_NONE = np.zeros(0, dtype=bool)
_NONE_TRIS = np.zeros((0, 3), dtype=np.int64)


@_dc.dataclass(frozen=True)
class _PackDeck:
    """One pack placement that may stand on a generated deck: its id, its
    resource, ``kind`` ``"hard_deck"``, ``"cover"`` (its top faces),
    ``"structure"`` (its deep vertices' hull), ``"over"`` (its elevated
    tops, :func:`pack_decks_near`) or ``"under"`` (the plan
    hull of a placement drawn wholly under the terrain), its frame plan, its
    placement point (frame) and whether every solid face is drawn under
    the terrain (a faked cut when it is a structure)."""

    object_id: str
    resource: str
    kind: str
    plan: Polygon
    xy: tuple = (0.0, 0.0)
    under_terrain: bool = False


def _static_solid(g, *flags) -> np.ndarray:
    """``g``'s solid triangles less those any of ``flags`` marks."""
    keep = np.ones(g.solid.shape[0], dtype=bool)
    for flag in flags:
        if flag.shape[0] == keep.shape[0]:
            keep &= ~flag
    return g.solid[keep]


def _placed(o, geom, law):
    return _fe.enter([geom], _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]


#: the authored-frame readings per parsed geometry (#2206): ``{id(g):
#: {key: local | None, (key, xy, heading, quantum): placed}}``, dropped
#: with the geometry
_LOCAL: dict[int, dict] = {}


def _held(g) -> dict:
    """``g``'s entry of :data:`_LOCAL`, dropped with the geometry."""
    memo = _LOCAL.get(id(g))
    if memo is None:
        memo = _LOCAL[id(g)] = {}
        weakref.finalize(g, _LOCAL.pop, id(g), None)
    return memo


def _local(memo: dict, key: tuple, local: _t.Callable[[], _t.Any]):
    if key not in memo:
        memo[key] = local()
    return memo[key]


def held_plan(o, g, law, key: tuple, local: _t.Callable[[], _t.Any]):
    """``o``'s plan read off its parsed geometry ``g``: ``local()`` -- a
    reading of the resource alone, in its AUTHORED frame, named by ``key``
    -- placed at ``o`` (:func:`_placed`), or ``None`` when it reads
    nothing.  Both are held per geometry (#2206: every placement of a
    resource, every deck asking and every prefix run of the build read
    the union once, and each placement places it once); the answers are
    the ones computed, so a caller never mutates them."""
    memo = _held(g)
    got = _local(memo, key, local)
    if got is None:
        return None
    at = (key, tuple(o.xy), float(o.heading_deg), _fe.quantum(law))
    if at not in memo:
        memo[at] = _placed(o, got, law)
    return memo[at]


def _cover_plan(o, g, law, depth: float, floor: "float | None" = None, region=None):
    """The frame plan of ``o``'s up-facing faces within ``depth`` of its
    ground (solid -- neither animated nor drawn under the terrain -- and
    draped), or ``None``.  With ``floor``: only its SOLID up-facing faces
    standing at least ``floor`` over its ground (an elevated top: a deck,
    an overpass, a roof -- never a draped face).  With ``region``: ``None``
    also when no such face of ``o`` comes near it (:func:`_faces_near`), a
    plan that could not meet it, never read.

    The union is read in the AUTHORED frame, a reading of the resource
    alone, so it is held per geometry (:func:`held_plan`)."""
    ny_min = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    fl = None if floor is None else float(floor)
    tris = _local(_held(g), ("cover faces", float(depth), fl, ny_min),
                  lambda: _cover_faces(g, depth, floor, ny_min))
    if tris is None or (region is not None and not _faces_near(o, tris, region, law)):
        return None
    return held_plan(o, g, law, ("cover", float(depth), fl, ny_min),
                     lambda: _local_cover(tris))


def _cover_faces(g, depth: float, floor: "float | None", ny_min: float):
    """:func:`_cover_plan`'s faces in ``g``'s authored plan, ``(n, 3, 2)``
    ``(x, z)``, or ``None``."""
    v = g.vertices
    parts = [t for t in (_static_solid(g, g.animated, getattr(g, "under_terrain", _NONE)),
                         g.draped if floor is None else _NONE_TRIS) if t.shape[0]]
    if not parts:
        return None
    tris = np.concatenate(parts)
    low = -depth if floor is None else float(floor)
    up = (_face_normals_y(v, tris) >= ny_min) & (v[tris][:, :, 1].min(axis=1) >= low)
    return v[tris[up]][:, :, [0, 2]] if up.any() else None


def _local_cover(tris: np.ndarray):
    """The union of :func:`_cover_faces` in the authored frame, or ``None``."""
    polys = shapely.polygons(tris)
    polys = polys[shapely.is_valid(polys) & (shapely.area(polys) > 1e-6)].tolist()
    return _fe.union(polys, "deck_pack_cover.cover") if polys else None


def _faces_near(o, tris: np.ndarray, region, law) -> bool:
    """May ``o``'s placed union of ``tris`` meet ``region``?  ``False`` only
    when no face, placed, comes within a margin of it -- a margin past
    what the frame entry's snap to the quantum can move the union's
    boundary (#2206: KATL read 92 resources' tops, 1.3 M faces, for decks
    most of them stand nowhere near)."""
    a, b, d, e, xoff, yoff = _obj8.placement_affine(o.xy, o.heading_deg)
    xs = a * tris[:, :, 0] + b * tris[:, :, 1] + xoff
    ys = d * tris[:, :, 0] + e * tris[:, :, 1] + yoff
    m = 0.01 + 4.0 * _fe.quantum(law)
    lo_x, hi_x, lo_y, hi_y = xs.min(axis=1), xs.max(axis=1), ys.min(axis=1), ys.max(axis=1)
    box = shapely.bounds(shapely.get_parts(region))
    near = np.zeros(tris.shape[0], dtype=bool)
    for x0, y0, x1, y1 in box.tolist():
        near |= (lo_x <= x1 + m) & (hi_x >= x0 - m) & (lo_y <= y1 + m) & (hi_y >= y0 - m)
    if not near.any():
        return False
    placed = shapely.polygons(np.stack([xs[near], ys[near]], axis=-1))
    return bool(shapely.dwithin(placed, region, m).any())


def _structure_plan(o, g, law, depth: float):
    """The frame hull of ``o``'s solid vertices deeper than ``depth`` under
    its ground (animated ones aside), or ``None``."""
    solid = _static_solid(g, g.animated)
    if not solid.shape[0]:
        return None
    pts = g.vertices[np.unique(solid.reshape(-1))]
    deep = pts[pts[:, 1] < -depth]
    if deep.shape[0] < 3:
        return None
    hull = shapely.MultiPoint(deep[:, [0, 2]]).convex_hull
    return _placed(o, hull, law) if hull.geom_type == "Polygon" else None


def pack_decks_near(objects: _t.Sequence, cache, law, region,
                    over_m: "float | None" = None, deck_region=None) -> list[_PackDeck]:
    """Every pack hard deck (a), top and structure (b) whose plan reaches
    ``region`` (the union of the generated deck pieces, frame); with
    ``over_m``, also each placement's ELEVATED top (kind ``"over"``: its
    solid up-facing faces at least ``over_m`` over its ground, the
    pack's own bridge or roof over a generated road bridge,
    ``planar/road_bridge_pack``).  ``deck_region`` (wider than ``region``):
    where a HARD DECK is read, (c); no face is read there."""
    if not objects or region is None or region.is_empty:
        return []
    depth = float(law.tables.structures.deck_gen.pack_structure_depth_m)
    out: list[_PackDeck] = []
    for o in objects:
        hd = getattr(o, "hard_deck", None)
        if hd is not None and not hd.is_empty and hd.intersects(
                region if deck_region is None else deck_region):
            out.append(_PackDeck(str(o.id), str(o.path), "hard_deck", hd))
            continue
        bb = getattr(o, "plan_bbox", None)
        if cache is None or bb is None or o.resolved is None or not bb.intersects(region):
            continue
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        ut = getattr(g, "under_terrain", _NONE)
        under = bool(g.solid.shape[0]) and ut.shape[0] == g.solid.shape[0] and bool(ut.all())
        if under:
            hull = shapely.MultiPoint(g.vertices[np.unique(g.solid.reshape(-1))][:, [0, 2]])
            plan = _placed(o, hull.convex_hull, law)
            if plan is not None and not plan.is_empty and plan.intersects(region):
                out.append(_PackDeck(str(o.id), str(o.path), "under", plan, tuple(o.xy), True))
        reads = [("cover", lambda o_, g_, law_, d_: _cover_plan(o_, g_, law_, d_,
                                                                 region=region)),
                 ("structure", _structure_plan)]
        if over_m is not None:
            reads.append(("over", lambda o_, g_, law_, d_: _cover_plan(o_, g_, law_, d_,
                                                                       over_m, region)))
        for kind, read in reads:
            plan = read(o, g, law, depth)
            if plan is not None and not plan.is_empty and plan.intersects(region):
                out.append(_PackDeck(str(o.id), str(o.path), kind, plan,
                                    tuple(o.xy), under))
    return out


def faked_cuts(piece: Polygon, packs: _t.Sequence[_PackDeck], law) -> list[_PackDeck]:
    """The pack placements over ``piece`` that only fake its cut (module
    doc): each drawn wholly under the terrain, its plan over the piece by
    ``[deck_gen] min_area_m2`` -- when one of them is a structure (a pit);
    ``[]`` otherwise."""
    a_min = float(law.tables.structures.deck_gen.min_area_m2)

    def over(p) -> bool:
        try:
            return p.plan.intersection(piece).area >= a_min
        except shapely.errors.GEOSException:
            return False
    if not any(p.kind == "structure" and p.under_terrain and over(p) for p in packs):
        return []
    return [p for p in packs if p.kind == "under" and over(p)]


def pack_refusal(piece: Polygon, axes: _t.Sequence, packs: _t.Sequence[_PackDeck],
                 law, why_of: _t.Callable[[str], str] = lambda _i: "",
                 roads: _t.Sequence = (), reach: float = 0.0) -> str:
    """Why the pack's own crossing refuses ``piece`` (module doc), or
    ``""``.  ``axes``: the covered roads' lines; ``why_of(object id)``:
    the reason ``deck_bridges`` refused that hard deck as a bridge;
    ``roads`` / ``reach``: the covered roads' MAPPED lines and the cut's
    approach run, for (c)."""
    g = law.tables.structures.deck_gen
    beside = _beside(piece, packs, law, roads, reach)
    if beside:
        return beside
    inside = [a.intersection(piece) for a in axes]
    total = sum(x.length for x in inside)
    top = structure = None
    for p in packs:
        try:
            if p.kind == "hard_deck":
                if p.plan.intersection(piece).area > 1.0:
                    why = why_of(p.object_id)
                    return (f"the pack's hard deck {p.object_id} ({p.resource}) stands on it"
                            + (f" (refused as a bridge: {why})" if why else ""))
            elif p.kind == "structure":
                if structure is None and \
                        p.plan.intersection(piece).area >= float(g.min_area_m2):
                    structure = p
            elif p.kind == "cover" and top is None and total > 0.0:
                cov = sum(x.intersection(p.plan).length for x in inside)
                if cov >= float(g.pack_cover_share) * total:
                    top = (p, cov / total)
        except shapely.errors.GEOSException:        # an invalid pack outline
            continue
    if structure is None or top is None:
        return ""
    return (f"the pack models the crossing: {structure.object_id} ({structure.resource}) "
            f"reaches under its ground and {top[0].object_id} ({top[0].resource}) draws a "
            f"top over {100 * top[1]:.0f} % of the covered road")


#: a pad or wall cell this share inside a hidden placement's plan was read off it
HIDDEN_CELL_SHARE = 0.5


def hidden_cells_off(classification, decks) -> tuple[_t.Any, list[str]]:
    """``classification`` less the building pads and retaining walls the
    classification read off a placement a GENERATED deck hides (its
    ``hidden_plans``: the pack's faked cut, drawn under the terrain and
    hidden in the pack copy) -- a cell at least :data:`HIDDEN_CELL_SHARE`
    inside one.  The placement is not drawn, so what was read off it is no
    ground: left in, its pad stood at the faked floor's rim and stopped the
    real cut (MEASURED KJFK ``o4gen_0abbd35b`` / ``o4gen_db1cfe30`` over the
    motorways under ``deprimido_jetblue.obj``: the ground under the decks
    6.2 m over their floors).  The same for a cell read off the parts a
    pack bridge piece hidden only piece-wise keeps drawn elsewhere
    (``kept_plans``): bridge solid, no building ground (#2203 follow-up,
    MEASURED KDFW: 220.obj's north plate as a pad over the road it spans).
    No such plan, no change."""
    import dataclasses as _dc

    from shapely.ops import unary_union
    plans = [Polygon(r) for d in decks
             for r in (*(getattr(d, "hidden_plans", ()) or ()),
                       *(getattr(d, "kept_plans", ()) or ()))
             if len(r) >= 3]
    if not plans or classification is None:
        return classification, []
    hid = unary_union([p if p.is_valid else p.buffer(0.0) for p in plans])
    keep, gone = [], []
    for c in classification.cells:
        if c.role in ("building", "retaining_wall") and len(c.ring) >= 3:
            p = Polygon(c.ring, c.holes)
            p = p if p.is_valid else p.buffer(0.0)
            if p.area > 0.0 and p.intersection(hid).area >= HIDDEN_CELL_SHARE * p.area:
                gone.append(f"{c.role} {c.ref}")
                continue
        keep.append(c)
    if not gone:
        return classification, []
    return (_dc.replace(classification, cells=tuple(keep)),
            [f"generated decks: {len(gone)} cell(s) read off hidden pack placements dropped "
             f"({', '.join(gone[:6])})"])


def _beside(piece: Polygon, packs: _t.Sequence[_PackDeck], law,
            roads: _t.Sequence, reach: float) -> str:
    """(c): the pack hard deck that abuts ``piece`` (module doc), named,
    or ``""``.  One that overlaps it is (a)'s."""
    g = law.tables.structures.deck_gen
    touch = float(g.bearing_m) + float(g.edge_margin_m)
    near = piece.buffer(reach) if reach > 0.0 else None
    on = [r.intersection(near) for r in roads] if near is not None else []
    for p in packs:
        if p.kind != "hard_deck":
            continue
        try:
            if p.plan.intersection(piece).area > 1.0:
                continue
            gap = p.plan.distance(piece)
            run = sum(x.intersection(p.plan).length for x in on)
        except shapely.errors.GEOSException:     # an invalid pack outline
            continue
        if gap <= touch:
            return (f"the pack's hard deck {p.object_id} ({p.resource}) abuts it "
                    f"({gap:.1f} m, within the ring's growth {touch:g} m; RULINGS 2026-11-17n)")
        if run > 1.0:
            return (f"the covered road runs {run:.0f} m on under the pack's hard deck "
                    f"{p.object_id} ({p.resource}) {gap:.1f} m beside it, within the cut's "
                    f"approach run {reach:g} m: the pack models the crossing "
                    f"(RULINGS 2026-11-17n)")
    return ""


def overhead_decks(objects: _t.Sequence, cache, region, level: "float | None", law
                   ) -> frozenset[str]:
    """The pack hard decks over ``region`` that pass OVER the crossing: no
    up-facing solid face of theirs over ``region`` stands lower than
    ``[bridge] clearance_minimum_m`` over ``level`` (the carried pavement's)
    -- a people-mover viaduct over the taxiway, never the crossing's own
    deck, so they refuse no generated deck (#2181 item 2; MEASURED KPHX
    33.434942, -111.992308: ``SkyTrain.obj``'s guideway over taxiway bridge
    ``-96`` refused the deck over the road under it).  Read face by face
    over the region, never by the object's highest top: KRDU's
    ``STH_TML.obj`` tops out 10 m over the taxiway it carries at grade."""
    if level is None or region is None or region.is_empty or cache is None:
        return frozenset()
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    ny_min = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    out = set()
    for o in objects or ():
        hd, top = getattr(o, "hard_deck", None), getattr(o, "deck_top_z", None)
        if hd is None or top is None or hd.is_empty or o.resolved is None:
            continue
        try:
            if not hd.intersects(region) or float(top) < float(level) + clear:
                continue
        except shapely.errors.GEOSException:
            continue
        g = cache.geometry(o.resolved)
        if g is None:
            continue
        base = float(getattr(o, "anchor_z", 0.0) or 0.0) + float(getattr(o, "agl_m", 0.0) or 0.0)
        tris = _static_solid(g, g.animated, getattr(g, "under_terrain", _NONE))
        if not tris.shape[0]:
            continue
        v = g.vertices
        low = (_face_normals_y(v, tris) >= ny_min) & \
            (v[tris][:, :, 1].max(axis=1) < float(level) + clear - base)
        polys = [q for q in shapely.polygons(v[tris[low]][:, :, [0, 2]])
                 if q.is_valid and q.area > 1e-6] if low.any() else []
        plan = _placed(o, _fe.union(polys, "deck_pack_cover.overhead"), law) if polys else None
        if plan is None or plan.is_empty or plan.intersection(region).area <= 1.0:
            out.add(str(o.id))
    return frozenset(out)
