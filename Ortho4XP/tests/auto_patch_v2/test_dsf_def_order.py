"""#2291 twins: two pack writes the round-trip verifier refused in the
owner's 1.0.585 run, both the WRITE's text against what DSFTool dumps.

* A definition added out of DSFTool's dump order (``dsf_additions.
  DEF_ORDER``): CYYZ's new 3D-tree ``POLYGON_DEF``s were written after its
  ``NETWORK_DEF``; the re-dump lists every POLYGON_DEF first, so the
  structural rows differed.  :func:`dsf_additions.def_insert_at` is where
  a new definition goes.
* ``DIVISIONS`` is the encoder's cap on the pool cut, and the dump prints
  the cut the geometry needed: TNCM's 8 draped photos hidden left no pool
  and DSFTool printed its default ``DIVISIONS 2``
  (``dsf_write._divisions_reconciled``).

Synthetic texts; the round trips need DSFTool and skip without it.
"""
from __future__ import annotations

import pytest
from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf_additions as A
from auto_patch_v2.airport import dsf_write as W

HEAD = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\n"
        "DIVISIONS 16\nHEIGHTS 0.50000 0.0\n"
        "PROPERTY sim/west -63\nPROPERTY sim/east -62\n"
        "PROPERTY sim/north 18\nPROPERTY sim/south 17\n"
        "PROPERTY sim/planet earth\nPROPERTY sim/overlay 1\n")
POLY = ("BEGIN_POLYGON 0 65535 4\nBEGIN_WINDING\n"
        "POLYGON_POINT -62.8 17.9 1.0 1.0\nPOLYGON_POINT -62.9 17.9 0.0 1.0\n"
        "POLYGON_POINT -62.9 17.95 0.0 0.0\nEND_WINDING\nEND_POLYGON\n")
NET = ("BEGIN_SEGMENT 0 1 1 -62.5 17.5 0.000000000\n"
       "END_SEGMENT 2 -62.4 17.5 0.000000000\n")


def _lines(*defs: str) -> list[str]:
    return (HEAD + "".join(d + "\n" for d in defs)).splitlines()


@pytest.mark.parametrize("defs, keyword, after", [
    (("OBJECT_DEF a.obj", "POLYGON_DEF p.pol", "NETWORK_DEF n.net"),
     "POLYGON_DEF", "POLYGON_DEF p.pol"),
    (("OBJECT_DEF a.obj", "NETWORK_DEF n.net"), "POLYGON_DEF", "OBJECT_DEF a.obj"),
    (("POLYGON_DEF p.pol", "NETWORK_DEF n.net"), "OBJECT_DEF", "PROPERTY sim/overlay 1"),
    (("TERRAIN_DEF t", "POLYGON_DEF p.pol", "RASTER_DEF r"), "NETWORK_DEF",
     "POLYGON_DEF p.pol"),
    ((), "POLYGON_DEF", "PROPERTY sim/overlay 1"),
])
def test_a_new_definition_goes_where_dsftool_lists_it(defs, keyword, after):
    lines = _lines(*defs)
    at = A.def_insert_at(lines, keyword)
    assert lines[at - 1] == after
    kinds = [ln.split()[0] for ln in lines[:at] + [keyword] + lines[at:]
             if ln.split()[:1] and ln.split()[0] in A.DEF_ORDER]
    assert kinds == sorted(kinds, key=A.DEF_ORDER.index)


def test_an_object_def_in_a_dump_without_one_goes_ahead_of_the_polygons():
    text = HEAD + "POLYGON_DEF p.pol\nNETWORK_DEF n.net\n" + POLY
    out, idx = A.add_objects(text, [("o4/deck.obj", -62.5, 17.5, 3.0, 0.0)])
    lines = out.split("\n")
    assert idx == [0]
    assert lines.index("OBJECT_DEF o4/deck.obj") < lines.index("POLYGON_DEF p.pol")


@pytest.mark.parametrize("rows", ["", "OBJECT_DEF a.obj\nOBJECT 0 -62.9 17.95 10.0\n"])
@pytest.mark.parametrize("printed, ok", [("2", True), ("8", True), ("16", True),
                                          ("32", False)])
def test_divisions_is_a_cap_never_a_value(rows, printed, ok):
    expected = HEAD + rows
    actual = expected.replace("DIVISIONS 16", f"DIVISIONS {printed}")
    report = W.compare_dumps(expected, actual)
    assert report.ok is ok, report.findings
    lost = W.compare_dumps(expected, expected.replace("DIVISIONS 16\n", ""))
    assert not lost.ok, "a lost DIVISIONS row is still refused"


def _round_trip(tmp_path, text: str) -> W.RoundTripReport:
    tool = _dsftool_path()
    src = tmp_path / "x.text"
    src.write_text(text, encoding="utf-8", newline="\n")
    W.encode(str(src), str(tmp_path / "x.dsf"), tool)
    return W.verify_roundtrip(str(tmp_path / "x.dsf"), text, tool)


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_every_photo_hidden_round_trips(tmp_path):
    """TNCM's shape: polygon definitions only, every one omitted."""
    assert _round_trip(tmp_path, HEAD).ok


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_a_polygon_def_added_beside_a_network_round_trips(tmp_path):
    """CYYZ's shape: a POLYGON_DEF added to a dump that declares a network."""
    lines = _lines("POLYGON_DEF p.pol", "NETWORK_DEF lib/g10/roads.net")
    lines.insert(A.def_insert_at(lines, "POLYGON_DEF"), "POLYGON_DEF q.for")
    text = "\n".join(lines) + "\n" + POLY + POLY.replace(
        "BEGIN_POLYGON 0 65535 4", "BEGIN_POLYGON 1 767 4") + NET
    report = _round_trip(tmp_path, text)
    assert report.ok, report.findings
    wrong = text.replace("POLYGON_DEF q.for\n", "").replace(
        "NETWORK_DEF lib/g10/roads.net\n",
        "NETWORK_DEF lib/g10/roads.net\nPOLYGON_DEF q.for\n")
    assert not _round_trip(tmp_path, wrong).ok, "the old order is the refusal"


def test_the_line_ending_mark_is_not_content():
    """DSFTool prints 'A' on macOS and 'I' on Linux/Windows as the first
    row (CI run 45919109708); the comparison never reads it as a change."""
    other = "I" + HEAD[1:]
    report = W.compare_dumps(HEAD, other)
    assert not any("structural" in f for f in report.findings), report.findings
