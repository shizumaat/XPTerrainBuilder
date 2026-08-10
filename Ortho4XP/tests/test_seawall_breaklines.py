"""SEAWALL AT THE PAVEMENT/WATER EDGE (Round 7, owner 2026-08-10, VMMC).

Charter, owner in-sim at VMMC: "taxiways at the right level, however...
we need a vertical wall drop to water level, otherwise the water itself
is sloping up to the taxiway."

R6-1 made patch pavement LAND (the ring blocks the flood), but the mesh
OUTSIDE the ring still had to descend from deck elevation to sea level
over whatever horizontal run the triangulation gave it — a ramp where
reality has a wall.  The vector map now emits a companion breakline
offset OUTWARD by ``SEAWALL_OFFSET_M`` along exactly the ring segments
that border water, carrying the water's own level and the bare
``INTERP_ALT`` mark.  The mesh then drops deck -> water over 0.5 m.

Pinned here: the offset and its sign, the "land segments emit nothing"
half of the law, the marker's ABSENCE of water-blocking bits (the sea
must keep owning its own foreshore), the altitude of each limb, and the
plumbing that carries the pavement union to both water encoders.  The
R6-1 ring marker is re-pinned against the new insertion: the wall must
not disturb it.

Headless: shapely geometry and a bare ``Vector_Map`` in ``tmp_path``, no
network, no tile build, no Triangle4XP run.
"""
from __future__ import annotations

import inspect
import sys
from math import cos, radians
from pathlib import Path

import numpy
import pytest
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Geo_Utils as GEO  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

ATTR = VECT.Vector_Map.dico_attributes
WATER = ATTR["WATER"]
SEA = ATTR["SEA"]
SEA_EQUIV = ATTR["SEA_EQUIV"]
INTERP_ALT = ATTR["INTERP_ALT"]

TILE_LAT = 22  # VMMC
TILE_LON = 113
# Tile-relative origin the synthetic geometry is laid out around: far
# enough from the tile edges that ``cut_to_tile`` never clips the wall.
ORIGIN = (0.01, 0.01)
M_LAT = GEO.m_to_lat
M_LON = GEO.m_to_lat / cos(radians(TILE_LAT))


def _flood_crosses(segment_mark, flood_attribute):
    """Twin of ``regionplague`` (Triangle4XP.c:13545-13549).

    A flood spreads across a constrained segment unless the segment's
    mark shares a bit with the flood's own attribute.
    """
    return not (segment_mark & flood_attribute)


def box_m(x0, y0, x1, y1):
    """A tile-relative box given in metres east/north of ``ORIGIN``."""
    return geometry.box(
        ORIGIN[0] + x0 * M_LON,
        ORIGIN[1] + y0 * M_LAT,
        ORIGIN[0] + x1 * M_LON,
        ORIGIN[1] + y1 * M_LAT,
    )


def to_m(coords):
    """``(N, 2)`` tile-relative degrees back to metres from ``ORIGIN``."""
    coords = numpy.asarray(coords, dtype=float)
    return numpy.column_stack(
        [
            (coords[:, 0] - ORIGIN[0]) / M_LON,
            (coords[:, 1] - ORIGIN[1]) / M_LAT,
        ]
    )


class _DEM:
    """Flat stand-in for ``tile.dem`` at a non-zero inland water level."""

    LEVEL = 12.5

    def alt_vec(self, way):
        return numpy.full((len(way), 1), self.LEVEL)


class _Tile:
    def __init__(self, lat=TILE_LAT, lon=TILE_LON):
        self.lat = lat
        self.lon = lon
        self.dem = _DEM()
        self.auto_patch = "All"


# ── the constants and the marker ─────────────────────────────────────


class TestSeawallConstants:
    def test_offset_is_half_a_metre(self):
        assert VMAP.SEAWALL_OFFSET_M == 0.5

    def test_sea_limb_sits_at_zero(self):
        assert VMAP.SEAWALL_SEA_LEVEL_M == 0.0

    def test_marker_is_the_bare_interp_alt_idiom(self):
        assert VMAP.SEAWALL_MARKER == INTERP_ALT
        assert VMAP.SEAWALL_MARKER == 8

    def test_marker_carries_no_water_blocking_bits(self):
        # The law: the wall constrains mesh z but the sea may own it.
        assert VMAP.SEAWALL_MARKER & (WATER | SEA | SEA_EQUIV) == 0

    def test_every_water_flood_crosses_the_wall(self):
        for flood in (WATER, SEA, SEA_EQUIV):
            assert _flood_crosses(VMAP.SEAWALL_MARKER, flood)

    def test_the_wall_is_not_the_ring(self):
        # The ring blocks every water flood; the wall blocks none.  Two
        # different jobs, two different markers.
        assert VMAP.SEAWALL_MARKER != VMAP.PATCH_RING_MARKER
        for flood in (WATER, SEA, SEA_EQUIV):
            assert not _flood_crosses(VMAP.PATCH_RING_MARKER, flood)


class TestSeawallOffsetOverride:
    def test_default_without_the_env_var(self, monkeypatch):
        monkeypatch.delenv(VMAP.SEAWALL_OFFSET_ENV, raising=False)
        assert VMAP.seawall_offset_m() == 0.5

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv(VMAP.SEAWALL_OFFSET_ENV, "1.25")
        assert VMAP.seawall_offset_m() == 1.25

    def test_unparseable_override_falls_back(self, monkeypatch):
        monkeypatch.setenv(VMAP.SEAWALL_OFFSET_ENV, "wide")
        assert VMAP.seawall_offset_m() == 0.5

    def test_non_positive_override_never_disables_the_wall(
        self, monkeypatch
    ):
        for raw in ("0", "-3"):
            monkeypatch.setenv(VMAP.SEAWALL_OFFSET_ENV, raw)
            assert VMAP.seawall_offset_m() == 0.5


# ── the geometry ─────────────────────────────────────────────────────


def _half_seaward():
    """A 200x100 m pavement whose southern half lies in the sea."""
    pavement = box_m(0, 0, 200, 100)
    sea = geometry.MultiPolygon([box_m(-500, -500, 700, 50)])
    return (pavement, sea)


class TestSeawallBreaklines:
    def test_seaward_segments_only(self):
        (pavement, sea) = _half_seaward()
        lines = VMAP.seawall_breaklines(pavement, sea, TILE_LAT)
        assert lines
        for coords in lines:
            north = to_m(coords)[:, 1].max()
            # The landward (northern) ring edge is at y = +100 m and its
            # offset curve at +100.5 m: it must contribute nothing.
            assert north <= 50.0 + 1e-6

    def test_the_offset_is_half_a_metre_outward(self):
        (pavement, sea) = _half_seaward()
        lines = VMAP.seawall_breaklines(pavement, sea, TILE_LAT)
        assert lines
        for coords in lines:
            for point in to_m(coords):
                # Outside the pavement, and 0.5 m from its boundary
                # (corners excepted, where the mitre reaches sqrt(2)/2).
                pointm = geometry.Point(point)
                pavement_m = geometry.box(0, 0, 200, 100)
                assert not pavement_m.contains(pointm)
                assert pointm.distance(pavement_m.exterior) <= 0.75
                assert pointm.distance(pavement_m.exterior) >= 0.5 - 1e-6

    def test_a_fully_inland_ring_gets_no_seawall(self):
        pavement = box_m(0, 0, 50, 50)
        far_water = geometry.MultiPolygon([box_m(500, 500, 600, 600)])
        assert VMAP.seawall_breaklines(pavement, far_water, TILE_LAT) == []

    def test_a_corridor_through_the_sea_is_walled_both_sides(self):
        # The VMMC-shaped twin: taxiway C1/G/H, a narrow deck with open
        # water on both flanks.
        corridor = box_m(0, 0, 400, 40)
        sea = geometry.MultiPolygon([box_m(-100, -300, 500, 300)])
        lines = VMAP.seawall_breaklines(corridor, sea, TILE_LAT)
        assert lines
        ys = numpy.concatenate([to_m(coords)[:, 1] for coords in lines])
        assert ys.min() == pytest.approx(-0.5, abs=0.05)
        assert ys.max() == pytest.approx(40.5, abs=0.05)

    def test_the_env_override_widens_the_wall(self, monkeypatch):
        monkeypatch.setenv(VMAP.SEAWALL_OFFSET_ENV, "2.0")
        (pavement, sea) = _half_seaward()
        lines = VMAP.seawall_breaklines(pavement, sea, TILE_LAT)
        assert lines
        ys = numpy.concatenate([to_m(coords)[:, 1] for coords in lines])
        assert ys.min() == pytest.approx(-2.0, abs=0.05)

    def test_explicit_offset_beats_the_environment(self, monkeypatch):
        monkeypatch.setenv(VMAP.SEAWALL_OFFSET_ENV, "2.0")
        (pavement, sea) = _half_seaward()
        lines = VMAP.seawall_breaklines(
            pavement, sea, TILE_LAT, offset_m=1.0
        )
        ys = numpy.concatenate([to_m(coords)[:, 1] for coords in lines])
        assert ys.min() == pytest.approx(-1.0, abs=0.05)

    def test_a_hole_in_the_pavement_is_walled_inward(self):
        # "Outward" means away from the pavement, which for an enclosed
        # pond means INTO the hole.
        outer = box_m(0, 0, 200, 200)
        pond = box_m(80, 80, 120, 120)
        pavement = outer.difference(pond)
        water = geometry.MultiPolygon([pond])
        lines = VMAP.seawall_breaklines(pavement, water, TILE_LAT)
        assert lines
        points = numpy.concatenate([to_m(coords) for coords in lines])
        assert points[:, 0].min() == pytest.approx(80.5, abs=0.05)
        assert points[:, 0].max() == pytest.approx(119.5, abs=0.05)

    def test_empty_and_missing_inputs_are_no_ops(self):
        (pavement, sea) = _half_seaward()
        assert VMAP.seawall_breaklines(None, sea, TILE_LAT) == []
        assert VMAP.seawall_breaklines(pavement, None, TILE_LAT) == []
        assert (
            VMAP.seawall_breaklines(geometry.Polygon(), sea, TILE_LAT) == []
        )
        assert (
            VMAP.seawall_breaklines(
                pavement, geometry.MultiPolygon(), TILE_LAT
            )
            == []
        )

    def test_a_broken_geometry_never_costs_the_water_encoding(self):
        (pavement, sea) = _half_seaward()

        class _Broken:
            is_empty = False
            bounds = (-1.0, -1.0, 1.0, 1.0)

        assert VMAP.seawall_breaklines(_Broken(), sea, TILE_LAT) == []
        assert VMAP.seawall_breaklines(pavement, _Broken(), TILE_LAT) == []


# ── insertion into the vector map ────────────────────────────────────


class TestInsertSeawalls:
    def test_sea_limb_inserts_bare_interp_alt_edges_at_zero(self):
        (pavement, sea) = _half_seaward()
        vector_map = VECT.Vector_Map()
        tile = _Tile()
        count = VMAP.insert_seawalls(vector_map, tile, pavement, sea)
        assert count >= 1
        markers = set(vector_map.data_edges.values())
        assert markers == {VMAP.SEAWALL_MARKER}
        assert set(vector_map.data_nodes.values()) == {0.0}

    def test_inland_limb_takes_the_water_level_the_map_knows(self):
        pavement = box_m(0, 0, 200, 100)
        lake = geometry.MultiPolygon([box_m(-500, -500, 700, 50)])
        vector_map = VECT.Vector_Map()
        tile = _Tile()
        count = VMAP.insert_seawalls(
            vector_map, tile, pavement, lake, alt_vec=tile.dem.alt_vec
        )
        assert count >= 1
        assert set(vector_map.data_nodes.values()) == {_DEM.LEVEL}

    def test_a_fully_inland_ring_inserts_nothing(self):
        vector_map = VECT.Vector_Map()
        count = VMAP.insert_seawalls(
            vector_map,
            _Tile(),
            box_m(0, 0, 50, 50),
            geometry.MultiPolygon([box_m(500, 500, 600, 600)]),
        )
        assert count == 0
        assert not vector_map.data_edges
        assert not vector_map.data_nodes

    def test_no_pavement_union_is_a_no_op(self):
        vector_map = VECT.Vector_Map()
        (_pavement, sea) = _half_seaward()
        assert VMAP.insert_seawalls(vector_map, _Tile(), None, sea) == 0
        assert not vector_map.data_edges

    def test_the_sea_limb_wins_where_the_limbs_overlap(self):
        # Node identity is by coordinate, and include_sea runs first.
        (pavement, sea) = _half_seaward()
        vector_map = VECT.Vector_Map()
        tile = _Tile()
        VMAP.insert_seawalls(vector_map, tile, pavement, sea)
        VMAP.insert_seawalls(
            vector_map, tile, pavement, sea, alt_vec=tile.dem.alt_vec
        )
        assert set(vector_map.data_nodes.values()) == {0.0}


# ── the R6-1 ring is untouched by the wall ───────────────────────────


class TestRingMarkerSurvivesTheWall:
    def test_the_ring_keeps_the_full_marker_and_the_wall_is_separate(self):
        pavement = box_m(0, 0, 200, 100)
        sea = geometry.MultiPolygon([box_m(-500, -500, 700, 50)])
        vector_map = VECT.Vector_Map()
        tile = _Tile()
        ring = numpy.array(pavement.exterior.coords, dtype=float)
        alti = numpy.full((len(ring), 1), 4.0)
        vector_map.insert_way(
            numpy.hstack([ring, alti]), VMAP.PATCH_RING_MARKER, check=True
        )
        ring_edges_before = sum(
            1
            for marker in vector_map.data_edges.values()
            if marker == VMAP.PATCH_RING_MARKER
        )
        assert ring_edges_before == 4
        VMAP.insert_seawalls(vector_map, tile, pavement, sea)
        markers = list(vector_map.data_edges.values())
        # The wall runs 0.5 m clear of the ring: it neither splits the
        # ring's edges nor ORs itself into them.
        assert markers.count(VMAP.PATCH_RING_MARKER) == ring_edges_before
        assert markers.count(VMAP.SEAWALL_MARKER) >= 1
        assert set(markers) == {
            VMAP.PATCH_RING_MARKER,
            VMAP.SEAWALL_MARKER,
        }
        # And the deck altitude is untouched by the wall's zeros.
        assert 4.0 in set(vector_map.data_nodes.values())
        assert 0.0 in set(vector_map.data_nodes.values())


# ── the plumbing ─────────────────────────────────────────────────────


class TestSeawallPlumbing:
    def test_include_sea_walls_the_sea_seed_area(self):
        source = " ".join(inspect.getsource(VMAP.include_sea).split())
        assert (
            "insert_seawalls(vector_map, tile, patches_area, seed_area)"
            in source
        )

    def test_include_water_accepts_the_pavement_union(self):
        parameters = inspect.signature(VMAP.include_water).parameters
        assert "patches_area" in parameters
        assert parameters["patches_area"].default is None

    def test_include_water_walls_both_mapped_water_families(self):
        source = " ".join(inspect.getsource(VMAP.include_water).split())
        assert "for inland_area in (water_area, sea_equiv_area):" in source
        assert "alt_vec=tile.dem.alt_vec," in source

    def test_build_poly_file_forwards_the_union_to_the_water(self):
        source = " ".join(inspect.getsource(VMAP.build_poly_file).split())
        assert (
            "include_water(vector_map, tile, patches_area=patches_area)"
            in source
        )
        # R6-1's forwarding to the sea is unchanged.
        assert (
            "include_sea(vector_map, tile, patches_area=patches_area)"
            in source
        )
