# Unused-code clean-up plan (proposal, 2026-10-15)

Status: PROPOSAL for Beta 3. Owner order 2026-10-15: "Write the proposal, then
file it as an issue for Beta 3." It dispatches nothing by itself; the project
master runs it, one lane and one landing at a time.

Law it serves: RULINGS 2026-10-04a/b/c (reuse before new; 1,000 lines is a
warning, never a gate; the duplicate ratchet is the gate) and the owner's
words that started it: "small re-usable modules, and eliminating code that
does the same thing in slightly different ways multiple places."

## Where things stand (measured 2026-10-15, main e5f799bb3)

| | 2026-10-04 morning | 2026-10-05 (clean-up landed) | 2026-10-15 |
|---|---|---|---|
| `Ortho4XP/src` (tracked `.py`) | 420,576 | 230,808 | 259,353 |
| `auto_patch_v2` | 113,478 | 110,848 | 131,063 |
| `auto_patch` (v1 remainder) | 229,736 | 40,938 | 41,998 |
| insets pipeline + `elevation_access` | 19,820 (one file) | 9,472 + 11,981 | 9,714 + 12,812 |
| `Ortho4XP/tests` | 316,351 | about 205,000 | 236,162 |
| `Ortho4XP/tools` | 95,027 | about 76,000 | 83,760 |

Gates and reports today (`tools/ratchets.py`):

- identical-body duplicates: 10 functions in 4 groups (baseline 10) — holding;
- near-duplicates (reported, not gated): 68 functions in 29 groups;
- upward imports between v2 packages: 1 (recorded 1) — holding;
- files past 1,000 lines: 78 (61 under `Ortho4XP/src`); 49 files grew since
  the baseline; 6 newly past 1,000;
- functions of 200+ lines: 123 (37 in `auto_patch_v2`).

Exports no other production module uses (`blast.py --map`, tests not counted
as users): `auto_patch_v2/airport` 317, `constraints` 146, `planar` 84,
`solve` 51, `classify` 34; `auto_patch` 303.

The code base regrew by 28,545 source lines in ten days. Some of that is
Beta 2 behaviour; none of it has been attributed. Nothing gates new dead code.

Known unused or misplaced code, not yet removed:

1. **v1 object stage, about 10,200 lines unreached** (lane `objtests`,
   2026-10-04, table `docs/v1-retirement/object-stage-reach-20261004.tsv`):
   157 definitions — `post_mesh` 28 / 3,615 lines (`discover_and_rebake_airport`,
   `_bake_bridge_abutment_seats`, `_bake_basin_group_seat_facilities`, …),
   `object_anchor` 26 / 2,674 (`structure_deltas` 1,240), `object_rebake`
   24 / 1,214 (`apply` 483), `dsf_reader` 17 / 844, `apt_dat_reader` 19 / 666,
   all of `object_clusters`, and smaller sets. Evidence: 46 rows measured, the
   rest static; 17 post-mesh rows were never measured. `post_mesh.py` and
   `object_anchor.py` have not changed since. Some are still called by tools
   (`tools/object_seating_report.py`, `tools/harness/build_airport.py`
   `find_airport_apt_dat`, `tools/attic/*`).
2. **The v1 remainder grew from 27 to 29 modules** (`object_plan.py` 10-04,
   `provenance_code.py` 10-05, `provenance_env.py` 10-12) against its own rule
   "fix in place, add nothing new" (`src/auto_patch/CLAUDE.md`). Each may be
   right; each should be an explicit `KEEP` decision in
   `tests/test_v1_retired.py` or move to where new code belongs.
3. **Placement census cluster in the engine package**, about 1,700–2,100
   lines of reporting (`airport/placement_census.py`, `placement_seams.py`,
   `placement_cockpit.py`, the reporting half of `placement_motion.py`) —
   scoped out of lane `diagout` because it needed an edit in a file another
   lane owned. Also the reporting half of `planar/__main__.py` (about 450
   lines: `main`, `structure_records`, `write_kml`).
4. **`Ortho4XP/src/Unused/`**: 806 lines, 8 files (`O4_Forest.py`,
   `O4_OverlayDSF_Utils.py`, …), still tracked and still showing up in the
   near-duplicate report.
5. **Structure, not dead code:** the insets pipeline file (9,714 lines, five
   or six responsibilities: resolution ladder, `ensure_airport_insets` + bake,
   building-footprint masking, water detection, acceptance probes, base-tile
   selection), and `elevation_access/strategies/las_tile_index.py` (strategy
   plus a LAS gridder).

## The plan

The order matters: measure, then stop regrowth, then delete, then restructure.
Deleting first, from eleven-day-old evidence, would repeat the mistake of
2026-10-04 (a 29 GB disk claim, an unmeasured test-coverage alarm) — both
read right and were wrong.

### Step 1 — measure (one Opus scout, read-only, no builds)

- Attribute the 28,545 source lines added since 2026-10-05 by cause: new
  behaviour (name the issue), duplication, gated-off arms, dead code. Same
  method as scout `v2growth` (2026-10-04): tokenize/ast composition per
  package, `git log --numstat` grouped by lane and issue.
- Re-derive the v1 `KEEP` reach today (production import closure plus
  string-named modules) and refresh the object-stage reach table on current
  main. Mark rows that need an app-mesh measurement (#737: replays do not
  match the app at the object stage).
- List v2 definitions with no reference outside their own module and tests,
  ranked by size, with the evidence class (no reference anywhere / tests only /
  tools only).
- Deliverable: one findings file and a ranked deletion list with estimated
  lines and risk. Cheap; changes nothing.

### Step 2 — make dead code a number that can only fall (one small Opus lane)

- `tools/archmap.py` already computes "used by another non-test module". Add
  an `unused` section to `tools/ratchets.py`: the count (and lines) of public
  top-level definitions in `Ortho4XP/src` that nothing outside their module
  and tests references, recorded in `tools/ratchet_baseline.json`, may fall
  and never rise — the same shape as the duplicate gate. Dynamic use
  (registries, `getattr`, string dispatch) needs an explicit allow-list with
  a reason per entry, not a silent exemption.
- Promote the near-duplicate count from a report to a ratchet at today's
  value (68), so it too can only fall.
- `src/auto_patch/` additions: `tests/test_v1_retired.py` refuses a new module
  outside `KEEP` unless `KEEP` changes in the same commit (it already does for
  imports; extend it to files on disk if it does not).
- No engine change; lands any time.

Steps 1 and 2 change no engine output and can run before the Beta 2 tag if
the master has a slot. Everything below waits for Beta 3.

### Step 3 — delete in waves (one Opus lane per wave, one landing and one sweep each)

Each wave: attribution table first; byte-identical patches on the sweep's
airports; the full non-Qt suite; tests selected by changed files
(`blast.py --tests-for`); an undefined-name scan after any move; tools that
still call deleted code re-pointed or retired with their `tools/INDEX.md`
rows. Lower the ratchet baseline in the same PR.

| Wave | Scope | Size | Gate before deletion |
|---|---|---|---|
| A | v1 object stage, unreached definitions | about 10,200 lines | the 17 post-mesh rows measured on an APP-built mesh (#737); re-point `object_seating_report`, `build_airport.find_airport_apt_dat` |
| B | v2 dead definitions from step 1's list | to be measured | step 1's evidence class per row |
| C | `Ortho4XP/src/Unused/` and other files no production module imports | 806 lines | grep for importers |
| D | placement census cluster and the reporting half of `planar/__main__.py` out of the engine package | about 2,200 lines moved | `test_fresh_import`, the layer ratchet, replay of a registered HECA capture |
| E | near-duplicate groups from `ratchets.py dupes --near`, largest first | to be measured | AST/behaviour equality check per pair; a pair that differs in behaviour is an owner question, not a choice |

### Step 4 — restructure (after the deletions, separate lanes)

- Insets pipeline file split by responsibility (step 2 of lane `insetsplit`,
  never run).
- `las_tile_index.py`: the LAS gridder into its own module.
- The longest v2 functions (`pipeline/build.py::build`,
  `planar/structures.py::build_structures`, `airport/placement_plan.py::build_splits`
  — 800+ lines each on 2026-10-04): split by pass, behaviour identical.

These remove no code and carry risk, which is why they come last.

## Rules of the road (learned 2026-10-04, see memory `lane-handover-checks`)

- Tests are selected by the files changed (`blast.py --tests-for --since
  origin/main`) plus one full non-Qt run before a branch is handed over.
- An undefined-name scan after any move or re-point (`py_compile` does not
  catch a missing import).
- Each lane writes to its own scratch folder; `pwd` and the branch are
  checked before any state-changing git or delete command.
- Lane builds never run while the owner is building in the app.
- Size is a warning, never a reason to split; split by responsibility.
- Every report carries net lines added/removed and new public symbols.

## Expected result

Waves A–D remove or relocate roughly 13,000–15,000 lines with no change in
output, plus whatever step 1 finds in the 28,545 new lines. Step 2 is the part
that lasts: without it the code base regrows dead code at the rate it did
between 2026-10-05 and 2026-10-15.

## Addendum (2026-10-17, from the OrthoStudio XP comparison)

Source: `docs/findings/orthostudio-xp-comparison-20261017.md` §3 and
`docs/specs/code-quality-beta3-spec.md`. Three things the plan above did not
cover, added as rows of the same plan — not a second plan.

### Step 3 — a sixth wave

| Wave | Scope | Size | Gate before deletion |
|---|---|---|---|
| F | the duplicate v1 readers, re-pointed to their v2 counterparts and deleted: `cifp_reader` (252 vs `airport/cifp` 168), `flat_site` (892 vs 486), `obj8_reader` (587 vs `airport/obj8` 1,518), `apt_dat_reader` (1,976 vs 823), `dsf_reader` (2,485 vs 661; the duplicate ratchet already flags `dsf_reader.py:1136` vs `airport/dsf.py:603`) | about 6,200 lines | per pair: a behaviour table of every public function and its callers (`blast.py`); a pair that differs in behaviour is an owner question; callers re-pointed (`tools/harness/build_airport.py`, `O4_Airport_Elevation_Insets.py`, `o4_engine/patch_commands.py`, `flat_site_mode.py`, `O4_Default_Terrain_Map.py`, `o4_engine/pack_objects.py`, eight `tools/` scripts); `KEEP` shrinks; sweep patches byte-identical |

Wave C also takes `Ortho4XP/tools/attic/` (17 files, 4,108 lines, measured
2026-10-17): a script no index row names and nothing imports is deleted with
the readers it called; one that is still used is promoted with an index row.

### Step 4 — named rows

From `tools/ratchets.py funcs` (2026-10-17, 124 functions of 200+ lines):

- `tools/check_grade.py` (14,715 lines) → package `tools/check_grade/`, one
  module per law family, `run_checks` (1,215 lines at `:13422`) the dispatcher;
  gate: census output byte-identical on the sweep patches, `test_harness`
  green (spec §3).
- `O4_DSF_Utils.py:814 build_dsf` (1,349 lines): the W7 vectorisation helpers
  are its first cuts (`dsf-and-masks-measure-first-spec.md`).
- `auto_patch_v2/pipeline/build.py:645 build` (1,046 lines): one function per
  stage block, which the v2 stage cache needs anyway (`v2-stage-cache-spec.md`).
- `auto_patch/object_anchor.py:2346 structure_deltas` (1,240 lines): wave A
  deletes it; no split.
