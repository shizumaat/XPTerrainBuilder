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
is cut into ONE DECK PER TAXI ROUTE across it at the route's class width,
taxiway plus shoulders (owner RULINGS 2026-11-19s (3) (b), (4) (c);
``planar/deck_width``).  Its END LINES are where the pavement runs onto it
(``airside_deck_seat.facing_contacts``, the pack deck's own reading; else
its own ends, ``deck_width.route_ends``).  THE PRE-SOLVE TOP (``top_a`` /
``top_b``, the planar consumers' estimate) is one plane: level across the
route, tilted along it by the DEM just outside the end lines, clamped to
``tilt_cap_share`` of the family's longitudinal cap; the BUILT top is the
no-bridge airside over the ring (RULINGS 2026-11-19s (1): stage 1 withholds
the deck, ``planar/deck_airside``; ``constraints/deck_floor_follow`` reads
the surface).  THE FLOOR stands ``thickness_m + [tunnel]
clearance_m`` under the top (Q6) -- 4.2 m (``[bridge] clearance_minimum_m``)
over a small road (owner 2026-11-17T19:08Z, ``structure_approach.
design_clearance_m``).

Nothing here names an airport, a pack or a resource.  Build-time impact:
one shapely union per airport and a few facing-contact reads per deck
piece -- milliseconds; an airport with no covered road under its
taxiways returns at once.
"""
from __future__ import annotations

import hashlib
import math
import re
import types
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..airport.airside_deck_seat import facing_contacts
from ..classify.roles import TAXI_FAMILY
from ..law.tables import role_cap
from ..model.deck_bank import deck_bank_slope
from ..model.structures import GENERATED_WITNESS, DeckBridge, is_generated
from .deck_bridge import CellRoles, _deck_z, _end_pair, _routes_across, _taxi_at_both_ends
from .deck_gen_cover import bridge_ribbons, covered_state, distinct_ways, union_with
from .deck_gen_pairs import one_bridge, one_cut, riders
from .deck_route import carried_route
from .structure_approach import carriageway_width_m, design_clearance_m, is_tunnel, standing_cover
from .structure_underpass import underpass_bores

__all__ = ["generated_decks", "GENERATED_WITNESS", "GENERATED_DIR", "is_generated",
           "carried_off", "covers_bore", "GLOBAL_OFFER", "global_only"]

#: the refusal of a structure the airport's Global Airports entry cannot
#: carry: every note ending in it is an OFFER candidate (#2169; RULINGS
#: 2026-11-16y (2)) that ``gateway_stage`` reads off the publication
GLOBAL_OFFER = ("the airport is drawn by Global Airports alone: the app OFFERS to install "
                "its Gateway pack and modify it (RULINGS 2026-11-16y (2))")

#: where the object stage writes the generated decks in the pack
GENERATED_DIR = "objects/o4_generated"
_RUNWAY_FAMILY = ("runway", "runway_crossing")
XY = tuple[float, float]


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
    # #2181: a piece read from two tiles' extracts is one road
    for w in distinct_ways(ways):
        ln = LineString(w.points)
        out.append(_Road(str(w.id), dict(w.tags or {}), ln, ln.length,
                         carriageway_width_m(w.tags, law) / 2.0, parents.get(id(w))))
    # #2181: a tunnel read from two tiles' extracts is ONE tunnel
    tunnels = distinct_ways([w for w in getattr(airport, "osm_ways", ()) or ()
                             if len(w.points) >= 2 and is_tunnel(w, tn.admitted_values)
                             and any((w.tags or {}).get(k) for k in ("highway", "railway"))])
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
    out, notes = [], []
    # #2181 (``deck_gen_cover`` rule 1): the cover grows only through the
    # pieces OSM maps in the state of the piece under the deck
    ways = distinct_ways(ways)
    by_state: dict = {}
    for st in (False, True):
        ls = [LineString(w.points) for w in ways if covered_state(getattr(w, "tags", None)) == st]
        by_state[st] = (ls, STRtree(ls) if ls else None)
    lines = [LineString(w.points) for w in ways]
    tree = STRtree(lines) if lines else None
    for r in roads:
        if r.parent is None or tree is None:
            out.append(r)
            continue
        state = _parent_state(r, ways)
        if not state and _beside_covered(r.parent, *by_state[True]):
            # #2181: OSM maps the road covered on, and open here -- the
            # stretch between two bridges is open sky (``deck_gen_cover``)
            notes.append(f"road {r.id} {r.tags.get('highway') or r.tags.get('railway')} is "
                         f"mapped open where it joins a covered piece: open sky between "
                         f"the bridges, no deck over it (#2181 item 1)")
            continue
        st_lines, st_tree = by_state[state]
        if st_tree is None:
            out.append(r)
            continue
        chain = _road_chain(r.parent, st_lines, st_tree, max_cover)
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


def _beside_covered(parent: LineString, lines, tree) -> bool:
    """A mapped COVERED line (``deck_gen_cover.covered_state``) joins
    ``parent`` end to end."""
    if tree is None:
        return False
    for e in (Point(parent.coords[0]), Point(parent.coords[-1])):
        for j in tree.query(e.buffer(0.05)):
            ln = lines[int(j)]
            if not ln.equals(parent) and any(Point(q).distance(e) < 0.05
                                             for q in (ln.coords[0], ln.coords[-1])):
                return True
    return False


def _parent_state(r: _Road, ways) -> bool:
    """The cover state OSM maps the road an underpass piece was clipped
    from in (``deck_gen_cover.covered_state``): its own way's tags (the
    piece's carry the bore's ``tunnel``)."""
    # by the line, never the id: a twin from another tile's extract was
    # dropped (``distinct_ways``) and carries another id
    for w in ways:
        if len(w.points) >= 2 and LineString(w.points).equals_exact(r.parent, 0.05):
            return covered_state(getattr(w, "tags", None))
    return False


def _depth_m(law, roads) -> float:
    """A generated deck's floor depth under its top: the slab plus the
    clearance its covered ``roads`` need (Q6;
    ``structure_approach.design_clearance_m``, owner 2026-11-17T19:08Z: 4.2 m
    over a small road, ``[tunnel] clearance_m`` over the rest) -- the
    largest of them."""
    clear = max((design_clearance_m(r.tags, law) for r in roads),
                default=float(law.tables.structures.tunnel.clearance_m))
    return float(law.tables.structures.deck_gen.thickness_m) + clear


def _bank_run_m(law, roads) -> float:
    """The run of the bank under a generated deck: its floor's depth
    (:func:`_depth_m`) over the bank slope under a generated deck
    (``model/deck_bank.deck_bank_slope``, every bridge's, RULINGS
    2026-11-17p) -- the bank ``planar/structures`` cuts from each end line
    down to the floor (``deck_bridge.deck_cut``), so the generator and the
    cut read one number."""
    return _depth_m(law, roads) / deck_bank_slope(law)


def _cut_reach(roads, law, depth: "_t.Mapping[str, float] | None" = None):
    """#2131 THE DECK SPANS ITS CUT (owner 2026-11-17: "the bridge objects
    need to be a bit longer, and the cuts wider"): per covered road its
    carriageway, the level floor ``shoulder_m`` beyond each edge, then the
    bank's run (:func:`_bank_run_m`) to the crest -- the plan the deck must
    cover so the floor under it carries the whole drawn road.  Round 1 read
    a 3 m bank to a 6 m deep floor: the 1:3 bank the cut builds from the end
    lines took the whole floor and the drawn road ran up it (ESSA U -74:
    0.58 m under the deck's edge).  ``depth``: a road's floor depth by id
    where it shares a deck with a road needing more clearance
    (:func:`_shared_depths`), else its own (:func:`_depth_m`)."""
    sh = float(law.tables.structures.deck_gen.shoulder_m)
    slope = deck_bank_slope(law)
    return unary_union([r.line.buffer(
        r.half_m + sh + (depth or {}).get(r.id, _depth_m(law, (r,))) / slope, cap_style="flat")
        for r in roads])


def _shared_depths(roads, law, R) -> dict[str, float]:
    """Per road id the floor depth of the deck piece of ``R`` it runs under:
    one deck has ONE floor, the deepest its roads need (:func:`_depth_m`) --
    a small road beside a motorway under one deck is cut to the motorway's
    floor, and its bank reaches as far (owner 2026-11-17T19:08Z: 4.2 m for
    small roads, a deck over both keeps the larger)."""
    out: dict[str, float] = {}
    for piece in getattr(R, "geoms", [R]):
        under = [r for r in roads if r.line.intersects(piece)]
        d = _depth_m(law, under) if under else 0.0
        for r in under:
            out[r.id] = max(out.get(r.id, 0.0), d)
    return out


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


def _blocked(piece: Polygon, taken, blocked, axes=(), packs=(), law=None,
             why_of=lambda _i: "", roads=()) -> str:
    from .deck_bridge import deck_polygon
    from .deck_pack_cover import pack_refusal
    for db in taken:
        if deck_polygon(db).intersection(piece).area > 1.0:
            return f"the pack's deck {db.object_id} stands on it"
    for b in blocked:
        try:
            if b.intersection(piece).area > 1.0:
                return "a pack trench / corridor / floor stands on it"
        except Exception:                      # an invalid pack outline
            continue
    return pack_refusal(piece, axes, packs, law, why_of, roads,
                        _approach_run_m(law)) if packs else ""


def _approach_run_m(law) -> float:
    """The stretch a covered road runs in the generated cut past the ring:
    the floor's depth (the slab plus ``[tunnel] clearance_m``, Q6) over
    ``[tunnel] ramp_grade`` -- the approach ramp's run (:func:`_approaches`)."""
    g = law.tables.structures.deck_gen
    tn = law.tables.structures.tunnel
    return (float(g.thickness_m) + float(tn.clearance_m)) / float(tn.ramp_grade)


def global_only(airport) -> bool:
    """X-Plane draws the airport from its Global Airports entry: the app
    never writes there, it offers the Gateway pack (RULINGS 16y (2))."""
    apt = str(getattr(getattr(airport, "pack", None), "apt_dat_path", "") or "")
    return "global airports" in apt.replace("\\", "/").lower()


def _pack_refusal(airport) -> str:
    # #2169: a Global Airports entry is named FIRST, DSF or not -- its
    # refusal is the offer's candidate, never "no pack DSF"
    if global_only(airport):
        return GLOBAL_OFFER
    pack = getattr(airport, "pack", None)
    if pack is None or not getattr(pack, "dsf_paths", ()):
        return "the airport has no pack DSF to write the deck into (A1 (5))"
    return ""


def generated_decks(classification, airport, law, taken: _t.Sequence = (),
                    blocked: _t.Sequence = (), objects: _t.Sequence = (), cache=None,
                    deck_notes: _t.Sequence[str] = (), covered: _t.Sequence = ()
                    ) -> tuple[tuple[DeckBridge, ...], list[str]]:
    """``(every generated deck, one note per deck or refusal)`` (module
    doc).  ``taken``: the pack's own hard decks (``deck_bridges``);
    ``blocked``: the pack's trench / corridor / floor outlines (frame);
    ``objects`` / ``cache``: the pack read, whose own hard decks and tops
    refuse a piece whether ``deck_bridges`` admitted them or not
    (``planar/deck_pack_cover``); ``deck_notes``: its notes, naming why;
    ``covered``: more covered roads (:class:`_Road`) -- those under a pack
    frame the build hid (``planar/deck_takeover``: its bridges stated the
    crossing, as a hard deck bores its road, ``planar/deck_bores``)."""
    if classification is None or not classification.cells:
        return (), []
    g = law.tables.structures.deck_gen
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
    # #2183 item 4 (``deck_gen_cover`` rule 3): a mapped aeroway bridge over
    # the pack's hole under its own bridge object is pavement for the deck
    ribbons, rib_notes = bridge_ribbons(P, airport, law)
    P = union_with(P, ribbons)
    notes += rib_notes
    roads = []
    for r in _covered_roads(airport, law, classification) + list(covered):
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
    # #2183 item 4: a deck over a pack's hole spans the hole, pavement to
    # pavement -- its end lines stand where the pavement runs on
    R = _over_holes(R, ribbons, g)
    # #2181 (``deck_gen_pairs`` rule 3): one mapped bridge, one deck
    from .structure_underpass import aeroway_decks
    aero = [LineString(a.points) for a in aeroway_decks(airport, law)]
    R = one_bridge(R, aero)
    shared = _shared_depths(roads, law, R)
    if any(abs(d - _depth_m(law, (r,))) > 1e-9 for r in roads if (d := shared.get(r.id))):
        # a deck over roads of two clearances: each bank reaches the deck's floor
        C = _cut_reach(roads, law, shared)
        R = one_bridge(_over_holes(P.intersection(C.buffer(float(g.bearing_m))).buffer(
            float(g.edge_margin_m), join_style="mitre"), ribbons, g), aero)
    roles = CellRoles(classification, airport)
    surface = types.SimpleNamespace(roles=roles)
    from ..law.tables import rolled_on_roles
    from .deck_width import route_ends
    _rolled = rolled_on_roles(law)

    def pave(r) -> bool:
        return bool(r) and r in _rolled
    to_xy, to_ll = airport.frame.transformers()
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    refused_pack = _pack_refusal(airport)
    from .deck_pack_cover import overhead_decks, pack_decks_near
    # (c) RULINGS 2026-11-17n: a pack hard deck beside a piece, over its
    # road within the approach run, refuses it too (``deck_pack_cover``)
    packs = pack_decks_near(objects, cache, law, R,
                            deck_region=R.buffer(_approach_run_m(law)))

    def why_of(oid: str) -> str:
        own = re.compile(re.escape(oid) + r"(?![0-9])")
        return next((n for n in deck_notes if own.search(n)), "")
    out: list[DeckBridge] = []
    for piece in _route_pieces(R, roads, airport, law, notes,
                               lambda xy: pave(roles.at_xy(xy))):
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
        # #2181 item 2: a pack deck standing a road's clearance over the
        # carried pavement passes OVER the crossing (``overhead_decks``)
        over = overhead_decks(objects, cache, piece, _carried_level(airport, piece), law)
        why = _blocked(piece, [d for d in taken if not (over & {d.object_id, *d.members})],
                       blocked, [r.line for r in under],
                       [p for p in packs if p.object_id not in over], law,
                       why_of, [r.parent or r.line for r in under]) or refused_pack
        if over and not why:
            clear = float(law.tables.structures.bridge.clearance_minimum_m)
            notes.append(f"{where}: the pack's {', '.join(sorted(over))} stand(s) over the "
                         f"crossing (top {clear:g} m or more over the pavement): no refusal "
                         f"(#2181 item 2)")
        if why:
            notes.append(f"{where}: REFUSED -- {why}")
            continue
        road_dir = _mean_dir([r.line.intersection(piece) for r in under])
        # #2181 item 1 / #2183 item 5: a road bridge beside the deck rides it
        piece, rides, ride_notes = riders(
            piece, P.intersection(piece), {r.id for r in under},
            getattr(airport, "road_bridges", ()) or (), law)
        notes += [f"{where}: {n}" for n in ride_notes]
        piece = _straight_sided(piece, road_dir,
                               _route_dir(carried_route(airport, piece)[1], piece))

        def ends_of(pc, road_dir=road_dir):
            pairs = facing_contacts([to_ll(x, y) for x, y in pc.exterior.coords[:-1]],
                                    surface, step, every=True)
            got = _end_pair(pairs, road_dir, to_xy, _routes_across(airport, pc)) \
                if pairs else None
            # a deck at its class width inside a wider pavement meets pavement
            # all round: its ends are its own edges along the road
            return got if got is not None else route_ends(pc, road_dir, roles.at_xy, pave,
                                                          step, to_ll)
        pair = ends_of(piece)
        for frac in (0.75, 0.5, 0.25, 0.0) if pair is None else ():
            # #2131: the carried pavement ends inside the bank's reach (a
            # taxiway between two aprons): the longest deck short of it
            short = _shortened(piece, under, P, law, frac)
            short = _straight_sided(short, road_dir, _route_dir(
                carried_route(airport, short)[1], short)) if short is not None else None
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
        depth = _depth_m(law, under)
        hid = _deck_id(piece)
        approach = _approaches(piece, under, P, mapped, law)
        main = max(under, key=lambda r: r.line.intersection(piece).length)
        x = main.line.intersection(piece)
        road = tuple(x.coords) if x.geom_type == "LineString" else ()
        from .deck_pack_cover import faked_cuts
        fakes = faked_cuts(piece, packs, law)
        out.append(DeckBridge(
            f"o4gen_{hid}", f"{GENERATED_DIR}/deck_{hid}.obj", (),
            tuple(piece.exterior.coords[:-1]), sa, sb, top_a, top_b,
            min(top_a, top_b) - depth,
            0.5 * (ends[0] + ends[1]) if ends else float(_deck_z(airport, sa + sb, 0.0) or 0.0),
            walls=(), floor_min_m=depth, witness=GENERATED_WITNESS, family=family,
            route=route, route_ref=ref, road=road,
            covered=tuple((r.id, tuple(sorted(r.tags.items())), tuple(r.line.coords))
                          for r in under),
            approach=tuple(tuple(q.exterior.coords[:-1]) for q in approach),
            hides=tuple((f.object_id, f.resource, tuple(reversed(to_ll(*f.xy))))
                        for f in fakes),
            hidden_plans=tuple(tuple(q.exterior.coords[:-1]) for f in fakes
                               for q in getattr(f.plan, "geoms", [f.plan])
                               if q.geom_type == "Polygon"),
            riders=rides))
        notes.append(f"{where}: GENERATED o4gen_{hid} ({family}, rise {rise:+.2f} m "
                     f"A->B, floor {depth:.1f} m under the top; spec 2123 A1)"
                     + (f"; {sum(q.area for q in approach):,.0f} m2 of pack pavement over "
                        f"its open approaches leaves them (#2131)" if approach else "")
                     + "".join(f"; the pack's {f.object_id} ({f.resource}) only fakes the cut "
                               f"(drawn under the terrain): hidden in the pack copy"
                               for f in fakes))
    out, pair_notes = one_cut(out, mapped, law, lambda tags: _reach_of(tags, law))
    return tuple(out), notes + pair_notes


def _route_pieces(R, roads, airport, law, notes: list[str], pave_at=None) -> list[Polygon]:
    """Each piece of ``R`` (the pavement over the cut) as ONE DECK PER
    TAXI ROUTE across it, at the route's class width (owner RULINGS
    2026-11-19s (3) (b), (4) (c); ``planar/deck_width``) -- never the
    pavement's width; a piece no taxi route crosses (a runway's) as read."""
    from .deck_width import route_decks
    g = law.tables.structures.deck_gen
    out: list[Polygon] = []
    for piece in sorted(getattr(R, "geoms", [R]), key=lambda q: -q.area):
        if piece.geom_type != "Polygon" or piece.area < float(g.min_area_m2):
            continue
        piece = Polygon(piece.exterior).simplify(0.05)
        under = [r for r in roads if r.line.intersection(piece).length > 1.0]
        decks = route_decks(piece, _mean_dir([r.line.intersection(piece) for r in under]),
                            airport, law, pave_at)
        c = piece.centroid
        notes += [f"generated deck piece at ({c.x:.0f}, {c.y:.0f}): {n}" for _p, n in decks]
        out += [p for p, _n in decks if p.area >= float(g.min_area_m2)] or [piece]
    return out


def _carried_level(airport, piece: Polygon) -> "float | None":
    """The carried pavement's level over ``piece``: the HIGHEST ground on
    its ring -- the ring stands on the pavement beside the cut, and a
    bare-earth survey reads the cut under it (#2181 item 2; a mean read
    the cut and took KRDU's own ``STH_TML.obj`` taxiway deck, 4 m over it,
    for a structure passing over the crossing)."""
    dem = getattr(airport, "dem", None)
    if dem is None:
        return None
    zs = [float(dem.z(x, y)) for x, y in piece.exterior.coords]
    zs = [z for z in zs if math.isfinite(z)]
    return max(zs) if zs else None


def _over_holes(R, ribbons, g):
    """``R`` with every hole ribbon (``deck_gen_cover.bridge_ribbons``) it
    reaches, grown by the ring's ``edge_margin_m``."""
    hit = [rb.buffer(float(g.edge_margin_m), join_style="mitre") for rb in ribbons
           if rb.intersects(R)]
    return unary_union([R, *hit]) if hit else R


def _reach_of(tags, law) -> float:
    """A road's cut reach either side of its axis under a generated deck
    (:func:`_cut_reach`'s: carriageway, shoulder, the bank's run)."""
    from ..model.deck_bank import deck_bank_slope
    r = _Road("", tags, LineString(), 0.0, carriageway_width_m(tags, law) / 2.0)
    return r.half_m + float(law.tables.structures.deck_gen.shoulder_m) \
        + _depth_m(law, (r,)) / deck_bank_slope(law)


def _shortened(piece: Polygon, under, P, law, frac: float) -> "Polygon | None":
    """``piece`` reaching only ``frac`` of the bank's run past its roads'
    floors (:func:`_cut_reach`), as the ring is drawn (``bearing_m``,
    ``edge_margin_m``); ``None`` where nothing of a deck is left."""
    g = law.tables.structures.deck_gen
    reach = float(g.shoulder_m) + frac * _bank_run_m(law, under)
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
    out = []
    for r in under:
        if r.parent is not None:
            continue
        run = _depth_m(law, under) / float(tn.ramp_grade)
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


def _straight_sided(piece: Polygon, road_dir: "XY | None",
                   route_dir: "XY | None" = None) -> Polygon:
    """THE DECK HAS STRAIGHT SIDES (owner sim read 2026-11-17T19:42Z: "I
    think probably sticking with straight sides makes sense for now"): the
    quadrilateral that holds the whole ``piece`` with two sides along the
    road under it (its end lines, the cut's crests) and two along the
    carried route (``route_dir``; across the road where none is given or it
    runs within 20 deg of the road) -- never the pavement ring's notches.
    An oblique crossing is a parallelogram: a rectangle square to the road
    took in the pack's service-road pavement beside the taxiway, never cut
    (MEASURED ESSA ``o4gen_07971284``, 5.7 m).  ``piece`` itself without a
    road direction."""
    if road_dir is None or piece.is_empty:
        return piece
    ux, uy = road_dir
    wx, wy = -uy, ux
    if route_dir is not None and abs(route_dir[0] * ux + route_dir[1] * uy) \
            < math.cos(math.radians(_CREST_TURN_DEG)):
        wx, wy = route_dir
    det = ux * wy - uy * wx
    ab = [((x * wy - y * wx) / det, (ux * y - uy * x) / det) for x, y in piece.exterior.coords]
    a0, a1 = min(a for a, _b in ab), max(a for a, _b in ab)
    b0, b1 = min(b for _a, b in ab), max(b for _a, b in ab)
    return Polygon([(a * ux + b * wx, a * uy + b * wy)
                    for a, b in ((a0, b0), (a1, b0), (a1, b1), (a0, b1))])


def _route_dir(route, piece: Polygon) -> "XY | None":
    """The carried route's direction where it crosses ``piece`` (its
    segment nearest the centroid); ``None`` for none."""
    if len(route) < 2:
        return None
    c = piece.centroid
    seg = min(zip(route[:-1], route[1:], strict=True),
              key=lambda st: LineString(st).distance(c))
    dx, dy = seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]
    n = math.hypot(dx, dy)
    return None if n <= 1e-9 else (dx / n, dy / n)


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
    (``deck_bridge.deck_ground``).

    THE CLEAN CUT (walled-multibridge-frames spec W8): the same knife takes
    the airside pavement inside every WALLED pack deck's span cut -- its rim
    strip (``deck_bridge._walled_trench``) inside its ring -- so the faces
    under a span are the trench's only, never a taxiway or apron cell over
    the floor (MEASURED KORD I-190: 12 / 7 pavement vertices inside the two
    spans' floor strips)."""
    import dataclasses as _dc

    from ..law.tables import rolled_on_roles
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon, walled_span_cuts
    gen = [d for d in decks if is_generated(d)]
    spans = [g for _oid, g in walled_span_cuts(
        decks, float(law.tables.structures.tunnel.wall_gap_m))]
    if not (gen or spans) or classification is None:
        return classification, []
    knife = unary_union([deck_polygon(d) for d in gen]
                        + [Polygon(q) for d in gen for q in d.approach if len(q) >= 3]
                        + spans)
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    air = rolled_on_roles(law)
    cells, n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                           mark="generated_deck_cut", cuts=lambda c: c.role in air)
    return (_dc.replace(classification, cells=tuple(cells)),
            [f"generated decks: {n} airside cell(s) cut under {len(gen)} deck ring(s) "
             f"(spec 2123 A3) and {len(spans)} walled span(s) (walled frames W8)"])
