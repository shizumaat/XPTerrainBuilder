"""ISSUE #1899 TWIN: ``v2_solve_replay --rederive-from PKL`` re-runs
``low_hold_retarget`` and ``taxi_route_yield.derive`` alone off a
``--solved-out`` pickle's stage-1 levels, and refuses a pickle that
carries none.  Offline: the two derivations are stubbed, no corpus."""
from __future__ import annotations

import dataclasses as _dc
import pickle
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import replay_arms as A  # noqa: E402
import replay_rederive as R  # noqa: E402


@_dc.dataclass(frozen=True)
class _PM:
    taxi_trend_z: dict
    registries: object = None


def test_a_pickle_without_stage1_levels_is_refused(tmp_path):
    p = tmp_path / "old.pkl"
    p.write_bytes(pickle.dumps({"icao": "XXXX", "pm": _PM({})}))
    with pytest.raises(SystemExit, match="no stage-1 levels"):
        R.rederive(p, {}, None)


def test_summarise_reads_the_held_targets_and_both_derivations(monkeypatch):
    seen = {}

    def low_hold(pm_x, law, levels, rep):
        seen["tz"] = dict(pm_x.taxi_trend_z)
        rep.update(low_hold_spans=1, low_hold_worst_m=0.5)
        return {1: 9.5, 2: 20.0}

    route = types.SimpleNamespace(high_ll=(0, 0), low_ll=(1, 1), length_m=10.0,
                                  needed=0.02, cap=0.02, over_ceiling=True,
                                  edges=frozenset({1}))
    monkeypatch.setitem(sys.modules, "auto_patch_v2.constraints.taxi_trend",
                        types.SimpleNamespace(low_hold_retarget=low_hold))
    monkeypatch.setitem(sys.modules, "auto_patch_v2.constraints.taxi_route_yield",
                        types.SimpleNamespace(derive=lambda pm, law, ap: (route,)))
    res = R.summarise(_PM({1: 0.0}), None, None, {1: 9.0}, {1: 10.0, 2: 20.0})
    assert seen["tz"] == {1: 10.0, 2: 20.0}      # the held targets, not pm's
    assert res["moved"] == {1: -0.5} and res["low_hold_targets_moved"] == 1
    assert res["routes"][0]["over_ceiling"] is True


def test_the_mode_is_its_own_arm_context():
    a = types.SimpleNamespace(stage1_diff=None, rederive_from="x.pkl")
    assert A.context_of(a) == "rederive"
    assert A.takes_effect("--design-weight", "rederive")
    assert not A.takes_effect("--drop-generator", "rederive")
