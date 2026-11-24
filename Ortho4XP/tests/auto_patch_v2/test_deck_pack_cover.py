"""Twins of ``planar/deck_pack_cover`` (#2123 A1 (2) "the pack always
wins"; owner 2026-11-17): the pack's hard deck refuses a generated deck;
a pack structure AND a top over the road refuse it; a cut with no top, a
top with no structure and a depth punch drawn under the terrain do not."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport.obj8 import ObjGeometry, parse_obj8
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.planar.deck_pack_cover import pack_decks_near, pack_refusal
from shapely.geometry import LineString, box

LAW = load_default()
PIECE = box(-20, -20, 20, 20)
ROAD = LineString([(-60, 0), (60, 0)])


def _quad(y: float, half: float) -> tuple[list, list]:
    """An up-facing square at ``y`` (authored x, y, z)."""
    v = [(-half, y, -half), (half, y, -half), (half, y, half), (-half, y, half)]
    return v, [(0, 2, 1), (0, 3, 2)]


def _pit(depth: float, half: float) -> tuple[list, list]:
    """Two walls reaching ``depth`` under the ground."""
    v = [(-half, 0, -half), (half, 0, -half), (half, -depth, -half), (-half, -depth, -half),
         (-half, 0, half), (half, 0, half), (half, -depth, half), (-half, -depth, half)]
    return v, [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]


def _geom(parts, draped=False, under=False) -> ObjGeometry:
    vs, ts, n = [], [], 0
    for v, t in parts:
        vs += v
        ts += [(a + n, b + n, c + n) for a, b, c in t]
        n += len(v)
    tris = np.asarray(ts, dtype=np.int64)
    empty = np.zeros((0, 3), dtype=np.int64)
    k = 0 if draped else len(ts)
    return ObjGeometry("x.obj", np.asarray(vs, dtype=float), empty if draped else tris,
                       np.zeros(k, dtype=np.int8), tris if draped else empty,
                       np.zeros(k, dtype=bool), np.full(k, under, dtype=bool))


def _obj(oid: str, g: ObjGeometry, hard_deck=None):
    return types.SimpleNamespace(id=oid, path=f"{oid}.obj", resolved=oid, xy=(0.0, 0.0),
                                 heading_deg=0.0, hard_deck=hard_deck,
                                 plan_bbox=box(-50, -50, 50, 50)), g


def _refusal(*placed) -> str:
    geoms = {o.resolved: g for o, g in placed}
    cache = types.SimpleNamespace(geometry=lambda r: geoms.get(r))
    packs = pack_decks_near([o for o, _g in placed], cache, LAW, PIECE)
    return pack_refusal(PIECE, [ROAD], packs, LAW, lambda _i: "walled trench")


def test_a_hard_deck_refuses_whether_or_not_it_was_admitted():
    why = _refusal(_obj("hd", _geom([_quad(0.0, 5.0)]), hard_deck=box(-30, -30, 30, 30)))
    assert "hard deck hd" in why and "walled trench" in why


def test_a_structure_with_a_top_over_the_road_is_the_packs_crossing():
    why = _refusal(_obj("walls", _geom([_pit(9.0, 30.0)])),
                   _obj("top", _geom([_quad(0.0, 40.0)], draped=True)))
    assert "models the crossing" in why and "walls" in why and "top" in why


def test_a_cut_with_no_top_leaves_the_deck_ours():
    assert _refusal(_obj("walls", _geom([_pit(9.0, 30.0), _quad(-9.0, 30.0)]))) == ""


def test_a_draped_top_with_no_structure_is_pavement_only():
    assert _refusal(_obj("top", _geom([_quad(0.0, 40.0)], draped=True))) == ""


def test_a_depth_punch_drawn_under_the_terrain_is_no_top():
    """A pit and a near-invisible quad over it, both drawn before the mesh
    (``ATTR_layer_group terrain -1``): the pack fakes a cut; no top."""
    assert _refusal(_obj("pit", _geom([_pit(7.0, 30.0), _quad(0.05, 40.0)], under=True))) == ""


def test_the_parser_marks_triangles_drawn_under_the_terrain(tmp_path):
    p = tmp_path / "punch.obj"
    p.write_text("I\n800\nOBJ\nPOINT_COUNTS 3 0 0 6\n"
                 "VT 0 0 0 0 1 0 0 0\nVT 1 0 0 0 1 0 0 0\nVT 0 0 1 0 1 0 0 0\n"
                 "IDX 0\nIDX 1\nIDX 2\nIDX 0\nIDX 1\nIDX 2\n"
                 "TRIS 0 3\nATTR_layer_group terrain -1\nTRIS 3 3\n"
                 "ATTR_layer_group_draped runways 1\nATTR_layer_group objects 1\n",
                     encoding="utf-8", newline="\n")
    g = parse_obj8(str(p))
    assert g.under_terrain.tolist() == [False, True]


def test_a_faked_cut_under_a_deck_is_named_and_hidden_in_the_pack_copy():
    """The pit drawn under the terrain is a faked cut (owner 2026-11-17,
    KPHX): named for the deck, and its row leaves the DSF dump while the
    definition and every other row stay."""
    from auto_patch_v2.airport import generated_pack as gen
    from auto_patch_v2.planar.deck_pack_cover import faked_cuts

    placed = [_obj("pit", _geom([_pit(7.0, 30.0)], under=True)),
              _obj("punch", _geom([_quad(0.05, 40.0)], under=True)),
              _obj("lamp", _geom([_quad(0.0, 1.0)]))]
    geoms = {o.resolved: g for o, g in placed}
    packs = pack_decks_near([o for o, _g in placed],
                            types.SimpleNamespace(geometry=geoms.get), LAW, PIECE)
    assert sorted(f.object_id for f in faked_cuts(PIECE, packs, LAW)) == ["pit", "punch"]
    alone = [p for p in packs if p.object_id == "punch"]
    assert faked_cuts(PIECE, alone, LAW) == []        # a punch with no pit fakes nothing
    o2, g2 = _obj("walls", _geom([_pit(7.0, 30.0)]))
    packs2 = pack_decks_near([o2], types.SimpleNamespace(geometry=lambda _r: g2), LAW, PIECE)
    assert faked_cuts(PIECE, packs2, LAW) == []
    dump = ("OBJECT_DEF Digging/Test.obj\nOBJECT_DEF a.obj\n"
            "OBJECT 0 -112.004276046 33.435438523 90.0\n"
            "OBJECT 1 -112.004276046 33.435438523 0.0\n"
            "OBJECT 0 -112.100000000 33.400000000 0.0\n")
    text, counts = gen.apply_text(dump, {"hides": [
        {"object_id": "pit", "resource": "Digging/Test.obj",
         "lon": -112.0042760461955, "lat": 33.43543852263106}]})
    assert counts["hidden"] == 1
    assert "OBJECT_DEF Digging/Test.obj" in text and "OBJECT 1 -112.004276046" in text
    assert "OBJECT 0 -112.004276046" not in text and "OBJECT 0 -112.100000000" in text


def _beside_refusal(deck, road=ROAD, reach=120.0) -> str:
    """(c) RULINGS 2026-11-17n: a pack hard deck ``deck`` (frame plan) beside
    PIECE, the covered road's mapped line ``road``."""
    o, g = _obj("hd", _geom([_quad(0.0, 5.0)]), hard_deck=deck)
    o.plan_bbox = deck.envelope
    cache = types.SimpleNamespace(geometry=lambda r: g)
    packs = pack_decks_near([o], cache, LAW, PIECE.buffer(reach))
    return pack_refusal(PIECE, [ROAD], packs, LAW, lambda _i: "", [road], reach)


def test_a_hard_deck_touching_the_ring_refuses_it():
    """LPMA: the pack draws the platform beside the runway; a hard deck
    within the ring's growth (bearing + edge margin, 3.5 m) abuts it."""
    assert "abuts it (3.0 m" in _beside_refusal(box(23, -40, 60, 40),
                                                LineString([(0, 30), (1, 30)]))


def test_a_hard_deck_over_the_covered_road_within_the_approach_run_refuses_it():
    """LPMA ``-23``: the road under the generated piece runs on 105 m under
    ``runway23_area``'s hard deck 11.45 m beside it."""
    why = _beside_refusal(box(31.5, -40, 200, 40), LineString([(-60, 0), (400, 0)]))
    assert "runs 108 m on under the pack's hard deck hd" in why and "11.5 m beside" in why


def test_a_hard_deck_beside_it_over_another_road_or_beyond_the_run_leaves_it_ours():
    off_road = box(31.5, 10, 200, 40)                   # beside, not over the road
    assert _beside_refusal(off_road) == ""
    far = box(150, -40, 300, 40)                         # over the road, past the run
    assert _beside_refusal(far, LineString([(-60, 0), (400, 0)])) == ""


def test_a_resources_cover_is_read_once_and_placed_per_object(monkeypatch):
    # #2206 step 2: the authored-frame union is held per geometry; every
    # placement is the one a fresh read gives
    import types as _ty

    from auto_patch_v2.planar import deck_pack_cover as dpc
    g = _geom([_quad(0.5, 10.0), _pit(6.0, 10.0)])
    objs = [_ty.SimpleNamespace(id=f"o{i}", xy=(30.0 * i, 5.0), heading_deg=17.0 * i)
            for i in range(3)]
    fresh = [dpc._placed(o, dpc._local_cover(g, 2.0, None, float(
        LAW.tables.structures.bridge.deck_plate_normal_y_min)), LAW) for o in objs]
    calls = []
    real = dpc._local_cover
    monkeypatch.setattr(dpc, "_local_cover", lambda *a: calls.append(1) or real(*a))
    got = [dpc._cover_plan(o, g, LAW, 2.0) for o in objs]
    assert len(calls) == 1
    assert [p.wkb_hex for p in got] == [p.wkb_hex for p in fresh]
    dpc._cover_plan(objs[0], g, LAW, 2.0, 0.25)
    assert len(calls) == 2                    # another floor is another reading
