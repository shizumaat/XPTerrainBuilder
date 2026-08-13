# Performance phase charter (Fable, 2026-08-13)

Owner rulings: phase opened 2026-08-13; baseline FROZEN at
`Ortho4XP/baselines/1.0.245/MANIFEST.txt` (byte-identity or row-by-row
explained deltas — known imperfections held constant); budgets 60 s per
airport auto-patch / 300 s per tile, COLD, adjudicated IN this phase;
timing runs exclusive/foreground; ab-time protocol (never single runs,
never through the run ledger); committed build-time baselines re-recorded
with owner approval at phase open (2026-08-04 drift artifact).

Standing flags entering the docket: HECA solve (326 s historically;
562 s whole-airport recorded post-joins), #16 weld enumeration
+0.76 s×build, rim detector +2.2 s (memoization untried, gated OFF
anyway), corridor solve growth (the feature), OTHH ~18-21 min arms.

## Phase plan

P1 — PROFILE (exclusive, first, alone): where does the time actually
go? (a) Mine the recorded phase-time ledger (~/.ortho4xp/
auto_patch_build_times) across the five baseline airports — free, no
builds. (b) ONE profiled HECA airport build + ONE profiled KCLT tile
build (py-spy or cProfile, foreground, nothing else on the machine;
profiler runs measure DISTRIBUTION, not wall — wall comes from
check_build_time --runs N afterwards). Deliverable: a cost table
(phase × function, top 20 sinks) with the solve's internal breakdown.

P2 — INSTRUMENTS (parallel lanes after P1's timed section):
census-by-body-hash caching; per-round wall/token logging in the run
ledger; fixture airports (mini corpus per defect class); the
solve-stage repro cutter (Fable-specced separately once P1 names the
capture boundary).

P3 — OPTIMIZATION LANES: one lane per P1-named sink, each with (a) the
frozen-baseline identity gate as its acceptance, (b) ab-time --runs N
for the wall claim, (c) the Fable whole-pipeline review per the hard
law before landing anything ≥1% of budget.

P4 — ADJUDICATE the budgets + pay the flagged items; re-record
baselines (owner approval); close with a phase report.

Dev-model v2 applies: pre-delegated decision trees, report caps,
author-verified premises, Fable small-diff carve-out.
