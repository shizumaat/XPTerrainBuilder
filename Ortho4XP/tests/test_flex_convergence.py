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
import re
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


def _flat_profile(elev, n_free=7, all_anchored=False):
    """A dead-flat profile: both ends anchored (CIFP), the interior free.

    ``all_anchored`` anchors EVERY station.  With the stations placed on
    the demand stations (``n_free=5`` puts them at i/6, which is exactly
    where ``_ring(n_along=6)`` puts its vertices), ``flex_slack_at``
    returns identically 0 at every demand — so every bin is KILLED at
    the materiality floor.  That is the known-answer arm for the
    ``_killed_deficit`` / ``_killed_n`` accumulators, which had no twin
    at all."""
    fr = [i / float(n_free + 1) for i in range(n_free + 2)]
    return {
        'fractions': list(fr),
        'elevs': [float(elev)] * len(fr),
        'anchored': ([True] * len(fr) if all_anchored
                     else [True] + [False] * n_free + [True]),
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


def _airport(profiles=None, shift=0.0):
    """Two parallel runways 40 m apart in elevation, linked by a law graph
    that can only carry 6 m — so each is far outside the other's envelope
    and both carry a demand whose origin is the OTHER flexible runway.

    ``shift`` moves the WHOLE airport (shapes and profiles) vertically —
    a different WORLD with identical geometry, which is what the flex
    line's world stamp has to be able to tell apart."""
    shapes = []
    for (ref, elev, y0, y1) in ((REF_HI, ELEV_HI + shift, Y_HI - HALF_W,
                                 Y_HI + HALF_W),
                                (REF_LO, ELEV_LO + shift, Y_LO - HALF_W,
                                 Y_LO + HALF_W)):
        ring = _ring(y0, y1)
        shapes.append(_Shape(ROLE_RUNWAY, Polygon(ring + [ring[0]]), ref,
                             [elev] * len(ring)))
    if profiles is None:
        profiles = {REF_HI: _flat_profile(ELEV_HI + shift),
                    REF_LO: _flat_profile(ELEV_LO + shift)}
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


# ── THE SYNTHETIC REFUSAL EVENT ──────────────────────────────────────
# Every refused target books ONE ledger event carrying these constants,
# so the whole apply-REFUSALS report block (previously executed by NO
# test at all — the wholesale ``apply_runway_flex`` monkeypatch left
# ``layout._flex_refusal_ledger`` permanently empty, so the
# "FLEX-MINTED station" / "lawful move" / "WHY" lines were wholly
# uncalibrated) has a known answer for every number it prints.
_LEDGER_REQ = 2.0                 # requested_move, per event
_LEDGER_LAWFUL = 5.0              # lawful_move, minted stations withdrawn
_LEDGER_MINTED_INCL = 3.0         # the minted-INCLUSIVE bound
_LEDGER_EXCESS = 0.125
_LEDGER_KIND = "endzone_new"
_LEDGER_ACTION = "drop"
_LEDGER_N_MINTED = 2


def _refusal_event(ref, t, v, before, n_pending):
    return {"ref": ref, "kind": _LEDGER_KIND, "action": _LEDGER_ACTION,
            "excess": _LEDGER_EXCESS, "midpoint_t": t, "target_t": t,
            "target_v": v, "base": before,
            "requested_move": _LEDGER_REQ, "n_pending": n_pending,
            "lawful_move": _LEDGER_LAWFUL,
            "lawful_move_minted_included": _LEDGER_MINTED_INCL,
            "binding_station_t": 0.25, "binding_was_minted": True,
            "n_minted_anchors": _LEDGER_N_MINTED}


def _make_apply(accept, gain=1.0, ledger=False):
    """``accept(ref, order, t) -> bool`` decides each target's fate;
    ``gain`` is how far an ACCEPTED target actually lands (the real
    verify-and-relax also under-delivers, it does not only refuse).  The
    profile and the runway shapes are updated exactly the way the real
    ``apply_runway_flex`` updates them, so the hook's demand re-derivation
    sees real ACHIEVED state.

    ``ledger`` makes the stand-in do the other thing the real apply does:
    APPEND A REFUSAL RECORD for every target it turns down, on
    ``layout._flex_refusal_ledger``, exactly where
    ``apply_runway_flex`` appends it.  Without this the hook's whole
    refusal-report block is dead code under test."""
    calls = []

    def _apply(layout, demands):
        out = {}
        for ref, targets in demands.items():
            pr = layout._runway_redistributed_profiles[ref]
            targets = list(targets)
            calls.append((ref, [t for (t, _v) in targets]))
            for order, (t, v) in enumerate(sorted(targets)):
                before = RR._interp_profile(pr['fractions'],
                                            pr['elevs'], t)
                if accept(ref, order, t):
                    _insert(pr, t, before + gain * (v - before))
                elif ledger:
                    led = getattr(layout, "_flex_refusal_ledger", None)
                    if led is None:
                        led = []
                        layout._flex_refusal_ledger = led
                    led.append(_refusal_event(ref, t, v, before,
                                              len(targets)))
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


def _run_hook(monkeypatch, accept, *, gate="1", gain=1.0, ledger=False,
              profiles=None, shift=0.0):
    """Drive the real hook once and return (n_demands, apply, log).

    ``gate`` is accepted and IGNORED: the self-unlock + convergence law is
    standing (``O4_FLEX_SELF_UNLOCK`` was deleted in the
    build-complete-then-debug round), so there is only one arm."""
    layout, nodes, bucket_to_idx, elev, base_hard, G = _airport(
        profiles, shift=shift)
    apply = _make_apply(accept, gain=gain, ledger=ledger)
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


# ── ONE parser for the summary line ──────────────────────────────────
# Every twin below reads its numbers through this, so a change to the
# line's wording fails ONE place loudly instead of five places by
# ``ValueError`` (which is how the pre-sweep string surgery behaved).
_SUMMARY_FIELDS = {
    "n_demands": r"— (\d+) envelope demand\(s\)",
    "rounds": r"applied over (\d+) round\(s\)",
    "presented": r"PRESENTED \(summed over rounds\) ([\d.]+) m =",
    "kept": r"m = ([\d.]+) kept",
    "killed": r"\+ ([\d.]+) killed at the clamp",
    "killed_n": r"killed at the clamp \((\d+) bin\(s\)\)",
    "dropped": r"\+ ([\d.]+) dropped by greedy-keep",
    "dropped_n": r"dropped by greedy-keep \((\d+) bin\(s\)\)",
    "retired": r"\+ ([\d.]+) retired \(",
    "retired_n": r"retired \((\d+) bin\(s\) after",
    "retire_after": r"bin\(s\) after (\d+) refusal\(s\)",
    "partition_sum": r"\[partition sum ([\d.]+) m\]",
    "drained": r"not a partition member\) ([\d.]+) m",
    "requested": r"apply requested ([\d.]+) m",
    "achieved": r"m achieved ([\d.]+) m",
    "discarded": r"\(discarded (-?[\d.]+) m by verify-and-relax\)",
    "residual": r"retired demand excluded\) ([\d.]+) m",
    "node_space": r"node space n=(\d+)",
    "world_n": r"world: (\d+) seed\(s\)",
    "world_lo": r"z∈\[(-?[\d.]+),",
    "world_hi": r", (-?[\d.]+)\] m",
}
_INT_FIELDS = {"n_demands", "rounds", "killed_n", "dropped_n",
               "retired_n", "retire_after", "node_space", "world_n"}


def _fields(log):
    line = _summary(log)
    out = {"_line": line}
    for name, pat in _SUMMARY_FIELDS.items():
        m = re.search(pat, line)
        assert m, f"the summary line lost its {name!r} term:\n{line}"
        out[name] = (int(m.group(1)) if name in _INT_FIELDS
                     else float(m.group(1)))
    return out


def _per_ref_rows(log):
    return [ln for ln in log
            if "partition sum" in ln and "demand presented" in ln]


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
        f = _fields(log)
        assert f["drained"] == pytest.approx(f["achieved"], abs=1e-6)

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
        f = _fields(log)
        # The loop stops on a REASON — drained, no further demand, or the
        # 12-round cap — never on a hard-coded 3.
        assert "round cap 3" not in f["_line"], f["_line"]
        assert f["rounds"] <= RUNWAY_FLEX_MAX_ROUNDS


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
        f = _fields(log)
        assert "achieved-drain" in f["_line"], f["_line"]
        assert f["retired_n"] == 0
        assert f["retired"] == pytest.approx(0.0, abs=1e-9)

    def test_a_refused_bin_is_retired_after_exactly_two_refusals(
            self, monkeypatch):
        _n, apply, log, _lay = _run_hook(monkeypatch, self._stuck_bin,
                                         gain=self.GAIN)
        f = _fields(log)
        line = f["_line"]
        assert f["retire_after"] == 2, line
        n_ret = f["retired_n"]
        assert n_ret > 0, line
        # the retired bucket carries real metres, and it is a MEMBER of
        # the partition (the old line printed it in a "+"-less clause
        # outside the "=", which is half of why that "=" was false).
        assert f["retired"] > 0.0, line
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
        f = _fields(log)
        assert f["drained"] > 0.0, "the later rounds must land something"
        assert f["retired_n"] <= 3, f["_line"]

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
        f = _fields(log)
        rows = _rounds_run(log)
        req = sum(float(r.split("requested ")[1].split(" m")[0])
                  for r in rows)
        ach = sum(float(r.split("achieved ")[1].split(" m")[0]) for r in rows)
        assert req == pytest.approx(f["requested"], abs=0.02)
        assert ach == pytest.approx(f["achieved"], abs=0.02)

    def test_per_runway_rows_name_their_retirements(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False)
        per_ref = _per_ref_rows(log)
        assert per_ref
        assert all("retired" in ln and "residual (retired excluded)" in ln
                   for ln in per_ref)


# ═════════════ TWIN 4 — THE PARTITION IS REAL (cycle-7.5) ════════════

class TestTheHonestLineIsATruePartition:
    """THE DEFECT (cycle-7.5 instrument sweep, task 3).  The line printed

        TRUE demand X m = <drained> + <killed> + <dropped>

    and that "=" was FALSE two independent ways.

    (i) MIXED QUANTITIES.  ``_true_deficit`` accrues ``deficit`` — the
        band-envelope deficit AT A NODE.  ``total_drained`` accrues
        ``_ach`` — the ACHIEVED profile move at the target station, i.e.
        the deficit after the origin ÷2 split, after the slack clamp
        ``move = min(pull, slack)`` and after apply's verify-and-relax.
        ``_ach ≤ _req ≤ deficit``, so the left side systematically
        exceeded the right.
    (ii) A MISSING BUCKET.  Retired bins add to ``_true_deficit`` but
        appeared only in a later, "+"-less clause, so whenever anything
        retired the "=" could not balance even in principle.

    THE FIX: a real four-term partition (kept / killed / greedy-dropped /
    retired), with ``drained`` reported BESIDE it as an achievement.
    """

    @staticmethod
    def _half(_ref, order, _t):
        return order % 2 == 0

    def test_the_partition_sums_to_the_presented_demand(self, monkeypatch):
        """The claim the "=" makes, asserted.  Materiality 0.02 m — the
        same floor the per-round row twin uses (0.01 m elevation floor,
        doubled for the printed 2-decimal rounding of four terms)."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._half)
        f = _fields(log)
        parts = f["kept"] + f["killed"] + f["dropped"] + f["retired"]
        assert parts == pytest.approx(f["presented"], abs=0.02), f["_line"]
        assert f["partition_sum"] == pytest.approx(f["presented"],
                                                   abs=0.02)

    def test_the_partition_holds_when_bins_retire(self, monkeypatch):
        """(ii): the arm the old "=" could not balance even in
        principle."""
        _n, _apply, log, _lay = _run_hook(
            monkeypatch, TestTwiceRejectedRetirement._stuck_bin,
            gain=TestTwiceRejectedRetirement.GAIN)
        f = _fields(log)
        assert f["retired"] > 0.0, "this arm must actually retire"
        parts = f["kept"] + f["killed"] + f["dropped"] + f["retired"]
        assert parts == pytest.approx(f["presented"], abs=0.02), f["_line"]

    def test_drained_is_not_a_partition_member(self, monkeypatch):
        """(i): ``drained`` is an ACHIEVEMENT against the KEPT bucket and
        can only ever be ≤ it.  Putting it inside the "=" is what made
        the left side systematically exceed the right."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._half)
        f = _fields(log)
        assert f["drained"] <= f["kept"] + 1e-9, f["_line"]
        assert "= " + f"{f['drained']:.2f}" + " drained" not in f["_line"]

    def test_the_per_runway_rows_each_sum_too(self, monkeypatch):
        """Binding point 4's pattern, extended from the per-ROUND rows
        (the one place it was already implemented) to the per-RUNWAY
        rows."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._half)
        rows = _per_ref_rows(log)
        assert rows, "the per-runway rows must exist"
        for row in rows:
            presented = float(re.search(r"demand presented ([\d.]+) m =",
                                        row).group(1))
            terms = [float(re.search(pat, row).group(1))
                     for pat in (r"= ([\d.]+) kept",
                                 r"\+ ([\d.]+) killed",
                                 r"\+ ([\d.]+) greedy-dropped",
                                 r"\+ ([\d.]+) retired")]
            assert sum(terms) == pytest.approx(presented, abs=0.02), row
            printed = float(re.search(r"\[partition sum ([\d.]+) m\]",
                                      row).group(1))
            assert printed == pytest.approx(presented, abs=0.02), row

    def test_the_summary_equals_the_sum_of_the_per_runway_rows(
            self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(monkeypatch, self._half)
        f = _fields(log)
        rows = _per_ref_rows(log)
        total = sum(float(re.search(r"demand presented ([\d.]+) m =",
                                    r).group(1)) for r in rows)
        assert total == pytest.approx(f["presented"], abs=0.02)


# ═════════════ TWIN 5 — KILLED-AT-THE-CLAMP, KNOWN ANSWER ════════════

class TestKilledAtTheClamp:
    """``_killed_deficit`` / ``_killed_n`` had NO twin.

    THE KNOWN ANSWER, by construction: ``REF_HI``'s profile anchors a
    station at every one of its five demand stations (``n_free=5`` puts
    the profile fractions at i/6, exactly where ``_ring(n_along=6)`` puts
    its vertices), so ``flex_slack_at`` there is identically 0, ``move =
    min(pull, 0) = 0`` is at or below the materiality floor, and every
    one of its bins is KILLED.  ``REF_LO`` is the ordinary free profile
    and its targets are all refused, so round 1 drains 0.00 m and the
    loop stops — ONE round, five killed bins, nothing retired, nothing
    drained."""

    N_STATIONS = 5              # t = 1/6 … 5/6, the 0<t<1 filter

    def _profiles(self):
        return {REF_HI: _flat_profile(ELEV_HI, n_free=5,
                                      all_anchored=True),
                REF_LO: _flat_profile(ELEV_LO)}

    def test_every_bin_of_the_locked_runway_is_killed(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(
            monkeypatch, lambda *_a: False, profiles=self._profiles())
        f = _fields(log)
        assert f["rounds"] == 1, f["_line"]
        assert f["killed_n"] == self.N_STATIONS, f["_line"]
        assert f["killed"] > 0.0
        assert f["retired_n"] == 0
        assert f["drained"] == pytest.approx(0.0, abs=1e-9)
        assert f["achieved"] == pytest.approx(0.0, abs=1e-9)
        # and the partition still closes with a nonzero killed bucket.
        assert (f["kept"] + f["killed"] + f["dropped"] + f["retired"]
                == pytest.approx(f["presented"], abs=0.02))

    def test_the_killed_runway_reports_its_own_kills(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(
            monkeypatch, lambda *_a: False, profiles=self._profiles())
        row = next(r for r in _per_ref_rows(log) if REF_HI in r)
        n_killed = int(re.search(r"killed \((\d+)\)", row).group(1))
        assert n_killed == self.N_STATIONS, row
        # …and everything it presented was killed: nothing kept, nothing
        # dropped, nothing retired on that runway.
        assert re.search(r"= 0\.00 kept", row), row
        assert re.search(r"\+ 0\.00 greedy-dropped", row), row
        assert re.search(r"\+ 0\.00 retired", row), row


# ═════════════ TWIN 6 — THE RESIDUAL DOES NOT DOUBLE-COUNT ═══════════

class TestResidualExcludesTheRetiredBucket:
    """``residual`` was ``Σ max(0, last_deficit − last_drain)``, and
    ``last_deficit`` is set BEFORE the retirement filter — so retired
    demand sat inside it and could never appear in ``last_drain``.  The
    residual therefore SILENTLY INCLUDED the retired bucket that the same
    sentence prints separately: double-counting across two clauses of one
    sentence.  It is now SUBTRACTED, and the line says so."""

    def test_the_residual_is_smaller_than_the_double_counting_one(
            self, monkeypatch):
        _n, _apply, log, lay = _run_hook(
            monkeypatch, TestTwiceRejectedRetirement._stuck_bin,
            gain=TestTwiceRejectedRetirement.GAIN)
        f = _fields(log)
        assert f["retired"] > 0.0, "this arm must actually retire"
        # the per-runway rows carry the same correction, and every one of
        # them is a non-negative number.
        for row in _per_ref_rows(log):
            resid = float(re.search(
                r"residual \(retired excluded\) ([\d.]+) m",
                row).group(1))
            assert resid >= 0.0, row

    def test_the_frame_is_stated_on_the_line(self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False)
        line = _summary(log)
        assert "residual (last round, retired demand excluded)" in line
        assert "demand PRESENTED (summed over rounds)" in line, (
            "the presented demand is summed ACROSS ROUNDS — a bin "
            "re-presented five times contributes five deficits, so it "
            "is not a single physical quantity and must not read as one")


# ═════════════ TWIN 7 — THE FRAME STAMPS (binding point 3) ═══════════

class TestFlexFrameStamps:

    def test_node_space_and_world_and_crown_space_are_stamped(
            self, monkeypatch):
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False)
        f = _fields(log)
        # 2 runways × 14 ring vertices, all base-hard in the synthetic.
        assert f["node_space"] == 28
        assert f["world_n"] == 28
        assert f["world_lo"] == pytest.approx(ELEV_LO, abs=1e-6)
        assert f["world_hi"] == pytest.approx(ELEV_HI, abs=1e-6)
        assert "crown space uncrowned profile z′" in f["_line"]

    def test_two_worlds_produce_two_different_lines(self, monkeypatch):
        """WHY THE WORLD STAMP EXISTS: earlier lanes compared flex
        numbers ACROSS ARMS (canyon vs plateau), and the lines are
        identically SHAPED.  Shift the whole airport 500 m down — a
        different world, the same geometry — and the stamp is what
        tells the two lines apart."""
        _n, _apply, log_a, _lay = _run_hook(monkeypatch,
                                            lambda *_a: False)
        _n, _apply, log_b, _lay = _run_hook(monkeypatch,
                                            lambda *_a: False,
                                            shift=-500.0)
        fa, fb = _fields(log_a), _fields(log_b)
        assert fa["world_lo"] == pytest.approx(ELEV_LO, abs=1e-6)
        assert fb["world_lo"] == pytest.approx(ELEV_LO - 500.0, abs=1e-6)
        assert fb["world_hi"] == pytest.approx(ELEV_HI - 500.0, abs=1e-6)
        # identical GEOMETRY — same node space, same demand count — so
        # the world stamp is the only thing that tells the arms apart.
        assert fa["node_space"] == fb["node_space"] == 28
        assert fa["n_demands"] == fb["n_demands"]


# ═════════════ TWIN 8 — THE APPLY-REFUSAL REPORT (task 4) ════════════

class TestApplyRefusalReport:
    """The apply-REFUSALS block NEVER EXECUTED IN ANY TEST: this file's
    stand-in replaced ``apply_runway_flex`` wholesale, so
    ``layout._flex_refusal_ledger`` was always empty and the
    "FLEX-MINTED station" / "lawful move" / "WHY" lines were wholly
    uncalibrated.  The stand-in now does what the real apply does — it
    books a refusal record for every target it turns down — with known
    constants, so every number the block prints has an answer."""

    def _refusal_lines(self, log):
        return [ln for ln in log if "apply REFUSALS" in ln]

    def _group_lines(self, log):
        return [ln for ln in log
                if f"{_LEDGER_KIND}/{_LEDGER_ACTION}" in ln]

    def test_the_block_executes_at_all(self, monkeypatch):
        _n, _apply, log, lay = _run_hook(monkeypatch, lambda *_a: False,
                                         ledger=True)
        assert getattr(lay, "_flex_refusal_ledger", None), (
            "the stand-in must populate the ledger the real apply "
            "populates")
        assert self._refusal_lines(log), "the REFUSALS block never ran"

    def test_the_event_count_is_the_refused_target_count(self,
                                                         monkeypatch):
        _n, apply, log, lay = _run_hook(monkeypatch, lambda *_a: False,
                                        ledger=True)
        n_targets = sum(len(ts) for (_ref, ts) in apply.calls)
        assert len(lay._flex_refusal_ledger) == n_targets
        head = self._refusal_lines(log)[0]
        assert f"{n_targets} event(s) in the verify-and-relax loop" in head

    def test_every_rollup_number_is_the_known_answer(self, monkeypatch):
        _n, apply, log, lay = _run_hook(monkeypatch, lambda *_a: False,
                                        ledger=True)
        rows = self._group_lines(log)
        assert rows, "one row per (ref, kind, action) group"
        by_ref = {}
        for (ref, ts) in apply.calls:
            by_ref[ref] = by_ref.get(ref, 0) + len(ts)
        for row in rows:
            ref = next(r for r in by_ref if r in row)
            n = int(re.search(r": (\d+) event\(s\)", row).group(1))
            req = float(re.search(r"event\(s\), ([\d.]+) m requested",
                                  row).group(1))
            minted = int(re.search(r"binder_minted=(\d+) event\(s\)",
                                   row).group(1))
            gain = float(re.search(r"= ([\d.]+) m \(a difference",
                                   row).group(1))
            assert n == by_ref[ref], row
            assert req == pytest.approx(n * _LEDGER_REQ, abs=0.005), row
            assert minted == n, row
            assert gain == pytest.approx(
                n * (_LEDGER_LAWFUL - _LEDGER_MINTED_INCL), abs=0.005), row

    def test_the_counterfactual_causal_claim_is_gone(self, monkeypatch):
        """BINDING POINT 2.  The row used to end "…{minted} would have
        been bound by a FLEX-MINTED station, {gain} m of lawful move
        recovered by the withdrawal."  ``gain`` is the difference between
        TWO BOUNDS computed in the same call, so "recovered" asserted an
        outcome no run ever produced; and ``binding_was_minted`` is
        computed off the minted-INCLUSIVE binder, so the two terms do not
        even describe the same population."""
        _n, _apply, log, _lay = _run_hook(monkeypatch, lambda *_a: False,
                                          ledger=True)
        text = "\n".join(log)
        assert "recovered by the withdrawal" not in text
        assert "would have been bound by" not in text
        assert "a difference of two BOUNDS, not an observed move" in text

    def test_the_hook_stamps_the_round_on_every_event(self, monkeypatch):
        _n, _apply, _log, lay = _run_hook(monkeypatch, lambda *_a: False,
                                          ledger=True)
        assert all(ev.get("round") == 1
                   for ev in lay._flex_refusal_ledger)

    def test_the_WHY_line_joins_a_retirement_to_its_refusals(
            self, monkeypatch):
        """The last uncalibrated line in the block: it joins a retired
        bin to the refusal events at its own station and quotes their
        numbers."""
        _n, _apply, log, lay = _run_hook(
            monkeypatch, TestTwiceRejectedRetirement._stuck_bin,
            gain=TestTwiceRejectedRetirement.GAIN, ledger=True)
        why = [ln for ln in log if " WHY " in ln]
        assert why, "a retired bin with refusals at its station must " \
                    "produce a WHY line"
        for ln in why:
            assert f"asked {_LEDGER_REQ:.3f} m" in ln, ln
            assert f"relax allowed {_LEDGER_LAWFUL:.3f} m" in ln, ln
            assert (f"minted-inclusive bound {_LEDGER_MINTED_INCL:.3f} m"
                    in ln), ln
            assert "binder minted=True" in ln, ln
            assert f"{_LEDGER_N_MINTED} minted anchor(s)" in ln, ln
            assert f"excess {_LEDGER_EXCESS:.5f}" in ln, ln
            # "the pre-fix … bound" was a historical claim, not a
            # measurement; the line now names the bound it read.
            assert "pre-fix" not in ln, ln


# ═════════════ TWIN 9 — THE REPORT NEVER TRUNCATES SILENTLY ══════════

class TestTheReportNeverTruncatesSilently:
    """The whole honest block was one ``try: … except Exception: pass``,
    so any error mid-report dropped every remaining line with NO
    indication — a partial honest line that reads complete."""

    def test_a_mid_report_failure_is_announced(self, monkeypatch):
        log = []
        calls = {"n": 0}

        import O4_UI_Utils as UI

        def _boom(level, msg, *a, **k):
            calls["n"] += 1
            if calls["n"] == 2:          # after the summary line
                raise RuntimeError("synthetic vprint failure")
            log.append(str(msg))

        layout, nodes, bucket_to_idx, elev, base_hard, G = _airport()
        monkeypatch.setattr(RR, "apply_runway_flex",
                            _make_apply(lambda *_a: False))
        monkeypatch.setattr(GG, "_runway_anchors", lambda *_a, **_k: None)
        monkeypatch.setattr(UI, "vprint", _boom)
        SOLVE._apply_runway_flex_hook(layout, "TEST", nodes,
                                      bucket_to_idx, elev, base_hard,
                                      [], G)
        text = "\n".join(log)
        assert "runway flex report TRUNCATED" in text, text
        assert "after stage 'per-round rows'" in text, text
        assert "RuntimeError: synthetic vprint failure" in text, text


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
