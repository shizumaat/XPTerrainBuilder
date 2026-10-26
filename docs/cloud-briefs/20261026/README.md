# Beta 5 cloud lanes, 2026-10-26

From the master session (local; it has the corpus, the apps and the sim owner). The owner asked for cloud agents wherever the work does not need the Mac. Each cloud lane takes ONE issue, and its spec is the `## #N` section of [`triage.md`](triage.md). Re-read this file before every pick: the master updates it.

## Rules (root `CLAUDE.md`, "Single master")
- Report ONLY through your PR body. Never comment on issues, never merge, never create a routine or trigger, never notify the owner.
- PR body opens with these two lines exactly:
  ```
  <!-- claude-projects-attribution: {"github_login":"shizumaat"} -->
  _Requested by **Noah**_
  ```
  then `Fixes #N`, Before/After, How. Commit trailer: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Push only when the PR is ready (CI queue). The master lands PRs in batches of about 10.
- Two UIs, one layout: a Mac app UI change lands in the Qt app in the same PR (`Ortho4XP/tests/test_qt_layout_parity.py`).
- No airport-specific code (`tests/test_no_airport_specific_code.py`).

## What cost a CI round — run before opening a PR
1. Merge current `origin/main`. From `Ortho4XP/`, run `venv/bin/python ../tools/ratchets.py` (duplicate, layers, lint) and `ruff check --select I001` on the changed files.
2. The whole-tree registry twins, which `blast.py` never lists: `test_windows_text_io` (every `open()` takes `encoding=`), `test_patch_env_classification` + `test_auto_patch_freshness` (every new `O4_*` variable classified in `src/auto_patch/provenance_env.py`), `test_tile_failures` (every new exception class gets an `O4_Tile_Failures.EXCEPTION_CODES` code), `test_console_encoding` (every argparse tool pins the console), `test_v1_retired`.
3. **Closure twins:** a new module imported by a build step must be registered in `src/O4_Step_Code.py` (`_SHARED` / `_BEYOND_SHARED`) AND in `src/auto_patch/provenance_code.py` `PATCH_CODE_MODULES`. Run `tests/test_step_code_closure.py` and `tests/test_patch_code_closure.py`. This failed CI in four PRs this month.
4. Tests that skip without the corpus are invisible to you. When you change a signature, grep every caller, skipped twins included.

## Ready now (33)
#740 (step 2 only), #818, #820, #824, #825, #1223, #1224, #1236, #1248, #1261, #1281, #1314, #1315, #1316, #1317, #1318, #1319, #1320, #1321, #1322, #1323 (spec only), #1325, #1326, #1327 (parallel ring cells + progress lines only; the rung change stays with the owner), #1328 (+#1220), #1329, #1334, #1339, #1341, #1345, #1350, #1351, #1357.

## Owner-gated (do not start): #39, #566, #1226, #1229.

## Local only (master): #1340, #1346, #1352, #1353, #1354 (in flight, PR #1368), and every row marked local-only YES in `triage.md`.

## File collisions to avoid
- #1322 and #1326 both touch the Mac/Qt build and activity models: one lane takes both.
- #1325 and #1357 both touch the patch-editor gestures: one lane takes both.
- #1334, #1339 and #1345 all touch imagery provider listing: one lane takes all three, in the order #1345 → #1334 → #1339.
- #1350, #1351 and #1341 all touch the activity and tile-info panes: separate lanes, but rebase on whichever lands first.

## Windows CI traps (added after batch Y)
- Close every GDAL/rasterio dataset (`ds = None`) before `os.replace`/`os.remove` on its file. Windows refuses to replace a file that has an open handle.
- A test's `subprocess.run(env=...)` must start from `{**os.environ, ...}`.
- Derive paths with `os.path`, never by splitting on "/".
