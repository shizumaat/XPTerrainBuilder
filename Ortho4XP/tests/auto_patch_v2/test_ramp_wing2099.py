"""#2099 G4 twins (spec ``docs/specs/2099-G4.md`` §2 S / W / C, bar 9).

* S (``airport/ramp_wing``): a walled ramp authored as one placement at its
  own zero, butting a wing's far end, joins the mouth's group with its offset
  -- a 0.6 m gap joins, a 3 m gap does not, no mapped road between its walls
  does not; the offset reaches its plate and its record;
* W (``planar/wing_cut``): the ramp wing's own cut -- the corridor between
  its walls is ground, the lot over a wall's plan is cut back, the deck's
  group feet are unchanged;
* C (``constraints/roads.lot_chords_outside``): a lot's notch chord is no
  pair.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
import types
from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon
from shapely.geometry import box as _box

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_mouth_group2099 as MG  # noqa: E402
import test_wing_cut2099 as WC  # noqa: E402
from auto_patch_v2.airport import mouth_group as M  # noqa: E402
from auto_patch_v2.model.airport import OsmWay  # noqa: E402

LAW = MG.LAW
#: the mapped road between the ramp's walls, and the road it meets at x = 60
BETWEEN = ((0.0, -40.6), (60.0, -40.6))
CROSS = ((60.0, -100.0), (60.0, 0.0))


def _placed(oid, path, xy, plan):
    o = MG._placed(oid, path, xy)
    o.plan_bbox = plan
    return o


def _site(tmp_path, dx=0.0, foot=-7.0):
    """The deck box (floor -7.5, top 0.5) and its wing ``w1`` running 40 m
    south at x = 10.3 (top 7.2, foot -1.0 over its zero = the box's floor);
    the RAMP ``r``: two walls along x, 20 m apart (y -50.6 and -30.6), foot
    ``foot``, top 0.5 over its own zero, its south wall ``dx`` + 0.6 m east
    of the wing's end."""
    bx = MG._cuboid(tmp_path / "box.obj", -10, 10, -7.5, 0.5, -10, 10, hard=True)
    wing = MG._cuboid(tmp_path / "wing.obj", -0.3, 0.3, -1.0, 7.2, 0.0, 40.0)
    ramp = WC._walls_obj(tmp_path / f"ramp{foot}.obj",
                         [(0.0, 10.0, 30.0, 10.0, foot, foot, 0.5, 0.6),
                          (0.0, -10.0, 30.0, -10.0, foot, foot, 0.5, 0.6)])
    x0 = 10.9 + dx
    return [_placed("box", bx, (0.0, 0.0), _box(-10, -10, 10, 10)),
            _placed("w1", wing, (10.3, -10.0), _box(10.0, -50.0, 10.6, -10.0)),
            _placed("r", ramp, (x0, -40.6), _box(x0, -50.9, x0 + 30.0, -30.3))]


def _groups(objs, roads=(BETWEEN, CROSS)):
    part = MG._partition([(o.id, o.path) for o in objs], [(0, 1)])
    return M.mouth_groups(part, objs, [M.Mouth("box", -7.5, "test")], MG._cache(), LAW,
                          roads=roads)


def test_a_ramp_butting_a_wing_end_joins_with_its_offset(tmp_path):
    groups, notes = _groups(_site(tmp_path))
    (g,) = groups
    assert [w for w, _r in g.wings] == ["r", "w1"] and g.ramps == {"r"}
    assert g.offset("r") == pytest.approx(6.7, abs=0.01)          # 7.2 - 0.5
    assert any("a ramp wing" in n for n in notes)
    st = [(1.0, 2.0)]
    plates = M.wing_plates([g], {"box": (0.25, st, 0.0, "deck", 170.0)})
    assert plates["w1"][0] == pytest.approx(7.75) and plates["r"][0] == pytest.approx(1.05)
    assert plates["r"][4] == pytest.approx(170.0 - 7.5 + 6.7)
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT
    recs = M.wing_records([g], [{"id": "box", "seat": PORTAL_SEAT, "elevation": 170.0}],
                          PORTAL_SEAT)
    assert {r["id"]: r["elevation"] for r in recs} == {"w1": 162.5, "r": pytest.approx(169.2)}


def test_a_ramp_3_m_off_the_wing_end_stays_out(tmp_path):
    groups, _n = _groups(_site(tmp_path, dx=2.4))
    assert [w for w, _r in groups[0].wings] == ["w1"] and groups[0].offsets == ()


def test_a_ramp_with_no_mapped_road_between_its_walls_stays_out(tmp_path):
    groups, notes = _groups(_site(tmp_path), roads=(CROSS,))
    assert groups[0].offsets == ()
    assert any("no ramp wing" in n and "facing wall lines" in n for n in notes)


def test_a_ramps_foot_far_off_the_wings_is_refused(tmp_path):
    """The ramp's foot at the junction end 3.7 m over the wing's foot."""
    groups, notes = _groups(_site(tmp_path, foot=-4.0))
    assert groups[0].offsets == () and any("frontage_step_max_m" in n for n in notes)


def test_the_ramps_floor_is_its_own_cut_and_the_lot_over_its_wall_is_cut_back(tmp_path):
    """W: the corridor between the ramp's walls is ``wing_cut:r`` ground at
    the ramp's floor, the lot over the south wall's plan is cut back to it,
    and the deck's group feet are the wing's alone."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.wing_cut import group_walled, wing_cuts
    objs = _site(tmp_path)
    part = MG._partition([(o.id, o.path) for o in objs], [(0, 1)])
    ways = tuple(OsmWay(-k, "small_roads", pts, False, {"highway": "service"})
                 for k, pts in enumerate((BETWEEN, CROSS), 1))
    airport = types.SimpleNamespace(partition=part, osm_ways=ways)
    lot = Cell(0, "parking_lot", "pol", ((15.0, -55.0), (35.0, -55.0), (35.0, -35.0),
                                          (15.0, -35.0)), (), None, None, "groundside", "x", {})
    tun = types.SimpleNamespace(deck_bridge="box", portal="", half_width_m=3.5, axis=())
    deck = _dc.replace(WC._deck(), road=((0.0, -300.0), (0.0, 300.0)))
    cl, cuts, _notes = wing_cuts(airport, objs, MG._cache(), (deck,), (tun,), WC._Cl((lot,)), LAW)
    ramp = next(c for c in cuts if c.mouth == "r")
    assert ramp.ref == "wing_cut:r" and ramp.floor_y == pytest.approx(-7.5 + 6.7, abs=0.01)
    assert ramp.seats == (tuple(deck.seats_a), tuple(deck.seats_b)) and ramp.walls
    region = Polygon(ramp.region[0])
    assert region.contains(Point(25.0, -40.6)) and region.contains(Point(25.0, -49.5))
    lots = [Polygon(c.ring) for c in cl.cells if c.role == "parking_lot"]
    assert lots and all(q.intersection(region).area < 0.3 for q in lots)
    assert all(q.intersection(Polygon(w)).area < 0.3 for q in lots for w in ramp.walls)
    assert any(c.ref.startswith("wing_wall:r") for c in cl.cells)
    assert any(q.contains(Point(25.0, -53.0)) for q in lots)        # the lot behind the wall stays
    with_ramp, _n = group_walled((deck,), airport, objs, MG._cache(), LAW)
    alone, _n = group_walled((deck,), airport, objs[:2], MG._cache(), LAW)
    assert with_ramp[0].group_feet == alone[0].group_feet and alone[0].group_feet


def test_a_lots_notch_chord_is_no_pair():
    """C (09-05ae (1) applied to lots): a U-shaped lot's chord across its
    notch leaves the face; a road role reads none."""
    from auto_patch_v2.constraints.roads import lot_chords_outside
    ring = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (20.0, 30.0), (20.0, 10.0), (10.0, 10.0),
            (10.0, 30.0), (0.0, 30.0)]
    out = lot_chords_outside("parking_lot", ring, [], LAW)
    assert (3, 6) in out and (0, 2) in out and (0, 4) not in out
    assert lot_chords_outside("service_road", ring, [], LAW) == set()


def test_a_ramp_walls_plan_declares_its_step():
    """W: a ramp wall's plan is a declared ``wall_terrace`` line, its step
    the solved one across it, never over the wall's own height."""
    from auto_patch_v2.model.wing_cut import WallLine, WingCut
    from auto_patch_v2.pipeline.wing_wall_joints import wing_wall_joints
    line = WallLine("r", ((0.0, 0.0), (20.0, 0.0)), ((0.0, -1.0), (20.0, -1.0)), (-5.0, -4.0),
                    (0.5, 0.5))
    plan = ((0.0, 0.0), (20.0, 0.0), (20.0, -1.0), (0.0, -1.0))
    cut = WingCut("r", "wing_cut:r", (), (line,), walls=(plan,))
    xy = {0: (0.0, 0.0), 1: (20.0, 0.0), 2: (20.0, -1.0), 3: (0.0, -1.0), 4: (50.0, 50.0)}
    vs = {v: types.SimpleNamespace(xy=p, key=(43.0 + p[1] * 1e-5, -79.0 + p[0] * 1e-5))
          for v, p in xy.items()}
    planar = types.SimpleNamespace(wing_cuts=(cut,), vertices=vs)
    z = [160.0, 161.0, 164.5, 164.5, 0.0]
    (j,) = wing_wall_joints(planar, LAW, z)
    assert j["kind"] == "wall_terrace" and j["shapes"] == ["wing_wall:r"]
    assert j["height_m"] == pytest.approx(5.5) and j["declared_step_m"] == pytest.approx(4.51)
    (k,) = wing_wall_joints(planar, LAW, [150.0, 161.0, 164.5, 164.5, 0.0])
    assert k["declared_step_m"] == pytest.approx(5.51)                 # never over the wall


def test_a_back_strip_stands_a_parapet_under_the_top_only_near_the_ground():
    """D5' (RULINGS 2026-11-16l): the back strip's level is the top less the
    parapet; a station whose level stands over frontage_step_max_m off the
    ground behind the wall gets none (the wall stands proud there)."""
    from auto_patch_v2.model.wing_cut import WallLine
    from auto_patch_v2.planar.wing_cut import _parapet_ok
    line = WallLine("w", ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0)),
                    ((0.0, -1.0), (10.0, -1.0), (20.0, -1.0)), (1.0, 1.0, 1.0), (6.0, 6.0, 6.0))
    ground = {0.0: 104.6, 10.0: 103.0, 20.0: 101.0}          # behind each station
    env = types.SimpleNamespace(parapet=float(LAW.tables.structures.tunnel.object
                                              .retaining_parapet_m),
                                step_max=float(LAW.tables.emit.design.frontage_step_max_m),
                                dem=types.SimpleNamespace(z=lambda x, y: ground[round(x, 1)]))
    assert _parapet_ok(line, env, 0.0, {"floor_z": 100.0}) == [True, True, False]


def test_the_back_rows_hold_the_top_less_its_drop():
    """D5': the strip behind a line is held at its top less the drop the
    planar stage read (a parapet; none where the airside's ground is behind)."""
    from auto_patch_v2.model.wing_cut import WallLine, WingCut, wing_top_y
    line = WallLine("w", ((0.0, 0.0), (0.0, 20.0)), ((-0.6, 0.0), (-0.6, 20.0)), (1.0, 1.0),
                    (6.0, 6.0), (1.0, 0.0))
    cut = WingCut("p", "wing_cut:p", (), (line,), floor_z=100.0)
    assert wing_top_y(cut, (-2.0, 0.0)) == pytest.approx(5.0)
    assert wing_top_y(cut, (-2.0, 20.0)) == pytest.approx(6.0)
    assert wing_top_y(cut, (-2.0, 10.0)) == pytest.approx(5.5)
