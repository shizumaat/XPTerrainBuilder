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
* A TRIANGLE's plane gradient is bound ANISOTROPICALLY (RULINGS
  2026-09-06k (2), superseding 04y's isotropic cone): the component of
  ``∇z`` ALONG the serving centreline's direction at that stretch's
  LONGITUDINAL cap and the component ACROSS it at the stretch's
  TRANSVERSE cap (``rulesets.<authority>.taxi`` by letter) — TWO
  two-sided rows per triangle (``taxi.box_rows``), a BOX, never the
  16-half-plane cone.  The serving stretch is the crossing stretch
  NEAREST the triangle's centroid (strictest on a tie), its direction
  the nearest segment of that stretch's polyline there; a face no
  stretch crosses is served by the nearest stretch of the map at the
  face's own caps (the ``_junction_letter`` inheritance: the nearest
  through-route minted it); a map with no taxi stretch states no plane
  row (the mesh edges alone price the body).  Why: the isotropic cone
  bounds ANY two points of a junction by cap × their STRAIGHT distance —
  the chord law the owner withdrew (05aa) re-entering through the
  bounded cells (HECA pav132's 695 m of planes carried +10.05 m of the
  05C/23C hard chain); the box lets the body fall across the serving
  taxiway at the transverse cap (04t-2/3) while holding the taxi grade
  along it.  Triangles on the A side of a face crossed by an A and a D
  stretch are boxed at A's caps, on the D side at D's; a triangle
  STRADDLING the two takes its centroid's stretch while each of its
  edges keeps its own cap.
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

import math
import typing as _t

from ..law import Law
from ..law.tables import role_cap, snap_margin_m
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .geometry import chords_covered, face_cover, project_to_chain
from .precedence import View, view
from .stretches import Stretches, nearest_line_cap, stretches
from .taxi import (BOX_RULING, GEN as TAXI_GEN, PricedPair, axis_index,
                   box_pair_rows, box_rows, pad_vertices, taxi_pair_routes)

__all__ = ["junction_mesh", "face_triangles", "face_mesh_edges",
           "mesh_edge_caps", "triangle_caps", "triangle_boxes", "mesh_edges_ll",
           "junction_roles", "crossing_lines", "crossing_axes", "stretch_axes",
           "nearest_axis"]

GEN = "junction_mesh"
XY = tuple[float, float]
#: ``generate`` publishes ``junction_mesh.box_pairs``: the short pairs of
#: the mesh population boxed (RULINGS 2026-09-06s; ``taxi.taxi_box``).
STATS: dict[str, dict[str, int]] = {}
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


#: A stretch as the box law reads it: ``(polyline m, cap_l, cap_t)``.
Axis = tuple[list[XY], float, float]


def crossing_axes(vw: View, st: Stretches, fid: int) -> list[Axis]:
    """The stretches crossing ``fid`` as ``(polyline m, cap_l, cap_t)``."""
    return [([vw.xy[v] for v in st.items[sid].vertices],
             st.items[sid].cap_l, st.items[sid].cap_t)
            for sid in st.face_stretches.get(fid, ())]


def stretch_axes(vw: View, st: Stretches) -> list[Axis]:
    """Every stretch of the map as ``(polyline m, cap_l, cap_t)`` — the
    fallback population of a face no stretch crosses."""
    return [([vw.xy[v] for v in s.vertices], s.cap_l, s.cap_t) for s in st.items]


def nearest_axis(p: XY, axes: _t.Sequence[Axis], tie_m: float = 1e-6
                 ) -> tuple[tuple[float, float], float, float] | None:
    """The serving stretch at ``p``: ``(unit direction, cap_l, cap_t)`` of
    the axis nearest ``p`` by perpendicular distance — the direction of
    its nearest segment; the STRICTEST longitudinal cap among axes tied
    within ``tie_m`` (the direction of that one); ``None`` with no
    axis."""
    best: tuple[float, float, float, tuple[float, float]] | None = None
    for pts, cap_l, cap_t in axes:
        if len(pts) < 2:
            continue
        d, k, _t_, _s = project_to_chain(p, pts)
        (ax, ay), (bx, by) = pts[k], pts[k + 1]
        n = math.hypot(bx - ax, by - ay)
        if n < 1e-12:
            continue
        u = ((bx - ax) / n, (by - ay) / n)
        if best is None or d < best[0] - tie_m or \
                (abs(d - best[0]) <= tie_m and cap_l < best[1]):
            best = (d, float(cap_l), float(cap_t), u)
    if best is None:
        return None
    return best[3], best[1], best[2]


def triangle_boxes(vw: View, axes: _t.Sequence[Axis],
                   tris: _t.Iterable[tuple[int, int, int]],
                   fallback: _t.Sequence[Axis] = (),
                   face_caps: tuple[float, float] | None = None
                   ) -> dict[tuple[int, int, int], tuple[tuple[float, float], float, float]]:
    """Each triangle's box: ``(unit axis, cap_along, cap_across)`` from the
    crossing stretch nearest its centroid; with no crossing stretch, the
    nearest of ``fallback`` (the map's stretches) for the DIRECTION at
    the face's own ``face_caps``; a triangle with no serving stretch at
    all has no box."""
    out: dict[tuple[int, int, int], tuple[tuple[float, float], float, float]] = {}
    for a, b, c in tris:
        (ax, ay), (bx, by), (cx, cy) = vw.xy[a], vw.xy[b], vw.xy[c]
        cen = ((ax + bx + cx) / 3.0, (ay + by + cy) / 3.0)
        hit = nearest_axis(cen, axes)
        if hit is None and fallback and face_caps is not None:
            fb = nearest_axis(cen, fallback)
            if fb is not None:
                hit = (fb[0], face_caps[0], face_caps[1])
        if hit is not None:
            out[(a, b, c)] = hit
    return out


def junction_mesh(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Mesh-edge rows and triangle BOX rows for every junction-mesh face
    (module docstring)."""
    vw = view(planar, law)
    st = stretches(planar, law)
    roles = junction_roles(law)
    if not roles:
        return []
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    box_max = law.tables.emit.within_shape.withdrawn_chord_min_m
    pads = pad_vertices(vw)
    pad_cap = law.tables.common.roles["building"].longitudinal
    all_axes: list[Axis] | None = None
    index = axis_index(vw, st)
    # the junction faces' common-stretch pairs, the publication's own
    # (cached) population — never a second O(n²) walk of the rings
    common_pairs: dict[int, list[PricedPair]] = {}
    if index:
        for pr in taxi_pair_routes(planar, law, airport):
            common_pairs.setdefault(pr.face, []).append(pr)
    stats = STATS.setdefault("junction_mesh", {"box_pairs": 0})
    stats["box_pairs"] = 0
    rows: list[Row] = []
    for f in vw.faces_of_role(roles):
        cap = role_cap(law, f.role, f.code_number, f.code_letter)
        if cap is None:
            continue
        lines = crossing_lines(vw, st, f.id)
        tris = face_triangles(vw, f.id)
        edges = face_mesh_edges(vw, f.id, tris)
        caps = mesh_edge_caps(vw, lines, edges, cap.longitudinal)
        # THE SHORT-PAIR BOX over the mesh population (RULINGS 2026-09-06s;
        # ``taxi`` module docstring): every mesh edge and every common-
        # stretch pair (04y) under ``withdrawn_chord_min_m``, a taxi row
        pop: dict[tuple[int, int], float] = {}
        for a, b in edges:
            pop[(a, b)] = vw.dist(a, b)
        for pr in common_pairs.get(f.id, ()):
            pop.setdefault((min(pr.a, pr.b), max(pr.a, pr.b)), pr.d_chord)
        if index:
            src_box = Source(TAXI_GEN, BOX_RULING, (f"face:{f.id}", f.ref))
            got = box_pair_rows(vw, index, ((a, b, d) for (a, b), d in sorted(pop.items())
                                            if min_d <= d < box_max), src_box)
            stats["box_pairs"] += len(got)
            rows.extend(got)
        src_e = Source(GEN, "junction mesh edge at the nearest stretch cap (04y)",
                       (f"face:{f.id}", f.ref))
        src_pad = Source(GEN, "common.roles.building frontage pair (09-01g)",
                         (f"face:{f.id}", f.ref))
        src_t = Source(GEN, "junction triangle plane box along the serving stretch "
                            "(06k-2: longitudinal along, transverse across)",
                       (f"face:{f.id}", f.ref))
        for (a, b), c in sorted(caps.items()):
            d = vw.dist(a, b)
            if d < min_d:
                continue
            if a in pads or b in pads:
                rows.append(Diff(a, b, min(c, pad_cap), d, src_pad))
            else:
                rows.append(Diff(a, b, c, d, src_e))
        axes = crossing_axes(vw, st, f.id)
        if not axes and tris:
            if all_axes is None:
                all_axes = stretch_axes(vw, st)
            fallback = all_axes
        else:
            fallback = ()
        boxes = triangle_boxes(vw, axes, tris, fallback, (cap.longitudinal, cap.transverse))
        for tri, (axis, cl, ct) in boxes.items():
            rows.extend(box_rows(list(tri), vw.xy, axis, cl, ct, src_t))
    return rows


def triangle_caps(vw: View, lines: _t.Sequence[tuple[_t.Sequence[XY], float]],
                  tris: _t.Iterable[tuple[int, int, int]], base_cap: float
                  ) -> dict[tuple[int, int, int], float]:
    """Each triangle's LONGITUDINAL cap: the crossing stretch nearest its
    centroid (the box's along-axis cap; ``triangle_boxes`` carries the
    axis and the transverse cap)."""
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
