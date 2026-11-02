"""#1754 / #1727 (owner RULINGS 2026-11-02a (3), Q310): every ring vertex of
a service-road ribbon takes the road's own profile, at-grade safety-area
roads included.  Only in the END AREA of a runway end a walled plate caps
(28p (1), #1201) does the road take the safety area's level instead.
Synthetic: one runway along +y, its north end at (0, 0); a plate 290-310 m
past it; two service ribbons on the safety area, one in that end area and
one 1 km down the runway's side."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.plate_ground import plated_end_areas
from auto_patch_v2.airport.road_profile import at_grade_rsa_vertices
from auto_patch_v2.law import Law
from auto_patch_v2.model.walled_plate import WalledPlate
from shapely.geometry import Point


@pytest.fixture(scope="module")
def law():
    return Law.load()


def _runway():
    def end(n, xy):
        return types.SimpleNamespace(name=n, xy=xy, approach="visual")
    return types.SimpleNamespace(id="16/34",
                                 ends=(end("16", (0.0, 0.0)), end("34", (0.0, -3000.0))),
                                 code_number=4, code_letter="E", instrument=False, width_m=45.0)


def _plate() -> WalledPlate:
    return WalledPlate(ids=("dsf:1",), runway="16/34", end=0, plate_y=0.0, inner_s=290.0,
                       stations=((0.0, 288.0),), inner=((-100.0, 290.0), (100.0, 290.0)),
                       outer=((-100.0, 310.0), (100.0, 310.0)),
                       footprint=((-100.0, 290.0), (100.0, 290.0), (100.0, 310.0),
                                  (-100.0, 310.0), (-100.0, 290.0)),
                       height_m=20.0, step_m=15.0, end_name="16")


class _Map:
    """Two 4-vertex service ribbons, each sharing its ring with one runway
    safety-area face."""

    def __init__(self):
        sq = [(-5.0, 100.0), (5.0, 100.0), (5.0, 110.0), (-5.0, 110.0)]
        side = [(120.0, -1000.0), (130.0, -1000.0), (130.0, -990.0), (120.0, -990.0)]
        self.vertices = {}
        for k, xy in enumerate(sq + side):
            self.vertices[k] = types.SimpleNamespace(xy=xy, incident_faces=(), dem_z=0.0)
        F = types.SimpleNamespace
        self.faces = {
            0: F(id=0, role="service_road", ref="small_roads:-1", ring=(0, 1, 2, 3), holes=()),
            1: F(id=1, role="service_road", ref="small_roads:-2", ring=(4, 5, 6, 7), holes=()),
            2: F(id=2, role="graded_strip", ref="adjacent_ground:runway:4:zone2#1",
                 ring=(0, 1, 2, 3, 4, 5, 6, 7), holes=()),
        }
        for v, x in self.vertices.items():
            x.incident_faces = (0 if v < 4 else 1, 2)

    def ring_vertices(self, cyc):
        return list(cyc)


def _airport(plates):
    ways = [types.SimpleNamespace(id=-1, tags={"highway": "service"}),
            types.SimpleNamespace(id=-2, tags={"highway": "service"})]
    return types.SimpleNamespace(runways=(_runway(),), walled_plates=plates, osm_ways=ways)


def test_the_plated_end_area_runs_from_the_end_to_the_inner_edge(law):
    (area,) = plated_end_areas(_airport((_plate(),)), law)
    assert area.contains(Point(0.0, 150.0))
    assert not area.contains(Point(0.0, 300.0))          # past the inner edge
    assert not area.contains(Point(0.0, -50.0))          # the runway itself
    assert plated_end_areas(_airport(()), law) == ()


def test_only_the_plated_end_area_withdraws_the_road_profile(law):
    pm = _Map()
    ap = _airport((_plate(),))
    every = at_grade_rsa_vertices(ap, pm, law)
    assert every == frozenset(range(8))                  # both at grade (28p (1))
    plated = at_grade_rsa_vertices(ap, pm, law, within=plated_end_areas(ap, law))
    assert plated == frozenset(range(4))                 # the side road keeps its profile
    assert at_grade_rsa_vertices(_airport(()), pm, law, within=()) == frozenset()
