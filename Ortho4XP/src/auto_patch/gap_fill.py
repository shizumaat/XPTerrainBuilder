"""Gap-fill + drainage SPINE emitter (user design ruling 2026-07-09,
docs/chain_identity_one_solve_plan.md "GAP-FILL + DRAINAGE SPINE").

Ground ENCLOSED between pavements — an interior ring of the airside
pavement union, e.g. the hole bounded by a runway, a parallel taxiway and
two connector stubs — is graded as ONE unit:

  * the BOUNDARY is the pavement chains VERBATIM (zero new boundary
    geometry: no buffer / simplify / snap / clean touches any boundary
    coordinate — this codebase Ruppert-explodes on near-parallel
    constrained pairs, one sub-µm pair minting 10^5-10^6 tile triangles,
    so a shared coordinate must stay bit-identical), and
  * the INTERIOR is a single drainage SPINE polyline that splits the gap
    into two half-gap faces sharing the spine chain.  ALL new nodes live
    on the spine; chain identity is free by construction.

DOCTRINE: all grade law comes from ``grade_law`` (the drainage solve
reads ``adjacent_ground_envelope`` per bounding parent — no rule numbers
here); the spine is the ONLY new geometry; the boundary is verbatim.  The
spine is an OPEN WAY floating >= 2 m inside the gap (the 2026-07-09
round-2 redesign): it never touches the ring, so there is no landing
geometry, no T-vertex insertion, and no polygon split.

Behind ``config.GAP_FILL_SPINE_ENABLED`` (env ``O4_GAP_FILL_SPINE``); the
module checks the gate itself so the pipeline wiring stays one call.

SLICE B STAGE B2 (one-solve terrain absorption, gate
``O4_ONE_SOLVE_TERRAIN`` + ``O4_ONE_SOLVE_TERRAIN_GAP_FILL_SPINE``,
docs/slice_b_solver_absorption_design.md §B2): gate-ON, the spine
GEOMETRY is constructed PRE-SOLVE (``construct_gap_fill_presolve``) so
every spine vertex becomes a FREE solver variable — envelope INTERVAL
edges to its two frozen-nearest bounding pavement stations, a DEM seed,
and a ``TAXIWAY_MAX_GRADE_CHANGE_PER_M`` second-difference fairing along
the chain (the solver side lives in ``elevation_per_surface``).  The
analytic valuation below (``_spine_interval`` / ``_drain_target`` /
``_smooth_spine``) DIES gate-ON: the emitter reads the solve's writeback
from ``layout.gap_fill_presolve`` instead.  Face EMISSION (census,
blockers, legacy supersession, verbatim rings) stays at the post-solve
slot in both modes — the blocker subjects (legacy surface_clearance
strips, groundside, ribbons) only exist post-solve, and the emitted ring
must be the pavement chain as it stands AT emission
(conformance-densified) to stay verbatim.
"""
from __future__ import annotations

import math
import os

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union
from shapely.strtree import STRtree

import O4_UI_Utils as UI

# Module-local catch tuple, matching adjacent_ground's convention
# (shapely-domain + ValueError; never built-ins).
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

from .config import (
    ADJACENT_GROUND_LIP_WIDTH_M,
    APRON_SHOULDER_WIDTH_M,
    CLEARANCE_OBSTRUCTION_THRESHOLD_M,
    DRAINAGE_SPINE_LAW_ENABLED,
    GAP_FILL_INTERIOR_FLOOR_DEPTH_M,
    GAP_FILL_INTERIOR_FLOOR_ENABLED,
    GAP_FILL_INTERIOR_RINGS_ENABLED,
    GAP_FILL_MAX_WIDTH_M,
    GAP_FILL_MIN_AREA_M2,
    GAP_FILL_RIM_POCKET_GRADED_FRACTION,
    GAP_FILL_RIM_POCKETS_ENABLED,
    GAP_FILL_SPINE_ENABLED,
    GAP_FILL_SPINE_STEP_M,
    GAP_PAVEMENT_CONFORM_MARGIN_M,
    OPEN_FRONTAGE_CLOSE_M,
    POCKET_COLLAR_RINGS_ENABLED,
    RUNWAY_STRIP_HALF_WIDTH_BY_CODE,
    TILE_CUT_HALF_WIDTH_M,
    runway_code_number,
    taxiway_strip_graded_half_width_for_letter,
)
from .grade_law import (adjacent_ground_envelope, drainage_spine_envelope,
                        drainage_spine_parents)

# THE spine envelope, chosen ONCE for the whole module (owner field report
# 2026-08-02, gate ``O4_DRAINAGE_SPINE_LAW``): with the gate on, both the
# analytic interval and the solver's frozen parent specs read the
# ENCLOSED-INTERIOR law — ceiling at most ``DRAINAGE_SPINE_MIN_FALL_M``
# below each bounding pavement edge, corridor floor unchanged.  Gate off ⇒
# the lateral corridor verbatim, i.e. byte-identical.  A single binding is
# what keeps the two readers in lockstep: there is no site where one law
# could be selected and the other not.
_spine_envelope = (drainage_spine_envelope if DRAINAGE_SPINE_LAW_ENABLED
                   else adjacent_ground_envelope)
from .layout import (
    BuiltShape,
    R_EARTH,
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_CROSS_CONNECTOR,
    ROLE_GRADED_STRIP,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_STUB,
    ROLE_TUNNEL_RAMP,
    ROLE_TUNNEL_TRENCH,
    RUNWAY_END_REGIME_REFS,
    taxi_shape_code_letter,
)
from .clearance import (
    _AIRSIDE_PAVEMENT_ROLES,
    _edge_interp_alt,
    _nearest_pav_alt,
    _open_coords,
)
# THE STAGE TAG (staged-solve round).  A gap-fill spine's stage is its
# ENCLOSURE HOST's, decided here at mint and carried on the pre-solve
# entry — ``solver_primitives._build_gap_spine_constraints`` stamps the
# constraint from it and never guesses.
from .solve_stage import STAGE_A as _STAGE_A, STAGE_B as _STAGE_B
from .emit_decimate import _key
from .enclaves import (
    ENCLAVE_SURROUND_ROLES,
    enclave_covering,
    is_pocket_width,
)
from .geom_safe import min_rotated_rect

__all__ = ["emit_gap_fill_spines", "construct_gap_fill_presolve"]

_GAP_FILL_REF = "gap_fill_spine"
# Pit-fill patches from the enclosed-pocket interior depth floor
# (``emit_gap_interior_floor``, owner ruling 2026-07-19).
_GAP_PIT_FLOOR_REF = "gap_pit_floor"
# Open-frontage corridor faces carry their OWN ref so they are
# distinguishable from enclosed-gap faces and from the legacy
# ``adjacent_ground`` bands they supersede (the DEM-free tear sentinel
# in tools/check_grade.py keys on ref=="adjacent_ground", so a corridor
# face is never mis-flagged as a band tear — and, having no band-vs-band
# clip seams, it produces none).
_OPEN_FRONTAGE_REF = "open_frontage_spine"
# Standoff buffered around every foreign shape before it is subtracted
# from the corridor closing (the groundside no-weld ruling, 2026-07-09:
# grading strips keep >= 1 m off groundside pavement + buildings).  A
# corridor slab therefore never welds onto a foreign shape; the corridor
# band / daylight law owns the 1 m collar.
_OPEN_FRONTAGE_FOREIGN_STANDOFF_M = 1.0
# TUNNEL BLOCKERS (R6, owner spec round4-othh-fixes 2026-08-10).  A
# below-grade tunnel ramp / trench / portal wall is NOT enclave-interior
# content the enclave law re-verdicts: it is a law-cut hole in the
# ground with its own profile, and a drainage spine laid across it runs
# THROUGH the ramp (OTHH S6, measured on 1.0.229).  ``_enclave_exempt``
# therefore keeps them as blockers on both blocker sets, so the gap face
# is never graded over them and no spine enters their footprint.
# ``tunnel_ramp`` / ``tunnel_trench`` are ROLES; the portal walls carry
# ``role=retaining_wall`` with ``ref="tunnel_wall"`` (bridges.py), and
# only THAT ref is pulled out — a plain retaining wall stays exempt (the
# 2026-08-07 HECA specimen this exemption was minted for).
_TUNNEL_BLOCKER_ROLES = frozenset((ROLE_TUNNEL_RAMP, ROLE_TUNNEL_TRENCH))
_TUNNEL_BLOCKER_REFS = frozenset(("tunnel_wall",))
# SERVICE-ROAD BLOCKERS (owner ruling 2026-08-15): gap-fill spines and
# drainage must STOP at a service road, never run through it.  A service
# road / service junction inside an enclave pocket therefore stays a
# blocker on the HARD set too — which routes a road-crossed pocket into
# the R19-2 subdivision (the roads BOUND the residual pockets exactly as
# they do in the non-enclave path) instead of letting ``_build_spine``
# march through the road pavement (measured at HECA patch
# HECA_20260815T1329: 31 gap faces burying 21,099 m² of road pavement,
# 9 drainage spines running 108 m inside roads).
# OPEN QUESTION (not ruled 2026-08-15): ``groundside_pavement`` is NOT
# in this set — the owner's ruling names service roads only; groundside
# pavement inside an enclave keeps its exemption until ruled otherwise.
_SERVICE_ROAD_BLOCKER_ROLES = frozenset((
    ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION))
# ── R19-2: THE SUBDIVIDERS OF AN ENCLOSED HOLE ───────────────────────
# An ENCLOSED hole (an interior ring of the airside union — it touches
# no coverage-box edge by construction) that the width test refuses is
# not one wide field: the groundside and service surfaces standing IN it
# already divide it into pockets, each of them narrow.  HECA's 22,483 m²
# airside hole is refused at a 188.5 m min-rect short side — 8 % over
# ``GAP_FILL_MAX_WIDTH_M`` — and every residual face between its
# groundside/service shapes is far under it.  Those shapes bound the
# ground the way pavement does; subdividing by them is not a cap raise
# (the cap NEVER moves — a blanket raise would take the airport's 3.40
# km² infield with it) but a truer reading of what the face is.
_POCKET_SUBDIVIDER_ROLES = frozenset((
    ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
))
# A cross-section thinner than this is not a gradeable half-gap — the
# station is a pinch of the ring, not the drainage body.
_MIN_CROSS_WIDTH_M = 2.0
# Target the corridor DRAINAGE offset a quarter of the way UP from the
# floor: fall from both pavement edges at >= the law minimum without
# cutting to the 5 % floor (user design ruling 2026-07-09).
_DRAIN_FROM_CEILING = 0.25
# Longitudinal relaxation sweeps over the spine (second-difference,
# endpoints pinned to their boundary pavement values).
_SMOOTH_SWEEPS = 20

# ── GAP INTERIOR RING constants (ratified 2026-07-11, REVISED per the
# in-sim round-8 ruling: rings are ALWAYS complete closed loops; the
# gating lives in the VALUES, not the geometry) ────────────────────────
# A ring station whose clamped value sits within this of the terrain is
# a VALUE NO-OP (the ring rides the terrain there — invisible in the
# mesh).  A gap where EVERY station of BOTH rings is a no-op skips its
# rings entirely (the per-gap economy gate — all-or-nothing, never
# per-arc: arc ends read as ragged walls in the sim, round-8 verdict).
_RING_VALUE_NOOP_TOLERANCE_M = 0.05
# Minimum clearance a ring node keeps from the gap boundary, the spine
# and every other ring chain — the near-parallel Ruppert guard (the
# codebase's spine standoff is 2.0 m; rings reuse the same class of
# floor, slightly tighter so a lip ring at 3 m offset survives corners).
_RING_MIN_CLEARANCE_M = 1.5
# Minimum spacing between consecutive accepted ring nodes (corner fans
# converge inward offsets; closer nodes are dropped).
_RING_MIN_NODE_SPACING_M = 2.0
# ROUND-9 (Noah 2026-07-14): the rings are boundaries of TRUE POLYGON
# INWARD OFFSETS (the round-8 per-station offset walk self-crossed at
# boundary concavities and parent-width transitions — 9 of 27 CYXY
# loops).  Region smoothing = morphological opening + closing at this
# minimum-feature radius: fingers/spikes thinner than it are dropped,
# boundary notches narrower than it are NOT traced (calibrated against
# Noah's hand-edited reference loop, CYXY_auto_MOD way -68615 — the
# reference expresses GEOMETRY only).
_RING_MIN_FEATURE_RADIUS_M = 10.0
# Hard clearance collar against the gap boundary: every smoothed ring
# region is clipped to gap.buffer(-this), so no notch-fill can push a
# loop into the zero-lens danger zone at the pavement chain.
_RING_BOUNDARY_CLEARANCE_M = 1.6
# Maximum along-ring VALUE drop per meter (max-relaxation raising the
# low side, capped at each node's point-law ceiling): the point-law
# BOUNDS step where the governing parent switches family (a 75 m
# runway band floor sits meters below a 12.5 m junction band floor),
# and terrain alone cannot be asked to absorb that step between two
# 15 m stations (round-8: no cliffs ALONG the ring).  5 % = the band
# maximum down slope — the steepest lawful graded transition.
_RING_ALONG_BENCH_SLOPE = 0.05
# Ring 1 (lip) is suppressed when the effective ring-2 offset comes
# within this of the lip offset — two near-coincident parallel
# breaklines are exactly the lens class the zero-lens law forbids.
_RING_MIN_SEPARATION_M = 2.0
# Coincidence tolerance (NOT a rule number) for deciding that a pit-floor
# rim vertex sits ON the ring-2 core boundary.  The pit region is clipped
# EXACTLY against that boundary, so a shared vertex is exact up to
# shapely's own arithmetic; this is the float slack, nothing more.
_PIT_RIM_WELD_TOL_M = 0.01

# ── TWO-NEAREST-PARENT INDEX search window (OPT-1) ────────────────────
# NOT rule numbers — search-window sizes only.  ``_AirsideNearestIndex``
# DOUBLES its query radius until the candidate set provably contains the
# two nearest parents, so the SELECTION is exact for any value here; the
# constants only trade tree queries against candidate-set size.  The seed
# adapts to the previous station's answer (gap stations are spatially
# coherent), floored/capped so it can neither collapse to a useless
# window nor blow up into a full scan.
_NEAREST_SEED_RADIUS_M = 48.0
_NEAREST_MIN_SEED_RADIUS_M = 8.0
_NEAREST_MAX_SEED_RADIUS_M = 4096.0
# Hard bound on the doubling escalation.  Unreachable for any finite
# station (8 m x 2^64 covers the solar system, and the whole-list exit
# fires long before) — it exists so a non-finite coordinate degrades to
# the full scan instead of spinning.
_NEAREST_MAX_DOUBLINGS = 64

_RUNWAY_ROLES = (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)
_APRON_ROLES = (ROLE_APRON,)
_TAXIWAY_ROLES = (
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
)


def _unit(dx: float, dy: float):
    d = math.hypot(dx, dy)
    if d < 1e-12:
        return None
    return (dx / d, dy / d)


def _long_side_length(polygon) -> float:
    """Length of the polygon's longest vertex chord — the runway
    length proxy for code-number keying (no source_runways here)."""
    try:
        ring = list(polygon.exterior.coords)
    except _GEOM_EXC:
        return 0.0
    best = 0.0
    n = len(ring)
    for i in range(n):
        xi, yi = ring[i]
        for j in range(i + 1, n):
            xj, yj = ring[j]
            d = math.hypot(xj - xi, yj - yi)
            if d > best:
                best = d
    return best


def _parent_family_code(layout, shape):
    """Resolve ``(role, code_number, code_letter)`` for a bounding
    pavement ``shape`` so ``adjacent_ground_envelope`` picks the family's
    corridor.  Replicates adjacent_ground's ``_family_params`` role/code
    logic MINIMALLY — that helper needs ``rw_axes`` built from
    ``source_runways``, which this emitter's signature does not receive,
    so the runway code number is read from the shape's OWN long-chord
    length via ``runway_code_number`` instead of a row-100 axis.  The
    envelope keys runways by code NUMBER and taxiways by code LETTER; the
    shape's actual role string is passed through (it already lives in the
    envelope's per-family role sets)."""
    role = shape.role
    if role in _RUNWAY_ROLES:
        return (role, runway_code_number(_long_side_length(shape.polygon)),
                None)
    if role in _APRON_ROLES:
        return (role, None, None)
    if role in _TAXIWAY_ROLES:
        return (role, None, taxi_shape_code_letter(layout, shape))
    return (role, None, None)


def _parent_flat_value(parent):
    """A gap parent's FLAT value — the primary representation for
    building pads (user ruling: buildings are flat; the ROLE_BUILDING
    writeback stores avg of corners → ``altitude``) and the FALLBACK for
    any parent whose per-vertex ``node_altitudes`` do not align with the
    ring being registered (per-vertex values are preferred at the call
    site — runway-end skirts carry the governed runway-end profile
    per vertex)."""
    if getattr(parent, "altitude", None) is not None:
        return float(parent.altitude)
    na = getattr(parent, "node_altitudes", None)
    if na:
        vals = [v for v in na if v is not None]
        if vals:
            return float(sum(vals) / len(vals))
    return None


def _face_is_verbatim(face_poly, chain_keys) -> bool:
    """True when EVERY boundary vertex of ``face_poly`` (exterior and any
    interior parent ring) is a VERBATIM pavement-or-parent ring vertex —
    chain identity.  A residual difference that mints a foreign crossing
    point (a parent edge cutting a pavement edge mid-span) fails this:
    that vertex is new boundary geometry and would Ruppert-explode, so
    the part is blocked."""
    try:
        rings = [face_poly.exterior] + list(face_poly.interiors)
    except _GEOM_EXC:
        return False
    for ring in rings:
        for vx, vy in ring.coords:
            if _key(vx, vy) not in chain_keys:
                return False
    return True


def _parent_residual_faces(gap_poly, parents, chain_keys):
    """The gradeable face(s) for one enclosed gap.  With no bounding
    parent inside it is the gap itself.  With parent shape(s) inside —
    a BUILDING PAD (flat value authority, user design 2026-07-09 queue
    item 5) or a RUNWAY-END SKIRT (NON-flat value authority whose ring
    vertices carry the governed inverse-RESA runway-end profile,
    supervisor follow-up 2026-07-09) — the parent BOUNDS the gap the
    way pavement does, and the gradeable ground is the RESIDUAL
    ``gap minus parent_union``, split into its chain-safe parts:

      * a parent that FILLS its hole leaves no residual above
        ``GAP_FILL_MIN_AREA_M2`` → the gap lawfully vanishes (the
        parent surface IS the ground there — nothing left to drain);
      * a wholly-interior parent leaves an ANNULAR residual whose inner
        ring is the parent chain VERBATIM (the emitted face covers the
        parent footprint; the parent's own way prevails there by
        X-Plane seed-region processing, the junction-hole precedent in
        to_osm — the parent shape itself still emits exactly as today);
      * a residual part whose boundary is NOT verbatim (a
        difference-minted crossing vertex — e.g. a parent ring cutting
        a pavement edge mid-span) is blocked (zero-lens law).

    Every candidate + skip is logged (no silent skip)."""
    parents_in = []
    for p in parents:
        try:
            if gap_poly.intersection(p.polygon).area > 1.0:
                parents_in.append(p)
        except _GEOM_EXC:
            continue
    if not parents_in:
        return [gap_poly]
    try:
        parent_union = unary_union([p.polygon for p in parents_in])
        residual = gap_poly.difference(parent_union)
    except _GEOM_EXC:
        residual = None
    parts = ([] if residual is None or residual.is_empty
             else [residual] if residual.geom_type == "Polygon"
             else [g for g in getattr(residual, "geoms", [])
                   if g.geom_type == "Polygon"])
    refs = ",".join(str(getattr(p, "ref", None) or p.role)
                    for p in parents_in)
    residual_area = sum(g.area for g in parts)
    _c = gap_poly.centroid
    if residual_area < GAP_FILL_MIN_AREA_M2:
        UI.vprint(1, f"  [gap-fill] parent fills gap (residual "
                     f"{residual_area:.0f} < {GAP_FILL_MIN_AREA_M2:.0f} m2, "
                     f"parent(s)={refs}) — the parent IS the surface; "
                     f"centroid=({_c.x:.0f},{_c.y:.0f}) skipped.")
        return []
    faces = []
    for g in parts:
        if g.is_empty or g.area < GAP_FILL_MIN_AREA_M2:
            continue
        if not _face_is_verbatim(g, chain_keys):
            _cc = g.centroid
            UI.vprint(1, f"  [gap-fill] parent-residual part non-verbatim "
                         f"boundary (parent(s)={refs}) area={g.area:.0f} m2 "
                         f"centroid=({_cc.x:.0f},{_cc.y:.0f}) — blocked.")
            continue
        faces.append(g)
    UI.vprint(1, f"  [gap-fill] parent-bounded gap (parent(s)={refs}): "
                 f"{len(faces)} residual face(s) of {residual_area:.0f} m2 "
                 f"centroid=({_c.x:.0f},{_c.y:.0f}).")
    return faces


def _veto_is_only_subdividers(layout, gap_poly, blockers) -> bool:
    """R19-2 — True when every shape vetoing this ENCLOSED hole is one of
    its own SUBDIVIDERS and the hole is over the width cap.

    The foreign-shape veto says "a foreign shape inside the gap means
    the corridor bands own it".  That is right for a shape the gap law
    cannot read — a tunnel, a crossing zone, a partial-straddle strip.
    It is NOT right for the groundside/service surfaces standing in an
    enclosed hole: they BOUND the ground the way a building pad does
    (``_parent_residual_faces``), and the hole between them is exactly
    the pocket the drainage law exists for.

    The deferral is deliberately NARROW — both conditions, always:

      * every blocker overlapping the gap is a subdivider role.  One
        tunnel, one crossing zone, one shape of any other class and the
        veto stands unchanged.

    A vetoed gap emits NOTHING today, so deferring the veto can only ADD
    the faces the law says are owed — and the caller's own guard (every
    residual pocket must be under ``GAP_FILL_MAX_WIDTH_M``) is what
    keeps a WIDE region from being subdivided into the pocket-collar
    machinery instead.
    """
    hit = []
    for _oid, op in blockers:
        try:
            if gap_poly.intersection(op).area > 1.0:
                hit.append(_oid)
        except _GEOM_EXC:
            return False
    if not hit:
        return False
    by_id = {id(sh): sh for sh in (getattr(layout, "shapes", ()) or ())}
    for _oid in hit:
        sh = by_id.get(_oid)
        if sh is None or sh.role not in _POCKET_SUBDIVIDER_ROLES:
            return False
    return True


def _subdivide_enclosed_face(layout, face_poly, chain_keys):
    """R19-2 — the residual faces of an ENCLOSED hole, split by the
    groundside/service shapes standing inside it.  ``[]`` when nothing
    inside subdivides it, or when no residual part is chain-safe.

    Same law as ``_parent_residual_faces``: the shapes BOUND the ground
    the way pavement does, the gradeable ground is the residual, and a
    part whose boundary carries a difference-minted crossing vertex is
    BLOCKED (the zero-lens law).  The chain here is the face's own
    boundary plus the subdividers' rings, which are emitted geometry in
    their own right.

    This never raises ``GAP_FILL_MAX_WIDTH_M``: every residual part goes
    back through the SAME width test.  A hole whose parts are still wide
    is still refused."""
    subs = []
    for sh in (getattr(layout, "shapes", ()) or ()):
        if sh.role not in _POCKET_SUBDIVIDER_ROLES:
            continue
        if sh.polygon is None or sh.polygon.is_empty:
            continue
        if sh.polygon.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        try:
            if face_poly.intersection(sh.polygon).area > 1.0:
                subs.append(sh)
        except _GEOM_EXC:
            continue
    if not subs:
        return []
    keys = set(chain_keys or ())
    for (vx, vy) in _open_coords(face_poly):
        keys.add(_key(vx, vy))
    for sh in subs:
        geoms = ([sh.polygon] if sh.polygon.geom_type == "Polygon"
                 else list(sh.polygon.geoms))
        for g in geoms:
            try:
                for (vx, vy) in g.exterior.coords:
                    keys.add(_key(vx, vy))
            except _GEOM_EXC:
                continue
    try:
        residual = face_poly.difference(
            unary_union([sh.polygon for sh in subs]))
    except _GEOM_EXC:
        return []
    parts = ([] if residual is None or residual.is_empty
             else [residual] if residual.geom_type == "Polygon"
             else [g for g in getattr(residual, "geoms", [])
                   if g.geom_type == "Polygon"])
    refs = ",".join(str(getattr(sh, "ref", None) or sh.role)
                    for sh in subs)
    faces = []
    for g in parts:
        if g.is_empty or g.area < GAP_FILL_MIN_AREA_M2:
            continue
        if not _face_is_verbatim(g, keys):
            _cc = g.centroid
            UI.vprint(1, f"  [gap-fill] enclosed-hole residual part "
                         f"non-verbatim boundary area={g.area:.0f} m2 "
                         f"centroid=({_cc.x:.0f},{_cc.y:.0f}) — blocked.")
            continue
        faces.append(g)
    _c = face_poly.centroid
    UI.vprint(1, f"  [gap-fill] enclosed hole subdivided by {len(subs)} "
                 f"groundside/service shape(s) ({refs}): {len(faces)} "
                 f"residual face(s) of {sum(g.area for g in faces):.0f} m2 "
                 f"centroid=({_c.x:.0f},{_c.y:.0f}).")
    return faces


def _region_is_everywhere_narrower(poly, width_m) -> bool:
    """TRUE WIDTH: no point of ``poly`` is more than ``width_m`` / 2 from
    its boundary (an erosion by the half-width leaves nothing).

    The MRR short side — the enclosed law's gate — measures the smallest
    ENCLOSING rectangle, which over-reports a CURVED region badly: HECA's
    excavation-rim pocket at the owner's knoll is nowhere wider than
    ~60 m (it erodes to nothing at 30 m) and yet its min-rotated-rect
    short side reads 399 m, because the sliver wraps the apron rim.  The
    ruling-3 pockets are rim-following by construction, so they are gated
    on this instead — and ONLY they are: the enclosed holes keep the MRR
    gate they were measured under.
    """
    try:
        return poly.buffer(-0.5 * float(width_m)).is_empty
    except _GEOM_EXC:                                  # pragma: no cover
        return False


def _grade_face(layout, airside, face_poly, step, registry,
                dem=None, tile_lat=None, tile_lon=None,
                rw_axes=None, width_rule=None) -> int:
    """Area/width-gate ONE gradeable face (a whole enclosed gap, or a
    pad-residual part) and emit its drainage spine.  Logs the candidate
    and any lawful width/area skip.  Returns the emitted face count.

    ``dem``/``tile_lat``/``tile_lon``/``rw_axes`` feed the interior-ring
    construction (gate ``O4_GAP_FILL_INTERIOR_RINGS``); with ``dem``
    None (the open-frontage path, synthetic fixtures without terrain)
    the violation trigger cannot fire and no ring emits."""
    if face_poly.is_empty or not face_poly.is_valid:
        return 0
    if face_poly.area < GAP_FILL_MIN_AREA_M2:
        return 0
    try:
        axes = _mrr_axes(min_rotated_rect(face_poly))
    except _GEOM_EXC:
        return 0
    if axes is None or axes[1] is None:
        return 0
    short_side, long_dir, long_len = axes
    _c = face_poly.centroid
    UI.vprint(1, f"  [gap-fill] candidate area="
                 f"{face_poly.area:.0f} m2 short="
                 f"{short_side:.0f} centroid=({_c.x:.0f},{_c.y:.0f})")
    if short_side > GAP_FILL_MAX_WIDTH_M:
        # A caller with its own width law (ruling 3's rim pockets, whose
        # curved slivers the MRR over-reports) is consulted before the
        # skip. It never reaches the collar branch either way: the collar
        # is the ENCLOSED width-skip class, selected structurally.
        if width_rule is not None:
            if width_rule(face_poly):
                return _emit_one_gap(layout, airside, face_poly, long_dir,
                                     long_len, step, registry, dem=dem,
                                     tile_lat=tile_lat, tile_lon=tile_lon,
                                     rw_axes=rw_axes)
            UI.vprint(1, f"  [rim-pocket] skipped pocket (wider than "
                         f"{GAP_FILL_MAX_WIDTH_M:.0f} m by its own width "
                         f"law) area={face_poly.area:.0f} m2")
            return 0
        UI.vprint(1, f"  [gap-fill] skipped gap (width "
                     f"{short_side:.0f} > {GAP_FILL_MAX_WIDTH_M:.0f})"
                     f" area={face_poly.area:.0f} m2")
        # ARC B1 (owner ruling 2026-07-24): a WIDTH-skipped pocket still
        # owes its two closed drainage collar rings — this is the ONLY
        # skip class the collar covers, and it is selected structurally
        # (foreign-shape / partial-straddle pockets never reach here).
        if POCKET_COLLAR_RINGS_ENABLED and dem is not None:
            _emit_pocket_collar_rings(layout, airside, face_poly, dem,
                                      tile_lat, tile_lon, rw_axes, step)
        return 0
    return _emit_one_gap(layout, airside, face_poly, long_dir, long_len,
                         step, registry, dem=dem, tile_lat=tile_lat,
                         tile_lon=tile_lon, rw_axes=rw_axes)


def _mrr_axes(mrr):
    """``(short_side_m, long_unit_dir, long_side_m)`` of a minimum
    rotated rectangle polygon."""
    coords = list(mrr.exterior.coords)
    if len(coords) < 4:
        return None
    p0, p1, p2 = coords[0], coords[1], coords[2]
    e1 = (p1[0] - p0[0], p1[1] - p0[1])
    e2 = (p2[0] - p1[0], p2[1] - p1[1])
    l1 = math.hypot(*e1)
    l2 = math.hypot(*e2)
    if l1 >= l2:
        long_dir = _unit(*e1)
        return (l2, long_dir, l1)
    long_dir = _unit(*e2)
    return (l1, long_dir, l2)


def _build_spine(gap_poly, long_dir, long_len, step):
    """March cross-sections along the long axis, take each widest
    section's midpoint, then extend both ends exactly onto the gap ring.
    Returns the ordered spine coordinate list (>= 3 points), or None."""
    ux, uy = long_dir
    vx, vy = (-uy, ux)                    # perpendicular unit
    cen = gap_poly.centroid
    cx, cy = cen.x, cen.y
    span = long_len + step               # half-length of a cutting line
    try:
        ring = list(gap_poly.exterior.coords)
    except _GEOM_EXC:
        return None
    projs = [(x - cx) * ux + (y - cy) * uy for x, y in ring]
    s_min, s_max = min(projs), max(projs)
    mids: list[tuple[float, float]] = []
    n_st = int(math.floor((s_max - s_min) / step))
    for i in range(n_st + 1):
        s = s_min + i * step
        bx, by = cx + ux * s, cy + uy * s
        cutter = LineString([(bx - vx * span, by - vy * span),
                             (bx + vx * span, by + vy * span)])
        try:
            inter = cutter.intersection(gap_poly)
        except _GEOM_EXC:
            continue
        segs = ([inter] if inter.geom_type == "LineString"
                else [g for g in getattr(inter, "geoms", [])
                      if g.geom_type == "LineString"])
        segs = [g for g in segs if not g.is_empty]
        if not segs:
            continue
        widest = max(segs, key=lambda g: g.length)
        if widest.length < _MIN_CROSS_WIDTH_M:
            continue
        mid = widest.interpolate(0.5, normalized=True)
        mids.append((mid.x, mid.y))
    if len(mids) < 2:
        return None
    # OPEN-WAY SPINE (user design 2026-07-09, round 2): the spine
    # never touches the gap boundary — it floats inside as an open
    # constrained way (the crown-spine mechanism), so the boundary
    # stays the pavement chain verbatim EVERYWHERE, there is no
    # landing geometry (the shallow-landing 96 mm sliver class dies
    # by construction), no polygon split, and U-shaped / partially
    # open gaps need no special casing.  Hold the spine ends >= 2 m
    # off the ring.
    if list(gap_poly.interiors):
        # ANNULAR face (a gap parent — building pad / runway-end skirt
        # — wholly inside): the parent's ring is a constrained chain
        # too, so EVERY spine point keeps >= 2 m off the FULL boundary
        # (exterior + parent rings) — a spine vertex hugging the parent
        # ring would mint a near-parallel pair.  Segments that would
        # cross the parent hole are handled by the sub-chain split at
        # emission.  Faces WITHOUT interiors keep the original
        # end-trim path byte-identical.
        ring_ls = gap_poly.boundary
        out = [p for p in mids if ring_ls.distance(Point(p)) >= 2.0]
    else:
        ring_ls = gap_poly.exterior
        out = [p for p in mids]
        while out and ring_ls.distance(Point(out[0])) < 2.0:
            out = out[1:]
        while out and ring_ls.distance(Point(out[-1])) < 2.0:
            out = out[:-1]
    # De-duplicate consecutive coincident points.
    dedup: list[tuple[float, float]] = []
    for p in out:
        if not dedup or math.hypot(p[0] - dedup[-1][0],
                                   p[1] - dedup[-1][1]) > 1e-6:
            dedup.append(p)
    return dedup if len(dedup) >= 2 else None


class _AirsideNearestIndex:
    """EXACT two-nearest-parent selector over one ``airside`` list.

    OPT-1 (2026-07-24, pure performance — emitted values must not move).
    Three call sites pick a station's two bounding pavement parents
    (``_spine_interval``, ``_build_collar_rings._point_interval``,
    ``_freeze_spine_parent_specs``) and all three used to walk EVERY
    airside shape per station::

        for s in airside:
            d = s.polygon.exterior.distance(p)

    ``.exterior`` REBUILDS the ring object on every access, so that walk
    cost one ring construction per shape per station on top of the
    distance itself (HECA profile: 8.7 M ``get_exterior_ring`` calls,
    6.3 s tottime — ~91 % of the collar-ring pass).

    This index hoists the exteriors ONCE per pass and answers each
    station from an STRtree bbox prefilter with a DOUBLING radius.  It is
    not an approximation:

      * the query square of half-width ``r`` about the station CONTAINS
        the disc of radius ``r``, so every shape within ``r`` is in the
        candidate set and every shape outside the candidate set is
        strictly farther than ``r``;
      * the radius doubles until the SECOND-nearest candidate sits at
        ``<= r`` (or the candidate set is the whole list) — at which
        point no excluded shape can rank in the top two, and the answer
        is provably the full-scan answer.

    Ties resolve on ``(distance, original airside index)``, which is
    exactly what the old stable ``sort(key=distance)`` over ``airside``
    produced.  Tie order is load-bearing: the two parents feed
    ``adjacent_ground_envelope`` asymmetrically (the NEARER one owns the
    empty-intersection fallback), so ordering a tie differently would
    silently move emitted altitudes.

    A shape whose distance raises is DROPPED, mirroring the per-shape
    ``try/except`` the scan carried.
    """

    __slots__ = ("_airside", "_exteriors", "_shape_idx", "_n", "_tree",
                 "_seed_r")

    def __init__(self, airside):
        self._airside = airside
        exteriors: list = []
        shape_idx: list[int] = []
        for i, s in enumerate(airside):
            try:
                ring = s.polygon.exterior
            except _GEOM_EXC:
                continue
            exteriors.append(ring)
            shape_idx.append(i)
        self._exteriors = exteriors
        self._shape_idx = shape_idx
        self._n = len(exteriors)
        self._tree = STRtree(exteriors) if exteriors else None
        self._seed_r = _NEAREST_SEED_RADIUS_M

    def _ranked(self, hits, p):
        """``[(distance, airside_index), ...]`` for tree items ``hits``,
        sorted on the frozen ``(distance, original index)`` key — the law's
        own ranking (``grade_law.drainage_spine_parents``), unlimited here
        because the soundness escalation in ``two_nearest`` reads the
        SECOND entry to decide whether the candidate set is sufficient."""
        exteriors = self._exteriors
        shape_idx = self._shape_idx
        ranked = []
        for j in hits:
            try:
                d = exteriors[j].distance(p)
            except _GEOM_EXC:
                continue
            ranked.append((d, shape_idx[j], None))
        return [(d, k) for d, k, _pl in drainage_spine_parents(
            ranked, max_parents=len(ranked))]

    def two_nearest(self, p):
        """The two nearest airside shapes to ``p`` as
        ``[(distance, shape), ...]`` (0-2 entries) — identical to the
        retired ``sorted(((s.polygon.exterior.distance(p), s) for s in
        airside), key=distance)[:2]`` under a stable sort.

        The RANKING itself is ``grade_law.drainage_spine_parents`` (the
        law's own selection, shared with ``tools/check_grade``); this
        class supplies the exact candidate set it needs.  ``_ranked``
        already produces ``(distance, airside index)`` pairs, which are
        that function's ``(distance_m, tie_key)`` — so routing through
        it is a no-op on this side and a lockstep guarantee on the
        other."""
        tree = self._tree
        if tree is None:
            return []
        n = self._n
        px, py = p.x, p.y
        r = self._seed_r
        airside = self._airside
        for _ in range(_NEAREST_MAX_DOUBLINGS):
            hits = tree.query(box(px - r, py - r, px + r, py + r))
            n_hits = len(hits)
            if n_hits >= 2 or n_hits >= n:
                ranked = self._ranked(hits, p)
                # SOUNDNESS: the candidate set is sufficient once the
                # second-nearest candidate is inside the query radius
                # (everything excluded is strictly beyond it), or once it
                # IS the whole list (nothing left to exclude).
                if n_hits >= n or (len(ranked) >= 2 and ranked[1][0] <= r):
                    if len(ranked) >= 2:
                        self._seed_r = min(
                            _NEAREST_MAX_SEED_RADIUS_M,
                            max(_NEAREST_MIN_SEED_RADIUS_M,
                                2.0 * ranked[1][0]))
                    return [(d, airside[i]) for d, i in ranked[:2]]
            r *= 2.0
        # Escalation exhausted (non-finite station): the exact full scan.
        ranked = self._ranked(range(n), p)
        return [(d, airside[i]) for d, i in ranked[:2]]


# Per-PASS index cache.  ``airside`` lists come from ``_airside_shapes``
# once per emitter pass and are never mutated, so the index is keyed by
# list IDENTITY; the entry holds the list itself, which both validates
# the key (``is``) and keeps CPython from recycling that ``id`` under a
# different list.  Bounded so a whole-tile run never pins more than a few
# passes' shapes alive.
_NEAREST_INDEX_CACHE: dict[int, tuple] = {}
_NEAREST_INDEX_CACHE_MAX = 4


def _airside_index(airside) -> _AirsideNearestIndex:
    """The pass-cached :class:`_AirsideNearestIndex` for ``airside``."""
    key = id(airside)
    hit = _NEAREST_INDEX_CACHE.get(key)
    if hit is not None and hit[0] is airside and hit[1] == len(airside):
        return hit[2]
    index = _AirsideNearestIndex(airside)
    if (key not in _NEAREST_INDEX_CACHE
            and len(_NEAREST_INDEX_CACHE) >= _NEAREST_INDEX_CACHE_MAX):
        # dicts are insertion-ordered — drop the oldest pass.
        _NEAREST_INDEX_CACHE.pop(next(iter(_NEAREST_INDEX_CACHE)))
    _NEAREST_INDEX_CACHE[key] = (airside, len(airside), index)
    return index


# ══════════════════════════════════════════════════════════════════════
# THE CONFORMANCE BAND (owner ruling 2026-08-15 evening, RULINGS "GAP
# INTERIOR RINGS NEVER CLIFF AGAINST PAVEMENT"; Fable spec F3
# docs/specs/gap-conformance-spec.md §"The law" 1)
#
#   "a ``gap_interior_ring`` must never create a cliff.  Wherever ring
#    geometry is CLOSE TO PAVEMENT it takes the pavement's SOLVED
#    elevation (conformance, not terrain), and the descent to terrain
#    happens through a DRAINAGE SPINE ... never through a step at the
#    pavement edge."
#
# Within ``GAP_PAVEMENT_CONFORM_MARGIN_M`` of any ENCLOSING graded
# pavement edge, a gap surface vertex takes the NEAREST pavement edge's
# SOLVED elevation — ``_edge_interp_alt``, i.e. interpolated ALONG the
# edge between its two node altitudes, the mouth-weld read posture
# (uncrowned, post-solve).  A vertex near TWO pavements blends them by
# INVERSE DISTANCE: the sliver case, where both sides conform and there
# is no interior at all.
#
# WHICH PAVEMENT ENCLOSES.  ``airside`` alone is not the answer and the
# measured offender proves it: CYXY ring -10527 sits 4-5 m under a
# ``service_road`` / ``groundside_pavement`` frontage 11 m away, and no
# airside shape is anywhere near.  A residual pocket of the R19-2
# subdivision is BOUNDED by its groundside/service subdividers exactly
# as an enclosed hole is bounded by airside (the same shapes
# ``_POCKET_SUBDIVIDER_ROLES`` names for the subdivision), so their
# solved edges are conformance sources here.  Reading them moves
# NOTHING on their side: this is a read of a shipped value.
# ══════════════════════════════════════════════════════════════════════

def _conform_shapes(layout, airside):
    """Every ENCLOSING GRADED PAVEMENT whose solved edge the conformance
    band may read: the airside parents plus the groundside / service
    pavement that bounds a residual pocket.  A shape with no solved
    values at all (neither ``node_altitudes`` nor a flat ``altitude``)
    carries nothing to conform to and is left out."""
    out = list(airside)
    for s in layout.shapes:
        if s.role not in _POCKET_SUBDIVIDER_ROLES:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.polygon.geom_type != "Polygon":
            continue
        if not s.node_altitudes and getattr(s, "altitude", None) is None:
            continue
        out.append(s)
    return out


# Per-PASS conformance index cache, keyed by the ``airside`` list
# IDENTITY exactly as ``_NEAREST_INDEX_CACHE`` is (one conformance set
# per emitter pass; the groundside/service population is complete before
# gap-fill runs and the pass only APPENDS ``graded_strip`` faces, which
# are not conformance sources).
_CONFORM_INDEX_CACHE: dict[int, tuple] = {}


def _conform_index(layout, airside):
    """``(shapes, index)`` — the pass-cached two-nearest index over the
    conformance sources of :func:`_conform_shapes`."""
    key = id(airside)
    hit = _CONFORM_INDEX_CACHE.get(key)
    if hit is not None and hit[0] is airside and hit[1] == len(airside):
        return hit[2], hit[3]
    shapes = _conform_shapes(layout, airside)
    index = _AirsideNearestIndex(shapes)
    if (key not in _CONFORM_INDEX_CACHE
            and len(_CONFORM_INDEX_CACHE) >= _NEAREST_INDEX_CACHE_MAX):
        _CONFORM_INDEX_CACHE.pop(next(iter(_CONFORM_INDEX_CACHE)))
    _CONFORM_INDEX_CACHE[key] = (airside, len(airside), shapes, index)
    return shapes, index


def _conform_edge_value(index, px, py, margin=None):
    """LAW 1 — the conformance value at ``(px, py)``, or ``(None, None)``.

    ``margin`` None means the BAND read: only pavement within
    ``GAP_PAVEMENT_CONFORM_MARGIN_M`` counts, so a vertex standing on a
    tile-seam chord (a pocket boundary that is not pavement at all)
    conforms to nothing and falls through to the terrain law.  A caller
    that wants the nearest edge regardless of range — the spine's
    boundary endpoints under law 3 — passes an explicit reach.

    The slack on the range test is ``_PIT_RIM_WELD_TOL_M``, the float
    slack and nothing more: the eroded interior of law 2 is built at
    exactly this margin with a fine ``quad_segs``, so its boundary
    stations sit at the margin up to arithmetic.

    Returns ``(value, distance_to_nearest_source)``."""
    reach = (GAP_PAVEMENT_CONFORM_MARGIN_M + _PIT_RIM_WELD_TOL_M
             if margin is None else float(margin))
    picks = []
    for d, s in index.two_nearest(Point(px, py)):
        if d > reach:
            continue
        e = _edge_interp_alt(s, px, py)
        if e is None:
            continue
        picks.append((float(d), float(e)))
    if not picks:
        return None, None
    if len(picks) == 1:
        return picks[0][1], picks[0][0]
    # INVERSE-DISTANCE blend between the two bounding pavements (spec
    # §1, the sliver case): both sides conform, so the shelf between
    # them is one continuous surface and there is no step to cross.
    wts = [1.0 / max(d, 1e-6) for d, _v in picks]
    total = sum(wts)
    value = sum(w * v for w, (_d, v) in zip(wts, picks)) / total
    return value, min(d for d, _v in picks)


def _spine_interval(layout, airside, px, py):
    """The drainage interval ``(lo, hi)`` and reference edge altitudes at
    spine point ``(px, py)``: the two nearest DISTINCT bounding pavement
    parents each contribute ``[edge + floor(d), edge + ceil(d)]`` from
    ``adjacent_ground_envelope``; the combined interval is
    ``[max(floors), min(ceils)]``.  On an empty intersection it falls back
    to the nearer parent's own interval (user design ruling 2026-07-09).

    Under ``O4_DRAINAGE_SPINE_LAW`` the per-parent offsets come from
    ``grade_law.drainage_spine_envelope`` instead, so ``min(ceils)``
    composes to ``min(edge₁, edge₂) − DRAINAGE_SPINE_MIN_FALL_M`` — the
    owner's "below the lower adjacent pavement" — with the floors
    untouched."""
    p = Point(px, py)
    # OPT-1: the STRtree index reproduces the retired full airside scan
    # exactly, tie order included (see _AirsideNearestIndex).
    parents = _airside_index(airside).two_nearest(p)
    per_parent = []                      # (edge_alt, floor_abs|None, ceil_abs|None)
    edge_alts = []
    for d, s in parents:
        e = _edge_interp_alt(s, px, py)
        if e is None:
            e = _nearest_pav_alt(airside, px, py, max_distance_m=1e9)
        if e is None:
            continue
        role, cn, cl = _parent_family_code(layout, s)
        try:
            floor_off, ceil_off = _spine_envelope(
                role, cn, cl, max(0.0, d))
        except _GEOM_EXC:
            continue
        if floor_off is None and ceil_off is None:
            edge_alts.append(float(e))
            continue
        edge_alts.append(float(e))
        per_parent.append((
            float(e),
            None if floor_off is None else float(e) + floor_off,
            None if ceil_off is None else float(e) + ceil_off))
    floors = [q[1] for q in per_parent if q[1] is not None]
    ceils = [q[2] for q in per_parent if q[2] is not None]
    lo = max(floors) if floors else None
    hi = min(ceils) if ceils else None
    if lo is not None and hi is not None and lo > hi and per_parent:
        # Empty intersection — the nearer (first) parent's interval alone.
        lo, hi = per_parent[0][1], per_parent[0][2]
    return lo, hi, edge_alts


#: Layout attribute the spine emitters publish alongside
#: ``layout.gap_spines`` — one per-node TERRAIN list per emitted spine
#: way, index-for-index with ``gap_spines``.  It is the F3 law-3 floor
#: carried forward to the LATE re-clamp (``reclamp_gap_spines``), which
#: has no DEM of its own and would otherwise cut the manufactured canal
#: straight back open against the final pavement.  ``None`` in the slot
#: = no terrain was read for that way (DEM-free paths); such a way keeps
#: the historical unconditional re-clamp.
_GAP_SPINE_TERRAIN_STORE = "gap_spine_terrain"


def _append_gap_spine(layout, pts_ll, values, terrain=None) -> None:
    """Append one emitted drainage-spine way, keeping the law-3 terrain
    floor store index-aligned with ``layout.gap_spines``.  EVERY append
    goes through here so the two lists cannot drift."""
    if getattr(layout, "gap_spines", None) is None:
        layout.gap_spines = []
    store = getattr(layout, _GAP_SPINE_TERRAIN_STORE, None)
    if store is None:
        store = []
        setattr(layout, _GAP_SPINE_TERRAIN_STORE, store)
    while len(store) < len(layout.gap_spines):
        store.append(None)
    layout.gap_spines.append((pts_ll, list(values)))
    store.append(None if terrain is None else list(terrain))


def reclamp_gap_spines(layout) -> int:
    """Re-clamp every emitted drainage spine into its law interval against
    the pavement that ACTUALLY SHIPS (owner field report 2026-08-02, gate
    ``O4_DRAINAGE_SPINE_LAW``).  Returns the number of vertices moved.

    WHY A RE-CLAMP AND NOT A RE-REFERENCE.  The zone-row twin
    (``solve.py`` ~:3299) re-references its corridor against the pavement
    ring ``_writeback`` has just written, INSIDE the solver writeback,
    because that is where its values are produced.  A gap spine's values
    are produced there too — but the pavement they are referenced to moves
    AGAIN afterwards, in the LATE ``final_grade_projection`` the pipeline
    runs after the solve has returned (and after this emitter has run).
    There is no writeback left to re-reference in, so the composing answer
    is to evaluate the SAME law once more, through the SAME reader, on the
    final rings: no third code path, no second law, and idempotent — a
    spine already inside its interval is untouched.

    Called from the pipeline immediately after the late projection, which
    is the last pass that moves AIRSIDE pavement (the strip-reconcile and
    conformance passes after it move graded strips and groundside lots,
    which are not spine parents)."""
    if not DRAINAGE_SPINE_LAW_ENABLED:
        return 0
    spines = getattr(layout, "gap_spines", None) or []
    if not spines:
        return 0
    airside = _airside_shapes(layout)
    if len(airside) < 2:
        return 0
    n_moved = 0
    worst = 0.0
    n_floored = 0
    floors = getattr(layout, _GAP_SPINE_TERRAIN_STORE, None) or []
    for w, (_pts_ll, values) in enumerate(spines):
        terrain = floors[w] if w < len(floors) else None
        for i, ((lat, lon), z) in enumerate(zip(_pts_ll, values)):
            if z is None:
                continue
            try:
                px, py = layout.ll_to_m(lat, lon)
                lo, hi, _edges = _spine_interval(layout, airside, px, py)
            except _GEOM_EXC:
                continue
            nz = float(z)
            if lo is not None and nz < lo:
                nz = lo
            if hi is not None and nz > hi:
                nz = hi
            # F3 LAW 3 IS THE FLOOR AND IT SURVIVES THIS PASS.  The
            # drainage-spine law's CEILING (below the lower adjacent
            # pavement) is what cut the CYXY canal 7.7 m under its own
            # ground; the owner's ruling says the descent stops when it
            # MEETS terrain.  The re-clamp still re-references against
            # the pavement that ships — it may raise to the floor and
            # lower toward the ceiling — but never below the terrain the
            # emitter read at that station.
            _t = (terrain[i] if terrain is not None and i < len(terrain)
                  else None)
            if _t is not None and nz < float(_t):
                nz = float(_t)
                n_floored += 1
            if abs(nz - float(z)) > 1e-6:
                worst = max(worst, abs(nz - float(z)))
                values[i] = nz
                n_moved += 1
    if n_moved:
        UI.vprint(1, f"  [gap-fill] drainage-spine law re-clamp: "
                     f"{n_moved} spine vertex/vertices moved against the "
                     f"final pavement (worst {worst:.2f} m; "
                     f"{n_floored} held at the F3 terrain floor).")
    return n_moved


def _drain_target(lo, hi, edge_alts):
    """Value inside the drainage interval: a quarter up from the floor
    (fall from both edges at >= the law minimum, not cut to the 5 %
    floor).  Falls back to a single bound, then to the lower pavement
    seed (user design ruling 2026-07-09)."""
    if lo is not None and hi is not None:
        return hi - _DRAIN_FROM_CEILING * (hi - lo)
    if hi is not None:
        return hi
    if lo is not None:
        return lo
    return min(edge_alts) if edge_alts else None


def _spine_lawful_profile(layout, conform, spine, values, dem,
                          tile_lat, tile_lon, intervals=None):
    """LAW 3 as amended by F3b (gap-conformance spec) — THE STAGED
    SPINE LAW.

        value(s) = max(cone_floor(s), min(terrain(s), drainage_ceiling))

    clamped into the station's interval, where ``cone_floor(s)`` is the
    lawful descent from EACH conformed boundary end (``max`` of the two
    walks at ``_RING_ALONG_BENCH_SLOPE``) and the drainage ceiling is
    the station's interval ``hi`` — the staged
    ``grade_law.drainage_spine_envelope`` composition: PINNED to the
    edge value within ``GAP_PAVEMENT_CONFORM_MARGIN_M`` (the owner's
    conformance ruling), ``min(edges) − DRAINAGE_SPINE_MIN_FALL_M`` in
    the interior (the dam clause).

    The cone floor is the anti-trench guard: depth is bounded by what a
    lawful descent from the conformed boundaries can carve, which is
    what kills the stamped-flat trench class (CYXY 60.7124,-135.0802:
    nine nodes flat at 695.8, 7.7 m under 703.5 terrain).  The
    ``min(terrain, ceiling)`` half follows terrain where terrain is
    already below the drainage ceiling and GRADES DOWN an enclave hill
    that would otherwise dam its own interior (the F3b correction: the
    superseded clause-3 terrain FLOOR followed terrain UP and collided
    with the dam law — HECA +1,332).

    Returns ``(values, terrain)`` — the terrain is published with the
    emitted spine (``_GAP_SPINE_TERRAIN_STORE``) for reporting.  ``dem``
    None (the open-frontage pilot, DEM-free fixtures) returns ``values``
    unchanged: without terrain the interval clamp already carries the
    law."""
    if dem is None or not spine or len(spine) != len(values):
        return list(values), None
    from .elevation import _sample_dem
    terrain: list[float | None] = []
    for px, py in spine:
        try:
            lat, lon = layout.m_to_ll(px, py)
            t = _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            t = None
        terrain.append(None if t is None else float(t))
    # Arc length along the spine.
    s = [0.0]
    for (ax, ay), (bx, by) in zip(spine, spine[1:]):
        s.append(s[-1] + math.hypot(bx - ax, by - ay))
    length = s[-1]
    # The CONFORMED boundary endpoints.  Reach is the band margin: the
    # spine ends float just inside the eroded interior, so a pocket
    # bounded by pavement answers, and a seam-open one does not.
    ends = []
    for j in (0, len(spine) - 1):
        bv, _bd = _conform_edge_value(conform, spine[j][0], spine[j][1])
        ends.append(float(bv) if bv is not None else float(values[j]))
    cap = _RING_ALONG_BENCH_SLOPE
    out = []
    for i in range(len(spine)):
        # F3b staged law: value = max(cone_floor, min(terrain, drainage
        # ceiling)), clamped into the station's own interval.  The cone
        # floor bounds the depth to the lawful descent from the
        # conformed boundaries (the anti-trench guard); the min() is the
        # dam clause where terrain is high (an enclave hill is GRADED
        # DOWN to drain — the owner's ruling refutes terrain-following
        # there) and terrain-following where terrain already sits below
        # the drainage ceiling.  Band stations arrive with PINNED
        # intervals from the staged envelope and collapse to the pin.
        cone = max(ends[0] - cap * s[i], ends[1] - cap * (length - s[i]))
        lo_i, hi_i = (intervals[i] if intervals is not None
                      and i < len(intervals) else (None, None))
        base = None
        if terrain[i] is not None and hi_i is not None:
            base = min(terrain[i], hi_i)
        elif terrain[i] is not None:
            base = terrain[i]
        elif hi_i is not None:
            base = hi_i
        v = cone if base is None else max(cone, base)
        if lo_i is not None:
            v = max(v, lo_i)
        if hi_i is not None:
            v = min(v, hi_i)
        out.append(round(v, 1))
    return out, terrain


def _smooth_spine(vals, intervals, sweeps):
    """Second-difference relaxation clamped into each vertex interval;
    endpoints pinned."""
    n = len(vals)
    if n < 3:
        return list(vals)
    v = list(vals)
    for _ in range(sweeps):
        for i in range(1, n - 1):
            cand = 0.5 * (v[i - 1] + v[i + 1])
            lo, hi = intervals[i]
            if lo is not None:
                cand = max(cand, lo)
            if hi is not None:
                cand = min(cand, hi)
            v[i] = cand
    return v


# ══════════════════════════════════════════════════════════════════════
# GAP INTERIOR RINGS (ratified 2026-07-11, gate
# O4_GAP_FILL_INTERIOR_RINGS, requires O4_GAP_FILL_SPINE; REVISED per
# Noah's in-sim round-8 ruling — complete loops, value-gated)
#
# A single mid-gap spine cannot enforce the graded-band law when the
# enclosed interior genuinely drops: the mesh spans pavement edge to
# spine in ONE leg, so a low spine puts the whole drop AT the pavement
# edge (CYXY evidence node 60.7210897,-135.0776149 — 73 % where the
# band allows 5 %).  Rings mirror the EXTERIOR adjacent-ground band
# cross-section bent around the gap: the verbatim gap boundary is the
# d=0 row (pavement values), ring 1 the drainage-lip breakpoint row,
# ring 2 the graded band-edge row — the finite-to-open floor
# transition locus.
#
# ROUND-8 REVISION (the first cut violation-gated the GEOMETRY into
# per-arc runs; 66 fragmented chains read as ragged walls in the sim):
# both rings are ALWAYS complete, unbroken, concentric closed loops —
# no arcs, no taper, nothing to fall off.  The gating lives in the
# VALUES: each station carries clamp(terrain, floor, ceiling) at its
# point-law distances (the exterior per-vertex law verbatim — the
# ``_make_edge_projection_resampler`` semantics applied at the ring
# stations).  Where terrain is lawful the ring RIDES the terrain (a
# value no-op, invisible in the mesh); where it violates, the clamp
# pins to the floor (fill) or the ceiling (cut).  Terrain is
# continuous and the clamp is continuous, so the ring has no cliffs
# ALONG it anywhere, by construction.  A gap where EVERY station of
# BOTH rings is a value no-op skips its rings entirely (per-gap node
# economy — all-or-nothing, never per-arc).
#
# ENCODING (ratified answer 2, unchanged in round 8): a DERIVED value
# read from the post-solve pavement edges at emission — NOT new solver
# variables.  An equality-pinned solver variable adds zero information
# to the solve while adding interval edges that can conflict inside
# the machinery; deriving at emission guarantees exact clamp equality
# with no float round-trip, keeps the solve byte-identical gate-ON vs
# gate-OFF, and cannot regress solver feasibility.  Rings are emitted
# as constrained BREAKLINE ways inside the (single, verbatim) gap face
# via the crown-spine mechanism (layout.gap_interior_rings → to_osm →
# include_patches DUMMY edges) — never a polygon split (an inward
# offset ring of a concave gap self-intersects, and a split would mint
# the parallel shared-edge pair class that Ruppert-explodes).
# ══════════════════════════════════════════════════════════════════════


def _ring_runway_axes(layout, source_runways):
    """Runway centerline axes ``(LineString, unit, length)`` in local
    meters — the TRUE ICAO code source for runway-bounded ring widths
    (ratified answer 1: the adjacent_ground ``_family_params`` approach;
    a tile-cut runway SEGMENT's own chord under-keys the code)."""
    axes: list[tuple] = []
    if not source_runways:
        return axes
    for r in source_runways:
        try:
            rax, ray = layout.ll_to_m(r.lat_a, r.lon_a)
            rbx, rby = layout.ll_to_m(r.lat_b, r.lon_b)
        except (_GEOM_EXC + (AttributeError, TypeError)):
            continue
        rlen = math.hypot(rbx - rax, rby - ray)
        if rlen < 1.0:
            continue
        axes.append((LineString([(rax, ray), (rbx, rby)]),
                     ((rbx - rax) / rlen, (rby - ray) / rlen), rlen))
    return axes


def _ring_parent_band(layout, shape, rw_axes):
    """``(role, code_number, code_letter, band_half_width_m)`` for one
    bounding airside ``shape`` — the family key + graded band-edge
    distance the interior ring is built at.  Runway shapes key their
    ICAO code from the nearest RUNWAY AXIS length when axes are
    available (ratified answer 1), falling back to the segment-chord
    proxy only without them.  Returns None for a family with no finite
    band floor (nothing to pin a ring to)."""
    role = shape.role
    if role in _RUNWAY_ROLES:
        code = None
        if rw_axes:
            try:
                cen = shape.polygon.centroid
                axis = min(rw_axes, key=lambda a: a[0].distance(cen))
                code = runway_code_number(axis[2])
            except _GEOM_EXC:
                code = None
        if code is None:
            code = runway_code_number(_long_side_length(shape.polygon))
        return (role, code, None, RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code])
    if role in _TAXIWAY_ROLES:
        letter = taxi_shape_code_letter(layout, shape)
        return (role, None, letter,
                taxiway_strip_graded_half_width_for_letter(letter))
    if role in _APRON_ROLES:
        return (role, None, None, APRON_SHOULDER_WIDTH_M)
    return None


# ── Loop-resample support (2026-07-25 collar loop-resample ruling) ────
# The resample ladder's acceptance test and the fallback's densifier.
# Both are pure geometry helpers on an OPEN point ring (no repeated
# closing vertex); the caller closes the ring for the cover test.
def _ring_covered_by(cover, pts) -> bool:
    """True iff the CLOSED polyline through ``pts`` stays inside
    ``cover``.  ``cover=None`` (a degenerate inward buffer) is treated as
    "no test" — the historical behaviour of the inner-cover rung."""
    if cover is None:
        return True
    try:
        if cover.is_empty:
            return False
        return bool(cover.covers(LineString(list(pts) + [pts[0]])))
    except _GEOM_EXC:
        return False


def _densify_closed_ring(pts, max_chord_m: float):
    """Subdivide every chord of a CLOSED point ring longer than
    ``max_chord_m`` with COLLINEAR intermediate points.

    The point set is geometrically UNCHANGED — every inserted vertex sits
    exactly on the chord it splits — so no cover / clearance / simplicity
    property of the ring can change.  What DOES change is the law: each
    added node gets its own ``_level`` sample and enters the along-ring
    bench, so law values interpolate over ``max_chord_m`` spans instead of
    over whatever the simplify fallback happened to leave (measured HECA
    2026-07-25: chords to 445 m, SPJC to 320 m).
    """
    n = len(pts)
    if max_chord_m <= 0.0 or n < 3:
        return list(pts)
    out = []
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out.append((ax, ay))
        seg = math.hypot(bx - ax, by - ay)
        if seg <= max_chord_m:
            continue
        k = int(math.ceil(seg / max_chord_m))
        for j in range(1, k):
            t = j / k
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def _build_collar_rings(layout, airside, gap_poly, dem, tile_lat, tile_lon,
                        rw_axes, step):
    """Construct the two concentric COLLAR ring breaklines for ONE
    enclosed region — the spine-free core of the interior-ring machinery
    (arc B1, 2026-07-24: extracted VERBATIM from
    ``_build_gap_interior_rings`` so a pocket the spine emitter skips can
    receive the identical rings without a drainage-spine face)
    (round-9 rebuild: TRUE POLYGON INWARD OFFSETS — the per-station
    offset walk of round 8 self-crossed at boundary concavities and
    parent-width transitions, 9 self-intersecting loops at CYXY).

    REGIONS, not stations:

      * ring-2 CORE  = gap minus the union of every bounding parent's
        polygon buffered by ITS band width (per-parent widths, true
        runway codes) — the exact distance-law band annulus;
      * ring-1 region = gap shrunk by the drainage lip
        (``gap.buffer(-ADJACENT_GROUND_LIP_WIDTH_M)``).

    Both regions are SMOOTHED by a morphological opening + closing at
    ``_RING_MIN_FEATURE_RADIUS_M`` (drops fingers/spikes, fills
    boundary-notch tracing — calibrated against Noah's hand-edited
    reference loop, CYXY_auto_MOD way -68615) and clipped to
    ``gap.buffer(-_RING_BOUNDARY_CLEARANCE_M)`` (the zero-lens
    boundary floor).  Shapely polygon boundaries are SIMPLE BY
    CONSTRUCTION; simplicity is a HARD INVARIANT re-asserted on every
    resampled loop (a non-simple product raises — a bug, never a
    repair case).  A concave gap naturally splitting into several
    core components is CORRECT — each sub-area gets its collar; the
    hole-in-the-middle rung falls out of the geometry.

    Kept from round 8: closed loops; per-node values
    ``clamp(terrain, floor, ceiling)`` at TRUE two-nearest-parent
    distances (``_point_interval`` — the smoothed loop's varying
    offset is handled by true-distance evaluation); the two-sided
    along-ring value bench; the per-gap economy skip; ring 1
    all-or-nothing per gap (dropped when any ring-1 loop crowds a
    ring-2 loop).

    Returns a result dict::

        {"chains": [(pts_xy, alts), ...],   # [] = nothing to emit
         "stats": {...},
         "core_parts": [Polygon, ...],      # the ring-2 CORE region
         "lip_parts":  [Polygon, ...],
         "ring2_loops": [LinearRing, ...],
         "ring2_recs": [rec, ...],          # EMITTED ring-2 stations
         "ring2_stations": [rec, ...],      # ALL sampled ring-2 stations
         "loop_lines": [LineString, ...]}   # accepted loops, closed

    A ``rec`` carries ``pt`` / ``v`` (clamp value) / ``lo`` / ``hi`` /
    ``terrain`` / ``noop`` / ``floor_engaged`` and — once emitted —
    ``benched`` (the along-ring benched value).  ``ring2_stations`` is
    populated even when the per-gap economy gate suppresses the chains,
    so the pit-floor pass (arc B2) always has a LOCAL ring-2 law
    reference to work from."""
    lip = ADJACENT_GROUND_LIP_WIDTH_M
    # OPT-1: hoisted out of ``_dem_at`` — the import ran once per DEM
    # sample (once per ring station) purely to re-look-up a module that
    # is always already loaded here.
    from .elevation import _sample_dem
    _m_to_ll = layout.m_to_ll
    # OPT-1: pass-level two-nearest-parent index (built once per airside
    # list, shared across every gap/pocket of the pass).
    nearest = _airside_index(airside)
    # F3 law 1: the conformance sources — airside PLUS the groundside /
    # service pavement that encloses a residual pocket.
    _conform_shp, conform = _conform_index(layout, airside)

    def _dem_at(x, y):
        try:
            lat, lon = _m_to_ll(x, y)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    band_cache: dict[int, tuple | None] = {}

    def _band_of(s):
        key = id(s)
        if key not in band_cache:
            band_cache[key] = _ring_parent_band(layout, s, rw_axes)
        return band_cache[key]

    def _point_interval(pt):
        """The lawful ``(floor_abs, ceiling_abs)`` interval AT a ring
        point: the point's TRUE distance to each of its two nearest
        bounding parents (the ``_spine_interval`` two-nearest
        convention), each parent's envelope at that distance on top of
        its interpolated edge altitude — combined as
        ``[max(floors), min(ceilings)]``; an empty intersection falls
        back to the NEARER parent's own interval.  The FLOOR is
        evaluated at ``min(d, band width)`` (the exterior emitter's
        ``floor_depth`` clamp — the band-edge floor never opens where
        the smoothed loop swings past the band edge).  ``(None,
        None)`` = no law governs the point."""
        p = Point(pt)
        per_parent = []
        # OPT-1: identical two-nearest selection, STRtree-backed.
        for d, s in nearest.two_nearest(p):
            pband = _band_of(s)
            if pband is None:
                continue
            prole, pcn, pcl, pw = pband
            try:
                fo, _co_at_w = adjacent_ground_envelope(
                    prole, pcn, pcl, max(0.0, min(d, pw)))
                _fo_raw, co = adjacent_ground_envelope(
                    prole, pcn, pcl, max(0.0, d))
            except _GEOM_EXC:
                continue
            if fo is None and co is None:
                continue
            e = _edge_interp_alt(s, pt[0], pt[1])
            if e is None:
                e = _nearest_pav_alt(airside, pt[0], pt[1],
                                     max_distance_m=1e9)
            if e is None:
                continue
            per_parent.append((
                None if fo is None else float(e) + float(fo),
                None if co is None else float(e) + float(co)))
        floors = [q[0] for q in per_parent if q[0] is not None]
        ceils = [q[1] for q in per_parent if q[1] is not None]
        lo = max(floors) if floors else None
        hi = min(ceils) if ceils else None
        if lo is not None and hi is not None and lo > hi and per_parent:
            lo, hi = per_parent[0]          # nearer parent's interval
        return lo, hi

    def _level(pt):
        """Per-node record.

        F3 LAW 1 FIRST: a station inside the CONFORMANCE BAND takes the
        nearest enclosing pavement edge's SOLVED elevation (inverse-
        distance blended between two).  It is PINNED — ``lo == hi == v``
        — so the along-ring bench below cannot walk a conformed station
        off the pavement it conforms to, which is the whole point of the
        ruling: no cliff at the pavement edge, ever.

        Outside the band the round-8 semantics stand unchanged: VALUE =
        clamp(terrain, floor, ceiling) at the point-law interval.
        Lawful terrain → value no-op (the ring rides the ground); drop
        below floor → floor pin (fill); rise above ceiling → ceiling pin
        (cut)."""
        if pt is None:
            return None
        terrain = _dem_at(*pt)
        cv, _cd = _conform_edge_value(conform, pt[0], pt[1])
        if cv is not None:
            v = float(cv)
            return {"pt": pt, "v": v, "terrain": terrain,
                    "lo": v, "hi": v,
                    "noop": (terrain is not None
                             and abs(v - terrain)
                             <= _RING_VALUE_NOOP_TOLERANCE_M),
                    "floor_engaged": (terrain is not None and v > terrain
                                      + _RING_VALUE_NOOP_TOLERANCE_M),
                    "conformed": True}
        lo, hi = _point_interval(pt)
        if terrain is None:
            v = lo if lo is not None else hi
            if v is None:
                return None
            return {"pt": pt, "v": float(v), "terrain": None,
                    "lo": lo, "hi": hi, "noop": False,
                    "floor_engaged": False, "conformed": False}
        v = float(terrain)
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        return {"pt": pt, "v": v, "terrain": float(terrain),
                "lo": lo, "hi": hi,
                "noop": abs(v - terrain) <= _RING_VALUE_NOOP_TOLERANCE_M,
                "floor_engaged": (lo is not None and
                                  v > terrain +
                                  _RING_VALUE_NOOP_TOLERANCE_M),
                "conformed": False}

    stats = {"stations": 0, "eligible": 0, "noop_stations": 0,
             "engaged_stations": 0, "chains": 0, "nodes": 0,
             "skipped": False,
             # Loop-resample ladder forensics (2026-07-25): how many loops
             # were accepted at each rung, and the worst chord the
             # simplify fallback left BEFORE the post-densify.
             "resample_inner": 0, "resample_gap": 0,
             "resample_simplify": 0, "resample_max_chord_m": 0.0}
    ring2_stations: list[dict] = []

    def _result(chains, core_parts=(), lip_parts=(), ring2_loops=(),
                ring2_recs=(), loop_lines=()):
        return {"chains": list(chains), "stats": stats,
                "core_parts": list(core_parts),
                "lip_parts": list(lip_parts),
                "ring2_loops": list(ring2_loops),
                "ring2_recs": list(ring2_recs),
                "ring2_stations": ring2_stations,
                "loop_lines": list(loop_lines)}

    # ── REGIONS: the ERODED POCKET (F3 law 2) ─────────────────────────
    # THE INTERIOR IS THE ERODED POCKET.  The region that may descend to
    # terrain is the pocket eroded by the conformance margin; everything
    # outside it is band and conforms (law 1).  This REPLACES the round-9
    # per-parent band annulus (gap minus every bounding parent's polygon
    # buffered by ITS band width), which had no term for the
    # groundside/service frontages that bound a residual pocket and so
    # ran the ring right up to them — the measured CYXY cliff.
    #
    # The erosion IS the geometry the owner asked for, with no hand-drawn
    # line: a lobe narrower than 2x the margin erodes away entirely (the
    # 8-15 m sliver at 60.709358,-135.0734701 is pure conformance band),
    # and a neck wider than that survives as the ring's cut across it.
    # No morphological opening/closing here — that would erode a second
    # time and, worse, its CLOSING fills notches, which would push ring
    # stations back INSIDE the margin the erosion just established.
    # ``quad_segs`` is deliberately fine so a corner arc's chord sits at
    # the margin to within ``_PIT_RIM_WELD_TOL_M`` and law 1's band test
    # answers TRUE for every station of the eroded boundary.
    try:
        core = gap_poly.buffer(-GAP_PAVEMENT_CONFORM_MARGIN_M,
                               quad_segs=64)
        lip_region = gap_poly.buffer(-lip, quad_segs=4)
    except _GEOM_EXC:
        return _result([])

    def _smooth_region(region):
        """Morphological opening (drop fingers/spikes thinner than the
        minimum-feature radius) then closing (fill notch tracing),
        clipped to the hard boundary-clearance collar; returns the
        polygon parts above the noise floor."""
        if region is None or region.is_empty:
            return []
        r = _RING_MIN_FEATURE_RADIUS_M
        try:
            region = region.buffer(-r, quad_segs=4).buffer(r, quad_segs=4)
            region = region.buffer(r, quad_segs=4).buffer(-r, quad_segs=4)
            region = region.intersection(
                gap_poly.buffer(-_RING_BOUNDARY_CLEARANCE_M, quad_segs=4))
        except _GEOM_EXC:
            return []
        return [g for g in _poly_parts(region)
                if g.area >= GAP_FILL_MIN_AREA_M2]

    def _eroded_parts(region):
        """The eroded interior's surviving pieces (F3 law 2, "largest
        piece(s) kept"): every polygon part above the emitter's own
        minimum-area floor.  A negative buffer of a valid polygon is
        valid and its boundary is simple by construction, so there is
        nothing to repair and nothing to smooth."""
        if region is None or region.is_empty:
            return []
        return [g for g in _poly_parts(region)
                if g.area >= GAP_FILL_MIN_AREA_M2]

    core_parts = _eroded_parts(core)
    lip_parts = _smooth_region(lip_region)

    def _region_loops(parts):
        loops = []
        for pg in parts:
            for ring in [pg.exterior] + list(pg.interiors):
                try:
                    if ring.length >= 6.0 * _RING_MIN_NODE_SPACING_M:
                        loops.append(ring)
                except _GEOM_EXC:
                    continue
        return loops

    ring2_loops = _region_loops(core_parts)
    ring1_loops = _region_loops(lip_parts)
    # Ring 1 all-or-nothing per gap (round-8 rung 3): drop it whole
    # when any ring-1 loop crowds a ring-2 loop.
    stats["ring1_loops"] = len(ring1_loops)
    stats["ring2_loops"] = len(ring2_loops)
    stats["ring1_dropped_crowding"] = False
    if ring1_loops and ring2_loops:
        try:
            if any(l1.distance(l2) < _RING_MIN_SEPARATION_M
                   for l1 in ring1_loops for l2 in ring2_loops):
                ring1_loops = []
                stats["ring1_dropped_crowding"] = True
        except _GEOM_EXC:
            ring1_loops = []
            stats["ring1_dropped_crowding"] = True
    if not ring2_loops and not ring1_loops:
        return _result([], core_parts, lip_parts, ring2_loops)

    # ── Resample each loop at the station step + point-law values ────
    sampled = []                # (level_tag, pts, recs)
    inner_cover = None
    try:
        inner_cover = gap_poly.buffer(-0.8, quad_segs=4)
    except _GEOM_EXC:
        inner_cover = None
    for tag, loops in (("ring2", ring2_loops), ("ring1", ring1_loops)):
        for loop in loops:
            perim = loop.length
            n = max(8, int(round(perim / step)))
            if perim / n < _RING_MIN_NODE_SPACING_M:
                n = max(3, int(perim // _RING_MIN_NODE_SPACING_M))
            if n < 3:
                continue
            pts = None
            # Chords of a coarse resample can cut inside pavement at a
            # concave boundary detail (a foreign-crossing mint).
            # Densify until the closed polyline stays covered by the
            # gap; final fallback = the smoothed loop's own vertices,
            # topology-preserving-simplified (simple by construction).
            ladder = []
            for n_try in (n, 2 * n, 4 * n):
                cand = []
                for i in range(n_try):
                    q = loop.interpolate((i / n_try) * perim)
                    cand.append((float(q.x), float(q.y)))
                ladder.append(cand)
                try:
                    ok = (inner_cover is None or inner_cover.covers(
                        LineString(cand + [cand[0]])))
                except _GEOM_EXC:
                    ok = False
                if ok:
                    pts = cand
                    stats["resample_inner"] += 1
                    break
            if pts is None:
                # SECOND RUNG (2026-07-25 ruling).  The 0.8 m inner-cover
                # margin above is a PROXY for the real criterion the
                # comment states — "chords must not cut inside pavement".
                # Measured SPJC pocket (731,-160): at n the cover test
                # fails LEGITIMATELY (13.1 m of chord genuinely outside
                # the pocket, cutting pavement at concave details), but at
                # 2n and 4n the ONLY failure is the margin itself, with
                # 0 m outside the pocket.  Rejecting those in favour of a
                # 61-node simplify over 2,419 m (chords to 320 m; 14 of 49
                # HECA collar loops took the same fallback, to 445 m) —
                # and admitting the fallback with NO cover test at all —
                # is incoherent.  So re-test the SAME ladder against the
                # real criterion, ``gap_poly`` itself, and take the
                # SPARSEST candidate that passes it.
                for cand in ladder:
                    if _ring_covered_by(gap_poly, cand):
                        pts = cand
                        stats["resample_gap"] += 1
                        break
            if pts is None:
                try:
                    simp = loop.simplify(0.75, preserve_topology=True)
                    pts = [(float(x), float(y))
                           for x, y in list(simp.coords)[:-1]]
                except _GEOM_EXC:
                    continue
                if len(pts) < 3:
                    continue
                stats["resample_simplify"] += 1
                stats["resample_max_chord_m"] = max(
                    stats["resample_max_chord_m"],
                    max(math.hypot(pts[(i + 1) % len(pts)][0] - pts[i][0],
                                   pts[(i + 1) % len(pts)][1] - pts[i][1])
                        for i in range(len(pts))))
                # POST-DENSIFY the fallback: geometrically identical
                # (collinear inserts), but every added node carries a law
                # sample into the bench, bounding law interpolation at the
                # station step instead of at the simplify tolerance's
                # arbitrary chord length.
                pts = _densify_closed_ring(pts, step)
            # SIMPLICITY — the round-9 hard invariant.  The source is
            # a shapely polygon boundary (simple by construction); the
            # resampled chord polygon must stay simple too (the
            # minimum-feature radius bounds curvature well above the
            # station step).  A violation is a BUG, never a repair
            # case.
            try:
                if not Polygon(pts).is_valid:
                    raise ValueError(
                        "gap interior ring loop resampled NON-SIMPLE "
                        f"(gap centroid {gap_poly.centroid.wkt}) — "
                        "round-9 invariant violated")
            except _GEOM_EXC:
                raise
            recs = [_level(pt) for pt in pts]
            if any(r is None for r in recs):
                continue                    # no law + no terrain: drop
            sampled.append((tag, pts, recs))
            if tag == "ring2":
                ring2_stations.extend(recs)

    # Forensics for the ladder ruling: only the non-default rungs print.
    if stats["resample_gap"] or stats["resample_simplify"]:
        _rc = gap_poly.centroid
        UI.vprint(1, f"  [gap-ring] loop resample at "
                     f"({_rc.x:.0f},{_rc.y:.0f}): "
                     f"{stats['resample_inner']} inner-cover, "
                     f"{stats['resample_gap']} gap-cover (2nd rung), "
                     f"{stats['resample_simplify']} simplify fallback"
                     + (f" (worst chord {stats['resample_max_chord_m']:.0f} m"
                        f" -> densified at {step:.0f} m)"
                        if stats["resample_simplify"] else "") + ".")

    if not sampled:
        return _result([], core_parts, lip_parts, ring2_loops)

    # ── Per-gap economy gate (round-8, all-or-nothing) ────────────────
    engaged = noop = 0
    for _tag, _pts, recs in sampled:
        for r in recs:
            if r["noop"]:
                noop += 1
            else:
                engaged += 1
    stats["stations"] = stats["eligible"] = engaged + noop
    stats["noop_stations"] = noop
    stats["engaged_stations"] = engaged
    if engaged == 0:
        stats["skipped"] = True
        return _result([], core_parts, lip_parts, ring2_loops)

    def _bench_along(pts, alts, los, his):
        """Two-sided along-ring value bench (round-8 continuity law,
        unchanged): FILL side raises the low neighbor (ceiling-capped),
        CUT side lowers the high neighbor (floor-capped) at
        ``_RING_ALONG_BENCH_SLOPE``; every loop is closed, so the
        relaxation is cyclic.  A residual step survives only where the
        caps themselves demand it (clamp-limited)."""
        n = len(alts)
        if n < 3:
            return [round(x, 2) for x in alts]
        v = list(alts)
        order = list(range(n))
        for _ in range(2):
            for rng in (order, order[::-1]):
                prev = rng[-1]              # cyclic
                for k in rng:
                    pk, pp = pts[k], pts[prev]
                    dist = math.hypot(pk[0] - pp[0], pk[1] - pp[1])
                    allow = _RING_ALONG_BENCH_SLOPE * dist
                    cand = v[prev] - allow   # FILL: raise the low side
                    if cand > v[k]:
                        cap = his[k]
                        v[k] = cand if cap is None else min(cand, cap)
                    cand = v[prev] + allow   # CUT: lower the high side
                    if cand < v[k]:
                        cap = los[k]
                        v[k] = cand if cap is None else max(cand, cap)
                    prev = k
        return [round(x, 2) for x in v]

    chains: list[tuple[list, list]] = []
    ring2_recs: list[dict] = []
    emitted_loop_lines: list = []
    for tag, pts, recs in sampled:
        # Cross-loop zero-lens guard: a loop hugging an already
        # accepted loop below the clearance floor is dropped whole
        # (loops are region boundaries — they never cross, but two
        # components can crowd a thin sliver).
        try:
            cand_ls = LineString(pts + [pts[0]])
        except _GEOM_EXC:
            continue
        too_close = False
        for other in emitted_loop_lines:
            try:
                if cand_ls.distance(other) < _RING_MIN_CLEARANCE_M:
                    too_close = True
                    break
            except _GEOM_EXC:
                too_close = True
                break
        if too_close:
            continue
        alts = _bench_along(pts, [r["v"] for r in recs],
                            [r["lo"] for r in recs],
                            [r["hi"] for r in recs])
        out_pts = pts + [pts[0]]
        out_alts = alts + [alts[0]]
        chains.append((out_pts, out_alts))
        emitted_loop_lines.append(cand_ls)
        stats["chains"] += 1
        stats["nodes"] += len(pts)
        if tag == "ring2":
            for r, a in zip(recs, alts):
                r["benched"] = a
                ring2_recs.append(r)

    return _result(chains, core_parts, lip_parts, ring2_loops,
                   ring2_recs, emitted_loop_lines)


def _build_gap_interior_rings(layout, airside, gap_poly, spine, values,
                              dem, tile_lat, tile_lon, rw_axes, step):
    """The interior-ring construction for ONE EMITTED gap face: the
    spine-free collar rings (``_build_collar_rings``) plus the two
    spine-coupled steps that only exist on the spine/face path — the
    ring-2 ceiling re-coupling (spine values may only move DOWN) and the
    spine trim to the ring core.  Returns ``(chains, clamped_values,
    stats, spine_chains)`` exactly as before."""
    res = _build_collar_rings(layout, airside, gap_poly, dem, tile_lat,
                              tile_lon, rw_axes, step)
    chains = res["chains"]
    stats = res["stats"]
    if not chains:
        return [], list(values), stats, None
    core_parts = res["core_parts"]
    lip_parts = res["lip_parts"]
    ring2_loops = res["ring2_loops"]
    ring2_recs = res["ring2_recs"]
    emitted_loop_lines = res["loop_lines"]

    # ── Spine re-coupling (unchanged law): ring 2 is the spine's
    # CEILING where the nearest ring-2 node is FLOOR-ENGAGED and the
    # spine node sits INSIDE the core.  Values only ever move DOWN. ────
    clamped = list(values)
    core_union = unary_union(core_parts) if core_parts else None
    # The spine's TRIM REGION is the innermost emitted region: the
    # core when ring-2 loops exist; the lip region when the bands
    # cover the whole gap (core empty, ring 1 alone) — the drainage
    # crest survives inside the lip ring instead of dying with the
    # core (the zones-fully-overlap rung keeps its central spine).
    if ring2_loops and core_union is not None:
        trim_region = core_union
    else:
        try:
            trim_region = unary_union(lip_parts) if lip_parts else None
        except _GEOM_EXC:
            trim_region = None
    in_core: list[bool] = []
    for j, (sx, sy) in enumerate(spine):
        p = Point(sx, sy)
        inside = False
        try:
            inside = (trim_region is not None
                      and trim_region.covers(p))
        except _GEOM_EXC:
            inside = False
        in_core.append(inside)
        if not inside or not ring2_recs:
            continue
        best = None
        for r in ring2_recs:
            d = math.hypot(r["pt"][0] - sx, r["pt"][1] - sy)
            if best is None or d < best[0]:
                best = (d, r)
        if best is not None and best[1]["floor_engaged"]:
            clamped[j] = min(clamped[j], round(best[1]["benched"], 1))

    # ── SPINE TRIM to the core (round-8, unchanged rationale): a
    # full-length spine would cross the closed loops at the gap ends.
    # Keep spine nodes inside the (smoothed) core with 2 m of loop
    # clearance; split at any remaining segment that clips a loop. ─────
    spine_chains: list[list[int]] | None = []
    keep = []
    for j, (sx, sy) in enumerate(spine):
        ok = in_core[j]
        if ok:
            p = Point(sx, sy)
            for g in emitted_loop_lines:
                try:
                    if g.distance(p) < 2.0:
                        ok = False
                        break
                except _GEOM_EXC:
                    ok = False
                    break
        keep.append(ok)
    cur: list[int] = []
    for j in range(len(spine)):
        if not keep[j]:
            if len(cur) >= 2:
                spine_chains.append(cur)
            cur = []
            continue
        if cur:
            seg = LineString([spine[cur[-1]], spine[j]])
            clipped = False
            try:
                for g in emitted_loop_lines:
                    if seg.distance(g) < _RING_MIN_CLEARANCE_M / 2.0:
                        clipped = True
                        break
            except _GEOM_EXC:
                clipped = True
            if clipped:
                if len(cur) >= 2:
                    spine_chains.append(cur)
                cur = []
        cur.append(j)
    if len(cur) >= 2:
        spine_chains.append(cur)
    stats["spine_nodes_kept"] = sum(1 for x in keep if x)
    stats["spine_nodes_total"] = len(spine)
    return chains, clamped, stats, spine_chains


# ══════════════════════════════════════════════════════════════════════
# POCKET COLLAR RINGS (arc B1, owner ruling 2026-07-24, gate
# O4_POCKET_COLLAR_RINGS)
#
#   "we should be able to identify when there's a significant drop in the
#    center of an enclosed area, but first there should be two fully
#    enclosed rings of adjacent ground covering the necessary drainage
#    slope rules per zone, THEN the gap pit in the middle."
#
# The interior rings above are built INSIDE ``_emit_one_gap``, so they only
# ever reach a gap the drainage-spine emitter treats.  A pocket wider than
# GAP_FILL_MAX_WIDTH_M is skipped before that — and the ONLY thing that ever
# reached such a pocket was the flat pit clamp of
# ``emit_gap_interior_floor``.  Measured SPJC 2026-07-24: a 235,167 m2
# pocket (461 m short dimension) took ONE flat 158,651 m2 patch at 16.1 m,
# 2.7-3.4 m ABOVE the taxiway junctions ringing it.
#
# With the gate ON a WIDTH-SKIPPED pocket gets the SAME two collar rings
# first — identical construction, identical round-8 semantics (complete
# closed loops, gating in the VALUES not the geometry, all-or-nothing node
# economy) — and the pit pass then works only INSIDE ring 2.
#
# SCOPE: WIDTH-skipped pockets ONLY.  Pockets skipped for "foreign shape
# inside" or for a partial-straddle legacy strip are deliberately EXCLUDED
# for now — they already carry partial coverage by design (the corridor
# bands / the straddling strip own that ground), so a collar there would
# double-govern it.  Those two classes never reach ``_grade_face``, which is
# exactly where this hook lives, so the exclusion is structural.
# ══════════════════════════════════════════════════════════════════════

# Layout attribute the collar pass publishes for the pit-floor pass
# (arc B2): one record per collared pocket.
_POCKET_COLLAR_STORE = "pocket_collars"


def _emit_pocket_collar_rings(layout, airside, pocket_poly, dem, tile_lat,
                              tile_lon, rw_axes, step) -> int:
    """Emit the two collar rings for ONE width-skipped pocket and publish
    the pocket's collar record.  Returns the emitted chain count.

    The rings go to ``layout.gap_interior_rings`` — the SAME open
    constrained-way mechanism the treated-gap rings use (``to_osm`` →
    ``o4_feature=gap_interior_ring``), so a collar ring is
    indistinguishable from an interior ring downstream.

    The record is published even when NO chain emits (the round-8
    economy gate: every station of both rings is a value no-op), because
    the ring-2 CORE region and its station values are the pit-floor
    pass's scope and its LOCAL law reference — both exist independently
    of whether the rings themselves were worth their nodes."""
    try:
        res = _build_collar_rings(layout, airside, pocket_poly, dem,
                                  tile_lat, tile_lon, rw_axes, step)
    except _GEOM_EXC as exc:
        UI.vprint(1, f"  [gap-collar] collar-ring construction FAILED "
                     f"(pocket left bare): {exc!r}")
        return 0
    chains = res["chains"]
    stats = res["stats"]
    _c = pocket_poly.centroid
    if chains:
        if getattr(layout, "gap_interior_rings", None) is None:
            layout.gap_interior_rings = []
        for _pts, _alts in chains:
            layout.gap_interior_rings.append(
                ([layout.m_to_ll(_x, _y) for _x, _y in _pts],
                 list(_alts)))
        UI.vprint(1, f"  [gap-collar] width-skipped pocket at "
                     f"({_c.x:.0f},{_c.y:.0f}) area="
                     f"{pocket_poly.area:.0f} m2: {stats['chains']} "
                     f"collar loop(s), {stats['nodes']} node(s), "
                     f"{stats['engaged_stations']} engaged / "
                     f"{stats['noop_stations']} terrain-riding of "
                     f"{stats['stations']} station(s); regions "
                     f"ring1={stats.get('ring1_loops')} "
                     f"ring2={stats.get('ring2_loops')}"
                     f"{' (ring 1 dropped: crowds ring 2)' if stats.get('ring1_dropped_crowding') else ''}.")
    elif stats.get("skipped"):
        UI.vprint(1, f"  [gap-collar] width-skipped pocket at "
                     f"({_c.x:.0f},{_c.y:.0f}): collar rings SKIPPED "
                     f"(economy gate — every station of both rings is a "
                     f"value no-op; {stats['stations']} station(s)).")
    else:
        UI.vprint(1, f"  [gap-collar] width-skipped pocket at "
                     f"({_c.x:.0f},{_c.y:.0f}): no collar ring region "
                     f"(bands cover the pocket, or no law governs it).")
    try:
        core_union = (unary_union(res["core_parts"])
                      if res["core_parts"] else None)
    except _GEOM_EXC:
        core_union = None
    store = getattr(layout, _POCKET_COLLAR_STORE, None)
    if store is None:
        store = []
        setattr(layout, _POCKET_COLLAR_STORE, store)
    store.append({"pocket": pocket_poly, "core": core_union,
                  "ring2": list(res["ring2_stations"]),
                  "chains": len(chains), "nodes": stats["nodes"]})
    return len(chains)


def collared_pocket_zone_union(layout):
    """The published COLLARED-POCKET zone union, or ``None``.

    THE consumer entry point (the crossing-influence-zone pattern,
    ``crossing_terrain.crossing_influence_zone_union``): adjacent-ground
    bands take this single geometry as a hard keep-out and build NO band
    geometry inside a collared pocket.  A collar ring and a band marching
    into the same pocket are two surfaces governing ONE patch of terrain
    — the overlap crashes X-Plane — and the band's own "covered frontage"
    probe cannot see the conflict, because a width-skipped pocket has no
    gap FACE to stand the bands down.  ``None`` (nothing collared) means
    no keep-out.

    Keyed on ACTUAL RING EMISSION, not on the record's existence: a
    record is published even when ZERO chains emit (the round-8 economy
    gate / no collar region — see ``_emit_pocket_collar_rings``), and
    such a pocket is still the bands' ground to grade, so it stays OUT of
    the zone.  ``rec["chains"]`` is exactly the number of ways appended to
    ``layout.gap_interior_rings`` for that pocket, so the count is the
    faithful emission key."""
    store = getattr(layout, _POCKET_COLLAR_STORE, None) or []
    polys = [rec["pocket"] for rec in store
             if rec.get("chains") and rec.get("pocket") is not None
             and not rec["pocket"].is_empty]
    if not polys:
        return None
    try:
        union = unary_union(polys)
    except _GEOM_EXC:
        return None
    if union is None or union.is_empty:
        return None
    return union


def collared_pocket_zone_prepared(layout):
    """Prepared-geometry form of the collared-pocket zone union for
    point-containment loops (the band march's station test), or
    ``None``."""
    union = collared_pocket_zone_union(layout)
    if union is None:
        return None
    from shapely.prepared import prep
    try:
        return prep(union)
    except _GEOM_EXC:
        return None


# ══════════════════════════════════════════════════════════════════════
# OPEN-FRONTAGE CORRIDOR SPINE (slice B pilot, user design ruling 3
# 2026-07-09; docs/chain_identity_one_solve_plan.md §Slice B)
#
# The OPEN generalization of the enclosed-gap spine.  An enclosed gap is
# an INTERIOR RING of the airside union; a corridor between a runway and
# a parallel taxiway is bounded by pavement on its two long sides but OPEN
# at the ends, so it is NOT an interior ring and the enclosed path never
# owns it.  With the legacy surface_clearance chain deleted the corridor
# bands inherit that open frontage and are the WRONG tool there (facing
# bands off different edge references disagree at the clip seam → tears +
# coincident-twin lenses).  Emit instead ONE face per corridor:
#   * long sides = the two facing pavement chains VERBATIM (a subsequence
#     of existing pavement ring vertices — chain identity, zero new
#     boundary geometry on pavement);
#   * ends = STRAIGHT closures across the corridor mouth between two
#     pavement ring vertices — TRUE outer edges facing free terrain (a
#     lawful vertical face lives ONLY here, per ruling 3; the corridor-law
#     march / daylight rules own everything beyond the mouth);
#   * interior = ONE drainage spine (the crown/valley), emitted via the
#     proven open-way crown mechanism (layout.gap_spines).
# ══════════════════════════════════════════════════════════════════════


def _poly_parts(geom):
    """Polygon components of a shapely geometry (drops non-areal parts)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]


def _touching_shapes(poly, airside, tol):
    """The airside shapes whose exterior runs within ``tol`` of ``poly`` —
    the pavement chains a candidate corridor is bounded by.  A genuine
    corridor faces >= 2 DISTINCT shapes (a concave notch of ONE shape
    faces only itself and is not a between-pavement corridor)."""
    out = []
    for s in airside:
        try:
            if s.polygon.exterior.distance(poly) <= tol:
                out.append(s)
        except _GEOM_EXC:
            continue
    return out


def _detect_open_corridors(union, close_r, subtract):
    """Morphological CLOSING of the airside union bridges every open
    channel up to ``2 * close_r`` wide; the difference against the union
    is the newly-covered ground — enclosed gaps (interior rings) AND open
    corridors.  The closing-difference keeps the union's exact boundary on
    every pavement-facing side VERBATIM (GEOS does not perturb ``union``'s
    coordinates on a shared boundary — only the buffered end caps are new
    geometry).  ``subtract`` (enclosed-gap union + a standoff-buffered union
    of every foreign shape) is then removed so a single coarse closing blob
    SPLITS into the individual corridor slabs between pavements instead of
    being wholly blocked by one obstacle inside it; the subtraction only
    touches the FOREIGN-facing side of a corridor (foreign shapes sit in the
    corridor interior / far edge, never on the pavement-facing boundary),
    so the pavement chains stay verbatim.  Returns the polygon parts."""
    try:
        closed = union.buffer(close_r, quad_segs=2,
                              join_style=1).buffer(-close_r, quad_segs=2,
                                                   join_style=1)
        bridged = closed.difference(union)
        if subtract is not None and not subtract.is_empty:
            bridged = bridged.difference(subtract)
    except _GEOM_EXC:
        return []
    return _poly_parts(bridged)


def _corridor_verbatim_face(corridor_poly, airside, registry, air_ext,
                            ring_verts):
    """Rebuild a corridor region as a face whose PAVEMENT-facing boundary
    is a verbatim pavement SUBSEQUENCE and whose ENDS are straight closures
    across the mouth between two pavement ring vertices.  Walk the exterior
    ring and classify each vertex:

      * VERBATIM pavement ring vertex (in ``registry``) → keep, verbatim
        value;
      * a TRANSITION point ON a pavement edge (<= 0.15 m, mid-edge — where
        the morphological-closing end cap crossed the pavement line): the
        pavement-node rule (Noah, 2026-07-09 — grading shapes never mint a
        node on a pavement edge) says extend to the BRACKETING ring vertex
        — snap to the nearest pavement ring vertex within
        ``OPEN_FRONTAGE_CLOSE_M`` (the buffer radius bounds how far the
        cut sits from the true pavement end).  The corridor side then runs
        to a real vertex and the mouth closure spans two real vertices
        (zero new pavement-edge nodes).  A colinear on-edge FOOT is the
        fallback if no ring vertex is in range;
      * a FAR non-verbatim vertex (a buffered end-cap point facing free
        terrain — a TRUE outer edge) → DROP it; the segment between the
        flanking kept vertices is the straight mouth closure.

    Returns ``(face_poly, ring_coords, ring_alts)`` or None."""
    return _verbatim_boundary_face(
        corridor_poly, air_ext, ring_verts, registry,
        foot_value=lambda vx, vy: _nearest_pav_alt(airside, vx, vy,
                                                   max_distance_m=5.0))


def _verbatim_boundary_face(region_poly, exteriors, ring_verts, registry,
                            foot_value=None):
    """THE VERBATIM-FACE CORE — one implementation, two callers.

    Rebuilds ``region_poly``'s ring so its FEATURE-facing boundary is a
    verbatim subsequence of the bounding features' own ring vertices and
    its open segments become straight closures between two real vertices
    (the classification the open-corridor law rules, above).  The caller
    supplies WHICH features bound the region: ``exteriors`` (their ring
    exteriors), ``ring_verts`` (their ring vertices) and ``registry``
    (vertex key → value; membership is the verbatim test).

    ``registry`` may be a bare KEY SET when the caller wants geometry
    only.  ``foot_value`` values an on-edge FOOT the snap could not pull
    onto a ring vertex; ``None`` (the value-free caller — the ruling-3
    pocket detector, which must run identically pre- and post-solve)
    keeps the foot with no value.  Returns ``(face_poly, ring, alts)``;
    ``alts`` is ``None`` when no value source was given.
    """
    _value_at = (registry.get if hasattr(registry, "get")
                 else (lambda _k: None))
    ring = _open_coords(region_poly)
    if len(ring) < 3:
        return None
    new_ring: list[tuple[float, float]] = []
    alts: list = []
    for vx, vy in ring:
        k = _key(vx, vy)
        if k in registry:
            new_ring.append((vx, vy))
            alts.append(_value_at(k))       # boundary vertex, verbatim
            continue
        pt = Point(vx, vy)
        d_pav = None
        for ext in exteriors:
            try:
                d = ext.distance(pt)
            except _GEOM_EXC:
                continue
            if d_pav is None or d < d_pav:
                d_pav = d
        if d_pav is not None and d_pav <= 0.15:
            # ON a pavement edge → a transition point.  Extend to the
            # nearest pavement RING VERTEX (pavement-node rule).
            best_vd, best_v = None, None
            for rx, ry in ring_verts:
                d = math.hypot(vx - rx, vy - ry)
                if d <= OPEN_FRONTAGE_CLOSE_M and (
                        best_vd is None or d < best_vd):
                    best_vd, best_v = d, (rx, ry)
            if best_v is not None:
                rk = _key(best_v[0], best_v[1])
                if rk in registry:
                    new_ring.append((best_v[0], best_v[1]))
                    alts.append(_value_at(rk))
                    continue
            # Fallback: keep the colinear on-edge foot (an exact T-vertex,
            # the survivable class — never a near-parallel lens).
            e = foot_value(vx, vy) if foot_value is not None else None
            if e is not None or foot_value is None:
                new_ring.append((vx, vy))
                alts.append(None if e is None else float(e))
                continue
        # FAR non-verbatim: an end-closure / true-outer-edge vertex — drop
        # it (the flanking kept vertices close the mouth with a straight
        # segment).
        continue
    # De-duplicate consecutive coincident kept vertices (the extension can
    # pull two adjacent transition points onto the same ring vertex).
    dr: list[tuple[float, float]] = []
    da: list = []
    for (x, y), a in zip(new_ring, alts):
        if not dr or math.hypot(x - dr[-1][0], y - dr[-1][1]) > 1e-6:
            dr.append((x, y))
            da.append(a)
    if len(dr) < 3:
        return None
    try:
        face_poly = Polygon(dr)
    except _GEOM_EXC:
        return None
    if face_poly.is_empty or not face_poly.is_valid:
        return None
    return face_poly, dr, (None if foot_value is None else da)


def _emit_open_corridor(layout, airside, face_poly, ring, alts,
                        step) -> int:
    """Grade ONE clean corridor face (verbatim ring + straight closures):
    build the drainage spine, solve its values, append the face + spine.
    Returns 1 on emit, 0 on a lawful skip (logged)."""
    try:
        axes = _mrr_axes(min_rotated_rect(face_poly))
    except _GEOM_EXC:
        return 0
    if axes is None or axes[1] is None:
        return 0
    short_side, long_dir, long_len = axes
    _c = face_poly.centroid
    UI.vprint(1, f"  [open-frontage] corridor face area="
                 f"{face_poly.area:.0f} m2 short={short_side:.0f} "
                 f"centroid=({_c.x:.0f},{_c.y:.0f})")
    if short_side > GAP_FILL_MAX_WIDTH_M:
        UI.vprint(1, f"  [open-frontage] skipped corridor (width "
                     f"{short_side:.0f} > {GAP_FILL_MAX_WIDTH_M:.0f}) "
                     f"area={face_poly.area:.0f} m2")
        return 0
    spine = _build_spine(face_poly, long_dir, long_len, step)
    if spine is None:
        UI.vprint(1, "  [open-frontage] no spine for corridor "
                     f"(area={face_poly.area:.0f} m2) — skipped.")
        return 0
    intervals: list[tuple] = []
    targets: list[float] = []
    for px, py in spine:
        lo, hi, edge_alts = _spine_interval(layout, airside, px, py)
        target = _drain_target(lo, hi, edge_alts)
        if target is None:
            UI.vprint(1, "  [open-frontage] no pavement value at spine — "
                         "skipped.")
            return 0
        intervals.append((lo, hi))
        targets.append(target)
    values = _smooth_spine(targets, intervals, _SMOOTH_SWEEPS)
    values = [round(v, 1) for v in values]
    layout.shapes.append(BuiltShape(
        polygon=face_poly, role=ROLE_GRADED_STRIP, ref=_OPEN_FRONTAGE_REF,
        node_altitudes=list(alts) + [alts[0]]))
    pts_ll = [layout.m_to_ll(px, py) for px, py in spine]
    # The open-frontage pilot (default OFF) reads no DEM, so it publishes
    # no F3 terrain floor — the store keeps a None in this way's slot and
    # the late re-clamp treats it exactly as it always has.
    _append_gap_spine(layout, pts_ll, list(values))
    return 1


def _emit_open_frontage(layout, airside, comps, union, registry,
                        chain_keys, other_polys, parents, step,
                        hard_polys=None) -> int:
    """Detect + grade every OPEN corridor between facing pavement chains
    (behind ``O4_OPEN_FRONTAGE_SPINE``, checked by the caller).  Every
    candidate region is logged with an emit / skip reason — no silent
    skips.  Returns the corridor-face count.

    ``hard_polys`` (ENCLAVE LAW, spec §3; SCOPING v2 item 2): the
    blocker subset an enclave interior may NOT exempt, exactly as the
    enclosed-gap loop uses it.  THE SECOND VETO CALL SITE — the
    corridor-blocker loop below is the other place a foreign shape
    vetoes the ruled treatment, and the exemption did not reach it: a
    corridor lying inside a published enclave is airside-interior ground
    under the same owner ruling that governs the holes, so the shapes it
    CONTAINS (the ones G-ENCLAVE re-verdicts) are not foreign owners of
    it.  ``None``: the full ``other_polys`` set blocks, as before —
    byte-identical, which is also this whole path's state under its own
    default-OFF gate."""
    # Enclosed gaps (interior rings) are owned by the enclosed-gap path;
    # every foreign shape (groundside / service / retaining wall / building)
    # carries a standoff (the groundside 1 m no-weld ruling).  Both are
    # SUBTRACTED from the closing so one coarse blob splits into individual
    # corridor slabs instead of being blocked whole by a single obstacle
    # inside it.  The subtraction only touches a corridor's FOREIGN-facing
    # side (foreign shapes sit in the interior / far edge, never on the
    # pavement-facing boundary), so the pavement chains stay verbatim.
    enclosed = []
    for comp in comps:
        for interior in comp.interiors:
            try:
                enclosed.append(Polygon(interior.coords))
            except _GEOM_EXC:
                continue
    try:
        enclosed_union = unary_union(enclosed) if enclosed else None
    except _GEOM_EXC:
        enclosed_union = None
    subtract_geoms = []
    if enclosed_union is not None and not enclosed_union.is_empty:
        subtract_geoms.append(enclosed_union)
    if other_polys:
        try:
            foreign_block = unary_union(
                [op for _oid, op in other_polys]).buffer(
                    _OPEN_FRONTAGE_FOREIGN_STANDOFF_M)
            if not foreign_block.is_empty:
                subtract_geoms.append(foreign_block)
        except _GEOM_EXC:
            pass
    try:
        subtract = unary_union(subtract_geoms) if subtract_geoms else None
    except _GEOM_EXC:
        subtract = None
    corridors = _detect_open_corridors(
        union, OPEN_FRONTAGE_CLOSE_M, subtract)
    if not corridors:
        return 0
    region = layout.airport_boundary
    air_ext = []
    ring_verts: list[tuple[float, float]] = []
    for _s in airside:
        try:
            _ext = _s.polygon.exterior
        except _GEOM_EXC:
            continue
        air_ext.append(_ext)
        ring_verts.extend((float(x), float(y)) for x, y in _ext.coords[:-1])
    emitted = 0
    for corr in corridors:
        if corr.is_empty or corr.area < GAP_FILL_MIN_AREA_M2:
            continue
        _c = corr.centroid
        # Enclosed-gap overlap → owned by the interior-ring path.
        if enclosed_union is not None:
            try:
                if corr.intersection(enclosed_union).area > 0.5 * corr.area:
                    UI.vprint(1, f"  [open-frontage] skipped region "
                                 f"(enclosed gap — interior-ring path owns "
                                 f"it) area={corr.area:.0f} m2 "
                                 f"centroid=({_c.x:.0f},{_c.y:.0f})")
                    continue
            except _GEOM_EXC:
                pass
        # Outside the airport region → not our ground.
        if region is not None:
            try:
                if not region.contains(corr.representative_point()):
                    UI.vprint(1, f"  [open-frontage] skipped region "
                                 f"(outside airport boundary) area="
                                 f"{corr.area:.0f} m2 "
                                 f"centroid=({_c.x:.0f},{_c.y:.0f})")
                    continue
            except _GEOM_EXC:
                pass
        # A genuine corridor faces >= 2 DISTINCT pavement shapes.
        touching = _touching_shapes(corr, airside, tol=0.5)
        if len(touching) < 2:
            UI.vprint(1, f"  [open-frontage] skipped region (faces "
                         f"{len(touching)} pavement shape(s), need >= 2 — "
                         f"concave notch, not a corridor) area="
                         f"{corr.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})")
            continue
        # A foreign shape inside (groundside / service / retaining wall)
        # means the corridor-band / daylight law owns it — skip.
        #
        # ENCLAVE INTERIOR (spec §3): a corridor that IS enclave ground
        # takes the ruled treatment, and the shapes inside it are
        # re-verdicted airside-interior by G-ENCLAVE rather than being
        # foreign owners of it — so only the blockers the law cannot
        # exempt (``_enclave_exempt``: the enclave's own surround
        # material and the runway-end regime) still veto.  Same
        # ``enclave_covering`` predicate and same ``hard_polys`` set as
        # the enclosed-gap loop; nothing new is computed here.
        _covering = (_enclave_treatable(layout, corr)
                     if hard_polys is not None else None)
        _corr_blockers = (hard_polys if _covering is not None
                          else other_polys)
        overlapped = False
        _cb = None
        for _oid, op in _corr_blockers:
            try:
                _ov = corr.intersection(op).area
                if _ov > 1.0:
                    overlapped = True
                    _cb = (_oid, _ov)
                    break
            except _GEOM_EXC:
                continue
        if overlapped:
            _bs = (next((s for s in layout.shapes if id(s) == _cb[0]), None)
                   if _cb is not None else None)
            UI.vprint(1, f"  [open-frontage] skipped corridor (foreign "
                         f"shape inside) area={corr.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f}) "
                         f"blocker={getattr(_bs, 'role', '?')}/"
                         f"{getattr(_bs, 'ref', '') or ''} "
                         f"enclave="
                         f"{'covered' if _covering is not None else 'none'}")
            continue
        # Parents (building pads / runway-end skirts) inside → reuse the
        # enclosed-gap parent machinery (residual faces + annular spine).
        parents_in = []
        for p in parents:
            try:
                if corr.intersection(p.polygon).area > 1.0:
                    parents_in.append(p)
            except _GEOM_EXC:
                continue
        if parents_in:
            faces = _parent_residual_faces(corr, parents, chain_keys)
            n = 0
            for face_poly in faces:
                n += _grade_face(layout, airside, face_poly, step, registry)
            emitted += n
            continue
        # Clean corridor: verbatim pavement long-sides + straight-closure
        # ends, then the drainage spine.
        built = _corridor_verbatim_face(
            corr, airside, registry, air_ext, ring_verts)
        if built is None:
            UI.vprint(1, f"  [open-frontage] skipped corridor "
                         f"(non-verbatim / degenerate face) area="
                         f"{corr.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})")
            continue
        face_poly, face_ring, face_alts = built
        emitted += _emit_open_corridor(
            layout, airside, face_poly, face_ring, face_alts, step)
    if emitted:
        UI.vprint(1, f"  [open-frontage] emitted {emitted} open-corridor "
                     f"drainage-spine face(s).")
    return emitted


# ══════════════════════════════════════════════════════════════════════
# SLICE B STAGE B2 — PRE-SOLVE spine construction (one-solve absorption)
# ══════════════════════════════════════════════════════════════════════


def _airside_shapes(layout):
    """The airside pavement shapes the gap detection runs on — ONE
    definition shared by the pre-solve construction and the post-solve
    emitter so both see the identical union (parity is load-bearing:
    the emitter matches its spines against the pre-solve store by
    coordinate)."""
    return [s for s in layout.shapes
            if s.role in _AIRSIDE_PAVEMENT_ROLES
            and s.polygon is not None and not s.polygon.is_empty
            and s.polygon.geom_type == "Polygon"]


# SEAM HEALING (owner ruling 2026-07-26; SPLP adjacent-ground bands
# 165/168).  "Fully enclosed pavement area" was classified off the
# POST-tile-cut airside union, so a pocket whose enclosing pavement ring
# continues into the neighbour tile was never a hole in either tile's own
# union — the cut broke the ring, the hole opened toward the seam, and
# the pocket fell through to the open-edge band consumer (which covered
# 40k of its 52k m² and detached 12-25 m from the west/south frontage).
# With this gate ON the DETECTION union is healed with
# ``layout.tile_seam_offcuts`` — the exact dropped neighbour halves
# ``tile_cut`` records (evidence-bounded, never invents pavement; the
# same pattern the band-march prolongation ratified 2026-07-24) — and
# each detected hole is clipped straight back to the in-tile side of
# every cut-back line, its minted seam chords densified on the shared
# ``cutback_stations`` lattice so the two tiles' independent builds land
# the same seam nodes (chord stations take DEM at emission — the
# ``_SEAM_DEM_TERRAIN_ROLES`` contract).  No offcuts (every single-tile
# airport) => detection identical to the plain union, byte-identical
# output.
GAP_FILL_SEAM_HEAL_ENABLED = os.environ.get(
    "O4_GAP_FILL_SEAM_HEAL", "1") == "1"

_SEAM_CHORD_TOL_M = 0.02


def _tile_clip_specs(layout, airside, offcuts):
    """``(axis, line_coord, keep_sign)`` per integer tile line inside the
    HEALED footprint, in local metres — ``axis`` 0 for x (integer
    longitude), 1 for y (integer latitude); ``keep_sign`` points from the
    line INTO the current tile (every post-cut airside shape lies wholly
    in-tile, so any airside point decides the side).  Mirrors
    ``tile_cut.derive_tile_cut_lines`` — which cannot be reused directly
    here because the post-cut layout no longer straddles the line."""
    if layout.anchor is None or not airside:
        return []
    try:
        healed = unary_union([s.polygon for s in airside]
                             + list(offcuts))
        minx, miny, maxx, maxy = healed.bounds
        ref = airside[0].polygon.representative_point()
    except _GEOM_EXC:
        return []
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    min_lat = lat0 + math.degrees(miny / R_EARTH)
    max_lat = lat0 + math.degrees(maxy / R_EARTH)
    min_lon = lon0 + math.degrees(minx / (R_EARTH * cos0))
    max_lon = lon0 + math.degrees(maxx / (R_EARTH * cos0))
    specs = []
    for lat_int in range(
            int(math.ceil(min_lat)), int(math.floor(max_lat)) + 1):
        if min_lat < lat_int < max_lat:
            y_int = math.radians(lat_int - lat0) * R_EARTH
            specs.append((1, y_int, 1.0 if ref.y >= y_int else -1.0))
    for lon_int in range(
            int(math.ceil(min_lon)), int(math.floor(max_lon)) + 1):
        if min_lon < lon_int < max_lon:
            x_int = math.radians(lon_int - lon0) * R_EARTH * cos0
            specs.append((0, x_int, 1.0 if ref.x >= x_int else -1.0))
    return specs


def _densify_seam_chords(ring_pts, clip_specs):
    """Insert the shared ``cutback_stations`` lattice points on every
    ring segment that runs ALONG a tile cut-back line, so the seam edge
    of a clipped gap face carries the same stations the pavement and
    graded-strip seam pins use (cross-tile reproducible from the anchor
    frame alone)."""
    from .tile_cut import cutback_stations
    out: list[tuple[float, float]] = []
    n = len(ring_pts)
    for i in range(n):
        x0, y0 = ring_pts[i]
        x1, y1 = ring_pts[(i + 1) % n]
        out.append((x0, y0))
        for ax, coord, keep in clip_specs:
            cb = coord + keep * TILE_CUT_HALF_WIDTH_M
            a0 = x0 if ax == 0 else y0
            a1 = x1 if ax == 0 else y1
            if (abs(a0 - cb) <= _SEAM_CHORD_TOL_M
                    and abs(a1 - cb) <= _SEAM_CHORD_TOL_M):
                t0 = y0 if ax == 0 else x0
                t1 = y1 if ax == 0 else x1
                for t in cutback_stations(t0, t1):
                    out.append((cb, t) if ax == 0 else (t, cb))
                break
    return out


def _clip_gap_to_tile(gap_poly, clip_specs):
    """Clip one healed gap polygon back to the in-tile side of every
    cut-back line; returns the polygon part(s), seam chords densified."""
    parts = [gap_poly]
    for ax, coord, keep in clip_specs:
        cb = coord + keep * TILE_CUT_HALF_WIDTH_M
        nxt = []
        for g in parts:
            minx, miny, maxx, maxy = g.bounds
            pad = 100.0
            if ax == 0:
                lo = cb if keep > 0 else minx - pad
                hi = cb if keep < 0 else maxx + pad
                clip_box = box(lo, miny - pad, hi, maxy + pad)
            else:
                lo = cb if keep > 0 else miny - pad
                hi = cb if keep < 0 else maxy + pad
                clip_box = box(minx - pad, lo, maxx + pad, hi)
            try:
                res = g.intersection(clip_box)
            except _GEOM_EXC:
                continue
            for gg in getattr(res, "geoms", [res]):
                if gg.geom_type == "Polygon" and not gg.is_empty:
                    nxt.append(gg)
        parts = nxt
    out = []
    for g in parts:
        ring = _open_coords(g)
        if len(ring) < 3:
            continue
        try:
            p = Polygon(_densify_seam_chords(ring, clip_specs))
        except _GEOM_EXC:
            continue
        if not p.is_empty and p.is_valid:
            out.append(p)
    return out


def _gap_detection_polys(layout, airside):
    """The enclosed-gap candidate polygons for this layout — ONE
    definition shared by the pre-solve construction, the spine emitter
    and the pit-floor pass (parity is load-bearing: the emitter matches
    its spines against the pre-solve store by coordinate, so all three
    passes MUST detect off identical geometry).  Plain path: the
    interior holes of the post-cut airside union.  Seam-heal path (see
    ``GAP_FILL_SEAM_HEAL_ENABLED`` above): holes of the offcut-healed
    union, clipped back to the tile."""
    offcuts = ([p for p in (getattr(layout, "tile_seam_offcuts", None)
                            or ()) if p is not None and not p.is_empty]
               if GAP_FILL_SEAM_HEAL_ENABLED else [])
    try:
        union = unary_union([s.polygon for s in airside] + offcuts)
    except _GEOM_EXC:
        return []
    if union.is_empty:
        return []
    comps = ([union] if union.geom_type == "Polygon"
             else [g for g in getattr(union, "geoms", [])
                   if g.geom_type == "Polygon"])
    clip_specs = (_tile_clip_specs(layout, airside, offcuts)
                  if offcuts else [])
    gaps: list[Polygon] = []
    for comp in comps:
        for interior in comp.interiors:
            try:
                gap_poly = Polygon(list(interior.coords))
            except _GEOM_EXC:
                continue
            if gap_poly.is_empty or not gap_poly.is_valid:
                continue
            if clip_specs:
                gaps.extend(_clip_gap_to_tile(gap_poly, clip_specs))
            else:
                gaps.append(gap_poly)
    return gaps


# ══════════════════════════════════════════════════════════════════════
# RULING 3 (Fable 2026-08-12b) — EXCAVATION-RIM POCKETS
# ══════════════════════════════════════════════════════════════════════
#
# "A coverage hole whose boundary is >= 75 % graded features (apron /
# roads / junctions / groundside pavement / pads) is ENCLOSED for
# gap-fill purposes even with an open segment — extend R19-2's
# subdivision to this case."
#
# WHY IT IS A SEPARATE DETECTOR AND NOT A WIDER ``_gap_detection_polys``.
# That function's holes are also the ENCLAVE law's regions
# (``enclaves.compute_gap_law_regions``), where "interior ring of the
# airside union" is the published meaning and widening it would stand
# adjacent-ground bands down over ground the enclave law never claimed
# (its own docstring measures that regression at 152,734 m2).  So the
# rim pockets are their own list, and the THREE GAP PASSES — pre-solve
# construction, the spine emitter and the pit floor — each append it to
# their candidates through this one function.  Parity is by construction:
# same code, same inputs, at every pass.

#: The roles whose boundary counts as GRADED for the rim test — the
#: ruling's own list.  Airside comes from ``_airside_shapes``; these are
#: the rest.  Object pads are NOT here: a pad is terrain the pad law
#: itself values (and at the measured site it is what the pocket is being
#: graded FOR), so it bounds nothing.
_RIM_POCKET_EXTRA_ROLES = None       # bound lazily (import cycle-free)


def _rim_pocket_extra_roles():
    global _RIM_POCKET_EXTRA_ROLES
    if _RIM_POCKET_EXTRA_ROLES is None:
        from .layout import (ROLE_BUILDING, ROLE_GROUNDSIDE_PAVEMENT,
                             ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD)
        _RIM_POCKET_EXTRA_ROLES = frozenset({
            ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD,
            ROLE_SERVICE_JUNCTION, ROLE_BUILDING})
    return _RIM_POCKET_EXTRA_ROLES


#: A pocket-boundary segment this close to the graded union's boundary IS
#: that boundary.  The difference against the union is coordinate-exact on
#: every feature-facing side (GEOS does not perturb the union there), so
#: this only has to survive the closing's own rounding.
_RIM_POCKET_BOUNDARY_TOL_M = 0.05


def _rim_pocket_bounding_shapes(layout, airside):
    """The graded features a rim pocket may be bounded by: the airside
    union plus the ruling's groundside/road/junction/pad classes."""
    extra = _rim_pocket_extra_roles()
    out = list(airside)
    seen = {id(s) for s in airside}
    for s in layout.shapes:
        if id(s) in seen or s.role not in extra:
            continue
        p = getattr(s, "polygon", None)
        if p is None or p.is_empty or p.geom_type != "Polygon":
            continue
        out.append(s)
    return out


def _graded_rim(poly, graded_union) -> tuple:
    """``(graded_fraction, open_runs)`` for ``poly``'s exterior against
    ``graded_union``'s boundary.

    ``graded_fraction`` is the ruling's own measure: the share of the
    exterior LENGTH that runs along a graded feature.  A segment counts by
    its midpoint — the closing mints no partial segments, since a side is
    either the union's own boundary (kept coordinate-exact by the
    difference) or a buffered end cap well clear of it.

    ``open_runs`` counts the CONTIGUOUS non-graded arcs, circularly.  A
    RECESS — the excavation-rim pocket this law is for — has exactly one:
    the owner's knoll is "OPEN to the SW" and graded on every other side.
    Two or more open runs is a through CHANNEL between facing pavements,
    which is the open-frontage corridor pilot's subject
    (``O4_OPEN_FRONTAGE_SPINE``, default OFF pending the owner's in-sim
    review) — this law does not admit those through the back door.
    """
    try:
        boundary = graded_union.boundary
        ring = list(poly.exterior.coords)
    except _GEOM_EXC:
        return 0.0, 0
    total = 0.0
    graded = 0.0
    flags: list[bool] = []
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        seg = math.hypot(bx - ax, by - ay)
        if seg <= 0.0:
            continue
        total += seg
        on_rim = False
        try:
            on_rim = boundary.distance(
                Point(0.5 * (ax + bx), 0.5 * (ay + by))
            ) <= _RIM_POCKET_BOUNDARY_TOL_M
        except _GEOM_EXC:
            on_rim = False
        if on_rim:
            graded += seg
        flags.append(on_rim)
    if total <= 0.0 or not flags:
        return 0.0, 0
    runs = sum(1 for i, f in enumerate(flags)
               if not f and flags[i - 1])       # circular: i-1 wraps
    if runs == 0 and not any(flags):
        runs = 1                                # wholly open
    return graded / total, runs


def _rim_pocket_polys(layout, airside, enclosed=()):
    """RULING 3's candidate regions: the open-boundary pockets whose rim
    is >= ``GAP_FILL_RIM_POCKET_GRADED_FRACTION`` graded feature.

    PURE (no mutation, no values), so the pre-solve construction, the
    spine emitter and the pit floor all call it and see the same regions
    at their own stage.  ``enclosed`` is the interior-ring candidate list
    from ``_gap_detection_polys``: those holes belong to that path and are
    subtracted here, exactly as the open-corridor detector subtracts them.

    Each admitted pocket is returned as a VERBATIM face — feature-facing
    boundary is the features' own ring vertices, the open segment a
    straight closure between two of them (``_verbatim_boundary_face``, the
    open-corridor law's own classification) — so nothing downstream mints
    a node on a graded edge.
    """
    if not GAP_FILL_RIM_POCKETS_ENABLED:
        return []
    bounds = _rim_pocket_bounding_shapes(layout, airside)
    if len(bounds) < 2:
        return []
    try:
        union = unary_union([s.polygon for s in bounds])
    except _GEOM_EXC:
        return []
    if union.is_empty:
        return []
    subtract = None
    if enclosed:
        try:
            subtract = unary_union(list(enclosed))
        except _GEOM_EXC:
            subtract = None
    pockets = _detect_open_corridors(union, OPEN_FRONTAGE_CLOSE_M, subtract)
    if not pockets:
        return []
    exteriors = []
    ring_verts: list[tuple[float, float]] = []
    keys: set[tuple[int, int]] = set()
    for s in bounds:
        try:
            ext = s.polygon.exterior
        except _GEOM_EXC:
            continue
        exteriors.append(ext)
        for vx, vy in ext.coords[:-1]:
            ring_verts.append((float(vx), float(vy)))
            keys.add(_key(vx, vy))
    out: list = []
    for pocket in pockets:
        if pocket.is_empty or pocket.area < GAP_FILL_MIN_AREA_M2:
            continue
        _c = pocket.centroid
        frac, open_runs = _graded_rim(pocket, union)
        if frac < GAP_FILL_RIM_POCKET_GRADED_FRACTION:
            UI.vprint(1, f"  [rim-pocket] skipped region (rim "
                         f"{frac * 100:.0f} % graded < "
                         f"{GAP_FILL_RIM_POCKET_GRADED_FRACTION * 100:.0f} "
                         f"%) area={pocket.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})")
            continue
        if open_runs > 1:
            # A through channel between facing pavements, not a recess —
            # the open-frontage corridor pilot's subject, and its gate is
            # the owner's to flip.
            UI.vprint(1, f"  [rim-pocket] skipped region ({open_runs} open "
                         f"runs — a through channel, not an excavation "
                         f"rim; the open-frontage corridor law owns it) "
                         f"area={pocket.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})")
            continue
        built = _verbatim_boundary_face(pocket, exteriors, ring_verts, keys)
        if built is None:
            UI.vprint(1, f"  [rim-pocket] skipped region (non-verbatim / "
                         f"degenerate face) area={pocket.area:.0f} m2 "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})")
            continue
        # TRIM BACK TO THE POCKET.  The verbatim rebuild extends a mouth
        # vertex to the nearest bounding RING VERTEX (the pavement-node
        # rule, up to the closing radius), and on a recess that extension
        # can reach around a corner and lap the very feature it followed
        # — which the enclosed loop then reads as a foreign shape INSIDE
        # the region and vetoes (measured on the fixture: a 25,400 m²
        # face over its own 4,200 m² service road).  Differencing against
        # the graded union restores the features' own boundary
        # coordinate-exactly and leaves the straight mouth chord, so the
        # face is chain-identical AND cannot overlap its own rim.
        try:
            trimmed = built[0].difference(union)
        except _GEOM_EXC:
            continue
        parts = _poly_parts(trimmed)
        if not parts:
            continue
        face = max(parts, key=lambda g: g.area)
        if face.area < GAP_FILL_MIN_AREA_M2:
            continue
        UI.vprint(1, f"  [rim-pocket] excavation-rim pocket admitted (rim "
                     f"{frac * 100:.0f} % graded) area={face.area:.0f} m2 "
                     f"centroid=({face.centroid.x:.0f},"
                     f"{face.centroid.y:.0f})")
        out.append(face)
    return out


def _rim_pocket_width_rule(poly) -> bool:
    """Ruling 3's own width law — see
    ``_region_is_everywhere_narrower``."""
    return _region_is_everywhere_narrower(poly, GAP_FILL_MAX_WIDTH_M)


def _gap_candidate_polys(layout, airside):
    """THE GAP LAW'S CANDIDATE REGIONS — enclosed holes (R19-2's own
    detector) PLUS ruling 3's excavation-rim pockets.  The three gap
    passes call THIS, so a region is seen by all of them or by none.

    Returns ``(candidates, rim_ids)``: ``rim_ids`` are the ``id()``s of
    the rim-pocket entries, which carry their own width law downstream
    (and never the enclosed width-skip's collar treatment)."""
    enclosed = _gap_detection_polys(layout, airside)
    rim = _rim_pocket_polys(layout, airside, enclosed)
    return enclosed + rim, {id(p) for p in rim}


def _rim_airside_arm_mids(airside, gap_poly):
    """REPORTING ONLY — ``(n_mid, n_airside_mid)`` for a rim pocket:
    how many of the pocket's rim segment MIDPOINTS lie within
    ``_RIM_POCKET_BOUNDARY_TOL_M`` of an airside shape's exterior.

    THE STAGE VERDICT NEVER CONSULTS THIS (see ``_gap_host_stage``): a
    rim pocket is stage B whatever its rim is made of.  What the count
    still answers is HOW MUCH IMMUTABLE AIRSIDE BOUNDARY the stage-B
    spine reads — including the limit case the ruling's letter moves,
    a pocket whose rim is airside all the way round (``n_airside_mid ==
    n_mid``) — so the build says it in one census line instead of a
    later lane re-deriving it.

    Midpoints, not exterior-to-exterior distance, so a corner-only touch
    does not count — the identical measure ``_graded_rim`` uses for the
    graded fraction, and the reason the two cannot disagree about what
    "on the rim" means.  Membership is by IDENTITY against the
    ``airside`` list (``_airside_shapes`` built it from
    ``_AIRSIDE_PAVEMENT_ROLES``), so no role literal is spelled here."""
    try:
        ring = list(gap_poly.exterior.coords)
    except _GEOM_EXC:
        return (0, 0)
    mids = []
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        if math.hypot(bx - ax, by - ay) <= 0.0:
            continue
        mids.append(Point(0.5 * (ax + bx), 0.5 * (ay + by)))
    if not mids:
        return (0, 0)
    exts = []
    for s in airside:
        try:
            exts.append(s.polygon.exterior)
        except _GEOM_EXC:
            continue
    n_air = 0
    for m in mids:
        for ext in exts:
            try:
                if ext.distance(m) <= _RIM_POCKET_BOUNDARY_TOL_M:
                    n_air += 1
                    break
            except _GEOM_EXC:
                continue
    return (len(mids), n_air)


def _gap_host_stage(rim_pocket):
    """THE SOLVE STAGE of the gap face's ENCLOSURE HOST (staged-solve
    lanes S1d/S4; S4's measurement that a rim-pocket drainage spine
    WRITES AIRSIDE elevations when ``O4_GAP_FILL_RIM_POCKETS=1``).

    A gap-fill drainage spine is a CONSTRUCT over a host surface, and
    ``solve_stage``'s own rule for such a construct is "the stage of its
    HOST, never its own construct role" (``graded_strip`` is not a
    stage).  This function answers WHO THE HOST IS, and after the
    2026-08-14 ruling it is a two-line answer:

    * an ENCLOSED gap is, by construction of ``_gap_detection_polys``, an
      interior ring of the AIRSIDE union — airside-hosted with no
      geometry test at all: ``STAGE_A``.
    * a RIM POCKET is admitted precisely BECAUSE it is not such a ring
      (``_rim_pocket_bounding_shapes`` widens the rim to airside PLUS the
      ruling-3 groundside/road/junction/pad classes): ``STAGE_B``,
      UNCONDITIONALLY.

    RULINGS 2026-08-14, "RIM-POCKET SPINES ARE UNCONDITIONALLY STAGE B"
    (Fable, resolving S1d's stop) — the predecessor's conditional "one
    airside arm on the rim ⇒ ``STAGE_A``" branch REPEATED THE FALSE-
    ENCLOSURE PREMISE ONE LEVEL UP.  Airside-is-king means airside is
    never PULLED; it does not mean everything TOUCHING airside becomes an
    airside VARIABLE.  A rim-pocket spine RECEIVES: where a rim arm is
    airside, the spine reads that arm's settled stage-A value as an
    IMMUTABLE BOUNDARY — the corridor-mouth weld posture, and reading
    airside is the implementation of airside-is-king, not a violation of
    it.  The read is structural, not a promise: the spine's constraint
    entry carries ``STAGE_B`` into ``_partition_by_stage``, and its
    airside parent stations carry airside ring roles, so
    ``_receiver_nodes_from_roles`` never admits them as receivers and
    ``feasibility_project_partitioned`` freezes every non-receiver node
    for the whole groundside pass.  A write attempt is not possible to
    express; the rails would have to be removed first.

    NO ROLE LITERAL, NO GEOMETRY TEST, and in particular NOT
    ``solve_stage.stage_of_roles`` over the rim roles — that fold returns
    ``STAGE_A`` for ``{service_road, building}`` (``ROLE_BUILDING`` is not
    in ``layout.GROUNDSIDE_ROLES``), which is the conservative side for a
    NODE and the wrong side for an ENCLOSURE HOST.  A pad bounds ground;
    it does not make the ground airside.  Nothing about the rim's
    composition can reach this verdict any more, which is the ruling.
    """
    return _STAGE_B if rim_pocket else _STAGE_A


def _enclave_treatable(layout, poly):
    """The published enclave whose interior ``poly`` is AND whose ground
    the ruled treatment can actually take, or ``None`` — the gate on the
    whole enclave exemption (spec §3, width-scoped 2026-08-08).

    TWO conditions, and the second is not a refinement of the first:

      * ``enclave_covering`` — the region is enclave interior, so the
        shapes inside it are airside-interior contents the G-ENCLAVE
        re-verdict owns rather than foreign owners of the ground;
      * ``is_pocket_width`` — the GAP LAW can treat it.  The owner's
        sentence is "takes the gap interior ring and spine treatment",
        and that treatment is pocket-width ground's form; the same
        constant already scopes the band keep-out, so both halves of
        the enclave law now decline WIDE ground on ONE width test.

    Why the width half is load-bearing rather than tidy: without it the
    exemption does not GIVE a wide region the ruled treatment, it merely
    moves which machinery claims it.  The gap law declines the face on
    width a few lines below either way, after which
    ``_emit_pocket_collar_rings`` takes the region as a "width-skipped
    pocket" and its collared-pocket zone stands the adjacent-ground
    bands down over the whole of it.  Measured at HECA: the 3.40 km²
    infield (short side 1,264 m) is vetoed by the foreign shapes inside
    it in the control and keeps 150,438 m² of Annex 14 §3.4.11-13 graded
    strip; exempted, it was collared instead and lost every square metre
    of that band — with adjudicated airside rising in both constant-DEM
    worlds.  The conservative direction is also the control's: a wide
    region keeps the blocker set it has always had.
    """
    if not is_pocket_width(poly):
        return None
    return enclave_covering(layout, poly)


def _enclave_exempt(shape) -> bool:
    """True when the ENCLAVE law may exempt ``shape`` from the
    foreign-shape blocker (spec §3).

    The exemption covers the shapes an enclave interior CONTAINS and the
    enclave law re-verdicts — groundside pavement, terraces, bands and
    their walls.  Four classes are never exempt, and none is an
    exception to the law so much as a shape the law does not reach:

      * a SURROUND-role shape (``ENCLAVE_SURROUND_ROLES``) is part of the
        union that DEFINES the enclave — a building inside a hole is the
        owner's own escape-proof boundary material (CYXY building4), not
        interior contents, and its flat pad authority still governs the
        ground it stands on;
      * a RUNWAY-END REGIME shape (``RUNWAY_END_REGIME_REFS``) carries
        the governed runway-end profile.  Whether it BOUNDS a gap or
        BLOCKS it is decided by its own sub-gate
        (``O4_GAP_FILL_SKIRT_PARENTS``); the enclave law does not
        adjudicate that gate from underneath it;
      * a TUNNEL shape (``_TUNNEL_BLOCKER_ROLES`` /
        ``_TUNNEL_BLOCKER_REFS``, R6 owner spec 2026-08-10) is BELOW
        grade with its own portal profile — the enclave law re-verdicts
        surface pavement, not a law-cut hole, and a gap face graded over
        one puts the drainage spine THROUGH the ramp (OTHH S6);
      * a SERVICE ROAD / SERVICE JUNCTION (``_SERVICE_ROAD_BLOCKER_ROLES``,
        owner ruling 2026-08-15): gap-fill spines and drainage must STOP
        at a service road, never run through it.  Kept on the hard set,
        the road routes its pocket into the R19-2 subdivision (it is a
        ``_POCKET_SUBDIVIDER_ROLES`` member), so the residual pockets
        around it still take the ruled treatment — the spine stops at
        the road instead of burying it.  ``groundside_pavement`` is NOT
        ruled and stays exempt (open question, see the set's comment).
    """
    if getattr(shape, "role", None) in ENCLAVE_SURROUND_ROLES:
        return False
    if getattr(shape, "ref", None) in RUNWAY_END_REGIME_REFS:
        return False
    if getattr(shape, "role", None) in _TUNNEL_BLOCKER_ROLES:
        return False
    if getattr(shape, "ref", None) in _TUNNEL_BLOCKER_REFS:
        return False
    if getattr(shape, "role", None) in _SERVICE_ROAD_BLOCKER_ROLES:
        return False
    return True


def _gap_parents(layout):
    """The gap-parent shapes (building pads + runway-end skirts) per
    their sub-gates — shared by construction and emission (same parity
    argument as ``_airside_shapes``).  Gate-ON both exist PRE-solve:
    pads are phase-1 shapes; skirts are pre-solve under the B1 sub-gate
    (which the B2 gate REQUIRES — pipeline hard-error)."""
    _pad_parents = os.environ.get("O4_GAP_FILL_PAD_PARENTS", "1") == "1"
    _skirt_parents = os.environ.get(
        "O4_GAP_FILL_SKIRT_PARENTS", "1") == "1"
    pads = [s for s in layout.shapes
            if s.role == ROLE_BUILDING and s.polygon is not None
            and not s.polygon.is_empty
            and s.polygon.geom_type in ("Polygon", "MultiPolygon")] \
        if _pad_parents else []
    # The runway-end REGIME is carried by more than one ref on the same
    # role (the fill skirt and the RESA cut, arc A2 2026-07-24): select
    # on the frozen ``RUNWAY_END_REGIME_REFS`` set from ``layout`` — never
    # a literal ref string here.
    skirts = [s for s in layout.shapes
              if getattr(s, "ref", None) in RUNWAY_END_REGIME_REFS
              and s.polygon is not None and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"] \
        if _skirt_parents else []
    return pads, skirts


def _freeze_spine_parent_specs(layout, airside, px, py):
    """FROZEN-NEAREST station mapping (design open question 1, START
    FROZEN-NEAREST — ratified 2026-07-10): for spine point ``(px, py)``,
    the two nearest DISTINCT bounding pavement shapes (the same
    parent selection as the analytic ``_spine_interval``), each frozen
    to (a) its nearest ring VERTEX — the pavement chain station the
    envelope interval edge couples to — and (b) the envelope offsets
    ``adjacent_ground_envelope(role, code_number, code_letter, d)`` at
    the CONSTRUCTION-TIME lateral distance ``d`` to that parent's edge
    (``grade_law.drainage_spine_envelope`` under ``O4_DRAINAGE_SPINE_LAW``
    — the SAME binding ``_spine_interval`` reads, so the solver's slab and
    the analytic interval cannot disagree about the law).
    The station identity and ``d`` never re-derive as the solve moves
    elevations; the elevation coupling itself stays live through the
    interval edge.  A parent whose envelope is fully open
    ``(None, None)`` contributes no edge (mirrors the analytic path,
    where such a parent contributes only its edge altitude).

    Returns ``[(station_xy, floor_offset, ceiling_offset), ...]``
    (0-2 entries)."""
    p = Point(px, py)
    specs = []
    # OPT-1: identical two-nearest selection, STRtree-backed.
    for d, s in _airside_index(airside).two_nearest(p):
        role, cn, cl = _parent_family_code(layout, s)
        try:
            floor_off, ceil_off = _spine_envelope(
                role, cn, cl, max(0.0, d))
        except _GEOM_EXC:
            continue
        if floor_off is None and ceil_off is None:
            continue
        # Frozen station = the parent's nearest ring vertex (every
        # pavement ring vertex is a solver node, so the station is
        # mappable to a node index at constraint-build time).
        try:
            ring = _open_coords(s.polygon)
        except _GEOM_EXC:
            continue
        if not ring:
            continue
        sx, sy = min(ring, key=lambda v: (v[0] - px) ** 2
                                         + (v[1] - py) ** 2)
        specs.append(((float(sx), float(sy)),
                      None if floor_off is None else float(floor_off),
                      None if ceil_off is None else float(ceil_off)))
    return specs


def construct_gap_fill_presolve(layout) -> int:
    """Stage B2 PRE-SOLVE construction: detect the enclosed gaps and
    build their drainage-spine GEOMETRY before ``per_surface_solve`` so
    the spine vertices join the solver node list as FREE variables (the
    B0 admission hook reads ``layout.gap_fill_presolve``).  Values are
    NOT computed here — they come from the solve's writeback.

    The detection mirrors ``emit_gap_fill_spines`` geometry-for-geometry
    EXCEPT the blockers whose subjects do not exist yet pre-solve
    (legacy surface_clearance strips and the other post-solve features):
    those are evaluated at EMISSION, where they exist, exactly as today.
    Construction is therefore a SUPERSET of emission — a spine built for
    a gap that emission later blocks simply never emits (its solver
    variables settle inside their lawful envelope and are dropped).
    The mirroring includes the R19-2 SUBDIVISION (owner ruling
    2026-08-15): a hole vetoed only by its own groundside/service
    subdividers is split into its residual pockets here exactly as the
    emitter splits it, so the per-pocket spines coordinate-match the
    value store instead of the whole-hole spine that would never emit.

    Stores ``layout.gap_fill_presolve = [{"spine": [(x, y), ...],
    "specs": [per-node ``_freeze_spine_parent_specs`` list],
    "host_stage": ``_gap_host_stage`` verdict, "values": None}, ...]``
    and returns the entry count.  ``host_stage`` is the entry's SOLVE
    STAGE, decided at mint from the enclosure host and consumed by
    ``solver_primitives._build_gap_spine_constraints`` — an entry
    reaching that builder without one is a defect there, never a
    default."""
    if not GAP_FILL_SPINE_ENABLED:
        return 0
    airside = _airside_shapes(layout)
    if len(airside) < 2:
        return 0
    gap_candidates, rim_ids = _gap_candidate_polys(layout, airside)
    # ── THE ABSORPTION GATE IS RETIRED (S4, owner ruling 2026-08-13) ───
    # ``O4_RIM_PRESOLVE_ABSORB`` used to drop the rim pockets from this
    # construction so their spine vertices were never solver variables.
    # It was measured INERT in production (pockets default OFF ⇒
    # ``rim_ids`` empty ⇒ the branch never ran), and it is the wrong
    # shape of boundary: which constructs a solve stage may move is the
    # STAGE TAG's job (``solve_stage.py``), never a per-construct flag.
    # A rim pocket admitted here is a stage-B variable and stage A must
    # be structurally free of it — see
    # ``solver_primitives._build_gap_spine_constraints``.
    if not gap_candidates:
        return 0
    pads, skirts = _gap_parents(layout)
    parents = pads + skirts
    # Geometry-only chain-key set (the ``_face_is_verbatim`` gate needs
    # keys, not values): every airside + parent ring vertex.
    chain_keys: set[tuple[int, int]] = set()
    for s in airside:
        try:
            for vx, vy in s.polygon.exterior.coords:
                chain_keys.add(_key(vx, vy))
        except _GEOM_EXC:
            continue
    for p in parents:
        geoms = ([p.polygon] if p.polygon.geom_type == "Polygon"
                 else list(p.polygon.geoms))
        for g in geoms:
            try:
                for vx, vy in g.exterior.coords:
                    chain_keys.add(_key(vx, vy))
            except _GEOM_EXC:
                continue
    airside_ids = {id(s) for s in airside}
    parent_ids = {id(s) for s in parents}
    # Foreign blockers PRESENT pre-solve (bridge plates, boundary…).
    # Post-solve-only features are checked at emission instead.
    other_polys = [(id(s), s.polygon) for s in layout.shapes
                   if id(s) not in airside_ids
                   and id(s) not in parent_ids
                   and s.polygon is not None and not s.polygon.is_empty
                   and s.polygon.geom_type in ("Polygon", "MultiPolygon")]
    # The ones an ENCLAVE interior may exempt (spec §3, width-scoped by
    # ``_enclave_treatable``) — the emitter's rule, mirrored so
    # construction stays a superset of emission.
    hard_polys = [(id(s), s.polygon) for s in layout.shapes
                  if id(s) not in airside_ids
                  and id(s) not in parent_ids
                  and s.polygon is not None and not s.polygon.is_empty
                  and s.polygon.geom_type in ("Polygon", "MultiPolygon")
                  and not _enclave_exempt(s)]
    # CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-terrain-
    # ownership.md): the published zone blocks a gap exactly like a
    # foreign shape — a gap-fill face must never bury a crossing or its
    # depressed public road (round-8 finding: gap-fill was the fourth
    # corridor consumer, and the only one that never clipped).  Published
    # pre-solve, so this construct pass and the emitter see the identical
    # geometry (the coordinate-matching parity both rely on).
    from .crossing_terrain import crossing_influence_zone_union
    _crossing_zone = crossing_influence_zone_union(layout)
    zone_polys = ([(0, _crossing_zone)] if _crossing_zone is not None
                  else [])
    step = GAP_FILL_SPINE_STEP_M
    entries: list[dict] = []
    _rim_seen = _rim_with_airside = _rim_all_airside = 0
    for gap_poly in gap_candidates:
            if gap_poly.area < GAP_FILL_MIN_AREA_M2:
                continue
            # ENCLAVE INTERIOR (spec §3) — the emitter's rule, mirrored
            # here so construction stays a superset of emission.
            blockers = (hard_polys + zone_polys
                        if _enclave_treatable(layout, gap_poly) is not None
                        else other_polys + zone_polys)
            overlapped = False
            for _oid, op in blockers:
                try:
                    if gap_poly.intersection(op).area > 1.0:
                        overlapped = True
                        break
                except _GEOM_EXC:
                    continue
            subdivided = None
            if overlapped and _veto_is_only_subdividers(
                    layout, gap_poly, blockers):
                # ── R19-2 SUBDIVISION, MIRRORED (owner ruling 2026-08-15)
                # The emitter subdivides a hole vetoed only by its own
                # groundside/service subdividers; the SUPERSET contract
                # and the coordinate-matched value store require the
                # pre-solve constructor to mint spines for the SAME
                # residual pockets, or every such pocket emits on the
                # analytic fallback.  Identical guard: the subdivision
                # stands only if every residual pocket is itself under
                # the width cap — otherwise the veto stands, as in the
                # emitter.
                _parts = _subdivide_enclosed_face(layout, gap_poly,
                                                  chain_keys)
                _all_pocket = bool(_parts)
                for _pt in _parts:
                    try:
                        _ax = _mrr_axes(min_rotated_rect(_pt))
                    except _GEOM_EXC:
                        _all_pocket = False
                        break
                    if _ax is None or _ax[0] is None \
                            or _ax[0] > GAP_FILL_MAX_WIDTH_M:
                        _all_pocket = False
                        break
                if _all_pocket:
                    subdivided = _parts
                    overlapped = False
            if overlapped:
                continue
            # THE ENCLOSURE HOST'S STAGE, once per candidate (S1d): every
            # face and every station of this gap shares one enclosure, so
            # the question is asked of the CANDIDATE, not of each face.
            # ``id(gap_poly) in rim_ids`` is the rim-pocket membership
            # test the width rule below already uses, and after the
            # 2026-08-14 ruling it is the WHOLE question.
            _is_rim = id(gap_poly) in rim_ids
            host_stage = _gap_host_stage(_is_rim)
            _n_before = len(entries)
            # BODIES: the subdivided residual pockets when the R19-2
            # branch above took the hole, else the whole gap — the same
            # ``_bodies`` fold the emitter applies, so the spines minted
            # here coordinate-match the ones it will emit.
            _bodies = subdivided if subdivided else [gap_poly]
            faces = []
            for _body in _bodies:
                faces.extend(
                    _parent_residual_faces(_body, parents, chain_keys)
                    if parents else [_body])
            for face_poly in faces:
                if face_poly.is_empty or not face_poly.is_valid:
                    continue
                if face_poly.area < GAP_FILL_MIN_AREA_M2:
                    continue
                try:
                    axes = _mrr_axes(min_rotated_rect(face_poly))
                except _GEOM_EXC:
                    continue
                if axes is None or axes[1] is None:
                    continue
                short_side, long_dir, long_len = axes
                if short_side > GAP_FILL_MAX_WIDTH_M and not (
                        id(gap_poly) in rim_ids
                        and _rim_pocket_width_rule(face_poly)):
                    # Ruling 3: a rim pocket is gated on its own width
                    # law here too, so the pre-solve spine EXISTS for the
                    # regions the emitter will grade (parity — otherwise
                    # every rim pocket emits on the analytic fallback).
                    continue
                spine = _build_spine(face_poly, long_dir, long_len, step)
                if spine is None:
                    continue
                specs = [_freeze_spine_parent_specs(layout, airside, px, py)
                         for px, py in spine]
                entries.append({"spine": [(float(px), float(py))
                                          for px, py in spine],
                                "specs": specs,
                                "host_stage": host_stage,
                                "values": None})
            # ONE CENSUS LINE PER BUILD, rim pockets only (below).  The
            # stage is already decided; this measures the BOUNDARY the
            # stage-B spine will read — and names the limit case the
            # ruling's letter moves, a pocket whose rim is airside all
            # the way round.  Only candidates that actually minted a
            # spine are counted, so the line describes what solved.
            if _is_rim and len(entries) > _n_before:
                _n_mid, _n_air = _rim_airside_arm_mids(airside, gap_poly)
                _rim_seen += 1
                if _n_air:
                    _rim_with_airside += 1
                if _n_mid and _n_air == _n_mid:
                    _rim_all_airside += 1
    layout.gap_fill_presolve = entries
    if entries:
        n_pts = sum(len(e["spine"]) for e in entries)
        UI.vprint(1, f"  [gap-fill] PRE-SOLVE constructed {len(entries)} "
                     f"drainage spine(s), {n_pts} solver node(s) "
                     f"(one-solve terrain absorption, stage B2).")
    if _rim_seen:
        UI.vprint(1, f"  [gap-fill] rim-pocket stage census: {_rim_seen} "
                     f"pocket(s), ALL stage B (RULINGS 2026-08-14); "
                     f"{_rim_with_airside} read >=1 immutable airside rim "
                     f"arm, {_rim_all_airside} airside-enclosed all round.")
    return len(entries)


def _solved_spine_values(layout, spine):
    """Stage B2 gate-ON valuation: the solve-writeback values for
    ``spine``, matched against ``layout.gap_fill_presolve`` by
    coordinate (same station count, every point within 0.01 m — the
    construction is deterministic from the gap geometry, so pre-solve
    and emission-time spines coincide; the tolerance absorbs
    float-level drift from conformance-densified rings).  Returns the
    value list or None (no store / no match / unwritten entry)."""
    entries = getattr(layout, "gap_fill_presolve", None)
    if not entries:
        return None
    for entry in entries:
        vals = entry.get("values")
        if not vals or len(entry["spine"]) != len(spine):
            continue
        if any(v is None for v in vals):
            continue
        if all(math.hypot(ex - px, ey - py) <= 0.01
               for (ex, ey), (px, py) in zip(entry["spine"], spine)):
            return list(vals)
    return None


def emit_gap_fill_spines(layout, dem, tile_lat, tile_lon,
                         source_runways=None) -> int:
    """Grade every enclosed gap of the airside pavement union as one unit
    (gate ``GAP_FILL_SPINE_ENABLED``).  Mutates ``layout.shapes``; returns
    the number of ``graded_strip`` half-gap faces emitted.

    ``dem`` / ``tile_lat`` / ``tile_lon``: the spine drainage solve is
    PURE law + pavement reads (an enclosed gap is bounded by pavement on
    all sides, so the DEM never enters the interior SPINE value); the
    INTERIOR-RING violation trigger (gate ``O4_GAP_FILL_INTERIOR_RINGS``)
    does read the DEM — rings emit only where the interior genuinely
    drops below the band floor.  ``source_runways`` (the apt.dat runway
    rows) keys runway-bounded ring widths by the TRUE ICAO code
    (ratified answer 1); None falls back to the segment-chord proxy.
    """
    if GAP_FILL_INTERIOR_RINGS_ENABLED and not GAP_FILL_SPINE_ENABLED:
        # HARD ERROR, not silent no-op (fail-loudly doctrine, the B2
        # gate-dependency pattern): the rings are constructed BY the
        # gap emitter, so this configuration can produce nothing.
        # RuntimeError deliberately — the pipeline's _GEOM_EXC wrapper
        # (ValueError + shapely) must NOT swallow a configuration error.
        raise RuntimeError(
            "O4_GAP_FILL_INTERIOR_RINGS requires O4_GAP_FILL_SPINE=1: "
            "interior rings are constructed by the gap-fill emitter "
            "(ratified design 2026-07-11); enable both or neither.")
    if not GAP_FILL_SPINE_ENABLED:
        return 0
    airside = _airside_shapes(layout)
    if len(airside) < 2:
        return 0
    # NO early return on an empty candidate list: the open-frontage
    # pilot below runs on corridor geometry, not holes.
    gap_candidates, rim_ids = _gap_candidate_polys(layout, airside)

    # WELD-VALUE registry (mm key): every airside ring vertex → its solved
    # value, so a gap-ring vertex (which IS a pavement ring vertex) emits
    # the pavement value VERBATIM.  First writer wins.
    registry: dict[tuple[int, int], float] = {}
    for s in airside:
        na = s.node_altitudes
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        for i, (vx, vy) in enumerate(coords):
            if na and i < len(na) and na[i] is not None:
                value = float(na[i])
            elif not na and s.altitude is not None:
                value = float(s.altitude)
            else:
                continue
            k = _key(vx, vy)
            if k not in registry:
                registry[k] = value

    # GAP PARENTS (user design 2026-07-09 queue item 5 + supervisor
    # follow-up).  Two parent families, each behind its own sub-gate
    # (separate gates keep each law independently A/B-able against the
    # shipped gap-fill — a pad regression and a skirt regression bisect
    # apart):
    #   * BUILDING PADS (O4_GAP_FILL_PAD_PARENTS, default ON): FLAT with
    #     an authoritative value (user ruling: buildings are flat) —
    #     apron-family envelope members.
    #   * RUNWAY-END SKIRTS (O4_GAP_FILL_SKIRT_PARENTS, default ON):
    #     NON-flat — their ring vertices carry the governed inverse-RESA
    #     runway-end profile (per-vertex node_altitudes; skirt anchored
    #     at the runway end, dev 9345739).  The skirt shape itself keeps
    #     emitting exactly as today; the gap fills AROUND it.
    # A parent BOUNDS a gap the way pavement does, so it is NOT a
    # blocker.  A hole with a parent inside is graded on the RESIDUAL
    # ground only; the parent's value WINS at parent-ring nodes —
    # per-vertex for skirts, flat for pads — registered here AFTER
    # pavement (first-writer-wins keeps pavement winning at any shared
    # node: the pavement-value-wins ruling) — and the parent ring is a
    # VERBATIM boundary chain (zero new boundary vertices).
    pads, skirts = _gap_parents(layout)
    parents = pads + skirts
    # Geometry-only key set for the verbatim gate: every pavement +
    # parent ring vertex.  A residual boundary vertex outside this set
    # is a difference-minted crossing point (not chain-safe).
    chain_keys: set[tuple[int, int]] = set(registry)
    for p in parents:
        flat_value = _parent_flat_value(p)
        geoms = ([p.polygon] if p.polygon.geom_type == "Polygon"
                 else list(p.polygon.geoms))
        for g in geoms:
            try:
                coords = list(g.exterior.coords)
            except _GEOM_EXC:
                continue
            # Per-vertex values only when the altitude list aligns with
            # THIS ring (single-Polygon shapes — skirts always; pads in
            # synthetic fixtures); a MultiPolygon pad falls back to its
            # flat value.
            na = (p.node_altitudes
                  if (g is p.polygon and p.node_altitudes) else None)
            for i, (vx, vy) in enumerate(coords):
                k = _key(vx, vy)
                chain_keys.add(k)
                if na and i < len(na) and na[i] is not None:
                    registry.setdefault(k, float(na[i]))  # pavement wins
                elif flat_value is not None:
                    registry.setdefault(k, flat_value)    # pavement wins

    airside_ids = {id(s) for s in airside}
    parent_ids = {id(s) for s in parents}
    # LEGACY SUPERSESSION (user 2026-07-09: 13 of 27 CYXY holes were
    # blocked ONLY by legacy surface_clearance strips — the chain the
    # gap-fill replaces).  A legacy strip lying WHOLLY inside a gap is
    # removable (a whole-piece drop is chain-safe; the gap's drainage
    # surface supersedes the strip's cut).  Skirts and every other
    # feature stay blockers.
    # Gate: default ON since the OPEN-WAY spine redesign (2026-07-09
    # round 2) — the boundary-landing sliver class died by construction
    # and the CYXY supersession audit reads zero new lenses (the
    # near-parallel count equals the pre-gap baseline's own).
    _supersede = os.environ.get(
        "O4_GAP_FILL_SUPERSEDE", "1") == "1"
    legacy_strips = [s for s in layout.shapes
                     if getattr(s, "ref", None) == "surface_clearance"
                     and s.polygon is not None
                     and not s.polygon.is_empty] if _supersede else []
    legacy_ids = {id(s) for s in legacy_strips}
    # Gap parents (building pads / runway-end skirts, per their gates)
    # are EXCLUDED from the blocker set — they bound the gap (handled in
    # _parent_residual_faces), not block it.  Every other foreign shape
    # (groundside, service, retaining wall …) still blocks.
    other_polys = [(id(s), s.polygon) for s in layout.shapes
                   if id(s) not in airside_ids
                   and id(s) not in legacy_ids
                   and id(s) not in parent_ids
                   and s.polygon is not None and not s.polygon.is_empty
                   and s.polygon.geom_type in ("Polygon", "MultiPolygon")]
    # The blockers an ENCLAVE interior may NOT exempt (``_enclave_exempt``):
    # the enclave's own surround material and the runway-end regime.
    hard_polys = [(id(s), s.polygon) for s in layout.shapes
                  if id(s) not in airside_ids
                  and id(s) not in legacy_ids
                  and id(s) not in parent_ids
                  and s.polygon is not None and not s.polygon.is_empty
                  and s.polygon.geom_type in ("Polygon", "MultiPolygon")
                  and not _enclave_exempt(s)]
    # CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-terrain-
    # ownership.md): the published zone blocks a gap exactly like a
    # foreign shape, and the open-frontage path subtracts it so a
    # corridor SPLITS around the depressed road instead of burying it
    # (round-8 finding: a gap-fill strip buried the tunnel=yes road at
    # 36.1106,-86.6834 — gap-fill was the only corridor consumer that
    # never clipped).  Same published geometry the pre-solve construct
    # pass consulted, so the coordinate-matching parity holds.
    from .crossing_terrain import crossing_influence_zone_union
    _crossing_zone = crossing_influence_zone_union(layout)
    zone_polys = ([(0, _crossing_zone)] if _crossing_zone is not None
                  else [])

    step = GAP_FILL_SPINE_STEP_M
    # Runway axes for the interior-ring / pocket-collar width keying
    # (gate-ON only — with both gates OFF nothing reads them, keeping the
    # plain path untouched).
    _ring_axes = (_ring_runway_axes(layout, source_runways)
                  if (GAP_FILL_INTERIOR_RINGS_ENABLED
                      or POCKET_COLLAR_RINGS_ENABLED) else None)
    emitted = 0
    for gap_poly in gap_candidates:
            # Ring coords stay verbatim — detection already produced the
            # final gap polygons (seam-healed + tile-clipped when offcuts
            # exist; see ``_gap_detection_polys``).
            if gap_poly.area < GAP_FILL_MIN_AREA_M2:
                continue
            # A foreign shape inside the gap (groundside / service /
            # retaining wall …) means the corridor bands own it — skip.
            # Gap parents (building pads / runway-end skirts) are NOT in
            # ``other_polys`` when their law is on: they bound the gap
            # (handled below).  Legacy surface_clearance strips are NOT
            # blockers either: wholly-inside ones are superseded
            # (removed) when the gap emits; a PARTIALLY-inside strip
            # blocks (cutting it would mutate a welded ring — only
            # whole-piece drops are chain-safe).
            #
            # ENCLAVE INTERIOR (spec §3, owner 2026-08-07): a gap that IS
            # a published enclave is airside-interior by law — "such an
            # area is airside-interior and takes the gap interior ring +
            # spine treatment".  Its contents are re-verdicted by
            # G-ENCLAVE (``enclaves`` + ``pavement_scoring``), so a shape
            # sitting inside it is not a foreign owner of that ground and
            # never vetoes the ruled treatment.  This gate is what minted
            # the specimen retaining wall: a 5.58 m² groundside sliver
            # (over the 1.0 m² bar) sent a 1,914.6 m² apron-ringed void to
            # the band consumer, which owed it a 7.4 m wall — and the same
            # line explains all five HECA voids of the class (dossier §3).
            # The published CROSSING ZONE still blocks unconditionally: a
            # crossing means a tunnel/bridge, which is the owner's escape
            # clause, so such a region is not an enclave in the first
            # place.  And the exemption is WIDTH-SCOPED — see
            # ``_enclave_treatable``: a region the gap law will decline
            # on width gains nothing from it and loses its bands to the
            # pocket-collar machinery instead (HECA's 3.40 km² infield).
            _covering = _enclave_treatable(layout, gap_poly)
            blockers = (hard_polys + zone_polys
                        if _covering is not None
                        else other_polys + zone_polys)
            overlapped = False
            _blocker = None
            for _oid, op in blockers:
                try:
                    _ov = gap_poly.intersection(op).area
                    if _ov > 1.0:
                        overlapped = True
                        _blocker = (_oid, op, _ov)
                        break
                except _GEOM_EXC:
                    continue
            subdivided = None
            if overlapped and _veto_is_only_subdividers(
                    layout, gap_poly, blockers):
                # ── R19-2: SUBDIVIDE INSTEAD OF SKIP ──────────────────
                # MEASURED (HECA arm 2026-08-12, the owner's pocket at
                # 30.1165544,31.4112743): the pocket is lost at THIS
                # line, not at the width test — a 19,080 m² enclosed
                # hole vetoed by a single service_junction overlapping
                # it by 37 m².  A groundside/service surface standing in
                # an enclosed hole is not a foreign owner of that
                # ground: it BOUNDS it, exactly as a building pad does
                # (``_parent_residual_faces``), and the pockets between
                # them are what the drainage law is for.
                #
                # THE GUARD, and it is what keeps this from being a cap
                # raise in disguise: the subdivision stands ONLY if
                # every residual pocket is itself POCKET WIDTH.  HECA's
                # 3.40 km² infield is vetoed by a service_junction too;
                # subdividing it would hand its parts to the width skip
                # and the pocket-collar rings, which stand the
                # adjacent-ground bands down over the whole region (the
                # measurement in ``_enclave_treatable``: 150,438 m² of
                # Annex 14 §3.4.11-13 graded strip lost).  Its parts are
                # far over the cap, so the subdivision is ABANDONED and
                # the region keeps the veto it has always had.
                _parts = _subdivide_enclosed_face(layout, gap_poly,
                                                  chain_keys)
                _all_pocket = bool(_parts)
                for _pt in _parts:
                    try:
                        _ax = _mrr_axes(min_rotated_rect(_pt))
                    except _GEOM_EXC:
                        _all_pocket = False
                        break
                    if _ax is None or _ax[0] is None \
                            or _ax[0] > GAP_FILL_MAX_WIDTH_M:
                        _all_pocket = False
                        break
                _c = gap_poly.centroid
                if _all_pocket:
                    UI.vprint(1,
                        f"  [gap-fill] enclosed hole vetoed ONLY by its "
                        f"own groundside/service subdividers and every "
                        f"residual pocket is under the width cap "
                        f"(area={gap_poly.area:.0f} m2 "
                        f"centroid=({_c.x:.0f},{_c.y:.0f})) — "
                        f"subdividing instead of skipping.")
                    subdivided = _parts
                    overlapped = False
                else:
                    UI.vprint(1,
                        f"  [gap-fill] enclosed hole subdivision "
                        f"ABANDONED (residual pocket over the width cap, "
                        f"or nothing chain-safe) area={gap_poly.area:.0f} "
                        f"m2 centroid=({_c.x:.0f},{_c.y:.0f}) — the veto "
                        f"stands.")
            if overlapped:
                _c = gap_poly.centroid
                # NAME THE BLOCKER (instrument truth, owner 2026-08-06):
                # the bare "foreign shape inside" line said a gap was
                # vetoed but never by WHAT, so an arm that lifts some
                # vetoes and not others cannot be attributed from its own
                # log — SPJC's 213,743 m² pocket carried the identical
                # line in both arms of the v1 verification and cost a
                # round to chase.  The report says which shape, how much
                # of the gap it covers, and whether the enclave law
                # reached the gap at all (``enclave=`` covered / none:
                # ``enclave_covering`` needs half the gap inside ONE
                # published enclave, so a region the surround union
                # subdivides reads ``none`` and keeps the FULL blocker
                # set).  Numbers and frame only — the verdict is the
                # law's.
                _bs = None
                if _blocker is not None:
                    _bs = next((s for s in layout.shapes
                                if id(s) == _blocker[0]), None)
                _who = (f"{getattr(_bs, 'role', '?')}/"
                        f"{getattr(_bs, 'ref', '') or ''} "
                        f"overlap={_blocker[2]:.0f} m2"
                        if _bs is not None else
                        (f"crossing_zone overlap={_blocker[2]:.0f} m2"
                         if _blocker is not None else "?"))
                UI.vprint(1, f"  [gap-fill] skipped gap (foreign shape "
                             f"inside) area={gap_poly.area:.0f} m2 "
                             f"centroid=({_c.x:.0f},{_c.y:.0f}) "
                             f"blocker={_who} "
                             f"enclave={'covered' if _covering is not None else 'none'} "
                             f"blocker_set="
                             f"{'hard' if _covering is not None else 'all'}")
                continue
            superseded = []
            for s in legacy_strips:
                try:
                    inside = gap_poly.intersection(s.polygon).area
                except _GEOM_EXC:
                    inside = 0.0
                if inside <= 1.0:
                    continue
                if inside < 0.99 * s.polygon.area:
                    overlapped = True     # partial straddle — block
                    break
                superseded.append(s)
            if overlapped:
                _c = gap_poly.centroid
                UI.vprint(1, f"  [gap-fill] skipped gap (partial-"
                             f"straddle legacy strip) area="
                             f"{gap_poly.area:.0f} m2 "
                             f"centroid=({_c.x:.0f},{_c.y:.0f})")
                continue
            # FACES to grade: the whole gap, or — when gap parent(s)
            # (building pads / runway-end skirts) bound it — the
            # RESIDUAL ground around the parent(s), each a chain-safe
            # part (parent-fill → lawful vanish; non-verbatim →
            # blocked; both logged in the helper).
            _bodies = subdivided if subdivided else [gap_poly]
            faces = []
            for _body in _bodies:
                faces.extend(
                    _parent_residual_faces(_body, parents, chain_keys)
                    if parents else [_body])
            n_faces = 0
            # RULING 3: a rim pocket carries its own width law (the MRR
            # over-reports a rim-following sliver) and never the collar.
            _wrule = (_rim_pocket_width_rule
                      if id(gap_poly) in rim_ids else None)
            for face_poly in faces:
                n_faces += _grade_face(
                    layout, airside, face_poly, step, registry,
                    dem=dem, tile_lat=tile_lat, tile_lon=tile_lon,
                    rw_axes=_ring_axes, width_rule=_wrule)
            if n_faces and superseded:
                _sup_ids = {id(s) for s in superseded}
                layout.shapes[:] = [s for s in layout.shapes
                                    if id(s) not in _sup_ids]
                legacy_strips[:] = [s for s in legacy_strips
                                    if id(s) not in _sup_ids]
                UI.vprint(1,
                    f"  [gap-fill] superseded "
                    f"{len(_sup_ids)} legacy surface_clearance "
                    f"strip(s) inside an emitted gap.")
            emitted += n_faces

    # ── OPEN-FRONTAGE CORRIDOR SPINE (slice B pilot, ruling 3) ──────────
    # The enclosed-gap loop above owns interior rings.  This pilot, behind
    # its OWN sub-gate (default OFF — Noah has not reviewed it in-sim),
    # additionally owns OPEN corridors between facing pavements (a runway ↔
    # parallel-taxiway strip and similar): ground bounded by two pavement
    # chains on its long sides but open at the ends, which the legacy
    # surface_clearance chain used to grade and the corridor bands do
    # badly once it is deleted.  A no-op with the gate off.
    if os.environ.get("O4_OPEN_FRONTAGE_SPINE", "0") == "1":
        # The open-corridor detection runs on the PLAIN in-tile airside
        # union (open corridors are not holes, so the seam-heal path
        # above never concerns them).
        try:
            _of_union = unary_union([s.polygon for s in airside])
        except _GEOM_EXC:
            _of_union = None
        if _of_union is not None and not _of_union.is_empty:
            _of_comps = ([_of_union]
                         if _of_union.geom_type == "Polygon"
                         else [g for g in getattr(_of_union, "geoms", [])
                               if g.geom_type == "Polygon"])
            emitted += _emit_open_frontage(
                layout, airside, _of_comps, _of_union, registry,
                chain_keys, other_polys, parents, step,
                hard_polys=hard_polys)
    # Stage B2 movement report: solved-vs-analytic spine value deltas
    # accumulated per emitted gap (gate-ON only — the store is empty or
    # absent gate-OFF).
    _deltas = getattr(layout, "_gap_spine_value_deltas", None)
    if _deltas:
        _ds = sorted(_deltas)
        UI.vprint(1, f"  [gap-fill] stage B2 solved-vs-analytic spine "
                     f"values: n={len(_ds)} worst={_ds[-1]:.2f} m "
                     f"median={_ds[len(_ds) // 2]:.2f} m.")
    _grings_total = getattr(layout, "gap_interior_rings", None)
    if _grings_total:
        UI.vprint(1, f"  [gap-fill] interior rings TOTAL: "
                     f"{len(_grings_total)} chain(s), "
                     f"{sum(len(_gp) for _gp, _ga in _grings_total)} "
                     f"node(s) (gate O4_GAP_FILL_INTERIOR_RINGS).")
    return emitted


def _pocket_is_collared(gap_poly, collars) -> bool:
    """True when ``gap_poly`` is (or contains) a pocket the collar pass
    already took — the legacy pit clamp must not also govern it.  The
    collar records a FACE of the pocket (the pocket itself when no gap
    parent sits inside), so the test is "most of the collared face lies
    in this pocket"."""
    for rec in collars:
        face = rec.get("pocket")
        if face is None or face.is_empty:
            continue
        try:
            if gap_poly.intersection(face).area > 0.5 * face.area:
                return True
        except _GEOM_EXC:
            continue
    return False


def _pocket_pit_floor_v2(layout, rec, dem, tile_lat, tile_lon,
                         other_polys, other_shapes=()) -> int:
    """PIT FLOOR v2 (arc B2, 2026-07-24) for ONE collared pocket.

    Replaces the 2026-07-19 whole-pocket flat clamp.  The four defects
    it retires, and what stands in their place:

    * SCOPE — the old pass owned the WHOLE pocket.  v2 runs INSIDE the
      ring-2 CORE only (``rec["core"]``).  Outside it the collar rings
      own the ground; a pit patch never reaches the pavement.
    * REFERENCE — the old pass used the MEDIAN solved pavement value
      over the entire pocket ring (locally meaningless: at SPJC the
      461 m pocket's median lip was 18.6 m while the junctions right
      there sit at 12.4-13.5 m).  v2 reads the ring-2 station clamp
      values as a nearest-dominated CONTINUOUS field — the LOCAL law
      surface.  There is no median.
    * FLOOR — ``local_ring2_value − GAP_FILL_INTERIOR_FLOOR_DEPTH_M``.
      The constant keeps its VALUE; its MEANING is re-specified from
      "below the pocket-median pavement lip" to "below the LOCAL
      ring-2 law surface".  The floor is therefore a field over the
      pocket, not one number.
    * VALUES — per-vertex ``node_altitudes``: each rim vertex takes
      ``max(DEM, local_floor)``.  On the daylight contour that IS the
      DEM, so the patch meets natural ground continuously instead of
      ending in a wall; the flat ``[round(floor,2)] * len(ring)``
      plateau is gone.

    Geometry: the grid detection is kept, but the raw axis-aligned cell
    union is morphologically OPENED then CLOSED at the rings'
    ``_RING_MIN_FEATURE_RADIUS_M`` (the same ``_smooth_region`` law the
    collar loops use), so the footprint is no longer an orthogonal
    staircase of sample cells.  Clips are EXACT — no ``buffer(-0.5)``
    inset, no ``buffer(0.25)`` foreign standoff (the 2026-07-09 WELD
    RULING: a standoff leaves a groove of raw DEM that the mesh renders
    as a knife-edge blade); shared boundaries share coordinates.

    TRIGGER (no new magic numbers): a candidate region must contain at
    least one station where the DEM sits more than
    ``CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"]`` BELOW the local
    floor — the codebase's obstruction-trigger convention — and must
    reach ``GAP_FILL_MIN_AREA_M2`` of connected area.

    Returns the number of pit patches emitted."""
    import numpy as np

    depth = GAP_FILL_INTERIOR_FLOOR_DEPTH_M
    core = rec.get("core")
    stations = rec.get("ring2") or []
    if depth <= 0.0 or core is None or core.is_empty or not stations:
        return 0
    trigger = CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"]

    # LOCAL law surface: the ring-2 station clamp values (benched where
    # the ring emitted, raw clamp where the economy gate suppressed the
    # chains — the law is the same either way), read as a CONTINUOUS
    # field by inverse-distance-SQUARED (Shepard) blending.
    #
    # Nearest-station lookup was the first cut and it is wrong: a
    # Voronoi field is piecewise CONSTANT, so every cell boundary is a
    # step, and where the detected region's edge lands on one the rim
    # renders as a wall (measured SPJC 2026-07-24: a 5.02 m rim step at
    # local (487,-246), floor 17.15 over DEM 12.13).  With a continuous
    # floor field the daylight contour ``{DEM == floor}`` is a true
    # level set, so the rim meets natural ground BY CONSTRUCTION.  1/d^2
    # is nearest-dominated — the blend stays LOCAL, which is the whole
    # point of the reference change; it is emphatically not a
    # whole-pocket median.
    _sx = np.array([float(r["pt"][0]) for r in stations])
    _sy = np.array([float(r["pt"][1]) for r in stations])
    _sv = np.array([float(r.get("benched", r["v"])) for r in stations])

    def _floor_at(px, py):
        w = 1.0 / np.maximum((_sx - px) ** 2 + (_sy - py) ** 2, 1e-6)
        return float((w * _sv).sum() / w.sum()) - depth

    from .elevation import _sample_dem

    def _dem_at(px, py):
        lat, lon = layout.m_to_ll(px, py)
        return _sample_dem(dem, tile_lat, tile_lon, lat, lon)

    from shapely.prepared import prep
    minx, miny, maxx, maxy = core.bounds
    span = max(maxx - minx, maxy - miny)
    cell = max(8.0, span / 150.0)
    prepared = prep(core)
    below_cells = []
    deep_pts = []
    y = miny
    while y < maxy:
        x = minx
        while x < maxx:
            cx, cy = x + 0.5 * cell, y + 0.5 * cell
            if prepared.contains(Point(cx, cy)):
                alt = _dem_at(cx, cy)
                if alt is not None:
                    fl = _floor_at(cx, cy)
                    if alt < fl:
                        below_cells.append(Polygon([
                            (x, y), (x + cell, y),
                            (x + cell, y + cell), (x, y + cell)]))
                        if alt < fl - trigger:
                            deep_pts.append((Point(cx, cy), fl - alt))
            x += cell
        y += cell
    if not below_cells or not deep_pts:
        return 0

    # MORPHOLOGICAL smoothing at the rings' minimum-feature radius —
    # the staircase killer (``_smooth_region``'s opening + closing).
    r = _RING_MIN_FEATURE_RADIUS_M
    try:
        region = unary_union(below_cells)
        region = region.buffer(-r, quad_segs=4).buffer(r, quad_segs=4)
        region = region.buffer(r, quad_segs=4).buffer(-r, quad_segs=4)
        # DAYLIGHT RESTORE.  Detection marks a whole cell from its
        # CENTRE, so the true ``DEM == floor`` contour lies up to half a
        # cell OUTSIDE the marked union; the opening above then pulls the
        # boundary a further ~half-serration INWARD.  Left there the rim
        # sits below the contour — i.e. it ends in a wall of
        # (floor - DEM), measured 1.72 m median at SPJC 2026-07-24.
        # Grow the SMOOTHED region back out by one detection cell: a
        # dilation of a smooth region stays smooth (no staircase
        # returns), and the rim lands at or beyond the contour, where
        # DEM >= floor and the vertex value IS the DEM — daylight.  The
        # overshoot skirt is a no-op surface: patch value == terrain.
        region = region.buffer(cell, quad_segs=4)
        # EXACT clips (weld ruling): scope to the ring-2 core, then out
        # of every other shape.  No buffer on either side.
        region = region.intersection(core)
        for op in other_polys:
            if region.is_empty:
                break
            if op.intersects(region):
                region = region.difference(op)
    except _GEOM_EXC:
        return 0
    try:
        core_edge = core.boundary
    except _GEOM_EXC:
        core_edge = None
    # WELD NEIGHBOURS: the shapes the region was clipped against that
    # actually touch this core.  A rim vertex on one of their boundaries
    # shares a coordinate with it (the clip is exact), so it must share
    # the VALUE too — otherwise the shared node splits and the mesh
    # renders the difference as a wall.
    neighbours = []
    for s in other_shapes:
        try:
            if s.polygon.intersects(core):
                neighbours.append((s, s.polygon.bounds, s.polygon.boundary))
        except _GEOM_EXC:
            continue
    emitted = 0
    pit_area = 0.0
    worst = 0.0
    for part in _poly_parts(region):
        if part.is_empty or part.area < GAP_FILL_MIN_AREA_M2:
            continue
        _pp = prep(part)
        hits = [d for p, d in deep_pts if _pp.covers(p)]
        if not hits:
            continue                    # shallow residue — not a pit
        ring = _open_coords(part)
        if len(ring) < 3:
            continue
        alts = []
        for vx, vy in ring:
            fl = _floor_at(vx, vy)
            # (1) WELD to a neighbouring SHAPE whose boundary this rim
            # vertex shares — its value is the authority there.
            adopted = None
            _t = _PIT_RIM_WELD_TOL_M
            for s, (bx0, by0, bx1, by1), bnd in neighbours:
                if not (bx0 - _t <= vx <= bx1 + _t
                        and by0 - _t <= vy <= by1 + _t):
                    continue
                try:
                    if bnd.distance(Point(vx, vy)) > _t:
                        continue
                except _GEOM_EXC:
                    continue
                e = _edge_interp_alt(s, vx, vy)
                if e is not None:
                    adopted = float(e)
                    break
            if adopted is not None:
                alts.append(round(adopted, 2))
                continue
            on_ring2 = False
            if core_edge is not None:
                try:
                    on_ring2 = (core_edge.distance(Point(vx, vy))
                                <= _PIT_RIM_WELD_TOL_M)
                except _GEOM_EXC:
                    on_ring2 = False
            if on_ring2:
                # WELD TO THE COLLAR (2026-07-09 weld ruling).  Where the
                # pit reaches the ring-2 core boundary the neighbouring
                # surface is NOT raw DEM — it is the collar ring, a
                # constrained breakline carrying the law value at this
                # exact coordinate.  A rim pinned to the FLOOR here would
                # put two values (law and law - depth) on one node: the
                # deliberate node-split wall, over the whole shared
                # frontage.  The patch adopts the ring value verbatim
                # instead, and the surface falls from it to the floor
                # inside — "sloped from the rim down to the floor".
                v = fl + depth
            else:
                terrain = _dem_at(vx, vy)
                # RIM ON THE DAYLIGHT CONTOUR: where the boundary sits on
                # ground at or above the floor the patch takes the DEM
                # verbatim, so it meets natural ground with no step; where
                # the boundary cuts below the floor (a grid-quantised rim,
                # or a clip against a neighbouring shape) it takes the
                # local floor — the lawful fill level.
                v = fl if terrain is None else max(float(terrain), fl)
            alts.append(round(v, 2))
        layout.shapes.append(BuiltShape(
            polygon=part, role=ROLE_GRADED_STRIP,
            ref=_GAP_PIT_FLOOR_REF,
            node_altitudes=alts + [alts[0]]))
        emitted += 1
        pit_area += part.area
        worst = max(worst, max(hits))
    if emitted:
        _c = rec["pocket"].centroid
        UI.vprint(1,
            f"  [gap-floor] v2 collared pocket at ({_c.x:.0f},"
            f"{_c.y:.0f}): {emitted} pit patch(es) totalling "
            f"{pit_area:.0f} m2 inside the ring-2 core "
            f"({core.area:.0f} m2), worst DEM drop {worst:.1f} m below "
            f"the LOCAL ring-2 floor (ring-2 value - {depth:.1f}); rim "
            f"on the daylight contour.")
    return emitted


def emit_gap_interior_floor(layout, dem, tile_lat, tile_lon) -> int:
    """Clamp enclosed-pocket interiors to a drainage-depth floor (owner
    ruling 2026-07-19; gates ``GAP_FILL_INTERIOR_FLOOR_ENABLED`` and
    ``GAP_FILL_INTERIOR_FLOOR_DEPTH_M`` > 0).

    DISABLED BY DEFAULT — owner ruling 2026-07-24: past the grade-law
    zones a large infield blends back into the DEM, so nothing here may
    override terrain beyond ring 2.  That restores the round-8
    interior-rings design ("Terrain INSIDE ring 2 stays open-floor —
    large infields lawfully follow terrain"), which this pass had
    contradicted.  The collar rings still carry the per-zone drainage law
    off the pocket's own pavement ring, so the graded slope down from
    pavement is unaffected; only the core reverts to terrain.  See the
    gate's ``config.py`` comment for what re-enabling should look like
    (an enclosure test, not a plain flip).

    Runs AFTER ``emit_gap_fill_spines``: a treated gap is covered by its
    emitted ``graded_strip`` face and skips this pass by coverage; the
    pass targets the pockets the emitter lawfully SKIPPED (wider than
    ``GAP_FILL_MAX_WIDTH_M``, foreign shape inside, parent straddle),
    whose interiors ride raw DEM.

    TWO REGIMES:

    * COLLARED pockets (arc B2, gate ``POCKET_COLLAR_RINGS_ENABLED``) —
      the width-skipped pockets ``_emit_pocket_collar_rings`` has just
      given two closed collar rings.  These go to
      ``_pocket_pit_floor_v2``: scope = inside ring 2, reference = the
      LOCAL ring-2 station value, rim on the daylight contour, sloped
      per-vertex values, exact welds.  This is the owner's 2026-07-24
      sequence — rings first, THEN the pit in the middle.
    * every OTHER pocket — the 2026-07-19 pass, unchanged:

      * lip = median solved pavement value at the pocket's own ring
        vertices (the enclosing pavement edge);
      * floor = lip − ``GAP_FILL_INTERIOR_FLOOR_DEPTH_M``;
      * grid-sample the DEM inside the pocket; union the violating cells
        (DEM < floor) into pit regions, clear of every existing shape;
      * emit each pit region as a FLAT ``graded_strip`` patch at the floor
        value (ref ``gap_pit_floor``).

      With ``POCKET_COLLAR_RINGS_ENABLED`` OFF nothing is collared and
      this is the only regime — byte-identical to 2026-07-19.

    No-op economy: a pocket whose terrain never drops below the floor
    emits nothing — large infields keep following terrain, down to
    drainage depth.  Mutates ``layout.shapes``; returns the number of
    pit patches emitted.
    """
    if not GAP_FILL_INTERIOR_FLOOR_ENABLED:
        return 0            # owner ruling 2026-07-24 — see the docstring
    depth = GAP_FILL_INTERIOR_FLOOR_DEPTH_M
    if depth <= 0.0 or dem is None:
        return 0
    airside = _airside_shapes(layout)
    if len(airside) < 2:
        return 0
    gap_candidates, rim_ids = _gap_candidate_polys(layout, airside)
    if not gap_candidates:
        return 0

    # Solved pavement value at every airside ring vertex (mm key).
    registry: dict[tuple[int, int], float] = {}
    for s in airside:
        na = s.node_altitudes
        try:
            coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        for i, (vx, vy) in enumerate(coords):
            if na and i < len(na) and na[i] is not None:
                registry.setdefault(_key(vx, vy), float(na[i]))
            elif not na and s.altitude is not None:
                registry.setdefault(_key(vx, vy), float(s.altitude))

    # Every OTHER shape (emitted gap faces, bands, groundside, parents,
    # …): coverage test + keep-clear region for the pit patches.
    airside_ids = {id(s) for s in airside}
    other_polys = [s.polygon for s in layout.shapes
                   if id(s) not in airside_ids
                   and s.polygon is not None and not s.polygon.is_empty
                   and s.polygon.geom_type in ("Polygon", "MultiPolygon")]

    from .elevation import _sample_dem

    def _dem_at(px: float, py: float):
        lat, lon = layout.m_to_ll(px, py)
        return _sample_dem(dem, tile_lat, tile_lon, lat, lon)

    emitted = 0
    # ── ARC B2: COLLARED pockets take pit floor v2 ────────────────────
    # ``_emit_pocket_collar_rings`` published one record per width-skipped
    # pocket it collared.  Those pockets are handled by the v2 pass and
    # are then EXCLUDED from the legacy loop below (their ground is owned
    # by the collar outside ring 2 and by the v2 patch inside it).  The
    # store is absent gate-OFF, so both statements are no-ops there and
    # the legacy loop runs exactly as it did.
    collars = (list(getattr(layout, _POCKET_COLLAR_STORE, None) or [])
               if POCKET_COLLAR_RINGS_ENABLED else [])
    if collars:
        _other_shapes = [s for s in layout.shapes
                         if id(s) not in airside_ids
                         and s.polygon is not None
                         and not s.polygon.is_empty
                         and s.polygon.geom_type == "Polygon"]
    for _rec in collars:
        emitted += _pocket_pit_floor_v2(layout, _rec, dem, tile_lat,
                                        tile_lon, other_polys,
                                        _other_shapes)

    for gap_poly in gap_candidates:
            if gap_poly.area < GAP_FILL_MIN_AREA_M2:
                continue
            if _pocket_is_collared(gap_poly, collars):
                continue
            # Treated gaps are covered by their emitted faces — skip any
            # pocket mostly covered by existing non-airside shapes.
            try:
                covered = sum(
                    gap_poly.intersection(op).area
                    for op in other_polys
                    if op.intersects(gap_poly))
            except _GEOM_EXC:
                covered = 0.0
            if covered >= 0.4 * gap_poly.area:
                continue
            # Pavement lip at THIS pocket's ring.
            lip_values = [registry[k] for k in
                          (_key(vx, vy)
                           for vx, vy in gap_poly.exterior.coords)
                          if k in registry]
            if len(lip_values) < 3:
                _c = gap_poly.centroid
                UI.vprint(1, f"  [gap-floor] pocket at ({_c.x:.0f},"
                             f"{_c.y:.0f}) has no pavement values on "
                             f"its ring — skipped.")
                continue
            lip_values.sort()
            lip = lip_values[len(lip_values) // 2]
            floor = lip - depth
            # Grid-sample the interior for violations.
            minx, miny, maxx, maxy = gap_poly.bounds
            span = max(maxx - minx, maxy - miny)
            cell = max(8.0, span / 150.0)
            violating_cells = []
            y = miny
            while y < maxy:
                x = minx
                while x < maxx:
                    cx, cy = x + 0.5 * cell, y + 0.5 * cell
                    if gap_poly.contains(Point(cx, cy)):
                        alt = _dem_at(cx, cy)
                        if alt is not None and alt < floor:
                            violating_cells.append(Polygon([
                                (x, y), (x + cell, y),
                                (x + cell, y + cell), (x, y + cell)]))
                    x += cell
                y += cell
            if not violating_cells:
                continue
            try:
                pit_region = unary_union(violating_cells).simplify(
                    1.0, preserve_topology=True)
                pit_region = pit_region.intersection(
                    gap_poly.buffer(-0.5))
                for op in other_polys:
                    if op.intersects(pit_region):
                        pit_region = pit_region.difference(
                            op.buffer(0.25))
            except _GEOM_EXC:
                continue
            parts = ([pit_region] if pit_region.geom_type == "Polygon"
                     else [g for g in getattr(pit_region, "geoms", [])
                           if g.geom_type == "Polygon"])
            n_pocket = 0
            pocket_area = 0.0
            for part in parts:
                if part.is_empty or part.area < 25.0:
                    continue
                ring = _open_coords(part)
                if len(ring) < 3:
                    continue
                alts = [round(floor, 2)] * len(ring)
                layout.shapes.append(BuiltShape(
                    polygon=part, role=ROLE_GRADED_STRIP,
                    ref=_GAP_PIT_FLOOR_REF,
                    node_altitudes=alts + [alts[0]]))
                n_pocket += 1
                pocket_area += part.area
            if n_pocket:
                emitted += n_pocket
                _c = gap_poly.centroid
                UI.vprint(1,
                    f"  [gap-floor] pocket at ({_c.x:.0f},{_c.y:.0f}) "
                    f"area={gap_poly.area:.0f} m2: {n_pocket} pit "
                    f"patch(es) totalling {pocket_area:.0f} m2 clamped "
                    f"to floor {floor:.1f} m (lip {lip:.1f} - "
                    f"{depth:.1f}).")
    return emitted


def _emit_one_gap(layout, airside, gap_poly, long_dir, long_len, step,
                  registry, dem=None, tile_lat=None, tile_lon=None,
                  rw_axes=None) -> int:
    """Build the drainage spine, solve its values, split the gap into
    half-gap faces and emit them.  Returns the face count."""
    spine = _build_spine(gap_poly, long_dir, long_len, step)
    if spine is None:
        UI.vprint(1, "  [gap-fill] no spine for enclosed gap "
                     f"(area={gap_poly.area:.0f} m2) — skipped.")
        return 0

    # STAGE B2 (one-solve absorption): gate-ON the spine values come
    # from the solve writeback (``layout.gap_fill_presolve``); the
    # analytic valuation below then serves ONLY the solved-vs-analytic
    # movement report.  Gate-OFF there is no store, ``solved`` is None
    # and the analytic path is byte-identical to before.
    solved = _solved_spine_values(layout, spine)

    # Per-vertex drainage interval + target.
    intervals: list[tuple] = []
    targets: list[float] = []
    ok = True
    for px, py in spine:
        lo, hi, edge_alts = _spine_interval(layout, airside, px, py)
        target = _drain_target(lo, hi, edge_alts)
        if target is None:
            ok = False
            break
        intervals.append((lo, hi))
        targets.append(target)
    if not ok and solved is None:
        UI.vprint(1, "  [gap-fill] no pavement value at spine — skipped.")
        return 0

    # Open-way spine (2026-07-09 round 2): the ends float >= 2 m
    # inside the gap, so they take their own corridor target like
    # every station — the surface between spine end and boundary
    # lerps in the mesh; the pavement value lives on the ring itself.
    if solved is not None:
        values = [round(v, 1) for v in solved]
        if ok:
            # Movement report (ratified 2026-07-10): how far the solve
            # writeback sits from the retired analytic target.
            analytic = _smooth_spine(targets, intervals, _SMOOTH_SWEEPS)
            store = getattr(layout, "_gap_spine_value_deltas", None)
            if store is None:
                store = layout._gap_spine_value_deltas = []
            store.extend(abs(v - a) for v, a in zip(solved, analytic))
    else:
        if getattr(layout, "gap_fill_presolve", None) is not None:
            UI.vprint(1, "  [gap-fill] WARN: stage B2 gate is ON but no "
                         "pre-solve spine matches this emitted gap — "
                         "analytic valuation fallback.")
        values = _smooth_spine(targets, intervals, _SMOOTH_SWEEPS)
        values = [round(v, 1) for v in values]

    # ── GAP INTERIOR RINGS (ratified 2026-07-11, round-8 revision:
    # complete closed loops, value-gated) — band-breakpoint breaklines
    # inside the face; the spine values may only move DOWN (ring-2
    # ceiling re-coupling).  Failure degrades loudly to the ring-less
    # face (never blocks the gap emission). ────────────────────────────
    _spine_chains = None
    if GAP_FILL_INTERIOR_RINGS_ENABLED and dem is not None:
        ring_stats = None
        try:
            (ring_chains, values, ring_stats,
             _spine_chains) = _build_gap_interior_rings(
                layout, airside, gap_poly, spine, values, dem,
                tile_lat, tile_lon, rw_axes, step)
        except _GEOM_EXC as _ring_exc:
            ring_chains = []
            _spine_chains = None
            UI.vprint(1, f"  [gap-fill] interior-ring construction "
                         f"FAILED (face kept ring-less): {_ring_exc!r}")
        _c = gap_poly.centroid
        if ring_chains:
            if getattr(layout, "gap_interior_rings", None) is None:
                layout.gap_interior_rings = []
            for _rc_pts, _rc_alts in ring_chains:
                layout.gap_interior_rings.append(
                    ([layout.m_to_ll(_rx, _ry) for _rx, _ry in _rc_pts],
                     list(_rc_alts)))
            UI.vprint(1, f"  [gap-fill] interior rings: "
                         f"{ring_stats['chains']} loop(s)/chain(s), "
                         f"{ring_stats['nodes']} node(s), "
                         f"{ring_stats['engaged_stations']} engaged / "
                         f"{ring_stats['noop_stations']} terrain-riding "
                         f"of {ring_stats['stations']} station(s) "
                         f"(centroid=({_c.x:.0f},{_c.y:.0f})).")
        elif ring_stats is not None and ring_stats.get("skipped"):
            UI.vprint(1, f"  [gap-fill] interior rings SKIPPED (economy "
                         f"gate: every station of both rings is a value "
                         f"no-op — terrain lawful throughout; "
                         f"{ring_stats['stations']} station(s), "
                         f"centroid=({_c.x:.0f},{_c.y:.0f})).")

    # ── F3 LAW 3: the spine descends lawfully and NEVER below terrain.
    # LAST word on the spine profile, so no earlier author (the analytic
    # corridor target, the solve writeback, the ring-2 ceiling
    # re-coupling above) can leave a station under its own ground.  The
    # ring-2 min() re-coupling is SUBSUMED here: the profile leaves the
    # conformed boundary at the band's own maximum down slope, so it is
    # already at or below the ring value it starts from. ──────────────
    _conform_shp, _conform_idx = _conform_index(layout, airside)
    values, _spine_terrain = _spine_lawful_profile(
        layout, _conform_idx, spine, values, dem, tile_lat, tile_lon,
        intervals=intervals if ok else None)

    # OPEN-WAY EMISSION (user design 2026-07-09, round 2): ONE face —
    # the gap polygon itself, ring verbatim — plus the spine as an
    # interior open constrained way (layout.gap_spines → the
    # crown-spine mechanism, o4_feature=gap_drainage_spine).  No
    # split, no landing geometry, no keyhole rails.
    _air_ext = []
    for _s in airside:
        try:
            _air_ext.append(_s.polygon.exterior)
        except _GEOM_EXC:
            continue
    ring = _open_coords(gap_poly)
    if len(ring) < 3:
        return 0
    # SEAM-CHORD stations (seam-heal path): a clipped gap's edge along a
    # tile cut-back line carries densified lattice stations that are NOT
    # pavement chain vertices — they take DEM verbatim, the
    # ``_SEAM_DEM_TERRAIN_ROLES`` contract, so the two tiles' independent
    # halves agree at the seam by sampling the same raster.
    _seam_cb = []
    if GAP_FILL_SEAM_HEAL_ENABLED and dem is not None:
        _offc = [p for p in (getattr(layout, "tile_seam_offcuts", None)
                             or ()) if p is not None and not p.is_empty]
        if _offc:
            _seam_cb = [
                (ax, coord + keep * TILE_CUT_HALF_WIDTH_M)
                for ax, coord, keep in _tile_clip_specs(
                    layout, airside, _offc)]
    if _seam_cb:
        from .elevation import _sample_dem as _seam_sample_dem
    new_ring: list[tuple[float, float]] = []
    alts = []
    for vx, vy in ring:
        k = _key(vx, vy)
        if k in registry:
            new_ring.append((vx, vy))
            alts.append(registry[k])        # boundary vertex, verbatim
            continue
        if _seam_cb and any(
                abs((vx if _ax == 0 else vy) - _cb) <= _SEAM_CHORD_TOL_M
                for _ax, _cb in _seam_cb):
            _lat, _lon = layout.m_to_ll(vx, vy)
            _e = _seam_sample_dem(dem, tile_lat, tile_lon, _lat, _lon)
            if _e is not None:
                new_ring.append((vx, vy))
                alts.append(float(_e))      # seam station, DEM verbatim
                continue
        # UNION-DIVERGENCE point — where two pavement rings disagree
        # by millimetres the union outline follows neither, and an
        # un-snapped gap vertex mints a near-parallel lens (measured
        # 96 mm at CYXY hole 22).  Snap onto the nearest airside
        # exterior within 0.15 m and adopt the pavement edge value.
        pt = Point(vx, vy)
        best_d, best_pt = None, None
        for ext in _air_ext:
            try:
                d = ext.distance(pt)
            except _GEOM_EXC:
                continue
            if d <= 0.15 and (best_d is None or d < best_d):
                best_d = d
                best_pt = ext.interpolate(ext.project(pt))
        if best_pt is not None:
            e = _nearest_pav_alt(airside, best_pt.x, best_pt.y,
                                 max_distance_m=5.0)
            if e is not None:
                new_ring.append((best_pt.x, best_pt.y))
                alts.append(float(e))
                continue
        e = _nearest_pav_alt(airside, vx, vy, max_distance_m=5.0)
        if e is None:
            # F3 LAW 1 on the FACE BOUNDARY.  A pocket boundary vertex
            # that is not an airside chain vertex still STANDS ON an
            # enclosing graded pavement edge whenever the R19-2
            # subdividers are what bound this residual pocket — and the
            # old fallback handed it ``values[0]``, the spine's own
            # first value.  That is the CYXY cliff at the face level:
            # the boundary of the gap took the trench's elevation while
            # the road it touches shipped 4 m higher.  Conform to the
            # edge it actually adjoins.
            e, _cd = _conform_edge_value(_conform_idx, vx, vy)
        new_ring.append((vx, vy))
        alts.append(float(e) if e is not None else values[0])
    # PARENT-HOLE PRESERVATION (test_no_self_overlap fix).  When a gap
    # parent (runway-end skirt / building pad) sits WHOLLY inside the
    # gap, ``_parent_residual_faces`` already carved it out — the
    # ``gap_poly`` handed here is an ANNULUS whose interior ring is the
    # parent footprint (residual = gap − parent_union).  ``_open_coords``
    # keeps only the EXTERIOR ring, though, so without re-adding the
    # holes the emitted face refills the parent footprint and BURIES it
    # (CYXY: a graded_strip covered runway_end_skirt #242 by 1,925 m²).
    # Re-attach the residual's interior rings so the emitted polygon is
    # clipped against its bounding parents exactly as the residual was.
    # The exterior ``new_ring`` (and its ``alts``) is untouched, so the
    # per-vertex ``node_altitudes`` contract (exterior-ring aligned, the
    # only ring ``to_osm`` reads) still holds.  A parent that only
    # partially straddles the gap leaves no interior ring here — its bite
    # already lives in the exterior — so nothing changes for that case.
    parent_holes = [list(r.coords) for r in gap_poly.interiors]
    try:
        face_poly = Polygon(new_ring, parent_holes)
        if not face_poly.is_valid or face_poly.is_empty:
            face_poly = gap_poly
            new_ring = list(_open_coords(gap_poly))
    except _GEOM_EXC:
        face_poly = gap_poly
    if face_poly.area < GAP_FILL_MIN_AREA_M2:
        # The residual passed the min-area gate, but carving the parent
        # hole(s) can drop a thin annulus below it — a sliver graded_strip
        # is not worth an emitted shape.  Skip (no spine ways emit either).
        _c = gap_poly.centroid
        UI.vprint(1, f"  [gap-fill] parent-clipped face below min area "
                     f"({face_poly.area:.0f} < {GAP_FILL_MIN_AREA_M2:.0f} "
                     f"m2) centroid=({_c.x:.0f},{_c.y:.0f}) — skipped.")
        return 0
    layout.shapes.append(BuiltShape(
        polygon=face_poly, role=ROLE_GRADED_STRIP, ref=_GAP_FILL_REF,
        node_altitudes=alts + [alts[0]]))
    # Spine ways to emit: the full spine as today, or — when interior
    # rings emitted (round-8) — the ring-core TRIMMED sub-chains from
    # the builder (a full-length spine would cross the closed loops at
    # the gap ends).  Gate-OFF ``_spine_chains`` is None and the path
    # below is byte-identical to before.
    base_chains: list[list[int]] = (
        _spine_chains if _spine_chains is not None
        else [list(range(len(spine)))])
    if list(gap_poly.interiors):
        # ANNULAR face (gap parent wholly inside): a straight segment
        # between two spine stations can cross the parent hole — that
        # open constrained way would transversally cross the parent's
        # ring (a fresh lens mint).  Split each spine sub-chain at any
        # connecting segment not COVERED by the face; each surviving
        # sub-chain (>= 2 points) emits as its own open way.  Faces
        # without interiors keep the single-way path byte-identical.
        chains: list[list[int]] = []
        for bc in base_chains:
            if not bc:
                continue
            chains.append([bc[0]])
            for a, b in zip(bc, bc[1:]):
                seg = LineString([spine[a], spine[b]])
                covered = False
                try:
                    covered = gap_poly.covers(seg)
                except _GEOM_EXC:
                    covered = False
                if covered:
                    chains[-1].append(b)
                else:
                    chains.append([b])
        emitted_ways = 0
        for chain in chains:
            if len(chain) < 2:
                continue
            pts_ll = [layout.m_to_ll(*spine[j]) for j in chain]
            _append_gap_spine(layout, pts_ll,
                              [values[j] for j in chain],
                              None if _spine_terrain is None
                              else [_spine_terrain[j] for j in chain])
            emitted_ways += 1
        if emitted_ways == 0:
            # No drainage way survived the parent hole — the face is
            # already appended and keeps its boundary values; log it.
            UI.vprint(1, "  [gap-fill] annular face emitted without a "
                         "drainage spine (every spine segment crossed "
                         "the parent ring).")
        elif emitted_ways > 1:
            UI.vprint(1, f"  [gap-fill] annular face spine split into "
                         f"{emitted_ways} open ways around the parent "
                         f"ring.")
    else:
        for chain in base_chains:
            if len(chain) < 2:
                continue
            pts_ll = [layout.m_to_ll(*spine[j]) for j in chain]
            _append_gap_spine(layout, pts_ll,
                              [values[j] for j in chain],
                              None if _spine_terrain is None
                              else [_spine_terrain[j] for j in chain])
    return 1
