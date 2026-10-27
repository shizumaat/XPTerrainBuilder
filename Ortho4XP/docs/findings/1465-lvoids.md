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
