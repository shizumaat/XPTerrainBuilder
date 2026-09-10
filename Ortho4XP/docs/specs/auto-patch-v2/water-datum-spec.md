# WATER IS A DATUM — the water witness, the inset cut-out, the mesh precedence

Owner law: RULINGS **2026-09-09m** ("the water is weird with a sharp cliff at
the land/water border and some water being lifted up to terrain level instead
of staying at about 4 m below the bridge levels").  Attribution and the four
rulings this spec implements: **2026-09-09o** (scout `othhwater`).  Adjacent
law: 05k (the flat-site datum), 08f (the seats already gate on water), 09g
(the daylight foot), 09j/09l (the bank).

Lane `v2water` implements (1), (2), (3).  Ruling (4) — the SHORE BANK in
`emit/bank.py` — is the NEXT round (`emit/bank.py` is held by `v2bankmesh`).

---

## 0. What is wrong (measured, 09o)

* No patch vertex stands on water at OTHH (0 of 43,410; nearest 2.77 m).  The
  canal is a **Z0 PLATEAU** baked into the DEM by the flat-site inset's
  constant-Z0 **bbox** — `Data+25+051.alt` reads 3.962 m over 80.7 % of the
  airport bbox, canal and ≈ 1 km of open sea included.
* The mesh then **exempts** those water triangles from sea levelling:
  `O4_Mesh_Utils.post_process_nodes_altitudes` tests `attr >= INTERP_ALT`
  FIRST, so a triangle the patch's INTERP_ALT seeds reached comes out attr 10
  (`SEA|INTERP_ALT`) and copies the DEM's plateau instead of levelling to 0.
  Result: 1,692 of 2,197 water triangles carry a one-triangle 3.962 m step;
  every water vertex in the frame is exactly 0.000 (699) or 3.962 (782),
  interleaved along the canal at 0.9 m.
* The v2 production frame has **no water concept**: `is_water` exists only
  POST-mesh (`emit/rebake.py`), so the bank cannot daylight at a shore
  (9,436 rays at the minimum, 7 daylighted).

## 1. THE WATER WITNESS — one derivation site

### 1.1 The reader (never a private copy)

`O4_Vector_Map` gains **one** cache-only reader beside the coastline's:

    cached_water_multipolygon(tile)   # inland water, tile-relative
    cached_tile_water(tile)           # (sea, inland), memoised on the tile

`cached_tile_water` composes:

* **sea** = `sea_area_from_coastline(cached_coastline_multilinestring(tile))`
  — the SAME two functions `overlay_flat_site_insets`' R21 island law and
  `include_sea` already use ("the SEA/LAND partition has exactly ONE
  implementation in the tree", `sea_area_from_coastline`'s own docstring);
* **inland** = the tile's `WATER_QUERIES` layer through
  `OSM.OSM_queries_to_OSM_layer(..., cached_suffix="water",
  cache_schema=WATER_CACHE_TAG_SCHEMA)` → `OSM.OSM_to_MultiPolygon` — the
  same layer, queries, tags and schema `include_water` and `_tidal_water_area`
  read, i.e. the layers the mesh's masks are built from.

**CACHE ONLY, never a download** (the shared-repo write guard, and
`cached_coastline_multilinestring`'s own reason): the file must exist and its
schema must match, else the answer is "no data" — `(None, None)` — said out
loud by the caller, never fetched.  `None` ≠ empty: no data is not "no water".

Measured on the corpus for +25+051 (read-only): coastline 222 ways → sea
0.4434 deg², water layer 703 polygons → 0.005371 deg².  **The owner's canal
site (25.2557, 51.6168) is SEA**, not inland water.

### 1.2 The witness

`auto_patch_v2/airport/dem_production.ProductionDem` gains, per 1° tile,
beside its baked raster:

    is_water(x, y) -> bool
    water_many(xs, ys) -> (is_water: bool[], level_m: float[])   # NaN off water
    water_state() -> dict          # provenance: source, counts, per-tile "no data"

Frame metres in, via the sampler's own inverse transformer, then the core's
tile-relative degrees.  Polygons are indexed in an `STRtree`; the query is
vectorised (`query(points, predicate="covers")`), never a per-point loop.

**THE LEVEL RULE** (stated once, here):

* a **sea** polygon (coastline-derived) → **0.0 m**, the datum the mesh's own
  `sea_smoothing_mode=zero` levels it to;
* an **inland body** (one polygon of the water layer, not covered by the sea)
  → **the median of the production DEM over that body's interior**, one level
  per polygon, computed lazily on first touch and cached.  Rationale: the
  engine's inland-water treatment (`tile.water_smoothing`) iterates a
  per-triangle mean, i.e. it converges the body to ONE level; the median of
  the body's own DEM cells is that level, robust to the bank cells the
  polygon edge clips.  It is read AFTER (2) cuts water out of the inset, so
  the plateau can no longer be the thing it measures.
* No water data on disk → the witness answers **False everywhere** and says so
  in the provenance.  A missing cache never invents water and never refuses
  the build (the frame's own cold checks own that class).

## 2. CONSUMER CENSUS (owner ruling 30l) — every pass reading ground geometry

Ruled in ONE table before any consumer is edited.  "Reads the witness" means
the pass reads it FROM `ProductionDem`; nobody re-derives water.

| # | Pass / file | What it reads today | Ruling for water | Edited this round |
|---|---|---|---|---|
| 1 | `constraints/water.py` (**new**) | — | THE PIN: a graded-strip (zone ring + gap-interior hole) vertex whose production sample is water gets a HARD `Linear` at the water level; it is not an unknown | YES (new) |
| 2 | `constraints/__init__.py` | stacks generators; `seam_exempt` post-pass | `water_exempt` post-pass, exactly parallel: every row GOVERNING a water-pinned vertex (`follows=v`, or every term pinned) is dropped, so a band cannot fight the pin | YES |
| 3 | `constraints/zones.py` `zone_bands` / `strip_transverse` | zone corridor rows on strip vertices | rows dropped by (2) — the pin is the vertex's own law, like `own_law` / `wall_vertices` | no (via 2) |
| 4 | `constraints/strips.py` (longitudinal, arc, RESA, end corridor, RAOA) | strip vertices | same, dropped by (2) | no (via 2) |
| 5 | `constraints/seams.py` | soft DEM pin per seam vertex | a seam vertex on water takes the WATER pin (hard) and its soft DEM row is dropped by (2) — after (2) the two values agree anyway | no (via 2) |
| 6 | `constraints/flat_site.py` `flat_datum` | `FlatVerdict.region` ∋ vertex → soft `z = Z0` | region no longer covers water (row 7), and a water-pinned vertex's row is dropped by (2) | no (via 7 + 2) |
| 7 | `airport/flat_site.py` `detect` | `region_polygon(airport, margin)` → `_rings(full)` | **the datum region is `full − water`** at its single derivation site, so every consumer of `FlatVerdict.region` (the datum rows AND the seats' `_Region` in `emit/rebake.py`) excludes water with no second rule | YES |
| 8 | `airport/flat_site.py` `dem_relief` | S2 relief over the core region | UNCHANGED — it already drops a sea band (`sea_band_max_m`) and the region cut only removes cells it would have dropped | no |
| 9 | `emit/rebake.py` seats | `sampler(lat,lon) -> (z, is_water)` post-mesh; `_Region.inside` | UNCHANGED — 08f already gates every seat on water; row 7 additionally keeps the datum region off water | no |
| 10 | `emit/bank.py` `daylight_feet` / level rings | `_dem_many(dem, ...)` | **NEXT ROUND** (09o (4)).  The hook is already in place: `daylight_feet` is handed the `dem` object, so the shore rule reads `getattr(dem, "water_many", None)` — no new plumbing, no second water source | no (owed) |
| 11 | `emit/graded.py`, `emit/osm_adapter.py` | solved z per vertex | UNCHANGED — a pinned vertex emits its pinned z like any other | no |
| 12 | `solve/design.py` / `solve/rows.py` | DEM objective, detached-body plane targets | UNCHANGED — a hard pin removes the vertex from the free columns by the existing reduction; no water term in the objective | no |
| 13 | `constraints/structures.py`, `planar/structures.py` | tunnel/basin/wall datums | UNCHANGED — a structure keeps its generator's datum (the same carve-out `flat_datum` makes); structure-role vertices are excluded from the pin candidate set | no |
| 14 | `verify/*` census (`no_step`, `adjacent_ground_tear`, `strip_seam_tear`, proximity pairs) | pairs over emitted vertices | a pin↔pin pair prices water against water and is EXEMPT (the seam-pin precedent); a pin↔free pair at the shoreline is the BANK's job (row 10) and is REPORTED, not exempted | no this round (reported) |
| 15 | `planar/zones.py`, `planar/build.py` | ring construction | UNCHANGED — water changes elevations, never plan geometry | no |
| 16 | `auto_patch/flat_site_mode.py` | the synthetic inset extent | **the inset is CUT** (§3) | YES |
| 17 | `O4_Airport_Elevation_Insets.overlay_flat_site_insets` | `_ConstantInset` over the feathered bbox | a `_MaskedConstantInset` over `bbox − water` when the tile has water data | YES |
| 18 | `O4_Airport_Elevation_Insets._bake_island_continuity` (R21 isthmus) | `_MaskedConstantInset` over measured LAND | UNCHANGED — its polygon is already land-only by construction | no |
| 19 | `O4_Mesh_Utils.post_process_nodes_altitudes` | triangle attributes | **water bit outranks the INTERP_ALT seed** (§4) | YES |
| 20 | `O4_Vector_Map` `PATCH_RING_MARKER` / seawall | ring marks | UNCHANGED — see §4.2 | no |
| 21 | `O4_Mask_Utils.water_type_is_inland`, `O4_DSF_Utils.remap_water_tri_type` | triangle attributes for texture/mask | UNCHANGED — §4 changes only the ALTITUDE treatment, never an attribute | no |

Trimming at the single derivation site over per-consumer vetoes (30l): rows
3–6 and 9 are governed by rows 2 and 7, not by edits of their own.

## 3. THE INSET CUT (ruling 09o (2))

One derivation site: `auto_patch/flat_site_mode.py`.

* `water_cutout(tile)` → the tile's `sea ∪ inland` as one tile-relative
  geometry from `O4_Vector_Map.cached_tile_water`, memoised per tile;
  `None` when no cache is on disk.
* Every substitution (the airport extent AND every claimed-object cluster)
  carries `"water_cutout"`: the cut-out geometry clipped to its own feathered
  rectangle, or `None`.
* `overlay_flat_site_insets` builds a `_MaskedConstantInset` over
  `feathered_rect − water` instead of `_ConstantInset` whenever that geometry
  is a proper subset of the rectangle.  Nothing else changes: the feather is
  still driven from the RECTANGLE's data edge (`_MaskedConstantInset` gains an
  explicit `bounds=` so a clipped corner cannot move it), and a nodata post is
  already exactly what `_bake_one_inset` means by "the base keeps its value".
  The mask edge is a hard step at the shoreline — the vertical sea wall the
  owner ruled a reclaimed edge is (R17b-2), not a beach ramp.
* An airport with no water in its rectangle bakes the identical
  `_ConstantInset` it bakes today (CYXY, HECA, LEMD: byte-identical).

**THE OWNER MUST REFRESH.**  The baked inset for this tile is CACHED in the
shared corpus, and this lane writes NOTHING there.  After the merge the owner
runs, once:

    venv/bin/python tools/harness/build_airport.py OTHH --tile 25 51 --refresh-data dem

Until that refresh the corpus inset still carries Z0 over water and the mesh
read will still show 3.962 water vertices from THAT source; (4) alone removes
the sawtooth's mesh half.

## 4. THE MESH PRECEDENCE (ruling 09o (3))

### 4.1 The change

`O4_Mesh_Utils.post_process_nodes_altitudes`, the classification at :805:

    ONE precedence line — a triangle carrying ANY water bit
    (WATER | SEA | SEA_EQUIV) is routed to sea/water levelling FIRST and
    is NOT added to interp_alt_tris; the INTERP_ALT branch keeps every
    triangle with no water bit, unchanged.

Inside the water branch the existing routing is verbatim: `SEA` without
`WATER` → `sea_tris` (inland water wins over coastline sea); `WATER` or
`SEA_EQUIV` → `water_tris`.  The `:968-970` copy of column 5 into the altitude
is untouched for non-water triangles.

Why this is safe against the `PATCH_RING_MARKER` design (`O4_Vector_Map:76`):
that law puts all four bits on the closed patch **ring**, so the flood STOPS
at the pavement boundary and the pavement interior keeps **bit 8 alone** —
segment marks never become triangle attributes.  Pavement is therefore never
water-bitted and is unaffected.  The triangles this reclassifies are exactly
the ones the ring failed to fence: open water an INTERP_ALT seed reached
(OTHH: 2,180 SEA|INTERP_ALT triangles, 13.7 km²).

### 4.2 Effect on the seawall

**The seawall stays marker-8-only** (`O4_Vector_Map:105-125`), unchanged.  Its
whole design is that the wall breakline carries INTERP_ALT and NOTHING else so
that "every water flood crosses it freely and the 0.5 m band between ring and
wall stays owned by the sea".  Under §4.1 that band's triangles — SEA-flooded,
now also seed-reached — go to sea levelling, which is precisely what the
seawall law says they are for: the water side of the wall sits at the water's
level and the drop happens over 0.5 m.  Before this change a seed that reached
the band froze it at the DEM and turned the wall back into the ramp it was
written to abolish.  No marker, offset or admission set changes.

## 5. TWINS

* `tests/auto_patch_v2/test_water_datum.py` — a synthetic frame with a canal
  polygon: zone/gap-interior vertices over it are pinned at 0.0 and are not
  unknowns; a band row on a pinned vertex is dropped; the flat-site datum
  region excludes the canal; an inland body takes its DEM median; no water
  data → no pins, no region change.
* `tests/test_flat_site_water_cutout.py` (engine suite) — a synthetic tile:
  `overlay_flat_site_insets` leaves the base DEM over a water polygon inside
  the flat bbox and writes Z0 beside it; with no water cache the bake is the
  pre-change constant bbox.
* `tests/test_mesh_water_precedence.py` (engine suite) — a synthetic
  Triangle4XP output whose water triangle carries `SEA|INTERP_ALT`: it levels
  to 0.0; a plain INTERP_ALT triangle still copies column 5.

## 6. BUILD-TIME IMPACT

The witness is built once per tile from two cached OSM layers already read by
the build (coastline: the R21 land law reads it; water: `include_water`
reads it) and queried through an `STRtree`; the pin generator is one
vectorised query over the graded-strip vertices.  Expected < 1 s at OTHH,
under the 1 % (0.6 s per-airport / 3 s per-tile) evaluation floor.  The mesh
change is a branch reorder: zero cost.  Measured at the closing OTHH build.
