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

THE RING (spec A2): ``C`` = the covered roads' carriageways plus their
banks; ``R`` = (``P`` ∩ ``C`` ⊕ ``bearing_m``) ⊕ ``edge_margin_m``
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
           "carried_off"]

#: ``DeckBridge.witness`` of a generated deck
GENERATED_WITNESS = "generated"
#: where the object stage writes the generated decks in the pack
GENERATED_DIR = "objects/o4_generated"
_RUNWAY_FAMILY = ("runway", "runway_crossing")
XY = tuple[float, float]


def is_generated(db) -> bool:
    """A deck this module generated (no pack placement stands behind it)."""
    return getattr(db, "witness", "") == GENERATED_WITNESS


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
        parts = [q for q in getattr(x, "geoms", [x]) if q.geom_type == "LineString"]
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
    C = unary_union([r.line.buffer(r.half_m + float(g.bank_m), cap_style="flat")
                     for r in roads])
    # the pavement OVER the roads: the classification cuts each road's own
    # ribbon out of the taxiway it passes under, so the pavement is closed
    # across a carriageway's width (near the roads only)
    w = max(r.half_m for r in roads) + float(g.bank_m) + 1.0
    near = unary_union([r.line.buffer(float(g.max_cover_m)) for r in roads])
    P = P.intersection(near).buffer(w, join_style="mitre").buffer(-w, join_style="mitre")
    # Q2 as ruled: an underpass piece is the clip the structure pass makes;
    # the road's COVER is its whole stretch under the pavement
    from .structure_underpass import bore_roads
    roads, long_notes = _whole_cover(roads, P, float(g.max_cover_m),
                                     bore_roads(airport, law, rail=True))
    notes += long_notes
    if not roads:
        return (), notes
    C = unary_union([r.line.buffer(r.half_m + float(g.bank_m), cap_style="flat")
                     for r in roads])
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
        ring_ll = [to_ll(x, y) for x, y in piece.exterior.coords[:-1]]
        pairs = facing_contacts(ring_ll, surface, step, every=True)
        road_dir = _mean_dir([r.line.intersection(piece) for r in under])
        pair = _end_pair(pairs, road_dir, to_xy, _routes_across(airport, piece)) \
            if pairs else None
        if pair is None:
            notes.append(f"{where}: REFUSED -- no pavement runs across it (RULINGS "
                         f"2026-10-27c)")
            continue
        sa, sb = (tuple(to_xy(lo, la) for la, lo in e) for e in pair)
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
                          for r in under)))
        notes.append(f"{where}: GENERATED o4gen_{hid} ({family}, rise {rise:+.2f} m "
                     f"A->B, floor {depth:.1f} m under the top; spec 2123 A1)")
    return tuple(out), notes


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
    knife = unary_union([deck_polygon(d) for d in gen])
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
