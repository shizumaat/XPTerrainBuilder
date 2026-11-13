"""#2045: the estimate-error calculator (``o4_engine.estimate_error``,
``tools/estimate_error.py``) on a synthetic tile store."""

import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import estimate_error as EE  # noqa: E402


def _rec(at, steps, **features):
    return {"finished_at": at, "features": features, "step_seconds": steps}


STORE = {
    # one stepwise build (four records) then a rebuild a day later
    "+39-105": [_rec(100.0, {"vector": 1600.0}, airports=3,
                     airport_seconds={"KDEN": 1340.0}),
                _rec(220.0, {"mesh": 120.0}),
                _rec(230.0, {"masks": 8.0}),
                _rec(310.0, {"imagery": 80.0}, textures_downloaded=300,
                     download_seconds=58.0),
                _rec(90000.0, {"vector": 1500.0}, airports=3,
                     airport_seconds={"KDEN": 1300.0})],
    "+10+010": [_rec(50.0, {"mesh": 60.0}), _rec(60.0, {"mesh": 30.0})],
}


def test_records_group_into_builds():
    builds = EE._builds(STORE)
    sizes = sorted((b["tile"], len(b["records"])) for b in builds)
    # a repeated step starts a new build; so does a gap of over an hour
    assert sizes == [("+10+010", 1), ("+10+010", 1),
                     ("+39-105", 1), ("+39-105", 4)]


def test_replay_predicts_each_build_from_what_came_before():
    seen = []

    def predict(key, features, same, every, before):
        seen.append((key, len(every), before, features.get(
            "airports_planned")))
        return 100.0

    rows = EE.replay(STORE, predict)
    first = [s for s in seen if s[2] == 100.0]
    assert all(n == 2 for _k, n, _b, _p in first)     # only +10+010 (50, 60 s)
    rebuild = [s for s in seen if s[2] == 90000.0][0]
    assert rebuild[3] == {"KDEN": None}       # the tile's earlier solve list
    big = [r for r in rows
           if r["tile"] == "+39-105" and len(r["steps"]) == 4][0]
    assert big["cold"] and big["airports"] == 3
    assert big["actual"] == pytest.approx(1808.0)
    assert big["predicted"] == pytest.approx(400.0)


def test_the_summary_splits_classes_with_n():
    rows = [{"tile": "a", "cold": False, "airports": 1, "predicted": 200.0,
             "actual": 100.0, "steps": {"vector": (200.0, 100.0)}},
            {"tile": "b", "cold": True, "airports": 0, "predicted": 50.0,
             "actual": 100.0, "steps": {"mesh": (50.0, 100.0)}}]
    summary = EE.summarise(rows)
    assert summary["all"]["n"] == 2
    assert summary["all"]["median_factor"] == pytest.approx(2.0)
    assert summary["cached+airports"]["median_ratio"] == pytest.approx(2.0)
    assert summary["cold+no-airports"]["median_ratio"] == pytest.approx(0.5)
    assert summary["step:vector"]["n"] == 1


def test_the_tool_reads_a_store(tmp_path, capsys):
    store = tmp_path / "store"
    store.mkdir()
    for tile, records in STORE.items():
        (store / (tile + ".json")).write_text(json.dumps(records),
                                              encoding="utf-8", newline="\n")
    path = os.path.join(os.path.dirname(__file__), "..", "tools",
                        "estimate_error.py")
    spec = importlib.util.spec_from_file_location("estimate_error_tool", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.main(["--store", str(store), "--tile", "+39-105"]) == 0
    out = capsys.readouterr().out
    assert "all" in out and "+39-105" in out
