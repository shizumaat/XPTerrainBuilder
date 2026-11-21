"""The Beta 8 fallback (owner 2026-11-19T13:51Z; RULINGS 2026-11-19m (2)):
a pack's WALLED MULTI-BRIDGE FRAME our generated decks can take is hidden,
and the generated decks carry it (``planar/deck_takeover``).

Synthetic: walled pieces of one frame along a road on x, walls at u = +-15
over the whole stretch (``deck_bridge._walled_trench``)."""
from __future__ import annotations

import dataclasses
import types

from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
from auto_patch_v2.planar import deck_takeover as dt

GAP = 0.6


@dataclasses.dataclass(frozen=True)
class _Cl:
    cells: tuple


def _deck(s0: float, oid: str = "o", walls: bool = True, u0: float = -20.0,
          u1: float = 20.0, members=("o", "o2")) -> DeckBridge:
    """A walled deck piece across the road: s (x) in [s0, s0 + 10], u (y)
    in [u0, u1]; the frame's walls at u = +-15 from s -50 to 150."""
    ring = ((s0, u0), (s0 + 10.0, u0), (s0 + 10.0, u1), (s0, u1))
    sa = tuple((s0 + d, u0) for d in (2.0, 5.0, 8.0))
    sb = tuple((s0 + d, u1) for d in (2.0, 5.0, 8.0))
    faces = ((-15.0, -50.0, 150.0), (15.0, -50.0, 150.0))
    return DeckBridge(oid, "frame.obj", members, ring, sa, sb, 0.0, 0.0, -5.05, 199.0,
                      walls=((1.0, 0.0), (0.0, 1.0), faces, ()) if walls else ())


def _gen(s0: float, hid: str = "g") -> DeckBridge:
    ring = ((s0, -18.0), (s0 + 10.0, -18.0), (s0 + 10.0, 18.0), (s0, 18.0))
    return DeckBridge(f"o4gen_{hid}", f"objects/o4_generated/deck_{hid}.obj", (), ring,
                      ((s0, -18.0),), ((s0, 18.0),), 0.0, 0.0, -5.2, 199.0,
                      witness=GENERATED_WITNESS)


def test_two_walled_bridges_apart_along_one_trench_are_a_multi_bridge_frame():
    got = dt._multibridge_frames([_deck(0.0), _deck(60.0)], GAP)
    assert len(got) == 1 and len(got[0]) == 2


def test_one_bridge_is_no_multi_bridge_frame():
    assert dt._multibridge_frames([_deck(0.0)], GAP) == []


def test_bridges_side_by_side_over_one_crossing_are_no_multi_bridge_frame():
    """Two pieces at the same station along the road (one taxiway over a
    dual carriageway): no open walled stretch between them."""
    assert dt._multibridge_frames([_deck(0.0, u0=-20.0, u1=-1.0),
                                  _deck(0.0, u0=1.0, u1=20.0)], GAP) == []


def test_wall_less_bridges_are_no_multi_bridge_frame():
    assert dt._multibridge_frames([_deck(0.0, walls=False), _deck(60.0, walls=False)],
                                 GAP) == []


def test_a_trench_object_states_the_walls_of_its_frame():
    """Bridges whose walls no wall pair reads (a co-placed trench object's
    frame, RULINGS 2026-11-19a): the trench object's plan between them
    walls the stretch; bridges past its plan are not one trench."""
    from shapely.geometry import box
    a, b = _deck(0.0, walls=False), _deck(60.0, walls=False)
    tr = types.SimpleNamespace(object_id="o2", outline=box(-5.0, -25.0, 75.0, 25.0))
    assert len(dt._multibridge_frames([a, b], GAP, [tr])) == 1
    off = types.SimpleNamespace(object_id="o2", outline=box(-5.0, -25.0, 20.0, 25.0))
    assert dt._multibridge_frames([a, b], GAP, [off]) == []
    other = types.SimpleNamespace(object_id="zz", outline=box(-5.0, -25.0, 75.0, 25.0))
    assert dt._multibridge_frames([a, b], GAP, [other]) == []


def test_paved_over_paves_a_hidden_plate_where_no_cell_owns_it():
    """The plate continues the paved cell beside it; the road ribbon under
    it keeps its own cell."""
    from auto_patch_v2.classify.roles import Cell
    from shapely.geometry import box

    def cell(role, ref, x0, y0, x1, y1):
        p = box(x0, y0, x1, y1)
        return Cell(1, role, ref, tuple(p.exterior.coords)[:-1], (), 3, "C", "airside",
                    "slice", {})
    cl = _Cl((cell("primary_parallel", "twy", -40.0, -10.0, 0.0, 10.0),
                                      cell("service_road", "road", 10.0, -20.0, 14.0, 20.0)))
    plate = types.SimpleNamespace(hard_deck=box(0.0, -10.0, 30.0, 10.0), id="o")
    got, notes = dt._paved_over(cl, [plate], load_default())
    new = got.cells[2:]
    assert {c.role for c in new} == {"primary_parallel"} and {c.ref for c in new} == {"twy"}
    import shapely
    assert abs(sum(shapely.Polygon(c.ring).area for c in new) - (600.0 - 80.0)) < 1e-6
    assert "paved" in notes[0]
    alone, none = dt._paved_over(_Cl(cl.cells[1:]), [plate],
                                load_default())
    assert len(alone.cells) == 1 and none == []


def test_two_frames_are_read_apart():
    """Two single-bridge objects over one walled road are two frames."""
    assert dt._multibridge_frames([_deck(0.0, "a"), _deck(60.0, "b")], GAP) == []


def test_generated_decks_are_never_a_frame():
    g1, g2 = _gen(0.0, "1"), _gen(60.0, "2")
    assert dt._multibridge_frames([g1, g2], GAP) == []


def _take() -> dt._Takeover:
    a, b = _deck(0.0), _deck(60.0)
    return dt._Takeover("o", "frame.obj",
                       (("o", "frame.obj", (-87.9, 41.98)), ("o2", "bed.obj", (-87.9, 41.98))),
                       (((-5.0, -40.0), (75.0, -40.0), (75.0, 40.0), (-5.0, 40.0)),),
                       (a, b))


def test_attach_hides_the_frame_with_the_first_deck_standing_on_it():
    law = load_default()
    gen = (_gen(200.0, "far"), _gen(0.0, "w"), _gen(60.0, "e"))
    got, notes = dt._attach(gen, [_take()], law)
    far, w, e = got
    assert far.hides == () and far.replaces == () and e.hides == ()
    assert [h[0] for h in w.hides] == ["o", "o2"] and w.replaces == ("o", "o2")
    assert len(w.hidden_plans) == 1
    assert "o4gen_w, o4gen_e" in notes[0]
    assert dt.hidden_ids(got) == {"o", "o2"}


def test_attach_names_a_frame_no_deck_stands_on():
    law = load_default()
    got, notes = dt._attach((_gen(200.0, "far"),), [_take()], law)
    assert got[0].hides == () and "no generated deck stands on its bridges" in notes[0]


def test_without_drops_only_the_hidden_placements():
    objs = [types.SimpleNamespace(id=i) for i in ("o", "o2", "x")]
    assert [o.id for o in dt._without(objs, {"o", "o2"})] == ["x"]
    assert dt._without(objs, set()) is objs


def test_stage_one_reads_the_hidden_set_off_the_full_map():
    from auto_patch_v2.model.stage_one import from_full
    full = types.SimpleNamespace(decks=(dataclasses.replace(_gen(0.0), replaces=("o", "o2")),))
    objs = [types.SimpleNamespace(id=i) for i in ("o", "o2", "x")]
    with from_full(full):
        kept, cl, notes = dt.full_hidden(objs, None, None, load_default())
    assert [o.id for o in kept] == ["x"] and cl is None and notes == []
    assert dt.full_hidden(objs, None, None, load_default())[0] is objs     # no full map


def test_stage_one_hides_what_the_one_decision_hid_not_only_the_frames():
    """KRDU STH_TML obj140 (+ obj141 / obj142): a combined frame dropped by
    the span bands rides a generated deck's ``hides``, never its
    ``replaces`` -- stage 1's map still read it (lane lkrdue).  A ``hides``
    row with a ``within`` plan (a piece) keeps its placement."""
    from auto_patch_v2.model.stage_one import from_full
    g = dataclasses.replace(_gen(0.0), replaces=("o",), hides=(
        ("o", "a.obj", (0.0, 0.0)), ("c140", "STH_TML.obj", (0.0, 0.0)),
        ("c141", "r.obj", (0.0, 0.0)), ("p", "plate.obj", (0.0, 0.0), ((0.0, 0.0),))))
    assert dt.hidden_ids((g,)) == {"o", "c140", "c141"}
    objs = [types.SimpleNamespace(id=i) for i in ("o", "c140", "c141", "p", "x")]
    with from_full(types.SimpleNamespace(decks=(g,))):
        kept = dt.full_hidden(objs, None, None, load_default())[0]
    assert [o.id for o in kept] == ["p", "x"]
    assert [o.id for o in dt.without_hidden(objs, (g,))] == ["p", "x"]


def test_without_hands_every_pass_one_list():
    objs = [types.SimpleNamespace(id=i) for i in ("o", "x")]
    cache = types.SimpleNamespace(placed={})
    a, b = dt._without(objs, {"o"}, cache), dt._without(objs, {"o"}, cache)
    assert a is b and [o.id for o in a] == ["x"]


def test_take_frames_leaves_an_object_floors_frame_alone(monkeypatch):
    seen = {}

    def fake(objects, *a, **k):
        seen["ids"] = [o.id for o in objects]
        return (), []
    monkeypatch.setattr(dt, "_takeovers", fake)
    objs = [types.SimpleNamespace(id=i) for i in ("o", "x")]
    got = dt.take_frames(objs, None, None, None, load_default(), {"o"}, [])
    assert seen["ids"] == ["x"] and got[0] is objs and got[2] == ()


def _frames_fixture(monkeypatch, gen_rings):
    """``takeovers`` over a stubbed pack read: one frame of two walled
    bridges (placements o, o2) and generated decks at ``gen_rings``."""
    hd = types.SimpleNamespace(is_empty=False)
    objs = [types.SimpleNamespace(id="o", path="frame.obj", xy=(0.0, 0.0), resolved=None,
                                  hard_deck=hd),
            types.SimpleNamespace(id="o2", path="bed.obj", xy=(0.0, 0.0), resolved=None,
                                  hard_deck=None),
            types.SimpleNamespace(id="x", path="other.obj", xy=(500.0, 0.0), resolved=None,
                                  hard_deck=None)]
    seen = {}
    monkeypatch.setattr(dt, "_frames", lambda o, tol: [([objs[0]], objs[:2])])
    monkeypatch.setattr(dt, "_pieces", lambda decks: 2)
    monkeypatch.setattr(dt, "deck_bridges", lambda *a, **k: ((_deck(0.0), _deck(60.0)), []))
    monkeypatch.setattr(dt, "_trenches", lambda *a: [])
    monkeypatch.setattr(dt, "_paved_over", lambda cl, hidden, law, airport=None: (cl, []))

    monkeypatch.setattr(dt, "roads_under", lambda spans, ap, law: [])

    def gen(cl, ap, law, taken, blocked, objects, cache, covered=()):
        seen["objects"] = [o.id for o in objects]
        return tuple(_gen(s, str(k)) for k, s in enumerate(gen_rings)), []
    monkeypatch.setattr(dt, "generated_decks", gen)
    airport = types.SimpleNamespace(
        frame=types.SimpleNamespace(
            transformers=lambda: (None, lambda x, y: (41.0 + y, -87.0 + x))),
        pack=types.SimpleNamespace(name="Some Pack"), dem=None)
    return objs, airport, seen


def test_takeovers_hide_a_frame_every_bridge_of_which_a_generated_deck_takes(monkeypatch):
    objs, airport, seen = _frames_fixture(monkeypatch, (0.0, 60.0))
    takes, notes = dt._takeovers(objs, object(), types.SimpleNamespace(cells=(1,)), airport,
                                load_default())
    assert seen["objects"] == ["x"]                 # the probe reads the pack without it
    (t,) = takes
    assert [m[0] for m in t.members] == ["o", "o2"] and t.members[0][2] == (-87.0, 41.0)
    assert any("HIDDEN" in n for n in notes)
    assert sum("multi-bridge frame hidden: pack Some Pack" in n for n in notes) == 2


def test_takeovers_keep_a_frame_one_bridge_of_which_no_generated_deck_takes(monkeypatch):
    objs, airport, _seen = _frames_fixture(monkeypatch, (0.0,))
    takes, notes = dt._takeovers(objs, object(), types.SimpleNamespace(cells=(1,)), airport,
                                load_default())
    assert takes == () and any("KEPT" in n for n in notes)


def test_roads_under_take_only_a_way_crossing_the_bridge_midline():
    """The road under a bridge crosses its midline (``deck_bores``'
    reading); a short link ending under the deck short of it is not one."""
    deck = _deck(0.0)                      # ring s 0..10, u -20..20; road along s
    way = types.SimpleNamespace
    airport = types.SimpleNamespace(osm_ways=[
        way(id=-1, tags={"highway": "primary"}, points=[(-30.0, 0.0), (40.0, 0.0)]),
        way(id=-2, tags={"highway": "service"}, points=[(-30.0, 5.0), (3.0, 5.0)]),
        way(id=-3, tags={"aeroway": "taxiway"}, points=[(5.0, -40.0), (5.0, 40.0)])])
    got = dt.roads_under([deck], airport, load_default())
    assert [r.id for r in got] == ["-1"]
    assert abs(got[0].line.length - 10.0) < 1e-9 and got[0].parent.length == 70.0


# ── ONE DECISION PER CROSSING (owner RULINGS 2026-11-20a (1), #2191) ──────

def _placement(oid: str, path: str, xy=(5.0, 0.0), hdg: float = 0.0, bbox=True):
    from shapely.geometry import box
    return types.SimpleNamespace(id=oid, path=path, xy=xy, heading_deg=hdg, resolved=path,
                                 plan_bbox=box(-50.0, -50.0, 60.0, 50.0) if bbox else None,
                                 anchor_z=190.0, agl_m=0.0)


def _airport():
    return types.SimpleNamespace(
        dem=types.SimpleNamespace(z=lambda x, y: 199.0),
        frame=types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y, x))))


def test_one_decision_hides_a_pack_bridge_over_our_crossing_with_its_mates(monkeypatch):
    """KMCO ``puente.obj`` (no hard deck: the deck law cannot seat it) draws
    the taxiway's deck over the road our deck spans: hidden with its
    co-placed ``_luz`` lights; a lamp elsewhere stays."""
    from shapely.geometry import box
    g = dataclasses.replace(_gen(0.0), covered=(("-1", (("highway", "service"),),
                                                 ((5.0, -30.0), (5.0, 30.0))),))
    body, luz = _placement("b", "puente.obj"), _placement("l", "puente_luz.obj")
    lamp = _placement("x", "lamp.obj", xy=(40.0, 40.0))
    tops = {"b": box(-2.0, -20.0, 12.0, 20.0)}
    monkeypatch.setattr(dt, "_body_top", lambda o, *_a: tops.get(str(o.id)))
    # the lights carry no solid (their plan is none)
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: None if str(o.id) == "l"
                        else ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)))
    law = load_default()
    out, notes = dt._one_decision([g], (), [body, luz, lamp], object(), _airport(), law)
    assert [h[0] for h in out[0].hides] == ["b", "l"]
    assert out[0].pack_under == ()
    assert any("HIDDEN" in n for n in notes)


def test_one_decision_counts_a_pack_top_left_under_our_deck_as_a_defect(monkeypatch):
    """A deck-level top under the footprint that does not span the road is
    no bridge to hide -- and the pack's and ours both stand there: the
    build records it (``pack_under``, census ``pack_bridge_under_deck``)."""
    from shapely.geometry import box
    g = dataclasses.replace(_gen(0.0), covered=(("-1", (("highway", "service"),),
                                                 ((5.0, -30.0), (5.0, 30.0))),))
    shed = _placement("s", "shed.obj")
    monkeypatch.setattr(dt, "_body_top", lambda o, *_a: box(0.0, 8.0, 10.0, 17.0))
    out, _n = dt._one_decision([g], (), [shed], object(), _airport(), load_default())
    assert out[0].hides == () and [u[0] for u in out[0].pack_under] == ["s"]


def test_a_shared_anchor_is_no_frame(monkeypatch):
    """lmslframe (D): KDFW places ~150 objects on one anchor -- hiding the
    bridge body hides its overlapping plate mate, never a stranger there,
    nor a lights object once a stranger shares the anchor."""
    from shapely.geometry import box
    g = dataclasses.replace(_gen(0.0), covered=(("-1", (("highway", "service"),),
                                                 ((5.0, -30.0), (5.0, 30.0))),))
    body, plate = _placement("b", "bridge.obj"), _placement("p", "plate.obj")
    lights, terminal = _placement("l", "lights.obj"), _placement("t", "terminal.obj")
    tops = {"b": box(-2.0, -20.0, 12.0, 20.0)}
    plans = {"b": ((-2.0, -20.0), (12.0, -20.0), (12.0, 20.0)),
             "p": ((0.0, -10.0), (10.0, -10.0), (10.0, 10.0)),
             "t": ((300.0, 300.0), (400.0, 300.0), (400.0, 400.0))}
    monkeypatch.setattr(dt, "_body_top", lambda o, *_a: tops.get(str(o.id)))
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    out, _n = dt._one_decision([g], (), [body, plate, lights, terminal], object(), _airport(),
                              load_default())
    assert sorted(h[0] for h in out[0].hides) == ["b", "p"]


def test_a_giant_shared_anchor_plate_never_hides_the_terminal(monkeypatch):
    """MEASURED KDFW 1.0.569 (lane lcross22; owner 2026-11-20T22:39Z "make
    sure we're not hiding half the airport pack"): the bridge plate (a
    313 x 176 m plan) shares one anchor with 100 terminal objects whose
    plans it overlaps -- the hide takes the plate and its piece riding the
    deck, never a terminal object beside the crossing nor a building."""
    from shapely.geometry import box
    g = dataclasses.replace(_gen(0.0), covered=(("-1", (("highway", "service"),),
                                                 ((5.0, -30.0), (5.0, 30.0))),))
    plate = _placement("p220", "220.obj")
    piece = _placement("p221", "221.obj")
    terms = [_placement(f"t{k}", f"{110 + k}.obj") for k in range(100)]
    tower = _placement("tw", "tower.obj")
    tops = {"p220": box(-150.0, -88.0, 163.0, 88.0)}
    rect = lambda x0, y0, x1, y1: ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    plans = {"p220": rect(-150.0, -88.0, 163.0, 88.0), "p221": rect(0.0, -10.0, 10.0, 10.0),
             "tw": rect(1.0, -2.0, 9.0, 2.0)}
    plans.update({f"t{k}": rect(20.0 + 10 * (k % 10), -80.0 + 10 * (k // 10),
                                28.0 + 10 * (k % 10), -72.0 + 10 * (k // 10))
                  for k in range(100)})

    def top(o, cache, law, lo, hi):
        if str(o.id) == "tw" and hi == float("inf"):
            return box(1.0, -2.0, 9.0, 2.0)          # a roof high over the deck
        return tops.get(str(o.id)) if hi != float("inf") else None
    monkeypatch.setattr(dt, "_body_top", top)
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    objs = [plate, piece, tower, *terms]
    out, notes = dt._one_decision([g], (), objs, object(), _airport(), load_default())
    assert sorted(h[0] for h in out[0].hides) == ["p220", "p221"]
    assert any("pack placements hidden: 2 of 103" in n for n in notes)


def test_the_hide_guard_keeps_only_the_bodies_past_its_share():
    """The backstop: hides past ``[deck_gen] hide_max_share`` of the pack
    keep only the bridge bodies (their mates stay drawn)."""
    law = load_default()
    hides = tuple((f"m{k}", "m.obj", (0.0, 0.0)) for k in range(30))
    d = dataclasses.replace(_gen(0.0), hides=(("b", "b.obj", (0.0, 0.0)),) + hides)
    notes: list = []
    (kept,) = dt._capped([d], list(range(100)), {"b"}, notes, law)
    assert [h[0] for h in kept.hides] == ["b"] and "DEFECT" in notes[0]
    notes = []
    (same,) = dt._capped([d], list(range(2000)), {"b"}, notes, law)
    assert same is d and notes == ["pack placements hidden: 31 of 2000"]


def test_a_frame_takeover_hides_only_what_rides_its_bridges(monkeypatch):
    """A frame's co-placed members far from its bridges (a shared anchor's
    buildings) stay drawn; its deck placement, a bed under its bridges and
    its lights on an anchor no stranger shares go (``_frame_members``)."""
    rect = lambda x0, y0, x1, y1: ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    plans = {"o": rect(0.0, -20.0, 70.0, 20.0), "bed": rect(2.0, -15.0, 68.0, 15.0),
             "far": rect(300.0, 300.0, 400.0, 400.0)}
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    monkeypatch.setattr(dt, "_body_top", lambda *a: None)
    P = lambda i: types.SimpleNamespace(id=i, path=f"{i}.obj", xy=(0.0, 0.0))
    fr = (_deck(0.0), _deck(60.0))
    law = load_default()
    got = dt._frame_members(fr, [P("o"), P("bed"), P("luz")], [], None, law)
    assert [q.id for q in got] == ["o", "bed", "luz"]
    got = dt._frame_members(fr, [P("o"), P("bed"), P("luz"), P("far")], [], None, law)
    assert [q.id for q in got] == ["o", "bed"]


# ── A SPAN BAND OUR DECK TAKES (#2202 KRDU STH_TML, lane lcross22) ─────────

def _span_piece(s0: float, s1: float, oid: str = "o140", cut_spans=((0.0, 10.0), (60.0, 70.0))):
    """A piece of a pack frame cut to its spans (18i): its axis along x
    from (0, 0) to (100, 0), this piece over span [s0, s1]."""
    ring = ((s0, -20.0), (s1, -20.0), (s1, 20.0), (s0, 20.0))
    return DeckBridge(oid, "STH_TML.obj", (oid, "o141"), ring, ((s0, -20.0),), ((s1, -20.0),),
                      0.0, 0.0, -5.0, 199.0,
                      span_cut=((0.0, 0.0), (100.0, 0.0), cut_spans, 0.015))


def _ll(x, y):
    return (35.0 + y * 1e-5, -78.0 + x * 1e-5)


def test_a_combined_frame_one_span_of_which_our_deck_takes_is_dropped_whole(monkeypatch):
    """Owner 2026-11-20T23:53Z (KRDU south STH_TML, #2202 items 2-3): our
    deck takes one span of the pack's combined deck -- the WHOLE object
    goes (no piece kept, not the raised middle), its riders with it, a
    terminal on the anchor stays; the span no deck of ours takes is named."""
    law = load_default()
    rect = lambda x0, y0, x1, y1: ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    plans = {"o140": rect(0.0, -20.0, 70.0, 20.0), "o141": rect(2.0, -18.0, 68.0, 18.0),
             "t": rect(300.0, 300.0, 400.0, 400.0)}
    monkeypatch.setattr(dt, "_plan", lambda o, *_a: plans.get(str(o.id)))
    monkeypatch.setattr(dt, "_body_top", lambda *a: None)
    P = lambda i: types.SimpleNamespace(id=i, path=f"{i}.obj", xy=(50.0, 0.0))
    a = dataclasses.replace(_span_piece(0.0, 10.0), members=("o140", "o141", "t"))
    b = dataclasses.replace(_span_piece(60.0, 70.0), members=("o140", "o141", "t"))
    out, notes = dt._span_bands((a, b, _gen(0.0)), [P("o140"), P("o141"), P("t")], None, law,
                               _ll)
    (g,) = out
    assert sorted(h[0] for h in g.hides) == ["o140", "o141"]
    assert any("whole object is HIDDEN" in n and "no generated deck takes span(s) 60-70 m"
               in n for n in notes)


def test_a_frame_cut_to_two_spans_is_a_combined_frame():
    """The full map's takeover reads it as a multi-bridge frame (hidden
    whole where our decks take every span)."""
    assert dt._combined([_span_piece(0.0, 10.0), _span_piece(60.0, 70.0)])
    assert not dt._combined([_span_piece(0.0, 10.0, cut_spans=((0.0, 10.0),))])
    assert len(dt._multibridge_frames([_span_piece(0.0, 10.0), _span_piece(60.0, 70.0)],
                                      GAP)) == 1


def test_a_span_band_left_under_our_deck_is_counted():
    """The census family counts a hard-deck span band (the bar previously
    passed by construction): a band under our deck that is not the span
    it stands over (a cut whose span reading misses it) is ``pack_under``."""
    law = load_default()
    d = _span_piece(0.0, 10.0, cut_spans=((40.0, 50.0),))       # no span holds it
    out, _n = dt._span_bands((d, _gen(0.0)), [], None, law, _ll)
    assert [u[0] for u in out[1].pack_under] == ["o140"]


def test_crossings_one_road_part_is_no_linemerge_error(monkeypatch):
    """#2220 (CYYZ 1.0.571): a single road part under a deck unions to a bare
    LineString, which shapely's linemerge refuses; it counts as one road."""
    from shapely import LineString, Polygon
    from auto_patch_v2.planar import deck_takeover as dt
    monkeypatch.setattr(dt, "deck_polygon", lambda db: Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]))
    assert dt._crossings(object(), [LineString([(-5, 5), (15, 5)])]) == 1
