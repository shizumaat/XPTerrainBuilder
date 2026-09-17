# Brief pack — lane `betawinsettings`

Base: main `c76ee1e1` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Qt Settings window and first-run wizard fit a small Windows laptop

## The brief

## Lane betawinsettings — the Qt Settings window and the first-run wizard fit a small Windows laptop

MEASURED by lane betawinpanel on the GitHub runners (`minimumSizeHint`, 2026-09-17):

| dialog | windows | mac | linux |
|---|---|---|---|
| `O4_Qt_Settings.SettingsWindow` | **1228 x 169** (sizeHint 1228 x 364) | 696 x 200 | 696 x 173 |
| `O4_Qt_Wizard.OnboardingWizard` | 586 x 198 (sizeHint **864** x 204) | 602 x 215 | 462 x 202 |
| About (`QMessageBox.about`) | 427 x 118 | 258 x 147 | 228 x 147 (fine, stock) |

Cause class (proven for the main panel, merge 6db2e0d9): NOT the Windows style (both
runners report `fusion`) — the offscreen font on windows-latest advances a digit at
12 px against 8 px on macOS, and widgets report their FULL TEXT WIDTH as their minimum.
A Settings window that cannot shrink below 1228 px is unusable on a 1280 px laptop
(and on any scaled display); a wizard preferring 864 px overflows an 800 px screen.
These are resizable top-level dialogs, so they do not clip silently — they simply
cannot be made to fit.

The idiom already in the tree (Ortho4XP/src/O4_Qt_GUI.py, merged 6db2e0d9 — read it):
`ElidedRowLabel` (one line, sizeHint = full text, minimumSizeHint = one ellipsis, tail
elision, full text in the tooltip, never overwrites a caller-set tooltip),
`_may_be_squeezed(combo)` (AdjustToMinimumContentsLengthWithIcon), `_never_widen`
(Ignored horizontal policy). If the dialogs need them, MOVE them to a small shared
module (e.g. `Ortho4XP/src/O4_Qt_Widgets.py`) and import from both places — one
definition, never a copy; update the spec's hidden imports only if the freeze needs it
(a top-level `import` is visible to PyInstaller; say which you relied on).

DO:
1. ATTRIBUTE first, on the Windows runner: a throwaway diagnostic test listing each
   dialog's top offenders (child `minimumSizeHint().width()` / `sizeHint().width()`,
   windows vs mac). Delete the diagnostic before your final commit. Report the table.
2. FIX in `O4_Qt_Settings.py` and `O4_Qt_Wizard.py`: long setting names/hints wrap or
   elide (word-wrapped hint labels; elided row labels with the full text in the
   tooltip), path fields and combos may be squeezed, the settings rows live in a scroll
   area so HEIGHT never forces the window either. Prefer this over fixed widths. Target,
   on ALL THREE platforms: SettingsWindow `minimumSizeHint` <= 760 x 560 and a default
   size that fits 1280 x 720; OnboardingWizard `sizeHint` <= 760 x 560. The settings
   layout CONTENT is law shared with the mac app (`O4_Settings_Model._LAYOUT` mirrors
   `Sources/XPTerrainBuilder/SettingsLayout.swift`) — change presentation only, never
   the categories, rows or order.
3. TWINS that hold the line: for each dialog, with EVERY row/category populated with
   realistically long values (long paths, the longest provider name, the first-run
   X-Plane page showing its longest rejection reason), assert the size bounds above.
   They must run on all three CI platforms (no win32 skip).
4. Say what changed visually on mac/Linux (the owner reads the mac look; keep it).

EXCEPTION to no-push: you may push ONLY branch `claude/betawinsettings` to trigger CI
(ci.yml runs on every branch push), at most 6 rounds; read results with gh run
list/view and the jobs logs API (`gh api --allow-escape-sequences
repos/shizumaat/XPTerrainBuilder/actions/jobs/<id>/logs`). A cancelled job keeps no
logs. Never push main, never dispatch Release, never open a PR; the final diff must
not touch `.github/workflows/`.

Rules: not a law lane (no airport build). Worktree from Ortho4XP/:
`tools/harness/lane_worktree.sh up betawinsettings`; merge main first. The bash guard
refuses engine test commands whose effective cwd is not an Ortho4XP/ with venv and
OSM_data (run tests from your worktree's Ortho4XP/ in their own call, never ending a
compound command with a `cd` elsewhere), pattern-matches test-runner words inside
heredocs (write files with the Write tool), and refuses `git stash`. Release Xcode
only; never quit the owner's app; never run make_app/make_engine. `tools/blast.py
<file>` before editing src. Qt tests monkeypatch PREFS_FILE before window
construction (see tests/test_qt_window_layout.py; use `MainWindow._after`-style
owned timers if you add any deferred call — an ownerless QTimer.singleShot fires on a
destroyed window, fixed 829b777d). Commit early; do not merge. Report branch + sha,
the green three-OS run link, the offender table, the before/after sizes per platform,
what changed visually, and everything not done.

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

