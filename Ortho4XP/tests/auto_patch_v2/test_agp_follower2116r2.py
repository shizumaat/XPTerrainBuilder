"""#2116 R2 (spec ``docs/specs/2116-R2.md``): a footprint over an AGP
follower mints no pad (G1), an open strip between two ground-floor parts of
one follower is a plate (C1b), a stack's bank beside its own run-on road
follows the road (E), a solid the carried route crosses holds no end (H).
Synthetic, headless."""
from __future__ import annotations

import types

import numpy as np
import shapely
from auto_patch_v2.airport import agp_gap_plates as GP
from auto_patch_v2.airport import agp_plan as AP
from auto_patch_v2.law import Law
from auto_patch_v2.model.agp_group import AgpPlate
from shapely.geometry import box

LAW = Law.for_airport("")
AGP = LAW.tables.structures.agp


def _tris(x0, y0, x1, y1):
    """Two triangles covering a box, ``(2, 3, 2)``."""
    return np.array([[(x0, y0), (x1, y0), (x1, y1)], [(x0, y0), (x1, y1), (x0, y1)]], float)


def _plan(*boxes):
    tris = np.concatenate([_tris(*b) for b in boxes])
    lo, hi = tris.reshape(-1, 2).min(axis=0), tris.reshape(-1, 2).max(axis=0)
    return AP._FollowerPlan("agp:g", "dsf:obj1", tris, shapely.STRtree(shapely.polygons(tris)),
                           (*lo.tolist(), *hi.tolist()))


def test_a_footprint_over_a_follower_is_covered_and_one_beside_it_is_not():
    plan = _plan((0, 0, 100, 60))
    got = AP.follower_cover([plan], box(10, 10, 90, 50))
    assert got is not None and got[1] > 0.99
    half = AP.follower_cover([plan], box(80, 10, 120, 50))    # half over the plan
    assert half is not None and 0.4 < half[1] < 0.6
    assert AP.follower_cover([plan], box(200, 0, 240, 40)) is None
    assert AGP.pad_cover_min == 0.5


def _plate(k, ring, y=0.15, built=True):
    p = shapely.Polygon(ring)
    return AgpPlate("agp:g", "dsf:obj1", k, tuple(p.exterior.coords[:-1]), (), y,
                    1629.5 + y, round(p.area, 1), 2.0, built)


def _feet_box(x0, y0, x1, y1, y=0.0):
    """A wall foot ring sampled every metre as ``(k, 1, 3)`` at height ``y``."""
    ring = shapely.Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]).exterior
    pts = [ring.interpolate(d) for d in np.arange(0.0, ring.length, 1.0)]
    return np.array([[(p.x, p.y, y)] for p in pts], float)


NO_FEET = np.zeros((0, 1, 3))
NO_FLOORS = lambda: np.zeros((0, 3, 2))          # noqa: E731


def test_an_open_strip_between_two_parts_is_a_plate_at_the_lower_side():
    a = _plate(0, [(0, 0), (40, 0), (40, 40), (0, 40)], y=0.15)
    b = _plate(1, [(65, 0), (100, 0), (100, 40), (65, 40)], y=0.10)   # a 25 m strip
    got = GP.with_gap_plates([a, b], NO_FEET, NO_FLOORS, 1629.5, AGP, 0.05, None, [])
    gap = [p for p in got if "agp_gap_plate" in p.why]
    assert len(got) == 3 and len(gap) == 1 and gap[0].built and gap[0].k == 2
    assert abs(gap[0].y - 0.10) < 1e-9 and abs(gap[0].level - (1629.5 + 0.10 - 0.05)) < 1e-9
    assert abs(gap[0].area_m2 - 25 * 40) < 1.0
    # the other side a part with no floor: its FEET at the datum (a hall
    # wall); the side a plate stands on reads its own lowest solid, its feet
    feet = np.concatenate([_feet_box(0, 0, 40, 40, y=0.02), _feet_box(65, -5, 120, 45, y=0.0)])
    got = GP.with_gap_plates([a], feet, NO_FLOORS, 1629.5, AGP, 0.05, None, [])
    gap = [p for p in got if "agp_gap_plate" in p.why]
    assert len(gap) == 1 and abs(gap[0].y - 0.0) < 1e-9


def test_sides_at_two_levels_or_a_covered_strip_are_listed_never_built():
    a = _plate(0, [(0, 0), (40, 0), (40, 40), (0, 40)], y=0.15)
    b = _plate(1, [(65, 0), (100, 0), (100, 40), (65, 40)], y=0.45)
    notes: list[str] = []
    got = GP.with_gap_plates([a, b], NO_FEET, NO_FLOORS, 1629.5, AGP, 0.05, None, notes)
    assert len(got) == 2 and any("agp_gap_listed" in n for n in notes)
    b = _plate(1, [(65, 0), (100, 0), (100, 40), (65, 40)], y=0.15)
    roof = _tris(38, -2, 67, 42)                                 # a building over the strip
    notes = []
    got = GP.with_gap_plates([a, b], NO_FEET, lambda: roof, 1629.5, AGP, 0.05, None, notes)
    assert len(got) == 2 and any("agp_gap_covered" in n for n in notes)
    # wider than plate_gap_max_m: no strip at all
    far = _plate(1, [(80, 0), (120, 0), (120, 40), (80, 40)], y=0.15)
    assert len(GP.with_gap_plates([a, far], NO_FEET, NO_FLOORS, 1629.5, AGP, 0.05,
                                  None, [])) == 2


def test_a_stack_bank_beside_its_own_run_on_road_follows_the_road():
    """#2116 R2 E: a stack-ground vertex within the stand-off reach of the
    ribbon its own graded end's path runs on is bound to the ribbon's edge
    at ``bank_slope x distance``; one off the path's ribbon is not."""
    from auto_patch_v2.constraints import fill_bank as FB
    from auto_patch_v2.model.constraints import Linear
    from auto_patch_v2.model.planar import STACK_GROUND_PREFIX
    V = {1: (0.0, 0.0), 2: (50.0, 0.0), 3: (50.0, 6.0), 4: (0.0, 6.0),       # the road
         5: (0.0, 7.5), 6: (50.0, 7.5), 7: (50.0, 30.0), 8: (0.0, 30.0),     # the bank
         9: (0.0, 60.0), 10: (50.0, 60.0), 11: (50.0, 66.0), 12: (0.0, 66.0)}  # another road
    faces = {1: types.SimpleNamespace(role="service_road", ref="small_roads:-1", ring=(1, 2, 3, 4)),
             2: types.SimpleNamespace(role=None, ring=(5, 6, 7, 8),
                                      ref=STACK_GROUND_PREFIX + "stack:S:bank#0"),
             3: types.SimpleNamespace(role="service_road", ref="small_roads:-2",
                                      ring=(9, 10, 11, 12))}
    inc = {v: [f for f, q in faces.items() if v in q.ring] for v in V}
    planar = types.SimpleNamespace(
        faces=faces, edges={}, bridge_stacks=None, ring_vertices=lambda r: tuple(r),
        vertices={v: types.SimpleNamespace(xy=xy, incident_faces=inc[v], dem_z=0.0)
                  for v, xy in V.items()})
    end = types.SimpleNamespace(path=((25.0, -20.0), (25.0, 3.0), (25.0, 40.0)), run=40.0,
                                access=())
    st = types.SimpleNamespace(id="stack:S", graded_ends=lambda: (end,))
    air = types.SimpleNamespace(deck_stacks=(st,))
    rows = [r for r in FB._bank_road_rows(planar, LAW, air, set()) if isinstance(r, Linear)]
    got = {r.terms[0][0]: r for r in rows}
    assert set(got) == {5, 6}                      # the bank's road-side edge only
    slope = float(LAW.tables.emit.design.bank_slope)
    assert abs(got[5].hi - slope * 1.5) < 1e-9 and got[5].follows == 5
    assert {v for v, _c in got[5].terms[1:]} <= {1, 2, 3, 4}
