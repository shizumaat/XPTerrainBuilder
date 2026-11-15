"""#2099 (owner ruling 2026-11-15T16:07Z: "Like other areas, tunnel mouths
made of multiple touching pieces need to be treated as an object group";
spec ``docs/specs/2099-mouth-groups.md``).

* the two general bugs found on the way: ``geom/foot_planes.floor_plane``
  over NaN candidates, and ``pack_partition`` over NaN anchors.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.geom.foot_planes import floor_plane, ground_plane


def test_floor_plane_leaves_a_nan_candidate_out():
    zs = [10.0] * 30 + [math.nan] * 5
    assert floor_plane(zs) == 10.0
    assert floor_plane([math.nan, math.nan]) is None
    assert ground_plane([math.nan, 4.0, 4.0]) == 4.0
    assert ground_plane([math.nan]) is None


def test_a_cold_dem_partition_is_refused_and_a_partial_one_is_said():
    from auto_patch_v2.airport.pack_partition import _refuse_groundless
    _refuse_groundless({"placements": 10, "unresolved": 2}, "XXXX")      # none: silent
    with pytest.raises(ValueError, match="cold"):
        _refuse_groundless({"placements": 10, "unresolved": 2, "no_ground": 8}, "XXXX")
    _refuse_groundless({"placements": 10, "unresolved": 2, "no_ground": 3}, "XXXX")


def test_the_deck_raster_is_the_same_grid_a_chunk_at_a_time(monkeypatch):
    """#2099 (found on the closing tile, CYSN's 827k-face fence): the plan
    trace is sampled a chunk of faces at a time -- the same grid, bounded
    memory."""
    import numpy as np

    from auto_patch_v2.airport import deck_signature as D
    rng = np.random.default_rng(7)
    xz = rng.uniform(0.0, 60.0, size=(500, 3, 2))
    whole = D._raster(xz, 0.5)
    monkeypatch.setattr(D, "_RASTER_POINTS", 37)
    chunked = D._raster(xz, 0.5)
    assert np.array_equal(whole[0], chunked[0]) and whole[2] == chunked[2]
