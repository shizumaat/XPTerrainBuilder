"""THE RUNWAY CROWN MINIMUM BINDS — generation-binding twin + validator.

Owner ruling ``docs/RULINGS.md`` 2026-08-05 (commit d48bc0a), which
answers standing open question Q5 for one family:

    "RUNWAY CROWNS: generated and bound (this answers open question Q5
     for runways — the crown minimum BINDS on runways; taxiway/apron
     crowns stay recorded-unbound with citations)."

Citations: FAA AC 150/5300-13 Table 3-6 line S-1 and §4.14.2 item 1a
(1.0 % cross-slope minimum); ICAO Annex 14 §3.1.19 (the runway transverse
"should not … be less than 1 per cent except at runway or taxiway
intersections").

WHAT WAS UNBOUND, AND WHY THAT MATTERED.  The crown was GENERATED —
``crown.runway_crown_drop_m`` has always shed the runway edge — but the
minimum was asserted by nothing.  Two independent numbers
(``config.RUNWAY_CROWN_TRANSVERSE`` and the rulesets'
``runway_transverse_min``) happened to both read 0.010, and no instrument
compared them; either could have moved and left every runway crowned
below its own mandated floor with only a code read to notice.  The emit
grid could do it on its own: a 22.4 m half-width crowned to 0.224 m,
rounded to 0.22 m, and realised 0.98 %.
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import auto_patch.config as CFG
from auto_patch import crown as CR
from auto_patch import grade_law as GL

_RULESETS = ("faa", "icao")
# Real runway half-widths: 30 m (code F, 60 m wide) down to 7.5 m, plus
# the awkward ones the 1 cm emit grid used to round the wrong way.
_HALF_WIDTHS = [7.5, 10.0, 11.25, 15.0, 18.0, 22.4, 22.5, 23.0, 25.0,
                29.9, 30.0, 45.0]


# ── THE SCOPE THE OWNER RULED ───────────────────────────────────────

def test_the_minimum_binds_on_runways_and_only_on_runways():
    """Runways yes; taxiways stay recorded-unbound this version."""
    assert GL.transverse_minimum_binds("runway") is True
    assert GL.transverse_minimum_binds("runway_crossing") is True
    assert GL.transverse_minimum_binds("taxiway") is False
    assert GL.transverse_minimum_binds("primary_parallel") is False
    assert GL.transverse_minimum_binds("apron") is False
    assert CFG.CROWN_MINIMUM_BOUND_RUNWAYS is True
    assert CFG.CROWN_MINIMUM_BOUND_TAXIWAYS is False


def test_the_taxiway_minimum_is_still_RECORDED():
    """Unbound is not deleted: the citation and the value survive, so
    the gap census stays complete and the flip stays one constant."""
    assert GL.transverse_minimum_for_role("taxiway", "faa") == 0.010
    assert GL.transverse_minimum_for_role("runway", "faa") == 0.010
    assert GL.transverse_minimum_for_role("runway", "icao") == 0.010


@pytest.mark.parametrize("ruleset", _RULESETS)
def test_the_runway_constraint_row_is_mandatory_DOWN(ruleset):
    """The bound band is ``[-cap·t, -min·t]``: a runway transect may not
    be FLAT, and it may not rise away from the centreline."""
    for t in (5.0, 22.5, 30.0):
        lo, hi = GL.transverse_surface_bounds("runway", "C", t, ruleset)
        cap = GL.transverse_cap_for_role("runway", "C", ruleset)
        low = GL.transverse_minimum_for_role("runway", ruleset)
        assert lo == pytest.approx(-cap * t)
        assert hi == pytest.approx(-low * t)
        assert hi < 0.0, "a FLAT runway transect is inside the band"


@pytest.mark.parametrize("ruleset", _RULESETS)
def test_the_taxiway_constraint_row_stays_symmetric(ruleset):
    lo, hi = GL.transverse_surface_bounds("taxiway", "C", 11.0, ruleset)
    assert lo == pytest.approx(-hi)
    assert hi > 0.0


# ── THE GENERATION SIDE — the rate comes FROM the law ───────────────

@pytest.mark.parametrize("ruleset", _RULESETS)
def test_the_generated_rate_is_derived_from_the_ruleset(ruleset):
    rate = GL.runway_crown_rate(ruleset)
    assert rate >= GL.transverse_minimum_for_role("runway", ruleset)
    assert rate <= GL.transverse_cap_for_role("runway", "C", ruleset)


import dataclasses as _dc


def _ruleset_with(**kw):
    """A copy of the FAA ruleset with fields replaced (it is frozen —
    which is why the twins clone rather than monkeypatch)."""
    return _dc.replace(CFG.get_ruleset("faa"), **kw)


def test_a_raised_minimum_RAISES_the_generated_crown(monkeypatch):
    """The binding is real, not a coincidence of two equal constants: a
    ruleset whose minimum moves drags the generated rate with it."""
    steep = _ruleset_with(runway_transverse_min=0.012)
    monkeypatch.setattr(GL, "get_ruleset", lambda *_a, **_k: steep)
    assert GL.runway_crown_rate("faa") == pytest.approx(0.012)
    assert CR.runway_crown_drop_m(30.0, "faa") >= 0.36 - 1e-9


def test_a_minimum_above_its_own_maximum_is_LOUD(monkeypatch):
    """A ruleset that contradicts itself must say so — never a silently
    softened number (``feasibility-is-guaranteed``)."""
    broken = _ruleset_with(runway_transverse_min=0.99)
    monkeypatch.setattr(GL, "get_ruleset", lambda *_a, **_k: broken)
    with pytest.raises(ValueError):
        GL.runway_crown_rate("faa")


@pytest.mark.parametrize("ruleset", _RULESETS)
@pytest.mark.parametrize("half_width", _HALF_WIDTHS)
def test_the_EMITTED_drop_never_realises_below_the_minimum(half_width,
                                                           ruleset):
    """THE VALIDATOR TWIN, on the number that actually ships.

    The emitted drop is quantized to the 1 cm emit grid, so what the law
    has to hold is the REALISED rate ``drop / half_width`` — not the
    rate the generator intended.  ``round`` failed this at 22.4 m
    (0.982 %); ``ceil`` to the grid cannot.
    """
    drop = CR.runway_crown_drop_m(half_width, ruleset)
    t = min(float(half_width), CR._RUNWAY_HALFW_CAP_M)
    low = GL.transverse_minimum_for_role("runway", ruleset)
    high = GL.transverse_cap_for_role("runway", "C", ruleset)
    realised = drop / t
    assert realised >= low - 1e-12, (
        f"half-width {half_width} m crowned to {drop} m = "
        f"{realised * 100:.3f} %, under the {low * 100:.1f} % minimum")
    assert realised <= high + 1e-12, (
        f"half-width {half_width} m crowned past the transverse cap")
    # And the drop is ON the 1 cm emit grid, so the stamped ring values
    # and the exported ``crown_drops`` sidecar agree exactly.
    assert abs(drop * 100.0 - round(drop * 100.0)) < 1e-6


def test_the_grid_rounds_UP_never_down():
    """The specific regression: 22.4 m used to lose 0.004 m to ``round``
    and land under the floor.  Also pins that an exact centimetre is not
    pushed to the next one by float noise."""
    assert CR.runway_crown_drop_m(22.4) == pytest.approx(0.23)
    assert CR.runway_crown_drop_m(23.0) == pytest.approx(0.23)
    assert CR.runway_crown_drop_m(30.0) == pytest.approx(0.30)


def test_a_descoped_runway_family_still_emits_no_ridge(monkeypatch):
    """Binding the minimum must not resurrect a crown the family scoping
    turned off — an unbuilt surface has no cross-slope to bound."""
    monkeypatch.setattr(CR, "CROWN_RUNWAYS", False)
    assert CR.runway_crown_drop_m(30.0) == 0.0
    monkeypatch.setattr(CR, "CROWN_RUNWAYS", True)
    monkeypatch.setattr(CR, "ENABLE_SPINE_CROWN", False)
    assert CR.runway_crown_drop_m(30.0) == 0.0


def test_half_width_stays_capped_at_the_runway_cross_section():
    """A shoulder-widened runway crowns its RUNWAY cross-section, not the
    shoulder span — the cap is a geometry decision the binding must not
    quietly change."""
    assert CR.runway_crown_drop_m(45.0) == CR.runway_crown_drop_m(30.0)
    assert math.isclose(CR.runway_crown_drop_m(60.0),
                        CR.runway_crown_drop_m(30.0))


# ══════════════════════════════════════════════════════════════════════
# THE VALIDATOR HALF — the crown's CENSUS READER (S7 escalation, ruled
# 2026-08-14)
# ══════════════════════════════════════════════════════════════════════
# UNTIL NOW THIS FILE WAS THE WHOLE STORY, and that was the gap: the
# minimum was bound ONLY where it is generated.  S7 measured a runway
# emitted dead flat against a declared 0.30 m crown drop censusing ZERO
# rows — the within-shape law re-centres each pair's budget on the
# DESIGNED crown (``grade_law.crown_pair_offset``) and then judges the
# residue against the runway's own transverse CAP, and a 1 % crown sits
# inside a 1.5 % cap by construction.  With the 2026-08-14 clarification
# naming the runway crown as one of the three surviving drainage laws,
# it was a law we could not see.  ``check_grade._check_runway_crown`` is
# the reader; these are its twins, both directions.
#
# HOW THE CROWN IS EMITTED (and so what the reader compares): the runway
# RING carries the crowned surface ``z' − drop`` and the ridge is a
# separate ``o4_feature=crown_spine`` breakline at ``z'``.  The declared
# per-node drop is the axes sidecar's ``crown_drops`` — the SAME field
# the solver built to, which is what lets the reader honour the law's
# own relaxations (rail continuity, the tile-seam taper) instead of
# reporting them as defects.

def _law_reader():
    import importlib.util as _ilu
    root = Path(__file__).resolve().parents[1]
    spec = _ilu.spec_from_file_location(
        "s8_crown_check_grade", root / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


#: The fixture runway: 60 m wide (half-width 30 m, code F), 200 m of it.
_RW_HALF_W = 30.0
_RW_LEN = 200.0
_RW_Z = 100.0


def _crown_census(tmp_path, realised_drop_m, *, declare=True,
                  ridge=True, role="runway", ruleset="icao"):
    """Census one straight runway whose ring sits ``realised_drop_m``
    below its ridge, against a DECLARED drop of ``runway_crown_drop_m``.

    ``declare=False`` writes no crown field at all (the missing-declaration
    condition); ``ridge=False`` writes no crown-spine breakline.
    """
    from conftest import write_synthetic_patch, synthetic_patch_ll
    cg = _law_reader()
    declared = CR.runway_crown_drop_m(_RW_HALF_W, ruleset)
    edge_z = _RW_Z - realised_drop_m
    ring = [(-_RW_HALF_W, 0.0, edge_z), (_RW_HALF_W, 0.0, edge_z),
            (_RW_HALF_W, _RW_LEN, edge_z), (-_RW_HALF_W, _RW_LEN, edge_z)]
    ways = [{"role": role, "ref": "09/27", "ring": ring}]
    if ridge:
        ways.append({"role": "", "ref": "", "closed": False,
                     "o4_feature": "crown_spine",
                     "ring": [(0.0, y, _RW_Z)
                              for y in (0.0, 50.0, 100.0, 150.0, _RW_LEN)]})
    side = {"ruleset": ruleset}
    if declare:
        side["crown_drops"] = [
            list(synthetic_patch_ll(x, y)) + [declared]
            for (x, y, _z) in ring]
    osm = write_synthetic_patch(tmp_path, ways, sidecar=side)
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    return cg, fam["runway_crown"], declared


def test_the_crown_family_is_registered():
    """A check ``run_checks`` emits and the register does not name is the
    census-wrapper defect; ``tests/test_harness.py`` asserts the register
    against the emission, and this pins the key the reports quote."""
    cg = _law_reader()
    assert "runway_crown" in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert cg._CROWN_OUT_OF_SCOPE in cg.OUT_OF_SCOPE_CLASSES


def test_a_flat_runway_against_a_declared_crown_IS_censused(tmp_path):
    """THE S7 SPECIMEN, verbatim: a runway emitted dead flat while its
    build declared a 0.30 m crown drop."""
    cg, rows, declared = _crown_census(tmp_path, 0.0)
    assert declared == pytest.approx(0.30)
    assert rows, ("a dead-flat runway under a 0.30 m declared crown "
                  "censused ZERO — the kept crown law has no reader")
    assert all(cg.row_roles(r) == ("runway", "runway") for r in rows)
    # the shortfall is the whole declared drop, less the emit-grid noise
    worst = max(rows, key=lambda r: r.excess_pct)
    assert worst.de_m == pytest.approx(0.0, abs=1e-6)
    assert worst.excess_pct == pytest.approx(
        100.0 * (declared - cg.ELEV_ROUNDING_NOISE_M) / _RW_HALF_W, abs=0.05)
    assert all(r.out_of_scope is None for r in rows), (
        "a straight runway is not an intersection")


def test_a_properly_crowned_runway_censuses_zero(tmp_path):
    """The other direction — without it the twin above proves only that
    the family fires.  The ring sits its full declared drop below the
    ridge, which is what the emitter builds."""
    _cg, rows, declared = _crown_census(tmp_path, 0.30)
    assert declared == pytest.approx(0.30)
    assert rows == [], "a lawfully crowned runway must mint no row"


def test_the_emit_grid_alone_is_not_a_flat_runway(tmp_path):
    """One centimetre of round is not a defect: the ridge and the ring
    are both emitted on the 0.01 m grid and the drop is quantised UP onto
    it, so the allowance is the pair's own quantisation envelope."""
    _cg, rows, _d = _crown_census(tmp_path, 0.29)
    assert rows == []


def test_a_crown_shortfall_at_an_INTERSECTION_is_out_of_scope(tmp_path):
    """THE CITED EXCEPTION, not an invented one.  ICAO §3.1.19 exempts
    runway and taxiway INTERSECTIONS from the transverse minimum (FAA
    Table 3-6 S-1 likewise), and ``runway_crossing`` IS that surface
    here.  The rows are still MEASURED and still counted in the family —
    instruments report — but the acceptance verdict must not adjudicate
    a row the law expressly does not require."""
    cg, rows, _d = _crown_census(tmp_path, 0.0, role="runway_crossing")
    assert rows, "the row is measured, not dropped"
    assert all(r.out_of_scope == cg._CROWN_OUT_OF_SCOPE for r in rows)
    assert not any(cg.row_adjudicated("runway_crown", r) for r in rows)


def test_a_runway_that_DECLARED_NO_CROWN_is_its_own_condition(tmp_path):
    """NEVER A SILENT ZERO (the S3 blindness verdict, applied before this
    family can acquire the defect).  A shape with no declaration has no
    relaxation record to honour, so the ruleset's own floor judges it —
    and the count is reported separately from the honoured-declaration
    rows."""
    cg, rows, _d = _crown_census(tmp_path, 0.0, declare=False)
    assert rows, ("an undeclared runway censused zero — 'nothing was "
                  "declared' and 'the crown is lawful' would print the "
                  "same number")
    floor = GL.transverse_minimum_for_role("runway", "icao")
    worst = max(rows, key=lambda r: r.excess_pct)
    assert worst.excess_pct == pytest.approx(
        100.0 * (floor * _RW_HALF_W - cg.ELEV_ROUNDING_NOISE_M) / _RW_HALF_W,
        abs=0.05)


def test_a_patch_with_NO_RIDGE_at_all_censuses_the_whole_crown(tmp_path):
    """The catastrophic case the reader must not read as compliance: the
    crown-spine breakline is absent, so no crown was emitted anywhere —
    every declared node is short by its whole drop."""
    _cg, rows, declared = _crown_census(tmp_path, 0.0, ridge=False)
    assert declared == pytest.approx(0.30)
    assert rows, "no ridge means no crown, and that must not read zero"


def test_the_reader_honours_the_laws_own_relaxations(tmp_path):
    """A node whose drop the law LOWERED (rail continuity, the tile-seam
    taper) is judged at the drop it was given, not at ``rate ×
    half_width`` — which is why the reader reads the declared field
    rather than re-deriving the rate."""
    from conftest import write_synthetic_patch, synthetic_patch_ll
    cg = _law_reader()
    ring = [(-_RW_HALF_W, 0.0, _RW_Z - 0.05), (_RW_HALF_W, 0.0, _RW_Z - 0.05),
            (_RW_HALF_W, _RW_LEN, _RW_Z - 0.05),
            (-_RW_HALF_W, _RW_LEN, _RW_Z - 0.05)]
    osm = write_synthetic_patch(
        tmp_path,
        [{"role": "runway", "ref": "09/27", "ring": ring},
         {"role": "", "closed": False, "o4_feature": "crown_spine",
          "ring": [(0.0, y, _RW_Z) for y in (0.0, 100.0, _RW_LEN)]}],
        sidecar={"ruleset": "icao",
                 "crown_drops": [list(synthetic_patch_ll(x, y)) + [0.05]
                                 for (x, y, _z) in ring]})
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    assert fam["runway_crown"] == [], (
        "a relaxed 0.05 m declared drop, realised exactly, is lawful — "
        "re-deriving rate x half_width would report the law's own "
        "relaxation as a defect")


def test_a_patch_with_NO_CROWN_MACHINERY_AT_ALL_still_censuses(tmp_path):
    """THE GATE-OFF CASE, and the last place this family could go silent:
    with ``ENABLE_SPINE_CROWN`` / ``CROWN_RUNWAYS`` off the build emits
    NEITHER a declared drop NOR a ridge breakline, so a reader that needed
    either one would read zero on a runway with no crown at all — while
    ``CROWN_MINIMUM_BOUND_RUNWAYS`` still says the minimum binds.  The
    offset then comes from the LAW's own runway axis
    (``grade_law.runway_axis_and_width``), which is why the row can still
    price a cross-section."""
    cg, rows, _d = _crown_census(tmp_path, 0.0, declare=False, ridge=False)
    assert rows, ("a runway with no declaration AND no ridge censused "
                  "zero — the bound minimum is invisible exactly where "
                  "nothing was built")
    floor = GL.transverse_minimum_for_role("runway", "icao")
    worst = max(rows, key=lambda r: r.excess_pct)
    # the offset is the runway's real half-width, read off the law's axis
    assert worst.distance_m == pytest.approx(_RW_HALF_W, abs=0.5)
    assert worst.excess_pct == pytest.approx(
        100.0 * (floor * _RW_HALF_W - cg.ELEV_ROUNDING_NOISE_M) / _RW_HALF_W,
        abs=0.05)
