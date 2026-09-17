# Brief pack — lane `betapolish`

Base: main `4a079792` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta plan lane betapolish

## The brief

## Lane betapolish — plan §2 + §3 engine/Qt items, round 1 (NO release.yml, NO AppImage/icon this round — those follow betaversion's merge)
Deliver, one commit each:
1. Qt AutoPatchFailed handler — the one real parity gap. Swift prints the live per-airport line (Sources/XPTerrainBuilder/BuildModel.swift:680-688: "*** Tile …: airport X failed at the <stage> stage — <error>"); Qt's handler table (Ortho4XP/src/O4_Qt_GUI.py:684-694) lacks EV.AutoPatchFailed. Mirror the Swift wording; twin offscreen.
2. Qt persists engine stderr: today _StdoutTee (O4_Qt_GUI.py:470-478, installed ~:671) tees stdout only. Tee stderr to <data root>/logs/engine-stderr.log with 20 MB rotation (the Swift side: OrthoEngineClient.swift:615-664 EngineStderrLog — same size, same rotation rule). Twin.
3. O4_Config_Utils.py:175-195 make_dirs: a dangling symlink (os.path.islink and not os.path.exists) reports "tile directory is a symlink whose target is missing: <link> -> <target> (is the volume mounted?)"; replace the bare except with except OSError as e and include e in the message; keep raising so session.py's handler still surfaces a tile error. Found in the wild 2026-09-16 (VHHH, unmounted external volume, misreported as permissions). Twin with a tmp dangling link.
4. Linux 7z: O4_Overlay_Utils.py:19-31 falls back to a bare "7z" that Utils/lin does not vendor. Probe 7zz, 7z, 7za on PATH at use time; when none exists REFUSE with one line naming the package (p7zip-full / 7zip) instead of a FileNotFoundError deep in extraction. Do not vendor a binary this round. Twin.
5. Imagery/network failure is stated, not silent: O4_Imagery_Utils.py:1191-1200 logs connection failures at verbosity 2-3 and the tile completes with blank textures. At the END of a tile's imagery step, if any texture is missing/failed, emit ONE UI.loud_warning line with the count and the provider (loud_warning already reaches both UIs' consoles and Ortho4XP.log). Do NOT add a new wire event this round. Twin on the counting function.
6. Ortho4XP.spec: add hash_seed=0 to the EXE options exactly as Ortho4XP_Qt.spec:143 carries it (comment: both frozen engines carry the same belt). Spec must still parse (ast.parse). You cannot freeze; say so.
7. Docs an outsider will trust: README.md status paragraph (~:134-137 says "Prototype") rewritten to the beta state (three platforms, mac signed+notarized, arm64-only, Windows SmartScreen note); Ortho4XP/docs/DEFERRED_VERIFICATION.md:204 two stale claims corrected (the mac app HAS a provider sign-in UI: SettingsView.swift ProviderSignInSheet; _reaudit_conflict HAS UI callers: O4_Qt_GUI.py ~1782, ~1829) — verify each by grep before editing; add a dated "historical — see docs/BETA-PLAN-20260916.md" banner line at the top of Ortho4XP/docs/OPEN_ITEMS.md. Do NOT load Ortho4XP/STATUS.md whole (~90k tokens); leave it alone.
Closing tests: tests/test_qt_*.py offscreen, tests/test_engine*.py, your new twins, and whatever blast.py names for each file; quote the pass line and any FAILED names verbatim. Line numbers above may have drifted; re-find them.

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

