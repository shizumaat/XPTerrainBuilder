"""Twins for the colour-harmonization v2 ORCHESTRATION (issue #1, GEN-2).

``docs/specs/color-harmonization-spec.md`` §7.  The pure solver has its own
twin (``test_color_harmonization.py``); this file covers what the engine
does around it:

  * statistics are collected from the cached source JPEG on the download
    worker, with LAND taken from the builder's own mask tri-state
    (``O4_Mask_Utils.land_class_for_texture``) — the v1 luminance gate read
    the Gulf as the texture and minted the coast line of issue #1;
  * ``solve_color_field`` groups by (zoomlevel, provider), solves ascending
    so a nested ZL18 zone is conditioned on the ZL16 field around it, and
    PERSISTS ``color_field.json``;
  * a rerun that converts a SUBSET of the textures REUSES that file, so the
    subset matches what was built before (spec §3);
  * the imagery manifest RECORDS what ran — the tile cfg cannot;
  * all-water textures get no correction (spec §4 bar 4).

Headless: providers, JPEG paths and the masks root are monkeypatched, so
the "downloaded" textures are small synthetic JPEGs under ``tmp_path`` and
the "masks" are real PNG squares read through the real tri-state.
"""
from __future__ import annotations

import json
import types

import numpy
import pytest
from PIL import Image

import O4_Color_Harmonization as HARMONIZE
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Tile_Utils as TILE


PROVIDER_CODE = "FAKEPROV"
ZL = 16
STEP = HARMONIZE.GRID_STEP
TEXTURE = 256  # synthetic texture edge (the engine never assumes 4096 here)


@pytest.fixture()
def harmonization_tile(monkeypatch, tmp_path):
    """A minimal tile, a fake provider whose JPEGs live in tmp_path, and a
    masks root the real ``land_class_for_texture`` reads."""
    monkeypatch.setitem(IMG.providers_dict, PROVIDER_CODE, {"code": PROVIDER_CODE})
    monkeypatch.setattr(
        IMG.FNAMES, "jpeg_file_dir_from_attributes",
        lambda lat, lon, zoomlevel, provider: str(tmp_path / "jpegs"),
    )
    monkeypatch.setattr(
        IMG.FNAMES, "jpeg_file_name_from_attributes",
        lambda til_x, til_y, zoomlevel, provider_code: (
            f"{til_y}_{til_x}_{provider_code}{zoomlevel}.jpg"
        ),
    )
    masks = tmp_path / "Masks"
    masks.mkdir()
    monkeypatch.setattr(MASK.FNAMES, "mask_dir", lambda lat, lon: str(masks))
    (tmp_path / "jpegs").mkdir()
    build_dir = tmp_path / "build"
    (build_dir / "textures").mkdir(parents=True)

    tile = types.SimpleNamespace(
        lat=25, lon=51, mask_zl=ZL, color_harmonization=True,
        build_dir=str(build_dir), default_website=PROVIDER_CODE,
        default_zl=ZL, texture_mode="full_ortho",
    )
    IMG.initialize_color_harmonization(tile)

    def write_jpeg(til_x, til_y, grey, zoomlevel=ZL):
        path = tmp_path / "jpegs" / f"{til_y}_{til_x}_{PROVIDER_CODE}{zoomlevel}.jpg"
        Image.fromarray(
            numpy.full((TEXTURE, TEXTURE, 3), grey, numpy.uint8)
        ).save(path, quality=100)
        return path

    def write_mask(til_x, til_y, array):
        """A mask SQUARE at mask_zl, as the builder writes it.  Real squares
        are 4096 px and ``land_class_for_texture`` crops them at that size,
        so the twin upsamples ``array`` to 4096 rather than inventing a
        geometry the engine would never see."""
        Image.fromarray(array, "L").resize((4096, 4096), Image.NEAREST).save(
            masks / f"{til_y}_{til_x}.png"
        )

    return tile, write_jpeg, write_mask, tmp_path


def _collect(tile, keys, zoomlevel=ZL):
    for til_x, til_y in keys:
        IMG.collect_color_statistics_for_harmonization(
            tile, til_x, til_y, zoomlevel, PROVIDER_CODE
        )


def _row(count=3):
    """The keys of a west-to-east row of ``count`` textures."""
    return [(j * STEP, 0) for j in range(count)]


# --- statistics: the tri-state, not a luminance gate ---------------------------


def test_statistics_take_land_from_the_builders_mask_tri_state(
    harmonization_tile,
):
    """Three textures: one with no mask square (all land), one whose square
    is all water (never a witness, land 0), one half land / half feather —
    the feather is NOT land, so its land fraction is 0.5, not 1.0."""
    tile, write_jpeg, write_mask, _ = harmonization_tile
    for column, grey in ((0, 120), (1, 30), (2, 120)):
        write_jpeg(column * STEP, 0, grey)
    write_mask(STEP, 0, numpy.full((64, 64), 5, numpy.uint8))
    half = numpy.full((64, 64), 255, numpy.uint8)
    half[:, 32:] = 200  # feather band: shore, not land
    write_mask(2 * STEP, 0, half)

    _collect(tile, _row())
    stats = tile.color_harmonization_statistics
    assert len(stats) == 3
    assert stats[(0, 0, ZL, PROVIDER_CODE)]["land_class"] == "land"
    assert stats[(0, 0, ZL, PROVIDER_CODE)]["land_fraction"] == pytest.approx(1.0)
    water = stats[(STEP, 0, ZL, PROVIDER_CODE)]
    assert water["land_class"] == "water"
    assert water["land_fraction"] == 0.0 and water["witness"] is False
    feathered = stats[(2 * STEP, 0, ZL, PROVIDER_CODE)]
    assert feathered["land_class"] == "mask"
    assert feathered["land_fraction"] == pytest.approx(0.5, abs=0.01)
    assert feathered["witness"] is True
    # The source JPEG's mtime is recorded — the reuse check depends on it.
    assert stats[(0, 0, ZL, PROVIDER_CODE)]["mtime"] > 0


def test_missing_jpeg_and_unknown_provider_are_skipped(harmonization_tile):
    tile, write_jpeg, _wm, _tmp = harmonization_tile
    write_jpeg(0, 0, 120)
    IMG.collect_color_statistics_for_harmonization(tile, 48, 0, ZL, PROVIDER_CODE)
    IMG.collect_color_statistics_for_harmonization(tile, 0, 0, ZL, "NOT_A_PROVIDER")
    assert tile.color_harmonization_statistics == {}
    IMG.solve_color_field(tile)
    assert tile.color_harmonization_fields == {}
    assert IMG.color_harmonization_field_for_texture(
        tile, 0, 0, ZL, PROVIDER_CODE) is None


# --- the solve, end to end ------------------------------------------------------


def test_solve_pulls_a_dark_texture_toward_its_neighbours_continuously(
    harmonization_tile,
):
    """The issue-#1 case without the coast: a 100-count texture beside two
    140-count ones.  v1 gave each ONE constant and stepped at the seam; v2
    leaves the spec's −28 residual on the measured seam and a step under
    1 count in the APPLIED field."""
    tile, write_jpeg, _wm, _tmp = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    _collect(tile, _row())
    IMG.solve_color_field(tile)

    field = tile.color_harmonization_fields[(ZL, PROVIDER_CODE)]
    left = float(field.offset((0, 0))[0])
    middle = float(field.offset((STEP, 0))[0])
    assert middle - left == pytest.approx(-28.0, abs=0.5)
    assert left > 0 > middle  # the dark one lifts, the bright ones drop

    a = IMG.color_harmonization_field_for_texture(tile, 0, 0, ZL, PROVIDER_CODE)
    b = IMG.color_harmonization_field_for_texture(tile, STEP, 0, ZL, PROVIDER_CODE)
    assert a is not None and b is not None
    assert a.shape == (HARMONIZE.FIELD_SIZE, HARMONIZE.FIELD_SIZE, 3)
    assert numpy.abs(b[:, 0, :] - a[:, -1, :]).max() < 1.0


def test_all_water_texture_is_never_shifted(harmonization_tile):
    """Spec §4 bar 4.  The node still carries a harmonic value so the
    field does not jump across it — but the invisible texture itself gets
    no correction."""
    tile, write_jpeg, write_mask, _tmp = harmonization_tile
    for column, grey in ((0, 100), (1, 30), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    write_mask(STEP, 0, numpy.full((64, 64), 5, numpy.uint8))
    _collect(tile, _row())
    IMG.solve_color_field(tile)
    assert IMG.color_harmonization_field_for_texture(
        tile, STEP, 0, ZL, PROVIDER_CODE) is None
    field = tile.color_harmonization_fields[(ZL, PROVIDER_CODE)]
    node = float(field.offset((STEP, 0))[0])
    ends = (float(field.offset((0, 0))[0]), float(field.offset((2 * STEP, 0))[0]))
    assert min(ends) <= node <= max(ends)


def test_grids_are_separate_per_zoomlevel_and_provider(harmonization_tile):
    """A ZL18 zone inside a ZL16 grid solves as its own grid, conditioned
    on the coarser field (spec §2.5) — not mixed into one system."""
    tile, write_jpeg, _wm, _tmp = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    # Two ZL18 textures inside the ZL16 square at (0, 0): factor 4.
    for column in (0, 1):
        write_jpeg(column * STEP, 0, 150, zoomlevel=18)
    _collect(tile, _row())
    _collect(tile, [(0, 0), (STEP, 0)], zoomlevel=18)
    IMG.solve_color_field(tile)

    assert set(tile.color_harmonization_fields) == {
        (ZL, PROVIDER_CODE), (18, PROVIDER_CODE)}
    fine = tile.color_harmonization_fields[(18, PROVIDER_CODE)]
    assert fine.has((0, 0)) and fine.has((STEP, 0))
    coarse = tile.color_harmonization_fields[(ZL, PROVIDER_CODE)]
    # Spec §2.5: the anchor value is the COARSE field at the fine edge
    # midpoint plus the strength-scaled cast.  The ZL18 pair is 150 and the
    # ZL16 square covering it is 100, so the cast (coarse - fine) is -50 and
    # at ZL18 strength 0.2 the anchor is F16(0,0) - 10.  The ZL18 nodes
    # therefore sit 10 counts BELOW the coarse field they are nested in --
    # they follow it rather than drifting off on their own.
    covering = float(coarse.offset((0, 0))[0])
    assert float(fine.offset((0, 0))[0]) == pytest.approx(covering - 10.0, abs=0.5)
    assert float(fine.offset((STEP, 0))[0]) == pytest.approx(
        covering - 10.0, abs=0.5)
    # The coarse grid is solved FIRST and is untouched by its nested zone.
    assert float(coarse.offset((STEP, 0))[0] - coarse.offset((0, 0))[0]) == (
        pytest.approx(-28.0, abs=0.5))


# --- persistence and the subset rerun ------------------------------------------


def test_field_is_persisted_and_a_subset_rerun_reuses_it(harmonization_tile):
    """Spec §3.  The DSF step queues only textures whose DDS is absent, so
    a repaired-download rerun IS a subset: it must reuse the persisted
    field, not solve a different one from two textures."""
    tile, write_jpeg, _wm, tmp_path = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    _collect(tile, _row())
    IMG.solve_color_field(tile)
    assert tile.color_field_reused is False

    path = tmp_path / "build" / IMG.COLOR_FIELD_FILE
    assert path.is_file()
    record = json.loads(path.read_text())
    assert record["version"] == IMG.COLOR_FIELD_VERSION
    assert record["settings_hash"] == IMG.color_field_settings_hash()
    assert len(record["grids"]) == 1
    grid = record["grids"][0]
    assert grid["zoomlevel"] == ZL and grid["provider"] == PROVIDER_CODE
    assert grid["strength"] == 0.70
    # Two east seams were cast; the first carries the +40 step.
    assert len(grid["seams"]) == 2
    assert grid["seams"][0]["d"][0] == pytest.approx(40.0, abs=0.5)
    assert set(record["textures"]) == {
        f"{j * STEP}_0_{ZL}_{PROVIDER_CODE}" for j in range(3)}

    before = IMG.color_harmonization_field_for_texture(
        tile, 0, 0, ZL, PROVIDER_CODE)

    # The rerun: ONE texture re-downloaded, the other two skipped.
    rerun = types.SimpleNamespace(**vars(tile))
    IMG.initialize_color_harmonization(rerun)
    rerun.build_dir = tile.build_dir
    _collect(rerun, [(0, 0)])
    assert len(rerun.color_harmonization_statistics) == 1
    IMG.solve_color_field(rerun)
    assert rerun.color_field_reused is True
    after = IMG.color_harmonization_field_for_texture(
        rerun, 0, 0, ZL, PROVIDER_CODE)
    assert numpy.abs(after - before).max() < 1e-3
    # The reused field still knows the textures this run never touched.
    assert IMG.color_harmonization_field_for_texture(
        rerun, 2 * STEP, 0, ZL, PROVIDER_CODE) is not None


def test_a_changed_source_jpeg_or_setting_refuses_the_persisted_field(
    harmonization_tile, monkeypatch,
):
    tile, write_jpeg, _wm, tmp_path = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    _collect(tile, _row())
    IMG.solve_color_field(tile)
    record = json.loads(
        (tmp_path / "build" / IMG.COLOR_FIELD_FILE).read_text())

    stats = dict(tile.color_harmonization_statistics)
    assert IMG._persisted_field_covers(record, stats) is True
    # A re-downloaded JPEG (new mtime) invalidates it.
    changed = dict(stats)
    key = (0, 0, ZL, PROVIDER_CODE)
    changed[key] = dict(stats[key], mtime=stats[key]["mtime"] + 10.0)
    assert IMG._persisted_field_covers(record, changed) is False
    # A texture the record never saw invalidates it.
    extra = dict(stats)
    extra[(9 * STEP, 0, ZL, PROVIDER_CODE)] = stats[key]
    assert IMG._persisted_field_covers(record, extra) is False
    # So does a changed solver constant.
    monkeypatch.setattr(HARMONIZE, "SMOOTHNESS_MU", 0.5)
    assert IMG._persisted_field_covers(record, stats) is False


# --- provenance in the manifest ------------------------------------------------


def test_imagery_manifest_records_what_ran(harmonization_tile):
    """Spec §3: the cfg cannot say whether the feature ran (the sparse-cfg
    rule writes only tile-differing keys), so the manifest does."""
    tile, write_jpeg, _wm, tmp_path = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    _collect(tile, _row())
    IMG.solve_color_field(tile)
    tile.color_harmonization_active = True

    TILE._write_imagery_manifest(tile, {"done": 3, "failed": 0}, {"done": 3})
    manifest = json.loads(
        (tmp_path / "build" / TILE.os.path.basename(
            TILE.imagery_manifest_path(tile))).read_text())
    assert manifest["color_harmonization"] is True
    assert manifest["color_field"] == IMG.COLOR_FIELD_FILE
    assert manifest["color_field_reused"] is False
    assert manifest["schema"] == TILE.IMAGERY_MANIFEST_SCHEMA

    # A build with the feature OFF records that, and names no sidecar.
    off = types.SimpleNamespace(**vars(tile))
    off.color_harmonization_active = False
    TILE._write_imagery_manifest(off, {"done": 3, "failed": 0}, {"done": 3})
    manifest = json.loads(
        (tmp_path / "build" / TILE.os.path.basename(
            TILE.imagery_manifest_path(tile))).read_text())
    assert manifest["color_harmonization"] is False
    assert manifest["color_field"] is None


def test_manifest_records_a_reused_field(harmonization_tile):
    tile, write_jpeg, _wm, tmp_path = harmonization_tile
    for column, grey in ((0, 100), (1, 140), (2, 140)):
        write_jpeg(column * STEP, 0, grey)
    _collect(tile, _row())
    IMG.solve_color_field(tile)

    rerun = types.SimpleNamespace(**vars(tile))
    IMG.initialize_color_harmonization(rerun)
    _collect(rerun, [(0, 0)])
    IMG.solve_color_field(rerun)
    rerun.color_harmonization_active = True
    TILE._write_imagery_manifest(rerun, {"done": 1, "failed": 0}, {"done": 1})
    manifest = json.loads(
        (tmp_path / "build" / TILE.os.path.basename(
            TILE.imagery_manifest_path(rerun))).read_text())
    assert manifest["color_harmonization"] is True
    assert manifest["color_field_reused"] is True
