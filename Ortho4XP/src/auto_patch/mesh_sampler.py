"""Elevation sampling over a built Ortho4XP ``Data<tile>.mesh``.

Contract frozen by workstream W1 (``docs/dsf_object_integration_spec.md``
section 3.2); implementation lands in workstream W3, ported from the
verified prototype ``tools/mesh_elevation_sampler.py`` with one
deliberate correctness change: **the nearest-vertex fallback is deleted,
not guarded**.  The prototype silently returned a plausible elevation for
a point outside every retained triangle — a structure that has walked off
the tile — and a plausible number is exactly what a caller must not get.
Callers skip-and-report instead (invariant I-13).

Use the mesh, not the DEM: the mesh is the terrain after auto_patch's
grading.  At the KCLT anchor the mesh reads 219.83 m where the source DEM
reads 218.95 m.

Mesh format, as written by ``O4_Mesh_Utils.write_mesh_file``::

    MeshVersionFormatted 2
    Dimension 3

    Vertices
    <count>
    <longitude> <latitude> <elevation/100000> 0
    ...
    Normals
    <count>
    ...
    Triangles
    <count>
    <vertex_a> <vertex_b> <vertex_c> <terrain_type>

Note the ``/ 100000`` scaling on the elevation column.  The vertex line's
4th field is a hardcoded literal ``0`` (never read back) — NOT a tag; only
the TRIANGLE line's 4th field is a real terrain-type attribute.  Triangle
vertex indices are 1-based (straight from Triangle's ``.ele`` output;
confirmed at ``O4_Mesh_Utils.py`` read side, which subtracts 1).

THE TERRAIN-TYPE ATTRIBUTE CARRIES THE WATER BITS.  It is the same raw
value ``O4_DSF_Utils.remap_water_tri_type`` collapses into the DSF's
0=land / 1=inland / 2=sea classes: any bit of ``WATER_BIT_MASK`` set
means the triangle is water (bit 1 mapped/inland water, bit 4 the
coastline sea flood).  The mesh is therefore the frame-correct water
authority at post-mesh time — it knows a canal that OSM maps only as a
coastline — and :meth:`MeshElevationSampler.sample_at` returns it beside
the elevation, from ONE point-in-triangle scan.
"""

from __future__ import annotations

import os

import numpy

from typing import NamedTuple

# O4_Mesh_Utils.write_mesh_file writes the elevation column divided by
# this constant; reading multiplies it back.
MESH_ELEVATION_SCALE = 100000.0

# The water bits of a triangle's terrain-type attribute, exactly as
# ``O4_DSF_Utils.remap_water_tri_type`` reads them (its ``has_water``
# default).  Non-zero ⇒ the triangle is water of some kind; the
# inland/sea split below it is a DSF-texturing question this module has
# no opinion about.
WATER_BIT_MASK = 7

# One-entry parse cache: Phase 2 constructs a sampler PER OBJECT POOL
# (dozens per airport, several airports per tile) against the same
# ~160 MB tile mesh, and the text parse dominated the whole rebake
# (profiled 2026-07-15: ~80 constructions x ~1.3 s).  Keyed by
# (path, mtime_ns, size) so a rebuilt mesh is never served stale; one
# entry suffices (a run works one tile mesh at a time) and bounds the
# held memory to one tile's arrays (~100 MB).  The cached arrays are
# shared read-only between sampler instances — nothing mutates them
# after the parse.
_parse_cache_key: tuple[str, int, int] | None = None
_parse_cache_arrays: tuple[
    numpy.ndarray, numpy.ndarray, numpy.ndarray] | None = None


def _read_mesh_cached(
    mesh_path: str,
) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    global _parse_cache_key, _parse_cache_arrays
    stat = os.stat(mesh_path)
    key = (os.path.abspath(mesh_path), stat.st_mtime_ns, stat.st_size)
    if key != _parse_cache_key:
        _parse_cache_arrays = MeshElevationSampler._read_mesh(mesh_path)
        _parse_cache_key = key
    return _parse_cache_arrays


class MeshSample(NamedTuple):
    """One point's answer from the built mesh.

    ``terrain_type`` is the triangle's RAW attribute; ``is_water`` is the
    only reading of it this module makes (:data:`WATER_BIT_MASK`), so no
    caller has to know the bit layout.  The inland/sea split below it
    belongs to the DSF texturer, not here."""

    elevation_metres: float
    terrain_type: int
    is_water: bool


class OutsideMeshError(Exception):
    """Raised when a query point lies outside every retained triangle.

    Deliberately loud: the prototype's silent nearest-vertex fallback is
    the failure mode this class exists to kill (invariant I-13).
    """


class MeshElevationSampler:
    """Barycentric point-in-triangle elevation lookup over a built mesh.

    Only triangles overlapping ``bounds`` are retained.  That is much
    less of a reduction than it sounds: LEMD's box keeps 1,771,765 of
    the tile's 2,931,134 triangles (the airport sits in the tile's
    densest region), which is why the retained set is indexed by a
    UNIFORM GRID rather than scanned per query — see the index's own
    section below and RULINGS 2026-09-12g.  ``bounds`` is
    ``(min_lon, min_lat, max_lon, max_lat)``.

    :meth:`sample_at` answers one point; :meth:`sample_many` answers a
    batch through the same index and the same tie-break, and is what
    ``placement_geom.surface_many`` batches through.
    """

    def __init__(
        self,
        mesh_path: str,
        bounds: tuple[float, float, float, float],
        margin_degrees: float = 0.002,
    ) -> None:
        minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude = (
            bounds
        )
        minimum_longitude -= margin_degrees
        minimum_latitude -= margin_degrees
        maximum_longitude += margin_degrees
        maximum_latitude += margin_degrees

        vertices, triangles, triangle_attributes = _read_mesh_cached(
            mesh_path)

        vertex_inside_bounds = (
            (vertices[:, 0] >= minimum_longitude)
            & (vertices[:, 0] <= maximum_longitude)
            & (vertices[:, 1] >= minimum_latitude)
            & (vertices[:, 1] <= maximum_latitude)
        )
        keep_triangle = vertex_inside_bounds[triangles].any(axis=1)
        self._triangles = triangles[keep_triangle]
        self._triangle_attributes = triangle_attributes[keep_triangle]
        if not len(self._triangles):
            raise ValueError(
                f"no mesh triangles inside {bounds} — wrong tile?"
            )
        self._vertices = vertices

        corners = vertices[self._triangles]
        self._corner_a = corners[:, 0, :]
        self._corner_b = corners[:, 1, :]
        self._corner_c = corners[:, 2, :]
        # Per-triangle (longitude, latitude) bounding boxes for the
        # candidate prefilter in sample_at.
        self._triangle_minimum = corners[:, :, :2].min(axis=1)
        self._triangle_maximum = corners[:, :, :2].max(axis=1)
        self._build_grid_index()

    # ------------------------------------------------------------------
    # The uniform-grid index (RULINGS 2026-09-12g)
    #
    # This module's original prefilter was a LINEAR SCAN over every
    # retained triangle's bounding box, per query, on the premise of "a
    # few thousand queries per airport, against an airport-bounded
    # triangle subset".  Both halves of that premise were measured false
    # on 2026-09-12: LEMD's bounds retain 1,771,765 triangles (60 % of
    # the tile) and §16b's own-geometry cut asks 302,532 queries — 2.0 ms
    # each, 606-631 s of the 706 s mesh step.  The comment that shipped
    # here prescribed the fix ("a uniform-grid index over these triangle
    # bounding boxes — measure before building it"); the measurement is
    # 12g and this is the index.  The linear scan is DELETED, not gated.
    #
    # IDENTITY.  The grid is a pure ACCELERATOR of the same prefilter:
    # a triangle is registered in every cell its bounding box overlaps,
    # so the triangles whose bbox contains a query point are all in that
    # point's cell, and the per-candidate bbox test below is the scan's
    # own test verbatim.  The candidate set is therefore EQUAL to the
    # linear scan's, and it is visited in ASCENDING TRIANGLE INDEX (the
    # buckets are index-sorted), so at a shared edge — where two or three
    # triangles all answer — the triangle chosen is the same one the
    # scan chose.  Bit-identical elevations, terrain types and
    # ``OutsideMeshError`` points; verified against a 165,114-point LEMD
    # oracle and by ``tests/test_mesh_sampler_grid.py``.
    # ------------------------------------------------------------------

    # Cells per axis are chosen from this ladder (see _build_grid_index).
    _GRID_LADDER = (1, 16, 32, 64, 128, 256, 512, 1024)
    # A triangle spanning many cells is registered in each of them, so the
    # index's memory is sum over triangles of its cell span.  Refuse to
    # spend more than this many bucket entries per triangle: on a mesh
    # whose triangles vary by orders of magnitude in size (they do — an
    # airport's own triangles are metres across, the countryside's are
    # hundreds), a finer grid buys a smaller mean candidate count at a
    # superlinear memory cost.  4 x 1.77M entries is ~57 MB of int64.
    _GRID_MAX_ENTRIES_PER_TRIANGLE = 4.0

    def _build_grid_index(self) -> None:
        """Bucket every retained triangle into a uniform (lon, lat) grid.

        Cell count per axis is picked from :attr:`_GRID_LADDER`: the
        finest grid that is no finer than ``sqrt(triangle count)`` (one
        triangle per cell is the point of diminishing returns for a
        point query) and whose exact bucket-entry total stays within
        :attr:`_GRID_MAX_ENTRIES_PER_TRIANGLE` per triangle.  Both
        bounds are computed, not guessed — the entry total is the real
        sum of per-triangle cell spans.  At LEMD (1,771,765 triangles)
        this lands on 512 x 512: 3.5 candidates per query on average,
        against 1,771,765 for the scan it replaces.
        """
        triangle_count = len(self._triangles)
        minimum = self._triangle_minimum
        maximum = self._triangle_maximum
        self._grid_origin_x = float(minimum[:, 0].min())
        self._grid_origin_y = float(minimum[:, 1].min())
        extent_x = float(maximum[:, 0].max()) - self._grid_origin_x
        extent_y = float(maximum[:, 1].max()) - self._grid_origin_y
        # A degenerate extent (every triangle on one line) still needs a
        # non-zero cell size; one cell then holds everything, which is
        # exactly the old linear scan and still correct.
        if not (extent_x > 0.0) or not (extent_y > 0.0):
            cells = 1
        else:
            cells = 1
            limit = self._GRID_MAX_ENTRIES_PER_TRIANGLE * triangle_count
            root = triangle_count ** 0.5
            for candidate in self._GRID_LADDER:
                if candidate > root:
                    break
                entries = self._grid_entry_count(
                    candidate, extent_x, extent_y)
                if entries > limit:
                    break
                cells = candidate
        self._grid_cells = cells
        self._grid_step_x = (extent_x / cells) if extent_x > 0.0 else 1.0
        self._grid_step_y = (extent_y / cells) if extent_y > 0.0 else 1.0

        column_first, column_last, row_first, row_last = self._grid_span(
            minimum, maximum)
        per_triangle = (
            (column_last - column_first + 1)
            * (row_last - row_first + 1)
        ).astype(numpy.int64)
        total = int(per_triangle.sum())
        # Expand each triangle into one entry per cell it overlaps,
        # vectorised: a Python double loop over 1.77M triangles is
        # itself a double-digit-second cost.
        triangle_index = numpy.repeat(
            numpy.arange(triangle_count, dtype=numpy.int64), per_triangle)
        block_start = numpy.zeros(triangle_count, dtype=numpy.int64)
        numpy.cumsum(per_triangle[:-1], out=block_start[1:])
        offset = (
            numpy.arange(total, dtype=numpy.int64)
            - numpy.repeat(block_start, per_triangle)
        )
        width = numpy.repeat(
            (column_last - column_first + 1).astype(numpy.int64),
            per_triangle)
        column = numpy.repeat(column_first, per_triangle) + offset % width
        row = numpy.repeat(row_first, per_triangle) + offset // width
        cell = row.astype(numpy.int64) * cells + column.astype(numpy.int64)
        # Sort by (cell, triangle index): the tie-break the identity
        # argument above rests on is this sort's second key.
        order = numpy.lexsort((triangle_index, cell))
        self._grid_triangles = triangle_index[order]
        counts = numpy.bincount(cell, minlength=cells * cells)
        self._grid_start = numpy.zeros(cells * cells + 1, dtype=numpy.int64)
        numpy.cumsum(counts, out=self._grid_start[1:])

    def _grid_entry_count(
        self, cells: int, extent_x: float, extent_y: float
    ) -> int:
        """Exact bucket-entry total for a candidate cell count."""
        step_x = extent_x / cells
        step_y = extent_y / cells
        column_first, column_last, row_first, row_last = self._grid_span(
            self._triangle_minimum, self._triangle_maximum,
            cells, step_x, step_y)
        return int(
            (
                (column_last - column_first + 1).astype(numpy.int64)
                * (row_last - row_first + 1).astype(numpy.int64)
            ).sum()
        )

    def _grid_span(
        self,
        minimum: numpy.ndarray,
        maximum: numpy.ndarray,
        cells: int | None = None,
        step_x: float | None = None,
        step_y: float | None = None,
    ) -> tuple[
        numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray
    ]:
        """The inclusive cell span of each bounding box."""
        if cells is None:
            cells = self._grid_cells
            step_x = self._grid_step_x
            step_y = self._grid_step_y
        column_first = numpy.clip(
            ((minimum[:, 0] - self._grid_origin_x) / step_x).astype(
                numpy.int64), 0, cells - 1)
        column_last = numpy.clip(
            ((maximum[:, 0] - self._grid_origin_x) / step_x).astype(
                numpy.int64), 0, cells - 1)
        row_first = numpy.clip(
            ((minimum[:, 1] - self._grid_origin_y) / step_y).astype(
                numpy.int64), 0, cells - 1)
        row_last = numpy.clip(
            ((maximum[:, 1] - self._grid_origin_y) / step_y).astype(
                numpy.int64), 0, cells - 1)
        return column_first, column_last, row_first, row_last

    def _candidate_indices(
        self, latitude: float, longitude: float
    ) -> numpy.ndarray:
        """The retained triangles whose bounding box contains the point,
        in ascending triangle index.

        Clamping a point outside the grid's extent into the edge cell is
        safe: the extent IS the union of every retained bounding box, so
        no bounding box can contain such a point and the bbox test below
        rejects the whole cell — the same ``OutsideMeshError`` the scan
        raised.
        """
        cells = self._grid_cells
        column = int(
            (longitude - self._grid_origin_x) / self._grid_step_x)
        row = int((latitude - self._grid_origin_y) / self._grid_step_y)
        if column < 0:
            column = 0
        elif column >= cells:
            column = cells - 1
        if row < 0:
            row = 0
        elif row >= cells:
            row = cells - 1
        cell = row * cells + column
        bucket = self._grid_triangles[
            self._grid_start[cell]:self._grid_start[cell + 1]]
        if not len(bucket):
            return bucket
        return bucket[
            (self._triangle_minimum[bucket, 0] <= longitude)
            & (self._triangle_maximum[bucket, 0] >= longitude)
            & (self._triangle_minimum[bucket, 1] <= latitude)
            & (self._triangle_maximum[bucket, 1] >= latitude)
        ]

    @staticmethod
    def _read_mesh(
        mesh_path: str,
    ) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        """Read vertices, 0-based triangle indices and the per-triangle
        terrain-type attribute from a ``.mesh`` file.

        Returns ``(vertices, triangles, triangle_attributes)`` where
        ``vertices`` is ``(count, 3)`` float64
        ``(longitude, latitude, elevation_metres)``, ``triangles`` is
        ``(count, 3)`` int64 vertex indices and ``triangle_attributes``
        is ``(count,)`` int64 raw terrain-type values (see
        :data:`WATER_BIT_MASK`).
        """
        with open(mesh_path) as handle:
            while True:
                line = handle.readline()
                if not line:
                    raise ValueError(f"{mesh_path}: no Vertices section")
                if line.strip() == "Vertices":
                    break
            vertex_count = int(handle.readline())
            vertex_lines = [handle.readline() for _ in range(vertex_count)]
            # Each vertex line is "<longitude> <latitude>
            # <elevation/100000> 0" — the trailing literal 0 is dropped.
            vertices = numpy.array(
                " ".join(vertex_lines).split(), dtype=numpy.float64
            ).reshape(vertex_count, 4)[:, :3]
            vertices[:, 2] *= MESH_ELEVATION_SCALE

            while True:
                line = handle.readline()
                if not line:
                    raise ValueError(f"{mesh_path}: no Triangles section")
                if line.strip() == "Triangles":
                    break
            triangle_count = int(handle.readline())
            triangle_lines = [
                handle.readline() for _ in range(triangle_count)
            ]
            # Each triangle line is "<vertex_a> <vertex_b> <vertex_c>
            # <terrain_type>".  The attribute column is KEPT: it carries
            # the water bits, and the seat's land test reads them.  A
            # mesh written without the column (never seen from
            # ``write_mesh_file``, which copies Triangle's ``.ele`` rows
            # verbatim) reads as all-land rather than failing — the
            # water test is an EXTRA discriminator, and a mesh that
            # cannot answer must not make the whole seat unmeasurable.
            triangle_columns = numpy.array(
                " ".join(triangle_lines).split(), dtype=numpy.int64
            ).reshape(triangle_count, -1)
            triangles = triangle_columns[:, :3]
            triangle_attributes = (
                triangle_columns[:, 3]
                if triangle_columns.shape[1] > 3
                else numpy.zeros(triangle_count, dtype=numpy.int64)
            )

        # Triangle emits 1-based indices; normalise to 0-based and verify.
        if triangles.min() >= 1:
            triangles = triangles - 1
        if triangles.max() >= len(vertices):
            raise ValueError(f"{mesh_path}: triangle index out of range")
        return vertices, triangles, triangle_attributes

    def sample_at(self, latitude: float, longitude: float) -> "MeshSample":
        """The mesh's answer at a point: barycentric-interpolated
        elevation AND the terrain-type attribute of the triangle the
        point landed in.

        ONE point-in-triangle scan for both — the elevation and "is this
        water?" are the same question about the same triangle, and asking
        twice would walk the candidate list twice and could, at a shared
        edge, answer from two different triangles.

        Raises :class:`OutsideMeshError` outside every retained triangle.
        There is NO nearest-vertex fallback (invariant I-13).
        """
        # Candidate prefilter: the uniform-grid index (RULINGS
        # 2026-09-12g).  Same candidate set as the linear scan this
        # replaced, same ascending-index visit order.
        candidate_indices = self._candidate_indices(latitude, longitude)

        for candidate_index in candidate_indices:
            corner_a = self._corner_a[candidate_index]
            corner_b = self._corner_b[candidate_index]
            corner_c = self._corner_c[candidate_index]
            denominator = (corner_b[1] - corner_c[1]) * (
                corner_a[0] - corner_c[0]
            ) + (corner_c[0] - corner_b[0]) * (corner_a[1] - corner_c[1])
            if abs(denominator) < 1e-18:
                continue  # degenerate (zero-area) triangle
            weight_a = (
                (corner_b[1] - corner_c[1]) * (longitude - corner_c[0])
                + (corner_c[0] - corner_b[0]) * (latitude - corner_c[1])
            ) / denominator
            weight_b = (
                (corner_c[1] - corner_a[1]) * (longitude - corner_c[0])
                + (corner_a[0] - corner_c[0]) * (latitude - corner_c[1])
            ) / denominator
            weight_c = 1.0 - weight_a - weight_b
            if weight_a >= -1e-9 and weight_b >= -1e-9 and weight_c >= -1e-9:
                attribute = int(self._triangle_attributes[candidate_index])
                return MeshSample(
                    elevation_metres=float(
                        weight_a * corner_a[2]
                        + weight_b * corner_b[2]
                        + weight_c * corner_c[2]
                    ),
                    terrain_type=attribute,
                    is_water=bool(attribute & WATER_BIT_MASK),
                )

        # Deliberately NO nearest-vertex fallback here (invariant I-13):
        # the prototype's fallback silently returned a plausible elevation
        # for a point off the retained mesh, which is the one unacceptable
        # output.  Callers skip-and-report instead.
        raise OutsideMeshError(
            f"({latitude}, {longitude}) lies outside every retained mesh "
            f"triangle"
        )

    def sample_many(
        self,
        latitudes: "numpy.ndarray | list[float]",
        longitudes: "numpy.ndarray | list[float]",
    ) -> "list[MeshSample | None]":
        """:meth:`sample_at` for a whole batch of points at once.

        Returns one entry per point, ``None`` where :meth:`sample_at`
        would raise :class:`OutsideMeshError` — the batch form cannot
        raise for one point out of a hundred thousand, and the callers
        (``placement_geom.surface_many``) already drop the misses.

        Points are grouped by grid cell so one cell's candidate bucket is
        read once and tested against all of that cell's points in one
        broadcast.  The per-candidate arithmetic, the ``1e-18``
        degeneracy guard, the ``-1e-9`` barycentric tolerance and the
        ascending-triangle-index tie-break are :meth:`sample_at`'s,
        elementwise and in the same order, so the two agree point for
        point and bit for bit (asserted on the LEMD oracle and in
        ``tests/test_mesh_sampler_grid.py``).
        """
        latitude_array = numpy.asarray(
            latitudes, dtype=numpy.float64).reshape(-1)
        longitude_array = numpy.asarray(
            longitudes, dtype=numpy.float64).reshape(-1)
        if len(latitude_array) != len(longitude_array):
            raise ValueError(
                "sample_many: %d latitudes but %d longitudes"
                % (len(latitude_array), len(longitude_array))
            )
        point_count = len(latitude_array)
        answers: list[MeshSample | None] = [None] * point_count
        if not point_count:
            return answers

        cells = self._grid_cells
        column = numpy.clip(
            ((longitude_array - self._grid_origin_x)
             / self._grid_step_x).astype(numpy.int64), 0, cells - 1)
        row = numpy.clip(
            ((latitude_array - self._grid_origin_y)
             / self._grid_step_y).astype(numpy.int64), 0, cells - 1)
        cell = row * cells + column
        order = numpy.argsort(cell, kind="stable")
        sorted_cells = cell[order]
        group_starts = numpy.flatnonzero(
            numpy.r_[True, sorted_cells[1:] != sorted_cells[:-1]])
        group_bounds = numpy.r_[group_starts, point_count]

        for group in range(len(group_starts)):
            members = order[group_bounds[group]:group_bounds[group + 1]]
            this_cell = int(sorted_cells[group_bounds[group]])
            bucket = self._grid_triangles[
                self._grid_start[this_cell]:self._grid_start[this_cell + 1]]
            if not len(bucket):
                continue
            # Bound the broadcast: one cell's bucket times one chunk of
            # its points.
            chunk = max(1, int(1_000_000 // len(bucket)))
            for offset in range(0, len(members), chunk):
                block = members[offset:offset + chunk]
                self._sample_block(block, latitude_array, longitude_array,
                                   bucket, answers)
        return answers

    def _sample_block(
        self,
        block: numpy.ndarray,
        latitude_array: numpy.ndarray,
        longitude_array: numpy.ndarray,
        bucket: numpy.ndarray,
        answers: "list[MeshSample | None]",
    ) -> None:
        """One cell's candidates against one chunk of its points."""
        block_latitude = latitude_array[block][:, None]
        block_longitude = longitude_array[block][:, None]
        minimum = self._triangle_minimum[bucket]
        maximum = self._triangle_maximum[bucket]
        inside_box = (
            (minimum[None, :, 0] <= block_longitude)
            & (maximum[None, :, 0] >= block_longitude)
            & (minimum[None, :, 1] <= block_latitude)
            & (maximum[None, :, 1] >= block_latitude)
        )
        if not inside_box.any():
            return
        corner_a = self._corner_a[bucket]
        corner_b = self._corner_b[bucket]
        corner_c = self._corner_c[bucket]
        denominator = (
            (corner_b[:, 1] - corner_c[:, 1])
            * (corner_a[:, 0] - corner_c[:, 0])
            + (corner_c[:, 0] - corner_b[:, 0])
            * (corner_a[:, 1] - corner_c[:, 1])
        )
        nondegenerate = numpy.abs(denominator) >= 1e-18
        safe_denominator = numpy.where(nondegenerate, denominator, 1.0)
        delta_x = block_longitude - corner_c[None, :, 0]
        delta_y = block_latitude - corner_c[None, :, 1]
        weight_a = (
            (corner_b[None, :, 1] - corner_c[None, :, 1]) * delta_x
            + (corner_c[None, :, 0] - corner_b[None, :, 0]) * delta_y
        ) / safe_denominator[None, :]
        weight_b = (
            (corner_c[None, :, 1] - corner_a[None, :, 1]) * delta_x
            + (corner_a[None, :, 0] - corner_c[None, :, 0]) * delta_y
        ) / safe_denominator[None, :]
        weight_c = 1.0 - weight_a - weight_b
        accepted = (
            inside_box
            & nondegenerate[None, :]
            & (weight_a >= -1e-9)
            & (weight_b >= -1e-9)
            & (weight_c >= -1e-9)
        )
        hit = accepted.any(axis=1)
        if not hit.any():
            return
        # ``bucket`` is index-sorted, so the first accepted column is the
        # lowest triangle index — sample_at's tie-break.
        first = accepted.argmax(axis=1)
        elevation = (
            weight_a * corner_a[None, :, 2]
            + weight_b * corner_b[None, :, 2]
            + weight_c * corner_c[None, :, 2]
        )
        rows = numpy.flatnonzero(hit)
        chosen = first[rows]
        triangles = bucket[chosen]
        elevations = elevation[rows, chosen]
        attributes = self._triangle_attributes[triangles]
        for position, point_index in enumerate(block[rows]):
            attribute = int(attributes[position])
            answers[int(point_index)] = MeshSample(
                elevation_metres=float(elevations[position]),
                terrain_type=attribute,
                is_water=bool(attribute & WATER_BIT_MASK),
            )

    def elevation_at(self, latitude: float, longitude: float) -> float:
        """Barycentric-interpolated elevation in metres.

        Raises :class:`OutsideMeshError` outside every retained triangle.
        There is NO nearest-vertex fallback (invariant I-13)."""
        return self.sample_at(latitude, longitude).elevation_metres

    def elevation_at_or_none(
        self, latitude: float, longitude: float
    ) -> float | None:
        """As :meth:`elevation_at`, returning ``None`` instead of raising."""
        try:
            return self.elevation_at(latitude, longitude)
        except OutsideMeshError:
            return None

    def sample_at_or_none(
        self, latitude: float, longitude: float
    ) -> "MeshSample | None":
        """As :meth:`sample_at`, returning ``None`` instead of raising."""
        try:
            return self.sample_at(latitude, longitude)
        except OutsideMeshError:
            return None
