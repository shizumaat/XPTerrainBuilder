"""Runway flex completion — the twins for
``docs/specs/runway-flex-completion-spec.md``.

Four defects, four fixes.  All STANDING LAW since the
build-complete-then-debug round retired ``O4_FLEX_SELF_UNLOCK`` and
``O4_RUNWAY_DEM_FOLLOW``; the twins that pinned the gate-OFF arms are
deleted, not rewritten — that behaviour no longer exists.

1. **The self-anchor lock.**
   ``apply_runway_flex`` inserts every applied target as
   ``anchored=True``; ``flex_slack_at`` bounds against ALL anchored
   samples, and its bound is ``cap·|s_t − s_i|`` — so at the station of
   an anchor the slack is identically zero.  A station the flex touched
   in round 0 is therefore frozen for every later round (measured at
   HECA: 05R/23L's anchors grow 4 → 9 → 14, all flex-minted, and rounds
   1-2 at the deepest bin read slack 0.000 / move 0.000 against a 4.37 m
   deficit).  The fix tags flex-inserted samples ``flex_minted`` and
   withdraws only those from the bounding set.
2. **Non-convergence.**  Every HECA demand's binding seed is
   another flexible runway, so the origin split halves every pull; three
   fixed rounds of geometric halving leave 1/8 of the demand standing by
   construction.  The fix iterates to the 0.01 m materiality floor.
3. **DEM-follow seeding.**  A zero band seeded every profile as the
   straight CIFP chord, discarding a real, law-feasible ground sag the
   flex was then asked to re-derive from taxi feasibility.
4. The honest B2 instrument is report-only and is verified on the
   measured arm (the log line must reproduce the flex probe's
   independently computed demand accounting), not here.

Hermetic: hand-built profiles, an analytic DEM, no fixtures, no network,
no X-Plane install.
"""
from __future__ import annotations

import os
import sys

import pytest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.config import (                             # noqa: E402
    RUNWAY_DEM_FOLLOW_LAW_BAND_M,
    RUNWAY_FLEX_ENDZONE_MATERIALITY, RUNWAY_FLEX_MAX_ROUNDS,
    RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M, runway_dem_follow_band_m)

AXIS = 4130.0           # HECA 05R/23L's length, the stress case


# ═══════════════════ FIX 1 — the self-anchor lock ════════════════════


# ═══════════ FIX 1 — the minting provenance in apply_runway_flex ═════

_M_PER_DEG = 111320.0


class _Shape:
    def __init__(self, role, polygon, *, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = node_altitudes
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = True


class _Layout:

    def m_to_ll(self, x, y):
        return (30.0 + float(y) / _M_PER_DEG, 31.0 + float(x) / _M_PER_DEG)


# ═════════════ FIXES 1+2 — the two-round twin and the tail ═══════════


class TestConvergence:
    """The ÷2 split is the law; three rounds is not."""


    def test_the_cap_bounds_the_iteration(self):
        assert RUNWAY_FLEX_MAX_ROUNDS == 12
        assert RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M == 0.01

# ══════ §2a AMENDMENT — the apply-side per-segment cap ═══════════════
# Lead adjudication 2026-08-04: ``apply_runway_flex``'s verify-and-relax
# tested MAX_RUNWAY_GRADE only, so the flex was free to bake FAA END-ZONE
# (0.8 %) violations.  Measured at HECA: the profile the flex starts from
# has ZERO over-cap segments on every runway — all 17 gate-off end-zone
# violations are minted by the flex itself.  The repair is
# NO-NEW-REGRESSION: mint nothing, keep what you arrived with.


class TestApplySideSegmentCap:


    def test_materiality_floor_is_a_hundredth_of_a_point(self):
        assert RUNWAY_FLEX_ENDZONE_MATERIALITY == pytest.approx(0.0001)


# ═════════════════ FIX 3 — DEM-follow seeding ════════════════════════

_SAG_M = 9.0            # amplitude of the analytic sag
_LAT = 30.11            # HECA's latitude band
_LON = 31.40


class _Tile:
    def __init__(self, dem, lat, lon):
        self.dem = dem
        self.lat = lat
        self.lon = lon


class TestDemFollowSeeding:

    def test_the_band_is_one_law_bounded_value(self, monkeypatch):
        """ONE band, no arm: the gate and its zero-band arm are gone, and
        no env value may resurrect the straight-chord seeding."""
        monkeypatch.delenv("O4_RUNWAY_DEM_FOLLOW", raising=False)
        assert runway_dem_follow_band_m() == RUNWAY_DEM_FOLLOW_LAW_BAND_M
        monkeypatch.setenv("O4_RUNWAY_DEM_FOLLOW", "0")
        assert runway_dem_follow_band_m() == RUNWAY_DEM_FOLLOW_LAW_BAND_M
        assert RUNWAY_DEM_FOLLOW_LAW_BAND_M >= _SAG_M


# ══ CYCLE 5 — THE SELF-ANCHOR LOCK ON THE APPLY SIDE (two worlds) ═════
#
# ``docs/specs/cycle5-canyon-flex-spec.md`` fix 2.  ATTRIBUTED at HECA
# canyon (one build, the refusal ledger): every main-cap relax in
# ``apply_runway_flex``'s verify-and-relax loop — 61 of 61 on 05C/23C,
# 14 of 14 on 05R/23L — was bound by a station THE FLEX ITSELF MINTED a
# round earlier.  05R/23L bin 26 asked 1.789 m, the relax allowed
# 0.000 m, and the same bound with minted stations withdrawn allows
# 18.406 m; two such refusals RETIRE the bin, so a FALSE refusal was
# minting retirement.  Root cause: ``flex_slack_at`` (demand side)
# withdraws flex-minted samples from its bounding set as standing law,
# while apply re-solved with those same samples ANCHORED — one law, two
# spellings, and the apply side's was invented.
#
# The two worlds below are the plateau/canyon pair in miniature: the same
# CIFP thresholds, the same geometry, the same demand — but the canyon
# has been through a flex round already and carries its minted station.


