"""R17b-2 — THE WALL STANDS ON THE COASTLINE.

Round 7 admitted a sea wall only where PAVEMENT touches water: at VHHH
that is 11 breaklines / 1,562 m = 7.5 % of the 20,873 m reclaimed
shoreline, and the other edges render ~26 % beach ramps.  The owner
ruled the WHOLE airport edge is a vertical sea wall.

THE LAW.  Where the OSM coastline runs inside a flat site's CONSTANT-
INSET footprint — the reclaimed island, its claimed-object clusters and
the R17-2 declared corridor — the land side is already held at the
inset's Z0 (the coastline is encoded with ``tile.dem.alt_vec``), so the
coastline joins the wall's ADMISSION geometry and the existing 0.5 m
outward-offset breakline idiom supplies the sea-side node that makes the
face vertical.  Not one line of ``seawall_breaklines`` changes.

VMMC IS THE CONTROL: no constant inset over sea ⇒ the admission is empty
⇒ its breaklines are byte-identical.

Headless: synthetic geometry, production's own functions.
"""

from __future__ import annotations

import sys
from pathlib import Path

from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402

TILE_LAT, TILE_LON = 22, 113


class _Dem:
    def __init__(self, entries=None):
        if entries is not None:
            self.synthetic_flat_site_provenance = list(entries)


class _Tile:
    def __init__(self, dem=None):
        self.lat = TILE_LAT
        self.lon = TILE_LON
        self.dem = dem


def _entry(kind, x0, y0, x1, y1, z0=7.315):
    return {"kind": kind, "icao": "VHHH", "z0_m": z0,
            "extent_tile_degrees": [x0, y0, x1, y1]}


#: A synthetic island and the sea around it, tile-relative degrees.
ISLAND = geometry.box(0.30, 0.30, 0.40, 0.40)
SEA = geometry.box(0.0, 0.0, 1.0, 1.0).difference(ISLAND)
#: The constant inset covering the island (and some water around it).
INSET = (0.28, 0.28, 0.42, 0.42)
#: R17c-3 — the airport's own graded coverage ON the island: what
#: says which land inside the rectangle is the airport's.
COVERAGE = geometry.box(0.34, 0.34, 0.36, 0.36)


class TestTheInsetFootprintIsREAD:
    """It is the stamp DEM prep wrote while BAKING, never a re-derivation:
    a cluster the R11-2 datum check refused is not stamped, and inventing
    it here would claim ground the DEM does not hold at Z0."""

    def test_no_dem_is_the_inert_answer(self):
        assert VMAP.constant_inset_area(_Tile()).is_empty

    def test_no_stamp_is_the_inert_answer(self):
        assert VMAP.constant_inset_area(_Tile(_Dem())).is_empty

    def test_an_empty_stamp_is_the_inert_answer(self):
        assert VMAP.constant_inset_area(_Tile(_Dem([]))).is_empty

    def test_the_airport_extent_is_the_footprint(self):
        area = VMAP.constant_inset_area(
            _Tile(_Dem([_entry("synthetic_flat_site", *INSET)])))
        assert not area.is_empty
        assert area.contains(ISLAND)

    def test_declared_corridors_join_the_footprint_and_clusters_do_not(self):
        """R17c-3 REPLACES R17b-2's enumeration here.

        r17b admitted the claimed-object CLUSTER rectangles too, and
        those are the boxes that reached the mainland (VHHH's 15.11 km²
        HZMB cluster; 66,971 m of wall over 55.47 km² spanning three
        flat sites).  The owner's ruling (2026-08-12) names the
        airport's constant CORE ∪ its DECLARED corridors — so a cluster
        is out of the island reading and still in the BAKED reading
        (``kinds=None``), which is a different question."""
        entries = [
            _entry("synthetic_flat_site", 0.30, 0.30, 0.40, 0.40),
            _entry("synthetic_flat_site_object_cluster",
                   0.50, 0.30, 0.55, 0.35),
            _entry("declared_corridor", 0.40, 0.33, 0.50, 0.34),
        ]
        area = VMAP.constant_inset_area(_Tile(_Dem(entries)))
        assert area.contains(geometry.Point(0.45, 0.335))   # the corridor
        assert not area.contains(geometry.Point(0.52, 0.32))  # the cluster
        baked = VMAP.constant_inset_area(_Tile(_Dem(entries)), kinds=None)
        assert baked.contains(geometry.Point(0.52, 0.32))

    def test_a_malformed_entry_is_skipped_not_fatal(self):
        area = VMAP.constant_inset_area(_Tile(_Dem([
            {"kind": "synthetic_flat_site"},
            {"kind": "synthetic_flat_site", "extent_tile_degrees": [1, 2]},
            _entry("synthetic_flat_site", *INSET),
        ])))
        assert area.contains(ISLAND)


class TestTheCoastlineAdmission:
    def test_it_is_the_LAND_inside_the_inset(self):
        tile = _Tile(_Dem([_entry("synthetic_flat_site", *INSET)]))
        land = VMAP.coastline_wall_admission(tile, SEA, graded_area=COVERAGE)
        assert not land.is_empty
        # The island is admitted; the water inside the inset box is not.
        assert land.contains(geometry.Point(0.35, 0.35))
        assert not land.contains(geometry.Point(0.29, 0.29))

    def test_NO_INSET_NO_ADMISSION(self):
        """The mechanism's own control: with no stamped inset the law
        cannot fire at all.

        MEASURED CAVEAT (2026-08-11, VHHH real-DEM build log).  The
        amendment names VMMC as a byte-identical control on the grounds
        that it has "no constant inset over sea".  On tile +22+113 that
        is FALSE: the detector calls VMMC ``flat_candidate`` at Z0 6.10 m
        and bakes its extent plus two claimed-object cluster insets.
        VMMC is a reclaimed-platform airport too, so this law DOES fire
        there and its breaklines are NOT byte-identical.  Reported to the
        lead; the assertion below is about the mechanism, not about VMMC.
        """
        assert VMAP.coastline_wall_admission(_Tile(), SEA,
                                          graded_area=COVERAGE).is_empty
        assert VMAP.coastline_wall_admission(_Tile(_Dem([])), SEA,
                                          graded_area=COVERAGE).is_empty

    def test_no_sea_means_nothing_to_admit(self):
        tile = _Tile(_Dem([_entry("synthetic_flat_site", *INSET)]))
        assert VMAP.coastline_wall_admission(
            tile, geometry.Polygon(), graded_area=COVERAGE).is_empty


class TestTheWallItself:
    """The admission geometry widens; the breakline law is untouched."""

    def _wall_m(self, admission):
        lines = VMAP.seawall_breaklines(admission, SEA, float(TILE_LAT))
        total = 0.0
        for coords in lines:
            total += geometry.LineString(coords).length
        return len(lines), total

    def test_the_island_coastline_carries_a_wall(self):
        tile = _Tile(_Dem([_entry("synthetic_flat_site", *INSET)]))
        land = VMAP.coastline_wall_admission(tile, SEA, graded_area=COVERAGE)
        n, total = self._wall_m(land)
        assert n >= 1
        # The wall runs right around the island: its length is the
        # island's perimeter, up to the 0.5 m outward offset.
        assert total > 0.9 * ISLAND.exterior.length

    def test_a_small_inland_pavement_alone_carries_none(self):
        """RED BEFORE — the pre-R17b admission.  A patch whose pavement
        does not touch the water admits no coastline wall at all, which
        is the 7.5 %-coverage defect in one assertion."""
        pavement = geometry.box(0.34, 0.34, 0.36, 0.36)
        n, total = self._wall_m(pavement)
        assert n == 0 and total == 0.0

    def test_the_union_is_what_production_hands_the_law(self):
        """The two admissions compose: the patch coverage keeps its own
        wall and the coastline adds the rest."""
        from shapely import ops
        tile = _Tile(_Dem([_entry("synthetic_flat_site", *INSET)]))
        pavement = geometry.box(0.34, 0.34, 0.36, 0.36)
        land = VMAP.coastline_wall_admission(tile, SEA, graded_area=COVERAGE)
        n_union, m_union = self._wall_m(ops.unary_union([pavement, land]))
        n_land, m_land = self._wall_m(land)
        assert n_union == n_land
        assert abs(m_union - m_land) < 1e-9
