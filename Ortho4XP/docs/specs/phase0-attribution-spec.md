# Phase 0 — attribution of the 2026-08-30 regressions (NO FIXES)
# (POSTMORTEM-20260831.md; RULINGS 31a. Three tasks, three lanes.)

Base for all reads: main at 605aee75. The owner's flown build is app
1.0.271 / engine 1.50.1714; the owner's tile rebuilds landed Aug 30
22:17 (HECA), 22:23 (OTHH), 22:31 (LEMD), 22:50 (HECA) — their patches
are in the shared repo (`XPTerrainBuilderData/Patches/...`), READ-ONLY.
Every task reports attribution ONLY — a fix proposal is one paragraph
at the end of a report, never a commit.

## Task A — roads: name the grade-cap mechanism (build lane)

Owner law (31a): roads follow terrain up to 8 %, pinned only at
airside pavement. Observed: roads capped at a visibly low grade,
cutting through hills.

Suspects, in test order (single-suspect off-arms, one airport = HECA —
~85 m relief, the road-through-hills geometry):
1. `groundside._grade_limit_groundside_chords` — three call sites; the
   2026-08-30 round newly ARMED the pinned up-build at
   `pipeline.py:7076` (commit a4c693a7 family). Off-arm: disable the
   new arming; separately, disable the limiter entirely (two arms).
2. The bridge lane's free-road profile edits: `anchors.py` composed-
   anchor changes, the climb-run cap pricing, §3's free-end-tie
   removal (commits f2278013/556d4aa5/d0cfe869 family). Off-arm:
   revert those hunks in the lane worktree.
3. `adjacent_ground` band-cuts-groundside (`_zone12_claim` /
   `_cut_groundside_back_to_bands`, commit a4c693a7). Off-arm: its
   own gate.

Method: ONE control at 605aee75, then one arm per suspect (parallel
correctness builds are lawful). Measure with a road-profile-vs-DEM
read at 3+ hill road sites (pick from the HECA patch: longest
service_road chains crossing ≥10 m relief; quote way ids + lat/lon):
per site, emitted grade vs terrain-following-at-≤8 % expectation, and
|emitted − DEM| along the chain. The arm that restores terrain-
following names the mechanism. If NO single arm restores it, say so —
compounding is a finding, not a failure. This read is the seed of the
terrain-conformance instrument (31a): land the measurement script in
tools/ with an INDEX row and a twin — measurement code is in scope,
fixes are not.

## Task B — slowdown: name the phase (read-only lane)

Owner ledger `~/.ortho4xp/auto_patch_build_times/{HECA,LEMD,OTHH}.json`
records per-phase seconds. Diff the last pre-regression entry vs the
Aug-30-evening entries per airport, per phase. Name the phase(s) that
grew and map them to the day's merges (candidates: adjacent_ground
band emission, structure-walls footprint recompute — distinguish the
one-time cache-v7 recompute from steady-state by comparing the TWO
HECA builds 22:17 vs 22:50 — deck detection, claim severing, the
armed chord limiter). Also check `~/.ortho4xp/tile_build_times` for
the same tiles. No builds, no timing runs — recorded data only.

## Task C — sim divergence: what did the owner actually fly (read-only lane)

At 6 owner sites, read the FLOWN patch (shared-repo Patches, the
Aug-30-evening builds) vs the corresponding harness closing arms
(artifact ledger) with tools/osm_site.py:
- HECA 30.1125699,31.4053664 (cliff) · 30.1055367,31.3994026 (ramp) ·
  building79 site
- LEMD 40.4836744,-3.5809643 (bridge span — CORRECTION (Task C): the
  bridge branch WAS merged (13c9351b) and flown; the deck emits as
  ordinary road pavement, not a deck role) ·
  40.4924484,-3.5692887 (basin)
- OTHH 25.2715775,51.6023886 (mouth walls)
Per site: same shapes/values as the harness arm (production frame
matches — the fix is present but visually insufficient → item
re-scopes) or different (frame divergence → name the differing
config/env). Also verify the flown engine version stamps and that the
patches carry .axes.json sidecars.

## Acceptance

Three reports, attribution-only, each naming mechanisms by file:line
and commit. Owner then rules keep/revert per family (Phase 1) with
evidence. Budget: Task A = 1 control + ≤4 arms (HECA ~35-55 min each,
parallel); Tasks B/C = zero builds.
