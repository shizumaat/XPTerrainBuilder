# Runway flex completion: unlock the self-anchor, converge, seed the dip

Fable spec, 2026-08-04 evening. From the flex-probe attribution
(scratchpad flexprobe/out/ — the clamp table, the anchored-sample
inventory, the Stage-C counterfactual, HECA_flexprobe.json; read
first). Lines against a56cd0e. BINDING: docs/RULINGS.md (runway flex
law: CIFP immovable, profiles flex within grade law; streamlined lane
verification — STRESS AIRPORT: HECA, sentinel CYXY; no
degradation-shield interims). Resolves seed-fix open item (b) and is
the precondition for O4_BAND_SEED_COMPLETE's default flip.

## Mechanism (probe-attributed, interventional)

B2 drains only 25% of true demand at HECA. Three defects + one
upstream cause, each measured:
1. **The self-anchor lock.** apply_runway_flex inserts every applied
   target as anchored=True (runway_redistribute.py:1455/:1464,
   persisted :1508); flex_slack_at bounds against ALL anchored samples,
   so a station the flex touched in round 0 has slack ≡ 0 (cap·0) in
   every later round. 05R/23L's anchors grow 4→9→14 (05C/23C 4→48→54),
   every new one flex-minted, dead center. Rounds 1-2 at the 6907 bin:
   slack 0.000, move 0.000. HECA has NO crossing runways and NO tile
   seam — the only legitimate bounds are the 4 CIFP-derived samples
   within 63 m of the ends.
2. **÷2-split x 3-round non-convergence.** Every HECA demand's binding
   seed is another flexible runway (277/277), so every pull is halved;
   3 rounds of geometric halving leave 25% unmet even in the Stage-C
   counterfactual (measured: 2.004 of 2.672 m).
3. **Dishonest instrument.** The B2 log under-reports demand 45%
   (candidates killed at move<=0.01 skip the accumulators: true
   2380.07 m, logged 1310.60) and over-reports achievement
   (apply_runway_flex's verify-and-relax silently discards 9.89 of
   333.17 m requested).
4. **Upstream: the discarded dip.** RUNWAY_DEM_FOLLOW_BAND_M = 0.0
   (config.py:1285) seeds every profile as the straight CIFP chord
   (05R/23L measured 0.031 m worst deviation from chord). The real
   ground has a broad LAW-FEASIBLE sag — min 129.76 at t=0.510,
   8.64 m below the chord, max segment 1.27% vs the 1.5% cap — which
   the owner confirmed is physically real. The flex is asked to
   re-derive from taxi feasibility a shape the seeder threw away.

## The fixes

1. **Flex-minted anchors do not bound** (gate O4_FLEX_SELF_UNLOCK,
   default "0"). apply_runway_flex tags inserted samples
   flex_minted=True (persisted); flex_slack_at excludes flex-minted
   samples from the bounding set. CIFP thresholds, physical ends, and
   tile-seam samples keep bounding; crossing-reconciliation anchors
   keep bounding until Stage C (CYXY is the only baseline airport with
   a crossing runway — out of scope here, do NOT touch crossing
   handling). Twin: a synthetic two-round flex where round 1 moves a
   station round 0 touched.
2. **Converge to mutual feasibility** (same gate). Keep the
   snapshot-simultaneous rounds and the origin split, but iterate
   until round drain < 0.01 m or a hard cap of 12 rounds; the ÷2
   split's geometric tail then converges (pre-reg: the 6907 bin's
   Stage-C arithmetic drains fully at <=8 rounds). The greedy-keep,
   slack clamp, displacement budget (4.0 m), and tiered threshold band
   all stand.
3. **DEM-follow seeding** (gate O4_RUNWAY_DEM_FOLLOW, default "0",
   own A/B arm). The profile seed follows the smoothed DEM within
   runway grade law, clamped to the CIFP-pinned certain anchors and
   the existing curvature/FAA gates (RUNWAY_DEM_FOLLOW_BAND_M becomes
   the law-bounded follow band; pick the value from the probe's dip
   data and justify). Crown/emit spaces unchanged (the flex-space
   invariant at flex_slack_at's docstring governs); EAT pins derive
   from END values — CIFP-pinned, so unmoved (verify byte-identical
   EAT pins in the arm). Pre-reg: 05R/23L center within 1.0 m of the
   DEM sag; the 6907 taxi tension dissolves at the SOURCE (flex
   demands at 05R/23L center -> ~0); runway max grade never exceeded
   (FAA gates re-run are the enforcement, validator the twin).
4. **Honest instrument** (ungated, report-only). The B2 line quotes
   true demand (killed candidates included), requested vs achieved
   (apply discards named), and per-runway residual. Byte-inert on
   surfaces (prove on the stress arm).

## Verification (streamlined protocol)

STRESS: HECA (gate-on arms per fix + composed); SENTINEL: CYXY
(gate-off identity 2x — it has the crossing runway, so also assert
crossing anchors still bound under fix 1). Gate-off byte identity 2x
at HECA vs the CURRENT tip anchors (pin at dispatch — the ref-pull tip
battery is minting them; a stale anchor is a STOP). Pre-registered,
composed arm (1+2 on): 05R/23L drains its full Stage-C arithmetic
(3.847 m class); raw-envelope census at HECA falls (the 1284
seed_rwy_seam x seed_rwy_seam class shrinks — quote the number, band:
-30% success / any fall partial); with 3 on: the +9.16 m
center-vs-DEM offset falls below 1.0 m and runway earthwork drops.
Cross-airport claims pre-registered here, verified at the NEXT tip
battery (do not run a full battery in-lane). Suite: affected-module
matched control; twins per fix. Ledger tripwire only. Deliver: per-fix
diff, clamp table re-run (the probe's instrument is reusable),
composed verdict, file list. Do NOT commit. STOP: sentinel identity
mismatch; any FAA gate regression; fix-3 arm moves any CIFP threshold
value; second miss.

## LEAD ADJUDICATION + §2a AMENDMENT (2026-08-04 night; evidence
## scratchpad flexfix/out/)

Bands 1-4 PASS (several exceeded): self-anchor lock measurably gone
(zero-slack bins 153/277 → 0/1008); 05R/23L residual 25.06 → 1.18 m;
DEM-follow puts the center within 0.945 m of the real sag and 05R/23L
emits ZERO flex demands (the 6907 tension dissolves at the source;
node 6907's 2.672 m inversion row is eliminated); airport earthwork
−38.5%; the honest instrument reproduces the probe's JSON exactly.
DECISIVE extra arm: fix 3 + O4_BAND_SEED_COMPLETE=1 completes the
build with 1 sub-materiality inversion (vs the 1302-node abort) — the
named precondition for that gate's flip is MET.

**§2a AMENDMENT (the STOP's resolution — specified completion of an
attributed mechanism, not a new guess):** the spec's "slack clamp,
displacement budget ... all stand" froze the DEMAND-side clamps;
apply_runway_flex's verify-and-relax is the APPLY-side safety check
and testing only MAX_RUNWAY_GRADE there is a bug — the per-segment
end-zone cap (runway_segment_grade_cap, FAA 0.8% in the end
fractions) is law. Extend verify-and-relax to the per-segment cap in
NO-NEW-REGRESSION form: a target that would create a new
over-end-zone-cap segment (or worsen an existing one beyond the
0.01 pp materiality floor) is relaxed/rejected; the 17 PRE-EXISTING
over-cap segments at gate-off (05C/23C end zones — a standing defect
now visible, recorded for its own round) are not this round's
responsibility. Pre-registered: fix arms' end-zone table returns to
<= gate-off (17 segments / 728.0 m); the +9/+15 regressions gone;
05R/23L's marginal 4 clear or sit below materiality. This is the
lane's second and final attempt on the FAA band.

Other deviations RULED: the §2-combination census arms were the right
instrument (approved); EAT-pin identity is vacuous at HECA — the
claim moves to the next tip battery on KCLT (recorded); fix-2's
12-round plateau is ATTRIBUTED to displacement-budget saturation at
05C/23C and 05L/23R (815/1008 budget-bound) — accepted, the 4.0 m
budget is standing law and its adequacy is a flip-round question
along with 05C/23C's +77% fix-3 earthwork rise (both recorded as
flip-gating open items); the CYXY dedicated anchor probe + twins in
lieu of an inert build arm is approved practice for a
demand-free airport.

SEQUENCING: this lane lands AFTER the ref-pull tip (the lane is
default-inert — identity proven at both anchors — so the tip's minted
anchors survive its landing unchanged).
