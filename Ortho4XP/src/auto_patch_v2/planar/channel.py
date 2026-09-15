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
from .structure_approach import carriageway_width_m, is_bridge, is_tunnel, unit
from .structure_underpass import is_aeroway_bridge

__all__ = ["ChannelStats", "identify_channels", "channel_cells",
           "channel_ways", "channel_yields", "in_any_corridor",
           "FLOOR_ROLE", "WALL_ROLE",
           "WITNESS_BRIDGE", "WITNESS_NECK", "WITNESS_PACK"]

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

def _is_road_or_rail(w: OsmWay, law: Law) -> bool:
    tags = getattr(w, "tags", None) or {}
    if len(w.points) < 2:
        return False
    if is_bridge(w):
        return False           # a bridge way is the CROSSING, not the channel
    return bool(tags.get("highway") or tags.get("railway"))


def channel_ways(channels: _t.Sequence[Channel]) -> set[int]:
    """Every OSM way id any channel owns — the set ``build_structures``
    subtracts from its bore seeds (§45 (1): "A crossing inside a channel
    is NEVER a bore with mouths")."""
    return {int(i) for c in channels for i in c.ways}


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
    owned = channel_ways(channels)
    kept: list[OsmWay] = []
    for w in tunnel_ways:
        cid = "" if int(w.id) in owned else in_any_corridor(channels, LineString(w.points))
        if int(w.id) in owned or cid:
            refused.append(
                f"osm:{w.id}: inside {cid or 'its own'} channel corridor — the channel's "
                f"floor governs it and a crossing inside a channel is NEVER a bore with "
                f"mouths (§45 (1)/(6))")
            continue
        kept.append(w)
    cors = [c for c in corridors
            if not in_any_corridor(channels, getattr(c, "footprint", None))]
    grps = [g for g in extra_groups
            if not in_any_corridor(channels,
                                   getattr(getattr(g, "corridor", None), "footprint", None))]
    return kept, cors, grps


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


def _hole_region(union):
    """THE HOLE IN THE AIRSIDE PAVEMENT (§45 (1) (b)) — the pavement
    union's own interiors: the filled outline LESS the pavement.

    This is what separates a CHANNEL from a service road that merely
    crosses a taxiway spur.  KDFW's corridor IS a hole — ``ring69`` of
    the single 339-node outer pavement, 2,518 m x ~1,150 m, with the four
    taxiway necks bridging it (scout `channelscout` §4a).  A road running
    OUTSIDE the field and crossing one taxiway leaves the pavement into
    open ground, not into a hole the airfield cut for it.  Measured at
    LGAV on the first arm: without this clause the neck test read five
    channels, four of them service roads."""
    if union is None:
        return None
    shells = []
    for g in getattr(union, "geoms", [union]):
        if g.geom_type != "Polygon":
            continue
        shells.append(Polygon(g.exterior))
    if not shells:
        return None
    filled = unary_union(shells)
    holes = filled.difference(union)
    return None if holes.is_empty else holes


def _runs(flags: _t.Sequence[bool]) -> list[tuple[bool, int, int]]:
    """``[(value, i0, i1)]`` — maximal runs of equal flags, i1 inclusive."""
    out: list[tuple[bool, int, int]] = []
    for i, f in enumerate(flags):
        if out and out[-1][0] == f:
            out[-1] = (f, out[-1][1], i)
        else:
            out.append((f, i, i))
    return out


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


def _in_hole(ln: LineString, ss: list[float], run, holes) -> bool:
    """Whether an UNPAVED run of a way lies inside the pavement's own
    hole (:func:`_hole_region`) — tested at the run's midpoint, which is
    the deepest point of the corridor beside the neck."""
    if holes is None:
        return False
    _v, i0, i1 = run
    p = ln.interpolate((ss[i0] + ss[i1]) / 2.0)
    return bool(holes.contains(Point(p.x, p.y)))


def _aeroway_bridges(airport: Airport, law: Law) -> list[tuple[OsmWay, LineString]]:
    """§45 (1) (a): every taxied aeroway tagged ``bridge`` at or above
    ``[tunnel] underpass_min_layer`` — ONE predicate with §34 (5)'s
    (:func:`structure_underpass.is_aeroway_bridge`), never a second copy."""
    tn = law.tables.structures.tunnel
    out = []
    for w in airport.osm_ways:
        tags = getattr(w, "tags", None) or {}
        if not is_aeroway_bridge(tags) or len(w.points) < 2:
            continue
        try:
            layer = int(float(str(tags.get("layer", "0")).strip()))
        except ValueError:
            layer = 0
        if layer < tn.underpass_min_layer:
            continue
        out.append((w, LineString(w.points)))
    return out


def _pack_witnesses(cand: _Cand, objects: _t.Sequence, half_m: float,
                    crest_est: float, min_depth_m: float) -> list[str]:
    """§45 (1) (c): the pack's wall / floor objects along the axis.

    The 05k-1 authority — seat = floor, plate = crest, hull = footprint —
    read through the placement reading the basin pass already made
    (``planar/basins.read_objects``), so nothing re-parses an OBJ8.  A
    placement whose plan runs inside the corridor band and whose deepest
    GENUINE solid stands ``object_min_depth_m`` under the corridor's
    crest is the channel's witness.  It is NOT a basin seed, a sunken
    road, a tunnel-object corridor or a door well (§45 (7))."""
    band = cand.line.buffer(half_m, **_MITRE)
    out: list[str] = []
    for o in objects or ():
        # THE FOOTPRINT, NOT THE BBOX.  ``plan_bbox`` is the resource's
        # plan EXTENT, so one sprawling terminal matches every band on
        # the field: measured at LGAV on the first arm, five separate
        # channels all read the same 63.43 m "floor" off objects nowhere
        # near their axes.  The below-grade footprint is the geometry the
        # basin pass itself admits a pit on.
        bb = getattr(o, "below_grade", None) or getattr(o, "plan_bbox", None)
        z = getattr(o, "solid_min_z", None)
        if bb is None or z is None:
            continue
        try:
            if not band.intersects(bb):
                continue
        except Exception:                     # pragma: no cover
            continue
        if math.isnan(crest_est) or (crest_est - float(z)) < min_depth_m:
            continue
        out.append(str(getattr(o, "id", "")))
    return out


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
                      objects: _t.Sequence = ()) -> tuple[list[Channel], ChannelStats]:
    """THE CHANNEL RECORDS (§45 (1)–(7)), derived ONCE.

    Order, exactly as the brief's ORDER OF WORK ruled it: the
    hole-and-neck read of the apt.dat pavement union (1) (b) is the FIRST
    witness — it is free at all three airports and depends on neither
    OSM's tags, the DEM nor a pack — then ``bridge=yes`` (1) (a), then the
    pack's wall / floor objects (1) (c)."""
    stats = ChannelStats()
    ch = law.tables.structures.channel
    tn = law.tables.structures.tunnel
    br = law.tables.structures.bridge
    union = _pavement_union(airport)
    holes = _hole_region(union)
    cands: list[_Cand] = []
    for w in airport.osm_ways:
        if not _is_road_or_rail(w, law):
            continue
        c = _read_way(w, law, union, holes)
        if c is None:
            continue
        if c.necks:
            c.witnesses.add(WITNESS_NECK)
        cands.append(c)
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
    groups = _merge(live, ch.merge_m)
    channels: list[Channel] = []
    for k, grp in enumerate(groups):
        c = _build_one(airport, law, f"channel:{k}", grp, union, objects, stats)
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


def _merge(cands: list[_Cand], merge_m: float) -> list[list[_Cand]]:
    """Union-find over "within ``merge_m`` in plan" OR "sharing a
    crossing way"."""
    parent = list(range(len(cands)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            near = cands[i].line.distance(cands[j].line) <= merge_m
            shared = ({b[0] for b in cands[i].bridges}
                      & {b[0] for b in cands[j].bridges})
            if near or shared:
                join(i, j)
    out: dict[int, list[_Cand]] = {}
    for i, c in enumerate(cands):
        out.setdefault(find(i), []).append(c)
    return list(out.values())


def _build_one(airport: Airport, law: Law, cid: str, grp: list[_Cand], union,
               objects: _t.Sequence, stats: ChannelStats) -> Channel | None:
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

    # ── the corridor's half-width (§45 (1)'s precedence) ───────────────
    # the CARRIAGEWAYS ⊕ lane_width_m — the floor of every reading: every
    # member way's lateral offset from the axis, plus its own width
    lateral = 0.0
    for c in grp:
        for p in c.line.coords:
            s = axis_ln.project(Point(p))
            a = axis_fn(s)
            lateral = max(lateral, math.hypot(p[0] - a[0], p[1] - a[1]))
    widest = max(carriageway_width_m(c.way.tags, law) for c in grp)
    half_base = lateral + widest / 2.0 + tn.lane_width_m
    # ── THE CORRIDOR'S HALF-WIDTH, and the lane's ONE DEVIATION ────────
    # §45 (1) reads it off the HOLE first ("the hole's two edges are the
    # corridor edges").  MEASURED, and REPORTED not decided: at KDFW —
    # the only one of the three sites where the cut is measured at all —
    # the hole is 2,518 x ~1,150 m, the whole gap between the terminal
    # horseshoes, while the 1 m 3DEP DTM reads the cut 84.3-105.8 m wall
    # to wall at the six bridges (scout `channelscout` §2a/§4a).  Taking
    # the hole would cut a kilometre-wide trench across the middle of
    # DFW.  The width here is therefore the LAST of §45 (1)'s four —
    # the carriageways (+) ``lane_width_m``, with the banks of (5)
    # beyond it — raised toward the hole only as far as
    # ``corridor_max_half_width_m`` allows.  It can only UNDER-cut.
    decks, deck_half = _decks(airport, law, cid, grp, axis_ln, axis_fn, union)
    cap = ch.corridor_max_half_width_m
    seen_half = [h for _s, h in deck_half if h is not None and h <= cap]
    half_at = min(cap, max([half_base] + seen_half))
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

    # ── (3) THE FLOOR DATUM, in the ruled precedence ───────────────────
    profile, datum, wall_shape, witness_name = _floor(
        airport, law, cid, grp, axis_ln, axis_fn, ss, decks, half_at, objects, stats)
    if profile is None:
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
    to_ll = airport.frame.transformers()[1]

    def ll(p: XY) -> tuple[float, float]:
        la, lo_ = to_ll(p[0], p[1])
        return (round(la, 7), round(lo_, 7))

    notes = [f"{cid}: {len(grp)} way(s) within [channel] merge_m {ch.merge_m:.0f} m share the "
             f"corridor; axis {axis_ln.length:.0f} m, ends {ends[0]:.0f}..{ends[1]:.0f} m; "
             f"corridor half-width {half_at:.1f} m (carriageways ⊕ lane_width_m "
             f"{half_base:.1f} m, decks "
             f"{', '.join(f'{h:.1f}' for _s, h in deck_half if h is not None) or 'none'}); "
             f"bank {bank:.1f} m "
             f"at 1:{1.0 / ch.bank_slope:.0f}",
             f"{cid}: NO MOUTH (§45 (6)) — the ways are the channel's, never a bore's; "
             f"the mouth_standoff_m field test, the §29 cockpit tests and the "
             f"`ramp_crosses_pad` refusal are MOUTH rules and are not applied here"]
    return Channel(
        id=cid,
        ways=tuple(int(c.way.id) for c in grp),
        axis=tuple(axis_fn(s) for s in ss),
        profile=profile,
        widths=widths,
        decks=tuple(decks),
        walls=walls,
        ends=ends,
        witnesses=tuple(wits),
        datum_source=datum,
        crest=CREST_DESIGN,
        bank_slope=float(ch.bank_slope),
        floor_ref=f"channel_floor:{cid.split(':')[-1]}",
        wall_ref=f"channel_wall:{cid.split(':')[-1]}",
        region=region,
        crest_ring=crest_ring,
        region_ll=tuple(ll(p) for p in region),
        profile_ll=tuple((*ll(axis_fn(s)), float(z)) for s, z in profile),
        notes=tuple(notes))


def _wits(grp: list[_Cand]) -> set[str]:
    out: set[str] = set()
    for c in grp:
        out |= c.witnesses
    return out


def _decks(airport: Airport, law: Law, cid: str, grp: list[_Cand], axis_ln, axis_fn,
           union) -> tuple[list[Deck], list[tuple[float, float]]]:
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


def _span(union, axis_fn, s: float, reach: float) -> float | None:
    """How far the pavement reaches ACROSS the axis at ``s``, on the
    NARROWER side — the neck's own across-axis extent, which §45 (1) (b)
    calls the deck's span.  ``None`` where the ray finds no pavement edge
    within ``reach``: the caller then keeps the carriageway width and
    never invents a span out of the search radius (the first arm returned
    ``reach`` and read a 480 m half-corridor at LGAV)."""
    if union is None:
        return None
    p = axis_fn(s)
    a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
    u = unit(a, b)
    nv = (-u[1], u[0])
    best: float | None = None
    for sgn in (1.0, -1.0):
        ray = LineString([p, (p[0] + nv[0] * sgn * reach, p[1] + nv[1] * sgn * reach)])
        x = ray.intersection(union.boundary)
        pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
        if not pts:
            return None
        d = min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts)
        best = d if best is None else min(best, d)
    return None if best is None else max(1.0, best)


def _deck_ring(axis_fn, s0: float, s1: float, half: float) -> tuple[XY, ...]:
    left, right = _sides(axis_fn, [s0, s1], half)
    return tuple(left) + tuple(reversed(right))


def _sides(axis_fn, ss: _t.Sequence[float], half: float) -> tuple[list[XY], list[XY]]:
    left: list[XY] = []
    right: list[XY] = []
    for s in ss:
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        left.append((p[0] + nv[0] * half, p[1] + nv[1] * half))
        right.append((p[0] - nv[0] * half, p[1] - nv[1] * half))
    return left, right


def _floor(airport: Airport, law: Law, cid: str, grp: list[_Cand], axis_ln, axis_fn,
           ss: list[float], decks: list[Deck], half: float, objects: _t.Sequence,
           stats: ChannelStats):
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

    # (i) THE PACK'S FLOOR PLATES
    packs: list[str] = []
    floor_pack: float | None = None
    for c in grp:
        ids = _pack_witnesses(c, objects, half, crest_est, ch.object_min_depth_m)
        packs.extend(ids)
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


def _lidar_floor(airport: Airport, axis_fn, s: float, window_m: float) -> float:
    """§45 (3) (ii): the DTM floor at one station — the MINIMUM across
    ``lidar_floor_window_m`` on the axis normal.  The bank toes stand
    inside the corridor (KDFW's run 1:4 over 35–45 m) and the floor is
    what lies between them, so a single centreline sample would read a
    bank wherever the carriageway is not the deepest line."""
    p = axis_fn(s)
    a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
    u = unit(a, b)
    nv = (-u[1], u[0])
    best = float("nan")
    k = max(2, int(window_m // 2.0))
    for i in range(-k, k + 1):
        t = i * (window_m / (2.0 * k))
        z = _dem(airport, (p[0] + nv[0] * t, p[1] + nv[1] * t))
        if math.isnan(z):
            continue
        best = z if math.isnan(best) else min(best, z)
    return best


def _bank_width(airport: Airport, axis_fn, ss, profile, slope: float, shape: str,
                grid: float) -> float:
    """The bank's PLAN run, one value for the channel (§45 (5)).

    ``"face"`` — a pack wall stands here and the bank hides behind it at
    the identity spacing (near-vertical AT the face, §24 (1)); ``"lidar"``
    / ``"bank"`` — ``(crest − floor) / bank_slope``, sized off the DEM so
    the mesh has room.  The crest's VALUE is never the DEM (§45 (5)); this
    is plan geometry only."""
    if shape == "face":
        return max(grid, 1.0)
    from ..model.structures import profile_z
    drops = []
    for s in ss:
        z = _dem(airport, axis_fn(s))
        if math.isnan(z):
            continue
        drops.append(max(0.0, z - profile_z(profile, s)))
    drop = max(drops) if drops else 0.0
    return max(grid, drop / max(slope, 1e-6))


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


def _poly(ring) -> Polygon | None:
    if not ring or len(ring) < 3:
        return None
    p = Polygon(list(ring))
    if not p.is_valid:
        p = p.buffer(0)
    if p.is_empty:
        return None
    if p.geom_type != "Polygon":
        parts = [g for g in p.geoms if g.geom_type == "Polygon"]
        if not parts:
            return None
        p = max(parts, key=lambda g: g.area)
    return p


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    import shapely
    return [g for g in shapely.get_parts(geom)
            if g.geom_type == "Polygon" and g.area > 1e-6]
