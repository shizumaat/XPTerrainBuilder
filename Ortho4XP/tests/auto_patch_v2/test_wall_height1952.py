"""#1952 twins: a retaining wall's height is what it retains above the
ground on its low side, not its full modelled solid height (owner RULINGS
2026-11-09a (14)).

The wall: a footprint 1 m thick along y = 0..1 (x 0..200), its top 0.2 m
under its zero, its solid 11 m tall (KMCI's border wall is modelled down
to a footing 12-14 m under its top).  The ground steps 6 m across it: the
upper side (y < 0) at 296, the lower (y > 1) at 290.
"""
from __future__ import annotations

import math
import types

import numpy as np
from auto_patch_v2.airport import road_ramp, wall_class, wall_top
from shapely.geometry import box

WHOLE = box(0.0, 0.0, 200.0, 1.0)
CFG = types.SimpleNamespace(retaining_wall_thick_width_per_height=0.5,
                            retaining_wall_step_min_fraction=0.75,
                            retaining_wall_step_max_fraction=1.25,
                            retaining_wall_step_ring_m=3.0,
                            retaining_wall_clear_step_m=2.0)


class _StepDem:
    """296 m on the upper side (y < 0.5), 290 m on the lower."""

    def z_many(self, xs, ys):
        return np.where(np.asarray(ys, float) < 0.5, 296.0, 290.0)


AP = types.SimpleNamespace(dem=_StepDem())


def test_the_height_over_the_low_side_is_the_top_less_the_low_ground():
    # top as it sits 296.0 (the upper ground): it retains 6 m over 290
    kept = wall_class._kept_above_low_side(AP.dem, WHOLE, 1.0, 11.0, 296.0, 11.0)
    assert math.isclose(kept, 6.0)
    # a top under the low ground retains nothing; a face no taller than
    # what it stands over has no footing, and is read as its solid height
    assert wall_class._kept_above_low_side(AP.dem, WHOLE, 1.0, 11.0, 289.0, 11.0) is None
    assert wall_class._kept_above_low_side(AP.dem, WHOLE, 1.0, 5.0, 296.0, 5.0) is None


def test_a_wall_with_a_buried_footing_retains_its_height_over_the_low_side():
    # the solid 11 m and its depth under its zero (11.2 m) match no 6 m step
    assert not wall_class._retains_its_height(AP, WHOLE, 1.0, 11.0, CFG, 11.2)
    # the height over the low side does
    got = wall_class._retains_its_height(AP, WHOLE, 1.0, 11.0, CFG, 11.2, 296.0)
    assert math.isclose(got, 6.0)


def test_only_a_wall_hung_from_its_zero_reads_its_height_over_the_low_side():
    # KMCI's border wall (top 0.9 m under its zero) and KATL muro_concreto2A
    assert wall_class._hangs_from_zero(-0.9, 304.56, CFG)
    # a facade standing 15.4 m over its zero (LEMD OldTerminal T2SL4), a
    # parapet 6.1 m over it (KATL muro_ladrillo), or an unseated object
    assert not wall_class._hangs_from_zero(15.41, 596.0, CFG)
    assert not wall_class._hangs_from_zero(6.12, 300.0, CFG)
    assert not wall_class._hangs_from_zero(-0.9, None, CFG)


def test_the_step_a_retaining_wall_is_reads_the_height_it_retains(monkeypatch):
    comp = wall_class.WallComponent((WHOLE,), 11.0, "border.obj", 0, True, 6.0, -0.2)
    free = wall_class.WallComponent((box(0.0, 10.0, 200.0, 10.5),), 3.0, "kerb.obj", 1)
    monkeypatch.setattr(wall_class, "wall_class_components", lambda *_a: [comp, free])
    ap = types.SimpleNamespace(partition=object(), retaining_walls=())
    got = {p.label: p.height_m for p in road_ramp.wall_pieces(ap, CFG)}
    assert got == {"border.obj#comp0": 6.0, "kerb.obj#comp1": 3.0}


def test_the_top_is_capped_only_where_the_retained_face_stops_under_it():
    proud = types.SimpleNamespace(top_y=6.0, retained_top_y=0.0)
    assert wall_top._retaining_cap(proud) == 0.0
    # a footing under the low side's ground leaves the top the top
    footed = types.SimpleNamespace(top_y=-0.2, retained_top_y=None)
    assert wall_top._retaining_cap(footed) == math.inf
