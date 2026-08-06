# Ortho4XP/tools

> **Start at [`../../tools/INDEX.md`](../../tools/INDEX.md)** — the repo-wide tool
> index and the consultation surface the owner ruling requires (consult before
> creating, extend a near-fit rather than forking, promote a twice-used scratchpad
> script). It spans both trees and answers "which tool do I reach for"; this file
> is the long-form catalog of what each engine tool does. A tool absent from
> `INDEX.md` is treated as absent.
>
> To BUILD or MEASURE an airport, the answer is always
> [`harness/`](harness/): `build_airport.py`, `census.py`, `lane_worktree.sh`,
> `oracle.py`. A lane-private build or census wrapper is a defect.

Command-line tooling for the auto-patch engine. Everything here is live: each file
below is reachable from `src/`, `tests/`, a `CLAUDE.md`, `scripts/`, CI, the Swift
`Sources/`, or `tools/artifact_contracts.json` — or is a data file those tools own.

Retired diagnostics live in [`attic/`](attic/README.md) (owner ruling 2026-07-26);
they are not maintained and do not run from that directory without a one-line
`sys.path` fix, documented there.

**Run from `Ortho4XP/`**, with `venv/` and `OSM_data/` present. A wrong cwd exits 0
with a silently smaller layout, which reads as a fake speedup.

## ⚠ Executes work on import

Two tools have **no `if __name__ == "__main__"` guard** — importing them, or having
a test collector touch them, runs a full airport build:

| File | Module-level work |
|---|---|
| `check_connector_coverage.py` | `build_airport_pavement()` at line 20 |
| `full_airport_build.py` | `build_airport_pavement()` at line 36 |

(Ten more unguarded tools moved to `attic/` in the same ruling.) `_diag.py`,
`mesh_elevation_sampler.py` and `obj8_geometry.py` also lack a guard but do no
module-level work — they are libraries and are safe to import.

## Acceptance gates — pass/fail against a law or spec

| Tool | One line |
|---|---|
| `check_grade.py` | The grade validator. Within-shape grade, cross-shape proximity and edge-step checks on a patch OSM's per-vertex elevations. Reads the `.axes.json` sidecar when present |
| `check_build_time.py` | Makes the build-time HARD LAW executable: ≤ 60 s per airport, ≤ 300 s per tile, both cold and download-excluded; a ≥ 1 %-of-budget regression fails unless a committed approval matches |
| `chain_divergence_audit.py` | Distance from a conforming planar partition — T-vertices, divergent shared chains. Exactly the classes that exploded CYXY from 26 k to 1.55 M airport triangles |
| `crossing_zone_conformance.py` | Phase-1 of the crossing-terrain-ownership spec: nothing outside the crossing assembly may intersect the published influence zone |
| `check_connector_coverage.py` | Every apt.dat truck route must be covered by emitted pavement along its whole length; uncovered runs > 15 m = a severed airside↔groundside connector. **Unguarded** |
| `airport_inset_acceptance.py` | Airport-elevation-inset acceptance + perf: pins the Phase C1 working grid so 1 arc-second and densified runs compare, records step-1/2 wall time, `.alt` size and Triangle4XP counts |
| `compare_target.py` | Scores a produced layout against a hand-crafted target OSM: per-role counts, best-IoU matching, per-pair geometry deltas |

## Audits — measurement and forensics, no hard gate

| Tool | One line |
|---|---|
| `wedge_audit.py` | Counts near-zero-angle wedges (< 0.5°) where the short edge's far endpoint sits within 20 cm of the long edge — epsilon divergence. Named in `artifact_contracts.json` |
| `flex_audit.py` | FLEX-LAST law: diffs a flex-ON against a flex-OFF patch and asks, at each flexed cluster, whether the feeding taxiways were really at max grade. Reads the axes sidecar **without** guarding for its absence |
| `grade_feasibility_audit.py` | Classifies every within-shape violation as fundamentally infeasible vs feasible-but-unenforced, by treating the grade law as a difference-constraint system |
| `clearance_spike_audit.py` | Terrain spikes beside pavement that no clearance cut covers — turns "several spots at HECA" into coordinates |
| `clearance_conformance_audit.py` | Whether clearance cuts actually protect anything: a cut riding the DEM reads as "covered" to the spike audit while protecting nothing |
| `patch_provenance.py` | Decodes a patch's provenance stamp — git sha + dirty flag, gate configuration, which elevation insets baked into its DEM, timestamp. Root-line only, so seconds-fast over any patch tree |
| `object_seating_report.py` | Per-structure predicted float/sink against the mesh, worst-first with lat/lon, so an in-sim "that building floats" maps to a row |
| `decode_dsf_terrain_table.py` | Decodes an emitted DSF's `TERRAIN_DEF` table and per-patch attributes via `DSFTool --dsf2text`. The verification companion to the `texture_mode` writer |

## Build drivers — run a build, a bake or a suite

| Tool | One line |
|---|---|
| `build_target_osm.py` | Runs the auto-patch pavement builder on one ICAO and dumps to OSM; pair with `compare_target.py` |
| `full_airport_build.py` | The standard lab loop: build one airport as shipped → patch OSM + axes sidecar → `check_grade`. **Unguarded** |
| `production_airport_patch.py` | Single-airport rebuild through the **tile** prelude (insets, overlay, densification, airport smoothing) — the standalone lab loop's raw DEM can differ from production in values *and* geometry |
| `run_tile_build.py` | Headless full tile build that actually calls `tile.read_from_config()` — `Ortho4XP.py`'s single-tile CLI path does not, and silently builds with global defaults |
| `run_tile_mesh_only.py` | Same initialisation, steps 1–2 only. The loop for consumer-side mesh changes: no imagery needed |
| `profile_airport_build.py` | Wall-clock sampling profiler for one auto_patch build (~0.02 s interval, < 1 % overhead) — attribution matches the production phase numbers, unlike cProfile |
| `profile_tile_build.py` | The whole-tile companion, sampling every thread through `sys._current_frames()` so parallel stages attribute correctly |
| `fetch_airport_elevation_insets.py` | CLI front end to `O4_Airport_Elevation_Insets`: pre-warm or refresh one airport's inset cache and inspect it before a full tile build |
| `reanchor_dsf_objects.py` | Re-anchors DSF scenery objects against a built mesh. A thin parser over `post_mesh.discover_and_rebake_airport`, shared with the build hook so the two cannot drift |
| `reanchor_kclt_terminal_bakes.py` | The KCLT-hardcoded prototype `reanchor_dsf_objects.py` generalises. A **second independent writer** of `.o4_reanchor_provenance.json` with a duplicated filename constant — see `artifact_contracts.json` |
| `run_with_ledger.py` | Skips a command that already passed at an identical code-tree hash with identical `O4_*` env; append-only JSONL |
| `fast_suite.sh` | Development fast lane — cheap airports (CYXY, SPLP) plus every non-build unit test. **The full suite stays the merge gate** |

## Probes — interactive diagnosis and replay harnesses

| Tool | One line |
|---|---|
| `adjacent_ground_replay.py` | Snapshots the pipeline once just before `emit_adjacent_ground_bands`, then replays only that emitter plus the weld and residual report — turns a 3–8 min cycle into seconds |
| `interval_reach_replay.py` | Replays `feasibility_project` from an `O4_DUMP_SOLVE_STATE` pickle — the gates-ON spine build that exhausts its 2400-iteration budget at ~27.7 M visits |
| `skirt_value_replay.py` | Replays only `to_osm` + the runway-end skirt edge-grade check from a pickled layout: the *values* are decided in `to_osm`, not in the 3-minute solve |
| `spine_coverage.py` | Fraction of aircraft-centerline length carrying a real spine node, using the solver's own `_spine_membership` rule |
| `trace_reach_route.py` | Which runway ANCHOR and which route bind a point's reachable ceiling/floor — READS the live band (never a replay; the replayed engine was deleted 2026-07-29) and emits the route as KML. `--dem M` traces in a constant-DEM oracle world; `--inverted-pairs` traces the anchor pairs a final band inversion named, including on a build that died on that law |
| `trace_building_frontage.py` | Why a building's flat seat landed where it did: whole-ring median ceiling vs what its taxi-facing frontage can reach (the CYXY A2 apron cliff) |
| `probe_default_terrain.py` | Reconnaissance over X-Plane default Global Scenery: terrain-library namespace, non-projected land terrains, water terrain paths — the format basis for the texture-mode work |
| `mesh_region_tris.py` | Total built-mesh triangle count and how many fall inside the airport bbox — the number X-Plane load time actually tracks, not the patch's node count |
| `mesh_elevation_sampler.py` | Samples elevations from a built `Data<tile>.mesh` — the terrain the sim renders, *after* grading. Sampling the source DEM instead misleads by metres |

## Utilities and data

| File | One line |
|---|---|
| `_diag.py` | Shared helpers for the diagnostic tools: `sys.path` setup, X-Plane root default, `build` / `build_capturing_union`, geometry→OSM dump, shape signatures. **After the 2026-07-26 ruling all five of its importers are in `attic/`** — no live tool uses it |
| `obj8_geometry.py` | OBJ8 geometry and DSF object-placement primitives — anchor vs geometry reach, the basis of the whole re-anchor family |
| `msfs_to_obj8/` | MSFS glTF → OBJ8 conversion package (`convert`, `gltf_reader`, `atlas_pack`, `material_fidelity`) |
| `obj8_building_gen/` | Procedural OBJ8 building generation (`geometry`, `atlas`, `texture`, `obj8_writer`) |
| `obj8_preview/` | `obj8_to_html` — standalone OBJ8 viewer |
| `build_time_baselines.json` | Committed per-airport / per-tile baselines `check_build_time.py` measures against |
| `build_time_approvals.json` | Committed owner approvals that let a specific regression pass |
| `run_ledger.jsonl` | Append-only run ledger written by `run_with_ledger.py` |
| `attic/` | Retired diagnostics — see [`attic/README.md`](attic/README.md) |
