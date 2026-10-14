"""Twins of the base-slab witness (owner RULINGS 2026-10-10o (B), issue
#229; ``geom/base_slab``): a flat plane at the base of objects is pavement —
its OPEN part leaves every pad (``pad_shades``) and is a gap sheet
(``classify/gap_mint``); a floor under a roof, a raised plate, a thick body
and a free-standing plane are not admitted."""
from __future__ import annotations

import copy
import types

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.classify import gap_mint as gm
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.geom import base_slab as bs
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import base_slab_law
from auto_patch_v2.model.rebake import Member, Part, Unit

LAW, RULES = Law.for_airport("HECA"), load_rules()
LW = base_slab_law(LAW)

# a metre frame: lat = y, lon = x (the twin's to_xy is the identity)
def to_xy(lon, lat):
    return (lon, lat)


def _ring(b):
    return tuple((y, x) for x, y in tuple(b.exterior.coords)[:-1])


def _part(pid, b, *, base_y=0.0, h=0.3, feet=True):
    c = b.centroid
    x0, y0, x1, y1 = b.bounds
    return Part(pid, pid, c.y, c.x, base_y, b.area, (y0, x0, y1, x1),
                feet=((c.y, c.x, base_y),) if feet else (),
                rings=(_ring(b),), height_m=h)


def _partition(*parts):
    m = Member("dsf:obj0", "Terminals/slab.obj", "", "", 0.0, tuple(parts))
    return types.SimpleNamespace(units=(Unit("unit:0", (0.0, 0.0), 0.0, (m,)),))


def test_the_law_is_read_once_and_armed():
    assert LW.armed and LW.tall_min_m == LAW.tables.structures.placement.chain_min_height_m
    assert LW.min_m2 == 300.0 and LW.max_height_m == 2.0


def test_the_open_part_of_a_forecourt_slab_at_a_terminal_is_admitted():
    wall = _part(0, box(0, 0, 40, 40), h=12.0)           # the terminal
    slab = _part(1, box(40, 0, 100, 40))                 # the forecourt, touching it
    got = bs.base_slabs(_partition(wall, slab), to_xy, LW)
    assert len(got) == 1 and got[0].comp == 1
    assert got[0].open.area == pytest.approx(60 * 40, rel=1e-6)


def test_ground_under_a_roof_or_a_booth_is_not_the_slab():
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(0, 0, 100, 40))                  # runs under the terminal
    booth = _part(2, box(70, 10, 80, 20), base_y=0.3, h=3.0)
    got = bs.base_slabs(_partition(wall, slab, booth), to_xy, LW)
    assert len(got) == 1
    assert got[0].open.area == pytest.approx(60 * 40 - 100, rel=1e-6)
    assert got[0].open.intersection(box(0, 0, 40, 40)).area == pytest.approx(0.0, abs=1e-6)


def test_a_floor_plate_under_its_own_roof_stays_the_building_pad():
    wall = _part(0, box(0, 0, 4, 4), h=6.0)
    floor = _part(1, box(0, 0, 50, 50))
    roof = _part(2, box(0, 0, 50, 50), base_y=5.0, h=0.5, feet=False)
    assert bs.base_slabs(_partition(wall, floor, roof), to_xy, LW) == ()


@pytest.mark.parametrize("kw", [dict(base_y=1.5), dict(h=3.0), dict(feet=False)])
def test_raised_thick_or_elevated_plates_are_not_base_slabs(kw):
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    plate = _part(1, box(40, 0, 100, 40), **kw)
    assert bs.base_slabs(_partition(wall, plate), to_xy, LW) == ()


def test_a_free_standing_plane_is_not_at_the_base_of_objects():
    far = _part(0, box(0, 0, 40, 40), h=12.0)
    plane = _part(1, box(45, 0, 100, 40))                # 5 m from the building
    assert bs.base_slabs(_partition(far, plane), to_xy, LW) == ()


def test_pad_shades_carry_the_slab_and_disarmed_carries_nothing():
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(40, 0, 100, 40))
    part = _partition(wall, slab)
    sh = bs.pad_shades(part, to_xy, LW._replace(leaves_pads=True))
    assert sh is not None and sh.area == pytest.approx(2400.0, rel=1e-6)
    off = LW._replace(min_m2=0.0)
    assert bs.pad_shades(part, to_xy, off) is None
    assert bs.slab_polygons(part, to_xy, off) == []


def test_one_shade_path_carries_the_slab_and_the_sunken_ramp():
    """#655 + #657 merged: the sunken-ramp ground (``Airport.sunken_ramps``)
    rides the SAME ``pad_shades`` call as the slabs, armed or not."""
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(40, 0, 100, 40))
    part = _partition(wall, slab)
    ramp = box(200, 0, 210, 10)
    on = bs.pad_shades(part, to_xy, LW._replace(leaves_pads=True), ramp)
    assert on.area == pytest.approx(2500.0, rel=1e-6)
    off = bs.pad_shades(part, to_xy, LW._replace(leaves_pads=False), ramp)
    assert off.equals(ramp)
    assert bs.pad_shades(part, to_xy, None, None) is None


def test_the_gap_mint_takes_the_slab_as_a_sheet():
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(40, 0, 100, 40))
    frame = types.SimpleNamespace(
        entry=lambda: to_xy,
        transformers=lambda: (None, lambda x, y: (30.0 + y * 1e-5, 31.0 + x * 1e-5)))
    airport = types.SimpleNamespace(frame=frame, osm_ways=(), gap_sheets=(),
                                    partition=_partition(wall, slab))
    from shapely.geometry import LineString  # noqa: F401
    from auto_patch_v2.classify.evidence import Evidence
    ev = Evidence([], Polygon(), [], Polygon(), [], [], [], Polygon(), None,
                  False, 0, [], 0, 0)
    out = []

    def add(role, ref, poly, kind, cn=None, cl=None, evidence=None):
        out.append((role, ref, poly, kind))
    stats = gm.mint_gap_pieces(airport, ev, [], LAW, RULES, add, [])
    assert stats["base_slab_sheets"] == 1
    assert stats["base_slab_sheet_m2"] == pytest.approx(2400.0, rel=1e-6)
    # 14d (2): a 60 x 40 m forecourt has LOT proportions
    assert [r for r, *_ in out] == [gm.LOT_ROLE] and out[0][2].area > 2000.0


def test_the_base_of_objects_is_not_one_object_files():
    """A ground plane placed on its own (HECA ``OB-asphalt``) beside another
    file's building is a base slab; that building's ring covers it."""
    slab = _part(0, box(0, 0, 100, 40))
    m0 = Member("dsf:obj0", "ground/asphalt.obj", "", "", 0.0, (slab,))
    bldg = _part(1, box(80, 0, 120, 40), h=9.0)
    m1 = Member("dsf:obj1", "Hangar/hangar.obj", "", "", 0.0, (bldg,))
    part = types.SimpleNamespace(units=(Unit("unit:0", (0.0, 0.0), 0.0, (m0,)),
                                        Unit("unit:1", (0.0, 0.0), 0.0, (m1,))))
    got = bs.base_slabs(part, to_xy, LW)
    assert len(got) == 1 and got[0].unit == "unit:0"
    assert got[0].open.area == pytest.approx(80 * 40, rel=1e-6)


def test_a_slab_against_an_apron_stays_groundside_pavement():
    """10o (B): the slab is groundside pavement — a piece standing on it is
    never judged into the apron (the airside never moves for it)."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.law.tables import role_side
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(40, 0, 100, 40))
    frame = types.SimpleNamespace(
        entry=lambda: to_xy,
        transformers=lambda: (None, lambda x, y: (30.0 + y * 1e-5, 31.0 + x * 1e-5)))
    airport = types.SimpleNamespace(frame=frame, osm_ways=(), gap_sheets=(),
                                    partition=_partition(wall, slab))
    apron = box(40, -60, 100, 0)
    cell = Cell(0, "apron", "pav1", tuple(apron.exterior.coords)[:-1], (), None,
                None, role_side(LAW, "apron"), "apron", {})
    from auto_patch_v2.classify.evidence import Evidence
    ev = Evidence([], Polygon(), [], Polygon(), [], [], [], Polygon(), None,
                  False, 0, [], 0, 0)
    out = []

    def add(role, ref, poly, kind, cn=None, cl=None, evidence=None):
        out.append((role, ref, poly, kind, dict(evidence or {})))
    stats = gm.mint_gap_pieces(airport, ev, [cell], LAW, RULES, add, [])
    assert [(r, k) for r, _ref, _p, k, _e in out] == [(gm.LOT_ROLE, gm.KIND)]
    assert out[0][4]["base_slab"] == 1.0 and out[0][4]["touches_apron"] == 1.0
    assert stats["gap_pieces_apron"] == 0 and stats["gap_pieces_base_slab"] == 1


# ── owner RULINGS 2026-10-14d (lane drape229) ──────────────────────────

def _faces(table):
    """A face reader over ``{comp: FaceFacts}``."""
    return lambda member, comp: table.get(comp)


def test_a_kerb_ring_or_a_dock_is_not_a_plate():
    """Rule 5: a component whose SIDE faces dominate is not a slab (HECA
    ``T23/door`` comp 9 side 0.63; OTHH ``16L_ILS_Dock`` comp 0, 0.80)."""
    wall = _part(0, box(0, 0, 40, 40), h=12.0)
    slab = _part(1, box(40, 0, 100, 40))
    part = _partition(wall, slab)
    kerb = _faces({1: bs.FaceFacts(0.63, 0.0)})
    plate = _faces({1: bs.FaceFacts(0.08, 0.0)})
    assert bs.base_slabs(part, to_xy, LW, kerb) == ()
    assert len(bs.base_slabs(part, to_xy, LW, plate)) == 1
    # no facts (an unreadable file): the walled-touch reading stands
    assert len(bs.base_slabs(part, to_xy, LW, _faces({}))) == 1


def test_a_level_plate_with_no_wall_is_admitted_on_the_drape_side():
    """Rule 6: a LEVEL plate touching no walled part, holding a lane disc,
    is a slab (touches False); a sloped sheet, a sliver and a plate read
    without a face reader are not."""
    far = _part(0, box(0, 0, 40, 40), h=12.0)
    plane = _part(1, box(45, 0, 100, 40))                # 5 m from the building
    part = _partition(far, plane)
    level = _faces({1: bs.FaceFacts(0.1, 0.0)})
    got = bs.base_slabs(part, to_xy, LW, level)
    assert len(got) == 1 and got[0].touches is False
    rock = _faces({1: bs.FaceFacts(0.36, 0.83)})         # KASE Aspen_Rockwall
    assert bs.base_slabs(part, to_xy, LW, rock) == ()
    assert bs.base_slabs(part, to_xy, LW) == ()
    sliver = _partition(far, _part(1, box(45, 0, 345, 3)))   # 3 m wide
    assert bs.base_slabs(sliver, to_xy, LW, level) == ()


def test_proportions_read_a_curved_road_as_a_road_and_a_square_as_a_lot():
    """14d (2): ROAD = typical width <= [service] free_max_width_m and run
    >= [apron] arm_min_aspect widths; a road's junction bulge does not make
    it a lot (the widest place is not the proportion)."""
    from shapely.geometry import LineString
    from auto_patch_v2.geom.proportions import road_proportioned, typical_width_m
    road = LineString([(0, 0), (200, 0), (300, 100), (300, 400)]).buffer(5.0)
    road = road.union(box(195, -15, 225, 15))            # a 30 m junction
    W, A = RULES.service.free_max_width_m, RULES.apron.arm_min_aspect
    assert typical_width_m(box(0, 0, 100, 10)) == pytest.approx(10.0, rel=0.15)
    assert road_proportioned(road, W, A)
    assert gm.slab_role(road, RULES) == gm.ROLE
    assert not road_proportioned(box(0, 0, 60, 40), W, A)
    assert gm.slab_role(box(0, 0, 60, 40), RULES) == gm.LOT_ROLE
