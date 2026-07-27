# tools/attic — retired diagnostics

**Owner ruling 2026-07-26:** orphaned, one-off and superseded diagnostic tools move
here rather than being deleted. Nothing in this directory is referenced by `src/`,
`tests/`, the live `tools/`, either `CLAUDE.md`, `scripts/`, CI, the Swift
`Sources/`, or `tools/artifact_contracts.json`. Every file below was verified
individually before the move; the only surviving mentions are in `docs/` plan
documents and in `STATUS.md` history.

## These tools are NOT maintained

They may reference retired APIs, deleted modules, renamed env flags and airports
that no longer reproduce the defect they were written for. Treat them as *written
evidence of how a defect was measured*, not as runnable tooling. Read before running.

### They will not run as-is from this directory

Nearly all of them bootstrap `sys.path` from their own location, assuming they sit
in `tools/`:

```python
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))          # now .../tools/attic
_SRC_DIR = os.path.join(os.path.dirname(_TOOLS_DIR), "src")      # now .../tools/src  (wrong)
```

From `tools/attic/` that resolves one directory too deep, so `import auto_patch`
fails. The fix is one extra `dirname`:

```python
_TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

That single change repairs everything at once: `src/` is found again, and because
Python already puts the *script's* directory on `sys.path`, sibling imports inside
this attic keep working while imports of tools that stayed live
(`_diag`, `check_grade`, `obj8_geometry`, `mesh_elevation_sampler`,
`mesh_region_tris`) resolve through the restored `tools/` entry. The same applies
to `from conftest import xplane_root`, which several of these reach through a
`tests/` path built the same way.

Cross-directory imports that still point at live tools, for reference:

| attic tool | imports from live `tools/` |
|---|---|
| `diff_constraint_graphs.py`, `verify_splp_grade.py` | `check_grade` |
| `dsf_object_anchor_audit.py` | `obj8_geometry`, `mesh_elevation_sampler` |
| `mesh_hotspot_cells.py` | `mesh_region_tris` |
| `dump_pav_union.py`, `find_missing_pavement.py`, `monitor_coverage.py`, `probe_route_chains.py`, `trace_shape_drops.py` | `_diag` |

`tunnel_trench_audit.py` imports `custom_mesh_cutout_oracle`, which moved here with
it, so that pair stays self-contained.

---

## Orphans — zero references anywhere in the repo

| File | What it probed | Built for | Why atticked |
|---|---|---|---|
| `dump_pav_union.py` | Dumps the pipeline's real `pav_union` (merged, seam-cleaned pavement coverage, before runway/groundside subtraction) to JOSM-readable OSM | HECA / CYXY "is the union clean" reviews | Orphan — zero refs |
| `find_missing_pavement.py` | `pav_union − emitted`: pavement present in the source union that no emitted shape covers, ranked by area | The generic "where did pavement go" overview | Orphan — zero refs |
| `trace_shape_drops.py` | Wraps every shape-removing/rewriting pass and attributes LOST COVERAGE to the specific pass that opened the hole | HECA, CYXY, SPLP missing junctions/stubs/aprons | Orphan — only mention is prose in `find_missing_pavement.py`, which moved with it |
| `monitor_coverage.py` | Running `pav_union` coverage % after each geometry-mutating pipeline pass, with the delta per pass | Catching the pass that opens a coverage hole, the moment it happens | Orphan — zero refs |
| `pav_skeleton_osm.py` | Builds the pavement-derived spine (route-guided synthesis or pure Voronoi medial skeleton) and dumps it as JOSM layers | SPJC spine work | Orphan — zero refs |
| `snap_target_to_apt_dat.py` | Snaps every non-runway vertex in a hand-made target OSM to the nearest apt.dat/DSF pavement edge | Keeping comparison targets producible after DSF pavement entered the pipeline (owner 2026-04-27) | Orphan — zero refs |
| `runway_join_crown_probe.py` | Per taxi-centerline runway contact: crown-profile value vs runway-EDGE value vs what the join actually anchored to | Owner ruling 2026-07-16 (joins anchor to the crowned runway EDGE, never the centerline) | Orphan — zero refs |
| `profile_inset_construction.py` | Phase-attributes a COLD airport-inset build: discover / warp / footprint-fetch / buffer / rasterize / inpaint | The ~15 min cold OTHH (Doha) inset build | Orphan — zero refs |
| `inset_fill_acceptance.py` | A/B of the legacy `gdal.FillNodata` inpaint vs the vectorized distance-transform fill on the same GLO-30 inset raster | Airport-inset masked-hole fill acceptance | Orphan — zero refs |
| `mesh_triangle_quality.py` | Triangle-area histogram of a built `.mesh` plus the ~100 m cells where sub-1 m² micro-triangles concentrate | X-Plane load-time investigation (degenerate micro-triangulation, not honest curvature) | Orphan — zero refs |
| `mesh_attr_acceptance.py` | Round-9 acceptance: `INTERP_ALT` (attr ≥ 8) coverage of the J/R trench polygon and both abutment bands, plus the z landing check | One baked `Data+36-087.mesh` | Orphan — zero refs; hardcoded to a single tile |
| `render_app_icons.py` | Renders `Utils/icons/Ortho4XP_icon.svg` to `.icns` / `.ico` / `.png` for the legacy Qt GUI | The retired Ortho4XP Qt app window/bundle icon | Orphan — zero refs; the shipping app is now the Swift `XPTerrainBuilder` bundle (`scripts/make_app.sh`) |
| `symbol_closure.py` | Transitive module-level symbol closure: given seed names, the minimal keep-set and by complement the safe-to-delete set | M2 cleanup — carving elevation-neutral primitives out of `unified_jacobi` (`docs/cleanup_consolidation_plan.md`) | Orphan — zero refs. Genuinely generic (works on any module + seed list); kept here because nothing calls it |

## One-offs — hardcoded to a single airport / a single defect

| File | What it probed | Built for | Why atticked |
|---|---|---|---|
| `diag_splp_centerlines.py` | Arc-length vs DEM vs solved elevation along taxi centerlines near the violating junctions | SPLP grade violations −10025 / −10026 | One-off, airport-hardcoded |
| `diag_splp_corridor.py` | Concatenates the north+south "A" legs into one route and prototypes the 1-D grade-compliant DEM relaxation | SPLP "A" corridor (672 m + 642 m) | One-off; the algorithm it prototyped shipped in taxi redistribution |
| `diag_splp_junction.py` | Full anatomy of one junction at (4.1, 503.3): every vertex, DEM, which centerlines pass through, perp distance + arc position | SPLP −10025 (2.87 % violation) | One-off, single junction |
| `diag_splp_runway.py` | CIFP vs post-regrade threshold elevations, seam crossings, and the runway elevation taxiway A anchors to | SPLP runway 02/20, seam-wins/threshold-adjusts rule | One-off, airport-hardcoded |
| `diag_splp_stubA.py` | Corners, alts, DEM and HARD-seam-anchor status for stub/A shapes violating grade under the L2 cascade | SPLP stub/A | One-off; the L2 cascade it was written against is retired |
| `diag_splp_mesh_explosion.py` | Vertical walls, tiny edges and crossing slivers in the final layout — the geometry that makes Triangle4XP over-subdivide | SPLP tile −13/−77 (target ~250 k tris, observed > 2 M) | One-off; superseded by `chain_divergence_audit.py` / `wedge_audit.py`, which stayed live |
| `verify_splp_grade.py` | Build SPLP → write patch → run the grade audit; reports retarget count + worst within-shape grades | SPLP | One-off wrapper; `full_airport_build.py` (live) is the general form |
| `dump_heca_geom.py` | Builds HECA once and pickles runway + pavement geometry to `/tmp/heca_geom.pkl` so shoulder questions stop costing a 3–4 min build | HECA shoulders | One-off, airport-hardcoded, `/tmp` path |
| `analyze_heca_shoulders.py` | Offline: marches outward from each runway edge against non-runway airside pavement, reporting coverage vs distance and the abutting "shoulder" pieces | HECA (consumes `dump_heca_geom.py`'s pickle) | One-off, airport-hardcoded |
| `diag_heca_shoulders.py` | Builds the full HECA patch and finds junctions carrying a long thin strip along a runway edge (the "wings" to absorb into a widened runway) | HECA | One-off, airport-hardcoded |
| `adjacent_ground_coverage_replay.py` | Snapshot-replay one step earlier than `adjacent_ground_replay.py` — before `construct_adjacent_ground_presolve` — so a CONSTRUCT change can be exercised | Slice B stage B3 order 3, adjacent-ground coverage-gap closure | Superseded by `adjacent_ground_replay.py`, which stayed live |
| `junction_repair_impact.py` | Auto-wraps every layout-mutating `junction_repair` pass and reports each pass's delta in shape/vertex/role counts — separating load-bearing passes from no-ops | M7a, fixtures CYXY OEMA HECA SPJC (`docs/cleanup_consolidation_plan.md`) | One-off measurement; result written up in `docs/m7a_junction_repair_impact.md` |
| `object_bridge_patch_audit.py` | Patch-level (no mesh bake) check of six Feature-B / portal-pair invariants: approach-vs-approach overlap, legacy tunnel pieces, and four more | KBNA object-terrain sessions 2026-07-10 / 2026-07-15 | One-off, defect-specific. `crossing_zone_conformance.py` (live) cites its fast-iteration gate pattern in prose only |

## Superseded probes — cited only in `docs/` plan documents

| File | What it probed | Built for | Superseded by / doc |
|---|---|---|---|
| `diff_constraint_graphs.py` | Diffs the two independent within-shape constraint-pair generators (solver `grade_graph` vs `check_grade.iter_shape_grade_constraints`), keyed frame-independently by lat/lon | M4 constraint-graph measurement | `docs/m4_constraint_graph_findings.md`, `docs/cleanup_consolidation_plan.md` — the narrowing it measured has landed |
| `global_slice_probe.py` | Phase-1 acceptance metrics for the curve-native global slice: face count, spine coverage, invalid faces, T-junctions, edge crossings, determinism | SPJC, curve-native spine v2 Phase 1 | `docs/curve_native_spine_v2_plan.md`; `spine_coverage.py` (live) carries the coverage metric |
| `probe_spine_grade.py` | Field-vs-emitted grade along one taxi centerline through a junction — the decisive junction-centerline-spine metric | Junction-centerline-spine feature | `docs/curve_native_spine_v2_plan.md`, `docs/grade_law_consolidation_handover_2.md` |
| `probe_route_chains.py` | Phase-0 verification that bend-split `Centerline` pieces chain back into whole `RouteChain` routes (one `route_idx` per named route, arc lengths agree) | CYXY, anisotropic-edge route chaining | `docs/anisotropic_edge_handling_plan.md` §Phase 0 |
| `classify_centerlines_kml.py` | Medial-axis, codes-free centerline classifier: CENTERLINE / EDGE / SHORT from pavement geometry alone; dumps colour-coded KML | Curve-native spine prototype | `docs/curve_native_spine_plan.md`; superseded by `recognize_centerlines_kml.py`, then by the shipped recognizer |
| `recognize_centerlines_kml.py` | Route-anchored recognizer: a real centerline rides an apt.dat 1201/1202 route, an edge line is offset a half-width, a hold bar crosses perpendicular | Curve-native spine prototype (dense airports where the medial-axis test failed) | `docs/curve_native_spine_plan.md`; the recognizer shipped into the pipeline (`O4_RECOGNIZED_CENTERLINES`) |
| `dump_route_network_kml.py` | Dumps the completed taxi route network to KML, colouring synthetic turn-fillet arcs distinctly from source routes | SPJC fillet verification (`O4_TAXI_FILLET`) | `docs/curve_native_spine_plan.md` |
| `mesh_hotspot_cells.py` | Bins built-mesh triangle centroids into 25 m cells and reports the densest, with each cell's median triangle area — a Ruppert epsilon explosion vs lawful refinement | CYXY weld bake | `docs/chain_identity_one_solve_plan.md`; `mesh_region_tris.py` (live) is the general counter |
| `object_foot_anchor_probe.py` | Fast harness: per structure, the detected foot clusters, fitted rigid offset, and each foot's predicted rendered residual against the mesh | KBNA gantry/pond multi-foot objects | `docs/multi_foot_object_reanchor.md`; `object_seating_report.py` (live) is the full-airport form |
| `dsf_object_anchor_audit.py` | Per object definition: reach (greatest horizontal distance from local origin to any solid vertex) — finds anchors sitting hundreds of metres from their geometry | KDFW, CYUL, HECA anchor reconnaissance | `docs/dsf_object_anchor_plan.md`. **Note:** `docs/dsf_object_integration_spec.md:819` says to *keep* this tool and re-point its imports — atticked because that work never happened and nothing in code references it |
| `obj8_partition_audit.py` | The W2/W4 oracle: Pareto table of fidelity (per-part residual vs mesh) against tearing, across every candidate partition strategy | KCLT OldTerminal pool (1,638 objects) | `docs/dsf_object_integration_spec.md` (amendment A9), `docs/obj8_structure_partition.md` — the partition shipped |
| `object_terrain_feature_report.py` | Per-pack dump of the object-derived terrain-feature classifier (counts, contracts, refusals) — the CLI front end to `classify_object_terrain_features` | Workstream W-V, three-pack set (EGLL TaiModels, Nimbus KBNA, Aviotek EDDF) | `docs/object_terrain_features_spec.md` §4 |
| `tunnel_trench_audit.py` | Grid-samples a built `Data<tile>.mesh` over classified tunnels: flat floor below deck, rim at anchor datum, near-vertical walls, no sub-datum terrain outside the footprint | Feature A, `O4_OBJECT_TUNNEL_TERRAIN`, workstream W-V | `docs/object_terrain_features_spec.md` §§2.4/3.3 |
| `bridge_deck_audit.py` | Samples a built mesh at bridge abutments: does terrain meet the deck, does it clear the girder line over the depressed road corridor | Feature B, `O4_OBJECT_BRIDGE_TERRAIN`, workstream W-V | `docs/object_terrain_features_spec.md` §4 |
| `custom_mesh_cutout_oracle.py` | Parses a correlating author BASE MESH and samples it under every classified structure — the author's own heightfield as the buried-vs-exposed oracle | EGLL_MESH, ruling R11 / amendment A6 | `docs/object_terrain_features_spec.md`. Moved as a **pair** with `tunnel_trench_audit.py`, its only consumer |

> **Judgement flag on the last four rows plus `object_terrain_feature_report.py`:**
> these are the audit tools named in the *pending* workstream W-V of
> `docs/object_terrain_features_spec.md`, which is a design-and-build-order
> document, not a completed one. They qualified mechanically (docs-only mention,
> zero code references) but they are the group most likely to be wanted back.
