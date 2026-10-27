"""THE FLAT-SITE PLATEAU IS A FILL, NOT A CUT (owner RULINGS 2026-10-26r,
Q173 option a; #1208; refines 2026-10-20af/ag and replaces the #1137
5 m / 10 m off-site band).

"Flattening only raises ground; where the real ground stands more than
0.5 m above the flat level, keep the real ground, except where pavement
grading itself needs a cut."  So after the stamp bakes Z0, every post it
LOWERED whose honest surface stands more than 0.5 m above Z0 gets that
surface back (in full from 1.0 m, linearly between), the airport's own
pavement keeps Z0, and ground below Z0 stays lifted (the reclamation
class, 20af).  The #1137 case — a hill beside the airport — is one
instance.

Synthetic only: the fixtures of ``tests/test_flat_site_mode.py`` (no
X-Plane install, no CIFP, no network, no write anywhere).
"""
from __future__ import annotations

import dataclasses
import types

import numpy as np
import O4_Airport_Elevation_Insets as INSETS
import pytest
from auto_patch import flat_site_relief as RELIEF
from auto_patch_v2.airport import flat_site_prep as PREP
from shapely.geometry import box
from tests.test_flat_site_mode import (
    ANCHOR,
    LAND_BASE_M,
    FakeDEM,
    dico,
    make_tile,
    site_for,
    substitutions,
    wire_airport,
)

Z0 = 3.96
N = 3601
#: Just west of the boundary, inside the detector's 200 m margin and so
#: inside the plateau's footprint: the hill the 1.0.409 plateau flattened.
HILL_LON = ANCHOR[1] - 0.0112
HILL_M = 80.0
#: The airport's pavement: an apron about the anchor, well inside the
#: boundary (half-widths 0.004 deg lon, 0.0015 deg lat).
PAVEMENT = box(ANCHOR[1] - 0.004, ANCHOR[0] - 0.0015,
               ANCHOR[1] + 0.004, ANCHOR[0] + 0.0015)
#: Boundary grass: inside the boundary (half-lat 0.006), off the pavement.
GRASS = (ANCHOR[0] + 0.0040, ANCHOR[1])


def _wire_paved(monkeypatch):
    """The fixture airport plus one apt.dat pavement (:data:`PAVEMENT`)."""
    wire_airport(monkeypatch)

    def _site(icao, root, cifp, law, apt_dat_path=None):
        site = site_for(icao.upper(), [Z0] * 4)
        to_xy, _ll = site.frame.transformers()
        outer = tuple(to_xy(lo, la) for lo, la in PAVEMENT.exterior.coords[:-1])
        return dataclasses.replace(site, pavements=(PREP._Poly(outer, ()),))
    monkeypatch.setattr(PREP, "site_inputs", _site)


def _cell(dem, lat_deg, lon_deg):
    step = 1.0 / (dem.nxdem - 1)
    return float(dem.alt_dem[int(round((1.0 - lat_deg) / step)),
                             int(round(lon_deg / step))])


def _overlay(dem):
    tile = make_tile(dem)
    got = substitutions(tile)
    assert len(got) == 1 and got[0]["z0_m"] == pytest.approx(Z0)
    INSETS.overlay_flat_site_insets(tile, dico())
    return tile


def test_boundary_grass_above_the_flat_level_keeps_its_real_surface(monkeypatch):
    """The CYVR shape: a coastal flat standing 2 m above Z0.  Inside the
    boundary and in the margin it keeps 2 m; only the pavement is cut."""
    _wire_paved(monkeypatch)
    dem = FakeDEM(constant=Z0 + 2.0, n=N)
    _overlay(dem)
    assert _cell(dem, *GRASS) == pytest.approx(Z0 + 2.0, abs=1e-3)
    assert _cell(dem, ANCHOR[0], HILL_LON) == pytest.approx(Z0 + 2.0, abs=1e-3)
    assert _cell(dem, *ANCHOR) == pytest.approx(Z0, abs=1e-3)   # pavement
    report = dem.synthetic_flat_site_provenance[0]["fill_only"]
    assert report["restored_posts"] > 0
    assert report["max_offset_m"] == pytest.approx(2.0, abs=0.01)


def test_a_hill_beside_the_airport_keeps_its_real_surface(monkeypatch):
    """#1137's case, still held: the Taipa-hillside shape."""
    _wire_paved(monkeypatch)
    dem = FakeDEM(constant=LAND_BASE_M, n=N)
    step = 1.0 / (N - 1)
    dem.alt_dem[:, int(round((ANCHOR[1] - 0.0130) / step)):
                int(round((ANCHOR[1] - 0.0105) / step))] = HILL_M
    _overlay(dem)
    assert _cell(dem, ANCHOR[0], HILL_LON) == pytest.approx(HILL_M, abs=1e-3)


def test_ground_below_the_flat_level_is_still_lifted(monkeypatch):
    """The VHHH shape (20af, R8-1): sea-fill ground below Z0 takes Z0 on
    the pavement, the grass and the margin alike."""
    _wire_paved(monkeypatch)
    dem = FakeDEM(constant=LAND_BASE_M, n=N)
    _overlay(dem)
    for lat, lon in (ANCHOR, GRASS, (ANCHOR[0], ANCHOR[1] + 0.0105)):
        assert _cell(dem, lat, lon) == pytest.approx(Z0, abs=1e-3)
    assert dem.synthetic_flat_site_provenance[0]["fill_only"][
        "restored_posts"] == 0


def test_ground_within_half_a_metre_of_the_flat_level_is_flattened(monkeypatch):
    _wire_paved(monkeypatch)
    dem = FakeDEM(constant=Z0 + 0.4, n=1201)
    _overlay(dem)
    assert _cell(dem, *GRASS) == pytest.approx(Z0, abs=1e-3)
    assert dem.synthetic_flat_site_provenance[0]["fill_only"][
        "restored_posts"] == 0


def _unit_dem(values):
    return types.SimpleNamespace(x0=0.0, x1=1.0, y0=0.0, y1=1.0,
                                 nxdem=values.shape[1], nydem=values.shape[0],
                                 nodata=-32768.0,
                                 alt_dem=values.astype(np.float32))


def test_the_restore_ramps_from_half_a_metre_to_a_metre():
    """Z0 up to 0.5 m above it, the real surface from 1.0 m, linear in
    between — continuous; below Z0 stays lifted."""
    base = np.array([[-8.0, 0.25, 0.75, 1.0, 30.0]] * 3)
    dem = _unit_dem(base)
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    dem.alt_dem[...] = 0.0                      # the bake put Z0 = 0 everywhere
    RELIEF.restore_ground_above_flat_level(dem, snap, None, 0.0)
    assert dem.alt_dem[1].tolist() == pytest.approx([0.0, 0.0, 0.375, 1.0,
                                                     30.0])


def test_no_post_ends_more_than_half_a_metre_below_the_honest_surface():
    rng = np.random.default_rng(1208)
    base = rng.uniform(-5.0, 5.0, size=(40, 40))
    dem = _unit_dem(base)
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    feather = rng.uniform(0.0, 1.0, size=base.shape)        # a feathered bake
    dem.alt_dem[...] = feather * 0.0 + (1.0 - feather) * base
    RELIEF.restore_ground_above_flat_level(dem, snap, None, 0.0)
    assert float((base - dem.alt_dem).max()) <= RELIEF.KEEP_ABOVE_M + 1e-5


def test_only_a_cut_is_undone():
    """A post another stamp RAISED (after > before) is never pulled back."""
    dem = _unit_dem(np.full((3, 3), 5.0))
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    dem.alt_dem[...] = 6.0
    report = RELIEF.restore_ground_above_flat_level(dem, snap, None, 0.0)
    assert report["restored_posts"] == 0 and float(dem.alt_dem.min()) == 6.0


def test_the_pavement_stays_at_z0_whatever_the_dem_says():
    dem = _unit_dem(np.full((3, 5), 50.0))
    snap = RELIEF.snapshot_window(dem, [(0.0, 0.0, 1.0, 1.0)])
    dem.alt_dem[...] = 0.0
    pavement = box(-0.1, -0.1, 0.6, 1.1)        # the west three columns
    RELIEF.restore_ground_above_flat_level(dem, snap, pavement, 0.0)
    assert dem.alt_dem[1].tolist() == pytest.approx([0.0, 0.0, 0.0, 50.0,
                                                     50.0])


def test_the_pavement_reaches_the_bake_in_lon_lat(monkeypatch):
    """The decision record publishes its held ground in (lon, lat) — the
    rule's exemption — and it is the pavement, not the boundary (the
    fixture's runway is a point, so it has no strip)."""
    _wire_paved(monkeypatch)
    tile = make_tile(FakeDEM(constant=LAND_BASE_M, n=1201))
    got = substitutions(tile)
    site = RELIEF.site_geometry_tile_degrees(got[0]["record"], 0, 0)
    assert site is not None
    assert site.symmetric_difference(PAVEMENT).area < 1e-2 * PAVEMENT.area
