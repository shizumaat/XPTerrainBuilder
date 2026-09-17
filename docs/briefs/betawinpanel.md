# Brief pack — lane `betawinpanel`

Base: main `bff0919b` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta round 2 lane betawinpanel

## The brief

## Lane betawinpanel — the Windows Qt tile-details panel is silently clipped (found by lane betaci, 2026-09-17)

MEASURED on the windows-latest runner: `tests/test_qt_window_layout.py::TestPanelFitsItsViewport::test_panel_minimum_width_fits`
fails with `panel.minimumSizeHint().width() == 452` against a `266` px viewport. Under
the Windows style the font metrics and control margins overflow the right panel's fixed
width, and the horizontal scrollbar is off by design, so the frozen Windows app clips
the tile-details panel. betaci SKIPPED the test by name on win32 (it did not own
`Ortho4XP/src/O4_Qt_GUI.py`); macOS and Linux pass it. This is a beta blocker for
Windows testers.

Do:
1. Find which child widgets drive the 452 px minimum on Windows (log each child's
   minimumSizeHint / sizeHint in a throwaway diagnostic test run on the Windows
   runner; delete the diagnostic before you finish). Attribution before fix: report
   the top offenders with their widths on windows vs mac.
2. Fix the LAYOUT in O4_Qt_GUI.py so the panel's minimum width fits its viewport on
   all three platforms: prefer letting long labels elide/wrap (setWordWrap,
   QSizePolicy.Ignored/Preferred on the offenders, elided text) and removing fixed
   widths, over widening the panel or turning the horizontal scrollbar on. Do not
   change the mac/Linux look more than necessary; say what changed visually.
3. UN-SKIP the test on win32 (remove betaci's skip) — the closing test is that test
   GREEN on windows-latest, plus the full Qt set green on all three OSes.
4. While you are there: the owner has never run the Qt app on Windows since alpha.2.
   If the diagnostic shows OTHER panels/dialogs whose minimumSizeHint exceeds their
   container on Windows (the settings dialog, the first-run wizard page added today,
   the About dialog added today), list them with numbers; fix only what is cheap and
   the same class, report the rest.

You have ONE exception to the no-push rule: you may push ONLY branch
`claude/betawinpanel` to origin to trigger CI (ci.yml runs on every branch push; read
results with `gh run list/view`; a cancelled job keeps no logs, so keep steps
bounded). At most 6 CI rounds. Never push main, never dispatch Release, never open a
PR. You may NOT edit `.github/workflows/ci.yml` except to add a TEMPORARY diagnostic
step on your branch, removed before your final commit (the final diff must not touch
ci.yml).

Rules: not a law lane (no airport build). Worktree from Ortho4XP/:
`tools/harness/lane_worktree.sh up betawinpanel`; merge main first. The bash guard
refuses engine test commands whose effective cwd is not an Ortho4XP/ with venv and
OSM_data — run tests from your worktree's Ortho4XP/ and never end a compound command
with a `cd` elsewhere; it also pattern-matches test-runner words inside heredocs, so
write files with the Write tool, not heredocs. Release Xcode only; never quit the
owner's app; never run make_app/make_engine. `tools/blast.py <file>` before editing
src. Qt tests monkeypatch PREFS_FILE and TILE_SCAN_CACHE_FILE before window
construction (see tests/test_qt_mac_parity.py). Commit early; do not merge. Report
branch + sha, the green run link with per-job conclusions, the offender table, and
everything not done.

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

