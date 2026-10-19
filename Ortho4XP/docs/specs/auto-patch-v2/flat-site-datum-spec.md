# v2 — flat-site datum as law: preference (b) + declared table (c) (spec, 2026-09-04)

Owner ruling 2026-09-05k-2: **options (b) + (c)** of RULINGS 2026-09-05j.
Author: session (Fable). Implementer: lane `v2flatsite`. New law table
`src/auto_patch_v2/law/flat_site.toml`.

## 1. What v1 does (scout report, 2026-09-04) and what v2 keeps

v1 (`src/auto_patch/flat_site.py`, spec `flat-site-detector-spec.md`):
Z0 = mean CIFP threshold elevation; verdict `flat_candidate` iff S1
threshold spread < 5.0 m ∧ S2 DEM relief over pavement ∪ boundary ≤ the
source-class floor (8.0 m ≥ 1-arcsec, 2.0 m sub-10 m) and plane slope ≤
0.15 % (sea band ≤ 0 m excluded when Z0 ≥ 1 m; DSM trim); S3 |DEM median −
Z0| reported; S4 pack-object seat consensus (|median − Z0| ≤ 1.0, p95−p5 ≤
3.0) CONFIRMS, never gates; `flat_declared` from tile-cfg keys
`flat_site_declared` / `flat_site_declared_elevation_m`. Mechanism = a DEM
SUBSTITUTION in prep (`overlay_flat_site_insets`: constant inset at Z0 over
pavement ∪ boundary ⊕ 200 m plus claimed-object clusters within 5 km, 60 m
feather). Runways stay CIFP-absolute. Objects stay unseated only because the
pack was authored at Z0 and the 1 m re-bake law finds nothing.

v2 today inherits the substitution through the production DEM frame
(`airport/dem_production.py` composes the tile DEM with the flat-site
bake); nothing of it is in the law or in v2's provenance.

KEPT: the detector's signals and constants (moved into the table), the
CIFP datum, the feathered tile-DEM plateau for the terrain OUTSIDE the
patch (the core's mesh reads the same composed DEM, so the patch boundary
and the surrounding terrain agree). CHANGED: inside the patch the datum is
a LAW PREFERENCE the LP prices, recorded in the law digest and the
provenance line, overridable per airport by the table.

## 2. Law table `law/flat_site.toml`

```toml
[detector]                          # v1 flat-site-detector-spec v3, constants by name
threshold_spread_max_m   = 5.0      # S1 (FLAT_SITE_THRESHOLD_SPREAD_M, owner 08-09)
relief_floor_m           = { coarse = 8.0, fine = 2.0 }   # S2 p95−p5 by DEM source class (≥ 1 arcsec | sub-10 m)
fine_source_max_m        = 10.0     # a DEM pixel at or under this is "fine"
lidar_credible_max_m     = 2.0      # ≤ this pixel: lidar_credible short-circuit (never flat by statistics)
plane_slope_max          = 0.0015   # S2 plane-fit slope
sea_band_max_m           = 0.0      # S2a samples at or under this are sea when z0 ≥ sea_band_min_z0_m
sea_band_min_z0_m        = 1.0
dsm_trim_over_median_m   = 0.5      # S2b: trim samples above median + this × floor (fraction of relief floor)
seat_consensus_max_m     = 1.0      # S4 |median seat − Z0|
seat_spread_max_m        = 3.0      # S4 p95−p5 of seats
below_grade_base_y_m     = -1.0     # S4: object parts with base_y ≤ this are below grade (excluded)
margin_m                 = 200.0    # the flat REGION = pavement ∪ boundary ⊕ margin (report + preference extent)

[datum]
source     = "cifp"                 # "cifp" (mean threshold elevation) | "pack_seats" (S4 median) — the verdict's Z0
preference = "flat_datum"           # the Weights.preference group; ranked below law, above seam
weight     = 5.0e4                  # law 1e5 > flat_datum 5e4 > seam 1e4 > end_zone 1e3 > crown 1e2
runway_pins_hard = true             # thresholds stay CIFP-absolute (08-25); the datum NEVER pins pavement

[declared]                          # (c): per-airport overrides — the ONLY airport-specific facts in law/
# OTHH = { z0 = 3.96, source = "cifp" }        # example; absent = measured verdict
# VHHH = { z0 = 5.5,  source = "metres" }      # "metres" = the number IS the datum
```

`law/model.py`: `FlatSite(detector: FlatDetector, datum: FlatDatum,
declared: Mapping[str, Declared])`; `law/tables.py` loads + validates
(unknown key refuses; `declared` values are 4-letter ICAOs; `source ∈
{cifp, pack_seats, metres}`; `z0` required when `source = "metres"`). The
table joins the law digest (`law=<sha>` on the provenance line changes when
a datum is declared — the audit the owner asked for).

## 3. Mechanism

1. **Detector port** — `airport/flat_site.py` (≤ 500 lines, pure
   measurement over the loaded `Airport`: CIFP thresholds, the production
   DEM samples inside pavement ∪ boundary ⊕ margin, DSF object seats from
   the placements already loaded). Returns `FlatVerdict(verdict, z0,
   spread_m, relief_m, slope, seat_median, seat_spread, source_class,
   region: Polygon, signals: dict)`; verdict ∈ `flat_candidate | not_flat |
   lidar_credible | no_data | flat_declared`. A `[declared]` entry
   overrides the verdict and records `auto_verdict` beside it (v1's
   audit). Logged as one `[flat-site] ICAO: <verdict> — Z0 … | …` line in
   the v2 stage log, mirrored into `report.load.flat_site` and the
   provenance line (`flat=Z0` token when substituting).
2. **Preference rows (b)** — `constraints/flat_site.py`: for every planar
   vertex inside `region` whose face role is a GOVERNED pavement or
   groundside role (never runway: `runway_pins_hard`), one soft `Linear`
   row `z_i = Z0` in group `flat_datum`, source citing the verdict. The
   runway family keeps CIFP pins; taxiways/aprons/roads/pads get the
   datum as a preference the hard law rows outrank (a real gradient at a
   spread-< 5 m site still fans lawfully from the pinned thresholds —
   v1's behaviour). No new hard row anywhere. `Weights.preference` gains
   the group from the table (never a literal).
3. **DEM frame** — unchanged: the production frame keeps the core's
   feathered plateau so the patch boundary agrees with the tile mesh. The
   verdict v2 measures is compared with the core's (`synthetic_flat_site`
   provenance on the DEM object, read through `dem_production`): a
   disagreement is LOGGED (`flat-site: v2 <verdict> vs core <verdict>`),
   never silently reconciled — the owner's question.
4. **Declared register (c) is the ONE source** — the v1 detector's
   `flat_site_declared*` tile-cfg keys are RETIRED (loud `retired_cfg_key_
   warning`) and `auto_patch/flat_site.py` reads `[declared]` from the v2
   table (v1 → v2 import is the allowed direction), so DEM prep and the
   v2 law can never declare two different datums.
5. **Re-bake** — unchanged (1 m law); the report prints, per flat site,
   how many units would move (expected OTHH: the 13 of 04k or fewer).

## 4. Acceptance (ONE representative airport = OTHH)

- Twins (`tests/auto_patch_v2/test_flat_site.py`): the table register;
  a synthetic airport with two thresholds at 100.0/100.2 and a 1 m DEM
  ripple → `flat_candidate`, Z0 100.1, every apron vertex carries a
  `flat_datum` row, runway vertices none; the same with 8 m of DEM relief
  → `not_flat`, zero rows; a `[declared]` entry with `source = "metres"`
  overrides and records `auto_verdict`; the LP with the rows lands the
  apron at Z0 where the law allows and NOT where a hard taxi gradient
  forbids (the row is a preference).
- OTHH `build_airport.py OTHH --engine v2`: `[flat-site] OTHH:
  flat_candidate — Z0 3.96`, rows counted, census 0/0, patch body vs the
  05j build (`--base-arm`): the delta is reported (expected ≈ 0 because the
  DEM is already the plateau — say so with numbers).
- CYXY (`not_flat`): zero rows, patch byte-identical (`--base-arm`).
- Build-time statement: the detector reads samples already in memory
  (< 0.6 s expected; measure at OTHH).

## 5. Out of scope

Removing the core's DEM substitution (the tile mesh outside the patch
still needs the plateau), the fast-path partition of v1, and any VHHH
build (no data in the corpus — the declared-table example is
illustrative only).

## 6. Amendment 2026-10-18 — ONE flat-site decision (issue #932; owner option B)

Owner, 2026-10-18 (supersedes RULINGS 2026-10-18f Q2): "I lean toward
eliminating v1 to ensure we don't have two different systems or models",
then "Proceed with B!".

1. **The single decision point is DEM prep.**
   `auto_patch/flat_site_mode.flat_site_substitutions` runs THIS detector
   (`airport/flat_site.detect`, unchanged signals, `law/flat_site.toml`
   incl. `[declared]` and `[datum] source`) per tile airport, after the
   airport smoothing and the cached-inset bake and before anything consumes
   the raster (the v1 ordering point, flat-site-mode spec §2.1), on the
   raw raster through `dem_production.ProductionDem.over_prep` (the
   production sampler over the host tile only).  Inputs are v2's
   (`airport/flat_site_prep.py`): the pack `pack.select_pack` picks, the
   airport frame `load.read_apt` builds, runway ends JOINED to CIFP
   (`load.join_cifp`; a CIFP end with no apt.dat runway no longer counts in
   S1), pavement ∪ runways ∪ boundary, the water cut (`_cut_water`) with
   the apt.dat runways ∪ pavements as the land declaration (the build's
   classified surfaces do not exist yet — reported deviation).  v1
   `auto_patch/flat_site.py` is deleted; nothing of v1 decides.
2. **The record.**  `airport/flat_site.record(fv)` plus `origin` (the frame
   origin) and `region` (the dilated, water-cut rings in that frame) plus
   `plateau` (True once the synthetic inset landed on the raster, else the
   reason it did not).  One record per decided airport, kept on the DEM
   object as `flat_site_decisions = {ICAO: record}` beside
   `synthetic_flat_site_provenance` (same channel: the DEM object →
   `_BakedTile` → `ProductionDem.flat_site_decision()`).  The bake's
   `synthetic_flat_site` provenance entry carries the same record under
   `record`.
3. **The build reads it** (`airport/flat_site_read.verdict_for_build`):
   the `flat_site` stage rebuilds the `FlatVerdict` from the record and
   never re-measures.  The stage cache witnesses it through the DEM
   recorder (a method call on the DEM is digested), so no key input is
   added.  A build with NO record (flat-site mode off, an airport not in
   the tile's airport dictionary, an authored/fixture frame) measures with
   the same detector on the frame it holds and says so in its log line.
4. **S4** (pack seats) is measured in the build after the planar stage,
   as a report only (`signals["s4"]`); it never gated and never moves the
   decision.  `[datum] source = "pack_seats"` cannot be decided before the
   planar stage: DEM prep records the CIFP Z0 under that law value and the
   build reports the seat median beside it (owner question, not decided).
5. **Mismatch rule.**  A record whose verdict substitutes and whose
   `plateau` is True requires the composed DEM to carry Z0 over the
   record's gate extent: median |DEM − Z0| over the region's samples
   ≤ 0.05 m (`flat_site_read.PLATEAU_TOL_M`, a mechanism tolerance: the
   plateau is a constant raster).  Otherwise the build raises
   `ColdDemFrame` (catalogue `airport_elevation_missing`) — the frame is
   not the one DEM prep decided on.  A record whose frame origin differs
   from the build's frame is the same error.  The `signals["core"]`
   comparison and its "logged, not reconciled" note retire (§3.3
   superseded).
6. **Output change.**  Mesh and patch change only where v2 inputs give a
   different verdict, Z0 or extent than v1's did.  Candidates before
   building: any existing sidecar whose `report.load.flat_site.signals.core`
   differs from its `auto_verdict` / `z0_m` (the build's old
   "DISAGREEMENT" line).
