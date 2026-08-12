"""PATCH PAVEMENT IS LAND (owner 2026-08-10, VMMC).

Pavement that is in our patch must never come out water.  VMMC's
taxiways C1/G/H are OSM ``bridge=yes`` viaducts over real open water:
113,414 m2 of patch pavement lies seaward of the coastline, and the
built tile carried 263 mesh triangles / 114,406 m2 of ``SEA|INTERP_ALT``
(attr 10) over pavement — wet texture and transparent mask on a surface
the patch had levelled.

Root cause: closed patch rings were inserted with the ``INTERP_ALT``
marker ALONE (bit 8), and Triangle4XP's ``regionplague``
(Triangle4XP.c:13545-13549) crosses any segment whose mark does not
share a bit with the flood's own attribute — an elevation ring does not
stop a SEA flood.  The fix inserts closed patch pavement rings with
``INTERP_ALT | WATER | SEA | SEA_EQUIV`` (15) and withholds sea seeds
from the patch pavement union.

REGRESSION PIN: genuine road bridges over water (road ribbons and OBJ8
patch objects, both still bare ``INTERP_ALT``) must KEEP their water —
the tile's 36,410 ``WATER|INTERP_ALT`` (attr 9) triangles do not dry
out.

Headless: synthetic patch file in ``tmp_path``, no network, no tile
build, no Triangle4XP run — the flood rule and the attribute arithmetic
are asserted as twins of the C and of the classifiers.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_DSF_Utils as DSF  # noqa: E402
import O4_Mask_Utils as MASK  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

ATTR = VECT.Vector_Map.dico_attributes
WATER = ATTR["WATER"]
SEA = ATTR["SEA"]
SEA_EQUIV = ATTR["SEA_EQUIV"]
INTERP_ALT = ATTR["INTERP_ALT"]


# ── twins of Triangle4XP ─────────────────────────────────────────────


def _flood_crosses(segment_mark, flood_attribute):
    """Twin of ``regionplague`` (Triangle4XP.c:13545-13549).

    A flood spreads across a constrained segment unless the segment's
    mark shares a bit with the flood's own attribute.
    """
    return not (segment_mark & flood_attribute)


def _triangle_attribute(flood_attributes):
    """Twin of ``setelemattribute`` (Triangle4XP.c:1225).

    Triangle attributes are the OR of the floods that reached the
    triangle.  Segment marks are NOT triangle attributes: a ring marked
    15 leaves its interior at the seed's own bits.
    """
    attr = 0
    for flood in flood_attributes:
        attr |= flood
    return attr


# ── the marker ───────────────────────────────────────────────────────


class TestPatchRingMarker:
    def test_marker_carries_all_three_water_bits_and_interp_alt(self):
        assert VMAP.PATCH_RING_MARKER == (
            INTERP_ALT | WATER | SEA | SEA_EQUIV
        )
        assert VMAP.PATCH_RING_MARKER == 15

    def test_the_ring_blocks_every_water_flood(self):
        for flood in (WATER, SEA, SEA_EQUIV, INTERP_ALT):
            assert not _flood_crosses(VMAP.PATCH_RING_MARKER, flood)

    def test_the_old_interp_alt_ring_did_not_stop_the_sea(self):
        # The root cause, pinned: bit 8 alone blocks only its own flood.
        assert _flood_crosses(INTERP_ALT, SEA)
        assert _flood_crosses(INTERP_ALT, WATER)
        assert _flood_crosses(INTERP_ALT, SEA_EQUIV)
        assert not _flood_crosses(INTERP_ALT, INTERP_ALT)

    def test_interior_keeps_the_seed_bits_only(self):
        # Inside a patch ring the SEA flood never arrives, so the
        # triangle carries the INTERP_ALT seed's bit alone (8), not 10.
        assert _triangle_attribute([INTERP_ALT]) == 8
        # What the same interior scored BEFORE the ring blocked the sea:
        assert _triangle_attribute([INTERP_ALT, SEA]) == 10


# ── the classifiers read attr 8 as land ──────────────────────────────


class TestWaterClassificationArithmetic:
    def test_interp_alt_only_is_land_in_the_dsf(self):
        assert DSF.remap_water_tri_type(INTERP_ALT, False) == 0
        assert DSF.remap_water_tri_type(INTERP_ALT, True) == 0

    def test_sea_interp_alt_is_never_land(self):
        # attr 10 always classifies as sea (class 2) — which is exactly
        # why the ring, not a classifier tweak, is the fix.
        assert DSF.remap_water_tri_type(SEA | INTERP_ALT, False) == 2
        assert DSF.remap_water_tri_type(SEA | INTERP_ALT, True) == 2

    def test_water_interp_alt_is_unchanged_inland_water(self):
        # attr 9: the genuine road bridge over inland water.
        assert DSF.remap_water_tri_type(WATER | INTERP_ALT, False) == 1
        assert DSF.remap_water_tri_type(WATER | INTERP_ALT, True) == 2

    def test_mask_side_reads_the_same_bits(self):
        has_water = 7
        assert not MASK.water_type_is_inland(INTERP_ALT & has_water)
        assert MASK.water_type_is_inland((WATER | INTERP_ALT) & has_water)
        assert not MASK.water_type_is_inland((SEA | INTERP_ALT) & has_water)


# ── include_patches: what gets inserted ──────────────────────────────


class _DEM:
    """Flat stand-in for ``tile.dem`` — one altitude per way node."""

    def alt_vec(self, way):
        return numpy.zeros((len(way), 1))


class _Tile:
    def __init__(self, lat=30, lon=30):
        self.lat = lat
        self.lon = lon
        self.dem = _DEM()
        self.auto_patch = "All"


def _write_patch_file(patch_dir, lat=30, lon=30):
    """One closed pavement ring (cst_alt_abs) + one open way."""
    ring = [
        (lon + 0.0010, lat + 0.0010),
        (lon + 0.0030, lat + 0.0010),
        (lon + 0.0030, lat + 0.0030),
        (lon + 0.0010, lat + 0.0030),
        (lon + 0.0010, lat + 0.0010),
    ]
    open_way = [
        (lon + 0.0060, lat + 0.0060),
        (lon + 0.0080, lat + 0.0060),
    ]
    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "<osm version='0.6' upload='true' generator='test'>",
    ]
    node_id = -10
    ring_nodes = []
    for (x, y) in ring[:-1]:
        lines.append(
            "  <node id='{}' action='modify' visible='true'"
            " lat='{:.10f}' lon='{:.10f}' />".format(node_id, y, x)
        )
        ring_nodes.append(node_id)
        node_id -= 2
    open_nodes = []
    for (x, y) in open_way:
        lines.append(
            "  <node id='{}' action='modify' visible='true'"
            " lat='{:.10f}' lon='{:.10f}' />".format(node_id, y, x)
        )
        open_nodes.append(node_id)
        node_id -= 2
    lines.append("  <way id='-100' action='modify' visible='true'>")
    for ref in ring_nodes + [ring_nodes[0]]:
        lines.append("    <nd ref='{}' />".format(ref))
    lines.append("    <tag k='cst_alt_abs' v='75' />")
    lines.append("  </way>")
    lines.append("  <way id='-102' action='modify' visible='true'>")
    for ref in open_nodes:
        lines.append("    <nd ref='{}' />".format(ref))
    lines.append("    <tag k='cst_alt_abs' v='75' />")
    lines.append("  </way>")
    lines.append("</osm>")
    (patch_dir / "TEST_runways.patch.osm").write_text("\n".join(lines))
    return (ring, open_way)


def _run_include_patches(tmp_path, monkeypatch):
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    tile = _Tile()
    (ring, _open_way) = _write_patch_file(patch_dir, tile.lat, tile.lon)
    monkeypatch.setattr(
        VMAP.FNAMES, "patch_dir", lambda lat, lon: str(patch_dir)
    )
    vector_map = VECT.Vector_Map()
    # R17-3 added the role-scoped seawall admission union as a third
    # return value; the LAND authority this file is about is unchanged.
    (patches_area, patches_list, _graded) = VMAP.include_patches(
        vector_map, tile)
    return (vector_map, patches_area, patches_list, ring, tile)


class TestIncludePatchesInsertion:
    def test_closed_ring_edges_carry_the_full_marker(
        self, tmp_path, monkeypatch
    ):
        (vector_map, _area, _list, _ring, _tile) = _run_include_patches(
            tmp_path, monkeypatch
        )
        markers = [
            vector_map.data_edges[edge_id]
            for edge_id in vector_map.edges_dico
        ]
        ring_markers = [m for m in markers if m]
        assert len(ring_markers) == 4
        for marker in ring_markers:
            assert marker & INTERP_ALT
            assert marker & WATER
            assert marker & SEA
            assert marker & SEA_EQUIV
            assert marker == VMAP.PATCH_RING_MARKER

    def test_open_ways_stay_dummy(self, tmp_path, monkeypatch):
        (vector_map, _area, _list, _ring, _tile) = _run_include_patches(
            tmp_path, monkeypatch
        )
        markers = [
            vector_map.data_edges[edge_id]
            for edge_id in vector_map.edges_dico
        ]
        assert markers.count(ATTR["DUMMY"]) == 1

    def test_the_seed_stays_interp_alt(self, tmp_path, monkeypatch):
        # The marker change must not mint water SEEDS: only the ring
        # marks change, the interior is still seeded INTERP_ALT alone.
        (vector_map, _area, _list, _ring, _tile) = _run_include_patches(
            tmp_path, monkeypatch
        )
        assert set(vector_map.seeds) == {"INTERP_ALT"}
        assert len(vector_map.seeds["INTERP_ALT"]) == 1

    def test_patches_area_is_the_pavement_union(
        self, tmp_path, monkeypatch
    ):
        (_vm, patches_area, _list, ring, tile) = _run_include_patches(
            tmp_path, monkeypatch
        )
        assert not patches_area.is_empty
        local_ring = [(x - tile.lon, y - tile.lat) for (x, y) in ring]
        assert patches_area.contains(
            geometry.Polygon(local_ring).representative_point()
        )

    def test_altitude_survives_the_marker_change(
        self, tmp_path, monkeypatch
    ):
        # cst_alt_abs=75 against a zero DEM: the ring nodes still carry
        # the patch altitude (the marker is an EDGE attribute).
        (vector_map, _area, _list, _ring, _tile) = _run_include_patches(
            tmp_path, monkeypatch
        )
        assert set(vector_map.data_nodes.values()) == {75.0}


# ── regression pin: bridges over water keep their water ──────────────


class TestGenuineWaterIsUntouched:
    def test_road_ribbons_keep_the_bare_interp_alt_marker(self):
        # include_roads encodes road ribbons with "INTERP_ALT"
        # (O4_Vector_Map:966) and keep_obj8 inserts OBJ8 patch-object
        # edges with the same bare attribute — neither is a patch
        # pavement ring, so both stay at 8 and water floods across
        # them exactly as before.
        assert ATTR["INTERP_ALT"] == 8
        assert _flood_crosses(ATTR["INTERP_ALT"], WATER)
        assert _flood_crosses(ATTR["INTERP_ALT"], SEA)

    def test_a_road_bridge_over_water_still_scores_attr_9(self):
        attr = _triangle_attribute([INTERP_ALT, WATER])
        assert attr == 9
        assert DSF.remap_water_tri_type(attr, False) == 1
        assert MASK.water_type_is_inland(attr & 7)


# ── belt and braces: no sea seed inside patch pavement ───────────────


def _sea_and_pavement():
    """A sea polygon whose representative point lands on pavement."""
    sea = geometry.MultiPolygon([geometry.box(0.0, 0.0, 1.0, 1.0)])
    pavement = geometry.box(0.2, 0.2, 0.8, 0.8)
    return (sea, pavement)


class TestSeaSeedsAvoidPatchPavement:
    def test_no_seed_lands_inside_pavement(self):
        (sea, pavement) = _sea_and_pavement()
        seed_area = VMAP.sea_seed_areas(
            sea, None, patch_pavement_area=pavement
        )
        assert not seed_area.is_empty
        for piece in seed_area.geoms:
            assert not pavement.contains(piece.representative_point())

    def test_both_subtractors_apply_together(self):
        (sea, pavement) = _sea_and_pavement()
        lagoon = geometry.box(0.0, 0.85, 1.0, 1.0)
        seed_area = VMAP.sea_seed_areas(
            sea, lagoon, patch_pavement_area=pavement
        )
        for piece in seed_area.geoms:
            point = piece.representative_point()
            assert not pavement.contains(point)
            assert not lagoon.contains(point)

    def test_absent_pavement_changes_nothing(self):
        (sea, _pavement) = _sea_and_pavement()
        assert VMAP.sea_seed_areas(sea, None, None) is sea
        assert (
            VMAP.sea_seed_areas(sea, None, geometry.Polygon()) is sea
        )

    def test_a_broken_pavement_union_never_costs_the_coastline(self):
        (sea, _pavement) = _sea_and_pavement()

        class _Broken:
            is_empty = False

        assert VMAP.sea_seed_areas(sea, None, _Broken()) is sea

    def test_a_broken_pavement_union_keeps_the_tidal_subtraction(self):
        (sea, _pavement) = _sea_and_pavement()
        lagoon = geometry.box(0.0, 0.85, 1.0, 1.0)

        class _Broken:
            is_empty = False

        seed_area = VMAP.sea_seed_areas(sea, lagoon, _Broken())
        for piece in seed_area.geoms:
            assert not lagoon.contains(piece.representative_point())

    def test_fully_paved_sea_yields_no_seeds(self):
        sea = geometry.MultiPolygon([geometry.box(0.0, 0.0, 1.0, 1.0)])
        seed_area = VMAP.sea_seed_areas(
            sea, None, patch_pavement_area=geometry.box(0, 0, 1, 1)
        )
        assert seed_area.is_empty


# ── the plumbing that carries the pavement union to the sea ──────────


class TestPavementUnionReachesTheSeeding:
    def test_include_sea_accepts_the_pavement_union(self):
        parameters = inspect.signature(VMAP.include_sea).parameters
        assert "patches_area" in parameters
        assert parameters["patches_area"].default is None

    def test_build_poly_file_forwards_the_union_to_the_sea(self):
        # The union is the LAND authority and must reach include_sea
        # SEPARATELY from treated_area (which also carries the apt.dat
        # runway/taxiway/apron area — a cutter the law forbids).
        source = " ".join(
            inspect.getsource(VMAP.build_poly_file).split()
        )
        assert (
            "(apt_array, apt_area, patches_area, graded_area) ="
            " include_airports( vector_map, tile)" in source
        )
        assert (
            "include_sea(vector_map, tile, patches_area=patches_area,"
            " graded_area=graded_area)" in source
        )

    def test_include_airports_without_airports_returns_an_empty_union(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            VMAP, "load_airports_and_prepare_dem", lambda tile: (None, None)
        )
        result = VMAP.include_airports(VECT.Vector_Map(), _Tile())
        # R17-3: (apt_array, treated_area, patches_area, graded_area).
        assert len(result) == 4
        assert result[2].is_empty
        assert result[3].is_empty
