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


# --- round 3: the wall the pack built from sheets (#1952 R1/R2) -------------

class _FlatDem:
    """The lidar predates the wall: 300 m on both sides, no step."""

    def z_many(self, xs, ys):
        return np.full(len(np.asarray(xs)), 300.0)


def _ring(g):
    """A frame-xy box as the partition's ``(lat, lon)`` ring (the frame
    below maps ``(lon, lat)`` straight to ``(x, y)``)."""
    return [(y, x) for x, y in list(g.exterior.coords)[:-1]]


def _part(g, base_y, height, comp=0, line=False):
    return types.SimpleNamespace(rings=[_ring(g)], line=line, height_m=height,
                                 base_y=base_y, comp=comp, feet=(1,))


def _member(mid, resource, *parts):
    return types.SimpleNamespace(id=mid, resource=resource, parts=list(parts),
                                 origin=(0.0, 0.0), zero_y=0.0)


#: KMCI's border wall in miniature: a deep skirt (one part, y -13.98 ..
#: -2.74), a second skirt beside it (``stoneblock``), and the face sheet
#: whose bottom edge (y -4.74) is the low side's ground as authored
SKIRT = box(0.0, 0.0, 200.0, 1.15)


def _sheet_airport(skirt_parts=1, paved=True, stone=True):
    from auto_patch_v2.model.airport import Pavement, Surface
    skirt = [_part(SKIRT, -13.98, 11.24)]
    # a building's facade: its second part a storey standing on its zero
    skirt += [_part(box(0.0, 0.2, 200.0, 0.4), 0.0, 3.0, comp=1)][:skirt_parts - 1]
    stoneblock = _member("dsf:obj2", "Border/stoneblock.obj",
                         _part(box(0.0, 0.9, 200.0, 1.1), -14.06, 11.07))
    unit = types.SimpleNamespace(id="unit:1", agl_m=0.0, anchor=(0.0, 0.0), members=[
        _member("dsf:obj1", "Border/Trimsheet-16.obj", *skirt),
        *([stoneblock] if stone else []),
        _member("dsf:obj3", "Border/Trimsheet-17.obj",
                _part(box(0.0, 1.0, 200.0, 1.2), -4.74, 3.37, line=True))])
    apron = Pavement("pav3", Surface.CONCRETE,
                     tuple(box(0.0, -60.0, 200.0, 0.0).exterior.coords)[:-1], ())
    return types.SimpleNamespace(
        partition=types.SimpleNamespace(units=[unit]),
        frame=types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat))),
        dem=_FlatDem(), pavements=(apron,) if paved else ())


def _sheet_walls(monkeypatch, **kw):
    from auto_patch_v2.classify.rules import load_rules
    monkeypatch.setattr(wall_class, "obj_top_y", lambda *_a, **_k: -0.93)
    return wall_class.wall_class_components(_sheet_airport(**kw), load_rules().service)


def test_a_composite_wall_retains_its_top_over_its_face_sheets_bottom(monkeypatch):
    got = [c for c in _sheet_walls(monkeypatch) if c.retains]
    assert len(got) == 1, got                       # ONE wall: the skirt carries it
    (w,) = got
    assert w.resource == "Border/Trimsheet-16.obj" and w.low_side_source == "sheets"
    assert math.isclose(w.retained_m, 3.81, abs_tol=1e-6)
    assert w.top_y == -0.93 and len(w.sheets) == 3
    # the side witness: the apron (y < 0) is beside the upper face
    from auto_patch_v2.airport.wall_sides import _wall_faces
    up = _wall_faces(SKIRT)[w.paved_face[0]]
    assert max(y for _x, y in up.coords) < 0.5
    # the second skirt is a sheet of the composite, never a wall of its own
    assert not [c for c in _sheet_walls(monkeypatch) if "stoneblock" in c.resource]


def test_a_multi_part_facade_is_not_a_sheet_wall(monkeypatch):
    assert not [c for c in _sheet_walls(monkeypatch, skirt_parts=2, stone=False)
                if c.retains]


def test_a_wall_with_no_airside_beside_it_is_not_a_sheet_wall(monkeypatch):
    assert not [c for c in _sheet_walls(monkeypatch, paved=False) if c.retains]


def test_the_low_side_is_the_median_face_bottom_never_the_footing():
    from auto_patch_v2.airport.wall_sheets import SheetPart, low_side_y
    s = [SheetPart(("a", 0), None, -13.98, 825.0), SheetPart(("b", 0), None, -14.06, 828.0),
         SheetPart(("c", 0), None, -4.74, 777.0), SheetPart(("d", 0), None, -6.88, 120.0),
         SheetPart(("e", 1), None, -13.2, 50.0)]   # within the footing's metre
    assert low_side_y(s) == -4.74
    assert low_side_y(s[:2]) is None                # only footing: no low side read
