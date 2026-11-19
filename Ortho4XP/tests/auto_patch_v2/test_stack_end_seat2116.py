"""#2116 item 3 (owner RULINGS 2026-11-18c with 2026-10-22m): a member of a
TRENCH stack that 18c seats by its own end lines is PREDICTED at the pack
stage (``airport/stack_end_seat``), and the stack's ground gives it end
aprons at its plate top (``geom/deck_ground``), where the trench's bank ran
on past its end lines; the end-line roads are held there
(``model/deck_ends.end_road_vertices``)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_patch_v2.airport import stack_end_seat as SES  # noqa: E402
from auto_patch_v2.geom.deck_ground import end_aprons, ground_footprint  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.deck_stack import DeckStack  # noqa: E402
from test_floor_deck_ends import DECK, WALLS, ZERO, _obj  # noqa: E402

LAW = Law.for_airport("")
WEST, EAST = 1634.7, 1636.0


class _Dem:
    """The trench's floor between the deck's ends, a road level beyond."""

    def z(self, x: float, _y: float) -> float:
        return WEST if x < -5.0 else EAST if x > 26.0 else ZERO


def _scene(tmp_path, ways=("w", "e"), deck=DECK):
    _obj(tmp_path / "walls.obj", WALLS)
    _obj(tmp_path / "deck.obj", deck)
    objs = [NS(id=f"dsf:obj{i}", kind="OBJECT", resolved=str(tmp_path / name), xy=(0.0, 0.0),
               heading_deg=0.0) for i, name in enumerate(("walls.obj", "deck.obj"))]
    road = {"w": NS(id=-1, tags={"highway": "service"}, points=[(-60.0, 0.0), (-5.2, 0.0)]),
            "e": NS(id=-2, tags={"highway": "service"}, points=[(26.2, 0.0), (80.0, 0.0)])}
    airport = NS(dem=_Dem(), osm_ways=[road[k] for k in ways], osm_ways_mapped=None)
    st = DeckStack("stack:dsf:obj0", "dsf:obj0", "walls.obj",
                   (("dsf:obj0", "walls.obj"), ("dsf:obj1", "deck.obj")), ZERO, 0.0, (),
                   0.0, 3.5, (), (), (), (), ())
    return st, airport, objs


def test_the_deck_is_predicted_flush_at_its_lower_road(tmp_path):
    st, airport, objs = _scene(tmp_path)
    notes: list = []
    (out,) = SES.seat_stacks((st,), airport, objs, LAW, notes)
    (d,) = out.end_seated
    assert d.object_id == "dsf:obj1" and d.level == 0 and not d.carried
    # the deck's top (y 4.0 at the zero) lifted onto the west road
    assert d.top_a == pytest.approx(WEST - ZERO, abs=1e-6)
    assert d.top_b == pytest.approx(WEST - ZERO, abs=1e-6)
    assert sorted(out.ground_m("dsf:obj1", 0, e) for e in "ab") == pytest.approx([WEST, EAST])
    assert any("predicted" in n and "dsf:obj1" in n for n in notes)
    assert out.decks == () and out.zero_z == ZERO          # no level, the zero unmoved


def test_an_end_off_any_mapped_road_is_not_seated(tmp_path):
    st, airport, objs = _scene(tmp_path, ways=("w",))
    (out,) = SES.seat_stacks((st,), airport, objs, LAW)
    assert out is st and out.end_seated == ()


def test_the_seated_deck_gets_end_aprons_at_its_plate_top(tmp_path):
    st, airport, objs = _scene(tmp_path)
    (out,) = SES.seat_stacks((st,), airport, objs, LAW)
    assert len(end_aprons(out, LAW)) == len(end_aprons(st, LAW)) + 2
    fp = ground_footprint(out, LAW)
    mine = [(side, top, a, slab) for d, side, top, a, slab in fp["aprons"]
            if d.object_id == "dsf:obj1"]
    assert {side for side, *_ in mine} == {"a", "b"}
    plan = ground_footprint(st, LAW)
    for _side, top, a, slab in mine:
        assert ZERO + top == pytest.approx(WEST, abs=1e-6)
        assert not a.is_empty and slab.area > 0.0
        x0, _y0, x1, _y1 = slab.bounds
        assert x1 <= -5.0 + 1e-6 or x0 >= 26.0 - 1e-6          # beyond the deck's ends
        assert a.within(fp["outline"]) and not a.intersects(fp["bank"].buffer(-0.01))
    # the apron sits in a bank of its own: its edge is no toe
    assert fp["outline"].area > plan["outline"].area


def test_the_end_roads_are_held_at_the_seated_plate_top(tmp_path):
    from auto_patch_v2.model.deck_ends import end_road_vertices
    st, airport, objs = _scene(tmp_path)
    (out,) = SES.seat_stacks((st,), airport, objs, LAW)
    verts = {1: NS(xy=(-7.0, 0.0), incident_faces=(1,)),       # on the west road, 2 m out
             2: NS(xy=(28.0, 0.0), incident_faces=(2,)),       # on the east road, 2 m out
             3: NS(xy=(-40.0, 0.0), incident_faces=(1,))}      # far up the west road
    pm = NS(vertices=verts, faces={1: NS(role="service_road"), 2: NS(role="service_road")},
            bridge_stacks=None)
    got = end_road_vertices(pm, LAW, NS(deck_stacks=(out,)))
    assert set(got) == {1, 2}
    assert all(z == pytest.approx(WEST, abs=1e-6) for z, *_r in got.values())
    assert end_road_vertices(pm, LAW, NS(deck_stacks=(st,))) == {}


def test_a_kinked_end_is_held_one_step_past_every_station():
    """KDEN's east end turns a corner: the slab is the end EDGE swept along
    the span, never the chord between its two end stations."""
    from auto_patch_v2.model.deck_stack import StackDeck
    from shapely.geometry import Point
    end_a = ((0.0, 0.0), (0.0, 6.0), (2.0, 8.0), (2.0, 10.0))        # a kink at its corner
    end_b = ((30.0, 0.0), (30.0, 10.0))
    ring = ((0.0, 0.0), (30.0, 0.0), (30.0, 10.0), (2.0, 10.0), (0.0, 6.0))
    d = StackDeck("dsf:obj9", "deck.obj", 0, ring, 0, (), (), end_a, end_b, 4.0, 4.0)
    st = DeckStack("stack:dsf:obj0", "dsf:obj0", "walls.obj", (("dsf:obj9", "deck.obj"),),
                   ZERO, 0.0, (), 0.0, 3.5, (), (), (), (), (), end_seated=(d,),
                   end_seated_ground=(("dsf:obj9", 0, "a", ZERO + 4.0),
                                      ("dsf:obj9", 0, "b", ZERO + 4.0)))
    H = float(LAW.tables.structures.bridge.abutment_sample_step_m)
    (slab,) = [sl for dd, side, _t, _a, sl in ground_footprint(st, LAW)["aprons"]
               if dd.object_id == "dsf:obj9" and side == "a"]
    for x, y in end_a:
        assert slab.buffer(0.25).contains(Point(x - (H - 0.1), y))   # along the span (2 deg off x)


def test_the_seated_slab_is_a_piece_of_its_own(tmp_path):
    """The slab's outer edge is a ring of the minted ground (its vertices R1
    holds), where one apron piece let the solve chord past it to L_e."""
    from auto_patch_v2.planar.stack_ground import stack_ground_pieces
    st, airport, objs = _scene(tmp_path)
    (out,) = SES.seat_stacks((st,), airport, objs, LAW)
    slabs = {side: sl for d, side, _t, _a, sl in ground_footprint(out, LAW)["aprons"]
             if d.object_id == "dsf:obj1"}
    got = stack_ground_pieces(NS(deck_stacks=(out,)), [], [], 0.5, 0.05, 2.0, law=LAW)
    for side, slab in slabs.items():
        mine = [g for ref, g in got if f":apron:dsf:obj1#0{side}#" in ref]
        assert any(g.symmetric_difference(slab).area < 0.5 for g in mine)
    # the east end's road stands 1.3 m over the plate: its apron runs past
    # the slab, so it is minted as two pieces
    assert max(sum(1 for ref, _g in got if f":apron:dsf:obj1#0{s}#" in ref) for s in "ab") >= 2
