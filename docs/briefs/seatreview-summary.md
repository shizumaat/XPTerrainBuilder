# seatreview — review of PR #480 (`claude/pads63` @ `de63f227`), the pad seat with no step (spec §57 (3)), 2026-10-08

Fable spec author / reviewer. Pure reads: the code (`constraints/weld_floor.py`, `constraints/no_step.py` `hold_interval` /
`HoldPass`, `solve/flex.stage_one`, `tools/check_grade.py` `weld_widened_nodes`), the closing builds `/tmp/harness/p64_*`
(sidecars `*.osm.axes.json`, `*.v2/*.graded.json`), the J1 control `p64j1_HECA`, the lane's census row dumps and diffs
(`<scratch>/pads64/{rows_p64_HECA,rows_p64j1_HECA,rowsdiff_hairline_HECA}.json`), the dead lane's closers probes
(`<scratch>/pads63/closers_{HECA,KASE}.txt`), `docs/briefs/pads64-notes.md`. No build, no replay. Spec §57 (3) amended in place
(the design paragraph); the rulings below are the same text, short.

## Rulings

**D1 — the give is each closing contact's OWN SHORTFALL, floor-gated: ACCEPTED as the general statement of 08d (2).** The floor
is the gate ("a step < 1 m"), the give is what the weld needs (08c (1): a cap, not a target). Row set as built = every pavement-tier
row NAMING a closing contact (depth 1), never a runway row, never a pad row: minimal in rows, maximal in grade — see (ii-b).

**(ii-b) WHERE the give is spent: REPLACED.** Depth 1 forces the whole give into the first row off the pad. Graded profile,
`building147` east (p64 datum 71.113): contact 71.11 → **72.01 at 7.8 m (11.58 %)** → 72.21 at 25.7 → 72.64 at 54.5 → 72.90 at
71.6 m (1.5 % thereafter; the apron beyond the first row stands AT its reach lower bound 72.005, held by its own un-widened chain to
05C/23C). West: 71.11 → 70.13 at 16.5 m (5.9 %) → 69.59 at 51 m. The remainder spills into rows the widening does not name:
**62 new `airside_no_step apron|junction` census rows at 1.54–2.98 % over 51–144 m** within 200 m of the west contact (J1 control:
2); family 3,999 → 4,069; adjudicated airside 12,013 → 12,045. So 11.58 % is the depth-1 row set's doing, not 08d (2)'s.
Replacement: ONE over-cap grade allowance Δ_b per misfit block on every pavement-tier row of the FACES the closing contacts front,
Δ_b = the least at which the admissible set (re-read on `reach_anchored` with `cap + Δ_b`) is non-empty (bisection, ≤ 8 reach reads
× 0.7 s). Expected: east face ≥ 71.6 m at cap → ≤ **2.6 %**; west ≥ 246 m → ≤ **1.8 %**; KASE `building1` ≤ **2.8 %** (built 4.62 %).

**D2 — the weld projection (`seal_welds`): ACCEPTED WITH A BOUND.** Measured class: 8 HECA contacts on 4 pads, 0.020–0.042 m,
the solver's unsettled residual. Census at the eight coordinates (3 m): J1 control 4 `pad_frontage_infeasible` rows, p64 **0 rows of
any family** — nothing new minted there; the rows the contact sits in move ≤ 2 × `hard_tol_m` and the census prices a pair naming
it at `cap·d + move`. Lawful for that class (a weld row against a solved datum is a point; 12ag). BOUND: `|move| ≤ 0.05 m`
(`[design] seal_max_m`, the residual class). The `27f60b89` generalisation to an LP-RELAXED weld under the floor (`weld_seal.relaxed`
= 0 on every arm and build) is REPLACED: such a weld is a misfit the pair-graph read missed → back through (ii-b) with the LP's
relaxation as the give and ONE pass-1b re-solve; still off → the warning. A 0.3–0.9 m post-solve assignment moves the step one row
outward into rows nothing re-checks while the census allowance hides it (`single-pass-principle`, `emit-consensus-mints-violations`).

**D3 — a fixed closing contact (pin / runway column) stands the block down: REPLACED.** Fired 0 times on the four airports. The
released weld it leaves is the step 08c (4) forbids. Rule: a fixed contact DICTATES D (its value); the other closing contacts give
from that D under (ii-b); two fixed contacts disagreeing under the floor → warn, owner question Q5 (recommend: the pad takes the fixed
point's level, YES; two disagreeing: warn + sim read, YES).

**D4 — the hard Band on the datum inside the reach intersection: REPLACED (state it only when the reach intersection CUTS the
pair-graph interval).** It binds nowhere: 0 of 47 HECA datums within 0.05 m of a bound (`building147` isect `[53.72, 82.965]`
against pair-graph `[71.802, 70.252]`), KCLT no datum moved > 0.001 m. Its only effect is the row-set perturbation: KCLT 580 movers,
apron 1.02 m at 35.21575607, −80.94384692; the lane's `x_noband` arm shows one non-binding Band alone moves 268.

**F1 (the unsettled solve):** at HECA under this PR ten pads of one cluster (`building84/91/105/52/62/64/65/83/93` around
30.120, 31.407) rose a coherent **0.60 m** with no row naming them and no datum at a bound; KCLT 1.02 m from a row that constrains
nothing; HECA junctions 0.57 m on a null change (earlier review). Lawful each time (runway 0, taxi-tier equal) and nobody's
mechanism. Recommendation: F1 gets its own lane BEFORE Beta 2's sim reads are the acceptance — name the flat direction on the KCLT
capture, arm = a weak tie of every free airside column to its pass-1a level (weight ≪ the smoothing's), bar: null-change movers
≤ 20 at 0.02 m and 0 over 0.3 m; one day; no owner decision for the attribution.

**Hairline +13 at HECA:** the 15 new groundside `hairline_pair` rows (0.053–0.184 m) stand 56–886 m from the nearest pad and
760–1,850 m from any widened or sealed contact; four are 56–122 m from T3 (`building4`, datum 101.787 → 101.788); the cluster at
30.116, 31.407 is 350–430 m from the ten pads that rose 0.60 m. The §55 pieces re-cut against a base apron the re-solve moved:
lawful, groundside, inside the class 08c (6) re-cuts. Not this PR's mechanism; the bar miss is F1 noise, recorded with coordinates.

## Fix list for the implementer (each with its acceptance)

1. (ii-b) the face-wide Δ_b (bisection on `reach_anchored`), the record `weld_widened.{delta_pct, faces}`, the census pricing by
   face — ~3 h + HECA gaps3 and KASE replays `--from planar --emit --verify`: released 0, WARNED 0, steepest widened grade ≤ 3 % at
   `building147` and `building1`, `airside_no_step` rows within 200 m of `building147`'s west contact ≤ J1's + 3, adjudicated airside
   ≤ the J1 control's 12,013, runway 0, taxi-tier ± 3.
2. (ii-c) `seal_max_m` 0.05 and the relaxed-weld branch routed through (ii-b) + one pass-1b re-solve — ~2 h + a synthetic twin
   (the LP relaxes a weld by 0.3 m → widened, re-solved, released 0, sealed 0); `weld_seal.max_m` ≤ 0.05 on the four airports.
3. (ii-d) a fixed contact dictates D — ~1 h; `test_nearmiss148` re-stated (rim pinned 700.5: D = 700.5, the near-miss contact gives).
4. (ii-e) the Band stated only when it cuts — ~0.5 h; KCLT replay: 0 Bands, movers vs the J1 arm = the arm's own null class.

## Verdict

PR #480 may NOT merge as built: items 1, 2 and 4 first (the 11.58 % apron hump and the 62 new airside no-step rows at `building147`
are a visible defect at the owner's HECA read; the unbounded seal and the non-binding Band are latent). Item 3 may follow.
