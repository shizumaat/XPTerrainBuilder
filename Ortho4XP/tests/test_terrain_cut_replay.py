"""Twin of ``tools/terrain_cut_replay.py`` (RULINGS 2026-11-26b (2)/(4)):
the build's cut records of a patch folder, once per model, and the report
of the movers against a base run.  Headless (no raster, no corpus)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

import terrain_cut_replay as TCR  # noqa: E402


def _plan(tmp_path, name):
    rec = {"id": "dsf:obj1", "resource": "m.obj", "seat": "terrain_model", "elevation": 1.0,
           "cut": {"file": "m.obj", "lat": 1.0, "lon": 2.0, "heading": 0.0, "fill": True}}
    from auto_patch_v2.airport import terrain_model as TM
    rec["seat"] = TM.SEAT
    (tmp_path / name).write_text(json.dumps({"icao": "TEST", "pack_root": "",
                                             "authored_seats": [rec]}),
                                 encoding="utf-8", newline="")


def test_records_once_per_model(tmp_path):
    _plan(tmp_path, "o4_v2_rebake_TEST.json")
    _plan(tmp_path, "o4_v2_rebake_TEST.screen.json")
    recs = TCR.records(str(tmp_path), "TEST")
    assert [r["id"] for r in recs] == ["dsf:obj1"]
    assert TCR.records(str(tmp_path), "OTHER") == []


def test_the_report_names_the_movers_against_a_base(capsys):
    row = {"resource": "m.obj", "id": "dsf:obj1", "z0": 1.0, "rim_land": 3, "rim_cells": 4,
           "plan_m2": 100, "ring": {"n": 3, "p50": 0.0}}
    base = {"shape": [2, 2], "delta": [[0.0, -5.0], [0.0, 0.0]],
            "records": [dict(row, ring={"n": 3, "p50": 4.0})]}
    rep = {"patch_dir": "P", "posting_m": 10.0, "changed": 1, "shape": [2, 2],
           "delta": [[0.0, 0.0], [-0.5, 0.0]], "records": [row]}
    TCR.print_report(rep, base)
    out = capsys.readouterr().out
    assert "base {'n': 3, 'p50': 4.0}" in out
    assert "MOVERS against base: 2 posting(s) > 0.01 m (raised 1 max 5.00 m, " \
           "lowered 1 max 0.50 m)" in out
    assert np.isclose(TCR._pct(np.array([1.0, 3.0]), 2.0)["over"], 0.5)
