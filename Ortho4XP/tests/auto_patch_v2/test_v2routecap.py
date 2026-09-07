"""A TAXI ROUTE THROUGH AN APRON CARRIES THE TAXIWAY LAW (owner, RULINGS
2026-09-06t) AND THE APRON BESIDE IT IS ANISOTROPIC (spec author, RULINGS
2026-09-06v; spec ``docs/specs/auto-patch-v2/apron-route-cap-spec.md``,
§3 amended):

* §2 ``stretches.edge_cap``: a stretch edge bounded by apron faces keeps
  the stretch's cap; bounded by a runway slab it is tightened.
* §3 (amended) within an apron face crossed by a stretch EVERY priced
  pair is the BOX against the nearest crossing axis at any length —
  ``|Δz| ≤ cL_stretch·|Δs| + cA·|Δt|``, cA the apron cap: a pair
  perpendicular to the route reads 1 %, a pair parallel to it 40 m off
  reads 1.5 %.  The round-1 corridor (short pairs within the taxiway
  half-width, ``apron_corridor_pair_max_m``) was REFUTED by arithmetic
  and is deleted: the apron's frontage chords to the route's stations
  (any vertex with d(P,A) + d(P,B) < 1.5·d(A,B)) re-capped the route.
* §4 the synthetic apron (200 × 60 m, 1 %) with one letter-E stretch
  along its middle: a 1.5 m rise between two route vertices 100 m apart
  is FEASIBLE on the full generator set; a 1.6 m rise is INFEASIBLE and
  the IIS names the route's rows.
* Oracle / v2 verify LOCKSTEP on a stepped fixture.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, roads
from auto_patch_v2.constraints.apron import ROUTE_BOX_RULING, STATS as APRON_STATS
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.stretches import edge_cap, stretches
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import taxi_half_width_m
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.verify import census
from auto_patch_v2.verify.within import FAMILY_TAXI_BOX

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_grade as cg  # noqa: E402

RISE_OK_M = 1.5           # 1.5 % × 100 m between the two route vertices
RISE_BAD_M = 1.6
APRON_CAP = 0.010
LANE_CAP = 0.015          # letter E
LANE_Y = 330.0            # the letter-E stretch along the apron's middle
ROUTE_A = (50.0, LANE_Y)
ROUTE_B = (150.0, LANE_Y)
ABEAM_A = (110.0, 340.0)  # two ring vertices 10 m abeam the route, 10 m apart
ABEAM_B = (120.0, 340.0)
NOTCH_A = (110.0, 360.0)  # the notch's outer corner: 30 m off the axis
BAY_A = (60.0, 290.0)     # the south bay's floor: ring edges 40 m off the
BAY_B = (140.0, 290.0)    # axis, PARALLEL to the route


class _Dem:
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
def site(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    # the apron: 200 × 60 m with a NOTCH in its north edge whose two inner
    # corners sit 10 m abeam the lane, and a BAY in its south edge whose
    # floor is a ring edge 40 m off the lane, parallel to it
    apron = ((0.0, 300.0), (60.0, 300.0), BAY_A, BAY_B, (140.0, 300.0), (200.0, 300.0),
             (200.0, 360.0), (120.0, 360.0), ABEAM_B, ABEAM_A, NOTCH_A, (0.0, 360.0))
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubA", _rect(-8, 22.5, 8, 80), (), None, "A",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "apron", "apron1", apron, (), None, None, "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 91.5)), "A"),
            CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5)), "D"),
            CutLine("taxi_centerline", "laneE",
                    ((0.0, LANE_Y), ROUTE_A, (100.0, LANE_Y), ROUTE_B, (200.0, LANE_Y)), "E"))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _vid(pm, xy):
    v = min(pm.vertices, key=lambda k: math.dist(pm.vertices[k].xy, xy))
    assert math.dist(pm.vertices[v].xy, xy) < 0.01, (xy, pm.vertices[v].xy)
    return v


def _pair_rows(cs: ConstraintSet, a: int, b: int) -> list[Diff]:
    key = (min(a, b), max(a, b))
    return [r for r in cs.rows() if isinstance(r, Diff) and (min(r.a, r.b), max(r.a, r.b)) == key]


# ── §2: edge_cap ──────────────────────────────────────────────────────────

def test_a_stretch_edge_bounded_by_apron_faces_keeps_the_stretch_cap(site, law):
    airport, pm = site
    vw = view(pm, law)
    st = stretches(pm, law)
    lane = next(s for s in st.items if s.ref == "laneE")
    assert lane.code_letter == "E" and lane.cap_l == pytest.approx(LANE_CAP)
    assert taxi_half_width_m(law, "E") == 11.5      # the width law key (06t), kept
    for eid in lane.edges:
        e = pm.edges[eid]
        roles = {pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None}
        assert roles == {"apron"}, roles          # the lane splits the apron
        assert edge_cap(pm, law, st, eid, vw.caps) == (lane.cap_l, lane.cap_t)
        assert edge_cap(pm, law, st, eid, vw.caps)[0] > APRON_CAP


def test_a_stretch_edge_bounded_by_a_runway_slab_is_tightened(site, law):
    airport, pm = site
    vw = view(pm, law)
    st = stretches(pm, law)
    stub = next(s for s in st.items if s.ref == "stubA")
    assert stub.cap_l == pytest.approx(0.03)      # letter A: 3 % / 2 %
    seen_runway = seen_stub = False
    for eid in stub.edges:
        e = pm.edges[eid]
        roles = {pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None}
        cap = edge_cap(pm, law, st, eid, vw.caps)
        if roles == {"runway"}:
            seen_runway = True
            assert cap == (pytest.approx(0.015), pytest.approx(0.015))
        elif roles == {"stub"}:
            seen_stub = True
            assert cap == (stub.cap_l, stub.cap_t)
    assert seen_runway and seen_stub


# ── §3 (amended): every pair of a crossed apron face is the route box ─────

def test_every_pair_of_the_crossed_apron_is_the_box_with_the_apron_cap_across(site, law):
    airport, pm = site
    cs, counts, _w = generate(pm, law, airport, only={"apron_within_shape"})
    apron_rows = [r for r in cs.rows() if isinstance(r, Diff) and r.source.generator == "apron"]
    boxed = [r for r in apron_rows if r.source.ruling == ROUTE_BOX_RULING]
    # the lane splits the apron into two crossed faces: EVERY apron row is
    # a box row, none isotropic, at any length
    assert boxed and len(boxed) == len(apron_rows)
    assert APRON_STATS["apron_within_shape"]["route_box"] == len(boxed)
    assert max(r.d for r in boxed) > law.tables.emit.within_shape.withdrawn_chord_min_m
    a, b, c = _vid(pm, ABEAM_A), _vid(pm, ABEAM_B), _vid(pm, NOTCH_A)
    # (a, b): 10 m ALONG the axis → 1.5 % × 10 = 0.15 m
    ab = _pair_rows(cs, a, b)
    assert len(ab) == 1 and ab[0].bound_m == pytest.approx(LANE_CAP * 10.0, abs=1e-9)
    # (a, c): 20 m PERPENDICULAR to the route → the apron cap: 1 % × 20
    ac = _pair_rows(cs, a, c)
    assert len(ac) == 1 and ac[0].cap == pytest.approx(APRON_CAP)
    # the bay floor: the ring edges PARALLEL to the route, 40 m off it
    # (outside any taxiway half-width; the planar build nodes the 80 m
    # edge at its 40 m midpoint) → 1.5 %
    floor = [r for r in boxed if abs(pm.vertices[r.a].xy[1] - BAY_A[1]) < 1e-6
             and abs(pm.vertices[r.b].xy[1] - BAY_A[1]) < 1e-6]
    assert sorted(r.d for r in floor) == pytest.approx([40.0, 40.0]), floor
    assert all(r.cap == pytest.approx(LANE_CAP) for r in floor)
    # the abeam vertex's frontage chord to a route station (the chord that
    # re-capped the route under the corridor): boxed, Δs 60 / Δt 10
    ra = _vid(pm, ROUTE_A)
    fr = _pair_rows(cs, a, ra)
    assert len(fr) == 1 and fr[0].source.ruling == ROUTE_BOX_RULING
    assert fr[0].bound_m == pytest.approx(LANE_CAP * 60.0 + APRON_CAP * 10.0, abs=1e-9)


def test_an_apron_face_crossed_by_no_stretch_stays_isotropic(law):
    """The same apron with the lane stopped SHORT of it: no stretch has an
    edge on its ring, every row is the isotropic 1 % (the round-1 §2 twin
    of the crossing definition)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "apron", "apron1", _rect(0, 300, 200, 360), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5)), "D"),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    cs, _c, _w = generate(pm, law, airport, only={"apron_within_shape"})
    rows = [r for r in cs.rows() if isinstance(r, Diff) and r.source.generator == "apron"]
    assert rows and all(r.source.ruling != ROUTE_BOX_RULING for r in rows)
    assert all(r.cap == pytest.approx(APRON_CAP) for r in rows)
    assert APRON_STATS["apron_within_shape"]["route_box"] == 0


# ── §4: the route through the apron carries 1.5 % ─────────────────────────

def _solve(site, law, extra=(), diagnose=False):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport)
    if extra:
        cs = ConstraintSet.from_rows([*cs.rows(), *extra])
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=diagnose))
    return cs, sol


def _pins(pm, rise_m):
    src = Source("twin", "the imposed rise between two route vertices (spec §4)", ())
    return (Pin(_vid(pm, ROUTE_A), 700.0, src), Pin(_vid(pm, ROUTE_B), 700.0 + rise_m, src))


def test_the_centreline_rows_through_the_apron_hold_the_taxiway_cap(site, law):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport, only={"taxi_centerlines"})
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, (100.0, LANE_Y))
    rows = _pair_rows(cs, ra, rb)
    assert len(rows) == 1 and rows[0].cap == pytest.approx(LANE_CAP)
    assert rows[0].bound_m == pytest.approx(0.75)


def test_the_full_generator_set_admits_the_1_5m_rise(site, law):
    """§4: on EVERY generator (the apron's rows included) the 1.5 m rise
    over 100 m of route through the apron is feasible — the round-1
    refutation (the apron's 1 % frontage chords re-capping the route)
    is gone with the box on every pair of the crossed face."""
    airport, pm = site
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, ROUTE_B)
    cs, sol = _solve(site, law, extra=_pins(pm, RISE_OK_M), diagnose=True)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), (sol.status, sol.message, sol.iis)
    assert sol.z[rb] - sol.z[ra] == pytest.approx(RISE_OK_M, abs=1e-5)


def test_a_1_6m_rise_is_infeasible_and_the_iis_names_the_route_rows(site, law):
    airport, pm = site
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, ROUTE_B)
    lane = {v for v in pm.vertices if abs(pm.vertices[v].xy[1] - LANE_Y) < 1e-6}
    cs, sol = _solve(site, law, extra=_pins(pm, RISE_BAD_M), diagnose=True)
    assert sol.status == Status.INFEASIBLE, sol.status
    diffs = [r for r, _s in sol.iis if isinstance(r, Diff)]
    assert diffs
    # every named row lies ALONG the route (both ends on the lane) at the
    # lane's 1.5 % — the centreline rows or the apron's box rows on the
    # same chords — and their bounds sum to the 1.5 m the route admits
    assert all(r.a in lane and r.b in lane for r in diffs), diffs
    assert all(r.cap == pytest.approx(LANE_CAP) for r in diffs)
    assert sum(r.bound_m for r in diffs) == pytest.approx(RISE_OK_M, abs=1e-6)
    assert {ra, rb} <= {v for r in diffs for v in (r.a, r.b)}


# ── lockstep: the oracle and the v2 verify read the same rows ─────────────

def _readers(site, law, sol, out_dir):
    airport, pm = site
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert all(len(e) == 4 for e in pub["stretches"])     # the corridor element is gone
    v2 = census(surf, law, pub, roads.road_law_caps(pm, law))
    paths = write_patch(surf, law, out_dir, pub)
    fam: dict = {}
    cg.run_checks_law_true(Path(paths.patch), family_out=fam)
    return v2, fam, dict(cg._TAXI_BOX_STATS)


def test_oracle_and_verify_read_the_route_box_in_lockstep(site, law, tmp_path):
    airport, pm = site
    cs, sol = _solve(site, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    a = _vid(pm, ABEAM_A)
    # the solution itself: both readers read no box row and no apron row
    v2, fam, stats = _readers(site, law, sol, tmp_path / "held")
    assert v2[FAMILY_TAXI_BOX] == [] and list(fam.get(cg.TAXI_BOX_FAMILY) or []) == []
    assert [r for r in v2["within_shape"] if "apron" in str(r)] == []
    assert stats.get("pairs", 0) > 0
    # a 0.5 m step imposed on ABEAM_A: its 10 m pair along the route (the
    # box 0.15 m), its 20 m pair across it (the box = 1 % × 20 = 0.20 m)
    # and its 14.1 m chord to the route station (100, 330) read OVER in
    # BOTH readers as box rows (its 22.4 m chord to the notch's far corner
    # crosses the notch: dropped by the 05ae face cover in all three
    # readers); the crossed face has NO isotropic row anywhere
    z = list(sol.z)
    z[a] = z[a] + 0.5
    v2s, fams, _st = _readers(site, law, _dc.replace(sol, z=tuple(z)), tmp_path / "step")
    v2_d = sorted(round(r["distance_m"], 1) for r in v2s[FAMILY_TAXI_BOX])
    or_d = sorted(round(r.distance_m, 1) for r in (fams.get(cg.TAXI_BOX_FAMILY) or []))
    assert v2_d == or_d, (v2_d, or_d)
    assert v2_d == [10.0, 14.1, 20.0], v2_d
    # (the census frame is equirectangular, ~0.25 % off the solve's)
    caps = {round(r["distance_m"], 1): r["cap_pct"] for r in v2s[FAMILY_TAXI_BOX]}
    assert caps[10.0] == pytest.approx(1.5, abs=1e-6)     # along the route
    assert caps[20.0] == pytest.approx(1.0, abs=1e-6)     # across it: the apron cap
    or_caps = {round(r.distance_m, 1): r.cap_pct for r in fams[cg.TAXI_BOX_FAMILY]}
    assert or_caps[10.0] == pytest.approx(1.5, abs=1e-3)
    assert or_caps[20.0] == pytest.approx(1.0, abs=1e-3)
    assert [r for r in v2s["within_shape"] if "apron" in str(r)] == []
