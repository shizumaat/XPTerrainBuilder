"""DUAL CARRIAGEWAYS ARE ONE RAMP — the divergence-growth test.

RULINGS 2026-08-31h (owner):

    A tunnel approach whose carriageways hold CONSTANT SEPARATION for
    the whole approach and to the mouth emits ONE ramp surface spanning
    both (no fork, no inner faces — outer walls only).  A FORK exists
    only where road/rail ways actually DIVERGE (separation grows).  The
    divergence test is the separation profile along the arms.

WHY THE OLD TEST COULD NOT SEE IT.  The pre-ruling discriminator was
ABSOLUTE — ``spread > cluster_span + margin`` — so a wide-but-parallel
pair trips it at every station and reads as a *sustained* fork, which is
exactly what the sustain test then confirms.  Growth is the senior
question and is checked first.

THE MEASURED CASES THIS DISSOLVES (Batch 3 closing arm, OTHH):
25.2537652,51.6032373 — two symmetric arms 6.97 m apart, and
25.2761220,51.6134683 — arms 0.93 m apart, the crotch that could not
hold two 1.6 m wall bands at all.  Both were mis-modelled dual
carriageways.
"""
from __future__ import annotations

import math

import pytest

from auto_patch import bridges


class TestTheBarItself:

    def test_the_growth_bar_clears_the_measured_wobble(self):
        """The sustain spec records twin carriageways drifting 8.3-9.8 m
        over 150 m and crossing their absolute threshold on a 1.2 m
        relative splay.  The bar must sit above that noise."""
        assert bridges.TUNNEL_FORK_MIN_GROWTH_M >= 3.0
        assert bridges.TUNNEL_FORK_MIN_GROWTH_M == pytest.approx(5.0)

    def test_it_is_an_emitter_invariant_not_a_user_knob(self):
        """Same rule as TUNNEL_FORK_SUSTAIN_FRACTION: it lives in the
        emitter, not in config.py."""
        from auto_patch import config
        assert not hasattr(config, "TUNNEL_FORK_MIN_GROWTH_M")


def _growth(spreads):
    """The rule under test, stated directly: widest minus at-the-mouth."""
    return max(sp for _s, sp in spreads) - spreads[0][1]


class TestTheSeparationProfileDecides:
    """The profiles are the shapes the ruling names, at unit scale."""

    def test_constant_separation_is_a_dual_carriageway(self):
        """Wide, parallel, all the way to the mouth — ONE ramp."""
        spreads = [(s, 12.0) for s in range(5, 200, 5)]
        assert _growth(spreads) < bridges.TUNNEL_FORK_MIN_GROWTH_M

    def test_a_wobbling_pair_is_still_a_dual_carriageway(self):
        """The OTHH A-site profile: 9.52 m at the portal, drifting
        8.3-9.8 m for 150 m.  A 1.5 m wobble is not divergence."""
        prof = [9.52, 9.1, 8.6, 8.3, 8.9, 9.4, 9.8, 9.3, 8.7, 9.0]
        spreads = [(5.0 * i, v) for i, v in enumerate(prof)]
        assert _growth(spreads) < bridges.TUNNEL_FORK_MIN_GROWTH_M

    def test_the_6_97_m_arms_are_a_dual_carriageway(self):
        """Batch 3 residual site 25.2537652,51.6032373 — symmetric arms
        holding ~7 m apart."""
        spreads = [(5.0 * i, 6.97 + 0.3 * math.sin(i)) for i in range(30)]
        assert _growth(spreads) < bridges.TUNNEL_FORK_MIN_GROWTH_M

    def test_the_0_93_m_crotch_is_a_dual_carriageway(self):
        """Batch 3 residual site 25.2761220,51.6134683 — the crotch that
        could not hold two 1.6 m bands, because it was never a crotch."""
        spreads = [(5.0 * i, 0.93) for i in range(30)]
        assert _growth(spreads) < bridges.TUNNEL_FORK_MIN_GROWTH_M

    def test_a_real_Y_split_keeps_separating(self):
        """Arms that go different places grow without bound — a fork."""
        spreads = [(5.0 * i, 8.0 + 1.2 * i) for i in range(30)]
        assert _growth(spreads) >= bridges.TUNNEL_FORK_MIN_GROWTH_M

    def test_growth_is_measured_from_the_MOUTH_not_the_minimum(self):
        """'…for the whole approach AND TO THE MOUTH': the baseline is
        the separation at the mouth end of the probe, so a pair that
        pinches in the middle and returns is not thereby a fork."""
        spreads = [(0.0, 12.0), (5.0, 8.0), (10.0, 12.2), (15.0, 12.1)]
        assert _growth(spreads) < bridges.TUNNEL_FORK_MIN_GROWTH_M


class TestItIsWiredAndSenior:

    def test_the_growth_test_runs_BEFORE_the_sustain_test(self):
        """Senior question first: a constant 12 m separation holds above
        an 11.5 m absolute threshold at EVERY station, so the sustain
        test would confirm it as a fork.  Order is the law here."""
        import inspect
        src = inspect.getsource(bridges._emit_portal_cluster)
        g = src.index("TUNNEL_FORK_MIN_GROWTH_M")
        h = src.index("TUNNEL_FORK_SUSTAIN_FRACTION")
        assert g < h, (
            "the growth test must be evaluated before the sustain test")

    def test_it_clears_s_div_rather_than_editing_the_arms(self):
        """Dissolving a fork means never forking: the cluster falls back
        to the single-chain path that emits ONE ramp and cuts its far
        ends open — not a fork emitted and then patched."""
        import inspect
        src = inspect.getsource(bridges._emit_portal_cluster)
        seg = src[src.index("TUNNEL_FORK_MIN_GROWTH_M"):]
        assert "s_div = None" in seg[:2000]
