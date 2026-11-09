# Dynamic scenery loading: exploration (#1986)

Status: EXPLORATION, 2026-11-09 (lane `l1986`). Research only. No engine code
changed, nothing built. It is a private doc, so it holds the licensing
analysis (§6).

Scope (owner, 2026-11-09T19:04Z): dynamic scenery loading for X-Plane;
whether the grading and mesh work can be split from the imagery; a way to
build the world and keep it current so users can download it instead of
processing it locally; higher-resolution imagery loaded on the fly. Also
(owner, #1986 comment 18:54Z): learn from kubilus1/autoortho and
derekhe/xplane-map-enhancement-release, which the owner could not get
working on a Mac.

Every number is tagged **[measured]** (from this machine's records),
**[source]** (a cited page) or **[estimate]** (worked out here, with the
working shown). Anything about Laminar's unreleased engine is marked
**[speculation]**.

---

## Summary

| Question | Answer |
|---|---|
| 1. Prior art | Both use the same design: an Ortho4XP-built **mesh-only base pack** (DSF and `.ter` files, no imagery), plus a **FUSE virtual filesystem** mounted over each pack's `textures/` folder. When X-Plane reads a `.dds` file, the filesystem fetches map tiles and builds that DDS mip on the fly. AutoOrtho is open source (Apache-2.0). The original repo has been idle since 2024; the active fork is *AutoOrtho Continued* (3.0.3, 2026-11-03). XPME is closed source (.NET 10) with a paid "Pro" tier, and releases every few days. **On macOS, both projects' failures are in the FUSE layer** (macFUSE kext or FSKit, FUSE-T, mount helpers, unmount hangs) and in their packaging (Homebrew dependencies, a missing dylib). XPME's other big issue class is bad airport and terrain elevation in its base mesh, which is exactly what our engine does well. |
| 2. X-Plane today | DSF and `.ter` files are found when X-Plane starts and loaded tile by tile as you fly. A `.ter` file names its DDS texture. With `LOAD_CENTER`, X-Plane **re-reads the texture from disk at a new resolution as the distance changes**, which is the hook both tools exploit. A plugin **cannot** intercept terrain texture loading. It can read the aircraft position, and so can the built-in Web API (12.1.1 and later). Laminar announced a **Tile Scenery Engine** at FlightSimExpo 2026 (June 2026), described as tile and layer based, with LOD, streaming, more raster data and DSF compatibility, targeted for late 2026. There is no SDK yet **[speculation beyond that]**. |
| 3. Split the pipeline | It splits cleanly at step 3. The **vector, mesh and masks steps** (OSM, DEM and insets, the airport solve, triangulation, water masks) use no imagery and no imagery settings (`O4_Step_Reuse` already proves this). Step 3 only binds the textures. **A DSF can be built and shipped without imagery**: it records a texture *name* per triangle and *normalised* coordinates, so any pixel size of that DDS works. What gets fixed at build time is the **zoom-level grid** (which ZL16/17/18 texture tile each triangle uses) and the masks. The provider code in the name is only a label. The tile-bundle code (#1699 phase 1) already carries a tile's mesh, masks and solved airports to a machine with no OSM or DEM. |
| 4. World build | About **18,500 land tiles [estimate]**. Mesh-side wall time per tile on this Mac: median **562 s**, mean **1,055 s** (n=310) **[measured]**. That gives **1,500–5,400 machine-hours** per full world build, **~$250–$3,800** of cloud or rented compute **[estimate]**. Output is **~100–450 GB** **[estimate; AutoOrtho's whole world is 103 GB zipped, source]**. The cost of keeping it current is driven by what invalidates it, not by OSM churn. The tile-bundle key includes **each step's code digest** and the **Global Airports pack signature**, so today every engine release that touches step code and every X-Plane release that changes Gateway airports invalidates the bundles (§4.4). Tiles with a user's **custom airport pack** stay local: the patch library match, or a local solve, and then a local re-mesh of that tile. |
| 5. Distribution | Use **Cloudflare R2**: $0.015/GB-month, **egress free** **[source]**. That is **~$7–20/month** for 1–3 world versions, whatever the number of users **[estimate]**. B2 is cheaper to store but charges egress past 3× the stored bytes unless served through a partner CDN. Use content-addressed objects (sha256 names, immutable), plus one signed index per region (ed25519/minisign). An update downloads only the tiles whose hash changed. GitHub stays code-only (and the patch library's small entries, already ruled, §5.4). |
| 6. Imagery on demand | Show low resolution first, then refine near the aircraft. A ZL13 placeholder is 1/64 of the ZL16 bytes. **No commercial imagery may be hosted or redistributed by us**: the user's machine fetches from the provider, as today. Google's Map Tiles terms forbid prefetching and caching beyond what `Cache-Control` allows. The free and basic Bing Maps keys were retired on 2025-06-30. Open national orthophotos (NAIP, IGN, swisstopo, PNOA, PDOK and others) are the only imagery we could legally mirror. |
| 7. Recommendation | **Phase 0, the ruling asked for now:** one lane, no infrastructure, about 1 build. **(E1)** Measure a mesh-only bundle's compressed size on the HECA and CYXY tiles. **(E2)** Owner sim test: does X-Plane 12 pick up a DDS file *replaced on disk* at the next `LOAD_CENTER` reload? If yes, imagery on demand needs **no virtual filesystem on any OS**. **(E3)** Design a bundle "compatibility epoch" to replace the exact code digest. Then Phase 1: pre-built mesh for one region on R2 through the existing bundle import. Phase 2: imagery on demand. Phase 3: the world, kept current, plus an adapter for Laminar's engine. **Biggest risks:** Laminar's new engine moving the target; bundle invalidation forcing frequent world rebuilds; imagery terms; FSKit maturity if E2 fails. |

---

## 1. Prior art

### 1.1 AutoOrtho (kubilus1/autoortho) and AutoOrtho Continued

| | kubilus1/autoortho | ProgrammingDinosaur/autoortho4xplane ("AutoOrtho Continued") |
|---|---|---|
| Licence | Apache-2.0 [source: GitHub API] | Apache-2.0 [source] |
| State | Last release 0.7.2, 2024-01-21; last push 2024-10-27; 262 stars [source] | Active: 3.0.3 on 2026-11-03, releases weekly; 161 stars; 22 open issues [source] |
| Language | Python | Python plus a native C pipeline (`aopipeline`: libjpeg-turbo, OpenMP, BC1 compression) [source: docs/details.md] |
| Platforms | Linux, Windows; macOS "not supported" in practice | Linux, Windows, **macOS on Apple Silicon only** [source: README] |

**How it serves imagery** [source: `docs/details.md`]. The author states:
"There does not appear to be a way to hook directly into the internal
texture loading mechanism of X-Plane via plugins." AutoOrtho therefore mounts
a FUSE pass-through filesystem over each scenery pack's texture folder
(`Custom Scenery/z_ao_<region>/…` uses symlinks into the mount). It
recognises Ortho4XP's texture names `{row}_{col}_{maptype}{zl}.dds`. When
X-Plane reads a given **mip level** of a DDS, it downloads just the map tiles
that mip needs, decodes and compresses them, and returns the bytes. If a tile
is late it falls back to a lower zoom, and as a last resort a green tile
(`max_wait`). The Continued fork adds altitude-based dynamic zoom, ZL17
written into the ZL16 grid ("oversized ZL17 mipmap-zero"), a persistent DDS
cache with checksummed rows, prefetching along the route, and X-Plane 12
support [source: fork `docs/config.md`].

**What must be pre-built.** Regional **base packs** made with Ortho4XP using
`skip_downloads` (mesh, DSF, `.ter` and masks, no imagery), at ZL16 with
ZL18 around airports, plus `yAutoOrtho_Overlays` [source: `docs/details.md`,
`docs/scenery.md`]. The packs are hosted on **GitHub Releases** in
`kubilus1/autoortho-scenery`. The last world set (2023) totals
**≈103 GB zipped**: NA 25.8, ASI 33.2, EUR 16.8, AFR 12.3, SA 9.2,
AUS_PAC 6.2 GB [source: GitHub API, release asset sizes]. Those meshes are
plain Ortho4XP output **with no airport grading**. The fork's FAQ lists
"completely rebuild the Base Mesh packages with newer Ortho4XP versions" as
work in progress.

**Providers:** Bing, Google, EOX, ArcGIS, NAIP/USGS, and in the fork also
Yandex and Apple. They are fetched from the user's machine, with no account.

**Why it is hard on macOS** [source: issue trackers]:
- It needs a FUSE implementation. **macFUSE's kernel backend** requires
  enabling the kernel extension in recovery mode [source: macfuse.github.io,
  "no more rebooting into recovery mode" for FSKit]. **FSKit** (macFUSE 5.x,
  `-o backend=fskit`, libfuse3 only) needs macOS 26 for non-local volumes
  and is still being patched (5.5.0 mitigates "a data corruption issue in
  FSKit on macOS 26 and 27") [source: macFUSE release notes]. **FUSE-T**
  (kext-less, an NFS bridge) has non-standard terms, with a commercial
  licence for embedding [source: fuse-t.org].
- Issues: kubilus1 #593 "fuse: failed to start mount helper on macOS 26 /
  Apple Silicon", #563 "MacFUSE issues", #145 "Not running on MacOs".
  Continued fork: #457 "hangs on quit — mount worker stuck in lstat() …
  (macFUSE 5.4.0, macOS 27, M4)", #475 "taking hours to eject Macfuse",
  #463 and #452 FUSE-T detection, #444 "scenery cut-off / grey area during
  fast flight – macOS Apple Silicon". The fork had to write a whole
  `docs/macos-stability.md` about unmount deadlocks.
- Packaging: a PyInstaller app with a sidecar `ao_files/`. The native
  pipeline needs `brew install libomp jpeg-turbo curl` to build [source:
  fork docs]. The FAQ says macOS may kill X-Plane when the FUSE server
  stalls during loading ("Disabling multithreaded FUSE helps").

### 1.2 X-Plane Map Enhancement (derekhe/xplane-map-enhancement-release, "XPME", aiflygo.com)

| | |
|---|---|
| Licence | **Closed source.** The repo is "Only for release" and has no licence or source [source: GitHub API]. A commercial "Pro" tier exists: "Customized maps require the professional version" [source: aiflygo.com docs] |
| State | Very active: 4.7.27 → 4.7.31 between 2026-10-22 and 2026-11-06; 46 open issues; replies come from an "AI assistant" [source] |
| Stack | .NET 10 service (the ASP.NET runtime is required). **WinFsp** on Windows, **FUSE-T** on macOS, libfuse on Linux [source: aiflygo FAQ, download page] |
| Base packages | "**built with Ortho4XP**", ZL16, regional `XPME_*` packages. Hosted on QQ group files, Baidu Pan and GitHub Releases [source: aiflygo FAQ, download page] |
| Providers | Free: ArcGIS, Bing, Google. Pro: more sources, plus preloading, colour adjustment and higher-resolution ground [source] |

**How it serves imagery:** the same design as AutoOrtho. A local service
mounts virtual `textures` and `terrain` folders, and "map imagery is still
loaded on demand" [source: download page].

**Why it is hard on macOS** [source: issues]: #676 "macOS 27.2 – Host map
failed to start – Fuse-T 1.2.9" (log: "Host is missing entitlement:
com.apple.private.fskit.module-runner"); #673 "Adaptor.dylib is missing from
v4.7.29 package"; #680 "still times out when starting service. macOS";
#679 "XPlane becomes unresponsive … (Mac OS)"; #649 "Unable to start app
with Dotnet installed via Homebrew on Mac". The download page asks Mac users
to `brew reinstall sqlite libssh2 gettext aria2`, and Apple Silicon users to
check that Homebrew is under `/opt/homebrew`.

**Their other big issue class is our strength.** Base-mesh elevation is wrong
at airports and in terrain: #685 LIMJ, #681 CYHC, #666 BGSS, #663 SKBG,
#651 ZHSY, and #683 Mendig/Koblenz "regression from 4.2.0" (with no way back
to the old package). The official workaround is "Airport Flattening" or
regenerating the tile in Ortho4XP by hand. #662 has users asking for "a
page where everyone can share and improve the main airport mesh". That is
our patch library (#1699), unprompted.

### 1.3 What we reuse, and what we do better

| | Reuse | Do better |
|---|---|---|
| Design | Mesh-only base plus imagery bound when the sim reads it. Both projects prove it works in the field, at world scale. | **The base is our graded mesh** (airport solve, insets, masks), not plain Ortho4XP at ZL16. |
| Code | AutoOrtho is Apache-2.0, so it may be adopted into our GPL-3.0 engine with notice. Its ideas worth adopting: per-mip partial DDS builds, lower-ZL fallback, a JPEG and DDS disk cache with checksums. We already have our own DDS encoder, mips, cache and HTTP/2 fetcher (`O4_DDS_*`, `O4_Imagery_Async`, `O4_DDS_Cache`). | One provider stack and one cache for both builder and streamer. |
| macOS | — | **No kernel extension, no Homebrew, no third-party FUSE.** Either no filesystem at all (§2.4 E2), or a native **FSKit** module signed inside our notarised app. |
| Platforms | — | One app (Mac app plus Qt) with the same engine on Mac, Windows and Linux. |
| Distribution | — | Not GitHub Releases or Baidu: R2 with a signed index and delta updates (§5). |
| Updates | — | Users choose when to update, and old versions stay downloadable (XPME #683, #656, #669 complain about the opposite). |
| Airports | — | A pre-graded airport for Global Airports; the patch library or a local solve for custom packs (§4.5). |

---

## 2. X-Plane mechanics today

### 2.1 What loads when [source unless marked]

- **At start:** X-Plane reads `scenery_packs.ini` and indexes each pack's
  `Earth nav data/<10° folder>/<tile>.dsf`. A pack or DSF added later is
  seen only after a restart or a scenery reload. AutoOrtho's FAQ: start
  X-Plane *after* AutoOrtho "so that all new files and directories are
  picked up".
- **In flight:** DSFs for the tiles around the aircraft load asynchronously
  as it flies [source: AutoOrtho `details.md`]. The exact load radius in
  XP12 is not documented here **[estimate: a few tiles each way]**.
- **Terrain textures:** each terrain patch in a DSF names a `.ter` file. Our
  `.ter` (`O4_DSF_Utils.create_terrain_file`) holds `LOAD_CENTER <lat>
  <lon> <metres> 4096`, `BASE_TEX_NOWRAP ../textures/<x>_<y>_<prov><zl>.dds`,
  and for water a `BORDER_TEX` mask with `LOAD_CENTER_BORDER`
  [measured: code].
- **`LOAD_CENTER` is texture paging:** "X-Plane will load the texture with
  variable resolution based on distance from the user. X-Plane periodically
  reloads the texture as the user flies" [source: developer.x-plane.com,
  "limits on texture paging" / ".ter spec"]. DDS is recommended "so that
  reloads at lower resolution are fast". **This re-read from disk is the
  only hook AutoOrtho and XPME use**: they answer it with freshly built bytes.
- **Texture size:** the DSF stores per-vertex `s,t` coordinates normalised to
  0–1 over the texture tile (`GEO.st_coord`, scaled to 65535). The DDS
  pixel size is **not** baked in, so the same `.ter` can point at a 1024²,
  4096² or 8192² DDS [measured: code; source: AutoOrtho Continued serves ZL17
  into ZL16-grid DDS].

### 2.2 What a plugin can and cannot do

- **Cannot:** replace or intercept terrain texture loading [source: AutoOrtho
  author, quoted §1.1], or change a loaded DSF's mesh. XP12 renders with
  Vulkan and Metal, and the SDK exposes no terrain texture handles
  **[estimate, from the SDK as known; no counter-example found]**.
- **Can:** read the aircraft position, speed and flight plan (datarefs);
  trigger a full scenery reload (`XPLMReloadScenery`, which stalls the
  sim); place objects (`XPLMInstance`). **Without any plugin**, the
  built-in **Web API** on `localhost:8086` (REST plus WebSocket dataref
  subscriptions, since 12.1.1) gives a companion app the aircraft position
  [source: developer.x-plane.com/article/x-plane-web-api/].
- So any on-demand imagery must work **at the file level**: a virtual
  filesystem, or real files written ahead of the sim (§2.4).

### 2.3 The next-generation system

- **[source]** At FlightSimExpo 2026 (reported 2026-06-12), Laminar announced
  the **X-Plane Tile Scenery Engine**. The coverage paraphrases Laminar: a
  replacement for the DSF architecture; tile- and layer-based; LOD;
  streaming; "expanded raster data"; friendlier to GPUs; more detailed
  terrain editing; backward compatible with DSF. Targeting "late 2026" (an
  FSElite report quotes Ben Supnik aiming "before the end of 2026"). It comes
  after the SDK update, which comes first.
- **[speculation]** If "streaming" and "raster layers" include imagery
  layers that third parties can feed, a future XPTerrainBuilder could hand the
  sim imagery through a supported API, and the filesystem tricks become
  legacy. If the mesh format changes, our DSF writer (`O4_DSF_Utils`) gets a
  second adapter. The mesh and grading pipeline upstream of it (vector, mesh,
  masks, `auto_patch_v2`) does not depend on DSF. No SDK, format or date has
  been published as of this writing. Plan so that Phase 0 and Phase 1 pay off
  whichever way it lands (§7).

### 2.4 The open question that decides the architecture

Neither project tested whether imagery on demand needs a virtual filesystem.
Both assumed it does. A **no-filesystem** path is possible if X-Plane 12
re-opens the DDS from disk at each `LOAD_CENTER` reload (the documentation
says "periodically reloads"). If so:

1. At sim start, every texture a nearby DSF names exists as a small real
   placeholder DDS, for example 1024² from ZL14 imagery, ~0.7 MB as BC1 with
   mips **[estimate]**. The tile bundle could even ship tiny 256²
   placeholders (~43 KB each).
2. A companion process (the engine, driven by the Web API position) writes
   the full ZL16–18 DDS ahead of the aircraft and renames it over the
   placeholder atomically.
3. X-Plane's next paging reload reads the real file.

This needs **no FUSE, no FSKit, no WinFsp, no kext and no service that can
hang the sim**. The cache is just the textures folder, and eviction is just
writing the placeholder back. **Unverified:** whether X-Plane re-opens the
file or keeps a handle or in-memory copy; whether it accepts a changed pixel
size between reloads; how Windows behaves on rename over a file that is open
(§7 E2).

---

## 3. Splitting the pipeline

### 3.1 The real stages [measured: code]

`O4_Tile_Utils.build_all` runs four steps. The engine session calls them
`vector`, `mesh`, `masks` and `imagery` (`o4_engine/session.py` step table;
the `imagery` step is `TILE.build_tile`, "imagery & DSF"):

| Step | Entry (`O4_Step_Code.ENTRY_MODULES`) | Inputs | Reads imagery? |
|---|---|---|---|
| 1 vector | `O4_Vector_Map.build_poly_file`, `O4_OSM_Utils`, `O4_Airport_Utils`, `auto_patch.driver` (the airport solve, `auto_patch_v2`) | OSM (Overpass or local extracts, `O4_OSM_Extract_Filter`), apt.dat plus **the user's airport packs** (DSF, `scenery_packs.ini`), CIFP, cached elevation insets, `list_vector_vars` | **No** |
| 2 mesh | `O4_Mesh_Utils.build_mesh`, `O4_DEM_Utils`, `O4_Airport_Elevation_Insets`, `auto_patch.post_mesh` (incl. object stage rebake) | the vector outputs (`.poly`, `.node`, `.alt`), base DEM plus insets, `list_mesh_vars` | **No** |
| 3 masks | `O4_Mask_Utils.build_masks`, `O4_Bathymetry_Band` | `.mesh`, `o4_unpatched_airports.json`, `ratio_water`, `Utils/water_transition.png` | **No** |
| 4 imagery & DSF | `O4_Tile_Utils.build_tile` → `O4_DSF_Utils.build_dsf` (DSF encode) running alongside the download/convert queues (`O4_Imagery_*`, `O4_DDS_*`) | `.mesh`, `.apt`, masks, provider, `default_zl`, `zone_list`, `cover_zl`, `texture_mode`, `list_dsf_vars` | **Yes**: queues downloads; the DSF itself only names textures |

`O4_Step_Reuse` already rules on this (#615, owner 2026-10-12): "None of the
texture settings … is an input of any of the three". A rebuild that changes
only imagery re-runs only step 4. The tile-bundle census
(`docs/specs/tile-bundle-phase1-census.md`, #1699) traced the reads of steps
3 and 4. It found one hidden OSM read (the coastline cache, now carried) and
**no network access in the masks step**.

### 3.2 Where the time goes [measured: `~/.ortho4xp/tile_build_times`, 310 tiles, 2026-07-15 → 2026-11-09, last record per step]

| Step | p10 | median | p90 | mean |
|---|---|---|---|---|
| vector (incl. OSM fetch and airport solve) | 57 s | 452 s | 2,218 s | 897 s |
|   of which auto-patch solve (272 tiles with airports) | 31 s | 145 s | 1,250 s | 452 s |
|   vector, tiles with no airport (n=38) | 11 s | 42 s | 347 s | 120 s |
| mesh | 5 s | 22 s | 107 s | 73 s |
| masks | 5 s | 18 s | 189 s | 86 s |
| imagery & DSF | 21 s | 73 s | 495 s | 234 s |
| **mesh side (vector+mesh+masks)** | 87 s | **562 s** | 2,572 s | **1,055 s** |
| total | 142 s | 791 s | 3,130 s | 1,287 s |

Caveats: the sample leans towards airports (owner's case airports, a median of
2 airports per tile) and towards a **warm imagery cache** (the shared
`Orthophotos`/`DDS_cache`; 155 of 306 tiles downloaded anything, median 125 s
of download when they did). Even so, **the mesh side is about 70 % of a
user's median local build**. A pre-built mesh removes most of a user's wait
even before imagery streams.

### 3.3 Can a mesh-only DSF be shipped, with imagery bound later?

**Yes.** This is standard Ortho4XP practice (AutoOrtho's docs:
"`skip_downloads` … perfect for this project"). In our engine,
`build_dsf` only *queues* a texture whose DDS is not whole (`download_queue.put`).
The DSF encoding does not read any DDS [measured: code]. A no-download switch
for step 4 is a small engine change (Phase 1). `texture_mode=default_xplane`
DSFs use no imagery at all and are shippable as they are.

What gets **baked in** at DSF time, and what follows from it:

| Baked into the DSF or `.ter` | Consequence | Fix |
|---|---|---|
| The **ZL grid partition**: each triangle's texture tile `(x, y, zl)` from `default_zl`, `zone_list` and `cover_airports_with_highres`/`cover_zl` (`dico_customzl`) | The shipped mesh fixes *which* grid tiles exist; the user cannot change zones without re-running step 4. | Ship one standard grid: ZL16 everywhere, ZL17/18 cover at airports (as AutoOrtho does). Higher detail comes from **bigger DDS for the same grid tile** (8192² = ZL17 detail in a ZL16 tile; X-Plane caps at the GPU's maximum texture size). |
| The **provider code** in texture names (`…_BI16.dds`) | A label only. | The runtime maps any provider to that name (AutoOrtho does this). Use a neutral code. |
| **Water masks** (`BORDER_TEX` per grid tile) and airport fade masks | Derived from the mesh and OSM, not from imagery. | Ship them (the bundle already carries `masks/`). |
| `imprint_masks_to_dds` (mask burned into DDS alpha) | Would need the mask at imagery time. | Runtime DDS synthesis applies it, or shipped meshes always use the `BORDER_TEX` path. |
| Colour filters, harmonisation, per-zone providers | Imagery-only. | They move to the runtime. |
| The **object stage** (it rewrites the user's pack DSFs: rebake plans) and `O4_Mesh_Order` | Depend on the user's installed packs. | Always local. The bundle carries the plan, and the object stage runs locally (already so for bundles). |
| `.ter` `LOAD_CENTER` size `webmercator_pixel_size × 4096` | Assumes 4096 px. | Harmless: it is a paging hint, and AutoOrtho ships 4096 while serving 8192. To verify in E2. |

### 3.4 What exists already

- `src/tile_bundle/` (#1699 phase 1): `export`, `importer`, `key`,
  `contents`, `paths`. A bundle carries `build/Data<tile>.mesh`, `.apt`,
  `o4_unpatched_airports.json`, `dsf_inputs.npz`, `patches/` (solved
  patches, graded surface, rebake plans, anchor worklist) and `masks/`. It
  **forbids** `.dds`, `.dsf`, `.ter`, `.node`, `.poly`, `.alt` and pack
  files. The importer writes the vector step's record
  (`O4_Step_Reuse.adopt_bundle_record`) so that steps 1–3 are reused and only
  step 4 runs. `tools/tile_bundle_gate.py` proves an import into an empty
  installation produces the same DSF byte for byte, with no network access.
- `src/patch_library/` (#1699 phase 2): per-airport entries on public GitHub
  with match keys, per-source licence terms (`terms.py`: allowed /
  noncommercial / held), sha256 checks and size caps.

So **a portable, imagery-free, key-matched mesh package already exists**.
What is missing for "download the world" is: building bundles for every tile
in the cloud; a bundle key that survives an engine release (§4.4); hosting;
and choosing which DSF-ready variant to ship (the bundle, or the DSF plus
`.ter` themselves, §5.2).

---

## 4. Building the world and keeping it current

### 4.1 Size of the job

- **Tiles [estimate]:** ~18,500 land 1°×1° tiles (X-Plane's global
  scenery covers about that many; dropping Antarctica and the ice caps
  removes ~10 %).
- **Airports:** XP12's apt.dat has ~35–38k airports **[estimate]**, so about
  2 per land tile on average, close to the ledger's median of 2.
- **Per-tile mesh-side time [measured]:** median 562 s, mean 1,055 s on this
  Mac (Apple Silicon, ~12 cores; the ledger includes OSM and DEM fetches,
  which a world build replaces with local planet extracts).

### 4.2 Compute [estimate]

| | Low | High | Working |
|---|---|---|---|
| Machine-hours | 1,500 | 5,400 | 18,500 × 300 s (mostly rural tiles) … 18,500 × 1,055 s (the ledger mean, airport-heavy) |
| Cloud on-demand, 16 vCPU Arm (~$0.55–0.70/h) | $830 | $3,800 | — |
| Cloud spot (~$0.20–0.30/h) | $300 | $1,600 | — |
| Rented dedicated (Hetzner-class, 16-core, ~€100/month each) | ~€250 | ~€800 | 4–8 boxes for a month |
| Calendar time | ~1 week | ~1 month | with 8–30 machines in parallel |

The engine has not been timed on Linux at world scale. **±2× uncertainty.**
Outliers dominate the tail: the HECA solve alone took 2,182 s in the
auto-patch ledger [measured: `~/.ortho4xp/auto_patch_build_times`, 136
airports, median 37 s, p90 183 s; last record 2026-10-19].

Inputs at world scale: the OSM planet PBF (~80–90 GB **[estimate]**, refreshed
from replication diffs, never Overpass); the base DEM (viewfinder grid,
Copernicus GLO-30 or similar; several hundred GB **[estimate]**); airport
insets (this repo's `O4_Airport_Elevation_Insets` providers, per-source
terms). For scale, the owner's corpus here is 114 GB of OSM and 74 GB of
elevation for ~344 tiles [measured: `du`].

### 4.3 Output size

| Item | Per tile | Source |
|---|---|---|
| DSF | median 9.5 MB, mean 16.8 MB, p90 46.5 MB | [measured] 2,552 Ortho4XP tiles in the owner's Custom Scenery |
| `.ter` | median 353 files of ~0.3 KB | [measured] same |
| masks | mean 6.7 MB (coastal and water tiles only) | [measured] `XPTerrainBuilderData/Masks`, 74 tiles |
| airport patches and plans | a few MB per airport tile (2.9 MB compressed entry → 32 MB raw) | [measured] `patch-library-phase2-20261102.md` |
| **World** | **~100–450 GB** | [estimate] 18,500 × 6–25 MB; AutoOrtho's world, zipped: **103 GB** [source] |
| For contrast: imagery | median **2.7 GB**, mean 3.5 GB per tile | [measured] the same 2,532 tiles: **~8.8 TB** on the owner's disk |

Imagery is ~99.5 % of today's bytes. Streaming it is what removes the
storage problem.

### 4.4 Keeping it current: what changes, how often, what it invalidates

| Input | Changes | Detection | Invalidates |
|---|---|---|---|
| OSM | continuously (minutely diffs); the *filtered* subset (water, coastline, aeroways, levelled roads) far less | the hash of each tile's **filtered** extract, which the vector step already keys on (`O4_Step_Reuse` early cutoff) | that tile only. Churn per quarter is **unknown**: measure it (Phase 1) |
| Coastline | processed coastlines updated daily upstream | hash | coastal tiles |
| Global Airports (Gateway) | **each X-Plane update** ships a new Gateway export (several a year) | the pack signature (`pack_identity.pack_signature`: apt.dat block hash, DSF hash, flatten) | every tile whose airport block changed (the key covers all of a tile's graded airports) |
| Base DEM | almost never (static releases) | file hash | everything, rarely |
| Elevation insets (national lidar) | agencies add coverage yearly or so | the inset cache hash (already a vector-step input) | the tiles of affected airports |
| **Engine code** | every release that touches a step's import closure (vector 458, mesh 468, masks 476 of 584 modules: `O4_Step_Code`) | `key.first_difference` → "this app's … step code is not the bundle's engine's" | **every bundle in the world**, as the key is written today |

The last row is the main design problem, and it is ours. For a local cache,
keying on the exact code digest is correct (#346: no stale step ever). For a
distributed world it means a full world rebuild per app release. Phase 0 E3
should design a **compatibility epoch**: a bundle format version plus a law
version that the engine bumps only when an output-affecting change is
intended. Pair it with a CI gate that replays a fixed set of tiles and fails
when outputs move without the epoch moving. The patch library already
follows this idea: an entry "names the oldest engine version it needs"
(#1699 concept, Q13).

### 4.5 The custom airport pack problem

Grading reads the user's installed pack: its apt.dat block, its DSF, and its
flatten declaration. That is why the bundle key holds **pack signatures**.
The split is:

| Case | Pre-built in the world? | Local work |
|---|---|---|
| Every airport in the tile is the default Global Airports for that X-Plane version | **Yes**: one world build per X-Plane Gateway export | Only the object stage (rebake into the user's packs) |
| A tile with a custom pack, and the patch library has an exact match | No | Apply the library entry (skips the solve), then **re-mesh the tile**: vector-step finish, mesh, masks, DSF |
| A tile with a custom pack, no library match | No | Local solve (median 145 s, p90 1,250 s [measured]), then re-mesh |
| A tile whose bundle is from an older Gateway export than the user's X-Plane | Not by an exact match | Wait for the world build, or build locally |

Re-meshing needs the vector step's inputs (filtered OSM, DEM and insets),
which a bundle does not carry today. Two options: (a) the app downloads OSM
and DEM for only those tiles, as it does today; or (b) a second bundle
variant, **re-meshable**, that also carries the filtered OSM cache and the
DEM and inset grids (where `terms.py` allows the source). A typical user has
10–100 custom airports, so 10–100 tiles stay local; the rest of the world
downloads.

---

## 5. Distribution

### 5.1 Cost model [source for unit prices; estimate for totals]

| | Cloudflare R2 | Backblaze B2 |
|---|---|---|
| Storage | $0.015/GB-month (10 GB free) | $6.95/TB-month |
| Egress | **free** | free up to 3× average stored; then $0.01/GB; free to partner CDNs (Cloudflare) |
| Reads | $0.36 per million (Class B) | free-ish (API classes) |

World of 450 GB, 3 versions kept (1.35 TB):

| Users × monthly download | R2 | B2 direct | B2 behind Cloudflare |
|---|---|---|---|
| 1,000 × 40 GB (40 TB) | ~$20 storage + ~$1 reads | ~$9 + ~$360 egress | ~$9 |
| 10,000 × 40 GB (400 TB) | ~$20 + ~$7 | ~$9 + ~$4,000 | ~$9 |

**R2 is the default.** Its cost does not grow with users. (A 40 GB/user
month is a heavy case, roughly one region plus updates. Objects of about
20 MB.)

### 5.2 What is shipped

- **Unit:** one object per tile, content-addressed (`sha256/<hash>.tar.zst`),
  immutable, cacheable forever. Two forms are possible: (i) the existing
  **tile bundle**, which the app turns into a DSF by running step 4 locally
  in seconds (encoder ~27 s per tile without imagery); or (ii) a
  **DSF-ready pack** (DSF, `.ter`, masks, plan) that needs no engine work.
  (i) keeps one code path and the existing gate. (ii) is lighter for users
  who only want imagery streaming. **Recommend (i)** for Phase 1.
- **Index:** one JSON per region per release: tile → hash, size, key parts
  (Gateway export, epoch), date. Signed with ed25519 (minisign or
  signify). The public key is pinned in the app. The app verifies the index,
  then each object's sha256. That matches the patch library's sha256 and
  size checks.
- **Delta updates:** compare the new index with the installed one and
  download only the changed hashes. A binary delta inside a tile (`zstd
  --patch-from`) is an optimisation for later.
- **Choice and rollback:** keep N previous indexes, and let the user pin one
  (XPME's forced updates are a recurring complaint).

### 5.3 Discovery and trigger

- Integrate it with the existing import path: a "Download prepared tiles"
  action next to Build, keyed per tile. The app computes its own key (pack
  signatures and epoch), so a match is exact or not offered at all.

### 5.4 GitHub

Code only. **Note for the owner:** the patch library (#1699 phase 2,
owner-ruled 2026-11-02) puts airport entries (MB-scale, text-heavy) in a
public GitHub repo. That remains within GitHub's purpose. World tiles
(hundreds of GB, binary) must not go there: AutoOrtho hosts 103 GB on
GitHub Releases, which is what the owner's "GitHub only for code" rules out.

---

## 6. Imagery on demand

### 6.1 Low-res first, refine by view [estimate]

- A ZL16 texture is ~256 map tiles (256²), ~4–6 MB of JPEG, and ~11 MB as
  BC1 DDS with mips. A median tile needs ~234 textures, so the **first visit
  costs ~1–1.5 GB** to download at ZL16.
- A ZL13 placeholder for the same grid tile is 1/64 of that (~20 MB per 1°
  tile). With EOX Sentinel-2 cloudless (10 m) the placeholder layer can come
  from one source worldwide.
- Order of refinement: placeholders for the load ring at sim start, then
  ZL16 inside ~10 km of the aircraft or along the flight plan, then ZL17/18
  at airports below ~3,000 ft AGL (AutoOrtho Continued's altitude steps are
  the precedent). Position comes from the Web API.
- Mechanism: the no-filesystem placeholder swap if E2 passes (§2.4).
  Otherwise a filesystem per OS: **FSKit** on macOS (a signed app
  extension; `FSPathURLResource` since macOS 26; no kext; young, with known
  gaps and a FSKit data-corruption mitigation in macFUSE 5.5 [source]);
  **WinFsp** on Windows (GPLv3 with FLOSS exception, so it fits our GPL
  engine; **[estimate]** ProjFS hydrates whole files, a poor fit for
  mip-level reads); **libfuse3** on Linux.

### 6.2 Licensing (private analysis; not legal advice)

| Source | Terms relevant to streaming and caching | Consequence |
|---|---|---|
| Google (Map Tiles API) | "you must not pre-fetch, index, store, or cache any Content except under the limited conditions stated in the terms"; caching only as `Cache-Control` allows; attribution required [source: developers.google.com/maps/documentation/tile/policies] | A persistent DDS cache or route prefetch from Google is outside the terms. The scraping endpoints Ortho4XP-family tools use are not the licensed API at all. |
| Bing Maps | free and basic keys stopped on 2025-06-30; enterprise keys run until 2028-06-30, then move to Azure Maps [source] | The current Bing tile endpoint has no stable licensed footing. |
| Esri World Imagery (ArcGIS) | needs an ArcGIS account and terms for basemap use; offline use requires a licence **[estimate; terms not re-read here]** | Same as Google: user-side fetch only. |
| Mapbox Satellite | paid per request; caching rules are in Mapbox's terms **[estimate]** | Possible as a user-supplied key (Pro-like). |
| EOX Sentinel-2 cloudless | 2016 mosaic CC BY 4.0; later years CC BY-NC-SA 4.0 **[estimate; verify on eox.at]** | Fine for a non-commercial low-res placeholder with attribution. |
| Open national orthophotos: NAIP and USGS (public domain), IGN France (Etalab 2.0), swisstopo (OGD), PNOA Spain (CC BY 4.0), PDOK NL, basemap.at and others (CC BY) **[estimate per licence; verify each]** | redistribution allowed with attribution | The **only** imagery we could pre-process and mirror on R2 ourselves. The storage is large (tens to hundreds of TB at full resolution), so not in Phase 1. |

Position: XPTerrainBuilder never hosts, mirrors or redistributes commercial
imagery. The user's machine fetches it, exactly as local builds do today.
Streaming does not change who fetches. It does change **how long the cache
keeps imagery and whether we prefetch**, and Google's terms bar both. The
streaming component should apply per-provider cache rules (honour
`Cache-Control` where terms require it) and show attribution. The
`patch_library/terms.py` pattern (allowed / noncommercial / held per source)
is the model for a per-provider streaming policy table. The mesh we
distribute is an OSM-derived Produced Work under ODbL (attribution: "©
OpenStreetMap contributors"). The base DEM's terms (viewfinder panoramas'
redistribution terms are not stated clearly) need the same `terms.py`
classification before a world release.

---

## 7. Recommendation

### Phase 0: rule now (one lane, ~1 build, no infrastructure)

- **E1, size and fidelity.** Export tile bundles for the HECA tile (the
  owner's site) and CYXY (the cheap control) from one build. Record the
  compressed bytes, and the DSF, `.ter` and mask bytes. Run
  `tile_bundle_gate.py` on each. Confirms §4.3 on our own mesh.
- **E2, the hot-swap test** (owner sim read, ~15 minutes). On CYXY: a DSF
  built with **tiny placeholder DDS** (256², ZL16 names). In flight, the
  engine renames full ZL16 DDS over the placeholders near the aircraft.
  Observe: does the sharp imagery appear without a reload? After how long?
  Does an 8192² file in a 4096 `LOAD_CENTER` work? Any stutter or error in
  `Log.txt`? Repeat once on Windows. **This one result decides between "no
  filesystem anywhere" and "three native filesystems".**
- **E3, the compatibility epoch.** A short spec, not code: replace the
  code-digest field of `tile_bundle.key` for *distributed* bundles with
  `(bundle format, law epoch)`, plus a replay gate that fails when outputs
  move without the epoch moving. The local cache keeps the exact digest.
- **Owner decisions to ask:** (a) is a hosted world in scope (cost: ~$10–30
  a month to host, plus ~$300–3,800 per world rebuild)? (b) region first:
  the owner's flying area, or where users are? (c) streaming of commercial
  providers only on the user's own keys and terms, or not at all?

### Phase 1: pre-built mesh for one region (after Phase 0)

The no-download switch for step 4; the compatibility epoch; a
cloud or rented build of one ~10°×10° region at the default profile against
the current Global Airports; bundles on R2 with a signed index; "Download
prepared tiles" in both apps (Mac and Qt, per the layout parity rule);
measure OSM churn by hashing filtered extracts from two planet snapshots.
Imagery is still built locally by step 4. That alone removes ~70 % of a
user's median local build time [measured, §3.2].

### Phase 2: imagery on demand

Whichever mechanism E2 chose. Placeholders first, then refinement driven by
the Web API position. One provider stack and cache shared with the builder
(`O4_Imagery_*`, `O4_DDS_*`). Per-provider streaming policy (§6.2).

### Phase 3: the world, kept current

A scheduled world build: monthly for OSM-driven changed tiles, and on each
X-Plane Gateway export for airport tiles. Old releases stay downloadable.
An adapter for Laminar's Tile Scenery Engine once its SDK is published.

### Biggest risks

1. **Laminar's Tile Scenery Engine** (late 2026 target) may supersede DSF and
   the filesystem trick, or offer supported streaming. Mitigation: Phases 0
   and 1 build the engine-independent part (graded mesh as data, plus
   distribution). Hold Phase 2's filesystem work until E2 and Laminar's SDK
   are known.
2. **Bundle invalidation**: the exact code digest plus Gateway churn make
   distributed bundles go stale on every release (§4.4). E3 addresses it.
   Without it, the world is rebuilt per app release.
3. **Imagery terms** for streaming and caching (§6.2), with Bing's free
   access gone. The product can stream only what users may fetch.
4. **Filesystem maturity on macOS** if E2 fails: FSKit is young, and
   AutoOrtho's and XPME's trackers are dominated by mount, unmount and
   service bugs.
5. **Distribution licence of the mesh inputs** (ODbL attribution; base DEM
   terms) must be cleared before a public world release.
6. **Support load**: the prior art shows the streaming component, not the
   mesh, generates most issues.

---

## Sources

- kubilus1/autoortho: repo and API metadata; `docs/details.md`, `docs/faq.md`,
  `docs/scenery.md`; issues #34, #145, #470, #539, #563, #593 —
  https://github.com/kubilus1/autoortho
- kubilus1/autoortho-scenery: release asset sizes —
  https://github.com/kubilus1/autoortho-scenery/releases
- ProgrammingDinosaur/autoortho4xplane: README, `docs/config.md`,
  `docs/faq.md`, `docs/macos-stability.md`; issues #444, #452, #457, #462,
  #463, #475 — https://github.com/ProgrammingDinosaur/autoortho4xplane
- derekhe/xplane-map-enhancement-release: repo metadata; issues #649, #656,
  #659, #662, #663, #666, #673, #676, #679–#685 —
  https://github.com/derekhe/xplane-map-enhancement-release
- XPME docs: https://www.aiflygo.com/docs/xplane-map-enhancement/ ,
  …/download/ , …/faq/
- macFUSE: https://macfuse.github.io ; macFUSE 5.x release notes (FSKit
  backend, `-o backend=fskit`, 5.5.0 FSKit mitigation)
- FUSE-T: https://fuse-t-org.pages.dev/ , https://github.com/macos-fuse-t/fuse-t
- Apple FSKit: https://developer.apple.com/documentation/fskit ;
  FSPathURLResource (macOS 26) and forum thread 799283
- X-Plane texture paging: https://developer.x-plane.com/2008/06/limits-on-texture-paging/ ,
  https://developer.x-plane.com/article/terrain-type-ter-file-format-specification/ ,
  https://developer.x-plane.com/2011/03/three-things-you-need-for-fast-orthophotos
- X-Plane Web API: https://developer.x-plane.com/article/x-plane-web-api/
- Tile Scenery Engine: https://thresholdx.net/fsexpofriday-2026-laminar-research-announces-new-x-plane-12-scenery-engine/ ,
  https://fselite.net/content/x-plane-12-shows-new-updates-live-at-flight-sim-expo-2026/ ,
  https://fsnews.eu/x-plane-announces-new-sdk-panel-graphics-and-scenery-update-at-fsexpo-2026/
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Backblaze B2 pricing: https://www.backblaze.com/cloud-storage/pricing
- Google Map Tiles policies: https://developers.google.com/maps/documentation/tile/policies
- Bing Maps for Enterprise retirement: https://learn.microsoft.com/en-us/bingmaps/getting-started/
- This repo: `src/O4_Step_Code.py`, `src/O4_Step_Reuse.py`,
  `src/O4_Tile_Utils.py`, `src/O4_DSF_Utils.py` (`create_terrain_file`,
  `dico_customzl`, `build_dsf`), `src/tile_bundle/*`, `src/patch_library/*`,
  `docs/specs/tile-bundle-phase1-census.md`,
  `docs/specs/patch-library-phase2-20261102.md`; ledgers
  `~/.ortho4xp/tile_build_times/` and `~/.ortho4xp/auto_patch_build_times/`.
