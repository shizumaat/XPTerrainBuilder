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
           "roads_under", "one_decision", "span_bands"]


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
    #: the frame's deck placements' ids (the bodies :func:`_capped` keeps)
    bodies: tuple = ()


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


def _combined(pieces: _t.Sequence[DeckBridge]) -> bool:
    """A frame COMBINING SEVERAL BRIDGES IN ONE OBJECT that cannot follow
    the real terrain (owner 2026-11-20T23:53Z, KRDU: "When a pack combines
    multiple bridges into a single object that can't follow the real
    terrain slopes, like KRDU, both the North bridges and the taxiway E
    bridges plus taxiway, we drop that whole object"): its deck was cut to
    two or more spans (RULINGS 2026-11-18i ``span_cut``: one rigid plate
    over two crossings, at grade between them), a taxiway or runway on
    it."""
    spans = {sp for p in pieces if getattr(p, "span_cut", ()) for sp in p.span_cut[2]}
    return len(spans) >= 2 and any(p.family != "road" for p in pieces)


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
        if _combined(pieces):
            # owner 2026-11-20T23:53Z: a pack object combining several
            # bridges that cannot follow the real terrain is dropped whole
            out.append(tuple(pieces))
            continue
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


def _frame_members(fr, placed, gen_polys, cache, law) -> list:
    """The placements of frame ``fr`` (``placed``: every co-placed one) its
    takeover hides: its deck placements (the bridges' bodies), the
    placements riding its decks (:func:`_rides`: within the hull of its
    bridges and the generated decks on them, ``[tunnel] wall_gap_m`` and
    ``[bridge] abutment_sample_step_m`` out -- its walls, beds, riders),
    and its lights where no other solid shares the anchor.  Never a
    building, never an object on a shared anchor elsewhere (owner
    2026-11-20T22:39Z, the KDFW shared-anchor read)."""
    decks = {p.object_id for p in fr}
    spans = [deck_polygon(p) for p in fr]
    gens = [g for g in gen_polys if any(g.intersects(s) for s in spans)]
    reach = float(law.tables.structures.tunnel.wall_gap_m) \
        + float(law.tables.structures.bridge.abutment_sample_step_m)
    foot = unary_union(spans + gens).convex_hull.buffer(reach)
    hi = max((float(p.floor_min_m) for p in fr), default=0.0) \
        + float(law.tables.structures.bridge.clearance_minimum_m)
    out, bare, stranger = [], [], False
    for q in placed:
        if str(q.id) in decks:
            out.append(q)
        elif _plan(q, cache, law) is None:
            bare.append(q)
        elif _rides(q, foot, hi, cache, law):
            out.append(q)
        else:
            stranger = True
    return out if stranger else out + bare


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
    # a frame of one deck piece may still be cut to two spans (_combined)
    cand = [fr for _decks, fr in _frames(objects, tol)]
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
        placed = _frame_members(fr, [by_id[m] for m in db.members if m in by_id],
                                polys, cache, law)
        out.append(_Takeover(db.object_id, db.resource,
                            tuple((str(q.id), str(q.path), tuple(reversed(to_ll(*q.xy))))
                                  for q in placed),
                            tuple(r for q in placed if (r := _plan(q, cache, law))),
                            tuple(fr), tuple(sorted({p.object_id for p in fr}))))
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
    terrain) standing between ``lo`` and ``hi`` over its own ground (its
    placement's ``y = 0``: a pack bridge stands on the road it spans, its
    deck a slab and a clearance over it) as one frame plan, or ``None``.
    Read in the object's own frame, never against the survey: the pack's
    anchor level is what the object stage re-seats (KMCO ``puente2.obj``:
    980 m wide, its anchor's survey 5 m over the taxiway it carries)."""
    from ..airport import frame_entry as _fe
    from ..airport.object_cut import _face_normals_y
    g = cache.geometry(o.resolved) if cache is not None and o.resolved else None
    if g is None or g.solid is None or not len(g.solid):
        return None
    tris = _static_solid(g, g.animated, getattr(g, "under_terrain", np.zeros(0, dtype=bool)))
    if not tris.shape[0]:
        return None
    v = g.vertices
    ny = float(law.tables.structures.bridge.deck_plate_normal_y_min)
    ys = v[tris][:, :, 1]
    # a DECK over a road: a clearance over the object's own lowest solid --
    # never the road surface a tunnel-ramp object draws (KRDU NewC2_RP.obj)
    floor = float(ys.min()) + float(law.tables.structures.bridge.clearance_minimum_m)
    up = (_face_normals_y(v, tris) >= ny) & (ys.min(axis=1) >= max(lo, floor)) \
        & (ys.max(axis=1) <= hi)
    if not up.any():
        return None
    polys = [p for p in shapely.polygons(v[tris[up]][:, :, [0, 2]])
             if p.is_valid and p.area > 1e-6]
    return _placed(o, _fe.union(polys, "deck_takeover.body"), law) if polys else None


def _bodies(g: DeckBridge, objects, cache, airport, law, skip: _t.AbstractSet[str],
            share: "float | None") -> list[tuple[_t.Any, float]]:
    """``[(placement, its deck-level top's area over the deck)]``: every
    pack placement of ``objects`` (``skip`` aside) drawing a top at a
    bridge deck's height over its own ground -- from ``[deck_gen]
    pack_structure_depth_m`` under it to the generated deck's own depth
    (``floor_min_m``: the slab and the road's clearance) plus ``[bridge]
    clearance_minimum_m`` over it (never a structure passing over: a
    people-mover guideway stands higher) -- over ``g``'s footprint by
    ``[deck_gen] min_area_m2``, and, with ``share``, over at least that
    share of its covered roads' axis inside it (a bridge over the road).
    Its top stands a clearance over its own lowest solid (a deck, never a
    ramp's road surface); a pack HARD deck is never one (the deck law's)."""
    from shapely.geometry import LineString

    from .deck_bridge import deck_polygon
    ring = deck_polygon(g)
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    lo = -float(law.tables.structures.deck_gen.pack_structure_depth_m)
    hi = float(g.floor_min_m) + clear
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    axes = [LineString(c).intersection(ring) for _w, _t, c in g.covered or () if len(c) >= 2]
    total = sum(x.length for x in axes)
    out = []
    for o in objects or ():
        bb = getattr(o, "plan_bbox", None)
        if str(o.id) in skip or bb is None or not bb.intersects(ring):
            continue
        hd = getattr(o, "hard_deck", None)
        if (hd is not None and not hd.is_empty) or str(getattr(o, "deck_kind", "") or "") in (
                "flag", "signature"):
            # a pack HARD deck is the deck law's: it refused the crossing or
            # passes over it (``deck_pack_cover.overhead_decks``: KRDU
            # STH_TML.obj, the terminal over the taxiway) -- never hidden here
            continue
        top = _body_top(o, cache, law, lo, hi)
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


def _rides(q, footprint, hi: float, cache, law) -> bool:
    """``q`` RIDES the deck ``footprint`` (owner 2026-11-20T22:39Z, KDFW:
    "make sure we're not hiding half the airport pack"): at least
    ``[deck_gen] hide_inside_share`` of its solid plan lies within the
    footprint, and it is no BUILDING -- no up-facing top of ``[deck_gen]
    min_area_m2`` stands a clearance over the deck's level ``hi`` (its own
    ground's frame, :func:`_body_top`).  A placement with no solid plan
    (its lights) is judged by its frame (:func:`_mates`)."""
    from shapely.geometry import Polygon
    pq = _plan(q, cache, law)
    if pq is None or footprint is None:
        return False
    try:
        plan = Polygon(pq).buffer(0.0)
        if plan.area <= 0.0 or plan.intersection(footprint).area < float(
                law.tables.structures.deck_gen.hide_inside_share) * plan.area:
            return False
    except shapely.errors.GEOSException:             # an invalid pack outline
        return False
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    roof = _body_top(q, cache, law, hi + clear, float("inf"))
    return roof is None or roof.area < float(law.tables.structures.deck_gen.min_area_m2)


def _mates(o, objects, hidden: _t.AbstractSet[str], cache, law, tol: float,
           footprint=None, hi: float = 0.0) -> list:
    """``o`` and its FRAME MATES: the placements co-placed with it
    (``deck_bridge.co_placed``) that belong to its bridge -- one whose solid
    plan overlaps ``o``'s by ``[deck_gen] min_area_m2`` AND rides the deck
    ``footprint`` (:func:`_rides`: within it, no building), or one with no
    solid at all (its lights) where every solid co-placed with ``o`` is such
    a mate.  An anchor many placements share (a whole pack placed at one
    point: KDFW's Aerosoft objects, ~150 on one anchor, the bridge plates
    313 x 176 m overlapping the terminal's plans) is no frame: hiding the
    bridge never hides the airport (lane lcross21 (D); MEASURED KDFW
    1.0.569: 103 placements hidden by plan overlap alone, lane lcross22)."""
    from shapely.geometry import Polygon

    from .deck_bridge import co_placed
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    own = _plan(o, cache, law)
    body = Polygon(own).buffer(0.0) if own else None
    near = [q for q in objects if q is not o and str(q.id) not in hidden and co_placed(o, q, tol)]
    solid, bare, stranger = [], [], False
    for q in near:
        pq = _plan(q, cache, law)
        if pq is None:
            bare.append(q)
        elif body is not None and Polygon(pq).buffer(0.0).intersection(body).area >= a_min \
                and (footprint is None or _rides(q, footprint, hi, cache, law)):
            solid.append(q)
        else:
            stranger = True
    # a stranger on the anchor: the lights there are no longer the bridge's
    return [o, *solid] if stranger else [o, *solid, *bare]


def _capped(out: list, objects, bodies: _t.AbstractSet[str], notes: list[str], law) -> list:
    """THE HIDE GUARD (owner 2026-11-20T22:39Z): the decks of ``out`` hide
    at most ``[deck_gen] hide_max_share`` of the pack's placements
    ``objects`` (never fewer than ``hide_floor_count``); past it every deck keeps only the bridge ``bodies`` it
    took (a frame's deck placements, a body over a crossing; their mates
    stay drawn) and the
    note says so -- a read to check, never half the airport hidden."""
    n = len(objects or ())
    ids = {h[0] for d in out for h in getattr(d, "hides", ()) or ()}
    cap = float(law.tables.structures.deck_gen.hide_max_share) * n
    if not n or len(ids) <= max(cap, float(law.tables.structures.deck_gen.hide_floor_count)):
        notes.append(f"pack placements hidden: {len(ids)} of {n}")
        return out
    kept = []
    for d in out:
        hides = tuple(h for h in getattr(d, "hides", ()) or () if h[0] in bodies)
        kept.append(_dc.replace(d, hides=hides) if hides != tuple(d.hides or ()) else d)
    notes.append(f"DEFECT -- the hides would take {len(ids)} of {n} pack placements "
                 f"(over [deck_gen] hide_max_share {cap / n:.0%}): only the "
                 f"{len({h[0] for d in kept for h in d.hides})} bridge bodies hidden, "
                 f"their mates kept (owner 2026-11-20T22:39Z)")
    return kept


def one_decision(gen: _t.Sequence[DeckBridge], takes: _t.Sequence[_Takeover], objects,
                 cache, airport, law) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(gen, notes)``: THE ONE DECISION per crossing our decks were
    generated at (the block comment above): the walled frames this build
    hid (:func:`_attach`), then every other pack bridge body over a
    generated deck's crossing hidden with its frame mates (``hides``,
    ``hidden_plans``), and what is still left under a deck's footprint
    recorded as its defect (``pack_under``)."""
    out, notes = _attach(gen, takes, law)
    out = list(out)
    if not objects or cache is None:
        return tuple(out), notes
    share = float(law.tables.structures.deck_gen.pack_cover_share)
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    clear = float(law.tables.structures.bridge.clearance_minimum_m)
    reach = float(law.tables.structures.bridge.abutment_sample_step_m)
    to_ll = airport.frame.transformers()[1]
    hidden = {h[0] for d in out for h in getattr(d, "hides", ()) or ()}
    bodies = {m for t in takes for m in t.bodies}
    for k, g in enumerate(out):
        if g.family == "road":
            continue
        # the deck over the crossing: what rides it is hidden with the body
        foot = deck_polygon(g).buffer(reach)
        for o, area in _bodies(g, objects, cache, airport, law, hidden, share):
            mates = _mates(o, objects, hidden, cache, law, tol, foot,
                           float(g.floor_min_m) + clear)
            hidden.update(str(q.id) for q in mates)
            bodies.add(str(o.id))
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
    out = _capped(out, objects, bodies, notes, law)
    hidden = {h[0] for d in out for h in getattr(d, "hides", ()) or ()}
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


# ── A SPAN BAND OUR DECK TAKES (lane lcross22, #2202 items 2-4) ──────────
#
# A pack hard deck CUT TO ITS SPANS (RULINGS 2026-11-18i, ``DeckBridge.
# span_cut``: KRDU STH_TML obj140 with its riders obj141 / obj142) is one
# rigid object over two or more crossings.  Owner 2026-11-20T23:53Z: "When
# a pack combines multiple bridges into a single object that can't follow
# the real terrain slopes, like KRDU ... we drop that whole object, so we
# can follow the terrain better and build our own bridges" -- no piece of
# it is kept (not the raised middle of a taxiway either).  The full map's
# takeover reads such a frame as a multi-bridge frame (:func:`_combined`)
# and hides it whole where our decks take every span; where a generated
# deck still stands on one of its spans after that, :func:`span_bands`
# drops it whole too and names any span left without our deck.  Never
# both: a pack span band still under a generated deck is the deck's
# ``pack_under`` defect (census ``pack_bridge_under_deck``).


def _span_of(d: DeckBridge) -> "int | None":
    """The index of the span (``span_cut[2]``) span piece ``d`` stands on:
    the one holding its ring's centroid's station along the cut's axis."""
    a, b, spans = d.span_cut[0], d.span_cut[1], d.span_cut[2]
    L = float(np.hypot(b[0] - a[0], b[1] - a[1]))
    if L <= 0.0 or not spans:
        return None
    c = deck_polygon(d).centroid
    st = ((c.x - a[0]) * (b[0] - a[0]) + (c.y - a[1]) * (b[1] - a[1])) / L
    return next((k for k, (sa, sb) in enumerate(spans) if sa - 1.0 <= st <= sb + 1.0), None)


def span_bands(decks: _t.Sequence[DeckBridge], objects, cache, law, to_ll=None
               ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(decks, notes)``: every pack frame cut to its spans (18i) one of
    whose spans a GENERATED deck of ``decks`` stands on by ``[deck_gen]
    min_area_m2`` is dropped WHOLE (owner 2026-11-20T23:53Z: a combined
    multi-bridge object keeps no piece): its pieces leave the decks and
    its placements are hidden with that deck (``hides``), never a building
    (:func:`_frame_members`); a span no generated deck takes is named
    DEFECT.  Then any pack span band still under a generated deck is that
    deck's ``pack_under`` defect.  ``objects``: the pack placements;
    ``cache``: the geometry cache; ``to_ll``: ``(x, y) -> (lat, lon)``."""
    a_min = float(law.tables.structures.deck_gen.min_area_m2)
    gen = [(k, deck_polygon(d)) for k, d in enumerate(decks) if is_generated(d)]
    if not gen:
        return tuple(decks), []
    taken: dict[tuple, set[int]] = {}
    over: dict[int, int] = {}                    # pack piece index -> generated deck index
    for i, d in enumerate(decks):
        if is_generated(d) or not getattr(d, "span_cut", ()):
            continue
        p = deck_polygon(d)
        hit = [k for k, g in gen if p.intersection(g).area >= a_min]
        k = _span_of(d)
        if hit and k is not None:
            taken.setdefault((tuple(d.span_cut[0]), tuple(d.span_cut[1])), set()).add(k)
            over[i] = hit[0]
    if not taken:
        return _under_defects(tuple(decks), gen, a_min, to_ll), []
    # owner 2026-11-20T23:53Z: no piece of a combined frame is kept -- every
    # piece of a frame one of whose spans our deck takes leaves the decks,
    # and the frame is hidden with that deck (never a building, the KDFW
    # rule: ``_frame_members``); a span no generated deck takes is named
    out: list = list(decks)
    notes: list[str] = []
    gone: set[int] = set()
    for key, ks in taken.items():
        mine = [i for i, d in enumerate(decks) if getattr(d, "span_cut", ())
                and (tuple(d.span_cut[0]), tuple(d.span_cut[1])) == key]
        gone.update(mine)
        d0 = decks[mine[0]]
        g_i = over[next(i for i in mine if i in over)]
        g = out[g_i]
        ids = {m for i in mine for m in (decks[i].members or (decks[i].object_id,))}
        frame = [decks[i] for i in mine]
        placed = _frame_members(frame, [q for q in objects or () if str(q.id) in ids],
                                [p for _k, p in gen], cache, law) \
            if objects else []
        have = {h[0] for h in g.hides}
        if to_ll is not None:
            out[g_i] = _dc.replace(g, hides=tuple(g.hides) + tuple(
                (str(q.id), str(q.path), tuple(reversed(to_ll(*q.xy))))
                for q in placed if str(q.id) not in have))
        free = [sp for k, sp in enumerate(d0.span_cut[2]) if k not in ks]
        notes.append(f"{d0.object_id} {d0.resource.rsplit('/', 1)[-1]}: a combined "
                     f"multi-bridge object, span(s) "
                     + ", ".join(f"{d0.span_cut[2][k][0]:.0f}-{d0.span_cut[2][k][1]:.0f} m"
                                 for k in sorted(ks))
                     + f" taken by our deck(s) "
                     + ", ".join(sorted({decks[over[i]].object_id for i in mine if i in over}))
                     + ": the whole object is HIDDEN with " + g.object_id
                     + " (owner 2026-11-20T23:53Z)"
                     + ("" if not free else "; DEFECT -- no generated deck takes span(s) "
                        + ", ".join(f"{a:.0f}-{b:.0f} m" for a, b in free)))
    out = [d for i, d in enumerate(out) if i not in gone]
    gen = [(k, deck_polygon(d)) for k, d in enumerate(out) if is_generated(d)]
    return _under_defects(tuple(out), gen, a_min, to_ll), notes


def _under_defects(decks: tuple, gen, a_min: float, to_ll) -> tuple:
    """``decks`` with each pack span band (a hard-deck piece cut to its
    spans) standing on a generated deck recorded on it (``pack_under``):
    ours and the pack's both there."""
    if to_ll is None:
        return decks
    out = list(decks)
    for i, d in enumerate(decks):
        # a span band (18i): the pack's overhead decks pass over, never on it
        if is_generated(d) or not getattr(d, "span_cut", ()):
            continue
        p = deck_polygon(d)
        for k, g in gen:
            a = p.intersection(g).area
            if a >= a_min:
                rec = (str(d.object_id), str(d.resource),
                       tuple(reversed(to_ll(*p.centroid.coords[0]))), round(a, 1))
                if rec[0] not in {u[0] for u in out[k].pack_under}:
                    out[k] = _dc.replace(out[k], pack_under=tuple(out[k].pack_under) + (rec,))
    return tuple(out)
