# Brief pack — lane `diagout`

Base: main `49fca06e` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane diagout — diagnostics leave the engine package (RULINGS 2026-10-04c (4))

Goal: `Ortho4XP/src/auto_patch_v2` holds the engine; reporting that production never calls moves to `Ortho4XP/tools`. Engine output byte-identical.

Candidates measured by scout `v2growth` (line counts at 208380fd; re-measure): `pipeline/xplat.py` 1,014, `airport/placement_census.py` 968, `solve/design_report.py` 905, `planar/__main__.py` 697, `solve/why.py` 577, `airport/placement_seams.py` 410, `pipeline/why.py` 316, `pipeline/capture_state.py` 316, `classify/explain.py` 180, plus about six smaller files — roughly 6,050 lines. The scout found 266 of 274 v2 modules in the static production import closure; the other eight were CLIs and diagnostics reached only from tools.

Method, in this order:
1. FIRST DELIVERABLE, before moving anything: one table — each candidate, who imports it (production module, tool, test), and the verdict MOVE / STAYS (production calls it; name the caller) / SPLIT (a production-called part and a reporting part). Derive the production closure the way `tests/test_v1_retired.py` does; do not trust the scout's list. `pipeline/xplat.py` was IN the production closure: find out what production uses of it (stage digests?) and whether the cross-platform comparer half is test/tool-only.
2. Move what is MOVE to `Ortho4XP/tools` (one tool per responsibility; consult `tools/docq.py index <name>` first — several of these already have a tool front-end, and the front-end and the moved module should become ONE file, not two). For SPLIT, the production half stays under a name that says what it does and the reporting half moves.
3. Importers follow: tests under `tests/auto_patch_v2`, tools, `tools/v2_solve_replay.py`, the freeze specs (`Ortho4XP.spec`, `Ortho4XP_Qt.spec` hiddenimports) and `scripts/check_frozen_tile.py`. A moved module must not be needed by the frozen engine; if it is, it STAYS.
4. `tools/INDEX.md` rows in the same commit; `tools/artifact_contracts.json` if a writer path moves.
5. Issue #341 (fresh-import cycle when `airport/placement_body`, `placement_census` or `placement_cockpit` is imported first) sits in this neighbourhood: if moving `placement_census` resolves or exposes it, fix the cycle and add a twin that imports each v2 module first in a fresh interpreter; otherwise report what you found.

Closing: `tools/ratchets.py` passes; the standing suite; one replay of a registered HECA capture `--from classify --emit --verify` on your tree and on main (same hash, same verify rows); ONE HECA harness build with body hash equal to `sw1028_HECA` — the frozen-engine risk is why this lane builds.

Avoid: `src/O4_Airport_Elevation_Insets.py` (lane insetsplit), `tools/blast.py` / `tools/brief_pack.py` (lanes archmap, mover353), `src/auto_patch/` object-stage tests (lane objtests), `airport/placement_carrier.py` and `emit/osm_adapter.py` comments (lane mover353).

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: the MOVE/STAYS/SPLIT table, branch, sha, lines moved out of the package, the #341 finding, hash comparison, suite, net lines, new public symbols, every item NOT done.

## RULINGS

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

