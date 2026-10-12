# demfall561 — base elevation fallback when the configured source cannot be reached (#561)

## RESUME HERE

- Branch `claude/demfall561` (from `aed288725`), worktree `.claude/worktrees/demfall561`.
- Step 1 (census + design): DONE (`819589fd3`).
- Step 2 (implement + twins): DONE (`377340c51`).
- Step 3 (real fallback fetch into lane scratch, Viewfinder transport forced to fail): DONE, section 4.
- Step 4 (tests): DONE, section 5. Ratchets pass.
- Nothing left to do in this lane; open questions are in section 6.
- Scratch (lane-local, nothing was written to the shared corpus): the session scratchpad `dl/`,
  `glo/`, `elev/`, `elev_ref/`, `elev_time/`, `scripts/` (edge.py, vfp.py, real_fallback.py,
  time_fetch.py). NOTE: another lane of the same session wrote `suite.log` in that scratchpad while
  this lane's suite ran; this lane's result is read from its own run ledger, not from that file.

## 1. Census — base-tile strategies, callers, cache paths

Registry: `Providers/Elevation/<CODE>.elv`, `role=base`. Selection: `resolve_base_definition`
(`O4_Airport_Elevation_Insets.py:9186`), automatic ranking `select_base_definitions_auto` (enabled,
covering, >= 1 arc-second).

| CODE | strategy (file) | host | cache path | auto? | global? | usable as a fallback |
|---|---|---|---|---|---|---|
| VIEWFINDER3 | `viewfinder_zip` | viewfinderpanoramas.org `dem3/<zone>.zip` | `<block>/N48W123.hgt` (1201 sq) | yes, priority 10 (the default under `elevation_level` auto/90) | yes | no — the failing host |
| VIEWFINDER1 | `viewfinder_zip` | same host, `dem1/` | same path (3601 sq) | yes, priority 60, zone list only | 35 zones | no — the same host |
| NED1 | `usgs_seamless` | prd-tnm.s3.amazonaws.com | `<block>/N48W123_NED1.tif` (3612 sq) | yes, priority 70 | CONUS box | not global; a different grid |
| NED13 | `usgs_seamless` | same | `…_NED13.tif` | never auto | CONUS | no |
| SONNY1 | `hgt_archive_drop` | none (manual drop folder) | `…_SONNY1.hgt` | only where dropped | Europe | no — no download |
| SRTM | `manual_download` | none (dead upstream) | `…_SRTMv3.hgt` | disabled | — | no |
| ALOS | `manual_download` | none (dead upstream) | `…_ALOS3W30.tif` | disabled | — | no |
| COPERNICUSGLO30 (role=airport_inset) | `degree_named_cog` | copernicus-dem-30m.s3.amazonaws.com, one COG per cell | airport inset directory | — | global | YES — the only automatic global source the registry holds besides Viewfinder |

Callers of the base tier:

| site | what it does | cache path it reads |
|---|---|---|
| `O4_DEM_Utils.DEM.load_data` (:413) | global sources (`View`/`SRTM`/`ALOS`) -> `build_combined_raster`; others -> `ensure_elevation` + one file | `FNAMES.elevation_data(short_source, lat, lon)` |
| `O4_DEM_Utils.build_combined_raster` (:971) | 3x3 assembly, home 3601 sq + 36-post band from each neighbour (shared post skipped, `overlap=1`) | `FNAMES.elevation_data(source, lat0, lon0)` per cell |
| `O4_DEM_Utils._ensure_cell_elevation` (:950) | names the cell in a transport refusal | — |
| `O4_DEM_Utils.ensure_elevation` (:1221) | shim -> `ensure_base_tile` | — |
| `O4_Airport_Elevation_Insets.ensure_base_tile` (:9277) | resolve, file lock, `strategy.ensure_tile` | strategy `tile_cache_path` |
| `O4_Airport_Elevation_Insets.base_tile_is_cached` (:9244) | scheduler fetch-admission predicate, file system only | strategy `tile_cache_path` |
| `O4_DEM_Utils.is_cached` (:163) | the same over the 3x3 | via `base_tile_is_cached` |
| `O4_DEM_Utils.http_request` (:1338) | the one base transport: 6 tries, 10 s timeout, back-off 2+4+8+16+32 s | — |
| `auto_patch/provenance.dem_fingerprint` (:881) | airport freshness stamp `o4_dem` — with the default (empty) base token the base cell files are NOT in it | — |

## 2. Measurements (2026-10-12, this machine)

Transport (curl, into lane scratch):

| object | size | first byte | whole download |
|---|---|---|---|
| `viewfinderpanoramas.org/dem3/M10.zip` (x3) | 37.0 MB | 0.70–0.72 s | 46.4 / 56.7 / 84.0 s |
| `viewfinderpanoramas.org/dem1/O32.zip` | 112.7 MB | 0.67 s | 41.9 s |
| Copernicus GLO-30 `N48W123` / `N47W123` / `N48W122` | 32.1 / 39.8 / 43.9 MB | 0.6–0.7 s | 4.9 / 5.2 / 5.2 s |
| Copernicus GLO-90 `N48W123` / `N47W123` | 3.9 / 4.8 MB | 0.6 s | 1.9 / 2.0 s |

The 10 s in `http_request` is `requests`' per-read stall timeout (no byte for 10 s), not a cap on the
whole download: a healthy 46–84 s download passes it. The owner's failures were the server sending
nothing for 10 s, six times; the same log shows `ProxyError … Tunnel connection failed: 400 Bad Request`
on viewfinderpanoramas.org, tnmaccess.nationalmap.gov and an AWS S3 bucket in the same minutes, so the
owner's own proxy was also failing — a fallback on AWS helps when Viewfinder is down, not when the
local proxy is.

Edge, N47W123 / N48W123 (land posts only, metres; `scripts/edge.py`):

| comparison | mean | RMS | p95 | max |
|---|---|---|---|---|
| Viewfinder vs Viewfinder on the shared row lat 48 (N47 top vs N48 bottom) — the baseline today | — | 2.49 | — | 31 |
| same, N47W123 east vs N47W122 west / N46 top vs N47 bottom | — | 3.12 / 2.67 | — | 23 / 21 |
| GLO-30 minus Viewfinder, shared row lat 48 | +7.55 | 12.74 | 28.5 | 39.3 |
| GLO-30 minus Viewfinder, 36-post band north of 48 | +8.78 | 13.72 | 29.4 | 47.9 |
| GLO-30 minus Viewfinder, whole N48W123 | +7.48 | 12.87 | 27.0 | 116 |
| GLO-90 minus Viewfinder, shared row / whole cell | +7.57 / +7.43 | 12.40 / 12.49 | 27.6 / 26.2 | 37.3 / 119 |
| 0.1-degree block means of GLO-30 minus Viewfinder | min −0.57, max +20.6 | | | |

Reading: the difference is NOT the vertical datum (EGM2008 vs EGM96 is well under 1 m; open blocks
agree to −0.6 m). It is the surface model: Copernicus carries the forest canopy and buildings, the
Viewfinder tile here is bare-earth-like. An untied fallback cell beside a Viewfinder cell would step
12.7 m RMS / 39 m max on the shared row — five times today's Viewfinder-vs-Viewfinder 2.5 m. So an
edge tie is required, not optional. Voids: 0 in either Viewfinder cell; GLO has no nodata value and
no voids (water is flattened). Registration: GLO-30 is 3600x3600, pixel centres ON the arc-second
posts, north row and west column present, south row and east column in the neighbouring objects
(GLO-90 the same at 1200). Viewfinder dem3 is 1201x1201 with all four edges.

## 3. Design chosen

1. **Source: Copernicus GLO-30 first, GLO-90 second.** It is the only automatic global source in the
   registry besides Viewfinder; its access code (`DegreeNamedCogStrategy`: cell URL, existence probe,
   `/vsicurl/` warp) is reused. GLO-30 first because one file serves both base classes (1 and 3
   arc-second) and costs 5 s; GLO-90 second because it is a different bucket and an eighth of the
   size. Measured against Viewfinder the two are equal (RMS 12.9 vs 12.5 m).
2. **Registry:** two new definitions, `COPERNICUSGLO30BASE.elv` and `COPERNICUSGLO90BASE.elv`:
   `role=base`, `enabled=False` (so the automatic PRIMARY selection never takes them — the SRTM/ALOS
   precedent), and a new key `fallback_rank=1|2`. One new strategy file,
   `elevation_access/strategies/degree_cog_base_tile.py` (key `degree_cog_base_tile`), which writes a
   3601x3601 float32 GeoTIFF with its pixel centres on the hgt posts — the south row and east column
   come from the neighbouring Copernicus objects (replicated from the next row where a neighbour is
   absent). `warp_vsicurl_sources_to_geotiff` gains one optional parameter (`output_size`).
3. **Policy:** one new module `elevation_access/base_fallback.py`. `ensure_base_tile` calls it instead
   of the strategy directly. Order: valid cached configured file -> configured download -> (only on a
   TRANSPORT refusal after the retries: new subclass `ElevationTransportRefused`) the ranked fallbacks.
   A 404 / mapping defect (#173), a host refusal (403/407) and a redirect loop keep refusing. A host
   that just failed is not retried for the other cells of the same build (memo with a 10-minute life).
   If every source fails the refusal lists each source and its failure in plain words.
4. **Provenance rule: own cache path, configured source first, every build.** The fallback lands at
   `<block>/N48W123_<CODE>.tif`, never at the configured path. A reader takes the fallback file ONLY
   where the configured file is absent, so the next build tries the configured source again and, when
   it answers, the fallback file is simply never read again. Build hash: `dem_fingerprint` gains one
   line per substituted cell (`base_fallback:<cell>=<identity>`) ONLY when a cell is substituted —
   every existing stamp is byte-identical; an airport patch solved beside a fallback cell reads stale
   and rebuilds once the configured source is back. Build log: one plain line per substituted cell,
   every build that reads one.
5. **Seam: tie the fallback cell to its configured neighbours.** Where a 4-neighbour's configured
   file is cached and on the same post grid, the fallback cell's shared row/column is set to the
   neighbour's shared posts and the difference fades linearly to zero over 240 posts (4 arc-minutes,
   about 7.4 km at this latitude); sides are applied in a fixed order so both builds of an adjacent pair see the same
   array. Result on the shared row: 0 m against the neighbour's own edge (better than today's 2.5 m).
   Two adjacent fallback cells need no tie (one dataset, shared posts from the same objects).
6. **Timeout:** no change proposed to the 10 s stall timeout or the six tries (they are not what
   failed; a 37 MB zip downloads in 46–84 s under them). With the fallback the cost of a dead host is
   paid once per build (about 2 minutes), not per cell.

Not in this lane: `o4_engine/events.py` and `Sources/` (lane `failmsg562`); a fallback for the
airport-inset tier; a tie against neighbours on a different grid (NED1's 3612-square GeoTIFF).

OWNER QUESTION carried to the report: RULINGS 2026-10-02c keeps Copernicus GLO-30 (a surface model)
out of every wide-area use except approach ring 2; a base-tile fallback is a wide-area use. The issue
text of 2026-10-12 names GLO-30 as the candidate, which this lane reads as the owner's permission for
this one use — to be confirmed.

## 4. Step 3 — the real fetch (2026-10-12, `scripts/real_fallback.py`, `scripts/time_fetch.py`)

Lane-local elevation directory holding the corpus' Viewfinder cells around N48W123 WITHOUT
`N48W123.hgt`; `O4_DEM_Utils.http_request` replaced by a function raising the transport refusal.

- Tile 47/-123 (the owner's case, fallback NEIGHBOUR): built; Viewfinder asked once; cell +48-123
  taken from Copernicus GLO-30; the home tile's 3601x3601 interior is byte-identical to the
  all-Viewfinder build. Wall 23.6–25.2 s including the fetch.
- Cold fetch alone: GLO-30 tile 18–51 s (23.8 MB on disk), GLO-90 tile 16.4 s (20.4 MB). The tile
  equals the raw Copernicus objects post for post (max difference 0.0000 m), including the south
  row (from the N47 object) and the east column (from the W122 object). No voids.
- Shared row lat 48, fallback cell vs Viewfinder N47 (land posts): UNTIED mean +7.09, RMS 12.58,
  p95 28.2, max 52.0 m; TIED 0.00 / 0.00 / 0.00 / 0.00 m.
- Tile 48/-123 itself as the fallback cell (the reverse case): north and south edges equal the
  Viewfinder neighbours' shared posts exactly (0.00 m); west and east edges equal them except one
  corner post each (14 m and 13 m — the two Viewfinder neighbours disagree on that post; RMS over
  the edge 0.23 / 0.22 m). Interior vs Viewfinder N48W123: mean +6.56, RMS 12.65, max 133 m (the
  surface model; untied it is +7.25 / 12.77 / 133).
- Band beyond the tile edge (tile 47, the 36 posts north of lat 48), fallback build minus
  all-Viewfinder build: mean +1.34, RMS 10.68, max 55.4 m; the step from the edge row to the first
  band row is RMS 6.10 m (4.62 m all-Viewfinder).
- Log lines as printed:
  `Viewfinderpanoramas did not answer; asking Copernicus GLO-30 for elevation cell +48-123.`
  `Viewfinderpanoramas did not answer; elevation cell +48-123 taken from Copernicus GLO-30 instead
  (<path>/N48W123_COPERNICUSGLO30BASE.tif). Viewfinderpanoramas is asked again on the next build.
  Reason: the View elevation download of https://viewfinderpanoramas.org/dem3/M10.zip failed 6
  times on the transport (last: …)`
  `Elevation cell +48-123 (Copernicus GLO-30) tied to its south neighbour: edge difference up to
  52.0 m closed over 240 posts.`

## 5. Tests

- `tests/test_base_elevation_fallback.py` (new, 29 twins): policy, transport class, seam, read,
  fingerprint, shipped registry, the strategy, the warp's fixed grid.
- By changed files (14 files): 366 passed.
- Full non-Qt suite at `377340c51`: 9309 passed, 19 skipped, 1 xfailed, 1 xpassed, exit 0, 1146 s
  (run ledger key `bd21c01781f7…`).
- `tools/ratchets.py`: DUPLICATE RATCHET PASS, LAYER RATCHET PASS.

## 6. Changed after the design note, and open

- The package may not import the pipeline (`tests/test_elevation_access_registry.py`), so
  `base_fallback` takes the parsed registry as an argument; `O4_DEM_Utils.read_base_cell` is the
  reader's entry.
- `degree_cog_base_tile` imports `degree_named_cog` (cell names + existence probe): a FOURTH
  cross-strategy import, recorded in the twin's pinned set and the package docstring.
- A corner post belongs to two sides; the row tied first keeps it (section 4).
- Not done: a tile build; a tie against a neighbour on another grid (logged, not tied); the tile
  mesh is not rebuilt by itself when the configured source returns (only airport patches are, through
  the fingerprint); two stacked fallback cells beside one configured cell keep a small residual near
  the shared corner; the GUI tile-info summary does not show a substituted cell.
