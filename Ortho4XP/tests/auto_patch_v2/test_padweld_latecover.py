"""LEMD building49 (lane lpadweld, 2026-11-27): the BASE map of the last
stage (``pipeline/stage_one_map.gap_free``) leaves out the pad roads, gap
pieces and car lots, but their ground is patch.  A way running from a patch
ribbon on into a pad road never LEAVES the coverage, so §37 (9) mints no
coverage-edge join there (``emit/road_join._late_coverage``).  MEASURED:
way ``-1094`` pinned at the core's 605.00 m where it meets the pad road
``-1092``, welded 10 m on to ``building49`` at 607.92 m — a 1.15 m step."""
from __future__ import annotations

import types

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.emit.road_join import _late_coverage, road_coverage_joins
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.stage_one_map import gap_free


def _map():
    """One 20 x 10 m road face, x in [0, 20]; its end section at x = 18."""
    xy = {1: (0.0, 0.0), 2: (20.0, 0.0), 3: (20.0, 10.0), 4: (0.0, 10.0),
          5: (18.0, 2.0), 6: (18.0, 8.0)}
    verts = {k: types.SimpleNamespace(xy=v, dem_z=100.0) for k, v in xy.items()}
    face = types.SimpleNamespace(ring=(1, 2, 3, 4), holes=())
    return types.SimpleNamespace(vertices=verts, faces={1: face},
                                 ring_vertices=lambda cyc: list(cyc))


def _profiles():
    way = types.SimpleNamespace(xy=[(2.0, 5.0), (18.0, 5.0), (40.0, 5.0)],
                                z=[100.0, 100.0, 102.0], s=[0.0, 16.0, 38.0])
    return types.SimpleNamespace(all_ways=[way])


FRAME = {5: (0, 16.0, 0.0), 6: (0, 16.0, 0.0)}
LAW = Law.for_airport("ZZZZ")


def test_a_way_leaving_into_open_ground_is_joined():
    joins, rep = road_coverage_joins(_map(), LAW, _profiles(), FRAME)
    assert rep["exits"] == 1 and set(joins) == {5, 6}


def test_a_way_running_on_into_a_last_stage_cell_is_not():
    pm = _map()
    late = (((20.0, 0.0), (60.0, 0.0), (60.0, 10.0), (20.0, 10.0)), ())
    joins, rep = road_coverage_joins(pm, LAW, _profiles(), FRAME,
                                     _late_coverage(pm, (late,)))
    assert rep["exits"] == 0 and joins == {}


def _cell(i, role, ref, ring, ev):
    return Cell(id=i, role=role, ref=ref, ring=ring, holes=(), code_number=None,
                code_letter=None, side="groundside", kind=role, evidence=ev)


def test_gap_free_keeps_the_late_cells_ground():
    ring = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
    keep = _cell(1, "building", "building1", ring, {})
    road = _cell(2, "service_road", "small_roads:-1", ring, {"pad_road": 1.0})
    base = gap_free(Classification(cells=(keep, road), cut_lines=(), stats={}, notes=()))
    assert base.cells == (keep,)
    assert base.late_cover == ((ring, ()),)
