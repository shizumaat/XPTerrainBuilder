"""#1598 (owner ruling 2026-11-04, "1598. Yes"): a draped-pavement OVERLAY
pack is PAVEMENT EVIDENCE where the airport's own pavement is not
(``airport/overlay_pavement``)."""
from __future__ import annotations

import struct
import types

from auto_patch_v2.airport import overlay_pavement as OV
from shapely.geometry import Polygon, box

LAW = types.SimpleNamespace(tables=types.SimpleNamespace(emit=types.SimpleNamespace(
    identity=types.SimpleNamespace(overlay_pavement_sliver_m=3.0,
                                   overlay_pavement_reach_m=50.0))))
OWN = box(0, 0, 100, 100)


def test_only_what_the_own_pavement_does_not_cover_is_added():
    # the overlay redraws the own apron and extends it 40 m east
    got = OV._evidence([(box(0, 0, 140, 100), "asphalt")], OWN, None, LAW)
    assert len(got) == 1
    piece, tag = got[0]
    assert tag == "asphalt"
    assert abs(piece.area - 40 * 100) < 1e-6
    assert piece.bounds == (100.0, 0.0, 140.0, 100.0)


def test_a_pack_whose_pages_never_meet_the_own_pavement_adds_nothing():
    assert OV._evidence([(box(120, 0, 160, 100), "a")], OWN, None, LAW) == []


def test_an_edge_mismatch_is_no_pavement():
    # two packs tracing one apron 1 m apart: a 1 m strip, not a road
    assert OV._evidence([(box(0, 0, 101, 100), "a")], OWN, None, LAW) == []


def test_a_detached_lot_needs_the_boundary_or_the_reach():
    pages = [(box(0, 0, 100, 100), "a"),            # meets the own pavement
             (box(130, 0, 170, 40), "near"),        # 30 m off: inside the reach
             (box(300, 0, 340, 40), "far")]         # 200 m off
    tags = sorted(t for _p, t in OV._evidence(pages, OWN, None, LAW))
    assert tags == ["near"]
    boundary = box(-10, -10, 400, 120)
    tags = sorted(t for _p, t in OV._evidence(pages, OWN, boundary, LAW))
    assert tags == ["far", "near"]


def test_each_page_keeps_its_own_piece_the_later_drawn_on_top():
    # a lot page drawn over a broad taxi page: two sources, as the pack's
    # own pages are, never one merged piece
    pages = [(box(0, 0, 200, 100), "taxi"), (box(100, 0, 130, 100), "lot")]
    got = {t: p.bounds for p, t in OV._evidence(pages, OWN, None, LAW)}
    assert got == {"lot": (100.0, 0.0, 130.0, 100.0), "taxi": (130.0, 0.0, 200.0, 100.0)}


def _dsf(path, defs):
    poly = struct.pack("<4sI", b"YLOP", 8 + sum(len(d) + 1 for d in defs)) \
        + b"".join(d.encode() + b"\0" for d in defs)
    defn = struct.pack("<4sI", b"NFED", 8 + len(poly)) + poly
    prop = struct.pack("<4sI", b"PORP", 8 + 14) + b"sim/overlay\x001\0"
    head = struct.pack("<4sI", b"DAEH", 8 + len(prop)) + prop
    path.write_bytes(b"XPLNEDSF" + struct.pack("<I", 1) + head + defn)


def test_the_screen_reads_the_dsf_polygon_definitions(tmp_path, monkeypatch):
    import O4_DSF_Header as H
    pav, forest = tmp_path / "pav" / "x.dsf", tmp_path / "for" / "x.dsf"
    for p in (pav, forest):
        p.parent.mkdir()
    _dsf(pav, ["lib/g10/forests/x.for", "Pack/Asphalt_Top_Plain.pol"])
    _dsf(forest, ["lib/g10/forests/x.for", "sports/golf_green.pol"])
    assert H.dsf_polygon_defs(str(pav)) == ["lib/g10/forests/x.for",
                                            "Pack/Asphalt_Top_Plain.pol"]
    roots = {str(pav.parent): str(pav), str(forest.parent): str(forest)}
    monkeypatch.setattr(OV, "tile_candidates", lambda m, la, lo: sorted(roots))
    monkeypatch.setattr(OV._dsf, "dsf_path_in_pack", lambda r, la, lo: roots[r])
    # the pavement gate, not the name of the pack, decides
    assert OV.dump_candidates("main", 1, 2) == [str(pav.parent)]


def test_an_unreadable_definition_table_leaves_the_dump_to_decide(tmp_path):
    import O4_DSF_Header as H
    p = tmp_path / "z.dsf"
    p.write_bytes(b"7z\xbc\xaf\x27\x1c")
    assert H.dsf_polygon_defs(str(p)) is None
    assert OV._defines_pavement(str(p), lambda d: (None, None))


def test_pieces_are_minted_as_dsf_overlay_sources(tmp_path, monkeypatch):
    from auto_patch_v2.model.airport import Pavement, Surface
    own = [Pavement("dsf:pol0", Surface(1), tuple(OWN.exterior.coords[:-1]), ())]
    page = Pavement("dsf:pol7", Surface(1), tuple(box(0, 0, 140, 100).exterior.coords[:-1]),
                    (), "Pack/Asphalt_Top_Plain.pol")
    monkeypatch.setattr(OV, "dump_candidates", lambda m, la, lo, index=None: ["/cs/over"])
    monkeypatch.setattr(OV, "_read_pack_pages",
                        lambda root, la, lo, mc, read: ("dump", read("dump")))
    notes = []
    got = OV.load_pavements("/cs/main", (1, 2), "/mc", None, lambda d, r: [page],
                            own, (), LAW, notes.append)
    assert [p.id for p in got] == ["dsf:overlay0"]
    assert got[0].description == "Pack/Asphalt_Top_Plain.pol"
    assert abs(Polygon(got[0].outer).area - 4000) < 1e-6
    assert "over: 1 piece(s), 4,000 m2" in notes[0]
