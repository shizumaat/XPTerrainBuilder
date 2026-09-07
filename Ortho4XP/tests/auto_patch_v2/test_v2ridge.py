"""The v2ridge twins (RULINGS 2026-09-06p; lane v2ridge): (1) THE
RUNWAY-EDGE TIE binds a stub rim 7 m off a runway edge to the strip
transverse bound and the geometric readers — the v2 verify, the v1
oracle's ``strip_transverse`` family and ``tools/harness/runway_edge_
tie.py`` — flag the surface without it; (2) a LATERAL HOP attaches at
the PERPENDICULAR FOOT: a rim vertex whose nearest station is hundreds
of metres away meets the opposite rim across the taxiway's width, never
through the station.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import GENERATORS, generate, roads, zones
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.routes import LATERAL, reach, route_path, routes
from auto_patch_v2.constraints.runway_profile import threshold_pins
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.solve.tiers import row_tier
from auto_patch_v2.verify import census
from auto_patch_v2.verify.strips import FAMILY_STRIP_TRANSVERSE
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _PlaneDem, _rect, _rot

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "harness"))
import check_grade as cg  # noqa: E402
import runway_edge_tie as tool  # noqa: E402

STUB_LEN = 7.0            # the shoulder stub's far rim: 7 m off the runway edge
STUB_X0, STUB_X1 = 100.0, 700.0   # the shoulder stub runs 600 m along the edge
STUB_CL_X = 690.0         # ...and its only centreline is a 7 m cross at its far end
LIFT_M = 6.0              # the ridge: the rim 6 m above the edge


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def build_ridge(law):
    """A runway; a SHOULDER stub along its north edge (``stubC``, HECA
    pav101's class: a 600 m x 7 m face touching the runway edge whose
    only 1202 centreline is a 7 m cross at its far end, so its rim 7 m
    off the edge attaches hundreds of metres away and nothing of its own
    joins it to the edge beside it); a stub to a long parallel taxiway
    (``taxiA``, whose rims hop to interpolated feet on its stationed
    centreline)."""
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", r((600.0, 0.0)), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _PlaneDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -600, -HALF_WIDTH, 600, HALF_WIDTH), (),
             3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "stub", "stubC", _rect(r, STUB_X0, HALF_WIDTH, STUB_X1,
                                       HALF_WIDTH + STUB_LEN), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", (r((-400.0, 91.5)), r((400.0, 91.5)))),
            CutLine("taxi_centerline", "stubB", (r((0.0, HALF_WIDTH)), r((0.0, 91.5)))),
            CutLine("taxi_centerline", "stubC", (r((STUB_CL_X, HALF_WIDTH)),
                                                 r((STUB_CL_X, HALF_WIDTH + STUB_LEN)))))
    pm, stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm, stats


@pytest.fixture(scope="module")
def ridge(law):
    return build_ridge(law)


def _vid(pm, x, y, tol=0.6):
    return min(pm.vertices, key=lambda v: math.hypot(pm.vertices[v].xy[0] - x,
                                                     pm.vertices[v].xy[1] - y)
               if math.hypot(pm.vertices[v].xy[0] - x, pm.vertices[v].xy[1] - y) <= tol
               else 1e9)


def _verts_of_role(pm, role):
    return {v for f in pm.faces.values() if f.role == role
            for v in [*pm.ring_vertices(f.ring), *(u for h in f.holes for u in pm.ring_vertices(h))]}


def _far_rim(pm, x0=STUB_X0 - 0.6, x1=STUB_X0 + 300.0):
    """The shoulder stub's far-rim vertices (y = edge + 7 m) between
    ``x0`` and ``x1`` — hundreds of metres from its only centreline."""
    return sorted(v for v in _verts_of_role(pm, "stub") - _verts_of_role(pm, "runway")
                  if abs(pm.vertices[v].xy[1] - (HALF_WIDTH + STUB_LEN)) < 0.6
                  and x0 <= pm.vertices[v].xy[0] <= x1)


RIDGE_HOLD = (250.0, 450.0)   # the ridge stations held at their unpinned value
RIM_LIFT = (300.0, 400.0)     # the rim vertices lifted onto the ridge


# ── (2) the hop at the perpendicular foot ────────────────────────────────

def test_a_rim_far_from_every_station_hops_to_the_perpendicular_foot(ridge, law):
    airport, pm, _ = ridge
    g = routes(pm, law, airport)
    assert g.stats["feet"] > 0 and g.n > g.n_planar
    taxi = _verts_of_role(pm, "primary_parallel")
    x0 = 200.0
    south = min((v for v in taxi if abs(pm.vertices[v].xy[1] - 80.0) < 0.6),
                key=lambda v: abs(pm.vertices[v].xy[0] - x0))
    north = min((v for v in taxi if abs(pm.vertices[v].xy[1] - 103.0) < 0.6),
                key=lambda v: abs(pm.vertices[v].xy[0] - x0))
    xs, xn = pm.vertices[south].xy[0], pm.vertices[north].xy[0]
    assert abs(xs - x0) < 60.0 and abs(xn - x0) < 60.0
    snap = law.tables.emit.identity.min_distinct_spacing_m
    stations = {v for v in pm.vertices if g.station[v] and not g.is_foot(v)}
    near_station = min(abs(pm.vertices[s].xy[0] - xs) for s in stations if s in taxi
                       and abs(pm.vertices[s].xy[1] - 91.5) < 0.6)
    assert near_station > snap, near_station          # the foot is INSIDE a segment
    d, bud, path = route_path(g, south, north)
    # across the taxiway at its width: hop to the foot, along the segment
    # between the two feet, hop to the other rim — never via a station
    assert d == pytest.approx(23.0 + abs(xs - xn), abs=2.0 * snap + 1.0), (d, path)
    assert len(path) >= 3 and g.is_foot(path[1]) and all(g.station[u] for u in path[1:-1])
    fa, fb, t = g.foot[path[1]]
    assert 0.0 < t < 1.0 and fa in stations and fb in stations
    (ax, ay), (bx, by) = pm.vertices[fa].xy, pm.vertices[fb].xy
    assert abs(ay - 91.5) < 0.6 and abs(by - 91.5) < 0.6
    assert ax + t * (bx - ax) == pytest.approx(xs, abs=snap)
    # the shoulder stub's rim: its nearest centreline is the 7 m cross at
    # x = 690, hundreds of metres away — HECA pav101's class: the hop
    # clamps to that cross's station and the runway edge 7 m away is
    # hundreds of route metres off (the tie, not the hop, binds it)
    rim = _far_rim(pm)
    assert rim
    v = min(rim, key=lambda u: pm.vertices[u].xy[0])       # the westernmost
    edge = min(_verts_of_role(pm, "runway"),
               key=lambda u: math.hypot(pm.vertices[u].xy[0] - pm.vertices[v].xy[0],
                                        pm.vertices[u].xy[1] - pm.vertices[v].xy[1]))
    assert math.hypot(pm.vertices[edge].xy[0] - pm.vertices[v].xy[0],
                      pm.vertices[edge].xy[1] - pm.vertices[v].xy[1]) < STUB_LEN + 1.0
    m = (g.a == v) | (g.b == v)
    assert m.sum() == 1 and float(g.length[m][0]) > 400.0
    dr, _br, pr = route_path(g, v, edge)
    assert dr > 800.0, (dr, pr)
    ct = T.role_cap(law, "primary_parallel", None, "D").transverse
    cl = T.role_cap(law, "primary_parallel", None, "D").longitudinal
    assert bud == pytest.approx(ct * 23.0 + cl * abs(xs - xn), abs=cl * 2.0 * snap + 0.02)
    # the reach ceiling arrives AT the foot: the centreline's value there
    # plus the hop — not the station's value plus a 200 m walk
    band = reach(g, threshold_pins(pm, law, airport))
    j = _vid(pm, 0.0, 91.5)               # where stubB's centreline meets taxiA's
    assert band[south][1] == pytest.approx(band[j][1] + cl * abs(xs) + ct * 11.5,
                                           abs=cl * snap + 0.02)
    end = _vid(pm, 400.0, 91.5)
    assert band[south][1] < band[end][1] - 1.0


def test_the_hop_row_is_a_three_term_linear_on_the_segment_ends(ridge, law):
    from auto_patch_v2.constraints import taxi
    airport, pm, _ = ridge
    g = routes(pm, law, airport)
    rows = taxi.taxi_chain(pm, law, airport)
    feet = {ft[:2] for ft in g.foot.values()}
    three = [r for r in rows if isinstance(r, Linear)]
    assert three and all(len(r.terms) == 3 and r.lo == -r.hi for r in three)
    on_taxi = [r for r in three
               if all(abs(pm.vertices[u].xy[1] - 91.5) < 0.6 for u, _c in r.terms[1:])]
    assert on_taxi
    ct = T.role_cap(law, "primary_parallel", None, "D").transverse
    for r in on_taxi:
        v = r.terms[0][0]
        assert r.terms[0][1] == 1.0 and -(r.terms[1][1] + r.terms[2][1]) == pytest.approx(1.0)
        assert r.hi == pytest.approx(ct * abs(pm.vertices[v].xy[1] - 91.5), abs=ct * 0.6)
        assert (r.terms[1][0], r.terms[2][0]) in feet


# ── (1) the runway-edge tie ──────────────────────────────────────────────

def test_the_tie_binds_the_stub_rim_7m_off_the_edge(ridge, law):
    airport, pm, _ = ridge
    rim = _far_rim(pm)
    assert rim
    rows = zones.strip_transverse(pm, law, airport)
    by_v = {r.terms[0][0]: r for r in rows}
    runway = _verts_of_role(pm, "runway")
    rw = next(f for f in pm.faces.values() if f.role == "runway")
    bound = T.strip_transverse_bound(law, STUB_LEN, rw.code_number, rw.code_letter)
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    for v in rim:
        r = by_v.get(v)
        assert r is not None, f"no tie row on stub rim vertex {v}"
        assert r.lo is None and r.hi == pytest.approx(bound, abs=0.03 * 0.6)
        assert all(u in runway for u, _c in r.terms[1:])
        # the strip's row: it cites the strip face and sits in the strip's tier
        assert r.source.inputs[0].startswith("face:")
        assert pm.faces[int(r.source.inputs[0][5:])].role == "graded_strip"
        assert row_tier(pm, r, tier_of, len(tt) - 1) == tier_of["graded_strip"]
    # no runway-family vertex is ever tied
    assert not (set(by_v) & runway)


def _solve(ridge, law, only=None):
    airport, pm, _ = ridge
    cs, _c, _w = generate(pm, law, airport, only=only)
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return cs, sol


def _emit(ridge, law, sol, out_dir):
    airport, pm, _ = ridge
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    rows = census(surf, law, pub, roads.road_law_caps(pm, law))[FAMILY_STRIP_TRANSVERSE]
    paths = write_patch(surf, law, out_dir, pub)
    return rows, paths.patch


def _oracle(patch):
    nodes, ways = cg._parse_osm(Path(patch))
    return cg._check_runway_edge_tie(ways, nodes, cg._ll_to_m_factory(nodes))


def test_the_readers_flag_the_ridge_and_the_solve_holds_it(ridge, law, tmp_path):
    """The hard solve with the tie: every reader 0.  The same surface
    with the stub rim lifted 6 m (the HECA ridge, v2921 +6.02 at 6.6 m):
    the v2 verify, the oracle's ``strip_transverse`` family and the
    harness tool all flag the rim vertices, at the same magnitude."""
    airport, pm, _ = ridge
    _cs, sol = _solve(ridge, law)
    rows, patch = _emit(ridge, law, sol, tmp_path / "held")
    assert rows == [], rows[:2]
    assert _oracle(patch) == []
    held = tool.read_ties(patch, "ZZZZ")
    assert held and not any(r.over for r in held)
    assert {r.roles for r in held} >= {"stub", "primary_parallel+stub"} or any("stub" in r.roles for r in held)
    # the ridge
    rim = _far_rim(pm)
    z2 = list(sol.z)
    for v in rim:
        z2[v] += LIFT_M
    lifted = _dc.replace(sol, z=tuple(z2))
    rows, patch = _emit(ridge, law, lifted, tmp_path / "ridge")
    flagged = [r for r in rows if r["direction"] == "above"]
    assert len(flagged) >= len(rim)
    assert all("stub" in r["roles"] and "runway" in r["roles"] for r in flagged[:len(rim)])
    assert max(r["magnitude_m"] for r in flagged) == pytest.approx(LIFT_M, abs=0.3)
    ora = _oracle(patch)
    assert len(ora) >= len(rim)
    assert max(v.de_m for v in ora) == pytest.approx(LIFT_M, abs=0.3)
    assert all(v.excess_pct > 0 and v.cap_pct is not None for v in ora)
    got = tool.read_ties(patch, "ZZZZ")
    over = [r for r in got if r.over]
    assert len(over) >= len(rim) and max(r.rise for r in over) == pytest.approx(LIFT_M, abs=0.3)
    assert tool.main([str(patch), "--icao", "ZZZZ"]) == 1
    # the oracle's family is registered in its emission position and keyed
    # on the v2 refs: a patch with no adjacent_ground:* way reads nothing
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert keys.index(cg.RUNWAY_EDGE_TIE_FAMILY) == keys.index("strip_seam_tear") + 1
    assert cg.RUNWAY_EDGE_TIE_FAMILY == FAMILY_STRIP_TRANSVERSE


def test_without_the_tie_the_solve_leaves_the_rim_on_its_dem_and_the_readers_see_it(ridge, law, tmp_path):
    """The mechanism the ruling names: the runway held on its profile
    (HECA's: the 109 m hold and K cut it 3.4–5.8 m under the DEM) and
    the shoulder stub's rim pinned 6 m over it — with the tie generator
    OFF the hard set is FEASIBLE (nothing of the stub's own joins its rim
    to the edge 7 m away: its hop runs to a cross hundreds of metres off)
    and every geometric reader flags the ridge; with the tie ON the same
    pins are INFEASIBLE."""
    from auto_patch_v2.constraints.runway_profile import ridge_chains
    from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
    airport, pm, _ = ridge
    rim = _far_rim(pm, *RIM_LIFT)
    assert len(rim) >= 2
    only = {n for n, _ in GENERATORS} - {"strip_transverse"}
    cs, _c, _w = generate(pm, law, airport, only=only)
    base = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    assert base.status in (Status.OPTIMAL, Status.FEASIBLE), base.message
    src = Source("test", "the ridge", ())
    vw = view(pm, law)
    held = [u for chs in ridge_chains(vw).values() for c in chs for u in c
            if RIDGE_HOLD[0] <= pm.vertices[u].xy[0] <= RIDGE_HOLD[1]]
    assert held
    pins = [Pin(v, float(base.z[v]) + LIFT_M, src) for v in rim] + \
        [Pin(u, float(base.z[u]), Source("test", "the profile held", ())) for u in held]
    sol = solve(pm, ConstraintSet.from_rows(list(cs.rows()) + pins), DEFAULT_WEIGHTS,
                Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    rows, patch = _emit(ridge, law, sol, tmp_path / "notie")
    assert len(rows) >= len(rim)
    assert max(r["magnitude_m"] for r in rows) == pytest.approx(LIFT_M, abs=0.5)
    ora = _oracle(patch)
    assert len(ora) >= len(rim) and max(v.de_m for v in ora) == pytest.approx(LIFT_M, abs=0.5)
    assert sum(r.over for r in tool.read_ties(patch, "ZZZZ")) >= len(rim)
    cs_tie, _c, _w = generate(pm, law, airport)
    sol2 = solve(pm, ConstraintSet.from_rows(list(cs_tie.rows()) + pins), DEFAULT_WEIGHTS,
                 Options(diagnose_iis=False))
    assert sol2.status not in (Status.OPTIMAL, Status.FEASIBLE)
