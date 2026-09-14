"""§37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM
(Fable 2026-09-13; owner RULINGS 2026-09-13j item 5, ruled 2026-09-13aj).

Lane ``v2roadcap2`` measured KCLT's east access road (``dsf:pol51``) held
+13.24 m over its own DEM by NO ROW: ``--why-at`` on a pressure solve of
the same LP names zero binding rows, and the road sits +9.71 m ABOVE its
own ``preferred_road_z`` fit target (203.44) — the OBJECTIVE holds it,
welded by the bending term to the airside fill beside it (``graded_strip``
12.48 m off the DEM).  A weight contest is not a law.

**THE RULE.**  From each AIRSIDE CONTACT of a groundside road — the mouth
where the road meets an apron, pad or lot; that level is the airside's,
airside is king — the road's target along ROUTE distance ``s`` is

    target(s) = max(clamp(s), z_contact - road_cap * s)

It descends at the road's own longitudinal cap until it meets the FLOOR and
follows it from there (and climbs at the cap where the floor rises above
the contact); between two contacts the two ramps meet at their HIGHER
envelope; a road with NO airside contact targets the floor alone.

THE FLOOR IS THE CORE'S CLAMP, NOT THE RAW DEM (§37 (6) amended, owner
RULINGS 2026-09-13be): ``clamp(s)`` is ``cap_lipschitz_profile``'s
mid-envelope — the value the core's own ``include_roads`` would have given
the road, which it does NOT give inside the patch coverage because the
core removes its levelling there.  Where the terrain is cap-lawful the two
coincide.  THE TARGET IS A FUNCTION OF (ROUTE, STATION) ALONE (§37 (8),
RULINGS 2026-09-13bb), so it cannot tilt a section: see
:func:`road_ramp_targets`.  The
target is a DESIGN TARGET at the design-target weight (``[design] law``,
the weight every law row is priced at) and SUPERSEDES ``preferred_road_z``
— the core's clamped soft fit at ``[design] road`` (3) — for the vertices
it governs (:func:`with_road_ramp`, the one superseding site).  It carries
a HARD ceiling ``z <= target + [cockpit] visual_m`` (``RULING_CEILING``,
registered in ``[design] hard_rulings``), so smoothness can never lift the
road back onto the fill.

§37 (1)'s longitudinal cap and the road cross-section are UNCHANGED; the
bank (§37 (3)) then daylights only the short fill at the contact.  §34 (1)
and §36 (5) are the same law for tunnel and EAT ramps.

**THE ROUTE IS WALKED, NEVER CHORDED** (§34 (1)): ``s`` is the shortest
path from a contact along the road's own planar edges — the ribbon's own
graph, the metric ``road_terrain_conformance`` reads a chain in — so a
road that doubles back is priced by the length it runs, not by the chord.

**THE CONTACT LEVEL IS THE AIRSIDE'S OWN PRE-SOLVE LEVEL**: the airside
target published for that vertex where one exists (``apron_trend_z`` /
``taxi_trend_z`` / ``preferred_z``, §8.6/§8.7/§21) and never below the DEM
under it.  MEASURED at KCLT (base arm, 234 contacts): the solved airside
level stands a median 0.59 m and a p95 1.97 m off the DEM at the mouth, so
the estimate is the mouth's level to within the visual threshold at half
the mouths and within 2 m at 95 % of them.  It moves the target ONLY in
the descent leg — where the envelope stands above the DEM — because the
target is the HIGHER of the ramp and the ground.
"""
from __future__ import annotations

import dataclasses as _dc
import heapq
import math
import typing as _t

from ..law import Law
from ..law.tables import (family, is_value_role, role_cap, role_side,
                          senior_role)
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["deck_refs", "contact_roles", "road_ramp_targets",
           "road_route_frame", "reach_contacts", "merge_routes",
           "with_road_ramp", "RampTargets"]

class RampTargets(_t.NamedTuple):
    """The derivation's product: ``targets`` vertex id -> the ramp target,
    ``report`` the figures the build log and the spec's MEASURED block
    quote."""

    targets: dict[int, float]
    report: dict[str, _t.Any]
    #: §37 (7)'s route frame the targets were read in (the SAME one
    #: :func:`with_road_ramp` publishes — derived once per build)
    frame: dict[int, tuple[int, float, float]] = {}


def _road_roles(law: Law) -> frozenset[str]:
    """The GROUNDSIDE ROAD family — ``service_road`` / ``service_junction``,
    read from the ``road_cross_section`` family table, never typed here.
    A ``parking_lot`` has no axis in law (RULINGS 2026-09-04m) and
    ``groundside_pavement`` is not a road: neither ramps."""
    return frozenset(family(law, "road_cross_section").roles)


def deck_refs(pm: PlanarMap) -> frozenset[str]:
    """THE BRIDGE DECKS' refs (``planar/structures.py``: a mapped bridge's
    deck piece is a face of role ``service_road`` named
    ``bridge_deck:<way>``), read off the map's own structure records —
    never off the ref string.

    A DECK IS NOT A ROAD ON THE GROUND.  Its level is STATED by the
    structure: the clearance over the ramp beneath it and, since §33 (4)
    (owner RULINGS 2026-09-13d item 9), a lower bound at the graded
    surface of its two mapped ends, so it "smoothly connects the road on
    either end".  §37 (6) would pull it to the terrain under the crossing
    it spans — MEASURED on the LEMD capture: ``bridge_deck:-3923`` 4.72 m
    and ``-3731`` 4.20 m BELOW their core profile, and at KCLT
    ``bridge_deck:-3595`` 2.84 m — a hard ceiling against a structure's
    own datum.  The deck faces are therefore out of the ramp's population.
    """
    return frozenset(d.ref for tn in pm.structures for d in tn.decks)


def _owned(pm: PlanarMap, roads: _t.AbstractSet[str], law: Law) -> dict[int, str]:
    """Vertex -> its senior role, for every vertex a road face OWNS (the
    ``road_profile.road_family_vertices`` rule, scoped to the road family:
    a vertex shared with an apron or taxiway is the AIRSIDE surface's and
    is a CONTACT, not a road vertex)."""
    decks = deck_refs(pm)
    out: dict[int, str] = {}
    on_deck: set[int] = set()
    for fid, f in pm.faces.items():
        if f.role not in roads:
            continue
        vs = [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]
        if f.ref in decks:
            on_deck.update(vs)
            continue
        for v in vs:
            if v in out:
                continue
            sr = senior_role(law, pm.roles_at(v))
            if sr in roads:
                out[v] = sr
    # a vertex the deck SHARES with the road beside it is the deck's (its
    # ring vertices ARE the corridor rim's — ``constraints/structures.py``)
    for v in on_deck:
        out.pop(v, None)
    return out


def contact_roles(law: Law) -> frozenset[str]:
    """§37 (10) (1) THE AIRSIDE CONTACT SET (owner RULINGS 2026-09-13cs
    item 5): every face that carries its OWN airside level — apron, the
    pad, the whole TAXI family (``junction`` and ``stub`` with it) and the
    runway family, §40's shoulder joining as soon as the role is declared
    — plus the roles ``[road_contact] extra_roles`` names (the LOT, which
    ``precedence.toml`` partitions groundside but which is stated hard
    surface a road meets).

    Read off ``precedence.toml`` (``side = "airside"`` and ``value =
    true``), never typed here: §37 (6) named "apron, pad or lot" in PROSE
    and a taxiway was not in it, which is why HECA's ``route0`` ended
    4.4 m short of ``pav74`` with no contact at all and targeted the DEM
    1.2 m above it — a 33 % cliff.
    """
    roles = law.tables.precedence.roles
    out = {r for r in roles
           if role_side(law, r) == "airside" and is_value_role(law, r)}
    out.update(getattr(law.tables.emit.road_contact, "extra_roles", ()) or ())
    return frozenset(out)


def _airside_level(pm: PlanarMap, v: int) -> float | None:
    """THE AIRSIDE'S OWN LEVEL at one vertex: the highest of the published
    airside targets it carries (``apron_trend_z`` / ``taxi_trend_z`` /
    ``preferred_z``) and the DEM under it — airside is king, and the
    contact is never sunk below the ground."""
    cands = [z for z in (pm.apron_trend_z.get(v), pm.taxi_trend_z.get(v),
                         pm.preferred_z.get(v)) if z is not None]
    dem = pm.vertices[v].dem_z
    if dem is not None:
        cands.append(float(dem))
    return max(float(z) for z in cands) if cands else None


def reach_contacts(pm: PlanarMap, law: Law, owned: _t.Mapping[int, str],
                   mouths: _t.Mapping[int, float],
                   frame: _t.Mapping[int, tuple[int, float, float]],
                   reach_m: float, end_m: float
                   ) -> tuple[dict[int, tuple[int, int, float, float]],
                              list[dict[str, _t.Any]]]:
    """§37 (10) (1) THE CONTACT A ROAD DOES NOT TOUCH (owner RULINGS
    2026-09-13cs item 5): for each ROUTE END that carries no mouth, the
    nearest point on an airside face's EDGE within ``reach_m``.

    Returns ``vertex -> (a, b, u, s)``: the two vertices of the airside
    edge the road contacts, the interpolation parameter along it, and the
    ROUTE distance from the contact to that vertex.  The generator turns
    each into ONE-WAY ceiling ``z[v] <= (1-u)·z[a] + u·z[b] + cap·s``.

    THE CONTACT LEVEL IS NOT ESTIMATED, IT IS THE AIRSIDE'S OWN COLUMN.
    §37 (10) says "at that face's solved level", and pre-solve there is
    no such number: MEASURED at the site, HECA ``pav74``'s ring vertices
    beside ``route0`` carry NO published target at all (``taxi_trend_z``
    / ``apron_trend_z`` / ``preferred_z`` all absent) and their DEM is
    108.12 / 108.51, while the solve puts that edge at 106.77 — the
    taxiway is CUT 1.4 m.  An estimated contact of ``max(published,
    DEM)`` would have RAISED ``route0``'s end to 108.29 and made the
    cliff worse (measured, arm 1).  A row against the airside's own
    columns reads the level the solve gives it, and ``follows`` keeps it
    ONE-WAY: airside is king, no airside vertex moves for a road.

    An END is the road's own extent along its route — the vertices within
    ``end_m`` (one lane width) of its first or last station.  A road that
    runs BESIDE an apron for 400 m takes no contact from it: the mouth is
    where the vehicle crosses, and that is an end.  A vertex with a
    touching MOUTH between it and the end keeps that mouth's ramp; the
    nearer of two reach ends wins.
    """
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    cset = contact_roles(law)
    segs: list[LineString] = []
    ends: list[tuple[int, int]] = []
    for fid, f in pm.faces.items():
        if f.role not in cset:
            continue
        for cyc in (f.ring, *f.holes):
            vs = pm.ring_vertices(cyc)
            for a, b in zip(vs, list(vs[1:]) + [vs[0]]):
                pa, pb = pm.vertices[a].xy, pm.vertices[b].xy
                if math.dist(pa, pb) < 1e-6:
                    continue
                segs.append(LineString([pa, pb]))
                ends.append((a, b))
    out: dict[int, tuple[int, int, float, float]] = {}
    named: list[dict[str, _t.Any]] = []
    if not segs:
        return out, named
    tree = STRtree(segs)
    by_route: dict[int, list[tuple[float, int]]] = {}
    for v in owned:
        fr = frame.get(v)
        if fr is not None:
            by_route.setdefault(fr[0], []).append((fr[1], v))
    mouth_s: dict[int, list[float]] = {}
    for v in mouths:
        fr = frame.get(v)
        if fr is not None:
            mouth_s.setdefault(fr[0], []).append(fr[1])
    at: dict[int, float] = {}                   # vertex -> its own |Δs|
    for r, items in by_route.items():
        items.sort()
        ms = mouth_s.get(r, ())
        for end_s, group in ((items[0][0], [v for s_, v in items
                                            if s_ <= items[0][0] + end_m]),
                             (items[-1][0], [v for s_, v in items
                                             if s_ >= items[-1][0] - end_m])):
            if any(abs(m - end_s) <= end_m for m in ms):
                continue                       # the end already has a mouth
            best: tuple[float, int, int, float, int] | None = None
            for v in group:
                if v in mouths:
                    continue
                p = Point(pm.vertices[v].xy)
                for i in tree.query(p, predicate="dwithin", distance=reach_m):
                    i = int(i)
                    d = float(segs[i].distance(p))
                    if best is not None and d >= best[0]:
                        continue
                    ln = segs[i]
                    a, b = ends[i]
                    u = (ln.project(p) / ln.length) if ln.length else 0.0
                    best = (d, a, b, float(u), v)
            if best is None:
                continue
            _d, a, b, u, at_v = best
            n = 0
            for s_, v in items:
                ds = abs(s_ - end_s)
                if any(min(end_s, s_) < m < max(end_s, s_) for m in ms):
                    continue                   # a mouth stands between them
                if v in at and at[v] <= ds:
                    continue                   # a nearer end already governs
                at[v] = ds
                out[v] = (a, b, u, ds)
                n += 1
            named.append({"route": r, "governs": n, "gap_m": round(_d, 2),
                          "edge": (a, b), "u": round(u, 3),
                          "at": pm.vertices[at_v].xy})
    return out, named


def _contacts(pm: PlanarMap, roads: _t.AbstractSet[str], law: Law
              ) -> dict[int, float]:
    """THE MOUTHS: every vertex of a road face whose senior role is an
    AIRSIDE one, with the airside's own level there — the published
    airside target (``apron_trend_z`` / ``taxi_trend_z`` / ``preferred_z``)
    where the vertex carries one, never below the DEM under it."""
    out: dict[int, float] = {}
    for fid, f in pm.faces.items():
        if f.role not in roads:
            continue
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                if v in out:
                    continue
                roles = pm.roles_at(v)
                if not any(role_side(law, r) == "airside" for r in roles):
                    continue
                z = _airside_level(pm, v)
                if z is not None:
                    out[v] = z
    return out


def _graph(pm: PlanarMap, nodes: _t.AbstractSet[int]
           ) -> dict[int, list[tuple[int, float]]]:
    """The ROAD's own graph: every planar edge whose BOTH endpoints are
    road vertices or mouths, weighted by its length."""
    adj: dict[int, list[tuple[int, float]]] = {}
    for e in pm.edges.values():
        if e.a not in nodes or e.b not in nodes:
            continue
        d = math.dist(pm.vertices[e.a].xy, pm.vertices[e.b].xy)
        adj.setdefault(e.a, []).append((e.b, d))
        adj.setdefault(e.b, []).append((e.a, d))
    return adj


def _dijkstra(adj: _t.Mapping[int, list[tuple[int, float]]],
              seeds: _t.Mapping[int, float], cap: float
              ) -> tuple[dict[int, float], dict[int, float]]:
    """THE HIGHER ENVELOPE OF THE MOUTHS (§37 (6)): the highest level a
    contact can still be at after descending at ``cap`` along the road's
    own graph — a max-label Dijkstra, exact because every hop only ever
    LOWERS the label.  Returns the labels and the route distance walked."""
    lab: dict[int, float] = {}
    walked: dict[int, float] = {}
    pq: list[tuple[float, int]] = []
    for v, z in seeds.items():
        if lab.get(v, -math.inf) < z:
            lab[v] = z
            walked[v] = 0.0
            heapq.heappush(pq, (-z, v))
    while pq:
        nz, u = heapq.heappop(pq)
        z = -nz
        if z < lab.get(u, -math.inf) - 1e-9:
            continue
        for w, d in adj.get(u, ()):
            zw = z - cap * d
            if zw > lab.get(w, -math.inf) + 1e-9:
                lab[w] = zw
                walked[w] = walked.get(u, 0.0) + d
                heapq.heappush(pq, (-zw, w))
    return lab, walked


def _lift(ss: _t.Sequence[float], vals: _t.Sequence[float], cap: float
          ) -> dict[float, float]:
    """§37 (8) ONTO THE ROUTE: the cap-Lipschitz UPPER envelope of the
    per-vertex descent labels at the stations of ONE route, so the ramp is
    ONE VALUE PER STATION and can never tilt a section."""
    out = list(vals)
    for i in range(1, len(out)):                            # forward
        out[i] = max(out[i], out[i - 1] - cap * (ss[i] - ss[i - 1]))
    for i in range(len(out) - 2, -1, -1):                   # backward
        out[i] = max(out[i], out[i + 1] - cap * (ss[i + 1] - ss[i]))
    return {s_: z_ for s_, z_ in zip(ss, out)}


def _floor_along_route(pm: PlanarMap, law: Law, airport: Airport,
                       profiles=None):
    """``(profiles, per-face answer index)`` for THE RAMP'S FLOOR, read
    ALONG THE ROAD'S OWN CENTRELINE.

    THE FLOOR IS THE CORE'S CLAMP, NOT THE RAW DEM (§37 (6) amended, owner
    RULINGS 2026-09-13be).  Scout ``roadlevel``: the core's
    ``include_roads`` levelling is REMOVED inside the patch coverage + 6 m
    (``O4_Vector_Map.py:1749-1757``), so inside the coverage v2 is the sole
    road authority and it must give the road what the core would have —
    ``cap_lipschitz_profile``'s mid-envelope, which ``RoadProfiles`` already
    carries as each way's ``z``.  Where the terrain is cap-lawful the two
    coincide; where it is not, the road takes the lift or cut the core
    would have given it instead of the terrain's own step.

    IT IS ALSO WHAT KEEPS THE SECTION LEVEL (§37 (8)).  The clamp is
    cap-LIPSCHITZ along the route by construction and the descent envelope
    is too, so their max moves at most ``cap_l x |Δs|`` between two
    stations of ONE route — never more than the §37 (7) pair bound
    ``cap_l·|Δs| + cap_t·|Δt|``.  The RAW DEM is not: measured on the KCLT
    capture, 145 of 2,155 cross-section pairs carried targets already over
    their own 2 % bound (worst 3.51 m against 0.60 m over a 5.8 m station
    difference on ``dsf:pol51``), which is the tilt the surviving
    ``road_cross_section`` rows read.

    THE DEM IS STILL READ ALONG THE ROUTE, never under the kerb, for the
    REPORT (a road page on a side slope spans the hill transversely — KCLT
    ``dsf:pol51`` carries DEM samples from 199.91 to 216.55 m across 48 m
    of one page).
    """
    from .road_profile import RoadProfiles, core_profiles
    if profiles is None:
        prof, per_face = core_profiles(airport, pm, law)
    else:
        # the SAME profiles ``preferred_road_z`` built for this map (it
        # carries its own ``per_face`` answer index): read, never rebuilt
        prof, per_face = profiles, profiles.per_face
    return prof, per_face


def _dem_twin(prof, per_face):
    """The same ways with the clamped ``z`` swapped for the terrain
    ``dem`` — the REPORT's reading of how far the clamp stands off the
    ground under the road."""
    from .road_profile import RoadProfiles
    twin = {id(w): _dc.replace(w, z=w.dem) for w in prof.all_ways}
    dem_prof = RoadProfiles(prof.cap, prof.station_m, prof.lane_width_m,
                            prof.radius_m,
                            tuple(twin[id(w)] for w in prof.ways))
    dem_prof.axes = {fid: twin[id(w)] for fid, w in prof.axes.items()}
    per_face_dem = {fid: [(twin[id(w)], r) for w, r in lst]
                    for fid, lst in per_face.items()}
    return dem_prof, per_face_dem


def merge_routes(ways: _t.Sequence, raw: _t.Mapping[int, tuple[int, float, float]],
                 xy: _t.Mapping[int, tuple[float, float]],
                 lateral_m: float, overlap_m: float, slack_m: float
                 ) -> tuple[dict[int, int], list[dict[str, _t.Any]]]:
    """§37 (10) (2) TWO ROUTES ARE ONE CARRIAGEWAY WHEN THEIR CORRIDORS
    INTERPENETRATE (owner RULINGS 2026-09-13cs item 4).

    ``raw`` is the per-vertex ``(route, s, t)`` answer before the merge.
    Two routes whose frames place vertices within ``lateral_m`` of each
    other over at least ``overlap_m`` of arc are ONE route: returns
    ``route -> the route it merges into`` and the named pairs.

    A 3 m ribbon at HECA carries route 5936 (a 40 m stub) and route 5934,
    so every pair across it read ``NOT_A_PAIR``, the section was never
    priced and the road stepped 1.30 m over 3.05 m (42.6 %) against a
    1.5 % cap.  ``NOT_A_PAIR`` must never be the answer for two vertices
    on ONE ribbon.

    THE MERGE IS ONE-WAY, INTO THE LONGER ROUTE, AND ONLY WHERE THE
    SHORTER ONE LIES INSIDE IT (every station of the shorter way within
    ``lateral_m + slack_m`` of the longer's line).  Without that test one
    6 m proximity chains route to route across a whole network and the
    stations of the survivor mean nothing; with it a crossing (two routes
    meeting at a point, no arc together) and two roads with ground
    between them stay two routes.
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    vs = [v for v in raw if v in xy]
    if len(vs) < 2:
        return {}, []
    pts = [Point(xy[v]) for v in vs]
    tree = STRtree(pts)
    span: dict[tuple[int, int], list[float]] = {}
    hits = tree.query(pts, predicate="dwithin", distance=lateral_m)
    for i, j in zip(hits[0].tolist(), hits[1].tolist()):
        if i == j:
            continue
        ra, sa, _ = raw[vs[i]]
        rb, sb, _ = raw[vs[j]]
        if ra == rb:
            continue
        span.setdefault((ra, rb), []).append(sa)
    cand: set[tuple[int, int]] = set()
    for (ra, rb), ss in span.items():
        if max(ss) - min(ss) >= overlap_m:
            cand.add((min(ra, rb), max(ra, rb)))
    if not cand:
        return {}, []

    def length(r: int) -> float:
        w = ways[r]
        return float(w.s[-1]) if len(w.s) else 0.0

    parent: dict[int, int] = {}

    def find(r: int) -> int:
        while parent.get(r, r) != r:
            parent[r] = parent.get(parent[r], parent[r])
            r = parent[r]
        return r

    named: list[dict[str, _t.Any]] = []
    order = sorted(cand, key=lambda p: -max(length(p[0]), length(p[1])))
    for ra, rb in order:
        a, b = find(ra), find(rb)
        if a == b:
            continue
        if length(a) < length(b):
            a, b = b, a
        line = ways[a].line
        wb = ways[b]
        far = max(line.distance(Point(float(x), float(y)))
                  for x, y in wb.xy)
        if far > lateral_m + slack_m:
            continue
        parent[b] = a
        named.append({"into": a, "into_ref": ways[a].ref,
                      "into_kind": ways[a].kind, "route": b,
                      "ref": wb.ref, "kind": wb.kind,
                      "length_m": round(length(b), 1),
                      "max_lateral_m": round(far, 2)})
    return {r: find(r) for r in parent}, named


def road_route_frame(pm: PlanarMap, law: Law, airport: Airport,
                     profiles=None) -> tuple[dict[int, tuple[int, float, float]],
                                             dict[str, _t.Any]]:
    """§37 (7) THE ROAD'S ROUTE FRAME — vertex -> ``(route id, station s,
    signed lateral t)`` for EVERY road-family ring vertex (owner RULINGS
    2026-09-13av).

    A road pair is priced ALONG THE ROUTE, never across the plan chord:
    ``s`` is the arclength along the road's own centreline — the SAME way
    the ramp reads its DEM on (an OSM way, a mapped route, or the face's
    own axis, ``airport/road_profile.core_profiles``) — and ``t`` the
    signed offset across it, so two kerbs of one section stand a road
    width apart in ``t`` and zero apart in ``s``.  Two vertices on
    DIFFERENT routes are NOT A PAIR (a switchback's two branches, 45 m
    apart in plan and 280 m apart along the road at KCLT ``dsf:pol51``);
    a vertex no way answers has no frame and keeps the chord law.

    DECKS ARE IN: §37 (6)'s deck exclusion is about the ramp TARGET (a
    deck's level is §33 (4)'s), not about how its pairs are priced.
    """
    from .road_profile import core_profiles
    if profiles is None:
        prof, per_face = core_profiles(airport, pm, law)
    elif isinstance(profiles, tuple):
        prof, per_face = profiles           # already unpacked by the caller
    else:
        prof, per_face = profiles, profiles.per_face
    from shapely.geometry import Point
    roads = _road_roles(law)
    rid = {id(w): i for i, w in enumerate(prof.all_ways)}
    out: dict[int, tuple[int, float, float]] = {}
    xy: dict[int, tuple[float, float]] = {}
    seen: set[int] = set()
    for fid, f in pm.faces.items():
        if f.role not in roads:
            continue
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                if v in seen:
                    continue
                seen.add(v)
                vx = pm.vertices[v]
                # THE FACE IS THE ROAD: a way running THROUGH the face
                # answers EVERY vertex of it whatever the lateral distance
                # (``road_profile``'s own rule for through-ways, the core's
                # lateral levelling).  The ramp TARGET reads them within
                # the face's answer radius, because a value must not be
                # borrowed from a road 40 m away; a STATION may be, and
                # must: the 174 KCLT vertices outside the radius were
                # exactly the outer kerbs of the wide pages whose pairs
                # then fell back to the chord law and kept the switchback
                # bound (measured: ``dsf:pol51`` v16836 unframed, cut
                # 6.75 m).
                through: list = []
                for g in vx.incident_faces:
                    through.extend((w, math.inf) for w, _r in per_face.get(g, ()))
                a = prof.answer(vx.xy, vx.dem_z or 0.0, through)
                if a.way is None:
                    continue
                out[v] = (rid.get(id(a.way), -1), float(a.s), float(a.t))
                xy[v] = vx.xy
    # §37 (10) (2): two routes on ONE ribbon are ONE carriageway.  The
    # merged route is RE-STATIONED on the survivor's own centreline, so
    # every reader — the pair law, the ramp's floor, the coverage join —
    # sees one route with one station axis and NOT_A_PAIR is never the
    # answer for two vertices of one ribbon.
    from .road_profile import _signed_offset
    rc = law.tables.emit.road_contact
    all_ways = prof.all_ways
    into, merged = merge_routes(all_ways, out, xy, rc.pair_lateral_m,
                                rc.pair_overlap_m, prof.lane_width_m)
    if into:
        lines = {r: all_ways[r].line for r in set(into.values())}
        for v, (r, s_, t_) in list(out.items()):
            dst = into.get(r)
            if dst is None:
                continue
            ln = lines[dst]
            p = Point(xy[v])
            s2 = float(ln.project(p))
            out[v] = (dst, s2, _signed_offset(ln, s2, xy[v]))
    rep = {"vertices": len(seen), "framed": len(out),
           "merged_routes": len(into), "merged_pairs": merged,
           "no_route": len(seen) - len(out), "routes": len(prof.all_ways),
           # the ways BY ROUTE ID, so a caller reads the clamp on the route
           # THIS frame names (§37 (8)) instead of asking for a second
           # nearest-way answer that can pick another way for the kerb
           "_ways": dict(enumerate(prof.all_ways))}
    return out, rep


def road_ramp_targets(pm: PlanarMap, law: Law, airport: Airport,
                      profiles=None) -> RampTargets:
    """§37 (6)'s target for every groundside-road vertex, AS A FUNCTION OF
    (ROUTE, STATION) ALONE — §37 (8)'s "the ramp target is the road's
    CENTRELINE profile per station" (owner RULINGS 2026-09-13bb).

    ``target(r, s) = max(clamp_r(s), envelope_r(s))``

    * ``clamp_r(s)`` — the core's own cap-Lipschitz profile at that station
      of THE ROUTE THE FRAME NAMES (§37 (6) amended, RULINGS 2026-09-13be),
      never a second nearest-way answer;
    * ``envelope_r(s)`` — the mouths' descent over the road's own graph,
      LIFTED ONTO THE ROUTE as the cap-Lipschitz upper envelope of the
      stations it reached.

    Both terms are cap-Lipschitz in ``s``, so two vertices of one section
    differ by at most ``cap_l × |Δs|`` — inside §37 (7)'s pair bound
    ``cap_l·|Δs| + cap_t·|Δt|`` — and the hard ceiling can no longer TILT a
    section.  MEASURED on the KCLT capture: of 2,155 cross-section pairs,
    145 carried targets over their own 2 % bound when the target was a
    per-VERTEX reading of the raw DEM (worst 3.51 m against 0.60 m), 129
    still did with the clamp read per vertex (worst 3.67 m over a 1.2 m
    station difference — the descent envelope and the floor were each read
    per vertex, and two kerbs of one station can sit on different graph
    distances and different nearest ways); per (route, station) it is 0 by
    construction.

    ONE derivation, called ONCE per build from :func:`with_road_ramp`,
    which publishes it as ``PlanarMap.road_ramp_z``; the generator
    (:func:`road_ramp_rows`) reads that channel.  ``profiles`` is the road
    profile set ``preferred_road_z`` already built for this map (same cap,
    same lane width); it is rebuilt here when absent.
    """
    roads = _road_roles(law)
    owned = _owned(pm, roads, law)
    mouths = _contacts(pm, roads, law)
    mouths = {v: z for v, z in mouths.items() if v not in owned}
    caps = [role_cap(law, r).longitudinal for r in roads if role_cap(law, r)]
    cap = min(caps) if caps else None
    rep: dict[str, _t.Any] = {"vertices": len(owned), "mouths": len(mouths),
                              "decks_excluded": len(deck_refs(pm)),
                              "cap": cap, "targets": 0, "on_dem": 0,
                              "on_ramp": 0, "no_contact": 0, "no_route": 0,
                              "max_above_dem_m": 0.0, "max_reach_m": 0.0,
                              "max_route_off_vertex_dem_m": 0.0,
                              "max_clamp_over_dem_m": 0.0,
                              "reach_contacts": 0, "reach_ends": []}
    if not owned or cap is None:
        return RampTargets({}, rep, {})
    prof_f, per_face_f = _floor_along_route(pm, law, airport, profiles)
    dem_prof, per_face_dem = _dem_twin(prof_f, per_face_f)
    frame, frep = road_route_frame(pm, law, airport, (prof_f, per_face_f))
    ways = frep.pop("_ways")
    rep["no_route"] = frep["no_route"]
    rep["merged_routes"] = frep.get("merged_routes", 0)
    rep["merged_pairs"] = frep.get("merged_pairs", [])
    rep["_merged"] = frozenset(m["into"] for m in rep["merged_pairs"])
    # §37 (10) (1): the contact a road does not TOUCH — the road ENDS
    # within reach of an airside face's edge and takes that face's level
    # there.  It is NOT a seed of this envelope: the level is the airside
    # EDGE's own column, which pre-solve nobody knows (at HECA ``pav74``
    # carries no published target and its DEM stands 1.4 m ABOVE the level
    # the solve gives it, so seeding the estimate RAISED ``route0``'s end
    # to 108.29 — measured, arm 1).  It is a ROW: see
    # ``constraints/road_ramp.road_contact_rows``.
    rc = law.tables.emit.road_contact
    contact, reach_named = reach_contacts(pm, law, owned, mouths, frame,
                                          rc.contact_reach_m,
                                          prof_f.lane_width_m)
    rep["reach_contacts"] = len(reach_named)
    rep["reach_governed"] = len(contact)
    rep["reach_ends"] = reach_named
    adj = _graph(pm, set(owned) | set(mouths))
    # THE HIGHER ENVELOPE OF THE MOUTHS (§37 (6)): ``g`` is the highest
    # level any mouth can still be at after descending at the cap along
    # the route — a max-label Dijkstra, exact because every hop only ever
    # LOWERS the label.
    g, reach = _dijkstra(adj, mouths, cap)
    # ONTO THE ROUTE (§37 (8)): per route, the cap-Lipschitz UPPER envelope
    # of the descent values at the stations that carry one — so the ramp is
    # ONE VALUE PER STATION and not one per vertex.
    by_route: dict[int, list[tuple[float, int]]] = {}
    for v in set(owned) | set(mouths):
        f_ = frame.get(v)
        if f_ is not None:
            by_route.setdefault(f_[0], []).append((f_[1], v))
    env: dict[int, dict[float, float]] = {}
    for r, items in by_route.items():
        items.sort()
        ss = [s_ for s_, _v in items]
        env[r] = _lift(ss, [g.get(v, -math.inf) for _s, v in items], cap)
    targets: dict[int, float] = {}
    for v in sorted(owned):
        vx = pm.vertices[v]
        f_ = frame.get(v)
        if f_ is None or vx.dem_z is None:
            continue
        r, st, _lat = f_
        w_ = ways.get(r)
        if w_ is None:
            continue
        floor = float(w_.at(st))              # the core's clamp AT THAT STATION
        ramp = env.get(r, {}).get(st, -math.inf)
        t = max(floor, ramp)
        targets[v] = t
        # the REPORT reads the terrain under the same station
        through_d: list = []
        for fid in vx.incident_faces:
            through_d.extend(per_face_dem.get(fid, ()))
        a_d = dem_prof.answer(vx.xy, float(vx.dem_z), through_d)
        dem_route = float(a_d.z)
        rep["max_route_off_vertex_dem_m"] = max(
            rep["max_route_off_vertex_dem_m"], abs(dem_route - float(vx.dem_z)))
        rep["max_clamp_over_dem_m"] = max(rep["max_clamp_over_dem_m"],
                                          abs(floor - dem_route))
        if v not in g:
            rep["no_contact"] += 1
        if ramp > floor + 1e-9:
            rep["on_ramp"] += 1
            rep["max_above_dem_m"] = max(rep["max_above_dem_m"], t - dem_route)
            rep["max_reach_m"] = max(rep["max_reach_m"], reach.get(v, 0.0))
        else:
            rep["on_dem"] += 1
    rep["targets"] = len(targets)
    rep["max_above_dem_m"] = round(rep["max_above_dem_m"], 3)
    rep["max_reach_m"] = round(rep["max_reach_m"], 1)
    rep["max_route_off_vertex_dem_m"] = round(rep["max_route_off_vertex_dem_m"], 3)
    rep["max_clamp_over_dem_m"] = round(rep.get("max_clamp_over_dem_m", 0.0), 3)
    rep["_frame_report"] = frep
    rep["_contact_edge"] = contact
    return RampTargets(targets, rep, frame)


def with_road_ramp(pm: PlanarMap, law: Law, airport: Airport,
                   report: dict[str, _t.Any] | None = None,
                   profiles=None) -> PlanarMap:
    """THE ONE DERIVATION SITE (§37 (6)): publish the ramp target as
    ``PlanarMap.road_ramp_z`` and WITHDRAW ``preferred_road_z``'s soft fit
    for every vertex it governs — one target per vertex, not two
    authorities in a weight contest.  The rows are the generator's
    (:func:`road_ramp_rows`).

    Runs LAST of the target channels (``pipeline/build.py``, and the same
    order in ``tools/v2_solve_replay.py``): a mouth's level is read from
    the airside's own published target where it carries one.
    """
    tg = road_ramp_targets(pm, law, airport, profiles)
    frame = tg.frame
    frep = tg.report.pop("_frame_report", {})
    frep.pop("_ways", None)            # the Way objects are not a report
    if report is not None:
        report.update(tg.report)
        report.update({f"frame_{k}": v for k, v in frep.items()})
    contact = tg.report.pop("_contact_edge", {})
    merged = tg.report.pop("_merged", frozenset())
    # §37 (10) (1) AT THE MOUTH THE LEVEL IS THE AIRSIDE'S, AND ONLY THE
    # AIRSIDE'S.  A road END that takes a reach contact carries the §37 (6)
    # ramp target too — the clamp of its own terrain, which at HECA
    # ``route0`` is 108.29 while ``pav74``'s edge solves at 106.77 — and
    # the two are priced at the SAME ``[design] law`` weight, so the end
    # split the difference and landed 0.70 m short of the contact
    # (measured, arm 3).  A weight contest is not a law: the target is
    # WITHDRAWN over the end group (route distance under one lane width,
    # where the contact row's own allowance ``cap x s`` is under 0.32 m),
    # exactly as ``preferred_road_z`` is withdrawn under the ramp.
    lane = float(law.tables.emit.road_profile.lane_width_m)
    at_mouth = {v for v, (_a, _b, _u, s_) in contact.items() if s_ <= lane}
    targets = {v: z for v, z in tg.targets.items() if v not in at_mouth}
    if report is not None:
        report["contact_mouth_withdrawn"] = len(tg.targets) - len(targets)
    keep = {v: z for v, z in pm.preferred_z.items() if v not in tg.targets}
    if report is not None:
        report["preferred_withdrawn"] = len(pm.preferred_z) - len(keep)
    return _dc.replace(pm, road_ramp_z=targets, road_route_frame=frame,
                       road_contact_edge=contact, road_route_merged=merged,
                       preferred_z=keep)
