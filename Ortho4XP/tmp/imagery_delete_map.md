# Imagery / orthophoto DELETE-PATH ATTRIBUTION MAP

Lane `lane/imgharden`, 2026-08-14. Written BEFORE any code change.

Scope: every site in the engine that deletes a **user-visible imagery
artifact** (an orthophoto jpeg under `Orthophotos/`, a built `.dds`
texture in a scenery pack, a geotiff under `Geotiffs/`, a water mask
under `Masks/`) — plus the read sites that *decide* those deletions.

Reference incident: 2026-08-12, the app ran while a macOS TCC
volume-access dialog was killed unanswered; the engine ran in a
permission-denied window and the KCLT imagery was deleted.

---

## S1 — `O4_Tile_Utils.delete_incomplete_imgs` (src/O4_Tile_Utils.py:653)

**THE INCIDENT SITE.**

* Deletes: every orthophoto jpeg found anywhere under
  `FNAMES.Imagery_dir` (`Orthophotos/`) whose *basename* is in
  `IMG.incomplete_imgs[tile_coords]` (an `os.walk` of the WHOLE imagery
  tree — all tiles, not just this one), plus the same-stem `.dds` found
  anywhere under `tile.build_dir`.
* Trigger condition: `IMG.incomplete_imgs` is non-empty for the tile.
  Called from `build_all` (src/O4_Tile_Utils.py:584) between the two
  `build_tile` passes.
* `os.remove` here is **unguarded** (no try/except at all).

**Does a permission error reach it? YES — by two independent routes.**

Route A (the registration is written BEFORE the file is):
`O4_Imagery_Utils.download_jpeg_ortho` (src/O4_Imagery_Utils.py:1596)
appends `file_name` to `incomplete_imgs` at line 1644, on
`not success`, and only THEN tries `big_image.save(...)` (line 1651).
If the save fails — `except Exception` at line 1660, which is exactly
what an EPERM/EACCES write raises — the function returns 0 **with the
name already registered for deletion**. The bytes on disk are then the
user's ORIGINAL, healthy orthophoto, and S1 deletes it. Nothing in the
path ever read those bytes.

Route B (`success` is a *download* verdict, not a corruption verdict):
`success` comes from `parallel_execute` → `parallel_worker.run`
(src/O4_Parallel_Utils.py:291-300), which sets `success=0` on ANY
worker exception, including `PermissionError` from
`Image.open(url_local)` in the `local_tms` branch of `get_wmts_image`
(src/O4_Imagery_Utils.py:1285) and from
`_shared_tile_cache_get` (src/O4_Imagery_Utils.py:1192, bare
`except Exception: pass` → silent cache miss). A 404/403/timeout does
the same. None of these say anything about the artifact on disk.

**Amplifier — `os.path.isfile` reads EPERM as "absent".**
`build_jpeg_ortho` skips the download when the jpeg is already present
(src/O4_Imagery_Utils.py:1727 and :1793). `os.path.isfile()` swallows
`OSError` and returns **False** when the stat is denied. In a
permission-denied window the engine therefore concludes a healthy
orthophoto is MISSING, re-downloads it, white-fills the parts it cannot
get, registers it incomplete, and (save permitting) OVERWRITES it —
then S1 deletes it. "Cannot read" became "absent", then "corrupt".

**Verdict:** S1 + Route A is the mechanism of the KCLT deletion; the
`isfile` amplifier explains why a tile with complete imagery on disk
entered the download path at all. Deletion is lawful here ONLY for a
white-squared file the engine itself just wrote.

## S2 — `O4_Imagery_Utils.download_jpeg_ortho` registration (:1644)

Not a deleter; it is the site that *authorises* S1's deletion. Class:
error-class blind (registers before the write, and on a failure class
that proves nothing about the disk).

## S3 — `O4_Imagery_Utils.convert_texture`, geotiff pre-clean (:2237)

Deletes an existing `Geotiffs/<name>.tif` before regenerating it. Not
error-triggered (guarded by `os.path.exists`, which under EPERM returns
False and thus deletes nothing). Hazard is different in kind: if the
gdal conversion then fails (the 10-try loop at :2500 just logs), the
user's previous geotiff is gone. **Out of the permission-law scope —
recorded as DEFERRED, not changed in this lane.**

## S4 — `O4_Imagery_Utils.convert_texture`, mask + tmp removals
(:2324, :2373, :2480, :2527, :2532)

Deletes `build_dir/textures/<mask>.png` after imprinting it into the
dds, and the `Tmp_dir` png/tif scratch. Derived intermediates the same
run just produced; bare `except: pass`. No permission-triggered loss of
user data. No change.

## S5 — `O4_Tile_Utils.build_tile` cleaning sweep (:359-370)

`cleaning_level > 1` deletes `.png` under `build_dir/textures` and
rmtrees `build_dir/terrain`. Deliberate, level-gated pre-clean of
derived pack content; not error-triggered. No change.

## S6 — `O4_Tile_Utils.remove_unwanted_textures` (:600, remove at :627)

Deletes `.dds` in the pack not referenced by any `.ter`. The reference
set is read from `build_dir/terrain`; a denied `os.listdir` there
**raises** out of the function before any delete (and an empty/missing
dir returns early at :610), so a permission error cannot make it delete
a referenced texture. No change.

## S7 — `O4_Mask_Utils.delete_old_masks_in_tile` (:432)

Pre-clean of the previous run's masks before rewriting them. Already
error-class aware: `FileNotFoundError` silent, everything else
surfaces (the shared-repo-guard lesson at src/O4_File_Names.py:157).
No change.

## S8 — `O4_Imagery_Utils.initialize_local_combined_providers_dict` (:817)

Removes `.poly/.node/.1.node/.1.ele` triangulation scratch. Not
imagery. No change.

## Out of scope (recorded, not engine imagery)

* `Sources/XPTerrainBuilder/BuildPane.swift:472,606`,
  `BuildModel.swift:1070` — user-initiated pack removal, and they
  `trashItem` (recoverable), not `removeItem`.
* `Sources/SceneryKit/OrthoBuildRunner.swift:264` — deletes the engine
  job file on exit.

---

## THE CHANGE THIS MAP LICENSES

1. A read that FAILS is never evidence about the artifact. Add an
   error-class-aware presence probe: `absent` / `present` /
   `unreadable`, and make `build_jpeg_ortho` refuse loudly on
   `unreadable` instead of re-downloading over a file it cannot stat.
2. `incomplete_imgs` records only artifacts the engine **wrote** — the
   registration moves AFTER a successful save, and carries the exact
   path written. A save that failed (EPERM or otherwise) registers
   nothing.
3. S1 deletes only registered paths (and their derived dds), and its
   `os.remove` handles `PermissionError` by logging loudly and leaving
   the artifact in place.
