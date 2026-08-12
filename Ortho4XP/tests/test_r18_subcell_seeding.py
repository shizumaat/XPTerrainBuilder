"""R18-1 — EVERY ROAD-CUT SUB-CELL OF A PATCH FACE GETS ITS SEED.

``include_patches`` seeds one INTERP_ALT point per planar FACE of the
patch coverage, polygonizing the patch RING boundaries.  Triangle4XP's
regionplague is blocked by ANY segment carrying the same attribute bit,
and the patch rings are not the only INTERP_ALT geometry on a tile:
``include_roads`` encodes the buffered banked road network with the very
same marker, several steps LATER.  A road ribbon crossing a patch face
therefore cuts it into sub-cells the per-face seeding never saw, and an
unseeded sub-cell keeps the raw DEM altitude inside a patched apron.

MEASURED (HECA +30+031, 2026-08-11): the 339,000 m² apron face is cut by
40 road lines into 38 cells, the seed sits in cell #9, and the owner's
point at 30.1170578,31.4098155 sits in cell #3 whose one interior vertex
keeps 99.33 m inside an 86 m apron.

Headless: synthetic geometry through production's own
``O4_Vector_Utils.Vector_Map`` and ``O4_Vector_Map.seed_interp_alt_subcells``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
import pytest
from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

INTERP_ALT = VECT.Vector_Map.dico_attributes["INTERP_ALT"]
DUMMY = VECT.Vector_Map.dico_attributes["DUMMY"]

#: A 1 km-ish square patch face, in tile-relative degrees.
PATCH_RING = [(0.10, 0.10), (0.20, 0.10), (0.20, 0.20), (0.10, 0.20),
              (0.10, 0.10)]
#: A road ribbon straight across its middle, wall to wall.
ROAD_RIBBON = [(0.05, 0.148), (0.25, 0.148), (0.25, 0.152),
               (0.05, 0.152), (0.05, 0.148)]


def _vector_map_with_patch_face(road=None, seeded=True):
    """A vector map carrying one patch ring, optionally cut by a road
    ribbon, staged exactly as ``build_poly_file`` stages it: the patch
    ring encoded and per-FACE seeded first, the road encoded after."""
    vector_map = VECT.Vector_Map()
    patch_polygon = geometry.Polygon(PATCH_RING)

    def _encode(ring, marker):
        ids = [vector_map.insert_node(x, y, 0.0) for (x, y) in ring[:-1]]
        for index in range(len(ids)):
            vector_map.insert_edge(
                ids[index], ids[(index + 1) % len(ids)], marker, check=True)

    _encode(PATCH_RING, INTERP_ALT)
    # What include_patches leaves behind for the sub-cell pass.
    vector_map.interp_alt_patch_polygons = [patch_polygon]
    vector_map.interp_alt_patches_area = patch_polygon
    if seeded:
        # The historical per-FACE seed: one point, in whichever sub-cell
        # it happens to fall.  Put it deliberately in the SOUTH half.
        vector_map.seeds["INTERP_ALT"] = [numpy.array([0.15, 0.12])]
    if road is not None:
        _encode(road, INTERP_ALT)
    return vector_map, patch_polygon


def _seed_points(vector_map):
    return [geometry.Point(seed[0], seed[1])
            for seed in vector_map.seeds.get("INTERP_ALT", [])]


class TestRoadCutSubCells:
    def test_a_road_cut_face_gets_both_sub_cells_seeded(self):
        vector_map, patch_polygon = _vector_map_with_patch_face(ROAD_RIBBON)
        # BEFORE: one seed, and the north sub-cell has none — that IS the
        # defect (its triangles keep the raw DEM).
        north = geometry.box(0.10, 0.152, 0.20, 0.20)
        south = geometry.box(0.10, 0.10, 0.20, 0.148)
        assert not any(north.contains(p) for p in _seed_points(vector_map))
        assert any(south.contains(p) for p in _seed_points(vector_map))

        added = VMAP.seed_interp_alt_subcells(vector_map)

        assert added >= 1
        seeds = _seed_points(vector_map)
        assert any(north.contains(p) for p in seeds), "north sub-cell unseeded"
        assert any(south.contains(p) for p in seeds), "south seed lost"
        # Every seed still lies inside the patch coverage — a seed
        # outside it would flood ground the patch does not own.
        assert all(patch_polygon.contains(p) for p in seeds)

    def test_the_existing_face_seed_is_never_duplicated(self):
        # Purely additive: the sub-cell already holding the historical
        # seed gets no second one.
        vector_map, _polygon = _vector_map_with_patch_face(ROAD_RIBBON)
        VMAP.seed_interp_alt_subcells(vector_map)
        south = geometry.box(0.10, 0.10, 0.20, 0.148)
        assert sum(1 for p in _seed_points(vector_map)
                   if south.contains(p)) == 1

    def test_an_uncut_face_is_left_byte_identical(self):
        # THE INERTNESS CONTROL: a patch face no INTERP_ALT ribbon
        # crosses must come out of this pass unchanged, so a tile
        # without roads over its patches keeps its historical seeding.
        vector_map, _polygon = _vector_map_with_patch_face(road=None)
        before = [tuple(seed) for seed in vector_map.seeds["INTERP_ALT"]]
        added = VMAP.seed_interp_alt_subcells(vector_map)
        assert added == 0
        assert [tuple(s) for s in vector_map.seeds["INTERP_ALT"]] == before

    def test_a_DUMMY_ribbon_does_not_cut_a_cell(self):
        # Only geometry carrying the INTERP_ALT BIT blocks the flood, so
        # only that geometry defines a sub-cell.  A DUMMY ribbon (the
        # gluing network, the cplx-way diagonals) must not mint seeds.
        vector_map, _polygon = _vector_map_with_patch_face(road=None)
        ids = [vector_map.insert_node(x, y, 0.0) for (x, y) in ROAD_RIBBON[:-1]]
        for index in range(len(ids)):
            vector_map.insert_edge(
                ids[index], ids[(index + 1) % len(ids)], DUMMY, check=True)
        assert VMAP.seed_interp_alt_subcells(vector_map) == 0

    def test_three_ribbons_give_every_strip_a_seed(self):
        # Generalisation of the measured HECA shape: N parallel ribbons
        # cut the face into N+1 strips and every strip must be seeded.
        ribbons = [
            [(0.05, y), (0.25, y), (0.25, y + 0.004), (0.05, y + 0.004),
             (0.05, y)]
            for y in (0.125, 0.148, 0.172)]
        vector_map, patch_polygon = _vector_map_with_patch_face(ribbons[0])
        for ribbon in ribbons[1:]:
            ids = [vector_map.insert_node(x, y, 0.0) for (x, y) in ribbon[:-1]]
            for index in range(len(ids)):
                vector_map.insert_edge(
                    ids[index], ids[(index + 1) % len(ids)], INTERP_ALT,
                    check=True)
        VMAP.seed_interp_alt_subcells(vector_map)
        seeds = _seed_points(vector_map)
        strips = [geometry.box(0.10, lo, 0.20, hi) for lo, hi in
                  ((0.100, 0.125), (0.129, 0.148), (0.152, 0.172),
                   (0.176, 0.200))]
        for index, strip in enumerate(strips):
            assert any(strip.contains(p) for p in seeds), (
                f"strip {index} unseeded")

    def test_no_patch_polygons_is_a_no_op(self):
        # Guards the attribute-absent path (a direct include_patches
        # caller, an early return, a tile with no patch dir).
        assert VMAP.seed_interp_alt_subcells(VECT.Vector_Map()) == 0

    def test_a_failure_never_breaks_the_build(self, monkeypatch):
        # The historical per-face seeds already stand; this pass is a
        # refinement and must degrade to a no-op, never raise.
        vector_map, _polygon = _vector_map_with_patch_face(ROAD_RIBBON)
        before = list(vector_map.seeds["INTERP_ALT"])

        def _boom(*args, **kwargs):
            raise RuntimeError("synthetic polygonize failure")

        monkeypatch.setattr(VMAP.ops, "polygonize", _boom)
        assert VMAP.seed_interp_alt_subcells(vector_map) == 0
        assert len(vector_map.seeds["INTERP_ALT"]) == len(before)


class TestSeedsStayInsideTheCoverage:
    def test_a_ribbon_running_past_the_face_seeds_nothing_outside(self):
        # The road ribbon extends well beyond the patch ring (it does in
        # production — the buffered network spans the tile).  The faces
        # it forms outside the coverage must NOT be seeded: INTERP_ALT
        # out there would level ground the patch does not own.
        vector_map, patch_polygon = _vector_map_with_patch_face(ROAD_RIBBON)
        VMAP.seed_interp_alt_subcells(vector_map)
        outside = [p for p in _seed_points(vector_map)
                   if not patch_polygon.contains(p)]
        assert outside == [], f"{len(outside)} seed(s) outside the coverage"


@pytest.mark.parametrize("marker_name", ["INTERP_ALT"])
def test_no_new_marker_semantics(marker_name):
    # The spec is explicit: follow the existing seeding idiom, no new
    # marker.  The sub-cell seeds land in the SAME list under the SAME
    # key, and no new attribute is minted.
    vector_map, _polygon = _vector_map_with_patch_face(ROAD_RIBBON)
    VMAP.seed_interp_alt_subcells(vector_map)
    assert set(vector_map.seeds) == {marker_name}
    assert "INTERP_ALT" in VECT.Vector_Map.dico_attributes
