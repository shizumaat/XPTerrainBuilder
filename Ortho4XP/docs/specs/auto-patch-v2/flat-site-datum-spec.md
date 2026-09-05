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
