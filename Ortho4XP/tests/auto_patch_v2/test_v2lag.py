"""§20a THE LAG IS A CONVERGENCE CONDITION (Fable 2026-09-13; owner RULINGS
2026-09-13ac) — lane ``v2settle``.

The one-way rows (``[design] one_way_rulings``) price the adjacent ground,
the pad frontage and the groundside lot as FOLLOWERS: the leader's foot
leaves the matrix for the right-hand side at its previous outer-round
value, and the outer loop re-reads it.  That is a fixed-point iteration,
and a fixed-point iteration either converges or is reported.

Until 13ac it did neither.  ``one_way_max_rounds`` was 3, chosen because
HECA's leader move fell under the materiality by round 3 — but at LEMD it
reads 0.678 m against a 0.01 m tolerance on EVERY arm, and the loop simply
stopped, with ``LAG NOT SETTLED`` naming nothing.  The augmented-Lagrangian
polish then ran INSIDE a problem still moving under it, and §28's 42
one-way rows in the pad columns wobbled across ``hard_tol_m``.

So the cap's hit becomes a NAMED failure: which rows still move, the worst
row's generator and ruling, its LEADER vertex with the canonical lat/lon,
and that leader's last move.

§20a's OTHER half — a safety ceiling of >= 20 rounds — is REFUTED at LEMD
and NOT landed; ``law/emit.toml`` [design] one_way_max_rounds carries the
measurement, and the first twin below pins it.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.law import load_default
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.model.constraints import Linear, Source
from auto_patch_v2.solve.design_report import DesignReport


@pytest.fixture(scope="module")
def law():
    return load_default()


class _V:
    def __init__(self, lat, lon):
        self.key = (lat, lon)


class _PM:
    def __init__(self, keys):
        self.vertices = {v: _V(*ll) for v, ll in keys.items()}


def _row(gen, ruling):
    """One entry of ``Base.one``: the ``_Side`` tuple ``(terms, bound, row)``
    the assembler builds, not the ``Linear`` it was minted from."""
    return ([(7, 1.0), (9, -1.0)], 0.0,
            Linear(((7, 1.0), (9, -1.0)), None, 0.0, Source(gen, ruling, ())))


# ── the law ─────────────────────────────────────────────────────────────

def test_the_cap_is_the_measured_one_and_the_tolerance_is_the_materiality(law):
    """§20a asked for a SAFETY CEILING of >= 20 rounds.  MEASURED at LEMD
    on a fresh main capture, the arm alone (``--design-weight
    one_way_max_rounds=20``), that ceiling is REFUTED: the leader/follower
    iteration does not contract, and 20 rounds read 25 violated hard rows
    at 0.1225 m in 118.2 s where 3 read 4 rows at 0.0985 m in 62.1 s —
    six times the rows and +90 % of the solve, against a +10 % wall bar.

    So the cap stays the measured HECA value and §20a's other half — the
    NAMED failure below — carries "never a silent stop".  The twin pins
    the refutation so a future raise has to re-measure rather than reason
    from the spec text; ``law/emit.toml`` carries the numbers."""
    d = design_law(law)
    assert d.one_way_max_rounds == 3
    assert d.one_way_tol_m == pytest.approx(0.01)
    assert d.one_way_relax == pytest.approx(0.5)


# ── the named failure ───────────────────────────────────────────────────

def test_the_cap_hit_names_the_rows_the_leader_and_its_move():
    """Never a silent stop: the report carries the population, the worst
    row's law, the LEADER's canonical identity and its last move."""
    rep = DesignReport()
    rep.one_way_rounds = 20
    ow_i = np.array([4, 11, 12], dtype=np.int64)
    move = np.array([0.004, 0.678, 0.031])
    one = [None] * 13
    one[4] = _row("zones", "zones.adjacent_ground")
    one[11] = _row("pads", "structures.building_pad frontage_level")
    one[12] = _row("groundside_frontage", "structures.building_pad groundside_frontage")
    pm = _PM({7: (40.49615941816, -3.59037117965), 9: (40.48527108321, -3.59323243501)})

    f = rep.read_lag_failure(ow_i, move, 0.01, 20, one, {11: (7,)}, pm)

    assert f["rows_moving"] == 2 and f["rows"] == 3
    assert f["worst_row"] == 11
    assert f["worst_move_m"] == pytest.approx(0.678)
    assert f["generator"] == "pads"
    assert f["ruling"].startswith("structures.building_pad frontage_level")
    # v7 is the FOLLOWER of row 11; the leader is what the lag re-reads
    assert [r["v"] for r in f["leaders"]] == [9]
    assert f["leaders"][0]["lat"] == pytest.approx(40.48527108321)
    assert f["cap"] == 20 and f["rounds"] == 20 and f["tol_m"] == 0.01


def test_the_named_failure_reaches_the_line_and_the_sidecar():
    rep = DesignReport()
    rep.one_way_settled = False
    rep.one_way_rounds = 20
    rep.one_way_rows = 3
    one = [None] * 5
    one[4] = _row("pads", "structures.building_pad frontage_level")
    pm = _PM({7: (40.4, -3.5), 9: (40.49615941816, -3.59037117965)})
    rep.read_lag_failure(np.array([4]), np.array([0.678]), 0.01, 20, one, {}, pm)

    line = rep.lag_failure_line()
    assert "LAG NOT SETTLED after 20 of 20 round(s)" in line
    assert "0.6780 m" in line and "structures.building_pad frontage_level" in line
    assert "40.49615941816" in line          # the leader's canonical identity
    assert line in rep.line()
    assert rep.as_dict()["one_way_failure"]["worst_row"] == 4


def test_a_settled_lag_names_nothing():
    """The line is unchanged where the lag converges — §20a adds a failure
    report, not a new heading on every build."""
    rep = DesignReport()
    assert rep.one_way_settled and rep.one_way_failure == {}
    assert rep.lag_failure_line() == ""
    assert "LAG NOT SETTLED" not in rep.line()
    assert rep.as_dict()["one_way_failure"] == {}


def test_an_empty_move_vector_records_nothing_rather_than_raising():
    """A lag with no one-way rows never reaches the reader; if it does, it
    reports nothing rather than indexing an empty argmax."""
    rep = DesignReport()
    assert rep.read_lag_failure(np.zeros(0, dtype=np.int64), np.zeros(0),
                                0.01, 20, [], {}, _PM({})) == {}
