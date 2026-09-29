"""Twins for lane ``surfacesettle2`` (issues #21 GEML / #22 TFFJ) — owner
RULINGS 2026-09-27a (10) and (11).

(10) Q-21, GEML: the §37 (9) coverage-edge join pins the patch road at the
core RIBBON's level; where the 5 % pavement ceiling from stage 1's apron
cannot reach it, the RIBBON yields.  ``solve/pin_yield.py`` releases ONLY
the join pins the unsettled hard rows reach (through free columns), every
release is reported, ``emit/road_join.with_pin_yield`` moves the published
join to the patch's level and the core clamp pins its ribbon there
(``clamp_road_network(join_pins=...)``), the budget exceeded at the join.

(11) Q-22, TFFJ: a REACH contact within one lane width seeds the ramp from
stage 1's SOLVED apron level like a touching one —
``constraints/road_ramp.reach_seed_rewrite`` raises the ramp target and its
hard ceiling to ``z_edge - cap * s`` between §20b's stages.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import numpy
import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch_v2.constraints.road_ramp import (GEN, JOIN_RULING, RULING,  # noqa: E402
                                                 RULING_CEILING,
                                                 reach_seed_rewrite)
from auto_patch_v2.emit.road_join import with_pin_yield  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.law.tables import family, role_cap  # noqa: E402
from auto_patch_v2.model.constraints import (Band, ConstraintSet, Diff,  # noqa: E402
                                             Linear, Pin, Source)
from auto_patch_v2.solve.design_roles import ruling_head  # noqa: E402
from auto_patch_v2.solve.pin_yield import (hard_violated, implicated_pins,  # noqa: E402
                                           release_pins, stage1_read_pins)

CEIL = "rulesets.common.pavement_max_grade ceiling (owner 2026-09-09b (4))"
HARD = frozenset({ruling_head(Diff(0, 1, 0.0, 0.0, Source("x", CEIL)))})
YIELD = frozenset({ruling_head(Pin(0, 0.0, Source(GEN, JOIN_RULING)))})


def _cs_geml_like():
    """The GEML shape in five vertices: stage 1's apron edge v0 at 50.84
    (a constant), a lot v1 / v2 under the 5 % ceiling over 20 m hops, and
    the join pin v3 at the ribbon's 56.46 — 5.6 m over 60 m, 9.3 %.  A
    SECOND join v9 on an unrelated road, reachable by nothing violated."""
    src = Source("pavement_ceiling", CEIL)
    diffs = (Diff(0, 1, 0.05, 20.0, src), Diff(1, 2, 0.05, 20.0, src),
             Diff(2, 3, 0.05, 20.0, src), Diff(8, 9, 0.05, 20.0, src))
    pins = (Pin(3, 56.46, Source(GEN, JOIN_RULING, ("vertex:3",))),
            Pin(9, 40.0, Source(GEN, JOIN_RULING, ("vertex:9",))))
    return ConstraintSet(pins=pins, diffs=diffs)


def test_only_the_join_the_unsettled_rows_reach_is_released():
    cs = _cs_geml_like()
    z = numpy.array([50.84, 51.84, 52.84, 56.46, 0, 0, 0, 0, 40.2, 40.0])
    bad = hard_violated(cs, z, HARD, 0.02)
    assert [(r.a, r.b) for r in bad] == [(2, 3)]          # 3.62 m over 20 m
    got = implicated_pins(cs, HARD, YIELD, bad, fixed={0: 50.84})
    assert got == [3]                                     # v9 never moves
    out = release_pins(cs, got, YIELD)
    assert [p.v for p in out.pins] == [9]
    (t,) = [r for r in out.linears if r.terms == ((3, 1.0),)]
    assert t.lo == t.hi == pytest.approx(56.46)           # a target at its own value
    assert t.source.ruling == JOIN_RULING                 # same source: named the same


def test_a_constant_stops_the_flood():
    """Stage 1's level is a constant: a join beyond it is not reached."""
    cs = _cs_geml_like()
    z = numpy.array([50.84, 51.84, 52.84, 56.46, 0, 0, 0, 0, 40.2, 40.0])
    bad = [r for r in cs.diffs if (r.a, r.b) == (0, 1)]
    assert implicated_pins(cs, HARD, YIELD, bad, fixed={1: 51.84}) == []


# ISSUE #87 (RULINGS 2026-09-29d (c); spec-author: the yield is decided from
# STAGE-1 information alone).  HECA 30.13578, 31.41074: the apron/service_road
# join was held at 72.138 m with the platform off and released to 71.853 m
# with it on — stage 2's hard set (the platform's rows) moved a pin stage 1
# had solved the apron against.


def test_a_join_a_stage_1_row_reads_is_stage_ones():
    """v0 is stage 1's apron column; the join v3 is coupled to it by a row
    stage 1 keeps, so v3 is a stage-1 fact.  v9 is reached only through the
    foreign v8 (dropped from stage 1): not stage 1's."""
    cs = _cs_geml_like()
    cs = _dc.replace(cs, diffs=cs.diffs + (
        Diff(0, 3, 0.05, 20.0, Source("pavement_ceiling", CEIL)),))
    assert stage1_read_pins(cs, YIELD, drop={1, 2, 8}) == {3}
    # every coupling of v3 foreign too -> stage 1 never read it
    assert stage1_read_pins(_cs_geml_like(), YIELD, drop={1, 2, 8}) == set()
    assert stage1_read_pins(cs, frozenset(), drop=set()) == set()


def test_stage_2_cannot_release_a_join_stage_1_read():
    """The platform-on arm at the site: stage 2's unsettled row reaches the
    join, but the join is stage 1's (``among`` excludes it) — it is a
    constant that stops the flood, and nothing is released.  The join
    stage 1 never read still yields (GEML, 27a (10), is unchanged)."""
    cs = _cs_geml_like()
    z = numpy.array([50.84, 51.84, 52.84, 56.46, 0, 0, 0, 0, 40.2, 40.0])
    bad = hard_violated(cs, z, HARD, 0.02)
    all_pins = {p.v for p in cs.pins}
    assert implicated_pins(cs, HARD, YIELD, bad, fixed={0: 50.84},
                           among=all_pins - {3}) == []
    assert implicated_pins(cs, HARD, YIELD, bad, fixed={0: 50.84},
                           among=all_pins - {9}) == [3]
    assert implicated_pins(cs, HARD, YIELD, bad, fixed={0: 50.84},
                           among=None) == [3]


# ISSUE #89 (spec-author decision 2026-09-29): the keep test.  At HECA the
# stage-2 worst hard row (3.9474 m, far from every join) moved under 1e-4 m
# between the arms, and ``rep_y.worst < rep.worst`` kept 7-11 join releases
# on that noise.  A release is kept only if the worst drops by at least the
# elevation materiality, or the released pins' OWN rows are held.


def _keep_arm(z_after, worst_before, worst_after):
    """``design._yield_pins`` on the GEML shape plus a FAR violated hard
    row (v5-v6, 3.9474 m over, reached by no join), with the re-solve
    stubbed to return ``z_after`` / ``worst_after``."""
    from types import SimpleNamespace as NS

    from auto_patch_v2.solve.design import _yield_pins
    law = Law.load()
    assert CEIL.split(" (")[0] in law.tables.emit.design.hard_rulings
    cs = _cs_geml_like()
    cs = _dc.replace(cs, diffs=cs.diffs + (
        Diff(5, 6, 0.05, 20.0, Source("pavement_ceiling", CEIL)),))
    z0 = (50.84, 51.84, 52.84, 56.46, 0, 0.0, 4.9474, 0, 40.2, 40.0)
    planar = NS(vertices=[NS(xy=(float(i), 0.0)) for i in range(10)])
    rep0 = NS(hard_max_violation_m=worst_before, hard_settled=False)
    rep1 = NS(hard_max_violation_m=worst_after, hard_settled=False)
    return _yield_pins(planar, cs, law, NS(z=z0), rep0, {0: 50.84},
                       lambda _cs: (NS(z=tuple(z_after)), rep1))


def test_a_noise_level_global_improvement_keeps_no_release():
    """The join's own row is still violated after the release and the far
    worst row moved 5e-5 m: nothing is kept (it was, before #89)."""
    z = (50.84, 51.84, 52.84, 56.40, 0, 0.0, 4.94735, 0, 40.2, 40.0)
    sol, rep, recs, _cs = _keep_arm(z, 3.9474, 3.94735)
    assert recs == []
    assert rep.hard_max_violation_m == 3.9474           # the original kept
    assert sol.z[3] == 56.46


def test_a_real_local_improvement_keeps_the_release():
    """The worst far row is unchanged, but the released join's own row
    (2, 3) is now held: the release is kept and reported."""
    z = (50.84, 51.84, 52.84, 53.84, 0, 0.0, 4.9474, 0, 40.2, 40.0)
    sol, rep, recs, _cs = _keep_arm(z, 3.9474, 3.9474)
    assert [r["v"] for r in recs] == [3]
    assert recs[0]["excess_m"] == pytest.approx(-2.62)
    assert sol.z[3] == 53.84


def test_a_material_global_improvement_keeps_the_release():
    """A worst row lower by more than the materiality (0.01 m) keeps the release even
    where the join's own row is not yet held; 0.009 m does not."""
    z = (50.84, 51.84, 52.84, 56.40, 0, 0.0, 4.9364, 0, 40.2, 40.0)
    assert [r["v"] for r in _keep_arm(z, 3.9474, 3.9364)[2]] == [3]
    assert _keep_arm(z, 3.9474, 3.9384)[2] == []


def test_no_violation_releases_nothing():
    cs = _cs_geml_like()
    assert implicated_pins(cs, HARD, YIELD, [], fixed={}) == []


def test_the_law_names_the_join_as_the_pin_that_yields():
    d = Law.load().tables.emit.design
    assert tuple(d.yielding_pin_rulings) == ("roads.coverage_edge join",)
    assert ruling_head(Pin(0, 0.0, Source(GEN, JOIN_RULING))) in d.yielding_pin_rulings
    # the pin that yields is not a hard row: it is a Pin, reduced away
    assert "roads.coverage_edge join" not in d.hard_rulings


@_dc.dataclass(frozen=True)
class _PM:
    road_coverage_join: dict
    road_join_yield: dict = _dc.field(default_factory=dict)


def test_the_published_join_takes_the_patch_level_and_says_so():
    pm = _PM({3: 56.46, 7: 54.63, 9: 40.0})
    recs = [{"v": 3, "xy": (0, 0), "pinned_m": 56.46, "z_m": 54.28,
             "excess_m": -2.18},
            {"v": 9, "xy": (0, 0), "pinned_m": 40.0, "z_m": 40.004,
             "excess_m": 0.004}]
    out = with_pin_yield(pm, recs, tol_m=0.01)
    assert out.road_coverage_join == {3: 54.28, 7: 54.63, 9: 40.0}
    assert out.road_join_yield == {3: (56.46, 54.28)}     # 9 is within tolerance
    assert with_pin_yield(pm, [], 0.01) is pm


@_dc.dataclass(frozen=True)
class _SeedPM:
    road_reach_seed: dict


def _ramp_cs(vs, t):
    rows_l, rows_b = [], []
    for v in vs:
        rows_l.append(Linear(((v, 1.0),), t, t, Source(GEN, RULING, (f"vertex:{v}", "r"))))
        rows_b.append(Band(v, None, t + 0.5, Source(GEN, RULING_CEILING, (f"vertex:{v}", "r"))))
    return ConstraintSet(linears=tuple(rows_l), bands=tuple(rows_b))


def test_a_reach_seed_raises_target_and_ceiling_to_stage_1s_edge():
    law = Law.load()
    cap = min(role_cap(law, r).longitudinal
              for r in family(law, "road_cross_section").roles if role_cap(law, r))
    vis = float(law.tables.emit.cockpit.visual_m)
    # TFFJ: apron edge (a=100, b=101) solved at 23.7 by stage 1; the road
    # below it on its DEM at 20.0; vertices 1 m, 10 m and 80 m of route
    cs = _ramp_cs((1, 2, 3), 20.0)
    pm = _SeedPM({1: (100, 101, 0.5, 1.0), 2: (100, 101, 0.5, 10.0),
                  3: (100, 101, 0.5, 80.0)})
    out, rep = reach_seed_rewrite(pm, law, cs, {100: 23.6, 101: 23.8})
    tgt = {r.terms[0][0]: r.hi for r in out.linears}
    ceil = {r.v: r.hi for r in out.bands}
    assert tgt[1] == pytest.approx(23.7 - cap * 1.0)
    assert tgt[2] == pytest.approx(23.7 - cap * 10.0)
    assert tgt[3] == pytest.approx(20.0)                  # the floor wins far out
    assert ceil[1] == pytest.approx(23.7 - cap * 1.0 + vis)
    assert ceil[3] == pytest.approx(20.5)                 # untouched
    assert rep["raised"] == 2 and rep["unlevelled"] == 0


def test_a_seed_on_an_edge_stage_1_did_not_level_is_counted_not_guessed():
    law = Law.load()
    cs = _ramp_cs((1,), 20.0)
    out, rep = reach_seed_rewrite(_SeedPM({1: (100, 101, 0.5, 1.0)}), law, cs,
                                  {100: 23.6})
    assert out is cs and rep["unlevelled"] == 1


def test_a_seed_never_lowers_a_target():
    law = Law.load()
    cs = _ramp_cs((1,), 30.0)
    out, rep = reach_seed_rewrite(_SeedPM({1: (100, 101, 0.0, 1.0)}), law, cs,
                                  {100: 23.6, 101: 23.6})
    assert out.linears[0].hi == 30.0 and rep["raised"] == 0


# ── THE CORE RIBBON YIELDS AT THE JOIN ─────────────────────────────────

def _straight_way():
    from shapely import geometry
    import O4_Geo_Utils as GEO
    dlat = 1.0 / GEO.lat_to_m
    line = geometry.LineString([(0.0, i * 20.0 * dlat) for i in range(12)])
    band = geometry.Point(0.0, 0.0).buffer(30.0 * dlat)   # the first ~30 m
    return geometry.MultiLineString([line]), band, dlat


def test_the_ribbon_takes_the_released_join_level_beyond_its_budget():
    import O4_Vector_Utils as VECT
    net, band, dlat = _straight_way()

    def alt_vec(pts):
        return numpy.full(len(pts), 55.87)                 # flat terrain

    base = VECT.clamp_road_network(net, alt_vec, 0.08, 4.0, coverage=band)
    lev = VECT.clamp_road_network(net, alt_vec, 0.08, 4.0, coverage=band,
                                  join_pins=[(0.0, 20.0 * dlat, 54.28)])
    (w0,), (w1,) = base.ways, lev.ways
    assert numpy.allclose(w0["alt"], 55.87)
    k = int(numpy.argmin(numpy.abs(w1["s_m"] - 20.0)))
    assert w1["alt"][k] == pytest.approx(54.28)           # pinned at the patch level
    (rec,) = lev.join_pins[0]
    assert rec["excess_m"] == pytest.approx(1.59 - 1.0, abs=1e-6)
    assert lev.summary()["join_pinned_stations"] == 1
    # the rest of the ribbon climbs back to terrain at its caps
    assert w1["alt"][-1] == pytest.approx(55.87)


def test_no_released_join_leaves_the_ribbon_bit_identical():
    import O4_Vector_Utils as VECT
    net, band, dlat = _straight_way()

    def alt_vec(pts):
        p = numpy.asarray(pts, float)
        return 50.0 + 0.3 * p[:, 1] / dlat                 # a 30 % hill

    a = VECT.clamp_road_network(net, alt_vec, 0.08, 4.0, coverage=band)
    b = VECT.clamp_road_network(net, alt_vec, 0.08, 4.0, coverage=band,
                                join_pins=[])
    assert numpy.array_equal(a.ways[0]["alt"], b.ways[0]["alt"])
    assert b.join_pins == {}
