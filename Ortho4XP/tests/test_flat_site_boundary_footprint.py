"""THE FLAT-SITE PLATEAU FOLLOWS THE AIRPORT BOUNDARY, NEVER A BOX
(issue #1144, owner RULINGS 2026-10-20ag).

The DEM-prep stamp's footprint is the decision record's region —
pavement ∪ runways ∪ boundary ⊕ the flat-site margin, water-cut — plus the
feather, which lies wholly OUTSIDE it (R17c-2).  The bounding box of that
region, and the box of every claimed-object cluster, are retired: ground in
a box corner the airport never reaches keeps the real surface.

Synthetic only: the fixtures of ``tests/test_flat_site_mode.py`` with an
L-shaped airport whose bounding box has an empty north-east quarter.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

import O4_Airport_Elevation_Insets as INSETS
from auto_patch import flat_site_mode
from tests.test_flat_site_mode import (ANCHOR, FEATHER_M, MARGIN_M, R_EARTH,
                                       dico, flat_dem, make_tile,
                                       substitutions, wire_airport)

_W, _H = 0.012, 0.008          # half-extents in degrees (~1.3 km x 0.9 km)
#: An L: the bounding box minus its north-east quarter.
L_BOUNDARY = Polygon([
    (ANCHOR[1] - _W, ANCHOR[0] - _H),
    (ANCHOR[1] + _W, ANCHOR[0] - _H),
    (ANCHOR[1] + _W, ANCHOR[0]),
    (ANCHOR[1], ANCHOR[0]),
    (ANCHOR[1], ANCHOR[0] + _H),
    (ANCHOR[1] - _W, ANCHOR[0] + _H),
])
BASE_M = 1.0
Z0_M = 3.96
_DEG_M = math.pi * R_EARTH / 180.0


def _cell(dem, lat_deg, lon_deg):
    step = 1.0 / (dem.nxdem - 1)
    return float(dem.alt_dem[int(round((1.0 - lat_deg) / step)),
                             int(round(lon_deg / step))])


@pytest.fixture
def baked(monkeypatch):
    wire_airport(monkeypatch, boundary=L_BOUNDARY)
    monkeypatch.setattr(flat_site_mode, "water_cutout", lambda tile: None)
    dem = flat_dem(BASE_M, n=3601)
    tile = make_tile(dem)
    got = substitutions(tile)
    assert len(got) == 1 and got[0]["z0_m"] == pytest.approx(Z0_M)
    INSETS.overlay_flat_site_insets(tile, dico())
    return dem, got[0]


def test_the_empty_box_corner_keeps_the_real_surface(baked):
    dem, _sub = baked
    # Inside the bbox's north-east quarter, > margin + feather from the
    # L: the retired box stamp put Z0 here.
    off = (MARGIN_M + FEATHER_M + 200.0) / _DEG_M
    assert _cell(dem, ANCHOR[0] + off, ANCHOR[1] + off) == pytest.approx(
        BASE_M, abs=1e-4)


def test_the_boundary_and_its_margin_stand_at_z0(baked):
    dem, _sub = baked
    assert _cell(dem, ANCHOR[0] - _H / 2, ANCHOR[1]) == pytest.approx(
        Z0_M, abs=1e-3)
    # Half the margin north of the L's inner (north-facing) edge.
    half_margin = 0.5 * MARGIN_M / _DEG_M
    assert _cell(dem, ANCHOR[0] + half_margin,
                 ANCHOR[1] + _W / 2) == pytest.approx(Z0_M, abs=1e-3)


def test_the_feather_lies_outside_the_margin(baked):
    dem, _sub = baked
    lon = ANCHOR[1] + _W / 2
    inner = ANCHOR[0] + MARGIN_M / _DEG_M
    mid = _cell(dem, inner + 0.5 * FEATHER_M / _DEG_M, lon)
    assert BASE_M + 0.1 < mid < Z0_M - 0.1
    assert _cell(dem, inner + (FEATHER_M + 40.0) / _DEG_M, lon) == \
        pytest.approx(BASE_M, abs=1e-4)


def test_the_stamp_keeps_the_declared_box(baked):
    dem, sub = baked
    entry = dem.synthetic_flat_site_provenance[0]
    assert entry["extent_tile_degrees"] == list(sub["extent_deg"])
    assert sub["footprint_deg"].bounds == pytest.approx(sub["extent_deg"])
    x0, y0, x1, y1 = sub["extent_deg"]
    assert sub["footprint_deg"].area < 0.9 * (x1 - x0) * (y1 - y0)


def test_a_cluster_footprint_is_its_hull_not_its_box():
    tri = [(ANCHOR[1] + dx, ANCHOR[0] + dy) for dx, dy in
           ((0.020, 0.020), (0.022, 0.020), (0.024, 0.020),
            (0.020, 0.022), (0.020, 0.024), (0.022, 0.022))]
    (cluster,) = flat_site_mode.claimed_placement_cluster_bounds(
        tri, ANCHOR, 0, 0, margin_m=50.0, max_km=100.0)
    footprint = cluster["footprint_deg"]
    x0, y0, x1, y1 = cluster["extent_deg"]
    assert footprint.bounds == pytest.approx((x0, y0, x1, y1))
    assert footprint.area < 0.8 * (x1 - x0) * (y1 - y0)
