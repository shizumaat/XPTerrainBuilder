"""Twins of spec 2123 rounds A/B in the app pipeline (RULINGS 2026-11-16y):
the one apt.dat writer (``apt_flatten.write_regions``), the object-stage
recipe (``airport/generated_pack``), the paint table (``deck_paint``), the
road-bridge span clip (``planar/road_bridge_gen.clip_spans``), the tunnel
grouping of ``planar/deck_generated`` and the ``drawn_site --roads``
reader (``tools/drawn_site_roads``).  Headless: ``tmp_path``, no X-Plane."""
from __future__ import annotations

import dataclasses as dc
import json
import os
import sys

from shapely.geometry import LineString, Polygon, box

from auto_patch_v2.airport import apt_dat, apt_flatten, deck_paint
from auto_patch_v2.airport import generated_pack as gen
from auto_patch_v2.airport.deck_obj8 import DECK_MARK
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.placement import BACKUP_SUFFIX

from test_pack_edits_2123 import BLOCK, DUMP  # noqa: E402  (sibling twin, rootdir on sys.path)

REGION = box(17.004, 59.003, 17.006, 59.007)          # lon, lat: across the centre line


def _apt(tmp_path) -> str:
    d = tmp_path / "Pack" / "Earth nav data"
    d.mkdir(parents=True)
    p = d / "apt.dat"
    p.write_text("I\n1100 test\n\n" + "\n".join(BLOCK) + "\n1302 flatten 1\n\n99\n",
                 encoding="utf-8")
    return str(p)


def test_write_regions_cuts_records_and_reads_as_shipped(tmp_path):
    apt = _apt(tmp_path)
    shipped = open(apt, "rb").read()
    state, dropped = apt_flatten.write_regions(apt, "TEST", [REGION])
    assert state == "written" and dropped           # the centre line's inside
    live = open(apt, "rb").read()
    assert open(apt + BACKUP_SUFFIX, "rb").read() == shipped
    assert b"1302 flatten" not in live              # the strip rides along
    rec = json.load(open(apt + apt_flatten.EDITS_SUFFIX, encoding="utf-8"))
    assert rec["regions"] and rec["icao"] == "TEST"
    v = apt_flatten.classify(apt)
    assert v.state.name == "OURS" and apt_flatten.read_path(apt) == apt + BACKUP_SUFFIX
    (pav,) = apt_dat.parse_airport_block(apt_dat.read_airport_block(apt, "TEST")).pavements
    assert len(pav.rings) == 2                      # the read frame is the shipped file
    # a rewrite is the same bytes; no region leaves the strip alone
    apt_flatten.write_regions(apt, "TEST", [REGION])
    assert open(apt, "rb").read() == live
    apt_flatten.write_regions(apt, "TEST", [])
    assert open(apt, "rb").read() == apt_flatten.stripped(shipped)
    assert apt_flatten.classify(apt).state.name == "OURS"


def _pub():
    ring = [list(c) for c in REGION.exterior.coords[:-1]]
    return {"decks": [{"object_id": "o4gen_t", "resource": f"{gen.GENERATED_DIR}/deck_t.obj",
                       "ring": ring, "seats_a": [[17.0045, 59.003], [17.0055, 59.003]],
                       "seats_b": [[17.0045, 59.007], [17.0055, 59.007]],
                       "top_a": 0.0, "top_b": 0.3, "zero_m": 31.0, "family": "taxi",
                       "thickness_m": 1.0, "top_lift_m": 0.02}],
            "road_bridges": [{"id": "-60", "span_wkt": box(17.0015, 59.0015, 17.0025,
                                                           59.0025).wkt,
                              "junctions": [[17.001, 59.002, 0], [17.0015, 59.002, 1],
                                            [17.0025, 59.002, 1], [17.003, 59.002, 0]],
                              "subtype": 50, "net": "lib/g10/roads_EU.net"}]}


def test_recipe_builds_the_deck_paint_lights_and_chain(tmp_path):
    rec = gen.recipe(_pub(), _apt(tmp_path), "TEST", load_default())
    obj = rec["files"][f"{gen.GENERATED_DIR}/deck_t.obj"].decode("ascii")
    assert DECK_MARK in obj and "ATTR_hard_deck concrete" in obj
    assert "LIGHT_NAMED taxi_g " in obj and "LIGHT_NAMED taxi_g_rev " in obj
    assert "ATTR_poly_os 2" in obj                  # the centre line, redrawn
    assert f"{gen.GENERATED_DIR}/{gen.TEXTURE}" in rec["files"]
    (d,) = rec["decks"]
    assert d["msl"] == 31.0 and 0.0 <= d["hdg"] < 360.0
    assert len(rec["regions"]) == 2 and len(rec["chains"]) == 1
    text, counts = gen.apply_text(DUMP, rec)
    assert counts["decks"] == 1 and counts["chains"] == 1 and counts["pages_cut"] >= 1
    assert f"OBJECT_DEF {gen.GENERATED_DIR}/deck_t.obj" in text
    assert "NETWORK_DEF lib/g10/roads_EU.net" in text
    assert sum(1 for ln in text.split("\n") if ln.startswith("BEGIN_SEGMENT")) == 3


def test_files_record_and_remove(tmp_path):
    rec = gen.recipe(_pub(), _apt(tmp_path), "TEST", load_default())
    pack = tmp_path / "Pack"
    written = gen.write_files(str(pack), rec)
    assert len(written) == 2 and all(os.path.isfile(p) for p in written)
    row = gen.record("sha", rec, {"decks": 1}, "now")
    entry = {gen.RECORD_KEY: row}
    assert sorted(gen.files_of(entry)) == sorted(rec["files"])
    again = gen.recorded(entry, "sha")
    assert again["decks"] == rec["decks"] and gen.recorded(entry, "other") == {}
    other = pack / "objects" / "o4_generated" / "not_ours.obj"
    other.write_text("I\n800\nOBJ\n", encoding="ascii")
    gone = gen.remove(str(pack), gen.files_of(entry) + ["objects/o4_generated/not_ours.obj"])
    assert len(gone) == 2 and other.is_file()        # an unmarked file stays


def test_paint_table_reads_xplane_line_specs():
    (s,) = deck_paint.stripes_of(1)
    assert s[1] == 0.141 and s[2] == "yellow" and s[3] is None
    b = deck_paint.stripes_of(51)
    assert b[0][2] == "black" and b[1][2] == "yellow"
    assert deck_paint.stripes_of(30) == ()           # red guidance: not painted
    dashes = deck_paint.dashed_pieces(LineString([(0, 0), (3, 0)]), (0.375, 0.375))
    assert len(dashes) == 4 and abs(dashes[0].length - 0.375) < 1e-9
    assert deck_paint.light_names(101) == ("taxi_g", "taxi_g_rev")
    assert deck_paint.light_names(102) == ()


def test_span_cells_cut_only_the_pack_pavement_under_the_span():
    from auto_patch_v2.classify.roles import Cell, Classification
    from auto_patch_v2.law.tables import load_default as _law
    from auto_patch_v2.planar.road_bridge_gen import span_cells

    @dc.dataclass(frozen=True)
    class _Pav:
        id: str

    @dc.dataclass(frozen=True)
    class _Ap:
        pavements: tuple
        road_bridges: tuple

    def cell(i, ref, ring, role="parking_lot"):
        return Cell(i, role, ref, ring, (), None, None, "groundside", "slice", {})
    page = cell(0, "dsf:pol1", ((0, 0), (100, 0), (100, 100), (0, 100)))
    road = cell(1, "big_roads:-9", ((45, -20), (55, -20), (55, 120), (45, 120)), "service_road")
    cl = Classification((page, road), (), {}, ())
    ap = _Ap((_Pav("dsf:pol1"),), ({"span_xy": [[-10, 40], [110, 40], [110, 60], [-10, 60]]},))
    out, notes = span_cells(cl, ap, _law())
    refs = sorted(c.ref for c in out.cells)
    assert refs == ["big_roads:-9", "dsf:pol1", "dsf:pol1#1"] and len(notes) == 1
    for c in out.cells:
        if c.ref.startswith("dsf:"):
            assert Polygon(c.ring).intersection(box(0, 41, 100, 59)).area < 1e-6
    same, none = span_cells(cl, _Ap((), ()), _law())
    assert same is cl and none == []


def test_tunnel_ways_join_end_to_end():
    from auto_patch_v2.planar.deck_generated import _connected

    @dc.dataclass
    class W:
        id: str
        points: tuple
    ws = [W("a", ((0, 0), (10, 0))), W("b", ((10, 0), (20, 0))), W("c", ((50, 0), (60, 0)))]
    groups = sorted(sorted(w.id for w in g) for g in _connected(ws))
    assert groups == [["a", "b"], ["c"]]


def test_drawn_roads_reads_segments_levels_and_exclusions(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
    from drawn_site_roads import read_segments
    p = tmp_path / "d.txt"
    p.write_text("\n".join([
        "PROPERTY sim/exclude_net 17.0/59.0/17.1/59.1",
        "NETWORK_DEF lib/g10/roads_EU.net",
        "BEGIN_SEGMENT 0 50 1 17.01 59.01 0.0",
        "SHAPE_POINT 17.02 59.01 0",
        "END_SEGMENT 2 17.03 59.01 1.0",
        "BEGIN_SEGMENT 0 50 3 18.01 59.01 0.0",
        "END_SEGMENT 4 18.03 59.01 0.0", ""]), encoding="utf-8")
    segs, excl = read_segments(str(p), (17.0, 59.0, 17.05, 59.05))
    assert excl == [(17.0, 59.0, 17.1, 59.1)]
    (net, sub, pts), = segs
    assert net.endswith("roads_EU.net") and sub == 50 and pts[-1][2] == 1.0
