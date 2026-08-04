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

Gate ``O4_APRON_TERRACE_LAW`` (``config.APRON_TERRACE_LAW_ENABLED``),
default OFF.  Every entry point returns immediately with the gate off, so
the emitted patch is byte-identical.
"""
from __future__ import annotations

import math
import os as _os
from typing import Optional

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from auto_patch.config import (
    APRON_MAX_GRADE,
    APRON_TERRACE_CORRIDOR_HALF_WIDTH_M,
    APRON_TERRACE_JOINT_CLEARANCE_M,
    APRON_TERRACE_LAW_ENABLED,
    APRON_TERRACE_MAX_STEP_M,
    APRON_TERRACE_MIN_EXCESS_M,
    APRON_TERRACE_MIN_JOINT_LEN_M,
    APRON_TERRACE_OVERFIRE_AREA_FRAC,
)

_GEOM_EXC = (ValueError, GEOSException, TopologicalError, AttributeError)

__all__ = [
    "apron_terrace_law_enabled",
    "plan_apron_terraces",
    "apply_terrace_budgets",
    "emit_terrace_joint_faces",
    "terrace_joints_sidecar",
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


def _flank_window(nearest: float) -> float:
    """The sampling window for one flank: its own nearest row plus the
    slack that row's spacing implies."""
    return nearest + max(1.0, 0.25 * nearest)


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
    """The gate, read at CALL time (so tests and the A/B harness can
    toggle it in-process; ``config`` snapshots the env at import)."""
    env = _os.environ.get("O4_APRON_TERRACE_LAW")
    if env is not None:
        return env == "1"
    return bool(APRON_TERRACE_LAW_ENABLED)


class TerraceJoint:
    """One declared terrace joint: a polyline inside ONE apron, provably
    disjoint from every taxi corridor, carrying a declared step height.

    ``line`` is an open list of ``(x, y)`` in the layout's metre frame.
    ``step_m`` is the level change the law permits ACROSS this joint, on
    top of the ordinary cap allowance for the chord's own length.
    """

    __slots__ = ("line", "step_m", "shape_id", "geom", "panel_lo",
                 "panel_hi")

    def __init__(self, line, step_m: float, shape_id: int):
        self.line = [(float(x), float(y)) for (x, y) in line]
        self.step_m = float(step_m)
        self.shape_id = int(shape_id)
        self.geom = LineString(self.line)
        # Filled by ``apply_terrace_budgets`` once the panels are known.
        self.panel_lo: Optional[int] = None
        self.panel_hi: Optional[int] = None

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
        self.stats: dict = {
            "candidates": 0, "triggered": 0, "joints": 0,
            "joint_pieces_dropped_short": 0,
            "joint_lines_lost_to_corridor": 0,
            "apron_area_total": 0.0, "apron_area_panelized": 0.0,
            "faces_emitted": 0,
        }

    def add(self, joint: TerraceJoint) -> None:
        self.joints.append(joint)
        self.by_shape.setdefault(joint.shape_id, []).append(joint)
        self.stats["joints"] += 1

    def overfire_fraction(self) -> float:
        total = self.stats["apron_area_total"]
        if total <= 0.0:
            return 0.0
        return self.stats["apron_area_panelized"] / total

    def is_overfire(self) -> bool:
        return self.overfire_fraction() > APRON_TERRACE_OVERFIRE_AREA_FRAC


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

def corridor_cover(layout, polygon=None):
    """The NO-CROSS set: every taxi/route centerline (apt.dat + OSM,
    ground-vehicle SVC spines INCLUDED) buffered by the corridor
    half-width plus the joint clearance, PLUS every building frontage
    chord (``reach-follows-centerlines``: stands are aircraft travel, so a
    stand's frontage chord is a route).

    SERVICE SPINES ARE IN THE SET (spec interaction fence): "a wall across
    a vehicle route is still a wall".  Whether service routes may relax is
    an INTENT question for the owner; the conservative side is the side
    that mints fewer joints, and this is it.

    Returns a prepared-ish shapely geometry (or ``None`` when the layout
    has no corridor at all).
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
    if not pieces:
        return None
    try:
        cover = unary_union(pieces).buffer(half)
    except _GEOM_EXC:
        return None
    if cover.is_empty:
        return None
    if polygon is not None:
        try:
            cover = cover.intersection(polygon.buffer(1.0))
        except _GEOM_EXC:
            pass
    return cover


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
        joint_count = max(1, int(math.ceil(
            relief / APRON_TERRACE_MAX_STEP_M)))
        step_m = min(APRON_TERRACE_MAX_STEP_M, relief / joint_count)
        minted = 0
        for line in _terrace_lines(poly, gdir, joint_count):
            pieces = _cut_joint_pieces(line, poly, cover)
            if not pieces:
                plan.stats["joint_lines_lost_to_corridor"] += 1
                continue
            kept = 0
            for piece in pieces:
                if piece.length < APRON_TERRACE_MIN_JOINT_LEN_M:
                    plan.stats["joint_pieces_dropped_short"] += 1
                    continue
                plan.add(TerraceJoint(list(piece.coords), step_m,
                                      id(shape)))
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
          f"apron area panelized {plan.overfire_fraction() * 100:.1f} % "
          f"({'OVER-FIRE' if plan.is_overfire() else 'within band'})")
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


def _rewrite_edges(edges, joints, node_xy):
    """``cap·d`` → ``cap·d + Σ step`` on every edge crossing a joint.

    RELAXING ONLY.  An edge that crosses no joint is returned byte-
    identical, so every within-panel pair and every pair on or through a
    corridor keeps the full apron law (spec §4: "within-panel edges keep
    the full apron law ... corridor nodes remain global route members").
    Returns ``(new_edges, n_joint_edges)``.
    """
    if not joints:
        return edges, 0
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
        hits = _crossed_joints(joints, pa[0], pa[1], pb[0], pb[1])
        if not hits:
            out.append(e)
            continue
        out.append((a, b, float(budget) + sum(j.step_m for j in hits)))
        touched += 1
    return out, touched


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
    for entry in shape_constraints:
        joints = plan.by_shape.get(entry.get("shape_id", -1))
        if not joints:
            continue
        edges, touched = _rewrite_edges(entry.get("edges") or [], joints,
                                        node_xy)
        entry["edges"] = edges
        total += touched
        nodes = [i for i in (entry.get("nodes") or ())
                 if node_xy.get(i) is not None]
        if nodes:
            plan.panels[entry.get("shape_id", -1)] = _panel_components(
                nodes, edges, joints, node_xy)
        if nodes:
            plan.node_sets[entry.get("shape_id", -1)] = set(nodes)
        thunk = entry.get("lazy_expand")
        if thunk is not None:
            def _bound(_t=thunk, _j=joints, _xy=node_xy):
                return _rewrite_edges(list(_t()), _j, _xy)[0]
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
        bound, touched = _rewrite_edges(scoped, joints, node_xy)
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
    is NOT cut back (approved deviation, adjudication 768cded): the face
    laps that band of apron surface until the default-ON round lands the
    polygon split.  Called BEFORE interning, so the emit consensus can
    never average a joint away.

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
        pos, neg = [], []
        for (vx, vy), value in zip(coords, alts):
            t = (vx - x0) * ux + (vy - y0) * uy
            if t < -_JOINT_FLANK_PAD_M or t > norm + _JOINT_FLANK_PAD_M:
                continue
            side = (vx - x0) * nx + (vy - y0) * ny
            if abs(side) > _JOINT_FLANK_MAX_M:
                continue
            if abs(side) < _JOINT_ON_LINE_EPS_M:
                continue          # ON the joint: belongs to neither panel
            (pos if side > 0.0 else neg).append((abs(side), value))
        if not pos or not neg:
            continue
        pos.sort()
        neg.sort()
        # Only the flank ROW closest to the joint speaks for its panel: a
        # sample far behind it is panel interior, where the ordinary 1 %
        # law has already moved it off the joint's level.  EACH SIDE
        # against ITS OWN nearest — a shared threshold silently emptied
        # the far side and shipped a 0.0 m panel level into the sidecar
        # (caught on the first HEAZ arm, twinned in the suite).
        z_pos = _mean(v for (d, v) in pos if d <= _flank_window(pos[0][0]))
        z_neg = _mean(v for (d, v) in neg if d <= _flank_window(neg[0][0]))
        drop = abs(z_pos - z_neg)
        if drop <= 0.05:
            continue                      # no level change: no wall
        # The LOWER panel retreats.
        low_sign = 1.0 if z_pos < z_neg else -1.0
        z_low = min(z_pos, z_neg)
        z_high = max(z_pos, z_neg)
        rx, ry = nx * low_sign * STACKED_WALL_RETREAT_M, \
            ny * low_sign * STACKED_WALL_RETREAT_M
        top = list(joint.line)
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
                    continue              # runway-strip wall law
            except _GEOM_EXC:
                continue
        ring_pts = list(wall_poly.exterior.coords)[:-1]
        if len(ring_pts) < 3:
            continue
        wall_alts = []
        for (vx, vy) in ring_pts:
            side = (vx - x0) * nx + (vy - y0) * ny
            on_low = (side * low_sign) > 0.25 * STACKED_WALL_RETREAT_M
            wall_alts.append(round(z_low if on_low else z_high, 1))
        new_walls.append(BuiltShape(
            polygon=wall_poly, role=ROLE_RETAINING_WALL,
            ref="apron_terrace_joint",
            node_altitudes=wall_alts + [wall_alts[0]]))
        joint.panel_lo = round(z_low, 3)
        joint.panel_hi = round(z_high, 3)
    layout.shapes.extend(new_walls)
    plan.stats["faces_emitted"] = len(new_walls)
    return len(new_walls)


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
        rows.append({
            "points": [[round(la, 11), round(lo, 11)] for (la, lo) in pts],
            "step_m": round(float(j.step_m), 4),
            "panel_lo": j.panel_lo,
            "panel_hi": j.panel_hi,
        })
    return rows
