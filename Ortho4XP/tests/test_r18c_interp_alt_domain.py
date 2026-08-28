"""R18-1c — THE PATCH VALUE STOPS AT THE PATCH.

The CYXY round (owner sim read 2026-08-28,
``docs/specs/cyxy-interp-alt-flood-leak-spec.md``): the +60-136 mesh
carried a 700 m airport bench 500 m out into Whitehorse, then a 63.7 m
one-triangle cliff, because R18-1b harmonic-extended the CYXY patch ring
altitudes over the WHOLE connected attr==8 sub-mesh — and
``include_roads`` marks the banked road network with the same
INTERP_ALT bit, so that sub-mesh was the town's road network, 10.2 km
wide against a 1.94 km^2 patch coverage.

Two laws are asserted here, both headless and synthetic:

* the SEALING PREDICATE (``O4_Vector_Map.audit_interp_alt_seed_sealing``)
  — the spec's own hypothesis, kept as a guard: an INTERP_ALT seed must
  sit in a BOUNDED face of the INTERP_ALT edge arrangement, or
  Triangle4XP's plague floods the whole uncut land component (the VMMC
  class).  It PASSES on the real +60-136 inputs, which is how that
  hypothesis was refuted; it must still refuse a genuinely unsealed one.
* the DOMAIN SCOPE (``O4_Mesh_Utils.triangles_inside_coverage`` and
  ``audit_interp_alt_extent``) — the interpolation's domain is the patch
  coverage, and a vertex it moved outside that coverage is a REFUSAL,
  never a silent clip.
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
TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import O4_Mesh_Utils as MESH  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402

STRIDE = 6


# ── one spelling of the two markers, everywhere ───────────────────────
def test_the_three_spellings_of_PATCH_RING_MARKER_agree():
    import mesh_region_tris

    assert VMAP.PATCH_RING_MARKER == MESH.PATCH_RING_MARKER == 15
    assert mesh_region_tris.PATCH_RING_MARKER == VMAP.PATCH_RING_MARKER
    assert (mesh_region_tris.INTERP_ALT_BIT
            == VECT.Vector_Map.dico_attributes["INTERP_ALT"] == 8)


# ── the sealing predicate ─────────────────────────────────────────────
def square(vector_map, x0, y0, side, marker):
    """Insert a closed square way carrying ``marker``."""
    ring = numpy.array([
        [x0, y0, 0.0], [x0 + side, y0, 0.0],
        [x0 + side, y0 + side, 0.0], [x0, y0 + side, 0.0], [x0, y0, 0.0]])
    vector_map.insert_way(ring, marker, check=True)


def map_with_ring(seed_xy, marker=None):
    vector_map = VECT.Vector_Map()
    marker = (VMAP.PATCH_RING_MARKER if marker is None else marker)
    square(vector_map, 0.10, 0.10, 0.05, marker)
    vector_map.seeds["INTERP_ALT"] = [numpy.array(seed_xy)]
    return vector_map


class TestSealingPredicate:
    def test_a_seed_inside_its_ring_passes(self):
        vector_map = map_with_ring((0.125, 0.125))
        assert VMAP.audit_interp_alt_seed_sealing(vector_map) == 1

    def test_a_seed_OUTSIDE_its_ring_refuses(self):
        vector_map = map_with_ring((0.400, 0.400))
        with pytest.raises(VMAP.UnsealedInterpAltSeed) as caught:
            VMAP.audit_interp_alt_seed_sealing(vector_map)
        assert "UNSEALED" in str(caught.value)
        assert "0.400000000" in str(caught.value)

    def test_a_ring_that_LOST_its_bit_8_mark_refuses(self):
        # The spec's hypothesised mechanism: the ring is there, the mark
        # is not, so nothing blocks the plague.  WATER|SEA|SEA_EQUIV is
        # PATCH_RING_MARKER with bit 8 taken out.
        vector_map = map_with_ring((0.125, 0.125), marker=7)
        with pytest.raises(VMAP.UnsealedInterpAltSeed):
            VMAP.audit_interp_alt_seed_sealing(vector_map)

    def test_warn_mode_does_not_raise(self, monkeypatch):
        monkeypatch.setenv(VMAP.INTERP_ALT_SEAL_ENV, "warn")
        vector_map = map_with_ring((0.400, 0.400))
        assert VMAP.audit_interp_alt_seed_sealing(vector_map) == 1

    def test_no_seeds_is_a_no_op(self):
        assert VMAP.audit_interp_alt_seed_sealing(VECT.Vector_Map()) == 0

    def test_a_ROAD_RIBBON_ring_seals_its_own_seed(self):
        # include_roads marks the banked road buffers INTERP_ALT and
        # seeds each one: lawful, and it must not read as a leak.
        vector_map = VECT.Vector_Map()
        square(vector_map, 0.10, 0.10, 0.05, VMAP.PATCH_RING_MARKER)
        square(vector_map, 0.40, 0.40, 0.02,
               VECT.Vector_Map.dico_attributes["INTERP_ALT"])
        vector_map.seeds["INTERP_ALT"] = [numpy.array((0.125, 0.125)),
                                          numpy.array((0.410, 0.410))]
        assert VMAP.audit_interp_alt_seed_sealing(vector_map) == 2


# ── the domain scope ──────────────────────────────────────────────────
def vertices_from(points):
    array = numpy.zeros(STRIDE * len(points))
    for index, (x, y) in enumerate(points):
        array[STRIDE * index] = x
        array[STRIDE * index + 1] = y
    return array


COVERAGE = geometry.box(0.0, 0.0, 1.0, 1.0)


def prepared_coverage():
    from shapely.prepared import prep

    return prep(COVERAGE)


class TestTrianglesInsideCoverage:
    def test_a_wholly_interior_triangle_is_kept(self):
        vertices = vertices_from([(0.2, 0.2), (0.8, 0.2), (0.5, 0.8)])
        assert MESH.triangles_inside_coverage(
            vertices, [(0, 1, 2)], prepared_coverage()) == [(0, 1, 2)]

    def test_a_triangle_ON_the_ring_is_kept(self):
        # Every patch-valued vertex sits exactly on a ring: ``covers``,
        # not ``contains``, or the whole boundary would be dropped.
        vertices = vertices_from([(0.0, 0.0), (1.0, 0.0), (0.5, 0.5)])
        assert MESH.triangles_inside_coverage(
            vertices, [(0, 1, 2)], prepared_coverage()) == [(0, 1, 2)]

    def test_a_STRADDLING_triangle_is_dropped(self):
        # This is the 85-vertex class a centroid test let through at
        # +60-136: two vertices in, one out, and the outside one is then
        # a free vertex the solve moves.
        vertices = vertices_from([(0.8, 0.5), (0.95, 0.5), (1.4, 0.5)])
        assert MESH.triangles_inside_coverage(
            vertices, [(0, 1, 2)], prepared_coverage()) == []

    def test_a_wholly_outside_triangle_is_dropped(self):
        vertices = vertices_from([(2.0, 2.0), (2.5, 2.0), (2.2, 2.5)])
        assert MESH.triangles_inside_coverage(
            vertices, [(0, 1, 2)], prepared_coverage()) == []

    def test_the_road_ribbon_that_TOUCHES_the_patch_is_dropped(self):
        # The +60-136 mechanism in miniature: a ribbon triangle sharing a
        # ring vertex with the patch is still outside the patch.
        vertices = vertices_from([(1.0, 0.5), (1.6, 0.5), (1.3, 0.9)])
        assert MESH.triangles_inside_coverage(
            vertices, [(0, 1, 2)], prepared_coverage()) == []


class FakeTile:
    lat = 60
    lon = -136


class TestExtentDetector:
    def test_quiet_when_every_moved_vertex_is_inside(self):
        vertices = vertices_from([(0.2, 0.2), (0.5, 0.5)])
        assert MESH.audit_interp_alt_extent(
            FakeTile(), vertices, numpy.array([0, 1]),
            COVERAGE, prepared_coverage()) == 0

    def test_REFUSES_a_moved_vertex_outside_the_coverage(self):
        vertices = vertices_from([(0.2, 0.2), (3.0, 3.0)])
        with pytest.raises(MESH.InterpAltLeak) as caught:
            MESH.audit_interp_alt_extent(
                FakeTile(), vertices, numpy.array([0, 1]),
                COVERAGE, prepared_coverage())
        message = str(caught.value)
        assert "INTERP_ALT LEAK at +60-136" in message
        assert "1 vertex(es) OUTSIDE" in message

    def test_warn_mode_reports_instead_of_refusing(self, monkeypatch):
        monkeypatch.setenv(MESH.INTERP_ALT_LEAK_ENV, "warn")
        vertices = vertices_from([(0.2, 0.2), (3.0, 3.0)])
        assert MESH.audit_interp_alt_extent(
            FakeTile(), vertices, numpy.array([0, 1]),
            COVERAGE, prepared_coverage()) == 1

    def test_nothing_moved_is_a_no_op(self):
        vertices = vertices_from([(0.2, 0.2)])
        assert MESH.audit_interp_alt_extent(
            FakeTile(), vertices, None, COVERAGE, prepared_coverage()) == 0
        assert MESH.audit_interp_alt_extent(
            FakeTile(), vertices, numpy.array([], dtype=int),
            geometry.Polygon(), None) == 0

    def test_the_solve_reports_which_vertices_it_moved(self):
        # The detector judges what MOVED; that set has to come from the
        # solve itself, not from the triangle list it was handed.
        vertices = numpy.zeros(STRIDE * 3)
        for index, (x, y, carried) in enumerate(
                [(0.0, 0.0, 10.0), (1.0, 0.0, 10.0), (0.5, 1.0, 999.0)]):
            vertices[STRIDE * index] = x
            vertices[STRIDE * index + 1] = y
            vertices[STRIDE * index + 5] = carried
        report = {}
        MESH.interpolate_free_interior_altitudes(
            vertices, [(0, 1, 2)], {0, 1}, report=report)
        assert list(report["changed_indices"]) == [2]


class TestPatchCoveragePolygon:
    def _write_inputs(self, tmp_path, marker):
        node = tmp_path / "Data+60-136.node"
        poly = tmp_path / "Data+60-136.poly"
        corners = [(0.10, 0.10), (0.20, 0.10), (0.20, 0.20), (0.10, 0.20)]
        node.write_text(
            "4 2 1 0\n" + "".join(
                f"{i + 1} {x:.9f} {y:.9f} 0.000000000\n"
                for i, (x, y) in enumerate(corners)))
        poly.write_text(
            "0 2 1 0\n\n4 1\n"
            + "".join(f"{i + 1} {i + 1} {(i + 1) % 4 + 1} {marker}\n"
                      for i in range(4))
            + "\n0\n\n0\n")

        class Tile:
            lat, lon = 60, -136
            build_dir = str(tmp_path)

        return Tile()

    def test_marker_15_rings_become_the_coverage(self, tmp_path, monkeypatch):
        tile = self._write_inputs(tmp_path, VMAP.PATCH_RING_MARKER)
        monkeypatch.setattr(
            MESH.FNAMES, "input_node_file",
            lambda t: str(tmp_path / "Data+60-136.node"))
        monkeypatch.setattr(
            MESH.FNAMES, "input_poly_file",
            lambda t: str(tmp_path / "Data+60-136.poly"))
        (coverage, covered) = MESH.patch_coverage_polygon(tile)
        assert coverage.area == pytest.approx(0.01, rel=1e-9)
        assert covered.covers(geometry.Point(0.15, 0.15))
        assert not covered.covers(geometry.Point(0.30, 0.30))

    def test_a_ROAD_ribbon_ring_is_NOT_coverage(self, tmp_path, monkeypatch):
        # marker 8 is include_roads' own; only the patch rings count.
        tile = self._write_inputs(tmp_path, 8)
        monkeypatch.setattr(
            MESH.FNAMES, "input_node_file",
            lambda t: str(tmp_path / "Data+60-136.node"))
        monkeypatch.setattr(
            MESH.FNAMES, "input_poly_file",
            lambda t: str(tmp_path / "Data+60-136.poly"))
        (coverage, covered) = MESH.patch_coverage_polygon(tile)
        assert coverage.is_empty
        assert covered is None

    def test_unreadable_inputs_disable_rather_than_widen(self, monkeypatch):
        monkeypatch.setattr(
            MESH.FNAMES, "input_node_file", lambda t: "/nonexistent/x.node")
        monkeypatch.setattr(
            MESH.FNAMES, "input_poly_file", lambda t: "/nonexistent/x.poly")
        assert MESH.patch_coverage_polygon(FakeTile()) is None
