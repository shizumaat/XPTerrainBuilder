"""A texture on disk is whole or it is absent (#600).

The converter wrote straight onto the texture's final name, so a
converter killed mid-write left a short ``.dds`` there and the next build
took it as present.  The twins use a fake converter (nothing is spawned):

* a conversion that is killed or fails leaves NOTHING under the final
  name; a finished one lands whole and leaves no partial;
* a truncated ``.dds`` on disk is queued to be made again, a whole one is
  kept — the length is read from the file's own header.
"""
from __future__ import annotations

import os
import queue
import struct

import pytest

import O4_DDS_File as DDS
import O4_DSF_Utils as DSF
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Tile_Utils as TILE
from test_dsf_texture_modes import (  # noqa: E402
    _DSFTOOL, _LAND_AND_SEA_TRIS, _LAND_AND_SEA_VERTS, _make_tile,
    _prepare_build_dir, _write_mesh, stub_elevation)  # noqa: F401


def _dds(width=64, height=64, mips=7, fourcc=b"DXT1", bit_count=0):
    """The bytes of a whole DDS file with that header."""
    header = bytearray(DDS.HEADER_BYTES)
    header[:4] = b"DDS "
    struct.pack_into("<IIII", header, 4, 124, 0x1007 | (0x20000 if mips else 0),
                     height, width)
    struct.pack_into("<I", header, 28, mips)
    struct.pack_into("<II4sI", header, 76, 32, 0x4 if fourcc else 0x40,
                     fourcc or b"\0\0\0\0", bit_count)
    size = DDS.expected_size(bytes(header))
    return bytes(header) + b"\x55" * (size - DDS.HEADER_BYTES)


# ── the length a header declares ────────────────────────────────────────
@pytest.mark.parametrize("kwargs, pixels", [
    # 4096 px DXT1, 13 levels: 8 bytes x (4^0 + ... + 4^10 blocks, + the
    # 2 px and 1 px levels at one block each) -- DDSTool's own output size
    (dict(width=4096, height=4096, mips=13), 11184824),
    (dict(width=256, height=256, mips=9, fourcc=b"DXT5"), 87408),
    (dict(width=64, height=32, mips=0), 8 * 16 * 8),
    (dict(width=5, height=3, mips=0, fourcc=b"", bit_count=24), 15 * 3),
])
def test_the_header_says_how_long_the_file_is(kwargs, pixels):
    assert len(_dds(**kwargs)) == DDS.HEADER_BYTES + pixels


def test_a_header_this_module_cannot_size_is_not_guessed():
    header = bytearray(_dds()[:DDS.HEADER_BYTES])
    header[84:88] = b"XXXX"
    assert DDS.expected_size(bytes(header)) is None
    assert DDS.expected_size(b"not a dds file") is None


def test_whole_truncated_empty_and_foreign_files(tmp_path):
    whole = _dds()
    cases = {"whole.dds": (whole, True),
             "one_byte_short.dds": (whole[:-1], False),
             "half.dds": (whole[:len(whole) // 2], False),
             "header_only.dds": (whole[:DDS.HEADER_BYTES], False),
             "empty.dds": (b"", False),
             "not_dds.dds": (b"\x89PNG" + whole[4:], False)}
    for (name, (data, expected)) in cases.items():
        (tmp_path / name).write_bytes(data)
        assert DDS.is_whole(str(tmp_path / name)) is expected, name
    assert DDS.is_whole(str(tmp_path / "absent.dds")) is False


def test_a_partial_name_is_beside_the_texture_and_is_not_a_texture(tmp_path):
    final = str(tmp_path / "100_200_BI16.dds")
    partial = DDS.partial_name(final)
    assert os.path.dirname(partial) == os.path.dirname(final)
    assert partial.endswith(".dds") and partial != DDS.partial_name(final)
    assert DDS.is_partial_name(os.path.basename(partial))
    assert not DDS.is_partial_name("100_200_BI16.dds")


def test_landing_refuses_a_short_partial_and_keeps_the_texture(tmp_path):
    final = str(tmp_path / "100_200_BI16.dds")
    previous = _dds(fourcc=b"DXT5")
    with open(final, "wb") as handle:
        handle.write(previous)
    partial = DDS.partial_name(final)
    with open(partial, "wb") as handle:
        handle.write(_dds()[:500])

    assert DDS.land(partial, final) is False

    assert not os.path.exists(partial)
    with open(final, "rb") as handle:
        assert handle.read() == previous


# ── the conversion ──────────────────────────────────────────────────────
ATTRIBUTES = (100, 200, 16, "BI")


@pytest.fixture
def conversion(tmp_path, monkeypatch):
    """A tile whose texture needs nothing but the converter; returns
    (tile, the texture's final path). These tests drive the subprocess
    converter, so they pin it (the in-process encoder is the default)."""
    monkeypatch.setenv("O4_DDS_ENCODER", "tool")
    tile = type("Tile", (), {})()
    (tile.lat, tile.lon) = (50, 10)
    tile.build_dir = str(tmp_path / "build")
    tile.imprint_masks_to_dds = False
    os.makedirs(os.path.join(tile.build_dir, "textures"))
    monkeypatch.setitem(IMG.providers_dict, "BI",
                        {"code": "BI", "color_filters": "none",
                         "imagery_dir": "normal"})
    monkeypatch.setattr(IMG, "color_harmonization_field_for_texture",
                        lambda *args: None)
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setattr(IMG.time, "sleep", lambda seconds: None)
    final = os.path.join(tile.build_dir, "textures",
                         FNAMES.dds_file_name_from_attributes(*ATTRIBUTES))
    return tile, final


def _converter(monkeypatch, behaviour):
    """Fake converter: ``behaviour(output_path)`` returns its exit code."""
    outputs = []

    def call(command, **kwargs):
        outputs.append(command[-1])
        return behaviour(command[-1])

    monkeypatch.setattr(IMG.subprocess, "call", call)
    return outputs


def _write_part(fraction):
    def behaviour(path):
        data = _dds()
        with open(path, "wb") as handle:
            handle.write(data[:int(len(data) * fraction)])
        return 0 if fraction == 1 else -15
    return behaviour


def _textures(tile):
    return sorted(os.listdir(os.path.join(tile.build_dir, "textures")))


def test_a_finished_conversion_lands_whole(conversion, monkeypatch):
    (tile, final) = conversion
    outputs = _converter(monkeypatch, _write_part(1))

    IMG.convert_texture(tile, *ATTRIBUTES)

    assert _textures(tile) == [os.path.basename(final)]
    assert DDS.is_whole(final)
    assert outputs != [final] and len(outputs) == 1
    assert os.path.dirname(outputs[0]) == os.path.dirname(final)


def test_a_converter_killed_mid_write_leaves_nothing_under_the_final_name(
        conversion, monkeypatch):
    (tile, final) = conversion
    outputs = _converter(monkeypatch, _write_part(0.5))

    IMG.convert_texture(tile, *ATTRIBUTES)

    assert len(outputs) == 10                      # the converter's ten tries
    assert _textures(tile) == []


def test_a_converter_that_exits_zero_on_a_short_file_is_not_believed(
        conversion, monkeypatch):
    (tile, final) = conversion

    def short_but_zero(path):
        _write_part(0.5)(path)
        return 0

    _converter(monkeypatch, short_but_zero)

    IMG.convert_texture(tile, *ATTRIBUTES)

    assert _textures(tile) == []


def test_a_killed_build_leaves_a_partial_that_is_not_a_texture_and_is_swept(
        conversion, monkeypatch):
    """The ENGINE dies while the converter writes: what is left is under
    the partial name — no texture to any reader — and the next build's
    conversion of that texture removes it."""
    (tile, final) = conversion

    class Killed(BaseException):
        pass

    def dies(path):
        _write_part(0.5)(path)
        raise Killed()

    _converter(monkeypatch, dies)
    with pytest.raises(Killed):
        IMG.convert_texture(tile, *ATTRIBUTES)

    (left,) = _textures(tile)
    assert DDS.is_partial_name(left) and not os.path.exists(final)
    assert TILE._count_dds_textures(tile) == 0

    _converter(monkeypatch, _write_part(1))
    IMG.convert_texture(tile, *ATTRIBUTES)

    assert _textures(tile) == [os.path.basename(final)]
    assert DDS.is_whole(final)


# ── the "already on disk" test ──────────────────────────────────────────
@_DSFTOOL
def test_a_truncated_texture_is_queued_again_and_a_whole_one_is_kept(
        tmp_path, stub_elevation):
    build_dir = _prepare_build_dir(tmp_path)
    _write_mesh(build_dir, _LAND_AND_SEA_VERTS, _LAND_AND_SEA_TRIS)
    tile = _make_tile(build_dir, "full_ortho")

    def queued():
        download_queue = queue.Queue()
        assert DSF.build_dsf(tile, download_queue) == 1
        found = set()
        while not download_queue.empty():
            found.add(download_queue.get())
        return found

    wanted = queued()
    assert wanted
    paths = {attributes: os.path.join(
        build_dir, "textures",
        FNAMES.dds_file_name_from_attributes(*attributes))
        for attributes in wanted}
    for path in paths.values():
        with open(path, "wb") as handle:
            handle.write(_dds())
    assert queued() == set()

    (cut, cut_path) = sorted(paths.items())[0]
    with open(cut_path, "wb") as handle:
        handle.write(_dds()[:-4096])
    assert queued() == {cut}
