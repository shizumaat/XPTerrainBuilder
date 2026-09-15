"""THE OPEN CHANNEL (spec §45; owner RULINGS 2026-09-15i) — a road / rail
corridor under a STATED CROSSING that keeps its own floor through the
field.

Its own module because ``planar/structures.py`` stands at its 1,000-line
budget and because a channel is NOT a bore: it has no mouths (§45 (6)),
its crest is the design surface and not the DEM (§45 (5)), and the DEM is
not a witness against it (§45 (7)).

THE THREE WITNESS PROFILES the class was measured over (scout
``channelscout``, 2026-09-15 — every number in
``docs/briefs/channelscout-report.md``):

* **LGAV** — the pack models the walls and the floor (``Trench_0x.obj``,
  VT y −12.67…+5.73) and the 30 m Copernicus DEM is blind; one
  ``bridge=yes`` taxiway (way −379) crosses the mapped axis.
* **KDFW** — the 1 m 3DEP DTM SEES the cut (8.64–9.94 m under six
  taxiway bridges, banks ≈ 1:4) and the pack states nothing; the apt.dat
  pavement carries a 2,518 m hole with exactly four paved necks
  (29.1 / 29.9 / 30.3 / 35.0 m).
* **KPHX** — nothing but OSM and apt.dat: ``tunnel=building_passage`` ×6,
  two ``bridge=yes layer=3`` taxiways, two paved necks 23.0 / 22.4 m,
  58 m apart, and a 30 m DEM flat to 0.1 m.

The one thing all three share is the only thing the identification may
rest on: **the CROSSING is witnessed and the CHANNEL is not.**

WHAT THIS MODULE DOES AND DOES NOT DO.  It DERIVES the records
(:func:`identify_channels`) and turns them into planar cells
(:func:`channel_cells`).  It states no constraint row and judges no
emitted surface: ``constraints/channel.py`` reads the record for the rows
and ``verify/channel.py`` for the expectations, so the stated row and the
published expectation are one arithmetic (the drift ``deck_z_on_faces``'s
docstring names).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.structures import (CHANNEL_FLOOR_ROLE, CHANNEL_WALL_ROLE,
                                CREST_DESIGN, Channel, ChannelWall, Deck)
from .channel_geometry import (_across, _bank_toe_half, _bank_width, _deck_ring,
                               _hole_region, _in_hole, _lidar_floor, _parts,
                               _poly, _runs, _sides, _span, _spread_m,
                               _walls_half)
from .structure_approach import carriageway_width_m, is_bridge, is_tunnel, unit
from .structure_underpass import aeroway_decks

__all__ = ["ChannelStats", "identify_channels", "channel_cells",
           "FLOOR_ROLE", "WALL_ROLE",
           "WITNESS_BRIDGE", "WITNESS_NECK", "WITNESS_PACK",
           "WayKey", "way_key", "ANY_FEED"]

FLOOR_ROLE = CHANNEL_FLOOR_ROLE
WALL_ROLE = CHANNEL_WALL_ROLE

#: §45 (1)'s three witness names, recorded on the record VERBATIM ("Each
#: witness is recorded on the record by name").
WITNESS_BRIDGE = "bridge"      # (a) a bridge=yes taxied aeroway over the way
WITNESS_NECK = "neck"          # (b) a paved neck across an unpaved corridor
WITNESS_PACK = "pack"          # (c) the pack's wall / floor objects

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

#: §45 (3): the three floor DATUM sources, in the ruled precedence.
DATUM_PACK = "pack"            # (i)   the pack's floor plates along the axis
DATUM_LIDAR = "lidar"          # (ii)  a CREDIBLE lidar inset's DTM floor
DATUM_CLEARANCE = "clearance"  # (iii) deck top − bridge.clearance_m


@_dc.dataclass
class ChannelStats:
    """What the pass read, for the report and the structure replay."""

    channels: int = 0
    decks: int = 0
    ways: int = 0
    candidates: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    witnesses: list[str] = _dc.field(default_factory=list)
    notes: list[str] = _dc.field(default_factory=list)
    #: how many channels took each §45 (3) datum
    datum_pack: int = 0
    datum_lidar: int = 0
    datum_clearance: int = 0


# ── the road / rail candidates ───────────────────────────────────────────

WayKey = tuple[str, int]

#: A claim that could not be qualified to a feed (see
#: ``channel_claims.claimed_crossing_ways``): it matches the id in EVERY
#: feed.  Never minted from a way — a way always knows its feed.
ANY_FEED = "*"


def way_key(w) -> WayKey:
    """THE IDENTITY OF AN OSM WAY ACROSS PASSES: ``(feed, id)``, never the
    bare id (owner addendum 2026-09-15, measured by the schema session:
    the NEGATIVE ids the feeds mint COLLIDE — 8 of 11 LEMD deck ids carry
    two ways, one from a road feed and one from the airports feed).  A
    bare-id join between the aeroway half of §45 (1) (a) and the road /
    rail half of (1) (b)/(c) or (13) (b) therefore matches ways that are
    not the same way.  ``OsmWay.kind`` is the feed
    (``airport/load``: ``OsmWay(_osm_id(w.id), feed, ...)``), so it is
    the qualifier — one derivation, here."""
    return (str(getattr(w, "kind", "") or ""), int(w.id))


def _is_road_or_rail(w: OsmWay, law: Law) -> bool:
    tags = getattr(w, "tags", None) or {}
    if len(w.points) < 2:
        return False
    if is_bridge(w):
        return False           # a bridge way is the CROSSING, not the channel
    return bool(tags.get("highway") or tags.get("railway"))


# ── (1) IDENTIFICATION ───────────────────────────────────────────────────

def _pavement_union(airport: Airport):
    """THE APT.DAT AIRSIDE PAVEMENT UNION (§45 (1) (b)) — row 110 as
    loaded, INCLUDING §44's borrowed Global pavements (the borrow lands
    on ``Airport.pavements`` at load, so the hole-and-neck read at LGAV
    stands on the borrowed pavement exactly as the brief requires)."""
    polys = []
    for pv in airport.pavements:
        if len(pv.outer) < 3:
            continue
        p = Polygon(list(pv.outer), [list(h) for h in pv.holes if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    u = unary_union(polys)
    return None if u.is_empty else u


@_dc.dataclass
class _Cand:
    """One road/rail way's hole-and-neck read."""

    way: OsmWay
    line: LineString
    ss: list[float]
    necks: list[tuple[float, float]]      # (s0, s1) paved runs = the decks
    corridor_m: float                     # the unpaved run between/beside them
    witnesses: set[str] = _dc.field(default_factory=set)
    bridges: list[tuple[int, float, float]] = _dc.field(default_factory=list)  # (way id, s, half width)
    packs: list[str] = _dc.field(default_factory=list)


def _read_way(w: OsmWay, law: Law, union, holes) -> _Cand | None:
    """§45 (1) (b) THE HOLE AND ITS NECKS, read along ONE way.

    A maximal PAVED run under ``[channel] deck_max_width_m`` flanked by
    unpaved runs on both sides is a NECK — the deck, its plan width the
    run's own length along the road (KDFW's four read 29.1–35.0 m, KPHX's
    two 22.4–23.0 m).  The unpaved runs beside them are the CORRIDOR."""
    ch = law.tables.structures.channel
    ln = LineString(w.points)
    if ln.length < ch.station_m:
        return None
    step = ch.station_m
    n = max(2, int(ln.length // step) + 1)
    ss = [min(ln.length, k * step) for k in range(n + 1)]
    if ss[-1] < ln.length - 1e-6:
        ss.append(ln.length)
    if union is None:
        return _Cand(w, ln, ss, [], ln.length)
    inside = []
    for s in ss:
        p = ln.interpolate(s)
        inside.append(bool(union.contains(Point(p.x, p.y))))
    necks: list[tuple[float, float]] = []
    corridor = 0.0
    runs = _runs(inside)

    def _run_m(k: int) -> float:
        _v, i0, i1 = runs[k]
        return ss[i1] - ss[i0]

    for k, (val, i0, i1) in enumerate(runs):
        s0, s1 = ss[i0], ss[i1]
        if val:
            # THE NECK IS THE EXCEPTION AND THE CORRIDOR THE RULE.  A
            # paved run counts as a DECK only when the way leaves the
            # pavement for a REAL corridor on BOTH sides of it
            # (``corridor_min_length_m`` each).  Without that clause the
            # test reads every service road crossing an apron as a
            # channel: measured at LGAV on the first arm — 3,187
            # candidate ways, 6 "channels", four of them airport service
            # roads with a taxiway painted across them.
            flanked = (k > 0 and k + 1 < len(runs)
                       and _run_m(k - 1) >= ch.corridor_min_length_m
                       and _run_m(k + 1) >= ch.corridor_min_length_m
                       and _in_hole(ln, ss, runs[k - 1], holes)
                       and _in_hole(ln, ss, runs[k + 1], holes))
            if flanked and (s1 - s0) <= ch.deck_max_width_m:
                necks.append((s0, s1))
        else:
            corridor += s1 - s0
    return _Cand(w, ln, ss, necks, corridor)


def _aeroway_bridges(airport: Airport, law: Law) -> list[tuple[OsmWay, LineString]]:
    """§45 (1) (a): every taxied aeroway tagged ``bridge`` at or above
    ``[tunnel] underpass_min_layer``.

    THE DECK READ IS §34 (5)'s OWN (:func:`structure_underpass.
    aeroway_decks`), not a second copy — this function only pairs each
    deck with its line.  Until the owner's 2026-09-15 addendum it shared
    the tag predicate but repeated the loop and the layer parse verbatim,
    which is a second site for §34 (12) (4)'s below-grade witness to miss
    when ``v2vmmcshore`` r6 lands it."""
    return [(w, LineString(w.points)) for w in aeroway_decks(airport, law)]


def _pack_witnesses(cand: _Cand, objects: _t.Sequence, half_m: float,
                    crest_est: float, min_depth_m: float,
                    min_area_m2: float = 1.0,
                    pit_shells: _t.AbstractSet[str] = frozenset(),
                    dropped: list[str] | None = None) -> list[str]:
    """§45 (1) (c): the pack's wall / floor objects along the axis.

    The 05k-1 authority — seat = floor, plate = crest, hull = footprint —
    read through the placement reading the basin pass already made
    (``planar/basins.read_objects``), so nothing re-parses an OBJ8.  A
    placement whose plan runs inside the corridor band and whose deepest
    GENUINE solid stands ``object_min_depth_m`` under the corridor's
    crest is the channel's witness.  It is NOT a basin seed, a sunken
    road, a tunnel-object corridor or a door well (§45 (7))."""
    band = cand.line.buffer(half_m, **_MITRE)
    dropped = dropped if dropped is not None else []
    out: list[str] = []
    for o in objects or ():
        # THE FOOTPRINT, NEVER THE BBOX — the round-1 defect, attributed
        # before it was changed (§45 (12); RULINGS 2026-09-15s).
        # ``plan_bbox`` is the resource's plan EXTENT: at LGAV
        # ``Trench_03``'s is 7,984,284 m2 (2.5 x 3.2 km) and
        # ``Trench_06``'s 8,800,700 m2, so EVERY candidate band on the
        # field intersected them and five separate "channels" all read
        # one floor.  Worse, the number they read — 63.43 — came from
        # ``train_powercable.obj``, whose ``below_grade`` is a
        # ZERO-AREA MultiPolygon straddling the axis and whose
        # ``solid_min_z`` is the family's lowest: the floor of LGAV's
        # trench was the power cable.  So the witness is the object's
        # own below-grade footprint WITH REAL AREA, and an object that
        # states no footprint states no width and no floor.
        # §45 (13) (d) A BASIN'S OWN SHELL IS NEVER A CHANNEL'S WALL
        # (owner RULINGS 2026-09-15ac).  The object side is decided by the
        # object's own KIND, at the one derivation site the basin pass
        # already owns — ``airport/basin_witness.basin_member_ids``: a
        # placement carrying a basin FLOOR WITNESS is a PIT SHELL whose
        # rim tops out at grade (§24 (1)), not a trench wall running along
        # an axis.  Basins are built AFTER channels, so (13) (b)'s
        # "already claimed" set does not exist for objects and the kind
        # test is what stands in its place.  Measured at LEMD round 4:
        # ``channel:5`` (way −5989, neck + pack, ONE deck) took
        # ``dsf:obj7`` / ``dsf:obj10`` — two of ``basin:0``'s three
        # members ``Ground-FSX-LEMD36/37/85`` — and §24's owner-accepted
        # T4S basin then fell to "overlaps a tunnel structure".
        bb = getattr(o, "below_grade", None)
        z = getattr(o, "solid_min_z", None)
        if bb is None or z is None or getattr(bb, "area", 0.0) <= min_area_m2:
            continue
        try:
            if not band.intersects(bb):
                continue
        except Exception:                     # pragma: no cover
            continue
        if _depth_under_crest(o, crest_est) < min_depth_m:
            continue
        oid = str(getattr(o, "id", ""))
        if oid in pit_shells:
            # the test above is (13) (d)'s, and it runs HERE — after the
            # footprint / band / depth tests — for one reason only: so the
            # drop is REPORTABLE.  A placement refused before those tests
            # is a silent nothing, and the LGAV round-5 arm then cost two
            # full airport loads to learn WHICH object went (the answer:
            # Trench_07 / Trench_08).  Same rule, named.
            dropped.append(oid)
            continue
        out.append(oid)
    return out


def _res_of(o) -> str:
    """The placement's RESOURCE as the pack names it — ``resource`` when
    the reading carries one, else the placed ``path`` (``obj8`` states
    the path; the LGAV round-5 note read ``?`` for all three)."""
    for k in ("resource", "path"):
        v = getattr(o, k, None)
        if v:
            return str(v)
    return "?"


def _depth_under_crest(o, crest_est: float) -> float:
    """HOW FAR THIS PLACEMENT'S DEEPEST GENUINE SOLID STANDS UNDER THE
    GROUND OVER IT (§45 (1) (c)/(7)) — the ONE reading both the witness
    test and §45 (7)'s exclusion ask.

    ``obj8`` already measures it per component against the LOCAL terrain
    (``solid_min_depth_m``, negative below), and that is what is used.
    The scalar corridor mean is only the fallback, and the round-2 arm
    measured why it cannot be the rule: LGAV's axis is 1,954 m long over
    12.6 m of relief, so its mean DEM reads 67.48 while the DEM along it
    runs 64.32…76.96.  Against that mean ``Trench_07`` (its own local
    depth −11.03 m) read 1.02 m and ``Trench_08`` (−8.19 m) read −2.17 m
    — both refused by ``object_min_depth_m`` 3.0, which is why the trench
    did not witness its own channel."""
    d = getattr(o, "solid_min_depth_m", None)
    if d is not None:
        return -float(d)
    z = getattr(o, "solid_min_z", None)
    if z is None or math.isnan(crest_est):
        return 0.0
    return float(crest_est) - float(z)


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _lidar_credible(airport: Airport, law: Law) -> bool:
    """§45 (3) (ii): whether THIS airport's inset is a CREDIBLE lidar one
    — the inset's OWN class, read through the flat-site detector's single
    derivation (``law.tables.flat_site.detector.lidar_credible_max_m``),
    never a second pixel-size rule.  A refresh (``--refresh-data dem``,
    the owner's act) moves a site from (iii) to (ii) with no law change:
    this is the only place that reading lives."""
    fv = getattr(airport, "flat_site", None)
    if fv is not None:
        klass = (fv.signals or {}).get("s2_source_class")
        if klass:
            return str(klass) == "lidar"
    try:
        from ..airport.flat_site import _source_class
        klass, _pixel, _whence = _source_class(airport.dem, law)
    except Exception:                          # pragma: no cover - fixtures
        return False
    return str(klass) == "lidar"


# ── the derivation ───────────────────────────────────────────────────────

def identify_channels(airport: Airport, classification, law: Law,
                      objects: _t.Sequence = (),
                      claimed_ways: _t.AbstractSet[int] = frozenset(),
                      pit_shell_ids: _t.AbstractSet[str] = frozenset()
                      ) -> tuple[list[Channel], ChannelStats]:
    """THE CHANNEL RECORDS (§45 (1)–(7)), derived ONCE.

    Order, exactly as the brief's ORDER OF WORK ruled it: the
    hole-and-neck read of the apt.dat pavement union (1) (b) is the FIRST
    witness — it is free at all three airports and depends on neither
    OSM's tags, the DEM nor a pack — then ``bridge=yes`` (1) (a), then the
    pack's wall / floor objects (1) (c).

    §45 (13) A CHANNEL NEVER TAKES A MODELLED CROSSING (owner RULINGS
    2026-09-15aa) is applied HERE and nowhere else — three clauses, in
    precedence:

    (b) ``claimed_ways`` is the set of OSM way ids the engine ALREADY
        models: the mapped ``tunnel=yes`` bores ``build_structures``
        seeds from and the bore ways every 05k-1 object corridor claims
        (``tunnel_objects.read_corridors``).  It is handed IN, never
        re-derived — two derivations of "what is already modelled" is
        how a channel came to delete KCLT taxiway U's four bores.  A
        pack-wall or lidar witness does NOT override it: at LGAV the
        trench ways carry no ``tunnel`` tag and no object corridor, so
        nothing competes.
    (a) a crossing witnessed by an aeroway ``bridge=yes`` way ALONE — no
        neck, no pack, no lidar — is §34 (5)'s underpass and keeps the
        bore-with-mouths model; (1) (a) is a witness only in COMPANY
        (LGAV: bridge + pack).
    (c) otherwise a channel needs a pack or lidar witness, or a neck
        witness with at least ``min_decks_without_depth`` decks (§45
        (12), ratified).
    (d) ``pit_shell_ids`` is ``airport/basin_witness.basin_member_ids``
        — the basin pass's OWN derivation of "this placement carries a
        floor witness", handed IN for the same reason ``claimed_ways``
        is: a placement in it is a PIT SHELL and is never a (1) (c)
        wall/floor witness.  A channel left without a depth witness by
        it then faces (c).
    """
    stats = ChannelStats()
    ch = law.tables.structures.channel
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    union = _pavement_union(airport)
    holes = _hole_region(union)
    cands: list[_Cand] = []
    # §45 (13) (b) JOINED BY FEED, NEVER BY THE BARE ID (owner addendum
    # 2026-09-15): ``claimed_ways`` is a set of ``(feed, id)`` keys from
    # ``channel_claims.claimed_crossing_ways``.  A bare-int set is still
    # accepted — the twins that predate the key and any caller that
    # hands one in — but it is qualified against the way itself, because
    # a negative id alone names a road-feed way AND an airports-feed way
    # at 8 of LEMD's 11 decks.
    claimed = {i for i in (claimed_ways or ()) if isinstance(i, tuple)}
    claimed_bare = {int(i) for i in (claimed_ways or ()) if not isinstance(i, tuple)}
    n_claimed = 0
    for w in airport.osm_ways:
        if not _is_road_or_rail(w, law):
            continue
        if (way_key(w) in claimed or (ANY_FEED, int(w.id)) in claimed
                or int(w.id) in claimed_bare):
            # §45 (13) (b): the engine already models this crossing
            n_claimed += 1
            continue
        c = _read_way(w, law, union, holes)
        if c is None:
            continue
        if c.necks:
            c.witnesses.add(WITNESS_NECK)
        cands.append(c)
    if n_claimed:
        stats.notes.append(
            f"§45 (13) (b): {n_claimed} way(s) excluded from every channel candidate — a "
            f"mapped `tunnel=yes` bore or a 05k-1 object corridor already models them")
    stats.candidates = len(cands)
    # (1) (a) A DECK STATES A CROSSING: a taxied aeroway bridge over the way
    for w, bln in _aeroway_bridges(airport, law):
        half = carriageway_width_m(w.tags, law) / 2.0
        for c in cands:
            if not c.line.intersects(bln):
                continue
            x = c.line.intersection(bln)
            pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
            if not pts:
                continue
            s = c.line.project(Point(pts[0].x, pts[0].y))
            c.witnesses.add(WITNESS_BRIDGE)
            c.bridges.append((int(w.id), float(s), float(half)))
    # §45 (1): a channel is stated by its CROSSING.  A candidate with
    # neither a neck nor a bridge over it is an ordinary road.
    live = [c for c in cands if c.necks or c.bridges]
    if not live:
        return [], stats
    # ── the merge (§45 (1)): ways within ``merge_m``, and ways SHARING a
    # crossing, are ONE channel.  KDFW's two carriageways stand 121 m
    # apart — beyond ``merge_m`` — but taxiways A and B bridge the west
    # cut alone and Z / Y bridge the west and east cuts as two SEPARATE
    # spans, which is why KDFW is two parallel channels and the 121 m
    # median between them is real fill the mesh must keep (scout §1b/§2a).
    groups = _merge(live, ch.merge_m, ch.corridor_max_half_width_m)
    channels: list[Channel] = []
    for k, grp in enumerate(groups):
        c = _build_one(airport, law, f"channel:{k}", grp, union, objects, stats,
                       pit_shell_ids)
        if c is not None:
            channels.append(c)
    stats.channels = len(channels)
    stats.decks = sum(len(c.decks) for c in channels)
    stats.ways = sum(len(c.ways) for c in channels)
    for c in channels:
        stats.witnesses.append(
            f"{c.id}: ways {'+'.join(str(i) for i in c.ways)} — witnesses "
            f"{', '.join(c.witnesses)}; {len(c.decks)} deck(s); floor datum "
            f"{c.datum_source}; {c.profile[0][1]:.2f}..{c.profile[-1][1]:.2f} m over "
            f"{c.profile[-1][0] - c.profile[0][0]:.0f} m")
    return channels, stats


def _merge(cands: list[_Cand], merge_m: float, cap_m: float) -> list[list[_Cand]]:
    """§45 (11) A CHANNEL IS ONE CORRIDOR, NOT A TRANSITIVE CHAIN (owner
    RULINGS 2026-09-15s).

    Ways join a channel while they are within ``merge_m`` of a member (or
    share a crossing way) AND the merged group's spread ACROSS ITS AXIS
    stays under ``corridor_max_half_width_m``.  Round 1 used bare
    union-find over "within ``merge_m``" with no diameter bound, and
    40 m links chained ``channel:2`` **404.7 m** off its own axis — a
    corridor nobody mapped, assembled one hop at a time.

    Greedy from the LONGEST way outward, because the long mapped
    carriageway or rail IS the corridor and a stub joins it, never the
    other way round."""
    order = sorted(range(len(cands)), key=lambda i: -cands[i].line.length)
    groups: list[list[_Cand]] = []
    for i in order:
        c = cands[i]
        placed = False
        for g in groups:
            near = any(m.line.distance(c.line) <= merge_m for m in g)
            shared = bool({b[0] for b in c.bridges}
                          & {b[0] for m in g for b in m.bridges})
            if not (near or shared):
                continue
            if _spread_m(g, c) > cap_m:
                continue               # (11): the cap bounds the merge
            g.append(c)
            placed = True
            break
        if not placed:
            groups.append([c])
    return groups


def _build_one(airport: Airport, law: Law, cid: str, grp: list[_Cand], union,
               objects: _t.Sequence, stats: ChannelStats,
               pit_shells: _t.AbstractSet[str] = frozenset()) -> Channel | None:
    """One channel's record: the axis, the decks, the corridor's
    half-width, the FLOOR (§45 (3)), the walls (§45 (5)) and the ends."""
    ch = law.tables.structures.channel
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    # THE AXIS is the group's LONGEST member's own centreline: a mapped
    # carriageway is the corridor's real route, and averaging two
    # carriageways 121 m apart would put the axis on the median that is
    # real fill (scout §2a).  The other members ride beside it.
    lead = max(grp, key=lambda c: c.line.length)
    axis_ln = lead.line
    step = ch.station_m
    ss = [min(axis_ln.length, k * step) for k in range(int(axis_ln.length // step) + 1)]
    if not ss or ss[-1] < axis_ln.length - 1e-6:
        ss.append(axis_ln.length)
    if len(ss) < 2:
        stats.refused.append(f"{cid}: the axis is shorter than one station "
                             f"({axis_ln.length:.0f} m)")
        return None

    def axis_fn(s: float) -> XY:
        p = axis_ln.interpolate(min(max(s, 0.0), axis_ln.length))
        return (p.x, p.y)

    # ── §45 (10) THE HOLE IS A CROSSING WITNESS, NOT A WIDTH ──────────
    # (owner RULINGS 2026-09-15s, ruling the lane's round-1 deviation.)
    # The hole and its necks state THAT a crossing exists and WHERE the
    # decks are; the WIDTH takes its own precedence: (i) the pack's wall
    # objects along the axis, (ii) a credible lidar's bank toes on the
    # axis normal, (iii) the carriageways ⊕ ``lane_width_m`` with (5)'s
    # bank beyond — all capped by ``corridor_max_half_width_m``.  The
    # measurement that deleted the hole rule: at KDFW the hole is
    # 2,518 x ~1,150 m, the whole gap between the terminal horseshoes,
    # against a cut the 1 m DTM reads 84.3-105.8 m wall to wall.
    cap = ch.corridor_max_half_width_m
    widest = max(carriageway_width_m(c.way.tags, law) for c in grp)
    # (iii), the floor of every reading — the OVERLAP offset only
    # (:func:`_across`: an end-clamped projection is an overhang, not a
    # width; that is the 404.7 m of round 1)
    lateral = max((_across(axis_ln, c.line.coords) for c in grp), default=0.0)
    half_base = min(cap, lateral + widest / 2.0 + tn.lane_width_m)
    zs0 = [_dem(airport, axis_fn(s)) for s in ss]
    good0 = [z for z in zs0 if not math.isnan(z)]
    crest_est = (sum(good0) / len(good0)) if good0 else 0.0
    pit_drop: list[str] = []
    packs0 = _pack_ids(grp, objects, cap, airport, law, axis_fn, ss, pit_shells,
                       pit_drop)
    if pit_drop:
        # §45 (13) (d), NAMED: a candidate that read a wall/floor witness
        # and lost it to the pit test says WHICH placement it lost, in
        # the stats every replay publishes — a refused channel keeps no
        # record of its own, so this is the only place it can be said.
        _byid = {str(getattr(o, "id", "")): o for o in objects or ()}
        _seen = list(dict.fromkeys(pit_drop))
        _res = ", ".join(
            f"{i} ({_res_of(_byid.get(i))})" for i in _seen)
        stats.notes.append(
            f"{cid}: §45 (13) (d) dropped {len(_seen)} pack wall/floor "
            f"witness(es) — a basin FLOOR WITNESS (airport/basin_witness."
            f"basin_member_ids) is a pit shell, never a channel's wall: {_res}")
    decks, deck_half = _decks(airport, law, cid, grp, axis_ln, axis_fn, union,
                              objects, packs0)
    # (i) THE PACK'S WALL OBJECTS ALONG THE AXIS.  Searched at the cap —
    # the widest a corridor may be — and then the width is what they
    # MEASURE, never the search radius.
    packs = packs0
    half_walls = _walls_half(axis_ln, objects, packs)
    if half_walls:
        half_at, width_src = min(cap, max(half_walls, half_base)), "pack walls (10) (i)"
    elif _lidar_credible(airport, law):
        # (ii) THE BANK TOES on the axis normal
        toe = _bank_toe_half(airport, law, axis_fn, ss, cap)
        half_at, width_src = ((min(cap, max(toe, half_base)), "lidar bank toes (10) (ii)")
                              if toe else (half_base, "carriageways ⊕ lane_width_m (10) (iii)"))
    else:
        half_at, width_src = half_base, "carriageways ⊕ lane_width_m (10) (iii)"
    widths = tuple((float(s), float(half_at)) for s in (ss[0], ss[-1]))

    # ── the ENDS (§45 (2)): where the corridor leaves the pavement union
    # ⊕ ``mouth_standoff_m``.  Beyond them §37 governs and the floor
    # rejoins the road's own profile at ≤ ``ramp_max_grade``.
    field = union.buffer(tn.mouth_standoff_m, **_MITRE) if union is not None else None
    inside = [bool(field.contains(Point(axis_fn(s)))) if field is not None else True
              for s in ss]
    if not any(inside):
        stats.refused.append(f"{cid}: no station of the axis stands on the field "
                             f"(the pavement union ⊕ mouth_standoff_m {tn.mouth_standoff_m:.0f} m)")
        return None
    s_in = [s for s, ok in zip(ss, inside) if ok]
    ends = (float(min(s_in)), float(max(s_in)))
    # §45 (2) THE ENDS.  The channel's own faces exist BETWEEN them;
    # beyond them the road law §37 governs and the floor rejoins the
    # road's own profile at <= ramp_max_grade — which is §37's join, not
    # a second ramp of ours.  Everything from here (the profile, the
    # region, the banks) is stated over the stations INSIDE the ends.
    ss = [s for s in ss if ends[0] - 1e-6 <= s <= ends[1] + 1e-6]
    if len(ss) < 2:
        stats.refused.append(f"{cid}: only {len(ss)} station(s) of the axis stand between "
                             f"the ends {ends[0]:.0f}..{ends[1]:.0f} m")
        return None
    corridor_m = sum(c.corridor_m for c in grp) / max(1, len(grp))
    if not decks:
        stats.refused.append(f"{cid}: witnessed ({', '.join(sorted(_wits(grp)))}) but no "
                             f"crossing spans the corridor — a channel is stated by its "
                             f"deck (§45 (1))")
        return None
    if corridor_m < ch.corridor_min_length_m:
        stats.refused.append(f"{cid}: the unpaved corridor reads {corridor_m:.0f} m, under "
                             f"[channel] corridor_min_length_m {ch.corridor_min_length_m:.0f} — "
                             f"a gap between two pavements, not a channel through the field")
        return None

    to_ll = airport.frame.transformers()[1]

    def ll(p: XY) -> tuple[float, float]:
        la, lo_ = to_ll(p[0], p[1])
        return (round(la, 7), round(lo_, 7))

    # ── (3) THE FLOOR DATUM, in the ruled precedence ───────────────────
    profile, datum, wall_shape, witness_name = _floor(
        airport, law, cid, grp, axis_ln, axis_fn, ss, decks, half_at, objects, stats,
        packs)
    if profile is None:
        return None
    # §45 (13) (a) A BRIDGE-ONLY WITNESS IS §34 (5)'s UNDERPASS (owner
    # RULINGS 2026-09-15aa).  Measured by round 3's six dry replays: on a
    # bridge witness ALONE the pass took KCLT taxiway U's crossing (ways
    # -14074 -3590 -4356 -4359) and deleted the four bores
    # `tunnel:-14074@0..3` the §34 (5) underpass had built, and did the
    # same to LEMD's F-6 service roads -5821/-5820.  §45 (1) (a) is a
    # witness only in COMPANY — at LGAV the bridge stands beside the
    # Trench walls.
    if set(_wits(grp)) == {WITNESS_BRIDGE}:
        stats.refused.append(
            f"{cid}: witnessed by an aeroway bridge ALONE (no neck, no pack wall/floor "
            f"object, no credible lidar) — that is §34 (5)'s UNDERPASS and keeps its "
            f"bore-with-mouths model; §45 (1) (a) is a witness only in company "
            f"(§45 (13) (a)). Ways {'+'.join(str(int(c.way.id)) for c in grp)}")
        return None
    # §45 (12): a channel with NO DEPTH WITNESS — no pack walls (3) (i),
    # no credible lidar (3) (ii), so the floor is (3) (iii)'s "Cut the
    # road down" — needs more than one crossing, WHATEVER witnessed it.
    # With one anchor the floor ramps away from it at ``ramp_max_grade``
    # for the whole axis.
    #
    # The clause was written for a NECK-only channel (LGAV way −4003) and
    # is generalised here by MEASUREMENT, not by preference: the six dry
    # replays of round 3 found LEMD's `channel:0` claiming ways −5821 /
    # −5820 on a BRIDGE witness with ONE crossing and no depth — those
    # are taxiway F-6's service roads, §34 (5)'s own canonical underpass
    # — and deleting the bore `tunnel:-5821+-5820@0` that the underpass
    # pass had built.  One crossing with no depth is a CROSSING; §34 (5)
    # already owns it.
    if (datum == DATUM_CLEARANCE
            and (WITNESS_NECK not in _wits(grp)
                 or len(decks) < ch.min_decks_without_depth)):
        stats.refused.append(
            f"{cid}: witnessed by a paved neck alone and with {len(decks)} crossing(s) "
            f"(< [channel] min_decks_without_depth {ch.min_decks_without_depth}) — a single "
            f"neck is a CROSSING, not a channel; with one anchor \"Cut the road down\" "
            f"ramps the floor away at {tn.ramp_max_grade:.0%} for the whole axis "
            f"({profile[0][1]:.2f}..{max(z for _s, z in profile):.2f} m over "
            f"{axis_ln.length:.0f} m). Ways {'+'.join(str(int(c.way.id)) for c in grp)} "
            f"at {ll(axis_fn(ss[0]))} -> {ll(axis_fn(ss[-1]))} (§45 (12))")
        return None
    if datum == DATUM_PACK:
        stats.datum_pack += 1
    elif datum == DATUM_LIDAR:
        stats.datum_lidar += 1
    else:
        stats.datum_clearance += 1

    # ── (5) THE WALLS: crest = the DESIGN surface, shape witness-first ──
    left, right = _sides(axis_fn, ss, half_at)
    walls = (ChannelWall("left", wall_shape, CREST_DESIGN, tuple(left), tuple(left),
                         witness_name),
             ChannelWall("right", wall_shape, CREST_DESIGN, tuple(right), tuple(right),
                         witness_name))
    region = tuple(left) + tuple(reversed(right))
    # the bank's plan run at each station: (crest − floor) / bank_slope,
    # sized off the DEM ONLY to give the mesh room — the crest's VALUE is
    # the solved surface (§45 (5)), stated by ``constraints/channel.py``.
    bank = _bank_width(airport, axis_fn, ss, profile, ch.bank_slope, wall_shape,
                       law.tables.emit.identity.min_distinct_spacing_m)
    lo, ro = _sides(axis_fn, ss, half_at + bank)
    crest_ring = tuple(lo) + tuple(reversed(ro))
    wits = sorted(_wits(grp))
    notes = [f"{cid}: {len(grp)} way(s) within [channel] merge_m {ch.merge_m:.0f} m share the "
             f"corridor; axis {axis_ln.length:.0f} m, ends {ends[0]:.0f}..{ends[1]:.0f} m; "
             f"corridor half-width {half_at:.1f} m from {width_src} (§45 (10): the HOLE "
             f"states the crossing, never the width — carriageways ⊕ lane_width_m reads "
             f"{half_base:.1f} m here), {len(decks)} crossing(s); bank {bank:.1f} m "
             f"at 1:{1.0 / ch.bank_slope:.0f}",
             f"{cid}: NO MOUTH (§45 (6)) — the ways are the channel's, never a bore's; "
             f"the mouth_standoff_m field test, the §29 cockpit tests and the "
             f"`ramp_crosses_pad` refusal are MOUTH rules and are not applied here"]
    return Channel(
        id=cid,
        ways=tuple(int(c.way.id) for c in grp),
        way_keys=tuple(way_key(c.way) for c in grp),
        axis=tuple(axis_fn(s) for s in ss),
        profile=profile,
        widths=widths,
        decks=tuple(decks),
        walls=walls,
        ends=ends,
        witnesses=tuple(wits),
        datum_source=datum,
        crest_estimate_m=float(crest_est),
        witness_ids=tuple(packs),
        width_source=width_src,
        crest=CREST_DESIGN,
        bank_slope=float(ch.bank_slope),
        floor_ref=f"channel_floor:{cid.split(':')[-1]}",
        wall_ref=f"channel_wall:{cid.split(':')[-1]}",
        region=region,
        crest_ring=crest_ring,
        region_ll=tuple(ll(p) for p in region),
        profile_ll=tuple((*ll(axis_fn(s)), float(z)) for s, z in profile),
        notes=tuple(notes))


def _pack_ids(grp: list[_Cand], objects: _t.Sequence, half_m: float,
              airport: Airport, law: Law, axis_fn, ss,
              pit_shells: _t.AbstractSet[str] = frozenset(),
              dropped: list[str] | None = None) -> list[str]:
    """§45 (1) (c) / (10) (i): the pack placements that witness THIS
    channel — read once, so the width (i), the floor (3) (i), the deck
    pieces (12) and §45 (7)'s exclusion all name the SAME set."""
    ch = law.tables.structures.channel
    zs = [_dem(airport, axis_fn(s)) for s in ss]
    good = [z for z in zs if not math.isnan(z)]
    crest = (sum(good) / len(good)) if good else float("nan")
    out: list[str] = []
    for c in grp:
        for i in _pack_witnesses(c, objects, half_m, crest, ch.object_min_depth_m,
                                 pit_shells=pit_shells, dropped=dropped):
            if i not in out:
                out.append(i)
    return out


def _wits(grp: list[_Cand]) -> set[str]:
    out: set[str] = set()
    for c in grp:
        out |= c.witnesses
    return out


def _decks(airport: Airport, law: Law, cid: str, grp: list[_Cand], axis_ln, axis_fn,
           union, objects: _t.Sequence = (), packs: _t.Sequence[str] = ()
           ) -> tuple[list[Deck], list[tuple[float, float | None]]]:
    """§45 (1)/(4) THE DECKS.  Every neck of every member way, plus every
    aeroway bridge crossing it, as ``Deck`` records with ``datum =
    "design"``: the neck's faces keep their airside role and law — the
    taxiway surface runs across at the airside design surface — and under
    the deck the road is a bore under cover, not emitted."""
    ch = law.tables.structures.channel
    out: list[Deck] = []
    halves: list[tuple[float, float | None]] = []
    seen: list[tuple[float, float]] = []
    cap = ch.corridor_max_half_width_m
    spans: list[tuple[float, float, int]] = []
    for c in grp:
        # (1) (b) every PAVED NECK across the unpaved corridor
        for s0, s1 in c.necks:
            a, b = c.line.interpolate(s0), c.line.interpolate(s1)
            spans.append((axis_ln.project(Point(a.x, a.y)),
                          axis_ln.project(Point(b.x, b.y)), int(c.way.id)))
        # (1) (a) every taxied aeroway BRIDGE over the way: its own
        # carriageway across the crossing station (the neck the apt.dat
        # pavement would have drawn had the pack authored one)
        for _wid, s, half in c.bridges:
            p = c.line.interpolate(min(max(s, 0.0), c.line.length))
            t = axis_ln.project(Point(p.x, p.y))
            spans.append((t - half, t + half, int(c.way.id)))
    # (12) THE ROOFED PIECES ARE DECKS.  A witnessing placement's own
    # hard deck, cut into the pieces that cross the axis: LGAV's
    # `Trench_06` is a 4,077 x 149 m plate ROOFED OVER 6 % of its area,
    # so its roofed stretches are the crossings and the other 94 % is the
    # open trench.  The obj8 reader hands back the plate's HULL
    # (532,554 m2 at LGAV — the whole corridor), so a piece longer than
    # ``deck_max_width_m`` ALONG the axis is a roof, not a crossing, and
    # is refused by the same rule §45 (1) (b) applies to a paved neck.
    want = set(packs or ())
    for o in objects or ():
        if str(getattr(o, "id", "")) not in want:
            continue
        hd = getattr(o, "hard_deck", None)
        if hd is None or getattr(hd, "is_empty", True):
            continue
        for g in getattr(hd, "geoms", [hd]):
            if g.geom_type != "Polygon" or g.area <= 1.0:
                continue
            piece = axis_ln.intersection(g)
            for part in getattr(piece, "geoms", [piece]):
                if part.geom_type != "LineString" or part.length <= 1e-6:
                    continue
                a, b = part.coords[0], part.coords[-1]
                u0 = axis_ln.project(Point(a))
                u1 = axis_ln.project(Point(b))
                u0, u1 = (u0, u1) if u0 <= u1 else (u1, u0)
                if (u1 - u0) > ch.deck_max_width_m:
                    continue                # a roof along the axis, not a crossing
                spans.append((u0, u1, int(next(iter(grp)).way.id)))
    for t0, t1, wid in spans:
        t0, t1 = (t0, t1) if t0 <= t1 else (t1, t0)
        if any(t0 <= u1 + ch.station_m and t1 >= u0 - ch.station_m
               for u0, u1 in seen):
            continue
        seen.append((t0, t1))
        mid = (t0 + t1) / 2.0
        span = _span(union, axis_fn, mid, cap)
        halves.append((mid, span))
        ring = _deck_ring(axis_fn, t0, t1, span if span is not None else cap)
        out.append(Deck(ref=f"channel_deck:{cid.split(':')[-1]}#{len(out)}",
                        way=wid, s0=float(t0), s1=float(t1),
                        ring=ring, datum=CREST_DESIGN))
    return out, halves


def _floor(airport: Airport, law: Law, cid: str, grp: list[_Cand], axis_ln, axis_fn,
           ss: list[float], decks: list[Deck], half: float, objects: _t.Sequence,
           stats: ChannelStats, packs: _t.Sequence[str] = ()):
    """§45 (3) THE FLOOR DATUM — precedence, then "Cut the road down".

    (i) the pack's floor plates along the axis; (ii) a CREDIBLE lidar
    inset (the DTM floor at each station); (iii) neither: under each deck
    the floor is the deck top − ``bridge.clearance_m`` and between decks
    the road's own longitudinal law clamped ≤ that datum and
    ≤ ``ramp_max_grade``.  Returns ``(profile, datum, wall shape, witness)``.

    The clamp is stated as ``min over decks of (z_d + grade·|s − s_d|)``,
    which IS "≤ that datum and ≤ ramp_max_grade" written once: two decks
    closer than ``2 × clearance / ramp_max_grade`` keep the floor down
    between them (KPHX's two stand 58 m apart against a 127.5 m reach, so
    the road never climbs between the terminals)."""
    ch = law.tables.structures.channel
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    # the corridor's CREST estimate, used only to judge a pack witness's
    # depth and to report: the DEM along the axis outside the decks
    samples = [_dem(airport, axis_fn(s)) for s in ss]
    good = [z for z in samples if not math.isnan(z)]
    crest_est = (sum(good) / len(good)) if good else float("nan")

    # (i) THE PACK'S FLOOR PLATES — the SAME witness set the width (10)
    # (i) read, never a second read at a second radius
    packs = list(packs)
    floor_pack: float | None = None
    if packs:
        zs = [float(o.solid_min_z) for o in objects
              if str(getattr(o, "id", "")) in set(packs)
              and getattr(o, "solid_min_z", None) is not None]
        if zs:
            floor_pack = min(zs)
            for c in grp:
                c.witnesses.add(WITNESS_PACK)
            profile = tuple((float(s), float(floor_pack)) for s in (ss[0], ss[-1]))
            stats.notes.append(f"{cid}: floor from the pack (§45 (3) (i)) — "
                               f"{len(set(packs))} placement(s), deepest genuine solid "
                               f"{floor_pack:.2f} m against a crest of {crest_est:.2f}")
            return profile, DATUM_PACK, "face", ",".join(sorted(set(packs))[:4])

    # (ii) A CREDIBLE LIDAR INSET
    if _lidar_credible(airport, law):
        prof = []
        for s in ss:
            z = _lidar_floor(airport, axis_fn, s, ch.lidar_floor_window_m)
            if not math.isnan(z):
                prof.append((float(s), float(z)))
        if len(prof) >= 2:
            stats.notes.append(f"{cid}: floor from a CREDIBLE lidar inset (§45 (3) (ii)) — "
                               f"{len(prof)} station(s), "
                               f"{min(z for _s, z in prof):.2f}..{max(z for _s, z in prof):.2f} m "
                               f"under a crest of {crest_est:.2f}")
            return tuple(prof), DATUM_LIDAR, "lidar", "lidar inset"

    # (iii) CUT THE ROAD DOWN
    anchors: list[tuple[float, float]] = []
    for d in decks:
        mid = (d.s0 + d.s1) / 2.0
        top = _dem(airport, axis_fn(mid))
        if math.isnan(top):
            continue
        anchors.append((mid, top - br.clearance_m))
    if not anchors:
        stats.refused.append(f"{cid}: no deck top could be sampled — the DEM answers NaN "
                             f"at every crossing, so §45 (3) (iii) has no datum")
        return None, "", "bank", ""
    grade = tn.ramp_max_grade
    # THE DECK'S OWN STATION IS IN THE PROFILE.  Without it the datum
    # lands between two sampled stations and the floor reads the CLIMB's
    # value under the deck itself — measured on the twin: 95.30 against
    # the 94.90 the clearance states, one half-station of 8 % grade.
    stations = sorted(set(list(ss) + [sd for sd, _z in anchors]))
    prof = []
    for s in stations:
        prof.append((float(s), float(min(z + grade * abs(s - sd) for sd, z in anchors))))
    stats.notes.append(
        f"{cid}: floor by §45 (3) (iii) \"Cut the road down\" — deck top − "
        f"bridge.clearance_m {br.clearance_m:.1f} m at {len(anchors)} crossing(s), the road's "
        f"own law between them clamped at ramp_max_grade {grade:.0%}; "
        f"{min(z for _s, z in prof):.2f}..{max(z for _s, z in prof):.2f} m")
    return tuple(prof), DATUM_CLEARANCE, "bank", "bridge.clearance_m"


# ── the cells (§45 (8) EMISSION) ─────────────────────────────────────────

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
            floor = floor.difference(du)
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


