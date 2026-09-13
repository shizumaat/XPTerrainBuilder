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

    target(s) = max(DEM(s), z_contact - road_cap * s)

It descends at the road's own longitudinal cap until it meets the DEM and
follows the DEM from there (and climbs at the cap where the DEM rises
above the contact); between two contacts the two ramps meet at their
HIGHER envelope; a road with NO airside contact targets the DEM.  The
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
from ..law.tables import family, role_cap, role_side, senior_role
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["deck_refs", "road_ramp_targets", "with_road_ramp", "RampTargets"]

class RampTargets(_t.NamedTuple):
    """The derivation's product: ``targets`` vertex id -> the ramp target,
    ``report`` the figures the build log and the spec's MEASURED block
    quote."""

    targets: dict[int, float]
    report: dict[str, _t.Any]


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
                dem = pm.vertices[v].dem_z
                cands = [z for z in (pm.apron_trend_z.get(v),
                                     pm.taxi_trend_z.get(v),
                                     pm.preferred_z.get(v)) if z is not None]
                if dem is not None:
                    cands.append(float(dem))
                if cands:
                    out[v] = max(float(z) for z in cands)
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


def _dem_along_route(pm: PlanarMap, law: Law, airport: Airport,
                     profiles=None):
    """``vertex -> the DEM ALONG THE ROAD'S OWN CENTRELINE`` at that
    vertex's projection, and the vertices no way answers.

    THE DEM IS READ ALONG THE ROUTE, NEVER UNDER THE KERB.  A road page on
    a side slope spans the hill transversely — KCLT's ``dsf:pol51`` carries
    DEM samples from 199.91 to 216.55 m across 48 m of one page — and the
    road cross-section law (2 %) forbids a ribbon that tilts with it.  A
    per-vertex DEM target is therefore transversely INFEASIBLE and the
    solve answers it with a cut: the first arm of this rule measured
    ``dsf:pol51`` fill +10.90 -> +0.50 m and cut 2.40 -> **7.43 m**.  §37
    (6)'s ``DEM(s)`` is the terrain at ROUTE STATION s, and every vertex of
    the section takes it — the core's own lateral levelling
    (``airport/road_profile.py``), read here off the SAME ways, the SAME
    projection and the SAME answer rule, with the clamped profile ``z``
    swapped for the terrain ``dem`` the clamp was built from.
    """
    from .road_profile import RoadProfiles, core_profiles
    if profiles is None:
        prof, per_face = core_profiles(airport, pm, law)
    else:
        # the SAME profiles ``preferred_road_z`` built for this map (it
        # carries its own ``per_face`` answer index): read, never rebuilt
        prof, per_face = profiles, profiles.per_face
    twin = {id(w): _dc.replace(w, z=w.dem) for w in prof.all_ways}
    dem_prof = RoadProfiles(prof.cap, prof.station_m, prof.lane_width_m,
                            prof.radius_m,
                            tuple(twin[id(w)] for w in prof.ways))
    dem_prof.axes = {fid: twin[id(w)] for fid, w in prof.axes.items()}
    per_face_dem = {fid: [(twin[id(w)], r) for w, r in lst]
                    for fid, lst in per_face.items()}
    return dem_prof, per_face_dem


def road_ramp_targets(pm: PlanarMap, law: Law, airport: Airport,
                      profiles=None) -> RampTargets:
    """§37 (6)'s target for every groundside-road vertex (module docstring).

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
                              "max_route_off_vertex_dem_m": 0.0}
    if not owned or cap is None:
        return RampTargets({}, rep)
    dem_prof, per_face_dem = _dem_along_route(pm, law, airport, profiles)
    adj = _graph(pm, set(owned) | set(mouths))
    # THE HIGHER ENVELOPE OF THE MOUTHS (§37 (6)): ``g`` is the highest
    # level any mouth can still be at after descending at the cap along
    # the route — a max-label Dijkstra, exact because every hop only ever
    # LOWERS the label.
    g: dict[int, float] = {}
    pq: list[tuple[float, int]] = []
    for v, z in mouths.items():
        if g.get(v, -math.inf) < z:
            g[v] = z
            heapq.heappush(pq, (-z, v))
    reach: dict[int, float] = {v: 0.0 for v in mouths}
    while pq:
        nz, u = heapq.heappop(pq)
        z = -nz
        if z < g.get(u, -math.inf) - 1e-9:
            continue
        for w, d in adj.get(u, ()):
            zw = z - cap * d
            if zw > g.get(w, -math.inf) + 1e-9:
                g[w] = zw
                reach[w] = reach.get(u, 0.0) + d
                heapq.heappush(pq, (-zw, w))
    targets: dict[int, float] = {}
    for v in sorted(owned):
        vx = pm.vertices[v]
        if vx.dem_z is None:
            continue
        through: list = []
        for fid in vx.incident_faces:
            through.extend(per_face_dem.get(fid, ()))
        a = dem_prof.answer(vx.xy, float(vx.dem_z), through)
        dem = float(a.z)
        if a.kind is None:
            rep["no_route"] += 1
        else:
            rep["max_route_off_vertex_dem_m"] = max(
                rep["max_route_off_vertex_dem_m"], abs(dem - float(vx.dem_z)))
        ramp = g.get(v)
        if ramp is None:
            rep["no_contact"] += 1
            targets[v] = dem
            continue
        t = max(dem, ramp)
        targets[v] = t
        if t > dem + 1e-9:
            rep["on_ramp"] += 1
            rep["max_above_dem_m"] = max(rep["max_above_dem_m"], t - dem)
            rep["max_reach_m"] = max(rep["max_reach_m"], reach.get(v, 0.0))
        else:
            rep["on_dem"] += 1
    rep["targets"] = len(targets)
    rep["max_above_dem_m"] = round(rep["max_above_dem_m"], 3)
    rep["max_reach_m"] = round(rep["max_reach_m"], 1)
    rep["max_route_off_vertex_dem_m"] = round(rep["max_route_off_vertex_dem_m"], 3)
    return RampTargets(targets, rep)


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
    if report is not None:
        report.update(tg.report)
    keep = {v: z for v, z in pm.preferred_z.items() if v not in tg.targets}
    if report is not None:
        report["preferred_withdrawn"] = len(pm.preferred_z) - len(keep)
    return _dc.replace(pm, road_ramp_z=tg.targets, preferred_z=keep)
