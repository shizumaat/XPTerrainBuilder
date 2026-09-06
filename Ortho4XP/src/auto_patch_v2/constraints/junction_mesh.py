"""JUNCTION BODIES ARE PRICED BY THEIR MESH (RULINGS 2026-09-04y, applying
04t-3): "a junction body chord whose endpoints lie on stretches of
DIFFERENT letters is not a law edge — v2 prices junction bodies as the
oracle does (triangle planes at the stretch cap; centreline chords per
stretch), never as all-pairs across letters."

THE RULE, per face of a role in ``emit.within_shape.junction_mesh_roles``:

* THE MESH is the face's own Delaunay triangulation, built exactly as the
  v1 oracle builds it (``grade_graph.mesh_edge_keys``: GEOS Delaunay over
  the ring's vertices, triangles whose centroid lies inside the face) and
  PUBLISHED as sidecar ``mesh_edges`` so the oracle consumes v2's mesh
  1:1 (``MeshEdgesExact``) instead of re-triangulating the emitted ring.
  A TRIANGLE WITH AN EDGE LEAVING ITS FACE IS NOT A PLANE ROW and its
  edges are not mesh edges (RULINGS 2026-09-05ae(1), the same rule as
  the apron chord's: a chord across a hole or a re-entrant is not a
  surface path; ``geometry.face_cover`` at the snap tolerance).
* A MESH EDGE (ring edges included) is priced at the cap of the crossing
  stretch NEAREST its midpoint — perpendicular distance to the stretch
  polyline, strictest on a tie, the face's own cap when no stretch
  crosses the face (``stretches.nearest_line_cap``).  A mesh edge with a
  PAD endpoint holds the pad's cap (the frontage rule, 09-01g).
* A TRIANGLE's plane gradient is bound at the cap of the crossing
  stretch NEAREST ITS CENTROID (the 16 half-plane linearisation of
  ``taxi.plane_rows``): the plane is what X-Plane renders.  Triangles on
  the A side of a face crossed by an A and a D stretch are at 3 %, on the
  D side at 1.5 %.  A triangle STRADDLING the two is at its centroid's
  stretch while each of its edges keeps its own cap — a plane bound is
  isotropic, so binding a straddling triangle at the stricter letter
  would forbid the ruling's own example (X ↔ the next G node at 3 % is
  the G edge of a triangle whose third edge lies on the D stretch).
* THE COMMON-STRETCH PAIRS (both vertices on one stretch) are the
  verify reader's population at that stretch's cap over the ROUTE
  (``taxi.taxi_pair_routes`` with ``common_only``, RULINGS 2026-09-05ab);
  the solve states them by the CHAIN (05ac: the stretch's centreline
  edges and the vertices' lateral hops, ``taxi.taxi_chain``), never as
  pair rows; every other chord of the face is NOT a law edge and
  produces no row anywhere.

The verify reader (``verify/within.py``) prices the same population from
the published ``mesh_edges`` and ``stretches``; the v1 oracle prices the
same mesh edges at the same nearest-stretch cap
(``check_grade`` JUNCTION STRETCH CAPS, reading sidecar ``stretches``).
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import role_cap, snap_margin_m
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .geometry import chords_covered, face_cover
from .precedence import View, view
from .stretches import Stretches, nearest_line_cap, stretches
from .taxi import pad_vertices, plane_rows

__all__ = ["junction_mesh", "face_triangles", "face_mesh_edges",
           "mesh_edge_caps", "triangle_caps", "mesh_edges_ll", "junction_roles",
           "crossing_lines"]

GEN = "junction_mesh"
XY = tuple[float, float]
#: The oracle's vertex-matching precision for a triangle corner
#: (``grade_graph.mesh_edge_keys`` rounds to 3 dp).
_CORNER_DP = 3


def junction_roles(law: Law) -> frozenset[str]:
    return frozenset(law.tables.emit.within_shape.junction_mesh_roles)


def face_triangles(vw: View, fid: int) -> list[tuple[int, int, int]]:
    """The face's Delaunay triangles as vertex-id triples, the oracle's
    own construction (``mesh_edge_keys``): every triangle of the GEOS
    Delaunay over the ring (and hole) vertices whose centroid the face
    contains.  Degenerate faces yield no triangles (the ring edges alone
    then price the body, as in the oracle's fallback)."""
    from shapely.geometry import Polygon
    from shapely.ops import triangulate
    ring = vw.rings[fid]
    holes = vw.holes[fid]
    if len(ring) < 3:
        return []
    idx: dict[tuple[float, float], int] = {}
    for v in [*ring, *(h for hole in holes for h in hole)]:
        x, y = vw.xy[v]
        idx.setdefault((round(x, _CORNER_DP), round(y, _CORNER_DP)), v)
    try:
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in holes if len(h) >= 3])
        if (not poly.is_valid) or poly.is_empty or poly.area <= 0.0:
            return []
        tris = triangulate(poly)
    except Exception:  # a bad triangulation never aborts a build (oracle rule)
        return []
    cand: list[tuple[int, int, int]] = []
    for t in tris:
        if not poly.contains(t.centroid):
            continue
        ids = [idx.get((round(x, _CORNER_DP), round(y, _CORNER_DP)))
               for x, y in list(t.exterior.coords)[:-1]]
        if any(i is None for i in ids) or len(set(ids)) != 3:
            continue
        cand.append((ids[0], ids[1], ids[2]))  # type: ignore[arg-type]
    if not cand:
        return []
    # every edge inside the face, or the triangle is not a row (05ae-1)
    cover = face_cover(vw.face_ring_xy(fid), [[vw.xy[v] for v in h] for h in holes],
                       snap_margin_m(vw.law))
    segs = [(vw.xy[u], vw.xy[w]) for a, b, c in cand for u, w in ((a, b), (b, c), (c, a))]
    ok = chords_covered(cover, segs)
    return [tri for k, tri in enumerate(cand) if ok[3 * k] and ok[3 * k + 1] and ok[3 * k + 2]]


def face_mesh_edges(vw: View, fid: int,
                    tris: _t.Sequence[tuple[int, int, int]] | None = None
                    ) -> set[tuple[int, int]]:
    """The mesh EDGE set of a face: its ring (and hole) edges plus every
    triangle edge, as ``(min, max)`` id pairs."""
    out: set[tuple[int, int]] = set()
    for cyc in [vw.rings[fid], *vw.holes[fid]]:
        n = len(cyc)
        for i in range(n):
            a, b = cyc[i], cyc[(i + 1) % n]
            if a != b:
                out.add((min(a, b), max(a, b)))
    for a, b, c in (tris if tris is not None else face_triangles(vw, fid)):
        for u, w in ((a, b), (b, c), (c, a)):
            out.add((min(u, w), max(u, w)))
    return out


def crossing_lines(vw: View, st: Stretches, fid: int
                   ) -> list[tuple[list[XY], float]]:
    """The stretches crossing ``fid`` as ``(polyline m, cap)``."""
    return [([vw.xy[v] for v in st.items[sid].vertices], st.items[sid].cap_l)
            for sid in st.face_stretches.get(fid, ())]


def mesh_edge_caps(vw: View, lines: _t.Sequence[tuple[_t.Sequence[XY], float]],
                   edges: _t.Iterable[tuple[int, int]], base_cap: float
                   ) -> dict[tuple[int, int], float]:
    """Each mesh edge's cap: the crossing stretch nearest its midpoint."""
    out: dict[tuple[int, int], float] = {}
    for a, b in edges:
        (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
        out[(a, b)] = nearest_line_cap((0.5 * (ax + bx), 0.5 * (ay + by)),
                                       lines, base_cap)
    return out


def junction_mesh(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Mesh-edge rows and triangle-plane rows for every junction-mesh
    face (module docstring)."""
    vw = view(planar, law)
    st = stretches(planar, law)
    roles = junction_roles(law)
    if not roles:
        return []
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    pads = pad_vertices(vw)
    pad_cap = law.tables.common.roles["building"].longitudinal
    rows: list[Row] = []
    for f in vw.faces_of_role(roles):
        cap = role_cap(law, f.role, f.code_number, f.code_letter)
        if cap is None:
            continue
        lines = crossing_lines(vw, st, f.id)
        tris = face_triangles(vw, f.id)
        edges = face_mesh_edges(vw, f.id, tris)
        caps = mesh_edge_caps(vw, lines, edges, cap.longitudinal)
        src_e = Source(GEN, "junction mesh edge at the nearest stretch cap (04y)",
                       (f"face:{f.id}", f.ref))
        src_pad = Source(GEN, "common.roles.building frontage pair (09-01g)",
                         (f"face:{f.id}", f.ref))
        src_t = Source(GEN, "junction triangle plane_gradient at the stretch cap (04y)",
                       (f"face:{f.id}", f.ref))
        for (a, b), c in sorted(caps.items()):
            d = vw.dist(a, b)
            if d < min_d:
                continue
            if a in pads or b in pads:
                rows.append(Diff(a, b, min(c, pad_cap), d, src_pad))
            else:
                rows.append(Diff(a, b, c, d, src_e))
        for tri, tcap in triangle_caps(vw, lines, tris, cap.longitudinal).items():
            rows.extend(plane_rows(list(tri), vw.xy, tcap, src_t))
    return rows


def triangle_caps(vw: View, lines: _t.Sequence[tuple[_t.Sequence[XY], float]],
                  tris: _t.Iterable[tuple[int, int, int]], base_cap: float
                  ) -> dict[tuple[int, int, int], float]:
    """Each triangle's plane cap: the crossing stretch nearest its centroid."""
    out: dict[tuple[int, int, int], float] = {}
    for a, b, c in tris:
        (ax, ay), (bx, by), (cx, cy) = vw.xy[a], vw.xy[b], vw.xy[c]
        out[(a, b, c)] = nearest_line_cap(((ax + bx + cx) / 3.0, (ay + by + cy) / 3.0),
                                          lines, base_cap)
    return out


def mesh_edges_ll(planar: PlanarMap, law: Law) -> list[list[list[float]]]:
    """Sidecar ``mesh_edges``: every junction-mesh face's mesh edges as
    ``[[lat, lon], [lat, lon]]`` by vertex identity key (the v1 oracle's
    ``MeshEdgesExact`` and v2 verify consume exactly these)."""
    vw = view(planar, law)
    roles = junction_roles(law)
    out: list[list[list[float]]] = []
    seen: set[tuple[int, int]] = set()
    for f in vw.faces_of_role(roles):
        for a, b in sorted(face_mesh_edges(vw, f.id)):
            if (a, b) in seen:
                continue
            seen.add((a, b))
            ka, kb = planar.vertices[a].key, planar.vertices[b].key
            out.append([[ka[0], ka[1]], [kb[0], kb[1]]])
    return out
