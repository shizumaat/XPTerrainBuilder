# Approach-graded elevation rings — specification (Fable, lane `rings164`, 2026-10-01)

**Issue:** #164. **Owner law:** RULINGS 2026-10-01g (the ruling, radii 10 km / 20 km
CONFIRMED, measured from the AERODROME BOUNDARY), 10-01d/e (holes fill down the
ladder; the KASE void map), 09-30ay/ax (the two-layer inset, las-tile spec §4/§12),
30bu/30bw (the ladder; global assembly), e9daef5 + the harness traps (one shared
corpus; every new artefact is an explicit `--refresh-data` scope; cold-cache
refusals; `frame.json` provenance), 2026-08-30l (consumer census BEFORE any
consumer is edited), 2026-07-18 build-time law (`Ortho4XP/CLAUDE.md` item 6).
**Status:** DRAFT for ratification. Nothing here is implemented; one Opus lane (§10)
implements it after ratification.

**The owner's words (10-01g):** "How big is the feather around airports that
transitions from 1m to the base level? I think we should try to broaden that a bit,
so we can do 1m at the airport, then 10m for surrounding say 10km, then 30m for 10k,
then the base dem for everything else." — and: the coastline level's
approach-visibility grading (`O4_Cfg_Vars.elevation_level` hint: 10 m within 20 km
of an airport, 20 m to 50 km, 30 m beyond) is THE RULE TO GENERALISE, not a parallel
one.

---

## §0 THE FACTS THIS SPEC DESIGNS AGAINST (measured this lane, read-only)

Today (`elevation_level=auto`): core = aerodrome boundary + 300 m at 1 m
(`core["footprint_buffer_m"]`, `assemble_two_layer_inset`); surround = the inset box
(boundary bounds + `airport_elevation_inset_margin_m` 2,000 m) at 10 m, feathered
`core_feather_m` = 60 m inside the core edge; the inset's OUTER edge feathers over
`airport_elevation_inset_feather_m` = 60 m into the tile's base DEM (`_bake_one_inset`
:14953) — at KASE the base is `N39W107.hgt`, 3 arc-second (VIEWFINDER3, ~92 m
posting). Beyond that box the mesh drapes on the 90 m base.

1. **The grade ring the owner sees is the 60 m feather hiding a 10 m-vs-90 m step at
   the inset box edge, 2 km from the boundary.** Measured on the cached
   `KASE_usgs3dep.tif` (5,320 × 7,118 cells at 0.998 m, 144.5 MB raw / 32 MB on disk)
   against `N39W107.hgt` bilinear, over the 0–60 m band inside the box edge
   (n = 400,000): inset − base median **+0.90 m**, p95 |Δ| **6.57 m**, max |Δ|
   **19.87 m**. Over the 60 m feather that is a worst transition grade of **33.1 %**
   (p95 **11.9 %**, median 2.5 %) — exactly the design surface's own bank
   (`emit.design.bank_slope` = 0.33, "an embankment / cut slope a pilot reads as
   ground, not a wall"), which is why a 60 m band of it, drawn as a rectangle around
   the airport, reads as a built edge. (The owner's "1.4 m median / 7 m max" is the
   lidar-vs-base figure over the CORE, 10-01e; the box edge sits in steeper ground.)
2. **A 10 m-vs-30 m step is small.** Proxy: the KASE surround area-averaged to 30 m
   and read back bilinear against its 10 m self, over the whole box (n = 377,492):
   median 0.000, p95 |Δ| **1.68 m**, p99 2.99 m, max **9.32 m** — in terrain whose
   10 m slope is median 19 % / p95 57 % (Aspen; a flat airport's figures are far
   smaller). 10 m-vs-90 m over the whole box: p95 7.46 m, p99 11.8 m, max 33.2 m —
   the bound for the 30 m → base transition at a mountain airport.
3. **Ring geometry at KASE** (boundary polygon from the sidecar, 1.30 × 3.11 km;
   inset box 5.31 × 7.11 km): ring 1 (boundary + 10 km) = 21.3 × 23.1 km = 492 km² =
   4.9 M cells at 10 m (19 MB float32) / 6.0 M cells at 1/3″ (23 MB); ring 2
   (boundary + 20 km) = 41.3 × 43.1 km = 1,781 km² = 2.0 M cells at 30 m (8 MB) / 2.4 M
   at 1″ (9 MB), of which the annulus is 1,288 km². KEGE and KLXV (same tile) are the
   same size class. The tile is 9,528 km²; a 1/3″ tile-wide raster is 116.7 M cells
   = 445 MB (the `elevation_level=10` cost the owner does not want to pay). Ring 1 at
   KASE is 5.2 % of the tile; the three airports' ring-1 union 1,019 km² = 10.7 %.
4. **What 10 m content costs the mesh.** The cached `Data+39-107.mesh` (app 1.0.367,
   1,348,571 vertices / 2,688,564 triangles, 282 tri/km² tile-wide, working grid
   11017² at 1/3″) binned by distance from the three boundaries: core (≤ 300 m)
   2,094 tri/km²; the inset-box margin (300–2,300 m, 10 m USGS content at KASE,
   1 m at KEGE) **759 tri/km²** (KASE 765, KEGE 1,014, KLXV 441); 2.3–10 km (90 m
   base) **280**; 10–20 km 286; beyond 268. So 10 m content densifies the mesh by
   ≈ **+480 tri/km²** over the 90 m base in this terrain, and the three ring-1
   annuli (1,019 km²) bound ring 1's cost at **≈ +0.49 M triangles (+18 %)**; ring 2
   (30 m over 2,444 km²) is bounded at roughly a third of that per km² — call it
   +0.2 M (+7 %). Tile step 2 (mesh) measured 55.7 s cold / 31.9 s warm on this tile.
5. **The working grid is already dense where rings land.** Any tile with a
   meter-class inset ballots to 1/2″ or 1/3″ (`resolve_working_grid_factor`; KASE
   1/3″ at worst ideal-bake error 0.808 m; Cairo 1/2″). Rings exist ONLY around
   inset airports (§1), so the grid they need is already paid for; a ring never
   votes.
6. **The machinery already exists twice.** The coastline band
   (`O4_Elevation_Level.ensure_coastline_band` :487) grades 0.1° cells by distance to
   the nearest airport BOX (20 / 50 km → 10.29 / 20 / 30.87 m warps of ONE wide-area
   provider), caches `cell_ii_jj_<code>_<res>m.tif`, mosaics them into a VRT and
   bakes through the strip bake `bake_tile_overlay_into_alt_dem` (:940) with a
   blurred-valid-mask hand-back of width `airport_elevation_inset_feather_m`. Its
   recorded limits (elevation-level spec §3.4): airports of neighbouring tiles are
   invisible; and — found this lane — a 10 m cell abutting a 20 m cell in the VRT is
   NOT feathered (the blur feathers data↔nodata only), the same class of step as (1)
   at a cell edge. The per-airport side has `assemble_two_layer_inset` (:2374) and,
   on `claude/holefill154` (670f8d21), `assemble_ladder_inset(core, fills)`.

---

## §1 THE DESIGN (owner-ruled; mechanism specified here)

Around every airport that HOLDS AN INSET on the tile (an entry of
`list_cached_inset_dems` with a boundary in the cached airports layer — the same
admission as the inset selection, `inset_keys(dico_airports, mode)`), measured
from the AERODROME BOUNDARY polygon (`airport_boundary_polygons`, NOT the ARP, NOT
the box):

| ring | extent (from the boundary) | class | posting | source |
|---|---|---|---|---|
| 0 | boundary + 300 m (the core) | 1 m | as today | the inset (unchanged) |
| inset box | boundary bounds + 2,000 m | 10 m surround / 1 m | as today | the inset (unchanged) |
| 1 | out to **10 km** | 10 m | `grid_posting_metres(3)` = 10.29 m | finest wide-area provider with native ≤ 10 m (§2) |
| 2 | out to **20 km** | 30 m (1″) | `grid_posting_metres(1)` = 30.87 m | the same provider at 1″ (§2) |
| beyond | — | base | — | the tile's base DEM |

Transitions, outer edge of the finer layer, feathered INSIDE the finer layer:

| transition | feather | law constant | worst grade at KASE (fact 1–2) |
|---|---|---|---|
| 1 m core → 10 m surround | 60 m (`core_feather_m`, unchanged) | — | as today |
| inset (box edge) → ring 1 | 60 m (`airport_elevation_inset_feather_m`, unchanged) | — | ≈ 0: the surround and ring 1 are THE SAME 10 m product (resampling residual only); for a 1 m-only inset (KEGE) it is the 1 m-vs-10 m step, measured by the lane |
| ring 1 → ring 2 | **F1 = 300 m** (10 postings of the coarser class, `APPROACH_RING_FEATHER_POSTINGS = 10` × 30.87 m, rounded) | `emit.design.bank_slope` 0.33 is the ceiling; `ruleset.taxi.transverse` 0.015 the p95 target | max 9.3 / 300 = **3.1 %**, p95 **0.56 %** |
| ring 2 → base | **F2 = 900 m** (10 × 92.6 m, the 3″ posting) | same | bound max 33 / 900 = **3.7 %**, p95 **0.83 %** |

The rule behind the two constants: the 60 m feather was sized for the 1 m → 10 m
seam (6 postings of the coarser class) and was then reused at a 10 m → 90 m seam
where it is 0.65 of one posting — that is the defect. A feather is a number of
postings of the COARSER side, never a fixed metre count. Both new feathers leave
every measured transition an order of magnitude under the bank and the p95 under
the taxiway transverse cap; both are ≪ the ring widths (ring 1 annulus ≥ 7.7 km,
ring 2 10 km). Where ring 1 collapses into ring 2 (§2), the inset's 60 m feather
meets a 30 m ring: this is the non-US case only (the two-layer 10 m surround exists
only on the USGS ladder), and a 1 m → 30 m seam over 60 m is what a plain inset
over the 1″ base already is today under `elevation_level=30`.

---

## §2 SOURCES PER RING — through the existing registry, never a second one

* **Ring 1** = `select_tile_overlay_definition(lat, lon, 10, providers_config)`
  (`O4_Elevation_Level` :165) restricted to candidates whose
  `_definition_resolution_m` ≤ 10 m — i.e. `_wide_area_candidate_definitions` (:202)
  with one added filter, finest-first, then priority. In the US that is USGS3DEP
  (`tnm_cog`, the 1/3″ product through its ladder's own discovery — the coastline
  band's exact path); in Europe the national WCS/STAC services that declare
  `supports_wide_area` (SPAIN5M, ITALY10M, NORWAY1M, POLAND1M, SWEDEN1M, FINLAND2M,
  ENGLAND1M, NETHERLANDS50CM, DENMARK40CM, …), warped at 10.29 m through COG
  overviews / WCS resolution. A sub-metre lidar service is read at 10.29 m, never at
  native (the band's rule; `_inset_target_resolution_m`'s "never finer than native"
  is moot here).
* **Ring 2** = the SAME definition at 30.87 m when it covers the cell (one product,
  one datum, one vintage across the 10 m → 30 m seam — the measured 1.7 m p95 step is
  pure resolution; a second product would add datum and vintage to it). When the
  ring-1 provider does not cover a ring-2 cell, the finest wide-area definition with
  native ≤ 30 m that does. Today NO such definition exists outside the ≤ 10 m set:
  `COPERNICUSGLO30.elv` is `degree_named_cog`, which declares
  `supports_wide_area = False` deliberately (a SURFACE model whose rooftops are
  corrected only by the airport-scoped footprint mask) — **INTENT Q1 (§9)**. Until
  ruled: ring 2 exists only where a ≤ 10 m wide-area provider covers it.
* **Collapse rule.** No ≤ 10 m wide-area provider over a ring-1 cell → the cell is
  fetched at the ring-2 class from the ring-2 provider (ring 1 collapses into
  ring 2). No ring-2 provider either → the cell is `no-coverage` (cached negative,
  as the band does) and the base DEM stands; the plan records it. A tile with no
  inset airport has NO ring plan (byte-identical to today).
* **THE RUNG (owner RULINGS 2026-10-02f, amending this section's letter).**
  "Through its ladder's own discovery" above was read as `fetch_inset(definition,
  ...)` with no ladder, which takes RUNG 0 — for USGS3DEP the 1 m PROJECTS
  resampled to the class, which carry the #130 Aspen hole (KASE's ring-1 cells
  read 0.0003–0.99 valid; the bake handed the holes back to the 90 m base).
  RULED: a ring cell is fetched from the provider's ladder rung whose native
  resolution is at most the ring's class — the COARSEST such rung, among the
  rungs that can be a surround (`_rung_can_be_surround`: never a point-cloud
  tile index, never an AOI polygon POST, never a rung judged by airport cover).
  USGS3DEP ring 1 = the `10|1/3 arc-second` rung; ring 2 = the same product at
  30.87 m, which is this section's "one product, one datum, one vintage".
  ONE derivation site (`O4_Elevation_Level.surround_rung_for_class`), shared
  with the coastline band, which took the same defect through the same call.
* **Per-cell discovery negatives** live in the ring directory's `index.json`
  exactly as the band's stamp does (`_read_coastline_band_stamp`); the once-per-
  engine-version re-probe door (RULINGS 2026-09-15aq (4)) applies to them through
  the same predicate family — a ring negative is a capability-free negative.

---

## §3 WHERE THE RINGS LIVE — RULED: ONE TILE-WIDE DISTANCE-GRADED OVERLAY

**Ruled:** rings are the COASTLINE BAND MECHANISM generalised — per-tile 0.1° cells
graded by distance to the nearest aerodrome boundary, cached per cell, assembled
per CLASS, baked coarsest-first through the strip bake as base terrain — NOT a
per-airport N-layer raster through `assemble_ladder_inset`.

Reasons, in order of weight:

1. **Union by construction.** A cell's class is decided by the distance to the
   NEAREST boundary of any airport on the tile (or a neighbour's, §5). Two airports
   50 km apart (KASE/KEGE) have overlapping ring-2 boxes and nearly touching ring-1
   boxes; per-airport rasters baked one after the other would feather airport A's
   ring-2 OUTER edge (30 m → base over 900 m) INSIDE airport B's ring 1 — a 900 m
   dip to the 90 m base cut through 10 m ground. A union pass would be needed
   anyway; the distance-graded overlay IS that pass.
2. **Memory and bytes.** A per-airport 40 km box at 10 m is 17.8 M cells = 71 MB
   float32 (the owner's figure), ×3 on this tile, mostly duplicating each other and
   the base; the cell plan holds only the cells a ring needs, each at its own class,
   and the strip bake (`STRIP_CELL_BUDGET` 4 M cells + halo) never holds more than
   one strip. The per-airport inset stays what it is — a 1 m raster over the 5 × 7 km
   box — so the holefill154 assembler keeps ONE job (holes in the core) and the
   inset's bytes do not grow ×10.
3. **The solve's production DEM is untouched where it matters.** The inset bakes
   LAST (`smooth_raster_over_airports` → `bake_airport_insets_into_alt_dem`) with
   weight 1 everywhere beyond 60 m inside its own edge: the baked surface over the
   inset box, minus its outer 60 m band, is BYTE-IDENTICAL whatever lies beneath.
   Rings change nothing the solve reads except that 60 m band at the box edge, 2 km
   from the boundary (§8 (5) makes the lane prove it on the control captures).
4. **One mechanism, not two.** The band already does cells, grading, caching,
   negatives, VRT mosaic, strip bake and the grid-factor stamp; the generalisation
   is a ladder table and a layer loop, and it FIXES the band's own unfeathered
   cell-edge step (fact 6) for free.
5. **Neighbour tiles compose.** Each tile bakes its own plan; at a tile seam both
   sides read the same cells (a cell is keyed by its degree indices, provider and
   resolution; a neighbour's plan that needs the same cell reuses the file) and
   the strip bake's tile-edge ramp returns both to the shared base at the border —
   today's overlay continuity rule, unchanged.

What is rejected and why: the per-airport N-layer raster (double bake, 71 MB per
airport, a second union pass, and it would put ring data INSIDE the file the
re-cut rule, the ARP sanity read, the witness and the census all judge as "the
inset"); a tile-wide 1/3″ raster (445 MB, the `elevation_level=10` cost).

### §3.1 The plan (one derivation site, disk-state driven)

`O4_Elevation_Level.resolve_approach_ring_plan(tile, dico_airports)` — the ring
analogue of `resolve_coastline_band_plan`, pure and offline:

* **Airports:** every string-keyed airport of `dico_airports` admitted by the inset
  mode (`inset_keys`) whose inset exists on disk (`cached_inset_paths_for_icao`),
  PLUS (§5) the admitted airports of each 8-neighbour tile whose cached airports
  layer exists (`FNAMES.osm_cached(lat±1, lon±1, "airports")`, parsed through
  `build_airports_dico` on a throwaway `Tile`), whose boundary lies within 20 km of
  this tile. A neighbour with no cached layer contributes nothing and is recorded
  as `neighbours_unknown` — never a refusal (the coastline spec's recorded limit,
  now closed where the data is there).
* **Distance field:** the boundary polygons (EPSG:4326, moved by the tile origin)
  buffered in metres (`_buffer_geometry_m`) by 10 km and 20 km; `R1` = the union of
  the 10 km buffers, `R2` = the union of the 20 km buffers. Measured from the
  BOUNDARY, as ruled.
* **Cells:** the tile's 10 × 10 grid of 0.1° cells (`COASTLINE_CELL_DEGREES`). A
  cell intersecting `R1` is a ring-1 cell (fetched at the ring-1 class); a cell
  intersecting `R2` but not `R1` is a ring-2 cell; others are not in the plan. A
  cell is fetched at the FINEST class any part of it needs; the exact ring edge is
  the bake's business (§3.2), not the fetch's. Over-delivery (10 m data in the
  ring-2 part of a ring-1 cell) costs no second fetch and no memory.
* **Classes:** `APPROACH_RING_LADDER = ((10_000.0, 3), (20_000.0, 1))` — (reach in
  metres from the boundary, grid factor whose posting is the warp target). The
  coastline band's own table becomes `COASTLINE_APPROACH_LADDER = ((20_000, 3),
  (50_000, 20.0 m), (inf, 1))`, UNCHANGED in values; ONE grading function
  `approach_class(distance_m, ladder)` serves both (the generalisation the owner
  asked for; **INTENT Q2** asks whether the band should adopt the ring radii).
* **Output:** `{"cells": [{column, row, class_m, reach_ring, provider, path,
  stem}], "layers": {10.29: [...], 30.87: [...]}, "regions": {"R1": wkt, "R2": wkt},
  "airports": [...], "neighbours_unknown": [...], "feathers": {"ring1_m": 300,
  "ring2_m": 900}}`, stamped to `<ring dir>/index.json` (plan + per-cell outcomes,
  rewritten only on change — the band's `_write_coastline_band_stamp` discipline;
  a byte-identical stamp is never rewritten, e9daef5).

### §3.2 The bake — the strip bake, per class layer, coarsest first

`bake_tile_overlay_into_alt_dem(tile)` (:940) is refactored into
`bake_overlay_layer_into_alt_dem(tile, overlay_path, *, feather_m, region=None,
label)` (the body as it is) plus the existing caller for the numeric-level overlay
(feather `airport_elevation_inset_feather_m`, no region — byte-identical). Rings call
it from a new `bake_approach_rings_into_alt_dem(tile)` placed in
`compose_tile_dem_from_disk` (`O4_Vector_Map` :2070) immediately AFTER the
numeric-level overlay bake and BEFORE `smooth_raster_over_airports` (rings are base
terrain: smoothed like base, the insets bake last over them):

1. ring-2 layer: the VRT of the plan's 30.87 m cells (`gdal.BuildVRT`, the band's
   `band_<code>.vrt` convention, written to the tile's tmp dir — a DERIVED file,
   never the shared repo), `region = R2`, `feather_m = 900`;
2. ring-1 layer: the VRT of the 10.29 m cells, `region = R1`, `feather_m = 300`;
3. (coastline mode only) the band's layers, one per class, in the same loop.

`region` enters the strip's validity mask: per strip (with its halo) the region
polygon is rasterised (`gdal.RasterizeLayer` on a MEM raster of the strip's
working-grid cells) and ANDed with the overlay's data validity; the existing
blurred-mask hand-back (`_box_blur_mask`, `clip(2·blur − 1, 0, 1)`) then ramps the
layer to whatever is already in `alt_dem` over `feather_cells = ceil(feather_m /
posting)` inside the region edge. No new feather implementation: the overlay bake's
own, parameterised. The halo grows to `feather_cells` (ring 2: 900 / 10.3 = 88 rows
each side of a 363-row strip at 1/3″) — bounded, separable cumsum, cheap.

Resampling: bilinear, as the strip bake is today (a 10.29 m layer on a 1/3″ grid is
a near-identity read; on a 1/2″ grid — the Cairo class — it is a mild subsample;
accepted and recorded, §9 STOP 6).

Provenance: `tile.dem.approach_ring_provenance = {"layers": [{class_m, provider,
cells, region_km2, feather_m}], "plan_stamp": sha}`; `dem_production._bake` carries
it to the frame as `rings:<stem>` beside `tile:<stem>`; `auto_patch.provenance`'s
stamp gains `rings=10m:<provider>:<n cells>,30m:<provider>:<n>` (additive field;
one decoder).

---

## §4 THE INSET BOX — RULED: UNCHANGED

`airport_elevation_inset_margin_m` stays 2,000 m and the inset box stays the solve's
production-DEM box. Reasons: (a) the margin is the SOLVE's reach ("the clearance
band and custom object neighbourhoods extend well past the boundary" — the hint),
not an approach-visibility radius; (b) the margin is in the inset completion key
(`_inset_completion_key`) and the re-cut rule (`inset_recut_is_needed`: required box
not contained in the requested box) — changing it re-cuts EVERY cached inset
(565 rasters on the corpus) and turns every warm tile cold; (c) a 20 km inset is
the 71 MB-per-airport raster §3 rejects. `dem_production._required_inset_box` is
untouched (census row 7).

---

## §5 DOWNLOAD + CORPUS

* **Artefacts** (new directory, the band's layout): `Elevation_data/<block>/
  <stem>_approach_rings/cell_<ii>_<jj>_<code>_<rung>_<res>m.tif` (+ `.json`
  provenance sidecar per cell, the `fetch_inset` provenance + `fetch_date` +
  `ring_rung`), `index.json` (plan stamp + per-cell outcomes + negatives).
  Cells are fetched through `INSETS.fetch_inset(RUNG_definition, cell_box,
  target_resolution_m, path)` — the band's one call per missing cell
  (`ensure_coastline_band` :487), reused, through the rung §2 names (owner
  RULINGS 2026-10-02f: the rung is part of the stem and of the plan stamp, so a
  cell fetched under the old no-ladder rule is simply not the planned file —
  COLD, and `--refresh-data rings` re-fetches it). A cell whose file already
  exists in the tile's `_coastline_band` directory with the same stem — the
  rung included — is REUSED by reference (never copied): one cell cache, two
  plans, one rung per class.
* **Bytes.** A 0.1° cell at 10.29 m is ≈ 0.95 M cells = 3.8 MB raw (deflate ≈ 40 %
  on smooth 10 m ground; the 1 m lidar compresses to 22 %); at 30.87 m 0.1 M cells
  = 0.4 MB. KASE needs ≈ 9 ring-1 cells + ≈ 16 ring-2 cells ≈ 40 MB raw / ≈ 16 MB on
  disk; the three-airport tile ≈ 60 MB raw (overlapping cells counted once). Per
  airport the band-class download is ≈ 25 cell GETs at the TNM/COG overview level
  (seconds each), against the 7 GB LAS precedent (30ay) — surgical by construction.
* **Scope:** a NEW `--refresh-data` scope **`rings`**, listed BEFORE `dem` in
  `REFRESH_SCOPES`, matched by DIRECTORY SUFFIX (`scope_of` gains a directory-suffix
  table beside `SUFFIX_SCOPES`: a relpath whose second component ends in
  `_approach_rings` is `rings`). `dem` alone does NOT warm rings (a session that
  warms `dem` today must stay byte-identical in effect); `--refresh-data rings`
  derives the plan from the cached airports layer (cold layer → refuses naming
  `osm_layers`, the KDFW precedent) and fetches every missing cell under the
  per-scope lock, hash-stamped in `refresh_ledger.jsonl`.
* **Cold-cache rule.** The harness frame check (`build_airport.py` beside
  `this_airports_inset_problem`) derives the plan offline and REFUSES when any
  planned cell is UNANSWERED (no raster, no negative), naming
  `--refresh-data rings`; `--allow-degraded-dem` proceeds WITHOUT rings (the engine
  bakes only the cells on disk; a missing cell is a hole the base fills, as the
  band does) and records it. Production (`dem_production.frame_state`) reads the
  same predicate (`INSETS`-style one derivation site:
  `O4_Elevation_Level.approach_ring_frame_problem(lat, lon, plan)`) and reports it
  on the provenance; the APP fetches the missing cells in its own step-1 pass
  (`ensure_approach_rings(tile, dico_airports)`, beside `ensure_tile_overlay`).
* **`frame.json` rows:** `approach_rings: {planned, on_disk, missing, negatives,
  providers, layers, neighbours_unknown, stamp}` (its own key, like
  `ladder_recheck`), and `dem_inset_provenance["rings:<stem>"]`.
* **The corpus stamp.** `dem_cache_state`'s key set is FROZEN (adding a key re-keys
  every stored arm). RULED: the ring state does NOT enter `dem_cache_state`; the
  ledger's `corpus_stamp` (`artifact_ledger.py` :182) gains ONE new `parts`
  component `rings_dir` = the `<stem>_approach_rings` directory listing
  (name, size, mtime_ns — the inset-dir idiom). This re-keys every stored arm ONCE
  (the merge sweep rebuilds controls at app-build time anyway; the alternative —
  leaving rings out of the stamp — would serve a pre-rings control for a post-rings
  build, the silent cross-corpus comparison the stamp exists to prevent).
* **Re-check reach: NEVER.** The ladder re-check (30aw (2)) exists because a FINER
  rung may list later; a ring cell is a fixed class from a seamless wide-area
  product. A changed provider set changes the plan's stem → the old cell is simply
  not the planned file → COLD → `--refresh-data rings`. A per-cell negative is
  re-asked once per engine version (15aq (4)) under that scope, never in a build.
* **Build-time pollution flag:** a step-1 pass that fetched ring cells sets
  `features.rings_fetched` on the tile build record; `check_build_time.py` treats
  it exactly as `insets_fetched` (a download-polluted run is no baseline).

---

## §6 CONSUMER CENSUS (RULINGS 2026-08-30l) — every pass that reads the affected region, ONE table

Region = the working grid between the inset box edge and 20 km from any boundary,
plus the inset's outer 60 m band. Grepped: `alt_dem`, `bake_`, `_airport_bounding_boxes`,
`list_cached_inset_dems`, `tile_overlay`, `coastline_band`, `inset_provenance`,
`dem_cache_state`, `corpus_stamp`, `summarize_tile_elevation_sources`, `elevation_gap_census`,
`--witness`, `insets_fetched`.

| # | consumer (file:symbol) | reads | interaction | ruling |
|---|---|---|---|---|
| 1 | `O4_Elevation_Level.ensure_approach_rings` (NEW, step-1 download hook beside `ensure_tile_overlay`) | plan + cells | fetches missing cells (the band's loop) | app: fetches; harness: never (refuses cold, §5) |
| 2 | `O4_Elevation_Level.resolve_approach_ring_plan` (NEW) | airports layers (own + cached neighbours), inset dir, registry | THE ONE derivation of cells/classes/regions | pure, offline, stamped; both build steps re-derive from disk |
| 3 | `O4_Vector_Map.compose_tile_dem_from_disk` :2070 | the bake ORDER | ring bake inserted after the numeric overlay bake, before airport smoothing | rings are base terrain; insets still bake last |
| 4 | `O4_Elevation_Level.bake_tile_overlay_into_alt_dem` :940 | overlay path, feather | refactored to `bake_overlay_layer_into_alt_dem(path, feather_m, region)`; the level caller unchanged | twin: level overlay byte-identical |
| 5 | `O4_Elevation_Level.ensure_coastline_band` / `resolve_coastline_band_plan` :487/:842 | cells, ladder | ladder table lifted into `approach_class(distance, ladder)`; its bake becomes per-class layers through row 4 (fixes its own cell-edge step) | values unchanged (Q2) |
| 6 | `O4_Airport_Utils.smooth_raster_over_airports` | `alt_dem` over airport masks; radius from INSET extents | rings lie under the smoothing like base terrain; the radius decision reads insets only | unchanged |
| 7 | `auto_patch_v2.airport.dem_production._required_inset_box` / `frame_state` / `_bake` | inset box; frame; provenance | box UNCHANGED (§4); `frame_state` gains the ring predicate (reports, degrades only when the app would have baked rings this build did not — i.e. same as the harness cold rule); `_bake` carries `rings:<stem>` | one derivation site shared with the harness |
| 8 | the v2 solve (production DEM reads: §21 trend, zones, pads, road eases, flat-site detector) | `alt_dem` inside the inset box | byte-identical beyond the box's outer 60 m band (row 3 + inset weight 1); the band changes from blend-with-base to blend-with-ring-1 | §8 (5): control captures byte-identical; a mover there is a STOP |
| 9 | `INSETS.bake_airport_insets_into_alt_dem` / `_bake_one_inset` :14818/:14953 | `alt_dem` under the inset | now blends against ring 1 (same product) in its 60 m band; `ring_offset_m` datum warning now measures inset-vs-ring-1 (smaller) | unchanged code; the provider-systematic-offset warning reads a different (better) comparator — noted |
| 10 | `INSETS.resolve_working_grid_factor` / `densify_tile_dem_for_insets` :16923 | cached INSET list | rings are not insets (own directory, not `*.tif` in `_airport_insets`) → never on the ballot | rings never vote (fact 5) |
| 11 | `INSETS.assemble_inset_composite_source` + `DEM.alt_composite` / `enable_baked_query` | the query path | the composite lists insets only; the baked query reads the baked grid → ring values are what any post-bake DEM read outside the box returns | one surface, two readers — intended |
| 12 | `O4_Mesh_Utils.build_curv_tol_weight_map` :463 + Triangle4XP curvature | the `.alt` raster | more relief detail in rings → more triangles (fact 4 bound) | §8 (6) bounds it; no weight-map change |
| 13 | `O4_Mask_Utils` / `O4_Bathymetry_Band` | masks; seabed band (water only) | the bathymetry band bakes water cells; rings bake land cells of the same tile — disjoint by the water mask; the COASTLINE BAND overlaps ring 1 at coastal airports | row 5: one cell cache, class-by-class layers, finest wins per cell |
| 14 | `tools/harness/build_airport.py` frame check (`require_dem_frame`, `dem_cache_state`, `this_airports_inset_problem`) | cache warmth | NEW `approach_rings` frame key (§5); `dem_cache_state` keys FROZEN, untouched; refusal names `--refresh-data rings` | `--allow-degraded-dem` covers it, authorises no write |
| 15 | `tools/harness/artifact_ledger.corpus_stamp` :182 | `dem_cache_before`, inset dir listings | NEW `rings_dir` part | one-time re-key (§5) |
| 16 | `tools/harness/shared_repo_guard.REFRESH_SCOPES` / `scope_of` | write paths | NEW `rings` scope by directory suffix, before `dem` | twin: `scope_of("Elevation_data/+30-110/N39W107_approach_rings/x.tif") == "rings"` |
| 17 | `tools/harness/census.py` header (`patch_provenance`) | the patch's provenance stamp | prints the new `rings=` field | additive |
| 18 | `O4_Qt_GUI` tile info (`summarize_tile_elevation_sources` :18119) and `O4_Qt_Settings`; Swift `SettingsLayout.swift` :101-106 | registry + indexes; cfg schema | one new line "approach rings: 10 m to 10 km (CODE), 30 m to 20 km" from the plan stamp when present, else "not fetched"; the new cfg key (§7) gets one `SettingItem` row in each UI | engine owns the feature, UIs expose (standing) |
| 19 | `tools/fetch_airport_elevation_insets.py --witness` | per-airport inset | prints the airport's ring plan rows (cells, class, provider, on-disk) — read-only | extended, not forked |
| 20 | `tools/elevation_gap_census.py`, `tools/inset_coverage_census.py` | 1 m holders; inset rasters | no ring reads | unchanged |
| 21 | `tools/check_build_time.py` | `features.insets_fetched` | + `features.rings_fetched` | §5 |
| 22 | `O4_Vector_Map.ensure_tile_frame` (neighbour warm, §D.1) | neighbour's step-1 fetch half | ALSO runs `ensure_approach_rings` for the neighbour under its own mode (a class-S neighbour's rings reach into this tile) | same hook, same mode |
| 23 | seam / neighbour tiles (`_seam_neighbour_tiles`, factor harmonisation) | inset footprints across seams | rings do not take part in the factor ballot; at a seam both tiles bake the same cells and ramp to the shared base over the tile-edge feather (today's overlay rule) | continuity kept; the 60 m seam dip to base is the existing overlay behaviour, recorded |

Single derivation sites, per 30l (a): the plan (row 2), the class function (row 5),
the layer bake (row 4), the frame predicate (rows 7/14). No per-consumer veto.

---

## §7 INTERACTION WITH `elevation_level` ≠ auto — precedence

Per cell, the FINEST class wins; a ring layer is baked only where it is finer
than what the level already delivers ("levels never coarsen what auto would have
chosen", and rings never coarsen a level):

| `elevation_level` | tile-wide overlay | ring 1 (10 m) | ring 2 (30 m) |
|---|---|---|---|
| `auto`, `90` | none | baked | baked |
| `coastline` | the band's cells (coastal) | baked; coastal cells take max(band class, ring class) | same |
| `30` | 1″ tile-wide (factor 1 from the level; the inset ballot may raise it) | baked (finer than the overlay) | SUPERSEDED (the overlay already is 30 m) — plan records `superseded` |
| `10`, `5`, `1` | ≤ 10 m tile-wide | SUPERSEDED | SUPERSEDED |
| `custom_dem` set | none (the level only densifies) | not fetched, not baked (the user's raster is authoritative, as for the band) | same |

One cfg key, engine-owned, APP-level like `elevation_level`:
`approach_rings` ∈ {`auto`, `off`} (default `auto`; `off` = today's behaviour,
byte-identical, the gate the sim read adjudicates — BUILD ECONOMY: gates only for a
mechanism awaiting the owner's sim adjudication, removed once adjudicated). Radii
and feathers are constants, not keys (the owner ruled them; a user knob here is a
second ladder). `DEM_FRAME_KEYS` gains `approach_rings` so the harness frame check
sees a divergence.

---

## §8 ACCEPTANCE

1. **KASE, the grade ring:** on the assembled working grid (the `.alt` the lane's
   closing build writes, or the in-memory `alt_dem` of a `compose_tile_dem_from_disk`
   probe), the worst and p95 slope across a 1 km-wide band centred on the inset box
   edge, BEFORE (fact 1: 33.1 % / 11.9 % implied; the lane measures the actual
   baked band) and AFTER: after ≤ the terrain's own p95 slope in the same band
   ± 1 pp (the ring is gone when the band's slope distribution is that of its
   surroundings). Report the three transitions' worst / p95 grades (box edge,
   10 km, 20 km) against the §1 table.
2. **Approach relief at 10 km from 10 m:** a probe on the RW15 extended centreline
   9 km from the threshold (the Roaring Fork valley floor): the baked value equals
   the 10.29 m cell's bilinear value within 0.05 m, not the 90 m base's; and the
   same probe at 15 km reads the 30.87 m cell's.
3. **Transitions below the bank:** every transition's worst grade < `emit.design.
   bank_slope` (0.33) and p95 < `ruleset.taxi.transverse` (0.015) on the KASE tile
   (expected 3.7 % / 0.83 % worst case, §1).
4. **Plan correctness (synthetic twin):** a fake tile with three boundary polygons
   (one 8 km from a neighbour-tile boundary, one coastal), providers mocked at
   1 m/10 m/30 m/none: cells graded by boundary distance (not box, not ARP),
   neighbour airport included when its layer is cached and recorded as unknown when
   not, collapse into ring 2 where no ≤ 10 m provider, `superseded` under level 10,
   coastline cells take the finer class.
5. **Airside untouched (controls):** HECA / KCLT / SPJC / CYXY / KASE
   `v2_solve_replay` captures taken on the shared corpus WITH rings warm, replayed
   `--from load … --emit --verify`: patch bodies byte-identical to the registered
   pre-rings captures (opr153/sw1003 hashes: HECA e23751e99ea8, KCLT 75d1a4fe9846,
   SPJC 95c56d57e2fd, CYXY 821367a36da2, KASE 8af25eb69b0a); zero movers at
   `--tol 0.02`. ANY mover is a STOP: it means the solve read the box's outer 60 m
   band (row 8), and the owner rules, never the lane.
6. **Mesh and build time, bounded:** KASE tile (+39-107) closing build: triangles
   ≤ +30 % of 2,688,564 (fact 4 bound +25 %); step-2 wall per `check_build_time.py
   --runs 3` reported with the delta; the ring bake itself ≤ 3 s per tile. The
   increase is ≥ 1 % of the 300 s tile budget → the brief's BUILD-TIME IMPACT
   STATEMENT is mandatory and the number goes to the final-design profiling round
   (the per-change gate is suspended, 2026-08-04; the law is not).
7. **Corpus-clean:** the closing build's `frame.json` shows `shared_repo_writes`
   empty and `contaminated: false`; rings warmed only by the session's
   `--refresh-data rings` event, recorded in the refresh ledger.
8. **Twins, one per mechanism:** `tests/test_approach_rings.py` (plan, class
   function with both ladders, collapse, supersede, neighbour inclusion, cold
   predicate, scope mapping, `rings_fetched` flag), extension of
   `test_elevation_level.py` (layer bake with `region` + feather; level overlay
   byte-identical), of `test_elevation_coastline.py` (the band through the shared
   class function and per-class layers, cell-edge feathered), of `test_harness.py`
   (frame key, corpus-stamp part, refusal wording), of `test_fetch_inset_witness.py`
   (ring rows). A twin that fetches is a defect (network is blocked in the suite).

---

## §9 STOP LIST (and INTENT questions for the owner)

STOP — the lane does not:

1. change the inset box, `airport_elevation_inset_margin_m`, the core buffer, the
   core feather or the inset bake (§4; rows 7–9 unchanged);
2. put ring data inside an inset raster or its sidecar, or into
   `_airport_insets/` (the re-cut rule, the ARP sanity read, the witness and the
   census judge that file);
3. add a key to `dem_cache_state` (frozen) — the ring state rides its own frame key
   and the corpus-stamp part (§5);
4. write any derived file (VRT, scratch, plan) into the shared repo as a build side
   effect — VRTs live in the tile's tmp dir; the stamp is rewritten only on change;
5. fetch in the harness, or re-check rings at build time (§5: never);
6. add a resampler to the strip bake (bilinear stays; the 1/2″-grid subsample is
   recorded, not fixed);
7. expose radii, feathers or classes as cfg keys (one key, `approach_rings`
   auto/off);
8. make Copernicus GLO-30 wide-area, or any provider's `supports_wide_area` change,
   without Q1's answer;
9. touch the coastline band's radii (Q2) or its cache directory;
10. run the five-airport sweep, or more than ONE real build (KASE, closing).

INTENT questions (mechanisms were measured; these are intent):

* **Q1 — ring 2 outside wide-area lidar coverage.** Outside the US and the European
  WCS/STAC services no `supports_wide_area` provider ≤ 30 m exists: HECA, OTHH, VHHH,
  LEMD(?) get NO rings and keep the 90 m base to the box edge. Copernicus GLO-30 is
  the obvious 30 m source but is a SURFACE model (rooftops, canopy) and was
  deliberately barred from tile-wide use. May it serve ring 2 ONLY (never ring 1),
  under a per-definition opt-in (`approach_ring_class=30`), accepting rooftop
  heights at 30 m posting 2–20 km from the airport — the same class of artefact the
  SRTM-derived 90 m base already carries there? Recommendation: yes, as a follow-up
  lane after KASE, measured on HECA.
* **Q2 — one ladder table or two.** The coastline band keeps 10 m to 20 km / 20 m to
  50 km / 30 m beyond (its users' current behaviour); rings are 10 m to 10 km / 30 m
  to 20 km (ruled). Should the band adopt the ring radii so there is ONE table
  (coastal cells 10–20 km from an airport then read 30 m instead of 10 m; 20–50 km
  30 m instead of 20 m)? Recommendation: keep both tables, one function, until a
  coastline-mode sim read.
* **Q3 — default ON at merge.** `approach_rings=auto` by default means every build of
  an inset tile needs warm rings (the app fetches them; the harness refuses cold
  until the session warms the five control tiles under `--refresh-data rings`).
  Confirm default ON after the KASE sim read, or ship `off` until then.

---

## §10 LANE PLAN — ONE Opus lane, cap 2, synthetic-first

**Lane `rings164impl`** (Opus, moderate effort; branch `claude/rings164impl` from
main after this spec is ratified; worktree via `lane_worktree.sh up`). Attempt cap 2
per pre-registered target; materiality floor 0.01 m (elevation) / 0.01 pp (grade);
`.progress` heartbeat.

Order of work (each step lands with its twin before the next):

1. **The class function and the plan** (`O4_Elevation_Level`): `approach_class`,
   `APPROACH_RING_LADDER`, `COASTLINE_APPROACH_LADDER` (the band rewired to it, values
   unchanged), `resolve_approach_ring_plan` with neighbour-tile airports, the stamp
   (`FNAMES.approach_ring_directory/_index/_cell_dem`), `approach_ring_frame_problem`.
   Twin §8 (4) on a FAKE 3-ring fixture (`tmp_path` tile, three synthetic boundary
   polygons, mocked registry) — no network, no corpus.
2. **The layer bake**: `bake_overlay_layer_into_alt_dem(path, feather_m, region)`
   refactor (level overlay byte-identical twin), `bake_approach_rings_into_alt_dem`
   in `compose_tile_dem_from_disk`, the band baked per class through it. Synthetic
   twin: a 300 × 300 working grid, a 10 m layer with a step of 9.3 m against a 30 m
   layer, region = a disc: worst grade across the 300 m feather = 3.1 % ± 0.1,
   values inside the disc beyond the feather equal the 10 m layer exactly, the
   coarse-first order verified by a cell straddling both regions.
3. **Fetch + corpus**: `ensure_approach_rings` (the band's loop over the plan's
   cells, band-cell reuse by stem), `features.rings_fetched`, the `rings` scope +
   `scope_of` suffix table, the harness frame key + refusal + `--refresh-data rings`
   derivation, the corpus-stamp part, `frame.json` rows, provenance `rings=`,
   census header, `--witness` rows, Qt/Swift one row each + the `approach_rings`
   cfg key in `O4_Cfg_Vars` (`list_app_vars`, schema) and `DEM_FRAME_KEYS`. Twins in
   `test_harness.py` / `test_approach_rings.py`.
4. **Offline replay evidence (before any build):** on a LANE-LOCAL `Elevation_data`
   overlay (the las130 pattern: `FNAMES.Elevation_dir` re-pointed; cells fetched
   lane-locally for +39-107 only), `compose_tile_dem_from_disk` for +39-107 → §8 (1)
   (2) (3) measured on `alt_dem`; the five control captures replayed §8 (5).
5. **The session's event:** the session (not the lane) warms the shared corpus:
   `build_airport.py KASE --tile 39 -107 --refresh-only --refresh-data rings` and
   the same for the four control tiles (one locked, ledgered act each; ≈ 16 MB per
   airport on disk).
6. **Closing test — ONE build:** `build_airport.py KASE --tile 39 -107` on the
   shared corpus; report §8 (1)–(3), (6), (7); `check_build_time.py --runs 3` for
   step 2 (foreground, `unsetopt bg_nice`); register the closing products with
   `frames.py register --kind mesh|patch`.
7. **Report:** site numbers first (the three transition grades, the 10 km probe),
   the triangle and step-2 deltas with the BUILD-TIME IMPACT STATEMENT, bytes
   fetched per tile, the branch and sha, every deviation (to this spec's author,
   never decided in the lane), everything not done.

Not in this lane: Q1 (Copernicus ring 2), Q2, any inset-side change, the sweep.
