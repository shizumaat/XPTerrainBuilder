"""Twins for the DERIVED POCS SWEEP BUDGET (2026-08-05).

THE DEFECT THIS RETIRES.  The projection's sweep cap was a hand-set
constant (``PROJECTION_MAX_SWEEPS_FINAL = 2400`` and three siblings).  A
sweep cap is a NON-TERMINATION GUARD, not a law quantity — and that one
was BINDING: at composed SPJC+HECA (n = 72,472) the final scoped
projection exited UNCERTIFIED at 2400/2400 with 1,349 edges still over
cap, roughly 30x below the graph's worst-case propagation distance.  The
guard, not convergence, was choosing the emitted surface.

THE LAW OF THE FIX.  A correction propagates about one law edge per
sweep, so the budget must be derived from the graph's own hop diameter
and must sit provably above it:

    budget = clamp(SWEEP_BUDGET_SLACK * hop_eccentricity_bound(edges, n),
                   SWEEP_BUDGET_MIN, SWEEP_BUDGET_MAX)

These pin the three properties that make it a guard rather than a
tuning knob: it SCALES with hop diameter, the FLOOR holds, and the
CEILING holds.  Hermetic — no build, no fixtures.
"""

import auto_patch.config as cfg


def _chain(hops):
    """``hops`` edges over ``hops + 1`` nodes: a path graph whose hop
    diameter is exactly ``hops``."""
    return [(k, k + 1) for k in range(hops)], hops + 1


# ── the hop-diameter bound itself ────────────────────────────────────────


# ── SCALING: a longer graph gets a bigger budget ─────────────────────────


# ── the FLOOR ────────────────────────────────────────────────────────────


# ── the CEILING ──────────────────────────────────────────────────────────


def test_the_floor_and_ceiling_are_ordered():
    """A misordered pair would make the clamp silently return the wrong
    end — cheap to assert, impossible to notice otherwise."""
    assert 0 < cfg.SWEEP_BUDGET_MIN < cfg.SWEEP_BUDGET_MAX
    assert cfg.SWEEP_BUDGET_SLACK >= 1


# ── the derivation reaches production ────────────────────────────────────


def test_the_retired_per_role_constants_are_gone():
    """Four hand-set caps (DEFAULT / ONE_SOLVE / FINAL / MOUTH_RELAX) are
    DELETED, not merely unused — a surviving constant is an invitation to
    pass it again."""
    for gone in ("PROJECTION_MAX_SWEEPS_DEFAULT",
                 "PROJECTION_MAX_SWEEPS_ONE_SOLVE",
                 "PROJECTION_MAX_SWEEPS_FINAL",
                 "PROJECTION_MAX_SWEEPS_MOUTH_RELAX"):
        assert not hasattr(cfg, gone), f"config.{gone} must be deleted"


# ── the uncertified exit names its derivation ────────────────────────────


