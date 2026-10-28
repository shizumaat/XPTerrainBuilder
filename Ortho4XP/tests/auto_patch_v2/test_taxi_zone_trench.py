"""Q245 (owner 2026-10-27, "Yes"; spec ``lfpg-cuts-tunnels-rules-spec.md``
§10 R2): A TAXIWAY'S ZONE OF GRADED GROUND GIVES WAY TO A TRENCH THE SURVEY
SHOWS INSIDE IT (``planar/lidar_road.survey_road_trenches``, cut at
``planar/zones.zone_regions``).

Found at LFPG (the Roissypole road's open approach and the 2A south service
portal: a taxiway's adjacent-ground zone graded across the survey's cut).
The twins hold the general rule on a synthetic field: a mapped road inside a
taxiway band, in a both-sides cut on a credible survey, takes its trench out
of the band; no cut, or a coarse DEM, takes nothing."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import zone_edge_offset_m
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.lidar_road import survey_road_trenches
from auto_patch_v2.planar.road_yield import road_carriageways
from auto_patch_v2.planar.terrain_edge import EdgeReport
from auto_patch_v2.planar.zones import zone_regions
from shapely.geometry import Point
from shapely.ops import unary_union

#: a taxiway 30 m wide along y, its east edge at x = 0
PAV = ((-30.0, -400.0), (0.0, -400.0), (0.0, 400.0), (-30.0, 400.0))
#: the trench's depth under the ground beside it (m)
DEPTH = 7.0


class _Survey:
    """700 m ground; with ``cut`` a trench ``DEPTH`` deep, 12 m wide, along
    y = 0 east of the taxiway's edge (the open approach to a portal under
    it).  ``lidar`` False is a coarse DEM."""
    provenance = {"synthetic": "trench"}

    def __init__(self, cut: bool, lidar: bool = True):
        self.cut, self.lidar = cut, lidar

    def z(self, x: float, y: float) -> float:
        if self.cut and abs(y) < 6.0 and 0.0 < x < 300.0:
            return 700.0 - DEPTH
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)

    def source_pixel_m(self):
        return (1.0, "inset") if self.lidar else (30.0, "inset")


class _Field:
    """The airport as the survey reader sees it: its DEM."""
    flat_site = None

    def __init__(self, dem):
        self.dem = dem


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells():
    return (Cell(0, "junction", "T", PAV, (), None, "C", "airside", "junction", {}),)


def _setup(law):
    """The band's reach past the edge, and a service road leaving the
    taxiway's edge east across its band, in the trench where there is one."""
    reach = zone_edge_offset_m(law, "junction", None, "C")
    way = OsmWay(1, "big_roads", ((0.5, 0.0), (300.0, 0.0)), False,
                 {"highway": "service"})
    return reach, road_carriageways((way,), law)


def _taxi(law, cw, field=None, rep=None):
    fn = None if field is None else (
        lambda region: survey_road_trenches(field, law, cw, region))
    regions = zone_regions(_cells(), law, carriageways=cw, edge_report=rep, trenches=fn)
    return unary_union([r.polygon for r in regions if r.family == "taxi"])


def test_the_taxiway_zone_gives_way_to_the_surveyed_trench(law):
    reach, cw = _setup(law)
    half = cw[0][1]
    tn = law.tables.structures.tunnel
    # in the band, on the trench's bank: past the carriageway and its
    # stand-off (the standing road yield), inside the bank
    p = Point(reach / 2.0,
              half + float(tn.wall_gap_m) + float(tn.wall_band_width_m) + DEPTH / 2.0)
    assert _taxi(law, cw).covers(p)                       # the standing law
    rep = EdgeReport()
    assert not _taxi(law, cw, _Field(_Survey(cut=True)), rep).covers(p)
    assert rep.survey_trenches == 1 and rep.trench_cut_m2 > 0.0
    assert "Q245" in rep.line()


@pytest.mark.parametrize("cut,lidar", [(False, True), (True, False)])
def test_no_cut_or_a_coarse_dem_takes_nothing(law, cut, lidar):
    _reach, cw = _setup(law)
    base = _taxi(law, cw)
    rep = EdgeReport()
    got = _taxi(law, cw, _Field(_Survey(cut=cut, lidar=lidar)), rep)
    assert rep.survey_trenches == 0
    assert got.symmetric_difference(base).area < 1e-6


def test_the_trench_is_read_only_near_the_band(law):
    _reach, cw = _setup(law)
    field = _Field(_Survey(cut=True))
    band = _taxi(law, cw)
    got = survey_road_trenches(field, law, cw, band)
    assert len(got) == 1
    # read one cut reach past the band, never the road's whole 300 m
    tn = law.tables.structures.tunnel
    assert got[0].bounds[2] <= band.bounds[2] + 4.0 * float(tn.mouth_depth_m) + 1e-6
    # a road that never enters the band reads nothing
    far = road_carriageways((OsmWay(2, "big_roads", ((100.0, 0.0), (300.0, 0.0)),
                                    False, {"highway": "service"}),), law)
    assert survey_road_trenches(field, law, far, band) == ()
