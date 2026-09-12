# Ortho4XP/tools

> **Start at [`../../tools/INDEX.md`](../../tools/INDEX.md)** — the repo-wide tool
> index and the consultation surface the owner ruling requires (consult before
> creating, extend a near-fit rather than forking, promote a twice-used scratchpad
> script). It spans both trees and answers "which tool do I reach for"; this file
> is the long-form catalog of what each engine tool does. A tool absent from
> `INDEX.md` is treated as absent.
>
> That link is relative to the REPO ROOT, so in a lane worktree it resolves to
> the worktree's own tracked copy. A worktree checked out at a ref that predates
> the index has none — `tools/harness/lane_worktree.sh up NAME` mirrors the main
> tree's in read-only (and `check NAME` says MISSING / STALE / DIFFERS). Consult
> the mirror; a lane's own promotion edits the TRACKED file, never the mirror.
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
| `clearance_spike_audit.py` | Terrain spikes beside pavement that no clearance cut covers — turns "several spots at HECA" into coordinates |
| `clearance_conformance_audit.py` | Whether clearance cuts actually protect anything: a cut riding the DEM reads as "covered" to the spike audit while protecting nothing |
| `patch_provenance.py` | Decodes a patch's provenance stamp — git sha + dirty flag, gate configuration, which elevation insets baked into its DEM, timestamp. Root-line only, so seconds-fast over any patch tree |
| `object_seating_report.py` | Per-structure predicted float/sink against the mesh, worst-first with lat/lon, so an in-sim "that building floats" maps to a row |
| `object_pad_evidence_report.py` | Per-structure BUILDING EVIDENCE for a pack's OBJ8 rings (R18-2): the vertical-structure reading, the OSM-footprint join, the name vouching, the upstream refusal ledger, and what each pending default-OFF defence would cost on this pack. Guarded; reads every number out of the engine's own code path |
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
| `reanchor_kclt_terminal_bakes.py` | The KCLT-hardcoded prototype of the deleted `reanchor_dsf_objects.py` (seat, retired 2026-09-12s). A **second independent writer** of `.o4_reanchor_provenance.json` with a duplicated filename constant — see `artifact_contracts.json` |
| `run_with_ledger.py` | Skips a command that already passed at an identical code-tree hash with identical `O4_*` env; append-only JSONL |
| `fast_suite.sh` | Development fast lane — cheap airports (CYXY, SPLP) plus every non-build unit test. **The full suite stays the merge gate** |

## Probes — interactive diagnosis and replay harnesses

| Tool | One line |
|---|---|
| `adjacent_ground_replay.py` | Snapshots the pipeline once just before `emit_adjacent_ground_bands`, then replays only that emitter plus the weld and residual report — turns a 3–8 min cycle into seconds |
| `interval_reach_replay.py` | Replays production's main-yield projection (fp#8) offline from an `O4_DUMP_SOLVE_STATE` pickle, at any sweep block/ceiling (`--sweeps`, `--hard-cap`) and under any named constraint-class arm (`--arm`) or law-family knife (`--drop-family`). The projection lane's measurement instrument: budget ladder, class ladder, slab-class decomposition. |
| `skirt_value_replay.py` | Replays only `to_osm` + the runway-end skirt edge-grade check from a pickled layout: the *values* are decided in `to_osm`, not in the 3-minute solve |
| `spine_coverage.py` | Fraction of aircraft-centerline length carrying a real spine node, using the solver's own `_spine_membership` rule |
| `trace_reach_route.py` | (builds GUARDED — it arms the harness build entry's own `arm_shared_repo_protection`, so its in-process build cannot write the shared corpus) Which runway ANCHOR and which route bind a point's reachable ceiling/floor — READS the live band (never a replay; the replayed engine was deleted 2026-07-29) and emits the route as KML. `--dem M` traces in a constant-DEM oracle world; `--inverted-pairs` traces the anchor pairs a final band inversion named, including on a build that died on that law; `--below-grade-anchors` classifies every anchor seed of the live field; `--hard-seed-writers [THRESH]` attributes WHO wrote each hard seed below THRESH — born-in-seeding vs a later pass (with the writing `file:line`), and with `O4_SEED_BRANCH_ATTRIB=1` names the SEEDING BRANCH (pin family / warm-start constant fill / per-vertex DEM sample / nearest-hard backfill) plus the owning shape and ring index, and tallies what the band's seed-completeness union carries |
| `trace_building_frontage.py` | Why a building's flat seat landed where it did: whole-ring median ceiling vs what its taxi-facing frontage can reach (the CYXY A2 apron cliff) |
| `probe_default_terrain.py` | Reconnaissance over X-Plane default Global Scenery: terrain-library namespace, non-projected land terrains, water terrain paths — the format basis for the texture-mode work |
| `mesh_region_tris.py` | Total built-mesh triangle count and how many fall inside the airport bbox — the number X-Plane load time actually tracks, not the patch's node count. `--water-audit` is the mesh-side WATER read (every water vertex's z, every water triangle's z-step, `--near LAT LON R` for one site), split into the SEA class `sea_smoothing_mode=zero` levels and the inland/equiv bodies that hold their own level — lumping them makes "how many water vertices are off zero" unreadable (RULINGS 2026-09-09o/09z)   `--edge-audit --near LAT LON R` is the TERRAIN EDGE's AREA read (owner RULINGS 2026-09-10g, the CYXY texture tearing): over every triangle in the radius, (a) OVERLAPPING NODES — vertex pairs closer in plan than `identity.min_distinct_spacing_m` but more than `--overlap-dz` apart in z, (b) WALLS — triangles steeper than `--wall-slope` where the DEM under the same footprint is gentler by `--dem-slope-factor`, (c) PAST THE EDGE — every vertex on no patch-valued triangle against the tile's own `.alt`.  `--kml` writes the offenders for the sim read.  A transect cannot see a fold beside it: round 1's one-line bar passed while 18.4 M overlapping pairs sat 237 m away.  Prove it on the control mesh first (0 pairs) |
| `patch_water_audit.py` | The EMIT-side half of the same read: how much of an emitted patch's BANKED REGION covers water and how many `bank_foot` nodes stand inside it, with the region read as the mesh reads it (exteriors − holes, spec §13.3) — a ring FOLLOWING the water line is a hole, and counting ring polygons naively reports its area twice (OTHH: naive 3,218 m², true 0.0) |
| `runway_end_ground.py` | The GROUND off a runway end as the patch emitted it: SURFACE-role vertices (graded_strip/junction/service_junction/apron — below-grade families deliberately out) within `--radius-m` of each `--end`, and how many sit at or below `--level-m`. The rounds-17/17b/17c acceptance population (VHHH's 1,681 canyon vertices → ~0). Reads the patch with `check_grade._parse_osm`, so it and the census read one geometry |
| `undulation.py` | THE UNDULATION READ (owner 2026-09-08t "unrealistic undulation" in a number): per role and per way, the RMS SECOND DIFFERENCE of `alt_abs` along every emitted chain and the max grade change per 100 m. Patch-only and law-free, so a v1 patch, a v2 patch and another engine version compare on one footing. Skips `o4_feature=bank_foot` (the bank IS the DEM, 09-09e) |
| `pad_level_report.py` | THE PAD-LEVEL INSTRUMENT (owner RULINGS 2026-09-10l "Pad takes the apron edge level", 10y "a pad is ONE PLANE fitted to its frontage"). Three reads, one tool, because they are one question asked of the two arms. `pads SOLVED.pkl [--ref REF] [--icao ICAO] [--band MIN MAX]` — per rigid face: its rim, the residual of the LEAST-SQUARES PLANE through its own vertices (09c's "one plane", the 0.01 m bar) and its TILT against the 1 % ceiling, the roles it FRONTS with the contact count, and per fronting role the pavement's OWN level in a band beside the contacts against the contacts' own — the fit's residual, which is what says whether the pad took the pavement's level or the pavement took the pad's. `transect SOLVED.pkl --to LAT,LON --from-ref REF [--step M]` — z at 1 m stations over the patch's OWN triangulation (`solve.rows._face_triangles`, never a re-triangulation) from that face's ring vertex nearest the target to the target: the "does the apron still fall into the terminal" read of RULINGS 10h/10k, reported as the fall over the span and the worst station step. `delta A.osm B.osm [--role building] [--materiality M]` — the pad LEVEL change between two emitted patches, joined per way on its `o4_ref`/shapeID tag (never proximity, memory `canonical-identity-join`): how many moved beyond materiality, p50/p90/max, and each ring's SPREAD before and after (a pad is one plane, so its spread is its tilt over its span). It prices no law and counts no defects — `harness/census.py` is the only defect count. The first two read a `v2_solve_replay.py --solved-out` pickle (the solve arm), the third emitted patches (the build arm). Promoted 2026-09-10 from lane `v2padlevel`'s three scratchpad readers (`probe`, `transect`, `paddelta`) on their SECOND round of use (RULINGS `7e90032`). Twin: `tests/test_pad_level_report.py` |
| `rwy_profile.py` | The runway ridge as emitted: station, BOW (min of z − threshold chord), the crossing-runway z, max grade and max grade change. `--binned` reads EVERY two-threshold runway and `--compare` puts a control patch beside it — the bow figures every HECA round quotes. `--target` adds the read against the design surface's own TARGET PROFILE (spec §21: the ground's long-wave trend through the threshold pins), fitted by `constraints/runway_chord`'s own `_Trend` |
| `mesh_elevation_sampler.py` | Samples elevations from a built `Data<tile>.mesh` — the terrain the sim renders, *after* grading. Sampling the source DEM instead misleads by metres. CLI: `--lon L --lat-range A B` / `--lat L --lon-range A B` sweeps a TRANSECT, `--point LAT LON` samples one, `--step-flag M` annotates jumps ≥ M m — which is how a shore FACE (one step) is told from a beach RAMP (several).  `--grade-bar B` turns a transect into a GRADE read (every station-to-station gap, max, and how many exceed B — the bank acceptance is a grade, not an elevation); `--bank-annulus-slopes --tile LAT LON` reports the triangle-slope distribution over the tile's bank annulus, read from `O4_Mesh_Utils.bank_annulus_polygon` so it is the law's own region (RULINGS 2026-09-09t/aa).  For WHY a station reads the grade it reads, run the mesh step with `O4_BANK_BLEND_DUMP=<path>`: the engine writes a per-vertex provenance CSV over the whole annulus (which path valued each vertex — ray / fallback / pre-valued / pavement-kept / outside the blend's triangle set — with `d_in`, `D(p)`, `z_foot(p)` and the value it already carried), RULINGS 2026-09-09ad |

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
