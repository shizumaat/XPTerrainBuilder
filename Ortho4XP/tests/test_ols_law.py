"""OLS law unit tests (slice 1) — pure, headless, no DEM / X-Plane needed.

The law lives in ``grade_law.ols_*``; the rule VALUES live in ``config``.
Design + citations: ``docs/specs/obstacle-limitation-surfaces-spec.md``.

The property these tests exist for is CONTINUITY: the composed lateral
ceiling runs ``zones 1-2 -> zone-3 +5 % -> OLS transitional``, and a step
anywhere along it would mint a wall between two active cut bands — the
exact class the 2026-07-09 weld ruling exists to prevent.  So the join at
the handover distance is asserted EXACTLY (not to a tolerance): both sides
read the same ``_adjacent_strip_envelope`` helper, so they must agree to
the bit.
"""
import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from auto_patch.config import OLS_APPROACH_FIRST_SECTION_SLOPE

CLASSES = ("visual", "non_precision", "precision")
CODES = (1, 2, 3, 4)


def test_npa_code_34_first_section_is_two_percent():
    """Regression pin for the gap-audit correction (2026-07-24): NPA code
    3/4 is 2 %, the SAME as precision 3/4 — 3.33 % is NPA code 1/2.  The
    audit carried the wrong keying until this arc re-verified Table 4-1."""
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][3] == 0.02
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][4] == 0.02
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][1] == 0.0333
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][2] == 0.0333
    assert (OLS_APPROACH_FIRST_SECTION_SLOPE["precision"][4]
            == OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][4])


