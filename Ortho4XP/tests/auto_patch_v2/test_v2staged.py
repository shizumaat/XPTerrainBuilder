"""Twins for §20b THE STAGED SOLVE — AIRSIDE SOLVES FIRST, EVERYTHING ELSE
CONFORMS (owner RULINGS 2026-09-13dh, ordered 2026-09-14an; lane
``v2staged``).

The fixture is the brief's: a runway, an APRON, a building PAD welded to
the apron's edge, and a groundside SERVICE ROAD, over terrain that dips
under the pad and rises under the road — so every coupling the law has
between airside and what conforms to it is live.

What the twins hold, and why each is a law and not a number:

1. **STAGE 2 CANNOT MOVE AIRSIDE.**  Every airside-pavement vertex is
   SUBSTITUTED (``_reduce``'s stage channel) before stage 2 assembles, so
   it carries NO COLUMN there.  Not a bound, not a tolerance: the unknown
   does not exist.
2. **THE SHIPPED VALUE IS STAGE 1's, to 1e-9.**  The staged solve's z on
   every airside vertex IS the airside-alone solve's.
3. **THE SINGLE SOLVE MOVES IT, so the instrument is not vacuous.**  The
   same map with ``staged_solve`` false lands airside somewhere else.
4. **A ROW COUPLING AIRSIDE TO A PAD / ROAD IS ONE-WAY BY CONSTRUCTION.**
   In stage 2 its airside terms are folded into the right-hand side — a
   constant — so no lag and no skirt is needed to keep them from pulling.
5. **THE PAD MEETS THE APRON EDGE.**  A vertex the pad shares with the
   apron is one unknown fixed by stage 1: the weld is exact, and the
   apron's value there is airside's own.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import (_solve_stage, airside_stage_roles,
                                        airside_stage_vertices, stage_split)

RUN_LEN = 1600.0
HALF_W = 22.5


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """A dip under the pad and a rise under the road: neither conforms for
    free."""

    provenance = {"synthetic": "staged"}

    def z(self, x: float, y: float) -> float:
        if -62.0 <= x <= 62.0 and 178.0 <= y <= 242.0:
            return 697.0
        if y > 250.0:
            return 704.0
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


def _cells():
    """The apron, a pad welded to its far edge, and a service road beyond."""
    return [
        Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 260.0, 180.0), (),
             None, None, "airside", "apron", {}),
        Cell(2, "building", "padA", _rect(-60.0, 180.0, 60.0, 240.0), (),
             None, None, "airside", "pad", {}),
        Cell(3, "service_road", "roadA", _rect(-260.0, 252.0, 260.0, 264.0),
             (), None, None, "groundside", "road", {}),
    ]


def _law_arm(law, **design):
    d0 = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit,
                                     design=_dc.replace(d0, **design))))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


@pytest.fixture(scope="module")
def arms(law, built):
    """The matched pair on ONE map: the staged solve and the single solve."""
    pm, cs = built
    staged, rep_s = solve_design(pm, cs, _law_arm(law, staged_solve=True))
    single, rep_1 = solve_design(pm, cs, _law_arm(law, staged_solve=False))
    assert staged.status in (Status.OPTIMAL, Status.FEASIBLE), staged.status
    assert single.status in (Status.OPTIMAL, Status.FEASIBLE), single.status
    return (np.asarray(staged.z, float), rep_s,
            np.asarray(single.z, float), rep_1)


# ── the roles stage 1 owns ───────────────────────────────────────────────

def test_stage_one_is_the_runway_the_taxi_family_and_the_apron(law):
    """§20b (1): the role set is READ FROM THE LAW — every airside
    pavement role that is not rigid.  The pad (``building``, rigid) and
    the strip family (airside, not pavement) are stage 2's."""
    roles = airside_stage_roles(law)
    assert "runway" in roles and "apron" in roles and "junction" in roles
    assert "building" not in roles              # the pad conforms
    assert "graded_strip" not in roles          # the ground conforms
    assert "service_road" not in roles          # groundside conforms
    assert all(r != "parking_lot" for r in roles)


def test_a_pad_vertex_welded_to_the_apron_is_stage_ones(law, built):
    """The weld: a vertex the pad SHARES with the apron is a vertex of an
    airside face, so it is stage 1's — one unknown, decided by airside."""
    pm, _cs = built
    air = airside_stage_vertices(pm, law)
    pad = next(f for f in pm.faces.values() if f.ref == "padA")
    shared = [v for v in pm.ring_vertices(pad.ring) if v in air]
    assert shared, "the fixture's pad fronts the apron"


# ── (1) stage 2 has no airside column at all ─────────────────────────────

def test_stage_two_carries_no_airside_column(law, built):
    """§20b (2)/(3): SUBSTITUTION, not a ±tolerance box.  After stage 1
    every airside vertex is fixed, so stage 2's reduction gives it no
    column — the unknown does not exist and no row can move it."""
    pm, cs = built
    lw = _law_arm(law, staged_solve=True)
    drop, foreign = stage_split(pm, cs, lw)
    levels: dict[int, float] = {}
    _sol1, _rep1 = _solve_stage(pm, cs, lw, drop=drop, fixed=foreign,
                                levelled_out=levels)
    from auto_patch_v2.solve.design import assemble
    from auto_patch_v2.solve.design_report import DesignReport
    base2 = assemble(pm, cs, lw, DesignReport(), fixed=levels)
    air = airside_stage_vertices(pm, lw)
    free = [v for v in sorted(air) if int(base2.red.col[v]) >= 0]
    assert not free, (len(free), free[:8])


# ── (2) the shipped airside value IS stage 1's ───────────────────────────

def test_the_shipped_airside_value_is_stage_ones(law, built, arms):
    """The bar: stage-2 airside values equal stage-1's to 1e-9."""
    pm, cs = built
    lw = _law_arm(law, staged_solve=True)
    drop, foreign = stage_split(pm, cs, lw)
    levels: dict[int, float] = {}
    _sol1, _rep1 = _solve_stage(pm, cs, lw, drop=drop, fixed=foreign,
                                levelled_out=levels)
    z_staged = arms[0]
    air = sorted(airside_stage_vertices(pm, lw))
    d = max(abs(z_staged[v] - levels[v]) for v in air if v in levels)
    assert d <= 1e-9, d


def test_the_single_solve_puts_airside_somewhere_else(law, built, arms):
    """The instrument is not vacuous: with ``staged_solve`` false the SAME
    map lands its airside elsewhere — which is the pull §20b removes."""
    pm, _cs = built
    z_staged, _rs, z_single, _r1 = arms
    air = sorted(airside_stage_vertices(pm, _law_arm(law, staged_solve=True)))
    worst = max(abs(z_staged[v] - z_single[v]) for v in air)
    assert worst > 0.01, worst


# ── (4) the coupling rows are one-way by construction ────────────────────

def test_a_pad_or_road_row_has_a_constant_on_its_airside_side(law, built):
    """§20b (2): a row coupling airside to a pad / road keeps ONLY its
    groundside columns in stage 2 — the airside terms are folded into the
    right-hand side by the reduction, which is what "one-way by
    construction" means.  No ``follows=``, no lag, no skirt."""
    pm, cs = built
    lw = _law_arm(law, staged_solve=True)
    drop, foreign = stage_split(pm, cs, lw)
    levels: dict[int, float] = {}
    _sol1, _rep1 = _solve_stage(pm, cs, lw, drop=drop, fixed=foreign,
                                levelled_out=levels)
    from auto_patch_v2.solve.design import assemble
    from auto_patch_v2.solve.design_report import DesignReport
    base2 = assemble(pm, cs, lw, DesignReport(), fixed=levels)
    air = airside_stage_vertices(pm, lw)
    mixed = 0
    for terms, _hi, _row in base2.one:
        vs = {v for v, _c in terms}
        if vs & air and not vs <= air:
            mixed += 1
            assert all(int(base2.red.col[v]) < 0 for v in vs & air)
    assert mixed, "the fixture couples airside to what conforms"


# ── the report ───────────────────────────────────────────────────────────

def test_the_report_names_both_stages(arms):
    """The staged clause is the report's own: stage 1's problem, its hard
    set, the substitution and both clocks."""
    _zs, rep_s, _z1, rep_1 = arms
    assert rep_s.staged and not rep_1.staged
    assert "staged (20b)" in rep_s.line()
    assert "staged (20b)" not in rep_1.line()
    s1 = rep_s.stages["stage1"]
    assert s1["unknowns"] > 0 and s1["rows"] > 0
    assert rep_s.stage1_fixed > 0
    assert rep_s.stage1_unlevelled == 0          # §20b (4): the level belt
    assert rep_s.stage_dropped_rows > 0
    assert rep_s.stage1_wall_s > 0.0 and rep_s.stage2_wall_s > 0.0
    # the HARD SET IS THE COMBINATION (the census table)
    assert rep_s.hard_rows >= s1["hard_rows"]
    assert rep_s.hard_rows == s1["hard_rows"] + rep_s.stages["stage2"]["hard_rows"]


def test_stage_two_is_smaller_than_the_single_solve(arms):
    """Substitution removes columns: stage 2 is SMALLER than the one
    problem the single solve factorises, which is why two solves are not
    two solves' worth of work."""
    _zs, rep_s, _z1, rep_1 = arms
    assert rep_s.unknowns < rep_1.unknowns


# ── what the staged arm CHANGES, held with its number ────────────────────

def test_a_pad_welded_to_two_pavements_takes_the_airsides_own_drop(law):
    """§20b's consequence for a WELDED pad, measured on ``test_v2padlevel``'s
    own fixture (an apron and a taxiway 1.8 m apart over the 60 m the pad
    spans, i.e. 3 %), and the reason it is reported rather than decided:

    * with the single solve the pad holds its 1 % ceiling (0.0079) because
      the two pavements YIELD toward it;
    * staged, ten of the pad's fourteen vertices are vertices of an airside
      face, so stage 1 fixes them and the pad's plane is the AIRSIDE'S OWN
      drop, 3 % — the weld is exact and the pad's own ceiling is unreachable.

    Nothing holds that ceiling because 14al withdrew the two-sided ceiling
    row over a pair of two airside-shared vertices (``constraints/pads.py``,
    `pad_skirt_m = 0`) — a withdrawal whose whole purpose was to stop such a
    row PULLING the airside, which under §20b it cannot do.  Reversing it is
    the spec author's call, not this lane's; the twin holds both numbers so
    the ruling has something to rule on.
    """
    from tests.auto_patch_v2.test_v2padlevel import (_two_pavement_cells,
                                                     _airport as _pad_airport,
                                                     _pad_plane, _verts)
    from auto_patch_v2.constraints import generate as _generate
    cells, dem = _two_pavement_cells(1.8)
    tilts = {}
    for staged in (False, True):
        lw = _law_arm(law, staged_solve=staged)
        ap = _pad_airport(lw, dem)
        pm, _st = build(ap, Classification(tuple(cells), (), {}, ()), lw)
        cs, _c, _w = _generate(pm, lw, ap)
        sol, _rep = solve_design(pm, cs, lw)
        tilts[staged] = _pad_plane(pm, np.asarray(sol.z, float))[2]
    assert tilts[False] <= 0.012, tilts          # the 1 % ceiling holds
    assert 0.029 <= tilts[True] <= 0.031, tilts  # the airside's own 3 %
