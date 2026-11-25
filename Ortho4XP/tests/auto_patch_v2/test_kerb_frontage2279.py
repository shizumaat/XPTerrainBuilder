"""#2279 step 2, THE KERB-LEVEL FRONTAGE (spec
``docs/specs/2279-kerb-frontage-spec.md``): a unit's landside lot keeps
the plan bays that front no airside (the kerb drive), carries the
building's airside floor as its kerb line, and its frontage vertices take
the unit block's datum + the storey's rise, one-way; the rows across the
building's wall are withdrawn.  Synthetic."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.classify.airside_edge import airside_edge_flip
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.classify.storey_edge import (STOREY_PLAN_KEY, STOREY_UNIT_KEY, knife_storeys,
                                                storey_band)
from auto_patch_v2.constraints import kerb_frontage as kf
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.model.registries import LANDSIDE_KERB
from auto_patch_v2.planar.kerb_frontage import landside_plans
from shapely.geometry import Polygon, box

LAW = Law.for_airport("SYNT")


def XY(lon, lat):
    return (lon, lat)


def _part(x0, y0, x1, y1, base_y, feet=False):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=((y0, x0, base_y),) if feet else (),
                                 line=False, scatter=False)


def _landside():
    """A terminal on the apron (y < 0) whose upper parts stand +4.1 over
    its floor; a 140 x 20 m KERB DRIVE bay opens on its landside face
    (y 40-60, between the wings) and the pack's lot covers the building
    and the landside to y 100; its ground stands a storey up."""
    floor = _part(100.0, -20.0, 140.0, -2.0, 0.0, feet=True)
    upper = [_part(20.0, 0.0, 60.0, 60.0, 4.1), _part(200.0, 0.0, 250.0, 60.0, 4.1),
             _part(60.0, 0.0, 200.0, 40.0, 4.1)]
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=[floor, *upper])])
    ap = types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                               frame=types.SimpleNamespace(entry=lambda: XY),
                               dem=types.SimpleNamespace(z=lambda x, y: 46.0 + 4.6 * (y > 0)))
    final = [["apron", "apron0", box(-50.0, -100.0, 320.0, 0.0), None, {}, "apron"],
             ["parking_lot", "lot0", box(0.0, 0.0, 270.0, 100.0), None, {}, "parking_lot"]]
    return ap, final


def test_the_kerb_drive_in_the_plan_stays_the_landsides():
    ap, final = _landside()
    band = storey_band(ap, LAW, [], final)
    cuts: dict = {}
    airside_edge_flip(final, [], LAW, load_rules(), storey=band, storey_cuts=cuts, to_xy=XY)
    assert final[1][0] == "parking_lot"
    assert knife_storeys(final, cuts, LAW, 1.0, band) == 1
    under = sum(f[2].area for f in final[2:] if f[0] == "apron")
    drive = box(60.0, 40.0, 200.0, 60.0)
    hull = box(20.0, 0.0, 250.0, 60.0)
    # the building's airside floor is the hull less the landside bay
    assert under == pytest.approx(hull.area - drive.area, rel=1e-3)
    lot = final[1]
    assert lot[2].intersection(drive).area > 0.5 * drive.area
    plan = Polygon(lot[4][STOREY_PLAN_KEY][0])
    assert plan.area == pytest.approx(hull.area - drive.area, rel=1e-3)
    assert lot[4][STOREY_UNIT_KEY] == (0,)
    cell = types.SimpleNamespace(ref="lot0", evidence=lot[4])
    got = landside_plans([cell])
    assert got["lot0"][1] == 4.1 and got["lot0"][0].area == pytest.approx(plan.area)


def _map():
    """Kerb vertex 1 (lot, 0.8 m off the plan), wall vertex 2 (apron on the
    plan edge), datum 3 inside the plan, a far lot vertex 4."""
    xy = {1: (0.0, 0.8), 2: (0.0, 0.0), 3: (0.0, -10.0), 4: (0.0, 30.0)}
    face = types.SimpleNamespace
    faces = {0: face(id=0, ref="lot0", role="parking_lot", ring=(1, 4), holes=()),
             1: face(id=1, ref="apron0", role="apron", ring=(2,), holes=())}
    plan = box(-50.0, -20.0, 50.0, 0.0)
    held = {"b": {LANDSIDE_KERB: ({"lot": "lot0", "y": 4.1, "plan": plan, "air_z": 46.0},)}}
    return types.SimpleNamespace(
        faces=faces, ring_vertices=lambda ring: ring,
        vertices={v: types.SimpleNamespace(xy=p, dem_z=44.0 if v == 4 else 49.0)
                  for v, p in xy.items()},
        registries=types.SimpleNamespace(held=held, landings={}))


def test_the_kerb_takes_the_block_datum_plus_the_rise_one_way(monkeypatch):
    import auto_patch_v2.model.platform as mp
    monkeypatch.setattr(mp, "stage_air_vertices", lambda pm, law: {2})
    monkeypatch.setattr(mp, "datum_vertices", lambda pm, law, fills=False: {"b": 3})
    pm = _map()
    kerb, wall = kf.kerb_vertices(pm, LAW)
    assert set(kerb) == {1} and wall == {2, 3}
    rows = kf.kerb_frontage_rows(pm, LAW)
    assert len(rows) == 2 and all(r.follows == (1,) for r in rows)
    up, down = rows
    assert dict(up.terms) == {1: 1.0, 3: -1.0} and up.hi == 4.1
    assert dict(down.terms) == {1: -1.0, 3: 1.0} and down.hi == -4.1
    src = Source("groundside_ramps", "r")
    across, along = Diff(1, 2, 0.05, 0.8, src), Diff(1, 4, 0.05, 29.2, src)
    kept, n = kf.kerb_wall_exempt([across, along, *rows], pm, LAW)
    assert n == 1 and kept == [along, *rows]


def test_a_road_ramp_row_on_the_kerb_gives_way(monkeypatch):
    import auto_patch_v2.model.platform as mp
    from auto_patch_v2.model.constraints import Band
    monkeypatch.setattr(mp, "stage_air_vertices", lambda pm, law: {2})
    pm = _map()
    ceiling = Band(1, None, 50.0, Source("road_ramp", "roads.groundside_road ramp ceiling"))
    far = Band(4, None, 50.0, Source("road_ramp", "roads.groundside_road ramp ceiling"))
    kept, n = kf.kerb_wall_exempt([ceiling, far], pm, LAW)
    assert n == 1 and kept == [far]


def test_no_kerb_where_the_ground_has_come_down_to_the_floor(monkeypatch):
    import auto_patch_v2.model.platform as mp
    monkeypatch.setattr(mp, "stage_air_vertices", lambda pm, law: {2})
    pm = _map()
    pm.vertices[1].dem_z = 47.0          # under air_z + half the rise
    kerb, _wall = kf.kerb_vertices(pm, LAW)
    assert not kerb


def test_the_census_road_cap_allows_a_declared_wall():
    """K3: a pavement pair across a declared wall joint is allowed the
    wall's step by ``pavement_over_road_cap`` (RULINGS 2026-10-19l)."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
    import check_grade as cg

    def ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)
    nodes = {"a": (30.12, 31.40), "b": (30.12 + 0.6 / 111_320.0, 31.40),
             "c": (30.12 + 0.6 / 111_320.0, 31.40 + 5.0 / 96_000.0),
             "d": (30.12, 31.40 + 5.0 / 96_000.0)}
    lot = cg.Way(wid="lot", role="parking_lot", ref="lot0", aeroway="",
                 nids=["b", "c"], elevs=[51.2, 51.2], tags={"role": "parking_lot"})
    floor = cg.Way(wid="apron", role="apron", ref="apron0", aeroway="",
                   nids=["a", "d"], elevs=[47.1, 47.1], tags={"role": "apron"})
    bare = cg._check_pavement_over_road_cap([lot, floor], nodes, ll_to_m)
    joint = [([(-10.0, 0.3), (10.0, 0.3)], 4.11)]
    walled = cg._check_pavement_over_road_cap([lot, floor], nodes, ll_to_m,
                                              terrace_joints_m=joint)
    assert len(bare) == 2 and walled == []
