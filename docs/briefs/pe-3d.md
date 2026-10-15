# Brief pack — lane `pe-3d`

Base: main `5cb281fa7` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L6a: live 3D preview (Mac)

## The brief

## Lane pe-3d — L6 round 6a of the patch editor (#46): live 3D preview (Mac)

THE SPEC IS LAW FOR THIS LANE: `Ortho4XP/docs/specs/patch-editor-20261015.md`
on branch `claude/patch-editor` — read §0 (A8, A9), §2 (`terrain_sample`, and
the "Clarified" paragraph), §5 and §8. Mockup:
`Ortho4XP/docs/mockups/patch-editor-20261015.html`, section "3D preview".
L2 is merged on this branch: read `Sources/SceneryKit/PatchWire.swift`
(`O4TerrainSample`, `terrainSample` wrapper already exist),
`PatchDocument.swift`, `PatchSpatialGrid.swift`,
`Sources/XPTerrainBuilder/PatchEditModel.swift` before writing anything.
If the spec is wrong or cannot be built as written, STOP and report.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-3d claude/patch-editor`.
Run git as `git -C <your worktree> …` (never cd + git). Merge main into your
branch before your final test run. Never commit on main, never push, never
merge, never comment on issues.

PARALLEL LANE: pe-engine (L1) is adding `patch_list/load/save/revert`, a new
`o4_engine/patch_commands.py`, `o4_engine/patch_edit.py`, and their rows in
the `o4_engine/jsonl.py` command table. Do NOT touch those files except to add
your own row(s) to the jsonl table (keep the diff to your lines so the merge
is trivial).

### Deliver (6a only — buildings are 6b, imagery drape and Last build 6c)
1. Engine: `terrain_sample` exactly per §2, in a NEW module (e.g.
   `o4_engine/terrain_commands.py`), registered in the jsonl table. Reuse
   `auto_patch_v2/airport/dem.load_dem` (base + insets; the airport solve's
   own sampler) — find how it needs its `Frame`/ICAO and call it; never a
   second DEM reader. Grid: row 0 = south edge, row-major, float32 LE base64.
   Cache-only: a missing DEM is an `ok: false` error naming the tile and
   saying the data must be refreshed — never a download. Extent per A9 is
   the CLIENT's request (bbox + 500 m, 5 m); the engine just serves the bbox
   and spacing it is given, refusing (error sentence) a request over
   4,000,000 samples.
2. `Sources/SceneryKit/PatchTriangulator.swift`: ear clipping with holes
   (patch ways tagged `o4_feature=gap_interior_ring` are holes of the face
   they lie inside — read how the engine emits them in
   `auto_patch_v2/emit/osm_adapter.py` and say in the report how you pair a
   hole with its outer ring). Output triangles in node ids so a moved node
   updates in place.
3. `Sources/XPTerrainBuilder/TerrainPreviewWindow.swift` (+ small helper
   files as needed): `WindowGroup(id: "terrain-preview")` registered in
   `XPTerrainBuilderApp.swift`; opened by ⌘3 and a "3D" button added to the
   map's top-left toolbar area (wiring only in `MapCanvasView`). Title
   "3D Preview · ICAO". SceneKit: terrain grid mesh from `terrain_sample`
   with the patch faces cut out (drop grid triangles whose centroid lies
   inside a patch face), one `SCNGeometry` per patch shape at node
   elevations, vertical exaggeration ×1–×10 (default ×3), orbit / zoom /
   ⌥-pan camera, "Reset view", Wireframe toggle, legend + chip as the
   mockup. Selected nodes (from `PatchEditModel.selection`, empty until L3)
   drawn as yellow markers.
4. LIVE: observe `PatchEditModel`'s document changes; a change to a node's
   position/alt rebuilds only the shapes that use it (one buffer each); a
   topology change re-triangulates only the affected shapes. The window
   never writes to the model. Expose ONE notification point in
   `PatchEditModel` for "these node ids / way ids changed" if it does not
   exist (L3 will call it); keep that edit minimal and say so.
5. Tests: pytest for `terrain_sample` (synthetic DEM in `tmp_path` — never
   the shared data repo; shape, row order, refusal over the cap, missing-DEM
   error); `swift test` for the triangulator (convex, concave, one and two
   holes, a real patch face with a hole taken from the L2 fixture or a small
   excerpt: triangle area sum = polygon area within 1e-6 relative, every
   triangle inside, no triangle inside a hole) and for the cut-out rule.

### Constraints
- `tools/blast.py <file>` before editing under `Ortho4XP/src/` or `Sources/`;
  `--find` before adding. `tools/ratchets.py` at the end.
- New behaviour in new files; `MapCanvasView.swift`, `XPTerrainBuilderApp.swift`,
  `PatchEditModel.swift`, `jsonl.py` get wiring only.
- No airport-specific code (05e); no downloads; never write the data repo.
- Run only the tests covering the change, once.
- Build-time impact: none (on-demand command).
- Convergence guards: attempt cap 2 per failing target, then STOP and report;
  heartbeat START/step/EXIT stamps in your scratch dir `.progress`.

### Report (short)
Branch + head sha; per deliverable done / not done; test results; how holes
pair with outer rings; every user-facing string added; net lines; new public
symbols; whether you could run the window against a real engine (likely not
until pe-engine lands — say so); spec points to rule on.

## RULINGS

## 2026-09-05e — pad-flat blocker refuted and closed; `pad_flat` verify; app 1.0.283

* `lane/v2padflat` 998a8c47 merged. The red M5 twin was the PINNED-runway fixture in relaxed mode: the 04t(1) last resort made one pad a plane (slope 2.27 %, residual 0) by design; the hard fixture is green and pads are one `Flat` each (`constraints/pads.py:40`). Landed: bands on a detached pad act on the group's single level (the per-vertex form was hard-infeasible on a 100 m pad along a 1.5 % lip — KCLT's class); `verify/pads.py` `pad_flat` (unrelaxed pad spread > elevation materiality, relaxed pad plane residual > relaxation materiality) registered as a DEFECT that fails the airport by name in the driver and the harness. CYXY 0/0 pads 10/10 flat (`bd78e2c034b4`), SPJC 0/0 53/53 (`d7ca6dc04663`), KCLT 143/143.
* OWNER (intent): how much may a relaxed pad slope — `[relaxation] pad_slope_max`; spawner default until ruled: 1 % (a 2.27 % floor is a visible tilt).

## Map: o4_engine

Generated by `tools/blast.py --map` — what already exists here. `tools/blast.py --find <keyword>` before adding a function.

```
src/o4_engine — the Controller layer of Ortho4XP's one-engine / many-views architecture
10 modules | exports another module uses, most used first (36 unused exports not shown)
download_meter  Process-wide download telemetry for build-t… | record begin update +1
events  Typed events — the engine protocol's vocabu… | ScanBatch TileState StepProgress +19
failure_report  The failure report a user sends us: redacte…
jsonl  JSON-lines standard-input/output transport…
parallel  Parallel tile builds: the phase-aware subpr… | ParallelBuildRun
redaction  Redaction of text that leaves the user's ma… | RULES KEPT Redactor
secret_broker  Secret-store brokerage: route platform-secr… | SecretBroker
session  EngineSession — the Controller of the one-e… | EngineSession build_done plan_steps +3
task_meter  Process-wide pacing telemetry for countable… | begin advance end
tile_time_model  Learned per-step wall-clock estimates for w… | remaining_step_seconds estimate_texture_features record_build +2
```

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
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`.
  Do NOT set `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR`: the harness makes its own
  overlay, and with them set a build refuses ("pack DSF dump MISSING", #342) — they are
  the pytest suite's mechanism, set by `tests/conftest.py`.
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

