"""Boundary-conformance invariant for the emitted patch.

DESIGN REQUIREMENT (user, long-standing): the emitted pavement shapes must
form a CONFORMING planar partition — adjacent shapes share *identical*
vertices along common edges, and no two shapes' edges cross.  "No area
overlap" (``test_no_self_overlap``) is necessary but NOT sufficient: two
shapes can be area-disjoint yet share a boundary non-conformingly (a
T-junction — one shape has a vertex mid-edge that its neighbour lacks).

Why it matters: Ortho4XP feeds the patch to Triangle4XP as constraint
edges.  A T-junction or crossing forces the constrained triangulation to
node the arrangement, spraying near-degenerate sub-cm² sliver triangles
along the seam.  At HECA this turned ~119k healthy airport triangles into
~2.36M (94 % sub-1 m²) and a 9m40s X-Plane load.  Area-overlap checks are
blind to it because a T-junction's intersection is a zero-area line.

This module both DETECTS violations (the runtime invariant + test gate)
and ENFORCES conformance (insert each neighbour vertex that lies on a
shape's edge, so shared boundaries become vertex-identical).  Run at the
end of the pipeline for EVERY airport, not just baselines.
"""
from __future__ import annotations

import math
from collections import defaultdict, namedtuple

import O4_UI_Utils as UI
from shapely.strtree import STRtree

from . import grade_law as _GL

from .layout import (
    BuiltShape,
    PavementLayout,
    REF_RUNWAY_END_RESA,
    REF_RUNWAY_END_SKIRT,
    ROLE_BRIDGE_CAUSEWAY,
    ROLE_BRIDGE_TRENCH,
    ROLE_OLS_CUT,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CLEARANCE,
    ROLE_RUNWAY_CROSSING,
    ROLE_TUNNEL_RAMP,
    ROLE_TUNNEL_TRENCH,
    SHARED_VERTEX_TOL_M,
    VERTEX_ALT_MERGE_TOL_M,
    corner_alts_from_high_low,
)

__all__ = [
    "find_conformance_violations",
    "enforce_conformance",
    "repair_emit_quantized_rings",
    "planarize_airside",
    "reclip_emit_frame_overlaps",
    "weld_candidate_pairs",
    "FINAL_WELD_TOL_M",
    "weld_node_identity_tol",
    "WeldPair",
    "CONFORMANCE_TOL_M",
]

# Perpendicular distance under which a neighbour vertex is considered "on"
# a shape's edge (a T-junction to be inserted).  Matches the shared-vertex
# snap tolerance so a point already treated as a shared corner elsewhere is
# treated consistently here.
CONFORMANCE_TOL_M = SHARED_VERTEX_TOL_M

# THE FINAL WELD'S OWN TOLERANCE.  The post-solve T-vertex weld and the
# final epsilon-wedge weld (``pipeline.py`` parts 30h / 30j) both run
# TIGHT: only truly-ON-edge nodes (the wedge class sits at 0.000-0.003 m
# perpendicular); the full 0.5 m conformance tolerance would bow an edge
# outward by up to the tolerance and mint hairline overlaps
# (zero-tolerance ``test_no_self_overlap``).  Named here, once, because a
# CONSUMER now reads the weld's law as well as the weld: the pad-host
# level family's membership relation is "will weld together"
# (``anchors._pad_lip_index``, task #16), and a second spelling of this
# number in that consumer would be a second tolerance.
FINAL_WELD_TOL_M = 0.01

# Refs whose footprints intentionally OVERLAY other pavement rather than
# tiling with it, so they are exempt from the conformance partition.  The
# DEM bridge is a wide transition strip laid alongside/over the perimeter
# band; it is trimmed against pavement (no area overlap) but is not part
# of the airside constraint partition in the same way.
#
# NOTE (user 2026-05-22): the airport-boundary RIBBON (``ref ==
# "airport_boundary"``) is NO LONGER exempt.  It now lies entirely inside
# row-130 and pavement is clipped back to its inner edge
# (``_clip_pavement_to_boundary_interior``), so the ribbon and pavement
# must form a conforming partition — sharing seam nodes bidirectionally —
# or Triangle4XP nodes the seam into slivers.
# Wingtip / RESA clearance cuts (``ref == "surface_clearance"``) are
# terrain-grading overlays laid alongside pavement with a built-in gap
# (they share no edge with pavement), so — like the DEM bridge — they
# are not part of the airside conforming partition.
_OVERLAY_REFS = {"boundary_dem_bridge", "surface_clearance"}

# CUT-ONLY receivers: the shape families whose OWN law is "cut, never
# fill" (docs/STANDARDS.md "Lateral (wingtip) clearance"; the emitters'
# rule is ``clearance._resa_cut_alt`` = ``min(ceiling, DEM)`` and the OLS
# ceiling equivalent).  Role/ref sources: ``layout.ROLE_RUNWAY_CLEARANCE``
# (lateral wingtip cuts + the runway-END regime), ``layout.ROLE_OLS_CUT``,
# ``layout.REF_RUNWAY_END_RESA``.
#
# Why the weld needs them (SPJC 2026-07-25): the final epsilon-wedge weld
# values an inserted T-vertex by the host edge's plain lerp, and on a row
# where BOTH hosts are ceiling-limited that lerp IS the analytic ceiling
# ``ref + slope·d`` — which floats above a terrain depression BETWEEN the
# hosts (two inserted vertices measured +2.12 / +2.22 m over the DEM
# envelope on the ``runway_end_resa`` daylight row, from a lawful n = 24
# emit).  ``enforce_conformance(dem=…)`` re-applies the receiver's own cut
# law as a final bound on the inserted value.
_CUT_ONLY_REFS = frozenset((REF_RUNWAY_END_RESA,))
_CUT_ONLY_ROLES = frozenset((ROLE_RUNWAY_CLEARANCE, ROLE_OLS_CUT))
# ...and the FILL-only refs that OVERRIDE the role test: the runway-end
# SKIRT carries ROLE_RUNWAY_CLEARANCE but is fill-only by owner ruling
# (``clearance._skirt_lift_alt`` = ``max(floor, DEM)``), so an insert into
# it must never be pulled DOWN to the terrain.
_FILL_ONLY_REFS = frozenset((REF_RUNWAY_END_SKIRT,))


def _is_cut_only(shape) -> bool:
    """True when ``shape``'s own elevation law is CUT-ONLY, so none of its
    vertices may sit above the DEM it cuts (see ``_CUT_ONLY_ROLES``)."""
    ref = getattr(shape, "ref", None)
    if ref in _FILL_ONLY_REFS:
        return False
    return (ref in _CUT_ONLY_REFS
            or (getattr(shape, "role", None) or "") in _CUT_ONLY_ROLES)


def _make_cut_law_clamp(layout: "PavementLayout", dem,
                        tile_lat: int, tile_lon: int):
    """Build ``bound(shape, alt, px, py) -> alt`` — the final bound an
    inserted vertex's value passes through — or None when the clamp is
    inapplicable (gate off, no DEM, no anchor), in which case the caller
    leaves every inserted value exactly as computed today.

    Sampling is IDENTICAL to the clearance emitters' own ``sample_dem``
    closure (``elevation._sample_dem`` on the same DEM object and tile
    frame, local metres → lat/lon through the layout anchor), so the
    clamp reads the same surface the emitter tested its ceiling against.
    """
    from .config import CONFORMANCE_CUT_CLAMP_ENABLED
    if (dem is None or not CONFORMANCE_CUT_CLAMP_ENABLED
            or getattr(layout, "anchor", None) is None):
        return None
    from .elevation import _sample_dem

    def bound(shape, alt, px: float, py: float):
        if alt is None or not _is_cut_only(shape):
            return alt
        try:
            lat, lon = layout.m_to_ll(px, py)
            dem_alt = _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except Exception:
            return alt
        if dem_alt is None or not math.isfinite(dem_alt):
            return alt          # no reading ⇒ plain value, unchanged
        # The RECEIVER'S OWN cut law re-applied (``min(ceiling, DEM)``),
        # not a neighbour's claim — so this is not a value-authority
        # transfer and the coincident-adopt authority guard above stands.
        return min(float(alt), float(dem_alt))

    return bound


def _open_ring(poly):
    """Exterior ring coords without the closing duplicate, or None."""
    if poly is None or poly.is_empty or poly.geom_type != "Polygon":
        return None
    coords = list(poly.exterior.coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return coords if len(coords) >= 3 else None


def _vertex_alts(shape, n):
    """Per-(open-ring-)vertex altitudes for ``shape`` (length ``n``), or
    None if the shape carries no usable altitude model.

    Used so an inserted vertex can be given the linearly-interpolated
    altitude along its edge, and the shape re-emitted as ``node_altitudes``
    when it was a sloped quad (which only supports exactly 4 corners)."""
    na = shape.node_altitudes
    if na is not None:
        a = list(na)
        if len(a) == n + 1:      # includes closing repeat
            a = a[:-1]
        if len(a) == n:
            return a
        return None
    if (shape.altitude_high is not None
            and shape.altitude_low is not None and n == 4):
        return corner_alts_from_high_low(
            shape.altitude_high, shape.altitude_low)
    if shape.altitude is not None:
        return [shape.altitude] * n
    return None


def _make_insert_altitude(layout, elig):
    """Build THE altitude rule for a vertex INSERTED on a shape's edge —
    shared by all three insert passes (``enforce_conformance``,
    ``_resolve_edge_crossings``, ``_resolve_yielding_tjunctions``).

    The historical rule was a plain lerp of the host edge's emitted
    altitudes.  That lerp is CROWN-UNAWARE: the spine crown (part 30)
    emits ``z = z′ − c`` where ``c`` is a designed per-node drop, so a
    host edge whose endpoints carry DIFFERENT drops is not linear in
    emitted z — lerping across it re-derives a value the solver never
    produced.  Measured at HECA (de-seg residual A2): the final weld
    re-inserted a junction vertex the solver had placed at 136.298 into a
    neighbour's crown-discontinuous edge, lerped 136.415, and the emit
    consensus averaged the two claims to 136.36 — a 3.57 % within-shape
    pair against the crowned runway-edge vertex 2.52 m away.

    Resolution order:

    1. COINCIDENT-ADOPT — the receiver is a SOFT airside shape (the
       law's ``grade_graph.SOFT_VISIBILITY_ROLES`` family, the shapes the
       solver value-welds) and the insert point interns — through the
       canonical-point registry's own radius rule, the SAME rule
       ``layout.to_osm`` assigns OSM node identity by — to a canonical
       node carrying an already-emitted altitude on another eligible
       ring: adopt that altitude, so the welded node keeps ONE value
       (generalizes the overlay ``donor_alt`` path — a T-junction insert
       IS another shape's vertex by construction).  Guards, measured at
       KCLT (within 9 → 25 + runway_grade 0 → 5 without them):
         * soft receivers only — a runway / rect / skirt ring is a value
           AUTHORITY (profile plane / band law); it must keep its own
           edge interpolation, never a neighbour's claim;
         * a donor farther in VALUE than ``VERTEX_ALT_MERGE_TOL_M`` from
           the edge's own interpolation is a deliberate wall/cliff (the
           emitter's node-split rule) and is never adopted.
    2. CROWN-AWARE INTERPOLATION — the host edge's endpoints carry
       different crown drops: interpolate in uncrowned space
       ``z′ = z + c`` and subtract the insert point's own drop (the same
       transform ``crown.extend_field_to_new_ring_nodes`` applies to
       post-solve ring inserts).  ALL drop lookups are EXACT-canonical
       (a point that isn't a registered canonical node reads 0):
         * ``z′`` lerp minus a linearly-INTERPOLATED drop is
           algebraically the plain z lerp, so the transform only means
           something when the insert IS a node with its OWN field entry;
         * the validator assigns the emitted nid that same field value
           (``check_grade._crown_drops_by_nid``), so exact lookups keep
           the two readers consistent, while a radius lookup
           (``crown_drop_at``'s 0.5 m nearest) stamps a neighbouring
           node's FULL drop onto a mid-edge insert — measured at KCLT as
           0.1–0.2 m dips on the 18L/36R ring near the crown taper.
    3. Otherwise the plain lerp, expression-identical to the historical
       code path — when the adopt guards don't all hold and the endpoint
       drops are equal (``c`` cancels), the emit is byte-identical to the
       pre-fix behaviour by construction.
    """
    # No import cycle: grade_graph never imports conformance.
    from .grade_graph import SOFT_VISIBILITY_ROLES

    soft_roles = frozenset(SOFT_VISIBILITY_ROLES)
    registry = getattr(layout, "canonical_points", None)
    donor_memo: dict = {"map": None}

    def _donor_values():
        """Canonical point → list of already-emitted altitudes at ring
        vertices interning to it.  Built lazily (only when a pass
        actually inserts a vertex).  Keyed through the registry's OWN
        radius rule — the emit interns node identity the same way
        (``layout.to_osm`` → ``registry.get_or_add``), so vertices that
        will become ONE OSM node pool their claims here."""
        if donor_memo["map"] is None:
            by_cp: dict = {}
            if registry is not None:
                for s2 in elig:
                    ring2 = _open_ring(s2.polygon)
                    if ring2 is None:
                        continue
                    alts2 = _vertex_alts(s2, len(ring2))
                    if alts2 is None:
                        continue
                    for (dx, dy), da in zip(ring2, alts2):
                        if da is None:
                            continue
                        cp = registry.find_nearest(dx, dy, registry.tol_m)
                        if cp is not None:
                            by_cp.setdefault(cp, []).append(float(da))
            donor_memo["map"] = by_cp
        return donor_memo["map"]

    def _is_canonical(x, y):
        """True when (x, y) IS a registered canonical node (exact
        identity — no radius matching; see the aliasing note)."""
        return (registry is not None
                and registry.find_nearest(x, y, registry.tol_m) == (x, y))

    def insert_altitude(receiver_role, ax, ay, alt_a, bx, by, alt_b,
                        t, px, py):
        lerp = alt_a + t * (alt_b - alt_a)
        # 1. coincident-adopt (soft receiver; node identity through the
        # registry radius — the same rule the emit interns node ids by,
        # so the adopted claim and the insert become ONE emitted node).
        if receiver_role in soft_roles and registry is not None:
            cp = registry.find_nearest(px, py, registry.tol_m)
            if cp is not None:
                donors = _donor_values().get(cp)
                if donors:
                    adopted = min(donors, key=lambda v: abs(v - lerp))
                    if abs(adopted - lerp) <= VERTEX_ALT_MERGE_TOL_M:
                        return adopted
        # 2. crown-aware interpolation across a drop discontinuity — ONLY
        # when all three points are provably canonical nodes, the one
        # case where their field drops are exact for both readers.  Any
        # non-canonical point falls through to the plain lerp (a radius
        # drop lookup stamps a neighbouring node's FULL drop onto a
        # mid-edge insert — measured at KCLT as 0.1-0.2 m dips on the
        # 18L/36R ring near the crown taper; a false 0-drop reading
        # would flip the discontinuity test the other way).
        field = getattr(layout, "_crown_drop_key", None)
        if (field and _is_canonical(ax, ay) and _is_canonical(bx, by)
                and _is_canonical(px, py)):
            c_a = field.get((ax, ay), 0.0)
            c_b = field.get((bx, by), 0.0)
            if c_a != c_b:
                c_p = field.get((px, py), 0.0)
                return (alt_a + c_a) + t * ((alt_b + c_b)
                                            - (alt_a + c_a)) - c_p
        # 3. plain lerp — byte-identical to the historical behaviour.
        return lerp

    return insert_altitude


def _eligible(shape):
    p = getattr(shape, "polygon", None)
    if p is None or p.is_empty or p.geom_type != "Polygon":
        return False
    return getattr(shape, "ref", None) not in _OVERLAY_REFS


def _build_vertex_index(shapes):
    """Return (cell_size, grid) where grid maps a coarse cell to the list
    of (x, y) vertices in it, for fast 'points near an edge' queries."""
    cell = 5.0  # metres
    grid = defaultdict(list)
    for s in shapes:
        ring = _open_ring(s.polygon)
        if ring is None:
            continue
        for x, y in ring:
            grid[(int(x / cell), int(y / cell))].append((x, y))
    return cell, grid


def _radius_index(points, tol):
    """Membership-with-RADIUS over a growing point set: returns
    ``(near, add)`` where ``near(x, y)`` is True when a registered point
    lies within ``tol`` of (x, y), and ``add(x, y)`` registers one.

    Exact set membership is NOT point identity at weld scale: two donor
    rings can carry bitwise-distinct vertices at the same location
    (float noise apart — each ring re-derived the point through its own
    geometry ops), and each passes an exact-tuple test independently.
    """
    cell = max(float(tol), 1e-9)
    tol2 = float(tol) * float(tol)
    grid = defaultdict(list)

    def add(x, y):
        grid[(int(x // cell), int(y // cell))].append((x, y))

    def near(x, y):
        i0, j0 = int(x // cell), int(y // cell)
        for i in (i0 - 1, i0, i0 + 1):
            for j in (j0 - 1, j0, j0 + 1):
                for qx, qy in grid.get((i, j), ()):
                    dx, dy = qx - x, qy - y
                    if dx * dx + dy * dy < tol2:
                        return True
        return False

    for x, y in points:
        add(x, y)
    return near, add


def _points_near_edge(grid, cell, ax, ay, bx, by, tol):
    """Yield distinct (x, y) grid vertices within ``tol`` of segment a-b's
    bounding band (a cheap superset; precise test done by the caller).

    THE BAND, NOT THE BOX (perf P3 wave 2).  The scan used to visit every
    cell of the segment's bounding BOX, which is quadratic in the edge
    length for a diagonal edge while the segment itself is linear: a 60 m
    edge at 45° (the densifier's chord cap, so the common long edge here)
    covers 144 cells of which ~36 can hold a point within ``tol``.  The
    walk below visits, per column (or per row, whichever axis the segment
    runs along), only the rows the segment can reach there, padded by one
    cell so no index convention can clip it.  The yielded set stays a
    SUPERSET of every point within ``tol`` of the segment — which is the
    whole contract: all three callers filter exactly
    (``_tjunctions_on_edge``) and sort the survivors, so a narrower
    superset cannot change a single result.  Twin:
    ``tests/test_emit_finalize_prefilters.py``.
    """
    minx, maxx = (ax, bx) if ax <= bx else (bx, ax)
    miny, maxy = (ay, by) if ay <= by else (by, ay)
    i0 = int((minx - tol) / cell)
    i1 = int((maxx + tol) / cell)
    j0 = int((miny - tol) / cell)
    j1 = int((maxy + tol) / cell)
    seen = set()
    dx = bx - ax
    dy = by - ay
    # A box only a few cells across IS its own band — walking it costs
    # more than scanning it.
    if (i1 - i0) < 3 or (j1 - j0) < 3:
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                for pt in grid.get((i, j), ()):
                    if pt not in seen:
                        seen.add(pt)
                        yield pt
        return
    if abs(dx) >= abs(dy):
        for i in range(i0, i1 + 1):
            # A cell with index ``i`` holds only x in
            # [(i-1)*cell, (i+1)*cell] under either sign convention of
            # int()'s truncation — a superset, which is all that is
            # needed.  Clipped to the segment's own x-range.
            xlo = (i - 1) * cell
            xhi = (i + 1) * cell
            if xlo < minx - tol:
                xlo = minx - tol
            if xhi > maxx + tol:
                xhi = maxx + tol
            if xlo > xhi:
                continue
            ylo = ay + dy * (xlo - ax) / dx
            yhi = ay + dy * (xhi - ax) / dx
            if ylo > yhi:
                ylo, yhi = yhi, ylo
            jj0 = int((ylo - tol) / cell) - 1
            jj1 = int((yhi + tol) / cell) + 1
            if jj0 < j0:
                jj0 = j0
            if jj1 > j1:
                jj1 = j1
            for j in range(jj0, jj1 + 1):
                for pt in grid.get((i, j), ()):
                    if pt not in seen:
                        seen.add(pt)
                        yield pt
        return
    for j in range(j0, j1 + 1):
        ylo = (j - 1) * cell
        yhi = (j + 1) * cell
        if ylo < miny - tol:
            ylo = miny - tol
        if yhi > maxy + tol:
            yhi = maxy + tol
        if ylo > yhi:
            continue
        xlo = ax + dx * (ylo - ay) / dy
        xhi = ax + dx * (yhi - ay) / dy
        if xlo > xhi:
            xlo, xhi = xhi, xlo
        ii0 = int((xlo - tol) / cell) - 1
        ii1 = int((xhi + tol) / cell) + 1
        if ii0 < i0:
            ii0 = i0
        if ii1 > i1:
            ii1 = i1
        for i in range(ii0, ii1 + 1):
            for pt in grid.get((i, j), ()):
                if pt not in seen:
                    seen.add(pt)
                    yield pt


def _tjunctions_on_edge(ax, ay, bx, by, candidates, tol):
    """Return [(t, (px, py)), ...] for candidate points lying on the OPEN
    segment a-b (perpendicular dist < tol, projection strictly interior,
    not within tol of either endpoint)."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return []
    L = math.sqrt(L2)
    out = []
    for px, py in candidates:
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        if t <= 0.0 or t >= 1.0:
            continue
        # perpendicular distance
        perp = abs((px - ax) * dy - (py - ay) * dx) / L
        if perp >= tol:
            continue
        # not coincident with an endpoint
        if t * L < tol or (1.0 - t) * L < tol:
            continue
        out.append((t, (px, py)))
    out.sort()
    return out


def find_conformance_violations(shapes, tol=CONFORMANCE_TOL_M):
    """Detect conformance violations among emitted shapes.

    Returns ``(t_junctions, crossings)`` where each is a list of
    ``(x, y)`` locations: a T-junction is a vertex of one shape lying on
    the interior of another shape's edge; a crossing is two shapes' edges
    intersecting at an interior point of both.  An empty result means the
    patch is a conforming partition (the invariant holds).
    """
    elig = [s for s in shapes if _eligible(s)]
    cell, grid = _build_vertex_index(elig)
    own = []          # set of own-ring vertices per shape (to exclude)
    rings = []
    for s in elig:
        ring = _open_ring(s.polygon)
        rings.append(ring)
        own.append(set(ring) if ring else set())

    t_junctions = []
    for ring, ownset in zip(rings, own):
        if ring is None:
            continue
        n = len(ring)
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            cands = [pt for pt in _points_near_edge(
                        grid, cell, ax, ay, bx, by, tol)
                     if pt not in ownset]
            for _, pt in _tjunctions_on_edge(ax, ay, bx, by, cands, tol):
                t_junctions.append(pt)

    # Crossings via edge STRtree.
    edges = []
    for ring in rings:
        if ring is None:
            continue
        n = len(ring)
        for i in range(n):
            a = ring[i]
            b = ring[(i + 1) % n]
            if a != b:
                edges.append((a, b))
    crossings = []
    if edges:
        lines = _edge_linestrings(edges)
        tree = STRtree(lines)
        for i, ln in enumerate(lines):
            for j in tree.query(ln):
                if j <= i:
                    continue
                a0, a1 = edges[i]
                b0, b1 = edges[j]
                if {a0, a1} & {b0, b1}:
                    continue          # share an endpoint: not a crossing
                inter = ln.intersection(lines[j])
                if inter.geom_type == "Point":
                    px = (inter.x, inter.y)
                    if px not in (a0, a1, b0, b1):
                        crossings.append(px)
    return t_junctions, crossings


def snap_subcm_vertex_twins(layout: "PavementLayout",
                            tol: float = 0.005) -> tuple[int, int]:
    """Conform CROSS-SHAPE vertex twins closer than ``tol`` (5 mm) to one
    shared coordinate (2026-07-27).

    Ring vertices of abutting shapes can end up bitwise-distinct at the
    same physical corner — the spine-slice arrangement nodes on a 1 cm
    grid (``junction_spine``: ``grid_size=0.01``) while difference-built
    and repair-rebuilt rings keep full-precision source coords, so a
    shared corner carries mm-apart twins.  The canonical-point registry
    interns the pair as ONE solver node, but each emitted ring keeps its
    own variant: the solver measures the edge from the canonical
    position and the validator from the ring-local one, and the budget
    LOCKSTEP test catches the drift (CYXY: one shared edge, 7.7e-5 —
    two junction rings 2.5 mm apart at one corner).  The epsilon-wedge
    weld cannot help: it INSERTS T-vertices, propagating both twins
    into the neighbour instead of unifying them.

    Groups are formed by union-find over a ``tol``-cell grid across
    DIFFERENT shapes only (a shape's own near-duplicate vertices are its
    author's business); every member rewrites to the group's
    lexicographically smallest coordinate — deterministic, and a ≤5 mm
    lateral move with altitudes untouched is far below every grade /
    overlap tolerance in the pipeline.  Runs immediately BEFORE the
    final epsilon-wedge weld so the weld sees unified corners.

    Returns ``(n_shapes_touched, n_vertices_snapped)``.
    """
    cell = max(float(tol), 1e-9)
    tol2 = float(tol) * float(tol)
    grid: dict = defaultdict(list)   # cell -> [(x, y, shape_idx, ring_no, vtx_no)]
    entries: list = []
    for si, s in enumerate(layout.shapes):
        p = getattr(s, "polygon", None)
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        rings = [list(p.exterior.coords)]
        rings += [list(r.coords) for r in p.interiors]
        for ri, ring in enumerate(rings):
            closed = (len(ring) >= 2 and ring[0] == ring[-1])
            upto = len(ring) - 1 if closed else len(ring)
            for vi in range(upto):
                x, y = ring[vi]
                eid = len(entries)
                entries.append([x, y, si, ri, vi])
                grid[(int(x // cell), int(y // cell))].append(eid)
    if not entries:
        return (0, 0)

    parent = list(range(len(entries)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for eid, (x, y, si, _ri, _vi) in enumerate(entries):
        i0, j0 = int(x // cell), int(y // cell)
        for i in (i0 - 1, i0, i0 + 1):
            for j in (j0 - 1, j0, j0 + 1):
                for oid in grid.get((i, j), ()):
                    if oid <= eid:
                        continue
                    ox, oy, osi = entries[oid][0], entries[oid][1], \
                        entries[oid][2]
                    if osi == si:
                        continue
                    dx, dy = ox - x, oy - y
                    if dx * dx + dy * dy < tol2:
                        ra, rb = find(eid), find(oid)
                        if ra != rb:
                            parent[rb] = ra
    groups: dict = defaultdict(list)
    for eid in range(len(entries)):
        groups[find(eid)].append(eid)
    rewrites: dict = defaultdict(dict)   # shape_idx -> {(ring,vtx): (x,y)}
    n_vertices = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        coords = {(entries[m][0], entries[m][1]) for m in members}
        if len(coords) < 2:
            continue
        rep = min(coords)
        for m in members:
            x, y, si, ri, vi = entries[m]
            if (x, y) != rep:
                rewrites[si][(ri, vi)] = rep
                n_vertices += 1
    n_shapes = 0
    for si, moves in rewrites.items():
        s = layout.shapes[si]
        p = s.polygon
        rings = [list(p.exterior.coords)]
        rings += [list(r.coords) for r in p.interiors]
        for ri, ring in enumerate(rings):
            closed = (len(ring) >= 2 and ring[0] == ring[-1])
            for (rj, vi), rep in moves.items():
                if rj != ri:
                    continue
                ring[vi] = rep
                if closed and vi == 0:
                    ring[-1] = rep
        try:
            from shapely.geometry import Polygon as _Poly
            newp = _Poly(rings[0], rings[1:])
            if not newp.is_valid:
                newp = newp.buffer(0)
            if (newp.is_empty or newp.geom_type != "Polygon"
                    or abs(newp.area - p.area) > 1.0):
                continue          # never trade a twin for broken geometry
        except Exception:
            continue
        s.polygon = newp
        n_shapes += 1
    return (n_shapes, n_vertices)


#: ONE candidate pair of the weld: the neighbour vertex ``donor_point``
#: welds into ``receiver``'s ring edge ``edge_index → edge_index+1`` at
#: ``point`` (the donor's own coordinate, or the canonical point it
#: interns to — see the canonical-identity guard in
#: ``_plan_shape_inserts``).  After the weld the two shapes carry ``point``
#: as ONE node: that is the vertex-identity class this pair creates.
WeldPair = namedtuple("WeldPair",
                      "receiver edge_index t point donor_point")


def weld_node_identity_tol(tol=CONFORMANCE_TOL_M) -> float:
    """The radius at which the weld treats two vertices as ALREADY one
    node (``_radius_index`` over the receiver's own ring).  A consumer
    that needs the weld's node identity must ask for it here rather than
    invent a tolerance of its own — there is exactly one weld law."""
    return max(float(tol), _NODE_IDENTITY_TOL_M)


#: CREATION-ORDER SENIORITY (spec §2).  The pipeline's own part order IS
#: the rank: a shape minted by an earlier part is senior to one minted by a
#: later part.  ``pipeline`` stamps ``_mint_rank`` on the shapes it creates
#: through :func:`stamp_mint_rank`; anything unstamped predates the
#: registry and is SENIOR to everything stamped (rank -1), which is the
#: conservative reading — the solve/projection output is the most senior
#: surface there is.  No new constants: the ranks are ordinals of the parts
#: that already exist.
MINT_RANK_UNSTAMPED = -1


def stamp_mint_rank(shapes, rank: int) -> int:
    """Stamp a ring-minting pass's rank onto the shapes it just created.
    Returns how many were stamped.  Idempotent: a shape that already
    carries a rank keeps its FIRST one, because that is when it was made."""
    n = 0
    for sh in (shapes or ()):
        if getattr(sh, "_mint_rank", None) is None:
            try:
                setattr(sh, "_mint_rank", int(rank))
                n += 1
            except (AttributeError, TypeError):
                pass
    return n


def _mint_rank(shape) -> int:
    r = getattr(shape, "_mint_rank", None)
    return MINT_RANK_UNSTAMPED if r is None else int(r)


def _junior_cap(shape) -> float:
    """The junior ring's OWN cap — the role limit it is already graded at.
    Read from ``config.ROLE_GRADE_LIMITS``, never re-spelled."""
    from .config import ROLE_GRADE_LIMITS, APRON_MAX_GRADE
    return float(ROLE_GRADE_LIMITS.get((shape.role or ""), APRON_MAX_GRADE))


def apply_conforming_mints(layout, mints, tol) -> tuple:
    """Make every JUNIOR ring conform to the values the mints settled.

    For each minted position, the shapes that carry a vertex there and are
    JUNIOR to the minting receiver adopt the senior value at that vertex and
    walk their own neighbourhood outward under their own cap
    (``grade_law.conforming_mint``).  A SENIOR vertex is never written —
    the rank comparison is what guarantees it, and the caller asserts it.

    Returns ``(n_minted, n_walked, walks)`` where ``walks`` records
    ``(x, y, senior_rank, junior_ref, reach_m)`` per conformed ring, for the
    sidecar (spec §5) so a census row inside a walk region is attributable.
    """
    if not mints:
        return 0, 0, []
    n_walk = 0
    walks = []
    for sh in layout.shapes:
        poly = getattr(sh, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        ring = _open_ring(poly)
        if not ring:
            continue
        alts = _vertex_alts(sh, len(ring))
        if alts is None:
            continue
        cap = _junior_cap(sh)
        rank = (_mint_rank(sh), str(getattr(sh, "ref", "") or ""))
        n = len(ring)
        changed = False
        new = list(alts)
        for i, (x, y) in enumerate(ring):
            hit = mints.get((round(x, 6), round(y, 6)))
            if hit is None:
                continue
            senior_value, senior_rank = hit
            if rank <= senior_rank:
                continue          # this ring IS the senior one — never move
            if new[i] is not None and abs(float(new[i]) - senior_value) <= 1e-9:
                continue
            new[i] = senior_value
            changed = True
            reach = 0.0
            # walk BOTH ways out of the mint, each under the junior's cap
            for step in (1, -1):
                vals, dists, idxs = [], [], []
                px, py = x, y
                j = i
                for _ in range(n - 1):
                    j = (j + step) % n
                    qx, qy = ring[j]
                    dists.append(math.hypot(qx - px, qy - py))
                    vals.append(new[j])
                    idxs.append(j)
                    px, py = qx, qy
                for (k, v) in _GL.conforming_mint(senior_value, vals,
                                                  dists, cap):
                    new[idxs[k]] = v
                    n_walk += 1
                    reach = max(reach, sum(dists[:k + 1]))
            walks.append((float(x), float(y), int(senior_rank[0]),
                          str(getattr(sh, "ref", "") or ""), float(reach)))
        if changed:
            sh.node_altitudes = [float(v) if v is not None else None
                                 for v in new]
            sh.altitude_high = None
            sh.altitude_low = None
    return len(mints), n_walk, walks


def _weld_frame(layout: "PavementLayout", include_overlay_refs: bool):
    """The weld's own working set: ``(elig, cell, grid, registry)``.
    Shared by ``enforce_conformance`` and ``weld_candidate_pairs`` so both
    enumerate candidates against the SAME donor index."""
    elig = [s for s in layout.shapes
            if (_eligible(s) or (include_overlay_refs
                                 and getattr(s, "polygon", None) is not None
                                 and not s.polygon.is_empty
                                 and s.polygon.geom_type == "Polygon"))]
    cell, grid = _build_vertex_index(elig)
    return elig, cell, grid, getattr(layout, "canonical_points", None)


def _private_snap_hits(ax, ay, bx, by, candidates, tol, snap_tol,
                       registry, is_private):
    """PRIVATE ON-EDGE ADOPTION candidates for one edge (spec
    weld-before-projection-spec.md §1 closure, session 2026-08-29).

    The emit-time "private on-edge node move" takes a node owned by
    exactly ONE chain, lying within ``(_WELD_TOL_M, ONEDGE_SNAP_TOL_M)``
    of a foreign chain's edge interior, MOVES it onto that edge, and the
    nid-level weld then splices it into the chain — all AFTER
    ``final_grade_projection``, so the receiving (possibly airside) way
    gains a vertex NO law graph ever priced (measured CYXY: groundside
    ring vertices spliced into service_junction ways,
    ``test_solver_and_validator_same_nodes``).  This enumerates the SAME
    class in the layout frame so the pre-projection weld adopts the
    donor's CANONICAL point into the receiving ring — the ring then
    carries the vertex, ``_build_node_list`` prices it, and at emit both
    rings intern to ONE nid (owners == 2, so the emit move and splice
    both stand down by their own tests).

    Returns ``[(t, canonical_point, True)]`` — the trailing flag marks a
    snap hit for the caller (its insert point is deliberately OFF the
    edge by up to ``snap_tol``; the edge bends through it, the same
    magnitude the emit move imposes on the donor ring today)."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return []
    L = math.sqrt(L2)
    out = []
    for px, py in candidates:
        # THE EMITTED FRAME: the emit move tests the node at its
        # CANONICAL position (interning happens before the move), and a
        # ring vertex can sit up to the registry bucket away from its
        # canonical point — measuring the RING coordinate here missed
        # the measured CYXY case (ring vertex 0.44 m off the edge,
        # canonical point 0.02 m off).  Resolve first, then measure.
        cp = (px, py)
        if registry is not None:
            got = registry.find_nearest(px, py, registry.tol_m)
            if got is not None:
                cp = got
        t = ((cp[0] - ax) * dx + (cp[1] - ay) * dy) / L2
        if t <= 0.0 or t >= 1.0:
            continue
        perp = abs((cp[0] - ax) * dy - (cp[1] - ay) * dx) / L
        # The strict T-junction path owns perp < tol; the emit move's
        # frame is (weld tol, snap tol) with ENDPOINT clearance at the
        # snap radius (layout.py, the ratified private on-edge move).
        if perp < tol or perp >= snap_tol:
            continue
        if t * L <= snap_tol or (1.0 - t) * L <= snap_tol:
            continue
        if not is_private(cp):
            continue
        out.append((t, cp, True))
    return out


def _plan_shape_inserts(ring, grid, cell, tol, registry,
                        snap_tol=None, is_private=None):
    """PURE: the T-vertex inserts the weld would make into ONE open ring.

    Returns ``(inserts, new_ring)`` where ``inserts`` is
    ``[(edge_index, t, (px, py), (dx, dy)), ...]`` in ring order — the
    donor vertex ``(dx, dy)`` welding into edge ``edge_index`` at
    ``(px, py)`` — and ``new_ring`` is the open ring the weld would build.
    Nothing is mutated: the caller decides what to do with the plan
    (``enforce_conformance`` derives insert altitudes and rebuilds the
    polygon; ``weld_candidate_pairs`` just reports the pairs).

    THIS IS THE WELD'S CANDIDATE ENUMERATION — the only one.  A second
    implementation of "which vertices will weld together" is a defect
    (the census-wrapper precedent), which is why the accessor and the
    weld share this function rather than agreeing by inspection.

    ``snap_tol`` / ``is_private`` (both or neither): additionally adopt
    PRIVATE on-edge donors in the emit move's frame — see
    :func:`_private_snap_hits`.  Defaults keep every existing caller
    byte-identical."""
    n = len(ring)
    ownset = set(ring)
    # NODE IDENTITY, not the insert tolerance (see
    # ``_NODE_IDENTITY_TOL_M``): an insert within the canonical WELD
    # radius of a vertex this ring already carries is that vertex —
    # reuse it, never mint a twin.  With the full conformance
    # tolerance the two radii coincide, so only the TIGHT
    # (planarize) pass changes behaviour, which is where the
    # post-solve near-duplicates were minted.
    near_own, own_add = _radius_index(ring, weld_node_identity_tol(tol))
    inserts: list = []
    new_ring: list = []
    _snap_on = snap_tol is not None and is_private is not None
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        new_ring.append((ax, ay))
        # Snap mode widens the superset by the registry bucket: a donor
        # RING vertex can sit up to tol_m from the CANONICAL point the
        # snap test measures (see _private_snap_hits).
        _search = (snap_tol + (registry.tol_m if registry is not None
                               else 0.0)) if _snap_on else tol
        cands = [pt for pt in _points_near_edge(
                    grid, cell, ax, ay, bx, by, _search)
                 if pt not in ownset]
        hits = [(t, pt, False) for t, pt
                in _tjunctions_on_edge(ax, ay, bx, by, cands, tol)]
        if _snap_on:
            hits.extend(_private_snap_hits(ax, ay, bx, by, cands, tol,
                                           snap_tol, registry, is_private))
            hits.sort(key=lambda h: h[0])
        for t, (px, py), _is_snap in hits:
            donor = (px, py)
            # CANONICAL-IDENTITY GUARD (2026-07-29, CYXY service
            # sliver): the OSM emitter interns every vertex through
            # the canonical-point registry, so an inserted vertex
            # that resolves to a DIFFERENT canonical point is
            # dragged onto that point at emit.  When the canonical
            # point still lies on this edge, insert IT (the
            # position the node will actually emit at); when it
            # lies off the edge, skip the insert — the "weld"
            # would emit bent (a groundside vertex 0.40 m from its
            # canonical point bowtied a CYXY service sliver via the
            # emit ``buffer(0)`` repair, minting a vertex the final
            # grade projection never graded).
            if registry is not None and not _is_snap:
                _cp = registry.find_nearest(px, py, registry.tol_m)
                if _cp is not None and _cp != (px, py):
                    _tc = _param_on_edge(ax, ay, bx, by, _cp[0], _cp[1])
                    if not (0.0 < _tc < 1.0):
                        continue
                    _fx = ax + (bx - ax) * _tc
                    _fy = ay + (by - ay) * _tc
                    _off = math.hypot(_cp[0] - _fx, _cp[1] - _fy)
                    if _off > tol:
                        # Off-edge canonical point: the strict weld must
                        # skip (inserting the FOOT would emit dragged onto
                        # the canonical point — bent).  But when the donor
                        # is PRIVATE and inside the emit move's snap
                        # frame, this is the adoption class: insert the
                        # canonical point itself (see _private_snap_hits).
                        if not (_snap_on and _off < snap_tol
                                and is_private(_cp)):
                            continue
                    t, (px, py) = _tc, _cp
            # A candidate near a shallow corner can qualify on TWO
            # edges of this ring; inserting it twice self-touches
            # the ring, the rebuild goes invalid, and the bail
            # below used to discard EVERY insertion for the shape
            # (the immortal-T-vertex class: dense welded rings
            # never conformed).  First edge wins.
            if (px, py) in ownset:
                continue
            # ...and "twice" needs no exact tuple match: two DONOR
            # rings can each carry a vertex at the same location,
            # bitwise-distinct by float noise, and each passes the
            # tolerance checks independently — the second insert
            # minted a zero-length edge (SPJC ``runway_end_resa``
            # 2026-07-25: inserts #26/#27 both at (-824.764,
            # 1609.243), from two adjacent_ground donors).
            # Coordinate-identical within ``tol`` ⇒ ONE insert.
            if near_own(px, py):
                continue
            ownset.add((px, py))
            own_add(px, py)
            new_ring.append((px, py))
            inserts.append((i, t, (px, py), donor))
    return inserts, new_ring


def _rebuilt_ring_polygon(s, new_ring):
    """``(polygon, reason)`` for the ring the weld built — the SHARED
    rebuild test, so a shape the weld would leave UNWELDED (invalid
    rebuild) is dropped identically by the accessor and the weld.

    Interior rings MUST ride along: an exterior-only rebuild fills the
    shape's holes, silently covering whatever shape occupies them (SPJC:
    ``gap_pit_floor`` over an ``adjacent_ground`` strip inside its hole,
    31.86 m² — the zero-tolerance self-overlap invariant)."""
    from shapely.geometry import Polygon
    try:
        new_poly = Polygon(new_ring, [list(r.coords)
                                      for r in s.polygon.interiors])
        if not new_poly.is_valid or new_poly.is_empty:
            return None, "invalid"
        return new_poly, None
    except Exception:
        return None, "exception"


def weld_candidate_pairs(layout: "PavementLayout",
                         tol=CONFORMANCE_TOL_M,
                         owner_roles: "set[str] | None" = None,
                         include_overlay_refs: bool = False,
                         ) -> "list[WeldPair]":
    """PURE, SIDE-EFFECT-FREE: the candidate pairs ``enforce_conformance``
    would weld on ``layout`` AS IT STANDS, as ``WeldPair`` records.

    Same arguments, same enumeration, same rebuild bail as the weld
    itself — the DEM/cut-clamp arguments are omitted because they only
    value an inserted vertex, never decide whether it is inserted.

    Why it exists (task #16): the pad-host LEVEL FAMILY is an EMIT-TIME
    structure.  ``relevel_pads_to_host_pavement`` runs post-solve,
    pre-emit, but the shared ring vertices that chain a pad to its host
    are minted LATER, by the final epsilon-wedge weld.  The family's
    membership relation is therefore "will weld together", read from the
    weld's own law through this accessor — never a second proximity join.

    The layout is NOT modified; call it as often as you like."""
    elig, cell, grid, registry = _weld_frame(layout, include_overlay_refs)
    out: list = []
    for s in elig:
        if owner_roles is not None and (s.role or "") not in owner_roles:
            continue
        ring = _open_ring(s.polygon)
        if ring is None:
            continue
        inserts, new_ring = _plan_shape_inserts(ring, grid, cell, tol,
                                                registry)
        if not inserts:
            continue
        poly, _reason = _rebuilt_ring_polygon(s, new_ring)
        if poly is None:
            continue      # the weld bails and leaves the shape UNWELDED
        for (ei, t, pt, donor) in inserts:
            out.append(WeldPair(s, ei, t, pt, donor))
    return out


def enforce_conformance(layout: "PavementLayout",
                        tol=CONFORMANCE_TOL_M,
                        owner_roles: "set[str] | None" = None,
                        include_overlay_refs: bool = False,
                        dem=None,
                        tile_lat: int = 0,
                        tile_lon: int = 0,
                        private_snap_tol: "float | None" = None,
                        ) -> tuple[int, int]:
    """Make the emitted shapes a conforming partition by inserting, into
    each shape's edges, every NEIGHBOUR vertex that lies on that edge
    (a T-junction).  The inserted vertex takes the edge's linearly
    interpolated altitude; a sloped-quad shape that gains a vertex is
    converted to ``node_altitudes`` (it can no longer be a 4-corner quad).

    ``owner_roles``: when given, only shapes whose role is in this set may
    RECEIVE inserted vertices (every eligible shape still contributes its
    vertices as candidates).  Used for the PRE-SOLVE pass: conform only
    apron/junction edges so abutting aprons share a canonical node and the
    solver grades them to match — WITHOUT inserting vertices into taxi-rect
    sloping edges (which would break their 4-corner planar form before the
    solver assigns altitudes).

    ``dem`` / ``tile_lat`` / ``tile_lon``: when given (the same DEM object
    and tile frame the clearance emitters were driven with), an insert into
    a CUT-ONLY receiver (``_is_cut_only``) is additionally bounded by the
    DEM at the insert point — the receiver's own "cuts never fill" law,
    which the host-edge lerp is blind to.  Default None ⇒ today's values
    everywhere; the gate ``CONFORMANCE_CUT_CLAMP_ENABLED`` off likewise.

    Returns ``(shapes_modified, vertices_inserted)``.  Idempotent: a second
    call inserts nothing.  Overlay refs (DEM bridge / clearance) are skipped
    unless ``include_overlay_refs`` — their "built-in gap" premise does not
    always hold (a bridge vertex CAN land exactly on a pavement edge, and an
    unwelded on-edge node tears Triangle4XP's triangulation), so the FINAL
    post-solve weld pass includes them.

    ``private_snap_tol``: when set (the pre-projection pass, part 18b),
    additionally adopt PRIVATE on-edge donor vertices in the emit-time
    "private on-edge node move" frame — a vertex owned by exactly ONE
    shape, within ``(tol, private_snap_tol)`` of a foreign edge interior,
    is inserted at its CANONICAL point so the final law graph prices it
    and the emit move/splice both stand down (spec
    weld-before-projection-spec.md §1; ``_private_snap_hits``).
    """
    elig, cell, grid, registry = _weld_frame(layout, include_overlay_refs)
    # Canonical-key → owning shape indices, for the private-donor test.
    # Interior (hole) rings count as owners — a vertex shared with a hole
    # is not private — but only EXTERIOR vertices are donor candidates
    # (they are what ``_build_vertex_index`` indexes).
    _owners: "dict | None" = None
    if private_snap_tol is not None:
        _owners = {}
        for _oi, _s2 in enumerate(elig):
            _rr = _open_ring(_s2.polygon)
            _all_rings = [] if _rr is None else [_rr]
            try:
                for _hole in _s2.polygon.interiors:
                    _all_rings.append(list(_hole.coords)[:-1])
            except Exception:
                pass
            for _ring2 in _all_rings:
                for (_vx, _vy) in _ring2:
                    _k = None
                    if registry is not None:
                        _k = registry.get(float(_vx), float(_vy))
                    if _k is None:
                        _k = (_vx, _vy)
                    _owners.setdefault(_k, set()).add(_oi)
    # Donor altitudes, for OVERLAY receivers only: a vertex welded into a
    # DEM-bridge / clearance edge must ADOPT the donor's altitude (the two
    # coincident nodes would otherwise emit metres apart — the very tear the
    # weld exists to fix).  Airside receivers keep edge interpolation
    # (surface-neutral; the solver is authoritative there).
    donor_alt: dict = {}
    if include_overlay_refs:
        for s2 in elig:
            ring2 = _open_ring(s2.polygon)
            if ring2 is None:
                continue
            alts2 = _vertex_alts(s2, len(ring2))
            if alts2 is None:
                continue
            for (dx, dy), da in zip(ring2, alts2):
                if da is not None:
                    donor_alt[(dx, dy)] = float(da)
    shapes_modified = 0
    vertices_inserted = 0
    insert_altitude = _make_insert_altitude(layout, elig)
    # ── THE CONFORMING MINT'S WORK LIST (spec
    # ``creation-order-seniority-spec.md`` §1; owner RULINGS 2026-08-21e) ──
    # Every insert this pass makes is a MINT against an already-settled
    # surface: the receiving edge is SENIOR (it was there; the vertex is
    # landing on it), so the minted vertex takes the receiving ring's own
    # value at that position — which this pass already does, via
    # ``insert_altitude``.  What was missing is the other half: the DONOR
    # ring keeps its own value at the same coordinate, and the emit
    # consensus then unifies the two at a step NEITHER ring priced.
    # Collect (position -> senior value, senior rank) here and make the
    # junior rings conform after the insert loop.
    _mints: dict = {}
    # Final bound for CUT-ONLY receivers (None ⇒ no clamp at all).
    cut_bound = _make_cut_law_clamp(layout, dem, tile_lat, tile_lon)

    for _ri, s in enumerate(elig):
        if owner_roles is not None and (s.role or "") not in owner_roles:
            continue
        ring = _open_ring(s.polygon)
        if ring is None:
            continue
        n = len(ring)
        alts = _vertex_alts(s, n)
        # A shape emitted with a SINGLE ``altitude`` (no high/low, no
        # node_altitudes) is flat: every corner sits at that level, so a
        # vertex inserted on an edge between two equal-altitude corners is
        # also at that level — the shape stays flat.  Keep the single
        # ``altitude`` instead of converting to ``node_altitudes`` (which
        # for a TERMINAL would violate H26's flat-only rule — the HECA
        # terminal10 case — and is redundant for any other flat shape).
        flat_single_alt = (s.node_altitudes is None
                           and s.altitude_high is None
                           and s.altitude_low is None
                           and s.altitude is not None)
        # Private-donor predicate, bound to THIS receiver: single owner,
        # and that owner is not the receiver itself (its own hole vertex
        # is the hole↔exterior weld's business, not adoption's).
        _is_private = None
        if _owners is not None:
            def _is_private(_cp, _recv=_ri, _own_map=_owners):
                _o = _own_map.get(_cp)
                return (_o is not None and len(_o) == 1
                        and _recv not in _o)
        # THE CANDIDATE PAIRS — the weld's own enumeration, the same call
        # ``weld_candidate_pairs`` makes (one code path, task #16).
        inserts, new_ring = _plan_shape_inserts(ring, grid, cell, tol,
                                                registry,
                                                snap_tol=private_snap_tol,
                                                is_private=_is_private)
        inserted_here = len(inserts)
        if not inserted_here:
            continue
        # Value each inserted vertex on the edge it landed on.  The plan is
        # in ring order, so walking it edge by edge reproduces ``new_ring``
        # position for position.
        new_alts = None
        if alts is not None:
            _recv_overlay = getattr(s, "ref", None) in _OVERLAY_REFS
            by_edge: dict = {}
            for (_ei, _t, _pt, _dp) in inserts:
                by_edge.setdefault(_ei, []).append((_t, _pt))
            new_alts = []
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                new_alts.append(alts[i])
                for t, (px, py) in by_edge.get(i, ()):
                    _da = (donor_alt.get((px, py))
                           if _recv_overlay else None)
                    if _da is not None:
                        _ins_alt = _da
                    else:
                        _ins_alt = insert_altitude(
                            s.role, ax, ay, alts[i],
                            bx, by, alts[(i + 1) % n],
                            t, px, py)
                    # CUT-ONLY receivers: bound however the value was
                    # derived (lerp, adopt or donor) by the shape's own
                    # cut law — a no-op when no DEM/gate is in play.
                    if cut_bound is not None:
                        _ins_alt = cut_bound(s, _ins_alt, px, py)
                    new_alts.append(_ins_alt)
                    # THE MINT: this position now carries a SENIOR value.
                    # Ties break on (rank, shape id) so two receivers
                    # claiming one position resolve deterministically.
                    if _GL.CONFORMING_MINT and _ins_alt is not None:
                        _rk = (_mint_rank(s), str(getattr(s, "ref", "") or ""))
                        _pk = (round(px, 6), round(py, 6))
                        _cur = _mints.get(_pk)
                        if _cur is None or _rk < _cur[1]:
                            _mints[_pk] = (float(_ins_alt), _rk)
        # Rebuild the polygon; bail (leave shape untouched) if invalid —
        # LOUDLY: a bailed shape keeps every T-vertex it should have
        # welded, and the un-welded nodes Ruppert-explode the tile mesh.
        new_poly, _bail = _rebuilt_ring_polygon(s, new_ring)
        if new_poly is None:
            if _bail == "invalid":
                import O4_UI_Utils as UI
                UI.vprint(1,
                    f"  [conformance] WARN: {s.role}/"
                    f"{getattr(s, 'ref', None)}: rebuilt ring invalid "
                    f"after {inserted_here} T-vertex insert(s) — shape "
                    f"left UNWELDED (mesh-sliver risk).")
            continue
        s.polygon = new_poly
        if new_alts is not None and not flat_single_alt:
            # node_altitudes carries the closing repeat.
            s.node_altitudes = new_alts + [new_alts[0]]
            s.altitude_high = None
            s.altitude_low = None
        # flat_single_alt: leave s.altitude as-is (the new vertex inherits
        # it); the shape stays flat and keeps the single-altitude model.
        shapes_modified += 1
        vertices_inserted += inserted_here
    return shapes_modified, vertices_inserted


def _repair_keeps_the_no_overlap_invariant(layout, shape, repaired):
    """The buffer(0) repair, RE-CLIPPED against every strictly higher-
    priority shape it now covers.  Returns the polygon to keep, or
    ``None`` when nothing survives (caller then leaves the ring alone).

    WHY (CYXY service_junction #145 ∩ service_road #142, 0.1878 m²,
    attributed 2026-09-01 with ``who_wrote --footprint``).  A ring that
    self-intersects in the quantized frame is a BOWTIE: the twisted lobe
    is not covered by the ring-as-written (winding rule), so
    ``_drop_overlap_against_fixed_shapes`` — which ran earlier and DID
    remove this exact overlap — sees no overlap there.  ``buffer(0)``
    then untwists it, and the repaired ring covers ground the pre-repair
    ring did not: the overlap is minted by the repair, after the only
    pass that polices it.  This is not a tolerance — the repair simply
    finishes the job under the SAME priority tiers
    ``_drop_overlap_against_fixed_shapes`` uses (``_OVERLAP_TIER``, one
    table for both), so a repaired residue yields to fixed geometry
    exactly as an unrepaired one does.  On a shape that gained no
    overlap it is a no-op."""
    tb = _tier(getattr(shape, "role", None))
    if tb <= 0:
        return repaired
    minx, miny, maxx, maxy = repaired.bounds
    out = repaired
    for other in layout.shapes:
        if other is shape:
            continue
        op = getattr(other, "polygon", None)
        if op is None or op.is_empty:
            continue
        if _tier(getattr(other, "role", None)) >= tb:
            continue
        obounds = op.bounds
        if (obounds[0] > maxx or obounds[2] < minx
                or obounds[1] > maxy or obounds[3] < miny):
            continue
        try:
            if not out.intersects(op):
                continue
            if out.intersection(op).area <= 0.0:
                continue
            out = out.difference(op)
        except Exception:
            return None
        if out.is_empty:
            return None
        if out.geom_type == "MultiPolygon":
            out = max(out.geoms, key=lambda g: g.area)
        if out.geom_type != "Polygon" or not out.is_valid:
            return None
        minx, miny, maxx, maxy = out.bounds
    return out


def repair_emit_quantized_rings(layout: "PavementLayout") -> int:
    """Pre-projection twin of the emit-time quantized-validity repair
    (``layout.to_osm``: "repaired invalid polygon at emit (buffer(0) ...
    quantization self-intersection)").

    The OSM emitter interns every vertex through the canonical-point
    registry and writes lat/lon rounded to 11 dp, so a ring that is valid
    at full precision can self-intersect in the EMITTED frame; the emit
    repair then buffer(0)s it and interns any new self-touch vertex FRESH
    — after ``final_grade_projection``, so the emitted way carries a
    vertex no law graph priced (measured CYXY service_junction, 31→14
    verts, ``test_solver_and_validator_same_nodes``).  Running the SAME
    repair here, on the same canonical-quantized frame, makes the
    repaired ring the FINAL ring: the projection prices it and the emit
    check finds the quantized image already valid (idempotent — the emit
    block stays as the residual guard).

    Returns the number of shapes repaired."""
    from shapely.geometry import Polygon
    registry = getattr(layout, "canonical_points", None)
    repaired = 0
    for s in layout.shapes:
        p = getattr(s, "polygon", None)
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        if getattr(s, "ref", None) in _OVERLAY_REFS:
            continue
        try:
            ring = list(p.exterior.coords)[:-1]
        except Exception:
            continue
        if len(ring) < 3:
            continue
        # THE EMITTED FRAME: canonical coordinates, 11 dp lat/lon.
        q = []
        for (x, y) in ring:
            key = (registry.get(float(x), float(y))
                   if registry is not None else None)
            cx, cy = key if key is not None else (x, y)
            la, lo = layout.m_to_ll(cx, cy)
            q.append((round(la, 11), round(lo, 11)))
        try:
            qpoly = Polygon([(lo, la) for la, lo in q])
        except Exception:
            continue
        if qpoly.is_valid:
            continue
        try:
            rep = qpoly.buffer(0)
            if rep.geom_type == "MultiPolygon":
                rep = max(rep.geoms, key=lambda g: g.area)
            if (rep.geom_type != "Polygon" or rep.is_empty
                    or not rep.is_valid):
                continue
        except Exception:
            continue
        coord_to_idx = {q[k]: k for k in range(len(q))}
        new_ring_m: list = []
        kept_idx: list = []
        for lo, la in list(rep.exterior.coords)[:-1]:
            k = coord_to_idx.get((round(la, 11), round(lo, 11)))
            if k is not None:
                new_ring_m.append(ring[k])
                kept_idx.append(k)
            else:
                new_ring_m.append(tuple(layout.ll_to_m(la, lo)))
                kept_idx.append(None)
        if len(new_ring_m) < 3:
            continue
        try:
            new_poly = Polygon(new_ring_m,
                               [list(r.coords) for r in p.interiors])
            if not new_poly.is_valid or new_poly.is_empty:
                continue
        except Exception:
            continue
        # THE REPAIR MAY NOT MINT AN OVERLAP (see
        # ``_repair_keeps_the_no_overlap_invariant``).  Untwisting a
        # bowtie can put pavement over a higher-priority neighbour the
        # overlap pass already cleared; clip it back here, and if nothing
        # survives leave the ring alone for the emit-time guard.
        clipped = _repair_keeps_the_no_overlap_invariant(
            layout, s, new_poly)
        if clipped is None:
            continue
        if clipped is not new_poly:
            new_poly = clipped
            ring_at = {}
            for _k, (_rx, _ry) in enumerate(ring):
                ring_at.setdefault((round(_rx, 9), round(_ry, 9)), _k)
            new_ring_m = [(x, y)
                          for x, y in list(new_poly.exterior.coords)[:-1]]
            kept_idx = [ring_at.get((round(x, 9), round(y, 9)))
                        for x, y in new_ring_m]
            if len(new_ring_m) < 3:
                continue
        # Carry per-vertex altitudes the way the emit repair does:
        # surviving vertices keep theirs, new self-touch vertices take
        # the nearest pre-repair vertex's value.  The projection reprices
        # every pavement ring after this anyway.
        na = getattr(s, "node_altitudes", None)
        if na:
            old = list(na)
            if len(old) == len(ring) + 1:
                old = old[:-1]
            if len(old) == len(ring):
                new_alts = []
                for j, k in enumerate(kept_idx):
                    if k is not None:
                        new_alts.append(old[k])
                    else:
                        x, y = new_ring_m[j]
                        bi, bd = 0, None
                        for kk in range(len(ring)):
                            d = ((ring[kk][0] - x) ** 2
                                 + (ring[kk][1] - y) ** 2)
                            if bd is None or d < bd:
                                bd, bi = d, kk
                        new_alts.append(old[bi])
                s.node_altitudes = new_alts + [new_alts[0]]
            else:
                # Already misaligned — emit drops such lists; do the same
                # here so the projection reprices from scratch.
                s.node_altitudes = None
        s.polygon = new_poly
        repaired += 1
        import O4_UI_Utils as UI
        UI.vprint(1,
            f"  [conformance] {s.role}: repaired quantization "
            f"self-intersection BEFORE the projection (buffer(0), "
            f"{len(ring)}→{len(new_ring_m)} verts) — the law graph "
            f"prices the repaired ring (weld-before-projection §1).")
    return repaired


def _param_on_edge(ax, ay, bx, by, px, py) -> float:
    """Parameter t∈[0,1] of the foot of ``(px,py)`` on segment a→b."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return -1.0
    return ((px - ax) * dx + (py - ay) * dy) / L2


# Crossing inserts dedupe at MICROMETRE scale, NOT at ``CONFORMANCE_TOL_M``:
# unlike the T-junction rule, the crossing detector is EXACT (it wants the
# intersection point itself to be a vertex of both rings), so skipping a real
# second crossing centimetres away would leave it flagged forever.  This radius
# only has to be wide enough to catch a duplicate that degenerates the ring and
# narrow enough that no distinct crossing ever falls inside it.
_CROSSING_DEDUPE_TOL_M = 1e-6

# ── NODE IDENTITY (cycle-5, docs/specs/cycle5-node-identity-spec.md) ──
# A canonical solve node has exactly ONE plan coordinate.  The canonical
# registry interns every coordinate within ``SHARED_VERTEX_TOL_M`` onto a
# single node, so a point landing inside that radius of an EXISTING ring
# vertex already IS that node: inserting it mints a twin — one node with
# two ring coordinates — and the solver (which binds the strictest law at
# the shared node) and the coordinate-keyed validator (which reads the
# law at each ring coordinate) then disagree on the same pair.  Measured
# at CYXY: ``planarize_airside`` added +670 near-duplicate pairs at stage
# 09 and 94 of the 193 solver↔validator budget mismatches.
#
# This is the IDENTITY radius, deliberately separate from the INSERT
# tolerance (how far off an edge a vertex may sit and still count as
# lying on it, ``_PLANARIZE_INSERT_TOL_M`` = 5 cm): a T-junction may only
# be inserted when it is BOTH collinear enough to be shape-preserving AND
# not already a node.  ``pipeline._dedup_coincident_ring_vertices`` keeps
# its own, much tighter 5 cm — per this spec it deletes COINCIDENT
# vertices, and widening it to the weld radius would delete legitimate
# short edges instead.
_NODE_IDENTITY_TOL_M = SHARED_VERTEX_TOL_M


def _edge_linestrings(edges):
    """``[LineString(a, b), ...]`` for a list of ``(a, b)`` coordinate
    pairs, built in ONE vectorised call (perf P3 wave 2).

    ``shapely.linestrings`` on an ``(n, 2, 2)`` array constructs exactly
    the geometries ``LineString([a, b])`` does — same coordinates, same
    float64 — at a fraction of the per-object cost, and a big airport
    builds one of these per conformance pass over ~10^5 ring edges.
    """
    import numpy as np
    import shapely

    return list(shapely.linestrings(
        np.asarray(edges, dtype=float).reshape(len(edges), 2, 2)))


def _crossing_candidate_pairs(tree, lines, edges):
    """Yield ``(ei, ej)`` with ``ej > ei`` for every bbox-overlapping edge
    pair that does not SHARE AN ENDPOINT — the crossing scan's own
    prefilter, evaluated in bulk (perf P3 wave 2).

    Identical pair SET to the per-line ``tree.query`` loop it replaces
    (one bulk query over the same tree), with the endpoint-sharing test
    spelled as exact coordinate equality exactly as ``{a0, a1} & {b0, b1}``
    did.  The order within the set is the bulk query's; every consumer
    sorts what it collects per edge, so order cannot reach an output.
    """
    import numpy as np

    pairs = tree.query(lines)
    if pairs.size == 0:
        return
    left, right = pairs[0], pairs[1]
    keep = right > left
    left = left[keep]
    right = right[keep]
    if left.size == 0:
        return
    ends = np.asarray(edges, dtype=float)          # (n, 2, 2)
    a0 = ends[left, 0]
    a1 = ends[left, 1]
    b0 = ends[right, 0]
    b1 = ends[right, 1]
    shares = (
        (a0 == b0).all(axis=1) | (a0 == b1).all(axis=1)
        | (a1 == b0).all(axis=1) | (a1 == b1).all(axis=1))
    for ei, ej in zip(left[~shares].tolist(), right[~shares].tolist()):
        yield ei, ej


def _resolve_edge_crossings(layout: "PavementLayout") -> int:
    """Insert each edge–edge intersection point as a shared vertex in BOTH
    crossing shapes.

    A "crossing" is two shapes' edges meeting at an interior point of both.
    The intersection point lies EXACTLY on both edges, so inserting it splits
    each edge there without moving it (shape-preserving, no bend, no area
    change) — and because both shapes now have a vertex at that point, it is a
    shared endpoint, not an interior crossing, so the conformance invariant
    stops flagging it.  The ≤noise-area sliver of a near-tangent crossing stays
    below the overlap-clip's floor.  Returns the number of vertices inserted."""
    from shapely.geometry import Polygon

    elig = [s for s in layout.shapes if _eligible(s)]
    rings = [_open_ring(s.polygon) for s in elig]
    edges: list[tuple[tuple, tuple]] = []
    meta: list[tuple[int, int]] = []           # (shape_idx, edge_idx_in_ring)
    for si, ring in enumerate(rings):
        if ring is None:
            continue
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            if a != b:
                edges.append((a, b))
                meta.append((si, i))
    if not edges:
        return 0
    lines = _edge_linestrings(edges)
    tree = STRtree(lines)
    # inserts[shape_idx][edge_idx] -> [(t, point)]
    inserts: dict = defaultdict(lambda: defaultdict(list))
    for ei, ej in _crossing_candidate_pairs(tree, lines, edges):
        a0, a1 = edges[ei]
        b0, b1 = edges[ej]
        try:
            inter = lines[ei].intersection(lines[ej])
        except Exception:
            continue
        if inter.geom_type != "Point":
            continue
        X = (inter.x, inter.y)
        if X in (a0, a1, b0, b1):
            continue
        si, i = meta[ei]
        sj, j = meta[ej]
        ta = _param_on_edge(a0[0], a0[1], a1[0], a1[1], X[0], X[1])
        tb = _param_on_edge(b0[0], b0[1], b1[0], b1[1], X[0], X[1])
        if 0.0 < ta < 1.0:
            inserts[si][i].append((ta, X))
        if 0.0 < tb < 1.0:
            inserts[sj][j].append((tb, X))
    if not inserts:
        return 0

    n_inserted = 0
    insert_altitude = _make_insert_altitude(layout, elig)
    for si, by_edge in inserts.items():
        shape = elig[si]
        ring = rings[si]
        if ring is None:
            continue
        n = len(ring)
        alts = _vertex_alts(shape, n)
        flat_single_alt = (shape.node_altitudes is None
                           and shape.altitude_high is None
                           and shape.altitude_low is None
                           and shape.altitude is not None)
        new_ring: list = []
        new_alts: list | None = [] if alts is not None else None
        added_here = 0
        for i in range(n):
            new_ring.append(ring[i])
            if new_alts is not None:
                new_alts.append(alts[i])
            if i in by_edge:
                seen: set = set()
                a_i = alts[i] if alts is not None else None
                a_j = alts[(i + 1) % n] if alts is not None else None
                (ax, ay) = ring[i]
                (bx, by) = ring[(i + 1) % n]
                # Zero-length-edge guard, seeded with the edge's OWN
                # endpoints: ``0 < t < 1`` admits a crossing a nanometre
                # from a corner, and two partners crossing float-noise
                # apart take DIFFERENT rounded-t keys whenever the pair
                # straddles a rounding boundary — so neither existing
                # test stops a degenerate edge from reaching the rebuild.
                # Deliberately per-EDGE, not ring-wide: the two crossings
                # a partner makes entering and leaving a thin sliver sit
                # on OPPOSITE edges microns apart and are both real, and
                # a ring-wide radius would drop one and leave that
                # crossing unresolvable.
                # NODE IDENTITY DOES NOT REACH HERE, deliberately
                # (cycle-5, measured): a T-junction insert within the
                # weld radius of an existing vertex is a REDUNDANT node
                # and skipping it costs nothing, but a CROSSING is a
                # place where two shapes' edges genuinely cross — skip
                # it and the crossing stays unresolved, which is an
                # OVERLAP (``test_no_self_overlap``, zero tolerance),
                # not a duplicate node.  Widening this radius to 0.5 m
                # dropped exactly such a crossing 0.2 m from a receiver
                # corner (``test_conformance.py::
                # test_crossing_insert_skipped_on_top_of_its_own_corner``).
                # The radius therefore stays float-noise-sized.
                near_ins, ins_add = _radius_index(
                    [(ax, ay), (bx, by)], _CROSSING_DEDUPE_TOL_M)
                for t, X in sorted(by_edge[i]):
                    key = round(t, 4)
                    if key in seen:
                        continue
                    seen.add(key)
                    if near_ins(X[0], X[1]):
                        continue
                    ins_add(X[0], X[1])
                    new_ring.append(X)
                    if new_alts is not None:
                        new_alts.append(insert_altitude(
                            shape.role, ax, ay, a_i, bx, by, a_j,
                            t, X[0], X[1]))
                    added_here += 1
        if not added_here:
            continue
        try:
            # Interior rings ride along (exterior-only fills the holes).
            new_poly = Polygon(new_ring + [new_ring[0]],
                               [list(r.coords)
                                for r in shape.polygon.interiors])
            if not new_poly.is_valid or new_poly.is_empty:
                continue
        except Exception:
            continue
        shape.polygon = new_poly
        if new_alts is not None and not flat_single_alt:
            shape.node_altitudes = new_alts + [new_alts[0]]
            shape.altitude_high = None
            shape.altitude_low = None
        n_inserted += added_here
    return n_inserted


# A T-junction whose vertex sits within this perpendicular distance of the edge
# is COLLINEAR (a clip ``difference()`` plants vertices exactly on the edge):
# inserting it bends the edge by ≤ this, so it is effectively shape-preserving
# and cannot create a >noise overlap.  Vertices farther off the edge are real
# near-misses left alone (inserting them would bend an edge into a neighbour —
# the 13.5 m² overlap the 0.5 m insert produced).
_PLANARIZE_INSERT_TOL_M = float(__import__("os").environ.get(
    "O4_PLANARIZE_INSERT_TOL_M", "0.05"))


# Overlap-priority tiers (mirrors elevation._drop_overlap_against_fixed_shapes):
# a LOWER number yields to nothing; a shape may conform (bend) to a vertex of a
# STRICTLY-higher-priority shape with no overlap risk, because that vertex sits
# on the higher shape's fixed boundary.  Bending toward a SAME/lower-tier peer
# can push an edge into it (the 3 m² junction×junction overlap), so those are
# left to the collinear-only insert.
_OVERLAP_TIER = {
    "runway": 0, "runway_crossing": 0, "building": 1,
    "primary_parallel": 2, "secondary_parallel": 2, "stub": 2,
    "cross_connector": 2, "service_road": 2,
    "junction": 3, "apron": 3, "service_junction": 3, "boundary": 4,
}


def _tier(role) -> int:
    return _OVERLAP_TIER.get(role or "", 3)


def _resolve_yielding_tjunctions(layout: "PavementLayout", tol: float) -> int:
    """Insert, into each shape B's edge, every nearby vertex of a STRICTLY
    higher-priority shape A (``tier(A) < tier(B)``) within ``tol`` — B yields
    (conforms) to A's fixed boundary, so the bend cannot overlap A.  This clears
    runway/rect-vertex-on-junction near-misses that the collinear insert leaves.
    Returns the number of vertices inserted."""
    from shapely.geometry import Polygon
    elig = [s for s in layout.shapes if _eligible(s)]
    rings = [_open_ring(s.polygon) for s in elig]
    cell, grid = _build_vertex_index(elig)
    # coord -> highest priority (lowest tier) among shapes owning it
    vtx_tier: dict = {}
    for s, ring in zip(elig, rings):
        if not ring:
            continue
        t = _tier(s.role)
        for v in ring:
            if t < vtx_tier.get(v, 99):
                vtx_tier[v] = t
    n_inserted = 0
    insert_altitude = _make_insert_altitude(layout, elig)
    for si, (shape, ring) in enumerate(zip(elig, rings)):
        if ring is None:
            continue
        tb = _tier(shape.role)
        n = len(ring)
        ownset = set(ring)
        # NODE IDENTITY (``_NODE_IDENTITY_TOL_M``) — a no-op at the one
        # call site (planarize passes the full conformance tolerance,
        # which IS the weld radius), stated so the law is uniform across
        # all three insert paths.
        near_own, own_add = _radius_index(
            ring, max(float(tol), _NODE_IDENTITY_TOL_M))
        alts = _vertex_alts(shape, n)
        flat_single_alt = (shape.node_altitudes is None
                           and shape.altitude_high is None
                           and shape.altitude_low is None
                           and shape.altitude is not None)
        new_ring: list = []
        new_alts: list | None = [] if alts is not None else None
        added = 0
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            new_ring.append((ax, ay))
            if new_alts is not None:
                new_alts.append(alts[i])
            cands = [pt for pt in _points_near_edge(grid, cell, ax, ay, bx, by, tol)
                     if pt not in ownset and vtx_tier.get(pt, 99) < tb]
            for t, (px, py) in _tjunctions_on_edge(ax, ay, bx, by, cands, tol):
                # Same duplicate-insert guard as ``enforce_conformance``
                # (see that loop for the full story).  Twice over: a
                # candidate near a shallow corner qualifies on TWO edges
                # of this ring, and two donor rings can carry the same
                # location bitwise-distinct (float noise apart).  The
                # first self-touches the rebuilt ring, the second mints a
                # zero-length edge; either way the bail below discards
                # EVERY insert for the shape and its T-vertices are
                # immortal.  First edge wins; coordinate-identical within
                # ``tol`` ⇒ ONE insert.
                if (px, py) in ownset or near_own(px, py):
                    continue
                ownset.add((px, py))
                own_add(px, py)
                new_ring.append((px, py))
                if new_alts is not None:
                    new_alts.append(insert_altitude(
                        shape.role, ax, ay, alts[i],
                        bx, by, alts[(i + 1) % n],
                        t, px, py))
                added += 1
        if not added:
            continue
        try:
            # Interior rings ride along (exterior-only fills the holes).
            new_poly = Polygon(new_ring + [new_ring[0]],
                               [list(r.coords)
                                for r in shape.polygon.interiors])
            if not new_poly.is_valid or new_poly.is_empty:
                continue
        except Exception:
            continue
        shape.polygon = new_poly
        if new_alts is not None and not flat_single_alt:
            shape.node_altitudes = new_alts + [new_alts[0]]
            shape.altitude_high = None
            shape.altitude_low = None
        n_inserted += added
    return n_inserted


def planarize_airside(layout: "PavementLayout", icao: str = "",
                      max_iters: int = 6) -> tuple[int, int]:
    """Drive the conformance invariant toward ZERO, SHAPE-PRESERVINGLY, so it is
    safe as the FINAL (post-solve) geometry pass.

    Iterates two insert-only steps until stable:
      * ``enforce_conformance`` with a TIGHT tolerance — inserts only COLLINEAR
        T-junction vertices (≤ ``_PLANARIZE_INSERT_TOL_M`` off the edge), so no
        edge bends into a neighbour (no overlap), and
      * ``_resolve_edge_crossings`` — inserts each edge-intersection point on
        both edges (the point lies exactly on both, so zero bend).
    Both interpolate inserted-vertex altitudes from the edge, so running this
    AFTER the solve introduces no cliffs.  Returns the residual
    ``(t_junctions, crossings)`` at the CHECK tolerance.

    NODE IDENTITY (cycle-5, ``_NODE_IDENTITY_TOL_M``): an insert landing
    within the canonical weld radius of a vertex the receiving ring
    already carries REUSES that vertex — the point is already that solve
    node, and minting a twin is what made the solver and the
    coordinate-keyed validator read different laws on one pair.  Such a
    reuse therefore stays in the residual counts this returns: the
    residual is a REPORT at the check tolerance, and a T-junction /
    crossing that is already a node needs no vertex."""
    tj_total = cr_total = 0
    for _ in range(max_iters):
        _, nv = enforce_conformance(layout, tol=_PLANARIZE_INSERT_TOL_M)
        # A lower-tier shape may also conform to a strictly-higher-tier shape's
        # vertex at the full CHECK tolerance (it bends onto a fixed boundary, so
        # no overlap) — clears runway/rect-on-junction near-misses.
        nv += _resolve_yielding_tjunctions(layout, tol=CONFORMANCE_TOL_M)
        nc = _resolve_edge_crossings(layout)
        tj_total += nv
        cr_total += nc
        if nv == 0 and nc == 0:
            break
    tj, cr = find_conformance_violations(layout.shapes)
    if tj_total or cr_total:
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: planarized airside — inserted "
                f"{tj_total} T-junction + {cr_total} crossing vertex(es); "
                f"residual {len(tj)} T-junction(s), {len(cr)} crossing(s).")
        except Exception:
            pass
    return len(tj), len(cr)


def densify_long_edges(layout, roles, max_edge_m: float = 60.0) -> int:
    """Insert mid-edge vertices on over-long exterior-ring edges of the
    given roles BEFORE the solve (user in-sim finding 2026-07-09: a
    construction-born 1,279 m junction edge gave the solver nothing to
    hold the pavement edge with, and the mesh sagged between the distant
    nodes toward the neighbouring graded strips).  Pre-solve: inserted
    vertices become solver nodes, so the edge profile is LAW-solved, not
    interpolated.  ``node_altitudes``, when present, gain the linear
    interpolation to stay index-aligned.  Returns vertices inserted."""
    import math as _math
    from shapely.geometry import Polygon as _Polygon
    from .fabric_sparse import stationing_declined as _stationing_declined
    inserted = 0
    for s in layout.shapes:
        if (s.role not in roles or s.polygon is None
                or s.polygon.is_empty
                or s.polygon.geom_type != "Polygon"):
            continue
        # THE FABRIC MODEL (owner RULINGS 2026-08-08): on a sparse shape
        # there is NO generic stationing — a node exists only where the
        # law needs a vertex, plus adequate spine/curve nodes.  This 60 m
        # pass IS reg-set §5.1 T8 ("no standard specifies vertex
        # density"), retired under W2's ``O4_FABRIC_W2_RETIRE_STATIONING`` and
        # inside the cluster under the Phase-A gate.  Inert when neither
        # is armed (``stationing_declined`` short-circuits).
        if _stationing_declined(s):
            continue
        ring = list(s.polygon.exterior.coords)
        closed = bool(ring) and ring[0] == ring[-1]
        if closed:
            ring = ring[:-1]
        n = len(ring)
        if n < 3:
            continue
        alts = None
        if s.node_altitudes and len(s.node_altitudes) >= n:
            alts = list(s.node_altitudes[:n])
        new_ring = []
        new_alts = [] if alts is not None else None
        changed = False
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            new_ring.append((ax, ay))
            if new_alts is not None:
                new_alts.append(alts[i])
            L = _math.hypot(bx - ax, by - ay)
            if L <= max_edge_m:
                continue
            cuts = int(_math.ceil(L / max_edge_m))
            for k in range(1, cuts):
                t = k / cuts
                new_ring.append((ax + (bx - ax) * t,
                                 ay + (by - ay) * t))
                if new_alts is not None:
                    a0 = alts[i]
                    a1 = alts[(i + 1) % n]
                    new_alts.append(
                        a0 + (a1 - a0) * t
                        if a0 is not None and a1 is not None
                        else a0)
                inserted += 1
                changed = True
        if not changed:
            continue
        try:
            # Interior rings ride along (exterior-only fills the holes).
            poly = _Polygon(new_ring, [list(r.coords)
                                       for r in s.polygon.interiors])
            if not poly.is_valid or poly.is_empty:
                continue
        except Exception:
            continue
        s.polygon = poly
        if new_alts is not None:
            s.node_altitudes = new_alts + [new_alts[0]]
    return inserted


# ── EMIT-FRAME OVERLAP RE-CLIP (lane weldov, RULINGS 2026-09-01w) ────
#
# THE CLASS.  ``layout.to_osm`` interns every ring vertex through the
# shared ``CanonicalPointRegistry`` (``get_or_add`` @ 0.5 m), so a
# vertex whose bucket is already claimed EMITS AT THE CLAIMANT'S
# COORDINATE.  Conformance parks feature/strip vertices exactly ON a
# neighbour's edge; when such a vertex's bucket is claimed by a nearby
# canonical point OFF that edge, the emitted ring bows across the
# neighbour and mints a double-cover the pre-emit frame never had
# (invariant A1).  Measured 2026-09-02 (attribution round, RULINGS
# 2026-09-01w): SPJC 13 pairs / 5.13 m², CYXY 2 / 0.59 m², every pair
# raw-overlap 0.000000 m².  Winning-coordinate classes, by pair count:
#   1. adjacent-ground ZONE-NODE attractors — the solve's
#      ``_build_node_list`` interns band zone-row grid points into the
#      SHARED registry (solver_primitives.py ``get_or_add``), minting
#      canonical points that are no emitted ring's vertex (9/15 pairs,
#      all graded_strip ∩ graded_strip);
#   2. triangulation LOOKUP interning — ``_vertex_elev_anchored``
#      calls ``get_or_add`` as a QUERY, registering 2-dp quantized
#      triangulation vertices as attractors (probe-spec §1x violated
#      by a pipeline pass; 4/15, all junction ∩ junction);
#   3. genuine neighbour-corner donors — the known T-vertex
#      donor-coordinate bow ("wall weld" class; 2-3/15).
# Retiring channels 1-2 is a cross-cutting weld/solver change (the
# zone-node identity is load-bearing for the writeback); THIS pass is
# the recorded scoped remedy — the last-word re-clip precedent
# (building-pad re-clip, bridge re-clip §T5 lineage): the ring that
# gained area it did not have pre-weld is re-clipped against its
# neighbour, IN THE FRAME THE WELD PRODUCES.

#: Roles the re-clip must never mutate: the runway family and the
#: law-evidence corridor/deck surfaces (senior byte-identity).
_RECLIP_NEVER_YIELD = frozenset({
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_RUNWAY_CLEARANCE,
    ROLE_BRIDGE_TRENCH, ROLE_BRIDGE_CAUSEWAY, ROLE_TUNNEL_TRENCH,
    ROLE_TUNNEL_RAMP,
})

#: Geometry exceptions the re-clip treats as "skip and report" (the
#: same set ``canonical_points`` guards its snaps with).
from .canonical_points import _GEOM_EXC as _RECLIP_GEOM_EXC  # noqa: E402


def reclip_emit_frame_overlaps(layout: "PavementLayout", icao: str = "",
                               max_sweeps: int = 4) -> int:
    """Last-word EMIT-FRAME overlap re-clip.  Detection is
    ``verification.check_self_overlap`` itself (the shared emit-frame
    instrument — one detector, no census-wrapper fork); for each pair
    the YIELDER is the ring that GAINED area into its neighbour during
    the weld (largest gain; never a ``_RECLIP_NEVER_YIELD`` role; tie →
    the junior, higher-index shape per creation-order seniority).  The
    yielder's ring is first resolved to its emitted coordinates
    (read-only through the registry — identical to what ``to_osm``
    would emit for it), then clipped against the neighbour's resolved
    ring via ``groundside._clip_shape_yielding_to`` (``snap_tol=0`` —
    shrink-only, cannot sweep an edge across a third shape;
    ``keep_interiors=True`` — a donut strip keeps its hole), and every
    final ring vertex whose bucket would still move it is pinned with
    ``registry.add_exact`` so the emit interning keeps the clip
    verbatim.  A lawful shared edge (no emit-frame overlap) is never
    touched.  Iterates to a fixed point (≤ ``max_sweeps``); any
    residual pair is reported loudly, never hidden.  Returns the
    number of shapes clipped/dropped.
    """
    registry = getattr(layout, "canonical_points", None)
    if registry is None:
        return 0
    from .verification import check_self_overlap, emit_frame_polygon
    from .groundside import _clip_shape_yielding_to

    def _resolved(p):
        # THE instrument's own frame (one resolution, shared with
        # ``check_self_overlap`` — a private variant here would let
        # the pass repair a frame the instrument does not read).
        return emit_frame_polygon(p, registry)

    def _largest_polygon(g):
        if g is None or g.is_empty:
            return None
        if g.geom_type == "Polygon":
            return g
        return max((q for q in getattr(g, "geoms", ())
                    if q.geom_type == "Polygon" and not q.is_empty),
                   key=lambda q: q.area, default=None)

    def _pin_ring(poly):
        """Register every ring vertex whose bucket would move it, as
        its OWN canonical entry (distance 0 wins every later lookup),
        so ``to_osm`` emits the clipped ring verbatim."""
        try:
            rings = [poly.exterior] + list(poly.interiors)
        except _RECLIP_GEOM_EXC:
            return
        for r in rings:
            for x, y in list(r.coords)[:-1]:
                cp = registry.get(float(x), float(y))
                if cp is None or cp != (float(x), float(y)):
                    registry.add_exact(float(x), float(y))

    n_acted = 0
    for _sweep in range(max_sweeps):
        pairs = check_self_overlap(layout)
        if not pairs:
            break
        drop_ids: set = set()
        acted_this_sweep = 0
        for area, ia, ib, loc in pairs:
            sa, sb = layout.shapes[ia], layout.shapes[ib]
            if id(sa) in drop_ids or id(sb) in drop_ids:
                continue
            res_a, res_b = _resolved(sa.polygon), _resolved(sb.polygon)
            if (res_a is None or res_a.is_empty
                    or res_b is None or res_b.is_empty):
                UI.vprint(1, f"  [emit-reclip] {icao}: pair "
                             f"{sa.role}[#{ia}] ∩ {sb.role}[#{ib}] @ "
                             f"{loc} — degenerate emit-frame "
                             f"resolution, SKIPPED (reported, not "
                             f"hidden).")
                continue
            try:
                gain_a = (res_a.difference(sa.polygon)
                          .intersection(res_b).area)
                gain_b = (res_b.difference(sb.polygon)
                          .intersection(res_a).area)
            except _RECLIP_GEOM_EXC:
                gain_a = gain_b = 0.0
            elig = [t for t in ((gain_a, ia, sa, res_a, res_b),
                                (gain_b, ib, sb, res_b, res_a))
                    if t[2].role not in _RECLIP_NEVER_YIELD]
            if not elig:
                UI.vprint(1, f"  [emit-reclip] {icao}: pair "
                             f"{sa.role}[#{ia}] ∩ {sb.role}[#{ib}] @ "
                             f"{loc} ({area:.4f} m²) — both roles are "
                             f"never-yield, SKIPPED (reported, not "
                             f"hidden).")
                continue
            # largest gain yields; tie → junior (higher index) yields.
            elig.sort(key=lambda t: (t[0], t[1]))
            gain_y, iy, ys, res_y, res_kept = elig[-1]
            # Adopt the emitted coordinates for the yielder first: the
            # overlap only EXISTS in that frame, and the clip below
            # must cut the ring that actually ships.  1:1 vertex count
            # keeps ``node_altitudes`` aligned; the clip's own
            # nearest-vertex carry covers any renoding.  The frame's
            # raw-ring fallback / MultiPolygon union coerce to the
            # largest Polygon part — ``BuiltShape.polygon`` is a
            # Polygon and the clip needs one.
            res_y_poly = _largest_polygon(res_y)
            if res_y_poly is None:
                UI.vprint(1, f"  [emit-reclip] {icao}: yielder "
                             f"{ys.role}[#{iy}] @ {loc} resolves to no "
                             f"polygon — SKIPPED (reported, not "
                             f"hidden).")
                continue
            ys.polygon = res_y_poly
            new_poly = _clip_shape_yielding_to(
                ys, res_kept, snap_tol=0.0, keep_interiors=True)
            if new_poly is None:
                drop_ids.add(id(ys))
                UI.vprint(1, f"  [emit-reclip] {icao}: {ys.role}"
                             f"[#{iy}] lies wholly inside its welded "
                             f"neighbour @ {loc} — DROPPED "
                             f"({area:.4f} m² pair).")
            else:
                _pin_ring(new_poly)
                UI.vprint(1, f"  [emit-reclip] {icao}: re-clipped "
                             f"{ys.role}[#{iy}] against its welded "
                             f"neighbour @ {loc} (pair {area:.4f} m², "
                             f"yielder gained {gain_y:.4f} m²).")
            acted_this_sweep += 1
            n_acted += 1
        if drop_ids:
            layout.shapes = [s for s in layout.shapes
                             if id(s) not in drop_ids]
        if not acted_this_sweep:
            break
    if n_acted:
        residual = check_self_overlap(layout)
        if residual:
            worst = residual[0]
            UI.vprint(1, f"  [emit-reclip] {icao}: RESIDUAL — "
                         f"{len(residual)} emit-frame overlap pair(s) "
                         f"survive the re-clip (worst {worst[0]:.4f} m² "
                         f"@ {worst[3]}); reported, not hidden.")
    return n_acted
