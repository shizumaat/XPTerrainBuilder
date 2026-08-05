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
