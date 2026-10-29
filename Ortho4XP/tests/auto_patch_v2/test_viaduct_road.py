"""R6 (owner RULINGS 2026-10-28k, Q228 a; spec ``lfpg-cuts-tunnels-rules-
spec.md`` R6): A ROAD UNDER STACKED VIADUCTS INSIDE THE AIRPORT SITS A MOUTH
DEPTH BELOW THE APRON (``planar/viaduct_road``).

Found at LFPG (the Terminal 2 central road under the departure and arrival
viaducts).  The twins hold the general rule on a synthetic field: a mapped
road running >= ``viaduct_min_run_m`` under ``layer >= viaduct_min_layer``
bridge ways inside the aerodrome boundary is two sibling Law-B halves level
at ``apron - mouth_depth_m``, climbing back to the ground beyond the run; a
lower viaduct, a short run or a run outside the boundary builds nothing."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Boundary, OsmWay
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar.viaduct_road import ID_PREFIX, viaduct_road_groups
from shapely.geometry import Polygon

GROUND = 100.0
#: an apron north of the road, its south edge 60 m off it
APRON = ((-300.0, 60.0), (300.0, 60.0), (300.0, 200.0), (-300.0, 200.0))
BOX = ((-2000.0, -2000.0), (2000.0, -2000.0), (2000.0, 2000.0), (-2000.0, 2000.0))


class _Dem:
    def z(self, x: float, y: float) -> float:
        return GROUND


class _Field:
    def __init__(self, ways, boundary=BOX):
        self.osm_ways = tuple(ways)
        self.dem = _Dem()
        self.boundaries = (Boundary("b", boundary, ()),) if boundary else ()


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ways(layer: int = 2, span: float = 200.0):
    road = OsmWay(1, "big_roads", ((-1000.0, 0.0), (0.0, 0.0), (1000.0, 0.0)), False,
                  {"highway": "service"})
    via = OsmWay(2, "big_roads", ((-span / 2.0, 0.0), (span / 2.0, 0.0)), False,
                 {"highway": "trunk", "bridge": "yes", "layer": str(layer)})
    return [road, via]


def _cells():
    c = Cell(0, "apron", "A", APRON, (), None, None, "airside", "apron", {})
    return (c,), (Polygon(APRON),)


def test_a_road_under_stacked_viaducts_is_lowered_a_mouth_depth(law):
    cells, polys = _cells()
    groups, notes, refused = viaduct_road_groups(_Field(_ways()), law, cells, polys)
    assert not refused and len(notes) == 1 and "R6" in notes[0]
    assert len(groups) == 2
    a, b = groups
    assert a.sibling == b.tid and b.sibling == a.tid
    assert a.tid.startswith(ID_PREFIX) and a.kind == "sunken_road"
    assert not a.capped and not a.mouth_strip
    tn = law.tables.structures.tunnel
    floor = GROUND - tn.mouth_depth_m
    for g in groups:
        # level under the viaducts (100 m each side of the midpoint) ...
        assert profile_z(g.profile, 0.0) == pytest.approx(floor)
        assert profile_z(g.profile, 95.0) == pytest.approx(floor)
        # ... climbing back to the ground beyond the run at the design grade
        s_top, z_top = g.profile[-1]
        assert z_top == pytest.approx(GROUND, abs=tn.ramp_grade * 5.0 + 1e-6)
        rise = (z_top - floor) / (s_top - g.profile[1][0])
        assert rise <= tn.ramp_grade + 1e-9
        assert g.corridor.floor_z == pytest.approx(floor)


@pytest.mark.parametrize("layer,span,boundary", [
    (1, 200.0, BOX),                     # a single-level bridge is not a viaduct stack
    (2, 60.0, BOX),                      # under 100 m of cover
    (2, 200.0, ((1500.0, 1500.0), (1900.0, 1500.0), (1900.0, 1900.0))),  # outside the field
    (2, 200.0, None),                    # no aerodrome boundary at all
])
def test_no_witness_builds_nothing(law, layer, span, boundary):
    cells, polys = _cells()
    groups, notes, refused = viaduct_road_groups(_Field(_ways(layer, span), boundary), law,
                                                 cells, polys)
    assert groups == [] and notes == [] and refused == []


def test_no_apron_near_the_run_is_refused_by_name(law):
    groups, notes, refused = viaduct_road_groups(_Field(_ways()), law, (), ())
    assert groups == [] and len(refused) == 1 and "no airside apron" in refused[0]
