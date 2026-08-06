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

import math
import os
import sys

import pytest
from shapely.geometry import Polygon

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch import runway_redistribute as RR            # noqa: E402
from auto_patch.canonical_points import (                   # noqa: E402
    CanonicalPointRegistry)
from auto_patch.config import (                             # noqa: E402
    RUNWAY_DEM_FOLLOW_LAW_BAND_M,
    RUNWAY_FLEX_ENDZONE_MATERIALITY, RUNWAY_FLEX_MAX_ROUNDS,
    RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M, runway_dem_follow_band_m)
from auto_patch.layout import ROLE_RUNWAY                    # noqa: E402
from auto_patch.pavement.runway_segments import (            # noqa: E402
    RUNWAY_END_FRACTION,
    MAX_RUNWAY_GRADE, RUNWAY_END_GRADE as RUNWAY_END_GRADE_PP)

AXIS = 4130.0           # HECA 05R/23L's length, the stress case
E_A = 136.46            # its CIFP threshold elevations
E_B = 142.43


@pytest.fixture
def unlock_on():
    """No-op: the self-unlock + convergence law is STANDING (the
    ``O4_FLEX_SELF_UNLOCK`` gate is retired).  Kept so the twins that
    assert that behaviour keep reading as "with the law in force"."""


@pytest.fixture
def unlock_off():
    """No-op, retained only for the twins below that are arm-INDEPENDENT
    (the ``flex_minted`` provenance array is maintained unconditionally,
    and always was)."""


def _chord_profile(extra=()):
    """The straight CIFP chord: thresholds anchored at both ends, a free
    interior sample at mid-length, plus any ``extra`` samples given as
    ``(t, elev, anchored, flex_minted)``."""
    rows = [(0.0, E_A, True, False),
            (0.5, (E_A + E_B) / 2.0, False, False),
            (1.0, E_B, True, False)]
    rows.extend(extra)
    rows.sort()
    return {
        'fractions': [r[0] for r in rows],
        'elevs': [r[1] for r in rows],
        'anchored': [r[2] for r in rows],
        'flex_minted': [r[3] for r in rows],
        'seam_t': [],
        'axis_len2': AXIS ** 2,
        'threshold_strict_fraction': 0.0,
    }


# ═══════════════════ FIX 1 — the self-anchor lock ════════════════════

class TestFlexMintedAnchorsDoNotBound:
    """``flex_slack_at``: a sample the flex itself minted carries no law
    authority, so it must not bound the next round."""

    # A flex-minted anchor sitting 1.0 m below the chord at t = 0.45 —
    # exactly what round 0 leaves behind at HECA.
    MINTED_T = 0.45
    MINTED_E = E_A + (E_B - E_A) * 0.45 - 1.0

    def _profile(self, minted: bool):
        return _chord_profile(
            extra=[(self.MINTED_T, self.MINTED_E, True, minted)])

    def test_gate_on_unlocks_the_station(self, unlock_on):
        """With the gate on the same profile is bounded only by the CIFP
        thresholds, so the station can move again — and by exactly the
        pairwise-envelope budget of the NEARER threshold, priced with the
        PER-SEGMENT law (lead completion (a), 2026-08-04 night): the ramp
        from threshold A crosses the 0.8 % end zone before reaching the
        1.5 % main body, so its budget is the INTEGRAL of the cap, not
        ``MAX_RUNWAY_GRADE × distance``."""
        prof = self._profile(True)
        slack = RR.flex_slack_at(prof, self.MINTED_T, -1.0)
        assert slack > 1.0
        current = RR._interp_profile(prof['fractions'], prof['elevs'],
                                     self.MINTED_T)
        # the binding threshold is A (0.45 of 4130 m away vs 0.55)
        d_a = self.MINTED_T * AXIS
        budget = ((RUNWAY_END_GRADE_PP * RUNWAY_END_FRACTION
                   + MAX_RUNWAY_GRADE * (self.MINTED_T
                                         - RUNWAY_END_FRACTION)) * AXIS)
        expected = budget - (E_A - current)
        assert slack == pytest.approx(expected, abs=1e-6)
        # THE DEFECT (a) repairs: the old all-main-cap pricing over-granted
        # this bound, and never under-grants — the completion can only ever
        # tighten where the law tightens.
        old = MAX_RUNWAY_GRADE * d_a - (E_A - current)
        assert slack < old
        assert budget >= min(RUNWAY_END_GRADE_PP, MAX_RUNWAY_GRADE) * d_a

    def test_a_real_anchor_at_the_same_station_still_freezes_it(
            self, unlock_on):
        """The gate withdraws MINTED anchors only.  The identical
        profile whose t = 0.45 anchor is NOT minted (a crossing
        reconciliation, a seam sample) keeps its zero slack."""
        slack = RR.flex_slack_at(self._profile(False), self.MINTED_T, -1.0)
        assert slack == pytest.approx(0.0, abs=1e-9)

    def test_cifp_thresholds_still_bound_under_the_gate(self, unlock_on):
        """A station 100 m inside the A threshold may still only move by
        cap x 100 m — CIFP is immovable truth (RULINGS 2026-08-04)."""
        prof = self._profile(True)
        t = 100.0 / AXIS
        current = RR._interp_profile(prof['fractions'], prof['elevs'], t)
        slack = RR.flex_slack_at(prof, t, -1.0)
        assert slack <= MAX_RUNWAY_GRADE * 100.0 - (E_A - current) + 1e-9
        assert slack < 1.6            # NOT unbounded

    def test_all_minted_profile_falls_back_to_the_full_set(self, unlock_on):
        """Pathological guard: a profile carrying nothing but minted
        anchors keeps the old bound rather than reporting free slack."""
        prof = _chord_profile()
        prof['flex_minted'] = [True] * len(prof['fractions'])
        assert RR.flex_slack_at(prof, 0.5, -1.0) == pytest.approx(
            RR.flex_slack_at(_chord_profile(), 0.5, -1.0), abs=1e-9)

    def test_absent_tag_is_the_pre_spec_behaviour(self, unlock_on):
        """A profile from before this change (no ``flex_minted`` key) is
        read as "nothing minted" — every anchor bounds, as today."""
        prof = self._profile(True)
        del prof['flex_minted']
        assert RR.flex_slack_at(prof, self.MINTED_T, -1.0) == pytest.approx(
            0.0, abs=1e-9)


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
    def __init__(self, shapes, profiles):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry()
        self.anchor = (30.0, 31.0)
        self._runway_redistributed_profiles = profiles

    def m_to_ll(self, x, y):
        return (30.0 + float(y) / _M_PER_DEG, 31.0 + float(x) / _M_PER_DEG)


def _flex_layout(profile, ref="05R/23L", half_w=30.0):
    """One runway rectangle along +x, with the profile registered."""
    poly = Polygon([(0.0, -half_w), (AXIS, -half_w),
                    (AXIS, half_w), (0.0, half_w)])
    alts = [E_A, E_B, E_B, E_A]
    shape = _Shape(ROLE_RUNWAY, poly, ref=ref, node_altitudes=alts)
    profile = dict(profile)
    profile['axis_a'] = (0.0, 0.0)
    profile['axis_d'] = (AXIS, 0.0)
    profile['axis_len2'] = AXIS ** 2
    return _Layout([shape], {ref: profile}), shape


class TestMintingProvenance:
    """``apply_runway_flex`` is the only minter, and it never launders
    real authority away."""

    def test_an_applied_target_is_tagged_minted(self, unlock_off):
        layout, _s = _flex_layout(_chord_profile())
        prof = layout._runway_redistributed_profiles["05R/23L"]
        target_t = 0.40
        before = RR._interp_profile(prof['fractions'], prof['elevs'],
                                    target_t)
        RR.apply_runway_flex(layout, {"05R/23L": [(target_t, before - 0.8)]})
        fr = prof['fractions']
        minted = prof['flex_minted']
        anch = prof['anchored']
        assert len(minted) == len(fr) == len(anch)
        k = min(range(len(fr)), key=lambda i: abs(fr[i] - target_t))
        assert anch[k] and minted[k], "the applied target is minted"
        # The CIFP thresholds keep their (non-minted) provenance.
        assert not minted[0] and not minted[-1]
        assert anch[0] and anch[-1]

    def test_a_target_landing_on_a_real_anchor_does_not_launder_it(
            self, unlock_off):
        """Placing a target on an ALREADY-anchored sample (a crossing
        reconciliation) must not mark it minted — that would silently
        strip a real anchor of its bounding power."""
        cross_t = 0.60
        cross_e = E_A + (E_B - E_A) * cross_t
        layout, _s = _flex_layout(
            _chord_profile(extra=[(cross_t, cross_e, True, False)]))
        prof = layout._runway_redistributed_profiles["05R/23L"]
        RR.apply_runway_flex(layout,
                             {"05R/23L": [(cross_t, cross_e - 0.3)]})
        k = min(range(len(prof['fractions'])),
                key=lambda i: abs(prof['fractions'][i] - cross_t))
        assert prof['anchored'][k]
        assert not prof['flex_minted'][k], "crossing authority preserved"

    def test_crossing_reconciled_vertex_clears_a_stale_mint(
            self, unlock_off):
        """A ring vertex that deviates from the profile is folded in as a
        crossing anchor.  Even where an earlier round minted that
        station, the geometric authority UPGRADES the provenance — this
        is the clause that holds CYXY's 02/20 crossing anchors."""
        cross_t = 0.30
        stale = _chord_profile(
            extra=[(cross_t, E_A + (E_B - E_A) * cross_t - 0.5, True, True)])
        layout, shape = _flex_layout(stale)
        prof = layout._runway_redistributed_profiles["05R/23L"]
        # A ring vertex at the crossing station carrying a value the
        # profile does not have (the partner runway's surface).
        x = cross_t * AXIS
        shape.polygon = Polygon([(0.0, -30.0), (x, -30.0), (AXIS, -30.0),
                                 (AXIS, 30.0), (x, 30.0), (0.0, 30.0)])
        recon = RR._interp_profile(prof['fractions'], prof['elevs'],
                                   cross_t) + 0.4
        shape.node_altitudes = [E_A, recon, E_B, E_B, recon, E_A]
        RR.apply_runway_flex(layout, {"05R/23L": [(0.7, E_B - 1.0)]})
        k = min(range(len(prof['fractions'])),
                key=lambda i: abs(prof['fractions'][i] - cross_t))
        assert prof['anchored'][k]
        assert not prof['flex_minted'][k]


# ═════════════ FIXES 1+2 — the two-round twin and the tail ═══════════

# The measured Stage-C demand at HECA's deepest 05R/23L bin (the 6907
# taxi tension): 2.672 m, of which the 3-round loop drained 2.004.
STAGE_C_DEMAND_M = 2.672


def _drive_rounds(n_rounds, *, split=2.0, target_t=0.45,
                  drop_m=STAGE_C_DEMAND_M, stop_at_floor=False):
    """Drive ``apply_runway_flex`` the way the B2 hook does: each round
    recomputes the deficit against the CURRENT profile, halves it (the
    origin split — at HECA every binding seed is another flexible
    runway, 277/277 candidates), clamps to ``flex_slack_at`` and
    applies.  Returns the per-round move list and the final residual."""
    layout, _s = _flex_layout(_chord_profile())
    prof = layout._runway_redistributed_profiles["05R/23L"]
    original = RR._interp_profile(prof['fractions'], prof['elevs'],
                                  target_t)
    wanted = original - drop_m
    moves = []
    for _r in range(n_rounds):
        current = RR._interp_profile(prof['fractions'], prof['elevs'],
                                     target_t)
        deficit = abs(wanted - current)
        if deficit <= 0.0:
            moves.append(0.0)
            continue
        pull = deficit / split
        slack = RR.flex_slack_at(prof, target_t, -1.0)
        move = min(pull, slack)
        if move <= 0.01:
            moves.append(0.0)
            if stop_at_floor:
                break
            continue
        RR.apply_runway_flex(layout,
                             {"05R/23L": [(target_t, current - move)]})
        moves.append(move)
        # the hook's own stopping rule: a round that drains less than
        # the materiality floor is the last one.
        if stop_at_floor and move < RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M:
            break
    residual = abs(wanted - RR._interp_profile(
        prof['fractions'], prof['elevs'], target_t))
    return moves, residual


class TestConvergence:
    """The ÷2 split is the law; three rounds is not."""

    def test_gate_on_round_one_moves_a_station_round_zero_touched(
            self, unlock_on):
        """The spec's twin: a synthetic two-round flex where round 1
        moves a station round 0 touched."""
        moves, _residual = _drive_rounds(2)
        assert moves[0] > 0.5
        assert moves[1] > 0.5

    def test_gate_on_eight_rounds_reach_the_materiality_floor(
            self, unlock_on):
        """Pre-registered arithmetic: the ÷2 tail on the measured
        Stage-C demand (2.672 m) reaches the 0.01 m materiality floor at
        8 rounds — exactly 2.672/2**8 = 0.01043 m, i.e. AT the floor to
        its own precision.  Reported as PASS-with-residual, never
        iterated on (CLAUDE.md item 3(a))."""
        moves, residual = _drive_rounds(8)
        assert residual == pytest.approx(STAGE_C_DEMAND_M / 2 ** 8,
                                         rel=1e-6)
        assert residual <= 1.1 * RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M
        # ... against the 3-round loop, which by construction can only
        # ever reach 1/2**3 of the demand and leaves 0.334 m standing —
        # 33x the materiality floor.  (The HECA counterfactual measured
        # 25 % left, i.e. one of its three rounds moved nothing at all.)
        _m3, r3 = _drive_rounds(3)
        assert r3 == pytest.approx(STAGE_C_DEMAND_M / 2 ** 3, rel=1e-6)
        assert r3 > 30 * RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M
        # monotone drain: each round moves less than the one before
        nz = [m for m in moves if m > 0.0]
        assert all(nz[i + 1] <= nz[i] + 1e-9 for i in range(len(nz) - 1))

    def test_gate_on_stops_itself_inside_the_hard_cap(self, unlock_on):
        """The loop's own stopping rule (round drain < the floor) trips
        well inside ``RUNWAY_FLEX_MAX_ROUNDS`` — the cap is a guard, not
        the mechanism."""
        moves, residual = _drive_rounds(RUNWAY_FLEX_MAX_ROUNDS,
                                        stop_at_floor=True)
        assert len(moves) < RUNWAY_FLEX_MAX_ROUNDS
        assert residual <= 2 * RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M

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

# The end zone is the first/last RUNWAY_END_FRACTION (0.25) of the
# length; a target at t = 0.10 pulling 4.0 m down over 413 m grades at
# 0.97 % — inside the 1.5 % MAIN cap (so the old check passes it) and
# well outside the 0.8 % end-zone cap (so §2a must not).
_EZ_T = 0.10
_EZ_DROP = 4.0


@pytest.fixture
def segcap_on():
    """No-op: §2a's apply-side per-segment cap is STANDING LAW."""


class TestApplySideSegmentCap:

    def _run(self):
        layout, _s = _flex_layout(_chord_profile())
        prof = layout._runway_redistributed_profiles["05R/23L"]
        before = RR._interp_profile(prof['fractions'], prof['elevs'], _EZ_T)
        got = RR.apply_runway_flex(
            layout, {"05R/23L": [(_EZ_T, before - _EZ_DROP)]})
        after = RR._interp_profile(prof['fractions'], prof['elevs'], _EZ_T)
        return prof, before, after, dict(got.get("05R/23L") or ())

    def test_gate_on_relaxes_it_to_the_largest_lawful_value(self,
                                                            segcap_on):
        """§2a as COMPLETED by lead ruling (b), 2026-08-04 night: the
        over-cap target is not discarded — it is relaxed to the largest
        value its station's per-segment law allows.  The end zone stays
        lawful (that is §2a, unchanged) and the airport keeps the LAWFUL
        part of a demand it is owed (that is the completion).

        The measured failure this repairs: at HECA, dropping 05L/23R's
        t=0.8990 target left the station +0.486 m where +2.531 m was
        lawful, and the 2.0 m shortfall WAS the uniform 2.8917 m final-
        band inversion."""
        _prof, before, after, _got = self._run()
        grade = abs(after - E_A) / (_EZ_T * AXIS)
        assert grade <= RUNWAY_END_GRADE_PP + 1e-9, "the end zone is law"
        # it MOVED (the completion) …
        assert after < before - 1.0
        # … but never past the request, and never past the law.
        assert after > before - _EZ_DROP
        assert grade == pytest.approx(RUNWAY_END_GRADE_PP, abs=1e-6), (
            "a relaxed target lands ON its cap, not short of it")

    def test_the_shortfall_is_visible_to_the_caller(self, segcap_on):
        """The honest instrument (fix 4) must still see it: the achieved
        value comes back SHORT of the request, which is what the B2
        line's 'discarded by verify-and-relax' term reports — now a
        partial discard (the unlawful part) rather than the whole
        target."""
        _prof, before, after, got = self._run()
        assert _EZ_T in got
        assert got[_EZ_T] == pytest.approx(after, abs=1e-6)
        assert got[_EZ_T] > (before - _EZ_DROP), "short of the request"
        # material, i.e. above the convergence materiality floor — this
        # request was very nearly lawful (3.901 of the 4.0 m it asked for),
        # so only the last 0.099 m is discarded.  Under the pre-completion
        # DROP the whole 4.0 m was.
        assert (abs(got[_EZ_T] - (before - _EZ_DROP))
                > RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M)

    def test_a_mid_runway_target_still_applies(self, segcap_on):
        """§2a bounds the END ZONE, not the flex.  A mid-runway target —
        every one of HECA 05R/23L's, at t 0.45-0.65 — is untouched."""
        layout, _s = _flex_layout(_chord_profile())
        prof = layout._runway_redistributed_profiles["05R/23L"]
        before = RR._interp_profile(prof['fractions'], prof['elevs'], 0.45)
        RR.apply_runway_flex(layout, {"05R/23L": [(0.45, before - 1.5)]})
        after = RR._interp_profile(prof['fractions'], prof['elevs'], 0.45)
        assert after == pytest.approx(before - 1.5, abs=1e-6)

    def test_a_pre_existing_violation_is_kept_not_this_rounds_job(
            self, segcap_on):
        """The 17 gate-off segments are a standing defect recorded for
        their own round.  A profile that ARRIVES over cap keeps its
        violation, and an unrelated target still applies."""
        # anchored sample at t=0.05, 3.0 m below the A threshold:
        # 1.45 % over 206.5 m — over the 0.8 % end cap, under 1.5 %.
        prof0 = _chord_profile(extra=[(0.05, E_A - 3.0, True, False)])
        layout, _s = _flex_layout(prof0)
        prof = layout._runway_redistributed_profiles["05R/23L"]
        before = RR._interp_profile(prof['fractions'], prof['elevs'], 0.45)
        RR.apply_runway_flex(layout, {"05R/23L": [(0.45, before - 1.0)]})
        assert prof['flex_endzone_ref'], "the arrival defect is recorded"
        k = min(range(len(prof['fractions'])),
                key=lambda i: abs(prof['fractions'][i] - 0.05))
        assert prof['elevs'][k] == pytest.approx(E_A - 3.0, abs=1e-6)
        after = RR._interp_profile(prof['fractions'], prof['elevs'], 0.45)
        assert after == pytest.approx(before - 1.0, abs=1e-6)

    def test_the_reference_is_absolute_across_calls(self, segcap_on):
        """35 apply calls against a per-call reference could each spend
        one materiality floor and ratchet a real violation into being.
        The snapshot is taken ONCE and never re-taken."""
        layout, _s = _flex_layout(_chord_profile())
        prof = layout._runway_redistributed_profiles["05R/23L"]
        RR.apply_runway_flex(layout, {"05R/23L": [(0.45, 138.0)]})
        ref1 = list(prof['flex_endzone_ref'])
        RR.apply_runway_flex(layout, {"05R/23L": [(0.55, 138.5)]})
        assert list(prof['flex_endzone_ref']) == ref1
        assert ref1 == [], "this profile arrived lawful"
        # ... and after two calls the end zone is still lawful: nothing
        # was minted, so nothing accumulated.
        fr, el = prof['fractions'], prof['elevs']
        for k in range(1, len(fr)):
            seg = (fr[k] - fr[k - 1]) * AXIS
            if seg <= 0.1 or not (fr[k] <= 0.25 or fr[k - 1] >= 0.75):
                continue
            assert abs(el[k] - el[k - 1]) / seg <= RUNWAY_END_GRADE_PP + 1e-9

    def test_materiality_floor_is_a_hundredth_of_a_point(self):
        assert RUNWAY_FLEX_ENDZONE_MATERIALITY == pytest.approx(0.0001)


# ═════════════════ FIX 3 — DEM-follow seeding ════════════════════════

_SAG_M = 9.0            # amplitude of the analytic sag
_LAT = 30.11            # HECA's latitude band
_LON = 31.40


class _SagDEM:
    """Analytic DEM: the CIFP chord minus a half-sine sag along the
    runway, i.e. a BROAD, law-feasible dip.  Max slope of the sag is
    ``_SAG_M·pi/AXIS`` = 0.68 %, comfortably inside the 1.5 % runway
    cap, so nothing here is asking the seeder to break law."""

    nodata = -32768

    def __init__(self, tile_lat, tile_lon, end_a_lon, end_b_lon):
        self.tile_lat = tile_lat
        self.tile_lon = tile_lon
        self.a = end_a_lon
        self.b = end_b_lon

    def alt(self, node):
        lon = float(node[0]) + self.tile_lon
        t = (lon - self.a) / (self.b - self.a)
        chord = E_A + (E_B - E_A) * t
        if t <= 0.0 or t >= 1.0:
            return chord
        return chord - _SAG_M * math.sin(math.pi * t)


class _Tile:
    def __init__(self, dem, lat, lon):
        self.dem = dem
        self.lat = lat
        self.lon = lon


def _seed_profile():
    """Run the real seeder over a single 4130 m runway on the sag DEM and
    return its persisted profile state."""
    from auto_patch.pavement import runway_segments as RS
    cos_lat = math.cos(math.radians(_LAT))
    dlon = AXIS / (_M_PER_DEG * cos_lat)
    lon_a, lon_b = _LON, _LON + dlon
    pairs = [("RW05R", {"lat": _LAT, "lon": lon_a, "elevation_m": E_A,
                        "displaced_m": 0.0},
              "RW23L", {"lat": _LAT, "lon": lon_b, "elevation_m": E_B,
                        "displaced_m": 0.0})]
    apt = {"05R": (_LAT, lon_a, 45.0, 0.0, 60.0),
           "23L": (_LAT, lon_b, 45.0, 0.0, 60.0)}
    tile = _Tile(_SagDEM(30, 31, lon_a, lon_b), 30, 31)
    _xml, _chain, state = RS.generate_patch_osm(
        "ZZZZ", pairs, tile=tile, apt_runways=apt)
    assert state, "the seeder produced no profile state"
    return next(iter(state.values()))


def _max_segment_grade(fractions, elevs, phys):
    worst = 0.0
    for i in range(1, len(fractions)):
        d = abs(fractions[i] - fractions[i - 1]) * phys
        if d > 0.5:
            worst = max(worst, abs(elevs[i] - elevs[i - 1]) / d)
    return worst


class TestDemFollowSeeding:

    def test_the_band_is_one_law_bounded_value(self, monkeypatch):
        """ONE band, no arm: the gate and its zero-band arm are gone, and
        no env value may resurrect the straight-chord seeding."""
        monkeypatch.delenv("O4_RUNWAY_DEM_FOLLOW", raising=False)
        assert runway_dem_follow_band_m() == RUNWAY_DEM_FOLLOW_LAW_BAND_M
        monkeypatch.setenv("O4_RUNWAY_DEM_FOLLOW", "0")
        assert runway_dem_follow_band_m() == RUNWAY_DEM_FOLLOW_LAW_BAND_M
        assert RUNWAY_DEM_FOLLOW_LAW_BAND_M >= _SAG_M

    def test_the_seeding_follows_the_sag_within_law(self):
        st = _seed_profile()
        phys = st['phys_dist_m']
        e0, e1 = st['elevs'][0], st['elevs'][-1]
        # the seeded centre sits within 1.0 m of the DEM sag
        mid = min(range(len(st['fractions'])),
                  key=lambda i: abs(st['fractions'][i] - 0.5))
        dem_mid = (e0 + (e1 - e0) * st['fractions'][mid]
                   - _SAG_M * math.sin(math.pi * st['fractions'][mid]))
        assert abs(st['elevs'][mid] - dem_mid) < 1.0
        # ... and the profile obeys runway grade law everywhere
        assert _max_segment_grade(st['fractions'], st['elevs'],
                                  phys) <= MAX_RUNWAY_GRADE + 1e-9

    def test_the_seeding_never_moves_a_cifp_threshold(self, monkeypatch):
        """STOP condition of the fix-3 arm, pinned as a twin: CIFP
        threshold values are immovable truth (RULINGS 2026-08-04) — the
        band shapes the INTERIOR only.

        The comparison arm is built by zeroing the BAND CONSTANT, not by
        an env gate (there is none any more): a zero band IS the straight
        chord, so every ANCHORED sample must be bit-identical between the
        two and only free interior samples may move."""
        from auto_patch.pavement import runway_segments as RS
        on = _seed_profile()
        monkeypatch.setattr(RS, "runway_dem_follow_band_m", lambda: 0.0)
        off = _seed_profile()
        for st in (off, on):
            assert st['anchored'][0] and st['anchored'][-1]
        assert on['elevs'][0] == pytest.approx(off['elevs'][0], abs=1e-9)
        assert on['elevs'][-1] == pytest.approx(off['elevs'][-1], abs=1e-9)
        off_anch = {round(f, 9): e for f, e, a
                    in zip(off['fractions'], off['elevs'], off['anchored'])
                    if a}
        on_anch = {round(f, 9): e for f, e, a
                   in zip(on['fractions'], on['elevs'], on['anchored'])
                   if a}
        assert set(off_anch) == set(on_anch)
        for f in off_anch:
            assert on_anch[f] == pytest.approx(off_anch[f], abs=1e-9)


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

_C5_MINTED_T = 0.51           # where round 0 left a minted station
_C5_DEMAND_T = 0.52           # the demand one 41 m station along
_C5_MOVE = 1.789              # the metres HECA 05R/23L bin 26 asked for


def _c5_world(*, canyon):
    """PLATEAU: the straight CIFP chord, nothing flexed yet.
    CANYON: the identical profile after a round-0 flex left a minted
    station 1.0 m below the chord at ``_C5_MINTED_T`` — the state HECA's
    canyon build is in when bin 26 is presented."""
    if not canyon:
        return _flex_layout(_chord_profile())
    minted_e = E_A + (E_B - E_A) * _C5_MINTED_T - 1.0
    return _flex_layout(_chord_profile(
        extra=[(_C5_MINTED_T, minted_e, True, True)]))


def _c5_apply(layout, t, move_down):
    prof = layout._runway_redistributed_profiles["05R/23L"]
    before = RR._interp_profile(prof['fractions'], prof['elevs'], t)
    got = dict(RR.apply_runway_flex(
        layout, {"05R/23L": [(t, before - move_down)]}).get("05R/23L") or ())
    after = RR._interp_profile(prof['fractions'], prof['elevs'], t)
    return before, after, got


class TestApplySideSelfAnchorLock:

    def test_the_plateau_proves_the_move_lawful(self):
        """The control: with no flex history, the same demand lands in
        full.  This is what "the plateau proves the lawful room exists"
        means — identical CIFP pins, identical geometry."""
        layout, _s = _c5_world(canyon=False)
        before, after, _got = _c5_apply(layout, _C5_DEMAND_T, _C5_MOVE)
        assert after == pytest.approx(before - _C5_MOVE, abs=1e-6)

    def test_the_canyon_drains_the_same_demand(self):
        """THE FIX.  The canyon world carries a flex-minted station one
        bin away.  It carries no CIFP / seam / crossing authority, so it
        may not freeze the re-solve — the demand the plateau proves
        lawful must land here too."""
        layout, _s = _c5_world(canyon=True)
        before, after, got = _c5_apply(layout, _C5_DEMAND_T, _C5_MOVE)
        assert after == pytest.approx(before - _C5_MOVE, abs=1e-6), (
            "a flex-minted station froze the apply-side re-solve: the "
            "refusal is FALSE, and two of them retire the bin")
        assert got[_C5_DEMAND_T] == pytest.approx(after, abs=1e-6)

    def test_the_demand_side_agreed_all_along(self):
        """The two sides now price ONE law: what ``flex_slack_at`` grants
        on the demand side is what the apply side can deliver.  (Before
        the fix the demand side granted this move and the apply side
        refused it — that disagreement IS the defect.)"""
        layout, _s = _c5_world(canyon=True)
        prof = layout._runway_redistributed_profiles["05R/23L"]
        slack = RR.flex_slack_at(prof, _C5_DEMAND_T, -1.0)
        assert slack > _C5_MOVE
        before, after, _got = _c5_apply(layout, _C5_DEMAND_T, _C5_MOVE)
        assert (before - after) <= slack + 1e-9

    def test_a_REAL_anchor_still_refuses_it(self):
        """The other half of the law, and the guard against over-fixing:
        the identical station marked NOT minted — a crossing
        reconciliation, a seam sample, real geometric authority — still
        binds, and the flex is still refused there.  A TRUE refusal is a
        verdict and retirement stays (spec: retirement stays; only FALSE
        refusals may not mint it)."""
        minted_e = E_A + (E_B - E_A) * _C5_MINTED_T - 1.0
        layout, _s = _flex_layout(_chord_profile(
            extra=[(_C5_MINTED_T, minted_e, True, False)]))
        before, after, _got = _c5_apply(layout, _C5_DEMAND_T, _C5_MOVE)
        assert abs(after - (before - _C5_MOVE)) > 0.5, (
            "a station with real authority must still bound the flex")

    def test_the_persisted_profile_still_carries_the_flex_line(self):
        """The withdrawal is about what may FREEZE the re-solve.  The
        PERSISTED provenance is unchanged: a flex-applied station stays
        ANCHORED and tagged, because the law line the band reader quotes
        is "anchored ∪ flex-applied" (cycle-4 ruling)."""
        layout, _s = _c5_world(canyon=True)
        prof = layout._runway_redistributed_profiles["05R/23L"]
        _c5_apply(layout, _C5_DEMAND_T, _C5_MOVE)
        pairs = {round(f, 6): (a, m) for f, a, m
                 in zip(prof['fractions'], prof['anchored'],
                        prof['flex_minted'])}
        assert pairs[round(_C5_MINTED_T, 6)] == (True, True)
        assert pairs[round(_C5_DEMAND_T, 6)] == (True, True)

    def test_the_refusal_ledger_names_the_reason(self):
        """The attribution instrument is standing, not a one-off probe:
        a refusal records which law it was made under and what the relax
        believed lawful, so the next reader never has to re-derive it."""
        layout, _s = _flex_layout(_chord_profile())
        prof = layout._runway_redistributed_profiles["05R/23L"]
        before = RR._interp_profile(prof['fractions'], prof['elevs'], _EZ_T)
        RR.apply_runway_flex(layout, {"05R/23L": [(_EZ_T,
                                                   before - _EZ_DROP)]})
        led = getattr(layout, "_flex_refusal_ledger", None) or []
        assert led, "a refused/relaxed target must leave a record"
        ev = led[0]
        assert ev["ref"] == "05R/23L"
        assert ev["kind"] in ("main_cap", "endzone_new")
        assert ev["action"] in ("relax", "drop")
        assert ev["requested_move"] == pytest.approx(_EZ_DROP, abs=1e-6)
        assert "lawful_move" in ev and "binding_was_minted" in ev
