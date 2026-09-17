# Brief pack — lane `betaci`

Base: main `4a079792` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta plan lane betaci

## The brief

## Lane betaci — plan §1 B4: Windows and Linux run tests in CI (you OWN .github/workflows/ci.yml; do NOT touch release.yml)
Facts: ci.yml is one macos-15 job (swift build/test). release.yml shows the working install recipe per platform: Python 3.13; Windows installs Ortho4XP/Utils/win/*.whl (gdal, scikit-fmm) then requirements.txt minus gdal/scikit-fmm; Linux apt libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 and skips gdal (optional at runtime: O4_DEM_Utils.py guards the import). The dev/test tail of requirements.txt (pytest, pytest-xdist, hypothesis) IS needed here. Locally (mac) the corpus-independent set passes: tests/test_harness.py + tests/test_engine*.py = 447 passed / 65 s; tests/test_qt_*.py = 239 passed offscreen. conftest resolves ~/XPTerrainBuilderData and guards WRITES, so an absent data repo is inert; candidates needing triage on a clean runner: test_data_root.py, test_bathymetry*.py, test_census_cache.py, test_post_mesh.py, test_dsf_object_*.py, test_silent_tile_death.py (already skips).
Deliver: a matrix job (windows-latest, ubuntu-22.04) in ci.yml running, from Ortho4XP/, pytest on tests/test_harness.py tests/test_engine*.py tests/test_qt_*.py with QT_QPA_PLATFORM=offscreen and MPLBACKEND=Agg, -p no:cacheprovider, a job timeout of 30 min, pip cache. A test that fails for a genuine platform reason is either FIXED (path separators, a missing platform binary under Utils/<platform>) or skipped with a reason naming the platform and the cause — never deleted, never a blanket xfail; list every such test in your report. The mac job also runs the same pytest set (today it runs no Python at all).
EXCEPTION to the no-push rule (owner said go on B4, whose closing test is a green matrix): you MAY push ONLY your own branch claude/betaci to origin to trigger CI (ci.yml runs on every branch push), and read results with gh run list/view. Never push main, never dispatch Release, never open a PR. Bound yourself to at most 6 CI rounds; then report where it stands.
Closing test: a green run on your branch for all three OSes (link + per-job conclusions), plus one deliberate red (a commit that breaks an import, pushed, observed red on both new runners, then reverted) to prove the jobs can fail. Round 2 (not now, after betaversion merges): a frozen-bundle fixture tile run inside release.yml — give me a short design for it in your report, do not implement.

### Rules common to the four beta lanes (session, 2026-09-17)
- NOT an auto_patch law lane: no airport build, no census, no five-airport sweep, no RULINGS/spec reading. Read docs/BETA-PLAN-20260916.md for context (your section only).
- Worktree: from Ortho4XP/, `tools/harness/lane_worktree.sh up <lane>` (bare NAME) so pytest has the venv and mounts; branch `claude/<lane>`. Merge main first.
- Toolchain: the RELEASE Xcode via xcode-select. NEVER pass DEVELOPER_DIR=/Applications/Xcode-beta.app (uninstalled). `swift build` / `swift test` need no override.
- The owner's app may be running: never quit it, never run scripts/make_app.sh or make_engine.sh, never touch dist.nosync/. Never sign anything.
- Before editing anything under Ortho4XP/src/ or Sources/: `Ortho4XP/venv/bin/python tools/blast.py <file>` and run the tests it names.
- WIRE PROTOCOL: Ortho4XP/src/o4_engine/events.py class names ARE the JSONL wire names; Sources/SceneryKit/OrthoEngineClient.swift matches them as string literals. A new/renamed event must land on BOTH sides in the same commit; `tools/blast.py` reports drift.
- FILE OWNERSHIP this round (other lanes run in parallel): `.github/workflows/release.yml` = betaversion ONLY; `.github/workflows/ci.yml` = betaci ONLY; first-run sheets/wizard + canBuild + the cifp refusal = betafirstrun; About dialogs = betaversion; Qt event-handler table, Qt stderr tee, make_dirs, imagery warning, 7z, specs = betapolish. If you need a file another lane owns, STOP and report instead of editing it.
- Commit early, one commit per deliverable (a sleep/crash killed a lane twice yesterday). Keep tool calls bounded; no unbounded wait loops.
- Do not merge, do not push (exception stated in your own brief if any). Report: branch + sha, each closing check with its rc and FAILED lines verbatim, and everything NOT done.

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

