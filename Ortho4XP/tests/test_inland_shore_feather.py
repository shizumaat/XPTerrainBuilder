"""Inland shore feather (2026-07-17).

Inland water used to be clamped fully opaque in the masks and blended
at one constant alpha in the DSF — razor shorelines on every lagoon and
lake.  The feather: mask pixels over inland water ease from opaque at
the land shoreline down to the constant ``ratio_water`` grey, FLOORED
at that grey (no deep-water transparency can ever appear inside mapped
water), and inland-water terrains whose square carries a mask blend
through it like the masked sea overlay.

Headless: synthetic arrays for the compositor, a stub tile writing a
real ``.ter`` for the border routing.
"""

from __future__ import annotations

import os
import sys

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_DSF_Utils as DSF  # noqa: E402
import O4_Mask_Utils as MASK  # noqa: E402

GREY = 200


def _scene(size=96, margin=16):
    """Land block left, inland water middle, sea right; a blurred fade
    standing in for blur_mask output (values only matter over sea)."""
    pre_mask = numpy.zeros((size, size), dtype=numpy.uint8)
    pre_mask[:, : size // 3] = 255              # land
    pre_mask[:, size // 3: 2 * size // 3] = GREY  # inland water
    blured = numpy.full((size, size), 40, dtype=numpy.uint8)  # sea fade
    return (pre_mask, blured, margin)


class TestComposeWaterMask:
    def test_land_is_opaque_and_sea_keeps_the_fade(self):
        (pre_mask, blured, margin) = _scene()
        composed = MASK.compose_water_mask(
            pre_mask, blured, GREY, feather_pixels=8, crop_margin=margin)
        crop = slice(margin, pre_mask.shape[0] - margin)
        land = (pre_mask == 255)[crop, crop]
        sea = (pre_mask == 0)[crop, crop]
        assert (composed[land] == 255).all()
        assert (composed[sea] == 40).all()

    def test_inland_feathers_from_shore_down_to_grey(self):
        (pre_mask, blured, margin) = _scene()
        composed = MASK.compose_water_mask(
            pre_mask, blured, GREY, feather_pixels=8, crop_margin=margin)
        row = composed[32]
        inland_start = 96 // 3 - margin        # first inland column
        inland_end = 2 * 96 // 3 - margin
        shore_value = row[inland_start]
        deep_inland_value = row[inland_end - 4]
        assert shore_value > GREY + 30          # near-opaque at the shore
        assert deep_inland_value == GREY        # settled at the constant
        # Monotone easing between the two.
        segment = row[inland_start:inland_end - 4].astype(int)
        assert (numpy.diff(segment) <= 0).all()

    def test_inland_never_below_the_grey_floor(self):
        (pre_mask, blured, margin) = _scene()
        blured[:] = 0                            # worst case: full fade
        composed = MASK.compose_water_mask(
            pre_mask, blured, GREY, feather_pixels=8, crop_margin=margin)
        crop = slice(margin, pre_mask.shape[0] - margin)
        inland = ((pre_mask > 0) & (pre_mask != 255))[crop, crop]
        assert composed[inland].min() >= GREY

    def test_zero_feather_restores_the_hard_clamp(self):
        (pre_mask, blured, margin) = _scene()
        composed = MASK.compose_water_mask(
            pre_mask, blured, GREY, feather_pixels=0, crop_margin=margin)
        crop = slice(margin, pre_mask.shape[0] - margin)
        inland = ((pre_mask > 0) & (pre_mask != 255))[crop, crop]
        assert (composed[inland] == 255).all()


class _TerrainTile:
    def __init__(self, build_dir):
        self.build_dir = str(build_dir)
        self.imprint_masks_to_dds = False
        self.use_decal_on_terrain = False
        self.terrain_casts_shadows = True
        self.mask_zl = 16


class TestInlandTerrainBorder:
    def _terrain_text(self, tmp_path, mask_border):
        tile = _TerrainTile(tmp_path)
        os.makedirs(os.path.join(str(tmp_path), "textures"), exist_ok=True)
        name = DSF.create_terrain_file(
            tile, "24000_31000_Arc16.dds", 24000, 31000, 16, "Arc",
            1, True, mask_border=mask_border)
        with open(os.path.join(str(tmp_path), "terrain", name), encoding="utf-8") as ter:
            return ter.read()

    def test_mask_border_references_the_tile_mask(self, tmp_path):
        import O4_File_Names as FNAMES

        text = self._terrain_text(tmp_path, mask_border=True)
        assert "water_transition.png" not in text
        mask_name = FNAMES.mask_file(24000, 31000, 16, "Arc")
        assert "BORDER_TEX ../textures/" + mask_name in text

    def test_default_keeps_the_constant_blend(self, tmp_path):
        text = self._terrain_text(tmp_path, mask_border=False)
        assert "water_transition.png" in text


# ---------------------------------------------------------------------------
# Far-inland water (#1981): a lake with no sea anywhere near still gets
# its shore feathered — the masks step used to build masks only for
# squares the sea reached, so every far-inland shoreline stayed hard.
# ---------------------------------------------------------------------------
def _lake(size=96, margin=16):
    """A round lake in the middle of land, no sea anywhere."""
    pre_mask = numpy.full((size, size), 255, dtype=numpy.uint8)
    yy, xx = numpy.mgrid[0:size, 0:size]
    lake = (yy - size / 2) ** 2 + (xx - size / 2) ** 2 < (size / 4) ** 2
    pre_mask[lake] = GREY
    return (pre_mask, lake, margin)


class TestInlandShoreMask:
    def test_lake_far_from_sea_is_feathered_and_floored(self):
        (pre_mask, lake, margin) = _lake()
        mask = MASK._build_inland_shore_mask(
            pre_mask, GREY, feather_pixels=6, crop_margin=margin)
        assert mask is not None
        crop = slice(margin, pre_mask.shape[0] - margin)
        water = lake[crop, crop]
        assert (mask[~water] == 255).all()        # land stays opaque
        assert mask[water].min() == GREY          # settles at the grey
        assert mask[water].min() >= GREY          # never below it
        assert mask[water].max() > GREY + 30      # soft at the shore
        centre = mask.shape[0] // 2
        assert mask[centre, centre] == GREY

    def test_square_with_no_water_builds_nothing(self):
        pre_mask = numpy.full((96, 96), 255, dtype=numpy.uint8)
        assert MASK._build_inland_shore_mask(
            pre_mask, GREY, feather_pixels=6, crop_margin=16) is None

    def test_square_inside_a_lake_keeps_the_constant_blend(self):
        pre_mask = numpy.full((96, 96), GREY, dtype=numpy.uint8)
        assert MASK._build_inland_shore_mask(
            pre_mask, GREY, feather_pixels=6, crop_margin=16) is None

    def test_zero_feather_builds_nothing(self):
        (pre_mask, _lake_px, margin) = _lake()
        assert MASK._build_inland_shore_mask(
            pre_mask, GREY, feather_pixels=0, crop_margin=margin) is None


class _LakeTile:
    """Every attribute the masks step reads; a far-inland tile."""

    def __init__(self, build_dir, feather_m=120.0):
        self.lat, self.lon = 64, -148
        self.build_dir = str(build_dir)
        self.grouped = True
        self.mask_zl = 14
        self.use_masks_for_inland = False
        self.inland_shore_feather_m = feather_m
        self.ratio_water = 0.3
        self.masks_custom_extent = ""
        self.masks_use_DEM_too = "False"
        self.custom_dem = ""
        self.fill_nodata = ""
        self.masking_mode = "sand"
        self.masks_width = 100.0
        self.distance_masks_too = False
        self.coastal_foam_edge = True   # must NOT foam an inland lake


def _write_lake_mesh(tile):
    """One lake triangle (tag 1, inland water) ~2 km across at the
    tile centre, plus land filler; no sea triangle anywhere."""
    import O4_File_Names as FNAMES

    lat, lon = tile.lat + 0.5, tile.lon + 0.43
    vertices = [(lon, lat), (lon + 0.04, lat), (lon + 0.02, lat + 0.015)]
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices", "3"]
    for (v_lon, v_lat) in vertices:
        lines.append("%.9f %.9f 0.000000000 0" % (v_lon, v_lat))
    lines += ["", "Normals", "3"] + ["0.00 0.00 0"] * 3
    triangles = ["1 2 3 1"] + ["1 1 1 0"] * 150
    lines += ["", "Triangles", str(len(triangles))] + triangles
    mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    os.makedirs(os.path.dirname(mesh_path), exist_ok=True)
    with open(mesh_path, "w", encoding="utf-8", newline="") as mesh:
        mesh.write("\n".join(lines) + "\n")


@pytest.fixture
def data_root(tmp_path):
    import O4_File_Names as FNAMES
    import O4_UI_Utils as UI

    original_override = FNAMES._data_root_override
    FNAMES.set_data_root(str(tmp_path))
    UI.is_working = 0
    UI.red_flag = False
    try:
        yield tmp_path
    finally:
        UI.is_working = 0
        FNAMES._data_root_override = original_override
        FNAMES._apply_data_root()


class TestFarInlandSquares:
    def test_lake_square_is_recorded_without_sea(self, data_root):
        tile = _LakeTile(data_root / "build")
        _write_lake_mesh(tile)
        (dico_sea, dico_inland, coastline_sea_present) = (
            MASK.record_water_tris(tile))
        assert dico_sea == {}
        assert not coastline_sea_present
        assert dico_inland                       # the lake's square(s)

    def test_zero_feather_records_no_inland_only_square(self, data_root):
        tile = _LakeTile(data_root / "build", feather_m=0.0)
        _write_lake_mesh(tile)
        (dico_sea, dico_inland, _) = MASK.record_water_tris(tile)
        assert dico_sea == {} and dico_inland == {}

    def test_build_masks_writes_a_feathered_lake_mask(self, data_root):
        import O4_File_Names as FNAMES
        from PIL import Image

        tile = _LakeTile(data_root / "build")
        _write_lake_mesh(tile)
        assert MASK.build_masks(tile) == 1
        mask_dir = FNAMES.mask_dir(tile.lat, tile.lon)
        masks = [name for name in os.listdir(mask_dir)
                 if name.endswith(".png")]
        assert len(masks) == 1                   # the lake's square only
        mask = numpy.array(Image.open(os.path.join(mask_dir, masks[0])))
        water = mask < 255
        assert water.any() and (mask == 255).any()
        grey = int(mask[water].min())
        # Floored at the ratio_water grey, eased up toward the shore, and
        # no coastal foam inside a lake.
        assert grey > MASK.ALL_WATER_MAX
        assert mask[water].max() > grey + 20
        assert numpy.unique(mask[water]).size > 5

    def test_zero_feather_builds_no_mask(self, data_root):
        import O4_File_Names as FNAMES

        tile = _LakeTile(data_root / "build", feather_m=0.0)
        _write_lake_mesh(tile)
        assert MASK.build_masks(tile) == 1
        mask_dir = FNAMES.mask_dir(tile.lat, tile.lon)
        assert not [name for name in os.listdir(mask_dir)
                    if name.endswith(".png")]
