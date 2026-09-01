"""A runway ring vertex emits ITS OWN runway's law line, always.

Owner ruling RULINGS 2026-09-01l ("HECA RUNWAYS ARE A REGRESSION … nothing
is allowed to pull a runway past its caps"), lane H7.

THE DEFECT these twins pin (HECA 05C/23C, measured 2026-09-01 over five
instrumented builds).  The runway's persisted longitudinal profile ends the
build LAWFUL — zero segments over the 1.25 % ICAO code-4 cap — and 265 of
its 267 ring vertices emit that profile to within 5 mm.  TWO do not: at
30.11693,31.42056 and 30.11357,31.41731, the only two ring vertices whose
node is shared with BOTH a junction and an apron, the emitted value is
110.46 / 106.55 against a law line of 109.69 / 106.07.  Those two vertices
are the airport's whole runway longitudinal red (2.40 / 2.12 / 2.33 %).

Measured by canonical key inside single passes: the solve's seeding hands
both nodes over HARD at the pre-flex law value; the runway flex lowers the
profile ~4.6 m and the nodes LEAVE the flex hook on the flexed law line,
still ``base_hard``; by the solve's writeback they read 0.77 / 0.48 m
high.  ``final_grade_projection`` already preserves the runway profile
around ITS writeback; the SOLVE's writeback had no preserve, and the
projection's then faithfully restored what this one stamped.

ATTRIBUTED by ``git bisect --first-parent`` over the 1,112 first-parent
commits since the engine landed (10 steps, HECA runway-profile probe as the
predicate; good 38b3eaf5 2026-07-20, bad 4715e3e9): first bad commit
``7786ff0e`` "Merge lane/c4law: cycle-4 targets 2+3 (flex budget
eliminated, ride never enters an anchor)", Aug 5 18:28 — the SAME commit
lane H5 attributed for SPLP's runway rows.

Synthetic fixtures only: no X-Plane install, no CIFP, no DEM, no write.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from auto_patch.elevation_per_surface import solver_primitives as SP


class _Shape:
    def __init__(self, ref="05C/23C"):
        self.ref = ref
        self.role = "runway"


class _Registry:
    tol_m = 0.5

    def find_nearest(self, x, y, tol):
        return (x, y)


class _Layout:
    """A 1000 m runway rising 0 -> 10 m, i.e. a uniform 1 % law line."""

    def __init__(self, crown=None):
        self.canonical_points = _Registry()
        self._crown_drop_key = dict(crown or {})
        self._runway_redistributed_profiles = {
            "05C/23C": {
                # ``axis_d`` is the FULL axis vector and ``axis_len2`` its
                # squared length — the projection ``(v·d)/|d|²`` is then
                # the station FRACTION, exactly as the profile stores it.
                "axis_a": (0.0, 0.0),
                "axis_d": (1000.0, 0.0),
                "axis_len2": 1000.0 ** 2,
                "fractions": [0.0, 1.0],
                "elevs": [100.0, 110.0],
                "crown_drop_m": 0.3,
            }
        }


_RING = [(0.0, 0.0), (250.0, 0.0), (500.0, 0.0), (750.0, 0.0)]
_LAW = [100.0, 102.5, 105.0, 107.5]          # the profile at those stations


def test_a_vertex_the_solve_moved_is_restamped_onto_the_law_line():
    """The measured shape of the defect: one ring vertex 0.77 m proud of
    the runway's own law line comes back onto it."""
    layout = _Layout()
    solved = list(_LAW)
    solved[2] = _LAW[2] + 0.77
    findings: list = []
    out = SP._runway_law_line_corners(
        layout, _Shape(), _RING, solved, findings)
    assert out[2] == pytest.approx(_LAW[2])
    assert out[0] == _LAW[0] and out[1] == _LAW[1] and out[3] == _LAW[3]
    assert len(findings) == 1
    ref, x, y, delta, t = findings[0]
    assert ref == "05C/23C" and (x, y) == (500.0, 0.0)
    assert delta == pytest.approx(-0.77, abs=1e-4)
    assert t == pytest.approx(0.5, abs=1e-6)


def test_a_ring_already_on_its_law_line_is_untouched():
    """The preserve may not move a surface it was not written for: with
    every vertex on the law line the corner list is returned AS IS (the
    same object), so the emit is byte-identical."""
    layout = _Layout()
    solved = list(_LAW)
    findings: list = []
    out = SP._runway_law_line_corners(
        layout, _Shape(), _RING, solved, findings)
    assert out is solved
    assert findings == []


def test_the_emit_crown_drop_is_subtracted():
    """The writeback stamps EMITTED values, and the profile is UNCROWNED —
    so the preserve is ``law - crown``.  Restoring a pre-writeback
    snapshot instead would emit the runway one crown drop high (measured:
    206 of 208 moved HECA vertices moved by exactly the crown drop)."""
    crown = {pt: 0.3 for pt in _RING}
    layout = _Layout(crown=crown)
    solved = [v - 0.3 for v in _LAW]
    solved[2] += 0.77
    out = SP._runway_law_line_corners(layout, _Shape(), _RING, solved, [])
    assert out[2] == pytest.approx(_LAW[2] - 0.3)
    assert out[0] == pytest.approx(_LAW[0] - 0.3)


def test_a_ref_with_no_persisted_profile_is_inert():
    """No profile, no law line — the preserve has nothing to say and must
    not invent one."""
    layout = _Layout()
    solved = [0.0, 0.0, 0.0, 0.0]
    findings: list = []
    out = SP._runway_law_line_corners(
        layout, _Shape(ref="09/27"), _RING, solved, findings)
    assert out is solved and findings == []


def test_a_sub_materiality_delta_is_left_alone():
    """Under the convergence floor the difference is solver noise, not a
    pull — and rewriting it would churn the emit for nothing."""
    layout = _Layout()
    solved = list(_LAW)
    solved[1] += 0.5 * SP.RUNWAY_PRESERVE_MATERIALITY_M
    findings: list = []
    out = SP._runway_law_line_corners(
        layout, _Shape(), _RING, solved, findings)
    assert out is solved and findings == []


def test_the_restamp_is_the_law_line_even_for_a_large_move():
    """A runway is never met half way: whatever the solve did, the vertex
    emits the profile (the ruling is absolute, not a tolerance)."""
    layout = _Layout()
    for offset in (0.02, 0.77, 5.0, -4.6):
        solved = list(_LAW)
        solved[1] = _LAW[1] + offset
        out = SP._runway_law_line_corners(
            layout, _Shape(), _RING, solved, [])
        assert out[1] == pytest.approx(_LAW[1])


def test_the_kill_switch_restores_the_pre_fix_stamp():
    """``O4_RUNWAY_WRITEBACK_PRESERVE=0`` is the A/B arm."""
    layout = _Layout()
    solved = list(_LAW)
    solved[2] += 0.77
    prev = SP.RUNWAY_WRITEBACK_PRESERVE
    try:
        SP.RUNWAY_WRITEBACK_PRESERVE = False
        out = SP._runway_law_line_corners(
            layout, _Shape(), _RING, solved, [])
        assert out is solved
    finally:
        SP.RUNWAY_WRITEBACK_PRESERVE = prev


def test_the_writeback_runway_branch_routes_through_the_preserve():
    """A twin on the helper alone would pass with the call site deleted."""
    import inspect
    src = inspect.getsource(SP._writeback)
    assert "_runway_law_line_corners" in src, (
        "the ROLE_RUNWAY writeback branch must route through the preserve")
    assert "_record_runway_preserve_findings" in src, (
        "every restamp must be published — a silent one hides the pull "
        "RULINGS 2026-09-01l forbids")


def test_the_restamps_are_published_on_the_layout():
    """The report is the instrument: a restamp nobody can see is a
    correction that looks like there was never a defect."""
    class _L:
        pass

    layout = _L()
    SP._record_runway_preserve_findings(
        layout, [("05C/23C", 1.0, 2.0, -0.77, 0.5)])
    rows = getattr(layout, "_runway_profile_preserve_restamps", None)
    assert rows and rows[0][0] == "05C/23C" and rows[0][3] == -0.77
    # …and appends rather than replaces (the writeback runs twice a build)
    SP._record_runway_preserve_findings(
        layout, [("05C/23C", 3.0, 4.0, 0.48, 0.25)])
    assert len(layout._runway_profile_preserve_restamps) == 2
