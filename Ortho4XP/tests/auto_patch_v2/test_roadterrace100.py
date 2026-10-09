"""OWNER RULINGS 2026-10-03b (#100, NLWF): THE ROAD TERRACE — a mapped-road
ribbon bordering airside pavement takes that pavement's level (a cut
terrace) and climbs at <= the road cap only on bare runs, from the level of
the last bordered pavement.  Derivation ``airport/road_ramp.road_terrace``
(geometry, pre-solve); profile + stage-2 rewrite
``constraints/road_ramp.terrace_profile`` / ``terrace_rewrite``."""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.classify import classify
from auto_patch_v2.constraints.road_ramp import terrace_profile
from auto_patch_v2.law import Law
from auto_patch_v2.planar.build import build as planar_build

from test_roadmint100 import SOUTH, _SlopeDem, _way, _with

CAP = 0.08


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _route(n, step=10.0):
    """One route of ``n`` stations ``step`` apart, vertex id = index."""
    return {i: (0, i * step) for i in range(n)}


def _feet(levels_by_v):
    """``foot`` entries whose (a, b) are two airside columns carrying the
    level: column ``1000 + v`` (u = 0)."""
    foot = {v: (1000 + v, 1000 + v, 0.0, "apron") for v in levels_by_v}
    lv = {1000 + v: z for v, z in levels_by_v.items()}
    return foot, lv


def test_a_bordered_run_on_a_hillside_takes_the_flat_pavement_level():
    """Beside a FLAT apron (level 100) the DEM-read floor climbs 1 m per
    station: every bordered station targets 100 — no climb."""
    st = _route(6)
    foot, lv = _feet({v: 100.0 for v in st})
    floor = {v: 100.0 + v for v in st}
    out, rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor, CAP)
    assert out == {v: 100.0 for v in st}
    assert rep["bordered"] == 6 and rep["bare"] == 0
    assert rep["max_cut_m"] == pytest.approx(5.0)


def test_a_bordered_run_beside_a_sloping_taxiway_slopes_with_it():
    """Beside a taxiway falling 1.5 % the road falls with it (no
    over-flattening on a sloping airport)."""
    st = _route(6)
    foot, lv = _feet({v: 100.0 - 0.015 * 10.0 * v for v in st})
    out, _rep = terrace_profile({"foot": foot, "pad": {}, "station": st},
                                lv, {v: 120.0 for v in st}, CAP)
    for v in st:
        assert out[v] == pytest.approx(100.0 - 0.15 * v)


def test_a_bare_run_climbs_at_the_cap_from_the_last_bordered_level():
    """Stations 0-2 bordered at 100; 3-9 bare with the terrain at 110:
    the road climbs at the cap from 100 until it meets the terrain."""
    st = _route(10)
    foot, lv = _feet({0: 100.0, 1: 100.0, 2: 100.0})
    floor = {v: 110.0 for v in st}
    out, rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor, CAP)
    for v in range(3, 10):
        d = (v - 2) * 10.0
        assert out[v] == pytest.approx(min(110.0, 100.0 + CAP * d))
        assert out[v] - out[v - 1] <= CAP * 10.0 + 1e-9
    assert rep["bare"] == 7


def test_a_run_between_two_bordered_runs_is_straight_and_a_pad_frontage_is_held():
    """Stations 0 and 6 bordered (100 / 103), 1-5 between them over a hill:
    straight between the two levels, never up the hill.  Past station 6, two
    pad-bordered stations hold 103, then a bare run climbs from there."""
    st = _route(12)
    foot, lv = _feet({0: 100.0, 6: 103.0})
    floor = {v: 120.0 for v in st}
    pad = {7: "b1", 8: "b1"}
    out, rep = terrace_profile({"foot": foot, "pad": pad, "station": st}, lv, floor, CAP)
    for v in range(1, 6):
        assert out[v] == pytest.approx(100.0 + 0.5 * v)
    assert out[7] == out[8] == pytest.approx(103.0)
    assert out[9] == pytest.approx(103.0 + CAP * 10.0)
    assert rep["linked"] == 5 and rep["pad_held"] == 2


def test_a_coverage_join_is_reached_at_the_cap():
    """A §37 (9) join pinned at 110 two stations past a bordered run at 100:
    the join is never governed, and the road leaves the terrace at the cap
    to meet it (no hard conflict of the ceiling against the pin)."""
    st = _route(6)
    foot, lv = _feet({v: 100.0 for v in range(5)})
    out, rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv,
                               {v: 100.0 for v in st}, CAP, anchors={5: 110.0})
    assert 5 not in out
    for v in range(5):
        assert out[v] == pytest.approx(max(100.0, 110.0 - CAP * 10.0 * (5 - v)))
    assert rep["anchored"] >= 1


def _solve(airport, law):
    from auto_patch_v2.airport.road_ramp import with_road_ramp
    from auto_patch_v2.classify.rules import load_rules
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.no_step import hold_pass
    from auto_patch_v2.constraints.road_ramp import reach_seed_rewrite
    from auto_patch_v2.pipeline.stage_one_map import stage_one_problem
    from auto_patch_v2.solve import solve_design

    # issue #303: the [service] thresholds are the CALLER's to hand over
    # (``airport`` may not read ``classify``) — the same record
    # ``pipeline/build`` passes, so this arm stays the build's own frame.
    svc = load_rules().service

    def derive(cl0):
        pm0, _ = planar_build(airport, cl0, law)
        pm0 = with_road_ramp(pm0, law, airport, service=svc)
        cs0, _c, _w = generate(pm0, law, airport)
        return pm0, cs0, None, hold_pass(pm0, law)
    cl = classify(airport, law)
    pm, _ = planar_build(airport, cl, law)
    pm = with_road_ramp(pm, law, airport, service=svc)
    cs, _c, _w = generate(pm, law, airport)
    s1 = stage_one_problem(cl, derive)
    if s1 is not None:
        s1.bind(pm)
    sol, rep = solve_design(pm, cs, law, hold=hold_pass(pm, law), stage1=s1,
                            stage2_rewrite=lambda lv: reach_seed_rewrite(pm, law, cs, lv))
    return pm, sol, rep


def test_a_ribbon_in_the_runway_strip_on_a_hillside_stays_at_the_runway_level(law):
    """THE NLWF CLASS, synthetic: a tertiary road 40 m south of the runway
    (inside its strip) on a hillside rising 0.5 m per metre south of
    y = -20 (the DEM under the road stands ~10 m above the runway).  Every
    ribbon vertex is BORDERED by the runway (``road_terrace``), the stage-2
    rewrite targets the runway edge's own solved level, the road is solved
    there (the hill is the cut), and every AIRSIDE value equals the
    ribbon-free airport's (airside is untouched by construction)."""
    from auto_patch_v2.model.planar import is_osm_ribbon_ref
    from auto_patch_v2.solve.design_roles import airside_stage_vertices
    a1 = _dc.replace(_with(_way(-3, SOUTH, highway="tertiary")), dem=_SlopeDem())
    a0 = _dc.replace(_with(), dem=_SlopeDem())
    pm1, sol1, rep1 = _solve(a1, law)
    pm0, sol0, _r0 = _solve(a0, law)
    terr = pm1.road_terrace
    rib = {v for f in pm1.faces.values() if is_osm_ribbon_ref(f.ref)
           for v in pm1.ring_vertices(f.ring)}
    gov = set(terr["station"]) & rib
    assert gov and set(terr["foot"]) >= {v for v in gov
                                         if -48.0 <= pm1.vertices[v].xy[1] <= -32.0
                                         and 600.0 < pm1.vertices[v].xy[0] < 900.0}
    assert {terr["foot"][v][3] for v in terr["foot"]} == {"09/27"}
    tr = rep1.reach_seed.get("terrace", {})
    assert tr.get("governed", 0) > 0 and tr.get("bordered", 0) > 0
    # the road is solved at the runway's level, metres under its DEM
    z = sol1.z
    for v in terr["foot"]:
        a, b, u, _ref = terr["foot"][v]
        lvl = (1 - u) * z[a] + u * z[b]
        assert abs(z[v] - lvl) <= 0.6, (v, z[v], lvl)
    assert max(pm1.vertices[v].dem_z - z[v] for v in terr["foot"]) > 5.0
    # airside identical with and without the ribbon
    z0 = {pm0.vertices[v].xy: sol0.z[v] for v in airside_stage_vertices(pm0, law)}
    at1 = {pm1.vertices[v].xy: v for v in range(len(pm1.vertices))}
    assert z0 and all(abs(sol1.z[at1[xy]] - zz) <= 1e-9 for xy, zz in z0.items())


def test_a_fence_along_a_bordered_run_is_recorded_as_the_terrace_witness(law, tmp_path):
    """10-03b's SECOND WITNESS (report only): a pack fence facade running
    along the bordered ribbon (3 m outside its kerb) is recorded in
    ``road_terrace_witness`` with the DEM along it and the level the terrace
    gave the road — and a facade 60 m away, along nothing, is not."""
    from auto_patch_v2.classify import load_rules
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    from auto_patch_v2.pipeline.terrace_witness import terrace_witness
    a1 = _dc.replace(_with(_way(-3, SOUTH, highway="tertiary")), dem=_SlopeDem())
    pm1, sol1, _rep = _solve(a1, law)
    to_ll = a1.frame.transformers()[1]

    def poly(path_idx, pts):
        out = [f"BEGIN_POLYGON {path_idx} 2 2", "BEGIN_WINDING"]
        for x, y in pts:
            lat, lon = to_ll(x, y)
            out.append(f"POLYGON_POINT {lon:.9f} {lat:.9f}")
        return out + ["END_WINDING", "END_POLYGON"]
    lines = ["POLYGON_DEF objects/vele_fence.fac", "POLYGON_DEF objects/other_fence.fac"]
    lines += poly(0, [(620.0, -47.0), (750.0, -47.0), (880.0, -47.0)])
    lines += poly(1, [(620.0, -110.0), (750.0, -110.0), (880.0, -110.0)])
    dump = tmp_path / "x.dsf.txt"
    dump.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    wit = terrace_witness(pm1, a1, sol1.z, load_rules(), str(dump))
    assert [w["object"] for w in wit] == ["objects/vele_fence.fac"]
    w = wit[0]
    assert w["along_share"] >= 0.8 and w["refs"] == ["09/27"]
    assert w["dem_m"]["min"] == pytest.approx(113.5, abs=0.6)
    assert w["agreement_m"]["road_minus_dem_min"] < -5.0     # the road is in the cut
    assert "road_terrace_witness" in SIDECAR_KEYS


# ── THE BARE EXIT IS BUILT AT ITS DESIGN GRADE (RULINGS 2026-10-09c (2b)) ──

DESIGN, LANE = 0.05, 7.0


def _bare_exit(n: int, rise: float):
    """Stations 0-2 bordered at 100, the rest bare with the road's own
    target ``rise`` above; the profile at the design grade."""
    st = _route(n)
    foot, lv = _feet({0: 100.0, 1: 100.0, 2: 100.0})
    floor = {v: 100.0 + rise for v in st}
    return terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor, CAP,
                           design=DESIGN, lane=LANE)


def test_a_bare_run_with_ample_run_leaves_at_the_design_grade():
    """400 m of bare road for a 10 m rise: 5 %, meeting its target after
    200 m — not the cap's 100 m (the cap is a ceiling, 08c (1))."""
    out, rep = _bare_exit(43, 10.0)
    for v in range(3, 43):
        assert out[v] == pytest.approx(min(110.0, 100.0 + DESIGN * (v - 2) * 10.0))
    assert rep["bare_steepened"] == 0 and rep["max_bare_grade"] == DESIGN


def test_a_bare_run_that_fits_only_at_7_3_percent_leaves_at_7_3_percent():
    """100 m of bare road for a 7.3 m rise: the least grade that brings the
    road onto its own target by the end of its run."""
    out, rep = _bare_exit(13, 7.3)
    for v in range(3, 13):
        assert out[v] == pytest.approx(100.0 + 0.073 * (v - 2) * 10.0)
    assert out[12] == pytest.approx(107.3)
    assert rep["bare_steepened"] == 1 and rep["max_bare_grade"] == pytest.approx(0.073)


def test_a_bare_run_that_needs_more_than_the_cap_leaves_at_the_cap():
    """70 m for 10 m is over the cap: built at the cap, as it was."""
    out, rep = _bare_exit(10, 10.0)
    old, _r = terrace_profile({"foot": _feet({0: 100.0, 1: 100.0, 2: 100.0})[0], "pad": {},
                               "station": _route(10)},
                              _feet({0: 100.0, 1: 100.0, 2: 100.0})[1],
                              {v: 110.0 for v in _route(10)}, CAP)
    assert out == pytest.approx(old) and rep["max_bare_grade"] == CAP


def test_the_road_reaches_a_coverage_join_at_the_design_grade_where_the_run_fits():
    """Stations 0-2 bordered at 100, a coverage join pinned at 110 at
    station 42 (400 m on): the join's cone is the design grade's — 10 m
    over 400 m fits 5 % — so the road is on its own target (the 110 m
    ground) until 5 % from the terrace, not held to the cap's cone."""
    st = _route(43)
    foot, lv = _feet({0: 100.0, 1: 100.0, 2: 100.0})
    floor = {v: 110.0 for v in st}
    out, rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor, CAP,
                               {42: 110.0}, design=DESIGN, lane=LANE)
    for v in range(3, 42):
        assert out[v] == pytest.approx(min(110.0, 100.0 + DESIGN * (v - 2) * 10.0))
    assert out[2] == pytest.approx(100.0)             # the bordered level stands


def test_a_join_too_near_for_the_design_grade_is_reached_at_the_least_grade():
    """The join 100 m from the last bordered station, 7.3 m above it."""
    st = _route(13)
    foot, lv = _feet({0: 100.0, 1: 100.0, 2: 100.0})
    floor = {v: 120.0 for v in st}
    out, _rep = terrace_profile({"foot": foot, "pad": {}, "station": st}, lv, floor, CAP,
                                {12: 107.3}, design=DESIGN, lane=LANE)
    for v in range(3, 12):
        assert out[v] == pytest.approx(100.0 + 0.073 * (v - 2) * 10.0)
    assert out[2] == pytest.approx(100.0)
