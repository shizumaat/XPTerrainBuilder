"""APRON TERRACE LAW — level panels, joints that never cross a spine.

Owner ruling 2026-08-04 (``docs/RULINGS.md``, "Apron terrace law"); spec
``docs/specs/apron-terrace-law-spec.md``:

    "long aprons on genuinely steep ground MAY terrace into level panels
     with declared joint steps — but it has to be done in a way that does
     not interrupt any spine where aircraft have to travel."

BINDING CONSTRAINT, and it is STRUCTURAL here rather than checked-after:
a terrace joint is born as ``(terrace line ∩ apron) − corridor cover``.
The corridor cover is every taxi/route centerline crossing the apron,
buffered by its corridor half-width PLUS
``APRON_TERRACE_JOINT_CLEARANCE_M``.  A joint that would cross a route is
therefore never minted — there is no later pass that shortens it, and no
ordering in which a joint and a route can coexist on the same ground.
``tools/check_grade`` carries the validator twin (joint ∩ ``routes_exact``
⇒ ERROR) as the lockstep instrument, not as the enforcement.

THE MECHANISM THIS LEGALISES (``carrier_attrib/DOSSIER.md`` §4/§6/§7/§8).
Real ground steeper than the apron cap over long runs: HEAZ (0,163) is a
378.1 m within-apron edge under a DEM rising 1.47 %; HECA (1021,17424) is
2.45 % over 521 m; (768,3063) is 1.70 % over 1 469 m.  One continuous
1 %-capped surface across those spans is infeasible BY TOPOLOGY, not by
any wrong anchor value — the residue a terrace law legalises rather than
removes (``feasibility-is-guaranteed``: a lawful surface exists, and this
is the law under which it exists).

WHAT THIS MODULE DOES, in the order the solve calls it:

1. ``plan_apron_terraces`` — the TRIGGER + the PANELIZATION.  For every
   apron constraint component: the two-sided envelope ``L − U`` on its own
   cap graph with its hard anchors pinned (the same adjudication
   ``one_solve._stall_envelope_gap`` runs, on one component instead of the
   whole system), the steep-truth signature (the binding witness pair's
   DEM chord grade exceeds the cap that pair is held to), and the excess
   floor.  Components that pass get terrace lines perpendicular to the
   apron's own DEM gradient, cut out of the corridor cover.
2. ``apply_terrace_budgets`` — the SOLVER BINDING.  Panels are constraint
   GROUPS inside the ONE solve (no second solve, ``single-solve
   architecture``).  A within-apron law edge whose chord crosses ``k``
   declared joints gets ``cap·d + Σ step`` instead of ``cap·d``; every
   other edge — every edge inside a panel, and every edge on or through a
   corridor — keeps the full apron law untouched.  Panels fall out as the
   connected components of the joint-free edge subgraph.
3. ``emit_terrace_joint_faces`` — the JOINT GEOMETRY.  One
   ``retaining_wall`` face per settled joint, placed in the
   ``STACKED_WALL_RETREAT_M`` band on the lower side — the same machine
   and constants as ``adjacent_ground.emit_stacked_conflict_walls``.
   NOTE (approved deviation, spec adjudication 768cded): the apron
   polygon itself is NOT cut back, so the face laps that band of apron
   surface; the polygon split is queued for the default-ON round.
   Minted BEFORE interning so no emit-time consensus can average a
   joint away.
4. ``terrace_joints_sidecar`` — the validator's half of the lockstep.

Frame: the layout's local metre frame throughout (the solver's frame);
only the sidecar converts to lat/lon.

STANDING LAW (owner 2026-08-05, BUILD-COMPLETE-THEN-DEBUG): there is no
``O4_APRON_TERRACE_LAW`` gate any more and no "terrace off" arm.

D2 — THE FACE'S ACTUAL STEP IS READABLE AND BOUNDED BY ITS DECLARATION.
The v2 round left one residue: 12 HECA faces emitted over
``APRON_TERRACE_MAX_STEP_M`` (worst 6.0 m) while declaring ≤1.994 m.
Mechanism (attributed, not guessed): ONE level per side was read for the
WHOLE joint, from a flank window whose nearest rows can sit 100 m+ away,
so a single extrapolation spoke for a joint hundreds of metres long.

The fix here is PLAN-TIME PANEL-BOUNDARY DENSIFICATION.  At plan time the
joint's boundary is densified into STATIONS (``_joint_stations``,
``_JOINT_STATION_SPACING_M``); each station carries the NEAREST apron
node on each side and that node's perpendicular offset.  The face is then
minted PER STATION from that station's own two nearest settled nodes, and
each station's height is held to the law's OWN allowance for its reader
distance, ``step + cap·(d_pos + d_neg)`` — the declaration, plus exactly
the relief the cap licenses over the distance the reader had to cross.
The same station table is the population ``_bind_joint_step_pairs`` binds
into the solve, so the emitter and the solver speak about identical
ground (one computation, two consumers).

WHAT THIS DOES NOT DO, and why (lead direction 2026-08-05).  An INTERIOR
joint has no emitted geometry at it, so a station's reader distance is
whatever the apron ring offers.  Manufacturing that geometry — splitting
the apron at the joint — is out: the emit-time §3(d) split was measured
to MINT defects (its new ring vertices adopted the FACE's level, a value
the solve never produced) and is removed.  The structural close is a
PRE-SOLVE panel boundary, born before the solver builds its node list so
its vertices are solve VARIABLES; that is named as the follow-up, and its
precondition is that the boundary exist pre-solve rather than at emit.
Until then the residue is DECLARED (each station's bound is in the
sidecar) rather than silent.
"""
from __future__ import annotations

import math
import os as _os
from typing import Optional

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry import Point as _Point
from shapely.ops import unary_union

from auto_patch.config import (
    APRON_MAX_GRADE,
    APRON_TERRACE_CORRIDOR_HALF_WIDTH_M,
    APRON_TERRACE_FACING_PROXIMITY_M,
    APRON_TERRACE_FACING_STEP_M,
    APRON_TERRACE_JOINT_CLEARANCE_M,
    APRON_TERRACE_LAW_ENABLED,
    APRON_TERRACE_MAX_STEP_M,
    APRON_TERRACE_MIN_EXCESS_M,
    APRON_TERRACE_MIN_JOINT_LEN_M,
)

_GEOM_EXC = (ValueError, GEOSException, TopologicalError, AttributeError)

__all__ = [
    "apron_terrace_law_enabled",
    "construct_apron_terrace_presolve",
    "plan_apron_terraces",
    "terrace_station_edges",
    "apply_terrace_budgets",
    "emit_terrace_joint_faces",
    "terrace_joints_sidecar",
    "terrace_certificates_sidecar",
    "runway_strip_keepout_geometry",
    "TerraceJoint",
    "TerracePlan",
]

# Role literal — the apron is the only class the ruling names.  (Kept as a
# literal for the blast index, exactly like the rest of the solver.)
ROLE_APRON = "apron"
ROLE_RETAINING_WALL = "retaining_wall"

# The joint FACE retreats this far perpendicular to the joint (the
# stacked-wall machine's own constant, re-read here so the two never
# drift), so the joint LINE is trimmed by it at both ends: the emitted
# geometry, not merely the centreline, keeps the pinned spine clearance.
_RETREAT_TRIM_M = 0.6
# Joint-flank sampling (the emitter's level reader): a ring vertex counts
# as flanking a joint when its station along the joint is inside the
# joint's own span (± this pad) and its offset is within this radius.
_JOINT_FLANK_PAD_M = 25.0
_JOINT_FLANK_MAX_M = 150.0
# A ring vertex this close to the joint line sits ON the joint and belongs
# to neither panel — reading it as one panel's level is how a 0 m step
# gets minted where a real one exists.
_JOINT_ON_LINE_EPS_M = 0.05
# The level a FACE is emitted at is the settled surface AT THE JOINT, not
# the mean of a flank window (flip-readiness v2 §3(b), defect D2).  Each
# side's samples are fit as ``z ≈ a + b·s`` in the joint-normal offset
# ``s`` and evaluated at ``s = 0``.  Measured cost of the mean: HECA
# emitted 10 faces of 2.14-5.52 m while declaring ≤1.994 m — the
# difference was lawful cap-graded relief up to 150 m away, folded into
# a vertical face by a zeroth-order read.  A first-order fit evaluated
# at the joint is the same data read faithfully; it invents nothing and
# grades nothing (EMITTERS EMIT, NEVER GRADE).
_JOINT_FIT_MIN_SAMPLES = 3
_JOINT_FIT_MIN_SPREAD_M = 1.0
# §3(c): how close a neighbour must come before its boundary counts as
# WELDED to this apron rather than FACING it across a gap.  A welded
# neighbour is one laterally contiguous surface (the contiguity family's
# ground, not the terrace law's) and has no cross-shape step to conform
# to; a gapped one does.  Sized just above the emitter's canonical
# proximity tolerance so a shared vertex can never read as a gap.
_FACING_WELD_TOL_M = 0.55


# (The ``O4_TERRACE_V2_NO_*`` attribution switches are DELETED — owner
# 2026-08-05, no gates: prototype-era instrumentation, and every clause
# they held out is now standing law.)


# ── D2: PLAN-TIME PANEL-BOUNDARY DENSIFICATION ──────────────────────
# A joint's boundary is densified into STATIONS this far apart.  The grid
# is a PURE FUNCTION of the joint's own length, so the plan-time binding
# and the emit-time face agree on the stations without carrying node ids
# across the solve (single-pass: one computation, two consumers).
# 25 m is the apron ring's own coarse spacing — finer buys nothing
# because the station has to find a settled row on each side.
_JOINT_STATION_SPACING_M = 25.0


def _station_grid(length: float) -> list:
    """Station arc-lengths along a joint of ``length`` metres."""
    if not (length > 0.0):
        return [0.0]
    n = max(1, int(math.ceil(length / _JOINT_STATION_SPACING_M)))
    return [length * (k + 0.5) / n for k in range(n)]








def _mean(values):
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


class _XY:
    """``.get(index)`` over the solver's ``nodes`` list of ``(x, y)``.

    The solve carries positions as a LIST; a plain dict copy of 132 k
    HECA nodes would be a second population of the same data (and the
    single-pass principle says do not build one)."""

    __slots__ = ("_seq",)

    def __init__(self, seq):
        self._seq = seq

    def get(self, index, default=None):
        if 0 <= index < len(self._seq):
            p = self._seq[index]
            if p is not None:
                return (float(p[0]), float(p[1]))
        return default

    def __getitem__(self, index):
        p = self.get(index)
        if p is None:
            raise KeyError(index)
        return p

    def __contains__(self, index):
        return self.get(index) is not None


def _as_xy(node_xy):
    """Accept either a mapping or the solver's node list."""
    if hasattr(node_xy, "get") and not isinstance(node_xy, list):
        return node_xy
    return _XY(node_xy)


def apron_terrace_law_enabled() -> bool:
    """STANDING LAW — always True (owner 2026-08-05, no gates).

    Retained ONLY as the call-site handle the solve still branches on
    (``solve.py``, KILL-lane territory: the ``if`` there is now
    unconditional-in-effect and is listed as a handoff deletion).  There
    is no env override and no "off" arm."""
    return True


class TerraceJoint:
    """One declared terrace joint: a polyline inside ONE apron, provably
    disjoint from every taxi corridor, carrying a declared step height.

    ``line`` is an open list of ``(x, y)`` in the layout's metre frame.
    ``step_m`` is the level change the law permits ACROSS this joint, on
    top of the ordinary cap allowance for the chord's own length.
    """

    __slots__ = ("line", "step_m", "shape_id", "geom", "panel_lo",
                 "panel_hi", "faced", "actual_step_m",
                 "flank_span_m", "line_ordinal", "stations",
                 "low_sign", "grid", "hi", "lo")

    def __init__(self, line, step_m: float, shape_id: int,
                 line_ordinal: int = 0):
        self.line = [(float(x), float(y)) for (x, y) in line]
        self.step_m = float(step_m)
        self.shape_id = int(shape_id)
        self.geom = LineString(self.line)
        # Filled by ``apply_terrace_budgets`` once the panels are known.
        self.panel_lo: Optional[float] = None
        self.panel_hi: Optional[float] = None
        # ── §3(a) faced-or-no-relief ───────────────────────────────
        # ``faced`` is set by the emitter; the sidecar demotes an unfaced
        # joint's allowance to the level the surface actually expresses.
        self.faced: bool = False
        self.actual_step_m: Optional[float] = None
        self.flank_span_m: Optional[float] = None
        # Which terrace LINE of its apron this piece came from (§2(b)'s
        # evidence bound is per line: collinear pieces of one line are
        # one step, not several).
        self.line_ordinal = int(line_ordinal)
        # ── D2: PLAN-TIME PANEL-BOUNDARY DENSIFICATION ──────────────
        # The joint's own boundary, densified into STATIONS at plan time
        # (positions only, so it is one computation shared by the solver
        # binding and the face emitter).  Each entry is
        # ``(s, i, d_i, j, d_j)``: the station's arc-length along the
        # joint, the nearest apron node on the positive side and its
        # perpendicular offset, and the same for the negative side.
        # The face is then read and BOUNDED per station, in the law's
        # own frame — ``step + cap·(d_i + d_j)`` — instead of one
        # whole-joint extrapolation over the flank window.
        self.stations: list = []
        # ── THE PRE-SOLVE PANEL BOUNDARY (completion round) ──────────
        # ``grid``/``hi``/``lo`` are the joint's own boundary geometry,
        # minted BEFORE the solve by
        # :func:`construct_apron_terrace_presolve`: ``hi`` is the row ON
        # the joint line (the upper panel's edge), ``lo`` the same
        # stations retreated ``STACKED_WALL_RETREAT_M`` to the low side
        # (the lower panel's edge).  Both rows are apron RING vertices,
        # therefore solve variables — which is what lets the face be
        # read by IDENTITY and the declared step be BOUND rather than
        # merely reported.
        self.low_sign: float = 1.0
        self.grid: list = []
        self.hi: list = []
        self.lo: list = []

    def length(self) -> float:
        return float(self.geom.length)


class TerracePlan:
    """The whole airport's terrace plan + the round's census."""

    def __init__(self):
        self.joints: list[TerraceJoint] = []
        # shape id -> list of TerraceJoint
        self.by_shape: dict[int, list[TerraceJoint]] = {}
        # Per-apron trigger census (spec band 6): one row per candidate.
        self.trigger_rows: list[dict] = []
        # Panel assignment from the last ``apply_terrace_budgets`` call:
        # node index -> panel id (per shape id).
        self.panels: dict[int, dict[int, int]] = {}
        # The panelized apron's node membership IN THE CURRENT PASS's
        # index space (rebuilt every pass; never carried across one).
        self.node_sets: dict[int, set] = {}
        # ── §2 THE CERTIFICATE ─────────────────────────────────────
        # shape id -> the recorded evidence chain that authorised this
        # apron to panelize.  Written into the sidecar so the twin can
        # audit "certificate-free panelization = 0" from the patch alone.
        self.certificates: dict[int, dict] = {}
        # The NO-CROSS set this plan was cut against.  Kept so §3(d)'s
        # split can test its own extension against the SAME geometry the
        # joints were cut out of — one computation, two consumers (a
        # second ``corridor_cover`` call at emit time would be a second
        # instrument over the same ground).
        self.cover = None
        # ── §3(c) FACING BOUNDARY RUNS ─────────────────────────────
        # shape id -> node indices on a stretch of the panelized apron's
        # exterior ring that FACES another pavement shape.  Held to full
        # apron law (never terrace-relaxed) and conformed to the
        # neighbour by generation-side step constraints.
        self.facing_nodes: dict[int, set] = {}
        self.stats: dict = {
            "candidates": 0, "triggered": 0, "joints": 0,
            "joint_pieces_dropped_short": 0,
            "joint_lines_lost_to_corridor": 0,
            "apron_area_total": 0.0, "apron_area_panelized": 0.0,
            "faces_emitted": 0,
            # §3(a): joints that could not face on EITHER side at plan
            # time.  Never minted — no budget, no sidecar row.
            "joints_stillborn_keepout": 0,
            # §3(a) LOUD COUNTER: a face dropped at EMIT time for keepout
            # reasons.  MUST READ 0 — its firing means the plan-time
            # predicate and the emit predicate diverged (a frame bug).
            "faces_dropped_keepout": 0,
            # §3(a): faces not emitted because the two flanks settled
            # level (Δ ≤ 0.05 m).  Their sidecar allowance is DEMOTED to
            # the actual settled step; counted and quoted, never silent.
            "joints_demoted_level": 0,
            # §3(b): joint-step pair constraints handed to the solve.
            "joint_step_pairs": 0,
            # §3(c): edges left at full apron law because an endpoint
            # sits on a facing boundary run.
            "facing_edges_excluded": 0,
            "facing_conformance_pairs": 0,
            # THE PRE-SOLVE SPLIT.  Mirrored onto the plan from
            # ``layout.apron_terrace_presolve_stats`` so the census keeps
            # one schema; the split itself happens before the solve.
            # ``laps_kept_no_split`` is STRUCTURALLY 0 now — a band that
            # cannot separate its apron mints no joint at all
            # (``joints_stillborn_hole``), so there is no lap to keep.
            "polygons_split": 0,
            "split_pieces_added": 0,
            "laps_kept_no_split": 0,
            "joints_stillborn_hole": 0,
            # ── D2: THE DENSIFIED PANEL BOUNDARY ────────────────────
            # ``station_readings`` is how many (level, level) pairs the
            # faces were actually read from — one per station with a
            # settled row on both sides, instead of one per JOINT.
            # ``stations_over_bound`` is the honest residue: stations
            # whose read exceeds ``step + cap·retreat``.  Nothing is
            # clamped to make it zero.
            "station_readings": 0,
            "stations_over_bound": 0,
            # A joint whose low side FLIPS along its run — its face
            # would have to cross the joint.  Counted, majority side
            # taken.
            "joints_sign_flipped": 0,
        }

    def add(self, joint: TerraceJoint) -> None:
        self.joints.append(joint)
        self.by_shape.setdefault(joint.shape_id, []).append(joint)
        self.stats["joints"] += 1

    def area_fraction(self) -> float:
        """The panelized share of apron area — REPORT ONLY (§2(c)).

        The area-share STOP is retired: the owner's ruling targets long
        aprons on genuinely steep ground, so the target population IS the
        large-area family and an area guard fires precisely when the law
        works as ruled.  The certificate (§2(a)) and the evidence bound
        (§2(b)) are the law; this number is quoted honestly beside them.
        """
        total = self.stats["apron_area_total"]
        if total <= 0.0:
            return 0.0
        return self.stats["apron_area_panelized"] / total










def _dem_gradient(node_xy, node_dem, nodes):
    """Least-squares plane fit of the DEM over the component's nodes:
    returns ``((gx, gy), slope)`` — the unit direction of steepest DEM
    ascent and its magnitude — or ``None``."""
    pts = [(node_xy[i][0], node_xy[i][1], node_dem[i]) for i in nodes
           if i < len(node_dem) and node_dem[i] == node_dem[i]
           and node_xy.get(i) is not None]
    if len(pts) < 3:
        return None
    n = float(len(pts))
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    mz = sum(p[2] for p in pts) / n
    sxx = syy = sxy = sxz = syz = 0.0
    for (x, y, z) in pts:
        dx, dy, dz = x - mx, y - my, z - mz
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
        sxz += dx * dz
        syz += dy * dz
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:
        return None
    a = (sxz * syy - syz * sxy) / det
    b = (syz * sxx - sxz * sxy) / det
    slope = math.hypot(a, b)
    if slope < 1e-9:
        return None
    return (a / slope, b / slope), slope


# ────────────────────────────────────────────────────────────────────
# 2.  THE CORRIDOR COVER — the no-cross set
# ────────────────────────────────────────────────────────────────────

def runway_strip_keepout_geometry(layout):
    """The runway-strip footprint union, buffered by the joint clearance.

    §1 of the flip-readiness spec: the ONE law function
    (``grade_law.runway_strip_wall_keepout_rings``, reached through
    ``adjacent_ground.runway_strip_wall_keepout``) that the wall emitters
    and ``tools/check_grade`` already build from.

    GATE RECONCILIATION (the named hazard): ``require_gate=False`` is the
    whole answer.  The footprint GEOMETRY is read regardless of
    ``O4_STRIP_PRECEDENCE`` (that gate governs corridor LAW, not where
    strips ARE) and regardless of ``O4_RUNWAY_STRIP_WALL_LAW`` (its "0"
    escape is archaeology — the owner's walls-are-never-lawful-in-a-strip
    ruling is not gate-shaped).

    The ``APRON_TERRACE_JOINT_CLEARANCE_M`` buffer covers the measured
    emitter-vs-validator footprint drift (rsa amendment 4: endpoints
    0.27-0.98 m, ring width to 1.19 m — all < 2.0 m).
    """
    try:
        from auto_patch.adjacent_ground import runway_strip_wall_keepout
        block = runway_strip_wall_keepout(layout, require_gate=False)
    except (ImportError, AttributeError, *_GEOM_EXC):
        return None
    if block is None or block.is_empty:
        return None
    try:
        return block.buffer(APRON_TERRACE_JOINT_CLEARANCE_M)
    except _GEOM_EXC:
        return block


def corridor_cover(layout, polygon=None):
    """The NO-CROSS set: every taxi/route centerline (apt.dat + OSM,
    ground-vehicle SVC spines INCLUDED) buffered by the corridor
    half-width plus the joint clearance, PLUS every building frontage
    chord (``reach-follows-centerlines``: stands are aircraft travel, so a
    stand's frontage chord is a route), PLUS — §1 — every RUNWAY STRIP
    footprint buffered by the joint clearance, PLUS every BUILDING
    FOOTPRINT buffered by the same clearance (lead 2026-08-05: a joint was
    minted 0.60 m from a pad because the cover carried the frontage chord
    but not the pad).

    SERVICE SPINES ARE IN THE SET (spec interaction fence): "a wall across
    a vehicle route is still a wall".  Whether service routes may relax is
    an INTENT question for the owner; the conservative side is the side
    that mints fewer joints, and this is it.

    THE STRIP FENCE IS STRUCTURAL (§1).  A joint is born as
    ``(terrace line ∩ apron) − cover``; with the strip footprint IN the
    cover, a joint inside any strip is impossible by construction —
    exactly as joints-crossing-routes already are.  Before this, only the
    FACE emitter consulted the keepout, so the joint (line + step budget
    + sidecar row) was minted in the strip anyway and its allowance
    outlived the dropped face (the S1 specimen, KCLT 1.53 m).

    Returns a prepared-ish shapely geometry (or ``None`` when the layout
    has neither a corridor nor a runway).
    """
    from auto_patch.elevation_per_surface.solver_primitives import (
        _corridor_segments)
    half = (APRON_TERRACE_CORRIDOR_HALF_WIDTH_M
            + APRON_TERRACE_JOINT_CLEARANCE_M)
    pieces = []
    segs = _corridor_segments(layout, include_roads=True)
    for ((ax, ay), (bx, by)) in segs:
        if math.hypot(bx - ax, by - ay) < 1e-6:
            continue
        pieces.append(LineString([(ax, ay), (bx, by)]))
    # Building frontage chords: the chord from each building pad to the
    # nearest corridor point is aircraft travel (the stand lead-in).  With
    # no corridor at all there is nothing to lead in to.
    if pieces:
        corridor_union = unary_union(pieces)
        for s in getattr(layout, "shapes", ()):
            if (s.role or "") != "building":
                continue
            poly = getattr(s, "polygon", None)
            if poly is None or poly.is_empty:
                continue
            try:
                pt = poly.representative_point()
                near = corridor_union.interpolate(
                    corridor_union.project(pt))
                if pt.distance(near) > 1e-6:
                    pieces.append(LineString([(pt.x, pt.y),
                                              (near.x, near.y)]))
            except _GEOM_EXC:
                continue
    # ── §1 THE RUNWAY-STRIP FENCE ────────────────────────────────────
    strip = runway_strip_keepout_geometry(layout)
    cover = None
    if pieces:
        try:
            cover = unary_union(pieces).buffer(half)
        except _GEOM_EXC:
            cover = None
    if strip is not None:
        try:
            cover = strip if cover is None else unary_union([cover, strip])
        except _GEOM_EXC:
            cover = cover if cover is not None else strip
    # ── BUILDING FOOTPRINTS ARE IN THE COVER (lead 2026-08-05) ───────
    # Same shape as the strip fence, and for the same reason: the cover
    # carried each stand's frontage CHORD but not the pad it leads to, so
    # a joint could be — and was — minted 0.60 m from a building
    # footprint.  A terrace step at a pad edge is a wall against the
    # building, which no reading of the ruling licenses.  The footprint
    # union is buffered by the joint clearance exactly like the strip
    # footprint, so the fence is structural: a joint inside (or within
    # clearance of) a pad is impossible by construction, never dropped
    # after the fact.
    pads = []
    for s in getattr(layout, "shapes", ()):
        if (s.role or "") != "building":
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        pads.append(poly)
    if pads:
        try:
            pad_fence = unary_union(pads).buffer(
                APRON_TERRACE_JOINT_CLEARANCE_M)
            cover = (pad_fence if cover is None
                     else unary_union([cover, pad_fence]))
        except _GEOM_EXC:
            pass
    if cover is None or cover.is_empty:
        return None
    if polygon is not None:
        try:
            cover = cover.intersection(polygon.buffer(1.0))
        except _GEOM_EXC:
            pass
    return cover


def _pavement_neighbours(layout, shape):
    """Every OTHER shape of this layout that the step readers judge —
    the population a facing boundary run can face (§3(c)).

    The membership predicate is the step readers' OWN
    (``check_grade._role_grade_limit(...) is None`` ⇒ skipped), read from
    the SAME ``ROLE_GRADE_LIMITS`` table, so emitter and validator cannot
    disagree about who is a neighbour.

    ONE EXCLUSION, and it is structural: a SIBLING PANEL of the same
    terrace declaration is not a neighbour.  Two panels split apart by a
    declared joint stand 0.6 m from each other by construction, so the
    facing law would read the DECLARED step as an undeclared one and
    conform it away — the two clauses would be fighting over the same
    ground.  The joint's own step edge governs there, and nothing else.
    """
    from auto_patch.config import ROLE_GRADE_LIMITS
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return []
    group = getattr(shape, "_terrace_panel_group", None)
    try:
        (x0, y0, x1, y1) = poly.bounds
    except _GEOM_EXC:
        return []
    pad = APRON_TERRACE_FACING_PROXIMITY_M + 1.0
    out = []
    for s in getattr(layout, "shapes", ()):
        if s is shape:
            continue
        if (group is not None
                and getattr(s, "_terrace_panel_group", None) == group):
            continue                      # sibling panel — see above
        if ROLE_GRADE_LIMITS.get(s.role or "", None) is None:
            continue
        p = getattr(s, "polygon", None)
        if p is None or p.is_empty:
            continue
        try:
            (a0, b0, a1, b1) = p.bounds
        except _GEOM_EXC:
            continue
        if a1 < x0 - pad or a0 > x1 + pad or b1 < y0 - pad or b0 > y1 + pad:
            continue
        out.append(s)
    return out


def _facing_boundary(layout, shape):
    """``(facing_geom, neighbour_union)`` for one panelized apron (§3(c)).

    ``facing_geom`` is the stretch of THIS apron's exterior ring that
    comes within ``APRON_TERRACE_FACING_PROXIMITY_M`` of another paved
    shape — the "FACING BOUNDARY RUN".  ``None`` when the apron faces
    nothing.

    RULING §3(c): panel outer boundaries against non-panelized
    neighbours keep FULL law.  The terrace law owns apron INTERIORS; the
    lateral-contiguity family governs the outer ring.  The HECA specimen
    is apron ``-10519`` (panelized) 0.72-0.89 m from apron ``-10520``
    (not panelized): the panel's level change reached the outer boundary
    and shipped 0.57/0.72 m of UNDECLARED step, with no joint (24.3 m
    away), no face and no allowance behind it.
    """
    neighbours = _pavement_neighbours(layout, shape)
    if not neighbours:
        return None, None
    try:
        ring = shape.polygon.exterior
    except _GEOM_EXC:
        return None, None
    parts = []
    for s in neighbours:
        try:
            parts.append(s.polygon.exterior)
        except _GEOM_EXC:
            continue
    if not parts:
        return None, None
    try:
        nb = unary_union(parts)
        band = nb.buffer(APRON_TERRACE_FACING_PROXIMITY_M)
        facing = ring.intersection(band)
        # A GAP IS NOT A WELD.  Almost every apron ring on a real
        # airport runs flush against a taxiway or junction — those
        # neighbours SHARE the boundary and are already one laterally
        # contiguous surface, governed by the contiguity family, with no
        # step to conform to.  The class §3(c) is about is the GAPPED
        # one: HECA ``-10519``/``-10520`` sit 0.72-0.89 m apart with no
        # shared vertex, so the panel's level change appears as a
        # cross-shape STEP.  Subtracting the welded stretch is the
        # difference between fencing that class (HEAZ 248 edges) and
        # denying the terrace law to the whole apron ring (measured:
        # HECA 6,198 edges, and the airside win collapsed with it).
        welded = nb.buffer(_FACING_WELD_TOL_M)
        facing = facing.difference(welded)
    except _GEOM_EXC:
        return None, None
    if facing.is_empty:
        return None, nb
    return facing, nb


def _face_bands(line_pts):
    """The TWO candidate retreat bands of a joint — one per side.

    The low side is unknown before the solve, so §3(a) tests BOTH: a
    joint that could not face on EITHER side is inadmissible by geometry
    alone and must never be minted."""
    (x0, y0) = line_pts[0]
    (x1, y1) = line_pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return []
    nx, ny = -dy / norm, dx / norm
    out = []
    for sign in (1.0, -1.0):
        rx = nx * sign * _RETREAT_TRIM_M
        ry = ny * sign * _RETREAT_TRIM_M
        top = list(line_pts)
        bot = [(x + rx, y + ry) for (x, y) in top]
        try:
            poly = Polygon(top + bot[::-1])
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:
            continue
        out.append(poly)
    return out


# §3(d) SPLIT REACH.  A joint piece was trimmed ``_RETREAT_TRIM_M`` off
# each end so the FACE's corner keeps the pinned clearance.  Where that
# end was cut by the APRON BOUNDARY rather than by the no-cross cover,
# the trim can be given back plus a small overshoot, so the wall band
# CROSSES the ring and the difference SPLITS the apron into panels
# instead of punching an interior hole.  The overshoot must exceed the
# emitter's canonical proximity tolerance so the crossing is
# unambiguous.
_SPLIT_OVERSHOOT_M = 0.75


def _face_admissible(line_pts, keepout) -> bool:
    """§3(a) PLAN-TIME FACE ADMISSIBILITY.

    A joint's admissibility is decided ONCE, here, by geometry that needs
    no solve.  Both candidate retreat bands are tested against the
    keepout; if NEITHER can carry a face the joint is STILLBORN — never
    in ``plan.joints``, never a solver budget, never a sidecar row.

    This is what makes "faced-or-no-relief" self-enforcing: the budget
    cannot outlive the face because both are minted from the SAME
    plan-time fact.  With §1 landed the keepout class is empty by
    construction (strip footprint + 2.0 m clearance > 0.6 m retreat), and
    the rule still holds for every OTHER keepout the wall machinery ever
    grows.
    """
    if keepout is None:
        return True
    bands = _face_bands(line_pts)
    if not bands:
        return False
    for band in bands:
        try:
            if not band.intersects(keepout):
                return True
        except _GEOM_EXC:
            continue
    return False




# ────────────────────────────────────────────────────────────────────
# 3.  PANELIZATION — terrace lines cut out of the corridor cover
# ────────────────────────────────────────────────────────────────────

def _extent_along(polygon, direction):
    """The polygon's extent (m) along ``direction`` — the run the ground's
    relief is spread over."""
    (gx, gy) = direction
    try:
        ring = list(polygon.exterior.coords)
    except _GEOM_EXC:
        return 0.0
    ts = [x * gx + y * gy for (x, y) in ring]
    return float(max(ts) - min(ts)) if ts else 0.0


def _terrace_lines(polygon, gradient, count):
    """``count`` full-width terrace lines perpendicular to ``gradient``,
    evenly spaced across the polygon's extent ALONG the gradient.

    A terrace line follows the CONTOUR — that is what makes it lawful to
    step across, and it is also the direction a spine running up the slope
    would cross, which is why the cut against the corridor cover below is
    the whole binding constraint rather than a detail."""
    (gx, gy) = gradient
    px, py = -gy, gx                      # the contour direction
    try:
        ring = list(polygon.exterior.coords)
    except _GEOM_EXC:
        return []
    ts = [x * gx + y * gy for (x, y) in ring]
    ss = [x * px + y * py for (x, y) in ring]
    t_lo, t_hi = min(ts), max(ts)
    s_lo, s_hi = min(ss), max(ss)
    if t_hi - t_lo < 1e-6:
        return []
    pad = 10.0
    out = []
    for k in range(1, count + 1):
        t = t_lo + (t_hi - t_lo) * k / (count + 1)
        a = (gx * t + px * (s_lo - pad), gy * t + py * (s_lo - pad))
        b = (gx * t + px * (s_hi + pad), gy * t + py * (s_hi + pad))
        out.append(LineString([a, b]))
    return out


def _cut_joint_pieces(line, polygon, cover):
    """``(terrace line ∩ apron) − corridor cover`` → the joint pieces.

    THIS is the binding constraint.  A joint piece cannot cross a route
    because it is DEFINED as the part of the terrace line that is not in
    the corridor cover; nothing downstream may lengthen it."""
    try:
        inside = line.intersection(polygon)
    except _GEOM_EXC:
        return []
    if inside.is_empty:
        return []
    if cover is not None:
        try:
            inside = inside.difference(cover)
        except _GEOM_EXC:
            return []
        if inside.is_empty:
            return []
    parts = []
    if isinstance(inside, LineString):
        parts = [inside]
    elif isinstance(inside, MultiLineString):
        parts = [g for g in inside.geoms]
    else:
        parts = [g for g in getattr(inside, "geoms", ())
                 if isinstance(g, LineString)]
    # END TRIM.  The difference leaves each piece's endpoint exactly ON
    # the cover boundary; the joint FACE then retreats
    # ``STACKED_WALL_RETREAT_M`` perpendicular to the joint, which on an
    # oblique joint would put the wall's corner that far back toward the
    # corridor.  Trim the retreat off both ends so the emitted GEOMETRY,
    # not merely the line, keeps the pinned clearance.
    # A terrace line is STRAIGHT, so every piece of it is a straight
    # sub-segment: the trimmed piece is exactly its two interpolated
    # stations, with no interior vertex to preserve.
    out = []
    trim = _RETREAT_TRIM_M
    for p in parts:
        if p.is_empty or p.length <= 2.0 * trim:
            continue
        a = p.interpolate(trim)
        b = p.interpolate(p.length - trim)
        out.append(LineString([(a.x, a.y), (b.x, b.y)]))
    return [p for p in out if not p.is_empty and p.length > 0.0]


# ════════════════════════════════════════════════════════════════════
# 4a.  THE PRE-SOLVE PANEL BOUNDARY  (completion round 2026-08-05)
# ════════════════════════════════════════════════════════════════════
#
# WHAT CHANGED AND WHY.  Every residue this law carried — the D2 face
# height, the 5 defects the §3(d) split minted, the 2 479 m² face lap —
# had ONE root, named in the flip-readiness evidence: *the panel boundary
# did not exist at plan time*.  The face was minted post-solve from an
# extrapolated reading of flank vertices up to 150 m away, and the split
# that would have created real boundary vertices ran AFTER the face, so
# those vertices adopted the FACE's level — a value the solve never
# produced.
#
# The fix is structural and it is the target architecture's own shape
# ("ingest all data -> refine all geometry -> ONE elevation solve
# carrying ALL grade law -> emitters emit, never grade"): the terrace
# panelization is GEOMETRY REFINEMENT, so it happens BEFORE the solve.
# The apron is split into panels here; the panel boundary vertices are
# ordinary apron ring vertices; the node list admits them; the solve
# gives them values; the emitter reads those values by IDENTITY.  Every
# ring vertex carries a solve-produced value because there is no other
# kind of value in the system any more.
#
# DECIDED AND NOTED (12320bd allows this; the owner should see it):
#   1. THE TRIGGER IS NOW DEM + GEOMETRY ONLY.  The old trigger ran the
#      component ENVELOPE over the solve's current values, which is
#      unavailable pre-solve — and under RULINGS 5578b6a ("there is no
#      lawful-infeasible ground") an envelope excess is a DEFECT REPORT
#      about the law or the instrument, never a licence to terrace.  What
#      licenses a terrace is the GROUND: an apron whose own DEM plane is
#      steeper than the apron cap over its own extent cannot be one
#      panel.  That reading (``geom_excess``) was already in the law and
#      already preferred whenever it was the larger of the two
#      (``relief = max(worst_gap, geom_excess)``), and the flip evidence
#      measured the envelope UNDER-firing against it (HEAZ 1.55 m vs
#      3.06 m: one joint minted where the ground asked for two).  The
#      envelope machinery (``_component_envelope``, ``_cap_distance``)
#      is retained: it is the certificate's cross-check, not its trigger.
#   2. A JOINT THAT CANNOT SPLIT ITS APRON IS STILLBORN.  Every shape in
#      this system is simply connected and ~17 ring iterations in the
#      solver assume it.  A wall band that would punch an interior ring
#      instead of separating the apron therefore mints no joint at all —
#      no budget, no face, no relief, counted loudly as
#      ``joints_stillborn_hole``.  This is §3(a)'s own principle (the
#      budget cannot outlive the face) applied one step earlier.
#   3. THE POST-SOLVE SPLIT IS RETIRED, NOT REVIVED.  ``_split_lower_
#      panels`` / ``_split_reach_line`` were parked pending "interior-ring
#      emit support, plus a panel boundary that exists BEFORE the solve".
#      The second half of that precondition removes the need for the
#      first: with the split pre-solve there is no lap to close and no
#      emitter-assigned boundary value to mint.  The reach-line END
#      GIVE-BACK logic those functions carried is preserved verbatim in
#      :func:`_split_reach_line` below, which now runs at plan time.

def _split_reach_line(line_pts, polygon, cover):
    """The joint line extended so its wall band REACHES the apron ring.

    A joint piece was trimmed ``_RETREAT_TRIM_M`` off each end so the
    FACE's corner keeps the pinned clearance.  Where that end was cut by
    the APRON BOUNDARY rather than by the no-cross ``cover``, the trim
    can be given back plus a small overshoot, so the wall band CROSSES
    the ring and the difference SPLITS the apron into panels instead of
    punching an interior hole.  An end that was cut by a corridor or a
    runway strip keeps its clearance and is left where it is.

    Returns ``(line, both_ends_reach)``.
    """
    (x0, y0), (x1, y1) = line_pts[0], line_pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return list(line_pts), False
    ux, uy = dx / norm, dy / norm
    ext = _RETREAT_TRIM_M + _SPLIT_OVERSHOOT_M
    ends = []
    for (px, py, sx, sy) in ((x0, y0, -ux, -uy), (x1, y1, ux, uy)):
        cand = (px + sx * ext, py + sy * ext)
        ok = True
        if cover is not None:
            try:
                ok = not LineString([(px, py), cand]).intersects(cover)
            except _GEOM_EXC:
                ok = False
        if ok and polygon is not None:
            # the extension is only useful if it actually leaves the
            # apron — otherwise the band still ends in the interior
            try:
                ok = not polygon.contains(_Point(*cand))
            except _GEOM_EXC:
                ok = False
        ends.append((cand if ok else (px, py), ok))
    return [ends[0][0], ends[1][0]], (ends[0][1] and ends[1][1])


def _joint_stations(line_pts, low_sign: float, retreat: float):
    """The joint's PANEL BOUNDARY, as coordinates.

    Returns ``(grid, hi_row, lo_row)``: the station arc-lengths, the row
    ON the joint line (the UPPER panel's new edge) and the row retreated
    ``retreat`` metres to the low side (the LOWER panel's new edge).
    These exact tuples are used three times — to cut the apron, to bind
    the declared step in the solve, and to mint the wall face — so the
    three cannot describe different geometry.
    """
    (x0, y0), (x1, y1) = line_pts[0], line_pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return [], [], []
    ux, uy = dx / norm, dy / norm
    nx, ny = -dy / norm, dx / norm
    rx, ry = nx * low_sign * retreat, ny * low_sign * retreat
    # Endpoints INCLUDED: the band's corners are the vertices the
    # difference will cut the apron ring at, so they must be stations
    # like any other or the emitted wall would not share them.
    grid = [0.0] + _station_grid(norm) + [norm]
    hi = [(x0 + ux * s, y0 + uy * s) for s in grid]
    lo = [(x + rx, y + ry) for (x, y) in hi]
    return grid, hi, lo


def _low_side_sign(line_pts, gdir) -> float:
    """Which side of the joint the ground FALLS toward (+1 / -1).

    ``gdir`` is the unit direction of steepest DEM ASCENT, so the low
    side is the one the joint normal points to when the normal opposes
    the gradient.  Decided from the ground, at plan time, once — the
    post-solve majority vote it replaces could disagree with the
    geometry the apron had already been cut into.
    """
    (x0, y0), (x1, y1) = line_pts[0], line_pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return 1.0
    nx, ny = -dy / norm, dx / norm
    return -1.0 if (nx * gdir[0] + ny * gdir[1]) > 0.0 else 1.0


def _apron_dem_plane(polygon, sample_dem):
    """``((gx, gy), slope)`` for one apron polygon, from the DEM alone.

    Samples the ring vertices plus a coarse interior grid (the ring
    alone can be degenerate — a long thin apron's vertices are nearly
    collinear) and fits the same least-squares plane
    :func:`_dem_gradient` fits, through the same code.
    """
    try:
        ring = _open_ring_xy(polygon)
    except _GEOM_EXC:
        return None
    if len(ring) < 3:
        return None
    pts = list(ring)
    try:
        (minx, miny, maxx, maxy) = polygon.bounds
        step = max(25.0, max(maxx - minx, maxy - miny) / 12.0)
        gy = miny + 0.5 * step
        while gy < maxy:
            gx = minx + 0.5 * step
            while gx < maxx:
                if polygon.contains(_Point(gx, gy)):
                    pts.append((gx, gy))
                gx += step
            gy += step
    except _GEOM_EXC:
        pass
    xy = {}
    dem = []
    idx = []
    for (x, y) in pts:
        z = sample_dem(x, y)
        if z is None or z != z:
            continue
        i = len(dem)
        xy[i] = (float(x), float(y))
        dem.append(float(z))
        idx.append(i)
    if len(idx) < 3:
        return None
    return _dem_gradient(_as_xy(xy), dem, idx)


def _open_ring_xy(polygon):
    coords = list(polygon.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for (x, y) in coords]


def construct_apron_terrace_presolve(layout, dem, tile_lat: int,
                                     tile_lon: int,
                                     icao: str = "") -> int:
    """PANELIZE EVERY APRON, BEFORE THE SOLVE.  Returns #joints minted.

    Splits each triggered apron polygon at its terrace joints and stages
    the declaration on ``layout.apron_terrace_presolve``:

        [{"shape_id": id(largest panel), "ref": …, "certificate": {…},
          "joints": [{"line": [(x,y),…], "step_m": …, "line_ordinal": …,
                      "low_sign": ±1.0, "grid": [s,…],
                      "hi": [(x,y),…], "lo": [(x,y),…]}, …]}, …]

    The apron's own ``BuiltShape`` is KEPT and re-pointed at the largest
    panel (identity survives for everything that captured it earlier in
    the pipeline); the sibling panels are appended as new apron shapes
    with the same ref.  Every ``hi``/``lo`` coordinate is therefore an
    apron RING vertex by the time ``_build_node_list`` runs, which is the
    whole point: the panel boundary is a set of solve variables.

    Never raises: one apron's geometry failure drops that apron from the
    declaration and is counted.
    """
    from auto_patch.elevation import _sample_dem
    layout.apron_terrace_presolve = []
    if dem is None or getattr(layout, "anchor", None) is None:
        return 0
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    _R = 6378137.0

    def sample_dem(x: float, y: float):
        try:
            lat = lat0 + math.degrees(y / _R)
            lon = lon0 + math.degrees(x / (_R * cos0))
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except (*_GEOM_EXC, ZeroDivisionError):
            return None

    return _construct_from_sampler(layout, sample_dem, icao=icao)


def _construct_from_sampler(layout, sample_dem, icao: str = "") -> int:
    """:func:`construct_apron_terrace_presolve` with the DEM already
    resolved to a ``(x, y) -> z | None`` callable.

    Split out so the twins drive the REAL panelizer against an analytic
    ground instead of a second implementation — one panelizer, one
    population, which is the whole reason the mid-solve one was retired.
    """
    from auto_patch.adjacent_ground import (STACKED_WALL_RETREAT_M,
                                            runway_strip_wall_keepout)
    from auto_patch.layout import BuiltShape
    layout.apron_terrace_presolve = []
    stats = {"candidates": 0, "triggered": 0, "joints": 0,
             "joints_stillborn_keepout": 0, "joints_stillborn_hole": 0,
             "joint_pieces_dropped_short": 0,
             "joint_lines_lost_to_corridor": 0,
             "polygons_split": 0, "split_pieces_added": 0}
    cover = corridor_cover(layout)
    try:
        keepout = runway_strip_wall_keepout(layout, require_gate=False)
    except (ImportError, AttributeError, *_GEOM_EXC):
        keepout = None
    aprons = [s for s in list(getattr(layout, "shapes", ()))
              if s.role == ROLE_APRON and s.polygon is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"]
    new_shapes: list = []
    for shape in aprons:
        stats["candidates"] += 1
        try:
            entry = _panelize_apron(layout, shape, cover, keepout,
                                    sample_dem, STACKED_WALL_RETREAT_M,
                                    stats)
        except _GEOM_EXC:
            continue
        if entry is None:
            continue
        panels = entry.pop("_panels")
        # The apron KEEPS ITS IDENTITY as the largest panel; the rest
        # become sibling aprons.  Losing pavement to a geometry op is
        # never the lawful answer, so every piece is emitted.
        shape.polygon = panels[0]
        # Sibling panels of ONE declaration are marked so the facing law
        # never reads a DECLARED step as an undeclared one (see
        # ``_pavement_neighbours``).  The group key is the surviving
        # shape's identity, which is also the presolve entry's key.
        _group = id(shape)
        shape._terrace_panel_group = _group
        for extra in panels[1:]:
            sib = BuiltShape(polygon=extra, role=ROLE_APRON,
                             ref=getattr(shape, "ref", ""))
            sib._terrace_panel_group = _group
            new_shapes.append(sib)
        stats["polygons_split"] += 1
        stats["split_pieces_added"] += len(panels) - 1
        stats["triggered"] += 1
        stats["joints"] += len(entry["joints"])
        layout.apron_terrace_presolve.append(entry)
    if new_shapes:
        layout.shapes.extend(new_shapes)
    layout.apron_terrace_presolve_stats = stats
    # ── THE WALL BANDS, PUBLISHED AT PLAN TIME ──────────────────────
    # NAMED HAZARD, NOT YET MEASURED (completion round, no builds):
    # between the solve and ``emit_terrace_joint_faces`` the 0.6 m band
    # between two panels is ground no shape covers, and
    # ``emit_adjacent_ground_bands`` runs FIRST (pipeline ~6024 vs
    # ~6376).  Its march reads a static block built from
    # ``layout.shapes``, so in principle it can march a graded strip
    # into that slot and mint terrain where a retaining wall is about to
    # stand.  The band geometry is therefore published HERE, where it is
    # first known, so the march (or the test phase's check) has the
    # exact polygons rather than having to re-derive them.  The march is
    # deliberately NOT changed on a guess — attribute it with a build
    # first (mechanism before fix).
    layout.apron_terrace_wall_bands = [
        b for e in layout.apron_terrace_presolve
        for b in (e.pop("_bands", None) or ())]
    if stats["joints"] or _os.environ.get("O4_STEP_DEBUG") == "1":
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [apron-terrace] {icao}: PRE-SOLVE panelization — "
            f"{stats['candidates']} apron candidate(s), "
            f"{stats['triggered']} panelized into "
            f"{stats['triggered'] + stats['split_pieces_added']} panel(s), "
            f"{stats['joints']} declared joint(s); stillborn "
            f"{stats['joints_stillborn_keepout']} unfaceable / "
            f"{stats['joints_stillborn_hole']} would punch a hole; "
            f"pieces dropped short {stats['joint_pieces_dropped_short']}, "
            f"lines lost to the corridor cover "
            f"{stats['joint_lines_lost_to_corridor']}")
    return stats["joints"]


def _panelize_apron(layout, shape, cover, keepout, sample_dem,
                    retreat: float, stats):
    """One apron: trigger, cut, split.  ``None`` when it does not fire.

    Returns the presolve entry with an extra ``_panels`` key (the panel
    polygons, largest first) that the caller pops.
    """
    poly = shape.polygon
    plane = _apron_dem_plane(poly, sample_dem)
    if plane is None:
        return None
    (gdir, plane_slope) = plane
    # ── THE TRIGGER: the GROUND's own demand, DEM + geometry only ────
    # An apron whose DEM plane is steeper than the apron cap cannot be
    # one panel: over its own extent along the gradient it demands
    # ``(slope − cap)·extent`` metres of relief that no single lawful
    # surface can absorb.  Instrument-independent, and it is the reading
    # the old law already preferred whenever it was the larger.
    if plane_slope <= APRON_MAX_GRADE:
        return None
    extent = _extent_along(poly, gdir)
    geom_excess = max(0.0, (plane_slope - APRON_MAX_GRADE) * extent)
    if geom_excess < APRON_TERRACE_MIN_EXCESS_M:
        return None
    joint_count = max(1, int(math.ceil(geom_excess
                                       / APRON_TERRACE_MAX_STEP_M)))
    step_m = min(APRON_TERRACE_MAX_STEP_M, geom_excess / joint_count)
    # §3(c): joint lines keep the joint clearance from FACING boundary
    # runs, so no joint discharges its step at a neighbour's face.
    facing, _nb = _facing_boundary(layout, shape)
    cut_cover = cover
    if facing is not None and not facing.is_empty:
        try:
            fence = facing.buffer(APRON_TERRACE_JOINT_CLEARANCE_M)
            cut_cover = (fence if cut_cover is None
                         else unary_union([cut_cover, fence]))
        except _GEOM_EXC:
            pass
    joints: list = []
    bands: list = []
    # Panels accumulate: joint k+1 is cut out of the geometry joint k
    # left behind, so two joints of one apron can never both claim the
    # same ground.
    panels = [poly]
    for ordinal, line in enumerate(_terrace_lines(poly, gdir,
                                                  joint_count)):
        pieces = _cut_joint_pieces(line, poly, cut_cover)
        if not pieces:
            stats["joint_lines_lost_to_corridor"] += 1
            continue
        kept = 0
        for piece in pieces:
            if piece.length < APRON_TERRACE_MIN_JOINT_LEN_M:
                stats["joint_pieces_dropped_short"] += 1
                continue
            pts = list(piece.coords)
            if not _face_admissible(pts, keepout):
                stats["joints_stillborn_keepout"] += 1
                continue
            host = _panel_containing(panels, pts)
            if host is None:
                stats["joints_stillborn_hole"] += 1
                continue
            reach, _both = _split_reach_line(pts, host, cut_cover)
            low_sign = _low_side_sign(reach, gdir)
            grid, hi, lo = _joint_stations(reach, low_sign, retreat)
            if len(hi) < 2:
                stats["joints_stillborn_hole"] += 1
                continue
            band = _band_polygon(hi, lo)
            split = _split_panel(panels, host, band)
            if split is None:
                # The band would punch an INTERIOR RING (or vanish the
                # apron).  Every shape in this system is simply
                # connected; a joint that cannot separate its apron is
                # STILLBORN, exactly as an unfaceable one is — no
                # budget, no face, no relief.
                stats["joints_stillborn_hole"] += 1
                continue
            panels = split
            bands.append(band)
            joints.append({
                "line": [(float(x), float(y)) for (x, y) in pts],
                "reach": [(float(x), float(y)) for (x, y) in reach],
                "step_m": float(step_m),
                "line_ordinal": int(ordinal),
                "low_sign": float(low_sign),
                "grid": [float(s) for s in grid],
                "hi": [(float(x), float(y)) for (x, y) in hi],
                "lo": [(float(x), float(y)) for (x, y) in lo],
            })
            kept += 1
        if kept == 0:
            stats["joint_lines_lost_to_corridor"] += 1
    if not joints:
        return None
    panels = sorted(panels, key=lambda p: -p.area)
    return {
        "shape_id": id(shape),
        "ref": getattr(shape, "ref", ""),
        "joints": joints,
        "_panels": panels,
        "_bands": bands,
        "certificate": {
            "ref": getattr(shape, "ref", ""),
            "plane_slope": round(float(plane_slope), 5),
            "extent_m": round(float(extent), 1),
            "geom_excess_m": round(float(geom_excess), 4),
            "relief_m": round(float(geom_excess), 4),
            "max_step_m": APRON_TERRACE_MAX_STEP_M,
            "line_budget": joint_count,
            "lines_used": len({j["line_ordinal"] for j in joints}),
            "declared_step_m": round(float(step_m), 4),
            "joints": len(joints),
            "panels": len(panels),
        },
    }


def _band_polygon(hi, lo):
    """The wall band: the joint's hi row and its retreated lo row."""
    ring = list(hi) + list(lo)[::-1]
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    return poly


def _panel_containing(panels, pts):
    """The panel a joint piece runs inside, or ``None``."""
    mid = _Point(0.5 * (pts[0][0] + pts[-1][0]),
                 0.5 * (pts[0][1] + pts[-1][1]))
    for p in panels:
        try:
            if p.contains(mid):
                return p
        except _GEOM_EXC:
            continue
    return None


def _split_panel(panels, host, band):
    """``panels`` with ``host`` replaced by ``host − band``.

    Two outcomes are both lawful and both accepted:

    * the band CROSSES the apron and the difference gives two panels —
      the clean case, and the one the reach-line give-back aims for;
    * the band ends inside the apron (an end that was cut by a corridor
      or a runway strip keeps its clearance and cannot be given back) and
      the difference gives ONE NOTCHED panel.  A notch is simply
      connected: the apron wraps around the band's inner end, and the
      law already says exactly what that means — a pair passing around
      the joint's end steps over nothing and keeps the full apron cap
      (``_crossed_joints``), while a pair that does step over the joint
      gets ``step + cap·d``.

    ``None`` when the subtraction would punch an INTERIOR RING, remove
    the panel entirely, or fail.  Every shape in this system is simply
    connected — ~17 ring iterations in the solver assume it — so a joint
    that could only be expressed as a hole is stillborn instead.
    """
    if band is None:
        return None
    try:
        rest = host.difference(band)
    except _GEOM_EXC:
        return None
    if rest.is_empty:
        return None
    pieces = ([rest] if rest.geom_type == "Polygon"
              else [g for g in getattr(rest, "geoms", ())
                    if g.geom_type == "Polygon" and not g.is_empty])
    if not pieces:
        return None
    if any(len(g.interiors) for g in pieces):
        return None                      # would punch an interior ring
    out = [p for p in panels if p is not host]
    out.extend(pieces)
    return out


def plan_apron_terraces(layout, shape_constraints, node_xy, node_dem,
                        elev, hard, icao: str = "",
                        bucket_to_idx=None) -> Optional[TerracePlan]:
    """THE BINDER — resolve the PRE-SOLVE declaration into this pass's
    index space and hand the solve its constraints.

    The panelization itself now happens before the solve
    (:func:`construct_apron_terrace_presolve`), so this function no
    longer decides anything: it reads ``layout.apron_terrace_presolve``,
    resolves each joint's ``hi``/``lo`` station rows to node indices, and
    returns the ``TerracePlan`` the budget appliers and the face emitter
    consume.  One panelizer, one population, no second instrument.

    ``bucket_to_idx`` is the solve's canonical bucket map; without it the
    stations are resolved against the coordinates carried in
    ``shape_constraints`` (the standalone/unit-twin path).

    Returns an empty plan when nothing panelized — never ``None`` in
    production; ``None`` only if the law itself is off.
    """
    if not apron_terrace_law_enabled():
        return None
    node_xy = _as_xy(node_xy)
    plan = TerracePlan()
    plan.cover = corridor_cover(layout)
    store = getattr(layout, "apron_terrace_presolve", None) or ()
    shapes_by_id = {id(s): s for s in getattr(layout, "shapes", ())}
    for s in getattr(layout, "shapes", ()):
        if s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty:
            continue
        try:
            plan.stats["apron_area_total"] += float(s.polygon.area)
        except _GEOM_EXC:
            pass
    plan.stats["candidates"] = sum(
        1 for s in getattr(layout, "shapes", ())
        if s.role == ROLE_APRON)
    # Mirror the PRE-SOLVE construction's own counters (never the
    # joint/trigger totals — those are recounted here from the joints
    # this pass actually resolved, so the two can be compared).
    _pre = getattr(layout, "apron_terrace_presolve_stats", None) or {}
    for _k in ("joints_stillborn_keepout", "joints_stillborn_hole",
               "joint_pieces_dropped_short",
               "joint_lines_lost_to_corridor",
               "polygons_split", "split_pieces_added"):
        if _k in _pre:
            plan.stats[_k] = _pre[_k]
    resolve = _station_resolver(layout, shape_constraints, node_xy,
                                bucket_to_idx)
    for entry in store:
        shape_id = entry.get("shape_id", -1)
        shape = shapes_by_id.get(shape_id)
        if shape is None:
            # The apron was dropped after the declaration was staged.
            # Its joints go with it — a budget may never outlive the
            # surface it was declared on.
            plan.stats["joints_orphaned"] = (
                plan.stats.get("joints_orphaned", 0)
                + len(entry.get("joints") or ()))
            continue
        plan.certificates[shape_id] = dict(entry.get("certificate") or {})
        plan.stats["triggered"] += 1
        try:
            plan.stats["apron_area_panelized"] += float(shape.polygon.area)
        except _GEOM_EXC:
            pass
        row = dict(entry.get("certificate") or {})
        row["verdict"] = "panelized"
        row["joints"] = len(entry.get("joints") or ())
        plan.trigger_rows.append(row)
        for jd in (entry.get("joints") or ()):
            joint = TerraceJoint(jd["reach"], jd["step_m"], shape_id,
                                 line_ordinal=jd.get("line_ordinal", 0))
            joint.low_sign = float(jd.get("low_sign", 1.0))
            joint.grid = [float(s) for s in jd.get("grid") or ()]
            joint.hi = [(float(x), float(y)) for (x, y) in jd["hi"]]
            joint.lo = [(float(x), float(y)) for (x, y) in jd["lo"]]
            # STATIONS AS SOLVE VARIABLES.  ``(k, s, i_hi, i_lo)`` — the
            # station's index in the row, its arc-length, and the two
            # node indices the declared step is BOUND between.  A
            # station whose rows did not intern (a panel dropped, a
            # bucket collision) simply carries ``None`` and binds
            # nothing; it is counted, never guessed at.
            sts = []
            for k, s_arc in enumerate(joint.grid):
                if k >= len(joint.hi) or k >= len(joint.lo):
                    break
                i_hi = resolve(joint.hi[k])
                i_lo = resolve(joint.lo[k])
                if i_hi is None or i_lo is None or i_hi == i_lo:
                    plan.stats["stations_unresolved"] = (
                        plan.stats.get("stations_unresolved", 0) + 1)
                    continue
                sts.append((k, float(s_arc), int(i_hi), int(i_lo)))
            joint.stations = sts
            plan.add(joint)
    # The §3(c) FACING population, resolved to node indices in THIS
    # pass's index space (positions only — no values, so it is the same
    # computation the pre-solve cut used).
    # EVERY PANEL of a panelized apron, not just the one that kept the
    # apron's identity: a sibling panel can abut a foreign apron just as
    # the parent could, and §3(c) is about that boundary.
    _groups = {id(shapes_by_id[sid]) for sid in plan.by_shape
               if sid in shapes_by_id}
    for entry in shape_constraints:
        shape_id = entry.get("shape_id", -1)
        shape = shapes_by_id.get(shape_id)
        if shape is None:
            continue
        if (shape_id not in plan.by_shape
                and getattr(shape, "_terrace_panel_group", None)
                not in _groups):
            continue
        facing, _nb = _facing_boundary(layout, shape)
        if facing is None or facing.is_empty:
            continue
        try:
            band = facing.buffer(APRON_TERRACE_FACING_PROXIMITY_M)
        except _GEOM_EXC:
            continue
        fnodes = set()
        for i in (entry.get("nodes") or ()):
            p = node_xy.get(i)
            if p is None:
                continue
            try:
                if band.contains(_Point(p[0], p[1])):
                    fnodes.add(i)
            except _GEOM_EXC:
                continue
        if fnodes:
            plan.facing_nodes[shape_id] = fnodes
    if (_os.environ.get("O4_APRON_TERRACE_DEBUG") == "1"
            or _os.environ.get("O4_STEP_DEBUG") == "1"):
        _report_plan(plan, icao)
    return plan


def _station_resolver(layout, shape_constraints, node_xy, bucket_to_idx):
    """``(x, y) -> node index`` for a panel-boundary station.

    THE CANONICAL JOIN, not a proximity join: a station coordinate is a
    ring vertex of the panel it bounds, so it interns to exactly the
    bucket that vertex claimed.  The fallback (no ``bucket_to_idx`` —
    the standalone/unit-twin path) indexes the constraint entries' own
    node coordinates at the registry's tolerance, which resolves the
    SAME vertex; it never invents a nearest neighbour beyond it.
    """
    cps = getattr(layout, "canonical_points", None)
    if bucket_to_idx is not None and cps is not None:
        def _by_registry(xy):
            k = cps.get(float(xy[0]), float(xy[1]))
            if k is None:
                k = cps.get_or_add(float(xy[0]), float(xy[1]))
            return bucket_to_idx.get(k)
        return _by_registry
    grid: dict = {}
    for entry in shape_constraints or ():
        for i in (entry.get("nodes") or ()):
            p = node_xy.get(i)
            if p is None:
                continue
            grid.setdefault((round(p[0] / 0.5), round(p[1] / 0.5)),
                            []).append((i, p[0], p[1]))

    def _by_grid(xy):
        best, best_d = None, None
        cx, cy = round(xy[0] / 0.5), round(xy[1] / 0.5)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for (i, px, py) in grid.get((gx, gy), ()):
                    d = math.hypot(px - xy[0], py - xy[1])
                    if d <= 0.5 and (best_d is None or d < best_d):
                        best, best_d = i, d
        return best
    return _by_grid


def rebind_terrace_stations(plan: Optional[TerracePlan], layout,
                            shape_constraints, node_xy,
                            bucket_to_idx=None) -> int:
    """Re-resolve every joint's station node indices in a NEW index space.

    A node index is only meaningful inside ONE ``_build_node_list`` call
    (the rod-key lesson: a plan carried by index across a rebuild binds
    the wrong vertices silently).  The joint's GEOMETRY is what the plan
    actually carries, so the second pass re-resolves the same coordinates
    through the same canonical join.  Returns the station count bound.
    """
    if plan is None or not plan.joints:
        return 0
    resolve = _station_resolver(layout, shape_constraints,
                                _as_xy(node_xy), bucket_to_idx)
    n = 0
    for joint in plan.joints:
        sts = []
        for k, s_arc in enumerate(joint.grid or ()):
            if k >= len(joint.hi) or k >= len(joint.lo):
                break
            i_hi = resolve(joint.hi[k])
            i_lo = resolve(joint.lo[k])
            if i_hi is None or i_lo is None or i_hi == i_lo:
                continue
            sts.append((k, float(s_arc), int(i_hi), int(i_lo)))
        joint.stations = sts
        n += len(sts)
    return n


def terrace_station_edges(plan: Optional[TerracePlan]):
    """THE ACTUAL-STEP BINDING — the law edges that hold each declared
    joint to the step it declared.

    ``[(i_hi, i_lo, step + cap·retreat), …]``.  This is the ONE
    constraint the pre-solve split makes possible and the post-solve
    reader never could: the two rows are in DIFFERENT panels now, so no
    within-shape law generates the pair, and without this edge the step
    across a declared joint would be unbounded.  The budget is the
    declaration plus the cap over the face's OWN width — a wall may be
    as tall as the step it declares, never as tall as the distance its
    reader had to travel.
    """
    from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
    out: list = []
    if plan is None:
        return out
    for joint in plan.joints:
        budget = (float(joint.step_m)
                  + APRON_MAX_GRADE * STACKED_WALL_RETREAT_M)
        for (_k, _s, i_hi, i_lo) in joint.stations:
            out.append((i_hi, i_lo, budget))
    return out



def _report_plan(plan: TerracePlan, icao: str) -> None:
    st = plan.stats
    print(f"    [apron-terrace] {icao}: {st['candidates']} apron "
          f"candidate(s), {st['triggered']} panelized, {st['joints']} "
          f"declared joint(s); pieces dropped short "
          f"{st['joint_pieces_dropped_short']}, terrace lines lost to "
          f"the corridor cover {st['joint_lines_lost_to_corridor']}; "
          f"stillborn (unfaceable) {st['joints_stillborn_keepout']}; "
          f"apron area panelized {plan.area_fraction() * 100:.1f} % "
          f"(REPORT ONLY — §2(c): the certificate and the evidence bound "
          f"are the law, area has no STOP power)")
    for row in plan.trigger_rows:
        print(f"    [apron-terrace]   {row.get('ref') or '(no ref)'}: "
              f"{row.get('verdict', 'panelized')} "
              f"joints={row.get('joints', 0)} "
              f"panels={row.get('panels', 0)} "
              f"declared step={row.get('declared_step_m', 0.0):.3f} m "
              f"| GEOM relief demand={row.get('geom_excess_m', 0.0):.3f} m "
              f"(plane {row.get('plane_slope', 0.0) * 100:.2f} % over "
              f"{row.get('extent_m', 0.0):.0f} m), line budget "
              f"{row.get('line_budget', 0)} used "
              f"{row.get('lines_used', 0)}")


# ────────────────────────────────────────────────────────────────────
# 4.  SOLVER BINDING — panels as constraint groups in the ONE solve
# ────────────────────────────────────────────────────────────────────

def _crossed_joints(joints, ax, ay, bx, by):
    """The joints this chord crosses.  Straddle prefilter first (the
    chord must span the joint's own extent along the joint normal) so the
    O(n²) apron visibility graph costs one dot product per joint per edge
    in the common no-cross case."""
    hits = []
    for j in joints:
        (x0, y0) = j.line[0]
        (x1, y1) = j.line[-1]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy)
        if norm < 1e-9:
            continue
        nx, ny = -dy / norm, dx / norm
        sa = (ax - x0) * nx + (ay - y0) * ny
        sb = (bx - x0) * nx + (by - y0) * ny
        if (sa > 0.0) == (sb > 0.0):
            continue                      # same side of the joint's line
        try:
            if j.geom.intersects(LineString([(ax, ay), (bx, by)])):
                hits.append(j)
        except _GEOM_EXC:
            continue
    return hits


def _rewrite_edges(edges, joints, node_xy, facing_nodes=None,
                   excluded_out=None):
    """``cap·d`` → ``cap·d + Σ step`` on every edge crossing a joint.

    RELAXING ONLY.  An edge that crosses no joint is returned byte-
    identical, so every within-panel pair and every pair on or through a
    corridor keeps the full apron law (spec §4: "within-panel edges keep
    the full apron law ... corridor nodes remain global route members").

    §3(c) EXCLUSION: an edge with an endpoint on a FACING BOUNDARY RUN is
    NEVER rewritten either.  Panel outer boundaries against non-panelized
    neighbours keep FULL law — the terrace law owns apron interiors, and
    a boundary node held to the interior at terrace budget is exactly how
    HECA ``-10519`` shipped a 0.72 m undeclared step at ``-10520``'s face.

    Returns ``(new_edges, n_joint_edges)``.
    """
    if not joints:
        return edges, 0
    out = []
    touched = 0
    fn = facing_nodes or ()
    for e in edges:
        if len(e) != 3:
            out.append(e)
            continue
        a, b, budget = e
        pa, pb = node_xy.get(a), node_xy.get(b)
        if pa is None or pb is None:
            out.append(e)
            continue
        hits = _crossed_joints(joints, pa[0], pa[1], pb[0], pb[1])
        if not hits:
            out.append(e)
            continue
        if a in fn or b in fn:
            out.append(e)                     # §3(c): full law, untouched
            if excluded_out is not None:
                excluded_out[0] += 1
            continue
        out.append((a, b, float(budget) + sum(j.step_m for j in hits)))
        touched += 1
    return out, touched




def _facing_conformance_edges(facing_nodes, own_nodes, node_xy, others):
    """§3(c) CONFORMANCE: cross-shape step constraints from each facing
    node to the nearest node of the shape it faces.

    The budget is the step READERS' own (``APRON_TERRACE_FACING_STEP_M``
    — ``check_grade``'s ``--edge-step``), so the boundary cannot drift
    from the neighbour IN THE SOLVE instead of being caught drifting by
    the validator afterwards.  One shared number, one law, both sides.

    ``others`` is the candidate partner population as ``[(index, x, y)]``
    — nodes belonging to any OTHER constraint entry.  A partner must be a
    solver node: the solve can only constrain what it holds.
    """
    if not facing_nodes or not others:
        return []
    lim = APRON_TERRACE_FACING_PROXIMITY_M
    out = []
    seen = set()
    for i in facing_nodes:
        p = node_xy.get(i)
        if p is None:
            continue
        best = None
        for (j, qx, qy) in others:
            if j == i or j in own_nodes:
                continue
            d = math.hypot(qx - p[0], qy - p[1])
            if d > lim:
                continue
            if best is None or d < best[0]:
                best = (d, j)
        if best is None:
            continue
        key = (i, best[1]) if i < best[1] else (best[1], i)
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1], APRON_TERRACE_FACING_STEP_M))
    return out


def _panel_components(nodes, edges, joints, node_xy):
    """Panels = connected components of the JOINT-FREE edge subgraph.

    A panel is therefore exactly "the apron region you can walk without
    stepping over a declared joint" — the constraint GROUP of spec §4.
    Corridor nodes are in whatever panel their joint-free edges put them,
    which is the shared-identity property the ruling needs: a corridor
    node is never on its own side of a joint."""
    parent = {i: i for i in nodes}

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in edges:
        if len(e) != 3:
            continue
        a, b, _bud = e
        if a not in parent or b not in parent:
            continue
        pa, pb = node_xy.get(a), node_xy.get(b)
        if pa is None or pb is None:
            continue
        if _crossed_joints(joints, pa[0], pa[1], pb[0], pb[1]):
            continue
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb
    roots: dict[int, int] = {}
    out: dict[int, int] = {}
    for i in nodes:
        r = _find(i)
        if r not in roots:
            roots[r] = len(roots)
        out[i] = roots[r]
    return out


def apply_terrace_budgets(plan: Optional[TerracePlan], shape_constraints,
                          node_xy) -> int:
    """Bind the plan into ``shape_constraints`` (spec §4).  Returns the
    number of law edges whose budget the joints relaxed.

    Also wraps any LAZY entry's ``lazy_expand`` thunk so the deferred body
    pairs come back already terrace-bound — the two-decimators lesson in
    a different costume: a second producer of the same edges must not be
    able to hand back an unbound set.
    """
    if plan is None or not plan.joints:
        return 0
    node_xy = _as_xy(node_xy)
    total = 0
    plan.stats["joint_step_pairs"] = 0
    plan.stats["facing_edges_excluded"] = 0
    plan.stats["facing_conformance_pairs"] = 0
    # Partner population for §3(c) conformance: every OTHER entry's nodes.
    # Built once (single-pass) and only when some apron actually faces.
    others = None
    if plan.facing_nodes:
        others = []
        for entry in shape_constraints:
            if entry.get("shape_id", -1) in plan.facing_nodes:
                continue
            for i in (entry.get("nodes") or ()):
                p = node_xy.get(i)
                if p is not None:
                    others.append((i, p[0], p[1]))
    for entry in shape_constraints:
        shape_id = entry.get("shape_id", -1)
        joints = plan.by_shape.get(shape_id) or []
        facing = plan.facing_nodes.get(shape_id) or set()
        if not joints and not facing:
            continue
        edges = entry.get("edges") or []
        if joints:
            # STRUCTURALLY VACUOUS SINCE THE PRE-SOLVE SPLIT, and kept
            # because vacuous-by-construction is the strongest form of
            # the guarantee: a panel's own edges cannot cross a joint —
            # the joint IS the panel's boundary — so there is nothing
            # within a shape left to relax, and therefore no facing node
            # that could be relaxed by accident.  The cross-joint law is
            # ``terrace_station_edges``.
            excl = [0]
            edges, touched = _rewrite_edges(edges, joints,
                                            node_xy, facing_nodes=facing,
                                            excluded_out=excl)
            plan.stats["facing_edges_excluded"] += excl[0]
        else:
            touched = 0
        # ── §3(c) CONFORMANCE ────────────────────────────────────────
        nodes = [i for i in (entry.get("nodes") or ())
                 if node_xy.get(i) is not None]
        if facing and others:
            conf = _facing_conformance_edges(facing, set(nodes), node_xy,
                                             others)
            if conf:
                edges = list(edges) + conf
                plan.stats["facing_conformance_pairs"] += len(conf)
        entry["edges"] = edges
        total += touched
        if nodes:
            plan.panels[shape_id] = _panel_components(
                nodes, edges, joints, node_xy)
            plan.node_sets[shape_id] = set(nodes)
        thunk = entry.get("lazy_expand")
        if thunk is not None:
            def _bound(_t=thunk, _j=joints, _xy=node_xy, _f=facing):
                return _rewrite_edges(list(_t()), _j, _xy,
                                      facing_nodes=_f)[0]
            entry["lazy_expand"] = _bound
    # ── THE ACTUAL-STEP BINDING joins the ONE solve ──────────────────
    # With the apron split BEFORE the solve, the two sides of a joint
    # are two shapes: no within-shape law generates the cross-joint
    # pair, so the declared step has to be handed over explicitly.  One
    # entry for the whole airport (the pairs are already per-joint), so
    # every projection that reads ``shape_constraints`` enforces it.
    st_edges = terrace_station_edges(plan)
    if st_edges and isinstance(shape_constraints, list):
        shape_constraints.append({
            "role": ROLE_APRON,
            "ref": "apron_terrace_joint",
            "shape_id": -1,
            "nodes": sorted({i for e in st_edges for i in e[:2]}),
            "edges": st_edges,
        })
        plan.stats["joint_step_pairs"] += len(st_edges)
        total += len(st_edges)
    return total


def apply_terrace_budgets_to_edges(plan: Optional[TerracePlan], edges,
                                   node_xy):
    """Bind the plan onto a RAW edge list — the unified graph's own
    ``u_edges``.

    ``solve``/``final_grade_projection`` project the unified graph's
    all-pair edges SEPARATELY from ``shape_constraints`` ("the EXACT
    pairs/caps the validator checks"), so a relief granted only in
    ``shape_constraints`` would be taken straight back by that second
    projection — the two-instruments trap in its edge-set costume.  One
    law, both edge sets.

    SCOPED BY NODE SET: only a pair whose BOTH endpoints belong to the
    panelized apron is eligible.  A chord from some other shape that
    happens to sail over the apron is NOT an apron pair and keeps its own
    law; relaxing it would be a law hole opened by geometry rather than
    by the ruling.  Returns ``(edges, n_relaxed)``.
    """
    if plan is None or not plan.joints or not edges:
        return edges, 0
    node_xy = _as_xy(node_xy)
    total = 0
    out = list(edges)
    for shape_id, joints in plan.by_shape.items():
        members = plan.node_sets.get(shape_id)
        if not members:
            continue
        scoped = []
        rest = []
        for e in out:
            if len(e) == 3 and e[0] in members and e[1] in members:
                scoped.append(e)
            else:
                rest.append(e)
        if not scoped:
            continue
        bound, touched = _rewrite_edges(
            scoped, joints, node_xy,
            facing_nodes=plan.facing_nodes.get(shape_id) or set())
        total += touched
        out = rest + bound
    # One law, both edge sets: the unified graph is projected separately
    # from ``shape_constraints``, so the actual-step binding has to ride
    # both or the second projection takes the relief straight back.
    st_edges = terrace_station_edges(plan)
    if st_edges:
        out = list(out) + st_edges
        total += len(st_edges)
    return out, total


# ────────────────────────────────────────────────────────────────────
# 5.  JOINT GEOMETRY — the declared step, as a wall, before interning
# ────────────────────────────────────────────────────────────────────

def _ring_values(shape):
    """Open exterior ring + aligned per-vertex values (the same
    derivation ``adjacent_ground._ring_values`` uses)."""
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty or poly.geom_type != "Polygon":
        return None
    try:
        coords = list(poly.exterior.coords)
    except _GEOM_EXC:
        return None
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return None
    alts = getattr(shape, "node_altitudes", None)
    if alts is not None:
        alts = list(alts)
        if len(alts) == len(coords) + 1:
            alts = alts[:-1]
        if len(alts) != len(coords):
            return None
        return coords, [float(a) for a in alts]
    if getattr(shape, "altitude", None) is not None:
        return coords, [float(shape.altitude)] * len(coords)
    return None


def _apron_ring_values(layout) -> dict:
    """``{canonical key: settled value}`` over every apron panel ring.

    THE IDENTITY READ.  After the pre-solve split a joint's ``hi``/``lo``
    stations ARE ring vertices of the two panels they separate, so the
    face's levels are a LOOKUP, not a reading: no flank window, no fit,
    no extrapolation, and no value the solve did not produce.  The key is
    the same decimetre spelling the canonical registry snaps at, so a
    vertex the split moved by float noise still resolves to itself.
    """
    out: dict = {}
    for s in getattr(layout, "shapes", ()):
        if s.role != ROLE_APRON:
            continue
        rv = _ring_values(s)
        if rv is None:
            continue
        coords, alts = rv
        for ((x, y), z) in zip(coords, alts):
            out[(round(x, 1), round(y, 1))] = float(z)
    return out


def _value_at(index: dict, xy):
    """The settled value at a station coordinate, or ``None``."""
    (x, y) = xy
    kx, ky = round(x, 1), round(y, 1)
    v = index.get((kx, ky))
    if v is not None:
        return v
    # One decimetre of slack in each direction: the difference op can
    # move a cut vertex by float noise, never by a real distance.
    for dx in (-0.1, 0.0, 0.1):
        for dy in (-0.1, 0.0, 0.1):
            v = index.get((round(kx + dx, 1), round(ky + dy, 1)))
            if v is not None:
                return v
    return None


def emit_terrace_joint_faces(layout, plan: Optional[TerracePlan]) -> int:
    """Mint one ``retaining_wall`` face per declared joint whose two
    panels actually settled at different levels.

    The face occupies the ``STACKED_WALL_RETREAT_M`` band BETWEEN the two
    panels — ground no apron polygon covers any more, because the split
    ran before the solve.  There is no lap and there is no
    emitter-assigned boundary value: every one of the face's own ring
    vertices is a panel ring vertex whose value the SOLVE produced, read
    here by identity.  EMITTERS EMIT, NEVER GRADE.

    Runway-strip fence (owner 2026-08-01, spec §5(d)): a face inside a
    runway strip footprint is inadmissible and is dropped here as well as
    flagged by the validator — walls at runway edges are NEVER lawful.
    The counter MUST read 0: plan-time admissibility proved every minted
    joint faceable before the apron was ever cut.
    """
    if plan is None or not plan.joints:
        return 0
    from auto_patch.adjacent_ground import runway_strip_wall_keepout
    from auto_patch.layout import BuiltShape
    keepout = runway_strip_wall_keepout(layout, require_gate=False)
    index = _apron_ring_values(layout)
    new_walls: list = []
    plan.stats["faces_dropped_keepout"] = 0
    plan.stats["joints_demoted_level"] = 0
    plan.stats.setdefault("station_readings", 0)
    plan.stats.setdefault("stations_over_bound", 0)
    plan.stats.setdefault("joints_sign_flipped", 0)
    plan.stats.setdefault("stations_unread", 0)
    for joint in plan.joints:
        if len(joint.hi) < 2 or len(joint.hi) != len(joint.lo):
            continue
        bound = float(joint.step_m) + APRON_MAX_GRADE * _RETREAT_TRIM_M
        rows: list = []                   # (k, s, z_hi, z_lo)
        for k, s_arc in enumerate(joint.grid or range(len(joint.hi))):
            if k >= len(joint.hi):
                break
            z_hi = _value_at(index, joint.hi[k])
            z_lo = _value_at(index, joint.lo[k])
            if z_hi is None or z_lo is None:
                plan.stats["stations_unread"] += 1
                continue
            rows.append((k, float(s_arc), z_hi, z_lo))
        if len(rows) < 2:
            continue
        plan.stats["station_readings"] += len(rows)
        drops = [abs(z_hi - z_lo) for (_k, _s, z_hi, z_lo) in rows]
        drop = max(drops)
        n_over = sum(1 for d in drops if d > bound)
        plan.stats["stations_over_bound"] += n_over
        n_flip = sum(1 for (_k, _s, z_hi, z_lo) in rows if z_hi < z_lo)
        if 0 < n_flip < len(rows):
            plan.stats["joints_sign_flipped"] += 1
        joint.flank_span_m = round(_RETREAT_TRIM_M, 3)
        joint.actual_step_m = round(float(drop), 4)
        joint.stations = [
            {"s": round(s_arc, 2), "z_pos": round(z_hi, 3),
             "z_neg": round(z_lo, 3), "span_m": _RETREAT_TRIM_M,
             "bound_m": round(bound, 4),
             "reader_slack_m": round(APRON_MAX_GRADE * _RETREAT_TRIM_M, 4),
             "over_m": round(max(0.0, abs(z_hi - z_lo) - bound), 4)}
            for (_k, s_arc, z_hi, z_lo) in rows]
        if drop <= 0.05:
            # The panels settled LEVEL — only knowable post-solve, so
            # this joint emits no face, and its sidecar allowance is
            # DEMOTED to the step the surface actually expresses (0 for
            # this class).  No unbacked relief survives the drop.
            plan.stats["joints_demoted_level"] += 1
            continue
        top = [joint.hi[k] for (k, _s, _zh, _zl) in rows]
        bot = [joint.lo[k] for (k, _s, _zh, _zl) in rows]
        ring = top + bot[::-1]
        try:
            wall_poly = Polygon(ring)
            if not wall_poly.is_valid:
                wall_poly = wall_poly.buffer(0)
            if wall_poly.is_empty or wall_poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:
            continue
        if keepout is not None:
            try:
                if wall_poly.intersects(keepout):
                    # LOUD COUNTER — this MUST read 0.  A hit means the
                    # plan-time predicate and this one diverged: a FRAME
                    # BUG.  The defence-in-depth drop stays (a wall in a
                    # strip is never lawful) and the allowance dies with
                    # it — the joint is demoted.
                    plan.stats["faces_dropped_keepout"] += 1
                    joint.actual_step_m = 0.0
                    continue
            except _GEOM_EXC:
                continue
        # The ring is built from the station rows VERBATIM, so the
        # altitudes align with it by construction — top row at the
        # upper panel's own value, bottom row at the lower panel's.
        alts = ([round(z_hi, 1) for (_k, _s, z_hi, _zl) in rows]
                + [round(z_lo, 1) for (_k, _s, _zh, z_lo) in rows][::-1])
        # ALIGNMENT IS CHECKED AGAINST THE POLYGON, not against the list
        # it was built from: ``buffer(0)`` may have repaired the ring and
        # changed its vertex count, and a misaligned ``node_altitudes``
        # ships vertices with no ``alt_abs`` at all (the EGGW
        # tunnel-plate collapse).  A face that cannot align is dropped
        # and counted, never shipped half-valued.
        try:
            _n_ring = len(list(wall_poly.exterior.coords)) - 1
        except _GEOM_EXC:
            continue
        if len(alts) != len(ring) or _n_ring != len(ring):
            plan.stats["faces_dropped_unaligned"] = (
                plan.stats.get("faces_dropped_unaligned", 0) + 1)
            continue
        new_walls.append(BuiltShape(
            polygon=wall_poly, role=ROLE_RETAINING_WALL,
            ref="apron_terrace_joint",
            node_altitudes=alts + [alts[0]]))
        joint.panel_lo = round(min(min(r[2], r[3]) for r in rows), 3)
        joint.panel_hi = round(max(max(r[2], r[3]) for r in rows), 3)
        joint.faced = True
    layout.shapes.extend(new_walls)
    plan.stats["faces_emitted"] = len(new_walls)
    return len(new_walls)



def terrace_joints_sidecar(layout) -> list:
    """``terrace_joints`` for ``<patch>.axes.json`` (spec §5).

    One row per declared joint: the polyline in lat/lon (11 decimals, the
    canonical identity spelling), the panel levels it separates and the
    declared step height.  Empty list with the gate off — the key is
    written unconditionally so a reader can distinguish "no joints" from
    "old patch"."""
    plan = getattr(layout, "_apron_terrace_plan", None)
    if plan is None or not getattr(plan, "joints", None):
        return []
    rows = []
    for j in plan.joints:
        try:
            pts = [list(layout.m_to_ll(x, y)) for (x, y) in j.line]
        except _GEOM_EXC:
            continue
        # ── §3(a) FACED-OR-NO-RELIEF ────────────────────────────────
        # A joint that emitted NO face grants exactly what the surface
        # expresses — its ACTUAL settled step (0 for the level class,
        # 0 when the emitter never reached it).  Before this, an unfaced
        # joint kept its full declared allowance: a budget relaxation
        # with no geometry behind it (HECA 17/118, KCLT 5/17, steps to
        # 1.889 m — the S1 in-strip joint among them).
        # NO FACE ⇒ NO RELIEF (the pre-registered hard zero: "sidecar
        # joints with step_m > 0 and no emitted face = 0").  Whatever the
        # flanks settled at, an allowance with no wall behind it is the
        # D1 defect itself — HECA carried 17 of 118, KCLT 5 of 17, steps
        # to 1.889 m, and the S1 in-strip joint was one of them.  The
        # actual settled step stays visible as a REPORT field.
        declared = float(j.step_m) if j.faced else 0.0
        rows.append({
            "points": [[round(la, 11), round(lo, 11)] for (la, lo) in pts],
            "step_m": round(declared, 4),
            "declared_step_m": round(float(j.step_m), 4),
            "faced": bool(j.faced),
            # REPORT FIELDS (never trusted by the validator — it
            # recomputes the actual step from the patch itself).
            "actual_step_m": (None if j.actual_step_m is None
                              else round(float(j.actual_step_m), 4)),
            "flank_span_m": j.flank_span_m,
            "panel_lo": j.panel_lo,
            "panel_hi": j.panel_hi,
            # ── D2 ──────────────────────────────────────────────────
            # The DENSIFIED panel boundary: one row per station, each
            # with the two levels the face was minted from, the reader
            # distance it had to cross and the law's own bound for that
            # distance (``step + cap·span``).  The validator recomputes
            # the step from the patch, but it judges against THIS bound
            # — lockstep, and the reader distance is part of the
            # declaration instead of being hidden inside it.
            "stations": j.stations,
            "reader_bound_m": (
                None if not j.stations
                else round(max(r["bound_m"] for r in j.stations), 4)),
        })
    return rows


def terrace_certificates_sidecar(layout) -> list:
    """``terrace_certificates`` for ``<patch>.axes.json`` (§2(a)).

    One row per PANELIZED apron carrying the evidence chain that
    authorised it: raw DEM-infeasible edge count, envelope excess, the
    steep-truth signature, the relief it certified and the line budget
    that relief bought.  The twin audits "certificate-free panelization
    = 0" and "lines ≤ evidence bound" from the patch alone."""
    plan = getattr(layout, "_apron_terrace_plan", None)
    if plan is None or not getattr(plan, "certificates", None):
        return []
    return [dict(row) for row in plan.certificates.values()]
