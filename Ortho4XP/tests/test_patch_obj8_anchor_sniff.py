"""OBJ8 patch-object anchor sniff (``O4_Vector_Map._read_obj8_anchor``).

``include_patches`` walks every SUBDIRECTORY of a tile's patch dir and reads
the first line of EVERY file in it looking for an ANCHOR.  Those are ordinary
folders on disk, so they contain non-OBJ8 files: a macOS ``.DS_Store`` is
binary and used to abort the whole tile build with

    UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80 in position 3131

(real case: Patches/+20+050/+25+051/NOAH/.DS_Store, killing the +25+051
build).  An undecodable file must be skipped exactly like a file whose first
line lacks ANCHOR.  Headless, tmp_path-based, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402


def _alt_lookup(lon, lat):
    """Stand-in for ``tile.dem.alt`` — only the 3-value form uses it."""
    return 100.0


# ── the crash class ──────────────────────────────────────────────────


def test_binary_file_is_skipped_without_exception(tmp_path):
    # 0x80 early in the stream: undecodable as UTF-8 on the FIRST line.
    junk = tmp_path / ".DS_Store"
    junk.write_bytes(b"\x00\x00\x01Bud1\x80\x81\x82\x83 no newline here")
    assert VMAP._read_obj8_anchor(str(junk), _alt_lookup) is None


def test_binary_file_with_late_undecodable_byte_is_skipped(tmp_path):
    # Decodable ASCII prefix, no newline for a long while, then 0x80: the
    # readline() call still has to swallow the decode error.
    junk = tmp_path / "blob.bin"
    junk.write_bytes(b"ANCHOR " + b"A" * 4096 + b"\x80\x81 tail")
    assert VMAP._read_obj8_anchor(str(junk), _alt_lookup) is None


# ── the valid forms still parse ──────────────────────────────────────


def test_four_value_anchor_parses(tmp_path):
    obj = tmp_path / "shape.obj"
    obj.write_text("ANCHOR 31.403444 30.128508 74.5 180.0\nVT 0 0 0\n")
    assert VMAP._read_obj8_anchor(str(obj), _alt_lookup) == (
        31.403444,
        30.128508,
        74.5,
        180.0,
    )


def test_three_value_anchor_takes_altitude_from_the_dem(tmp_path):
    obj = tmp_path / "shape.obj"
    obj.write_text("ANCHOR 31.403444 30.128508 180.0\nVT 0 0 0\n")
    assert VMAP._read_obj8_anchor(str(obj), _alt_lookup) == (
        31.403444,
        30.128508,
        100.0,
        180.0,
    )


def test_three_value_anchor_skips_when_the_dem_lookup_fails(tmp_path):
    def boom(lon, lat):
        raise ValueError("outside the tile")

    obj = tmp_path / "shape.obj"
    obj.write_text("ANCHOR 31.403444 30.128508 180.0\n")
    assert VMAP._read_obj8_anchor(str(obj), boom) is None


# ── the pre-existing skip classes are unchanged ──────────────────────


def test_first_line_without_anchor_is_skipped(tmp_path):
    obj = tmp_path / "notes.txt"
    obj.write_text("just some text\nANCHOR 1 2 3 4\n")
    assert VMAP._read_obj8_anchor(str(obj), _alt_lookup) is None


def test_malformed_anchor_is_skipped(tmp_path):
    obj = tmp_path / "shape.obj"
    obj.write_text("ANCHOR nope nope nope\n")
    assert VMAP._read_obj8_anchor(str(obj), _alt_lookup) is None


def test_empty_file_is_skipped(tmp_path):
    obj = tmp_path / "empty.obj"
    obj.write_bytes(b"")
    assert VMAP._read_obj8_anchor(str(obj), _alt_lookup) is None


def test_unopenable_path_is_skipped(tmp_path):
    # A directory inside the object dir: open() raises, the sniff skips it.
    sub = tmp_path / "subdir"
    sub.mkdir()
    assert VMAP._read_obj8_anchor(str(sub), _alt_lookup) is None
    assert VMAP._read_obj8_anchor(str(tmp_path / "absent.obj"), _alt_lookup) is None
