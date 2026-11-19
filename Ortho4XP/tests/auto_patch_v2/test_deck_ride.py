"""Twins of RULINGS 2026-11-19c (``airport/deck_ride``): a pack placement
standing on a GENERATED deck rides its top -- an object row on the deck is
written ``OBJECT_MSL`` with its lowest point on the deck's graded top; one
beside the deck is not touched; an object string crossing the deck keeps
its off-deck pieces as strings and its on-deck piece becomes its objects
seated on the top.  Headless: ``tmp_path``, no X-Plane."""
from __future__ import annotations

from auto_patch_v2.airport import deck_ride
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.law.tables import load_default
from test_generated_2123 import _apt, _pub  # noqa: E402  (sibling twin, rootdir on sys.path)

#: a 3 m kerb along z, its lowest vertex 0.1 m under its origin
_OBJ = "\n".join(["I", "800", "OBJ", "", "POINT_COUNTS 4 0 0 6",
                  "VT -0.3 -0.1 -1.5 0 1 0 0 0", "VT 0.3 -0.1 -1.5 0 1 0 0 0",
                  "VT 0.3 0.4 1.5 0 1 0 0 0", "VT -0.3 0.4 1.5 0 1 0 0 0",
                  "IDX10 0 1 2 0 2 3", "TRIS 0 6", ""])
_M_PER_DEG = 111_320.0


def _top(lat: float) -> float:
    """``_pub``'s deck top: zero 31, 0 at lat 59.003 rising 0.3 to 59.007, lift 0.02."""
    return 31.0 + 0.3 * (lat - 59.003) / 0.004 + 0.02


def _pack(tmp_path):
    pack = tmp_path / "Pack"
    (pack / "kerb").mkdir(parents=True, exist_ok=True)
    (pack / "kerb" / "kerb.obj").write_text(_OBJ, encoding="ascii", newline="\n")
    (pack / "kerb" / "kerb.str").write_text(
        "A\n850\nOBJECT_STRING\n\nOFFSET 0\nOBJECT 0 0 kerb.obj\n", encoding="ascii",
        newline="\n")
    return pack


_DUMP = "\n".join([
    "A", "800 written by DSFTool", "DSF2TEXT", "",
    "PROPERTY sim/west 17",
    "OBJECT_DEF kerb/kerb.obj",
    "POLYGON_DEF kerb/kerb.str",
    "OBJECT 0 17.0050000 59.0050000 0.000000",          # on the deck
    "OBJECT 0 17.0030000 59.0050000 0.000000",          # beside it (60 m west)
    "BEGIN_POLYGON 0 3 2", "BEGIN_WINDING",              # across the deck, west to east
    "POLYGON_POINT 17.0030000 59.0040000",
    "POLYGON_POINT 17.0070000 59.0040000",
    "END_WINDING", "END_POLYGON", ""])


def _rows(text: str) -> list[list[str]]:
    return [ln.split() for ln in text.split("\n") if ln.startswith("OBJECT ")
            or ln.startswith("OBJECT_MSL ")]


def test_a_placement_on_a_generated_deck_rides_it_and_one_beside_does_not(tmp_path):
    rec = gen.recipe(_pub(), _apt(tmp_path), "TEST", load_default(), xplane_root="")
    (top,) = rec["deck_tops"]
    assert top["object_id"] == "o4gen_t" and len(top["z"]) == len(top["ring"])
    text, counts = gen.apply_text(_DUMP, rec, pack_root=str(_pack(tmp_path)))
    rows = _rows(text)
    on = [r for r in rows if r[0] == "OBJECT_MSL" and r[1] == "0" and r[2] == "17.0050000"]
    assert len(on) == 1
    # its lowest vertex (-0.1) on the top at its footprint's LOW end: heading 0,
    # the kerb runs 1.5 m either side of its anchor north-south, the top rises north
    assert abs(float(on[0][4]) - 0.1 - _top(59.005 - 1.5 / _M_PER_DEG)) < 0.005
    assert "OBJECT 0 17.0030000 59.0050000 0.000000" in text      # beside: untouched
    assert counts["deck_riders"] == 1 and counts["deck_strings"] == 1
    # the string: its two off-deck pieces stay strings, the on-deck piece
    # (lon 17.004-17.006, ~115 m) is its kerbs, one per 3 m, heading east
    assert text.count("BEGIN_POLYGON 0 3 2") == 2
    # (the kerb's definition is the one the dump declares)
    kerbs = [r for r in rows if r[0] == "OBJECT_MSL" and r[1] == "0" and r[3].startswith("59.004")]
    assert len(kerbs) == counts["deck_string_objects"] and 35 <= len(kerbs) <= 40
    assert all(17.004 <= float(r[2]) <= 17.006 for r in kerbs)
    assert all(abs(float(r[5]) - 90.0) < 0.5 for r in kerbs)
    assert all(abs(float(r[4]) - 0.1 - _top(59.004)) < 0.005 for r in kerbs)
    # the generated deck itself is placed after the riders and never rides
    deck = [r for r in rows if r[0] == "OBJECT_MSL" and float(r[4]) == 31.0]
    assert len(deck) == 1


def test_a_recorded_recipe_keeps_the_deck_tops(tmp_path):
    rec = gen.recipe(_pub(), _apt(tmp_path), "TEST", load_default(), xplane_root="")
    again = gen.recorded({gen.RECORD_KEY: gen.record("sha", rec, {}, "now")}, "sha")
    assert again["deck_tops"] == rec["deck_tops"]


def test_no_deck_tops_leaves_the_dump_alone():
    assert deck_ride.ride_text(_DUMP, ())[0] == _DUMP
