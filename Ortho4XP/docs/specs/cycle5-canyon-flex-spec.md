# Cycle 5 — Canyon flex round (the (a)+(d) verdict on the three pairs)

**Status: BINDING.** Evidence: c5tip report (c5tip worktree,
tmp/c5tip_report.md, Job 2). The prior "LAW-half / metric-cap-topology"
classification of HECA canyon's three-pair BandInversionError is
FALSIFIED: the priced budgets are exactly cap × the walked spine length
(1.5000% — not under-priced, no unpriced relief exists on a spine);
the PLATEAU world achieves pair 2's spread at 22.66 m with 3.13 m slack
on IDENTICAL CIFP thresholds; the canyon anchor values are measurably
DEM-driven (+5.31/+6.24 m on 05R/23L joins vs plateau). Two defects:

## Fix 1 (d) FIRST — the law/ride split lies

`_anchor_law_values` reports ride −0.000/+0.040 m for values that are
5.31 m DEM-driven, and the classifier sentence "the CIFP thresholds
themselves do not reach each other … the DEM cannot be blamed" is false
for all three pairs — it routed this residual away from the flex.
Attribute the leak channel: the law line is anchored ∪ flex-applied
stations, and the flex APPLIES world-dependent targets — so DEM enters
the "law line" through lawfully-applied flex values, and/or the
anchored station set itself differs by world. Required: the instrument
must separate (i) the world-invariant CIFP-forced spread (compute it —
the plateau world is the measurement: same tool, same plan coordinates)
from (ii) everything world-dependent, and its sentence must only blame
CIFP when (i) alone exceeds the budget. This reader is the round's own
acceptance instrument — fix and twin it first (the c5solve fix-4
pattern).

## Fix 2 (a) — the flex gives up on drainable demand

Canyon 05R/23L: demanded 241.08 m, drained 15.33 m, RETIRED 8 bins
carrying 168.62 m (apply refused 1.898 m twice → retirement), stopped
at round cap 12 re-presenting the same 0.34 m; the same runway demands
0.05 m in the plateau. The plateau proves the lawful room exists.
Attribute WHY apply_runway_flex's verify-relax refuses the requested
moves in the canyon (which law it believes is violated, and whether
that belief is true — a false refusal is the bug; a true refusal means
the REQUEST is malformed, e.g. targets derived from DEM-ridden
envelope values that overshoot slack). Then fix at the attributed
site. Constraints: CIFP pins absolute; runway grade caps + priced
slack are the only bounds (owner flex ruling — no new caps, no budget
resurrection); retirement stays (a TRUE refusal twice is a verdict)
but a FALSE refusal may not mint retirement.

## Acceptance

- Fixed instrument's read on the three pairs, before/after (the
  world-invariant CIFP-forced spread quoted per pair).
- HECA --dem 10000 through the harness: the BandInversionError class
  is expected to CLEAR (the plateau proves feasibility); if a residual
  survives, the fixed instrument classifies it and the report quotes
  it — no re-cap, no quarantine, no "law shortfall" language unless
  the CIFP-forced spread alone exceeds the budget.
- HECA --dem 1 unchanged within materiality (the plateau flex demands
  0.05 m — a fix that moves the plateau surface >0.01 m is suspect);
  HEAZ sentinel both worlds.
- Flex twins (test_flex_convergence, test_runway_flex_completion,
  test_final_band_inversion) green; new twin: a two-world synthetic
  where the flex must drain a canyon-only demand the plateau proves
  lawful.
- The extended tracer (--dem, --inverted-pairs) is available in the
  c5tip worktree's tree for route verification.

Budget: ~4-6 HECA/HEAZ constant-DEM builds + twins. Materiality
0.01 m; attempt cap 2 per fix; heartbeat; foreground builds only;
no real-DEM; no shared-repo writes.
