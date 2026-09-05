"""Twins for the ROUTE law (lane v2route; RULINGS 2026-09-04o / 04q):
the route graph (service excluded, centrelines first-class), route-
distance no-step pairs against chord pairs on an apron beside a runway
joined only by a long taxi loop, the pair budget as Σ cap·len along the
path, the reach bands as the envelope the hard rows imply, the junction
code letter inherited from the chains it serves, and the sidecar /
verify population equality.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest

from auto_patch_v2.classify import classify
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, no_step
from auto_patch_v2.constraints.routes import (CENTRELINE, build_routes, reach,
                                              route_neighbours, route_path,
                                              route_roles, routes)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import REACH_GENERATOR, Band, ConstraintSet
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve.highs import solve
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.no_step import no_step_direct

from test_classify import _synthetic as classify_airport


class _RampDem:
    """2 % climbing away from the runway."""

    provenance = {"synthetic": "plane 2 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.02 * max(0.0, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def loop(law):
    """A runway; an apron 17.5 m north of its edge (a CHORD well inside
    the 150 m window) that no pavement joins to it directly — its only
    route is a stub up at x = 500, a parallel taxiway west to x = −100
    and a stub down into the apron: ~830 m of pavement.  A service road
    hugs the apron's west side."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubE", _rect(488.5, 22.5, 511.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-120, 190, 520, 213), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "stub", "stubW", _rect(-111.5, 140, -88.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(4, "apron", "apron1", _rect(-200, 40, 0, 140), (), None, None,
             "airside", "apron", {}),
        Cell(5, "service_road", "road1", _rect(-230, 40, -200, 140), (), None,
             None, "groundside", "road", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubE", ((500.0, 0.0), (500.0, 201.5))),
            CutLine("taxi_centerline", "taxiA", ((-100.0, 201.5), (500.0, 201.5))),
            CutLine("taxi_centerline", "stubW", ((-100.0, 100.0), (-100.0, 201.5))),
            CutLine("road_centerline", "road1", ((-215.0, 40.0), (-215.0, 140.0))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _verts_of_role(pm, role):
    return {v for f in pm.faces.values() if f.role == role
            for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}


def test_route_graph_excludes_service_and_carries_centrelines(loop, law):
    _airport, pm = loop
    g = build_routes(pm, law)
    assert "service_road" not in route_roles(law) and "runway" in route_roles(law)
    road = _verts_of_role(pm, "service_road") - _verts_of_role(pm, "apron")
    assert road and not (road & g.nodes), "service roads are no airside route"
    # every taxi-centreline edge is a graph edge, marked as such
    centre = {e.length_key for e in pm.edges.values()
              if e.kind.value == "centerline"
              and any(pm.faces[f].role != "service_road" for f in pm.faces_of_edge(e.id))}
    on_graph = {(int(a), int(b)) for a, b, k in zip(g.a, g.b, g.kind) if k == CENTRELINE}
    assert centre and centre <= on_graph
    assert g.stats["nodes"] == len(g.nodes) and g.stats["edges"] == len(g.a)
    assert np.all(g.cap > 0) and np.all(g.length > 0)


def test_chord_pair_does_not_exist_but_the_route_pair_does(loop, law):
    _airport, pm = loop
    g = routes(pm, law)
    apron_south = sorted(v for v in _verts_of_role(pm, "apron") if abs(pm.vertices[v].xy[1] - 40.0) < 1e-6)
    rw_north = sorted(v for v in _verts_of_role(pm, "runway") if abs(pm.vertices[v].xy[1] - 22.5) < 1e-6
                      and -200 <= pm.vertices[v].xy[0] <= 0)
    assert apron_south and rw_north
    a = apron_south[0]
    b = min(rw_north, key=lambda u: abs(pm.vertices[u].xy[0] - pm.vertices[a].xy[0]))
    chord = math.hypot(*(np.subtract(pm.vertices[a].xy, pm.vertices[b].xy)))
    assert chord < law.tables.emit.no_step.window_m          # a chord pair WOULD have existed
    assert route_path(g, a, b, max_len=law.tables.emit.no_step.window_m) is None
    d, bud, path = route_path(g, a, b)
    assert d > 700.0 and bud > 0.0 and path[0] == a and path[-1] == b
    pairs = no_step.no_step_edges(pm, law)
    keys = {(x, y) for x, y, *_ in pairs}
    apron, runway = _verts_of_role(pm, "apron"), _verts_of_role(pm, "runway")
    assert not any((x in apron and y in runway) or (x in runway and y in apron) for x, y in keys), \
        "an apron↔runway pair across the grass must not exist (04o)"
    # the apron does pair along its own pavement and with the stub it joins
    stub_w = _verts_of_role(pm, "stub") & {v for v in pm.vertices if pm.vertices[v].xy[0] < 0}
    assert any((x in apron and y in stub_w) or (x in stub_w and y in apron) for x, y in keys)
    assert all(d <= law.tables.emit.no_step.window_m + 1e-9 for *_x, d in pairs)


def test_pair_budget_is_the_sum_of_cap_times_length_along_the_path(loop, law):
    _airport, pm = loop
    g = routes(pm, law)
    pairs = no_step.no_step_edges(pm, law)
    assert pairs
    apron, taxi = _verts_of_role(pm, "apron"), _verts_of_role(pm, "stub")
    mixed = [p for p in pairs if (p[0] in apron) != (p[1] in apron) and (p[0] in taxi or p[1] in taxi)]
    assert mixed, "apron↔stub pairs must exist along the lane"
    caps = {round(c, 6) for _a, _b, c, _d in pairs}
    assert {0.01, 0.015} <= caps, caps                   # apron-only, taxi-only paths
    for a, b, cap, d in pairs[:400] + mixed[:50]:
        rp = route_path(g, a, b, max_len=law.tables.emit.no_step.window_m)
        assert rp is not None
        dist, bud, _path = rp
        assert dist == pytest.approx(d, abs=1e-6)
        assert cap * d == pytest.approx(bud, abs=1e-6)     # Diff.bound_m == Σ cap_e · len_e
    # a mixed pair's cap is BETWEEN the two roles' caps: the path's own
    # mix, never the strictest endpoint over a chord
    assert any(0.01 < cap < 0.015 for _a, _b, cap, _d in mixed), sorted({round(c, 5) for *_x, c, _d in mixed})


def test_reach_bands_are_the_envelope_of_the_hard_rows(loop, law):
    airport, pm = loop
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    pins = threshold_pins(pm, law, airport)
    assert set(pins.values()) == {700.0}
    band = reach(routes(pm, law), pins)
    for v, z in pins.items():
        assert band[v] == (pytest.approx(z), pytest.approx(z))
    rows = no_step.reach_bands(pm, law, airport)
    assert rows and all(isinstance(r, Band) and r.source.generator == REACH_GENERATOR for r in rows)
    assert {r.v for r in rows} == set(band)
    assert all(r.lo <= r.hi for r in rows)
    # the far apron corner's ceiling is the route's budget above the pin
    apron = _verts_of_role(pm, "apron")
    far = max(apron, key=lambda v: band[v][1])
    d, bud, _p = route_path(routes(pm, law), far, next(iter(pins)))
    assert band[far][1] == pytest.approx(700.0 + bud, abs=1e-6) or band[far][1] <= 700.0 + bud + 1e-6
    # the solve WITHOUT the bands lands inside them: they add nothing to a
    # feasible hard set, they only name the envelope
    cs, _c, _w = generate(pm, law, airport)
    without = ConstraintSet.from_rows(r for r in cs.rows()
                                      if r.source.generator != REACH_GENERATOR)
    sol = solve(pm, without, DEFAULT_WEIGHTS)
    assert sol.status.value == "optimal"
    for r in rows:
        assert r.lo - 1e-6 <= sol.z[r.v] <= r.hi + 1e-6, (r.v, r.lo, sol.z[r.v], r.hi)
    # ...and with them the solve is the same OPTIMUM: the same objective,
    # and the with-band surface inside the bands too.  Point identity is
    # NOT the meaning: the L1 fit has ties, and under the runway transverse
    # maximum (RULINGS 2026-09-05o/s: two-sided rows on every off-ridge
    # runway edge vertex) HiGHS returns two optima 0.011 m apart on this
    # loop (measured 2026-09-05) — a tie between equal-cost surfaces, not
    # a band that cut the feasible set.
    sol2 = solve(pm, cs, DEFAULT_WEIGHTS)
    assert sol2.status.value == "optimal"
    o1, o2 = sol.residual.objective, sol2.residual.objective
    assert abs(o1 - o2) <= 1e-6 * max(1.0, abs(o1)), (o1, o2)
    for r in rows:
        assert r.lo - 1e-6 <= sol2.z[r.v] <= r.hi + 1e-6, (r.v, r.lo, sol2.z[r.v], r.hi)
    moved = float(np.max(np.abs(np.asarray(sol.z) - np.asarray(sol2.z))))
    assert moved < 0.05, moved                    # a tie among equal optima, never a band's pull


def test_route_neighbours_respects_window_and_k(loop, law):
    _airport, pm = loop
    g = routes(pm, law)
    got = route_neighbours(g, g.nodes, 60.0, 4)
    per: dict[int, int] = {}
    for a, b, d, bud in got:
        assert 0 < d <= 60.0 and bud > 0
        per[a] = per.get(a, 0) + 1
        per[b] = per.get(b, 0) + 1
    assert got and max(per.values()) >= 4


def test_chord_metric_is_refused(loop, law):
    _airport, pm = loop
    emit = _dc.replace(law.tables.emit, no_step=_dc.replace(law.tables.emit.no_step, metric="chord"))
    bad = _dc.replace(law, tables=_dc.replace(law.tables, emit=emit))
    with pytest.raises(LawError, match="route"):
        no_step.no_step_edges(pm, bad)


def test_junction_inherits_the_letter_of_the_chains_it_serves():
    """RULINGS 2026-09-04q-2: the route-proximity cut's junction carries
    the strictest letter of the taxi chains through / beside it.  The
    synthetic classify airport slices one face from the parallel P (class
    D, y = 112.5) up the strip into the apron where route A (class C)
    runs; the junction parts span both, so they inherit D — the strictest
    (widest) of the two — where the chord-era cut minted None."""
    from shapely.geometry import LineString, Polygon
    airport = classify_airport(gate=True)
    law = Law.for_airport("SYNT")
    cl = classify(airport, law)
    junctions = [c for c in cl.cells if c.role == "junction" and c.ref == "apron"]
    assert junctions
    nodes = {k: n.xy for k, n in airport.taxi_nodes.items()}
    for c in junctions:
        poly = Polygon(c.ring, c.holes)
        letters = {e.width_class for e in airport.taxi_edges if e.width_class
                   and LineString([nodes[e.a], nodes[e.b]]).intersection(poly.buffer(1.0)).length > 1.0}
        assert letters and c.code_letter == max(letters), (c.code_letter, letters)
        assert c.evidence.get("near_route") == 1.0 and c.evidence.get("letter_chains", 0) >= 1
    # the letter reaches the cap the planar face is priced at
    from auto_patch_v2.law.tables import role_cap
    for c in junctions:
        assert role_cap(law, "junction", None, c.code_letter).longitudinal == \
            role_cap(law, "stub", None, c.code_letter).longitudinal


def test_sidecar_and_verify_read_the_same_population(loop, law):
    airport, pm = loop
    cs, _c, _w = generate(pm, law, airport)
    sol = solve(pm, cs, DEFAULT_WEIGHTS)
    assert sol.status.value == "optimal"
    pub = publication(pm, law, airport, sol.z)
    edges = no_step.no_step_edges(pm, law)
    assert len(pub["airside_no_step_edges"]) == len(edges)
    ll = {vid: [v.key[0], v.key[1]] for vid, v in pm.vertices.items()}
    for rec, (a, b, cap, d) in zip(pub["airside_no_step_edges"], edges):
        assert rec["a"] == ll[a] and rec["b"] == ll[b]
        assert rec["dist_m"] == pytest.approx(d, abs=1e-4)          # the ROUTE distance
        assert rec["budget_m"] == pytest.approx(cap * d, abs=1e-6)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs, {})
    p = Patch.of(surf, law, pub, {})
    assert no_step_direct(p) == []
    # a step minted by hand at one published pair is read back at that pair
    a, b, cap, d = edges[0]
    z = list(sol.z)
    z[a] += cap * d + 1.0
    sol2 = _dc.replace(sol, z=z)
    surf2 = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs, {})
    rows = no_step_direct(Patch.of(surf2, law, pub, {}))
    assert rows and all(r["family"] == "airside_no_step" for r in rows)


# ── RULINGS 2026-09-05v: no apron plan chord in the route graph ──────────

@pytest.fixture(scope="module")
def between(law):
    """A runway; a stub up at x = −300 into a 700 m × 100 m apron; a
    second taxiway leaving the apron's far end (x = +300) northward to
    nowhere.  The apron sits BETWEEN two taxiways; the far taxiway is
    reached from the thresholds only through the apron, whose 700 m body
    chord (608 m corner to far mouth) is NOT a route (2026-09-05v)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubW", _rect(-311.5, 22.5, -288.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "apron", "apron1", _rect(-350, 190, 350, 290), (), None, None,
             "airside", "apron", {}),
        Cell(3, "stub", "stubN", _rect(288.5, 290, 311.5, 400), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubW", ((-300.0, 0.0), (-300.0, 190.0))),
            CutLine("taxi_centerline", "stubN", ((300.0, 290.0), (300.0, 400.0))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _apron_face_vertex_sets(pm):
    return [{v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
            for f in pm.faces.values() if f.role == "apron"]


@pytest.mark.parametrize("fx", ["loop", "between"])
def test_no_chord_edge_lies_on_one_apron_face(fx, law, request):
    """The twin of 2026-09-05v: the route graph carries no CHORD edge whose
    two endpoints lie on one apron face; the apron's perimeter (its ring
    edges) and the centrelines crossing it are its only routes."""
    from auto_patch_v2.constraints.routes import CHORD, RING
    _airport, pm = request.getfixturevalue(fx)
    g = build_routes(pm, law)
    sets = _apron_face_vertex_sets(pm)
    assert sets
    chords = [(int(a), int(b)) for a, b, k in zip(g.a, g.b, g.kind) if k == CHORD]
    for s in sets:
        assert not [(a, b) for a, b in chords if a in s and b in s]
        # ...and every apron ring edge IS a route
        rings = {(int(a), int(b)) for a, b, k in zip(g.a, g.b, g.kind) if k in (RING, CENTRELINE)}
        assert s <= {v for e in rings for v in e}


def test_apron_body_chord_is_not_a_route_the_far_taxiway_takes_the_route_budget(between, law):
    """The apron between two taxiways: the reach band at the far taxiway
    is the ROUTE's budget — runway ring, stub, the apron PERIMETER, the
    far stub — not the 608 m apron body chord's (which grants ~0.9 m
    less at the apron cap and, hard as a band, would bind where the
    apron law's own relaxable chord row is the only law on it)."""
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    from auto_patch_v2.constraints.routes import CHORD
    from auto_patch_v2.law.tables import role_cap
    airport, pm = between
    g = routes(pm, law)
    pins = threshold_pins(pm, law, airport)
    assert set(pins.values()) == {700.0}
    band = reach(g, pins)
    top = [v for v in _verts_of_role(pm, "stub") if abs(pm.vertices[v].xy[1] - 400.0) < 1e-6]
    mouth_w = [v for v in _verts_of_role(pm, "apron") if abs(pm.vertices[v].xy[1] - 190.0) < 1e-6
               and abs(pm.vertices[v].xy[0] + 300.0) < 12.0]
    mouth_n = [v for v in _verts_of_role(pm, "apron") if abs(pm.vertices[v].xy[1] - 290.0) < 1e-6
               and abs(pm.vertices[v].xy[0] - 300.0) < 12.0]
    assert top and mouth_w and mouth_n
    v = top[0]
    pin = next(iter(pins))
    d, bud, path = route_path(g, pin, v)
    assert band[v][1] == pytest.approx(700.0 + bud, abs=1e-6)
    # the route runs the apron's PERIMETER: no CHORD edge of the path
    # lies on the apron (the runway / stub per-stretch chords are routes)
    kinds = {}
    for a, b, k in zip(g.a, g.b, g.kind):
        kinds[(int(a), int(b))] = int(k)
    apron_v = _verts_of_role(pm, "apron")
    assert any(x in apron_v and y in apron_v for x, y in zip(path, path[1:]))
    assert all(kinds[(min(x, y), max(x, y))] != CHORD
               for x, y in zip(path, path[1:]) if x in apron_v and y in apron_v)
    # the withdrawn chord: apron west mouth -> north mouth straight across
    # the body, at the apron cap; the route around it grants more
    apron_cap = role_cap(law, "apron").longitudinal
    a, b = mouth_w[0], mouth_n[0]
    chord = math.hypot(*(np.subtract(pm.vertices[a].xy, pm.vertices[b].xy)))
    assert chord > 550.0
    da, ba, _pa = route_path(g, pin, a)
    dperim, bperim, pperim = route_path(g, a, b)
    assert dperim > chord + 50.0 and bperim > apron_cap * chord + 0.5
    assert band[b][1] == pytest.approx(700.0 + ba + bperim, abs=1e-6)
    assert band[b][1] > 700.0 + ba + apron_cap * chord + 0.5
    # reach and no_step keep their form on this map
    rows = no_step.reach_bands(pm, law, airport)
    assert {r.v for r in rows} == set(band) and all(r.lo <= r.hi for r in rows)
    pairs = no_step.no_step_edges(pm, law)
    assert pairs and all(0 < dd <= law.tables.emit.no_step.window_m + 1e-9 for *_x, dd in pairs)
    assert (min(a, b), max(a, b)) not in {(x, y) for x, y, *_ in pairs}


# ── RULINGS 2026-09-05z: the runway is like an apron in the route graph ──

@pytest.fixture(scope="module")
def crossing(law):
    """A runway with a stub on EACH edge at x = 0, the two cut centrelines
    ending on the runway edges (as classify's runway cut leaves them),
    and the apt.dat 1202 network crossing the runway through a node on
    its centreline: stubN (0, 190) → (0, 0) → stubS (0, −190), plus the
    runway's own 1202 edges along the centreline."""
    from auto_patch_v2.model.airport import TaxiEdge, TaxiNode
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    nodes = {1: TaxiNode(1, (0.0, 190.0), "both"), 2: TaxiNode(2, (0.0, 0.0), "both"),
             3: TaxiNode(3, (0.0, -190.0), "both"), 4: TaxiNode(4, (-600.0, 0.0), "both"),
             5: TaxiNode(5, (600.0, 0.0), "both")}
    edges = (TaxiEdge(1, 2, "N", False, False, "D"), TaxiEdge(2, 3, "S", False, False, "D"),
             TaxiEdge(4, 2, "09/27", False, True, None), TaxiEdge(2, 5, "09/27", False, True, None))
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), nodes, edges,
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubN", _rect(-11.5, 22.5, 11.5, 190), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "stub", "stubS", _rect(-11.5, -190, 11.5, -22.5), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubN", ((0.0, 22.5), (0.0, 190.0))),
            CutLine("taxi_centerline", "stubS", ((0.0, -190.0), (0.0, -22.5))))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _runway_ring_edges_that_are_no_route(pm, law):
    """Every runway-family ring edge between two EDGE vertices — neither
    endpoint on the ridge or a centreline (an edge vertex's hop to an
    ADJACENT anchor is one ring edge long and lawful, 05z c) — that is
    not shared with a non-runway route face."""
    from auto_patch_v2.constraints.routes import RIDGE_KIND
    from auto_patch_v2.law.tables import role_family
    ridge = {eid for bl in pm.breaklines.values() if bl.kind == RIDGE_KIND for eid in bl.edges}
    anchors = {v for eid, e in pm.edges.items() if eid in ridge or e.kind.value == "centerline"
               for v in (e.a, e.b)}
    out = set()
    for f in pm.faces.values():
        if role_family(law, f.role) != "runway":
            continue
        for cyc in (f.ring, *f.holes):
            for eid in cyc:
                e = pm.edges[eid]
                if eid in ridge or e.kind.value == "centerline" or e.a in anchors or e.b in anchors:
                    continue
                if any(role_family(law, pm.faces[o].role) != "runway" and pm.faces[o].role in route_roles(law)
                       for o in pm.faces_of_edge(eid)):
                    continue
                out.add(e.length_key)
    return out


@pytest.mark.parametrize("fx", ["crossing", "loop", "between"])
def test_no_graph_edge_lies_on_a_runway_ring(fx, law, request):
    """05z: the runway's EDGES are not graph edges — no route lies on a
    runway ring edge that is not the ridge, a centreline part, or a
    taxi face's own ring edge."""
    airport, pm = request.getfixturevalue(fx)
    g = build_routes(pm, law, airport)
    on_graph = {(int(a), int(b)) for a, b in zip(g.a, g.b)}
    edges = _runway_ring_edges_that_are_no_route(pm, law)
    assert edges
    assert not (edges & on_graph)
    # ...and every runway ring vertex is still a graph node (it hops)
    assert _verts_of_role(pm, "runway") <= g.nodes


def test_runway_edges_reach_each_other_through_the_crossing(crossing, law):
    """05z (b): a stub on each edge; the two edges' reach bands overlap by
    at least the transverse allowance, because both reach through the
    crossing and the centreline — not around the runway end."""
    from auto_patch_v2.constraints.routes import CROSSING, EDGE_HOP
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    from auto_patch_v2.law.tables import runway_transverse_max
    airport, pm = crossing
    g = routes(pm, law, airport)
    assert g.stats["crossing"] > 0 and g.stats["crossing_unmatched"] == 0
    assert g.stats["edge_hop"] > 0 and g.stats["ring"] > 0
    assert set(np.unique(g.kind)) >= {CROSSING, EDGE_HOP}
    north = [v for v in _verts_of_role(pm, "runway") if abs(pm.vertices[v].xy[1] - 22.5) < 1e-6
             and abs(pm.vertices[v].xy[0]) < 1e-6]
    south = [v for v in _verts_of_role(pm, "runway") if abs(pm.vertices[v].xy[1] + 22.5) < 1e-6
             and abs(pm.vertices[v].xy[0]) < 1e-6]
    assert len(north) == 1 and len(south) == 1
    n, s = north[0], south[0]
    d, bud, path = route_path(g, n, s)
    assert d == pytest.approx(45.0, abs=1e-6), (d, path)           # straight across
    cap = role_cap(law, "runway", 3, "D").longitudinal
    assert bud == pytest.approx(cap * 45.0, abs=1e-6)
    pins = threshold_pins(pm, law, airport)
    band = reach(g, pins)
    lo, hi = max(band[n][0], band[s][0]), min(band[n][1], band[s][1])
    allowance = runway_transverse_max(law, "D", 3) * 45.0
    assert hi - lo >= allowance
    assert abs(band[n][1] - band[s][1]) <= cap * 45.0 + 1e-6
    # an edge vertex on NO crossing hops along its ring to the crossing
    far = min((v for v in _verts_of_role(pm, "runway")
               if abs(pm.vertices[v].xy[1] - 22.5) < 1e-6 and abs(pm.vertices[v].xy[0]) > 1e-6),
              key=lambda v: abs(pm.vertices[v].xy[0]))
    d2, _b2, path2 = route_path(g, far, n)
    assert d2 == pytest.approx(abs(pm.vertices[far].xy[0]), abs=1e-6) and path2 == [far, n]


def test_reach_along_the_centreline_is_pin_plus_cap_times_distance(crossing, law):
    """05z (a): from a threshold pin the reach along the centreline is
    pin ± cap · distance at the runway longitudinal cap by code."""
    from auto_patch_v2.constraints.routes import RIDGE_KIND
    airport, pm = crossing
    g = routes(pm, law, airport)
    ridge = [v for bl in pm.breaklines.values() if bl.kind == RIDGE_KIND for v in bl.vertices(pm)]
    pin = min(ridge, key=lambda v: pm.vertices[v].xy[0])
    assert pm.vertices[pin].xy == pytest.approx((-600.0, 0.0))
    cap = role_cap(law, "runway", 3, "D").longitudinal
    band = reach(g, {pin: 700.0})
    for v in ridge:
        dist = pm.vertices[v].xy[0] + 600.0
        assert band[v][1] == pytest.approx(700.0 + cap * dist, abs=1e-6), v
        assert band[v][0] == pytest.approx(700.0 - cap * dist, abs=1e-6), v
    # the far edge vertex: pin ± cap · (centreline + crossing) — the
    # route, never the ring around the end
    south = [v for v in _verts_of_role(pm, "runway") if abs(pm.vertices[v].xy[1] + 22.5) < 1e-6
             and abs(pm.vertices[v].xy[0]) < 1e-6][0]
    assert band[south][1] == pytest.approx(700.0 + cap * (600.0 + 22.5), abs=1e-6)
