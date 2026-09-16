"""WHAT AN OPEN CHANNEL CLAIMS, AND WHAT IT YIELDS (spec §45 (1)/(6)/(7)
and §45 (13); owner RULINGS 2026-09-15i, amended 15s and 15aa) — lane
``v2channel``.

Its own module beside ``planar/channel.py`` for that file's 1,000-line
budget, and because these five readings are the channel's INTERFACE to
every other pass: which ways the engine already models (so a channel
never takes one), which ways a channel owns (so they never become bores),
which object a channel claims as its own wall/floor witness (so it never
becomes a basin), and what the tunnel pass must therefore drop.

The round-3 dry replays are why ``claimed_crossing_ways`` is handed IN
from the passes' own outputs rather than re-derived here: a second
reading of "what is already modelled" is what let a channel delete KCLT
taxiway U's four bores and LEMD's F-6 underpass.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..model.airport import Airport, OsmWay
from ..model.structures import Channel
from .channel import (ANY_FEED, FLOOR_ROLE, WALL_ROLE, _depth_under_crest,
                      WayKey, way_key)
from .channel_geometry import _parts, _poly
from .structure_approach import is_tunnel

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

__all__ = ['add_channel_cells', 'channel_cells'] + ['crossing_claims', 'claimed_crossing_ways', 'channel_ways', 'channel_yields', '_within_corridor', 'channel_claiming', 'in_any_corridor', 'way_key', 'WayKey', 'ANY_FEED', 'channel_swallowing']


def crossing_claims(airport: Airport, law: Law, corridors: _t.Sequence = (),
                    classification=None) -> tuple[frozenset[WayKey], frozenset[WayKey]]:
    """§45 (13) (b)/(20): ``(the HARD claims, the SYNTHESISED ones)``.

    THE HARD HALF is what the engine models from DATA the channel cannot
    override: the mapped ``tunnel=yes`` bores ``build_structures`` seeds
    from (``is_tunnel`` on ``[tunnel] admitted_values`` — the same
    predicate, not a copy) and the bore ways each 05k-1 object corridor
    claims (``Corridor.bore_ways``, ``tunnel_objects.read_corridors``).
    Neither ever yields.

    THE SYNTHESISED HALF is §34 (5)'s own: a bore the engine INFERRED
    from a ``bridge=yes`` aeroway over an untagged road.  §45 (16) put
    those ways in the claimed set (round 7 measured KCLT's four taxiway-U
    bores taken by a channel) and §45 (20) then ruled what round 8
    measured with it: at LGAV the TWY H bores took ways −2914/−4017 off
    the trench channel, which carries pack walls under it.  A synthesised
    bore and a channel's deck model the SAME crossing, so where the
    channel carries a DEPTH witness ((1) (c) pack walls or (3) (ii) lidar
    reading a cut) the synthesised bore YIELDS: its ways return to the
    channel and the bore is not built.  The decision is the channel's own
    (``planar/channel.identify_channels``), because only the built record
    knows whether the depth witness stands.

    They are read here, once, off §34 (5)'s OWN function — never
    re-derived: the round-3 replays are why "what is already modelled" is
    ONE reading handed in."""
    tn = law.tables.structures.tunnel
    hard = {way_key(w) for w in airport.osm_ways
            if is_tunnel(w, tn.admitted_values) and len(w.points) >= 2}
    # A corridor states its bore ways as BARE ids (``Corridor.bore_ways``
    # is ``tuple[int, ...]``), so they are qualified here against the
    # ways themselves.  MEASURED 2026-09-15: no producer sets that field
    # — ``bore_ways=`` appears nowhere in ``src`` — so this half of (13)
    # (b) contributes nothing today and the exclusions all come from the
    # mapped ``tunnel=yes`` half above.  A bare id is resolved to every
    # feed that carries it (the collision is exactly what cannot be
    # resolved from an int), which is why the field should carry the way.
    bare = {int(i) for c in (corridors or ())
            for i in (getattr(c, "bore_ways", ()) or ())}
    if bare:
        seen = {int(w.id) for w in airport.osm_ways if int(w.id) in bare}
        hard.update(way_key(w) for w in airport.osm_ways if int(w.id) in bare)
        # a claimed id no feed carries is kept as ANY_FEED rather than
        # dropped: the claim is the pass's output and this function must
        # not lose it just because the id cannot be qualified
        hard.update((ANY_FEED, i) for i in bare - seen)
    synth: set[WayKey] = set()
    if classification is not None and getattr(classification, "cells", None):
        from shapely.geometry import Polygon as _Poly
        from .structure_underpass import underpass_bores as _up
        cells = list(classification.cells)
        up_ways, _parents, _notes = _up(airport, law, cells,
                                        [_Poly(c.ring, c.holes) for c in cells])
        # the synthetic way keeps its PARENT road's id and feed, so its
        # ``way_key`` IS the road way a channel would otherwise take
        synth = {way_key(w) for w in up_ways} - hard
    return frozenset(hard), frozenset(synth)


def claimed_crossing_ways(airport: Airport, law: Law,
                          corridors: _t.Sequence = (),
                          classification=None) -> frozenset[WayKey]:
    """§45 (13) (b): every way the engine already models, hard and
    synthesised — :func:`crossing_claims`' two halves as one set, for the
    callers that do not decide the §45 (20) yield."""
    hard, synth = crossing_claims(airport, law, corridors, classification)
    return frozenset(hard | synth)


def channel_ways(channels: _t.Sequence[Channel]) -> set[WayKey]:
    """Every OSM way any channel owns, as ``(feed, id)`` keys — the set
    ``build_structures`` subtracts from its bore seeds (§45 (1): "A
    crossing inside a channel is NEVER a bore with mouths").  The record
    carries ``way_keys`` for exactly this join; ``ways`` stays the plain
    id list the citations and the sidecar print."""
    out: set[WayKey] = set()
    for c in channels:
        keys = tuple(getattr(c, "way_keys", ()) or ())
        out.update((str(k), int(i)) for k, i in keys)
    return out


def channel_yields(channels: _t.Sequence[Channel], tunnel_ways: _t.Sequence[OsmWay],
                   corridors: _t.Sequence, extra_groups: _t.Sequence,
                   refused: list[str]):
    """WHAT THE CHANNEL TAKES OUT OF THE TUNNEL PASS (§45 (1)/(6)/(7)).

    ``(the bore seeds that remain, the object corridors, the extra
    groups)`` — every input the structure pass would otherwise read a
    SECOND time inside an identified corridor, with its reason appended
    to ``refused``.

    Both halves of the bore test, because both populations exist at the
    three measured sites: a MAPPED bore way the channel owns (its id is
    on the record), and a bore the §34 (5) underpass pass SYNTHESISED
    under a deck that is a channel's neck — KPHX's four, whose eight
    mouths were then ALL refused "the mouth stands against building pad
    building16".  A channel has no mouth (§45 (6)), so neither way
    reaches ``mouths()`` at all and those eight refusals vanish by
    construction rather than by relaxing the pad rule.

    And §45 (7): a wall/floor object standing along the axis is the
    channel's witness (1) (c) — never a tunnel-object corridor, a sunken
    road or a door well.  LGAV measured the alternative: 60 Trench
    refusals, four passes each refusing the same geometry against a DEM
    it stands 12 m under."""
    # §45 (13) (b) SUPERSEDES THE GEOMETRIC DROP (owner RULINGS
    # 2026-09-15aa).  Round 2 dropped a bore seed whose LINE merely lay
    # inside a channel's corridor as well as one the channel OWNED.  Under
    # (13) (b) a way the engine already models is never a channel
    # candidate at all, so a way inside a corridor that the channel does
    # NOT own is a modelled crossing and KEEPS its bore — dropping it
    # anyway contradicts the ruling that admitted it.  Measured at LEMD:
    # the geometric half still deleted five bores (`tunnel:-15327@0`,
    # `-5980@0`, `-15327+-5980@0`, `-17265+-5946+-6640+-1359@0/@1`) whose
    # ways (13) (b) had already excluded from every candidate.
    owned = channel_ways(channels)
    kept: list[OsmWay] = []
    for w in tunnel_ways:
        if way_key(w) in owned:
            refused.append(
                f"osm:{w.id}: the channel's own way — its floor governs the crossing and a "
                f"crossing inside a channel is NEVER a bore with mouths (§45 (1)/(6))")
            continue
        kept.append(w)
    # §45 (11): an object pass yields ONLY where its footprint lies
    # INSIDE the corridor — a structure beside it keeps its own reading
    cors = [c for c in corridors
            if not _within_corridor(channels, getattr(c, "footprint", None))]
    grps = [g for g in extra_groups
            if not _within_corridor(channels,
                                    getattr(getattr(g, "corridor", None), "footprint", None))]
    return kept, cors, grps


def _within_corridor(channels: _t.Sequence[Channel], geom) -> str:
    """The channel whose corridor CONTAINS ``geom`` (§45 (11)'s
    ``within``), or ``""``."""
    if geom is None or getattr(geom, "is_empty", False):
        return ""
    for c in channels:
        ring = c.region or c.crest_ring
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty and geom.within(poly):
            return c.id
    return ""


def channel_claiming(channels: _t.Sequence[Channel], obj, law: Law) -> str:
    """§45 (7) AS SCOPED BY §45 (11) (owner RULINGS 2026-09-15s): the id
    of the channel that CLAIMS this placement as its own wall/floor
    witness, or ``""``.

    Two conditions, both required, and both narrower than round 1's:

    * the placement's BELOW-GRADE FOOTPRINT — never its ``plan_bbox`` —
      lies INSIDE the corridor (``within``, not merely intersecting);
    * its deepest genuine solid stands ``[channel] object_min_depth_m``
      under the channel's crest.

    Round 1 tested "``plan_bbox`` intersects the crest ring", and LGAV's
    two 20 m2 covered pits (``basin:2``/``basin:3``,
    ``TowerTerm_Aera-Fence1.obj``) were swallowed by a corridor they
    merely stood beside.  "A pit beside the corridor keeps its basin"
    (§45 (11)) — this is that sentence."""
    bg = getattr(obj, "below_grade", None)
    z = getattr(obj, "solid_min_z", None)
    if bg is None or z is None or getattr(bg, "is_empty", True):
        return ""
    if getattr(bg, "area", 0.0) <= 1.0:
        return ""
    min_depth = float(law.tables.structures.channel.object_min_depth_m)
    for c in channels:
        ring = c.region or c.crest_ring
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        try:
            if not bg.within(poly):
                continue
        except Exception:                     # pragma: no cover - shapely edge
            continue
        if _depth_under_crest(obj, float(c.crest_estimate_m or 0.0)) < min_depth:
            continue
        return c.id
    return ""


def channel_swallowing(channels: _t.Sequence[Channel], region, member_ids) -> str:
    """§45 (7)/(11) AS A POST-FILTER ON A *BUILT* BASIN (amended (13) (d),
    owner RULINGS 2026-09-15aw): the id of the channel this basin IS —
    its region lies INSIDE that channel's corridor AND every one of its
    members is one of that channel's own (1) (c) witnesses — or ``""``.

    Why the members and not the geometry alone: a pit BESIDE the corridor
    keeps its basin (§45 (11)), and a pit that happens to lie inside one
    but is made of placements the channel never witnessed is a pit inside
    a channel, not the channel's wall.  Both conditions together are the
    only case where the same objects would otherwise be read twice — once
    as the channel's floor, once as a pit.

    It replaces round 5's PLACEMENT drop, which ran before the region
    pass and so could not know whether a basin would be built at all;
    keying on the built basin is what the amendment asks for, and it
    refuses BEFORE the cut, so a swallowed basin cuts no cells."""
    ids = {str(i) for i in (member_ids or ())}
    if not ids or region is None or getattr(region, "is_empty", True):
        return ""
    for c in channels:
        wits = {str(i) for i in (getattr(c, "witness_ids", ()) or ())}
        if not wits or not ids <= wits:
            continue
        ring = c.region or c.crest_ring
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        try:
            if region.within(poly):
                return c.id
        except Exception:                     # pragma: no cover - shapely edge
            continue
    return ""


def in_any_corridor(channels: _t.Sequence[Channel], geom) -> str:
    """The id of the channel whose CREST RING contains ``geom`` (any
    overlap), or ``""``.

    §45 (7) THE DEM IS NOT A WITNESS AGAINST A CHANNEL: a wall/floor
    object standing along the axis is the channel's witness (1) (c) and
    "is never a basin seed, a sunken road, a tunnel-object corridor or a
    door well" — this is the ONE test every one of those passes asks, so
    LGAV's 60 Trench refusals become one channel and not five readings of
    the same geometry."""
    if geom is None or getattr(geom, "is_empty", False):
        return ""
    for c in channels:
        ring = c.crest_ring or c.region
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        try:
            if poly.intersects(geom):
                return c.id
        except Exception:                     # pragma: no cover - shapely edge
            continue
    return ""




# ── the cells (§45 (8) EMISSION) ─────────────────────────────────────────
#
# Here and not in ``planar/channel.py`` for that file's 1,000-line budget,
# and because this module already owns :func:`add_channel_cells`, its one
# caller inside ``src``.

def channel_cells(channels: _t.Sequence[Channel], law: Law
                  ) -> tuple[list[tuple[str, str, Polygon, str]], list[Polygon]]:
    """``([(role, ref, polygon, channel id)…], [the knives])`` — the floor
    and the void, and what the corridor CUTS.

    §45 (8): floor faces ``tunnel_trench`` (already a ``FLOOR_ROLE``),
    banks ``retaining_wall`` (the VOID role — the mesh triangulates the
    bank inside it, exactly as it makes a tunnel's wall), decks UNCHANGED
    airside faces.  Emittable in a heightfield: at every (x, y) exactly
    one of floor / bank / deck, because the deck rings are subtracted from
    both the floor and the void and the void is the crest ring less the
    floor."""
    out: list[tuple[str, str, Polygon, str]] = []
    knives: list[Polygon] = []
    for c in channels:
        floor = _poly(c.region)
        outer = _poly(c.crest_ring) or floor
        if floor is None or outer is None:
            continue
        decks = [_poly(d.ring) for d in c.decks]
        du = unary_union([d for d in decks if d is not None]) if decks else None
        if du is not None and not du.is_empty:
            # §45 (17): the floor stands the WALL BAND back from the deck
            # as it does from the corridor edge — a deck's faces are
            # AIRSIDE and meet the band's crest, never the floor.  Without
            # the set-back the deck's own ring became the floor's edge and
            # one vertex carried the taxiway surface and the floor at once
            # (KDFW v14070: 182.28 against 169.40 over ~23 m, 378
            # infeasible ``pavement_ceiling`` rows).
            band = float(getattr(c, "wall_band_m", 0.0) or 0.0)
            floor = floor.difference(du.buffer(band, **_MITRE) if band > 0.0 else du)
            outer = outer.difference(du)
        void = outer.difference(floor)
        for k, part in enumerate(_parts(floor)):
            out.append((FLOOR_ROLE, c.floor_ref + (f"#{k}" if k else ""), part, c.id))
        for k, part in enumerate(_parts(void)):
            out.append((WALL_ROLE, c.wall_ref + (f"#{k}" if k else ""), part, c.id))
        # the knife is handed on as POLYGONS: subtracting the decks can
        # leave the crest region in pieces, and the keep-out publication
        # reads ``.exterior`` off each one
        knives.extend(_parts(outer))
    return out, knives


def add_channel_cells(channels: _t.Sequence[Channel], law: Law, new_cells: list,
                      footprints: list, keepouts: list, stats) -> int:
    """§45 (8): put each channel's FLOOR and BANK into the pending cells
    and its corridor into the knives and the keep-outs, and return how
    many faces it added.

    The corridor is a keep-out like every structure footprint — that is
    what stops the zone bands at the crest (``planar/zones``) — and the
    knife is what cuts the pavement the corridor runs through.  Lives
    here so ``planar/structures.build_structures`` carries two lines of
    channel and none of its law."""
    if not channels:
        return 0
    cells, knives = channel_cells(channels, law)
    if not cells:
        return 0
    new_cells.extend(cells)
    footprints.extend(knives)
    keepouts.extend(knives)
    stats.channels = len(channels)
    stats.channel_faces = len(cells)
    return len(cells)
