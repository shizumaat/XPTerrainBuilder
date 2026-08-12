"""R18-1b — NO VERTEX INSIDE A PATCH FACE ANSWERS WITH DEM.

Fable lead amendment 1 (2026-08-12), on the refutation of round 18's
seeding hypothesis: every face in HECA's patch coverage IS seeded (the
sub-cell pass adds zero) and the hill still stood at 98.05 m, because
``O4_Mesh_Utils.post_process_nodes_altitudes`` gives each INTERP_ALT
vertex ITS OWN carried vector altitude — which for a free interior
Steiner vertex is the DEM the mesher sampled, not the patch.

The law: such a vertex takes the altitude its face's AUTHORED vertices
imply.  Implemented as the discrete harmonic extension, so it reproduces
a plane exactly, obeys the maximum principle everywhere else, and leaves
every authored vertex byte-identical.

Headless: the function is pure over the mesh arrays — no files, no
mesher, no X-Plane install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Mesh_Utils as MESH  # noqa: E402

#: The column layout ``post_process_nodes_altitudes`` loads: 6 per
#: vertex, column 2 the working altitude and column 5 the carried
#: vector altitude the INTERP_ALT treatment copies into it.
STRIDE = 6
Z_COLUMN = 2
VECTOR_COLUMN = 5

#: Anything a DEM might hand back inside a patched apron — HECA's hill
#: was 99.33 m inside an 86 m apron.
DEM_SENTINEL = 999.0


def build(vertex_rows):
    """``vertices`` array from ``[(x, y, carried_altitude), ...]``."""
    vertices = numpy.zeros(STRIDE * len(vertex_rows))
    for index, (x, y, carried) in enumerate(vertex_rows):
        vertices[STRIDE * index] = x
        vertices[STRIDE * index + 1] = y
        vertices[STRIDE * index + Z_COLUMN] = carried
        vertices[STRIDE * index + VECTOR_COLUMN] = carried
    return vertices


def carried(vertices, index):
    return vertices[STRIDE * index + VECTOR_COLUMN]


def square_fan(plane):
    """A unit square of 4 AUTHORED corners around 1 FREE centre, as 4
    triangles.  ``plane(x, y)`` supplies the authored altitudes; the
    centre carries the DEM sentinel."""
    corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    rows = [(x, y, plane(x, y)) for x, y in corners]
    rows.append((0.5, 0.5, DEM_SENTINEL))
    triangles = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return build(rows), triangles, {0, 1, 2, 3}   # the patch ring


class TestPlanarReproduction:
    def test_a_flat_face_gives_the_interior_the_face_value(self):
        vertices, triangles, authored = square_fan(lambda x, y: 86.5)
        report = {}
        changed = MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored, report=report)
        assert changed == 1
        assert carried(vertices, 4) == pytest.approx(86.5, abs=1e-9)
        assert report == {"free": 1, "solved": 1, "isolated": 0,
                          "non_finite": 0}

    def test_a_TILTED_face_is_reproduced_exactly(self):
        # The harmonic extension is exact on affine data — the interior
        # vertex must land ON the plane, not merely between the corners.
        def plane(x, y):
            return 86.0 + 4.0 * x - 2.5 * y

        vertices, triangles, authored = square_fan(plane)
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        assert carried(vertices, 4) == pytest.approx(plane(0.5, 0.5),
                                                     abs=1e-9)

    def test_an_ALL_ZERO_face_still_supplies_its_interior(self):
        # A sea-level airport: every authored vertex is exactly 0.0 m,
        # so the whole right-hand side is zero.  If "no Dirichlet data"
        # is inferred from a zero right-hand side, this face's interior
        # is declared isolated and keeps the DEM — which is the defect
        # this amendment exists to remove, reintroduced at sea level.
        vertices, triangles, authored = square_fan(lambda x, y: 0.0)
        report = {}
        changed = MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored, report=report)
        assert report["isolated"] == 0
        assert changed == 1
        assert carried(vertices, 4) == pytest.approx(0.0, abs=1e-9)

    def test_the_dem_value_it_replaces_is_irrelevant(self):
        # Whatever the mesher sampled there, the answer comes from the
        # face.  (Mutation guard: an implementation that blended with
        # the old value would fail this.)
        def plane(x, y):
            return 86.0 + 4.0 * x - 2.5 * y

        results = []
        for sentinel in (-500.0, 0.0, 99.33, 10000.0):
            vertices, triangles, authored = square_fan(plane)
            vertices[STRIDE * 4 + VECTOR_COLUMN] = sentinel
            MESH.interpolate_free_interior_altitudes(
                vertices, triangles, authored)
            results.append(carried(vertices, 4))
        assert results == pytest.approx([plane(0.5, 0.5)] * 4, abs=1e-9)


class TestAuthoredVerticesAreUntouched:
    def test_authored_columns_are_byte_identical(self):
        vertices, triangles, authored = square_fan(
            lambda x, y: 86.0 + x - y)
        before = vertices.copy()
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        for index in sorted(authored):
            lo, hi = STRIDE * index, STRIDE * (index + 1)
            assert (vertices[lo:hi] == before[lo:hi]).all(), index

    def test_only_column_5_of_a_free_vertex_moves(self):
        vertices, triangles, authored = square_fan(lambda x, y: 86.0)
        before = vertices.copy()
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        moved = numpy.nonzero(vertices != before)[0]
        assert list(moved) == [STRIDE * 4 + VECTOR_COLUMN]


class TestManyFreeVertices:
    #: The two authored ends. 0.0 m is deliberate: an authored value of
    #: exactly zero (an airport at sea level) must still count as
    #: Dirichlet data — see the implementation's note.
    LOW, HIGH = 0.0, 30.0

    def _strip(self, n_free):
        """A run of ``n_free`` free vertex PAIRS bridging two authored
        ends, as a chain of triangles — the shape a long apron interior
        takes.  Authored vertices come FIRST (indices 0 and 1), which is
        the ordering the discriminator relies on."""
        rows = [(0.0, 0.0, self.LOW),                  # authored
                (float(n_free + 1), 0.0, self.HIGH)]   # authored
        for k in range(n_free):
            rows.append((float(k + 1), 0.0, DEM_SENTINEL))   # low
            rows.append((float(k + 1), 1.0, DEM_SENTINEL))   # high
        triangles = []
        previous = 0
        for k in range(n_free):
            low, high = 2 + 2 * k, 3 + 2 * k
            triangles.append((previous, low, high))
            previous = low
        triangles.append((previous, 1, len(rows) - 1))
        return build(rows), triangles, {0, 1}

    def test_the_maximum_principle_holds(self):
        # No interior vertex may leave the range of its face's authored
        # data — the property that makes "no DEM inside a patch face"
        # a guarantee rather than a hope.
        vertices, triangles, authored = self._strip(6)
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        last = len(vertices) // STRIDE - 1
        free_values = [carried(vertices, i)
                       for i in range(len(authored), last + 1)]
        assert min(free_values) >= self.LOW - 1e-9
        assert max(free_values) <= self.HIGH + 1e-9

    def test_a_sea_level_authored_end_is_still_dirichlet_data(self):
        # Regression: reachability was read off the right-hand side, so
        # an authored 0.0 m neighbour looked like NO neighbour and the
        # whole run was declared isolated and left on the DEM.
        vertices, triangles, authored = self._strip(6)
        report = {}
        changed = MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored, report=report)
        assert report["isolated"] == 0
        assert changed == report["free"] > 0

    def test_no_free_vertex_keeps_the_dem_sentinel(self):
        vertices, triangles, authored = self._strip(6)
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        last = len(vertices) // STRIDE - 1
        for index in range(len(authored), last + 1):
            assert carried(vertices, index) != DEM_SENTINEL, index

    def test_monotone_along_the_run(self):
        # The low chain carries the gradient from one authored end to
        # the other; harmonic data on a path is monotone.
        vertices, triangles, authored = self._strip(6)
        MESH.interpolate_free_interior_altitudes(
            vertices, triangles, authored)
        chain = [carried(vertices, 2 + 2 * k) for k in range(6)]
        assert chain == sorted(chain), chain

    def test_deterministic(self):
        runs = []
        for _ in range(3):
            vertices, triangles, authored = self._strip(6)
            MESH.interpolate_free_interior_altitudes(
                vertices, triangles, authored)
            runs.append(vertices.copy())
        assert (runs[0] == runs[1]).all() and (runs[1] == runs[2]).all()


class TestLegitimateSurvivors:
    def test_a_component_with_no_authored_vertex_keeps_its_own_value(self):
        # Two free vertices touching only each other: nothing to
        # interpolate FROM.  They keep their value and are REPORTED —
        # this is the "legitimate survivor" class the acceptance names.
        rows = [(0.0, 0.0, 86.0), (1.0, 0.0, 86.0), (0.5, 1.0, 86.0),
                (5.0, 5.0, DEM_SENTINEL), (6.0, 5.0, DEM_SENTINEL),
                (5.5, 6.0, DEM_SENTINEL)]
        vertices = build(rows)
        triangles = [(0, 1, 2), (3, 4, 5)]
        report = {}
        changed = MESH.interpolate_free_interior_altitudes(
            vertices, triangles, {0, 1, 2}, report=report)
        assert changed == 0
        assert report["free"] == 3 and report["isolated"] == 3
        for index in (3, 4, 5):
            assert carried(vertices, index) == DEM_SENTINEL

    def test_a_mixed_mesh_solves_the_reachable_and_reports_the_rest(self):
        rows = [(0.0, 0.0, 10.0), (1.0, 0.0, 20.0), (0.5, 1.0, 30.0),
                (0.5, 0.4, DEM_SENTINEL),
                (5.0, 5.0, DEM_SENTINEL), (6.0, 5.0, DEM_SENTINEL),
                (5.5, 6.0, DEM_SENTINEL)]
        vertices = build(rows)
        triangles = [(0, 1, 3), (1, 2, 3), (2, 0, 3), (4, 5, 6)]
        report = {}
        changed = MESH.interpolate_free_interior_altitudes(
            vertices, triangles, {0, 1, 2}, report=report)
        assert changed == 1
        assert report["isolated"] == 3
        assert carried(vertices, 3) == pytest.approx(20.0, abs=1e-9)
        assert carried(vertices, 4) == DEM_SENTINEL


class TestNoOps:
    def test_no_free_vertices_is_a_no_op(self):
        vertices, triangles, _ = square_fan(lambda x, y: 86.0)
        before = vertices.copy()
        report = {}
        assert MESH.interpolate_free_interior_altitudes(
            vertices, triangles, {0, 1, 2, 3, 4}, report=report) == 0
        assert (vertices == before).all()
        assert report["free"] == 0

    def test_no_patch_valued_set_disables_it(self):
        # The caller passes None when it could not establish the
        # patch-valued set — the historical behaviour must stand.
        vertices, triangles, _ = square_fan(lambda x, y: 86.0)
        before = vertices.copy()
        assert MESH.interpolate_free_interior_altitudes(
            vertices, triangles, None) == 0
        assert (vertices == before).all()

    def test_an_EMPTY_patch_valued_set_disables_it(self):
        # A region with no patch ring at all (a road ribbon outside any
        # patch) has nothing to interpolate FROM and must come out
        # byte-unchanged rather than averaged into mush.
        vertices, triangles, _ = square_fan(lambda x, y: 86.0)
        before = vertices.copy()
        assert MESH.interpolate_free_interior_altitudes(
            vertices, triangles, set()) == 0
        assert (vertices == before).all()

    def test_no_triangles_is_a_no_op(self):
        vertices, _triangles, authored = square_fan(lambda x, y: 86.0)
        before = vertices.copy()
        assert MESH.interpolate_free_interior_altitudes(
            vertices, [], authored) == 0
        assert (vertices == before).all()


class TestPatchValuedVertexIdentification:
    """The discriminator is PATCH-RING MEMBERSHIP, read off the input
    ``.poly``: a vertex is patch-valued exactly when a PATCH_RING_MARKER
    edge ends on it.  The id->index mapping relies on the mesher writing
    the input vertices first, in order, which is VERIFIED against the
    input ``.node``, never trusted.

    THE MEASURED REASON this is not "the vector map authored it": HECA's
    hill vertex IS an authored input node (id 138790, carried altitude
    99.33 m) whose four incident edges are all DUMMY — an ORTHOGRID
    node.  An authored-set discriminator protects it and it keeps the
    DEM, which is exactly the defect (measured: 12,936 Steiner points
    fixed, class 54 -> 50, hill unmoved)."""

    class _Tile:
        def __init__(self, path):
            self._path = path

    def _write_input_node(self, path, rows):
        with open(path, "w") as handle:
            handle.write(f"{len(rows)} 2 1 0\n")
            for index, (x, y) in enumerate(rows, start=1):
                handle.write(f"{index} {x:.9f} {y:.9f} 0.0\n")

    def _write_input_poly(self, path, edges):
        with open(path, "w") as handle:
            handle.write("0 2 1 0\n\n")
            handle.write(f"{len(edges)} 1\n")
            for index, (a, b, attribute) in enumerate(edges, start=1):
                handle.write(f"{index} {a} {b} {attribute}\n")
            handle.write("\n0\n\n0\n")

    def _bind(self, monkeypatch, tmp_path, rows, edges):
        node, poly = tmp_path / "in.node", tmp_path / "in.poly"
        self._write_input_node(node, rows)
        self._write_input_poly(poly, edges)
        monkeypatch.setattr(MESH.FNAMES, "input_node_file",
                            lambda tile: str(node))
        monkeypatch.setattr(MESH.FNAMES, "input_poly_file",
                            lambda tile: str(poly))

    def test_only_patch_ring_endpoints_are_patch_valued(
            self, tmp_path, monkeypatch):
        # Node 1-2 wear the patch ring; 3-4 wear DUMMY (the orthogrid /
        # gluing class) and INTERP_ALT (a road ribbon) — neither is a
        # patch value.
        self._bind(
            monkeypatch, tmp_path,
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            [(1, 2, MESH.PATCH_RING_MARKER), (3, 4, 0), (2, 3, 8)])
        vertices = build([(0.0, 0.0, 1.0), (1.0, 0.0, 2.0),
                          (1.0, 1.0, 3.0), (0.0, 1.0, DEM_SENTINEL)])
        assert MESH.patch_valued_vertex_indices(object(), vertices) == {0, 1}

    def test_the_marker_matches_the_vector_map(self):
        # Wire-protocol drift guard: the marker is mirrored, not
        # imported (an import here would close a producer/consumer
        # cycle), so a change on either side must fail a test.
        import O4_Vector_Map as VMAP
        assert MESH.PATCH_RING_MARKER == VMAP.PATCH_RING_MARKER

    def test_a_REORDERED_mesher_disables_the_feature(
            self, tmp_path, monkeypatch):
        # If Triangle ever stopped preserving input order, the id->index
        # mapping would misclassify vertices and rewrite the patch
        # itself.  It must refuse instead.
        self._bind(
            monkeypatch, tmp_path,
            [(9.0, 9.0), (1.0, 0.0), (1.0, 1.0)],
            [(1, 2, MESH.PATCH_RING_MARKER)])
        vertices = build([(0.0, 0.0, 1.0), (1.0, 0.0, 2.0),
                          (1.0, 1.0, 3.0), (0.5, 0.5, DEM_SENTINEL)])
        assert MESH.patch_valued_vertex_indices(object(), vertices) is None

    def test_a_missing_input_file_disables_the_feature(self, monkeypatch):
        monkeypatch.setattr(MESH.FNAMES, "input_node_file",
                            lambda tile: "/nonexistent/in.node")
        assert MESH.patch_valued_vertex_indices(
            object(), numpy.zeros(60)) is None


class TestScopeIsPinned:
    """The pass governs the vector-authored patch/road regions
    (attribute EXACTLY ``INTERP_ALT``), not everything the INTERP_ALT
    TREATMENT covers (which is ``>= INTERP_ALT``, i.e. the apt.dat
    RUNWAY / TAXIWAY / APRON / HANGAR regions too).

    MEASURED when the widening was tried (2026-08-12): it changed the
    interpolated set NOT AT ALL (12,123 free vertices either way, the
    owner point 91.13 m and the class identical), while moving 49,717
    vertices instead of 11,960 — 3,771 of them by more than 3 m, one by
    32.19 m.  The motivating hypothesis was refuted in the same run: the
    owner point's triangle came back with attribute 8, already in scope.
    So the scope is PINNED here, and widening it must be a deliberate
    act that fails this test first."""

    def test_apt_dat_region_attributes_are_out_of_scope(self):
        from O4_Vector_Utils import Vector_Map
        treated = Vector_Map.dico_attributes["INTERP_ALT"]
        for name in ("RUNWAY", "TAXIWAY", "APRON", "HANGAR"):
            attribute = Vector_Map.dico_attributes[name]
            # They pass the TREATMENT's >= test …
            assert attribute >= treated, name
            # … and must fail the interpolation's == scope.
            assert attribute != treated, name

    def test_a_component_without_a_patch_ring_is_never_captured(self):
        # The 55,020 free vertices in patch-ring-free components on
        # +30+031 (road ribbons, other airports' ground) must keep their
        # values however the scope is drawn — that is the containment
        # half of the law, and it is what the isolation branch does.
        rows = [(0.0, 0.0, 86.0), (1.0, 0.0, 86.0), (0.5, 1.0, 86.0),
                (5.0, 5.0, DEM_SENTINEL), (6.0, 5.0, DEM_SENTINEL),
                (5.5, 6.0, DEM_SENTINEL), (5.5, 5.5, DEM_SENTINEL)]
        vertices = build(rows)
        before = vertices.copy()
        triangles = [(3, 4, 6), (4, 5, 6), (5, 3, 6)]
        report = {}
        assert MESH.interpolate_free_interior_altitudes(
            vertices, triangles, {0, 1, 2}, report=report) == 0
        assert report["isolated"] == 4
        assert (vertices == before).all()
