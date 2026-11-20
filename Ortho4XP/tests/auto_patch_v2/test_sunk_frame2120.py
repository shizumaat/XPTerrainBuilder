"""Twin of ``airport/sunk_frame`` -- the wall class's FOURTH WITNESS (#2120
R2, spec ``docs/specs/2120-R2.md`` §1-§2).  A block its author drew DOWN
from his ground (``OBJECT_AGL`` < 0) is a retaining wall where the ground
steps across it: its upper ground at ``y = -lift`` when its top stands
there (R2), or at its road plate's ``y`` when a mapped road runs on a plate
capping it (R3); a flat sunk frame (a pool) is no wall (R4).  KATL's 2026-11
pack: ``katl126_wall`` (y 0..20, AGL -19.81) floated its road plate 20 m
standing its walls' feet on the ground; ``katl125_wall`` (AGL -4.57, its
origin on the LOW level) carries its road plate at y 20.

W5: a retaining wall never chains a building (16k, 14a (2)): its member is
no §16g unit member, and only a runway-end WALLED plate leads a unit."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pytest
from auto_patch_v2.airport.wall_class import wall_class_components
from auto_patch_v2.classify.rules import load_rules
from tests.auto_patch_v2.test_wall_class_thick import FRAME, _StepDem

CFG = load_rules().service
_M_LAT = 1.0 / 111_320.0
LAT0, LON0 = 33.64, -84.42


def _ring(width: float, length: float = 100.0):
    dlon = length / (111_320.0 * np.cos(np.radians(LAT0)))
    return [(LAT0, LON0), (LAT0, LON0 + dlon), (LAT0 + width * _M_LAT, LON0 + dlon),
            (LAT0 + width * _M_LAT, LON0)]


def _airport(lift: float, height: float, step: float, *, width: float = 20.0,
             plate: bool = False, road: dict | None = None):
    """A block ``width`` m across (north) and 100 m long (east) placed at
    ``lift``, its walls y 0..``height``; the ground ``step`` m higher north
    of its axis; optionally a plate row at its top and a mapped road along
    the block's axis."""
    ring = _ring(width)
    wall = NS(rings=[ring], height_m=height, base_y=0.0, comp=0, line=False, feet=(1,))
    members = [NS(id="dsf:obj1", resource="objects/block_000.obj", parts=[wall],
                  zero_y=0.0, deck_kind="", origin=(LAT0, LON0))]
    if plate:
        top = NS(rings=[ring], height_m=0.0, base_y=height, comp=0, line=False, feet=())
        members.append(NS(id="dsf:obj2", resource="objects/block_002.obj", parts=[top],
                          zero_y=0.0, deck_kind="candidate", origin=(LAT0, LON0)))
    to_xy = FRAME.entry()
    _x, y_axis = to_xy(LON0, LAT0 + 0.5 * width * _M_LAT)
    ways = []
    if road is not None:
        a, b = to_xy(LON0, LAT0), to_xy(LON0 + 90.0 / (111_320.0 * np.cos(np.radians(LAT0))),
                                         LAT0)
        ways.append(NS(points=[(a[0] + 5.0, y_axis), (b[0], y_axis)], tags=road, closed=False))
    unit = NS(id="unit:1", agl_m=lift, members=members, anchor=(LAT0, LON0))
    return NS(partition=NS(units=[unit]), frame=FRAME, osm_ways=ways,
              dem=_StepDem(y_axis, 300.0, 300.0 - step), sunken_ramps=None)


def _deck(lift: float = -4.57):
    """A R3 deck block whose plan stands wholly on the LOW ground: the
    ground steps up at its north (upper) face (2120-WF3 W-A: a deck block
    is read part by part, so its plan must be low to be all deck)."""
    ap = _airport(lift, 20.0, 10.0, plate=True, road={"highway": "service"})
    _x, y_face = FRAME.entry()(LON0, LAT0 + 20.0 * _M_LAT)
    ap.dem = _StepDem(y_face, 300.0, 290.0)
    return ap


def _retaining(ap):
    return [c for c in wall_class_components(ap, CFG) if c.retains]


def test_r2_a_stepped_block_sunk_to_its_top_retains_from_its_authored_ground():
    (c,) = _retaining(_airport(-19.81, 20.0, 10.0))
    assert c.low_side_source == "dem" and c.seat_z is None
    assert c.retained_top_y == pytest.approx(19.81)     # y_up = -lift
    assert c.top_y == pytest.approx(20.0)               # its parapet the author's 0.19 m
    assert c.retained_m == pytest.approx(10.0)          # the step, under y_up - base


def test_r3_a_plate_topped_block_carrying_a_road_retains_from_its_plate():
    (c,) = _retaining(_airport(-4.57, 20.0, 10.0, plate=True, road={"highway": "service"}))
    assert c.retained_top_y == pytest.approx(20.0)      # the plate, whatever -lift says
    assert c.retained_m == pytest.approx(10.0)


@pytest.mark.parametrize("road", [
    None,                                               # a flat-roofed building on a slope
    {"highway": "service", "tunnel": "yes"},            # a bore under it
    {"highway": "service", "layer": "-1"},              # a road under it
])
def test_r3_a_plate_topped_block_with_no_road_on_its_plate_is_no_wall(road):
    assert _retaining(_airport(-4.57, 20.0, 10.0, plate=True, road=road)) == []


def test_r4_a_flat_sunk_frame_is_no_wall():
    assert _retaining(_airport(-19.81, 20.0, 0.0)) == []
    assert _retaining(_airport(-2.2, 4.04, 0.0)) == []  # a pool sunk in flat ground


class _SlopeDem:
    """A plane rising ``grade`` northward."""

    def __init__(self, grade: float):
        self.grade = grade

    def z_many(self, xs, ys):
        return 300.0 + self.grade * np.asarray(ys, dtype=float)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def test_r4_a_pool_sunk_in_a_slope_is_no_wall():
    """ELLX ``pool_5`` (lift -2.20, rim walls 3-4 m, its block on a slope):
    read at the wall class's own ring (its 4 m height) the ground steps
    across no wall of it; 8 m out it would read the slope (54 %)."""
    to_ll = FRAME.transformers()[1]
    walls = []
    for k, (x0, y0, x1, y1) in enumerate([(0, 0, 20, 0.3), (0, 9.7, 20, 10), (0, 0, 0.3, 10),
                                          (19.7, 0, 20, 10)]):
        ring = [to_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        walls.append(NS(rings=[ring], height_m=4.0, base_y=0.0, comp=k, line=False, feet=(1,)))
    m = NS(id="dsf:pool", resource="objects/pool_5.001.obj", parts=walls, zero_y=0.0,
           deck_kind="", origin=to_ll(0.0, 0.0))
    ap = NS(partition=NS(units=[NS(id="unit:1", agl_m=-2.2, members=[m], anchor=m.origin)]),
            frame=FRAME, osm_ways=[], dem=_SlopeDem(0.15), sunken_ramps=None)
    assert _retaining(ap) == []


@pytest.mark.parametrize("lift,height", [
    (0.0, 20.0),        # standing on its authored ground
    (-1.5, 20.0),       # its top far over the author's ground: a building on a slope
    (+4.0, 20.0),       # lifted
    (-6.0, 3.0),        # wholly buried under the author's ground
])
def test_a_frame_that_is_not_sunk_is_no_wall(lift, height):
    assert _retaining(_airport(lift, height, 10.0)) == []


def test_w5_a_retaining_plate_leads_no_unit_a_walled_plate_does():
    from auto_patch_v2.airport.open_frame_seat import plate_led, walled_unit_zero
    wall = NS(plate_kind="retaining", plate_y=19.81, plate_stations=((LAT0, LON0),))
    walled = NS(plate_kind="walled", plate_y=-9.9, plate_stations=((LAT0, LON0),))
    assert plate_led(wall) and plate_led(walled)
    assert walled_unit_zero([walled], lambda la, lo: 300.0) == pytest.approx(309.9)


def test_w5_a_terminal_touching_a_retaining_wall_keeps_its_own_seat():
    """the wall's member is no §16g unit member: the buildings it touches
    take the zero they have with no wall in the plan (#2099 P5b's fixture,
    the plate of kind ``retaining``)"""
    from auto_patch_v2.airport.retaining_seat import RETAINING_PLATE
    from tests.auto_patch_v2.test_wall_top_plate2099 import _plan, _plan_ns, _units
    counts: dict = {}
    seats = _units(_plan(kind=RETAINING_PLATE), counts)
    assert (2, 0, 0) not in seats and counts["unit_members_left_retaining"] == 1
    alone = _plan_ns(_plan().units[:2])
    assert {k: v[1] for k, v in seats.items()} == {k: v[1] for k, v in _units(alone).items()}


def test_w3_one_seat_path_the_frame_rides_its_wall_plate():
    """``retaining_seats`` seats the sunk block's plate ``y_up`` on its upper
    stations, and every row of its frame (the plate row beside the walls)
    rides the same plate"""
    from auto_patch_v2.airport.retaining_seat import retaining_seats
    ap = _airport(-4.57, 20.0, 10.0, plate=True, road={"highway": "service"})
    got = {s.oid: s for s in retaining_seats(ap, CFG, 0.5, 5.0)}
    assert set(got) == {"dsf:obj1", "dsf:obj2"}
    assert got["dsf:obj1"].y == got["dsf:obj2"].y == pytest.approx(20.0)
    z = ap.dem.z_many([p[0] for p in got["dsf:obj1"].stations],
                      [p[1] for p in got["dsf:obj1"].stations])
    assert np.all(z == 300.0)                           # the upper level only


def test_w3_a_block_with_no_two_long_faces_is_seated_on_its_high_ring():
    """no face pair (``wall_sides._wall_faces``: here a triangle): the ring
    round the footprint, its high side only"""
    from auto_patch_v2.airport.retaining_seat import retaining_seats
    from auto_patch_v2.airport.wall_class import WallComponent
    from shapely.geometry import Polygon
    ap = _airport(-19.81, 20.0, 10.0)
    _x, y_axis = FRAME.entry()(LON0, LAT0 + 10.0 * _M_LAT)
    tri = Polygon([(0.0, y_axis - 15.0), (60.0, y_axis - 15.0), (30.0, y_axis + 15.0)])
    comp = WallComponent((tri,), 20.0, "objects/block_000.obj", 0, True, 10.0, 20.0, None,
                         (LAT0, LON0), NS(id="dsf:obj1"), 19.81, "dem",
                         sunk_rule="upper")       # the sunk witness's reading (R2)
    (s,) = retaining_seats(ap, CFG, 0.5, 5.0, comps=[comp])
    z = ap.dem.z_many([p[0] for p in s.stations], [p[1] for p in s.stations])
    assert len(s.stations) >= 4 and np.all(z == 300.0)


def test_the_sunk_census_lists_what_the_witness_admits():
    """``tools/sunk_census.py`` (the airport census, #2120 R2 §2) reads the
    ONE classifier: a row per sunk-admitted wall, none for a flat frame"""
    import importlib.util
    from pathlib import Path
    tool = Path(__file__).resolve().parents[2] / "tools" / "sunk_census.py"
    spec = importlib.util.spec_from_file_location("_sunk_census", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (row,) = mod.sunk_rows(_deck(), CFG)
    assert row["id"] == "dsf:obj1" and row["rule"] == "plate" and row["y_up"] == 20.0
    assert row["class"] == "B" and row["cover_m2"] > 0.9 * row["area_m2"]
    assert row["unit"] == "unit:1" and row["lift"] == -4.57
    assert abs(row["lat"] - LAT0) < 0.001 and abs(row["lon"] - LON0) < 0.002
    assert mod.sunk_rows(_airport(-19.81, 20.0, 0.0), CFG) == []


def test_b1_a_deck_block_retains_only_the_strip_along_its_upper_face():
    """2120-W3 B1 (class B, R3 with its origin on the low level): the one
    retaining piece is the ``FILL_SLOT_M`` strip inside its plan along its
    UPPER face; its whole plan is its ``cover`` -- no pad from any of it
    (``wall_shade``) -- and it carries no fill of its own"""
    from auto_patch_v2.airport.wall_shade import wall_shade
    from auto_patch_v2.model.wall_reach import FILL_SLOT_M
    ap = _deck()
    (c,) = _retaining(ap)
    assert c.sunk_rule == "plate" and c.fill_drop_m is None
    (cover,) = c.cover                  # 2120-WF3 W-A: the plan less the strip
    (strip,) = c.pieces
    plan = strip.union(cover)
    assert strip.area == pytest.approx(FILL_SLOT_M * 100.0, rel=0.02)
    assert strip.bounds[3] == pytest.approx(plan.bounds[3], abs=0.01)  # the upper (north) face
    assert strip.bounds[1] == pytest.approx(plan.bounds[3] - FILL_SLOT_M, abs=0.01)
    assert wall_shade(ap, CFG).buffer(0.01).covers(plan)     # to the millimetre


def test_b1_a_road_under_the_deck_is_not_cut_and_reads_its_own_ground():
    """under the deck the ground stays low: a road there is neither cut
    (``far_side_cut``) nor lifted (``smear_sampler`` reads the low ground)"""
    from auto_patch_v2.airport.wall_sides import (
        crosses_wall,
        far_side_cut,
        smear_sampler,
        wall_sides,
    )
    from shapely.geometry import box
    ap = _deck()
    (c,) = _retaining(ap)
    (w,) = wall_sides(ap, CFG, [c])
    x0, y0, x1, _y1 = c.cover[0].bounds
    road = box(x0 + 10.0, y0 + 2.0, x1 - 10.0, y0 + 8.0)              # 10+ m off the strip
    assert far_side_cut(road, [w]).area == pytest.approx(road.area)
    sample = smear_sampler(ap.dem.z_many, [w])
    mid = (0.5 * (x0 + x1), y0 + 5.0)
    assert float(sample([mid[0]], [mid[1]])[0]) == pytest.approx(290.0)
    assert not crosses_wall((mid[0] - 20.0, mid[1]), (mid[0] + 20.0, mid[1]), [w])


def test_class_a_cuts_a_road_mapped_into_it_from_the_low_face_at_that_face():
    """2120-W3 class A (R2): the block is earth behind its face; a road
    entering from the low side ends at the low face, its line too"""
    from auto_patch_v2.airport.wall_sides import far_side_cut, wall_sides
    from auto_patch_v2.classify.wall_cutback import cut_lines_at_walls
    from shapely.geometry import box
    ap = _airport(-19.81, 20.0, 10.0)
    (c,) = _retaining(ap)
    assert c.sunk_rule == "upper" and c.fill_drop_m == 0.0 and not c.cover
    (w,) = wall_sides(ap, CFG, [c])
    x0, y0, x1, _y1 = w.poly.bounds
    road = box(x0 + 10.0, y0 - 10.0, x1 - 10.0, y0 + 6.0)             # 6 m into the block
    kept = far_side_cut(road, [w])
    assert kept.bounds[3] == pytest.approx(y0, abs=0.01)
    assert kept.area == pytest.approx(box(x0 + 10.0, y0 - 10.0, x1 - 10.0, y0).area, rel=0.01)
    import dataclasses as dc

    @dc.dataclass(frozen=True)
    class Cut:
        kind: str
        points: tuple
    line = Cut("road_centerline", ((x0 + 20.0, y0 - 10.0), (x0 + 20.0, y0 + 6.0)))
    (part,), _st = cut_lines_at_walls([line], [w])
    assert max(y for _x, y in part.points) == pytest.approx(y0, abs=0.01)


def test_f1_a_retaining_block_fill_rides_its_upper_face():
    """2120-W3 F1: a fill vertex is held RELATIVE to the upper-face vertices
    bracketing its station, ``fill_drop_m`` under them -- one plane row, never
    an absolute level; the drop is the rim tolerance where a plate of its
    frame caps it within that of ``y_up``"""
    from auto_patch_v2.constraints.wall_zone import (
        RetainingLine,
        face_vertices,
        fill_row,
        fill_top,
        fill_wall,
    )
    from auto_patch_v2.model.constraints import Source
    from shapely.geometry import LineString, box
    poly = box(0.0, 0.0, 100.0, 20.0)
    w = RetainingLine(poly, 40.0, 10.0, {}, LineString([(100.0, 20.0), (0.0, 20.0)]),
                      ((0.0, 300.0), (100.0, 302.0)), LineString([(0.0, 0.0), (100.0, 0.0)]),
                      None, fill_drop_m=1.0)
    xy = {1: (90.0, 20.0), 2: (40.0, 20.0), 3: (10.0, 20.2), 9: (30.0, 10.0), 7: (50.0, 30.0)}
    assert fill_wall([w], xy[9]) is w and fill_top([w], xy[9]) is None
    face = face_vertices(w, xy)
    assert [v for _s, v in face] == [1, 2, 3]
    row = fill_row(w, 9, xy[9], face, Source("wall_terrace", "r", ()))
    terms = dict(row.terms)
    assert terms[9] == 1.0 and terms[2] == pytest.approx(-2.0 / 3.0)
    assert terms[3] == pytest.approx(-1.0 / 3.0) and row.lo == row.hi == -1.0
    # with no drop read the fill is the old absolute top (another wall)
    other = w._replace(fill_drop_m=None)
    assert fill_wall([other], xy[9]) is None and fill_top([other], xy[9]) == pytest.approx(301.4)
    # the drop: rim tolerance under a plate capping it at y_up, else 0
    (c,) = _retaining(_airport(-19.81, 20.0, 10.0, plate=True))
    assert c.sunk_rule == "upper" and c.fill_drop_m == pytest.approx(1.0)


def test_d1_no_road_block_remains():
    """2120-W3 D1: the road block is deleted, not kept gated"""
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"
    hits = [p.name for p in src.rglob("*.py") if "road_block" in p.read_text(encoding="utf-8")]
    assert hits == []
