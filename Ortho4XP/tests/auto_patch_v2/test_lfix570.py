"""Twins of the test-570 integration fixes (lane lfix570; RULINGS 2026-11-20a,
20u, 20v, 20w):

1. a hairline cut cell its noding folds stays as it was, and the mouth-pair
   union reads each cell's valid area (KMCO 1.0.570 "non-noded
   intersection");
2. a combined frame ``_span_bands`` drops never refuses our decks
   (``deck_takeover.decide_crossings``: KRDU STH_TML obj140's south spans);
3. a hide reaches the bodies of a split whose original the DSF names by a
   library export, and the written text is read back (``drawn_rows``) into
   the census (KRDU ``STH_TML__b0_*.obj``);
4. a mate is judged against ALL our decks over the crossings (KDFW 223 /
   224, each over four decks).
"""
from __future__ import annotations

import json
import pathlib
import sys
import types

from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
from auto_patch_v2.planar import deck_takeover as dt
from shapely.geometry import Polygon, box

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))


def _airport():
    return types.SimpleNamespace(
        dem=types.SimpleNamespace(z=lambda x, y: 199.0),
        frame=types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y, x))))


# -- 1. KMCO: the folded hairline and the robust union ----------------------

def test_a_hairline_cut_cell_its_noding_would_fold_stays_as_it_was(monkeypatch):
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar import deck_carve as dc
    sliver = ((0.0, 0.0), (40.0, 0.0), (40.0, 0.1), (0.0, 0.1))
    cell = Cell(0, "graded_strip", f"{dc.CARVE_REF}:o4gen_x:ground", sliver, (), None, None,
                "groundside", "structure", {})
    # the noding hands back a ring whose two sides cross (the KMCO fold)
    folded = ((0.0, 0.0), (20.0, 0.12), (40.0, 0.0), (40.0, 0.1), (20.0, -0.02), (0.0, 0.1))
    monkeypatch.setattr("auto_patch_v2.planar.chords.densify_within",
                        lambda pts, zone, cap: list(folded) + [folded[0]])
    out, n = dc._ring_dense([cell], box(10.0, -5.0, 30.0, 5.0).boundary, load_default())
    assert n == 0 and out[0].ring == sliver


def test_the_mouth_road_union_reads_each_cells_valid_area():
    from auto_patch_v2.geom.valid_area import valid_area
    from shapely.ops import unary_union
    bow = Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])          # self-crossing
    good = box(5.0, 0.0, 15.0, 10.0)
    u = unary_union([valid_area(p) for p in (bow, good)])
    assert u.is_valid and u.area > good.area


# -- 2. KRDU: a dropped combined frame never refuses our decks ---------------

def _piece(oid: str, ring) -> DeckBridge:
    return DeckBridge(oid, "frame.obj", (oid,), ring, (), (), 0.0, 0.0, -5.0, 100.0)


def _gen(hid: str, ring) -> DeckBridge:
    return DeckBridge(f"o4gen_{hid}", f"objects/o4_generated/deck_{hid}.obj", (), ring,
                      (), (), 0.0, 0.0, -5.2, 100.0, witness=GENERATED_WITNESS)


def test_a_dropped_combined_frame_offers_its_crossings_to_our_decks_again(monkeypatch):
    """Pass one: the frame refuses the south crossing and our north deck
    takes its north span, so ``_span_bands`` drops the frame whole.  Pass two
    offers again without it: both crossings get our decks."""
    frame = _piece("dsf:obj140", ((0, 0), (10, 0), (10, 10), (0, 10)))
    calls = []

    def gen(cl, ap, law, taken, blocked, objects, cache, notes, covered=()):
        calls.append([d.object_id for d in taken])
        north = _gen("n", ((0, 0), (5, 0), (5, 5), (0, 5)))
        south = _gen("s", ((5, 5), (10, 5), (10, 10), (5, 10)))
        return ((north,) if taken else (north, south)), []
    monkeypatch.setattr(dt, "generated_decks", gen)
    monkeypatch.setattr(dt, "_one_decision", lambda g, *a: (tuple(g), []))

    def bands(decks, *a):
        gens = [d for d in decks if d.object_id.startswith("o4gen")]
        return tuple(gens), [f"dropped with {len(gens)} deck(s)"]
    monkeypatch.setattr(dt, "_span_bands", bands)
    out, notes = dt.decide_crossings((frame,), (), [], None, None, _airport(), load_default())
    assert calls == [["dsf:obj140"], []]
    assert sorted(d.object_id for d in out) == ["o4gen_n", "o4gen_s"]
    assert any("offered to our decks again" in n for n in notes)


def test_no_frame_dropped_reads_the_crossings_once(monkeypatch):
    frame = _piece("dsf:obj9", ((0, 0), (10, 0), (10, 10), (0, 10)))
    calls = []

    def gen(*a, **k):
        calls.append(1)
        return (), []
    monkeypatch.setattr(dt, "generated_decks", gen)
    monkeypatch.setattr(dt, "_one_decision", lambda g, *a: (tuple(g), []))
    monkeypatch.setattr(dt, "_span_bands", lambda decks, *a: (tuple(decks), []))
    out, notes = dt.decide_crossings((frame,), (), [], None, None, _airport(), load_default())
    assert calls == [1] and [d.object_id for d in out] == ["dsf:obj9"] and notes == []


# -- 3. KRDU: the hide reaches the split bodies; the written pack read -------

def _split():
    from auto_patch_v2.model.placement import Anchor, Body, PlacementRef, Split
    body = Body("b0", "deck", (0,), Anchor(-78.7901, 35.8701, 0.0), "foot",
                "F3R8_Summer/STH_TML__b0_97b1e1fc.obj")
    return Split(PlacementRef(140, "F3R8_Summer/STH_TML.obj", -78.79, 35.87, 0.0), (body,))


def _text(*objects):
    defs = sorted({o[0] for o in objects})
    return "\n".join([f"OBJECT_DEF {d}" for d in defs]
                     + [f"OBJECT {defs.index(r)} {lo:.9f} {la:.9f} 0.000000"
                        for r, lo, la in objects])


def test_a_hide_by_library_path_reaches_the_bodies_of_its_split(tmp_path):
    from auto_patch_v2.airport import dsf_row_hide as H
    from auto_patch_v2.airport import generated_pack as gen
    root = tmp_path / "pack"
    (root / "F3R8_Summer").mkdir(parents=True)
    (root / "F3R8_Summer" / "STH_TML.obj").write_text("A\n800\nOBJ\n", encoding="utf-8", newline="")
    (root / "library.txt").write_text(
        "A\n800\nLIBRARY\n\nEXPORT KRDU/F3R8/STH_TML.obj F3R8_Summer/STH_TML.obj\n",
        encoding="utf-8", newline="")
    text = _text(("F3R8_Summer/STH_TML__b0_97b1e1fc.obj", -78.7901, 35.8701),
                 ("other.obj", -78.80, 35.88))
    hides = [("KRDU/F3R8/STH_TML.obj", -78.79, 35.87)]
    # the read-back finds the drawn body by name, whatever the resolution
    assert len(H.drawn_rows(text, hides, (_split(),))) == 1
    assert H.through_splits(hides, (_split(),)) == hides          # no export read
    rec = {"hides": [{"resource": hides[0][0], "lon": -78.79, "lat": 35.87}]}
    out, counts = gen.apply_text(text, rec, splits=(_split(),), pack_root=str(root))
    assert counts["hidden"] == 1 and counts["hides_drawn"] == []
    assert "OBJECT 0 " not in out and "OBJECT 1 -78.8" in out


def test_the_census_reads_the_hidden_rows_the_written_pack_still_draws(tmp_path):
    from check_grade_lib.families.pack_bridge_under_deck import written_pack_records
    dsf_dir = tmp_path / "Earth nav data" / "+30-080"
    dsf_dir.mkdir(parents=True)
    dsf = dsf_dir / "+35-079.dsf"
    (dsf_dir / "o4_placement_provenance.json").write_text(json.dumps({"dsfs": {
        "+35-079.dsf": {"o4_generated": {"counts": {"hides_drawn": [
            ["F3R8_Summer/STH_TML__b0_97b1e1fc.obj", -78.7901, 35.8701]]}}}}}),
        encoding="utf-8", newline="")
    patches = tmp_path / "Patches"
    patches.mkdir()
    (patches / "o4_v2_rebake_KRDU.json").write_text(json.dumps({"dsf_path": str(dsf)}),
                                                    encoding="utf-8", newline="")
    got = written_pack_records(patches / "KRDU.osm")
    assert [(r["object"], r["lat"]) for r in got] == [
        ("F3R8_Summer/STH_TML__b0_97b1e1fc.obj", 35.8701)]
    assert written_pack_records(tmp_path / "nowhere" / "KRDU.osm") == []


# -- 4. KDFW: the mate's share over ALL our decks ----------------------------

def _placement(oid: str, path: str):
    return types.SimpleNamespace(id=oid, path=path, xy=(0.0, 0.0), heading_deg=0.0,
                                 resolved=path, plan_bbox=box(-100.0, -100.0, 100.0, 100.0),
                                 anchor_z=190.0, agl_m=0.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def test_a_mate_over_four_decks_is_hidden_with_their_bridge(monkeypatch):
    """KDFW 224.obj runs across four taxiway decks, under half of it on any
    one: judged against them all it rides them and is hidden; a building on
    the anchor stays."""
    gens = []
    for k in range(4):
        x0 = -40.0 + 20.0 * k
        gens.append(DeckBridge(
            f"o4gen_{k}", f"objects/o4_generated/deck_{k}.obj", (), _rect(x0, -20.0,
                                                                         x0 + 18.0, 20.0),
            (), (), 0.0, 0.0, -5.2, 199.0, witness=GENERATED_WITNESS,
            covered=(("-1", (("highway", "service"),), ((x0 + 9.0, -30.0), (x0 + 9.0, 30.0))),)))
    body, rail, tower = (_placement("b", "220.obj"), _placement("r", "224.obj"),
                         _placement("t", "tower.obj"))
    plans = {"b": _rect(-40.0, -20.0, 38.0, 20.0), "r": _rect(-40.0, -2.0, 38.0, 2.0),
             "t": _rect(-10.0, -5.0, 0.0, 5.0)}

    def top(o, cache, law, lo, hi):
        if hi == float("inf"):
            return box(-10.0, -5.0, 0.0, 5.0) if str(o.id) == "t" else None
        return box(-40.0, -20.0, 38.0, 20.0) if str(o.id) == "b" else None
    monkeypatch.setattr(dt, "_body_top", top)
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    monkeypatch.setattr(dt, "_solid_plan", lambda o, *_a: Polygon(plans[str(o.id)]))
    monkeypatch.setattr("auto_patch_v2.planar.deck_bridge.co_placed", lambda a, b, tol: True)
    out, _n = dt._one_decision(gens, (), [body, rail, tower], object(), _airport(),
                              load_default())
    hidden = {h[0] for d in out for h in d.hides}
    assert {"b", "r"} <= hidden and "t" not in hidden


def test_a_mate_drawing_pieces_at_other_sites_is_hidden_only_on_our_decks(monkeypatch):
    """KDFW 224.obj: 96 triangles over 0.9 x 2.8 km, 567 m2 of its solid
    under the four decks -- under half of it there, so never hidden whole
    (20u); its pieces on our decks are (a piece-wise ``hides`` row)."""
    gens = [DeckBridge("o4gen_0", "objects/o4_generated/deck_0.obj", (),
                       _rect(-40.0, -20.0, 38.0, 20.0), (), (), 0.0, 0.0, -5.2, 199.0,
                       witness=GENERATED_WITNESS,
                       covered=(("-1", (("highway", "service"),), ((0.0, -30.0), (0.0, 30.0))),))]
    body, rail = _placement("b", "220.obj"), _placement("r", "224.obj")
    plans = {"b": _rect(-40.0, -20.0, 38.0, 20.0), "r": _rect(-40.0, -900.0, 38.0, 900.0)}
    solid = box(-30.0, -2.0, 30.0, 2.0).union(box(-30.0, 800.0, 30.0, 880.0))

    term = _placement("t", "130.obj")                   # a terminal's wall reaches the deck
    plans["t"] = _rect(-40.0, -900.0, 38.0, 900.0)

    def top(o, cache, law, lo, hi):
        if hi == float("inf"):
            return None
        return {"b": box(-40.0, -20.0, 38.0, 20.0),
                "r": box(-30.0, -2.0, 30.0, 2.0)}.get(str(o.id))
    monkeypatch.setattr(dt, "_body_top", top)
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    monkeypatch.setattr(dt, "_solid_plan",
                        lambda o, *_a: solid if str(o.id) in ("r", "t") else None)
    monkeypatch.setattr("auto_patch_v2.planar.deck_bridge.co_placed", lambda a, b, tol: True)
    out, notes = dt._one_decision(gens, (), [body, rail, term], object(), _airport(),
                                  load_default())
    rows = {h[0]: h for h in out[0].hides}
    assert len(rows["b"]) == 3 and len(rows["r"]) == 4          # the piece-wise row
    assert "t" not in rows                    # no deck-level top there: never a piece
    assert any("pieces at other sites" in n for n in notes)


def test_a_piece_wise_hide_drops_only_the_split_bodies_within_its_plan():
    from auto_patch_v2.airport import dsf_row_hide as H
    from auto_patch_v2.model.placement import Anchor, Body, PlacementRef, Split
    near = Body("b0", "deck", (0,), Anchor(-97.0400, 32.8800, 0.0), "foot", "224__b0_a.obj")
    far = Body("b1", "deck", (1,), Anchor(-97.0400, 32.9000, 0.0), "foot", "224__b1_b.obj")
    sp = Split(PlacementRef(1385, "Objects/224.obj", -97.05, 32.89, 0.0), (near, far))
    within = ((-97.041, 32.879), (-97.039, 32.879), (-97.039, 32.881), (-97.041, 32.881))
    piece = [("Objects/224.obj", -97.05, 32.89, within)]
    assert H.pieces_within(piece, (sp,)) == [("224__b0_a.obj", -97.04, 32.88)]
    text = _text(("224__b0_a.obj", -97.04, 32.88), ("224__b1_b.obj", -97.04, 32.90))
    assert len(H.drawn_pieces(text, piece, (sp,))) == 1
    out, _n = H.hide_rows(text, H.pieces_within(piece, (sp,)))
    assert H.drawn_pieces(out, piece, (sp,)) == [] and "-97.040000000 32.900000000" in out
    # no split written: its pieces on the deck are still drawn, named
    whole = _text(("Objects/224.obj", -97.05, 32.89))
    assert len(H.drawn_pieces(whole, piece, ())) == 1
