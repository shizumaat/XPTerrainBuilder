"""THE FRONTAGE LAW, BOTH SIGNS (RULINGS 2026-11-25g; spec
``docs/specs/terminal-frontage-split-level-20261125.md`` step 2, lane
lfront2): the airside floor the apron's own objects stand at, a held
record a storey down as its block's lower-level witness, the record on its
block reconciled to a minted level, the band read along the face both
signs, the classify wall, and the census family.  Synthetic."""
from __future__ import annotations

import os
import sys
import types

from auto_patch_v2.airport import unit_storey as us
from auto_patch_v2.constraints import kerb_frontage as kf
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import LANDSIDE_KERB, UNIT_LEVELS
from shapely.geometry import LineString, MultiLineString, box

LAW = Law.for_airport("SYNT")
AIR = box(-80.0, -10.0, 0.0, 100.0)
LAND = box(100.0, -10.0, 160.0, 100.0)


def _part(x0, y0, x1, y1, base_y, feet=True, height=4.0):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=((y0, x0, base_y),) if feet else (),
                                 line=False, scatter=False, height_m=height)


class _Dem:
    def __init__(self, air: float, land: float):
        self.air, self.land = air, land

    def z(self, x, y):
        return self.land if x > 40.0 else self.air


def _airport(parts, air=0.0, land=0.0, pavement=True):
    unit = types.SimpleNamespace(id="unit:0",
                                 members=[types.SimpleNamespace(id="m0", parts=parts)])
    pav = [types.SimpleNamespace(id="apt:1", outer=list(AIR.exterior.coords)[:-1], holes=())]
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                                 frame=types.SimpleNamespace(
                                     entry=lambda: (lambda lon, lat: (lon, lat))),
                                 dem=_Dem(air, land), retaining_walls=(), osm_ways=(),
                                 flat_site=None, pavements=pav if pavement else ())


def _apron_objects(y, n):
    """``n`` small open objects (trucks, stairs) on the apron, base ``y``."""
    return [_part(-60.0 + 4.0 * i, 10.0, -58.0 + 4.0 * i, 12.0, y, feet=False, height=1.5)
            for i in range(n)]


def _terminal(land_y, floor_y=0.0, size=90.0):
    floor = [_part(0.0, 0.0, 40.0, size, floor_y)]
    land = [_part(60.0 + 6.0 * i, 0.0, 64.0 + 6.0 * i, size, land_y) for i in range(6)]
    return floor + land


def test_the_airside_floor_is_where_the_aprons_objects_stand():
    """LDSP: the frame's zero is a storey under the apron; the apron's own
    open objects outnumber the grounded parts there, so the floor is
    theirs and the landside hall reads a storey DOWN."""
    parts = _terminal(-2.8) + _apron_objects(3.0, 12)
    r = us.unit_levels(_airport(parts, air=3.0, land=-2.8), LAW, AIR, ground=LAND)[0]
    assert r.air_y == 3.0 and r.land_y == -2.8 and r.verdict == us.HELD
    assert abs(r.rise + 5.8) < 1e-9


def test_grounded_parts_outvote_the_open_objects():
    """PHLI: the grounded floor parts outnumber the open roof trims over
    the apt.dat pavement: the floor stands."""
    parts = _terminal(4.1) + _apron_objects(7.3, 3) + [
        _part(-5.0 + i, 20.0, -4.5 + i, 21.0, 0.0) for i in range(5)]
    r = us.unit_levels(_airport(parts, land=4.0), LAW, AIR, ground=LAND)[0]
    assert r.air_y == 0.0 and r.land_y == 4.1


def test_no_apt_pavement_reads_the_grounded_floor():
    parts = _terminal(-2.8) + _apron_objects(3.0, 12)
    r = us.unit_levels(_airport(parts, pavement=False), LAW, AIR, ground=LAND)[0]
    assert r.air_y == 0.0


def test_the_band_confirms_by_the_rises_side():
    assert kf._confirms(15.0, 17.0, -5.7, 0.0)          # under the apron's ground
    assert not kf._confirms(15.0, 17.0, -5.7)           # half the rise not shown
    assert not kf._confirms(17.5, 17.0, -5.7, 0.0)      # above it: no
    assert kf._confirms(49.3, 47.1, 4.1) and not kf._confirms(47.5, 47.1, 4.1)


def _map(y):
    """Band vertex 1 (lot, 0.8 m off the face), wall vertex 2 (apron on the
    plan edge), datum 3 inside the plan, vertex 4 along the plan's
    airside end (no face there)."""
    xy = {1: (0.0, 0.8), 2: (0.0, 0.0), 3: (0.0, -10.0), 4: (-50.8, -10.0)}
    face = types.SimpleNamespace
    faces = {0: face(id=0, ref="lot0", role="parking_lot", ring=(1, 4), holes=()),
             1: face(id=1, ref="apron0", role="apron", ring=(2,), holes=())}
    plan = box(-50.0, -20.0, 50.0, 0.0)
    rec = {"lot": None, "unit": 0, "y": y, "plan": plan, "air_z": 17.0,
           "face": MultiLineString([LineString([(-50.0, 0.0), (50.0, 0.0)])])}
    return types.SimpleNamespace(
        faces=faces, ring_vertices=lambda ring: ring,
        vertices={v: types.SimpleNamespace(xy=p, dem_z=15.0) for v, p in xy.items()},
        registries=types.SimpleNamespace(held={"b": {LANDSIDE_KERB: (rec,)}}, landings={}))


def test_a_lower_frontage_is_read_along_the_face(monkeypatch):
    import auto_patch_v2.model.platform as mp
    monkeypatch.setattr(mp, "stage_air_vertices", lambda pm, law: {2})
    monkeypatch.setattr(mp, "datum_vertices", lambda pm, law, fills=False: {"b": 3})
    pm = _map(-5.7)
    kerb, _wall = kf.kerb_vertices(pm, LAW)
    assert set(kerb) == {1}                    # vertex 4 is off the face
    up, down = kf.kerb_frontage_rows(pm, LAW)
    assert dict(up.terms) == {1: 1.0, 3: -1.0} and up.hi == -5.7


def _rec(verdict=us.HELD, area=421.0, clues=None):
    lv = (us.Level(-2.7, area, 5, 1.0),)
    return us.UnitLevels(0, box(0, 0, 10, 10), 3.0, -2.7, lv, "storey_parts",
                         MultiLineString(), (17.2, 11.4), verdict, clues or {})


def _ap(deck=""):
    m = types.SimpleNamespace(deck_kind=deck)
    return types.SimpleNamespace(partition=types.SimpleNamespace(
        units=[types.SimpleNamespace(members=[m])]))


def test_the_unit_record_is_published_unless_a_lot_holds_the_unit():
    from auto_patch_v2.planar.kerb_frontage import _unit_records
    reg = types.SimpleNamespace(held={"b": {UNIT_LEVELS: _rec()}, "c": {}})
    got = _unit_records(reg, set(), _ap(), LAW)
    assert [b for b, _r in got] == ["b"] and got[0][1]["y"] == -5.7
    assert _unit_records(reg, {0}, _ap(), LAW) == []


def test_the_frontage_law_takes_only_a_held_floor_with_no_kerb_deck():
    assert us.frontage_held(_rec(), _ap(), LAW)
    assert not us.frontage_held(_rec(us.FAR), _ap(), LAW)
    assert not us.frontage_held(_rec(), _ap("flag"), LAW)            # L3: a pack deck
    assert not us.frontage_held(_rec(clues={"upper_roads": [7]}), _ap(), LAW)
    assert not us.frontage_held(_rec(area=0.9), _ap(), LAW)          # no floor's worth


def test_the_minted_level_wins():
    """KATL ``building32``: storey parts -18.8, the frame's lower floor
    minted -15.00 -- the record reads the minted level."""
    from auto_patch_v2.planar.unit_levels_read import _minted
    reg = types.SimpleNamespace(landings={
        "building32/p2": {"block": "building32", "y": -15.0, "deck": None},
        "building32/p1": {"block": "building32", "y": 6.0, "deck": None}})
    assert _minted(reg, "building32", -18.8) == -15.0
    assert _minted(reg, "building32", 4.0) == 6.0
    assert _minted(reg, "other", -18.8) is None


def test_held_down_skips_a_floor_zero_frame(monkeypatch):
    from auto_patch_v2.planar import low_level as ll
    rec = us.UnitLevels(0, box(0, 0, 10, 10), 3.0, -2.7, (), "storey_parts",
                        MultiLineString(), (17.2, 11.4), us.HELD, {})
    member = types.SimpleNamespace(floor_zero=False)
    ap = types.SimpleNamespace(partition=types.SimpleNamespace(
        units=[types.SimpleNamespace(members=[member])]),
        frame=types.SimpleNamespace(entry=lambda: None))
    monkeypatch.setattr(ll, "unit_share", lambda P, airport, to_xy: (0, []))
    assert ll._held_down(box(0, 0, 1, 1), [rec], ap) is rec
    assert ll._held_down(box(0, 0, 1, 1), [rec], ap,
                         [types.SimpleNamespace(unit=0)]) is None
    member.floor_zero = True
    assert ll._held_down(box(0, 0, 1, 1), [rec], ap) is None


def test_the_census_prices_a_band_vertex_off_its_floor():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
    import check_grade as cg
    from check_grade_lib.families.frontage_level import check_frontage_level
    nodes = {"a": (43.5, 16.3), "b": (43.5001, 16.3)}
    road = cg.Way(wid="r", role="service_road", ref="r0", aeroway="",
                  nids=["a", "b"], elevs=[13.07, 14.0], tags={"role": "service_road"})
    rec = {"band_ll": [[43.5, 16.3, 13.07], [43.5001, 16.3, 13.07]]}
    rows = check_frontage_level([rec], nodes, [road])
    assert len(rows) == 1 and abs(rows[0].de_m - 0.93) < 1e-9
    assert check_frontage_level(None, nodes, [road]) == []
    assert "frontage_level" in {k for k, _t, _b in cg.LAW_FAMILIES}
