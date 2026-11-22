# A custom patch, per airport: as made, our auto patch, or a blend (#2179)

Issue #2179 (owner 2026-11-19T13:07Z), KASE 39.2232, -106.8689. Lane `lspec2179`, spec only:
nothing implemented, nothing built. Law it works under: RULINGS 2026-10-26c ("Use auto patch"),
2026-11-03e (an `_edited` patch is ours), 2026-11-18f (a pack's patch is a WITNESS, relative evidence),
2026-11-18k (a custom patch uses the unmodified airport), 2026-11-18l (a new custom patch turns "Fit
custom airport buildings" off), 2026-11-19b (re-base + blend band), 2026-09-08t (the design surface),
2026-09-10av (the ground datum), 2026-09-09ab (the bank blend), 2026-11-03d (wire number frozen:
capability flags), #1244 (Mac app is the layout authority, Qt mirrors), 05e/05g (no airport-specific
code). Evidence: offline reads of the owner's 1.0.562 files only (§2); scratch scripts
`Ortho4XP/tmp/lspec2179/kase_custom_read*.py` (lane-local, deleted at report; reproduce from §2.1).

A "custom patch" below is 18k's: a manual `*.patch.osm` in the tile's `Patches/` folder other than the
patch editor's own `<ICAO>_edited.patch.osm`. The `_edited` patch is untouched by everything here.

## 0. The answer in three lines per option

* **(a) As made** — the user's patch, unmodified (no re-base, no band), meshed on the elevation it was
  made for: the airport's own sub-DEMs (its lidar inset and approach rings) are left out of the build
  DEM, so around the airport the tile is the base raster exactly as a plain Ortho4XP build. Cheap (no
  solve). Gives the author's intent where the patch covers the pack's pavement; gives NOTHING where it
  does not (KASE: 109,000 m² of the pack's pavement uncovered, edges 1.8 m p50 off the coarse DEM, §2.3).
* **(b) Our auto patch** — the custom file stays where it is but is not applied; v2 grades the airport as
  for any other (complete coverage, law-true, lidar). This is today's "Use auto patch" without the
  rename. Cost: one v2 airport build (KASE 271 s at 1.0.562).
* **(c) Blend** — our auto patch, SHAPED by the custom patch: v2's design solve gains one weak family of
  rows that keeps the patch's RELATIVE heights (height differences between neighbouring vertices inside
  its pads and ramps), yielding to every law row. Coverage, seams and edges are v2's (no step on
  pavement, banks only off pavement); the author's terraces and ramps survive where lawful; grass
  keeps the lidar. Cost: one v2 airport build plus the witness rows. Supersedes 19b's re-base + band.

**Recommended default (owner decides, Q1): automatic, by evidence** — (a) when the fit names a
reference source the build holds AND the patch covers the pack's airside pavement (§5.2); (c) otherwise.
At KASE that picks (c): the patch leaves 35 % of the pack's airside pavement uncovered.

## 1. Census — every code path that reads a custom patch today

`tools/blast.py` run on each module named (index 95fadb7). "Reads" = decides on, loads, transforms,
or shows. The rule "manual patch name" is `O4_File_Names.is_manual_patch_name` (any `*.patch.osm` not
`_auto`); "custom" = manual minus `edited_patch_name(icao)`.

### 1.1 Detection (which file is a custom patch, which airport it covers)

| # | Site (file:function) | What it decides | custom vs `_edited` |
|---|---|---|---|
| D1 | `O4_File_Names.py:is_manual_patch_name / patch_file_icao / edited_patch_name / manual_patch_icaos_in` | the naming rule every other site uses | manual (both) |
| D2 | `O4_Custom_Patches.py:custom_patches / custom_patch_tiles` | the map band + tile info "Custom patch" line (both apps) | manual (both) |
| D3 | `O4_Custom_Patches.py:_unmodified_files / unmodified_airports` | the 18k/18l airport list | custom only |
| D4 | `auto_patch/selection.py:select_patch_airports(manual_icaos=)` via `driver.py:generate_auto_patches` (`manual_icaos_in`, disposition `"manual"` → "Skipping … (manual patch exists)") | the auto patch is NOT generated | manual (both) |
| D5 | `auto_patch/selection.py:manual_patch_files_for / auto_patch_not_applied(edited_ok=)` | the ONE admission test the mesh and the object stage share | manual; `edited_ok` lets `_edited` place |
| D6 | `O4_Vector_Map.py:include_patches` (manual first; `_auto` skipped for a manual ICAO; the verbosity-0 "using the CUSTOM patch" line; `_untagged_user_ring`; `patches_list` gets the ICAO) | what the MESH is built from | manual (both) |
| D7 | `O4_Airport_Utils.py:encode_runways_taxiways_and_aprons / encode_hangars` (skip `if airport in patches_list`) | the legacy Ortho4XP pavement flattening is OFF for the airport | manual (both) |
| D8 | `auto_patch/terrain_cut_stage.py:apply(tile, vector_map, patches_list, …)` | 13k terrain cuts for included airports | manual (both) |
| D9 | `O4_Patch_Rebase.py:_is_custom` | 19b re-base + band apply | custom only |
| D10 | `auto_patch/object_stage.py:_custom_patch_airports`, used by `_object_stage` (placement skip, `_CUSTOM_PATCH_LINE`) and `restore_unpatched_packs` | 18k: pack restored and never placed | custom only |
| D11 | `O4_Qt_Patch_Model.py:is_hand_made` | the Qt patch editor's custom label | custom only |
| D12 | `O4_Patch_Fast_Path.py:_remember`; `O4_Step_Reuse.py:_patch_files / _patch_inputs` | vector-step reuse keys on the patch files | manual (all `*.osm`) |
| D13 | `tile_bundle/inputs.py:user_files`; `tile_bundle/install.py:_place`; `tile_bundle/pack_shipped.py:_set_aside_installed` | bundles carry / set aside custom patches | manual |
| D14 | `o4_engine/patch_commands.py:custom_patches / use_auto_patch / _effective_patch / _save_target`; `o4_engine/patch_drop.py:_patches_under`; `o4_engine/patch_insert.py:_new_patch`; `patch_library/entry.py:change`, `patch_library/apply.py` | the JSONL commands and the patch editor / library writes | manual / edited |
| D15 | Mac: `Sources/SceneryKit/CustomPatches.swift` (`customPatches`, `useAutoPatch`), `BuildModel.swift` (`customPatchTiles`, `useAutoPatch(for:)`), `BuildPane.swift:341` (tile info row), `MapCanvasView.swift` (band). Qt: `O4_Qt_GUI.py:_make_widgets` (button), `_refresh_custom_patch_tiles`, `_refresh_custom_patch`, `_use_auto_patch`; `O4_Qt_Map.py` (band) | the UI | manual |

### 1.2 Re-base (19b) and blend band (19b part 2, lane lrebase2)

| # | Site | Reads |
|---|---|---|
| R1 | `O4_Vector_Map.py:include_patches` → `O4_Patch_Rebase.mesh_path` | the path the mesh loads (copy in `<build dir>/custom_patch_rebase/`) |
| R2 | `O4_Patch_Rebase.py:_prepared` → `_height_points`, `_sources` (build DEM, base raster before insets, every sub-DEM), `_pick_reference` (smallest median \|patch − source\|, ≥ 80 % cover, build DEM wins a tie), `_OffsetField` (Gaussian 200 m on 5 m), `_rebase_text` (pad = field mean over plan, ramp end = field at end edge) | the fit and the re-based heights; `<file>.json` report |
| R3 | `O4_Patch_Rebase.py:_with_band` → `O4_Patch_Band.py:band_rings / band_osm` (`[design] bank_slope` 1:3 daylight, ≥ `bank_min_width_m` 5 m, ≤ `MAX_WIDTH_M` 40 m; holes `o4_void=yes`) | the `bank_foot` rings written into the copy |
| R4 | `O4_Bank_Annulus.py:patch_paths_read` (via `O4_Patch_Rebase.read_path`), `_bank_rings_from_patches`, `_nested`; `O4_Mesh_Utils.py:bank_pavement_lines`, `bank_annulus_blend_values` (09ab); `O4_Patch_Voids.py:is_hole` | the mesh blend over the band |
| R5 | Setting `rebase_custom_patches` (tile, default on): `O4_Cfg_Vars.py` (`list_vector_vars`), `O4_Settings_Model.py:247`, `SettingsLayout.swift:161` | the off switch |

### 1.3 Object fitting (18k, 18l) and the screen records (#2171)

| # | Site | Reads |
|---|---|---|
| O1 | `O4_Custom_Patches.py:stand_down_new` (called from `o4_engine/session.py:_build_worker_loop`), `_signature`, `_seen` (`<build dir>/custom_patches_seen.json`), `fit_state`, `fit_confirm_text`; writes the tile cfg through `O4_Settings_Model.write_tile` | 18l: a new custom patch turns `modify_custom_airports` off |
| O2 | `o4_engine/build_airports.py:build_airports / _custom_patch_fit` → `BuildAirportsReady.custom_patches / fit_buildings / fit_confirm`; Mac `BuildAirportsWire.swift`, `BuildModel.setValue`; Qt `O4_Qt_Build_Airports.py`, `O4_Qt_Settings.py:_confirm_custom_fit` | the Build card and the confirm |
| O3 | `auto_patch/object_stage.py:_object_stage` — the custom-airport `continue` (D10) sits BEFORE `_oplan.from_screen(...)`; `restore_unpatched_packs` → `unpatched_pack.restore_airport`; `_pack_stand_down` | 18k restore; #2171's "screen record STALE → placement SKIPPED" is no longer reached for a custom airport (it still is for `_edited`) |
| O4 | `auto_patch_v2/airport/pack_patch_witness.py:patch_files / read_pads / level_at / pack_pads` (read by `rebake_plan`, 18f) | a PACK-SHIPPED patch as deck/trench witness — reads the pack's folder, never the tile's `Patches/`; the reader (c) reuses |

**One reader, many deciders.** D3, D4, D5, D6, D9, D10 each re-derive "is this airport custom" from
file names. A per-airport choice must be read in ONE place (§5.1) or the mesh and the object stage
will disagree again (the OTHH #13/#15 class `auto_patch_not_applied` was written to end).

## 2. KASE evidence (offline; no build)

### 2.1 What was read

* The owner's build `zOrtho4XP_+39-107/build_logs/20261119T043146Z_+39-107.log` (app 1.0.562): "KASE:
  using the CUSTOM patch KASE.patch.osm", "re-based from base elevation (Viewfinderpanoramas) to the build
  DEM (median +3.6 m)", "blends into the build DEM over a band 5 m wide (p90 7 m)". Its re-based copy
  `custom_patch_rebase/KASE.patch.osm` (+ `.json`: fit median \|d\| Viewfinderpanoramas 2.19 m, lidar
  3.84, build DEM 3.87; band 34 rings, 10 holes, width p50 5.0 / p90 7.4 / max 40 m).
* The input: `XPTerrainBuilderData/Patches/+30-110/+39-107/KASE.patch.osm.disabled` (262 ways: 147 pads,
  114 ramps, 1 malformed; the copy carries the same 262 + 34 band rings). The owner set it aside after
  that build ("Use auto patch"); the next build (20261119T045824Z) is the auto patch (271 s). The
  installed DSF is therefore the AUTO build — the custom mesh is gone, so §2 reads the patch surfaces
  against the DEMs, not a mesh.
* DEMs: `KASE_usgs3dep.tif` (1 m, the build's inset) and `N39W107.hgt` (3″ Viewfinderpanoramas, the base).
* The pack's airside pavement: our auto patch's runway/taxiway/apron rings (`role` ∈ runway,
  primary_parallel, stub, junction, apron) from the same tile, 312,190 m² — the pavement v2 reads from the
  pack (Fly2High KASE XP12) and apt.dat.
* Landmarks: RWY 15 threshold 39.23221, -106.87317; RWY 33 threshold 39.21157, -106.86333 (pack apt.dat
  row 100); "east/west" = side of the 15/33 centreline.

### 2.2 The mechanisms, measured

**M1 — the patch does not cover the pack's pavement, and its edges meet that pavement with a step that
19b turns into a 1:3 bank ON the apron. Dominant.**

* 108,900 m² of the 312,200 m² of pack airside pavement (35 %) lies outside every custom-patch ring.
  Largest pieces: **the main apron east of the runway at midfield, 86,500 m²** (pack DSF apron `pol43`,
  around 39.22352, -106.86725 — ~1,080 m down RWY 15 from its threshold, ~145 m east of the centreline);
  7,400 m² at 39.21559, -106.86372 (~2,015 m down, 125 m east); 4,200 m² at 39.21451, -106.86411
  (~2,115 m down, 50 m east).
* On a custom-patch build that pavement is meshed on the 1 m lidar (D6/D7: KASE is in `patches_list`,
  so the legacy flattening skips it too). **The lidar is not the problem there**: residual from a 15 m
  local plane over the uncovered pavement is p50 0.006 m, p95 0.036 m, max 0.47 m.
* **The edges are.** 4,516 m of patch-ring edge lies inside the pack's pavement. Patch height minus the
  ground 1.5 m outside the ring:

  | patch | vs | \|dz\| p50 | p90 | edge > 0.5 m | edge > 1.0 m |
  |---|---|---|---|---|---|
  | authored | lidar | 3.16 m | 4.28 m | 4,493 m | 4,322 m |
  | re-based (19b, as built) | lidar | 0.55 m | 1.81 m | 2,377 m | 1,244 m |
  | authored | base .hgt (the DEM it was made for), 30 m out | 1.77 m | 4.16 m | 3,224 m of 3,461 | 2,827 m |

* 19b's band lays a 1:3 (33 %) ramp, ≥ 5 m wide, outside the PATCH's paved union — which here is the
  PACK's pavement: **≈ 23,300 m² of band lies on the pack's apron/taxiways**, largest 9,500 m² at
  39.22344, -106.86754 (main apron, ~1,080 m down RWY 15, ~120 m east), then 4,000 m² at 39.21962,
  -106.86527 (~1,550 m down, 155 m east) and 3,200 m² at 39.22777, -106.86927 (~580 m down, 145 m east).
* Worst edge sites after the re-base: patch ramp way −58329 beside the pack's pavement from ~390 m to
  ~625 m down RWY 15, ~148 m east (patch +2.2 … +3.1 m above the pavement; e.g. 39.22870, -106.86966);
  pad −35728 at 39.22598, -106.86802 (~800 m down, 150–177 m east; +2.3 … +2.5 m).

These lips and 1:3 ramps on the apron are the "unusable pavement spots".

**M2 — re-base residual at seams (small, new).** Seams between touching patch rings on the pack's
pavement: 12; with a step > 0.25 m: authored 1 (max 0.45 m), re-based 3 (max 0.45 m) — e.g. pad −35540 |
ramp −55190 0.43 m at 39.21883, -106.86378 (~1,675 m down RWY 15, 243 m east): touching pads take
different means of the 200 m field. (The patch's 32 seams > 0.5 m, up to 6.0 m, all lie OFF the pack's
pavement — authored terraces around buildings, e.g. pad −60256 | pad −60288 at 39.21936, -106.86264.)

**M3 — DEM coarseness.** The patch's flat pads stand over lidar that varies under them: 84 of 126 pads
≥ 30 m² have a lidar spread (p95 − p5) > 1 m; worst pad −33402, 7,190 m², 4.8 m, at 39.22169,
-106.87012 (~1,190 m down RWY 15, 160 m west). That is cut/fill, not unusable pavement (the pad is
flat); its edge step is what the band absorbs on grass. On the coarse .hgt the same steps existed
(third row of the table) but Ortho4XP's mesh on a 90 m raster has few vertices off the rings, so a step
spreads over one long triangle: 1.77 m p50 / 4.16 m p90 over ~30 m is 6 % / 14 % (an ESTIMATE from the
raster, not a mesh; L2 measures it). The coarse DEM hid the steps; it did not remove them.

### 2.3 What the evidence says about the options

* (a) would NOT make KASE's apron usable: the patch was not made for this pack's apron (35 % uncovered),
  and on its own DEM the uncovered-apron edges are still 1.8 m p50 off. It is right for a patch that
  covers its pack's pavement — the usual case: a patch shipped with the pack it was built for.
* 19b fixed the absolute level (pads −3.70 → −0.07 m vs lidar) but its band is placed by the patch's
  coverage, not the pack's, so at KASE it ramps across the apron (M1).
* (b) is complete and law-true (the owner's own move at 04:58Z).
* (c) is (b) plus the author's shape: M1 disappears (v2 covers and welds the apron; contacts flush and
  tangent, 08t (5)), M2 disappears (seams are v2 faces under the law), M3's cut/fill becomes v2's bank law
  in the graded strips.

### 2.4 Elevation at the edge of the airport (for (a))

KASE's inset reaches only KASE (`KASE_usgs3dep.json` bbox -106.8816 … -106.8564, 39.2054 … 39.2394);
KEGE and KLXV are ~50 km away. Base .hgt minus lidar along the patch rings' hull grown by 150 m (15.7 km
of edge, 66 % inside the inset): \|d\| p50 3.5 m, p90 8.8 m, max 17.8 m (KASE lies in a valley the 3″
raster smooths). A 60 m feather (`airport_elevation_inset_feather_m`) over that would be a 15 % p90 / 30 %
max ramp around the airport, crossing Highway 82 — so (a) must not cut a hole in the lidar around the
patch; it must leave the airport's sub-DEMs out WHOLE (§3).

## 3. (a) "As made" — the DEM it was made for

**Reference.** 19b (2)'s fit, unchanged (`O4_Patch_Rebase._pick_reference`): the source with the smallest
median \|patch − source\| over the patch's height points, among the build DEM, the base raster as read
before any inset, and each sub-DEM, ≥ 80 % cover, build DEM wins a tie. No new threshold. Outcomes:

* reference = build DEM → (a) is "the file as authored on the build DEM" (no re-base, no band);
* reference = the base raster → (a) leaves out the airport's own sub-DEMs (below);
* reference = a sub-DEM other than the airport's (rare: a neighbour's inset) → (a) keeps that one and
  leaves out the others the airport owns;
* no candidate (patch outside every source's cover) → (a) is "as authored on the build DEM", and the card
  says the reference is unknown.

**Operationally.** The airport's sub-DEMs are the inset(s) `O4_Airport_Elevation_Insets.ensure_insets_for_tile`
fetches for that ICAO (composite `assemble_inset_composite_source`, raster bake
`bake_airport_insets_into_alt_dem`, 60 m feather) and its approach rings
(`O4_Elevation_Level.ensure_approach_rings` / `bake_approach_rings_into_alt_dem`). For an (a) airport whose reference
is the base raster, those sub-DEMs are left out of BOTH halves (query composite and `.alt` bake) — one
exclusion list handed to both, so the G2 "one surface, two readers" law holds. Nothing else changes:
other airports' insets and rings stay; where one of them overlaps the (a) airport's patch hull + 150 m,
that overlap is excluded from it and the existing feather ramps it (KASE: no overlap).

**Where the airport meets our DEM.** There is no new seam at the airport: the tile around it is the base
raster, as a plain Ortho4XP build — the author's world. The seams that remain are the existing outer
edges of OTHER sub-DEMs. Inside, the mesh is what Ortho4XP made for the author: each ring an INTERP_ALT
barrier at its tagged height, the DEM outside, no band (19b's band and re-base are off for (a)).

**Cost / loss.** No solve; one fewer inset fetch. The lidar is lost for the whole airport area (the
owner's 00:18Z "grass gets the lidar detail" does not hold for (a), by definition). The pack is used
unmodified (18k), the "Fit" switch as 18l.

**Failure modes.** F-a1 coverage gap (KASE): the evidence row says so (§5.2) and the automatic default
picks (c). F-a2 the author used a raster we do not hold (another 1″ source): the fit picks the nearest;
the card names the reference and its median \|d\|. F-a3 the patch crosses a tile edge: per tile, as
patches are; the neighbour tile's own patch decides there.

## 4. (c) "Blend" — the patch's relative heights in our solve

### 4.1 Algorithm

1. **The witness.** The airport's custom patch is read by `auto_patch_v2/airport/pack_patch_witness`
   (18f's reader, extended to a tile `Patches/` file): each pad a flat level, each ramp a profile from
   its low short side to its high one — extended to honour `profile` / `steepness` / `cell_size` exactly
   as `include_patches` meshes them (7 KASE ramps carry `profile`), one function both read.
   `level_at(v)` answers the author's height at a point.
2. **Relative, not absolute (18f: "relative evidence, not absolute targets").** For every edge (u, v) of
   the planar map whose two vertices lie inside the SAME witness ring and on faces of the pavement roles
   or the graded-strip roles, one row
   `(z_u − z_v) − (level_at(u) − level_at(v)) = 0` at weight `[design] author_shape` (new law-table key,
   start 30 — between `ground_datum` 3 and the law's 300 — set by the L3 replay sweep). Edges whose ends
   lie in two different rings carry NO row: an authored step between rings on pavement is a gap the law
   grades (08t (5) flush and tangent; the no-step rows), within the grade caps of `Law.for_airport`.
   Gradients are invariant under a constant offset and nearly so under 19b's 200 m field, so (c) needs
   no re-base: the absolute level comes from v2's own anchors (CIFP threshold pins, the ground datum §23,
   datum chaining 08t (6)).
3. **Single derivation site.** A new module `auto_patch_v2/solve/design_witness.py` (sibling of
   `design_ground.py`) is the ONLY place that says which edges carry an author row;
   `solve/design.assemble` mints the rows from it and `tools/v2_why_solve` names them from it.
4. **Merge with our patch = the patch IS ours.** v2 builds the whole airport (all pack pavement, zones,
   structures, roads); the witness only adds rows. Pavement the custom patch does not cover (KASE's
   apron) has no rows: it is the auto patch there, welded to the witnessed surface by the contact law.
   Ground outside v2's faces is the build DEM (lidar). The custom file is not meshed (D6 skips it).
5. **Emit / freshness.** Written as `<ICAO>_auto.patch.osm` (the name every reader admits); the freshness
   stamp gains `o4_custom_witness` = sha256 of the custom file's body (provenance `FRESHNESS_KEYS`,
   `engine_v2._stamp_header`, keyed by content per 13o) and the choice; a changed patch or choice rebuilds.
6. **Report.** `report.json` and the build log: rows minted, the witness residual inside rings (p50/p90 of
   \|Δz − Δlevel\| per edge), metres of authored on-pavement steps graded, and the five worst by
   lat, lon. Log line: "KASE: blend — our auto patch, shaped by your custom patch KASE.patch.osm".

### 4.2 How it differs from 19b

| | 19b re-base + band (today) | (c) blend |
|---|---|---|
| Surface meshed | the user's rings, each moved by a smooth offset | our v2 patch |
| Coverage | the patch's (KASE: 35 % of the pack's pavement uncovered) | the pack's pavement + zones, complete |
| Pad shape | one height per pad (flat, as authored) | the author's relative shape, yielding to law |
| Seams between rings | kept (re-base adds steps: 3 > 0.25 m at KASE) | graded by the law (no step on pavement) |
| Edges | 1:3 bank from each ring edge, on whatever lies there (≈ 23,300 m² of KASE apron) | v2 graded strips and bank law, off pavement |
| Absolute level | build DEM − patch, low-passed 200 m | v2's anchors (CIFP pins, ground datum) |
| Cost | ~1 s | one v2 airport build (KASE 271 s at 1.0.562) |

### 4.3 Feasibility and failure modes

* **Feasibility.** v2's design solve is one weighted least squares (08t); added rows can never make it
  infeasible. Row count ≈ edges inside rings (KASE: a few × 10⁴), small next to bending + law rows.
* F-c1 author's ramp steeper than the cap → the law row (300) outprices the witness (30): graded to the
  cap; reported as a witness residual.
* F-c2 author's runway profile vs CIFP → pins are equalities; the runway's chord/vertical-curve rows are
  law; the witness yields; residual reported.
* F-c3 patch made for another layout (KASE) → its rings over grass carry no rows (only pavement/strip
  faces do); over pack pavement only within-ring differences — harmless where misaligned (flat pad =
  "flat here").
* F-c4 weight too high → micro-steps of the author's mesh show through within rings; too low → no visible
  effect. L3 sweeps 10/30/100 on the KASE replay; bar: census law-true counts no worse than the auto
  replay, witness residual p90 ≤ 0.1 m inside rings where no law row binds.
* F-c5 this amends 08t (1) ("never a per-vertex pull on pavement") for (c) airports only: the witness is
  a pull on height DIFFERENCES, not levels — recorded with the owner's choice of (c).
* F-c6 objects: the airport is auto-patched, so the pack's objects are placed as for any auto airport,
  under the "Fit" switch (18l). 18k applies to (a) only. Owner Q3.
* F-c7 build time: (c) is (b)'s cost plus < 1 % (rows). KASE is over the 60 s budget already (271 s);
  not this spec's to fix.

## 5. The setting

### 5.1 Storage and the one reader

* **Tile setting `custom_patch_use`** (`O4_Cfg_Vars`, type `list`, default `[]`, in `list_vector_vars`
  beside `rebase_custom_patches` so the vector step keys on it — `O4_Step_Reuse._step_settings`). Items
  `"ICAO=mode"`, mode ∈ `as_made` | `auto_patch` | `blend`; an ICAO not listed takes the default (§5.2).
  Written through `O4_Settings_Model.write_tile` (as `stand_down_new` writes `modify_custom_airports`).
  Per tile because a patch is per tile and the tile cfg already travels with the tile and its bundle.
* **The ONE reader:** `O4_Custom_Patches.use_of(tile, icao) -> (mode, reason)` and
  `uses(tile) -> {icao: (mode, reason)}`. Every census row that decides (D3, D4, D5, D6, D9, D10, O1, O2)
  calls it; none re-derives from file names. Concretely: D4 `select_patch_airports` gets the ICAOs whose
  mode is `as_made` as `manual_icaos` (blend/auto airports are generated); D6 skips a custom file whose
  airport is `auto_patch`/`blend` and loads its `_auto`; D5 `auto_patch_not_applied` answers by mode; D9
  re-base is not called for any mode (19b retired, Q2) — `mesh_path` returns the file for `as_made`; D10
  and O1/O2 list only `as_made` airports as "custom" (18k/18l follow the file only when it is meshed).
* `.disabled` (10-26c) still means "not a patch". The picker never renames; "Use auto patch" becomes the
  picker's `auto_patch` (Q4).

### 5.2 The default (owner decides — Q1)

Proposed `default` = automatic, by evidence, computed at the build's start and recorded in
`<build dir>/custom_patch_evidence.json` (the card shows the last one):

* **coverage** = share of the pack's airside pavement (the polygons v2's load stage reads, via its loader
  without the solve) inside the patch's rings; **largest gap** (m², lat, lon);
* **reference** = §3's fit (name, median \|d\|).

`as_made` when coverage ≥ 98 % and no gap > 1,000 m² (one apron stand) — else `blend`. KASE: 65 %, gap
86,500 m² → `blend`. (A ratio and an area, not an airport table; the gate
`test_no_airport_specific_code.py` holds.) The alternative defaults the owner may prefer: always
`as_made` (18k's spirit, cheapest; KASE keeps its spots until the user picks) or always `blend`.

### 5.3 Engine (engine owns cross-platform features)

* Command `custom_patch_use` `{tile: "+39-107", icao: "KASE", use: "as_made"|"auto_patch"|"blend"|"default"}`
  → reply `{tile, icao, use, effective, reason}`; refusal text is the user's sentence (`ValueError`, as
  `patch_commands.use_auto_patch`). Registered in `o4_engine/jsonl` beside `custom_patches`.
* `custom_patches` reply: each tile's entry gains `airports: [{icao, files, use, effective, reason,
  evidence: {coverage, gap_m2, gap_at, reference, fit_m}}]` (additive).
* `BuildAirportsReady` gains `custom_patch_use: list` (one entry per custom-patch airport in the tiles,
  same shape) — additive field on the existing class; no new event class, so no new wire literal in
  `OrthoEngineClient.swift`. Capability flag `"custom_patch_use"` in `events.CAPABILITIES` (the number
  stays 1.32, 2026-11-03d); `tests/test_engine_capabilities.py` covers both halves.
* Build log, verbosity 0, once per airport (replaces today's CUSTOM line for that airport):
  "KASE: custom patch KASE.patch.osm used as made, on the base elevation (Viewfinderpanoramas) it was made
  for." / "KASE: our auto patch is used; your custom patch KASE.patch.osm is kept, not applied." /
  "KASE: blend — our auto patch, shaped by your custom patch KASE.patch.osm." plus, under the automatic
  default, the reason: "(it leaves 86,500 m² of the pack's pavement uncovered, at 39.22352, -106.86725)".

### 5.4 UI — Mac app (authority) and Qt mirror (#1244)

* **Build card, Airports list** (Mac `BuildPane` Airports card from `BuildAirportsWire`; Qt
  `O4_Qt_Build_Airports`): a custom-patch airport's row shows "Custom patch" and a three-way picker
  (proposed labels, Q4): **"As made"** (help: "Uses the patch unchanged, on the elevation it was made
  for. The airport keeps its author's shape; our high-resolution elevation is not used here.") /
  **"Our auto patch"** ("Grades the airport to the slope rules from the pack and our elevation; your patch
  is kept but not used.") / **"Blend"** ("Our auto patch, shaped by your patch where the slope rules
  allow."). Under it, when automatic: "Automatic: Blend — the patch leaves 35 % of the pavement
  uncovered."
* **Tile info, "Custom patch" row** (Mac `BuildPane.swift:341`, Qt `_refresh_custom_patch`): the same
  picker replaces the "Use auto patch" button.
* **Settings > Elevation & Airports:** the "Move custom patches onto this build's elevation?" row goes
  with 19b (Q2). No new Settings row (the choice is per airport).
* `tests/test_qt_layout_parity.py` gains the picker on both surfaces; `BuildAirportsTests.swift` decodes
  the field; `test_qt_custom_patch.py` drives the Qt picker.

## 6. Lane plan

Order: L1 → (L2 ∥ L3) → L4. Each lane stops at replay/unit evidence (17r); the integration builds KASE
once. Never touch KEGE/KLXV results (same tile; KEGE certified): every lane reports their patch body
hash unchanged.

| Lane | Effort | Scope | Tests / evidence | Size |
|---|---|---|---|---|
| **L1 choice plumbing + (b)** | medium | `custom_patch_use` setting; `O4_Custom_Patches.use_of/uses`; route D3–D6, D9, D10, O1, O2 through it; the evidence record (coverage via v2's pavement loader, fit via `_pick_reference`); JSONL command, `custom_patches` + `BuildAirportsReady` fields, capability flag; Mac + Qt pickers; build-log lines | unit: `use_of` per mode and default; fixture tile with a custom patch → `select_patch_airports` generates for `auto_patch`/`blend`, `include_patches` loads `_auto` not the custom file, `auto_patch_not_applied` agrees, object stage places / restores per mode; `test_custom_patches.py`, `test_custom_patch_fit.py`, `test_build_airports.py`, `test_engine_capabilities.py`, `test_qt_layout_parity.py`, `test_qt_custom_patch.py`, `BuildAirportsTests.swift`; KASE evidence record computed offline = §2 numbers | ~600 + UI |
| **L2 (a) as made** | high | one sub-DEM exclusion list for an `as_made` airport whose reference is not the build DEM, honoured by `assemble_inset_composite_source` AND `bake_airport_insets_into_alt_dem` AND `O4_Elevation_Level.bake_approach_rings_into_alt_dem`; overlap cut with the existing feather; `mesh_path` returns the file unmodified | synthetic twin (base + inset + ring, one excluded → query and `.alt` both base inside, other inset untouched, G2 two-reader equality); KASE offline: the composite over the airport == `N39W107.hgt`; the §2.3 table's third row recomputed on the composite | ~300 |
| **L3 (c) blend** | high | `pack_patch_witness` reads a tile custom patch + ramp profiles (one profile function shared with `include_patches`); `solve/design_witness.py`; `[design] author_shape` in the law table; driver hands the witness path for `blend` airports; freshness key `o4_custom_witness`; report + log | `v2_solve_replay.py --replay KASE.pkl --from constraints` arms auto vs blend (weights 10/30/100): census law-true counts (grade-check skill) blend ≤ auto; witness residual inside rings; 0 m of step on pack pavement; band-on-pavement area 0; KEGE/KLXV body identical; unit: rows only within one ring, none across rings, none on grass faces | ~500 |
| **L4 retire 19b** (if Q2 yes) | low | delete `O4_Patch_Band`, the band/re-base write path in `O4_Patch_Rebase` (keep `_height_points`, `_pick_reference`, `_sources` for L1/L2), the `rebase_custom_patches` setting rows (Cfg_Vars, Settings_Model, SettingsLayout.swift), `O4_Bank_Annulus.patch_paths_read`'s copy branch; `test_patch_band.py`, `test_patch_rebase.py` trimmed; RULINGS note | `tools/ratchets.py` unused/dupes fall; `test_step_code_closure.py` | ~−600 |

**Integration build (once, KASE, `--tile 39 -107 --pack-copy`, on the merged code, mode = the default the
owner picks; the other two modes by replay only).** `drawn_gate.py KASE --tag <T> --against <the
integration's KASE control>` at:

* `KASE_APRON=39.22344,-106.86754,60` — main apron east of the runway at midfield (the band's largest
  piece on pavement; the uncovered apron's edge)
* `KASE_RAMP_N=39.22870,-106.86966,40` — patch ramp −58329 beside the pavement, ~470 m down RWY 15, 150 m east
* `KASE_PAD_N=39.22598,-106.86802,40` — pad −35728 edge, ~800 m down RWY 15, 150–177 m east
* `KASE_SEAM=39.21883,-106.86378,30` — re-base seam pad|ramp, ~1,675 m down RWY 15, 243 m east
* `KASE_APRON_S=39.21559,-106.86372,40` — 7,400 m² uncovered piece, ~2,015 m down RWY 15, 125 m east
* `KASE_PAD_W=39.22169,-106.87012,60` — the 7,190 m² pad over 4.8 m of lidar relief, ~1,190 m down, 160 m west

and KEGE / KLXV patch bodies unchanged in the same tile.

## 7. Questions for the owner

1. **Default.** Recommend **automatic by evidence**: "As made" when the patch covers its pack's pavement
   (≥ 98 %, no gap > 1,000 m²), else "Blend" — KASE → Blend. Alternatives: always "As made" (18k's
   spirit; KASE keeps its spots until the user picks) or always "Blend".
2. **Retire 19b's re-base + band** (and its Settings row) once (c) lands? Recommend **yes**: at KASE its
   band lies on ≈ 23,300 m² of apron and its re-base adds pavement seams; (c) does its job with complete
   coverage, and (a) covers "as authored". Its fit stays (it names the reference for (a) and the card).
3. **Objects under "Blend".** Recommend the pack's objects are **placed as for an auto-patched airport**
   (subject to the "Fit custom airport buildings" switch, 18l), since the ground is ours; 18k's
   "unmodified airport" stays for "As made".
4. **Wording and place.** Recommend a three-way picker on the Build card's airport row and in the tile
   info (replacing "Use auto patch"), labelled **"As made" / "Our auto patch" / "Blend"** with the help
   lines of §5.4.
