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


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setenv("O4_APRON_TERRACE_LAW", "1")


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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    before = {(a, b): bud for (a, b, bud) in entry["edges"]}
    AT.apply_terrace_budgets(plan, [entry], nodes_xy)
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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    before = {(a, b): bud for (a, b, bud) in entry["edges"]}
    n = AT.apply_terrace_budgets(plan, [entry], nodes_xy)
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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    assert plan.joints == []
    row = plan.trigger_rows[0]
    assert row["excess"] < APRON_TERRACE_MIN_EXCESS_M
    assert row["verdict"] in ("below_floor", "feasible")


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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    assert plan.joints == []
    # Flat ground short-circuits at the SOUND prefilter (no direct law
    # edge is DEM-infeasible ⇒ no pair can be, anywhere).
    assert plan.trigger_rows[0]["verdict"] == "dem_within_cap"


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
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, {lo, hi}, icao="TEST")
    row = plan.trigger_rows[0]
    assert row["dem_infeasible_edges"] > 0        # the kerb is real
    assert plan.joints == []
    assert row["verdict"] == "value_defect_not_steep"


def test_plan_accepts_the_solver_s_node_LIST():
    """Production hands the plan the solver's ``nodes`` LIST, not a dict.
    (Regression twin: the first HEAZ arm silently produced the DEFAULT
    surface because the list adapter had no ``__getitem__`` — a build that
    reads as "the law did nothing" is worse than a crash.)"""
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    node_list = [nodes_xy[i] for i in sorted(nodes_xy)]
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    plan = AT.plan_apron_terraces(layout, [entry], node_list, node_dem,
                                  elev, hard, icao="TEST")
    assert plan is not None and plan.joints
    assert AT.apply_terrace_budgets(plan, [entry], node_list) > 0


def test_gate_off_is_inert():
    """Gate OFF ⇒ no plan at all, and the sidecar key is an empty list."""
    import os
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    os.environ["O4_APRON_TERRACE_LAW"] = "0"
    try:
        assert AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                      elev, hard) is None
        assert AT.apply_terrace_budgets(None, [entry], nodes_xy) == 0
        assert AT.terrace_joints_sidecar(layout) == []
    finally:
        os.environ["O4_APRON_TERRACE_LAW"] = "1"


# ── 4. EMIT + SIDECAR ───────────────────────────────────────────────

def _panelized_layout():
    shape, nodes_xy, node_dem, entry, elev, hard = _steep_case()
    layout = _FakeLayout([shape], centerlines=[[(300.0, -500.0),
                                                (300.0, 500.0)]])
    plan = AT.plan_apron_terraces(layout, [entry], nodes_xy, node_dem,
                                  elev, hard, icao="TEST")
    AT.apply_terrace_budgets(plan, [entry], nodes_xy)
    layout._apron_terrace_plan = plan
    # Settle the ring at panel levels so the emitter has a step to mint.
    ring = list(shape.polygon.exterior.coords)[:-1]
    # One level per PANEL: each declared joint the vertex sits past adds
    # its own declared step, so the settled ring steps exactly where the
    # law says it may.
    xs = sorted(j.line[0][0] for j in plan.joints)
    alts = [100.0 + 2.0 * sum(1 for jx in xs if x > jx) for (x, _y) in ring]
    shape.node_altitudes = alts + [alts[0]]
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
