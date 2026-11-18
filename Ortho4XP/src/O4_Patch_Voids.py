"""The patch's UNCOVERED HOLES: constrained in the mesh, never covered.

A v2 patch writes a face that has a hole as two closed ways: the face's
own ring (its holes FILLED — a closed way has no interior rings) and one
``o4_feature=gap_interior_ring`` way per hole the faces inside it do not
cover, carrying the HOST face's ``shapeID``
(``auto_patch_v2.emit.osm_adapter``).  The hole's interior minus the faces
inside it is ground the patch does not describe — a VOID — and it belongs
to the DEM.

MEASURED (owner, KDEN 1.0.557, 39.843615,-104.691320): ``include_patches``
took every closed way as a filled polygon, so the void of hole -12289
(448,092 m2 inside host ``adjacent_ground:taxi:F:zone1#32``, inner faces
65,308 m2) counted as patch coverage, took an INTERP_ALT seed, and the
R18-1b harmonic fill laid a plane from the ring heights across ~383,000 m2
of a drainage valley (up to +15.5 m over the lidar, a -4.8 m step).  The
tile carried 148 such holes (1.76 km2), KAPA 36, KBKF 3.

THE RULE: the hole ring stays a constrained ``PATCH_RING_MARKER`` edge (it
bounds the host's INTERP_ALT flood and holds the ring heights), but its
interior is subtracted from the HOST's polygon, so it is not in
``patches_area``, takes no INTERP_ALT seed, and the vector step records the
voids for the mesh step (:func:`write`), whose patch coverage
(``O4_Mesh_Utils.patch_coverage_polygon``) drops the arrangement cells that
lie in one (:func:`drop_void_cells`).  A face inside the hole is its own
closed way and stays covered.
"""
from __future__ import annotations

import json
import os

HOLE_FEATURE = "gap_interior_ring"
SIDECAR_SUFFIX = ".patch_voids.json"
SIDECAR_VERSION = 1


def is_hole(wtags) -> bool:
    """Whether a patch way's tags mark an uncovered hole ring."""
    return (wtags or {}).get("o4_feature") == HOLE_FEATURE


def host_key(wtags):
    """The host face a ring belongs to: its ``shapeID`` (a hole carries its
    host's), or ``None`` for a ring with no ``shapeID`` or a feature ring
    other than a hole (a structure rim or a bank foot is never a host)."""
    wtags = wtags or {}
    if wtags.get("o4_feature") not in (None, HOLE_FEATURE):
        return None
    return wtags.get("shapeID")


def holes_by_host(ways) -> dict:
    """``{shapeID: [hole polygon, ...]}`` of ``ways`` — ``(wtags, polygon)``
    pairs of ONE patch file (``shapeID`` is per file).  Invalid or empty
    hole polygons are left out: a ring that is not a polygon removes no
    coverage."""
    out: dict = {}
    for (wtags, polygon) in ways:
        if not is_hole(wtags) or polygon is None:
            continue
        key = host_key(wtags)
        if key is None or not polygon.is_valid or polygon.is_empty:
            continue
        out.setdefault(key, []).append(polygon)
    return out


def subtract_holes(polygon, holes):
    """The host ``polygon`` minus its ``holes``; the polygon itself when it
    has none or the difference fails (a hole is a refinement: losing it
    costs the void, never the host)."""
    if not holes:
        return polygon
    try:
        from shapely import ops
        covered = polygon.difference(ops.unary_union(holes))
    except Exception:
        return polygon
    return polygon if covered.is_empty else covered


def voids(hole_polygons, patches_area):
    """The union of the holes minus everything the patches cover (the faces
    inside the holes, another patch's rings) — the ground no patch
    describes.  An empty polygon when there is none."""
    from shapely import geometry, ops
    if not hole_polygons:
        return geometry.Polygon()
    try:
        out = ops.unary_union(hole_polygons)
        if patches_area is not None and not patches_area.is_empty:
            out = out.difference(patches_area)
        return out
    except Exception:
        return geometry.Polygon()


def sidecar_path(poly_file: str) -> str:
    """The voids sidecar beside the vector step's ``.poly``."""
    return poly_file + SIDECAR_SUFFIX


def write(poly_file: str, void_area) -> None:
    """Record ``void_area`` (tile-relative) beside ``poly_file``; a tile
    with no void removes a stale sidecar instead."""
    path = sidecar_path(poly_file)
    if void_area is None or void_area.is_empty:
        if os.path.exists(path):
            os.remove(path)
        return
    from shapely.geometry import mapping
    with open(path, "w") as handle:
        json.dump({"version": SIDECAR_VERSION,
                   "voids": mapping(void_area)}, handle)


def read(poly_file: str):
    """The voids recorded beside ``poly_file``, or ``None`` when there is no
    sidecar (a tile with no void, or a vector step that predates it — whose
    ``.poly`` then also seeded its holes, so a filled coverage matches it)."""
    path = sidecar_path(poly_file)
    if not os.path.exists(path):
        return None
    from shapely.geometry import shape
    with open(path) as handle:
        payload = json.load(handle)
    if payload.get("version") != SIDECAR_VERSION:
        raise ValueError(f"{path}: unknown version {payload.get('version')}")
    return shape(payload["voids"])


def drop_void_cells(cells, void_area):
    """The arrangement ``cells`` whose interior point is not in
    ``void_area``.  Judged on a point, not by overlap: the cells and the
    voids are the same rings written at two precisions (the ``.node`` and
    the patch), so a cell inside a void shares its boundary to ~1e-9."""
    if void_area is None or void_area.is_empty:
        return list(cells)
    from shapely.prepared import prep
    inside = prep(void_area)
    return [cell for cell in cells
            if not inside.contains(cell.representative_point())]
