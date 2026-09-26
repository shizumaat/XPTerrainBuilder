"""Twins for lane ``surfacesettle`` (issues #21 GEML / #22 TFFJ): THE HARD
SET IS READ IN THE ROW'S OWN METRES.

The design solve scales every hard row by ``2 / Σ|c|`` over its REDUCED
terms — the free columns only — and the design report's post-projection
re-read and its infeasibility certificate read the violation off that
same scaled matrix.  A row with one PINNED side (a §37 (9) coverage-edge
join, a stage-1 airside level substituted into stage 2) reduces to a
single free term and read DOUBLE; a row whose free term is a small
interpolation weight read up to 20x.  MEASURED on the lane's captures
(base main 4cd4025f): GEML reported 20 rows / worst 3.5369 m where the
surface misses 17 / 1.5744 m (the worst named row, 29184, misses by
0.1719 m: its only free coefficient is 0.0972); TFFJ reported 263 /
13.6115 m against 256 / 6.8058 m; CYXY 15 / 0.7278 against 14 / 0.3639.
``v2_solve_replay --why-hard`` has always read the full term sum; the
report now reads through the same derivation
(``design_report.row_metre_scale``).  The SOLVE is unchanged: the three
captures' solved ``z`` are array-identical before and after.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.solve.design_report import (_infeasible_set, hard_metres,
                                               row_metre_scale)


class _Red:
    def __init__(self, col, value):
        self.col = np.asarray(col, np.int64)
        self.value = np.asarray(value, float)


def test_the_metre_scale_is_the_rows_own_term_sum():
    """1 for a Δz pair and for a point-vs-interpolated-point row, whatever
    is pinned: the scale is a property of the LAW ROW, not of which of its
    vertices this stage happens to hold fixed."""
    assert row_metre_scale(((0, 1.0), (1, -1.0))) == pytest.approx(1.0)
    # GEML row 29184: v760 -1, v745 +0.902798 (pinned), v741 +0.097202
    assert row_metre_scale(((760, -1.0), (745, 0.902798), (741, 0.097202))) \
        == pytest.approx(1.0)
    one = [(((0, 1.0), (1, -1.0)), 0.0, None),
           (((2, -1.0), (3, 0.902798), (4, 0.097202)), 0.0, None)]
    out = hard_metres(one, np.array([0, 1]), np.array([0.5, 0.1719]))
    assert out == pytest.approx([0.5, 0.1719])


def test_the_certificate_reads_the_shortfall_in_metres():
    """A chain of three 0.20 m ceilings whose two ENDS are pinned 1.00 m
    apart: the smallest total shortfall any surface can leave is exactly
    0.40 m.  Scaled by the component's own columns, the two end rows (one
    free term each) counted their slack twice and the certificate said
    0.80 m."""
    n = 4
    col = [-1, 0, 1, -1]
    red = _Red(col, [0.0, 0.0, 0.0, -1.0])
    one = [(((i, 1.0), (i + 1, -1.0)), 0.2, None) for i in range(3)]
    hard_i = np.arange(3, dtype=np.int64)
    z = np.linspace(0.0, -1.0, n)
    cert = _infeasible_set(hard_i, np.array([0, 1, 2]), one, red, z)
    assert cert["infeasible"]
    assert cert["total_slack_m"] == pytest.approx(0.4, abs=1e-6)


@pytest.fixture(scope="module")
def pinned_pair_map():
    """One runway over flat terrain; two of its vertices PINNED 3 m apart
    and a third, free, between them, tied to each by a hard ceiling that
    allows 0.5 m: no surface holds both, and each row has ONE free term."""
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.airport import (Airport, Runway, RunwayEnd,
                                             SceneryPack)
    from auto_patch_v2.model.frame import Frame
    from auto_patch_v2.planar.build import build

    class _Dem:
        provenance = {"synthetic": "surfacesettle"}

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
    vs = sorted(pm.vertices)[:3]
    a, b, c = vs
    head = law.tables.emit.design.hard_rulings[0]
    src = Source("pavement_ceiling", head, ())
    d_ab = float(np.hypot(*np.subtract(pm.vertices[a].xy, pm.vertices[b].xy)))
    d_bc = float(np.hypot(*np.subtract(pm.vertices[b].xy, pm.vertices[c].xy)))
    cs = ConstraintSet(pins=(Pin(a, 703.0, src), Pin(c, 700.0, src)),
                       diffs=(Diff(a, b, 0.5 / d_ab, d_ab, src),
                              Diff(b, c, 0.5 / d_bc, d_bc, src)),
                       flats=(), offsets=(), linears=(), bands=())
    return law, pm, cs


def test_the_report_and_the_surface_read_one_number(pinned_pair_map):
    """End to end through ONE design stage (``_solve_stage``, what both §20b
    stages and the single solve run): the report's worst hard row is the
    violation the SHIPPED surface carries in that row's own metres — the
    number ``--why-hard`` prints — never the reduced reading's double."""
    from auto_patch_v2.solve import Options
    from auto_patch_v2.solve.design import _solve_stage as solve_design
    from auto_patch_v2.solve.design import assemble
    from auto_patch_v2.solve.design_report import DesignReport, hard_exceeds
    law, pm, cs = pinned_pair_map
    sol, rep = solve_design(pm, cs, law, Options())
    z = np.asarray(sol.z, float)
    base = assemble(pm, cs, law, DesignReport())
    tol = float(law.tables.emit.design.hard_tol_m)
    true = []
    for k in base.hard:
        terms, hi, _row = base.one[k]
        v = (sum(c * float(z[i]) for i, c in terms) - hi) * row_metre_scale(terms)
        if hard_exceeds(v, tol):
            true.append(v)
    assert true, "the fixture must leave the pinned pair unsettled"
    assert not rep.hard_settled
    f = rep.hard_failure
    assert f["rows_violated"] == len(true)
    assert f["worst_m"] == pytest.approx(max(true), abs=1e-6)
    # the pair cannot hold: 3.0 m between the pins, 1.0 m allowed
    assert f["certificate"]["infeasible"]
    assert f["certificate"]["total_slack_m"] == pytest.approx(2.0, abs=1e-3)
