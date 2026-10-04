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


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.config import RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M

AXIS = 3000.0
HALF_W = 30.0
REF_HI = "09H/27H"          # the high runway
REF_LO = "09L/27L"          # the low one, 40 m below it
ELEV_HI = 100.0
ELEV_LO = 60.0
# The law budget between the two runways: small enough that 40 m of
# separation is infeasible, so BOTH profiles carry a real demand.
LINK_BUDGET_M = 6.0


# ── the synthetic airport ─────────────────────────────────────────────


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

    def m_to_ll(self, x, y):
        return (30.0 + float(y) / 111320.0, 31.0 + float(x) / 111320.0)


class _G:
    def __init__(self):
        self.runway_anchor = {}
        self.runway_anchor_sample = {}
        self.edges = []
        self.pos = {}


def _ring(y0, y1, n_along=6):
    """A rectangle with interior vertices along its length, so the hook's
    ``0 < t < 1`` demand filter has stations to work with."""
    xs = [AXIS * i / float(n_along) for i in range(n_along + 1)]
    return ([(x, y0) for x in xs] + [(x, y1) for x in reversed(xs)])


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


# ═════════════ TWIN 1 — the loop iterates on ACHIEVED state ══════════


# ═════════════ TWIN 2 — twice-rejected retirement ════════════════════


    # (``test_gate_off_never_retires`` lived here.  It pinned the
    # gate-off arm — no retirement ledger, three fixed rounds, the
    # refused bin re-presented every round.  That arm was DELETED with
    # ``O4_FLEX_SELF_UNLOCK`` in the build-complete-then-debug round.)


# ═════════════ TWIN 3 — the honest per-round line ════════════════════


# ═════════════ TWIN 4 — THE PARTITION IS REAL (cycle-7.5) ════════════


# ═════════════ TWIN 5 — KILLED-AT-THE-CLAMP, KNOWN ANSWER ════════════


# ═════════════ TWIN 6 — THE RESIDUAL DOES NOT DOUBLE-COUNT ═══════════


# ═════════════ TWIN 7 — THE FRAME STAMPS (binding point 3) ═══════════


# ═════════════ TWIN 8 — THE APPLY-REFUSAL REPORT (task 4) ════════════


# ═════════════ TWIN 9 — THE REPORT NEVER TRUNCATES SILENTLY ══════════


# ═════════════ the guard rails ═══════════════════════════════════════

class TestGuards:


    def test_the_floor_is_the_materiality_floor(self):
        assert RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M == 0.01

