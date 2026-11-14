# #2089 — Inset threshold correction (spec, 2026-11-14)

Owner decision 2026-11-14T20:27Z (option 1): "Correct the inset: when a
high-resolution DEM disagrees with the surveyed thresholds, shift it with a
smooth correction fitted to those thresholds. It would apply to every airport."

LICJ (+38+013) is the test case, never the scope (RULINGS 2026-10-05e). Law
this rests on: 2026-10-19aa (insets are judged at the CIFP thresholds),
2026-09-04i ("the DEM is not always reliable"), 2026-09-03j (one production
DEM frame), 2026-08-30l (consumer census), 2026-11-13o (content keys),
e9daef5 (no corpus write).

Open questions (§10) are put to the owner; the lane implements the
recommended answers (model B admitted, bar 3.0 m, refuse above 10 m) and
keeps each a constant / one switch so a different answer is a one-line change.

## 1. Measured (cached corpus, no build)

| LICJ threshold | CIFP m | inset (ITALY10M) m | residual r = CIFP − inset | base (.hgt) m |
|---|---|---|---|---|
| RW02 | 12.80 | 4.65 | +8.03 | 13.32 |
| RW07 | 10.06 | 5.89 | +4.20 | 10.20 |
| RW20 | 6.71 | 4.44 | +2.29 | 7.34 |
| RW25 | 15.24 | 15.82 | −0.46 | 15.26 |

(Inset column is the point sample; r uses the 15 m disc median.)

Owner sites: inset 5.11 m at P1 (38.184827, 13.101037) and 1.38 m at P2
(38.186264, 13.099513).

| Model | P1 | P2 |
|---|---|---|
| Thresholds only, plane | 6.10 | 1.88 |
| Thresholds only, inverse-distance | 7.55 | 3.67 |
| Base-witnessed shape, exact at thresholds (§3 model B) | 9.96 | 5.77 |

The error is not a tilt: it peaks on the shore strip between thresholds, and
the base DEM reproduces all four residuals within 1.4 m after a 150 m
low-pass. Shoreline north of P2 today: 0.93 m, then 4.76 m on the base
beyond the inset's no-data edge. With model B: 5.48 m, then 4.76 m, falling
to the water.

Corpus (620 cached insets with a CIFP reading): max|r| > 3 m on 84, > 10 m
on 22. Lidar-class battery airports are ≤ 0.35 m. Over 3 m on the battery:
LICJ, SPJC (3.56 / 3.42), TFFJ (−5.31), LICP (+20.35).

## 2. Where it lives (one derivation, one application)

The correction is arithmetic, not data (the flat-site precedent): it is
never written to `Elevation_data`, never cached, and no file is opened for
writing.

- NEW `src/elevation_access/threshold_correction.py`: numpy / scipy / GDAL
  reads only, no `O4_*` import. It holds the constants (§3), the reader
  `threshold_readings(inset_path, thresholds)`, `verdict(readings)`,
  `correction_field(...)` and the provenance record. The disc reader is
  MOVED here from `tools/harness/build_airport.py` (`_inset_disc_median_m`,
  `_threshold_judgement`); the harness imports it. One reader, one bar.
- PLAN, in `O4_Airport_Elevation_Insets.py`:
  `plan_threshold_corrections(tile)`, called at the END of
  `densify_tile_dem_for_insets` (rename today's body `_densify…`; the
  public function calls it, then the plan). That is the one moment every
  composition path passes with the working grid final and `alt_dem` still
  the pure base: `O4_Vector_Map.compose_tile_dem_from_disk:2117` (tile
  step 1, v2 `ProductionDem._compose`, the harness) and
  `O4_Mesh_Utils.py:2765` (step-2 re-bake). It is a no-op on a header-only
  DEM. For each `bake_candidate_inset_paths(tile)` entry:
  1. Airport code from the file name; CIFP thresholds through
     `flat_site_mode` (export `_resolve_xplane_root` and `_cifp_runways` as
     public names; `tile.auto_patch_xplane_root` wins).
  2. Readings and verdict (§3).
  3. For an `apply` verdict whose extent lies wholly inside the tile, copy
     the base window: `alt_dem[window].copy()`.
  4. Store `tile.dem.inset_threshold_plans[inset_path]`.
  Extract the window index arithmetic and the sub-DEM lookup of
  `_bake_one_inset` (`:7447-7490`) into two helpers that both the plan and
  the bake call.
- APPLY, in `_bake_one_inset`, only when `inset` was not passed in
  (synthetic flat-site insets are never corrected): after `valid` and the
  ring-offset measurement, before `blended`. Build the field from the
  plan, then `inset_values[valid] += (τ·C)[valid]`.
  **HARD RULE:** compute `valid` first and add on valid cells only. A
  corrected no-data sentinel would bake as ground (the #1956 class).

## 3. The model

Constants live in the new module and nowhere else:
`BAR_M = 3.0` (the harness's `INSET_ARP_SANITY["warn_abs_delta_m"]` reads
it), `CAP_M = 10.0` (= `INSET_DATUM_WARNING_THRESHOLD_M`),
`MIN_WITNESSES = 2`, `DISC_RADIUS_M = 15.0`, `SOFTEN_M = 15.0`,
`TAPER_M = 300.0`, `BASE_SIGMA_M = 150.0`, `BASE_TOL_M = 1.5`,
`BASE_PRIOR = 0.02`, `MATERIALITY_M = 0.01`.

**Readings.** For every CIFP `RW*` record of the inset's airport, m_i is
the median of the inset FILE's valid cells within 15 m (at least one
cell); r_i = z_i − m_i. A threshold with no valid cell is not a witness.
Judged per inset file, so an under-layer and a top layer are judged
separately.

**Verdict.**
- Fewer than 2 witnesses: none.
- max|r_i| ≤ BAR_M: none. The bake is byte-identical and no provenance key
  is written.
- max|r_i| > CAP_M: `refused`. Raster untouched, one loud line, recorded
  (a datum-class or CIFP-class disagreement; see Q3).
- Otherwise: `apply`.

No outlier rejection. Thresholds are hard pins in the solve, so the ground
must follow whatever the airside does there. "One end agrees, the others do
not" is handled by the field, not by an offset.

**Field**, on the bake's working-grid window, in metres:
- T(x) = Σ w_i r_i / Σ w_i, with w_i = 1 / (d_i(x)² + SOFTEN_M²). Exact at
  the thresholds, bounded by the residuals, defined for any n ≥ 2.
- lo = min(0, min r_i); hi = max(0, max r_i).
- **Model B (base-witnessed)**, only when the inset's extent lies inside
  the tile and the stashed base window matches the bake window:
  - D = base − inset on cells that are valid, not base no-data, and inside
    [lo − BASE_TOL_M, hi + BASE_TOL_M]. A cell where the base disagrees by
    more than the surveyed range is canopy, buildings or slope noise, not
    evidence.
  - S = (G_σ∗(M·D) + κ·T) / (G_σ∗M + κ), with σ = BASE_SIGMA_M,
    κ = BASE_PRIOR, `scipy.ndimage.gaussian_filter(mode="constant")`.
  - e_i = r_i − S(threshold_i). Admitted only if max|e_i| ≤ BASE_TOL_M
    (LICJ: +0.23, +0.13, −0.90, −1.39).
  - C = clip(S + IDW(e_i), lo, hi).
- **Model T (thresholds only)** otherwise: C = T. This covers a straddling
  inset (two tile copies have no single base), a base that does not
  reproduce the thresholds, and a missing stash.
- **Taper.** τ = t²(3 − 2t), t = clip(d_edge / TAPER_M, 0, 1), where
  d_edge is the bake's own rectangular `distance_to_edge`. The correction
  is zero at the inset box edge and full 300 m inside it; the box is the
  boundary's box plus 465 m, `inset_fetch_margin_m`. It is NOT tapered at
  a no-data edge: land beside the sea keeps its corrected height.
- max|τ·C| < MATERIALITY_M: treated as none.

## 4. Shore and #1956

- The sentinel-smear and provider-fill masks act on the file, upstream;
  they are not touched. The correction never changes `valid`.
- At LICJ the corrected land meets the base beyond the no-data edge within
  about 0.7 m and then falls to the water. That is the embankment.
- No shore-specific code.

## 5. Provenance

- A record exists only for `apply` and `refused`; an absent key means
  nothing to report:
  `{"status", "model": "base_witness"|"thresholds", "why", "bar_m",
  "readings": [{"runway", "elevation_m", "inset_m", "residual_m",
  "base_fit_m"}], "applied_m": [min, max], "taper_m"}`.
- It is set on `tile.dem.inset_threshold_corrections[inset_path]` and
  copied into that inset's `airport_inset_provenance` entry as
  `threshold_correction`. That reaches `dem_provenance_from_dem`, the v2
  report and `frame.json`.
- `ProductionDem._bake` adds `correction:<stem>:<airport>` to its
  provenance.
- `O4_Unpatched_Airports.record_inset_sources` rows gain `corrected_m`.
  `O4_Tile_Info._airport_elevation_text` appends ", corrected to runway
  thresholds" for those airports. This is an engine string that both UIs
  already show; no layout change.
- One log line per applied or refused inset.
- The harness `inset_arp_sanity` entry gains the same verdict, so a WARN
  reads as corrected at the bake.
- `O4_ZProv` is not involved; it logs patch-tainted vector nodes only.
- Freshness: `o4_dem` (input files), `o4_cifp` and `o4_code` already cover
  the inputs. Add the new module wherever the code-closure twins require.
  `O4_Step_Reuse` vector-step inputs gain `inset_cifp` (the content
  identity of the CIFP file of every airport with a bake-candidate inset);
  a record without the key reads as equal (13o).

## 6. Consumer census (RULINGS 2026-08-30l)

| # | Reader | Reads | Ruling |
|---|---|---|---|
| 1 | `.alt` write, Triangle4XP | baked raster | corrected; intended |
| 2 | `DEM.alt_vec` baked query (patch pins, roads, vector z) | baked raster | corrected. Gate off or an unbaked user sub-DEM: the composite reads the RAW inset; log one loud line when a correction was applied; not fixed |
| 3 | v2 `ProductionDem.z_many` (body datum and trend, ground datum, zone rings, bank daylight, seam pins) | baked raster | corrected; thresholds stay CIFP pins, and the DEM now meets them |
| 4 | Threshold seam yield (2026-10-26b) | \|CIFP − DEM\| near a seam | shrinks; straddlers use model T on both tiles |
| 5 | Flat-site detector and plateau | baked raster, after the bake | reads the corrected surface; the plateau still overrides inside its footprint |
| 6 | Cluster insets' `refuse_datum_offset_over_m` | ring vs raster | reads the corrected raster; fine |
| 7 | Ring-offset and provider systematic warnings | raw inset values | measured BEFORE the correction; unchanged |
| 8 | Tile overlay, approach rings, bathymetry band | baked earlier | never corrected; the taper meets them at the box edge |
| 9 | Smoothing radius, coverage mask, curvature weight boxes, `fine_many`, `source_pixel_m` | extents and resolution | unaffected |
| 10 | Working-grid ballot, acceptance probes, seam harmonisation | raw inset files | unaffected |
| 11 | Inset water supplement (hydro-flat rings) | raw file | unaffected; `TileWater.level_of` samples the baked raster, so inland levels move with the land |
| 12 | `terrain_cut_stage` bake, apply, hold | baked raster | corrected; the step-2 path gets the same plan |
| 13 | Object stage, drawn gate, `drawn_site` | mesh and products | corrected through 1 |
| 14 | Sentinel smear, provider fill, ladder fills | the file | upstream; fills are valid cells and are corrected with the core |
| 15 | Harness ARP and threshold sanity, `--strict-inset-datum` | raw file | still judges the file; the record names the correction |
| 16 | `mesh_inset_error.py`, `apron_drape_read.py` | mesh vs raw inset | will show the correction as a difference at applied airports; note it in their index rows |
| 17 | `o4_engine/terrain_commands.py` | raw files | NOT VERIFIED (lane: read it and rule it in the report); unchanged |

Emittable: a smooth scalar added to a height raster (LICJ peak added slope
2.8 %).

## 7. Tests (headless, `tmp_path`, synthetic airport codes only)

`tests/test_inset_threshold_correction.py`:
1. Within the bar: baked array equals the control (`array_equal`); no
   provenance key.
2. Constant offset of −5 m: the 15 m disc median of the baked raster at
   every threshold is within 0.10 m of CIFP; zero change at the box edge;
   the taper is monotone.
3. LICJ-pattern residuals (+8, +4, +2, −0.5): exact at the thresholds;
   field within [−0.5, 8].
4. No-data cells are never corrected: the baked raster there equals the
   base, and no cell falls below the control's minimum.
5. Model B is admitted on a base that reproduces the thresholds, and a
   mid-field probe lands within 1 m of truth where model T misses by more
   than 2 m. Model B is refused on a canopy base (+15 m away from the
   thresholds) and falls to T.
6. Straddling extent: model T even with an agreeing base. Two copies
   offset by a pixel differ at the seam by no more than they differ at
   the thresholds.
7. One witness: none. Over the cap: `refused`, raster unchanged.
8. The ring-offset return value is unchanged by a correction.
9. `tests/test_harness.py`: the harness and engine readings are the same
   numbers.
10. Step reuse carries `inset_cifp`.

Also run `test_no_airport_specific_code`, `test_v1_retired`, the code
closure and registry twins, and the existing inset and flat-site suites
that `tools/blast.py` names for the changed files.

Extend `tools/inset_coverage_census.py` with `--section thresholds`
(per cached inset: readings, verdict, model, straddler copies that
disagree) and add its `tools/INDEX.md` row. The lane report carries the
applied and refused list; that is the master's sweep expectation.

## 8. Closing test

`build_airport.py LICJ --tile 38 13 --pack-copy DIR --tag …`, judged
against the shared control at the base sha. `drawn_gate.py LICJ --tag …
--against CONTROL.json` with `--site P1=38.184827,13.101037`,
`--site P2=38.186264,13.099513`, `--site coast=38.186446,13.099469,60`:
PASS, no MOVED (other than the intended P1/P2/coast lift, which the report
states with numbers).

Drawn-mesh reads (`tools/mesh_elevation_sampler.py --point …
--alt-raster`), quoted first in the report:

| Site | Control | Bar (model B) | Bar if Q1 is answered "thresholds only" |
|---|---|---|---|
| P1 | 4.85 m | 9.0–11.0 m | ≥ 7.0 m |
| P2 | 1.31 m | 4.5–6.5 m | ≥ 3.5 m |

- P1 step to the adjacent airside: ≤ 1.0 m, target 0.5 m (was over 5 m).
- Transect from P2 north to the water: no upward step over 0.5 m.
- Coast: lowest drawn elevation within 60 m ≥ −0.5 m, and the count of
  `.alt` cells below −1 m inside the inset box equals the control's.
- Byte-unchanged: a patch-only harness build of one within-bar airport
  (KEGE, 0.17 / 0.20 m) has a patch body sha equal to the artifact-ledger
  control.
- LICP on the same tile must read `refused` with its raster window
  unchanged.

Build time: the plan costs a few disc reads per inset and the field one
Gaussian per applied inset, under 0.5 s per tile (< 1 % of 300 s).

Convergence: materiality 0.01 m; at most 2 fix iterations per bar; write
`.progress` stamps. Never raise the lane cap; delete scratch builds when
reporting.

`docs/DEFERRED_VERIFICATION.md`: the SPJC seam (two copies, model T) and
the TFFJ and SPJC movement, read at the batch sweep.

## 9. Known limits

- Approach rings from the same provider keep the bias outside the inset
  box (the LICJ plain beyond 465 m).
- A straddler whose two copies sit on either side of the bar would be
  corrected on one tile only; the census flags it.
- A neighbour airport's correction overlapping this airport's box is not
  in this patch's stamp (the same class as a neighbour's flat-site
  plateau).

## 10. Open questions for the owner

1. **Base DEM as the shape witness (model B)?** Thresholds alone give P2
   3.7 m and P1 7.6 m. With the base admitted only where it reproduces
   the thresholds, P2 is 5.8 m and P1 10.0 m. Recommended: yes.
2. **Bar of 3.0 m?** It is the existing "inset disagrees" number: 84 of
   620 cached insets, including SPJC and TFFJ. A 2.0 m bar gives 148 and
   adds HECA, EIDW and KSFO. Recommended: 3.0.
3. **Above 10 m (22 insets, e.g. LICP +20 m, ESVL +10 to +13 m): refuse
   and report, or correct anyway?** Recommended: refuse and report.
