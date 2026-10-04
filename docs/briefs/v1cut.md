# Brief pack — lane `v1cut`

Base: main `bc036d1e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane v1cut — finish the v1 retirement (stage B round 2) on CURRENT main

State: `src/auto_patch/` is 130 files / 229,736 lines on main. The round-2 cut halted 2026-09-17 on `claude/v1retire` @ 711f21b5 ("partial cut, NOT merge-ready", 11 reds); main is 1,361 commits ahead, so that branch is a MAP, not a merge source. Read its per-group deletion commits (b3d90cf0 pavement/, 32cd7959 elevation_per_surface/, 0d69ed4a elevation stage, b138e39e law and graders, 7021bfea features and roads, the layout group inside the checkpoint) and redo the cut on a fresh branch from main.

- The keep set is declared in `Ortho4XP/tests/test_v1_retired.py` (KEEP, 27 modules / 44,717 lines). Re-derive what production reaches TODAY before deleting; KEEP may have moved in 1,361 commits. A module joining or leaving KEEP is reported, not silently edited.
- v2 imports nothing from v1 (0 files). 354 test files (185,210 lines) and 102 `Ortho4XP/tools` scripts import v1. A test whose only subject is deleted is retired by name with the reason in place of the body (the pattern the old lane used); a tool whose only subject is deleted goes, with its `tools/INDEX.md` row; a tool or test with a live subject is re-pointed.
- The old lane's remaining list still applies: flip `test_v1_retired.py` to the ABSENCE assertion (modules on disk within KEEP); re-point `tools/check_build_time.py` `_run_one` and `tools/blast.py` FIXTURE_CANARIES (one line; lane sizeratchet edits blast.py additively); split `config.py` down to what is still read; the `auto_patch/__init__.py` charter; `src/auto_patch/CLAUDE.md` rewritten for what remains (its hard time law and the gotchas that still apply SURVIVE); `Ortho4XP_Qt.spec` hidden imports (frozen-engine trap: a function-level import is invisible to the freezer).
- Commit per group, tree green at each commit. If the round is too large for one pass, stop at a GREEN commit and report the exact resume step; never leave a checkpoint with reds.
- Closing: the standing suite; ONE HECA run through the harness entry; census identical to main's registered reference (sw1026); patch body hash compared with a same-tree control per the patch A/B law; the Swift package compiles; collection count and line counts before and after.

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Report only in your final report: branch, sha, measurements, net lines added/removed, new public symbols, and every item NOT done.

## RULINGS

## 2026-10-04a — OWNER: FILE SIZE, RATCHETS AND THE ARCHITECTURE MAP (confirmed in session 2026-10-04; SUPERSEDES the numbers of 2026-09-13bz, keeps its sentence "split by responsibility, never fold comments to make a number"). MEASURED at main bc036d1e (tracked `.py` lines, comments and blanks included): v1 `src/auto_patch/` 130 files / 229,736 lines — the stage-B round-2 cut never landed (`claude/v1retire` @ 711f21b5, halted 2026-09-17, main 1,361 commits ahead; `tests/test_v1_retired.py` KEEP = 27 modules / 44,717 lines); v2 `src/auto_patch_v2/` 26,646 lines on 2026-09-05 → 113,478 (274 files; median 316, p75 594, p90 959, max 1,481; 23 files past 1,000); `O4_Airport_Elevation_Insets.py` 12,933 → 19,820 between 09-28 and 10-04 (eight provider strategy classes in one file, #130 #153 #154); 102 files under `Ortho4XP/src` past 1,000 lines. 13bz's twin covered `auto_patch_v2` only and refused at 1,500 — every other tree was unguarded. RULED: (1) **SIZE** — soft limit 600 lines (a PR that takes a file past it states why the file is not split); hard limit 1,000 lines for any NEW source file; a file already past 1,000 at the baseline is RATCHETED — it may shrink, never grow. Scope: `Ortho4XP/src`, `Ortho4XP/tools`, `tools`, `Sources`; tests are reported, not gated. (2) **ONE FILE PER FAMILY MEMBER** — a family (elevation providers, solver constraints, emit adapters, law tables) is a package with a base interface, a registry and one module per member; a new member is a new file, never an append. (3) **RATCHETS AT MERGE** — the size baseline and a duplicate count (functions with identical normalised bodies across files) may fall and never rise; v2's package order (plan table, 1 `airport/` … 7 `emit/`) becomes an import-direction check. (4) **THE MAP IS GENERATED** — `tools/blast.py --map <package>` / `--find <keyword>` from module docstrings and `__all__`; `tools/brief_pack.py` attaches the map of every package a brief touches; a twin fails a module with no docstring or no `__all__`. No hand-written class list. (5) **EVERY LANE REPORT / PR BODY** carries net lines added and removed and the new public symbols. ORDER: ratchets (lane `sizeratchet`) and the v1 cut (lane `v1cut`) in parallel, with scout `v2growth` attributing the 87k v2 lines; then the map tooling and layering check; then the insets split into a providers package.

## 2026-09-13bz — OWNER (verbatim): "The 1,000 line cap is a guideline, not a hard number. It should be a warning that we may need to consider the architecture if it's getting that long, does it all logically still fit, or should it be split into separate classes/functions/modules..." — RULED: `tests/auto_patch_v2/test_model.py`'s file-length twin now WARNS past 1,000 lines (naming the file and its length; "consider the architecture") and refuses only past 1,500 — the point at which a lane must split before merging. The standing guidance to lanes changes from "files under 1,000 lines" to "a file past 1,000 lines is a signal to ask whether it still logically fits; split by responsibility when it does not, never fold comments to make a number"; `emit/bank.py`'s dropped attribution hooks (13bx) may come back when its seam-band and coverage halves split (lane `v2hairline` owns that split — `emit/seam_band.py` already exists). `CLAUDE.md`, `lane.md` and `brief_pack.py`'s STANDING block updated.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

