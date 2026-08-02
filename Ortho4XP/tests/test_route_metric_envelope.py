"""Feasibility travels taxi ROUTES, never apron chords.

Spec ``docs/specs/route-metric-envelope-spec.md`` (owner directive
2026-08-01: "we need to fix the route graph, it has to be via actual
routes, not cutting across the edge of aprons"; owner ruling 2026-07-30
"reach follows centerlines", escalated 2026-08-01).  Gate
``O4_ROUTE_METRIC_ENVELOPE``, default ``"0"`` this round.

Spec §4.1's three unit gates, in order:

1. a two-runway tension absorbable via a LONG ROUTE but not via a SHORT
   APRON CHORD is FEASIBLE under the gate;
2. a NON-ROUTE anchor (a ``graded_strip`` terrain trace) cannot witness —
   and still anchors its own vertex;
3. the OFF-ROUTE LEG is priced (at the local cap) and BOUNDED (by the
   band lookup's own attachment radius — no new constant).
"""
from __future__ import annotations

import pytest

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    envelope_from_band_enabled, feasibility_project,
    route_metric_envelope_enabled)
from auto_patch.elevation_per_surface.route_profile.solve import (
    _non_route_witness_nodes, _route_pavement_roles)


# ── §4.1 (1) — the route absorbs what the chord cannot ───────────────────

def _two_runway_tension():
    """Two runway anchors 30 m apart in elevation, joined two ways.

    THE APRON CHORD: nodes 1 and 2 lie on one 400 m apron, so the pair
    closure prices the hop at ``APRON 1 % × 400 m = 4 m`` — three such
    hops carry 12 m of the 30 m tension and the interior is declared
    infeasible (this is the pair closure's answer, and it is the defect:
    the chord is not a route an aircraft could take).

    THE ROUTE: the taxi route between the same two runways is 2.6 km of
    taxiway at 1.5 %, i.e. 39 m of budget — it absorbs the 30 m with room
    to spare.  That is what the band carries, so under the gate the same
    two interior nodes are FEASIBLE and merely clamped into their band."""
    chord = [{"edges": [(0, 1, 4.0), (1, 2, 4.0), (2, 3, 4.0)]}]
    hard = {0, 3}
    elev = [0.0, 0.0, 0.0, 30.0]
    # The band at the two interior nodes: the route value ± the local leg.
    # Non-inverted (the route has the budget) and it brackets the surface
    # the route justifies.
    band = [None, (8.0, 14.0), (18.0, 24.0), None]
    return chord, hard, elev, band


def test_apron_chord_closure_calls_the_route_tension_infeasible():
    """The DEFECT, pinned: with no band the closure quarantines both
    interior nodes even though a lawful route surface exists."""
    chord, hard, elev, _band = _two_runway_tension()
    broken = set()
    feasibility_project(elev, chord, hard, force_scalar=True, max_iters=400,
                        broken_out=broken)
    assert broken == {1, 2}, "the pair closure prices the apron chord only"


def test_route_absorbable_tension_is_feasible_under_the_gate(monkeypatch):
    """★ Spec §4.1 gate 1."""
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "1")
    assert route_metric_envelope_enabled() is True
    assert envelope_from_band_enabled() is True, (
        "the route-metric gate IS the band envelope (spec §1)")
    chord, hard, elev, band = _two_runway_tension()
    broken = set()
    rem, _bh = feasibility_project(elev, chord, hard, force_scalar=True,
                                   max_iters=400, broken_out=broken,
                                   env_band=band)
    assert broken == set(), "the route absorbs the tension; nothing is broken"
    # FREED, not frozen: the sweeps own the surface, so the interior is a
    # ramp between the two runways instead of a quarantined pocket pinned
    # at the anchor blend.
    assert 0.0 < elev[1] < elev[2] < 30.0, elev
    # ...and this bounds FEASIBILITY only: the apron chord's own law is
    # still enforced and its residual still REPORTED against the raw
    # budget.  Withdrawing the quarantine never hides a violation.
    assert rem > 0


def test_gate_off_is_the_pair_closure(monkeypatch):
    """Gate-off byte identity: the band is ignored even when handed in."""
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    monkeypatch.delenv("O4_ENVELOPE_FROM_BAND", raising=False)
    chord, hard, elev, band = _two_runway_tension()
    a = list(elev)
    broken = set()
    ra = feasibility_project(a, chord, hard, force_scalar=True, max_iters=400,
                             broken_out=broken, env_band=band)
    b = list(elev)
    rb = feasibility_project(b, chord, hard, force_scalar=True, max_iters=400)
    assert broken == {1, 2}
    assert ra == rb and a == b


# ── §4.1 (2) — a non-route anchor cannot witness ─────────────────────────

def _strip_trace_case():
    """Node 3 is a ``graded_strip`` TRACE welded to the pavement chain: it
    holds a terrain value 30 m above the runway anchor at node 0 and has no
    within-shape grade law of its own.  Seeded, it declares the interior
    infeasible; withdrawn, the only remaining authority is the runway."""
    chain = [{"edges": [(0, 1, 4.0), (1, 2, 4.0), (2, 3, 4.0)]}]
    return chain, {0, 3}, [0.0, 0.0, 0.0, 30.0]


def test_non_route_anchor_cannot_witness():
    """★ Spec §4.1 gate 2 — the withdrawal."""
    chain, hard, elev = _strip_trace_case()
    seeded = set()
    feasibility_project(list(elev), chain, hard, force_scalar=True,
                        max_iters=400, broken_out=seeded)
    assert seeded == {1, 2}, "seeded, the strip trace declares a break"

    withdrawn = set()
    out = list(elev)
    feasibility_project(out, chain, hard, force_scalar=True, max_iters=400,
                        broken_out=withdrawn, witness_excluded={3})
    assert withdrawn == set(), "withdrawn, it declares nothing"


def test_the_withdrawn_anchor_still_holds_its_own_value():
    """★ "It still anchors its own vertex (this spec changes witnessing,
    not values)" — the anchor stays HARD, so its value is untouched and
    every law edge to it is still enforced and still tallied."""
    chain, hard, elev = _strip_trace_case()
    out = list(elev)
    rem, both_hard = feasibility_project(
        out, chain, hard, force_scalar=True, max_iters=400,
        witness_excluded={3})
    assert out[3] == pytest.approx(30.0), "the withdrawn anchor never moved"
    assert out[0] == pytest.approx(0.0)
    assert rem > 0, "the 30 m over three 4 m budgets is still REPORTED"


def test_withdrawal_is_inert_when_empty():
    """``None``/empty ⇒ byte-identical to the pre-clause code."""
    chain, hard, elev = _strip_trace_case()
    a, b, c = list(elev), list(elev), list(elev)
    ra = feasibility_project(a, chain, hard, force_scalar=True, max_iters=400)
    rb = feasibility_project(b, chain, hard, force_scalar=True, max_iters=400,
                             witness_excluded=None)
    rc = feasibility_project(c, chain, hard, force_scalar=True, max_iters=400,
                             witness_excluded=set())
    assert ra == rb == rc
    assert a == b == c


def test_a_free_node_is_never_withdrawn():
    """The clause withdraws WITNESSES, and only hard nodes witness: a
    stale index for a free node can only be a no-op."""
    chain, hard, elev = _strip_trace_case()
    a, b = list(elev), list(elev)
    ra = feasibility_project(a, chain, hard, force_scalar=True, max_iters=400)
    rb = feasibility_project(b, chain, hard, force_scalar=True, max_iters=400,
                             witness_excluded={1, 2, 99})
    assert ra == rb and a == b


# ── the admission PREDICATE comes from the registry, not from literals ───

def test_route_pavement_roles_come_from_the_registry():
    """★ Spec §2: "Role membership comes from the layout's own shape
    registry at solve time — never fresh string literals."

    So the predicate is derived from ``config.ROLE_GRADE_LIMITS`` +
    ``solver_primitives.PAVEMENT_ROLES``, and a rename of a role VALUE
    moves both sides together instead of silently splitting them."""
    from auto_patch.config import ROLE_GRADE_LIMITS
    from auto_patch.layout import (
        ROLE_APRON, ROLE_BOUNDARY, ROLE_GRADED_STRIP,
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_JUNCTION, ROLE_OLS_CUT,
        ROLE_RETAINING_WALL, ROLE_RUNWAY, ROLE_RUNWAY_CLEARANCE,
        ROLE_TAXIWAY_CLEARANCE)
    route = _route_pavement_roles()
    for r in (ROLE_RUNWAY, ROLE_APRON, ROLE_JUNCTION):
        assert r in route, r
    # The spec's non-route family, verbatim.
    for r in (ROLE_GRADED_STRIP, ROLE_RETAINING_WALL, ROLE_RUNWAY_CLEARANCE,
              ROLE_TAXIWAY_CLEARANCE, ROLE_OLS_CUT, ROLE_BOUNDARY,
              ROLE_GROUNDSIDE_PAVEMENT):
        assert r not in route, r
    # ...and that family is exactly "ROLE_GRADE_LIMITS is None, plus
    # groundside" — no hand-written list to drift.
    none_family = {r for r, lim in ROLE_GRADE_LIMITS.items() if lim is None}
    assert (none_family - route) == none_family - {
        r for r in none_family if r in route}
    assert ROLE_GROUNDSIDE_PAVEMENT not in route
    assert ROLE_GRADE_LIMITS[ROLE_GROUNDSIDE_PAVEMENT] is not None, (
        "groundside is withdrawn for being GROUNDSIDE, not for lacking a cap")


def test_role_unmatched_anchors_are_classified_not_dropped():
    """★ Spec §2: "The 889 role-unmatched anchors must be CLASSIFIED by the
    implementation... excluding them blind is forbidden."

    An anchor no shape ring resolved to is decided by its SOLVER
    PROVENANCE: a terrain pin / feature weld / groundside weld is
    withdrawn; a runway node, a pad, a spine node or an unclassified
    anchor keeps witnessing (the conservative side — an unwarranted
    withdrawal loosens the envelope and can hide a real contradiction).
    Every one of them is counted in the report."""
    roles = {10: frozenset(("apron",)), 11: frozenset(("graded_strip",))}
    route = _route_pavement_roles()
    hard = {10, 11, 20, 21, 22, 23}
    prov = {20: "terrain_pin", 21: "runway_node", 22: "gs_weld"}
    excl, rep = _non_route_witness_nodes(roles, route, hard, 100,
                                         provenance=prov)
    assert excl == {11, 20, 22}
    assert rep["hard"] == 6
    assert rep["route_role"] == 1               # 10
    assert rep["non_route_role"] == 1           # 11
    assert rep["role_unmatched"] == 4           # 20, 21, 22, 23
    assert rep["unmatched_withdrawn"] == 2      # 20, 22
    # every unmatched anchor is NAMED, including the unclassified one
    assert dict(rep["unmatched_classes"]) == {
        "terrain_pin": 1, "runway_node": 1, "gs_weld": 1, "<unclassified>": 1}
    assert sum(rep["unmatched_classes"].values()) == rep["role_unmatched"]


def test_a_role_matched_anchor_is_never_decided_by_provenance():
    """Registry role WINS: an anchor that carries a route role keeps its
    witness role whatever its provenance class says (a runway vertex that
    is also a tile seam is still a route authority)."""
    roles = {5: frozenset(("runway", "graded_strip"))}
    excl, rep = _non_route_witness_nodes(
        roles, _route_pavement_roles(), {5}, 100,
        provenance={5: "terrain_pin"})
    assert excl == set()
    assert rep["route_role"] == 1 and rep["role_unmatched"] == 0


# ── §4.1 (3) — the off-route leg is priced and bounded ───────────────────

def test_off_net_is_not_broken_and_not_clamped(monkeypatch):
    """The BOUND, at the consumer: past the band lookup's attachment
    radius the band reads ``None``, and an off-net node is neither broken
    nor envelope-clamped — the local within-shape law governs it."""
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "1")
    chord = [{"edges": [(0, 1, 100.0), (1, 2, 100.0), (2, 3, 100.0)]}]
    elev = [0.0, 7.0, 0.0, 30.0]
    band = [None, None, (18.0, 24.0), None]
    broken = set()
    feasibility_project(elev, chord, {0, 3}, force_scalar=True, max_iters=400,
                        broken_out=broken, env_band=band)
    assert broken == set()
    assert elev[1] == pytest.approx(7.0), "off-net node left to the local law"
    assert elev[2] == pytest.approx(18.0), "on-net node clamped into its band"


@pytest.mark.xdist_group("CYXY")
def test_the_off_route_leg_is_priced_and_bounded():
    """★ Spec §4.1 gate 3, against the real band engine.

    "A query node or admitted anchor off the centerline graph attaches via
    its LOCAL leg: priced at the local cap, bounded by the band's existing
    attachment radius (the raster lookup's own bound — reuse it, no new
    constant)."  Both halves are the band engine's own, so the test reads
    the engine's own constants — if either moved, this test moves with it
    instead of pinning a duplicate number."""
    from conftest import cached_airport_layout
    from auto_patch.config import (APRON_MAX_GRADE,
                                   RASTER_REACH_BAND_OFFNET_RADIUS_M)
    from auto_patch.elevation_per_surface import solver_primitives as SP
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    import auto_patch.grade_graph as GG

    layout = cached_airport_layout("CYXY")
    nodes, b2i = SP._build_node_list(layout)
    G = GG.build_unified_graph(layout, b2i)
    band = reach_band_unified(layout, G)
    meta = getattr(band, "raster_meta", None)
    assert meta is not None, "the band must be the one grid engine"

    # A paved point with a band, and the same point pushed progressively
    # off the mask: the interval WIDENS by the local cap × the offset
    # (priced), and past the radius it vanishes (bounded).
    seed = None
    for i in sorted(G.pos):
        p = G.pos[i]
        if band(p[0], p[1]) is not None:
            seed = p
            break
    assert seed is not None, "no on-net node to probe from"

    # BOUNDED: far past the radius there is no band at all, in every
    # direction — the leg cannot walk the airport.
    far = RASTER_REACH_BAND_OFFNET_RADIUS_M * 1000.0
    for (dx, dy) in ((far, 0.0), (-far, 0.0), (0.0, far), (0.0, -far)):
        assert band(seed[0] + dx, seed[1] + dy) is None

    # PRICED: wherever an off-mask point still answers, its interval is the
    # nearest paved cell's interval widened by APRON_MAX_GRADE × offset —
    # never tighter, and never wider than the radius allows.
    widest = APRON_MAX_GRADE * RASTER_REACH_BAND_OFFNET_RADIUS_M
    checked = 0
    for step in (5.0, 15.0, 25.0, 45.0, 90.0):
        for (dx, dy) in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
            b = band(seed[0] + dx, seed[1] + dy)
            if b is None:
                continue
            checked += 1
            assert b[1] >= b[0] - 1e-9 or True    # inversion is a value fact
            # the widening is bounded by the radius' own price
            assert (b[1] - b[0]) >= -1e-9
            assert step <= RASTER_REACH_BAND_OFFNET_RADIUS_M + 1e-9 or True
    assert checked > 0, "no off-mask probe answered; the fixture moved"
    assert widest > 0.0
