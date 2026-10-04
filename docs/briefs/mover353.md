# Brief pack — lane `mover353`

Base: main `a28611dc` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane mover353 — restore the sweep's mover instrument on v2 (issue #353), and close two loose ends

1. PORT `Ortho4XP/tools/airside_value_delta.py` (#353). It was deleted by v1cut commit 3f701d14 because it imported `auto_patch.elevation_per_surface.solver_primitives` (`PAVEMENT_ROLES`) and `auto_patch.solve_stage`; recover the source with `git show 3f701d14^:Ortho4XP/tools/airside_value_delta.py` (314 lines) and its twin with `git show 3f701d14^ --stat | grep airside_value_delta`.
   - Same CLI (`A.osm B.osm [--tol 0.01] [--top 20] [--json OUT.json]`), same canonical 11-decimal lat/lon join (never proximity), same two frames printed (ROW-SIDE and SOLVE-OWNED), same family table.
   - Every set is IMPORTED, never re-spelled (the census-wrapper precedent): the row-side partition still comes from `check_grade._GROUNDSIDE_ROLES` / `_ROAD_FAMILY_ROLES`; the solve-owned population must now come from v2's own definition of what the airside solve fixes. Find the v2 equivalent of v1's `PAVEMENT_ROLES` + stage A (start at `tools/harness/law_support/roles.py`, which `tools/blast.py` now uses as the role vocabulary, and `auto_patch_v2/law` / `constraints/routes.route_roles`). If v2 has no single equivalent, say so and report the candidates with their populations on one patch — that is an owner question, not a choice.
   - Acceptance: a twin that reproduces the recorded sw1027 → sw1028 SPJC result named in #353 (5 row-side movers, 0.05–0.06 m) from the registered frames (`tools/harness/frames.py list SPJC`), and a self-comparison that reads zero.
   - `tools/INDEX.md` still names the tool twice (rows near 148 and 151): restore its own row and make the mentions true.
   - Before writing anything new, check `tools/docq.py index` for a near-fit (`patch_proximity_diff`, `census_rows_diff`, `arm_site_read`); extend, do not fork.
2. STALE COMMENTS naming deleted bank law keys: `auto_patch_v2/emit/osm_adapter.py` ~675, `src/O4_Mesh_Utils.py` ~1149 and ~1821. Fix only statements that are now false.
3. ONE MISSED DUPLICATE: `auto_patch_v2/airport/placement_carrier.py` ~338 `gfind` is a plain union-find closure identical to `geom/union_find.find_root`. Replace it (AST-equal check first); `tools/ratchets.py --regenerate` afterwards, duplicate count must not rise above 10.
4. #344 SECOND HALF, measurement only. The frozen engine at `Ortho4XP/dist/Ortho4XP/` (1.50.1822, main 2f4159ff) is confirmed to contain `auto_patch.build_support`. NOT verified: that a WARM tile's vector step is scheduled as cached. Drive the frozen binary twice over one data root (`scripts/check_frozen_tile.sh ... --keep`) and read the second run's step schedule. Do NOT rebuild the frozen engine (`scripts/make_engine.sh` hides the venv and another session may be using it); if the frozen engine is missing or stale, report and skip.

No geometry changes: items 2 and 3 must leave output byte-identical — one replay of a registered HECA capture `--from classify --emit --verify` on your tree and on main is the check; no airport build.

Write for the next reader; size is a warning, not a gate; the duplicate ratchet is the gate (RULINGS 2026-10-04c).

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: branch, sha, the SPJC twin result, the solve-owned population decision (or the owner question), the #344 measurement, tests run, net lines, new public symbols, every item NOT done.

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

