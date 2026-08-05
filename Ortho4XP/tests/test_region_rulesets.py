"""Region rulesets, phase B — the FAA/ICAO split.

Spec: ``docs/specs/DRAFT-rulesets-phase-b-spec.md``.  Owner ruling:
``docs/RULINGS.md`` "Region-specific rulesets" (2026-08-02) — "FAA applies
within the USA, and ICAO everywhere else … support region specific
regulations and provide the code structure to allow the possibility to
choose and/or support multiple rulesets in the future".

Three twin families, per spec §3:
  1. the RESOLVER table (which airport gets which authority);
  2. the SIDECAR round-trip (the validator judges in the BUILD's frame);
  3. LOCKSTEP (emitter and validator accessors return identical
     constants for both keys, across every split family).

Plus per-row value twins for the §4 table: each number is asserted
against its PRIMARY citation, so a silent edit to a regulation constant
fails here rather than at an airport.
"""
import os

import pytest

from auto_patch import config as CFG
from auto_patch import grade_law as GL


# ── §3 twin 1 — the resolver table ───────────────────────────────────

@pytest.mark.parametrize("icao,expected", [
    # the contiguous USA
    ("KCLT", "faa"), ("KATL", "faa"), ("KSFO", "faa"),
    # FAA-jurisdiction territories (spec §2)
    ("PANC", "faa"),        # Alaska
    ("PHNL", "faa"),        # Hawaii
    ("PGUM", "faa"),        # Guam
    ("PMDY", "faa"),        # Midway
    ("PWAK", "faa"),        # Wake
    # everywhere else — the owner's own default
    ("HECA", "icao"), ("HEAZ", "icao"),
    ("SPJC", "icao"), ("SPLP", "icao"),
    ("CYXY", "icao"),       # Canada is ICAO under "within the USA"
    ("MMMX", "icao"),       # Mexico likewise
    ("PKMJ", "icao"),       # Marshall Islands: a P… that is NOT US
    ("EGLL", "icao"), ("LFPG", "icao"),
    # unparseable / missing identifiers fail SAFE to the owner's default
    ("", "icao"), (None, "icao"), ("  ", "icao"),
])
def test_resolver_table(icao, expected, monkeypatch):
    monkeypatch.delenv("O4_RULESET", raising=False)
    assert CFG.resolve_ruleset(icao) == expected


def test_resolver_is_case_insensitive(monkeypatch):
    monkeypatch.delenv("O4_RULESET", raising=False)
    assert CFG.resolve_ruleset("kclt") == "faa"
    assert CFG.resolve_ruleset("panc") == "faa"


def test_eat_prefixes_are_a_different_ruling(monkeypatch):
    """The EAT departure surface keys on {K, C, P, M} ("FAA for North
    America", an EARLIER and differently-scoped owner ruling).  Phase B
    must NOT reuse it: Canada and Mexico are ICAO for grade law.  The two
    resolvers coexist; harmonizing them is an owner question."""
    monkeypatch.delenv("O4_RULESET", raising=False)
    assert "C" in CFG.EAT_FAA_ICAO_PREFIXES
    assert "M" in CFG.EAT_FAA_ICAO_PREFIXES
    assert CFG.resolve_ruleset("CYXY") == "icao"
    assert CFG.resolve_ruleset("MMMX") == "icao"


def test_env_override_is_a_testing_knob_not_a_law_gate(monkeypatch):
    monkeypatch.setenv("O4_RULESET", "faa")
    assert CFG.resolve_ruleset("HECA") == "faa"
    monkeypatch.setenv("O4_RULESET", "icao")
    assert CFG.resolve_ruleset("KCLT") == "icao"
    monkeypatch.setenv("O4_RULESET", "")
    assert CFG.resolve_ruleset("KCLT") == "faa"


def test_unknown_ruleset_raises_never_falls_back(monkeypatch):
    """A law must never silently pick another authority's numbers."""
    monkeypatch.setenv("O4_RULESET", "tp312")
    with pytest.raises(ValueError):
        CFG.resolve_ruleset("CYXY")
    monkeypatch.delenv("O4_RULESET", raising=False)
    with pytest.raises(ValueError):
        CFG.get_ruleset("casa")


def test_registry_is_open_ended():
    """Adding an authority is adding a ``Ruleset(...)`` to the registry —
    no structural change, no new branch at a law site (the owner's
    "multiple rulesets in the future" clause)."""
    assert set(CFG.RULESETS) == {"faa", "icao"}
    for key, rs in CFG.RULESETS.items():
        assert isinstance(rs, CFG.Ruleset)
        assert rs.key == key


# ── §3 twin 2 — the sidecar round-trip ───────────────────────────────

def test_sidecar_carries_the_ruleset_key():
    """``layout._write_axes_sidecar`` writes the key the BUILD ran under,
    and ``check_grade`` consumes it instead of re-resolving from the ICAO
    identifier (the two-instruments law applied to authority).

    Source-inspection twin (the ref-pull precedent): reaching the write
    site needs a full build, which this suite does not run."""
    import inspect
    from auto_patch import layout as LAY
    src = inspect.getsource(LAY.PavementLayout._write_axes_sidecar)
    assert '"ruleset": _grade_law_ruleset_of(self)' in src

    check = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(LAY.__file__))), "..", "tools", "check_grade.py")
    with open(os.path.normpath(check)) as fh:
        text = fh.read()
    assert 'ruleset_key = _data.get("ruleset")' in text
    assert "ruleset=ruleset_key," in text
    assert "_set_active_ruleset(ruleset)" in text


def test_ruleset_of_prefers_the_carried_key_over_re_resolution():
    class _Layout:
        icao = "HECA"
        ruleset = "faa"        # what the build actually ran under

    assert GL.ruleset_of(_Layout()) == "faa"

    class _NoKey:
        icao = "HECA"

    assert GL.ruleset_of(_NoKey()) == "icao"
    assert GL.ruleset_of("KCLT") == "faa"
    assert GL.ruleset_of(None) == CFG.DEFAULT_RULESET


# ── §3 twin 3 — lockstep across every split family ───────────────────

@pytest.mark.parametrize("family,_keying", CFG.RULESET_SPLIT_FAMILIES)
@pytest.mark.parametrize("key", ["faa", "icao"])
def test_every_split_family_resolves_for_every_ruleset(family, _keying, key):
    """A family added to :class:`Ruleset` without a populated table — or
    a table that resolves to nothing for a real aerodrome class — fails
    HERE rather than at an airport."""
    rs = CFG.get_ruleset(key)
    table = getattr(rs, family)
    if table is None:
        # NA-F / NA-I: the family genuinely does not exist in this
        # authority (ICAO has no RESA near-zone column).  Legitimate.
        return
    assert isinstance(table, CFG.CodeTable)
    for code, letter in ((4, "E"), (3, "C"), (2, "B"), (1, "A")):
        table.value(code, letter)      # must not raise


@pytest.mark.parametrize("key", ["faa", "icao"])
def test_emitter_and_validator_read_one_accessor(key):
    """The emitter's call and the validator's call are the SAME function
    with the same arguments, so they cannot return different numbers."""
    for code, letter in ((4, "E"), (3, "C"), (1, "A")):
        assert (CFG.ruleset_runway_max_grade(code, letter, key)
                == CFG.ruleset_runway_max_grade(code, letter, key))
        assert (GL.runway_strip_max_longitudinal_slope(code, key, letter)
                == CFG.ruleset_strip_max_longitudinal_slope(code, letter, key))


# ── §4 the per-authority value table, against its citations ──────────

def test_row1_runway_longitudinal_maximum():
    """ICAO Annex 14 §3.1.14: 1.25 % (code 4), 1.5 % (code 3), 2 %
    (code 1-2).  FAA AC 150/5300-13B §3.16.1: 2.0 % (AAC A/B), 1.50 %
    (AAC C/D/E)."""
    assert CFG.ruleset_runway_max_grade(4, "E", "icao") == pytest.approx(0.0125)
    assert CFG.ruleset_runway_max_grade(3, "C", "icao") == pytest.approx(0.015)
    assert CFG.ruleset_runway_max_grade(2, "B", "icao") == pytest.approx(0.020)
    assert CFG.ruleset_runway_max_grade(4, "E", "faa") == pytest.approx(0.015)
    assert CFG.ruleset_runway_max_grade(2, "B", "faa") == pytest.approx(0.020)
    # The predicted phase-B surface change: ICAO code-4 runways TIGHTEN.
    assert (CFG.ruleset_runway_max_grade(4, "E", "icao")
            < CFG.ruleset_runway_max_grade(4, "E", "faa"))


def test_row2_end_zone_cap_and_its_applicability():
    """ICAO §3.1.14 applies 0.8 % at code 4 unconditionally, at code 3
    ONLY for precision Cat II/III, and NOT AT ALL at code 1-2.  FAA
    §3.16.1.2 applies it to AAC C/D/E within the lesser of the quarter
    and 2,500 ft (762 m)."""
    assert CFG.ruleset_runway_end_grade(4, "E", "precision", "icao") == 0.008
    assert CFG.ruleset_runway_end_grade(4, "E", "visual", "icao") == 0.008
    assert CFG.ruleset_runway_end_grade(3, "C", "precision", "icao") == 0.008
    assert CFG.ruleset_runway_end_grade(3, "C", "visual", "icao") is None
    assert CFG.ruleset_runway_end_grade(2, "B", "precision", "icao") is None
    # Missing data must never buy the PERMISSIVE reading.
    assert CFG.ruleset_runway_end_grade(3, "C", None, "icao") == 0.008
    assert CFG.ruleset_runway_end_grade(4, "E", None, "faa") == 0.008
    assert CFG.ruleset_runway_end_grade(4, "B", None, "faa") is None


def test_row2_end_zone_length():
    """FAA takes the LESSER of the quarter and 762 m; ICAO the quarter."""
    assert CFG.ruleset_runway_end_zone_length_m(2800.0, "icao") == 700.0
    assert CFG.ruleset_runway_end_zone_length_m(2800.0, "faa") == 700.0
    # A long runway is where the two diverge (KCLT-class and above).
    assert CFG.ruleset_runway_end_zone_length_m(4000.0, "icao") == 1000.0
    assert CFG.ruleset_runway_end_zone_length_m(4000.0, "faa") == 762.0


def test_row3_max_grade_change():
    """ICAO §3.1.15: 1.5 % (code 3-4), 2 % (code 1-2).  FAA §3.16.1:
    ±2.0 % (A/B), ±1.50 % (C/D/E)."""
    assert CFG.ruleset_runway_max_grade_change(4, "E", "icao") == 0.015
    assert CFG.ruleset_runway_max_grade_change(1, "A", "icao") == 0.020
    assert CFG.ruleset_runway_max_grade_change(4, "E", "faa") == 0.015
    assert CFG.ruleset_runway_max_grade_change(4, "A", "faa") == 0.020


def test_row4_vertical_curve():
    """ICAO §3.1.16 as metres of curve per 1 %: 30/0.1 = 300 (code 4),
    30/0.2 = 150 (code 3), 30/0.4 = 75 (code 1-2).  FAA §3.16.1:
    1,000 ft (305 m) per 1 % for C/D/E, 300 ft (91 m) for A/B."""
    assert CFG.ruleset_runway_vertical_curve_k_m(4, "E", "icao") == 300.0
    assert CFG.ruleset_runway_vertical_curve_k_m(3, "C", "icao") == 150.0
    assert CFG.ruleset_runway_vertical_curve_k_m(4, "E", "faa") == 305.0
    assert CFG.ruleset_runway_vertical_curve_k_m(4, "A", "faa") == 91.4
    # The live blended rate IS ICAO code 4 — 0.1 % per 30 m = 1/30000.
    assert (CFG.ruleset_runway_max_grade_change_per_m(4, "E", "icao")
            == pytest.approx(CFG.RUNWAY_MAX_GRADE_CHANGE_PER_M))
    # The FAA "no curve below 0.40 %" relief is stated for A/B ONLY
    # (§3.16.1.1); C/D/E get the stricter contained reading.
    assert CFG.ruleset_runway_vertical_curve_min_change(1, "A", "faa") == 0.004
    assert CFG.ruleset_runway_vertical_curve_min_change(4, "E", "faa") is None
    assert CFG.ruleset_runway_vertical_curve_min_change(4, "E", "icao") is None


def test_row5_strip_longitudinal():
    """ICAO §3.4.13: 1.5 / 1.75 / 2 %.  FAA §3.16.5 item 1: the runway's
    own cap.  The two AGREE at code 4 / AAC C-E, which is why the FAA
    fixture exercises the same number."""
    assert CFG.ruleset_strip_max_longitudinal_slope(4, "E", "icao") == 0.015
    assert CFG.ruleset_strip_max_longitudinal_slope(3, "C", "icao") == 0.0175
    assert CFG.ruleset_strip_max_longitudinal_slope(4, "E", "faa") == 0.015
    # SPLIT at code 3: FAA 1.5 % against ICAO 1.75 %.
    assert (CFG.ruleset_strip_max_longitudinal_slope(3, "C", "faa")
            < CFG.ruleset_strip_max_longitudinal_slope(3, "C", "icao"))


def test_row6_strip_half_width():
    """ICAO {1:30, 2:40, 3:75, 4:75}.  FAA Appendix G: RSA width 500 ft
    (152.4 m) for every C/D/E row ⇒ 76.2 m half-width — the ~1.2 m
    widening the spec predicted at KCLT."""
    assert CFG.ruleset_strip_half_width_m(4, "E", "icao") == 75.0
    assert CFG.ruleset_strip_half_width_m(1, "A", "icao") == 30.0
    assert CFG.ruleset_strip_half_width_m(4, "E", "faa") == 76.2
    assert (CFG.ruleset_strip_half_width_m(4, "E", "faa")
            - CFG.ruleset_strip_half_width_m(4, "E", "icao")
            == pytest.approx(1.2))


def test_rows_7_8_are_DEFERRED_by_owner_question_1():
    """The 2026-07-08 mandatory-DOWN ruling was premised on ONE blended
    ruleset.  Until the owner answers, BOTH rulesets keep the blended
    values — the deferral is visible law, not drift."""
    for key in ("faa", "icao"):
        rs = CFG.get_ruleset(key)
        assert rs.strip_lip_width_m == CFG.ADJACENT_GROUND_LIP_WIDTH_M
        assert rs.strip_lip_min_down_slope == \
            CFG.ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE
        assert rs.strip_band_min_down_slope == \
            CFG.RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE
        assert CFG.ruleset_strip_band_max_down_slope(4, key) == 0.03


def test_rows_13_14_taxiway():
    """ICAO §3.9.8 / §3.9.11 relax A/B to 3 % / 2 %; FAA §4.14.1.1.1 and
    §4.14.2 item 1a give 1.5 % for every letter (its ≤30,000 lb
    relaxation is NOT taken — the builder does not know a taxiway's
    fleet)."""
    assert CFG.ruleset_taxi_max_grade("B", "icao") == 0.030
    assert CFG.ruleset_taxi_max_grade("D", "icao") == 0.015
    assert CFG.ruleset_taxi_max_grade("B", "faa") == 0.015
    assert CFG.ruleset_taxi_transverse_max("B", "icao") == 0.020
    assert CFG.ruleset_taxi_transverse_max("B", "faa") == 0.015
    # and the legacy accessors honour the split without breaking callers
    assert CFG.taxi_grade_cap_for_letter("B") == 0.030          # blended
    assert CFG.taxi_grade_cap_for_letter("B", ruleset="faa") == 0.015
    assert CFG.taxi_transverse_cap_for_letter("B", ruleset="faa") == 0.015


def test_row15_16_stand_and_apron():
    """ICAO §3.13.6 and FAA §5.9.2.1.1 both cap a stand at 1 %.  The
    apron MINIMUM exists only in the FAA text (§5.9.1.1); ICAO §3.13.5 is
    qualitative, so a numeric ICAO minimum would be MINTED, not cited."""
    assert CFG.ruleset_stand_max_grade("icao") == 0.01
    assert CFG.ruleset_stand_max_grade("faa") == 0.01
    assert CFG.ruleset_apron_min_drainage_grade("faa") == 0.005
    assert CFG.ruleset_apron_min_drainage_grade("icao") is None
    assert CFG.ruleset_apron_max_grade_change("faa") == 0.02
    assert CFG.ruleset_apron_max_grade_change("icao") is None


def test_row18_shoulders():
    """FAA Table 3-6 S-2: paved shoulders 1.5-5.0 % (a mandatory DOWN
    band) plus a MANDATED 38 ± 13 mm paved→unpaved drop-off (§4.14.2
    item 2).  ICAO §3.2.3: flush, transverse ≤2.5 %, no drop-off."""
    assert CFG.ruleset_shoulder_transverse_band("faa") == (0.015, 0.05)
    assert CFG.ruleset_shoulder_transverse_band("icao") == (None, 0.025)
    assert CFG.ruleset_shoulder_edge_dropoff("faa") == (0.038, 0.013)
    assert CFG.ruleset_shoulder_edge_dropoff("icao") == (None, None)


def test_row19_raoa_is_icao_only():
    """Annex 14 §3.8 / CS ADR-DSN.B.205.  The string "radio altimeter"
    does not occur in AC 150/5300-13B (verified), so the FAA column is
    None and KCLT is untouched — jurisdictional fidelity."""
    icao = CFG.get_ruleset("icao")
    assert icao.raoa_length_m == 300.0
    assert icao.raoa_half_width_m == 60.0
    assert icao.raoa_max_grade_change_per_m == pytest.approx(0.02 / 30.0)
    faa = CFG.get_ruleset("faa")
    assert faa.raoa_length_m is None
    assert faa.raoa_max_grade_change_per_m is None


def test_region_invariant_constants_stay_out_of_the_registry():
    """Owner constants and engineering-judgment values are NOT split
    (spec §7), so nothing is silently absorbed into an authority."""
    fields = set(CFG.Ruleset.__dataclass_fields__)
    for name in ("APRON_MAX_GRADE", "GROUNDSIDE_MAX_GRADE",
                 "SERVICE_ROAD_MAX_GRADE", "TUNNEL_RAMP_MAX_GRADE",
                 "ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT",
                 "WINGSPAN_BY_CODE_LETTER", "TERMINAL_PADS_SLOPE"):
        assert hasattr(CFG, name), name
        assert name.lower() not in fields, name
    # The apron MAXIMUM is the owner's 1 % (region-invariant); only the
    # apron MINIMUM and its grade-change rule are authority-split.
    assert "apron_max_grade" not in fields
    assert "apron_min_drainage_grade" in fields
    assert "apron_max_grade_change" in fields


def test_provisional_values_are_flagged_as_provisional():
    """A repo CHOICE must never read as a citation.  The ICAO strip/RESA
    arc rate (owner question 2) and the groundside drainage minimum
    (owner question 3) both carry their flag."""
    assert CFG.get_ruleset("icao").strip_arc_rate_provisional is True
    assert CFG.get_ruleset("faa").strip_arc_rate_provisional is False
    assert CFG.get_ruleset("icao").end_skirt_rate_provisional is True
    assert CFG.GROUNDSIDE_MIN_DRAINAGE_GRADE_PROVISIONAL is True
    assert CFG.GROUNDSIDE_MIN_DRAINAGE_GRADE == 0.010


def test_crown_minimum_is_recorded_but_not_bound():
    """Owner question 5: binding the 1 % transverse MINIMUM models a real
    crown on every runway and taxiway — a visible geometry change at
    every airport.  The values are CARRIED (so the validator can report)
    and asserted by no constraint until the owner rules."""
    assert CFG.CROWN_MINIMUM_BOUND is False
    assert CFG.get_ruleset("faa").runway_transverse_min == 0.010
    assert CFG.get_ruleset("icao").runway_transverse_min == 0.010
    assert CFG.get_ruleset("faa").taxi_transverse_min == 0.010
    # ICAO §3.9.11 states no taxiway minimum — fidelity, not an omission.
    assert CFG.get_ruleset("icao").taxi_transverse_min is None
    # unbound ⇒ the surface bound stays symmetric, no crown mandated
    lo, hi = GL.transverse_surface_bounds("taxiway", "C", 10.0, "faa")
    assert lo == pytest.approx(-0.15)
    assert hi == pytest.approx(0.15)


# ── the end-skirt constants now have ONE copy ────────────────────────

def test_end_skirt_constants_derive_from_the_faa_ruleset():
    """The values came from the FAA text, so they LIVE on the FAA
    ruleset; ``grade_law``'s historical names are that ruleset's view.
    Exactly one copy — an edit to either moves both."""
    assert GL.RUNWAY_END_SKIRT_NEAR_ZONE_M == 61.0
    assert GL.RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE == 0.03
    assert GL.RUNWAY_END_SKIRT_MAX_DOWN_GRADE == 0.05
    faa = CFG.get_ruleset("faa")
    assert GL.RUNWAY_END_SKIRT_NEAR_ZONE_M == faa.end_skirt_near_zone_m
    assert (GL.RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M
            == faa.end_skirt_max_grade_change_per_m)


def test_icao_skirt_has_no_near_zone():
    """Annex 14 §3.5.10 is a single ≤5 % down cap with no 61 m near
    zone, so an ICAO skirt descends FASTER near the end than an FAA
    one — jurisdictional fidelity, and the predicted row-10 delta."""
    near, near_max, max_down, rate = GL.runway_end_skirt_law("icao")
    assert near is None and near_max is None
    assert max_down == 0.05
    assert rate == pytest.approx(0.02 / 30.5)     # PROVISIONAL, flagged

    faa_depths = GL.runway_end_skirt_floor_profile([61.0, 240.0], 0.0, "faa")
    icao_depths = GL.runway_end_skirt_floor_profile([61.0, 240.0], 0.0, "icao")
    assert icao_depths[0] > faa_depths[0]
    assert icao_depths[1] > faa_depths[1]
    # …and both stay monotone and non-negative.
    assert 0.0 <= faa_depths[0] < faa_depths[1]


def test_runway_profile_law_is_one_resolver():
    law = GL.runway_profile_law(4, "E", "precision", 4000.0, "icao")
    assert law["max_grade"] == pytest.approx(0.0125)
    assert law["end_grade"] == pytest.approx(0.008)
    assert law["end_zone_m"] == pytest.approx(1000.0)
    assert law["max_grade_change_per_m"] == pytest.approx(1.0 / 30000.0)
    law = GL.runway_profile_law(4, "E", "precision", 4000.0, "faa")
    assert law["max_grade"] == pytest.approx(0.015)
    assert law["end_zone_m"] == pytest.approx(762.0)
    assert law["max_grade_change_per_m"] == pytest.approx(0.01 / 305.0)
