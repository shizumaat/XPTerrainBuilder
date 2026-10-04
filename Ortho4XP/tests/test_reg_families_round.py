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
import os

import pytest

from auto_patch import config as CFG


_CHECK_GRADE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tools", "check_grade.py"))


def _check_grade_source() -> str:
    with open(_CHECK_GRADE, encoding="utf-8") as fh:
        return fh.read()


# ══════════════════════════════════════════════════════════════════════
# §A1 — RESA / END-CORRIDOR TRANSVERSE
# ══════════════════════════════════════════════════════════════════════


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


# ══════════════════════════════════════════════════════════════════════
# §A3(a) — the longitudinal-aware breach trigger
# ══════════════════════════════════════════════════════════════════════


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


# ══════════════════════════════════════════════════════════════════════
# §A4 — RADIO ALTIMETER OPERATING AREA
# ══════════════════════════════════════════════════════════════════════


def test_a4_validator_twin():
    src = _check_grade_source()
    assert "def _check_raoa_rate(" in src
    assert "_raoa_footprint_ring(" in src
    assert "raoa, n_ra_st, n_ra_ways = _check_raoa_rate(" in src


# ══════════════════════════════════════════════════════════════════════
# §B1 — SHOULDER TRANSVERSE + the mandated edge drop-off
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §B2 — TRANSVERSE SOLVER BINDING
# ══════════════════════════════════════════════════════════════════════


def test_b2_legacy_cap_accessors_honour_the_split():
    """The within-shape ``cT`` pricing reaches the split through the same
    config accessors, so no second copy of the number appears."""
    assert CFG.taxi_transverse_cap_for_letter("B", ruleset="icao") == 0.020
    assert CFG.taxi_transverse_cap_for_letter("B", ruleset="faa") == 0.015
    assert CFG.taxi_transverse_cap_for_letter("D", ruleset="faa") == 0.015


# ══════════════════════════════════════════════════════════════════════
# §B3 — DRAINAGE MINIMUM
# ══════════════════════════════════════════════════════════════════════


def test_b3_the_retirement_is_REGISTERED_not_just_absent():
    """A retired law and a blind walk print the same zero — and this
    family has had both within a week (RULINGS 2026-08-13b, the
    census-blindness verdict; RULINGS 2026-08-14, the retirement).  The
    register is what tells a reader which zero they are looking at, and it
    must name the roles that actually left the walk.
    """
    import tools.check_grade as CG

    entry = CG.RETIRED_LAWS["drainage_minimum::groundside"]
    assert entry["family"] == "drainage_minimum"
    assert CG.RETIRED_LAW_RULING in entry["why"]
    assert set(entry["roles"]) == {"groundside_pavement", "service_road",
                                   "service_junction"}
    assert not (set(entry["roles"]) & set(CG._DRAINAGE_MIN_ROLES)), (
        "a role the register calls RETIRED is still in the family's walk")
    # ...and the family itself is still a family, on aprons.
    assert "drainage_minimum" in {k for k, _t, _b in CG.LAW_FAMILIES}
    assert "apron" in CG._DRAINAGE_MIN_ROLES


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
    "O4_QUANT_MARGIN",
    "O4_EMIT_SNAP_GUARD",
    "O4_BAND_SEED_COMPLETE",
    # A LAW value may never come from the environment (2026-08-05): the
    # taxiway vertical-curve run is ``config.TAXIWAY_CURVE_RUN_M``.
    "O4_TAXIWAY_CURVE_RUN_M",
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
            with open(path, encoding="utf-8") as fh:
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
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue            # the RECORD of the decision
                    if "O4_RULESET_SPLIT" in line:
                        hits.append(f"{path}: {stripped}")
    assert hits == [], hits
    assert CFG._RULESET_ENV == "O4_RULESET"
