"""Issues #1335 (KOUN) and #1349 (KSEE): the road-reach ribbon never feeds
an invalid reach to its intersection.

``_ribbon_over`` widens a road's ribbon only around its core-width ribbon:
``reach = core.buffer(hw - core_hw)``.  ``core`` comes out of
``shapely.set_precision(..., grid)`` and so carries that fixed precision
model; GEOS snap-rounds a buffer of such a geometry onto the grid, and
where two mitred corners lay a grid step apart the reach came back as
NESTED SHELLS.  The next ``intersection`` raised ``TopologyException: Ring
edge missing`` and the airport shipped without a patch.  The fixture holds
the two reported ways' axes and the standing geometry they were cut by
(local metres).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import shapely

from auto_patch_v2.classify.ribbon_mint import _Occupied, _ribbon_over

_CASES = json.loads((Path(__file__).parent / "fixtures"
                     / "road_reach_ring_edge_1335.json").read_text())["cases"]


@pytest.mark.parametrize("issue", sorted(_CASES))
def test_the_reach_ribbon_of_the_reported_way_is_minted_valid(issue):
    c = _CASES[issue]
    axes = [shapely.from_wkt(a) for a in c["axes"]]
    obstacle = shapely.from_wkt(c["obstacle"])
    rib = _ribbon_over(axes, c["hw"], _Occupied(obstacle), c["core_hw"], c["grid"])
    assert rib.is_valid and rib.area > 0.0
    # still a ribbon: inside the way's half-width, off what stands
    corridor = shapely.union_all([a.buffer(c["hw"] + c["grid"]) for a in axes])
    assert rib.difference(corridor).area < 1e-6
    assert rib.intersection(obstacle).area < c["grid"] * sum(a.length for a in axes)
