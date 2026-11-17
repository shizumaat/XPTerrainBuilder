"""THE GENERATED TAXIWAY DECK (spec ``docs/specs/2123.md`` Part A; owner
RULINGS 2026-11-16y; issue #2123).

A taxiway or runway that crosses over a road the pack draws only as
pavement (no hard-deck object, no trench) used to be a TERRAIN bridge
(RULINGS 2026-08-30d): the covered stretch between the mouths stood at
taxiway level and the road drew over it.  Where the crossing is a short
one, the app now makes the bridge itself: a deck OBJECT the object stage
writes into the airport's pack (``airport/generated_pack``), and here, at
planar time, the deck RECORD every hard-deck consumer already reads
(``model/structures.DeckBridge``, ``witness="generated"``) -- so the cut
under it, its floor, its banks, the ground it rests on and its end-line
anchors are the pack hard deck's own derivations (spec A3/A5), never a
second copy.

WHERE (spec A1; every threshold a ``[deck_gen]`` law key):

1. a road (or rail) the structure pass bores lies under TAXI- or
   RUNWAY-family pavement: a §34 (5) underpass bore
   (``structure_underpass.underpass_bores``) or a mapped tunnel way;
2. no pack deck, trench, portal, object corridor or object floor
   touches it -- the pack always wins;
3. every road under it is covered no longer than ``max_cover_m`` (Q2: a
   longer one is a TUNNEL, read on the road's own covered length);
4. the airport has a pack DSF to write the deck into (a Global Airports
   block alone is refused by name: RULINGS 16y (2)'s offer is its path).

THE RING (spec A2; #2131): ``C`` = the covered roads' carriageways, a
level floor ``shoulder_m`` beyond each edge and the bank's run to the crest
(:func:`_cut_reach`); ``R`` = (``P`` ∩ ``C`` ⊕ ``bearing_m``) ⊕ ``edge_margin_m``
(mitred), ``P`` the taxi/runway pavement.  Each connected piece of ``R``
is one deck.  Its END LINES are where the pavement runs onto it
(``airside_deck_seat.facing_contacts``, the pack deck's own reading).
THE TOP is one plane: level across the route, tilted along it by the DEM
just outside the end lines, clamped to ``tilt_cap_share`` of the family's
longitudinal cap.  THE FLOOR stands ``thickness_m + [tunnel]
clearance_m`` under the top (Q6).

Nothing here names an airport, a pack or a resource.  Build-time impact:
one shapely union per airport and a few facing-contact reads per deck
piece -- milliseconds; an airport with no covered road under its
taxiways returns at once.
"""
from __future__ import annotations

import hashlib
import math
import types
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union

from ..airport.airside_deck_seat import facing_contacts
from ..classify.roles import TAXI_FAMILY
from ..law.tables import role_cap
from ..model.structures import DeckBridge
from .deck_bridge import CellRoles, _deck_z, _end_pair, _routes_across, _taxi_at_both_ends
from .deck_route import carried_route
from .structure_approach import carriageway_width_m, is_tunnel, standing_cover
from .structure_underpass import underpass_bores

__all__ = ["generated_decks", "GENERATED_WITNESS", "GENERATED_DIR", "is_generated",
           "carried_off", "covers_bore"]

#: ``DeckBridge.witness`` of a generated deck
GENERATED_WITNESS = "generated"
#: where the object stage writes the generated decks in the pack
GENERATED_DIR = "objects/o4_generated"
_RUNWAY_FAMILY = ("runway", "runway_crossing")
XY = tuple[float, float]


def is_generated(db) -> bool:
    """A deck this module generated (no pack placement stands behind it)."""
    return getattr(db, "witness", "") == GENERATED_WITNESS


def covers_bore(db, line) -> bool:
    """#2131: ``db`` is a GENERATED deck and the bore ``line`` runs under it.
    The generator spans a road only where its whole cover is no longer than
    ``max_cover_m`` (A1 (3)), so every mapped end of that bore is the open
    cut's: the deck witnesses it (``planar/end_witness``) and takes its
    mouth however far the mapped end stands past the ring
    (``deck_bridge.deck_under``).  MEASURED ESSA ``-141`` (86 m tunnel, a
    36 m deck over it): its east end stood 6.8 m off the ring, beyond the
    pack deck's 5 m end tolerance -- refused, so the deck stood over no cut
    and neither road ramped down to it (owner 2026-11-17, 59.657084,
    17.950759)."""
    from .deck_bridge import deck_polygon
    return is_generated(db) and line.intersection(deck_polygon(db)).length > 1.0


class _Road(_t.NamedTuple):
    id: str
    tags: _t.Mapping[str, str]
    line: LineString
    covered_m: float
    half_m: float
    #: the mapped road a §34 (5) underpass piece was clipped from (``None``
    #: for a mapped tunnel): its stretch under the pavement is the cover
    parent: "LineString | None" = None


def _covered_roads(airport, law, classification) -> list[_Road]:
    """The roads the structure pass reads as COVERED (A1 (1)): every
    §34 (5) underpass piece and every mapped tunnel chain, with its
    covered length (the underpass piece, the tunnel chain) and its
    carriageway half width."""
    tn = law.tables.structures.tunnel
    cells, _gap, polys = standing_cover(classification)
    out: list[_Road] = []
    ways, parents, _notes = underpass_bores(airport, law, cells, polys)
    for w in ways:
        ln = LineString(w.points)
        out.append(_Road(str(w.id), dict(w.tags or {}), ln, ln.length,
                         carriageway_width_m(w.tags, law) / 2.0, parents.get(id(w))))
    tunnels = [w for w in getattr(airport, "osm_ways", ()) or ()
               if len(w.points) >= 2 and is_tunnel(w, tn.admitted_values)
               and any((w.tags or {}).get(k) for k in ("highway", "railway"))]
    for group in _connected(tunnels):
        merged = linemerge([LineString(w.points) for w in group])
        covered = sum(LineString(w.points).length for w in group)
        for g in getattr(merged, "geoms", [merged]):
            if g.geom_type != "LineString" or g.length < tn.underpass_min_span_m:
                continue
            w = max(group, key=lambda t: LineString(t.points).intersection(
                g.buffer(0.5)).length)
            out.append(_Road(str(w.id), dict(w.tags or {}), g, covered,
                             carriageway_width_m(w.tags, law) / 2.0))
    return out


def _connected(ways) -> list[list]:
    """The mapped tunnel ways in groups joined end to end: one TUNNEL, its
    covered length the whole group's (a rail tunnel mapped as many ways is
    one tunnel, however short the piece under a taxiway)."""
    from ..geom.union_find import find_root
    parent = list(range(len(ways)))
    ends: dict[tuple, int] = {}
    for i, w in enumerate(ways):
        for p in (w.points[0], w.points[-1]):
            k = (round(p[0], 1), round(p[1], 1))
            if k in ends:
                a, b = find_root(parent, i), find_root(parent, ends[k])
                parent[a] = b
            else:
                ends[k] = i
    groups: dict[int, list] = {}
    for i, w in enumerate(ways):
        groups.setdefault(find_root(parent, i), []).append(w)
    return list(groups.values())


def _road_chain(parent: LineString, lines, tree, reach: float) -> LineString:
    """``parent`` grown through every mapped road line (``lines``, indexed
    by ``tree``) joined to it end to end (OSM splits a road at a bridge),
    up to ``reach`` metres more each way -- the road the pavement covers,
    whichever way it is mapped as."""
    chain = parent
    for _ in range(8):
        ends = [Point(chain.coords[0]), Point(chain.coords[-1])]
        near = {int(j) for e in ends for j in tree.query(e.buffer(0.05))}
        grown = [lines[j] for j in sorted(near) if lines[j].length <= reach
                 and not lines[j].equals(chain)
                 and any(lines[j].distance(e) < 0.05 for e in ends)
                 and lines[j].difference(chain.buffer(0.05)).length > 0.5]
        if not grown:
            break
        merged = linemerge(unary_union([chain, *grown]))
        if merged.geom_type != "LineString":
            # a junction: keep the longest straight run through the parent
            merged = max((q for q in merged.geoms if q.distance(parent) < 0.05),
                         key=lambda q: q.length, default=chain)
        if merged.length <= chain.length + 0.5:
            break
        chain = merged
    return chain


def _whole_cover(roads, P, max_cover: float, ways=()) -> tuple[list, list[str]]:
    """Each underpass road's stretch under the pavement ``P`` -- the piece
    of its mapped road there holding the clip -- as its line and covered
    length; a road covered over ``max_cover`` is a tunnel and dropped."""
    from shapely.strtree import STRtree
    out, notes = [], []
    lines = [LineString(w.points) for w in ways]
    tree = STRtree(lines) if lines else None
    for r in roads:
        if r.parent is None or tree is None:
            out.append(r)
            continue
        chain = _road_chain(r.parent, lines, tree, max_cover)
        x = chain.intersection(P)
        mid = r.line.interpolate(0.5, normalized=True)
        # an EMPTY LineString is a LineString too (the chain missing the
        # pavement: KPHX's capture raised IndexError on its coords)
        parts = [q for q in getattr(x, "geoms", [x])
                 if q.geom_type == "LineString" and not q.is_empty]
        best = min(parts, key=lambda q: q.distance(mid), default=None)
        if best is None or best.distance(mid) > 1.0:
            out.append(r)
            continue
        # the chain from the first to the last of the clip and the cover
        from shapely.ops import substring
        ss = [chain.project(Point(q)) for g in (best, r.line) for q in (g.coords[0], g.coords[-1])]
        line = substring(chain, min(ss), max(ss))
        if line.geom_type != "LineString":
            line = r.line
        if line.length > max_cover:
            notes.append(f"covered road {r.id} {r.tags.get('highway')} {line.length:.1f} m "
                         f"under the pavement: a tunnel (over max_cover_m {max_cover:g} m, "
                         f"Q2) -- no generated deck")
            continue
        out.append(r._replace(line=line, covered_m=line.length))
    return out, notes


def _bank_run_m(law) -> float:
    """The run of the bank under a generated deck: its floor's depth (the
    slab plus ``[tunnel] clearance_m``, Q6) over ``emit.design.bank_slope``
    -- the bank ``planar/structures`` cuts from each end line down to the
    floor (``deck_bridge.deck_cut``), so the generator and the cut read one
    number."""
    g = law.tables.structures.deck_gen
    depth = float(g.thickness_m) + float(law.tables.structures.tunnel.clearance_m)
    return depth / float(law.tables.emit.design.bank_slope)


def _cut_reach(roads, law):
    """#2131 THE DECK SPANS ITS CUT (owner 2026-11-17: "the bridge objects
    need to be a bit longer, and the cuts wider"): per covered road its
    carriageway, the level floor ``shoulder_m`` beyond each edge, then the
    bank's run (:func:`_bank_run_m`) to the crest -- the plan the deck must
    cover so the floor under it carries the whole drawn road.  Round 1 read
    a 3 m bank to a 6 m deep floor: the 1:3 bank the cut builds from the end
    lines took the whole floor and the drawn road ran up it (ESSA U -74:
    0.58 m under the deck's edge)."""
    reach = float(law.tables.structures.deck_gen.shoulder_m) + _bank_run_m(law)
    return unary_union([r.line.buffer(r.half_m + reach, cap_style="flat") for r in roads])


def _deck_id(ring: Polygon) -> str:
    key = ";".join(f"{x:.1f},{y:.1f}" for x, y in ring.exterior.coords[:-1])
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def _ends_ground(airport, law, sa, sb) -> "tuple[float, float, float] | None":
    """``(ground at end A, at end B, A->B distance)``: per end-line station
    the HIGHEST DEM from ``tilt_probe_m`` to ``level_probe_m`` outside the
    deck along the route (a bare-earth DEM drops the bridge and reads the
    road's cut under it: the ground beside the cut is the taxiway's, #714's
    reading), averaged over the line."""
    g = law.tables.structures.deck_gen
    dem = getattr(airport, "dem", None)
    if dem is None:
        return None
    ca = (sum(p[0] for p in sa) / len(sa), sum(p[1] for p in sa) / len(sa))
    cb = (sum(p[0] for p in sb) / len(sb), sum(p[1] for p in sb) / len(sb))
    d = math.hypot(cb[0] - ca[0], cb[1] - ca[1])
    if d <= 1.0:
        return None
    ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
    steps = [float(g.tilt_probe_m) + 3.0 * k for k in range(
        int(max(0.0, float(g.level_probe_m) - float(g.tilt_probe_m)) / 3.0) + 1)]

    def ground(st, sign):
        per = []
        for x, y in st:
            zs = [float(dem.z(x + sign * ux * t, y + sign * uy * t)) for t in steps]
            zs = [z for z in zs if math.isfinite(z)]
            if zs:
                per.append(max(zs))
        return sum(per) / len(per) if per else None
    za, zb = ground(sa, -1.0), ground(sb, 1.0)
    return None if za is None or zb is None else (za, zb, d)


def _tilt(law, ends, roles: CellRoles, at, cap_role: str) -> float:
    """``top_b - top_a``: the ground's rise from end A to end B
    (:func:`_ends_ground`), clamped to ``tilt_cap_share`` x the family's
    longitudinal cap over the deck (A2)."""
    if ends is None:
        return 0.0
    za, zb, d = ends
    g = law.tables.structures.deck_gen
    cell_role = roles.at_xy(at) or cap_role
    rc = role_cap(law, cell_role if cell_role in (*TAXI_FAMILY, *_RUNWAY_FAMILY)
                  else cap_role)
    cap = float(rc.longitudinal) if rc is not None else 0.0
    span = d + 2.0 * float(g.level_probe_m)
    lim = float(g.tilt_cap_share) * cap * span
    return max(-lim, min(lim, zb - za)) * d / span


def _blocked(piece: Polygon, taken, blocked) -> str:
    from .deck_bridge import deck_polygon
    for db in taken:
        if deck_polygon(db).intersection(piece).area > 1.0:
            return f"the pack's deck {db.object_id} stands on it"
    for b in blocked:
        try:
            if b.intersection(piece).area > 1.0:
                return "a pack trench / corridor / floor stands on it"
        except Exception:                      # an invalid pack outline
            continue
    return ""


def _pack_refusal(airport) -> str:
    pack = getattr(airport, "pack", None)
    if pack is None or not getattr(pack, "dsf_paths", ()):
        return "the airport has no pack DSF to write the deck into (A1 (5))"
    apt = str(getattr(pack, "apt_dat_path", "") or "")
    if "global airports" in apt.replace("\\", "/").lower():
        return ("the airport is drawn by Global Airports alone: the app OFFERS to install "
                "its Gateway pack and modify it (RULINGS 2026-11-16y (2)); no deck here")
    return ""


def generated_decks(classification, airport, law, taken: _t.Sequence = (),
                    blocked: _t.Sequence = ()
                    ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(every generated deck, one note per deck or refusal)`` (module
    doc).  ``taken``: the pack's own hard decks (``deck_bridges``);
    ``blocked``: the pack's trench / corridor / floor outlines (frame)."""
    if classification is None or not classification.cells:
        return (), []
    g = law.tables.structures.deck_gen
    tn = law.tables.structures.tunnel
    fam = set(TAXI_FAMILY) | set(_RUNWAY_FAMILY)
    paved, refs = [], set()
    for c in classification.cells:
        if c.role in fam and len(c.ring) >= 3:
            p = Polygon(c.ring, c.holes)
            paved.append(p if p.is_valid else p.buffer(0.0))
            refs.add(str(c.ref))
    if not paved:
        return (), []
    # P is the AIRPORT'S pavement (apt.dat 110) the taxi / runway cells come
    # from: the classification cuts the road ribbons out of the taxiway they
    # pass under, which the deck spans (spec A2: "P = taxi/runway pavement
    # over C")
    for pv in getattr(airport, "pavements", ()) or ():
        if str(pv.id) in refs and len(pv.outer) >= 3:
            p = Polygon(pv.outer, [h for h in pv.holes if len(h) >= 3])
            paved.append(p if p.is_valid else p.buffer(0.0))
    P = unary_union(paved)
    notes: list[str] = []
    roads = []
    for r in _covered_roads(airport, law, classification):
        # the classification cuts a road's own ribbon out of the pavement
        # over it: the road is under the pavement within its half width
        if r.line.distance(P) > r.half_m + 1.0:
            continue
        if r.covered_m > float(g.max_cover_m):
            # A1 (3) / Q2: a TUNNEL -- it starts no deck, and never joins one
            notes.append(f"covered road {r.id} {r.tags.get('highway') or r.tags.get('railway')} "
                         f"{r.covered_m:.1f} m: a tunnel (over max_cover_m "
                         f"{float(g.max_cover_m):g} m, A1 (3) / Q2) -- no generated deck")
            continue
        roads.append(r)
    if not roads:
        return (), notes
    # the pavement OVER the roads: the classification cuts each road's own
    # ribbon out of the taxiway it passes under, so the pavement is closed
    # across a carriageway's width (near the roads only)
    w = max(r.half_m for r in roads) + float(g.shoulder_m) + 1.0
    near = unary_union([r.line.buffer(float(g.max_cover_m)) for r in roads])
    P = P.intersection(near).buffer(w, join_style="mitre").buffer(-w, join_style="mitre")
    # Q2 as ruled: an underpass piece is the clip the structure pass makes;
    # the road's COVER is its whole stretch under the pavement
    from .structure_underpass import bore_roads
    mapped = bore_roads(airport, law, rail=True)
    roads, long_notes = _whole_cover(roads, P, float(g.max_cover_m), mapped)
    notes += long_notes
    if not roads:
        return (), notes
    C = _cut_reach(roads, law)
    R = P.intersection(C.buffer(float(g.bearing_m))).buffer(
        float(g.edge_margin_m), join_style="mitre")
    roles = CellRoles(classification, airport)
    surface = types.SimpleNamespace(roles=roles)
    to_xy, to_ll = airport.frame.transformers()
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    refused_pack = _pack_refusal(airport)
    out: list[DeckBridge] = []
    for piece in sorted(getattr(R, "geoms", [R]), key=lambda q: -q.area):
        if piece.geom_type != "Polygon" or piece.area < float(g.min_area_m2):
            continue
        piece = Polygon(piece.exterior).simplify(0.05)
        under = [r for r in roads if r.line.intersection(piece).length > 1.0]
        if not under:
            continue
        c = piece.centroid
        where = f"generated deck at ({c.x:.0f}, {c.y:.0f}) {piece.area:,.0f} m2 over " \
                + ", ".join(f"{r.id} {r.tags.get('highway') or r.tags.get('railway')} "
                            f"{r.covered_m:.1f} m" for r in under)
        long_ = [r for r in under if r.covered_m > float(g.max_cover_m)]
        if long_:
            notes.append(f"{where}: REFUSED -- a tunnel, covered over max_cover_m "
                         f"{float(g.max_cover_m):g} m (A1 (3) / Q2)")
            continue
        why = _blocked(piece, taken, blocked) or refused_pack
        if why:
            notes.append(f"{where}: REFUSED -- {why}")
            continue
        road_dir = _mean_dir([r.line.intersection(piece) for r in under])

        def ends_of(pc, road_dir=road_dir):
            pairs = facing_contacts([to_ll(x, y) for x, y in pc.exterior.coords[:-1]],
                                    surface, step, every=True)
            return _end_pair(pairs, road_dir, to_xy, _routes_across(airport, pc)) \
                if pairs else None
        pair = ends_of(piece)
        for frac in (0.75, 0.5, 0.25, 0.0) if pair is None else ():
            # #2131: the carried pavement ends inside the bank's reach (a
            # taxiway between two aprons): the longest deck short of it
            short = _shortened(piece, under, P, law, frac)
            pair = ends_of(short) if short is not None else None
            if pair is not None:
                notes.append(f"{where}: the carried pavement ends inside the bank's reach "
                             f"-- the deck spans {100 * frac:.0f} % of the bank's run "
                             f"(#2131)")
                piece = short
                break
        if pair is None:
            notes.append(f"{where}: REFUSED -- no pavement runs across it (RULINGS "
                         f"2026-10-27c)")
            continue
        sa, sb = (_crest(tuple(to_xy(lo, la) for la, lo in e), road_dir) for e in pair)
        family, route, ref = carried_route(airport, piece)
        if family == "road" and _taxi_at_both_ends(sa, sb, roles):
            family = "taxi"
        if family == "road":
            notes.append(f"{where}: REFUSED -- no taxiway or runway runs across it")
            continue
        ends = _ends_ground(airport, law, sa, sb)
        rise = _tilt(law, ends, roles, sa[0], "runway" if family == "runway"
                     else "primary_parallel")
        top_a, top_b = 0.0, float(rise)
        depth = float(g.thickness_m) + float(tn.clearance_m)
        hid = _deck_id(piece)
        approach = _approaches(piece, under, P, mapped, law)
        main = max(under, key=lambda r: r.line.intersection(piece).length)
        x = main.line.intersection(piece)
        road = tuple(x.coords) if x.geom_type == "LineString" else ()
        out.append(DeckBridge(
            f"o4gen_{hid}", f"{GENERATED_DIR}/deck_{hid}.obj", (),
            tuple(piece.exterior.coords[:-1]), sa, sb, top_a, top_b,
            min(top_a, top_b) - depth,
            0.5 * (ends[0] + ends[1]) if ends else float(_deck_z(airport, sa + sb, 0.0) or 0.0),
            walls=(), floor_min_m=depth, witness=GENERATED_WITNESS, family=family,
            route=route, route_ref=ref, road=road,
            covered=tuple((r.id, tuple(sorted(r.tags.items())), tuple(r.line.coords))
                          for r in under),
            approach=tuple(tuple(q.exterior.coords[:-1]) for q in approach)))
        notes.append(f"{where}: GENERATED o4gen_{hid} ({family}, rise {rise:+.2f} m "
                     f"A->B, floor {depth:.1f} m under the top; spec 2123 A1)"
                     + (f"; {sum(q.area for q in approach):,.0f} m2 of pack pavement over "
                        f"its open approaches leaves them (#2131)" if approach else ""))
    return tuple(out), notes


def _shortened(piece: Polygon, under, P, law, frac: float) -> "Polygon | None":
    """``piece`` reaching only ``frac`` of the bank's run past its roads'
    floors (:func:`_cut_reach`), as the ring is drawn (``bearing_m``,
    ``edge_margin_m``); ``None`` where nothing of a deck is left."""
    g = law.tables.structures.deck_gen
    reach = float(g.shoulder_m) + frac * _bank_run_m(law)
    C = unary_union([r.line.buffer(r.half_m + reach, cap_style="flat") for r in under])
    R = P.intersection(C.buffer(float(g.bearing_m))).buffer(
        float(g.edge_margin_m), join_style="mitre").intersection(piece)
    parts = [q for q in getattr(R, "geoms", [R]) if q.geom_type == "Polygon"
             and q.area >= float(g.min_area_m2)]
    if not parts:
        return None
    return Polygon(max(parts, key=lambda q: q.area).exterior).simplify(0.05)


def _approaches(piece: Polygon, under, P, mapped, law) -> list[Polygon]:
    """#2131 THE APPROACHES ARE OPEN: the pack pavement ``P`` laid over a
    MAPPED TUNNEL's road past the deck's ring (the corridor, where pavement
    lies over it) -- the tunnel's own stretch
    beyond it and, from each mapped end (OSM states the portal; the road
    runs open from there), the first stretch of every mapped road
    leaving that end, up to the design ramp's run (the floor's depth over
    ``[tunnel] ramp_grade``), at the ramp's width (carriageway,
    ``shoulder_m``, the rim's stand-off), leaves with the deck's ring -- so
    the ramp climbs out instead of standing at a wall where the pavement
    starts (#2072 A's dead end).  MEASURED ESSA ``-141``: ``pav24``'s taxiway
    junction lay over ``-58`` for 40 m west of the portal, the road visible
    in the photo; the cut stopped there.  An underpass piece's road is
    covered wherever ``P`` lies over it (:func:`_whole_cover`): it has no
    approach pavement to leave."""
    from shapely.ops import substring
    g = law.tables.structures.deck_gen
    tn = law.tables.structures.tunnel
    run = (float(g.thickness_m) + float(tn.clearance_m)) / float(tn.ramp_grade)
    out = []
    for r in under:
        if r.parent is not None:
            continue
        # the ramp's outer edge (carriageway, shoulder, rim stand-off), the
        # stand-off a stop is read at (``structures._pad_hit``'s gap) and the
        # deck's own bearing and edge margin (a sliver of the cell the ring cut
        # stood 9.6 m off -141's axis at its portal and stopped the ramp there)
        wide = r.half_m + float(g.shoulder_m) + 2.0 * float(tn.wall_gap_m) \
            + float(tn.wall_band_width_m) + float(g.bearing_m) + float(g.edge_margin_m)
        # the tunnel's own stretch past the ring, then each road leaving its ends
        open_ = [r.line]
        for end in (Point(r.line.coords[0]), Point(r.line.coords[-1])):
            for w in mapped:
                ln = LineString(w.points)
                if Point(ln.coords[0]).distance(end) < 0.5:
                    open_.append(substring(ln, 0.0, min(ln.length, run)))
                elif Point(ln.coords[-1]).distance(end) < 0.5:
                    ln = LineString(ln.coords[::-1])
                    open_.append(substring(ln, 0.0, min(ln.length, run)))
        # round caps: the tunnel and the road leaving its end meet at an
        # angle, and two flat caps leave a wedge of pavement at the portal.
        # The whole corridor where pavement lies over it: ``P`` is read off
        # the taxi family, and a cross-connector's sliver at the portal is
        # pavement too (the knife cuts the rolled-on cells only)
        corridor = unary_union([q.buffer(wide) for q in open_]).difference(piece)
        out += [q for q in getattr(corridor, "geoms", [corridor])
                if q.geom_type == "Polygon" and q.intersection(P).area > 1.0]
    return out


#: an end-line edge within this of the road's direction lies on the crest
_CREST_TURN_DEG = 20.0


def _crest(stations: tuple, road_dir: "XY | None") -> tuple:
    """#2131: a generated deck's END LINE is its cut's crest -- parallel to
    the road by construction (:func:`_cut_reach`) -- so of the stations where
    the pavement runs onto the ring, the longest run along edges within
    ``_CREST_TURN_DEG`` of the road.  The rest turn the ring's mitred corner
    (MEASURED ESSA -3077: the corner stations tilted the end line 30 deg and
    the bank band cut from it took half the floor; 52 % of the road's
    carriageway on the floor).  The stations unchanged where no run of two
    lies on it."""
    if road_dir is None or len(stations) < 3:
        return stations
    cos_t = math.cos(math.radians(_CREST_TURN_DEG))
    runs, cur = [], [stations[0]]
    for p, q in zip(stations[:-1], stations[1:], strict=True):
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        if d > 1e-9 and abs((q[0] - p[0]) * road_dir[0] + (q[1] - p[1]) * road_dir[1]) / d >= cos_t:
            cur.append(q)
        else:
            runs.append(cur)
            cur = [q]
    runs.append(cur)
    best = max(runs, key=lambda r: math.hypot(r[-1][0] - r[0][0], r[-1][1] - r[0][1]))
    return tuple(best) if len(best) >= 2 else stations


def _mean_dir(pieces) -> "XY | None":
    sx = sy = 0.0
    for x in pieces:
        for gg in getattr(x, "geoms", [x]):
            if gg.geom_type != "LineString" or gg.length <= 1.0:
                continue
            (x0, y0), (x1, y1) = gg.coords[0], gg.coords[-1]
            if (x1 - x0) * sx + (y1 - y0) * sy < 0.0:
                x0, y0, x1, y1 = x1, y1, x0, y0
            sx, sy = sx + x1 - x0, sy + y1 - y0
    n = math.hypot(sx, sy)
    return None if n <= 1.0 else (sx / n, sy / n)


def carried_off(classification, decks, law) -> tuple[_t.Any, list[str]]:
    """``classification`` with the airside pavement each GENERATED deck
    carries cut out of its cells (A3: the deck is the pavement there, as a
    pack deck's apt.dat leaves a hole under its object; the object stage
    cuts the same region out of the pack's apt.dat).  The ground under the
    ring is then the corridors' and the deck's own
    (``deck_bridge.deck_ground``)."""
    import dataclasses as _dc

    from ..law.tables import rolled_on_roles
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon
    gen = [d for d in decks if is_generated(d)]
    if not gen or classification is None:
        return classification, []
    knife = unary_union([deck_polygon(d) for d in gen]
                        + [Polygon(q) for d in gen for q in d.approach if len(q) >= 3])
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    air = rolled_on_roles(law)
    cells, n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                           mark="generated_deck_cut", cuts=lambda c: c.role in air)
    return (_dc.replace(classification, cells=tuple(cells)),
            [f"generated decks: {n} airside cell(s) cut under {len(gen)} deck ring(s) "
             f"(spec 2123 A3)"])
