"""Cut shapes along integer lat/lon tile boundaries.

X-Plane / Ortho4XP renders each 1° × 1° lat-lon tile as a separate
DSF file.  A single shape that spans two tiles is awkwardly bisected
at the seam, producing visual artifacts.  Per user 2026-05-10: for
each integer lat or lon line passing through the airport's pavement
footprint, build a buffered line (``half_width_m`` each side, so a
10 m strip by default) and subtract it from every shape.  Shapes
that split into multiple pieces are replaced with separate
``BuiltShape`` entries; sloped 4-corner rects convert to per-vertex
``node_altitudes`` (cut pieces are non-rectangular and the legacy
``[H, L, L, H]`` 4-corner convention no longer applies).

The mechanism mirrors how the pavement builder clips runway shapes
out of ``pav_union`` — just at a different geometric target.  Ortho4XP
and X-Plane stitch the resulting tile seams together at render time.

Public API:
    cut_layout_at_tile_boundaries
"""
from __future__ import annotations

import copy
import math
from collections.abc import Callable

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .layout import (
    BuiltShape, PavementLayout, R_EARTH,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_RUNWAY, ROLE_JUNCTION,
    ROLE_APRON, ROLE_BUILDING, ROLE_SERVICE_ROAD, ROLE_TUNNEL_RAMP,
    ROLE_RETAINING_WALL, ROLE_GRADED_STRIP, ROLE_RUNWAY_CROSSING,
    vertex_bucket,
)
from .config import (
    TUNNEL_RAMP_MAX_GRADE, RUNWAY_SEAM_DEM_PIN, TILE_CUT_HALF_WIDTH_M,
    TILE_SEAM_TERRAIN_DEM_PIN_ENABLED,
)


# Roles whose slice-edge vertices are DEM-pinned at the seam so adjacent
# tile builds agree there (corridor junctions + aprons + service roads —
# the rect-era taxi roles are retired, owner 2026-07-29).  Runways
# follow the FAA profile (not terrain) and terminals stay flat, so they
# are excluded.
_PIN_SLICE_ROLES = frozenset({
    ROLE_JUNCTION, ROLE_APRON, ROLE_SERVICE_ROAD,
})

# POST-solve feature roles carrying SYNTHETIC (non-DEM) elevations —
# tunnel ramps / depressed-road plates at apt_elev−8 m and their
# retaining walls at deck level.  When the tile slice cuts one, its
# seam edge would otherwise sit metres above/below the neighbouring
# tile's raw terrain.  Per user 2026-06-10 these must MATCH the DEM at
# the seam and GRADE back to their design elevation inside the tile
# (``_grade_feature_piece_to_seam_dem``).  Groundside / boundary /
# clearance features already follow the DEM, so they agree at the seam
# naturally.
_SEAM_GRADE_FEATURE_ROLES = frozenset({
    ROLE_TUNNEL_RAMP, ROLE_RETAINING_WALL,
})

# Narrow exception set — covers real shapely degeneracy without
# masking programming errors (KeyError/TypeError/IndexError propagate).
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)


__all__ = ["cut_layout_at_tile_boundaries"]

# A vertex this close (m) to an integer tile line is a tile-cut seam
# boundary vertex (tile_cut offsets them ``half_width_m`` = 5 m off the
# line) — terrain-pinned and effectively immutable.
_SEAM_LINE_TOL_M = 6.0
# Within-junction grade cap (matches ROLE_GRADE_LIMITS[junction] = 1.5%).
_RUNWAY_SEAM_GRADE_CAP = 0.015
# Pavement roles that can be a tile-cut seam stub abutting a junction.
_SEAM_PIECE_ROLES = frozenset({
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_APRON, ROLE_BUILDING,
})

# AIRSIDE pavement roles whose NEIGHBOUR-TILE offcut — the piece this cut
# drops because its representative point falls in the adjacent tile — is
# recorded on ``layout.tile_seam_offcuts`` (owner ruling 2026-07-24, the
# adjacent-ground seam-prolongation; see config
# ``ADJACENT_GROUND_SEAM_PROLONG_ENABLED``).  The offcut is the ONLY
# in-build evidence of where the pavement really continues past the seam,
# so the adjacent-ground corridor march can prolong a cut-back frontage
# without ever inventing pavement that is not there.  Recorded (not
# emitted): nothing downstream renders these polygons.
_SEAM_OFFCUT_ROLES = frozenset({
    ROLE_RUNWAY, ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION, ROLE_APRON,
})

# TERRAIN-GRADING roles whose CUT-BACK edge is a DEM-anchored seam contract
# (owner rulings 2026-06-20 / 2026-07-24: "the tile seam at ALL points must
# be anchored at DEM"; STANDARDS.md — "every non-runway role takes the seam
# DEM directly at its own vertex").  A ``graded_strip`` is a CUT/FILL of
# terrain, so its cut-back edge is where that modification has to hand back
# to the untouched terrain the 10 m seam gap renders.  Before this pin the
# strip's cut-back nodes carried whatever the polygon difference
# interpolated along the ORIGINAL band chord — measured SPLP: a single
# straight 223 m edge, 3.3 m below its own DEM at one end, and the two tile
# halves disagreeing by up to 2.58 m (mean 0.96 m) along the seam.
_SEAM_DEM_TERRAIN_ROLES = frozenset({ROLE_GRADED_STRIP})
# Node spacing (m) along a pinned cut-back edge.  The polygon difference
# mints exactly TWO vertices per cut-back edge (the crossings), so without
# densification the pin would only anchor the ends and the surface between
# them would still be a chord.  Matches the runway seam-contact anchor
# spacing (``config.RUNWAY_SEAM_CONTACT_STEP_M``): finer than the DEM
# posting, so the emitted line IS the terrain line.  Nodes land on absolute
# multiples of the step in the layout frame — the anchor frame is the
# airport's, identical in both tile builds — so both halves of a seam place
# their nodes at the same stations.
_SEAM_TERRAIN_PIN_STEP_M = 10.0
# A ring vertex is ON a cut-back line within this distance.
_SEAM_CUTBACK_TOL_M = 0.20


def derive_tile_cut_lines(layout: PavementLayout) -> list:
    """The integer lat/lon lines this layout's footprint straddles, as
    LineStrings in local metres.

    ONE SOURCE for the cut geometry: ``cut_layout_at_tile_boundaries``
    cuts on these, and the post-unify seam re-pin
    (:func:`repin_airside_seam_cutbacks`) locates its cut-back edges from
    the same list, so the two passes can never disagree about where the
    seam is.  Empty when the layout has no anchor, no shapes, or no
    integer line strictly inside its bounds (the single-tile case).
    """
    if not layout.shapes or layout.anchor is None:
        return []
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    polys = [s.polygon for s in layout.shapes
             if s.polygon is not None and not s.polygon.is_empty]
    if not polys:
        return []
    try:
        union = unary_union(polys)
    except _GEOM_EXC:
        return []
    minx, miny, maxx, maxy = union.bounds

    # Footprint bounds in lat/lon.
    min_lat = lat0 + math.degrees(miny / R_EARTH)
    max_lat = lat0 + math.degrees(maxy / R_EARTH)
    min_lon = lon0 + math.degrees(minx / (R_EARTH * cos0))
    max_lon = lon0 + math.degrees(maxx / (R_EARTH * cos0))

    cut_lines: list[LineString] = []
    # Integer lat lines strictly inside the airport's lat range.
    for lat_int in range(
            int(math.ceil(min_lat)), int(math.floor(max_lat)) + 1):
        if min_lat < lat_int < max_lat:
            y_int = math.radians(lat_int - lat0) * R_EARTH
            cut_lines.append(LineString([
                (minx - 100.0, y_int), (maxx + 100.0, y_int)]))
    # Integer lon lines strictly inside the airport's lon range.
    for lon_int in range(
            int(math.ceil(min_lon)), int(math.floor(max_lon)) + 1):
        if min_lon < lon_int < max_lon:
            x_int = math.radians(lon_int - lon0) * R_EARTH * cos0
            cut_lines.append(LineString([
                (x_int, miny - 100.0), (x_int, maxy + 100.0)]))
    return cut_lines


def cutback_stations(t0: float, t1: float,
                     step: float = _SEAM_TERRAIN_PIN_STEP_M) -> list[float]:
    """The ABSOLUTE stations strictly between ``t0`` and ``t1``.

    ONE SOURCE for the cut-back densification spacing: both
    ``_pin_terrain_piece_seam_edge`` (graded strips) and
    :func:`repin_airside_seam_cutbacks` (airside pavement) place their
    nodes here, so a strip and the pavement beside it land on the SAME
    stations and the two tiles' independent builds reproduce them from
    the anchor frame alone.  Returned in traversal order (reversed when
    ``t1 < t0``); empty when the edge is shorter than one step.
    """
    if abs(t1 - t0) <= step:
        return []
    lo, hi = (t0, t1) if t1 > t0 else (t1, t0)
    stations = [k * step for k in range(int(math.floor(lo / step)) + 1,
                                        int(math.ceil(hi / step)) + 1)]
    stations = [t for t in stations if lo + 1e-6 < t < hi - 1e-6]
    if t1 < t0:
        stations.reverse()
    return stations


def cut_layout_at_tile_boundaries(
        layout: PavementLayout,
        half_width_m: float = TILE_CUT_HALF_WIDTH_M,
        min_piece_area_m2: float = 1.0,
        current_tile_lat: int | None = None,
        current_tile_lon: int | None = None,
        dem=None,
        skip_roles: frozenset = frozenset()) -> int:
    """Cut every shape crossing an integer lat or lon tile boundary,
    leaving a ``2 * half_width_m`` wide gap (default 10 m).

    Then DROP every shape piece whose representative point falls
    outside the current tile.  The neighbour-tile auto_patch run
    will generate the patch covering its portion.

    ``current_tile_lat`` / ``current_tile_lon`` identify the tile
    being processed by the driver — these can differ from the
    airport's anchor tile when a cross-tile airport is being
    processed during a NEIGHBOUR-tile build (e.g. Ortho4XP
    generates tile -13/-78, which includes SPLP because the
    airport extends into it, but SPLP's anchor is in -13/-77).
    When None, fall back to ``floor(layout.anchor)`` (the
    airport-anchor tile) — backward-compatible default for tests
    and direct ``build_airport_pavement`` calls.

    Mutates ``layout.shapes`` in place.  Returns the net change in
    shape count (positive when shapes split, negative when slivers
    fall below ``min_piece_area_m2`` and get dropped).

    ``skip_roles`` shapes are passed through UNTOUCHED — neither cut nor
    altitude-resampled.  Used by the POST-solve feature cut to freeze AIRSIDE
    pavement: it was already cut by the PRE-solve call and graded by the solver
    against the seam DEM anchors, so re-touching it here only clobbers those
    solved altitudes (the gapped airside edge grazes the cut buffer and triggers
    a spurious re-sample).  The single source of airside elevation truth is the
    solve.
    """
    if not layout.shapes or layout.anchor is None:
        return 0
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    cut_lines = derive_tile_cut_lines(layout)
    if not cut_lines:
        return 0
    # RECORD the lines this cut actually opened.  After the cut + drop the
    # layout no longer STRADDLES the line (its pieces stop 5 m short), so a
    # later pass cannot re-derive them from the footprint — the post-unify
    # airside seam re-pin reads them from here.  Recorded as
    # ``(axis, coordinate)`` in local metres, accumulated across the several
    # cut calls a build makes, deduplicated.
    recorded = list(getattr(layout, "tile_cut_lines", None) or ())
    for line in cut_lines:
        spec = _line_axis_spec(line)
        if spec is not None and spec not in recorded:
            recorded.append(spec)
    layout.tile_cut_lines = recorded    # type: ignore[attr-defined]

    try:
        cut_polys = [line.buffer(half_width_m, cap_style=2)
                     for line in cut_lines]
        cut_union = unary_union(cut_polys)
    except _GEOM_EXC:
        return 0

    # NOTE (user 2026-05-28): do NOT cut ``layout.airport_boundary`` here.
    # Cutting the outline polygon with the seam band inserted a straight
    # edge ALONG the tile line into the perimeter, and the boundary ribbon
    # (_emit_airport_boundary_shape traces the perimeter) then ran a ribbon
    # ALONG the seam.  The boundary must be sliced like every other shape:
    # the ribbon emits from the FULL outline and its emitted ROLE_BOUNDARY
    # rects are sliced + neighbour-tile pieces dropped by the post-emit
    # cut_layout_at_tile_boundaries call — so the ribbon ends AT the seam
    # instead of following it.

    # The CURRENT tile (the one this auto_patch run is generating)
    # is the airport-anchor tile.  Per user 2026-05-12: after the
    # cut, drop any shape (or shape piece) that's not inside the
    # current tile — when the neighbour tile is processed in its own
    # auto_patch run, IT generates the patch covering its portion of
    # the airport.  Without this drop, ``_runway_clamped_alt`` etc.
    # would try to sample the neighbour-tile DEM (which isn't
    # loaded) and substitute 0 m, producing altitude-0 boundary
    # rects in X-Plane.
    cur_tile_lat = (current_tile_lat if current_tile_lat is not None
                    else int(math.floor(lat0)))
    cur_tile_lon = (current_tile_lon if current_tile_lon is not None
                    else int(math.floor(lon0)))

    def _in_current_tile(poly: Polygon) -> bool:
        try:
            c = poly.representative_point()
        except _GEOM_EXC:
            try:
                c = poly.centroid
            except _GEOM_EXC:
                return True  # fail open
        lat = lat0 + math.degrees(c.y / R_EARTH)
        lon = lon0 + math.degrees(c.x / (R_EARTH * cos0))
        return (cur_tile_lat <= lat < cur_tile_lat + 1
                and cur_tile_lon <= lon < cur_tile_lon + 1)

    # (airport_boundary is intentionally left UNCUT — see note above; the
    # ribbon it generates is sliced as ordinary ROLE_BOUNDARY shapes below.)

    n_before = len(layout.shapes)
    new_shapes: list[BuiltShape] = []
    # Neighbour-tile OFFCUTS (see ``_SEAM_OFFCUT_ROLES``): the airside
    # pavement pieces this cut drops as out-of-tile.  Collected here and
    # published on the layout so the adjacent-ground march can bound its
    # seam prolongation by real pavement.
    seam_offcuts: list[Polygon] = []
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            new_shapes.append(s)
            continue
        if skip_roles and s.role in skip_roles:
            # Frozen (already cut pre-solve + solved) — pass through untouched.
            new_shapes.append(s)
            continue
        try:
            if not s.polygon.intersects(cut_union):
                # No cut — keep iff the shape is in the current tile.
                if _in_current_tile(s.polygon):
                    new_shapes.append(s)
                continue
            diff = s.polygon.difference(cut_union)
        except _GEOM_EXC:
            new_shapes.append(s)
            continue
        if diff.is_empty:
            # Source polygon entirely inside the cut buffer.  No
            # pavement pieces but a bridge will be emitted below.
            pieces: list[Polygon] = []
        elif diff.geom_type == "Polygon":
            pieces = [diff]
        elif diff.geom_type == "MultiPolygon":
            pieces = [g for g in diff.geoms
                      if g.geom_type == "Polygon" and not g.is_empty]
        else:
            # Unexpected result (e.g. non-empty GeometryCollection);
            # keep the original shape and skip the cut + bridge.
            if _in_current_tile(s.polygon):
                new_shapes.append(s)
            continue
        pieces = [p for p in pieces if p.area >= min_piece_area_m2]
        if s.role in _SEAM_OFFCUT_ROLES:
            seam_offcuts.extend(p for p in pieces
                                if not _in_current_tile(p))
        pieces = [p for p in pieces if _in_current_tile(p)]

        slope_sampler = _make_slope_sampler(s)
        for piece in pieces:
            new_s = _build_piece_shape(s, piece, slope_sampler)
            if new_s is not None:
                # Seam DEM is the top-priority anchor: pin this piece's
                # slice-edge vertices to the (Ortho4XP-smoothed) terrain
                # so the solver grades the surface down to the seam
                # (user 2026-05-20).  Session 51: extended to junctions
                # /aprons too (not just sloping rects) — in the single-
                # solve order their slice-edge vertices would otherwise be
                # fully soft and diverge between adjacent-tile builds
                # (test_cross_tile_cut_edge_elevations_consistent).  The
                # pin makes both tiles compute the same DEM value there.
                if RUNWAY_SEAM_DEM_PIN and s.role == ROLE_RUNWAY:
                    # Runway pieces take the REDISTRIBUTED FAA PROFILE at
                    # every vertex (user SPLP seam-dip report 2026-07-03).
                    # The profile already folds the seam DEM at the
                    # centerline-boundary crossing (the one point where
                    # "seam = threshold at DEM" is well-defined — user
                    # 2026-06-20), so per-vertex DEM pins added nothing at
                    # benign seams and carved a terrain notch into the
                    # runway at oblique ones: SPLP's seam crosses RW02/20
                    # at 18°, its two band-edge corners span 141 m of
                    # station, and their raw-DEM values (55.5 / 59.7 —
                    # a ravine wall) violate the 1.5 % cap by 2×, so the
                    # emitted surface V-notched 4.2 m and every
                    # ``runway_clamp_floor`` computed from it was poisoned
                    # (the mirrored junction dips).  Profile evaluation is
                    # deterministic across adjacent tile builds (same CIFP
                    # + same boundary HGT pixels), which is all the
                    # 2026-06-20 pin actually needed.  Falls back to the
                    # DEM pin when no CIFP profile exists for the ref.
                    #
                    # ★ 2026-07-25 owner ruling (config
                    # ``RUNWAY_SEAM_VERTEX_DEM_PIN``): "every node along
                    # the tile seam cutback MUST be exactly at DEM ...
                    # definitely including the runway."  The 4.2 m V-notch
                    # above no longer reproduces — re-measured at the same
                    # corners it is 2.03 m over 140.86 m of station =
                    # 1.44 %, inside the cap, and the OLD sampler reads the
                    # same, so the ravine wall was a DEM-STATE artifact,
                    # not terrain.  With the gate ON the runway takes the
                    # per-vertex DEM pin like every other role; the profile
                    # path stays as the fallback for a ref the DEM cannot
                    # value.
                    from .config import RUNWAY_SEAM_VERTEX_DEM_PIN
                    if RUNWAY_SEAM_VERTEX_DEM_PIN:
                        if not _terrain_pin_slice_nodes(
                                new_s, cut_union, (), layout, dem,
                                cur_tile_lat, cur_tile_lon):
                            # DEM valued nothing here — the profile is the
                            # fallback, exactly as before the ruling.
                            _pin_runway_piece_to_profile(
                                new_s, cut_union, layout)
                    elif not _pin_runway_piece_to_profile(
                            new_s, cut_union, layout):
                        _terrain_pin_slice_nodes(
                            new_s, cut_union, (), layout, dem,
                            cur_tile_lat, cur_tile_lon)
                elif s.role in _PIN_SLICE_ROLES:
                    _terrain_pin_slice_nodes(
                        new_s, cut_union, (), layout, dem,
                        cur_tile_lat, cur_tile_lon)
                elif s.role in _SEAM_GRADE_FEATURE_ROLES:
                    _grade_feature_piece_to_seam_dem(
                        new_s, cut_union, layout, dem,
                        cur_tile_lat, cur_tile_lon)
                elif s.role in _SEAM_DEM_TERRAIN_ROLES:
                    _pin_terrain_piece_seam_edge(
                        new_s, cut_lines, half_width_m, layout, dem,
                        cur_tile_lat, cur_tile_lon)
                new_shapes.append(new_s)
    layout.shapes = new_shapes
    if seam_offcuts:
        prior = list(getattr(layout, "tile_seam_offcuts", None) or ())
        layout.tile_seam_offcuts = prior + seam_offcuts

    # Absorb the tiny wedges the slice leaves on either side back into
    # their adjacent shape, so the cut doesn't leave an extra sliver
    # (user 2026-05-23).  The wedge's seam-edge vertices carry the
    # terrain-pinned (critical) seam altitude into the merged shape.
    _absorb_seam_slivers(layout, cut_lines, half_width_m)

    return len(layout.shapes) - n_before


# Roles that participate in the airside pavement partition — only these
# absorb / are absorbed by the seam-sliver pass (boundary ribbon, DEM
# bridge, runway and groundside have their own seam handling).
_ABSORB_ROLES = frozenset({
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
    ROLE_CROSS_CONNECTOR, ROLE_JUNCTION, ROLE_APRON, ROLE_BUILDING,
})


def _absorb_seam_slivers(layout: PavementLayout,
                         cut_lines: list,
                         half_width_m: float) -> int:
    """Merge each tiny slice-created seam wedge into its adjacent
    (larger) shape so the tile cut leaves no extra sliver on either
    side of the slice.

    A wedge is a SMALL piece that (a) has ≥ 2 vertices on a cut line
    (a seam edge) and (b) hugs ONE larger neighbour — it shares ≥ 40 %
    of its own perimeter with that neighbour (i.e. it is a fragment of,
    or flush against, that shape).  It is unioned into the neighbour and
    dropped.

    Elevation is reconciled per-vertex from BOTH shapes' existing
    altitudes (the wedge's terrain-pinned seam-edge altitudes win for
    the seam vertices, which is the whole point — the slice-edge
    altitude is what X-Plane stitches neighbouring tiles against).  The
    merged shape becomes ``node_altitudes`` (it is no longer a clean
    4-corner rect).  Returns the number of wedges absorbed.
    """
    if not cut_lines or not layout.shapes:
        return 0
    SLIVER_MAX_AREA_M2 = 150.0
    NEIGHBOUR_MIN_RATIO = 1.5
    SHARE_TOL_M = 0.5            # near-adjacency band for shared length
    SHARE_MIN_M = 3.0           # min real contact with the neighbour
    SEAM_VERTEX_TOL_M = half_width_m + 2.0

    def _near_seam(x: float, y: float) -> bool:
        p = Point(x, y)
        return any(line.distance(p) <= SEAM_VERTEX_TOL_M
                   for line in cut_lines)

    def _seam_vertex_count(poly: Polygon) -> int:
        ring = list(poly.exterior.coords)
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        return sum(1 for (x, y) in ring if _near_seam(x, y))

    def _near_shared_len(a: Polygon, b: Polygon) -> float:
        # Length of a's boundary lying within SHARE_TOL_M of b — robust
        # to the small float offsets the slice leaves between touching
        # pieces (exact boundary∩boundary reads ~0 there).
        try:
            return a.exterior.intersection(
                b.buffer(SHARE_TOL_M)).length
        except _GEOM_EXC:
            return 0.0

    absorbed = 0
    dropped: set = set()
    # Iterate: absorbing one wedge can make an adjacent wedge flush with
    # the now-larger neighbour (e.g. a junction triangle beside a
    # connector slice that itself merges into the connector bulk).
    for _pass in range(6):
        changed = False
        shapes = layout.shapes
        for sv in list(shapes):
            if id(sv) in dropped:
                continue
            if (sv.role not in _ABSORB_ROLES
                    or sv.polygon is None or sv.polygon.is_empty
                    or sv.polygon.geom_type != "Polygon"):
                continue
            try:
                sv_area = sv.polygon.area
            except _GEOM_EXC:
                continue
            if sv_area >= SLIVER_MAX_AREA_M2:
                continue
            if _seam_vertex_count(sv.polygon) < 2:
                continue
            # Neighbour sharing the most boundary (near-adjacency), at
            # least NEIGHBOUR_MIN_RATIO larger than the wedge.
            best = None
            best_share = 0.0
            for nb in shapes:
                if nb is sv or id(nb) in dropped:
                    continue
                if (nb.role not in _ABSORB_ROLES
                        or nb.polygon is None or nb.polygon.is_empty
                        or nb.polygon.geom_type != "Polygon"):
                    continue
                if nb.polygon.area < NEIGHBOUR_MIN_RATIO * sv_area:
                    continue
                shlen = _near_shared_len(sv.polygon, nb.polygon)
                if shlen > best_share:
                    best_share = shlen
                    best = nb
            if best is None or best_share < SHARE_MIN_M:
                continue
            ok = _absorb_one_sliver(sv, best)
            if ok:
                dropped.add(id(sv))
                absorbed += 1
                changed = True
        if not changed:
            break

    if dropped:
        layout.shapes = [s for s in layout.shapes if id(s) not in dropped]
    if absorbed:
        try:
            import O4_UI_Utils as UI
            UI.vprint(1,
                f"  [pav-builder] absorbed {absorbed} tile-slice seam "
                f"wedge(s) into adjacent shape(s).")
        except Exception:
            pass
    return absorbed


def _absorb_one_sliver(sv: BuiltShape, nb: BuiltShape) -> bool:
    """Union wedge ``sv`` into neighbour ``nb`` in place, reconciling
    per-vertex altitudes (the wedge's terrain-pinned seam-edge altitudes
    are carried in).  ``nb`` becomes a ``node_altitudes`` shape.  Returns
    True on success (caller drops ``sv``)."""
    try:
        merged = unary_union([nb.polygon, sv.polygon])
        if merged.geom_type == "MultiPolygon":
            # Tiny float gap between touching pieces — bridge it.
            merged = merged.buffer(0.05).buffer(-0.05)
    except _GEOM_EXC:
        return False
    if (merged.is_empty or merged.geom_type != "Polygon"
            or not merged.is_valid):
        return False
    # Altitude lookup from BOTH source shapes (seam-pinned wedge
    # vertices included — they win for the seam edge).
    src: dict = {}
    for sh in (nb, sv):
        coords, alts = _shape_corner_alts(sh)
        if alts is None:
            continue
        for (x, y), a in zip(coords, alts):
            if a is not None:
                src[vertex_bucket(x, y)] = float(a)
    if not src:
        return False
    ring = list(merged.exterior.coords)
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3:
        return False
    merged_alts: list = []
    for (x, y) in ring:
        b = vertex_bucket(x, y)
        if b in src:
            merged_alts.append(src[b])
            continue
        # Vertex introduced by the union (rare) — nearest source alt.
        best_a = None
        best_d2 = 4.0  # within 2 m
        for sh in (nb, sv):
            coords, alts = _shape_corner_alts(sh)
            if alts is None:
                continue
            for (cx, cy), a in zip(coords, alts):
                if a is None:
                    continue
                d2 = (cx - x) ** 2 + (cy - y) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best_a = float(a)
        if best_a is None:
            return False
        merged_alts.append(best_a)
    if len(merged_alts) != len(ring):
        return False
    nb.polygon = merged
    nb.node_altitudes = merged_alts + [merged_alts[0]]
    nb.altitude_high = None
    nb.altitude_low = None
    return True


def _shape_corner_alts(s: BuiltShape):
    """Return ``(open_coords, open_alts)`` — the shape's exterior ring
    (closing repeat dropped) and a per-vertex elevation list, or
    ``(open_coords, None)`` when no elevation is known."""
    if s.polygon is None or s.polygon.is_empty:
        return [], None
    try:
        coords = list(s.polygon.exterior.coords)
    except _GEOM_EXC:
        return [], None
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    n = len(coords)
    if n == 0:
        return coords, None
    if s.node_altitudes and len(s.node_altitudes) >= n:
        return coords, [float(s.node_altitudes[k]) for k in range(n)]
    if s.altitude_high is not None and s.altitude_low is not None:
        sampler = _make_slope_sampler(s)
        if sampler is not None:
            return coords, [sampler(x, y) for x, y in coords]
    if s.altitude is not None:
        return coords, [float(s.altitude)] * n
    return coords, None


def _make_slope_sampler(
        s: BuiltShape) -> Callable[[float, float], float] | None:
    """Build a closure that samples a sloped 4-corner rect's
    elevation at any (x, y) by projecting onto the high-mid → low-mid
    axis.  Returns None when ``s`` isn't a 4-corner sloped rect.
    """
    if s.altitude_high is None or s.altitude_low is None:
        return None
    if s.polygon is None or s.polygon.is_empty:
        return None
    try:
        coords = list(s.polygon.exterior.coords)
    except _GEOM_EXC:
        return None
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) != 4:
        return None
    high_mid_x = 0.5 * (coords[0][0] + coords[3][0])
    high_mid_y = 0.5 * (coords[0][1] + coords[3][1])
    low_mid_x = 0.5 * (coords[1][0] + coords[2][0])
    low_mid_y = 0.5 * (coords[1][1] + coords[2][1])
    ax = low_mid_x - high_mid_x
    ay = low_mid_y - high_mid_y
    L2 = ax * ax + ay * ay
    H = float(s.altitude_high)
    L = float(s.altitude_low)
    if L2 < 1e-6:
        avg = 0.5 * (H + L)
        return lambda x, y: avg

    def sample(x: float, y: float) -> float:
        t = ((x - high_mid_x) * ax + (y - high_mid_y) * ay) / L2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        return H + t * (L - H)
    return sample


def _pin_runway_piece_to_profile(fs, cut_union, layout) -> bool:
    """Rewrite a cut runway piece's ``node_altitudes`` from the runway's
    REDISTRIBUTED FAA profile and record its slice-edge vertex buckets as
    seam anchors.

    The profile (``runway_redistribute.sample_redistributed_profile``) is
    laterally flat and already anchored to the seam DEM at the
    centerline-boundary crossing, so every piece vertex — including the
    band-edge corners an oblique seam fans across the runway's width —
    lands on one FAA-compliant, cross-tile-deterministic surface.
    Replaces both the nearest-neighbour resample from the parent ring
    (which grabbed whichever vertex was closest — the SPLP 4.6 m
    cross-seam step of 2026-06-20) and the per-vertex raw-DEM pin that
    fixed it (which carved the terrain into the runway — the SPLP 4.2 m
    seam V-notch of 2026-07-03).

    Returns ``False`` (caller falls back to the DEM pin) when no
    redistributed profile exists for the piece's ref.
    """
    from .runway_redistribute import sample_redistributed_profile
    if (fs.ref is None or fs.polygon is None or fs.polygon.is_empty
            or layout is None):
        return False
    try:
        coords = list(fs.polygon.exterior.coords)
        cut_boundary = cut_union.boundary
    except _GEOM_EXC:
        return False
    if sample_redistributed_profile(layout, fs.ref,
                                    *coords[0][:2]) is None:
        return False
    seam_keys = getattr(layout, "_seam_anchor_keys", None)
    if seam_keys is None:
        seam_keys = set()
        layout._seam_anchor_keys = seam_keys  # type: ignore[attr-defined]
    alts = []
    for (x, y) in coords:
        v = sample_redistributed_profile(layout, fs.ref, x, y)
        if v is None:
            return False
        alts.append(round(float(v), 2))
        try:
            if Point(x, y).distance(cut_boundary) < 0.75:
                seam_keys.add(vertex_bucket(float(x), float(y)))
        except _GEOM_EXC:
            continue
    fs.node_altitudes = alts
    fs.altitude = None
    fs.altitude_high = None
    fs.altitude_low = None
    return True


def _line_axis_spec(line):
    """``(axis, coordinate)`` of an axis-aligned cut line, else None.

    ``axis`` is 0 for a vertical (constant-x) line, 1 for a horizontal one
    — the same convention ``_cutback_line_specs`` returns.
    """
    try:
        (ax, ay), (bx, by) = list(line.coords)[0], list(line.coords)[-1]
    except (_GEOM_EXC + (IndexError, ValueError)):
        return None
    if abs(bx - ax) < 1e-6:
        return (0, ax)
    if abs(by - ay) < 1e-6:
        return (1, ay)
    return None


def cutback_specs_for_layout(layout, half_width_m=TILE_CUT_HALF_WIDTH_M):
    """The ``(axis, coordinate)`` cut-back lines of this layout.

    Prefers ``layout.tile_cut_lines`` — the lines a real
    ``cut_layout_at_tile_boundaries`` call recorded — because after the cut
    the footprint no longer straddles the tile line and cannot be used to
    re-derive them.  Falls back to deriving from the footprint (a layout
    that has not been cut yet, e.g. in tests).
    """
    recorded = getattr(layout, "tile_cut_lines", None)
    if recorded:
        specs = []
        for axis, c in recorded:
            specs.append((axis, c - half_width_m))
            specs.append((axis, c + half_width_m))
        return specs
    return _cutback_line_specs(derive_tile_cut_lines(layout), half_width_m)


def _cutback_line_specs(cut_lines, half_width_m):
    """The CUT-BACK lines of a cut, as ``(axis, coordinate)`` pairs in local
    metres — ``axis`` 0 for a vertical (constant-x) line, 1 for a horizontal
    one.  ``cut_lines`` are the integer lat/lon lines the cut buffered;
    each contributes the two lines ``+/- half_width_m`` off it, which is
    exactly where the surviving pavement (and now the graded strip) ends."""
    specs: list[tuple[int, float]] = []
    for line in cut_lines:
        try:
            (ax, ay), (bx, by) = list(line.coords)[0], list(line.coords)[-1]
        except (_GEOM_EXC + (IndexError, ValueError)):
            continue
        if abs(bx - ax) < 1e-6:            # constant x -> vertical line
            axis, c = 0, ax
        elif abs(by - ay) < 1e-6:          # constant y -> horizontal line
            axis, c = 1, ay
        else:
            continue
        specs.append((axis, c - half_width_m))
        specs.append((axis, c + half_width_m))
    return specs


def _pin_terrain_piece_seam_edge(fs, cut_lines, half_width_m, layout,
                                 dem, tile_lat, tile_lon) -> int:
    """DENSIFY and DEM-PIN the cut-back edges of a terrain-grading piece
    (``_SEAM_DEM_TERRAIN_ROLES``).  Returns the number of nodes pinned.

    The cut's polygon difference leaves a graded strip ending on a cut-back
    line with just the two crossing vertices, valued by interpolation along
    whatever band chord happened to cross — a value with no relation to the
    terrain the neighbouring 10 m seam gap renders, and one the OTHER tile's
    independent build has no way to reproduce.  This pass replaces that edge
    with a terrain LINE: nodes every ``_SEAM_TERRAIN_PIN_STEP_M`` at
    absolute stations, each at its own DEM altitude.

    CROSS-TILE DETERMINISM: the pin is a pure function of (cut-back line
    position, station spacing, DEM) — no build state — and adjacent tiles
    read the SAME terrain there (the airport elevation inset is composited
    into both tiles' working DEM, and Ortho4XP's per-tile raster carries a
    0.01 deg halo, so the two rasters agree bit-for-bit across the seam
    despite differing resolutions).  Both halves therefore land on the
    terrain line and meet it from their own side."""
    if (not TILE_SEAM_TERRAIN_DEM_PIN_ENABLED
            or dem is None or layout is None or fs.polygon is None
            or fs.polygon.is_empty or not fs.node_altitudes):
        return 0
    specs = _cutback_line_specs(cut_lines, half_width_m)
    if not specs:
        return 0
    try:
        coords = list(fs.polygon.exterior.coords)
    except _GEOM_EXC:
        return 0
    alts = list(fs.node_altitudes)
    if len(coords) < 4 or len(alts) < len(coords):
        return 0
    nodata = getattr(dem, "nodata", -32768)

    def _dem_at(x: float, y: float):
        try:
            lat, lon = layout.m_to_ll(x, y)
            v = float(dem.alt((lon - tile_lon, lat - tile_lat)))
        except _GEOM_EXC:
            return None
        if v != v or v == nodata:
            return None
        return v

    step = _SEAM_TERRAIN_PIN_STEP_M
    open_n = len(coords) - 1

    def _spec_of(i):
        for axis, c in specs:
            if abs(coords[i][axis] - c) <= _SEAM_CUTBACK_TOL_M:
                return (axis, c)
        return None

    on_spec = [_spec_of(i) for i in range(open_n)]
    if not any(on_spec):
        return 0
    out_xy: list[tuple[float, float]] = []
    out_z: list[float] = []
    n_pinned = 0
    for i in range(open_n):
        x0, y0 = coords[i][0], coords[i][1]
        out_xy.append((x0, y0))
        v0 = _dem_at(x0, y0) if on_spec[i] is not None else None
        if v0 is None:
            out_z.append(alts[i])
        else:
            out_z.append(round(v0, 2))
            n_pinned += 1
        # A CUT-BACK EDGE is one whose BOTH ends sit on the SAME cut-back
        # line: densify it onto absolute stations so the emitted line
        # follows terrain instead of chording across it.
        j = (i + 1) % open_n
        if on_spec[i] is None or on_spec[i] != on_spec[j]:
            continue
        var = 1 - on_spec[i][0]          # the coordinate that varies
        t0, t1 = coords[i][var], coords[j][var]
        # Shared station math (``cutback_stations``) — the airside re-pin
        # sweep places its nodes on the very same absolute multiples, so a
        # graded strip and the pavement it abuts meet vertex-for-vertex.
        ts = cutback_stations(t0, t1, step)
        for t in ts:
            px = ((coords[i][0], t) if var == 1 else (t, coords[i][1]))
            v = _dem_at(px[0], px[1])
            if v is None:
                continue
            out_xy.append(px)
            out_z.append(round(v, 2))
            n_pinned += 1
    if not n_pinned:
        return 0
    out_xy.append(out_xy[0])
    out_z.append(out_z[0])
    try:
        poly = Polygon(out_xy)
        if poly.is_empty or not poly.is_valid:
            return 0
    except _GEOM_EXC:
        return 0
    fs.polygon = poly
    fs.node_altitudes = out_z
    return n_pinned


# ── AIRSIDE SEAM RE-PIN (owner ruling 2026-07-25) ─────────────────────────
# AIRSIDE pavement roles whose cut-back edges the post-unify sweep
# densifies and DEM-pins.  ROLE_RUNWAY was deliberately ABSENT until
# 2026-07-26: it carries an FAA vertical profile as well as the seam
# contract, so a raw per-vertex overwrite of the runway ring here was held
# to risk the 4.2 m V-notch of 2026-07-03 (see ``config.RUNWAY_SEAM_DEM_PIN``
# for that ruling's reasoning).
#
# ★ 2026-07-26 owner ruling (``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``):
#   "ALL nodes along the seam MUST be at exact DEM and anchored BEFORE the
#    solve, then the solver can grade between them and its other anchors to
#    maintain grade."
# The runway joins the sweep — see ``_seam_repin_roles``.  The V-notch that
# motivated the exclusion was re-measured on 2026-07-25 at 1.44 % (inside
# the 1.5 % cap) and traced to the DEM state of 2026-07-03.
_AIRSIDE_SEAM_REPIN_ROLES = frozenset({
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_APRON, ROLE_RUNWAY_CROSSING,
})


def _seam_repin_roles() -> frozenset:
    """The roles :func:`repin_airside_seam_cutbacks` sweeps.

    Reads the gate at CALL time (not import time) so a test can flip
    ``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS`` with ``monkeypatch.setattr``
    and get the pre-ruling role set back.
    """
    from . import config as _cfg
    if getattr(_cfg, "RUNWAY_SEAM_CUTBACK_DEM_ANCHORS", False):
        return _AIRSIDE_SEAM_REPIN_ROLES | {ROLE_RUNWAY}
    return _AIRSIDE_SEAM_REPIN_ROLES


def repin_airside_seam_cutbacks(layout, dem, tile_lat: int, tile_lon: int,
                                half_width_m: float = TILE_CUT_HALF_WIDTH_M
                                ) -> tuple[int, int]:
    """DENSIFY and DEM-pin every AIRSIDE cut-back edge.  Idempotent.

    Returns ``(vertices_inserted, vertices_pinned)``.

    ``tile_cut`` mints exactly the two slice crossings on each cut-back
    edge, so a long airside seam edge ran between DEM-true ends with
    nothing in between — a chord across the terrain the 10 m seam gap
    renders at raw DEM, and no shared node for the neighbouring tile's
    independent build to agree on.  This sweep runs once at the end of
    ``pipeline._unify_airside_geometry`` (the FINAL pre-solve node set, so
    every vertex it mints is a solver node) and:

      1. densifies each cut-back edge onto the absolute stations
         :func:`cutback_stations` yields — the SAME source the
         graded-strip pin uses, so strip and pavement meet vertex for
         vertex;
      2. sets every seam vertex, pre-existing or newly minted, to
         ``dem.alt`` at its own position (on shapes that carry
         ``node_altitudes``; a SOFT pre-solve shape has none, and the
         solver re-samples the DEM at every registered bucket anyway);
      3. registers each seam vertex's bucket on
         ``layout._seam_anchor_keys``, which is what makes the per-surface
         solver HARD-anchor it on writeback instead of letting the body
         fill drag it up to the route level.

    Pure function of (cut-back line, station spacing, DEM) — no build
    state — so both tiles land on the identical node set and the identical
    altitudes.  A no-op returning ``(0, 0)`` when the gate is off, the
    layout has no anchor/DEM, or no integer tile line crosses the
    footprint (every single-tile airport).

    ★ ROLE_RUNWAY joined the swept roles on 2026-07-26 (owner ruling,
    ``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``; see
    :func:`_seam_repin_roles`).  Its cut-back edge carried ONLY the two
    slice crossings ``cut_layout_at_tile_boundaries`` mints — 148 m apart at
    SPLP's 18-degree oblique crossing — and every node later inserted
    between them (emit-time chord densification, the epsilon-wedge weld) was
    valued by PLAIN LERP, floating up to 0.45 m above the terrain the 10 m
    gap renders.  Densifying pre-solve onto the shared stations both fixes
    the values and removes the lerp source (no chord long enough to densify).
    """
    from .config import AIRSIDE_SEAM_DEM_REPIN
    if (not AIRSIDE_SEAM_DEM_REPIN or dem is None or layout is None
            or not getattr(layout, "shapes", None)
            or getattr(layout, "anchor", None) is None):
        return (0, 0)
    specs = cutback_specs_for_layout(layout, half_width_m)
    if not specs:
        return (0, 0)
    nodata = getattr(dem, "nodata", -32768)

    def _dem_at(x: float, y: float):
        try:
            lat, lon = layout.m_to_ll(x, y)
            v = float(dem.alt((lon - tile_lon, lat - tile_lat)))
        except _GEOM_EXC:
            return None
        if v != v or v == nodata:
            return None
        return v

    def _spec_of(x: float, y: float):
        point = (x, y)
        for axis, c in specs:
            if abs(point[axis] - c) <= _SEAM_CUTBACK_TOL_M:
                return (axis, c)
        return None

    seam_keys = getattr(layout, "_seam_anchor_keys", None)
    if seam_keys is None:
        seam_keys = set()
        layout._seam_anchor_keys = seam_keys  # type: ignore[attr-defined]

    step = _SEAM_TERRAIN_PIN_STEP_M
    n_inserted = 0
    n_pinned = 0
    roles = _seam_repin_roles()
    for shape in layout.shapes:
        if shape.role not in roles:
            continue
        if shape.polygon is None or shape.polygon.is_empty:
            continue
        try:
            coords = list(shape.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        if len(coords) < 4:
            continue
        open_n = len(coords) - 1
        on_spec = [_spec_of(coords[i][0], coords[i][1])
                   for i in range(open_n)]
        if not any(spec is not None for spec in on_spec):
            continue
        # A shape carrying per-vertex altitudes keeps its array aligned
        # with the ring.  A shape still tagged as a flat/sloping RECT
        # (``altitude``/``altitude_high``) is left to the cut's own rect
        # path — densifying it would break the 4-corner invariant that
        # tagging depends on — but its seam buckets are still registered,
        # which is what actually holds the vertex in the solve.
        alts = (list(shape.node_altitudes[:len(coords)])
                if shape.node_altitudes
                and len(shape.node_altitudes) >= len(coords) else None)
        rect_tagged = alts is None and (
            shape.altitude is not None
            or shape.altitude_high is not None
            or shape.altitude_low is not None)
        out_xy: list[tuple[float, float]] = []
        out_z: list[float] = []
        n_inserted_here = 0
        values_changed = False
        for i in range(open_n):
            x0, y0 = coords[i][0], coords[i][1]
            out_xy.append((x0, y0))
            value = _dem_at(x0, y0) if on_spec[i] is not None else None
            if value is None:
                out_z.append(alts[i] if alts is not None else 0.0)
            else:
                rounded = round(value, 2)
                if alts is not None and abs(alts[i] - rounded) > 1e-9:
                    values_changed = True
                out_z.append(rounded)
                seam_keys.add(vertex_bucket(float(x0), float(y0)))
                n_pinned += 1
            # A CUT-BACK EDGE has BOTH ends on the SAME cut-back line.
            # Already-densified edges yield NO stations (consecutive
            # vertices sit exactly one step apart) — that is what makes a
            # second sweep insert nothing.
            j = (i + 1) % open_n
            if on_spec[i] is None or on_spec[i] != on_spec[j] or rect_tagged:
                continue
            var = 1 - on_spec[i][0]          # the coordinate that varies
            for t in cutback_stations(coords[i][var], coords[j][var], step):
                point = ((coords[i][0], t) if var == 1 else (t, coords[i][1]))
                value = _dem_at(point[0], point[1])
                if value is None:
                    continue
                out_xy.append(point)
                out_z.append(round(value, 2))
                seam_keys.add(vertex_bucket(float(point[0]), float(point[1])))
                n_inserted_here += 1
                n_pinned += 1
        if n_inserted_here:
            try:
                poly = Polygon(out_xy + [out_xy[0]])
                if poly.is_empty or not poly.is_valid:
                    continue                # keep the ring, drop the insert
            except _GEOM_EXC:
                continue
            shape.polygon = poly
            n_inserted += n_inserted_here
        elif not values_changed:
            continue                        # nothing to rewrite (idempotent)
        # NEVER fabricate an altitude array: a SOFT pre-solve shape has no
        # altitudes yet and must stay soft (the solver seeds it from the
        # DEM and hard-holds exactly the seam buckets registered above).
        if alts is not None:
            shape.node_altitudes = out_z + [out_z[0]]
    return (n_inserted, n_pinned)


def _terrain_pin_slice_nodes(fs, cut_union, clip_pts, layout,
                             dem, tile_lat, tile_lon) -> int:
    """Overwrite a filler's slice-edge ``node_altitudes`` with the DEM
    terrain altitude (so they follow the tilted terrain at a steep
    crossing instead of the rect's flat end value), leaving nodes shared
    with the clean rect's perpendicular clip edge (``clip_pts``)
    untouched.  The pinned buckets are recorded on
    ``layout._seam_anchor_keys`` so the per-surface solver HARD-anchors
    them to these terrain altitudes (otherwise the final solve grades
    them back toward the flat rect).

    Returns the NUMBER of vertices pinned, so the runway caller (owner
    ruling 2026-07-25, ``config.RUNWAY_SEAM_VERTEX_DEM_PIN``) can fall
    back to the redistributed FAA profile when the DEM valued nothing."""
    if (dem is None or layout is None
            or fs.polygon is None or fs.polygon.is_empty):
        return 0
    try:
        cut_boundary = cut_union.boundary
        coords = list(fs.polygon.exterior.coords)
    except _GEOM_EXC:
        return 0
    nodata = getattr(dem, "nodata", -32768)

    def _dem_at(x: float, y: float) -> float | None:
        try:
            lat, lon = layout.m_to_ll(x, y)
            v = float(dem.alt((lon - tile_lon, lat - tile_lat)))
        except _GEOM_EXC:
            return None
        if v != v or v == nodata:  # NaN / no-data
            return None
        return v

    # Single-solve order (session 51): tile_cut runs PRE-solve, so a
    # cut piece typically has NO altitude data yet (node_altitudes /
    # altitude / altitude_high all None).  DEM-seed every vertex so the
    # slice-edge HARD pins below have a backing array and the solver
    # warm-starts the soft (interior) vertices from terrain.  Guarded on
    # "no altitude data at all" so it never clobbers a solved flat
    # ``altitude`` (post-solve feature pieces keep their tags).
    created_from_dem = False
    if fs.node_altitudes and len(fs.node_altitudes) >= len(coords):
        alts = list(fs.node_altitudes)
    elif (fs.node_altitudes is None and fs.altitude is None
          and fs.altitude_high is None and fs.altitude_low is None):
        alts = [round(_dem_at(x, y) or 0.0, 2) for (x, y) in coords]
        created_from_dem = True
    else:
        return 0
    seam_keys = getattr(layout, "_seam_anchor_keys", None)
    if seam_keys is None:
        seam_keys = set()
        layout._seam_anchor_keys = seam_keys  # type: ignore[attr-defined]
    changed = False
    n_pinned = 0
    # AIRSIDE pins are RUNWAY-CLAMPED (user SPLP report 2026-07-03): the
    # raw-DEM pin sat metres below the design surface next to a runway,
    # making the pin↔runway chain infeasible — the solve split the
    # violation into a V-notch at the seam (mirrored on both tiles).  The
    # clamp floor comes from CIFP-profiled runways, identical on both
    # tiles, so cross-tile continuity is preserved.  ROLE_RUNWAY is not in
    # ``_PIN_SLICE_ROLES``, so a runway arriving here under
    # ``RUNWAY_SEAM_VERTEX_DEM_PIN`` is never clamped: it takes the RAW DEM
    # at its own vertex, which is exactly what the 2026-07-25 ruling asks
    # for ("every node along the tile seam cutback MUST be exactly at DEM").
    #
    # ★ 2026-07-24 owner ruling: the clamp is OFF by default
    # (``config.SEAM_PIN_RUNWAY_CLAMP``) — a cut-back slice-edge node IS the
    # DEM at its own position, because the 10 m gap this cut opens renders
    # at raw DEM and any lift shows as a gutter under the pavement.
    from .seam_anchors import runway_clamp_floor
    from .config import SEAM_PIN_RUNWAY_CLAMP
    _clamp = (SEAM_PIN_RUNWAY_CLAMP and fs.role in _PIN_SLICE_ROLES)
    for i, (x, y) in enumerate(coords):
        # Skip the corners shared with the clean rect (the flat join).
        if any(math.hypot(x - cp[0], y - cp[1]) < 0.5 for cp in clip_pts):
            continue
        try:
            if Point(x, y).distance(cut_boundary) >= 0.75:
                continue  # not a slice-edge node
        except _GEOM_EXC:
            continue
        v = _dem_at(x, y)
        if v is None:
            continue
        if _clamp:
            try:
                f = runway_clamp_floor(layout, x, y)
            except _GEOM_EXC:
                f = None
            if f is not None and f > v:
                v = f
        alts[i] = round(v, 2)
        seam_keys.add(vertex_bucket(float(x), float(y)))
        n_pinned += 1
        changed = True
    if changed or created_from_dem:
        fs.node_altitudes = alts
        if created_from_dem:
            # The piece is now a DEM-seeded node_altitudes shape; clear
            # the (None) rect tags so the solver treats it consistently.
            fs.altitude_high = None
            fs.altitude_low = None
            fs.altitude = None
    return n_pinned


def _grade_feature_piece_to_seam_dem(
        fs: BuiltShape,
        cut_union,
        layout,
        dem,
        tile_lat: int,
        tile_lon: int,
        grade_cap: float = TUNNEL_RAMP_MAX_GRADE,
) -> None:
    """Post-solve feature piece cut at a tile seam: pin its slice-edge
    vertices to the seam DEM and grade every other vertex from the seam
    toward the piece's design elevation at ≤ ``grade_cap``.

    Per user 2026-06-10: every shape must MATCH the terrain at the tile
    boundary — the neighbouring tile renders raw DEM there — and ramp
    back to its own level inside the tile.  Without this, a depressed-
    road plate (apt_elev−8 m) or a deck-level retaining wall cut at the
    seam presents an 8 m vertical face against the next tile's terrain.

    Mutates ``fs`` in place: converts to ``node_altitudes`` (seam
    vertices at DEM, interior clamped to the cap-feasible band toward
    the design elevation).  No-op when the piece has no slice-edge
    vertex or no elevation data.
    """
    if (dem is None or layout is None
            or fs.polygon is None or fs.polygon.is_empty):
        return
    try:
        cut_boundary = cut_union.boundary
        coords = list(fs.polygon.exterior.coords)
    except _GEOM_EXC:
        return
    if len(coords) < 4:
        return
    # Per-vertex DESIGN elevations from the piece's existing tags
    # (``_build_piece_shape`` has already converted sloped quads to
    # node_altitudes; flat plates carry ``altitude``).
    if fs.node_altitudes and len(fs.node_altitudes) >= len(coords):
        design = [float(a) for a in fs.node_altitudes[:len(coords)]]
    elif fs.altitude is not None:
        design = [float(fs.altitude)] * len(coords)
    else:
        return
    nodata = getattr(dem, "nodata", -32768)

    def _dem_at(x: float, y: float) -> float | None:
        try:
            lat, lon = layout.m_to_ll(x, y)
            v = float(dem.alt((lon - tile_lon, lat - tile_lat)))
        except _GEOM_EXC:
            return None
        if v != v or v == nodata:
            return None
        return v

    seam: list[tuple[float, float, float]] = []   # (x, y, dem_alt)
    seam_alt_by_idx: dict[int, float] = {}
    for i, (x, y) in enumerate(coords):
        try:
            if Point(x, y).distance(cut_boundary) >= 0.75:
                continue
        except _GEOM_EXC:
            continue
        v = _dem_at(x, y)
        if v is None:
            continue
        seam.append((float(x), float(y), v))
        seam_alt_by_idx[i] = v
    if not seam:
        return
    new_alts: list[float] = []
    for i, (x, y) in enumerate(coords):
        if i in seam_alt_by_idx:
            new_alts.append(round(seam_alt_by_idx[i], 2))
            continue
        lo = float("-inf")
        hi = float("inf")
        for sx, sy, sv in seam:
            d = math.hypot(x - sx, y - sy)
            hi = min(hi, sv + grade_cap * d)
            lo = max(lo, sv - grade_cap * d)
        if lo > hi:                      # conflicting seam anchors
            new_alts.append(round(0.5 * (lo + hi), 2))
            continue
        new_alts.append(round(min(max(design[i], lo), hi), 2))
    fs.node_altitudes = new_alts
    fs.altitude = None
    fs.altitude_high = None
    fs.altitude_low = None


def _build_piece_shape(
        orig: BuiltShape,
        piece: Polygon,
        slope_sampler: Callable[[float, float], float] | None,
) -> BuiltShape | None:
    """Construct a BuiltShape for one cut piece, copying tags from
    ``orig`` and resampling altitudes for the new polygon vertices.

    * Flat shape (``altitude`` set, ``altitude_high`` None):
      keeps ``altitude`` unchanged; ``node_altitudes`` cleared.
    * Sloped 4-corner rect: convert to ``node_altitudes`` by
      projecting each new vertex onto the original H→L axis.  The
      polygon's vertex count typically differs from 4 post-cut so
      the legacy [H, L, L, H] convention no longer applies.
    * Per-vertex ``node_altitudes``: resample via nearest-neighbour
      against the original ring.
    """
    new_s = copy.copy(orig)
    new_s.polygon = piece

    # Flat with single altitude — corner count irrelevant.
    if orig.altitude is not None and orig.altitude_high is None:
        new_s.altitude = orig.altitude
        new_s.altitude_high = None
        new_s.altitude_low = None
        new_s.node_altitudes = None
        return new_s

    # Sloped 4-corner rect → per-vertex node_altitudes.
    if slope_sampler is not None:
        try:
            coords = list(piece.exterior.coords)
        except _GEOM_EXC:
            return None
        alts = [round(float(slope_sampler(x, y)), 2)
                for (x, y) in coords]
        new_s.node_altitudes = alts
        new_s.altitude = None
        new_s.altitude_high = None
        new_s.altitude_low = None
        return new_s

    # Per-vertex node_altitudes → resample via NN.
    if orig.node_altitudes:
        try:
            old_coords = list(orig.polygon.exterior.coords)
        except _GEOM_EXC:
            return None
        if old_coords and old_coords[0] == old_coords[-1]:
            old_open = old_coords[:-1]
        else:
            old_open = old_coords
        from .elevation import _resample_node_altitudes_nn
        new_alts = _resample_node_altitudes_nn(
            piece, old_open, orig.node_altitudes)
        if new_alts is not None:
            new_s.node_altitudes = new_alts
        return new_s

    # No elevation data — keep as-is with the new polygon.
    return new_s
