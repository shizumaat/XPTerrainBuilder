# Brief pack — lane `betafirstrun`

Base: main `4a079792` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta plan lane betafirstrun

## The brief

## Lane betafirstrun — plan §1 B2: first run asks for the X-Plane folder; a build without CIFP refuses
Facts (scout, 28e6423c): the only first-run sheet is the data folder (Sources/XPTerrainBuilder/MapMainView.swift:57-64 presents DataFolderSheet; DataFolderSheet.swift asks nothing else); X-Plane paths are seeded reactively (MapMainView.swift:41-49 → BuildModel.seedPathsFromXPlane, BuildModel.swift:1475-1499); canBuild (BuildModel.swift:1000-1004) does not require an X-Plane folder; with none, custom_scenery_dir and cifp_data_path stay empty and Ortho4XP/src/O4_Vector_Map.py:1460-1479 prints UI.loud_warning then builds every airport on raw DEM and exits 0. Qt: O4_Qt_Wizard.py is the first-launch onboarding; O4_Qt_GUI.py:1348-1349 seeds cifp when empty; O4_Settings_Model.py:79-87 has xplane_dir/cifp rows.
RULED by the session: (a) both UIs REQUIRE a valid X-Plane folder before a build can start (valid = contains "Custom Scenery/" and "Resources/default data/CIFP/"); the first-run flow asks for it right after the data folder, pre-filled from any detected install, and writes custom_scenery_dir + cifp_data_path. (b) The ENGINE refuses (rc != 0, the existing per-tile error/BuildDone error path naming the key — do NOT invent a new event) when auto-patch is ENABLED and cifp_data_path is empty or not a directory; an explicit auto-patch-disabled config still builds (census every reader of cifp_data_path and the auto-patch enable key first, one table in your report; tools/harness/build_airport.py --tile already enforces the same law — reuse its predicate if importable, never a second spelling). (c) Line numbers above may have drifted; re-find them.
Closing tests: swift build + swift test green; a Swift unit test that canBuild is false with no X-Plane path and the reason string is surfaced; pytest twins: engine refusal on blank key with auto-patch on, no refusal with auto-patch off, Qt wizard page validates a fake X-Plane tree (QT_QPA_PLATFORM=offscreen, monkeypatch PREFS_FILE before window construction as tests/test_qt_mac_parity.py does); run tests/test_qt_*.py, tests/test_engine*.py and whatever blast.py names.

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

