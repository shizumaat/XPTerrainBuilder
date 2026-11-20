"""THE PACK'S WALLED MULTI-BRIDGE FRAME, HIDDEN: OUR OWN DECKS TAKE ITS
CROSSINGS (owner 2026-11-19T13:51Z, the Beta 8 fallback: "can we detect
complex, multi-bridge objects like the ones at KORD and KRDU and simply hide
them and install our own bridges that we can cut and align correctly with the
terrain?"; RULINGS 2026-11-19m (2): "If the author's object is removed
(hidden by the user), our generated bridge objects (``planar/deck_generated``,
spec 2123) take over and the lidar sets the depth").

THE RULE (general: no airport, pack, resource or coordinate is named):

1. A WALLED MULTI-BRIDGE FRAME (``docs/specs/walled-multibridge-frames-spec.md``
   §1) is a pack frame -- one placement, or a co-placed set
   (``deck_bridge._frames``) -- holding TWO OR MORE hard-deck bridges
   (``deck_bridge.deck_bridges``: the airport's pavement runs across each,
   RULINGS 2026-10-27c) whose road the frame's own walls line
   (``deck_bridge.is_walled``) or a trench object of the frame states
   (``airport/trench_objects``, RULINGS 2026-11-19a), carrying a taxiway or
   runway, and EITHER two of them standing APART along that trench (their
   spans along the road disjoint, the stretch between walled: the frame's
   walls run on along it, ``deck_bridge._walled_trench`` toward the other,
   or its trench object stands there) OR one of them spanning two or more
   separate mapped roads (the lines under it merged end to end).  One
   bridge over one road, or pieces side by side each over its own
   carriageway, is no such frame; nor is a frame an object floor reads
   (``airport/object_floor``: it stays the floor's, walled-multibridge-
   frames W1; RULINGS 2026-11-19m (3)).
2. It is TAKEN OVER only when, with the frame's placements gone and its deck
   plates paved (:func:`_paved_over`), a GENERATED deck stands on every one
   of its taxiway / runway bridges (overlapping it by ``[deck_gen]
   min_area_m2``; a road bridge of the frame is the road-bridge rule's);
   otherwise it stays the pack's and the note names the bridge no generated
   deck takes.
3. A taken-over frame is HIDDEN: every placement of it leaves the planar
   build's object list (:func:`_without`; no corridor, trench, floor, basin
   or wall reads it, on either map: the build runs as if the user had hidden
   it), and the generated decks standing on its bridges carry it
   (:func:`_attach`): ``hides`` (the pack copy drops its rows,
   ``airport/generated_pack``; the original stays the backup and Restore
   originals puts it back), ``hidden_plans`` (what the classification read
   off it is no ground, ``deck_pack_cover.hidden_cells_off``) and
   ``replaces`` (stage 1's map reads the same hidden set off the full map's
   decks, :func:`_replaced_ids`).

Build-time impact: one ``deck_bridges`` read over the frames holding two or
more deck pieces (few per airport) and, only where a frame qualifies, one
``generated_decks`` probe (seconds); an airport with no such frame returns at
the piece count.  Where a frame is hidden the planar build reads the pack
twice (``planar/build``: the first read finds the object floors the frames
must not be): ~20-40 s more at such an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import itertools
import typing as _t

import numpy as np
import shapely
from shapely.ops import linemerge, unary_union

from ..classify.roles import TAXI_FAMILY
from ..model.structures import DeckBridge, is_generated
from .deck_bridge import (
    _frames,
    _road_dir,
    _walled_trench,
    deck_bridges,
    deck_polygon,
    mid_line,
    project_span,
)
from .deck_generated import generated_decks
from .deck_pack_cover import _placed, _static_solid

__all__ = ["take_frames", "full_hidden",
           "roads_under", "one_decision"]


@_dc.dataclass(frozen=True)
class _Takeover:
    """One hidden walled multi-bridge frame (module doc)."""

    #: the frame's deck placement and its resource
    object_id: str
    resource: str
    #: every placement of the frame, ``(id, resource, (lon, lat))`` -- the
    #: rows the pack copy hides (``DeckBridge.hides``)
    members: tuple
    #: the members' plans (frame rings, ``DeckBridge.hidden_plans``)
    plans: tuple
    #: the frame's bridges (``DeckBridge``): a generated deck stands on each
    bridges: tuple


def _apart(a: DeckBridge, b: DeckBridge, gap: float, trench=None) -> bool:
    """``a`` and ``b`` stand APART along one walled trench: their spans along
    ``a``'s road do not overlap while their reaches across it do, and the
    stretch between them is walled -- ``a``'s walls run on along it
    (``deck_bridge._walled_trench`` toward ``b`` is wider than ``a``'s own)
    or the frame's trench object (``trench``, its plan) stands there."""
    r = _road_dir(a)
    n = (r[1], -r[0])
    (a0, a1), (b0, b1) = project_span(a.ring, r), project_span(b.ring, r)
    (c0, c1), (d0, d1) = project_span(a.ring, n), project_span(b.ring, n)
    if min(a1, b1) > max(a0, b0) or min(c1, d1) <= max(c0, d0):
        return False
    if trench is not None:
        pa, pb = deck_polygon(a).centroid, deck_polygon(b).centroid
        if trench.contains(shapely.Point(0.5 * (pa.x + pb.x), 0.5 * (pa.y + pb.y))):
            return True
    own, both = _walled_trench(a, gap), _walled_trench(a, gap, b)
    return own is not None and both is not None and both[0].area > own[0].area + 1.0


def _crossings(db: DeckBridge, roads) -> int:
    """How many separate mapped roads run under bridge ``db``: the mapped
    road / rail lines inside its ring merged end to end (a way split under
    the deck is one road), each over a metre (``deck_generated``'s reading
    of a road under a piece)."""
    p = deck_polygon(db)
    parts = [x for ln in roads if (x := ln.intersection(p)).length > 1.0]
    if not parts:
        return 0
    m = linemerge(unary_union(parts))
    return sum(1 for g in getattr(m, "geoms", [m]) if g.length > 1.0)


def _multibridge_frames(decks: _t.Sequence[DeckBridge], gap: float, trenches=(),
                       roads=()) -> list[tuple[DeckBridge, ...]]:
    """Every pack frame of ``decks`` that is a walled multi-bridge frame
    (module doc, rule 1), its bridges in ``decks`` order.  ``gap`` is
    ``[tunnel] wall_gap_m``; ``trenches`` the pack's trench objects
    (``airport/trench_objects``: a frame holding one states its walls,
    RULINGS 2026-11-19a); ``roads`` the mapped road / rail lines (frame)."""
    by: dict[str, list[DeckBridge]] = {}
    for db in decks:
        if not is_generated(db):
            by.setdefault(db.object_id, []).append(db)
    out = []
    for pieces in by.values():
        ids = set(pieces[0].members)
        tr = [t.outline for t in trenches or () if str(t.object_id) in ids
              and getattr(t, "outline", None) is not None]
        trench = unary_union(tr).buffer(0.0) if tr else None
        walled = [p for p in pieces if trench is not None
                  or (p.walls and _walled_trench(p, gap) is not None)]
        if not any(p.family != "road" for p in walled):
            continue
        if any(_apart(a, b, gap, trench) or _apart(b, a, gap, trench)
               for a, b in itertools.combinations(walled, 2)) \
                or any(_crossings(p, roads) >= 2 for p in walled):
            out.append(tuple(pieces))
    return out


def _road_lines(airport) -> list:
    """Every mapped road / rail way that is no bridge, as a frame line."""
    from shapely.geometry import LineString

    from .structure_underpass import is_bridge
    return [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
            if len(w.points) >= 2 and not is_bridge(w)
            and any((w.tags or {}).get(k) for k in ("highway", "railway"))]


def _pieces(decks) -> int:
    u = unary_union([q.hard_deck for q in decks])
    return sum(1 for p in getattr(u, "geoms", [u]) if p.geom_type == "Polygon" and p.area >= 1.0)


def _plan(o, cache, law) -> "tuple | None":
    """``o``'s plan (frame ring): the hull of its drawn solid -- neither
    animated nor drawn under the terrain -- or ``None``."""
    g = cache.geometry(o.resolved) if cache is not None and o.resolved else None
    if g is None or g.solid is None or not len(g.solid):
        return None
    tris = _static_solid(g, g.animated, getattr(g, "under_terrain", np.zeros(0, dtype=bool)))
    if not tris.shape[0]:
        return None
    hull = shapely.MultiPoint(g.vertices[np.unique(tris.reshape(-1))][:, [0, 2]]).convex_hull
    plan = _placed(o, hull, law) if hull.geom_type == "Polygon" else None
    return None if plan is None or plan.is_empty or plan.geom_type != "Polygon" \
        else tuple(plan.exterior.coords[:-1])


def _trenches(objects, cache, airport, law) -> list:
    """The trench objects among ``objects`` (``airport/trench_objects``, the
    pack read's own call): a co-placed trench's walls are its frame's."""
    from ..airport.deck_signature import is_tunnel_way
    from ..airport.trench_objects import covered_candidates, read_trench_objects
    ways = [w for w in getattr(airport, "osm_ways", ()) or ()
            if is_tunnel_way(w.tags, law.tables.structures.tunnel.admitted_values)
            and len(w.points) >= 2]
    return read_trench_objects(objects, cache, law,
                               ways + covered_candidates(airport.osm_ways))[0]


def roads_under(bridges: _t.Sequence[DeckBridge], airport, law) -> list:
    """The mapped roads under the pack ``bridges`` as covered roads of
    ``generated_decks``: each road / rail way passing under a bridge --
    crossing its midline inside its ring (``deck_bridge.mid_line``, the
    reading ``planar/deck_bores`` bores a hard deck's road by) -- clipped
    to the ring (once per bridge), its mapped way its parent (the cover is
    read off the pavement over it, ``deck_generated._whole_cover``).  A way
    ending under the deck short of the midline (a 10 m link between two
    bores) is not under it."""
    from shapely.geometry import LineString

    from .deck_generated import _Road
    from .structure_approach import carriageway_width_m
    from .structure_underpass import bore_roads
    out = []
    lines = [(w, LineString(w.points)) for w in bore_roads(airport, law, rail=True)]
    for db in bridges:
        p, (r, mid) = deck_polygon(db), mid_line(db)
        for w, ln in lines:
            x = ln.intersection(p)
            parts = [g for g in getattr(x, "geoms", [x])
                     if g.geom_type == "LineString" and g.length > 1.0
                     and min(q[0] * r[0] + q[1] * r[1] for q in g.coords) < mid
                     < max(q[0] * r[0] + q[1] * r[1] for q in g.coords)]
            if parts:
                best = max(parts, key=lambda g: g.length)
                out.append(_Road(str(w.id), dict(w.tags or {}), best, best.length,
                                 carriageway_width_m(w.tags, law) / 2.0, ln))
    return out


def _taken(span: DeckBridge, polys, a_min: float) -> bool:
    p = deck_polygon(span)
    return any(p.intersection(g).area >= a_min for g in polys)


def _takeovers(objects, cache, classification, airport, law, ground=None, trenches=None,
              everything=None) -> tuple[tuple[_Takeover, ...], list[str]]:
    """``(every walled multi-bridge frame of ``objects`` taken over, one note
    per frame read and per placement hidden)`` (module doc, rules 1-2).
    ``ground``: the author's ground ``deck_bridges`` reads (``None``: the
    pack's, ``airport/below_grade_witness.ground_of``); ``trenches``: the
    pack's trench objects (``None``: read here); ``everything``: the whole
    pack, when ``objects`` leaves some out (the generated probe reads it)."""
    everything = objects if everything is None else everything
    if not objects or cache is None or classification is None:
        return (), []
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    cand = [fr for decks, fr in _frames(objects, tol) if _pieces(decks) >= 2]
    if not cand:
        return (), []
    if ground is None and getattr(airport, "dem", None) is not None:
        from ..airport.below_grade_witness import ground_of
        ground = ground_of(airport, everything, cache, law)
    mine = [q for fr in cand for q in fr]
    trenches = _trenches(mine, cache, airport, law) if trenches is None else trenches
    decks, _n = deck_bridges(mine, cache, classification, airport, law, trenches,
                             ground=ground)
    frames = _multibridge_frames(decks, float(law.tables.structures.tunnel.wall_gap_m),
                                trenches, _road_lines(airport))
    if not frames:
        return (), []
    gone = {m for fr in frames for m in fr[0].members}
    paved, _pn = _paved_over(classification, [o for o in objects if str(o.id) in gone], law)
    gen, _gn = generated_decks(paved, airport, law, (), (),
                               [o for o in everything if str(o.id) not in gone], cache,
                               covered=roads_under([p for fr in frames for p in fr],
                                                   airport, law))
    polys = [deck_polygon(g) for g in gen]
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    to_ll = airport.frame.transformers()[1]
    by_id = {str(o.id): o for o in everything}
    pack = getattr(getattr(airport, "pack", None), "name", "") or "the pack"
    out: list[_Takeover] = []
    notes: list[str] = []
    for fr in frames:
        db = fr[0]
        where = (f"{db.object_id} {db.resource.rsplit('/', 1)[-1]}: a walled multi-bridge "
                 f"frame, {len(fr)} bridge(s) "
                 + ", ".join(f"{deck_polygon(p).area:,.0f} m2" for p in fr))
        # a ROAD bridge of the frame is the road-bridge rule's (spec 2123 B):
        # our decks carry the taxiways and runways
        left = [p for p in fr if p.family != "road" and not _taken(p, polys, a_min)]
        if left:
            # the probe's own refusals name why (a frame kept is a read to check)
            why = [n for n in _gn if "REFUSED" in n]
            notes.append(f"{where}: KEPT -- no generated deck takes its bridge(s) "
                         + ", ".join(f"{deck_polygon(p).area:,.0f} m2" for p in left)
                         + " (owner 2026-11-19T13:51Z)"
                         + "".join(f"; probe: {n}" for n in why[:4]))
            continue
        placed = [by_id[m] for m in db.members if m in by_id]
        out.append(_Takeover(db.object_id, db.resource,
                            tuple((str(q.id), str(q.path), tuple(reversed(to_ll(*q.xy))))
                                  for q in placed),
                            tuple(r for q in placed if (r := _plan(q, cache, law))),
                            tuple(fr)))
        notes.append(f"{where}: HIDDEN -- our generated decks take every bridge, the lidar "
                     f"sets the trench (owner 2026-11-19T13:51Z, RULINGS 2026-11-19m (2))")
        notes.extend(f"multi-bridge frame hidden: pack {pack}: {q.id} {q.path}" for q in placed)
    return tuple(out), notes


def full_hidden(objects, classification, cache, law) -> tuple[list, _t.Any, list[str]]:
    """``(objects, classification, notes)`` on stage 1's map: the pack less
    the frames the full map hid (:func:`_replaced_ids`, never a second
    reading), their deck plates paved; unchanged anywhere else."""
    from ..model.stage_one import full_map
    from .deck_airside import withheld
    full = full_map()
    # the no-bridge arm's full map withholds the decks that carry them
    # (``planar/deck_airside.no_bridge_arm``)
    hid = _replaced_ids((*(getattr(full, "decks", ()) or ()), *withheld())) \
        if full is not None else frozenset()
    if not hid:
        return objects, classification, []
    classification, notes = _paved_over(classification,
                                       [o for o in objects if str(o.id) in hid], law)
    return _without(objects, hid, cache), classification, notes


def take_frames(objects, cache, classification, airport, law,
                skip: _t.AbstractSet[str] = frozenset(), trenches=None
                ) -> tuple[list, _t.Any, tuple[_Takeover, ...], list[str]]:
    """``(objects less every hidden frame's placements, the classification
    with the pavement they drew (:func:`_paved_over`), the takeovers, their
    notes)`` on the full map (module doc).  ``skip``: placements an object
    floor reads (that frame stays the floor's, walled-multibridge-frames
    W1); ``trenches``: the pack read's trench objects (``None``: read
    here)."""
    takes, notes = _takeovers([o for o in objects if str(o.id) not in skip], cache,
                             classification, airport, law, trenches=trenches,
                             everything=objects)
    hid = {m[0] for t in takes for m in t.members}
    if not hid:
        return objects, classification, takes, notes
    classification, more = _paved_over(classification, [o for o in objects if str(o.id) in hid],
                                      law)
    return _without(objects, hid, cache), classification, takes, notes + more


#: the roles a hidden deck's plate continues (the pavement drawn beside it),
#: a taxiway or runway first (the route a deck carries, spec 2123 A1)
_CARRIED = frozenset(TAXI_FAMILY) | {"runway", "runway_crossing"}
_PAVED = _CARRIED | {"apron", "groundside_pavement"}


def _paved_over(classification, hidden: _t.Sequence, law) -> tuple[_t.Any, list[str]]:
    """``classification`` with the DECK PLATES of the ``hidden`` placements
    paved where no cell owns them: the author drew the airport's pavement
    across the crossing as the deck itself (the apt.dat leaves it out:
    MEASURED KRDU CTR_TML, 713 of the 3,077 m2 deck piece paved in the
    apt.dat, ~370 m2 classified), so with the deck hidden that pavement
    runs on across it -- the surface ``generated_decks`` reads the crossing
    off (spec 2123 A2 ``P``) and the cut leaves under its decks
    (``carried_off``).  Each plate part takes the role, ref and code of the
    paved cell with the most area within ``[bridge] abutment_sample_step_m``
    of it, a taxiway or runway cell before any other; a plate with no paved
    cell beside it is left alone."""
    from shapely.strtree import STRtree
    if classification is None or not classification.cells:
        return classification, []
    pieces = [p for q in hidden if (hd := getattr(q, "hard_deck", None)) is not None
              and not hd.is_empty for p in getattr(hd, "geoms", [hd])
              if p.geom_type == "Polygon" and p.area >= 1.0]
    if not pieces:
        return classification, []
    cells = [c for c in classification.cells if len(c.ring) >= 3]
    polys = [shapely.Polygon(c.ring, c.holes).buffer(0.0) for c in cells]
    tree = STRtree(polys)
    reach = float(law.tables.structures.bridge.abutment_sample_step_m)
    new: list = []
    for piece in pieces:
        near = [int(i) for i in tree.query(piece.buffer(reach), predicate="intersects")]
        donors = [(cells[i].role in _CARRIED, polys[i].intersection(piece.buffer(reach)).area,
                   i) for i in near if cells[i].role in _PAVED]
        if not donors:
            continue
        donor = cells[max(donors)[2]]
        free = piece.difference(unary_union([polys[i] for i in near])) if near else piece
        for part in getattr(free, "geoms", [free]):
            if part.geom_type != "Polygon" or part.area < 1.0:
                continue
            new.append(_dc.replace(donor, id=0, ring=tuple(part.exterior.coords)[:-1],
                                   holes=tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                   evidence={"deck_takeover": 1.0, "area_m2": part.area}))
    if not new:
        return classification, []
    return (_dc.replace(classification, cells=tuple(classification.cells) + tuple(new)),
            [f"hidden deck plates paved: {len(new)} cell(s), "
             f"{sum(shapely.Polygon(c.ring).area for c in new):,.0f} m2 "
             f"({', '.join(sorted({c.role for c in new}))})"])


def _without(objects, hidden: _t.AbstractSet[str], cache=None) -> list:
    """``objects`` less the placements ``hidden`` names -- ONE list per
    ``cache`` and hidden set, so every planar pass of a build hands the pack
    reads (``planar/pack_reads``, memoised on the list's identity) the same
    list."""
    if not hidden:
        return objects
    key = ("deck_takeover", id(objects), frozenset(hidden))
    store = getattr(cache, "placed", None)
    if isinstance(store, dict) and key in store and store[key][0] is objects:
        return store[key][1]
    out = [o for o in objects if str(o.id) not in hidden]
    if isinstance(store, dict):
        store[key] = (objects, out)
    return out


def _attach(gen: _t.Sequence[DeckBridge], takes: _t.Sequence[_Takeover], law
           ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``gen`` (the build's generated decks) with every hidden frame of
    ``takes`` carried by the first deck standing on one of its bridges
    (module doc, rule 3), and one note per frame no deck stands on at the
    build (its placements stay hidden: they left the object list)."""
    out = list(gen)
    notes: list[str] = []
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    polys = [deck_polygon(g) for g in out]
    for t in takes:
        spans = [deck_polygon(b) for b in t.bridges]
        hit = [k for k, g in enumerate(polys)
               if any(g.intersection(s).area >= a_min for s in spans)]
        if not hit:
            notes.append(f"{t.object_id} {t.resource.rsplit('/', 1)[-1]}: hidden, but no "
                         f"generated deck stands on its bridges at the build")
            continue
        k = hit[0]
        g = out[k]
        out[k] = _dc.replace(g, hides=tuple(g.hides) + t.members,
                             hidden_plans=tuple(g.hidden_plans) + t.plans,
                             replaces=tuple(getattr(g, "replaces", ()) or ())
                             + tuple(m[0] for m in t.members))
        notes.append(f"{t.object_id} {t.resource.rsplit('/', 1)[-1]}: hidden with "
                     f"{out[k].object_id}; generated decks on its bridges: "
                     + ", ".join(out[i].object_id for i in hit))
    return tuple(out), notes


def _replaced_ids(decks: _t.Sequence[DeckBridge]) -> frozenset:
    """The placement ids every deck of ``decks`` takes over (stage 1's map
    reads them off the full map's decks)."""
    return frozenset(m for d in decks for m in getattr(d, "replaces", ()) or ())


# ── ONE DECISION PER CROSSING (owner RULINGS 2026-11-20a (1), #2191) ──────
#
# "Should be the same rule that determines whether we build our own bridge
# or not, that also hides the pack's bridges if we do" (owner 14:01Z).  The
# pack's bridge is KEPT where it seats lawfully: a pack hard deck
# (``deck_bridges``: its one zero flush at its end lines, the deck/flush law)
# standing on the crossing refuses the generated deck (``deck_generated.
# _blocked`` / ``deck_pack_cover.pack_refusal``), so no deck is generated
# there.  Where we generate, EVERY pack bridge body over the crossing --
# a walled multi-bridge frame (rule 3 above, 19p) or any other placement
# drawing a deck-level top over the road the deck spans (a single span the
# deck law cannot seat: no hard deck, no end lines) -- is hidden in the pack
# copy with its frame mates (co-placed lights, riders), and Restore
# originals puts it back.  Never both: a pack bridge body left under a
# generated deck footprint is a DEFECT the build counts
# (``DeckBridge.pack_under``, census family ``pack_bridge_under_deck``).
# MEASURED KMCO 1.0.567 (owner pack copy 13:39Z): ``puente.obj`` /
# ``puente2.obj`` (``deck_kind`` candidate, no hard deck, tops 6.2 m over
# their anchors) under our decks, hides [] -- seated too low, flashing.


def _body_top(o, cache, law, lo: float, hi: float):
    """``o``'s up-facing solid faces (neither animated nor drawn under the
    terrain) standing between the absolute levels ``lo`` and ``hi`` -- a
    deck at the carried pavement's level -- as one frame plan, or ``None``."""
    from ..airport import frame_entry as _fe
    from ..airport.object_cut import _face_normals_y
    g = cache.geometry(o.resolved) if cache is not None and o.resolved else None
    if g is None or g.solid is None or not len(g.solid):
        return None
    tris = _static_solid(g, g.animated, getattr(g, "under_terrain", np.zeros(0, dtype=bool)))
    if not tris.shape[0]:
        return None
    base = float(getattr(o, "anchor_z", 0.0) or 0.0) + float(getattr(o, "agl_m", 0.0) or 0.0)
    v = g.vertices
    ny = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    ys = v[tris][:, :, 1] + base
    up = (_face_normals_y(v, tris) >= ny) & (ys.min(axis=1) >= lo) & (ys.max(axis=1) <= hi)
    if not up.any():
        return None
    polys = [p for p in shapely.polygons(v[tris[up]][:, :, [0, 2]])
             if p.is_valid and p.area > 1e-6]
    return _placed(o, _fe.union(polys, "deck_takeover.body"), law) if polys else None


def _bodies(g: DeckBridge, objects, cache, airport, law, skip: _t.AbstractSet[str],
            share: "float | None") -> list[tuple[_t.Any, float]]:
    """``[(placement, its deck-level top's area over the deck)]``: every
    pack placement of ``objects`` (``skip`` aside) drawing a top at the
    carried pavement's level (within ``[bridge] clearance_minimum_m`` of it:
    never a structure passing over, never a pit) over ``g``'s footprint by
    ``[deck_gen] min_area_m2`` -- and, with ``share``, over at least that
    share of its covered roads' axis inside it (a bridge over the road)."""
    from shapely.geometry import LineString

    from .deck_bridge import deck_polygon
    from .deck_generated import _carried_level
    ring = deck_polygon(g)
    level = _carried_level(airport, ring)
    if level is None:
        return []
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    axes = [LineString(c).intersection(ring) for _w, _t, c in g.covered or () if len(c) >= 2]
    total = sum(x.length for x in axes)
    out = []
    for o in objects or ():
        bb = getattr(o, "plan_bbox", None)
        if str(o.id) in skip or bb is None or not bb.intersects(ring):
            continue
        top = _body_top(o, cache, law, level - clear, level + clear)
        if top is None:
            continue
        try:
            area = top.intersection(ring).area
            if area < a_min:
                continue
            if share is not None and (total <= 0.0 or sum(
                    x.intersection(top).length for x in axes) < share * total):
                continue
        except shapely.errors.GEOSException:         # an invalid pack outline
            continue
        out.append((o, area))
    return out


def one_decision(gen: _t.Sequence[DeckBridge], takes: _t.Sequence[_Takeover], objects,
                 cache, airport, law) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(gen, notes)``: THE ONE DECISION per crossing our decks were
    generated at (the block comment above): the walled frames this build
    hid (:func:`_attach`), then every other pack bridge body over a
    generated deck's crossing hidden with its frame mates (``hides``,
    ``hidden_plans``), and what is still left under a deck's footprint
    recorded as its defect (``pack_under``)."""
    from .deck_bridge import co_placed
    out, notes = _attach(gen, takes, law)
    out = list(out)
    if not objects or cache is None or getattr(airport, "dem", None) is None:
        return tuple(out), notes
    share = float(law.tables.structures.deck_gen.pack_cover_share)
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    to_ll = airport.frame.transformers()[1]
    hidden = {h[0] for d in out for h in getattr(d, "hides", ()) or ()}
    for k, g in enumerate(out):
        if g.family == "road":
            continue
        for o, area in _bodies(g, objects, cache, airport, law, hidden, share):
            mates = [q for q in objects if q is o or (str(q.id) not in hidden
                                                      and co_placed(o, q, tol))]
            hidden.update(str(q.id) for q in mates)
            g = _dc.replace(g, hides=tuple(g.hides) + tuple(
                (str(q.id), str(q.path), tuple(reversed(to_ll(*q.xy)))) for q in mates),
                hidden_plans=tuple(g.hidden_plans) + tuple(
                    r for q in mates if (r := _plan(q, cache, law))))
            notes.append(f"{g.object_id}: the pack's bridge {o.id} {o.path} ({area:,.0f} m2 "
                         f"over it) cannot be seated by the deck law (no hard deck): our "
                         f"deck takes the crossing, it is HIDDEN in the pack copy with "
                         + ", ".join(f"{q.id} {q.path}" for q in mates if q is not o)
                         + (" (none)" if len(mates) == 1 else "")
                         + " (RULINGS 2026-11-20a (1))")
        out[k] = g
    for k, g in enumerate(out):
        left = _bodies(g, objects, cache, airport, law, hidden, None)
        if left:
            out[k] = _dc.replace(g, pack_under=tuple(
                (str(o.id), str(o.path), tuple(reversed(to_ll(*o.xy))), round(a, 1))
                for o, a in left))
            notes.append(f"{g.object_id}: DEFECT -- pack placement(s) under its footprint: "
                         + ", ".join(f"{o.id} {o.path} {a:,.0f} m2" for o, a in left)
                         + " (RULINGS 2026-11-20a (1))")
    return tuple(out), notes
