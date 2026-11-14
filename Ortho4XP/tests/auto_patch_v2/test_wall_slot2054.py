"""#2054 round 2 twins (spec ``docs/specs/2054-round2-wall-slot-spec.md``
§6; owner RULINGS 2026-11-13t/u): the road at a retaining wall's foot
taking the ground to it (R2), and no road under a runway-end walled
plate's body (R3).  R1's step slot is replaced by 13t (not built here).

A synthetic wall along x = 60 (y -100..100), 20 m retained: the upper
level west of it, the lower level east (``airport/wall_sides``)."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import wall_sides as WS
from auto_patch_v2.airport.walled_plate import body_plan
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.edge_line_mint import grow_feet_to_walls
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.wall_cutback import cut_roads_at_walls
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import road_family_roles, snap_margin_m
from shapely.geometry import Point, Polygon, box


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _StepDem:
    """Upper ground 300 m west of the wall, lower 280 m east, smeared."""

    def z_many(self, xs, ys):
        t = np.clip((np.asarray(xs, float) - 50.0) / 25.0, 0.0, 1.0)
        return 300.0 - 20.0 * t

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _sides(thick: float):
    wall = box(60.0, -100.0, 60.0 + thick, 100.0)
    comp = types.SimpleNamespace(retains=True, retained_m=20.0, height_m=20.0,
                                 pieces=(wall,), top_y=6.8, resource="w")
    ap = types.SimpleNamespace(dem=_StepDem(), partition=object())
    cfg = types.SimpleNamespace(retaining_wall_clear_step_m=2.0)
    (w,) = WS.wall_sides(ap, cfg, [comp])
    return wall, w


def _cell(i, role, ring, side="groundside", ref=None):
    return Cell(i, role, ref or f"{role}{i}", tuple(ring.exterior.coords)[:-1], (),
                None, None, side, role, {})


def test_the_road_at_the_foot_takes_the_ground_to_the_wall(law):
    """0.5 m wall, the apron on its upper face, a road 3 m off its low
    face: the road grows to the wall (the snap margin short of it); the
    step is made across the footprint."""
    _wall, w = _sides(0.5)
    apron = _cell(0, "apron", box(20.0, -100.0, 60.0, 100.0), side="airside")
    road = _cell(1, "service_road", box(63.5, -50.0, 71.0, 50.0))
    cells = [apron, road]
    st = grow_feet_to_walls(types.SimpleNamespace(retaining_walls=(w,)), cells, law,
                            load_rules())
    assert st["wall_foot_hosts_grown"] == 1
    g = Polygon(cells[1].ring, cells[1].holes)
    assert cells[1].ref == road.ref and cells[1].role == "service_road"
    assert g.bounds[0] <= 60.5 + snap_margin_m(law) + 0.05
    assert g.distance(w.poly) >= snap_margin_m(law) - 0.05      # never in the footprint
    assert Polygon(cells[0].ring).equals(Polygon(apron.ring))   # airside as it was
    assert cells[1].evidence["wall_foot"] == "w"


def test_an_airside_host_or_one_on_the_upper_side_never_grows(law):
    _wall, w = _sides(0.5)
    rules = load_rules()
    cells = [_cell(0, "apron", box(63.5, -50.0, 71.0, 50.0), side="airside")]
    st = grow_feet_to_walls(types.SimpleNamespace(retaining_walls=(w,)), cells, law, rules)
    assert st["wall_foot_hosts_grown"] == 0
    cells = [_cell(0, "service_road", box(50.0, -50.0, 56.0, 50.0))]   # the upper side
    st = grow_feet_to_walls(types.SimpleNamespace(retaining_walls=(w,)), cells, law, rules)
    assert st["wall_foot_hosts_grown"] == 0


def _plate_airport():
    """A walled plate whose body (all parts) spans x 0..40, y 0..30 -- the
    plate itself and its slopes; a frame whose entry is ``(lon, lat)``."""
    parts = (types.SimpleNamespace(rings=(((0.0, 0.0), (20.0, 0.0), (20.0, 40.0),
                                           (0.0, 40.0)),)),
             types.SimpleNamespace(rings=(((20.0, 0.0), (30.0, 0.0), (30.0, 40.0),
                                           (20.0, 40.0)),)))
    member = types.SimpleNamespace(id="dsf:obj1", parts=parts)
    other = types.SimpleNamespace(id="dsf:obj2", parts=(types.SimpleNamespace(
        rings=(((100.0, 100.0), (100.0, 110.0), (110.0, 110.0)),)),))
    part = types.SimpleNamespace(units=(types.SimpleNamespace(members=(member, other)),))
    frame = types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat)))
    return types.SimpleNamespace(walled_plates=(types.SimpleNamespace(ids=("dsf:obj1",)),),
                                 partition=part, frame=frame)


def test_a_road_crossing_a_walled_plate_body_is_cut_at_its_plan(law):
    ap = _plate_airport()
    plan = body_plan(ap)
    assert plan.area == pytest.approx(40.0 * 30.0)
    assert body_plan(ap) is plan                                  # memoised
    road = _cell(0, "service_road", box(-20.0, 10.0, 60.0, 18.0))
    runway = _cell(1, "runway", box(-20.0, 20.0, 60.0, 25.0), side="airside")
    margin = snap_margin_m(law)
    out, st = cut_roads_at_walls([road, runway], frozenset(road_family_roles(law)), (),
                                 1.0, margin, plan)
    assert st["plate_cut_cells"] == 1 and st["wall_cut_cells"] == 0
    roads = [c for c in out if c.role == "service_road"]
    assert len(roads) == 2                                        # the two remainders
    grown = plan.buffer(margin * 0.99)
    assert not any(grown.contains(Point(p)) for c in roads for p in c.ring)
    (rw,) = [c for c in out if c.role == "runway"]
    assert Polygon(rw.ring).equals(Polygon(runway.ring))          # only roads lose it


def test_no_body_no_change(law):
    road = _cell(0, "service_road", box(-20.0, 10.0, 60.0, 18.0))
    out, st = cut_roads_at_walls([road], frozenset(road_family_roles(law)), (), 1.0,
                                 snap_margin_m(law), None)
    assert st == {"wall_cut_cells": 0, "wall_cut_m2": 0.0} and out[0] == road
    assert body_plan(types.SimpleNamespace(walled_plates=(), partition=None,
                                           frame=None)) is None
