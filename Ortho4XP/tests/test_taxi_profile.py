"""Twin of ``tools/taxi_profile.py``: one straight centreline, one steep edge."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import taxi_profile as tp  # noqa: E402

LAT0, LON0 = 30.0, 31.0


def _ll(x: float) -> tuple[float, float]:
    return LAT0, LON0 + x / (111195.08 * math.cos(math.radians(LAT0)))


def _graded(zs: list[float], step: float = 50.0) -> dict:
    verts = [[i, *_ll(i * step), z] for i, z in enumerate(zs)]
    return {"vertices": verts, "breaklines": [
        {"id": 0, "kind": "taxi_centerline", "ref": "taxi1", "vertices": list(range(len(zs)))},
        {"id": 1, "kind": "runway_profile", "ref": "09/27", "vertices": [0, 1]}]}


def test_a_lawful_centreline_has_no_reading_over_its_cap() -> None:
    res = tp.read(_graded([100.0, 100.7, 101.4, 102.1]), {}, 0.015)
    assert len(res["edges"]) == 3                       # the runway ridge is not read
    assert tp.over(res["edges"]) == []
    assert all(tp.over(w) == [] for w in res["windows"].values())


def test_one_steep_edge_is_named_and_the_window_reads_its_run() -> None:
    # 50 m edges: 0.5 m (1 %), 2.0 m (4 %), 0.5 m (1 %)
    res = tp.read(_graded([100.0, 100.5, 102.5, 103.0]), {}, 0.015, windows=(100.0,))
    bad = tp.over(res["edges"])
    assert len(bad) == 1 and abs(bad[0][0] - 0.04) < 1e-3 and bad[0][2] == "taxi1"
    w = tp.over(res["windows"][100.0])
    assert w and abs(w[0][0] - 0.025) < 1e-3             # 2.5 m over the 100 m around it


def test_the_stretch_cap_governs_by_ref() -> None:
    axes = {"stretches": [[[], 0.03, "B", "taxi1"]]}
    res = tp.read(_graded([100.0, 100.5, 102.0]), tp.stretch_caps(axes), 0.015)
    assert tp.over(res["edges"]) == []                  # 3 % under a code-B 3 % cap
