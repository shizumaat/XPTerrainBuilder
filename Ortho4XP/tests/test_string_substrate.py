"""Tests for the string SUBSTRATE (Fable RULING 1, 2026-07-31).

Headless, synthetic, no network and no X-Plane install: every fixture is
hand-built metre-space geometry, so the ruled mechanics are asserted
directly rather than through an airport.

The ruled mechanics under test, each with its own case:
  1. per-station membership at ``tol_m``;
  2. maximal runs;
  3. sub-``tol_m`` runs absorbed (anti-chatter, derived from the owner's
     constant);
  4. every CUT mints a seam joint to the covering piece — and a way's own
     endpoint is not a cut.
Plus the two properties the ruling turns on: SUBSEGMENT (not per-way)
granularity, and RECOGNITION-NOT-BRIDGING.
"""

from __future__ import annotations


import pytest

from auto_patch.config import TAUT_STRING_SPINE_TOLERANCE_M

TOL = float(TAUT_STRING_SPINE_TOLERANCE_M)
STEP = 5.0


def _line(x0, y0, x1, y1):
    return [(x0, y0), (x1, y1)]


# ── the owner's constant is what we test against ────────────────────

def test_owner_constant_is_eight_metres():
    """The ruling wires ``bound_m``/the corridor at the owner's 8.0 m.

    Guards the literal from drifting silently under the module (this is
    the constant the anti-chatter rule is DERIVED from, so a change moves
    two behaviours at once).
    """
    assert TAUT_STRING_SPINE_TOLERANCE_M == pytest.approx(8.0)


# ── resampling ──────────────────────────────────────────────────────


# ── (1) per-station membership ──────────────────────────────────────


# ── (2) maximal runs + SUBSEGMENT granularity ───────────────────────


# ── (3) anti-chatter absorption ─────────────────────────────────────

# The absorption fixtures use a COLLINEAR construction so the uncovered
# window is exact and computable, not eyeballed: apt.dat and the OSM way
# lie on the SAME line, apt.dat covering all but a gap of width G.  A
# station is then uncovered iff it is more than tol_m from BOTH gap
# edges, so the uncovered window is exactly ``G - 2 * tol_m``.  The
# fixture places that window decisively on one side of the criterion
# rather than asserting a geometric intuition.


# ── (4) seam joints ─────────────────────────────────────────────────


# ── assembly, ordering, determinism ─────────────────────────────────


# ── required-explicit sampling resolution ───────────────────────────


# ── stats are a closed account ──────────────────────────────────────


# ── the index is an optimisation, never a behaviour ─────────────────


# ══════════════════════════════════════════════════════════════════════
# THE RUNWAY CLIP (owner ruling 2026-07-31)
# ══════════════════════════════════════════════════════════════════════


from auto_patch.config import TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M


def test_owner_clip_constant_is_fifty():
    """Owner-supplied; only he moves it (guards silent recalibration)."""
    assert TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M == pytest.approx(50.0)


# ── FABLE'S NAMED REGRESSION PINS (2026-07-31) ──────────────────────
# Three properties the owner's clip must hold for good.  Each is pinned
# against the mechanism that would break it, not against a number.


