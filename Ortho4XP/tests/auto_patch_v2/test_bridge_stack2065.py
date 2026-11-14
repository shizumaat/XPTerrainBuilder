"""#2065 A3 (spec ``docs/specs/2065-bridge-class-A3.md`` C3): the grade-up to
every bridge end — the land-end states (``airport/bridge_end_state``), the
floorless free / kept stack's ground (``geom/deck_ground``), its rows
(``constraints/deck_stack``), the way rewrite (``airport/deck_stack``) and the
crossing seeds (``airport/deck_ends``).  Synthetic, headless."""
from __future__ import annotations

import dataclasses as dc
import math
import types

import numpy as np
from auto_patch_v2.airport import bridge_end_state as BES
from auto_patch_v2.airport import deck_ends as DE
from auto_patch_v2.airport import deck_stack as DS
from auto_patch_v2.constraints.deck_stack import deck_stack_rows
from auto_patch_v2.geom.deck_ground import ground_footprint
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.deck_stack import (FREE, KEPT, DeckStack, StackDeck, StackEnd,
                                            live_stacks)
from shapely.geometry import LineString, Point, Polygon, box

LAW = Law.for_airport("")
BR = LAW.tables.structures.bridge
STEP = float(BR.abutment_sample_step_m)


def _way(i, pts, **tags):
    return OsmWay(i, "big_roads", tuple(pts), False, dict(tags))


class _Air:
    def __init__(self, polys=()):
        self.polys = list(polys)

    def contains(self, p) -> bool:
        return any(q.contains(p) for q in self.polys)


class _Obs:
    """A duck-typed ``bridge_end_state.Obstacles``: flat DEM at ``g``."""

    def __init__(self, ways, g=0.0, airside=(), water=None, decks=(), solids=(), off=None,
                 under=None):
        self.graph = BES._Graph(ways)
        self.dem = object()
        self.airside = _Air(airside)
        self._g, self._water, self._decks, self._solids = g, water, list(decks), list(solids)
        self._off, self._under = off, under or {}

    def z(self, xs, ys):
        out = np.full(len(xs), float(self._g))
        if self._off is not None:
            out[np.asarray(xs) > self._off] = np.nan
        return out

    def water(self, _box):
        return self._water

    def near(self, corridor, own):
        return ([o for o in self._decks if o.hard_deck.intersects(corridor)],
                [o for o in self._solids if o.plan_bbox.intersects(corridor)])

    def standing(self, o):
        return o.fp

    def underside(self, o, x, y):
        return self._under[str(o.id)]


def _end(obs, zero=10.0, top=0.0, ground=0.0, carried=(-1,), stub=False, own=()):
    """The land end at x = 0 facing +x on a road along the x axis."""
    return BES.end_state(oid="D", side="b", stations=((0.0, -4.0), (0.0, 4.0)), top=top,
                         out=(1.0, 0.0), ground=ground, zero=zero, carried=carried, stub=stub,
                         own=set(own), obs=obs, law=LAW)


def test_the_path_follows_the_carried_way_then_the_straightest_join():
    ways = [_way(-1, [(-20, 0), (0, 0), (30, 0)], highway="primary"),
            _way(-2, [(30, 0), (60, 25)], highway="primary"),           # 40 deg: a join
            _way(-3, [(30, 0), (30, 60)], highway="service"),           # 90 deg: none
            _way(-4, [(60, 25), (90, 25)], highway="primary")]
    path, routed, used = BES._walk_path((0.0, 0.0), (1.0, 0.0), (-1,), BES._Graph(ways), 200.0)
    assert used == (-1, -2, -4) and path[1] == (30.0, 0.0) and path[-1] == (90.0, 25.0)
    assert abs(routed - (30.0 + math.hypot(30, 25) + 30.0)) < 1e-6
    # an end on no carried way has no routed path
    assert BES._walk_path((0.0, 50.0), (1.0, 0.0), (-1,), BES._Graph(ways), 50.0)[1] == 0.0


def test_a_road_end_grades_at_five_percent_with_no_length_cap():
    obs = _Obs([_way(-1, [(-20, 0), (0, 0), (500, 0)], highway="primary")])
    e = _end(obs, zero=15.0)                          # gap 15 m: RUN 305 m (14e: no cap)
    assert e.state == "graded" and abs(e.grade - 0.05) < 1e-12
    assert abs(e.run - (15.0 / 0.05 + STEP)) < 1e-9 and e.run > 300.0
    assert abs(LineString(e.path).length - e.run) < 1e-6


def test_a_rail_end_grades_at_the_rail_grade():
    obs = _Obs([_way(-1, [(-20, 0), (0, 0), (900, 0)], railway="rail")])
    e = _end(obs, zero=6.7)
    assert e.rail and abs(e.grade - float(LAW.tables.structures.tunnel.rail_ramp_grade)) < 1e-12
    assert e.grade == 0.0125 and abs(e.run - (6.7 / 0.0125 + STEP)) < 1e-6


def test_flush_and_unread_ends():
    obs = _Obs([_way(-1, [(-20, 0), (0, 0), (50, 0)], highway="primary")])
    assert _end(obs, zero=0.03).state == "flush"
    u = _end(obs, ground=math.nan)
    assert u.state == "unread" and "free_end_unread" in u.why


def test_the_held_and_listed_witnesses():
    road = [_way(-1, [(-20, 0), (0, 0), (500, 0)], highway="primary")]
    # end_route_stops: the mapped route stops before RUN
    short = _Obs([_way(-1, [(-20, 0), (0, 0), (40, 0)], highway="primary")])
    assert _end(short, zero=5.0).state == "held" and "end_route_stops" in _end(short, 5.0).why
    # end_at_pack_solid: the standing plan of another frame's object on the path
    solid = types.SimpleNamespace(id="S", path="hall.obj", plan_bbox=box(30, -5, 50, 5),
                                  fp=box(30, -5, 50, 5))
    e = _end(_Obs(road, solids=[solid]), zero=5.0)
    assert e.state == "held" and "end_at_pack_solid" in e.why and "(at 30 m)" in e.why
    # ... never one of its own frame
    assert _end(_Obs(road, solids=[]), zero=5.0, own={"S"}).state == "graded"
    # listed: airside, water, off the DEM
    assert "end_on_airside" in _end(_Obs(road, airside=[box(40, -9, 60, 9)]), zero=5.0).why
    assert "end_on_water" in _end(_Obs(road, water=box(50, -9, 70, 9)), zero=5.0).why
    assert "end_off_dem" in _end(_Obs(road, off=60.0), zero=5.0).why
    # the NEAREST decides
    both = _Obs(road, airside=[box(80, -9, 90, 9)], solids=[solid])
    assert _end(both, zero=5.0).state == "held"
    # a stub's ray over fill_road_reach_m is listed; under it graded
    reach = float(LAW.tables.structures.building_pad.fill_road_reach_m)
    g_far = (reach + 1.0 - STEP) * 0.05
    assert _end(_Obs([]), zero=g_far, carried=(), stub=True).state == "listed"
    assert _end(_Obs([]), zero=(reach - 2.0 - STEP) * 0.05, carried=(),
                stub=True).state == "graded"


def test_the_ramp_passes_under_a_deck_at_clearance_and_is_listed_under_it():
    road = [_way(-1, [(-20, 0), (0, 0), (500, 0)], highway="primary")]
    deck = types.SimpleNamespace(id="P", hard_deck=box(20, -10, 30, 10),
                                 plan_bbox=box(20, -10, 30, 10))
    # at s = 20 the ramp stands 10 - 0.05 (20 - 5) = 9.25
    clear = float(BR.clearance_m)
    ok = _end(_Obs(road, decks=[deck], under={"P": 9.25 + clear + 1e-6}), zero=10.0)
    assert ok.state == "graded" and ok.under == ("P",)
    low = _end(_Obs(road, decks=[deck], under={"P": 9.25 + clear - 0.1}), zero=10.0)
    assert low.state == "listed" and "end_under_low_deck" in low.why


def test_an_at_grade_crossing_is_recorded_and_another_level_is_not():
    ways = [_way(-1, [(-20, 0), (0, 0), (500, 0)], highway="primary"),
            _way(-7, [(40, -30), (40, 30)], highway="service"),
            _way(-8, [(60, -30), (60, 30)], highway="service", bridge="yes", layer="1")]
    e = _end(_Obs(ways), zero=5.0)
    assert e.crossings == (-7,)


# ── the floorless stack ─────────────────────────────────────────────────

def _deck(oid="D"):
    ring = ((-40.0, -4.0), (0.0, -4.0), (0.0, 4.0), (-40.0, 4.0))
    plate = (((-40.0, -4.0, 0.0), (0.0, -4.0, 0.0), (0.0, 4.0, 0.0)),
             ((-40.0, -4.0, 0.0), (0.0, 4.0, 0.0), (-40.0, 4.0, 0.0)))
    return StackDeck(oid, "d.obj", 0, ring, 1, (-1,), (), ((-40.0, -4.0), (-40.0, 4.0)),
                     ((0.0, -4.0), (0.0, 4.0)), 0.0, 0.0, plate)


def _stack(ends, kind=FREE, bridge="free:D"):
    return DeckStack(id="stack:" + bridge, walls_id="", walls_resource="", members=(("D", ""),),
                     zero_z=10.0, zero_spread_m=0.0, end_zeros=(), feet_y=0.0, crest_y=0.0,
                     floor=(), rim=(), runouts=(), under_ways=(), decks=(_deck(),), kind=kind,
                     ends=tuple(ends), bridge=bridge)


def _curved_end(gap=2.0, state="graded"):
    pts = [(0.0, 0.0)] + [(20.0 * math.sin(t), 20.0 - 20.0 * math.cos(t))
                          for t in np.linspace(0.05, 1.5, 30)]
    run = gap / 0.05 + STEP
    return StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 10.0 - gap, gap,
                    state, "", tuple(pts), run if state == "graded" else 0.0, 0.05)


def test_a_floorless_stack_has_aprons_that_follow_a_curved_way_and_a_bank():
    st = _stack([_curved_end(gap=1.0)])
    fp = ground_footprint(st, LAW)
    assert fp["caps"].is_empty and fp["shadows"] == []
    (_d, side, top, apron, slab), = fp["aprons"]
    assert side == "b" and top == 0.0 and not apron.is_empty and slab.area > 0.0
    # the apron follows the way: its far part bends up (+y), not along +x
    assert apron.bounds[3] > 10.0 and not apron.contains(Point(35.0, 0.0))
    assert not fp["bank"].is_empty and not fp["bank"].intersects(Polygon(_deck().ring)
                                                                  .buffer(-0.01))
    # a FREE flush end gets the slab alone, no bank
    flat = ground_footprint(_stack([dc.replace(_curved_end(), state="flush", run=0.0)]), LAW)
    assert flat["bank"].is_empty and abs(flat["aprons"][0][3].area - 8.0 * STEP) < 1e-6


def test_the_rowed_ends_by_mode():
    ends = [dc.replace(_curved_end(), state=s, side=k)
            for s, k in (("graded", "a"), ("flush", "b"), ("held", "c"), ("listed", "d"),
                         ("governing", "e"))]
    assert [e.side for e in _stack(ends).rowed_ends()] == ["a", "b"]
    assert [e.side for e in _stack(ends, kind=KEPT).rowed_ends()] == ["a"]


def _map(st):
    """A planar stub: a ground face across the apron, one under the deck."""
    verts, faces = {}, {}

    def face(role, ref, pts):
        ids = []
        for p in pts:
            verts[len(verts)] = types.SimpleNamespace(xy=tuple(p), incident_faces=[len(faces)],
                                                      dem_z=0.0)
            ids.append(len(verts) - 1)
        faces[len(faces)] = types.SimpleNamespace(role=role, ref=ref, ring=tuple(ids), holes=())
    face("graded_strip", "stack_ground:x", [(1.0, -2.0), (1.0, 2.0), (3.0, 0.0)])
    face("graded_strip", "stack_ground:y", [(15.0, -1.0), (15.0, 1.0), (16.0, 0.0)])
    face("graded_strip", "ground", [(-20.0, -1.0), (-20.0, 1.0), (-19.0, 0.0)])
    face("service_road", "big_roads:-1", [(14.0, 3.0), (14.5, 3.0), (14.2, 3.5)])
    return types.SimpleNamespace(faces=faces, vertices=verts, ring_vertices=lambda r: list(r),
                                 bridge_stacks=(st,))


def test_the_rows_slab_profile_and_ceiling():
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05)
    st = _stack([end])
    rows = deck_stack_rows(_map(st), LAW, types.SimpleNamespace(deck_stacks=(st,)))
    flush = float(BR.deck_flush_m)
    slab = [r for r in rows if r.source.inputs[2] == "D#0 end b"]
    assert len(slab) == 3 and all(abs(r.hi - 10.0) < 1e-9 and abs(r.lo - (10.0 - flush)) < 1e-9
                                  for r in slab)
    prof = [r for r in rows if "profile" in r.source.inputs[2]]
    # the vertices at s = 15 / 16: P = 10 - 0.05 (s - 5); the road vertex is the ramp's
    assert len(prof) == 3 and all(9.4 < r.hi <= 9.5 + 1e-9 and abs(r.hi - r.lo - 0.25) < 1e-9
                                  for r in prof)
    ceil = [r for r in rows if "under the deck" in r.source.inputs[2]]
    assert len(ceil) == 3 and all(r.lo is None and abs(r.hi - (10.0 - flush)) < 1e-9
                                  for r in ceil)
    # KEPT: no ceiling; a FREE stack the planar stage refused: no row
    kept = dc.replace(st, kind=KEPT, bridge="kept:D")
    rk = deck_stack_rows(_map(kept), LAW, types.SimpleNamespace(deck_stacks=(kept,)))
    assert rk and not [r for r in rk if "under the deck" in r.source.inputs[2]]
    pm = _map(st)
    pm.bridge_stacks = ()
    assert deck_stack_rows(pm, LAW, types.SimpleNamespace(deck_stacks=(st,))) == []
    assert live_stacks((st, kept), types.SimpleNamespace(bridge_stacks=(kept,))) == (kept,)
    assert live_stacks((st, kept), None) == (st, kept)


def test_the_way_rewrite_untagged_tagged_and_run_on():
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05)
    st = _stack([end])
    plain = [_way(-1, [(-60, 0), (60, 0)], highway="primary")]
    got = DS._rewrite_ways(plain, [st], LAW)
    on = [w for w in got if w.tags.get("bridge") == "yes"]
    assert len(on) == 1 and abs(LineString(on[0].points).length - 40.0) < 1e-6
    tagged = [_way(-1, [(-40, 0), (10, 0)], highway="primary", bridge="yes", layer="1"),
              _way(-2, [(10, 0), (60, 0)], highway="primary")]
    got = DS._rewrite_ways(tagged, [st], LAW)
    # the tagged stretch over the plate is untouched; its run-on past the
    # graded end (0 .. 10 m) is at grade
    over = [w for w in got if w.id == -1 and w.tags.get("bridge") == "yes"]
    run_on = [w for w in got if w.id == -1 and "bridge" not in w.tags]
    assert over and LineString(over[0].points).bounds[2] <= 0.02
    assert run_on and abs(LineString(run_on[0].points).length - 10.0) < 0.02
    assert "layer" not in run_on[0].tags
    # a stack with no GRADED end rewrites nothing
    none = _stack([dc.replace(end, state="flush")])
    assert DS._rewrite_ways(plain, [none], LAW) == tuple(plain)


def test_an_at_grade_crossing_is_seeded_at_the_profile():
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05, crossings=(-7,))
    st = _stack([end])
    verts = {0: types.SimpleNamespace(xy=(25.0, 1.0)), 1: types.SimpleNamespace(xy=(25.0, 30.0))}
    faces = {0: types.SimpleNamespace(role="service_road", ref="big_roads:-7#0", ring=(0, 1))}
    pm = types.SimpleNamespace(faces=faces, vertices=verts, ring_vertices=lambda r: list(r),
                               bridge_stacks=(st,))
    got = DE._crossing_vertices(pm, LAW, types.SimpleNamespace(deck_stacks=(st,)))
    assert set(got) == {0} and abs(got[0] - (10.0 - 0.05 * 20.0)) < 1e-9


def test_a_trench_stack_is_untouched_by_the_bridge_kinds():
    assert DeckStack.__dataclass_fields__["kind"].default == "trench"
    st = dc.replace(_stack([_curved_end()]), kind="trench", ends=())
    assert st.rowed_ends() == () and st.graded_ends() == ()
    assert Point(0, 0).within(box(-1, -1, 1, 1))


# ── the object stage (rules 9, 10) ──────────────────────────────────────

def _datum(graded=()):
    from auto_patch_v2.airport.anchor_rule import Datum
    ends = (((36.0, -86.0004), (36.00008, -86.0004)), ((36.0, -85.9996), (36.00008, -85.9996)))
    return Datum(0.0, (), "deck top", ends=ends, step_m=STEP, graded=tuple(graded))


def _surface(at_a, at_b, at_origin):
    def f(lat, lon):
        if lon < -86.0002:
            return at_a
        if lon > -85.9998:
            return at_b
        return at_origin
    return f


def test_a_kept_22m_bridge_keeps_its_seat_when_its_far_end_is_raised():
    from auto_patch_v2.airport.bridge_approach import approach_seat
    origin = (36.00004, -86.0)
    # today's seat: flush at end a (10.0, the higher; the road under is 4.0)
    base = approach_seat(_datum(), _surface(10.0, 8.0, 4.0), origin=origin, authored_agl_m=0.0)
    assert abs(base.zero - 10.0) < 1e-9
    # the terrain graded up end b to 10.5: without the flag the seat flips
    raised = _surface(10.0, 10.5, 4.0)
    assert abs(approach_seat(_datum(), raised, origin=origin, authored_agl_m=0.0).zero
               - 10.5) < 1e-9
    kept = approach_seat(_datum((False, True)), raised, origin=origin, authored_agl_m=0.0)
    assert abs(kept.zero - 10.0) < 1e-9


def test_a_kept_22p_bridge_with_both_ends_graded_keeps_its_clearance():
    from auto_patch_v2.airport.bridge_approach import approach_seat
    origin = (36.00004, -86.0)
    # 22p: no embankment at either end (6.0 / 6.1 over the road at 6.0, clearance 5 m)
    base = approach_seat(_datum(), _surface(6.0, 6.1, 6.0), origin=origin, authored_agl_m=5.0)
    assert "authored clearance" in base.reason and abs(base.zero - 11.0) < 1e-9
    # both ends graded up to the deck (11.0): the clearance stands
    graded = approach_seat(_datum((True, True)), _surface(11.0, 11.0, 6.0), origin=origin,
                           authored_agl_m=5.0)
    assert "authored clearance" in graded.reason and abs(graded.zero - 11.0) < 1e-9


def test_rule_10_an_unread_land_end_is_counted_never_dropped():
    from auto_patch_v2.airport.free_bridge_seat import _bridge_zero
    end = types.SimpleNamespace(ground=5.0, top=1.0, why="read")
    one = types.SimpleNamespace(ends=(end,), clearance=None, unread=(1,))
    zero, _why, unread = _bridge_zero([one], [[False, False]])
    assert abs(zero - 4.0) < 1e-9 and unread == 1
    # a joint read nowhere is no land end
    assert _bridge_zero([one], [[False, True]])[2] == 0
    # a deck read nowhere counts both its land ends
    assert _bridge_zero([one, None], [[False, False], [False, True]])[2] == 2


def test_the_planar_stage_holds_a_graded_end_entering_a_lot_and_drops_the_refused():
    from auto_patch_v2.planar.free_bridge import planar_stacks
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05)
    st = _stack([end])
    fb = types.SimpleNamespace(id=st.bridge)

    def cl(ref):
        c = types.SimpleNamespace(ref=ref, ring=((20, -9), (40, -9), (40, 9), (20, 9)), holes=())
        return types.SimpleNamespace(cells=[c])
    kept, _n = planar_stacks((st,), (fb,), cl("gap:0/s0"))
    assert kept == (st,)
    held, notes = planar_stacks((st,), (fb,), cl("gap:0/s0/lot"))
    assert held == () and any("end_on_lot" in n for n in notes)
    gone, notes = planar_stacks((st,), (), cl("gap:0/s0"))
    assert gone == () and "free_stack_refused_at_planar" in notes[0]


def test_a_graded_corridor_cuts_the_faces_it_crosses_but_never_the_airside():
    from auto_patch_v2.planar.stack_ground import bridge_corridor_lines
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 0.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05)
    a = types.SimpleNamespace(deck_stacks=(_stack([end]),))
    lines = bridge_corridor_lines(a, LAW)
    cross = [g for g in lines if abs(g.bounds[0] - g.bounds[2]) < 1e-6]
    assert len(cross) == 8 and all(abs(g.length - 8.0) < 1e-6 for g in cross)
    sides = [g for g in lines if abs(g.bounds[1] - g.bounds[3]) < 1e-6]
    assert abs(sum(g.length for g in sides) - 2 * 45.0) < 1e-6
    cut = bridge_corridor_lines(a, LAW, [box(20, -9, 30, 9)])
    assert not any(g.intersects(box(20, -9, 30, 9).buffer(0.4)) for g in cut)
    assert bridge_corridor_lines(types.SimpleNamespace(deck_stacks=()), LAW) == []
