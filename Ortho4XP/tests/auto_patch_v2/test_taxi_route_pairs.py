"""Twins for RULINGS 2026-09-05ac (the 05aa/05ab law stated by the
CHAIN; spec §8/§9; lane v2relaxfull7): the taxi grade law is the route
graph's own edges as rows — centreline edges, lateral hops, crossings —
and NO pair row.  A bent stub: the chain implies every pair within its
route budget (the LP can push a pair exactly to Σ cap·len along its
route, never past it, and never to the chord reading); a straight
stretch: the bound between two stations is identical to the old chord
row; the row count is a fraction of the pair formulation; the publication
and the verify reader carry the solver's route budgets; a hop on an apron
face is an apron row the relaxation admits, a taxiway's is not.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.optimize import linprog
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, taxi
from auto_patch_v2.constraints.geometry import polyline_length
from auto_patch_v2.constraints.routes import (CENTRELINE, CROSSING, LATERAL,
                                              route_path, routes)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication, taxi_route_pairs
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import relax
from auto_patch_v2.solve.highs import Options, Status, solve
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import route_pair_budgets, within_shape

from test_routes import _RampDem, _rect, _vid, loop  # noqa: F401  (the apron fixture)

#: The hook: north from the runway edge, east, then back south — 777 m of
#: centreline for a 310 m chord between its ends (ratio 0.40).
HOOK = [(0.0, 22.5), (0.0, 300.0), (300.0, 300.0), (300.0, 100.0)]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def hook(law):
    """A runway; the HOOK stub (its centreline every vertex of ``HOOK``);
    and an L-shaped ORPHAN stub at x = −300 with NO centreline at all
    (nothing to attach to: no node, no hop, no taxi row)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    poly = orient(LineString(HOOK).buffer(11.5, cap_style=2, join_style=2), 1.0)
    ring = tuple((round(x, 6), round(y, 6)) for x, y in list(poly.exterior.coords)[:-1])
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "hook", ring, (), None, "D", "airside", "taxi", {}),
        Cell(2, "stub", "orphan", ((-311.5, 22.5), (-288.5, 22.5), (-288.5, 177.0),
                                   (-200.0, 177.0), (-200.0, 200.0), (-311.5, 200.0)),
             (), None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "hook", ((0.0, 0.0), *HOOK)),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _taxi_diffs(pm, law, airport) -> list[Diff]:
    """The chain as the solve states it: hops + crossings, centreline edges."""
    return [*taxi.taxi_chain(pm, law, airport), *taxi.taxi_centerlines(pm, law, airport)]


def _push(pm, rows: list[Diff], a: int, b: int) -> float:
    """``max z_a − z_b`` subject to the rows alone (an LP over the pair's
    reach through the chain): the bound the chain IMPLIES for the pair."""
    n = len(pm.vertices)
    m = len(rows)
    A = np.zeros((2 * m, n))
    ub = np.zeros(2 * m)
    for k, r in enumerate(rows):
        A[2 * k, r.a], A[2 * k, r.b] = 1.0, -1.0
        A[2 * k + 1, r.a], A[2 * k + 1, r.b] = -1.0, 1.0
        ub[2 * k] = ub[2 * k + 1] = r.bound_m
    c = np.zeros(n)
    c[a], c[b] = -1.0, 1.0
    res = linprog(c, A_ub=A, b_ub=ub, bounds=[(-1e4, 1e4)] * n, method="highs")
    assert res.status == 0, res.message
    return float(-res.fun)


def test_every_taxi_row_is_a_route_edge_and_no_pair_row_exists(hook, law):
    """05ac: the taxi generator's rows ARE the graph's edges — one per
    lateral hop and crossing (``taxi_chain``), one per centreline edge
    (``taxi_centerlines``) — at the edge's own budget; no row joins two
    vertices the graph does not join directly."""
    airport, pm = hook
    g = routes(pm, law, airport)
    edges = {(int(a), int(b)): (float(cap * ln), int(k))
             for a, b, cap, ln, k in zip(g.a, g.b, g.cap, g.length, g.kind)}
    chain = taxi.taxi_chain(pm, law, airport)
    assert chain
    seen = set()
    for r in chain:
        key = (min(r.a, r.b), max(r.a, r.b))
        assert key in edges and edges[key][1] in (LATERAL, CROSSING), key
        assert r.bound_m == pytest.approx(edges[key][0], abs=1e-9)
        assert r.source.generator == "taxi" and "chain" in r.source.ruling
        assert r.source.inputs and r.source.inputs[0].startswith("face:")
        seen.add(key)
    assert len(seen) == len(chain) == g.stats["lateral"] + g.stats["crossing"]
    for r in taxi.taxi_centerlines(pm, law, airport):
        key = (min(r.a, r.b), max(r.a, r.b))
        assert key in edges and edges[key][1] == CENTRELINE, key
    assert not hasattr(taxi, "taxi_within_shape"), "the pair generator is gone (05ac)"


def test_bent_stub_the_chain_implies_every_pair_within_its_route_budget(hook, law):
    """§9 by the chain: between the hook's start and end stations the LP
    can push the pair EXACTLY to cap × the CENTRELINE length (every bend
    followed) — more than twice the withdrawn chord reading — and every
    routed pair of the hook is bound by Σ cap·len along its route, each
    edge of that route being a row."""
    airport, pm = hook
    start, end = _vid(pm, 0.0, 22.5), _vid(pm, 300.0, 100.0)
    cap = role_cap(law, "stub", None, "D").longitudinal
    chord = math.hypot(300.0, 100.0 - 22.5)
    centre = polyline_length(HOOK)
    assert chord < 0.5 * centre
    rows = _taxi_diffs(pm, law, airport)
    pushed = _push(pm, rows, start, end)
    assert pushed == pytest.approx(cap * centre, abs=1e-6)
    assert pushed > 2.0 * cap * chord
    g = routes(pm, law, airport)
    bound = {(min(r.a, r.b), max(r.a, r.b)): r.bound_m for r in rows}
    hook_ids = {f.id for f in pm.faces.values() if f.ref == "hook"}
    pairs = [pp for pp in taxi.taxi_pair_routes(pm, law, airport) if pp.face in hook_ids]
    assert pairs and all(pp.routed for pp in pairs)
    for pp in pairs:
        dist, budget, path = route_path(g, pp.a, pp.b)
        assert dist == pytest.approx(pp.dist) and budget == pytest.approx(pp.budget)
        along = sum(bound[(min(u, v), max(u, v))] for u, v in zip(path, path[1:]))
        assert along == pytest.approx(budget, abs=1e-9)      # every edge of the route is a row
    # the pushed bound of a sample of pairs equals its route budget (the
    # chain neither over- nor under-states the route reading)
    for pp in sorted(pairs, key=lambda q: -q.d_chord)[:6]:
        assert _push(pm, rows, pp.a, pp.b) == pytest.approx(pp.budget, abs=1e-6)


def test_straight_stretch_the_bound_is_the_old_chord(hook, law):
    """On the hook's straight first leg (x = 0, 22.5 → 300) the chain's
    bound between the two end stations is cap × their distance — the
    withdrawn chord row's own bound, unchanged; a hop off the leg adds
    its transverse budget and nothing else."""
    airport, pm = hook
    rows = _taxi_diffs(pm, law, airport)
    cap = role_cap(law, "stub", None, "D")
    s0, s1 = _vid(pm, 0.0, 22.5), _vid(pm, 0.0, 300.0)
    assert _push(pm, rows, s0, s1) == pytest.approx(cap.longitudinal * 277.5, abs=1e-6)
    stations = sorted((v for v, vv in pm.vertices.items()
                       if abs(vv.xy[0]) < 1e-6 and 22.5 <= vv.xy[1] <= 300.0),
                      key=lambda v: pm.vertices[v].xy[1])
    for u, v in zip(stations, stations[1:]):
        d = pm.vertices[v].xy[1] - pm.vertices[u].xy[1]
        assert _push(pm, rows, u, v) == pytest.approx(cap.longitudinal * d, abs=1e-6)
    # the west-edge corner of the leg (a stub AND a runway ring vertex: one
    # hop per face): the stub's hop is transverse × 11.5, straight across
    g = routes(pm, law, airport)
    edge_v = _vid(pm, -11.5, 22.5)
    hop = [(int(a), int(b), float(c), float(ln), int(f))
           for a, b, c, ln, k, f in zip(g.a, g.b, g.cap, g.length, g.kind, g.face)
           if k == LATERAL and edge_v in (a, b)]
    stub_hop = [h for h in hop if pm.faces[h[4]].role == "stub"]
    assert len(stub_hop) == 1 and len(hop) == 2
    _a, _b, c, ln, _f = stub_hop[0]
    assert ln == pytest.approx(11.5) and c * ln == pytest.approx(cap.transverse * 11.5, abs=1e-6)


def test_the_chain_is_a_fraction_of_the_pair_formulation(hook, law):
    """The row count: hops + crossings + centreline edges against the
    pair population the reader prices (every pair of every ring)."""
    airport, pm = hook
    rows = _taxi_diffs(pm, law, airport)
    pairs = taxi.taxi_pair_routes(pm, law, airport)
    assert 0 < len(rows) < len(pairs) / 3
    cs, counts, _w = generate(pm, law, airport)
    assert counts["taxi_chain"] == len(taxi.taxi_chain(pm, law, airport))
    assert "taxi_within_shape" not in counts


def test_an_orphan_has_no_hop_and_no_taxi_row(hook, law):
    """The orphan L attaches to nothing — no node, no hop, no taxi row on
    its own rim; the publication names its pairs ``null`` and the verify
    reader skips them (no law edge, 05ab)."""
    airport, pm = hook
    orphan = _face(pm, "orphan")
    g = routes(pm, law, airport)
    on_runway = {v for f in pm.faces.values() if f.role == "runway"
                 for v in pm.ring_vertices(f.ring)}
    verts = set(pm.ring_vertices(orphan.ring))
    loose = verts - on_runway
    assert loose and not (loose & g.nodes)
    for r in _taxi_diffs(pm, law, airport):
        assert r.a not in loose and r.b not in loose
    pairs = [pp for pp in taxi.taxi_pair_routes(pm, law, airport) if pp.face == orphan.id]
    unrouted = [pp for pp in pairs if not pp.routed]
    assert pairs and unrouted and all(pp.a in loose or pp.b in loose for pp in unrouted)
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    pub = publication(pm, law, airport, sol.z)
    nulls = [e for e in pub["taxi_route_pairs"] if e[2] is None]
    all_unrouted = [pp for pp in taxi.taxi_pair_routes(pm, law, airport) if not pp.routed]
    assert len(nulls) == len(all_unrouted) >= len(unrouted)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    patch = Patch.of(surf, law, pub, {})
    routed = route_pair_budgets(patch)
    assert all(routed.get((min(pp.a, pp.b), max(pp.a, pp.b)), 1) is None for pp in unrouted)
    within, xsec = within_shape(patch)
    assert within == [] and xsec == []


def test_verify_reads_the_solvers_route_budgets(hook, law):
    """The reader prices exactly the solver's budgets: every published
    routed pair carries the route budget of ``taxi_pair_routes``; the
    pruned publication (tighter pairs always, looser pairs only where the
    surface exceeds the chord) reads IDENTICALLY to publishing every pair
    — on the solved surface and on a surface pushed to the route bound."""
    airport, pm = hook
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    tol = law.tables.emit.materiality.elevation_m
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    pps = {(min(pp.a, pp.b), max(pp.a, pp.b)): pp for pp in taxi.taxi_pair_routes(pm, law, airport)}
    routed = route_pair_budgets(Patch.of(surf, law, pub, {}))
    for k, rec in routed.items():
        if rec is not None:
            assert k in pps and rec[0] == pytest.approx(pps[k].budget, abs=1e-5)
    ll = {v: pub_ll for v, pub_ll in _ll_of(pm, airport).items()}
    full = [[ll[pp.a], ll[pp.b], None, None] if not pp.routed
            else [ll[pp.a], ll[pp.b], round(pp.budget, 6), round(pp.dist, 4)]
            for pp in pps.values() if not pp.routed or abs(pp.budget - pp.chord_bound_m) > tol]
    pruned = taxi_route_pairs(pm, law, airport, sol.z, ll, tol)
    assert len(pruned) < len(full)
    tighter = {(min(pp.a, pp.b), max(pp.a, pp.b)) for pp in pps.values()
               if pp.routed and pp.budget < pp.chord_bound_m - tol}
    assert tighter <= set(routed), "every tighter pair is published"
    for z in (sol.z, _pushed_surface(pm, law, airport, sol.z)):
        s2 = graded_surface(pm, law, _with_z(sol, z), airport.frame.origin, airport.frame.crs)
        p_full = dict(pub); p_full["taxi_route_pairs"] = full
        p_pruned = dict(pub); p_pruned["taxi_route_pairs"] = taxi_route_pairs(pm, law, airport, z, ll, tol)
        w_full, _x = within_shape(Patch.of(s2, law, p_full, {}))
        w_pruned, _x = within_shape(Patch.of(s2, law, p_pruned, {}))
        assert sorted((r["magnitude_m"], r["distance_m"]) for r in w_full) == \
            sorted((r["magnitude_m"], r["distance_m"]) for r in w_pruned)


def _ll_of(pm, airport):
    _to_xy, to_ll = airport.frame.transformers()
    dp = airport.frame.identity_dp
    out = {}
    for v, vv in pm.vertices.items():
        la, lo = to_ll(*vv.xy)
        out[v] = [round(la, dp), round(lo, dp)]
    return out


def _with_z(sol, z):
    import dataclasses
    return dataclasses.replace(sol, z=tuple(float(x) for x in z))


def _pushed_surface(pm, law, airport, z0):
    """The hook's start/end pair pushed to its route bound (the LP of
    ``_push`` with every chain row): a lawful surface the CHORD reading
    would flag, so the pruned publication has to carry the pair."""
    rows = _taxi_diffs(pm, law, airport)
    start, end = _vid(pm, 0.0, 22.5), _vid(pm, 300.0, 100.0)
    n = len(pm.vertices)
    m = len(rows)
    A = np.zeros((2 * m, n)); ub = np.zeros(2 * m)
    for k, r in enumerate(rows):
        A[2 * k, r.a], A[2 * k, r.b] = 1.0, -1.0
        A[2 * k + 1, r.a], A[2 * k + 1, r.b] = -1.0, 1.0
        ub[2 * k] = ub[2 * k + 1] = r.bound_m
    c = np.zeros(n); c[start], c[end] = -1.0, 1.0
    z0 = np.asarray(z0, float)
    res = linprog(c, A_ub=A, b_ub=ub, bounds=[(zi - 50.0, zi + 50.0) for zi in z0], method="highs")
    assert res.status == 0, res.message
    return res.x


def test_a_hop_on_an_apron_is_an_apron_row_the_relaxation_admits(loop, law):
    """The chain row's tier is the FACE's: an apron vertex's hop to the
    taxilane touching it cites ``common.roles.apron`` and ``relaxable``
    admits it (04t-1); a taxiway rim's hop cites the taxi ruleset and is
    refused."""
    airport, pm = loop
    chain = taxi.taxi_chain(pm, law, airport)
    apron = [r for r in chain if r.source.ruling.startswith("common.roles.apron")]
    stub = [r for r in chain if r.source.ruling.startswith("rulesets.taxi.transverse")]
    assert apron and stub
    apron_cap = law.tables.common.roles["apron"].transverse
    assert all(pm.faces[int(r.source.inputs[0][5:])].role == "apron" for r in apron)
    admitted = relax.relaxable(pm, law, apron + stub)
    got = {id(x.row) for x in admitted}
    assert all(id(r) in got for r in apron)
    assert not any(id(r) in got for r in stub)
    # a hop straight across (no centreline walk) is priced at the apron cap
    g = routes(pm, law, airport)
    assert any(abs(c - apron_cap) < 1e-12 for c, k in zip(g.cap, g.kind) if k == LATERAL)
