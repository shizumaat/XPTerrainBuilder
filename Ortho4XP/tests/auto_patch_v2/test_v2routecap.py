"""A TAXI ROUTE THROUGH AN APRON CARRIES THE TAXIWAY LAW (owner, RULINGS
2026-09-06t; spec ``docs/specs/auto-patch-v2/apron-route-cap-spec.md``):

* §2 ``stretches.edge_cap``: a stretch edge bounded by apron faces keeps
  the stretch's cap; bounded by a runway slab it is tightened.
* §3 the apron's short pairs inside the route's corridor (the letter's
  taxiway half-width) are the BOX against the crossing stretch; pairs
  outside every corridor keep the apron cap.
* §4 the synthetic apron (200 × 60 m, 1 %) with one letter-E stretch
  along its middle: a 1.5 m rise between two route vertices 100 m apart;
  a 1.6 m rise is infeasible and the IIS names the route rows.
  MEASURED (lane v2routecap 2026-09-06): under the spec's LETTER (the box
  on pairs under 30 m only) the rise is INFEASIBLE — the apron's long
  frontage chords (41 / 61 m at 1 %) from the abeam vertex to the route's
  stations re-cap the route; with the corridor box on every in-corridor
  pair (``emit.within_shape.apron_corridor_pair_max_m``, the round's
  experiment knob) the §4 twin holds.  Both arms are recorded here for
  the ruling; the default is the spec's letter.
* Oracle / v2 verify LOCKSTEP on the fixture, both arms.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, roads
from auto_patch_v2.constraints.apron import CORRIDOR_RULING, STATS as APRON_STATS
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
LITERAL, EXTENDED = "literal-30m", "every-in-corridor-pair"
sys.path.insert(0, str(ROOT / "tools"))
import check_grade as cg  # noqa: E402

RISE_OK_M = 1.5           # 1.5 % × 100 m between the two route vertices
RISE_BAD_M = 1.6
APRON_CAP = 0.010
LANE_Y = 330.0            # the letter-E stretch along the apron's middle
ROUTE_A = (50.0, LANE_Y)
ROUTE_B = (150.0, LANE_Y)
ABEAM_A = (110.0, 340.0)  # two ring vertices 10 m abeam the route, 10 m apart
ABEAM_B = (120.0, 340.0)
NOTCH_A = (110.0, 360.0)  # the notch's outer corner: 30 m off the axis


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


def _arm(law, arm):
    """The law under one arm: the spec's letter (the default) or the
    corridor box on every in-corridor apron pair."""
    if arm == LITERAL:
        return law
    ws = _dc.replace(law.tables.emit.within_shape, apron_corridor_pair_max_m=1e9)
    emit = _dc.replace(law.tables.emit, within_shape=ws)
    return _dc.replace(law, tables=_dc.replace(law.tables, emit=emit))


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
    # corners sit 10 m abeam the lane (inside letter E's 11.5 m corridor)
    apron = ((0.0, 300.0), (200.0, 300.0), (200.0, 360.0), (120.0, 360.0),
             ABEAM_B, ABEAM_A, NOTCH_A, (0.0, 360.0))
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
    assert lane.code_letter == "E" and lane.cap_l == pytest.approx(0.015)
    assert lane.half_width_m == pytest.approx(taxi_half_width_m(law, "E")) == 11.5
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


# ── §3: the corridor box on the apron's short pairs ───────────────────────

def test_short_pairs_in_the_corridor_are_boxed_and_the_rest_keep_the_apron_cap(site, law):
    airport, pm = site
    cs, counts, _w = generate(pm, law, airport, only={"apron_within_shape"})
    a, b, c = _vid(pm, ABEAM_A), _vid(pm, ABEAM_B), _vid(pm, NOTCH_A)
    boxed = [r for r in cs.rows() if isinstance(r, Diff) and r.source.ruling == CORRIDOR_RULING]
    assert boxed and APRON_STATS["apron_within_shape"]["corridor_box"] == len(boxed)
    # (a, b): 10 m along the axis, 10 m abeam → the box 1.5 % × 10 = 0.15 m
    ab = _pair_rows(cs, a, b)
    assert len(ab) == 1 and ab[0].source.ruling == CORRIDOR_RULING
    assert ab[0].bound_m == pytest.approx(0.015 * 10.0, abs=1e-9)
    # (a, c): 20 m across, midpoint 20 m off the axis → outside the corridor
    ac = _pair_rows(cs, a, c)
    assert len(ac) == 1 and ac[0].source.ruling != CORRIDOR_RULING
    assert ac[0].cap == pytest.approx(APRON_CAP)
    # every boxed pair is short and has its midpoint inside the corridor
    hw = taxi_half_width_m(law, "E")
    for r in boxed:
        (xa, ya), (xb, yb) = pm.vertices[r.a].xy, pm.vertices[r.b].xy
        assert r.d < law.tables.emit.within_shape.withdrawn_chord_min_m
        assert abs(0.5 * (ya + yb) - LANE_Y) <= hw + 1e-9
    # no long pair is boxed; a long spine chord from the abeam vertex to a
    # route vertex is still the apron's 1 % row (the spec's §3 letter)
    ra = _vid(pm, ROUTE_A)
    long_rows = _pair_rows(cs, a, ra)
    assert long_rows and all(r.source.ruling != CORRIDOR_RULING for r in long_rows)


# ── §4: the route through the apron carries 1.5 % ─────────────────────────

def _solve(site, law, extra=(), diagnose=False, arm=LITERAL):
    airport, pm = site
    law = _arm(law, arm)
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
    assert len(rows) == 1 and rows[0].cap == pytest.approx(0.015)
    assert rows[0].bound_m == pytest.approx(0.75)


def test_the_route_own_rows_carry_1_5pc_and_refuse_1_6pc(site, law):
    """§2's claim on the route's OWN law: the chain rows (centrelines +
    hops) admit the 1.5 m rise over 100 m and refuse 1.6 m, the IIS
    naming the centreline rows through the apron."""
    airport, pm = site
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, ROUTE_B)
    for rise, ok in ((RISE_OK_M, True), (RISE_BAD_M, False)):
        cs, _c, _w = generate(pm, law, airport, only={"taxi_centerlines", "taxi_chain"})
        cs = ConstraintSet.from_rows([*cs.rows(), *_pins(pm, rise)])
        sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=True))
        if ok:
            assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
            assert sol.z[rb] - sol.z[ra] == pytest.approx(rise, abs=1e-5)
        else:
            assert sol.status == Status.INFEASIBLE, sol.status
            route = [r for r, _s in sol.iis if isinstance(r, Diff) and r.source.generator == "taxi"
                     and "centreline" in r.source.ruling]
            assert len(route) == 2 and all(r.cap == pytest.approx(0.015) for r in route)


@pytest.mark.parametrize("arm, named", [
    (LITERAL, [("apron", 41.2), ("apron", 60.8)]),
    (EXTENDED, [("apron", 58.3), ("apron", 58.3)]),
])
def test_the_apron_frontage_chords_recap_the_route_under_both_arms(site, law, arm, named):
    """THE MEASURED REFUTATION of the spec's §4 premise (module docstring),
    reported to the spec's author, not decided here.  Under the LETTER
    (the box on pairs under 30 m) the abeam vertex's 41 / 61 m frontage
    chords to the route's stations bind at 1 %; with the box on EVERY
    in-corridor pair the south-edge vertex (100, 300) — 30 m off the
    axis, outside any taxiway half-width — binds through its two 58.3 m
    chords (Σ 1.17 m < 1.5 m).  Arithmetic: any apron vertex with
    d(RA) + d(RB) < 150 m re-caps the route under "1 % all directions"."""
    airport, pm = site
    cs, sol = _solve(site, law, extra=_pins(pm, RISE_OK_M), diagnose=True, arm=arm)
    assert sol.status == Status.INFEASIBLE, sol.status
    iis = sorted((r.source.generator, round(r.d, 1)) for r, _s in sol.iis if isinstance(r, Diff))
    assert iis == named, iis
    assert all("frontage chord" in r.source.ruling for r, _s in sol.iis if isinstance(r, Diff))
    # the ring pair 30 m off the axis keeps the apron cap in both arms
    c = _vid(pm, NOTCH_A)
    rows = [r for r in cs.rows() if isinstance(r, Diff) and c in (r.a, r.b)
            and r.source.generator == "apron"]
    assert rows and all(r.cap == pytest.approx(APRON_CAP) for r in rows
                        if r.source.ruling != CORRIDOR_RULING)


def test_the_extended_arm_boxes_the_long_in_corridor_chords_in_generator_and_verify(site, law, tmp_path):
    """The knob's population (v2 only: the oracle reads the checked-in
    default law): every in-corridor pair, the 60.8 m frontage chord from
    the abeam vertex to ROUTE_A included, and the verify reads it."""
    airport, pm = site
    a, ra = _vid(pm, ABEAM_A), _vid(pm, ROUTE_A)
    ext = _arm(law, EXTENDED)
    cs, _c, _w = generate(pm, ext, airport, only={"apron_within_shape"})
    rows = _pair_rows(cs, a, ra)
    assert len(rows) == 1 and rows[0].source.ruling == CORRIDOR_RULING
    assert rows[0].bound_m == pytest.approx(0.015 * 60.0 + 0.015 * 10.0, abs=1e-9)
    cs, sol = _solve(site, law, arm=EXTENDED)
    z = list(sol.z)
    z[a] = z[ra] + 2.0
    surf = graded_surface(pm, ext, _dc.replace(sol, z=tuple(z)), airport.frame.origin,
                          airport.frame.crs)
    pub = publication(pm, ext, airport, tuple(z))
    v2 = census(surf, ext, pub, roads.road_law_caps(pm, ext))[FAMILY_TAXI_BOX]
    assert [r for r in v2 if r["distance_m"] == pytest.approx(60.8, abs=0.2)], \
        sorted(round(r["distance_m"], 1) for r in v2)


# ── lockstep: the oracle and the v2 verify read the same rows ─────────────

def _readers(site, law, sol, out_dir, arm=LITERAL):
    airport, pm = site
    law = _arm(law, arm)
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert all(len(e) == 5 for e in pub["stretches"])
    v2 = census(surf, law, pub, roads.road_law_caps(pm, law))
    paths = write_patch(surf, law, out_dir, pub)
    fam: dict = {}
    cg.run_checks_law_true(Path(paths.patch), family_out=fam)
    return v2, fam, dict(cg._TAXI_BOX_STATS)


def test_oracle_and_verify_read_the_corridor_box_in_lockstep(site, law, tmp_path):
    arm = LITERAL                 # the oracle reads the checked-in law dir
    airport, pm = site
    cs, sol = _solve(site, law, arm=arm)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    a, b, c = _vid(pm, ABEAM_A), _vid(pm, ABEAM_B), _vid(pm, NOTCH_A)
    # the solution itself: both readers read no box row and no apron row
    v2, fam, stats = _readers(site, law, sol, tmp_path / "held", arm)
    assert v2[FAMILY_TAXI_BOX] == [] and list(fam.get(cg.TAXI_BOX_FAMILY) or []) == []
    apron_within = [r for r in v2["within_shape"] if r["roles"][0] == "apron"] \
        if v2["within_shape"] and "roles" in v2["within_shape"][0] else \
        [r for r in v2["within_shape"] if "apron" in str(r)]
    assert apron_within == [], apron_within[:3]
    assert stats.get("pairs", 0) > 0
    # a 0.5 m step imposed on ABEAM_A: the 10 m pair to ABEAM_B is the box
    # (0.15 m) in BOTH readers; the 20 m pair to the notch corner is the
    # apron's 1 % row (0.20 m) in BOTH readers, never the box
    z = list(sol.z)
    z[a] = z[a] + 0.5
    v2s, fams, _st = _readers(site, law, _dc.replace(sol, z=tuple(z)), tmp_path / "step", arm)
    # (the census frame is equirectangular, ~0.25 % off the solve's)
    v2_box = [r for r in v2s[FAMILY_TAXI_BOX] if r["distance_m"] == pytest.approx(10.0, abs=0.1)]
    or_box = [r for r in (fams.get(cg.TAXI_BOX_FAMILY) or [])
              if r.distance_m == pytest.approx(10.0, abs=0.1)]
    assert len(v2_box) == 1 and len(or_box) == 1, (len(v2_box), len(or_box))
    assert v2_box[0]["cap_pct"] == pytest.approx(1.5, abs=1e-6)
    assert or_box[0].cap_pct == pytest.approx(1.5, abs=1e-3)   # the frame's Δs/Δt split
    # (the v1 oracle forgives the apron's own 1 % rows here — its apron
    # envelope, pre-existing and not this lane's population; what this
    # twin holds is that NEITHER reader boxes the out-of-corridor pair)
    v2_apron = [r for r in v2s["within_shape"] if r["distance_m"] == pytest.approx(20.0, abs=0.1)]
    assert len(v2_apron) == 1 and v2_apron[0]["cap_pct"] == pytest.approx(1.0, abs=1e-6)
    assert not [r for r in v2s[FAMILY_TAXI_BOX] if r["distance_m"] == pytest.approx(20.0, abs=0.1)]
    assert not [r for r in (fams.get(cg.TAXI_BOX_FAMILY) or [])
                if r.distance_m == pytest.approx(20.0, abs=0.1)]
    # the whole box population agrees: the same rows (by distance) over
    # the step — the 10 m ring edge and the 14.1 m spine chord to the
    # route vertex (100, 330), both inside the corridor
    v2_d = sorted(round(r["distance_m"], 1) for r in v2s[FAMILY_TAXI_BOX])
    or_d = sorted(round(r.distance_m, 1) for r in (fams.get(cg.TAXI_BOX_FAMILY) or []))
    assert v2_d == or_d == [10.0, 14.1], (v2_d, or_d)
