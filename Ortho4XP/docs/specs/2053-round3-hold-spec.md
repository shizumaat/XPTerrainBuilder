# #2053 round 3 — the mesh holds the bridged-ground cut (Fable review spec, 2026-11-13)

Reviewer: Fable scout after the missed round 2 (`claude/lisland2` 397e54dca on 4a11309d8), one-miss rule (RULINGS 2026-11-11c). Nothing here was built; every bar in §5 needs the one closing build.

## 0. Verified / not verified

Verified by reading: round-2 diff (`floor_m` in `terrain_cut._floor/_cut_grid/cut_fit`, `TerrainModel.cut_floor_m`, record key `cut.floor_m`, `terrain_cut_stage._fit`); `Utils/src/Triangle4XP.c` (criterion ~7328–7366, weight load ~17094–17155, `altitude()` 3599, node output ~15743); `O4_Mesh_Utils.build_curv_tol_weight_map` (539), `apply_inset_box_curv_weights` (513), `post_process_nodes_altitudes` (2052–2395); `O4_Mesh_Pins.py`; `planar/build.py` 451–476 (`dem_z` substitution site); `constraints/terrain_shaped.py`; `geom/terrain_deck.py`; `airport/bridged_ground.py`; `airport/terrain_model.py`; RULINGS 13g/13i/13k.

Measured offline from `dsf:obj2327` `colegioNavalBase.obj` (frame `lisland2053/o4_v2_rebake_SBRJ.json`, elevation −1.587, `erode_m` 5.0), 1 m bins: 97,040 covered cells, 0 holes; 24,016 (24.7 %) have a roof ≥ 3 m over a ground-level floor (median y 5.15); single-surface cells 56,768 at ground level (y 4.6–5.6 → 3.56 m MSL), 11,580 lower (quay y 2.65, skirt to −0.2), 2,895 at y 5.6–8.1, 1,781 at y ≥ 8.1 (floorless roofs `_floor` cannot see). 125,199 of 126,399 m² faces up (no hull bottom). Share of inner ground-level samples whose lowest floor within r is > 0.5 m under them: r 2 → 1.3 %, 5 → 4.7 %, 10 → 10.3 %, 15 → 16.0 %, 30 → 31.8 %.

Not verified: round-2 figures (4244 / 1539 / 1.45 m, 1148 of 1422, 117 under way −10550) are from the lane report; the measuring script and build products were deleted; curvature_tol 2 / inset weight 6 from the report.

## 1. Verdict on round 2

Keep the `floor_m` plumbing with one change to the band rule (C1). It is not the fix: the failure is in how the raster becomes the drawn surface.

1. Every ordinary mesh vertex is the bilinear raster at the vertex (Triangle4XP ~15743, `altitude` 3599); `post_process_nodes_altitudes` overwrites only water vertices and INTERP_ALT corners.
2. 13k's "no triangle pokes" proof assumes triangles no wider than `ERODE_M`; `bridged_ground.ERODE_M = CELL_M = 5 m`, but a drawn point's support is one triangle edge + one posting diagonal (~30 + 14.6 m). Nothing on the mesh side replaced the guarantee.
3. Triangle size is curvature-only: refine when `maxedge_m × K × w > curv_tol`, never below one posting. At w 6, tol 2, px 10.3 m: edges ≤ 14 m for a 2.5 m step, 35 m for 1 m, 71 m for 0.5 m.
4. Patch nodes inside the plan carry `alt_abs` at the uncut DEM and ramp attribute-0 triangles up into the open ground.
5. Worst poke ≈ DEM 5.0 − island 3.56 = 1.44 m (1.44 baseline, 1.45 round 2): an uncut source, not a sag (inference). Candidates: patch-road nodes, ring vertices mixing an uncut posting, uncut ground under floorless roofs.

Smaller defects in 397e54dca: in the 10 m band the bound is `max(eroded top, lowest)` and `lowest` can be an arm's rim underside over low open ground; `_floor` reads `bot` (any orientation) and cannot see a floorless roof.

## 2. Mechanism (general rule)

A cut record that names `erode_m` (an object carrying riders) gets the 13k guarantee from the MESH: (a) posting-sized triangles wherever the cut ground steps by the 0.5 m ground visibility bar; (b) after meshing every free vertex is lowered by the least amount that puts every drawn triangle under the object's bound, sampled at 1 m; (c) the patch reads the cut ground under the plan. A terrain model's record (no `erode_m`) is byte-identical.

Rejected: curvature weight alone (cannot go below a posting, does nothing for uncut sources); finer cut postings (raster is tile-wide); lattice input nodes / regional max area (no precedent, hairline risk, 09x reserves `a` for the bank annulus); plain star-minimum (sinks every slope).

## 3. Ordered changes

**C1 `auto_patch_v2/airport/terrain_cut.py`.** Split `_cut_grid` into `_bound(bot, top, cell, erode_m, floor_m) -> ndarray` (all `CELL_M` → `cell`); `_cut_grid` calls it at `CELL_M` (assert bit-identity for terrain models). When `floor_m > 0`: `bound = where(edge <= BAND_M, eroded_top, eroded_floor)` — no `lowest` term. `floor_m == 0` unchanged. New `HOLD_CELL_M = 1.0`, `hold_bound(tris_authored, erode_m, floor_m) -> (x0, z0, bound)` (1 m bins, one-cell erosion). Binning via `terrain_shaped.grid_of_triangles`/`_bin` gaining `cell=CELL_M` through a shared `bin_triangles(p, cell) -> (x0, z0, bot, top)`; NO new `DeckGrid` field (pickled in captures). New pure `hold_heights(xy, z, tris, free, sample_xy, sample_bound) -> (z_new, unresolved)`: per mesh triangle take the covered 1 m sample centres with barycentrics λ; ≤ 20 passes: `e = Σλ_i z_i − b`, bad if `e > 1e-3`; per bad sample pick the free corner k maximising `λ_k × max(z_k − b, 0)`, lower by `d = min(e/λ_k, z_k − b)`; each vertex takes its largest d; stop when none bad or no bad sample has a free corner above b. Only lowers; never below the lowest bound in its star. `b = z0 + bound − UNDER_M`.

**C2 `auto_patch/terrain_cut_stage.py` `hold(tile, vertices, corners, fixed) -> dict`.** For each `cut_records(patch_dir)` record whose `cut` names `erode_m`: triangles meeting `plan_box`, project with `projector` + `fit.local`, `hold_heights` with `free = ~fixed`, write column 2 and zero normal columns 3–4 of moved vertices (`O4_Mesh_Pins` convention). One log line per record (lowered, worst move, unresolved). Never raises into the build (same try/log shape as `bake`). Called in `O4_Mesh_Utils.post_process_nodes_altitudes` after the stranded-pins block (~2375), before "Writing output nodes file"; `fixed` = all `interp_alt_tris` corners ∪ `water_valued` ∪ `pins[0]`.

**C3 `O4_Mesh_Utils.py`.** Factor `apply_inset_box_curv_weights`' cell arithmetic into `raise_box_curv_weight(tile, weight_array, box, weight) -> int` (inset function calls it — no near-duplicate). In `build_curv_tol_weight_map`, outside the `apt_curv_tol` switch: for each held record's `plan_box` raise weight to `tile.curvature_tol × posting_m / HOLD_STEP_M`, `HOLD_STEP_M = 0.5` (owner ground bar 2026-10-15; ~41 on SBRJ). Boxes from `terrain_cut_stage.held_boxes(tile)`.

**C4 new `auto_patch_v2/airport/object_ground.py`.** Fourth substitution at `planar/build.py` 451–476 after `covered_ground` (#714), `road_shadow` (#951), `bridge_ground` (#1935): for every `airport.terrain_models` entry with `seat_by == bridged_ground.SEAT_BY` and every vertex no airside face carries (`_airside_vertices`): `zs[v] = min(zs[v], target_at(cut_fit(grid, z0, heading, erode_m, cut_floor_m) at model.xy)[v])`. Cut only. One `[planar]` log line. Seat (`bridged_ground._models`) runs before and keeps the uncut DEM. Register in `pipeline/stage_code.py`, `airport/partition_code.py`, `auto_patch/provenance_code.py` beside `bridged_ground`.

**C5 tool `Ortho4XP/tools/drawn_cover.py`** (+ INDEX row + twin `tests/test_drawn_cover.py`, same commit; `drawn_site.py --cover` hands over). Imports `drawn_site`'s `DrawnMesh`, `Resources`, `pack_rows`, `row_base`, `tile_triangles`. `drawn_cover.py ICAO --tag T --object SUBSTR [--patch P.osm] [--bar 0.05] [--json] [--against BASE.json]`. Installed products only; object as written binned at 1 m; per sample `mesh − (base + top)`. Classes OPEN (top − low < 3 m; floorless roofs fall here) / ROOFED (reported vs floor, not judged); band (≤ 10 m from edge) / inner; on-/off-patch (`tools/patch_faces.PatchFaces`). Each sample over the bar names its drawn triangle's highest corner: patch node, water, plan edge, inner. Sections SINK (OPEN share > 0.5 m under top), RIDERS (pack rows anchored on the plan, mesh vs top, list > 0.5 m), RIM (drawn ground 1.5 m outside each edge run). Exit 0 only when off-patch OPEN samples over `--bar` are 0. Commit the tool BEFORE the closing build.

**C6 docs.** `terrain_cut` module doc: THE HOLD + the consumer rows. `bridged_ground` doc: correct the 5 m-erosion claim. No RULINGS append (master records).

## 4. Consumer census (tile ground inside a held plan; RULINGS 2026-08-30l)

| Consumer | Reads | Ruling |
|---|---|---|
| Triangle4XP refinement | `.alt` curvature × weight | weight raised over plan box (C3) |
| Free mesh vertices (attr 0) | bilinear `.alt` | held (C2) |
| Plan-edge ring vertices (DUMMY) | bilinear cut/uncut | held like any free vertex |
| Water / sea vertices | water datum | fixed (09m/09z) |
| INTERP_ALT corners (patch, ribbons, apt.dat) | column 5 | fixed in mesh; right at source by C4 |
| Patch-pinned stranded vertices (#2034) | column 5 | fixed |
| Patch groundside vertices under plan | `Vertex.dem_z` | substituted with cut ground (C4) |
| Patch airside vertices | `dem_z` | untouched (airside is king) |
| Patch row reading `airport.dem` directly | corpus DEM | probe first (§6.2); fix in same PR and list |
| Seat (`bridged_ground._models`, `terrain_model`) | corpus DEM | uncut, unchanged |
| Step-1 roads, unpatched airports | `tile.dem` | follow cut raster, unchanged |
| Pack OBJECT/AGL riders on plan | drawn mesh | follow held ground; RIDERS reported, not gated |
| Refinement re-bake (`tile.iterate`) | rewritten `.alt` | re-applies cut; hold after every mesh |
| Terrain models (no `erode_m`) | — | no weight/hold/C4: byte-identical |
| Hidden models | — | not cut, not held |
| Step reuse | cut ids | unchanged + C4 registration |
| Masks, DSF raster, coastline | source DEM | unchanged |

## 5. Bar (one closing build `SBRJ --tile -23 -44 --pack-copy`)

`drawn_cover.py SBRJ --tag <tag> --object colegioNavalBase --patch <patch>`:
- B1 off-patch OPEN samples > 0.05 m over top: 0 (band and inner).
- B2 on-patch samples > 0.5 m over: 0; 0.05–0.5 listed with attribution.
- B3 both bridge far ends within ±0.1 m (`drawn_site.py --site` each end, `--tol 0.1`).
- B4 `drawn_gate.py` PASS at the site (`--against` only if a control exists; do not build one).
- B5 Sugarloaf still 12,626 postings cut, no hold line for it.
- Reported only: SINK (~10 % expected), RIDERS > 0.5 m, RIM, unresolved count.

policeman4 is out of scope (RULINGS 13r, lane lrider13r).

## 6. Order of work

1. Unit tests first (`test_bridged_ground.py`, new `test_terrain_cut_hold.py`): `_bound` at CELL_M == old `_cut_grid` for floor_m 0; band cell beside a high rim-bottom keeps its own top; `hold_heights` — linear ramp unchanged, two-level step under Delaunay → 0 violations and no vertex under the lower level, fixed high corner → unresolved > 0 without digging neighbours below bound, only-lowers; `raise_box_curv_weight` == old inset cells; `hold` skips no-`erode_m` records; `object_ground` groundside-only and never raises; `drawn_cover` twin.
2. SBRJ capture + replay (`--probe-site`, `--why-hard` at the SW-corner road): road vertices at the cut ground; a row still at 5.0 is named and fixed.
3. Closing build, tool, gate, registry twins (stage/step/provenance code, windows_text_io, patch_env_classification, tile_failures, console_encoding), `tests/auto_patch_v2`, `tools/ratchets.py dupes --near` and `unused`.

## 7. Risks

- Riders: a heightfield cannot hold both sides of a 2.5 m quay; ~10 % of ground-level area within 10 m of a step sinks > 0.5 m. Seating plan-anchored rows on the object's surface is a separate owner question.
- Land-side rim: outside 13k's region; reported, not fixed.
- B2 near the plan edge where a road leaves onto uncut land: 0.05–0.5 residuals possible.
- `bot` as floor over-cuts objects with a hull bottom (invisible except to riders).
- Hold overshoot bounded by the star's lowest bound.
- Weight on a `limit_tris`-bound tile acts as priority, not extra triangles.
