"""The remaining regulatory families — rounds A and B.

Spec: ``docs/specs/DRAFT-reg-families-round-spec.md``.

COMPLETENESS STANDARD (owner 2026-08-02, verbatim: "our grade law must
not allow us to generate an airport patch that violates any of the region
appropriate regulations"): every family needs BOTH a generation-binding
constraint AND its validator twin, reading ONE law function.  These tests
assert exactly that pairing per family:

  §A1  RESA / end-corridor transverse
  §A2  ROFA back slope (FAA-only)
  §A3a longitudinal-aware breach trigger
  §A3b strip vertical-curvature arc
  §A4  RAOA (ICAO-only)
  §B1  shoulder transverse + the mandated edge drop-off
  §B2  transverse solver binding
  §B3  drainage minimum

Plus the gate sweep: under build-complete-then-debug (docs/RULINGS.md
2026-08-05) every listed law gate is GONE and its law is standing.
"""
import inspect
import os

import pytest

from auto_patch import config as CFG
from auto_patch import grade_law as GL


_CHECK_GRADE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tools", "check_grade.py"))


def _check_grade_source() -> str:
    with open(_CHECK_GRADE) as fh:
        return fh.read()


# ══════════════════════════════════════════════════════════════════════
# §A1 — RESA / END-CORRIDOR TRANSVERSE
# ══════════════════════════════════════════════════════════════════════

def test_a1_constants_against_their_citations():
    """FAA AC §3.16.5 item 6 + Table 3-6 S-3: inside the first 200 ft
    (61 m) the RSA transverse takes 1.5-5.0 % (AAC A/B) and 1.5-3.0 %
    (AAC C/D/E); beyond it Figure 3-35's ±5.0 %.  ICAO Annex 14 §3.5.11:
    ±5 % throughout, no near-zone column and no mandated fall."""
    assert GL.resa_transverse_band(30.0, "E", "faa") == (0.015, 0.03)
    assert GL.resa_transverse_band(30.0, "A", "faa") == (0.015, 0.05)
    assert GL.resa_transverse_band(100.0, "E", "faa") == (None, 0.05)
    assert GL.resa_transverse_band(30.0, "E", "icao") == (None, 0.05)
    assert GL.resa_transverse_band(400.0, "E", "icao") == (None, 0.05)


def test_a1_envelope_is_mandatory_down_only_where_the_law_mandates():
    """Where a minimum fall is mandated (FAA near zone) a FLAT
    cross-section is OUTSIDE the corridor — the ceiling is strictly below
    zero.  Where none is (ICAO) the corridor is the symmetric ±cap."""
    floor, ceiling = GL.resa_transverse_envelope(30.0, 40.0, "E", "faa")
    assert ceiling < 0.0                      # flat is unlawful
    assert floor == pytest.approx(-0.03 * 40.0)
    assert ceiling == pytest.approx(-0.015 * 40.0)
    floor, ceiling = GL.resa_transverse_envelope(30.0, 40.0, "E", "icao")
    assert floor == pytest.approx(-0.05 * 40.0)
    assert ceiling == pytest.approx(0.05 * 40.0)
    # flush on the axis under every authority
    assert GL.resa_transverse_envelope(30.0, 0.0, "E", "faa") == (0.0, 0.0)


def test_a1_generation_binding_clamp():
    """IDENTITY ON LAWFUL GROUND, minimal move otherwise — the same two
    properties the landed longitudinal clamp documents."""
    offsets = [-40.0, -20.0, 0.0, 20.0, 40.0]
    axis_alt = 100.0
    lawful = [99.0, 99.5, 100.0, 99.5, 99.0]          # 2.5 % fall, ICAO-ok
    out = GL.resa_transverse_clamp(offsets, lawful, axis_alt, 100.0,
                                   "E", "icao")
    assert out == pytest.approx(lawful)

    unlawful = [93.0, 96.0, 100.0, 96.0, 93.0]        # 17.5 % — way over
    out = GL.resa_transverse_clamp(offsets, unlawful, axis_alt, 100.0,
                                   "E", "icao")
    for t, z in zip(offsets, out):
        floor, ceiling = GL.resa_transverse_envelope(100.0, t, "E", "icao")
        assert floor - 1e-9 <= z - axis_alt <= ceiling + 1e-9
    # and it moved the LEAST amount: each unlawful sample sits ON a bound
    assert out[0] == pytest.approx(axis_alt - 0.05 * 40.0)


def test_a1_validator_twin_exists_and_reads_the_law_function():
    src = _check_grade_source()
    assert "def _check_resa_transverse_grade(" in src
    assert "_resa_transverse_band(" in src
    assert "resa_transverse_band as _resa_transverse_band" in src
    assert "resa_tr, n_rt_pairs, n_rt_ways = _check_resa_transverse_grade(" \
        in src


# ══════════════════════════════════════════════════════════════════════
# §A2 — ROFA BACK SLOPE (FAA ruleset only)
# ══════════════════════════════════════════════════════════════════════

def test_a2_table_3_7_values():
    """S-5 run:rise by ADG — 8:1 (I-II), 10:1 (III-IV), 16:1 (V-VI) —
    and D-1's run in metres (25/40/59/86/107/131 ft)."""
    faa = CFG.get_ruleset("faa")
    assert faa.rofa_back_slope_ratio_by_adg["A"] == 8.0      # ADG I
    assert faa.rofa_back_slope_ratio_by_adg["C"] == 10.0     # ADG III
    assert faa.rofa_back_slope_ratio_by_adg["E"] == 16.0     # ADG V
    assert faa.rofa_back_slope_run_m_by_adg["E"] == pytest.approx(32.6)
    assert faa.rofa_back_slope_run_m_by_adg["A"] == pytest.approx(7.6)


def test_a2_side_slope_S4_is_NOT_bound_owner_exemption():
    """docs/RULINGS.md 2026-08-02: the FAA existing-runway exemption is
    APPROVED — Table 3-7 S-4 (side slope ≤0 %) does NOT bind.  This
    family owns the RISING side only, so no field carries S-4."""
    fields = set(CFG.Ruleset.__dataclass_fields__)
    assert not any("side_slope" in f for f in fields)
    assert "rofa_back_slope_ratio_by_adg" in fields


def test_a2_is_a_no_op_under_every_non_faa_ruleset():
    """ICAO has no ROFA; its analogue is §3.4.16's ≤5 %, already zone 3.
    Jurisdictional fidelity, not a silent skip."""
    assert GL.rofa_back_slope_ceiling("E", "icao") is None
    assert GL.rofa_back_slope_ceiling("E", "faa") is not None


def test_a2_back_slope_binds_through_the_adjacent_ground_envelope():
    """ONE law, emitter + validator both read it (the spec's own
    wording): the back slope replaces zone 3's flat ≤5 % rise inside the
    D-1 run and hands back to it beyond."""
    f = GL.rofa_back_slope_ceiling("E", "faa")
    assert f(0.0) == pytest.approx(0.0)
    # 16:1 ⇒ 6.25 % rise over the 32.6 m run
    assert f(32.6) == pytest.approx(32.6 / 16.0)
    # beyond D-1 the generic ≤5 % continues, CONTINUOUSLY
    assert f(42.6) == pytest.approx(32.6 / 16.0 + 0.05 * 10.0)
    # ADG I is the steepest permitted rise (8:1 = 12.5 %)
    g = GL.rofa_back_slope_ceiling("A", "faa")
    assert g(7.6) == pytest.approx(7.6 / 8.0)

    # …and the envelope actually consumes it: an FAA code-4 runway's
    # zone-3 ceiling differs from the ICAO one at the same distance.
    d = 120.0
    _, faa_ceiling = GL.adjacent_ground_envelope("runway", 4, "E", d, "faa")
    _, icao_ceiling = GL.adjacent_ground_envelope("runway", 4, "E", d, "icao")
    assert faa_ceiling != pytest.approx(icao_ceiling)


# ══════════════════════════════════════════════════════════════════════
# §A3(a) — the longitudinal-aware breach trigger
# ══════════════════════════════════════════════════════════════════════

def test_a3a_trigger_fires_on_a_longitudinal_breach():
    """The population the RSA round's reader saw: ground that conforms
    LATERALLY (so no band was emitted) while breaching LONGITUDINALLY."""
    s = [0.0, 30.0, 60.0, 90.0]
    z = [100.0, 100.3, 100.6, 100.9]        # exactly 1.0 % — lawful at 1.5 %
    assert GL.strip_longitudinal_breaches(s, z, 0.015) == []
    z = [100.0, 102.3, 104.6, 106.9]        # 7.6 % — the HEAZ worst class
    assert GL.strip_longitudinal_breaches(s, z, 0.015) == [1, 2, 3]


def test_a3a_trigger_is_blind_to_neither_axis():
    """A profile lawful on SLOPE but breaching the arc rate is still a
    breach — that is the whole point of the completeness half."""
    # A REVERSAL at ±1.33 %: every pair is inside the 1.5 % slope cap,
    # but the grade CHANGE across the middle station is 2.67 pp over
    # 30 m against the arc law's 1.97 pp.
    s = [0.0, 30.0, 60.0]
    z = [100.0, 99.6, 100.0]
    assert GL.strip_longitudinal_breaches(s, z, 0.015) == []
    rate = 0.02 / 30.5
    assert GL.strip_longitudinal_breaches(s, z, 0.015, rate) == [1]


def test_a3a_missing_readings_never_fabricate_a_breach():
    s = [0.0, 30.0, 60.0]
    assert GL.strip_longitudinal_breaches(s, [100.0, None, 108.0], 0.015) == []


def test_a3a_population_caveat_is_recorded_in_the_law():
    """The 146-row HEAZ measurement was taken at 5eaf1e2 and a later flip
    adjudication FALSIFIED its reproduction at the current base.  The
    mechanism ships as designed; the population is a debugging question
    and must not be quoted as an effect size."""
    doc = GL.strip_longitudinal_breaches.__doc__ or ""
    assert "FALSIFIED" in doc
    assert "146" in doc


# ══════════════════════════════════════════════════════════════════════
# §A3(b) — the strip vertical-curvature arc
# ══════════════════════════════════════════════════════════════════════

def test_a3b_rate_constants_and_the_provisional_flag():
    """FAA AC §3.16.5 item 5 gives ±2 % per 100 ft (30.5 m) — CITED.
    ICAO §3.4.14 gives no number, so the ICAO rate is a repo CHOICE and
    says so (owner question 2)."""
    assert CFG.ruleset_strip_arc_rate_per_m("faa") == pytest.approx(0.02 / 30.5)
    assert CFG.get_ruleset("faa").strip_arc_rate_provisional is False
    assert CFG.ruleset_strip_arc_rate_per_m("icao") == pytest.approx(0.02 / 30.5)
    assert CFG.get_ruleset("icao").strip_arc_rate_provisional is True


def test_a3b_clamp_is_identity_on_an_already_smooth_run():
    pts = [(float(i) * 30.0, 0.0) for i in range(6)]
    alts = [100.0 + 0.01 * p[0] for p in pts]        # a constant 1 % ramp
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015,
        arc_rate_per_m=CFG.ruleset_strip_arc_rate_per_m("icao"))
    assert out == pytest.approx(alts)


def test_a3b_clamp_removes_a_curvature_kink():
    pts = [(float(i) * 30.0, 0.0) for i in range(5)]
    alts = [100.0, 100.0, 100.0, 101.0, 102.0]      # 0 % → 3.3 % step
    rate = CFG.ruleset_strip_arc_rate_per_m("icao")
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015, arc_rate_per_m=rate)
    assert out != pytest.approx(alts)
    # every interior triple now satisfies the rate, and the slope law too
    for k in range(1, len(out) - 1):
        dp = pts[k][0] - pts[k - 1][0]
        dn = pts[k + 1][0] - pts[k][0]
        change = abs((out[k + 1] - out[k]) / dn - (out[k] - out[k - 1]) / dp)
        assert change <= rate * 0.5 * (dp + dn) + 1e-9
    for a, b in zip(out, out[1:]):
        assert abs(b - a) <= 0.015 * 30.0 + 1e-9


def test_a3b_default_none_keeps_the_landed_slope_only_behaviour():
    pts = [(float(i) * 30.0, 0.0) for i in range(5)]
    alts = [100.0, 100.0, 100.0, 101.0, 102.0]
    plain = GL.runway_strip_longitudinal_clamp(pts, alts, (1.0, 0.0), 0.015)
    assert plain == GL.runway_strip_longitudinal_clamp(
        pts, alts, (1.0, 0.0), 0.015, arc_rate_per_m=None)


def test_a3b_generation_binding_and_twin():
    """The EMITTER's call site passes the arc rate; the CENSUS reads the
    same ``strip_longitudinal_law`` resolver."""
    from auto_patch import adjacent_ground as AG
    src = inspect.getsource(AG.emit_adjacent_ground_bands)
    assert "strip_longitudinal_law(" in src
    assert "arc_rate_per_m=_arc" in src

    census = _check_grade_source()
    assert "def _check_strip_arc_rate(" in census
    assert "_strip_longitudinal_law(" in census


# ══════════════════════════════════════════════════════════════════════
# §A4 — RADIO ALTIMETER OPERATING AREA
# ══════════════════════════════════════════════════════════════════════

def test_a4_footprint_is_300m_by_120m_before_the_threshold():
    """Annex 14 §3.8.2 "at least 300 m" before the threshold, §3.8.3
    60 m each side (the 30 m aeronautical-study reduction is NOT taken —
    it requires a study this builder cannot perform)."""
    ring = GL.raoa_footprint_ring((0.0, 0.0), (1.0, 0.0), "icao")
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    assert min(xs) == pytest.approx(-300.0)     # BEFORE the threshold
    assert max(xs) == pytest.approx(0.0)
    assert min(ys) == pytest.approx(-60.0)
    assert max(ys) == pytest.approx(60.0)
    assert ring[0] == ring[-1]                  # closed


def test_a4_is_a_no_op_under_the_faa_ruleset():
    """"radio altimeter" does not occur in AC 150/5300-13B — verified.
    KCLT is untouched by this family."""
    assert GL.raoa_footprint_ring((0.0, 0.0), (1.0, 0.0), "faa") is None
    assert GL.raoa_applies("precision", "faa") is False
    assert GL.raoa_applies("precision", "icao") is True
    assert GL.raoa_applies("non_precision", "icao") is False


def test_a4_applicability_reuses_the_repo_classifier():
    """§3.8.1 scopes the area to PRECISION approach runways, and the
    class comes from the repo's ONE classifier — no second
    classification is minted."""
    assert GL.raoa_applies(
        CFG.runway_end_approach_class(3, 0), "icao") is True
    assert GL.raoa_applies(
        CFG.runway_end_approach_class(1, 0), "icao") is False


def test_a4_rate_clamp_binds_2pct_per_30m():
    s = [0.0, 30.0, 60.0, 90.0, 120.0]
    alts = [100.0, 100.0, 100.0, 101.0, 102.0]
    out = GL.raoa_rate_clamp(s, alts, "icao")
    rate = CFG.get_ruleset("icao").raoa_max_grade_change_per_m
    for k in range(1, len(out) - 1):
        change = abs((out[k + 1] - out[k]) / 30.0
                     - (out[k] - out[k - 1]) / 30.0)
        assert change <= rate * 30.0 + 1e-9
    # a no-op where the family does not exist
    assert GL.raoa_rate_clamp(s, alts, "faa") == pytest.approx(alts)


def test_a4_clamp_is_identity_on_a_compliant_profile():
    s = [0.0, 30.0, 60.0, 90.0]
    alts = [100.0, 100.3, 100.6, 100.9]         # constant grade, no change
    assert GL.raoa_rate_clamp(s, alts, "icao") == pytest.approx(alts)


def test_a4_validator_twin():
    src = _check_grade_source()
    assert "def _check_raoa_rate(" in src
    assert "_raoa_footprint_ring(" in src
    assert "raoa, n_ra_st, n_ra_ways = _check_raoa_rate(" in src


# ══════════════════════════════════════════════════════════════════════
# §B1 — SHOULDER TRANSVERSE + the mandated edge drop-off
# ══════════════════════════════════════════════════════════════════════

def test_b1_shoulder_band_per_authority():
    """FAA Table 3-6 S-2 mandates a 1.5-5.0 % fall (so a FLAT shoulder is
    unlawful and the ceiling is below zero); ICAO §3.2.3 mandates FLUSH
    with a ≤2.5 % cap (so the corridor is symmetric)."""
    floor, ceiling = GL.shoulder_transverse_envelope(3.0, 3.0, "faa")
    assert floor == pytest.approx(-0.05 * 3.0)
    assert ceiling == pytest.approx(-0.015 * 3.0)
    assert ceiling < 0.0
    floor, ceiling = GL.shoulder_transverse_envelope(3.0, 3.0, "icao")
    assert floor == pytest.approx(-0.025 * 3.0)
    assert ceiling == pytest.approx(0.025 * 3.0)


def test_b1_shoulder_sub_band_enters_the_adjacent_ground_envelope():
    """Generation binding: the shoulder is PAVEMENT, so it takes the
    shoulder band and the zone-1 lip starts at the shoulder's outer
    edge.  Declaring no shoulder reproduces the pre-§B1 profile exactly."""
    base = GL.adjacent_ground_envelope("runway", 4, "E", 5.0, "icao")
    same = GL.adjacent_ground_envelope("runway", 4, "E", 5.0, "icao",
                                       shoulder_width_m=None)
    assert base == same
    with_sh = GL.adjacent_ground_envelope("runway", 4, "E", 5.0, "icao",
                                          shoulder_width_m=3.0)
    assert with_sh != base
    # inside the shoulder the shoulder band governs
    inside = GL.adjacent_ground_envelope("runway", 4, "E", 2.0, "faa",
                                         shoulder_width_m=3.0)
    assert inside == pytest.approx(
        GL.shoulder_transverse_envelope(2.0, 3.0, "faa"))


def test_b1_edge_dropoff_is_a_MANDATE_not_a_defect():
    """FAA §4.14.2 item 2 (and §5.9.1.5 for aprons): 1.5 in ± 1/2 in
    = 38 ± 13 mm between paved and unpaved.  A step inside that is the
    REGULATION being obeyed."""
    assert GL.shoulder_edge_dropoff_allowance_m("faa") == pytest.approx(0.051)
    assert GL.shoulder_edge_dropoff_allowance_m("icao") == 0.0
    assert GL.shoulder_edge_dropoff_exempt(0.038, True, "faa") is True
    assert GL.shoulder_edge_dropoff_exempt(0.051, True, "faa") is True
    assert GL.shoulder_edge_dropoff_exempt(0.060, True, "faa") is False
    # …only at a paved/unpaved boundary, and never under ICAO (flush)
    assert GL.shoulder_edge_dropoff_exempt(0.038, False, "faa") is False
    assert GL.shoulder_edge_dropoff_exempt(0.038, True, "icao") is False


def test_b1_exemption_has_ONE_predicate_home():
    """Interaction fence: seam v4, the step checks and the census read
    one text (``strip_seam_law``), which delegates to the law."""
    from auto_patch import strip_seam_law as SSL
    assert "paved_unpaved_dropoff_exempt" in SSL.__all__
    assert SSL.paved_unpaved_dropoff_exempt(0.038, 0.051) is True
    assert SSL.paved_unpaved_dropoff_exempt(0.038, 0.0) is False
    # …and the LAW resolves the number and calls straight through, so
    # the seam module stays stdlib-only (it is on a hot solve path and is
    # imported by the standalone ``tools/check_grade.py``).
    src = inspect.getsource(GL.shoulder_edge_dropoff_exempt)
    assert "paved_unpaved_dropoff_exempt" in src


# ══════════════════════════════════════════════════════════════════════
# §B2 — TRANSVERSE SOLVER BINDING
# ══════════════════════════════════════════════════════════════════════

def test_b2_one_station_generator_for_both_consumers():
    """Lockstep BY CONSTRUCTION: the solver's constraint rows and the
    validator's transect reader are built over the SAME stations."""
    stations = GL.transverse_transect_stations((0.0, 0.0), (100.0, 0.0), 20.0)
    assert len(stations) == 11                          # 10 m step
    centre, normal, offsets = stations[0]
    assert centre == pytest.approx((0.0, 0.0))
    assert normal == pytest.approx((0.0, 1.0))
    assert offsets == (-20.0, -10.0, 0.0, 10.0, 20.0)
    assert stations[-1][0][0] == pytest.approx(100.0)
    # degenerate inputs return nothing rather than guessing
    assert GL.transverse_transect_stations((0.0, 0.0), (0.0, 0.0), 20.0) == []


def test_b2_caps_are_ruleset_keyed_per_role():
    assert GL.transverse_cap_for_role("taxiway", "C", "icao") == 0.015
    assert GL.transverse_cap_for_role("taxiway", "B", "icao") == 0.020
    assert GL.transverse_cap_for_role("taxiway", "B", "faa") == 0.015
    assert GL.transverse_cap_for_role("runway", "E", "icao") == 0.015
    assert GL.transverse_cap_for_role("runway", "B", "icao") == 0.020
    assert GL.transverse_cap_for_role("apron", None, "faa") == CFG.APRON_MAX_GRADE
    # a role with no transverse law of its own says so
    assert GL.transverse_cap_for_role("boundary", None, "faa") is None


def test_b2_surface_bounds_are_what_the_solver_constrains():
    lo, hi = GL.transverse_surface_bounds("taxiway", "B", 12.0, "icao")
    assert lo == pytest.approx(-0.24)
    assert hi == pytest.approx(0.24)
    lo, hi = GL.transverse_surface_bounds("taxiway", "B", 12.0, "faa")
    assert lo == pytest.approx(-0.18)
    assert hi == pytest.approx(0.18)


def test_b2_crown_minimum_recorded_not_bound_but_flippable():
    """Owner question 5.  The values are carried and the flip is ONE
    line; nothing asserts them until the owner rules."""
    assert CFG.CROWN_MINIMUM_BOUND is False
    assert GL.transverse_minimum_for_role("runway", "faa") == 0.010
    assert GL.transverse_minimum_for_role("taxiway", "faa") == 0.010
    assert GL.transverse_minimum_for_role("apron", "faa") is None


def test_b2_legacy_cap_accessors_honour_the_split():
    """The within-shape ``cT`` pricing reaches the split through the same
    config accessors, so no second copy of the number appears."""
    assert CFG.taxi_transverse_cap_for_letter("B", ruleset="icao") == 0.020
    assert CFG.taxi_transverse_cap_for_letter("B", ruleset="faa") == 0.015
    assert CFG.taxi_transverse_cap_for_letter("D", ruleset="faa") == 0.015


# ══════════════════════════════════════════════════════════════════════
# §B3 — DRAINAGE MINIMUM
# ══════════════════════════════════════════════════════════════════════

def test_b3_apron_minimum_is_faa_only():
    """FAA §5.9.1.1 "Provide a minimum 0.5 percent apron gradient".
    ICAO §3.13.5 is qualitative, so the ICAO half is a no-op — a numeric
    ICAO minimum would be MINTED, not cited."""
    assert GL.drainage_minimum_grade("apron", "faa") == 0.005
    assert GL.drainage_minimum_grade("apron", "icao") is None
    assert GL.drainage_minimum_grade("stand", "faa") == 0.005


def test_b3_groundside_minimum_is_region_invariant_and_provisional():
    for key in ("faa", "icao"):
        assert GL.drainage_minimum_grade("groundside", key) == 0.010
    assert CFG.GROUNDSIDE_MIN_DRAINAGE_GRADE_PROVISIONAL is True


def test_b3_named_exclusions():
    """Building pads stay FLAT (``TERMINAL_PADS_SLOPE=False`` is owner
    law); terrace panels are exempt until owner question 4 is answered
    (the apron terrace law's "level panels")."""
    assert CFG.TERMINAL_PADS_SLOPE is False
    assert GL.drainage_minimum_grade("apron", "faa", building_pad=True) is None
    assert GL.drainage_minimum_grade("apron", "faa", terrace_panel=True) is None
    assert GL.drainage_minimum_grade("groundside", "faa",
                                     building_pad=True) is None


def test_b3_stand_band_is_one_law_not_two():
    """The pre-registration's "no stand exceeds 1.0 %" upper twin and its
    0.5 % lower twin are ONE band, so they cannot disagree."""
    low, high = GL.drainage_minimum_band("stand", "faa")
    assert low == pytest.approx(0.005)
    assert high == pytest.approx(0.010)
    low, high = GL.drainage_minimum_band("stand", "icao")
    assert low is None
    assert high == pytest.approx(0.010)


def test_b3_a_minimum_above_the_cap_is_LOUD():
    """Feasibility is guaranteed (docs/RULINGS.md): a genuine
    contradiction is an ERROR, never a silently softened number."""
    class _Fake:
        pass
    import auto_patch.grade_law as _gl
    original = _gl.ROLE_GRADE_LIMITS.get("apron")
    try:
        _gl.ROLE_GRADE_LIMITS["apron"] = 0.001      # below the FAA 0.5 %
        with pytest.raises(ValueError):
            GL.drainage_minimum_band("apron", "faa")
    finally:
        if original is None:
            _gl.ROLE_GRADE_LIMITS.pop("apron", None)
        else:
            _gl.ROLE_GRADE_LIMITS["apron"] = original


def test_b3_shortfall_is_the_one_reading():
    assert GL.drainage_minimum_shortfall(0.002, "apron", "faa") == \
        pytest.approx(0.003)
    assert GL.drainage_minimum_shortfall(0.008, "apron", "faa") == 0.0
    assert GL.drainage_minimum_shortfall(0.000, "apron", "icao") == 0.0


def test_b3_validator_twin():
    src = _check_grade_source()
    assert "def _check_drainage_minimum(" in src
    assert "_drainage_minimum_shortfall(" in src
    assert "drain_min, n_dm_pairs, n_dm_ways = _check_drainage_minimum(" in src


# ══════════════════════════════════════════════════════════════════════
# THE GATE SWEEP (docs/RULINGS.md 2026-08-05, build-complete-then-debug)
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("env", [
    "O4_STRIP_PRECEDENCE",
    "O4_RAW_LAW_SWEEPS",
    "O4_EMIT_SNAP_GUARD",
    "O4_BAND_SEED_COMPLETE",
])
def test_retired_law_gates_are_gone_from_the_source(env):
    """"NO GATES.  Every believed-in law becomes standing law; O4_ law
    gates and their env overrides are DELETED as their territory is
    touched.""" ""
    import auto_patch
    root = os.path.dirname(os.path.abspath(auto_patch.__file__))
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path) as fh:
                text = fh.read()
            # a mention in a comment/docstring is the RECORD of the
            # retirement; an environ read is the gate still being alive
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if env in line and "environ" in line:
                    hits.append(f"{path}: {stripped}")
    assert hits == [], hits


def test_the_retired_gates_laws_are_standing():
    from auto_patch import emit_snap
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch.elevation_per_surface.route_profile import one_solve

    assert CFG.STRIP_PRECEDENCE_ENABLED is True
    assert emit_snap.emit_snap_enabled() is True
    assert one_solve.raw_law_sweeps_enabled() is True
    # BAND-SEED COMPLETENESS went further in the SEATS lane: the
    # predicate is deleted, not made constant-true, so the standing law
    # is asserted by its ABSENCE.
    assert not hasattr(BF, "band_seed_complete_enabled")


def test_standing_laws_ignore_their_old_env_values(monkeypatch):
    """A stale ``O4_...=0`` in an environment must not resurrect a
    retired gate."""
    from auto_patch import emit_snap
    from auto_patch.elevation_per_surface import building_feasibility as BF
    from auto_patch.elevation_per_surface.route_profile import one_solve

    for env in ("O4_RAW_LAW_SWEEPS", "O4_EMIT_SNAP_GUARD",
                "O4_BAND_SEED_COMPLETE", "O4_STRIP_PRECEDENCE"):
        monkeypatch.setenv(env, "0")
    assert emit_snap.emit_snap_enabled() is True
    assert one_solve.raw_law_sweeps_enabled() is True
    assert not hasattr(BF, "band_seed_complete_enabled")
    assert 'O4_BAND_SEED_COMPLETE"' not in open(BF.__file__).read()


def test_no_ruleset_split_gate_was_introduced():
    """The draft specced ``O4_RULESET_SPLIT`` default "0"; under
    build-complete-then-debug the split is STANDING LAW and no such gate
    exists.  ``O4_RULESET`` survives only as a testing override."""
    import auto_patch
    root = os.path.dirname(os.path.abspath(auto_patch.__file__))
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path) as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue            # the RECORD of the decision
                    if "O4_RULESET_SPLIT" in line:
                        hits.append(f"{path}: {stripped}")
    assert hits == [], hits
    assert CFG._RULESET_ENV == "O4_RULESET"
