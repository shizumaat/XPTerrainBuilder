"""R17c-2 THE FEATHER STOPS AT THE WALL / R17c-3 THE AIRPORT'S ISLAND.

r17b landed the coastline wall's ADMISSION and measured two things that
made it necessary-but-not-sufficient (RULINGS 2026-08-12):

  * the admission spanned ALL flat-site rectangles on the tile — three
    flat sites plus mainland coastline, 66,971 m of wall over 55.47 km²
    — where the owner's ruling walls THE AIRPORT's reclaimed edge;
  * the wall was admitted and the shore still rendered a RAMP: the
    flat-site constant inset feathers its blend over the last 60 m
    INSIDE its own extent, and at a reclaimed island that extent edge is
    the shoreline, so the ramp is the beach (VHHH north-shore transect
    7.315 → 0 over 33–44 m, four mesh samples).

Both laws are geometry, and both are tested here on synthetic geometry
through production's own functions.

Headless: no DEM, no network, no X-Plane install.
"""

from __future__ import annotations

import sys
from pathlib import Path

from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Geo_Utils as GEO  # noqa: E402

TILE_LAT, TILE_LON = 22, 113

#: The AIRPORT's island, the MAINLAND shore inside the same rectangle,
#: and the sea between them — the VHHH/Lantau shape in miniature.
ISLAND = geometry.box(0.30, 0.34, 0.40, 0.40)
MAINLAND = geometry.box(0.25, 0.20, 0.45, 0.30)
SEA = geometry.box(0.0, 0.0, 1.0, 1.0).difference(
    ISLAND.union(MAINLAND))
#: One flat-site extent big enough to hold BOTH — which is exactly the
#: scope failure: a rectangle around an airport is not the airport.
CORE = (0.28, 0.22, 0.42, 0.42)
#: The airport's own emitted graded coverage, on the island.
COVERAGE = geometry.box(0.33, 0.36, 0.37, 0.38)


class _Dem:
    def __init__(self, entries):
        self.synthetic_flat_site_provenance = list(entries)


class _Tile:
    def __init__(self, dem=None):
        self.lat = TILE_LAT
        self.lon = TILE_LON
        self.dem = dem


def _entry(kind, x0, y0, x1, y1, icao="VHHH", z0=7.315):
    return {"kind": kind, "icao": icao, "z0_m": z0,
            "extent_tile_degrees": [x0, y0, x1, y1]}


def _tile_with_core():
    return _Tile(_Dem([_entry("synthetic_flat_site", *CORE)]))


class TestR17c3TheScopeIsTheAirportsIsland:
    """Never every flat rectangle on the tile, never mainland."""

    def test_the_mainland_inside_the_same_rectangle_is_NOT_admitted(self):
        land = VMAP.coastline_wall_admission(_tile_with_core(), SEA,
                                             graded_area=COVERAGE)
        assert not land.is_empty
        assert land.intersects(ISLAND)
        assert not land.intersects(MAINLAND.buffer(-1e-4))

    def test_the_island_the_coverage_stands_on_IS_admitted(self):
        land = VMAP.coastline_wall_admission(_tile_with_core(), SEA,
                                             graded_area=COVERAGE)
        # The whole island, not merely the coverage ring: the wall runs
        # the island's edge, which is the owner's ruling.
        assert land.contains(geometry.Point(0.31, 0.39))
        assert land.contains(COVERAGE.representative_point())

    def test_NO_COVERAGE_IS_NO_ADMISSION_never_the_whole_rectangle(self):
        """The wrong scope must not be the fallback.  With nothing
        saying which land is the airport's, admitting the rectangle is
        precisely what the ruling refused."""
        assert VMAP.coastline_wall_admission(
            _tile_with_core(), SEA, graded_area=None).is_empty
        assert VMAP.coastline_wall_admission(
            _tile_with_core(), SEA,
            graded_area=geometry.Polygon()).is_empty

    def test_a_second_airports_island_is_admitted_by_ITS_OWN_coverage(self):
        """VMMC is not a byte-identical control (owner 2026-08-12): it is
        a flat site too and its island is lawful under the same scoping.
        One pass serves every airport on the tile, naming no ICAO."""
        second = geometry.box(0.60, 0.60, 0.70, 0.70)
        sea = geometry.box(0.0, 0.0, 1.0, 1.0).difference(
            ISLAND.union(MAINLAND).union(second))
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("synthetic_flat_site", 0.58, 0.58, 0.72, 0.72,
                   icao="VMMC", z0=6.10),
        ]))
        both = geometry.MultiPolygon(
            [COVERAGE, geometry.box(0.63, 0.63, 0.67, 0.67)])
        land = VMAP.coastline_wall_admission(tile, sea, graded_area=both)
        assert land.intersects(ISLAND) and land.intersects(second)
        assert not land.intersects(MAINLAND.buffer(-1e-4))

    def test_a_cluster_rectangle_reaching_the_mainland_admits_nothing(self):
        """The r17b defect in one assertion: the claimed-object cluster
        box covers mainland shore, and under R17c-3 it is out of the
        island reading entirely."""
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", 0.30, 0.34, 0.40, 0.40),
            _entry("synthetic_flat_site_object_cluster",
                   0.25, 0.20, 0.45, 0.30),
        ]))
        land = VMAP.coastline_wall_admission(tile, SEA,
                                             graded_area=COVERAGE)
        assert not land.intersects(MAINLAND.buffer(-1e-4))

    def test_the_isthmus_joins_when_it_is_continuous(self):
        """R21 in the corridor's slot: the isthmus is measured precisely
        because it makes two grounds one, so it joins the island exactly
        when it has — the component test is the membership law, never a
        private union."""
        east = geometry.box(0.42, 0.35, 0.48, 0.39)
        isthmus = geometry.box(0.40, 0.363, 0.42, 0.367)
        sea = geometry.box(0.0, 0.0, 1.0, 1.0).difference(
            ISLAND.union(MAINLAND).union(east).union(isthmus))
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("flat_site_isthmus", 0.40, 0.363, 0.48, 0.367),
        ]))
        land = VMAP.coastline_wall_admission(tile, sea,
                                             graded_area=COVERAGE)
        assert land.intersects(ISLAND)
        assert land.intersects(isthmus)


class TestR17c3TheWallLength:
    """The admission geometry moves; the breakline law does not."""

    def _wall(self, admission, sea):
        return VMAP.seawall_breaklines(admission, sea, float(TILE_LAT))

    def test_the_wall_runs_the_island_edge_and_not_the_mainland(self):
        land = VMAP.coastline_wall_admission(_tile_with_core(), SEA,
                                             graded_area=COVERAGE)
        lines = self._wall(land, SEA)
        assert lines
        total = sum(geometry.LineString(c).length for c in lines)
        assert total > 0.9 * ISLAND.exterior.length
        assert total < 1.2 * ISLAND.exterior.length     # not + mainland


class TestR17c2TheFeatherStopsAtTheWall:
    """The constant inset holds Z0 TO the declared extent; the blend
    ramp lands OUTSIDE it."""

    def test_the_grown_extent_is_the_declared_one_plus_the_feather(self):
        tile = _Tile()
        x0, y0, x1, y1 = 0.30, 0.34, 0.40, 0.40
        gx0, gy0, gx1, gy1 = INSETS._feather_outward_extent(
            tile, x0, y0, x1, y1, 60.0)
        assert gx0 < x0 and gy0 < y0 and gx1 > x1 and gy1 > y1
        # Exactly the feather, in metres, on each axis.
        assert abs((y0 - gy0) * GEO.lat_to_m - 60.0) < 1e-6
        lon_m = GEO.lon_to_m(tile.lat + (y0 + y1) / 2.0)
        assert abs((x0 - gx0) * lon_m - 60.0) < 1e-6

    def test_weight_reaches_ONE_on_the_declared_boundary(self):
        """THE POINT.  ``_bake_one_inset`` ramps
        ``clip(distance_to_edge / feather_m)`` from its raster's own
        edge, so with the raster grown by the feather the weight is 1
        (full Z0) everywhere from the declared boundary inward — the
        shore keeps Z0 to the wall line instead of ramping to sea."""
        tile = _Tile()
        x0, y0, x1, y1 = 0.30, 0.34, 0.40, 0.40
        feather = 60.0
        gx0, gy0, gx1, gy1 = INSETS._feather_outward_extent(
            tile, x0, y0, x1, y1, feather)
        for (px, py) in ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2),
                         ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1),
                         ((x0 + x1) / 2, (y0 + y1) / 2)):
            lon_m = GEO.lon_to_m(tile.lat + py)
            d = min((px - gx0) * lon_m, (gx1 - px) * lon_m,
                    (py - gy0) * GEO.lat_to_m, (gy1 - py) * GEO.lat_to_m)
            assert min(d / feather, 1.0) >= 1.0 - 1e-9

    def test_the_ramp_is_wholly_outside_the_declared_extent(self):
        """Halfway out into the grown band the weight is partial — the
        feather still exists, it has just moved off the site."""
        tile = _Tile()
        x0, y0, x1, y1 = 0.30, 0.34, 0.40, 0.40
        feather = 60.0
        _gx0, gy0, _gx1, _gy1 = INSETS._feather_outward_extent(
            tile, x0, y0, x1, y1, feather)
        py = y0 - (y0 - gy0) / 2.0
        d = (py - gy0) * GEO.lat_to_m
        assert 0.0 < min(d / feather, 1.0) < 1.0

    def test_a_zero_feather_grows_nothing(self):
        """The inert answer: with the feather off the extent is the
        declared one, byte-for-byte."""
        tile = _Tile()
        assert INSETS._feather_outward_extent(
            tile, 0.3, 0.34, 0.4, 0.4, 0.0) == (0.3, 0.34, 0.4, 0.4)

    def test_the_PROVENANCE_extent_is_never_the_grown_one(self):
        """The stamp is what the wall's admission reads, and admitting
        the grown box would wall 60 m of open sea.  The grower is a
        pure function of its arguments and touches no stamp — asserted
        by construction here, and by the bake passing the DECLARED
        extent into the provenance entry beside it."""
        import inspect
        src = inspect.getsource(INSETS.overlay_flat_site_insets)
        assert '"extent_tile_degrees": [x0, y0, x1, y1]' in src
        assert '_feather_outward_extent(tile, x0, y0, x1, y1' in src
