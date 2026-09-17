# Brief pack — lane `disabledpacks`

Base: main `0604641d` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

A scenery pack disabled in scenery_packs.ini is ignored by the build (RULINGS 2026-09-17b)

## The brief

## Lane disabledpacks — OWNER RULED (RULINGS 2026-09-17b): a scenery pack DISABLED in scenery_packs.ini is IGNORED by the build

The consumer census is DONE (scout, 2026-09-17, main bc30688b, file:line measured). It is
your spec; do not re-derive it, verify a line only when you are about to edit it.

### The census table (condensed; HONOURS = reads the ini and excludes disabled today)
apt.dat selection — ONE selector since RULINGS 17a:
- A1 `src/auto_patch_v2/airport/apt_dat.py:278 find_apt_dat` — `sorted(os.listdir(Custom Scenery))`, first pack with row-110 for the ICAO, else first carrying it, else Global. **BLIND.** Everything below inherits from it:
  A2 `auto_patch/engine_v2.py:99 select_apt_dat`; A3 `auto_patch/osm_load.py:596`; A4 `driver.py:1389-1397` (worklist + the skip line that already says "no enabled scenery pack defines it"); A5 `driver.py:280-284` freshness gate; A6 `flat_site_mode.py:705`; A7 `driver.py:605` object-anchor worklist STEP 1; A8 `auto_patch_v2/airport/pack.py:92-108 select_pack`.
- A10 `auto_patch/apt_dat_reader.py:668 find_all_airport_apt_dats` (one live caller: `pavement_scoring.py:621`) — BLIND.
- A11 `apt_dat_reader.py:365 find_airport_apt_dat` — BLIND; production-dead, but `tools/harness/build_airport.py:3127` calls it: FILTER it, do not delete.
- A9 §44 borrow (Global block) and A12 `O4_Airport_Index.py:126` (never scans third-party packs): NO CHANGE.
Object/DSF side:
- B3 `driver.py:411-451 _enabled_airport_pack_tile_dsfs` — HONOURS (`:444`), ini order, unlisted packs appended sorted. THE MODEL.
- B6 THE WRITE: `auto_patch/object_rebake.py` writes `.obj/.dsf/.anchor_bak`/split bodies INTO the pack; its pack set = worklist = A7 ∪ B3. Step 1 (A7) is blind ⇒ **today a DISABLED pack can be REWRITTEN when it wins A1.** Fixing A1 closes it; add a belt: the rebake refuses (names and skips) a pack outside the enabled set.
- B5 flat-site claimed placements: honours step 2, blind step 1 — closed by A1.
- B9 `O4_Airport_Elevation_Insets.py:6426 _disabled_custom_scenery_pack_names` — HONOURS; switch to the shared module.
- B8 `auto_patch/object_terrain_assembly.py:355 _discover_sibling_road_networks` — BLIND, and the scout found NO live importer of the module (v1 retired). Confirm by symbol census; if dead, leave it alone and report (deletion is the v1-retirement lane's), if live, filter it.
- **E1 (a real defect): `auto_patch/agp_reader.py:93`** tests `line.startswith("SCENERY_PACK")`, which `SCENERY_PACK_DISABLED` also satisfies ⇒ disabled packs enter the merged library.txt priority order and can WIN a virtual library path over an enabled pack (objects the sim never draws supply geometry). Exact-token test; exclude disabled.
UIs (C1 Qt `O4_Custom_Scenery.py:104,235` + `O4_Qt_GUI.py:1747-1891`; C2 Swift `Sources/SceneryKit/InstallationScanner.swift:194-199,295-318`): both HONOUR by DIMMING and must KEEP LISTING disabled packs (that is how a user re-enables one). NO UI change in this lane (owner question open on the gray Global mark).
Freshness: F1 `driver.py:367-404 _scenery_pack_state` stamps `<pack>|enabled/disabled` and `driver.py:284` compares the selected path ⇒ once A1 honours the ini a toggle INVALIDATES the patch by both routes (assert it in a twin). F3 ini cache keyed on (path, mtime, size); F4 library sidecar fingerprints the ini — both already self-invalidate. F7 DEM insets move only under `--refresh-data dem` — a stated limitation, no change.
FOUR Python ini parsers today: `driver.py:329-363`, `O4_Custom_Scenery.py:104-121`, `O4_Airport_Elevation_Insets.py:6426-6446`, `agp_reader.py:69-107`.

### The ONE derivation site
NEW `Ortho4XP/src/O4_Scenery_Packs.py` — stdlib only, imports NO `O4_*` and NO `auto_patch*` (auto_patch_v2 imports zero v1 modules by law, `auto_patch_v2/airport/pack.py:1-21`; agp_reader must stay importable with no Ortho4XP modules on sys.path, `agp_reader.py:203-209`; a top-level `O4_*` module is reachable from both engines lazily, e.g. `airport/dem_production.py:550`). API: `parse_ini(ini_path) -> (ordered_names, disabled_names)`; `enabled_pack_names(custom_scenery_dir) -> set[str]`; `pack_enabled(pack_path_or_name, custom_scenery_dir) -> bool`; `custom_scenery_dir_for(path) -> str | None` (the walk-up at `driver.py:390-394`).
RULES (session assumptions, each already the behaviour of at least one reader; Swift `InstallationScanner.swift:197-198` is the reference):
- ini ABSENT/unreadable ⇒ every on-disk pack enabled.
- `SCENERY_PACK` ⇒ enabled; `SCENERY_PACK_DISABLED` ⇒ excluded — EXACT first token, never startswith.
- on disk but NOT LISTED ⇒ enabled (X-Plane adds new packs enabled; ~2,501 of the owner's 4,222 entries are unlisted).
- listed but absent, or a DANGLING SYMLINK (2,502 of the owner's entries are symlinks onto a removable volume; all dangle when it is unmounted) ⇒ not in the set, NEVER an error (`os.path.isdir` semantics).
- `*GLOBAL_AIRPORTS*` (XP12's virtual entry) and any path not under `Custom Scenery/` are not pack names; `Global Airports`, `Global Scenery/`, `Resources/default scenery/` are never filtered.
- A sole-source disabled pack ⇒ the airport falls back to Global Airports (it is still built, from what the sim draws). A zero-pavement enabled winner keeps §44's borrow — NO §44 change.
A frozen bundle must see the module: a TOP-LEVEL `import O4_Scenery_Packs` in whichever frozen-visible module first needs it, or function-level imports made visible by a hiddenimports entry in BOTH specs (Ortho4XP.spec, Ortho4XP_Qt.spec) — the lazy-import class shipped broken on 2026-09-10; say which you did. `tests/test_frozen_spec_parity.py` exists.

### Edit order (no airport build needed for any of it)
1. `O4_Scenery_Packs.py` + `tests/test_scenery_packs.py` (absent ini, unlisted, dangling symlink, `*GLOBAL_AIRPORTS*`, token exactness, Windows-style backslash paths, a pack named with a trailing slash).
2. `auto_patch_v2/airport/apt_dat.py:296-305` — filter the listdir loop. Twins: a disabled pack never wins; sole-source disabled ⇒ Global; toggling the ini flips the selection AND `_auto_patch_is_current` goes False (tests/test_auto_patch_freshness.py, tests/auto_patch_v2/test_airport_load.py, tests/test_auto_patch_apt_dat_integration.py, tests/test_apt_dat_reader.py).
3. `agp_reader.py:93` — E1 (tests/test_agp_reader.py; it already has ini reorder/remove invalidation tests at :358/:370).
4. `apt_dat_reader.py` — filter `find_all_airport_apt_dats` and `find_airport_apt_dat`.
5. Delegate the three remaining parsers to the module, behaviour-preserving (`driver.py:329`, `O4_Custom_Scenery.py:104` — it keeps REPORTING disabled packs, `O4_Airport_Elevation_Insets.py:6426`): tests/test_auto_patch_freshness.py:572-618, tests/test_post_mesh.py:874-1019 and :1030, tests/test_custom_scenery.py, tests/test_airport_elevation_insets.py:4300-4340.
6. The rebake belt (B6): refuse a pack outside the enabled set, named on the log line; twin.
7. The skip line `driver.py:1395` stays as worded (it is now true). Swift: no code change; add ONE parity assertion that Swift and Python agree on the four edge rules (tests/test_qt_mac_parity.py:160 is the pattern; `Tests/SceneryKitTests/PackActionsTests.swift:153` already pins `*GLOBAL_AIRPORTS*`).

### Closing (no harness airport build — the flipping airports are not campaign airports and their tiles are cold)
- READ-ONLY measurement on the owner's install (`/Users/noah/X-Plane 12`, never write there): call the real `find_apt_dat` for LFMN, LPFR, EBBR, OBBI, OBBS, LEAM, EGLH, GEML before (main) and after (your branch) and print the table. Expected from the census: LFMN → `c_FRA - 100_airport - LFMN_JustSim_XPL12_v1.0`; LPFR → `aaa_Boundless_LPFR_Airport`; EBBR → `…EBBR_JustSim_2.0`; OBBI/OBBS/LEAM/EGLH → Global Airports; GEML unchanged. A mismatch is a finding — report it, do not tune toward the table.
- `tools/blast.py` for every edited src file and run what it names; the standing suite once (`tools/brief_pack.py` STANDING line), FAILED lines verbatim; tests/test_qt_*.py offscreen; tests/test_frozen_spec_parity.py.
- RULINGS: do NOT write one (the session records the merge under the next free 2026-09-17 key).

Rules: worktree from Ortho4XP/ `tools/harness/lane_worktree.sh up disabledpacks`; merge main first. The bash guard refuses engine test commands whose effective cwd is not an Ortho4XP/ with venv and OSM_data (run tests from your worktree's Ortho4XP/ in their own call), pattern-matches test-runner words inside heredocs (write files with the Write tool) and refuses `git stash`. Release Xcode only; never quit the owner's app; never run make_app/make_engine; no push; commit early, one commit per edit-order step; do not merge. Lane betawinsettings is editing O4_Qt_Settings.py / O4_Qt_Wizard.py — do not touch those or `.github/workflows/`. Report branch + sha, the before/after selection table, each closing check's pass line with FAILED names verbatim, how the frozen bundle sees the new module, and everything not done.

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

