"""Issue #291 / OWNER RULINGS 2026-10-03c (HECA cargo area 30.1132604,
31.4052094): THE ROAD TERRACE REACHES EVERY ROAD, AND A WALL IS THE STEP.

(1) 10-03b's bordered-run rule (``airport/road_ramp.road_terrace``) covers
    the apt.dat 1206 corridor and the DSF road page as well as the mapped
    ribbon: a 1206 route beside an apron takes the apron's stage-1 level
    (one-way; the airside is untouched).
(2) a wall-class pack piece between the airside-level road / apron and a
    lower lot (``wall_terrace``): the road is not held to the lot's level
    (no MEET across the wall), the lot follows its building's pad, and the
    step is DECLARED along the wall line (``terrace_joints`` kind
    ``wall_terrace``).
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import box

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import GroundRoute, TaxiNode

from test_roadmint100 import _with
from test_roadterrace100 import _solve


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


class _WestSlopeDem:
    """A hillside WEST of the apron (x < 300): +0.3 m per metre — the
    1206 route at x = 290 stands ~3 m over the apron edge."""
    provenance = {"base": "synthetic"}

    def z(self, x: float, y: float) -> float:
        return 100.0 + max(0.0, 300.0 - x) * 0.3

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _with_route(a, pts):
    """``a`` plus one 1206 truck route along ``pts`` (node ids 40..)."""
    nodes = dict(a.taxi_nodes)
    ids = []
    for i, p in enumerate(pts):
        nodes[40 + i] = TaxiNode(40 + i, p, "both")
        ids.append(40 + i)
    routes = tuple(a.ground_routes) + tuple(
        GroundRoute(ids[i], ids[i + 1], "truck", False) for i in range(len(ids) - 1))
    return _dc.replace(a, taxi_nodes=nodes, ground_routes=routes)


#: a 1206 route 10 m west of the apron's west edge (x = 300, y 300..500)
WEST_ROUTE = ((290.0, 330.0), (290.0, 470.0))


def _route_faces(pm):
    return [f for f in pm.faces.values()
            if f.role == "service_road" and str(f.ref).startswith("route")]


#: 10-03l twin (ii): a lot WEST of the route and a 3 m wall between them
WEST_WALL = box(280.85, 330.0, 281.15, 470.0)


def _west_lot(a):
    from auto_patch_v2.model.airport import Pavement, Surface
    from test_classify import _rect
    lot = Pavement("lot", Surface.CONCRETE, _rect(240.0, 340.0, 276.0, 460.0), ())
    return _dc.replace(a, pavements=tuple(a.pavements) + (lot,))


@pytest.fixture(scope="module")
def solved(law):
    """(no wall, route-free control, wall-witnessed) — one DEM, one route."""
    from auto_patch_v2.airport import road_ramp as rr
    from auto_patch_v2.airport.road_ramp import WallPiece
    a1 = _dc.replace(_with_route(_with(), WEST_ROUTE), dem=_WestSlopeDem())
    a0 = _dc.replace(_with(), dem=_WestSlopeDem())
    a2 = _west_lot(a1)
    no_wall, free = _solve(a1, law), _solve(a0, law)
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(rr, "wall_pieces", lambda _ap, _cfg=None: (
            WallPiece(WEST_WALL, 3.0, "wall.obj#comp0"),))
        walled = _solve(a2, law)
    finally:
        mp.undo()
    return no_wall, free, walled


def _beside(pm):
    route_v = {v for f in _route_faces(pm) for v in pm.ring_vertices(f.ring)}
    assert route_v, "the synthetic 1206 route minted no corridor face"
    return {v for v in route_v if 340.0 <= pm.vertices[v].xy[1] <= 460.0}


def test_a_1206_route_beside_an_apron_across_a_bank_keeps_its_own_target(law, solved):
    """OWNER RULINGS 2026-10-03l (#315 / #316, CYXY 60.7090573, -135.0740232):
    a NON-RIBBON road beside airside pavement with NO placed-wall witness
    leaves the terrace — no foot, no station — and is solved on its own
    §37 (6) target (its ground), not at the apron's level across the bank."""
    (pm1, sol1, rep1), _free, _walled = solved
    beside = _beside(pm1)
    terr = pm1.road_terrace
    assert not terr.get("wall")
    assert not (beside & set(terr["foot"])) and not (beside & set(terr["station"]))
    tr = rep1.reach_seed.get("terrace", {})
    assert tr.get("bordered", 0) == 0
    z = sol1.z
    tgt = {v: pm1.road_ramp_z[v] for v in beside if v in pm1.road_ramp_z}
    assert tgt, "the route carries no §37 (6) target beside the apron"
    assert max(abs(z[v] - t) for v, t in tgt.items()) <= 0.6
    # on its ground: never the 1.5 m+ cut the adjacency weld made (the
    # uphill kerb's bench on the 30 % cross slope is the cross-section's)
    assert max(pm1.vertices[v].dem_z - z[v] for v in beside) <= 1.2


def test_a_1206_route_along_a_placed_wall_rides_the_apron_level(law, solved):
    """10-03l (the HECA #291 key): the SAME route with a wall-class piece
    between it and a lot (10-03c's witness, ``wall_terraces``) is in the
    terrace along the wall — ``foot`` on the apron, solved at the apron's
    level, metres under its own DEM (the hill is the cut)."""
    _no_wall, _free, (pm2, sol2, rep2) = solved
    beside = _beside(pm2)
    terr = pm2.road_terrace
    assert len(terr["wall"]) == 1
    feet = {v: terr["foot"][v] for v in beside if v in terr["foot"]}
    assert feet and set(feet) >= (beside & set(terr["station"]))
    assert rep2.reach_seed.get("terrace", {}).get("bordered", 0) > 0
    z = sol2.z
    for v, (a, b, u, _ref) in feet.items():
        lvl = (1 - u) * z[a] + u * z[b]
        assert abs(z[v] - lvl) <= 0.6, (v, z[v], lvl)
    assert max(pm2.vertices[v].dem_z - z[v] for v in beside) > 1.5


def test_the_wall_key_leaves_a_ribbon_in_the_terrace():
    """10-03l (iii): ``wall_keyed`` trims ``own`` vertices only — a ribbon
    vertex keeps its foot / station with no wall anywhere (10-03b stands),
    an ``own`` vertex stays only inside a wall's ``upper`` span of ITS
    route, and one outside the span (or on another route) leaves."""
    from auto_patch_v2.airport.road_ramp import wall_keyed
    st = {1: (7, 0.0), 2: (7, 10.0),                 # ribbon, route 7
          10: (8, 0.0), 11: (8, 20.0), 12: (8, 30.0), 13: (8, 60.0),
          20: (9, 5.0)}                              # own, another route
    foot = {v: (100, 101, 0.5, "apron") for v in (1, 2, 10, 12, 13, 20)}
    terr = {"foot": foot, "pad": {11: "b1"}, "station": st, "kerb": {}, "meet": {13: True},
            "own": {v: True for v in (10, 11, 12, 13, 20)}, "wall": {}}
    out, left = wall_keyed(terr)
    assert left == 5 and set(out["station"]) == {1, 2} and set(out["foot"]) == {1, 2}
    terr["wall"] = {0: {"upper": [10, 12, 999]}}
    out, left = wall_keyed(terr)
    assert left == 2
    assert set(out["station"]) == {1, 2, 10, 11, 12} and set(out["foot"]) == {1, 2, 10, 12}
    assert out["pad"] == {11: "b1"} and out["meet"] == {}


def test_the_airside_is_untouched_by_the_1206_terrace(law, solved):
    """AIRSIDE IS KING: every stage-1 airside value equals the route-free
    airport's (the weld is one-way by construction)."""
    from auto_patch_v2.solve.design_roles import airside_stage_vertices
    _no_wall, (pm0, sol0, _r0), (pm1, sol1, _r1) = solved
    z0 = {pm0.vertices[v].xy: sol0.z[v] for v in airside_stage_vertices(pm0, law)}
    at1 = {pm1.vertices[v].xy: v for v in range(len(pm1.vertices))}
    common = [xy for xy in z0 if xy in at1]
    assert len(common) > 0.8 * len(z0)
    worst = max(abs(sol1.z[at1[xy]] - z0[xy]) for xy in common)
    assert worst <= 0.02, worst


class _LotDem:
    """The apron (y <= 500) on flat ground at 100; north of the wall line
    (y = 505) the ground drops to 97 and climbs again at 4 % across the lot
    — a lot that, left to its DEM, would not be flat."""
    provenance = {"base": "synthetic"}

    def z(self, x: float, y: float) -> float:
        return 97.0 + max(0.0, y - 510.0) * 0.06 if y > 505.0 else 100.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


#: a 3 m wall 0.3 m thick along the apron's north edge, 5 m off it
WALL = box(300.0, 504.85, 500.0, 505.15)


def _lot_airport():
    from auto_patch_v2.model.airport import Building, Pavement, Surface
    from test_classify import _rect, _synthetic
    a = _synthetic(gate=True, island=False)
    lot = Pavement("lot", Surface.CONCRETE, _rect(300.0, 510.0, 500.0, 560.0), ())
    bld = Building("b9", _rect(320.0, 520.0, 480.0, 550.0), (), "osm", None, None)
    return _dc.replace(a, pavements=tuple(a.pavements) + (lot,),
                       buildings=tuple(a.buildings) + (bld,), dem=_LotDem())


def _lot_arm(law, monkeypatch, walls):
    from auto_patch_v2.airport import road_ramp as rr
    # the stub carries ``wall_pieces``' own signature — it takes the
    # [service] record the caller hands over (issue #303)
    monkeypatch.setattr(rr, "wall_pieces",
                        lambda _ap, _cfg=None: tuple(walls))
    return _solve(_lot_airport(), law)


def _span(pm, sol, pred):
    zs = [float(sol.z[v]) for f in pm.faces.values() if pred(f)
          for v in pm.ring_vertices(f.ring)]
    return min(zs), max(zs)


def test_a_wall_between_the_apron_and_a_lower_lot_is_a_declared_terrace(law, monkeypatch):
    """10-03c, synthetic: apron at 100, a 3 m wall along its edge, a lot
    below it carrying a building.  With the wall the lot is graded FLAT to
    its building's level, the apron is unchanged, and ONE ``wall_terrace``
    joint is declared along the wall line at the wall's height; without
    the wall nothing is declared and the lot follows its own ground."""
    from auto_patch_v2.airport.road_ramp import WallPiece
    from auto_patch_v2.pipeline.publication import terrace_joints_ll
    pm1, sol1, r1 = _lot_arm(law, monkeypatch, (WallPiece(WALL, 3.0, "wall.obj#comp0"),))
    pm0, sol0, r0 = _lot_arm(law, monkeypatch, ())
    # the pair rows across the wall are the joint's, not a grade (stage 2)
    assert r1.reach_seed["wall_release"]["walls"] == 1
    assert r0.reach_seed["wall_release"]["released"] == 0
    lot = lambda f: f.ref == "lot" and f.role == "groundside_pavement"  # noqa: E731
    pad = lambda f: f.role == "building" and f.ref != "building1"   # noqa: E731
    apron = lambda f: f.role == "apron"                             # noqa: E731
    # the wall declares exactly one terrace, along its own line
    recs = pm1.road_terrace["wall"]
    assert len(recs) == 1 and next(iter(recs.values()))["pairs"]
    js = [j for j in terrace_joints_ll(pm1, law, sol1.z) if j["kind"] == "wall_terrace"]
    assert len(js) == 1
    assert js[0]["height_m"] == pytest.approx(3.0)
    assert js[0]["declared_step_m"] <= 3.01 + 1e-9
    assert js[0]["length_m"] == pytest.approx(200.0, abs=0.5)
    # the lot at the wall's foot is at its building's level
    rec = next(iter(recs.values()))
    feet = [lv for lv, _pv in rec["pairs"]]
    p0, p1 = _span(pm1, sol1, pad)
    assert feet and all(p0 - 0.15 <= sol1.z[v] <= p1 + 0.15 for v in feet), \
        ([round(float(sol1.z[v]), 2) for v in feet], (p0, p1))
    # the apron is unchanged by the wall
    assert _span(pm1, sol1, apron) == pytest.approx(_span(pm0, sol0, apron), abs=1e-6)
    # without the wall: no declaration, no row, the lot follows its ground
    assert not pm0.road_terrace.get("wall")
    assert not [j for j in terrace_joints_ll(pm0, law, sol0.z) if j["kind"] == "wall_terrace"]
    m0, m1 = _span(pm0, sol0, lot)
    assert m1 - m0 > 2.0


def test_a_piece_shorter_than_its_own_height_is_not_a_wall():
    """#291: a wall-class piece SHORTER THAN ITS OWN HEIGHT (a post, a pier
    stub) is not a wall a terrace runs along (HECA's witness carried 9
    sub-metre records)."""
    from auto_patch_v2.airport.road_ramp import _piece_length, wall_midline
    assert _piece_length(box(0.0, 0.0, 2.5, 0.3)) == pytest.approx(2.5, abs=0.05)
    # a BENT wall is as long as it runs (an L of 2 x 20 m legs: ~40 m)
    from shapely.geometry import LineString
    bent = LineString([(0, 0), (20, 0), (20, 20)]).buffer(0.15, cap_style="flat",
                                                          join_style="mitre")
    assert _piece_length(bent) == pytest.approx(40.0, abs=0.5)
    line = wall_midline(box(0.0, 0.0, 20.0, 0.3))
    assert sorted(line) == [pytest.approx((0.0, 0.15)), pytest.approx((20.0, 0.15))]


def test_the_wall_lot_ruling_is_one_way(law):
    """The lot row follows; the pad leads (``[design] one_way_rulings``)."""
    from auto_patch_v2.constraints.road_ramp import WALL_LOT_RULING
    from auto_patch_v2.solve.design_roles import one_way_rulings, ruling_head
    from auto_patch_v2.model.constraints import Linear, Source
    row = Linear(((1, 1.0), (2, -1.0)), 0.0, 0.0, Source("wall_terrace", WALL_LOT_RULING, ()))
    assert ruling_head(row) in one_way_rulings(law)


def test_a_1206_road_is_governed_on_its_bordered_runs_only():
    """#291: a 1206 corridor / DSF page vertex (``own``) is governed where it
    is bordered or straight between two bordered stations; its pad-bordered
    and bare runs keep their own targets (it is a pad's frontage — holding
    it would drag the pad).  A ribbon vertex keeps 10-03b's full profile."""
    from auto_patch_v2.constraints.road_ramp import terrace_profile
    st = {i: (0, i * 10.0) for i in range(8)}
    foot = {v: (1000 + v, 1000 + v, 0.0, "apron") for v in (0, 3)}
    lv = {1000: 100.0, 1003: 103.0}
    floor = {v: 110.0 for v in st}
    terr = {"foot": foot, "pad": {4: "b1", 5: "b1"}, "station": st}
    rib, _ = terrace_profile(terr, lv, floor, 0.08)
    own, _ = terrace_profile({**terr, "own": {v: True for v in st}}, lv, floor, 0.08)
    assert rib[1] == own[1] == pytest.approx(101.0)          # linked: both
    assert rib[4] == rib[5] == pytest.approx(103.0)          # ribbon: pad-held
    assert 4 not in own and 5 not in own and 6 not in own    # 1206: its own
    assert rib[6] == pytest.approx(103.0 + 0.08 * 10.0)      # ribbon: bare climb


def test_the_pair_rows_across_a_bent_wall_to_its_lot_side_are_released(law):
    """THE WALL IS THE STEP: between the stages a pair row from the road
    kerb to a lot vertex BEYOND a bent wall (its outline, never a chord of
    it) is withdrawn; a road chord past the wall and a pair that does not
    cross it are kept.  MEASURED HECA: ``metal_strip_2.obj`` comp 117 fills
    1.9 % of its rectangle — the chord missed every crossing."""
    from types import SimpleNamespace as NS
    from shapely.geometry import LineString
    from auto_patch_v2.constraints.road_ramp import wall_release
    from auto_patch_v2.model.constraints import ConstraintSet, Diff, Source
    wall = LineString([(0, 1), (20, 1), (20, 21)]).buffer(0.15, cap_style="flat",
                                                        join_style="mitre")
    pts = {0: (10.0, 0.0),      # road kerb (upper), below the wall's first leg
           1: (10.0, 3.0),      # lot vertex beyond it (lower)
           2: (22.0, 10.0),     # road vertex beyond the second leg
           3: (12.0, 0.0)}      # another road kerb vertex
    pm = NS(vertices={v: NS(xy=p) for v, p in pts.items()},
            road_terrace={"wall": {0: {"line": list(wall.exterior.coords),
                                       "height_m": 3.0, "lower": [1]}}})
    src = Source("roads", "x", ())
    cs = ConstraintSet(diffs=(Diff(0, 1, 0.05, 3.0, src),     # across, to the lot
                              Diff(0, 2, 0.05, 15.0, src),    # road chord past the wall
                              Diff(0, 3, 0.05, 2.0, src)))    # same side
    out, rep = wall_release(pm, law, cs)
    assert rep["released"] == 1
    assert [(d.a, d.b) for d in out.diffs] == [(0, 2), (0, 3)]
