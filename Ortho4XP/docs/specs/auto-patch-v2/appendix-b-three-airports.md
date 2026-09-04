# Appendix B — v1 at SPJC / SPLP / CYXY, and what the mesh pays (scout, 2026-09-03; read-only, no builds)

Scope evidence for auto-patch-v2 milestones M1–M3. Numbers from the 09-02 sweep arms (artifact ledger blobs, tree fa5d6af5).


**Which patches are "latest".** The main-tree `Ortho4XP/Patches/-20-080/-13-078/SPJC|SPLP_auto.patch.osm` (md5 `377b0e97…` / `04383532…`, mtime 2026-07-25, **no `.axes.json` sidecar**) are stale July copies that `lane_worktree.sh` has propagated into 40+ worktrees. The 09-02 candidate-tree builds are the sweep arms `SPJC_20260901T234856`, `SPLP_20260901T235149`, `CYXY_20260901T235159` (tree `fa5d6af5`, provenance sha `e2b27678` clean, 145 gates ON, only nondefault `O4_LOG_VERBOSITY=1`); `/tmp/harness` was cleared, but they survive in the artifact ledger `/Users/noah/.ortho4xp/artifact_ledger/entries/{1299bc65…,cabf2dfe…,f8472a93…}.json` → `blobs/<sha256>`. All numbers below are from those blobs, read with a scratchpad parser (`scratchpad/v2scout/patchstats.py`, not promoted).

## 1. The patches

| | SPJC | SPLP (whole) | CYXY |
|---|---|---|---|
| patch bytes / sidecar bytes | 2,750,831 / 24,094,113 | 301,013 / 1,115,828 | 1,238,590 / 5,146,905 |
| nodes / ways (closed / open) | 14,495 / 1,120 (972 / 148) | 1,654 / 96 (90 / 6) | 6,660 / 480 (429 / 51) |
| shapes (`aeroway`+`role`) / feature ways (no role) | 915 / 205 | 82 / 14 | 385 / 95 |
| nodes with `alt_abs` | 14,022 (96.7 %) | 1,651 (99.8 %) | 6,598 (99.1 %) |
| ways with way-level `altitude` | 118 (building 71, object_pad 15, apron 13, svc_junction 11, junction 7, strip 1) | 4 | 52 (building 24, junction 10, apron 8, svc_junction 8…) |
| chords n / p50 / p95 / max (m) | 22,819 / 9.5 / 53.2 / 496 | 2,192 / 15.0 / 58.9 / 191 | 9,258 / 14.4 / 54.7 / 500 |
| chords < 1 m / > 60 m | 525 / 241 | 11 / 20 | 116 / 59 |
| interior rings (`o4_feature=gap_interior_ring`) | 57 (3,457 chords at 15 m) | 8 | 44 (2,459 chords) |
| welds: coords shared by ≥ 2 ways / node ids shared | 7,360 / 7,195 | 476 / 476 | 2,169 / 2,136 |
| coords carrying ≥ 2 node ids (twins) | 165 | 0 | 33 |

Ways per role — SPJC: junction 397, graded_strip 192, service_junction 100, apron 85, building 71, object_pad 17, ols_cut 16, service_road 15, runway_clearance 9, groundside_pavement 7, runway 2, tunnel_ramp 2, retaining_wall 2. Feature ways: apron_lattice 88 (50 m chords), gap_interior_ring 57, gap_drainage_spine 46, apron_spine_station 12, crown_spine 2 (12 m stations). Ref families: adjacent_ground 147, building 71, service 67, gap_fill_spine 45, ols_approach 15, runway_end_skirt 8. SPLP: graded_strip 25, junction 24, service_junction 14, apron 7, ols_cut 6, building 3, runway 1. CYXY: junction 113, graded_strip 87, service_junction 64, apron 37, building 24, service_road 20, groundside_pavement 18, runway 7 (`o4_single_poly`), runway_clearance 7, ols_cut 6, runway_crossing 2.

Note the apron chord median at SPJC is **1.96 m** (3,752 chords, 108 under 1 m): the lateral-corridor/service cross-section node insertion densifies apron edges to ~2 m. Building pads carry chords to 496 m (105 > 60 m); the "60 m pavement-node rule" (`emit decimation: retained 236 vertex(es)`) applies to pavement only.

Sidecar keys by JSON size, SPJC: `airside_no_step_edges` 11.4 MB, `pair_caps` 7.6 MB, `xsection_spans` 2.4 MB, `mesh_edges` 1.3 MB, `interior_zones` 338 kB, `axes_exact` 209 kB, `axes` 189 kB, `routes_exact` 171 kB, `apron_lattice_edges` 160 kB, `routes` 113 kB, `frontage_band` 72 kB, `pad_binding_routes` 42 kB, `crown_drops` 31 kB, `station_caps` 27 kB, `apron_seniority` 12 kB, `airside_certificate` 8.7 kB, `svc_free_ends` 5.8 kB, `band_clamp_nodes` 4.8 kB; 25 more keys ≤ 1.4 kB (mostly empty: `terrace_joints`, `basin_facilities`, `road_bridge_decks`, `seam_pins`…). Same key set at SPLP/CYXY (CYXY: no_step_edges 2.2 MB, pair_caps 1.6 MB). The sidecar is 8.8× (SPJC) / 4.2× (CYXY) the patch; the census reads it (`law_context_from_sidecar`).

Tile-cut: SPLP straddles −77/−78; the data-repo pieces `/Users/noah/XPTerrainBuilderData/Patches/-20-080/-13-077/SPLP_auto.patch.osm` (298,631 B, 101 ways) and `-13-078/SPLP…` (524,346 B, 259 ways — carries SPJC-side service roads) are the 08-30 tile-build cuts, engine 1.50.1714.

## 2. What fires (09-02 arms; phase times from `~/.ortho4xp/auto_patch_build_times/*.json`)

Phase seconds, last 09-02 entry — SPJC 166.2 s: solve 113.2, emit/finalize 49.2, rects/junctions/roads 3.1, rest 0.9. SPLP 9.5 s: solve 6.8, emit 1.6. CYXY 41.5 s: solve 30.9, emit 9.2. Solve+emit is 97–98 % everywhere; SPJC solve alone is 1.9× the 60 s budget.

| pass (review §Architecture / brief list) | SPJC | SPLP | CYXY | evidence |
|---|---|---|---|---|
| runway datum + FAA profile | fires (2 rwy, `o4_single_poly`) | fires (1) | fires (7 rings) | patch roles |
| taxi rects / global slice / junctions | fires 397 junctions | 24 | 113 | roles |
| service roads / service junctions | fires 115 | 14 | 84 | roles; `road-piece-ledger` 12–13 seams |
| building pads (`O4_DSF_OBJECT_*`) | fires 71 + 17 object_pad; 88 pad rings stood down as weld hosts | 3 | 24 | roles; ledger tail |
| tunnels / walls | **fires small**: 2 tunnel_ramp + 2 retaining_wall (tunnel_wall) | no-op | no-op | roles; `tunnel_vetoes` 1.4 kB / 3.7 kB / 0 |
| bridges / decks (`road_bridge_decks`) | no-op (key empty) | no-op | no-op | sidecar |
| basins (`basin_facilities`) | no-op | no-op | no-op | sidecar |
| adjacent-ground bands (graded_strip/adjacent_ground) | fires 192 strips | 25 | 87 | roles |
| gap-fill drainage spines + interior rings | fires 46 + 57 | 5 + 8 | 29 + 44 | `o4_feature` |
| apron lattice / spine stations | fires 88 + 12 | no-op | 17 + 2 | `o4_feature` |
| crown spines / runway crown | fires 2 spines, 961 nodes crowned (08-16 log) | 1 | 3 | `o4_feature`; `crown_gap` junction 223 / rwy 15 |
| OLS cuts / ols_road | fires 16 | 6 (+7 ols_road refs) | 6 | roles |
| runway-end skirts / RESA | fires 8 + 1 | 1 | 7 | refs |
| terraces (`terrace_joints`) | no-op | no-op | no-op | sidecar keys empty |
| pavement scorer v2 (shadow) | 30/598 differ, 55 gated out of APRON | 1/46, 9 gated | 22/249, 82 gated | `[pav-score]` ledger tails |
| FGP S1–S3 | gate-OFF (byte-identical) | same | same | STATUS 20260902a |
| nid-level final weld residue | 11 post-projection adjacencies | 0 | 6 | `[pav-builder]` tails |
| emit decimation | 236 vertices retained | 36 | 74 | tails |
| tile_cut | fires only in tile builds (SPLP two pieces) | — | — | data-repo pieces |

Unknown for the 09-02 arms: per-pass lines before the last ~6 kB of the run-ledger `output_tail` (`Ortho4XP/tools/run_ledger.jsonl`, 09-01T23:51–23:52 rows) — the full `.progress` logs were deleted with `/tmp/harness`; the only complete SPJC/SPLP/CYXY logs on disk are `Ortho4XP/tmp/final_{SPJC,SPLP,CYXY}.log` (08-16, pre-Batches 1–4) and `/tmp/harness/r1s_cyxy_off.progress` (09-03, CYXY only, 47.9 s, sha `3a4217e5…` ≠ the 09-02 body).

## 3. Law-true census (09-02 sweep, `Ortho4XP/tmp/census_cache/*.json` stored 2026-09-02T00:14, ruleset icao, `pass: false` on all three)

| airport | total | airside (acceptance) | groundside | top classes |
|---|---|---|---|---|
| SPJC | 686 (685 within, 1 step) | **596** | 90 | airside_no_step apron\|building 203, building\|junction 141, strip_arc 57, drainage_spine apron 37, no_step apron 34, transverse road 28 / junction 26, no_step junction 28, no_step ?\|building 25, road_cross_section 33, apron_lattice_membrane 14, within_shape 22 |
| SPLP | 35 | **27** | 8 | strip_arc 17, road_cross_section 8, strip_longitudinal 4, **within_shape runway\|runway 3 (1.68–1.73 % vs 1.5 cap)** + junction 1, airside_no_step runway 1, drainage_spine 1 |
| CYXY | 160 law-true, 153 adjudicated (7 runway_intersection out of scope) | **67** (74 raw) | 86 | transverse service_road 32 / service_junction 26 / apron 14, airside_no_step junction 17 + apron 7, road_cross_section 23, apron_lattice_membrane 12, runway_crown 7, within_shape 12, runway_end_skirt 3 |

So the zero-airside families v2 must close: at SPJC it is almost entirely pad↔pavement steps (369 of 596) plus strip arcs and drainage spines; at CYXY transverse/no-step at junctions; at SPLP the strip arcs and the runway itself. The plan's "(not split)" for SPJC/SPLP is answered above (596 / 27). SPLP's three runway rows contradict "runway profile: 0 on all five" (`zero-airside-plan-20260903.md:24`) — the twin measures the centreline profile, the census measures ring pairs.

## 4. The mesh side

- Ingestion: `src/O4_Vector_Map.py:2526` `include_patches` reads each `*.patch.osm` with `OSM_layer.update_dicosm` (0.1 s class, memory `include-patches-27s-was-union-not-parse`), then for every way: altitude from `cst_alt_abs`/`altitude`/`node_altitudes` (:2648–2691), per-node `alt_abs` override (:2778–2788), closed way → `vector_map.insert_way(..., PATCH_RING_MARKER, check=True)` (:2804) and `ops.unary_union` of all rings once (:2850, the former quadratic accumulator). Open ways → `DUMMY` (:2824). `PATCH_RING_MARKER` = INTERP_ALT|WATER|SEA|SEA_EQUIV = 15 (`O4_Vector_Map.py:97`).
- `insert_way` (`src/O4_Vector_Utils.py:317`) calls `insert_edge` (:187) per chord with `check=True`: an R-tree query and `are_encroached` against every existing edge, splitting both at transverse crossings and re-dicing colinear overlaps (:215–300). Cost ∝ chords × local edge density — this is where 2 m apron chords and interior rings are paid in step 1, but step 1 minus autopatch is only 2.5 s (−13-078), 2.6 s (−13-077), 3.1 s (+60-136) per `~/.ortho4xp/tile_build_times/*.json` (08-30 entries: vector 352.4/37.9/123.6 s of which autopatch 349.9/35.3/120.5).
- Step 2 (`O4_Mesh_Utils.py:1040` `build_mesh`): Triangle4XP `-pq<min_angle>AuYB` on the `.poly`; then `post_process_nodes_altitudes` (:652) harmonic-extends patch-valued altitudes over free interior vertices (:786–837, R18-1b/c). Measured step-2 wall 08-30: −13-078 **8.1 s**, −13-077 **23.3 s**, +60-136 **11.2 s** (`Ortho4XP.log` 17643–17745). Whole-tile the mesh is cheap; the patch generation is 30–40× it.
- Constrained-edge counts (`Ortho4XP/Tiles/zOrtho4XP_+60-136/Data+60-136.poly`, 08-28): 92,380 segments — DUMMY 47,041, WATER 33,406, **patch rings (15) 7,163**, INTERP_ALT 4,043, apt.dat 16/32 239; 71,115 input nodes, CYXY patch 6,660 of them; mesh 726,617 vertices. `-13-078` (07-25, pre-marker-15 code): 64,344 segments, 53,539 nodes, mesh 112,276 vertices. No `.poly` exists for the 08-30 builds (the data-repo `Tiles/` holds only `.alt/.apt`).
- What drives cost, per `tools/chain_divergence_audit.py:1–60` and `docs/chain_identity_one_solve_plan.md:18–30,160–175`: T-vertices, near-parallel constrained pairs ≤ 15 cm, twin rings, sub-micron clusters — the CYXY weld bake went 26,727 → 1,552,854 airport-region triangles on exactly these, and the nid-level weld brought it back to 24,333 (welded flat bands are triangle-negative). No memory file `chain-divergence-audit` exists; the tool docstring and that plan doc are the record. Current residue at the three airports: 165/0/33 coincident-coordinate twins; 11/0/6 post-projection weld inserts; the tile verify logs (`/Users/noah/XPTerrainBuilderData/Patches/-20-080/-13-078/auto_patch_verify_debug.log`) report 12 epsilon-wedges at SPJC (0–55 mm), 4 at SPLP, 8 at CYXY — the audit itself was not re-run on the 09-02 arms.

## 5. Not a lawful surface even where the census passes

1. `WARN: node_altitudes misaligned with ring … per-vertex altitudes dropped for this shape` — 1 shape at SPJC, 2 at CYXY drape to raw DEM silently (ledger tails 09-01T23:51/23:52).
2. `[single-authority] mode=EMIT: 53 (SPJC) / 13 / 39 node(s) where the author differs from the tier mean` (32/9/30 ≥ 0.01 m) — two writers disagree on emitted values.
3. `POST-PROJECTION WELD RESIDUE` 11 / 0 / 6 adjacencies "NO law priced them".
4. `G-APRON-AIRSIDE gated 55 / 9 / 82 shape(s) out of APRON … vouch for nothing`.
5. Verify log at −13-078: ADJACENT-GROUND "un-cut above ceiling" up to 6.7 m on SPJC aprons (9 sites), RUNWAY-GRADE 1.77 % on SPLP 02/20 (08-30, pre-H7 — but the 09-02 census still carries 3 runway rows).
6. Mechanism remnants present in the patch body: 57+8+44 `gap_interior_ring` DUMMY rings and 46/5/29 drainage spines, 88 `apron_lattice` ways at SPJC, 2 tunnel ramps + 2 walls at SPJC (the 08-16 log vetoed both SPJC tunnels — the current pair is unexplained by any log I could find), 13 SPJC / 8 CYXY apron rings carrying a single way-level `altitude` (4–14 node flat slivers), 165 coincident node twins at SPJC. Per memory `spjc-is-gentle`, 596 airside rows at an airport the prototype built acceptably is itself the bug signal; 344 of them are pad-vs-pavement steps.

## Could not verify
- Full `[pav-builder]` logs for the 09-02 SPJC/SPLP arms (only the last ~6 kB survive in the run ledger); no build was run.
- Triangle counts for the 08-30 tiles (no `.ele`/`.poly` retained; `.mesh` gives vertices only); Triangle4XP counts for `-13-077` (no working dir).
- `docs/specs/auto-patch-v2-plan.md` referenced by `review-20260903-week.md:151` does not exist anywhere in the repo or worktrees.
- `tools/INDEX.md` referenced by root `CLAUDE.md` does not exist at `Ortho4XP/tools/INDEX.md` (`tools/README.md` is what exists).
- `check_grade` "20 passes" enumeration: the review doc has only the redundancy table (rows a–n above), not a numbered pass list; the table's row set was used.
