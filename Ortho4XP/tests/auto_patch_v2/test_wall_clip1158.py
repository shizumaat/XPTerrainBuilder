"""Twin of ``classify/wall_clip`` (#1158, owner RULINGS 2026-10-20ak / 20ax /
20ba): pavement never crosses a pack retaining wall.  A wall 100 m long and
2 m thick along y = 0..2, the ground 300 m north of it and 290 m south (a
10 m wall, KATL ``muro_concreto``'s class)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

from auto_patch_v2.airport.wall_class import WallComponent, retaining_sides
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.classify.wall_clip import clip_at_walls, cutting_walls

CFG = load_rules().service


class _StepDem:
    def z_many(self, xs, ys):
        return np.where(np.asarray(ys, dtype=float) > 1.0, 300.0, 290.0)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


AP = NS(dem=_StepDem())
WALL = WallComponent((box(0.0, 0.0, 100.0, 2.0),), 10.0, "objects/muro.obj", 0, True)


def _walls():
    return cutting_walls(AP, [WALL], CFG)


def test_the_sides_are_read_off_the_step():
    up, lo, ring = retaining_sides(AP, WALL, CFG, CFG.retaining_wall_clear_step_m)
    assert ring == 10.0
    assert up.centroid.y > 2.0 and lo.centroid.y < 0.0
    assert up.area > 800.0 and lo.area > 800.0


def test_an_overhang_past_the_lower_face_leaves_the_pavement():
    """20ak: the taxiway along the top overhangs the wall 3 m onto the low
    side — the footprint and the 3 m past it leave; the taxiway stops at the
    wall's upper face."""
    taxi = unary_union([box(-20.0, 2.0, 120.0, 40.0), box(5.0, -3.0, 95.0, 2.0)])
    out, st = clip_at_walls([("pav14", taxi)], _walls())
    assert [sid for sid, _g in out] == ["pav14"]
    g = out[0][1]
    assert g.intersection(box(5.0, -3.0, 95.0, 2.0)).area < 1e-6
    assert abs(g.area - (taxi.area - 90.0 * 5.0)) < 1.0
    assert abs(st["wall_clip_overhang_m2"] - 270.0) < 1.0 and st["wall_clip_two_level"] == 0


def test_pavement_on_both_levels_is_cut_by_the_footprint_only():
    """20ax: pavement that runs on past both side bands stands on two
    levels; the wall's footprint leaves it and both sides stay."""
    apron = box(10.0, -40.0, 90.0, 40.0)
    out, st = clip_at_walls([("pav1", apron)], _walls())
    assert st["wall_clip_two_level"] == 1
    assert sorted(sid for sid, _g in out) == ["pav1", "pav1#wall1"]
    assert abs(sum(g.area for _s, g in out) - (apron.area - 80.0 * 2.0)) < 1e-6


def test_pavement_clear_of_the_wall_is_untouched():
    lower = box(0.0, -30.0, 100.0, -0.5)      # an apron at the wall's foot
    out, st = clip_at_walls([("pav2", lower)], _walls())
    assert out == [("pav2", lower)] and st["wall_clip_polygons"] == 0


def test_a_wall_at_most_the_clear_step_cuts_nothing():
    low = WallComponent(WALL.pieces, 2.0, WALL.resource, 0, True)
    assert cutting_walls(AP, [low], CFG) == []
    assert cutting_walls(AP, [WallComponent(WALL.pieces, 10.0, WALL.resource, 0, False)], CFG) == []
