"""#2068 owner sim read 2026-11-14T20:01Z: THE FLOOR YARD
(``classify/floor_yard``).  A unit's fence standing at the unit's FLOOR,
beside the floor pad, where the natural ground falls more than a band
under the floor's, is the edge of a terrace: the ground it encloses on its
groundside stands on the fence-foot plane, its airside keeps its ground;
a fence at grade, one in a cut, one off the floor and no floor pad
take nothing.
The floor pad's held record carries the yard (``yard_edge.yard_records``)."""
from __future__ import annotations

import sys
import types

import pytest
from auto_patch_v2.airport import unit_storey
from auto_patch_v2.classify import fence_yard as fy
from auto_patch_v2.classify import floor_yard as fl
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.constraints.yard_edge import yard_records
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import EdgeLine
from auto_patch_v2.model.registries import FLOOR_YARD, Registries
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

LAW = Law.for_airport("SYNT")
PAD = box(40.0, 30.0, 60.0, 50.0)                 # the terminal, at the unit's floor
LOT = box(5.0, 58.0, 52.0, 82.0)                  # groundside parking inside the fence
APRON = box(70.0, 30.0, 130.0, 100.0)             # airside beyond the fence's east leg
FENCE = [(55.0, 45.0), (60.0, 90.0), (0.0, 90.0)]  # from the pad's corner north, then west


def _cell(i, role, ref, g, side, ev=None):
    return Cell(i, role, ref, tuple(g.exterior.coords)[:-1], (), None, None, side, role,
                dict(ev or {}))


class _Dem:
    def __init__(self, fn):
        self.fn = fn

    def z(self, x, y):
        return self.fn(x, y)


def _ground(fall):
    """The pad's ground at 5.0; north of it the natural ground ``fall``
    under it."""
    return _Dem(lambda x, y: 5.0 if y <= 52.0 else 5.0 - fall)


def _mint(monkeypatch, base=0.2, fall=2.5, floor_pad=True):
    part = types.SimpleNamespace(base_y=0.0)
    ur = unit_storey._UnitRead(0, None, ((part, PAD),) if floor_pad else (), 0.0,
                               PAD.bounds)
    monkeypatch.setattr(unit_storey, "_unit_reads", lambda *_a, **_k: [ur])
    line = EdgeLine("unit:0:f#0", "fence.obj", tuple(FENCE), False, 0.0, 3.5, 0.0, 0.3, 0.0,
                    unit=0, base_ys=tuple(base for _p in FENCE), panel_m=3.5)
    cells = [_cell(0, "building", "building2", PAD, "airside"),
             _cell(1, "parking_lot", "lot", LOT, "groundside"),
             _cell(2, "apron", "pol1", APRON, "airside")]
    out = []

    def add(r, rf, poly, kind, cn=None, cl=None, evidence=None):
        out.append((r, rf, poly, dict(evidence or {})))
    airport = types.SimpleNamespace(edge_lines=(line,), dem=_ground(fall), partition=object(),
                                    frame=types.SimpleNamespace(entry=lambda: None))
    st = fy.mint_fence_yards(airport, cells, LAW, load_rules(), add)
    return out, st, cells


def test_a_floor_fence_over_falling_ground_holds_its_groundside_at_the_fence_foot(monkeypatch):
    out, st, cells = _mint(monkeypatch)
    assert out and st["fence_yards"] == len(out)
    assert all(r == "groundside_pavement" and f.endswith(":building2") for r, f, _p, _e in out)
    yard = unary_union([p for _r, _f, p, _e in out])
    # the free ground between the lot and the fence's north leg is the yard
    assert yard.contains(Point(30.0, 86.0))
    # the fence's airside (toward the apron) keeps its ground
    assert not yard.intersects(Point(65.0, 70.0))
    # nothing beyond the fence
    assert not yard.intersects(Point(30.0, 95.0))
    pl = fy._yard_plane_of(cells[0].evidence)
    assert pl is not None and pl[0] == pytest.approx(0.2) and pl[1] == pl[2] == 0.0
    rec = fl.floor_yard_reads(cells)["building2"]
    assert rec["y_p"] == 0.0 and rec["yard_hull"] and "witness" in st["floor_yard:building2"]


@pytest.mark.parametrize("case", ["at_grade", "cut", "off_the_floor", "no_floor_pad"])
def test_doubt_takes_nothing(monkeypatch, case):
    out, st, cells = _mint(monkeypatch, base=4.0 if case == "off_the_floor" else 0.2,
                           fall={"at_grade": 0.3, "cut": -2.5}.get(case, 2.5),
                           floor_pad=case != "no_floor_pad")
    assert out == [] and st["fence_yards"] == 0
    assert fl.floor_yard_reads(cells) == {}


def test_the_held_block_carries_the_floor_yard_to_the_solve():
    reg = Registries(held={"building2": {FLOOR_YARD: {"yard_plane": (0.2, 0.0, 0.0, 0.0, 0.0),
                                                      "yard_hull": (), "y_p": 0.0}},
                           "building3": {}},
                     landings={"building2/p1": {"pad": "building1", "yard_plane": (1, 0, 0, 0, 0)},
                               "u/landing0": {"pad": "x"}})
    got = yard_records(types.SimpleNamespace(registries=reg))
    assert sorted(got) == ["building2", "building2/p1"]
    assert got["building2"]["pad"] == "building2" and got["building2"]["y_p"] == 0.0


def test_the_yard_is_its_fill_a_cut_on_the_far_side_is_trimmed(monkeypatch):
    """F7 (KMCI building43: the plane cut a 1.5 m bank): where the natural
    ground rises more than a band over the yard plane, the yard leaves it."""
    rise = _Dem(lambda x, y: 5.0 if y <= 52.0 else (9.0 if x < 20.0 else 2.5))
    monkeypatch.setattr(sys.modules[__name__], "_ground", lambda fall: rise)
    out, st, _cells = _mint(monkeypatch)
    yard = unary_union([p for _r, _f, p, _e in out])
    assert yard.contains(Point(30.0, 86.0))          # the fill at the fence stays
    assert not yard.intersects(Point(10.0, 86.0))    # the cut leaves
    assert all(e["yard_cut_m2"] > 0.0 for _r, _f, _p, e in out)


def test_a_fill_pocket_cut_off_from_the_witness_fence_is_dropped():
    """F7: what the trim severs from the witness fence goes with the cut."""
    region = unary_union([box(0.0, 0.0, 40.0, 10.0), box(0.0, 20.0, 40.0, 30.0)])
    dem = _Dem(lambda x, y: 9.0 if 10.0 < x < 14.0 and y < 10.0 else 0.0)
    left, gross, cut = fl._trim_to_fill(dem, region, region, (0.0, 0.0, 0.0, 0.0, 0.0), 0.0,
                                        LineString([(0.0, 0.0), (0.0, 10.0)]), 1.0)
    assert left.contains(Point(5.0, 5.0)) and not left.intersects(Point(30.0, 5.0))
    assert not gross.intersects(Point(30.0, 5.0)) and cut == pytest.approx(30.0 * 10.0, rel=0.1)
    # a piece the trim leaves whole stays, witness or not (a road between)
    assert left.contains(Point(30.0, 25.0))


def test_slivers_do_not_mint():
    """F8 (HECA building155: three slivers of 30 m2; LOWS building17: 67 of
    1-13 m2 along the fence)."""
    rules = load_rules().edge_lines
    pieces = unary_union([box(0, 0, 20, 1),            # 20 m2
                          box(0, 10, 100, 11),         # 100 m2, 1 m wide
                          box(0, 20, 12, 32)])         # 144 m2, 12 m wide
    got = fl._min_pieces(pieces, rules.yard_piece_min_m2, rules.yard_piece_min_width_m)
    assert got.area == pytest.approx(144.0)
