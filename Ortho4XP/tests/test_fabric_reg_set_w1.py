"""The fabric-model REG SET, encoded — phase B work item W1.

Spec: ``docs/specs/fabric-phase-b-spec.md`` W1.  Source of every value:
``docs/specs/fabric-model-reg-set.md`` (all rows PV-2026-08-08 against
ICAO Annex 14 Vol I 8th ed., EASA CS-ADR-DSN Issue 7, and the
owner-supplied AC 150/5300-13B Chg 1 "with errata" in ``regs/``).  Owner
law: ``docs/RULINGS.md`` 2026-08-08 "Reg-set rulings" 1-4, "105 m
precision strip DROPPED" (which REVERSES the same-day adoption — Q5
encodes nothing), "THE FABRIC MODEL"; and 2026-08-02 "Region-specific
rulesets" (jurisdictional fidelity, emitter and validator read the SAME
ruleset).

Eight twin families, one per W1 entry family, plus three cross-cutting
ones:

  A. the three-axis FAA RSA / ROFA width matrix (F-9)
  B. the per-end RSA length FUNCTION (F-12 / R11)
  C. the TWO lip families (F-10)
  D. taxiway shoulder width by TDG (F-11)
  E. R24 — the TOFA back slope, FAA only
  F. the 1.0 % taxiway cross-fall (reg-set ruling 2)
  G. the 105 m precision-approach graded strip — DROPPED, asserted as
     an ABSENCE (Q5, reversed)
  H. the ICAO graded-strip mandatory-DOWN drop (reg-set ruling 1)

  X1. PROVENANCE — every W1 entry carries value, citation, authority
      class and PV date, machine-checkably.
  X2. JURISDICTIONAL FIDELITY — no entry blends the two authorities.
  X3. NO EMITTER BEHAVIOUR CHANGE **AT W1** — every live consumed
      constant is still pinned to the value it had before W1, and the
      envelope is still bit-for-bit what it was WITH W2'S FLAGS OFF.
      W2 flipped the three consumers (``RULESET_W2_FLIPS``); the pin
      twins retired into successors in the same commit, and the
      successors below assert BOTH arms — off-arm identity and the
      authority-true on-arm values.

Every family's twin asserts LOCKSTEP the same way: there is exactly ONE
accessor, and it returns the same answer to whoever asks.  A family
whose emitter and validator each grow a private reader is the
census-wrapper defect wearing a different hat.
"""
import dataclasses

import pytest

from auto_patch import config as CFG
from auto_patch import grade_law as GL


_RULESETS = ("faa", "icao")


# ══════════════════════════════════════════════════════════════════════
# A — the three-axis FAA RSA / ROFA width matrix (F-9)
# ══════════════════════════════════════════════════════════════════════

def test_A_the_matrix_has_all_three_axes():
    """Appendix G is keyed AAC group × ADG × visibility minimum.  The
    repo carried ONE column; F-9 says the failure mode on this table is
    a changed KEY, never a changed number."""
    assert set(CFG.FAA_AAC_GROUPS) == {"A/B", "C/D/E"}
    assert CFG.FAA_ADG_NUMERALS == ("I", "II", "III", "IV", "V", "VI")
    assert CFG.FAA_VISIBILITY_MINIMA == (
        "visual", "ge_1mi", "ge_3_4mi", "lt_3_4mi")
    # every RDC row carries all four visibility columns
    for rdc, cols in CFG.FAA_RSA_WIDTH_FT_BY_RDC.items():
        assert set(cols) == set(CFG.FAA_VISIBILITY_MINIMA), rdc


def test_A_the_two_missing_AB_rows_are_restored():
    """F-9 consequence 1: "A/B-III is 300 ft (45.7 m half-width) and
    A/B-IV is 500 ft (76.2 m).  The repo's three-value table collapses
    A/B to two entries." """
    assert CFG.faa_rsa_width_ft("A/B", "III") == 300
    assert CFG.faa_rsa_width_ft("A/B", "IV") == 500
    assert CFG.faa_rsa_half_width_m("A/B", "III") == pytest.approx(45.7)
    assert CFG.faa_rsa_half_width_m("A/B", "IV") == pytest.approx(76.2)


def test_A_the_visibility_axis_is_present():
    """F-9 consequence 2: at minimums lower than 3/4 mile the RSA widens
    to 300 ft for A/B-I AND A/B-II and to 400 ft for A/B-III.  C/D/E is
    flat at 500 ft across all four columns — which is exactly why the
    omission has never shown at KCLT."""
    assert CFG.faa_rsa_width_ft("A/B", "I", "lt_3_4mi") == 300
    assert CFG.faa_rsa_width_ft("A/B", "II", "lt_3_4mi") == 300
    assert CFG.faa_rsa_width_ft("A/B", "III", "lt_3_4mi") == 400
    for adg in CFG.FAA_ADG_NUMERALS:
        widths = {CFG.faa_rsa_width_ft("C/D/E", adg, col)
                  for col in CFG.FAA_VISIBILITY_MINIMA}
        assert widths == {500}, adg
    # the default column is the one the builder can actually key today
    assert CFG.FAA_VISIBILITY_DEFAULT == "ge_3_4mi"
    assert (CFG.faa_rsa_width_ft("A/B", "I")
            == CFG.faa_rsa_width_ft("A/B", "I", "ge_3_4mi"))


def test_A_rofa_widths_and_the_small_aircraft_row():
    """App. G dim Q: 400 ft A/B-I, 500 ft A/B-II, 800 ft everywhere
    else, 800 ft in every <3/4-mile column; the A/B-I small-aircraft
    table (G-1) is 250 ft."""
    assert CFG.faa_rofa_width_ft("A/B", "I") == 400
    assert CFG.faa_rofa_width_ft("A/B", "II") == 500
    assert CFG.faa_rofa_width_ft("C/D/E", "V") == 800
    assert CFG.faa_rofa_width_ft("A/B", "I", "lt_3_4mi") == 800
    assert CFG.faa_rofa_width_ft("A/B", "I", small_aircraft=True) == 250
    # ...and no RSA small-aircraft row is invented: the verified table
    # states none, so asking for one gets the ordinary row.
    assert CFG.FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT.keys() == {("A/B", "I")}


def test_A_the_letter_proxy_is_a_VIEW_of_the_matrix_not_a_second_copy():
    """NO BEHAVIOUR CHANGE.  The carried literals are pinned here, and
    the live tables are now derived from the matrix — so this twin fails
    if the derivation ever moves a number, which is the whole point of
    re-rooting rather than duplicating."""
    carried_rsa = {"A": 18.3, "B": 22.9, "C": 76.2,
                   "D": 76.2, "E": 76.2, "F": 76.2}
    carried_rofa = {"A": 61.0, "B": 76.2, "C": 121.9,
                    "D": 121.9, "E": 121.9, "F": 121.9}
    assert CFG.FAA_RSA_HALF_WIDTH_M_BY_LETTER == carried_rsa
    assert CFG.FAA_ROFA_HALF_WIDTH_M_BY_LETTER == carried_rofa
    for letter, rdc in CFG.FAA_RDC_BY_CODE_LETTER.items():
        assert CFG.FAA_RSA_HALF_WIDTH_M_BY_LETTER[letter] == \
            CFG.faa_rsa_half_width_m(*rdc)
        assert CFG.FAA_ROFA_HALF_WIDTH_M_BY_LETTER[letter] == \
            CFG.faa_rofa_half_width_m(*rdc)


def test_A_lockstep_the_live_strip_accessor_is_unmoved():
    """The strip half-width accessor emitter and validator share still
    returns exactly what it returned before W1 — 76.2 m at FAA C/D/E,
    75.0 m at ICAO code 4, the ~1.2 m KCLT widening.  Re-rooting the
    table on the matrix must be invisible from every call site.

    Lockstep is asserted as SOURCE plus VALUE, never as object
    identity: several suites ``importlib.reload(config)``, which mints
    a new function object while the emitter's module-level alias still
    points at the old one.  That is a reload artefact, not a law
    divergence — an identity assertion here fails only in a full-suite
    run and says nothing about the regulation."""
    import inspect
    from auto_patch import adjacent_ground as AG
    assert CFG.ruleset_strip_half_width_m(4, "E", "faa") == 76.2
    assert CFG.ruleset_strip_half_width_m(4, "E", "icao") == 75.0
    # the emitter READS the accessor; it does not carry its own table
    src = inspect.getsource(AG)
    assert "ruleset_strip_half_width_m as _ruleset_strip_half_width_m" in src
    assert "FAA_RSA_HALF_WIDTH_M_BY_LETTER = " not in src
    # ...and every reader answers with the same number
    for code, letter in ((4, "E"), (3, "C"), (1, "A")):
        for key in _RULESETS:
            expected = CFG.ruleset_strip_half_width_m(code, letter, key)
            assert AG._ruleset_strip_half_width_m(code, letter, key) == expected
            assert GL.ruleset_strip_half_width_m(code, letter, key) == expected


def test_A_an_unknown_key_raises_never_guesses():
    """A law must never silently pick a column."""
    with pytest.raises(ValueError):
        CFG.faa_rsa_width_ft("A/B", "VII")
    with pytest.raises(ValueError):
        CFG.faa_rsa_width_ft("C/D/E", "III", "half_a_mile")


# ══════════════════════════════════════════════════════════════════════
# B — the per-end RSA length FUNCTION (F-12 / R11, reg-set ruling 3)
# ══════════════════════════════════════════════════════════════════════

def test_B_it_is_a_function_of_four_keys_not_a_constant():
    """F-12: "the shape of the fix is not 'add a constant' — it is
    ``runway_end_governed_length`` becoming a function of (ruleset, RDC,
    per-end visibility minimum, per-end vertical guidance, stopway
    presence)."  Each key must be able to move the answer."""
    # Each key gets the row where it actually moves the answer; where a
    # key does NOT move a row (A/B-III's R and P coincide at 600 ft)
    # that is the table's own shape, not a missing axis.
    base_ab = CFG.faa_rsa_end_length_m("A/B", "I")
    assert CFG.faa_rsa_end_length_m("C/D/E", "I") != base_ab         # RDC
    assert CFG.faa_rsa_end_length_m(
        "A/B", "I", visibility_minimum="lt_3_4mi") != base_ab        # vis
    base_cde = CFG.faa_rsa_end_length_m("C/D/E", "V")
    assert CFG.faa_rsa_end_length_m(
        "C/D/E", "V", vertical_guidance=True) != base_cde            # fn 11
    assert CFG.faa_rsa_governed_length_beyond_runway_end_m(
        "C/D/E", "V", stopway_length_m=90.0) != base_cde             # fn 9
    assert CFG.get_ruleset("faa").resa_length_is_per_end_function is True
    assert CFG.get_ruleset("icao").resa_length_is_per_end_function is False


def test_B_dim_R_beyond_the_departure_end():
    """App. G dim R, per END: 240 ft A/B-I, 300 ft A/B-II, 600 ft
    A/B-III, 1,000 ft A/B-IV and every C/D/E row; the <3/4-mile column
    raises A/B-I and A/B-II to 600 ft and A/B-III to 800 ft."""
    for adg, ft in (("I", 240), ("II", 300), ("III", 600), ("IV", 1000)):
        assert CFG.faa_rsa_end_length_m("A/B", adg) == pytest.approx(
            ft * 0.3048, abs=0.05), adg
    for adg in CFG.FAA_ADG_NUMERALS:
        assert CFG.faa_rsa_end_length_m("C/D/E", adg) == pytest.approx(304.8)
    assert CFG.faa_rsa_end_length_m(
        "A/B", "I", visibility_minimum="lt_3_4mi") == pytest.approx(182.9)
    assert CFG.faa_rsa_end_length_m(
        "A/B", "III", visibility_minimum="lt_3_4mi") == pytest.approx(243.8)


def test_B_fn11_dispatches_on_vertical_guidance():
    """App. G fn 11, verbatim: "This value only applies if that runway
    end is equipped with electronic or visual vertical guidance… If
    there is no such guidance for that runway, use the value for 'length
    beyond departure end.'"  CIFP supplies the key (RULINGS "Instrument
    truth is law")."""
    # C/D/E: 1,000 ft beyond the departure end, 600 ft prior to a
    # vertically-guided threshold — the guided end is SHORTER.
    assert CFG.faa_rsa_end_length_m("C/D/E", "V") == pytest.approx(304.8)
    assert CFG.faa_rsa_end_length_m(
        "C/D/E", "V", vertical_guidance=True) == pytest.approx(182.9)
    # A/B-I and A/B-II: R and P coincide, so guidance moves nothing.
    for adg in ("I", "II"):
        assert (CFG.faa_rsa_end_length_m("A/B", adg, vertical_guidance=True)
                == CFG.faa_rsa_end_length_m("A/B", adg))


def test_B_fn9_is_the_DATUM_and_is_a_separate_key():
    """App. G fn 9, verbatim: "The RSA length beyond the runway end
    begins at the runway end when a stopway is not present.  When a
    stopway is present, the length begins at the stopway end."

    Datum and length are independent — conflating them is what turned a
    per-end table into one symmetric ICAO-derived constant."""
    assert CFG.faa_rsa_end_datum_offset_m() == 0.0
    assert CFG.faa_rsa_end_datum_offset_m(120.0) == 120.0
    assert CFG.faa_rsa_end_datum_offset_m(None) == 0.0
    whole = CFG.faa_rsa_governed_length_beyond_runway_end_m(
        "C/D/E", "V", stopway_length_m=120.0)
    assert whole == pytest.approx(120.0 + 304.8)
    # the stopway does not change the LENGTH, only where it starts
    assert CFG.faa_rsa_end_length_m("C/D/E", "V") == pytest.approx(304.8)


def test_B_the_two_datums_are_per_source_never_blended():
    """Reg-set ruling 3, "fix both per source": ICAO measures from the
    END OF THE RUNWAY STRIP (§3.5.3), which itself runs 60 m past the
    runway end (§3.4.2, 30 m at code 1 non-instrument); the FAA measures
    from the runway end, or the stopway end where one exists (fn 9)."""
    assert CFG.ruleset_resa_length_datum("icao") == "strip_end"
    assert CFG.ruleset_resa_length_datum("faa") == "runway_or_stopway_end"
    assert CFG.ruleset_strip_beyond_end_m(4, "icao") == 60.0
    assert CFG.ruleset_strip_beyond_end_m(1, "icao") == 30.0
    assert CFG.ruleset_strip_beyond_end_m(1, "icao", instrument=True) == 60.0
    # the FAA has no separate "strip", so the ICAO datum offset is None
    assert CFG.ruleset_strip_beyond_end_m(4, "faa") is None


def test_B_icao_mandate_and_recommendation_are_separate_keys():
    """§3.5.3 **shall** 90 m against §3.5.4 **should** 240 / 120 / 30 m.
    Ruling 3 handles them "as mandate-vs-recommendation", so a caller
    cannot silently take the softer number."""
    assert CFG.ruleset_resa_length_m(4, "icao") == 90.0
    assert CFG.ruleset_resa_length_m(4, "icao", mandate="recommended") == 240.0
    assert CFG.ruleset_resa_length_m(1, "icao", mandate="recommended") == 30.0
    assert CFG.ruleset_resa_length_m(
        1, "icao", mandate="recommended", instrument=True) == 120.0
    with pytest.raises(ValueError):
        CFG.ruleset_resa_length_m(4, "icao", mandate="whatever")
    # the FAA publishes no such constant — its length is the function
    assert CFG.ruleset_resa_length_m(4, "faa") is None
    assert CFG.ruleset_resa_length_m(4, "faa", mandate="recommended") is None


# ══════════════════════════════════════════════════════════════════════
# C — the TWO lip families (F-10)
# ══════════════════════════════════════════════════════════════════════

def test_C_the_faa_has_two_different_lips():
    """F-10's table, exactly:

      runway / shoulder / stopway edge — Fig. 3-33 Detail A note 2 —
      3 m — 3 %-5 % negative
      taxiway / taxilane / apron edge  — ¶4.14.2 Standards item 4 —
      3 m — 5 ±0.5 % ⇒ 4.5 %-5.5 %

    The widths agree; the bands differ in BOTH directions."""
    rw_w, rw_lo, rw_hi = CFG.ruleset_runway_edge_lip("faa")
    tw_w, tw_lo, tw_hi = CFG.ruleset_taxiway_edge_lip("faa")
    assert (rw_w, rw_lo, rw_hi) == (3.0, 0.03, 0.05)
    assert (tw_w, tw_lo, tw_hi) == (3.0, 0.045, 0.055)
    assert tw_w == rw_w, "the widths agree (3 m)"
    assert tw_lo > rw_lo, "steeper at the floor (4.5 vs 3.0)"
    assert tw_hi > rw_hi, "above the runway ceiling (5.5 vs 5.0)"


def test_C_the_icao_taxiway_lip_is_UNSOURCED():
    """F-3 / F-10: §3.11.5 and CS ADR-DSN.D.330(b) state flush, an up
    cap and a down cap — and no lip.  Absence verified by full read, so
    under jurisdictional fidelity the ICAO taxiway lip is None, not a
    copy of the runway's."""
    assert CFG.ruleset_taxiway_edge_lip("icao") == (None, None, None)
    # the ICAO RUNWAY lip is real and stays (§3.4.15 final clause)
    assert CFG.ruleset_runway_edge_lip("icao") == (3.0, 0.03, 0.05)


def test_C_the_taxiway_lip_is_carved_OUT_of_the_TSA_band():
    """¶4.14.2 item 5 states the 1.5-5 % TSA band "except as noted in
    subparagraph 4 above", so lip and band are a near-zone/far-zone
    pair exactly like the RSA's — never alternatives."""
    assert CFG.ruleset_taxiway_lip_carved_out_of_band("faa") is True
    assert CFG.ruleset_taxiway_lip_carved_out_of_band("icao") is False
    faa = CFG.get_ruleset("faa")
    assert (faa.taxiway_strip_band_min_down_slope,
            faa.taxiway_strip_band_max_down_slope) == (0.015, 0.05)


def test_C_lockstep_one_reader_per_lip_family():
    """Two families, two accessors, and neither is a view of the other —
    the collapse F-10 reports is exactly what happens when one reader
    serves two surfaces."""
    for key in _RULESETS:
        assert (CFG.ruleset_runway_edge_lip(key)
                == CFG.ruleset_runway_edge_lip(CFG.get_ruleset(key)))
        assert (CFG.ruleset_taxiway_edge_lip(key)
                == CFG.ruleset_taxiway_edge_lip(CFG.get_ruleset(key)))
    assert (CFG.ruleset_runway_edge_lip("faa")
            != CFG.ruleset_taxiway_edge_lip("faa"))


# ══════════════════════════════════════════════════════════════════════
# D — taxiway shoulder width by TDG (F-11, Table 4-2)
# ══════════════════════════════════════════════════════════════════════

def test_D_width_is_TDG_keyed():
    """AC Table 4-2: 10 ft (3.0 m) TDG 1A/1B, 15 ft (4.6 m) 2A/2B,
    20 ft (6.1 m) 3/4, 30 ft (9.1 m) 5/6.  The repo carried this "by
    ADG" — a DISCREPANT KEY, not a wrong number."""
    expect = {"1A": 3.0, "1B": 3.0, "2A": 4.6, "2B": 4.6,
              "3": 6.1, "4": 6.1, "5": 9.1, "6": 9.1}
    for tdg, width in expect.items():
        assert CFG.ruleset_taxiway_shoulder_width_m(tdg, "faa") == width, tdg
    assert CFG.FAA_TAXIWAY_SHOULDER_WIDTH_FT_BY_TDG["3"] == 20


def test_D_fn3_four_engine_TDG6():
    """Table 4-2 fn 3: 40 ft (12.2 m) where the most demanding aircraft
    has four engines and is TDG 6.  It applies at TDG 6 only."""
    assert CFG.ruleset_taxiway_shoulder_width_m(
        "6", "faa", four_engine=True) == 12.2
    assert CFG.ruleset_taxiway_shoulder_width_m(
        "5", "faa", four_engine=True) == 9.1


def test_D_provision_stays_ADG_keyed():
    """¶4.13.1 Standards item 2 — paved shoulders for ADG-IV and larger.
    Width TDG, provision ADG: two axes that must not be blended into
    one table (the blend is how F-11 happened)."""
    assert CFG.ruleset_taxiway_shoulder_paved_from_adg("faa") == "IV"
    assert CFG.ruleset_taxiway_shoulder_paved_from_adg("icao") is None


def test_D_icao_states_an_overall_width_and_no_per_side_width():
    """§3.10.1 / CS ADR-DSN.D.305(a) give taxiway+shoulders ≥25 m (C),
    34 m (D), 38 m (E), 44 m (F) and no per-side number at all."""
    assert CFG.ruleset_taxiway_shoulder_width_m("5", "icao") is None
    for letter, total in (("C", 25.0), ("D", 34.0),
                          ("E", 38.0), ("F", 44.0)):
        assert CFG.ruleset_taxiway_plus_shoulders_total_width_m(
            letter, "icao") == total
    assert CFG.ruleset_taxiway_plus_shoulders_total_width_m("D", "faa") is None


def test_D_the_taxiway_shoulder_SLOPE_stays_a_no_op():
    """R17 — the FAA taxiway-shoulder band (1.5-5 %, ¶4.14.2 item 3) is
    numerically identical to its TSA band (item 5), so riding the strip
    band reproduces it exactly; ICAO states no taxiway-shoulder slope.
    KEEP, now for a verified reason rather than an assumed one."""
    faa = CFG.get_ruleset("faa")
    assert (faa.taxiway_strip_band_min_down_slope,
            faa.taxiway_strip_band_max_down_slope) == (0.015, 0.05)


# ══════════════════════════════════════════════════════════════════════
# E — R24, the TOFA back slope (FAA only, new this round)
# ══════════════════════════════════════════════════════════════════════

def test_E_tofa_back_slope_is_4_to_1_and_FAA_only():
    """¶4.14.2 Standards item 6b + Figure 4-29: ≤4:1 where a back slope
    is necessary.  ICAO has no object-free-area family — its analogue is
    §3.11.6's 5 % cap, already ``ungraded_strip_max_up_slope``."""
    assert CFG.ruleset_tofa_back_slope_ratio("faa") == 4.0
    assert CFG.ruleset_tofa_back_slope_ratio("icao") is None


def test_E_it_is_far_steeper_than_any_ROFA_value():
    """R24's own note: 4:1 is far steeper than any ROFA back slope
    (8:1 / 10:1 / 16:1), so it will rarely bind — but its absence left
    the FAA taxiway branch with NO far-zone ceiling at all."""
    faa = CFG.get_ruleset("faa")
    tofa_rise = 1.0 / CFG.ruleset_tofa_back_slope_ratio("faa")
    for ratio in faa.rofa_back_slope_ratio_by_adg.values():
        assert tofa_rise > 1.0 / ratio
    # a CEILING, never a mandate: the ratio is a maximum RISE
    assert tofa_rise == pytest.approx(0.25)


# ══════════════════════════════════════════════════════════════════════
# F — the 1.0 % taxiway cross-fall (R20 / reg-set ruling 2)
# ══════════════════════════════════════════════════════════════════════

def test_F_faa_states_the_minimum_as_a_Standard():
    """¶4.14.2 Standards item 1a: "1.0 to 1.5 percent from centerline to
    pavement edge".  1.0 % is simultaneously the FAA runway transverse
    minimum (Table 3-6 S-1), so it is one number, not two."""
    faa = CFG.get_ruleset("faa")
    assert faa.taxi_transverse_min == 0.010
    assert faa.runway_transverse_min == 0.010
    assert CFG.ruleset_taxi_transverse_min_provisional("faa") is False
    entry = CFG.reg_entry("taxi_transverse_min", "faa")
    assert entry.authority_class == "Standard"


def test_F_icao_takes_it_as_a_named_PROVISIONAL_house_constant():
    """Reg-set ruling 2: ICAO states NO taxiway minimum anywhere, so the
    FAA 1.0 % is adopted here as a named house constant, labelled
    PROVISIONAL, with the ICAO text quoted beside it.  F-6's distinction
    is preserved IN THE LABEL, not erased by it."""
    icao = CFG.get_ruleset("icao")
    assert icao.taxi_transverse_min == 0.010
    assert CFG.ruleset_taxi_transverse_min_provisional("icao") is True
    entry = CFG.reg_entry("taxi_transverse_min", "icao")
    assert entry.authority_class == "house constant (PROVISIONAL)"
    # ...and it sits INSIDE the ICAO ceiling, with 0.5 pp of headroom
    assert icao.taxi_transverse_min < CFG.ruleset_taxi_transverse_max(
        "D", "icao")
    assert (CFG.ruleset_taxi_transverse_max("D", "icao")
            - icao.taxi_transverse_min) == pytest.approx(0.005)


def test_F_bind_the_MINIMUM_never_the_CROWN_FORM():
    """The cross-fall is a *Standard*; the centre crown is only a
    *Recommended Practice* on the same page, and item 1c admits a
    constant-slope shed section.  So a mandated crown is NOT
    primary-sourced on either ruleset."""
    for key in _RULESETS:
        assert CFG.ruleset_taxi_crown_form_binding(key) is False
    assert CFG.reg_entry(
        "taxi_crown_form_binding", "faa").authority_class == \
        "Recommended Practice"


def test_F_the_taxiway_minimum_stays_RECORDED_NOT_BOUND():
    """W1 is constants only.  ``CROWN_MINIMUM_BOUND_TAXIWAYS`` is still
    False, so giving the ICAO field a value moves no emitted geometry
    and no census row: the taxiway transect band stays symmetric under
    BOTH rulesets.

    The old third assertion — that the drainage-minimum family never read
    a taxiway either — went with the family (RULINGS 2026-08-13b,
    "DRAINAGE MINIMUM RETIRES — ONLY RUNWAYS CROWN")."""
    assert CFG.CROWN_MINIMUM_BOUND_TAXIWAYS is False
    assert GL.transverse_minimum_binds("taxiway") is False
    for key in _RULESETS:
        lo, hi = GL.transverse_surface_bounds("taxiway", "C", 11.0, key)
        assert lo == pytest.approx(-hi) and hi > 0.0


def test_F_lockstep_one_reader_for_the_taxiway_minimum():
    """Emitter and validator both go through
    ``grade_law.transverse_minimum_for_role``, which reads the ruleset
    field — there is no second copy to disagree with."""
    for key in _RULESETS:
        assert (GL.transverse_minimum_for_role("taxiway", key)
                == CFG.get_ruleset(key).taxi_transverse_min)


# ══════════════════════════════════════════════════════════════════════
# G — the 105 m precision-approach graded strip: DROPPED (Q5, reversed)
# ══════════════════════════════════════════════════════════════════════

def test_G_the_105m_precision_strip_is_NOT_encoded_anywhere():
    """RULINGS 2026-08-08 "105 m precision strip DROPPED (owner;
    supersedes the same-day adoption)".  Owner, on learning the 105 m
    has no FAA anchor: "If there's no FAA citation for the 105 m
    precision strip, we can drop it as well."  SPECIFICATION VALUES
    ONLY — so neither ruleset carries a field, no accessor exists, and
    no provenance row makes the value look encodable.

    Asserted as ABSENCE rather than as ``is None``: a None field is
    still a place for a reversed value to creep back into."""
    fields = set(CFG.Ruleset.__dataclass_fields__)
    for name in ("strip_precision_half_width_m",
                 "strip_precision_taper_to_m",
                 "strip_precision_taper_length_m"):
        assert name not in fields, name
        assert CFG.reg_entry(name, "icao") is None, name
        assert CFG.reg_entry(name, "faa") is None, name
    assert not hasattr(CFG, "ruleset_strip_precision_half_width_m")
    assert not hasattr(CFG, "ruleset_strip_precision_taper")
    assert not any("precision" in e.field for e in CFG.REG_SET_ENTRIES)


def test_G_the_strip_half_widths_stay_the_specification_values():
    """With the guidance adoption reversed, a precision-approach runway
    grades to the same specified half-width as any other: 75 m at ICAO
    code 3/4 (§3.4.8-3.4.9), 76.2 m at FAA C/D/E (App. G, 500 ft).  The
    reg-set arithmetic that motivated the reversal, asserted: 105 m
    would have exceeded the FAA RSA half-width by 28.8 m with no FAA
    clause behind it."""
    assert CFG.ruleset_strip_half_width_m(4, "E", "icao") == 75.0
    assert CFG.ruleset_strip_half_width_m(4, "E", "faa") == 76.2
    assert 105.0 - CFG.faa_rsa_half_width_m("C/D/E", "V") == \
        pytest.approx(28.8)


def test_G_no_entry_currently_exceeds_its_citation():
    """The two owner-adoption labels survive in the vocabulary so a
    future adoption can be FLAGGED, but after the reversal this reg set
    contains no value that goes past its source — the only owner-sourced
    number left is ruling 2's house constant, labelled as one."""
    assert {"owner-adopted (guidance)",
            "owner-adopted-beyond-citation"} <= CFG.REG_AUTHORITY_CLASSES
    used = {e.authority_class for e in CFG.REG_SET_ENTRIES}
    assert "owner-adopted (guidance)" not in used
    assert "owner-adopted-beyond-citation" not in used
    assert "house constant (PROVISIONAL)" in used


# ══════════════════════════════════════════════════════════════════════
# H — the ICAO graded-strip mandatory-DOWN drop (reg-set ruling 1)
# ══════════════════════════════════════════════════════════════════════

def test_H_the_faa_keeps_its_own_Standard():
    """Table 3-6 row S-3: RSA side slope 1.5-5.0 % (AAC-A/B) and
    1.5-3.0 % (AAC-C/D/E) — a real MINIMUM of 1.5 %.  KCLT keeps the
    FAA form."""
    assert CFG.ruleset_strip_band_mandatory_down("faa") is True
    assert CFG.ruleset_strip_band_authority_min_down_slope("faa") == 0.015
    assert CFG.get_ruleset("faa").strip_band_drop_provisional is False


def test_H_the_icao_side_DROPS_it_flagged_PROVISIONAL():
    """F-2: the 1.5 % transverse MINIMUM is FAA-only.  ICAO §3.4.15 and
    CS ADR-DSN.B.185 state no minimum — only "adequate to prevent the
    accumulation of water", a ceiling, and the 3 m negative lip.  Ruling
    1 drops the blend on the ICAO ruleset and flags it PROVISIONAL: the
    owner revisits at the sim look at a strip without the band."""
    assert CFG.ruleset_strip_band_mandatory_down("icao") is False
    assert CFG.ruleset_strip_band_authority_min_down_slope("icao") is None
    assert CFG.get_ruleset("icao").strip_band_drop_provisional is True
    # the CEILING is untouched — dropping a floor is not dropping a law
    assert CFG.ruleset_strip_band_max_down_slope(4, "icao") == 0.03
    assert CFG.ruleset_strip_band_max_down_slope(1, "icao") == 0.05


def test_H_the_icao_instrument_strip_key_is_encoded():
    """F-1: ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` is the NON-instrument
    table (§3.4.9).  For an INSTRUMENT runway §3.4.8 / CS
    ADR-DSN.B.175(a) give 40 m at code 1, not 30 m."""
    assert CFG.ruleset_strip_half_width_m_instrument(1, "icao") == 40.0
    assert CFG.ruleset_strip_half_width_m_instrument(2, "icao") == 40.0
    assert CFG.ruleset_strip_half_width_m_instrument(4, "icao") == 75.0
    # the live (non-instrument) table is unmoved
    assert CFG.ruleset_strip_half_width_m(1, "A", "icao") == 30.0
    # the FAA has no such split — it keys visibility instead
    assert CFG.ruleset_strip_half_width_m_instrument(1, "faa") is None


# ══════════════════════════════════════════════════════════════════════
# X1 — PROVENANCE: value · citation · authority class · PV date
# ══════════════════════════════════════════════════════════════════════

#: Every field W1 landed or re-labelled, and the ruleset it is claimed
#: under.  A field added to the reg set without a ``RegEntry`` fails
#: here, which is what stops a constant becoming folklore.
_W1_FIELDS = [
    ("faa", "FAA_RSA_WIDTH_FT_BY_RDC"),
    ("faa", "FAA_ROFA_WIDTH_FT_BY_RDC"),
    ("faa", "FAA_RSA_HALF_WIDTH_M_BY_LETTER"),
    ("faa", "FAA_RSA_LENGTH_BEYOND_END_FT_BY_RDC"),
    ("faa", "FAA_RSA_LENGTH_PRIOR_TO_THRESHOLD_FT_BY_RDC"),
    ("faa", "resa_length_datum"),
    ("icao", "resa_length_datum"),
    ("icao", "resa_length_min_m"),
    ("icao", "resa_length_recommended_m"),
    ("icao", "resa_length_recommended_m_instrument"),
    ("icao", "strip_beyond_end_m"),
    ("icao", "strip_beyond_end_m_instrument"),
    ("faa", "strip_lip_min_down_slope"),
    ("icao", "strip_lip_min_down_slope"),
    ("faa", "taxiway_lip_min_down_slope"),
    ("icao", "taxiway_lip_min_down_slope"),
    ("faa", "taxiway_lip_carved_out_of_band"),
    ("faa", "taxiway_shoulder_width_m_by_tdg"),
    ("faa", "taxiway_shoulder_width_m_tdg6_four_engine"),
    ("faa", "taxiway_shoulder_paved_from_adg"),
    ("icao", "taxiway_plus_shoulders_total_width_m"),
    ("faa", "tofa_back_slope_ratio"),
    ("icao", "tofa_back_slope_ratio"),
    ("faa", "taxi_transverse_min"),
    ("icao", "taxi_transverse_min"),
    ("faa", "taxi_crown_form_binding"),
    ("faa", "strip_band_min_down_slope_authority"),
    ("icao", "strip_band_min_down_slope_authority"),
    ("icao", "strip_half_width_m_instrument"),
    ("faa", "strip_half_width_m_instrument"),
]


@pytest.mark.parametrize("ruleset,field", _W1_FIELDS)
def test_X1_every_W1_entry_carries_its_provenance(ruleset, field):
    entry = CFG.reg_entry(field, ruleset)
    assert entry is not None, f"{ruleset}:{field} has no RegEntry"
    assert entry.value.strip(), field
    assert entry.citation.strip(), field
    assert entry.authority_class in CFG.REG_AUTHORITY_CLASSES, field
    assert entry.pv_date == "2026-08-08", field


def test_X1_the_authority_class_vocabulary_is_closed():
    """An unrecognised class raises at construction rather than reading
    as a citation."""
    with pytest.raises(ValueError):
        CFG.RegEntry(field="x", ruleset="faa", value="v",
                     citation="c", authority_class="probably fine")
    with pytest.raises(ValueError):
        CFG.RegEntry(field="x", ruleset="tp312", value="v",
                     citation="c", authority_class="Standard")


def test_X1_every_ruleset_field_named_by_an_entry_actually_exists():
    """A provenance record pointing at a field that is not there is the
    F-11 failure mode in the repo's own registry."""
    fields = set(CFG.Ruleset.__dataclass_fields__)
    for entry in CFG.REG_SET_ENTRIES:
        if entry.field.isupper():
            assert hasattr(CFG, entry.field), entry.field
        else:
            assert entry.field in fields, entry.field


# ══════════════════════════════════════════════════════════════════════
# X2 — JURISDICTIONAL FIDELITY: never blend the two authorities
# ══════════════════════════════════════════════════════════════════════

def test_X2_faa_entries_cite_the_AC_and_icao_entries_cite_annex14():
    """Owner 2026-08-02: each ruleset carries its OWN authority's value,
    "take the stricter" is superseded.  A citation naming the other
    authority is the tell that a value was blended — except where the
    ruling itself is the source (ruling 2's house constant, Q5's
    owner adoption), which is exactly why those carry their own
    authority classes."""
    owner_adopted = {"house constant (PROVISIONAL)",
                     "owner-adopted (guidance)",
                     "owner-adopted-beyond-citation"}
    for entry in CFG.REG_SET_ENTRIES:
        if entry.authority_class in owner_adopted:
            assert "RULINGS" in entry.citation, entry.field
            continue
        if entry.ruleset == "faa":
            assert ("AC 150/5300-13B" in entry.citation
                    or "no FAA clause" in entry.citation), entry.field
            assert "Annex 14" not in entry.citation, entry.field
        elif entry.ruleset == "icao":
            assert ("Annex 14" in entry.citation
                    or "CS ADR-DSN" in entry.citation), entry.field
            assert "AC 150/5300-13B" not in entry.citation, entry.field


def test_X2_an_absent_family_is_None_not_the_other_authority_value():
    """Where a family exists in only one authority the other's field is
    ``None`` and the law is a no-op there — never a borrowed number."""
    assert CFG.ruleset_tofa_back_slope_ratio("icao") is None
    assert CFG.ruleset_taxiway_edge_lip("icao") == (None, None, None)
    assert CFG.ruleset_taxiway_shoulder_width_m("3", "icao") is None
    assert CFG.ruleset_strip_band_authority_min_down_slope("icao") is None
    assert CFG.ruleset_resa_length_m(4, "faa") is None
    assert CFG.ruleset_strip_beyond_end_m(4, "faa") is None
    assert CFG.ruleset_strip_half_width_m_instrument(1, "faa") is None
    assert CFG.ruleset_taxiway_plus_shoulders_total_width_m("D", "faa") is None


@pytest.mark.parametrize("key", _RULESETS)
def test_X2_every_new_family_resolves_for_every_ruleset(key):
    """The registry's own discipline: a family added to :class:`Ruleset`
    that cannot answer for a real aerodrome class fails HERE rather than
    at an airport."""
    accessors = (
        lambda r: CFG.ruleset_strip_band_mandatory_down(r),
        lambda r: CFG.ruleset_strip_band_authority_min_down_slope(r),
        lambda r: CFG.ruleset_runway_edge_lip(r),
        lambda r: CFG.ruleset_taxiway_edge_lip(r),
        lambda r: CFG.ruleset_taxiway_lip_carved_out_of_band(r),
        lambda r: CFG.ruleset_tofa_back_slope_ratio(r),
        lambda r: CFG.ruleset_taxi_transverse_min_provisional(r),
        lambda r: CFG.ruleset_taxi_crown_form_binding(r),
        lambda r: CFG.ruleset_taxiway_shoulder_paved_from_adg(r),
        lambda r: CFG.ruleset_resa_length_datum(r),
        lambda r: CFG.ruleset_resa_length_m(4, r),
        lambda r: CFG.ruleset_strip_beyond_end_m(4, r),
        lambda r: CFG.ruleset_strip_half_width_m_instrument(1, r),
        lambda r: CFG.ruleset_taxiway_shoulder_width_m("3", r),
        lambda r: CFG.ruleset_taxiway_plus_shoulders_total_width_m("D", r),
    )
    for fn in accessors:
        fn(key)          # must not raise
        assert fn(key) == fn(CFG.get_ruleset(key)), "key and record agree"


def test_X2_the_registry_stays_open_ended():
    """Adding an authority is still adding a ``Ruleset(...)`` — every new
    field has a default, so a third ruleset does not have to know about
    the fabric round to be constructible."""
    fields = CFG.Ruleset.__dataclass_fields__
    for name in ("tofa_back_slope_ratio", "taxiway_lip_width_m",
                 "resa_length_datum",
                 "strip_band_min_down_slope_authority"):
        f = fields[name]
        assert (f.default is not dataclasses.MISSING
                or f.default_factory is not dataclasses.MISSING), name


# ══════════════════════════════════════════════════════════════════════
# X3 — NO EMITTER BEHAVIOUR CHANGE (W1 is constants only)
# ══════════════════════════════════════════════════════════════════════

def test_X3_every_live_consumed_constant_is_pinned_to_its_pre_W1_value():
    """W1 lands the authority-true numbers; W2 owns switching consumers.
    These are the fields ``grade_law.adjacent_ground_envelope`` reads
    TODAY, pinned as literals — if one moves, geometry moved with it and
    that is a STOP, not a landing."""
    for key in _RULESETS:
        rs = CFG.get_ruleset(key)
        assert rs.strip_lip_width_m == 3.0
        assert rs.strip_lip_min_down_slope == 0.03
        assert rs.strip_lip_max_down_slope == 0.05
        assert rs.strip_band_min_down_slope == 0.015
        assert rs.taxiway_strip_band_min_down_slope == 0.015
        assert rs.taxiway_strip_band_max_down_slope == 0.05
        assert rs.ungraded_strip_max_up_slope == 0.05
    assert CFG.ruleset_strip_half_width_m(4, "E", "faa") == 76.2
    assert CFG.ruleset_strip_half_width_m(4, "E", "icao") == 75.0
    assert CFG.RUNWAY_END_CLEARANCE_LENGTH_BY_CODE == {
        1: 60.0, 2: 90.0, 3: 150.0, 4: 240.0}


@pytest.fixture
def w2_flags_off(monkeypatch):
    """Every W2 flag that can reach ``adjacent_ground_envelope``, OFF."""
    for env in ("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY",
                "O4_FABRIC_W2_RETIRE_APRON_SURROUND",
                "O4_FABRIC_W2_RETIRE_SERVICE_SHADOW"):
        monkeypatch.setenv(env, "0")
    return None


def test_X3_the_adjacent_ground_envelope_is_bit_for_bit_what_it_was(
        w2_flags_off):
    """SUCCESSOR to the W1 pin (retired with the W2 flips, same commit).

    The pin's job was "W1 moved no geometry"; W2 moves geometry ON
    PURPOSE, so the same numbers now certify the OFF ARM — with every W2
    flag disabled the function is bit-for-bit the pre-W2 corridor.  That
    is the per-flag identity proof the batch plan requires, at the one
    function every W1 constant could have reached.  Spot values across
    all three zones and both branches, under both rulesets, as plain
    numbers — no derivation the change could also have moved."""
    # runway branch, ICAO code 4: lip (0-3 m), band, then ungraded
    assert GL.adjacent_ground_envelope("runway", 4, "E", 1.0, "icao") == \
        pytest.approx((-0.05, -0.03))
    assert GL.adjacent_ground_envelope("runway", 4, "E", 10.0, "icao") == \
        pytest.approx((-0.36, -0.195))
    # taxiway branch, code letter C, inside the lip and inside the band
    assert GL.adjacent_ground_envelope("taxiway", None, "C", 1.0, "icao") == \
        pytest.approx((-0.05, -0.03))
    assert GL.adjacent_ground_envelope("taxiway", None, "C", 6.0, "icao") == \
        pytest.approx((-0.30, -0.135))
    # and the FAA arm, which the lip correction would have moved first
    assert GL.adjacent_ground_envelope("taxiway", None, "C", 1.0, "faa") == \
        pytest.approx((-0.05, -0.03))
    # the two families W2 retires outright, pre-W2: the apron's 3 m
    # 1-3 % shoulder and the service road's flat 15 m cut shadow
    assert GL.adjacent_ground_envelope("apron", None, None, 1.0, "faa") == \
        pytest.approx((-0.03, -0.01))
    assert GL.adjacent_ground_envelope(
        "service_road", None, None, 6.0, "faa") == (None, 0.0)


def test_X3_the_W2_flip_list_is_exactly_the_divergences():
    """SUCCESSOR to the pending-flip pin (retired with the flips).

    The pin asserted the divergence and that no flip had landed.  All
    three landed in W2, so what has to stay true now is: the two halves
    still DISAGREE (a live constant quietly edited to match would move
    the flag-OFF arm, which is emitted geometry and a STOP), and each
    row names a REGISTERED flag that actually selects between them."""
    from auto_patch import fabric_flags as FF
    assert not hasattr(CFG, "RULESET_W2_PENDING_FLIPS"), (
        "the pending-flip checklist retired into RULESET_W2_FLIPS")
    assert len(CFG.RULESET_W2_FLIPS) == 3
    for family, live_field, authority_field, key, flag in \
            CFG.RULESET_W2_FLIPS:
        rs = CFG.get_ruleset(key)
        assert hasattr(rs, live_field), live_field
        assert hasattr(rs, authority_field), authority_field
        assert getattr(rs, live_field) != getattr(rs, authority_field), (
            f"{family}: {key}.{live_field} now equals {authority_field} — "
            f"a live constant moved, and that is emitted geometry on the "
            f"flag-OFF arm, i.e. a STOP")
        assert flag in FF.FLAG_INDEX, (
            f"{family}: {flag} is not a registered Phase-B flag")
        assert FF.FLAG_INDEX[flag].default == "1"


def test_X3_each_flip_selects_the_authority_value_on_and_the_blend_off(
        monkeypatch):
    """The flips are LIVE: the consumer reads each authority's own
    mandate by default, and the pre-W2 blend with the flag off."""
    icao = CFG.get_ruleset("icao")
    faa = CFG.get_ruleset("faa")
    # ruling 1 — ICAO mandates no fall across the graded strip, so its
    # band ceiling stops descending past the lip; the FAA form does not
    # move (KCLT), which is the whole point of a per-authority flip.
    monkeypatch.delenv("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", raising=False)
    assert GL._w2_strip_band_min_down(icao) is None
    assert GL._w2_strip_band_min_down(faa) == faa.strip_band_min_down_slope
    assert GL.adjacent_ground_envelope("runway", 4, "E", 60.0, "icao")[1] == \
        pytest.approx(-0.09)
    monkeypatch.setenv("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", "0")
    assert GL._w2_strip_band_min_down(icao) == icao.strip_band_min_down_slope
    assert GL.adjacent_ground_envelope("runway", 4, "E", 60.0, "icao")[1] == \
        pytest.approx(-0.945)
    # F-10 — the FAA taxiway/apron edge lip is 4.5-5.5 %, not the
    # runway's 3-5 %; ICAO states no taxiway lip at all, so its near
    # zone is ZERO wide and the band starts at the edge.
    monkeypatch.delenv("O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY", raising=False)
    assert GL._w2_paved_edge_lip(faa) == (3.0, 0.045, 0.055)
    assert GL._w2_paved_edge_lip(icao) == (0.0, 0.0, 0.0)
    assert GL.adjacent_ground_envelope("taxiway", None, "C", 1.0, "faa") == \
        pytest.approx((-0.055, -0.045))
    monkeypatch.setenv("O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY", "0")
    assert GL._w2_paved_edge_lip(faa) == (3.0, 0.03, 0.05)
    assert GL.adjacent_ground_envelope("taxiway", None, "C", 1.0, "faa") == \
        pytest.approx((-0.05, -0.03))


def test_X3_the_reg_set_added_no_new_region_invariant_constant():
    """Owner constants and engineering-judgment values stay OUT of the
    registry (the phase-B spec's §7 rule), so W1 cannot have absorbed
    one by accident."""
    fields = set(CFG.Ruleset.__dataclass_fields__)
    for name in ("APRON_MAX_GRADE", "GROUNDSIDE_MAX_GRADE",
                 "SERVICE_ROAD_MAX_GRADE", "APRON_SHOULDER_WIDTH_M",
                 "ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT"):
        assert hasattr(CFG, name), name
        assert name.lower() not in fields, name
