"""Flex convergence — the twins for
``docs/specs/flex-convergence-spec.md``.

THE DEFECT (attributed in-lane, HECA composed arm, 2026-08-04 night):
``_apply_runway_flex_hook`` iterated on REQUESTED state.  ``move`` — what
the clamp chain decided to ask for — was booked as "drained" the moment a
candidate survived the greedy keep, before ``apply_runway_flex`` had been
called at all, and the round-drain convergence test then read that same
fiction.  With §2a closing the unlawful end-zone release valve, apply's
verify-and-relax refuses about half the requests, and the fiction became
load-bearing:

* the hook booked 312.76 m drained on 05L/23R where apply landed 116.52 m;
* rounds 1-11 re-presented a BIT-IDENTICAL rejected target set (05L/23R
  t=0.8990: requested 64.417 m twelve times, achieved 60.903 → 60.918,
  shortfall +3.499 m every round);
* because the round drain was requested, it never fell under the 0.01 m
  floor, so the loop always ran to the 12-round cap — 441 demands over the
  same 12 rounds against the pre-spec arm's 285.

THE FIX (spec §2/§3; STANDING LAW since the gate was retired):

1. accounting, the round-drain floor and demand re-derivation all read
   ACHIEVED state;
2. a bin whose target apply refuses TWICE is retired for the run, loudly;
3. the honest B2 line extends with a per-round requested/achieved/retired
   row.

These twins drive the REAL hook over a synthetic two-runway airport with a
stand-in ``apply_runway_flex`` whose refusal policy is the experiment.
Hermetic: hand-built geometry and profiles, no fixtures, no network, no
X-Plane install.
"""
from __future__ import annotations

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
from auto_patch import grade_graph as GG                     # noqa: E402
from auto_patch import runway_redistribute as RR             # noqa: E402
from auto_patch.canonical_points import (                    # noqa: E402
    CanonicalPointRegistry)
from auto_patch.config import (                              # noqa: E402
    RUNWAY_FLEX_MAX_ROUNDS, RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    solve as SOLVE)
from auto_patch.layout import ROLE_RUNWAY                     # noqa: E402

AXIS = 3000.0
HALF_W = 30.0
REF_HI = "09H/27H"          # the high runway
REF_LO = "09L/27L"          # the low one, 40 m below it
ELEV_HI = 100.0
ELEV_LO = 60.0
Y_HI = 0.0
Y_LO = 600.0
# The law budget between the two runways: small enough that 40 m of
# separation is infeasible, so BOTH profiles carry a real demand.
LINK_BUDGET_M = 6.0


# ── the synthetic airport ─────────────────────────────────────────────

class _Cap:
    """A grade cap that prices a leg at ``rate`` per metre."""

    def __init__(self, budget):
        self._budget = float(budget)

    def at(self, _d, _x):
        return self._budget


class _Shape:
    def __init__(self, role, polygon, ref, node_altitudes):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = list(node_altitudes)
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
        return (30.0 + float(y) / 111320.0, 31.0 + float(x) / 111320.0)


class _G:
    def __init__(self):
        self.runway_anchor = {}
        self.runway_anchor_sample = {}
        self.edges = []
        self.pos = {}


def _flat_profile(elev, n_free=7):
    """A dead-flat profile: both ends anchored (CIFP), the interior free."""
    fr = [i / float(n_free + 1) for i in range(n_free + 2)]
    return {
        'fractions': list(fr),
        'elevs': [float(elev)] * len(fr),
        'anchored': [True] + [False] * n_free + [True],
        'flex_minted': [False] * len(fr),
        'seam_t': [],
        'axis_a': (0.0, 0.0),
        'axis_d': (AXIS, 0.0),
        'axis_len2': AXIS ** 2,
        'threshold_strict_fraction': 0.0,
        'end_zone_cap': None,
        'threshold_cap': None,
        'blast_a_m': 0.0,
        'blast_b_m': 0.0,
    }


def _ring(y0, y1, n_along=6):
    """A rectangle with interior vertices along its length, so the hook's
    ``0 < t < 1`` demand filter has stations to work with."""
    xs = [AXIS * i / float(n_along) for i in range(n_along + 1)]
    return ([(x, y0) for x in xs] + [(x, y1) for x in reversed(xs)])


def _airport():
    """Two parallel runways 40 m apart in elevation, linked by a law graph
    that can only carry 6 m — so each is far outside the other's envelope
    and both carry a demand whose origin is the OTHER flexible runway."""
    shapes = []
    for (ref, elev, y0, y1) in ((REF_HI, ELEV_HI, Y_HI - HALF_W,
                                 Y_HI + HALF_W),
                                (REF_LO, ELEV_LO, Y_LO - HALF_W,
                                 Y_LO + HALF_W)):
        ring = _ring(y0, y1)
        shapes.append(_Shape(ROLE_RUNWAY, Polygon(ring + [ring[0]]), ref,
                             [elev] * len(ring)))
    profiles = {REF_HI: _flat_profile(ELEV_HI),
                REF_LO: _flat_profile(ELEV_LO)}
    layout = _Layout(shapes, profiles)

    cps = layout.canonical_points
    nodes, elev, base_hard, bucket_to_idx = [], [], [], {}
    per_shape = []
    for s in layout.shapes:
        ring = list(s.polygon.exterior.coords)
        ring_open = ring[:-1] if ring[0] == ring[-1] else ring
        idxs = []
        for k, (x, y) in enumerate(ring_open):
            b = cps.get_or_add(float(x), float(y))
            if b not in bucket_to_idx:
                bucket_to_idx[b] = len(nodes)
                nodes.append((float(x), float(y)))
                elev.append(float(s.node_altitudes[k]))
                base_hard.append(True)
            idxs.append(bucket_to_idx[b])
        per_shape.append(idxs)

    G = _G()
    for i, (x, y) in enumerate(nodes):
        G.pos[i] = (x, y)
        G.runway_anchor[i] = elev[i]
    # One link per along-station pair: the ONLY route between the two
    # runways, priced at LINK_BUDGET_M.
    hi_idx, lo_idx = per_shape
    for a, b in zip(hi_idx, lo_idx):
        G.edges.append((a, b, _Cap(LINK_BUDGET_M), None))
    # and along each runway, generously (the runway's own law is the
    # profile, not this graph).
    for idxs in per_shape:
        for a, b in zip(idxs, idxs[1:]):
            G.edges.append((a, b, _Cap(50.0), None))
    return layout, nodes, bucket_to_idx, elev, base_hard, G


# ── the stand-in apply: its refusal policy IS the experiment ──────────

def _insert(profile, t, value):
    fr, el = profile['fractions'], profile['elevs']
    an, mi = profile['anchored'], profile['flex_minted']
    for k, f in enumerate(fr):
        if abs(f - t) < 1e-3:
            el[k] = value
            if not an[k]:
                mi[k] = True
            an[k] = True
            return
    at = next((k for k, f in enumerate(fr) if f > t), len(fr))
    fr.insert(at, t)
    el.insert(at, value)
    an.insert(at, True)
    mi.insert(at, True)


def _make_apply(accept, gain=1.0):
    """``accept(ref, order, t) -> bool`` decides each target's fate;
    ``gain`` is how far an ACCEPTED target actually lands (the real
    verify-and-relax also under-delivers, it does not only refuse).  The
    profile and the runway shapes are updated exactly the way the real
    ``apply_runway_flex`` updates them, so the hook's demand re-derivation
    sees real ACHIEVED state."""
    calls = []

    def _apply(layout, demands):
        out = {}
        for ref, targets in demands.items():
            pr = layout._runway_redistributed_profiles[ref]
            targets = list(targets)
            calls.append((ref, [t for (t, _v) in targets]))
            for order, (t, v) in enumerate(sorted(targets)):
                if accept(ref, order, t):
                    before = RR._interp_profile(pr['fractions'],
                                                pr['elevs'], t)
                    _insert(pr, t, before + gain * (v - before))
            shapes = [s for s in layout.shapes
                      if s.role == ROLE_RUNWAY and s.ref == ref]
            RR._apply_profile_to_shapes(
                shapes, pr['axis_a'][0], pr['axis_a'][1],
                pr['axis_d'][0], pr['axis_d'][1], pr['axis_len2'],
                pr['fractions'], pr['elevs'])
            out[ref] = [(t, RR._interp_profile(pr['fractions'],
                                               pr['elevs'], t))
                        for (t, _v) in targets]
        return out

    _apply.calls = calls
    return _apply


def _run_hook(monkeypatch, accept, *, gate="1", gain=1.0):
    """Drive the real hook once and return (n_demands, apply, log).

    ``gate`` is accepted and IGNORED: the self-unlock + convergence law is
    standing (``O4_FLEX_SELF_UNLOCK`` was deleted in the
    build-complete-then-debug round), so there is only one arm."""
    layout, nodes, bucket_to_idx, elev, base_hard, G = _airport()
    apply = _make_apply(accept, gain=gain)
    monkeypatch.setattr(RR, "apply_runway_flex", apply)
    monkeypatch.setattr(GG, "_runway_anchors",
                        lambda *_a, **_k: None)
    log = []
    import O4_UI_Utils as UI
    monkeypatch.setattr(UI, "vprint",
                        lambda level, msg, *a, **k: log.append(str(msg)))
    n = SOLVE._apply_runway_flex_hook(layout, "TEST", nodes, bucket_to_idx,
                                      elev, base_hard, [], G)
    return n, apply, log, layout


def _rounds_run(log):
    return [ln for ln in log if "round " in ln and "requested" in ln
            and "achieved" in ln]


def _summary(log):
    return next(ln for ln in log if "runway flex (B2)" in ln)


# ═════════════ TWIN 1 — the loop iterates on ACHIEVED state ══════════

class TestAchievedStateIteration:
    """The spec's twin: a synthetic where apply rejects half."""

    @staticmethod
    def _half(ref, order, _t):
        return order % 2 == 0            # accept every other target

    def test_the_synthetic_really_does_reject_half(self, monkeypatch):
        n, apply, _log, _lay = _run_hook(monkeypatch, self._half)
        assert n > 0, "the synthetic airport must produce demands"
        assert apply.calls, "apply must have been called"

    def test_drained_equals_achieved_not_requested(self, monkeypatch):
        """THE DEFECT, inverted: the line's 'drained' term and its
        'achieved' term are now the same measurement, so they agree.  On
        requested-state booking they diverged by the whole discard (HECA:
        660.19 booked vs 317.08 landed)."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._half)
        line = _summary(log)
        drained = float(line.split(" m = ")[1].split(" drained")[0])
        achieved = float(line.split("achieved ")[1].split(" m ")[0])
        assert drained == pytest.approx(achieved, abs=1e-6)

    def test_a_wholly_refused_round_stops_the_loop(self, monkeypatch):
        """Round drain is ACHIEVED drain: an apply that refuses
        everything drains 0.00 m, which is under the materiality floor, so
        the loop stops instead of spinning to the cap."""
        _n, apply, log, _lay = _run_hook(monkeypatch,
                                         lambda *_a: False)
        line = _summary(log)
        assert "achieved-drain" in line, line
        rounds = int(line.split(" over ")[1].split(" round")[0])
        assert rounds < RUNWAY_FLEX_MAX_ROUNDS
        assert rounds <= 2, f"a refused round must end the loop: {line}"

    def test_requested_state_would_have_spun_to_the_cap(self, monkeypatch):
        """The counterfactual the fix removes: with every target refused
        the REQUESTED drain is large every round (the demand never goes
        away), so a requested-state floor could never trip.  Measured
        here off the per-round rows the honest line now prints."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False)
        rows = _rounds_run(log)
        assert rows, "the per-round line must exist"
        req = float(rows[0].split("requested ")[1].split(" m")[0])
        ach = float(rows[0].split("achieved ")[1].split(" m")[0])
        assert req > 10 * RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M
        assert ach == pytest.approx(0.0, abs=1e-9)

    def test_there_is_no_fixed_three_round_arm(self, monkeypatch):
        """The fixed-3-round loop was the gate-off arm and is GONE: the
        loop now always runs to the drain floor or ``RUNWAY_FLEX_MAX_ROUNDS``."""
        _n, apply, log, _lay = _run_hook(monkeypatch, self._half)
        line = _summary(log)
        # The loop stops on a REASON — drained, no further demand, or the
        # 12-round cap — never on a hard-coded 3.
        assert "round cap 3" not in line, line
        assert "; 0 bin(s) retired after" not in line, line


# ═════════════ TWIN 2 — twice-rejected retirement ════════════════════

class TestTwiceRejectedRetirement:
    """A refusal policy that keeps the loop ALIVE (most targets land) but
    refuses ONE station for ever — the HECA shape, where 05L/23R's end-zone
    bins were refused twelve times while other bins kept moving."""

    STUCK_T = 4.0 / 8.0         # a station the synthetic profile carries
    # Accepted targets land only part of the way, so the OTHER bins keep
    # asking for several rounds and the run outlives the retirement (the
    # HECA shape — 05C/23C was still landing metres in round 3).
    GAIN = 0.35

    @classmethod
    def _stuck_bin(cls, _ref, _order, t):
        return abs(t - cls.STUCK_T) > 1e-6

    @staticmethod
    def _refuse_all(_ref, _order, _t):
        return False

    def test_a_wholly_refused_first_round_needs_no_retirement(
            self, monkeypatch):
        """Belt and braces: when NOTHING lands, the achieved-drain floor
        ends the loop in round 1, so retirement never has to fire."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._refuse_all)
        line = _summary(log)
        assert "achieved-drain" in line, line
        assert "; 0 bin(s) retired after" in line, line

    def test_a_refused_bin_is_retired_after_exactly_two_refusals(
            self, monkeypatch):
        _n, apply, log, _lay = _run_hook(monkeypatch, self._stuck_bin,
                                         gain=self.GAIN)
        line = _summary(log)
        assert " bin(s) retired after 2 refusal(s)" in line, line
        n_ret = int(line.split("verify-and-relax); ")[1]
                    .split(" bin(s) retired")[0])
        assert n_ret > 0, line
        # Every retired bin is named, loudly.
        named = [ln for ln in log if ln.strip().startswith("[pav-builder]")
                 and "RETIRED" in ln]
        assert len(named) == n_ret
        assert all("apply refused" in ln and "not re-presented" in ln
                   for ln in named)
        # …and it retires in round 2, not later.
        assert all("retired in round 2)" in ln for ln in named), named

    def test_a_retired_bin_is_never_re_presented(self, monkeypatch):
        """The whole point: no call after the second may carry a target
        the two calls before it already refused."""
        _n, apply, _log, _lay = _run_hook(monkeypatch, self._stuck_bin,
                                          gain=self.GAIN)
        by_ref = {}
        for (ref, ts) in apply.calls:
            by_ref.setdefault(ref, []).append(set(round(t, 9) for t in ts))
        stuck = round(self.STUCK_T, 9)
        seen_after = False
        for ref, rounds in by_ref.items():
            assert len(rounds) >= 3, f"{ref} needs 3+ rounds: {rounds}"
            assert stuck in rounds[0] and stuck in rounds[1], rounds
            for k in range(2, len(rounds)):
                assert stuck not in rounds[k], (
                    f"{ref} re-presented the twice-refused bin in call {k}")
                seen_after = True
        assert seen_after, "the run must outlive the retirement"

    def test_progress_at_a_bin_resets_its_ledger(self, monkeypatch):
        """A bin that MOVES is never retired for two stale refusals
        earlier in the run — the counter is consecutive, not cumulative."""
        state = {"n": 0}

        def _refuse_then_accept(_ref, _order, _t):
            state["n"] += 1
            return state["n"] > 3       # first three refused, then all move

        _n, _apply, log, _lay = _run_hook(monkeypatch, _refuse_then_accept)
        line = _summary(log)
        n_ret = int(line.split("verify-and-relax); ")[1]
                    .split(" bin(s) retired")[0])
        moved = float(line.split(" m = ")[1].split(" drained")[0])
        assert moved > 0.0, "the later rounds must land something"
        assert n_ret <= 3, line

    # (``test_gate_off_never_retires`` lived here.  It pinned the
    # gate-off arm — no retirement ledger, three fixed rounds, the
    # refused bin re-presented every round.  That arm was DELETED with
    # ``O4_FLEX_SELF_UNLOCK`` in the build-complete-then-debug round.)


# ═════════════ TWIN 3 — the honest per-round line ════════════════════

class TestHonestPerRoundLine:

    def test_one_row_per_applying_round_with_all_three_terms(
            self, monkeypatch):
        """One row per round that reached apply, numbered from 1 (a final
        round that finds no demand at all breaks before apply and has
        nothing to report)."""
        _n, apply, log, _lay = _run_hook(
            monkeypatch, lambda _r, order, _t: order % 2 == 0)
        line = _summary(log)
        rounds = int(line.split(" over ")[1].split(" round")[0])
        rows = _rounds_run(log)
        assert 1 <= len(rows) <= rounds, (rows, line)
        for k, row in enumerate(rows, start=1):
            assert f"round {k}:" in row
            assert "requested" in row and "achieved" in row
            assert "retired" in row and "bin(s)" in row

    def test_the_per_round_rows_sum_to_the_summary(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(
            monkeypatch, lambda _r, order, _t: order % 3 != 0)
        line = _summary(log)
        rows = _rounds_run(log)
        req = sum(float(r.split("requested ")[1].split(" m")[0])
                  for r in rows)
        ach = sum(float(r.split("achieved ")[1].split(" m")[0]) for r in rows)
        assert req == pytest.approx(
            float(line.split("apply requested ")[1].split(" m")[0]),
            abs=0.02)
        assert ach == pytest.approx(
            float(line.split("achieved ")[1].split(" m ")[0]), abs=0.02)

    def test_per_runway_rows_name_their_retirements(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False)
        per_ref = [ln for ln in log
                   if (REF_HI in ln or REF_LO in ln) and "demand" in ln]
        assert per_ref
        assert all("retired" in ln and "carrying" in ln for ln in per_ref)


# ═════════════ the guard rails ═══════════════════════════════════════

class TestGuards:

    def test_the_retire_threshold_is_two(self):
        import inspect
        src = inspect.getsource(SOLVE._apply_runway_flex_hook)
        assert "_RETIRE_AFTER = 2" in src

    def test_the_floor_is_the_materiality_floor(self):
        assert RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M == 0.01

    def test_the_hook_returns_the_demand_count(self, monkeypatch):
        n, apply, _log, _lay = _run_hook(
            monkeypatch, lambda _r, order, _t: order % 2 == 0)
        assert n == sum(len(ts) for (_ref, ts) in apply.calls)
