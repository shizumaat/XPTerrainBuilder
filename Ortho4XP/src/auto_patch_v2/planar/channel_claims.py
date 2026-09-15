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

from ..law import Law
from ..model.airport import Airport, OsmWay
from ..model.structures import Channel
from .channel import _depth_under_crest
from .structure_approach import is_tunnel

__all__ = ['add_channel_cells'] + ['claimed_crossing_ways', 'channel_ways', 'channel_yields', '_within_corridor', 'channel_claiming', 'in_any_corridor']


def claimed_crossing_ways(airport: Airport, law: Law,
                          corridors: _t.Sequence = ()) -> frozenset[int]:
    """§45 (13) (b): THE WAYS THE ENGINE ALREADY MODELS, read off the
    passes' OWN outputs and never re-derived.

    Two sources, both existing: the mapped ``tunnel=yes`` bores
    ``build_structures`` seeds from (``is_tunnel`` on
    ``[tunnel] admitted_values`` — the same predicate, not a copy) and
    the bore ways each 05k-1 object corridor claims
    (``Corridor.bore_ways``, ``tunnel_objects.read_corridors``).  The
    round-3 replays are why this is ONE function handed IN rather than a
    test inside the channel pass: a second reading of "what is already
    modelled" is exactly what let a channel delete four KCLT bores."""
    tn = law.tables.structures.tunnel
    out = {int(w.id) for w in airport.osm_ways
           if is_tunnel(w, tn.admitted_values) and len(w.points) >= 2}
    for c in corridors or ():
        out.update(int(i) for i in (getattr(c, "bore_ways", ()) or ()))
    return frozenset(out)


def channel_ways(channels: _t.Sequence[Channel]) -> set[int]:
    """Every OSM way id any channel owns — the set ``build_structures``
    subtracts from its bore seeds (§45 (1): "A crossing inside a channel
    is NEVER a bore with mouths")."""
    return {int(i) for c in channels for i in c.ways}


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
        if int(w.id) in owned:
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
    from .channel import channel_cells
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
