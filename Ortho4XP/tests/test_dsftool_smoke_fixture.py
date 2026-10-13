"""The DSFTool smoke test's comparison notices what a broken tool would do (#587).

``Utils/toolchains/smoke_test_dsftool.py`` round-trips an airport-shaped
overlay through a DSFTool binary and compares the dump with the text sent
(owner RULINGS 2026-10-13a (9)).  On Windows and Linux that script is the
ONLY evidence for the bundled binary, so its comparison must accept what a
correct encoder does (reordering, renumbered junctions, pool rounding) and
refuse every loss.  No binary is run here: the "dump" is edited text.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "Utils", "toolchains", "smoke_test_dsftool.py")
_spec = importlib.util.spec_from_file_location("smoke_test_dsftool", _SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

SENT = smoke.airport_text(1)


def test_the_fixture_carries_every_row_family_of_an_airport_overlay():
    said = smoke.structure(SENT)

    assert [k for k, _ in said["defs"]].count("OBJECT_DEF") == 300
    assert {k for k, _ in said["defs"]} == {"OBJECT_DEF", "POLYGON_DEF", "NETWORK_DEF"}
    assert sorted(p[0] for p in said["placements"]) == [
        "OBJECT", "OBJECT", "OBJECT_AGL", "OBJECT_MSL"]
    holed, facade = said["polygons"]
    assert (len(holed[3]), holed[2]) == (2, 2)          # outer ring + hole
    assert (len(facade[3]), facade[2]) == (1, 3)        # wall type per point
    assert sorted(len(s[2]) for s in said["segments"]) == [2, 4]   # 2 shape points
    # the trait variant places every object above definition 255
    assert {p[1] for p in smoke.structure(smoke.airport_text(297))["placements"]} == {
        297, 298, 299}


def test_what_a_correct_encoder_changes_is_accepted():
    rows = SENT.splitlines()
    first_object = next(i for i, r in enumerate(rows) if r.startswith("OBJECT "))
    rows[first_object], rows[first_object + 1] = rows[first_object + 1], rows[first_object]
    dump = "\n".join(rows) + "\n"
    dump = dump.replace("-122.500000000 47.500000000 90.000000",
                        "-122.500000477 47.499999523 89.997253")          # pool rounding
    dump = dump.replace("BEGIN_SEGMENT 0 50 1 ", "BEGIN_SEGMENT 0 50 41 ")  # junction ids
    dump = dump.replace("END_SEGMENT 2 ", "END_SEGMENT 40 ")
    dump = "# pool  0: p=3 s=4\n" + dump.replace(
        "HEIGHTS 0.03125 0.0", "HEIGHTS 0.03125 -5.0  # max encodeable 2042.96875")

    assert smoke.differences(SENT, dump) == []


@pytest.mark.parametrize("what, old, new", [
    ("a dropped shape point", "SHAPE_POINT -122.798000000 47.801500000 0.000000000\n", ""),
    ("a moved shape point", "SHAPE_POINT -122.798000000", "SHAPE_POINT -122.798100000"),
    ("a lost hole", "END_WINDING\nBEGIN_WINDING\nPOLYGON_POINT -122.597000000 47.603000000\n"
     "POLYGON_POINT -122.597000000 47.607000000\nPOLYGON_POINT -122.593000000 47.607000000\n"
     "POLYGON_POINT -122.593000000 47.603000000\n", ""),
    ("a facade wall type", "47.700000000 1.000000000", "47.700000000 0.000000000"),
    ("an MSL height pooled at 1 m", "131.500000000 45.000000", "131.000000000 45.000000"),
    ("an AGL object turned on-ground", "OBJECT_AGL 3 -122.530000000 47.530000000 12.250000000",
     "OBJECT 3 -122.530000000 47.530000000"),
    ("a lost definition", "POLYGON_DEF buildings/smoke_terminal.fac\n", ""),
    ("a lost segment", "BEGIN_SEGMENT 0 30 2 -122.797000000 47.802000000 0.000000000\n"
     "END_SEGMENT 3 -122.795000000 47.803000000 0.000000000\n", ""),
    ("the overlay property", "PROPERTY sim/overlay 1\n", ""),
])
def test_every_loss_is_named(what, old, new):
    assert old in SENT, what

    assert smoke.differences(SENT, SENT.replace(old, new)), what
