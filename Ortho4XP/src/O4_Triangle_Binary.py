# OrthoStudio XP, Copyright (C) 2026 radioharris. Free software under the GNU GPL: see LICENSE.
# Additional terms (GPL v3 section 7) apply to radioharris's material in this file: see NOTICE.
#
# Ported from OrthoStudio XP (https://github.com/radioharris/orthostudio-xp),
# src/orthostudio/mesh/triangle_io.py (binary half) at
# 7c028d82dcc59a27296972973aa0663ef37efddc.  Modified for XPTerrainBuilder,
# 2026-10-17 (RULINGS 2026-10-17c / 17a Q6, mesh-io-spec §4): the readers
# return O4_Triangle_IO's NodeTable / Elements (so one post-treatment reads
# either encoding), the .poly is converted from this engine's text .poly
# (Triangle's own text semantics for a region without an area), the
# O4_TRIANGLE_IO flag and the binary-capability probe are added.  LICENSE
# here is Ortho4XP/Licence/gpl.txt; NOTICE is
# Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE.
"""The binary exchange files of Triangle4XP ``-b`` (OSXPNOD1 / OSXPPOL1 / OSXPELE1).

Integers are int32 and reals float64, native byte order (little-endian on
every supported platform); layouts as in ``Utils/Triangle4XP-CHANGES.md``.
Vertex numbers are kept as Triangle numbers them (1-based here).  Chosen by
``O4_TRIANGLE_IO=binary`` (default ``text``) and only when the Triangle4XP
binary carries the switch (``binary_capable``) and the run does not refine
(``-r`` reads a text ``.ele``; Triangle4XP refuses ``-b`` with it).  An
``iterate`` run refines the previous run's ``.node`` / ``.ele``, which a
binary run left binary: ``refine_inputs_as_text`` turns them back into text
before the ``-r`` run.
"""

import os
import struct

import numpy as np

from O4_Triangle_IO import (Elements, NodeTable, TriangleFormatError, read_ele_text,
                            read_node_text, read_poly_segments, write_ele_text,
                            write_node_text)

__all__ = [
    "ELE_MAGIC",
    "NODE_MAGIC",
    "POLY_MAGIC",
    "TRIANGLE_IO_ENV",
    "adopt_binary_outputs",
    "binary_capable",
    "binary_inputs",
    "binary_requested",
    "read_ele",
    "read_ele_binary",
    "read_node",
    "read_node_binary",
    "read_poly_holes_regions",
    "refine_inputs_as_text",
    "use_binary_io",
    "write_ele_binary",
    "write_node_binary",
    "write_poly_binary",
]

NODE_MAGIC = b"OSXPNOD1"
POLY_MAGIC = b"OSXPPOL1"
ELE_MAGIC = b"OSXPELE1"
_MAGIC_LEN = 8
TRIANGLE_IO_ENV = "O4_TRIANGLE_IO"

_NODE_HEADER = struct.Struct("=5i")  # n_vertices, dim, n_attrs, n_markers, first_number
_ELE_HEADER = struct.Struct("=4i")  # n_triangles, n_corners, n_attrs, first_number
_SEG_HEADER = struct.Struct("=2i")  # n_segments, seg_markers
_COUNT = struct.Struct("=i")
_F64 = np.dtype("=f8")
_I32 = np.dtype("=i4")


def binary_requested() -> bool:
    """``O4_TRIANGLE_IO=binary`` (anything else, or unset, is text)."""
    return os.environ.get(TRIANGLE_IO_ENV, "text").strip().lower() == "binary"


def use_binary_io(executable, refine) -> bool:
    """Whether this mesh run exchanges binary files with Triangle4XP:
    requested, not refining (``-r``), and the binary carries ``-b``."""
    return binary_requested() and not refine and binary_capable(executable)


_CAPABLE = {}


def binary_capable(executable) -> bool:
    """Whether the Triangle4XP at ``executable`` carries ``-b`` (its image
    holds the OSXPPOL1 magic).  A binary without it would read a binary
    ``.poly`` as text, so the caller falls back to text.  Cached per path
    and modification time."""
    try:
        key = (executable, os.stat(executable).st_mtime_ns)
    except OSError:
        return False
    if key not in _CAPABLE:
        with open(executable, "rb") as handle:
            _CAPABLE[key] = POLY_MAGIC in handle.read()
    return _CAPABLE[key]


def _read_exact(handle, n, what):
    data = handle.read(n)
    if len(data) != n:
        raise TriangleFormatError(f"unexpected end of file while reading {what}")
    return data


def _read_array(handle, dtype, shape, what):
    count = int(np.prod(shape)) if shape else 0
    data = _read_exact(handle, count * dtype.itemsize, what)
    return np.frombuffer(data, dtype=dtype).reshape(shape)


def _expect_magic(handle, magic, path):
    got = _read_exact(handle, _MAGIC_LEN, "magic")
    if got != magic:
        raise TriangleFormatError(f"{path}: expected magic {magic!r}, found {got!r}")


def _write_node_body(handle, points, markers=None, first_number=1):
    points = np.ascontiguousarray(points, dtype=_F64)
    handle.write(_NODE_HEADER.pack(points.shape[0], 2, points.shape[1] - 2,
                                   0 if markers is None else 1, first_number))
    handle.write(points.tobytes())
    if markers is not None:
        handle.write(np.ascontiguousarray(markers, dtype=_I32).tobytes())


def _read_node_body(handle, path):
    n, dim, n_attrs, n_markers, first = _NODE_HEADER.unpack(
        _read_exact(handle, _NODE_HEADER.size, "node header"))
    if dim != 2 or n_attrs < 0 or n < 0:
        raise TriangleFormatError(f"{path}: bad node header {(n, dim, n_attrs, n_markers)}")
    points = _read_array(handle, _F64, (n, 2 + n_attrs), "vertex table")
    markers = _read_array(handle, _I32, (n,), "vertex markers") if n_markers else None
    return points, markers, first


def write_node_binary(path, points, markers=None, first_number=1) -> None:
    """Write an ``OSXPNOD1`` file: ``points`` (n, 2 + n_attrs) float64."""
    with open(path, "wb") as handle:
        handle.write(NODE_MAGIC)
        _write_node_body(handle, points, markers, first_number)


def read_node_binary(path) -> NodeTable:
    """Read an ``OSXPNOD1`` file as a NodeTable (markers, when present, are
    the last column of ``values``, as in the text reader)."""
    with open(path, "rb") as handle:
        _expect_magic(handle, NODE_MAGIC, path)
        points, markers, first = _read_node_body(handle, path)
    values = points if markers is None else np.column_stack([points, markers])
    return NodeTable(ids=np.arange(first, first + len(points), dtype=np.int64),
                     values=np.array(values, dtype=np.float64),
                     header_line=None, trailer_line=None)


def read_poly_holes_regions(path) -> tuple:
    """``(holes (h, 2), regions (r, 4))`` of a text ``.poly``; a region with
    no area field takes its attribute as area, as Triangle's text reader
    does (``readholes``: ``regionlist[index] = regionlist[index - 1]``)."""
    with open(path, "rb") as handle:
        lines = [line.split() for line in handle.read().split(b"\n")]
    rows = iter([fields for fields in lines if fields and not fields[0].startswith(b"#")])
    header = next(rows)
    for _ in range(int(header[0])):
        next(rows)
    for _ in range(int(next(rows)[0])):
        next(rows)
    holes = np.array([[float(x) for x in next(rows)[1:3]]
                      for _ in range(int(next(rows)[0]))]).reshape(-1, 2)
    region_header = next(rows, None)
    regions = []
    for _ in range(int(region_header[0]) if region_header else 0):
        fields = next(rows)
        if len(fields) < 4:
            raise TriangleFormatError(f"{path}: region line with fewer than 3 values")
        regions.append([float(x) for x in fields[1:4]]
                       + [float(fields[4] if len(fields) > 4 else fields[3])])
    return holes, np.array(regions, dtype=np.float64).reshape(-1, 4)


def write_poly_binary(path, poly_text_path) -> None:
    """Write the ``OSXPPOL1`` twin of this engine's text ``.poly`` (no
    vertices of its own: they live in the ``.node``)."""
    (segments, markers) = read_poly_segments(poly_text_path)
    (holes, regions) = read_poly_holes_regions(poly_text_path)
    with open(path, "wb") as handle:
        handle.write(POLY_MAGIC)
        handle.write(_NODE_HEADER.pack(0, 2, 0, 0, 1))
        handle.write(_SEG_HEADER.pack(len(segments), 0 if markers is None else 1))
        handle.write(np.ascontiguousarray(segments, dtype=_I32).tobytes())
        if markers is not None:
            handle.write(np.ascontiguousarray(markers, dtype=_I32).tobytes())
        handle.write(_COUNT.pack(len(holes)))
        handle.write(np.ascontiguousarray(holes, dtype=_F64).tobytes())
        handle.write(_COUNT.pack(len(regions)))
        handle.write(np.ascontiguousarray(regions, dtype=_F64).tobytes())


def write_ele_binary(path, triangles, attributes, first_number=1) -> None:
    """Write an ``OSXPELE1`` file (what Triangle4XP ``-b`` writes; tests)."""
    triangles = np.ascontiguousarray(triangles, dtype=_I32)
    attributes = np.ascontiguousarray(attributes, dtype=_F64).reshape(len(triangles), -1)
    with open(path, "wb") as handle:
        handle.write(ELE_MAGIC)
        handle.write(_ELE_HEADER.pack(len(triangles), triangles.shape[1],
                                      attributes.shape[1], first_number))
        handle.write(triangles.tobytes())
        handle.write(attributes.tobytes())


def read_ele_binary(path) -> Elements:
    """Read an ``OSXPELE1`` file (vertex numbers as written)."""
    with open(path, "rb") as handle:
        _expect_magic(handle, ELE_MAGIC, path)
        n, corners, n_attrs, _first = _ELE_HEADER.unpack(
            _read_exact(handle, _ELE_HEADER.size, "element header"))
        if corners not in (3, 6) or n < 0 or n_attrs < 0:
            raise TriangleFormatError(f"{path}: bad element header {(n, corners, n_attrs)}")
        triangles = _read_array(handle, _I32, (n, corners), "triangle table")
        attributes = _read_array(handle, _F64, (n, n_attrs), "triangle attributes")
    return Elements(triangles=triangles.astype(np.int64),
                    attributes=np.array(attributes, dtype=np.float64))


def _starts_with(path, magic) -> bool:
    with open(path, "rb") as handle:
        return handle.read(_MAGIC_LEN) == magic


def read_node(path) -> NodeTable:
    """A ``.node`` in either encoding (the magic decides)."""
    return read_node_binary(path) if _starts_with(path, NODE_MAGIC) else read_node_text(path)


def read_ele(path) -> Elements:
    """An ``.ele`` in either encoding (the magic decides)."""
    return read_ele_binary(path) if _starts_with(path, ELE_MAGIC) else read_ele_text(path)


def binary_inputs(node_file, poly_file) -> str:
    """Write the OSXPNOD1 / OSXPPOL1 twins of the text ``node_file`` and
    ``poly_file`` beside them (``<base>.b.node`` / ``<base>.b.poly``; the
    text step-1 products stay as they are) and return the ``.b.poly`` path
    Triangle4XP ``-b`` is given."""
    base = os.path.splitext(poly_file)[0] + ".b"
    nodes = read_node_text(node_file)
    write_node_binary(base + ".node", nodes.values, first_number=int(nodes.ids[0])
                      if nodes.n_vertices else 1)
    write_poly_binary(base + ".poly", poly_file)
    return base + ".poly"


def adopt_binary_outputs(binary_poly, output_node_file, output_ele_file) -> None:
    """Move Triangle4XP ``-b``'s ``<base>.b.1.node`` / ``.b.1.ele`` (and a
    text ``.b.1.poly`` when it wrote one) onto the names every later step
    reads, and delete the binary inputs.  The readers sniff the magic."""
    base = os.path.splitext(binary_poly)[0]
    os.replace(base + ".1.node", output_node_file)
    os.replace(base + ".1.ele", output_ele_file)
    if os.path.isfile(base + ".1.poly"):
        os.replace(base + ".1.poly",
                   os.path.splitext(output_ele_file)[0] + ".poly")
    for leftover in (base + ".node", base + ".poly"):
        if os.path.isfile(leftover):
            os.remove(leftover)


def refine_inputs_as_text(node_file, ele_file) -> bool:
    """Rewrite a binary ``node_file`` / ``ele_file`` (the previous run's
    outputs) as the text a ``-r`` run reads, in place; text files are left
    as they are.  The ``.node`` is written as the text post-treatment
    writes it (``write_node_text``'s ``%.15f``), so a refinement reads the
    same values in either IO mode.  Returns whether anything was rewritten."""
    converted = False
    if os.path.isfile(node_file) and _starts_with(node_file, NODE_MAGIC):
        with open(node_file, "rb") as handle:
            _expect_magic(handle, NODE_MAGIC, node_file)
            points, markers, _first = _read_node_body(handle, node_file)
        values = points if markers is None else np.column_stack([points, markers])
        header = f"{len(points)} 2 {points.shape[1] - 2} {0 if markers is None else 1}\n"
        write_node_text(node_file, header, values, "")
        converted = True
    if os.path.isfile(ele_file) and _starts_with(ele_file, ELE_MAGIC):
        elements = read_ele_binary(ele_file)
        write_ele_text(ele_file, elements.triangles, elements.attributes)
        converted = True
    return converted
