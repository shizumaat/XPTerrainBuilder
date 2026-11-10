"""Twins for the placeholder build mode (#1992, local-imagery-cache spec
§3 and §14 P1a): ``O4_Imagery_Placeholder``, ``O4_DDS_Tiers`` and their
wiring into the imagery and scenery-file steps.

* a tier cut from a DDS is that DDS's own levels, byte for byte;
* with ``imagery_on_demand`` on, a texture's imagery is the same square
  ``placeholder_zl_drop`` zooms coarser (4 map requests at the default),
  converted — mask imprint and colour field included — into a whole
  512 px DDS under the full texture's name, kept in the placeholder store
  (a hard link) and never in the content-keyed DDS cache;
* the colour field is solved once from the placeholders and a second
  pass reuses it without rewriting the file;
* the DSF and the ``.ter`` files are the full build's byte for byte;
* the two settings are step-4 inputs only: toggling them stales no
  reusable step; the imagery manifest records the mode.

Network-free: the provider is a stub whose tile fetch is replaced.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import types

import numpy
import pytest
from PIL import Image

import O4_Cfg_Vars as CFGVARS
import O4_DDS_Cache as DDSCACHE
import O4_DDS_Encode as DDSENC
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_File_Names as FNAMES
import O4_Imagery_Placeholder as PLACEHOLDER
import O4_Imagery_Utils as IMG
import O4_Step_Reuse as REUSE
import O4_Tile_Utils as TILE

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools",
                                "fixtures"))
import make_mesh_dsf_fixture as FIX  # noqa: E402

PROVIDER = "FAKEPH"
ZL = 16
#: a ZL16 texture's top-left map tile (multiples of 16, as build_dsf names them)
TEXTURE = (35552, 18752)


def _dds(path, width, fmt="bc1", seed=0):
    """A whole ``width`` px DDS encoded from deterministic pixels."""
    rng = numpy.random.default_rng(seed)
    pixels = rng.integers(0, 255, (width, width, 3), dtype=numpy.uint8)
    DDSENC.encode_texture(pixels, fmt, str(path))
    return path


# --- O4_DDS_Tiers ---------------------------------------------------------


def test_a_tier_is_the_full_textures_own_levels(tmp_path):
    full = _dds(tmp_path / "full.dds", 1024)
    data = full.read_bytes()
    (_w, _h, fmt), levels = DDS.split_levels(data)
    tier = TIERS.tier_from_dds(data, 256)
    (w, h, tier_fmt), tier_levels = DDS.split_levels(tier)
    assert (w, h, tier_fmt) == (256, 256, fmt)
    assert [bytes(v) for v in tier_levels] == [bytes(v) for v in levels[2:]]
    final = tmp_path / "tier.dds"
    final.write_bytes(TIERS.tier_from_dds(data, 512))
    assert DDS.is_whole(str(final))
    assert TIERS.texture_header(str(final)) == (512, "bc1")
    with pytest.raises(ValueError):
        TIERS.tier_from_dds(data, 300)


def test_tier_ladder():
    assert [TIERS.tier_width(d) for d in TIERS.TIER_DROPS] == [512, 1024,
                                                              2048, 4096]
    assert TIERS.tier_zoom(16, 3) == 13
    with pytest.raises(ValueError):
        TIERS.tier_width(4)


def test_is_dxt5_reads_the_header(tmp_path):
    assert TIERS.is_dxt5(str(_dds(tmp_path / "a.dds", 64, "bc3")))
    assert not TIERS.is_dxt5(str(_dds(tmp_path / "b.dds", 64, "bc1")))


# --- O4_Imagery_Placeholder -----------------------------------------------


def _tile(build_dir, **over):
    values = dict(lat=60, lon=-136, build_dir=str(build_dir), mask_zl=14,
                  default_zl=ZL, default_website=PROVIDER,
                  texture_mode="full_ortho", imagery_on_demand=True,
                  placeholder_zl_drop=3, imprint_masks_to_dds=False,
                  sea_nodata_fill=False, color_harmonization=False)
    values.update(over)
    return types.SimpleNamespace(**values)


def test_drop_follows_the_mode(tmp_path):
    assert PLACEHOLDER.drop(_tile(tmp_path)) == 3
    assert PLACEHOLDER.drop(_tile(tmp_path, placeholder_zl_drop=2)) == 2
    assert PLACEHOLDER.drop(_tile(tmp_path, placeholder_zl_drop=4)) == 3
    assert PLACEHOLDER.drop(_tile(tmp_path, imagery_on_demand=False)) == 0
    assert PLACEHOLDER.drop(
        _tile(tmp_path, texture_mode="default_xplane")) == 0
    assert PLACEHOLDER.drop(types.SimpleNamespace()) == 0


def test_the_cfg_registry_refuses_a_256_px_placeholder():
    assert CFGVARS.cfg_vars["placeholder_zl_drop"]["values"] == (2, 3)
    assert CFGVARS.cfg_vars["placeholder_zl_drop"]["default"] == 3
    assert CFGVARS.cfg_vars["imagery_on_demand"]["default"] is False


def test_tilbox_and_names():
    assert PLACEHOLDER.tilbox(32, 48, 3) == [4, 6, 6, 8]
    assert PLACEHOLDER.tilbox(32, 48, 0) == [32, 48, 48, 64]
    with pytest.raises(ValueError):
        PLACEHOLDER.tilbox(36, 48, 3)
    name = PLACEHOLDER.jpeg_name(128, 128, 16, "Arc", 3)
    # never the name of a ZL13 texture of a build at ZL13 (16, 16)
    assert name == "128_128_Arc16_low13.jpg"
    assert name != FNAMES.jpeg_file_name_from_attributes(16, 16, 13, "Arc")


def test_needs_build_by_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp_path / "data" / relative))
    on, off = _tile(tmp_path), _tile(tmp_path, imagery_on_demand=False)
    missing = str(tmp_path / "none.dds")
    assert PLACEHOLDER.needs_build(on, missing)
    assert PLACEHOLDER.needs_build(off, missing)
    small = str(_dds(tmp_path / "small.dds", 512))
    # #1992 P2: a placeholder with no kept copy is made again (a downgrade
    # needs the copy; "Update Imagery" drops it to refresh the placeholder)
    assert PLACEHOLDER.needs_build(on, small)
    assert PLACEHOLDER.keep(on, small)
    assert not PLACEHOLDER.needs_build(on, small)
    assert PLACEHOLDER.needs_build(off, small)      # back to full: rebuilt
    finer = str(_dds(tmp_path / "finer.dds", 1024))
    assert not PLACEHOLDER.needs_build(on, finer)   # a landed tier stays
    short = tmp_path / "short.dds"
    short.write_bytes(open(small, "rb").read()[:1000])
    assert PLACEHOLDER.needs_build(on, str(short))


# --- download + convert, network-free --------------------------------------


@pytest.fixture()
def placeholder_build(monkeypatch, tmp_path):
    """A stub webmercator provider whose tile fetch paints the box it was
    asked for; JPEG and store folders under tmp_path; the DDS cache must
    never be written."""
    provider = {"code": PROVIDER, "grid_type": "webmercator",
                "imagery_dir": "normal", "color_filters": "none"}
    monkeypatch.setitem(IMG.providers_dict, PROVIDER, provider)
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp_path / "data" / relative))
    calls = []

    def fake_tilbox(tilbox, zoomlevel, provider_, progress=None):
        calls.append((list(tilbox), zoomlevel))
        side = 256 * (tilbox[2] - tilbox[0])
        image = Image.new("RGB", (side, side), (90, 120, 60))
        image.paste((200, 30, 30), (0, 0, side // 2, side // 2))
        return True, image

    monkeypatch.setattr(IMG, "build_texture_from_tilbox", fake_tilbox)

    def no_store(key, dds_final):
        raise AssertionError("a placeholder entered the DDS cache")

    monkeypatch.setattr(DDSCACHE, "store", no_store)
    build_dir = tmp_path / "build"
    (build_dir / "textures").mkdir(parents=True)
    return _tile(build_dir), calls, tmp_path


def test_a_placeholder_is_a_whole_512_px_texture_kept_in_the_store(
        placeholder_build):
    tile, calls, tmp_path = placeholder_build
    attrs = (*TEXTURE, ZL, PROVIDER)
    assert IMG.build_jpeg_ortho(tile, *attrs) == 1
    x13, y13 = TEXTURE[0] // 8, TEXTURE[1] // 8
    assert calls == [([x13, y13, x13 + 2, y13 + 2], 13)]   # 4 map tiles
    folder, name = IMG._source_jpeg_location(tile, *attrs)
    assert folder.endswith(PROVIDER + "_13")
    with Image.open(os.path.join(folder, name)) as jpeg:
        assert jpeg.size == (512, 512)
    # A second build finds the JPEG: no request.
    assert IMG.build_jpeg_ortho(tile, *attrs) == 1
    assert len(calls) == 1

    IMG.convert_texture(tile, *attrs)
    final = os.path.join(tile.build_dir, "textures",
                         FNAMES.dds_file_name_from_attributes(*attrs))
    assert DDS.is_whole(final)
    assert TIERS.texture_header(final) == (512, "bc1")
    kept = PLACEHOLDER.kept_path(tile, os.path.basename(final))
    assert os.path.samefile(kept, final)
    assert not PLACEHOLDER.needs_build(tile, final)


def test_mask_imprint_on_a_placeholder(placeholder_build):
    tile, _calls, _tmp = placeholder_build
    tile.imprint_masks_to_dds = True
    attrs = (*TEXTURE, ZL, PROVIDER)
    mask = os.path.join(tile.build_dir, "textures", FNAMES.mask_file(*attrs))
    Image.new("L", (4096, 4096), 255).save(mask)
    assert IMG.build_jpeg_ortho(tile, *attrs) == 1
    IMG.convert_texture(tile, *attrs)
    final = os.path.join(tile.build_dir, "textures",
                         FNAMES.dds_file_name_from_attributes(*attrs))
    assert TIERS.texture_header(final) == (512, "bc3")
    assert TIERS.is_dxt5(final)


def test_colour_field_is_solved_from_placeholders_and_then_frozen(
        placeholder_build, monkeypatch):
    tile, _calls, tmp_path = placeholder_build
    tile.color_harmonization = True
    import O4_Mask_Utils as MASK
    masks = tmp_path / "Masks"
    masks.mkdir()
    monkeypatch.setattr(MASK.FNAMES, "mask_dir", lambda lat, lon: str(masks))
    keys = [(TEXTURE[0] + 16 * j, TEXTURE[1]) for j in range(3)]

    def one_pass():
        IMG.initialize_color_harmonization(tile)
        for x, y in keys:
            assert IMG.build_jpeg_ortho(tile, x, y, ZL, PROVIDER) == 1
            IMG.collect_color_statistics_for_harmonization(
                tile, x, y, ZL, PROVIDER)
        IMG.solve_color_field(tile)

    one_pass()
    assert len(tile.color_harmonization_statistics) == 3
    field = IMG.color_field_path(tile)
    written = os.stat(field).st_mtime_ns
    one_pass()
    assert tile.color_field_reused is True
    assert os.stat(field).st_mtime_ns == written


# --- the scenery-file step and the step inputs -----------------------------


def _dsf_and_terrain(work, on_demand, monkeypatch):
    """``build_dsf`` on the committed fixture mesh in full_ortho mode;
    ``(dsf bytes, {terrain file: bytes}, queued textures)``."""
    os.makedirs(work)
    shutil.copyfile(os.path.join(FIX.FIXTURE_DIR, FIX.MESH_OUTPUT),
                    os.path.join(work, FIX.MESH_OUTPUT))
    base = FIX.mesh_tile

    def tile_in_mode(directory):
        tile = base(directory)
        tile.imagery_on_demand = on_demand
        tile.placeholder_zl_drop = 3
        return tile

    monkeypatch.setattr(FIX, "mesh_tile", tile_in_mode)
    monkeypatch.setattr(FIX.DSF.TILELOG, "creation_agent",
                        lambda: FIX.FIXTURE_CREATION_AGENT)
    data = FIX.run_dsf_stage(work, "full_ortho")
    build_dir = os.path.join(work, "build_full_ortho")
    terrain = {}
    for root, _dirs, files in os.walk(build_dir):
        for name in files:
            path = os.path.join(root, name)
            if name.endswith((".ter", ".png", ".pol")):
                terrain[os.path.relpath(path, build_dir)] = open(
                    path, "rb").read()
    return data, terrain


def test_dsf_terrain_and_masks_are_the_full_builds(tmp_path, monkeypatch):
    full, full_ter = _dsf_and_terrain(str(tmp_path / "off"), False,
                                      monkeypatch)
    low, low_ter = _dsf_and_terrain(str(tmp_path / "on"), True, monkeypatch)
    assert low == full
    assert low_ter == full_ter and full_ter
    manifest = FIX.read_manifest()
    import hashlib
    assert hashlib.sha256(low).hexdigest() == FIX.expected_sha256(
        manifest, "full_ortho.dsf")


def test_the_mode_is_a_step_4_input_only():
    for name in ("imagery_on_demand", "placeholder_zl_drop"):
        assert name in CFGVARS.list_dsf_vars
        for step in REUSE.REUSABLE_STEPS:
            assert name not in REUSE._step_settings(step), (name, step)


def test_the_imagery_manifest_records_the_mode(tmp_path):
    (tmp_path / "textures").mkdir()
    tile = _tile(tmp_path)
    TILE._write_imagery_manifest(tile, {"done": 1}, {"done": 1})
    manifest = json.loads(open(TILE.imagery_manifest_path(tile), encoding="utf-8").read())
    assert manifest["on_demand"] is True
    assert manifest["placeholder_zl"] == 13
    assert manifest["pinned"] is False
    off = _tile(tmp_path, imagery_on_demand=False)
    TILE._write_imagery_manifest(off, {"done": 1}, {"done": 1})
    manifest = json.loads(open(TILE.imagery_manifest_path(off), encoding="utf-8").read())
    assert manifest["on_demand"] is False and manifest["placeholder_zl"] is None
