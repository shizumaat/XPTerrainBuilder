"""THE ISLAND'S SHORE ROADS STAND AT THE FLAT LEVEL (issue #1885; owner
2026-11-04T18:57Z: "for 'flat' airports ... on fill, when the road is close
to the airport and the other side nearby is water, we should include that
in the airport 'island' area").

Synthetic only (``auto_patch_v2/airport/flat_site_shore_roads.py``): a
square island, an aerodrome in its west half, an honest surface that is the
flat fill except a road deck the DEM reads as a lump and a hill.  No file,
no DEM, no network.
"""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import flat_site_shore_roads as SHORE
from auto_patch_v2.law import Law
from shapely.geometry import Point, box

Z0 = 7.3
TILE = (22, 113)
#: tile-relative degrees; ~1.1 km a side at 22 N
ISLAND = box(0.50, 0.50, 0.51, 0.51)
GATE = box(0.50, 0.50, 0.505, 0.51)
HILL = box(0.5075, 0.5005, 0.5095, 0.5025)
M_PER_DEG = (103_200.0, 110_750.0)
HIGHWAYS = ("primary", "service")
LAW = Law.for_airport("ZZZZ")


def _way(points_xy, **tags):
    """A ``RawWay``-shaped way from tile-relative ``(x, y)`` points."""
    return types.SimpleNamespace(
        tags={"highway": "primary", **tags},
        points=tuple((TILE[0] + y, TILE[1] + x) for x, y in points_xy))


#: north-south, east of the aerodrome, on the fill: its own deck is a lump
DECK = _way([(0.5070, 0.5040), (0.5070, 0.5090)])
#: up the hill's middle
HILL_ROAD = _way([(0.5085, 0.5008), (0.5085, 0.5022)], highway="service")


def honest(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    z = np.full(xs.shape, Z0 + 0.6)                      # the fill reads 0.6 high
    deck = (np.abs(xs - 0.5070) < 0.00008) & (ys > 0.5040) & (ys < 0.5090)
    z[deck] = Z0 + 8.0
    z[(xs > HILL.bounds[0]) & (xs < HILL.bounds[2])
      & (ys > HILL.bounds[1]) & (ys < HILL.bounds[3])] = Z0 + 15.0
    return z


def _hold(ways):
    return SHORE._road_hold(ways, HIGHWAYS, GATE, ISLAND, honest, Z0, 1.0,
                                 30.0, 9.3, M_PER_DEG, *TILE, LAW)


def _on(held, x, y):
    return held is not None and held.contains(Point(x, y))


def test_a_road_on_the_fill_outside_the_aerodrome_is_held_at_the_flat_level():
    held, rep = _hold([DECK])
    assert _on(held, 0.5070, 0.5065)
    assert rep["ways"] == 1 and rep["held_m"] > 400.0


def test_the_hold_reaches_one_post_diagonal_past_the_carriageway():
    """The bilinear stencil (the strips' rule): a post beside the edge is
    held too, so the road never reads a restored neighbour."""
    held, _ = _hold([DECK])
    half = 3.5                                        # the core's ribbon
    edge = (half + 9.3 * np.sqrt(2.0) - 1.0) / M_PER_DEG[0]
    assert _on(held, 0.5070 + edge, 0.5065)
    assert not _on(held, 0.5070 + 2 * edge, 0.5065)


def test_a_road_climbing_a_hill_keeps_the_real_surface():
    held, rep = _hold([HILL_ROAD])
    assert not _on(held, 0.5085, 0.5015)
    assert rep["hill_kept"] > 0


@pytest.mark.parametrize("way", [
    _way([(0.5070, 0.5040), (0.5070, 0.5090)], tunnel="yes"),   # a bore keeps its ramps
    _way([(0.5020, 0.5040), (0.5020, 0.5090)]),                 # inside the aerodrome
    _way([(0.5200, 0.5040), (0.5200, 0.5090)]),                 # off the island
    _way([(0.5070, 0.5040), (0.5070, 0.5090)], highway="footway"),
])
def test_what_is_never_held(way):
    held, rep = _hold([way])
    assert held is None and rep["ways"] == 0


def test_no_island_holds_nothing():
    held, _ = SHORE._road_hold([DECK], HIGHWAYS, GATE, None, honest, Z0, 1.0,
                                    30.0, 9.3, M_PER_DEG, *TILE, LAW)
    assert held is None


@pytest.mark.parametrize("median,expect", [(2.0, True), (6.8, True), (7.0, False), (None, False)])
def test_on_fill_is_z0_above_the_honest_median(median, expect):
    rec = {"z0_m": Z0, "signals": {"s2": {"median_m": median}}}
    assert SHORE._on_fill(rec, 0.5) is expect


def _snapshot():
    """A 0.02-degree working-grid window over the island (101 posts a side)."""
    xs = np.linspace(0.495, 0.515, 101)
    ys = np.linspace(0.515, 0.495, 101)
    gx, gy = np.meshgrid(xs, ys)
    frame = (0.0, 1.0, 0.0, 1.0, 5001, 5001)
    c0, r0 = int(round(0.495 * 5000)), int(round((1.0 - 0.515) * 5000))
    return (r0, r0 + 100, c0, c0 + 100, honest(gx.ravel(), gy.ravel()).reshape(gx.shape)), frame


def test_site_hold_reads_the_snapshot_and_names_the_count():
    snap, frame = _snapshot()
    rec = {"z0_m": Z0, "signals": {"s2": {"median_m": 2.0}}}
    held, why = SHORE.site_hold(rec, LAW, GATE, snap, frame, lambda g: (ISLAND, None),
                                lambda *box_ll: [DECK], HIGHWAYS, *TILE, M_PER_DEG, 1.0)
    assert _on(held, 0.5070, 0.5065) and "1 way(s)" in why


@pytest.mark.parametrize("median,island,why", [
    (7.2, ISLAND, "not on fill"), (2.0, None, "no island (mainland)")])
def test_site_hold_refusals(median, island, why):
    snap, frame = _snapshot()
    rec = {"z0_m": Z0, "signals": {"s2": {"median_m": median}}}
    held, got = SHORE.site_hold(rec, LAW, GATE, snap, frame,
                                lambda g: (island, "mainland"),
                                lambda *box_ll: [DECK], HIGHWAYS, *TILE, M_PER_DEG, 1.0)
    assert held is None and got == why


def test_the_hold_never_reaches_into_the_aerodrome():
    """Airside is king: a road along the boundary is held outside it, never
    within one post diagonal of the gate."""
    held, _ = _hold([_way([(0.5052, 0.5040), (0.5052, 0.5090)])])
    assert held is not None
    assert held.intersection(GATE.buffer(9.3 * np.sqrt(2.0) / M_PER_DEG[0] * 0.99)).area == 0.0


def test_the_patch_road_reach_outside_the_aerodrome_is_never_held():
    """``clear_m`` (``osm_roads.boundary_reach_m``): the roads the patch
    ribbons and grades itself just outside the boundary keep their DEM."""
    way = _way([(0.5058, 0.5040), (0.5058, 0.5090)])       # ~85 m east of the gate
    held, _ = SHORE._road_hold([way], HIGHWAYS, GATE, ISLAND, honest, Z0, 1.0,
                                    30.0, 9.3, M_PER_DEG, *TILE, LAW, clear_m=150.0)
    assert held is None
    held, _ = SHORE._road_hold([way], HIGHWAYS, GATE, ISLAND, honest, Z0, 1.0,
                                    30.0, 9.3, M_PER_DEG, *TILE, LAW, clear_m=0.0)
    assert held is not None
