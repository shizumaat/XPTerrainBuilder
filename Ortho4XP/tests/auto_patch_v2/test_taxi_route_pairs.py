"""Twins for RULINGS 2026-09-05ab / spec §9 (lane v2relaxfull6): a taxi
within-shape pair is priced over the CENTRELINE ROUTE — a bent stub
whose chord is under half its centreline prices the centreline, never
the chord; a pair no route joins has no row; the publication and the
verify reader carry exactly the solver's budgets.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, taxi
from auto_patch_v2.constraints.geometry import polyline_length
from auto_patch_v2.constraints.routes import routes
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.highs import Options, Status, solve
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import route_pair_budgets, within_shape

from test_routes import _RampDem, _rect, _vid

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
    (nothing to attach to: no node, no route — a chord that leaves the
    L has no row, a chord inside it keeps the plane rule)."""
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
        # an L: north from the runway, then east — its long diagonal leaves
        # the pavement, its short chords stay inside
        Cell(2, "stub", "orphan", ((-311.5, 22.5), (-288.5, 22.5), (-288.5, 177.0),
                                   (-200.0, 177.0), (-200.0, 200.0), (-311.5, 200.0)),
             (), None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "hook", ((0.0, 0.0), *HOOK)),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def test_bent_stub_prices_the_centreline_never_the_chord(hook, law):
    """§9 twin: between the hook's start and end stations — a chord that
    leaves the pavement — the within-shape row's bound is cap × the
    CENTRELINE length (every bend followed), not cap × the chord that
    is under half of it; a chord inside the hook keeps the plane rule."""
    airport, pm = hook
    start, end = _vid(pm, 0.0, 22.5), _vid(pm, 300.0, 100.0)
    cap = role_cap(law, "stub", None, "D").longitudinal
    chord = math.hypot(300.0, 100.0 - 22.5)
    centre = polyline_length(HOOK)
    assert chord < 0.5 * centre
    rows = [r for r in taxi.taxi_within_shape(pm, law, airport) if {r.a, r.b} == {start, end}]
    assert rows == [], "no chord row across open ground, and a looser route states none"
    # the centreline cut splits the stub into a face per side; both hold the pair
    hook_faces = [f.id for f in pm.faces.values() if f.ref == "hook"]
    pps = [pp for pp in taxi.taxi_pair_routes(pm, law, airport)
           if {pp.a, pp.b} == {start, end} and pp.face in set(hook_faces)]
    assert 1 <= len(pps) == len(hook_faces)
    for pp in pps:
        assert pp.routed and not pp.in_face and not pp.priced
        assert pp.dist == pytest.approx(centre, abs=1.0)            # the route, not the chord
        assert pp.budget == pytest.approx(cap * centre, abs=cap * 1.0)
        assert pp.budget > cap * chord * 2.0
    hook_ids = set(hook_faces)
    pairs = [pp for pp in taxi.taxi_pair_routes(pm, law, airport) if pp.face in hook_ids]
    assert pairs and all(pp.routed for pp in pairs)
    assert all(pp.dist >= pp.d_chord - 1e-6 for pp in pairs)
    leaving = [pp for pp in pairs if not pp.in_face]
    staying = [pp for pp in pairs if pp.in_face]
    assert leaving and staying
    assert any({pp.a, pp.b} == {start, end} for pp in leaving)
    by_pair = {(min(r.a, r.b), max(r.a, r.b)): r for r in taxi.taxi_within_shape(pm, law, airport)
               if r.source.inputs[0] in {f"face:{i}" for i in hook_ids}}
    for pp in staying:                       # the plane rule, unchanged
        r = by_pair[(min(pp.a, pp.b), max(pp.a, pp.b))]
        assert r.d == pytest.approx(pp.d_chord) and r.cap == pytest.approx(pp.cap_chord)
    for pp in leaving:                       # the route: a row only where stricter
        r = by_pair.get((min(pp.a, pp.b), max(pp.a, pp.b)))
        if pp.budget < pp.cap_chord * pp.d_chord:
            assert r is not None and r.d == pytest.approx(pp.dist) \
                and r.bound_m == pytest.approx(pp.budget, abs=1e-6)
        else:
            assert r is None


def test_a_pair_no_route_joins_has_no_row_and_publishes_null(hook, law):
    """§9 twin: the orphan L attaches to nothing — no node, no route: a
    pair whose chord leaves the L gets no within-shape row (the
    publication names it ``null``, the verify reader skips it); a pair
    whose chord stays inside keeps the plane rule."""
    airport, pm = hook
    orphan = _face(pm, "orphan")
    g = routes(pm, law, airport)
    on_runway = {v for f in pm.faces.values() if f.role == "runway"
                 for v in pm.ring_vertices(f.ring)}
    verts = set(pm.ring_vertices(orphan.ring))
    loose = verts - on_runway                     # its own rim: nothing to attach to
    assert loose and not (loose & g.nodes)
    assert verts & on_runway <= g.nodes           # the runway-edge corners hop to the ridge
    pairs = [pp for pp in taxi.taxi_pair_routes(pm, law, airport) if pp.face == orphan.id]
    unrouted = [pp for pp in pairs if not pp.routed]
    assert pairs and unrouted and all(pp.a in loose or pp.b in loose for pp in unrouted)
    leaving = [pp for pp in unrouted if not pp.in_face]
    staying = [pp for pp in unrouted if pp.in_face]
    assert leaving and staying
    corner_n, corner_e = _vid(pm, -311.5, 22.5), _vid(pm, -200.0, 177.0)
    assert any({pp.a, pp.b} == {corner_n, corner_e} for pp in leaving)
    rows = {(min(r.a, r.b), max(r.a, r.b)): r for r in taxi.taxi_within_shape(pm, law, airport)
            if r.source.inputs[0] == f"face:{orphan.id}"}
    assert not any((min(pp.a, pp.b), max(pp.a, pp.b)) in rows for pp in leaving)
    assert all((min(pp.a, pp.b), max(pp.a, pp.b)) in rows for pp in staying)
    unrouted = leaving
    all_unrouted = [pp for pp in taxi.taxi_pair_routes(pm, law, airport)
                    if not pp.routed and not pp.in_face]
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    pub = publication(pm, law, airport, sol.z)
    nulls = [e for e in pub["taxi_route_pairs"] if e[2] is None]
    assert len(nulls) == len(all_unrouted) >= len(unrouted)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    patch = Patch.of(surf, law, pub, {})
    routed = route_pair_budgets(patch)
    assert all(routed.get((min(pp.a, pp.b), max(pp.a, pp.b)), 1) is None for pp in unrouted)
    # the solve honoured the route budgets; the reader prices them alike
    within, xsec = within_shape(patch)
    assert within == [] and xsec == []


def test_verify_reads_the_solvers_route_budgets(hook, law):
    """§9 twin: every published route pair carries the solver's own bound;
    a hook pair whose route budget differs from the chord reading is
    published, one on a straight run (chord = route) is not."""
    airport, pm = hook
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    pub = publication(pm, law, airport, sol.z)
    tol = law.tables.emit.materiality.elevation_m
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    routed = route_pair_budgets(Patch.of(surf, law, pub, {}))
    by_pair = {(min(r.a, r.b), max(r.a, r.b)): r for r in taxi.taxi_within_shape(pm, law, airport)}
    pps = {(min(pp.a, pp.b), max(pp.a, pp.b)): pp for pp in taxi.taxi_pair_routes(pm, law, airport)}
    start, end = _vid(pm, 0.0, 22.5), _vid(pm, 300.0, 100.0)
    key = (min(start, end), max(start, end))
    assert key in routed and routed[key] is not None
    assert routed[key][0] == pytest.approx(pps[key].budget, abs=1e-5)
    for k, rec in routed.items():
        if rec is not None:
            assert k in pps and rec[0] == pytest.approx(pps[k].budget, abs=1e-5)
            if k in by_pair:
                assert rec[0] == pytest.approx(by_pair[k].bound_m, abs=1e-5)
    assert routed, "the hook's leaving chords are published"
    # a pair of consecutive stations on the straight first leg: chord = route
    a, b = _vid(pm, 0.0, 22.5), None
    for v, vv in pm.vertices.items():
        if abs(vv.xy[0]) < 1e-6 and 22.5 < vv.xy[1] < 300.0 and v in cs_vertices(by_pair):
            b = v
            break
    assert b is not None
    k = (min(a, b), max(a, b))
    assert k in by_pair and abs(by_pair[k].bound_m - by_pair[k].cap * by_pair[k].d) < tol
    assert k not in routed


def cs_vertices(by_pair):
    out = set()
    for a, b in by_pair:
        out.add(a); out.add(b)
    return out
