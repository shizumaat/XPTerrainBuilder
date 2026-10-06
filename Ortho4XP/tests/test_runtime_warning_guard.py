"""#418 guard twin: the paths that leaked numpy RuntimeWarnings run silent
with RuntimeWarning promoted to an error.

* ``O4_Bathymetry.set_depth_ratio`` — ``node_bathy`` is ``uint8``; under
  numpy 2's scalar promotion an ``int`` ``ratio_bathy`` keeps the product in
  ``uint8`` and WRAPS (``10 * 1 * 200`` reads 2000 mod 256), the
  "overflow encountered in scalar multiply" ``test_dsf_texture_modes`` showed.
  The cfg type is ``float`` and every production read goes through it, so the
  stub was the defect, not the engine.
* ``geom.rotated_rect.rotated_rectangle`` and the harness tools that read a
  rectangle (``test_rotated_rectangle_guard`` holds the bytes).
"""
from __future__ import annotations

import importlib.util
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

import O4_Bathymetry as BATHY
from O4_Cfg_Vars import cfg_vars

ROOT = Path(__file__).resolve().parent.parent


def _stub_tile(ratio_bathy):
    tile = type("Tile", (), {})()
    tile.ratio_bathy = ratio_bathy
    return tile


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ratio_bathy_is_float_on_every_production_read():
    """The tile reads it through ``cfg_vars['ratio_bathy']['type']`` (config
    file, global config) or the default; both are float."""
    spec = cfg_vars["ratio_bathy"]
    assert spec["type"] is float
    assert isinstance(spec["default"], float)
    assert isinstance(spec["type"]("1"), float)


def test_set_depth_ratio_is_silent_on_the_cfg_type():
    node_bathy = np.arange(256, dtype=np.uint8)
    node_is_coast = np.zeros(256, dtype=bool)
    tile = _stub_tile(cfg_vars["ratio_bathy"]["default"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        got = [BATHY.set_depth_ratio(n, node_is_coast, node_bathy, tile)
               for n in range(256)]
    want = [max(min(10 * 1.0 * v / 255, 1), 0.1) for v in range(256)]
    assert got == want


def test_an_int_ratio_is_the_defect_the_stub_carried():
    """Why the stub's type matters: an int wraps in uint8 (wrong value, and
    the warning).  Pinned so a future numpy promotion change is seen."""
    node_bathy = np.array([200], dtype=np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        wrapped = 10 * 1 * node_bathy[0] / 255
    assert wrapped != 10 * 1.0 * 200 / 255
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(RuntimeWarning):
            BATHY.set_depth_ratio(0, np.zeros(1, dtype=bool), node_bathy,
                                  _stub_tile(1))


def test_dsf_texture_modes_stub_carries_the_cfg_type(tmp_path):
    mod = _load("rwguard_dsf_texture_modes",
                ROOT / "tests" / "test_dsf_texture_modes.py")
    tile = mod._make_tile(str(tmp_path), "full_ortho")
    assert type(tile.ratio_bathy) is cfg_vars["ratio_bathy"]["type"]


def test_rectangle_readers_are_silent():
    cg = _load("rwguard_check_grade", ROOT / "tools" / "check_grade.py")
    from auto_patch_v2.geom.rotated_rect import rotated_rectangle
    rings = ([(0, 0), (10, 0), (10, 4), (0, 4)],
             [(0, 0), (10, 0), (10, 0), (0, 0)],
             [(0, 0), (1, 1), (2, 2)],
             [(0, 0), (8, 6), (5, 10), (-3, 4)])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        for ring in rings:
            rotated_rectangle(Polygon(ring))
            cg._ring_width_m(ring)
