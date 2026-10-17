# OrthoStudio XP, Copyright (C) 2026 radioharris. Free software under the GNU GPL: see LICENSE.
# Additional terms (GPL v3 section 7) apply to radioharris's material in this file: see NOTICE.
#
# Ported from OrthoStudio XP (https://github.com/radioharris/orthostudio-xp),
# src/orthostudio/mesh/mesh_file.py at 7c028d82dcc59a27296972973aa0663ef37efddc.
# Modified for XPTerrainBuilder, 2026-10-17 (RULINGS 2026-10-17c,
# Ortho4XP/docs/specs/mesh-io-spec.md §3): the reader returns the arrays of
# this engine's ``read_mesh_file`` (altitude scale applied, 0-based uint32
# corners, uint32 attributes) and accepts a REAL attribute column; the writer
# takes the post-processed Triangle4XP vertices and its ``.ele`` (this
# engine's ``write_mesh_file``: tile-relative coordinates, attribute
# normalised) and keeps the temporary file + ``os.replace``; the ``.npz``
# twin and the ``MeshData`` dataclass are not taken.  LICENSE here is
# Ortho4XP/Licence/gpl.txt; NOTICE is Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE.
"""The ``.mesh`` file: one numpy reader and one byte-identical writer.

The ``.mesh`` stays a TEXT file, byte-identical to what the per-line writer
produced (mesh-io-spec §2: every consumer keeps reading it).  What changed
is how it is read and written: whole blocks parsed in one call, rows
formatted in chunks with the same CPython float formatting.
"""

import os
from dataclasses import dataclass

import numpy as np

from O4_Num_Text import parse_numbers, write_rows
from O4_Triangle_IO import read_ele_text, triangle_attributes

__all__ = ["MESH_Z_SCALE", "MeshArrays", "MeshFormatError", "read_mesh", "write_mesh"]

#: Altitudes are written as metres / 100000 and read back times it.
MESH_Z_SCALE = 100000

_VERTICES_TAG = b"Vertices"
_NORMALS_TAG = b"Normals"
_TRIANGLES_TAG = b"Triangles"


class MeshFormatError(ValueError):
    """A ``.mesh`` file is malformed."""


@dataclass(frozen=True)
class MeshArrays:
    """One ``.mesh`` with ``read_mesh_file``'s semantics: ``coords`` (N, 5)
    float64 lon, lat, altitude in METRES, normal x, normal y; ``triangles``
    (T, 3) uint32 0-based; ``attributes`` (T,) uint32."""

    version: float
    coords: np.ndarray
    triangles: np.ndarray
    attributes: np.ndarray

    def as_legacy_tuple(self) -> tuple:
        """``(version, nbr_nodes, coords flat, nbr_tris, tri_idx flat,
        tri_types)`` — what ``O4_Mesh_Utils.read_mesh_file`` returns."""
        return (self.version, len(self.coords), self.coords.ravel(),
                len(self.triangles), self.triangles.ravel(), self.attributes)


def _section(data: bytes, tag: bytes, start: int) -> tuple:
    """``(count, offset of the first row)`` of the section named ``tag``."""
    pos = data.find(b"\n" + tag + b"\n", start)
    if pos < 0:
        raise MeshFormatError(f"section {tag.decode()!r} not found")
    count_start = pos + len(tag) + 2
    count_end = data.find(b"\n", count_start)
    if count_end < 0:
        raise MeshFormatError(f"section {tag.decode()!r}: no count")
    return int(data[count_start:count_end]), count_end + 1


def _block(block: bytes, count: int, width: int, dtype, what: str) -> np.ndarray:
    values = parse_numbers(block, dtype) if block.strip() else np.zeros(0, dtype)
    if values.size != count * width:
        raise MeshFormatError(
            f"{what}: expected {count} rows of {width} values, parsed {values.size}")
    return values.reshape(count, width)


def _triangle_rows(block: bytes, count: int) -> tuple:
    """``(corners int64 1-based, attributes uint32)``; the attribute column
    may hold a REAL (a mesh written before the attribute was normalised)."""
    try:
        table = _block(block, count, 4, np.int64, "triangles")
        attributes = table[:, 3]
    except ValueError:
        table = _block(block, count, 4, np.float64, "triangles")
        attributes, _ = triangle_attributes(table[:, 3])
    return table[:, :3].astype(np.int64), attributes.astype(np.uint32)


def read_mesh(path) -> MeshArrays:
    """Read an Ortho4XP ``.mesh`` file."""
    with open(path, "rb") as handle:
        data = handle.read()
    if b"\r" in data[:256]:
        data = data.replace(b"\r\n", b"\n")
    first_eol = data.find(b"\n")
    if first_eol < 0 or not data.startswith(b"MeshVersionFormatted"):
        raise MeshFormatError(f"{path}: not a .mesh file")
    version = float(data[:first_eol].split()[-1])
    n_vertices, v_start = _section(data, _VERTICES_TAG, first_eol)
    n_normals, n_start = _section(data, _NORMALS_TAG, v_start)
    n_triangles, t_start = _section(data, _TRIANGLES_TAG, n_start)
    if n_normals != n_vertices:
        raise MeshFormatError(f"{path}: {n_normals} normals for {n_vertices} vertices")
    v_end = data.rfind(b"\n" + _NORMALS_TAG + b"\n", v_start, n_start)
    t_end = data.rfind(b"\n" + _TRIANGLES_TAG + b"\n", n_start, t_start)
    vertices = _block(data[v_start:v_end], n_vertices, 4, np.float64, "vertices")
    normals = _block(data[n_start:t_end], n_vertices, 3, np.float64, "normals")
    corners, attributes = _triangle_rows(data[t_start:], n_triangles)
    coords = np.empty((n_vertices, 5))
    coords[:, :3] = vertices[:, :3]
    coords[:, 2] *= MESH_Z_SCALE
    coords[:, 3:] = normals[:, :2]
    return MeshArrays(version=version, coords=coords,
                      triangles=(corners - 1).astype(np.uint32),
                      attributes=attributes)


def write_mesh(mesh_file_name, vertices, ele_file_name, lon, lat, dummy=0) -> None:
    """Write the ``.mesh`` from Triangle4XP's post-processed ``vertices``
    (flat, six per vertex: tile-relative x, y, altitude, normal x, normal y,
    carried altitude) and its ``.ele``.  The attribute column is normalised
    (a REAL degenerate attribute becomes ``dummy``).  Written to a temporary
    file in the same directory and renamed into place: neighbour tile builds
    read this file concurrently (step 2.5 masks)."""
    table = np.asarray(vertices, dtype=np.float64).reshape(-1, 6)
    elements = read_ele_text(ele_file_name)
    if elements.attributes.shape[1] > 1 or elements.triangles.shape[1] != 3:
        raise MeshFormatError(
            f"{ele_file_name}: {elements.triangles.shape[1]} corners and "
            f"{elements.attributes.shape[1]} attributes per triangle; the .mesh "
            "takes 3 corners and at most one attribute")
    positions = np.empty((len(table), 3))
    positions[:, 0] = table[:, 0] + lon
    positions[:, 1] = table[:, 1] + lat
    positions[:, 2] = table[:, 2] / MESH_Z_SCALE
    temporary = mesh_file_name + ".tmp" + str(os.getpid())
    with open(temporary, "w", encoding="ascii", newline="\n") as handle:
        handle.write("MeshVersionFormatted 2\nDimension 3\n\n")
        handle.write(f"Vertices\n{len(table)}\n")
        write_rows(handle, "%.15f %.15f %.15f 0\n", positions)
        handle.write(f"\nNormals\n{len(table)}\n")
        write_rows(handle, "%.2f %.2f 0\n", table[:, 3:5])
        handle.write(f"\nTriangles\n{elements.n_triangles}\n")
        if elements.attributes.shape[1]:
            attributes, _ = triangle_attributes(elements.attributes[:, 0], dummy)
            rows = np.column_stack([elements.triangles, attributes])
            write_rows(handle, "%d %d %d %d\n", rows)
        else:
            write_rows(handle, "%d %d %d\n", elements.triangles)
    os.replace(temporary, mesh_file_name)
