# Brief pack — lane `solvemodel`

Base: main `94762c4f` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Remove the solve_model (Airport elevation solve) setting — v1's solver switch, nothing in v2 reads it (owner RULINGS 2026-09-13bh).

## The brief

Owner 2026-09-13 (RULINGS 13bh): the `solve_model` cfg key ("Airport elevation solve", Iterative / Constructive — v1's solver switch) is REMOVED, exactly as stage A removed `auto_patch_engine` (RULINGS 13az, lane v1settings — read its diff: `git show 46a98f49 --stat` and the `O4_Cfg_Vars.py` / `O4_Config_Utils.py` / `SettingsLayout.swift` / `o4_schema_snapshot.json` / `build_airport.py` / `artifact_ledger.py` edits).

Do (each edit preceded by `Ortho4XP/venv/bin/python tools/blast.py <file>`):
1. `Ortho4XP/src/O4_Cfg_Vars.py`: delete the `solve_model` registry entry and its `cfg_tile_vars` registration; add `solve_model` to `retired_cfg_keys` so a tile/global cfg carrying it is CLEANED on read (one INFO line, no warning), as `auto_patch_engine` is.
2. `Ortho4XP/src/O4_Solve_Model.py`: delete the module; its readers — v1 `src/auto_patch/driver.py` (leave v1 code otherwise untouched: make the call site read the constant `"iterative"` or drop the argument if only v1 consumes it), v1 `route_profile/solve.py` (untouched if it only receives the value), `tools/harness/build_airport.py` and `tools/harness/artifact_ledger.py` (the ledger VARIANT KEY carries `solve_model` — keep the stored keys readable: the variant string keeps a constant `solve_model=iterative` component so existing artifacts still key, as v1settings kept `"v2"` for the engine), `O4_Settings_Model.py` (retired-key drop already generic).
3. Swift: `Sources/XPTerrainBuilder/SettingsLayout.swift:97` `SettingItem("solve_model", …)` deleted; regenerate `Sources/SceneryKit/Resources/o4_schema_snapshot.json` the way v1settings did; `swift build` (make_app.sh's DEVELOPER_DIR default now exports Xcode-beta; use `DEVELOPER_DIR=/Applications/Xcode-beta.app swift build`).
4. Twins: cfg carrying `solve_model = constructive` loads clean (key gone, no warning); `grep -rn solve_model Ortho4XP/src Sources` → only the retired-key line and the ledger's constant; existing ledger artifacts still resolve (a twin over `artifact_ledger`'s variant key).
Closing test: ONE CYXY build through the harness — body_sha identical to a base arm at your base sha (`--base-arm`); suite twice.

## Bars

- `grep -rn solve_model Ortho4XP/src Sources Ortho4XP/tools` → the retired-key cleaner line and the ledger's constant variant component only.
- A tile cfg carrying `solve_model = constructive` loads clean and builds; no warning.
- CYXY body_sha identical to the base arm; `[guard] shared repo UNCHANGED`.
- `swift build` succeeds; the "Airport elevation solve" row is gone.
- Suite twice: `tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_engine_dispatch.py tests/test_legacy_cfg_values.py tests/test_settings_model.py`.
- v1 modules otherwise untouched (`git diff --stat <base> -- Ortho4XP/src/auto_patch/` shows only the driver's call site).

## Files

Yours: `Ortho4XP/src/O4_Cfg_Vars.py`, `Ortho4XP/src/O4_Solve_Model.py`, `Ortho4XP/src/auto_patch/driver.py`, `Sources/XPTerrainBuilder/SettingsLayout.swift`, `Ortho4XP/tools/harness/build_airport.py`, `Ortho4XP/tools/harness/artifact_ledger.py`

## RULINGS

## 2026-09-13bh — OWNER (verbatim): "Yes, elevation_method should be removed." (the `solve_model` key, "Airport elevation solve" — Iterative / Constructive — v1's solver switch; readers: v1 `driver.py`, v1 `route_profile/solve.py`, the harness ledger variant key, the Swift Settings row; nothing in v2) — RULED: removed as stage A was (registry entry, retired-key cleaning, Settings row + schema snapshot, ledger variant key, `O4_Solve_Model.py` gone) — lane `solvemodel`, brief pack `docs/briefs/solvemodel.md`.

## 2026-09-13az — v1settings MERGED (feecb525, lane 46a98f49): STAGE A of the v1 retirement (13au) — `auto_patch_engine` gone from `O4_Cfg_Vars` (a tile cfg still carrying `auto_patch_engine = v1` has the line DELETED on read with one INFO `removed retired key …`, no warning, no attribute; `O4_Settings_Model.write_global` already drops retired keys); `resolved_auto_patch_engine()` → `"v2"` unconditionally; `driver.py`'s selector and `O4_Mesh_Utils`' post-mesh dispatch v2-only (the v1 arm `post_mesh.rebake_dsf_objects` no longer called; the modules stand, unreachable); the Swift Settings row and the five `o4_schema_snapshot.json` entries gone (`swift build` complete; Qt never named the key — it renders from the registry); `build_airport.py --engine` DELETED (`--dem`, `--geometry-only`, `--solve-capture` — v1-only wirings — refused BY NAME rather than left inert; the constant-DEM oracle world is a v2 wiring item if wanted); `frame.json` and the artifact-ledger variant key keep the spelling `"v2"` so stored arms still key. CYXY no-flag vs base `--engine v2`: body `fc59980475f5` BOTH, patch `cmp`-clean, 315 ways / 4,703 nodes / 311 verify rows, law digest `8e1c95e96b37` both. `tests/test_auto_patch_engine_is_global.py` deleted; twins in `test_auto_patch_engine_dispatch.py`, `test_legacy_cfg_values.py`, `test_harness.py`. Merge conflict: `docs/frames.jsonl` (append-only; union, 9 rows). One red after the merge, fixed by the session: `test_post_mesh.py::test_mesh_hook_swallows_exceptions` monkeypatched the v1 hook the guard no longer calls — re-pointed at `engine_v2.rebake_after_mesh` (the property, a swallowed re-seat failure, unchanged). Suite 1,499/0 twice on main (the wider set incl. the cfg/settings/provenance twins). The brief-pack lane: 107 tool uses, 221k tokens — against 350k–550k for today's fresh lanes on the old startup. STAGE B (13aw) waits for the owner's 1.0.327 read. Owner question open: `elevation_method` (`O4_Cfg_Vars.py:225`, Iterative/Constructive, v1-only) — retire with stage B unless the owner says otherwise.

## Tool: lane_worktree

| `Ortho4XP/tools/harness/lane_worktree.sh` | You are setting up (`up`), auditing (`check`), reporting (`data`) or tearing down (`down`) a lane worktree. `up`/`check`/`down` take a NAME **or a PATH** (absolute or relative — anything with a slash), resolved through `git worktree list` rather than a hard-coded parent dir (2026-08-27): a Claude Code chip session's worktree lives NESTED at `<repo>/Ortho4XP/.claude/worktrees/<name>`, not `$MAIN_REPO/.claude/worktrees/<name>`, and the PATH form mounts the shared corpus into that EXISTING tree (the `up ../../Ortho4XP/.claude/worktrees/…` relative-NAME workaround this retires); a bare NAME finds the unique registered worktree with that basename wherever it lives, else creates at `$MAIN_REPO/.claude/worktrees/NAME` as before. A path that is not a registered worktree, an ambiguous name, the main repo itself, and a REF combined with the PATH form all refuse loudly; `data` enumerates every registered worktree, chip trees included. Twin: `tests/test_harness.py` §4 (`test_the_ritual_accepts_an_existing_worktree_by_path`). Mounts the WHOLE shared data repo (enumerated from it, never hard-coded), symlinks `venv` from the main engine tree, clones `Patches` + `Ortho4XP.cfg` as lane-local, audits untracked paths, and refuses teardown while a process or a shared-repo lock holds the tree. `data` reports which trees are on the shared corpus and which are private. **It also makes THIS FILE reachable in the lane** (2026-08-06): a worktree checked out at a ref that predates the tracked `tools/INDEX.md` gets a read-only MIRROR of the main tree's, and `check` reports MISSING (a failure, with the fix) / STALE / DIFFERS — a lane that cannot read the index consults nothing and forks the near-fit, which is precisely what rule 1 above is for. A TRACKED index is never overwritten: editing it IS how a lane lands its promotion. |

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; files under 1,000 lines.
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

