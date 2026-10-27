# Inset and ring fetch: read only what the build uses (#1327, #1330; lane linsets)

Law: owner RULINGS 2026-10-26t (Q175) option (a) — read approach rings and
outer airport zones from a source no finer than they need (or the 0.5 m
source's own overview layer), fetch only the part of each inset box the build
reads, share one download pool across tiles; unchanged quality where pavement
is graded.  RULINGS 2026-10-02f (the ring cell's ladder rung) and 2026-10-02c
(GLO-30 serves ring 2 only where no wide-area source covers) are unchanged.

## 1. Attribution (measured 2026-10-26, this tree, GDAL 3.13.3)

One ring cell fetched three ways through the shared warp
(`warp_vsicurl_sources_to_geotiff`), cold curl cache each time:

| cell | sources | wall | output vs all-sources |
|---|---|---|---|
| +55-004 `cell_01_08` SCOTLAND50CM 10.31 m, all | 18 | 149.7 s | — |
| same, only the 14 sources that carry overviews | 14 | 17.7 s | byte-identical |
| +47+007 `cell_00_00` SWISSALTI3D 10.31 m, all | 238 | 150.5 s | — |
| same, newest vintage of each 1 km tile only | 108 | 10.2 s | byte-identical |

* The 0.5 m-ness is NOT the cost.  GDAL's warp already reads a COG's
  overview (`-ovr AUTO`, its default): SRSP phases 3–6 and the national
  programme carry 2–6 overview levels, and the swissALTI3D ring fetch
  already picks the 2 m asset (`_select_stac_dtm_assets`).
* THE COST IS HIDDEN SOURCES.  SRSP phase-1 and phase-2 (1 m, 2–10 km tiles,
  `LAYOUT` not COG, **no overviews**) are read at full resolution for a
  10 m cell — 132 s of the 150 s — and every pixel they deliver is
  overwritten by the later 0.5 m campaigns (the mosaic is later-wins,
  finest last).  swissALTI3D lists 2019, 2021 and 2025 vintages of the same
  tile; the older two are read and overwritten.
* Fetch-to-fetch noise of the provider itself (fresh vs the 2026-10-25
  cached cell, same sources, same code path): SCOTLAND50CM p50 1.1 cm, p99
  22 cm, max 2.16 m; SWISSALTI3D p50 0.65 cm, p99 23 cm, max 4.26 m.  This
  is the "provider's own resampling noise" bar.
* Ring cells fetch 4 per tile with NO provider slot
  (`_fetch_approach_ring_cells` calls `fetch_inset` bare), so three tiles
  open twelve streams to one host; the inset fetch already holds the
  provider's machine-wide class (#1236).
* Inset boxes are boundary bbox + `airport_elevation_inset_margin_m`
  (2000 m): EGPH 512 MB.  The graded zones reach at most 304.8 m beyond
  pavement (FAA RSA length; ICAO strip end 60 m + RESA 240 m = 300 m; RAOA
  300 m; zone 2 ≤ 76.2 m from the centreline), and the boundary already
  holds the pavement (`update_airport_boundaries`).

**Refuted: re-ranking ring providers coarsest-first.**  Coverage boxes are
rectangles.  At +55-004 ring 2 the candidates are SCOTLAND50CM 0.5 m and
ENGLAND1M 1 m (bbox to 55.9 N, no data in Scotland); at +47+007 ring 1,
SWISSALTI3D 0.5 m and ITALY10M 10 m (bbox to 47.2 N, no Italian data on the
Jura).  Coarsest-first sends those cells to a provider with no data there,
the cell records no coverage and the 90 m base stands.  The provider
ranking stays; "no finer than needed" is delivered by the READ (rules R1,
02f's coarsest rung, the overview).

## 2. Rules

**R1 — a hidden source is never read** (`elevation_access/layered_warp.py`,
wired into `geojson_tile_index` (so `os_grid_bucket`) and `stac`).  The
mosaic order stays the law (later wins).  Sources are cut into CONTIGUOUS
chunks from the end (a chunk closes when the next source's footprint
overlaps one already in it); the last chunk warps the whole box exactly as
before; each earlier chunk warps only its members whose footprint touches a
pixel still without data, and only over the window of those pixels, on the
same pixel grid, and fills nothing but holes.  Exact except at the
partial-density edge pixels where GDAL blends a later source over an earlier
one (now: no blend) — within the noise above.  A source without a known
footprint is never skipped.

**R2 — the inset box is the graded reach** (`inset_fetch_margin_m`) —
**HELD for the owner (section 5, A2): implemented and measured on the local
branch `claude/linsets-trim`, not in the PR.**  The
box margin is `min(airport_elevation_inset_margin_m, INSET_GRADED_REACH_M
+ airport_elevation_inset_feather_m + INSET_FETCH_PAD_M)` = min(setting,
305 + 60 + 100 m).  Derived once in `_airport_bounding_boxes` (its default
margin), so the fetch, the recut test, the harness frame and the pre-flight
agree.  The coastline band's visibility ladder keeps the setting's box (its
tiers are not this ruling's subject).  The delivery WARN reads the reach
(`min(1000 m, graded reach + feather)`), not 1000 m.  Cached insets cut for
the larger box still contain the new one: no recut, no refetch.  Beyond the
box the 10 m ring stands (it is baked under every inset already).

**R3 — one pool**: a ring cell holds its provider's fetch slot
(`_held_provider_fetch_slot`), the class the inset fetch and every tile of
the session share (#1236).

**R4 — a progress line per ring cell** (`approach rings: N/M cells`).

## 3. Consumer census for R2 (every reader of the inset box or extent)

| consumer | reads | ruling |
|---|---|---|
| `ensure_insets_for_tile` fetch | default margin | trimmed (the point) |
| `inset_recut_is_needed` | requested ⊇ required | smaller required: no recut |
| `dem_production._required_inset_box`, `frame_state` | default margin | trimmed — same predicate as the fetch |
| `build_airport` warm/las rows, `inset_preflight` | default margin | trimmed — same |
| coastline visibility ladder (`O4_Elevation_Level` ~808) | box distance tiers | passes the SETTING: unchanged |
| bake (`_bake_one_inset`), `baked_inset_boxes`, mesh curv weights | delivered extent | smaller beyond 465 m only; graded region inside |
| `inset_delivery_shortfall` WARN | 1000 m functional | reach-based (else every new inset warns) |
| completion stamp key | setting value | unchanged (smaller box needs no re-judge) |
| approach rings | boundary polygons | unchanged |

## 4. Acceptance

* A1 ring cells: R1 output vs the all-sources warp — identical or within
  the §1 noise (both cells above, plus one cold cell each tile).
* A2 graded region: the cached inset CROPPED to the R2 box (same pixels)
  baked vs the full cached inset baked — the composed DEM inside boundary
  + 305 m identical.
* A3 R1 at inset resolution: a fresh R1 inset vs a fresh all-sources
  inset over the same box — within noise inside the graded region.
* A4 time: ring-cell and inset fetch wall before/after (single runs swing
  ±25 %; network-bound runs more — quoted as such).

## 5. Results (2026-10-26, this tree)

**A1 — R1 on ring cells, through the engine's own fetch path**
(`fetch_inset(rung, cell box, class, path)`), against the all-sources warp
taken minutes earlier:

| cell | before | after | sources read | output |
|---|---|---|---|---|
| +55-004 `cell_01_08` SCOTLAND50CM 10.31 m | 149.7 s | 10.8 s | 6 of 18 | byte-identical |
| +47+007 `cell_00_00` SWISSALTI3D 10.31 m | 150.5 s | 10.8 s | 126 of 238 | byte-identical |

The first cut warped each later chunk over the WINDOW of its holes only; it
was not identical (Jura cell: 26.7 % of pixels differ, p99 6 mm, max 8.0 m
on cliffs — the warp's approximate transformer segments follow the output
window).  Every chunk now warps the SAME box on the same grid (GDAL warps
each source over its own window of that output), and only the fill is
restricted to holes: byte-identical on both cells.

**A4 — one cold tile, +47+007 (lane-local Elevation_data, one run,
network-bound, concurrent with the closing build):** 16 insets in 164 s
(184 MB — this run carried R2's trimmed boxes; the shared cache's insets
total 1.53 GB) and 60 ring cells in 618 s.  The 2026-10-25 app build of
the same tile spent 13,084 s in its vector step (16 insets + 60 rings
fetched, three tiles at once).  Border cells gain least: where the newest
swissALTI3D vintage is nodata (France), every older vintage under the hole
is still read.

**A2 — R2, the cached insets CROPPED to the trimmed box (same pixels),
tile composed twice (`compose_tile_dem_from_disk`), all 14 inset airports
of +47+007:** inside boundary + 305 m, **0 nodes changed** at every
airport (LFSB 132,024 nodes, max |Δ| 0.000 m).  Between the trimmed box
and the old 2 km box the 10 m ring replaces the inset: p99 0.85–3.4 m at
the Swiss and German airfields — **but at LFSB 6,196 nodes and at LFGB
2,791 nodes fall to 0 m** (p99 157–163 m, max 315 m).  Attribution: the
base `N47E007.hgt` carries 0.215 % voids (one inside LFSB), the DEM load
fills them "to zero" when they are too many to interpolate, and the ring
cells over France come from SWISSALTI3D (its coverage box spans the tile;
it has no data in France), so nothing covers the voids once the inset
stops at 465 m.  Today the same craters stand beyond 2 km.  R2 therefore
waits for an owner call: (i) trim anyway; (ii) fill base voids first (an
interpolating or fallback fill instead of "to zero"); (iii) trim only
where the base has no void under the trimmed-away annulus.  Recommended:
(ii), which also removes the craters that stand beyond 2 km today.
Side note: the flat-site read of EDTG moved 4.13 → 4.15 m relief under the
crop (decision and Z0 unchanged).

**Closing build** — LFSB through `build_airport.py LFSB --refresh-data dem`
(the scope the harness named: per-version re-ask of no-coverage negatives),
`LFSB_20261026T194640`, rc 0, created 413.6 s, wall 493.4 s; census law-true
1,150, adjudicated 579 (airside 283, groundside 295, mixed 1).  R1/R3/R4
change what a fetch READS, not what is cached, so this build bakes the same
rasters as main.

**A3 not run** (a fresh R1 inset vs a fresh plain inset at 0.5 m): A1 is
byte-identical on both strategies and the chunk fill is resolution-blind;
the same comparison at inset resolution is owed.
