"""Twin of ``tools/terrain_shell_replay.py`` (#2272 round 2): the seat
records it replays, the body / band / rim measures and the water report on
a synthetic shell and raster -- no pack, no corpus."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(_HERE, "..", "tools"), os.path.join(_HERE, "..", "src")]

import terrain_shell_replay as R  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402

LAT, LON = 17.5, -62.5


def _solid(size=60.0, y=5.0):
    q = np.array([[-size / 2, y, -size / 2], [size / 2, y, -size / 2],
                  [size / 2, y, size / 2], [-size / 2, y, size / 2]])
    return np.stack([q[[0, 1, 2]], q[[0, 2, 3]]])


def _rows():
    return [{"verdict": "terrain shell", "resource": "Ortho/x_Hill.obj", "lat": LAT, "lon": LON,
             "heading": 0.0, "z0": 1.0},
            {"verdict": "terrain model", "resource": "big.obj", "lat": LAT, "lon": LON,
             "heading": 0.0, "z0": 1.0}]


def _raster(sh, ground):
    n = 401
    f = {"tile_lat": 17, "tile_lon": -63, "nxdem": n, "nydem": n,
         "x0": 0.498, "x1": 0.502, "y0": 0.498, "y1": 0.502}
    return R.Raster(np.full((n, n), ground, np.float32), f, sh.to_ll)


def test_the_shells_are_seat_records_with_shell_and_fill(monkeypatch):
    recs = R.shell_records(_rows(), "/pack", "ICAO")
    assert len(recs) == 1
    c = recs[0]["cut"]
    assert c["shell"] and c["fill"] and c["file"] == "/pack/Ortho/x_Hill.obj"
    assert recs[0]["seat"] == TM.SEAT and recs[0]["elevation"] == 1.0


def test_the_measures_read_body_band_rim_and_water(monkeypatch):
    monkeypatch.setattr(TM, "plan_solid", lambda path: _solid())
    sh = R.Shells(R.shell_records(_rows(), "/pack", "ICAO"))
    sh.samples()
    assert [i["name"] for i in sh.items] == ["Hill"]
    ras = _raster(sh, 10.0)
    m = R.measure(ras, sh, ras.base)
    assert m["body_n"] > 0 and m["body_over"] == m["body_n"]         # 10 m over a 6 m shell
    assert m["band_over_pct"] == pytest.approx(100.0)
    assert m["rim_float_m"] == 0 and m["rim_lowered_pct"] == 0.0
    low = np.full_like(ras.base, 2.0)
    m = R.measure(ras, sh, low)
    assert m["body_over"] == 0 and m["rim_float_m"] == m["rim_land_m"] > 200
    assert m["rim_lowered_pct"] == pytest.approx(100.0)
    w = R.water_report(ras, sh)["Hill"]
    assert w["plan_under_datum_pct"] == 0.0 and w["rim_under_datum_m"] == 0
