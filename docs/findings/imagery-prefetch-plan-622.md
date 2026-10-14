# Imagery download in parallel with the vector/mesh steps — plan (#622 item 3)

Lane `reuse615`, 2026-10-13. NOT built tonight; items 1, 2 and 4 of #622
(the download's share of the bar, the measured rate, one engine-side model
both apps render) landed on `claude/reuse622`. This file is the plan for
item 3, for the master to schedule.

## What the dependency graph allows

- The texture SET is mesh-derived: `O4_DSF_Utils.build_dsf` walks the
  triangles and queues `(til_x, til_y, zl, provider)` per textured
  triangle (zone list, airport cover zoom, sea/land). It cannot be known
  exactly before the mesh step.
- The texture GRID is the zoom level's and is the same for every imagery
  source. So a tile that was built before at the same zoom names its
  textures already: the live `terrain/*.ter` files of the active scenery
  (`O4_Tile_Staging.LIVE`) are named after their texture
  (`<texture name><suffix>.ter`, `O4_DSF_Utils` ter naming; the texture
  name carries the grid position, source and zoom —
  `FNAMES.dds_file_name_from_attributes`).
  Re-keyed to the new source, that list is the best pre-mesh guess.
- A first build of a tile has no such list. The whole-tile grid at the
  base zoom is an upper bound (~130/cos(lat) textures at ZL16 over the
  1° square) but sea tiles use far fewer — prefetching it would download
  imagery the build never uses. So the first build does not prefetch.

## Design

1. **Prefetch list** (`O4_Imagery_Prefetch.candidates(tile)`, new module):
   the live terrain folder's texture attributes at the tile's planned
   zoom, re-keyed to the planned source, minus orthophotos already in the
   imagery cache (`FNAMES.jpeg_file_dir_from_attributes`). Empty when the
   zoom differs, the tile was never built, the texture mode is
   `default_xplane`, or the source is a combined one.
2. **Where it runs**: a prefetch is an `imagery`-class fetch for the
   parallel orchestrator (`o4_engine/parallel.py`): admitted only while
   the imagery class has room (`imagery_class_limit()`), so the
   per-provider concurrency limit is the one the imagery step already
   obeys. It runs in a WORKER CHILD (the children own provider sign-in
   through the secret broker; the parent never downloads) as a new step
   key `prefetch` placed in the tile's program between `vector` and
   `mesh`, with `IMG.build_jpeg_ortho` per candidate and no DDS
   conversion (conversion needs the colour-harmonization field and the
   masks).
3. **Stop rule (#598)**: what arrived stays — orthophotos are cache, not
   scenery; a Stop cancels the child exactly as the imagery step's
   download queue is cancelled (`UI.red_flag`). Nothing is activated.
4. **Top-up**: the imagery step is unchanged; it finds the prefetched
   orthophotos in the cache and downloads only the rest
   (`note_orthophoto_download` counts only those, so the bar and the rate
   stay honest).
5. **Progress**: the prefetch step gets its own window priced by the
   same download model (`tile_time_model._imagery_components`'s download
   term over the candidate count); the imagery step's `textures_to_download`
   then falls by what was prefetched.

## Why it was not built tonight

It is a new orchestrator step, a new child program entry and a provider
download path outside the imagery step, and it can only be proven on a
real network download (the harness tile path does not go through the
orchestrator; no twin exercises sign-in or a provider's rate limit).
That is more than fits safely before the 07:00 test build.

## Twins it needs

- candidates: terrain folder at the same zoom → re-keyed list; other
  zoom / default textures / combined source / never built → empty;
  cached orthophotos removed.
- orchestrator: a prefetch step is admitted only under imagery-class
  room; a Stop during it leaves the downloaded orthophotos and activates
  nothing; the imagery step then downloads only the remainder.
