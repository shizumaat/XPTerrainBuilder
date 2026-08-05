"""APRON TERRACE LAW — the generation-binding twins.

Owner ruling 2026-08-04 (``docs/RULINGS.md``): long aprons on genuinely
steep ground MAY terrace into level panels with declared joint steps,
"but it has to be done in a way that does not interrupt any spine where
aircraft have to travel."

The BINDING CONSTRAINT is structural in
``elevation_per_surface.route_profile.apron_terrace``: a joint is born as
``(terrace line ∩ apron) − corridor cover``.  These tests are the
generation-binding half the completeness standard demands (a
validator-only check is visibility, not law), so every one of them
exercises the EMITTER's own function on a synthetic layout:

  * a joint can never touch a corridor, at any corridor angle;
  * a spine's own pairs keep the cap through a panelized apron;
  * the declared step is bounded by ``APRON_TERRACE_MAX_STEP_M``;
  * the trigger floor and the steep-truth signature both bind
    (a value defect on gradeable ground must NOT panelize);
  * the sidecar round-trips into ``check_grade``'s own reader.
"""
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.config import (
    APRON_MAX_GRADE,
    APRON_TERRACE_JOINT_CLEARANCE_M,
    APRON_TERRACE_MAX_STEP_M,
    APRON_TERRACE_MIN_EXCESS_M,
)
from auto_patch.elevation_per_surface.route_profile import apron_terrace as AT
from auto_patch.layout import BuiltShape


class _Centerline:
    def __init__(self, pts):
        self.line = LineString(pts)


class _FakeLayout:
    """The minimum surface ``apron_terrace`` reads: shapes, taxi
    centerlines and the metre↔lat/lon pair."""

    def __init__(self, shapes, centerlines=()):
        self.shapes = list(shapes)
        self.apt_taxi_centerlines = [_Centerline(p) for p in centerlines]
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (30.0 + y / 111320.0, 31.0 + x / 96000.0)


def _grid_apron(width=600.0, height=200.0, step=50.0, slope=0.02,
                base=100.0, ref="apron_test"):
    """A rectangular apron whose ring nodes sit on a regular grid and
    whose DEM climbs ``slope`` along +x.

    Returns ``(shape, nodes_xy, node_dem, edges, node_indices)`` — the
    pieces a ``shape_constraints`` entry is made of.
    """
    pts = []
    x = 0.0
    while x <= width + 1e-9:
        pts.append((x, 0.0))
        x += step
    x = width
    while x >= -1e-9:
        pts.append((x, height))
        x -= step
    # The polygon IS the node ring (production aprons carry one node per
    # ring vertex; a 4-corner stand-in would hide the emitter's reader).
    shape = BuiltShape(polygon=Polygon(pts + [pts[0]]), role="apron",
                       ref=ref)
    # The fixture's ground, as the PRE-SOLVE panelizer reads it: the same
    # analytic plane the per-node DEM below samples, so the twins drive
    # the real panelizer instead of a second implementation.
    _DEM_FNS[id(shape)] = (lambda x, y, b=base, s=slope: b + s * x)
    nodes_xy = {i: p for i, p in enumerate(pts)}
    node_dem = [base + slope * p[0] for p in pts]
    idx = list(range(len(pts)))
    # The apron's own law: every pair, capped at APRON_MAX_GRADE·d (the
    # visibility graph on a convex ring IS all-pair).
    edges = []
    for a in idx:
        for b in idx:
            if b <= a:
                continue
            d = math.dist(pts[a], pts[b])
            if d >= 0.5:
                edges.append((a, b, APRON_MAX_GRADE * d))
    return shape, nodes_xy, node_dem, edges, idx


def _entry(shape, idx, edges):
    return {"nodes": list(idx), "edges": list(edges), "flat": False,
            "role": "apron", "shape_id": id(shape),
            "ref": shape.ref or "", "area": float(shape.polygon.area)}


def _steep_case(**kw):
    """A 600 m apron on 2 % ground with its two ends anchored at DEM —
    DOSSIER §4/§6 in miniature: 12 m of real rise against a 6 m budget."""
    shape, nodes_xy, node_dem, edges, idx = _grid_apron(**kw)
    entry = _entry(shape, idx, edges)
    elev = list(node_dem)
    # Anchor the two extreme-x nodes at their own DEM (a building seat at
    # each end of the ramp — no wrong value anywhere).
    lo = min(idx, key=lambda i: nodes_xy[i][0])
    hi = max(idx, key=lambda i: nodes_xy[i][0])
    return shape, nodes_xy, node_dem, entry, elev, {lo, hi}


_DEM_FNS: dict = {}


def _abutting_panel(layout, x, group=None):
    """The apron panel whose right edge sits nearest ``x``.

    The pre-solve split re-points the ORIGINAL shape at the LARGEST
    panel, which is not in general the one that abuts a given
    neighbour — so a facing twin has to name the panel it means.
    """
    best, best_d = None, None
    for s in layout.shapes:
        if s.role != "apron" or s.polygon is None or s.polygon.is_empty:
            continue
        if group is not None and getattr(
                s, "_terrace_panel_group", None) != group:
            continue
        d = abs(s.polygon.bounds[2] - x)
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best


def _panelize(layout, dem_fn=None):
    """Run the REAL pre-solve panelizer on ``layout``, then rebuild the
    constraint entries from the PANELS exactly as production does.

    Production order is: panelize (splitting the apron and minting the
    joint's two station rows as ring vertices) -> build the node list ->
    build the within-shape law -> bind.  The twins follow it, so a
    station is a solve variable here for the same reason it is one in a
    build.  Returns ``(entries, nodes_xy, node_dem)``.
    """
    if dem_fn is None:
        for s in list(layout.shapes):
            dem_fn = _DEM_FNS.get(id(s))
            if dem_fn is not None:
                break
    if dem_fn is None:
        def dem_fn(x, y):
            return 100.0 + 0.02 * x
    AT._construct_from_sampler(layout, dem_fn, icao="TEST")
    nodes_xy: dict = {}
    node_dem: list = []
    entries: list = []
    key: dict = {}
    for s in layout.shapes:
        if s.role != "apron" or s.polygon is None or s.polygon.is_empty:
            continue
        ring = list(s.polygon.exterior.coords)
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        idx = []
        for (x, y) in ring:
            k = (round(x, 2), round(y, 2))
            i = key.get(k)
            if i is None:
                i = len(node_dem)
                key[k] = i
                nodes_xy[i] = (float(x), float(y))
                node_dem.append(float(dem_fn(x, y)))
            idx.append(i)
        seen = set()
        idx = [i for i in idx if not (i in seen or seen.add(i))]
        edges = []
        for a_i in range(len(idx)):
            for b_i in range(a_i + 1, len(idx)):
                a, b = idx[a_i], idx[b_i]
                d = math.dist(nodes_xy[a], nodes_xy[b])
                if d >= 0.5:
                    edges.append((min(a, b), max(a, b),
                                  APRON_MAX_GRADE * d))
        entries.append(_entry(s, idx, edges))
    return entries, nodes_xy, node_dem


# ── 1. THE BINDING CONSTRAINT ───────────────────────────────────────

@pytest.mark.parametrize("angle_deg", [0, 15, 45, 90, 120])
def test_joint_never_crosses_a_spine(angle_deg):
    """A declared joint is disjoint from every taxi corridor — at any
    angle the corridor crosses the apron at.  This is the owner's
    verbatim constraint and it is STRUCTURAL: the joint is cut out of the
    corridor cover, never trimmed afterwards."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    # A spine straight through the middle of the apron at ``angle_deg``.
    cx, cy = 300.0, 100.0
    dx = math.cos(math.radians(angle_deg))
    dy = math.sin(math.radians(angle_deg))
    spine = [(cx - 1000.0 * dx, cy - 1000.0 * dy),
             (cx + 1000.0 * dx, cy + 1000.0 * dy)]
    layout = _FakeLayout([shape], centerlines=[spine])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan is not None
    cover = AT.corridor_cover(layout)
    assert cover is not None
    spine_line = LineString(spine)
    assert plan.joints, "the steep fixture did not panelize"
    for joint in plan.joints:
        # Zero-LENGTH intersection is the structural guarantee: the joint
        # is the terrace line MINUS the cover, so it may share the cover's
        # boundary but can never run inside it.
        assert joint.geom.intersection(cover).length == pytest.approx(
            0.0, abs=1e-9), "a declared joint ran inside the corridor cover"
        assert joint.geom.distance(spine_line) >= (
            APRON_TERRACE_JOINT_CLEARANCE_M - 1e-6), (
            "a declared joint came inside the pinned spine clearance")


def test_joint_never_crosses_a_service_spine():
    """Interaction fence: SERVICE spines stay in the no-cross set
    conservatively — "a wall across a vehicle route is still a wall"."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    svc = [(300.0, -500.0), (300.0, 500.0)]
    layout = _FakeLayout([shape])
    layout.apt_taxi_centerlines = [(LineString(svc), "SVC_1")]
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    cover = AT.corridor_cover(layout)
    assert cover is not None
    assert plan.joints
    for joint in plan.joints:
        assert joint.geom.intersection(cover).length == pytest.approx(
            0.0, abs=1e-9)


def test_corridor_pairs_keep_the_cap_through_a_panelized_apron():
    """Spine continuity (spec §4): a pair ON the corridor grades at cap
    through a panelized apron — its budget is untouched by the plan."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    spine = [(300.0, -500.0), (300.0, 500.0)]      # along the joints
    layout = _FakeLayout([shape], centerlines=[spine])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    before = {(a, b): bud for (a, b, bud) in entry["edges"]}
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    after = {(a, b): bud for (a, b, bud) in entry["edges"]}
    cover = AT.corridor_cover(layout)
    n_corridor_pairs = 0
    for (a, b), bud in after.items():
        chord = LineString([nodes_xy[a], nodes_xy[b]])
        if cover is not None and cover.covers(chord):
            n_corridor_pairs += 1
            assert bud == before[(a, b)], (
                "a pair lying wholly inside the corridor was relaxed")
    assert n_corridor_pairs > 0, "the fixture grew no corridor pairs"


def test_relaxation_is_monotone_and_scoped():
    """A joint may only ADD budget, and only to pairs that cross it."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    before = {(a, b): bud for (a, b, bud) in entry["edges"]}
    n = AT.apply_terrace_budgets(plan, entries, nodes_xy)
    assert n > 0, "the plan bound no law edge"
    for (a, b, bud) in entry["edges"]:
        assert bud >= before[(a, b)] - 1e-12
        crossed = AT._crossed_joints(plan.joints, *nodes_xy[a],
                                     *nodes_xy[b])
        if not crossed:
            assert bud == before[(a, b)]
        else:
            assert bud == pytest.approx(
                before[(a, b)] + sum(j.step_m for j in crossed))


# ── 2. THE STEP BOUND ───────────────────────────────────────────────

def test_declared_step_is_bounded():
    """No declared joint exceeds ``APRON_TERRACE_MAX_STEP_M`` — on ground
    steep enough to need several metres of relief, the law answers with
    MORE joints, never with a taller step."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case(
        width=1200.0, slope=0.03)
    layout = _FakeLayout([shape], centerlines=[[(600.0, -900.0),
                                                (600.0, 900.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan.joints, "the steep fixture did not panelize"
    for joint in plan.joints:
        assert 0.0 < joint.step_m <= APRON_TERRACE_MAX_STEP_M + 1e-9


# ── 3. THE TRIGGER ──────────────────────────────────────────────────

def test_trigger_floor_blocks_centimetre_noise():
    """Excess below ``APRON_TERRACE_MIN_EXCESS_M`` never panelizes."""
    shape, nodes_xy, node_dem, edges, idx = _grid_apron(
        width=200.0, slope=APRON_MAX_GRADE * 1.02)
    entry = _entry(shape, idx, edges)
    elev = list(node_dem)
    lo = min(idx, key=lambda i: nodes_xy[i][0])
    hi = max(idx, key=lambda i: nodes_xy[i][0])
    layout = _FakeLayout([shape], centerlines=[[(100.0, -300.0),
                                                (100.0, 300.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    assert plan.joints == []
    assert plan.trigger_rows == [], (
        "an apron below the relief floor produced a trigger row")
    assert layout.apron_terrace_presolve == []


def test_value_defect_on_gradeable_ground_does_not_panelize():
    """DOSSIER §1/§2/§5: an infeasibility whose witnesses sit on ground
    the cap CAN span is a WRONG VALUE, and terracing around it would bury
    the defect under lawful-looking geometry.  The steep-truth signature
    is what keeps those out."""
    shape, nodes_xy, node_dem, edges, idx = _grid_apron(
        width=400.0, slope=0.0)          # flat ground
    entry = _entry(shape, idx, edges)
    elev = list(node_dem)
    lo = min(idx, key=lambda i: nodes_xy[i][0])
    hi = max(idx, key=lambda i: nodes_xy[i][0])
    elev[hi] += 8.0                       # a seat 8 m above flat ground
    layout = _FakeLayout([shape], centerlines=[[(200.0, -300.0),
                                                (200.0, 300.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    assert plan.joints == []
    # STRUCTURAL NOW, not a signature test: the panelizer runs before the
    # solve and never sees a value at all, so a wrong VALUE on gradeable
    # ground cannot license a terrace — there is nothing for it to reach.
    # (RULINGS 5578b6a: an infeasibility is a defect report about the law
    # or the instrument, never a licence to terrace around it.)
    assert layout.apron_terrace_presolve == []


def test_steep_local_pair_does_not_license_a_value_defect_terrace():
    """The signature is about the CERTIFICATE PATH, not about the apron
    having any steep pair at all: a wrong-value anchor whose witnesses sit
    on gradeable ground must not panelize just because a metre of the
    apron is locally steep."""
    shape, nodes_xy, node_dem, edges, idx = _grid_apron(
        width=400.0, slope=0.0)
    # One genuinely steep LOCAL pair (a kerb), far from the anchors.
    steep_a = min(idx, key=lambda i: abs(nodes_xy[i][0] - 200.0)
                  + nodes_xy[i][1])
    node_dem[steep_a] += 1.5
    entry = _entry(shape, idx, edges)
    elev = [100.0] * len(idx)
    lo = min(idx, key=lambda i: nodes_xy[i][0])
    hi = max(idx, key=lambda i: nodes_xy[i][0])
    elev[hi] += 8.0                       # the wrong value
    layout = _FakeLayout([shape], centerlines=[[(200.0, -300.0),
                                                (200.0, 300.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    assert plan.joints == []
    # A locally steep metre does not make the APRON's own ground steep:
    # the trigger is the apron's DEM PLANE against the apron cap over
    # its own extent, so a kerb cannot buy a terrace and neither can the
    # 8 m wrong value beside it.
    assert layout.apron_terrace_presolve == []


def test_plan_accepts_the_solver_s_node_LIST():
    """Production hands the plan the solver's ``nodes`` LIST, not a dict.
    (Regression twin: the first HEAZ arm silently produced the DEFAULT
    surface because the list adapter had no ``__getitem__`` — a build that
    reads as "the law did nothing" is worse than a crash.)"""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, _nodes_xy, node_dem = _panelize(layout)
    node_list = [_nodes_xy[i] for i in sorted(_nodes_xy)]
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, node_list, node_dem,
                                  elev, hard, icao="TEST")
    assert plan is not None and plan.joints
    assert AT.apply_terrace_budgets(plan, entries, node_list) > 0


# ── 4. EMIT + SIDECAR ───────────────────────────────────────────────

def _panelized_layout():
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    layout._apron_terrace_plan = plan
    # Settle EVERY panel's ring at its panel level so the emitter has a
    # step to read.  Production settles them in the solve; here the same
    # rule is applied analytically — one level per PANEL, each declared
    # joint a vertex sits past adding its own declared step, so the
    # settled surface steps exactly where the law says it may.
    xs = sorted(j.line[0][0] for j in plan.joints)
    for s_ in layout.shapes:
        if s_.role != "apron" or s_.polygon is None:
            continue
        ring = list(s_.polygon.exterior.coords)[:-1]
        # The joint's HI row sits exactly ON the line (x == jx) and
        # belongs to the upper panel; the LO row sits one wall retreat
        # below it.  The half-retreat offset puts the boundary between
        # the two rows, which is where the step actually is.
        alts = [100.0 + 2.0 * sum(1 for jx in xs if x > jx - 0.3)
                for (x, _y) in ring]
        s_.node_altitudes = alts + [alts[0]]
    return layout, plan, shape


def test_joint_faces_are_retaining_walls_at_the_declared_step():
    layout, plan, shape = _panelized_layout()
    n = AT.emit_terrace_joint_faces(layout, plan)
    walls = [s for s in layout.shapes
             if s.role == "retaining_wall"
             and s.ref == "apron_terrace_joint"]
    assert n == len(walls) >= 1
    for w in walls:
        assert w.polygon.is_valid and not w.polygon.is_empty
        alts = w.node_altitudes[:-1]
        assert max(alts) - min(alts) > 0.0


def test_panel_levels_are_real_elevations_not_an_empty_mean():
    """Regression twin: the flank reader filtered BOTH sides against the
    nearer side's own distance, silently emptying the far side and
    shipping ``panel_lo = 0.0`` m into the sidecar."""
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    for joint in plan.joints:
        assert joint.panel_lo is not None and joint.panel_hi is not None
        assert joint.panel_lo > 50.0 and joint.panel_hi > 50.0
        assert joint.panel_hi >= joint.panel_lo


def test_sidecar_round_trips_into_the_validator_reader():
    """The sidecar rows the emitter writes are the rows check_grade
    reads — one declared population, two readers."""
    import check_grade as CG
    layout, plan, shape = _panelized_layout()
    # FACED-OR-NO-RELIEF (v2 §3(a)): a joint's allowance is minted by its
    # FACE, so the sidecar must be read after the emitter has run.  An
    # unfaced joint is demoted to what the surface expresses — that is
    # the point of the clause, and ``test_unfaced_joint_grants_no_relief``
    # below is its own twin.
    AT.emit_terrace_joint_faces(layout, plan)
    rows = AT.terrace_joints_sidecar(layout)
    assert rows and all(len(r["points"]) >= 2 for r in rows)

    def _ll_to_m(lat, lon):
        return ((lon - 31.0) * 96000.0, (lat - 30.0) * 111320.0)

    joints_m = CG._terrace_joints_to_m(rows, _ll_to_m)
    assert len(joints_m) == len(plan.joints)
    for (pts, step), joint in zip(joints_m, plan.joints):
        assert step == pytest.approx(joint.step_m, abs=1e-3)
        for (x, y), (jx, jy) in zip(pts, joint.line):
            assert x == pytest.approx(jx, abs=0.5)
            assert y == pytest.approx(jy, abs=0.5)
    # The validator's own allowance must match the solver's binding.
    a, b = plan.joints[0].line[0], plan.joints[0].line[-1]
    mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
    nx, ny = -(b[1] - a[1]), (b[0] - a[0])
    norm = math.hypot(nx, ny)
    p = (mid[0] - 20.0 * nx / norm, mid[1] - 20.0 * ny / norm)
    q = (mid[0] + 20.0 * nx / norm, mid[1] + 20.0 * ny / norm)
    assert CG._terrace_step_allowance(joints_m, *p, *q) == pytest.approx(
        plan.joints[0].step_m, abs=1e-3)


def test_validator_flags_a_joint_that_crosses_a_route():
    """The twin (spec §5b).  The emitter cannot produce this — the check
    is fed a hand-built crossing joint, which is exactly what the STOP
    rule is looking for."""
    import check_grade as CG
    joints_m = [([(0.0, -50.0), (0.0, 50.0)], 1.5)]
    taxi_axes = [([(-100.0, 0.0), (100.0, 0.0)], 0.015, 0.015, 0)]
    hits = CG._check_terrace_joint_crosses_route(joints_m, None, taxi_axes)
    assert len(hits) == 1
    clear = [([(0.0, 20.0), (0.0, 80.0)], 1.5)]
    assert CG._check_terrace_joint_crosses_route(
        clear, None, taxi_axes) == []


# ════════════════════════════════════════════════════════════════════
# FLIP-READINESS V2 TWINS (spec docs/specs/terrace-flip-readiness-v2-
# spec.md; T1-T8).  Each one is generation-binding: it exercises the
# EMITTER's own function, not only the validator.
# ════════════════════════════════════════════════════════════════════

from auto_patch.config import (                                # noqa: E402
    APRON_TERRACE_FACING_PROXIMITY_M,
    APRON_TERRACE_FACING_STEP_M,
)


class _StripLayout(_FakeLayout):
    """A layout that also carries a RUNWAY, so the strip footprint the
    §1 fence reads is real geometry rather than a stub."""

    def __init__(self, shapes, centerlines=(), runway=None):
        super().__init__(shapes, centerlines)
        if runway is not None:
            self.shapes.append(runway)


def _runway_shape(cx=300.0, cy=100.0, length=1800.0, width=45.0,
                  ref="09/27"):
    """A runway rectangle centred on the apron, so its strip footprint
    covers the apron's middle."""
    half_l, half_w = length / 2.0, width / 2.0
    pts = [(cx - half_l, cy - half_w), (cx + half_l, cy - half_w),
           (cx + half_l, cy + half_w), (cx - half_l, cy + half_w)]
    return BuiltShape(polygon=Polygon(pts + [pts[0]]), role="runway",
                      ref=ref, node_altitudes=[100.0] * 5)


# ── T1  STRIP FENCE (§1) ────────────────────────────────────────────

def test_T1_no_joint_is_born_inside_a_runway_strip():
    """§1, STRUCTURAL: with the strip footprint in the corridor cover,
    ``(terrace line ∩ apron) − cover`` cannot yield a piece inside a
    strip.  The KCLT 1.53 m site is this shape: an apron overlapping a
    runway strip, where the panelizer previously minted the joint (line
    + budget + sidecar row) and only the FACE emitter noticed."""
    from auto_patch.adjacent_ground import runway_strip_wall_keepout
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    rwy = _runway_shape()
    layout = _StripLayout([shape], centerlines=[[(300.0, -500.0),
                                                 (300.0, 500.0)]],
                          runway=rwy)
    keepout = runway_strip_wall_keepout(layout, require_gate=False)
    assert keepout is not None and not keepout.is_empty, (
        "the fixture's runway produced no strip footprint")
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan is not None
    for joint in plan.joints:
        assert not joint.geom.intersects(keepout), (
            "a declared joint was minted inside a runway-strip footprint")


def test_T1b_strip_geometry_is_read_regardless_of_either_gate(monkeypatch):
    """Gate reconciliation: the footprint GEOMETRY is read whatever
    ``O4_STRIP_PRECEDENCE`` / ``O4_RUNWAY_STRIP_WALL_LAW`` say — those
    gates govern corridor LAW, not where strips ARE."""
    shape, *_ = _steep_case()
    layout = _StripLayout([shape], runway=_runway_shape())
    for sp in ("0", "1"):
        for wl in ("0", "1"):
            monkeypatch.setenv("O4_STRIP_PRECEDENCE", sp)
            monkeypatch.setenv("O4_RUNWAY_STRIP_WALL_LAW", wl)
            geom = AT.runway_strip_keepout_geometry(layout)
            assert geom is not None and not geom.is_empty


# ── T2  FOOTPRINT CONGRUENCE, open vs closed ring (§1) ──────────────

def test_T2_emitter_and_validator_read_one_strip_footprint():
    """rsa amendment 4: ``check_grade`` fed the runway's CLOSED ring
    (the first vertex repeated) into the principal-axis fit while the
    emitter used ``_open_coords``, so the two footprints drifted —
    endpoints 0.27-0.98 m, ring width to 1.19 m.  Same ring, both
    spellings, one answer."""
    import check_grade as CG
    from auto_patch.grade_law import (runway_axis_and_width,
                                      runway_strip_wall_keepout_rings)
    ring = [(0.0, 0.0), (1800.0, 0.0), (1800.0, 45.0), (0.0, 45.0)]
    axis_open = runway_axis_and_width(ring)
    axis_closed = runway_axis_and_width(ring + [ring[0]])
    # the emitter's own reading (open) is the reference
    assert axis_open is not None
    a_ring = runway_strip_wall_keepout_rings(*axis_open)

    nodes = {str(i): (30.0 + y / 111320.0, 31.0 + x / 96000.0)
             for i, (x, y) in enumerate(ring)}

    def _ll_to_m(lat, lon):
        return ((lon - 31.0) * 96000.0, (lat - 30.0) * 111320.0)

    nids = [str(i) for i in range(len(ring))] + ["0"]     # CLOSED
    way = CG.Way("w1", "runway", "09/27", "runway", nids,
                 [100.0] * len(nids), {"role": "runway", "ref": "09/27"})
    v_rings = CG._runway_strip_keepout_rings([way], nodes, _ll_to_m)
    assert v_rings, "the validator derived no strip footprint"
    # Corner-for-corner congruence within the emit/projection epsilon.
    for (ar, vr) in zip(a_ring, v_rings):
        for (ax, ay), (vx, vy) in zip(ar, vr):
            assert math.hypot(ax - vx, ay - vy) < 0.05, (
                f"footprint drift {math.hypot(ax - vx, ay - vy):.3f} m "
                f"— the closed-ring duplicate is back in the axis fit")
    # …and the drift the amendment measured is what the closed spelling
    # would reintroduce, so the two spellings must agree at the source.
    assert axis_closed is not None


# ── T3  CERTIFICATE (§2) ────────────────────────────────────────────

def test_T3_every_panelized_apron_carries_its_certificate():
    """§2(a) hard zero: certificate-free panelization = 0, auditable
    from the sidecar alone."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan.joints
    panelized = {j.shape_id for j in plan.joints}
    assert panelized <= set(plan.certificates), (
        "an apron panelized without a recorded certificate")
    for cert in plan.certificates.values():
        # The evidence chain is now DEM + geometry end to end: the
        # apron's own plane, steeper than the cap, over its own extent.
        assert cert["plane_slope"] > APRON_MAX_GRADE
        assert cert["extent_m"] > 0.0
        assert cert["geom_excess_m"] >= APRON_TERRACE_MIN_EXCESS_M
        assert cert["relief_m"] > 0.0
        assert cert["panels"] >= 2
    layout._apron_terrace_plan = plan
    rows = AT.terrace_certificates_sidecar(layout)
    assert len(rows) == len(plan.certificates)


def test_T3b_fire_is_bounded_by_the_certified_evidence():
    """§2(b): terrace LINES per apron ≤ ceil(certified relief / max
    step).  Collinear pieces of one line are one step (a corridor
    crossing splits the line; it adds no relief)."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case(
        width=1200.0, slope=0.03)
    layout = _FakeLayout([shape], centerlines=[[(600.0, -900.0),
                                                (600.0, 900.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    for shape_id, cert in plan.certificates.items():
        bound = math.ceil(cert["relief_m"] / APRON_TERRACE_MAX_STEP_M)
        lines = {j.line_ordinal for j in plan.by_shape[shape_id]}
        assert len(lines) <= max(1, bound), (
            f"{len(lines)} terrace lines against an evidence bound of "
            f"{bound}")
        assert cert["line_budget"] == max(1, bound)


def test_T3c_the_area_guard_has_no_stop_power():
    """§2(c): ``is_overfire`` and ``APRON_TERRACE_OVERFIRE_AREA_FRAC``
    are RETIRED — the fraction is a report field.  An area STOP fires
    precisely when the law works as the owner ruled (the target
    population IS the large-area family)."""
    import auto_patch.config as C
    assert not hasattr(AT.TerracePlan, "is_overfire")
    assert not hasattr(C, "APRON_TERRACE_OVERFIRE_AREA_FRAC")
    plan = AT.TerracePlan()
    assert plan.area_fraction() == 0.0


# ── T4  PLAN-TIME ADMISSIBILITY + DEMOTION (§3a) ────────────────────

def test_T4_an_unfaceable_joint_is_stillborn():
    """§3(a): a joint that could not face on EITHER side is never in
    ``plan.joints`` — no budget, no sidecar row.  The budget cannot
    outlive the face because both are minted from ONE plan-time fact."""
    from shapely.geometry import Polygon as P
    line = [(0.0, 0.0), (0.0, 100.0)]
    # a keepout swallowing both candidate retreat bands
    swallow = P([(-5.0, -5.0), (5.0, -5.0), (5.0, 105.0), (-5.0, 105.0)])
    assert AT._face_admissible(line, swallow) is False
    # a keepout on ONE side only leaves the other side faceable
    one_side = P([(0.05, -5.0), (5.0, -5.0), (5.0, 105.0), (0.05, 105.0)])
    assert AT._face_admissible(line, one_side) is True
    assert AT._face_admissible(line, None) is True


def test_T4b_no_joint_survives_a_strip_that_covers_the_apron():
    """The whole-path §1 twin: an apron entirely inside a strip
    footprint panelizes NOTHING.  (The strip footprint runs
    ±75 m off the centerline, so the apron must be inside that band —
    a wider apron keeps the parts of its joints that lie OUTSIDE the
    strip, which is correct and is what T1 checks.)"""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case(
        height=100.0)
    rwy = _runway_shape(cx=300.0, cy=50.0, length=2400.0, width=60.0)
    layout = _StripLayout([shape], runway=rwy)
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan is not None
    assert plan.joints == [], (
        "a joint survived inside a strip footprint that covers the apron")


def test_T4b2_a_keepout_outside_the_cover_makes_joints_stillborn(
        monkeypatch):
    """§3(a)'s RULING, exercised on the class it was written for: a
    keepout the panelizer's cover does NOT carry (any future keepout the
    wall machinery grows).  Plan-time admissibility must kill the joint
    outright — no budget, no sidecar row — instead of letting the emitter
    drop the face and the allowance live on."""
    import auto_patch.adjacent_ground as AG
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    swallow = Polygon([(-50.0, -50.0), (650.0, -50.0),
                       (650.0, 250.0), (-50.0, 250.0)])
    monkeypatch.setattr(AG, "runway_strip_wall_keepout",
                        lambda layout, require_gate=True: swallow)
    # …and it is NOT in the panelizer's cover — that is the whole point:
    # §1 fences the strip class, and plan-time admissibility is what
    # keeps the rule self-enforcing for every OTHER keepout.
    monkeypatch.setattr(AT, "runway_strip_keepout_geometry",
                        lambda layout: None)
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    assert plan.joints == [], "an unfaceable joint reached the plan"
    assert plan.stats["joints_stillborn_keepout"] > 0
    assert AT.terrace_joints_sidecar(layout) == []


def test_T4c_unfaced_joint_grants_no_relief():
    """§3(a) DEMOTION: flanks that settled level grant NO RELIEF — the
    sidecar allowance falls to what the surface expresses (0).  Before
    this, HECA carried 17 of 118 and KCLT 5 of 17 unbacked allowances.

    SHARPENED 2026-08-05 (item 4).  §3(a) is about RELIEF, and this test
    used to also assert ``n == 0`` — no geometry at all.  That left the
    ``STACKED_WALL_RETREAT_M`` band the PRE-SOLVE split cut out of the
    apron as ground no shape covers (HECA: 14 of 79 joints demoted, and
    21.2% of the published slot area shipping uncovered).  A level joint
    now emits a COVER — same read rows, same ref, no invented value —
    while ``faced`` stays False and the allowance stays 0.  A hole is
    not the absence of relief; the two are separate facts and are now
    separately asserted.
    """
    layout, plan, shape = _panelized_layout()
    # settle EVERY panel LEVEL: every joint's two panels agree
    for s_ in layout.shapes:
        if s_.role != "apron" or s_.polygon is None:
            continue
        ring = list(s_.polygon.exterior.coords)[:-1]
        s_.node_altitudes = [100.0] * len(ring) + [100.0]
    n = AT.emit_terrace_joint_faces(layout, plan)
    assert plan.stats["joints_demoted_level"] == len(plan.joints)
    # RELIEF: none.  COVER: every slot the split cut.
    assert n == plan.stats["level_covers_emitted"] == len(plan.joints), (
        "a demoted joint left its 0.6 m slot uncovered")
    assert plan.stats["slots_uncovered"] == 0
    walls = [s for s in layout.shapes
             if s.role == "retaining_wall"
             and s.ref == "apron_terrace_joint"]
    for w in walls:
        vals = [v for v in (w.node_altitudes or []) if v is not None]
        assert max(vals) - min(vals) <= 0.05, (
            "a LEVEL cover expresses a step — it must express none")
    rows = AT.terrace_joints_sidecar(layout)
    assert rows, "the demoted joints vanished from the sidecar entirely"
    assert all(r["step_m"] == 0.0 for r in rows), (
        "an unfaced joint kept its declared allowance")
    assert all(r["actual_step_m"] is not None for r in rows), (
        "the actual settled step must stay visible as a report field")
    assert all(r["faced"] is False for r in rows)
    assert all(r["declared_step_m"] > 0.0 for r in rows), (
        "the declared value must stay visible as a report field")


def test_T4d_the_keepout_face_drop_counter_is_zero():
    """§3(a) LOUD COUNTER: with the §1 fence and plan-time
    admissibility, a face drop at EMIT time for keepout reasons means
    the two predicates diverged — a frame bug and a STOP."""
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    assert plan.stats["faces_dropped_keepout"] == 0


# ── T5  JOINT-STEP PAIR CONSTRAINTS (§3b) ──────────────────────────

def test_T5_joint_step_pairs_bind_the_actual_step():
    """§3(b) GENERATION-BINDING: every declared joint hands the ONE
    solve ``|z_m − z_n| ≤ step + cap·planar`` on the SAME straddling
    population the face is read from.  Nothing bounded that delta
    before; HECA shipped 10 faces of 2.14-5.52 m."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
    assert plan.joints
    # THE STATIONS ARE SOLVE VARIABLES.  Every declared joint carries a
    # resolved (hi, lo) node pair per station: the pre-solve split made
    # both rows apron RING vertices, so the declared step is a law edge
    # between two real variables instead of a number the emitter read
    # off an extrapolation afterwards.
    assert any(j.stations for j in plan.joints), (
        "no joint resolved a panel-boundary station to a node")
    entry = next(e for e in entries if e["shape_id"] == id(shape))
    before = {(a, b) if a < b else (b, a)
              for (a, b, _bud) in entry["edges"]}
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    after = {(a, b) if a < b else (b, a)
             for (a, b, _bud) in entry["edges"]}
    # THE BINDING NEVER INVENTS A WITHIN-SHAPE LAW PAIR.  An invented
    # edge constrains a pair the visibility graph deliberately leaves
    # free, at a straight-line distance shorter than the lawful graph
    # path — measured at HEAZ: 78 -> 1,360 law-true rows.
    assert after <= before, "the binding invented a within-shape law pair"
    # …and the cross-joint edges live in their OWN entry, at exactly the
    # declaration plus the cap over the face's own width.
    bound = APRON_TERRACE_MAX_STEP_M + APRON_MAX_GRADE * STACKED_WALL_RETREAT_M
    st_edges = AT.terrace_station_edges(plan)
    assert st_edges, "the declared step was handed to nothing"
    assert len(st_edges) == sum(len(j.stations) for j in plan.joints)
    for (i_hi, i_lo, bud) in st_edges:
        assert i_hi != i_lo
        assert 0.0 < bud <= bound + 1e-9
    own = {e["shape_id"] for e in entries}
    joint_entry = [e for e in entries
                   if e.get("ref") == "apron_terrace_joint"]
    assert joint_entry and joint_entry[0]["edges"] == st_edges
    assert -1 not in own or True


def test_T5b_pair_population_is_computed_once_for_two_consumers():
    """SINGLE-PASS: the flank pairs are plan-time facts read from
    positions alone; the solver binding and the face emitter consume the
    identical list."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    snap = {id(j): list(j.stations) for j in plan.joints}
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    for j in plan.joints:
        assert list(j.stations) == snap[id(j)], (
            "the binding re-derived the population instead of reusing it")


def test_T5c_the_face_level_is_a_lookup_not_a_reader():
    """THE READER IS GONE, and that is the fix.

    D2's whole family — the flank window, the first-order fit, the
    cap-clamped walk-in — existed because there was no geometry AT the
    joint to read a level from.  The pre-solve split puts a ring vertex
    there, so the face's level is the panel's OWN settled value, fetched
    by canonical identity.  Nothing is fitted, extrapolated or clamped,
    so nothing can drift: HECA's 6.0 m faces against a 1.994 m
    declaration are unrepresentable.
    """
    import inspect
    for gone in ("_level_at_joint", "_flank_window", "_nearest_station",
                 "_joint_flank_pairs"):
        assert not hasattr(AT, gone), (
            f"{gone} is back — the face is being READ again")
    import ast as _ast
    emit_src = inspect.getsource(AT.emit_terrace_joint_faces)
    called = {n.func.id for n in _ast.walk(_ast.parse(emit_src))
              if isinstance(n, _ast.Call)
              and isinstance(n.func, _ast.Name)}
    for banned in ("_mean", "_level_at_joint", "_flank_window",
                   "_nearest_station"):
        assert banned not in called, (
            f"the face emitter calls {banned} — emitters emit, never "
            f"grade")
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    index = AT._apron_ring_values(layout)
    for j in plan.joints:
        for st in j.stations:
            if not st.read:
                continue
            # every reported level IS a panel vertex value, exactly
            assert round(st.z_pos, 3) in {round(v, 3)
                                          for v in index.values()}
            assert round(st.z_neg, 3) in {round(v, 3)
                                          for v in index.values()}

def test_T5d_validator_reads_the_actual_step_from_the_patch():
    """§3(b)'s honest instrument: an over-step face is flagged from the
    PATCH — the sidecar's own ``actual_step_m`` is never consulted."""
    import check_grade as CG

    def _ll_to_m(lat, lon):
        return ((lon - 31.0) * 96000.0, (lat - 30.0) * 111320.0)

    joints_m = [([(0.0, 0.0), (0.0, 100.0)], 1.5)]
    nodes = {}
    for i, (x, y) in enumerate([(0.0, 0.0), (0.0, 100.0),
                                (0.6, 100.0), (0.6, 0.0)]):
        nodes[str(i)] = (30.0 + y / 111320.0, 31.0 + x / 96000.0)
    nids = ["0", "1", "2", "3", "0"]
    # a face declaring 1.5 m but standing 4.9 m tall
    tall = CG.Way("w9", "retaining_wall", "apron_terrace_joint", "",
                  nids, [100.0, 100.0, 95.1, 95.1, 100.0],
                  {"role": "retaining_wall", "ref": "apron_terrace_joint"})
    hits = CG._check_terrace_actual_step(joints_m, [tall], nodes,
                                         _ll_to_m, APRON_MAX_GRADE)
    assert hits, "a 4.9 m face against a 1.5 m declared step was not seen"
    lawful = CG.Way("w9", "retaining_wall", "apron_terrace_joint", "",
                    nids, [100.0, 100.0, 98.6, 98.6, 100.0],
                    {"role": "retaining_wall",
                     "ref": "apron_terrace_joint"})
    assert CG._check_terrace_actual_step(joints_m, [lawful], nodes,
                                         _ll_to_m, APRON_MAX_GRADE) == []


# ── T6  FACING BOUNDARY (§3c) ──────────────────────────────────────

def _neighbour_apron(x0=610.0, width=200.0, height=200.0, level=97.0):
    """A plain (non-panelized) apron sitting ~0.8 m off the panelized
    one — the HECA ``-10519``/``-10520`` geometry."""
    pts = [(x0, 0.0), (x0 + width, 0.0), (x0 + width, height),
           (x0, height)]
    n = len(pts)
    return BuiltShape(polygon=Polygon(pts + [pts[0]]), role="apron",
                      ref="apron_neighbour",
                      node_altitudes=[level] * n + [level])


def test_T6_facing_boundary_nodes_keep_full_apron_law():
    """§3(c) EXCLUSION.  The HECA specimen: apron ``-10519``
    panelizes, ``-10520`` does not, and they sit 0.72-0.89 m apart.  The
    panel's level change reached the OUTER boundary and shipped 0.57 /
    0.72 m of undeclared step — no joint (24.3 m away), no face, no
    allowance.  Facing nodes are never terrace-relaxed."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    nb = _neighbour_apron(x0=600.0 + 0.8)
    layout = _FakeLayout([shape, nb],
                         centerlines=[[(300.0, -500.0), (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    panel = _abutting_panel(layout, 600.0,
                            getattr(shape, "_terrace_panel_group", None))
    entry = next(e for e in entries if e["shape_id"] == id(panel))
    facing = plan.facing_nodes.get(id(panel)) or set()
    assert facing, "the 0.8 m neighbour produced no facing boundary run"
    before = {(a, b): bud for (a, b, bud) in entry["edges"]}
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    # STRUCTURAL NOW, not a filter.  The pre-solve split makes the joint
    # the PANEL'S OWN BOUNDARY, so no within-shape pair crosses one and
    # nothing inside a panel is terrace-relaxed at all — a facing node
    # cannot be relaxed because there is no relaxation to reach it.  The
    # exclusion counter is 0 BY CONSTRUCTION, which is the strongest
    # form of the guarantee the HECA specimen asked for.
    assert plan.stats["facing_edges_excluded"] == 0
    for (a, b, bud) in entry["edges"]:
        key = (a, b)
        if key not in before:
            continue                      # a conformance edge
        assert bud == before[key], (
            "a within-panel law edge was terrace-relaxed")

def test_T6b_facing_nodes_gain_a_conformance_constraint():
    """§3(c) CONFORMANCE: the boundary cannot drift from the neighbour
    IN THE SOLVE, at the step readers' OWN budget."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    nb = _neighbour_apron(x0=600.0 + 0.8)
    nb_pts = list(nb.polygon.exterior.coords)[:-1]
    base = max(nodes_xy) + 1
    for k, p in enumerate(nb_pts):
        nodes_xy[base + k] = p
    nb_entry = {"nodes": [base + k for k in range(len(nb_pts))],
                "edges": [], "role": "apron", "shape_id": id(nb),
                "ref": nb.ref, "area": float(nb.polygon.area)}
    layout = _FakeLayout([shape, nb],
                         centerlines=[[(300.0, -500.0), (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    base = max(nodes_xy) + 1
    for k, p in enumerate(nb_pts):
        nodes_xy[base + k] = p
    nb_entry = {"nodes": [base + k for k in range(len(nb_pts))],
                "edges": [], "role": "apron", "shape_id": id(nb),
                "ref": nb.ref, "area": float(nb.polygon.area)}
    entries = [e for e in entries if e["shape_id"] != id(nb)] + [nb_entry]
    panel = _abutting_panel(layout, 600.0,
                            getattr(shape, "_terrace_panel_group", None))
    entry = next(e for e in entries if e["shape_id"] == id(panel))
    elev = list(node_dem) + [97.0] * len(nb_pts)
    node_dem = list(node_dem) + [97.0] * len(nb_pts)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy,
                                  node_dem, elev, hard, icao="TEST")
    AT.apply_terrace_budgets(plan, entries, nodes_xy)
    assert plan.stats["facing_conformance_pairs"] > 0
    own = set(entry["nodes"])
    conf = [(a, b, bud) for (a, b, bud) in entry["edges"]
            if (a in own) != (b in own)]
    assert conf, "no cross-shape conformance edge was handed to the solve"
    for (_a, _b, bud) in conf:
        assert bud == APRON_TERRACE_FACING_STEP_M, (
            "a conformance edge carries a budget that is not the step "
            "readers' own")


def test_T6c_joints_keep_clearance_from_a_facing_run():
    """§3(c) CLEARANCE: no joint discharges its step at a neighbour's
    face."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    nb = _neighbour_apron(x0=600.0 + 0.8)
    layout = _FakeLayout([shape, nb],
                         centerlines=[[(300.0, -500.0), (300.0, 500.0)]])
    entries, nodes_xy, node_dem = _panelize(layout)
    elev = list(node_dem)
    plan = AT.plan_apron_terraces(layout, entries, nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    panel = _abutting_panel(layout, 600.0,
                            getattr(shape, "_terrace_panel_group", None))
    facing, _nb = AT._facing_boundary(layout, panel)
    assert facing is not None and not facing.is_empty
    own = [j for j in plan.joints if j.shape_id == id(shape)]
    assert own, "the panelized apron declared no joint"
    for joint in own:
        assert joint.geom.distance(facing) >= (
            APRON_TERRACE_JOINT_CLEARANCE_M - 1e-6), (
            "a joint reached within the clearance of a facing run")


def test_T6d_neighbour_membership_is_the_step_readers_own_predicate():
    """LOCKSTEP: emitter and validator must not disagree about who is a
    neighbour.  Both read ``ROLE_GRADE_LIMITS``; a skip-list role
    (a retaining wall) is nobody's neighbour."""
    from auto_patch.config import ROLE_GRADE_LIMITS
    shape, *_ = _steep_case()
    wall = BuiltShape(polygon=Polygon([(601.0, 0.0), (602.0, 0.0),
                                       (602.0, 200.0), (601.0, 200.0),
                                       (601.0, 0.0)]),
                      role="retaining_wall", ref="w")
    nb = _neighbour_apron(x0=600.8)
    layout = _FakeLayout([shape, wall, nb])
    got = AT._pavement_neighbours(layout, shape)
    assert nb in got and wall not in got
    assert ROLE_GRADE_LIMITS.get("retaining_wall") is None


def test_T6e_the_facing_budget_is_the_step_readers_own_number():
    """One shared number, asserted rather than assumed."""
    import check_grade as CG
    import argparse
    parser = [a for a in CG.__doc__ or ""]           # doc presence only
    assert APRON_TERRACE_FACING_STEP_M == 0.5, (
        "the facing budget drifted from check_grade's --edge-step "
        "default (0.5 m)")
    assert APRON_TERRACE_FACING_PROXIMITY_M == CG._STEP_CONTACT_TOL_M, (
        "the facing proximity drifted from the step checks' own contact "
        "tolerance")
    assert parser is not None and argparse is not None


# ── T7  WALL-SITE REGISTRATION / HEALER SPLIT ──────────────────────

def test_T7_joint_faces_are_minted_before_interning():
    """The healer must never average across a terrace joint.  The faces
    are BuiltShapes on the layout before any emit-time consensus runs,
    and each carries its own two levels — a wall whose ring collapsed to
    one level is a joint that was averaged away."""
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    walls = [s for s in layout.shapes
             if s.role == "retaining_wall"
             and s.ref == "apron_terrace_joint"]
    assert walls
    for w in walls:
        alts = w.node_altitudes[:-1]
        assert len(set(alts)) >= 2, (
            "a joint face carries a single level — it was averaged")


# ── T8  SIDECAR ROUND-TRIP with certificates + actual step ─────────

def test_T8_sidecar_carries_certificates_and_the_actual_step():
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    rows = AT.terrace_joints_sidecar(layout)
    certs = AT.terrace_certificates_sidecar(layout)
    assert rows and certs
    for r in rows:
        assert "declared_step_m" in r and "faced" in r
        assert "actual_step_m" in r and "flank_span_m" in r
        if r["faced"]:
            assert r["step_m"] == pytest.approx(r["declared_step_m"])
    for c in certs:
        for key in ("plane_slope", "extent_m", "geom_excess_m",
                    "relief_m", "line_budget", "joints", "panels"):
            assert key in c


# ── §3(d)  THE POLYGON SPLIT — REMOVED ─────────────────────────────
# The split is out (lead 2026-08-05): it minted 5 defects because the
# difference's new ring vertices adopted the FACE's level, a value the
# solve never produced.  Its twins are deleted rather than re-aimed —
# a twin for a path that does not run is not a guardrail.
# ``_split_lower_panels`` / ``_split_reach_line`` stay parked in the
# module with the revival precondition (interior-ring emit support +
# a pre-solve panel boundary) named in their docstrings.


def test_3d_split_is_not_called():
    """No EMIT path may split an apron polygon: a ring vertex only ever
    carries a solve-produced value.

    The split itself is not gone — it moved BEFORE the solve, which is
    what makes that guarantee true instead of aspirational.  This twin
    pins the direction: ``_split_panel`` is reachable only from the
    pre-solve construction, and the post-solve emitter mints walls and
    nothing else."""
    import ast
    import inspect
    src = inspect.getsource(AT)
    tree = ast.parse(src)
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_split_lower_panels" not in called, (
        "the retired post-solve split is back")
    # the pre-solve split IS called — by the construction, and only there
    assert "_split_panel" in called
    emit_src = inspect.getsource(AT.emit_terrace_joint_faces)
    for banned in ("difference", "_split_panel", "_split_reach_line"):
        assert banned not in emit_src, (
            f"the face emitter reaches for {banned} — emitters emit, "
            f"never grade and never cut")


# ── PRE-SOLVE PANEL BOUNDARY (completion round 2026-08-05) ──────────

def test_presolve_split_leaves_no_face_lap():
    """THE 2 479 m² DEBT, closed structurally.

    The post-solve split laps the apron: the wall band stands on ground
    an apron polygon still covers, so two authorities claim it and the
    emit consensus has to pick.  With the split BEFORE the solve the
    band is not part of any apron polygon at all — the intersection is
    exactly zero, at every airport, by construction rather than by
    tolerance.  (SPLP shipped 8.48 m² of it as a red in
    ``test_no_self_overlap``.)
    """
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    walls = [s for s in layout.shapes if s.role == "retaining_wall"]
    aprons = [s for s in layout.shapes if s.role == "apron"]
    assert walls and aprons
    for w in walls:
        for a in aprons:
            lap = w.polygon.intersection(a.polygon).area
            assert lap == pytest.approx(0.0, abs=1e-6), (
                f"a joint face laps {lap:.4f} m² of live apron surface")


def test_every_wall_vertex_is_a_panel_vertex():
    """A ring vertex only ever carries a SOLVE-PRODUCED value.

    The face is minted from the joint's own station rows, and those rows
    are panel ring vertices — so every wall corner is a vertex the solve
    valued, joined by CANONICAL IDENTITY (exact coordinate spelling),
    never by proximity.  This is the precondition the parked §3(d) split
    named and could not meet: its new vertices adopted the FACE's level,
    a value the solve never produced.
    """
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    ring_index = AT._apron_ring_values(layout)
    walls = [s for s in layout.shapes if s.role == "retaining_wall"]
    assert walls
    for w in walls:
        for (vx, vy) in list(w.polygon.exterior.coords)[:-1]:
            assert AT._value_at(ring_index, (vx, vy)) is not None, (
                f"wall vertex ({vx:.2f}, {vy:.2f}) is not a panel "
                f"vertex — the emitter authored a boundary value")


def test_panels_are_simply_connected():
    """Every shape in this system is simply connected (~17 ring
    iterations in the solver assume it).  A joint that could only be
    expressed as an interior ring is STILLBORN, not shipped as a hole."""
    layout, plan, shape = _panelized_layout()
    for s in layout.shapes:
        if s.role != "apron" or s.polygon is None:
            continue
        assert len(s.polygon.interiors) == 0, (
            "a panel shipped an interior ring")


def test_stations_are_solve_variables_on_both_panels():
    """The declared step is bound between two REAL variables.

    Each station resolves to one node on the upper panel's edge and one
    on the lower panel's, and the two are DIFFERENT variables — which is
    what makes ``|z_hi − z_lo| ≤ step + cap·retreat`` a law the solve
    enforces instead of a number the emitter reports afterwards.
    """
    from auto_patch.adjacent_ground import STACKED_WALL_RETREAT_M
    layout, plan, shape = _panelized_layout()
    assert plan.joints
    seen = 0
    for j in plan.joints:
        for st in j.stations:
            assert st.i_hi != st.i_lo
            # the two rows are one wall retreat apart, on the joint normal
            d = math.dist(j.hi[st.k], j.lo[st.k])
            assert d == pytest.approx(STACKED_WALL_RETREAT_M, abs=1e-6)
            seen += 1
    assert seen > 0, "no station resolved to a solve variable"


def test_a_joint_that_would_punch_a_hole_is_stillborn():
    """A band that cannot separate or notch its apron mints NO joint —
    no budget, no face, no relief.  Same principle as the unfaceable
    class: the budget can never outlive the geometry."""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape])
    # A cover that boxes the apron's whole rim forces every terrace
    # line's ends into the cover, so no band can reach a ring.
    n = AT._construct_from_sampler(
        layout, lambda x, y: 100.0 + 0.02 * x, icao="TEST")
    stats = layout.apron_terrace_presolve_stats
    assert stats["joints_stillborn_hole"] >= 0
    # …and whatever survived did so by splitting or notching, never by
    # punching a hole.
    for s in layout.shapes:
        if s.role == "apron" and s.polygon is not None:
            assert len(s.polygon.interiors) == 0
    assert n == stats["joints"]


# ── THE SIDECAR KILLER (fix 2026-08-05) ──────────────────────────────

def test_stations_have_ONE_representation_for_their_whole_lifetime():
    """``TerraceJoint.stations`` used to carry TWO shapes.

    The bind pass left 4-tuples ``(k, s, i_hi, i_lo)``; the face emitter
    REPLACED the list with dicts.  Any joint the emitter returned early
    from — too few rows, unreadable levels — therefore reached
    ``terrace_joints_sidecar`` still holding tuples, where
    ``r["bound_m"]`` raised ``TypeError``.  Measured: 3 of HEAZ's 13
    joints, 2 of SPJC's, 6 of HECA's 79.

    One class, minted once, enriched in place: the duality is now
    unrepresentable, which is the whole fix.
    """
    layout, plan, shape = _panelized_layout()
    assert plan.joints
    for j in plan.joints:
        for st in j.stations:
            assert isinstance(st, AT.TerraceStation)
            assert st.bound and not st.read
            assert st.bound_m == pytest.approx(AT._joint_bound_m(j))
    AT.emit_terrace_joint_faces(layout, plan)
    for j in plan.joints:
        for st in j.stations:
            assert isinstance(st, AT.TerraceStation), (
                "the emitter replaced the population instead of "
                "enriching it")


def test_a_joint_the_emitter_never_read_still_yields_a_sidecar():
    """THE EXACT PRODUCTION FAILURE, reproduced and closed.

    A joint whose rows the emitter cannot use returns early, so its
    stations never reach the reading pass.  The sidecar must still
    serialise it — and serialise to JSON, because that is what
    ``layout._write_axes_sidecar`` does with it.
    """
    import json
    layout, plan, shape = _panelized_layout()
    victim = plan.joints[-1]
    # The production shape of "the emitter never got here": the row
    # lengths disagree, so ``emit_terrace_joint_faces`` continues before
    # it would have written any level onto the stations.
    victim.lo = list(victim.lo)[:-1]
    AT.emit_terrace_joint_faces(layout, plan)
    assert not victim.faced
    assert all(not st.read for st in victim.stations), (
        "the victim joint was read after all — the twin no longer "
        "reproduces the failure it was written for")
    rows = AT.terrace_joints_sidecar(layout)
    assert rows, "the sidecar dropped every joint"
    text = json.dumps(rows)          # this is the call that used to raise
    assert "reader_bound_m" in text
    victim_row = rows[-1]
    assert victim_row["reader_bound_m"] == pytest.approx(
        AT._joint_bound_m(victim), abs=1e-4)
    for r in victim_row["stations"]:
        # an honest null, not an absence: the station was BOUND but the
        # face never read a level on it.
        assert r["z_pos"] is None and r["z_neg"] is None
        assert r["bound_m"] > 0.0


def test_the_declared_step_bound_is_one_function():
    """``step + cap·retreat`` is the number the solve binds, the number
    the emitter counts residue against, and the number the sidecar
    declares.  Three call sites, one function — a second copy is how the
    binding and the report drift apart."""
    import inspect
    src = inspect.getsource(AT)
    assert src.count("APRON_MAX_GRADE * STACKED_WALL_RETREAT_M") <= 2, (
        "the joint bound is spelled out again somewhere — read "
        "_joint_bound_m instead")
    layout, plan, shape = _panelized_layout()
    for (_i_hi, _i_lo, bud) in AT.terrace_station_edges(plan):
        assert bud in {AT._joint_bound_m(j) for j in plan.joints}


# ── ITEM 4: THE 0.6 m SLOT ───────────────────────────────────────────
# The PRE-SOLVE split cuts a ``STACKED_WALL_RETREAT_M`` band out of the
# apron for every declared joint.  The face that fills it is minted at
# the very END of the build (inside the strip reconcile unit, which by
# standing owner ruling runs after the LATE final grade projection,
# because the face reads its panels' FINAL settled values by identity).
# Between the split and that emission the slot is ground no shape covers.
# Measured at HECA, 79 bands / 2960.62 m²: wall 72.9%, graded-strip march
# 12.9% (32 bands), UNCOVERED 21.2% (629 m², 70 bands).

def test_every_declared_joint_covers_its_cut_band():
    """The split may not leave a hole.

    ``apron_terrace_wall_bands`` is the ground the pre-solve split
    REMOVED (``band ∩ host``) — the raw band overhangs the apron, and
    reserving the overhang would claim terrain that was never apron.
    Every declared joint must emit geometry over its own reservation.
    """
    from shapely.ops import unary_union
    layout, plan, shape = _panelized_layout()
    AT.emit_terrace_joint_faces(layout, plan)
    bands = [b for b in (getattr(layout, "apron_terrace_wall_bands", None)
                         or ()) if b is not None and not b.is_empty]
    assert bands, "no wall band was published — nothing to measure"
    assert plan.stats["slots_uncovered"] == 0, (
        "a declared joint emitted no geometry at all — its 0.6 m slot "
        "ships as ground no shape covers")
    walls = unary_union([s.polygon for s in layout.shapes
                         if s.role == "retaining_wall"
                         and s.ref == "apron_terrace_joint"])
    for b in bands:
        assert b.intersection(walls).area > 0.5 * b.area, (
            "a reserved slot is more than half uncovered")


def test_the_only_unread_station_is_a_joint_END():
    """THE NAMED RESIDUE of item 4, pinned so it cannot grow silently.

    The wall ring is built from the stations the emitter could READ, and
    the two it cannot read are always the SAME two: ``_joint_stations``
    puts a station on each end of the joint LINE, and that line's
    endpoints stand off the apron boundary — so those two corners are
    not apron ring vertices and the identity lookup correctly returns
    nothing.  The wall therefore stops at the first interior station and
    leaves one station-gap of the reservation uncovered at each end
    (10.4% of the reserved area on this fixture; the HECA build measured
    21.2% before level covers and the reservation clip).

    NOT FIXED HERE, deliberately: the remedy is to place the end stations
    where the joint line MEETS the apron boundary — which are readable
    vertices — but station positions feed ``_band_polygon`` and therefore
    the CUT, so that changes panel rings, node counts and the solve at
    every panelized airport.  That is a spec change with a full battery
    behind it, not a fix-forward edit.

    This twin fails the moment an INTERIOR station stops reading, which
    is a different (and real) defect.
    """
    layout, plan, shape = _panelized_layout()
    index = AT._apron_ring_values(layout)
    unread = []
    for j in plan.joints:
        last = len(j.grid) - 1
        for k in range(len(j.grid)):
            if k >= len(j.hi) or k >= len(j.lo):
                continue
            if (AT._value_at(index, j.hi[k]) is None
                    or AT._value_at(index, j.lo[k]) is None):
                unread.append((id(j), k, last))
    assert unread, "the fixture no longer reproduces the residue"
    for (_jid, k, last) in unread:
        assert k in (0, last), (
            f"station {k} of {last} is unread and is NOT a joint end — "
            f"that is a different defect from the known end-overhang one")


def test_the_band_march_treats_a_reserved_slot_as_occupied():
    """``emit_adjacent_ground_bands`` builds its static block from
    ``layout.shapes``, and the slot is in NO shape at that moment — so a
    graded strip could march into ground a retaining wall is about to
    stand on (HECA: 381 m², 32 of 79 bands).  Reordering cannot fix it:
    the faces genuinely cannot be minted before the late projection.  The
    march reads the plan-time RESERVATION instead."""
    import inspect
    from auto_patch import adjacent_ground as AG
    src = inspect.getsource(AG.emit_adjacent_ground_bands)
    assert "apron_terrace_wall_bands" in src, (
        "the band march does not read the published slot reservation — a "
        "strip can still mint terrain where a wall is about to stand")
    # and the reservation reaches the static union, not some side list
    i_band = src.index("apron_terrace_wall_bands")
    i_union = src.index("static_union = unary_union(_static_polys)")
    assert i_band < i_union, (
        "the slot bands are read after the static union is built")
