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


class TestTheBarItself:


    def test_it_is_an_emitter_invariant_not_a_user_knob(self):
        """Same rule as TUNNEL_FORK_SUSTAIN_FRACTION: it lives in the
        emitter, not in config.py."""
        from auto_patch import config
        assert not hasattr(config, "TUNNEL_FORK_MIN_GROWTH_M")


