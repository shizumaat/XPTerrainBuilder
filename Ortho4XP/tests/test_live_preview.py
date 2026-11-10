"""The map's "Live flight preview" (#2001): the engine reads ONE small mip
of each installed texture square and lists the squares of a viewport.

Synthetic textures only: every mip level is filled with its own flat
colour, so a level read at the wrong offset shows the wrong colour, and a
file cut short after the level read proves the rest is never read.
"""
from __future__ import annotations

import base64
import io
import os

import O4_DDS_File as DDS
import O4_Geo_Utils as GEO
import O4_Imagery_OnDemand_Index as INDEX
import O4_Live_Preview as LIVE
import O4_World_Pack as WP
import pytest
from o4_engine import events as EV
from o4_engine import live_preview_commands as CMD


def _colour(level: int) -> tuple:
    """Level ``level``'s 5:6:5 colour (red steps, blue full) as RGB."""
    r5 = 2 * level + 1
    return ((r5 << 3) | (r5 >> 2), 0, 255)


def _bc1_block(level: int) -> bytes:
    c0 = ((2 * level + 1) << 11) | 0x1F
    return c0.to_bytes(2, "little") + b"\0\0" + b"\0\0\0\0"


def _block(level: int, fmt: str, alpha: int) -> bytes:
    if fmt == "bc1":
        return _bc1_block(level)
    return bytes([alpha, 0]) + b"\0" * 6 + _bc1_block(level)


def _dds(width: int, height: int, fmt: str = "bc1", alpha: int = 255) -> bytes:
    count = DDS.full_mip_count(width, height)
    levels = []
    for k, (w, h) in enumerate(DDS.mip_dims(width, height, count)):
        blocks = DDS.level_size(w, h, fmt) // DDS.BLOCK_FORMATS[fmt][1]
        levels.append(_block(k, fmt, alpha) * blocks)
    return DDS.assemble(width, height, fmt, levels)


def _write(path, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return str(path)


def _decoded(mip: dict):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(mip["data"])))


# ─── the mip read ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("fmt", ["bc1", "bc3"])
def test_the_level_offsets_add_up(fmt):
    data = _dds(1024, 512, fmt)
    (_dims, levels) = DDS.split_levels(data)
    view = memoryview(data)
    for k, level in enumerate(levels):
        off = DDS.level_offset(1024, 512, fmt, k)
        assert bytes(view[off:off + len(level)]) == bytes(level)
    assert DDS.parse_header(data) == (1024, 512, fmt, 11)


@pytest.mark.parametrize("fmt", ["bc1", "bc3"])
def test_the_256_level_is_read_and_nothing_after_it(tmp_path, fmt):
    data = _dds(4096, 4096, fmt)
    end = DDS.level_offset(4096, 4096, fmt, 5)       # the 256 px level ends here
    path = _write(tmp_path / "t.dds", data[:end])     # the rest cut away
    with pytest.raises(ValueError):
        DDS.split_levels(data[:end])                  # a whole-file read fails
    w, h, got_fmt, blocks = DDS.read_level(path, 256)
    assert (w, h, got_fmt) == (256, 256, fmt)
    from O4_DDS_Decode import decode_blocks
    rgba = decode_blocks(blocks, w, h, fmt)
    assert tuple(rgba[0, 0, :3]) == _colour(4)        # 4096 >> 4


def test_the_level_is_the_finest_that_fits(tmp_path):
    path = _write(tmp_path / "t.dds", _dds(512, 512))
    assert DDS.read_level(path, 4096)[:2] == (512, 512)
    assert DDS.read_level(path, 300)[:2] == (256, 256)
    assert DDS.read_level(path, 64)[:2] == (64, 64)
    single = _write(tmp_path / "one.dds", DDS.assemble(
        64, 64, "bc1", [_bc1_block(0) * 256]))
    assert DDS.read_level(single, 32)[:2] == (64, 64)   # the coarsest it has


def test_a_short_or_foreign_file_is_refused(tmp_path):
    data = _dds(1024, 1024)
    short = _write(tmp_path / "short.dds", data[:DDS.level_offset(1024, 1024, "bc1", 2) + 10])
    with pytest.raises(ValueError):
        DDS.read_level(short, 256)
    foreign = _write(tmp_path / "x.dds", b"PNG not a texture" * 20)
    with pytest.raises(ValueError):
        DDS.read_level(foreign, 256)
    with pytest.raises(ValueError):
        LIVE.mip_image(str(tmp_path / "x.png"))


def test_an_opaque_square_is_a_jpeg_and_a_masked_one_a_png(tmp_path):
    opaque = _write(tmp_path / "a.dds", _dds(1024, 1024, "bc1"))
    mip = LIVE.mip_image(opaque, 256)
    assert (mip["width"], mip["height"], mip["format"]) == (256, 256, "jpeg")
    r, g, b = _decoded(mip).convert("RGB").getpixel((128, 128))
    want = _colour(2)
    assert abs(r - want[0]) < 8 and g < 8 and b > 245
    masked = _write(tmp_path / "m.dds", _dds(1024, 1024, "bc3", alpha=100))
    mip = LIVE.mip_image(masked, 128)
    assert (mip["width"], mip["format"]) == (128, "png")
    assert _decoded(mip).getpixel((5, 5))[3] == 100
    assert len(base64.b64decode(LIVE.mip_image(opaque, 256)["data"])) < 40_000


# ─── the squares ───────────────────────────────────────────────────────────
def test_a_texture_name_is_its_slippy_square():
    sq = LIVE.parse_texture("21216_21712_BI16.dds")
    north, west = GEO.gtile_to_wgs84(21712, 21216, 16)
    south, east = GEO.gtile_to_wgs84(21712 + 16, 21216 + 16, 16)
    assert sq["zl"] == 16 and sq["provider"] == "BI"
    for key, value in (("north", north), ("west", west), ("south", south),
                       ("east", east)):
        assert sq[key] == pytest.approx(value, abs=1e-9)
    assert LIVE.parse_texture("21216_21712_BI16_sea_overlay.dds") is None
    assert LIVE.parse_texture("21216_21712_BI16.ter") is None


def _tile_textures(folder, lat=53, lon=-61, zl=16, names=None) -> list:
    """Every square of tile (lat, lon) at ``zl`` (or ``names``), each a
    tiny texture."""
    x0, y0 = GEO.wgs84_to_gtile(lat + 1, lon, zl)
    x1, y1 = GEO.wgs84_to_gtile(lat, lon + 1, zl)
    names = names or ["%d_%d_BI%d.dds" % (y, x, zl)
                      for y in range(y0 // 16 * 16, y1 + 1, 16)
                      for x in range(x0 // 16 * 16, x1 + 1, 16)]
    tiny = _dds(64, 64)
    for name in names:
        _write(os.path.join(folder, name), tiny)
    return names


def test_squares_are_capped_by_zoom_and_count_nearest_first(tmp_path):
    folder = str(tmp_path / "tex")
    names = _tile_textures(folder)
    assert len(names) > LIVE.MAX_SQUARES
    def folders(lat, lon):
        return [folder] if (lat, lon) == (53, -61) else []
    far = LIVE.squares(53, -61, 54, -60, 50, folders)       # 0.09° = 4 px
    assert far == {"squares": [], "capped": False, "reason": "zoom"}
    near = LIVE.squares(53, -61, 54, -60, 3000, folders)
    assert near["capped"] and len(near["squares"]) == LIVE.MAX_SQUARES
    assert {s["px"] for s in near["squares"]} == {256}
    centre = [((s["north"] + s["south"]) / 2 - 53.5) ** 2
              + ((s["west"] + s["east"]) / 2 + 60.5) ** 2 for s in near["squares"]]
    assert centre == sorted(centre)
    mid = LIVE.squares(53.4, -60.6, 53.6, -60.4, 600, folders)
    assert not mid["capped"] and {s["px"] for s in mid["squares"]} == {64}
    assert all(s["east"] >= -60.6 and s["west"] <= -60.4 for s in mid["squares"])


def test_the_first_folder_wins_and_partials_are_skipped(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    name = "21216_21712_BI16.dds"
    _tile_textures(a, names=[name])
    _tile_textures(b, names=[name, "21216_21728_BI16.dds"])
    _write(os.path.join(b, DDS.partial_name(os.path.join(b, "21216_21744_BI16.dds"))
                        .rsplit(os.sep, 1)[-1]), b"x")
    got = LIVE.squares(53, -61, 54, -60, 3000, lambda la, lo: LIVE.existing_dirs([a, b, a]))
    paths = {s["key"].split("/")[1]: s["path"] for s in got["squares"]}
    assert sorted(paths) == [name, "21216_21728_BI16.dds"]
    assert paths[name] == os.path.join(a, name)


def test_a_landed_tier_changes_the_stamp(tmp_path):
    folder = str(tmp_path / "t")
    name = _tile_textures(folder, names=["21216_21712_BI16.dds"])[0]
    def listed():
        return LIVE.squares(53, -61, 54, -60, 3000, lambda la, lo: [folder])["squares"][0]
    before = listed()["stamp"]
    path = os.path.join(folder, name)
    _write(path, _dds(256, 256))                     # a finer tier lands
    os.utime(path, ns=(1, os.stat(path).st_mtime_ns + 5_000_000_000))
    assert listed()["stamp"] != before


# ─── the commands ──────────────────────────────────────────────────────────
def test_folders_are_where_x_plane_reads_them(tmp_path):
    scenery = tmp_path / "Custom Scenery"
    tile = WP.tile_name(53, -61)
    own = scenery / ("zOrtho4XP_" + tile) / "textures"
    world = scenery / WP.PACK_NAME / "textures" / tile
    ondemand = tmp_path / "Tiles" / ("zOrtho4XP_" + tile) / "textures"
    for folder in (own, world, ondemand):
        folder.mkdir(parents=True)
    conn = INDEX.open_index(str(tmp_path / "index.sqlite"))
    INDEX.upsert(conn, {"tile": tile, "name": "21216_21712_BI16.dds",
                        "build_dir": str(ondemand.parent)})
    folders = CMD.tile_folders(str(scenery), conn)(53, -61)
    assert folders == [str(ondemand), str(world), str(own)]
    assert CMD.tile_folders(str(scenery), None)(53, -61) == [str(world), str(own)]
    assert CMD.tile_folders("", None)(53, -61) == []


def test_the_commands_answer_end_to_end(tmp_path, monkeypatch):
    scenery = tmp_path / "cs"
    folder = scenery / ("zOrtho4XP_" + WP.tile_name(53, -61)) / "textures"
    _tile_textures(str(folder), names=["21216_21712_BI16.dds"])
    monkeypatch.setattr(INDEX, "index_path", lambda *a: str(tmp_path / "none.sqlite"))
    reply = CMD.live_preview_squares(53.3, -60.8, 53.5, -60.6, 2000,
                                     scenery_dir=str(scenery))
    (square,) = reply["squares"]
    assert not os.path.exists(tmp_path / "none.sqlite")   # never created
    mip = CMD.live_preview_mip(square["path"], square["px"])
    assert mip["format"] == "jpeg" and mip["width"] == 64


def test_the_mac_apps_fixture_is_the_engines_reply(tmp_path):
    """``fixtures/live_preview_reply.json`` (decoded by the Mac app's
    ``LivePreviewWireTests``) carries the fields the engine replies, and
    the Mac app keeps as many images as the rule says."""
    import json
    from pathlib import Path
    here = Path(__file__).resolve().parent
    fixture = json.loads((here / "fixtures" / "live_preview_reply.json")
                         .read_text(encoding="utf-8"))
    folder = str(tmp_path / "t")
    _tile_textures(folder, names=["21216_21712_BI16.dds"])
    reply = LIVE.squares(53, -61, 54, -60, 3000, lambda la, lo: [folder])
    assert set(fixture) == set(reply)
    assert set(fixture["squares"][0]) == set(reply["squares"][0])
    swift = (here.parents[1] / "Sources" / "SceneryKit" / "LivePreviewWire.swift"
             ).read_text(encoding="utf-8")
    assert "public static var limit: Int { %d }" % LIVE.APP_CACHE_IMAGES in swift


def test_the_commands_are_in_the_table_and_the_hello():
    import inspect

    from o4_engine import jsonl
    assert "**live_preview_handlers()" in inspect.getsource(jsonl._build_handlers)
    assert set(CMD.live_preview_handlers()) == {"live_preview_squares",
                                                "live_preview_mip"}
    assert "live_preview" in EV.CAPABILITIES
