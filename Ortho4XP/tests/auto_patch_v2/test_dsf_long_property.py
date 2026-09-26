"""#23: DSFTool's text reader cuts a line at 511 characters, so a pack's
long ``PROPERTY sim/exclude_net`` polygon (PHNY ``+20-157.dsf``, 596
characters) came back shortened on an UNEDITED dump -> encode -> dump and
the round-trip verify refused the write.  ``dsf_write.encode`` rewrites
the encoded property atom from the text's rows verbatim."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf_write as W


def _poly(n: int) -> str:
    pts = ",".join(f"-156.{960000 + 37 * k:06d}/20.{780000 + 29 * k:06d}"
                   for k in range(n))
    return "-156.990000/20.780000/-156.960000/20.790000;" + pts


LONG_NET = _poly(40)          # ~800 characters: well past the 511 cut
PROPS = [
    ("sim/west", "-157"), ("sim/east", "-156"), ("sim/north", "21"),
    ("sim/south", "20"), ("sim/planet", "earth"),
    ("sim/creation_agent", "WorldEditor 2.5.0r1"),
    ("laminar/internal_revision", "0"), ("sim/overlay", "1"),
    ("sim/filter/aptid", "PHNY"),
    ("sim/exclude_obj", "-156.954480/20.785802/-156.944336/20.792671"),
    ("sim/exclude_fac", "-156.954480/20.785802/-156.944336/20.792671"),
    ("sim/exclude_for", "-156.954480/20.785802/-156.944336/20.792671"),
    ("sim/exclude_bch", "-156.954733/20.795443/-156.952488/20.797436"),
    ("sim/exclude_lin", "-156.954733/20.795443/-156.952488/20.797436"),
    ("sim/exclude_pol", "-156.954733/20.795443/-156.952488/20.797436"),
    ("sim/exclude_str", "-156.954733/20.795443/-156.952488/20.797436"),
    ("sim/exclude_net", LONG_NET),
    ("sim/exclude_net", _poly(6)),
    ("sim/exclude_net", "-156.954534/20.786617/-156.945021/20.797388"),
    ("sim/require_agpoint", "1/0"), ("sim/require_object", "1/0"),
    ("sim/require_facade", "1/82"),
]

DUMP = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n"
        + "".join(f"PROPERTY {n} {v}\n" for n, v in PROPS)
        + "OBJECT_DEF objects/hangar.obj\n"
        "OBJECT_DEF lib/cars/car_static_invar.obj\n"
        "POLYGON_DEF pavement/asphalt.pol\n"
        "OBJECT 0 -156.955000000 20.790000000 12.000000\n"
        "OBJECT_MSL 1 -156.956000000 20.791000000 120.500000000 90.000000\n"
        "BEGIN_POLYGON 0 65535 4\nBEGIN_WINDING\n"
        "POLYGON_POINT -156.95 20.79 0.0 0.0\n"
        "POLYGON_POINT -156.94 20.79 1.0 0.0\n"
        "POLYGON_POINT -156.94 20.80 1.0 1.0\n"
        "END_WINDING\nEND_POLYGON\n")


def test_text_properties_keeps_values_verbatim():
    got = W.text_properties(DUMP)
    assert got == PROPS
    assert max(len(f"PROPERTY {n} {v}") for n, v in got) > W.DSFTOOL_LINE_MAX


def _fake_dsf(props, extra_head=b"") -> bytes:
    payload = b"".join(n.encode() + b"\0" + v.encode() + b"\0" for n, v in props)
    prop = struct.pack("<4sI", b"PORP", 8 + len(payload)) + payload
    head_body = prop + extra_head
    head = struct.pack("<4sI", b"DAEH", 8 + len(head_body)) + head_body
    defn = struct.pack("<4sI", b"NFED", 16) + struct.pack("<4sI", b"TRET", 8)
    body = b"XPLNEDSF" + struct.pack("<I", 1) + head + defn
    return body + hashlib.md5(body).digest()


def test_replace_properties_rewrites_only_the_prop_atom(tmp_path):
    """Pure-bytes twin (no DSFTool): the PROP atom takes the new strings,
    HEAD's length follows, every other atom is byte-identical and the MD5
    footer is recomputed."""
    other = struct.pack("<4sI", b"XXXX", 12) + b"abcd"
    p = tmp_path / "t.dsf"
    p.write_bytes(_fake_dsf([("sim/exclude_net", "short")], other))
    W.replace_properties(str(p), PROPS)
    assert p.read_bytes() == _fake_dsf(PROPS, other)
    b = p.read_bytes()
    assert hashlib.md5(b[:-16]).digest() == b[-16:]


def test_replace_properties_refuses_a_non_dsf(tmp_path):
    p = tmp_path / "x.dsf"
    p.write_bytes(b"7z\xbc\xaf\x27\x1c" + b"\0" * 40)
    with pytest.raises(ValueError):
        W.replace_properties(str(p), PROPS)


PLACEHOLDER = "-156.990000/20.780000/-156.960000/20.790000;LONGNET"


def _pristine_dump(tmp_path: Path, tool: str) -> str:
    """What a pack's dump looks like: DSFTool's own canonical form (its
    DIVISIONS / HEIGHTS rows, pooled elevations) with the long row that a
    WED-written DSF carries — made by one short-row round trip, then the
    placeholder swapped for the long value."""
    seed = tmp_path / "seed.text"
    seed.write_text(DUMP.replace(LONG_NET, PLACEHOLDER))
    W._run([tool, "--text2dsf", str(seed), str(tmp_path / "seed.dsf")])
    text = Path(W.dump(str(tmp_path / "seed.dsf"),
                       str(tmp_path / "seed2.text"), tool)).read_text()
    assert PLACEHOLDER in text
    return text.replace(PLACEHOLDER, LONG_NET)


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_long_exclusion_survives_the_round_trip(tmp_path):
    tool = _dsftool_path()
    pristine = _pristine_dump(tmp_path, tool)
    src = tmp_path / "in.text"
    src.write_text(pristine)
    # the defect itself: DSFTool alone cuts the long row
    raw = tmp_path / "raw.dsf"
    W._run([tool, "--text2dsf", str(src), str(raw)])
    back = W.dump(str(raw), str(tmp_path / "raw.text"), tool)
    rep = W.compare_dumps(pristine, Path(back).read_text())
    assert not rep.ok
    assert rep.findings[0].startswith("structural row")
    assert "PROPERTY sim/exclude_net" in rep.findings[0]
    # the fix: encode() restores every property verbatim, in order
    out = W.encode(str(src), str(tmp_path / "out.dsf"), tool)
    rep = W.verify_roundtrip(out, pristine, tool)
    assert rep.ok, rep.findings
    again = W.dump(out, str(tmp_path / "out.text"), tool)
    assert W.text_properties(Path(again).read_text()) == PROPS


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_a_long_non_property_row_is_refused(tmp_path):
    src = tmp_path / "in.text"
    src.write_text(DUMP.replace("objects/hangar.obj",
                                "objects/" + "h" * 600 + ".obj"))
    with pytest.raises(RuntimeError, match="text reader keeps 511"):
        W.encode(str(src), str(tmp_path / "out.dsf"), _dsftool_path())
