"""The post-mesh sea guard (lflood, +53+009, app 1.0.557): a SEA region
that leaked onto land refuses the tile instead of shipping a flooded DSF;
a mesh whose sea stays in the coastline's sea passes untouched."""

import numpy
import O4_Sea_Leak_Guard as GUARD
import O4_Tile_Failures as FAIL
import pytest
from shapely import geometry

SEA, WATER, INTERP = 2, 1, 8


class _Tile:
    lat, lon = 53, 9


def _grid_mesh(n=40):
    """A unit-square mesh of 2 n^2 triangles: ``(xy, corners, centroids)``."""
    g = numpy.linspace(0.0, 1.0, n + 1)
    xx, yy = numpy.meshgrid(g, g)
    xy = numpy.column_stack([xx.ravel(), yy.ravel()])
    tris = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            b, c, d = a + 1, a + n + 1, a + n + 2
            tris += [(a, b, d), (a, d, c)]
    corners = numpy.array(tris)
    return xy, corners, xy[corners].mean(axis=1)


#: the coastline's sea: the western tenth of the tile (an estuary)
_ESTUARY = geometry.box(0.0, 0.0, 0.1, 1.0)


def _attrs(centroids, flooded):
    attrs = numpy.where(centroids[:, 0] < 0.1, SEA, 0)
    attrs[(centroids[:, 1] > 0.5) & (centroids[:, 0] < 0.05)] |= WATER
    attrs[(centroids[:, 0] > 0.7) & (centroids[:, 1] > 0.7)] = INTERP
    if flooded:            # the seed's region leaked: every land triangle
        attrs = attrs | SEA
    return attrs


def test_a_mesh_whose_sea_stays_in_the_coastline_passes():
    xy, corners, centroids = _grid_mesh()
    km2 = GUARD.audit_sea_extent(_Tile(), xy, corners,
                                 _attrs(centroids, False), sea=_ESTUARY)
    assert km2 == 0.0


def test_a_flooded_mesh_is_refused_with_the_leak_named():
    xy, corners, centroids = _grid_mesh()
    with pytest.raises(GUARD.SeaLeak, match="SEA LEAK at \\+53\\+009") as e:
        GUARD.audit_sea_extent(_Tile(), xy, corners,
                               _attrs(centroids, True), sea=_ESTUARY)
    assert "OUTSIDE the coastline's sea" in str(e.value)
    assert FAIL.code_for_exception(e.value) == "mesh_refused"


def test_a_leak_onto_one_small_island_is_refused_too():
    """The 11-16 build's own residue: one sliver seed on the wrong side
    of an island in the estuary flooded the island (1.2 km2)."""
    xy, corners, centroids = _grid_mesh(200)
    island = geometry.box(0.03, 0.40, 0.07, 0.44)
    estuary = _ESTUARY.difference(island)
    attrs = numpy.where(centroids[:, 0] < 0.1, SEA, 0)
    assert GUARD.leaked_sea(xy, corners, attrs, estuary)[1] > 0
    with pytest.raises(GUARD.SeaLeak):
        GUARD.audit_sea_extent(_Tile(), xy, corners, attrs, sea=estuary)


def test_the_warn_switch_reports_instead_of_refusing(monkeypatch):
    monkeypatch.setenv(GUARD.SEA_LEAK_ENV, "warn")
    xy, corners, centroids = _grid_mesh()
    km2 = GUARD.audit_sea_extent(_Tile(), xy, corners,
                                 _attrs(centroids, True), sea=_ESTUARY)
    assert km2 > GUARD.SEA_LEAK_MAX_KM2


def test_a_tile_without_a_coastline_on_disk_is_not_judged(monkeypatch):
    """No coastline, no partition to judge by: an open-ocean tile's
    fallback seed floods it by design."""
    monkeypatch.setattr(GUARD, "_coastline_sea", lambda tile: None)
    xy, corners, centroids = _grid_mesh()
    attrs = numpy.full(len(corners), SEA)
    assert GUARD.audit_sea_extent(_Tile(), xy, corners, attrs) == 0.0
