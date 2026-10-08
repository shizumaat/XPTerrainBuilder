# emitspec — the simplest patch that gives the same terrain (RULINGS 2026-10-08e (B)): design summary

Spec: `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` §58 (`tools/docq.py spec '§58'`).
Probes (scratch prototypes, pure reads over `/tmp/harness/swg_*.osm`): `docs/briefs/emitspec-probes/`.
Branch `claude/emitspec` off main `1d231358`. Nothing in the engine was edited; no build, no replay.

## What the mesh builder does with a shape (file:line)
- Altitude is per node: `O4_Vector_Map.py:4008-4177` — way tags (`cst_alt_abs`, `altitude`, …) only seed the vector that node `alt_abs` (:4147-4153) overrides. v2 writes node `alt_abs` only (`emit/osm_adapter.py:484-492`). "A single shape altitude" exists (`cst_alt_abs`, :4017) but is the same value on every node; no other reader honours it (census reads `altitude` as legacy, `check_grade.py:468`).
- A ring = constrained `PATCH_RING_MARKER` edges (:4173); every arrangement face is INTERP_ALT-seeded (:4256-4283); a mesher-inserted vertex on a ring segment takes the linear value (`O4_Mesh_Utils.py:992-1055`); a free interior vertex takes the uniform-weight GRAPH-harmonic extension of the ring nodes (:707-873). Exact on a flat region; NOT the plane on a slope (:1066); a free vertex beside a ring at another level is pulled toward it (:940-971, the R18-1b class).
- v2 has NO decimation: the two "decimators" of the lore (`emit_decimate`, `to_osm` chord retention) were v1 and are deleted. v2's only ring reshapers are `weld_to_shore` and `merge_sub_spacing` (`osm_adapter.py:677-1038`), run in `pipeline/build.py:1336-1340` after `publication()` (:1286) and before `write_patch` (:1369).

## The consumer table (scout census, read only; scenarios: (a) same-role merge, (b) cross-role merge, (c) drop collinear nodes, (d) fine sidecar + merged .osm)

| # | Consumer (read site) | Reads | Joined on | (a) | (b) | (c) | (d) |
|---|---|---|---|---|---|---|---|
| 1 | Mesh `include_patches` `O4_Vector_Map.py:3980-4208` | ways; way tags `cst_alt_abs`/`cst_alt_rel`/`var_alt_rel`/`altitude`/`node_altitudes`/`altitude_high` (:4017-4062); node `alt_abs` (:4147-4153); closed → ring (:4172) | node id | ring OK; interior exact only if flat (graph-harmonic) | + rows 2-3 | OK (linear on segment) | n/a |
| 2 | Seawall admission :4167-4169, `seawall_admission_area` :256-270 | `role` ∈ `GRADED_COVERAGE_ROLES` (:208-215) | union | OK | BREAKS if a graded role merges with a non-graded one | OK | n/a |
| 3 | Open breaklines :4197-4208 | `o4_feature` ∈ OPEN_BREAKLINE_FEATURES (:167) | none | OK | OK | OK if those nodes kept | n/a |
| 4 | `patches_area`, INTERP_ALT seeds :4256-4290; `seed_interp_alt_subcells` :3697; `size_bank_annulus_regions` :3653 | union/polygonized rings | none | OK (fewer seeds) | OK | OK | n/a |
| 5 | Road pins `road_join_yield_pins` :2321-2358, `road_bridge_deck_pins` :2264-2300 | sidecar coordinates | sidecar | OK | OK | OK | OK |
| 6 | Bank rings `_bank_rings_from_patches` `O4_Mesh_Utils.py:1177-1265` | every closed way not `bank_foot` = design ring (:1257-1260) | none | OK | OK | OK | n/a |
| 7 | `bank_pavement_lines` :1281-1350 | ways with `aeroway`/`highway` keys as linework (`BANK_PAVEMENT_TAG_KEYS` :1272) | none | internal lines vanish (a read) | BREAKS if merged way loses `aeroway` | OK | n/a |
| 8 | Coverage/leak/hairline: `patch_coverage_polygon` :2099, `audit_interp_alt_extent` :2187, `hairline_preflight` :412 | the `.poly` edges | none | OK | OK | OK if dropped from all rings | n/a |
| 9 | Census parse `check_grade.py:363-434` (regex :334-345) | ways ≥3 nd; `role`,`ref`,`aeroway`,`o4_feature`; elevations incl. node `alt_abs`; `cst_alt_abs` NOT read | node id | OK | OK | OK | — |
| 10 | `within_shape` (`_graded_pairs` :2372-2830, :9206), `road_cross_section`, `plane_gradient` :1144, `drainage_minimum`, `transverse` | mutually visible pairs per way; caps from `role`, `o4_grade_law`, `o4_grade_law_cap`, `_lifted`, `_taxi_yield`, `o4_single_poly`, code letter/number, `class`; `face_holes` by `str(shapeID)` (:2717, :2764) | way; shapeID | CHANGES COUNTS; BREAKS if cap tags differ | BREAKS (one cap prices two surfaces) | CHANGES COUNTS | BREAKS: holes by old id unfound (13da class) |
| 11 | `cross_shape` :9443, `vertex_to_edge_step` :9862, `mid_edge_step` :9964, `runway_step`, `strip_seam_tear` :5832 | vertex vs other ways; equal `shapeID` skipped (:6014-6017) | way; shapeID | pairs move to within_shape | BREAKS role-pair skips | fewer rows; T-vertex reads ≤ z quantum | OK |
| 12 | `stacked_nodes` :6101, `sentinel_elevation` :6205 | node id, xy | id/xy | OK | OK | OK | OK |
| 13 | Per-vertex sidecar: `_crown_drops_by_nid` :1015, `_pad_relief_by_nid` :1021, `_road_frame_by_nid` :1040-1065, `_seam_nids_from_pins` :949, `station_caps` | `[lat, lon, v]` | round 7 dp → nid; miss skipped (:1063) | OK | OK | silently unread for a dropped node | OK |
| 14 | Published law edges `_check_published_law_edges` :4846-4870 (`airside_no_step`, `pad_pavement_no_step_edges`, `apron_lattice_membrane`), `taxi_route_pairs`, `mesh_edges` | `{a,b,budget_m}` | endpoint lat/lon → node | OK | OK | `n_unmatched` rises (:4853) | OK |
| 15 | `jetway_strip` :7163-7232, `seam_residual` :7237, `road_coverage_join` :7426, `eat_ceiling` :8292, `pad_airside_renode` :6983 | sidecar vertices | 7 dp → (z, way) | OK | row on merged role | `got is None: continue` (:7208) | OK |
| 16 | Sidecar-only families (`hard_conflict` :7109, `platform_*`, `pad_cluster_mismatch` :6919, `basin_floor_declaration` :6756, `design_target`) | sidecar | none | OK | OK | OK | OK |
| 17 | Geometry-over-ways families (`zone_on_pavement` :3321-3380, `ramp_in_strip` :7987, `frontage_near_miss` :9549-9694, `pad_airside_weld` :6813, strip/RESA/RAOA :3508-4382, `hairline_pair` :8141) | polygons by `role`; holes by shapeID | role; shapeID | per-vertex rows fall | BREAKS: role selects population | counts fall | BREAKS as row 10 |
| 18 | `runway_crown` :4539 | `crown_spine` nodes + `crown_drops`; runway rings | node id; 7 dp | OK (runway never merges) | BREAKS | BREAKS if spine/edge nodes dropped | OK |
| 19 | Apron tier report :9076; `census.py:1342`, :1946; `rwy_xfall.py:134` | shapeID labels; `n_ways` | shapeID | labels change | same | same | OK |
| 20 | v2 verify `verify/frame.py:200-240` | the `GradedSurface` MODEL; caps by face id | face id | unchanged if emit-side (populations then differ from census) | same | same | BREAKS if ids re-minted |
| 21 | `face_tags` `pipeline/publication.py:233` → `osm_adapter.py:424,462` | per-face tags | face id | BREAKS unless members' tags equal | BREAKS | OK | — |
| 22 | Object stage `engine_v2.py:921-990` → `placement_read.py:60-95`; `rebake_after_mesh` :1136 | `<ICAO>.graded.json`, the mesh, the plan — not the .osm | ref/role/vertex id in graded.json | OK if graded.json fine | BREAKS `graded_roles_from_doc` if merged | OK | OK |
| 23 | Rebake staleness `airport/rebake_screen.py:260-281` | body sha256 of the .osm | hash | OK if screen hashes the body written | same | same | n/a |
| 24 | Freshness `build_support.py:246-290`, `driver._auto_patch_is_current` :326, `_stamp_header` :242 | `<osm>` header only | none | OK | OK | OK | OK |
| 25 | Identity `harness/build_airport.py:3509-3514` (`body_sha256` = lines[2:]), `census.py:309-405` | bytes | hash | changes once | same | same | sidecar hash moves too |
| 26 | `tools/v2_late_read.py --patches` :508-512 | `(role, ref)` groups | role, ref, coords | internal nodes vanish | BREAKS grouping | changes | n/a |
| 27 | `tools/v2_solve_replay.py --emit` :974-1018 | calls `write_patch` itself | — | follows if inside `write_patch` | same | same | same |
| 28 | shapeID tools: `v2_explain.py:109-117`, `v2_why.py:143-178`, `role_overlap_read`, `role_edge_census`, `compare_target`, `arm_site_read.py:194`, `who_wrote.py:232-277` | way by shapeID; `v2_why` assumes shapeID = face id | shapeID | BREAKS unless merged id is a member id + member list | same | OK | — |
| 29 | Other `_parse_osm` tools (airside_value_delta, apron_drape_read, lattice_overlap_read, patch_proximity_diff, patch_transect, runway_end_ground, rwy_profile, seawall_admission, road_terrain_conformance, tunnel_portal_acceptance, osm_site, pad_level_report, runway_edge_tie) | ways by role/ref | role/ref | counts change | BREAKS role selection | counts change | — |
| 30 | App (Swift `Sources/`, Qt) | zero reads of `patch.osm`/`shapeID`/`alt_abs`/`axes.json` | — | OK | OK | OK | OK |
| 31 | Tests on emitted counts: `tests/auto_patch_v2/test_emit_holes.py:71,78,137`, `tests/test_rsa_strip_law.py:132`; 25 files call `render_patch`/`write_patch` | counts | — | re-found | same | same | — |

Sidecar keys by key type: face id — `face_holes`, `taxi_yield_caps`, `lifted_caps`; vertex lat/lon — `crown_drops`, `pad_relief`, `seam_pins`, `station_caps`, `road_route_frame`, `road_coverage_join`, `road_join_yield`, `*_no_step_edges`, `taxi_route_pairs`, `mesh_edges`, `plateau_rings`, `jetway_strips`, `eat_rects`, `pad_airside_renode`, `road_cap_governs`, `design_target`, `hard_conflict`; neither — `cluster_pads`, `platforms`, `gap_pieces`, `terrace_joints`, `object_cuts`, `tunnel_objects`, `axes`, `stretches`, `routes`, `runway_*`, `shore_edges`, `natural_shore`, `apron_tier`, `late_stage`, `pad_refusals`, `deck_shades`, `runway_flex`, `road_terrace_witness`, `seam_half_width_m`.

VERDICT: the mesh is indifferent to role/ref/id; every instrument prices shapes by role and pairs by way; the object stage reads `graded.json`. Hence §58 (5): one writer, the SIMPLE `.osm` for the mesh, the FINE `graded.json` + sidecar (+ new key `simple_shapes`: written shapeID → member face ids + written role) for every instrument.

## The prize (probe_simplify, xy 0.01 m, guard 3 m) — ways / nodes
NLWF 35/549 → 32/543 (across) · KASE 103/1,776 → 102/1,769 · CYXY 337/4,527 → 334/4,504 · SPJC 644/10,118 → 615/9,990 · KCLT 1,638/22,291 → 1,608/22,117 · **OTHH 1,717/27,797 → 917/23,029 across-role, 1,233/25,890 within-role** · HECA 2,050/42,917 → 2,028/42,380. At 0.02 m: OTHH 888/22,680, HECA 2,012/42,239. The prize is a flat-airport prize; sloped faces are non-planar at the cm and their nodes do change the terrain.

## Owner's site (OTHH 25.259994, 51.6104872 r 150: 57 faces / 1,691 ring vertices)
Across-role: 33 shapes — one 16-face 3.96 m shape (apron + plateau + building6 pad + 11 collar slivers + junction + service roads, 930 vertices → ~600), 5 trench floors at −0.84 m (other plane, rimmed), 1 trench ramp (sloped), `secondary_parallel pav32` (3.66–4.01, non-planar), the 345-node collar ring (relief 3.83–4.14), ~22 small 3.96 m pieces reachable only across a rim or a non-planar face. Within-role: 47.

## The equivalence instrument
Definition: |Δz| < 0.01 m at every mesh vertex inside the coverage, coverage boundary unmoved. Tier 1 proxy (`probe_equivalence.py`, the builder's own `interpolate_free_interior_altitudes` on a shared Delaunay with per-arm constraint filtering): OTHH site **0.0022 m max, 0 over 0.01** (0.48 m without the 3 m fence guard — that reading is rule N5); HECA site 0.000 m (nothing droppable). OTHH whole components: 0.34–0.37 m with ~10 % over 0.01 — proxy artefact suspected (same component read 0.006 m before per-arm triangle removal), NOT settled. Tier 2 = the real read: `tools/mesh_equivalence.py` (extend `run_tile_mesh_only.py` + `auto_patch/mesh_sampler.py`), two mesh steps per airport, bar 0 over 0.01 m — S0 of the plan, before any engine code.

## Where it runs
`emit/simplify.py` (new family member) inside `write_patch` / `write_tile_pieces`, after `weld_to_shore` + `merge_sub_spacing`, producing a second `GradedSurface` that `render_patch` writes; `graded.json` and the sidecar keep the fine surface; `simple_shapes` joins them. Rules M1–M4 / N1–N5 in §58 (7); first step merges FLAT components only.

## Owner questions
Q1 across-role merging (recommend YES); Q2 a future preview draws the simple shapes (recommend YES, fine roles on hover); Q3 the 3 m fence beside foreign rings (recommend YES).

## Not settled / not done
- Tier-2 (real mesh) equivalence not run — no build/replay in this lane; the tier-1 whole-component disagreement is attributed to the proxy, not proven.
- `face_holes` at OTHH: 244 of 7,267 hole-ring coordinates have no emitted node (hole vertices no way names) — expected under `render_patch:389-399`, noted for the `simple_shapes` join.
- The "within_shape per-vertex fix of this week" named in the brief was not located by the scout (commits 5914a241, 09e5b9c9, d543312e, 461ca337 touch `check_grade.py`; none is described so).
- Per-key cost of N4 (keep every sidecar-named vertex) not measured.
- No INDEX row: the probes are prototypes under `docs/briefs/`, not tools; `mesh_equivalence.py` gets its row at S0.
