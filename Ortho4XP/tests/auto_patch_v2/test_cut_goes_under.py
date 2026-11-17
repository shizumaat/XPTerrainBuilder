"""Twins of the cut-cover round (owner 2026-11-17 18:30Z "Be sure the cut
goes all the way under anywhere we add a bridge"; 19:08Z 4.2 m for small
roads): a generated deck's floor follows its end lines as stage 1 solved
them (``constraints/deck_floor_follow``), the lower road under a generated
road bridge's span holds its clearance as a hard ceiling
(``constraints/road_bridge_ceiling``), the pads and walls read off a pack
placement a generated deck hides leave the classification
(``planar/deck_pack_cover.hidden_cells_off``) and the clearance by road
class (``structure_approach.design_clearance_m``).  Synthetic, no capture."""
from __future__ import annotations

import dataclasses as dc
import types

from auto_patch_v2.constraints.deck_floor_follow import floor_follow_rewrite
from auto_patch_v2.constraints.edge_floor import DECK_FLOOR
from auto_patch_v2.constraints.road_bridge_ceiling import road_bridge_ceiling_rows
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
from auto_patch_v2.model.structures import DeckAnchor, DeckBridge
from auto_patch_v2.planar.deck_generated import GENERATED_WITNESS
from auto_patch_v2.planar.deck_pack_cover import hidden_cells_off
from auto_patch_v2.planar.structure_approach import design_clearance_m

LAW = load_default()


def _deck(**kw):
    ring = ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0))
    return DeckBridge("o4gen_t", "objects/o4_generated/deck_t.obj", (), ring,
                      ((0.0, 0.0), (0.0, 20.0)), ((40.0, 0.0), (40.0, 20.0)), 0.0, 0.3,
                      -6.0, 29.4, floor_min_m=6.0, witness=GENERATED_WITNESS, **kw)


def _anchor(end, stations):
    return DeckAnchor("o4gen_t", end, stations[0], tuple(stations), 0.0, 0.0, 0.0, "taxi",
                      "", 0.0)


def test_clearance_by_road_class():
    assert design_clearance_m({"highway": "service"}, LAW) == 4.2
    assert design_clearance_m({"highway": "motorway"}, LAW) == 5.0
    assert design_clearance_m({"railway": "rail"}, LAW) == 5.0


def test_the_floor_follows_the_solved_end_lines():
    # pre-solve floor 23.4 (29.4 - 6); stage 1 put the ends at 28.7 / 29.0:
    # the floor goes to min(28.7 - 6.0, 29.0 - 6.3) = 22.7
    db = _deck()
    tn = types.SimpleNamespace(id="tunnel:-1@0", deck_bridge="o4gen_t")
    pm = types.SimpleNamespace(decks=(db,), structures=(tn,),
                               deck_anchors=(_anchor("a", (1, 2)), _anchor("b", (3, 4))))
    src = Source("structures", DECK_FLOOR, ("tunnel:-1@0",))
    other = Pin(9, 50.0, Source("x", "y", ("tunnel:-1@0",)))
    cs = ConstraintSet(pins=(Pin(7, 23.4, src), Pin(8, 23.4, src), other))
    lv = {1: 28.7, 2: 28.7, 3: 29.0, 4: 29.0}
    out, rep = floor_follow_rewrite(pm, cs, lv)
    z = {p.v: p.z for p in out.pins}
    assert abs(z[7] - 22.7) < 1e-9 and abs(z[8] - 22.7) < 1e-9 and z[9] == 50.0
    assert rep["pins"] == 2 and abs(rep["max_drop_m"] - 0.7) < 1e-9
    # a deck solved higher than estimated keeps its deeper pin
    same, rep = floor_follow_rewrite(pm, cs, {k: v + 2.0 for k, v in lv.items()})
    assert same is cs and rep["pins"] == 0


def test_the_lower_road_under_a_span_takes_a_hard_ceiling():
    low = types.SimpleNamespace(id="-4", points=((60.0, -80.0), (60.0, 80.0)),
                                tags={"highway": "service"})
    span = ((0.0, -8.0), (100.0, -8.0), (100.0, 8.0), (0.0, 8.0))
    ap = types.SimpleNamespace(osm_ways=(low,), road_bridges=(
        {"id": "-1", "levels": [20.0, 25.0], "axis_xy": [[0.0, 0.0], [100.0, 0.0]],
         "span_xy": [list(p) for p in span], "over": ["-4"]},))
    vx = {1: (60.0, 0.0), 2: (60.0, 7.0), 3: (60.0, 20.0), 4: (30.0, 0.0)}
    pm = types.SimpleNamespace(vertices={v: types.SimpleNamespace(xy=xy) for v, xy in vx.items()})
    rows = {b.v: b for b in road_bridge_ceiling_rows(pm, LAW, ap)}
    assert set(rows) == {1, 2}           # off the span (3) and off the road (4): none
    assert abs(rows[1].hi - (23.0 - 4.2)) < 1e-9 and rows[1].lo is None
    assert road_bridge_ceiling_rows(pm, LAW, types.SimpleNamespace(osm_ways=())) == []


def test_pads_read_off_a_hidden_placement_leave():
    def cell(role, ref, ring):
        return types.SimpleNamespace(role=role, ref=ref, ring=ring, holes=())
    sq = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    far = ((50.0, 0.0), (60.0, 0.0), (60.0, 10.0), (50.0, 10.0))
    @dc.dataclass(frozen=True)
    class _Cl:
        cells: tuple
    cl = _Cl(cells=(cell("building", "building1", sq),
                                      cell("retaining_wall", "w", sq),
                                      cell("service_road", "r", sq),
                                      cell("building", "building2", far)))
    out, notes = hidden_cells_off(cl, (_deck(hidden_plans=(sq,)),))
    assert [c.ref for c in out.cells] == ["r", "building2"] and notes
    same, notes = hidden_cells_off(cl, (_deck(),))
    assert same is cl and not notes


def test_the_deck_has_straight_sides_and_a_steeper_bank():
    from auto_patch_v2.planar.deck_generated import _straight_sided as straight_sided
    from auto_patch_v2.planar.deck_bank import deck_bank_slope
    from shapely.geometry import Polygon
    # an L-shaped pavement piece over a road along y: one rectangle holds it,
    # two sides along the road
    piece = Polygon([(0, 0), (30, 0), (30, 10), (10, 10), (10, 20), (0, 20)])
    rect = straight_sided(piece, (0.0, 1.0))
    assert rect.contains(piece.buffer(-1e-6)) and abs(rect.area - 600.0) < 1e-6
    assert straight_sided(piece, None) is piece
    # an oblique route: two sides along the road, two along the route
    import math
    r = (math.cos(math.radians(60)), math.sin(math.radians(60)))
    par = straight_sided(piece, (0.0, 1.0), r)
    assert par.contains(piece.buffer(-1e-6))
    xs = list(par.exterior.coords)
    sides = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(xs[:-1], xs[1:], strict=True)]
    assert any(abs(dx) < 1e-9 for dx, _dy in sides)                       # along the road
    assert any(abs(dx * r[1] - dy * r[0]) < 1e-9 and dx != 0 for dx, dy in sides)  # along the route
    # owner sim read 2026-11-17T19:42Z: steeper than the channel's 1:2
    assert deck_bank_slope(LAW) > float(LAW.tables.structures.channel.bank_slope)


def test_the_lower_road_carries_nodes_under_the_span():
    from auto_patch_v2.model.airport import OsmWay
    from auto_patch_v2.planar.road_bridge_gen import _densified
    low = OsmWay(-4, "small_roads", ((60.0, -80.0), (60.0, 80.0)), False, {"highway": "service"})
    other = OsmWay(-5, "small_roads", ((0.0, 50.0), (10.0, 50.0)), False, {"highway": "service"})
    span = [[0.0, -8.0], [100.0, -8.0], [100.0, 8.0], [0.0, 8.0]]
    out = _densified((low, other), ({"over": ["-4"], "span_xy": span, "ground": []},))
    pts = out[0].points
    assert out[1] is other and pts[0] == low.points[0] and pts[-1] == low.points[-1]
    under = [y for x, y in pts if abs(y) <= 10.0]
    assert len(under) >= 10 and all(x == 60.0 for x, _y in pts)
    assert [y for _x, y in pts] == sorted(y for _x, y in pts)


#: a frame's walls on both sides of the road (``(r, n, faces)``, the road along y)
_BOTH_WALLS = ((0.0, 1.0), (1.0, 0.0), ((5.0, 0.0, 20.0), (35.0, 0.0, 20.0)))


def _pack_deck(**kw):
    """A wall-less PACK hard deck (no generated witness) over the same ring."""
    ring = ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0))
    return DeckBridge("dsf:obj7", "objects/H7.obj", ("dsf:obj7",), ring,
                      ((0.0, 0.0), (0.0, 20.0)), ((40.0, 0.0), (40.0, 20.0)), 0.0, 0.0,
                      -7.42, 100.0, floor_min_m=7.42, **kw)


def test_every_wall_less_deck_stands_on_the_one_bank():
    """RULINGS 2026-11-17p (#1717): a wall-less pack deck's span is the
    bank, as a generated deck's -- the one slope; a WALLED pack deck keeps
    the fill behind its walls flush (30f (3))."""
    from auto_patch_v2.constraints.edge_deck import _bank_slope
    from auto_patch_v2.planar.deck_bank import bank_past_m, banked, deck_bank_slope
    pack, walled, gen = _pack_deck(), _pack_deck(walls=_BOTH_WALLS), _deck()
    assert banked(pack) and banked(gen) and not banked(walled)
    es = lambda d: (types.SimpleNamespace(deck=d),)    # noqa: E731
    assert _bank_slope(LAW, es(pack)) == _bank_slope(LAW, es(gen)) == deck_bank_slope(LAW)
    assert _bank_slope(LAW, es(walled)) is None
    assert bank_past_m(LAW) == 1.0


def test_a_pack_decks_ground_runs_past_its_ring():
    """RULINGS 2026-11-17p: the ground a wall-less pack deck rests on runs
    ``bank_past_m`` past its ring (the bank 1 m past the bridge), as a
    generated deck's; a walled deck's stops at its reach."""
    from auto_patch_v2.planar.deck_bridge import deck_ground
    from shapely.geometry import Polygon

    @dc.dataclass(frozen=True)
    class _Cl:
        cells: tuple
    ring = _pack_deck().ring
    tn = types.SimpleNamespace(deck_bridge="dsf:obj7", deck_ring=ring,
                               edge_seats=(("dsf:obj7", ((0.0, 0.0), (0.0, 20.0)), 7.4),
                                           ("dsf:obj7", ((40.0, 0.0), (40.0, 20.0)), 7.4)))
    from auto_patch_v2.classify.roles import Cell
    far = Cell(0, "apron", "far", ((500.0, 500.0), (510.0, 500.0), (510.0, 510.0)), (),
               None, None, "airside", "pavement", {})
    cl = _Cl(cells=(far,))

    def area(decks):
        out, _n = deck_ground(cl, [tn], LAW, decks)
        return sum(Polygon(c.ring, c.holes).area for c in out.cells if c.ref != "far")
    base, walled = area(()), area((_pack_deck(walls=_BOTH_WALLS),))
    banked_ = area((_pack_deck(),))
    assert abs(base - 800.0) < 1e-6 and abs(walled - base) < 1e-6
    assert abs(banked_ - 42.0 * 22.0) < 1e-6


def test_a_deck_walled_on_one_side_is_banked():
    """MEASURED LFPG H16 (obj13023): a deck whose frame models a wall on one
    side of the road only is cut as a banked deck (``deck_bridge.
    _walled_trench`` is ``None``), so its span is the bank too."""
    from auto_patch_v2.planar.deck_bank import banked
    import auto_patch_v2.planar.deck_bridge as DB
    one_side = _pack_deck(walls=(_BOTH_WALLS[0], _BOTH_WALLS[1], _BOTH_WALLS[2][:1]))
    assert DB._walled_trench(one_side, 0.0) is None and banked(one_side)
    both = _pack_deck(walls=_BOTH_WALLS)
    assert DB._walled_trench(both, 0.0) is not None and not banked(both)
