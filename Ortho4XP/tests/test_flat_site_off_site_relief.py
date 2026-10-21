"""A HILL IS NOT THE SITE (issue #1137) — the flat-site plateau keeps the
airport's own surfaces at Z0 and gives a hill beside them its real surface.

Owner, app 1.0.409 in-sim: VMMC 22.158794, 113.571673 (the Taipa hillside
west of the terminal) sat at apron level — ``Data+22+113.alt`` 6.096 m,
the same raster composed with FLAT-SITE mode off 86.4 m — because the
synthetic inset is the RECTANGLE of the detector's region (and one per
claimed-object cluster) minus water, and every land post inside it took
Z0.  VHHH's Lantau hillside behind Tung Chung read 7.62 m against 294 m.

Synthetic only: the fixtures of ``tests/test_flat_site_mode.py`` (no
X-Plane install, no CIFP, no network, no write anywhere).
"""
from __future__ import annotations

import types

import numpy as np
import O4_Airport_Elevation_Insets as INSETS
import pytest
from auto_patch import flat_site_relief as RELIEF
from shapely.geometry import box
from tests.test_flat_site_mode import (
    ANCHOR,
    BOUNDARY,
    LAND_BASE_M,
    FakeDEM,
    dico,
    make_tile,
    substitutions,
    wire_airport,
)

Z0 = 3.96
N = 3601
#: Just west of the boundary, inside the detector's 200 m margin and so
#: inside the bake's rectangle: the hill the 1.0.409 plateau flattened.
HILL_LON = ANCHOR[1] - 0.0112
HILL_M = 80.0


def _hill_dem(hill_m=HILL_M):
    dem = FakeDEM(constant=LAND_BASE_M, n=N)
    step = 1.0 / (N - 1)
    west = int(round((ANCHOR[1] - 0.0130) / step))
    edge = int(round((ANCHOR[1] - 0.0105) / step))
    dem.alt_dem[:, west:edge] = hill_m
    return dem


def _cell(dem, lat_deg, lon_deg):
    step = 1.0 / (dem.nxdem - 1)
    return float(dem.alt_dem[int(round((1.0 - lat_deg) / step)),
                             int(round(lon_deg / step))])


def _overlay(dem):
    tile = make_tile(dem)
    got = substitutions(tile)
    assert len(got) == 1 and got[0]["z0_m"] == pytest.approx(Z0)
    x0, _y0, _x1, _y1 = got[0]["extent_deg"]
    assert x0 < HILL_LON - 0.0005, "the fixture's hill must sit in the box"
    INSETS.overlay_flat_site_insets(tile, dico())
    return tile


def test_a_hill_in_the_plateau_box_keeps_its_real_surface(monkeypatch):
    wire_airport(monkeypatch)
    dem = _hill_dem()
    _overlay(dem)
    # The hill beside the airport: its real surface, not Z0.
    assert _cell(dem, ANCHOR[0], HILL_LON) == pytest.approx(HILL_M, abs=1e-3)
    # The airport's own ground: Z0 as before.
    assert _cell(dem, ANCHOR[0], ANCHOR[1]) == pytest.approx(Z0, abs=1e-3)
    entry = dem.synthetic_flat_site_provenance[0]
    assert entry["off_site_relief"]["restored_posts"] > 0
    assert entry["off_site_relief"]["max_offset_m"] == pytest.approx(
        HILL_M - Z0, abs=0.01)


def test_low_ground_beside_the_airport_is_still_lifted(monkeypatch):
    """ONLY ABOVE: the margin's land below Z0 (the reclamation class R8-1
    exists for) takes Z0 exactly as before."""
    wire_airport(monkeypatch)
    dem = _hill_dem()
    _overlay(dem)
    east_margin = ANCHOR[1] + 0.0105
    assert _cell(dem, ANCHOR[0], east_margin) == pytest.approx(Z0, abs=1e-3)


def test_ground_within_the_band_restores_nothing(monkeypatch):
    """Ground nowhere above Z0 + band/2: the rule restores nothing."""
    wire_airport(monkeypatch)
    dem = FakeDEM(constant=Z0 + 4.9, n=1201)
    tile = make_tile(dem)
    substitutions(tile)
    INSETS.overlay_flat_site_insets(tile, dico())
    report = dem.synthetic_flat_site_provenance[0]["off_site_relief"]
    assert report["restored_posts"] == 0


def _unit_dem(values):
    return types.SimpleNamespace(x0=0.0, x1=1.0, y0=0.0, y1=1.0,
                                 nxdem=values.shape[1], nydem=values.shape[0],
                                 nodata=-32768.0,
                                 alt_dem=values.astype(np.float32))


def test_the_band_ramps_so_the_plateau_meets_the_hill_without_a_cliff():
    """Z0 up to band/2 above it, the real surface beyond band, linear in
    between — continuous in the honest surface; below Z0 stays lifted."""
    base = np.array([[-8.0, 4.0, 7.5, 10.0, 30.0]] * 3)
    dem = _unit_dem(base)
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    dem.alt_dem[...] = 0.0                      # the bake put Z0 = 0 everywhere
    RELIEF.restore_off_site_relief(dem, snap, box(5.0, 5.0, 6.0, 6.0),
                                   0.0, 10.0)
    assert dem.alt_dem[1].tolist() == pytest.approx([0.0, 0.0, 3.75, 10.0,
                                                     30.0])


def test_the_airports_own_surfaces_stay_at_z0_whatever_the_dem_says():
    dem = _unit_dem(np.full((3, 5), 50.0))
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    dem.alt_dem[...] = 0.0
    site = box(-0.1, -0.1, 0.6, 1.1)            # the west three columns
    RELIEF.restore_off_site_relief(dem, snap, site, 0.0, 10.0)
    assert dem.alt_dem[1].tolist() == pytest.approx([0.0, 0.0, 0.0, 50.0,
                                                     50.0])


def test_the_gate_reaches_the_bake_in_lon_lat(monkeypatch):
    """The decision record publishes its gate in (lon, lat) — the rule's
    site — and it is the airport's boundary, not the margin-grown region."""
    wire_airport(monkeypatch)
    tile = make_tile(FakeDEM(constant=LAND_BASE_M, n=1201))
    got = substitutions(tile)
    site = RELIEF.site_geometry_tile_degrees(got[0]["record"], 0, 0)
    assert site is not None
    assert site.symmetric_difference(BOUNDARY).area < 1e-3 * BOUNDARY.area
