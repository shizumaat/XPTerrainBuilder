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
    "plan_apron_terraces",
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


def _nearest_station(grid, t: float) -> int:
    """Index of the station nearest arc-length ``t``."""
    best_k, best_d = 0, None
    for k, s in enumerate(grid):
        d = abs(s - t)
        if best_d is None or d < best_d:
            best_k, best_d = k, d
    return best_k


def _flank_window(nearest: float) -> float:
    """The sampling window for one flank: its own nearest row plus the
    slack that row's spacing implies."""
    return nearest + max(1.0, 0.25 * nearest)


def _level_at_joint(samples):
    """The settled level AT the joint line for one flank.

    ``samples`` is ``[(offset_m, z), …]`` for ONE side, offsets already
    absolute (distance from the joint line).  Returns the first-order fit
    evaluated at offset 0, or the plain mean when the samples are too few
    or too clustered to support a slope.

    This is the D2 fix: the previous reader returned ``mean(z)`` over a
    window that can reach ``_JOINT_FLANK_MAX_M``, so a lawfully
    cap-graded apron contributed ``cap · window`` of relief to what was
    then emitted as a VERTICAL face."""
    if not samples:
        return None
    if len(samples) < _JOINT_FIT_MIN_SAMPLES:
        return _mean(z for (_d, z) in samples)
    ds = [d for (d, _z) in samples]
    spread = max(ds) - min(ds)
    if spread < _JOINT_FIT_MIN_SPREAD_M:
        return _mean(z for (_d, z) in samples)
    n = float(len(samples))
    md = sum(ds) / n
    mz = sum(z for (_d, z) in samples) / n
    sdd = sum((d - md) ** 2 for d in ds)
    sdz = sum((d - md) * (z - mz) for (d, z) in samples)
    if sdd < 1e-9:
        return mz
    slope = sdz / sdd
    # WALK IN FROM THE NEAREST SAMPLE, AT NO MORE THAN THE CAP.  A bare
    # ``mz - slope*md`` is an EXTRAPOLATION: with every sample 100-150 m
    # from the joint, a noisy slope lands anywhere.  Measured, HECA:
    # emitted joint faces of 39.9 / 29.4 / 26.7 m — far worse than the
    # 5.5 m the flank MEAN produced.  The law itself supplies the bound:
    # from a settled vertex ``d`` metres away the surface at the joint
    # cannot differ by more than ``cap·d``, so the fitted slope decides
    # the DIRECTION and the cap decides how far.
    near_d, near_z = min(samples, key=lambda s: s[0])
    delta = -slope * near_d
    lim = APRON_MAX_GRADE * near_d
    if delta > lim:
        delta = lim
    elif delta < -lim:
        delta = -lim
    return near_z + delta


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
                 "panel_hi", "flank_pairs", "faced", "actual_step_m",
                 "flank_span_m", "line_ordinal", "stations")

    def __init__(self, line, step_m: float, shape_id: int,
                 line_ordinal: int = 0):
        self.line = [(float(x), float(y)) for (x, y) in line]
        self.step_m = float(step_m)
        self.shape_id = int(shape_id)
        self.geom = LineString(self.line)
        # Filled by ``apply_terrace_budgets`` once the panels are known.
        self.panel_lo: Optional[float] = None
        self.panel_hi: Optional[float] = None
        # ── §3(b) ONE COMPUTATION, TWO CONSUMERS ────────────────────
        # The plan-time straddling node pairs.  ``apply_terrace_budgets``
        # binds them into the ONE solve; ``emit_terrace_joint_faces``
        # reads its levels from the SAME population.  Nothing is derived
        # twice and the two halves cannot describe different ground.
        self.flank_pairs: list = []
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
            # §3(d) — PARKED, so these stay 0 (see
            # ``_split_lower_panels``).  Kept so the census schema does
            # not change shape while the split is out.
            "polygons_split": 0,
            "split_pieces_added": 0,
            "laps_kept_no_split": 0,
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


# ────────────────────────────────────────────────────────────────────
# 1.  THE TRIGGER — the component envelope, reused not re-invented
# ────────────────────────────────────────────────────────────────────

def _component_envelope(nodes, edges, anchors, values):
    """``(gap, lower, upper, witness_lo, witness_hi)`` for ONE constraint
    component, or ``None``.

    The same two-sided envelope ``one_solve._stall_envelope_gap``
    adjudicates a stalled carrier with — ``U(i) = min_a (v_a + d(a,i))``,
    ``L(i) = max_a (v_a − d(a,i))`` over the cap-weighted shortest path
    ``d`` — restricted to one component's own nodes and edges.  ``L > U``
    is exactly infeasibility.  Interval/box constraints are omitted, which
    can only REMOVE constraints, so a positive verdict is conservative and
    certain (the same argument as the production instrument).

    Pure Python Dijkstra with a heap: a component is a single apron
    (hundreds of nodes, thousands of edges), not the 272 k-edge system, so
    there is no scipy dependency and no whole-graph cost.
    """
    import heapq
    if not anchors:
        return None
    adjacency: dict[int, list[tuple[int, float]]] = {i: [] for i in nodes}
    for (a, b, budget) in edges:
        if a not in adjacency or b not in adjacency:
            continue
        w = float(budget)
        if w < 0.0:
            continue
        adjacency[a].append((b, w))
        adjacency[b].append((a, w))

    def _multi_source(offsets):
        dist = {i: math.inf for i in nodes}
        heap = []
        source = {}
        for a, off in offsets.items():
            if off < dist.get(a, math.inf):
                dist[a] = off
                source[a] = a
                heapq.heappush(heap, (off, a, a))
        while heap:
            d, i, src = heapq.heappop(heap)
            if d > dist[i] + 1e-12:
                continue
            for (j, w) in adjacency[i]:
                nd = d + w
                if nd < dist[j] - 1e-12:
                    dist[j] = nd
                    source[j] = src
                    heapq.heappush(heap, (nd, j, src))
        return dist, source

    v_min = min(values[a] for a in anchors)
    v_max = max(values[a] for a in anchors)
    up_dist, up_src = _multi_source({a: values[a] - v_min for a in anchors})
    lo_dist, lo_src = _multi_source({a: v_max - values[a] for a in anchors})
    gap: dict[int, float] = {}
    witness_lo: dict[int, int] = {}
    witness_hi: dict[int, int] = {}
    for i in nodes:
        u = v_min + up_dist[i]
        low = v_max - lo_dist[i]
        if not (math.isfinite(u) and math.isfinite(low)):
            continue
        gap[i] = low - u
        witness_lo[i] = lo_src.get(i, -1)
        witness_hi[i] = up_src.get(i, -1)
    if not gap:
        return None
    return gap, witness_lo, witness_hi, adjacency


def _cap_distance(adjacency, a, b):
    """Cap-weighted shortest path between two nodes (the LAW's own
    allowance for ``|z_a − z_b|``).  ``inf`` when disconnected."""
    import heapq
    if a == b:
        return 0.0
    dist = {a: 0.0}
    heap = [(0.0, a)]
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist.get(i, math.inf) + 1e-12:
            continue
        if i == b:
            return d
        for (j, w) in adjacency.get(i, ()):
            nd = d + w
            if nd < dist.get(j, math.inf) - 1e-12:
                dist[j] = nd
                heapq.heappush(heap, (nd, j))
    return math.inf


def _entry_edges(entry):
    """The entry's law edges INCLUDING a lazy tier's deferred body pairs.

    A flatness-certified entry carries only its ring pairs eagerly.  The
    trigger must see the body pairs — they are the long cross-apron chords
    the steep truth lives on — but expanding the thunk here would defeat
    the certificate.  A certified shape has a DEM gradient provably below
    ``0.6 · cap`` (``solver_primitives._certify_flat_shape``), i.e. it
    CANNOT carry the steep-truth signature, so the trigger reads its ring
    pairs only and will never fire on it.  That is a proof, not a
    shortcut: the certificate is the negation of the signature.
    """
    return [e for e in (entry.get("edges") or ()) if len(e) == 3]


def _raw_dem_steep_run(node_xy, node_dem, nodes):
    """``(run_m, slope)`` — the apron's own raw-DEM steep run.

    INSTRUMENT-INDEPENDENT by construction: DEM values and node positions,
    no envelope, no certificate, no anchor.  ``slope`` is the DEM drop
    between the shape's DEM extremes divided by their separation — the
    same reading the dossier quotes as "1.47 %" / "2.45 %" and the one the
    lead's annotation requires beside every instrument-derived number.
    """
    best_lo = best_hi = None
    for i in nodes:
        if i >= len(node_dem):
            continue
        z = node_dem[i]
        if z != z or node_xy.get(i) is None:
            continue
        if best_lo is None or z < node_dem[best_lo]:
            best_lo = i
        if best_hi is None or z > node_dem[best_hi]:
            best_hi = i
    if best_lo is None or best_hi is None or best_lo == best_hi:
        return 0.0, 0.0
    (ax, ay) = node_xy[best_lo]
    (bx, by) = node_xy[best_hi]
    run = math.hypot(bx - ax, by - ay)
    if run < 1.0:
        return run, 0.0
    return run, abs(float(node_dem[best_hi]) - float(node_dem[best_lo])) / run


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
    disagree about who is a neighbour."""
    from auto_patch.config import ROLE_GRADE_LIMITS
    poly = getattr(shape, "polygon", None)
    if poly is None or poly.is_empty:
        return []
    try:
        (x0, y0, x1, y1) = poly.bounds
    except _GEOM_EXC:
        return []
    pad = APRON_TERRACE_FACING_PROXIMITY_M + 1.0
    out = []
    for s in getattr(layout, "shapes", ()):
        if s is shape:
            continue
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


def _split_reach_line(line_pts, polygon, cover):
    """PARKED — NOT CALLED (the §3(d) split is out; see
    ``_split_lower_panels`` for the measured verdict and the revival
    precondition).

    The joint line extended for the §3(d) subtraction.

    Each end is pushed back out by ``_RETREAT_TRIM_M +
    _SPLIT_OVERSHOOT_M`` — but ONLY when that extension stays clear of
    the no-cross ``cover``.  An end that was cut by a corridor or a
    runway strip keeps its clearance and is left where it is; an end
    that simply ran out of apron gets its trim back, which is what makes
    the band reach the ring.

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


def _joint_flank_pairs(joint, member_nodes, node_xy):
    """§3(b) THE ONE COMPUTATION: straddling node pairs for one joint.

    Every node of the joint's own apron within ``_JOINT_FLANK_MAX_M`` of
    the joint line, inside the joint's own span, is assigned a side; each
    node on the positive side is paired with its NEAREST partner on the
    negative side.  Returns ``[(i, j, planar_m), …]`` deduplicated.

    Positions only — no values, so this runs at PLAN time and both the
    solver binding and the face emitter consume the identical
    population.  ``planar_m`` is the pair's own separation, which is what
    the law allows cap over: ``|z_i − z_j| ≤ step + cap·planar``.
    """
    (x0, y0) = joint.line[0]
    (x1, y1) = joint.line[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return []
    nx, ny = -dy / norm, dx / norm
    ux, uy = dx / norm, dy / norm
    pos, neg = [], []
    for i in member_nodes:
        p = node_xy.get(i)
        if p is None:
            continue
        (vx, vy) = p
        t = (vx - x0) * ux + (vy - y0) * uy
        if t < -_JOINT_FLANK_PAD_M or t > norm + _JOINT_FLANK_PAD_M:
            continue
        side = (vx - x0) * nx + (vy - y0) * ny
        if abs(side) > _JOINT_FLANK_MAX_M or abs(side) < _JOINT_ON_LINE_EPS_M:
            continue
        (pos if side > 0.0 else neg).append((i, vx, vy))
    if not pos or not neg:
        return []
    seen = set()
    out = []
    for (i, ax, ay) in pos:
        best = None
        for (j, bx, by) in neg:
            # RELIEF ONLY WHERE THE CHORD ACTUALLY STEPS OVER THE JOINT.
            # Straddling the joint's infinite LINE is not crossing its
            # finite RUN: a pair that passes around the joint's end steps
            # over nothing and keeps the full apron law.  Same predicate
            # as ``_rewrite_edges`` — one rule, no second population.
            # The NEAREST CROSSING partner is the pair that speaks for
            # the local step; a nearer non-crossing neighbour is not a
            # flank pair at all.
            if not _crossed_joints([joint], ax, ay, bx, by):
                continue
            d = math.hypot(bx - ax, by - ay)
            if best is None or d < best[0]:
                best = (d, j, bx, by)
        if best is None:
            continue
        key = (i, best[1]) if i < best[1] else (best[1], i)
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1], round(best[0], 4)))
    return out


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


def plan_apron_terraces(layout, shape_constraints, node_xy, node_dem,
                        elev, hard, icao: str = "") -> Optional[TerracePlan]:
    """THE TRIGGER + THE PANELIZATION (spec §1/§2).

    ``node_xy``: ``{index: (x, y)}`` in the layout metre frame.
    ``node_dem``: per-index DEM sample (list/array; NaN where unknown).
    ``elev``: the current per-index values (the anchors' declared values).
    ``hard``: the set of indices held hard in the pass that follows.

    Returns a ``TerracePlan`` (possibly empty) or ``None`` with the gate
    off.  Never raises: a geometry failure on one apron drops that apron
    from the plan and is counted, it does not fail a build.
    """
    if not apron_terrace_law_enabled():
        return None
    node_xy = _as_xy(node_xy)
    plan = TerracePlan()
    shapes_by_id = {id(s): s for s in getattr(layout, "shapes", ())}
    cover = corridor_cover(layout)
    plan.cover = cover
    # §3(a): the keepout the FACE will be tested against at emit time,
    # read HERE so admissibility is decided once, before any budget.
    keepout = None
    try:
        from auto_patch.adjacent_ground import runway_strip_wall_keepout
        keepout = runway_strip_wall_keepout(layout, require_gate=False)
    except (ImportError, AttributeError, *_GEOM_EXC):
        keepout = None
    debug = _os.environ.get("O4_APRON_TERRACE_DEBUG") == "1"
    for entry in shape_constraints:
        if entry.get("role") != ROLE_APRON:
            continue
        shape = shapes_by_id.get(entry.get("shape_id", -1))
        if shape is None:
            continue
        poly = getattr(shape, "polygon", None)
        if poly is None or poly.is_empty or poly.geom_type != "Polygon":
            continue
        try:
            plan.stats["apron_area_total"] += float(poly.area)
        except _GEOM_EXC:
            pass
        nodes = [i for i in (entry.get("nodes") or ())
                 if i < len(elev) and node_xy.get(i) is not None]
        if len(nodes) < 4:
            continue
        edges = _entry_edges(entry)
        if not edges:
            continue
        plan.stats["candidates"] += 1
        node_set = set(nodes)
        anchors = sorted(node_set & set(hard))
        # RAW-DEM READING — INSTRUMENT-INDEPENDENT (lead annotation
        # 2026-08-04: the envelope/certificate instrument behind the
        # trigger is under owner challenge, so every instrument-derived
        # number in this census is quoted BESIDE the raw one).  This is
        # DEM + geometry only: the apron's own steepest DEM chord and the
        # run it spans.  It never gates anything here — it is the
        # cross-check against the ``drain_worklist`` steep-run list.
        raw_run, raw_slope = _raw_dem_steep_run(node_xy, node_dem, nodes)
        row = {"ref": entry.get("ref", ""), "nodes": len(nodes),
               "edges": len(edges), "anchors": len(anchors),
               "excess": 0.0, "dem_grade": 0.0, "cap_grade": 0.0,
               "raw_dem_run_m": round(raw_run, 1),
               "raw_dem_slope": round(raw_slope, 5),
               "raw_steep": bool(raw_slope > APRON_MAX_GRADE),
               "verdict": "no_anchor", "joints": 0}
        # ── DEM-INFEASIBLE EDGE PREFILTER — sound, cheap, instrument-
        # independent.  If EVERY direct law edge satisfies the DEM within
        # its own budget, then along any path ``|dem_a − dem_b| ≤ Σ
        # budgets``, so it is ≤ the shortest-path allowance for every
        # pair: the steep-truth signature CANNOT hold anywhere in this
        # component and the envelope need not be run at all.  This is
        # what keeps the trigger O(|E|) on the aprons that are not the
        # fix population, and it is also the census's raw reading (lead
        # annotation: quote the raw beside the instrument).
        n_dem_infeasible = 0
        worst_dem_over = 0.0
        for (a, b, budget) in edges:
            if a >= len(node_dem) or b >= len(node_dem):
                continue
            za, zb = node_dem[a], node_dem[b]
            if za != za or zb != zb:
                continue
            over = abs(float(za) - float(zb)) - float(budget)
            if over > 0.0:
                n_dem_infeasible += 1
                worst_dem_over = max(worst_dem_over, over)
        row["dem_infeasible_edges"] = n_dem_infeasible
        row["dem_worst_over_m"] = round(worst_dem_over, 4)
        if n_dem_infeasible == 0:
            row["verdict"] = "dem_within_cap"
            plan.trigger_rows.append(row)
            continue
        if not anchors:
            plan.trigger_rows.append(row)
            continue
        env = _component_envelope(nodes, edges, anchors, elev)
        if env is None:
            row["verdict"] = "no_envelope"
            plan.trigger_rows.append(row)
            continue
        gap, witness_lo, witness_hi, adjacency = env
        worst_node, worst_gap = None, 0.0
        for i, g in gap.items():
            if g > worst_gap:
                worst_node, worst_gap = i, g
        row["excess"] = round(float(worst_gap), 6)
        if worst_node is None or worst_gap < APRON_TERRACE_MIN_EXCESS_M:
            row["verdict"] = ("below_floor" if worst_gap > 0.0
                              else "feasible")
            plan.trigger_rows.append(row)
            continue
        # ── STEEP-TRUTH SIGNATURE (spec §1) ──────────────────────────
        # The certificate path's DEM chord grade must exceed the cap that
        # path is held to: |DEM_a − DEM_b| > d_cap(a, b), where d_cap is
        # the law's OWN allowance for |z_a − z_b|.  An infeasibility whose
        # witnesses sit on ground the cap could span is a WRONG VALUE
        # (DOSSIER §1/§2/§5) and must not be panelized — those are the
        # seat/spine fixes, and terracing around them would bury the
        # defect under lawful-looking geometry.
        a_lo = witness_lo.get(worst_node, -1)
        a_hi = witness_hi.get(worst_node, -1)
        if a_lo < 0 or a_hi < 0 or a_lo == a_hi:
            row["verdict"] = "no_witness_pair"
            plan.trigger_rows.append(row)
            continue
        d_cap = _cap_distance(adjacency, a_lo, a_hi)
        dem_a = node_dem[a_lo] if a_lo < len(node_dem) else float("nan")
        dem_b = node_dem[a_hi] if a_hi < len(node_dem) else float("nan")
        if not (dem_a == dem_a and dem_b == dem_b
                and math.isfinite(d_cap)):
            row["verdict"] = "no_dem"
            plan.trigger_rows.append(row)
            continue
        dem_drop = abs(float(dem_a) - float(dem_b))
        row["dem_grade"] = round(dem_drop, 4)
        row["cap_grade"] = round(float(d_cap), 4)
        if dem_drop <= d_cap:
            # Real ground the cap CAN span ⇒ the infeasibility is a value
            # defect, not steep truth.  Reported, never panelized.
            row["verdict"] = "value_defect_not_steep"
            plan.trigger_rows.append(row)
            continue
        # ── PANELIZATION ────────────────────────────────────────────
        gradient = _dem_gradient(node_xy, node_dem, nodes)
        if gradient is None:
            row["verdict"] = "no_gradient"
            plan.trigger_rows.append(row)
            continue
        (gdir, plane_slope) = gradient
        # ── HOW MUCH RELIEF, AND FROM WHICH READING ─────────────────
        # The ENVELOPE decides WHETHER to panelize (spec §1, the trigger).
        # It does NOT decide HOW MANY panels: that is the ground's own
        # demand — "a panel whose bounding corridors demand more relief
        # than cap spans may take further interior terrace lines"
        # (spec §2) — and the ground is read from the DEM, not from an
        # instrument.  Measured at HEAZ arm A: the envelope excess on the
        # 600 m / 1.51 % apron was 1.55 m against a GEOMETRIC demand of
        # 3.06 m, so one joint was minted where the ground asks for two,
        # and the final-projection residue moved 944 → 855 against a
        # ≤700 partial band.  The lead's 2026-08-04 annotation names the
        # same hazard from the other side (the envelope instrument is
        # under owner challenge and may under-fire at specific aprons).
        # Both readings are carried, the LARGER sizes the panelization,
        # and both are in the census so the two can be compared.
        extent = _extent_along(poly, gdir)
        geom_excess = max(0.0, (plane_slope - APRON_MAX_GRADE) * extent)
        relief = max(float(worst_gap), geom_excess)
        row["geom_excess"] = round(geom_excess, 4)
        row["plane_slope"] = round(plane_slope, 5)
        row["extent_m"] = round(extent, 1)
        # ── §2(b) FIRE BOUNDED BY EVIDENCE ──────────────────────────
        # The certified relief divided by the max step is how many
        # terrace LINES this apron's own evidence supports.  Collinear
        # pieces of ONE line are one step, not several (a corridor
        # crossing the line splits it; it does not add relief), so the
        # bound is on lines and each piece records the line it came from.
        joint_count = max(1, int(math.ceil(
            relief / APRON_TERRACE_MAX_STEP_M)))
        step_m = min(APRON_TERRACE_MAX_STEP_M, relief / joint_count)
        # ── §3(c) CLEARANCE: joint lines keep the joint clearance from
        # FACING boundary runs, so no joint discharges its step at a
        # neighbour's face.  Folded into this apron's own cut cover.
        facing, _nb = _facing_boundary(layout, shape)
        cut_cover = cover
        if facing is not None and not facing.is_empty:
            try:
                fence = facing.buffer(APRON_TERRACE_JOINT_CLEARANCE_M)
                cut_cover = (fence if cut_cover is None
                             else unary_union([cut_cover, fence]))
            except _GEOM_EXC:
                pass
        minted = 0
        for ordinal, line in enumerate(_terrace_lines(poly, gdir,
                                                      joint_count)):
            pieces = _cut_joint_pieces(line, poly, cut_cover)
            if not pieces:
                plan.stats["joint_lines_lost_to_corridor"] += 1
                continue
            kept = 0
            for piece in pieces:
                if piece.length < APRON_TERRACE_MIN_JOINT_LEN_M:
                    plan.stats["joint_pieces_dropped_short"] += 1
                    continue
                pts = list(piece.coords)
                # ── §3(a) STILLBORN: unfaceable on BOTH sides ───────
                if not _face_admissible(pts, keepout):
                    plan.stats["joints_stillborn_keepout"] += 1
                    continue
                joint = TerraceJoint(pts, step_m, id(shape),
                                     line_ordinal=ordinal)
                joint.flank_pairs = _joint_flank_pairs(joint, nodes,
                                                       node_xy)
                plan.add(joint)
                kept += 1
                minted += 1
            if kept == 0:
                plan.stats["joint_lines_lost_to_corridor"] += 1
        row["joints"] = minted
        row["verdict"] = "panelized" if minted else "no_lawful_joint"
        if minted:
            plan.stats["triggered"] += 1
            try:
                plan.stats["apron_area_panelized"] += float(poly.area)
            except _GEOM_EXC:
                pass
            # ── §2(a) THE CERTIFICATE (hard invariant) ──────────────
            # An apron panelizes ONLY with the full recorded chain.  It
            # was already structural — every ``continue`` above is a
            # missing link — but it becomes AUDITABLE here: the row is
            # written into the sidecar so the twin can verify
            # "certificate-free panelization = 0" from the patch alone.
            plan.certificates[id(shape)] = {
                "ref": row["ref"],
                "dem_infeasible_edges": n_dem_infeasible,
                "dem_worst_over_m": row["dem_worst_over_m"],
                "envelope_excess_m": row["excess"],
                "steep_dem_drop_m": row["dem_grade"],
                "steep_cap_allow_m": row["cap_grade"],
                "raw_dem_run_m": row["raw_dem_run_m"],
                "raw_dem_slope": row["raw_dem_slope"],
                "relief_m": round(float(relief), 4),
                "max_step_m": APRON_TERRACE_MAX_STEP_M,
                "line_budget": joint_count,
                "lines_used": len({j.line_ordinal
                                   for j in plan.by_shape.get(id(shape),
                                                              ())}),
                "declared_step_m": round(float(step_m), 4),
                "joints": minted,
            }
            # ── §3(c) EXCLUSION population, resolved to node indices ─
            if facing is not None and not facing.is_empty:
                try:
                    band = facing.buffer(APRON_TERRACE_FACING_PROXIMITY_M)
                except _GEOM_EXC:
                    band = None
                if band is not None:
                    from shapely.geometry import Point as _Pt
                    fnodes = set()
                    for i in nodes:
                        p = node_xy.get(i)
                        if p is None:
                            continue
                        try:
                            if band.contains(_Pt(p[0], p[1])):
                                fnodes.add(i)
                        except _GEOM_EXC:
                            continue
                    if fnodes:
                        plan.facing_nodes[id(shape)] = fnodes
        plan.trigger_rows.append(row)
    if debug or _os.environ.get("O4_STEP_DEBUG") == "1":
        _report_plan(plan, icao)
    return plan


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
        if row["verdict"] in ("feasible", "below_floor", "dem_within_cap"):
            continue
        print(f"    [apron-terrace]   {row['ref'] or '(no ref)'}: "
              f"{row['verdict']} nodes={row['nodes']} "
              f"anchors={row['anchors']} excess={row['excess']:.3f} "
              f"dem_drop={row['dem_grade']:.3f} "
              f"cap_allow={row['cap_grade']:.3f} joints={row['joints']} "
              f"| RAW DEM run={row['raw_dem_run_m']:.0f} m slope="
              f"{row['raw_dem_slope'] * 100:.2f} % "
              f"({'steep' if row['raw_steep'] else 'gradeable'}), "
              f"DEM-infeasible edges={row.get('dem_infeasible_edges', 0)} "
              f"worst over={row.get('dem_worst_over_m', 0.0):.3f} m"
              + (f" | GEOM relief demand={row['geom_excess']:.3f} m "
                 f"(plane {row['plane_slope'] * 100:.2f} % over "
                 f"{row['extent_m']:.0f} m)"
                 if "geom_excess" in row else ""))


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


def _bind_joint_step_pairs(edges, joints, node_xy, facing_nodes=None):
    """§3(b) GENERATION-BINDING: the joint-step pair constraints.

    Each declared joint binds its plan-time straddling pairs to
    ``|z_m − z_n| ≤ step_m + cap·planar(m, n)`` — the identical rule the
    within-pair reader applies, on the identical population the FACE is
    read from.  ``APRON_TERRACE_MAX_STEP_M`` then bounds the EMITTED
    surface transitively: nothing generation-side bounded the settled
    flank delta before, and the validator read the DECLARED step, so
    HECA shipped 10 faces of 2.14-5.52 m against declared ≤1.994 m.

    THE BINDING TIGHTENS EDGES THE LAW ALREADY HAS; IT NEVER ADDS ONE.
    That distinction is the whole clause, and it is MEASURED, not
    assumed: an earlier form of this function appended the pairs as NEW
    law edges, which constrains node pairs the apron's visibility graph
    deliberately leaves unconstrained — and at a STRAIGHT-LINE distance
    shorter than the lawful graph path, so the invented edge is tighter
    than the law it claims to express.  HEAZ, single-clause arm:
    78 → 1,360 law-true rows.  A pair that is not a law pair is not a
    law pair.

    Returns ``(edges, n_bound)``; ``edges`` is the same list object shape
    with tightened budgets where the clause bites (in practice a no-op
    for a pair crossing exactly its own joint — the rewritten budget is
    already ``cap·d + step`` — and a genuine tightening for a flank pair
    that ``_rewrite_edges`` handed the steps of SEVERAL joints).
    """
    if not joints:
        return edges, 0
    fn = facing_nodes or ()
    want: dict = {}
    for j in joints:
        for (m, n, d) in (j.flank_pairs or ()):
            if node_xy.get(m) is None or node_xy.get(n) is None:
                continue
            if m in fn or n in fn:
                continue                  # §3(c): facing runs keep full law
            key = (m, n) if m < n else (n, m)
            bound = float(j.step_m) + APRON_MAX_GRADE * float(d)
            if key not in want or bound < want[key]:
                want[key] = bound
    if not want:
        return edges, 0
    out = []
    n_bound = 0
    for e in edges:
        if len(e) != 3:
            out.append(e)
            continue
        a, b, budget = e
        key = (a, b) if a < b else (b, a)
        cap_here = want.get(key)
        if cap_here is not None and cap_here < float(budget) - 1e-12:
            out.append((a, b, cap_here))
            n_bound += 1
        else:
            out.append(e)
    return out, n_bound


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
        joints = plan.by_shape.get(shape_id)
        if not joints:
            continue
        facing = plan.facing_nodes.get(shape_id) or set()
        excl = [0]
        edges, touched = _rewrite_edges(entry.get("edges") or [], joints,
                                        node_xy, facing_nodes=facing,
                                        excluded_out=excl)
        plan.stats["facing_edges_excluded"] += excl[0]
        # ── §3(b) the joint-step pair constraints join the ONE solve ──
        edges, n_bound = _bind_joint_step_pairs(edges, joints, node_xy,
                                                facing_nodes=facing)
        plan.stats["joint_step_pairs"] += n_bound
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


def emit_terrace_joint_faces(layout, plan: Optional[TerracePlan]) -> int:
    """Mint one ``retaining_wall`` face per declared joint run whose two
    sides actually settled at different levels (spec §3).

    The face occupies the ``STACKED_WALL_RETREAT_M`` band on the LOWER
    side of the joint — the same machine and the same constants as
    ``adjacent_ground.emit_stacked_conflict_walls``.  The apron polygon
    is NOT cut back: the §3(d) split was REMOVED (lead 2026-08-05 —
    measured to mint 5 defects because its new ring vertices adopted the
    FACE's level, a value the solve never produced), so the face laps
    that 0.6 m band.  The lap (HECA 2 479 m²) is named emit-round debt,
    not a defect this pass may paper over.  Called BEFORE interning, so
    the emit consensus can never average a joint away.

    D2: the face is read and minted PER STATION (``_station_grid``) —
    one level pair for a 500 m joint was the mechanism behind the 6.0 m
    faces.  Each station carries its own lawful bound in the sidecar;
    nothing is clamped.

    Runway-strip fence (owner 2026-08-01, and spec §5(d)): a face inside a
    runway strip footprint is inadmissible and is dropped here as well as
    flagged by the validator — walls at runway edges are NEVER lawful.
    """
    if plan is None or not plan.joints:
        return 0
    from auto_patch.adjacent_ground import (STACKED_WALL_RETREAT_M,
                                            runway_strip_wall_keepout)
    from auto_patch.layout import BuiltShape
    keepout = runway_strip_wall_keepout(layout, require_gate=False)
    shapes_by_id = {id(s): s for s in getattr(layout, "shapes", ())}
    new_walls: list = []
    plan.stats["faces_dropped_keepout"] = 0
    plan.stats["joints_demoted_level"] = 0
    plan.stats.setdefault("station_readings", 0)
    plan.stats.setdefault("stations_over_bound", 0)
    plan.stats.setdefault("joints_sign_flipped", 0)
    for joint in plan.joints:
        shape = shapes_by_id.get(joint.shape_id)
        if shape is None:
            continue
        rv = _ring_values(shape)
        if rv is None:
            continue
        coords, alts = rv
        # Level on each side of the joint, from the settled ring values.
        (x0, y0) = joint.line[0]
        (x1, y1) = joint.line[-1]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy)
        if norm < 1e-9:
            continue
        nx, ny = -dy / norm, dx / norm
        ux, uy = dx / norm, dy / norm
        # The level ON EACH SIDE, read from the ring vertices that flank
        # the joint.  NEAREST-FLANK, not a fixed band: apron ring spacing
        # runs from a metre to a hundred, and a fixed radius would read
        # one side only (measured on the synthetic twin at 50 m spacing —
        # the whole face silently vanished).  A vertex counts when its
        # station along the joint lies within the joint's own span.
        # D2: the samples are bucketed by STATION (the plan-time
        # densification of the panel boundary), so one long joint is read
        # as the several local steps it actually is.
        grid = _station_grid(norm)
        buckets = [([], []) for _ in grid]
        for (vx, vy), value in zip(coords, alts):
            t = (vx - x0) * ux + (vy - y0) * uy
            if t < -_JOINT_FLANK_PAD_M or t > norm + _JOINT_FLANK_PAD_M:
                continue
            side = (vx - x0) * nx + (vy - y0) * ny
            if abs(side) > _JOINT_FLANK_MAX_M:
                continue
            if abs(side) < _JOINT_ON_LINE_EPS_M:
                continue          # ON the joint: belongs to neither panel
            k = _nearest_station(grid, t)
            (buckets[k][0] if side > 0.0 else buckets[k][1]).append(
                (abs(side), value))
        # ── D2: ONE LEVEL PAIR PER STATION, NOT ONE PER JOINT ────────
        # The v2 reader took ONE level per side for the WHOLE joint, from
        # a flank window whose nearest rows can be 100 m+ away.  On a
        # 500 m joint that is a single extrapolation speaking for the
        # whole run, and it is how HECA shipped 6.0 m faces against a
        # 1.994 m declaration.  Each station now reads its OWN two
        # nearest settled rows and carries its OWN lawful bound
        # ``step + cap·(d_pos + d_neg)`` — the declaration plus exactly
        # the relief the cap licenses over the distance the reader had to
        # cross.  Nothing is clamped: a station over its own bound is a
        # LOUD row, because clamping would mint a face level the solve
        # never produced (the same defect that retired the §3(d) split).
        st_levels: list = []          # (s, z_pos, z_neg, span, bound)
        for k, s in enumerate(grid):
            pos, neg = buckets[k]
            if not pos or not neg:
                continue
            pos.sort()
            neg.sort()
            win_pos = [(d, v) for (d, v) in pos
                       if d <= _flank_window(pos[0][0])]
            win_neg = [(d, v) for (d, v) in neg
                       if d <= _flank_window(neg[0][0])]
            z_pos = _level_at_joint(win_pos)
            z_neg = _level_at_joint(win_neg)
            if z_pos is None or z_neg is None:
                continue
            span = pos[0][0] + neg[0][0]
            # THE LAW'S BOUND is the declaration plus the cap over the
            # face's OWN width — a wall may be as tall as the step it
            # declares, never as tall as the distance its reader had to
            # travel.  The reader distance is reported BESIDE it
            # (``reader_slack_m``) so a station over the bound can be
            # attributed to the reading rather than argued about.
            st_levels.append((s, float(z_pos), float(z_neg), float(span),
                              float(joint.step_m)
                              + APRON_MAX_GRADE * _RETREAT_TRIM_M))
        if not st_levels:
            continue
        worst = max(st_levels, key=lambda r: abs(r[1] - r[2]))
        drop = abs(worst[1] - worst[2])
        joint.flank_span_m = round(worst[3], 3)
        joint.actual_step_m = round(float(drop), 4)
        joint.stations = [
            {"s": round(s, 2), "z_pos": round(zp, 3), "z_neg": round(zn, 3),
             "span_m": round(sp, 3), "bound_m": round(bd, 4),
             "reader_slack_m": round(APRON_MAX_GRADE * sp, 4),
             "over_m": round(max(0.0, abs(zp - zn) - bd), 4)}
            for (s, zp, zn, sp, bd) in st_levels]
        n_over = sum(1 for r in joint.stations if r["over_m"] > 0.0)
        plan.stats["station_readings"] += len(st_levels)
        plan.stats["stations_over_bound"] += n_over
        if drop <= 0.05:
            # §3(a): FLANKS SETTLED LEVEL.  Only knowable post-solve, so
            # this joint emits no face — and its sidecar allowance is
            # DEMOTED to the step the surface actually expresses (0 for
            # this class), so the validator grants exactly what the
            # geometry shows.  No unbacked relief survives the drop.
            plan.stats["joints_demoted_level"] += 1
            continue
        # The LOWER panel is the one the majority of stations put lower;
        # a joint whose sign FLIPS along its run is counted (its face
        # would have to cross the joint) and takes the majority side.
        n_pos_low = sum(1 for (_s, zp, zn, _sp, _bd) in st_levels
                        if zp < zn)
        if 0 < n_pos_low < len(st_levels):
            plan.stats["joints_sign_flipped"] += 1
        low_sign = 1.0 if n_pos_low * 2 >= len(st_levels) else -1.0
        rx, ry = nx * low_sign * STACKED_WALL_RETREAT_M, \
            ny * low_sign * STACKED_WALL_RETREAT_M
        # THE FACE FOLLOWS THE STATIONS.  Top row on the joint line at
        # each station's own arc-length, bottom row the same points
        # retreated onto the low side; each vertex carries ITS station's
        # settled level, so the wall expresses the panels it separates
        # instead of one flat pair of numbers.  (The §3(d) polygon split
        # is REMOVED — see ``_split_lower_panels`` — so the band laps the
        # apron; that lap is the accepted emit-round debt.)
        top = [(x0 + ux * s, y0 + uy * s) for (s, *_r) in st_levels]
        if len(top) < 2:
            # A single-station joint still needs two points to bound a
            # face: use the joint's own endpoints.
            top = [joint.line[0], joint.line[-1]]
            st_face = [st_levels[0], st_levels[0]]
        else:
            st_face = st_levels
        bot = [(x + rx, y + ry) for (x, y) in top]
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
                    # §3(a) LOUD COUNTER — this MUST read 0.  With the
                    # §1 fence in the panelizer no joint can be in a
                    # strip at all, and plan-time admissibility proved
                    # this side (or the other) faceable before the joint
                    # was minted.  A hit here means the plan-time
                    # predicate and this one diverged: a FRAME BUG, and
                    # a STOP for the round.  The defense-in-depth drop
                    # stays (a wall in a strip is never lawful), but the
                    # allowance dies with it — the joint is demoted.
                    plan.stats["faces_dropped_keepout"] += 1
                    joint.actual_step_m = 0.0
                    continue
            except _GEOM_EXC:
                continue
        ring_pts = list(wall_poly.exterior.coords)[:-1]
        if len(ring_pts) < 3:
            continue
        # Each emitted ring vertex takes the level of the STATION it sits
        # at, on the side it sits on — a nearest-station read over the
        # face's own points, never an average.
        wall_alts = []
        for (vx, vy) in ring_pts:
            t = (vx - x0) * ux + (vy - y0) * uy
            side = (vx - x0) * nx + (vy - y0) * ny
            on_low = (side * low_sign) > 0.25 * STACKED_WALL_RETREAT_M
            best = min(st_face, key=lambda r: abs(r[0] - t))
            z_lo = min(best[1], best[2])
            z_hi = max(best[1], best[2])
            wall_alts.append(round(z_lo if on_low else z_hi, 1))
        new_walls.append(BuiltShape(
            polygon=wall_poly, role=ROLE_RETAINING_WALL,
            ref="apron_terrace_joint",
            node_altitudes=wall_alts + [wall_alts[0]]))
        joint.panel_lo = round(min(worst[1], worst[2]), 3)
        joint.panel_hi = round(max(worst[1], worst[2]), 3)
        joint.faced = True
    layout.shapes.extend(new_walls)
    plan.stats["faces_emitted"] = len(new_walls)
    return len(new_walls)


def _split_lower_panels(layout, plan, retreat_bands) -> None:
    """PARKED — NOT CALLED (lead direction 2026-08-05).

    PRECONDITION FOR REVIVAL: interior-ring emit support, plus a panel
    boundary that exists BEFORE the solve.  Measured verdict that parked
    it: with the split the terrace law minted 5 defects, because the
    difference introduces ring vertices that then adopt the FACE's level
    — a value the solve never produced, which violates the architecture's
    solve-value discipline (a ring vertex only ever carries a
    solve-produced value).  Without it terrace improves every airport on
    both sides (HECA airside −2 356 / groundside −92, KCLT −27,
    HEAZ −9).  The 2 479 m² lap it would have cleared is named cosmetic
    debt for the emit round.  Kept verbatim because the geometry is
    correct and the revival is a scheduling question, not a redesign.

    §3(d): the LOWER panel's apron polygon retreats by the settled
    wall band, so the face no longer laps live apron surface.

    Each settled ``wall_poly`` is subtracted from its apron; the ring
    adopts the wall's own vertices by CANONICAL JOIN (the wall's
    coordinates verbatim — shared vertices are byte-equal, never
    proximity-joined), and each adopted vertex takes the wall's own level
    for its side.  No lap, no naked step.  Measured lap before this:
    HECA 6,222 m² of doubled surface along the 0.6 m band.

    A difference that separates the apron into several pieces mints
    sibling apron shapes rather than dropping surface — losing pavement
    to a geometry op is never the lawful answer.
    """
    if not retreat_bands:
        return
    from auto_patch.layout import BuiltShape
    shapes_by_id = {id(s): s for s in getattr(layout, "shapes", ())}
    added: list = []
    for shape_id, bands in retreat_bands.items():
        shape = shapes_by_id.get(shape_id)
        if shape is None:
            continue
        rv = _ring_values(shape)
        if rv is None:
            continue
        coords, alts = rv
        # canonical join: the ORIGINAL ring's own vertices keep their own
        # settled values, keyed by exact coordinate spelling.
        by_pos = {(round(x, 6), round(y, 6)): z
                  for ((x, y), z) in zip(coords, alts)}
        # BAND BY BAND, each subtraction accepted only when it leaves a
        # HOLE-FREE result.  A band that would punch an interior ring is
        # REVERTED and counted: ``to_osm`` drops interior rings, so
        # subtracting one there would remove nothing from the patch
        # while pretending the lap was cleared.  Honest counter, never a
        # silent no-op.
        current = shape.polygon
        n_applied = 0
        for band in bands:
            try:
                nxt = current.difference(band[0])
            except _GEOM_EXC:
                plan.stats["laps_kept_no_split"] += 1
                continue
            if nxt.is_empty:
                plan.stats["laps_kept_no_split"] += 1
                continue
            cand = ([nxt] if nxt.geom_type == "Polygon"
                    else [g for g in getattr(nxt, "geoms", ())
                          if g.geom_type == "Polygon" and not g.is_empty])
            if not cand or any(len(g.interiors) for g in cand):
                plan.stats["laps_kept_no_split"] += 1
                continue
            current = nxt
            n_applied += 1
        if not n_applied:
            continue
        pieces = ([current] if current.geom_type == "Polygon"
                  else [g for g in getattr(current, "geoms", ())
                        if g.geom_type == "Polygon" and not g.is_empty])
        if not pieces:
            continue
        pieces.sort(key=lambda p: -p.area)

        def _value_at(px, py):
            v = by_pos.get((round(px, 6), round(py, 6)))
            if v is not None:
                return v
            # A vertex the difference INTRODUCED: it lies on a wall
            # band's boundary, so it takes that wall's own level for the
            # side it is on — the wall's numbers verbatim, which is what
            # makes the ring and the face share one step instead of two.
            best = None
            probe = _Point(px, py)
            for (wp, z_low, z_high, (jx, jy), (nx, ny), low_sign,
                 retreat) in bands:
                try:
                    d = wp.exterior.distance(probe)
                except _GEOM_EXC:
                    continue
                if best is None or d < best[0]:
                    side = (px - jx) * nx + (py - jy) * ny
                    on_low = (side * low_sign) > 0.25 * retreat
                    best = (d, z_low if on_low else z_high)
            if best is not None and best[0] <= 1.0:
                return best[1]
            # Off every band (a corner the union rounded): fall back to
            # the nearest ORIGINAL ring vertex — the closest thing the
            # solve actually settled.
            near = None
            for ((x, y), z) in zip(coords, alts):
                d = math.hypot(x - px, y - py)
                if near is None or d < near[0]:
                    near = (d, z)
            return near[1] if near else 0.0

        def _alts_for(poly):
            ring = list(poly.exterior.coords)
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            vals = [round(float(_value_at(x, y)), 1) for (x, y) in ring]
            return vals + [vals[0]] if vals else None

        first_alts = _alts_for(pieces[0])
        if not first_alts:
            continue
        shape.polygon = pieces[0]
        shape.node_altitudes = first_alts
        shape.altitude = None
        shape.altitude_high = None
        shape.altitude_low = None
        plan.stats["polygons_split"] += 1
        for extra in pieces[1:]:
            extra_alts = _alts_for(extra)
            if not extra_alts:
                continue
            added.append(BuiltShape(
                polygon=extra, role=shape.role, ref=shape.ref,
                node_altitudes=extra_alts))
            plan.stats["split_pieces_added"] += 1
    if added:
        layout.shapes.extend(added)


# ────────────────────────────────────────────────────────────────────
# 6.  THE VALIDATOR'S HALF — the sidecar
# ────────────────────────────────────────────────────────────────────

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
