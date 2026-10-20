"""The per-texture DDS cache, keyed on content (#839, ``O4_DDS_Cache``).

The gate (spec ``step-reuse-content-keys-spec.md`` §2.5): a texture served
from the cache is byte-identical to the one a fresh conversion makes, and a
build whose ``textures/`` was cleared converts nothing the second time.  The
key holds every input that changes the bytes — the source pixels (after the
colour filter, the harmonization field and the mask), the format, and the
converter (its code, its mip filter, the library versions; or the tool's
binary and flags) — so each of those misses when it changes.

The conversions here are real (a small JPEG through the in-process
encoder) where the bytes are the point, and a fake subprocess converter
where only the routing is.
"""
from __future__ import annotations

import os
import shutil

import numpy
import pytest
from PIL import Image

import O4_DDS_Cache as CACHE
import O4_DDS_Encode as DDSENC
import O4_DDS_File as DDS
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG

needs_ispc = pytest.mark.skipif(not DDSENC.ispc_available(),
                                reason="needs ispc_texcomp")

ATTRIBUTES = (100, 200, 16, "BI")


def _tile(root, name="build"):
    tile = type("Tile", (), {})()
    (tile.lat, tile.lon) = (50, 10)
    tile.build_dir = str(root / name)
    tile.imprint_masks_to_dds = False
    os.makedirs(os.path.join(tile.build_dir, "textures"), exist_ok=True)
    return tile


def _final(tile):
    return os.path.join(tile.build_dir, "textures",
                        FNAMES.dds_file_name_from_attributes(*ATTRIBUTES))


@pytest.fixture
def imagery(tmp_path, monkeypatch):
    """A provider with one 256 px orthophoto on disk; returns its path."""
    monkeypatch.setitem(IMG.providers_dict, "BI",
                        {"code": "BI", "color_filters": "none",
                         "imagery_dir": "normal"})
    monkeypatch.setattr(IMG, "color_harmonization_field_for_texture",
                        lambda *args: None)
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"))
    monkeypatch.setattr(IMG.time, "sleep", lambda seconds: None)
    folder = FNAMES.jpeg_file_dir_from_attributes(
        50, 10, 16, IMG.providers_dict["BI"])
    os.makedirs(folder)
    path = os.path.join(folder, FNAMES.jpeg_file_name_from_attributes(
        *ATTRIBUTES))
    pixels = numpy.random.default_rng(839).integers(
        0, 256, (32, 32, 3), dtype=numpy.uint8)
    Image.fromarray(pixels).resize((256, 256)).save(path, quality=90)
    return path


@pytest.fixture
def encoder(monkeypatch):
    """The real in-process encoder, chosen and counted."""
    monkeypatch.setenv("O4_DDS_ENCODER", "inproc")
    calls = []
    real = DDSENC.encode_texture

    def counted(source, fmt, path):
        calls.append(path)
        return real(source, fmt, path)

    monkeypatch.setattr(IMG.DDSENC, "encode_texture", counted)
    return calls


def _bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _clear(tile):
    shutil.rmtree(os.path.join(tile.build_dir, "textures"))
    os.makedirs(os.path.join(tile.build_dir, "textures"))


def _entries():
    root = CACHE.cache_root()
    return sorted(os.path.join(d, f) for (d, _s, files) in os.walk(root)
                  for f in files if f.endswith(".dds"))


# ── the gate ────────────────────────────────────────────────────────────
@needs_ispc
def test_a_cleared_build_converts_nothing_and_gets_identical_bytes(
        tmp_path, imagery, encoder):
    tile = _tile(tmp_path)
    IMG.convert_texture(tile, *ATTRIBUTES)
    first = _bytes(_final(tile))
    assert len(encoder) == 1 and len(_entries()) == 1

    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)

    assert len(encoder) == 1                     # served, not converted
    assert _bytes(_final(tile)) == first
    assert os.listdir(os.path.join(tile.build_dir, "textures")) == [
        os.path.basename(_final(tile))]          # no partial left behind


@needs_ispc
def test_the_served_texture_is_the_freshly_converted_one(
        tmp_path, imagery, encoder, monkeypatch):
    """Cached vs converted with the cache OFF: the same sha256."""
    monkeypatch.setenv("O4_DDS_CACHE", "0")
    fresh = _tile(tmp_path, "fresh")
    IMG.convert_texture(fresh, *ATTRIBUTES)
    assert _entries() == []                      # off stores nothing

    monkeypatch.delenv("O4_DDS_CACHE")
    warm = _tile(tmp_path, "warm")
    IMG.convert_texture(warm, *ATTRIBUTES)
    neighbour = _tile(tmp_path, "neighbour")
    IMG.convert_texture(neighbour, *ATTRIBUTES)

    assert len(encoder) == 2                     # fresh + warm; neighbour hit
    assert (_bytes(_final(neighbour)) == _bytes(_final(warm))
            == _bytes(_final(fresh)))


@needs_ispc
def test_the_cache_off_converts_every_time(tmp_path, imagery, encoder,
                                           monkeypatch):
    monkeypatch.setenv("O4_DDS_CACHE", "0")
    tile = _tile(tmp_path)
    IMG.convert_texture(tile, *ATTRIBUTES)
    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)
    assert len(encoder) == 2 and _entries() == []


# ── the key: each input that changes the bytes misses ───────────────────
@needs_ispc
def test_a_colour_filter_change_misses(tmp_path, imagery, encoder,
                                       monkeypatch):
    tile = _tile(tmp_path)
    IMG.convert_texture(tile, *ATTRIBUTES)
    plain = _bytes(_final(tile))

    monkeypatch.setitem(IMG.color_filters_dict, "brighter",
                        [["brightness-contrast", 20, 0]])
    monkeypatch.setitem(IMG.providers_dict["BI"], "color_filters", "brighter")
    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)

    assert len(encoder) == 2 and _bytes(_final(tile)) != plain
    assert len(_entries()) == 2


@needs_ispc
def test_a_harmonization_change_misses(tmp_path, imagery, encoder,
                                       monkeypatch):
    tile = _tile(tmp_path)
    field = numpy.zeros((4, 4, 3), dtype=numpy.float32)
    monkeypatch.setattr(IMG, "color_harmonization_field_for_texture",
                        lambda *args: field)
    IMG.convert_texture(tile, *ATTRIBUTES)
    before = _bytes(_final(tile))

    field[:] = 12.0
    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)

    assert len(encoder) == 2 and _bytes(_final(tile)) != before


def test_the_key_separates_format_pixels_and_converter():
    pixels = numpy.zeros((8, 8, 3), dtype=numpy.uint8)
    inproc = "inproc A"
    key = CACHE.texture_key(pixels, "bc1", inproc)
    assert key == CACHE.texture_key(pixels.copy(), "bc1", inproc)
    other = pixels.copy()
    other[3, 3, 1] = 1
    assert CACHE.texture_key(other, "bc1", inproc) != key
    assert CACHE.texture_key(pixels, "bc3", inproc) != key
    assert CACHE.texture_key(pixels, "bc1", "inproc B") != key
    assert CACHE.texture_key(pixels.reshape(4, 16, 3), "bc1", inproc) != key
    assert CACHE.texture_key(pixels, "bc1", None) is None


def test_the_encoder_identity_follows_its_code_and_mip_filter(
        tmp_path, monkeypatch):
    src = os.path.dirname(os.path.abspath(CACHE.__file__))
    copy = tmp_path / "src"
    copy.mkdir()
    for name in CACHE._ENCODER_MODULES:
        shutil.copy(os.path.join(src, name + ".py"), copy / (name + ".py"))
    monkeypatch.setattr(CACHE, "_HERE", str(copy))
    monkeypatch.setattr(CACHE, "_identities", {})
    base = CACHE.converter_identity("inproc")
    assert base is not None and base.startswith("inproc ")

    monkeypatch.setattr(CACHE, "_identities", {})
    with open(copy / "O4_DDS_Mips.py", "a", encoding="utf-8",
              newline="\n") as handle:
        handle.write("\n# a change to the mip chain\n")
    assert CACHE.converter_identity("inproc") != base

    monkeypatch.setattr(CACHE, "_identities", {})
    changed_code = CACHE.converter_identity("inproc")
    monkeypatch.setattr(DDSENC, "DEFAULT_MIP_MODE", "srgb")
    monkeypatch.setattr(CACHE, "_identities", {})
    assert CACHE.converter_identity("inproc") != changed_code


def test_the_tool_identity_follows_its_binary_flags_and_libraries(tmp_path):
    binary = tmp_path / "nvcompress"
    binary.write_bytes(b"v1")
    first = CACHE.converter_identity("tool", str(binary), ("-bc1", "-fast"))
    assert first is not None
    assert CACHE.converter_identity(
        "tool", str(binary), ("-bc3", "-fast")) != first
    (tmp_path / "nvtt.dll").write_bytes(b"lib")
    os.utime(binary, ns=(1, 1))                  # a new stamp: re-read
    with_lib = CACHE.converter_identity("tool", str(binary), ("-bc1", "-fast"))
    assert with_lib != first
    binary.write_bytes(b"v2")
    assert CACHE.converter_identity(
        "tool", str(binary), ("-bc1", "-fast")) != with_lib
    assert CACHE.converter_identity(
        "tool", str(tmp_path / "absent"), ()) is None


def test_the_chosen_encoder_is_in_the_key(tmp_path, imagery, monkeypatch):
    """``O4_DDS_ENCODER`` picks the converter, so it picks the key."""
    binary = tmp_path / "DDSTool"
    binary.write_bytes(b"tool")
    monkeypatch.setattr(IMG, "dds_convert_cmd", str(binary))
    monkeypatch.setattr(IMG.DDSENC, "ispc_available", lambda: True)
    monkeypatch.setenv("O4_DDS_ENCODER", "inproc")
    inproc = IMG._dds_cache_key(imagery, False, True)
    monkeypatch.setenv("O4_DDS_ENCODER", "tool")
    tool = IMG._dds_cache_key(imagery, False, False)
    assert None not in (inproc, tool) and inproc != tool
    monkeypatch.setenv("O4_DDS_CACHE", "0")
    assert IMG._dds_cache_key(imagery, False, False) is None


# ── routing through the subprocess converter ────────────────────────────
def _whole_dds(path, fill=b"\x55"):
    header = DDS.build_header(8, 8, "bc1", 1)
    with open(path, "wb") as handle:
        handle.write(header + fill * (DDS.expected_size(header)
                                      - DDS.HEADER_BYTES))


def _fake_tool(monkeypatch, tmp_path, behaviour):
    binary = tmp_path / "nvcompress"
    binary.write_bytes(b"tool")
    monkeypatch.setattr(IMG, "dds_convert_cmd", str(binary))
    outputs = []

    def call(command, **kwargs):
        outputs.append(command[-1])
        return behaviour(command[-1])

    monkeypatch.setattr(IMG.subprocess, "call", call)
    return outputs


def test_the_tool_path_stores_and_serves(tmp_path, imagery, monkeypatch):
    monkeypatch.setenv("O4_DDS_ENCODER", "tool")
    outputs = _fake_tool(monkeypatch, tmp_path,
                         lambda path: _whole_dds(path) or 0)
    tile = _tile(tmp_path)
    IMG.convert_texture(tile, *ATTRIBUTES)
    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)
    assert len(outputs) == 1 and DDS.is_whole(_final(tile))


def test_a_texture_the_encoder_fails_is_kept_under_the_tools_key(
        tmp_path, imagery, monkeypatch):
    """#900's fallback: the tool made it, so the tool's key holds it — an
    in-process hit must never serve the tool's bytes."""
    monkeypatch.setenv("O4_DDS_ENCODER", "inproc")
    monkeypatch.setattr(IMG.DDSENC, "ispc_available", lambda: True)

    def broken(source, fmt, path):
        raise RuntimeError("encoder died")

    monkeypatch.setattr(IMG.DDSENC, "encode_texture", broken)
    monkeypatch.setattr(IMG.UI, "lvprint", lambda *args: None)
    outputs = _fake_tool(monkeypatch, tmp_path,
                         lambda path: _whole_dds(path) or 0)
    tile = _tile(tmp_path)
    IMG.convert_texture(tile, *ATTRIBUTES)

    (entry,) = _entries()
    assert os.path.basename(entry) == (
        IMG._dds_cache_key(imagery, False, False) + ".dds")
    assert IMG._dds_cache_key(imagery, False, True) + ".dds" != (
        os.path.basename(entry))
    _clear(tile)
    IMG.convert_texture(tile, *ATTRIBUTES)       # encoder fails, tool key hits
    assert len(outputs) == 1


def test_a_failed_conversion_stores_nothing(tmp_path, imagery, monkeypatch):
    monkeypatch.setenv("O4_DDS_ENCODER", "tool")
    monkeypatch.setattr(IMG.UI, "lvprint", lambda *args: None)
    _fake_tool(monkeypatch, tmp_path, lambda path: 1)
    IMG.convert_texture(_tile(tmp_path), *ATTRIBUTES)
    assert _entries() == []


# ── the store ───────────────────────────────────────────────────────────
def test_a_short_entry_is_a_miss_and_is_removed(tmp_path):
    key = "ab" + "0" * 62
    entry = os.path.join(CACHE.cache_root(), "ab", key + ".dds")
    os.makedirs(os.path.dirname(entry))
    _whole_dds(entry)
    with open(entry, "r+b") as handle:
        handle.truncate(100)
    final = str(tmp_path / "t.dds")
    assert CACHE.serve(key, final) is False
    assert not os.path.exists(entry) and not os.path.exists(final)


def test_a_hit_is_a_link_and_touches_the_entry(tmp_path):
    texture = str(tmp_path / "made.dds")
    _whole_dds(texture)
    key = "cd" + "1" * 62
    assert CACHE.store(key, texture)
    (entry,) = _entries()
    os.utime(entry, ns=(10**9, 10**9))
    served = str(tmp_path / "served.dds")
    assert CACHE.serve(key, served)
    assert _bytes(served) == _bytes(texture)
    assert os.stat(entry).st_mtime_ns > 10**9


def test_the_least_recently_used_go_first(tmp_path):
    root = tmp_path / "cache"
    paths = []
    for age in range(4):
        path = root / f"{age:02d}" / f"{age:02d}{'0' * 62}.dds"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x" * 1000)
        os.utime(path, ns=((10 + age) * 10**9,) * 2)
        paths.append(path)
    removed = CACHE.evict(str(root), cap=2500)
    assert sorted(removed) == sorted(str(p) for p in paths[:2])
    assert [p.exists() for p in paths] == [False, False, True, True]


def test_the_cap_defaults_to_twenty_gigabytes():
    assert CACHE.max_bytes({}) == 20 * 10**9
    assert CACHE.max_bytes({"O4_DDS_CACHE_MAX_GB": "1.5"}) == 1_500_000_000
    assert CACHE.max_bytes({"O4_DDS_CACHE_MAX_GB": "junk"}) == 20 * 10**9
    assert CACHE.enabled({}) and not CACHE.enabled({"O4_DDS_CACHE": "0"})


def test_the_suite_cache_is_lane_local():
    assert CACHE.cache_root() == os.environ["O4_DDS_CACHE_DIR"]
    assert not CACHE.cache_root().startswith(FNAMES.data_path(""))
