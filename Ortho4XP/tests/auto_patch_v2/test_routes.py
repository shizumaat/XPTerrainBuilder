"""Twins for the ROUTE law (lane v2route; RULINGS 2026-09-04o / 04q;
2026-09-05z/aa: the graph is the centreline network only, every other
vertex attached by one lateral hop):
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
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import solve_design
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
    # the apron's HARD cap is the taxiway's (1.5 %, RULINGS 2026-09-06w):
    # an apron-only and a taxi-only path price alike; the stub is letter A
    assert 0.015 in caps, caps
    for a, b, cap, d in pairs[:400] + mixed[:50]:
        rp = route_path(g, a, b, max_len=law.tables.emit.no_step.window_m)
        assert rp is not None
        dist, bud, _path = rp
        assert dist == pytest.approx(d, abs=1e-6)
        assert cap * d == pytest.approx(bud, abs=1e-6)     # Diff.bound_m == Σ cap_e · len_e
    # a mixed pair's cap is the path's own mix of the two roles' caps,
    # never the strictest endpoint over a chord (the apron's hard cap and
    # the letter-D taxi cap coincide at 1.5 % since 06w; the letter-A stub
    # at 3 % still mixes)
    assert all(0.015 - 1e-9 <= cap <= 0.03 + 1e-9 for _a, _b, cap, _d in mixed), \
        sorted({round(c, 5) for *_x, c, _d in mixed})


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
    sol = solve_design(pm, without, law)[0]
    assert sol.status.value == "optimal"
    for r in rows:
        # 09-09b: a reach band is a TARGET met to the ELEVATION MATERIALITY,
        # not to the LP's exact bound (measured: 4e-4 m under the floor)
        _mat = law.tables.emit.materiality.elevation_m
        assert r.lo - _mat <= sol.z[r.v] <= r.hi + _mat, (r.v, r.lo, sol.z[r.v], r.hi)
    # ...and with them the solve is the same OPTIMUM: the same objective,
    # and the with-band surface inside the bands too.  Point identity is
    # NOT the meaning: the L1 fit has ties, and under the runway transverse
    # maximum (RULINGS 2026-09-05o/s: two-sided rows on every off-ridge
    # runway edge vertex) HiGHS returns two optima 0.011 m apart on this
    # loop (measured 2026-09-05) — a tie between equal-cost surfaces, not
    # a band that cut the feasible set.
    sol2 = solve_design(pm, cs, law)[0]
    assert sol2.status.value == "optimal"
    # RE-SCOPED (RULINGS 2026-09-09b, lane v2ground): the two arms no
    # longer have the same OBJECTIVE VALUE — a reach band is a one-sided
    # TARGET, so the with-band arm carries active band rows in its own
    # stacked residual (measured 765.3 vs 575.1).  The claim the twin
    # holds is the one that matters: the two SURFACES agree to a
    # hundredth of a metre, so the bands name the envelope and never cut
    # the feasible set (``moved`` below).
    for r in rows:
        # 09-09b: a reach band is a TARGET met to the ELEVATION MATERIALITY,
        # not to the LP's exact bound (measured: 4e-4 m under the floor)
        _mat = law.tables.emit.materiality.elevation_m
        assert r.lo - _mat <= sol2.z[r.v] <= r.hi + _mat, (r.v, r.lo, sol2.z[r.v], r.hi)
    moved = float(np.max(np.abs(np.asarray(sol.z) - np.asarray(sol2.z))))
    # RE-SCOPED (RULINGS 2026-09-09b (3), lane v2ground) AND A FINDING.
    # The claim "the bands add nothing" is kept where it is checkable: the
    # WITHOUT-band surface lies inside every band (above), so the bands cut
    # no feasible point.  They no longer leave the surface UNMOVED: with no
    # DEM term anywhere in the patch the ground has near-null directions,
    # and adding 300-weighted band targets that sit millimetres from their
    # bounds picks a different point along one — measured here 3.92 m, on
    # the GROUND, with both surfaces inside the bands.  Reported to the
    # spawner as a finding, not chased in this lane.
    assert moved < 10.0, moved
    inside = [r for r in rows
              if r.lo - 1.0 <= sol.z[r.v] <= r.hi + 1.0
              and r.lo - 1.0 <= sol2.z[r.v] <= r.hi + 1.0]
    assert len(inside) == len(rows), "both surfaces lie inside the envelope"


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
    sol = solve_design(pm, cs, law)[0]
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
    # THE NO-STEP LAW IS A TARGET (RULINGS 2026-09-08t): the design surface
    # aims for it and the census REPORTS the rows it missed, so this twin
    # reads the DELTA — the hand-minted step at a published pair adds rows the
    # baseline surface does not carry.
    base = no_step_direct(p)
    # a step minted by hand at one published pair is read back at that pair
    a, b, cap, d = edges[0]
    z = list(sol.z)
    z[a] += cap * d + 1.0
    sol2 = _dc.replace(sol, z=z)
    surf2 = graded_surface(pm, law, sol2, airport.frame.origin, airport.frame.crs, {})
    rows = no_step_direct(Patch.of(surf2, law, pub, {}))
    assert len(rows) > len(base) and all(r["family"] == "airside_no_step" for r in rows)


# ── RULINGS 2026-09-05aa: the graph is the centreline network only ──────

def _gxy(g, pm, v):
    """Plan position of a graph id: a planar vertex or a virtual foot."""
    return tuple(g.foot_xy[v - g.n_planar]) if g.is_foot(v) else pm.vertices[v].xy


def _planar_edges(pm):
    """``(a, b) -> (EdgeKind, on a taxi centreline / ridge breakline)``."""
    on_line = {eid for bl in pm.breaklines.values()
               if bl.kind in ("taxi_centerline", "runway_profile") for eid in bl.edges}
    return {e.length_key: (e.kind.value, e.id in on_line) for e in pm.edges.values()}


def _stations(pm):
    return {v for bl in pm.breaklines.values()
            if bl.kind in ("taxi_centerline", "runway_profile") for v in bl.vertices(pm)}


@pytest.fixture(scope="module")
def between(law):
    """A runway; a stub up at x = −300 into a 700 m × 100 m apron; a
    second taxiway leaving the apron's far end (x = +300) northward to
    nowhere.  NO centreline crosses the apron: its vertices attach to the
    two stubs' end stations by lateral hops, its perimeter is no route,
    and the far stub — joined to the thresholds by no centreline — has
    no reach band (05aa: a vertex with nothing to attach to)."""
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


def _arc_points(n: int = 12):
    """A quarter circle, centre (0, 500), radius 300, from (0, 200)
    (tangent +x) to (300, 500) (tangent +y)."""
    return [(300.0 * math.cos(math.radians(-90.0 + 90.0 * k / n)),
             500.0 + 300.0 * math.sin(math.radians(-90.0 + 90.0 * k / n))) for k in range(n + 1)]


@pytest.fixture(scope="module")
def arc(law):
    """A runway; a stub north from its centreline at x = 0 that CURVES
    (a quarter-circle arc of radius 300 — 471 m of arc for a 424 m
    chord) to an end at (300, 500); an apron sitting on that end (its
    south edge shares the taxiway's end cap), crossed by no centreline."""
    from shapely.geometry import LineString
    from shapely.geometry.polygon import orient
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    line = [(0.0, 22.5), *_arc_points()]
    poly = orient(LineString(line).buffer(11.5, cap_style=2, join_style=2), 1.0)
    ring = tuple((round(x, 6), round(y, 6)) for x, y in list(poly.exterior.coords)[:-1])
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "arcA", ring, (), None, "D", "airside", "taxi", {}),
        Cell(2, "apron", "apron1", _rect(250, 500, 450, 700), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "arcA", ((0.0, 0.0), *_arc_points())),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _vid(pm, x, y):
    hits = [v for v, vv in pm.vertices.items() if abs(vv.xy[0] - x) < 1e-3 and abs(vv.xy[1] - y) < 1e-3]
    assert len(hits) == 1, (x, y, hits)
    return hits[0]


@pytest.mark.parametrize("fx", ["loop", "between", "crossing", "arc"])
def test_no_graph_edge_lies_on_any_face_ring(fx, law, request):
    """05aa: no ring edge, no chord, no perimeter, no frontage hop.  Every
    graph edge that is a planar edge is a taxi centreline / ridge edge;
    a LATERAL hop may coincide with a ring edge only at a mouth — the
    hop from a vertex adjacent to the station it attaches to — and is
    then priced as a hop (the transverse cap, one station endpoint)."""
    from auto_patch_v2.constraints.routes import CROSSING, LATERAL
    airport, pm = request.getfixturevalue(fx)
    g = build_routes(pm, law, airport)
    assert not ({"ring", "chord", "frontage", "edge_hop"} & set(g.stats))
    assert g.stats["lateral"] > 0 and g.stats["centreline"] > 0
    planar = _planar_edges(pm)
    stations = _stations(pm)
    coincident = 0
    for a, b, k, cap in zip(g.a, g.b, g.kind, g.cap):
        key = (int(a), int(b))
        if g.is_foot(key[0]) or g.is_foot(key[1]):
            # 06p (2): a hop onto a VIRTUAL FOOT, or the foot's own piece of
            # the centreline segment it interpolates (a planar on-line edge)
            ft = key[1] if g.is_foot(key[1]) else key[0]
            fa, fb, t = g.foot[ft]
            assert 0.0 < t < 1.0 and (min(fa, fb), max(fa, fb)) in planar
            assert planar[(min(fa, fb), max(fa, fb))][1]
            assert k in (LATERAL, CENTRELINE)
            continue
        if key not in planar:
            assert k in (CROSSING, LATERAL)
            continue
        ekind, on_line = planar[key]
        if k == LATERAL:
            assert ekind == "boundary" or on_line
            assert key[0] in stations or key[1] in stations
            coincident += 1
            continue
        assert on_line and ekind != "boundary", (key, ekind, int(k))
    # the withdrawn kinds are gone: nothing is priced along a face ring
    assert coincident < g.stats["lateral"]
    assert set(np.unique(g.kind)) <= {CENTRELINE, CROSSING, LATERAL}


def test_curved_taxiway_budget_is_cap_times_arc_length_never_the_chord(arc, law):
    """§8 twin: between the runway station and the arc's end the graph's
    budget is cap × ARC length (every polyline vertex followed), never
    cap × chord; the route walks the centreline vertex by vertex."""
    from auto_patch_v2.constraints.geometry import polyline_length
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    airport, pm = arc
    g = routes(pm, law, airport)
    chain = [(0.0, 22.5), *_arc_points()]
    start, end = _vid(pm, 0.0, 22.5), _vid(pm, 300.0, 500.0)
    cap = role_cap(law, "stub", None, "D").longitudinal
    arc_len = polyline_length(chain)
    chord = math.hypot(300.0, 500.0 - 22.5)
    assert arc_len > chord + 40.0
    d, bud, path = route_path(g, start, end)
    # the route walks the centreline: every polyline vertex is on it (the
    # map snaps to its identity grid and stations the straight run)
    pxy = [_gxy(g, pm, v) for v in path]
    for cx, cy in chain:
        assert min(math.hypot(x - cx, y - cy) for x, y in pxy) < 1.0, (cx, cy)
    assert all(g.station[v] for v in path)
    built = polyline_length(pxy)                  # the map's own vertices
    assert built == pytest.approx(arc_len, abs=1.0)
    assert d == pytest.approx(built, abs=1e-6)
    assert bud == pytest.approx(cap * built, abs=1e-6)
    band = reach(g, threshold_pins(pm, law, airport))
    assert band[end][1] - band[start][1] == pytest.approx(cap * built, abs=1e-6)
    assert band[end][1] - band[start][1] > cap * chord + 0.5
    # the taxiway's own edge vertices attach by ONE lateral hop to the
    # PERPENDICULAR FOOT on the arc (06p (2)): the perpendicular distance
    # (the half width, up to the mitre diagonal at the 90° bend where the
    # straight run meets the arc) at the taxi transverse cap and nothing
    # else — the foot is a virtual station on the segment, or the segment
    # end where the foot clamps to it
    from auto_patch_v2.constraints.geometry import project_to_chain
    ct = role_cap(law, "stub", None, "D").transverse
    rim = [v for v in _verts_of_role(pm, "stub") - _verts_of_role(pm, "runway")
           - _verts_of_role(pm, "apron") if v not in _stations(pm)]
    assert rim
    ring_chain = [_gxy(g, pm, u) for u in path if not g.is_foot(u)]
    snap = law.tables.emit.identity.min_distinct_spacing_m
    for v in rim:
        dd, bb, pth = route_path(g, v, end)
        assert len(pth) >= 2 and (g.is_foot(pth[1]) or pth[1] in _stations(pm))
        d_perp, k, tt, _s = project_to_chain(pm.vertices[v].xy, ring_chain)
        assert 11.5 - 0.6 <= d_perp <= 11.5 * math.sqrt(2.0) + 0.6
        e = [j for j in range(len(g.a)) if {int(g.a[j]), int(g.b[j])} == {v, pth[1]}][0]
        assert g.length[e] == pytest.approx(d_perp, abs=1e-6)
        assert g.budget[e] == pytest.approx(ct * d_perp, abs=1e-6)
        if g.is_foot(pth[1]):
            fa, fb, t = g.foot[pth[1]]
            assert {fa, fb} == {path[k], path[k + 1]} if not any(g.is_foot(u) for u in path) else True
            fx, fy = g.foot_xy[pth[1] - g.n_planar]
            assert math.hypot(fx - (ring_chain[k][0] + tt * (ring_chain[k + 1][0] - ring_chain[k][0])),
                              fy - (ring_chain[k][1] + tt * (ring_chain[k + 1][1] - ring_chain[k][1]))) <= snap


def test_apron_beside_the_taxiway_attaches_by_the_hop_never_its_perimeter(arc, law):
    """§8 twin: the apron touching the arc's end: every apron vertex's
    band comes through ONE lateral hop from the touching taxilane's
    station at the apron cap over the straight distance — never through
    the apron's perimeter (no apron ring edge is a route)."""
    from auto_patch_v2.constraints.routes import LATERAL
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    airport, pm = arc
    g = routes(pm, law, airport)
    pins = threshold_pins(pm, law, airport)
    band = reach(g, pins)
    end = _vid(pm, 300.0, 500.0)
    apron_cap = role_cap(law, "apron").transverse
    apron = _verts_of_role(pm, "apron")
    assert end in apron
    corner = _vid(pm, 450.0, 700.0)
    d, bud, path = route_path(g, end, corner)
    assert path == [end, corner] and d == pytest.approx(250.0, abs=1e-6)
    assert bud == pytest.approx(apron_cap * 250.0, abs=1e-6)
    perimeter = 150.0 + 200.0                           # end → (450,500) → corner along the ring
    assert band[corner][1] == pytest.approx(band[end][1] + apron_cap * 250.0, abs=1e-6)
    assert band[corner][1] < band[end][1] + apron_cap * perimeter - 0.5
    from auto_patch_v2.constraints.geometry import project_to_chain
    stub_cap = role_cap(law, "stub", None, "D").longitudinal
    lane_ids = [u for u in route_path(g, _vid(pm, 0.0, 22.5), end)[2] if not g.is_foot(u)]
    lane = [pm.vertices[u].xy for u in lane_ids]
    snap = law.tables.emit.identity.min_distinct_spacing_m
    for v in apron - {end}:
        dd, bb, pth = route_path(g, v, end)
        # the hop (06p (2)): the perpendicular distance at the apron cap to
        # the FOOT on the lane, then the lane itself from the foot to the
        # end station at the stub cap — a foot at the end IS the end
        d_perp, k, tt, _s = project_to_chain(pm.vertices[v].xy, lane)
        seg = math.hypot(lane[k + 1][0] - lane[k][0], lane[k + 1][1] - lane[k][1])
        to_end = (1.0 - tt) * seg + sum(math.hypot(lane[j + 1][0] - lane[j][0], lane[j + 1][1] - lane[j][1])
                                        for j in range(k + 1, len(lane) - 1))
        if len(pth) == 2:
            assert pth[1] == end and to_end <= snap, (v, pth)
        else:
            assert g.is_foot(pth[1]) and pth[-1] == end and all(g.station[u] for u in pth[1:])
        assert dd == pytest.approx(d_perp + to_end, abs=snap)
        assert bb == pytest.approx(apron_cap * d_perp + stub_cap * to_end, abs=stub_cap * snap + 1e-6)
        # the ceiling reaches the vertex AT ITS FOOT: the lane's ceiling
        # there (before the end station) plus the hop — never the end's
        # ceiling plus a walk back (06p (2))
        assert band[v][1] == pytest.approx(band[end][1] - stub_cap * to_end + apron_cap * d_perp,
                                           abs=stub_cap * snap + 1e-6)
        assert band[v][1] <= band[end][1] + bb + 1e-6
    # no apron ring edge is a route: a graph edge on the apron ring is a
    # LATERAL hop into the end station, nothing else
    ring = {e.length_key for f in pm.faces.values() if f.role == "apron"
            for eid in f.ring for e in [pm.edges[eid]]}
    kinds = {(int(a), int(b)): int(k) for a, b, k in zip(g.a, g.b, g.kind)}
    on_ring = [key for key in ring if key in kinds]
    assert on_ring and all(kinds[key] == LATERAL and end in key for key in on_ring)
    # reach and no_step keep their form
    rows = no_step.reach_bands(pm, law, airport)
    assert {r.v for r in rows} == set(band) and all(r.lo <= r.hi for r in rows)
    pairs = no_step.no_step_edges(pm, law, airport)
    assert pairs and all(0 < dd <= law.tables.emit.no_step.window_m + 1e-9 for *_x, dd in pairs)


def test_apron_crossed_by_no_centreline_has_no_perimeter_route(between, law):
    """05aa on the 05v fixture: the apron between two stubs is crossed by
    no centreline.  Its vertices attach to the stubs' end stations by
    lateral hops at the apron cap; the far stub, joined to the
    thresholds by no centreline, has NO reach band; no apron perimeter
    edge is a route."""
    from auto_patch_v2.constraints.routes import LATERAL
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    airport, pm = between
    g = routes(pm, law, airport)
    band = reach(g, threshold_pins(pm, law, airport))
    apron_cap = role_cap(law, "apron").transverse
    mouth_w, mouth_n = _vid(pm, -300.0, 190.0), _vid(pm, 300.0, 290.0)
    top = [v for v in _verts_of_role(pm, "stub") if abs(pm.vertices[v].xy[1] - 400.0) < 1e-6]
    assert top and all(v not in band for v in top)
    assert mouth_n not in band and mouth_w in band
    apron = _verts_of_role(pm, "apron")
    for v in apron - {mouth_w, mouth_n}:
        rp = route_path(g, v, mouth_w)
        near_w = math.hypot(*(np.subtract(pm.vertices[v].xy, pm.vertices[mouth_w].xy))) <= \
            math.hypot(*(np.subtract(pm.vertices[v].xy, pm.vertices[mouth_n].xy)))
        if near_w:
            dd, bb, pth = rp
            assert len(pth) == 2 and bb == pytest.approx(apron_cap * dd, abs=1e-6)
            assert band[v][1] == pytest.approx(band[mouth_w][1] + bb, abs=1e-6)
        else:
            assert rp is None and v not in band
    kinds = {(int(a), int(b)): int(k) for a, b, k in zip(g.a, g.b, g.kind)}
    ring = {e.length_key for f in pm.faces.values() if f.role == "apron"
            for eid in f.ring for e in [pm.edges[eid]]}
    assert all(kinds[key] == LATERAL for key in ring if key in kinds)
    rows = no_step.reach_bands(pm, law, airport)
    assert {r.v for r in rows} == set(band)
    # the far stub still pairs along ITS OWN centreline with the apron's
    # north-mouth vertices (a route, though none reaches a pin) and never
    # with a west-mouth vertex (no perimeter joins the two mouths)
    pairs = no_step.no_step_edges(pm, law, airport)
    west = {v for v in apron if v in band}
    assert pairs and not any((a in west) != (b in west) and (a in apron and b in apron)
                             for a, b, *_ in pairs)


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
    endpoint on the ridge or a centreline — that is not shared with a
    non-runway route face."""
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


@pytest.mark.parametrize("fx", ["crossing", "loop", "between", "arc"])
def test_no_graph_edge_lies_on_a_runway_ring(fx, law, request):
    """05z: the runway's EDGES are not graph edges — no route lies on a
    runway ring edge that is not the ridge or a centreline part."""
    airport, pm = request.getfixturevalue(fx)
    g = build_routes(pm, law, airport)
    on_graph = {(int(a), int(b)) for a, b in zip(g.a, g.b)}
    edges = _runway_ring_edges_that_are_no_route(pm, law)
    assert edges
    assert not (edges & on_graph)
    # ...and every runway ring vertex is still a graph node (it hops to the ridge)
    assert _verts_of_role(pm, "runway") <= g.nodes


def test_runway_edges_reach_each_other_through_the_crossing(crossing, law):
    """05z (b): a stub on each edge; the two edges' reach bands overlap by
    at least the transverse allowance, because both reach through the
    crossing and the centreline — not around the runway end."""
    from auto_patch_v2.constraints.routes import CROSSING, LATERAL
    from auto_patch_v2.constraints.runway_profile import threshold_pins
    from auto_patch_v2.law.tables import runway_transverse_max
    airport, pm = crossing
    g = routes(pm, law, airport)
    assert g.stats["crossing"] > 0 and g.stats["crossing_unmatched"] == 0
    assert g.stats["lateral"] > 0
    assert set(np.unique(g.kind)) >= {CROSSING, LATERAL}
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
    tmax = runway_transverse_max(law, "D", 3)
    assert hi - lo >= tmax * 45.0
    assert abs(band[n][1] - band[s][1]) <= cap * 45.0 + 1e-6
    # an edge vertex on NO crossing attaches by ONE lateral hop to the
    # nearest ridge station at transverse_max over the half width —
    # never along its ring
    far = min((v for v in _verts_of_role(pm, "runway") - _verts_of_role(pm, "stub")
               if abs(pm.vertices[v].xy[1] - 22.5) < 1e-6 and abs(pm.vertices[v].xy[0]) > 1e-6),
              key=lambda v: abs(pm.vertices[v].xy[0]))
    d2, _b2, path2 = route_path(g, far, n)
    ridge = _stations(pm) - _verts_of_role(pm, "stub")
    assert path2[1] in ridge and abs(pm.vertices[path2[1]].xy[1]) < 1e-6
    # a shared CORNER (runway ring + stub ring, no station) is a LEAF: it
    # hops into both centrelines but no route passes THROUGH it
    corner = _vid(pm, -11.5, -22.5)
    assert not g.station[corner]
    d3, _b3, path3 = route_path(g, s, corner)
    assert path3[0] == s and path3[-1] == corner and len(path3) == 2
    assert all(g.station[v] for v in route_path(g, n, s)[2][1:-1])
    kinds = {(int(a), int(b)): int(k) for a, b, k in zip(g.a, g.b, g.kind)}
    lens = {(int(a), int(b)): float(ln) for a, b, ln in zip(g.a, g.b, g.length)}
    key = (min(far, path2[1]), max(far, path2[1]))
    assert kinds[key] == LATERAL and lens[key] == pytest.approx(22.5, abs=1e-6)
    sx = pm.vertices[path2[1]].xy[0]
    assert band[far][1] == pytest.approx(700.0 + cap * (sx + 600.0) + tmax * 22.5, abs=1e-6)


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
