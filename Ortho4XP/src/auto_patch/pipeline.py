"""End-to-end orchestration of the airport pavement builder.

Sequences the phase-1 (geometry + role) and phase-2 (elevation)
passes by calling out into the focused ``O4_Pavement_*`` modules:

* OSM tile + airport extraction.
* apt.dat selection (best-of-OSM vs custom-pack heuristics).
* Phase-1 construction → ``O4_Pavement_Rects``,
  ``O4_Pavement_Centerlines``, ``O4_Pavement_Stubs``,
  ``O4_Pavement_Junctions``, ``O4_Pavement_Terminals``.
* Phase-2 elevation → ``O4_Pavement_Elevation``.
* Feature emit → ``O4_Pavement_Boundary``,
  ``O4_Pavement_Groundside``, ``O4_Pavement_Bridges``.
* Output via ``PavementLayout.to_osm`` (in ``O4_Pavement_Layout``).

Public API:

    build_airport_pavement(icao, xplane_root, *, compute_elevations=True,
                            taxiway_data=None, tile_dem=None,
                            airport_boundary=None)

Backward-compat shim ``O4_Airport_Pavement_Builder`` re-exports
``build_airport_pavement`` (and a few helpers used by other
modules) so existing call sites keep working.
"""
from __future__ import annotations

import math
import os
import re
import time
from typing import List, Optional, Sequence, Tuple

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import (
    linemerge, nearest_points, transform as shp_transform, unary_union)

# Narrow exception tuple for shapely / numeric-geometry failure
# modes + file I/O.  Programming errors propagate so they surface
# immediately rather than being silently masked at runtime.
_GEOM_EXC = (OSError, ValueError,
             GEOSException, TopologicalError)

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from . import apt_dat_reader as APR
# Rod-carry probe (docs/specs/single-space-string-audit-spec.md §2).
# ``rod_ckpt`` returns immediately unless O4_ROD_CARRY_AUDIT=1, so the
# post-solve checkpoint calls below are inert in a default build.
from .rod_carry_audit import checkpoint as _rod_carry_checkpoint
# Post-solve mutation seam audit (round 17 §R17-1(a)); returns immediately
# unless O4_MUTATION_SEAM_AUDIT=1, so every seam below is inert by default.
from .mutation_seam_audit import checkpoint as _mutation_seam_checkpoint
# Post-solve AIRSIDE GEOMETRY seam audit (S1e phase 1); returns immediately
# unless O4_GEOM_SEAM_AUDIT=1, so every seam below is inert by default.
from .geom_guard import seam_checkpoint as _geom_seam_checkpoint
# §T4 road-piece ledger: which pass took a road-corridor / tunnel piece.
from .road_piece_ledger import checkpoint as _road_piece_checkpoint


def _rod_ckpt(layout, name: str) -> None:
    """ONE named post-solve pipeline seam, for the probes that need it.

    Write-only instruments hang off the same seam list — they are the
    seams that EXIST, and none of them invents one:

    * the rod-carry checkpoint (gate ``O4_ROD_CARRY_AUDIT``),
    * the string mover ledger's ``final_proj_N.entry`` sub-boundary
      (round-2 spec §2; gate ``O4_STRING_MOVER_LEDGER``, which is the only
      thing that puts a ledger on the layout),
    * the post-solve MUTATION SEAM audit (round 17 §R17-1(a); gate
      ``O4_MUTATION_SEAM_AUDIT``) — which pass moved the EMITTED
      pavement, the attribution the projection's mutation-set count
      cannot give because its window spans every stage at once, and
    * the ROAD-PIECE LEDGER (§T4; gate ``O4_ROAD_PIECE_LEDGER``, default
      ON) — which pass DELETED a road-corridor or tunnel piece, the
      question the LEMD 40-rects/78-fills loss had no instrument for.

    All gates off ⇒ one function call, one ``getattr`` and one env read
    per seam.
    """
    _rod_carry_checkpoint(layout, name)
    _road_piece_checkpoint(layout, name)
    # THE COVERAGE PROBE RUNS AT THE POST-SOLVE SEAMS TOO.  It was
    # sprinkled only at the pre-solve/feature seams, so a point lost
    # AFTER the solve — which is where every tunnel clip and re-clip
    # lives — had no trace at all.  Same instrument, same env gate
    # (``O4_COVERAGE_PROBE``), no-op without it.
    from .geom_guard import probe_points_only as _covp_seam
    _covp_seam(layout, name)
    if getattr(layout, "_string_mover_ledger", None) is not None:
        from .elevation_per_surface.route_profile.solve import (
            mover_stage_boundary as _mover_stage_boundary)
        _mover_stage_boundary(layout, name)
    _mutation_seam_checkpoint(layout, name)
    _geom_seam_checkpoint(layout, name)


# ──────────────────────────────────────────────────────────────────
# Constants (re-exported from O4_Pavement_Config + O4_Pavement_Layout)
# ──────────────────────────────────────────────────────────────────
from .config import (
    CLASS_BOUNDARY_MIN_PIECE_M2,
    MIN_SEGMENT_LEN_M,
    LOAD_DSF_PAVEMENT,
    DSF_BUILDINGS,
    DSF_CLUSTER_OSM_ABSORB_FRAC,
    TERM_BRIDGE_GROUPING,
    TERMINAL_SIMPLIFY_TOL_M,
    PAD_MIN_AREA_M2,
    RUNWAY_APRON_AREA_RATIO,
    ABSORB_RUNWAY_IN_APRON,
    OSM_SMALL_ROAD_HIGHWAY_TYPES,
    SERVICE_ROAD_WIDTH_M,
    MIN_SERVICE_STRIP_LEN_M,
    SERVICE_ROAD_PAVEMENT_NEAR_M,
    ENABLE_SERVICE_ROADS,
    SERVICE_SOURCE_DEDUPE,
    SERVICE_SOURCE_DEDUPE_FRAC,
    AIRPORT_ROAD_FEED,
    SERVICE_ROAD_CARVE,
)
from .layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    ROLE_RUNWAY,
    ROLE_STUB,
    ROLE_BUILDING,
    _airport_anchor,
    _projection,
)


# ──────────────────────────────────────────────────────────────────
# Data model (re-exported from O4_Pavement_Layout)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Input loaders
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# OSM cache + apt.dat selection helpers
# ──────────────────────────────────────────────────────────────────
from .osm_load import (
    _load_airport_road_network,
    _load_osm_airports,
    _load_osm_big_roads,
    _load_osm_small_roads,
    _pick_best_apt_dat_against_osm,
)
from .pavement.service_roads import build_service_road_network
from . import finalize


# ──────────────────────────────────────────────────────────────────
# Meter-space projection (re-exported from O4_Pavement_Layout)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Runway rects, crossings, shoulders (re-exported from
# O4_Pavement_Runways)
# ──────────────────────────────────────────────────────────────────
from .pavement.runways import (
    _detect_runway_shoulders,
    _detect_runway_border_strip_shoulders,
    _detect_runway_shoulder_extent,
    _runway_rect_m,
    _widen_runway_rect,
)


# ──────────────────────────────────────────────────────────────────
# Pavement union helpers (re-exported from pavement.union_helpers)
# ──────────────────────────────────────────────────────────────────
from .pavement.union_helpers import (
    _merge_near_touching,
)


# ──────────────────────────────────────────────────────────────────
# Stub residue / runway-bridge helpers
# (re-exported from pavement.stubs)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# (2026-07-31) The tunable runway / parallel-taxiway centerline
# pull-backs (session 56: _RWY_JUNCTION_BUFFER_M, _RWY_DIAG_BUFFER_M,
# _PARALLEL_BUFFER_M) were retired with the rect trim chain they tuned.
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Airside node-unification (refactor Phases 6+7)
# ──────────────────────────────────────────────────────────────────

# Post-solve-emitted FEATURE roles (terrain transitions / clearance), which
# conform TO the frozen airside without the airside ever receiving a vertex.
# (boundary_dem_bridge + surface_clearance are overlay-exempt in conformance.)
_POSTSOLVE_FEATURE_OWNER_ROLES = frozenset({
    "boundary", "groundside_pavement", "tunnel_ramp", "retaining_wall",
})


def _unify_airside_geometry(layout, icao: str, dem=None,
                            tile_lat: int | None = None,
                            tile_lon: int | None = None) -> None:
    """Settle the airside pavement node-set into a CONFORMING partition:
    re-connect discovered lane dead-ends, weld near-coincident airside
    vertices to one canonical coordinate, insert every shared-boundary
    vertex (full conformance), then the final near-corner / neighbour-corner
    snaps.  Adjacent airside shapes end up sharing identical vertices along
    every common edge — no T-junction slivers, no coincident-but-separate
    vertex pairs.

    Refactor Phases 6+7: this runs PRE-solve so the solver sees the FINAL
    node-set and writes ONE altitude per shared bucket — eliminating the
    post-solve coincident-vertex CLIFFS that arose when weld/conformance
    snapped vertices coincident AFTER the solver graded them to independent
    elevations (the HECA #291↔#371 class).  Pure geometry — no altitude
    dependency — so it is safe before any altitude is assigned.
    """
    from .canonical_points import weld_layout_vertices
    from .conformance import enforce_conformance
    from .junction_repair import (
        _snap_near_corner_vertices_to_plane_corners,
        _share_neighbour_corners_into_junctions)
    from .layout import (
        ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
        ROLE_CROSS_CONNECTOR, ROLE_JUNCTION, ROLE_RUNWAY,
        ROLE_RUNWAY_CROSSING, ROLE_APRON, ROLE_BUILDING,
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)

    # (2026-07-31) The discovered-(TX)-lane dead-end reconnect ran here.
    # Retired with the rest of the medial-axis discovery branch: it needs a
    # 4-corner rect SHAPE carrying a ``TX`` ref, and ``TX`` refs are minted
    # only on discovered CENTERLINES — the rect builder that turned those
    # into shapes went with d4f61d6, and the global slice emits every face
    # with ``ref=""``.  It could not fire.  See ``pavement/
    # discovered_taxiways.py``'s header for the retirement record.

    # A junction EDGE that grazes past a rect/runway CORNER with no
    # junction vertex nearby never shares a node with the rect (the
    # vertex-based push/snap machinery can't see it) — route the edge
    # THROUGH the corner.  Runs here, at final pre-solve geometry, because
    # the graze often only exists after the junction-repair / overlap-clip
    # passes (the Phase-1 call in elevation.py catches the early cases).
    from .pavement.vertices import (
        _insert_junction_corners_into_grazing_apron_edges,
        _insert_rect_corners_into_grazing_junction_edges)
    _insert_rect_corners_into_grazing_junction_edges(layout)
    _insert_junction_corners_into_grazing_apron_edges(layout)

    # Weld near-coincident airside vertices to one fresh canonical
    # coordinate so a rect corner and the junction vertex beside it become a
    # single point (the conformance below then has only genuine T-junctions
    # left).  ROLE_BUILDING included so a terminal's boundary vertices weld
    # 1:1 with the surrounding apron's (one solver node, no tilt/wall).
    # SERVICE roles joined 2026-07-29: the small-roads layer's pieces are
    # law-carrying airside shapes (SOFT_VISIBILITY_ROLES) but were never
    # welded, so adjacent service_road/service_junction rings kept
    # near-coincident duplicate vertices (up to tol) that the solver's
    # canonical registry later merged onto ONE node — ring coordinate ≠
    # node position (CYXY: a 0.40 m drift minted a quantization bowtie,
    # an emit-time buffer(0) vertex outside the law graph, and
    # solver↔validator budget-key mismatches).
    _weld_roles = {ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
                   ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
                   ROLE_RUNWAY, ROLE_RUNWAY_CROSSING, ROLE_APRON,
                   ROLE_BUILDING, ROLE_SERVICE_ROAD,
                   ROLE_SERVICE_JUNCTION}
    n_welded = weld_layout_vertices(layout, _weld_roles)
    if n_welded:
        UI.vprint(1,
            f"  [pav-builder] {icao}: pre-solve welded shared vertices in "
            f"{n_welded} airside shape(s).")

    # Full conformance: insert every neighbour vertex that lies on a shape's
    # edge so the partition is conforming.  At this point the only non-airside
    # shapes present are groundside (separated post-solve); the boundary
    # ribbon / DEM bridge / clearance are emitted post-solve and conformed to
    # the (now frozen) airside by the one-sided post-solve feature conformance.
    n_shapes, n_verts = enforce_conformance(layout)
    if n_verts:
        UI.vprint(1,
            f"  [pav-builder] {icao}: pre-solve conformance — inserted "
            f"{n_verts} shared-boundary vertex(es) into {n_shapes} shape(s).")

    # PRE-SOLVE EDGE DENSIFY (user in-sim finding 2026-07-09): a
    # construction-born over-long pavement edge (CYXY: a 1,279 m
    # junction chord) gives the SOLVER nothing to hold the edge
    # profile with — the mesh then interpolates the pavement between
    # far-apart nodes and it sags against the graded strips beside it.
    # Inserted here the new vertices are solver nodes: the edge is
    # LAW-solved, not lerped.  60 m spacing matches the emit
    # decimators' MAX_CHORD, so the nodes survive to the mesh.
    from .conformance import densify_long_edges
    from .clearance import _AIRSIDE_PAVEMENT_ROLES as _DENSIFY_ROLES
    n_dense = densify_long_edges(layout, _DENSIFY_ROLES, 60.0)
    if n_dense:
        UI.vprint(1,
            f"  [pav-builder] {icao}: pre-solve edge densify — "
            f"inserted {n_dense} vertex(es) on over-60 m pavement "
            f"edges.")

    # FINAL near-corner snap: a non-rect vertex left on a sloped rect's edge
    # near a corner is snapped onto the corner so the two SHARE it; companion
    # share-neighbour-corners handles the 0.10–0.5 m junction case.
    _snap_near_corner_vertices_to_plane_corners(layout, icao=icao)
    _share_neighbour_corners_into_junctions(layout, icao=icao)

    # AIRSIDE SEAM RE-PIN (owner ruling 2026-07-25, config
    # ``AIRSIDE_SEAM_DEM_REPIN``).  LAST in this pass, so it sees the
    # settled node-set and every vertex it mints is a solver node: densify
    # each airside cut-back edge onto the shared 10 m stations, pin each
    # seam vertex to the DEM at its own position, and register the buckets
    # the solver hard-holds.  ROLE_RUNWAY JOINED the sweep on 2026-07-26
    # (owner ruling, ``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``) — see
    # ``tile_cut._seam_repin_roles``.  No-op without a DEM, and on
    # every single-tile airport (no cut line).
    if dem is not None:
        from .tile_cut import repin_airside_seam_cutbacks
        n_new, n_pin = repin_airside_seam_cutbacks(
            layout, dem, tile_lat, tile_lon)
        if n_new or n_pin:
            UI.vprint(1,
                f"  [pav-builder] {icao}: airside seam re-pin — "
                f"{n_pin} cut-back node(s) at DEM ({n_new} newly "
                f"densified onto 10 m stations).")


# Defect 4a (KBNA 2026-07-15) ring-needle collapse thresholds.  A needle is
# a ring apex whose interior angle is below ``_NEEDLE_ANGLE_DEG`` while BOTH
# bounding edges are longer than ``_NEEDLE_MIN_EDGE_M`` — a construction
# artifact (the slice/weld/conformance chain folding a long thin tongue to a
# near-collinear spike, e.g. KBNA junction 289's 2.8° apex between 48.6 m and
# 57.6 m edges), NOT real geometry.  The min-edge guard protects a genuine
# sharp corner built from short segments (a real taper toe carries a short
# edge); only wide-edged spikes with no plausible physical width are dropped.
#
# WIDENED 2026-07-16 (KBNA Donelson round 8): 5°/10 m left surviving spikes at
# 7.5°/7.6°/9.7° (edges 48/21 m) on junctions 289/290 and 4.4-14.9° apexes on
# the adjacent-ground bands that inherit those rings.  A 10°/8 m band is still
# firmly a degenerate spike: a 10° apex between two 8 m edges encloses only
# 0.5·8·8·sin10° ≈ 5.6 m² and is < 1.4 m wide at its base — no plausible
# real-pavement width, so no coverage is lost by collapsing it (the true
# pavement is recovered upstream by the shared-vertex weld heal in
# pavement.vertices, not by keeping these spikes).  Bands inherit the pavement
# rings, so collapsing the pavement spike dissolves the band spike with it.
_NEEDLE_ANGLE_DEG = 10.0
_NEEDLE_MIN_EDGE_M = 8.0
# A needle collapse deletes the apex, cutting the chord between its
# neighbours — the area removed is the apex triangle.  A genuine
# construction spike encloses almost nothing (KBNA 289/290's 7.5-9.7° apexes
# between 48/21 m edges remove ≈ 85 m²), but the SAME angle/edge test also
# matches the sharp TIP of a real (if thin) pavement wedge, where deleting the
# apex would carve out live pavement (KBNA Donelson: a 159 m² tip at the
# owner's spot).  Cap the CUMULATIVE per-ring removal at this floor — the same
# floor _record_airside_drop treats as a real drop — so artifact spikes still
# dissolve while no ring loses real pavement to the collapse (keeps the
# build-time airside-drop counter at zero).
_NEEDLE_MAX_DROP_AREA_M2 = 100.0
# THE SOURCE-COVERAGE DISCRIMINATOR (Fable ruling 2026-08-02, gate
# ``O4_NEEDLE_SOURCE_GUARD``).  Area cannot separate the two classes the
# collapse must tell apart: the KBNA 289/290 artifact apexes remove ≈85 m²
# and HECA's H1 REAL pavement wedge is 90.8 m² — no threshold fits between
# them (field-report round, §D1).  What DOES separate them is what the
# removed triangle covers: an artifact spike encloses ground the SOURCE
# pavement never paved, while a real wedge tip is source pavement.  So the
# discriminator is the test — a drop is admissible only when the apex
# triangle does not cover source pavement — and the cumulative area cap
# above stays on as a secondary bound.
# Fraction of the apex triangle that must be ON source pavement for the
# apex to count as real pavement (a hair over "touches" so a triangle that
# merely grazes a source edge still collapses).
_NEEDLE_SOURCE_COVER_FRAC = 0.10


def _collapse_ring_needles(coords_open, na_open, source_union=None):
    """Drop degenerate needle apexes from an OPEN ring (no closing repeat).

    Iterates to a fixed point (nested spikes / a newly-exposed apex after a
    drop): at each vertex whose two bounding edges both exceed
    ``_NEEDLE_MIN_EDGE_M`` and whose interior angle is below
    ``_NEEDLE_ANGLE_DEG``, delete the apex (and its aligned altitude) —
    UNLESS doing so would push the cumulative area removed from this ring
    past ``_NEEDLE_MAX_DROP_AREA_M2`` (a real-pavement wedge tip, not a
    zero-area artifact spike; kept so no coverage is lost).

    ``source_union`` (the source pavement footprint, passed only under
    ``O4_NEEDLE_SOURCE_GUARD``) adds THE discriminator: an apex whose
    triangle COVERS source pavement is real pavement and is never dropped,
    whatever its area.  Off ⇒ area is the only test, exactly as before.

    Returns ``(coords_open, na_open, n_dropped)``; ``na_open`` may be
    ``None`` (geometry-only).  ``_collapse_ring_needles.last_kept_on_source``
    counts the apexes the guard alone saved (build-time reporting)."""
    import math as _math
    angle_deg = _NEEDLE_ANGLE_DEG
    min_edge = _NEEDLE_MIN_EDGE_M
    max_drop = _NEEDLE_MAX_DROP_AREA_M2
    coords = list(coords_open)
    na = list(na_open) if na_open is not None else None
    dropped = 0
    kept_on_source = 0
    area_removed = 0.0
    changed = True
    while changed and len(coords) > 3:
        changed = False
        n = len(coords)
        for i in range(n):
            ax, ay = coords[(i - 1) % n]
            bx, by = coords[i]
            cx, cy = coords[(i + 1) % n]
            v1x, v1y = ax - bx, ay - by
            v2x, v2y = cx - bx, cy - by
            n1 = _math.hypot(v1x, v1y)
            n2 = _math.hypot(v2x, v2y)
            if n1 <= min_edge or n2 <= min_edge:
                continue
            cosv = max(-1.0, min(1.0, (v1x * v2x + v1y * v2y) / (n1 * n2)))
            ang = _math.degrees(_math.acos(cosv))
            if ang < angle_deg:
                # Apex-triangle area (the pavement the chord cut removes).
                apex_area = 0.5 * abs(v1x * v2y - v1y * v2x)
                if (area_removed + apex_area
                        > max_drop):
                    continue          # real-pavement tip — keep it
                if (source_union is not None and apex_area > 0.0
                        and _apex_covers_source(
                            (ax, ay), (bx, by), (cx, cy), apex_area,
                            source_union)):
                    kept_on_source += 1
                    continue          # REAL pavement — the discriminator
                del coords[i]
                if na is not None:
                    del na[i]
                dropped += 1
                area_removed += apex_area
                changed = True
                break
    _collapse_ring_needles.last_kept_on_source = kept_on_source
    return coords, na, dropped


_collapse_ring_needles.last_kept_on_source = 0


def _apex_covers_source(a, b, c, apex_area, source_union) -> bool:
    """Does the apex triangle ``a-b-c`` cover SOURCE pavement?

    True ⇒ dropping the apex would carve real pavement out of the emitted
    surface (the H1 class); False ⇒ the spike encloses ground the source
    never paved (the KBNA construction-artifact class).  A geometry failure
    answers True — the conservative side, where the apex is KEPT and no
    coverage can be lost to a broken measurement."""
    from shapely.geometry import Polygon as _Poly
    try:
        tri = _Poly((a, b, c))
        if not tri.is_valid:
            tri = tri.buffer(0)
        if tri.is_empty:
            return False
        return (tri.intersection(source_union).area
                >= _NEEDLE_SOURCE_COVER_FRAC * apex_area)
    except Exception:
        return True


def _dedup_coincident_ring_vertices(layout, icao: str, tol_m: float = 0.05,
                                    collapse_needles: bool = False):
    """Drop consecutive coincident exterior-ring vertices (zero-length
    edges) from every shape, keeping ``node_altitudes`` aligned.

    ``collapse_needles`` (defect 4a; passed True at the PRE-SOLVE call so
    the collapse is baked before the solver/validator read the ring): also
    drop degenerate ring-needle apexes (``_collapse_ring_needles``) from
    AIRSIDE shapes.  Off (post-solve idempotent copy) it is a pure
    zero-length dedup, byte-identical to before.

    The spine polygonize + weld/conformance can leave a vertex repeated at
    the same coordinate (SPJC: 44 zero-length edges).  X-Plane / Triangle4XP
    triangulate a zero-length edge into a degenerate (near-zero-area) sliver
    that renders as a STRETCHED / distorted texture.  Removing the duplicate
    is geometry-neutral (the kept vertex sits at the same spot, same
    altitude) so it cannot create a T-junction or move a seam — safe to run
    just before the final conformance check / emit.  Returns the count of
    shapes cleaned.

    ``tol_m`` STAYS AT 5 cm and is NOT the canonical weld radius
    (0.5 m) — deliberately, per the cycle-5 node-identity spec
    (``docs/specs/cycle5-node-identity-spec.md``).  This pass DELETES a
    vertex, and at the weld radius it would delete legitimate short
    edges.  The node-identity law is enforced where the twin would be
    MINTED instead — ``conformance._NODE_IDENTITY_TOL_M`` (a
    planarize insert reuses an existing ring vertex within the weld
    radius) and ``canonical_points.snap_polygon_to_lattice`` (a
    pre-solve cut is born on the settled lattice).  Cleaning up after a
    twin was minted is not the same act as never minting one."""
    import math as _math
    from shapely.geometry import Polygon as _Poly
    from .clearance import _AIRSIDE_PAVEMENT_ROLES as _AIRSIDE_ROLES
    n_fixed = 0
    n_needle_shapes = 0
    n_needle_total = 0
    n_needle_kept_src = 0
    # THE SOURCE-COVERAGE DISCRIMINATOR (gate ``O4_NEEDLE_SOURCE_GUARD``):
    # the source pavement footprint the collapse must never carve into —
    # the SAME union ``verification.check_source_coverage`` measures against
    # (source ∪ runway), so the guard and the coverage invariant cannot
    # disagree about what "source pavement" means.
    # DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-
    # spec.md`` §1; evidence: the classification round ``1e5a781``, which
    # added the discriminator after the area heuristic was measured unable
    # to separate a genuine needle from source pavement).
    needle_source = None
    if (collapse_needles
            and os.environ.get("O4_NEEDLE_SOURCE_GUARD", "1") == "1"):
        needle_source = getattr(layout, "source_pavement_union", None)
        if needle_source is not None and not needle_source.is_empty:
            _rwy_u = getattr(layout, "runway_union", None)
            if _rwy_u is not None and not _rwy_u.is_empty:
                try:
                    needle_source = needle_source.union(_rwy_u)
                except Exception:
                    pass
        else:
            needle_source = None
    for s in layout.shapes:
        p = getattr(s, "polygon", None)
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        _area_before = p.area
        coords = list(p.exterior.coords)            # includes closing repeat
        if len(coords) < 4:
            continue
        na = s.node_altitudes
        # node_altitudes aligns 1:1 with exterior.coords (closing repeat) in
        # the canonical form; only dedup-with-altitude when that holds, else
        # dedup geometry only (flat / high-low shapes carry no per-vertex
        # list to misalign).
        aligned = na is not None and len(na) == len(coords)
        na_list = list(na) if aligned else None
        new_coords = [coords[0]]
        new_na = [na_list[0]] if aligned else None
        for k in range(1, len(coords)):
            px, py = new_coords[-1]
            x, y = coords[k]
            if _math.hypot(x - px, y - py) < tol_m:
                continue                            # skip duplicate
            new_coords.append((x, y))
            if aligned:
                new_na.append(na_list[k])
        # OUT-AND-BACK SPIKES (user 2026-07-04, CYUL apron #233): a ring
        # that visits a far vertex and RETURNS to the same point
        # (…A → S → A…) carries a zero-area needle — the "node out in
        # the grass" 251 m from its shape.  Remove the spike tip and the
        # returning duplicate (repeat until stable: nested spikes).
        changed_spike = True
        while changed_spike and len(new_coords) >= 4:
            changed_spike = False
            m = len(new_coords) - 1                 # closing repeat at [-1]
            for k in range(1, m):
                ax, ay = new_coords[k - 1]
                bx, by = new_coords[(k + 1) % m]
                if _math.hypot(ax - bx, ay - by) < tol_m:
                    del new_coords[k:k + 2]
                    if aligned:
                        del new_na[k:k + 2]
                    changed_spike = True
                    break
        # RING-NEEDLE COLLAPSE (defect 4a): drop degenerate wide-edged spike
        # apexes from airside shapes, pre-solve.  Runs on the OPEN ring so the
        # apex's aligned altitude is dropped with it.
        n_needle = 0
        if (collapse_needles
                and getattr(s, "role", None) in _AIRSIDE_ROLES
                and len(new_coords) >= 4):
            has_close = new_coords[0] == new_coords[-1]
            open_coords = new_coords[:-1] if has_close else list(new_coords)
            open_na = None
            if aligned:
                open_na = new_na[:-1] if has_close else list(new_na)
            open_coords, open_na, n_needle = _collapse_ring_needles(
                open_coords, open_na, source_union=needle_source)
            n_needle_kept_src += _collapse_ring_needles.last_kept_on_source
            if n_needle:
                new_coords = list(open_coords) + [open_coords[0]]
                if aligned:
                    new_na = list(open_na) + [open_na[0]]
        if len(new_coords) == len(coords) and n_needle == 0:
            continue                                # nothing removed
        # keep the ring closed
        if new_coords[0] != new_coords[-1]:
            new_coords.append(new_coords[0])
            if aligned:
                new_na.append(new_na[0])
        if len(new_coords) < 4:
            continue                                # would degenerate
        try:
            np_ = _Poly(new_coords, [list(r.coords) for r in p.interiors])
            if not np_.is_valid or np_.is_empty:
                continue
        except Exception:
            continue
        # A needle collapse should only ever shave a degenerate spike (a
        # 10° apex between 8 m edges encloses < 6 m²); if a single shape
        # loses more than the airside-drop floor to it, that is real
        # pavement, not an artifact — record it as a loud build-time verify
        # drop (must read ZERO on a healthy build).
        if n_needle and (_area_before - np_.area) > 100.0:
            from .pavement.vertices import _record_airside_drop
            _record_airside_drop(
                layout, s, p, _area_before - np_.area, "needle-collapse")
        s.polygon = np_
        if aligned:
            s.node_altitudes = new_na
        n_fixed += 1
        if n_needle:
            n_needle_shapes += 1
            n_needle_total += n_needle
    if n_fixed:
        UI.vprint(1,
            f"  [pav-builder] {icao}: removed zero-length edge(s) "
            f"(duplicate ring vertices) from {n_fixed} shape(s).")
    if n_needle_total:
        UI.vprint(1,
            f"  [pav-builder] {icao}: collapsed {n_needle_total} degenerate "
            f"ring needle(s) (<{_NEEDLE_ANGLE_DEG:.0f} deg apex, edges "
            f">{_NEEDLE_MIN_EDGE_M:.0f} m) from {n_needle_shapes} airside "
            f"shape(s).")
    if n_needle_kept_src:
        UI.vprint(1,
            f"  [pav-builder] {icao}: source-coverage guard KEPT "
            f"{n_needle_kept_src} needle apex(es) covering real source "
            f"pavement (they would have been collapsed on area alone).")
    return n_fixed


def _admit_dsf_building_footprint(
        outer_ring_lonlat,
        hole_rings_lonlat,
        to_meters_transform,
        airport_bounding_box_meters,
        boundary_gate_meters,
        building_polygons_meters) -> bool:
    """Admit one DSF building ring into the DSF building pool.

    The single downstream path shared by every DSF building source
    (``.fac`` facades / ``.agp`` hangars via ``read_dsf_buildings``, and
    OBJ8 structure footprints via ``read_dsf_object_buildings``):
    Polygon, ``buffer(0)`` repair, to-metres transform, bounding-box
    reject, boundary-CENTROID gate (keep the whole footprint rather than
    clipping a building that grazes the boundary), then append to
    ``building_polygons_meters``.  Returns True when the footprint was
    appended.
    """
    try:
        building_polygon_lonlat = Polygon(
            [(lon, lat) for (lon, lat) in outer_ring_lonlat],
            [[(lon, lat) for (lon, lat) in h]
             for h in hole_rings_lonlat if len(h) >= 3],
        )
        if not building_polygon_lonlat.is_valid:
            building_polygon_lonlat = building_polygon_lonlat.buffer(0)
        if (building_polygon_lonlat.is_empty
                or building_polygon_lonlat.geom_type != "Polygon"):
            return False
        building_polygon_meters = shp_transform(
            to_meters_transform, building_polygon_lonlat)
        if (building_polygon_meters.is_empty
                or building_polygon_meters.geom_type != "Polygon"):
            return False
        if airport_bounding_box_meters is not None:
            (bounds_min_x, bounds_min_y,
             bounds_max_x, bounds_max_y) = building_polygon_meters.bounds
            if (bounds_max_x < airport_bounding_box_meters[0]
                    or bounds_min_x > airport_bounding_box_meters[2]
                    or bounds_max_y < airport_bounding_box_meters[1]
                    or bounds_min_y > airport_bounding_box_meters[3]):
                return False
        if boundary_gate_meters is not None:
            try:
                if not boundary_gate_meters.contains(
                        building_polygon_meters.centroid):
                    return False
            except _GEOM_EXC:
                return False
        building_polygons_meters.append(building_polygon_meters)
        return True
    except _GEOM_EXC:
        return False


def _osm_building_evidence_predicate(nodes, ways, relations, to_m):
    """``ring_lonlat -> bool``: does an OSM building footprint intersect
    this DSF-object ring?  Evidence source (a) of R18-2.

    Built once per build (the STRtree over the OSM building polygons is
    the whole point — the gate runs over every object ring), and returns
    a predicate that is always ``False`` when the airport has no mapped
    buildings at all, which is the honest answer: no OSM evidence.
    """
    from .terminals import _extract_osm_building_evidence
    try:
        buildings = _extract_osm_building_evidence(
            nodes, ways, relations, to_m)
    except _GEOM_EXC:
        buildings = []
    if not buildings:
        return (lambda _ring_lonlat: False), 0
    from shapely.strtree import STRtree
    tree = STRtree(buildings)

    def _has_evidence(ring_lonlat) -> bool:
        try:
            ring_m = Polygon([to_m(lon, lat) for (lon, lat) in ring_lonlat])
            if not ring_m.is_valid:
                ring_m = ring_m.buffer(0)
            if ring_m.is_empty:
                return False
            for index in tree.query(ring_m):
                if buildings[index].intersects(ring_m):
                    return True
        except _GEOM_EXC:
            return False
        return False

    return _has_evidence, len(buildings)


def _collect_dsf_object_building_footprints(
        dsf_path, xplane_root, admit_footprint,
        osm_building_evidence=None, refused_out=None) -> int:
    """Phase 1 of the DSF object integration: OBJ8 structure footprints
    join the DSF building pool beside the ``.fac`` facades, through the
    IDENTICAL downstream path (``admit_footprint`` =
    ``_admit_dsf_building_footprint`` with the caller's gates bound).
    Role ``"object"`` then flows through ``_cluster_dsf_building_facades``
    and ``_combine_building_sources`` exactly like a facade — additive,
    no overlap predicate (ruling R4; spec section 2.3).

    THE BUILDING-EVIDENCE GATE (R18-2, owner ruling 2026-08-11b) closes
    HERE, before anything enters the pool and therefore before facade
    clustering.  A ring is admitted when EITHER
    ``dsf_reader.OBJECT_BUILDING_ROLE`` (the reader's vertical-structure
    verdict, carried on the role) OR ``osm_building_evidence(ring)`` (an
    intersecting OSM building footprint) holds.  Neither ⇒ the ring is
    an apron slab / barrier / vehicle hull with no building under it and
    seeds no pad.  ``osm_building_evidence=None`` means the caller has
    no OSM in hand, which is NOT evidence of absence — the gate then
    rests on the vertical test alone.

    Gated on ``DSF_OBJECT_BUILDINGS`` here (function-local import so
    tests can monkeypatch the flag); the caller has already gated on
    ``DSF_BUILDINGS`` (the object source shares the building path).
    ``refused_out``, when a list, collects one
    ``(ring_lonlat, centroid_lonlat, area_m2)`` row per refusal for the
    build log.  Returns the number of footprints admitted.
    """
    from .config import DSF_OBJECT_BUILDING_EVIDENCE, DSF_OBJECT_BUILDINGS
    if not DSF_OBJECT_BUILDINGS:
        return 0
    from . import dsf_reader as _DSFR
    admitted = 0
    for outer_ring, hole_rings, role in _DSFR.read_dsf_object_buildings(
            dsf_path, xplane_root=xplane_root):
        if len(outer_ring) < 3:
            continue
        if DSF_OBJECT_BUILDING_EVIDENCE and role != _DSFR.OBJECT_BUILDING_ROLE:
            if not (osm_building_evidence is not None
                    and osm_building_evidence(outer_ring)):
                if refused_out is not None:
                    refused_out.append(outer_ring)
                continue
        if admit_footprint(outer_ring, hole_rings):
            admitted += 1
    return admitted


# ──────────────────────────────────────────────────────────────────
# STRING-SUBSTRATE CAPTURE (Fable RULING 4, 2026-07-31 —
# docs/specs/s1-taut-chord-constructor-spec.md, second rulings block)
# ──────────────────────────────────────────────────────────────────

def _capture_string_substrate(layout, icao: str, apt_centerlines,
                              nodes, ways, to_m) -> None:
    """Capture the taut-chord constructor's substrate INPUT, both tiers.

    Called from ``build_airport_pavement`` AT the S2 snapshot (the
    ``layout.apt_taxi_centerlines = list(osm_centerlines)`` assignment
    under the "Preserve the full input centerline set" comment) — that
    call site is the whole point and must not move: recognition
    reassigns the attribute a few lines later.

    Captures INPUT only.  It never builds the substrate: that happens
    once, at the hook, in the pure ``build_string_substrate`` every
    test and instrument calls.

    Gate ``O4_TAUT_STRING_CONSTRUCTION`` (default OFF), read directly
    to match ``route_profile/solve.py``'s hook rather than minting a
    config constant the hook does not use.  Gate OFF ⇒ returns before
    ANY import: no capture, no import, no new attribute.  That early
    return is load-bearing — ``taut_string`` must stay unimported in a
    gate-off build, and the fingerprint import below is inside it.

    ``apt_centerlines`` is the SAME list object assigned to
    ``layout.apt_taxi_centerlines``; ``nodes``/``ways`` are the single
    ``_load_osm_airports`` result from the same build (also published
    as ``layout._osm_airport_features``) — no OSM file is re-read.

    Writes the field in the shape the hook's ``substrate_from_carriage``
    reads: ``{"apt": [(coords, is_service)], "osm": [(way_id, coords)],
    "fingerprint": str}``.
    """
    # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
    # The taut-string machinery is the owner's PAUSED feature: the strings
    # verdict is pending (memory ``string-purpose-statement``: strings are a
    # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
    # surface authority), so this switch is deliberately NOT deleted with
    # the law gates.  It selects whether a PARKED feature runs at all, not
    # which law the build obeys.  Retire or adopt it when the owner rules.
    if os.environ.get("O4_TAUT_STRING_CONSTRUCTION", "0") != "1":
        return
    from .layout import (AptSubstratePiece, set_string_substrate_src,
                         substrate_polyline_length_m)
    from .osm_load import capture_osm_taxi_linework
    # ★ THE ONE FINGERPRINT (Ruling 4).  Imported from the hook's own
    # module so capture and hook compute the SAME function over the
    # SAME content — two implementations of "the same hash" would make
    # the hook's assertion vacuous the first time they drifted.
    from .elevation_per_surface.route_profile.taut_string import (
        substrate_fingerprint)

    sub_apt: list = []
    for cl in apt_centerlines or []:
        ln = getattr(cl, "line", None)
        if ln is None or ln.is_empty:
            continue
        # Materialising the coordinates into an immutable tuple IS the
        # deep copy Ruling 4 requires — and it is stronger than
        # ``copy.deepcopy`` of the shapely object: recognition's later
        # reassignment cannot reach a tuple of floats.
        cs = tuple((float(x), float(y)) for x, y in ln.coords)
        if len(cs) < 2:
            continue
        # Service pieces are CARRIED, not filtered (Ruling 5's
        # substrate corollary: they COUNT for membership / coverage and
        # are excluded only from the STRUNG domain).
        sub_apt.append(AptSubstratePiece(
            coords=cs, is_service=bool(getattr(cl, "is_service", False))))

    sub_osm = capture_osm_taxi_linework(nodes or {}, ways or [], to_m)
    src = {
        "apt": sub_apt,
        "osm": sub_osm,
        "fingerprint": substrate_fingerprint(sub_apt, sub_osm),
    }
    set_string_substrate_src(layout, src)
    _apt_m = sum(substrate_polyline_length_m(p.coords) for p in sub_apt)
    _osm_m = sum(substrate_polyline_length_m(w.coords) for w in sub_osm)
    UI.vprint(1, f"  [string-substrate] {icao}: captured apt "
                 f"{len(sub_apt)} piece(s) {_apt_m:.1f} m / osm "
                 f"{len(sub_osm)} way(s) {_osm_m:.1f} m / fp "
                 f"{src['fingerprint'][:12]}")
    if not sub_osm:
        # LAWFUL degradation (Ruling 4) — logged, never silent.  The
        # known cause is the cwd / worktree trap: a build run outside
        # Ortho4XP/ (or in a worktree without OSM_data/) loads no OSM
        # cache, so the OSM tier is legitimately empty and the
        # substrate is apt.dat-only.
        UI.vprint(1, f"  [string-substrate] {icao}: OSM tier EMPTY — no "
                     f"aeroway=taxiway linework in the airport cache "
                     f"(apt.dat-only substrate; lawful degradation).")


# ──────────────────────────────────────────────────────────────────
# Top-level builder
# ──────────────────────────────────────────────────────────────────

#: Kill switch for the weld-before-projection reorder (spec
#: ``docs/specs/weld-before-projection-spec.md``).  Default ON in the lane;
#: ``O4_WELD_BEFORE_PROJECTION=0`` restores the pre-spec ordering exactly.
_WELD_BEFORE_PROJECTION = (
    os.environ.get("O4_WELD_BEFORE_PROJECTION", "1") != "0")


def _road_contact_scope(layout, pav_union, to_m):
    """THE REGION auto_patch STILL OWNS OF THE ROAD FAMILY (spec §3.3).

    Two parts, and they are the two ownerships RULINGS 31b leaves with
    auto_patch after the core takes general roads:

    (a) THE TRANSITION — within ``SERVICE_ROAD_PAVEMENT_NEAR_M`` (25 m)
        of aircraft pavement.  The same constant the mint already used
        to decide which OSM small roads are airport roads at all, and
        the same one ``road_transition`` profiles inside, so the region
        the patch paves and the region it profiles are ONE region.
    (b) BRIDGE / TUNNEL GROUND — within the same distance of a feed way
        that ASSERTS ``bridge`` or ``tunnel``.  This is the exact
        complement of the core's own exclusion (``O4_Vector_Map``'s
        ``tags_for_exclusion``, census #106): the core levels every
        approach and refuses the tagged span; auto_patch keeps the
        tagged span and lets the approach go.  Stated as one seam in
        two files rather than two thresholds that can drift.

    ``None`` when there is no pavement and no tagged way — the caller
    then mints as before (unit fixtures with no airfield).

    DERIVED ONCE PER BUILD and memoised on the layout: BOTH minters of
    road-family pavement read this ONE region (the OSM/1206 mint at the
    service-network build, and ``groundside.carve_narrow_service_strips``
    on the truck-route feed — RULINGS 31d finding A).  A second
    derivation is a second ownership boundary, which is the defect class
    the census-wrapper precedent names.
    """
    cached = getattr(layout, "_road_contact_scope_cache", None)
    if cached is not None:
        return cached[0]
    from .config import SERVICE_ROAD_PAVEMENT_NEAR_M as _NEAR
    parts = []
    if pav_union is not None and not pav_union.is_empty:
        try:
            parts.append(pav_union.buffer(float(_NEAR)))
        except _GEOM_EXC:                                  # pragma: no cover
            pass
    net = getattr(layout, "airport_road_network", None)
    ways = getattr(net, "ways", None) or ()
    if ways:
        from O4_OSM_Utils import way_asserts_any_tag
        nodes = getattr(net, "nodes", None) or {}
        spans = []
        for (_wid, _nds, _tags) in ways:
            if not way_asserts_any_tag(_tags, ("bridge", "tunnel")):
                continue
            pts = [to_m(nodes[n][1], nodes[n][0]) for n in _nds
                   if n in nodes]
            if len(pts) >= 2:
                try:
                    spans.append(LineString(pts))
                except _GEOM_EXC:                          # pragma: no cover
                    continue
        if spans:
            try:
                parts.append(unary_union(spans).buffer(float(_NEAR)))
            except _GEOM_EXC:                              # pragma: no cover
                pass
    scope = None
    if parts:
        try:
            scope = parts[0] if len(parts) == 1 else unary_union(parts)
            if scope.is_empty:
                scope = None
        except _GEOM_EXC:                                  # pragma: no cover
            scope = None
    try:
        layout._road_contact_scope_cache = (scope,)
    except Exception:                                      # pragma: no cover
        pass
    return scope


def gap_spine_stand_down_solve(*, layout, icao, solve, rebuild):
    """THE GAP-SPINE BRIDGE STAND-DOWN — owner ruling 2026-08-27 "2",
    ``docs/specs/gap-spine-bridge-stand-down-spec.md`` Amendment 1.

    ``solve()`` runs phases [5]+[6] on ``layout`` (and may raise
    :class:`BandInversionError`); ``rebuild()`` re-runs the WHOLE airport
    build, which this function first disables bridge synthesis for.
    Returns the layout that ships.

    THE TEST IS THE RETRY, not a predicted spread.  The spec's original
    shape — refuse a bridge candidate whose two ends' governing anchor
    values already spread more than ``cap x route`` — was measured
    UNIMPLEMENTABLE at candidate time (lane/bridgedown probes, tree
    594daec3).  The band's end values are phase-2 EMITTED runway
    elevations (``_decrowned_anchor_seeds`` <- ``G.runway_anchor`` <-
    ``_sample_runway_segment_elev``), and at the synthesis site — phase 4,
    before the global slice — the runway shapes carry ``altitude=None``
    and no ``node_altitudes``, so all 21 of HEAZ's runway-join contacts
    sample ``None``.  The only phase-1-legible alternative, the CIFP
    envelope, is a second notion of the end's value AND measures
    non-firing (the refusal's own CIFP half reports the forced spread
    FITS the budget on every HEAZ pair).

    The same probes corrected the attribution's mechanism sentence.  HEAZ
    mints THIRTEEN bridges (5-244 m), not one, and the binding inverted
    chain lies 195-292 m from the nearest bridge segment: the mechanism
    is the bridges' AGGREGATE effect on the global slice, not one
    over-budget route.  Per-candidate refusal cannot express that; a
    per-AIRPORT interventional re-run can, and it is what the owner's
    "restores the pre-c6a85e9c surface exactly" describes.

    ONE SHOT, never a masking loop — and the one-shot property is
    STRUCTURAL rather than a counter: the retry runs with synthesis
    disabled, so ITS layout carries no bridges, so this function is a
    pass-through inside it.  A build that refuses for any other reason
    (no bridges minted) never enters the adjudication and raises exactly
    as before, byte-for-byte.

    A retry that ALSO refuses EXONERATES the bridges: the original
    refusal is re-raised unchanged.  A refusal is never swallowed to
    shield a surface, the same way a dying mechanism is never kept alive
    to shield one (no-degradation-shield).

    SCOPE is the smallest sound one.  The bridge is minted in phase 4 and
    every later phase mutates the layout in place, so there is no
    checkpoint to resume from at the synthesis step — the sound unit is
    the whole airport build.  It is scoped to THIS airport by
    construction (``driver._build_write_verify_one`` builds one airport
    per worker process) and the flag is restored in a ``finally``
    regardless of outcome.
    """
    from .elevation_per_surface.building_feasibility import (
        BandInversionError, FINAL_BAND_INVERSION_TOL_M as _tol)
    bridges = list(getattr(layout, "gap_spine_bridges", None) or [])
    if not bridges:
        return solve()
    try:
        return solve()
    except BandInversionError as band_exc:
        rows = list(getattr(layout, "_final_band_inversions", None) or [])
        over = sum(1 for r in rows
                   if float(r.get("deficit_m", 0.0)) > _tol)
        band_n = int(getattr(layout, "_final_band_node_count", 0) or 0)
        refusal = (str(band_exc).splitlines() or [""])[0].strip()
        UI.vprint(1, f"  [gap-spine] {icao}: the post-solve band law "
                     f"REFUSED a build carrying {len(bridges)} synthesized "
                     f"gap-spine bridge(s) — retrying the airport ONCE with "
                     f"them stood down.  A one-shot INTERVENTIONAL test run "
                     f"in production, never a masking loop: the retry mints "
                     f"no bridge, so it cannot retry again.")
        from . import config as _cfg_gsb
        was_enabled = getattr(_cfg_gsb, "GAP_SPINE_BRIDGE_ENABLED", True)
        try:
            _cfg_gsb.GAP_SPINE_BRIDGE_ENABLED = False
            retry_layout = rebuild()
        except BandInversionError:
            UI.vprint(1, f"  [gap-spine] {icao}: bridges EXONERATED — the "
                         f"retry WITHOUT the {len(bridges)} bridge(s) "
                         f"refuses too, so they are not the mechanism.  The "
                         f"ORIGINAL refusal stands: {refusal}")
            raise band_exc
        finally:
            _cfg_gsb.GAP_SPINE_BRIDGE_ENABLED = was_enabled
        # CLEAN without them => the bridges ARE the mechanism.  The
        # nodeless region they would have filled stays unfilled: round-3
        # spine stations and the lattice are the anchor mechanism there,
        # not synthesized routes.
        try:
            retry_layout.gap_spine_stand_down = [{
                "icao": icao,
                "bridge_count": len(bridges),
                "bridges": bridges,
                "refusal": refusal,
                "inverted_node_count": over,
                "band_node_count": band_n,
                "materiality_m": float(_tol),
            }]
        except AttributeError:                             # pragma: no cover
            pass
        UI.vprint(1, f"  [gap-spine] {icao}: {len(bridges)} bridge(s) "
                     f"STAND DOWN — the retry without them is CLEAN, so the "
                     f"bridges are the mechanism of the refusal ({over} of "
                     f"{band_n} band-covered node(s) inverted by more than "
                     f"{_tol:g} m).  The nodeless region they would have "
                     f"filled stays unfilled; this patch is the bridge-free "
                     f"surface.  Original refusal: {refusal}")
        return retry_layout


def build_airport_pavement(icao: str, xplane_root: str,
                            *,
                            compute_elevations: bool = True,
                            taxiway_data=None,
                            tile_dem=None,
                            airport_boundary=None,
                            current_tile_lat=None,
                            current_tile_lon=None,
                            ) -> PavementLayout:
    """Build the complete role-classified layout for ``icao``.

    The layout is ready to compare against a target OSM via
    ``tools/compare_target.py``.

    When ``compute_elevations`` is True (default), a Phase-2
    elevation pass runs at the end:
      * Single runway shapes are replaced with per-100m segmented
        runway rects produced by the legacy CIFP+DEM generator.
      * Taxi rects get ``altitude_high``/``altitude_low`` tags
        from DEM sampling at axis endpoints, anchored to the
        adjacent runway segment when within 30 m.
      * Terminal pads get ``altitude`` from the DEM at centroid.
      * Junctions, buildings, aprons are left un-elevated (X-Plane
        triangulator interpolates them from neighbouring shared
        vertices).

    Optional integration parameters (all default to ``None`` so
    standalone callers — ``tools/build_target_osm.py``, the test
    harness — work unchanged):

      * ``taxiway_data``: per-airport list from
        ``osm_aeroway.extract_taxiway_info``.  Threaded through to
        Pipeline's centerline-union helper so reclassification /
        downstream consumers can see OSM taxiway centerlines that
        didn't survive into rects.
      * ``tile_dem``: pre-loaded ``O4_DEM_Utils.DEM`` for the
        containing tile (typically Ortho4XP's smoothed DEM after
        ``smooth_raster_over_airports``).  When supplied, the
        Phase-2 elevation solver and boundary-shape emit consume
        this DEM directly instead of calling
        ``_load_airport_dem`` per-airport — avoids redundant DEM
        loads in the tile-pipeline driver and keeps auto_patch's
        elevation field aligned with Ortho4XP's smoothed terrain.
      * ``airport_boundary``: optional pre-computed airport
        boundary (``dico_airports[icao]['boundary']`` from
        Ortho4XP's ``update_airport_boundaries``).  Currently
        reserved — the parameter is plumbed through but the
        boundary-shape emit still derives its outline from
        apt.dat row-130 until the source-of-truth question is
        decided.
    """
    from .progress import for_build as _progress_for_build
    _progress = _progress_for_build(icao, compute_elevations=compute_elevations)

    # FLAT-SITE mode classifies inside DEM PREP, which several passes can
    # enter first (``elevation._compute_elevations`` reaches
    # ``_load_airport_dem`` before the per-surface solver does) and whose
    # result ``elevation._DEM_CACHE`` memoises for the whole process.  So
    # the install it reads CIFP and apt.dat under is recorded HERE, before
    # anything can compose a DEM — threading it through one call site only
    # let the FIRST caller compose an unsubstituted surface that every
    # later caller then got back from the cache (measured 2026-08-09).
    try:
        from . import flat_site_mode as _flat_site_mode
        _flat_site_mode.set_build_xplane_root(xplane_root)
    except Exception:                                # pragma: no cover
        pass

    _progress.step()  # [1] Loading apt.dat & runway geometry

    # O4_FORCE_APT_DAT overrides source selection (e.g. compare Global Airports
    # vs a custom pack) — diagnostic only.
    apt_path = (os.environ.get("O4_FORCE_APT_DAT")
                or _pick_best_apt_dat_against_osm(xplane_root, icao))
    if apt_path is None:
        raise RuntimeError(f"No apt.dat found for {icao}")
    apt = APR.load_airport(apt_path, icao)
    if apt is None:
        raise RuntimeError(f"Could not load airport block for {icao}")

    # Complexity-based build-time prior (progress display only): the
    # apt.dat counts predict total time from past recorded builds, so
    # the window can show a ballpark "About m:ss remaining" from the
    # start and refine it phase by phase.  Full builds only — a
    # geometry-only build is a different (much shorter) animal.
    _build_started_at = time.time()
    _build_features = None
    if compute_elevations:
        try:
            from . import build_time_model as _time_model
            _build_features = _time_model.complexity_features(apt)
            _progress.set_time_model(
                _time_model.predict_total_seconds(icao, _build_features),
                _time_model.predict_phase_seconds(icao, _build_features))
        except Exception:
            pass

    anchor = _airport_anchor(apt)
    to_m = _projection(anchor)

    layout = PavementLayout(icao=icao, anchor=anchor,
                             apt_dat_path=apt_path)
    # The apt.dat row-100 runway list, carried on the layout so the
    # VERIFICATION readers can reach the same authoritative geometry the
    # emitters used.  ``driver`` calls ``verify_and_log`` with
    # ``source_runways=None`` (it has no ``apt`` in scope at that point),
    # which left the adjacent-ground caps mirror measuring station-to-axis
    # distance off a min-rotated-rect midline instead of the real
    # centreline — and the emitted pavement is LONGER than the apt.dat
    # axis (SPJC 16R/34L: 3,617 m vs 3,497 m), so stations past the axis
    # endpoints got a different ``d_axis`` on each side and the A4/OLS
    # caps drifted out of lockstep.  One list, one axis, both readers.
    layout.apt_runways = list(getattr(apt, "runways", None) or ())

    # Project the apt.dat row-130 airport boundary (in lat/lon) into
    # meter space so downstream emission has it ready when the
    # boundary shape is built.
    if apt.boundary is not None and not apt.boundary.is_empty:
        try:
            from shapely.ops import transform as _shp_transform
            # Smart source cleanup: drop digitization NEEDLES from the
            # hand-traced row-130 ring (sharp near-zero-area zigzags) so
            # every boundary consumer — ribbon, DEM bridge, interior
            # clip — sees a clean ring.  A needle's apex folds the
            # ribbon strip over itself → boundary∩boundary overlap
            # (HEAZ @ 30.10017,31.35442).
            from .boundary import _despike_airport_boundary
            layout.airport_boundary = _despike_airport_boundary(
                _shp_transform(
                    lambda lon, lat, z=None: to_m(lon, lat),
                    apt.boundary),
                icao=icao)
        except _GEOM_EXC:
            layout.airport_boundary = None

    # ── Runways ──────────────────────────────────────────────────
    runway_polys: List[Polygon] = []
    rwy_bearings: List[float] = []
    rwy_centerlines: List[LineString] = []
    for r in apt.runways:
        rect = _runway_rect_m(r, to_m)
        if rect.is_empty:
            continue
        runway_polys.append(rect)
        ref = f"{r.desig_a}/{r.desig_b}"
        layout.shapes.append(BuiltShape(
            polygon=rect, role=ROLE_RUNWAY, ref=ref))
        ax, ay = to_m(r.lon_a, r.lat_a)
        bx, by = to_m(r.lon_b, r.lat_b)
        if math.hypot(bx - ax, by - ay) > 1.0:
            rwy_centerlines.append(LineString([(ax, ay), (bx, by)]))
            rwy_bearings.append(
                math.degrees(math.atan2(bx - ax, by - ay)) % 180.0)
    layout.runway_union = unary_union(runway_polys) if runway_polys else None

    _progress.step()  # [2] Assembling pavement & runway shoulders

    # ── Pavement union in meter space ────────────────────────────
    pav_polys: List[Polygon] = []
    for pav in apt.pavements:
        if pav.polygon is None or pav.polygon.is_empty:
            continue
        pm = shp_transform(to_m, pav.polygon)
        if pm.is_empty:
            continue
        if pm.geom_type == "Polygon":
            pav_polys.append(pm)
            layout.apt_pavement_records.append(
                (pm, pav.name, pav.surface_code))
        else:
            for g in getattr(pm, "geoms", []):
                if g.geom_type == "Polygon":
                    pav_polys.append(g)
                    layout.apt_pavement_records.append(
                        (g, pav.name, pav.surface_code))
    # Snapshot the apt.dat-only polygon list before DSF additions.
    # Terminal-pad selection prefers the SMALLEST containing
    # polygon, and DSF often ships small overlay-style polygons
    # over apt.dat pavement; without this snapshot a small DSF
    # overlay covering part of the apron will win over the larger
    # apt.dat terminal pavement and the resulting terminal pad
    # loses most of its area (SPJC terminal1 regressed from
    # 105 K m² → 35 K m² before this fix).
    apt_only_pav_polys: List[Polygon] = list(pav_polys)
    # Stash the pre-DSF snapshot for the scoring classifier's provenance
    # layer (DSF-drawn area = area these polygons do not cover).
    layout.apt_only_pavement_polys = list(apt_only_pav_polys)

    # Capture every apt.dat row-110 pavement polygon vertex so the
    # source-attribution test recognises junction perimeter
    # vertices inherited from row-110 (junctions are built as
    # ``pav_union.difference(rects)`` — see junction_emit.py).
    _seen = set()
    _boundary_lines = []
    for _p in pav_polys:
        try:
            rings = [_p.exterior, *_p.interiors]
        except _GEOM_EXC:
            continue
        for _r in rings:
            _boundary_lines.append(_r)
            for _x, _y in _r.coords:
                _key = (round(_x, 2), round(_y, 2))
                if _key in _seen:
                    continue
                _seen.add(_key)
                layout.apt_pavement_vertices.append((float(_x), float(_y)))
    # Also store the boundary line union so mid-edge points count
    # as legitimate row-110 inheritances.
    if _boundary_lines:
        try:
            layout.apt_pavement_boundary = unary_union(_boundary_lines)
        except _GEOM_EXC:
            layout.apt_pavement_boundary = None

    # ── Runway shoulder absorption ─────────────────────────────────
    # Long thin row-110 polygons parallel to a runway and touching
    # or overlapping it are runway shoulders (or, when wider than
    # the apt.dat row-100 width and centered on the runway, the
    # runway's own envelope polygon — apt.dat sometimes labels
    # these as "taxiways", e.g. HECA's "New Taxiway 1").  Fold them
    # into the runway: widen the runway emit to the union of
    # perpendicular extents, mutate the runway's apt.dat record so
    # downstream CIFP segmenting picks up the new width, and remove
    # the absorbed polygons from the pavement set so they don't
    # re-emit as junction polygons wrapping the runway.
    #
    # Asymmetric shoulders (one side only — common at gravel
    # crosswind runways like CYXY's 02/20) are handled by shifting
    # the runway centerline toward the shoulder midpoint while
    # widening to the union extent.  The CIFP threshold elevations
    # (anchored at the original runway thresholds) still apply
    # because the threshold lat/lon stays paired with the same
    # apt.dat designation; the perpendicular shift moves the
    # centerline by the shoulder offset (typically < 20 m, well
    # within DEM noise tolerance).
    absorbed_pav_indices: set = set()
    # Runways the whole-polygon pass widened — the later extent-based
    # shoulder pass skips these so the two don't compound.
    _shoulder_widened_refs: set = set()
    for ridx, r in enumerate(apt.runways):
        new_left, new_right, absorbed = _detect_runway_shoulders(
            r, to_m, pav_polys)
        new_width = new_right - new_left
        # Only widen when the new extent meaningfully exceeds the
        # apt.dat row-100 width (≥ 0.5 m on top of current).
        if new_width <= r.width_m + 0.5:
            continue
        offset = 0.5 * (new_left + new_right)
        # Shift centerline by ``offset`` perpendicular.  The
        # perpendicular vector in meter space is (nx, ny) =
        # (-uy, ux), where (ux, uy) is the runway's
        # along-axis unit vector.
        ax_m, ay_m = to_m(r.lon_a, r.lat_a)
        bx_m, by_m = to_m(r.lon_b, r.lat_b)
        udx = bx_m - ax_m
        udy = by_m - ay_m
        L_axis = math.hypot(udx, udy)
        if L_axis < 1.0:
            continue
        ux_m, uy_m = udx / L_axis, udy / L_axis
        nx_m, ny_m = -uy_m, ux_m
        # Apply offset back through the inverse of ``to_m``.  Our
        # to_m projection (see ``_projection``) is anchored at
        # ``layout.anchor`` = (lat0, lon0) and uses cos(lat0).
        lat0, lon0 = layout.anchor
        cos0 = math.cos(math.radians(lat0))
        d_lat_per_m = 1.0 / R_EARTH
        d_lon_per_m = 1.0 / (R_EARTH * cos0) if cos0 > 1e-9 else 0.0
        d_lat = math.degrees(ny_m * offset * d_lat_per_m)
        d_lon = math.degrees(nx_m * offset * d_lon_per_m)
        old_w = r.width_m
        old_lat_a, old_lon_a = r.lat_a, r.lon_a
        if abs(offset) > 0.05:
            r.lat_a = r.lat_a + d_lat
            r.lon_a = r.lon_a + d_lon
            r.lat_b = r.lat_b + d_lat
            r.lon_b = r.lon_b + d_lon
        r.width_m = new_width
        new_rect = _runway_rect_m(r, to_m)
        if new_rect.is_empty:
            r.lat_a, r.lon_a = old_lat_a, old_lon_a
            r.width_m = old_w
            continue
        runway_polys[ridx] = new_rect
        # Preserve the PUBLISHED width before this widened value travels on:
        # rules keyed on "the runway width" (ICAO Annex 14 §3.5.3's RESA
        # factor of two) must not be handed runway+shoulders.  Readers use
        # ``Runway.declared_width_m``; only set on the success path, so a
        # rolled-back widening leaves the runway untouched.
        if r.published_width_m is None:
            r.published_width_m = old_w
        ref = f"{r.desig_a}/{r.desig_b}"
        _shoulder_widened_refs.add(ref)
        for s in layout.shapes:
            if s.role == ROLE_RUNWAY and s.ref == ref:
                s.polygon = new_rect
                break
        absorbed_pav_indices.update(absorbed)
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: widened runway "
                f"{r.desig_a}/{r.desig_b}: {old_w:.1f}m → "
                f"{r.width_m:.1f}m"
                + (f" (centerline shifted {offset:+.1f}m)"
                if abs(offset) > 0.5 else "")
                + f" — absorbed {len(absorbed)} shoulder polygon(s).")
        except _GEOM_EXC:
            pass

    if absorbed_pav_indices:
        # Filter both pav_polys and the apt-only snapshot.  Use
        # WKB-identity to filter apt_only_pav_polys (its indices
        # don't necessarily match pav_polys' if either was modified;
        # the snapshot was taken just above so they're identical at
        # this point, but using WKB is robust to future changes).
        absorbed_wkbs = {pav_polys[i].wkb for i in absorbed_pav_indices
                         if 0 <= i < len(pav_polys)}
        pav_polys = [p for i, p in enumerate(pav_polys)
                     if i not in absorbed_pav_indices]
        apt_only_pav_polys = [p for p in apt_only_pav_polys
                              if p.wkb not in absorbed_wkbs]
        layout.runway_union = (unary_union(runway_polys)
                                if runway_polys else None)


    # Add draped pavement polygons from every available DSF for
    # this airport.  Some scenery packs (e.g. CYXY Whitehorse) ship
    # pavement geometry as DSF draped polygons referencing
    # ``lib/airport/pavement/*.pol`` definitions, with little or no
    # apt.dat row-110 coverage; for those airports the DSF is the
    # primary pavement source and we need to admit it.  Other packs
    # (e.g. SPJC Custom Scenery) ship apt.dat row-110 pavement AND
    # add layered visual overlays on top via DSF — emitting those
    # overlays as pavement duplicates the apt.dat coverage and pulls
    # non-pavement decoration into the layout.
    #
    # Three-tier filtering:
    #   1. ``O4_DSF_Reader._is_pavement_def`` admits only X-Plane
    #      stock pavement library paths (``lib/airport/pavement/...``
    #      and ``lib/airport/ground/pavement/...``).  Third-party
    #      libraries are dropped at this stage.
    #   2. Distance gate: the DSF tile is 1° × 1° (~110 km a side),
    #      and a single tile covers many airports' pavement.  Any
    #      DSF polygon whose bbox lies more than
    #      ``DSF_AIRPORT_RADIUS_M`` (5 km) from THIS airport's
    #      runway-bbox is somebody else's pavement — drop it.
    #      Caught the SPJC regression where 9 junctions ended up
    #      ~20 km away at SPLP because the SPJC custom scenery's
    #      DSF tile contains both airports' pavement.
    #   3. Overlay check: each surviving DSF polygon is compared
    #      against the apt.dat pavement union built so far.  If the
    #      polygon mostly overlaps existing pavement (≥ 80 %
    #      inside), treat it as an overlay and drop it entirely —
    #      preserves the apt.dat geometry.  Only DSF polygons that
    #      contribute substantially NEW coverage are appended.
    DSF_OVERLAY_FRAC = 0.80
    DSF_AIRPORT_RADIUS_M = 5_000.0
    # Boundary gate: the apt.dat row-130 boundary is authoritative for
    # what belongs to this airport — we must not pull in any pavement
    # outside it.  Foreign DSF/OSM pavement is CLIPPED to the boundary
    # (only the buffer below, a small tile-/projection-alignment slop,
    # is tolerated past the drawn line).  The bbox distance gate
    # (DSF_AIRPORT_RADIUS_M, 5 km) is far too coarse to separate
    # closely-spaced airports: HEAZ (Almaza) and HECA (Cairo Intl) sit
    # ~1 km apart in tile +30+031, so HEAZ's 5 km bbox swallowed HECA's
    # entire DSF apron/terminal pavement.  Both airports then emitted
    # overlapping polygons at conflicting elevations into the same tile
    # DSF — corrupting the mesh and crashing X-Plane on load.
    DSF_AIRPORT_BOUNDARY_BUFFER_M = 50.0
    apt_pav_union: Optional[Polygon] = None
    if pav_polys:
        try:
            apt_pav_union = unary_union(pav_polys)
        except _GEOM_EXC:
            apt_pav_union = None

    # Buffered row-130 boundary in meter space, used to gate DSF and
    # OSM pavement to this airport's own footprint.  None when the
    # airport has no usable boundary → falls back to the bbox-only
    # distance gate below (unchanged behaviour for sparse-apt.dat
    # airports like CYXY).
    boundary_gate_m: Optional[Polygon] = None
    _ab = getattr(layout, "airport_boundary", None)
    if _ab is not None and not _ab.is_empty:
        try:
            _bg = _ab.buffer(DSF_AIRPORT_BOUNDARY_BUFFER_M)
            if not _bg.is_empty:
                boundary_gate_m = _bg
        except _GEOM_EXC:
            boundary_gate_m = None

    # Load OSM airport data.  ``nodes``/``ways``/``relations`` are
    # reused by terminal extraction further below.  (DSF pavement is
    # no longer gated against an OSM-aeroway footprint — see the
    # resource-type note in the DSF loop.)
    nodes, ways, relations = _load_osm_airports(
        xplane_root, icao, anchor[0], anchor[1])
    # Publish the aeroway layer on the layout (references, no copy) so
    # the classification pass can measure OSM airside backing without a
    # second read of the same cache.  Inert on its own.
    # Relations included (owner 2026-07-29): relation-mapped aerodromes
    # must reach the scorer's G-BOUNDARY assembly — the tuple grew a
    # third element; existing readers index [0]/[1] and are unaffected.
    layout._osm_airport_features = (nodes, ways, relations)
    # Compute the airport's bounding box from runway corners +
    # apt.dat pavement.  DSF polygons farther than
    # DSF_AIRPORT_RADIUS_M from this bbox are not this airport's.
    apt_bbox_m: Optional[Tuple[float, float, float, float]] = None
    bbox_polys = list(runway_polys) + list(pav_polys)
    if bbox_polys:
        try:
            uni = unary_union(bbox_polys)
            if not uni.is_empty:
                bx_min, by_min, bx_max, by_max = uni.bounds
                apt_bbox_m = (bx_min - DSF_AIRPORT_RADIUS_M,
                               by_min - DSF_AIRPORT_RADIUS_M,
                               bx_max + DSF_AIRPORT_RADIUS_M,
                               by_max + DSF_AIRPORT_RADIUS_M)
        except _GEOM_EXC:
            apt_bbox_m = None
    third_party_pav_ids: set = set()
    # Wide draped ``.lin`` border-strip placements collected in the DSF
    # sweep: ``(path_line_m, width_m, closed, def_path)``.  Filtered
    # after the sweep by the wraps-pavement test and unioned into the
    # pavement (user 2026-07-16, KBNA BordaTaxiway_* strips).
    dsf_border_line_candidates: List[tuple] = []
    # DSF terminal/hangar building footprints (meter space), collected
    # in the same DSF sweep as pavement and unioned with the OSM
    # building outlines at terminal-pad construction below.
    # DSF terminal / hangar / term_bridge building footprints (meter
    # space).  term_bridge_* slabs are admitted here too (gated by
    # TERM_BRIDGE_GROUPING) — they are just another component of a
    # complex building and union into the same per-building outline.
    dsf_building_polys: List[Polygon] = []
    n_dsf_buildings = 0
    n_dsf_object_buildings = 0
    # R18-2 building evidence, the OSM half.  Built ONCE for the whole
    # DSF sweep (the same nodes/ways/relations loaded above; no second
    # OSM read) and bound into every pack's object-ring gate.
    _osm_building_evidence, _n_osm_building_evidence = (
        _osm_building_evidence_predicate(nodes, ways, relations, to_m))
    _object_rings_refused: List = []
    # Rebuild-freshness record: which pack DSFs this build ACTUALLY reads and
    # which 1°×1° tiles it looks for them in (``layout.dsf_sources_read`` /
    # ``dsf_tiles_scanned``, stamped by ``to_osm`` and re-stat'ed by the
    # driver's freshness gate).  Initialised to EMPTY here, before the gate
    # that can skip the whole block: "looked, read nothing" must be a recorded
    # answer, not the ``None`` that means "never recorded" (which the gate
    # treats as unverifiable and rebuilds).
    layout.dsf_sources_read = []
    layout.dsf_tiles_scanned = []
    try:
        if not LOAD_DSF_PAVEMENT:
            raise StopIteration  # skip the DSF block entirely
        from . import dsf_reader as _DSFR
        seen_dsf: set = set()
        # Read DSF pavement ONLY from the pack that supplied the chosen
        # apt.dat (``apt_path``).  Pulling in every pack's DSF re-imports
        # a foreign copy of the airport: when a Custom Scenery pack
        # overrides CYXY but the stock Global Airports pack still carries
        # the original geometry, its DSF re-introduces shapes the user
        # deleted from the custom pack (the overlay gate can't suppress a
        # polygon once the custom apt.dat union no longer covers it).
        # X-Plane itself shadows Global with the custom pack, so mirror
        # that: same-pack DSF only.
        all_apt_dats = [apt_path]
        n_dsf_kept = 0
        n_dsf_dropped_overlay = 0
        n_dsf_dropped_far = 0
        n_dsf_dropped_vehicle = 0
        dsf_vehicle_area_m2 = 0.0
        from .config import (
            DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M
            as _OBJ_PAV_MIN_AIRCRAFT_WIDTH_M,
            DSF_OBJECT_PAVEMENT_OPENING_RATIO
            as _OBJ_PAV_OPENING_RATIO,
            DSF_OBJECT_PAVEMENT_SHOULDER_CONTACT_RATIO
            as _OBJ_PAV_SHOULDER_CONTACT)
        from . import object_footprints as _OBJ_FOOTPRINTS
        # Vehicle-classified object patches are DEFERRED, not dropped:
        # after the sweep (when every kept pavement polygon exists) the
        # shoulder pass readmits the ones in edge-contact with kept
        # pavement — a painted taxiway shoulder fails the width test
        # exactly like a road, and only contact separates them.
        deferred_vehicle_patches: List[Tuple[Polygon, str]] = []
        # Third-party .pol pavement (tier-2 reader admissions, e.g.
        # ZDP_Library concrete at KPHX): real base pavement for
        # coverage purposes, but excluded from apron-merge semantics
        # below (a full-airport base-texture layer under the runways
        # must not read as "an apron enclosing the runway" — it
        # apron-merged 65/67 KPHX runway segments).  Tracked in
        # ``third_party_pav_ids`` (initialised before this block).
        #
        # A cross-tile airport's scenery pack ships ONE DSF PER TILE
        # (KPHX straddles the −112 meridian; its south/east aprons
        # live only in the pack's +33-112.dsf).  Read every tile DSF
        # the airport's pavement bbox touches, not just the anchor
        # tile — the boundary/distance gates still clip each polygon
        # to this airport.
        _dsf_tiles: set = {(math.floor(anchor[0]),
                            math.floor(anchor[1]))}
        if apt_bbox_m is not None:
            _cos0 = math.cos(math.radians(anchor[0]))
            for _bx, _by in ((apt_bbox_m[0], apt_bbox_m[1]),
                             (apt_bbox_m[2], apt_bbox_m[3])):
                _blat = anchor[0] + math.degrees(_by / R_EARTH)
                _blon = anchor[1] + math.degrees(
                    _bx / (R_EARTH * _cos0)) if _cos0 > 1e-9 else anchor[1]
                _dsf_tiles.add((math.floor(_blat), math.floor(_blon)))
            # Fill the rectangle between the two corners (an airport
            # can only realistically span 2×2 tiles).
            _lats = sorted({t[0] for t in _dsf_tiles})
            _lons = sorted({t[1] for t in _dsf_tiles})
            _dsf_tiles = {(la, lo) for la in range(_lats[0], _lats[-1] + 1)
                          for lo in range(_lons[0], _lons[-1] + 1)}
        for ad in all_apt_dats:
          for _tlat, _tlon in sorted(_dsf_tiles):
            # Record the tile as VISITED (and, below, whatever DSF it
            # yielded) as the sweep goes, not up front: should the sweep
            # abort part-way the record still describes exactly what was
            # read, so the freshness gate re-derives the same answer instead
            # of finding an unvisited tile's DSF and rebuilding forever.
            layout.dsf_tiles_scanned.append((_tlat, _tlon))
            dsf = _DSFR.find_associated_dsf(ad, _tlat + 0.5, _tlon + 0.5)
            if dsf is None or dsf in seen_dsf:
                continue
            seen_dsf.add(dsf)
            layout.dsf_sources_read.append(dsf)
            # ``.pol`` draped pavement, then — behind its gate — the
            # draped-only OBJ8 ground-paint pages (HECA Tai Models:
            # base asphalt/concrete drawn as one whole-airport object
            # per texture).  Both readers return the same tuple shape,
            # so ONE loop applies the distance/boundary/overlay gates
            # and third-party marking to both sources (object def
            # paths are never stock ⇒ marked third-party below).
            _dsf_pavement_tuples = list(_DSFR.read_dsf_pavements(
                dsf, xplane_root=xplane_root))
            from .config import DSF_OBJECT_PAVEMENT as _DSF_OBJECT_PAVEMENT
            if _DSF_OBJECT_PAVEMENT:
                _dsf_pavement_tuples.extend(
                    _DSFR.read_dsf_object_pavements(
                        dsf, xplane_root=xplane_root))
            for outer, holes, def_path in _dsf_pavement_tuples:
                if len(outer) < 3:
                    continue
                try:
                    # Honour interior windings as holes — a perforated
                    # pavement ring (big outer + infield/building holes)
                    # must NOT be filled into a solid blob.
                    poly_ll = Polygon(
                        [(lon, lat) for (lon, lat) in outer],
                        [[(lon, lat) for (lon, lat) in h]
                         for h in holes if len(h) >= 3],
                    )
                    if not poly_ll.is_valid:
                        poly_ll = poly_ll.buffer(0)
                    if (poly_ll.is_empty
                            or poly_ll.geom_type != "Polygon"):
                        continue
                    pm = shp_transform(to_m, poly_ll)
                    if pm.is_empty or pm.geom_type != "Polygon":
                        continue
                    # Distance gate: skip polygons outside this
                    # airport's expanded bbox.
                    if apt_bbox_m is not None:
                        px_min, py_min, px_max, py_max = pm.bounds
                        if (px_max < apt_bbox_m[0]
                                or px_min > apt_bbox_m[2]
                                or py_max < apt_bbox_m[1]
                                or py_min > apt_bbox_m[3]):
                            n_dsf_dropped_far += 1
                            continue
                    # VEHICLE-PAVEMENT admission filter (owner direction
                    # 2026-07-18): an OBJECT-sourced ground-paint patch
                    # that is essentially nowhere as wide as aircraft
                    # pavement is a painted service road / drainage
                    # channel.  Morphological opening (erode by half the
                    # minimum aircraft width, dilate back) recovers the
                    # aircraft-capable cores; a low surviving-area ratio
                    # marks a vehicle corridor even when wide pockets
                    # (road intersections/plazas) survive plain erosion.
                    # Drop it HERE — before the union — so it never
                    # costs slice/weld/solve work and simply rides the
                    # DEM.  See config
                    # DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M and
                    # object_footprints.is_vehicle_pavement_patch.
                    if (_OBJ_PAV_MIN_AIRCRAFT_WIDTH_M > 0.0
                            and def_path.lower().endswith(".obj")
                            and _OBJ_FOOTPRINTS.is_vehicle_pavement_patch(
                                pm, _OBJ_PAV_MIN_AIRCRAFT_WIDTH_M,
                                _OBJ_PAV_OPENING_RATIO)):
                        deferred_vehicle_patches.append((pm, def_path))
                        continue
                    # Boundary gate: clip the DSF polygon to this
                    # airport's row-130 boundary so nothing outside it
                    # (a neighbouring airport's pavement) is pulled in.
                    # A polygon entirely outside clips to empty → drop;
                    # one straddling the boundary keeps only its inside
                    # part.
                    if boundary_gate_m is not None:
                        try:
                            clipped_b = pm.intersection(boundary_gate_m)
                            if (clipped_b.geom_type == "MultiPolygon"
                                    and not clipped_b.is_empty):
                                clipped_b = max(clipped_b.geoms,
                                                key=lambda g: g.area)
                            if (clipped_b.is_empty
                                    or clipped_b.geom_type != "Polygon"
                                    or clipped_b.area < 5.0):
                                n_dsf_dropped_far += 1
                                continue
                            pm = clipped_b
                        except _GEOM_EXC:
                            n_dsf_dropped_far += 1
                            continue
                    # NOTE: DSF pavement is filtered by RESOURCE TYPE
                    # at read time — ``dsf_reader._is_pavement_def``
                    # admits only ``lib/airport/pavement/`` and
                    # ``lib/airport/ground/pavement/`` defs (real
                    # asphalt/concrete surface) and rejects
                    # ``ground/terrain/`` (grass/lawn), lines,
                    # markings, facades, etc.  Per user 2026-05-21 we
                    # TRUST that classification: every reader-admitted
                    # pavement polygon inside the airport boundary is
                    # kept.  The earlier OSM-aeroway-gap clip and the
                    # oversized-vs-apt.dat RATIO gate were dropped —
                    # they discarded real aprons and runway/taxiway
                    # shoulders (which aren't OSM-tagged and can be
                    # large single polygons) along with decoration.
                    # NOTE: the apparent "whole-airport" pavement tiles
                    # are perforated rings (a big outer winding with
                    # holes); their HOLES are honoured by the reader,
                    # so ``pm`` is already the true net surface — no
                    # area cap is needed.
                    # Overlay check: drop the polygon if most of its
                    # area lies inside the existing apt.dat pavement
                    # union (it's a decorative overlay rather than
                    # new pavement).
                    # The dropped polygon's OUTSIDE remainder is real
                    # pavement though (user 2026-07-02, SPJC: a mostly-
                    # overlapping DSF apron's outside strip was dropped
                    # with it, leaving terrain holes beside the stands)
                    # — keep any remainder piece above the sliver floor;
                    # a true tinted overlay is ~100 % inside and still
                    # drops entirely.
                    if apt_pav_union is not None:
                        try:
                            inter_area = pm.intersection(
                                apt_pav_union).area
                            if (pm.area > 0
                                    and inter_area / pm.area
                                    >= DSF_OVERLAY_FRAC):
                                n_dsf_dropped_overlay += 1
                                rem = pm.difference(apt_pav_union)
                                for g in (rem.geoms
                                          if rem.geom_type
                                          == "MultiPolygon"
                                          else [rem]):
                                    if (g.geom_type == "Polygon"
                                            and not g.is_empty
                                            and g.area >= 50.0):
                                        pav_polys.append(g)
                                        n_dsf_kept += 1
                                continue
                        except _GEOM_EXC:
                            pass
                    pav_polys.append(pm)
                    if not _DSFR.is_stock_pavement_def(def_path):
                        third_party_pav_ids.add(id(pm))
                    n_dsf_kept += 1
                except _GEOM_EXC:
                    continue
            # Wide ``.lin`` border strips from the SAME DSF (bbox-gated
            # here; the wraps-pavement test runs after the sweep, once
            # the full pavement union exists to test against).
            if os.environ.get("O4_DSF_BORDER_LINE_PAVEMENT", "1") == "1":
                for _bl_pts, _bl_width, _bl_closed, _bl_def in \
                        _DSFR.read_dsf_pavement_border_lines(
                            dsf, xplane_root=xplane_root):
                    if len(_bl_pts) < 2:
                        continue
                    try:
                        _bl_line = LineString(
                            [to_m(lon, lat) for (lon, lat) in _bl_pts])
                    except _GEOM_EXC:
                        continue
                    if _bl_line.is_empty or _bl_line.length < 5.0:
                        continue
                    if apt_bbox_m is not None:
                        _bx_min, _by_min, _bx_max, _by_max = \
                            _bl_line.bounds
                        if (_bx_max < apt_bbox_m[0]
                                or _bx_min > apt_bbox_m[2]
                                or _by_max < apt_bbox_m[1]
                                or _by_min > apt_bbox_m[3]):
                            continue
                    dsf_border_line_candidates.append(
                        (_bl_line, _bl_width, _bl_closed, _bl_def))
            # Terminal / hangar building footprints from the SAME DSF.
            # Same projection + distance + boundary gates as pavement,
            # but a CENTROID-in-boundary gate (keep the whole footprint
            # rather than clipping a building that grazes the boundary).
            if DSF_BUILDINGS:
                _admit = (lambda outer_ring, hole_rings:
                          _admit_dsf_building_footprint(
                              outer_ring, hole_rings, to_m, apt_bbox_m,
                              boundary_gate_m, dsf_building_polys))
                for b_outer, b_holes, _b_role in \
                        _DSFR.read_dsf_buildings(
                            dsf, xplane_root=xplane_root):
                    if len(b_outer) < 3:
                        continue
                    # term_bridge slabs are only admitted when the
                    # grouping gate is on; otherwise they are ignored
                    # entirely (byte-identical to the pre-grouping read).
                    if _b_role == "bridge" and not TERM_BRIDGE_GROUPING:
                        continue
                    if _admit(b_outer, b_holes):
                        n_dsf_buildings += 1
                # OBJ8 structure footprints from the SAME DSF (Phase 1
                # of the DSF object integration) join the pool through
                # the IDENTICAL admission path.  Gated inside on
                # DSF_OBJECT_BUILDINGS (default off) and on the R18-2
                # building-evidence ruling (the OSM half of which is the
                # predicate built once, above this sweep).
                n_dsf_object_buildings += \
                    _collect_dsf_object_building_footprints(
                        dsf, xplane_root, _admit,
                        osm_building_evidence=_osm_building_evidence,
                        refused_out=_object_rings_refused)
        # ── SHOULDER readmission (owner in-sim report 2026-07-18) ──
        # Runs after the whole sweep so the contact test sees EVERY
        # kept pavement polygon (apt.dat row-110 + .pol + wide object
        # sheets).  A vehicle-classified strip in edge-contact with
        # kept pavement for at least half its long side is a painted
        # taxiway shoulder — absorb it (third-party marked like every
        # object patch); the rest stay dropped and ride the DEM.
        n_dsf_shoulder_readmitted = 0
        if deferred_vehicle_patches:
            try:
                from shapely.strtree import STRtree
                _shoulder_tree = STRtree(pav_polys)
                for _vp, _vp_def in deferred_vehicle_patches:
                    try:
                        _near = [pav_polys[i] for i in
                                 _shoulder_tree.query(_vp)]
                    except _GEOM_EXC:
                        _near = list(pav_polys)
                    _contact = _OBJ_FOOTPRINTS.abutting_contact_ratio(
                        _vp, _near)
                    if _contact >= _OBJ_PAV_SHOULDER_CONTACT:
                        pav_polys.append(_vp)
                        third_party_pav_ids.add(id(_vp))
                        n_dsf_kept += 1
                        n_dsf_shoulder_readmitted += 1
                    else:
                        n_dsf_dropped_vehicle += 1
                        dsf_vehicle_area_m2 += _vp.area
            except _GEOM_EXC:
                for _vp, _vp_def in deferred_vehicle_patches:
                    n_dsf_dropped_vehicle += 1
                    dsf_vehicle_area_m2 += _vp.area
        if (n_dsf_kept or n_dsf_dropped_overlay
                or n_dsf_dropped_far or n_dsf_dropped_vehicle):
            try:
                msg = (f"  [pav-builder] {icao}: DSF pavement: "
                       f"{n_dsf_kept} kept, "
                       f"{n_dsf_dropped_overlay} dropped as overlay, "
                       f"{n_dsf_dropped_far} dropped as off-airport")
                if n_dsf_dropped_vehicle:
                    msg += (f", {n_dsf_dropped_vehicle} object patch(es) "
                            f"({dsf_vehicle_area_m2 / 1e4:.1f} ha) dropped "
                            f"as vehicle/drainage paint (nowhere "
                            f">= {_OBJ_PAV_MIN_AIRCRAFT_WIDTH_M:.0f} m "
                            f"wide - rides the DEM)")
                if n_dsf_shoulder_readmitted:
                    msg += (f", {n_dsf_shoulder_readmitted} narrow "
                            f"patch(es) readmitted as abutting shoulders")
                UI.vprint(1, msg + ".")
            except _GEOM_EXC:
                pass
        if n_dsf_buildings:
            try:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: DSF buildings: "
                    f"{n_dsf_buildings} terminal/hangar facade(s) "
                    f"inside boundary.")
            except _GEOM_EXC:
                pass
        if n_dsf_object_buildings:
            try:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: DSF object buildings: "
                    f"{n_dsf_object_buildings} OBJ8 structure "
                    f"footprint(s) inside boundary.")
            except _GEOM_EXC:
                pass
        if _object_rings_refused:
            # Skip-and-report, never silent (R18-2): each refused ring
            # is a pad that WOULD have been laid on no building
            # evidence.  Worst-first by area so the phantom mega-pads
            # lead.
            try:
                _rows = []
                for _ring in _object_rings_refused:
                    try:
                        _rm = Polygon([to_m(lon, lat)
                                       for (lon, lat) in _ring])
                        if not _rm.is_valid:
                            _rm = _rm.buffer(0)
                        # Centroid in the ring's OWN lon/lat (there is no
                        # inverse projection in scope, and a lon/lat
                        # centroid is what a reviewer flies to).
                        _cll = Polygon(_ring).buffer(0).centroid
                        _rows.append((_rm.area, _cll.y, _cll.x))
                    except _GEOM_EXC:
                        continue
                _rows.sort(reverse=True)
                UI.vprint(1,
                    f"  [pav-builder] {icao}: building evidence gate "
                    f"REFUSED {len(_object_rings_refused)} OBJ8 "
                    "structure ring(s) — no tall structure over their "
                    "own footprint and no OSM building under them "
                    f"({_n_osm_building_evidence} OSM building "
                    "footprint(s) in the evidence set; "
                    "O4_DSF_OBJECT_BUILDING_EVIDENCE).")
                for _area, _lat, _lon in _rows[:10]:
                    UI.vprint(1,
                        f"      refused {_area:9.0f} m2 at "
                        f"{_lat:.7f},{_lon:.7f}")
            except _GEOM_EXC:
                pass
    except StopIteration:
        # DSF read intentionally disabled.
        try:
            UI.vprint(1,
                f"  [pav-builder] {icao}: DSF pavement read "
                f"disabled (LOAD_DSF_PAVEMENT=False).")
        except _GEOM_EXC:
            pass
    except _GEOM_EXC:
        pass

    # ── Pavement border-line strips (user 2026-07-16, KBNA hole) ─────
    # Construction style: a pack draws pavement as ``.pol`` polygons
    # PLUS wide draped ``.lin`` borders traced ALONG the polygon
    # outlines (KBNA ``BordaTaxiway_*``: 4-31 m wide, declared by the
    # resource's SCALE/TEX_WIDTH/S_OFFSET).  X-Plane centers the strip
    # on its path, so half of it is rendered pavement OUTSIDE the
    # ``.pol`` union — at KBNA that outer half is the missing 5-13 m
    # edge band plus the whole junction gap at 36.1156,-86.6682 (two
    # taxiways' 27 m concrete borders meet there).  A candidate strip
    # is included as pavement only when its path WRAPS the pavement:
    # at least half its sampled length runs within a few meters of the
    # pavement-union boundary.  Painted markings never qualify (the
    # reader's ≥ 2 m width floor), and a strip elsewhere on the field
    # (not along pavement) fails the wrap test.  Gate
    # O4_DSF_BORDER_LINE_PAVEMENT=0 restores the ``.pol``-only union.
    _BORDER_WRAP_SAMPLE_STEP_M = 5.0
    _BORDER_WRAP_EDGE_TOL_M = 3.0
    _BORDER_WRAP_MIN_FRACTION = 0.5
    if dsf_border_line_candidates:
        try:
            _border_reference = unary_union(
                [g for g in (list(pav_polys) + list(runway_polys))
                 if g is not None and not g.is_empty])
            _border_boundary = (_border_reference.boundary
                                if not _border_reference.is_empty
                                else None)
            _n_border_kept = 0
            _border_area = 0.0
            for (_bl_line, _bl_width, _bl_closed,
                 _bl_def) in dsf_border_line_candidates:
                if _border_boundary is None or _border_boundary.is_empty:
                    break
                try:
                    _n_samples = max(
                        2, int(_bl_line.length
                               / _BORDER_WRAP_SAMPLE_STEP_M))
                    _n_on_edge = sum(
                        1 for k in range(_n_samples)
                        if _border_boundary.distance(_bl_line.interpolate(
                            (k + 0.5) / _n_samples, normalized=True))
                        <= _BORDER_WRAP_EDGE_TOL_M)
                    if (_n_on_edge / _n_samples
                            < _BORDER_WRAP_MIN_FRACTION):
                        continue
                    _line_eff = _bl_line
                    if _bl_closed:
                        _coords = list(_bl_line.coords)
                        if _coords[0] != _coords[-1]:
                            _line_eff = LineString(
                                _coords + [_coords[0]])
                    _strip = _line_eff.buffer(_bl_width / 2.0,
                                              cap_style=2)
                    if boundary_gate_m is not None:
                        _strip = _strip.intersection(boundary_gate_m)
                except _GEOM_EXC:
                    continue
                for _piece in (_strip.geoms
                               if hasattr(_strip, "geoms")
                               else [_strip]):
                    if (_piece.geom_type == "Polygon"
                            and not _piece.is_empty
                            and _piece.area >= 25.0):
                        pav_polys.append(_piece)
                        third_party_pav_ids.add(id(_piece))
                        _border_area += _piece.area
                _n_border_kept += 1
            if _n_border_kept:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: DSF border-line strips: "
                    f"{_n_border_kept} of "
                    f"{len(dsf_border_line_candidates)} wide .lin "
                    f"path(s) wrap pavement — {_border_area:.0f} m2 "
                    f"added as pavement.")
        except _GEOM_EXC:
            pass

    pav_union = unary_union(pav_polys) if pav_polys else None
    # Merge near-touching apt.dat polygons so the union is one big
    # coverage (with real holes only) — see ``_merge_near_touching``.
    pav_union = _merge_near_touching(pav_union)
    # Per user 2026-05-05: simplify pav_union FIRST so all
    # downstream consumers (rect snap, junction emit) see a clean
    # 1 m-resolution coverage polygon.  Apt.dat row-110 polygons
    # routinely contain over-resolved curves (sub-meter steps) and
    # 0.2 m doubled-vertex needles that would otherwise survive
    # into the residue.  Rect corners snap to this simplified
    # boundary, so subtracting rects from pav_union should align
    # perfectly.
    from .pavement.union_helpers import (
        _close_open_clean,
        _simplify_pavement_polygon,
    )
    # Seam cleanup (user 2026-05-21): where apt.dat and DSF pavement
    # share a boundary, their slightly-different vertices leave BOTH thin
    # interior holes (gaps) AND thin exterior lips (spurs).  A single
    # mitre-join close-then-open removes both — narrower than the
    # effective-width threshold — with no net area change, replacing the
    # old separate ``_drop_sliver_holes`` (+ never-wired
    # ``_trim_sliver_spurs``).  Real grass infields and smooth bezier
    # curves (mitre-preserved) are untouched.  Run BEFORE the simplify so
    # the final boundary is clean for the downstream rect snap / junction
    # emit.
    pav_union = _close_open_clean(pav_union)
    # Simplify to a clean ~2 m-resolution coverage polygon: drop apt.dat
    # over-resolution (sub-meter curve steps) and doubled-vertex needles
    # so rect corners snap to a stable boundary and subtracting rects
    # aligns.  (User-approved tol=2.0 to match the reviewed union.)
    #
    # User 2026-06-28: DISABLED by default.  The 2 m vertex moves blur the
    # narrow truck-route necks that distinguish a groundside parking LOT from
    # the apron it abuts (CYXY 101/102 = a 12.5k m² apt.dat⊕DSF polygon meeting
    # the main apron over a 7.6 m truck-only neck) — we want pav_union to keep
    # the EXACT source outline so those connections stay legible for role
    # classification.  Set O4_PAV_UNION_SIMPLIFY=1 to restore the old behaviour.
    if os.environ.get("O4_PAV_UNION_SIMPLIFY", "0") == "1":
        pav_union = _simplify_pavement_polygon(pav_union, tol=2.0)

    # Record the SOURCE pavement union (apt.dat row-110 ⊕ DSF, before
    # runway subtraction) for build-time verification: every emitted
    # pavement shape must rest on this (∪ runway).  Captured here, before
    # the runway / ground-zone differences below mutate ``pav_union``.
    layout.source_pavement_union = pav_union

    # Source-attribution boundary for the junction-vertex test: junctions
    # are cut from THIS union (apt.dat row-110 + DSF pavement), so a
    # junction perimeter vertex following the union boundary is legitimately
    # sourced — even where the boundary comes from DSF pavement, which the
    # row-110-only ``apt_pavement_vertices`` capture above doesn't include.
    # (Test-only; the builder never reads ``apt_pavement_boundary``.  The
    # row-110-only ``apt_pavement_vertices`` still feeds canonical_points,
    # so the snap seed is unchanged.)  UNION with the existing row-110
    # boundary rather than replacing it: the union is simplified (tol=2.0)
    # so it can sit ~2 m off an unsimplified row-110 vertex — keeping both
    # is strictly more permissive and can't regress airports without DSF.
    if pav_union is not None and not pav_union.is_empty:
        try:
            _pub = pav_union.boundary
            if layout.apt_pavement_boundary is not None:
                layout.apt_pavement_boundary = unary_union(
                    [layout.apt_pavement_boundary, _pub])
            else:
                layout.apt_pavement_boundary = _pub
        except _GEOM_EXC:
            pass

    # ── AIRPORT-REGION ROAD FEED (2026-07-26) ────────────────────
    # Publish the ONE shared road/rail dataset for this airport here,
    # the first point where the query box's inputs (row-130 boundary,
    # source pavement union, runway union) all exist.  See the section
    # header at the bottom of ``osm_load`` for what it fixes: the tile
    # ``small_roads`` cache the small-road loader reads is written only
    # at ``road_level >= 2`` and the default is 1, so at default config
    # EVERY airport saw zero minor-road evidence, silently.
    #
    # FOUNDATION ONLY — nothing downstream reads it yet (classification
    # refinement and inset road grading will), so the emitted patch is
    # byte-identical with ``O4_AIRPORT_ROAD_FEED`` on or off.  The
    # service-road builder below deliberately keeps reading
    # ``_load_osm_small_roads``; rewiring it would widen the service-road
    # network at every airport in the world and is the owner's call.
    if AIRPORT_ROAD_FEED:
        try:
            _load_airport_road_network(layout)
        except Exception as _road_feed_error:
            # Evidence is never a dependency: a failed feed logs and the
            # build proceeds exactly as it did before the feed existed.
            UI.vprint(
                1, f"   [road-feed] {icao}: feed unavailable "
                   f"({_road_feed_error}); continuing without it.")

    # ── Border-strip-derived shoulder DECLARATION (user 2026-07-17) ──
    # KBNA construction style: the runway's own ``.pol`` pieces are
    # exact runway width and the shoulder is a wide draped ``.lin``
    # border traced along the runway outline — the strip's declared
    # width states the shoulder width EXACTLY (width/2; 13/31's 24 m
    # border ⇒ 12 m, 02C/20C's 20 m ⇒ 10 m).  Rather than grow a new
    # widening mechanism, DECLARE the measurement into the apt.dat
    # coded-shoulder path below ("this runway HAS 12 m shoulders"):
    # the established block widens symmetrically, junctions cut at the
    # shoulder edge (the OMAA-proven model), downstream segmentation
    # reads the widened ``width_m``, and the extent pass skips the
    # runway via the coded skip-set update.  Shoulders are symmetric
    # even when the border evidence is one-sided — the other side's
    # shoulder band is simply covered by abutting taxiway/apron
    # ``.pol`` pavement (13/31's right edge), and cutting junctions at
    # the shoulder line there is exactly the coded-shoulder semantics.
    # NOTE: the runway-segmentation contact budget
    # (RUNWAY_SHOULDER_SEGMENT) ran BEFORE DSF ingest, so it cannot
    # see a border-derived code — inert at KBNA (zero row-110
    # contacts); revisit if a border-styled pack ships row-110
    # contact geometry.
    # Without the wide-biased extent clamp these runways used to get
    # (15 m/side against continuous flanking pavement), the emitted
    # rect lands on the author's true shoulder edge instead of eating
    # ~4 m of taxiway complex per side and shredding the junctions.
    from .config import (
        RUNWAY_BORDER_SHOULDER,
        RUNWAY_BORDER_SHOULDER_EDGE_TOL_M,
        RUNWAY_BORDER_SHOULDER_MIN_SIDE_COVER_M,
        RUNWAY_BORDER_SHOULDER_MIN_STRIP_COVER_M,
        RUNWAY_BORDER_SHOULDER_SAMPLE_STEP_M,
        RUNWAY_SHOULDER_EXTENT_MAX_M,
        RUNWAY_SHOULDER_EXTENT_MIN_M,
    )
    if (RUNWAY_BORDER_SHOULDER and runway_polys
            and dsf_border_line_candidates):
        _border_strip_lines = [
            (_bl_line, _bl_width)
            for (_bl_line, _bl_width, _bl_closed, _bl_def)
            in dsf_border_line_candidates]
        for r in apt.runways:
            if r.shoulder_code // 100 >= 1:
                continue        # apt.dat already declares a width
            ref = f"{r.desig_a}/{r.desig_b}"
            if ref in _shoulder_widened_refs:
                continue
            try:
                border_shoulder_w = (
                    _detect_runway_border_strip_shoulders(
                        r, to_m, _border_strip_lines,
                        edge_tol_m=RUNWAY_BORDER_SHOULDER_EDGE_TOL_M,
                        sample_step_m=(
                            RUNWAY_BORDER_SHOULDER_SAMPLE_STEP_M),
                        min_strip_cover_m=(
                            RUNWAY_BORDER_SHOULDER_MIN_STRIP_COVER_M),
                        min_side_cover_m=(
                            RUNWAY_BORDER_SHOULDER_MIN_SIDE_COVER_M),
                        min_w=RUNWAY_SHOULDER_EXTENT_MIN_M,
                        max_w=RUNWAY_SHOULDER_EXTENT_MAX_M))
            except _GEOM_EXC:
                continue
            if border_shoulder_w is None:
                continue
            coded_width_m = int(round(border_shoulder_w))
            if coded_width_m < 1:
                continue
            r.shoulder_code = (100 * coded_width_m
                               + (r.shoulder_code % 100))
            UI.vprint(1,
                f"  [pav-builder] {icao}: runway {ref}: .lin border "
                f"strips declare {coded_width_m} m shoulders "
                f"(strip width / 2) — handled by the coded-shoulder "
                f"path.")

    # ── Runway shoulder widening (user 2026-05-23) ──────────────────
    # apt.dat row 100 field 4 encodes the runway shoulder as
    # ``100 * shoulder_width_m + surface_code`` (X-Plane 12 spec): when
    # the value is > 100 the 100s/1000s digits give the shoulder width in
    # whole metres per side (e.g. HECA's 701 = surface 1 + 7 m, 724 =
    # surface 24 + 7 m); a value < 100 is a bare surface code with no
    # explicit width (X-Plane's own 3-5 m default scaling — we leave
    # those runways unwidened, e.g. SPJC 27/28, CYXY 1).  The shoulder
    # strip isn't in the row-100 width, so without accounting for it it
    # falls into the junction/apron residue as thin "wings" running along
    # the runway.  For each runway with an explicit shoulder width, widen
    # its rect symmetrically by that width per side (spec-driven, no
    # pavement analysis), keeping it a clean 4-corner rect.  Done here,
    # BEFORE the runway is subtracted from the pavement union below, so
    # the strip becomes runway and the junctions come out clean; Phase-2
    # segmentation (reads ``width_m``) builds sub-rects at the widened
    # width.  Skip runways already widened by the pre-DSF whole-polygon
    # shoulder pass so the two don't compound.
    if runway_polys:
        _widened_any = False
        for ridx, r in enumerate(apt.runways):
            if ridx >= len(runway_polys):
                continue
            shoulder_w_m = r.shoulder_code // 100   # encoded width (m)/side
            if shoulder_w_m < 1:
                continue
            ref = f"{r.desig_a}/{r.desig_b}"
            if ref in _shoulder_widened_refs:
                continue
            rect = runway_polys[ridx]
            if rect is None or rect.is_empty:
                continue
            half = r.width_m / 2.0
            old_w = r.width_m
            new_rect = _widen_runway_rect(
                r, layout.anchor,
                -(half + shoulder_w_m), half + shoulder_w_m, to_m)
            if new_rect is None or new_rect.is_empty:
                continue
            runway_polys[ridx] = new_rect
            for s in layout.shapes:
                if s.role == ROLE_RUNWAY and s.ref == ref:
                    s.polygon = new_rect
                    break
            _widened_any = True
            UI.vprint(1,
                f"  [pav-builder] {icao}: shoulder-widened runway "
                f"{ref}: {old_w:.1f}m → {r.width_m:.1f}m "
                f"(+{shoulder_w_m}m/side, apt.dat shoulder code "
                f"{r.shoulder_code}).")
        if _widened_any:
            layout.runway_union = (unary_union(runway_polys)
                                   if runway_polys else None)
        for ridx, r in enumerate(apt.runways):
            # Row-100-widened runways join the skip set so the
            # extent pass below doesn't compound on top.
            if r.shoulder_code // 100 >= 1:
                _shoulder_widened_refs.add(f"{r.desig_a}/{r.desig_b}")

    # ── Extent-based runway shoulder widening (user 2026-06-12) ────
    # Shoulders carried only by DSF pavement (KPHL StarSim: a whole-
    # airport Groundtextures asphalt.pol ring, 3.7 M m²/87 holes) have
    # no discrete row-110 strip polygon for the whole-polygon pass
    # (which also runs pre-DSF) and no row-100 declared width for the
    # spec pass above — the strip along each runway edge falls into
    # residue and emits as apron pieces hugging the runway.  Measure
    # the pavement itself: when a consistent strip of shoulder-range
    # width runs along a runway edge in the FINAL union and is mostly
    # NOT row-110-covered (the DSF gap — measured KPHL q1/median
    # extents 3-11 m at 100 % station coverage on every side), widen
    # the rect over it here, BEFORE the runway subtraction below, so
    # the strip becomes runway.  Row-110-carried shoulders keep their
    # established handling (whole-polygon absorption; SPJC's envelope
    # shoulders deliberately live in the junction cut — see the
    # INTERSECTION_PROX_M budget above).
    from .config import (
        RUNWAY_SHOULDER_EXTENT,
        RUNWAY_SHOULDER_EXTENT_MAX_APT_FRAC,
        RUNWAY_SHOULDER_EXTENT_MAX_M,
        RUNWAY_SHOULDER_EXTENT_MIN_COVERAGE,
        RUNWAY_SHOULDER_EXTENT_MIN_M,
        RUNWAY_SHOULDER_EXTENT_STATION_M,
        RUNWAY_SHOULDER_EXTENT_STEP_M,
    )
    if (RUNWAY_SHOULDER_EXTENT and runway_polys
            and pav_union is not None and not pav_union.is_empty):
        _apt_only_union = None
        try:
            _apt_only_union = unary_union(
                [p for p in apt_only_pav_polys
                 if p is not None and not p.is_empty])
        except _GEOM_EXC:
            _apt_only_union = None
        _ext_widened_any = False
        for ridx, r in enumerate(apt.runways):
            if ridx >= len(runway_polys):
                continue
            ref = f"{r.desig_a}/{r.desig_b}"
            if ref in _shoulder_widened_refs:
                continue
            rect = runway_polys[ridx]
            if rect is None or rect.is_empty:
                continue
            try:
                extent = _detect_runway_shoulder_extent(
                    r, to_m, pav_union, _apt_only_union,
                    station_m=RUNWAY_SHOULDER_EXTENT_STATION_M,
                    step_m=RUNWAY_SHOULDER_EXTENT_STEP_M,
                    min_w=RUNWAY_SHOULDER_EXTENT_MIN_M,
                    max_w=RUNWAY_SHOULDER_EXTENT_MAX_M,
                    min_coverage=RUNWAY_SHOULDER_EXTENT_MIN_COVERAGE,
                    max_apt_frac=RUNWAY_SHOULDER_EXTENT_MAX_APT_FRAC)
            except _GEOM_EXC:
                continue
            if extent is None:
                continue
            new_left, new_right = extent
            old_w = r.width_m
            new_rect = _widen_runway_rect(
                r, layout.anchor, new_left, new_right, to_m)
            if new_rect is None or new_rect.is_empty:
                continue
            runway_polys[ridx] = new_rect
            for s in layout.shapes:
                if s.role == ROLE_RUNWAY and s.ref == ref:
                    s.polygon = new_rect
                    break
            _shoulder_widened_refs.add(ref)
            _ext_widened_any = True
            UI.vprint(1,
                f"  [pav-builder] {icao}: extent-widened runway "
                f"{ref}: {old_w:.1f}m → {r.width_m:.1f}m "
                f"(measured shoulder strip "
                f"{-new_left - old_w / 2.0:+.1f}m/"
                f"{new_right - old_w / 2.0:+.1f}m per side).")
        if _ext_widened_any:
            layout.runway_union = (unary_union(runway_polys)
                                   if runway_polys else None)

    # ── Pavement-runway intersection points (per user 2026-05-05) ──
    # RELOCATED POST-DSF (user ruling 2026-07-17: "segmentation
    # contacts definitely need to run after we've processed the DSF or
    # we could miss important things").  This block previously ran
    # before the DSF sweep on ``apt_only_pav_polys`` — at packs that
    # ship ALL their taxiway pavement as draped ``.pol`` (KBNA, KCLT)
    # it collected ZERO exit contacts and the runways segmented on
    # thresholds alone.  It now runs on the FULL pavement set (apt.dat
    # ⊕ DSF ⊕ admitted border strips) AFTER every shoulder-widening
    # pass, so contacts are measured against the final widened rect at
    # the true paved connection points.  Two consequences of the new
    # position: pavement polygons wholly INSIDE a runway's rect are
    # skipped (a segmented-runway pack draws the runway itself as ~95
    # short ``.pol`` pieces — their internal joints are not exit
    # contacts), and the RUNWAY_SHOULDER_SEGMENT coded-budget
    # extension is retired (the rect is already widened to the coded /
    # border-derived shoulder edge before contacts are collected;
    # extending the band again would double-reach past the shoulder
    # and catch parallel taxiways).
    # Walk each pavement polygon's exterior; collect
    # the vertices that sit within ``INTERSECTION_PROX_M`` of a
    # runway's 4-corner rect boundary AND project to a centerline
    # parameter strictly between 0 and 1 (not at the runway ends).
    # These t-values become segment seam corners during Phase 2's
    # runway segmentation, so chain corners (= the runway-union
    # exterior) align exactly with apt.dat-pavement boundaries.
    # Without this, the junction-widening pass has to bridge the
    # gap with boundary-trace waypoints — the alignment makes that
    # unnecessary.  Per user direction: dedup intersections within
    # 2 m centerline distance (a junction can span a 2 m gap
    # without needing a node there).
    #
    # Per user 2026-05-11: tolerance widened from 0.5 m to 3.0 m so
    # apt.dat pavement boundaries drawn slightly INSIDE the row-100
    # runway rect (1-2 m offsets are common — SPJC's row-110 stops
    # 1.75 m short of 16R/34L at the V1 throat) still register as
    # runway intersection points.  Without this, the segmenter
    # doesn't insert a seam corner at the chart-level pavement
    # transition, and the downstream junction-widening pass can't
    # share a vertex with the runway there — leaving a visible
    # 1-2 m sliver gap between every taxi-junction and the runway
    # boundary.  The runway segmenter projects each kept point onto
    # the centerline and emits the seam corner there; the actual
    # corner sits on the runway boundary (rect-perpendicular at
    # half-width) regardless of how far the source pavement vertex
    # was off-edge, so widening the tolerance just unlocks more
    # near-runway pavement landmarks as segmentation breakpoints
    # without distorting the segmenter's output geometry.
    #
    # Per user 2026-05-14: bumped 3.0 → 6.0 m to capture SPLP's
    # north-end pavement corners drawn ~5 m INSIDE the runway
    # rect.  At 3 m those corners were missed; the runway
    # segmenter put no seam there, and the apron junction between
    # the A stub and the runway had to span ~110 m of runway
    # boundary (segment 25's full length) without a shared-vertex
    # snap point — the junction's runway edge ran past the A-stub
    # corner with no clean trapezoid shape.
    #
    # Per user 2026-05-17: budget = RUNWAY_SHOULDER_M (standard
    # FAA shoulder allowance, ~7.6 m per side) + CHART_TOL_M.
    # The runway rect from apt.dat row 100 covers only the
    # published runway width; the actual paved area extends past
    # this by the shoulder width on each side (SPJC's row 100
    # declares shoulder surface code 27/28 for 16L/34R — shoulders
    # are present but not given an explicit width in apt.dat).
    # apt.dat row-110 boundary polygons that include the shoulder
    # area sit up to ~RUNWAY_SHOULDER_M past the row-100 rect.
    # Without this allowance the intersection collector misses
    # SPJC's apt.dat boundary vertex at lat -12.036366 lon
    # -77.107520 (11.3 m perpendicular from runway 16L rect — the
    # shoulder edge), no runway seam fires at Lima's natural
    # pavement termination, and Lima's end junction degenerates
    # into a triangle.
    RUNWAY_SHOULDER_M = 7.6
    CHART_TOL_M = 4.4
    INTERSECTION_PROX_M = RUNWAY_SHOULDER_M + CHART_TOL_M  # 12.0 m
    # Dedup proportionally to PROX so multi-vertex clusters of a
    # single pavement transition (row-110 boundaries drawn with 3-4
    # vertices within a 3 m span at the runway edge) collapse to one
    # seam corner instead of fragmenting the runway segment.
    INTERSECTION_DEDUP_M = 5.0
    pav_runway_intersections: dict = {}
    for ridx, r in enumerate(apt.runways):
        if ridx >= len(runway_polys):
            continue
        rect = runway_polys[ridx]
        if rect is None or rect.is_empty:
            continue
        rect_boundary = rect.exterior
        cl_ax, cl_ay = to_m(r.lon_a, r.lat_a)
        cl_bx, cl_by = to_m(r.lon_b, r.lat_b)
        cl_dx = cl_bx - cl_ax
        cl_dy = cl_by - cl_ay
        cl_L2 = cl_dx * cl_dx + cl_dy * cl_dy
        if cl_L2 < 1.0:
            continue
        # Extend centerline endpoints by blast pads so ``t`` is
        # computed in the blast-extended frame — matching both the
        # rect_boundary (which includes blast pads, see
        # ``_runway_rect_m``) and the segmenter's own phys_end_a/b
        # parameterisation (which also absorbs blast pads).  Without
        # this, a row-110 vertex sitting in the blast-pad zone (e.g.
        # SPJC 16R V1 throat at 1.79 m off the runway boundary,
        # ax≈−5 m in row-100 frame) lands at t<0 and gets dropped
        # by ``end_skirt`` — the segmenter never sees it as a
        # candidate breakpoint, so the sloped end-segment (which
        # must stay 4-corner) can't split there to give the apron
        # junction a shared snap node.
        blast_a_m = r.blast_a_m or 0.0
        blast_b_m = r.blast_b_m or 0.0
        if blast_a_m > 0.0 or blast_b_m > 0.0:
            row100_dist = math.sqrt(cl_L2)
            ux = cl_dx / row100_dist
            uy = cl_dy / row100_dist
            cl_ax -= ux * blast_a_m
            cl_ay -= uy * blast_a_m
            cl_bx += ux * blast_b_m
            cl_by += uy * blast_b_m
            cl_dx = cl_bx - cl_ax
            cl_dy = cl_by - cl_ay
            cl_L2 = cl_dx * cl_dx + cl_dy * cl_dy
        phys_dist = math.sqrt(cl_L2)
        # Avoid the runway end zones — the segmenter handles those
        # via thresholds + physical-end anchors and we don't want
        # spurious end-zone seams.
        end_skirt_t = 5.0 / phys_dist
        intersections: List[Tuple[float, float]] = []
        # Split the runway at each adjacent pavement shape's CONTACT with
        # it — the NEAR and FAR edges of where the shape's boundary runs
        # along / abuts / crosses the runway — NOT at every intermediate
        # node (user 2026-05-23).  Intersect each pavement polygon's
        # boundary with a narrow band around the runway boundary: each
        # contiguous arc within the band is ONE contact (one abutting
        # shape's run along the runway edge), so we cut only at the arc's
        # two along-runway extremes and skip its interior nodes.  This
        # makes a junction whose straight edge runs 100 m along the runway
        # with no intermediate vertices ONE contact → ONE runway sub-rect,
        # and — being PROXIMITY-based, not crossing-based — also catches a
        # shape that comes right up to the runway edge without crossing
        # it.  Blast pads / displaced thresholds are part of the runway
        # rect and treated the same (contacts there cut too); only the
        # CIFP threshold cut itself comes from the segmenter's anchored
        # fractions.
        # The generic FAA-allowance budget from the FINAL (widened)
        # rect edge.  The former RUNWAY_SHOULDER_SEGMENT coded-budget
        # extension (OMAA 20 m ⇒ reach 24.4 m from the UNWIDENED rect)
        # is retired by the post-DSF relocation: every coded /
        # border-derived shoulder has already widened the rect to the
        # shoulder edge, so the generic band measured from that edge
        # reaches the same physical connection points — and extending
        # it again would double-reach past the shoulder into parallel
        # taxiway pavement.
        prox_m = INTERSECTION_PROX_M
        try:
            prox_band = rect_boundary.buffer(prox_m)
        except _GEOM_EXC:
            prox_band = None
        if prox_band is not None:
            for pav_poly in pav_polys:
                # Quick reject + own-pavement skip: a polygon wholly
                # inside the rect is runway pavement (segmented-piece
                # packs), not an exit contact.
                try:
                    if pav_poly.distance(rect_boundary) > prox_m:
                        continue
                    if rect.contains(pav_poly):
                        continue
                except _GEOM_EXC:
                    pass
                try:
                    near = pav_poly.boundary.intersection(prox_band)
                except _GEOM_EXC:
                    continue
                if near.is_empty:
                    continue
                arcs = (list(near.geoms)
                        if near.geom_type in ("MultiLineString",
                                              "GeometryCollection",
                                              "MultiPoint")
                        else [near])
                for arc in arcs:
                    if arc.is_empty:
                        continue
                    if arc.geom_type == "Point":
                        acoords = [(arc.x, arc.y)]
                    elif arc.geom_type == "LineString":
                        acoords = list(arc.coords)
                    else:
                        continue
                    a_ts = [((px - cl_ax) * cl_dx
                             + (py - cl_ay) * cl_dy) / cl_L2
                            for px, py in acoords]
                    # Cut at the contact arc's near + far edges only.
                    for t in (min(a_ts), max(a_ts)):
                        if t <= end_skirt_t or t >= 1.0 - end_skirt_t:
                            continue
                        intersections.append((t, cl_ax + t * cl_dx,
                                              cl_ay + t * cl_dy))
        # Per user (session 44): also break EVERY runway at its RUNWAY
        # CROSSINGS — where another runway's pavement overlaps this
        # one.  Without a seam there, a runway with no pavement-vertex
        # breakpoints emits as ONE rect that runs un-split across the
        # other runway, so ``_resolve_runway_crossings`` has no sub-rect
        # boundary to isolate and the crossing never becomes a clean
        # junction (CYXY 02/20).  Use RECT-OVERLAP, not centerline×
        # centerline: at CYXY the short 02/20 crosses 14L/32R's pavement
        # but 02/20's centerline ends before reaching 14L/32R's
        # centerline, so a centerline-intersection test misses that
        # crossing entirely.  Clip on BOTH sides of each crossing:
        # project the overlap REGION onto this runway's centerline and
        # add a seam at its ENTRY (t_lo) and EXIT (t_hi), so the crossing
        # region becomes its own segment (the segmenter splits there, the
        # two runways' crossing sub-rects overlap exactly, and
        # ``_resolve_runway_crossings`` merges them into one clean
        # crossing-junction; the apron can absorb a freed runway end —
        # CYXY runway-02 end).  ``rect`` includes blast pads / displaced-
        # threshold pavement, so crossings in those paved zones split too.
        for r2idx in range(len(apt.runways)):
            if r2idx == ridx or r2idx >= len(runway_polys):
                continue
            r2_rect = runway_polys[r2idx]
            if r2_rect is None or r2_rect.is_empty:
                continue
            try:
                ov = rect.intersection(r2_rect)
            except _GEOM_EXC:
                continue
            if ov.is_empty or ov.area < 1.0:
                continue
            # Project every vertex of the overlap region onto this
            # runway's centerline → t-range [t_lo, t_hi].
            ov_polys = (list(ov.geoms)
                        if ov.geom_type == "MultiPolygon" else [ov])
            ov_ts: List[float] = []
            for op in ov_polys:
                if op.geom_type != "Polygon" or op.is_empty:
                    continue
                for ox, oy in op.exterior.coords:
                    ov_ts.append(
                        ((ox - cl_ax) * cl_dx
                         + (oy - cl_ay) * cl_dy) / cl_L2)
            if not ov_ts:
                continue
            for t in (min(ov_ts), max(ov_ts)):
                if t <= end_skirt_t or t >= 1.0 - end_skirt_t:
                    continue
                # Seam point ON this runway's centerline at parameter t.
                intersections.append((t, cl_ax + t * cl_dx,
                                      cl_ay + t * cl_dy))
        if not intersections:
            continue
        # Sort by centerline t and dedup.  Per user 2026-05-11: dedup
        # by EUCLIDEAN distance between consecutive candidate points
        # rather than centerline-t alone.  A row-110 boundary that
        # approaches the runway with a slight angle puts multiple
        # close-together apt.dat vertices on the runway edge —
        # each at a slightly different axial position but only ~3 m
        # apart in real space.  Centerline-t dedup keeps them all
        # (their t values differ by ≥ dedup_t_gap); euclidean dedup
        # merges them into a single seam corner, which is what the
        # runway segmenter actually needs.  Without this, every
        # close-together row-110 vertex becomes a runway-segment
        # seam corner and the downstream junction polygon has to
        # wrap around all of them (the cluster of -349/-351/-352
        # corners on -10109's east edge that pinched -10182).
        intersections.sort(key=lambda x: x[0])
        dedup_m2 = INTERSECTION_DEDUP_M * INTERSECTION_DEDUP_M
        # Per user 2026-05-14: also dedup by ALONG-AXIS distance.
        # With INTERSECTION_PROX_M widened to 6 m we pick up
        # opposite-side pavement vertices at the same chart-level
        # runway transition (e.g. SPLP north end: an outside-edge
        # vertex on the west boundary at one t and an inside-the-
        # rect vertex on the east boundary at a t value only 4 m
        # along the runway).  Euclidean dedup misses these (10 m
        # apart across the runway), but they represent the SAME
        # transition and should collapse to one seam.  Otherwise
        # the runway segmenter inserts two adjacent seams ~4 m
        # apart and the resulting micro-segment fails the grade
        # check at the 23 % vertex-pair grade on its short edge.
        INTERSECTION_DEDUP_ALONG_M = 5.0
        deduped: List[Tuple[float, float, float]] = []
        for t, px, py in intersections:
            if deduped:
                dpx = px - deduped[-1][1]
                dpy = py - deduped[-1][2]
                if dpx * dpx + dpy * dpy < dedup_m2:
                    continue
                dt_along_m = abs(t - deduped[-1][0]) * phys_dist
                if dt_along_m < INTERSECTION_DEDUP_ALONG_M:
                    continue
            deduped.append((t, px, py))
        # Convert intersection meter-coords back to lat/lon via the
        # layout's m_to_ll (the segmenter consumes lat/lon).  Store
        # under both designator orderings so the segmenter lookup
        # finds them regardless of which key it tries.
        ll_pts = [layout.m_to_ll(px, py) for _, px, py in deduped]
        # Also store under the canonical (zero-padding-reconciled) pair
        # so the segmenter — which iterates CIFP's zero-padded ``RW09``
        # designators — matches regardless of whether THIS apt.dat
        # zero-pads its single-digit runways (see
        # ``runway_segments.canonical_runway_desig``).
        from .pavement.runway_segments import canonical_runway_desig
        ca = canonical_runway_desig(r.desig_a)
        cb = canonical_runway_desig(r.desig_b)
        for key in (
                (r.desig_a, r.desig_b),
                (r.desig_b, r.desig_a),
                ("RW" + r.desig_a.lstrip("RW"),
                 "RW" + r.desig_b.lstrip("RW")),
                ("RW" + r.desig_b.lstrip("RW"),
                 "RW" + r.desig_a.lstrip("RW")),
                (ca, cb), (cb, ca)):
            pav_runway_intersections[key] = list(ll_pts)
    layout._pav_runway_intersections = pav_runway_intersections

    # Stash the pre-runway-subtraction pavement polygon list for
    # the apron-merged-runway detection in _compute_elevations.
    # A runway segment is "apron-merged" when the apt.dat polygon
    # CONTAINING it is much larger than the segment itself —
    # apron pavement enclosing a runway is far wider than the
    # runway, while a normal runway lies inside a runway-shaped
    # apt.dat polygon that's only marginally larger than itself.
    # Third-party DSF base-texture polys are NOT apron candidates: a
    # full-airport ``.pol`` layer under the runways would apron-merge
    # every runway segment (KPHX lost 65/67 to ZDP concrete).
    apron_candidates = [p for p in pav_polys
                        if id(p) not in third_party_pav_ids]
    if pav_union is not None and layout.runway_union is not None:
        # Per user 2026-04-28: where a runway passes through a much
        # larger apron polygon, the runway is "apron-merged" — the
        # apron physically covers the runway pavement and the
        # downstream runway-segment-chain processing will drop the
        # apron-merged segments.  Don't subtract those parts from
        # pav_union now: the apron junctions should cover them
        # naturally, with no runway-shaped void to fill later.
        #
        # Detection mirrors ``_compute_elevations``'s segment-level
        # check (line ~3469) but applied to the original runway
        # polygons: the runway/candidate intersection counts as
        # apron-merged when the candidate is ≥
        # RUNWAY_APRON_AREA_RATIO × the intersection area.  A small
        # taxiway-sized candidate doesn't qualify (intersection is
        # most of the candidate); only big apron polygons do.
        apron_merged_regions: List[Polygon] = []
        for r_poly in (runway_polys if ABSORB_RUNWAY_IN_APRON else ()):
            for cand in apron_candidates:
                try:
                    inter = r_poly.intersection(cand)
                    if inter.is_empty or inter.area < 1.0:
                        continue
                    if cand.area > inter.area * RUNWAY_APRON_AREA_RATIO:
                        # Take the intersection as the apron-merged
                        # region — extracted as Polygon parts only.
                        if inter.geom_type == "Polygon":
                            apron_merged_regions.append(inter)
                        elif hasattr(inter, "geoms"):
                            for g in inter.geoms:
                                if (g.geom_type == "Polygon"
                                        and not g.is_empty):
                                    apron_merged_regions.append(g)
                except _GEOM_EXC:
                    continue
        if apron_merged_regions:
            try:
                merged_union = unary_union(apron_merged_regions)
                effective_runway = layout.runway_union.difference(
                    merged_union)
            except _GEOM_EXC:
                effective_runway = layout.runway_union
        else:
            effective_runway = layout.runway_union
        # Two pav_union variants:
        #   * ``pav_union_for_rects`` — full runway subtraction.
        #     Used by ``_build_taxi_rects`` for centerline clipping
        #     and the apron-interior boundary check.  Keeps F-style
        #     rects from extending into apron-merged-runway regions
        #     and failing the corner-on-boundary check (regression
        #     observed at CYXY's North F when residue switched to
        #     effective-runway subtraction).
        #   * ``pav_union`` (mutated below) — effective_runway
        #     subtraction so the residue / apron junctions cover
        #     apron-merged regions naturally.
        pav_union_for_rects = pav_union.difference(layout.runway_union)
        pav_union = pav_union.difference(effective_runway)
        layout._effective_runway_union = effective_runway
        layout._pav_union_for_rects = pav_union_for_rects

    # Collect all apt.dat pavement vertices (pre-union, real apt.dat
    # coord set) + runway corners.  This is the authoritative vertex
    # set the target snapper uses; rect corners will snap to these
    # preferentially so output shares vertices with target.
    apt_pav_vertices: List[Tuple[float, float]] = []
    for _pp in pav_polys:
        if _pp.is_empty or _pp.geom_type != "Polygon":
            continue
        _ec = list(_pp.exterior.coords)
        if _ec and _ec[0] == _ec[-1]:
            _ec = _ec[:-1]
        apt_pav_vertices.extend(_ec)
        for _ring in _pp.interiors:
            _rc = list(_ring.coords)
            if _rc and _rc[0] == _rc[-1]:
                _rc = _rc[:-1]
            apt_pav_vertices.extend(_rc)
    for _rp in runway_polys:
        _rc = list(_rp.exterior.coords)
        if _rc and _rc[0] == _rc[-1]:
            _rc = _rc[:-1]
        apt_pav_vertices.extend(_rc)

    _progress.step()  # [3] Building taxiways & terminals

    # ── Taxi centerlines (apt.dat primary, OSM fallback) ─────────
    # Per user 2026-05-12: apt.dat row 1201/1202 taxi-network is
    # the authoritative source for the taxi graph at airports that
    # have it.  Since the pavement footprint is also drawn from
    # apt.dat row-110 polygons, the taxi-network endpoints align
    # exactly with the pavement boundary — eliminating the OSM-vs-
    # apt.dat boundary mismatch where OSM centerlines clipped
    # against ``pav_union`` produced empty / too-short intersections
    # (CYXY's long E parallel, all of F and G — the user's
    # "taxiways turning into big junctions" report).  Fall back to
    # OSM only when the apt.dat block has no taxi-network at all
    # (some custom packs omit rows 1201/1202).
    # (session 51 per user 2026-05-27) Taxi centerlines come ONLY from
    # apt.dat (rows 1201/1202).  The OSM fallback was REMOVED: OSM
    # geometry didn't align with apt.dat pavement boundaries and produced
    # mis-clipped centerlines.  If apt.dat is missing a taxi network the
    # build will have no taxiway rects — fix the apt.dat input, don't
    # synthesise from OSM.
    _trimmed_leadins: list = []
    apt_centerlines = APR.taxi_centerlines(
        apt, to_m, rwy_centerlines=rwy_centerlines,
        trimmed_leadins=_trimmed_leadins)
    # Ramp lead-in routes trimmed from the slicing spine — still part
    # of the AUTHORED aircraft network, consumed by the reachability
    # law only (owner 2026-07-28, CYXY building2).
    layout.apt_taxi_leadin_centerlines = _trimmed_leadins
    osm_centerlines = apt_centerlines  # legacy name retained; see below
    if apt_centerlines:
        UI.vprint(1,
            f"  [pav-builder] {icao}: using {len(apt_centerlines)} "
            f"apt.dat taxi-network centerline(s) "
            f"({len(apt.taxi_nodes)} nodes, "
            f"{len(apt.taxi_edges)} edges).")
        # ICAO taxiway size now travels PER-SEGMENT on each ``TaxiCenterline``
        # (``seg_sizes``, from the row-1202 edge ``kind``) — there is no name→
        # letter table; size consumers read it off the geometry (user 2026-06-29).
        # Runway THRESHOLDS (both ends of each runway, layout-local metres) —
        # the hard anchors the building route-feasibility metric routes to
        # (P4, building_feasibility.py).  to_m(lon, lat) -> (x, y).
        layout.runway_thresholds = []
        for _r in apt.runways:
            layout.runway_thresholds.append(to_m(_r.lon_a, _r.lat_a))
            layout.runway_thresholds.append(to_m(_r.lon_b, _r.lat_b))
    else:
        # No 1201/1202 network — fall back to the airport's PAINTED
        # taxiway centerlines (row 120, paint code 1/7/51/57).  Small
        # Global Airports fields routinely ship only the painted
        # lines; they carry the authored bezier curves and connect
        # aprons to the runway, where strip discovery reconstructs a
        # much cruder network (user 2026-06-11; KOQN).  Gated by
        # PAINTED_CENTERLINE_FALLBACK; airports WITH a network are
        # untouched (cross-referencing painted geometry against the
        # network is a separate, future step).
        from .config import PAINTED_CENTERLINE_FALLBACK
        painted_cl: list = []
        if PAINTED_CENTERLINE_FALLBACK:
            painted_cl = APR.painted_taxi_centerlines(
                apt, to_m,
                pavement_union_m=pav_union,
                runway_union_m=layout.runway_union)
        if painted_cl:
            osm_centerlines = painted_cl
            UI.vprint(1,
                f"  [pav-builder] {icao}: no apt.dat taxi network — "
                f"using {len(painted_cl)} painted (row-120) taxiway "
                f"centerline(s) instead.")
        else:
            UI.vprint(1,
                f"  [pav-builder] {icao}: apt.dat has no taxi network "
                f"(and no usable painted centerlines) — no taxi rects "
                f"will be emitted (fix the apt.dat input).")
    # Preserve the full input centerline set for the apron-
    # reclassification pass (junction_repair).  Surviving rect
    # ``source_axis`` lines cover only the part of the network
    # that emitted as taxi rects; centerlines absorbed into
    # junction polygons or dropped during decomposition are no
    # longer reachable from layout.shapes.
    layout.apt_taxi_centerlines = list(osm_centerlines)

    # ── STRING-SUBSTRATE CAPTURE (Fable RULING 4, 2026-07-31;
    # docs/specs/s1-taut-chord-constructor-spec.md, second rulings
    # block — §10(i) FIRED AND CLOSED) ────────────────────────────
    # THIS IS THE S2 SNAPSHOT.  The taut-chord constructor's substrate
    # is assembled from this exact centerline set ∪ the OSM linear
    # taxiways, and NEITHER tier is reachable at the solver hook:
    #
    #   gap 2 — ``centerline_recognition.recognize_curved_centerlines``
    #     (called ~20 lines below) REASSIGNS ``apt_taxi_centerlines``
    #     to merged / resampled / re-split geometry, so the hook-time
    #     attribute is a processed proxy of this snapshot, not this
    #     snapshot.  Capturing HERE, deep-copied into immutable
    #     coordinate tuples, is the whole point: the reassignment
    #     below cannot reach a tuple of floats.  (The regression guard
    #     is ``tests/test_string_substrate_capture.py``.)
    #   gap 1 — the OSM linework is materialised in phase 1 and
    #     discarded; there is no field to read in phase 2.
    #
    # Captured under ONE projection (``to_m``, line ~679) into ONE
    # write-once attribute.  Gate OFF ⇒ no capture, no import, no new
    # attribute — inertness by construction, not by re-proof.  The
    # phase-1 side CAPTURES AND FINGERPRINTS; it never builds (the
    # substrate is built once, at the hook, by the pure
    # ``build_string_substrate`` every test and instrument calls).
    #
    # The gate lives inside ``_capture_string_substrate`` so the tests
    # drive the REAL production path (gate included) rather than a
    # re-implementation of it.
    _capture_string_substrate(layout, icao, osm_centerlines,
                              nodes, ways, to_m)

    # (2026-07-29) The painted-centerlines stash for the per-junction
    # spine slice was removed with junction_spine.py — only that retired
    # consumer read ``layout._painted_centerlines``.

    # RAW painted lines in METERS (ALL row-120 features, paint codes IGNORED — a
    # code marks centerline OR edge line unreliably, so the taxi-fillet extractor
    # discriminates GEOMETRICALLY: a fillet rides the route centerlines, an edge
    # line sits a half-width off).  Populated whenever painted lines exist.
    try:
        from shapely.geometry import LineString as _LS_pl
        layout._painted_lines_m = [
            _LS_pl([to_m(lo, la) for lo, la in pl.line.coords])
            for pl in (apt.painted_lines or [])
            if pl.line is not None and len(pl.line.coords) >= 2]
    except Exception:
        layout._painted_lines_m = []

    # RECOGNIZED CURVED CENTERLINES (user 2026-06-30, gate O4_RECOGNIZED_CENTERLINES):
    # swap each straight taxi route for the painted centerline that rides it (real
    # curves), before the rects / spine consume ``apt_taxi_centerlines``.  Routes
    # with no riding painted centerline keep their raw straight geometry.
    try:
        from .centerline_recognition import recognize_curved_centerlines
        recognize_curved_centerlines(layout, icao)
        # (2026-07-31) The re-feed of the recognized centerlines into the
        # local ``osm_centerlines`` list went with the rect chain — its
        # stated purpose ("the taxi RECTS must be built from the SAME
        # recognized centerlines the spine uses") had no consumer left.
        # Recognition still rewrites ``layout.apt_taxi_centerlines``, which
        # IS what the slice reads.
    except Exception:
        UI.vprint(1, f"  [pav-builder] {icao}: curved-centerline recognition "
                  f"skipped (error).")

    # apt.dat ramp starts (stands) + ground-vehicle service roads.
    # 1206 service roads become ``service_road`` rects (cap
    # SERVICE_ROAD_MAX_GRADE) when the
    # feature is enabled.  Parsing the apt.dat 1206 centerlines is skipped
    # while service roads are disabled (don't derive routes we won't use).
    # SERVICE_ROAD_CARVE (s79, docs/service_road_carve.md) needs the same
    # merged 1206 centerlines for its ON-pavement road detection.
    if ENABLE_SERVICE_ROADS or SERVICE_ROAD_CARVE:
        layout.apt_service_centerlines = APR.service_road_centerlines(apt, to_m)
        # Two one-way truck routes on ONE road (or a loop's out-and-back
        # legs) collapse onto a single shared line until they diverge —
        # one spine down the middle instead of a per-leg ridge (user
        # 2026-07-04, CYXY 'Crew cars').
        if os.environ.get("O4_MERGE_PARALLEL_SVC", "1") == "1":
            _n_par = APR.snap_parallel_service_runs(
                layout.apt_service_centerlines)
            if _n_par:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: merged {_n_par} parallel "
                    f"truck-route run(s) onto a single line.")
        if layout.apt_service_centerlines:
            UI.vprint(1,
                f"  [pav-builder] {icao}: "
                f"{len(layout.apt_service_centerlines)} service-road "
                f"centerline(s) ({len(apt.truck_edges)} truck edges).")

    # ── Terminal groundside-pavement subtraction (user 2026-04-29):
    # remove curbside / drop-off / parking pavement from pav_union
    # before downstream rect / junction construction sees it.
    # Groundside pavement sits at a different elevation than the
    # building's airside apron, so allowing it to become an apron
    # junction grade-clamps the building to the wrong altitude.
    # Subtract a perpendicular outward strip from each terminal
    # building's groundside edges (classified by OSM aeroway /
    # highway adjacency + apt.dat-pavement connectivity).
    try:
        _osm_terminal_buildings = _extract_osm_terminals(
            nodes, ways, relations, to_m)
        # Per user 2026-04-30 (CYXY -10123 NW phantom groundside):
        # pass the FULL apt.dat pavement polygon list so the
        # classifier can BFS from runway-touching polys through
        # transitive touches.  Without this, edges of the
        # terminal next to apron pavement that's not directly
        # touching a runway (e.g. the apron extends NW past the
        # terminal) classified UNKNOWN and got mis-promoted to
        # groundside.
        # Connectivity over the FULL pavement list — row-110 AND DSF
        # (owner report 2026-07-27, SPJC building81).  The 2026-07-07
        # form walked the apt-only snapshot whenever it was non-empty
        # (full list only as a zero-row-110 fallback), so a MIXED pack
        # — row-110 on the legacy side, the new terminal's aprons drawn
        # only in the DSF — left every new-terminal edge without an
        # airside rescue: the BFS could not reach pavement it never saw,
        # the edges fell through to road evidence (airside service
        # roads are ``highway=service`` in OSM too), and 100 m
        # groundside stamps carved ~190 k m² of real apron.  The BFS
        # walks whatever pavement actually exists; the airside rescue
        # is tested BEFORE road evidence, so pavement chained to a
        # runway always wins (the zone-level R-VETO).
        # ROAD FEED evidence (2026-07-27): the extract's ``ways`` carry
        # no minor roads at default config, so curbside edges often had
        # no groundside indicator at all; the feed supplies them.  The
        # UNKNOWN-edge promotion that papered over that hole is gone —
        # groundside now requires this positive evidence (see
        # ``_terminal_groundside_zone``'s contract).
        _road_net = getattr(layout, "airport_road_network", None)
        _ground_zone = _terminal_groundside_zone(
            _osm_terminal_buildings, nodes, ways, to_m,
            apt_pavement_seeds=runway_polys,
            apt_pavement_polys=(pav_polys or apt_only_pav_polys),
            relations=relations,
            road_ways=getattr(_road_net, "ways", None),
            road_nodes=getattr(_road_net, "nodes", None))
        # O4_COVERAGE_PROBE at the ground-zone boundary: report, per probe
        # point, whether the PRE-subtraction pav_union covers it and whether
        # the ground zone claims it — the earliest coverage handoff, before
        # the slice ever sees the union (a point can only be lost downstream
        # of wherever this says it still exists).
        _cpz = os.environ.get("O4_COVERAGE_PROBE")
        if _cpz:
            try:
                from shapely.geometry import Point as _CpPt
                for _tok in _cpz.split(";"):
                    _la, _lo = (float(v) for v in _tok.split(","))
                    _px, _py = to_m(_lo, _la)
                    _in_pu = (pav_union is not None
                              and pav_union.covers(_CpPt(_px, _py)))
                    _in_gz = (_ground_zone is not None
                              and not _ground_zone.is_empty
                              and _ground_zone.covers(_CpPt(_px, _py)))
                    print(f"  [gz-probe] ({_la:.5f},{_lo:.5f}): "
                          f"pav_union(pre-subtract)={_in_pu} "
                          f"ground_zone={_in_gz}")
            except Exception as _e:
                print(f"  [gz-probe] ERROR {_e!r}")
        if (_ground_zone is not None and not _ground_zone.is_empty
                and pav_union is not None and not pav_union.is_empty):
            # ``pav_union`` is None when the airport has no apt.dat
            # pavement polygons at all (OSM-terminal-only fields, e.g.
            # in tile +44-094) — there is then nothing to intersect /
            # subtract the groundside zone against, so skip the whole
            # capture rather than crash on ``None.intersection`` (the
            # downstream ``pav_union.difference`` would fail too).
            # Capture the groundside-only visible pavement BEFORE
            # the subtraction below empties pav_union of it.  Per
            # user 2026-04-29: groundside pavement should remain
            # in the output but follow DEM (with a 0.1 m gap from
            # the terminal building) rather than being flattened
            # to airside-apron elevation.  The shapes captured
            # here are emitted later with per-vertex DEM altitudes;
            # the 0.1 m terminal gap is enforced inside the emit
            # function using the LAYOUT's terminal shapes (which
            # may differ slightly from the OSM source extracts due
            # to apt.dat row-110 / DSF residue absorption).
            try:
                _groundside_visible = pav_union.intersection(
                    _ground_zone)
                _gs_polys: List[Polygon] = []
                if _groundside_visible is not None:
                    if _groundside_visible.geom_type == "Polygon":
                        if (not _groundside_visible.is_empty
                                and _groundside_visible.area >= 5.0):
                            _gs_polys.append(_groundside_visible)
                    elif (_groundside_visible.geom_type
                            == "MultiPolygon"):
                        for _g in _groundside_visible.geoms:
                            if (_g.geom_type == "Polygon"
                                    and not _g.is_empty
                                    and _g.area >= 5.0):
                                _gs_polys.append(_g)
                # Stash on the layout so the elevation pass can
                # find them once DEM is loaded.  (Apron-island
                # absorption — pieces wrongly carved out of the apron by
                # the groundside strip — happens later in
                # ``_emit_groundside_pavement_dem`` where the built apron
                # shapes exist to measure enclosure against; pav_union is
                # one undifferentiated blob here so apron vs road can't be
                # told apart yet.)
                layout._groundside_polys = _gs_polys
            except _GEOM_EXC:
                layout._groundside_polys = []
            try:
                pav_union = pav_union.difference(_ground_zone)
                if hasattr(layout, "_pav_union_for_rects"):
                    layout._pav_union_for_rects = (
                        layout._pav_union_for_rects.difference(
                            _ground_zone))
                # Also subtract from the granular polygon list so
                # downstream apron-merged-runway / rect-corner
                # detection sees a consistent pavement footprint.
                _new_pav_polys: List[Polygon] = []
                for _p in pav_polys:
                    try:
                        _q = _p.difference(_ground_zone)
                    except _GEOM_EXC:
                        _new_pav_polys.append(_p)
                        continue
                    if _q.is_empty:
                        continue
                    if _q.geom_type == "Polygon":
                        _new_pav_polys.append(_q)
                    elif _q.geom_type == "MultiPolygon":
                        for _g in _q.geoms:
                            if (_g.geom_type == "Polygon"
                                    and not _g.is_empty
                                    and _g.area >= 1.0):
                                _new_pav_polys.append(_g)
                pav_polys[:] = _new_pav_polys
                # Same for apt_only_pav_polys (used for terminal
                # containment + rect-corner snapping).
                _new_apt_only: List[Polygon] = []
                for _p in apt_only_pav_polys:
                    try:
                        _q = _p.difference(_ground_zone)
                    except _GEOM_EXC:
                        _new_apt_only.append(_p)
                        continue
                    if _q.is_empty:
                        continue
                    if _q.geom_type == "Polygon":
                        _new_apt_only.append(_q)
                    elif _q.geom_type == "MultiPolygon":
                        for _g in _q.geoms:
                            if (_g.geom_type == "Polygon"
                                    and not _g.is_empty
                                    and _g.area >= 1.0):
                                _new_apt_only.append(_g)
                apt_only_pav_polys[:] = _new_apt_only
                # Also subtract from apron_candidates — captured at
                # line 2519 BEFORE this subtract — so apron-junction
                # construction in _compute_elevations can't wrap
                # around the terminal into the groundside zone (per
                # user 2026-04-29 / way -10125 vs -10111: the apron
                # junction was extending past the terminal to the
                # upper-side roads, sharing an edge with the new
                # DEM-following groundside pavement and creating a
                # 7 m vertical cliff at CYXY).
                _new_apron_cand: List[Polygon] = []
                for _p in apron_candidates:
                    try:
                        _q = _p.difference(_ground_zone)
                    except _GEOM_EXC:
                        _new_apron_cand.append(_p)
                        continue
                    if _q.is_empty:
                        continue
                    if _q.geom_type == "Polygon":
                        _new_apron_cand.append(_q)
                    elif _q.geom_type == "MultiPolygon":
                        for _g in _q.geoms:
                            if (_g.geom_type == "Polygon"
                                    and not _g.is_empty
                                    and _g.area >= 1.0):
                                _new_apron_cand.append(_g)
                apron_candidates[:] = _new_apron_cand
                try:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: subtracted "
                        f"{_ground_zone.area:,.0f} m² of "
                        f"groundside pavement (terminal "
                        f"curbside / drop-off / parking).")
                except _GEOM_EXC:
                    pass
            except _GEOM_EXC:
                pass
    except _GEOM_EXC:
        pass

    # ── Discovered (medial-axis) taxiways: RETIRED 2026-07-31 ────
    # The medial-axis discovery pass ran here and synthesised a ``TX…``
    # centerline for every strip of pavement carrying no apt.dat/OSM
    # centerline.  It had exactly TWO consumers and d4f61d6 deleted both on
    # 2026-07-29: ``_build_taxi_rects`` (the rect GENERATION block) and
    # ``junction_spine.py``.  Nothing downstream read its output after that
    # — the global slice takes its spine from ``layout.apt_taxi_centerlines``
    # (snapshotted above, deliberately, for junction_repair's apron
    # reclassification), never from the local ``osm_centerlines`` list the
    # discovery appended to.  MEASURED 2026-07-31 before removal: 595
    # discovered centerlines at HECA (27 at SPJC) and ZERO effect on the
    # emitted patch — identical body hash (``tail -n +3``) with the block
    # gone, at both airports.  Phase 3 "Building taxiways & terminals" paid
    # for it: HECA 16.71 → 6.02 s, SPJC 4.78/4.69 → 3.08 s (the medial
    # Voronoi itself, plus the ~590 extra lines every downstream trim then
    # walked).
    # The extractor itself was DELETED in the dead-code round — see
    # ``pavement/discovered_taxiways.py``, whose medial-axis helpers still
    # serve the 1206 road strip-extension and whose header keeps the
    # retirement record (including what rebuilding it would require).

    # ── (line, name) projection + parallel SPINE / CORRIDOR model:
    #    RETIRED 2026-07-31 ──────────────────────────────────────────
    # The projection of the ``TaxiCenterline`` spine model down to
    # ``(line, name)`` tuples ran here, followed by the per-ref overall
    # chord bearings, the primary-parallel SPINE lines (± 800 m) and the
    # ± 30 m parallel-CORRIDOR polygons.  All of it fed the RECT-BUILDING
    # chain below — junction-point detection, the diagonal / perpendicular
    # / corridor trims, split-at-points, bend-hook trim, the off-corridor
    # drop and the building-pad trim — whose only consumers
    # (``_build_taxi_rects`` + its ~15 shaping passes, and
    # ``junction_spine.py``) d4f61d6 deleted on 2026-07-29.  Nothing has
    # read the transformed list since: the global slice takes its spine
    # from ``layout.apt_taxi_centerlines``, snapshotted ABOVE this point
    # (deliberately — junction_repair's apron reclassification needs the
    # UNtrimmed input set), never from the local ``osm_centerlines`` list
    # the chain rewrote.
    # MEASURED before removal (interventional; frozen COPIED src/ trees, one
    # build per process, warm caches, body sha256 of ``tail -n +3``): the
    # emitted patch is BYTE-IDENTICAL with the whole chain gone at SPJC,
    # HECA, CYXY and HEAZ — the last of which takes BOTH branches SPJC
    # never exercised (PAINTED_CENTERLINE_FALLBACK and the OSM
    # ``_find_junction_points`` fallback).
    # STILL LIVE, do not confuse with the above: the service-road (SVC)
    # block further down appends ``TaxiCenterline(is_service=True, …)`` to
    # ``layout.apt_taxi_centerlines``.  That append feeds the slice.

    # ── Pavement source-of-truth (user 2026-04-28): apt.dat row-110
    # ∪ DSF pavement, period.  Earlier revisions augmented pav_union
    # with a 30 m-wide synthetic buffer around any OSM centerline
    # that didn't intersect apt.dat/DSF; the rationale was to keep
    # rect-extraction working at airports where the OSM taxiway
    # network is more complete than the apt.dat coverage.  That
    # workaround is dropped: OSM centerlines drive WHICH taxiways
    # exist (geometry, ref tag, role), but the actual pavement
    # surface comes from apt.dat ∪ DSF only.  Centerlines without
    # matching apt.dat/DSF coverage produce no rect — that's an
    # apt.dat data gap to be fixed at the source, not papered over
    # with a synthetic strip whose width arbitrarily differs from
    # the OSM-tagged taxi width.

    # ── Terminals: expand OSM building outlines to the containing
    # apt.dat pavement polygon (or buffer if no polygon contains).
    # The target terminal is the "pad" — apt.dat pavement up to the
    # apron boundary.  OSM aeroway=terminal gives the building
    # footprint; we use that as a seed.
    osm_terminal_polys = _extract_osm_terminals(
        nodes, ways, relations, to_m)
    # Union the DSF terminal/hangar building footprints with the OSM
    # outlines (user 2026-06-12).  Stacked / abutting facade pieces are
    # first clustered into one outline per building; the merge is
    # OSM-AUTHORITATIVE (owner 2026-08-09): every OSM terminal way is
    # kept as one building and the DSF clusters majority-inside it are
    # ABSORBED, while clusters the OSM doesn't cover become pads as
    # before.  Off (DSF_BUILDINGS=0) → OSM-only, the pre-existing
    # behaviour.
    # The kept OSM ways, by IDENTITY, out of the merge — the emission-time
    # re-punch (spec §2.6) needs to know which seeds are ways.
    _kept_osm_ways: List[Polygon] = list(osm_terminal_polys)
    if DSF_BUILDINGS and dsf_building_polys:
        dsf_seed_polys = _cluster_dsf_building_facades(dsf_building_polys)
        combined_n_before = len(osm_terminal_polys)
        osm_terminal_polys = _combine_building_sources(
            dsf_seed_polys, osm_terminal_polys,
            DSF_CLUSTER_OSM_ABSORB_FRAC,
            kept_osm_out=_kept_osm_ways)
        _n_absorbed = (len(dsf_seed_polys) + combined_n_before
                       - len(osm_terminal_polys))
        UI.vprint(1,
            f"  [pav-builder] {icao}: building sources merged — "
            f"{len(dsf_seed_polys)} DSF building(s) + "
            f"{combined_n_before} OSM → {len(osm_terminal_polys)} "
            f"seed(s) (OSM-authoritative; {_n_absorbed} DSF cluster(s) "
            f"absorbed into OSM way(s)).")
    # Building-pad simplification: strip sub-pad noise (closely-spaced
    # OSM vertices and the arc facets left by the DSF facade-cluster
    # snap-buffer) that would only spawn sliver triangles in the
    # eventual ear-clip, while PRESERVING the real building corners.
    # Tolerance is TERMINAL_SIMPLIFY_TOL_M (config; dialled back to
    # 0.5 m so articulated terminal pads keep their genuine corners —
    # user 2026-06-14).
    _way_seed_ids = {id(w) for w in _kept_osm_ways}
    _cluster_pads: List[Polygon] = []
    _way_pads: List[Polygon] = []
    for otp in osm_terminal_polys:
        # Boundary gate: OSM aeroway=terminal buildings are loaded
        # from a wide region and include neighbouring airports'
        # terminals.  A terminal belongs wholly to one airport, so
        # keep it only when its centroid lies within this airport's
        # row-130 boundary.
        if boundary_gate_m is not None:
            try:
                if not boundary_gate_m.contains(otp.centroid):
                    continue
            except _GEOM_EXC:
                pass
        # Apt.dat-only candidates — DSF polygons (overlays, gap
        # fills) shouldn't compete for terminal-pad selection.
        pad0 = _terminal_pad_from_building(otp, apt_only_pav_polys)
        if pad0 is None:
            continue
        _sink = _way_pads if id(otp) in _way_seed_ids else _cluster_pads
        # Absorb finger-pier gate stands into simple pad(s) (all sources);
        # a split pier comes back as one pad per piece.
        for pad in _close_building_outline(pad0):
            try:
                simp = pad.simplify(
                    TERMINAL_SIMPLIFY_TOL_M, preserve_topology=True)
                if (simp.geom_type == "Polygon"
                        and not simp.is_empty
                        and simp.area >= PAD_MIN_AREA_M2):
                    pad = simp
            except _GEOM_EXC:
                pass
            _sink.append(pad)
    # ── R6-1: A DSF BUILDING PAD NEVER SPANS WATER (round-6 OTHH
    # residuals spec).  The DSF cluster's footprint ring is a CONVEX HULL
    # (``object_footprints.structure_ring``), and at OTHH that hull
    # bridged a lagoon and its shore: building1 (way -10001, 19,466 m²)
    # carried 2,055 m² — 10.6 % — of open water on the 2026-08-10
    # rebuild, and close/simplify added nothing.  So the CLUSTER pads are
    # clipped by the OSM water ∪ sea union here, after the close/simplify
    # loop and before the kept-way re-punch.  OSM-WAY pads are NOT
    # clipped: the mapper owns the footprint they drew (Emiri -77 is 27 m
    # inland and clean).  The union is read from the tile's own
    # ``water`` / ``coastline`` caches — no download, and a failure to
    # prove water means no clip (the clip DELETES pad area).
    from .config import (
        DSF_PAD_WATER_CLIP as _PAD_WATER_CLIP,
        DSF_PAD_WATER_CLIP_SEA_BAND_M as _PAD_WATER_BAND_M,
    )
    if _PAD_WATER_CLIP and _cluster_pads:
        try:
            from .osm_load import _load_osm_water_sea_union
            _pads_u = unary_union(_cluster_pads)
            _water_u = _load_osm_water_sea_union(
                layout.anchor[0], layout.anchor[1], to_m,
                _pads_u.bounds, sea_band_m=_PAD_WATER_BAND_M)
        except _GEOM_EXC:
            _water_u = None
        if _water_u is not None and not _water_u.is_empty:
            _n_pads_before = len(_cluster_pads)
            _area_before = sum(p.area for p in _cluster_pads)
            _cluster_pads = clip_pads_by_water(_cluster_pads, _water_u)
            _area_after = sum(p.area for p in _cluster_pads)
            if abs(_area_after - _area_before) > 1.0:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: R6-1 water clip — "
                    f"{_n_pads_before} cluster pad(s) → "
                    f"{len(_cluster_pads)}, "
                    f"{_area_before - _area_after:.0f} m² of pad over "
                    "OSM water ∪ sea removed (OSM-way pads untouched).")
    # ── RE-PUNCH the kept ways out of the cluster pads (spec §2.6, v3).
    # The merge-time clip is UNDONE by ``_close_building_outline`` above
    # for any clip hole narrower than BUILDING_OUTLINE_FILL_GATE_M (the
    # close's fill radius is 110 m and its reopen test returns EMPTY at
    # 55 m), after which the way's own pad sits INSIDE the cluster pad
    # and ``elevation._drop_overlap_against_fixed_shapes`` deletes it as
    # an "OSM relation duplicate" — measured at OTHH: 26 constructed pads
    # gone vs 3 in the control, the Emiri way among them.  Punching the
    # ways out again here restores the §2.3b invariant AT EMISSION, so
    # the duplicate test stops firing by geometry (no elevation.py change).
    if _way_pads and _cluster_pads:
        _n_cluster_before = len(_cluster_pads)
        _cluster_pads = repunch_kept_ways_from_pads(_cluster_pads, _way_pads)
        UI.vprint(1,
            f"  [pav-builder] {icao}: kept-way re-punch — "
            f"{_n_cluster_before} cluster pad(s) → {len(_cluster_pads)} "
            f"against {len(_way_pads)} OSM-way pad(s).")
    terminal_polys: List[Polygon] = _cluster_pads + _way_pads
    if osm_terminal_polys:
        UI.vprint(1,
            f"  [pav-builder] {icao}: building pads "
            f"{len(terminal_polys)}/{len(osm_terminal_polys)} kept "
            f"(boundary-gate/area filters); CONSTRUCTED "
            f"{len(terminal_polys)} (refs building1.."
            f"building{len(terminal_polys)}) — any ref absent from the "
            f"emitted patch was dropped downstream.")

    # ── Terminal gap for depressed roads (user 2026-06-10) ───────
    # Where a depressed road (KPHX Sky Harbor Blvd class — a public
    # road passing under aeroway bridges inside the boundary) runs
    # through a terminal pad, the terminal must SPLIT and leave a
    # gap for the road to pass through: carve the road corridor
    # (half-width + 0.5 m clearance) out of the pad and keep each
    # surviving piece as its own terminal.  Runs at construction —
    # pre-solve — because terminals are frozen airside after the
    # solve (geom-guard).  Gated on the airport actually having
    # aeroway bridges so the big_roads OSM layer isn't parsed for
    # the common no-bridge airport.
    from .config import EMIT_DEPRESSED_ROADS as _EMIT_DEPRESSED
    if _EMIT_DEPRESSED and terminal_polys and any(
            _tags.get("aeroway") and _tags.get("bridge", "")
            in ("yes", "viaduct")
            for _wid, _nds, _tags in ways):
        try:
            from .bridges import _depressed_road_corridor_band
            _road_band = _depressed_road_corridor_band(
                layout, xplane_root, icao)
        except _GEOM_EXC:
            _road_band = None
        if _road_band is not None and not _road_band.is_empty:
            _carved: List[Polygon] = []
            _n_split = 0
            for tp in terminal_polys:
                try:
                    if not tp.intersects(_road_band):
                        _carved.append(tp)
                        continue
                    diff = tp.difference(_road_band)
                except _GEOM_EXC:
                    _carved.append(tp)
                    continue
                pieces = [g for g in
                          (diff.geoms if hasattr(diff, "geoms")
                           else [diff])
                          if g.geom_type == "Polygon"
                          and not g.is_empty and g.area >= 100.0]
                if pieces:
                    _carved.extend(pieces)
                    _n_split += 1
                # else: pad entirely inside the corridor — the road
                # wins; the pad is dropped.
            if _n_split:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: split {_n_split} "
                    f"terminal pad(s) around depressed-road "
                    f"corridor(s) ({len(terminal_polys)} → "
                    f"{len(_carved)} pads).")
                terminal_polys = _carved

    # ── THE TINY-PAD FOLD (owner ruling RULINGS 2026-08-24) ──────────
    # A pad below ``PAD_MIN_AREA_M2`` is not an independent seat
    # authority, so it never becomes a pad at all: no ``ROLE_BUILDING``
    # shape ⇒ no building seat (``anchors.build_building_seats`` walks
    # the shapes), no frontage vertex (``grade_law.frontage_vertex_keys``
    # walks the building rings), no pad interception (A5 reads
    # ``ctx.building_polys``, likewise built from the shapes), and no
    # punch-out of the apron beneath it — the footprint REMAINS APRON and
    # its ring seats with the surrounding surface.  Where the tiny pad
    # abuts a real building, that building's weld / frontage reach
    # already governs the same ground; no new joiner is introduced.
    #
    # Applied HERE — after the water clip, the kept-way re-punch and the
    # depressed-road carve — so a pad that only FALLS below the floor as
    # a carve remnant folds too, and ``terminal_union`` (the apron
    # punch-out) never sees a folded pad.
    # Exemplar: HECA -10144, 216 m², seated 2.56 m below the terminal it
    # serves 68 m away.
    if terminal_polys:
        _kept_pads = [p for p in terminal_polys
                      if p is not None and not p.is_empty
                      and p.area >= PAD_MIN_AREA_M2]
        _n_folded = len(terminal_polys) - len(_kept_pads)
        if _n_folded:
            _folded_area = sum(
                p.area for p in terminal_polys
                if p is not None and not p.is_empty
                and p.area < PAD_MIN_AREA_M2)
            UI.vprint(1,
                f"  [pav-builder] {icao}: {_n_folded} tiny pad(s) under "
                f"{PAD_MIN_AREA_M2:g} m² folded into the surrounding "
                f"surface ({_folded_area:,.0f} m² returned to apron; "
                f"{len(terminal_polys)} → {len(_kept_pads)} pads) "
                f"— RULINGS 2026-08-24.")
            terminal_polys = _kept_pads

    terminal_union = (unary_union(terminal_polys)
                      if terminal_polys else None)
    for i, tp in enumerate(terminal_polys):
        # ref "building{N}" (user 2026-06-15): the pad pool now mixes
        # terminals, hangars, and DSF term_bridge slabs, so a generic
        # "building" label is more accurate than "terminal".  The ROLE is
        # already ROLE_BUILDING; only the display ref changes.
        layout.shapes.append(BuiltShape(
            polygon=tp, role=ROLE_BUILDING, ref=f"building{i+1}"))

    # (2026-07-31) The "drop discovered (TX) centerlines threading THROUGH a
    # building" pass (CYXY TX16) ran here.  It tested ``ref.startswith("TX")``
    # and TX refs exist only on medial-axis DISCOVERED centerlines, retired
    # above — so it now has nothing to match.  Measured at HECA before
    # removal: it dropped 6 of the 595 discovered lines, all of them already
    # unread.  The ``trim_centerlines_at_buildings`` call that used to run
    # further down went with the rest of the rect chain on 2026-07-31.

    # ── Junction points + the rect trim/split chain: RETIRED
    #    2026-07-31 (see the note above) ──────────────────────────────
    # Deleted here: the apt.dat / OSM junction-point detection (including
    # the O(n²) shapely ``intersects`` crossing scan and the
    # ``_find_junction_points`` OSM fallback), the diagonal-stub trim at
    # the parallel spines, the buffered-runway trim, the parallel-corridor
    # perpendicular trim, the diagonal-stub corridor trim,
    # ``_split_centerlines_at_points`` and ``_trim_short_bend_hooks``.
    # Every one of them rewrote the local ``osm_centerlines`` list and
    # nothing downstream read it.  The helpers themselves are KEPT in
    # ``pavement/centerlines.py`` / ``pavement/junctions.py`` (still
    # imported there, still unit-tested); only the dead call sites are
    # gone.

    # ── (s79) ON-PAVEMENT service-road centerlines (SVC refs) ─────
    # docs/service_road_carve.md: qualifying apt.dat 1206 truck-route
    # runs (narrow dedicated strips, away from terminals) join the
    # centerline set here and ride the SAME rect → junction →
    # absorption decomposition as a taxiway (user 2026-06-11), with
    # role ``service_road`` forced by the SVC ref prefix in
    # ``_build_taxi_rects``.  Late join — after the taxi-specific
    # trim / spine passes (roads are not aircraft taxi paths), before
    # the off-corridor drop and rect construction.
    _svc_lines: List[Tuple[LineString, str]] = []
    if SERVICE_ROAD_CARVE and pav_union is not None \
            and not pav_union.is_empty:
        _svc_routes = list(getattr(layout, "apt_service_centerlines",
                                   None) or [])
        if _svc_routes:
            from .pavement.service_roads import detect_road_runs
            from .pavement.centerlines import split_merged_centerline
            # Mode-B source polys = apt.dat-AUTHORED pavement only:
            # narrow DSF strips at HECA qualified runs the user ruled
            # NOT roads (2026-06-11 verdict pinned HECA's set); the
            # edge-blended-road case (CYXY pav[1] "New Taxiway 40")
            # is an apt.dat 110 polygon.
            _svc_runs = detect_road_runs(
                _svc_routes, pav_union,
                terminal_polys=terminal_polys,
                runway_union=layout.runway_union,
                source_polys=apt_only_pav_polys)
            from .pavement.service_roads import _split_at_bends as _svc_bends
            _svc_bend_split = (
                os.environ.get("O4_SVC_BEND_SPLIT", "1") == "1")
            for _k, (_run, _w, _rname) in enumerate(_svc_runs, 1):
                _ref = f"SVC{_k}"
                for _piece, _pr in split_merged_centerline(
                        _run, _ref, rwy_centerlines):
                    if _piece.is_empty or _piece.length < 1.0:
                        continue
                    # split_merged_centerline's bend-clustering over the long
                    # winding 1206 route can still emit a piece that SPANS a sharp
                    # corner (CYXY 188: a 33° turn mid-piece) — the taxi-rect builder
                    # then lays ONE rect across the curve, drifting off the route into
                    # a skewed wedge.  Bend-split each piece at sharp turns so the
                    # STRAIGHT parts each get a clean even-width rect and the corner
                    # falls out as junction residue (the taxiway model, user
                    # 2026-06-27).  Gate off → single piece.
                    _runs = (_svc_bends(list(_piece.coords))
                             if _svc_bend_split else [list(_piece.coords)])
                    for _sub in _runs:
                        if len(_sub) < 2:
                            continue
                        try:
                            _subln = LineString(_sub)
                        except _GEOM_EXC:
                            continue
                        if _subln.is_empty or _subln.length < 1.0:
                            continue
                        _svc_lines.append((_subln, _ref))
            if _svc_lines:
                # ★ 1206 provenance vs DISCOVERED (TX) lanes resolves at
                # the rect OVERLAP pass (SVC beats TX there), NOT here:
                # a feed-time line yield killed lanes whose road rect
                # then failed to emit (coverage/degenerate drops) —
                # SPJC lost TX6/TX9 secondary_parallels to roads that
                # never materialised.  Arbitrating on EMITTED geometry
                # keeps whichever surface actually exists.
                # Reclassification / repair passes measure junction
                # territory against the FULL preserved centerline set —
                # roads included, so the road-junction territory at
                # bends (the #198 U-turn) stays junction, not apron.  On the
                # SPINE model these are TaxiCenterline(is_service=True) so the
                # taxi-spine consumers skip them by flag (not a name prefix).
                layout.apt_taxi_centerlines = (
                    list(layout.apt_taxi_centerlines)
                    + [APR.TaxiCenterline(line=_ln, is_service=True, name=_rf,
                                          seg_sizes=[""] * max(0, len(_ln.coords) - 1))
                       for (_ln, _rf) in _svc_lines])
                UI.vprint(1,
                    f"  [pav-builder] {icao}: {len(_svc_lines)} "
                    f"service-road centerline piece(s) from "
                    f"{len(_svc_runs)} qualifying 1206 run(s).")

    # ── Off-corridor centerline drop: RETIRED 2026-07-31 ─────────
    # ``_drop_offcorridor_centerlines`` (runway-crossing + junction-buried)
    # ran here on the dead rect-chain list, and its log line reported a
    # discard nothing consumed.  The function is kept in
    # ``pavement/centerlines.py``.

    # ── Canonical-point registry (user 2026-05-18) ────────────────
    # Build the shared registry now, before any rect / junction
    # construction, and store on the layout so every downstream
    # pass that creates or modifies a polygon vertex resolves
    # through it.  Seeded with apt.dat row-110 pavement vertices
    # and runway corners — the immutable input geometry — so the
    # registry's "first wins" rule starts from real apt.dat data
    # rather than from whichever rect happens to register first.
    from .canonical_points import CanonicalPointRegistry
    from .layout import SHARED_VERTEX_TOL_M
    layout.canonical_points = CanonicalPointRegistry(
        tol_m=SHARED_VERTEX_TOL_M)
    layout.canonical_points.seed(layout.apt_pavement_vertices)
    if layout.runway_union is not None and not layout.runway_union.is_empty:
        try:
            _ru = layout.runway_union
            for _rp in (_ru.geoms
                        if _ru.geom_type == "MultiPolygon" else [_ru]):
                if _rp.geom_type != "Polygon":
                    continue
                _ext = list(_rp.exterior.coords)
                if _ext and _ext[0] == _ext[-1]:
                    _ext = _ext[:-1]
                layout.canonical_points.seed(_ext)
        except _GEOM_EXC:
            pass

    # ── (s81) Taxilanes stop at building edges: call site RETIRED
    #    2026-07-31 ────────────────────────────────────────────────
    # ``trim_centerlines_at_buildings`` ran here against the dead rect-
    # chain list (the ruling's LIVE effect is in the slice, which cuts
    # ``_cn_pav`` by ``terminal_union`` below, and in the route-graph laws
    # that read the UNtrimmed ``layout.apt_taxi_centerlines``).  The
    # function is kept in ``terminals.py``, unit-tested by
    # tests/test_hangar_pads.py; it has had no production call site since
    # the ``O4_SVC_CURVED_JUNCTION`` experiment was retired (2026-08-07).

    _progress.step()  # [4] Building the global-slice faces & service roads

    # (2026-07-29, owner ruling) The taxi-rect GENERATION block that ran
    # here (…_build_taxi_rects + ~15 shaping passes, ~560 lines) was
    # retired: under the global slice its output was discarded — the
    # slice below cuts the real pav_union along the route-arc spine and
    # emits every face directly.  Its only side effect was interning
    # rect corners into layout.canonical_points, so registry numbering
    # differs from rect-era builds (verify semantically, not byte-wise).

    # ── CURVE-NATIVE GLOBAL SLICE ────────────────────────────────────
    # Cut the real pav_union by the route-arc spine (or the recognized
    # painted centerlines) in ONE global arrangement — the faces are
    # conformant by construction.  docs/curve_native_spine_v2_plan.md.
    # (2026-07-29, owner ruling) This is the ONLY path: the legacy
    # O4_ROUTE_ARC_SPINE / O4_CURVE_NATIVE_SPINE gates and the rect-model
    # branch were retired.
    if os.environ.get("O4_RECOGNIZED_CENTERLINES", "0") != "1":
        from .pavement.route_arcs import apply_route_arc_spine
        apply_route_arc_spine(layout, icao)
    from .pavement.global_slice import (
        build_global_slice_faces, classify_faces)
    from .layout import ROLE_APRON, ROLE_JUNCTION
    _cn_pav = pav_union
    # SOURCE FIDELITY (user 2026-07-02, test_pavement_rests_on_source):
    # the slice emits EVERY face of its input, so the input must be
    # real source pavement (apt.dat row-110 ∪ DSF ∪ runway).  The
    # working pav_union accretes non-source area downstream of the
    # early source snapshot (lot merges, closing, absorbed residue) —
    # under the rect model those regions never became shapes (rect
    # residue rules dropped them), but the slice would emit them as
    # pavement over grass (SPLP faces at 20-24 % on source) AND their
    # bulk displaces/clips the boundary→DEM bridges.
    _src = getattr(layout, "source_pavement_union", None)
    if os.environ.get("O4_SLICE_SOURCE_CLIP", "1") != "1":
        _src = None
    if _src is not None and not _src.is_empty:
        try:
            _src_all = _src
            if (layout.runway_union is not None
                    and not layout.runway_union.is_empty):
                _src_all = _src_all.union(layout.runway_union)
            _cn_pav = _cn_pav.intersection(_src_all.buffer(0.5))
        except _GEOM_EXC:
            _cn_pav = pav_union
    if terminal_union is not None and not terminal_union.is_empty:
        try:
            _cn_pav = _cn_pav.difference(terminal_union)
        except _GEOM_EXC:
            pass
    # ── THE GAP-BRIDGING SPINE (spec heca-apron-round2 §1) ───────────
    # A FEED GAP is two taxi-route ends sitting unconnected on ONE piece
    # of continuous apron pavement: real, taxiable pavement the apt.dat
    # route graph never joined (HECA taxiway J, node 462 -> node 470,
    # 254 m, no 1202 edge and no OSM way).  The slice cuts along
    # CENTERLINES, so with no centerline there the emitted apron carries
    # a NODELESS region whose membrane is uncontrolled and which the
    # census cannot even see (no nodes -> no rows).  Synthesize the
    # missing centerline HERE — before the feed loop below — so it is a
    # first-class route: it cuts the slice, it gets a profile, and the
    # nearest-anchor chords price against it.
    #
    # ``_cn_pav`` is the slice's OWN pavement input, so the visibility
    # population is exactly the pavement the faces will be cut from;
    # the runway union is removed because a runway is not apron.
    if _cn_pav is not None and not _cn_pav.is_empty:
        from .gap_spine_bridge import synthesize_gap_spine_bridges
        _apron_pav = _cn_pav
        if (layout.runway_union is not None
                and not layout.runway_union.is_empty):
            try:
                _apron_pav = _apron_pav.difference(layout.runway_union)
            except _GEOM_EXC:
                pass
        try:
            synthesize_gap_spine_bridges(layout, _apron_pav,
                                         airport=apt, to_m=to_m)
        except Exception as _gsb_exc:                     # report, never gate
            UI.vprint(1, f"  [gap-spine-bridge] {icao}: synthesis "
                         f"FAILED ({type(_gsb_exc).__name__}: "
                         f"{_gsb_exc}) — no bridge this build")
    _cn_cls, _cn_svc, _cn_seen = [], [], set()
    for _it in (getattr(layout, "apt_taxi_centerlines", []) or []):
        _ln = getattr(_it, "chained_line", None) or getattr(_it, "line", None)
        if (_ln is None or _ln.is_empty or _ln.length < 1.0
                or id(_ln) in _cn_seen):
            continue
        _cn_seen.add(id(_ln))
        # SERVICE ROADS (user 2026-07-02): narrow truck routes are
        # sliced too — the road centerline cuts its strip out of the
        # surrounding pavement and the resulting narrow faces emit as
        # ROLE_SERVICE_JUNCTION at the road grade cap, which also
        # feeds the law's road_zone carve relaxation.  Kept in a
        # SEPARATE list so face classification can tell taxi spine
        # from truck path (a face touching both is taxi territory).
        if getattr(_it, "is_service", False):
            _cn_svc.append(_ln)
        else:
            _cn_cls.append(_ln)
    # ROAD-FEED SERVICE CENTERLINES (owner defect 2026-07-27, HECA
    # shape 636): ``apt_taxi_centerlines`` comes from the airports
    # OSM layer ONLY — at HECA that layer carries ZERO
    # ``highway=service`` ways, so the slice never cut along 2.2 km
    # of service road crossing one face and classification's R1
    # apron veto froze the whole 93k m² blob (apron + groundside +
    # roads in one shape).  The per-airport road feed
    # (``layout.airport_road_network``) already carries every
    # drivable ``highway=`` way for the region; append the ones that
    # actually TOUCH the sliced pavement to the service set so the
    # service-only-face rule and ``carve_narrow_service_strips``
    # work exactly as they do when the airports layer has the roads.
    # Pavement-intersection prefilter + duplicate suppression keep
    # the noding cost bounded (HECA: 4,611 feed ways → a few dozen
    # appended lines).
    if (os.environ.get("O4_SLICE_ROAD_FEED_SERVICE", "1") == "1"
            and _cn_pav is not None and not _cn_pav.is_empty):
        _net = getattr(layout, "airport_road_network", None)
        if (_net is not None
                and getattr(_net, "source", "none") != "none"
                and getattr(_net, "ways", None)):
            from shapely.prepared import prep as _cn_prep
            from .layout import _projection as _cn_projection
            try:
                _cn_pav_prep = _cn_prep(_cn_pav)
            except _GEOM_EXC:
                _cn_pav_prep = None
            # SINGLE-SPINE dedup (owner 2026-07-28 round 9: four
            # CYXY spots showed a second spine slicing parallel
            # strips out of taxiways/roads).  A feed way is OSM's
            # rendering of the SAME physical way wherever it runs
            # inside the AUTHORED network's corridor — service
            # lines (4 m) AND taxi routes (6 m; narrow taxiways
            # read as road-width, so free-road scoping alone does
            # not stop the duplicate).  Segment-level: only the
            # OUTSIDE remainder of a partially-riding way joins.
            _svc_dup_block = None
            _dup_parts = []
            if _cn_svc:
                try:
                    _dup_parts.append(unary_union(
                        _cn_svc).buffer(4.0))
                except _GEOM_EXC:
                    pass
            if _cn_cls:
                try:
                    _dup_parts.append(unary_union(
                        _cn_cls).buffer(6.0))
                except _GEOM_EXC:
                    pass
            if _dup_parts:
                try:
                    _svc_dup_block = unary_union(_dup_parts)
                except _GEOM_EXC:
                    _svc_dup_block = None
            _cn_to_m = _cn_projection(layout.anchor)
            _n_feed_svc = 0
            # ── §1/§2 (RULINGS 2026-08-30c): THE ROAD BRIDGE DECK ────
            # Published BEFORE the admission loop, because §2 admits a
            # deck way on BRIDGE EVIDENCE alone — without the
            # touching-pavement test below, which is exactly what drops
            # a span that crosses only the structure it bridges (LEMD
            # -2192 over the tunnel ramps at 40.4836744,-3.5809643).
            from . import road_bridge_deck as _deck
            _deck.publish_candidates(
                layout,
                touches_pavement=(
                    (lambda _w, _line: bool(_cn_pav_prep.intersects(_line)))
                    if _cn_pav_prep is not None else None))
            _n_deck_admitted = 0
            if _cn_pav_prep is not None:
                for _wid, _nrefs, _tags in _net.ways:
                    if not _tags.get("highway"):
                        continue
                    _pts = [_net.nodes[n] for n in _nrefs
                            if n in _net.nodes]
                    if len(_pts) < 2:
                        continue
                    try:
                        _fl = LineString(
                            [_cn_to_m(_lo, _la)
                             for _la, _lo in _pts])
                    except _GEOM_EXC:
                        continue
                    if _fl.is_empty or _fl.length < 1.0:
                        continue
                    _touches = bool(_cn_pav_prep.intersects(_fl))
                    _is_deck_way = _deck.is_candidate_way(layout, _wid)
                    if _is_deck_way:
                        # §2: bridge evidence admits it; record whether
                        # today's surface would have kept it, so a §1/§6
                        # stand-down restores exactly that.
                        _deck.note_bridge_evidence_only(
                            layout, _wid, _touches)
                        if not _touches:
                            _n_deck_admitted += 1
                    elif not _touches:
                        continue
                    if _svc_dup_block is not None:
                        try:
                            _fl_out = _fl.difference(_svc_dup_block)
                        except _GEOM_EXC:
                            _fl_out = _fl
                        _fl_pieces = [
                            g for g in getattr(_fl_out, "geoms",
                                               [_fl_out])
                            if g.geom_type == "LineString"
                            and g.length >= 5.0]
                        if not _fl_pieces:
                            continue  # authored network has it
                        for _fp in _fl_pieces:
                            _cn_svc.append(_fp)
                        _n_feed_svc += 1
                    else:
                        _cn_svc.append(_fl)
                        _n_feed_svc += 1
            if _n_feed_svc:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: road-feed service "
                    f"centerlines joined the slice: {_n_feed_svc} "
                    f"way(s) touching pavement"
                    + (f", {_n_deck_admitted} of them a ROAD BRIDGE DECK "
                       f"admitted on bridge evidence alone (§2)"
                       if _n_deck_admitted else "") + ".")
    # ── CORRIDOR COURSES (owner ruling 2026-08-12b, "one corridor = ONE
    # continuous law object end-to-end").  Stashed BEFORE free-road
    # scoping, because scoping is exactly what fragments a corridor into
    # the per-junction pieces the ruling names as the defect: the scoped
    # pieces stay the SLICE's input (the free-road ruling is untouched —
    # nothing new is carved), while the grade graph registers ONE chain
    # per corridor course so the corridor's axis coverage has no
    # axis-free gap.  apt.dat 1206 routes are whole courses already
    # (name-grouped linemerge); the feed ways are linemerged into maximal
    # chains and the ones a 1206 route already spells are dropped by the
    # same centerline-level dedupe the minter uses.
    if _cn_svc:
        _corridors = list(_cn_svc)
        _apt_courses = [
            cl.line for cl in (getattr(layout, "apt_service_centerlines",
                                       None) or [])
            if getattr(cl, "line", None) is not None
            and not cl.line.is_empty]
        if _apt_courses:
            from .pavement.service_roads import dedupe_service_sources
            _feed_only, _n_cd = dedupe_service_sources(
                [(ln, "") for ln in _apt_courses],
                [(ln, "") for ln in _corridors],
                width=SERVICE_ROAD_WIDTH_M,
                min_frac=SERVICE_SOURCE_DEDUPE_FRAC)
            _corridors = [e[0] for e in _feed_only]
        try:
            from shapely.ops import linemerge as _lm
            from shapely.geometry import MultiLineString as _MLS
            if _corridors:
                _merged = _lm(_MLS(
                    [ln for ln in _corridors if ln.geom_type == "LineString"])
                    if len(_corridors) > 1 else _corridors[0])
                _corridors = ([_merged] if _merged.geom_type == "LineString"
                              else [g for g in getattr(_merged, "geoms", ())
                                    if not g.is_empty])
        except Exception:
            pass
        layout._service_corridor_lines = _apt_courses + _corridors
        UI.vprint(1,
            f"  [pav-builder] {icao}: "
            f"{len(layout._service_corridor_lines)} service corridor "
            f"course(s) registered end-to-end "
            f"({len(_apt_courses)} apt.dat 1206 + {len(_corridors)} feed "
            f"chain(s)).")
    # ── FREE-ROAD scoping of the service slice set (owner ruling
    # 2026-07-27, canonical text in ``groundside.
    # free_road_subsegments``): a road inside or edge-sharing an
    # apron IS the apron — it is never carved; only the sub-segments
    # where the pavement cross-section is road-width (or the road
    # crosses open terrain) reach the slice.  Unfiltered, every
    # service line cut faces straight through wide aprons and the
    # face classifiers mis-roled the frontage (SPJC east terminal:
    # 109 k m² of phantom ``service_junction``; HECA: the
    # "svc junctions 4→76" carve the owner flagged).  Applies to the
    # apt.dat 1206 routes and the road-feed ways alike — the ruling
    # names roads, not sources.
    #
    # R7a (owner ruling 2026-08-15, Fable amendment A1): the width test
    # alone cannot tell an apron from a landside car park — a DSF
    # ``.pol`` pack delivers both as one blob — so a wide station is
    # released from the apron only on POSITIVE LANDSIDE EVIDENCE
    # (``landside_evidence_layer``: parking-aisle corridors, and
    # pavement outside the runway-touch chain).  Absence of AIRSIDE
    # evidence is not evidence: genuine DSF apron routinely carries no
    # OSM aeroway and no apt.dat name at all.
    if _cn_svc and _cn_pav is not None and not _cn_pav.is_empty:
        from .groundside import (free_road_subsegments,
                                 apron_spine_subsegments)
        from .pavement_classification import landside_evidence_layer
        _n_svc_lines_in = len(_cn_svc)
        _svc_len_in = sum(ln.length for ln in _cn_svc)
        _cn_svc_all = list(_cn_svc)
        _cn_land_ev = landside_evidence_layer(layout, pav_union=_cn_pav)
        _cn_svc = free_road_subsegments(
            _cn_svc, _cn_pav, landside_evidence=_cn_land_ev)
        _svc_len_out = sum(ln.length for ln in _cn_svc)
        # APRON SPINES (owner ruling RULINGS 2026-08-25h).  The stretches
        # the free-road walk just REMOVED are the ones that run inside or
        # along an apron, and until now they were dropped entirely — those
        # roads reached the grade graph with no centerline, so the apron
        # chain and the road family solved the same welded stations
        # independently (the back-edge sawtooth).  They come back as
        # SPINES AT THE APRON'S CAP.  Recognition is the free-road
        # predicate's own complement, never a third contact test.
        from .config import SERVICE_APRON_SPINE as _APRON_SPINE_ON
        layout._apron_spine_subsegments = (
            apron_spine_subsegments(_cn_svc_all, _cn_svc)
            if _APRON_SPINE_ON else [])
        if layout._apron_spine_subsegments:
            UI.vprint(1,
                f"  [pav-builder] {icao}: apron spines — "
                f"{len(layout._apron_spine_subsegments)} service "
                f"sub-segment(s), "
                f"{sum(l.length for l in layout._apron_spine_subsegments):,.0f} m "
                f"running inside/along apron pavement now carry a SPINE at "
                f"the apron cap (RULINGS 2026-08-25h); they stay OUT of the "
                f"reachability band (REACH_NO_SERVICE_SPINES stands).")
        UI.vprint(1,
            f"  [pav-builder] {icao}: free-road landside evidence layer "
            f"carries {len(_cn_land_ev.parts)} piece(s) "
            f"(R7a/A1 2026-08-15).")
        if _svc_len_out < _svc_len_in - 1.0:
            UI.vprint(1,
                f"  [pav-builder] {icao}: free-road scoping kept "
                f"{_svc_len_out:,.0f} of {_svc_len_in:,.0f} m of "
                f"service centerline for the slice "
                f"({_n_svc_lines_in} → {len(_cn_svc)} line(s)); "
                f"the rest runs inside/along APRON pavement and "
                f"grades with the apron (owner rulings 2026-07-27 + "
                f"R7a 2026-08-15).")
    # NO dedup — the route-arc graph is planarized, noded and
    # arc-deduped by construction, and the 3.5 m paint-dedup eats the
    # SHORT junction connector fragments (SPJC 481→399), which
    # disconnects the spine chains through junctions: PHASE A then
    # solves adjacent route chains to different levels and freezes
    # both (the 2.6 m frozen-spine walls, 1622 residual edges).
    _cn_eff = list(_cn_cls)
    # Diagnostic (O4_DUMP_SLICE_INPUT=<prefix>): dump the exact pav_union +
    # spine fed to the slice as two JOSM layers, to verify inputs.
    _cn_dump = os.environ.get("O4_DUMP_SLICE_INPUT")
    if _cn_dump:
        from .pavement.global_slice import dump_slice_inputs_osm
        dump_slice_inputs_osm(layout, _cn_pav, _cn_eff, _cn_dump,
                              runway_union=layout.runway_union)
    # Taxi centerlines first, service roads appended — a face's
    # ``centerline_ids`` >= len(_cn_eff) are truck routes.
    _cn_all = list(_cn_eff) + _cn_svc
    # END-CAP chords at service-line ends dying mid-pavement (owner
    # 2026-07-28): sever BOTH halves of the road at the interval
    # station, not just the spine side.  Ids >= _cn_cap_base are
    # CUT-ONLY — stripped from face classification below.
    _cn_cap_base = len(_cn_all)
    try:
        from .groundside import service_end_cap_lines
        _cn_all = _cn_all + service_end_cap_lines(_cn_svc, _cn_pav)
    except Exception:
        pass
    # Stash the scoped service subsegments for post-build probing
    # (severance debugging needs to see WHERE the free intervals
    # actually ended — the full centerlines can't show that).
    layout._slice_service_subsegments = list(_cn_svc)
    if not hasattr(layout, "_apron_spine_subsegments"):
        layout._apron_spine_subsegments = []
    _cn_dbg_pts = None
    _cp_spec = os.environ.get("O4_COVERAGE_PROBE")
    if _cp_spec:
        from .layout import _projection as _cp_proj
        _cp_to_m = _cp_proj(layout.anchor)
        _cn_dbg_pts = []
        for _part in _cp_spec.split(";"):
            _la, _lo = (float(v) for v in _part.split(","))
            _cn_dbg_pts.append(_cp_to_m(_lo, _la))
    _cn_faces = build_global_slice_faces(
        _cn_pav, _cn_all, runway_union=layout.runway_union, dedup=False,
        debug_pts=_cn_dbg_pts)
    _svc_base = len(_cn_eff)
    _svc_faces = set()
    for _fi, _f in enumerate(_cn_faces):
        _taxi_ids = [i for i in _f.centerline_ids if i < _svc_base]
        _svc_ids = [i for i in _f.centerline_ids
                    if _svc_base <= i < _cn_cap_base]
        if _svc_ids and not _taxi_ids:
            # A face whose ONLY centerlines are truck routes is road
            # territory (user 2026-07-02: service roads between aprons
            # and parking lots) — ROLE_SERVICE_JUNCTION at any width.
            # This also SEVERS the runway touch-chain there, so lot
            # faces beyond it demote to groundside (DEM-follow) via
            # _reclassify_runway_disconnected_to_groundside, matching
            # the rect model where the road CARVE separated the lots.
            _svc_faces.add(_fi)
        # classification below reasons over TAXI spine only; a face
        # touching both taxi and truck lines is taxi territory.
        _f.centerline_ids = _taxi_ids
    classify_faces(_cn_faces, _cn_all)
    from .layout import ROLE_SERVICE_JUNCTION as _ROLE_SVC_JCT
    # Fold the truck-territory verdict into the face's own ``kind`` BEFORE
    # anything re-partitions the list: ``_svc_faces`` holds INDICES into
    # this exact list, and the class-change cut below changes its length.
    for _fi, _f in enumerate(_cn_faces):
        if _fi in _svc_faces:
            _f.kind = "service"
            _f.axis = None
    # ── SCORER V2 — CLASS-CHANGE BOUNDARY CUT (owner RULINGS 2026-08-29d;
    #    spec docs/specs/scorer-v2-class-boundary-spec.md §1/§3) ────────
    # A face carrying BOTH authored evidence classes spans an authored
    # boundary between them (the founding site: HECA's apron back edge,
    # where apt.dat row-110 #111 and the pack's own paint both stop and a
    # lot begins).  Cut it there; the groundside side joins the GROUNDSIDE
    # POOL rather than being emitted as airside pavement, so it takes
    # groundside law through the existing emitter
    # (``_emit_groundside_pavement_dem`` at the groundside slot below) —
    # DEM-following altitudes, groundside terrace law, the lots staying
    # lots.  Nothing is deleted: every square metre that leaves the
    # airside side arrives in that pool.
    from .pavement_classification import authored_class_regions
    from .pavement.global_slice import split_faces_at_class_change
    _cls_air, _cls_gnd = authored_class_regions(layout)
    _cn_faces, _cn_class_stats = split_faces_at_class_change(
        _cn_faces, _cls_air, _cls_gnd,
        min_piece_m2=CLASS_BOUNDARY_MIN_PIECE_M2)
    _cn_roles = {"corridor": 0, "junction": 0, "apron": 0, "service": 0}
    _cn_gs_pool = 0
    for _f in _cn_faces:
        if _f.class_side == "groundside":
            # THE GROUNDSIDE SIDE IS NOT AN AIRSIDE SHAPE.  It joins the
            # pool the groundside emitter builds from, which is consumed
            # later in this build (pipeline's groundside slot), so it gets
            # the same DEM-follow treatment every other lot gets.
            if getattr(layout, "_groundside_polys", None) is None:
                layout._groundside_polys = []
            layout._groundside_polys.append(_f.polygon)
            _cn_gs_pool += 1
            continue
        _cn_roles[_f.kind] = _cn_roles.get(_f.kind, 0) + 1
        if _f.kind == "service":
            _role = _ROLE_SVC_JCT
        elif _f.kind == "apron":
            _role = ROLE_APRON
        else:
            _role = ROLE_JUNCTION
        layout.shapes.append(BuiltShape(
            polygon=_f.polygon, role=_role, ref="", source_axis=_f.axis))
    UI.vprint(1, f"  [pav-builder] {icao}: curve-native global slice — "
              f"{len(_cn_faces)} face(s) from {len(_cn_all)} centerline(s) "
              f"({_cn_roles['corridor']} corridor / "
              f"{_cn_roles['junction']} junction / {_cn_roles['apron']} apron / "
              f"{_cn_roles['service']} service; "
              f"rects/junction-emit/spine bypassed).")
    if _cn_class_stats and _cn_class_stats["faces_cut"]:
        UI.vprint(1,
            f"  [pav-builder] {icao}: class-change boundary cut — "
            f"{_cn_class_stats['faces_cut']} face(s) carried BOTH authored "
            f"evidence classes and were cut at the authored edge; "
            f"{_cn_gs_pool} piece(s) / "
            f"{_cn_class_stats['groundside_area_m2']:.0f} m2 joined the "
            f"GROUNDSIDE pool (groundside law, DEM-following); "
            f"{_cn_class_stats['pockets_kept']} authored-layer pocket(s) "
            f"kept airside (RULINGS 2026-08-29d).")
    elif _cn_class_stats and _cn_class_stats["reason"]:
        UI.vprint(1,
            f"  [pav-builder] {icao}: class-change boundary cut INERT "
            f"({_cn_class_stats['reason']}) — the face list is byte-"
            f"identical to the pre-ruling build.")
    from .geom_guard import coverage_probe as _covp
    _covp(layout, "post-slice")

    # ── NARROW truck-route strips → centered service corridors ────────
    # (user 2026-07-04, CYXY): the truck route is a SPINE in the CENTER
    # of its road — where the contiguous pavement cross-section at the
    # spine is narrow, the WHOLE strip is service pavement.  The slice
    # cuts pavement ALONG the route, so each half of a narrow strip
    # merges into the big face it touches and no narrow face ever exists
    # for classify_faces — one side (or neither) read as road.  Carving
    # the centered corridor also severs the aircraft touch-chain, so
    # lots/pads beyond it demote to groundside downstream.  Gate
    # O4_SERVICE_STRIP_CARVE=0 restores the sliced-halves behaviour.
    _n_strip = 0
    if os.environ.get("O4_SERVICE_STRIP_CARVE", "1") == "1":
        from .groundside import carve_narrow_service_strips
        # THE FEED IS CLIPPED TO THE CONTACT SCOPE (RULINGS 31d finding
        # A): this pass is the road family's SECOND minter and it was
        # carving general road pavement — 1,325 ref-less
        # service_junction rings beyond 25 m of airside at HECA, the
        # very ground the core owns under 31b.  Same region as the mint,
        # derived once (``_road_contact_scope`` memoises on the layout).
        _carve_own: dict = {}
        _n_strip = carve_narrow_service_strips(
            layout, pav_union, terminal_union,
            contact_scope=_road_contact_scope(layout, pav_union, to_m),
            ownership_out=_carve_own)
        layout._road_ownership_carve = _carve_own
        if _carve_own.get("carve_released_to_core_m"):
            UI.vprint(1,
                f"  [pav-builder] {icao}: truck-route carve feed CLIPPED "
                f"to the contact scope — "
                f"{_carve_own['carve_kept_m']:.0f} m carved, "
                f"{_carve_own['carve_released_to_core_m']:.0f} m of "
                f"{_carve_own['carve_offered_m']:.0f} m RELEASED to the "
                f"core (RULINGS 31d finding A).")
        if _n_strip:
            UI.vprint(1,
                f"  [pav-builder] {icao}: carved {_n_strip} narrow "
                f"truck-route strip piece(s) as centered service "
                f"corridor(s).")
        _covp(layout, "post-service-strip-carve")

    # ── Rectless SVC connector → service_junction: RETIRED 2026-08-07
    #    (owner approval, RULINGS "Standing approvals granted / withheld") ──
    # The default-OFF ``O4_SVC_CURVED_JUNCTION`` experiment emitted the
    # uncovered pavement corridor of a too-curved/short SVC centerline piece
    # as a ``service_junction``, so the lot it served would reclassify
    # road-only → groundside.  It was ruled a NET NEGATIVE at CYXY when it
    # was written (user 2026-06-29: the lots did reclassify, but the apron
    # edges re-graded, +~100 moderate within-shape pairs, and the all-pair
    # 4 % connectors were themselves steep on slope), never turned on, and
    # is superseded by the groundside truck-spine corridor emitter
    # (``groundside.py``, ``ROLE_SERVICE_JUNCTION`` corridors CENTERED on the
    # truck spine).  Retired with its gate, its ``_svc_widths`` width table
    # and the ``HANGAR_PADS as HANGAR_PADS_GATE`` import — all three had no
    # other reader.  ``trim_centerlines_at_buildings`` (terminals.py) is
    # KEPT: it is unit-tested by tests/test_hangar_pads.py, and this was its
    # last production call site.  Default OFF ⇒ production output is
    # unchanged (CYXY body sha identity, verified).

    # ── Ground-vehicle service_road rects ────────────────────────
    # Combine apt.dat 1206 truck routes with OSM small roads inside the
    # boundary (+ a small outside buffer), and mint SERVICE_ROAD_MAX_GRADE
    # rects ONLY where a route is a dedicated strip OUTSIDE aircraft
    # pavement (the builder drops the on-apron portions; aircraft rules
    # apply there, and pavement-clear minting means nothing existing is
    # double-paved).  These also act as apron↔DEM transition ramps.
    # SOURCE PRECEDENCE (owner 2026-08-12b): the 1206 set is authoritative,
    # the OSM small roads complement it, and an OSM line that merely
    # re-spells a 1206 route is deduped at CENTERLINE level below.
    # THE MINTER'S SOURCE IS THE CORRIDOR SET (owner 2026-08-12b, measured
    # at KCLT).  It used to be ``apt_service_centerlines`` + the tile's OSM
    # small-road cache, and at KCLT that cache is EMPTY
    # (``_load_osm_small_roads(35, -81)`` → 0 ways): the airport's service
    # roads reach this build through the per-airport ROAD FEED, which
    # nothing offered the minter.  So the ruled ramp corridor
    # (35.2136167,-80.9422409 → 35.213515,-80.9403524) had no source here
    # at all and its ~30 m pavement gap stayed unpaved with the feature ON.
    # The corridor COURSES stashed above are exactly the set the ruling
    # names — 1206 routes + the feed ways that TOUCH pavement, already
    # deduped between the two sources — so the minter now reads them, and
    # the small-road cache still complements where it has anything.
    _apt_service_lines: List = (
        list(getattr(layout, "apt_service_centerlines", []) or [])
        if ENABLE_SERVICE_ROADS else [])
    _corridor_lines: List[Tuple[LineString, str]] = (
        [(ln, "road") for ln in
         (getattr(layout, "_service_corridor_lines", None) or [])
         if ln is not None and not ln.is_empty]
        if ENABLE_SERVICE_ROADS else [])
    # ── §F5: THE WIDTH THE SOURCE STATES ─────────────────────────────
    # (LEMD ramp/road fidelity spec Amendment 1, ruling 2.)  The minter
    # took ONE width for every route while the feed states a width per
    # way: at the owner's LEMD item-3 probe way -2096 is
    # ``highway=service lanes=4`` (14.0 m) against the 6.0 m emitted, so
    # half the carriageway draped on raw DEM — the "very bumpy" surface
    # and the "half the width" are ONE defect.  The courses carry no
    # tags, so the width is re-associated to them geometrically here,
    # where the feed is in hand, and travels as the third element of the
    # entry the minter already reads.  A course that associates with
    # nothing keeps ``SERVICE_ROAD_WIDTH_M``.
    if _corridor_lines:
        from .pavement.service_roads import attach_course_widths
        _corridor_lines = attach_course_widths(
            _corridor_lines,
            getattr(layout, "airport_road_network", None),
            to_m, default=SERVICE_ROAD_WIDTH_M)
        _n_wide = sum(1 for _e in _corridor_lines
                      if abs(_e[2] - SERVICE_ROAD_WIDTH_M) > 1e-9)
        if _n_wide:
            UI.vprint(1,
                f"  [pav-builder] {icao}: {_n_wide} of "
                f"{len(_corridor_lines)} service corridor course(s) take "
                f"a STATED width from their own OSM way (widths "
                f"{sorted({round(_e[2], 1) for _e in _corridor_lines})}); "
                f"the rest keep {SERVICE_ROAD_WIDTH_M:g} m.")
    _osm_service_lines: List[Tuple[LineString, str]] = []
    # The corridor set ALREADY carries the 1206 courses (they are its first
    # half), so it REPLACES them here rather than joining them — one
    # physical corridor, one source, exactly as the grade graph does with
    # the same set.  Without a slice (unit fixtures) the 1206 set stands.
    _service_lines: List = (_corridor_lines if _corridor_lines
                            else list(_apt_service_lines))
    if ENABLE_SERVICE_ROADS and pav_union is not None and not pav_union.is_empty:
        # Keep-region = within SERVICE_ROAD_PAVEMENT_NEAR_M (25 m) of any
        # apt.dat/DSF pavement.  Keeps only the apron-access / crossing
        # roads that join the airfield; drops the deep-interior road grid
        # of large airports (HECA ~852 → a handful).  apt.dat 1206 truck
        # routes are added unconstrained above.
        try:
            _bound_buf = pav_union.buffer(SERVICE_ROAD_PAVEMENT_NEAR_M)
        except _GEOM_EXC:
            _bound_buf = None
        if _bound_buf is not None and not _bound_buf.is_empty:
            sn_nodes, sn_ways = _load_osm_small_roads(anchor[0], anchor[1])
            # Dense cities (HECA: ~9k small roads) make a full
            # intersection() per road prohibitive.  Cheap bbox reject +
            # prepared-geometry intersects() pre-check skip the roads that
            # don't touch the keep-region before paying for the exact clip.
            from shapely.prepared import prep as _prep
            _bb_minx, _bb_miny, _bb_maxx, _bb_maxy = _bound_buf.bounds
            _bound_prep = _prep(_bound_buf)
            for _wid, _nds, _tags in sn_ways:
                if _tags.get("highway") not in OSM_SMALL_ROAD_HIGHWAY_TYPES:
                    continue
                _pts = []
                for _n in _nds:
                    if _n in sn_nodes:
                        _la, _lo = sn_nodes[_n]
                        _pts.append(to_m(_lo, _la))
                if len(_pts) < 2:
                    continue
                # Bounding-box reject (cheap): road entirely outside the
                # boundary-buffer bbox can't contribute.
                _xs = [p[0] for p in _pts]
                _ys = [p[1] for p in _pts]
                if (max(_xs) < _bb_minx or min(_xs) > _bb_maxx
                        or max(_ys) < _bb_miny or min(_ys) > _bb_maxy):
                    continue
                try:
                    _ls = LineString(_pts)
                    if not _bound_prep.intersects(_ls):
                        continue
                    _clip = _ls.intersection(_bound_buf)
                except _GEOM_EXC:
                    continue
                if _clip.is_empty:
                    continue
                _nm = _tags.get("name", "") or _tags.get("highway", "road")
                if _clip.geom_type == "LineString":
                    _osm_service_lines.append((_clip, _nm))
                elif _clip.geom_type == "MultiLineString":
                    for _g in _clip.geoms:
                        if not _g.is_empty:
                            _osm_service_lines.append((_g, _nm))
    if _osm_service_lines:
        # CENTERLINE-LEVEL SOURCE DEDUPE (owner 2026-08-12b, ruling 1):
        # the 1206 spelling wins wherever an OSM small road covers the
        # same corridor — two spellings of one road would otherwise mint
        # twice and give one physical corridor two spines.
        if SERVICE_SOURCE_DEDUPE and _service_lines:
            from .pavement.service_roads import dedupe_service_sources
            _osm_service_lines, _n_dedup = dedupe_service_sources(
                _service_lines, _osm_service_lines,
                width=SERVICE_ROAD_WIDTH_M,
                min_frac=SERVICE_SOURCE_DEDUPE_FRAC)
            if _n_dedup:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: service-source dedupe "
                    f"suppressed {_n_dedup} OSM small-road line(s) already "
                    f"spelled by an apt.dat 1206 route.")
        _service_lines.extend(_osm_service_lines)
    # ── §T7: THE COVERED-SPAN MASK, PUBLISHED ONCE ───────────────────
    # Derived here (the mapped bores are known from the road feed long
    # before the roofing exists) and consumed by the minter below and by
    # the post-mint suppression at the end of the build.  The road
    # network it reads is memoised, so the phase-6 tunnel pass reuses
    # this load rather than paying for a second one.
    from . import covered_span as _covered_span
    _covered_span.publish(layout)
    if _service_lines:
        # ── THE OWNERSHIP SHRINK (spec §3.3, RULINGS 31b) ────────────
        # auto_patch mints CONTACT STUBS, not road courses: the region
        # it still owns is within SERVICE_ROAD_PAVEMENT_NEAR_M of
        # aircraft pavement (the transition — spec §3.2, the same
        # constant ``road_transition`` profiles inside) or of a
        # bridge/tunnel-tagged feed way (auto_patch's (b)/(c), and the
        # exact complement of the core's own bridge/tunnel exclusion —
        # census #106, so the two owners' sets meet without a gap).
        # Everything else is the CORE's: ``include_roads`` levels it
        # under the same 8 % clamp, and the ``apt_area`` subtraction
        # (census #104) hands it precisely the ground released here.
        _own: dict = {}
        _scope = _road_contact_scope(layout, pav_union, to_m)
        _svc_rects, _svc_junctions = build_service_road_network(
            _service_lines, pav_union,
            width=SERVICE_ROAD_WIDTH_M, min_len=MIN_SERVICE_STRIP_LEN_M,
            covered_span=_covered_span.mask_of(layout),
            contact_scope=_scope, ownership_out=_own)
        _own["near_m"] = float(SERVICE_ROAD_PAVEMENT_NEAR_M)
        # ONE DECLARED MIGRATION, however many passes mint road pavement
        # (RULINGS 31d finding A).  The truck-route carve ran earlier in
        # this build and released its own far corridor metres; they are
        # part of the population leaving the patch, so they join the
        # count the census reads rather than living in a second key
        # nobody totals.
        _carve = dict(getattr(layout, "_road_ownership_carve", None) or {})
        if _carve:
            _own.update(_carve)
            _own["offered_m"] = round(
                _own["offered_m"] + _carve.get("carve_offered_m", 0.0), 2)
            _own["kept_m"] = round(
                _own["kept_m"] + _carve.get("carve_kept_m", 0.0), 2)
            _own["released_to_core_m"] = round(
                _own["released_to_core_m"]
                + _carve.get("carve_released_to_core_m", 0.0), 2)
        layout._road_ownership = _own
        UI.vprint(1,
            f"  [pav-builder] {icao}: road OWNERSHIP — "
            f"{_own.get('kept_m', 0.0):.0f} m of centerline kept as "
            f"contact stubs / bridge-tunnel ground inside "
            f"{SERVICE_ROAD_PAVEMENT_NEAR_M:g} m, "
            f"{_own.get('released_to_core_m', 0.0):.0f} m RELEASED to the "
            f"core's include_roads (of {_own.get('offered_m', 0.0):.0f} m "
            f"offered across {_own.get('courses', 0)} course(s)) — the "
            f"census population this patch declares gone (spec §3.4).")
        for _rect, _axis, _role, _ref in _svc_rects:
            layout.shapes.append(BuiltShape(
                polygon=_rect, role=_role, ref=_ref, source_axis=_axis,
                synthesised_road_corridor=True))
        for _jpoly, _jrole, _jref in _svc_junctions:
            layout.shapes.append(BuiltShape(
                polygon=_jpoly, role=_jrole, ref=_jref,
                synthesised_road_corridor=True))
        # §2/§3: mark which of the pieces just minted ARE a deck, so the
        # tunnel-ramp cut, its clearance annulus and the covered-span
        # suppression all pass them by.
        _n_deck_pieces = _deck.stamp_shapes(layout)
        # §2 + RULINGS 2026-08-30m: the deck's ground is ROAD FROM THE
        # MOMENT IT IS MINTED, so its strip becomes its own shape HERE,
        # while every piece is still road-family and no airside role is
        # in play.  Splitting only before the scorer was too late: by
        # then the strip is inside a lot the scorer votes on whole
        # (LEMD: 1,133 of 5,134 m², 0.22).  This is the single-site form
        # the consumer-census law prefers (RULINGS 2026-08-30l (a)).
        _deck.split_shapes_at_deck(layout, icao)
        if _n_deck_pieces:
            UI.vprint(1,
                f"  [bridge-deck] §2: {_n_deck_pieces} minted road "
                f"piece(s) ARE a mapped bridge deck — flagged uncuttable "
                f"(§3) pending §1 confirmation after the tunnel pass.")
        if _svc_rects or _svc_junctions:
            UI.vprint(1,
                f"  [pav-builder] {icao}: {len(_svc_rects)} service_road "
                f"rect(s) + {len(_svc_junctions)} service_junction(s) "
                f"(ground-vehicle network minted off aircraft pavement, "
                f"cap SERVICE_ROAD_MAX_GRADE).")
    # §T4's LEFT ENDPOINT: what the minter actually made.  Every later
    # seam's delta is measured from HERE, so "40 rects vanished between
    # the minter and emit" becomes a named pass instead of a difference
    # between two log lines nobody could join.
    _road_piece_checkpoint(layout, "00_service_road_mint")


    # ── THE SOLVE-STAGE BOUNDARY (perf P2 instrument 1) ──────────────
    # Everything from here on is phases [5] + [6] — the solve and the
    # feature emit.  It lives in :func:`solve_and_finalize` so a capture
    # taken HERE can be REPLAYED into it without re-running phases 1-4
    # (``tools/solve_cut.py``).  ``_tail`` is built ONCE and both the
    # capture and the call consume it, so the two can never drift.
    #
    # The extracted body is the pre-existing text VERBATIM at its
    # original indentation — the byte-identity gate (RULINGS 2026-08-13,
    # frozen 1.0.245 baseline) is what an "improved" re-indent would
    # break.  Its parameter names keep their leading underscores for the
    # same reason.  The parameter set is the READ-BEFORE-BOUND set of
    # the tail, verified by AST against phases 1-4's bindings; ``_covp``
    # and the two ROLE constants are re-imported inside instead (same
    # objects, no parameter).
    _tail = dict(
        layout=layout, icao=icao, xplane_root=xplane_root, apt=apt,
        nodes=nodes, ways=ways, to_m=to_m,
        apron_candidates=apron_candidates, tile_dem=tile_dem,
        current_tile_lat=current_tile_lat,
        current_tile_lon=current_tile_lon,
        compute_elevations=compute_elevations,
        _n_strip=_n_strip, _progress=_progress,
        _build_features=_build_features,
        _build_started_at=_build_started_at,
    )
    from . import solve_capture as _solve_capture
    _solve_capture.maybe_capture(_tail)          # no-op unless armed

    # ── THE GAP-SPINE BRIDGE STAND-DOWN ──────────────────────────────
    # Phases [5]+[6] run through the adjudicator, which is a pass-through
    # for every build that minted no bridge.  The law, the measurement
    # behind its shape and the one-shot argument are in
    # :func:`gap_spine_stand_down_solve`'s docstring — this is the ONE
    # place that can supply both of its callables, because ``rebuild``
    # means re-running phases 1-4 and only this function is them.
    return gap_spine_stand_down_solve(
        layout=layout, icao=icao,
        solve=lambda: solve_and_finalize(**_tail),
        rebuild=lambda: build_airport_pavement(
            icao, xplane_root,
            compute_elevations=compute_elevations,
            taxiway_data=taxiway_data,
            tile_dem=tile_dem,
            airport_boundary=airport_boundary,
            current_tile_lat=current_tile_lat,
            current_tile_lon=current_tile_lon))


def solve_and_finalize(*, layout: PavementLayout, icao: str,
                       xplane_root: str, apt,
                       nodes: dict, ways: list, to_m,
                       apron_candidates: list,
                       tile_dem=None,
                       current_tile_lat=None, current_tile_lon=None,
                       compute_elevations: bool = True,
                       _n_strip: int = 0,
                       _progress=None,
                       _build_features=None,
                       _build_started_at: float = 0.0,
                       ) -> PavementLayout:
    """Phases [5] + [6]: solve the elevation field, emit the features.

    Split out of :func:`build_airport_pavement` (2026-08-13) so the
    solve stage is REPLAYABLE from a capture taken at its boundary —
    the perf phase's repro cutter, ``tools/solve_cut.py``.  Called
    exactly once, from the end of ``build_airport_pavement``; the
    replay entry is the only other caller.

    Every parameter is a live phase-1-4 product.  ``_progress`` is the
    build's progress reporter (steps [5] and [6] are reported here),
    ``_n_strip`` the narrow-service-strip carve count phase 4 recorded,
    and ``_build_features`` / ``_build_started_at`` the build-time
    model's inputs, recorded as the very last act before the return.
    """
    from .layout import ROLE_APRON, ROLE_JUNCTION
    from .geom_guard import coverage_probe as _covp

    # ── Phase-2 elevations + feature emit ────────────────────────
    # Pre-solve geometry guard snapshot handle (assigned right before the
    # solve inside the block below; default None so the post-solve report
    # is a no-op when elevations are not computed / guard is disabled).
    _geom_guard_snap = None
    # Whether the airside node-unification (weld + full conformance + corner
    # snaps) already ran PRE-solve (refactor Phases 6+7).  The per-surface
    # path runs it before the solve; the post-solve block below then conforms
    # only the post-solve-emitted FEATURES (one-sided) to the frozen airside.
    # When False (non-per-surface / no-elevation path), the post-solve block
    # runs the full unification as a fallback.
    _airside_unified_presolve = False
    if compute_elevations:
        _progress.step()  # [5] Solving elevations (FAA grade compliance)
        _covp(layout, "pre-finalize-repair")
        finalize.compute_elevations_and_repair_geometry(
            layout, icao, xplane_root, apt,
            nodes=nodes, ways=ways, to_m=to_m,
            apron_candidates=apron_candidates,
            tile_dem=tile_dem,
            current_tile_lat=current_tile_lat,
            current_tile_lon=current_tile_lon)

        # Final Rule 2 enforcement (user 2026-05-01).  Triangulation
        # densification and Laplacian-solver vertex insertions can
        # leave a few junction vertices within SLOPING_EDGE_SNAP_M of a
        # sloping rect's sloping edge despite the in-densify guard.  A
        # final post-elevation snap clears these residual cases.
        # Aligned per-vertex altitudes are preserved by index, so the
        # snap is altitude-safe (a 10 m planar move at typical
        # taxi-grade ≤ 1.5 % shifts elevation by ≤ 15 cm — well
        # within the within-shape grade tolerance).
        from .junction_rules import (
            _enforce_runway_1to1_sharing,
            stitch_pavement_to_flat_runways,
            widen_junctions_to_runway_corners,
        )
        # (session 51) `_align_rect_slope_to_axis` was DROPPED: it
        # reacted to the SOLVED slope (flattening rects whose solved
        # slope came out perpendicular to source_axis), which has no
        # place in a single pre-finalized-geometry solve — the cascade
        # grades each rect along its own source_axis, so a
        # perpendicular-slope rect should not arise.
        #
        # (session 51) The two corner-snaps that used to run HERE were
        # removed: with the altitude gate they were no-ops at this
        # pre-solve point (rects have None altitudes), and they now do
        # their real work in the post-geometry block below (after
        # split/absorb/reclassify), on the settled junction set — the
        # same place the 2-solve order ran them effectively.
        # VEER FIX 2026-07-03 (user report "spines veer to a runway corner
        # at the very end"): the pass now SPARES spine cut/contact nodes
        # (ring vertices ON a taxi centerline) — blanket retirement under
        # the slice was measured WORSE (SPLP junction↔runway seam needs the
        # corner sharing: 4 new >0.5 m steps without it).
        # (``O4_RWY_1TO1`` DELETED 2026-08-05: the comment called it a
        # debug gate, but the pass MUTATES runway node sharing — emitted
        # geometry.  Resolved to the shipped "1" arm.)
        _enforce_runway_1to1_sharing(layout)
        _covp(layout, "post-rwy-1to1")
        # Rule 1 v6 widening (user 2026-05-02): runs ONLY here,
        # post-elevation, after the runway is segmented.  Inserts
        # outboard runway corners as new junction vertices with
        # matching altitudes.  Pre-elevation widening was disabled
        # because the cascade with Rule 4 + segmentation re-run
        # over-grew junctions past the 4-node cap.
        # (measured innocent in the veer investigation — it only ADDS
        # adjacent runway corners next to shared vertices)
        # (``O4_WIDEN_RWY_CORNERS`` DELETED 2026-08-05: same mislabel —
        # it inserts junction vertices at runway corners, which is emitted
        # geometry.  Resolved to the shipped "1" arm.)
        widen_junctions_to_runway_corners(layout)
        _covp(layout, "post-widen-to-rwy-corners")
        # Stitch pavement to flat runway shapes (user 2026-05-09):
        # for blast pads / flat-interior runway segments, insert a
        # shared vertex on the runway boundary at the projection of
        # every adjacent pavement vertex that sits within edge
        # tolerance.  These new shared vertices become HARD anchors
        # at the runway altitude when the per-surface solver runs,
        # cutting cap-projection distance from the runway corners
        # (often 100s of m apart on long blast pads) down to tens
        # of metres — adjacent junctions / stubs lift toward the
        # runway elevation instead of stalling at terrain.
        stitch_pavement_to_flat_runways(layout)
        _covp(layout, "post-stitch-flat-rwys")

        # Per user 2026-05-03: per-surface solver runs AS THE LAST
        # STEP of the pipeline, after every junction rule and
        # runway-corner insertion.  ``widen_junctions_to_runway_
        # corners`` inserts vertices with raw runway altitudes that
        # may violate the surrounding junction's per-axis grade
        # rule with respect to neighbouring (terrain-following)
        # vertices; the solver pass cap-projects them into
        # compliance.
        if layout.anchor is not None:
            from .elevation import _load_airport_dem
            from .elevation_per_surface import solve as per_surface_solve
            # Per user 2026-05-12: keep DEM-tile and indexing-coords
            # in lockstep.  ``_load_airport_dem`` returns the override
            # (= driver's current-build-tile DEM) if provided, else
            # loads the anchor tile.  So the coords to use are:
            #   - current_tile_lat/lon when tile_dem is provided
            #     (DEM is the current build tile);
            #   - floor(anchor) when tile_dem is None (DEM is the
            #     anchor tile, standalone / test path).
            # Previously used floor(anchor) unconditionally — WRONG
            # for cross-tile airports during a neighbour-tile build
            # where ``current_tile`` and ``anchor_tile`` diverge
            # (e.g. SPLP anchor in -13/-78 while Ortho4XP is building
            # -13/-77), causing _sample_dem to read the wrong row.
            dem = tile_dem if tile_dem is not None else _load_airport_dem(
                layout.anchor[0], layout.anchor[1],
                xplane_root=xplane_root)
            if tile_dem is not None and current_tile_lat is not None:
                tile_lat = current_tile_lat
                tile_lon = current_tile_lon
            else:
                tile_lat = int(math.floor(layout.anchor[0]))
                tile_lon = int(math.floor(layout.anchor[1]))

            # Capture elevation provenance off the ACTUAL DEM this solve grades
            # against: which airport-elevation insets baked into it (stamped on
            # the DEM object by bake_airport_insets_into_alt_dem) or the loud
            # RAW marker when none did.  The standalone raw-load path never
            # bakes, so this correctly reports RAW even with an inset cached.
            from . import provenance as _provenance
            layout.dem_inset_provenance = (
                _provenance.dem_provenance_from_dem(dem, icao=layout.icao)
                if dem is not None else None)
            # WORLD STAMP for the instruments (RULINGS 2026-08-06 binding
            # point 3).  The inset record alone cannot tell a real raw DEM
            # from an oracle world: both render "base RAW (no inset
            # baked)".  The DEM object's own class + ``source_path`` can —
            # a ``ConstantDEM`` announces itself as
            # ``<constant-dem 10000 m>``.  Report-only; nothing reads it
            # but the frame stamps.
            try:
                layout._dem_world_label = (
                    "None (no DEM object)" if dem is None else
                    f"{type(dem).__name__}"
                    f"{':' + str(getattr(dem, 'source_path', '') or '?')}")
            except AttributeError:                    # pragma: no cover
                pass

            # ── FLAT-SITE DETECTOR (report-only) ──────────────────
            # docs/specs/flat-site-detector-spec.md section 2.  This is
            # the pipeline's DEM-IN-HAND point: the CIFP thresholds, the
            # apt.dat pavement/boundary extent and the DEM (with its
            # inset provenance, captured just above) all exist here, and
            # nothing downstream has consumed the DEM yet.  It MEASURES
            # and RECORDS — four signals, one log line, one sidecar
            # evidence key — and changes no build path.  Wrapped whole:
            # a report may never take a build down.
            try:
                from . import flat_site as _flat_site

                _site_record = _flat_site.detect_for_layout(
                    layout, icao=icao, apt=apt, to_m=to_m, dem=dem,
                    tile_lat=tile_lat, tile_lon=tile_lon,
                    patch_dir=FNAMES.patch_dir(tile_lat, tile_lon),
                    xplane_root=xplane_root)
                if _site_record is not None:
                    UI.vprint(0, _flat_site.format_log_line(_site_record))
            except Exception as _site_error:          # pragma: no cover
                UI.vprint(1,
                          f"  [flat-site] {icao}: detector skipped "
                          f"({type(_site_error).__name__}: {_site_error})")

            # ── Seam-anchor pipeline (user 2026-05-13) ────────────
            # 1) Insert ring vertices at integer lat/lon line crossings
            #    and convert sloped rects to node_altitudes.
            # 2) Sample the SMOOTHED DEM at each seam vertex
            #    (elevation._sample_dem, per the seam ruling;
            #    deterministic across tiles via preserve_boundary).
            # 3) Redistribute the runway profile (user 2026-05-19):
            #    fold seam DEM altitudes into the FAA-compliant
            #    profile that ``runway_segments.generate_patch_osm``
            #    emitted, run the same gates (envelope clamp + hard
            #    cap + rate-of-grade-change), and rewrite every
            #    runway sub-rect's altitudes per-vertex via axis
            #    projection.  Replaces the older threshold-only
            #    ``regrade_runways_in_layout`` step — that approach
            #    only adjusted the two threshold corners and left
            #    interior segment-boundary corners at their emit-time
            #    CIFP values, so the runway's combined profile after
            #    seam DEM anchors entered was no longer FAA-compliant.
            # 4) Solver runs as before — every runway vertex is
            #    HARD-anchored (whole-runway authoritative) and
            #    adjacent shapes grade themselves against it.
            from .seam_anchors import (
                split_pavement_at_seams, apply_seam_dem_anchors)
            from .runway_redistribute import redistribute_runway_profile
            n_split = split_pavement_at_seams(layout)
            n_seam = apply_seam_dem_anchors(
                layout, dem, tile_lat, tile_lon)
            n_redistributed = redistribute_runway_profile(
                layout, dem, tile_lat, tile_lon)
            seam_keys = getattr(layout, "_seam_anchor_keys", set())
            if seam_keys or n_seam or n_redistributed:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: seam pipeline — "
                    f"{len(seam_keys)} seam vert(s), "
                    f"{n_seam} DEM-anchored, "
                    f"{n_redistributed} runway shape(s) redistributed.")

            # Feature B stage 2 (O4_OBJECT_BRIDGE_TERRAIN, docs/object_
            # terrain_features_spec.md section 3.2): classify the pack's
            # bridge objects NOW (pre-solve; the same cached result feeds
            # the post-solve corridor emitters) and hard-pin pavement at
            # the deck ends / across profile-carried spans using the
            # seam-anchor idiom above.  Gate off ⇒ attach is a no-op and
            # both pin writers return 0 without touching a shape.
            try:
                from . import object_terrain_assembly
                _bridge_classification = (
                    object_terrain_assembly.attach_bridge_classification(
                        layout, xplane_root))
                from .bridges import (
                    build_bridge_layout_shapes,
                    emit_bridge_ramp_shapes,
                    insert_bridge_deck_end_pins,
                    insert_bridge_profile_pins)
                # User ruling R12: the trench and causeway are
                # FIRST-CLASS layout shapes, born HERE with law values
                # (plus the R8 flush-seat cut and the bridge-object
                # building-pad removal) before the solve — the solver
                # and every later mutation pass leave them alone by
                # construction (roles outside every pass's role set).
                (n_bridge_trench, n_bridge_causeway,
                 n_bridge_pads_removed) = build_bridge_layout_shapes(
                    layout, dem, tile_lat, tile_lon)
                if (n_bridge_trench or n_bridge_causeway
                        or n_bridge_pads_removed):
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: object-bridge layout "
                        f"shapes — {n_bridge_trench} trench, "
                        f"{n_bridge_causeway} causeway, "
                        f"{n_bridge_pads_removed} building pad(s) "
                        f"removed.")
                # Feature A stage (O4_OBJECT_TUNNEL_TERRAIN, spec section
                # 3.3 + amendment A1, ruling R12): whole-body tunnel trench
                # + rim collar, born pre-solve as first-class layout shapes
                # from the SAME cached classification.  Gate off ⇒ no-op.
                (n_tunnel_trench, n_tunnel_rim) = (
                    object_terrain_assembly.build_tunnel_layout_shapes(
                        layout, dem, tile_lat, tile_lon))
                if n_tunnel_trench or n_tunnel_rim:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: object-tunnel layout "
                        f"shapes — {n_tunnel_trench} trench floor, "
                        f"{n_tunnel_rim} rim collar.")
                n_bridge_deck_pins = insert_bridge_deck_end_pins(
                    layout, dem, tile_lat, tile_lon)
                n_bridge_profile_pins = insert_bridge_profile_pins(
                    layout, dem, tile_lat, tile_lon)
                # W1b's emitter: a road-carried span standing in unpaved
                # ground has no ring to pin, so its ramp is BUILT.
                n_bridge_ramps = emit_bridge_ramp_shapes(
                    layout, dem, tile_lat, tile_lon)
                # ALWAYS print the summary when the classifier ran —
                # a zero here is the coupling-failure signal, and a
                # silent zero is this project's classic failure mode
                # (stage 2b: the first gated KBNA build pinned nothing
                # and said nothing at verbosity 1).
                if _bridge_classification is not None:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: object-bridge pins — "
                        f"{n_bridge_deck_pins} deck-end, "
                        f"{n_bridge_profile_pins} profile; "
                        f"{n_bridge_ramps} span(s) ramped.")
            except Exception as _object_bridge_error:  # never fail the build
                UI.vprint(1,
                          "   [object-bridge] solve-side pins skipped:",
                          _object_bridge_error)

            # CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-
            # terrain-ownership.md): publish the ONE pre-solve zone every
            # terrain writer honors — the portal pairs / classification it
            # reads were cached by ``build_bridge_layout_shapes`` above,
            # and every consumer construction (runway-end skirts, gap-fill
            # spines, adjacent-ground bands, clearance) runs after this
            # point and consults the published zone instead of
            # reconstructing crossing geometry itself.
            try:
                from .crossing_terrain import (
                    publish_crossing_influence_zones)
                n_crossing_zones = publish_crossing_influence_zones(layout)
                if n_crossing_zones:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: crossing influence "
                        f"zone published — {n_crossing_zones} "
                        f"component(s).")
            except Exception as _crossing_zone_error:  # never fail the build
                UI.vprint(1,
                          "   [crossing-zone] publication FAILED — "
                          "crossing keep-outs are INACTIVE this build:",
                          _crossing_zone_error)

            # (session 51 single-solve) The first solver pass + the
            # grade-based `_subdivide_violating_junctions` loop were
            # REMOVED here.  The pipeline now finalizes ALL geometry
            # before a SINGLE solve at the end, so there is no
            # geometry↔altitude loop to bootstrap: downstream geometry
            # passes (stitch / split / absorb) are de-coupled from
            # altitudes (role-based detection), and grade relief is
            # handled inside the solver (directional + hop-hierarchy)
            # plus the pre-solve apron neck-split, not by post-solve
            # subdivision.

        # Stitch pavement to terminal pads (user 2026-05-04): make
        # the two share an identical vertex sequence on every shared
        # edge — pavement vertices near a terminal corner snap to it,
        # vertices in the edge interior get inserted into the
        # terminal polygon.  Eliminates the 4 sub-metre "step"
        # artefacts that survived the densify-skip guard.
        from .junction_rules import (
            stitch_pavement_polygons,
            stitch_pavement_to_terminals,
        )
        stitch_pavement_to_terminals(layout)
        _covp(layout, "post-stitch-terminals")
        # Adjacent junction polygons whose rings have parallel-but-
        # near-coincident edges should share OSM nids on every shared
        # boundary segment.  Inserts vertices into the other polygon's
        # ring at the projected point with z linearly interpolated
        # along the host edge.  Companion to
        # ``stitch_pavement_to_terminals`` for junction-junction
        # adjacency.  Runs before the corner-snap reconciliation so
        # ``_enforce_shared_vertex_altitudes`` can average shared-
        # bucket altitudes the stitch makes coincident.
        stitch_pavement_polygons(layout)
        _covp(layout, "post-stitch-polygons")

        # (session 51 single-solve) The cross-shape ALTITUDE
        # reconciliation chain (`_snap_junction_altitudes_to_rect_corners`
        # + `_enforce_shared_vertex_altitudes`) and the second
        # `_subdivide_violating_junctions` loop were REMOVED here.  They
        # existed to patch up altitude disagreements introduced by
        # geometry passes that ran AFTER the first solve.  With all
        # geometry finalized before a SINGLE solve, the solver's
        # writeback is lossless — one elevation per shared bucket, so
        # adjacent shapes agree at shared corners by construction and
        # there is nothing to reconcile.

        # (2026-07-29) The sloped-rect split / flat-edge snap / wedge
        # absorb passes and the sloping-edge absorption chain that ran
        # here were retired with the rect machinery (owner ruling;
        # vacuous under the global slice).
        # Apron reclassification (user 2026-05-18): a junction whose
        # boundary strays > 55 m from any taxi/runway centerline
        # contains apron-territory pavement (no centerline running
        # through it) and should be tagged ``role=apron``.  Geometric,
        # not area-based — a 6-way mega-intersection stays a junction.
        #
        # (session 51) Runs BEFORE absorption now: in the single-solve
        # order absorb runs pre-solve, and if it ran on the raw junction
        # set it dissolved nearly every rect against transient
        # apron-territory residue still tagged ``junction`` (CYXY 21->0,
        # SPJC 74->3).  Reclassifying first converts that residue to
        # ROLE_APRON so absorb only targets genuine final junctions.
        # Under scorer enactment the LEGACY ROLE-DECIDING CHAIN IS
        # DISABLED (owner 2026-07-28: "To test if the new system
        # actually works, we need to disable the legacy system") — the
        # scorer is the only classifier.  Shape-making (slice, carve,
        # neck split) and geometry hygiene (welds, deconfliction,
        # airside/groundside separation) still run.
        from .config import PAVEMENT_SCORE_V2 as _PS_MODE
        _scorer_owns_roles = _PS_MODE == "on"
        if not _scorer_owns_roles:
            from .junction_repair import _reclassify_apron_junctions
            _reclassify_apron_junctions(layout, icao=icao)
            _covp(layout, "post-apron-reclass")
        # (s79) SERVICE-JUNCTION re-role (docs/service_road_carve.md):
        # a junction OR apron whose pavement neighbours are EXCLUSIVELY
        # ``service_road`` rects (the #198 U-turn bulge between the two
        # road legs; the HECA SVC29↔SVC30 connector #336; the HECA
        # SVC29/35/36 plaza #290 that reads as an apron) is road
        # territory — road-cap ``service_junction``, not a 1.5 % aircraft
        # junction/apron.  A shape shared with any aircraft pavement (the
        # road's mouth at taxiway S) stays its original role.
        #
        # ★ MUST run BEFORE the runway-disconnected→groundside pass
        # below: that pass excludes service roads from its airside
        # connectivity graph, so a road-only junction/apron reads
        # "runway-disconnected" and is demoted to DEM groundside before
        # this re-role can claim it — leaving the road runs split by a
        # DEM blob they cannot grade through (the HECA #336 cliff between
        # SVC29 and SVC30; the #290/#312 plaza severed from its SVC roads
        # by the 1 m groundside clearance gap).  Re-roling first makes it
        # a ``service_junction`` (excluded from that pass) so the road
        # network grades continuously across it.  An APRON only qualifies
        # when it touches NO aircraft pavement at all — a real aircraft
        # apron always chains to a taxiway/stub/building, so the guard
        # claims only genuine road plazas.
        if SERVICE_ROAD_CARVE and not _scorer_owns_roles:
            from .layout import ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD
            _aircraft_roles = {
                ROLE_RUNWAY, "primary_parallel", "secondary_parallel",
                ROLE_STUB, "cross_connector", "apron", "building"}
            _n_svc_j = _n_svc_r = 0
            for _ji, _js in enumerate(layout.shapes):
                if _js.role not in ("junction", "apron") \
                        or _js.polygon is None or _js.polygon.is_empty:
                    continue
                _has_road = _has_aircraft = False
                _road_neighbors = 0
                for _os9 in layout.shapes:
                    if _os9 is _js or _os9.polygon is None \
                            or _os9.polygon.is_empty:
                        continue
                    if _os9.role not in _aircraft_roles \
                            and _os9.role != ROLE_SERVICE_ROAD:
                        continue
                    try:
                        if _js.polygon.distance(_os9.polygon) > 0.2:
                            continue
                    except _GEOM_EXC:
                        continue
                    if _os9.role == ROLE_SERVICE_ROAD:
                        _has_road = True
                        _road_neighbors += 1
                    else:
                        _has_aircraft = True
                        break
                # A service road is NARROW (< 15 m wide, user 2026-06-26): only a
                # narrow road/connector piece becomes a service_junction; a WIDE
                # road-only residue (a parking lot carved beside the road — CYXY
                # the 31×61 m piece @(-473,403)) is NOT road, it stays apron/
                # junction (→ groundside if runway-disconnected) so the lot is one
                # surface, not split into a road-cap plaza + DEM groundside (cliff).
                _narrow = True
                if os.environ.get("O4_SVC_REROLE_NARROW_ONLY", "1") == "1":
                    try:
                        _narrow = _js.polygon.buffer(-7.5).is_empty
                    except _GEOM_EXC:
                        _narrow = True
                if _has_road and not _has_aircraft and _narrow:
                    # A piece that is the sole extension of ONE road is a CONNECTOR
                    # corridor → ``service_road`` (grades AXIALLY, a ramp toward DEM).
                    # ≥2 roads meeting = a real INTERSECTION → all-pair
                    # ``service_junction`` (user 2026-06-27).  A piece that links a
                    # road to a GROUNDSIDE lot is also a connector, but groundside is
                    # not emitted yet here — caught by the post-emit pass below.
                    if _road_neighbors == 1:
                        _js.role = ROLE_SERVICE_ROAD
                        _n_svc_r += 1
                    else:
                        _js.role = ROLE_SERVICE_JUNCTION
                        _n_svc_j += 1
            if _n_svc_j or _n_svc_r:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: re-roled road-only junction/apron(s) "
                    f"→ {_n_svc_r} service_road + {_n_svc_j} service_junction.")

        # ── FULL-WIDTH SERVICE CORRIDOR consolidation, pass 1 ────────
        # (user 2026-07-05 full-width corridor): a service road is ONE
        # corridor — the truck-route spine has pavement on BOTH sides
        # and the two half-strips are the same surface.  The slice cut
        # each road in half along its own spine and the carve/re-role
        # passes left along-route fragment chains; merge them into
        # full-width corridor pieces NOW, before the road-lot /
        # runway-disconnection classifiers below, so any conversion of
        # road pavement to groundside decides over the full-width slab
        # (whole-shape membership on a full-width shape), never a
        # half-strip notch.  Gate O4_FULL_WIDTH_SERVICE_CORRIDOR.
        from .groundside import consolidate_full_width_service_corridors
        _n_fw = consolidate_full_width_service_corridors(layout)
        if _n_fw:
            UI.vprint(1,
                f"  [pav-builder] {icao}: consolidated service-corridor "
                f"fragments into full-width corridor(s) "
                f"(−{_n_fw} shape(s)).")
            _covp(layout, "post-full-width-corridor-1")

        # A wide paved LOT reachable only via a service road is landside —
        # ONE groundside surface, not a road carved through it.  The
        # on-pavement 1206 carve shreds such a lot into a service_road rect
        # + narrow service_junction frames (CYXY 'Crew cars' loops the lot
        # rim); each fragment is individually narrow so the wide-lot guard
        # in the re-role above never fires.  This runs AFTER that re-role
        # (so the frames are already service_junction) and BEFORE the
        # runway-disconnected pass below (so the merged lot can grade as
        # groundside): a morphological opening on each connected service
        # component extracts the 2-D lot core and reclassifies it to
        # groundside, leaving the narrow connector strips as service_road.
        from .config import ROAD_ONLY_LOT_GROUNDSIDE
        _covp(layout, "pre-road-lots")
        if ROAD_ONLY_LOT_GROUNDSIDE and not _scorer_owns_roles:
            from .junction_repair import (
                _reclassify_road_only_lots_to_groundside)
            _reclassify_road_only_lots_to_groundside(
                layout, icao=icao, dem=dem,
                tile_lat=tile_lat, tile_lon=tile_lon)

        # ── PAVEMENT CLASSIFICATION v1 (owner rulings 2026-07-26) ──
        # ``apron`` is the geometry phase's FALLBACK bucket, so a pack
        # that draws LANDSIDE pavement (perimeter roads, car parks,
        # terminal frontage) as ordinary pavement puts all of it under
        # the airside 1.5 % apron law and flattens the terrain relief
        # beneath it — HECA: 251 shapes / 904,433 m², mean 5.35 m of
        # grading damage, worst +21 m.  This pass votes on POSITIVE
        # evidence (OSM aeroway backing vs the airport-region road
        # feed's corridors) and demotes what is landside; a shape that
        # is BOTH (a real apron with a 5 km road tail) is cut at the
        # mouth where the corridor leaves the body, the body keeping
        # apron.  See ``config.PAVEMENT_CLASS_V1`` and the module
        # docstring for the two rulings (R-VETO / R-SPLIT).
        #
        # ★ ORDER: AFTER ``_reclassify_apron_junctions`` (the apron set
        # is settled — this classifier must see the final aprons, not
        # junction residue) and BEFORE the runway-disconnected pass
        # below, so a demotion SEVERS the touch-chain and whatever the
        # demotion orphans is picked up by that existing cascade in the
        # same build rather than being left airside behind a landside
        # blob.
        from .config import PAVEMENT_CLASS_V1, PAVEMENT_SCORE_V2
        if PAVEMENT_SCORE_V2 == "on":
            # Phase B ENACTMENT no longer runs in this slot — it moved
            # AFTER the neck-split / route-proximity geometry (CYXY
            # ground truth 2026-07-28: verdicts enacted on pre-split
            # blobs were inherited by split-off corridors whose own
            # features contradict them; old #100/#25/#105 read APRON
            # from their parent blob while scoring TAXI on their final
            # geometry).  See the enact call below merge-fragments.
            pass
        elif PAVEMENT_CLASS_V1:
            from .pavement_classification import classify_pavement_v1
            classify_pavement_v1(layout, icao=icao, dem=dem,
                                 tile_lat=tile_lat, tile_lon=tile_lon)
            _covp(layout, "post-pavement-class")

        # An apron must have a touch-chain back to a runway (user
        # 2026-06-09); pavement islands without one are landside ramps /
        # parking → groundside (4 %).  MUST run before tile_cut: the
        # tile clip severs cross-tile chains and would false-positive
        # legitimately connected aprons.  Runs AFTER the service-junction
        # re-role above so road-only junctions are already ``service_
        # junction`` (excluded here) rather than being demoted to a DEM
        # groundside blob that splits the road network.
        _covp(layout, "post-road-lots")
        if PAVEMENT_SCORE_V2 != "on":
            # Under enactment the scorer's G-CHAIN owns this law and its
            # own orphan sweep handles the severing cascade; the later
            # service-adjacency-scoped reruns still run (orphan hygiene
            # for the neck-split / carve, which happen after the slot).
            from .junction_repair import (
                _reclassify_runway_disconnected_to_groundside)
            _reclassify_runway_disconnected_to_groundside(
                layout, icao=icao, dem=dem,
                tile_lat=tile_lat, tile_lon=tile_lon)
            _covp(layout, "post-rwy-disconnected")

        # (2026-07-29) The sloping-edge absorption chain
        # (ABSORB_RECTS_ALONGSIDE_APRONS, default OFF since session 47)
        # and the final Rule-2 sloping-edge snap were retired with the
        # rect machinery.

        # (session 51) The boundary→DEM bridge re-emit moved POST-solve
        # into the feature-emit phase below — bridges (like the boundary
        # ribbon and groundside) now emit ONCE, after the single solve,
        # against the fully-settled pavement profile.

        # Per user 2026-05-10: shapes cannot cross integer lat/lon
        # tile boundaries (X-Plane / Ortho4XP render each 1°x1° tile
        # separately).  Cut a 10 m gap along every tile boundary
        # line that passes through the airport's pavement footprint;
        # Ortho4XP + X-Plane stitch the seam at render time.
        from .tile_cut import cut_layout_at_tile_boundaries
        n_tile_delta = cut_layout_at_tile_boundaries(
            layout,
            current_tile_lat=current_tile_lat,
            current_tile_lon=current_tile_lon,
            dem=dem,
        )

        # THE single per-surface solver pass (session 51) — runs ONCE,
        # against the FULLY-FINALIZED geometry (all stitch / split /
        # absorb / reclassify / Rule-2 / tile_cut passes above have
        # settled, and every one is de-coupled from altitudes).  The
        # solver seeds soft nodes from the DEM, HARD-anchors runway +
        # seam vertices, and writes one elevation per shared bucket, so
        # the result is grade-compliant AND lossless at shared corners
        # with nothing left to reconcile afterward.
        #
        # Post-cut tile-edge vertices sit at ``half_width_m`` offset
        # from the integer seam line (5 m by default).  The seam
        # vertex itself was removed by the cut; the new vertex is
        # NOT a seam anchor — both this tile's auto_patch and the
        # adjacent tile's auto_patch independently pick altitudes
        # for their own (offset) boundary vertices, and Ortho4XP's
        # terrain mesh interpolates across the 10-m gap at render
        # time.  So the final solver pass is free to cap-project
        # post-cut boundary vertices toward grade compliance.
        # (session 51 per user 2026-05-27) Apron neck-split — split large
        # apron polygons at their narrow necks (taxi-width arm mouths) into
        # convex pads joined by connectors.  Runs at geometry-FINAL (right
        # before the single solve) so the mouth-pair vertices added by
        # stitches / snaps / conformance are all in the ring; running this
        # earlier (in junction_emit) missed many user-expected mouths
        # because one endpoint of each pair wasn't yet a ring vertex.
        from .config import ENABLE_APRON_NECK_SPLIT
        if ENABLE_APRON_NECK_SPLIT:
            from .pavement.apron_necks import split_polygon_at_necks
            from .layout import ROLE_APRON as _R_APRON, BuiltShape as _BS
            # Piece-role re-evaluation for RECLASSIFIED parents (user
            # 2026-07-06): ``_reclassify_apron_junctions`` flips a whole
            # junction to apron when ANY boundary corner strays past the
            # 55 m cap — a 53 k m² spine corridor with one distant bulge
            # (HECA 30.1143,31.4157) flips entirely, and the neck-split
            # pieces inherited apron unconditionally, so strings of
            # corridor cells along the spine emitted under the stand-apron
            # law.  Re-test each piece of a FLIPPED parent with the same
            # geometry rule (``_reeval_apron_piece_role``, promotion-only):
            # pieces hugging a centerline return to ROLE_JUNCTION; open
            # pavement beyond route reach stays apron.  Born-apron parents
            # are NOT re-tested (a genuine stand apron beside a taxiway
            # must keep the apron law).
            from .junction_repair import (
                _aeroway_centerlines_union,
                _reeval_apron_piece_role,
                _APRON_RECLASSIFY_MAX_DISTANCE_M as _RECLASS_CAP_M)
            _reeval_centerlines = None       # computed lazily, once
            _split_count = 0
            _n_piece_promoted = 0
            _new_shapes: list = []
            # Under scorer-owns, JUNCTION blobs split too (owner CYXY
            # #105, 2026-07-28): before enactment the raw slice roles
            # stand, so a mixed apron+taxiway-loop blob is still tagged
            # ``junction`` here and the apron-only filter skipped it —
            # enactment then scored the WHOLE blob and the "Ramp" name
            # made 36 k m² of taxiway loop an apron.  The split is pure
            # geometry; enact (which now runs after) scores each piece.
            # SERVICE_JUNCTION blobs likewise (owner CYXY #64,
            # 2026-07-28 round 6): the building2 lot+frontage blob was
            # born service_junction, skipped every splitter, and its
            # 4.8 m neck at the building corner — the owner's expected
            # cut — never fired; enactment then re-classed the whole
            # blob as one piece.
            from .layout import (ROLE_JUNCTION as _R_JCT_SPLIT,
                                 ROLE_SERVICE_JUNCTION as _R_SVJ_SPLIT)
            _splittable = ({_R_APRON, _R_JCT_SPLIT, _R_SVJ_SPLIT}
                           if _scorer_owns_roles else {_R_APRON})
            for _s in layout.shapes:
                if (_s.role not in _splittable or _s.polygon is None
                        or _s.polygon.is_empty
                        or _s.polygon.geom_type != "Polygon"):
                    _new_shapes.append(_s)
                    continue
                _pieces = split_polygon_at_necks(_s.polygon)
                if len(_pieces) <= 1:
                    _new_shapes.append(_s)
                    continue
                _split_count += 1
                for _p in _pieces:
                    # apron/junction pieces take the historical apron
                    # default (enact re-scores them); a service parent's
                    # pieces keep the service role — flipping them to
                    # apron would hand them to apron-only passes their
                    # evidence never earned.
                    _piece_role = (_R_APRON if _s.role != _R_SVJ_SPLIT
                                   else _R_SVJ_SPLIT)
                    if getattr(_s, "reclassified_from_junction", False):
                        if _reeval_centerlines is None:
                            _reeval_centerlines = \
                                _aeroway_centerlines_union(layout)
                        _piece_role = _reeval_apron_piece_role(
                            _p, _reeval_centerlines, _RECLASS_CAP_M)
                        if _piece_role != _R_APRON:
                            _n_piece_promoted += 1
                    _ns = _BS(polygon=_p, role=_piece_role, ref=_s.ref)
                    _new_shapes.append(_ns)
            if _split_count:
                layout.shapes = _new_shapes
                _promo_note = (f"; {_n_piece_promoted} corridor piece(s) "
                               f"re-evaluated back to junction"
                               if _n_piece_promoted else "")
                UI.vprint(1,
                    f"  [pav-builder] {icao}: neck-split "
                    f"{_split_count} apron(s) at geometry-final"
                    f"{_promo_note}.")
            # APRON ROUTE-PROXIMITY CUT (USER RULING 2026-07-06): "the
            # portion of any shape more than 50 m from a centerline or
            # runway COULD be apron, but anything less than 50 m from a
            # centerline or runway is NOT apron."  Every ROLE_APRON shape
            # is cut at the config.APRON_ROUTE_PROXIMITY_M contour around
            # the taxi centerlines (service/truck routes excluded — a
            # stand is legitimately served by a road) and the runway
            # union: the near band becomes ROLE_JUNCTION (maneuvering
            # surface, taxi law), the far part keeps the apron/stand law.
            # "No apron ever touches a runway" follows as a corollary.
            # An apron entirely inside the zone re-roles whole; entirely
            # outside stays whole.  Mitre joins / flat caps keep the cut
            # boundary arc-free (same reason as the groundside clip).
            from .config import (APRON_ROUTE_PROXIMITY_M,
                                 APRON_ROUTE_THROUGH_MIN_LEN_M)
            from .layout import ROLE_JUNCTION as _R_JCT_NEAR
            _near_zone = None
            try:
                _zone_parts = []
                _rwy_union = getattr(layout, "runway_union", None)
                _candidate_lines = []
                for _cl_item in (getattr(layout, "apt_taxi_centerlines",
                                         None) or []):
                    if getattr(_cl_item, "is_service", False):
                        continue
                    _ln = (getattr(_cl_item, "chained_line", None)
                           or getattr(_cl_item, "line", None))
                    if _ln is not None and not _ln.is_empty:
                        _candidate_lines.append(_ln)
                # THROUGH-ROUTES ONLY (KCLT terminal regression,
                # 2026-07-06): a gate LEAD-IN taxilane dead-ends on the
                # stand it serves — counting it toward the 50 m zone
                # makes every stand "near-route" (KCLT: 63 stand aprons
                # re-roled whole; the apron-island merges then lost
                # their hosts and the terminal ramp demoted to DEM
                # groundside).  A centerline joins the zone only when
                # EACH end either joins another taxi centerline or
                # reaches the runway union — dead-end spurs are the
                # stand's own territory, not the movement network.
                _JOIN_TOL_M = 2.0
                _taxi_union = None
                _taxi_lines = []
                for _k1, _ln in enumerate(_candidate_lines):
                    try:
                        _ends = (Point(*_ln.coords[0]),
                                 Point(*_ln.coords[-1]))
                    except Exception:
                        continue
                    _through = True
                    for _end in _ends:
                        _joined = (
                            _rwy_union is not None
                            and not _rwy_union.is_empty
                            and _rwy_union.distance(_end) <= _JOIN_TOL_M)
                        if not _joined:
                            for _k2, _other in enumerate(_candidate_lines):
                                if _k2 == _k1:
                                    continue
                                if _other.distance(_end) <= _JOIN_TOL_M:
                                    _joined = True
                                    break
                        if not _joined:
                            _through = False
                            break
                    # LENGTH BACKSTOP (owner ruling 2026-07-26, KCLT
                    # taxiway U): a route whose tips both die inside
                    # apron pavement fails the join test yet IS the
                    # movement network when it is hundreds of metres
                    # long — admit it so the cut can free the neck it
                    # runs through.  Gate lead-ins stay excluded (tens
                    # of metres, far under the floor).
                    if _through or _ln.length >= \
                            APRON_ROUTE_THROUGH_MIN_LEN_M:
                        _taxi_lines.append(_ln)
                if _taxi_lines:
                    _taxi_union = unary_union(_taxi_lines)
                    _zone_parts.append(_taxi_union.buffer(
                        APRON_ROUTE_PROXIMITY_M, cap_style=2,
                        join_style=2))
                if _rwy_union is not None and not _rwy_union.is_empty:
                    _zone_parts.append(_rwy_union.buffer(
                        APRON_ROUTE_PROXIMITY_M, join_style=2))
                if _zone_parts:
                    _near_zone = unary_union(_zone_parts)
            except _GEOM_EXC:
                _near_zone = None
            _n_cut = _n_whole = 0
            if (_near_zone is not None and not _near_zone.is_empty
                    and not _scorer_owns_roles):
                _cut_shapes: list = []
                for _s in layout.shapes:
                    if (_s.role != _R_APRON or _s.polygon is None
                            or _s.polygon.is_empty
                            or _s.polygon.geom_type != "Polygon"):
                        _cut_shapes.append(_s)
                        continue
                    try:
                        _far = _s.polygon.difference(_near_zone)
                    except _GEOM_EXC:
                        _cut_shapes.append(_s)
                        continue
                    _far_polys = [g for g in getattr(
                        _far, "geoms", [_far])
                        if g.geom_type == "Polygon" and g.area > 1.0]
                    if not _far_polys:
                        # wholly inside the zone → maneuvering surface
                        _s.role = _R_JCT_NEAR
                        _cut_shapes.append(_s)
                        _n_whole += 1
                        continue
                    if sum(g.area for g in _far_polys) \
                            >= _s.polygon.area - 1.0:
                        _cut_shapes.append(_s)      # wholly beyond → apron
                        continue
                    try:
                        _near_part = _s.polygon.intersection(_near_zone)
                    except _GEOM_EXC:
                        _cut_shapes.append(_s)
                        continue
                    _near_polys = [g for g in getattr(
                        _near_part, "geoms", [_near_part])
                        if g.geom_type == "Polygon" and g.area > 1.0]
                    # NEAR-PIECE ROUTE-CONTENT TEST (owner ruling
                    # 2026-07-26; CYXY shape 132): the 50 m contour can
                    # slice off an annulus band of an apron that no taxi
                    # route ever enters — a pure geometric artifact that
                    # then grades under taxi law with a hard edge against
                    # its own apron.  A split near-piece re-roles to
                    # junction only when a through taxi centerline
                    # actually enters it, or it genuinely lies inside the
                    # runway proximity zone (preserving the "no apron
                    # ever touches a runway" corollary); otherwise it is
                    # merged back into the apron side of the cut.
                    _kept_near: list = []
                    _rejected_near: list = []
                    for _g in _near_polys:
                        _has_route = (
                            _taxi_union is not None
                            and _g.intersection(_taxi_union).length > 0.0)
                        if (not _has_route and _rwy_union is not None
                                and not _rwy_union.is_empty):
                            _has_route = (_g.distance(_rwy_union)
                                          <= APRON_ROUTE_PROXIMITY_M)
                        if _has_route:
                            _kept_near.append(_g)
                        else:
                            _rejected_near.append(_g)
                    if not _kept_near:
                        # every near-piece was an artifact → the apron
                        # stays whole (original shape, uncut)
                        _cut_shapes.append(_s)
                        continue
                    if _rejected_near:
                        try:
                            _far_merge = unary_union(
                                _far_polys + _rejected_near)
                        except _GEOM_EXC:
                            _far_merge = None
                        if _far_merge is not None:
                            _far_polys = [g for g in getattr(
                                _far_merge, "geoms", [_far_merge])
                                if g.geom_type == "Polygon"
                                and g.area > 1.0]
                    for _g in _kept_near:
                        _cut_shapes.append(_BS(
                            polygon=_g, role=_R_JCT_NEAR, ref=_s.ref,
                            from_route_proximity_cut=True))
                    for _g in _far_polys:
                        _cut_shapes.append(_BS(
                            polygon=_g, role=_R_APRON, ref=_s.ref,
                            from_route_proximity_cut=True))
                    _n_cut += 1
                    if os.environ.get("O4_SLIVER_DEBUG") == "1":
                        _c = _s.polygon.representative_point()
                        print(f"    [apron-cut] area="
                              f"{_s.polygon.area:.0f} at ({_c.x:.0f},"
                              f"{_c.y:.0f}) -> {len(_near_polys)} "
                              f"junction + {len(_far_polys)} apron "
                              f"piece(s)")
                layout.shapes = _cut_shapes
            if _n_cut or _n_whole:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: apron route-proximity cut "
                    f"— {_n_cut} apron(s) split at the "
                    f"{APRON_ROUTE_PROXIMITY_M:.0f} m contour, "
                    f"{_n_whole} re-roled whole (inside the zone).")

        # Reclassify-to-apron + neck-split (above) run AFTER the
        # mid-finalize overlap-clip, so they can leave aprons overlapping
        # junctions / each other (HECA dense S/T/W/J/R cluster).  Resolve
        # those here, BEFORE the final solve, so the solver derives clean
        # node_altitudes for the clipped pieces (pure geometry pass).
        from .elevation import _drop_overlap_against_fixed_shapes
        _drop_overlap_against_fixed_shapes(
            layout, icao=icao, include_aprons=True)

        # Phase B ENACTMENT (owner approval 2026-07-28; scorer-owns-
        # roles — the legacy role chain is gated off throughout).  Runs
        # HERE, after the neck-split and the overlap clip, so verdicts
        # apply to the FINAL geometry: enacting in the old v1 slot let
        # later splits inherit a mixed parent blob's role against their
        # own evidence (CYXY old #100/#25/#105).  Before merge-
        # fragments and groundside emission, both of which read roles.
        if PAVEMENT_SCORE_V2 == "on":
            from .pavement_scoring import enact_classify
            enact_classify(layout, icao=icao, dem=dem,
                           tile_lat=tile_lat, tile_lon=tile_lon,
                           xplane_root=xplane_root)
            _covp(layout, "post-pavement-score")

        # (user 2026-06-03) Fold small apron fragments fully enclosed by apron/
        # terminal into their larger neighbour BEFORE the solve — the fragment's
        # edges/elevation disappear and the solver grades the unified apron, so
        # there is no post-solve step to reconcile (a post-solve merge just
        # relocated the cliff).  Runs AFTER the overlap-clip, which itself
        # creates small clipped apron fragments.  Hole-slice safe.
        _covp(layout, "pre-apron-frag-merge")
        from .groundside import merge_small_apron_fragments
        _n_frag = merge_small_apron_fragments(layout)
        if _n_frag:
            UI.vprint(1,
                f"  [pav-builder] {icao}: merged {_n_frag} small apron "
                f"fragment(s) into their host apron (pre-solve).")

        # ── Boundary-interior clip: RETIRED (user 2026-07-16) ─────────
        # The "no shape may straddle the row-130 boundary" invariant
        # (user 2026-05-22) served the boundary RIBBON: straddling
        # pavement was clipped back to the ribbon's inner edge so the
        # two tiled conformingly.  The adjacent-ground law superseded
        # the ribbon (nothing emits ROLE_BOUNDARY shapes any more), and
        # the clip actively harmed features that legitimately live
        # across the line — EGPB's tunnel-ramp chain straddled row-130
        # and the nearest-neighbour altitude resample flattened its
        # sloped rects into a hump.  Shapes now simply keep their
        # geometry wherever they land relative to row-130.

        # ── Groundside emit + absorb/reclassify (refactor Phase 4, PRE-solve) ─
        # Emit groundside pavement (DEM-following, solve-INDEPENDENT — the
        # per-surface solver only grades PAVEMENT_ROLES and is blind to
        # groundside), then settle the airside↔groundside role boundary
        # BEFORE the solve:
        #   * ``_absorb_apron_enclosed_groundside`` folds apron-enclosed
        #     groundside back into the bordering apron (node-shared MERGE), so
        #     the solver grades it as part of the apron — the apron-island
        #     flat-vs-graded cliff is gone at the source instead of being
        #     relocated by a post-solve merge.
        #   * ``_reclassify_groundside_orphan_junctions`` re-tags junctions
        #     that touch ONLY groundside as DEM groundside (the solver then
        #     ignores them) — no airside-flat-vs-DEM cliff at their seam.
        # The groundside DEM-altitude is final here; the post-solve
        # ``_separate_groundside_from_airside`` still opens the clearance gap
        # against the FINAL airside geometry.
        from .groundside import (
            _emit_groundside_pavement_dem as _emit_gs_dem,
            _absorb_apron_enclosed_groundside as _absorb_gs,
            _reclassify_groundside_orphan_junctions as _reclass_gs)
        try:
            _n_gs = _emit_gs_dem(layout, dem, tile_lat, tile_lon)
            if _n_gs:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: emitted {_n_gs} groundside "
                    f"pavement polygon(s) with DEM altitudes (pre-solve).")
        except _GEOM_EXC:
            pass
        _covp(layout, "post-groundside-emit")
        try:
            _n_abs = 0 if _scorer_owns_roles else _absorb_gs(layout)
            if _n_abs:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: absorbed {_n_abs} airside-wedged "
                    f"piece(s) back into apron (pre-solve).")
        except _GEOM_EXC:
            pass
        try:
            _n_orph = (0 if _scorer_owns_roles
                       else _reclass_gs(layout, dem, tile_lat, tile_lon))
            if _n_orph:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: reclassified {_n_orph} "
                    f"groundside-orphan junction(s) as DEM pavement (pre-solve).")
        except _GEOM_EXC:
            pass

        # LOT-CARRIED SERVICE ROADS → service_road (owner ruling
        # 2026-08-30, HECA round 6 item 3).  The SCOPED sever: where an
        # OSM service road shares a vertex with the groundside ring at
        # 11-dp identity, the lot was built around the road and is
        # merely carrying it — the corridor leaves the lot and grades
        # under the merged free-road ramp law.  Runs HERE, right after
        # groundside is emitted and well before the solve, so the
        # severed corridor is a road for the whole of phase 2.  §H3's
        # road-EVIDENCE severance stays refuted and off; this trigger is
        # an identity, not a coverage fraction.
        try:
            from .groundside import sever_lot_carried_service_roads
            sever_lot_carried_service_roads(layout, dem, tile_lat, tile_lon)
        except _GEOM_EXC:
            pass

        # GROUNDSIDE ROUTE CORRIDORS → service_road (user 2026-07-04, CYXY
        # #206): an OSM-captured groundside piece that IS a truck-route
        # road corridor (route runs through it end-to-end) grades as a
        # ROAD along its route, never as a re-levelled destination lot.
        # Under scorer enactment the SERVICE-vs-GROUNDSIDE call is the
        # scorer's (truck/road threading + the road_narrow ruling).
        if PAVEMENT_SCORE_V2 != "on":
            try:
                from .groundside import (
                    reclassify_groundside_route_corridors)
                _n_corr = reclassify_groundside_route_corridors(layout)
                if _n_corr:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: re-roled {_n_corr} "
                        f"groundside route-corridor piece(s) → service_road "
                        f"(rides a truck route).")
            except _GEOM_EXC:
                pass

        # GROUNDSIDE-CONNECTOR re-role (user 2026-06-27): a narrow service_junction
        # that links a service road to a groundside lot is a CONNECTOR corridor, not
        # an intersection — re-role it ``service_road`` so it grades AXIALLY (a ramp
        # toward DEM).  Runs HERE, after groundside is emitted, because the earlier
        # service-junction re-role cannot see groundside (not emitted yet).
        if not _scorer_owns_roles:
            from .layout import (ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD,
                                 ROLE_GROUNDSIDE_PAVEMENT)
            _gs_polys = [g.polygon for g in layout.shapes
                         if g.role == ROLE_GROUNDSIDE_PAVEMENT
                         and g.polygon is not None and not g.polygon.is_empty]
            _n_cr = 0
            for _sj in layout.shapes:
                if (_sj.role != ROLE_SERVICE_JUNCTION or _sj.polygon is None
                        or _sj.polygon.is_empty):
                    continue
                try:
                    if any(_sj.polygon.distance(_gp) <= 0.2 for _gp in _gs_polys):
                        _sj.role = ROLE_SERVICE_ROAD
                        _n_cr += 1
                except _GEOM_EXC:
                    continue
            if _n_cr:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: re-roled {_n_cr} groundside-connector "
                    f"service_junction(s) → service_road (axial ramp).")

        # ── R7b CLAUSE 3 — PARALLEL FRONTAGE CUTS BACK TO DEM (owner
        # ruling 2026-08-15 late, the sink ruling; Fable amendment A2).
        # "A road running PARALLEL to an apron for more than 1.5x the
        # road's width takes the STANDARD GROUNDSIDE CUTBACK and stays
        # AT DEM — at CYXY the landside frontage road is a second-story
        # level several metres above the airside apron; that separation
        # is real and must be preserved, not welded away."  The cutback
        # is GEOMETRIC and reuses ``_separate_groundside_from_airside``'s
        # own clearance buffer, mouth windows and DEM re-follow.
        # HERE, PRE-SOLVE and explicitly, for two reasons: the road must
        # stop sharing nodes with the apron BEFORE the solve can weld
        # them, and a road cut back POST-solve would lose the solved road
        # field (the opposite of "stays at DEM").  Runs after the
        # connector re-roles (roles final) and before the mouth
        # conformance below, which must see the road's final ring.
        # DEFAULT OFF (Fable adjudication 2026-08-15 late): the cutback
        # bought neither CYXY witness (both byte-identical in the
        # R7a-only arm; the frontage site carries zero road-airside
        # shared nodes) and cost +286 HECA / +76 SPJC through the
        # unlimited-road-chord gap. It re-arms (=1) when the road
        # chord limiter lands (wave 3: extend
        # _grade_limit_groundside_chords to the road roles under the
        # standing roads-like-taxiways ruling).
        # ``O4_ROAD_FRONTAGE_CUTBACK=1`` is the arm switch AND the
        # attribution instrument: with it off the round's R7a half runs
        # alone, so a census delta can be split between the two clauses
        # without arguing about it.
        if dem is not None and os.environ.get(
                "O4_ROAD_FRONTAGE_CUTBACK", "0") == "1":
            try:
                from .groundside import (
                    _separate_groundside_from_airside as _sep_road_frontage)
                _sep_road_frontage(layout, dem, tile_lat, tile_lon,
                                   road_frontage_cutback=True,
                                   groundside_clip=False)
            except _GEOM_EXC:
                pass

        # The road↔lot connection is FIRST-CLASS shared geometry (user
        # 2026-07-04, CYXY P4): insert shared vertices into groundside
        # lot rings at every service-shape mouth so the two emit welded
        # nodes and the groundside mouth-anchor weld binds by canonical
        # key (a mouth landing mid-edge on the lot ring had no key to
        # weld to, and the road emitted 3.1 m below the lot it serves).
        from .groundside import conform_service_mouths_to_groundside
        _n_mouth = conform_service_mouths_to_groundside(layout)
        if _n_mouth:
            UI.vprint(1,
                f"  [pav-builder] {icao}: conformed {_n_mouth} service-road "
                f"mouth vertex(es) into groundside lot ring(s).")
        # Parallel service roads within 2 m get matching projected
        # vertices so the DEM-follow's proximity coupling can bind them
        # (user 2026-07-06, HECA #578↔#64: offset nodes left a 0.9 m
        # mid-edge wall across a 1 m gap).
        from .groundside import conform_parallel_service_edges
        _n_parallel = conform_parallel_service_edges(layout)
        if _n_parallel:
            UI.vprint(1,
                f"  [pav-builder] {icao}: conformed {_n_parallel} "
                f"parallel service-road vertex(es) across narrow gaps.")

        # LATERAL-CONTIGUITY GRADE LAW (owner-confirmed FINAL 2026-08-02,
        # docs/RULINGS.md).  When its gate is on, this ONE pass replaces
        # the two proximity-band adoption passes below: they are the same
        # ruling in its earlier form (apron-only 2026-07-06, taxi-only
        # 2026-07-07, both delimited by a BUFFER band the owner has since
        # ruled out — "adjacency = literal shared boundary in the sliced
        # arrangement, never proximity"), and running both would cap the
        # same pieces twice.  Gate off ⇒ this returns immediately and the
        # two band passes run exactly as before.
        from .config import (
            LATERAL_CONTIGUITY_LAW_ENABLED as _LAT_LAW_ON)
        if _LAT_LAW_ON:
            from .groundside import apply_lateral_contiguity_law
            # MERGED-SURFACE LAWFULNESS (ruling 2026-08-03): a road stretch
            # absorbed into a groundside lot makes ONE surface, and the lot
            # emitter's own ramp-limited DEM follow is re-run over the
            # MERGED ring — which moves the host's pre-existing vertices,
            # lawfully, because the host is groundside and this is
            # groundside's law.  The sampler is only built when the
            # absorption gate is on, so the gate-off path is untouched.
            # (The earlier attempt — raw DEM for the NEW vertices only —
            # measured WORSE, CYXY within-shape 189 → 275; see
            # ``groundside.apply_lateral_contiguity_law``.)
            from .config import SERVICE_LOT_ABSORPTION as _ABSORB_ON
            _lat_dem_at = None
            if _ABSORB_ON:
                try:
                    from .groundside import _dem_sampler as _gs_dem_sampler
                    if layout.anchor is not None and dem is not None:
                        _lat_dem_at = _gs_dem_sampler(
                            layout, dem, tile_lat, tile_lon)
                except _GEOM_EXC:
                    _lat_dem_at = None
            try:
                apply_lateral_contiguity_law(layout, icao,
                                             dem_at=_lat_dem_at)
            except _GEOM_EXC as _lat_exc:
                UI.vprint(1, f"  [pav-builder] WARN: {icao}: "
                             f"lateral-contiguity law failed ({_lat_exc!r}) "
                             f"— pieces keep their own caps.")
            _covp(layout, "post-lateral-contiguity")

        # APRON-EDGE GRADE ADOPTION (USER RULING 2026-07-06, clarified):
        # "the portion of service road that is inside, or running along
        # the edge of an apron follows apron grading.  A service road
        # that leaves the apron ... the portion beyond the apron grades
        # at service road rules."  PORTION-based, like the 50 m cut:
        # eligible roads/junctions (≥ 1 m shared boundary with an apron)
        # are SPLIT at the apron-adjacency band contour — the band =
        # apron union buffered one road width (a road running alongside
        # adopts across its full width; a road leaving the apron exits
        # the band within ~a road width of the mouth).  Inside pieces
        # set ``adopts_apron_grade`` (solver caps + o4_grade_law tag);
        # outside pieces keep the service law.
        from .config import SERVICE_ROAD_WIDTH_M as _SVC_W_ADOPT
        from .layout import (ROLE_SERVICE_ROAD as _RSR_ADOPT,
                             ROLE_SERVICE_JUNCTION as _RSJ_ADOPT,
                             ROLE_APRON as _RAPR_ADOPT,
                             BuiltShape as _BS_ADOPT)
        _APRON_EDGE_BAND_M = float(_SVC_W_ADOPT) + 2.0
        _apron_polys_adopt = [
            _s.polygon for _s in layout.shapes
            if _s.role == _RAPR_ADOPT and _s.polygon is not None
            and not _s.polygon.is_empty
            and _s.polygon.geom_type == "Polygon"]
        _adopt_band = None
        if _apron_polys_adopt and not _LAT_LAW_ON:
            try:
                _adopt_band = unary_union(_apron_polys_adopt).buffer(
                    _APRON_EDGE_BAND_M, join_style=2)
            except _GEOM_EXC:
                _adopt_band = None
        _n_adopt_whole = _n_adopt_split = 0
        if _adopt_band is not None and not _adopt_band.is_empty:
            _adopt_boundary = unary_union(
                [_p.exterior for _p in _apron_polys_adopt])
            _adopt_shapes: list = []
            for _s in layout.shapes:
                if (_s.role not in (_RSR_ADOPT, _RSJ_ADOPT)
                        or _s.polygon is None or _s.polygon.is_empty
                        or _s.polygon.geom_type != "Polygon"):
                    _adopt_shapes.append(_s)
                    continue
                try:
                    _shares_edge = (
                        _s.polygon.exterior.distance(_adopt_boundary)
                        < 0.05
                        and _s.polygon.exterior.buffer(0.05)
                        .intersection(_adopt_boundary).length >= 1.0)
                except _GEOM_EXC:
                    _shares_edge = False
                if not _shares_edge:
                    _adopt_shapes.append(_s)
                    continue
                try:
                    _outside = _s.polygon.difference(_adopt_band)
                except _GEOM_EXC:
                    _adopt_shapes.append(_s)
                    continue
                _outside_polys = [g for g in getattr(
                    _outside, "geoms", [_outside])
                    if g.geom_type == "Polygon" and g.area > 1.0]
                if not _outside_polys:
                    # wholly inside/alongside the apron → adopts whole.
                    # GRADE only (owner 2026-07-28 round 9, CYXY
                    # #259/#264): the band is a PROXIMITY zone — a
                    # truck-route piece merely NEAR an apron is still
                    # the road; upgrading the ROLE here over-flipped
                    # threaded service pieces to apron.  Identity flips
                    # belong to the scorer's G-APRON-EDGE (real
                    # edge-binding) and reclass_building_faces
                    # (building airside faces).
                    _s.adopts_apron_grade = True
                    _adopt_shapes.append(_s)
                    _n_adopt_whole += 1
                    continue
                try:
                    _inside = _s.polygon.intersection(_adopt_band)
                except _GEOM_EXC:
                    _adopt_shapes.append(_s)
                    continue
                _inside_polys = [g for g in getattr(
                    _inside, "geoms", [_inside])
                    if g.geom_type == "Polygon" and g.area > 1.0]
                if not _inside_polys:
                    _adopt_shapes.append(_s)
                    continue
                for _g in _inside_polys:
                    # grade adoption only — see the whole-adopt note
                    # (owner 2026-07-28 round 9: role upgrades here
                    # over-flipped near-apron road pieces).
                    _adopt_shapes.append(_BS_ADOPT(
                        polygon=_g, role=_s.role, ref=_s.ref,
                        adopts_apron_grade=True,
                        from_route_proximity_cut=True))
                for _g in _outside_polys:
                    _adopt_shapes.append(_BS_ADOPT(
                        polygon=_g, role=_s.role, ref=_s.ref,
                        from_route_proximity_cut=True))
                _n_adopt_split += 1
            layout.shapes = _adopt_shapes
        if _n_adopt_whole or _n_adopt_split:
            UI.vprint(1,
                f"  [pav-builder] {icao}: apron-edge grade adoption — "
                f"{_n_adopt_whole} service shape(s) adopted whole, "
                f"{_n_adopt_split} split at the apron band (user rule).")

        # TAXIWAY-EDGE GRADE ADOPTION (USER RULING 2026-07-07, durable —
        # STATUS part 29 item 4): like the apron-edge rule, the PORTION of
        # a service road that is INSIDE, or SHARES A LONG EDGE with, a
        # TAXIWAY follows the more limiting (taxiway) grade law — 1.5 %
        # (letter-aware) instead of the road's own cap.  Only isolated narrow-
        # road stretches (nothing along their long edge) keep the full road
        # cap.  PORTION-based, split at the band exactly like the apron
        # rule.  The taxiway band = union of the taxi family (ROLE_JUNCTION
        # corridors + taxi rect roles) buffered one road width + 2 m; a road
        # running alongside adopts across its width; a road leaving exits the
        # band within ~a road width of the mouth.  APRON (1 %) is MORE
        # limiting than taxi (1.5 %), so a piece already adopting apron is
        # left untouched — this pass runs AFTER the apron pass and skips
        # apron-adopted shapes.
        from .layout import (taxi_shape_code_letter as _TAXI_LETTER,
                             ROLE_JUNCTION as _RJ_TX,
                             ROLE_PRIMARY_PARALLEL as _RPP_TX,
                             ROLE_SECONDARY_PARALLEL as _RSP_TX,
                             ROLE_STUB as _RSTUB_TX,
                             ROLE_CROSS_CONNECTOR as _RCC_TX)
        _TAXI_FAMILY_TX = frozenset({
            _RJ_TX, _RPP_TX, _RSP_TX, _RSTUB_TX, _RCC_TX})
        _TAXI_EDGE_BAND_M = float(_SVC_W_ADOPT) + 2.0
        _taxi_shapes_tx = [
            _s for _s in layout.shapes
            if _s.role in _TAXI_FAMILY_TX and _s.polygon is not None
            and not _s.polygon.is_empty
            and _s.polygon.geom_type == "Polygon"]
        _taxi_polys_tx = [_s.polygon for _s in _taxi_shapes_tx]
        _taxi_band = None
        if _taxi_polys_tx and not _LAT_LAW_ON:
            try:
                _taxi_union_tx = unary_union(_taxi_polys_tx)
                _taxi_band = _taxi_union_tx.buffer(
                    _TAXI_EDGE_BAND_M, join_style=2)
            except _GEOM_EXC:
                _taxi_band = None

        def _adjacent_taxi_letter(_road_poly):
            """ICAO code letter of the taxi shape this road hugs (nearest
            by boundary distance); None when unavailable → uniform 1.5 %."""
            _best_d, _best_let = float("inf"), None
            for _ts in _taxi_shapes_tx:
                try:
                    _d = _road_poly.distance(_ts.polygon)
                except _GEOM_EXC:
                    continue
                if _d < _best_d:
                    _best_d = _d
                    _best_let = _TAXI_LETTER(layout, _ts)
            return _best_let

        _n_taxi_whole = _n_taxi_split = 0
        if _taxi_band is not None and not _taxi_band.is_empty:
            _taxi_boundary = unary_union(
                [_p.exterior for _p in _taxi_polys_tx])
            _taxi_adopt_shapes: list = []
            for _s in layout.shapes:
                if (_s.role not in (_RSR_ADOPT, _RSJ_ADOPT)
                        or _s.polygon is None or _s.polygon.is_empty
                        or _s.polygon.geom_type != "Polygon"
                        # apron (1 %) already claimed this piece → keep it
                        or getattr(_s, "adopts_apron_grade", False)):
                    _taxi_adopt_shapes.append(_s)
                    continue
                try:
                    _shares_edge = (
                        _s.polygon.exterior.distance(_taxi_boundary)
                        < 0.05
                        and _s.polygon.exterior.buffer(0.05)
                        .intersection(_taxi_boundary).length >= 1.0)
                except _GEOM_EXC:
                    _shares_edge = False
                # INSIDE a taxiway (road overlapping taxi pavement) adopts
                # whole even if it shares no boundary edge.
                try:
                    _inside_taxi = (
                        _s.polygon.intersection(_taxi_union_tx).area > 1.0)
                except _GEOM_EXC:
                    _inside_taxi = False
                if not _shares_edge and not _inside_taxi:
                    _taxi_adopt_shapes.append(_s)
                    continue
                _let = _adjacent_taxi_letter(_s.polygon)
                try:
                    _outside = _s.polygon.difference(_taxi_band)
                except _GEOM_EXC:
                    _taxi_adopt_shapes.append(_s)
                    continue
                _outside_polys = [g for g in getattr(
                    _outside, "geoms", [_outside])
                    if g.geom_type == "Polygon" and g.area > 1.0]
                if not _outside_polys:
                    # wholly inside/alongside the taxiway → adopts whole
                    _s.adopts_taxi_grade = True
                    _s.adopted_taxi_letter = _let
                    _taxi_adopt_shapes.append(_s)
                    _n_taxi_whole += 1
                    continue
                try:
                    _inside = _s.polygon.intersection(_taxi_band)
                except _GEOM_EXC:
                    _taxi_adopt_shapes.append(_s)
                    continue
                _inside_polys = [g for g in getattr(
                    _inside, "geoms", [_inside])
                    if g.geom_type == "Polygon" and g.area > 1.0]
                if not _inside_polys:
                    _taxi_adopt_shapes.append(_s)
                    continue
                for _g in _inside_polys:
                    _taxi_adopt_shapes.append(_BS_ADOPT(
                        polygon=_g, role=_s.role, ref=_s.ref,
                        adopts_taxi_grade=True, adopted_taxi_letter=_let,
                        from_route_proximity_cut=True))
                for _g in _outside_polys:
                    _taxi_adopt_shapes.append(_BS_ADOPT(
                        polygon=_g, role=_s.role, ref=_s.ref,
                        from_route_proximity_cut=True))
                _n_taxi_split += 1
            layout.shapes = _taxi_adopt_shapes
        if _n_taxi_whole or _n_taxi_split:
            UI.vprint(1,
                f"  [pav-builder] {icao}: taxiway-edge grade adoption — "
                f"{_n_taxi_whole} service shape(s) adopted whole, "
                f"{_n_taxi_split} split at the taxi band (user rule).")

        # BUILDING-AIRSIDE-FACE re-role (owner 2026-07-28, SPJC #182:
        # "apron should always abut the airside side of buildings").
        # The adoption/carve splitters above run AFTER enactment and
        # mint service fragments the scorer never saw — any service
        # piece sharing a real edge with BOTH a building and aircraft
        # pavement is that building's airside frontage and becomes
        # apron.  Scorer-owns only (the legacy chain has its own laws).
        if _scorer_owns_roles:
            from .pavement_scoring import reclass_building_faces
            _n_face = reclass_building_faces(layout)
            if _n_face:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: building airside-face "
                    f"re-role — {_n_face} service piece(s) became "
                    f"apron (owner abutment ruling).")

        # (refactor Phase 5) The boundary ribbon + boundary→DEM bridge emit
        # and their airside vertex touches (_snap_bridge_vertices_to_runway_
        # corners, _insert_bridge_contacts_into_junctions) CANNOT move
        # pre-solve: the ribbon/bridge runway-distance clamp anchors to ALL
        # airside pavement (incl. aprons/taxiways, whose altitudes are only
        # known after the solve), so the bridge PLACEMENT is solve-dependent.
        # They stay post-solve; the bridge-contact insert is altitude-neutral
        # (collinear) and the post-solve feature conformance (Phase 7) keeps
        # the partition conforming without moving frozen airside vertices.

        # (refactor Phases 6+7) The partial pre-solve apron/junction
        # conformance is SUPERSEDED by the full airside node-unification
        # (_unify_airside_geometry) run below, just before the solve.

        # ── Pre-solve shape-drop passes (refactor Phase 2) ────────────
        # Drop small floating-orphan junctions left by
        # pav_union.difference(rects) — a wedge past a rect's edge that
        # shares no vertex with any shape (so no merge/sliver pass can
        # absorb it) and whose corners are all orphans (SPLP #33).  Pure
        # topology (area + shared-vertex test, no altitude dependency), so
        # it moved PRE-solve: the dropped wedge never enters the solver's
        # node graph or the weld/conformance node-set.
        from .junction_repair import _drop_floating_orphan_junctions
        _drop_floating_orphan_junctions(layout, icao=icao)

        # Drop small apron/junction residue that rests almost entirely OFF
        # the source pavement union — a thin strip beside a shoulder-widened
        # runway, or residue from a dropped runway-parallel centerline
        # (HECA #258/#228).  source_pavement_union is the authoritative real-
        # pavement footprint, so off-source residue is spurious.  Pure
        # geometry (area + on-source fraction), also moved PRE-solve.
        from .junction_repair import _drop_off_source_residue
        _drop_off_source_residue(layout, icao=icao)

        # Hole-free normalization: decompose any apron/junction still
        # carrying an interior ring (e.g. the overlap-clip's carve of a
        # wholly-contained terminal pad) into hole-free pieces with
        # conforming cuts.  MUST run before _unify_airside_geometry —
        # its weld rebuilds Polygon(exterior) and silently FILLS holes,
        # re-covering the carved terminal (KSDL terminal1, HECA ×3);
        # and to_osm writes exterior rings only, so a hole could never
        # reach the patch anyway.
        from .junction_repair import _decompose_airside_holed_shapes
        _decompose_airside_holed_shapes(layout, icao=icao)
        # Re-run the off-source residue drop on the decompose output:
        # splitting a big holed apron exposes filled boundary-bay
        # pockets (1to1 straightening chords over grass) as separate
        # ~0%-on-source pieces that the pre-decompose pass could not
        # see inside the monolithic shape.
        _drop_off_source_residue(layout, icao=icao)

        # (2026-07-29) The per-junction centerline-spine slice hook
        # (taxi_route_fillets + synthetic_junction_spine + junction_spine)
        # was retired with the legacy path: the GLOBAL slice already cut
        # every centerline into pav_union, so the fillet/synthetic/slice
        # feeders were bypassed on every build.

        # LATERAL corridor nodes (user 2026-06-26): a vertex on each apron/
        # junction edge within ±half-taxi-width of a spine, so the lateral grade
        # spine→apron is solved AND validated (else a steep runway-side drop is
        # invisible to the vertex-based check).  BEFORE conformance so the new
        # vertices propagate to neighbouring shapes.
        if os.environ.get("O4_LATERAL_SPINE_NODES", "1") == "1":
            from .lateral_spine_nodes import insert_lateral_spine_nodes
            insert_lateral_spine_nodes(layout, icao)

        # DENSIFY JUNCTION EDGES (user 2026-06-26): a junction is a taxiway that
        # follows its spine, so every junction exterior edge is subdivided to the
        # spine node spacing — a long edge with only its 2 corners can't track the
        # spine's rise (junction #97's 500 m flat edge).
        if os.environ.get("O4_DENSIFY_JUNCTION_EDGES", "1") == "1":
            from .lateral_spine_nodes import densify_junction_edges
            densify_junction_edges(layout, icao)

        # SPINE-FIRST service roads (config.SVC_SPINE_FIRST, part 30m):
        # project each SERVICE (truck-route) spine station onto the road /
        # service-junction edges so the road's new within-shape law
        # (grade_graph SOFT_VISIBILITY_ROLES gains service_road under the
        # same gate) binds aligned cross-section pairs at station spacing —
        # a road's long edges are otherwise vertex-free for 70-100 m and
        # the 2 % transverse law has nothing to sample (the CYXY cross-road
        # tear).  Same pre-conformance slot as the taxi lateral pass above.
        from .config import SVC_SPINE_FIRST as _SVC_SPINE_FIRST
        if _SVC_SPINE_FIRST:
            from .lateral_spine_nodes import insert_service_lateral_nodes
            insert_service_lateral_nodes(layout, icao)

        # Round tight pavement turn-backs (sharp tip / narrow flat end) into a
        # ~5-node half-circle so the boundary turns on a smooth arc (user
        # 2026-06-30, gate O4_ROUND_TURNBACK).  Pre-solve so the arc is graded;
        # the unify/clip/planarize below reconcile shared edges.
        from .pavement.vertices import _round_turnback_corners
        _round_turnback_corners(layout, icao)

        # ── Formation-time SOURCE CLIP (KCLT off-source phantom, Fix C) ──
        # An apron / junction face can acquire off-source area through
        # DOWNSTREAM recuts (route-proximity cut, frontage straightening) even
        # though the slice birthed it 100 % on source — KCLT #278 (8.3 k m² at
        # 35 %) is the near-runway band carved off a real 18R-end apron.  Clip
        # every < 50 %-on-source apron / junction back to the source pavement
        # (∪ runway halo) HERE — after merge_small_apron_fragments / groundside
        # emit / full-width-corridor consolidation (pass 1) have settled the
        # apron/junction set, and BEFORE _unify_airside_geometry below so the
        # clipped edges are re-noded, welded, and graded like any other pre-
        # solve geometry.  Gate O4_SOURCE_CLIP → no-op (byte-identical) off.
        if os.environ.get("O4_SOURCE_CLIP", "1") == "1":
            from .junction_repair import source_clip_partial_coverage_shapes
            source_clip_partial_coverage_shapes(layout, icao=icao)
            _covp(layout, "post-source-clip")

        # ── THE FABRIC MODEL: ARM SPARSE EMISSION (owner RULINGS
        # 2026-08-08; W2 flag O4_FABRIC_W2_SPARSE_ALL default ON, Phase-A gate
        # O4_FABRIC_SPARSE default OFF) ─────────────────────────────────
        # Armed HERE — after the apron/junction set has settled and
        # BEFORE the first pass the model changes (the 60 m stationing
        # inside ``_unify_airside_geometry`` below).  W2's scope is a ROLE
        # test over every pavement and pad, so it covers shapes born after
        # this point for free; Phase A freezes a REGION instead, because
        # its scope was two clusters and a shape LIST would go stale as
        # shapes are re-cut.  ``arm`` returns 0 and leaves every predicate
        # False when both are off, so this is byte-inert there.
        try:
            from . import fabric_sparse as _fabric_arm
            from .fabric_flags import registry_report as _flag_report
            _flag_line = _flag_report()
            if _flag_line:
                # A build whose numbers get quoted must be able to say
                # which world it was; a disabled flag with no trace in
                # the log is an arm nobody can reconstruct.
                UI.vprint(1, _flag_line)
            _n_cluster = _fabric_arm.arm(layout, icao)
            if _n_cluster:
                _fr = _fabric_arm.report()
                # The AREA is a Phase-A number (the cluster region's).  W2
                # has no region, so it is omitted rather than printed as
                # a zero a reader would take for a measurement.
                _area = _fr.get("region_area_m2")
                UI.vprint(1,
                    f"  [pav-builder] {icao}: FABRIC-SPARSE armed "
                    f"({_fr.get('mode', '?')}) — "
                    f"{_n_cluster} shape(s)"
                    + (f", {_area:.0f} m^2" if _area else "")
                    + f", roles {_fr.get('roles')}.")
        except _GEOM_EXC as _fab_arm_exc:                  # pragma: no cover
            UI.vprint(1, f"  [pav-builder] {icao}: fabric-sparse ARM "
                         f"FAILED: {_fab_arm_exc!r} — gate inert this build.")

        # ── Airside node-unification (refactor Phases 6+7, PRE-solve) ──
        # Weld + full conformance + final corner snaps, run HERE so the solver
        # sees the FINAL node-set and grades every shared vertex to ONE
        # altitude — the post-solve coincident-vertex cliffs (#291↔#371 class)
        # are eliminated at the source.  THE cliff fix.
        # The seam re-pin inside the unify pass needs the DEM and the tile
        # frame it is indexed in.  Resolved with the SAME rule the solve
        # uses (see the ``dem = tile_dem if ...`` block above): the current
        # build tile when the driver handed us its DEM, else the anchor
        # tile's own DEM — mixing the two reads terrain ~1 degree away.
        from .elevation import _load_airport_dem as _unify_load_dem
        _unify_dem = tile_dem if tile_dem is not None else _unify_load_dem(
            layout.anchor[0], layout.anchor[1])
        if tile_dem is not None and current_tile_lat is not None:
            _unify_tile_lat, _unify_tile_lon = (current_tile_lat,
                                                current_tile_lon)
        else:
            _unify_tile_lat = int(math.floor(layout.anchor[0]))
            _unify_tile_lon = int(math.floor(layout.anchor[1]))
        _unify_airside_geometry(layout, icao, dem=_unify_dem,
                                tile_lat=_unify_tile_lat,
                                tile_lon=_unify_tile_lon)
        _airside_unified_presolve = True
        _covp(layout, "post-unify-airside")

        # (s79) FINAL pre-solve overlap clip: the unify pass's vertex
        # snaps (weld / corner snaps / conformance) can sweep an apron
        # or junction edge back ONTO a fixed rect — measured at CYXY:
        # the pav[1] ROAD rect re-acquired a 13.5 m² apron overlap
        # AFTER the mid-finalize clip had zeroed it.  The clip is
        # idempotent, pure geometry, and pre-solve (node_altitudes not
        # yet derived), so re-running it here closes the window.
        if SERVICE_ROAD_CARVE:
            from .elevation import _drop_overlap_against_fixed_shapes
            _drop_overlap_against_fixed_shapes(
                layout, icao=icao, include_aprons=True)
            _covp(layout, "post-presolve-overlap-clip")

        # Finalize airside geometry PRE-solve (single-grade-graph Phase 0,
        # docs/single_grade_graph.md): the solver must grade the SAME node-set
        # the validator checks, so every airside GEOMETRY change must precede
        # the solve.  These two are pure-geometry cleanups of artifacts the
        # slice / weld / conformance chain leaves behind — coincident ring
        # vertices and illegal mid-flat-edge nodes on sloping rects — that used
        # to run post-solve.  Moving them here makes the graded geometry final
        # before the solve; the idempotent post-solve copies below then find
        # nothing to do (so the geom-guard reports 0 airside changes, modulo the
        # documented solve-dependent bridge-contact inserts).
        if os.environ.get("O4_PRESOLVE_CLEAN", "1") == "1":
            # O4_RING_NEEDLE_COLLAPSE=0 is the defect-4a A/B lever (keeps
            # the zero-length dedup, skips only the needle collapse).
            _dedup_coincident_ring_vertices(
                layout, icao,
                collapse_needles=os.environ.get(
                    "O4_RING_NEEDLE_COLLAPSE", "1") == "1")
            _covp(layout, "post-ring-dedup-needle")
            from .flatedge_snap import drop_flatedge_nodes as _pre_flatedge
            _pre_flatedge(layout)
            _covp(layout, "post-presolve-clean")

        # Pre-solve geometry guard (dev, O4_GEOM_GUARD=1): snapshot every
        # airside shape's ring geometry HERE, immediately before the solve,
        # so the comparison at emit can report how many airside shapes had
        # their geometry changed by a post-solve pass — the metric the
        # pre-solve-geometry refactor drives to 0 (see
        # docs/presolve_geometry_refactor.md).  No behaviour change.
        from .geom_guard import snapshot_airside_geometry
        _geom_guard_snap = snapshot_airside_geometry(layout)

        # ROAD-ONLY junction re-role (user 2026-06-27), at FINAL pre-solve geometry:
        # a junction with a GROUND-TRUCK (apt.dat 1206) route running THROUGH it and
        # NO aircraft taxiway is part of the service-road network, not an aircraft
        # junction — re-role it ``service_road`` so it grades AXIALLY / follows DEM
        # instead of being pinned flat at the airside bowl level.  Two ways in: a
        # truck route runs through it (wide truck yard / corridor — CYXY shape 151,
        # 340×45 m, 365 m of 1206 through, 0 m taxi), OR it is a thin residue strip
        # sharing nodes only with a service road (the spine-slice sliver — CYXY
        # SVC4's 109×0.8 m piece).  The earlier road-only re-role ran before the
        # slice and the sliver-merge only folds junction→junction, so these survive.
        # Aircraft adjacency (apron/runway/taxi rect) or an aircraft taxi-line
        # through it VETOES the re-role; boundary adjacency does not.
        if not _scorer_owns_roles:
            from .layout import (ROLE_SERVICE_ROAD, ROLE_JUNCTION)
            _cps = layout.canonical_points

            def _rk(x, y):
                return _cps.get_or_add(float(x), float(y))

            def _ring_keys(sh):
                c = list(sh.polygon.exterior.coords)
                if c and c[0] == c[-1]:
                    c = c[:-1]
                return {_rk(x, y) for (x, y) in c}

            # AIRCRAFT pavement (sharing nodes with it = a real aircraft junction).
            _aircraft = (ROLE_RUNWAY, "primary_parallel", "secondary_parallel",
                         ROLE_STUB, "cross_connector", "apron", "building")
            _aircraft_keys: set = set()
            _road_keys: set = set()
            for _o in layout.shapes:
                if _o.polygon is None or _o.polygon.is_empty:
                    continue
                if _o.role in _aircraft:
                    _aircraft_keys |= _ring_keys(_o)
                elif _o.role == ROLE_SERVICE_ROAD:
                    _road_keys |= _ring_keys(_o)
            _svc_lines = [cl.line for cl
                          in (getattr(layout, "apt_service_centerlines", None)
                              or []) if cl.line is not None and not cl.line.is_empty]
            _taxi_lines = [cl.line for cl
                           in (getattr(layout, "apt_taxi_centerlines", None) or [])
                           if cl.line is not None and not cl.line.is_empty
                           and not cl.is_service]
            _n_sl = 0
            for _s in layout.shapes:
                if (_s.role != ROLE_JUNCTION or _s.polygon is None
                        or _s.polygon.is_empty):
                    continue
                _keys = _ring_keys(_s)
                _airc = len(_keys & _aircraft_keys)
                if _airc > 2:                       # real aircraft adjacency → keep
                    continue
                try:
                    if any(ln.intersects(_s.polygon)
                           and ln.intersection(_s.polygon).length > 5.0
                           for ln in _taxi_lines):  # aircraft taxi through → keep
                        continue
                    _truck = sum(ln.intersection(_s.polygon).length
                                 for ln in _svc_lines if ln.intersects(_s.polygon))
                    _narrow = _s.polygon.buffer(-7.5).is_empty
                except _GEOM_EXC:
                    continue
                _road_shared = len(_keys & _road_keys)
                # (a) a truck route runs through it, or (b) a thin residue strip
                # sharing nodes with a service road.
                if _truck >= 15.0 or (_narrow and _road_shared >= 1):
                    _s.role = ROLE_SERVICE_ROAD
                    _n_sl += 1
            if _n_sl:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: re-roled {_n_sl} road-only "
                    f"junction(s) → service_road (truck route / sliver).")
            _covp(layout, "post-road-only-rerole")

            # The junction→service_road re-role above runs AFTER the
            # connectivity classifier (it can only see a junction's road-only
            # adjacency once unify/overlap-clip/tile_cut have settled), so an
            # apron cluster bridged to the airside only through that junction is
            # now orphaned behind a service road but still tagged ``apron``
            # (LPHR: 6 west-side aprons).  Re-run the runway-disconnection
            # classifier, SCOPED to components that touch a service road, to
            # demote those orphans to groundside.  ``require_service_adjacency``
            # keeps the post-tile_cut re-run from false-positiving an apron
            # whose aircraft-pavement chain was merely severed by the seam gap.
            # ... and the narrow-strip CARVE orphans the same way (user
            # 2026-07-04, CYXY): a lot/pad severed from the aircraft
            # chain by a carved service corridor — plus the apron
            # neck-split above can mint the orphan fragment only after
            # the first classifier run.
            if (_n_sl or _n_strip) and not _scorer_owns_roles:
                from .junction_repair import (
                    _reclassify_runway_disconnected_to_groundside)
                _reclassify_runway_disconnected_to_groundside(
                    layout, icao=icao, dem=dem,
                    tile_lat=tile_lat, tile_lon=tile_lon,
                    require_service_adjacency=True)

        # NOTE (user 2026-06-30): sub-2000 m² aprons are NOT demoted to junction.
        # The goal of the old demotion was to keep them UNANCHORED (a small
        # decomposition fragment shouldn't pin the network to its DEM level); that
        # is now handled directly by the apron-seat area filter in
        # build_nobuilding_apron_seats, so the shape keeps role=apron — correct
        # geometry that passes the junction invariants (HECA #455 stays an apron).

        # ── SIMPLE-SHAPES INVARIANT (user 2026-07-03) ─────────────────────
        # No airside shape may reach the solver/emit with INTERIOR rings:
        # the OSM emit drops them (rect-era X-Plane compat), which paves
        # over the grass hole.  Slice-level hole keyholes handle most; the
        # post-slice MERGE passes can re-create an annulus by unioning the
        # faces around a hole.  Decompose any survivor with the (modernised)
        # hole slicer — the same _decompose_polygon_with_holes the rect
        # model ran in junction_emit, which the global slice bypasses.
        from .pavement.junctions import _decompose_polygon_with_holes
        from .layout import ROLE_SERVICE_JUNCTION as _RSJ2
        _new_shapes = []
        _n_decomp = 0
        for _s in layout.shapes:
            _p = _s.polygon
            if (_s.role in (ROLE_APRON, ROLE_JUNCTION, _RSJ2)
                    and _p is not None and not _p.is_empty
                    and _p.geom_type == "Polygon" and _p.interiors):
                try:
                    _pieces = _decompose_polygon_with_holes(_p)
                except Exception:
                    _pieces = [_p]
                if _pieces and (len(_pieces) > 1
                                or not _pieces[0].interiors):
                    _n_decomp += 1
                    for _pc in _pieces:
                        _new_shapes.append(BuiltShape(
                            polygon=_pc, role=_s.role, ref=_s.ref,
                            source_axis=_s.source_axis,
                            is_bridge=_s.is_bridge))
                    continue
            _new_shapes.append(_s)
        if _n_decomp:
            layout.shapes[:] = _new_shapes
            UI.vprint(1,
                f"  [pav-builder] {icao}: decomposed {_n_decomp} "
                f"holed airside shape(s) into simple pieces "
                f"(pre-solve).")
        _covp(layout, "post-simple-shapes-decompose")

        # FINAL scoped runway-disconnection sweep (user 2026-07-04): the
        # narrow-strip carve + the passes after the 2nd classifier run
        # (simple-shapes decomposition, overlap clips) can leave an apron
        # fragment whose ONLY remaining touches are service shapes —
        # orphaned too late for the earlier runs (CYXY: the 692 m² pad at
        # (60.710421,-135.0725738) that is only accessed via the Crew-cars
        # road).  Service-adjacency scoping keeps seam-gapped aprons safe.
        if _n_strip and not _scorer_owns_roles:
            from .junction_repair import (
                _reclassify_runway_disconnected_to_groundside)
            _reclassify_runway_disconnected_to_groundside(
                layout, icao=icao, dem=dem,
                tile_lat=tile_lat, tile_lon=tile_lon,
                require_service_adjacency=True)
            # A lot and the demoted connector piece serving it are ONE
            # groundside surface (user 2026-07-04, CYXY P4: two
            # independently DEM-followed pieces met at coincident nodes
            # 2.6 m apart).  Merge BEFORE the solve so the road-mouth
            # weld binds against the single merged lot.
            from .groundside import _merge_touching_groundside
            _n_gsm = _merge_touching_groundside(
                layout, dem, tile_lat, tile_lon)
            if _n_gsm:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: merged {_n_gsm} touching "
                    f"groundside piece(s) (pre-solve).")

        # ── FULL-WIDTH SERVICE CORRIDOR consolidation, pass 2 ────────
        # (user 2026-07-05 full-width corridor): the groundside
        # route-corridor conversion, groundside-connector re-role and
        # the final road-only junction re-role above all mint NEW
        # service_road pieces after pass 1 ran — fold them into their
        # corridor now, at final pre-solve geometry, so the solver
        # grades each service corridor as ONE full-width surface.
        from .groundside import consolidate_full_width_service_corridors
        _n_fw2 = consolidate_full_width_service_corridors(layout)
        if _n_fw2:
            UI.vprint(1,
                f"  [pav-builder] {icao}: consolidated service-corridor "
                f"fragments into full-width corridor(s) "
                f"(−{_n_fw2} shape(s), final pre-solve).")
            _covp(layout, "post-full-width-corridor-2")

        # ── Runway-end-skirt PRE-SOLVE construction (Slice B stage B1,
        # gate O4_ONE_SOLVE_TERRAIN + O4_ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT,
        # both default OFF; docs/slice_b_solver_absorption_design.md §B1) ─
        # The runway-end skirt is the FIRST terrain feature absorbed into
        # the one-solve graph.  Its footprint + ring geometry are built
        # HERE, before ``per_surface_solve``, so the ring vertices join the
        # canonical node registry and the solver node list (the object-
        # bridge plate admission pattern, wired in stage B0's
        # ``_build_node_list`` hook) and every vertex becomes a HARD PIN at
        # its birth-computed profile value (``_seed_elevations`` skirt-pin
        # block).  The solver then grades neighbouring pavement to MEET the
        # pins and never reshapes them, exactly as it treats the object-
        # bridge deck pins.  Dependency (design §B1, verified at CYXY 2026-
        # 07-10): skirt values derive from the RUNWAY profile, which is
        # already redistributed to hard CIFP anchors far above (line ~4020)
        # — the taxi/apron/junction rects still carry None altitudes here,
        # so ``_nearest_pav_alt`` reads None off an unsolved neighbour and
        # the ref falls back to the runway value; the footprint is geometry-
        # only and identical to the legacy post-solve build (no CYXY skirt
        # abuts a post-solve-emitted feature — ribbon / groundside / tunnel
        # / bridge / clearance-cut — so the static-block clip against those
        # is a no-op at this airport).  With the gate OFF this block does
        # not run and the legacy post-solve emitter below fires unchanged.
        from .config import (ONE_SOLVE_TERRAIN,
                             ONE_SOLVE_TERRAIN_GAP_FILL_SPINE,
                             ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT)
        # GATE DEPENDENCY (Slice B stage B2, ratified 2026-07-10): the
        # gap sub-gate REQUIRES the skirt sub-gate — gap parents include
        # the runway-end skirts, which exist pre-solve only under B1.
        # HARD ERROR, not force-ON (fail-loudly doctrine): silently
        # widening the operator's gate scope would corrupt any A/B and
        # hide intent; the only supported configuration is both ON.
        if (ONE_SOLVE_TERRAIN and ONE_SOLVE_TERRAIN_GAP_FILL_SPINE
                and not ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT):
            raise ValueError(
                "O4_ONE_SOLVE_TERRAIN_GAP_FILL_SPINE requires "
                "O4_ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT: gap-fill "
                "pre-solve construction reads the runway-end skirts as "
                "gap parents, which exist pre-solve only under the "
                "skirt sub-gate (Slice B stage B2 dependency; "
                "docs/slice_b_solver_absorption_design.md).")
        _skirt_presolve = (ONE_SOLVE_TERRAIN
                           and ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT
                           and layout.anchor is not None)
        _gap_presolve = (ONE_SOLVE_TERRAIN
                         and ONE_SOLVE_TERRAIN_GAP_FILL_SPINE
                         and layout.anchor is not None)
        if _skirt_presolve:
            try:
                from .clearance import emit_runway_end_skirts as \
                    _emit_skirts_presolve
                _n_sk_pre = _emit_skirts_presolve(
                    layout, dem, tile_lat, tile_lon,
                    source_runways=apt.runways)
                if _n_sk_pre:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: PRE-SOLVE emitted "
                        f"{_n_sk_pre} runway-end skirt polygon(s) "
                        f"(one-solve terrain absorption, stage B1).")
                    # Cross-tile skirts are sliced like every other shape;
                    # airside pavement was already cut pre-solve, so only the
                    # new skirt pieces are cut (no-op single-tile).
                    from .geom_guard import _AIRSIDE_ROLES as _skpre_skip
                    from .tile_cut import cut_layout_at_tile_boundaries as \
                        _skpre_tile_cut
                    _skpre_tile_cut(
                        layout,
                        current_tile_lat=current_tile_lat,
                        current_tile_lon=current_tile_lon,
                        dem=dem,
                        skip_roles=_skpre_skip,
                    )
            except _GEOM_EXC as _skpre_exc:
                UI.vprint(1, f"  [pav-builder] {icao}: pre-solve runway-end "
                             f"skirt emission FAILED: {_skpre_exc!r}")

        # ── APRON TERRACE PRE-SOLVE PANELIZATION (owner ruling
        # 2026-08-04; completion round 2026-08-05) ────────────────────
        # THE PANEL BOUNDARY MUST EXIST BEFORE THE SOLVE.  Every residue
        # the terrace law carried — the D2 face height, the defects the
        # post-solve split minted, the 2 479 m² face lap — had one root:
        # the panel boundary was created AFTER the surface settled, so
        # its vertices took values the solve never produced.  Terracing
        # is geometry refinement, so it runs here, with the other
        # pre-solve constructions: each triggered apron is split into
        # panels and the joint's two station rows become ordinary apron
        # RING vertices, i.e. solve variables.  Everything downstream
        # (node list, grade graph, projections, writeback, emit) then
        # treats them as what they are, with no special case anywhere.
        # Runs FIRST among the pre-solve constructions: it is the only
        # one that changes ``layout.shapes``, and the gap-fill /
        # adjacent-ground stores capture shape references.
        if layout.anchor is not None:
            try:
                from .elevation_per_surface.route_profile.apron_terrace \
                    import construct_apron_terrace_presolve
                construct_apron_terrace_presolve(
                    layout, dem, tile_lat, tile_lon, icao=icao)
            except _GEOM_EXC as _terrpre_exc:
                UI.vprint(1, f"  [pav-builder] {icao}: pre-solve apron "
                             f"terrace panelization FAILED: "
                             f"{_terrpre_exc!r} — no panelization this "
                             f"build.")
                layout.apron_terrace_presolve = []

        # ── ENCLAVE REGIONS, SETTLED FRAME (owner 2026-08-07; spec
        # docs/specs/enclave-region-law-spec.md §1) ──────────────────────
        # The regions were published inside ``enact_classify`` because
        # G-ENCLAVE has to run there (a re-verdicted shape becomes airside
        # and closes its own region).  That frame is mid-build and more
        # FRAGMENTED than the surface that ships.  Everything below —
        # the gap-fill construction and emission, and the band march that
        # must stand down inside an enclave — lives in the SETTLED frame,
        # so the regions are re-published here, once, before the first of
        # them reads it.  Measured at HECA: classify 192 regions (183
        # pocket-width) vs settled 161 (150); reading the classify frame
        # in the band march deleted 152,734 m² of Annex 14 runway/taxiway
        # graded strip, because infield ground that the settled union
        # holds as ONE 3.4 km² region (short side 1,264 m, never keep-out)
        # is several pocket-width regions in the fragmented one.
        from .enclaves import republish_airside_enclaves_settled
        republish_airside_enclaves_settled(layout)

        # ── THE TWO PRE-SOLVE STORE CONSTRUCTIONS MOVED BELOW THE FABRIC
        # THINNING (staged-solve S1, THE GEOMETRY FREEZE) ────────────────
        # The gap-fill spine construction and the adjacent-ground band
        # construction USED TO RUN HERE, three and six statements before
        # ``fabric_sparse.thin_rings`` + the restation passes — i.e. before
        # the LAST passes that add, move and remove solve-consumed ring
        # vertices.  Both froze references onto rings that were then
        # decimated and re-stationed underneath them:
        # ``gap_fill._freeze_spine_parent_specs`` promises "the station
        # identity and ``d`` never re-derive as the solve moves
        # elevations", and it was freezing onto the PRE-THINNING ring.
        # Under the freeze both run after the last ring mutation, against
        # the geometry the solver actually consumes.  See the freeze block
        # below and ``tmp/s1_attribution.md`` §1(c) sites 51/52/54-57.
        from .config import (
            ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT,
            ADJACENT_GROUND_LAW_ENABLED as _AGL_ENABLED)
        _band_construct = (ONE_SOLVE_TERRAIN
                           and ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT
                           and _AGL_ENABLED
                           and layout.anchor is not None)

        # LATERAL-CONTIGUITY LAW, late re-bind (owner FINAL 2026-08-02).
        # The geometric half ran before the conformance passes so its cuts
        # and merges could be welded; the CAP is re-read here, against the
        # arrangement the solver is about to see and the emitter will ship.
        # Nothing moves — this writes one number per road shape.
        if _LAT_LAW_ON:
            from .groundside import apply_lateral_contiguity_law as _lat_law
            try:
                _lat_law(layout, icao, rebind_only=True)
            except _GEOM_EXC as _lat_exc2:
                UI.vprint(1, f"  [pav-builder] WARN: {icao}: "
                             f"lateral-contiguity re-bind failed "
                             f"({_lat_exc2!r}).")

        # ── ROAD ↔ AIRSIDE CROSSING CONFORMANCE (owner RULINGS
        # 2026-08-26b item 2; spec
        # ``docs/specs/road-airside-crossing-conformance-spec.md``) ──────
        # HERE, and for the same reason the re-bind above is here: the
        # arrangement is the one the solver is about to see, so the
        # airside union the crossing test reads and the airside ring
        # edges the pins name are the ones that will actually ship.  Read
        # only — this pass publishes two lists and moves nothing.
        try:
            from .groundside import road_airside_crossing_contacts
            road_airside_crossing_contacts(layout, icao)
        except _GEOM_EXC as _xconf_exc:
            UI.vprint(1, f"  [pav-builder] WARN: {icao}: road↔airside "
                         f"crossing conformance failed "
                         f"({_xconf_exc!r}).")

        # ── THE FABRIC MODEL — sparse lawful emission (owner RULINGS
        # 2026-08-08; docs/specs/fabric-model-spec.md Phase A; gate
        # O4_FABRIC_SPARSE, default OFF) ────────────────────────────────
        # LAST pre-solve act, deliberately: every construction above has
        # settled the node set (conformance welds, pad seats, mouths,
        # spine stations, the pre-solve band/terrace constructions this
        # gate already declined inside the cluster), so the weld set the
        # thinning holds is COMPLETE and what it removes is exactly the
        # population no law asked for.  Removed here — before the solve —
        # the sparse ring IS what the solver solves, what the census
        # measures and what the sim renders; a post-solve thin would give
        # three different populations.  Fully inert with the gate off.
        try:
            from . import fabric_sparse as _fabric
            _n_fab = _fabric.thin_rings(layout, icao)
            if _n_fab:
                # THE OWNER'S RIDER, RESTORED BY THE MACHINERY THAT OWNS
                # IT: "…as long as we keep adequate nodes on spines and
                # at curves."  The thinning above removes every vertex no
                # law asked for, which includes the SPINE STATIONS the
                # lateral/junction passes placed at ``config.SPINE_STEP_M``
                # — and the cross-section (``transverse``) law is priced
                # on PAIRS of stations facing each other across a
                # corridor, so losing them mints violations rather than
                # removing them (measured at CYXY, attempt 1: transverse
                # 31 -> 262 rows, junction|junction 7 -> 171).  Re-running
                # the two station passes restores exactly that population
                # at exactly their own spacing — "adequate" is MEASURED
                # from the existing machinery, never re-derived here — and
                # they are pure subdivide-to-spacing inserts, so outside
                # the cluster the second call finds nothing to do.
                # SCOPE SYMMETRY IS THE LAW HERE: restore the lateral
                # cross-section for EVERY role the thinning touched.
                # ``fabric_sparse._THIN_ROLES`` is {apron, junction,
                # service_junction, groundside_pavement} and the
                # transverse law prices {apron, junction,
                # service_junction} from an AIRCRAFT axis and
                # {service_road, service_junction} from a SERVICE one
                # (check_grade ``_TRANSVERSE_TAXI_ROLES`` /
                # ``_TRANSVERSE_SERVICE_ROLES``, imported from this
                # module's own ``TAXI_AXIS_PRICED_ROLES`` /
                # ``SERVICE_AXIS_PRICED_ROLES``), so all three of the
                # thinned priced roles need their stations back — from
                # the AIRCRAFT axes (the taxi pass) AND from the SERVICE
                # axes (``insert_service_lateral_nodes``, which the
                # first restoration attempt omitted).  Measured at CYXY,
                # attempt 1: transverse 31 -> 109 rows, of which
                # service_junction 21 -> 39 came from the missing service
                # pass and apron 3 -> 55 from stations the taxi pass
                # never had, because it projects a centerline's OWN
                # vertices and CYXY's axis carries a single 470 m
                # segment; ``station_step_m`` subdivides to the same
                # ``SPINE_STEP_M`` the service pass has always used.
                # Both are pure subdivide-to-spacing inserts inside the
                # corridor the law censuses, so they add nodes only
                # where a cross-section is priced — the owner's rider
                # ("adequate nodes on spines and at curves"), not the
                # generic stationing T8 retires.
                # THE STATION-DENSIFIED HALF IS RE-ARMED — R-c (lead
                # ruling 2026-08-08).  It was default-OFF for exactly one
                # commit because it BROKE HECA: with it on the build
                # refused at ``assert_no_final_band_inversion`` (1,655 of
                # 10,220 band-covered nodes inverted, e.g. anchors 7907
                # at 110.130 m vs 5044 at 60.730 m — a 49.400 m value
                # spread over a 47.723 m route budget).  MECHANISM, and
                # the reason the re-arm is safe now: a foot welded on
                # BOTH sides of a corridor added a CROSS EDGE to the one
                # grade graph, shortening routes and shrinking the route
                # budget between two far-apart hard anchors.  R-a removes
                # that channel at its source — a cross-section foot mints
                # no route-graph edge at all
                # (``grade_graph._build_global_spine``) — so the
                # transverse law and the route metric no longer share one
                # graph and the attempt cap resets with them.
                # ``O4_FABRIC_RC_STATION_STEP=0`` parks it again.
                from . import fabric_flags as _fabric_flags
                from .config import SPINE_STEP_M as _RESTAT_STEP_M
                _restat_step = (
                    _RESTAT_STEP_M
                    if _fabric_flags.on("O4_FABRIC_RC_STATION_STEP")
                    else None)
                _n_restat = 0
                if os.environ.get("O4_LATERAL_SPINE_NODES", "1") == "1":
                    from .lateral_spine_nodes import insert_lateral_spine_nodes
                    _n_restat += insert_lateral_spine_nodes(
                        layout, icao, station_step_m=_restat_step) or 0
                if os.environ.get("O4_DENSIFY_JUNCTION_EDGES", "1") == "1":
                    from .lateral_spine_nodes import densify_junction_edges
                    _n_restat += densify_junction_edges(layout, icao) or 0
                from .config import SVC_SPINE_FIRST as _RESTAT_SVC_FIRST
                if _RESTAT_SVC_FIRST:
                    from .lateral_spine_nodes import (
                        insert_service_lateral_nodes)
                    _n_restat += insert_service_lateral_nodes(
                        layout, icao) or 0
                _fabric.note_restation(_n_restat)
                _line = _fabric.emit_summary(icao)
                if _line:
                    UI.vprint(1, _line)
                _rod_ckpt(layout, "00a_fabric_sparse_thin")
        except _GEOM_EXC as _fab_exc:                      # pragma: no cover
            UI.vprint(1, f"  [pav-builder] {icao}: fabric-sparse thinning "
                         f"FAILED: {_fab_exc!r} — dense emission this build.")

        # ════════════════════════════════════════════════════════════════
        # THE GEOMETRY FREEZE (owner direction 2026-08-13; staged-solve
        # round S1).  Above this line is the LAST pass that may add, move
        # or split solve-consumed plan geometry.  Below it nothing may —
        # ``geometry_freeze.assert_frozen`` is the rail, and every
        # consumer of the one graph goes through it.
        #
        # Three constructions run INSIDE the freeze block, in this order,
        # and the order is the whole point:
        #
        #   1. GAP-FILL SPINES — pure plan geometry (S1 phase-1 verified:
        #      zero elevation reads of any kind), so they are built first
        #      and their frozen-nearest parent stations reference the
        #      FINAL rings.  Their vertices lie on no ring, so they enter
        #      the node list but contribute nothing to the graph.
        #   2. THE FREEZE ITSELF — one node list, one grade context, one
        #      unified graph, one reach band, published on the layout.
        #      This is the build that used to happen a second time inside
        #      ``adjacent_ground._build_construct_reach_band``.
        #   3. THE ADJACENT-GROUND BAND CONSTRUCTION — consumes the
        #      published band instead of building its own graph.
        #
        # Elevation-DEPENDENT geometry (conflict walls, terraces,
        # feathers, blends, the bands' own faces) stays post-solve and
        # ADDITIVE-ONLY; ``geometry_freeze.clear`` lifts the rail once the
        # solve has run, because phase [6] emission is lawful mutation.
        # ════════════════════════════════════════════════════════════════
        from . import geometry_freeze as _gfreeze

        # (1) Gap-fill drainage spines (Slice B stage B2; gates
        # O4_ONE_SOLVE_TERRAIN + O4_ONE_SOLVE_TERRAIN_GAP_FILL_SPINE).
        # The FIRST FREE terrain variables in the one-solve graph: the
        # solver admits every spine vertex (``_build_node_list``),
        # constrains it with envelope INTERVAL edges to its frozen-nearest
        # pavement stations plus a second-difference fairing, and writes
        # the solved values back into the store.  Face EMISSION stays at
        # the post-solve slot (blocker subjects only exist there).  A
        # construction failure degrades loudly to the analytic path.
        if _gap_presolve:
            try:
                from .gap_fill import construct_gap_fill_presolve
                construct_gap_fill_presolve(layout)
            except _GEOM_EXC as _gappre_exc:
                UI.vprint(1, f"  [pav-builder] {icao}: pre-solve gap-fill "
                             f"spine construction FAILED: {_gappre_exc!r}")

        # (1b) APRON INTERIOR LATTICE (spec heca-apron-round2 Amendment
        # 1 §1b).  The same slot and the same reason as the gap spines
        # above: these are FREE interior solver variables that must
        # exist before the plan is frozen and the ONE node list is
        # built.  An apron whose largest EMPTY interior disk exceeds
        # APRON_NODELESS_RADIUS_M has an uncontrolled membrane the
        # census cannot even see (no nodes -> no pairs -> no rows);
        # the lattice gives that ground anchors priced by the apron's
        # own caps.  Flag OFF: empty store, every leg vacuous.  A
        # construction failure degrades loudly and the build continues
        # exactly as it did before the amendment.
        try:
            from .apron_lattice import construct_apron_lattice_presolve
            construct_apron_lattice_presolve(layout)
        except _GEOM_EXC as _lat_exc:
            layout.apron_lattice_presolve = []
            UI.vprint(1, f"  [apron-lattice] {icao}: pre-solve lattice "
                         f"construction FAILED: {_lat_exc!r}")

        # (1c) APRON SPINE STATIONS (spec heca-apron-round3 §1; RULINGS
        # 2026-08-26b items 3/4/5).  The same slot and the same reason
        # as (1) and (1b): a station is PLAN GEOMETRY that must exist
        # before the plan is frozen and the ONE node list is built.
        # Where an aircraft taxi axis crosses an apron interior the axis
        # gains emitted CENTERLINE stations there — the anchored surface
        # the owner's 84.2 m line T did not have, which is why the
        # junction pieces the profile anchors stood 0.7-1.2 m proud of
        # the membrane beside them and the membrane itself sagged.
        # AFTER the lattice deliberately: the station constraint builder
        # reads the lattice store to join the two into ONE membrane
        # (§3), and a station that lands on an existing plan vertex is
        # skipped — both need the lattice points to exist first.  Flag
        # OFF: empty store, every leg vacuous.  A construction failure
        # degrades loudly and the build continues as before the round.
        try:
            from .apron_spine_stations import (
                construct_apron_spine_stations_presolve)
            construct_apron_spine_stations_presolve(layout)
        except _GEOM_EXC as _st_exc:
            layout.apron_spine_presolve = []
            UI.vprint(1, f"  [apron-spine] {icao}: pre-solve station "
                         f"construction FAILED: {_st_exc!r}")

        # (2) THE FREEZE POINT.
        _gfreeze.freeze(layout, icao=icao)
        if layout.anchor is not None:
            try:
                from . import grade_graph as _GG_frz
                from .elevation_per_surface.solver_primitives import (
                    _build_node_list as _bnl_frz)
                from .elevation_per_surface.building_feasibility import (
                    reach_band_unified as _rbu_frz)
                _frz_nodes, _frz_b2i = _bnl_frz(layout)
                _frz_ctx = _GG_frz.build_context(layout, _frz_b2i)
                _frz_G = _GG_frz.build_unified_graph(
                    layout, _frz_b2i, ctx=_frz_ctx)
                _frz_band = _rbu_frz(layout, _frz_G)
                _gfreeze.publish(layout, nodes=_frz_nodes,
                                 bucket_to_idx=_frz_b2i, ctx=_frz_ctx,
                                 graph=_frz_G, band=_frz_band)
                UI.vprint(1,
                    f"  [geometry-freeze] {icao}: plan geometry FROZEN "
                    f"({len(layout.shapes)} shape(s)); ONE node list "
                    f"({len(_frz_nodes)} node(s)), ONE grade graph "
                    f"({len(_frz_G.edges)} edge(s)), ONE reach band "
                    f"({'built' if _frz_band is not None else 'none'}) "
                    f"published for the pre-solve band, the solve and the "
                    f"validator.")
            except Exception as _frz_exc:              # pragma: no cover
                # LOUD DEGRADE, never a crash: without the published graph
                # every consumer builds its own, exactly as before the
                # freeze.  The rail stays armed — the failure is in the
                # BUILD, not in the geometry.
                UI.vprint(1,
                    f"  [geometry-freeze] {icao}: WARN the one graph/band "
                    f"could not be built ({_frz_exc!r}) — each consumer "
                    f"builds its own this build (pre-freeze behaviour); "
                    f"the freeze RAIL stays armed.")

        # (3) Adjacent-ground band FOOTPRINT march (Slice B stage B3 order
        # 1; gates O4_ONE_SOLVE_TERRAIN +
        # O4_ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT +
        # ADJACENT_GROUND_LAW_ENABLED).  Stages the raw band rings on
        # ``layout.adjacent_ground_presolve``; the post-solve emitter
        # consumes those frozen footprints instead of re-marching, clips
        # them against the post-solve static block and VALUES every vertex
        # off the solved altitudes.  It writes NO shape, so it is lawful
        # after the freeze point (the rail proves it).
        if _band_construct:
            try:
                from .adjacent_ground import \
                    construct_adjacent_ground_presolve
                construct_adjacent_ground_presolve(
                    layout, dem, tile_lat, tile_lon,
                    source_runways=apt.runways)
            except _GEOM_EXC as _agpre_exc:
                UI.vprint(1, f"  [pav-builder] {icao}: pre-solve "
                             f"adjacent-ground band construction FAILED: "
                             f"{_agpre_exc!r}")
            _gfreeze.assert_frozen(layout, "adjacent-ground construction")

        if layout.anchor is not None:
            # Runway CIFP thresholds are LOCKED — the solver never moves them.
            # The old runway-threshold-relief passes (step 3
            # ``relieve_grade_via_runway_thresholds`` and step 5
            # ``relieve_grade_via_inter_runway_split``), which adjusted
            # thresholds and re-solved, were removed (user 2026-06-06): CIFP
            # thresholds are the only surveyed-correct elevation we have, so a
            # taxi route that can't reach a runway within grade is a
            # pavement-side gap to close, never a reason to move a known-good
            # threshold.  The solver therefore runs exactly once.
            per_surface_solve(layout, icao,
                               dem=dem,
                               tile_lat=tile_lat, tile_lon=tile_lon)
            # THE FREEZE IS LIFTED HERE, and only here: phase [6] emission
            # (bands, spines, walls, cuts, the two final projections) is
            # ADDITIVE and conforms to the solved field, so it legitimately
            # mutates geometry.  Dropping the published graph with the rail
            # is deliberate — a stale one-graph must never survive into a
            # phase that rebuilds on mutated rings.
            _gfreeze.clear(layout)
            _rod_ckpt(layout, "00_post_solve")
            # §C RUNG 1 (spec lemd-rim-and-stations Amendment 1 §2): the
            # basin rim band re-seats at its nearest SOLVED anchored
            # neighbour.  It must be HERE and nowhere earlier — the
            # emitter runs pre-solve, where no built neighbour carries a
            # value yet, which is why every LEMD part took R_est while
            # the apron beside it emitted ~599.98.  One-directional
            # adoption: the rim moves, the neighbour never does.  A rim
            # plate is not a solver variable (record_pins=False, role
            # outside PAVEMENT_ROLES), so this is additive exactly like
            # the other post-solve emission passes.  Flag OFF: vacuous.
            try:
                from . import object_terrain_assembly as _ota_rim
                _rim_rep = _ota_rim.reseat_basin_rim_plates_post_solve(
                    layout)
                if _rim_rep.get("parts"):
                    UI.vprint(1, _ota_rim.format_rim_reseat_report(
                        icao, _rim_rep))
            except Exception as _rim_exc:                  # pragma: no cover
                UI.vprint(1, f"  [object-basin] {icao}: post-solve rim "
                             f"re-seat FAILED: {_rim_exc!r} — the R_est "
                             f"seed stands.")
            # (Legacy junction ring-curvature smoothing removed: it was a no-op
            # under the single-grade-graph connecting solve, which produces a
            # smooth in-grade junction surface directly.)

        if n_tile_delta != 0:
            UI.vprint(1,
                f"  [pav-builder] {icao}: tile-boundary cut "
                f"adjusted shape count by {n_tile_delta:+d}.")

        # (refactor Phase 2) The two shape-drop passes
        # (_drop_floating_orphan_junctions, _drop_off_source_residue) moved
        # PRE-solve — see above, just before the geometry-guard snapshot.

        # Final within-shape grade WARN reflects the absolute
        # final state — junction / apron / terminal Euclidean caps
        # post-final-solver.  Per user 2026-05-03 the WARN was
        # previously firing mid-pipeline with stale numbers.
        from .config import REPORT_GRADE_AUDIT
        if REPORT_GRADE_AUDIT:
            from .elevation import _report_within_shape_violations
            _report_within_shape_violations(layout, icao)

        _progress.step()  # [6] Emitting terrain features & finalizing

        # Feature B (O4_OBJECT_BRIDGE_TERRAIN, docs/object_terrain_features_
        # spec.md): classify the airport pack's bridge/tunnel objects and
        # cache the result on the layout for the bridge emitters below.
        # No-op (nothing read, nothing attached) with the gate off.
        try:
            from . import object_terrain_assembly
            object_terrain_assembly.attach_bridge_classification(
                layout, xplane_root)
        except Exception as _object_bridge_error:  # never fail the build
            UI.vprint(1, "   [object-bridge] classification skipped:",
                      _object_bridge_error)

        # ── Terrain-transition feature emit (POST-solve) ──────────────
        # Boundary ribbon, boundary→DEM bridge and taxi/road bridges emit
        # HERE, after the single solve, so each mirrors the FINAL pavement
        # profile (the runway-distance clamp anchors to settled apron/taxi
        # altitudes — see refactor Phase 5).  None are airside pavement
        # roles, so the solver never touched them.
        _progress.substep(0.02, "Emitting terrain transition features")
        finalize.emit_terrain_transition_features(
            layout, icao, xplane_root,
            tile_dem=tile_dem,
            current_tile_lat=current_tile_lat,
            current_tile_lon=current_tile_lon)
        _rod_ckpt(layout, "01_terrain_transition_emit")
        try:
            # Bridge vertex post-processing (POST-solve, with the bridge): the
            # boundary→DEM bridge is solve-dependent (Phase 5), so its airside
            # touches run here.  Collapse the bridge's ~1 m runway-clearance
            # arc onto shared runway/junction corners, and insert mid-edge
            # bridge contacts into junction rings so they share the node
            # (collinear → altitude-neutral, no grade change).
            from .boundary import (
                _snap_bridge_vertices_to_runway_corners as _snap_br,
                _insert_bridge_contacts_into_junctions as _ins_br)
            _snap_br(layout)
            _ins_br(layout)
        except _GEOM_EXC:
            pass
        _rod_ckpt(layout, "02_bridge_vertex_postproc")
        # The boundary ribbon / bridges just emitted may cross an integer
        # tile line on cross-tile airports — slice them like every other
        # shape (pavement was already cut pre-solve, so only the new
        # feature pieces are cut; no-op for single-tile airports).
        # Under the one-profile solver, airside is the solve's sole elevation
        # truth (graded against the seam DEM anchors), so FREEZE it here — the
        # gapped airside edge grazes the cut buffer and would otherwise get a
        # spurious altitude re-sample (the SPLP seam clobber).
        from .geom_guard import _AIRSIDE_ROLES as _PS_AIRSIDE
        _ps_skip = _PS_AIRSIDE
        cut_layout_at_tile_boundaries(
            layout,
            current_tile_lat=current_tile_lat,
            current_tile_lon=current_tile_lon,
            dem=dem,
            skip_roles=_ps_skip,
        )
        _rod_ckpt(layout, "03_tile_cut")

        # ── Surface-clearance chain: RETIRED (owner ruling 2026-07-26) ────
        # The adjacent-ground bands + runway-end skirts supersede the legacy
        # emit_surface_clearance_cuts strips; the chain, its B4_FLIP review
        # gate (O4_LEGACY_SURFACE_CLEARANCE), and its tests are deleted.
        # Recover from git history if ever needed.

    # ── Boundary-interior clip: RETIRED (user 2026-07-16) ─────────────
    # The "no shape may straddle the row-130 boundary" invariant (user
    # 2026-05-22) existed for the boundary ribbon, which the
    # adjacent-ground law superseded — see the matching note at the
    # (also retired) PRE-solve clip site.  Post-solve features
    # (clearance / tunnel ramps / groundside) now keep their geometry
    # across the row-130 line; EGPB's straddling tunnel-ramp rects were
    # being flattened into a hump by this clip's altitude resample.
    from .boundary import _conform_ribbon_to_pavement_seam

    # ── Boundary-conformance invariant (user 2026-05-22) ──────────────
    # RUNTIME requirement for EVERY airport: the emitted shapes must be a
    # CONFORMING partition — adjacent shapes share identical vertices
    # along common edges, no edge crossings.  Non-conformance (T-junctions
    # / crossings) makes Triangle4XP node the arrangement into degenerate
    # sub-cm² slivers (HECA: 119k→2.36M airport triangles, 9m40s load).
    # "No area overlap" (test_no_self_overlap) is necessary but blind to
    # zero-area T-junctions, which is how this slipped through.  Enforce
    # here (last geometry step), then assert the invariant holds.  The
    # boundary ribbon now participates (it tiles with pavement); only the
    # DEM bridge stays exempt (see conformance._OVERLAY_REFS).
    # ── Airside frozen; conform the post-solve FEATURES to it ─────────
    # (refactor Phases 6+7) The airside node-unification (re-connect
    # discovered lane dead-ends + weld + full conformance + near-corner /
    # neighbour-corner snaps) ran PRE-solve, so the airside partition is
    # already conforming and is FROZEN here.  Conform only the post-solve-
    # emitted FEATURES (boundary ribbon, groundside, tunnel ramps / walls) TO
    # that frozen airside — a ONE-SIDED pass (owner_roles=features) that
    # inserts vertices ONLY into feature edges, NEVER moving an airside
    # vertex (so the pre-solve-graded airside altitudes stay intact).  When
    # the pre-solve unification did NOT run (non-per-surface / no-elevation
    # path) fall back to the full both-sided unification here.
    # The bridge vertex post-processing and boundary-interior clip above
    # MOVE feature vertices after the emit-time deconflict — re-run it on
    # the settled geometry so road features stay single-cover; the
    # feature conformance below then heals the clipped seams.
    finalize.deconflict_road_features(layout, icao)
    _rod_ckpt(layout, "04_deconflict_road_features")

    from .conformance import (
        enforce_conformance, find_conformance_violations,
        FINAL_WELD_TOL_M as _FINAL_WELD_TOL_M)
    if _airside_unified_presolve:
        n_shapes, n_verts = enforce_conformance(
            layout, owner_roles=set(_POSTSOLVE_FEATURE_OWNER_ROLES))
        if n_verts:
            UI.vprint(1,
                f"  [pav-builder] {icao}: post-solve feature conformance — "
                f"inserted {n_verts} vertex(es) into {n_shapes} feature "
                f"shape(s) (airside frozen).")
    else:
        _unify_airside_geometry(layout, icao)
    _rod_ckpt(layout, "05_feature_conformance")

    # Ribbon YIELDS its elevation to abutting pavement at every shared
    # seam node (incl. the ones conformance just inserted), so there is
    # no vertical wall between pavement and the ribbon.  Altitude-only —
    # does not change geometry, so the conformance invariant still holds.
    n_seam = _conform_ribbon_to_pavement_seam(layout)
    if n_seam:
        UI.vprint(1,
            f"  [pav-builder] {icao}: ribbon seam — adopted pavement "
            f"altitude on {n_seam} ribbon rect(s).")

    # Flatten torn vertical slivers where a DEM-bridge ribbon necks to
    # near-zero width against the perimeter strip — a bridge inner vertex
    # (pavement altitude) ends up ~1 m from a perimeter-strip vertex
    # (clamped altitude) at a several-metre altitude gap, which X-Plane
    # tears (see ``_flatten_bridge_pinch_necks``).  Runs LAST so it catches
    # the pinch vertices conformance / contact-insertion grafted onto the
    # bridge rings.  Altitude-only — conformance invariant preserved.
    from .boundary import _flatten_bridge_pinch_necks
    n_pinch = _flatten_bridge_pinch_necks(layout, icao=icao)
    if n_pinch:
        UI.vprint(1,
            f"  [pav-builder] {icao}: flattened {n_pinch} DEM-bridge "
            f"pinch-neck vertex(es) (anti-tear).")

    # Re-clip DEM bridges against the FINAL pavement + ribbon geometry.
    # The emit-time trim used the emit-time snapshot; the boundary-
    # interior clip and feature conformance above can reshape the
    # ribbon and pavement edges and leave a stale overlap (LMML: ribbon
    # pieces × 37.8 m² over a DEM bridge).  The DEM bridge is
    # conformance-exempt, so this never reintroduces a T-junction.
    from .boundary import _clip_boundary_bridges_against_pavement
    n_bclip = _clip_boundary_bridges_against_pavement(layout)
    if n_bclip:
        UI.vprint(1,
            f"  [pav-builder] {icao}: re-clipped {n_bclip} DEM-bridge "
            f"shape(s) against final pavement / ribbon.")
    _rod_ckpt(layout, "06_ribbon_seam_and_bridge_clip")

    # Strip zero-length edges (duplicate ring vertices) the geometry passes
    # left behind — they triangulate into degenerate slivers (stretched
    # textures).  Geometry-neutral, so it runs after conformance enforcement
    # and before the final conformance audit.
    _dedup_coincident_ring_vertices(layout, icao)
    _rod_ckpt(layout, "07_dedup_ring_vertices")

    # (Legacy post-solve cap-debulge removed: it ran only under the retired
    # O4_SINGLE_GRADE_GRAPH=0 path; the single-grade-graph connecting solve grades
    # the cap in-grade, so the post-solve band-aid is superseded.)

    # Enforce the rect flat-end rule (user 2026-06-19): only a sloping rect's
    # 2 CORNERS are legal shared vertices on its flat end.  The spine slice +
    # the weld/conformance chain can leave an apron/junction vertex mid-flat-
    # edge (SPJC SVC13 ran corner→MID→corner along SVC13's flat end) — an
    # illegal shared vertex that triangulates to a Triangle4XP T-junction tear.
    # Drop any such node so the edge straightens corner-to-corner.  LATE pass
    # (final geometry + altitudes), before the conformance audit below.
    from .flatedge_snap import drop_flatedge_nodes
    drop_flatedge_nodes(layout)
    _rod_ckpt(layout, "08_drop_flatedge_nodes")

    # FINAL planarization (user 2026-06-30, gate O4_PLANARIZE_AIRSIDE): drive the
    # conformance invariant to 0 as the LAST geometry step — resolve edge
    # CROSSINGS (insert the intersection point on both edges) + collinear
    # T-junctions, both shape-preserving and altitude-interpolating so it is
    # safe post-solve.  Runs here, after EVERY geometry pass, so nothing can
    # re-introduce a crossing afterward (the pre-solve crossings returned because
    # later passes re-cut edges).
    if os.environ.get("O4_PLANARIZE_AIRSIDE", "1") == "1":
        from .conformance import planarize_airside
        planarize_airside(layout, icao=icao)
    _rod_ckpt(layout, "09_planarize_airside")

    # SERVICE lens deconfliction (user 2026-07-04): the canonical vertex
    # weld can cross two near-coincident service boundaries whose contact
    # chains carry different vertex sequences (corridor-converted road vs
    # the strip-carved junction it was trimmed against — 0.38 m² lens).
    # Runs BEFORE the final T-vertex weld so the clip's new on-edge
    # vertices get welded (running after left a residual T-junction).
    if compute_elevations:
        from .groundside import _deconflict_service_overlaps
        _n_svc_ov = _deconflict_service_overlaps(layout)
        if _n_svc_ov:
            UI.vprint(1,
                f"  [pav-builder] {icao}: deconflicted {_n_svc_ov} "
                f"overlapping service shape(s) (lens clip).")
        _rod_ckpt(layout, "10_service_lens_deconflict")

    # LAST-WORD building-pad re-clip (owner CYXY building1 2026-07-28):
    # the post-solve conformance weld's 0.5 m tolerance can bow a
    # pavement ring back ACROSS a building-pad edge (36.9 m²
    # apron∩building1) and nothing later owned the pair.  Pavement
    # yields to the pad (the slice's own ``pav − terminal_union``
    # invariant); pure difference with altitude carry, BEFORE the final
    # T-weld so the clip's new on-edge vertices get welded.
    from .groundside import _clip_pavement_against_building_pads
    _n_bpad = _clip_pavement_against_building_pads(layout)
    if _n_bpad:
        UI.vprint(1,
            f"  [pav-builder] {icao}: building-pad re-clip — "
            f"{_n_bpad} pavement shape(s) yielded to pads.")
    _rod_ckpt(layout, "11_building_pad_reclip")

    # (The §T5 LAST-WORD wall-foot re-clip stood here.  It existed only
    # to re-establish the foot/face partition after the post-solve
    # conformance weld bowed a face's inner edge across its own foot;
    # the foot retired with RULINGS 2026-09-01c, so there is no
    # partition to re-establish and the pass — and its seam — are gone.)

    # LAST-WORD bridge re-clip: drop_flatedge_nodes / planarize above can
    # STRAIGHTEN a pavement edge that the emit-time bridge clip followed,
    # re-creating a pavement∩bridge overlap (CYXY apron#25: 6.7 m²).  Run
    # the re-clip again on the final geometry (idempotent).
    n_bclip2 = _clip_boundary_bridges_against_pavement(layout)
    if n_bclip2:
        UI.vprint(1,
            f"  [pav-builder] {icao}: final DEM-bridge re-clip — "
            f"{n_bclip2} shape(s).")
    _rod_ckpt(layout, "12_bridge_reclip_final")

    # FINAL T-vertex weld (user 2026-07-02): a node lying ON another
    # shape's edge interior without a weld tears Triangle4XP's
    # triangulation (stretched textures).  Two classes escape the passes
    # above: (a) a FEATURE vertex on an AIRSIDE edge — the one-sided
    # feature conformance only inserts into feature edges, and
    # planarize_airside covers airside↔airside only; (b) DEM-bridge /
    # clearance overlay vertices — conformance-exempt on a "built-in
    # gap" premise that does not always hold (CYXY: bridge vertices
    # exactly on apron/boundary edges).  Insert-only at interpolated
    # altitudes (surface-neutral), so it is safe post-solve.  TIGHT
    # tolerance: only truly-ON-edge nodes (the tearing class sits at
    # 0.000-0.003 m); the full 0.5 m weld tolerance would bow an edge
    # outward by up to the tolerance and mint hairline overlaps
    # (zero-tolerance test_no_self_overlap).
    _n_ws, _n_wv = enforce_conformance(layout, tol=_FINAL_WELD_TOL_M,
                                       include_overlay_refs=True)
    if _n_wv:
        UI.vprint(1,
            f"  [pav-builder] {icao}: final T-vertex weld — inserted "
            f"{_n_wv} vertex(es) into {_n_ws} shape(s).")
    _rod_ckpt(layout, "13_final_t_vertex_weld")

    # LAST groundside↔airside separation (user 2026-07-04): the strip
    # carve + the late runway-disconnection sweeps demote shapes AFTER
    # the earlier separation runs, and a demoted lot's DEM-follow
    # rebuild can leave a hairline overlap with the service road it
    # abuts (CYXY: 0.6 m² lot∩road — zero-tolerance
    # test_no_self_overlap).  The pass is idempotent and keeps touching
    # service edges (share-svc), so a clean layout is unchanged.
    if compute_elevations:
        try:
            from .groundside import _separate_groundside_from_airside
            _dem_last = tile_dem if tile_dem is not None else None
            if _dem_last is None:
                from .elevation import _load_airport_dem as _lad_last
                _dem_last = _lad_last(layout.anchor[0], layout.anchor[1])
            _tl = (current_tile_lat if current_tile_lat is not None
                   else int(math.floor(layout.anchor[0])))
            _tn = (current_tile_lon if current_tile_lon is not None
                   else int(math.floor(layout.anchor[1])))
            _separate_groundside_from_airside(layout, _dem_last, _tl, _tn,
                                              preserve_field=True)
            # POST-SOLVE LAW SEATING (cycle-6 ingestion, spec Part D).
            # The classification slot demotes pavement to groundside long
            # before the solve, when NO higher surface carries a value —
            # so those pieces are necessarily born on a DEM seed, and
            # until now nothing came back for them.  This is that pass:
            # values only, the same ladder and the same emitter identity,
            # over every groundside ring still carrying its seed.  It
            # runs HERE — after the last groundside geometry mutation and
            # before the chord limiter — so the limiter closes any
            # residual on the seated field, not on the seed.
            # THE ONE ROUTE GRAPH (RULINGS 2026-08-06, "ONE graph:
            # groundside joins the route graph").  The band is built ONCE
            # here and handed to the ladder: every connected groundside
            # ring seats inside what its service-road routes can reach,
            # and a ring the graph does not reach is not solved at all.
            from .groundside import (groundside_route_band,
                                     seat_groundside_on_law,
                                     seat_service_pavement_on_law)
            _gs_band = groundside_route_band(layout)
            # SERVICE FIRST, THEN THE LOTS.  A lot welded to a service
            # junction grades to that junction's value, so the junction
            # has to carry law before the lot reads it — seating them in
            # the other order laundered a raw-DEM junction into the lot's
            # own law datum (HEAZ: the 559.84 m within-shape rows).
            _n_svc = seat_service_pavement_on_law(layout, _dem_last, _tl,
                                                  _tn, band_at=_gs_band)
            if _n_svc:
                UI.vprint(1,
                    f"  [groundside-law-seat] {icao}: re-seated {_n_svc} "
                    f"service road/junction shape(s) the one solve never "
                    f"reached (mouth band, road law).")
            # ── ROAD ↔ AIRSIDE CROSSING ADOPTION (RULINGS 2026-08-26b
            # item 2; spec Amendment 1 §3) ─────────────────────────────
            # HERE, between the service seat and the lot seat, and for the
            # same reason the service seat precedes the lot seat: a lot
            # welded to a road reads that road's value, so the road has to
            # carry its adopted law before the lot reads it.  The pass
            # writes VALUES on ROAD-FAMILY vertices only — a vertex any
            # non-road shape also carries is frozen — so no airside ring
            # can move.  Nothing about it is in the grade graph.
            try:
                from .groundside import (
                    adopt_road_airside_crossing_values as _adopt_xing)
                _adopt_xing(layout, icao)
            except _GEOM_EXC as _adopt_exc:
                UI.vprint(1, f"  [pav-builder] WARN: {icao}: road↔airside "
                             f"crossing adoption failed ({_adopt_exc!r}).")
            # THE FREE-ROAD PROFILE PASS RAN HERE — RETIRED 2026-08-31
            # (RULINGS 31b, spec §3.1).  Its chord branch made every
            # bracketed station take the pin-to-pin chord exactly and its
            # self-pins bracketed every ≥2-station chain, so 86 % of
            # HECA's road stations were a straight line between end
            # values and an 8 %-lawful hill emitted dead flat.  The law
            # it was reaching for is now ONE law in TWO owners: the core
            # clamps every general road (O4_Vector_Utils.
            # cap_lipschitz_profile), and auto_patch profiles the
            # AIRSIDE-CONTACT TRANSITION with the same function at the
            # solver's final writeback (road_transition.
            # solve_road_transitions).  Deleted, not gated (29f).
            _n_seated = seat_groundside_on_law(layout, _dem_last, _tl, _tn,
                                               band_at=_gs_band)
            if _n_seated:
                UI.vprint(1,
                    f"  [groundside-law-seat] {icao}: re-seated "
                    f"{_n_seated} groundside ring(s) that were still on "
                    f"their pre-solve DEM seed.")
            # The separation re-derives DEM altitudes for any piece it
            # clipped — AFTER the finalize-stage chord limiter ran, so a
            # rebuilt hillside piece reads >4 % across its interior again
            # (CYXY #207: 8 % over 7.8 m).  Re-limit (idempotent).
            # (The claim-drift audit that bracketed this call retired
            # with the R14-1 claim class — RULINGS 2026-08-31b, redesign
            # spec §5.1, census #32.)
            from .groundside import _grade_limit_groundside_chords
            _grade_limit_groundside_chords(layout)
        except _GEOM_EXC:
            pass
        _rod_ckpt(layout, "14_groundside_separation")

    tjs, crossings = find_conformance_violations(layout.shapes)
    if tjs or crossings:
        UI.vprint(1,
            f"  [pav-builder] WARN: {icao}: conformance invariant NOT "
            f"met — {len(tjs)} residual T-junction(s), {len(crossings)} "
            f"edge crossing(s) (→ Triangle4XP mesh slivers).")

    # Pre-solve geometry guard (dev): report how many airside shapes had
    # their geometry changed by a post-solve pass (target = 0).  Runs BEFORE
    # decimation so the report keeps measuring the unintended reshapes, not
    # the deliberate emit thinning.
    from .geom_guard import report_post_solve_changes
    report_post_solve_changes(layout, _geom_guard_snap, icao)

    # EMIT DECIMATION (user design 2026-07-03): drop 3D-collinear ring
    # vertices — node density follows the SOLVED profile (straights emit as
    # single segments; vertical transitions and curves keep their nodes).
    # Must see the final welded/conformant geometry, and a vertex may only
    # vanish when every ring sharing it agrees (no T-vertices minted).
    # BEFORE the final grade projection (user 2026-07-05): decimating a
    # junction ring re-triangulates its interior, so the decimated ring's
    # MESH has chords the pre-decimation law never contained — running the
    # projection on the decimated rings makes it the true last word on
    # values for the geometry X-Plane actually renders (SPJC 18-pair
    # 1.5-1.8 % junction class).  Gate O4_EMIT_DECIMATE.
    if compute_elevations:
        from .emit_decimate import (decimate_emit_nodes,
                                    normalize_runway_altitudes,
                                    repair_sliver_corners)
        # ONE runway representation (user 2026-07-06): any hi/lo
        # canonical rect still alive (incl. pieces minted by post-solve
        # splits) becomes per-vertex node_altitudes before the geometry
        # passes and the final projection.
        normalize_runway_altitudes(layout, icao)
        _rod_ckpt(layout, "15_normalize_runway_altitudes")
        # Sliver-needle repair BEFORE decimation + the final projection
        # (user 2026-07-06): the emit-time repair removed needle vertices
        # AFTER the last law projection, merging two enforced ring edges
        # into one nobody enforced (SPJC apron 77 m blend pair).  The
        # emit-time scan remains as the backstop for quantization-born
        # needles.
        repair_sliver_corners(layout, icao)
        _rod_ckpt(layout, "16_repair_sliver_corners")
        # LATE EDGE DENSIFY (user in-sim finding 2026-07-09): shapes
        # reshaped post-solve (junction merges / slice re-cuts) can be
        # born with over-long edges the pre-solve densify never saw
        # (CYXY: a 1,057 m junction chord).  Inserted here — BEFORE
        # decimation and the final grade projection (the ordering law)
        # — the lerped vertices are law-projected onto the mesh the
        # sim renders, and the 60 m spacing survives the decimators'
        # MAX_CHORD.
        from .conformance import densify_long_edges as _dle
        from .clearance import _AIRSIDE_PAVEMENT_ROLES as _dle_roles
        _n_dense2 = _dle(layout, _dle_roles, 60.0)
        if _n_dense2:
            UI.vprint(1,
                f"  [pav-builder] {icao}: late edge densify — inserted "
                f"{_n_dense2} vertex(es) on over-60 m pavement edges.")
        _rod_ckpt(layout, "17_late_edge_densify")
        _progress.substep(0.90, "Decimating emitted geometry")
        decimate_emit_nodes(layout, icao)
        _rod_ckpt(layout, "18_emit_decimate")

    # FINAL GRADE PROJECTION (round 4, user 2026-07-03): the passes above
    # (planarize, welds, clips, merges, emit decimation) reshaped rings
    # AFTER the elevation solve, so the law pairs of the FINAL rings differ
    # from what the solve projected.  One last scalar GS projection on the
    # final geometry (runway/seam/feature-weld nodes hard, pads movable-
    # flat) closes the post-solve mutation classes the validator otherwise
    # flags.
    if compute_elevations:
        from .elevation_per_surface.route_profile.solve import (
            final_grade_projection)
        # DEM + tile frame for the flatness-certificate tier (user
        # 2026-07-05) — the SAME dem/tile pairing rule the elevation solve
        # uses (current tile when the driver provided tile_dem, else the
        # anchor tile that _load_airport_dem covers), so certificate seeds
        # are bit-identical to the solve's node seeds.  Failure to load a
        # DEM just disables certification (eager generation).
        _projection_dem = None
        _projection_tile_lat = _projection_tile_lon = 0
        if layout.anchor is not None:
            try:
                from .elevation import _load_airport_dem as _projection_load
                _projection_dem = (tile_dem if tile_dem is not None
                                   else _projection_load(layout.anchor[0],
                                                         layout.anchor[1]))
                if tile_dem is not None and current_tile_lat is not None:
                    _projection_tile_lat = current_tile_lat
                    _projection_tile_lon = current_tile_lon
                else:
                    _projection_tile_lat = int(math.floor(layout.anchor[0]))
                    _projection_tile_lon = int(math.floor(layout.anchor[1]))
            except _GEOM_EXC:
                _projection_dem = None
        # ════════════════════════════════════════════════════════════════
        # THE GRADE PROJECTION — the pipeline's ONLY one (owner ruling
        # 2026-08-14, "THE DOUBLE PROJECTION RETIRES", superseding the
        # 2026-07-18 keep-both ruling).  The LATE call is retired; this
        # one survives.
        #
        # THE SPEC GUESSED THE OTHER WAY, AND THE MEASUREMENT INVERTED IT.
        # S1e's charter expected the LATE position to be the natural point
        # ("likely the current late position, with the mid call
        # retiring") and told the lane to re-measure rather than assume.
        # Both arms were built.  The late-only arm costs law:
        #
        #   projection exit, over-cap edges     HECA        CYXY
        #     control (mid, then late)          7107 → 7861   55 → 80
        #     late-only (one call)                     8933         85
        #     mid-only  (one call)                        —         55
        #   census vs the round-close reference
        #     late-only                              +263          +4
        #     mid-only                                  —   +0 (EXACT)
        #
        # THE MECHANISM, read off the projection's own exit line: the mid
        # call runs with 9,791 hard nodes at HECA, the late call with
        # 20,213.  The post-solve FEATURE emission is what doubles the
        # hard set — "nodes welded to already-emitted FEATURE shapes are
        # HARD" (``final_grade_projection``'s own contract) — so by the
        # late position half of airside is frozen and the projection can
        # only nudge what is left.  The two calls were never a duplicate
        # pair: the mid call is the only one that runs while airside
        # pavement is still FREE, and that freedom is law-solving power no
        # value-carry can hand back.
        #
        # WHY THE LATE CALL IS THE ONE THAT GOES.  It was added in
        # 2026-07-17 because band/gap emission, tile cuts, conformance
        # welds, crown completion and the densify passes reshape rings
        # after this point — i.e. because that refinement was NOT
        # value-preserving.  S1e phase 1 measured that it now is
        # (Ortho4XP/tmp/s1e_stage_map.md): those stages carry their solved
        # values by interpolation or weld adoption, with a RE-PROJECTION
        # CLASS of 2 vertices at CYXY and 8 at HECA, all at or below the
        # 0.01 m materiality floor or inside a named law pass.  The
        # premise the late call was built on has been closed by the
        # freeze-and-carry work, so the call itself is what retires.
        # ════════════════════════════════════════════════════════════════
        # ── WELD BEFORE PROJECTION (spec weld-before-projection-spec.md;
        # owner "proceed" 2026-08-21) ────────────────────────────────────
        # THE NID-LEVEL FINAL WELD USED TO RUN INSIDE ``to_osm``, i.e. after
        # the bake AND after this projection, so every ring adjacency it
        # minted was law nothing had priced: 22 of SPJC's 48 sub-5 m > 2x
        # rows are pairs whose ENDPOINTS are baked nodes (within 9 mm) but
        # whose PAIR the bake never saw, and the law-aware emit snap cannot
        # catch them because it validates BAKED pairs only.  Values are
        # single-authored throughout (the 2026-08-08 seat-is-the-weld
        # ruling holds) — the defect is topology TIMING, not authorship.
        #
        # Running the weld HERE puts those adjacencies in front of the bake
        # and the projection, so they are priced like any other ring edge
        # (ring-adjacent branch, A2/A3/A4 classification, MIN_PAIR_DIST_M
        # floor — no new law, coverage only).  It is the SAME weld function
        # the earlier passes use (``conformance.enforce_conformance``, whose
        # ``_plan_shape_inserts`` is the ONE candidate enumeration), at the
        # same FINAL_WELD_TOL_M, so no second notion of "which vertices
        # weld" is minted.  Insert-only at interpolated altitudes, which is
        # surface-neutral by construction.
        #
        # THE COUNT IS THE MEASUREMENT: if this reports 0 the reorder is a
        # no-op and the emit-minted class is authored by a POST-projection
        # pass instead (the epsilon-wedge weld at part 30j) — which is a
        # STOP and a finding, not a silent pass.
        if _WELD_BEFORE_PROJECTION and compute_elevations:
            from .conformance import (
                enforce_conformance as _enf_pre,
                snap_subcm_vertex_twins as _snap_pre,
                repair_emit_quantized_rings as _quant_pre,
                FINAL_WELD_TOL_M as _PRE_WELD_TOL_M)
            from .layout import ONEDGE_SNAP_TOL_M as _PRE_SNAP_TOL_M
            # QUANTIZED-VALIDITY REPAIR FIRST (same §1 closure): a ring
            # the emitter would buffer(0)-repair AFTER the projection is
            # repaired here instead, so the law graph is built on the
            # ring that actually ships (its own message reports sites).
            _quant_pre(layout)
            # THE SNAP IS THE INSERT'S DOCUMENTED PRECONDITION, so it runs
            # here too (AMENDMENT A1 §1b lets the snap STAY post-projection;
            # it does, unchanged — this is an ADDITIONAL idempotent call, not
            # a move).  Without it the weld propagates mm-apart cross-shape
            # twins instead of unifying them, which the solver/validator
            # budget lockstep test measures (CYXY, one edge, 7.7e-5 m).
            # Snapping already-unified twins is a no-op, so the
            # post-projection call keeps its own meaning.
            _n_ts_s, _n_ts_v = _snap_pre(layout)
            if _n_ts_v:
                UI.vprint(1,
                    f"  [weld-before-projection] {icao}: snapped {_n_ts_v} "
                    f"sub-cm vertex twin(s) across {_n_ts_s} shape(s) first "
                    f"(the insert's precondition; sub-cm, below the 0.01 m "
                    f"materiality floor).")
            # THE WEDGE INSERT AND THE NID INSERT ARE THE SAME FUNCTION at
            # the same tolerance — what distinguished the post-projection
            # wedge call was only its DEM/tile frame, the "cuts never fill"
            # bound for an insert on a CUT-ONLY shape (SPJC runway_end_resa:
            # two inserts floated +2.12 / +2.22 m above the DEM envelope
            # without it).  Carrying that frame here is what makes this ONE
            # pass do both halves' work (AMENDMENT A1 §1a).
            # ``private_snap_tol``: adopt the emit move's private on-edge
            # class into the receiving rings HERE, so the law graph
            # prices those vertices and the emit-time move + nid splice
            # both stand down (their node reads two owners) — the §1
            # residue class measured as ungraded emitted airside
            # vertices (test_solver_and_validator_same_nodes).
            _n_pw_s, _n_pw_v = _enf_pre(layout, tol=_PRE_WELD_TOL_M,
                                        include_overlay_refs=True,
                                        dem=_projection_dem,
                                        tile_lat=_projection_tile_lat,
                                        tile_lon=_projection_tile_lon,
                                        private_snap_tol=_PRE_SNAP_TOL_M)
            UI.vprint(1,
                f"  [weld-before-projection] {icao}: inserted {_n_pw_v} "
                f"T-vertex(es) into {_n_pw_s} shape(s) BEFORE the final "
                f"projection — these adjacencies now enter the bake and are "
                f"priced as ring edges (spec weld-before-projection-spec.md)."
                + ("  ZERO: the reorder is a no-op here; the emit-minted "
                   "class is authored by a POST-projection pass."
                   if not _n_pw_v else ""))
            _rod_ckpt(layout, "18b_weld_before_projection")
        final_grade_projection(layout, icao, dem=_projection_dem,
                               tile_lat=_projection_tile_lat,
                               tile_lon=_projection_tile_lon,
                               recapture_snapshot=False)
        _rod_ckpt(layout, "19_final_projection")

        def _post_projection_conformance_passes():
            # PAD-IN-SOLVED-PAVEMENT HOST LEVEL (user 2026-07-10, round 6
            # site 3): a building pad embedded in / abutting SOLVED pavement
            # must sit FLAT at the level the HOST pavement solved to at the
            # contact, not at its raw-DEM frontage seat.  The initial solve
            # already lifts a movable-flat pad to its host, but
            # ``final_grade_projection`` re-runs ``build_building_seats``
            # (DEM-biased) and re-stamps the pit value (CYXY building8 →
            # 705.0 while apron #129 solved 708.65; a -333 %/1.1 m step,
            # "a big hump in this apron").  Runs AFTER the projection so it
            # reads the FINAL host solution and nothing re-seats the pad
            # afterwards; it also lifts the shared apron lip so pad and
            # host weld at one flat level (no emit cliff).  Gate off →
            # no-op / byte-identical.
            from .elevation_per_surface.route_profile.anchors import (
                relevel_pads_to_host_pavement)
            _n_padhost = relevel_pads_to_host_pavement(layout)
            if _n_padhost:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: pad-host level — {_n_padhost} "
                    f"embedded pad(s) re-levelled to the host pavement "
                    f"solution.")
            # GROUNDSIDE RE-LIMIT after the projection (user 2026-07-06,
            # CYXY #184): groundside lots are NOT in the projection's
            # constraint roles, so enforcing a ROAD edge can nudge a welded
            # mouth a few cm past the lot ring's 4 % Lipschitz field
            # (measured: the limiter's lawful 699.80 pushed to 699.84 → a
            # 4.64 % lot pair).  The chord limiter is idempotent and its
            # weld re-adoption keeps road and lot emitting one value —
            # re-running it here re-levels the ring around the projected
            # weld; the cm-scale road-side drift it re-introduces sits
            # inside the validator's rounding envelope, unlike the
            # lot-side tear it removes.
            # RIBBON/BRIDGE RE-ADOPTION after the projection (user
            # 2026-07-06, CYXY apron #29): the seam cascade ran before
            # this projection — a pavement vertex the projection then
            # moved leaves the ribbon/bridge holding the STALE adopted
            # value, and the emit consensus drags the welded node back
            # over the pavement law (693.00 lawful → 692.85 emitted,
            # 1.25 % on a 1 % apron).  The cascade is altitude-only and
            # idempotent — re-running it re-adopts the projected values.
            try:
                from .boundary import _conform_ribbon_to_pavement_seam
                _conform_ribbon_to_pavement_seam(layout)
            except _GEOM_EXC:
                pass
            try:
                from .groundside import _grade_limit_groundside_chords
                layout._weld_relimit_moved_xy = []
                # WELD OUTRANKS CAP, ARMED HERE ONLY (owner ruling
                # 2026-08-30, the item-4 rework).  This is the LAST
                # road-family altitude writer of the build and the only
                # limiter call that runs after ``final_grade_projection``
                # — so a road built UP to a pinned airside weld floor
                # cannot be carried back into an airside value by any
                # later pass.  Armed at the two earlier call sites
                # (finalize's and the post-solve-law-seat one) it moved
                # 2,053 solve-owned airside nodes through the
                # projection; the ruling is that the pin is a READ-ONLY
                # SOURCE.  See ``groundside._chord_cut_and_fill``.
                # PHASE-0 ATTRIBUTION ARM (lane/phase0roads, TEMPORARY):
                # ``O4_ARM_NO_WELD_UPBUILD=1`` disarms the 2026-08-30
                # pinned up-build HERE and nowhere else — the spec's
                # suspect-1 "disable the new arming" arm
                # (docs/specs/phase0-attribution-spec.md Task A).  A
                # measurement switch, not a fix; the shipped armed call
                # below is untouched (and stays the ONE site carrying the
                # literal, which ``test_weld_outranks_cap_chord_limiter``
                # asserts).
                if os.environ.get("O4_ARM_NO_WELD_UPBUILD") == "1":
                    _grade_limit_groundside_chords(layout)
                else:
                    _grade_limit_groundside_chords(
                        layout, weld_outranks_cap=True)
                # THE WELD-RELIMIT SINK — DELETED 2026-08-04 (spec
                # ``docs/specs/kill-half-spec.md`` §2).  Welds this
                # re-adoption moved were pushed into
                # ``layout._break_node_ll`` so their over-cap pairs would
                # report as break-region blends instead of actionable
                # misses.  That is the third writer of the quarantine the
                # spec kills (quarret2 named it "sink C"; it contributed 0
                # nodes at HECA/CYXY/HEAZ in the kill-prep measurement).
                # ``_weld_relimit_moved_xy`` itself stays — it is the
                # limiter's own bookkeeping (``groundside.py``), not a
                # quarantine.
            except _GEOM_EXC:
                pass

        # T1b reorder (board): these passes run HERE, reading projected
        # values.  Running them before a projection would seat pads /
        # re-adopt ribbon values against unprojected solver values, which a
        # projection then moves again.  With the LATE call retired this is
        # the point immediately after the pipeline's only projection, so
        # the requirement is met by the same ordering it always was.
        _post_projection_conformance_passes()
        # THE FREE-ROAD PROFILE RE-SOLVE RAN HERE — RETIRED with the
        # pass (RULINGS 31b, spec §3.1); its replacement runs INSIDE
        # the final grade projection, at the writeback seam.
        #
        # THE PROFILER DOES NOT GET THE LAST WORD — REFUTED AND
        # REVERTED (spec author, Batch 2c, on Batch 2b's own
        # measurement).  A second, idempotent ``solve_road_transitions``
        # call ran HERE so the pinned-transition law would be the build's
        # last road-family writer (RULINGS 31d finding B).  who_wrote
        # confirmed the ordering — no road-family write frame after it —
        # and the census priced it: HECA 6,403 -> 7,496 ADJUDICATED
        # (+1,093) against the Batch-2 arm on one tree, and every row of
        # it road-family or its welded groundside
        # (service_junction|service_junction +581,
        # groundside_pavement|groundside_pavement +426, within_shape
        # +669, road_cross_section +234, transverse +173) with airside
        # EXACTLY unchanged (airside_no_step / apron|apron /
        # junction|junction all +0).
        #
        # THE MECHANISM, and it is a law conflict rather than a bug: the
        # conformance family is what reconciles a road ring LATERALLY,
        # and re-imposing a LONGITUDINAL transition profile after it
        # re-breaks that reconciliation — ``road_cross_section`` is
        # defined only over road-family rings and it is the family that
        # moved.  It is the same class the retired free-road pass's
        # key-exemption round measured (+187 law-true rows at CYXY,
        # "every one service_junction": one value per STATION is true of
        # a road ring and false of a junction blob).  RULED: conformance
        # keeps the last word, the writeback-seam call inside
        # ``final_grade_projection`` stands alone, and the isolated
        # post-profiler road moves finding B named are accepted as
        # lateral reconciliation doing its lawful job.
        _rod_ckpt(layout, "20_post_projection_conformance")

        # SPINE CROWN v2 (user ruling 2026-07-07, part 30): the crown is
        # built INSIDE the solve now — runway rings (uniform per-ref
        # profile − rate·half_width) and taxi/service corridor edges all
        # crown through the crown drop field applied at the solve's
        # writeback (crown.build_crown_drop_field), and the spine
        # breaklines are staged from the SOLVED route profiles
        # (crown.emit_crown_spines).  The v1 post-solve edge-drop pass
        # that lived here (freeze sets / vetoes / revoke valve) is gone.

        # Runway-end down-slope SKIRTS (Pass D, gate O4_RUNWAY_END_SKIRT):
        # the ABSOLUTE LAST emission — after decimation and the final
        # grade projection (which, since 8ca25a3, runs after decimation
        # and is the last word on values) — because the skirt bakes the
        # law floor from edge-interpolated pavement reads (end elevation
        # + entry grade) and any earlier placement reads rings/values
        # that later passes rewrite.  Emitting here, the emitter reads
        # exactly the geometry that renders — the same reads the
        # verification checker makes.  Skirts are freshly minted with a
        # pavement gap (no shared vertices), so arriving after
        # decimation mints no T-vertices.
        try:
            from .clearance import emit_runway_end_skirts
            _progress.substep(0.92, "Emitting runway-end skirts")
            # Stage B1: when the one-solve terrain gate built the skirts
            # PRE-SOLVE (above, as pinned solver-graph members), the legacy
            # post-solve emitter must NOT run again — the shapes already
            # exist.  The bridge↔skirt reconciliation below still runs so
            # boundary→DEM bridges are trimmed to the (now pre-solve) skirt
            # footprint regardless of which path emitted them.
            n_sk = 0 if _skirt_presolve else emit_runway_end_skirts(
                layout, _projection_dem,
                _projection_tile_lat, _projection_tile_lon,
                source_runways=apt.runways)
            if _skirt_presolve:
                # Reconcile pre-solve skirts with the post-solve boundary
                # bridges (no-op where none overlap, e.g. CYXY).
                try:
                    from .boundary import \
                        _reconcile_boundary_bridges_with_skirts as _rbbs_pre
                    _rbbs_pre(layout)
                except _GEOM_EXC:
                    pass
            if n_sk:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: emitted {n_sk} "
                    f"runway-end skirt polygon(s).")
                # A skirt reaches up to ~305 m off a runway end and can
                # cross an integer tile line — slice it like every other
                # post-solve feature (no-op single-tile).
                from .geom_guard import _AIRSIDE_ROLES as _skirt_skip
                from .tile_cut import cut_layout_at_tile_boundaries as \
                    _skirt_tile_cut
                _skirt_tile_cut(
                    layout,
                    current_tile_lat=current_tile_lat,
                    current_tile_lon=current_tile_lon,
                    dem=_projection_dem,
                    skip_roles=_skirt_skip,
                )
                # BRIDGE ↔ SKIRT reconciliation (user 2026-07-07): the
                # boundary→DEM bridge emitted in the feature phase
                # anchors to RAW DEM at a runway end and cannot match
                # the skirt/RESA surface emitted here (KCLT 18R: a ~10 m
                # bridge-vs-skirt step).  The skirt MUST stay last (it
                # bakes the floor from settled pavement), so instead of
                # reordering emission we trim the bridges to the
                # just-emitted skirt/RESA footprint — the skirt owns the
                # terrain transition inside its governed zone; the
                # bridge descends to the DEM only OUTSIDE it.
                from .boundary import \
                    _reconcile_boundary_bridges_with_skirts
                n_bsk = _reconcile_boundary_bridges_with_skirts(layout)
                if n_bsk:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: reconciled {n_bsk} "
                        f"boundary→DEM bridge(s) with the skirt/RESA "
                        f"surface (matched at the runway-end zone).")
        except _GEOM_EXC as exc:
            UI.vprint(1, f"  [pav-builder] {icao}: runway-end skirt "
                         f"emission FAILED: {exc!r}")

        # (The object-bridge causeway plates moved to the PRE-solve
        # layout builder — user ruling R12, ``build_bridge_layout_
        # shapes``: first-class ROLE_BRIDGE_CAUSEWAY shapes born with
        # law values; no late emission remains for feature B.)

        # ── GAP-FILL + DRAINAGE SPINE (slice B pilot, user design
        # 2026-07-09; docs/chain_identity_one_solve_plan.md) ────────────
        # Ground ENCLOSED between pavements grades as ONE unit: boundary
        # = the pavement chains verbatim, interior = a drainage spine
        # splitting the gap into two faces sharing the spine chain.
        # ORDERING: after the skirts (their shapes bound end-adjacent
        # gaps) and BEFORE the adjacent-ground bands — the gap shapes
        # join the bands' static union, so the corridor march skips
        # gap-covered frontage and only true outer edges keep bands.
        try:
            from .gap_fill import emit_gap_fill_spines
            _progress.substep(0.94, "Emitting gap-fill drainage spines")
            n_gap = emit_gap_fill_spines(
                layout, _projection_dem,
                _projection_tile_lat, _projection_tile_lon,
                source_runways=apt.runways)
            if n_gap:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: emitted {n_gap} gap-fill "
                    f"spine face(s) (enclosed between-pavement ground).")
        except _GEOM_EXC as exc:
            UI.vprint(1, f"  [pav-builder] {icao}: gap-fill spine "
                         f"emission FAILED: {exc!r}")

        # ── ENCLOSED-POCKET INTERIOR DEPTH FLOOR (owner ruling
        # 2026-07-19) ───────────────────────────────────────────────────
        # Pockets the gap-fill emitter SKIPPED (over-width, foreign
        # shape, parent straddle) ride raw DEM; clamp their interiors to
        # (pavement lip − GAP_FILL_INTERIOR_FLOOR_DEPTH_M), emitting
        # flat pit-fill patches only where the DEM actually violates.
        # ORDERING: after the spine emission (treated gaps are covered
        # by their faces and skip by coverage) and before the
        # adjacent-ground bands (pit patches join the static union).
        try:
            from .gap_fill import emit_gap_interior_floor
            n_pit = emit_gap_interior_floor(
                layout, _projection_dem,
                _projection_tile_lat, _projection_tile_lon)
            if n_pit:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: emitted {n_pit} enclosed-"
                    f"pocket pit-floor patch(es).")
        except _GEOM_EXC as exc:
            UI.vprint(1, f"  [pav-builder] {icao}: pocket pit-floor "
                         f"emission FAILED: {exc!r}")

        # ── Adjacent-ground LATERAL grade law (slice 3, gate
        # O4_ADJACENT_GROUND_LAW, default OFF) ──────────────────────────
        # The lateral generalization of the runway-end skirt: graded
        # `graded_strip` bands off every terrain-facing airside pavement
        # edge, cut/filled to the lawful corridor
        # (grade_law.adjacent_ground_envelope).  ORDERING: MUST run AFTER
        # emit_runway_end_skirts + its tile_cut (the skirt shapes are in
        # the static block, so the bands clip against them at runway ends
        # and never double-write) and BEFORE the final epsilon-wedge weld
        # (its new constrained edges get welded like every other feature).
        # Imported inside the gate so the module has NO import side effect
        # when the law is off (byte-inert).
        from .config import ADJACENT_GROUND_LAW_ENABLED
        if ADJACENT_GROUND_LAW_ENABLED:
            try:
                from .adjacent_ground import emit_adjacent_ground_bands
                _progress.substep(0.96, "Emitting adjacent-ground bands")
                n_ag = emit_adjacent_ground_bands(
                    layout, _projection_dem,
                    _projection_tile_lat, _projection_tile_lon,
                    source_runways=apt.runways)
                if n_ag:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: emitted {n_ag} "
                        f"adjacent-ground graded-strip/wall polygon(s).")
                    from .geom_guard import _AIRSIDE_ROLES as _ag_skip
                    from .tile_cut import cut_layout_at_tile_boundaries \
                        as _ag_tile_cut
                    _ag_tile_cut(
                        layout,
                        current_tile_lat=current_tile_lat,
                        current_tile_lon=current_tile_lon,
                        dem=_projection_dem,
                        skip_roles=_ag_skip,
                    )
            except _GEOM_EXC as exc:
                UI.vprint(1, f"  [pav-builder] {icao}: adjacent-ground "
                             f"band emission FAILED: {exc!r}")
        _rod_ckpt(layout, "21_skirts_gapfill_bands")

        # ── Obstacle limitation surfaces (gate OLS_CUT_ENABLED) ─────────
        # docs/specs/obstacle-limitation-surfaces-spec.md.  LAST of the
        # terrain-grading emitters by design: OLS is the continuation of
        # the adjacent-ground zone-3 ceiling and of the runway-end
        # corridor, so it must clip against the skirt, the RESA cut and
        # the bands — all of which are already emitted here.  The module
        # is imported INSIDE the gate so it is byte-inert when off.
        from .config import OLS_CUT_ENABLED as _ols_enabled
        if _ols_enabled:
            try:
                from .ols import emit_ols_cuts
                n_ols = emit_ols_cuts(
                    layout, _projection_dem,
                    _projection_tile_lat, _projection_tile_lon,
                    source_runways=apt.runways)
                if n_ols:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: emitted {n_ols} "
                        f"obstacle-limitation-surface cut polygon(s).")
                    # An OLS fan reaches up to a kilometre off a runway
                    # end, so it crosses integer tile lines far more often
                    # than any other feature — cut it like the rest.
                    from .geom_guard import _AIRSIDE_ROLES as _ols_skip
                    from .tile_cut import cut_layout_at_tile_boundaries \
                        as _ols_tile_cut
                    _ols_tile_cut(
                        layout,
                        current_tile_lat=current_tile_lat,
                        current_tile_lon=current_tile_lon,
                        dem=_projection_dem,
                        skip_roles=_ols_skip,
                    )
            except _GEOM_EXC as exc:
                UI.vprint(1, f"  [pav-builder] {icao}: OLS cut emission "
                             f"FAILED: {exc!r}")

        # ── TERRAIN-SIDE BUILDING PADS (gate DSF_OBJECT_OBJECT_PADS) ────
        # docs/specs/per-cluster-object-seating-spec.md section 5.4.  The
        # pads are derived IN-RUN from the object pad frame and THIS
        # build's own solved patch (RULINGS "OBJECT PADS: EMISSION-TIME
        # RELATIVE"); no request sidecar is read.  LAST of the terrain
        # emitters by design and by the spec's ordering clause:
        # "Pads emit AFTER adjacent-ground bands and OLS (they must weld
        # to final feature values), i.e. last in the terrain block,
        # before tile cut."  A pad is clipped by pavement and by every
        # feature above it, so all of them must already be here.  The
        # module is imported INSIDE the gate so it is byte-inert when off.
        from .config import DSF_OBJECT_OBJECT_PADS as _pads_enabled
        if _pads_enabled and _projection_dem is not None:
            # The Phase 2 WORKLIST lives in the patch directory of the
            # tile the driver wrote it for, and it is what names this
            # airport's object packs.  In a tile build that is
            # ``current_tile_*``; in the standalone patch build (no
            # ``tile_dem``, ``current_tile_lat`` None) it is the anchor
            # tile — which is exactly what ``_projection_tile_*`` already
            # resolved to, by the same rule.
            _pad_patch_dir = None
            try:
                import O4_File_Names as _FNAMES
                _pad_patch_dir = _FNAMES.patch_dir(
                    current_tile_lat if current_tile_lat is not None
                    else _projection_tile_lat,
                    current_tile_lon if current_tile_lon is not None
                    else _projection_tile_lon)
            except (ImportError, AttributeError, TypeError, ValueError):
                _pad_patch_dir = None
            try:
                from .object_pads import emit_object_pads
                # DEM tile coords (``_projection_tile_*``) and BUILD tile
                # coords (``current_tile_*``) differ for a cross-tile
                # airport: the sampler must be given the tile its DEM
                # actually covers (the MMOX +17 bug), the tile cut the
                # tile being built.
                n_pad = 0 if _pad_patch_dir is None else emit_object_pads(
                    layout, _projection_dem,
                    _projection_tile_lat, _projection_tile_lon,
                    icao=icao, patch_dir=_pad_patch_dir)
                if n_pad:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: emitted {n_pad} "
                        f"object-pad terrain polygon(s) for "
                        f"{len(layout.object_pad_records)} building pad(s).")
                    # A pad sits beside a building and can straddle an
                    # integer tile line like any other post-solve feature.
                    from .geom_guard import _AIRSIDE_ROLES as _pad_skip
                    from .tile_cut import cut_layout_at_tile_boundaries \
                        as _pad_tile_cut
                    _pad_tile_cut(
                        layout,
                        current_tile_lat=current_tile_lat,
                        current_tile_lon=current_tile_lon,
                        dem=_projection_dem,
                        skip_roles=_pad_skip,
                    )
                    # R19-3: OBJECT PADS RECONCILE WITH THE HOST.  The
                    # pad's target is the OBJECT's rendered/draped ground
                    # and nothing reconciled it with the pavement the
                    # solve produced — HECA's object_pad:56 sat at 105.51
                    # welded to an apron solved to ~93.5, and its values
                    # rode into the apron ring as a 148 % and a 55.6 %
                    # edge.  The SAME machinery the building pads use
                    # (``relevel_pads_to_host_pavement``), by role, at the
                    # pad's own relief budget.  Runs HERE because the pads
                    # do not exist at the post-projection pass where the
                    # building half runs.
                    from .elevation_per_surface.route_profile.anchors \
                        import relevel_pads_to_host_pavement as _relevel
                    from .layout import ROLE_OBJECT_PAD as _ROLE_OPAD
                    _n_opad = _relevel(layout, pad_role=_ROLE_OPAD)
                    if _n_opad:
                        UI.vprint(1,
                            f"  [pav-builder] {icao}: object-pad host "
                            f"level — {_n_opad} pad request(s) adopted "
                            f"the host pavement's solved level.")
            except (_GEOM_EXC + (TypeError, AttributeError, KeyError,
                                 IndexError, OSError)) as exc:
                # LOUD (verbosity 0): unlike a reporter, a failed pad
                # emission CHANGES THE SURFACE — the build continues with
                # terrain that does not meet its buildings, and that must
                # never be a quiet line.  TypeError is in the set on
                # purpose: shapely raises it from the dispatch layer, and
                # it took an OTHH build down on 2026-08-09.
                UI.lvprint(0, f"  [pav-builder] {icao}: object-pad "
                              f"emission FAILED: {exc!r}")

        # Round 9 (user ruling): re-run the non-overlap rule AFTER the
        # adjacent-ground bands — the last feature emitters that can
        # lap onto the object-bridge plates.  Gate off ⇒ no plates ⇒
        # no-op.
        try:
            from .bridges import enforce_bridge_plate_exclusivity
            enforce_bridge_plate_exclusivity(layout)
        except _GEOM_EXC:
            pass

    # FINAL EPSILON-WEDGE WELD (part 30j): the T-vertex weld at
    # ``enforce_conformance(tol=0.01)`` above runs BEFORE the last three
    # geometry-mutating passes — ``_separate_groundside_from_airside``
    # (rebuilds groundside lot rings by re-sampling the DEM-follow
    # outline), ``decimate_emit_nodes`` (drops per-shape ring vertices
    # independently), and the runway-end skirts.  Those passes re-derive
    # a neighbour's outline with a DIFFERENT vertex set, so a groundside
    # lot edge that runs ALONG the boundary ribbon (or a junction edge
    # along a longer neighbour) ends up with a foreign vertex sitting ON
    # the edge WITHOUT a shared node — an EPSILON WEDGE: two constrained
    # edges share one node, run near-parallel (<0.01°), and diverge by
    # sub-millimetre.  Triangle4XP's Ruppert encroachment rule then
    # ping-pongs splits on that near-zero-area sliver down to machine
    # epsilon, exploding the tile (KJQF: the boundary↔groundside_pavement
    # seam alone drove ~2.0M triangles / 55 % of the tile).  Re-running
    # the tight T-vertex weld on the FINAL vertex sets inserts each such
    # on-edge vertex into the edge it lies on, so the two shapes share
    # the node and the sliver vanishes.  TIGHT tolerance (0.01 m): only
    # truly-on-edge nodes (the wedge class sits at 0.000-0.003 m perp);
    # a wider tolerance would bow an edge outward and mint hairline
    # overlaps.  Insert-only at interpolated altitudes (surface-neutral),
    # so it is safe as the last geometry touch.  Measured KJQF isolated
    # triangulation: 1,993,832 → 14,252 tris.
    if compute_elevations:
        from .conformance import (enforce_conformance as _enf_final,
                                  find_conformance_violations as _fcv,
                                  snap_subcm_vertex_twins as _snap_twins,
                                  FINAL_WELD_TOL_M as _FINAL_WELD_TOL_M)
        # SUB-CM TWIN SNAP (2026-07-27): unify mm-apart cross-shape
        # vertex twins (arrangement-grid vs full-precision rings) onto
        # one coordinate BEFORE the weld — the weld inserts T-vertices
        # and would propagate both twins; the solver/validator budget
        # lockstep test catches the drift (CYXY, one edge, 7.7e-5).
        _n_tw_s, _n_tw_v = _snap_twins(layout)
        if _n_tw_v:
            UI.vprint(1,
                f"  [pav-builder] {icao}: snapped {_n_tw_v} sub-cm "
                f"vertex twin(s) across {_n_tw_s} shape(s) onto shared "
                f"coordinates.")
        # DEM + tile frame (the SAME pair the clearance / OLS emitters were
        # driven with above): an inserted T-vertex on a CUT-ONLY shape is
        # bounded by min(lerp, DEM) — the shape's own "cuts never fill" law,
        # which the host-edge lerp cannot see (SPJC runway_end_resa: the
        # weld floated two inserts +2.12 / +2.22 m above the DEM envelope
        # over a depression between two ceiling-limited hosts).
        _n_ews, _n_ewv = _enf_final(layout, tol=_FINAL_WELD_TOL_M,
                                    include_overlay_refs=True,
                                    dem=_projection_dem,
                                    tile_lat=_projection_tile_lat,
                                    tile_lon=_projection_tile_lon)
        if _n_ewv:
            UI.vprint(1,
                f"  [pav-builder] {icao}: final epsilon-wedge weld — "
                f"inserted {_n_ewv} vertex(es) into {_n_ews} shape(s)."
                + ("  *** POST-PROJECTION WELD RESIDUE: these adjacencies "
                   "were minted AFTER the bake and the projection, so NO "
                   "law priced them (spec weld-before-projection-spec.md "
                   "AMENDMENT A1 §1a requires 0 here — the pre-projection "
                   "pass and this one disagree on the weld set). ***"
                   if _WELD_BEFORE_PROJECTION else ""))
        elif _WELD_BEFORE_PROJECTION:
            UI.vprint(1,
                f"  [pav-builder] {icao}: final epsilon-wedge weld: 0 "
                f"insert(s) — the pre-projection weld left nothing to do "
                f"(AMENDMENT A1 §1a verification).")
        # RESIDUAL REPORT (chain identity, 2026-07-09): anything the
        # weld could NOT unify is a divergent chain the tile mesh will
        # Ruppert-refine — name each site so the build log localizes
        # the mint source instead of the bake discovering it.
        try:
            _res_tj, _res_x = _fcv(layout.shapes, tol=0.005)
            if _res_tj or _res_x:
                UI.vprint(1,
                    f"  [pav-builder] WARN {icao}: post-weld residual "
                    f"divergence — {len(_res_tj)} T-junction(s), "
                    f"{len(_res_x)} crossing(s):")
                for _x, _y in (_res_tj + _res_x)[:10]:
                    _la, _lo = layout.m_to_ll(_x, _y)
                    UI.vprint(1, f"      @ {_la:.7f},{_lo:.7f}")
        except _GEOM_EXC:
            pass
        # CROWN FIELD COMPLETION (B4 flip defect 2, 2026-07-15): the
        # adjacent-ground band emit + the epsilon-wedge weld above mint
        # pavement ring vertices AFTER ``final_grade_projection`` ran the
        # crown field extension, so those vertices read crown drop 0 while
        # a flanking solve-time vertex carries a real drop — the emitted
        # validators then measure the pair against the WRONG crown target
        # (CYXY junction: a lawful crown-ramp chord read as a 2.6 % spine
        # step).  Re-run the value-derived extension on the FINAL rings;
        # incremental — solve-time keys and already-extended keys are
        # never recomputed, values no longer move after this point.
        try:
            from .crown import extend_field_to_new_ring_nodes as _crown_ext
            _n_crown_ext = _crown_ext(layout, None)
            if _n_crown_ext:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: crown field completion — "
                    f"{_n_crown_ext} post-weld ring vertex(es) joined the "
                    f"crown drop field.")
        except _GEOM_EXC:
            pass

    # INTERIOR RUNWAY CROSS-EDGE CROWN (Phase 0 hotfix, user 2026-07-07;
    # docs/runway_single_polygon_plan.md): every interior segment cross-edge
    # of a crowned runway is a flat full-width mesh constraint at the dropped
    # (profile − rate·half_width) altitude, so the mesh dives from the
    # centerline ridge to the cross-edge and back at every segment line — a
    # visible centre DIP on every crowned runway.  Insert a centerline node at
    # the runway PROFILE altitude into BOTH abutting sub-rects (same canonical
    # point → the emit consensus welds them) so each cross-section reads as a
    # crown-matching tent.  ABSOLUTE LAST geometry touch (with the probe hook):
    # a mid-edge vertex on the crowned tent is the 3D-collinear class emit
    # decimation removes, so it must arrive after decimation / final
    # projection / skirts.  No-op when crown gated off or runways de-scoped.
    if compute_elevations:
        try:
            from .crown import insert_runway_crossedge_crown_nodes
            _n_xedge = insert_runway_crossedge_crown_nodes(layout)
            if _n_xedge:
                UI.vprint(1, f"  [pav-builder] {icao}: crowned {_n_xedge} "
                             f"interior runway cross-edge(s) (centerline "
                             f"node at profile level).")
        except _GEOM_EXC as exc:
            UI.vprint(1, f"  [pav-builder] {icao}: interior runway "
                         f"cross-edge crown FAILED: {exc!r}")

    # (``O4_PROBE_NODES`` DELETED 2026-08-05.  It was named a diagnostic
    # but INSERTED ring vertices into the emitted layout — an env var that
    # changes emitted bytes is a law gate whatever its name, and the
    # audit's mechanical test ("two builds of the same airport at the same
    # commit must not differ in one emitted byte because of an env var")
    # is what caught it.  ``geom_guard.insert_probe_nodes`` survives as a
    # tool entry point for offline probing of a saved layout.)

    # ABSOLUTE-LAST EDGE DENSIFY (user in-sim finding 2026-07-09): a
    # post-solve pass after the mid-pipeline densifies still mints
    # over-long pavement chords (CYXY: 1,057 m on junction #101 —
    # minted between the emit-stage densify and here).  Run once more
    # as the LAST geometry touch: lerped vertices on a straight solved
    # edge are surface-neutral, both emit decimators are MAX_CHORD-
    # capped so nothing downstream re-thins, and the mesh gets a node
    # every <= 60 m to hold the pavement edge (the user's ruling).
    if compute_elevations:
        try:
            from .conformance import densify_long_edges as _dle3
            from .clearance import _AIRSIDE_PAVEMENT_ROLES as _dle3_r
            _n_dense3 = _dle3(layout, _dle3_r, 60.0)
            if _n_dense3:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: final edge densify — "
                    f"inserted {_n_dense3} vertex(es) on over-60 m "
                    f"pavement edges.")
        except _GEOM_EXC:
            pass
    _rod_ckpt(layout, "22_weld_crown_densify")

    # ── STRIP RECONCILE (seam blend → tear heal → conflict walls) ───────
    # These three passes reconcile the graded_strip / adjacent_ground
    # population against the pavement it grades off.  They are ONE unit
    # with a fixed internal order:
    #   1. Cross-strip SEAM-STEP blend (2026-07-18, SPJC in-sim cliffs):
    #      strips from DIFFERENT emitters (adjacent-ground bands, gap-fill
    #      spines) grading off different hosts hold metre-scale value
    #      disagreements at near-adjacent — or exactly stacked — boundary
    #      vertices, emitting bare terrain cliffs (SPJC: 152 pairs, worst
    #      4.4 m over 1.26 m).  Must run at PIPELINE level over the
    #      COMPLETE strip population (the tearing seams are cross-family).
    #   2. Post-merge tear heal: the hard-merge consensus + the seam blend
    #      can mint sub-metre near-vertical pinches after the
    #      adjacent-ground emit's own final heal ran (that one sees only
    #      its own emit group, and earlier values).
    #   3. Stacked-conflict wall emission (owner ruling 2026-07-19: nodes
    #      are NEVER stacked — same spot ⇒ one merged node, one elevation;
    #      a genuine level change is horizontal wall geometry).  ``to_osm``
    #      hard-merges every coincident claim, so a strip vertex coincident
    #      with a designed-split authority corner (building pad, service
    #      road, groundside — non-donor classes) would be AVERAGED into it,
    #      bending the strip metres at one column.  Resolve those sites as
    #      geometry: retreat the strip edge and emit a retaining_wall face
    #      over the vacated band.
    # ORDER CONTRACT (2 before 3): a wall-retreated vertex is unshared by
    # the heal's tests, and healing after the retreat drops it, springing
    # the strip edge back across the already-emitted wall band (measured
    # CYXY: a 2.16 m² strip∩wall overlap, the zero-tolerance
    # self-overlap invariant).
    #
    # ★ SPEC reference-honesty-and-terracing §2b (owner plan 2026-07-30):
    # the unit used to run BEFORE the LATE final grade projection, so the
    # projection moved the host pavement AFTERWARDS and the strips never
    # re-reconciled — every legitimate pavement move minted a fresh
    # ``graded_strip ↔ adjacent_ground`` tear class (CYXY 0 → 6 under the
    # apron reference surface, HECA 7 → 23).  The spec's remedy is
    # REORDERING, not a second derivation (single-pass principle): the
    # unit MOVES to after the late projection so it reconciles the FINAL
    # pavement.  Gate ``O4_STRIP_RESOLVE_LAST`` (default on); OFF restores
    # the pre-spec position exactly, so gate-off is byte-identical.
    # STANDING (owner 2026-08-05, no gates): the strip reconcile unit
    # runs LAST.  Its internal order — heal, then tear-heal, then
    # retreat+wall — is measured law (``test_strip_heal_law_v4``), and
    # the ``O4_STRIP_RESOLVE_LAST`` gate is DELETED.
    _strip_resolve_last = True

    def _strip_reconcile_passes():
        if not compute_elevations:
            return
        try:
            from .adjacent_ground import blend_cross_strip_seam_steps
            # Unconditional since 2026-07-29 (the ``O4_RASTER_REACH_BAND``
            # gate this was scoped to went with the deleted band engines).
            _n_seam_blend = blend_cross_strip_seam_steps(
                layout.shapes, layout)
            if _n_seam_blend:
                UI.vprint(1, f"  [pav-builder] {icao}: cross-strip "
                             f"seam blend — re-levelled "
                             f"{_n_seam_blend} vertex(es) at "
                             f"strip-to-strip steps.")
        except _GEOM_EXC as _seam_blend_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: cross-strip seam "
                         f"blend failed ({_seam_blend_exc!r}).")
        try:
            from .adjacent_ground import _heal_emitted_band_tears
            # Unconditional since 2026-07-29 (the ``O4_RASTER_REACH_BAND``
            # gate this was scoped to went with the deleted band engines).
            _strip_shapes = [s for s in layout.shapes
                             if s.ref == "adjacent_ground"]
            _n_late_heal = _heal_emitted_band_tears(_strip_shapes, layout)
            if _n_late_heal:
                UI.vprint(1, f"  [pav-builder] {icao}: post-merge "
                             f"tear heal — collapsed pinch edge(s) "
                             f"in {_n_late_heal} strip(s).")
        except _GEOM_EXC as _late_heal_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: post-merge tear "
                         f"heal failed ({_late_heal_exc!r}).")
        try:
            from .adjacent_ground import emit_stacked_conflict_walls
            _n_conflict_walls = emit_stacked_conflict_walls(layout)
            if _n_conflict_walls:
                UI.vprint(1, f"  [pav-builder] {icao}: stacked-conflict "
                             f"walls — {_n_conflict_walls} retaining "
                             f"face(s) at strip-vs-designed-split level "
                             f"changes.")
        except _GEOM_EXC as _conflict_wall_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: stacked-conflict "
                         f"wall emission failed "
                         f"({_conflict_wall_exc!r}).")
        # ★ SINGLE-AUTHORITY EMISSION, §2 — THE LOSER RETREATS.
        # ``layout.to_osm`` now emits the precedence WINNER's value at a
        # contested node (standing law, the consensus mean is retired).
        # That alone would DRAG every losing claimant to the winner's
        # value — the measured groundside-tear cause.  This pass is the
        # other half: a loser beyond ``VERTEX_ALT_MERGE_TOL_M`` retreats
        # into its own interior and the difference ships as a
        # retaining_wall face; a loser within tol adopts.  Runs AFTER
        # the strip pass (which owns the graded_strip population and
        # must see it unretreated) and before the groundside terrace
        # faces, so all three see one committed geometry.
        try:
            from .adjacent_ground import emit_authority_retreat_walls
            _n_auth_walls = emit_authority_retreat_walls(layout)
            if _n_auth_walls:
                UI.vprint(1, f"  [pav-builder] {icao}: single-authority "
                             f"§2 — {_n_auth_walls} retaining face(s) "
                             f"where a losing claimant retreated instead "
                             f"of adopting a value beyond tolerance.")
        except _GEOM_EXC as _auth_wall_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: authority-retreat "
                         f"wall emission failed ({_auth_wall_exc!r}).")
        # ★ GROUNDSIDE TERRACE FACES (owner ruling 2026-07-30, spec §2a).
        # Same doctrine as the stacked-conflict walls above, applied to the
        # groundside lots: where a GRADED RIBBON (pavement or road) meets a
        # lot at a level the lot's own 4 % cap cannot reach, the boundary is
        # a designated TERRACE LINE — the lot retreats and the step ships as
        # a retaining_wall face instead of being averaged into the lot ring
        # by the emit consensus.  Runs LAST of the reconcile unit: the walls
        # it emits must see the strip retreats already committed.
        try:
            from .adjacent_ground import emit_groundside_terrace_walls
            _n_terrace = emit_groundside_terrace_walls(layout)
            if _n_terrace:
                UI.vprint(1, f"  [pav-builder] {icao}: groundside "
                             f"terraces — {_n_terrace} retaining face(s) "
                             f"at graded-ribbon level changes.")
        except _GEOM_EXC as _terrace_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: groundside terrace "
                         f"wall emission failed ({_terrace_exc!r}).")
        # ★ APRON TERRACE JOINT FACES (owner ruling 2026-08-04; spec
        # ``docs/specs/apron-terrace-law-spec.md`` §3).  The declared
        # joints the SOLVE panelized on become geometry here — lower panel
        # retreats ``STACKED_WALL_RETREAT_M``, one ``retaining_wall`` face
        # per joint run — using the same machine and the same constants as
        # the two passes above.  Minted BEFORE interning, so no emit-time
        # consensus can average a declared joint away (the HECA 1,497-row
        # lesson).  No plan on the layout (gate off) ⇒ one getattr.
        try:
            from .elevation_per_surface.route_profile.apron_terrace import (
                emit_terrace_joint_faces)
            _apron_plan = getattr(layout, "_apron_terrace_plan", None)
            _n_joint_faces = emit_terrace_joint_faces(layout, _apron_plan)
            if _n_joint_faces and _apron_plan is not None:
                _ts = _apron_plan.stats
                UI.vprint(1, f"  [pav-builder] {icao}: apron terraces — "
                             f"{_n_joint_faces} joint face(s) covering the "
                             f"cut band, of which "
                             f"{_ts.get('level_covers_emitted', 0)} are "
                             f"LEVEL COVERS (allowance demoted to 0, the "
                             f"slot still closed); "
                             f"{_ts['joints_demoted_level']} joint(s) "
                             f"demoted (flanks settled level); "
                             f"SLOTS LEFT UNCOVERED "
                             f"{_ts.get('slots_uncovered', 0)} (each is a "
                             f"0.6 m hole the pre-solve split cut and no "
                             f"emitter closed); "
                             f"{_ts['station_readings']} station reading(s) "
                             f"on the densified panel boundary, "
                             f"{_ts['stations_over_bound']} over their own "
                             f"declared bound (D2 residue — reported, "
                             f"never clamped), "
                             f"{_ts['joints_sign_flipped']} joint(s) whose "
                             f"low side flips along the run; KEEPOUT FACE "
                             f"DROPS {_ts['faces_dropped_keepout']} "
                             f"(must be 0 — a nonzero count means the "
                             f"plan-time and emit-time predicates "
                             f"diverged: FRAME BUG).")
        except _GEOM_EXC as _apron_terr_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: apron terrace "
                         f"joint emission failed ({_apron_terr_exc!r}).")

    if not _strip_resolve_last:
        _strip_reconcile_passes()

    # ── THE LATE PROJECTION IS RETIRED (owner ruling 2026-08-14) ────────
    # It was added 2026-07-17 for a reason that has since been closed: the
    # passes above (band/gap emission, tile cuts, conformance welds, crown
    # completion, the densify passes) reshaped rings after the projection
    # WITHOUT carrying their values, so the law pairs of the truly final
    # rings drifted over budget.  S1e phase 1 measured that refinement to
    # be VALUE-PRESERVING now (Ortho4XP/tmp/s1e_stage_map.md): those exact
    # stages carry their solved values by interpolation or weld adoption —
    # 17,514 HECA vertices decimated without moving a survivor, 1,148
    # inserts all lerp-or-weld — leaving a RE-PROJECTION CLASS of 8 at
    # HECA and 2 at CYXY, at or below the 0.01 m materiality floor.
    #
    # And running it INSTEAD of the earlier call is strictly worse, because
    # by this point the feature emission has frozen half of airside: the
    # projection sees 20,213 hard nodes at HECA where the earlier call sees
    # 9,791, so it can only nudge what is left.  Measured, both arms built:
    # late-only exits with 8,933 over-cap edges vs the pair's 7,861 and
    # censuses +263 rows against the round-close reference, while mid-only
    # reproduces the reference census EXACTLY at CYXY (328, every family).
    #
    # The pad-host law below still re-asserts: it is the R17-1(b)
    # last-author chain's own step, and it now runs on a surface no
    # projection follows.
    if compute_elevations:

        # ★ THE PAD-HOST LAW RE-ASSERTS AFTER THE TERRAIN EMITTERS
        # (task #16 amendment 1, Fable lead 2026-08-12).  The earlier
        # invocation's own docstring claimed "nothing re-seats the pad
        # afterwards" — measured FALSE: the late projection above re-runs
        # the DEM-biased frontage seat on the final geometry and re-stamps
        # the pad it just levelled.  HECA building114: relevelled to 85.59
        # at the post-projection pass, re-stamped 88.5 here
        # (``who_wrote.py`` node history, 2026-08-12), which is why all
        # THREE r19-1 mechanisms measured exact on the artifact and missed
        # in production — none of them was ever the miss.
        #
        # The remedy is authorship ORDER, not a change to either law: the
        # projection keeps full authority over the terrain (it runs
        # unmodified, and this pass reads the values it just wrote), and
        # the pad-host law re-asserts on top of that surface.  It is
        # convergent by construction — the pad adopts FROM the host and
        # the host body is never touched — so a second application on a
        # settled surface is a no-op, and it stays BEFORE the band seal,
        # which remains the pipeline's last elevation author (R17-1(b);
        # ``tests/test_r17_band_clamp_last_author.py``).
        try:
            from .elevation_per_surface.route_profile.anchors import (
                relevel_pads_to_host_pavement as _relevel_late)
            _n_padhost_late = _relevel_late(layout)
            if _n_padhost_late:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: pad-host level (post-late-"
                    f"projection) — {_n_padhost_late} embedded pad(s) "
                    f"re-levelled to the host pavement the projection "
                    f"actually left.")
            # The object-pad half only where the requests exist by now
            # (they are emitted upstream of here; at an airport with no
            # object pads this is not called at all).
            if getattr(layout, "object_pad_records", None):
                from .layout import ROLE_OBJECT_PAD as _ROLE_OPAD_LATE
                _n_opad_late = _relevel_late(layout,
                                             pad_role=_ROLE_OPAD_LATE)
                if _n_opad_late:
                    UI.vprint(1,
                        f"  [pav-builder] {icao}: object-pad host level "
                        f"(post-late-projection) — {_n_opad_late} pad "
                        f"request(s) re-adopted the host level.")
        except (_GEOM_EXC + (TypeError, AttributeError, KeyError,
                             IndexError)) as _relevel_late_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: post-late-"
                         f"projection pad-host level failed "
                         f"({_relevel_late_exc!r}) — projection values "
                         f"kept.")
    _rod_ckpt(layout, "23_final_projection_late")

    # ★ DRAINAGE-SPINE LAW re-clamp (owner field report 2026-08-02, gate
    # O4_DRAINAGE_SPINE_LAW).  The gap spines were valued against the
    # pavement as it stood at emission; the late projection above is the
    # last pass that moves AIRSIDE pavement, so the spine is re-clamped
    # into its law interval HERE, against the rings that actually ship.
    # No-op with the gate off (and whenever every spine is already inside
    # its interval).  See gap_fill.reclamp_gap_spines for why this is a
    # re-clamp and not the zone rows' foot re-reference.
    try:
        from .gap_fill import reclamp_gap_spines as _reclamp_spines
        _reclamp_spines(layout)
    except _GEOM_EXC as _spine_reclamp_exc:
        UI.vprint(1, f"  [pav-builder] WARN {icao}: drainage-spine "
                     f"re-clamp failed ({_spine_reclamp_exc!r}) — "
                     f"emitted spine values kept.")
    _rod_ckpt(layout, "24_spine_reclamp")

    # ★ SPEC §2b: the strip reconcile unit runs HERE by default — after the
    # last pavement move, so graded strips settle against the pavement that
    # actually ships instead of a value the late projection then invalidates.
    if _strip_resolve_last:
        _strip_reconcile_passes()
    _rod_ckpt(layout, "25_strip_reconcile")

    # ★ THE CLAMP IS THE LAST ELEVATION AUTHOR (round 17 §R17-1(b);
    # docs/specs/round17-vhhh-reclaimed-island-spec.md).  Every emitter,
    # every weld, both final projections and the strip reconcile have
    # run: this is the last point in the pipeline that can see a
    # pavement altitude before ``to_osm`` spells it.  The reach-band
    # clamp runs HERE, on THE band of record (§R17-1(c)) — so the order
    # is structural, not "currently last by luck" — and seals the result
    # so a post-seal author can be NAMED rather than inferred (the seal
    # is verified beside the band report below).
    if compute_elevations:
        try:
            from .elevation_per_surface.solver_primitives import (
                seal_pavement_to_band as _seal_band)
            _seal_band(layout, icao)
        except _GEOM_EXC as _seal_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: final band seal "
                         f"failed ({_seal_exc!r}) — emitted values kept, "
                         f"and the clamp is NOT the last author on this "
                         f"build.")
    # §3.2 ALTERNATION INSTRUMENT (RULINGS 2026-08-25h).  Measured on the
    # FINAL surface, after every writer, and stashed for the sidecar so the
    # census can surface it.  Report-first: it gates nothing.
    try:
        from .groundside import count_edge_alternation as _alt_n
        layout._edge_alternation_n = _alt_n(layout)
        layout._apron_spine_n = len(
            getattr(layout, "_apron_spine_subsegments", None) or [])
        UI.vprint(1,
            f"  [pav-builder] {icao}: edge alternation — "
            f"{layout._edge_alternation_n} adjacent station pair(s) along a "
            f"shared apron/road edge alternate authorship by more than the "
            f"tolerance ({layout._apron_spine_n} apron-spine segment(s) in "
            f"this build).  Report-first, gates nothing (RULINGS 2026-08-25h "
            f"spec section 3.2).")
    except Exception as _alt_exc:                          # pragma: no cover
        UI.vprint(1, f"  [pav-builder] {icao}: edge-alternation instrument "
                     f"FAILED: {_alt_exc!r}")
    _rod_ckpt(layout, "26_band_seal")


    # ★ THE LOUD ERROR (spec ``docs/specs/kill-half-spec.md`` §3) — the
    # POST-SOLVE law, ungated.  Every pass that could move a value has run;
    # the reach band's LAST value fields are the ones this patch was solved
    # against.  If the anchors contradict through any node by more than the
    # materiality floor, the build FAILS here, naming the nodes, their
    # floor/ceiling values and their route distances.  It replaces the
    # deleted quarantine (§2): an inverted band used to be painted over
    # with a blend and hidden from the census; it is now either
    # sub-materiality or a build error.  Deliberately OUTSIDE any
    # ``try``/``except`` — a build that cannot be graded lawfully must not
    # ship a patch.
    if compute_elevations:
        from .elevation_per_surface.building_feasibility import (
            assert_no_final_band_inversion as _assert_band,
            instrument_frame as _band_frame_stamp,
            BAND_NODE_SPACE as _band_node_space,
            FINAL_BAND_INVERSION_TOL_M as _band_tol)
        _n_residual = _assert_band(layout, icao)
        if _n_residual:
            # THE TOLERANCE IS INTERPOLATED, never spelled in the message:
            # a literal here can drift from the constant it claims to
            # report (cycle-7.5 instrument sweep).  ``PASS-with-residual``
            # stays — the LAW layer returned instead of raising, so that
            # verdict is the law's, not this line's.
            UI.vprint(1, f"  [pav-builder] {icao}: final reach band — "
                         f"{_n_residual} sub-materiality inversion(s) "
                         f"(≤ {_band_tol:g} m, "
                         f"FINAL_BAND_INVERSION_TOL_M), "
                         f"PASS-with-residual.  "
                         f"{_band_frame_stamp(layout, _band_node_space)}")

        # ★ BAND MEMBERSHIP — the REPORT half (cycle-5 instrument-fix spec
        # item 7).  The assertion above is INVERSION-ONLY: it fails a build
        # on ``floor > ceiling`` and is silent about a value that simply sits
        # OUTSIDE its band, so a 0.3 m ceiling excess shipped with a
        # "PASS-with-residual" line and was invisible until pytest ran.  This
        # measures membership with the SAME checker the suite uses and says
        # so in the log; it also lands in the patch's sidecar as EVIDENCE, so
        # the question is answerable from the artifacts a day later.
        #
        # NOT A GATE, on purpose: band membership is a derived
        # self-consistency device rather than a citable standard, the census
        # and tests/test_route_band.py hold the verdict, and gating here would
        # stop every build on a population the solve round is still landing.
        # It runs AFTER the assertion because rebuilding the band re-records
        # the inversion rows on the layout — the assertion must read the
        # solve's own field, not this report's rebuild.  Never fatal.
        try:
            from .grade_graph_validate import (
                final_band_excess_report as _band_excess,
                format_final_band_excess as _fmt_band_excess)
            UI.vprint(1, _fmt_band_excess(_band_excess(layout, icao), icao))
        except Exception as _band_excess_exc:
            UI.vprint(1, f"  [pav-builder] WARN {icao}: final band EXCESS "
                         f"report failed ({_band_excess_exc!r}) — membership "
                         f"NOT measured this build.")

        # THE SEAL VERIFICATION (round 17 §R17-1(b)): did anything write
        # a pavement altitude after the clamp?  Reported at zero too —
        # an absent line means the seal did not run.
        try:
            from .elevation_per_surface.solver_primitives import (
                verify_band_seal as _verify_seal)
            _seal_moved = _verify_seal(layout)
            if _seal_moved is None:
                UI.vprint(1, f"  [band-seal] {icao}: NOT SEALED this build "
                             f"— the last-author law is unproven here.")
            elif _seal_moved:
                UI.vprint(1, f"  [band-seal] {icao}: {len(_seal_moved)} "
                             f"shape(s) MOVED AFTER THE CLAMP — the clamp "
                             f"is not the last author: "
                             + "; ".join(f"#{i} {role} {dz:+.3f} m"
                                         for i, role, dz in _seal_moved[:5]))
            else:
                UI.vprint(1, f"  [band-seal] {icao}: SEAL INTACT — no "
                             f"pavement altitude was written after the "
                             f"band clamp.")
        except Exception as _seal_ver_exc:                 # pragma: no cover
            UI.vprint(1, f"  [band-seal] {icao}: seal verification FAILED "
                         f"({_seal_ver_exc!r}).")

        # THE SEAM LEDGER (round 17 §R17-1(a)) — which post-solve pass
        # moved the emitted surface, at the seams the pipeline marks.
        # Gate off (the default) ⇒ one env read.
        try:
            from .mutation_seam_audit import report as _seam_report
            _seam_report(layout, icao)
        except Exception:                                  # pragma: no cover
            pass

        # THE AIRSIDE GEOMETRY SEAM LEDGER (S1e phase 1) — which post-solve
        # pass mutated airside PLAN GEOMETRY, and whether it carried the
        # solved values through the mutation (the RE-PROJECTION CLASS the
        # double-projection retirement drives to zero).  Same seams, same
        # gate-off cost.
        try:
            from .geom_guard import seam_report as _geom_seam_report
            _geom_seam_report(layout, icao)
        except Exception:                                  # pragma: no cover
            pass

    # GROUNDSIDE LAW SEATING — what every groundside ring was seated ON
    # (cycle-6 ingestion, spec Part D).  The requirement is that a ring
    # vertex never takes the raw DEM, so the number to read is the LAW
    # ISLAND count: rings that reached the seat with no weld anchor and
    # no prior field of their own.  Printed even at zero — an absent
    # line means the pass did not run.  Never fatal.
    try:
        from .groundside import report_groundside_law_seat as _gs_seat_rep
        _gs_seat_rep(layout, icao)
    except Exception as _gs_seat_exc:
        UI.vprint(1, f"  [groundside-law-seat] {icao}: report failed "
                     f"({_gs_seat_exc!r}) — seating NOT measured.")

    # §T7's POST-MINT SUPPRESSION — emitter-independent.  The minter
    # never mints inside the mask; this catches what ANY other emitter
    # synthesised there (and the pieces a later split moved onto a bore).
    # Authored pavement over a bore is left alone: the flag rides the
    # shape, so "synthesised" is provenance, not a role guess.
    try:
        from . import covered_span as _covspan
        _covspan.suppress_synthesised_road_pavement(layout, icao)
    except Exception as _cs_exc:                           # pragma: no cover
        UI.vprint(1, f"  [covered-span] {icao}: post-mint suppression "
                     f"FAILED ({_cs_exc!r}) — NOT applied this build.")
    _road_piece_checkpoint(layout, "98_covered_span_suppression")

    # §T4's RIGHT ENDPOINT + the block.  This is the last state before
    # ``layout.to_osm``; the ledger prints one block naming every seam
    # that moved a road-corridor / tunnel piece count.
    _road_piece_checkpoint(layout, "99_end_of_build")
    from .road_piece_ledger import report as _road_piece_report
    _road_piece_report(layout, icao)

    # SHADOW pavement scoring classifier v2 (docs/specs/pavement-scoring-
    # classifier-spec.md): score every final pavement shape against all
    # evidence layers and log agreement with the chain's verdicts.
    # Mutates nothing; the emitted patch is byte-identical.  Must never
    # break a build — but a failure is loudly logged, not swallowed.
    try:
        from .config import PAVEMENT_SCORE_V2 as _ps_mode
        # Runs under "on" too: the enact-slot records describe
        # SLOT-TIME shapes, which later split/merge — this final pass
        # re-scores the EMITTED shapes and records their shapeID
        # (= layout.shapes index, what layout.to_osm tags), so a shape
        # the owner flags in the patch maps 1:1 to its decision.
        if _ps_mode in ("shadow", "on"):
            from .pavement_scoring import shadow_classify as _ps_shadow
            _ps_shadow(layout, icao=icao, xplane_root=xplane_root)
    except Exception as _ps_exc:
        UI.vprint(1, f"  [pav-score] {icao}: shadow scoring failed "
                     f"({type(_ps_exc).__name__}: {_ps_exc}) — build "
                     f"unaffected.")

    # Record this build's actual per-phase and total wall time so the
    # NEXT build of this (or a similarly-sized) airport starts with a
    # trustworthy remaining-time estimate.  Must be the LAST thing
    # before the return: the trailing edge densify and late final
    # grade projection above are real build cost (measured 2026-07-18:
    # ~40 s at OTHH for the late projection alone), and recording
    # before them undercounted the store — and every baseline derived
    # from it.  The emit-phase timer is still open here, so
    # ``phase_seconds()`` attributes the tail to the final phase.
    # Skipped under pytest — the xdist workers run airports under
    # heavy parallel load, which would poison the calibration with
    # inflated times.
    if (compute_elevations and _build_features is not None
            and os.environ.get("PYTEST_CURRENT_TEST") is None):
        try:
            from . import build_time_model as _time_model
            _time_model.record_build(
                icao, _build_features, _progress.phase_seconds(),
                time.time() - _build_started_at)
        except Exception:
            pass

    return layout


# ══════════════════════════════════════════════════════════════════
# Phase-2: elevations
# ══════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────
# DEM + CIFP + main elevation pipeline
# (re-exported from O4_Pavement_Junctions)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# DEM + CIFP + main elevation pipeline
# (re-exported from O4_Pavement_Elevation)
# ──────────────────────────────────────────────────────────────────
from .elevation import (
    _compute_elevations,
)


# ──────────────────────────────────────────────────────────────────
# Airport boundary shape (re-exported from O4_Pavement_Boundary)
# ──────────────────────────────────────────────────────────────────
from .boundary import _emit_airport_boundary_shape


# ──────────────────────────────────────────────────────────────────
# Groundside (curbside / drop-off) pavement
# (re-exported from O4_Pavement_Groundside)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Boundary→DEM bridge polygons (re-exported from O4_Pavement_Boundary)
# ──────────────────────────────────────────────────────────────────
from .boundary import _emit_boundary_dem_bridge


# ──────────────────────────────────────────────────────────────────
# Taxi/road bridges + tunnel portals + depressed-road segments
# (re-exported from O4_Pavement_Bridges; gated by EMIT_BRIDGES_AND_TUNNELS)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Per-shape elevation field + altitude reconciliation
# (re-exported from O4_Pavement_Elevation)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# Elevation finalization (corner buckets, clamp, sliver, overlap)
# (re-exported from O4_Pavement_Elevation)
# ──────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────
# OSM terminal pad extraction (re-exported from O4_Pavement_Terminals)
# ──────────────────────────────────────────────────────────────────
from .terminals import (
    _close_building_outline,
    _cluster_dsf_building_facades,
    _combine_building_sources,
    _extract_osm_terminals,
    _terminal_groundside_zone,
    _terminal_pad_from_building,
    building_pad_accounting,
    clip_pads_by_water,
    repunch_kept_ways_from_pads,
)


# ──────────────────────────────────────────────────────────────────
# Junction-polygon construction
# (re-exported from O4_Pavement_Junctions)
# ──────────────────────────────────────────────────────────────────
from .pavement.junctions import (
    _find_junction_points,
)


# Centerline-slice constants moved to O4_Pavement_Config (MIN_SEGMENT_LEN_M)
# and to O4_Pavement_Centerlines (RDP_SIMPLIFY_TOL_M, SIGNIFICANT_BEND_DEG,
# BEND_CLUSTER_M, GAP_BRIDGE_MAX_M) by slice 3e.
CLOSE_INTERSECTION_M = 200.0  # dead — kept until next cleanup pass
STUB_MAX_LEN_M = 250.0        # dead — kept until next cleanup pass


# ──────────────────────────────────────────────────────────────────
# Same-ref polyline bridging
# (re-exported from O4_Pavement_Centerlines)
# ──────────────────────────────────────────────────────────────────
from .pavement.centerlines import _bridge_same_ref_polylines


# ──────────────────────────────────────────────────────────────────
# OSM aeroway centerline extraction + splitting
# (re-exported from O4_Pavement_Centerlines)
# ──────────────────────────────────────────────────────────────────
from .pavement.centerlines import (
    _extract_osm_taxi_centerlines,
    _find_width_transition_breakpoints,
    _split_centerlines_at_points,
)


