# #1466 — ring and inset candidates read the provider's real footprint (lane lcover)

Builds on PR #1464 (linsets: `layered_warp`, `_item_footprints_by_href`).

## Attribution

* The ring cell walk (`O4_Elevation_Level._approach_ring_cell`) takes the
  FIRST ranked candidate whose `coverage_bbox` reaches the cell
  (`_definition_covers_box` → `definitions._coverage_bbox_intersects`).
  Coverage boxes are rectangles: SWISSALTI3D `5.9,45.7,10.6,47.9` spans
  all of +47+007, so its ring-1 cells over France and Germany go to
  SWISSALTI3D, the fetch answers no data, the cell records `no-coverage`
  and the 90 m base stands -- the walk never reaches ITALY10M (also no data
  there: its WCS serves a constant 0 beyond Italy, measured: 100 % of a
  1 km read of +47+007 is 0.0) nor the ring-2 collapse to GLO-30.
* Same shape at +55-004: ENGLAND1M's box reaches 55.9 N (a coarse WCS read
  of 55–56 N, 4–3 W holds valid data on 12.8 % of its pixels, all in the
  south), SCOTLAND50CM's reaches 54.6 N into England.

## Rule (general: no provider or airport named)

A provider REACHES a box when its declared box does AND its FOOTPRINT, when
known, overlaps the box's interior (`elevation_access.footprints.covers_box`).
The footprint, in order:

1. the strategy's own cached catalogue, read offline
   (`cached_source_boxes`: the tile index of `geojson_tile_index` and
   `os_grid_bucket`, already on disk once the provider was used);
2. a per-tile 0.1° cell map written by a one-off PROBE
   (`Elevation_data/footprints/<code>/<tile>.json`): `stac` asks one
   limit-1 search per cell; `wcs` reads the tile once at 500 m and marks a
   cell covered when it holds valid pixels that are not one constant
   (the fill a WCS serves beyond its data);
3. otherwise unknown: the declared box alone (today's behaviour).

The probe runs in the ring fetch step (`ensure_approach_rings`, before the
plan is resolved; `refresh` re-probes); the plan itself stays offline and
reads the same files, so the frame check and the bake agree with the fetch.
Readers: the ring cell walk, the tile-level wide-area candidate set, and the
inset loop's honest box negative (with `negative_is_unverified` /
`negative_is_version_stale`, which must read the same predicate).

A cell a provider's footprint misses walks on to the next candidate and,
past the last ring-1 one, collapses to ring 2 (RULINGS 2026-10-02c/f
unchanged): over France and Germany on +47+007 that is GLO-30.

## Acceptance

* Synthetic footprints: a provider whose box covers a cell but whose
  footprint does not is not chosen; an unknown footprint keeps today's
  choice; a probed map answers per cell; a WCS constant-fill cell is
  uncovered.
* +47+007 measured with the plan (cells per provider before/after) and a
  one-cell fetch of a French cell that changed provider.

## Results (2026-10-26, this branch, lane-local Elevation_dir)

**+47+007, every 0.1° cell, the ring walk's choice before/after the probe**
(probe 32.8 s, once per tile: SWISSALTI3D 100 limit-1 STAC searches, ITALY10M
one 500 m WCS read):

| | ring 1 SWISSALTI3D | ring 2 COPERNICUSGLO30 |
|---|---|---|
| before (box) | 100 cells | 0 |
| after (footprint) | 60 cells | 40 cells |

SWISSALTI3D's footprint holds 60 of 100 cells; ITALY10M's 0 of 30 (its WCS
serves a constant 0 there).  The 40 moved cells are the rows north of
47.6 N (Germany, Alsace) except the two Basel cells at 7.6–7.8 E, and two
Alsace cells at 47.5 N, 7.2–7.4 E.

**One-cell fetch, `cell_02_05` (7.2–7.3 E, 47.5–47.6 N, France)** through
`fetch_inset` as the ring code calls it: SWISSALTI3D ring 1 -- no raster
(0.7 s; a `no-coverage` cell, the 90 m base stood); COPERNICUSGLO30 ring 2 --
100 % valid, 304.1–619.7 m, 27.6 s.

**+55-004**: ENGLAND1M's probed footprint is 1 of 100 cells (`cell_09_00`,
3.1–3.0 W, 55.0–55.1 N, Gretna), so it can no longer take Edinburgh's southern
ring cells.  SCOTLAND50CM's footprint is its cached tile index (offline):
all 100 cells, the choice unchanged.

**Not done here**: a cell PARTLY inside a footprint (a border cell) is still
served by that provider alone and the part outside keeps the base; filling
it from the next candidate is a per-cell mosaic, a separate change.
Strategies without a catalogue reader or a probe (`tnm_cog`, `direct_cog`,
`coordinate_named_url_list`, `coral_atlas_library`, the static STAC and
tile-grid indexes) keep the box: they can join by growing
`cached_source_boxes` or `probe_cell_coverage`.
