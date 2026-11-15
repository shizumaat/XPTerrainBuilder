"""#2065 R2 twins (spec ``2065-bridge-class-A1.md`` §A4 S1 / S2 / S4): the
pack-stage read of a free bridge (``planar/free_bridge``) on a synthetic
pack, the planar stage's precedence (``admitted``), the publication of its
route ends on the rebake plan member (``published`` ->
``rebake_plan.with_free``) and the plan's round trip."""
from __future__ import annotations

import types

from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport.rebake_plan import with_free
from auto_patch_v2.model.free_bridge import FREE_PLATE, published
from auto_patch_v2.model.rebake import PLAN_VERSION, Member, RebakePlan, Unit
from auto_patch_v2.planar import free_bridge as FBR
from shapely.geometry import Polygon
from shapely.geometry import box as _box
from tests.auto_patch_v2.test_overpass_deck1692 import FRAME, LAW, THICK


def _way(i, pts, **tags):
    return types.SimpleNamespace(id=i, points=tuple(pts), tags=dict(tags))


def _obj(path, x0, z0, x1, z1, y):
    """An OBJ8 of one ``ATTR_hard_deck`` plate at authored height ``y``."""
    a, b, c, d = (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)
    verts = [a, b, c, a, c, d]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {len(verts)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _pack(tmp_path, run_on: float):
    """A 60 x 12 m plate at y 6 over a service road, on a mapped bridge that
    runs ``run_on`` m past its east end, with a lamp on its anchor (a frame
    of decks alone is 22d / 22p's)."""
    path = _obj(tmp_path / "deck.obj", -30.0, -6.0, 30.0, 6.0, 6.0)
    lamp = _obj(tmp_path / "lamp.obj", 4.0, -5.5, 4.5, -5.0, 12.0)
    deck = _box(-30.0, -6.0, 30.0, 6.0)
    o = types.SimpleNamespace(
        id="dsf:obj1", path="objects/deck.obj", resolved=path, xy=(0.0, 0.0),
        heading_deg=0.0, kind="OBJECT", anchor_z=0.0, agl_m=0.0, deck_kind="flag",
        hard_deck=deck, deck_top_z=6.0, plan_bbox=deck)
    post = types.SimpleNamespace(
        id="dsf:obj2", path="objects/lamp.obj", resolved=lamp, xy=(0.0, 0.0),
        heading_deg=0.0, kind="OBJECT", anchor_z=0.0, agl_m=0.0, deck_kind="",
        hard_deck=None, deck_top_z=None, plan_bbox=_box(4.0, 5.0, 4.5, 5.5))
    ways = [_way(1, [(-80.0, 0.0), (-30.5, 0.0)], highway="primary"),
            _way(2, [(-30.5, 0.0), (30.0 + run_on, 0.0)], highway="primary",
                 bridge="yes", layer="1"),
            _way(3, [(30.0 + run_on, 0.0), (150.0, 0.0)], highway="primary"),
            _way(9, [(0.0, -40.0), (0.0, 40.0)], highway="service")]
    airport = types.SimpleNamespace(frame=FRAME, osm_ways=tuple(ways), dem=None,
                                    deck_stacks=(), pavements=(), runways=(),
                                    free_bridges=())
    return airport, [o, post], O.ResourceCache(THICK)


def test_a_plate_on_a_mapped_bridge_ending_at_it_is_a_free_bridge(tmp_path):
    airport, objs, cache = _pack(tmp_path, 0.5)
    got, _kept, notes = FBR._read_free_bridges(airport, objs, cache, LAW)
    assert len(got) == 1 and got[0].deck_ids() == ("dsf:obj1",), notes
    (d,) = got[0].decks
    assert set(d.ways) >= {2} and len(d.ends) == 2 and all(e.land for e in d.ends)
    assert all(abs(e.top - 6.0) < 1e-6 for e in d.ends)
    assert {round(abs(e.stations[0][0])) for e in d.ends} == {30}


def test_a_plate_the_mapped_bridge_runs_on_past_is_no_free_bridge(tmp_path):
    """W7: the structure carries on 60 m past the east end: a joint."""
    airport, objs, cache = _pack(tmp_path, 60.0)
    got, _kept, notes = FBR._read_free_bridges(airport, objs, cache, LAW)
    assert got == () and any("W7" in n for n in notes)


def test_a_plate_with_pavement_on_it_is_left_to_class_a(tmp_path):
    airport, objs, cache = _pack(tmp_path, 0.5)
    pav = types.SimpleNamespace(outer=((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0),
                                       (-10.0, 10.0)), holes=())
    airport.pavements = (pav,)
    assert FBR._read_free_bridges(airport, objs, cache, LAW) == ((), (), [])


def test_the_planar_stage_takes_cut_and_class_a_frames_first(tmp_path):
    airport, objs, cache = _pack(tmp_path, 0.5)
    got, _kept, _n = FBR._read_free_bridges(airport, objs, cache, LAW)
    kept, _n = FBR.admitted(got, objs, None, airport)
    assert kept == got
    hard = types.SimpleNamespace(object_id="dsf:obj7", members=("dsf:obj1", "dsf:obj7"))
    assert FBR.admitted(got, objs, None, airport, decks=(hard,))[0] == ()
    assert FBR.admitted(got, objs, None, airport, cut_objects=("dsf:obj1",))[0] == ()


def _member(**kw):
    base = dict(id="dsf:obj1", resource="objects/deck.obj", authored_path="", live_path="",
                heading_deg=0.0, deck_kind="flag", deck_top_y=6.0,
                deck_ring=((36.0, -86.0), (36.0, -85.999), (36.0001, -85.999)))
    base.update(kw)
    return Member(**base)


def test_the_plan_member_carries_the_route_ends(tmp_path):
    airport, objs, cache = _pack(tmp_path, 0.5)
    got, _kept, _n = FBR._read_free_bridges(airport, objs, cache, LAW)
    rec = published(got, FRAME.transformers()[1], 1.5)["dsf:obj1"]
    assert rec["bridge"] == got[0].id and rec["land"] == [True, True] and len(rec["ends"]) == 2
    counts: dict = {}
    m = with_free(_member(), rec, 5.0, counts)
    assert m.plate_kind == FREE_PLATE and m.free_bridge == got[0].id
    assert m.deck_end_tops == (6.0, 6.0) and m.deck_end_land == (True, True)
    assert len(m.deck_ends) == 2 and len(m.deck_end_stations) >= 6
    # a plated deck keeps its plate's reader; a free member over a graded
    # face is published, its datum cleared and noted (A2)
    assert with_free(_member(plate_kind="split_level"), rec, 5.0, counts).plate_kind \
        == "split_level"
    g = with_free(_member(deck_datum_z=12.0), rec, 5.0, counts)
    assert g.plate_kind == FREE_PLATE and g.deck_datum_z is None
    assert any("12.00" in e for e in g.deck_evidence)
    assert counts == {"free_deck_members": 2, "free_deck_plated": 1,
                      "free_deck_over_graded_face": 1}
    # the plan round-trips the fields at its version
    plan = RebakePlan("ZZZZ", "pack", "/p", (Unit("unit:0", (36.0, -86.0), 0.0, (m,)),),
                      (), {})
    back = RebakePlan.from_json(plan.to_json())
    assert back.units[0].members[0] == m and PLAN_VERSION == 15


def test_the_published_end_chord_lies_outside_the_plate(tmp_path):
    """A2 END GROUND: the chord is the end line's first and last stations
    moved ``free_end_ground_out_m`` along the outward tangent."""
    airport, objs, cache = _pack(tmp_path, 0.5)
    got, _kept, _n = FBR._read_free_bridges(airport, objs, cache, LAW)
    to_ll = FRAME.transformers()[1]
    out = float(LAW.tables.structures.bridge.free_end_ground_out_m)
    rec = published(got, to_ll, out)["dsf:obj1"]
    for e, chord in zip(got[0].decks[0].ends, rec["ends"], strict=True):
        assert {round(abs(p[0]), 2) for p in (e.stations[0], e.stations[-1])} == {30.0}
        assert {round(abs(p[1]), 2) for p in (e.stations[0], e.stations[-1])} == {6.0}
        x = 30.0 + out if e.out[0] > 0 else -30.0 - out
        want = sorted(round(v, 7) for q in ((x, -6.0), (x, 6.0)) for v in to_ll(*q))
        assert sorted(round(v, 7) for q in chord for v in q) == want


def _two_deck_bridge(tmp_path):
    """Two free decks of ONE frame (one bridge) and a lamp standing on deck
    B; deck A's own ring does not hold the lamp."""
    from auto_patch_v2.model.free_bridge import FreeBridge, FreeDeck
    a = FreeDeck("dsf:a", ((-30.0, -6.0), (0.0, -6.0), (0.0, 6.0), (-30.0, 6.0)), (2,), ())
    b = FreeDeck("dsf:b", ((0.0, -6.0), (30.0, -6.0), (30.0, 6.0), (0.0, 6.0)), (2,), ())
    fb = FreeBridge("free:dsf:a", ("dsf:a", "dsf:b", "dsf:lamp"), (a, b))
    lamp = types.SimpleNamespace(id="dsf:lamp", plan_bbox=_box(10.0, 1.0, 11.0, 2.0))
    deck = [types.SimpleNamespace(id=d.object_id, plan_bbox=_box(*Polygon(d.ring).bounds))
            for d in (a, b)]
    return fb, deck + [lamp]


class _Roles:
    """Every cell under the lamp reads ``building`` (22n's witness)."""

    def at_xy(self, xy):
        return "building" if 9.0 < xy[0] < 12.0 else "apron"


def test_22n_reads_the_union_of_the_frames_free_decks(tmp_path, monkeypatch):
    """A2: a lamp on deck B of a two-deck bridge is inside the bridge."""
    from auto_patch_v2.planar import deck_bridge as DB
    fb, objs = _two_deck_bridge(tmp_path)
    monkeypatch.setattr(DB, "CellRoles", lambda _c, _a: _Roles())
    kept, notes = FBR.admitted((fb,), objs, object(), None)
    assert kept == (fb,), notes
