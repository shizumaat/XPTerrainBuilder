"""Twins of #2178: an airport on two tiles writes each tile's pack DSF
with ONE generated recipe; each DSF gets only the deck objects anchored
on it and the road chains clipped to it (``generated_tile``), any object
row still off the tile is left out before the encoder, and the apt.dat
cut of the airport is written once.  Headless: no DSFTool, no X-Plane."""
from __future__ import annotations

from auto_patch_v2.airport import apt_flatten
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport import generated_tile as gt
from shapely.geometry import box
from test_generated_2123 import REGION, _apt  # noqa: E402  (sibling twin)


def _dump(west: int, south: int) -> str:
    return "\n".join([
        "A", "800 written by DSFTool", "DSF2TEXT", "",
        f"PROPERTY sim/west {west}", f"PROPERTY sim/east {west + 1}",
        f"PROPERTY sim/south {south}", f"PROPERTY sim/north {south + 1}",
        "OBJECT_DEF lib/a.obj",
        f"OBJECT 0 {west + 0.5} {south + 0.5} 0.0", ""])


def _deck(name: str, lon: float, lat: float) -> dict:
    return {"object_id": name, "resource": f"{gen.GENERATED_DIR}/{name}.obj",
            "lon": lon, "lat": lat, "msl": 30.0, "hdg": 90.0}


#: one deck each side of the +59+017 / +59+018 edge, one chain across it
REC = {"decks": [_deck("west", 17.99, 59.5), _deck("east", 18.01, 59.5)],
       "regions": [box(17.98, 59.49, 18.02, 59.51).wkt], "hides": [],
       "chains": [{"subtype": 50, "net": "lib/g10/roads.net",
                   "junctions": [[17.98, 59.6, 0], [17.99, 59.6, 1],
                                 [18.01, 59.6, 1], [18.02, 59.6, 0]]}]}


def _objects(text: str) -> list[tuple[float, float]]:
    return [(float(t[2]), float(t[3])) for t in (ln.split() for ln in text.split("\n"))
            if t and t[0] == "OBJECT_MSL"]


def _segments(text: str) -> list[list[str]]:
    return [ln.split() for ln in text.split("\n") if ln.startswith(("BEGIN_SEGMENT",
                                                                     "END_SEGMENT"))]


def test_each_tile_dsf_gets_only_its_own_deck_and_chain_half():
    west, wc = gen.apply_text(_dump(17, 59), REC)
    east, ec = gen.apply_text(_dump(18, 59), REC)
    assert _objects(west) == [(17.99, 59.5)] and _objects(east) == [(18.01, 59.5)]
    assert wc["decks"] == ec["decks"] == 1
    assert wc["decks_other_tile"] == ec["decks_other_tile"] == 1
    assert wc["chains"] == ec["chains"] == 1 and wc["chains_clipped"] == 1
    w_end, e_start = _segments(west)[-1], _segments(east)[0]
    # the two halves meet on the edge at the same point and level
    assert w_end[2:5] == e_start[4:7] and float(w_end[2]) == 18.0
    for text, (lo, hi) in ((west, (17, 18)), (east, (18, 19))):
        for t in _segments(text):
            lon = float(t[2] if t[0] == "END_SEGMENT" else t[4])
            assert lo <= lon <= hi


def test_the_record_stays_whole_and_its_replay_filters_the_same_way():
    row = gen.record("sha", REC, {}, "now")
    assert len(row["decks"]) == 2 and len(row["chains"]) == 1
    again = gen.recorded({gen.RECORD_KEY: row}, "sha")
    assert _objects(gen.apply_text(_dump(18, 59), again)[0]) == [(18.01, 59.5)]


def test_a_dump_without_a_tile_box_keeps_the_recipe_whole():
    text = "A\n800\nDSF2TEXT\n\nOBJECT_DEF lib/a.obj\n"
    assert len(_objects(gen.apply_text(text, REC)[0])) == 2


def test_clip_chain_inside_outside_and_through():
    tile = (17.0, 59.0, 18.0, 60.0)
    assert gt._clip_chain([[17.1, 59.1, 0], [17.2, 59.1, 0]], tile) == \
        [[[17.1, 59.1, 0], [17.2, 59.1, 0]]]
    assert gt._clip_chain([[18.1, 59.1, 0], [18.2, 59.1, 0]], tile) == []
    (piece,) = gt._clip_chain([[16.9, 59.5, 0], [18.1, 59.5, 0]], tile)
    assert [p[0] for p in piece] == [17.0, 18.0]


def test_an_object_row_off_the_tile_is_left_out_and_counted():
    text = _dump(17, 59) + "OBJECT_MSL 0 18.2 59.5 30.0 0.0\nOBJECT_AGL 0 17.2 59.5 1.0 0.0\n"
    kept, gone = gt.drop_off_tile_objects(text, (17.0, 59.0, 18.0, 60.0))
    assert gone == 1 and "18.2 59.5" not in kept and "17.2 59.5" in kept
    assert gt.drop_off_tile_objects(text, None) == (text, 0)


def test_the_apt_dat_cut_is_written_once_for_both_tiles(tmp_path):
    apt = _apt(tmp_path)
    assert apt_flatten.write_regions(apt, "TEST", [REGION])[0] == "written"
    live = open(apt, "rb").read()
    assert apt_flatten.write_regions(apt, "TEST", [REGION])[0] == "unchanged"
    assert open(apt, "rb").read() == live
    assert apt_flatten.write_regions(apt, "TEST", [])[0] == "written"
