"""The terrain-model census (``tools/terrain_model_census.py``) reads a
pack through ``terrain_model``'s own gates and match: a synthetic pack's
photo-textured mountain is a candidate, its atlas-textured twin is not;
the raster sampler reads the finest raster and says where it is quality
elevation.  No corpus, no DSFTool."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "auto_patch_v2"))

import terrain_model_census as TMC  # noqa: E402
import test_terrain_model as TTM  # noqa: E402


def test_the_gates_count_the_pack(tmp_path):
    pack = tmp_path / "Pack"
    (pack / "o").mkdir(parents=True)
    TTM._write(pack / "o", "mountain.obj", TTM._hill)
    TTM._write(pack / "o", "block.obj", TTM._hill, uv="atlas")
    gates, shapes = TMC.candidates(str(pack))
    assert gates == {"objects": 2, "plan": 2, "photo": 1, "candidate": 1, "ground": 0}
    assert list(shapes) == ["o/mountain.obj"]


def test_the_sampler_reads_the_finest_raster_and_says_where_it_is_quality():
    fine = ((-0.01, 0.0001, 0, 0.01, 0, -0.0001), np.full((200, 200), 7.0), 1.0, "a.tif")
    coarse = ((-1.0, 0.01, 0, 1.0, 0, -0.01), np.full((200, 200), 3.0), 90.0, "b.hgt")
    z = TMC.sampler([fine, coarse], 0.0, 0.0)
    q = TMC.sampler([fine, coarse], 0.0, 0.0, fine=True)
    assert z(np.array([0.0, 5000.0]), np.array([0.0, 0.0])).tolist() == [7.0, 3.0]
    assert q(np.array([0.0, 5000.0]), np.array([0.0, 0.0])).tolist() == [True, False]
