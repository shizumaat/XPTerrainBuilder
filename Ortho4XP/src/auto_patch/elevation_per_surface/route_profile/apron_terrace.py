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

0. ``construct_apron_terrace_presolve`` — the TRIGGER + the
   PANELIZATION, before the solve.  THE TRIGGER IS THE ANCHOR ENVELOPE
   (owner, RULINGS 4cbed92 — see ``_envelope_demand``): for every apron,
   the interval ``[floor, ceiling]`` the anchors + caps + route geometry
   confine each point to, and the worst pair whose intervals no single
   1 %-capped panel can span.  The shortfall IS the relief the declared
   steps discharge.  Terrace lines run along the ENVELOPE contour (the
   perpendicular to that pair's axis), cut out of the corridor cover.
   The steep-truth DEM signature that used to be the trigger is DEMOTED
   to report-only certificate provenance: the owner ruled DEM steepness
   the wrong quantity, and the measured consequence was that a flat-DEM
   world — which carries the SAME CIFP threshold spread and therefore
   the same terrace demand — fired zero terraces.
1. ``plan_apron_terraces`` — the BINDER.  Resolves that declaration into
   the solve's index space; it decides nothing.
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
    FAN_RAMP_CAP,
    GROUNDSIDE_MAX_GRADE,
    APRON_TERRACE_CORRIDOR_HALF_WIDTH_M,
    APRON_TERRACE_FACING_PROXIMITY_M,
    APRON_TERRACE_FACING_STEP_M,
    APRON_TERRACE_JOINT_CLEARANCE_M,
    APRON_TERRACE_MAX_STEP_M,
    APRON_TERRACE_MIN_EXCESS_M,
    APRON_TERRACE_MIN_JOINT_LEN_M,
)

_GEOM_EXC = (ValueError, GEOSException, TopologicalError, AttributeError)

__all__ = [
    "construct_apron_terrace_presolve",
    "plan_apron_terraces",
    "terrace_station_edges",
    "apply_terrace_budgets",
    "emit_terrace_joint_faces",
    "terrace_joints_sidecar",
    "terrace_certificates_sidecar",
    "FanRampPlan",
    "FAN_RAMP_CAP",
    "plan_fan_ramp_zones",
    "split_aprons_at_fan_zones",
    "apply_fan_ramp_caps",
    "apply_fan_ramp_caps_to_edges",
    "fan_ramp_zones_sidecar",
    "rebind_terrace_stations",
    "runway_strip_keepout_geometry",
    "TerraceJoint",
    "TerracePlan",
    "TerraceStation",
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

# ── THE ANCHOR-ENVELOPE TRIGGER (RULINGS 4cbed92) ───────────────────
# The pair scan is quadratic in the sample count, so the sample count is
# bounded.  240 samples = 28 800 ordered pairs per apron, one numpy
# outer difference — sub-millisecond, and dense enough that a thinned
# ring moves the worst pair by well under the 0.01 m materiality floor.
_ENVELOPE_SAMPLE_MAX = 240
# A pair closer together than this cannot license a terrace: the joint
# and its wall band would not fit between them, so an "excess" read at
# that separation is instrument noise, not relief a panel boundary can
# discharge.  Sized at the minimum joint length.
_ENVELOPE_MIN_CHORD_M = 8.0
# A sample whose band is inverted by more than this is DROPPED from the
# pair scan and counted (see ``_envelope_demand``).  Read from the band
# law's own materiality floor so the trigger and the loud FINAL-band
# assert can never disagree about what "inverted" means.
try:
    from auto_patch.elevation_per_surface.building_feasibility import (
        FINAL_BAND_INVERSION_TOL_M as _BAND_INVERSION_TOL_M)
except ImportError:                                        # pragma: no cover
    _BAND_INVERSION_TOL_M = 0.01
_INF_POS = float("inf")
_INF_NEG = float("-inf")
_UNSET_ZONE = object()
# The demand-margin histogram's upper edges (metres).  Everything at or
# above ``APRON_TERRACE_MIN_EXCESS_M`` fired; the negative bins are what
# says whether an apron that did not fire was NEAR firing (the trigger is
# mis-scaled) or nowhere near it (the anchors are not the author of that
# apron's grade rows).
_DEMAND_MARGIN_BINS = (-100.0, -30.0, -10.0, -3.0, -1.0, -0.25, 0.0, 0.25,
                       1.0, 3.0, 10.0)


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


def _joint_bound_m(joint) -> float:
    """THE declared-step bound for one joint — ONE formula, three readers.

    ``step + cap·retreat``: a wall may be as tall as the step it declares
    plus the ordinary cap over the face's OWN width, never as tall as the
    distance its reader had to travel.  The solve binding
    (:func:`terrace_station_edges`), the emit-time residue counter
    (:func:`emit_terrace_joint_faces`) and the sidecar's
    ``reader_bound_m`` all read THIS function, so the number the solve
    enforced and the number the validator judges against cannot drift.
    """
    from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
    return float(joint.step_m) + APRON_MAX_GRADE * STACKED_WALL_RETREAT_M


class TerraceStation:
    """ONE station on a declared joint's densified panel boundary.

    THE SINGLE REPRESENTATION (fix 2026-08-05).  Before this class the
    same attribute ``TerraceJoint.stations`` carried TWO shapes: the bind
    pass left 4-tuples ``(k, s, i_hi, i_lo)`` and the face emitter
    REPLACED the list with dicts.  Every joint the emitter returned from
    early (too few rows, unreadable levels) therefore reached
    ``terrace_joints_sidecar`` still holding tuples, where ``r["bound_m"]``
    raised ``TypeError`` — and ``layout._write_axes_sidecar``'s bare
    ``except`` dropped the WHOLE sidecar.  Measured cost: 3 of HEAZ's 13
    joints, 6 of HECA's 79, and with the sidecar gone every census
    silently degraded to the context-free check (SPJC read 4,010 rows
    instead of 810).  One class, minted once, enriched in place: the two
    shapes are now unrepresentable.

    The BINDING half (``k``/``s``/``i_hi``/``i_lo``/``bound_m``) is known
    at plan time and is always present.  The READING half
    (``z_pos``/``z_neg``) is filled by the face emitter and stays ``None``
    on a station no face ever read — an honest null, not an absence.
    """

    __slots__ = ("k", "s", "i_hi", "i_lo", "bound_m", "span_m",
                 "z_pos", "z_neg")

    def __init__(self, k: int, s: float, i_hi, i_lo, bound_m: float,
                 span_m: float):
        self.k = int(k)
        self.s = float(s)
        # Solve-space node indices — meaningful ONLY inside the
        # ``_build_node_list`` call they were resolved in (see
        # :func:`rebind_terrace_stations`).  They never leave the
        # process: :meth:`as_row` does not serialise them.
        self.i_hi = i_hi
        self.i_lo = i_lo
        self.bound_m = float(bound_m)
        self.span_m = float(span_m)
        self.z_pos: Optional[float] = None
        self.z_neg: Optional[float] = None

    @property
    def bound(self) -> bool:
        """Did this station resolve to two distinct solve variables?"""
        return (self.i_hi is not None and self.i_lo is not None
                and self.i_hi != self.i_lo)

    @property
    def read(self) -> bool:
        """Did the face emitter read a settled level on both sides?"""
        return self.z_pos is not None and self.z_neg is not None

    @property
    def over_m(self) -> float:
        """Metres this station's settled step exceeds its own bound."""
        if not self.read:
            return 0.0
        return max(0.0, abs(self.z_pos - self.z_neg) - self.bound_m)

    def as_row(self) -> dict:
        """The ``<patch>.axes.json`` D2 row (spec §5).

        Solve-space indices are deliberately absent: a node index carried
        outside its own index space binds the wrong vertex (the rod-key
        lesson), so the sidecar carries GEOMETRY and LEVELS only.
        """
        from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
        return {
            "s": round(self.s, 2),
            "z_pos": None if self.z_pos is None else round(self.z_pos, 3),
            "z_neg": None if self.z_neg is None else round(self.z_neg, 3),
            "span_m": self.span_m,
            "bound_m": round(self.bound_m, 4),
            "reader_slack_m": round(
                APRON_MAX_GRADE * STACKED_WALL_RETREAT_M, 4),
            "over_m": round(self.over_m, 4),
        }


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
        # binding and the face emitter).  Every entry is a
        # :class:`TerraceStation` — ONE representation for the whole
        # lifetime: minted bound at plan time, enriched with the settled
        # levels by the face emitter, serialised by ``as_row``.
        # The face is then read and BOUNDED per station, in the law's
        # own frame — ``step + cap·retreat`` — instead of one
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
            # ── THE DEMAND CENSUS (fix cycle 2, item 3) ─────────────
            # Mirrored from the pre-solve construction.  "0 joints" is
            # only a PASS when ``candidates_demanded`` is also 0; with a
            # demand standing and nothing fired it is a defect, and no
            # reader can tell those apart without these counters.
            "candidates_demanded": 0, "candidates_under_floor": 0,
            "demand_total_m": 0.0, "demand_worst_m": 0.0,
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

    TWO EXCLUSIONS, and both are structural: a SIBLING PANEL of the same
    terrace declaration is not a neighbour.  Two panels split apart by a
    declared joint stand 0.6 m from each other by construction, so the
    facing law would read the DECLARED step as an undeclared one and
    conform it away — the two clauses would be fighting over the same
    ground.  The joint's own step edge governs there, and nothing else.

    The FAN-RAMP split (``split_aprons_at_fan_zones``) makes the same
    claim for a different reason.  Its pieces are FLUSH — they share the
    cut's vertices, so they share solver nodes and cannot step — but the
    cut runs the whole length of the ramp, so without this every
    remainder panel would "face" its own ramp along that entire line, the
    joint clearance would fence the apron off from itself, and the
    terrace law would be suppressed on exactly the aprons the ramp law
    just declared.  A piece of one declaration is not the neighbour of
    another piece of it.
    """
    from auto_patch.config import ROLE_GRADE_LIMITS
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return []
    group = getattr(shape, "_terrace_panel_group", None)
    fan_group = getattr(shape, "_fan_panel_group", None)
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
        if (fan_group is not None
                and getattr(s, "_fan_panel_group", None) == fan_group):
            continue                      # fan-ramp sibling — see above
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
#   1. THE TRIGGER IS THE ANCHOR ENVELOPE (owner, RULINGS 4cbed92 —
#      SUPERSEDES the DEM + geometry reading this slot used to describe).
#      The distinction that matters is WHOSE envelope.  The retired
#      mid-solve trigger ran the envelope over THE SOLVE'S CURRENT
#      VALUES, and under RULINGS 5578b6a an excess there is a defect
#      report about the law or the instrument, never a licence — a
#      terrace bought with a wrong value buries the defect.  What is read
#      here is the PRE-SOLVE ANCHOR envelope: hard anchor values, per-edge
#      caps and route geometry, no solved value anywhere, so there is no
#      value defect available for it to launder.  The DEM-plane reading
#      that briefly replaced it is demoted to certificate provenance; its
#      measured cost was total blindness in the flat-DEM oracle worlds,
#      which carry the full CIFP anchor tension and therefore the full
#      terrace demand.
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


def _apron_sample_points(polygon):
    """The apron's own sample set: ring vertices plus a coarse interior
    grid, decimated to :data:`_ENVELOPE_SAMPLE_MAX`.

    The ring ALONE can be degenerate (a long thin apron's vertices are
    nearly collinear), and the interior is where a route crossing the
    apron puts its own envelope — so both are sampled.  ONE sampler for
    the envelope trigger and the report-only DEM plane, so the
    certificate's two readings can never be talking about different
    ground.
    """
    try:
        ring = _open_ring_xy(polygon)
    except _GEOM_EXC:
        return []
    if len(ring) < 3:
        return []
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
    if len(pts) > _ENVELOPE_SAMPLE_MAX:
        # Uniform stride, endpoints kept.  The envelope is a ROUTE metric
        # and the DEM plane is a least-squares fit; neither reads a single
        # vertex, so thinning a dense ring changes the answer by less than
        # the materiality floor while keeping the pair scan quadratic in a
        # bounded number.
        stride = int(math.ceil(len(pts) / float(_ENVELOPE_SAMPLE_MAX)))
        pts = pts[::stride]
    return [(float(x), float(y)) for (x, y) in pts]


def _apron_dem_plane(polygon, sample_dem):
    """``((gx, gy), slope)`` for one apron polygon, from the DEM alone.

    REPORT-ONLY PROVENANCE (RULINGS 4cbed92).  This reading used to BE
    the trigger; the owner ruled DEM steepness the wrong quantity, so it
    now only travels in the certificate beside the envelope evidence that
    does the deciding.  Kept because it is the honest answer to "what did
    the ground under this apron look like", which is worth having next to
    "and this is why the law terraced it".
    """
    if sample_dem is None:
        return None
    pts = _apron_sample_points(polygon)
    if len(pts) < 3:
        return None
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


def _envelope_demand(polygon, envelope, cap: float, fan=None):
    """THE TRIGGER READING — the worst ANCHOR-ENVELOPE INFEASIBILITY
    inside one apron, or ``None`` where the apron is feasible as one
    panel.

    THE LAW (owner, RULINGS 4cbed92).  A terrace is licensed by what the
    ANCHORS demand, not by what the DEM does: "triggers derive from
    ANCHOR-ENVELOPE INFEASIBILITY (hard values + caps + geometry),
    identical in flat and real worlds".  The envelope IS the interval the
    projection enforces at every point — ``floor(p) = max over anchors
    (v_a − route budget a→p)``, ``ceiling(p) = min over anchors (v_a +
    route budget a→p)`` — the same two fields
    ``building_feasibility.spine_value_fields`` computes and the FINAL
    band assert judges.

    One capped surface can hold two points ``k`` and ``m`` iff some pair
    of admissible values is within the cap's own allowance over the chord
    between them::

        min |z_k − z_m|  =  max(0, L_k − U_m, L_m − U_k)   ≤   cap · d_km

    so the SHORTFALL — the relief no single lawful panel can absorb, and
    exactly the relief a declared joint step exists to discharge — is

        excess = max over pairs ( L_k − U_m − cap·d_km )

    Returns ``{"excess_m", "hi", "lo", "floor_hi", "ceiling_lo",
    "chord_m", "allowance_m", "gdir", "samples"}``.  ``gdir`` is the unit
    direction of steepest ENVELOPE ascent (low point → high point): the
    contour perpendicular to it is where a joint belongs, the same role
    the DEM gradient used to play.

    NOTE the asymmetry of the scan: ``L_k − U_m`` is evaluated over ALL
    ORDERED pairs, so ``L_m − U_k`` is the same scan with ``k`` and ``m``
    swapped and needs no separate term.
    """
    try:
        import numpy as _np
    except ImportError:                                    # pragma: no cover
        return None
    pts = _apron_sample_points(polygon)
    if len(pts) < 2:
        return None
    xs, ys, los, his = [], [], [], []
    n_inverted = 0
    for (x, y) in pts:
        try:
            b = envelope(x, y)
        except _GEOM_EXC:                                  # pragma: no cover
            b = None
        if b is None:
            continue
        try:
            lo_v, hi_v = float(b[0]), float(b[1])
        except (TypeError, ValueError, IndexError):        # pragma: no cover
            continue
        if lo_v != lo_v or hi_v != hi_v:
            continue
        if lo_v in (_INF_NEG, _INF_POS) or hi_v in (_INF_NEG, _INF_POS):
            continue
        if lo_v - hi_v > _BAND_INVERSION_TOL_M:
            # AN INVERTED BAND IS A DEFECT REPORT, NEVER A LICENCE
            # (RULINGS 5578b6a).  ``floor > ceiling`` at ONE point means
            # two anchors contradict each other through the route between
            # them — no elevation satisfies that point at all, and a
            # terrace cannot add budget to a route it is forbidden to
            # cross.  Reading it as apron relief would launder a law
            # defect into lawful-looking geometry, which is exactly what
            # the ruling forbids.  Measured: HECA's canyon world put
            # NEGATIVE median band width (down to −9.5 m) under five of
            # its ten largest aprons, and the unguarded scan turned every
            # one of them into terrace demand.
            n_inverted += 1
            continue
        xs.append(x)
        ys.append(y)
        los.append(lo_v)
        his.append(hi_v)
    n = len(xs)
    if n < 2:
        return {"excess_m": float("-inf"), "samples": n,
                "samples_offnet": len(pts) - n - n_inverted,
                "samples_inverted": n_inverted, "width_p50_m": None,
                "hi": None, "lo": None, "chord_m": 0.0}
    X = _np.asarray(xs, dtype=float)
    Y = _np.asarray(ys, dtype=float)
    L = _np.asarray(los, dtype=float)
    U = _np.asarray(his, dtype=float)
    D = _np.hypot(X[:, None] - X[None, :], Y[:, None] - Y[None, :])
    M = (L[:, None] - U[None, :]) - float(cap) * D
    if fan is not None and getattr(fan, "zones", None):
        # RAMPS FIRST (owner answer 2).  A pair whose two ends lie in ONE
        # fan-ramp zone is allowed the ZONE's cap, so what survives this
        # scan is exactly the relief 5 % could not span — which is what
        # the wall/step fallback is FOR.  Precedence lives here, in the
        # one trigger reading, rather than in a second pass that could
        # disagree with it.
        #
        # ONE polygon test PER SAMPLE, then the pair rule is an array
        # comparison: the per-pair form was n² prepared-geometry calls
        # per apron and it cost HECA's plateau build minutes.
        zid = _np.asarray([fan.zone_of(px, py) for (px, py) in zip(xs, ys)],
                          dtype=int)
        if (zid >= 0).any():
            caps = _np.asarray(fan.zone_caps(), dtype=float)
            same = (zid[:, None] == zid[None, :]) & (zid[:, None] >= 0)
            if same.any():
                zc = _np.where(zid >= 0, caps[_np.clip(zid, 0, None)],
                               float(cap))
                M = _np.where(same,
                              (L[:, None] - U[None, :])
                              - zc[:, None] * D, M)
    _np.fill_diagonal(M, -_np.inf)
    M[D < _ENVELOPE_MIN_CHORD_M] = -_np.inf
    k, m = _np.unravel_index(int(_np.argmax(M)), M.shape)
    excess = float(M[k, m])
    chord = float(D[k, m])
    dx, dy = X[k] - X[m], Y[k] - Y[m]
    norm = math.hypot(dx, dy)
    # THE MARGIN IS ALWAYS REPORTED, including when it is negative.  A
    # NEGATIVE margin is the honest statement "the anchors permit a
    # lawful single panel here", and telling that apart from "the band
    # could not be read" is the whole difference between a law that did
    # not have to fire and an instrument that went blind.
    out = {
        "excess_m": excess,
        "hi": (float(X[k]), float(Y[k])),
        "lo": (float(X[m]), float(Y[m])),
        "floor_hi": float(L[k]),
        "ceiling_lo": float(U[m]),
        "chord_m": chord,
        "allowance_m": float(cap) * chord,
        "gdir": ((dx / norm, dy / norm) if norm > 1e-9 else None),
        "samples": n,
        "samples_offnet": len(pts) - n - n_inverted,
        "samples_inverted": n_inverted,
        "width_p50_m": float(_np.median(U - L)),
        "span_m": float(D.max()),
    }
    if norm < 1e-9:                                        # pragma: no cover
        out["excess_m"] = float("-inf")
    return out


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

    envelope, anchors = presolve_anchor_envelope(layout, icao=icao)
    if envelope is None:
        layout.apron_terrace_presolve_stats = {
            "candidates": 0, "triggered": 0, "joints": 0,
            "no_envelope": 1}
        return 0
    return _construct_from_envelope(layout, envelope, sample_dem=sample_dem,
                                    icao=icao, anchors=anchors)


def presolve_anchor_envelope(layout, icao: str = ""):
    """``(envelope, anchors)`` — THE anchor envelope, computed PRE-SOLVE,
    exactly as the FINAL band assert computes it.

    ``envelope(x, y) -> (floor, ceiling) | None`` is
    ``building_feasibility.reach_band_unified`` on the unified grade
    graph: the interval the projection confines every solved pavement
    node to, from the hard anchor values, the per-edge caps and the route
    geometry — and nothing else.  It is a pure function of geometry +
    CIFP anchors, none of which the solve has moved yet (the same
    argument ``adjacent_ground._build_construct_reach_band`` makes for
    its own pre-solve band), so it is computable here.

    ``anchors(x, y, side) -> (anchor_node, anchor_value, route_budget) |
    None`` resolves a point to the anchor that authored its ``"floor"``
    or its ``"ceiling"``, via the nearest SPINE node — the certificate's
    evidence, read off the provenance the band build already published.

    Returns ``(None, None)`` on any failure: no envelope means no
    licensed terrace, which is the conservative answer (a build that
    cannot compute the demand must not invent one).

    COST, stated honestly: one extra ``_build_node_list`` +
    ``build_unified_graph`` + band build before the solve.  It is not
    shared with the construct band in ``adjacent_ground`` because THIS
    pass changes ``layout.shapes`` (it splits aprons into panels), so
    that one is built on different geometry by construction.
    """
    try:
        from auto_patch import grade_graph as _GG
        from auto_patch.elevation_per_surface.building_feasibility import (
            reach_band_unified)
        from auto_patch.elevation_per_surface.solver_primitives import (
            _build_node_list)
        _nodes, bucket_to_idx = _build_node_list(layout)
        ctx = _GG.build_context(layout, bucket_to_idx)
        G = _GG.build_unified_graph(layout, bucket_to_idx, ctx=ctx)
        band = reach_band_unified(layout, G)
    except Exception as _env_exc:                          # pragma: no cover
        try:
            import O4_UI_Utils as _UI
            _UI.vprint(1, f"  [apron-terrace] {icao}: the pre-solve ANCHOR "
                          f"ENVELOPE could not be built ({_env_exc!r}) — no "
                          f"terrace is licensed this build (the trigger is "
                          f"the envelope; there is no DEM fallback).")
        except Exception:                                  # pragma: no cover
            pass
        return None, None
    return band, _anchor_resolver(layout, G)


def _anchor_resolver(layout, G):
    """``(x, y, side) -> (anchor_node, anchor_value, route_budget)`` via
    the nearest spine node, or ``None`` when no provenance was published.
    """
    prov = getattr(layout, "_band_anchor_provenance", None)
    if not prov:
        return None
    pos = getattr(G, "pos", None) or {}
    spine = getattr(G, "spine_adj", None) or {}
    keys = [i for i in spine if i in pos]
    if not keys:
        return None
    try:
        import numpy as _np
        P = _np.asarray([pos[i] for i in keys], dtype=float)
    except Exception:                                      # pragma: no cover
        return None
    idx = _np.asarray(keys, dtype=int)
    values = prov.get("anchor_value") or {}

    def _resolve(x, y, side):
        d2 = (P[:, 0] - float(x)) ** 2 + (P[:, 1] - float(y)) ** 2
        node = int(idx[int(_np.argmin(d2))])
        row = (prov.get(side) or {}).get(node)
        if row is None:
            return None
        anchor, budget = int(row[0]), float(row[1])
        return (anchor, float(values.get(anchor, float("nan"))), budget)

    return _resolve


def _fan_for(fan, shape):
    """The fan plan restricted to ONE apron, or ``None``.

    The trigger asks about one apron at a time, and a zone belonging to a
    different apron must never license a pair here — the ground between
    two aprons is not inside either one's zone."""
    if fan is None or not getattr(fan, "zones", None):
        return None
    zones = fan.by_shape.get(id(shape))
    if not zones:
        return None
    sub = FanRampPlan()
    for z in zones:
        sub.add(id(shape), z)
    return sub


def _construct_from_envelope(layout, envelope, sample_dem=None,
                             icao: str = "", anchors=None,
                             fan=None) -> int:
    """:func:`construct_apron_terrace_presolve` with the ANCHOR ENVELOPE
    already resolved to an ``(x, y) -> (floor, ceiling) | None`` callable.

    Split out so the twins drive the REAL panelizer against an analytic
    envelope instead of a second implementation — one panelizer, one
    population, which is the whole reason the mid-solve one was retired.
    A PINNED envelope (``floor == ceiling`` tracking a plane) reduces the
    pair scan to ``(slope − cap)·extent`` exactly, so a twin written
    against the retired DEM-plane trigger keeps its numbers.
    """
    from auto_patch.adjacent_ground import (STACKED_WALL_RETREAT_M,
                                            runway_strip_wall_keepout)
    from auto_patch.layout import BuiltShape
    layout.apron_terrace_presolve = []
    stats = {"candidates": 0, "triggered": 0, "joints": 0,
             # ── THE DEMAND CENSUS (item 3, fix cycle 2) ─────────────
             # "0 joints" is two different worlds and the twins have to
             # be able to tell them apart: NOBODY ASKED (no apron's
             # envelope is infeasible — the surface is lawful as one
             # panel) versus ASKED AND NOTHING FIRED (the demand exists
             # and the panelizer answered none of it, which is a defect).
             "candidates_demanded": 0, "candidates_under_floor": 0,
             "candidates_no_band": 0,
             "demand_total_m": 0.0, "demand_worst_m": 0.0,
             "env_samples": 0, "env_samples_offnet": 0,
             "env_samples_inverted": 0,
             "margin_hist": {}, "biggest": [],
             "joints_stillborn_keepout": 0, "joints_stillborn_hole": 0,
             "joint_pieces_dropped_short": 0,
             "joint_lines_lost_to_corridor": 0,
             "polygons_split": 0, "split_pieces_added": 0,
             # Cycle-5 node identity: joint stations moved onto the
             # settled lattice before the band / the difference.
             "cut_vertices_snapped": 0}
    cover = corridor_cover(layout)
    # ── THE FAN-RAMP ZONES, BEFORE THE TERRACES (owner 21f0980) ──────
    # Precedence, structurally: the zones exist before a single terrace
    # line is cut, so the trigger's allowance already carries the 5 %
    # the ramp grants and the wall answers only what is left.
    fan = plan_fan_ramp_zones(layout, cover, icao=icao)
    # ── AND THE ZONES BECOME SHAPES, BEFORE ANY TERRACE LINE IS CUT ──
    # Precedence is now geometric as well as arithmetic: the ramp ground
    # has left the apron by the time the terrace trigger reads the
    # apron's envelope demand, so the shortfall a wall is asked to
    # discharge is the shortfall over the ground that is STILL held to
    # 1 % — the ruled "ramps first, wall fallback", with no second pass.
    split_aprons_at_fan_zones(layout, fan, icao=icao, cover=cover)
    layout._fan_ramp_plan = fan
    try:
        keepout = runway_strip_wall_keepout(layout, require_gate=False)
    except (ImportError, AttributeError, *_GEOM_EXC):
        keepout = None
    # A declared RAMP piece is not a terrace candidate: the relief on
    # that ground is the ramp, and a wall inside a ramp is not the law
    # (owner answer 2 — the wall is the FALLBACK for what 5 % could not
    # span, and 5 % is what this piece already holds).
    aprons = [s for s in list(getattr(layout, "shapes", ()))
              if s.role == ROLE_APRON and s.polygon is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"
              and not getattr(s, "fan_ramp_zone", False)]
    # THE SETTLED LATTICE, READ AFTER THE FAN SPLIT (cycle-5 node
    # identity): the fan cut already ran, so its pieces are part of the
    # settled set this cut must be born on.  One build for the whole
    # pass; each panel cut adds what it minted (``_panelize_apron`` ->
    # ``_snap_stations``).
    from auto_patch.canonical_points import (
        add_polygon_to_lattice as _add_to_lattice,
        settled_vertex_lattice as _settled_lattice)
    lattice = _settled_lattice(layout)
    new_shapes: list = []
    for shape in aprons:
        stats["candidates"] += 1
        try:
            entry = _panelize_apron(layout, shape, cover, keepout,
                                    envelope, STACKED_WALL_RETREAT_M,
                                    stats, sample_dem=sample_dem,
                                    anchors=anchors, fan=fan,
                                    lattice=lattice)
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
        # The panels this cut minted JOIN the lattice, so the NEXT
        # apron's joint stations snap to them too.
        for _p in panels:
            _add_to_lattice(_p, lattice)
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
    if (stats["joints"] or stats["candidates_demanded"]
            or _os.environ.get("O4_STEP_DEBUG") == "1"):
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [apron-terrace] {icao}: PRE-SOLVE panelization — "
            f"{stats['candidates']} apron candidate(s), "
            f"{stats['candidates_demanded']} with an ANCHOR-ENVELOPE "
            f"demand (worst {stats['demand_worst_m']:.3f} m, total "
            f"{stats['demand_total_m']:.2f} m; "
            f"{stats['candidates_under_floor']} under the "
            f"{APRON_TERRACE_MIN_EXCESS_M:g} m floor), "
            f"{stats['triggered']} panelized into "
            f"{stats['triggered'] + stats['split_pieces_added']} panel(s), "
            f"{stats['joints']} declared joint(s); stillborn "
            f"{stats['joints_stillborn_keepout']} unfaceable / "
            f"{stats['joints_stillborn_hole']} would punch a hole; "
            f"pieces dropped short {stats['joint_pieces_dropped_short']}, "
            f"lines lost to the corridor cover "
            f"{stats['joint_lines_lost_to_corridor']}; "
            f"{stats['cut_vertices_snapped']} joint station(s) snapped "
            f"onto the settled lattice before the cut")
        _UI.vprint(1,
            f"  [apron-terrace] {icao}: DEMAND CENSUS — envelope samples "
            f"{stats['env_samples']} ({stats['env_samples_offnet']} off-net, "
            f"{stats['env_samples_inverted']} DROPPED for an inverted band "
            f"— a defect report, never a licence), "
            f"{stats['candidates_no_band']} apron(s) with no readable band; "
            f"margin histogram (m, upper edge -> aprons) "
            f"{ {k: v for k, v in sorted(stats['margin_hist'].items(), key=lambda kv: (kv[0] == 'over', kv[0]))} }")
        for (area, margin, span, width, n) in stats["biggest"]:
            _UI.vprint(1,
                f"  [apron-terrace]   largest apron {area:,.0f} m²: margin "
                f"{margin:+.3f} m over a {span:.0f} m span, band width p50 "
                f"{width} m, {n} sample(s)")
    return stats["joints"]


def _census_demand(stats, poly, demand) -> None:
    """One row of the PER-APRON demand census, and the ten largest
    aprons the envelope did NOT license.

    The whole reason this exists: after the re-keying, HECA's plateau
    world showed 12 of 213 aprons demanding relief while the census
    carried 10 430 within-apron grade rows.  "The trigger under-fires"
    and "the envelope is not the author of those rows" predict the same
    joint count and want opposite fixes, and only the MARGIN
    distribution separates them — an apron sitting at −0.2 m says the
    law nearly fired, one at −40 m says the anchors were never the
    reason that apron is out of grade.
    """
    n = int(demand.get("samples") or 0)
    stats["env_samples"] += n
    stats["env_samples_offnet"] += int(demand.get("samples_offnet") or 0)
    stats["env_samples_inverted"] += int(demand.get("samples_inverted") or 0)
    if n < 2:
        stats["candidates_no_band"] += 1
        return
    margin = float(demand["excess_m"])
    if margin != margin or margin == float("-inf"):         # pragma: no cover
        return
    for edge in _DEMAND_MARGIN_BINS:
        if margin < edge:
            stats["margin_hist"][edge] = (
                stats["margin_hist"].get(edge, 0) + 1)
            break
    else:
        stats["margin_hist"]["over"] = stats["margin_hist"].get("over", 0) + 1
    try:
        area = float(poly.area)
    except _GEOM_EXC:                                      # pragma: no cover
        area = 0.0
    stats["biggest"].append(
        (area, round(margin, 3), round(float(demand.get("span_m") or 0.0), 1),
         (None if demand.get("width_p50_m") is None
          else round(float(demand["width_p50_m"]), 2)), n))
    stats["biggest"].sort(key=lambda r: -r[0])
    del stats["biggest"][10:]


def _panelize_apron(layout, shape, cover, keepout, envelope,
                    retreat: float, stats, sample_dem=None,
                    anchors=None, fan=None, lattice=None):
    """One apron: trigger, cut, split.  ``None`` when it does not fire.

    Returns the presolve entry with an extra ``_panels`` key (the panel
    polygons, largest first) that the caller pops.

    ``lattice`` — the SETTLED VERTEX LATTICE (cycle-5 node identity,
    ``docs/specs/cycle5-node-identity-spec.md``).  Like the fan-ramp
    split, this cut runs after ``pipeline._unify_airside_geometry``
    settled the airside node set, so the joint's station rows are
    snapped onto it BEFORE the band is built and the difference taken:
    the band, the declaration's ``hi``/``lo`` rows and the panel
    boundary are then one geometry on one node set.  Snapping the
    STATIONS rather than the band polygon is what keeps them in
    lockstep — a band snapped on its own would publish station rows the
    cut no longer follows.
    """
    poly = shape.polygon
    # ── THE TRIGGER: the ANCHORS' demand (RULINGS 4cbed92) ───────────
    # An apron whose own anchor envelope is infeasible under the apron
    # cap cannot be one panel, and the shortfall IS the relief the
    # declared steps discharge.  Identical in a flat world and a real one
    # — which is the whole reason the DEM-steepness reading it replaces
    # was ruled the wrong quantity: the flat worlds carry the same CIFP
    # threshold spread, so they carry the same terrace demand, and a
    # DEM-keyed trigger went blind in exactly the world the oracle
    # measures in.
    demand = _envelope_demand(poly, envelope, APRON_MAX_GRADE,
                              fan=_fan_for(fan, shape))
    if demand is None:
        stats["candidates_no_band"] += 1
        return None
    _census_demand(stats, poly, demand)
    envelope_excess = demand["excess_m"]
    if envelope_excess < APRON_TERRACE_MIN_EXCESS_M:
        if envelope_excess > 0.0:
            stats["candidates_under_floor"] += 1
        return None
    # COUNTED HERE, BEFORE ANY GEOMETRY CAN DROP IT: an apron the anchors
    # demanded relief on stays in the demand census even if every joint
    # it would have carried turns out stillborn.  That difference —
    # demanded minus triggered — is the only thing that distinguishes "no
    # apron asked" from "the panelizer answered nothing".
    stats["candidates_demanded"] += 1
    stats["demand_total_m"] += envelope_excess
    stats["demand_worst_m"] = max(stats["demand_worst_m"], envelope_excess)
    gdir = demand["gdir"]
    extent = _extent_along(poly, gdir)
    # REPORT-ONLY PROVENANCE: what the ground did, recorded beside what
    # the anchors demanded.  It decides nothing (§ the ruling).
    plane = _apron_dem_plane(poly, sample_dem)
    plane_slope = (None if plane is None else float(plane[1]))
    dem_geom_excess = (None if plane is None else
                       max(0.0, (plane_slope - APRON_MAX_GRADE)
                           * _extent_along(poly, plane[0])))
    joint_count = max(1, int(math.ceil(envelope_excess
                                       / APRON_TERRACE_MAX_STEP_M)))
    step_m = min(APRON_TERRACE_MAX_STEP_M, envelope_excess / joint_count)
    # §3(c): joint lines keep the joint clearance from FACING boundary
    # runs, so no joint discharges its step at a neighbour's face.
    facing, _nb = _facing_boundary(layout, shape)
    # SAME RULING as the fan zone: the geometry a CUT is taken against
    # must be lattice-coarse, or the joint pieces are born carrying the
    # cover's buffer-arc vertex pairs.  The fence is a buffer too, so
    # the coarsening is applied to the UNION, once, after it is built.
    cut_cover = cover
    if facing is not None and not facing.is_empty:
        try:
            fence = facing.buffer(APRON_TERRACE_JOINT_CLEARANCE_M)
            cut_cover = (fence if cut_cover is None
                         else unary_union([cut_cover, fence]))
        except _GEOM_EXC:
            pass
    true_cut_cover = cut_cover
    if cut_cover is not None and not cut_cover.is_empty:
        cut_cover = lattice_coarse_cover(cut_cover)
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
            # ── ONTO THE SETTLED LATTICE, BEFORE THE BAND ────────────
            # A station within the canonical weld tolerance of a settled
            # vertex IS that node.  Row LENGTHS are preserved (``grid``
            # is index-aligned with them); two stations that snap to one
            # point are one node, and ``_band_polygon``'s validity
            # repair handles the zero-length edge that leaves.
            if lattice is not None:
                # The keep-out guard binds against the TRUE cover — the
                # zero-tolerance structural law (ruling §1); the coarse
                # superset is only what the cut is SHAPED by.
                _ko = None
                try:
                    if (true_cut_cover is not None
                            and not true_cut_cover.is_empty):
                        _ko = true_cut_cover.buffer(-1e-9)
                except _GEOM_EXC:                          # pragma: no cover
                    _ko = None
                hi = _snap_stations(hi, lattice, stats, avoid=_ko)
                lo = _snap_stations(lo, lattice, stats, avoid=_ko)
                # (the station rows keep their length, so there is no
                #  re-clip here — a station that would land on a
                #  corridor simply stays where it is)
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
            # THE RESERVATION IS THE GROUND THE SPLIT ACTUALLY REMOVED
            # (item 4, 2026-08-05): ``host − band``, so the removed ground
            # is ``band ∩ host``.  The raw band OVERHANGS the apron —
            # ``_joint_stations`` puts its two end stations on the joint
            # line's own endpoints, which stand off the apron boundary —
            # and publishing the overhang would reserve terrain that was
            # never apron and that no emitter owes a cover.  Clipped here,
            # once, where ``host`` is in hand.
            try:
                _reserved = band.intersection(host)
                if _reserved.geom_type == "Polygon" and not _reserved.is_empty:
                    bands.append(_reserved)
                elif _reserved.geom_type.startswith("Multi"):
                    bands.extend(g for g in _reserved.geoms
                                 if g.geom_type == "Polygon"
                                 and not g.is_empty)
            except _GEOM_EXC:
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
        "certificate": _certificate(shape, demand, extent, plane_slope,
                                    dem_geom_excess, joint_count, step_m,
                                    joints, panels, anchors),
    }


def _certificate(shape, demand, extent, plane_slope, dem_geom_excess,
                 joint_count, step_m, joints, panels, anchors):
    """§2(a) THE CERTIFICATE — the evidence chain that authorised ONE
    apron to panelize, written into ``<patch>.axes.json`` so the twin can
    audit "certificate-free panelization = 0" from the patch alone.

    Re-keyed with the trigger (RULINGS 4cbed92): what is recorded is the
    ENVELOPE evidence — the anchor pair whose values contradict, the
    route budget between them and the resulting shortfall — because that
    is now what licenses the terrace.  The steep-truth DEM signature is
    still here, DEMOTED to ``dem_*`` provenance keys: read it to see what
    the ground did, never to see why the law fired.
    """
    (hx, hy) = demand["hi"]
    (lx, ly) = demand["lo"]
    cert = {
        "ref": getattr(shape, "ref", ""),
        "trigger": "anchor_envelope",
        # ── the ENVELOPE evidence (what licensed the terrace) ────────
        "envelope_excess_m": round(float(demand["excess_m"]), 4),
        "relief_m": round(float(demand["excess_m"]), 4),
        "floor_hi_m": round(float(demand["floor_hi"]), 4),
        "ceiling_lo_m": round(float(demand["ceiling_lo"]), 4),
        "pair_chord_m": round(float(demand["chord_m"]), 2),
        "pair_allowance_m": round(float(demand["allowance_m"]), 4),
        "pair_hi_xy": [round(hx, 2), round(hy, 2)],
        "pair_lo_xy": [round(lx, 2), round(ly, 2)],
        "envelope_samples": int(demand["samples"]),
        "cap": APRON_MAX_GRADE,
        "extent_m": round(float(extent), 1),
        # ── the PANELIZATION it bought ───────────────────────────────
        "max_step_m": APRON_TERRACE_MAX_STEP_M,
        "line_budget": joint_count,
        "lines_used": len({j["line_ordinal"] for j in joints}),
        "declared_step_m": round(float(step_m), 4),
        "joints": len(joints),
        "panels": len(panels),
        # ── DEMOTED: report-only DEM provenance ──────────────────────
        "dem_plane_slope": (None if plane_slope is None
                            else round(float(plane_slope), 5)),
        "dem_geom_excess_m": (None if dem_geom_excess is None
                              else round(float(dem_geom_excess), 4)),
    }
    if anchors is not None:
        # THE ANCHOR PAIR, named.  ``anchors`` resolves a point to the
        # (anchor node, anchor value, route budget) that authored its
        # floor / its ceiling — the provenance
        # ``building_feasibility.spine_value_fields`` already carried and
        # now publishes, so the certificate quotes it instead of running
        # a second Dijkstra to re-derive it.
        hi_a = anchors(hx, hy, "floor")
        lo_a = anchors(lx, ly, "ceiling")
        if hi_a is not None:
            cert["floor_anchor"] = hi_a[0]
            cert["floor_anchor_value_m"] = round(float(hi_a[1]), 3)
            cert["floor_route_budget_m"] = round(float(hi_a[2]), 3)
        if lo_a is not None:
            cert["ceiling_anchor"] = lo_a[0]
            cert["ceiling_anchor_value_m"] = round(float(lo_a[1]), 3)
            cert["ceiling_route_budget_m"] = round(float(lo_a[2]), 3)
        if hi_a is not None and lo_a is not None:
            cert["anchor_value_spread_m"] = round(
                abs(float(hi_a[1]) - float(lo_a[1])), 3)
            cert["anchor_route_budget_m"] = round(
                float(hi_a[2]) + float(lo_a[2]), 3)
    return cert


def _snap_stations(row, lattice, stats=None, avoid=None):
    """A joint's station row, with every station that lies within the
    canonical weld tolerance of a SETTLED vertex moved onto it.

    Length-preserving on purpose: ``grid`` is index-aligned with the
    row, and a pair of stations that collapse onto one lattice point
    were already ONE solve node — the collapse is the law, not a loss.

    ``avoid`` is the movement-surface keep-out; it outranks node
    identity exactly as in the fan cut, so a station whose target lies
    on a corridor keeps its own coordinate.
    """
    from auto_patch.layout import SHARED_VERTEX_TOL_M
    out = []
    moved = 0
    for (x, y) in row:
        fx, fy = float(x), float(y)
        cp = lattice.find_nearest(fx, fy, SHARED_VERTEX_TOL_M)
        if cp is not None and cp != (fx, fy):
            blocked = False
            if avoid is not None:
                try:
                    blocked = avoid.intersects(_Point(cp[0], cp[1]))
                except _GEOM_EXC:                          # pragma: no cover
                    blocked = False
            if not blocked:
                moved += 1
                fx, fy = cp
        out.append((fx, fy))
    if stats is not None and moved:
        stats["cut_vertices_snapped"] = (
            stats.get("cut_vertices_snapped", 0) + moved)
    return out


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
               "polygons_split", "split_pieces_added",
               # The demand census travels with the rest so a plan read
               # from a patch can answer "was any relief even asked for".
               "candidates_demanded", "candidates_under_floor",
               "demand_total_m", "demand_worst_m", "no_envelope"):
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
            # STATIONS AS SOLVE VARIABLES.  A :class:`TerraceStation`
            # carries the station's index in the row, its arc-length, and
            # the two node indices the declared step is BOUND between.  A
            # station whose rows did not intern (a panel dropped, a
            # bucket collision) resolves to nothing and is counted, never
            # guessed at.
            joint.stations = _mint_stations(joint, resolve, plan.stats)
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
            # GET, NEVER GET-OR-ADD.  The registry snaps within its
            # tolerance, so one extra insertion changes which LATER
            # vertices intern together and moves the emitted surface
            # (measured: a probe-only node-list rebuild moved SPJC by
            # +1 node and 86 altitudes).  A station is a panel ring
            # vertex, so its bucket is already claimed; if it is not,
            # the honest answer is "unresolved", which the caller
            # counts.
            k = cps.get(float(xy[0]), float(xy[1]))
            return None if k is None else bucket_to_idx.get(k)
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


def _mint_stations(joint, resolve, stats) -> list:
    """THE ONE station mint — plan-time bind and post-rebuild rebind.

    Both passes resolve the SAME geometry through the SAME canonical
    join, so they mint the same population through this one function;
    a second copy is how the two representations diverged in the first
    place.
    """
    from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
    bound = _joint_bound_m(joint)
    sts = []
    for k, s_arc in enumerate(joint.grid or ()):
        if k >= len(joint.hi) or k >= len(joint.lo):
            break
        i_hi = resolve(joint.hi[k])
        i_lo = resolve(joint.lo[k])
        if i_hi is None or i_lo is None or i_hi == i_lo:
            if stats is not None:
                stats["stations_unresolved"] = (
                    stats.get("stations_unresolved", 0) + 1)
            continue
        sts.append(TerraceStation(k, float(s_arc), int(i_hi), int(i_lo),
                                  bound, STACKED_WALL_RETREAT_M))
    return sts


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
        joint.stations = _mint_stations(joint, resolve, None)
        n += len(joint.stations)
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
    out: list = []
    if plan is None:
        return out
    for joint in plan.joints:
        for st in joint.stations:
            out.append((st.i_hi, st.i_lo, st.bound_m))
    return out



def _report_plan(plan: TerracePlan, icao: str) -> None:
    st = plan.stats
    print(f"    [apron-terrace] {icao}: {st['candidates']} apron "
          f"candidate(s), {st.get('candidates_demanded', 0)} with an "
          f"anchor-envelope demand (worst "
          f"{st.get('demand_worst_m', 0.0):.3f} m), "
          f"{st['triggered']} panelized, {st['joints']} "
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
              f"| ENVELOPE relief demand="
              f"{row.get('envelope_excess_m', 0.0):.3f} m (floor "
              f"{row.get('floor_hi_m', 0.0):.2f} vs ceiling "
              f"{row.get('ceiling_lo_m', 0.0):.2f} over a "
              f"{row.get('pair_chord_m', 0.0):.0f} m chord allowing "
              f"{row.get('pair_allowance_m', 0.0):.2f} m), line budget "
              f"{row.get('line_budget', 0)} used "
              f"{row.get('lines_used', 0)} "
              f"[DEM provenance: plane "
              f"{(row.get('dem_plane_slope') or 0.0) * 100:.2f} %]")


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




# ════════════════════════════════════════════════════════════════════
# 4b.  THE FAN-RAMP LAW  (owner ruling, RULINGS 21f0980)
# ════════════════════════════════════════════════════════════════════
#
# THE LAW, in the owner's own composition:
#
#   "aircraft-movement surfaces (spine corridors + frontage chords +
#    stand entries) hold the strict apron cap, always; frontage chords
#    run straight building→spine; between frontages at the back edge,
#    the fan-ramp zone carries up to 5% continuous grade fanning between
#    building seat levels; walls only as the ruled fallback; no ramp,
#    joint, or wall may touch any movement surface."
#
# WHAT IT IS FOR.  Between two adjacent terminal stands the apron has to
# get from one building's seat level to the next.  Held to the 1 % apron
# cap that transition is often infeasible, and the only relief the law
# had was a WALL — a step across ground nothing drives on, where a
# continuous ramp is both buildable and what real aprons do.  The owner
# ruled the ramp FIRST and the wall a fallback (precedence, answer 2).
#
# THE ZONE IS THE COMPLEMENT OF THE MOVEMENT SURFACES, and that is the
# whole trick: ``corridor_cover`` ALREADY carries every spine corridor,
# every building frontage chord, every stand entry and every pad, each
# buffered by the standard clearance — it is the set the terrace law is
# forbidden to cross.  So ``apron − cover`` is, by construction, "clear
# of every movement surface by standard clearance"; the frontage chords
# cut it into the wedges between adjacent buildings, and each wedge runs
# from the back apron edge out to the corridor clearance.  That is the
# ruling's zone, derived rather than re-specified — and it inherits the
# no-touch guarantee structurally instead of by a later check.
#
# THE FAN ITSELF IS NOT DRAWN.  The zone's interior edges enter the ONE
# solve at the zone cap as ordinary law edges; a surface fanning between
# the two seat levels is what that system solves to.  Nothing here
# builds a fan shape, which is the point — EMITTERS EMIT, NEVER GRADE.
#
# PRECEDENCE IS IN THE TRIGGER, NOT IN A SECOND PASS.  The zone cap
# enters ``_envelope_demand`` as the pair allowance, so the shortfall the
# terrace law then sees is exactly the relief 5 % could NOT span inside
# the zone.  Ramps first, wall fallback, one computation.

# ``FAN_RAMP_CAP`` is imported from ``config`` (the repo's rule: every
# grade value is defined once there and re-exported under the existing
# local name).  It has to be readable from ``tools/check_grade`` and from
# ``grade_graph`` without either importing this solve-side module.
# A zone smaller than this is a sliver of the difference operation, not
# ground anybody ramps: it would grant 5 % across a few square metres
# between two buffers that nearly meet.
_FAN_MIN_AREA_M2 = 200.0
# The ruling's "between ADJACENT buildings": a zone needs two.
_FAN_MIN_BUILDINGS = 2
# Two pads are ADJACENT when their footprints come within this of each
# other.  Past it they are not neighbouring stands and the ground
# between them is ordinary apron, not a transition between two seats.
_FAN_PAIR_MAX_GAP_M = 250.0
# How far into the apron a pair's zone reaches, as a multiple of the gap
# it has to fan across, hard-capped.  SELF-SCALING because that is what
# the geometry says: a fan spanning a 40 m gap needs 40 m of apron to do
# it in, and one spanning 200 m needs more.  The cap keeps a distant pair
# from claiming half an apron.
#
# WHY A BOUND AT ALL — measured, not assumed.  The first cut of this law
# took "``apron − corridor_cover``, adjacent to two pads" as the zone.
# On the twins' own two-terminal fixture that came out as 77 142 m² of a
# 120 000 m² apron: the region between the two frontage chords is joined
# to the apron's far corners by the 5 m strip behind the pads, so ONE
# component wrapped the whole surface and 5 % would have been granted
# across all of it.  The ruling's zone is bounded BY the two buildings.
_FAN_ZONE_DEPTH_GAP_MULT = 1.0
_FAN_ZONE_MAX_DEPTH_M = 120.0


class FanRampPlan:
    """The airport's declared fan-ramp zones + the round's census."""

    def __init__(self):
        # [{"shape_id", "polygon", "cap", "buildings", "area_m2"}]
        self.zones: list[dict] = []
        self.by_shape: dict[int, list[dict]] = {}
        self.stats: dict = {
            "apron_candidates": 0, "zones": 0, "zone_area_m2": 0.0,
            "pairs_considered": 0,
            "components_seen": 0, "dropped_small": 0,
            "dropped_one_building": 0, "edges_at_ramp_cap": 0,
        }

    def add(self, shape_id: int, zone: dict) -> None:
        self._prepared = None
        self.zones.append(zone)
        self.by_shape.setdefault(shape_id, []).append(zone)
        self.stats["zones"] += 1
        self.stats["zone_area_m2"] += zone["area_m2"]

    # ── THE INDEX ────────────────────────────────────────────────
    # Every consumer asks "which zone is this point / chord in", over
    # tens of thousands of pairs.  Shapely predicates on a raw polygon
    # are ~10 us each, so the naive scan is minutes at a real airport
    # (measured: HECA's plateau build went from 8 min to past 10).  The
    # index is a bbox prefilter plus a PREPARED geometry per zone, built
    # once and cached on the plan.
    def _index(self):
        idx = getattr(self, "_prepared", None)
        if idx is None:
            from shapely.prepared import prep
            idx = []
            for z in self.zones:
                poly = z["polygon"]
                idx.append((poly.bounds, prep(poly), float(z["cap"])))
            self._prepared = idx
        return idx

    def zone_of(self, x, y) -> int:
        """The index of the zone containing ``(x, y)``, or ``-1``."""
        for k, (bb, pre, _cap) in enumerate(self._index()):
            if not (bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]):
                continue
            if pre.intersects(_Point(x, y)):
                return k
        return -1

    def zone_caps(self) -> list:
        return [float(z["cap"]) for z in self.zones]

    def covers(self, x, y) -> bool:
        """Is ``(x, y)`` inside a declared zone?"""
        return self.zone_of(x, y) >= 0

    def pair_cap(self, ax, ay, bx, by, default: float) -> float:
        """THE SOLVER's and the VALIDATOR's predicate: the cap a
        within-apron PAIR is held to.

        BOTH endpoints inside ONE zone, and the CHORD between them inside
        it too.  A chord that leaves the zone crosses an aircraft-
        movement surface, and those hold the strict apron cap ALWAYS
        (the ruling's composition clause).  A pair with its two ends in
        two DIFFERENT zones is not in a zone: the ground between them is
        a corridor.
        """
        if not self.zones:
            return default
        # BOTH ENDS IN THE SAME ZONE IS NECESSARY, and it is the cheap
        # test — so it runs first and the chord predicate only ever sees
        # the handful of pairs that could pass it.
        ka = self.zone_of(ax, ay)
        if ka < 0 or self.zone_of(bx, by) != ka:
            return default
        try:
            chord = LineString([(ax, ay), (bx, by)])
        except _GEOM_EXC:                                  # pragma: no cover
            return default
        bb, pre, cap = self._index()[ka]
        try:
            if pre.covers(chord):
                return cap
        except _GEOM_EXC:                                  # pragma: no cover
            pass
        return default

    def endpoints_cap(self, ax, ay, bx, by, default: float) -> float:
        """THE TRIGGER's predicate: both ENDPOINTS in one zone.

        Deliberately weaker than :meth:`pair_cap`, and the difference is
        the point.  The solver prices one straight EDGE, so a chord
        leaving the zone must keep the strict cap.  The trigger asks a
        different question — "can a ramp inside this zone discharge this
        relief, or is a wall the only answer?" — and relief travels along
        the ground, not along the chord.  A zone polygon is connected, so
        two points inside it are joined by an in-zone PATH at least as
        long as their chord; ``cap_zone · chord`` is therefore a lower
        bound on what the ramp can carry between them.

        This is what makes precedence (owner answer 2) real: the wall law
        is left only the relief 5 % genuinely cannot span.
        """
        if not self.zones:
            return default
        ka = self.zone_of(ax, ay)
        if ka < 0 or self.zone_of(bx, by) != ka:
            return default
        return self._index()[ka][2]


def plan_fan_ramp_zones(layout, cover=None, icao: str = "") -> FanRampPlan:
    """Build the airport's fan-ramp zones.  GENERAL law — every apron
    with building frontage (owner answer 4); no gate, no airport list.

    ONE ZONE PER ADJACENT PAIR OF BUILDINGS, which is what the ruling
    says in as many words.  For pads ``A`` and ``B`` within
    ``_FAN_PAIR_MAX_GAP_M`` of each other, the pair's reach is
    ``hull(A ∪ B)`` grown by the gap it has to fan across (capped), and
    the zone is that reach ∩ apron − corridor cover:

      * ∩ APRON — the law grades apron, nothing else;
      * − COVER — the cover already carries every spine corridor, every
        frontage chord, every stand entry and every pad, each buffered by
        the standard clearance, so "clear of every aircraft-movement
        surface" is inherited STRUCTURALLY rather than checked after;
      * ∩ REACH — bounded by the two buildings it fans between, so the
        zone is the back-edge wedge and not the whole apron.

    A third pad standing between A and B is in the cover, so it splits
    the pair's zone by construction — "adjacent" needs no separate test.
    """
    from auto_patch.elevation_per_surface.solver_primitives import (
        _corridor_segments)
    plan = FanRampPlan()
    segs = _corridor_segments(layout, include_roads=True)
    if not segs:
        # No movement network ⇒ no frontage chords ⇒ nothing for a zone
        # to be BETWEEN, and nothing for it to be clear OF.  (The cover
        # is non-empty even here — it carries the pads — so this test
        # cannot be folded into an emptiness check on it.)
        return plan
    if cover is None:
        cover = corridor_cover(layout)
    if cover is None or cover.is_empty:
        return plan
    # THE ZONE IS CUT AGAINST A LATTICE-COARSE SUPERSET of the cover
    # (RULING 2026-08-06) — see :func:`lattice_coarse_cover`.  Only the
    # SHAPING difference below uses it; every other reader (the
    # pad-proximity test, the trigger, the joint keepout) keeps the true
    # cover, because they ask about the real movement surfaces.
    zone_cover = lattice_coarse_cover(cover, icao=icao)
    pads = []
    for s in getattr(layout, "shapes", ()):
        if (s.role or "") != "building":
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or poly.is_empty:
            continue
        pads.append(poly)
    if len(pads) < _FAN_MIN_BUILDINGS:
        return plan
    reaches = []
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            try:
                gap = float(pads[i].distance(pads[j]))
            except _GEOM_EXC:                              # pragma: no cover
                continue
            if gap > _FAN_PAIR_MAX_GAP_M:
                continue
            plan.stats["pairs_considered"] += 1
            depth = min(_FAN_ZONE_MAX_DEPTH_M,
                        max(1.0, gap * _FAN_ZONE_DEPTH_GAP_MULT))
            try:
                reach = _fan_pair_reach(pads[i], pads[j], depth)
            except _GEOM_EXC:                              # pragma: no cover
                continue
            if reach is not None and not reach.is_empty:
                reaches.append(reach)
    if not reaches:
        return plan
    for shape in list(getattr(layout, "shapes", ())):
        if (shape.role != ROLE_APRON or shape.polygon is None
                or shape.polygon.is_empty
                or shape.polygon.geom_type != "Polygon"):
            continue
        plan.stats["apron_candidates"] += 1
        for reach in reaches:
            try:
                zone = (shape.polygon.intersection(reach)
                        .difference(zone_cover))
            except _GEOM_EXC:
                continue
            if zone.is_empty:
                continue
            parts = ([zone] if zone.geom_type == "Polygon"
                     else [g for g in getattr(zone, "geoms", ())
                           if g.geom_type == "Polygon" and not g.is_empty])
            for g in parts:
                plan.stats["components_seen"] += 1
                try:
                    area = float(g.area)
                except _GEOM_EXC:                          # pragma: no cover
                    continue
                if area < _FAN_MIN_AREA_M2:
                    plan.stats["dropped_small"] += 1
                    continue
                near = 0
                for pad in pads:
                    try:
                        if g.intersects(pad.buffer(
                                APRON_TERRACE_JOINT_CLEARANCE_M * 1.5)):
                            near += 1
                    except _GEOM_EXC:                      # pragma: no cover
                        continue
                    if near >= _FAN_MIN_BUILDINGS:
                        break
                if near < _FAN_MIN_BUILDINGS:
                    plan.stats["dropped_one_building"] += 1
                    continue
                plan.add(id(shape), {
                    "shape_id": id(shape),
                    "polygon": g,
                    "cap": FAN_RAMP_CAP,
                    "buildings": near,
                    "area_m2": area,
                })
    if plan.zones or _os.environ.get("O4_STEP_DEBUG") == "1":
        import O4_UI_Utils as _UI
        st = plan.stats
        _UI.vprint(1,
            f"  [fan-ramp] {icao}: {st['zones']} zone(s) over "
            f"{st['zone_area_m2']:,.0f} m² on {st['apron_candidates']} apron "
            f"candidate(s) at {FAN_RAMP_CAP * 100:.0f} % "
            f"(RULINGS 21f0980, the groundside class); "
            f"{st['pairs_considered']} adjacent building pair(s), "
            f"{st['components_seen']} movement-clear component(s), "
            f"{st['dropped_small']} under {_FAN_MIN_AREA_M2:g} m², "
            f"{st['dropped_one_building']} not between two buildings")
    return plan


def _fan_pair_reach(pad_a, pad_b, depth: float):
    """How far a pair of adjacent buildings' fan reaches into the apron.

    ``hull(A ∪ B)`` grown by ``depth``, then CUT BACK to the pair's own
    extent along the axis joining them.  The cut is what makes this
    "between adjacent buildings" rather than "near them": a plain buffer
    also spills sideways PAST each building, and that ground is beside a
    stand, not between two of them — measured on the twins' fixture, a
    plain buffer handed 5 % to the apron's outer corners as well as to
    the gap.

    Depth is perpendicular to the axis, which is the direction the fan
    actually runs: from the back edge out toward the spine.
    """
    hull = unary_union([pad_a, pad_b]).convex_hull
    ca, cb = pad_a.centroid, pad_b.centroid
    ux, uy = cb.x - ca.x, cb.y - ca.y
    norm = math.hypot(ux, uy)
    grown = hull.buffer(depth)
    if norm < 1e-9:                                        # pragma: no cover
        return grown
    ux, uy = ux / norm, uy / norm
    ts = [x * ux + y * uy
          for pad in (pad_a, pad_b)
          for (x, y) in _open_ring_xy(pad)]
    if not ts:                                             # pragma: no cover
        return grown
    t_lo, t_hi = min(ts), max(ts)
    # The slab ``t_lo ≤ p·u ≤ t_hi``, as a polygon big enough to cover
    # the grown hull in the perpendicular direction.
    px, py = -uy, ux
    span = depth + hull.length + 1.0
    corners = [
        (ux * t_lo + px * -span, uy * t_lo + py * -span),
        (ux * t_hi + px * -span, uy * t_hi + py * -span),
        (ux * t_hi + px * span, uy * t_hi + py * span),
        (ux * t_lo + px * span, uy * t_lo + py * span),
    ]
    return grown.intersection(Polygon(corners))


def lattice_coarse_cover(cover, tol_m=None, icao: str = ""):
    """THE KEEP-OUT THE ZONE IS CUT AGAINST: a lattice-coarse SUPERSET of
    the true movement cover (RULING 2026-08-06, cycle-5 node-identity
    spec).

    The true cover is a ``buffer()`` — its arc vertices are spaced at
    roughly the canonical weld tolerance.  Cutting the fan/terrace zone
    against it therefore BORNS the zone with vertex pairs the canonical
    registry interns onto one node, and the ramp piece and the remainder
    panel then price that node's pairs under two different caps
    (measured at CYXY: aprons carry 0 such pairs before the cut and 884
    after; 193 solver↔validator budget mismatches).  Collapsing them
    after the fact is not available — the collapse chords across the
    cover's convex arcs and pushes 1.289 m² of ramp INSIDE the movement
    corridor, which the owner's fan-ramp ruling forbids outright.

    So the contradiction is resolved by CONSTRUCTION, with two
    properties this function guarantees and ``tests/test_fan_ramp_law``
    twins:

    (a) IT CONTAINS THE TRUE COVER.  The keep-out therefore still binds
        at ZERO tolerance against the true cover — a superset only ever
        protects more ground, never less.  Verified here, per call, not
        merely argued: the grow-and-coarsen is retried with a doubled
        margin until ``covers`` holds.
    (b) ITS BOUNDARY VERTICES ARE ``tol_m``-SEPARATED, so the cut is born
        satisfying the node-identity law and there is nothing to collapse
        afterwards (``canonical_points.coarsen_to_lattice_spacing``
        guarantees this structurally).

    Accepted consequence (ruling §3): the declared 5 % zone area shrinks
    slightly.  That is lawful — the wall/step fallback covers whatever
    the smaller zone cannot span (fan-ramp precedence, RULINGS 21f0980).

    Falls back to the TRUE cover, loudly, if no margin produces a
    verified superset — a smaller-but-correct keep-out is never the
    answer, and the node-identity defect is the lesser of the two.
    """
    from auto_patch.canonical_points import coarsen_to_lattice_spacing
    from auto_patch.layout import SHARED_VERTEX_TOL_M
    if cover is None or cover.is_empty:
        return cover
    t = SHARED_VERTEX_TOL_M if tol_m is None else float(tol_m)
    margin = t * 1.01
    for _ in range(4):
        try:
            coarse = coarsen_to_lattice_spacing(cover.buffer(margin), t)
            if (coarse is not None and not coarse.is_empty
                    and coarse.covers(cover)):
                return coarse
        except _GEOM_EXC:                                  # pragma: no cover
            pass
        margin *= 2.0
    try:
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [fan-ramp] {icao}: WARN — no verified lattice-coarse "
            f"SUPERSET of the movement cover (tried up to "
            f"{margin / 2:.2f} m); cutting against the TRUE cover, so "
            f"the cut is born with sub-tolerance vertex pairs.")
    except Exception:                                      # pragma: no cover
        pass
    return cover


class _FanHole(Exception):
    """A fan-zone cut that could only be expressed as an interior ring."""


def _cut_diag(tag, group_a, group_b) -> None:
    """NODE-IDENTITY diagnostic for the fan cut (``O4_APRON_TERRACE_DEBUG``).

    Reports how many vertices of ``group_a`` sit within the canonical weld
    tolerance of a ``group_b`` vertex WITHOUT being identical to it — i.e.
    how many welded-but-distinct pairs (one solve node, two ring
    coordinates) exist between the ramp side and the remainder side at
    this point in the construction.  Off by default; no behaviour.
    """
    if _os.environ.get("O4_APRON_TERRACE_DEBUG") != "1":
        return
    try:
        import O4_UI_Utils as _UI
        pa = [pt for g in group_a for pt in _open_ring_xy(g)]
        pb = [pt for g in group_b for pt in _open_ring_xy(g)]
        exact = twin = 0
        worst = 0.0
        for (x, y) in pa:
            best = min((math.hypot(x - a, y - b) for (a, b) in pb),
                       default=1e9)
            if best <= 1e-9:
                exact += 1
            elif best <= 0.5:
                twin += 1
                worst = max(worst, best)
        _UI.vprint(1,
            f"  [fan-cut-diag] {tag}: {exact} exact-shared, {twin} "
            f"welded-but-distinct (worst {worst:.4f} m) over "
            f"{len(pa)} vs {len(pb)} vertices")
    except Exception:                                      # pragma: no cover
        pass


def split_aprons_at_fan_zones(layout, plan: Optional[FanRampPlan],
                              icao: str = "", cover=None) -> int:
    """PRE-SOLVE PANELIZATION AT THE FAN-ZONE BOUNDARY.  Returns the
    number of zone PIECES that became shapes.

    WHY THIS EXISTS — the law was landed, correct, and INERT.  Measured
    on HECA's plateau build: 808 declared zones over 295 526 m² of
    movement-clear apron, and **170** within-apron law edges raised to
    the zone cap.  The reason is structural, not a tuning miss: the
    chord-predicate form of the law can only RAISE A PAIR THAT ALREADY
    EXISTS, an apron's solve variables are its RING vertices, and a
    fan-ramp zone is by construction INTERIOR ground — the back-edge
    wedge between two frontages.  Of 10 255 within-apron census rows at
    HECA, 9 739 had neither endpoint in any zone and exactly **9** were
    blocked by the whole-chord test.  Relaxing the predicate would have
    bought nine rows; the zone had no variables of its own to solve.

    SO THE ZONE BECOMES A SHAPE, which is the terrace law's own answer to
    the same problem (``construct_apron_terrace_presolve``: "the panel
    boundary is a set of solve variables").  Cut out before the solve,
    the zone's boundary is minted as ring vertices and its interior pairs
    are ITS OWN ALL-PAIRS at the zone cap — the ONE solve then has a
    surface it can actually fan, and the census reads the same law off
    the emitted piece's ``o4_grade_law`` tag.

    THE CUT IS THE TERRACE CUT, COMPONENT BY COMPONENT.  Zones overlap
    heavily (HECA: 3 232 335 m² of parts over a 295 526 m² union — one
    per adjacent building PAIR, and a stand has several neighbours), so
    the apron is split at the UNION's components, largest first, each out
    of the geometry the last one left behind.  A component that could
    only be expressed as an INTERIOR RING is STILLBORN and dropped,
    exactly as an unfaceable joint is: every shape in this system is
    simply connected.  Measured, that costs 3 of 30 zone-bearing aprons
    at HECA and keeps the central U-apron, whose six components include
    one island.

    A STILLBORN ZONE IS DROPPED FROM THE PLAN, not merely from the
    layout.  The declaration the sidecar publishes is then exactly the
    ground that became a 5 % shape — the solver's edge rewrite, the
    terrace trigger's ramp allowance and the census all read one set, and
    the wall law is left the relief the ramp genuinely could not take
    (owner answer 2, precedence).

    Losing pavement to a geometry op is never the lawful answer: every
    piece — zone and remainder alike — is kept and emitted.

    THE CUT IS BORN ON THE SETTLED LATTICE (cycle-5 node identity,
    ``docs/specs/cycle5-node-identity-spec.md``).  This runs AFTER
    ``pipeline._unify_airside_geometry`` settled the airside node set, so
    every vertex it mints within the canonical weld tolerance of a
    settled one is a node with TWO ring coordinates — measured at CYXY,
    23 welded-but-distinct pairs at cut time (worst 0.4756 m), and the
    ramp piece (5 %) and the remainder panel (1 %) then price the same
    solve node under two different caps: the solver binds the strictest,
    the coordinate-keyed validator reads 5 % off the ramp's own ring.
    So each component is SNAPPED onto the settled vertices before the
    difference; the boundary is then shared by construction.  Welding
    the pieces AFTERWARDS is the falsified alternative — it moves them
    independently and tears the partition (0.1384 m² of apron∩apron).
    """
    if plan is None or not plan.zones:
        return 0
    from auto_patch.canonical_points import (
        add_polygon_to_lattice, settled_vertex_lattice,
        snap_polygon_to_lattice)
    from auto_patch.layout import BuiltShape, SHARED_VERTEX_TOL_M
    st = plan.stats
    st.setdefault("zones_split_in", 0)
    st.setdefault("zones_stillborn_hole", 0)
    st.setdefault("aprons_split", 0)
    st.setdefault("remainder_pieces_added", 0)
    st.setdefault("cut_vertices_snapped", 0)
    st.setdefault("cut_snap_declined", 0)
    lattice = settled_vertex_lattice(layout, tol_m=SHARED_VERTEX_TOL_M)
    # THE MOVEMENT-SURFACE KEEP-OUT OUTRANKS NODE IDENTITY (owner's
    # fan-ramp ruling: no ramp may touch an aircraft-movement surface).
    # Handed to the snap whole; it applies the law's own epsilon-shrunk
    # predicate and re-clips against this geometry when needed.
    try:
        keep_out = cover if cover is not None else corridor_cover(layout)
    except _GEOM_EXC:                                      # pragma: no cover
        keep_out = None
    kept_zones: list = []
    new_shapes: list = []
    for shape in list(getattr(layout, "shapes", ())):
        zones = plan.by_shape.get(id(shape))
        if not zones:
            continue
        poly = getattr(shape, "polygon", None)
        if (poly is None or poly.is_empty or poly.geom_type != "Polygon"):
            continue
        # ── the zones of THIS apron, unioned into components ─────────
        parts = []
        for z in zones:
            try:
                g = poly.intersection(z["polygon"])
            except _GEOM_EXC:                              # pragma: no cover
                continue
            if g.is_empty:
                continue
            parts.extend([g] if g.geom_type == "Polygon"
                         else [q for q in getattr(g, "geoms", ())
                               if q.geom_type == "Polygon" and not q.is_empty])
        if not parts:
            continue
        try:
            merged = unary_union(parts)
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        comps = ([merged] if merged.geom_type == "Polygon"
                 else [g for g in getattr(merged, "geoms", ())
                       if g.geom_type == "Polygon" and not g.is_empty])
        comps = sorted((g for g in comps if g.area >= _FAN_MIN_AREA_M2),
                       key=lambda g: -g.area)
        if not comps:
            continue
        # ── ONTO THE SETTLED LATTICE, BEFORE THE DIFFERENCE ──────────
        # A component vertex within the canonical weld tolerance of a
        # settled vertex IS that node; snapped here, the cut inherits
        # the apron's own vertices and the ramp/panel boundary is
        # shared exactly.  A snap that degenerates the component keeps
        # the unsnapped one — losing the cut is worse than one twin,
        # and the count is reported.
        snapped_comps = []
        for comp in comps:
            g, n_moved = snap_polygon_to_lattice(
                comp, lattice, SHARED_VERTEX_TOL_M, avoid=keep_out)
            if g is None or g.is_empty or g.geom_type != "Polygon":
                st["cut_snap_declined"] += 1
                snapped_comps.append(comp)
                continue
            st["cut_vertices_snapped"] += n_moved
            snapped_comps.append(g)
        comps = [g for g in snapped_comps if g.area >= _FAN_MIN_AREA_M2]
        if not comps:
            continue
        # ── the terrace cut, one component at a time ─────────────────
        panels = [poly]
        survivors = []
        for comp in comps:
            st["zones_split_in"] += 1
            if len(comp.interiors):
                st["zones_stillborn_hole"] += 1
                continue
            # SUBTRACT FROM EVERY PANEL, NOT FROM A "HOST".  The panels
            # PARTITION the apron, and a component need not sit inside
            # any one of them — an earlier cut can have divided the
            # ground this one spans.  Taking a single host by
            # representative point and differencing only that leaves the
            # component's other part inside a sibling panel WHILE the
            # component is also emitted as a ramp piece: the two shapes
            # then OVERLAP, which is a zero-tolerance defect
            # (``test_no_self_overlap``) and puts one coordinate pair
            # under two different caps — measured, SPJC 0.9477 m² of
            # apron∩apron and 190/12 877 CYXY edges where the solver
            # priced 1 % and the validator 5 %.  Differencing every panel
            # cannot do that: the ramp's ground leaves the remainder
            # wherever it was.
            try:
                trial = []
                touched = False
                for p in panels:
                    if not p.intersects(comp):
                        trial.append(p)
                        continue
                    d = p.difference(comp)
                    if d.is_empty:
                        touched = True
                        continue
                    parts = ([d] if d.geom_type == "Polygon"
                             else [g for g in getattr(d, "geoms", ())
                                   if g.geom_type == "Polygon"
                                   and not g.is_empty])
                    if any(len(g.interiors) for g in parts):
                        raise _FanHole()
                    touched = True
                    trial.extend(parts)
            except _FanHole:
                # Would punch an interior ring: stillborn, exactly like
                # an unfaceable terrace joint.  Every shape here is
                # simply connected.
                st["zones_stillborn_hole"] += 1
                continue
            except _GEOM_EXC:                              # pragma: no cover
                st["zones_stillborn_hole"] += 1
                continue
            if not trial or not touched:
                st["zones_stillborn_hole"] += 1
                continue
            panels = trial
            survivors.append(comp)
        if not survivors:
            continue
        _cut_diag("step1 comps-vs-panels", survivors, panels)
        # ── THE RAMP IS THE GROUND THE CUT ACTUALLY REMOVED ─────────
        # Not the component that asked for it.  Same reasoning the wall
        # band already carries here ("THE RESERVATION IS THE GROUND THE
        # SPLIT ACTUALLY REMOVED"), and it is not bookkeeping: the
        # component came out of a union of overlapping per-pair zones,
        # and shapely's union/difference do not round-trip exactly, so
        # ``comp`` and ``apron − panels`` differ by slivers.  Emitting
        # ``comp`` put those slivers in the ramp piece AND in a
        # remainder panel — measured at SPJC as 0.9477 / 0.1181 /
        # 0.0001 m² of apron∩apron, a zero-tolerance defect, and as 190
        # CYXY edges priced 1 % by the solver and 5 % by the validator.
        # Defined as the difference, ``ramp ∪ panels == apron`` and
        # ``ramp ∩ panels == ∅`` BY CONSTRUCTION, whatever shapely did.
        try:
            removed = poly.difference(unary_union(panels))
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        ramp_pieces = ([removed] if removed.geom_type == "Polygon"
                       else [g for g in getattr(removed, "geoms", ())
                             if g.geom_type == "Polygon" and not g.is_empty])
        ramp_pieces = [g for g in ramp_pieces
                       if g.area >= _FAN_MIN_AREA_M2 and not g.interiors]
        if not ramp_pieces:
            # Nothing survived as real ground: put the apron back rather
            # than ship a cut that removed only slivers.
            st["zones_stillborn_hole"] += len(survivors)
            continue
        # Whatever the sliver filter dropped stays with the REMAINDER,
        # so no pavement is lost: re-derive the panels from the pieces
        # that will actually ship.
        try:
            rest = poly.difference(unary_union(ramp_pieces))
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        panels = ([rest] if rest.geom_type == "Polygon"
                  else [g for g in getattr(rest, "geoms", ())
                        if g.geom_type == "Polygon" and not g.is_empty])
        if not panels:
            st["zones_stillborn_hole"] += len(survivors)
            continue
        survivors = ramp_pieces
        _cut_diag("step3 ramps-vs-panels", survivors, panels)
        panels.sort(key=lambda p: -p.area)
        # THE APRON KEEPS ITS IDENTITY as the largest remainder panel —
        # everything that captured this shape earlier in the pipeline
        # still points at an apron.  Siblings and zones are appended.
        group = id(shape)
        shape.polygon = panels[0]
        shape._fan_panel_group = group
        for extra in panels[1:]:
            sib = BuiltShape(polygon=extra, role=ROLE_APRON,
                             ref=getattr(shape, "ref", ""))
            sib._fan_panel_group = group
            new_shapes.append(sib)
            st["remainder_pieces_added"] += 1
        for comp in survivors:
            zs = BuiltShape(polygon=comp, role=ROLE_APRON,
                            ref=getattr(shape, "ref", ""),
                            fan_ramp_zone=True)
            zs._fan_panel_group = group
            new_shapes.append(zs)
            kept_zones.append((zs, comp))
        # The pieces this apron's cut just minted JOIN the lattice, so a
        # later apron's cut (and the terrace cut after this pass) snaps
        # to them too — the settled set only ever grows.
        for p in panels:
            add_polygon_to_lattice(p, lattice)
        for comp in survivors:
            add_polygon_to_lattice(comp, lattice)
        st["aprons_split"] += 1
    if new_shapes:
        layout.shapes.extend(new_shapes)
    # ── RE-DECLARE THE PLAN AS WHAT WAS ACTUALLY BUILT ───────────────
    # One declaration, and it names the pieces that exist.  A zone the
    # cut could not express is gone from every reader at once — the
    # solver's edge rewrite, the terrace trigger's ramp allowance and
    # the census sidecar.  UNCONDITIONAL, including the all-stillborn
    # case: a plan that kept its old zones there would go on granting
    # 5 % on ground no shape was ever given at 5 %, which is precisely
    # the solver/census divergence this law exists to make impossible.
    plan.zones = []
    plan.by_shape = {}
    plan._prepared = None
    plan.stats["zones"] = 0
    plan.stats["zone_area_m2"] = 0.0
    for (zs, comp) in kept_zones:
        plan.add(id(zs), {
            "shape_id": id(zs),
            "polygon": comp,
            "cap": FAN_RAMP_CAP,
            "buildings": _FAN_MIN_BUILDINGS,
            "area_m2": float(comp.area),
        })
    if not (kept_zones or st["zones_split_in"]):
        return 0
    import O4_UI_Utils as _UI
    _UI.vprint(1,
        f"  [fan-ramp] {icao}: PRE-SOLVE panelization — "
        f"{st['aprons_split']} apron(s) cut at the zone boundary into "
        f"{len(kept_zones)} RAMP piece(s) over "
        f"{plan.stats['zone_area_m2']:,.0f} m² at "
        f"{FAN_RAMP_CAP * 100:.0f} % + {st['remainder_pieces_added']} "
        f"remainder sibling(s); {st['zones_stillborn_hole']} of "
        f"{st['zones_split_in']} component(s) STILLBORN (would punch an "
        f"interior ring) and dropped from the declaration; "
        f"{st['cut_vertices_snapped']} cut vertex(es) snapped onto the "
        f"settled lattice before the difference "
        f"({st['cut_snap_declined']} component(s) declined the snap)")
    return len(kept_zones)


def apply_fan_ramp_caps(plan: Optional[FanRampPlan], shape_constraints,
                        node_xy) -> int:
    """Raise the cap on every within-apron law edge that lies wholly
    inside a declared fan-ramp zone.  Returns the edge count.

    RELAXING ONLY, exactly like the terrace budget: an edge that is not
    wholly inside a zone is returned byte-identical, so every movement
    surface keeps the strict apron cap.
    """
    if plan is None or not plan.zones:
        return 0
    node_xy = _as_xy(node_xy)
    total = 0
    for entry in shape_constraints:
        zones = plan.by_shape.get(entry.get("shape_id", -1))
        if not zones:
            continue
        edges, touched = _rewrite_fan_edges(entry.get("edges") or [],
                                            zones, node_xy)
        entry["edges"] = edges
        total += touched
        thunk = entry.get("lazy_expand")
        if thunk is not None:
            def _bound(_t=thunk, _z=zones, _xy=node_xy):
                return _rewrite_fan_edges(list(_t()), _z, _xy)[0]
            entry["lazy_expand"] = _bound
    plan.stats["edges_at_ramp_cap"] = total
    return total


def apply_fan_ramp_caps_to_edges(plan: Optional[FanRampPlan], edges,
                                 node_xy):
    """The same law on the unified graph's own ``u_edges``.

    Both edge sets or neither: ``solve``/``final_grade_projection``
    project the unified all-pair edges SEPARATELY from
    ``shape_constraints``, so relief granted only in one is taken
    straight back by the other — the two-instruments trap in its
    edge-set costume (the terrace budget learned this the hard way).
    """
    if plan is None or not plan.zones:
        return edges, 0
    node_xy = _as_xy(node_xy)
    zones = plan.zones
    return _rewrite_fan_edges(edges, zones, node_xy)


def _rewrite_fan_edges(edges, zones, node_xy):
    """``cap·d`` → ``ramp cap·d`` for edges wholly inside one zone.

    Indexed: each NODE's zone is resolved once (memoised), and the
    chord predicate runs only for the edges whose two ends already agree
    on a zone.  The flat scan was one prepared-geometry call per edge per
    zone and did not finish inside the build budget at HECA.
    """
    sub = FanRampPlan()
    for z in zones:
        sub.add(z["shape_id"], z)
    zone_of: dict = {}

    def _zone(i, p):
        k = zone_of.get(i, _UNSET_ZONE)
        if k is _UNSET_ZONE:
            k = sub.zone_of(p[0], p[1])
            zone_of[i] = k
        return k

    out = []
    touched = 0
    for e in edges:
        if len(e) != 3:
            out.append(e)
            continue
        a, b, budget = e
        pa, pb = node_xy.get(a), node_xy.get(b)
        if pa is None or pb is None:
            out.append(e)
            continue
        d = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        if d < 1e-9:
            out.append(e)
            continue
        ka = _zone(a, pa)
        if ka < 0 or _zone(b, pb) != ka:
            out.append(e)
            continue
        _bb, pre, cap_z = sub._index()[ka]
        try:
            if not pre.covers(LineString([pa, pb])):
                out.append(e)
                continue
        except _GEOM_EXC:                                  # pragma: no cover
            out.append(e)
            continue
        relaxed = float(cap_z) * d
        if relaxed <= float(budget):
            # NEVER TIGHTEN.  The zone cap is an upper bound the ruling
            # GRANTS; an edge already carrying a looser budget (a
            # neighbour role's own law reaching in) keeps it.
            out.append(e)
            continue
        out.append((a, b, relaxed))
        touched += 1
    return out, touched


def fan_ramp_zones_sidecar(layout) -> list:
    """``fan_ramp_zones`` for ``<patch>.axes.json`` — THE ONE READER's
    source.

    The census judges a within-apron pair at the zone cap when the pair
    lies inside a declared zone and at the strict apron cap otherwise,
    reading THIS key — the same one-reader pattern ``terrace_joints``
    established, so the solver and the validator cannot each carry their
    own idea of where the ramp is.
    """
    plan = getattr(layout, "_fan_ramp_plan", None)
    if plan is None or not getattr(plan, "zones", None):
        return []
    out = []
    for z in plan.zones:
        try:
            ring = _open_ring_xy(z["polygon"])
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        if len(ring) < 3:
            continue
        try:
            ll = [list(layout.m_to_ll(x, y)) for (x, y) in ring]
        except _GEOM_EXC:                                  # pragma: no cover
            continue
        out.append({
            "ring_ll": ll,
            "cap": float(z["cap"]),
            "buildings": int(z["buildings"]),
            "area_m2": round(float(z["area_m2"]), 1),
        })
    return out


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
    from auto_patch.adjacent_ground import (STACKED_WALL_RETREAT_M,
                                            runway_strip_wall_keepout)
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
        # THE SAME NUMBER ``terrace_station_edges`` bound the solve to —
        # literally the same function, so the binding and the report are
        # one quantity.
        bound = _joint_bound_m(joint)
        by_k = {st.k: st for st in joint.stations}
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
        joint.flank_span_m = round(STACKED_WALL_RETREAT_M, 3)
        joint.actual_step_m = round(float(drop), 4)
        # ENRICH IN PLACE — never replace.  The station list IS the
        # plan-time population the solve was bound to; the emitter adds
        # the settled levels it read and nothing else.  A grid station
        # the bind pass could not resolve still gets its reading (it is
        # part of the face) but carries no solve indices.
        for (k, s_arc, z_hi, z_lo) in rows:
            st = by_k.get(k)
            if st is None:
                st = TerraceStation(k, float(s_arc), None, None, bound,
                                    STACKED_WALL_RETREAT_M)
                by_k[k] = st
                joint.stations.append(st)
            st.z_pos = float(z_hi)
            st.z_neg = float(z_lo)
        joint.stations.sort(key=lambda st: st.k)
        # ── LEVEL JOINTS STILL COVER THEIR SLOT (item 4, 2026-08-05) ──
        # The panels settled LEVEL — only knowable post-solve — so this
        # joint's ALLOWANCE is DEMOTED to the step the surface actually
        # expresses (0 for this class): no unbacked relief survives the
        # drop, and ``faced`` stays False so §3(a) reads it that way.
        #
        # But it must still EMIT.  The pre-solve split cut a
        # ``STACKED_WALL_RETREAT_M`` band out of the apron; a joint that
        # returns here leaves that band as ground NO SHAPE COVERS —
        # measured at HECA: 14 of 79 declared joints demoted, and 21.2%
        # of the published slot area (629 m² over 70 bands) shipping
        # uncovered while a graded strip marched into 12.9% of it.  A
        # hole is not the absence of relief, it is a hole.  The cover is
        # minted from the SAME read rows as any other face — both levels
        # are already in hand here (the branch is unreachable with fewer
        # than two readings), so nothing is invented and nothing graded.
        level_only = drop <= 0.05
        if level_only:
            plan.stats["joints_demoted_level"] += 1
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
        if level_only:
            # COVER, not relief.  Same ref, so the validator judges it
            # through the same law (its across-band delta is ~0, well
            # inside ``step + cap·d``); ``faced`` stays False, so §3(a)
            # demotes the sidecar allowance to 0 exactly as before.
            plan.stats["level_covers_emitted"] = (
                plan.stats.get("level_covers_emitted", 0) + 1)
            continue
        joint.faced = True
    layout.shapes.extend(new_walls)
    plan.stats["faces_emitted"] = len(new_walls)
    # A declared joint whose band NOTHING covers is a hole in the apron:
    # the pre-solve split cut a retreat band out and no emitter closed
    # it.  Reported, never silent — this is the honest residue of item
    # 4's fix (joints the emitter could not read at all: fewer than two
    # station readings, rows of unequal length, or a keepout drop).
    plan.stats["slots_uncovered"] = len(plan.joints) - len(new_walls)
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
            "stations": [st.as_row() for st in j.stations],
            "reader_bound_m": (
                None if not j.stations
                else round(max(st.bound_m for st in j.stations), 4)),
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
