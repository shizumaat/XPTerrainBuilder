"""Twins for the SEED-FIX round §3 / §4 / §5 (spec
``docs/specs/seed-fix-round-spec.md``).

All three fixes share ONE geometry — HECA's minting chain, taken verbatim
from the phase-A npz (``seed_attrib/``):

  * node 2861 — a no-building apron FEEDER CONTACT, DEM 60.200, band
    [62.119, 73.538], projected by the apron polytope to a seat of
    65.7485 and then stamped IMMOVABLE;
  * node 2862 — a free apron/junction node between them;
  * node 2863 — HARD ``seed_rwy_seam`` runway truth at 60.790, only
    ~0.19 m of route BUDGET from 2861 (0.1928 m on the real graph;
    0.1828 m on the two-hop synthetic below, which carries only the two
    budgets the stall report named).

|65.7485 − 60.790| = 4.9585 m across that budget: a ~4.77 m
contradiction between two IMMOVABLE values, which is what burns 3983
sweeps in the phase-A projection and can never certify.

  §3 — the apron-contact polytope must SEE 2863 (the law-graph budget
       oracle) so the feeder is capped to it instead of to its feeders
       alone;
  §4 — a seat that still contradicts must not become ``base_hard``, and
       must not be smuggled back by the spine-yield PRESERVED set;
  §5 — an empty interval in the phase-A harmonic must be NAMED, never
       silently split.
"""
import pytest

from auto_patch.elevation_per_surface.route_profile import anchors as AN
from auto_patch.elevation_per_surface.route_profile import solve as SV
from auto_patch.elevation_per_surface.route_profile.law_graph_budget import (
    build_anchor_envelope)


# ── the shared HECA geometry ─────────────────────────────────────────────
#: measured budgets: 2861<->2862 0.0576 m, 2862<->2863 0.1252 m
#: (the two carrier budgets the stall report named).
_SPINE_ADJ = {
    2861: [(2862, 0.0576)],
    2862: [(2861, 0.0576), (2863, 0.1252)],
    2863: [(2862, 0.1252)],
}
_HARD = {2863: 60.790}
_SEAT_2861 = 65.7485
_DEM_2861 = 60.200
_BAND_2861 = (62.1192, 73.5375)


# ── §3 ───────────────────────────────────────────────────────────────────

def test_the_anchor_cap_is_unconditional_law():
    """STANDING LAW (2026-08-05): there is no gate function and no env
    override left — the only thing that can switch the cap off is the
    absence of an envelope to cap against, which is the honest "no hard
    anchor on this graph"."""
    assert not hasattr(AN, "apron_contact_anchor_cap_enabled")
    import os
    assert not any(k.startswith("O4_APRON_CONTACT_ANCHOR_CAP")
                   for k in os.environ)


def test_the_oracle_prices_2861_against_the_runway_truth():
    """The budget oracle must reproduce the measured 0.1928 m route and
    the resulting box — if it prices differently it is a SECOND metric,
    which is the defect family, not the fix."""
    env = build_anchor_envelope(_SPINE_ADJ, _HARD)
    assert env is not None
    assert env.anchor_count == 1
    lo, hi = env.box(2861)
    assert env.ceil_route_m[2861] == pytest.approx(0.1828, abs=1e-4), (
        "0.0576 + 0.1252 = 0.1828 m of budget — the projection's own "
        "shortest path, not a straight-line or an area metric")
    assert lo == pytest.approx(60.790 - 0.1828, abs=1e-9)
    assert hi == pytest.approx(60.790 + 0.1828, abs=1e-9)


def test_the_stamped_seat_is_outside_the_box_and_the_band_is_too():
    """Both halves of the attribution in one assertion: the SEAT is
    wildly outside, and so is the entire BAND the clamp pulled the DEM
    target into — which is why capping the polytope is not enough on its
    own and §2 exists."""
    env = build_anchor_envelope(_SPINE_ADJ, _HARD)
    v = env.violation(2861, _SEAT_2861)
    assert v is not None and v["side"] == "ceiling"
    assert v["excess_m"] == pytest.approx(4.7757, abs=1e-3)
    assert v["witness"] == 2863
    lo, hi = env.box(2861)
    assert _BAND_2861[0] > hi, (
        "the band FLOOR is above the hard anchor's ceiling — the band "
        "and the runway truth cannot both be satisfied (§2's defect)")


def test_the_capped_polytope_seats_the_feeder_within_cap():
    """With the box tightened to the envelope, the apron projection puts
    the feeder inside the runway anchor's reach — the pre-registered
    '2861 re-seats within cap of 2863's runway truth'."""
    env = build_anchor_envelope(_SPINE_ADJ, _HARD)
    lo, hi = env.box(2861)
    # a second feeder 40 m away, comfortably reachable, so the polytope
    # is a real 2-variable problem and not a trivial clamp.
    targets = [min(max(_DEM_2861, lo), hi), 61.0]
    boxes = [(lo, hi), (60.0, 62.0)]
    positions = [(0.0, 0.0), (40.0, 0.0)]
    levels = AN._project_apron_contacts(targets, boxes, positions, 0.01)
    assert levels is not None
    assert abs(levels[0] - 60.790) <= 0.1828 + 1e-9, (
        "the seated feeder is within its ROUTE BUDGET of the runway truth")


def test_without_the_cap_the_polytope_can_seat_metres_away():
    """The falsifier: the SAME projection with the band-only box (today's
    behaviour) is free to seat the feeder 1.3 m past the runway truth's
    reach.  Without this the twin would pass for a no-op."""
    targets = [min(max(_DEM_2861, _BAND_2861[0]), _BAND_2861[1]), 61.0]
    boxes = [_BAND_2861, (60.0, 62.0)]
    positions = [(0.0, 0.0), (40.0, 0.0)]
    levels = AN._project_apron_contacts(targets, boxes, positions, 0.01)
    assert levels is not None
    assert abs(levels[0] - 60.790) > 0.1828, (
        "the uncapped polytope seats outside the runway anchor's reach")


# ── §4 ───────────────────────────────────────────────────────────────────

def test_the_seat_stamp_guard_is_standing_law():
    """STANDING LAW (2026-08-05, "BUILD-COMPLETE-THEN-DEBUG"): the guard
    has no gate function and no legacy arm.

    Tip-battery evidence that carried it, interventional, one gate at a
    time on one tree: HECA -236 within / -5 steps with severity DOWN
    (transverse worst 3.4344 -> 3.2004 m); byte-inert at KCLT, CYXY,
    SPLP, HEAZ.  SPJC was +16 within — attributed since to the
    emit-amplification corner class (node 10625), not to the guard, and
    fixed by ``emit_snap.shared_corner_authority_nodes``.

    The legacy "0" arm — stamping a seat IMMOVABLE against a runway truth
    it cap-contradicts — manufactures the very both-hard pair that
    ``feasibility-is-guaranteed`` forbids, so it is gone, not gated."""
    assert not hasattr(SV, "seat_stamp_guard_enabled")
    src = open(SV.__file__).read()
    assert 'environ.get("O4_SEAT_STAMP_GUARD"' not in src


def test_a_contradicting_seat_is_detected_and_a_lawful_one_is_not():
    """The guard's predicate, both directions.  A seat inside its
    envelope must be stamped exactly as today — a guard that yields every
    seat would 'fix' the burn by deleting the anchors."""
    env = build_anchor_envelope(_SPINE_ADJ, _HARD)
    assert env.violation(2861, _SEAT_2861, tol=0.01) is not None
    assert env.violation(2861, 60.80, tol=0.01) is None
    assert env.violation(2861, 60.790 + 0.1828 + 0.005, tol=0.01) is None, (
        "a sub-materiality overshoot is PASS-with-residual, not a yield")


def test_the_preserved_set_no_longer_smuggles_a_guarded_seat_back():
    """RED BEFORE / GREEN AFTER on the membership itself: ``building_seats``
    is preserved UNCONDITIONALLY, so without the amendment a seat §4
    refused to stamp is handed its immovability straight back by the
    spine-yield split."""
    frozen = {2861, 2862, 2863}
    common = dict(truth_hard={2863}, runway_nodes=set(),
                  building_seats={2861: _SEAT_2861}, runway_anchor={},
                  seam_pins=set())
    preserved_old, yield_old = SV._spine_yield_membership(
        frozen, 4000, **common)
    assert 2861 in preserved_old and 2861 not in yield_old

    preserved_new, yield_new = SV._spine_yield_membership(
        frozen, 4000, seat_stamp_yield={2861}, **common)
    assert 2861 not in preserved_new
    assert 2861 in yield_new
    # and nothing else moved: the two sets still partition the frozen set.
    assert preserved_new | yield_new >= frozen
    assert not (preserved_new & yield_new)
    assert 2863 in preserved_new, "runway truth is never yielded"


def test_membership_without_the_kwarg_is_unchanged():
    frozen = {1, 2, 3}
    kw = dict(truth_hard={1}, runway_nodes={2}, building_seats={3: 1.0},
              runway_anchor={}, seam_pins=set())
    a = SV._spine_yield_membership(frozen, 10, **kw)
    b = SV._spine_yield_membership(frozen, 10, seat_stamp_yield=None, **kw)
    assert a == b


# ── §5 ───────────────────────────────────────────────────────────────────

def test_an_empty_interval_is_named_not_silently_split(capsys):
    """A free node whose band floor sits ABOVE its neighbour cap slab
    ceiling: the harmonic has no admissible value and today ships
    ``0.5*(lo+hi)`` without a word."""
    # 0 -- 1 -- 2 ; 0 and 2 hard at 0.0, node 1 free with budget 0.1 each
    # side (so its cap ceiling is 0.1) and a band FLOOR of 5.0.
    elev = [0.0, 0.0, 0.0]
    base_hard = [True, False, True]
    spine_adj = {0: [(1, 0.1)], 1: [(0, 0.1), (2, 0.1)], 2: [(1, 0.1)]}
    node_band = [None, (5.0, 9.0), None]
    probe: dict = {}
    SV._solve_spine_profile(elev, base_hard, spine_adj, {},
                            node_band=node_band, max_sweeps=5,
                            probe_out=probe)
    rows = probe.get("empty_intervals") or []
    assert rows, "the empty interval must be RECORDED"
    row = rows[0]
    assert row["node"] == 1
    assert row["lo"] > row["hi"]
    assert row["deficit_m"] > 0.01
    assert row["lo_source"] == "band_floor"
    assert row["hi_source"].startswith("cap_slab_from_"), (
        "the report must name WHICH constraint bound each side — 'an "
        "empty interval' without the arg-max is not an attribution")
    out = capsys.readouterr().out
    assert "[empty-interval]" in out


def test_a_feasible_spine_reports_nothing():
    """The falsifier: no empty interval, no report.  Without it the twin
    would pass for a reporter that always fires."""
    elev = [0.0, 0.0, 0.0]
    base_hard = [True, False, True]
    spine_adj = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 1.0)], 2: [(1, 1.0)]}
    node_band = [None, (-1.0, 1.0), None]
    probe: dict = {}
    SV._solve_spine_profile(elev, base_hard, spine_adj, {},
                            node_band=node_band, max_sweeps=5,
                            probe_out=probe)
    assert (probe.get("empty_intervals") or []) == []
