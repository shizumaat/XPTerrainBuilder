"""Twins for TRANSVERSE IN THE SOLVE — the weighted 4-node transect rows.

Spec ``docs/specs/transverse-hyperplane-solve-spec.md`` §13 (a), (b), (d),
(f); owner ruling RULINGS 2026-08-21; AMENDMENT A1.

The constraint machinery was strictly pairwise (``|z_i − z_j| ≤ b``, unit
coefficients, ``one_solve.py:470``).  A corridor cross-section is not a
pair: its ends are INTERPOLATED along ring edges, so it is
``|w · z| ≤ b`` over four nodes.  These twins pin the half-space
projection, the two-row symmetry, the meters, and the identity of the
zero-transect arm.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch.elevation_per_surface.route_profile import one_solve as OS  # noqa: E402


def _hyper(idx4, w4, b, sid="s0"):
    return (tuple(idx4), tuple(w4), float(b), sid)


def _entry(hyper=(), edges=()):
    return {"edges": list(edges), "hyper": list(hyper)}


# ── (a) THE KERNEL ─────────────────────────────────────────────────────

def test_an_over_cap_transect_is_projected_onto_its_half_space():
    """Four free nodes, a 1 m fall across a transect budgeted at 0.2 m.
    The projection must land the row ON its half-space (residual ≤ tol),
    moving the free nodes in WEIGHT proportion."""
    # near = midpoint of (0,1) = 0.5*z0 + 0.5*z1 ; far = node 2 exactly.
    w = (0.5, 0.5, -1.0, -0.0)
    elev = [1.0, 1.0, 0.0, 0.0]
    rem, bh = OS.feasibility_project(
        elev, [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2)],
                      edges=[(0, 1, 10.0)])], set())
    val = sum(a * b for a, b in zip(w, elev))
    assert val <= 0.2 + 1e-3, f"the half-space was not reached: {val}"
    # …and the correction went in weight proportion: node 2 (weight 1)
    # absorbs twice what each half-weighted near node does.
    assert elev[2] > 0.0 and elev[0] < 1.0
    assert abs((1.0 - elev[0]) - (1.0 - elev[1])) < 1e-9


def test_a_hard_node_absorbs_nothing():
    w = (1.0, 0.0, -1.0, -0.0)
    elev = [1.0, 1.0, 0.0, 0.0]
    OS.feasibility_project(
        elev, [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2)],
                      edges=[(0, 1, 10.0)])], {0})
    assert elev[0] == 1.0, "a hard node moved"
    assert elev[2] > 0.0, "the free node did not absorb the whole excess"


# ── (b) TWO ROWS, BOTH SIDES ───────────────────────────────────────────

@pytest.mark.parametrize("sign", (1.0, -1.0))
def test_the_two_row_pair_bounds_the_transect_from_either_side(sign):
    """``|near − far| ≤ b`` is expressed as ``w`` and ``−w``; whichever
    side is over cap, the pair closes it."""
    w = (1.0, 0.0, -1.0, -0.0)
    elev = [sign * 1.0, 0.0, 0.0, 0.0]
    OS.feasibility_project(
        elev, [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2),
                             _hyper((0, 1, 2, 3),
                                    tuple(-x for x in w), 0.2)],
                      edges=[(0, 1, 10.0)])], set())
    assert abs(elev[0] - elev[2]) <= 0.2 + 1e-3


# ── (d) THE METERS ─────────────────────────────────────────────────────

def test_the_certificate_counts_an_over_cap_transect_as_transverse():
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    w = (1.0, 0.0, -1.0, -0.0)
    elev = [5.0, 0.0, 0.0, 0.0]
    cert = SV.projection_law_certificate(
        [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2)])], elev, 4, set())
    assert "transverse" in cert, cert
    n_over, worst, both_hard = cert["transverse"]
    assert n_over == 1 and worst == pytest.approx(4.8) and both_hard == 0
    # …and every node hard ⇒ counted as both-hard (the transect analogue
    # of an infeasible edge).
    cert2 = SV.projection_law_certificate(
        [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2)])], elev, 4,
        {0, 1, 2, 3})
    assert cert2["transverse"][2] == 1


def test_the_sweep_budget_is_priced_on_the_whole_law():
    """A transect couples four nodes; leaving the rows out of the basis
    derives ``max_iters`` from a smaller graph than the one being
    solved."""
    edges = [(i, i + 1, 1.0) for i in range(8)]
    rows = [_hyper((0, 1, 40, 41), (1.0, 0.0, -1.0, -0.0), 0.2)]
    a, _ = OS.derive_sweep_budget(edges, 42)
    b, _ = OS.derive_sweep_budget(edges, 42, rows)
    assert b >= a


# ── (f) IDENTITY WHEN THERE ARE NO TRANSECTS ───────────────────────────

def test_zero_transects_is_byte_identical():
    edges = [(0, 1, 0.1), (1, 2, 0.1)]
    a = [0.0, 1.0, 2.0]
    b = [0.0, 1.0, 2.0]
    OS.feasibility_project(a, [{"edges": edges}], set())
    OS.feasibility_project(b, [{"edges": edges, "hyper": []}], set())
    assert a == b


def test_a_path_that_cannot_carry_them_refuses(monkeypatch):
    """A projection path that cannot carry the rows must REFUSE, never
    solve a smaller law than it was handed."""
    monkeypatch.setattr(OS, "_chromatic_enabled", lambda: False)
    with pytest.raises(RuntimeError, match="cannot carry"):
        OS.feasibility_project(
            [0.0, 1.0, 0.0, 0.0],
            [_entry(hyper=[_hyper((0, 1, 2, 3),
                                  (1.0, 0.0, -1.0, -0.0), 0.2)],
                    edges=[(0, 1, 10.0)])], set())


# ── THE GUARD (attempt 2, 2026-08-21) ──────────────────────────────────
# Attempt 1 published a -2608 m apron value: a foot a fraction of a
# millimetre from a ring vertex became a near-zero WEIGHT, and the
# half-space step ``r / ||w_free||^2`` divides by that square.  Two
# guards, both asserted here: the foot SNAPS to the vertex it already is
# (geometric floor SHARED_VERTEX_TOL_M / edge length), and the step is
# capped at the row's own violation.

def test_a_foot_within_the_weld_tolerance_snaps_to_its_vertex():
    from auto_patch.lateral_spine_nodes import _snap_param
    # 30 m edge ⇒ floor 0.5/30 = 0.0167
    assert _snap_param(1e-6, 30.0) == 0.0
    assert _snap_param(1.0 - 1e-6, 30.0) == 1.0
    assert _snap_param(0.5, 30.0) == 0.5          # a real mid-edge foot
    # the SAME half metre on a long edge and a short one
    assert _snap_param(0.001, 300.0) == 0.0       # 0.3 m from the corner
    assert _snap_param(0.05, 5.0) == 0.0          # 0.25 m from the corner
    assert _snap_param(0.2, 30.0) == 0.2          # 6 m out: not a vertex
    # the admission tolerance can never survive as a NEGATIVE weight
    assert _snap_param(-1e-13, 30.0) == 0.0


def test_the_walker_never_emits_a_parameter_outside_its_edge():
    """The -1e-9 admission tolerance is about whether the hit EXISTS; the
    parameter is the position, and a position outside its own edge is not
    one.  Attempt 1's bound rows reached t = -1.6e-13."""
    from auto_patch import transect_walk as TW
    ring = [(0.0, -10.0, 10.0), (60.0, -10.0, 10.0),
            (60.0, 10.0, 10.4), (0.0, 10.0, 10.4)]
    sts = list(TW.walk_transects(
        [TW.TransectShape(role="apron", ring=ring, key="W")],
        [TW.TransectAxis(poly=[(0.0, 0.0), (60.0, 0.0)], seg_caps=[0.01])],
        lambda _a: {"apron"}))
    assert sts
    for st in sts:
        assert 0.0 <= st.t_lo <= 1.0 and 0.0 <= st.t_hi <= 1.0


def test_a_degenerate_weight_cannot_move_a_node_further_than_its_violation():
    """The step cap, on the shape attempt 1 actually produced: one free
    node carrying a 1e-6 weight.  Un-capped the correction is ~1e12 x r."""
    w = (1e-6, 1.0 - 1e-6, -1.0, -0.0)
    elev = [0.0, 0.0, -1.0, 0.0]          # r = near - far = 1.0 over b=0.2
    before = list(elev)
    OS.feasibility_project(
        elev, [_entry(hyper=[_hyper((0, 1, 2, 3), w, 0.2)],
                      edges=[(0, 1, 10.0)])], {1, 2})
    r0 = sum(a * b for a, b in zip(w, before)) - 0.2
    moved = max(abs(a - b) for a, b in zip(elev, before))
    assert moved <= abs(r0) + 1e-9, (
        f"a row moved a node by {moved} m against its own {r0} m violation")
    assert all(abs(v) < 1e3 for v in elev), "the projection diverged"
