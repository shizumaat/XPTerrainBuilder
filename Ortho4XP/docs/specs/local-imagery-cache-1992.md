# Local imagery on demand: placeholders, tiered fetch near the aircraft, storage cap (#1992)

Status: SPEC DRAFT **rev 2**, 2026-11-10 (lane `l1992d`, on lane `l1992`'s
2026-11-09 draft). Not ratified. No engine code changed. Rev 2 folds in the
E2 swap tests, the two recorder flights and the owner's decisions of
2026-11-10. Blocks that changed or are new carry **[rev 2]**. Rev 1's
**[E2]** markers are resolved and removed (§2.6 says where each one went).
§11 lists what is still unknown and how to test it. §14 is the
implementation plan.

Owner, #1992 (2026-11-09T19:33Z): users still select the tiles they build
mesh and grading for, "but we'd only download low res placeholder imagery.
The goal would be enabling global coverage with a user definable storage cap.
Images that haven't been used in a while could be automatically downgraded
back to low res to stay within the cap and make room for new imagery."

**[rev 2]** Owner decisions, #1992 (2026-11-10T00:41Z and 04:12Z): cap
default **100 GB**; placeholder default **512 px** ("512 as default makes
sense", superseding the 256 px of 00:41Z, after flight 2); **one world
on/off** plus per-tile **"always full resolution" pins**; imagery **loads
automatically within visible distance** of the aircraft; users **still
select the tiles or regions** they build (mesh and grading), and imagery
for them is fetched on demand; providers are the user's choice, as today.
Hosting is deferred (#1986). Owner design answer (2026-11-09T20:08Z): on a
spawn or jump, fetch the airport core first, then reload the scenery, with
no user action; keep the airport cores of built tiles sharp, inside the cap
and downgraded last; a flight plan is optional.

Background: `docs/specs/dynamic-scenery-exploration-20261109.md` (#1986,
branch `claude/l1986-dynamic-scenery`) §2.4, §3.3, §6.1 and E2. Hosting is
deferred; this is the local step.

Tags: **[measured]** this machine or this repo, **[source]** a cited page,
**[estimate]** worked out here.

---

## 1. Summary

| Part | Decision |
|---|---|
| Build | Steps 1-3 unchanged. Step 4 encodes the DSF and `.ter` files as today, and writes a **placeholder DDS** under every texture's own name: the same square at `zl - 3` (ZL13 for a ZL16 square: **512 px**, 4 map requests instead of 256, ~175 KB BC1 with mips). Water masks, `.ter` files and the DSF are unchanged (§3). **[rev 2]** 512 px is the owner's default; 256 px is refuted by flight 2 (X-Plane loads 512 px detail out to ~48 km at 60°N, §2.5). |
| Refine **[rev 2]** | An engine job reads the aircraft position from **X-Plane's Web API** (`localhost:8086`, 12.1.1+, no plugin) and lands, over the placeholder, the **tier** each square will need at its closest approach: 4096 px inside 1.65 S, 2048 px inside 2.8 S, 1024 px inside 5.2 S, where S is the square's `LOAD_CENTER` size (4.74 km for a ZL16 square at 61°N: 7.8 / 13.3 / 24.6 km). Each tier is a whole DDS landed with `os.replace` before X-Plane's step-up open at that distance, earliest deadline first (§4.3). |
| Spawn / jump **[rev 2]** | Airport cores of built tiles are kept sharp (§6). A spawn or jump anywhere else: land the core inside X-Plane's ~24 s flight-start window where the caches allow, then one automatic scenery reload for the rest (§4.5). |
| Measure "used" | **Not file access time** (APFS does not advance it after the first read, measured §5.2). A texture is used when the aircraft comes within its tier distance: the follow job writes `last_near_at` into the cache index (§5). |
| Cap **[rev 2]** | Default **100 GB** of upgraded imagery (every tier above the placeholder, cores included). Over the cap, the least recently near textures are **downgraded** to their kept placeholder, airport cores last. **Pins** ("always full resolution" tiles) are never downgraded and sit outside the cap (§6). |
| Settings **[rev 2]** | One world switch (imagery on demand: on/off), the cap, per-tile pins, "make all low-res again". Both apps, same rows (§7, #1244). |
| Offline | Placeholders always stand: every texture name always resolves to a whole DDS. No network means the scenery stays low-res, nothing breaks (§8). |
| Reuse | The fetcher, converter, DDS cache, atomic land, held-file retry, disk accounting and Storage machinery all exist (§9). New: placeholder writer, tier derivation, tier planner, Web API reader, follow job, index, downgrade sweep. |
| Unknowns **[rev 2]** | Rev 1's "depends on E2" is answered (§2). What remains (how X-Plane addresses the levels of a smaller file, S-scaling at other latitudes, slant vs ground distance, Windows rename, the reload trigger) is §11, each with its test. |

## 2. The E2 swap test, the recorder flights, and the design basis

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

Two runs were planned: **S** (small placeholders: is a changed header
picked up?) and **B** (blur: is a same-size pixel change picked up?). S
answered both (§2.3); B was not needed.

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
  them".
- XP 11.50+ also pages textures by VRAM pressure (developer blog, "All your
  VRAM is belonging to us", 2020), a second reload path.

### 2.3 Owner sim reads, 2026-11-09/10 [measured] **[rev 2]**

- **Ground test** (256 px placeholders, full textures swapped within 3 km
  of CYXY while parked): some areas sharpened after camera panning, not
  those under the aircraft; Developer > Reload Scenery then picked up every
  swapped file. So X-Plane **accepts a changed file, header size change
  included, whenever it next opens it**, and does **not** re-read a texture
  already resident at the finest level it wants.
- **In-flight test** (`swap.py follow --km 10`): squares ahead sharpened
  while flying, but close enough to see the pop-in; distant mountains stayed
  visibly low-res; the field, swapped while the aircraft sat on it, stayed
  blurry on return (resident at its finest level). Follow radius 10 km was
  shorter than the visible distance, and the kit held full textures only
  within ~15 km.

### 2.4 Recorder flights: what X-Plane opens, and when [measured] **[rev 2]**

`record_reads.py` (kit; to be promoted, §14 P1b) watches X-Plane's file
activity with `fs_usage`, polls the aircraft and camera position from the
Web API once a second, evicts the test tile's DDS files from the file
cache after each load, and asks the kernel (`mincore`) which pages were
read, hence which mip levels. `analyse_reads.py` turns the log into
distance bands.

- **Flight 1** (recorder v1, `flight1_salvage.txt`; no positions after the
  flight loaded). X-Plane never `read()`s a DDS: each load is open, `mmap`,
  page faults on the wanted mip levels, close, in 0.5-70 ms. At the flight
  start (01:23:03) **all 308 test-tile textures were loaded at mip 4 at
  once**; about **24 s later** 174 were loaded again, finer. `.ter` files
  are opened only at scenery loads, never one by one with distance. 912
  re-loads: every change of resolution is a new open of the file.
- **Flight 2** (recorder v2, `flight2_report.txt`, 2026-11-10
  02:13-02:23Z, 627 positions, 801 test-tile loads, every one with
  resident-page mip evidence, out to 98.8 km and 3,129 m): the table below.
  559 re-loads (399 finer, 123 coarser, 37 same); gaps mostly 10-60 s.
  A texture loaded at its finest level was **not re-opened as it fell
  behind**: no ZL16 step-down open was recorded at 13 or 25 km; the
  "coarser" loads are re-loads at ~47 km on the return leg, after X-Plane
  had dropped the texture in memory while far away (the step-down itself
  reads nothing).

### 2.5 The design basis: distance to resolution **[rev 2]**

Flight 2, loads by camera-to-square-centre distance (horizontal) and the
finest mip loaded (loads / distinct textures). ZL16 textures are 4096 px
(mip 0), ZL18 rows are the airport-cover squares.

| Band | mip 0 (4096) | mip 1 (2048) | mip 2 (1024) | mip 3 (512) |
|---|---|---|---|---|
| 0-2 km | 12/9 | | | |
| 2-5 km | 2/2 | 13/10 | | |
| 5-10 km | 88/66 | 2/2 | 16/16 | |
| 10-20 km | 1/1 | 142/98 | | 20/20 |
| 20-40 km | | | 229/151 | |
| 40-80 km | | | | 276/222 |

Read per zoom level, the step-up opens fall at sharp distances (median of
the step-up opens, extracted from the per-texture lines of
`flight2_report.txt`; p10-p90 in brackets) [measured]:

| Finest level wanted | ZL16, S = 4,744 m | ZL18, S = 1,195 m | In units of S |
|---|---|---|---|
| mip 3 (512 px) | ~48 km (first loads) | 11.2 km (10.8-11.6) | ~10 |
| mip 2 (1024 px) | 24.6 km (24.2-24.8), n=161 | 5.7 km (5.3-6.0), n=16 | 5.2 / 4.8 |
| mip 1 (2048 px) | 13.3 km (12.9-13.6), n=122 | 3.2 km (2.7-5.1), n=10 | 2.8 / 2.7 |
| mip 0 (4096 px) | 7.8 km (7.4-8.0), n=83 | 2.0 km (1.8-3.0), n=7 | 1.65 / 1.67 |

S is the `LOAD_CENTER` size the `.ter` declares (`LOAD_CENTER <lat> <lon>
4744 4096` for a ZL16 square at 61°N, `1195` for ZL18). Both zoom levels
fit the same rule, **d_k ≈ c_k · S** with c = 1.65, 2.8, 5.2, ~10 for mip
0..3: X-Plane asks for a fixed ground resolution per unit of distance.
Beyond ~10 S it wants mip 4 (256 px) or coarser; within 80 km it never
loaded coarser than mip 3, so a 256 px placeholder is visible on the
distant terrain and **512 px is the coarsest placeholder that X-Plane never
out-resolves beyond 5.2 S**.

Extrapolated by the rule (S = 9.78 km × cos lat for ZL16) **[estimate;
§11 U2]**:

| Latitude | S (ZL16) | 4096 inside | 2048 inside | 1024 inside | 512 inside |
|---|---|---|---|---|---|
| 60° (measured) | 4.7-4.9 km | 7.8 km | 13.3 km | 24.6 km | ~48 km |
| 45° | 6.9 km | 11.4 km | 19.4 km | 36 km | ~69 km |
| 30° | 8.5 km | 14.0 km | 23.7 km | 44 km | ~85 km |
| 0° | 9.8 km | 16.1 km | 27.4 km | 51 km | ~98 km |

**The read model** this spec builds on [measured, flights 1-2 and the owner
tests]: (1) every step **up** in resolution is a new open of the file and
reads whatever whole file is on disk at that moment, header size included;
(2) a step **down** happens in memory and reads nothing; (3) a texture at
the finest level it wants is not re-read until it has stepped down and
steps up again (for a square near the field: ~10 S away and back, ~48 km
at 60°N) or the scenery reloads; (4) at a flight load every texture in
range is loaded at mip 4, the finer levels ~24 s later. Hence: **a tier
must be on disk before the square's step-up crossing for that tier; a
tier landed after the square's last crossing of a pass shows only at the
next pass or reload.**

### 2.6 What rev 1's [E2] parts became **[rev 2]**

| Rev 1 | Now |
|---|---|
| §2.3 row "S shows": small placeholders, plain files | **Confirmed** (§2.3): plain files, `os.replace`, no virtual filesystem. |
| §2.3 row "S nothing, B shows": full-size placeholders, OS compression | **Refuted**: X-Plane honours the changed header. The full-size placeholder path (blocky 4096 px files, `decmpfs`/NTFS compression) is deleted from §3. |
| §2.3 row "only after Reload scenery" | **Partly**: needed only for textures already resident at their finest level, i.e. at a spawn or jump (§4.5). |
| §2.3 row "shows with stutter" | Not seen by the owner; frame time not yet recorded (§11 U10). |
| §2.3 row "within seconds at close range" | **Refuted**: a square swapped after its finest crossing stays as it was for that pass. |
| §3.1 `.ter` 4096 "[E2 confirms]" | **Confirmed**: a 256 px file under a `.ter` declaring 4096 loads. |
| §4.3 `R`, `T`, AGL and FL150 rules | **Replaced** by the per-square tier rule in units of S (§4.3). |
| §4.4 Windows rename | Moved to §4.7; still unmeasured (§11 U8). |

## 3. Placeholder build mode

### 3.1 What changes in step 4

Setting `imagery_on_demand` (§7) on, `texture_mode` `full_ortho` or
`airport_ortho`:

- **[rev 2]** The user still selects the tiles or regions to build (mesh,
  grading, airport patches) exactly as today; only their imagery changes.
- `O4_DSF_Utils.build_dsf` names textures and queues them as today
  (`download_queue.put(texture_attributes)`). The DSF, the `.ter` files
  (`create_terrain_file`: `LOAD_CENTER <lat> <lon> <m> 4096`,
  `BASE_TEX_NOWRAP ../textures/<y>_<x>_<prov><zl>.dds`) and the water and
  airport masks are **byte-identical to a full build**: none of them reads a
  pixel [measured: code, #1986 §3.1/3.3]. The `.ter` 4096 is a paging hint,
  not a size check: a 256 px file under it loads (§2.3) **[rev 2]**.
- The download worker fetches the square at `pzl = zl - placeholder_zl_drop`
  (default 3): the same 16x16-tile square at ZL16 is a 2x2-tile square at
  ZL13, 512 px. `O4_Imagery_Utils.build_texture_from_tilbox` already builds
  a texture from any tile box at any zoom; the placeholder is that call with
  the box scaled by `2**-drop`. Requests per texture: 256 at full, 4 at
  drop 3.
- The converter (`convert_texture`) runs unchanged on the placeholder image:
  colour filter, harmonization field, mask imprint (the mask resized to the
  placeholder size) and sea fill all apply, so a placeholder and its later
  tiers are processed the same way. Its output lands under the full
  texture's name through `O4_DDS_File.land`. A placeholder is **not** stored
  in the content-keyed `DDS_cache` (it would compete with full textures for
  that cache's 20 GB cap); it is kept in the placeholder store (§6.2).
- The placeholder JPEG lands in the imagery cache under its own zoom
  (`Orthophotos/.../<prov>_13/`), where any later build at that zoom also
  finds it.
- Airport cover textures (`cover_airports_with_highres`, ZL17/18) get
  placeholders the same way (ZL15 for ZL18).

### 3.2 Colour harmonization

The field (`O4_Imagery_Utils.solve_color_field`) is solved from seam-strip
statistics of 512x512 thumbnails (`O4_Color_Harmonization.THUMBNAIL_SIZE`,
decoded at 1/8 from a 4096 JPEG). A ZL13 placeholder JPEG **is** a 512x512
image of the same square, so the field is solved from the placeholders at
build time and **persisted and frozen** (`color_field_path(tile)`); every
tier arriving later (1024, 2048, 4096) reads the frozen field and never
re-solves it **[rev 2: all tiers, not only full]**. A re-solve mid-flight
would shift every placeholder's neighbours and draw new seams (the OTHH
seam precedent, memory "Color harmonization mints seams").

### 3.3 Size [estimate] **[rev 2]**

| Placeholder | per texture (BC1, mips) | per 1° tile, 60°N (308 textures) | per 1° tile, equator (~128) | 18,500 land tiles (median 234 textures, #1986 §6.1) |
|---|---|---|---|---|
| drop 4 (256 px) — **refuted** (§2.5) | 44 KB [measured: kit] | 13.5 MB | 5.6 MB | 190 GB |
| **drop 3 (512 px, owner default)** | 175 KB | 54 MB | 22 MB | **0.76 TB** |
| drop 2 (1024 px) | 700 KB | 215 MB | 90 MB | 3.0 TB |
| full ZL16 (4096 px) | 11.2 MB [measured: kit] | 3.4 GB | 1.4 GB | — |

Plus the DSF and masks per tile (#1986 §4.3). Every land tile at the
default is about 0.76 TB of placeholders; a user builds only the tiles or
regions they select, so a typical install holds a small part of that.
`placeholder_zl_drop` stays an expert setting (2 is allowed; 4 is refused
by the cfg registry, since X-Plane out-resolves it inside ~10 S).

### 3.4 Step reuse and the tile record

- `O4_Step_Reuse`: `imagery_on_demand` and `placeholder_zl_drop` enter the
  step-4 inputs, so toggling them re-runs step 4 only (DSF encode ~27 s,
  #1986 memory "DSF encoder 16-min premise false", plus the placeholders).
- The tile's imagery record (`Ortho4XP_<tile>_imagery.json`,
  `O4_Tile_Utils`) gains `"on_demand": true`, `"placeholder_zl"` and
  **[rev 2]** `"pinned": false`; the Library shows such a tile as
  "Low-res, sharpens in flight" (or "Full resolution, kept" when pinned).
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
**[rev 2]** It starts by itself when the world switch is on, the app is
open and the Web API answers (owner: "load imagery automatically").

### 4.2 Position

`GET http://localhost:8086/api/v2/datarefs?filter[name]=<ref>` once for
each dataref id, then `GET /api/v2/datarefs/<id>/value` at 1 Hz, or one
WebSocket subscription on `ws://localhost:8086/api/v2` (both since X-Plane
12.1.1, enabled by default on localhost) [source: developer.x-plane.com
"X-Plane Web API"; measured 2026-11-09: the kit's `swap.py follow` read
latitude, longitude, elevation and AGL from the owner's running X-Plane 12
on this Mac with these calls, no setup]. Datarefs: `sim/flightmodel/position/latitude`,
`.../longitude`, `.../elevation`, `.../y_agl`, `.../groundspeed`,
`.../true_psi`, and **[rev 2]** the camera (`sim/graphics/view/view_x/y/z`
with `local_x/y/z`): X-Plane pages by the camera, which an outside view
moves kilometres from the aircraft. The port is an expert setting
(`xplane_web_api_port`, default 8086). No plugin.

**[rev 2]** X-Plane hands out **new dataref ids when a flight loads**, and
its Web API can drop the connection then (flight 1 lost the position at
the flight load; flight 2's v2 poller forgets its ids on any error and
retries every second). The reader does the same; an id reset is the
flight-load witness of §4.5.

### 4.3 What to fetch, at which tier, and when **[rev 2: replaces rev 1's R/T rule]**

**Tiers.** For a square of size S (its `.ter` `LOAD_CENTER` metres; the
index stores it), the four files X-Plane can want within visible distance:

| Tier | Width | Source zoom (ZL16 square) | Requests | Bytes (BC1+mips) | Wanted inside |
|---|---|---|---|---|---|
| T0 placeholder | 512 | zl-3 (ZL13) | 4 | 175 KB | ~10 S (on disk from the build) |
| T1 | 1024 | zl-2 (ZL14) | 16 | 0.7 MB | 5.2 S |
| T2 | 2048 | zl-1 (ZL15) | 64 | 2.8 MB | 2.8 S |
| T3 full | 4096 | zl | 256 | 11.2 MB | 1.65 S |

**[rev 3, owner 2026-11-10T05:18Z, P3b]** Ground track and groundspeed are
the CAMERA's, measured from its position deltas over the last few seconds
on this machine's clock (`O4_Imagery_Follow_Motion`), never the
`sim/flightmodel/position/groundspeed` dataref: flight 2 was flown with a
ground-speed multiplier (4-8x) that dataref does not show. The target is
the loader keeping up at true speed (P3a: 98.3 % of step-up opens served at
true speed with one slot).

**Rule.** From the camera position, ground track and groundspeed, predict
each square's closest approach in the next few minutes (straight line plus
a lateral margin of 0.5 S for turns). Its **target tier** is the finest
tier wanted at that closest approach; each crossing `c_k · S` on the way
in is a **deadline** for a file at least that fine. A square already at or
above the tier a crossing wants needs nothing for it. The queue is
**earliest deadline first**; for each deadline the job lands the cheapest
file that both serves it and can arrive in time, so:

- a square passed **abeam beyond 2.8 S** gets T1 only (16 requests);
- abeam between 1.65 S and 2.8 S: T1, then T2;
- **on track** (closest approach inside 1.65 S): T1 by its 5.2 S crossing,
  then the full texture by its 2.8 S crossing (the full also serves the
  2048 crossing), so the square never shows the placeholder where X-Plane
  wants 1024 and never a 2048 file where it wants 4096.

A late tier is still landed (it shows at the next pass or reload, §2.5)
but drops to the lowest priority. Airport cover squares (ZL17/18) follow
the same rule with their own S (ZL18 full only inside ~2 km); rev 1's
3,000 ft AGL and FL150 rules are deleted: the S rule already limits them,
and slant distance (§11 U4) would limit them further at altitude.

**Lead.** A tier must start `T_lead` before its crossing:
`D_k = c_k · S + v · T_lead`, with `T_lead` covering download, convert and
queue (default 30 s, expert `ondemand_lead_s`; set from §11 U7). At 60°N
(S = 4.74 km), full-resolution fetch starts at [estimate]:

| Groundspeed | v · 30 s | Full (deadline 7.8 km) starts at | 2048 (13.3 km) at | 1024 (24.6 km) at |
|---|---|---|---|---|
| 100 kt (51 m/s) | 1.5 km | 9.3 km | 14.8 km | 26.1 km |
| 250 kt (129 m/s) | 3.9 km | **11.7 km** | 17.2 km | 28.5 km |
| 450 kt (231 m/s) | 6.9 km | 14.7 km | 20.2 km | 31.5 km |

So full resolution lands within a ~12 km lead and the 2048 / 1024 tiers
cover ~10-40 km, the owner's "visible distance"; beyond, the 512 px
placeholder is what X-Plane asks for anyway. Head-on at 250 kt the time
between a square's 1024 and 2048 crossings is ~88 s and between 2048 and
4096 ~43 s, the budget for its full fetch.

**Throughput** (straight track, horizontal distance; per minute of flight)
[estimate]:

| Case | Full / min | T2 / min | T1 / min | Requests / s | Upgraded bytes kept |
|---|---|---|---|---|---|
| 60°N, 250 kt | 5.5 | 3.8 | 16.8 (7.7 stay T1) | ~32 | 77 MB/min ≈ 4.6 GB/h |
| 60°N, 450 kt | 9.9 | 6.8 | 30 | ~58 | ≈ 8.3 GB/h |
| equator, 250 kt | 2.6 | 1.8 | 8.2 (3.8 stay T1) | ~15 | 37 MB/min ≈ 2.2 GB/h |

A build fetches 85-256 requests/s today, so the job's peak is a fraction
of a build's. Per-texture time (256 requests plus a 4096 BC1 encode) is
not yet measured under the job (§11 U7); with two textures in flight the
60°N 250 kt case needs one full texture every ~11 s.

### 4.4 Fetch, convert, swap

- One texture at a time per provider by default (`O4_Imagery_Prefetch`'s
  `TEXTURES_IN_FLIGHT = 1` precedent; ~~**[rev 2]** two allowed when the
  queue's earliest deadline is at risk~~ **[rev 3, owner ruling
  2026-11-10T05:18Z]** ADAPTIVE LIKE VIDEO STREAMING: the job keeps a
  buffer of fetched tiers ahead of the aircraft, measured as the queue's
  tightest slack (each queued fetch's time to its crossing minus when it
  would land with the work ahead of it at the current slots). Normally ONE
  download runs; while the buffer depletes (under 5 s, or falling faster
  than 0.5 s/s while under 15 s, for the 30 s lead; both scale with the
  lead) one more slot is added every 5 s, up to 4; after the buffer has
  held at 15 s or more for 20 s one slot is dropped every 5 s, back to one.
  `O4_Imagery_Fetch_Slots`, P3b), through the same fetcher a build
  uses (`O4_Imagery_Fetch`: AIMD window, `Retry-After`, per-host budget
  shared across processes; `O4_Imagery_Utils.host_request_limit`,
  `provider_max_threads`). The provider's own throttling therefore holds
  exactly as in a build; nothing on-demand asks harder than a build.
- `download_jpeg_ortho` at the tier's zoom (`zl - drop_k`, §4.3), then
  `convert_texture` with the tile object and the frozen field: it lands the
  DDS over what is there through `O4_DDS_File.land` (`os.replace`, §4.7)
  and, for the full tier, stores it in the content-keyed `DDS_cache` (hard
  link). T1/T2 files are not put in `DDS_cache`.
- **[rev 2]** A full DDS already in `DDS_cache` (another build's, or a
  downgraded one not yet evicted) is landed by hard link with no network.
- A swap is logged (`logs/imagery_on_demand.log`) and counted in the status
  event: textures sharp nearby, queued, late, failed, bytes used against
  the cap.

### 4.5 Spawn and jump **[rev 2, new]**

At a flight load X-Plane loads every texture in range at mip 4, then the
finer levels ~24 s later (§2.4); a texture already at its finest level is
not re-read until it steps down and up again (§2.5 read model), which for
the field means ~10 S away and back: for a local flight, never.

Witness: a Web API id reset or connection drop that recovers (a flight
load), or a camera jump of more than 5 S in under 5 s (map jump, replay,
"move to"). Then:

1. **Built airports need nothing.** The cores of built tiles' airports
   are kept upgraded (§6.1); spawning at any of them reads full files.
2. **Elsewhere:** plan the spawn core (squares within 1.65 S of the
   camera, the ZL17/18 covers, and the T2/T1 rings, §4.3) with the deadline
   "flight-start window" (~24 s after the witness). `DDS_cache` hits land in
   milliseconds, cached JPEGs need only a convert; network fetches usually
   miss the window (a core is ~30 textures, ~7,700 requests).
3. Whatever missed the window: when it has landed, **one scenery reload**,
   automatic (owner design answer), at most one per jump, through a Web API
   command if X-Plane exposes one, else a small plugin calling
   `XPLMReloadScenery` (§11 U9).

| Way | Pilot sees | Cost |
|---|---|---|
| Land in the flight-start window | sharp from the first second | only for cached imagery |
| Reload after the core lands | blurry for ~1-2 min, then a stall, then sharp | a stall of seconds to tens of seconds (a flight-1 scenery load opened 2,200-2,400 `.ter` files; §11 U9); a plugin if no command exists |
| Wait for the step-down | blurry field for the whole local flight | none |
| Prefetch before the flight ("Make sharp now", §8) | sharp | the user names the area |

The reload is skipped when nothing missed the window. ~~Whether it may also
fire in the air after a jump at speed is an owner question (§12).~~
**[rev 4]** It also fires in the air after a jump (owner, 2026-11-10).

**[rev 4, P5 as built]** `O4_Imagery_Spawn` (pure) and the follow job.

- **Witnesses.** `spawn`: the first position a follow session reads.
  `flight_load`: positions resume after a Web API drop. `jump`: the
  camera moved more than 5 S in under 5 s at a speed no aircraft flies
  (`O4_Imagery_Follow_Motion`). Positions that resume where the camera
  was (within 2 km) open nothing when the drop was shorter than 10 s (a
  stutter: X-Plane read nothing again; flight 1's load dropped the API
  for ~90 s) or when this job's own reload was sent less than 120 s
  before (the reload's stall). A new witness replaces an open episode.
- **Core.** Every square a camera standing at the new place wants finer
  than its file on disk, by the kept-core rule of §6.1
  (`O4_Imagery_OnDemand_Cores.core_tier`: full inside 1.65 S, 2048
  inside 2.8 S, 1024 inside 5.2 S). Checked on flight 1's start: the rule
  names 71 squares at the field (14 full, 19 at 2048, 38 at 1024); of the
  70 textures X-Plane opened finer than the placeholder ~24 s after the
  load, 63 at exactly the rule's tier and all within one tier [measured,
  `tests/test_imagery_spawn.py`]. Each square is fetched once, straight
  at its tier; files that need no download (a `DDS_cache` entry of the
  full tier, or the tier's cached JPEG) first, then the finest tier
  first, nearest first. Files that need no download take no fetch slot
  (up to 4 at once, still under R6's 4 landings a second: 71 files in
  18 s) and land while the job is offline. Downloads use the adaptive
  slots of §4.4 with the window's end as their deadline, so the buffer
  reads empty and the slots open.
- **Window.** 24 s after a `flight_load` or `jump` witness, of which 20 s
  are counted on (the witness may trail X-Plane's first opens; §11 U11).
  A session's first position has no window: X-Plane may have stood there
  for an hour, so whatever lands for its core is taken as missed.
- **Reload.** When nothing of the core is left to land (downloaded,
  or failed three times), the episode closes. One reload is sent if a
  file landed after the window AND the camera is still inside the
  distance where X-Plane wants a finer tier than the file it read at the
  load (§2.5: it holds the coarser level and no step-up open will come).
  Nothing missed, nothing landed (no network), or the camera gone from
  there: no reload. Never a second one for the same witness.
- **How.** X-Plane's own command `sim/operation/reload_scenery` through
  the Web API (§11 U9): no plugin. `imagery_follow_start` takes
  `reload: false` for a job that never reloads; `ImageryFollowStatus`
  carries `reloads`; capability `imagery_spawn_reload`. X-Plane before
  12.1.4, or with no flight loaded, has no such command: the job logs
  `reload=no` and goes on.
- **Log.** `logs/imagery_on_demand.log` gets `spawn=<witness> core=N
  local=N window_s=S` when an episode opens and `spawn_done=<witness>
  landed=N missed=N stale=N reload=sent|no` when it closes.

### 4.6 Partial and mip-level DDS files **[rev 2, new]**

X-Plane maps the file and touches only the levels it wants (a mip 3 load
pages 131-193 kB of an 11.2 MB file, flight 1). Can the job write only the
levels needed?

| Way | Ruling |
|---|---|
| (a) **Tier files**: a complete, smaller DDS whose top level is the tier width (512/1024/2048) | **Adopted.** Proven: X-Plane reads the new header at the next open (§2.3). This is already "only the needed levels": the 1024 tier is the full chain from mip 2 down. |
| (b) A 4096 header with the file cut after the levels present | **Refused.** A mapped read of a missing level faults past the end of the file (SIGBUS): a crash, not a blur. `O4_DDS_File.is_whole` rejects such a file by design. |
| (c) A full-size sparse file, top levels left as holes and filled in place later | **Refused for v1.** A hole reads as zeros (black squares) if X-Plane wants that level first; filling in place writes into a file X-Plane maps and that is hard-linked into the caches (breaks rule R2, §4.7); sparse support differs on APFS, NTFS and ext4. The disk saving it offers, (a) already has. |

The free direction: from a full DDS any lower tier is the same bytes minus
its top levels (`O4_DDS_File.split_levels` → `build_header` → `assemble`),
no re-encode, milliseconds per texture; the kit's `small` set was made
this way. Downgrades still use the kept placeholder (§6.2), so a square
looks the same as its never-upgraded neighbours.

### 4.7 Atomic swap rules **[rev 2, new]**

- **R1 Whole files only.** Every landing writes a complete DDS under
  `O4_DDS_File.partial_name` in the same directory (same volume), checks
  `is_whole`, and `os.replace`s it onto the name (`O4_DDS_File.land`).
- **R2 Never write into a landed texture.** It may be a hard link shared
  with `DDS_cache` or the placeholder store, and X-Plane may be paging it:
  every change is a new inode under the old name.
- **R3 Never delete or truncate a texture name.** A downgrade is a landing
  too. A missing name breaks the `.ter`; a short file under a mapping
  crashes X-Plane (§4.6 b).
- **R4 Never touch `.ter`, DSF or masks while X-Plane runs.** They are read
  only at scenery loads (flight 1); a change there needs a reload.
- **R5 Land before the crossing** (§4.3); late landings are logged and
  counted ("late") so §11 U5 is measured on every flight.
- **R6 Rate.** At most `ondemand_lands_per_s` (default 4) landings a
  second, so a burst never competes with X-Plane's own paging (§11 U10).
- **R7 Start clean.** The job sweeps partials (`sweep_partials`) and resets
  `upgrading` rows at start (§8).

**macOS and Linux:** renaming over a file another process has open or
mapped is legal; X-Plane keeps the old inode until it closes and unmaps,
which on macOS it does within 0.5-70 ms per load (flight 1).

**Windows:** `os.replace` (`MoveFileExW`, replace existing) is refused while
any process holds the target open without `FILE_SHARE_DELETE` or keeps a
mapped view of it. If X-Plane on Windows closes and unmaps per load as on
macOS, `O4_Held_File.retrying_a_held_file` wins within milliseconds; an
antivirus scan of the new file is the same refusal and the same retry. If
X-Plane keeps views mapped while a texture is resident, the landing waits
(requeued a few seconds later, never blocking the job) until it steps
down. Never delete then rename: that exposes a missing name. If renames
fail for whole passes, the fallback is a virtual filesystem (WinFsp,
#1986 §6.1), not a new texture name (that needs a `.ter` change and a
reload). Measured in §14 P6 (§11 U8).

## 5. The cache index and "last used"

### 5.1 The index

SQLite (standard library `sqlite3`, WAL) at
`<data folder>/Imagery_on_demand/index.sqlite`, one row per
(tile, texture name):

| column | meaning |
|---|---|
| `tile`, `name`, `zl`, `provider` | identity (the texture's file name) |
| `centre_lat`, `centre_lon`, `load_size_m` | from the name and the `.ter` `LOAD_CENTER` (S, §4.3) **[rev 2]** |
| `state` | `low`, `upgrading`, `upgraded`, `failed` **[rev 2]** |
| `tier_px` | width of the file on disk: 512, 1024, 2048 or 4096 **[rev 2]** |
| `core`, `pinned` | in an airport core (§6.1); in a pinned tile **[rev 2]** |
| `placeholder_path` | the kept placeholder DDS (§6.2) |
| `full_bytes` | freeable bytes of the upgraded file (`O4_Disk_Usage.freeable_bytes`: a hard link counts once) |
| `dds_cache_key`, `jpeg_path` | what a downgrade frees |
| `fetched_at`, `last_near_at`, `near_count`, `late_count` | for the LRU and §11 U5 |

The index is a cache of facts on disk: a rebuild walks the on-demand tiles'
`textures/`, reads each DDS header (`O4_DDS_File.split_levels`: width =
`tier_px`), the `.ter` files (S) and the tile records (`pinned`), and
restores every column except `last_near_at` (set to the rebuild time, so
nothing is downgraded by a lost index).

### 5.2 Why not file access time [measured 2026-11-09, this Mac]

APFS on `/System/Volumes/Data` updates `atime` on a read only when it is
older than `mtime`: a file read after it was written gets one `atime`
update, and every later read leaves it unchanged (measured: atime set to
2026-01-01 with mtime 2025-12-01, then read: atime stayed 2026-01-01).
Windows has last-access updates off on most volumes, and Spotlight, backup
and antivirus reads would count as "use" where it is on. `atime` also
cannot tell a texture X-Plane read at 512 px from 40 km away from one the
pilot flew over.

### 5.3 The measure

A texture is **used** when the camera comes within its tier distance
(`c_k · S` of its current tier) while the sim is running and not paused.
The follow job writes `last_near_at = now` for those rows at most once a
minute, and `near_count += 1` once per approach. The LRU sorts by
`last_near_at`. This is the sim's own position, measured, not a guess from
the filesystem, and it is what "used" means to the pilot: flown near.

## 6. Storage cap and LRU downgrade

### 6.1 What counts against the cap **[rev 2]**

`imagery_on_demand_cap_gb` (§7, **default 100**) bounds the freeable bytes
of everything a downgrade would free: every upgraded tier (T1-T3) in
on-demand tiles' `textures/`, their `DDS_cache` entries and their source
JPEGs at the tier zooms. Placeholders, DSFs, masks and normally built
tiles do not count. With hard links (DDS cache to `textures/`) a texture
counts once (`O4_Disk_Usage.freeable_bytes`).

- **Airport cores** (owner design answer): the squares within 1.65 S of
  each airport the tile build graded (the airports of its airport patches;
  their ZL17/18 cover squares included) plus their T2/T1 rings, ~30
  textures and ~0.4 GB per airport at 60°N [estimate]. Fetched after the
  build, counted in the cap, downgraded only when no other row is left.
- **[rev 5, RULINGS 2026-11-10c/d]** Pins are renamed **Favorites** in
  both apps (wire and index keep `pinned`). Favorites COUNT: one budget
  holds every on-demand tile's imagery, favorites included, and over it
  the order is ordinary sharp imagery → airport cores → favorites
  (`O4_Imagery_OnDemand_Budget.CLEAR_TIERS`); "Make all low-res again" by
  hand still keeps favorites. The budget also counts its FLOOR (the
  placeholders and the tiles' DSFs, never freed); a budget under it
  warns. 10d then makes this budget part of ONE disk budget for
  everything the app stores (`storage_budget_gb`, `o4_engine/storage_budget.py`):
  when it is set the sharp imagery is its fifth clear tier; when it is not,
  `imagery_on_demand_cap_gb` (now Expert) bounds the sharp imagery alone.
  The text below is rev 2's and is superseded where it says otherwise.
- **Pins** ("always full resolution", per tile, owner decision 3): the
  whole tile is fetched at full resolution, **never downgraded, and
  outside the cap** (the Storage row shows them as their own line).
  3.4 GB per tile at 60°N, 1.4 GB at the equator.

### 6.2 Downgrade

1. Pick rows `state = upgraded`, `pinned = 0`, sorted by (`core`,
   `last_near_at`) — cores last — skipping any square within 2 × its tier
   distance of the camera while the sim runs, and any texture landed in
   the last hour (`storage.IN_FLIGHT_SECONDS`).
2. Land the kept placeholder over the upgraded file: hard link the
   placeholder store's copy beside it under a partial name, then
   `O4_DDS_File.land` (the same atomic step as an upgrade, §4.7).
3. Free the full texture's `DDS_cache` entry (only when no other build dir
   holds it: `O4_DDS_Cache.held_by_built_tiles`) and its tier JPEG.
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
flown areas"), sized by `storage_scan`, with the pins as a second line. Its
clear action is a **downgrade of everything unpinned**, never a deletion:
deleting would leave textures missing. The existing `imagery` and `dds`
cache caps (`storage_cache_caps_gb`) must skip files the index marks
`upgraded` or `pinned` (their LRU would otherwise delete the source of a
sharp texture and the downgrade would later miscount); the
`_remove_redundant` sweep already skips DDS entries other tiles hold.

`O4_Imagery_Freshness.discard_tile_imagery` ("Update Imagery") downgrades an
on-demand tile to placeholders and refreshes the placeholders; on a pinned
tile it refetches the full set.

### 6.4 Storage math [estimate] **[rev 2, new]**

| Quantity | Value |
|---|---|
| Placeholders, every land tile at 512 px | ≈ 0.76 TB (§3.3); per built tile 22-54 MB |
| 100 GB cap, in full ZL16 textures | ≈ 8,900 (11.2 MB each): ≈ 29 whole tiles at 60°N, ≈ 70 at the equator |
| Fill rate, new ground (§4.3) | ≈ 4.6 GB/h at 60°N 250 kt, ≈ 2.2 GB/h at the equator: 100 GB ≈ 22-45 flight hours of new ground; flying the same area again costs nothing |
| One airport core | ≈ 0.3-0.5 GB; 100 built airports would hold ~40 GB of the cap, hence cores downgrade last, not never |
| One pin | 1.4-3.4 GB per tile, outside the cap |

## 7. Settings, both apps (#1244) **[rev 2]**

Mac: `Sources/XPTerrainBuilder/SettingsLayout.swift` rows; Qt: the same
settings through `O4_Qt_Settings*.py`; registry in `O4_Cfg_Vars.py` (types,
defaults, hints). Same rows, same order, same pane, in the same PR.

| Key | Pane | Row text | Default |
|---|---|---|---|
| `imagery_on_demand` | Imagery (`.app`) | "Fetch imagery on demand, worldwide?" Summary: "New builds get low-resolution imagery; full detail is fetched automatically around the aircraft and kept within the storage limit." | **on** (rev 5, RULINGS 2026-11-10c (3); was "off until §14 P6 passes") |
| `storage_budget_gb` **[rev 5]** | Storage | "How much disk space may XPTerrainBuilder use (GB)?" Summary: "More space keeps downloads and rebuild data, so tiles rebuild in minutes instead of re-downloading." The pane shows use, floor and the recommended minimum (floor + max(50 GB, 50 % of floor)) | 0 = not set |
| `imagery_on_demand_cap_gb` | Storage, expert **[rev 5]** | "How much space may sharp imagery use (GB)?" (applies only while `storage_budget_gb` is not set) | **100** |
| `placeholder_zl_drop` | Imagery, expert | "Low-res imagery detail (zoom levels below the build's)" | 3 (2 or 3 allowed) |
| `ondemand_lead_s` | Imagery, expert | "Start fetching this many seconds ahead" | 30 (§11 U7) |
| `ondemand_lands_per_s` | Imagery, expert | "Imagery swaps per second, at most" | 4 |
| `xplane_web_api_port` | Speed & Downloads, expert | "X-Plane Web API port" | 8086 |

Rev 1's `refine_radius_km` is deleted: the tier distances come from each
square's S (§4.3).

**Favorites [rev 5]:** the tile pane's "Favorite" row is a switch on every
tile the app built (enabled on a tile built on demand); the Library's
action reads "Add to Favorites" / "Remove from Favorites", its badge a
star; the map draws a star on a favorite tile (Mac `MapCanvasView`, Qt
`O4_Qt_Map_Favorite`). The rev 2 paragraph below is superseded.

**Pins:** a per-tile action in the Library (both apps: the tile's context
menu and its info pane) "Always keep full resolution" / "Let it go low-res
again"; stored in the tile record (`"pinned"`) and the index; a pinned
tile shows a pin badge. Storage pane: the `ondemand` store row (bytes,
cores) and the pins line, with the action "Make all low-res again" (one
confirmation naming the space freed; pins untouched). Main window: a status
line in the activity area while following ("Following X-Plane: 14 sharp
nearby, 2 downloading, 0 late"); if it adds a toolbar item, the
`test_qt_layout_parity.py` manifest gains it in both apps.

The job starts automatically when `imagery_on_demand` is on, the app is
open, and the Web API answers; it can be paused from the status line.

## 8. Offline and failure behaviour

- **Invariant:** every texture name of an on-demand tile resolves to a whole
  DDS at all times (placeholder or a tier). Every write is a land of a whole
  file; nothing deletes a texture name (§4.7).
- No network: the fetcher's connect failures pause the job (existing AIMD
  pause, then a 60 s retry); the status says "Offline: imagery stays
  low-res". X-Plane flies normally on placeholders. **[rev 2]** No reload
  is issued at a spawn without network (§4.5).
- Provider refuses (429, quota, terms): the fetcher's own back-off; a
  texture that fails three times is marked `failed` and retried next
  session.
- X-Plane not running, or the Web API off: the job idles and says so.
- App quits mid-fetch: a partial DDS never has the final name
  (`O4_DDS_File.partial_name`); the next start sweeps partials and resets
  `upgrading` rows to `low`.
- Before a flight with no network en route: "Make sharp now" on a map
  selection (Library/Map) fetches a chosen area without a position, under
  the same cap.

## 9. What it reuses (`tools/blast.py --find`)

| Need | Existing |
|---|---|
| Texture names, square geometry | `O4_File_Names.dds_file_name_from_attributes` [shared 5], `jpeg_file_name_from_attributes`; `O4_Geo_Utils.gtile_to_wgs84` [shared 7] |
| Texture list of a built tile, S | `O4_Imagery_Prefetch.candidates` (reads `terrain/*.ter` names); `.ter` `LOAD_CENTER` written by `O4_DSF_Utils.create_terrain_file` |
| Download at any zoom | `O4_Imagery_Utils.download_jpeg_ortho` [shared 1], `download_orthophoto_once`, `build_texture_from_tilbox` |
| Provider throttling | `O4_Imagery_Fetch` (AIMD, `Retry-After`, budget), `host_request_limit` [shared 1], `provider_max_threads` |
| Convert, mask, harmonize | `O4_Imagery_Utils.convert_texture` [shared 2], `solve_color_field`, `color_field_path` [shared 1] |
| Atomic land, partials, tiers from a full DDS | `O4_DDS_File.land` [shared 2], `partial_name`, `sweep_partials`, `is_whole`, `split_levels` [shared 2], `build_header`, `assemble`, `mip_dims` |
| Windows rename over a held file | `O4_Held_File.retrying_a_held_file` [shared 6] |
| Content-keyed DDS store | `O4_DDS_Cache.serve`, `store`, `held_by_built_tiles` |
| Bytes a delete frees | `O4_Disk_Usage.freeable_bytes` |
| Storage rows, LRU, log | `o4_engine/storage.py` (`STORES`, `_evict_to_cap`, `storage_scan`, `storage_auto_clean`, `logs/storage.log`), `storage_redundant.py`, `O4_Qt_Settings_Storage.StorageSection`, `StorageSettingsView.swift`, `BuildModel+Storage.swift` |
| Imagery commands, events | `o4_engine/imagery_commands.py` (command module pattern), `o4_engine/events.py`, `OrthoEngineClient.swift` |
| Build lock | `o4_engine/library.py` |
| Step reuse | `O4_Step_Reuse` |
| Mesh without imagery | `src/tile_bundle` (#1699) |
| Web API position, read tracing **[rev 2]** | the kit's `record_reads.py` (`resolve_refs`, `read_position`, `poll_positions`) and `analyse_reads.py`, promoted in §14 P1b; the engine reader is extracted from them once, never written twice |

New (one module each, **[rev 2]** list): `O4_Imagery_Placeholder` (the
placeholder writer), `O4_DDS_Tiers` (a tier from a full DDS, tier widths
and zooms), `O4_Imagery_Tier_Plan` (pure planner: closest approach,
deadlines, EDF queue), `O4_XPlane_WebAPI` (position and camera reader,
standard library), `O4_Imagery_OnDemand_Index` (the index and its rebuild),
`o4_engine/imagery_follow.py` (the job), `o4_engine/imagery_downgrade.py`
(the sweep).

## 10. Imagery terms

On-demand fetching changes **when** a texture is downloaded, not what or
from where: the user's machine fetches from the provider exactly as a build
does today, and keeps the result in the same caches. A provider whose terms
limit caching (Google Map Tiles: no caching beyond `Cache-Control`, #1986
§6.2) is no more and no less allowed here than in a build. The downgrade
makes the cache smaller, never larger. Nothing is redistributed. **[rev 2]**
The T1/T2 tiers are the provider's own lower-zoom tiles, fetched as a
build at that zoom would.

## 11. Remaining unknowns and how to test each **[rev 2: replaces "Parts that depend on E2"]**

| # | Unknown | Why it matters | Test | Phase |
|---|---|---|---|---|
| U1 | Does X-Plane address a smaller file's levels **relative to the file** (a 512 file's mip 0 at 25-48 km) or by **absolute pixels** against the `.ter`'s declared 4096 (then a 512 file would be read at 1/8 of the intended detail at each distance)? | The placeholder's real look and every tier's value | Recorder flight on a placeholder build: `mincore` levels touched per load of the 512 files, by distance | P1 |
| U2 | Do the thresholds scale with S at other latitudes (fitted at 61°N, ZL16 and ZL18 only)? | Every distance in §4.3 away from 60°N | One recorder flight on a 30°N tile (the HECA tile, the default representative airport); predicted mip 0 at ~14 km | P1 |
| U3 | Do X-Plane's texture-quality setting, screen size, FOV or VRAM pressure move the thresholds? | Users run other settings | Repeat one leg with texture quality one notch lower; compare `c_k` | P1 |
| U4 | Horizontal or slant distance? (The analysis used horizontal; flight 2 stayed below 3.1 km.) | High-altitude fetch volume | One leg at ~6,000 m over the tile; `c_k` with either distance | P3 |
| U5 | How many tiers land late, and does a late landing really wait for the next pass? | Pop-in seen by the pilot | Job counts `late`; recorder pairs each landing with the next open of that name | P3 |
| U6 | Do the provider's lower zooms (T1/T2) match the full zoom (date, colour)? A mismatch pops at each tier change | Tier ladder vs full-only | Offline: fetch ZL13-16 of 50 squares, downsample the full, per-square ΔE and change-detection; if it fails, the ladder is T0 → full, fetched earlier | P3a |
| U7 | Download + convert time per tier under the job, and the right `T_lead` | §4.3 lead table | Offline bench on the real fetcher (no sim), 100 textures per tier per provider | P3a |
| U8 | Windows: does X-Plane hold handles or mapped views; how often does `os.replace` fail? | §4.7 | Process Monitor (or `handle.exe`) trace during a flight + a swap stress with the kit's `swap.py`; Linux: `strace -f -e trace=openat,mmap,munmap,close` | P6 |
| U9 | ~~Can a Web API command reload the scenery, or is a plugin (`XPLMReloadScenery`) needed?~~ **[rev 4] Answered: a command, no plugin.** The Web API's v2 (X-Plane 12.1.4+) lists commands (`GET /api/v2/commands?filter[name]=<name>`) and activates one (`POST /api/v2/command/<id>/activate`, body `{"duration": 0}` = press and release) [source: developer.x-plane.com/article/x-plane-web-api, "Activate a command (v2+)"]; X-Plane 12 ships `sim/operation/reload_scenery`, "Force reloading the current scenery" [source: `Resources/plugins/Commands.txt` of the X-Plane 12 install on this Mac]. `O4_XPlane_WebAPI.reload_scenery` sends it. Not yet run against a live X-Plane (none was running). Still open: how long is the stall? | §4.5 | Time a reload with the recorder (first to last `.ter` open) on the P5 flight; confirm the POST is taken (`reload=sent` in the log, then the `.ter` burst) | P5 |
| U10 | Do landings or the job's disk I/O cause stutter? | R6 rate | Recorder logs frame period (`sim/time/framerate_period`); compare legs with the job on and off | P3 |
| U11 | Is the flight-start window always ~24 s (one sample)? | §4.5 step 2 | Recorder across five spawns (cold start, airport change, map jump, replay, situation load) | P5 |
| U12 | Does an outside or replay camera page by the camera (assumed) or the aircraft? | §4.2 position | One leg in an external view orbiting ~10 km out | P3 |

## 12. Owner decisions and the questions left **[rev 2]**

Decided (2026-11-10): cap 100 GB; placeholder 512 px; one world switch +
per-tile pins; automatic fetch within visible distance; users select the
tiles they build; providers as today; hosting deferred (#1986); spawn and
jump reload automatically; airport cores kept sharp, downgraded last.

Left for the owner:

**[rev 5]** Both answered 2026-11-10: favorites count (10c (2), then one
disk budget 10d); the world switch defaults on (10c (3)).

1. Pins **outside** the cap (this spec's reading of "don't count against
   the cap's LRU"), or counted in it but never evicted?
2. The world switch's default once §14 P6 passes: on or off?
3. ~~The automatic reload after a jump **in the air** at speed (a stall
   mid-flight), or only on the ground and at a flight load?~~ **[rev 4]**
   Decided 2026-11-10: yes, also in the air.

## 13. Work items

**[rev 2]** Superseded by the implementation plan, §14.

## 14. Implementation plan **[rev 2, new]**

Every phase is a lane brief (Opus; effort per CLAUDE.md), synthetic first:
offline twins on fixtures, the flight-2 log as a replay, at most one real
build (P1a's). Every lane runs the tests `tools/blast.py` names for the
files it touches, the CI registry twins (`windows_text_io`,
`console_encoding`, `tile_failures`, `patch_env_classification`),
`test_no_airport_specific_code.py` (CYXY and HECA are test cases, never a
case in the code) and `tools/ratchets.py`. Each phase ends with one **CYXY
verification flight** the owner flies with the promoted recorder (the
flight-2 profile: spawn on the runway at CYXY, sit 1 min, climb to
~3,000 m, fly west ~100 km south of 61°N, return, land, sit 1 min):

    sudo python3 Ortho4XP/tools/xplane_reads/record_reads.py --check --pack <tile pack>
    sudo python3 Ortho4XP/tools/xplane_reads/record_reads.py --pack <tile pack> --minutes 30 --out <kit>/pN.jsonl
    python3 Ortho4XP/tools/xplane_reads/analyse_reads.py <kit>/pN.jsonl > <kit>/pN_report.txt

and registers the log with `frames.py register` beside the l1992 kit.

### P1a — Placeholder build mode (medium)

- **Extends:** `O4_Imagery_Utils` (download worker: tile box at
  `zl - drop`, `build_texture_from_tilbox`; `convert_texture` mask resize;
  `solve_color_field` / `color_field_path` freeze), `O4_DSF_Utils.build_dsf`
  (unchanged output; the queue carries the mode), `O4_Step_Reuse` (step-4
  inputs), `O4_Tile_Utils` (imagery record keys), `O4_Cfg_Vars`
  (`imagery_on_demand`, `placeholder_zl_drop` as expert keys; the rows
  land in P4 — if the parity or glossary twins refuse a key with no row,
  P1a adds hidden rows in both apps).
- **New:** `src/O4_Imagery_Placeholder.py` (the writer and the placeholder
  store), `src/O4_DDS_Tiers.py` (tier widths and zooms; a tier from a full
  DDS by `split_levels` / `build_header` / `assemble`, the kit's
  `make_placeholders.py` small path).
- **Acceptance (offline):** a placeholder build of the `make_mesh_dsf_fixture`
  tile has a DSF, `.ter` files and masks byte-identical to the full build's;
  every texture `is_whole` and 512 px; the frozen field file exists and a
  second convert does not rewrite it; toggling the mode re-runs step 4
  only; network-free with a fake provider (the `test_imagery_fetch_twin`
  pattern); `O4_DDS_Tiers` round-trip: a tier of a full DDS equals the
  full's levels byte for byte.
- **Closing build:** one CYXY tile build in placeholder mode
  (`build_airport.py CYXY --tile 60 -136`, `df -h` ≥ 30 GB first).
- **Flight (owner):** the placeholder pack in place of the CYXY tile.
  Pass: every test-tile load reads a whole 512 file, no X-Plane log errors,
  thresholds within ±5 % of flight 2's; answers **U1** and **U3** (one leg
  at a lower texture quality). Optional second flight on the HECA tile for
  **U2**.

### P1b — Promote the recorder (low)

- **Moves** the kit's `record_reads.py` and `analyse_reads.py` to
  `Ortho4XP/tools/xplane_reads/` with one `tools/INDEX.md` row under
  "Measurement discipline" ("what X-Plane loads, at what distance and mip
  level; owner-run under sudo; stdlib python3 ≥ 3.9") in the same commit.
- **Generalises:** `--pack DIR` (repeatable) replaces the kit's `_swaptest`
  folder rule and the `KIT` default (`--out` required); adds a
  "thresholds" section to the analysis (step-up distance per mip per zoom
  level, in km and in units of S, the §2.5 table); records
  `sim/time/framerate_period` (**U10**). Stays standard-library only and
  importable with no engine on the path (the owner runs it with
  `/usr/bin/python3`).
- **Acceptance (offline):** a twin replays a trimmed raw `fs_usage` text
  fixture through `--from-text` and checks the records; `analyse_reads` on
  a trimmed flight-2 JSONL fixture reproduces the band table and the
  threshold medians of §2.5. The kit's `swap.py` stays in the kit (P3
  replaces it).
- **Flight:** none of its own; P1a's flight is its proof.

### P2 — Index, downgrade, cap, cores and pins (medium)

- **Extends:** `o4_engine/storage.py` (`STORES` gains `ondemand` with the
  pins line, `storage_scan`, `_evict_to_cap` skips `upgraded`/`pinned`
  rows), `storage_redundant.py`, `O4_DDS_Cache.held_by_built_tiles`,
  `O4_Disk_Usage.freeable_bytes`, `O4_Imagery_Freshness.discard_tile_imagery`,
  `O4_Held_File`, `o4_engine/imagery_commands.py` (`imagery_pin`,
  `imagery_ondemand_downgrade_all`, `imagery_ondemand_scan`; protocol
  version bump).
- **New:** `src/O4_Imagery_OnDemand_Index.py` (schema of §5.1, rebuild from
  headers, `.ter` S and tile records), `src/o4_engine/imagery_downgrade.py`
  (§6.2), the core set per tile (from the airports its patches graded).
- **Acceptance (offline):** synthetic `textures/` folders: a rebuild
  restores every column but `last_near_at`; a random sequence of
  upgrades, downgrades and crashes (killed mid-land) never leaves a name
  missing or short (property test); the cap holds with 90/110 %
  hysteresis; nothing within 2 × tier distance of a fake camera is
  downgraded; pins never; cores only after every other row; Update Imagery
  on on-demand and pinned tiles.
- **Flight (owner):** P1a's pack, the tile pinned through the command
  (full set from `DDS_cache`), cap set to 1 GB, the sweep run with X-Plane
  at CYXY, then the profile. Pass: the recorder shows the downgraded
  squares opened as 512 files at their next step-up, the squares near the
  camera full, no log errors.

### P3a — Tier planner and its replay (high)

- **New:** `src/O4_Imagery_Tier_Plan.py`, pure: closest approach from
  position, track and speed; target tier; deadlines `c_k · S`; EDF queue
  with the cheapest-file rule of §4.3; `c_k` as named constants from
  §2.5 (one place to update after U2/U3).
- **Acceptance (offline):** replay flight 2's positions and loads
  (`flight2.jsonl` through P1b's loader): with simulated per-tier times
  from **U7**, at least 98 % of the recorded step-up opens would have found
  a file at least as fine as the level loaded; request rate and bytes per
  minute within 20 % of §4.3's estimates. **U6** and **U7** are measured
  here offline (fetch bench, lower-zoom ΔE).
- **Flight:** none; runs in parallel with P2.

### P3b — Follow job and Web API (medium)

- **Extends:** `o4_engine/imagery_commands.py` (`imagery_follow_start` /
  `_stop`), `o4_engine/events.py` (`ImageryFollowStatus`),
  `o4_engine/library.py` (pause while a build holds the lock),
  `O4_Imagery_Utils.download_jpeg_ortho` / `convert_texture` (tier zoom),
  `O4_Imagery_Fetch` (two in flight when a deadline is at risk).
- **New:** `src/O4_XPlane_WebAPI.py` (extracted from the recorder's
  poller; the recorder then imports it when present, so there is one
  implementation), `src/o4_engine/imagery_follow.py` (job loop: plan,
  fetch, land under §4.7, `last_near_at`, late counts, the 110 % sweep
  trigger).
- **Acceptance (offline):** a fake Web API server on a local port replays
  flight 2's track (and an id reset mid-track); a fake provider serves
  tiles; the job lands the planner's files in order, keeps the §8
  invariant, survives the id reset, pauses for a build lock, stops cleanly.
  The Swift client gains the event name in the same PR (wire protocol).
- **Flight (owner):** P1a's pack, follow job on (started by the engine
  command), the profile plus one high leg (**U4**) and one outside-view
  leg (**U12**). Pass: ≥ 98 % of step-up opens read a file at least as
  fine as the level loaded; `late` counted and paired with the recorder's
  next opens (**U5**); frame period unchanged within noise (**U10**);
  bytes per hour within 25 % of §6.4.

### P4 — Both apps: Settings, pins, status (medium)

- **Extends:** Mac `SettingsLayout.swift`, `SettingsView.swift`,
  `StorageSettingsView.swift`, `BuildModel+Storage.swift`,
  `ImageryModel.swift`, `OrthoEngineClient.swift`, the Library tile menu
  and info pane; Qt `O4_Qt_Settings.py`, `O4_Qt_Settings_General.py`,
  `O4_Qt_Settings_Storage.py`, `O4_Qt_Imagery_Menu.py`; `O4_Cfg_Vars`
  rows of §7; `test_qt_layout_parity.py` manifest; glossary parity.
- **Acceptance:** parity and glossary twins; settings round-trip through
  the cfg; the pin action calls `imagery_pin`; the status line renders
  every `ImageryFollowStatus` field; "Make all low-res again" names the
  space it frees.
- **Flight (owner, in the test app):** switch on, pin the CYXY tile from
  the Library, unpin it, fly the profile. Pass: the recorder shows the
  pinned tile all full, then the unpinned tile following the tiers.

### P5 — Spawn and jump (high)

- **Extends:** `o4_engine/imagery_follow.py` (witnesses of §4.5,
  core-first planning with the flight-start deadline), `O4_XPlane_WebAPI`
  (reload command if **U9** finds one).
- **New, only if U9 finds no command:** a minimal X-Plane plugin (C,
  `XPLMReloadScenery` on a request from the engine; per-OS builds; macOS
  signing and notarization alongside the app) — its own spec section
  before code.
- **Acceptance (offline):** replay of flight 1's flight-start sequence
  (all at mip 4, finer ~24 s later): cache hits land inside the window; one
  reload per jump, none when nothing missed it, none without network.
- **Flight (owner):** spawn at CYXY with its core downgraded; spawn at a
  point with no built airport; a map jump away and back. Pass: the field
  reads full files after the reload (or inside the window when cached);
  reload stall timed (**U9**); window measured across five spawns
  (**U11**).
- **[rev 4] Built** (lane `lp5`): §4.5 "P5 as built". U9 found the
  command, so no plugin and no plugin spec. Twins:
  `tests/test_imagery_spawn.py` on
  `tests/fixtures/imagery_spawn/flight1_start.replay.json` (flight 1's
  first 160 s, cut with `tools/imagery_tier_replay.py extract ... --window
  0 160`). For U11 the recorder log gives, per spawn, the seconds from
  `pos_resumed` to the mip 4 burst and to the finer burst; the job's
  `spawn=` / `spawn_done=` lines give its side.

### P6 — Windows and Linux (medium)

- **Extends:** `Ortho4XP/tools/xplane_reads/` (a Process Monitor CSV
  reader on Windows, an `strace` reader on Linux, feeding the same
  analysis), `O4_Held_File` (retry timing for the landing), the follow
  job's requeue on a held name.
- **Acceptance:** CI on Windows and Linux runs the P2/P3b twins; a swap
  stress with the kit's `swap.py` against a running X-Plane on each OS
  (**U8**).
- **Flight (owner or a tester with the hardware):** the CYXY profile on
  Windows and on Linux with the job on. Pass as P3b, plus the `os.replace`
  refusal count and the longest wait per landing. **[rev 5]** The default
  is already on (RULINGS 2026-11-10c (3): the hold was caution, not a
  requirement); P6 no longer gates it, and the owner may reverse it after
  the first flight.

### Order and parallel lanes

| Wave | Lanes in parallel | Needs |
|---|---|---|
| 1 | **P1a**, **P1b**, **P3a** (and P6's swap stress with the kit, if a Windows machine is free) | nothing; P3a reads flight 2 through P1b's loader (agree its interface first: `analyse_reads.load`) |
| 2 | **P2**, **P3b** | P1a (placeholder store, `O4_DDS_Tiers`), P1b (Web API poller to extract), P3a (planner); P3b reads P2's index schema, so P2 lands its schema module first |
| 3 | **P4**, **P5** | P2 and P3b commands and events |
| 4 | **P6** | P3b (and P5 for the reload on each OS) |

At most three lanes at once; one real build in the whole plan (P1a's
closing CYXY tile build). Six owner flights (P1a, P2, P3b, P4, P5, P6),
plus the optional HECA flight for U2.
