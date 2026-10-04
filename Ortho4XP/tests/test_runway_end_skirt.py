"""Runway end skirt (inverse RESA) — approach classification and law.

The skirt governs terrain that DROPS beyond a runway end, mirroring the
Pass C RESA cut that governs terrain that rises.  Regulatory basis and
plan: ``docs/runway_end_skirt_plan.md``.
"""
import pytest

from auto_patch.config import runway_end_approach_class


# ──────────────────────────────────────────────────────────────────────
# Approach classification (apt.dat row-100 per-end markings + lights)
# ──────────────────────────────────────────────────────────────────────
class TestRunwayEndApproachClass:
    @pytest.mark.parametrize("markings", [3, 5])
    def test_precision_markings(self, markings):
        assert runway_end_approach_class(markings, 0) == "precision"

    @pytest.mark.parametrize("lights", [1, 2, 3, 4, 5, 8])
    def test_precision_approach_lights_upgrade_blank_markings(self, lights):
        """ALSF/Calvert/SSALR/MALSR imply a precision approach even when
        the markings field was left 0 (common in gateway data)."""
        assert runway_end_approach_class(0, lights) == "precision"

    def test_precision_lights_win_over_visual_paint(self):
        assert runway_end_approach_class(1, 8) == "precision"

    @pytest.mark.parametrize("markings", [2, 4])
    def test_non_precision_markings(self, markings):
        assert runway_end_approach_class(markings, 0) == "non_precision"

    @pytest.mark.parametrize("lights", [6, 7, 9, 10, 11, 12])
    def test_lesser_lighting_does_not_upgrade(self, lights):
        """SSALF/SALS/MALSF/MALS/ODALS/RAIL also serve non-precision
        approaches — they never upgrade the class on their own."""
        assert runway_end_approach_class(2, lights) == "non_precision"
        assert runway_end_approach_class(1, lights) == "visual"

    def test_explicit_visual_markings(self):
        assert runway_end_approach_class(1, 0) == "visual"

    def test_blank_row_defaults_long(self):
        """Missing data must never pick the SHORT skirt footprint."""
        assert runway_end_approach_class(0, 0) == "non_precision"


# ──────────────────────────────────────────────────────────────────────
# Floor profile (lowest lawful surface beyond the runway end)
# ──────────────────────────────────────────────────────────────────────
_STATIONS = [float(d) for d in range(0, 306, 5)]


# ──────────────────────────────────────────────────────────────────────
# _build_filled_skirts — the fill-direction twin of the cut builder
# ──────────────────────────────────────────────────────────────────────
_CAP = 240.0


# REGION RULESETS, phase B: the ``RUNWAY_END_SKIRT_*`` module constants
# ARE the FAA ruleset's values (AC 150/5300-13B §3.16.5), so every test
# below that asserts against them names ``"faa"`` explicitly.  ICAO
# Annex 14 §3.5.10 has NO 61 m near zone — its own behaviour has its own
# twins.  Passing no ruleset resolves to the module default, which is
# ICAO ("everywhere else" is the owner's default).
_FAA = "faa"


# ──────────────────────────────────────────────────────────────────────
# Pass D end-to-end: synthetic-layout harness shared by the emit,
# validator, blast-pad-flank and road-awareness test classes
# ──────────────────────────────────────────────────────────────────────


