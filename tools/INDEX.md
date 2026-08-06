# Tool index — the consultation surface

**Consult this file BEFORE writing any script that builds, measures, or
audits.** Owner ruling (RULINGS `7e90032`): consult-before-create,
extend-don't-fork, promote-on-reuse.

Three rules, and they are not advisory:

1. **A tool absent from this index is treated as absent.** Every new tool
   lands WITH its index entry, in the same commit.
2. **Extend a near-fit; never fork it.** If a listed tool almost does what
   you need, add the parameter or subcommand. A slightly-different duplicate
   is a defect — see the census-wrapper precedent below.
3. **Second use of a lane scratchpad script = promote it.** Move it to
   `tools/`, give it an index entry and a twin test, and delete the copy.

> **The census-wrapper precedent.** Two lanes each wrote their own private
> census wrapper around `check_grade.run_checks`. One dropped
> `terrace_joints_ll`, so declared, lawful apron terraces were reported as
> grade violations. The other dropped `ruleset` (an FAA airport judged under
> ICAO law) and enumerated 12 of the 21 law families by hand, reporting 9 —
> a HEAZ patch that the harness censuses at 110 rows was reported at 100.
> Neither wrapper was wrong-looking. Both were wrong. That is why the
> harness exists and why a private copy is a defect, not a shortcut.

Layout: paths are relative to the repo root (`/Users/noah/XPTerrainBuilder`).
Engine tools run **from `Ortho4XP/`** with `venv/` and `OSM_data/` present —
a wrong cwd exits 0 with a silently smaller layout.
`Ortho4XP/tools/README.md` is the long-form catalog of the engine tree's
tools (what each one does in detail); this file is the short "which one do
I reach for" surface across both trees. Retired tools live in
`Ortho4XP/tools/attic/` and are listed there, not here.

---

## THE HARNESS — the standard way to build and measure (start here)

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo; guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. **There is no other sanctioned way to build.** |
| `Ortho4XP/tools/harness/census.py` | You need DEFECT COUNTS from an emitted patch. All 21 law families always, law-true frame from the patch's own sidecar, airside/groundside/mixed split, worst-N rows, class table, sidecar evidence, JSON + table, A/B across patches. **The only numbers that may be quoted as defect counts.** `--zone-split` additionally buckets the within-shape rows by FAN-RAMP ZONE membership (on a declared ramp piece / inside a zone / crossing one / unrelated, plus the rows already steeper than the zone cap) — reach for it when a grade law grants relief on declared ground and you need to know whether the relief is where the defects are. It is a flag and not its own tool because it needs the census's law-true frame; a private copy of that frame is the census-wrapper defect above. |
| `Ortho4XP/tools/harness/lane_worktree.sh` | You are setting up (`up`), auditing (`check`), reporting (`data`) or tearing down (`down`) a lane worktree. Mounts the WHOLE shared data repo (enumerated from it, never hard-coded), symlinks `venv` from the main engine tree, clones `Patches` + `Ortho4XP.cfg` as lane-local, audits untracked paths, and refuses teardown while a process or a shared-repo lock holds the tree. `data` reports which trees are on the shared corpus and which are private. |
| `Ortho4XP/tools/harness/oracle.py` | You want the constant-DEM oracle: both worlds built once, all three assertions (compliance, extreme-seating saturation, band-width field), band-width artifact written. |
| `Ortho4XP/tools/harness/who_wrote.py` | A census says a vertex is wrong and you need to know WHICH PASS wrote it. Records every `node_altitudes` write during a harness build and reports (a) `--dem M`: the pass that INTRODUCED each vertex now sitting exactly on the constant DEM — the author, not the final projection that carried it; (b) `--at X,Y`: one plan coordinate's full value history, so two constant-DEM worlds' histories can be diffed to the exact pass where they first disagree; (c) `--author SITE`: the DISPLACEMENT census — how far a named pass moves values AWAY FROM THE SOLVE'S, split into `new_geometry` / `moved_post_solve` / `untouched`, where a move in the `untouched` class is a SECOND AUTHOR the single-solve architecture forbids (materiality `--author-tol`, default 0.01 m). Use (c) whenever the question is "is this pass re-authoring the solve"; (a) cannot see that class at all — a value overwritten by 25 m is not "sitting on the DEM". **Reach for this before reasoning about a value's origin from the code** — reading attribution as causal has falsified nine mechanisms in this campaign. |
| `Ortho4XP/tests/test_harness.py` | The harness's own twins. Run these after touching any harness entry or `check_grade`'s law register. |

**The shared data repo (owner ruling `e9daef5`).**
`/Users/noah/XPTerrainBuilderData` is THE data repo: DEM + insets, OSM
extracts + road feeds, airport mod cache, geotiffs, masks, DSF cache,
orthophotos. Every lane MOUNTS it via the ritual — never copies, never
keeps a private cache. Downloads and cache regenerations happen EXACTLY
ONCE as explicit, locked, hash-stamped events
(`build_airport.py --refresh-data <scope>`), never as a build side effect;
the refresh ledger lives in the repo at `.harness/refresh_ledger.jsonl`.
A build that writes there without authorisation is reported and its run is
marked CONTAMINATED.

`check_grade.py` is the harness's library: `LAW_FAMILIES`,
`law_context_from_sidecar`, `run_checks(family_out=...)`,
`run_checks_law_true`, `row_side`. Import those rather than re-deriving
them anywhere.

## Acceptance gates — pass/fail against a law or spec

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. |
| `Ortho4XP/tools/check_build_time.py` | A change may have cost build time. Makes the build-time budgets executable (≤ 60 s per airport, ≤ 300 s per tile, cold, download-excluded). **Never wrap it in the ledger** — its output is a time. |
| `Ortho4XP/tools/chain_divergence_audit.py` | Suspecting T-vertices / divergent shared chains (the class that took CYXY from 26 k to 1.55 M triangles). |
| `Ortho4XP/tools/crossing_zone_conformance.py` | Checking the crossing-terrain-ownership spec's phase-1 invariant. |
| `Ortho4XP/tools/check_connector_coverage.py` | Checking that every apt.dat truck route is covered by emitted pavement. **Unguarded: importing it runs a build.** |
| `Ortho4XP/tools/airport_inset_acceptance.py` | Accepting an airport-elevation-inset / working-grid change through a real tile's steps 1–2. |
| `Ortho4XP/tools/compare_target.py` | Scoring a produced layout against a hand-crafted target OSM. |

## Build drivers

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |
| `Ortho4XP/tools/full_airport_build.py` | LEGACY, superseded by the harness build entry. Kept only for old scripts that still call it; it makes none of the harness's refusals and carries an unstated inset-coverage frame gap (its standalone DEM prep degrades to the base surface on a cold cache with only a log line). Do not use it in new work. **Unguarded.** |
| `Ortho4XP/tools/build_target_osm.py` | Producing a compare-target OSM to pair with `compare_target.py`. |
| `Ortho4XP/tools/production_airport_patch.py` | You specifically need the single-airport rebuild through the **tile** prelude (insets, overlay, densification, smoothing). |
| `Ortho4XP/tools/run_tile_build.py` | A headless whole-tile build with the tile's own config. For a RELEASE-frame tile build use `harness/build_airport.py --tile` (it also applies the owner's X-Plane install paths, without which auto_patch is silently skipped). |
| `Ortho4XP/tools/run_tile_mesh_only.py` | Consumer-side mesh work: steps 1–2 only, no imagery. |
| `Ortho4XP/tools/fetch_airport_elevation_insets.py` | Inspecting an airport's inset cache. It WRITES into the shared data repo, so use it to warm a cache only as a deliberate act — `build_airport.py --refresh-data dem` does the same fetch under a lock, hash-stamped into the shared refresh ledger. |
| `Ortho4XP/tools/fast_suite.sh` | The development fast lane. The full suite stays the merge gate. |

## Measurement discipline

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/run_with_ledger.py` | Any expensive CORRECTNESS run (pytest, airport build, check_grade). Skips a run another session already passed at an identical tree + `O4_*` env. `--history` before repeating anything expensive. Never wrap a timing run. |
| `Ortho4XP/tools/profile_airport_build.py` | Attributing an airport build's wall time (sampling profiler, < 1 % overhead). |
| `Ortho4XP/tools/profile_tile_build.py` | The whole-tile companion; samples every thread. |
| `Ortho4XP/tools/patch_provenance.py` | Asking what a patch was built from: git sha, dirty flag, gate configuration, which insets baked into its DEM. Root-line only, so it is fast over a whole patch tree. |
| `tools/blast.py` | **Before editing anything under `Ortho4XP/src/` or `Sources/`.** Direct importers, tests to run, role-literal / env-flag / wire-protocol hazards, co-change neighbours. `--audit` checks its own recall. |

## Audits and forensics — no hard gate

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/grade_feasibility_audit.py` | Asking whether a violation is fundamentally infeasible or merely unenforced. |
| `Ortho4XP/tools/wedge_audit.py` | Hunting near-zero-angle wedges / epsilon divergence. |
| `Ortho4XP/tools/flex_audit.py` | Diffing a flex-ON against a flex-OFF patch. Reads the axes sidecar **without** guarding for its absence. |
| `Ortho4XP/tools/clearance_spike_audit.py` | Turning "spikes beside the pavement at HECA" into coordinates. |
| `Ortho4XP/tools/clearance_conformance_audit.py` | Asking whether a clearance cut protects anything or just rides the DEM. |
| `Ortho4XP/tools/object_seating_report.py` | "That building floats" → a row with lat/lon. |
| `Ortho4XP/tools/decode_dsf_terrain_table.py` | Verifying an emitted DSF's terrain table / per-patch attributes. |
| `Ortho4XP/tools/spine_coverage.py` | Fraction of aircraft centerline carrying a real spine node. |
| `Ortho4XP/tools/trace_reach_route.py` | Which runway ANCHOR and which route bind a point's ceiling and floor, and what the local off-route leg costs (emits KML). Reads the LIVE band — `reach_band_unified` for the band, `band.attachment_at` for the lookup's serving attachment, and the anchor provenance `spine_value_fields` recorded — so its numbers are the build's, not a replay. An off-net point is an ANSWER (the within-shape law governs it), not a refusal. Revived 2026-08-06: it used to replay the nearest-visible-centerline engine deleted on 2026-07-29 and refused coordinates the live band serves. |
| `Ortho4XP/tools/trace_building_frontage.py` | Why a building's flat seat landed where it did. |
| `Ortho4XP/tools/mesh_region_tris.py` | Built-mesh triangle count inside the airport bbox — the number load time tracks. |
| `Ortho4XP/tools/mesh_elevation_sampler.py` | Sampling the terrain the sim actually renders, after grading. |

## Replay harnesses — seconds instead of minutes

| Tool | Reach for it when |
|---|---|
| `Ortho4XP/tools/adjacent_ground_replay.py` | Iterating on `emit_adjacent_ground_bands` only. |
| `Ortho4XP/tools/interval_reach_replay.py` | Replaying `feasibility_project` from an `O4_DUMP_SOLVE_STATE` pickle. |
| `Ortho4XP/tools/skirt_value_replay.py` | Replaying `to_osm` + the runway-end skirt check from a pickled layout. |

## Libraries, data and one-offs

| File | Note |
|---|---|
| `Ortho4XP/src/auto_patch/constant_dem.py` | The oracle's own module: the DEM object, `band_width_field`, `band_width_summary`, `saturation_report`, the artifact writer. Drive it through `harness/oracle.py`; import these functions rather than re-deriving a band width. |
| `Ortho4XP/tools/_diag.py` | Shared diagnostic helpers. **All of its importers are in `attic/`** — no live tool uses it. Treat as one-off support, not a standard library. |
| `Ortho4XP/tools/obj8_geometry.py`, `msfs_to_obj8/`, `obj8_building_gen/`, `obj8_preview/` | The OBJ8 / object-placement family. |
| `Ortho4XP/tools/reanchor_dsf_objects.py` | Re-anchors DSF objects against a built mesh; shares its implementation with the build hook. |
| `Ortho4XP/tools/reanchor_kclt_terminal_bakes.py` | **ONE-OFF** — the KCLT-hardcoded prototype the tool above generalises, and a second independent writer of the same provenance file. Do not extend it; extend `reanchor_dsf_objects.py`. |
| `Ortho4XP/tools/probe_default_terrain.py` | **ONE-OFF** reconnaissance over X-Plane's default scenery. |
| `Ortho4XP/tools/build_time_baselines.json`, `build_time_approvals.json` | Committed baselines and owner approvals for `check_build_time.py`. |
| `Ortho4XP/tools/run_ledger.jsonl` | The append-only run ledger (gitignored, machine-local). |
| `tools/artifact_contracts.json` | Declared artifact contracts (`blast.py` reads it). |
| `Ortho4XP/tools/attic/` | Retired diagnostics; see `attic/README.md`. Not standard tools. |

---

## Promotion candidates (lane scratchpad scripts, already absorbed)

These were written independently in several lane scratchpads and are now
folded into the harness. If you find a copy in a scratchpad, use the
harness entry instead of the copy.

| Scratchpad script | Absorbed into |
|---|---|
| `census_lockstep.py`, `refpull_interim/census.py`, `testphase/census.py` | `harness/census.py` (law-true + bare frames, class table) |
| `integrate/worst.py` | `harness/census.py` (`--top N` worst rows) |
| `integrate/side.py` | `harness/census.py` (airside/groundside/**mixed** split, on the law's own role partition) |
| `integrate/build.sh`, `refpull_interim/arm.sh` + `arm.py` | `harness/build_airport.py` (env snapshot, `.progress`, ledger, body sha) |
| `reltiles/run_release_tile.py`, `buildtile.sh` | `harness/build_airport.py --tile` (owner X-Plane install paths, four release steps) |
| `testphase/oracle.py` | `harness/oracle.py` |
