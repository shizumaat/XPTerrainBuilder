"""FLAT-SITE FAST PATH (phase 3) — the SOLVE PARTITION.

Spec: ``docs/specs/flat-site-fast-path-spec.md`` (2026-08-10, FROZEN).

THE EQUIVALENCE TWIN IS THE SPEC.  On a synthetic flat fixture (constant
DEM, one runway, apron / junction / taxi spine / service road, one tunnel
ramp) the fast-path arm and the full-solve arm must agree at EVERY shared
node within the solver quantum (0.01 m), the born-at-Z0 shapes must read
EXACTLY Z0, and the runway profile must be byte-identical.  Everything
else here is the partition predicate: what it admits, what it refuses,
and that the gate off is byte-identical output.

No network, no DEM file, no X-Plane install: a hand-built layout, a
constant-DEM stub and the production solver.
"""
from __future__ import annotations

import importlib

import pytest
from shapely.geometry import LineString, Polygon

# NOTE the import ORDER: ``auto_patch.pipeline`` first, per the subsystem's
# ``junction_repair`` <-> ``elevation`` cycle note in src/auto_patch/CLAUDE.md.
import auto_patch.pipeline                                    # noqa: F401
from auto_patch import config as CFG
from auto_patch import flat_fast_path as FP
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile import solve_route_profile
from auto_patch.layout import SHARED_VERTEX_TOL_M, BuiltShape, PavementLayout

Z0 = 12.0
TILE_LAT, TILE_LON = 30, 31
ANCHOR = (30.5, 31.5)


class _ConstDEM:
    """The substituted surface: constant Z0 everywhere.  ``_sample_dem``
    only ever calls ``alt((x, y))``."""

    def __init__(self, value=Z0):
        self.value = float(value)

    def alt(self, xy):
        return self.value


class _Centerline:
    """The minimal shape ``grade_graph.centerline_specs`` reads."""

    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service
        self.seg_sizes = []
        self.route_line = line


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def _extent_wgs84(layout, half_m=4000.0):
    lat0, lon0 = layout.m_to_ll(-half_m, -half_m)
    lat1, lon1 = layout.m_to_ll(half_m, half_m)
    return [lon0, lat0, lon1, lat1]


def _fixture(*, with_tunnel=True, stamp=True, z0=Z0, runway_alt=None):
    """The synthetic flat site.

    Geometry, all in layout metres: one E-W runway on the origin, a
    junction hard against the runway strip, a taxi spine reaching an
    apron 500 m clear of it, a building pad on the apron's far edge, a
    service road, and (optionally) a tunnel ramp 6 m below grade.
    """
    layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    layout.canonical_points = CanonicalPointRegistry(tol_m=SHARED_VERTEX_TOL_M)
    runway_alt = z0 if runway_alt is None else runway_alt

    layout.shapes.append(BuiltShape(
        polygon=_rect(-1500.0, -22.0, 1500.0, 22.0),
        role="runway", ref="09/27",
        altitude_high=runway_alt, altitude_low=runway_alt))
    layout.shapes.append(BuiltShape(
        polygon=_rect(-60.0, 22.0, 60.0, 60.0), role="junction", ref="J1"))
    layout.shapes.append(BuiltShape(
        polygon=_rect(400.0, 400.0, 700.0, 700.0), role="apron", ref="A1"))
    layout.shapes.append(BuiltShape(
        polygon=_rect(700.0, 450.0, 760.0, 650.0),
        role="building", ref="B1"))
    layout.shapes.append(BuiltShape(
        polygon=_rect(300.0, 800.0, 400.0, 820.0),
        role="service_road", ref="S1"))
    if with_tunnel:
        layout.shapes.append(BuiltShape(
            polygon=_rect(0.0, 300.0, 60.0, 340.0),
            role="tunnel_ramp", ref="tunnel_ramp",
            node_altitudes=[z0 - 6.0] * 5))

    layout.apt_taxi_centerlines = [
        _Centerline(LineString([(0.0, 41.0), (300.0, 300.0),
                                (550.0, 550.0)])),
    ]
    if stamp:
        layout.dem_inset_provenance = {
            "insets": [], "raw": False,
            "synthetic_flat_site": {
                "icao": "ZZZZ", "kind": "synthetic_flat_site",
                "verdict": "flat_candidate", "z0_m": z0,
                "extent_wgs84": _extent_wgs84(layout), "feather_m": 60.0,
            },
        }
    else:
        layout.dem_inset_provenance = {
            "insets": [], "raw": True, "synthetic_flat_site": None}
    return layout


def _solve(layout, z0=Z0):
    solve_route_profile(layout, "ZZZZ", dem=_ConstDEM(z0),
                        tile_lat=TILE_LAT, tile_lon=TILE_LON)
    return layout


def _emitted_values(layout):
    """``{(ref, role, rounded vertex): altitude}`` — the join is the
    VERTEX COORDINATE, never a node index (index space is per-solve)."""
    out = {}
    for shape in layout.shapes:
        ring = list(shape.polygon.exterior.coords)
        alts = shape.node_altitudes
        if alts:
            values = list(alts[:len(ring)])
        elif shape.altitude is not None:
            values = [float(shape.altitude)] * len(ring)
        elif (shape.altitude_high is not None
                and shape.altitude_low is not None):
            from auto_patch.layout import corner_alts_from_high_low
            values = list(corner_alts_from_high_low(
                shape.altitude_high, shape.altitude_low))
            values = (values + [values[0]])[:len(ring)]
        else:
            continue
        for (x, y), value in zip(ring, values):
            if value is None:
                continue
            out[(shape.ref, shape.role,
                 round(x, 3), round(y, 3))] = float(value)
    return out


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """Every test states its own gate; default the module to ON."""
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", True, raising=False)


# ── THE EQUIVALENCE TWIN ─────────────────────────────────────────────

def test_fast_and_full_arms_agree_within_the_solver_quantum(monkeypatch):
    """Fast-path arm vs full-solve arm on the SAME fixture."""
    fast = _solve(_fixture())
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", False, raising=False)
    full = _solve(_fixture())

    fast_values = _emitted_values(fast)
    full_values = _emitted_values(full)
    shared = set(fast_values) & set(full_values)
    assert shared, "the two arms emitted no comparable vertex"
    # Both arms must cover the same vertices — a partition may not delete
    # or mint geometry.
    assert set(fast_values) == set(full_values)

    worst = max(abs(fast_values[k] - full_values[k]) for k in shared)
    assert worst <= FP.quantum_m(), (
        f"fast/full disagreement {worst:.4f} m > quantum "
        f"{FP.quantum_m()} m")


def test_the_fast_arm_actually_partitioned_something():
    """A twin that passes because NOTHING was fast-pathed proves nothing."""
    layout = _solve(_fixture())
    plan = getattr(layout, FP.PLAN_ATTRIBUTE, None)
    assert plan is not None
    assert plan.eligible, plan.counts
    assert plan.counts["pinned_nodes"] > 0


def test_eligible_shapes_read_exactly_z0():
    layout = _solve(_fixture())
    plan = getattr(layout, FP.PLAN_ATTRIBUTE)
    for shape in layout.shapes:
        if id(shape) not in plan.eligible:
            continue
        assert shape.node_altitudes, f"{shape.ref} lost its per-vertex values"
        for value in shape.node_altitudes:
            assert value == pytest.approx(Z0, abs=1e-9), shape.ref


def test_runway_profile_is_byte_identical_between_arms(monkeypatch):
    fast = _solve(_fixture())
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", False, raising=False)
    full = _solve(_fixture())

    def _runway(layout):
        return [(s.ref, s.altitude, s.altitude_high, s.altitude_low,
                 tuple(s.node_altitudes) if s.node_altitudes else None)
                for s in layout.shapes if s.role == "runway"]

    assert _runway(fast) == _runway(full)


def test_transition_surface_identical_within_quantum(monkeypatch):
    """The tunnel ramp is a below-grade LAW surface: neither arm may
    touch it, and the service road beside it takes the full solve."""
    fast = _solve(_fixture())
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", False, raising=False)
    full = _solve(_fixture())
    for layout in (fast, full):
        ramp = [s for s in layout.shapes if s.role == "tunnel_ramp"][0]
        assert ramp.node_altitudes == [Z0 - 6.0] * 5


# ── THE PARTITION PREDICATE ──────────────────────────────────────────

def _plan_of(layout):
    return FP.build_plan(layout)


def _by_ref(layout, plan):
    return {s.ref for s in layout.shapes if id(s) in plan.candidates}


def test_plain_apron_is_eligible():
    layout = _fixture()
    plan = _plan_of(layout)
    assert "A1" in _by_ref(layout, plan)


def test_strip_adjacent_junction_is_ineligible():
    layout = _fixture()
    plan = _plan_of(layout)
    assert "J1" not in _by_ref(layout, plan)
    assert plan.counts.get("refused_runway_envelope", 0) >= 1


def test_shape_inside_the_transition_reach_is_ineligible():
    """A tunnel ramp exists ⇒ the whole R5 transition-role family is
    refused (the reach of geometry that does not exist yet is unknown,
    and unknown is unbounded)."""
    layout = _fixture(with_tunnel=True)
    plan = _plan_of(layout)
    assert "S1" not in _by_ref(layout, plan)
    assert plan.counts.get("refused_transition_family", 0) >= 1


def test_service_road_is_eligible_when_nothing_is_below_grade():
    layout = _fixture(with_tunnel=False)
    plan = _plan_of(layout)
    assert "S1" in _by_ref(layout, plan)


def test_a_runway_off_z0_widens_the_envelope_and_refuses_the_apron():
    """The conservatism closure: where the runway does NOT sit at Z0 the
    full solve may carry that difference outward at the taxi cap, so a Z0
    plate inside that reach is a value the full solve never produced."""
    layout = _fixture(runway_alt=Z0 + 6.0)
    plan = _plan_of(layout)
    # 6 m / 1.5 % = 400 m of extra envelope — it swallows the apron.
    assert plan.counts["runway_extra_m"] == pytest.approx(
        6.0 / CFG.TAXI_MAX_GRADE, abs=0.01)
    assert "A1" not in _by_ref(layout, plan)


def test_shape_outside_the_constant_core_is_ineligible():
    """The core is the substituted extent ERODED BY THE FEATHER: inside
    the feather ring the raster ramps and is not constant."""
    layout = _fixture()
    entry = layout.dem_inset_provenance["synthetic_flat_site"]
    entry["extent_wgs84"] = _extent_wgs84(layout, half_m=500.0)
    plan = _plan_of(layout)
    assert "A1" not in _by_ref(layout, plan)
    assert plan.counts.get("refused_outside_core", 0) >= 1


def test_gate_off_is_byte_identical(monkeypatch):
    monkeypatch.setattr(CFG, "FLAT_SITE_FAST_PATH", False, raising=False)
    layout = _fixture()
    assert FP.build_plan(layout) is None
    solved = _solve(layout)
    assert getattr(solved, FP.PLAN_ATTRIBUTE, "missing") is None
    assert FP.skip_shape_ids(solved) == frozenset()
    assert FP.band_skip_idx(solved) == frozenset()


def test_no_substitution_stamp_admits_nothing():
    """A merely flat-ish REAL DEM does not converge to a constant, so the
    licence is the phase-2 substitution stamp, never the verdict."""
    layout = _fixture(stamp=False)
    assert FP.build_plan(layout) is None


# ── THE ROLE ENUMERATION (role literals are wire-adjacent) ───────────

def test_eligible_roles_are_read_off_role_grade_limits():
    roles = FP.eligible_roles()
    assert roles == frozenset(
        role for role, cap in CFG.ROLE_GRADE_LIMITS.items()
        if cap is not None
        and role not in {"runway", "runway_crossing", "tunnel_ramp",
                         "terminal"})
    # The families the spec names explicitly.
    for never in ("runway", "runway_crossing", "tunnel_ramp",
                  "retaining_wall", "boundary", "graded_strip",
                  "bridge_trench", "bridge_causeway", "object_pad",
                  "taxiway_clearance", "runway_clearance", "ols_cut"):
        assert never not in roles
    for always in ("apron", "junction", "building", "service_road",
                   "service_junction", "groundside_pavement"):
        assert always in roles


def test_an_unknown_role_is_never_eligible():
    """``_role_grade`` falls back to the taxi cap for an unknown role;
    inheriting eligibility from a fallback is the unprovable case."""
    assert "tunnel_trench" not in FP.eligible_roles()
    assert "a_role_nobody_defined" not in FP.eligible_roles()


def test_solver_eligible_roles_are_solver_members():
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    assert FP.solver_eligible_roles() <= frozenset(PAVEMENT_ROLES)
    # groundside_pavement is a pavement family member with NO solve
    # variable — it is born at Z0 by its own emitter's DEM sample.
    assert "groundside_pavement" in FP.eligible_roles()
    assert "groundside_pavement" not in FP.solver_eligible_roles()


# ── THE SEAM: senior pins own their value ────────────────────────────

def test_a_senior_pin_off_z0_demotes_the_whole_shape():
    """The object-bridge deck-pin registry is a SENIOR pin family; a
    candidate holding one that disagrees with Z0 is not provably
    constant, so the WHOLE shape falls back to the full solve."""
    from auto_patch.layout import vertex_bucket
    layout = _fixture()
    layout._object_bridge_pin_values = {
        vertex_bucket(400.0, 400.0): Z0 + 3.0}
    solved = _solve(layout)
    plan = getattr(solved, FP.PLAN_ATTRIBUTE)
    apron = [s for s in solved.shapes if s.ref == "A1"][0]
    assert id(apron) in plan.candidates
    assert id(apron) not in plan.eligible
    assert plan.counts.get("demoted_senior_pin", 0) >= 1


def test_a_senior_pin_at_z0_is_kept_not_rewritten():
    from auto_patch.layout import vertex_bucket
    layout = _fixture()
    layout._object_bridge_pin_values = {vertex_bucket(400.0, 400.0): Z0}
    solved = _solve(layout)
    plan = getattr(solved, FP.PLAN_ATTRIBUTE)
    apron = [s for s in solved.shapes if s.ref == "A1"][0]
    assert id(apron) in plan.eligible


def test_pinned_nodes_join_the_seam_pin_protection_set():
    solved = _solve(_fixture())
    plan = getattr(solved, FP.PLAN_ATTRIBUTE)
    protected = getattr(solved, "_seam_pin_idx", set())
    assert plan.node_idx
    assert plan.node_idx <= set(protected)


def test_band_skip_covers_only_exclusively_owned_nodes():
    """A node shared with an INELIGIBLE shape keeps its band — that
    shape's own law reads it."""
    solved = _solve(_fixture())
    plan = getattr(solved, FP.PLAN_ATTRIBUTE)
    assert plan.exclusive_node_idx <= plan.node_idx
    assert FP.band_skip_idx(solved) == frozenset(plan.exclusive_node_idx)


# ── WIRING TWINS (a rename on one side must fail here) ───────────────

def test_the_plan_attribute_is_spelled_once():
    assert SP._FAST_PATH_ATTRIBUTE == FP.PLAN_ATTRIBUTE


def test_node_bands_skip_idx_hands_none_and_skips_the_scan():
    from auto_patch.elevation_per_surface.route_profile.anchors import (
        node_bands)
    seen = []

    def band(x, y):
        seen.append((x, y))
        return (0.0, 1.0)

    nodes = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    out = node_bands(nodes, band, skip_idx={1})
    assert out[1] is None
    assert out[0] == (0.0, 1.0) and out[2] == (0.0, 1.0)
    assert (1.0, 0.0) not in seen


def test_reach_band_batch_accepts_the_skip_set():
    """``node_bands`` hands ``skip_idx`` straight to ``band.batch``."""
    import inspect

    from auto_patch.elevation_per_surface import building_feasibility as BF

    source = inspect.getsource(BF.reach_band_unified)
    assert "def _batch(nodes, limit, skip_idx=None)" in source


def test_born_flat_shapes_get_no_constraint_entry():
    """The grade-graph rows really are absent — the spec's §1 claim."""
    layout = _fixture()
    plan = FP.build_plan(layout)
    layout._flat_fast_path = plan
    nodes, b2i = SP._build_node_list(layout)
    elev, hard, have = SP._seed_elevations(
        layout, nodes, b2i, dem=_ConstDEM(), tile_lat=TILE_LAT,
        tile_lon=TILE_LON)
    skip = FP.skip_shape_ids(layout)
    assert skip
    with_skip = SP._build_shape_constraints(
        layout, b2i, born_flat_shape_ids=skip)
    without = SP._build_shape_constraints(layout, b2i)
    assert len(with_skip) == len(without) - len(skip)


def test_config_gate_reads_the_env_default():
    """Default ON; ``O4_FLAT_SITE_FAST_PATH=0`` is the kill switch."""
    module = importlib.reload(CFG)
    try:
        assert module.FLAT_SITE_FAST_PATH is True
        assert module.FLAT_SITE_FAST_PATH_QUANTUM_M == 0.01
        assert "FLAT_SITE_FAST_PATH" in module.__all__
    finally:
        importlib.reload(CFG)


# ── DECIMATION (spec §3: VERIFY, do not add machinery) ───────────────

def test_emit_decimate_already_collapses_a_constant_span():
    """A constant, straight span collapses to the chord cap — the tier is
    already right, so the fast path adds nothing here."""
    from auto_patch import emit_decimate as ED

    bottom = [(float(x), 0.0) for x in range(0, 401, 10)]
    top = [(float(x), 20.0) for x in range(400, -1, -10)]
    ring = bottom + top
    alts = [Z0] * len(ring)
    keep = ED._ring_keep_set(ring, alts, ED.Z_TOL_AIRSIDE_M)
    assert len(keep) < len(ring)
    kept_x = sorted(ring[i][0] for i in keep if ring[i][1] == 0.0)
    assert kept_x[0] == 0.0 and kept_x[-1] == 400.0
    for a, b in zip(kept_x, kept_x[1:]):
        assert b - a <= ED.MAX_CHORD_M + 1e-6
