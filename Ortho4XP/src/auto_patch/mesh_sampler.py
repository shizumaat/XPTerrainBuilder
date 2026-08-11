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

    Only triangles overlapping ``bounds`` are retained, which keeps a
    3-million-triangle tile down to something one airport's queries can
    scan.  ``bounds`` is ``(min_lon, min_lat, max_lon, max_lat)``.
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
        # candidate prefilter in elevation_at.
        self._triangle_minimum = corners[:, :, :2].min(axis=1)
        self._triangle_maximum = corners[:, :, :2].max(axis=1)

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
        # Candidate prefilter: a linear scan over every retained
        # triangle's bounding box, per query.  Fine at the current scale
        # (a few thousand queries per airport post-mesh, against an
        # airport-bounded triangle subset).  If profiling ever shows it
        # biting, the answer is a uniform-grid index over these triangle
        # bounding boxes — measure before building it.
        candidate_indices = numpy.nonzero(
            (self._triangle_minimum[:, 0] <= longitude)
            & (self._triangle_maximum[:, 0] >= longitude)
            & (self._triangle_minimum[:, 1] <= latitude)
            & (self._triangle_maximum[:, 1] >= latitude)
        )[0]

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
