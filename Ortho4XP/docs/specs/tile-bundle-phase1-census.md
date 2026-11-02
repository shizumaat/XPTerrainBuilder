# Tile bundles, phase 1 — the census of what steps 3 and masks read (#1699)

Status: MEASURED 2026-11-02 (lane `plib1`, branch `claude/plib-phase1`).
Design: "Patch library: design and plan" (owner, final 2026-11-02, Q301–Q306
answered), phase 1. Issue #1699.

The question (design, phase 1): before a tile bundle can replace the
OpenStreetMap, elevation and lidar downloads, every file the **scenery-file
step** (step 3: imagery + DSF, `O4_Tile_Utils.build_tile` →
`O4_DSF_Utils.build_dsf`) and the **masks step** (`O4_Mask_Utils.build_masks`)
read must be named, so no hidden DEM or OSM read is missed.

## 1. Method

* **Traced, per step.** `build_airport.py KPDX --tile 45 -123 --trace-reads
  FILE` on the branch (tag `plib1_B2`). `corpus_snapshot.ReadTrace` now marks
  each release step as its own PHASE (`build_airport.run_tile_steps` →
  `corpus_snapshot.mark_phase`) and records, beside every file opened for
  reading and every folder listed, every outgoing connection
  (`socket.connect`, `socket.getaddrinfo`, `urllib.Request`) and every child
  process (`subprocess.Popen`).
* **Read statically where no audit hook sees.** GDAL opens rasters in C;
  DSFTool, 7-Zip and Triangle are child processes. Those readers were read
  in the source (§3) and their callers listed.
* **Proved by the gate.** `tools/tile_bundle_gate.py` imports the bundle into
  an EMPTY installation and runs step 3 there under the same trace plus a
  `LeakWatch` over the shared data repo, the source build and the owner's
  Custom Scenery (§4). A read the census missed is a leak, a network event or
  a different DSF there.

## 2. What was read (tile +45-123, Portland; `plib1_B2`)

Masks step (`3 masks`): 3 files, no folder listed, **no network**, no child
process.

| Read | Written by | Bundle |
|---|---|---|
| `<build>/Data+45-123.mesh` | mesh step | **carried** (`build/`) |
| `<build>/o4_unpatched_airports.json` | vector step | **carried** (`build/`) |
| `Utils/water_transition.png` | engine resource | engine |

Scenery-file step (`4 tile`): 787 files, 4 folders listed, **no network on
the source machine**, one child process (`/usr/bin/vm_stat`, a memory probe).

| Read | Written by | Bundle |
|---|---|---|
| `<build>/Data+45-123.mesh` | mesh step | **carried** |
| `<build>/Data+45-123.apt` | vector step | **carried** |
| `<build>/o4_unpatched_airports.json` | vector step | **carried** |
| `<build>/XPTerrainBuilder_+45-123.cfg`, the global cfg | the user | the user's (imagery provider, zoom, zones) |
| `<build>/textures/*.dds` (271) | imagery (this step) | **never** — the user's imagery |
| `<build>/terrain_staged_+45-123/*.ter` (502), `<dsf>.tmp` | this step itself | — |
| **`OSM_data/+40-130/+45-123/+45-123_coastline.osm.bz2`** | vector step's OSM cache | **THE HIDDEN OSM READ** — replaced, §3 |
| `VERSION.txt`, `src/O4_Build_Info.py`, `/proc/meminfo` | engine | engine |

No pack file, no Global Scenery file and no DEM file was opened by Python in
either step on this tile (its Global Scenery donor is not under the
configured overlay source, and it has no shoreline).

## 3. The readers no audit hook sees, and the hidden OSM read

| Reader (caller) | What it reads | When | Bundle |
|---|---|---|---|
| `O4_Bathymetry_Band._band_geometry` (via `ensure_bathymetry_band` ← `O4_DSF_Utils.synthesize_elevation_and_bathymetry_data` / `splice_measured_bathymetry`) | the tile's OSM **coastline** cache (and its `water` cache when there is a coast) — **an Overpass download on a cold cache** | every step 3 that has no Global Scenery donor, or `dsf_bathymetry=True` | replaced by the bundle's **`build/Data<tile>.dsf_inputs.npz`** |
| same, GDAL | the bathymetry band cells (`Elevation_data/<10°>/<stem>_bathymetry_band/*.tif`) through the band VRT | the tile has a shoreline | the band **warped to the DSF post grid** in `dsf_inputs.npz` (`measured`) |
| `O4_DSF_Utils.tile_elevation_post_grid` → `O4_DEM_Utils.DEM` | the base DEM | synthesis (no donor, a band) | the DEM **on the DSF post grid** in `dsf_inputs.npz` (`elevation`) |
| `O4_DSF_Utils.extract_elevation_and_bathymetry_data` (7-Zip child) | the installed Global Scenery DSF | a donor is installed | never — the user's own X-Plane install |
| `O4_Mask_Utils` → `ensure_bathymetry_band(fine_nearshore_only/intertidal_ok)`, `custom_dem` (GDAL) | coastline, band cells, DEM | `masks_use_DEM_too` auto/True on a coastal tile | the masks themselves are **carried** and the masks step is reused |
| `O4_Imagery_Utils` download queue | orthophoto servers | a texture is missing | the user's imagery, fetched by the user |
| object stage (`O4_Object_Stage.run` → `auto_patch.object_stage.rebake_after_mesh`), DSFTool child | the user's pack DSF, its `.anchor_bak`, the pack's DSFTool text dump in `Airport_mod_cache` | every import, and the end of every mesh step | the plans (`patches/o4_v2_rebake_*.json`, screens) are **carried**; the pack is the user's |

`O4_DSF_Data_Inputs` is the file: `band` (does the tile have a measured
bathymetry band), `measured` (float32 1201 x 1201) and `elevation` (int16
1201 x 1201), computed by the export exactly as step 3 derives them
(`O4_DSF_Data_Inputs.compute`), stamped with the bundle key, and read by
step 3 only for a tile whose vector-step record that bundle laid down
(`O4_DSF_Data_Inputs.bundled`). The Global Scenery donor is NOT carried.

## 4. The gate (closing test)

`tools/tile_bundle_gate.py --build OUT/plib1_B2 --world DIR` (numbers in the
lane report and `DIR/gate.json`): the DSF written in the empty installation
is compared byte for byte with the source build's; the trace of the import
and of step 3 there must hold no network event; `LeakWatch` must see no read
of the shared data repo, the source build's folders or the owner's Custom
Scenery.

## 5. Not covered by this census

* A tile WITH a shoreline (the band's `measured` / `elevation` grids and the
  masks step's coastal branch were read statically, not traced) — the next
  coastal build should run the gate once.
* `default_xplane` and `airport_ortho` texture modes (the default-terrain
  map reads Global Scenery) — the user's install, not a download.
* Overlays (step 4 of Ortho4XP, `O4_Overlay_Utils`) — not part of a tile
  build here.
