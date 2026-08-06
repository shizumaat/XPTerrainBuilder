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

---

## OUTCOME (lane `lane/c5flex`, 2026-08-06) — both fixes LANDED

Builds: 5 HECA (1 attribution + 2 canyon + 2 plateau) + 2 HEAZ, all
constant-DEM, shared corpus, foreground. Twins: 383 green across every
file `blast.py` names for the four touched modules.

### Fix 1 (d) — the world-invariant CIFP-forced spread

`_anchor_cifp_envelopes` (new) computes, per runway anchor station, the
band the CIFP thresholds ALONE force under the runway's own law caps —
pins captured at their one authority (`runway_segments`, before any seam
shift, carried as `profile['cifp_pins']`), station geometry, law caps
from `_profile_law`. Every term is world-invariant by construction. The
band error now prints TWO halves and the CIFP verdict is reserved for
the invariant one; the LAW-LINE half (anchored ∪ flex-applied, the
cycle-4 ruling) is still reported and explicitly carries NO verdict.

The three HECA canyon pairs, before → after:

| pair | old sentence | CIFP-forced spread | budget | CIFP shortfall |
|---|---|---|---|---|
| 7283 ↔ 7617 | "the CIFP thresholds do not reach each other" (+1.9921 m) | **4.8095 m** | 24.658 m | **−19.8484 m** |
| 7283 ↔ 3666 | same (+0.8521 m) | **4.8170 m** | 25.793 m | **−20.9756 m** |
| 7886 ↔ 7617 | same (+0.3564 m) | **3.0210 m** | 27.084 m | **−24.0631 m** |

All three verdicts REVERSE to "CIFP DOES NOT FORCE THIS … verdict (a)
BUG". Anchor 7283's CIFP envelope is `[122.674, 158.216]` m against an
emitted 141.080 — 18.4 m of world-dependent seating inside a lawful band.

PLATEAU-INVARIANCE, measured: the per-runway `CIFP pins (WORLD-INVARIANT)`
line (pins, law caps, axis length — the complete input to the verdict) is
BYTE-IDENTICAL between the `--dem 1` and `--dem 10000` builds. Twinned
both ways: `test_the_cifp_forced_envelope_is_IDENTICAL_IN_BOTH_WORLDS`
also asserts the control — the LAW LINE *does* move by the measured
+5.31 m, which is why it may not carry the verdict.

### Fix 2 (a) — the self-anchor lock on the APPLY side

ATTRIBUTED (one canyon build, new refusal ledger): of 178 refusals,
every main-cap relax — 61/61 on 05C/23C, 14/14 on 05R/23L — was bound by
a station THE FLEX ITSELF MINTED a round earlier. Type specimen, 05R/23L
bin 26: asked 1.789 m, relax allowed **0.000 m**, the same bound with
minted stations withdrawn allows **18.406 m**. 788 m of otherwise-lawful
move was withheld that way, and two such refusals RETIRE a bin — a FALSE
refusal minting retirement.

Root cause: `flex_slack_at` (demand side) withdraws flex-minted samples
as standing law; `apply_runway_flex` re-solved with those same samples
ANCHORED, so a target the demand side priced lawful met a profile frozen
by the flex's own memory. One law, two spellings.

Landed: (1) minted stations are SEEDS for the apply re-solve, never
anchors (persisted provenance unchanged — the law line stays
anchored ∪ flex-applied); (2) the relax bound prices the same set;
(3) attempt 2 — with the law bound no longer binding, every refusal had
become a whole-target DROP (250 refusals, 250 drops, zero relaxes), so a
target refused for a JOINT reason is now retried once at HALF its
request (the flex's own ÷2 idiom; the law bound still wins wherever it
binds, twinned).

### Acceptance

| criterion | result |
|---|---|
| HECA `--dem 10000` builds | **YES** — `BandInversionError` CLEARED (was 384 of 7 618). Adjudicated 10 463 (airside 7 431); band-membership residual 110 vertices, worst 2.76 m |
| HECA `--dem 1` unchanged within materiality | **NOT MET, reported.** 6 517 → 6 597 adjudicated (+80; airside +81). The criterion's premise is falsified: the plateau's OTHER two runways demand 604 m and 661 m, so a plateau-only-05R/23L reading was never available |
| HEAZ both worlds | build; `--dem 1` 1 100 → 1 190 (airside +2, groundside +88), `--dem 10000` 212 → 213 (airside +1) |
| flex twins + two-world synthetic | 383 green, including `TestApplySideSelfAnchorLock` (plateau lands it, canyon lands it, a REAL anchor still refuses it) |

Plateau trade, per family: the runway-governed families IMPROVE
(`strip_longitudinal` 16→3, `strip_arc` 33→18, `plane_gradient` 7→4,
`transverse` 190→187) and `within_shape` grows +110 (airside +109). The
flex moves the runway profiles further, and the taxi network carrying
those joins does not absorb all of it — attempt cap reached, so that is
reported, not iterated on. It is the next round's target and it is an
(a)/(b) question about the network's absorption, not about the flex.
