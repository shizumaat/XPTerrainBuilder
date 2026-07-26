# Whole-tile 5-minute feasibility study

**STATUS: DRAFT FOR OWNER REVIEW — NOT RATIFIED.** Research output of the
2026-07-25 feasibility investigation (lead-session-class research agent).
No source was changed; every number below is either a recorded build entry
(`~/.ortho4xp/tile_build_times/*.json`), a committed baseline
(`tools/build_time_baselines.json`), or a labeled probe run on a
**contended** machine (several agents were active; treat probe wall times
as upper bounds — the conclusions rest on ratios of 100x+, not on ±25 %
noise).

Owner directive under study (verbatim): *"optimization plus default
settings that yield quality results in less than 5 minutes per tile, not
including download time."* The CLAUDE.md HARD LAW already carries the
provisional 300 s whole-tile compute budget; this study treats 300 s as
the target for DEFAULT settings.

---

## 1. Measured baseline model

### 1.1 The Cairo datum (+30+031, zoom 16, 3 ICAO airports, 2026-07-25)

| Step | Recorded s | What it actually was |
|---|---|---|
| vector | 698.6 | 694.8 s = auto-patch over HECA+2 (HECA alone 341.4 s clean, `tools/build_time_baselines.json`); ~4 s everything else |
| mesh | 906.0 / 922.4 | Triangle4XP refinement on the ×3 working grid — dissected in §2 |
| masks | 8.1 | negligible (no coastline in tile) |
| imagery | 23.8 | warm cache (246 textures, 0 missing) |
| DSF encode | ~16 min | pure-Python, **separate investigation in flight — treated as a dependency, not re-analyzed here** |

Compute total today (excl. DSF): **~1,637 s**. With DSF as-is: ~44 min.

### 1.2 The historic entries ("mesh 19.2 s, imagery 169 s")

They are not in the store: the recorder keeps only the last 8 records per
tile (`RECORDS_KEPT_PER_TILE = 8`, `src/o4_engine/tile_time_model.py:49`,
trim at `:266`), and the two Jul-25 build cycles rotated them out.
Reconstruction from this study's probes:

- **mesh 19.2 s is the factor-1 state.** A factor-1 Triangle4XP run on
  the identical Cairo inputs takes **0.69 s** (§2.2) and produces a
  382 k-triangle mesh; add the Python post-processing (~15-25 s at that
  size, §2.5) and you land almost exactly on 19.2 s. The tile meshed at
  19 s before the airport-inset working grid engaged.
- **imagery 169 s is cold DDS conversion.** The warm-cache entries are
  23.8/27.0 s with `textures_missing = 0`; 246 textures × ~0.6 s/texture
  jpeg→DDS conversion ≈ 150-170 s. Conversion is *compute*, not
  download — a fresh default tile pays it (labeled hypothesis; the
  historic record's `textures_missing` is gone with the record).

### 1.3 Where minutes go across the whole recorded corpus

All 25 tile histories in `~/.ortho4xp/tile_build_times/` were mined
(~186 step records). Entries inflated by downloads were identified via
`textures_missing > 0` / `insets_fetched > 0` / first-run OSM fetches and
excluded from the compute picture. Warm-compute envelope by tile class:

| Tile class (examples) | vector | mesh | masks | imagery (warm) | compute total |
|---|---|---|---|---|---|
| Ocean/remote (-09+179, -15-172, +22-160) | 5-10 | 1-16 | 4-12 | 1-35 | **15-70 s** |
| Rural, no airport (+36-009, -12-078) | 10-30 | 1-24 | 15-30 | 1-46 | **30-130 s** |
| Town + small airports (-13-077, -13-078, +60-136) | 30-130 (patch 26-126) | 6-23 | 11-21 | 5-38 | **60-210 s** |
| Mountain relief (+36-087, +37-008, +49-118) | 30-80 | 28-150 | 14-47 | 30-100 | **100-380 s** |
| Complex coast / fjord (+60+005, +36-009 cold, -09+178) | 70-300 | 1-124 | **300-900** | 10-190 | **400-1,200 s** |
| Metro multi-airport (+30+031, +25+051, +51-001, +46+006) | 157-2,932 (patch 150-1,217) | 20-922 | 8-198 | 24-80 | **400-3,600 s** |

Three sinks own essentially all the over-budget time:

1. **auto-patch airports** (vector step) — covered by the existing ≤60 s
   per-airport program, `docs/build_time_program_board.md`. Cited as a
   dependency; not re-litigated here.
2. **mesh on inset-densified tiles** — root-caused in §2; the central
   finding of this study.
3. **masks on fjord-class coastlines** (+60+005: 553/895 s on both runs
   — genuine compute, not cache-cold) — real, class-limited, and **not
   yet owned by any program** (open question §7).

DSF encode is a fourth sink on every tile, owned by the in-flight
investigation.

---

## 2. Mesh-step forensics: dissecting the 906 s

### 2.1 How the mesh step consumes the working grid

- Step 1 loads the base DEM as a 3,673² combined raster at 1 arc-second
  (base 3601 + 36-pixel margin, extent [-0.01, 1.01]²;
  `build_combined_raster`, `src/O4_DEM_Utils.py:475-498`), then Phase C1
  densifies it in place: `resolve_working_grid_factor`
  (`src/O4_Airport_Elevation_Insets.py:8338`) picks 1/2/3 and
  `densify_tile_dem_for_insets` (`:8630`) bilinearly resamples
  (`resample_grid_by_factor`, `:8598`) → 11,017² for Cairo (485 MB
  `.alt`, ~10.3 m posting). Insets are then baked into that array and it
  is written to disk.
- Step 2 (`build_mesh`, `src/O4_Mesh_Utils.py:653`) re-derives the same
  factor for the dimension check (`:711`) and hands the `.alt` **file**
  to the native C mesher: `mesh_cmd` passes `nxdem/nydem`, extent,
  `curvature_tol`, the `.alt` and a 1001² curvature-weight raster
  (`src/O4_Mesh_Utils.py:820-841`).
- Triangle4XP reads the whole raster into RAM (`Utils/src/Triangle4XP.c:
  16530-16541`), precomputes a per-pixel curvature map `hme`
  (`:16561-16610`, weight multiplied in at `:16600-16606`), and during
  refinement every tested triangle scans the `hme` max over its bbox;
  it keeps splitting while `maxedge² · scalx² · maxcurv² / curv_tol² > 1`
  and `maxedge² > pix_x·pix_y` (`:7297-7323`). So the DEM posting sets
  **both** the curvature content and the minimum triangle size.
- Airports get 4× stricter tolerance: `build_curv_tol_weight_map` writes
  `curvature_tol/apt_curv_tol = 2.0/0.5 = 4` into every airport bbox
  +500 m (`src/O4_Mesh_Utils.py:137-165`) — Cairo has 11 such boxes
  (all `apt.dat` airports, not just the 3 auto-patched).

### 2.2 Probe series (contended machine; identical .node/.poly/weights)

The original 11,017² `.alt` was snapshotted before a concurrent session
rewrote it (it was rebuilt at factor 1 at 15:47 during this analysis —
itself evidence that factor policy is being touched elsewhere; noted,
not investigated). Probes ran the production Triangle4XP binary with the
production argument vector, differing only in the raster:

| Raster handed to Triangle4XP | Grid | Triangles | Wall |
|---|---|---|---|
| ::3 subsample (= factor-1 grid, insets present at 30.9 m sampling) | 3,673² | 381,850 | **0.69 s** |
| ::2 subsample (real ×3 content at 20.6 m sampling) | 5,509² | 382,502 | **1.01 s** |
| Reconstructed ×3 base, **no insets baked** | 11,017² | 383,390 | **2.58 s** |
| ×3 base + insets re-baked **bilinearly** (this study, §2.4) | 11,017² | **383,390** | **2.57 s** |
| Production `.alt` (×3 + nearest-neighbour inset bake) | 11,017² | **2,482,100** | **~870 s** (recorded step 906/922 minus ~25-35 s Python post) |

Conclusion: **the ×3 grid itself costs ~2 s and ~1 GB RAM. 99.7 % of the
906 s is triangle demand created by the *content* the inset bake writes
into the raster.**

### 2.3 Where the triangles are

Localizing the production mesh (1,245,346 vertices, `Data+30+031.mesh`):
**69.6 % of all vertices (866,489) sit inside the 9 inset bounding
boxes, which cover 4.4 % of the tile** — 490 vs 10 vertices per
0.005°-cell, 49×. The hottest cells are the HECA urban surround
(31.34-31.40 E / 30.10-30.14 N) at ~17,000 vertices/km² — mean edge
~7.6 m, i.e. refinement saturated at the 10.3 m pixel floor.

### 2.4 Root cause: the bake is nearest-neighbour

`_bake_one_inset` samples each inset GeoTIFF onto the working grid with
`inset.alt_vec_strict(query)`
(`src/O4_Airport_Elevation_Insets.py:7430`), and `alt_vec_strict` is
**nearest-neighbour** (`numpy.round` of the pixel index,
`src/O4_DEM_Utils.py:577-591`) — the code's own comment block calls it
"NEAREST NEIGHBOUR on the sub-DEM's own native posting — a 30 m
staircase against the mesh's ramp" (`src/O4_DEM_Utils.py:435-440`).

The Jul-25 Cairo build consumed the new native-30 m GLO-30 inset cache
(`HECA_copernicusglo30.tif`, 364×266 @ 30 m, fetched 09:26 that day; the
older cache generation stored the same data pre-upsampled to 3 m). A
30 m staircase sampled at 10.3 m means every third working-grid step is
a cliff carrying the full pixel-to-pixel amplitude of urban Copernicus
DSM data (buildings, trees: the OSM building-mask covers only ~1.7 % of
the inset — the 1,000 m *margin* around HECA is unmasked Cairo city).
`hme` divides by pix² (=~92 m²), so a 1-3 m step reads as curvature
0.01-0.03; under the ×4 airport weight the refinement target edge drops
to the pixel floor across the whole urban margin. Measured curvature in
the HECA zone grows as ~pix^-1.6 down the scale pyramid (0.0020 at
30.9 m → 0.0039 at 20.6 m sampling vs 0.0004 in a control zone), exactly
the staircase signature; the source GeoTIFF itself at native 30 m is
tame (mean 0.0015, p99 0.0084).

Re-baking all 9 insets **bilinearly** (0.1 s in numpy) removes the
artifact completely: the mesh comes out *identical to the base-only
mesh* — GLO-30 content genuinely holds nothing that a 2.0/0.5 curvature
tolerance wants at 10 m posting. The 906 s bought a staircase artifact,
not fidelity.

A second irony compounds it: the factor ballot that *chose* ×3
(`ideal_bake_errors_per_probe`, `src/O4_Airport_Elevation_Insets.py:
8229`) models the bake as **bilinear** ("truth is the inset's own
bilinear value... each surrounding working-grid NODE takes the inset's
bilinear value"). The decision model assumes an interpolation the bake
does not perform — ×3 was selected to chase a ≤1.0 m quantization
tolerance (`WORKING_GRID_IDEAL_TOLERANCE_M`, `:7785`) that the
nearest-neighbour bake then re-forfeits (~0.9 m staircase error, per the
comment at `:7330`).

### 2.5 The rest of the mesh step

Python post-processing is *not* a major sink: replicating the
`post_process_nodes_altitudes` read/write loops
(`src/O4_Mesh_Utils.py:235-334`) on the probe's real output costs
3.3 µs/vertex → ~4 s at production size; adding the ele-scan and the
5M-line `write_mesh_file` gives ~25-35 s of the 906 s. Nothing else
matters until Triangle4XP's share is fixed.

---

## 3. Localized-densification options (owner question 1)

**(a) Mesher samples a query-time composite (base + insets consulted
inside footprints).** Requires teaching Triangle4XP's input path
(`Triangle4XP.c:16530`, `altitude()` `:3571`, `hme` precompute, bbox
scan) to consult N overlay rasters — a real C surgery on a 16k-line
file, plus a new CLI contract from `build_mesh`. **Not justified by the
evidence:** the flat raster is not the cost (2.6 s at ×3); the content
is. Rejected.

**(b) Per-region densification (uniform base + dense sub-rasters over
inset bboxes).** Same C surgery as (a) minus the compositing. Post-fix
value is ~2 s of mesh time, ~10 s of step-1 resample/write I/O, and
~930 MB of RAM/disk per ×3 tile (11,017² alt+hme ≈ 970 MB vs 108 MB at
factor 1). RAM matters for *parallel* tile builds, so this is a
plausible *second-generation* optimization — but it is not on the
critical path to 5 minutes. Deferred.

**(c) Cap the auto factor by tile cost.** After the §2.4 fix this is no
longer a *time* lever (×3 costs ~2 s), but the ballot should still stop
densifying for base-class insets on merit: a tile whose finest inset is
native-30 m GLO-30 gains nothing real from a 10 m grid (the probe
showed literally zero extra triangles), while paying ~1 GB RAM and
~0.5 GB of raster I/O. The mechanism already exists — factor 1 is on
the ballot for base-class insets (`_working_grid_candidate_factors`,
`:8387`) and only loses because the 1.0 m ideal-bake tolerance is
evaluated at the steepest probe cells of 30 m data. Recommendation:
after the bake fix, re-evaluate `WORKING_GRID_IDEAL_TOLERANCE_M` (or
scale it with the inset's native resolution) so base-class tiles
resolve to factor 1. Quality cost: ≤1-2 m Nyquist error at probe
points — inside GLO-30's own ±2-4 m accuracy band.

**(d) What the code's structure actually offered (RECOMMENDED): fix the
bake interpolation.** One call site: `_bake_one_inset` should sample the
inset bilinearly when the source is coarser than the working grid
(replace `alt_vec_strict` at `src/O4_Airport_Elevation_Insets.py:7430`
with a bilinear vec sampler — `_bilinear_sample_raster` at `:7949`
already exists), and **area-average** when the source is finer (a 1 m
lidar inset point-sampled at 10.3 m — bilinearly or not — aliases real
high-frequency content into the same kind of manufactured curvature;
`gdal.Warp` average resampling, or a box filter at bake time). Evidence
for the lidar half: +51-001 (dozens of `england1m` insets) meshes at
82-208 s today — expected to drop substantially, but **not probed**
(no surviving ×-factor artifacts for that tile; follow-up measurement
needed). Measured effect at Cairo: **mesh step 906 s → ~35 s** (2.6 s
Triangle + ~25-35 s Python post + weight map). This also *improves*
quality: X-Plane currently renders the 30 m staircase.

Consistency note for (d): the "one surface, two readers" ruling
(owner 2026-07-25, `src/O4_DEM_Utils.py:421-445`) is preserved — the
grading law reads `alt_baked`, which is bilinear *on the working
raster*; changing what the bake writes into that raster keeps both
readers on the same (now smoother) surface. The auto-patch solve runs
before/independently of this raster's mesh consumption; conformance is
re-verifiable (§6).

---

## 4. The default-settings package (owner question 2)

Cairo's config was near-stock for everything that matters here
(`default_zl=16`, `curvature_tol=2.0`, `apt_curv_tol=0.5`,
`limit_tris=3.0`, `airport_elevation_insets=True`,
`working_grid_arc_seconds=auto` — all equal to the `O4_Cfg_Vars`
defaults; its `airport_elevation_inset_margin_m=1000` is actually
*smaller* than the stock 2000 m default, so a stock build bakes an even
larger urban margin).

### 4.1 Optimizations that must land (dependencies)

| # | Item | Owner | Effect at Cairo class |
|---|---|---|---|
| O1 | **Inset bake resampling fix** (§3d) | this study → implementation ticket | mesh 906 → ~35 s |
| O2 | **≤60 s per-airport auto-patch** | `docs/build_time_program_board.md` (HECA 341 s today) | vector 699 → ≤185 s worst-case, ≤35 s typical |
| O3 | **DSF encode** | separate in-flight investigation | ~16 min → assumed ≤~60 s (do not double-count) |
| O4 | Masks on fjord-class coasts | **unowned — needs a decision** | +60+005 masks 553-895 s |

### 4.2 Default settings: what to change and what to keep

| Setting | Today | Proposal | Rationale |
|---|---|---|---|
| `default_zl` | 16 | **keep 16** | texture sharpness is the product; imagery compute is 25-170 s (conversion) and parallelizes with other steps in batch |
| `working_grid_arc_seconds` | auto | **keep auto**, but re-tune the ballot after O1 (§3c) so base-class (30 m) insets resolve to factor 1 | saves ~1 GB RAM + ~0.5 GB I/O; zero measured mesh-quality delta |
| `airport_elevation_inset_margin_m` | 2000 | **reduce to ~500, or building-mask the full inset extent** | the margin's job is seam blending (feather is 60 m); 2 km of unmasked urban DSM around metro airports is a quality *and* (pre-O1) cost bug |
| `apt_curv_tol` / weight-4 boxes | 0.5 | keep after O1; optional: apply the ×4 weight only over the *airport boundary* + taxi surfaces rather than bbox+500 m | post-O1 this stops being a cost driver; scoping it is polish |
| `curvature_tol`, `limit_tris`, `min_angle` | 2.0 / 3.0 / 10 | **keep** | factor-1 meshes across the corpus are 1-150 s; not the problem |
| `mask_zl`, `masks_width` | 14 / 100 | keep (this study did not analyze mask quality) | fjord cost needs O4, not a default nerf |

### 4.3 Projected default-build compute (post O1-O3)

| Class | vector | mesh | masks | imagery (cold convert) | total vs 300 s |
|---|---|---|---|---|---|
| Ocean/remote | 5-10 | 1-16 | 4-12 | 1-35 | **≤75 s PASS** |
| Rural | 10-30 | 1-25 | 15-30 | 30-90 | **≤175 s PASS** |
| Town + 1-2 airports (typical ≤10 s/airport) | 30-60 | 6-25 | 11-30 | 30-120 | **≤235 s PASS** |
| Mountain relief | 30-80 | 30-150 | 14-47 | 50-120 | **125-400 s BORDERLINE** (worst relief tiles exceed on mesh+imagery together) |
| Metro + 3 ICAO airports (Cairo class) | ~185 (3×≤60 worst) / ~35 typical | ~35 | 8-20 | 25 warm / ~170 cold | **~260-410 s BORDERLINE**: passes when airports hit *typical* budgets or imagery is warm; worst-case-everything misses |
| Mega-hub tiles (+25+051: 4 airports incl. OTHH-class) | ≤240 worst | 8-30 | 20-200 | 60-180 | **~330-650 s FAIL worst-case** without further airport wins |
| Fjord coast (+60+005) | 70-190 | 50-125 | **550-900 today** | 80-190 | **FAIL without O4** |

Honest bottom line for the owner: with O1-O3 landed, the 300 s default
budget holds for the large majority of the world's tiles. Two classes
cannot hit it without either additional work or an accepted tradeoff:
**(i) fjord/complex-coast tiles** (masks program O4 — or accept ~10-15
min there), and **(ii) tiles with 3+ heavy airports** (bounded by
3 × the per-airport budget; either the airport program beats its 60 s
worst-case on average, airports build concurrently, or these tiles are
accepted at 6-8 min). Cold-imagery DDS conversion (~0.4-0.7 s/texture)
is a swing item worth ~2 min on texture-heavy tiles; it could move into
the download/prefetch phase (it is embarrassingly parallel), which
would take it out of the compute path entirely — candidate follow-up.

---

## 5. Tile-class tradeoff menu (if the owner wants guarantees)

Levers available where the projection still exceeds 300 s, with their
visible cost:

| Lever | Saves | Quality consequence |
|---|---|---|
| Accept 6-8 min on metro-hub tiles | — | none (time only) |
| Build airports of one tile concurrently | up to (N-1)×60 s | none, if auto-patch is made safely parallel (engineering risk, not quality) |
| `apt_curv_tol` 0.5→1.0 default | mesh seconds only (post-O1) | slightly coarser terrain under airports; auto-patch INTERP_ALT triangles pin the pavement itself, so runway surfaces are unaffected |
| Drop working grid to factor 1 for base-class insets (§3c) | RAM/I-O, ~10 s step 1 | measured zero mesh delta at Cairo; ≤1-2 m at inset probe points, inside GLO-30 noise |
| `default_zl` 16→15 | ~50-60 % of imagery compute + downloads | visibly softer textures — **not recommended**; contradicts "quality results" |
| Masks: cap `masks_width`/resolution on fjord tiles | minutes on fjord class | softer water-land blend on the worst coastlines; needs its own study (O4) |

---

## 6. Quality guardrails and verification

For each proposed change:

1. **Bake fix (O1).** Consequence: airport-area terrain becomes smooth
   ramps instead of 30 m staircases (strictly better); solved-grade
   conformance must be re-proven because the raster surface under the
   grading law's `alt_baked` reader shifts by up to ~0.9 m off the old
   staircase. Verify: `tests/test_airport_elevation_insets.py`,
   `tests/test_conformance.py`, `tools/airport_inset_acceptance.py`,
   `check_grade` via `tools/run_with_ledger.py`; in-sim spot check at
   HECA (apron surround, runway shoulders) and one lidar airport
   (EGLL-class) for the area-average half. Build-time law:
   `tools/check_build_time.py --run HECA SPJC OTHH CYXY` before/after.
2. **Ballot re-tune (§3c).** Consequence: base-class-inset tiles keep a
   1" grid; probe-point error grows ≤1-2 m against *bilinear* truth.
   Verify: the acceptance-probe report per inset (already computed at
   fetch time), plus a before/after runway-profile RMS at one GLO-30
   airport.
3. **Margin/masking default.** Consequence: less DSM building noise
   baked near metro airports (quality-positive); a smaller margin
   shrinks the blended zone — check the feather seam (60 m) stays
   invisible at the new margin. Verify: in-sim orbit of HECA boundary;
   `test_airport_elevation_insets.py` seam assertions.
4. **Unchanged defaults (zoom, curv_tol).** No quality delta to verify.
5. **Non-regression watch.** The tile-time store now records
   `insets_fetched`/`textures_missing`; any future A/B must filter on
   them (this study found several corpus entries poisoned by download
   time), and single runs are ±25 % (memory: build-time noise floor) —
   use `check_build_time --runs N`.

---

## 7. Open questions for the owner

1. **Approve the bake-fix ticket (O1)?** Highest-leverage single change
   found: one call site, measured 906 → ~35 s at Cairo, quality-positive.
   Needs the conformance re-proof in §6.1 before landing (HARD LAW
   evaluation is trivially favorable, but the grade-law surface shifts).
2. **Who owns fjord-class masks (O4)?** Without it, complex-coast tiles
   sit at 10-20 min regardless of everything else. Accept, or charter a
   masks program?
3. **Metro-hub guarantee.** Is "typical ≤10 s/airport, worst 60 s"
   (existing program targets) acceptable as the *bound* for 3+-airport
   tiles (i.e., worst case ~6-8 min), or should parallel per-airport
   builds be chartered to make 300 s a hard ceiling?
4. **Imagery conversion placement.** May DDS conversion move into the
   download/prefetch phase (outside the compute budget by the owner's
   own definition, since it is I/O-bound-adjacent and parallel), or must
   it stay inside the 300 s?
5. **Margin default.** 2000 m → 500 m, or keep 2000 m and extend
   building-masking to the whole inset extent? (Both fix the urban-DSM
   quality issue; the second keeps more smooth-terrain correction area.)
6. **Ballot tolerance.** After O1, should `WORKING_GRID_IDEAL_TOLERANCE_M`
   scale with the inset's native resolution so 30 m-only tiles stop
   densifying (RAM/I-O win, zero measured mesh delta)?

---

## Appendix: probe provenance

- Inputs snapshotted from `/Users/noah/X-Plane 12/Custom Scenery/
  zOrtho4XP_+30+031/` (`Data+30+031.{node,poly,apt}`; the 485 MB
  11,017² `.alt` was subsampled to ::2/::3 before a concurrent session
  rewrote it at factor 1 at 15:47 on 2026-07-25).
- Weight raster reconstructed per `build_curv_tol_weight_map`
  (`src/O4_Mesh_Utils.py:137-165`): ones + ×4 boxes for all 11 apt.dat
  airports; the tile's coastline OSM cache is an empty result set
  (no coastline → no coastline weights, and no coastline elevation band
  — the ×3 came from the airport-inset ballot alone).
- Command vector identical to production `mesh_cmd`
  (`-pq10AuYBVPS1406356.37…`, extent 30.99/29.99/32.01/31.01,
  curv_tol 2), binary `Utils/mac/Triangle4XP`.
- All probe wall times measured 2026-07-25 on a contended machine.
- Bilinear re-bake script and run logs:
  scratchpad `probe/` (`f1_run.log`, `f15_run.log`, `f3base_run.log`,
  `f3bil_run.log`).
