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
bounds the host's INTERP_ALT flood and holds the ring heights), but it
covers nothing, and its VOID (:func:`voids`: the hole minus the faces
inside it) is taken out of ``patches_area`` — so it takes no INTERP_ALT
seed — and recorded for the mesh step (:func:`write`), whose patch coverage
(``O4_Mesh_Utils.patch_coverage_polygon``) drops the arrangement cells that
lie in one (:func:`drop_void_cells`).  A face inside the hole is its own
closed way and stays covered.  A hole the emitter did NOT write (covered,
hairline, or edge-coincident) stays filled, as before.
"""
from __future__ import annotations

import json
import os

HOLE_FEATURE = "gap_interior_ring"
#: The tag that marks ANY ring as an uncovered hole, whatever its
#: ``o4_feature`` -- the custom-patch blend band's inner foot ring
#: (``O4_Patch_Band``, #2173) is a ``bank_foot`` AND a void.
VOID_TAG = ("o4_void", "yes")
SIDECAR_SUFFIX = ".patch_voids.json"
SIDECAR_VERSION = 1


def is_hole(wtags) -> bool:
    """Whether a patch way's tags mark an uncovered hole ring."""
    wtags = wtags or {}
    return (wtags.get("o4_feature") == HOLE_FEATURE
            or wtags.get(VOID_TAG[0]) == VOID_TAG[1])


def voids(hole_polygons, cover_polygons):
    """The ground no patch describes: each hole minus the faces INSIDE it
    — a cover polygon no larger than the hole whose interior point lies in
    it (the emitter's own test, ``osm_adapter._hole_cover``) — unioned.

    Judged per hole, never as "the holes minus everything covered": a face
    whose OWN hole the emitter suppressed (its ring edges are another
    face's ring, RULINGS 2026-09-14g item 5) still writes that hole FILLED,
    and at KDEN that is how the void above stayed covered — ``pav2``
    ``cross_connector`` #351's 457,176 m2 hole IS ``adjacent_ground:taxi:F:
    zone1#32``'s ring, so it ships no way, and #351's filled ring covered
    the void of #32's emitted hole.  An emitted hole is the patch saying
    "void here" whatever encloses it.  An empty polygon when there is none."""
    from shapely import geometry, ops
    from shapely.strtree import STRtree
    if not hole_polygons:
        return geometry.Polygon()
    covers = [p for p in cover_polygons if p is not None and not p.is_empty]
    tree = STRtree(covers) if covers else None
    out = []
    for hole in hole_polygons:
        try:
            inside = [] if tree is None else [
                covers[int(j)] for j in tree.query(hole)
                if covers[int(j)].area <= hole.area * 1.001
                and hole.contains(covers[int(j)].representative_point())]
            void = hole.difference(ops.unary_union(inside)) if inside else hole
        except Exception:
            continue        # a refinement: losing it costs that void only
        if not void.is_empty:
            out.append(void)
    try:
        return ops.unary_union(out) if out else geometry.Polygon()
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
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
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
    with open(path, encoding="utf-8") as handle:
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
