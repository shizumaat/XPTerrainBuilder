"""R17D LAW 2 — CONNECTED-ISLAND WALLS + FEATHER.

Owner ruling 2026-08-12 ("CONNECTED-ISLAND WALLS", in-sim on the rebuilt
+22+113): the island CONNECTED to the airport complex — the owner's
point 22.3123837, 113.9521587, joined to VHHH across the causeway —
gets the straight seawall too; its edge must not slope to water.

R21 CONVERTED THE JOINING MECHANISM.  Where these twins used the
DECLARED CORRIDOR (retired with its cfg key, owner 2026-08-12) they now
use the ISTHMUS the flat-site family is measured to stand across: the
same structural role — an unconditional inset kind spanning the two
footprints — reached automatically instead of by declaration.

r17c had walled the airport's constant CORE ∪ its DECLARED corridors and
kept the claimed-object CLUSTER rectangles out WHOLE, because a cluster
box is the box that reached the mainland (VHHH's 15.11 km² HZMB cluster;
66,971 m of wall over 55.47 km²).  R17D admits the kind exactly where it
is CONNECTED, and the island scoping still refuses the mainland reach of
an admitted box — two gates, two different failures.

The FEATHER half (R17c-2, Z0 to the wall line and the ramp seaward) is
asserted here for the cluster bake, which is what "the same treatment"
means for a cluster island.  The isthmus bake takes NO feather (its edge
is the shoreline or the family's own footprint) — twinned in
``tests/test_r21_land_connected_continuity.py``.

Headless: no DEM, no network, no X-Plane install.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Airport_Elevation_Insets as INSETS  # noqa: E402

TILE_LAT, TILE_LON = 22, 113

#: The VHHH shape in miniature: the airport's island, the EAST island
#: joined to it by the declared corridor, the mainland shore, the sea.
ISLAND = geometry.box(0.30, 0.34, 0.40, 0.40)
#: R21: the two islands are ONE land component — the isthmus is real
#: ground in the coastline data, which is what the law measures (VHHH's
#: causeway: one 21.2 km² sea-bounded component, the neck ~148 m wide).
ISTHMUS_LAND = geometry.box(0.40, 0.3625, 0.44, 0.3675)
EAST = geometry.box(0.44, 0.35, 0.50, 0.39)
MAINLAND = geometry.box(0.25, 0.18, 0.60, 0.28)
#: A cluster island the airport claims but that touches nothing of it.
FARAWAY = geometry.box(0.80, 0.80, 0.86, 0.86)
SEA = geometry.box(0.0, 0.0, 1.0, 1.0).difference(
    ISLAND.union(ISTHMUS_LAND).union(EAST).union(MAINLAND).union(FARAWAY))
CORE = (0.28, 0.32, 0.42, 0.42)
#: The ISTHMUS stamp: the connecting land between the two footprints,
#: measured by R21's law and stamped by the bake.  It touches both, which
#: is what "connecting" means.
ISTHMUS = (0.39, 0.362, 0.46, 0.368)
#: The cluster box over the east island, and one over the far one.
EAST_CLUSTER = (0.43, 0.34, 0.51, 0.40)
FAR_CLUSTER = (0.79, 0.79, 0.87, 0.87)
#: The airport's own emitted graded coverage, on its island.  R21 needs
#: no second polygon beside it: the isthmus is LAND on the same
#: component, so the component the coverage stands on already carries it
#: (that is the whole point of the land-connection law).
COVERAGE = geometry.box(0.33, 0.36, 0.37, 0.38)
COVERAGE_WITH_CORRIDOR = COVERAGE


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


def _vhhh_tile():
    """Core + isthmus + BOTH cluster boxes — the connected one and the
    distant one, so every assertion below is made against one stamp,
    never a stamp curated per test."""
    return _Tile(_Dem([
        _entry("synthetic_flat_site", *CORE),
        _entry("flat_site_isthmus", *ISTHMUS),
        _entry("synthetic_flat_site_object_cluster", *EAST_CLUSTER),
        _entry("synthetic_flat_site_object_cluster", *FAR_CLUSTER),
    ]))


class TestTheConnectedClusterFootprint:
    """:func:`connected_cluster_inset_area` — the FOOTPRINT half."""

    def test_a_cluster_joined_by_the_isthmus_is_connected(self):
        core = VMAP.constant_inset_area(_vhhh_tile())
        joined = VMAP.connected_cluster_inset_area(_vhhh_tile(), core)
        assert joined.contains(geometry.Point(0.47, 0.37))

    def test_a_distant_cluster_is_NOT_connected(self):
        core = VMAP.constant_inset_area(_vhhh_tile())
        joined = VMAP.connected_cluster_inset_area(_vhhh_tile(), core)
        assert not joined.intersects(geometry.box(*FAR_CLUSTER).buffer(-1e-4))

    def test_connection_is_TRANSITIVE(self):
        """A chain of reclamation boxes along one causeway is one
        complex: the second hop is joined through the first."""
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("synthetic_flat_site_object_cluster",
                   0.42, 0.36, 0.46, 0.38),
            _entry("synthetic_flat_site_object_cluster",
                   0.46, 0.36, 0.50, 0.38),
        ]))
        joined = VMAP.connected_cluster_inset_area(
            tile, VMAP.constant_inset_area(tile))
        assert joined.contains(geometry.Point(0.44, 0.37))
        assert joined.contains(geometry.Point(0.48, 0.37))

    def test_no_core_is_the_inert_answer(self):
        """With no airport footprint on the tile there is nothing to be
        connected TO — never "admit every cluster"."""
        assert VMAP.connected_cluster_inset_area(
            _vhhh_tile(), geometry.Polygon()).is_empty
        assert VMAP.connected_cluster_inset_area(
            _vhhh_tile(), None).is_empty

    def test_no_cluster_stamp_is_the_inert_answer(self):
        tile = _Tile(_Dem([_entry("synthetic_flat_site", *CORE)]))
        assert VMAP.connected_cluster_inset_area(
            tile, VMAP.constant_inset_area(tile)).is_empty
        assert VMAP.connected_cluster_inset_area(
            _Tile(), geometry.box(*CORE)).is_empty

    def test_a_malformed_cluster_entry_is_skipped_not_fatal(self):
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("flat_site_isthmus", *ISTHMUS),
            {"kind": "synthetic_flat_site_object_cluster"},
            {"kind": "synthetic_flat_site_object_cluster",
             "extent_tile_degrees": [1, 2]},
            _entry("synthetic_flat_site_object_cluster", *EAST_CLUSTER),
        ]))
        joined = VMAP.connected_cluster_inset_area(
            tile, VMAP.constant_inset_area(tile))
        assert joined.contains(geometry.Point(0.47, 0.37))

    def test_the_UNCONDITIONAL_kinds_reading_is_untouched(self):
        """``constant_inset_area``'s default still answers "the core and
        the isthmus" — the cluster kind is admitted through
        the CONNECTION gate, never by widening that reading (a caller
        measuring the BAKED surface still asks with ``kinds=None``)."""
        core = VMAP.constant_inset_area(_vhhh_tile())
        assert not core.contains(geometry.Point(0.50, 0.395))
        assert VMAP.constant_inset_area(
            _vhhh_tile(), kinds=None).contains(geometry.Point(0.85, 0.85))


class TestTheConnectedIslandTakesTheWall:
    """The ADMISSION — what the wall law is handed."""

    def test_the_east_island_edge_is_admitted(self):
        """THE OWNER'S POINT.  With the cluster box connected, the whole
        east island's land joins the admission set, so its edge takes
        the vertical face instead of ramping to water."""
        land = VMAP.coastline_wall_admission(
            _vhhh_tile(), SEA, graded_area=COVERAGE_WITH_CORRIDOR)
        assert land.intersects(EAST)
        assert land.contains(geometry.Point(0.49, 0.385))

    def test_r17c_would_have_admitted_only_the_isthmus_overlap(self):
        """The measured gap this law closes: without the cluster kind the
        island is in the reading only where the ISTHMUS box happens to
        cover it, and the rest of its shore keeps the beach ramp."""
        r17c_tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("flat_site_isthmus", *ISTHMUS),
        ]))
        land = VMAP.coastline_wall_admission(
            r17c_tile, SEA, graded_area=COVERAGE_WITH_CORRIDOR)
        assert not land.contains(geometry.Point(0.49, 0.385))

    def test_the_distant_cluster_island_is_NOT_admitted(self):
        land = VMAP.coastline_wall_admission(
            _vhhh_tile(), SEA, graded_area=COVERAGE_WITH_CORRIDOR)
        assert not land.intersects(FARAWAY.buffer(-1e-4))

    def test_the_MAINLAND_an_admitted_cluster_reaches_is_still_refused(self):
        """r17c's reason for excluding the kind, kept: the east cluster
        box here also covers mainland shore, and the mainland is a
        different land COMPONENT carrying none of the graded coverage."""
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("flat_site_isthmus", *ISTHMUS),
            _entry("synthetic_flat_site_object_cluster",
                   0.43, 0.18, 0.51, 0.40),
        ]))
        land = VMAP.coastline_wall_admission(
            tile, SEA, graded_area=COVERAGE_WITH_CORRIDOR)
        assert land.intersects(EAST)
        assert not land.intersects(MAINLAND.buffer(-1e-4))

    def test_a_second_airport_is_judged_against_ITS_OWN_islands(self):
        """VMMC is not a byte-identical control (owner 2026-08-12): it is
        a flat site too.  One pass serves every airport on the tile and
        names no ICAO — VMMC's claimed cluster is connected to VMMC's own
        core, and the spur it reclaims is walled because it is VMMC's
        island, not because anything here knows what VMMC is."""
        vmmc = geometry.box(0.62, 0.62, 0.68, 0.68)
        #: The claimed reclamation: land-contiguous with VMMC's island,
        #: and OUTSIDE VMMC's own flat-site rectangle — so only the
        #: cluster box brings its outer shore into the reading.
        vmmc_spur = geometry.box(0.68, 0.63, 0.74, 0.67)
        sea = geometry.box(0.0, 0.0, 1.0, 1.0).difference(
            ISLAND.union(ISTHMUS_LAND).union(EAST).union(vmmc)
            .union(vmmc_spur))
        tile = _Tile(_Dem([
            _entry("synthetic_flat_site", *CORE),
            _entry("synthetic_flat_site", 0.60, 0.60, 0.70, 0.70,
                   icao="VMMC", z0=6.10),
            _entry("synthetic_flat_site_object_cluster",
                   0.69, 0.62, 0.75, 0.68, icao="VMMC", z0=6.10),
        ]))
        coverage = geometry.MultiPolygon(
            [COVERAGE, geometry.box(0.64, 0.64, 0.66, 0.66)])
        land = VMAP.coastline_wall_admission(tile, sea, graded_area=coverage)
        assert land.intersects(vmmc)
        assert land.contains(geometry.Point(0.73, 0.65))    # the spur
        # …and VHHH's island is admitted by VHHH's own coverage in the
        # same pass, which is what "no ICAO is named" means.
        assert land.intersects(ISLAND)

    def test_NO_COVERAGE_IS_STILL_NO_ADMISSION(self):
        """The connection gate never becomes the fallback the ruling
        refused: with nothing saying which land is the airport's, an
        admitted cluster box admits no land either."""
        assert VMAP.coastline_wall_admission(
            _vhhh_tile(), SEA, graded_area=None).is_empty


class TestTheFeatherOnTheClusterBake:
    """R17c-2 applied to the cluster inset exactly as to the airport's
    own extent: Z0 holds to the wall line, the ramp lands seaward."""

    def test_every_RECTANGULAR_bake_grows_its_raster_by_the_feather(self):
        src = inspect.getsource(INSETS.overlay_flat_site_insets)
        assert "_feather_outward_extent(tile, x0, y0, x1, y1" in src
        assert "_feather_outward_extent(tile, cx0, cy0, cx1, cy1" in src

    def test_every_PROVENANCE_extent_is_the_MEASURED_one(self):
        """The stamp is what the wall's admission reads, and admitting a
        grown box would wall 60 m of open sea — for a cluster island
        exactly as for the airport's own extent."""
        src = inspect.getsource(INSETS.overlay_flat_site_insets)
        assert '"extent_tile_degrees": [x0, y0, x1, y1]' in src
        assert '"extent_tile_degrees": [cx0, cy0, cx1, cy1]' in src

    def test_the_grown_cluster_extent_holds_Z0_to_its_declared_edge(self):
        """The bake ramps ``clip(distance_to_edge / feather_m)`` from its
        raster's own edge, so a raster grown by the feather reaches full
        Z0 ON the declared boundary — the cluster island's shore keeps Z0
        to the wall line."""
        import O4_Geo_Utils as GEO
        tile = _Tile()
        x0, y0, x1, y1 = EAST_CLUSTER
        feather = 60.0
        gx0, gy0, gx1, gy1 = INSETS._feather_outward_extent(
            tile, x0, y0, x1, y1, feather)
        for (px, py) in ((x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2),
                         ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)):
            lon_m = GEO.lon_to_m(tile.lat + py)
            d = min((px - gx0) * lon_m, (gx1 - px) * lon_m,
                    (py - gy0) * GEO.lat_to_m, (gy1 - py) * GEO.lat_to_m)
            assert min(d / feather, 1.0) >= 1.0 - 1e-9
