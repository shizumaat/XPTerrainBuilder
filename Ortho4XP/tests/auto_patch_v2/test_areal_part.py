"""Twins for #1136 (HEAZ) and #1147 (KCLT): AN AREA'S OVERLAY IS AN AREA.

GEOS's overlay is non-strict: a difference of two areas whose sliver
collapses on the grid hands back that sliver as a LineString beside the
polygons, and the NEXT overlay refuses the collection — the two messages
the owner's app 1.0.409 reported, each losing a whole airport's patch.
``geom/parts.areal_part`` keeps the polygons, and the producers
(``geom/fixed_overlay.fixed_difference``, the road ribbon's
``classify/ribbon_mint._ribbon_over``) hand back only that.  Each twin is
red on main 901f2f587."""
from __future__ import annotations

import pytest
import shapely
from shapely.errors import GEOSException
from shapely.geometry import LineString, Polygon, box

from auto_patch_v2.classify import ribbon_mint
from auto_patch_v2.geom.fixed_overlay import fixed_difference
from auto_patch_v2.geom.parts import areal_part

#: a 10 m square with a 0.1 um wide, 15 m long spike: on the 1e-6 m
#: overlay grid the spike collapses to a line (HEAZ runway 18/36's zone 2
#: carried a 15.3 m one)
SPIKE = Polygon([(0, 0), (10, 0), (10, 10), (5.0000002, 10), (5.0000002, 25),
                 (5.0000001, 25), (5.0000001, 10), (0, 10)])


def _mixed():
    g = shapely.difference(SPIKE, box(2, 2, 3, 3), grid_size=1e-6)
    assert g.geom_type == "GeometryCollection"
    assert {p.geom_type for p in shapely.get_parts(g)} == {"Polygon", "LineString"}
    return g


def test_the_mixed_collection_breaks_the_next_overlay():
    """The witness: both reported messages from the one collection."""
    g = _mixed()
    with pytest.raises(GEOSException, match="mixed-dimension"):
        shapely.difference(g, box(4, 4, 6, 6), grid_size=1e-6)
    with pytest.raises(GEOSException, match="result geometry dimension"):
        shapely.difference(Polygon(), g)


def test_areal_part_keeps_the_polygons_as_they_lie():
    g = _mixed()
    a = areal_part(g)
    assert a.geom_type == "Polygon" and a.is_valid
    assert a.area == pytest.approx(g.area)
    two = shapely.geometrycollections([box(0, 0, 1, 1), LineString([(5, 5), (6, 6)]),
                                       shapely.multipolygons([box(2, 0, 3, 1)])])
    assert areal_part(two).geom_type == "MultiPolygon"
    assert areal_part(two).area == pytest.approx(2.0)
    assert areal_part(LineString([(0, 0), (1, 1)])).is_empty
    assert areal_part(None).is_empty
    sq = box(0, 0, 1, 1)
    assert areal_part(sq) is sq


def test_fixed_difference_of_an_area_is_an_area():
    """#1136: zone 2 less the claim, then less the #951 road cut."""
    z2 = fixed_difference(SPIKE, box(2, 2, 3, 3))
    assert z2.geom_type in ("Polygon", "MultiPolygon")
    assert z2.area == pytest.approx(100.0 - 1.0, abs=1e-5)
    assert fixed_difference(z2, box(4, 4, 6, 6)).area == pytest.approx(95.0, abs=1e-5)


def test_a_ribbon_is_an_area():
    """#1147: a ribbon whose cut collapses a sliver is stored and cut by
    the next way as an area."""
    class _Collapsing:
        def cut(self, g):
            return _mixed()

    rib = ribbon_mint._ribbon_over([LineString([(0, 5), (10, 5)])], 3.0,
                                   _Collapsing(), 3.0, 0.01)
    assert rib.geom_type in ("Polygon", "MultiPolygon")
    occ = ribbon_mint._Occupied(Polygon())
    occ.add(rib)
    assert occ.cut(box(1, 1, 2, 2)).is_empty
