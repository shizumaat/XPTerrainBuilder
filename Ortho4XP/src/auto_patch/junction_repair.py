"""Junction-polygon elevation repair after the Laplacian solve.

Three concerns, four functions:

* ``_build_clamp_geom_state``: pre-compute spatial-index state of
  every other shape's boundary edges so individual junction
  vertices can be clamped fast.
* ``_clamp_junction_free_vertices``: walk each junction's free
  ring vertices and clamp their elevation to the union of
  feasibility bands implied by every neighbour boundary point
  within ``NEIGHBOUR_CLAMP_RADIUS_M``.
* ``_subdivide_violating_junctions``: split junctions that still
  contain a > ``SUBDIVIDE_VIOLATION_GRADE`` edge after clamp; the
  cut line passes through the worst-grade pair so each new
  sub-polygon admits a feasible elevation field.
* ``_merge_sliver_junctions_into_neighbours``: opposite direction —
  fold tiny sliver junctions into their largest neighbour so JOSM
  doesn't show duplicate-looking polygons.

Public API:
    _build_clamp_geom_state(layout)
    _clamp_junction_free_vertices(layout, geom_state)
    _subdivide_violating_junctions(layout)
    _merge_sliver_junctions_into_neighbours(layout, *, icao)
"""
from __future__ import annotations

import math

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

import O4_UI_Utils as UI

# Narrow exception tuple for shapely / numeric-geometry failure
# modes.  Programming errors propagate so they surface immediately.
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

from .canonical_points import snap_polygon_through_registry
from .geom_safe import min_rotated_rect
from .elevation import (
    NEIGHBOUR_CLAMP_RADIUS_M,
    TAXI_MAX_GRADE,
    _corner_elevation_bucket,
)
from .layout import (
    BuiltShape,
    PavementLayout,
    ROLE_APRON,
    ROLE_CROSS_CONNECTOR,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_STUB,
    ROLE_BUILDING,
    SHARED_VERTEX_TOL_M,
    corner_alts_from_high_low,
)


__all__ = [
    "SUBDIVIDE_MAX_PAIR_DIST_M",
    "SUBDIVIDE_MIN_AREA_M2",
    "SUBDIVIDE_SNAP_RADIUS_M",
    "SUBDIVIDE_VIOLATION_GRADE",
    "_build_clamp_geom_state",
    "_clamp_junction_free_vertices",
    "_merge_sliver_junctions_into_neighbours",
    "_subdivide_violating_junctions",
    "source_clip_partial_coverage_shapes",
]


def _build_clamp_geom_state(
        layout: "PavementLayout"
        ) -> tuple[list, list, dict, set] | None:
    """Build the GEOMETRY-ONLY state used by
    :func:`_clamp_junction_free_vertices`.

    The clamp's spatial grid + shared-bucket set are functions of
    polygon geometry alone; only the per-edge elevations change
    between iterations.  Hoisting this build out of the per-call
    body lets the outer fixed-point loop reuse it without
    rebuilding (8+ × cost saved at HECA).

    Returns ``(edge_geom, edge_endpoints, grid, shared_buckets)``
    where:

    * ``edge_geom``:    list of ``(shape_idx, vi_a, vi_b, ax, ay,
                        bx, by)`` — vertex indices index into
                        ``layout.shapes[shape_idx]``'s exterior
                        coords (closed ring's prefix, i.e. the last
                        repeat dropped) so the caller can read
                        current elevations per call.
    * ``edge_endpoints``: bucket key pair per edge (for
                          incident-edge skip).
    * ``grid``:         spatial bucket → list of edge indices.
    * ``shared_buckets``: buckets touched by ≥ 2 shapes.

    Returns None when ``layout.anchor`` is unset.
    """
    if layout.anchor is None:
        return None

    edge_geom: list[tuple[int, int, int,
                          float, float, float, float]] = []
    edge_endpoints: list[tuple[tuple[int, int],
                                tuple[int, int]]] = []
    bucket_count: dict[tuple[int, int], int] = {}
    for si, s in enumerate(layout.shapes):
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if not coords:
            continue
        for (cx, cy) in coords:
            bucket = _corner_elevation_bucket(cx, cy)
            bucket_count[bucket] = bucket_count.get(bucket, 0) + 1
        n = len(coords)
        for i in range(n):
            ax, ay = coords[i]
            bx, by = coords[(i + 1) % n]
            edge_geom.append((si, i, (i + 1) % n,
                               ax, ay, bx, by))
            edge_endpoints.append((
                _corner_elevation_bucket(ax, ay),
                _corner_elevation_bucket(bx, by)))

    shared_buckets = {b for b, c in bucket_count.items() if c >= 2}

    grid: dict[tuple[int, int], list[int]] = {}
    cell = NEIGHBOUR_CLAMP_RADIUS_M
    for ei, (_, _, _, ax, ay, bx, by) in enumerate(edge_geom):
        x0, x1 = (ax, bx) if ax <= bx else (bx, ax)
        y0, y1 = (ay, by) if ay <= by else (by, ay)
        ix0 = int(math.floor((x0 - cell) / cell))
        ix1 = int(math.floor((x1 + cell) / cell))
        iy0 = int(math.floor((y0 - cell) / cell))
        iy1 = int(math.floor((y1 + cell) / cell))
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                grid.setdefault((ix, iy), []).append(ei)

    return (edge_geom, edge_endpoints, grid, shared_buckets)


def _clamp_junction_free_vertices(
        layout: "PavementLayout",
        geom_state: tuple[list, list, dict, set] | None = None,
        ) -> int:
    """Per-junction free-vertex clamp using every nearby shape
    boundary as a soft anchor (Layer 2).

    Returns the number of free-vertex elevations that changed
    (informational).  Mutates each junction's
    ``node_altitudes`` and ``altitude`` in place.

    When ``geom_state`` is supplied (from
    :func:`_build_clamp_geom_state`), the geometry-only spatial
    grid + shared-bucket set is reused across iterations of the
    outer fixed-point loop.  Falls back to building it on first
    call when the caller doesn't.
    """
    if layout.anchor is None:
        return 0
    if geom_state is None:
        geom_state = _build_clamp_geom_state(layout)
        if geom_state is None:
            return 0
    edge_geom, edge_endpoints, grid, shared_buckets = geom_state
    cell = NEIGHBOUR_CLAMP_RADIUS_M

    # Read current per-shape elevation arrays once per call so the
    # inner clamp loop can look up edge endpoint elevations by
    # (shape_idx, vertex_idx) without re-parsing shapes per edge.
    shape_elevs: dict[int, list[float]] = {}
    for si, s in enumerate(layout.shapes):
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords_n = len(s.polygon.exterior.coords)
            if coords_n > 0 and (
                s.polygon.exterior.coords[0]
                == s.polygon.exterior.coords[-1]
            ):
                coords_n -= 1
        except _GEOM_EXC:
            continue
        if coords_n <= 0:
            continue
        if s.altitude is not None:
            shape_elevs[si] = [float(s.altitude)] * coords_n
        elif (s.altitude_high is not None
              and s.altitude_low is not None
              and coords_n == 4):
            shape_elevs[si] = corner_alts_from_high_low(
                s.altitude_high, s.altitude_low)
        elif s.node_altitudes is not None:
            na = list(s.node_altitudes)
            if len(na) == coords_n + 1:
                na = na[:-1]
            if len(na) == coords_n:
                shape_elevs[si] = [float(e) for e in na]

    # Reconstruct the boundary_edges layout used downstream
    # ``(shape_idx, ax, ay, bx, by, ea, eb)`` with current elevs.
    boundary_edges: list[tuple[int, float, float, float, float,
                                float, float]] = []
    boundary_edges_append = boundary_edges.append
    for (si, vi_a, vi_b, ax, ay, bx, by) in edge_geom:
        elevs = shape_elevs.get(si)
        if elevs is None:
            # Skip shapes that didn't yield a valid elev array.
            boundary_edges_append((si, ax, ay, bx, by, 0.0, 0.0))
            continue
        boundary_edges_append((si, ax, ay, bx, by,
                                elevs[vi_a], elevs[vi_b]))

    rect_like_roles = {ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL,
                       ROLE_SECONDARY_PARALLEL, ROLE_STUB,
                       ROLE_CROSS_CONNECTOR, ROLE_BUILDING}

    n_changed = 0
    for si, s in enumerate(layout.shapes):
        if s.role != ROLE_JUNCTION:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        if not coords:
            continue
        # Build per-vertex elevations and FREE-vs-anchored flags.
        if s.altitude is not None:
            elevs = [float(s.altitude)] * len(coords)
            uniform_alt = True
        elif s.node_altitudes is not None:
            na = list(s.node_altitudes)
            if len(na) == len(coords) + 1:
                na = na[:-1]
            if len(na) != len(coords):
                continue
            elevs = [float(e) for e in na]
            uniform_alt = False
        else:
            continue
        # A vertex is ANCHORED if its bucket is shared with another
        # shape (rect/runway/terminal or another junction with the
        # same coord).  We check via the shared_buckets set.
        is_anchor = []
        for (cx, cy) in coords:
            b = _corner_elevation_bucket(cx, cy)
            is_anchor.append(b in shared_buckets)
        # Now clamp each FREE vertex.
        new_elevs = list(elevs)
        for vi, (cx, cy) in enumerate(coords):
            if is_anchor[vi]:
                continue
            ix = int(math.floor(cx / cell))
            iy = int(math.floor(cy / cell))
            lo_v = float("-inf")
            hi_v = float("inf")
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    bucket = (ix + dx, iy + dy)
                    if bucket not in grid:
                        continue
                    v_bucket = _corner_elevation_bucket(cx, cy)
                    for ei in grid[bucket]:
                        (s_other, ax, ay, bx, by,
                         ea, eb) = boundary_edges[ei]
                        # Per user 2026-05-18: cross-shape grade
                        # enforcement happens ONLY at shared corners
                        # (via the OSM emitter's altitude-aware
                        # vertex bucketing).  Two non-shared shapes
                        # — a taxiway 70 m parallel to a runway, for
                        # example — must be free to slope
                        # independently along their own axes.
                        # Restrict the clamp to same-junction edges
                        # so cross-shape proximity doesn't impose a
                        # phantom grade constraint.
                        if s_other != si:
                            continue
                        # Skip ONLY edges incident to THIS vertex —
                        # they trivially equal the vertex's own
                        # elevation and would lock it in place.
                        ek0, ek1 = edge_endpoints[ei]
                        if v_bucket == ek0 or v_bucket == ek1:
                            continue
                        edx = bx - ax
                        edy = by - ay
                        seg2 = edx * edx + edy * edy
                        if seg2 < 0.04:
                            continue
                        t = ((cx - ax) * edx + (cy - ay) * edy) / seg2
                        if t < 0.0:
                            t = 0.0
                        elif t > 1.0:
                            t = 1.0
                        ccx = ax + t * edx
                        ccy = ay + t * edy
                        d = math.hypot(cx - ccx, cy - ccy)
                        if d > NEIGHBOUR_CLAMP_RADIUS_M:
                            continue
                        e_at = ea + t * (eb - ea)
                        band = max(d, 0.01) * TAXI_MAX_GRADE
                        if e_at - band > lo_v:
                            lo_v = e_at - band
                        if e_at + band < hi_v:
                            hi_v = e_at + band
            if lo_v > hi_v:
                # Conflicting nearby anchors — pick midpoint as a
                # least-squares-style compromise.  Layer 1 will
                # eventually reconcile the source corners.
                target = 0.5 * (lo_v + hi_v)
            else:
                target = elevs[vi]
                if target < lo_v:
                    target = lo_v
                if target > hi_v:
                    target = hi_v
            target = round(target, 1)
            if abs(target - elevs[vi]) > 0.05:
                new_elevs[vi] = target
                n_changed += 1
        # Persist changes.
        if uniform_alt:
            # Was a single altitude; if any free vertex shifted, we
            # have to switch to per-vertex node_altitudes.
            if any(abs(new_elevs[i] - elevs[i]) > 0.05
                   for i in range(len(elevs))):
                elev_range = max(new_elevs) - min(new_elevs)
                if elev_range < 0.05:
                    s.altitude = round(
                        sum(new_elevs) / len(new_elevs), 1)
                else:
                    s.altitude = None
                    closed = list(new_elevs) + [new_elevs[0]]
                    s.node_altitudes = closed
        else:
            # Already per-vertex.  Update node_altitudes (ring +
            # closing repeat).
            closed = list(new_elevs) + [new_elevs[0]]
            s.node_altitudes = closed
            # If everything collapsed to one value, switch back to
            # flat altitude.
            elev_range = max(new_elevs) - min(new_elevs)
            if elev_range < 0.05:
                s.altitude = round(
                    sum(new_elevs) / len(new_elevs), 1)
                s.node_altitudes = None
    return n_changed


SUBDIVIDE_VIOLATION_GRADE = 0.02   # 2 % — attempt subdivision
                                    # whenever the worst within-
                                    # shape pair exceeds the taxi
                                    # grade cap.  Lowered from 10 %
                                    # on 2026-05-05: the per-surface
                                    # solver leaves residual 1.5–3 %
                                    # violations on very large
                                    # junctions sitting over DEM
                                    # spikes; cutting them lets
                                    # each sub-polygon converge to
                                    # its own DEM-floor.
SUBDIVIDE_MAX_PAIR_DIST_M = 60.0   # only consider pairs within
                                    # this radius — same as
                                    # check_grade's
                                    # WITHIN_SHAPE_MAX_PAIR_DIST_M
                                    # (Triangle4XP-plausible edge).
SUBDIVIDE_MIN_AREA_M2 = 5.0        # don't emit sub-polygons
                                    # smaller than this — they'd
                                    # become slivers and re-trigger
                                    # the sliver-corner safety net.


SUBDIVIDE_SNAP_RADIUS_M = 5.0      # snap new cut-line vertices
                                    # to existing ring vertices when
                                    # within this radius.  Without
                                    # snapping, the cut introduces
                                    # 0.5-2 m new vertices very
                                    # close to existing ones; the
                                    # interpolated-vs-original
                                    # elevation mismatch over those
                                    # tiny distances produces huge
                                    # spurious grade percentages
                                    # (worse than the original
                                    # violation we were trying to fix).


def _subdivide_violating_junctions(layout: "PavementLayout") -> int:
    """Split junction polygons whose worst within-shape vertex pair
    exceeds ``SUBDIVIDE_VIOLATION_GRADE`` along a perpendicular
    cut through the midpoint of the violating pair.

    Cut-vertex placement: new vertices created where the cut line
    intersects the polygon boundary are SNAPPED to existing ring
    vertices within ``SUBDIVIDE_SNAP_RADIUS_M``.  Without snapping,
    the cut creates ring-adjacent vertex pairs spaced 0.5-2 m apart
    whose interpolated-vs-original elevations differ by small
    amounts — registering as huge grade percentages
    (e.g. 0.4 m / 0.5 m = 73.9 %) that are WORSE than the original
    violation we were trying to fix.

    Validation: a sub-polygon is only accepted when its own worst
    within-shape vertex pair is BETTER (smaller grade) than the
    parent's worst pair.  If the cut would produce a sub-polygon
    that's MORE violating, the original is kept and the cut is
    abandoned — prevents the iterative subdivision from making
    things worse.

    Returns the number of polygons that were subdivided
    (informational).
    """
    if not layout.shapes:
        return 0
    from shapely.geometry import LineString
    from shapely.ops import split as _shapely_split
    n_subdivided = 0
    new_shapes: list[BuiltShape] = []
    for s in layout.shapes:
        if s.role != ROLE_JUNCTION:
            new_shapes.append(s)
            continue
        if s.polygon is None or s.polygon.is_empty:
            new_shapes.append(s)
            continue
        try:
            ring = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        n = len(ring)
        if n < 4:
            new_shapes.append(s)
            continue
        if s.altitude is not None:
            elevs = [float(s.altitude)] * n
        elif s.node_altitudes is not None:
            na = list(s.node_altitudes)
            if len(na) == n + 1:
                na = na[:-1]
            if len(na) != n:
                new_shapes.append(s)
                continue
            elevs = [float(e) for e in na]
        else:
            new_shapes.append(s)
            continue

        def _worst_grade(pts: list[tuple[float, float]],
                         es: list[float]) -> tuple[float,
                                                    tuple[int, int] | None]:
            """Worst all-pair Euclidean grade within the polygon.
            Per user 2026-05-18: junction grade applies across the
            entire interior surface, not just along centerlines —
            same rule as aprons."""
            radius2 = SUBDIVIDE_MAX_PAIR_DIST_M ** 2
            min_d2 = 0.5 ** 2
            wg = 0.0
            wp = None
            m = len(pts)
            for a in range(m):
                xa, ya = pts[a]
                ea = es[a]
                for b in range(a + 1, m):
                    xb, yb = pts[b]
                    dx_ = xa - xb
                    dy_ = ya - yb
                    d2_ = dx_ * dx_ + dy_ * dy_
                    if d2_ < min_d2 or d2_ > radius2:
                        continue
                    d_ = math.sqrt(d2_)
                    de_ = abs(ea - es[b])
                    if de_ <= TAXI_MAX_GRADE * d_ + 0.10:
                        continue
                    g_ = de_ / d_
                    if g_ > wg:
                        wg = g_
                        wp = (a, b)
            return wg, wp

        worst_grade, worst_pair = _worst_grade(ring, elevs)
        if (worst_pair is None
                or worst_grade < SUBDIVIDE_VIOLATION_GRADE):
            new_shapes.append(s)
            continue
        # Build the perpendicular cut line through the midpoint.
        i, j = worst_pair
        pi = ring[i]
        pj = ring[j]
        mx = 0.5 * (pi[0] + pj[0])
        my = 0.5 * (pi[1] + pj[1])
        dx = pj[0] - pi[0]
        dy = pj[1] - pi[1]
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            new_shapes.append(s)
            continue
        # Perpendicular unit vector (rotate +90°).
        px = -dy / seg_len
        py = dx / seg_len
        bx_min, by_min, bx_max, by_max = s.polygon.bounds
        bbox_diag = math.hypot(bx_max - bx_min, by_max - by_min)
        L = max(bbox_diag * 2.0, 1000.0)
        cut = LineString([
            (mx - L * px, my - L * py),
            (mx + L * px, my + L * py),
        ])
        try:
            parts = _shapely_split(s.polygon, cut)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        sub_polys: list[Polygon] = []
        try:
            for g in getattr(parts, "geoms", [parts]):
                if (g is None or g.is_empty
                        or g.geom_type != "Polygon"
                        or g.area < SUBDIVIDE_MIN_AREA_M2):
                    continue
                sub_polys.append(g)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        if len(sub_polys) < 2:
            new_shapes.append(s)
            continue

        # Pre-compute snap-target ring vertices keyed by their
        # squared snap radius for O(n) lookup per sub-vertex.
        snap_r2 = SUBDIVIDE_SNAP_RADIUS_M ** 2

        def _snap_to_ring(qx: float, qy: float
                          ) -> tuple[float, float, int]:
            """Return the closest ring vertex within snap radius
            and its index, or ``(qx, qy, -1)`` if no ring vertex
            is close enough.
            """
            best_k = -1
            best_d2 = snap_r2
            for k in range(n):
                rx, ry = ring[k]
                d2 = (rx - qx) ** 2 + (ry - qy) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best_k = k
            if best_k >= 0:
                rx, ry = ring[best_k]
                return rx, ry, best_k
            return qx, qy, -1

        def _lookup_elev(qx: float, qy: float, hint_idx: int
                         ) -> float:
            """Look up elevation for sub-polygon vertex.  When
            ``hint_idx`` ≥ 0 (snapped to ring vertex) use the
            original elevation directly.  Otherwise interpolate
            along the closest original ring edge.
            """
            if hint_idx >= 0:
                return elevs[hint_idx]
            best_d2 = float("inf")
            best_e = elevs[0]
            for k in range(n):
                ax, ay = ring[k]
                bx, by = ring[(k + 1) % n]
                edx = bx - ax
                edy = by - ay
                seg2 = edx * edx + edy * edy
                if seg2 < 1e-9:
                    continue
                t = ((qx - ax) * edx + (qy - ay) * edy) / seg2
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                ccx = ax + t * edx
                ccy = ay + t * edy
                d2 = (qx - ccx) ** 2 + (qy - ccy) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    ea = elevs[k]
                    eb = elevs[(k + 1) % n]
                    best_e = ea + t * (eb - ea)
            return round(float(best_e), 1)

        # Build snapped sub-polygons + per-vertex elevations.
        # Acceptance criterion: each sub-polygon's own worst pair
        # must be MEASURABLY better (≥ 0.5 % grade improvement)
        # than the parent's worst.  This prevents cuts that
        # technically separate the worst pair but introduce new
        # cut-line-vertex pairs of similar magnitude (the bug
        # that made the relaxed version worse than the strict).
        validated_subs: list[tuple[Polygon, list[tuple[float, float]],
                                    list[float]]] = []
        cut_was_useful = True
        for sp in sub_polys:
            sub_ring_raw = list(sp.exterior.coords)
            if sub_ring_raw and sub_ring_raw[0] == sub_ring_raw[-1]:
                sub_ring_raw = sub_ring_raw[:-1]
            snapped_pts: list[tuple[float, float]] = []
            snapped_hints: list[int] = []
            for (qx, qy) in sub_ring_raw:
                sx, sy, hint = _snap_to_ring(qx, qy)
                if (snapped_pts and abs(snapped_pts[-1][0] - sx) < 1e-9
                        and abs(snapped_pts[-1][1] - sy) < 1e-9):
                    continue  # consecutive dup after snap
                snapped_pts.append((sx, sy))
                snapped_hints.append(hint)
            while (len(snapped_pts) >= 2
                   and abs(snapped_pts[0][0]
                           - snapped_pts[-1][0]) < 1e-9
                   and abs(snapped_pts[0][1]
                           - snapped_pts[-1][1]) < 1e-9):
                snapped_pts.pop()
                snapped_hints.pop()
            if len(snapped_pts) < 3:
                cut_was_useful = False
                break
            try:
                snapped_poly = Polygon(snapped_pts)
                if not snapped_poly.is_valid:
                    snapped_poly = snapped_poly.buffer(0)
                if (snapped_poly.is_empty
                        or snapped_poly.geom_type != "Polygon"
                        or snapped_poly.area < SUBDIVIDE_MIN_AREA_M2):
                    cut_was_useful = False
                    break
            except _GEOM_EXC:
                cut_was_useful = False
                break
            sub_elevs = [_lookup_elev(qx, qy, h)
                         for (qx, qy), h
                         in zip(snapped_pts, snapped_hints)]
            sub_worst, _ = _worst_grade(snapped_pts, sub_elevs)
            if sub_worst >= worst_grade - 0.005:
                cut_was_useful = False
                break
            validated_subs.append(
                (snapped_poly, snapped_pts, sub_elevs))

        if not cut_was_useful or len(validated_subs) < 2:
            # Fallback: iso-elevation cut.  When the perpendicular
            # cut through the worst-pair midpoint can't be validated
            # (typically because it produces a tiny sliver containing
            # the high-z corners + cut endpoints, whose own worst
            # pair isn't measurably better), try cutting along the
            # MEDIAN-elevation contour instead.  Walk ring edges; an
            # edge "crosses" the median when its endpoints straddle
            # it.  For a polygon that wraps two distinct elevation
            # regions (SPLP junction-10053: 4 corners at z=70, 2 at
            # z=77), exactly two edges cross — a clean cut between
            # the crossing midpoints separates the two regions.
            iso_subs = _try_iso_elevation_cut(
                s, ring, elevs, worst_grade)
            if iso_subs is not None and len(iso_subs) >= 2:
                validated_subs = iso_subs
            else:
                new_shapes.append(s)
                continue

        _registry = getattr(layout, "canonical_points", None)
        for sp, sub_pts, sub_elevs in validated_subs:
            # Route through registry so the cut produces canonical
            # corner coordinates shared with the parent ring's
            # vertices (which are already in the registry).
            if _registry is not None:
                snapped_sp = snap_polygon_through_registry(
                    sp, _registry)
                if (snapped_sp is None or snapped_sp.is_empty
                        or snapped_sp.geom_type != "Polygon"):
                    continue
                sp = snapped_sp
            sub_shape = BuiltShape(
                polygon=sp, role=ROLE_JUNCTION, ref=s.ref)
            elev_range = max(sub_elevs) - min(sub_elevs)
            if elev_range < 0.05:
                sub_shape.altitude = round(
                    sum(sub_elevs) / len(sub_elevs), 1)
            else:
                closed = list(sub_elevs) + [sub_elevs[0]]
                sub_shape.node_altitudes = closed
            new_shapes.append(sub_shape)
        n_subdivided += 1
    layout.shapes = new_shapes
    return n_subdivided


def _try_iso_elevation_cut(  # noqa: C901 (long helper, see body)
    s: "BuiltShape",
    ring: list[tuple[float, float]],
    elevs: list[float],
    parent_worst_grade: float,
) -> list[tuple["Polygon", list[tuple[float, float]],
                         list[float]]] | None:
    """Cut a junction polygon along its median-elevation contour.

    Returns a list of validated sub-polygons (each
    ``(polygon, snapped_pts, sub_elevs)``) or ``None`` if the cut
    isn't applicable.

    Rationale: when the polygon wraps two distinct elevation regions
    (e.g. corners 0-3 at z=70, corners 4-5 at z=77), the
    perpendicular-cut subdivide produces a tiny corner-sliver that
    fails validation.  An iso-elevation cut walks ring edges,
    finds the two edges where elevation crosses the median (between
    z_min and z_max), and cuts from one crossing point to the other.
    Each resulting sub-polygon has elevation range half the parent's.
    """
    n = len(ring)
    if n < 4:
        return None
    z_min = min(elevs)
    z_max = max(elevs)
    if z_max - z_min < 0.5:
        return None
    median = 0.5 * (z_min + z_max)
    crossings: list[tuple[float, float, int]] = []
    for k in range(n):
        z_a = elevs[k]
        z_b = elevs[(k + 1) % n]
        if (z_a < median) == (z_b < median):
            continue  # both on same side
        if abs(z_b - z_a) < 1e-6:
            continue  # too flat to interpolate
        t = (median - z_a) / (z_b - z_a)
        if t <= 0.001 or t >= 0.999:
            continue
        ax, ay = ring[k]
        bx, by = ring[(k + 1) % n]
        cx = ax + t * (bx - ax)
        cy = ay + t * (by - ay)
        crossings.append((cx, cy, k))
    if len(crossings) != 2:
        return None
    from shapely.geometry import LineString
    from shapely.ops import split as _shapely_split
    cx0, cy0, _ = crossings[0]
    cx1, cy1, _ = crossings[1]
    cut = LineString([(cx0, cy0), (cx1, cy1)])
    try:
        parts = _shapely_split(s.polygon, cut)
    except _GEOM_EXC:
        return None
    sub_polys: list[Polygon] = []
    for g in getattr(parts, "geoms", [parts]):
        if (g is None or g.is_empty
                or g.geom_type != "Polygon"
                or g.area < SUBDIVIDE_MIN_AREA_M2):
            continue
        sub_polys.append(g)
    if len(sub_polys) < 2:
        return None
    snap_r2 = SUBDIVIDE_SNAP_RADIUS_M ** 2

    def _snap_to_ring(qx: float, qy: float
                      ) -> tuple[float, float, int]:
        best_k = -1
        best_d2 = snap_r2
        for k in range(n):
            rx, ry = ring[k]
            d2 = (rx - qx) ** 2 + (ry - qy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_k = k
        if best_k >= 0:
            rx, ry = ring[best_k]
            return rx, ry, best_k
        return qx, qy, -1

    def _lookup_elev(qx: float, qy: float, hint_idx: int) -> float:
        if hint_idx >= 0:
            return elevs[hint_idx]
        best_d2 = float("inf")
        best_e = elevs[0]
        for k in range(n):
            ax, ay = ring[k]
            bx, by = ring[(k + 1) % n]
            edx = bx - ax
            edy = by - ay
            seg2 = edx * edx + edy * edy
            if seg2 < 1e-9:
                continue
            t = ((qx - ax) * edx + (qy - ay) * edy) / seg2
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            ccx = ax + t * edx
            ccy = ay + t * edy
            d2 = (qx - ccx) ** 2 + (qy - ccy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                ea = elevs[k]
                eb = elevs[(k + 1) % n]
                best_e = ea + t * (eb - ea)
        return round(float(best_e), 1)

    validated_subs: list[tuple[Polygon, list[tuple[float, float]],
                                list[float]]] = []
    for sp in sub_polys:
        sub_ring_raw = list(sp.exterior.coords)
        if sub_ring_raw and sub_ring_raw[0] == sub_ring_raw[-1]:
            sub_ring_raw = sub_ring_raw[:-1]
        snapped_pts: list[tuple[float, float]] = []
        snapped_hints: list[int] = []
        for (qx, qy) in sub_ring_raw:
            sx, sy, hint = _snap_to_ring(qx, qy)
            if (snapped_pts
                    and abs(snapped_pts[-1][0] - sx) < 1e-9
                    and abs(snapped_pts[-1][1] - sy) < 1e-9):
                continue
            snapped_pts.append((sx, sy))
            snapped_hints.append(hint)
        while (len(snapped_pts) >= 2
               and abs(snapped_pts[0][0] - snapped_pts[-1][0]) < 1e-9
               and abs(snapped_pts[0][1] - snapped_pts[-1][1]) < 1e-9):
            snapped_pts.pop()
            snapped_hints.pop()
        if len(snapped_pts) < 3:
            return None
        try:
            snapped_poly = Polygon(snapped_pts)
            if not snapped_poly.is_valid:
                snapped_poly = snapped_poly.buffer(0)
            if (snapped_poly.is_empty
                    or snapped_poly.geom_type != "Polygon"
                    or snapped_poly.area < SUBDIVIDE_MIN_AREA_M2):
                return None
        except _GEOM_EXC:
            return None
        sub_elevs = [_lookup_elev(qx, qy, h)
                     for (qx, qy), h
                     in zip(snapped_pts, snapped_hints)]
        # Compute this sub's worst-pair grade
        sub_worst = 0.0
        sm = len(snapped_pts)
        radius2 = SUBDIVIDE_MAX_PAIR_DIST_M ** 2
        for a in range(sm):
            xa, ya = snapped_pts[a]
            ea = sub_elevs[a]
            for b in range(a + 1, sm):
                xb, yb = snapped_pts[b]
                d2 = (xa - xb) ** 2 + (ya - yb) ** 2
                if d2 < 0.25 or d2 > radius2:
                    continue
                d_ = math.sqrt(d2)
                de_ = abs(ea - sub_elevs[b])
                if de_ <= TAXI_MAX_GRADE * d_ + 0.10:
                    continue
                g_ = de_ / d_
                if g_ > sub_worst:
                    sub_worst = g_
        # Iso cut should produce sub-polygons that are MEASURABLY
        # better; if not, this cut isn't useful either.
        if sub_worst >= parent_worst_grade - 0.005:
            return None
        validated_subs.append((snapped_poly, snapped_pts, sub_elevs))
    if len(validated_subs) < 2:
        return None
    return validated_subs


def _reinsert_lost_boundary_vertices(merged, sources,
                                     tol_m: float = 0.02):
    """Re-insert source-ring vertices that ``unary_union`` dissolved off the
    merged exterior even though they still LIE ON it (GEOS merges collinear
    segments when a shared edge is dissolved).  Those vertices are shared
    conformance anchors — e.g. a junction vertex at a stub's end corner; if
    the union silently drops it the stub is left ending in mid-air (HECA
    W2/B/Exit-2 after the conforming-cuts redesign produced residue pieces
    big enough to be sliver-merge targets).  Returns a Polygon with the
    on-boundary vertices restored (interiors preserved)."""
    from shapely.geometry import Polygon as _Poly
    try:
        ring = list(merged.exterior.coords)
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        have = {(round(x, 6), round(y, 6)) for x, y in ring}
        lost: list[tuple[float, float]] = []
        for src in sources:
            if src is None or src.is_empty:
                continue
            sc = list(src.exterior.coords)
            if sc and sc[0] == sc[-1]:
                sc = sc[:-1]
            for x, y in sc:
                if (round(x, 6), round(y, 6)) in have:
                    continue
                lost.append((float(x), float(y)))
        if not lost:
            return merged
        n = len(ring)
        inserts: dict[int, list[tuple[float, tuple[float, float]]]] = {}
        for px, py in lost:
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                dx, dy = bx - ax, by - ay
                seg2 = dx * dx + dy * dy
                if seg2 <= 1e-12:
                    continue
                t = ((px - ax) * dx + (py - ay) * dy) / seg2
                if t <= 1e-9 or t >= 1.0 - 1e-9:
                    continue
                qx, qy = ax + t * dx, ay + t * dy
                if (px - qx) ** 2 + (py - qy) ** 2 <= tol_m * tol_m:
                    inserts.setdefault(i, []).append((t, (px, py)))
                    break
        if not inserts:
            return merged
        out: list[tuple[float, float]] = []
        for i in range(n):
            out.append(ring[i])
            for _t, p in sorted(inserts.get(i, [])):
                out.append(p)
        rebuilt = _Poly(out, [r.coords for r in merged.interiors])
        if rebuilt.is_valid and not rebuilt.is_empty:
            return rebuilt
    except _GEOM_EXC:
        pass
    return merged


def _merge_sliver_junctions_into_neighbours(
        layout: "PavementLayout",
        icao: str = "",
        sliver_area_m2: float = 1000.0,
        sliver_ratio: float = 0.05,
        shared_vertex_tol_m: float = 0.5,
        ) -> int:
    """Merge small junction polygons into adjacent larger ones.

    A "sliver" is a junction polygon whose area is below
    ``sliver_area_m2`` AND whose ratio to a neighbour's area is
    below ``sliver_ratio``.  Two junctions are "adjacent" if they
    share at least 2 boundary vertices within
    ``shared_vertex_tol_m``.

    Common cause: ``_decompose_polygon_with_holes`` cuts a
    polygon-with-holes into simple pieces, occasionally carving
    off a tiny strip when the cut grazes the polygon's edge.
    The strip and main piece share a boundary segment (the cut
    line); the strip should be merged back.  Subdivision passes
    in ``_compute_elevations`` can produce similar slivers.

    Returns the number of slivers merged.
    """
    junction_idxs = [i for i, s in enumerate(layout.shapes)
                     if s.role == ROLE_JUNCTION
                     and s.polygon is not None
                     and not s.polygon.is_empty]
    if len(junction_idxs) < 2:
        return 0
    # Cache per-shape vertex sets in meter coords for fast tests.
    j_verts: dict[int, list[tuple[float, float]]] = {}
    for i in junction_idxs:
        try:
            coords = list(layout.shapes[i].polygon.exterior.coords)
        except _GEOM_EXC:
            j_verts[i] = []
            continue
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        j_verts[i] = coords
    tol2 = shared_vertex_tol_m * shared_vertex_tol_m
    merge_into: dict[int, int] = {}
    for i in junction_idxs:
        ai = layout.shapes[i].polygon.area
        if ai >= sliver_area_m2:
            continue
        best_idx: int | None = None
        best_area = 0.0
        for j in junction_idxs:
            if j == i:
                continue
            aj = layout.shapes[j].polygon.area
            if aj <= ai:
                continue
            if (ai / aj) > sliver_ratio:
                continue
            shared = 0
            for vx, vy in j_verts[i]:
                for ux, uy in j_verts[j]:
                    if (vx - ux) ** 2 + (vy - uy) ** 2 <= tol2:
                        shared += 1
                        break
                if shared >= 2:
                    break
            if shared >= 2 and aj > best_area:
                best_idx = j
                best_area = aj
        if best_idx is not None:
            merge_into[i] = best_idx
    if not merge_into:
        return 0
    # SPINE-EDGE VETO (user 2026-07-03, global slice): the slice cuts pav_union
    # ALONG the spine, so two adjacent faces' shared edge often IS a spine line;
    # unioning them dissolves that edge and its vertices, and the emitted patch
    # loses the spine nodes there (skeleton fidelity — a raw-slice face vertex
    # on the spine ended up 9 m from any emitted node).  A merge whose shared
    # boundary runs along a spine centerline is vetoed; merges across NON-spine
    # cuts (hole keyhole spurs, _decompose_polygon_with_holes cuts, tile-seam
    # edges) still clean up.
    import os as _os_v
    _veto_on = _os_v.environ.get("O4_SLIVER_SPINE_VETO", "1") == "1"
    _spine_tree = None
    _spine_lines: list = []
    if _veto_on:
        _spine_lines = [
            cl.line for cl in (getattr(layout, "apt_taxi_centerlines", None)
                               or [])
            if getattr(cl, "line", None) is not None
            and not cl.line.is_empty]
        if _spine_lines:
            from shapely.strtree import STRtree
            _spine_tree = STRtree(_spine_lines)

    def _shared_edge_carries_spine(a, b) -> bool:
        """True when a spine centerline runs along the shared boundary of the
        two polygons (any shared segment midpoint within SPINE_PERP_TOL_M).
        An OVERLAPPING pair is exempt (never vetoed): duplicate coverage
        violates the one-owner invariant and the merge is the fix — the veto
        protects only clean-abutting faces whose shared edge is a spine cut."""
        if _spine_tree is None:
            return False
        try:
            if a.intersection(b).area > 0.25:
                return False             # overlap → merge is the invariant fix
        except _GEOM_EXC:
            pass
        from .grade_graph import SPINE_PERP_TOL_M
        try:
            shared = a.exterior.intersection(b.exterior.buffer(0.1))
        except _GEOM_EXC:
            return True                  # can't prove the edge is safe → veto
        segs = ([shared] if shared.geom_type == "LineString"
                else [g for g in getattr(shared, "geoms", [])
                      if g.geom_type == "LineString"])
        for seg in segs:
            if seg.length < 0.2:
                continue
            mid = seg.interpolate(0.5, normalized=True)
            try:
                cand = _spine_tree.query(mid.buffer(SPINE_PERP_TOL_M))
            except _GEOM_EXC:
                cand = []
            for k in cand:
                if _spine_lines[int(k)].distance(mid) <= SPINE_PERP_TOL_M:
                    return True
        return False

    n_spine_veto = 0
    merged_slivers: set[int] = set()
    for sliver_i, target_j in merge_into.items():
        try:
            target_shape = layout.shapes[target_j]
            sliver_shape = layout.shapes[sliver_i]
            if _shared_edge_carries_spine(sliver_shape.polygon,
                                          target_shape.polygon):
                n_spine_veto += 1
                continue
            merged = unary_union([
                target_shape.polygon,
                sliver_shape.polygon])
            if (merged.geom_type == "Polygon"
                    and not merged.is_empty):
                # Restore shared conformance anchors the union dissolved
                # off the (collinear-merged) boundary — e.g. the junction
                # vertex at a stub's end corner.
                merged = _reinsert_lost_boundary_vertices(
                    merged, [target_shape.polygon,
                             sliver_shape.polygon])
                merged_slivers.add(sliver_i)
                # Build a per-vertex elevation lookup from the
                # ORIGINAL target + sliver vertices, then re-derive
                # node_altitudes for the merged polygon by nearest-
                # neighbour match.  Per user 2026-04-29 (CYXY apron
                # regression): just setting ``node_altitudes = None``
                # leaves the merged polygon with NO elevation at all
                # (no downstream re-derivation step exists), which
                # makes X-Plane interpolate from neighbour shapes
                # and produces the "terrain all over the place"
                # apron the user saw.
                lookup: list[tuple[float, float, float]] = []
                for src_shape in (target_shape, sliver_shape):
                    if not src_shape.node_altitudes:
                        # Sloped or flat alternatives.
                        if (src_shape.altitude_high is not None
                                and src_shape.altitude_low is not None):
                            avg = 0.5 * (
                                src_shape.altitude_high
                                + src_shape.altitude_low)
                        elif src_shape.altitude is not None:
                            avg = float(src_shape.altitude)
                        else:
                            continue
                        try:
                            sc = list(
                                src_shape.polygon.exterior.coords)
                        except _GEOM_EXC:
                            continue
                        if sc and sc[0] == sc[-1]:
                            sc = sc[:-1]
                        for sx, sy in sc:
                            lookup.append((sx, sy, float(avg)))
                        continue
                    src_alts = list(src_shape.node_altitudes)
                    try:
                        sc = list(src_shape.polygon.exterior.coords)
                    except _GEOM_EXC:
                        continue
                    if sc and sc[0] == sc[-1]:
                        sc = sc[:-1]
                    if (len(src_alts) == len(sc) + 1
                            and src_alts[0] == src_alts[-1]):
                        src_alts = src_alts[:-1]
                    for k, (sx, sy) in enumerate(sc):
                        if k >= len(src_alts):
                            break
                        lookup.append(
                            (sx, sy, float(src_alts[k])))
                if not lookup:
                    layout.shapes[target_j].polygon = merged
                    layout.shapes[target_j].node_altitudes = None
                    continue
                merged_coords = list(merged.exterior.coords)
                if (merged_coords
                        and merged_coords[0] == merged_coords[-1]):
                    merged_coords_open = merged_coords[:-1]
                else:
                    merged_coords_open = merged_coords
                new_alts: list[float] = []
                for mx, my in merged_coords_open:
                    best_d2 = float("inf")
                    best_alt = 0.0
                    for sx, sy, sa in lookup:
                        d2 = (mx - sx) ** 2 + (my - sy) ** 2
                        if d2 < best_d2:
                            best_d2 = d2
                            best_alt = sa
                    new_alts.append(round(best_alt, 1))
                # Closing-vertex repeat for the ring.
                if new_alts:
                    new_alts.append(new_alts[0])
                target_shape.polygon = merged
                target_shape.node_altitudes = new_alts
        except _GEOM_EXC:
            continue
    # Only remove slivers whose union actually succeeded — a vertex-touch
    # pair unions to a MultiPolygon (no merge applied); deleting the sliver
    # anyway would silently uncover its pavement.
    layout.shapes = [
        s for k, s in enumerate(layout.shapes)
        if k not in merged_slivers]
    try:
        UI.vprint(1,
            f"  [pav-builder] {icao}: merged "
            f"{len(merged_slivers)} sliver junction(s) into "
            f"adjacent larger junctions"
            + (f" ({n_spine_veto} vetoed on spine-carrying edges)."
               if n_spine_veto else "."))
    except _GEOM_EXC:
        pass
    return len(merged_slivers)


def _drop_thin_orphan_slivers(
        layout: "PavementLayout",
        icao: str = "",
        max_area_m2: float = 1000.0,
        min_aspect: float = 4.0,
        shared_vertex_tol_m: float = 0.5,
        ) -> int:
    """Drop thin sliver junction polygons that form residue along a
    stub / parallel rect's long edge.

    A "thin sliver" qualifies when ALL of:
      * Junction polygon area < ``max_area_m2``.
      * Aspect ratio (perimeter / (2*sqrt(pi*area))) > ``min_aspect``
        — i.e. shaped like a long thin strip, not a chunky polygon.
      * Shares ≥ 2 boundary vertices with a stub / primary_parallel
        / secondary_parallel / cross_connector (the rect whose long
        edge the sliver lies along).

    These typically form because the apt.dat row-110 pavement
    boundary curves inward between a stub's two end corners,
    leaving a thin pavement strip uncovered by the rect.  The
    strip gets emitted as a separate junction polygon that's
    geometrically isolated from the surrounding apron (only
    touches via stub-shared vertices, not via the apron boundary),
    so ``_merge_sliver_junctions_into_neighbours`` can't catch it
    (it requires ≥ 2 shared vertices with another JUNCTION).

    Dropping these slivers loses < 0.2 % of pavement coverage at
    typical airports but eliminates visible thin residue along
    diagonal-stub sloping edges (user 2026-05-12).

    Returns count of slivers dropped.
    """
    RECT_LIKE_ROLES = (
        ROLE_STUB, ROLE_PRIMARY_PARALLEL,
        ROLE_SECONDARY_PARALLEL, ROLE_CROSS_CONNECTOR,
    )
    junction_idxs = [i for i, s in enumerate(layout.shapes)
                     if s.role == ROLE_JUNCTION
                     and s.polygon is not None
                     and not s.polygon.is_empty]
    if not junction_idxs:
        return 0
    rect_idxs = [i for i, s in enumerate(layout.shapes)
                 if s.role in RECT_LIKE_ROLES
                 and s.polygon is not None
                 and not s.polygon.is_empty]
    if not rect_idxs:
        return 0

    # Cache per-shape open-ring vertices in meter coords.
    verts: dict[int, list[tuple[float, float]]] = {}
    for i in junction_idxs + rect_idxs:
        try:
            c = list(layout.shapes[i].polygon.exterior.coords)
        except _GEOM_EXC:
            verts[i] = []
            continue
        if c and c[0] == c[-1]:
            c = c[:-1]
        verts[i] = c

    tol2 = shared_vertex_tol_m * shared_vertex_tol_m

    # Relaxed sliver test (user 2026-05-29): a thin residue that forms between
    # a STRAIGHT rect long edge and a CURVED pavement boundary touches the rect
    # at only ONE corner (where chord meets arc), so the "≥2 shared corners"
    # gate misses it (SPJC stub C: junction #142, aspect 4.6, shares 1 corner).
    # Also drop a thin junction whose EVERY vertex lies within
    # ``ALONG_EDGE_TOL_M`` perpendicular of ONE rect's long (sloping) edge — it
    # hugs that edge and is pure residue.
    ALONG_EDGE_TOL_M = 5.0
    along_tol2 = ALONG_EDGE_TOL_M * ALONG_EDGE_TOL_M

    def _perp_d2_within(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            return None
        t = ((px - ax) * dx + (py - ay) * dy) / seg2
        if t < -0.05 or t > 1.05:
            return None              # foot of perpendicular outside the edge
        cx, cy = ax + t * dx, ay + t * dy
        return (px - cx) ** 2 + (py - cy) ** 2

    def _hugs_long_edge(jv, rv) -> bool:
        """True iff EVERY vertex of ``jv`` lies within ALONG_EDGE_TOL of one of
        the rect ``rv``'s two LONGEST (sloping) edges."""
        if len(rv) != 4 or len(jv) < 3:
            return False
        ring = [(rv[k], rv[(k + 1) % 4]) for k in range(4)]
        ring.sort(key=lambda e: -((e[1][0] - e[0][0]) ** 2
                                  + (e[1][1] - e[0][1]) ** 2))
        for (a, b) in ring[:2]:          # the 2 longest = sloping edges
            ok = True
            for vx, vy in jv:
                d2 = _perp_d2_within(vx, vy, a[0], a[1], b[0], b[1])
                if d2 is None or d2 > along_tol2:
                    ok = False
                    break
            if ok:
                return True
        return False

    to_drop: list[int] = []
    for i in junction_idxs:
        p = layout.shapes[i].polygon
        try:
            area = p.area
        except _GEOM_EXC:
            continue
        if area <= 0 or area >= max_area_m2:
            continue
        try:
            peri = p.length
        except _GEOM_EXC:
            continue
        aspect = peri / (2.0 * math.sqrt(math.pi * area))
        if aspect <= min_aspect:
            continue
        # Confirm 2+ shared vertices with a rect-like neighbour.
        share_with_rect = False
        for j in rect_idxs:
            shared = 0
            for vx, vy in verts[i]:
                for ux, uy in verts[j]:
                    if (vx - ux) ** 2 + (vy - uy) ** 2 <= tol2:
                        shared += 1
                        break
                if shared >= 2:
                    break
            if shared >= 2:
                share_with_rect = True
                break
        if not share_with_rect:
            # Relaxed: a sliver hugging a single rect's long edge (chord vs
            # curved boundary — only 1 shared corner) is still pure residue.
            for j in rect_idxs:
                if _hugs_long_edge(verts[i], verts[j]):
                    share_with_rect = True
                    break
        if share_with_rect:
            to_drop.append(i)

    if not to_drop:
        return 0
    drop_set = set(to_drop)
    layout.shapes = [
        s for k, s in enumerate(layout.shapes)
        if k not in drop_set]
    try:
        UI.vprint(1,
            f"  [pav-builder] {icao}: dropped "
            f"{len(to_drop)} thin orphan sliver junction(s) "
            f"(residue along stub/parallel long edges).")
    except _GEOM_EXC:
        pass
    return len(to_drop)


def _drop_floating_orphan_junctions(
        layout: "PavementLayout",
        icao: str = "",
        max_area_m2: float = 50.0,
        shared_vertex_tol_m: float = 0.5,
        ) -> int:
    """Drop small junction polygons that are FLOATING residue: they
    share NO vertex with any other shape (user 2026-05-20).

    ``pav_union.difference(rects)`` can leave a small wedge just past
    the end of a rect's edge, offset ~1 m by buffer/difference
    rounding.  Such a polygon shares no vertex with its near rect (too
    far) and no vertex with any junction, so neither
    ``_merge_sliver_junctions_into_neighbours`` (needs a shared
    JUNCTION edge) nor ``_drop_thin_orphan_slivers`` (needs a shared
    rect edge AND a thin >4 aspect) can absorb it — and its corners are
    all orphans (no source within tol), so it fails
    ``test_junction_vertices_have_source`` and (when it sits inside the
    pavement) ``test_junction_vertices_outside_pavement``.  SPLP #33 is
    the canonical case: a 19 m² triangle 1 m past taxiway B.

    Tight criterion so only genuine floating residue is dropped:
      * role == junction, 0 < area < ``max_area_m2`` (small);
      * shares 0 vertices (within ``shared_vertex_tol_m``) with ANY
        other shape — a legitimate junction always inherits boundary /
        rect-corner vertices from its neighbours.

    Returns count dropped.
    """
    tol2 = shared_vertex_tol_m * shared_vertex_tol_m
    rings: dict[int, list[tuple[float, float]]] = {}
    for k, s in enumerate(layout.shapes):
        if s.polygon is None or s.polygon.is_empty:
            rings[k] = []
            continue
        try:
            c = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            rings[k] = []
            continue
        if c and c[0] == c[-1]:
            c = c[:-1]
        rings[k] = c

    to_drop: list[int] = []
    for i, s in enumerate(layout.shapes):
        if s.role != ROLE_JUNCTION or s.polygon is None or s.polygon.is_empty:
            continue
        try:
            area = s.polygon.area
        except _GEOM_EXC:
            continue
        if area <= 0 or area >= max_area_m2:
            continue
        vi = rings[i]
        if not vi:
            continue
        shares = False
        for j, vj in rings.items():
            if j == i or not vj:
                continue
            for vx, vy in vi:
                for ux, uy in vj:
                    if (vx - ux) ** 2 + (vy - uy) ** 2 <= tol2:
                        shares = True
                        break
                if shares:
                    break
            if shares:
                break
        if not shares:
            to_drop.append(i)

    if not to_drop:
        return 0
    drop_set = set(to_drop)
    layout.shapes = [
        s for k, s in enumerate(layout.shapes) if k not in drop_set]
    try:
        UI.vprint(1,
            f"  [pav-builder] {icao}: dropped {len(to_drop)} floating "
            f"orphan junction(s) (no shared vertex, area < "
            f"{max_area_m2:.0f} m²).")
    except _GEOM_EXC:
        pass
    return len(to_drop)


def _drop_off_source_residue(
        layout: "PavementLayout",
        icao: str = "",
        max_area_m2: float = 2000.0,
        min_on_source_frac: float = 0.5,
        ) -> int:
    """Drop small apron / junction residue that rests almost entirely OFF
    the source pavement (apt.dat row-110 ∪ DSF ∪ runway).

    A thin strip wedged between a (shoulder-widened) runway edge and the
    real pavement — or residue left where a discovered runway-parallel
    centerline was dropped — gets emitted as an apron/junction even though
    there is no source pavement beneath it.  ``source_pavement_union`` is
    the authoritative footprint of real pavement, so an apron/junction
    sitting mostly off it is spurious (HECA #258 8 m × 133 m along 05R/23L,
    #228 11 m × 101 m along 05C/23C — both 8 % on source).

    Tight criterion so only genuine residue is dropped (a real apron is
    large and well on-source):
      * role ∈ {apron, junction}, 0 < area < ``max_area_m2`` (small);
      * on-source fraction < ``min_on_source_frac``.

    Returns count dropped.
    """
    src = getattr(layout, "source_pavement_union", None)
    if src is None or src.is_empty:
        return 0
    rwy = getattr(layout, "runway_union", None)
    if rwy is not None and not rwy.is_empty:
        try:
            src = src.union(rwy)
        except _GEOM_EXC:
            pass
    to_drop: list[int] = []
    for i, s in enumerate(layout.shapes):
        if s.role not in (ROLE_APRON, ROLE_JUNCTION):
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            area = s.polygon.area
        except _GEOM_EXC:
            continue
        if area <= 1.0:
            continue
        try:
            on = s.polygon.intersection(src).area
        except _GEOM_EXC:
            continue
        # Essentially-zero on-source coverage is spurious at ANY size:
        # aprons/junctions are cut FROM the source union, so a ~0%
        # piece can only be a synthesis artifact (e.g. a 1to1
        # straightening chord swallowing a boundary bay — SPJC's 5
        # pockets, 688-2447 m², exposed once the hole decompose split
        # them out of the big apron).  The size-capped branch keeps
        # its tight fraction for genuine-residue judgement calls.
        # ORDERING CONSTRAINT: this near-zero drop is judged BEFORE the
        # route-proximity-cut exemption below — a ~0%-on-source fragment
        # is phantom pavement whatever pass minted it (KCLT 18R-end
        # cluster: five 74-498 m² grass pieces, all flagged
        # ``from_route_proximity_cut`` and all 0 % on source, emitted as
        # apron/junction pavement over the RESA grass).
        if on / area <= 0.02:
            to_drop.append(i)
            continue
        # Route-proximity CUT pieces ABOVE the near-zero floor are
        # deliberate re-partitions of already-kept pavement: a near-band
        # fragment can individually sit mostly off-source even though its
        # PARENT passed this test (KCLT junction #255, 1.9 k m² dropped →
        # user-visible hole), so the size-capped fraction judgement below
        # must not apply to them.
        if getattr(s, "from_route_proximity_cut", False):
            continue
        if area < max_area_m2 and on / area < min_on_source_frac:
            to_drop.append(i)

    if not to_drop:
        return 0
    drop_set = set(to_drop)
    layout.shapes = [
        s for k, s in enumerate(layout.shapes) if k not in drop_set]
    try:
        UI.vprint(1,
            f"  [pav-builder] {icao}: dropped {len(to_drop)} off-source "
            f"residue apron/junction(s) (< {min_on_source_frac*100:.0f}% on "
            f"source pavement, area < {max_area_m2:.0f} m²).")
    except _GEOM_EXC:
        pass
    return len(to_drop)


# The junction sliver floor (MIN_JUNCTION_AREA, documented in junction_rules
# next to WIDEN_MAX_ABANDONED_PAVEMENT_M2): a clipped piece smaller than this
# has no mesh-scale presence and is dropped, exactly as the residue passes
# discard sub-floor apron / junction fragments.
SOURCE_CLIP_MIN_PIECE_AREA_M2 = 50.0


def source_clip_partial_coverage_shapes(
        layout: "PavementLayout",
        icao: str = "",
        min_on_source_frac: float = 0.5,
        ) -> int:
    """Formation-time SOURCE CLIP for partial-coverage apron / junction shapes.

    The global slice births every face 100 % on source
    (``pipeline._SLICE_SOURCE_CLIP``), but DOWNSTREAM recuts — the apron
    route-proximity cut, the ``_enforce_runway_1to1_sharing`` frontage
    straightening — can leave an apron / junction whose polygon is mostly OFF
    the real source pavement (apt.dat row-110 ∪ DSF ∪ runway).  KCLT junction
    #278 is 8.3 k m² at 35 % on source (the near-runway band carved off a real
    18R-end apron; the 65 % off-source remainder is RESA grass); #763 is a
    383 m² frontage split piece at 32 %.

    For each apron / junction shape whose on-source fraction <
    ``min_on_source_frac`` (judged by ``verification.check_source_adjacency`` —
    the SAME source union and on-source method the verify pass uses, so there
    is ONE definition of "on source"), clip the polygon to the source union
    (∪ runway) buffered by ``RUNWAY_REWRITE_CARVE_RUNWAY_HALO_M`` (the 1to1
    carve's runway-frontage halo — a small margin so the shape's near-runway
    contact strip survives).  The largest clipped piece replaces the shape's
    polygon; other pieces ≥ ``SOURCE_CLIP_MIN_PIECE_AREA_M2`` become their own
    shapes of the same role.

    Never touches runway / runway_crossing / groundside / boundary / clearance
    / service shapes (apron / junction only).  The clip only removes area from
    the ORIGINAL polygon, and aprons / junctions are already cut away from the
    runway upstream, so the runway-inclusive clip target can never introduce a
    runway overlap — it only preserves frontage CONTACT.

    ORDERING CONSTRAINT: this runs PRE-solve (before the per-surface elevation
    assignment), immediately before ``_unify_airside_geometry``, so the clipped
    edges are re-noded / welded / graded normally.  Apron / junction shapes
    carry no solved ``node_altitudes`` at this point; a clip changes the vertex
    count, so any (unexpected) pre-existing per-vertex list cannot be realigned
    and is cleared — the solver reassigns it.

    REMAINDER TRADEOFF: the clipped-away off-source remainder is off source BY
    CONSTRUCTION (it failed the source test), so it is DROPPED rather than
    handed to groundside DEM-follow — re-minting RESA grass as groundside
    pavement would merely relocate the phantom onto a DEM-following surface,
    and dropping it uncovers no real source (coverage-safe: the dual
    ``check_source_coverage`` invariant only guards INTERIOR source gaps).

    Gated by ``config.SOURCE_CLIP_PARTIAL_COVERAGE`` (O4_SOURCE_CLIP, default
    ON); OFF is byte-identical (the pass returns 0 without touching a shape).
    Returns the number of shapes clipped.
    """
    from .config import SOURCE_CLIP_PARTIAL_COVERAGE
    if not SOURCE_CLIP_PARTIAL_COVERAGE:
        return 0
    src = getattr(layout, "source_pavement_union", None)
    if src is None or src.is_empty:
        return 0
    rwy = getattr(layout, "runway_union", None)
    src_union = src
    if rwy is not None and not rwy.is_empty:
        try:
            src_union = src.union(rwy)
        except _GEOM_EXC:
            pass
    from .junction_rules import (
        RUNWAY_REWRITE_CARVE_RUNWAY_HALO_M, _polygonal_parts)
    try:
        clip_target = src_union.buffer(RUNWAY_REWRITE_CARVE_RUNWAY_HALO_M)
    except _GEOM_EXC:
        return 0
    if clip_target is None or clip_target.is_empty:
        return 0
    # Reuse the verifier's on-source method EXACTLY (one definition of
    # "on source"); filter its below-threshold list to apron / junction.
    from .verification import check_source_adjacency
    try:
        candidates = check_source_adjacency(layout, min_on_source_frac)
    except _GEOM_EXC:
        return 0
    idxs = [idx for (idx, _a, _f, _l) in candidates
            if 0 <= idx < len(layout.shapes)
            and layout.shapes[idx].role in (ROLE_APRON, ROLE_JUNCTION)]
    if not idxs:
        return 0
    new_shapes: list[BuiltShape] = []
    n_clipped = 0
    for i in idxs:
        s = layout.shapes[i]
        poly = s.polygon
        if poly is None or poly.is_empty:
            continue
        try:
            clipped = poly.intersection(clip_target)
        except _GEOM_EXC:
            continue
        clipped = _polygonal_parts(clipped)
        if clipped is None or clipped.is_empty:
            # No source under this shape at all — leave it to the near-zero
            # branch of _drop_off_source_residue; never null a shape here.
            continue
        if clipped.geom_type == "Polygon":
            raw_pieces = [clipped]
        elif clipped.geom_type == "MultiPolygon":
            raw_pieces = list(clipped.geoms)
        else:
            raw_pieces = []
        pieces = sorted(
            (p for p in raw_pieces
             if p.geom_type == "Polygon" and not p.is_empty and p.is_valid
             and p.area >= SOURCE_CLIP_MIN_PIECE_AREA_M2),
            key=lambda p: p.area, reverse=True)
        if not pieces:
            # The whole on-source portion is below the sliver floor.  Do NOT
            # drop the shape here — whole-shape phantom removal is
            # ``_drop_off_source_residue``'s job, which HONOURS the
            # route-proximity-cut exemption that protects a real-pavement
            # parent from the KCLT #255 rests-on-source hole.  This pass only
            # ever CLIPS a shape that has a genuine on-source piece to keep;
            # it never nulls a shape (so gate-off equivalence holds trivially
            # for every non-clipped shape).
            continue
        s.polygon = pieces[0]
        s.node_altitudes = None          # solver reassigns (geometry changed)
        for extra in pieces[1:]:
            new_shapes.append(BuiltShape(
                polygon=extra, role=s.role, ref=s.ref,
                source_axis=s.source_axis, is_bridge=s.is_bridge,
                from_route_proximity_cut=getattr(
                    s, "from_route_proximity_cut", False)))
        n_clipped += 1
    if new_shapes:
        layout.shapes.extend(new_shapes)
    if n_clipped:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: source-clipped {n_clipped} "
                f"partial-coverage apron/junction shape(s) to the source "
                f"pavement (< {min_on_source_frac*100:.0f}% on source; "
                f"off-source remainder dropped).")
        except _GEOM_EXC:
            pass
    return n_clipped


def _decompose_airside_holed_shapes(
        layout: "PavementLayout",
        icao: str = "",
        min_hole_area_m2: float = 100.0,
        ) -> int:
    """Hole-free normalization of airside residue, run just before the
    pre-solve node-unification.

    Interior-ring holes cannot survive to the OSM patch (``to_osm``
    writes exterior rings only), and ring-rebuilding passes silently
    FILL them — ``_enforce_runway_1to1_sharing`` and the
    ``_unify_airside_geometry`` weld both reconstruct
    ``Polygon(exterior_pts)``.  A terminal pad wholly inside an apron
    is carved out by the overlap-clip as an interior ring, so the
    carve came back as a double-cover the moment a later pass rebuilt
    the ring: KSDL terminal1 ∩ apron (1 030 m²), HECA ×3 — s70
    Phoenix triage item 6.  Decompose each holed apron/junction into
    hole-free pieces with conforming cuts
    (``_decompose_polygon_with_holes``, the junction-emit machinery)
    so there is no ring left to fill; cut endpoints land on canonical
    nodes shared with the adjacent shapes (node-shared seam).

    Returns the number of shapes decomposed.
    """
    holed: list[int] = []
    for i, s in enumerate(layout.shapes):
        if s.role not in (ROLE_APRON, ROLE_JUNCTION):
            continue
        p = s.polygon
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        try:
            if any(Polygon(h).area >= min_hole_area_m2
                   for h in p.interiors):
                holed.append(i)
        except _GEOM_EXC:
            continue
    if not holed:
        return 0
    from .pavement.junctions import _decompose_polygon_with_holes
    from .junction_rules import longest_runway_axis_deg
    # Conforming-cut node set: canonical registry + every fixed-shape
    # perimeter vertex (mirrors emit_junctions) so cut endpoints land
    # on nodes adjacent shapes already own.
    snap_pts: list[tuple[float, float]] = []
    reg = getattr(layout, "canonical_points", None)
    if reg is not None:
        try:
            snap_pts.extend(reg.points())
        except _GEOM_EXC:
            pass
    fixed_roles = (ROLE_RUNWAY, ROLE_BUILDING, ROLE_PRIMARY_PARALLEL,
                   ROLE_SECONDARY_PARALLEL, ROLE_STUB,
                   ROLE_CROSS_CONNECTOR)
    for s in layout.shapes:
        if s.role not in fixed_roles:
            continue
        if s.polygon is None or s.polygon.is_empty \
                or s.polygon.geom_type != "Polygon":
            continue
        try:
            c = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if c and c[0] == c[-1]:
            c = c[:-1]
        snap_pts.extend(c)
    axis_deg = longest_runway_axis_deg(layout)
    n_done = 0
    new_shapes: list[BuiltShape] = []
    for i in holed:
        s = layout.shapes[i]
        try:
            pieces = _decompose_polygon_with_holes(
                s.polygon, min_area_m2=50.0,
                runway_axis_deg=axis_deg,
                corner_snap_pts=snap_pts)
        except _GEOM_EXC:
            continue
        pieces = [p for p in pieces
                  if p is not None and p.geom_type == "Polygon"
                  and not p.is_empty and p.area >= 50.0]
        if not pieces:
            continue
        s.polygon = pieces[0]
        s.node_altitudes = None
        for p in pieces[1:]:
            new_shapes.append(BuiltShape(
                polygon=p, role=s.role, ref=s.ref,
                altitude=s.altitude))
        n_done += 1
    if new_shapes:
        layout.shapes.extend(new_shapes)
    if n_done:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: decomposed {n_done} holed "
                f"apron/junction(s) into hole-free pieces "
                f"(+{len(new_shapes)} shape(s)).")
        except _GEOM_EXC:
            pass
    return n_done


def _snap_near_corner_vertices_to_plane_corners(
        layout: "PavementLayout",
        icao: str = "",
        edge_prox_m: float = 0.5,
        corner_guard_m: float = 0.5,
        near_corner_snap_m: float = 1.5,
        ) -> int:
    """Snap a neighbouring (junction / apron / …) vertex that sits on a
    planar axial shape's edge INTERIOR near a corner onto that corner.

    A foreign vertex on a planar shape's edge interior breaks the shape's
    planar high→low slope (the per-vertex solver disagrees with the shape's
    interpolated altitude there → a step).  With the sloping-rect roles
    retired (owner 2026-07-29), the only axially-planar candidates are
    ``service_road`` shapes; the weld / conformance passes can leave such a
    vertex ~0.5 m off a corner sitting on the edge.

    This runs LAST (after conformance), on the emitted geometry, so it
    catches the final residual regardless of which pass produced it: for
    every such near-corner on-edge vertex, snap it onto the EXISTING
    corner (through the canonical registry) so the two SHARE the corner.
    Mid-edge vertices (farther than ``near_corner_snap_m`` from any
    corner) are left alone.  Returns the number of shapes modified.
    """
    from shapely.geometry import Polygon
    sloping_roles = {"service_road"}
    reg = getattr(layout, "canonical_points", None)
    # Sloped 4-corner rects — match the invariant test's "sloping" set:
    # a sloped rect (altitude_high/low or untagged), NOT a flat single-
    # altitude shape, NOT a per-vertex node_altitudes piece.
    rects: list[list[tuple[float, float]]] = []
    for s in layout.shapes:
        if s.role not in sloping_roles:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.node_altitudes is not None:
            continue
        if (s.altitude is not None
                and s.altitude_high is None
                and s.altitude_low is None):
            continue                       # flat single-altitude: exempt
        try:
            rc = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if rc and rc[0] == rc[-1]:
            rc = rc[:-1]
        if len(rc) != 4:
            continue
        rects.append([(float(x), float(y)) for x, y in rc])
    if not rects:
        return 0

    edge_prox2 = edge_prox_m * edge_prox_m
    snap2 = near_corner_snap_m * near_corner_snap_m
    guard2 = corner_guard_m * corner_guard_m
    n_changed = 0
    for s in layout.shapes:
        if s.role in sloping_roles:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        had_close = bool(coords) and coords[0] == coords[-1]
        if had_close:
            coords = coords[:-1]
        new_coords = list(coords)
        changed = False
        for vi, (px, py) in enumerate(coords):
            target = None
            for rc in rects:
                # Already at a corner of this rect → legitimate, skip it.
                if any((px - cx) ** 2 + (py - cy) ** 2 <= guard2
                       for cx, cy in rc):
                    continue
                for k in range(4):
                    ax, ay = rc[k]
                    bx, by = rc[(k + 1) % 4]
                    dx = bx - ax
                    dy = by - ay
                    L2 = dx * dx + dy * dy
                    if L2 <= 1e-9:
                        continue
                    t = ((px - ax) * dx + (py - ay) * dy) / L2
                    if t <= 0.001 or t >= 0.999:
                        continue
                    cxp = ax + t * dx
                    cyp = ay + t * dy
                    if (px - cxp) ** 2 + (py - cyp) ** 2 >= edge_prox2:
                        continue
                    near = (ax, ay) if t < 0.5 else (bx, by)
                    dnc2 = (px - near[0]) ** 2 + (py - near[1]) ** 2
                    if guard2 < dnc2 <= snap2:
                        target = near
                        break
                if target is not None:
                    break
            if target is not None:
                new_coords[vi] = (
                    reg.get_or_add(target[0], target[1])
                    if reg is not None else target)
                changed = True
        if not changed:
            continue
        ring = (new_coords + [new_coords[0]]) if had_close else new_coords
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            if poly.geom_type == "MultiPolygon":
                poly = max(poly.geoms, key=lambda g: g.area)
            if reg is not None:
                poly = snap_polygon_through_registry(poly, reg)
                if (poly is None or poly.is_empty
                        or poly.geom_type != "Polygon"):
                    continue
            if poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:
            continue
        s.polygon = poly
        n_changed += 1
    if n_changed:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: snapped near-corner vertex(es) "
                f"onto rect corners in {n_changed} shape(s).")
        except _GEOM_EXC:
            pass
    return n_changed


def _share_neighbour_corners_into_junctions(
        layout: "PavementLayout",
        icao: str = "",
        near_perimeter_m: float = 1.0,
        same_vertex_tol_m: float = 0.10,
        insert_perp_tol_m: float = 0.5,
        ) -> int:
    """Insert an unshared NEIGHBOUR corner that lies on a junction's edge
    into that junction's perimeter, so the junction SHARES it.

    ``test_junction_neighbour_corners_shared`` requires every neighbour
    vertex within ``near_perimeter_m`` of a junction's perimeter to
    coincide (within ``same_vertex_tol_m``) with a junction vertex.
    ``enforce_conformance`` inserts such T-junctions, but its endpoint
    guard skips any candidate within ``CONFORMANCE_TOL_M`` (0.5 m) ALONG an
    edge of a corner — even a genuinely distinct point 0.10-0.5 m from that
    corner (HECA: stub J3's corner is 0.52 m from junction #369's vertex
    v4, sitting on its edge → conformance treats it as "at v4" and skips,
    but it is 0.52 m > 0.10 m from v4, so the test still flags it).

    This pass closes that gap on the FINAL geometry, JUNCTION-scoped and
    using the test's own tolerances, so it acts only on the exact orphans
    the test flags — airports already passing have none, so it can't
    regress them.  Returns the number of junctions modified.
    """
    from shapely.geometry import Point, Polygon
    reg = getattr(layout, "canonical_points", None)
    junctions = [(i, s) for i, s in enumerate(layout.shapes)
                 if s.role == ROLE_JUNCTION
                 and s.polygon is not None and not s.polygon.is_empty]
    others = [s for s in layout.shapes
              if s.role != ROLE_JUNCTION
              and s.polygon is not None and not s.polygon.is_empty]
    if not junctions or not others:
        return 0
    nbr_pts: list[tuple[float, float]] = []
    for s in others:
        try:
            for ox, oy in list(s.polygon.exterior.coords)[:-1]:
                nbr_pts.append((float(ox), float(oy)))
        except _GEOM_EXC:
            continue

    same2 = same_vertex_tol_m * same_vertex_tol_m
    perp2_tol = insert_perp_tol_m * insert_perp_tol_m
    n_changed = 0
    for j_idx, j_s in junctions:
        try:
            coords = list(j_s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        had_close = bool(coords) and coords[0] == coords[-1]
        if had_close:
            coords = coords[:-1]
        if len(coords) < 3:
            continue
        x_min, y_min, x_max, y_max = j_s.polygon.bounds
        pad = near_perimeter_m + 0.5
        bnd = j_s.polygon.boundary
        # edge_index -> [(t, (x, y)), ...] to insert after that vertex.
        inserts: dict[int, list[tuple[float, tuple[float, float]]]] = {}
        for ox, oy in nbr_pts:
            if (ox < x_min - pad or ox > x_max + pad
                    or oy < y_min - pad or oy > y_max + pad):
                continue
            # already a junction vertex → fine.
            if any((ox - cx) ** 2 + (oy - cy) ** 2 <= same2
                   for cx, cy in coords):
                continue
            if bnd.distance(Point(ox, oy)) > near_perimeter_m:
                continue
            # locate the junction edge it lies on (interior, within perp tol)
            best = None
            for k in range(len(coords)):
                ax, ay = coords[k]
                bx, by = coords[(k + 1) % len(coords)]
                dx = bx - ax
                dy = by - ay
                L2 = dx * dx + dy * dy
                if L2 <= 1e-9:
                    continue
                t = ((ox - ax) * dx + (oy - ay) * dy) / L2
                if t <= 0.001 or t >= 0.999:
                    continue
                cxp = ax + t * dx
                cyp = ay + t * dy
                perp2 = (ox - cxp) ** 2 + (oy - cyp) ** 2
                if perp2 > perp2_tol:
                    continue
                if best is None or perp2 < best[2]:
                    best = (k, t, perp2)
            if best is not None:
                inserts.setdefault(best[0], []).append((best[1], (ox, oy)))
        if not inserts:
            continue
        new_coords: list = []
        for k in range(len(coords)):
            new_coords.append(coords[k])
            if k in inserts:
                seen_t: set = set()
                for t, pt in sorted(inserts[k]):
                    key = round(t, 4)
                    if key in seen_t:
                        continue
                    seen_t.add(key)
                    new_coords.append(
                        reg.get_or_add(pt[0], pt[1])
                        if reg is not None else pt)
        ring = (new_coords + [new_coords[0]]) if had_close else new_coords
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            if poly.geom_type == "MultiPolygon":
                poly = max(poly.geoms, key=lambda g: g.area)
            if reg is not None:
                poly = snap_polygon_through_registry(poly, reg)
                if (poly is None or poly.is_empty
                        or poly.geom_type != "Polygon"):
                    continue
            if poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:
            continue
        j_s.polygon = poly
        n_changed += 1
    if n_changed:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: inserted unshared neighbour "
                f"corner(s) into {n_changed} junction(s).")
        except _GEOM_EXC:
            pass
    return n_changed


# ── Apron reclassification ────────────────────────────────────────

# Per user 2026-05-18: a junction whose boundary strays >
# ``_APRON_RECLASSIFY_MAX_DISTANCE_M`` from the nearest taxi /
# runway centerline contains apron-territory pavement and should
# be reclassified as ``role=apron``.
#
# Threshold = 55 m.  Taxiway half-width is ~11.5 m and a normal
# 90° fillet apex sits ~22 m from the centerline; large airport
# fillets (SPJC mega-junctions, runway-taxi turn-off filleted to
# match wide-body taxi paths) can extend up to ~50 m from the
# straight-line apt.dat centerline.  55 m gives a small margin
# above that while still clearly catching apron territory (which
# extends 100 m+ from any centerline).
_APRON_RECLASSIFY_MAX_DISTANCE_M = 55.0
_APRON_RECLASSIFY_SAMPLE_STEP_M = 5.0
# A junction smaller than this stays a junction even if its boundary strays
# beyond the distance cap: a real apron is a sizeable expanse, so a small
# centerline-free residue blob is a junction, not an apron (user 2026-06-30).
_APRON_RECLASSIFY_MIN_AREA_M2 = 2000.0


def _aeroway_centerlines_union(layout: "PavementLayout"):
    """Union of every taxi + runway centerline known to the layout.

    Sources, in priority order:

    * ``layout.apt_taxi_centerlines`` — the full apt.dat / OSM
      taxi network captured BEFORE rect-and-junction decomposition.
      Centerlines that got absorbed into junction polygons survive
      here even though they're no longer on any shape.  Without
      this, a legitimate junction sitting on top of an absorbed
      centerline would test as "no centerline within 20 m" and
      get misflagged as apron.
    * Surviving taxi rects' ``source_axis``.  Redundant with the
      apt.dat set for most cases but catches OSM-only-derived
      centerlines (custom packs without apt.dat row 1201/1202).
    * Runway long-axes derived from each runway segment's 4 corners.
    """
    lines = []
    apt_lines = getattr(layout, "apt_taxi_centerlines", None) or []
    for item in apt_lines:
        # apt.dat / OSM taxi extraction returns
        # ``(LineString, name)`` tuples.
        ln = item.line if hasattr(item, "line") else (item[0] if isinstance(item, tuple) else item)
        if ln is not None and not ln.is_empty:
            lines.append(ln)
    for s in layout.shapes:
        if s.source_axis is not None and not s.source_axis.is_empty:
            lines.append(s.source_axis)
            continue
        if (s.role == ROLE_RUNWAY
                and s.polygon is not None
                and not s.polygon.is_empty):
            try:
                coords = list(s.polygon.exterior.coords)
            except _GEOM_EXC:
                continue
            if coords and coords[0] == coords[-1]:
                coords = coords[:-1]
            if len(coords) == 4:
                a_mid = (0.5 * (coords[0][0] + coords[3][0]),
                         0.5 * (coords[0][1] + coords[3][1]))
                b_mid = (0.5 * (coords[1][0] + coords[2][0]),
                         0.5 * (coords[1][1] + coords[2][1]))
                lines.append(LineString([a_mid, b_mid]))
    if not lines:
        return None
    try:
        return unary_union(lines)
    except _GEOM_EXC:
        return None


def _reeval_apron_piece_role(poly, cen, cap_m, step_m=2.0):
    """Re-derive apron vs junction for a single spine PIECE carved from an
    APRON parent, using the SAME geometry rule + cap as
    ``_reclassify_apron_junctions``: a piece whose whole boundary stays
    within ``cap_m`` of a taxi/runway centerline is a corridor
    (→ ROLE_JUNCTION, taxi-rate grade); one that strays beyond is
    apron-territory (→ ROLE_APRON, 1 %).

    Applied per piece AFTER a neck-split, this promotes the narrow corridor
    pieces sliced out of a wide apron blob — where a taxiway runs through
    it (CYXY taxiway G) — back to junction so they can climb at taxi rate,
    while the wide flanks left when a taxiway crosses a real apron (taxiway
    E through the main apron) stay apron.  PROMOTION-ONLY: splitting only
    removes area, so a piece's max boundary-to-centerline distance is
    always <= its parent's; this is only ever called on apron parents.
    (Extracted from the retired junction_spine.py, owner ruling 2026-07-29.)
    """
    if cen is None or cen.is_empty:
        return ROLE_APRON
    try:
        bnd = poly.boundary
        L = bnd.length
    except _GEOM_EXC:
        return ROLE_APRON
    if L <= 0:
        return ROLE_APRON
    n_steps = max(2, int(L / step_m) + 1)
    for i in range(n_steps):
        u = min(L, i * step_m)
        try:
            if cen.distance(bnd.interpolate(u)) > cap_m:
                return ROLE_APRON
        except _GEOM_EXC:
            continue
    return ROLE_JUNCTION


def _reclassify_apron_junctions(
        layout: "PavementLayout",
        icao: str = "",
        cap_m: float = _APRON_RECLASSIFY_MAX_DISTANCE_M,
        sample_step_m: float = _APRON_RECLASSIFY_SAMPLE_STEP_M,
        ) -> int:
    """Reclassify any junction whose boundary strays > ``cap_m``
    from the nearest taxi/runway centerline as ``role=apron``.

    The reclassification is geometric, not area-based: a 6-way
    mega-intersection is a valid junction even when it's large,
    but a pavement region without a centerline running through it
    is apron territory regardless of size.

    Centerline source is ``_aeroway_centerlines_union(layout)``,
    which now includes the original apt.dat taxi-network lines
    preserved on ``layout.apt_taxi_centerlines`` — without those,
    centerlines absorbed into junction polygons during the rect /
    junction decomposition would be missing from the union and
    legitimate junctions would fail the boundary-distance test.

    Returns the count of reclassified shapes.
    """
    centers = _aeroway_centerlines_union(layout)
    if centers is None or centers.is_empty:
        return 0
    # (USER RULING 2026-07-06 "no apron within 50 m of a centerline or
    # runway" is enforced downstream by the apron route-proximity CUT in
    # pipeline.py — a shape flipped here may legitimately contain BOTH
    # apron territory and a near-route band; the cut splits it at the
    # exact contour.)
    n_reclassified = 0
    for s in layout.shapes:
        if s.role != ROLE_JUNCTION:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            bnd = s.polygon.boundary
            L = bnd.length
        except _GEOM_EXC:
            continue
        if L <= 0:
            continue
        n_steps = max(2, int(L / sample_step_m) + 1)
        max_d = 0.0
        for i in range(n_steps):
            u = min(L, i * sample_step_m)
            try:
                p = bnd.interpolate(u)
                d = centers.distance(p)
            except _GEOM_EXC:
                continue
            if d > max_d:
                max_d = d
                if max_d > cap_m:
                    break
        if max_d > cap_m:
            # CONCEPT NOTE: "junction" is the STRUCTURAL kind (a
            # residue-decomposition polygon); ``role`` is the FINAL
            # tag.  An apron is just a junction reclassified here
            # because its interior strays > _APRON_RECLASSIFY_MAX_
            # DISTANCE_M from any centerline.  So a shape is a
            # ROLE_JUNCTION through most of the pipeline and only
            # becomes ROLE_APRON at this late pass — code that filters
            # `role == ROLE_JUNCTION` earlier still sees these.
            # Role-only change.  Per user 2026-05-18: aprons keep
            # per-corner ``node_altitudes`` (NOT a flat single
            # altitude); the solver already constrained the field
            # to 1.5 %.  Earlier flatten-on-reclass version averaged
            # each apron independently — adjacent aprons sharing a
            # corner (same canonical solver node, identical
            # altitude) ended up at different averages (each
            # apron's own mean), creating 4-8 m cliffs at shared
            # corners.  Preserving the solver's per-corner output
            # keeps shared corners consistent.
            s.role = ROLE_APRON
            # Whole-shape flip: one far corner beyond the cap condemned
            # the entire polygon.  Flag it so the apron neck-split can
            # re-evaluate each piece — spine-hugging corridor pieces
            # return to ROLE_JUNCTION (user 2026-07-06: strings of
            # corridor cells along a spine were emitting as apron).
            s.reclassified_from_junction = True
            n_reclassified += 1
    if n_reclassified:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: reclassified "
                f"{n_reclassified} junction(s) as apron "
                f"(boundary > {cap_m:.0f} m from any centerline).")
        except _GEOM_EXC:
            pass
    return n_reclassified


def _reclassify_runway_disconnected_to_groundside(
        layout: "PavementLayout",
        icao: str = "",
        dem=None,
        tile_lat: int = 0,
        tile_lon: int = 0,
        touch_tol_m: float = 0.05,
        require_service_adjacency: bool = False,
        ) -> int:
    """Reclassify aprons / junctions with NO touch-chain to a runway as
    groundside pavement (DEM-following, like every groundside shape).

    Per user 2026-06-09: an APRON must have a direct connection chain
    (through touching airside shapes) back to a runway — pavement
    islands without one are landside (FBO ramps, curbside, parking)
    and belong to the 4 % ``ROLE_GROUNDSIDE_PAVEMENT`` regime, not the
    airside apron solver (CYXY: 9 west-side "aprons" 92-35,500 m²,
    6-153 m from the airside network).  Only aprons and junctions are
    reclassified; a disconnected RECT (taxiway) is left alone and
    reported — that's a connectivity bug to fix, not a landside area.

    Each reclassified shape is RE-ELEVATED via the groundside
    ``_dem_follow_polygon`` (keeping its solved airside-flat altitude
    left a 2.7 m cliff against the true DEM-following groundside at
    CYXY), and ``_separate_groundside_from_airside`` re-runs so the
    no-shared-boundary groundside invariant holds for the new members.

    Runs at geometry-final, after ``_reclassify_apron_junctions`` and
    after all conformance/weld passes (so every legitimate connection
    already shares geometry), and BEFORE tile_cut (the tile clip severs
    cross-tile chains).  Returns the count reclassified.

    Per user 2026-06-11: airports with NO terminal have no landside —
    every paved area is airside (small fields' pavement islands are
    aircraft parking, not curbside), so this pass is skipped entirely
    and nothing emits as groundside.

    ``require_service_adjacency`` (user 2026-06-28) scopes the demotion to
    unreachable apron/junction COMPONENTS that actually touch a service
    road — the orphan the late junction→``service_road`` re-role creates.
    A bridge junction that carries a 1206 truck route is re-roled to
    ``service_road`` AFTER this pass first runs (LPHR: 6 west-side aprons),
    severing the apron cluster from the runway chain; the cluster is then
    landside but stays ``apron`` because the connectivity classifier already
    ran.  Re-running it catches the orphan — but that re-run happens after
    ``tile_cut`` (10 m seam gaps), so a plain re-run could false-positive an
    apron whose real aircraft-pavement chain was merely severed by the seam.
    Requiring the component to touch a service road (the actual orphaning
    cause) keeps the seam-gapped case airside.
    """
    from shapely.strtree import STRtree
    if not any(s.role == ROLE_BUILDING
               and s.polygon is not None and not s.polygon.is_empty
               for s in layout.shapes):
        return 0
    # AIRCRAFT-PAVEMENT connectivity only (user 2026-06-25): buildings and
    # service roads do NOT count as a runway chain.  A building sitting on an
    # apron, or a service road, is landside ACCESS — an apron reachable from the
    # runway only THROUGH a building or a SVC shape is itself landside and belongs
    # to groundside (CYXY apron-139: its only airside touch is a building + a
    # service road).  So the chain graph excludes ROLE_BUILDING (service roads
    # were already excluded).
    idxs = [i for i, s in enumerate(layout.shapes)
            if s.role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
                          ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
                          ROLE_STUB, ROLE_CROSS_CONNECTOR,
                          ROLE_JUNCTION, ROLE_APRON)
            and s.polygon is not None and not s.polygon.is_empty]
    if not idxs:
        return 0
    polys = [layout.shapes[i].polygon for i in idxs]
    tree = STRtree(polys)
    adj: dict[int, set[int]] = {k: set() for k in range(len(idxs))}
    for k, p in enumerate(polys):
        try:
            for m in tree.query(p.buffer(touch_tol_m)):
                m = int(m)
                if m == k:
                    continue
                if p.distance(polys[m]) <= touch_tol_m:
                    # A chain link needs a TRAVERSABLE shared edge — a
                    # corner/point contact cannot carry taxiing aircraft
                    # (user 2026-07-04, CYXY: a carved service strip left
                    # a ~point contact between the severed apron and its
                    # neighbour, keeping the whole lot "connected").
                    try:
                        shared = p.buffer(touch_tol_m).intersection(
                            polys[m].boundary).length
                    except _GEOM_EXC:
                        shared = 0.0
                    if shared < 1.0:
                        continue
                    adj[k].add(m)
                    adj[m].add(k)
        except _GEOM_EXC:
            continue
    seeds = [k for k, i in enumerate(idxs)
             if layout.shapes[i].role in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)]
    seen = set(seeds)
    stack = list(seeds)
    while stack:
        x = stack.pop()
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                stack.append(y)
    from .groundside import (
        _dem_follow_polygon, _dem_sampler,
        _separate_groundside_from_airside)
    from .config import GROUNDSIDE_MAX_GRADE
    _dem_at = (_dem_sampler(layout, dem, tile_lat, tile_lon)
               if dem is not None else None)
    # A runway-disconnected apron/junction with a 1206 TRUCK ROUTE running through
    # it is a ground-vehicle ROAD, not a landside lot — keep its airside role here
    # (the truck-route pass re-roles it ``service_road`` so it follows DEM as a road
    # and is NEVER separated from the service network it belongs to).  User
    # 2026-06-27: groundside 188, a 186 m corridor with 186 m of 1206 through it, was
    # wrongly demoted to groundside and walled off from the road it continues.
    _svc_lines = [cl.line for cl
                  in (getattr(layout, "apt_service_centerlines", None) or [])
                  if cl.line is not None and not cl.line.is_empty]
    # Service-adjacency scoping (second pass, post truck-route re-role):
    # demote only an unreachable apron/junction COMPONENT that touches a
    # service road — the exact orphan the bridge junction→service_road re-role
    # creates.  Component-level (not per-shape): the cluster's interior aprons
    # touch only each other; only its rim aprons touch the road (LPHR cluster
    # of 6 — 3 rim aprons touch the road, all 6 are eligible together).  None →
    # every unreachable apron/junction is eligible (first pass, unchanged).
    svc_eligible_i: "set[int] | None" = None
    if require_service_adjacency:
        from .layout import ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION
        svc_polys = [s.polygon for s in layout.shapes
                     if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
                     and s.polygon is not None and not s.polygon.is_empty]
        unreach = [k for k, i in enumerate(idxs)
                   if k not in seen
                   and layout.shapes[i].role in (ROLE_APRON, ROLE_JUNCTION)]
        unreach_set = set(unreach)
        comp_of: dict[int, int] = {}
        cid = 0
        for k0 in unreach:
            if k0 in comp_of:
                continue
            stack = [k0]
            comp_of[k0] = cid
            while stack:
                x = stack.pop()
                for y in adj[x]:
                    if y in unreach_set and y not in comp_of:
                        comp_of[y] = cid
                        stack.append(y)
            cid += 1
        comp_touch_svc: dict[int, bool] = {}
        for k in unreach:
            if comp_touch_svc.get(comp_of[k]):
                continue
            try:
                if any(polys[k].distance(g) <= touch_tol_m for g in svc_polys):
                    comp_touch_svc[comp_of[k]] = True
            except _GEOM_EXC:
                continue
        svc_eligible_i = {idxs[k] for k in unreach
                          if comp_touch_svc.get(comp_of[k])}

    n_reclassified = 0
    n_rect_orphans = 0
    converted: list[int] = []         # layout indices, for the cluster limit
    rect_orphan_idxs: list[int] = []
    for k, i in enumerate(idxs):
        if k in seen:
            continue
        s = layout.shapes[i]
        # In service-adjacency mode only road-orphaned components convert; a
        # disconnected rect is never in the set, so rect-orphan demotion (the
        # second sub-pass below) is inert here — by design.
        if svc_eligible_i is not None and i not in svc_eligible_i:
            continue
        if s.role in (ROLE_APRON, ROLE_JUNCTION):
            if _svc_lines:
                try:
                    _truck = 0.0
                    _route_ends_inside = False
                    for ln in _svc_lines:
                        if not ln.intersects(s.polygon):
                            continue
                        _truck += ln.intersection(s.polygon).length
                        _c = list(ln.coords)
                        from shapely.geometry import Point as _EndPt
                        if (s.polygon.buffer(1.0).contains(_EndPt(*_c[0]))
                                or s.polygon.buffer(1.0).contains(
                                    _EndPt(*_c[-1]))):
                            _route_ends_inside = True
                except _GEOM_EXC:
                    _truck = 0.0
                    _route_ends_inside = False
                # A JUNCTION with a truck route running THROUGH it = road
                # carriage — keep airside; the junction→service_road
                # re-role owns it (that re-role never takes aprons, so
                # deferring an APRON here just leaves it stuck).  An
                # unreachable APRON on/at the road — route through it or
                # ending inside it — is a ground-vehicle LOT, groundside
                # (user 2026-07-04, CYXY: the crew-car pad is only
                # ACCESSED via its road).
                if (_truck >= 15.0 and not _route_ends_inside
                        and s.role == ROLE_JUNCTION):
                    continue
            if _dem_at is not None:
                # simplify_tol=0: these boundaries come out of the
                # airside conformance pipeline already clean; the
                # default 2 m simplify moves adjacent pieces'
                # boundaries independently → mutual overlap (CYXY
                # #102∩#103, 5.4 m²).
                built = _dem_follow_polygon(
                    s.polygon, _dem_at, simplify_tol=0.0)
                if built is None:
                    continue          # never half-convert real pavement
                s.polygon, s.node_altitudes = built
            s.role = ROLE_GROUNDSIDE_PAVEMENT
            s.ref = "groundside"
            converted.append(i)
            n_reclassified += 1
        elif s.role in (ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
                        ROLE_STUB, ROLE_CROSS_CONNECTOR):
            n_rect_orphans += 1
            rect_orphan_idxs.append(i)

    # Second pass — disconnected RECTS (user 2026-06-11 auto-correct):
    # a SYNTHESIZED rect (discovered strip ``TX#`` / painted line
    # ``P#``) on a groundside island rides the island into groundside
    # (leaving it airside keeps a dangling short-edge verify warning
    # and an airside-solved rect inside a DEM-following island — KOQN
    # TX10).  Rects from the apt.dat 1201/1202 NETWORK keep their
    # airside role no matter what: the network is the authoritative
    # taxi-route declaration, so their disconnection is a
    # connectivity bug to surface, not a landside area (SPLP's 2
    # secondary rects are airside taxiways — converting them
    # regressed the compare-target fixture).
    if rect_orphan_idxs:
        import re as _re
        gs_polys = [layout.shapes[j].polygon for j in converted]
        gs_polys += [s.polygon for s in layout.shapes
                     if s.role == ROLE_GROUNDSIDE_PAVEMENT
                     and s.polygon is not None and not s.polygon.is_empty]
        # Runway-CONNECTED airside footprint: a rect abutting it is a
        # boundary taxiway beside a landside strip (SPLP TX#: real
        # airside, fixture-confirmed) — only an ISOLATED rect whose
        # whole island went groundside converts (KOQN TX10).
        airside_polys = [polys[k] for k in seen]
        for i in rect_orphan_idxs:
            s = layout.shapes[i]
            if not gs_polys:
                break
            if not _re.fullmatch(r"(TX|P)\d+", (s.ref or "")):
                continue              # network rect — never landside
            try:
                if s.polygon.area > 3000.0:
                    # A kilometre-scale taxiway is real airside even
                    # when touch-chain-broken (SPLP TX53/54, 12-14 k m²,
                    # fixture-confirmed) — only a small island STRIP
                    # demotes with its island.
                    continue
                near_gs = any(s.polygon.distance(g) <= 2.0
                              for g in gs_polys)
                near_airside = any(s.polygon.distance(g) <= 2.5
                                   for g in airside_polys)
            except _GEOM_EXC:
                continue
            if not near_gs or near_airside:
                continue
            if _dem_at is not None:
                built = _dem_follow_polygon(
                    s.polygon, _dem_at, simplify_tol=0.0)
                if built is None:
                    continue          # never half-convert real pavement
                s.polygon, s.node_altitudes = built
            s.role = ROLE_GROUNDSIDE_PAVEMENT
            s.ref = "groundside"
            s.altitude = None
            s.altitude_high = None
            s.altitude_low = None
            converted.append(i)
            n_reclassified += 1
            n_rect_orphans -= 1

    # New groundside members must honour the no-shared-boundary
    # invariant vs terminals / airside (clearance clip).  MUST run
    # BEFORE the chord grade limit below — it re-derives DEM altitudes
    # for clipped results and would overwrite the limited field.
    if n_reclassified and dem is not None:
        try:
            _separate_groundside_from_airside(
                layout, dem, tile_lat, tile_lon)
        except _GEOM_EXC:
            pass

    if n_reclassified or n_rect_orphans:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: reclassified "
                f"{n_reclassified} runway-disconnected apron/junction(s) "
                f"as groundside pavement (DEM-follow)"
                + (f"; {n_rect_orphans} disconnected taxi rect(s) left "
                   f"as-is" if n_rect_orphans else "")
                + ".")
        except _GEOM_EXC:
            pass
    return n_reclassified


def _reclassify_road_only_lots_to_groundside(
        layout: "PavementLayout",
        icao: str = "",
        dem=None,
        tile_lat: int = 0,
        tile_lon: int = 0,
        open_radius_m: float | None = None,
        min_lot_area_m2: float | None = None,
        lot_area_ratio: float | None = None,
        member_inside_frac: float = 0.10,
        touch_tol_m: float = 0.05,
        ) -> int:
    """A wide paved LOT reachable only via a service road is landside —
    ONE groundside surface, not a road carved through it.

    The on-pavement apt.dat-1206 carve runs a truck-route centerline
    THROUGH such a lot (CYXY 'Crew cars' loops the lot's rim, qualified
    sample-by-sample by the edge-hugging mode), shredding it into an
    oversized ``service_road`` rect + narrow ``service_junction`` frames.
    Each fragment is individually narrow, so the per-piece wide-lot guard
    in the service-junction re-role never fires, and because the pieces
    carry service roles they are excluded from the runway-disconnected →
    groundside pass — the lot never becomes groundside (it stays a
    fragmented road blob, even leaving an uncovered hole at CYXY).

    A road hugging a lot's rim is LOCALLY identical to a road hugging the
    airfield rim; only connectivity distinguishes them.  So this works on
    the UNION of each connected ``service_road`` + ``service_junction``
    component: a morphological OPENING (erode by the road half-width,
    dilate back) keeps only the genuinely 2-D parts — the lot — and drops
    the 1-D road strips.  A component whose opened core is a large enough
    fraction of its area is a lot; its member shapes lying mostly inside
    the core are reclassified to ``ROLE_GROUNDSIDE_PAVEMENT`` (DEM-
    following) and later merged into one surface, while the narrow
    connector strips stay ``service_road`` and meet the lot at its edge
    (``GROUNDSIDE_SHARE_SVC``).

    Runs after the service-junction re-role and BEFORE the runway-
    disconnected → groundside pass.  Skipped for terminal-less airports
    (no landside, same guard as that pass).  Returns the count
    reclassified.
    """
    from .config import (
        ROAD_LOT_AREA_RATIO,
        ROAD_LOT_MIN_AREA_M2,
        ROAD_LOT_OPEN_RADIUS_M,
    )
    R = ROAD_LOT_OPEN_RADIUS_M if open_radius_m is None else open_radius_m
    min_a = ROAD_LOT_MIN_AREA_M2 if min_lot_area_m2 is None else min_lot_area_m2
    ratio_min = ROAD_LOT_AREA_RATIO if lot_area_ratio is None else lot_area_ratio
    # Terminal-less airports have no landside — every paved island is
    # aircraft parking (same guard as the runway-disconnected pass).
    if not any(s.role == ROLE_BUILDING
               and s.polygon is not None and not s.polygon.is_empty
               for s in layout.shapes):
        return 0
    svc_idxs = [i for i, s in enumerate(layout.shapes)
                if s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
                and s.polygon is not None and not s.polygon.is_empty]
    if not svc_idxs:
        return 0
    # THROUGH-ROAD guard (user 2026-06-27): a thin corridor whose 1206 truck route
    # runs straight THROUGH its whole length is a service ROAD, not lot interior —
    # keep it ``service_road`` even though it overlaps the lot core.  A lot FRAME is
    # distinguished by its rim-looping route being far longer than the frame's
    # straight extent.  ``apt_service_centerlines`` are the truck routes.
    _svc_lines = [cl.line for cl
                  in (getattr(layout, "apt_service_centerlines", None) or [])
                  if cl.line is not None and not cl.line.is_empty]

    def _is_through_road(s):
        try:
            if s.polygon.area <= 0.0:
                return False
            mc = list(min_rotated_rect(s.polygon).exterior.coords)
            sides = [math.hypot(mc[j][0] - mc[j + 1][0],
                                mc[j][1] - mc[j + 1][1]) for j in range(4)]
            longest, shortest = max(sides), min(sides)
            tlen = sum(ln.intersection(s.polygon).length
                       for ln in _svc_lines if ln.intersects(s.polygon))
        except _GEOM_EXC:
            return False
        if longest <= 0.0 or shortest <= 0.0:
            return False
        # A very ELONGATED corridor carrying a substantial truck route that does
        # NOT loop is a through-ROAD — not lot interior (chunky, route ≈ 0) and not
        # a lot rim FRAME (also elongated, but its route LOOPS the rim so the route
        # length far exceeds the frame's straight extent, route > 1.4·longest).
        # CYXY 188 strips: aspect 19-21, route 0.5·longest, non-looping → road.
        # CYXY 'Crew cars' frame: aspect 8.9 but route 1.66·longest (loops) → lot.
        return (longest / shortest >= 5.0
                and 0.4 * longest <= tlen <= 1.4 * longest)

    def _as_polys(geom):
        if geom is None or geom.is_empty:
            return []
        if geom.geom_type == "Polygon":
            return [geom]
        return [g for g in getattr(geom, "geoms", ())
                if g.geom_type == "Polygon" and not g.is_empty]

    # Connected components over touching service shapes.
    from shapely.strtree import STRtree
    polys = [layout.shapes[i].polygon for i in svc_idxs]
    tree = STRtree(polys)
    adj: dict[int, set[int]] = {k: set() for k in range(len(svc_idxs))}
    for k, p in enumerate(polys):
        try:
            for m in tree.query(p.buffer(touch_tol_m)):
                m = int(m)
                if m != k and p.distance(polys[m]) <= touch_tol_m:
                    adj[k].add(m)
                    adj[m].add(k)
        except _GEOM_EXC:
            continue
    seen: set[int] = set()
    comps: list[list[int]] = []
    for k in range(len(svc_idxs)):
        if k in seen:
            continue
        stack = [k]
        seen.add(k)
        comp = [k]
        while stack:
            x = stack.pop()
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
                    comp.append(y)
        comps.append(comp)

    from .groundside import _dem_follow_polygon, _dem_sampler
    _dem_at = (_dem_sampler(layout, dem, tile_lat, tile_lon)
               if dem is not None else None)
    n = 0
    remove_idxs: set[int] = set()
    new_shapes: list[BuiltShape] = []
    for comp in comps:
        comp_polys = [polys[k] for k in comp]
        try:
            comp_union = unary_union(comp_polys)
            opened = comp_union.buffer(-R).buffer(R)
        except _GEOM_EXC:
            continue
        lot_pieces = [g for g in _as_polys(opened) if g.area >= min_a]
        if not lot_pieces:
            continue
        try:
            lot = unary_union(lot_pieces)
            comp_area = comp_union.area
            if comp_area <= 0.0 or (lot.area / comp_area) < ratio_min:
                # Mostly 1-D strips (a road network, e.g. HECA) — not a lot.
                continue
        except _GEOM_EXC:
            continue
        members: list[int] = []
        for k in comp:
            i = svc_idxs[k]
            s = layout.shapes[i]
            try:
                # A piece is part of the lot if any meaningful share of it
                # lies inside the ERODED core.  The threshold is low on
                # purpose: a thin connector strip (the road leading away to
                # the apron) erodes away entirely, so it has ~0 overlap with
                # the core, while a carved lot frame wrapping the core
                # overlaps well above the floor — a wide, robust gap (CYXY:
                # connectors 0.00 vs the #156 frame 0.17).
                inside = s.polygon.intersection(lot).area
                if s.polygon.area > 0.0 \
                        and (inside / s.polygon.area) >= member_inside_frac:
                    if _svc_lines and _is_through_road(s):
                        continue       # a through-road corridor → stays road
                    members.append(i)
            except _GEOM_EXC:
                continue
        if not members:
            continue
        try:
            merged = unary_union(
                [layout.shapes[i].polygon for i in members])
        except _GEOM_EXC:
            continue
        # AIRSIDE-ADJACENCY VETO (owner report 2026-07-27, SPJC east
        # terminal / HECA airside breaks).  The charter is "a wide paved
        # lot reachable ONLY via a service road" — but this pass never
        # tested that.  The road-feed service carve shreds a TERMINAL
        # FRONTAGE apron into service_road corridors + service_junction
        # fragments too, and those pass the opening test exactly like a
        # landside lot (SPJC: two ~97 k m² frontage blobs beside
        # building81 demoted; HECA: the flagged 419 k m² region).  A
        # candidate lot sharing a TRAVERSABLE edge (≥ 1 m, the
        # runway-disconnected pass's rule) with live airside pavement is
        # the apron's own service carving, and owner ruling R1
        # (2026-07-26) is absolute there: "a road inside, or sharing an
        # edge with a real apron must follow the apron's grade".  A
        # genuine landside lot (CYXY crew cars, 6-153 m from the airside
        # network) touches airside only THROUGH its service-road
        # connectors — which stay ``service_road`` and are not members —
        # so it still demotes.
        _airside_touch = False
        for _s in layout.shapes:
            if (_s.role not in (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
                                ROLE_PRIMARY_PARALLEL,
                                ROLE_SECONDARY_PARALLEL, ROLE_STUB,
                                ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
                                ROLE_APRON)
                    or _s.polygon is None or _s.polygon.is_empty):
                continue
            try:
                if merged.distance(_s.polygon) > touch_tol_m:
                    continue
                shared = merged.buffer(touch_tol_m).intersection(
                    _s.polygon.boundary).length
            except _GEOM_EXC:
                continue
            if shared >= 1.0:
                _airside_touch = True
                break
        if _airside_touch:
            continue
        # Emit the lot as ONE surface: union the carved fragments (the
        # oversized road rect + its junction frames) into a single polygon
        # per contiguous blob and drop carve-gap interior holes, so the lot
        # is one clean ``groundside`` shape with the thin connector road
        # reaching its edge — instead of a fragmented road blob.
        emitted = False
        for blob in _as_polys(merged):
            if blob.interiors:
                kept = [r for r in blob.interiors
                        if Polygon(r).area >= min_a]
                blob = Polygon(blob.exterior, kept)
            built_poly, built_alts = blob, None
            if _dem_at is not None:
                built = _dem_follow_polygon(
                    blob, _dem_at, simplify_tol=0.0)
                if built is None:
                    continue          # never half-convert real pavement
                built_poly, built_alts = built
            new_shapes.append(BuiltShape(
                polygon=built_poly,
                role=ROLE_GROUNDSIDE_PAVEMENT,
                ref="groundside",
                node_altitudes=built_alts))
            n += 1
            emitted = True
        if emitted:
            remove_idxs.update(members)

    if remove_idxs:
        layout.shapes = [s for j, s in enumerate(layout.shapes)
                         if j not in remove_idxs]
        layout.shapes.extend(new_shapes)

    if n and dem is not None:
        from .groundside import _separate_groundside_from_airside
        try:
            _separate_groundside_from_airside(
                layout, dem, tile_lat, tile_lon)
        except _GEOM_EXC:
            pass
    if n:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: {n} road-only lot(s) "
                f"(service_road/junction fragments) merged → one groundside "
                f"surface each.")
        except _GEOM_EXC:
            pass
    return n


# (2026-07-31) ``_connect_discovered_lane_dead_ends_to_junctions`` lived
# here (user 2026-05-28, SPJC TX15: extend a residue junction onto a
# discovered lane's dangling end corners so the two share vertices).  It
# selected on a 4-corner rect SHAPE carrying a ``TX`` ref.  ``TX`` refs are
# minted only on medial-axis DISCOVERED centerlines, and the rect builder
# that turned those centerlines into shapes was retired by d4f61d6
# (2026-07-29) — the global slice emits every face with ``ref=""``.  Dead
# by data from that day; retired 2026-07-31 with the discovery branch
# itself (pipeline.py, config.py, pavement/discovered_taxiways.py).
