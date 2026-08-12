# EAT anchor-rect — the pin gains the hard-anchor contradiction guard

Spec: 2026-08-11, FROZEN (Fable lead). Lane: **eatguard** (dispatch
ONLY after lanes r16geom and r17vhhh merge — shared solver files).
Pre-ship mode (docs/RULINGS.md); deviations STOP-and-report.

## Carried attribution (SQ1, interventional, lane/smallq ledger line)

KSTJ (+39-095): the `EAT_SURFACE_CEILING` pin (`[eat-anchor-rect]`,
default ON; sites: `clearance.py`, `solver_primitives.py`,
`config.py`) authors **241.8184 m into 18 junction nodes at another
runway's threshold** — 5.6 m below real 1 m-lidar ground (247.4x),
`end_elev + (0.025·D − tail)` with D_mid ≈ 321 m past the DER —
contradicting the RW35 CIFP floor anchor (247.510) by **5.692 m over
0.93–1.24 m route budgets** ⇒ 31-node final-band inversion ⇒ the
KSTJ patch is dropped from every +39-095 build.
Counterfactuals: `O4_EAT_SURFACE_CEILING=0` builds CLEAN (0
inversions; writeback clamps 118→2); `O4_BAND_SEED_EXACT=0`
identical-fail (seed-cell exonerated). The DEM and the r11
loud-fallback class are exonerated (inset 100 % valid, floor anchor
= DEM to 1 mm).

## The law

**AN EAT PIN NEVER CONTRADICTS A SENIOR HARD ANCHOR WITHIN ROUTE
BUDGET.** The seat machinery already owns exactly this guard
(`[seat-guard]`, `route_profile/solve.py` ~2608: "0 of 92 seat(s)
cap-contradict a hard runway/seam anchor within route budget") — the
EAT pin adopts the SAME predicate through the SAME implementation
(import/extend the seat-guard's check; a second spelling of the
predicate is the census-wrapper defect). Concretely: before an EAT
ceiling value pins a node, test it against every hard runway/seam
anchor reachable within the route-metric budget at the governing
grade cap; a pin that would force a contradiction (pin + cap·route <
anchor, or the mirror) is REFUSED for that node and counted in one
loud `[eat-anchor-rect]` line (nodes refused, worst shortfall,
anchor identity). Refusal is per-node, not per-rect — lawful pins in
the same rect stand. No new env flag: the guard is part of the
feature (`EAT_SURFACE_CEILING` stays the only switch).

Fold-in (standing memory item "EAT anchor-rect built, guards pending
ratification"): report — do not change — the false-EAT scoping
guards' current behaviour and the HECA −15 m pin's status under the
new guard (does the guard refuse it?), as a table for the owner's
pending ratification review.

## Tests

Twins, mutation-checked: (a) the KSTJ shape — a synthetic rect whose
regulation value contradicts a runway threshold anchor within budget
⇒ those nodes refused, siblings pinned, no inversion; (b) a lawful
EAT rect (no contradiction) pins identically to today byte-for-byte;
(c) guard-refusal line format. Directly-covering files once,
ledgered.

## Acceptance (battery LAST)

KSTJ via the harness (`--patch-only`; the `--tile` arm still refuses
on empty `default_website` — carried condition, not this round's):
**rc=0, zero band inversions, patch + sidecar written** (the SQ1
`O4_EAT_SURFACE_CEILING=0` arm's clean result, now with the feature
ON). HECA (the −15 m pin airport) + one EAT-exercising control
(HEAZ) `--patch-only`: census deltas 0 beyond the 0.01 m floor
except rows the refused pins lawfully release — quote them. Build
time: tripwire only.

## Bookkeeping

Convergence guards: cap 2, STOP on second miss; `.progress`
heartbeat. DEFERRED candidates per skip. Cross-refs: RULINGS
2026-08-11b, [[eat-anchor-rect-next]], the lane/smallq ledger line,
`[seat-guard]` (solve.py ~2608).
