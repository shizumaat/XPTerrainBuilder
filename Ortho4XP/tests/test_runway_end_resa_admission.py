"""Arc R slice R1 — runway-end RESA CUT admitted to the terrain graph.

The owner ruling (2026-07-24): the runway-end envelope is LAW THE SOLVER
ENFORCES — "ensuring terrain within a given area relative to a runway is
within an envelope, doesn't rise too steeply, or sink too quickly" — not
geometry stamped after the fact.  This file pins the ADMISSION half:

  * the ``(role, ref)`` gate and its HARD dependency chain (the cut is
    emitted inside the B1 skirt emitter's pre-solve call, and there is
    nothing to admit without ``RUNWAY_END_RESA_ENABLED``);
  * node-list ORDER — every free cut vertex must sort above every
    pavement variable, because the two solve-side terrain levers
    (host-authoritative interval kind, reach-band skip) are index
    thresholds;
  * the constraint encoding — exactly ONE ONE-SIDED interval edge per
    free cut vertex, its ceiling read from ``grade_law``;
  * the IDENTITY-COLLISION rule (a cut vertex on a pavement / skirt /
    spine variable adopts it — no edge), which is what makes the cut/fill
    twin-vertex disagreement structurally unrepresentable;
  * FIXED-POINT PARITY — the converged value of the encoding equals the
    analytic ``min(DEM, solved_ref + slope·d)`` to 1e-6.

Hermetic: hand-built layouts, no fixtures, no DEM files, no X-Plane.
"""
import pytest
from shapely.geometry import Polygon

import auto_patch.config as cfg
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile import one_solve as OS
from auto_patch.grade_law import runway_end_envelope
from auto_patch.layout import (
    REF_RUNWAY_END_RESA, REF_RUNWAY_END_SKIRT, ROLE_APRON, ROLE_RUNWAY,
    ROLE_RUNWAY_CLEARANCE,
)


# ── harness ──────────────────────────────────────────────────────────
class _FakeShape:
    def __init__(self, role, polygon, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.node_altitudes = node_altitudes


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()


def _all_gates_off(monkeypatch):
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN", False)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", False)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA", False)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_GAP_FILL_SPINE", False)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_GRADED_STRIP", False)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT",
                        False)


def _resa_chain_on(monkeypatch):
    """The minimal gate set the RESA admission requires."""
    _all_gates_off(monkeypatch)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN", True)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", True)
    monkeypatch.setattr(cfg, "RUNWAY_END_RESA_ENABLED", True)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA", True)


_RESA_PAIR = (ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
_SKIRT_PAIR = (ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_SKIRT)


# ── the gate ─────────────────────────────────────────────────────────
def test_resa_pair_is_a_declared_terrain_family():
    assert _RESA_PAIR in SP.TERRAIN_GRAPH_REFS
    # Same ROLE as the skirt, DIFFERENT ref — the reason admission is
    # (role, ref)-keyed and not role-keyed.
    assert _SKIRT_PAIR in SP.TERRAIN_GRAPH_REFS
    assert ROLE_RUNWAY_CLEARANCE not in SP.PAVEMENT_ROLES


def test_resa_not_admitted_by_default(monkeypatch):
    _all_gates_off(monkeypatch)
    assert _RESA_PAIR not in SP.admitted_terrain_refs()


def test_resa_subgate_requires_the_master_gate(monkeypatch):
    _all_gates_off(monkeypatch)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA", True)
    monkeypatch.setattr(cfg, "RUNWAY_END_RESA_ENABLED", True)
    assert SP.admitted_terrain_refs() == frozenset()


def test_resa_subgate_admits_its_pair(monkeypatch):
    _resa_chain_on(monkeypatch)
    admitted = SP.admitted_terrain_refs()
    assert _RESA_PAIR in admitted
    assert _SKIRT_PAIR in admitted


def test_resa_gate_hard_errors_without_the_skirt_subgate(monkeypatch):
    _resa_chain_on(monkeypatch)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", False)
    with pytest.raises(RuntimeError, match="RUNWAY_END_SKIRT"):
        SP.admitted_terrain_refs()


def test_resa_gate_hard_errors_without_the_cut_law(monkeypatch):
    _resa_chain_on(monkeypatch)
    monkeypatch.setattr(cfg, "RUNWAY_END_RESA_ENABLED", False)
    with pytest.raises(RuntimeError, match="O4_RUNWAY_END_RESA"):
        SP.admitted_terrain_refs()


def test_resa_gate_off_is_inert_when_deps_are_missing(monkeypatch):
    # A partial chain must only be loud when the RESA gate is actually ON.
    _all_gates_off(monkeypatch)
    monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN", True)
    assert SP.admitted_terrain_refs() == frozenset()


# ── node-list admission + ordering ───────────────────────────────────
_RWY = Polygon([(0.0, -20.0), (100.0, -20.0), (100.0, 20.0), (0.0, 20.0)])


def _cut(x0, x1, y0=-20.0, y1=20.0):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout_with_cut():
    return _FakeLayout([
        _FakeShape(ROLE_RUNWAY, _RWY),
        _FakeShape(ROLE_APRON, Polygon([(-60.0, -10.0), (-40.0, -10.0),
                                        (-40.0, 10.0), (-60.0, 10.0)])),
        _FakeShape(ROLE_RUNWAY_CLEARANCE, _cut(110.0, 160.0),
                   ref=REF_RUNWAY_END_RESA,
                   node_altitudes=[0.0, 0.0, 0.0, 0.0, 0.0]),
    ])


def test_node_list_excludes_the_cut_with_the_gate_off(monkeypatch):
    _all_gates_off(monkeypatch)
    layout = _layout_with_cut()
    nodes, _b2i = SP._build_node_list(layout)
    assert len(nodes) == 8                      # runway 4 + apron 4
    assert (110.0, -20.0) not in nodes


def test_gate_off_leaves_the_two_thresholds_equal(monkeypatch):
    """With no cut admitted the new terrain-leaf threshold IS the zone
    threshold — the property that makes the solve-side plumbing
    byte-inert off-gate."""
    _all_gates_off(monkeypatch)
    layout = _layout_with_cut()
    SP._build_node_list(layout)
    assert (layout._terrain_host_yield_first_index
            == layout._adjacent_ground_first_zone_index)


def test_cut_vertices_sort_above_every_pavement_variable(monkeypatch):
    _resa_chain_on(monkeypatch)
    layout = _layout_with_cut()
    nodes, b2i = SP._build_node_list(layout)
    first_free = layout._terrain_host_yield_first_index
    assert first_free == 8                       # runway 4 + apron 4
    assert len(nodes) == 12                      # + the 4 cut corners
    cps = layout.canonical_points
    for x, y in _cut(110.0, 160.0).exterior.coords[:-1]:
        assert b2i[cps.get_or_add(x, y)] >= first_free
    for x, y in _RWY.exterior.coords[:-1]:
        assert b2i[cps.get_or_add(x, y)] < first_free
    # The zone threshold still marks the first ZONE node, above the cut.
    assert layout._adjacent_ground_first_zone_index == len(nodes)


def test_a_cut_vertex_on_pavement_adopts_that_variable(monkeypatch):
    """IDENTITY: the cut's weld row shares vertices with the pavement it
    abuts — a shared vertex is ONE variable, so the cut never mints a
    second node there (and can never disagree with the fill)."""
    _resa_chain_on(monkeypatch)
    layout = _FakeLayout([
        _FakeShape(ROLE_RUNWAY, _RWY),
        # The cut's inner row sits exactly on the runway's east edge.
        _FakeShape(ROLE_RUNWAY_CLEARANCE, _cut(100.0, 150.0),
                   ref=REF_RUNWAY_END_RESA,
                   node_altitudes=[0.0] * 5),
    ])
    nodes, b2i = SP._build_node_list(layout)
    assert len(nodes) == 6              # 4 runway + 2 new outer corners
    cps = layout.canonical_points
    for x, y in ((100.0, -20.0), (100.0, 20.0)):
        assert b2i[cps.get_or_add(x, y)] < \
            layout._terrain_host_yield_first_index


# ── the constraint encoding ──────────────────────────────────────────
_SLOPE = cfg.RUNWAY_END_RESA_MAX_SLOPE
_REACH = cfg.CLEARANCE_MAX_REACH_M["runway"]


def _end_spec(anchor_xy=(100.0, -20.0), ref=50.0):
    return {
        "p0": (100.0, 0.0),
        "outward": (1.0, 0.0),
        "cap": float(_REACH),
        "half": 40.0,
        "governed": 240.0,
        "entry_grade": 0.0,
        "pavement_beyond_end": 0.0,
        "read_xy": (99.0, 0.0),
        "anchor_xy": anchor_xy,
        "ref_presolve": float(ref),
    }


def test_ceiling_offset_is_the_grade_law_value():
    spec = _end_spec()
    for d in (0.0, 1.0, 12.5, 100.0, 299.0):
        got = SP.runway_end_resa_ceiling_offset(spec, 100.0 + d, 7.0)
        want = runway_end_envelope(
            d, governed_length_beyond_pavement_m=spec["governed"],
            entry_grade=spec["entry_grade"],
            pavement_beyond_end_m=spec["pavement_beyond_end"],
            resa_reach_m=spec["cap"])[1]
        assert got == pytest.approx(want, abs=1e-9)
        assert got == pytest.approx(_SLOPE * d, abs=1e-9)


def test_ceiling_offset_clamps_behind_the_exit_and_past_the_reach():
    spec = _end_spec()
    # Behind the exit the law is flush (offset 0), never negative.
    assert SP.runway_end_resa_ceiling_offset(spec, 90.0, 0.0) == 0.0
    # AT / past the reach the law is unbounded; the emitter's band cap
    # holds the ramp at its terminal value, which is what the solver
    # must enforce so cut and emit agree.
    at_cap = SP.runway_end_resa_ceiling_offset(spec, 100.0 + _REACH, 0.0)
    assert at_cap == pytest.approx(_SLOPE * _REACH, abs=1e-6)
    beyond = SP.runway_end_resa_ceiling_offset(
        spec, 100.0 + _REACH + 500.0, 0.0)
    assert beyond == pytest.approx(at_cap, abs=1e-12)


def _cut_layout_with_store(cut_poly=None):
    layout = _layout_with_cut()
    if cut_poly is not None:
        layout.shapes[-1].polygon = cut_poly
    layout.runway_end_resa_presolve = [_end_spec()]
    return layout


def test_one_one_sided_edge_per_free_cut_vertex(monkeypatch):
    _resa_chain_on(monkeypatch)
    layout = _cut_layout_with_store()
    nodes, b2i = SP._build_node_list(layout)
    scs, cut_idx, collisions = SP._build_resa_cut_constraints(layout, b2i)
    assert len(scs) == 1
    entry = scs[0]
    assert entry["role"] == ROLE_RUNWAY_CLEARANCE
    assert entry["ref"] == REF_RUNWAY_END_RESA
    assert len(cut_idx) == 4
    assert len(entry["edges"]) == 4          # one per free cut vertex
    assert collisions == (0, 0, 0)
    cps = layout.canonical_points
    anchor = b2i[cps.get_or_add(100.0, -20.0)]
    for (i, j, lo, hi) in entry["edges"]:
        assert j == anchor
        assert lo is None, "the cut never fills — the floor side is OPEN"
        d = nodes[i][0] - 100.0
        assert hi == pytest.approx(_SLOPE * d, abs=1e-9)


def test_no_within_shape_rule_for_the_cut():
    """Nothing floats: the encoding gives the cut nodes no force beyond
    their one envelope edge — no within-shape grade rule exists for the
    role, so no neighbour coupling and no fairing can be generated."""
    assert cfg.ROLE_GRADE_LIMITS[ROLE_RUNWAY_CLEARANCE] is None


def test_adopted_vertices_take_no_edge(monkeypatch):
    _resa_chain_on(monkeypatch)
    layout = _cut_layout_with_store(cut_poly=_cut(100.0, 150.0))
    layout.shapes[-1].node_altitudes = [0.0] * 5
    _nodes, b2i = SP._build_node_list(layout)
    scs, _cut_idx, collisions = SP._build_resa_cut_constraints(layout, b2i)
    assert collisions[0] == 2, "the two shared runway corners must adopt"
    assert len(scs[0]["edges"]) == 2
    first_free = layout._terrain_host_yield_first_index
    for (i, _j, _lo, _hi) in scs[0]["edges"]:
        assert i >= first_free


def test_a_second_cut_piece_on_the_same_bucket_takes_no_second_edge(
        monkeypatch):
    """Two slabs on one variable is the measured B2 empty-intersection
    ping-pong class — the first claimant's corridor governs."""
    _resa_chain_on(monkeypatch)
    layout = _cut_layout_with_store()
    layout.shapes.append(_FakeShape(
        ROLE_RUNWAY_CLEARANCE, _cut(110.0, 160.0),
        ref=REF_RUNWAY_END_RESA, node_altitudes=[0.0] * 5))
    _nodes, b2i = SP._build_node_list(layout)
    scs, _cut_idx, collisions = SP._build_resa_cut_constraints(layout, b2i)
    assert collisions[1] == 4
    assert sum(len(e["edges"]) for e in scs) == 4


def test_end_association_is_geometric_and_deterministic():
    east = _end_spec()
    west = dict(_end_spec(), p0=(0.0, 0.0), outward=(-1.0, 0.0),
                anchor_xy=(0.0, -20.0))
    specs = [east, west]
    assert SP.runway_end_resa_end_index(specs, _cut(110.0, 160.0)) == 0
    assert SP.runway_end_resa_end_index(
        specs, _cut(-160.0, -110.0)) == 1


def test_store_absent_means_no_constraints():
    layout = _FakeLayout([])
    assert SP._build_resa_cut_constraints(layout, {}) == ([], set(),
                                                          (0, 0, 0))


# ── FIXED-POINT PARITY ───────────────────────────────────────────────
def test_converged_value_is_the_analytic_clamp(monkeypatch):
    """THE parity claim: projection of the DEM seed onto the one-sided
    slab IS ``min(DEM, solved_ref + slope·d)``.

    The anchor is held HARD at a value DELIBERATELY different from the
    pre-solve ``ref`` (that drift — median 0.110 m at CYXY — is the whole
    reason the cut is a solver variable), so a fixed point at the
    pre-solve reference would fail this test.
    """
    _resa_chain_on(monkeypatch)
    # A cut whose vertices span the ramp at several distances, with a DEM
    # that is above the ramp at some and below it at others (so BOTH
    # branches of the ``min`` are exercised).
    cut = Polygon([(110.0, -20.0), (140.0, -20.0), (240.0, -5.0),
                   (240.0, 5.0), (140.0, 20.0), (110.0, 20.0)])
    layout = _cut_layout_with_store(cut_poly=cut)
    layout.shapes[-1].node_altitudes = [0.0] * 7
    nodes, b2i = SP._build_node_list(layout)
    scs, cut_idx, _coll = SP._build_resa_cut_constraints(layout, b2i)

    cps = layout.canonical_points
    anchor = b2i[cps.get_or_add(100.0, -20.0)]
    first_free = layout._terrain_host_yield_first_index
    solved_ref = 50.137                     # the anchor AFTER the solve
    presolve_ref = layout.runway_end_resa_presolve[0]["ref_presolve"]
    assert abs(solved_ref - presolve_ref) > 0.1

    # DEM: a wall that overtakes the 5 % ramp near the exit and a shelf
    # that ducks under it far out.
    def _dem(x):
        d = x - 100.0
        return solved_ref + (8.0 if d < 150.0 else 0.5)

    elev = [0.0] * len(nodes)
    for i in range(len(nodes)):
        elev[i] = _dem(nodes[i][0])
    elev[anchor] = solved_ref
    hard = {anchor}

    feasibility_project(elev, scs, hard, force_scalar=True,
                        interval_yield_from=first_free)

    # RAW LAW SWEEPS ARE STANDING LAW (docs/RULINGS.md 2026-08-05,
    # build-complete-then-debug).  The sweep used to enforce the law
    # shrunk inward by the emit-quantization margin
    # (``one_solve._margined_interval``); that margin is DELETED — the
    # 0.01 m guarantee lives at emit (``auto_patch.emit_snap``), bounded
    # by one grid step per node so it cannot compound along a path.
    # Parity is therefore EXACT against the RAW analytic ceiling, with no
    # margin term to carry through the expectation.
    checked = 0
    for i in sorted(cut_idx):
        if i < first_free:
            continue
        d = nodes[i][0] - 100.0
        ceiling = solved_ref + _SLOPE * max(0.0, min(_REACH, d))
        assert elev[i] == pytest.approx(min(_dem(nodes[i][0]), ceiling),
                                        abs=1e-6)
        checked += 1
    assert checked >= 4
    # HOST AUTHORITY: the pavement anchor never moved.
    assert elev[anchor] == pytest.approx(solved_ref, abs=1e-12)


def test_the_cut_never_pulls_its_pavement_anchor(monkeypatch):
    """The safety property the whole design rests on: coupling is one-way
    host-authoritative, so a terrain node can never move pavement — even
    when the anchor is a FREE variable and the cut's DEM seed sits far
    outside the corridor."""
    _resa_chain_on(monkeypatch)
    layout = _cut_layout_with_store()
    nodes, b2i = SP._build_node_list(layout)
    scs, cut_idx, _coll = SP._build_resa_cut_constraints(layout, b2i)
    cps = layout.canonical_points
    anchor = b2i[cps.get_or_add(100.0, -20.0)]
    first_free = layout._terrain_host_yield_first_index
    elev = [40.0] * len(nodes)
    elev[anchor] = 40.0
    for i in cut_idx:
        elev[i] = 400.0                     # a cliff, 360 m over the ramp
    before = list(elev)
    feasibility_project(elev, scs, set(), force_scalar=True,
                        interval_yield_from=first_free)
    for i in range(first_free):
        assert elev[i] == pytest.approx(before[i], abs=1e-12), (
            f"pavement node {i} moved under a cut edge")
    for i in cut_idx:
        assert elev[i] < 400.0              # the cut yielded, alone


# ── the cut carries NO fairing law ───────────────────────────────────
class _FairShape:
    def __init__(self, role, polygon, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref


def _fair_layout():
    """A straight 4-vertex run whose middle node sags — the exact shape
    ``_fair_ring_edges`` exists to lift."""
    from auto_patch.canonical_points import CanonicalPointRegistry
    ring = Polygon([(0.0, 0.0), (20.0, -1.0), (40.0, 0.0), (40.0, 30.0),
                    (0.0, 30.0)])
    layout = _FakeLayout([_FairShape(ROLE_RUNWAY_CLEARANCE, ring,
                                     ref=REF_RUNWAY_END_RESA)])
    layout.canonical_points = CanonicalPointRegistry()
    cps = layout.canonical_points
    nodes, b2i = [], {}
    for (x, y) in list(ring.exterior.coords)[:-1]:
        k = cps.get_or_add(x, y)
        b2i[k] = len(nodes)
        nodes.append((x, y))
    return layout, nodes, b2i


def test_fairing_moves_a_free_ring_node_without_the_exemption():
    """Control: the cut ring IS a fairable straight run once its
    vertices resolve to solver nodes — so the exemption below is not
    vacuous."""
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _fair_ring_edges)
    layout, nodes, b2i = _fair_layout()
    elev = [10.0, 8.0, 10.0, 10.0, 10.0]
    _fair_ring_edges(layout, elev, b2i, set(), None, 0.001)
    assert elev[1] > 8.0 + 1e-6


def test_the_cut_is_exempt_from_ring_fairing():
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _fair_ring_edges)
    layout, nodes, b2i = _fair_layout()
    elev = [10.0, 8.0, 10.0, 10.0, 10.0]
    _fair_ring_edges(layout, elev, b2i, set(), None, 0.001,
                     skip_nodes={1})
    assert elev == [10.0, 8.0, 10.0, 10.0, 10.0]


def test_a_triple_is_dropped_on_ANY_free_cut_member():
    """HOST AUTHORITY, measured at CYXY: the 2.1 m pavement drag came
    from a cut-ring triple whose CENTRE was the pavement vertex the weld
    row shares with a junction.  Dropping only centre-matches would have
    left that class alive — the skip must fire on any of the three."""
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _fair_ring_edges)
    layout, nodes, b2i = _fair_layout()
    elev = [10.0, 8.0, 10.0, 10.0, 10.0]
    # node 1 is the (pavement-shared) centre; its neighbours 0 and 2 are
    # free cut nodes.  The centre must not move.
    _fair_ring_edges(layout, elev, b2i, set(), None, 0.001,
                     skip_nodes={0, 2})
    assert elev[1] == 8.0


def test_empty_skip_set_is_byte_inert():
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _fair_ring_edges)
    out = []
    for skip in (None, set(), frozenset()):
        layout, _nodes, b2i = _fair_layout()
        elev = [10.0, 8.0, 10.0, 10.0, 10.0]
        _fair_ring_edges(layout, elev, b2i, set(), None, 0.001,
                         skip_nodes=skip)
        out.append(tuple(elev))
    assert len(set(out)) == 1
