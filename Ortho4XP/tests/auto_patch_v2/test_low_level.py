"""THE LOWER LEVEL OF A STEPPED UNIT'S PAD (owner RULINGS 2026-10-19ai, #809;
``planar/low_level``): a held pad whose pack unit carries parts a storey
under its frontage level is split into its high block, a lower level
``<ref>/p1`` over those parts and the riser strip between."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import box

from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import plane_origin_ref, plane_of
from auto_patch_v2.planar.low_level import plan_low


def _part(x0, y0, x1, y1, base_y):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=(), line=False)


def _airport(parts):
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    return types.SimpleNamespace(
        partition=types.SimpleNamespace(units=[unit]),
        frame=types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat))))


@pytest.fixture(scope="module")
def law():
    return Law.load(ruleset="faa")


P = box(0.0, 0.0, 200.0, 100.0)          # the held pad; the apron north of it
AIR = box(0.0, 100.0, 200.0, 130.0)
FRONT = [_part(10.0 + 40.0 * i, 92.0, 40.0 + 40.0 * i, 100.0, 0.0) for i in range(4)]


def test_a_storey_down_is_a_lower_level_tied_by_its_band(law):
    low = [_part(0.0, 0.0, 100.0, 80.0, -13.0), _part(100.0, 0.0, 200.0, 80.0, -12.9)]
    got = plan_low(P, AIR, _airport(FRONT + low), law, 0.5)
    assert got is not None
    H, L, S, rec = got
    assert L.area == pytest.approx(200.0 * 80.0, rel=0.02)
    assert H.area > 0.0 and S.area > 0.0
    assert L.intersection(H).area == pytest.approx(0.0, abs=1e-6)
    assert L.distance(AIR) >= 3.0 - 1e-6                     # the frontage stays high
    assert rec["top_y"] == 0 and rec["y_lo"] == pytest.approx(-13.0)
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    assert rec["y_hi"] == pytest.approx(-step)


def test_no_storey_no_split(law):
    sill = [_part(0.0, 0.0, 100.0, 80.0, -1.0)]               # under one storey
    assert plan_low(P, AIR, _airport(FRONT + sill), law, 0.5) is None
    small = [_part(0.0, 0.0, 30.0, 30.0, -13.0)]              # under the unit-pad bar
    assert plan_low(P, AIR, _airport(FRONT + small), law, 0.5) is None


def test_the_object_stage_folds_the_lower_level_into_its_block():
    assert plane_of("building31/b0/p1") == ("building31/b0", 1)
    assert plane_origin_ref("building31/b0/p1") == "building31/b0"
    assert plane_origin_ref("building31/b0/p1#strip") == "building31/b0"
    assert plane_origin_ref("building31/b0") == "building31/b0"
    assert plane_origin_ref("unit/p1/b2") == "unit/p1/b2"     # a block inside a plane pad


def test_the_bending_skips_the_riser():
    """The riser between a block and its lower level is a declared step:
    ``solve/wall_cut`` cuts every triangle edge from a lower-level vertex
    to a strip vertex off that level, and nothing else."""
    from auto_patch_v2.solve.wall_cut import wall_cut_edges
    F = types.SimpleNamespace
    faces = {0: F(ref="b/b0", ring=(0, 1), holes=()),
             1: F(ref="b/b0/p1#strip", ring=(1, 2, 3, 4), holes=()),
             2: F(ref="b/b0/p1", ring=(3, 4, 5), holes=())}
    planar = F(faces=faces, ring_vertices=lambda r: tuple(r), road_terrace={})
    tris = [(1, 2, 3), (2, 3, 4), (3, 4, 5), (0, 1, 2)]
    assert wall_cut_edges(planar, tris) == frozenset({(1, 3), (2, 3), (2, 4)})
