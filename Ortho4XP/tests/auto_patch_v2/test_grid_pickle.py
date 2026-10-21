"""issue #1092 — a gridded geometry survives the stage-cache record and the
arrangement-memo front copy WITH its precision grid, so a cache hit (or a
served front) overlays exactly as the fresh computation does.

shapely 2.x pickles a geometry as bare WKB: without
``auto_patch_v2.geom.grid_pickle`` both paths hand back ``get_precision ==
0`` and the next overlay nodes off the grid (measured: the union below gains
off-grid vertices).  Synthetic throughout (no corpus).
"""
from __future__ import annotations

import pickle

import shapely
from shapely.geometry import Polygon
from auto_patch_v2.airport import stage_cache as SC
from auto_patch_v2.geom import grid_pickle as GP
from auto_patch_v2.pipeline import front_cache as FC
from auto_patch_v2.planar import arrangement_memo as AM

GRID = 0.01


def _cold():
    """A stage output holding a gridded face (as classify's minted faces do)."""
    face = shapely.set_precision(
        Polygon([(0, 0), (10.004, 0), (10.004, 5.0031), (0, 5.0031)]), GRID)
    return {"faces": [face], "plat": {"face": face}}


def _downstream(out):
    """The next overlay a later stage runs on the face: a union with an
    off-grid cutter — noded on the face's grid when it carries one."""
    cutter = Polygon([(9.0, 2.0), (12.3456, 2.0), (12.3456, 3.789), (9.0, 3.789)])
    return shapely.to_wkb(out["faces"][0].union(cutter))


def _served_from_record(tmp_path, out):
    recipe = {"inputs": {"a": "1"}, "code": {"classify": "c"}, "env": {}}
    key = SC.key_of("classify", recipe)
    blob, digest = SC.encode(out)
    path = str(tmp_path / "rec.bin")
    SC.write(path, FC.FrontCache.header("classify", key, recipe, digest, len(blob)),
             {}, blob, used=False)
    _head, _wit, load = SC.read(path, key, recipe)
    return load()


def test_a_stage_cache_hit_keeps_the_grid_and_overlays_as_the_cold_run(tmp_path):
    cold = _cold()
    hit = _served_from_record(tmp_path, cold)
    assert shapely.get_precision(hit["faces"][0]) == GRID
    assert shapely.to_wkb(hit["faces"][0]) == shapely.to_wkb(cold["faces"][0])
    assert _downstream(hit) == _downstream(cold)
    assert hit["plat"]["face"] is hit["faces"][0], "shared references stay shared"


def test_an_arrangement_memo_front_copy_keeps_the_grid():
    cold = _cold()
    front = {"pad_clip": {"faces": cold["faces"]}, "plat": cold["plat"], "rows": [1]}
    fresh = AM._fresh(front)
    got = {"faces": fresh["pad_clip"]["faces"]}
    assert shapely.get_precision(fresh["plat"]["face"]) == GRID
    assert _downstream(got) == _downstream(cold)


def test_an_ungridded_geometry_keeps_shapelys_own_reduce():
    g = Polygon([(0, 0), (1.23456789, 0), (1, 1)])
    assert GP._reduce(g) == g.__reduce__()
    assert shapely.get_precision(pickle.loads(pickle.dumps(g))) == 0.0
