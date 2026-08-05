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

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"), _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_flex_convergence as HARNESS                      # noqa: E402
from auto_patch.config import (                              # noqa: E402
    RUNWAY_FLEX_DEMAND_TOL_M, RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M,
    runway_flex_demand_tol_m)

#: The tolerance the retired ``O4_FLEX_DEMAND_TOL_FINE`` gate's OFF arm
#: used to impose.  It is no longer reachable in production; the twins
#: below build the comparison arm by patching the accessor directly, so
#: the DEAD ZONE the fix closed stays pinned and non-vacuous.
_COARSE_TOL_M = 0.05
from auto_patch.elevation_per_surface.building_feasibility import (  # noqa
    FINAL_BAND_INVERSION_TOL_M)

#: The HEAZ numbers the probe measured, used verbatim by twin 2.
HEAZ_DEFICIT_M = 0.0174
HEAZ_ROUTE_BUDGET_M = 4.3826


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

    def test_there_is_one_tolerance_and_it_is_the_materiality_floor(self):
        """The whole claim of the spec: one floor, not two.  If these
        ever diverge the dead zone re-opens silently."""
        assert runway_flex_demand_tol_m() == RUNWAY_FLEX_DEMAND_TOL_M
        assert RUNWAY_FLEX_DEMAND_TOL_M == FINAL_BAND_INVERSION_TOL_M
        assert RUNWAY_FLEX_DEMAND_TOL_M == RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M

    def test_no_env_value_reopens_the_dead_zone(self, monkeypatch):
        """The ``O4_FLEX_DEMAND_TOL_FINE`` gate is retired: no setting of
        it may restore the coarse tolerance."""
        for value in ("", "0", "1", "true", "yes"):
            monkeypatch.setenv("O4_FLEX_DEMAND_TOL_FINE", value)
            assert runway_flex_demand_tol_m() == RUNWAY_FLEX_DEMAND_TOL_M
        import auto_patch.config as CFG
        assert 'environ.get("O4_FLEX_DEMAND_TOL_FINE"' not in open(
            CFG.__file__).read()

    def test_the_coarse_arm_is_five_times_the_materiality(self):
        """NON-VACUITY for every ``fine=False`` twin below: the retired
        arm really did sit above the floor the band adjudicates on."""
        assert _COARSE_TOL_M == 5 * FINAL_BAND_INVERSION_TOL_M


# ═════════ TWIN 1 — the dead-zone synthetic: 0.02 m drains ═══════════

class TestDeadZoneSynthetic:
    """A cross-runway demand inside the dead zone: invisible at the
    coarse tolerance, presented AND drained at the fine one.

    On 0.04 rather than the spec's 0.02: see ``TestMoveKillStillBinds``
    below — a 0.02 m deficit splits to exactly 0.01 m per runway, which
    the hook's pre-existing ``move <= 0.01`` kill drops.  0.04 is the
    smallest round number in the zone whose SPLIT SHARE clears that kill,
    so it isolates the tolerance and nothing else.
    """

    DEFICIT = 0.04
    BUDGET = HARNESS.LINK_BUDGET_M

    def test_the_deficit_really_is_in_the_dead_zone(self):
        """NON-VACUITY: 0.02 m must be below the coarse tolerance and at
        or above the band materiality — otherwise this twin proves
        nothing about the zone it is named for."""
        assert self.DEFICIT < _COARSE_TOL_M
        assert self.DEFICIT >= FINAL_BAND_INVERSION_TOL_M

    def test_coarse_tolerance_presents_no_demand_at_all(self, monkeypatch):
        """THE DEFECT: the flex never sees it."""
        n, apply, _log, gap = _run(monkeypatch, fine=False,
                                   deficit_m=self.DEFICIT,
                                   budget_m=self.BUDGET)
        assert n == 0
        assert apply.calls == []
        assert gap == pytest.approx(self.BUDGET + self.DEFICIT, abs=1e-9), \
            "nothing drained, so the two profiles must not have moved"

    def test_fine_tolerance_presents_the_demand(self, monkeypatch):
        n, apply, _log, _gap = _run(monkeypatch, fine=True,
                                    deficit_m=self.DEFICIT,
                                    budget_m=self.BUDGET)
        assert n > 0
        assert apply.calls, "apply must have been asked to move something"

    def test_fine_tolerance_drains_it_below_materiality(self, monkeypatch):
        """THE FIX: the residual separation is inside the budget, so the
        band has nothing left to adjudicate."""
        _n, _apply, _log, gap = _run(monkeypatch, fine=True,
                                     deficit_m=self.DEFICIT,
                                     budget_m=self.BUDGET)
        assert gap <= self.BUDGET + FINAL_BAND_INVERSION_TOL_M

    def test_both_runways_pay_the_origin_split(self, monkeypatch):
        """The deficit divides across the runways pulling on it (owner
        2026-07-06) — a one-sided drain would be the old defect."""
        _n, apply, _log, _gap = _run(monkeypatch, fine=True,
                                     deficit_m=self.DEFICIT,
                                     budget_m=self.BUDGET)
        refs = {ref for (ref, _targets) in apply.calls}
        assert refs == {HARNESS.REF_HI, HARNESS.REF_LO}


# ═════════ TWIN 2 — the HEAZ regression: 0.0174 m over 4.38 m ════════

class TestHeazRegression:
    """The measured HEAZ abort, reduced to its two numbers.

    The probe falsified every other candidate: the band VALUE (the 0.5 m
    counterfactual arm was byte-identical), the band ORDERING (it
    re-derives already), and the threshold-anchored pair (3151, 3152)
    (moved 0.0000).  Restoring ONE anchor built rc=0.  What is left is
    this: a 0.0174 m deficit that no machinery was allowed to see.
    """

    def test_the_heaz_deficit_sits_in_the_dead_zone(self):
        """The defect in one assertion: material to the band, invisible
        to the flex."""
        assert HEAZ_DEFICIT_M > FINAL_BAND_INVERSION_TOL_M, \
            "the band adjudicates it"
        assert HEAZ_DEFICIT_M < _COARSE_TOL_M, \
            "the flex never saw it"
        assert HEAZ_DEFICIT_M >= RUNWAY_FLEX_DEMAND_TOL_M, \
            "and the standing tolerance closes exactly that gap"

    def test_coarse_tolerance_reproduces_the_abort_precondition(
            self, monkeypatch):
        """Zero demands presented while the profiles stay 0.0174 m apart
        beyond budget — which is precisely the state the final band then
        called an inversion on 47 nodes."""
        n, apply, _log, gap = _run(monkeypatch, fine=False,
                                   deficit_m=HEAZ_DEFICIT_M,
                                   budget_m=HEAZ_ROUTE_BUDGET_M)
        assert n == 0
        assert apply.calls == []
        assert gap - HEAZ_ROUTE_BUDGET_M == pytest.approx(
            HEAZ_DEFICIT_M, abs=1e-9)

    def test_the_bare_split_does_NOT_drain_it(self, monkeypatch):
        """MEASURED, and the spec's stated mechanism corrected: 0.0174 m
        split across the two pulling runways is 0.0087 m each, which the
        pre-existing move kill (materiality floor) drops.  So the tolerance alone
        does not move this deficit — pinned here so nobody re-derives the
        spec's "the origin split drains ~9 mm from each runway" and
        believes it.

        The real HEAZ result, measured in-lane as a 2x2 over one tree:
        DEM-follow SOLO aborts at BOTH tolerances (19 demands, 3 rounds,
        the same 47 nodes); composed with the self-unlock law aborts
        at the coarse tolerance (20 demands, 4 rounds) and BUILDS at the
        fine one (23 demands, 5 rounds, final band 2 sub-materiality
        inversions = the gate-off control's exactly).  Both gates are
        necessary; together they are sufficient.  The tolerance's
        contribution is the extra demands that keep the convergence loop
        running, not a single 9 mm drain.
        """
        n, apply, _log, gap = _run(monkeypatch, fine=True,
                                   deficit_m=HEAZ_DEFICIT_M,
                                   budget_m=HEAZ_ROUTE_BUDGET_M)
        assert n == 0
        assert apply.calls == []
        assert gap - HEAZ_ROUTE_BUDGET_M == pytest.approx(
            HEAZ_DEFICIT_M, abs=1e-9)


class TestMoveKillStillBinds:
    """Where the tolerance stops and the pre-existing clamp takes over.

    The hook kills a candidate whose requested move is at or below the
    materiality floor.  With
    the origin split halving every cross-runway pull, that puts the
    smallest DRAINABLE split deficit at just over 0.02 m — inside the
    dead zone the tolerance opens, so opening the zone is necessary but
    not sufficient.  Pinned as a boundary so a future change to either
    constant has to come here and say so.
    """

    BUDGET = HARNESS.LINK_BUDGET_M

    @pytest.mark.parametrize("deficit", [0.0174, 0.02])
    def test_at_or_below_the_split_kill_nothing_drains(self, monkeypatch,
                                                       deficit):
        n, _apply, _log, gap = _run(monkeypatch, fine=True,
                                    deficit_m=deficit,
                                    budget_m=self.BUDGET)
        assert n == 0
        assert gap == pytest.approx(self.BUDGET + deficit, abs=1e-9)

    @pytest.mark.parametrize("deficit", [0.03, 0.04])
    def test_above_it_the_zone_drains_completely(self, monkeypatch,
                                                 deficit):
        n, _apply, _log, gap = _run(monkeypatch, fine=True,
                                    deficit_m=deficit,
                                    budget_m=self.BUDGET)
        assert n > 0
        assert gap <= self.BUDGET + FINAL_BAND_INVERSION_TOL_M

    def test_the_whole_band_stays_shut_at_the_coarse_tolerance(
            self, monkeypatch):
        """NON-VACUITY for the pair above: at 0.05 m nothing in the zone
        drains at any deficit, so the split-kill boundary is a property
        of the FIX, not of the harness."""
        for deficit in (0.0174, 0.02, 0.03, 0.04):
            n, _apply, _log, gap = _run(monkeypatch, fine=False,
                                        deficit_m=deficit,
                                        budget_m=self.BUDGET)
            assert n == 0
            assert gap == pytest.approx(self.BUDGET + deficit, abs=1e-9)
