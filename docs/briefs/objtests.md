# Brief pack — lane `objtests`

Base: main `49fca06e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane objtests — re-found the object-stage tests the v1 cut removed (RULINGS 2026-10-04j "coverage owed")

The v1 cut (PR #350) retired every test that could not run without a deleted v1 module. That rule cut suites whose SUBJECT is kept code, because they built their inputs from v1 record classes:

| File | Tests before → after |
|---|---|
| `tests/test_object_basin_trench.py` | 282 → 88 |
| `tests/test_object_bridge_terrain.py` | 148 → 9 |
| `tests/test_post_mesh.py` | 49 → 18 |
| `tests/test_object_pads.py` | 42 → 1 |
| `tests/test_round12_bridge_deck_datum.py` | 41 → 7 |
| `tests/test_basin_group_seat.py` | 33 → 6 |

Sweep sw1029 listed production-reachable names with NO test reference left: `post_mesh._abutment_grade_samples_on_land`, `_abutment_line_frame_points`, `_candidate_grade_line_sets`; `object_terrain_features.PortalFaceStructure`, `region_polygon_in_frame`; `object_rebake.founded_seat_datum`; `agp_reader._scenery_pack_order`; `dsf_reader.find_associated_dsf`; `config.transverse_cap_for_longitudinal_cap`. Read the ruling: `tools/docq.py ruling 2026-10-04j`.

Deliver:
1. FIRST DELIVERABLE, a table, before writing any test: for the kept object stage (`src/auto_patch/post_mesh.py`, `object_rebake.py`, `object_anchor.py`, `object_frame.py`, `object_clusters.py`, `object_footprints.py`, `object_terrain_features.py`, `object_terrain_kinds.py`, `obj8_partition.py`, `mesh_sampler.py`) and the readers — each public or production-called function, whether production REACHES it today (trace from `engine_v2.rebake_after_mesh` and `driver.generate_auto_patches`; a coverage run of one registered HECA or OTHH replay through the object stage is the measurement, static reading is the fallback), and whether a test covers it. Three verdicts: COVERED / REACHED-UNCOVERED / UNREACHED.
2. For REACHED-UNCOVERED: tests. Recover what the deleted tests asserted with `git show 3f701d14^:Ortho4XP/tests/<file>` (the commit before the cut) and re-found each on inputs the kept code actually receives today — v2's rebake plan / the records `engine_v2` hands over — not on resurrected v1 classes. Port the assertion, not the scaffolding. Shared builders go in ONE test helper module, not copied per file.
3. For UNREACHED (the v1-shaped facility-record arms in `post_mesh` that nothing constructs): list them with the evidence. Do NOT delete them in this lane — deletion is a separate decision the master takes with your table.
4. The nine named functions each end with a verdict and, if reached, a test.
5. `tests/test_auto_patch_engine_dispatch.py` fails 5 when run ALONE (order-dependent, pre-existing): find the missing setup and fix it if it is a test-isolation defect; report if it is a product defect.

Tests are headless: `tmp_path`, no network, no X-Plane install, no shared-repo write (conftest enforces all three); text I/O names `encoding=` and `newline=`. No source changes except a seam a test genuinely needs — report any. No airport build: this lane changes no engine output.

Avoid: `auto_patch_v2` (lanes diagout, mover353), `O4_Airport_Elevation_Insets.py` (lane insetsplit), `tools/` (lanes archmap, mover353).

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: the reach/coverage table (counts per verdict), branch, sha, tests added per file, the UNREACHED list with line counts, the dispatch-test finding, suite numbers, net lines, every item NOT done.

## RULINGS

## 2026-10-04j V1CUT MERGED (1199d413, PR #350, peer-session lane v1cut 45dcbade; owner: "Proceed with v1cut now") + SWEEP sw1029 vs sw1028 — REFERENCES UNCHANGED (sw1028 stands). `Ortho4XP/src/auto_patch` 131 files / 229,735 lines → 27 / 40,938; 213 test files and 65 tools retired; 505 files, +861 / −320,685. SWEEP (six builds rc 0, optimal, shared repo UNCHANGED, none CONTAMINATED): every patch body byte-identical to sw1028 (CYXY 2a00c361ffc2, SPJC 9d611f11e04b, KCLT 1af240b658b6, KASE 738c2a8ceb64, HECA 7022b0b18461, NLWF 84be89f8b7bc), censuses identical; NLWF tile path (`--tile -15 -179`: vector + auto-patch + mesh; imagery/DSF stood down) patch body equal. Non-Qt suite 8033 passed / 3 failed (the three facade reds, fixed on main 1d640468), Qt 309 passed, blast audit PASS, duplicate ratchet PASS, 371 src modules import (2 fail identically on main: `O4_Geotag`, `placement_body` in isolation #341). Also this day — #337 surface gate PULLED from Beta 2 (OTHH runway 33 nodes / 0.30 m; no one-site fix; branch `claude/surface337` 2f348508, findings on the issue). OWED: (a) FROZEN CHECK — no frozen build was ever run on v1cut; #344 (`auto_patch.osm_load` named as a string in `o4_engine/parallel.py`, now `auto_patch.build_support`) is inferred from source; `Ortho4XP_Qt.spec` edited but never frozen — run `make_engine.sh` + `check_frozen_tile.sh` before the next app build and read CI's frozen jobs. (b) COVERAGE: production-reachable names that lost every test reference in the cut — `post_mesh._abutment_grade_samples_on_land`, `_abutment_line_frame_points`, `_candidate_grade_line_sets`; `object_terrain_features.PortalFaceStructure`, `region_polygon_in_frame`; `object_rebake.founded_seat_datum`; `agp_reader._scenery_pack_order`; `dsf_reader.find_associated_dsf`; `config.transverse_cap_for_longitudinal_cap` — the six builds are their only evidence, and no bridge/tunnel tile (OTHH) was built in this sweep. (c) `Ortho4XP/tools/attic/bridge_deck_audit.py:196` imports a deleted constant; stale entries in `tools/ratchet_baseline.json` (48) and `tools/artifact_contracts.json` (5).

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

