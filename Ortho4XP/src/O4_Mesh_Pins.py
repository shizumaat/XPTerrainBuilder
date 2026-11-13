"""A PATCH-PINNED VERTEX KEEPS ITS PATCH VALUE IN THE MESH (#2034).

``O4_Mesh_Utils.post_process_nodes_altitudes`` gives a vertex its carried
(column 5) altitude only through the triangles around it: every corner of
an INTERP_ALT triangle takes column 5, every other vertex keeps the DEM
Triangle4XP sampled into column 2.  A patch node whose triangles are ALL
outside every INTERP_ALT region therefore came out at the DEM although the
patch pinned it -- the vertex is an endpoint of a ``PATCH_RING_MARKER``
edge (``O4_Mesh_Utils._patch_ring_vertex_indices``), the Dirichlet datum
of the whole patch treatment.

MEASURED: the owner's LGAV +37+023 mesh (Rebuild_cache, 2026-11-10) has
exactly one such vertex among its 31,106 pinned ones, node -6749 -- a
``structure_rim`` (``channel_wall:0``) breakline foot at 37.931596,
23.939012, an OPEN way outside every patch ring, carried 66.82 m, written
77.21 m, its six triangles all attribute 0.  KIAH +29-096 (2026-11-06)
has three, all ``structure_rim`` (``tunnel_wall``) feet: -6.59, -0.55 and
+0.25 m.  Every other pinned vertex already took its value through an
INTERP_ALT neighbour.

THE LAW: a pinned vertex no INTERP_ALT triangle reached takes its carried
value too, exactly as it would have through one; the attribute-0
triangles around it then run from the patch value to the DEM, as they do
outside every pavement ring.  WATER IS A DATUM (owner RULINGS 2026-09-09z
(3)) is kept: a pinned vertex on a water or sea triangle stays levelled,
unless it is the pavement ring's own shore vertex (#945) -- the same
per-vertex test the INTERP_ALT copy applies.
"""
from __future__ import annotations

__all__ = ["pin_stranded_patch_vertices"]


def pin_stranded_patch_vertices(vertices, pinned, interp_alt_tris,
                                water_valued, pavement_shore):
    """Write column 5 into the altitude of every vertex of ``pinned`` that
    no triangle of ``interp_alt_tris`` touches; returns those indices.

    ``vertices`` is the flat six-per-vertex array (x, y, altitude, normal
    x, normal y, carried altitude), changed in place.  The normal is
    zeroed as the INTERP_ALT copy zeroes it: the DEM's normal belongs to
    the DEM's surface, not to the patch's.  A vertex of ``water_valued``
    is skipped unless it is in ``pavement_shore``.
    """
    reached = {v for tri in interp_alt_tris for v in tri}
    stranded = sorted(
        v for v in pinned
        if v not in reached
        and (v not in water_valued or v in pavement_shore))
    for v in stranded:
        vertices[6 * v + 2] = vertices[6 * v + 5]
        vertices[6 * v + 3] = 0
        vertices[6 * v + 4] = 0
    return stranded
