"""THE PATCH'S OWN GROUND AT AN ARBITRARY POINT.

WHY THIS EXISTS.  An object renders its ``y = 0`` plane at
``mesh(placement.lat, placement.lon) + AGL`` (``object_anchor.py``
amendment A18), so anything that wants terrain to MEET a building base
has to know what elevation the built mesh will carry at that one point.
Until now the only answer came from a BUILT mesh — the post-mesh rebake
of the PREVIOUS build (``post_mesh.rebake_dsf_objects``), which is what
made object pads a cross-build convergence.  The owner's 2026-08-14
ruling ("OBJECT PADS: EMISSION-TIME RELATIVE") moves the resolution into
the same build: downstream of the one solve, the patch already knows the
surface it is about to hand the mesher, so it can evaluate itself.

WHAT THE MESHER DOES, and therefore what this reproduces.  A patch ring
enters Triangle4XP as a constrained edge loop whose nodes carry the
patched altitude; the mesher triangulates and then
``O4_Mesh_Utils.post_process_nodes_altitudes`` gives every patch-valued
vertex its own carried altitude, while a FREE INTERIOR vertex (one
Triangle4XP inserted to refine a face) is harmonically extended from the
patch-valued vertices of its face (R18-1b, Fable amendment 2026-08-12).
Both rules make the surface inside a patch face an interpolation of that
face's own ring values and nothing else — never the DEM.  So the value
at an interior point is:

    the ring's own vertex altitudes, linearly interpolated over a
    Delaunay triangulation of those vertices

which is exact wherever the mesher's face corners are ring nodes (the
common case, measured), and the planar limit of the harmonic extension
wherever it inserted free vertices — the harmonic extension reproduces a
plane exactly, so the two agree on any face whose authored boundary is
planar and differ only by the curvature of a non-planar one.  The
premise test that authorised this design measured that residual against
three built meshes; see ``docs/DEFERRED_VERIFICATION.md``.

THE FRAME.  ``O4_Mesh_Utils`` triangulates in ``(lon * cos(lat0), lat)``
(``VECT.scalx``).  A Delaunay triangulation is invariant under UNIFORM
scaling, and layout LOCAL METRES is exactly that frame scaled by
~111320 — so a field built in layout metres triangulates the same way
the mesher does.  Feeding raw ``(lon, lat)`` would NOT: the longitude
axis is stretched by ``1 / cos(lat0)`` and the triangulation can flip.
Callers pass a conformal frame; ``from_layout`` is the production one.

WHAT IT IS NOT.  Not a solver input and not a law: pads are additive
post-solve emission (weld-or-gap), so this only READS the surface the
solve already produced.  Nothing here moves a pavement vertex.
"""

from __future__ import annotations

import math

#: A role whose shapes are OBJECT PADS never hosts an evaluation: a pad
#: is what the caller is about to place, so reading one would make the
#: target self-referential.  Prefix-matched, because the pad family
#: spells itself ``object_pad`` / ``object_pad_blend``.
PAD_ROLE_PREFIX = "object_pad"

#: Degenerate-triangle guard on the barycentric determinant, in the
#: caller's own frame squared.  Below this the three corners are
#: collinear to numerical precision and the face carries no plane.
_DEGENERATE_DET = 1e-18


def _open_ring(coords, alts):
    """``(coords, alts)`` with any closing repeat removed.

    ``BuiltShape.node_altitudes`` is one value per CLOSED-ring vertex
    while shapely exteriors also repeat the first point, and the two
    trims are the same trim — done once, here, so a caller can never
    pair an open coord list with a closed altitude list (the off-by-one
    that ``verification._shape_vertex_altitudes`` and
    ``adjacent_ground._shape_ring_values`` each re-derive locally).
    """
    coords = list(coords)
    alts = list(alts)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    alts = alts[: len(coords)]
    return coords, alts


class PatchGroundField:
    """The emitted patch's ground, evaluable at any point in its frame.

    ``shapes`` — ``(role, coords, alts)`` triples in ONE conformal
    planar frame (see the module docstring).  ``coords`` is a ring, open
    or closed; ``alts`` its per-vertex absolute altitudes.  Pad roles are
    dropped at construction rather than at the query, so the index and
    any linear reference can never disagree about what a host is.

    The field is READ-ONLY and built once per layout; every query is a
    covering test plus one point location.
    """

    def __init__(self, shapes) -> None:
        from shapely.geometry import Polygon

        self._rows = []
        for role, coords, alts in shapes:
            if role and str(role).startswith(PAD_ROLE_PREFIX):
                continue
            ring, values = _open_ring(coords, alts)
            if len(ring) < 3 or len(values) < len(ring):
                continue
            try:
                polygon = Polygon(ring)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
            except Exception:                         # pragma: no cover
                continue
            if polygon.is_empty or polygon.geom_type != "Polygon":
                continue
            self._rows.append((role, polygon, ring, values))
        self._tree = None
        if self._rows:
            try:
                from shapely.strtree import STRtree

                self._tree = STRtree([r[1] for r in self._rows])
            except Exception:                         # pragma: no cover
                self._tree = None
        self._triangulations: dict = {}

    def __len__(self) -> int:
        return len(self._rows)

    # ── host resolution ───────────────────────────────────────────────

    def host_index(self, x: float, y: float):
        """The index of the shape whose surface governs ``(x, y)``.

        When shapes NEST — a terminal apron inside a graded strip — the
        mesher's constrained edges make the INNERMOST ring the one whose
        values bound the face, so the smallest covering shape wins.  The
        tie is broken on area only; no role precedence is invented here,
        because precedence is a law and this module carries none.
        """
        from shapely.geometry import Point

        point = Point(x, y)
        if self._tree is not None:
            candidates = [int(i) for i in self._tree.query(point)]
        else:                                         # pragma: no cover
            candidates = range(len(self._rows))
        covering = [i for i in candidates
                    if self._rows[i][1].covers(point)]
        if not covering:
            return None
        return min(covering, key=lambda i: self._rows[i][1].area)

    def host_role(self, x: float, y: float):
        index = self.host_index(x, y)
        return None if index is None else self._rows[index][0]

    # ── evaluation ────────────────────────────────────────────────────

    def _triangulation(self, index: int):
        hit = self._triangulations.get(index)
        if hit is not None:
            return hit
        import numpy

        _role, _polygon, ring, values = self._rows[index]
        points = numpy.asarray(ring, dtype=float)
        try:
            from scipy.spatial import Delaunay

            triangulation = Delaunay(points)
        except Exception:                             # pragma: no cover
            triangulation = None
        hit = (triangulation, points,
               numpy.asarray(values, dtype=float))
        self._triangulations[index] = hit
        return hit

    def value_at(self, x: float, y: float):
        """``(value, host_role)`` — the patch's ground at ``(x, y)``.

        ``(None, None)`` when no emitted shape covers the point: there
        the mesh drapes the ambient DEM and the patch authors nothing,
        which is a real answer and never approximated here.  ``(None,
        role)`` when a shape covers the point but its own ring cannot
        place it (a degenerate or self-touching ring whose Delaunay hull
        excludes the point) — reported as a MISS rather than filled in,
        so a caller never mistakes a fallback for a patch value.
        """
        index = self.host_index(x, y)
        if index is None:
            return None, None
        role = self._rows[index][0]
        triangulation, points, values = self._triangulation(index)
        if triangulation is None:                     # pragma: no cover
            return None, role
        import numpy

        simplex = int(triangulation.find_simplex(
            numpy.asarray([[x, y]], dtype=float))[0])
        if simplex < 0:
            return None, role
        corners = triangulation.simplices[simplex]
        ax, ay = points[corners[0]]
        bx, by = points[corners[1]]
        cx, cy = points[corners[2]]
        determinant = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(determinant) < _DEGENERATE_DET:        # pragma: no cover
            return None, role
        wa = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / determinant
        wb = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / determinant
        wc = 1.0 - wa - wb
        value = (wa * values[corners[0]]
                 + wb * values[corners[1]]
                 + wc * values[corners[2]])
        if not math.isfinite(value):                  # pragma: no cover
            return None, role
        return float(value), role


def shapes_from_layout(layout):
    """``(role, coords, alts)`` for every valued shape of a layout.

    Local METRES, the layout's own frame — which is the mesher's frame
    up to a uniform scale (module docstring).  A shape with no altitude
    representation at all is skipped, not defaulted: it authors nothing
    the mesher will carry.
    """
    from .clearance import _open_coords
    from .verification import _shape_vertex_altitudes

    out = []
    for shape in getattr(layout, "shapes", ()) or ():
        polygon = getattr(shape, "polygon", None)
        if polygon is None or polygon.is_empty:
            continue
        if polygon.geom_type != "Polygon":
            continue
        try:
            coords = _open_coords(polygon)
        except Exception:                             # pragma: no cover
            continue
        if len(coords) < 3:
            continue
        alts = _shape_vertex_altitudes(shape, len(coords))
        if not alts:
            continue
        out.append((shape.role, coords, alts))
    return out


def field_from_layout(layout) -> PatchGroundField:
    """The layout's ground field, in layout local metres."""
    return PatchGroundField(shapes_from_layout(layout))
