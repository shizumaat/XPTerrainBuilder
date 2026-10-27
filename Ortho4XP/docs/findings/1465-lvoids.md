# Base elevation voids filled to 0 m (#1465; lane lvoids)

## Attribution

The ONE load site is `O4_DEM_Utils.DEM.__init__` (every tile, mask, DSF
and coastline load constructs a `DEM`; the base raster's nodata is decided
there and nowhere else).  With `fill_nodata=True` (the default) it calls
`fill_nodata_values_with_nearest_neighbor`, which

* refuses outright when the raster holds 10,000 or more void posts
  (returns 0), and the caller then runs `nodata_to_zero()`; and
* fills the rest after 20 dilation steps with 0.

`N47E007.hgt` (3601 posts, Viewfinderpanoramas) holds 27,883 void posts
(0.215 %) in 2,893 islands, the largest 1,152 posts (2,850 islands of at
most 100 posts).  27,883 > 10,000, so EVERY void of the tile went to 0 m,
the one inside LFSB included.  Nothing in the ladder is consulted: the
Copernicus fallbacks (`fallback_rank` 1, 2; #561) only replace a WHOLE
cell whose configured source cannot be reached.

## Rule

For a base cell read from the configured base source (not a user
`custom_dem` file, whose documented "too much nodata -> 0" stays):

1. Voids the neighbour fill closes (fewer than 10,000 posts, closed
   within its 20 steps) are filled by it exactly as before -- every tile
   that never reached 0 m is byte-identical.
2. Otherwise each void post takes the first ranked fallback source
   (`fallback_rank`, Copernicus GLO-30 then GLO-90) that covers the cell
   and holds data there, offset by the base-minus-fallback difference of
   the nearest valid base post, so the fill meets the base at the void's
   edge (GLO-30 is a surface model, +7.5 m mean against VFP).
3. Posts no fallback covers take the nearest valid base post's height.
4. 0 m is never written for a void.  A raster with no valid post at all
   keeps the old zero (nothing to interpolate from).

The fallback cell is cached at its own path (`<cell>_COPERNICUSGLO30BASE.tif`);
the cell is recorded in `DEM.base_substitutions` with `voids=N`, so the
freshness stamp and the tile's closing note name it (RULINGS 2026-10-12e).

## Acceptance

* +47+007: 0 posts at 0 m that were voids in `N47E007.hgt`; the LFSB void
  filled within a few metres of its rim.
* A tile without voids, or with voids the neighbour fill closes:
  byte-identical raster.
* Offline (fallback unreachable): voids take nearest heights, never 0.

Amendment (measured): the tile's base is the COMBINED raster (3673 posts,
0.01 deg beyond the cell on every side), so the fallback cell is sampled
on the base raster's own frame (`on_base_grid`); the 344 margin voids
(neighbour cells' posts) take the nearest-post fill and ask no further
source.

## Results (2026-10-26)

* `N47E007.hgt` alone: 27,883 void posts, all at 0 m before; after, 0 at
  0 m, 0 nodata, every valid post unchanged, all 27,883 from GLO-30.  Rim
  step (fill vs its valid neighbour) p50 1.40 / p95 5.54 / max 21.5 m;
  the natural post-to-post step 1-4 posts outside the voids p95 3.0 /
  max 31 m.  GLO-30 is a surface model: the voids over built-up Basel
  read up to ~14 m over their rim (e.g. 47.5936, 7.5359: fill 266.8 -
  282.8 m, rim 258 - 269 m).
* Composed tile DEM +47+007 (`compose_tile_dem_from_disk`, 11,017 posts a
  side): posts at 0 m 148,865 (main) -> 0 (this fix, full and trimmed
  inset boxes).
* #1330's trim on top (cached insets CROPPED to the trimmed box): inside
  boundary + 305 m 0 posts changed at all 14 airports (LFSB 132,024, LFGB
  39,389); between that and the old 2 km box 0 posts at 0 m at every
  airport (was LFSB 6,196, LFGB 2,791 without this fix); p99 |delta| there
  LFSB 3.49 m, LFGB 2.25 m (the 10 m ring replacing the inset).
* Closing build `lvoids1465_LFSB3` (trim + fix, `--refresh-data dem`:
  +2 files, the GLO-30 and GLO-90 cells of +47+007): rc 0, patch created
  249.8 s, body sha 2847b80c522e = the linsets control
  `LFSB_20261026T194640`; law-true 1,150, adjudicated 579 (airside 283,
  groundside 295, mixed 1) -- unchanged.
