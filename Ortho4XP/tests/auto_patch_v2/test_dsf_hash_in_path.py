"""DSFTool's text reader takes ``#`` as the start of a comment WHEREVER it
stands, so a pack resource path carrying one (CYHM: ``POLYGON_DEF Ground
Textures/RWY#/Arrow.pol``) came back ``Ground Textures/RWY`` on dump ->
encode -> dump and the round-trip verify refused the write.
``dsf_write.encode`` rewrites the cut definition tables (and properties)
from the text's rows verbatim, as it already did for #23's long rows."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf_write as W

DUMP = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n"
        "PROPERTY sim/west -80\nPROPERTY sim/east -79\nPROPERTY sim/north 44\n"
        "PROPERTY sim/south 43\nPROPERTY sim/planet earth\n"
        "PROPERTY sim/creation_agent WED#2\n"
        "OBJECT_DEF objects/plain.obj\n"
        "OBJECT_DEF objects/hangar#2.obj\n"
        "POLYGON_DEF Ground Textures/RWY#/Arrow.pol\n"
        "POLYGON_DEF Ground Textures/plain.pol\n"
        "OBJECT 0 -79.950000000 43.170000000 12.000000\n"
        "OBJECT 1 -79.951000000 43.171000000 90.000000\n"
        "BEGIN_POLYGON 0 65535 4\nBEGIN_WINDING\n"
        "POLYGON_POINT -79.95 43.17 0.0 0.0\n"
        "POLYGON_POINT -79.94 43.17 1.0 0.0\n"
        "POLYGON_POINT -79.94 43.18 1.0 1.0\n"
        "END_WINDING\nEND_POLYGON\n"
        "BEGIN_POLYGON 1 65535 4\nBEGIN_WINDING\n"
        "POLYGON_POINT -79.93 43.17 0.0 0.0\n"
        "POLYGON_POINT -79.92 43.17 1.0 0.0\n"
        "POLYGON_POINT -79.92 43.18 1.0 1.0\n"
        "END_WINDING\nEND_POLYGON\n")


def test_text_defs_keep_the_hash_verbatim():
    got = W._text_defs(DUMP)
    assert got["POLYGON_DEF"] == ["Ground Textures/RWY#/Arrow.pol", "Ground Textures/plain.pol"]
    assert got["OBJECT_DEF"] == ["objects/plain.obj", "objects/hangar#2.obj"]


def _strings(*xs: str) -> bytes:
    return b"".join(x.encode() + b"\0" for x in xs)


def _fake_dsf(polys: bytes) -> bytes:
    kids = [(b"TRET", b""), (b"TJBO", _strings("a.obj")), (b"YLOP", polys),
            (b"WTEN", b""), (b"NMED", b"")]
    defn_body = b"".join(struct.pack("<4sI", k, 8 + len(p)) + p for k, p in kids)
    defn = struct.pack("<4sI", b"NFED", 8 + len(defn_body)) + defn_body
    head = struct.pack("<4sI", b"DAEH", 16) + struct.pack("<4sI", b"PORP", 8)
    tail = struct.pack("<4sI", b"DOEG", 12) + b"geom"
    body = b"XPLNEDSF" + struct.pack("<I", 1) + head + defn + tail
    return body + hashlib.md5(body).digest()


def test_replace_defs_rewrites_only_that_table(tmp_path):
    """Pure-bytes twin (no DSFTool): the POLY table takes the paths, DEFN's
    length follows, every other atom is byte-identical, the MD5 is new."""
    p = tmp_path / "t.dsf"
    p.write_bytes(_fake_dsf(_strings("Ground Textures/RWY")))
    W._replace_defs(str(p), {"POLYGON_DEF": ["Ground Textures/RWY#/Arrow.pol"]})
    assert p.read_bytes() == _fake_dsf(_strings("Ground Textures/RWY#/Arrow.pol"))
    b = p.read_bytes()
    assert hashlib.md5(b[:-16]).digest() == b[-16:]


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_a_hash_in_a_resource_path_survives_the_round_trip(tmp_path):
    tool = _dsftool_path()
    src = tmp_path / "in.text"
    src.write_text(DUMP, encoding="utf-8", newline="")
    # the defect itself: DSFTool alone cuts the path at the '#'
    raw = tmp_path / "raw.dsf"
    W._run([tool, "--text2dsf", str(src), str(raw)])
    back = Path(W.dump(str(raw), str(tmp_path / "raw.text"), tool)).read_text(encoding="utf-8")
    assert W._text_defs(back)["POLYGON_DEF"][0] == "Ground Textures/RWY"
    assert not W.compare_dumps(DUMP, back).ok
    # the fix: encode() restores every definition and property verbatim
    out = W.encode(str(src), str(tmp_path / "out.dsf"), tool)
    again = Path(W.dump(out, str(tmp_path / "out.text"), tool)).read_text(encoding="utf-8")
    assert W._text_defs(again) == W._text_defs(DUMP)
    assert ("sim/creation_agent", "WED#2") in W.text_properties(again)
    rep = W.verify_roundtrip(out, again, tool)
    assert rep.ok, rep.findings
