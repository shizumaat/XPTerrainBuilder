"""THE CUT IS THE DECK'S (owner 2026-11-19T23:07Z: "When we insert a
bridge, we know the size and shape of the cut needed to provide the
clearance under it, whether there's OSM or not, if we have the evidence to
insert a bridge then we have to add the cut to the patch"; 23:09Z: "If we
insert a bridge, we need the cut, and the cut needs to grade smoothly away
from the bridge back to the natural terrain"; RULINGS 2026-11-19s (2)-(4)).

Every GENERATED deck of the full map (``planar/deck_generated``) mints its
own cut in the patch, ribbon or not, mapped road or not:

* ITS ONE CUT (:func:`_deck_paths`; owner 2026-11-20T00:33Z: "a single
  cut, not multiple parallel ones"): a trench the deck's full width,
  along its most senior covered road or rail (``DeckBridge.covered``) on
  its own line, chained on along its mapped OSM path (straight on where
  the map ends) as far as its ramp can need (:func:`_reach_m`), spanning
  the deck between its end lines (``CarvePath.span``); with none mapped,
  the cut's own axis -- the deck's road line, else along its end lines.
  Every road under the deck lies on its floor (``CarvePath.need``).
* ITS STRETCHES: the stretch of the path under every generated deck it
  passes (the ring grown by the bank's run-on): two parallel taxiways'
  decks closer than a ramp up and back down are one cut at full depth
  between them (``geom/carve_profile.merged``, 19s (3) (b)).
* THE SURVEYED GROUND along each path (``airport.dem``, the lidar road).
* ITS CELLS (:func:`deck_carve`): the floor (the carriageway and its
  shoulders, ``[deck_gen] shoulder_m``), the banks out to the estimated
  daylight line at the deck bank's slope (``model/deck_bank``), and the
  ground under the ring and its opened approaches -- ``graded_strip``
  faces under :data:`~..model.deck_carve.CARVE_REF`, cut out of every
  groundside cell they cross (never airside pavement, a runway, a
  structure, a building pad or a road ribbon, whose vertices stage 2
  levels where they stand).

Stage 2 levels them (``constraints/deck_carve``): the floor at
``min(lidar road floor, underside - clearance)`` under the deck, ramping
back along the path at the grade cap with vertical curves until it meets
the terrain, the banks at 1V:1.5H, each abutment's embankment from the
pavement.  Never on stage 1's map (its generated decks are withheld,
``planar/deck_airside``): the carve never moves airside.

Nothing here names an airport.  Build-time impact: per generated deck a
few hundred DEM samples, one small LP per path and a shapely knife.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..geom.carve_profile import PathFrame, floor_profile, smoothed
from ..geom.exact import hypot
from ..geom.parts import densified_parts, polygon_parts_with_area
from ..model.deck_bank import bank_past_m, deck_bank_slope
from ..model.deck_carve import CARVE_REF, CarvePath, DeckCarve, floor_band
from ..model.road_clearance import carriageway_width_m, design_clearance_m
from ..model.structures import is_generated

__all__ = ["deck_carve"]

#: the surveyed ground is read along a path this often (m)
STEP_M = 2.0
#: the cut's cells are noded along their edges this often (m)
NODE_M = 4.0
#: ... and along every generated deck's ring this often (m), so each deck's
#: floor is sampled under its own ring (KJFK 1.0.565 ``o4gen_a900c332``: a
#: 35 m triangle from the neighbour's ramp stood 0.15 m over its floor)
RING_NODE_M = 2.0
#: a cell edge this near a deck's ring runs along it (m)
_RING_BAND_M = 0.5
#: a mapped road continues a path when it leaves within this of its end (m)
_JOIN_M = 1.0
#: ... turning no more than this off the path's heading (cosine)
_JOIN_COS = 0.7
#: the ramp's reach is read with this much more depth than the estimate (m)
_DEPTH_MARGIN_M = 2.0
#: ... and runs this much past it (m)
_REACH_MARGIN_M = 20.0
#: a carve piece this thin is a seam of the overlay, not ground (m)
_HAIR_M = 0.3

XY = tuple[float, float]


def _carve_law(law, kind: str) -> tuple[float, float]:
    """``(cap, rate)`` of a ``road`` / ``rail`` / ``axis`` path: the road's
    ramp cap (``[tunnel] ramp_max_grade``) or the rail grade (``[tunnel]
    rail_ramp_grade``, 1.25 %), and its vertical curve's grade change per
    metre (``law.tables.road_steep_law``)."""
    from ..law.tables import road_steep_law
    rs = road_steep_law(law)
    if kind == "rail":
        return float(rs["rail_cap"]), float(rs["rail_grade_change_per_m"])
    return float(law.tables.structures.tunnel.ramp_max_grade), float(rs["grade_change_per_m"])


#: the road classes by seniority (a railway outranks them all)
_SENIORITY = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
              "residential", "service")


def _rank(tags: _t.Mapping[str, str]) -> int:
    """How senior a covered way is: a railway first, then its road class."""
    if (tags or {}).get("railway"):
        return len(_SENIORITY) + 1
    hw = str((tags or {}).get("highway", "")).replace("_link", "")
    return len(_SENIORITY) - _SENIORITY.index(hw) if hw in _SENIORITY else 0


def _kind(tags: _t.Mapping[str, str]) -> str:
    return "rail" if (tags or {}).get("railway") else "road"


def _road_lines(airport) -> tuple[list, "STRtree | None"]:
    """Every mapped road and railway line of the airport's OSM (never an
    aeroway), with its index."""
    lines = [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
             if len(w.points) >= 2 and any((w.tags or {}).get(k) for k in ("highway", "railway"))
             and not (w.tags or {}).get("aeroway")]
    return lines, (STRtree(lines) if lines else None)


def _onward(end: Point, heading: XY, lines, tree) -> "LineString | None":
    """The mapped line leaving ``end`` most nearly along ``heading``."""
    if tree is None:
        return None
    best, best_cos = None, _JOIN_COS
    for j in tree.query(end.buffer(_JOIN_M)):
        ln = lines[int(j)]
        if ln.distance(end) > _JOIN_M:
            continue
        t = ln.project(end)
        for piece in (substring(ln, t, ln.length), substring(ln, 0.0, t)):
            if piece.geom_type != "LineString" or piece.length < 1.0:
                continue
            c = list(piece.coords)
            if Point(c[-1]).distance(end) < Point(c[0]).distance(end):
                c.reverse()
            far = LineString(c).interpolate(min(5.0, LineString(c).length))
            dx, dy = far.x - end.x, far.y - end.y
            n = hypot(dx, dy)
            if n < 1e-6:
                continue
            cos = (dx * heading[0] + dy * heading[1]) / n
            if cos > best_cos:
                best, best_cos = LineString(c), cos
    return best


def _grow(coords: list[XY], reach: float, lines, tree) -> list[XY]:
    """``coords`` grown from its LAST point along the mapped road for
    ``reach`` metres (straight on past the map's end)."""
    out = list(coords)
    left = reach
    for _ in range(16):
        if left <= 0.0:
            break
        (x0, y0), (x1, y1) = out[-2], out[-1]
        n = max(hypot(x1 - x0, y1 - y0), 1e-9)
        heading = ((x1 - x0) / n, (y1 - y0) / n)
        nxt = _onward(Point(x1, y1), heading, lines, tree)
        if nxt is None:
            out.append((x1 + heading[0] * left, y1 + heading[1] * left))
            return out
        piece = substring(nxt, 0.0, min(left, nxt.length))
        pc = list(piece.coords)[1:]
        if not pc:
            break
        out.extend(pc)
        left -= piece.length
    return out


def _extended(line: LineString, reach: float, lines, tree) -> LineString:
    """``line`` chained on along its mapped road ``reach`` metres past each end."""
    c = [tuple(p) for p in line.coords]
    c = _grow(c, reach, lines, tree)
    c = list(reversed(_grow(list(reversed(c)), reach, lines, tree)))
    return LineString(c).simplify(0.05)


def _axis(db) -> "LineString | None":
    """The cut's own axis with no road mapped: the deck's road line, else
    a line through the ring along its end lines (parallel to the road)."""
    from .deck_bridge import deck_polygon
    ring = deck_polygon(db)
    if len(getattr(db, "road", ()) or ()) >= 2:
        ln = LineString(db.road)
    elif len(db.seats_a) >= 2:
        ln = LineString([db.seats_a[0], db.seats_a[-1]])
    else:
        return None
    (x0, y0), (x1, y1) = ln.coords[0], ln.coords[-1]
    n = max(hypot(x1 - x0, y1 - y0), 1e-9)
    c = ring.centroid
    u = ((x1 - x0) / n, (y1 - y0) / n)
    h = 0.5 * hypot(*(ring.bounds[2] - ring.bounds[0], ring.bounds[3] - ring.bounds[1]))
    return LineString([(c.x - u[0] * h, c.y - u[1] * h), (c.x + u[0] * h, c.y + u[1] * h)])


def _reach_m(db, law, cap: float, rate: float) -> float:
    """How far past the deck a path is chained: the ramp from the deck's
    floor (its estimated top less the slab and clearance, with margin) to
    the top at ``cap``, its two vertical curves, a margin; at most
    ``[tunnel] max_ramp_length_m``."""
    tn = law.tables.structures.tunnel
    depth = float(db.floor_min_m) + _DEPTH_MARGIN_M
    run = depth / max(cap, 1e-6) + cap / max(rate, 1e-9) + _REACH_MARGIN_M
    return min(run, float(tn.max_ramp_length_m))


def _stretches(frame: PathFrame, line: LineString, decks, past: float
               ) -> list[tuple[float, float, str]]:
    """``(s0, s1, deck id)`` of the path under each generated deck's ring
    grown by ``past``."""
    from .deck_bridge import deck_polygon
    out = []
    for d in decks:
        x = line.intersection(deck_polygon(d).buffer(past, join_style="mitre"))
        pts = [p for g in getattr(x, "geoms", [x]) if not g.is_empty
               for p in getattr(g, "coords", [])]
        if len(pts) < 2 or x.length < 1.0:
            continue
        s, _n = frame.project([p[0] for p in pts], [p[1] for p in pts])
        out.append((float(s.min()), float(s.max()), d.object_id))
    return out


def _terrain(frame: PathFrame, dem) -> tuple[tuple[float, float], ...]:
    """``(s, z)`` of the surveyed ground every :data:`STEP_M` along the path."""
    n = max(2, int(frame.length / STEP_M) + 1)
    out = []
    for k in range(n):
        s = frame.length * k / (n - 1)
        (x, y), _u = frame.at(s)
        try:
            z = float(dem.z(x, y))
        except Exception:      # noqa: BLE001 -- off the DEM: no ground read here
            continue
        if z == z:
            out.append((round(s, 3), round(z, 3)))
    return tuple(out)


def _estimate_floor(db, terrain, s0: float, s1: float, clearance: float, law) -> float:
    """The planar estimate of the floor under ``db`` (stage 2 re-reads it
    from the solved top, ``constraints/deck_carve``): the deeper of the
    lidar road -- its lowest survey within ``[deck_gen] level_probe_m`` of
    the stretch, the road open past the bridge -- and the pre-solve top
    less the slab and clearance."""
    probe = float(law.tables.structures.deck_gen.level_probe_m)
    under = [z for s, z in terrain if s0 - probe <= s <= s1 + probe]
    slab = float(law.tables.structures.deck_gen.thickness_m)
    design = float(db.deck_z) - slab - clearance
    return min([design] + under)


def _covered_roads(db) -> list[tuple[str, str, dict, LineString]]:
    """``(way, kind, tags, line)`` of every road or rail under ``db``, each
    way once (a way read twice: two tiles' extracts)."""
    out, seen = [], set()
    for way, tags_items, coords in getattr(db, "covered", ()) or ():
        if str(way) in seen or len(coords) < 2:
            continue
        seen.add(str(way))
        tags = dict(tags_items)
        out.append((str(way), _kind(tags), tags, LineString(coords)))
    return out


def _senior(roads, rings) -> "tuple | None":
    """The most senior of ``roads`` (rail first, then the road class), the
    tie broken by its length under ``rings`` (every deck of the cut)."""
    if not roads:
        return None
    return max(roads, key=lambda r: (_rank(r[2]), round(sum(r[3].intersection(g).length
                                                            for g in rings))))


def _deck_paths(db, decks, airport, law, lines=None, tree=None, main=None) -> DeckCarve:
    """The cut's record for the generated deck ``db`` (module doc):
    ONE trench (owner 2026-11-20T00:33Z: "The cut is the full width of the
    bridge regardless of what roads or rails pass under it, a single cut,
    not multiple parallel ones") along the deck's main covered road -- its
    mapped path chained on past the deck (:func:`_past_every_deck`) -- or,
    with none mapped, the cut's own axis, centred between the deck's end
    lines; every road or rail under it lies on its one floor.
    ``decks``: every generated deck of the map (the stretches); ``main``:
    the ``(way, kind, tags, line)`` the cut runs along where it is shared
    with other decks (:func:`_shared_mains`)."""
    from .deck_bridge import deck_polygon
    from .structure_underpass import aeroway_decks
    if lines is None:
        lines, tree = _road_lines(airport)
    past = bank_past_m(law)
    sh = float(law.tables.structures.deck_gen.shoulder_m)
    tn = law.tables.structures.tunnel
    ring = deck_polygon(db)
    evidence: list[str] = []
    roads = _covered_roads(db)
    for way, kind, tags, _ln in roads:
        cls = tags.get("railway") if kind == "rail" else tags.get("highway")
        evidence.append(f"OSM {kind} {way} {'railway' if kind == 'rail' else 'highway'}={cls}")
    if getattr(db, "replaces", ()):
        evidence.append("hidden pack frame")
    if any(LineString(a.points).intersects(ring) for a in aeroway_decks(airport, law)
           if len(a.points) >= 2):
        evidence.append("OSM bridge tag")
    # the rail's grade governs a cut a railway runs in (19s (2), 18e)
    kind = "rail" if any(k == "rail" for _w, k, _t, _l in roads + ([main] if main else [])) \
        else "road"
    cap, rate = _carve_law(law, kind)
    reach = _reach_m(db, law, cap, rate)
    if roads:
        # the cut runs along its most senior road (rail first, then the
        # road class), so two decks over one crossing share one line
        way, _k, tags, line = main or _senior(roads, [ring])
        cls = tags.get("railway") if _k == "rail" else tags.get("highway")
        path = _past_every_deck(line, reach, lines, tree, decks, past)
        direction = f"along OSM {_k} {way} ({cls})"
        clearance = max(design_clearance_m(tg, law) for _w, _k2, tg, _l in roads)
    else:
        ax = _axis(db)
        if ax is None:
            return DeckCarve(tuple(evidence), "", ())
        way, kind = "", "axis"
        path = _past_every_deck(ax, reach, [], None, decks, past)
        direction = "along the cut's own axis (no mapped road or rail)"
        clearance = float(tn.clearance_m)
    # the trench spans the deck between its end lines; the floor at least
    # carries every road under it with its shoulders (signed offsets)
    frame = PathFrame(list(path.coords))
    rx, ry = zip(*ring.exterior.coords, strict=True)
    _s, rn = frame.project_signed(rx, ry)
    span = (float(rn.min()), float(rn.max()))
    base = carriageway_width_m({}, law) / 2.0 + sh
    lo, hi = -base, base
    for _w, _k2, tg, ln in roads:
        inside = ln.intersection(ring)
        pts = [q for g in getattr(inside, "geoms", [inside]) if not g.is_empty
               for q in getattr(g, "coords", [])]
        if pts:
            _s, n = frame.project_signed([q[0] for q in pts], [q[1] for q in pts])
            w = carriageway_width_m(tg, law) / 2.0 + sh
            lo, hi = min(lo, float(n.min()) - w), max(hi, float(n.max()) + w)
    cp = _path(way, kind, max(-lo, hi), clearance, cap, rate, path, decks, past, airport,
               span, (lo, hi))
    own = [(a, b) for a, b, oid in cp.stretches if oid == db.object_id]
    if own and any(_estimate_floor(db, cp.terrain, a, b, 0.0, law) <= float(db.deck_z)
                   - float(law.tables.structures.deck_gen.thickness_m) - clearance
                   for a, b in own):
        evidence.append("lidar trench")
    return DeckCarve(tuple(evidence), direction, (cp,))


def _cut_groups(gen, carves) -> list[list]:
    """The generated decks that may be ONE cut (owner 2026-11-20T00:33Z):
    each runs under the other's path -- stage 2 decides whether they merge
    (``geom/carve_profile.merged`` on the solved floors, deeper than any
    planar estimate: KPHX's two decks 41 m apart merged at 333.3 m, read
    337.6 m here).  Sharing one line is harmless where they do not: each
    ramps out along it.  Groups of two or more."""
    from ..geom.union_find import find_root
    ids = [d.object_id for d in gen]
    at = {oid: k for k, oid in enumerate(ids)}
    under = {oid: {o for p in carves[oid].paths for _a, _b, o in p.stretches} for oid in ids}
    parent = list(range(len(ids)))
    for a in ids:
        for b in under[a]:
            if b != a and b in at and a in under[b]:
                parent[find_root(parent, at[b])] = find_root(parent, at[a])
    by_id = {d.object_id: d for d in gen}
    groups: dict[int, list] = {}
    for oid in ids:
        groups.setdefault(find_root(parent, at[oid]), []).append(by_id[oid])
    return [g for g in groups.values() if len(g) > 1]


def _shared_mains(gen, carves, law) -> dict[str, tuple]:
    """``{deck id: (way, kind, tags, line)}``: per deck of a cut several
    decks share (:func:`_cut_groups`) whose own path runs along another
    road than its neighbours', the group's most senior road crossing every
    deck of it (tie: its length under them) -- ONE line per cut, so no
    deck's ramp climbs across another's bank (KPHX 1.0.565: two decks over
    two roads, merged, each ramping out along its own road).  A group no
    road crosses whole keeps its paths."""
    from .deck_bridge import deck_polygon
    out: dict[str, tuple] = {}
    for grp in _cut_groups(gen, carves):
        ways = {p.way for d in grp for p in carves[d.object_id].paths}
        lines = {tuple(p.coords) for d in grp for p in carves[d.object_id].paths}
        if len(ways) < 2 and len(lines) < 2:
            # one road, one line (lane lcross21: KJFK ``o4gen_6f1f538c`` /
            # ``o4gen_e74205d8`` both ran along ``-6514`` on lines 14.8 m
            # apart, each chained from its own clip -- two floors where they
            # disagreed, a 12 % step on the ramp)
            continue
        rings = [deck_polygon(d) for d in grp]
        cands = {r[0]: r for d in grp for r in _covered_roads(d)}
        whole = [r for r in cands.values()
                 if all(r[3].intersection(g).length > 1.0 for g in rings)]
        best = _senior(whole or [], rings)
        if best is None:
            # no one road's covered piece crosses them all: the senior road's
            # mapped path, chained on, may (the pieces are clipped per deck)
            best = _senior(list(cands.values()), rings)
            if best is None:
                continue
        for d in grp:
            out[d.object_id] = best
    return out


def _past_every_deck(line: LineString, reach: float, lines, tree, decks, past: float
                     ) -> LineString:
    """``line`` chained on ``reach`` past each end -- and on past the last
    generated deck it then runs under, so the ramp out of the outermost
    deck of one cut has its whole reach too."""
    path = _extended(line, reach, lines, tree)
    st = _stretches(PathFrame(list(path.coords)), path, decks, past)
    if not st:
        return path
    lo, hi = min(a for a, _b, _o in st), max(b for _a, b, _o in st)
    more = max(0.0, reach - lo, reach - (path.length - hi))
    return _extended(line, reach + more, lines, tree) if more > 1.0 else path


def _path(way: str, kind: str, half: float, clearance: float, cap: float, rate: float,
          line: LineString, decks, past: float, airport, span=(), need=()) -> CarvePath:
    frame = PathFrame(list(line.coords))
    return CarvePath(way, kind, round(half, 3), round(clearance, 3), cap, rate,
                     tuple((round(x, 3), round(y, 3)) for x, y in line.coords),
                     tuple(_stretches(frame, line, decks, past)),
                     _terrain(frame, airport.dem),
                     tuple(round(v, 3) for v in span), tuple(round(v, 3) for v in need))


def _path_cells(p: CarvePath, decks_by_id, law, dem, owner: str = "") -> tuple:
    """``(floor, bank)``: the planar estimate of the path's cut -- its
    floor strip and its banks out to the daylight line plus a metre --
    over the stations where the estimated floor stands under the ground."""
    import numpy as np
    if not p.stretches or len(p.terrain) < 2:
        return None, None
    bank = deck_bank_slope(law)
    frame = PathFrame(p.coords)
    s = np.array([t[0] for t in p.terrain])
    r = smoothed([t[1] for t in p.terrain])
    st = []
    for a, b, oid in p.stretches:
        d = decks_by_id.get(oid)
        if d is not None:
            st.append((a, b, _estimate_floor(d, p.terrain, a, b, p.clearance_m, law)))
    if not st:
        return None, None
    z = floor_profile(s, r, st, p.cap, p.rate)
    # the full span less the embankments (``constraints/deck_carve._floor_band``)
    own = decks_by_id.get(owner)
    fz = min(f for _a, _b, f in st)
    lo, hi = floor_band(p, None if own is None else float(own.deck_z) - fz, law)
    left, right, fl, fr, idx = [], [], [], [], []
    for k, sk in enumerate(s):
        (x, y), (ux, uy) = frame.at(float(sk))
        nx, ny = -uy, ux
        side = [r[k]]
        for off in (hi + 4.0, lo - 4.0):
            try:
                side.append(float(dem.z(x + nx * off, y + ny * off)))
            except Exception:    # noqa: BLE001 -- off the DEM
                pass
        depth = max(0.0, max(side) - float(z[k]))
        if depth > 0.05 or any(a - 4.0 <= sk <= b + 4.0 for a, b, _z in st):
            idx.append(k)
        w = depth / bank + 1.0
        left.append((x + nx * (hi + w), y + ny * (hi + w)))
        right.append((x + nx * (lo - w), y + ny * (lo - w)))
        fl.append((x + nx * hi, y + ny * hi))
        fr.append((x + nx * lo, y + ny * lo))
    if len(idx) < 2:
        return None, None
    k0, k1 = max(0, idx[0] - 2), min(len(s) - 1, idx[-1] + 2)
    floor = Polygon(fl[k0:k1 + 1] + list(reversed(fr[k0:k1 + 1]))).buffer(0.0)
    band = Polygon(left[k0:k1 + 1] + list(reversed(right[k0:k1 + 1]))).buffer(0.0)
    return floor, band.difference(floor)


def _untouched(c, law) -> bool:
    """A cell the cut never takes: airside pavement, the runway family, a
    structure, a building pad, a road ribbon (stage 2 levels its vertices)."""
    from ..law.tables import airside_stage_roles, family
    if c.kind == "structure" or c.role == "building":
        return True
    keep = set(airside_stage_roles(law)) | set(family(law, "road_cross_section").roles)
    return c.role in keep


def _taken_over(decks, tunnels, past: float):
    """The ground a generated deck's cut takes over: its ring and opened
    approaches grown by the bank's run-on, and the corridor of every tunnel
    the structure pass cut under it."""
    from .deck_bridge import deck_polygon
    ids = {d.object_id for d in decks}
    parts = [unary_union([deck_polygon(d)] + [Polygon(q).buffer(0.0) for q in d.approach
                                              if len(q) >= 3]).buffer(past, join_style="mitre")
             for d in decks]
    for tn in tunnels:
        if str(getattr(tn, "deck_bridge", "") or "") in ids and len(tn.axis) >= 2:
            parts.append(LineString(tn.axis).buffer(float(tn.half_width_m) + 0.5,
                                                    cap_style="flat"))
            if len(tn.wall_path) >= 3:
                parts.append(Polygon(tn.wall_path).buffer(0.0))
    return unary_union(parts)


def _need_strips(carves, taken_over):
    """THE ROADS' OWN FLOOR, NODED (lane lcross20): per path of every cut its
    ``need`` strip -- every road under the deck with its shoulders
    (``CarvePath.need``), the least floor stage 2 lays whatever the solved
    top (``model/deck_carve.floor_band``) -- inside the ground the cut takes
    over.  The planar floor estimate can be wider than stage 2's band; a
    face spanning it then reads the road over its banks (MEASURED KRDU
    1.0.567 ``o4gen_80bc82b9``: the deck-ground face across ``-254``'s floor
    had no vertex within 10 m of the road, which stood 2.6 m over its floor,
    clearance 3.55 m of 4.2)."""
    parts = []
    for dc in carves:
        for p in dc.paths:
            if len(p.need) != 2 or len(p.coords) < 2:
                continue
            frame = PathFrame(p.coords)
            lo, hi = float(p.need[0]), float(p.need[1])
            n = max(2, int(frame.length / STEP_M) + 1)
            left, right = [], []
            for k in range(n):
                (x, y), (ux, uy) = frame.at(frame.length * k / (n - 1))
                left.append((x - uy * hi, y + ux * hi))
                right.append((x - uy * lo, y + ux * lo))
            strip = Polygon(left + right[::-1]).buffer(0.0)
            if not strip.is_empty:
                parts.append(strip)
    return unary_union(parts).intersection(taken_over) if parts else None


def _road_spans(gen, carves, airport, law, spans=None) -> list[tuple]:
    """``(axis run on to the end lines, half width with the ring's margin,
    the taxiway deck's id)`` of every generated ROAD deck spanning a
    generated deck's cut (``geom/road_span``, as ``pipeline/road_deck``
    draws it); riders aside (the deck carries them)."""
    from ..geom.deck_frame import deck_frame
    from ..geom.road_span import DeckSpan, span_to_cut
    if spans is None:
        spans = [DeckSpan(d.object_id, tuple(d.ring), [tuple(p.coords) for p in
                                                       carves[d.object_id].paths], fr)
                 for d in gen if d.object_id in carves and (fr := deck_frame(d)) is not None]
    margin = float(law.tables.structures.deck_gen.edge_margin_m)
    riding = {str(r) for d in gen for r in getattr(d, "riders", ()) or ()}
    out = []
    for b in getattr(airport, "road_bridges", ()) or ():
        axis = LineString(b.get("axis_xy") or ())
        if str(b.get("id")) in riding or axis.length <= 1.0:
            continue
        got = span_to_cut(axis, spans)
        if got is not None:
            out.append((got[0], float(b.get("half_m") or 0.0) + margin, got[1]))
    return out


class _RoadSpan(_t.NamedTuple):
    """A generated road deck over a deck's cut, as the cut's stretches read
    it: the ring it spans and the TAXIWAY deck's id (its floor, its top)."""

    object_id: str
    ring: tuple


def _road_stretch_decks(gen, carves, airport, law) -> list[_RoadSpan]:
    """THE ROAD DECK OVER THE CUT IS CUT LIKE ITS TAXIWAY DECK (owner
    2026-11-20T15:20Z: "Road bridges we create ... require the same
    clearance under them as taxiway bridges ... assume they will have the
    same height and slope as the taxiway bridges"; lane lcross20): each
    road deck spanning a generated deck's cut (:func:`_road_spans`) is a
    stretch of that deck on every path running under it -- the floor stays
    the taxiway deck's, level under it, and the ramps start past it.
    MEASURED KPHX 1.0.567 road bridges ``-301`` / ``-302`` (33.436006,
    -111.991618): the floor ramped up between the taxiway decks and them,
    0.93 / 0.30 m short of clearance."""
    out = []
    for ext, half, oid in _road_spans(gen, carves, airport, law):
        ring = ext.buffer(half, cap_style="flat", join_style="mitre")
        if ring.geom_type == "Polygon":
            out.append(_RoadSpan(oid, tuple(ring.exterior.coords)[:-1]))
    return out


def _landings(gen, carves, airport, law):
    """THE LANDINGS, NODED (lane lcross20; RULINGS 2026-11-19s (8) (d)):
    past each end line of every generated deck, across its width, and past
    each end of every generated ROAD deck spanning a cut (``geom/road_span``,
    as ``pipeline/road_deck`` draws it), a strip ``[deck_gen]
    end_landing_m`` deep -- the ground ``constraints/deck_carve`` lands at
    the end's level.  Splitting the cut's cells along it puts mesh vertices
    on each end and on the landing's far line, so no face across the end
    reads the trench bank under it (MEASURED KPHX 1.0.567: the road decks'
    far ends ran down the bank, their end point inside a bank face)."""

    from ..geom.deck_frame import deck_frame
    from ..geom.road_span import DeckSpan
    depth = float(law.tables.structures.deck_gen.end_landing_m)
    parts, spans = [], []
    for d in gen:
        fr = deck_frame(d)
        if fr is None:
            continue
        (ox, oy), (ux, uy), (wx, wy) = fr
        lu = hypot(ux, uy)
        if lu < 1e-6:
            continue
        ex, ey = ux / lu * depth, uy / lu * depth
        for (ax, ay), (dx, dy) in (((ox, oy), (-ex, -ey)), ((ox + ux, oy + uy), (ex, ey))):
            parts.append(Polygon([(ax, ay), (ax + wx, ay + wy), (ax + wx + dx, ay + wy + dy),
                                  (ax + dx, ay + dy)]))
        dc = carves.get(d.object_id)
        if dc is not None:
            spans.append(DeckSpan(d.object_id, tuple(d.ring),
                                  [tuple(p.coords) for p in dc.paths], fr))
    for ext, half, _oid in _road_spans(gen, carves, airport, law, spans):
        c = list(ext.coords)
        for p, q in ((c[0], c[1]), (c[-1], c[-2])):
            n = hypot(p[0] - q[0], p[1] - q[1]) or 1.0
            ox_, oy_ = (p[0] - q[0]) / n, (p[1] - q[1]) / n
            nx, ny = -oy_ * half, ox_ * half
            parts.append(Polygon([(p[0] + nx, p[1] + ny), (p[0] - nx, p[1] - ny),
                                  (p[0] - nx + ox_ * depth, p[1] - ny + oy_ * depth),
                                  (p[0] + nx + ox_ * depth, p[1] + ny + oy_ * depth)]))
    good = [q.buffer(0.0) for q in parts if q.is_valid or not q.buffer(0.0).is_empty]
    return unary_union(good) if good else None


def _split_structures(cells, blade, law, own: bool = False, ground: bool = False
                      ) -> tuple[list, int]:
    """``cells`` with every STRUCTURE cell the cut takes over (a corridor
    or deck ground under a generated deck) split along ``blade`` -- the
    roads' floors -- so the mesh carries vertices on each floor's edges
    (role and ref kept; a second piece takes ``<ref>#<k>``).  ``own``: the
    cut's own cells too (:data:`~..model.deck_carve.CARVE_REF`); ``ground``:
    every groundside cell the cut may take as well (never airside pavement,
    a road, a building: ``_untouched``) -- a landing past a road deck's end
    lies on the plain ground (KPHX ``o4road_eb86b0fb``: no vertex within 3 m
    of its end, 1.6 m under it)."""
    import dataclasses as _dcl

    from ..law.tables import airside_stage_roles
    from ..model.deck_carve import CARVE_REF as _ref
    air = set(airside_stage_roles(law))
    from ..law.tables import family
    # a road deck's approach ribbon is noded on the landing too: it rises to
    # the deck end there (owner RULINGS 2026-11-20e; KPHX ``-301`` over
    # ``-7449``: no ribbon vertex within 2.5 m of the deck end, 1.6 m under it)
    road_roles = set(family(law, "road_cross_section").roles) if ground else set()
    edge = blade.boundary
    out, n = [], 0
    for c in cells:
        mine = (c.kind == "structure" and c.role not in air
                and (own or not str(c.ref).startswith(_ref))) \
            or (ground and c.kind != "structure" and (not _untouched(c, law)
                                                       or c.role in road_roles))
        if not mine or len(c.ring) < 3:
            out.append(c)
            continue
        poly = Polygon(c.ring, c.holes).buffer(0.0)
        if not poly.intersects(edge):
            out.append(c)
            continue
        pieces = [d for g in (poly.intersection(blade), poly.difference(blade))
                  for q in polygon_parts_with_area(g) if q.area > 0.5
                  for d in densified_parts(q, NODE_M)]
        if len(pieces) < 2:
            out.append(c)
            continue
        n += 1
        for k, q in enumerate(pieces):
            out.append(_dcl.replace(c, ref=c.ref if k == 0 else f"{c.ref}#{k}",
                                    ring=tuple(q.exterior.coords)[:-1],
                                    holes=tuple(tuple(h.coords)[:-1] for h in q.interiors)))
    return out, n


def _crossed(pts: list, rings) -> list:
    """``pts`` (a closed coordinate list) with a vertex wherever a segment
    crosses ``rings`` (lines), more than :data:`_RING_BAND_M` from its ends."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:], strict=False):
        seg = LineString([a, b])
        if seg.length > 2.0 * _RING_BAND_M and seg.intersects(rings):
            x = seg.intersection(rings)
            ts = sorted({seg.project(Point(q)) for g in getattr(x, "geoms", [x])
                         if g.geom_type == "Point" for q in g.coords})
            out += [seg.interpolate(t).coords[0] for t in ts
                    if _RING_BAND_M < t < seg.length - _RING_BAND_M]
        out.append(b)
    return out


def _ring_dense(cells, rings, law) -> tuple[list, int]:
    """``cells`` with every cut cell and every non-airside structure cell
    noded where its edges cross the generated decks' rings (``rings``, their
    boundary lines) and every :data:`RING_NODE_M` where they run along one
    (:data:`_RING_BAND_M` either side, ``planar/chords.densify_within``):
    the mesh carries each deck's floor along its own ring, never a long
    triangle across it."""
    import dataclasses as _dcl

    from shapely.prepared import prep

    from ..law.tables import airside_stage_roles
    from .chords import densify_within
    air = set(airside_stage_roles(law))
    zone = rings.buffer(_RING_BAND_M)
    pz = prep(zone)
    out, n = [], 0
    for c in cells:
        mine = str(c.ref).startswith(CARVE_REF) or (c.kind == "structure"
                                                     and c.role not in air)
        if not mine or len(c.ring) < 3 or not pz.intersects(Polygon(c.ring).exterior):
            out.append(c)
            continue

        def dense(r):
            pts = densify_within(_crossed(list(r) + [r[0]], rings), zone, RING_NODE_M)
            return tuple(pts[:-1])
        ring, holes = dense(c.ring), tuple(dense(h) for h in c.holes if len(h) >= 3)
        if len(ring) == len(c.ring) and sum(map(len, holes)) == sum(len(h) for h in c.holes):
            out.append(c)
            continue
        if Polygon(c.ring, c.holes).is_valid and not Polygon(ring, holes).is_valid:
            # a hairline cut cell its own noding folds (MEASURED KMCO 1.0.570
            # ``o4gen_6c61fae4:ground#1``, 13.7 m2: two sides ~0.1 m apart
            # crossed once noded, and the next union threw "non-noded
            # intersection"): it stays as it was
            out.append(c)
            continue
        n += 1
        out.append(_dcl.replace(c, ring=ring, holes=holes))
    return out, n


def deck_carve(classification, decks, airport, law, tunnels=()
               ) -> tuple[_t.Any, tuple, list[str]]:
    """``(classification with every generated deck's cut cells, decks with
    their :class:`DeckCarve`, notes)`` (module doc).  Unchanged with no
    generated deck (stage 1's map: withheld).  ``tunnels``: the structure
    pass's corridors -- those under a generated deck are the deck's cut,
    split along its roads' floors (:func:`_split_structures`)."""
    from ..classify.roles import Cell
    from ..geom.fixed_overlay import is_hairline
    from ..law.tables import role_side
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon
    gen = [d for d in decks if is_generated(d)]
    if not gen or classification is None or getattr(airport, "dem", None) is None:
        return classification, tuple(decks), []
    lines, tree = _road_lines(airport)
    carves = {d.object_id: _deck_paths(d, gen, airport, law, lines, tree) for d in gen}
    by_id = {d.object_id: d for d in gen}
    notes: list[str] = []
    mains = _shared_mains(gen, carves, law)
    for oid, main in mains.items():
        got = _deck_paths(by_id[oid], gen, airport, law, lines, tree, main)
        if any(o == oid for p in got.paths for _a, _b, o in p.stretches):
            carves[oid] = got
            notes.append(f"{oid}: one cut with its neighbours -- along their most senior "
                         f"road {main[0]} (lane lcarve2)")
    road = _road_stretch_decks(gen, carves, airport, law)
    if road:
        # every path read again with the road decks over its cut as stretches
        with_road = [*gen, *road]
        for d in gen:
            main = mains.get(d.object_id)
            got = _deck_paths(d, with_road, airport, law, lines, tree, main)
            if main is None or any(o == d.object_id for p in got.paths
                                   for _a, _b, o in p.stretches):
                carves[d.object_id] = got
        notes.append(f"{len(road)} generated road deck(s) over a deck's cut: cut like it, the "
                     f"floor level under them (owner 2026-11-20T15:20Z)")
    past = bank_past_m(law)
    regions: list[tuple[str, str, _t.Any]] = []
    for d in gen:
        dc = carves[d.object_id]
        floors, banks = [], []
        for p in dc.paths:
            f, b = _path_cells(p, by_id, law, airport.dem, d.object_id)
            if f is not None:
                floors.append(f)
                banks.append(b)
        ground = unary_union([deck_polygon(d)] + [Polygon(q).buffer(0.0) for q in d.approach
                                                  if len(q) >= 3]).buffer(past, join_style="mitre")
        regions += [(d.object_id, "floor", unary_union(floors) if floors else None),
                    (d.object_id, "bank", unary_union(banks) if banks else None),
                    (d.object_id, "ground", ground)]
        notes.append(f"{d.object_id}: its cut is the deck's (owner 2026-11-19T23:07Z): "
                     f"evidence {', '.join(dc.evidence) or 'none'}; ramps {dc.direction}")
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    kept = unary_union([p for c, p in zip(classification.cells, polys, strict=True)
                        if _untouched(c, law) and not p.is_empty])
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    taken = kept
    new: list = []
    for oid, part, geom in regions:
        if geom is None or geom.is_empty:
            continue
        free = geom.difference(taken)
        for k, q in enumerate(d for g in polygon_parts_with_area(free)
                              if g.area > 0.5 and not is_hairline(g, max(spacing, _HAIR_M))
                              for d in densified_parts(g, NODE_M)):
            new.append(Cell(0, "graded_strip", f"{CARVE_REF}:{oid}:{part}" + (f"#{k}" if k else ""),
                            tuple(q.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in q.interiors),
                            None, None, role_side(law, "graded_strip"), "structure",
                            {CARVE_REF: 1.0, "area_m2": q.area}))
        taken = taken.union(free)
    cells, n = list(classification.cells), 0
    if new:
        knife = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in new])
        cells, n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                               mark=CARVE_REF, new_cells=new,
                               cuts=lambda c: not _untouched(c, law))
    floors = unary_union([g for _o, part, g in regions if part == "floor" and g is not None])
    n_split = 0
    taken_over = _taken_over(gen, tunnels, past)
    if not floors.is_empty:
        cells, n_split = _split_structures(cells, floors.intersection(taken_over), law)
    need = _need_strips([carves[d.object_id] for d in gen], taken_over)
    n_need = 0
    if need is not None and not need.is_empty:
        cells, n_need = _split_structures(cells, need, law, own=True)
    land = _landings(gen, carves, airport, law)
    n_land = 0
    if land is not None and not land.is_empty:
        cells, n_land = _split_structures(cells, land, law, own=True, ground=True)
    # ... and along every generated deck's ring, so a corridor running on
    # under the deck carries vertices on the ring (KJFK 1.0.565
    # ``o4gen_a900c332``: one tunnel-ramp face spanned the ring, a 35 m
    # triangle from the neighbour's ramp stood 0.15 m over its floor)
    rings = unary_union([deck_polygon(d) for d in gen])
    cells, n_ring = _split_structures(cells, rings.intersection(taken_over), law)
    cells, n_dense = _ring_dense(cells, rings.boundary, law)
    cells = [_dc.replace(c, id=i) for i, c in enumerate(cells)]
    notes.append(f"{len(new)} cut cell(s) minted under {len(gen)} generated deck(s), "
                 f"{n} groundside cell(s) cut, {n_split} structure cell(s) under them split "
                 f"along the roads' floors, {n_need} along their carriageways, {n_land} "
                 f"along the deck ends' landings and {n_ring} along the rings, {n_dense} noded "
                 f"every {RING_NODE_M:g} m along "
                 f"the rings (owner 2026-11-19T23:07Z)")
    out = tuple(_dc.replace(d, carve=carves.get(d.object_id)) if is_generated(d) else d
                for d in decks)
    return _dc.replace(classification, cells=tuple(cells)), out, notes
