# Brief pack — lane `wtclone338`

Base: main `6673a1e8` · generated 2026-10-04 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## The brief

# Lane wtclone338 — a worktree must not cost 29 GB (issue #338)

Measured 2026-10-04 (data volume 99% full, 26 GB free): the main tree's `Ortho4XP/tmp/engine_caches/Airport_mod_cache` is 28,999 MB (0 symlinks, dated 2026-08-15); `tools/harness/lane_worktree.sh up` clones every subdirectory of `tmp/` into the new worktree with `cp -R` (near line 402; `NEVER_MOUNT="Patches Tiles Previews tmp"`), so each of six live worktrees holds its own ~29 GB copy (`.claude/worktrees` = 194 GB).

The owner asked whether each worktree's copy can be a LINK to the one shared cache. A symlink cannot: it was tried and failed — the engine's sidecar writers truncate in place and wrote THROUGH symlinks into the shared corpus (measured 2026-08-12, seven OTHH sidecars; see `tools/harness/build_airport.py` `lane_cache_root` / `redirect_engine_caches` / `mirror_tree_as_overlay` docstrings). The lawful equivalent already exists in the harness: APFS copy-on-write clones (`clonefile`) — shared blocks, no extra disk until a file is rewritten, and a write lands lane-local.

Deliver:
1. `lane_worktree.sh up` no longer makes a full copy of `tmp/engine_caches`. Either clone it copy-on-write (`cp -cR`, verifying it is on APFS and falling back loudly, not silently, where clonefile is unavailable) or leave it out and let `redirect_engine_caches` seed the overlay on first build — choose by reading what the first build then costs (the lane-persistent root exists so `_compute_dsf_object_buildings` is not recomputed: HECA 66.6 s, OTHH ~455 s). State which and why. Apply the same treatment to the other `tmp/` subdirectories and to `Patches` / `Tiles` / `Previews` if they are also full copies.
2. `lane_worktree.sh check` reports a worktree whose `tmp/engine_caches` is a full (non-clone) copy if that is detectable cheaply; if it is not detectable, say so.
3. A way to reclaim space in EXISTING worktrees and in the main tree without losing derived sidecars: a `lane_worktree.sh` subcommand that re-seeds `tmp/engine_caches` as clones of the shared corpus while keeping files the lane actually rewrote. It must refuse while a build is running in that tree. Do NOT run it on any live worktree (v1cut, v2trim, v2trimctl, conc333, fac334, sweep1027) or on the main tree — the master runs it after you report.
4. Twins in `Ortho4XP/tests/test_harness.py` style; `tools/INDEX.md` rows updated in the same commit.
5. Measure with `df` before/after creating and removing one scratch worktree (real free-space delta, since `du` counts clones at full size): report both numbers.

Disk is tight: create at most ONE scratch worktree for the measurement and remove it; no airport build unless the "leave it out" option needs its first-build cost measured, and then CYXY only.

THE FOUR NEVERS (single master): never comment on an issue, never merge, never create a routine/trigger or follow-up, never notify the owner. Final report only: branch, sha, the free-space measurements, what changed, net lines added/removed, new public symbols, every item NOT done.

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

