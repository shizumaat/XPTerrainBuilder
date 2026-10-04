# Brief pack — lane `v2trim`

Base: main `900727f2` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane v2trim — remove what v2 does not need, share what it repeats (RULINGS 2026-10-04c (2)(3))

Engine output must be BYTE-IDENTICAL: nothing here changes geometry. Source: scout `v2growth` at 208380fd (line numbers may have moved; re-find by name).

Commit each item separately, tree green at each commit.

1. BANK PASS DELETION (04c (3)). `law/emit.toml` has `bank_omit = true` (shipped since 13cy); the pass returns the surface unchanged at `emit/bank.py` ~673. Delete `emit/bank.py`, `emit/terrain_edge.py`, `emit/seam_band.py`, the bank law keys and schema (`law/design_schema.py` ~249), and their tests. `coverage_polygon` is live (`emit/road_join.py` ~89 uses it): move it to a geometry module first. The scout did NOT verify that `terrain_edge` / `seam_band` have no path live under `bank_omit = true` — verify by reading every call site before deleting, and report anything that turned out live instead of deleting it.
2. DEAD SYMBOLS. Re-derive, then delete with their tests: no reference anywhere (26 symbols, 340 lines; e.g. `airport/placement_atom.py` `unit_clusters`, `airport/object_cut.py` `wall_polyline`, `airport/line_object.py` `station_delta`, `constraints/taxi.py` `all_pairs`, `constraints/no_step.py` `pad_only_vertices`) and referenced only from tests (26 symbols, 696 lines; e.g. `airport/placement_family.py` `bind_families` 246 and `_union_area_m2_reference`, `planar/channel_claims.py` `channel_claiming`, `airport/riders.py` `agp_half_extent_m`). Leave `pipeline/xplat.py` alone (a later lane moves diagnostics). The scout matched by name only: confirm each with grep over `src`, `Ortho4XP/tools`, `tools` and the Swift sources before deleting; a symbol used by a tool is not dead.
3. THE DRIFTED PAIR (correctness, do this carefully). `_footless_targets` is identical in `airport/placement_body.py` (~545) and `airport/placement_targets.py` (~23). `_carrier_pieces` exists in both (`placement_body.py` ~572, `placement_targets.py` ~50) and the copies now DIFFER; `placement_plan.py` ~77 imports the targets copy, `placement_cut.py` ~905 the body copy. Attribute first: diff the two, find the commit that made them diverge, and determine by replay (`tools/v2_solve_replay.py`, registered captures via `tools/harness/frames.py list`) whether the difference changes any output. If one implementation serves both callers with identical output, keep one. If the difference is behavioural, do NOT pick: report both behaviours with the measurement — that is an owner question.
4. SHARED HELPERS — one implementation each, in the module where a reader would look for it: the union-find `find` closure (27 copies, e.g. `airport/placement_atom.py`, `airport/placement_carrier.py`, `solve/rows.py`, `planar/structure_deck.py`); file sha256 (`airport/dsf_write.py`, `airport/pack.py`, `airport/backup_state.py`, `airport/partition_cache.py`); `_line_parts` (`classify/evidence.py`, `classify/roles.py`, `classify/ribbon_mint.py`); `_unit`/`_dir` (`airport/door_wells.py`, `airport/tunnel_walls.py`, `planar/structure_approach.py`, `planar/structure_geometry.py`); `_dem` and `_parts` across `planar/`; `_bearing`; `_inside`; `_dem_many`; `_governed_vertex` (`constraints/channel.py`) = `_deck_cell_vertex` (`constraints/structures.py`). Check `geom/` for an existing home before creating one. Names should say what the helper does.

Closing: `tools/ratchets.py` passes with the duplicate count LOWER (then `--regenerate`); the standing suite; ONE HECA run through the harness entry with the patch body hash equal to a same-tree control per the patch A/B law and the census identical to the registered sw1026 reference.

Avoid: `Ortho4XP/src/auto_patch/` (v1; lane v1cut is deleting most of it), `tools/ratchets.py` (lane sizeratchet round 3 is editing it), and moving diagnostics (a later lane).

Write for the next reader: clear names, one responsibility per module. Do not split or fold anything to reach a line count (04c (1)).

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: branch, sha, per-item lines removed, duplicate counts before/after, the `_carrier_pieces` finding, the hash/census comparison, net lines added/removed, new public symbols, every item NOT done.

## RULINGS

## 2026-10-04c — OWNER: 1,000 LINES IS A GUIDE AND A WARNING, NEVER A GATE; BANK PASS DELETED; DIAGNOSTICS LEAVE THE ENGINE PACKAGE (amends 04b (1); decides three questions from scout `v2growth`). Owner (verbatim): "The 1000 line should be a guide and warning, not a hard limit that results in code being split just to meet it and resulting in more mess and confusion. The goal is splitting functionality, and writing clean, human readable, easy to understand code that also is the most efficient for each new session to fix and add to." RULED: (1) **SIZE NEVER FAILS A TEST OR A MERGE.** `tools/ratchets.py` reports files past 1,000 lines and files that grew, as a warning the master reads at merge; `--justify` stays as an optional note, not a pass condition. A split is made because a file holds two responsibilities, never to reach a number — the 71 v2 files that cite the line law in prose and the two at exactly 999 lines are the anti-pattern. The same applies to FUNCTIONS: 38 v2 functions run 200+ lines (`pipeline/build.py::build` 890, `planar/structures.py::build_structures` 867, `airport/placement_plan.py::build_splits` 833); they are reported the same way and are the better target. (2) **THE DUPLICATE RATCHET STANDS** (identical bodies may fall, never rise; near-duplicates reported): a second implementation of an existing thing is the defect this round exists to stop. (3) **THE BANK PASS IS DELETED** — `bank_omit = true` has shipped since 13cy; `emit/bank.py`, `emit/terrain_edge.py`, `emit/seam_band.py` and the bank law keys go, `coverage_polygon` (used by `emit/road_join.py`) moves to a geometry module. Output must be byte-identical. (4) **DIAGNOSTICS MOVE OUT OF `auto_patch_v2`** to `Ortho4XP/tools` (the why / explain / census / xplat reporting, ~6,050 lines) wherever production does not call them; anything production calls stays and is named. (5) **RULING-HISTORY PROSE IN SOURCE STAYS** as it is. MEASURED by scout `v2growth` at 208380fd: v2 113,478 lines = code 57.7%, docstring 20.7%, comment 12.3%, blank 9.2%; the plan budgeted 20,100 with no object-placement stage; growth since 09-05 is scope — object placement +27,541, structures +15,799, pads/platforms/terraces +11,765, groundside roads +6,809 (71% of +86,832); duplication ~500 lines, dead top-level symbols 1,036 (lower bound), gated-off ~1,700.

## 2026-09-13cy Owner: "turn off bank foot emission for the next build so i can see output" — `bank_omit = true` shipped in app 1.0.330

* `[design] bank_omit = true` on main for the 1.0.330 build (the OMIT arm
  of 13cw as the shipped setting); the twin asserts true with this
  ruling. The owner's sim read of 1.0.330 is the bank class's
  adjudication: keep (flip back false, then the edge-grading law the
  census can measure) or delete.
* Every airport's patch edge in 1.0.330 is the design ring meeting the raw
  DEM over one triangle (LEMD: 2,584 steps > 3 m, worst 19.9 m) — expected,
  not a regression to report.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file. SIZE (owner 2026-10-04a/04b, `tools/ratchets.py`): no hard limit, but modules
  past 1,000 lines should be rare — a file that passes 1,000, or one already past it
  that grows, needs a recorded justification (`tools/ratchets.py --justify PATH "why"`,
  in the diff the master reviews); 600 is a reported soft band. THE PRIORITY IS REUSE:
  small one-responsibility modules, no second implementation of a thing that exists
  (the duplicate count is ratcheted; `dupes --near` is reported). Never fold comments
  to make a number.
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

