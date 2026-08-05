# Flex convergence: the hook iterates on ACHIEVED state

Fable spec, 2026-08-04 night. Mechanism from the flex lane's composed
STOP (canon: runway-flex-completion-spec.md FINAL LANE VERDICT;
evidence scratchpad flexfix/out/): with §2a closing the unlawful
end-zone release valve, the 12-round O4_FLEX_SELF_UNLOCK arm fails
loudly (BandInversionError, 1629 nodes, UNIFORM 2.8917 m class)
because the hook's accounting DIVERGES from apply — it counted
312.76 m drained on 05L/23R where apply landed 116.52 m: the demand
loop iterates on requested state a profile never reached, re-presenting
unmet demand every round (441 vs 285 demands over the same 12).
Localizer: §2a x 3 rounds passes; x 12 breaks. BINDING: RULINGS.md;
convergence guards; timing suspended.

## The fix (rides O4_FLEX_SELF_UNLOCK — this round makes it viable)
1. ATTRIBUTE first (in-lane, offline from flexfix/out/ JSONs + one
   instrumented arm if needed): where exactly requested-vs-achieved
   diverges in the loop, and what mints the UNIFORM 2.8917 class.
2. The hook consumes apply's ACHIEVED results (fix-4 plumbing already
   returns requested/achieved/shortfall per target): accounting,
   round-drain floor, and demand re-derivation all read achieved
   state; a target rejected by verify-and-relax TWICE at the same bin
   is retired for the run (loud record) — no infinite re-present.
3. Honest B2 line extends: per-round requested/achieved/retired.

## Verification (streamlined; stress HECA, sentinel CYXY)
Gate-off byte identity 2x HECA + 1x CYXY vs the tip anchors
(122708ac… / d89b73a8…; re-pin at dispatch). Pre-registered:
1. Composed arm (SELF_UNLOCK + §2a + 12 rounds) BUILDS — zero
   BandInversionError; the 2.8917 class absent (hard).
2. End-zone table ≤ the gate-off 17/728.0 m (no §2a regression).
3. 05R/23L residual ≤ 2.0 m; per-runway achieved ≥ the 3-round arm's.
4. No new over-cap class at stress+sentinel; census both frames
   quoted vs tip defaults.
5. Twins: achieved-state iteration (a synthetic where apply rejects
   half), twice-rejected retirement, honest per-round line.
STOP: band-1 miss after one attempt; identity mismatch; any new
class; second miss. Do NOT flip the gate default — flip evidence goes
to the flip round. Worktree; no commit; deviations = STOP-and-report.
