"""The photo UNDER the water (``water_imagery`` ``under``, RULINGS
2026-11-24f, ``src/O4_Water_Imagery.py``).

Headless: the module's rules on arrays and stub tiles, then one synthetic
tile through ``build_dsf`` (land, a shallow and a deep sea triangle and an
inland triangle in one texture, the mask stubbed) decoded with DSFTool.
"""
import os
import queue
import sys

import numpy
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import O4_DSF_Utils as DSF  # noqa: E402
import O4_Geo_Utils as GEO  # noqa: E402
import O4_Mask_Utils as MASK  # noqa: E402
import O4_Water_Imagery as WATERIMG  # noqa: E402
from test_dsf_texture_modes import (  # noqa: E402
    DECODE, _DSFTOOL, _emitted_dsf, _make_tile, _prepare_build_dir,
    _write_mesh)


def _tile(**kw):
    tile = type("Tile", (), {})()
    tile.water_imagery = "mask"
    tile.water_imagery_alpha = "opaque"
    tile.water_tech = "XP12"
    tile.imprint_masks_to_dds = False
    for (key, value) in kw.items():
        setattr(tile, key, value)
    return tile


class TestArm:
    def test_mask_is_today(self):
        assert not WATERIMG.draws_under(_tile())
        assert not WATERIMG.imprints_alpha(_tile())
        assert WATERIMG.imprints_alpha(_tile(imprint_masks_to_dds=True))

    def test_under_on_xp12_water(self):
        assert WATERIMG.draws_under(_tile(water_imagery="under"))
        assert not WATERIMG.draws_under(
            _tile(water_imagery="under", water_tech="XP11 + bathy"))

    def test_under_alpha_follows_its_own_setting(self):
        opaque = _tile(water_imagery="under", imprint_masks_to_dds=True)
        assert not WATERIMG.imprints_alpha(opaque)
        depth = _tile(water_imagery="under", water_imagery_alpha="depth")
        assert WATERIMG.imprints_alpha(depth)

    def test_a_tile_without_the_settings_is_mask(self):
        assert not WATERIMG.draws_under(type("Tile", (), {})())


class TestTriangleHasImagery:
    def _crop(self):
        crop = numpy.zeros((64, 64), dtype=numpy.uint8)
        crop[:, :16] = 255            # west quarter: land / shallow
        return crop

    def test_a_triangle_over_shallow_water_has_imagery(self):
        st = [(0.05, 0.9), (0.2, 0.9), (0.1, 0.6)]
        assert WATERIMG.triangle_has_imagery(self._crop(), st, 30)

    def test_a_triangle_over_open_water_has_none(self):
        st = [(0.6, 0.9), (0.9, 0.9), (0.8, 0.2)]
        assert not WATERIMG.triangle_has_imagery(self._crop(), st, 30)

    def test_the_floor_is_strict(self):
        crop = numpy.full((8, 8), 30, dtype=numpy.uint8)
        st = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]
        assert not WATERIMG.triangle_has_imagery(crop, st, 30)

    def test_t_runs_up_the_rows(self):
        crop = numpy.zeros((64, 64), dtype=numpy.uint8)
        crop[:8, :] = 255             # the northern rows
        north = [(0.2, 0.99), (0.8, 0.99), (0.5, 0.95)]
        south = [(0.2, 0.01), (0.8, 0.01), (0.5, 0.2)]
        assert WATERIMG.triangle_has_imagery(crop, north, 30)
        assert not WATERIMG.triangle_has_imagery(crop, south, 30)


class TestCoarseMask:
    def test_pooling_keeps_every_maximum(self):
        crop = numpy.zeros((4096, 4096), dtype=numpy.uint8)
        crop[4095, 7] = 200
        coarse = WATERIMG.coarse_mask(crop)
        assert coarse.shape == (WATERIMG.COARSE_MASK_CELLS,) * 2
        assert coarse.max() == 200 and coarse[-1, 0] == 200

    def test_a_small_crop_is_kept(self):
        crop = numpy.arange(16, dtype=numpy.uint8).reshape(4, 4)
        assert WATERIMG.coarse_mask(crop) is crop


# ── one synthetic tile through build_dsf ────────────────────────────────

def _texture_frame():
    """Texture attributes of the zoom-16 square holding (50.5, 10.5) and a
    function mapping its (s, t) to (lon, lat)."""
    (til_x, til_y) = GEO.wgs84_to_orthogrid(50.5, 10.5, 16)
    (lat_n, lon_w) = GEO.gtile_to_wgs84(til_x, til_y, 16)
    (lat_s, lon_e) = GEO.gtile_to_wgs84(til_x + 16, til_y + 16, 16)

    def lonlat(s, t):
        return (lon_w + s * (lon_e - lon_w), lat_s + t * (lat_n - lat_s))
    return (til_x, til_y, 16, "BI"), lonlat


def _scene():
    """Land (west), a shallow sea triangle beside it, a deep one east and
    an inland triangle north-west, all in one texture."""
    attributes, lonlat = _texture_frame()
    corners = [
        ((0.05, 0.10), (0.25, 0.10), (0.15, 0.30), 0),   # land
        ((0.30, 0.10), (0.45, 0.10), (0.38, 0.30), 2),   # shallow sea
        ((0.60, 0.10), (0.90, 0.10), (0.75, 0.40), 2),   # deep sea
        ((0.05, 0.60), (0.25, 0.60), (0.15, 0.90), 1),   # inland water
    ]
    vertices, triangles = [], []
    for (a, b, c, attr) in corners:
        base = len(vertices)
        vertices += [lonlat(*a), lonlat(*b), lonlat(*c)]
        triangles.append((base + 1, base + 2, base + 3, attr))
    return attributes, vertices, triangles


def _mask_crop():
    """Opaque west of s = 0.5 (land and shallows), open water east."""
    crop = numpy.zeros((1024, 1024), dtype=numpy.uint8)
    crop[:, :512] = 255
    return Image.fromarray(crop, "L")


def _build(tmp_path, monkeypatch, **settings):
    attributes, vertices, triangles = _scene()
    build_dir = _prepare_build_dir(tmp_path)
    _write_mesh(build_dir, vertices, triangles)
    monkeypatch.setattr(DSF, "elevation_and_bathymetry_data",
                        lambda tile: (b"", b""))
    monkeypatch.setattr(MASK, "needs_mask",
                        lambda tile, *attrs: _mask_crop())
    tile = _make_tile(build_dir, "full_ortho")
    for (key, value) in settings.items():
        setattr(tile, key, value)
    downloads = queue.Queue()
    assert DSF.build_dsf(tile, downloads) == 1
    terrain_dir = os.path.join(build_dir, "terrain")
    ters = {name: open(os.path.join(terrain_dir, name),
                       encoding="utf-8").read()
            for name in os.listdir(terrain_dir)}
    pngs = [name for name in os.listdir(os.path.join(build_dir, "textures"))
            if name.endswith(".png")]
    return DECODE.decode_dsf(_emitted_dsf(build_dir)), ters, pngs


@_DSFTOOL
def test_mask_lays_overlays_on_plain_water(tmp_path, monkeypatch):
    dump, ters, pngs = _build(tmp_path, monkeypatch)
    assert any(name.endswith("_sea_overlay.ter") for name in ters)
    assert any(name.endswith("_water_overlay.ter") for name in ters)
    assert pngs                                    # the mask PNG
    water = [p for p in dump.patches if p.terrain_path == "terrain_Water"]
    assert water                                   # under the overlays


@_DSFTOOL
@pytest.mark.parametrize("alpha", ["opaque", "depth"])
def test_under_draws_one_physical_floor(tmp_path, monkeypatch, alpha):
    dump, ters, pngs = _build(tmp_path, monkeypatch, water_imagery="under",
                              water_imagery_alpha=alpha)
    assert pngs == []                              # no mask PNG
    assert not any("overlay" in name for name in ters)
    under = {name: text for (name, text) in ters.items()
             if name.endswith(("_sea.ter", "_water.ter"))}
    assert len(under) == 2                         # sea and inland
    for text in under.values():
        assert "WATER_COLOR_MASK" in text and "WET" in text
        assert "BORDER_TEX" not in text
    floors = [p for p in dump.patches
              if p.terrain_path.endswith(("_sea.ter", "_water.ter"))]
    assert floors and all(p.flags == 1 for p in floors)     # physical
    assert all(p.plane_count == 9 for p in floors)
    # Only the deep sea triangle stays plain X-Plane water: one patch of
    # terrain_Water, never one under a floor triangle.
    water = [p for p in dump.patches if p.terrain_path == "terrain_Water"]
    assert len(water) == 1
