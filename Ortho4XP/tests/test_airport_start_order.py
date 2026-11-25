"""The tile's airport builds start longest first (2026-11-24, lane
lvector): only the start order moves, never the task list."""
from __future__ import annotations

from o4_engine import airport_time_model as M
from o4_engine import airport_time_model as S


def _tasks(*icaos):
    return [{"icao": icao, "n": i} for i, icao in enumerate(icaos)]


def test_the_longest_predicted_build_starts_first(monkeypatch):
    seconds = {"KAAA": 60.0, "KBBB": 470.0, "KCCC": 120.0, "KDDD": 120.0}
    monkeypatch.setattr(M, "predict_each", lambda icaos: {i: seconds[i] for i in icaos})
    tasks = _tasks("KAAA", "KBBB", "KCCC", "KDDD")
    order = S.longest_first(tasks)
    assert [t["icao"] for t in order] == ["KBBB", "KCCC", "KDDD", "KAAA"]
    assert all(a is b for a, b in zip(sorted(order, key=lambda t: t["n"]), tasks, strict=True))
    assert [t["icao"] for t in tasks] == ["KAAA", "KBBB", "KCCC", "KDDD"]


def test_no_prediction_keeps_the_task_order(monkeypatch):
    def broken(_icaos):
        raise OSError("no store")
    monkeypatch.setattr(M, "predict_each", broken)
    tasks = _tasks("KAAA", "KBBB")
    assert S.longest_first(tasks) == tasks
