"""Issue #877: the gap-joint Voronoi must never see ulp-neighbour sites.

A face ring that walks an antenna edge out and back lists the segment
twice (A->B, B->A).  Densifying both directions minted interior points one
ulp apart, and GEOS's Voronoi of such a site set raised (or returned
self-crossing cells whose next ``intersection`` raised) ``TopologyException:
side location conflict`` -- the airport build failed and shipped ungraded.
The geometry below is the minimal reproduction in local metres: an antenna
edge of one shape facing a two-edge run of another inside the 1 m contact
horizon.
"""
from __future__ import annotations

import shapely
from shapely.geometry import LineString

from auto_patch_v2.planar.shapes import _voronoi_sites

TOL = 1.0
ANTENNA = [((-91.0, 473.0), (-100.0, 453.0)), ((-100.0, 453.0), (-91.0, 473.0))]
FACING = [((-106.5, 481.0), (-90.5, 473.5)), ((-90.5, 473.5), (-75.0, 466.0))]


def _side():
    return {1: [LineString(s) for s in ANTENNA], 2: [LineString(s) for s in FACING]}


def test_an_antenna_edge_densifies_once_and_its_sites_have_no_ulp_neighbours():
    P, labs = _voronoi_sites(_side(), TOL)
    assert len(P) == len(set(P)) == len(labs)
    pts = sorted(P)
    for a, b in zip(pts, pts[1:]):
        assert shapely.Point(a).distance(shapely.Point(b)) > 1e-6
    # the antenna's sites are the ones a single direction mints
    once = shapely.segmentize(LineString(sorted(ANTENNA[0])), TOL).coords
    assert sum(1 for lab in labs if lab == 1) == len(once)


def test_the_gap_voronoi_of_an_antenna_edge_is_valid_and_intersects():
    P, labs = _voronoi_sites(_side(), TOL)
    cells = list(shapely.voronoi_polygons(shapely.multipoints(P)).geoms)
    assert cells and all(c.is_valid for c in cells)
    lens = (shapely.union_all(_side()[1]).buffer(TOL)
            .intersection(shapely.union_all(_side()[2]).buffer(TOL)))
    for i, c in enumerate(cells):
        for d in cells[i + 1:]:
            if c.touches(d):
                c.intersection(d).intersection(lens)     # raised before #877
