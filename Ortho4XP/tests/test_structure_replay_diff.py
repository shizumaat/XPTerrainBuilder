"""Twin for ``tools/structure_replay_diff.py`` (the base-vs-branch bar of
every structure lane).  The tool's whole job is to FAIL on the three
things a lane must not do, so each is asserted on a synthetic pair."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import structure_replay_diff as srd            # noqa: E402


def _arm(root: Path, name: str, rec: dict) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "structures.json").write_text(json.dumps(rec))


BASE = {"tunnels": [{"id": "t0", "ways": [-1], "replaced_ways": [-2]}],
        "basins": [{"id": "b0", "objects": ["a.obj"]}],
        "basin_refused": ["Trench_01.obj x1: a skirt, not a pit"]}


def test_an_untouched_arm_is_identical(tmp_path):
    _arm(tmp_path, "OTHH", BASE)
    _arm(tmp_path / "br", "OTHH", BASE)
    v = srd.compare(BASE, BASE, srd.DEFAULT_KEYS, ["§45"])
    assert v["identical"] and v["keys"]["tunnels"]["identical"]


def test_a_changed_replaced_ways_is_not_identical():
    """The count is the same and the record is NOT — which is exactly the
    class the count-only reading of this bar would have passed."""
    br = json.loads(json.dumps(BASE))
    br["tunnels"][0]["replaced_ways"] = [-2, -3]
    v = srd.compare(BASE, br, srd.DEFAULT_KEYS, ["§45"])
    assert not v["identical"]
    assert v["keys"]["tunnels"]["base"] == v["keys"]["tunnels"]["branch"] == 1


def test_a_foreign_refusal_fails_and_the_lanes_own_does_not():
    own = json.loads(json.dumps(BASE))
    own["basin_refused"].append("basin:9 lies inside a §45 channel corridor")
    assert srd.compare(BASE, own, srd.DEFAULT_KEYS, ["§45"])["identical"]

    foreign = json.loads(json.dumps(BASE))
    foreign["basin_refused"].append("basin:9 overlaps a tunnel structure")
    v = srd.compare(BASE, foreign, srd.DEFAULT_KEYS, ["§45"])
    assert not v["identical"] and v["refusals"]["basin_refused"]["foreign"]


def test_a_refusal_that_disappeared_fails():
    gone = json.loads(json.dumps(BASE))
    gone["basin_refused"] = []
    v = srd.compare(BASE, gone, srd.DEFAULT_KEYS, ["§45"])
    assert not v["identical"] and v["refusals"]["basin_refused"]["gone"] == 1


def test_the_cli_reports_a_missing_arm(tmp_path, capsys):
    _arm(tmp_path / "base", "OTHH", BASE)
    rc = srd.main(["--base", str(tmp_path / "base"), "--branch",
                   str(tmp_path / "br"), "--icao", "OTHH"])
    assert rc == 1 and "MISSING" in capsys.readouterr().out
