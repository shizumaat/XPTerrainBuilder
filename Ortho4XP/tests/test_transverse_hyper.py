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
