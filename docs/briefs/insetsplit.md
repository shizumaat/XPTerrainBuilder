# Brief pack — lane `insetsplit`

Base: main `49fca06e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane insetsplit — one module per elevation provider (RULINGS 2026-10-04a (2), 04c)

`Ortho4XP/src/O4_Airport_Elevation_Insets.py` is 19,820 lines: 32 classes (7,547 lines), 290 top-level functions. Every provider lane appended to it. Measured by scout `v2growth` (line numbers at 208380fd; re-find by name):

- 25 `*Strategy` classes: 21 inset strategies with `discover(self, definition, bounding_box_wgs84)` and `fetch(self, definition, bounding_box_wgs84, target_resolution_m, destination_path)` (one exception: an extra `resolve` argument on `ArcgisFeatureTileStrategy.discover`); 4 base-tile strategies with `ensure_tile`; `OsGridBucketStrategy` subclasses `GeojsonTileIndexStrategy`.
- The interface is duck-typed, no base class. A registry already exists: `ACCESS_STRATEGIES` and `register_access_strategy`, looked up at about ten sites.
- Shared helpers by number of strategies using them: `warp_vsicurl_sources_to_geotiff` 20, `_raster_vertical_unit` 19, `_coverage_bbox_intersects` 19, `_geotiff_has_valid_data` 15, `ProviderUnavailable` 11, `_parse_float` 10, `raise_transient_discovery_failure` 9, `TransientFetchError` 8, `discovery_json_payload` 7, `cap_exceeded_unavailable` 7.
- About 1,656 lines of helpers are used by exactly ONE strategy (649 with LAS, 150 with TNM, 122 with AOI, 108 with ArcGIS export) and travel with it.
- About 8,500 lines move; about 11,300 lines of pipeline stay, themselves five or six responsibilities (resolution ladder, `ensure_airport_insets` + bake, building-footprint masking, water detection, acceptance probes / working grid, base-tile selection).

Deliver, behaviour UNCHANGED (a move, not a rewrite):
1. A provider package (name it for what it is; the scout's sketch: `base` = the two-method protocol and the error types, `registry` = the existing dict and decorator, `common` = the shared helpers, then ONE MODULE PER STRATEGY with its single-use helpers). The protocol becomes explicit (a `typing.Protocol` or ABC); the one signature exception is reported, not papered over.
2. A new provider is then a new file plus one registration — say in the package docstring exactly how.
3. Everything that imported a name from `O4_Airport_Elevation_Insets` keeps working: find every importer (src, tools, tests, `scripts/`, the Swift side does not import it) and either re-point it or keep a re-export, and say which you chose and why. Prefer re-pointing; a re-export shim is a second home for the same name.
4. THE FREEZER: strategies register themselves on import, so a module nobody imports statically never registers and the frozen app silently loses a provider (issue #344 is this exact class). The package must import every strategy module statically from one place, and a twin must assert that the set of registered strategy keys after import equals the set before the split (record it first, at main). Check `Ortho4XP.spec` / `Ortho4XP_Qt.spec` hiddenimports.
5. The cross-language wire protocol and `provider` names in data files (`*.elv` definitions, manifests, `dem_inset_provenance`) are strings: none may change. Grep the corpus-facing names before and after.
6. Second step, only if the first is green: split the remaining pipeline file by the five or six responsibilities above. If time or risk says stop after step 1, stop at a green commit and report — step 2 can be its own lane.
7. `tools/INDEX.md` rows where a tool names the file; `tools/ratchets.py --regenerate` (the insets file's entry falls; duplicates must not rise).

Tests: the insets test files (find them: `git grep -l O4_Airport_Elevation_Insets -- Ortho4XP/tests`), run once; no test may reach the network (conftest refuses). Closing: ONE CYXY harness build and one HECA harness build with body hashes equal to `sw1028_CYXY` / `sw1028_HECA` and the same `dem_inset_provenance` in the frame — no `--refresh-data`, no `--allow-degraded-dem`.

Avoid: `auto_patch_v2` (lanes diagout, mover353), `tools/blast.py` / `tools/brief_pack.py` (lane archmap).

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: branch, sha, the package layout with line counts, the registered-key comparison, importers re-pointed vs re-exported, the two hash comparisons, tests run, net lines, new public symbols, whether step 2 was done, every item NOT done.

## RULINGS

## 2026-10-04a — OWNER: FILE SIZE, RATCHETS AND THE ARCHITECTURE MAP (confirmed in session 2026-10-04; SUPERSEDES the numbers of 2026-09-13bz, keeps its sentence "split by responsibility, never fold comments to make a number"). MEASURED at main bc036d1e (tracked `.py` lines, comments and blanks included): v1 `src/auto_patch/` 130 files / 229,736 lines — the stage-B round-2 cut never landed (`claude/v1retire` @ 711f21b5, halted 2026-09-17, main 1,361 commits ahead; `tests/test_v1_retired.py` KEEP = 27 modules / 44,717 lines); v2 `src/auto_patch_v2/` 26,646 lines on 2026-09-05 → 113,478 (274 files; median 316, p75 594, p90 959, max 1,481; 23 files past 1,000); `O4_Airport_Elevation_Insets.py` 12,933 → 19,820 between 09-28 and 10-04 (eight provider strategy classes in one file, #130 #153 #154); 102 files under `Ortho4XP/src` past 1,000 lines. 13bz's twin covered `auto_patch_v2` only and refused at 1,500 — every other tree was unguarded. RULED: (1) **SIZE** — soft limit 600 lines (a PR that takes a file past it states why the file is not split); hard limit 1,000 lines for any NEW source file; a file already past 1,000 at the baseline is RATCHETED — it may shrink, never grow. Scope: `Ortho4XP/src`, `Ortho4XP/tools`, `tools`, `Sources`; tests are reported, not gated. (2) **ONE FILE PER FAMILY MEMBER** — a family (elevation providers, solver constraints, emit adapters, law tables) is a package with a base interface, a registry and one module per member; a new member is a new file, never an append. (3) **RATCHETS AT MERGE** — the size baseline and a duplicate count (functions with identical normalised bodies across files) may fall and never rise; v2's package order (plan table, 1 `airport/` … 7 `emit/`) becomes an import-direction check. (4) **THE MAP IS GENERATED** — `tools/blast.py --map <package>` / `--find <keyword>` from module docstrings and `__all__`; `tools/brief_pack.py` attaches the map of every package a brief touches; a twin fails a module with no docstring or no `__all__`. No hand-written class list. (5) **EVERY LANE REPORT / PR BODY** carries net lines added and removed and the new public symbols. ORDER: ratchets (lane `sizeratchet`) and the v1 cut (lane `v1cut`) in parallel, with scout `v2growth` attributing the 87k v2 lines; then the map tooling and layering check; then the insets split into a providers package.

## 2026-10-04c — OWNER: 1,000 LINES IS A GUIDE AND A WARNING, NEVER A GATE; BANK PASS DELETED; DIAGNOSTICS LEAVE THE ENGINE PACKAGE (amends 04b (1); decides three questions from scout `v2growth`). Owner (verbatim): "The 1000 line should be a guide and warning, not a hard limit that results in code being split just to meet it and resulting in more mess and confusion. The goal is splitting functionality, and writing clean, human readable, easy to understand code that also is the most efficient for each new session to fix and add to." RULED: (1) **SIZE NEVER FAILS A TEST OR A MERGE.** `tools/ratchets.py` reports files past 1,000 lines and files that grew, as a warning the master reads at merge; `--justify` stays as an optional note, not a pass condition. A split is made because a file holds two responsibilities, never to reach a number — the 71 v2 files that cite the line law in prose and the two at exactly 999 lines are the anti-pattern. The same applies to FUNCTIONS: 38 v2 functions run 200+ lines (`pipeline/build.py::build` 890, `planar/structures.py::build_structures` 867, `airport/placement_plan.py::build_splits` 833); they are reported the same way and are the better target. (2) **THE DUPLICATE RATCHET STANDS** (identical bodies may fall, never rise; near-duplicates reported): a second implementation of an existing thing is the defect this round exists to stop. (3) **THE BANK PASS IS DELETED** — `bank_omit = true` has shipped since 13cy; `emit/bank.py`, `emit/terrain_edge.py`, `emit/seam_band.py` and the bank law keys go, `coverage_polygon` (used by `emit/road_join.py`) moves to a geometry module. Output must be byte-identical. (4) **DIAGNOSTICS MOVE OUT OF `auto_patch_v2`** to `Ortho4XP/tools` (the why / explain / census / xplat reporting, ~6,050 lines) wherever production does not call them; anything production calls stays and is named. (5) **RULING-HISTORY PROSE IN SOURCE STAYS** as it is. MEASURED by scout `v2growth` at 208380fd: v2 113,478 lines = code 57.7%, docstring 20.7%, comment 12.3%, blank 9.2%; the plan budgeted 20,100 with no object-placement stage; growth since 09-05 is scope — object placement +27,541, structures +15,799, pads/platforms/terraces +11,765, groundside roads +6,809 (71% of +86,832); duplication ~500 lines, dead top-level symbols 1,036 (lower bound), gated-off ~1,700.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file. SIZE (owner 2026-10-04c, `tools/ratchets.py`): 1,000 lines is a guide and a
  warning, never a gate — the report (files past 1,000, files that grew, functions of
  200+ lines) is read by the master at merge. Split by responsibility, never to make a
  number. THE PRIORITY IS REUSE: small one-responsibility modules, no second
  implementation of a thing that exists (the identical-body duplicate count IS a gate:
  it may fall, never rise; `dupes --near` is reported).
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
  intent questions with their measurement; files touched; net lines added/removed
  + new public symbols (owner 2026-10-04a (5)).

