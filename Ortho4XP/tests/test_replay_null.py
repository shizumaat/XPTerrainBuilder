"""``tools/v2_solve_replay.py --null-change`` (spec §61 (6); owner RULINGS
2026-10-09e) — the standing stability check, at fixture scale: the §8.6
stub fixture solved twice, the second time under ceilings its own answer
satisfies, moves NOTHING; and the one line the sweep greps keeps its shape.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import replay_null as RN  # noqa: E402

from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.solve import solve_design  # noqa: E402
from tests.auto_patch_v2 import test_v2valley as V  # noqa: E402

LINE = re.compile(
    r"^NULL-CHANGE (pass\w+ (\d+/\d+/\d+\.\d{3}|-) )+stage2 (\d+/\d+/\d+\.\d{3}|-) "
    r"\(movers > 0\.02 / > 0\.3 / worst m; bar 20 / 0; "
    r"promoted \d+=\d+, lp relaxed \d+=\d+\)(  LP SETS DIFFER \d+/\d+)?(  BAR MISSED)?$")


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def stub_null(law):
    pm, cs = V.stub_problem.__wrapped__(law)
    return RN.null_change(
        lambda bands: solve_design(pm, RN.with_bands(cs, bands), law), pm, law,
        n=12)


def test_the_stub_fixture_moves_nothing_under_a_null_change(stub_null):
    res = stub_null
    assert res["ceilings"] == 12 and res["passes"][0] == res["passes"][1] >= 1
    passes = [v for k, v in res.items() if k.startswith("pass") and k != "passes"]
    assert passes and all(m[:2] == [0, 0] for m in passes), res
    assert res["stage2"][:2] == [0, 0]
    assert res["promoted"][0] == res["promoted"][1]
    assert res["lp_relaxed"][0] == res["lp_relaxed"][1]
    assert res["lp_only"] == [0, 0]
    assert res["met"]


def test_the_line_is_the_one_the_sweep_greps(stub_null):
    line = RN.null_line(stub_null)
    assert LINE.match(line), line
    assert "BAR MISSED" not in line


def test_a_missed_bar_says_so():
    res = {"pass1a": [0, 0, 0.0], "pass1b": [1813, 0, 0.195], "passes": [2, 2],
           "stage2": [1900, 0, 0.2], "promoted": [[625, 813], [625, 815]],
           "lp_relaxed": [[0, 240], [0, 240]], "lp_only": [1, 1], "met": False}
    line = RN.null_line(res)
    assert LINE.match(line), line
    assert line.endswith("LP SETS DIFFER 1/1  BAR MISSED")
    assert "pass1b 1813/0/0.195" in line and "promoted 1438=1440" in line


def test_movers_read_only_the_columns_asked_for():
    import numpy as np
    za, zb = np.zeros(5), np.array([0.0, 0.03, 0.5, 0.01, 0.0])
    assert RN.movers(za, zb) == [2, 1, 0.5]
    assert RN.movers(za, zb, np.array([0, 3, 4])) == [0, 0, 0.01]
    assert RN.movers(za, zb, np.array([], dtype=int)) == [0, 0, 0.0]


def test_the_trace_restores_the_engine_function():
    from auto_patch_v2.solve import flex
    before = flex.yield_stage_one
    with RN.PassTrace():
        assert flex.yield_stage_one is not before
    assert flex.yield_stage_one is before
