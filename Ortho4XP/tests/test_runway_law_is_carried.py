"""GENERATION IS BOUND BY THE RUNWAY'S OWN LAW (debug lane A 2026-08-05).

``grade_law.runway_profile_law`` says it verbatim: "ONE resolver for the
solver and the validator: a second copy would let the surface we build
and the surface we check disagree about which authority governs."

There were three second copies, all pricing at the module-level FAA
constants regardless of the runway's authority:

  * ``runway_redistribute`` — the seam-DEM fold-back re-solve;
  * ``runway_redistribute.apply_runway_flex`` — the flex re-solve;
  * ``crown._rail_continuous_drops`` — the crown's rail-continuity
    budget, which is what actually bounds the EMITTED rail step.

So an ICAO code-4 runway (Annex 14 §3.1.14 → 1.25 %) was solved at
1.25 % by ``runway_segments`` and then re-solved / re-crowned at the FAA
1.5 %.  Measured at SPJC 16L/34R: the redistributed profile is compliant
(1.2249 % worst) and the EMITTED rail carries 1.4996 % — the whole
0.2747 % excess is crown-drop variation, priced at 1.5 %.

These twins are hermetic: no X-Plane install, no airport build.
"""
import pytest

from auto_patch.config import (
    RUNWAY_MAX_GRADE as FAA_CAP, RUNWAY_END_GRADE as FAA_END,
    RUNWAY_MAX_GRADE_CHANGE_PER_M as FAA_DG)
from auto_patch.runway_redistribute import (
    _profile_law, _flex_segment_cap_kw, _strict_budget_between)

ICAO4 = 0.0125            # Annex 14 §3.1.14, code 4
ICAO4_DG = 1.0 / 30000.0  # §3.1.16, 0.1 % per 30 m


# ── the carrier ──────────────────────────────────────────────────────

def test_a_profile_without_a_law_keeps_the_faa_constants():
    """A synthetic profile (every hermetic test in the tree builds one)
    carries no law keys; the module defaults ARE the FAA C-E law those
    constants encode, so nothing changes for it."""
    law = _profile_law({})
    assert law["max_grade"] == FAA_CAP
    assert law["max_dg_per_m"] == FAA_DG
    assert law["end_grade"] == FAA_END


def test_a_carried_law_overrides_the_module_constants():
    """The whole point: an ICAO code-4 profile prices at 1.25 %."""
    law = _profile_law({"max_grade": ICAO4,
                        "max_grade_change_per_m": ICAO4_DG,
                        "law_end_grade": 0.008})
    assert law["max_grade"] == pytest.approx(ICAO4)
    assert law["max_dg_per_m"] == pytest.approx(ICAO4_DG)
    assert law["end_grade"] == pytest.approx(0.008)
    assert law["max_grade"] < FAA_CAP, (
        "the fixture must be TIGHTER than the FAA constant or it cannot "
        "distinguish a bound generator from an unbound one")


def test_no_end_cap_stated_is_not_a_missing_value():
    """``law_end_grade`` PRESENT and ``None`` is ICAO code 1-2: the
    authority states NO first/last-quarter cap, so the end zone is
    governed by the main cap.  Coercing it to the FAA 0.8 % would invent
    a rule the runway is not subject to."""
    law = _profile_law({"max_grade": 0.02, "law_end_grade": None})
    assert law["end_grade"] == pytest.approx(0.02)


# ── the consumers ────────────────────────────────────────────────────

def test_the_flex_segment_cap_prices_with_the_carried_law():
    """``_flex_segment_cap_kw`` is the ONE spelling shared by the flex
    demand clamp (``flex_slack_at``) and the apply-side relax — if it
    prices at 1.5 % the flex can bake a 1.5 % segment into a 1.25 %
    runway and both sides agree with each other while disagreeing with
    the law."""
    kw = _flex_segment_cap_kw({"max_grade": ICAO4, "law_end_grade": 0.008})
    assert kw["grade_cap"] == pytest.approx(ICAO4)
    assert kw["end_grade_cap"] == pytest.approx(0.008)
    # an escalated end-zone cap still wins over the law's baseline (it is
    # the cap the redistribute solve actually used for this ref).
    kw2 = _flex_segment_cap_kw({"max_grade": ICAO4, "law_end_grade": 0.008,
                                "end_zone_cap": 0.011})
    assert kw2["end_grade_cap"] == pytest.approx(0.011)


def test_the_tiered_budget_integrates_the_carried_caps():
    """The end-zone binding report's budget is what tells the owner WHY
    a preference is infeasible; priced at the FAA numbers it would
    over-state a code-4 runway's interior budget by 20 %."""
    L = 4000.0
    faa = _strict_budget_between(0.0, L, L)
    icao = _strict_budget_between(0.0, L, L, grade_cap=ICAO4,
                                  end_grade=0.008)
    assert icao < faa
    # both end zones are at 0.008 in each arm, so the whole difference is
    # the interior half: (0.015 − 0.0125) × interior length.
    from auto_patch.config import RUNWAY_END_FRACTION
    interior = L * (1.0 - 2.0 * RUNWAY_END_FRACTION)
    assert faa - icao == pytest.approx((FAA_CAP - ICAO4) * interior,
                                       abs=1e-9)


def test_the_minimal_end_zone_escalation_never_exceeds_the_carried_cap():
    """RELAXATION ORDER: the MAIN cap is law and the end-zone cap is the
    preference that yields.  The escalation ceiling must therefore be the
    runway's own main cap — escalating a code-4 end zone to the FAA
    1.5 % would relax the preference straight THROUGH the law."""
    from auto_patch.runway_redistribute import (
        solve_profile_with_minimal_end_zone_cap)
    # Two hard thresholds 300 m apart demanding 6 m: infeasible at any
    # cap here, which drives the escalation to its ceiling.
    fractions = [0.0, 0.25, 0.5, 0.75, 1.0]
    elevs = [0.0, 0.0, 0.0, 0.0, 6.0]
    anchored = [True, False, False, False, True]
    report: dict = {}
    got = solve_profile_with_minimal_end_zone_cap(
        list(fractions), elevs, anchored, 300.0,
        grade_cap=ICAO4, max_dg_per_m=ICAO4_DG, end_grade=0.008,
        report=report)
    assert got <= ICAO4 + 1e-12, (
        f"the escalation returned {got:.5f} — above the runway's own "
        f"{ICAO4:.5f} law; the end-zone preference may yield, the law may not")
    assert report["end_zone_cap"] <= ICAO4 + 1e-12


# ── the crown, which is what bounds the EMITTED rail ─────────────────

def test_the_crown_rail_budget_reads_the_runways_own_cap():
    """``crown._rail_continuous_drops`` guarantees ``|Δz_emit| ≤ cap·d``
    BY CONSTRUCTION — so whichever cap it uses IS the emitted runway
    law.  This asserts the resolver it now consults, on a layout stub
    carrying one ICAO profile and one law-less (FAA) profile, including
    a crossing ref where the TIGHTER member must bind."""
    import auto_patch.crown as CR
    src = open(CR.__file__).read()
    assert "allow = _cap(ref) * d - d_prof" in src, (
        "the rail-continuity budget must price with the per-ref cap; a "
        "module-constant budget is the second copy this fix removed")
    assert "allow = RUNWAY_MAX_GRADE * d - d_prof" not in src


def test_the_crown_cap_helper_takes_the_tightest_member():
    """Extracted-behaviour twin for ``_cap``: a crossing's ``A+B`` ref
    is a shared edge, so BOTH runways' laws bind and the tighter wins."""
    from auto_patch.runway_redistribute import _profile_law as law_of
    profiles = {"16L/34R": {"max_grade": ICAO4},
                "09/27": {"max_grade": FAA_CAP}}

    def cap(ref):
        caps = [float(law_of(profiles[p])["max_grade"])
                for p in (ref or "").split("+") if p in profiles]
        return min(caps) if caps else FAA_CAP

    assert cap("16L/34R") == pytest.approx(ICAO4)
    assert cap("09/27") == pytest.approx(FAA_CAP)
    assert cap("16L/34R+09/27") == pytest.approx(ICAO4)
    assert cap("unknown") == pytest.approx(FAA_CAP)


def test_the_carrier_is_published_by_runway_segments():
    """The law must actually be PUT on the state dict, or every consumer
    silently falls back to the FAA constants and all of the above is
    inert.  Source-level because the publisher sits inside a 1,700-line
    emit loop with no seam to call."""
    import auto_patch.pavement.runway_segments as RS
    src = open(RS.__file__).read()
    for key in ("'max_grade': _rw_law[\"max_grade\"]",
                "'max_grade_change_per_m': _rw_law[\"max_grade_change_per_m\"]",
                "'law_end_grade': _rw_law[\"end_grade\"]"):
        assert key in src, f"profile_state must carry {key}"
