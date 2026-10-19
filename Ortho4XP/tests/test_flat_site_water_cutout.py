"""THE SYNTHETIC FLAT-SITE INSET NEVER WRITES Z0 OVER WATER (owner
RULINGS 2026-09-09m; mechanism 09o (2); spec
``docs/specs/auto-patch-v2/water-datum-spec.md`` §3).

The synthetic inset is a constant-Z0 BBOX.  At a coastal airport that
bbox covers water: measured on the owner's OTHH build (1.0.297),
``Data+25+051.alt`` reads Z0 3.962 m over 80.7 % of the airport bbox,
canal and ~1 km of open sea included — the plateau the mesh then drapes,
and the "water lifted up to terrain level" the owner read.

The law: water is CUT OUT of the raster (nodata there, which is what the
bake already means by "the base keeps its value"), with a HARD mask edge
at the shoreline — the vertical sea wall a reclaimed edge is ruled to
have (R17b-2), never a beach ramp.

Synthetic only: the fixtures of ``tests/test_flat_site_mode.py`` (no
X-Plane install, no CIFP, no network, no download, no write anywhere) and
a hand-made water polygon standing in for the tile's cached layers.
"""
from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

import O4_Airport_Elevation_Insets as INSETS
from auto_patch import flat_site_mode
from tests.test_flat_site_mode import (ANCHOR, FEATHER_M, dico, flat_dem,
                                       make_tile, sha, substitutions,
                                       wire_airport)

#: A canal across the airport's southern half, in tile degrees.
CANAL = box(ANCHOR[1] - 0.05, ANCHOR[0] - 0.004,
            ANCHOR[1] + 0.05, ANCHOR[0] - 0.002)


def _wire_water(monkeypatch, geometry):
    """Stand in for ``O4_Vector_Map.cached_tile_water`` — the ONE reader,
    patched here so no OSM cache is touched.  Production hands the SAME
    water to the bake (``water_cutout``) and to the detector's witness
    (``_tile_water``), so the twins do too (#945: the bake now reads the
    decision record's water-cut region)."""
    monkeypatch.setattr(flat_site_mode, "water_cutout",
                        lambda tile: geometry)
    monkeypatch.setattr(flat_site_mode, "_tile_water",
                        lambda tile: (geometry, None))


def _cell(dem, lat_deg, lon_deg):
    step = 1.0 / (dem.nxdem - 1)
    return dem.alt_dem[int(round((1.0 - lat_deg) / step)),
                       int(round(lon_deg / step))]


# ── the ruling ──────────────────────────────────────────────────────────

def test_water_inside_the_flat_bbox_keeps_the_base_dem(monkeypatch):
    wire_airport(monkeypatch)
    _wire_water(monkeypatch, CANAL)
    dem = flat_dem(1.0, n=3601)
    tile = make_tile(dem)

    got = substitutions(tile)
    assert len(got) == 1 and got[0]["z0_m"] == pytest.approx(3.96)
    INSETS.overlay_flat_site_insets(tile, dico())

    # DRY ground inside the bbox took Z0 ...
    assert _cell(dem, ANCHOR[0] + 0.002, ANCHOR[1]) == pytest.approx(3.96,
                                                                     abs=1e-3)
    # ... and the canal did NOT: it keeps the base surface.
    assert _cell(dem, ANCHOR[0] - 0.003, ANCHOR[1]) == pytest.approx(1.0,
                                                                     abs=1e-3)
    entry = dem.synthetic_flat_site_provenance[0]
    assert entry["water_cut_frac"] > 0.0


def test_the_shoreline_is_a_step_not_a_ramp(monkeypatch):
    """The mask edge is hard: adjacent posts across the canal's north
    bank read base and Z0, with no intermediate ramp posts."""
    wire_airport(monkeypatch)
    _wire_water(monkeypatch, CANAL)
    dem = flat_dem(1.0, n=3601)
    tile = make_tile(dem)
    substitutions(tile)
    INSETS.overlay_flat_site_insets(tile, dico())

    step = 1.0 / (dem.nxdem - 1)
    col = int(round(ANCHOR[1] / step))
    top = int(round((1.0 - (ANCHOR[0] - 0.0015)) / step))
    bottom = int(round((1.0 - (ANCHOR[0] - 0.0035)) / step))
    column = dem.alt_dem[top:bottom + 1, col]
    between = column[(column > 1.0 + 1e-2) & (column < 3.96 - 1e-2)]
    assert between.size <= 1, "a beach ramp appeared where a wall belongs"


def test_no_water_layer_bakes_the_pre_change_constant_bbox(monkeypatch):
    """An inland airport, or a tile with no cached water: byte-identical
    to the pre-change bake."""
    wire_airport(monkeypatch)
    dem_a = flat_dem(1.0, n=1201)
    _wire_water(monkeypatch, None)
    tile_a = make_tile(dem_a)
    substitutions(tile_a)
    INSETS.overlay_flat_site_insets(tile_a, dico())

    dem_b = flat_dem(1.0, n=1201)
    tile_b = make_tile(dem_b)
    got = substitutions(tile_b)
    x0, y0, x1, y1 = got[0]["extent_deg"]
    INSETS._bake_one_inset(
        tile_b, None, FEATHER_M,
        inset=INSETS._ConstantInset(
            *INSETS._feather_outward_extent(tile_b, x0, y0, x1, y1, FEATHER_M),
            got[0]["z0_m"]))

    assert sha(dem_a.alt_dem) == sha(dem_b.alt_dem)
    assert dem_a.synthetic_flat_site_provenance[0]["water_cut_frac"] == 0.0


def test_water_entirely_outside_the_bbox_changes_nothing(monkeypatch):
    """The cut is a NO-OP where the rectangle holds no water — the same
    constant inset, and the provenance says "measured, none"."""
    wire_airport(monkeypatch)
    far = box(0.90, 0.90, 0.95, 0.95)
    _wire_water(monkeypatch, far)
    dem = flat_dem(1.0, n=1201)
    tile = make_tile(dem)
    substitutions(tile)
    INSETS.overlay_flat_site_insets(tile, dico())
    assert dem.synthetic_flat_site_provenance[0]["water_cut_frac"] == 0.0


def test_a_wholly_submerged_extent_substitutes_nothing(monkeypatch):
    wire_airport(monkeypatch)
    _wire_water(monkeypatch, box(0.0, 0.0, 1.0, 1.0))
    dem = flat_dem(1.0, n=1201)
    tile = make_tile(dem)
    before = sha(dem.alt_dem)
    substitutions(tile)
    INSETS.overlay_flat_site_insets(tile, dico())
    assert sha(dem.alt_dem) == before
    assert not getattr(dem, "synthetic_flat_site_provenance", [])


# ── #945: the airport's OWN pavement over water is land for the cut ────

def test_pavement_over_the_water_takes_z0_and_the_rest_of_the_canal_does_not(
        monkeypatch):
    """VMMC's apron-to-runway taxiways are viaducts over open water.  The
    decision record already keeps the airport's own surfaces as land
    (§37 (11) (4)); the bake cut the RAW water and left a hole in the Z0
    raster under the deck, so the solve read the sea floor there (DEM
    1.76 m under a 6.10 m deck, the paved edges pulled 0.5-1.1 m below
    their centreline)."""
    import dataclasses

    from auto_patch_v2.airport import flat_site_prep as PREP
    from tests.test_flat_site_mode import BOUNDARY, FLAT_THRESHOLDS, site_for

    def with_bridge(icao, root, cifp, law, apt_dat_path=None):
        """The airport plus one taxiway deck crossing the canal."""
        site = site_for(icao.upper(), FLAT_THRESHOLDS, BOUNDARY)
        to_xy, _to_ll = site.frame.transformers()
        deck = ((-0.0005, -0.005), (0.0005, -0.005), (0.0005, 0.001),
                (-0.0005, 0.001))
        bridge = PREP._Poly(tuple(to_xy(ANCHOR[1] + dx, ANCHOR[0] + dy)
                                  for dx, dy in deck), ())
        return dataclasses.replace(site, pavements=(bridge,))

    wire_airport(monkeypatch)
    monkeypatch.setattr(PREP, "site_inputs", with_bridge)
    _wire_water(monkeypatch, CANAL)
    dem = flat_dem(1.0, n=3601)
    tile = make_tile(dem)
    substitutions(tile)
    INSETS.overlay_flat_site_insets(tile, dico())

    # the deck over the canal carries Z0 ...
    assert _cell(dem, ANCHOR[0] - 0.003, ANCHOR[1]) == pytest.approx(3.96,
                                                                     abs=1e-3)
    # ... the open canal beside it keeps the base surface ...
    assert _cell(dem, ANCHOR[0] - 0.003, ANCHOR[1] + 0.003) == pytest.approx(
        1.0, abs=1e-3)
    # ... and dry ground is Z0 as before.
    assert _cell(dem, ANCHOR[0] + 0.002, ANCHOR[1]) == pytest.approx(3.96,
                                                                     abs=1e-3)


def test_water_beside_site_subtracts_the_region_only():
    water = box(0.0, 0.0, 1.0, 0.5)
    record = {"region_ll": [[[[113.4, 22.4], [113.6, 22.4], [113.6, 22.6],
                              [113.4, 22.6]], []]]}
    got = flat_site_mode.water_beside_site(water, record, 22, 113)
    assert not got.intersects(box(0.41, 0.41, 0.49, 0.49))
    assert got.covers(box(0.7, 0.1, 0.8, 0.2))
    assert flat_site_mode.water_beside_site(water, {}, 22, 113) is water
    assert flat_site_mode.water_beside_site(None, record, 22, 113) is None


# ── the reader is cache-only ────────────────────────────────────────────

def test_the_reader_never_downloads_and_answers_none_with_no_cache(tmp_path,
                                                                   monkeypatch):
    """``water_cutout`` goes through ``O4_Vector_Map.cached_tile_water``,
    which reads DISK ONLY — with nothing there the answer is ``None`` and
    the bake is the pre-change bbox."""
    import O4_Vector_Map as VMAP
    import types
    monkeypatch.setattr(VMAP, "cached_tile_water", lambda tile: (None, None))
    tile = types.SimpleNamespace(lat=0, lon=0)
    assert flat_site_mode.water_cutout(tile) is None


def test_the_cutout_unions_sea_and_inland(monkeypatch):
    import O4_Vector_Map as VMAP
    import types
    sea = box(0.0, 0.0, 0.1, 0.1)
    lake = box(0.5, 0.5, 0.6, 0.6)
    monkeypatch.setattr(VMAP, "cached_tile_water", lambda tile: (sea, lake))
    got = flat_site_mode.water_cutout(types.SimpleNamespace(lat=0, lon=0))
    assert got is not None
    assert got.covers(box(0.01, 0.01, 0.02, 0.02))
    assert got.covers(box(0.51, 0.51, 0.52, 0.52))
    assert not got.intersects(box(0.3, 0.3, 0.4, 0.4))


def test_the_masked_inset_keeps_the_rectangle_it_was_given():
    """``bounds=`` pins the data edge: a clipped corner must not move the
    feather (the reason the parameter exists)."""
    rect = (0.4, 0.4, 0.6, 0.6)
    land = box(*rect).difference(box(0.4, 0.4, 0.45, 0.45))
    inset = INSETS._MaskedConstantInset(land, 3.96, 1e-3, 1e-3, bounds=rect)
    assert (inset.x0, inset.y0, inset.x1, inset.y1) == rect
    assert inset.mask_valid_posts > 0
    assert np.any(inset.alt_dem == np.float32(inset.nodata))
