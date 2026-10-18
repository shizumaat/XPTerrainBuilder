# OrthoStudio XP, Copyright (C) 2026 radioharris. Free software under the GNU GPL: see LICENSE.
# Additional terms (GPL v3 section 7) apply to radioharris's material in this file: see NOTICE.
# Origin: OrthoStudio XP (github.com/radioharris/orthostudio-xp), tests/test_textures_encode.py
#   and tests/test_textures_dds.py @ 7c028d82dcc59a27296972973aa0663ef37efddc;
#   LICENSE/NOTICE: THIRD_PARTY/orthostudio-xp/.
# Modified for XPTerrainBuilder, 2026-10-17: imports O4_DDS_Encode / O4_DDS_File; the
#   nvcompress-chain tests are dropped with the fallback; the header tests read the header
#   through O4_DDS_File.expected_size / is_whole (the one parser X-Plane-bound files meet);
#   the O4_DDS_ENCODER flag and the convert-site wiring are tested here.
"""The in-process DDS encoder: header and sizes, round trips, invariants, flag, wiring."""

from __future__ import annotations

import os
import struct

import numpy as np
import pytest

import O4_DDS_Encode as encode
import O4_DDS_File as dds
import O4_Imagery_Utils as IMG
from O4_DDS_Decode import decode_blocks, decode_dds
from O4_DDS_Refine import refine_blocks

needs_ispc = pytest.mark.skipif(not encode.ispc_available(), reason="needs ispc_texcomp")

# 128-byte header of the Ortho4XP reference texture 5952_8416_BI14.dds (DXT1, 4096², 13 mips).
REF_DXT1_HEADER = (
    bytes.fromhex("444453207c00000007100a00001000000010000000008000000000000d000000")
    + bytes(28) + b"UVER" + bytes(4) + b"NVTT" + bytes([0, 1, 2, 0])
    + (32).to_bytes(4, "little") + (4).to_bytes(4, "little") + b"DXT1" + bytes(20)
    + (0x401008).to_bytes(4, "little") + bytes(16)
)
REF_DXT5_HEADER = REF_DXT1_HEADER.replace(b"DXT1", b"DXT5").replace(
    (8388608).to_bytes(4, "little"), (16777216).to_bytes(4, "little")
)


def _zero_reserved1(header: bytes) -> bytes:
    return header[:32] + bytes(44) + header[76:]


def _size(w: int, h: int, fmt: str, mips: bool = True) -> int:
    count = dds.full_mip_count(w, h) if mips else 1
    return dds.HEADER_BYTES + sum(dds.level_size(a, b, fmt) for a, b in dds.mip_dims(w, h, count))


def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse == 0 else 10 * np.log10(255.0**2 / mse)


def _gradient(n: int = 64) -> np.ndarray:
    img = np.zeros((n, n, 4), np.uint8)
    ramp = np.linspace(0, 255, n).astype(np.uint8)
    img[:, :, 0] = ramp[None, :]
    img[:, :, 1] = ramp[:, None]
    img[:, :, 2] = 128
    img[:, :, 3] = np.random.default_rng(0).integers(0, 256, (n, n))
    return img


# -- the header writer (merged into O4_DDS_File) --------------------------------------------

def test_sizes_of_a_4096_texture() -> None:
    assert dds.full_mip_count(4096, 4096) == 13
    assert _size(4096, 4096, "bc1") == 11_184_952
    assert _size(4096, 4096, "bc3") == 22_369_776
    assert dds.level_size(4096, 4096, "bc1") == 8_388_608
    assert dds.level_size(4096, 4096, "bc3") == 16_777_216


def test_small_and_partial_blocks() -> None:
    assert dds.level_size(1, 1, "bc1") == 8
    assert dds.level_size(2, 2, "bc3") == 16
    assert dds.level_size(6, 6, "bc1") == 4 * 8
    assert _size(64, 64, "bc1") == 2872  # matches nvcompress on a 64x64 input
    assert dds.mip_dims(8, 2, dds.full_mip_count(8, 2)) == [(8, 2), (4, 1), (2, 1), (1, 1)]
    assert dds.full_mip_count(1, 1) == 1


def test_header_matches_reference_except_writer_tag() -> None:
    assert len(REF_DXT1_HEADER) == 128
    built = dds.build_header(4096, 4096, "bc1", 13)
    assert len(built) == dds.HEADER_BYTES
    assert built == _zero_reserved1(REF_DXT1_HEADER)
    assert dds.build_header(4096, 4096, "bc3", 13) == _zero_reserved1(REF_DXT5_HEADER)


@pytest.mark.parametrize("w,h,fmt,count", [(4096, 4096, "bc1", 13), (4096, 4096, "bc3", 13),
                                           (256, 128, "bc1", 1), (64, 64, "bc3", 7)])
def test_written_header_is_sized_by_the_reader(w, h, fmt, count) -> None:
    """Twin: the reader that guards X-Plane-bound textures (``expected_size`` / ``is_whole``,
    #600) sizes the written header to exactly the bytes ``assemble`` writes."""
    header = dds.build_header(w, h, fmt, count)
    levels = [bytes(dds.level_size(a, b, fmt)) for a, b in dds.mip_dims(w, h, count)]
    assert dds.expected_size(header) == len(dds.assemble(w, h, fmt, levels))
    assert dds.expected_size(REF_DXT1_HEADER) == 11_184_952


def test_assemble_and_split_round_trip() -> None:
    levels = [bytes([k]) * dds.level_size(w, h, "bc3")
              for k, (w, h) in enumerate(dds.mip_dims(8, 8, 4))]
    data = dds.assemble(8, 8, "bc3", levels)
    assert len(data) == _size(8, 8, "bc3")
    (w, h, fmt), parts = dds.split_levels(data)
    assert (w, h, fmt, len(parts)) == (8, 8, "bc3", 4)
    assert [bytes(p) for p in parts] == levels


def test_header_errors() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        dds.build_header(4, 4, "bc7", 1)
    with pytest.raises(ValueError, match="mip_count"):
        dds.build_header(4, 4, "bc1", 5)
    with pytest.raises(ValueError, match="expected"):
        dds.assemble(4, 4, "bc1", [b"\0" * 7])
    with pytest.raises(ValueError, match="not a DXT1/DXT5"):
        dds.split_levels(b"XXXX" + bytes(124))
    with pytest.raises(ValueError, match="truncated"):
        dds.split_levels(dds.build_header(4, 4, "bc1", 1) + b"\0" * 4)


# -- the encoder ---------------------------------------------------------------------------

@needs_ispc
@pytest.mark.parametrize("fmt", ["bc1", "bc3"])
def test_round_trip_synthetic(fmt: str, tmp_path) -> None:
    img = _gradient()
    data = encode.encode_dds(img, fmt)
    assert len(data) == _size(64, 64, fmt)
    levels = decode_dds(data)
    assert len(levels) == 7 and levels[-1].shape == (1, 1, 4)
    assert _psnr(levels[0][:, :, :3], img[:, :, :3]) > 33
    if fmt == "bc3":
        assert _psnr(levels[0][:, :, 3], img[:, :, 3]) > 28
    else:
        assert np.all(levels[0][:, :, 3] == 255)
    # what X-Plane reads off disk: a whole DDS by the #600 reader
    path = tmp_path / "t.dds"
    path.write_bytes(data)
    assert dds.is_whole(str(path))
    path.write_bytes(data[:-1])
    assert not dds.is_whole(str(path))


@needs_ispc
def test_no_mips_and_rgb_input() -> None:
    data = encode.encode_dds(_gradient()[:, :, :3], "bc1", mips=False)
    assert len(data) == _size(64, 64, "bc1", mips=False)
    assert len(dds.split_levels(data)[1]) == 1


@needs_ispc
def test_tiny_levels_are_padded_to_a_block() -> None:
    img = np.zeros((2, 2, 4), np.uint8)
    img[:, :, 0] = 200
    img[:, :, 3] = 255
    data = encode.encode_dds(img, "bc1")
    assert len(data) == 128 + 8 + 8
    levels = decode_dds(data)
    assert levels[0].shape == (2, 2, 4) and abs(int(levels[0][0, 0, 0]) - 200) <= 8
    assert len(encode.encode_level(np.zeros((6, 6, 4), np.uint8), "bc3")) == 4 * 16


@needs_ispc
def test_deterministic() -> None:
    img = _gradient()
    assert encode.encode_dds(img, "bc3") == encode.encode_dds(img, "bc3")


@needs_ispc
def test_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        encode.encode_dds(_gradient(), "bc7")
    with pytest.raises(ValueError, match="uint8"):
        encode.encode_dds(_gradient().astype(np.uint16), "bc1")
    with pytest.raises(ValueError, match="power-of-two"):
        encode.encode_dds(np.zeros((12, 12, 4), np.uint8), "bc1")


@needs_ispc
def test_force_four_colour_mode() -> None:
    good = struct.pack("<HHI", 0xF800, 0x001F, 0xE4E4E4E4)  # c0 > c1, indices 0,1,2,3 repeated
    inverted = struct.pack("<HHI", 0x001F, 0xF800, 0xE4E4E4E4 ^ 0x55555555)
    assert encode.count_three_colour_blocks(inverted, "bc1") == (1, 0)
    fixed = encode.force_four_colour_mode(inverted, "bc1")
    assert fixed == good
    assert np.array_equal(decode_blocks(fixed, 4, 4, "bc1"), decode_blocks(good, 4, 4, "bc1"))
    equal = struct.pack("<HHI", 0x1234, 0x1234, 0xAAAAAAAA)
    assert encode.count_three_colour_blocks(equal, "bc1") == (0, 1)
    assert encode.force_four_colour_mode(equal, "bc1") == struct.pack("<HHI", 0x1234, 0x1234, 0)
    alpha = bytes(8)  # BC3: the colour block is the second half
    assert encode.force_four_colour_mode(alpha + inverted, "bc3") == alpha + good
    assert encode.count_three_colour_blocks(encode.encode_level(_gradient(), "bc1"), "bc1") == (0, 0)


@needs_ispc
def test_refine_never_increases_error() -> None:
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (64, 64, 4), np.uint8)
    img[:, :, 3] = 255
    base = encode.encode_level(img, "bc1")
    refined = refine_blocks(base, img, "bc1", passes=2)
    assert len(refined) == len(base)
    err = [np.sum((decode_blocks(b, 64, 64, "bc1")[:, :, :3].astype(float) - img[:, :, :3]) ** 2)
           for b in (base, refined)]
    assert err[1] <= err[0]
    assert encode.count_three_colour_blocks(refined, "bc1") == (0, 0)
    assert refine_blocks(base, img, "bc1", passes=0) == base
    via_api = encode.encode_dds(img, "bc3", mips=False, refine_passes=1)
    assert len(via_api) == _size(64, 64, "bc3", mips=False)


def test_single_colour_tables_are_within_one_code() -> None:
    for bits in (5, 6):
        e0, e1 = (t.astype(int) for t in encode._single_colour_table(bits))
        x0 = (e0 << (8 - bits)) | (e0 >> (2 * bits - 8))
        x1 = (e1 << (8 - bits)) | (e1 >> (2 * bits - 8))
        assert np.abs((2 * x0 + x1 + 1) // 3 - np.arange(256)).max() <= 1


@needs_ispc
def test_flat_blocks_use_optimal_endpoints() -> None:
    img = np.empty((8, 8, 4), np.uint8)
    img[:] = (100, 50, 201, 255)
    raw = encode._encode_blocks_ispc(img, "bc1")
    fixed = encode.encode_level(img, "bc1")
    target = np.array((100, 50, 201))
    err_raw = np.abs(decode_blocks(raw, 8, 8, "bc1")[:, :, :3].astype(int) - target).max()
    err_fixed = np.abs(decode_blocks(fixed, 8, 8, "bc1")[:, :, :3].astype(int) - target).max()
    assert err_fixed <= 1 <= err_raw
    assert encode.count_three_colour_blocks(fixed, "bc1") == (0, 0)
    img[0, 0, 0] = 101  # block 0 is no longer uniform and is left to ispc; blocks 1-3 are fixed
    partial = encode.encode_flat_blocks(raw, img, "bc1")
    assert partial[:8] == raw[:8] and partial[8:] == fixed[8:]
    with pytest.raises(ValueError, match="multiple of 4"):
        encode.encode_flat_blocks(raw, np.zeros((6, 6, 4), np.uint8), "bc1")


@needs_ispc
def test_bc1_over_allocation_is_trimmed() -> None:
    """ispc_texcomp 1.0.1 returns width*height bytes for BC1; only the blocks are kept."""
    assert len(encode._encode_blocks_ispc(_gradient(), "bc1")) == dds.level_size(64, 64, "bc1")


# -- the flag and the convert site ------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, "inproc"), ("", "inproc"), ("tool", "tool"), (" TOOL ", "tool"),
    ("bogus", "inproc"), ("inproc", "inproc"), ("INPROC", "inproc"), (" inprocess ", "inproc")])
def test_flag_chooser(value, expected, monkeypatch) -> None:
    monkeypatch.setattr(encode, "ispc_available", lambda: True)
    env = {} if value is None else {encode.ENCODER_ENV: value}
    assert encode.chosen_encoder(env) == expected


def test_flag_falls_back_to_the_tool_without_the_wheel(monkeypatch) -> None:
    monkeypatch.setattr(encode, "ispc_available", lambda: False)
    assert encode.chosen_encoder({encode.ENCODER_ENV: "inproc"}) == "tool"
    assert encode.chosen_encoder({}) == "tool"


@needs_ispc
def test_convert_site_encodes_in_memory_pixels_and_lands_whole(tmp_path) -> None:
    """The in-process arm of the convert loop: pixels in memory are encoded into the PARTIAL
    name (no temp PNG), which lands whole on the final name (#600)."""
    from PIL import Image

    image = Image.fromarray(_gradient(), "RGBA")
    source = IMG._image_for_converter(image, "unused.png", True, True)
    assert isinstance(source, np.ndarray) and source.shape == (64, 64, 4)
    final = str(tmp_path / "t.dds")
    partial = dds.partial_name(final)
    assert IMG._encode_in_process(source, True, partial, final)
    assert dds.is_whole(final) and not os.path.exists(partial)
    assert dds.split_levels(open(final, "rb").read())[0] == (64, 64, "bc3")


@needs_ispc
def test_the_convert_site_encodes_an_image_file_in_its_own_thread(tmp_path,
                                                                  monkeypatch) -> None:
    """A path (the cached JPEG) is encoded in the calling convert thread: no process pool
    and no subprocess is started (#900: the spawned pool's workers crashed in the frozen
    app)."""
    import concurrent.futures
    import multiprocessing
    import subprocess

    from PIL import Image

    def refuse(*args, **kwargs):
        raise AssertionError("the default encode path started a process")

    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", refuse)
    monkeypatch.setattr(multiprocessing, "Process", refuse)
    monkeypatch.setattr(subprocess, "call", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    src = tmp_path / "t.jpg"
    Image.fromarray(_gradient()[:, :, :3], "RGB").save(src, quality=95)
    out = str(tmp_path / "t.dds")
    assert encode.encode_texture(str(src), "bc1", out) == _size(64, 64, "bc1")
    assert dds.is_whole(out)
    assert not hasattr(encode, "shutdown_pool")
