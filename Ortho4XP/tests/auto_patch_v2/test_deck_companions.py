"""Twin of ``deck_companions`` (owner 2026-11-21T06:47Z, KMCO 1.0.570: the
hidden pack bridge's shadow lines stayed drawn around the generated
decks).  Headless: a hand-written OBJ and DSF dump in ``tmp_path``."""
from __future__ import annotations

from auto_patch_v2.airport import deck_author_art, deck_companions, dsf_row_hide
from shapely.geometry import box

RING = box(17.004, 59.003, 17.006, 59.007)
ROUTE = [[17.005, 59.0], [17.005, 59.01]]


def _line(idx: int, *pts) -> list[str]:
    return [f"BEGIN_POLYGON {idx} 0 2", "BEGIN_WINDING",
            *[f"POLYGON_POINT {a} {b}" for a, b in pts], "END_WINDING", "END_POLYGON"]


DUMP = "\n".join([
    "A", "800", "DSF2TEXT", "", "POLYGON_DEF lines/shadow.lin", "POLYGON_DEF lines/taxi.lin",
    "OBJECT_DEF obj/bridge.obj", "OBJECT 0 17.005 59.005 0.0",
    *_line(0, (17.0045, 59.0025), (17.0045, 59.0075)),     # the bridge's shadow, on the deck
    *_line(0, (17.0038, 59.0025), (17.0038, 59.0075)),     # ... along its edge, beside ours
    *_line(1, (17.005, 58.99), (17.005, 59.02)),           # the taxiway line runs on past
    *_line(0, (17.003, 59.0072), (17.007, 59.0072)),       # wholly inside, off the crossing
    ""])


def test_a_hidden_bridge_takes_its_own_drapes(tmp_path):
    obj = tmp_path / "bridge.obj"
    # a plan box 200 m x 1000 m about the anchor (OBJ: x east, z south)
    obj.write_text("I\n800\nOBJ\n\nPOINT_COUNTS 4 0 0 6\n"
                   "VT -100 0 -500 0 1 0 0 0\nVT 100 0 -500 0 1 0 0 0\n"
                   "VT 100 0 500 0 1 0 0 0\nVT -100 0 500 0 1 0 0 0\n"
                   "IDX10 0 1 2 0 2 3 0 0 0 0\nTRIS 0 6\n", encoding="ascii")
    rows = deck_companions.placements(DUMP)
    assert rows == {"obj/bridge.obj": [(17.005, 59.005, 0.0)]}
    plan = deck_companions.plan_box(str(obj), 17.005, 59.005, 0.0)
    pages = deck_author_art.pack_pages(DUMP)
    found = deck_companions.companions(pages, [plan], [(RING, ROUTE)], 0.5)
    assert [k for k, _i in found] == [0, 1]
    hides = deck_companions.rows(pages, found, ["dsf:obj1"])
    assert hides[0]["companion"] and hides[0]["resource"] == "lines/shadow.lin"
    text, n = dsf_row_hide.hide_rows(DUMP, [(h["resource"], h["lon"], h["lat"]) for h in hides])
    assert n == 2 and "17.0045 59.0025" not in text and "17.005 58.99" in text
    # the shadow is never carried on the deck; the taxiway line is
    kept = deck_author_art.deck_lines(pages, RING, ROUTE, {k for k, _i in found})
    assert [p for p, _q in kept] == ["lines/taxi.lin"]
