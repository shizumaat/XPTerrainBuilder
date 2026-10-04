"""The flex demand DEAD ZONE — twins for
``docs/specs/demfollow-joint-spec.md``.

THE DEFECT (attributed in the demfollow probe, HEAZ under
``O4_RUNWAY_DEM_FOLLOW``, 2026-08-05): the envelope demand tolerance
``_DEMAND_TOL_M`` decides which deficits ``_apply_runway_flex_hook`` is
even ALLOWED to see.  At 0.05 m it sits five times above the final reach
band's own materiality floor (0.01 m), so a deficit in [0.01, 0.05) is

  * invisible to the flex — no demand is presented, nothing drains; and
  * material to the band — which then adjudicates it as a law defect.

Measured: 18/36 sinks −0.12 m at its join anchor and 05/23 −0.14 m at its
threshold-join, a 0.0174 m differential across the 292 m taxiway between
them (priced at exactly 1.5 %, so a 4.38 m route budget).  The flex
declined to move and the FINAL band inverted on all 47 route nodes of
that taxiway — a build abort with no lawful demand ever presented.

THE FIX (STANDING LAW; the gate was retired): align the two
floors — 0.05 m → 0.01 m — so demands in the zone are presented at all.

MECHANISM CORRECTION (measured here, against the spec's own text): the
spec expected "the origin split drains ~9 mm from each runway".  It does
not — a 0.0174 m deficit splits to 0.0087 m per runway and the hook's
pre-existing ``move <= 0.01`` kill drops it, so the smallest DRAINABLE
split deficit is just over 0.02 m.  ``TestMoveKillStillBinds`` pins that
boundary.  What the tolerance actually buys at HEAZ is extra demands
that keep the convergence loop running: measured as a 2x2 over one tree,
DEM-follow SOLO aborts at both tolerances (19 demands, 3 rounds, the
same 47 nodes); composed with the self-unlock law aborts coarse (20
demands, 4 rounds) and BUILDS fine (23 demands, 5 rounds, final band 2
sub-materiality inversions = the gate-off control's exactly).

WHY GATED, and what these twins do NOT claim: the fine tolerance moves
HECA's default surface (release anchor a1ade8bd → 675fc645), so it rides
a gate until the next anchor-minting tip.  The move is census-neutral
(law-true 8865/0/126 class-for-class identical), so the gate protects
IDENTITY, not lawfulness.  Separately measured in-lane and NOT pinned
here because it is a build-level result: with the gate on, HEAZ still
aborts under DEM-follow ALONE (the 3-round cap stops the loop before the
geometric tail is drained) and builds clean only in the composed world
(the self-unlock law as well, 5 rounds, "no further demand").  The
tolerance is necessary, not sufficient — these twins pin exactly that
necessity and nothing more.

Hermetic: the two-runway synthetic and the stand-in ``apply_runway_flex``
are reused verbatim from ``test_flex_convergence`` (single-pass — there
is one flex harness, not two).  No fixtures, no network, no X-Plane.
"""
from __future__ import annotations

import os
import sys


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"), _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_flex_convergence as HARNESS                      # noqa: E402
from auto_patch.config import (
    RUNWAY_FLEX_DEMAND_TOL_M,
    runway_flex_demand_tol_m,
)

#: The tolerance the retired ``O4_FLEX_DEMAND_TOL_FINE`` gate's OFF arm
#: used to impose.  It is no longer reachable in production; the twins
#: below build the comparison arm by patching the accessor directly, so
#: the DEAD ZONE the fix closed stays pinned and non-vacuous.
_COARSE_TOL_M = 0.05


def _accept_everything(_ref, _order, _t):
    return True


def _run(monkeypatch, *, fine, deficit_m, budget_m):
    """Drive the REAL hook over the shared synthetic, with the two
    runways separated by exactly ``budget_m + deficit_m`` — so the
    envelope deficit each runway sees is ``deficit_m`` and nothing else.

    ``fine=True`` is PRODUCTION (the tolerance is standing law now);
    ``fine=False`` reconstructs the retired coarse arm by patching the
    config accessor, which is the only way left to show the dead zone
    was real.

    Returns (n_demands, apply, log, final_gap_m)."""
    if not fine:
        import auto_patch.config as _CFG
        monkeypatch.setattr(_CFG, "runway_flex_demand_tol_m",
                            lambda: _COARSE_TOL_M)
    monkeypatch.setattr(HARNESS, "LINK_BUDGET_M", float(budget_m))
    monkeypatch.setattr(HARNESS, "ELEV_LO",
                        HARNESS.ELEV_HI - float(budget_m) - float(deficit_m))
    n, apply, log, layout = HARNESS._run_hook(
        monkeypatch, _accept_everything, gate="0")
    profiles = layout._runway_redistributed_profiles
    hi = min(profiles[HARNESS.REF_HI]['elevs'])
    lo = max(profiles[HARNESS.REF_LO]['elevs'])
    return n, apply, log, hi - lo


# ════════════ the constant itself: the gate is honest ════════════════

class TestTheTolerance:


    def test_no_env_value_reopens_the_dead_zone(self, monkeypatch):
        """The ``O4_FLEX_DEMAND_TOL_FINE`` gate is retired: no setting of
        it may restore the coarse tolerance."""
        for value in ("", "0", "1", "true", "yes"):
            monkeypatch.setenv("O4_FLEX_DEMAND_TOL_FINE", value)
            assert runway_flex_demand_tol_m() == RUNWAY_FLEX_DEMAND_TOL_M
        import auto_patch.config as CFG
        assert 'environ.get("O4_FLEX_DEMAND_TOL_FINE"' not in open(
            CFG.__file__, encoding="utf-8").read()


# ═════════ TWIN 1 — the dead-zone synthetic: 0.02 m drains ═══════════


# ═════════ TWIN 2 — the HEAZ regression: 0.0174 m over 4.38 m ════════


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test drove a v1 solve hook / the v1 cached layout build:
# ``TestDeadZoneSynthetic.test_both_runways_pay_the_origin_split``,
# ``TestDeadZoneSynthetic.test_coarse_tolerance_presents_no_demand_at_all``,
# ``TestDeadZoneSynthetic.test_fine_tolerance_presents_the_demand``,
# ``TestHeazRegression.test_coarse_tolerance_reproduces_the_abort_precondition``,
# ``TestHeazRegression.test_the_bare_split_does_NOT_drain_it``,
# ``TestMoveKillStillBinds.test_at_or_below_the_split_kill_nothing_drains``, `
# `TestMoveKillStillBinds.test_the_whole_band_stays_shut_at_the_coarse_toleran
# ce``.
