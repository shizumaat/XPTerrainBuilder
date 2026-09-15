"""Twins for §20a THE HARD SET SETTLES OR NAMES WHY (lane ``v2settle``;
the campaign's first-ranked standing debt, owner RULINGS 13y (B) / 13ab /
14as — "the airside solve does not settle").

Three laws, each measured at HECA before it was written:

1. **A HARD ROW MUST CARRY A COLUMN.**  ``design.assemble``'s own comment
   has always said "a row whose every foot is fixed carries no column and
   constrains nothing — it stays a reported target", and the code tested
   one WAY of being fixed (``red.dem_fixed``).  A foot held by a ``Pin`` is
   fixed too, and its row entered the hard set as a CONSTANT nothing can
   move.  MEASURED (HECA, §20b stage 1, capture off main b1b7704c): 142 of
   161,780 stage-1 hard rows carried no column, 9 of them violated —
   INCLUDING the worst row of the whole airside set (0.1794 m).  Cost
   beyond the report: phase C pins ``best_worst`` at that constant, so
   ``worst < best_worst`` never fires and the polish returns ROUND 1's
   iterate.  Stage 1 after the fix: 33 violated / 0.1794 m -> 6 / 0.0445 m,
   and the SHIPPED (single-solve) patch is byte-identical.

2. **A ROW AT THE BAR IS HELD, NOT VIOLATED.**  ``project_runway`` is a QP
   that solves its rows TO ``hard_tol_m``, so it lands them AT the bar; a
   strict ``> tol`` on a residual 2e-14 .. 6e-13 m above its own target
   reported 6 HELD runway rows as violations.  ONE derivation
   (``design_report.hard_exceeds``) for the report, the solve and the
   ``--why-hard`` instrument.

3. **AN INFEASIBLE SET IS NAMED, NOT TRADED.**  ``HARD SET NOT SETTLED``
   named one row by a 70-character slice of a ruling, which cannot say
   whether what is left is a residual the solve owes or rows NO SURFACE
   satisfies.  ``read_hard_failure`` names every survivor with its vertices
   and canonical lat/lon and takes a FEASIBILITY CERTIFICATE over them
   (``min Σ s`` with everything outside the component held): zero shortfall
   proves the law is satisfiable there, positive shortfall PROVES it is
   not.  At HECA stage 1 the certificate reads FEASIBLE (the residual is
   the solve's); at KCLT 143 of 406 survivors are a proven infeasible set
   (26.3994 m), every one of them ``structures.building_pad airside skirt``.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.model.constraints import Band, ConstraintSet, Diff, Pin, Source
from auto_patch_v2.solve.design import _carries_a_column
from auto_patch_v2.solve.design_report import (HARD_READ_EPS, DesignReport,
                                               _infeasible_set, hard_exceeds)


class _Red:
    """The reduction's two fields the row tests read: a column per vertex
    (-1 = fixed) and the value a fixed vertex holds."""

    def __init__(self, col, value):
        self.col = np.asarray(col, np.int64)
        self.value = np.asarray(value, float)


# ── 1. a hard row must carry a column ────────────────────────────────────

def test_a_row_on_a_pinned_foot_carries_no_column():
    """The 9-row class at HECA: a ``road_ramp`` ceiling whose single foot is
    a road-profile ``Pin``.  Fixed, not DEM-fixed — which is why the old
    ``dem_fixed`` test let it into the hard set."""
    red = _Red([-1, 0], [70.4, 0.0])
    assert not _carries_a_column(red, ((0, 1.0),))
    assert _carries_a_column(red, ((1, 1.0),))
    assert _carries_a_column(red, ((0, 1.0), (1, -1.0)))


def test_two_feet_of_one_rigid_group_cancel_to_a_constant():
    """A ±1 row over two vertices of the SAME ``Flat`` group shares one
    column and reduces to nothing: the same constant by another route, and
    the raw-terms test would have missed it."""
    red = _Red([3, 3], [0.0, 0.0])          # both on column 3
    assert not _carries_a_column(red, ((0, 1.0), (1, -1.0)))
    assert _carries_a_column(red, ((0, 1.0), (1, -0.5)))


def test_a_constant_row_never_reaches_the_hard_set(real_map):
    """End to end through ``assemble`` on a REAL map: a hard-ruling ceiling
    on a PINNED vertex is violated by 0.5 m and is NOT a hard row — it stays
    a reported target, exactly as the module's own comment states.  This is
    the HECA class (9 violated rows of 142 column-less ones), in one row."""
    from auto_patch_v2.solve.design import assemble
    law, pm, cs, pinned = real_map
    base = assemble(pm, cs, law, DesignReport())
    for k in base.hard:
        assert _carries_a_column(base.red, base.one[k][0]), k
    # and the row IS still there as a reported target
    assert any(terms == ((pinned, 1.0),) for terms, _hi, _r in base.one)


# ── 2. a row at the bar is held ──────────────────────────────────────────

@pytest.mark.parametrize("viol,held", [
    (0.02, True),                       # exactly the bar
    (0.020000000000583, True),          # HECA's worst runway row, measured
    (0.02 + HARD_READ_EPS / 2, True),
    (0.02 + HARD_READ_EPS * 10, False),
    (0.0445, False),                    # HECA stage 1's real survivor
])
def test_the_settle_test_carries_the_solvers_own_floor(viol, held):
    assert bool(hard_exceeds(viol, 0.02)) is (not held)


def test_the_settle_test_is_one_derivation_for_the_report():
    """``read_hard_set`` must not re-derive the comparison: six HELD runway
    rows were counted as violations because two readers rounded a solver
    residual opposite ways (RULINGS 2026-09-13ac called it cosmetic and left
    it)."""
    rep = DesignReport()
    viol = np.array([0.020000000000583, 0.0, 0.019])
    rep.read_hard_set(viol, 0.02, lambda k: "r")
    assert rep.hard_settled and rep.hard_active == 0


# ── 3. an infeasible set is named, not traded ────────────────────────────

def _chain(bounds, ends):
    """A chain ``v0 .. vN`` of ceilings ``z[i+1] - z[i] <= bound`` with BOTH
    ENDS FIXED ``ends`` apart — the shape of HECA's surviving rows.  Σbounds
    < the drop the ends demand is infeasible; Σbounds >= it is not."""
    n = len(bounds) + 1
    col = [-1] + list(range(n - 2)) + [-1]
    red = _Red(col, [ends[0]] + [0.0] * (n - 2) + [ends[1]])
    src = Source("pavement_ceiling", "rulesets.common.pavement_max_grade", ())
    one = [(((i, 1.0), (i + 1, -1.0)), float(b), Diff(i, i + 1, b, 1.0, src))
           for i, b in enumerate(bounds)]
    hard_i = np.arange(len(one), dtype=np.int64)
    z = np.linspace(ends[0], ends[1], n)
    return hard_i, one, red, z


def test_an_infeasible_chain_is_proved_infeasible():
    """Ends 1.00 m apart, three ceilings allowing 0.20 m each: no surface
    holds all three, and the certificate says so with the shortfall."""
    hard_i, one, red, z = _chain([0.2, 0.2, 0.2], (0.0, -1.0))
    cert = _infeasible_set(hard_i, np.array([0, 1, 2]), one, red, z)
    assert cert["infeasible"] and not cert["feasible"]
    assert cert["total_slack_m"] > 0.3
    assert cert["rows_in_set"] >= 1


def test_a_satisfiable_chain_is_proved_satisfiable():
    """The same chain with the ends 0.30 m apart: the law CAN hold, so a
    residual there is the solve's and must not be reported as the law's."""
    hard_i, one, red, z = _chain([0.2, 0.2, 0.2], (0.0, -0.3))
    cert = _infeasible_set(hard_i, np.array([0, 1, 2]), one, red, z)
    assert cert["feasible"] and not cert["infeasible"]
    assert cert["total_slack_m"] == pytest.approx(0.0, abs=1e-6)


def test_the_failure_line_names_the_rows_and_their_coordinates():
    """§20a's named failure for the hard set: which rows, where, and the
    certificate's verdict — never a truncated ruling alone."""
    hard_i, one, red, z = _chain([0.2, 0.2, 0.2], (0.0, -1.0))
    viol = np.array([0.1333, 0.1333, 0.1333])
    rep = DesignReport()
    rep.read_hard_set(viol, 0.02, lambda k: "r")
    rep.read_hard_failure(hard_i, viol, one, _planar(4), red, 0.02, z)
    line = rep.hard_failure_line()
    assert "HARD SET NOT SETTLED" in line
    assert "INFEASIBLE SET" in line and "CRITICAL" in line
    assert "0.1333 m on row" in line
    assert rep.hard_failure["rows_violated"] == 3
    assert rep.hard_failure["rows_named"][0]["vertices"][0]["lat"] is not None
    assert rep.as_dict()["hard_failure"]["certificate"]["infeasible"]


def test_a_settled_hard_set_names_nothing():
    rep = DesignReport()
    hard_i, one, red, z = _chain([0.2, 0.2, 0.2], (0.0, -0.3))
    rep.read_hard_failure(hard_i, np.zeros(3), one, _planar(4), red, 0.02, z)
    assert rep.hard_failure == {} and rep.hard_failure_line() == ""


# ── fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def real_map():
    """One runway over flat terrain, one vertex PINNED, and a hard-ruling
    ceiling on that pinned vertex 0.5 m under its pin."""
    import dataclasses as _dc

    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                             SceneryPack)
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.build import build

    class _Dem:
        provenance = {"synthetic": "settle"}

        def z(self, x, y):
            return 700.0

        def bounds(self):
            return (-5000.0, -5000.0, 5000.0, 5000.0)

    law = Law.for_airport("ZZZZ")
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"),
            RunwayEnd("27", (800.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"))
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0,
                      (Runway("09/27", 45.0, 1, ends, 3, "D"),), (), (), {},
                      (), (), (), (), (), (), (), SceneryPack(
                          "fixture", "apt.dat", "0", (), ()), _Dem(),
                      law.ruleset_key)
    cells = [Cell(0, "runway", "09/27",
                  ((-800.0, -22.5), (800.0, -22.5), (800.0, 22.5),
                   (-800.0, 22.5)), (), 3, "D", "airside", "runway", {})]
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pinned = next(iter(pm.vertices))
    head = law.tables.emit.design.hard_rulings[0]
    src = Source("road_ramp", head, ())
    cs = ConstraintSet(pins=(Pin(pinned, 700.9, src),),
                       bands=(Band(pinned, None, 700.4, src),),
                       diffs=(), flats=(), offsets=(), linears=())
    return law, pm, cs, pinned



class _V:
    def __init__(self, i):
        self.key = (60.0 + i * 1e-5, -135.0 - i * 1e-5)
        self.xy = (float(i), 0.0)
        self.dem_z = 700.0
        self.incident_faces = ()


class _P:
    def __init__(self, n):
        self.vertices = [_V(i) for i in range(n)]
        self.faces = {}
        self.edges = {}

    def ring_vertices(self, ring):
        return ()


def _planar(n):
    return _P(n)


def _flat_map(n):
    return _P(n)
