# Local imagery on demand: placeholders, fetch near the aircraft, storage cap (#1992)

Status: SPEC DRAFT, 2026-11-09 (lane `l1992`). Not ratified. No engine code
changed. Parts marked **[E2]** depend on the owner's swap-test sim read (§2);
everything else stands whatever E2 shows.

Owner, #1992 (2026-11-09T19:33Z): users still select the tiles they build
mesh and grading for, "but we'd only download low res placeholder imagery.
The goal would be enabling global coverage with a user definable storage cap.
Images that haven't been used in a while could be automatically downgraded
back to low res to stay within the cap and make room for new imagery."

Background: `docs/specs/dynamic-scenery-exploration-20261109.md` (#1986,
branch `claude/l1986-dynamic-scenery`) §2.4, §3.3, §6.1 and E2. Hosting is
deferred; this is the local step.

Tags: **[measured]** this machine or this repo, **[source]** a cited page,
**[estimate]** worked out here.

---

## 1. Summary

| Part | Decision |
|---|---|
| Build | Steps 1-3 unchanged. Step 4 encodes the DSF and `.ter` files as today, and writes a **placeholder DDS** under every texture's own name: the same square at `zl - 3` (ZL13 for a ZL16 square: 512 px, 4 map requests instead of 256, ~175 KB BC1 with mips). Water masks, `.ter` files and the DSF are unchanged (§3). |
| Refine | An engine job reads the aircraft position from **X-Plane's Web API** (`localhost:8086`, 12.1.1+, no plugin), fetches full-resolution textures for the squares ahead of and around the aircraft through the existing download and convert path, and **lands each one over its placeholder with `os.replace`** (§4). |
| Measure "used" | **Not file access time** (APFS does not advance it after the first read, measured §5.2). A texture is used when the aircraft comes within the refinement radius of its square: the follow job writes `last_near_at` into the cache index (§5). |
| Cap | A user-set cap (GB) on the full-resolution bytes of on-demand tiles. Over the cap, the least recently near textures are **downgraded**: the placeholder is landed back over the full texture and the full texture's JPEG and DDS-cache entry are freed (§6). |
| Settings | Imagery: on/off. Storage: the cap and a "make all low-res again" action. Both apps, same rows (§7, #1244). |
| Offline | Placeholders always stand: every texture name always resolves to a whole DDS. No network means the scenery stays low-res, nothing breaks (§8). |
| Reuse | The fetcher, converter, DDS cache, atomic land, held-file retry, disk accounting and Storage machinery all exist (§9). New: one placeholder writer, one follow job, one index, one downgrade sweep, one Web API reader. |
| Depends on E2 | Placeholder pixel size, swap timing (lead distance), whether a scenery reload or a virtual filesystem is needed (§2.3). |

## 2. The E2 swap test and what each result implies

### 2.1 The test

Kit: `/Users/noah/XPTerrainBuilderData/.harness/frames/l1992/cyxy-swapkit/`
(registered with `frames.py`; CYXY tile `+60-136`, built once at main
25cd0ff1b with the owner's provider Arc, ZL16; 288 ZL16 squares plus 20 ZL18
airport-cover squares). Three sets of the same 308 texture names: `full` (as built), `small` (16x smaller per side, 256 px: the
full texture's own mip 4 and below, re-headed, no re-encode), `blur` (full
4096 px size and byte size, every level above 256 px replaced by solid
blocks of the 256 px image). `swap.py` lands one set over another for all
squares or for the squares within N km of a point or of the aircraft (Web
API), atomically per file, and logs each swap with its UTC time.

Two runs answer two different questions:

- **Run S (small placeholders)**: does X-Plane pick up a file whose
  **header changed** (256 px to 4096 px) on its next paging reload?
- **Run B (blur placeholders)**: if S shows nothing, does X-Plane pick up a
  **same-size** file whose pixels changed? (Separates "re-reads the file but
  keeps the first header's size" from "never re-opens the file".)

### 2.2 What the documentation says [source]

- `.ter`/`.pol` `LOAD_CENTER`: "X-Plane will reduce the resolution of the
  texture as you fly away from that point", and "causes X-Plane to reload the
  textures while you fly"; DDS is recommended because the smaller versions
  are pre-computed in the file, so a low-resolution reload is fast
  (developer.x-plane.com, "Three Things You Need for Fast Orthophotos",
  2011; "DDS Revisited in X-Plane 10", 2012; "Limits on Texture Paging",
  2008: paging "happens on threads").
- Nothing Laminar published says whether a reload re-opens the file, reads a
  copy held in memory, or re-reads the size from the header.
- Indirect evidence that reloads go back to the FILE: AutoOrtho's FUSE
  filesystem sees X-Plane "pull open and read in DDS files as you go. Often
  more than once" (AutoOrtho docs/forum); xearthlayer's notes (issue #343)
  record "small mips read first and larger levels tens of seconds later" and
  that "tiles keep the resolution they were loaded with until X-Plane reloads
  them". The same notes say a virtual DDS's size "cannot change while the
  file is in use", and warn that degraded data served once is kept "for the
  flight" until the next reload.
- XP 11.50+ also pages textures by VRAM pressure (developer blog, "All your
  VRAM is belonging to us", 2020), a second reload path.

So the documentation predicts that a swap shows **at the next reload of that
texture at a different resolution**, not instantly, and leaves open whether
a changed header size is honoured. E2 is still needed.

### 2.3 Outcomes and what each implies

| E2 result | Implication for this spec |
|---|---|
| **S shows sharp imagery** on approach after the swap (no restart) | The spec as written: small placeholders (§3), plain files, no filesystem on any OS. The lead distance (§4.3) is set from the measured delay. Repeat on Windows once (rename over an open file, §4.4). |
| **S nothing, B shows** | X-Plane re-reads pixels but keeps the first size. Placeholders must carry the **full pixel size**, so a placeholder costs as much disk as the full texture (11 MB at 4096 px BC1) unless the filesystem compresses it: macOS transparent compression (`decmpfs`) or NTFS compression on Windows. A `blur` placeholder gzips to 383 KB of 11.2 MB [measured: kit]; `ditto --hfsCompression` did not set the compressed flag on a first try, so the OS-compressed size is unmeasured. The cap still works (downgrade = write the blocky placeholder back, compressed); the "global coverage" budget becomes the compressed size. |
| **Neither, but shows after Developer > Reload scenery** | Plain files work only with a reload. `XPLMReloadScenery` from a plugin stalls the sim for seconds, so swaps would be batched at a moment the user chooses (on the ground, before departure: "make the route sharp"). The in-flight loop becomes a virtual filesystem per OS (#1986 §6.1: FSKit, WinFsp, libfuse3). Placeholder build mode, index, cap and settings in this spec still apply. |
| **Shows, with stutter or `Log.txt` errors** | Swap only outside X-Plane's high-resolution radius (land textures before they page up), and rate-limit swaps per second. |
| **Shows within seconds even at close range** | No lead needed beyond the download time; refine radius can be small. |

## 3. Placeholder build mode

### 3.1 What changes in step 4

Setting `imagery_on_demand` (§7) on, `texture_mode` `full_ortho` or
`airport_ortho`:

- `O4_DSF_Utils.build_dsf` names textures and queues them as today
  (`download_queue.put(texture_attributes)`). The DSF, the `.ter` files
  (`create_terrain_file`: `LOAD_CENTER <lat> <lon> <m> 4096`,
  `BASE_TEX_NOWRAP ../textures/<y>_<x>_<prov><zl>.dds`) and the water and
  airport masks are **byte-identical to a full build**: none of them reads a
  pixel [measured: code, #1986 §3.1/3.3]. The `.ter` 4096 is a paging hint,
  not a size check (AutoOrtho ships 4096 and serves 8192) **[E2 confirms]**.
- The download worker fetches the square at `pzl = zl - placeholder_zl_drop`
  (default 3): the same 16x16-tile square at ZL16 is a 2x2-tile square at
  ZL13, 512 px. `O4_Imagery_Utils.build_texture_from_tilbox` already builds
  a texture from any tile box at any zoom; the placeholder is that call with
  the box scaled by `2**-drop`. Requests per texture: 256 at full, 4 at
  drop 3, 1 at drop 4.
- The converter (`convert_texture`) runs unchanged on the placeholder image:
  colour filter, harmonization field, mask imprint (the mask resized to the
  placeholder size) and sea fill all apply, so a placeholder and its later
  full texture are processed the same way. Its output lands under the full
  texture's name through `O4_DDS_File.land`. A placeholder is **not** stored
  in the content-keyed `DDS_cache` (it would compete with full textures for
  that cache's 20 GB cap); it is kept in the placeholder store (§6.2).
- The placeholder JPEG lands in the imagery cache under its own zoom
  (`Orthophotos/.../<prov>_13/`), where any later build at that zoom also
  finds it.
- Airport cover textures (`cover_airports_with_highres`, ZL17/18) get
  placeholders the same way (ZL15 for ZL18).
- If **[E2]** rules full-size placeholders, the writer instead expands the
  `pzl` image to the full pixel size with solid blocks (the kit's
  `make_placeholders.py` `blur` path) and asks the OS to compress the file.

### 3.2 Colour harmonization

The field (`O4_Imagery_Utils.solve_color_field`) is solved from seam-strip
statistics of 512x512 thumbnails (`O4_Color_Harmonization.THUMBNAIL_SIZE`,
decoded at 1/8 from a 4096 JPEG). A ZL13 placeholder JPEG **is** a 512x512
image of the same square, so the field is solved from the placeholders at
build time and **persisted and frozen** (`color_field_path(tile)`); full
textures arriving later read the frozen field and never re-solve it. A
re-solve mid-flight would shift every placeholder's neighbours and draw new
seams (the OTHH seam precedent, memory "Color harmonization mints seams").

### 3.3 Size [estimate]

| Placeholder | per texture (BC1, mips) | per 1° tile at lat 60 (308 textures) | 18,500 land tiles (median 234 textures, #1986 §6.1) |
|---|---|---|---|
| drop 4 (256 px) | 44 KB [measured: kit] | 13.5 MB | 190 GB |
| drop 3 (512 px, default) | 175 KB | 54 MB | 0.76 TB |
| drop 2 (1024 px) | 700 KB | 215 MB | 3.0 TB |
| full ZL16 (4096 px) | 11.2 MB [measured: kit] | 3.4 GB | — |

Plus the DSF and masks per tile (#1986 §4.3). "Global coverage" at the
default is about 0.76 TB of placeholders before any full texture; drop 4
makes it 190 GB. The placeholder drop is an expert setting; the default is an
owner question (§12).

### 3.4 Step reuse and the tile record

- `O4_Step_Reuse`: `imagery_on_demand` and `placeholder_zl_drop` enter the
  step-4 inputs, so toggling them re-runs step 4 only (DSF encode ~27 s,
  #1986 memory "DSF encoder 16-min premise false", plus the placeholders).
- The tile's imagery record (`Ortho4XP_<tile>_imagery.json`,
  `O4_Tile_Utils`) gains `"on_demand": true` and `"placeholder_zl"`; the
  Library shows such a tile as "Low-res, sharpens in flight".
- A tile bundle (`src/tile_bundle`, #1699) imports into a placeholder build
  with no change: the bundle carries no imagery by design.

## 4. Fetch near the aircraft

### 4.1 Where it runs

In the engine (owner standing: the engine owns cross-platform features), as
a long-running job the apps start and stop, like a Library job:
`imagery_follow_start` / `imagery_follow_stop` JSONL commands and a
`ImageryFollowStatus` event (class name = wire name; the Swift client
matches it as a string literal, `OrthoEngineClient.swift`). It never runs
during a build of the same tile (the converter and the build would race on
`textures/`; the job pauses while `library.start` holds the build lock).

### 4.2 Position

`GET http://localhost:8086/api/v2/datarefs?filter[name]=<ref>` once for
each dataref id, then `GET /api/v2/datarefs/<id>/value` at 1 Hz, or one
WebSocket subscription on `ws://localhost:8086/api/v2` (both since X-Plane
12.1.1, enabled by default on localhost) [source: developer.x-plane.com
"X-Plane Web API"; measured 2026-11-09: the kit's `swap.py follow` read
latitude, longitude, elevation and AGL from the owner's running X-Plane 12
on this Mac with these calls, no setup]. Datarefs: `sim/flightmodel/position/latitude`,
`.../longitude`, `.../elevation`, `.../y_agl`, `.../groundspeed`,
`.../true_psi`. The port is an expert setting (`xplane_web_api_port`,
default 8086; X-Plane can be started on another). No plugin. The kit's
`swap.py --sim` uses exactly these calls.

### 4.3 What to fetch first

- The index (§5) knows every on-demand texture and its square's centre
  (from its name, `O4_Geo_Utils.gtile_to_wgs84`).
- Candidate set: squares within `R` of the aircraft or of its position
  `T` seconds ahead along track (`T = 120 s`), where
  `R = refine_radius_km` (default 12 km) **[E2: R and T are set from the
  measured swap delay and from where X-Plane pages a texture to full
  resolution]**.
- Priority: time to reach the square (along-track distance / groundspeed),
  then lateral offset. Airport cover squares (ZL17/18) only below
  3,000 ft AGL within 5 km of the airport (AutoOrtho Continued's altitude
  steps are the precedent).
- Above ~FL150 the job refines nothing new (X-Plane shows ZL16 detail only
  at low resolution from there) **[estimate; E2 may move it]**.
- Throughput need [estimate]: at 250 kt (7.7 km/min) a 24 km wide swath
  sweeps ~185 km²/min, two ZL16 squares a minute at the equator (96 km²
  each) and about eight at 60°N (24 km² each). One texture is 256 map requests, about 1-3 s at
  the rates the fetcher reaches today. The job is idle most of the time.

### 4.4 Fetch, convert, swap

- One texture at a time per provider by default (`O4_Imagery_Prefetch`'s
  `TEXTURES_IN_FLIGHT = 1` precedent), through the same fetcher a build uses
  (`O4_Imagery_Fetch`: AIMD window, `Retry-After`, per-host budget shared
  across processes; `O4_Imagery_Utils.host_request_limit`,
  `provider_max_threads`). The provider's own throttling therefore holds
  exactly as in a build; nothing on-demand asks harder than a build.
- `download_jpeg_ortho` (full zoom), then `convert_texture` with the tile
  object: it lands the DDS over the placeholder through `O4_DDS_File.land`
  (`os.replace`, the atomic step; on Windows `O4_Held_File` retries while
  another process holds the file) and stores it in the content-keyed
  `DDS_cache` (hard link).
- On macOS and Linux, `os.replace` over a file X-Plane has open is legal;
  X-Plane keeps reading the old inode until it reopens. On Windows the
  rename is refused while X-Plane holds a handle **[E2: repeat the swap test
  once on Windows; if X-Plane holds handles for the whole flight, the swap
  must wait for the texture to page out]**.
- A swap is logged (`logs/imagery_on_demand.log`) and counted in the status
  event: textures sharp nearby, queued, failed, bytes used against the cap.

## 5. The cache index and "last used"

### 5.1 The index

SQLite (standard library `sqlite3`, WAL) at
`<data folder>/Imagery_on_demand/index.sqlite`, one row per
(tile, texture name):

| column | meaning |
|---|---|
| `tile`, `name`, `zl`, `provider` | identity (the texture's file name) |
| `centre_lat`, `centre_lon` | from the name |
| `state` | `placeholder`, `queued`, `fetching`, `full`, `failed` |
| `placeholder_path` | the kept placeholder DDS (§6.2) |
| `full_bytes` | freeable bytes of the full texture (`O4_Disk_Usage.freeable_bytes`: a hard link counts once) |
| `dds_cache_key`, `jpeg_path` | what a downgrade frees |
| `fetched_at`, `last_near_at`, `near_count` | for the LRU |

The index is a cache of facts on disk: a rebuild walks the on-demand tiles'
`textures/`, reads each DDS header (`O4_DDS_File.split_levels`: width 512
= placeholder, 4096 = full) and restores every column except `last_near_at`
(set to the rebuild time, so nothing is downgraded by a lost index).

### 5.2 Why not file access time [measured 2026-11-09, this Mac]

APFS on `/System/Volumes/Data` updates `atime` on a read only when it is
older than `mtime`: a file read after it was written gets one `atime`
update, and every later read leaves it unchanged (measured: atime set to
2026-01-01 with mtime 2025-12-01, then read: atime stayed 2026-01-01).
Windows has last-access updates off on most volumes, and Spotlight, backup
and antivirus reads would count as "use" where it is on. `atime` also
cannot tell a texture X-Plane read at 1/16 resolution from 30 km away
from one the pilot flew over.

### 5.3 The measure

A texture is **used** when the aircraft comes within `R` of its square
(the same radius that refines it) while the sim is running and not paused.
The follow job writes `last_near_at = now` for those rows at most once a
minute, and `near_count += 1` once per approach. The LRU sorts by
`last_near_at`. This is the sim's own position, measured, not a guess from
the filesystem, and it is what "used" means to the pilot: flown near.

## 6. Storage cap and LRU downgrade

### 6.1 What counts against the cap

`imagery_on_demand_cap_gb` (§7) bounds the freeable bytes of everything a
downgrade would free: full DDS in on-demand tiles' `textures/`, their
`DDS_cache` entries and their full-zoom source JPEGs. Placeholders, DSFs,
masks and normally built tiles do not count. With hard links (DDS cache to
`textures/`) a texture counts once (`O4_Disk_Usage.freeable_bytes`).

### 6.2 Downgrade

1. Pick rows `state = full` by oldest `last_near_at`, skipping any square
   within `2R` of the aircraft when the sim is running and any texture
   landed in the last hour (`storage.IN_FLIGHT_SECONDS`).
2. Land the kept placeholder over the full texture: hard link the
   placeholder store's copy beside it under a partial name, then
   `O4_DDS_File.land` (the same atomic step as an upgrade).
3. Free the full texture's `DDS_cache` entry (only when no other build dir
   holds it: `O4_DDS_Cache.held_by_built_tiles`) and its full-zoom JPEG.
4. Log the line in `logs/storage.log`, as every Storage deletion is.

Until the total is at most 90 % of the cap (hysteresis, so a flight does not
downgrade and refetch at the boundary). It runs at app launch, after a
follow session, and during one when the total passes 110 % of the cap.

The placeholder store (`Imagery_on_demand/placeholders/<tile>/<name>.dds`)
keeps one copy of each placeholder, so a downgrade needs no network and no
conversion. The tile's `textures/` copy is a hard link to it when the
texture is low-res: no extra disk.

### 6.3 With the existing Storage machinery

`o4_engine/storage.py` gains one store, `ondemand` ("Sharp imagery near
flown areas"), sized by `storage_scan`. Its clear action is a **downgrade of
everything**, never a deletion: deleting would leave textures missing. The
existing `imagery` and `dds` cache caps (`storage_cache_caps_gb`) must skip
files the index marks `full` (their LRU would otherwise delete the source of
a sharp texture and the downgrade would later miscount); the `_remove_redundant`
sweep already skips DDS entries other tiles hold.

`O4_Imagery_Freshness.discard_tile_imagery` ("Update Imagery") downgrades an
on-demand tile to placeholders and refreshes the placeholders.

## 7. Settings, both apps (#1244)

Mac: `Sources/XPTerrainBuilder/SettingsLayout.swift` rows; Qt: the same
settings through `O4_Qt_Settings*.py`; registry in `O4_Cfg_Vars.py` (types,
defaults, hints). Same rows, same order, same pane, in the same PR.

| Key | Pane | Row text | Default |
|---|---|---|---|
| `imagery_on_demand` | Imagery (`.app`) | "Download sharp imagery only near the aircraft?" Summary: "New builds get low-resolution imagery; full detail is fetched while you fly and kept within the storage limit." | off |
| `imagery_on_demand_cap_gb` | Storage | "How much space may sharp imagery use (GB)?" | owner question (§12); 50 proposed |
| `placeholder_zl_drop` | Imagery, expert | "Low-res imagery detail (zoom levels below the build's)" | 3 |
| `refine_radius_km` | Imagery, expert | "Sharpen imagery within (km)" | 12 **[E2]** |
| `xplane_web_api_port` | Speed & Downloads, expert | "X-Plane Web API port" | 8086 |

Storage pane: the `ondemand` store row with its bytes and the action "Make
all low-res again" (one confirmation naming the space freed). Main window:
a status line in the activity area while following ("Following X-Plane: 14
sharp nearby, 2 downloading"); if it adds a toolbar item, the
`test_qt_layout_parity.py` manifest gains it in both apps.

The job starts automatically when `imagery_on_demand` is on, the app is
open, and the Web API answers; it can be paused from the status line.

## 8. Offline and failure behaviour

- **Invariant:** every texture name of an on-demand tile resolves to a whole
  DDS at all times (placeholder or full). Every write is a land of a whole
  file; nothing deletes a texture name.
- No network: the fetcher's connect failures pause the job (existing AIMD
  pause, then a 60 s retry); the status says "Offline: imagery stays
  low-res". X-Plane flies normally on placeholders.
- Provider refuses (429, quota, terms): the fetcher's own back-off; a
  texture that fails three times is marked `failed` and retried next
  session.
- X-Plane not running, or the Web API off: the job idles and says so.
- App quits mid-fetch: a partial DDS never has the final name
  (`O4_DDS_File.partial_name`); the next start sweeps partials and resets
  `fetching` rows to `queued`.
- Before a flight with no network en route: "Make sharp now" on a map
  selection (Library/Map) fetches a chosen area without a position, under
  the same cap.

## 9. What it reuses (`tools/blast.py --find`)

| Need | Existing |
|---|---|
| Texture names, square geometry | `O4_File_Names.dds_file_name_from_attributes` [shared 5], `jpeg_file_name_from_attributes`; `O4_Geo_Utils.gtile_to_wgs84` |
| Texture list of a built tile | `O4_Imagery_Prefetch.candidates` (reads `terrain/*.ter` names) |
| Download at any zoom | `O4_Imagery_Utils.download_jpeg_ortho`, `build_texture_from_tilbox` |
| Provider throttling | `O4_Imagery_Fetch` (AIMD, `Retry-After`, budget), `host_request_limit`, `provider_max_threads` |
| Convert, mask, harmonize | `O4_Imagery_Utils.convert_texture`, `solve_color_field`, `color_field_path` |
| Atomic land, partials | `O4_DDS_File.land`, `partial_name`, `sweep_partials`, `is_whole`, `split_levels`, `assemble` [shared 2-3] |
| Windows rename over a held file | `O4_Held_File.retrying_a_held_file` |
| Content-keyed DDS store | `O4_DDS_Cache.serve`, `store`, `held_by_built_tiles` |
| Bytes a delete frees | `O4_Disk_Usage.freeable_bytes` |
| Storage rows, LRU, log | `o4_engine/storage.py` (`STORES`, `_evict_to_cap`, `storage_auto_clean`, `logs/storage.log`), `O4_Qt_Settings_Storage.StorageSection`, `StorageSettingsView.swift` |
| Step reuse | `O4_Step_Reuse` |
| Mesh without imagery | `src/tile_bundle` (#1699) |

New (one module each): `O4_Imagery_Placeholder` (the placeholder writer),
`o4_engine/imagery_follow.py` (the job), `O4_Imagery_OnDemand_Index` (the
index and its rebuild), `o4_engine/imagery_downgrade.py` (the sweep),
`O4_XPlane_WebAPI` (position reader, standard library).

## 10. Imagery terms

On-demand fetching changes **when** a texture is downloaded, not what or
from where: the user's machine fetches from the provider exactly as a build
does today, and keeps the result in the same caches. A provider whose terms
limit caching (Google Map Tiles: no caching beyond `Cache-Control`, #1986
§6.2) is no more and no less allowed here than in a build. The downgrade
makes the cache smaller, never larger. Nothing is redistributed.

## 11. Parts that depend on E2

| Part | Depends? |
|---|---|
| §3 placeholder build mode, masks, `.ter`, harmonization, step reuse | No (pixel size of the placeholder: yes, §2.3 row 2) |
| §4.2 position from the Web API | No |
| §4.3 radius, lead time, altitude cutoff | **Yes** |
| §4.4 swap by `os.replace` while flying | **Yes** (and the Windows repeat) |
| §5 index and "used" | No |
| §6 cap and downgrade | No (the downgrade is the same swap in reverse; its timing is §4.4's) |
| §7 settings, §8 offline | No |
| A virtual filesystem | Only if E2 row 3 |

## 12. Owner questions

1. Default cap (50 GB proposed) and default placeholder detail (drop 3 =
   512 px, ~0.76 TB for every land tile; drop 4 = 256 px, ~190 GB).
2. App-wide switch, or per tile (a tile set built "on demand" beside fully
   built tiles)?
3. Start following automatically when X-Plane runs, or only on a click?

## 13. Work items, in order

1. E2 sim read (owner, kit ready). Then fix §4.3/§4.4 numbers.
2. `O4_Imagery_Placeholder` + step-4 switch + step-reuse inputs; twin:
   a placeholder build's DSF, `.ter` and masks byte-identical to a full
   build's (`tools/tile_bundle_gate.py` style), placeholders whole and
   512 px.
3. Index + rebuild; twin from a synthetic `textures/` folder.
4. Web API reader + follow job + events (wire names in Swift in the same
   PR); twin with a fake Web API server on a local port.
5. Downgrade sweep + Storage store row; twin: cap honoured, invariant held
   (every name whole), nothing near the aircraft downgraded.
6. Settings rows, both apps; parity twin.
7. One CYXY closing build, owner sim read of the full loop.
