# #1521 / #1522 / #1523 — 1.0.433 sluggishness (lane lqueue, 2026-10-27)

Queue went grey for up to a minute (#1521). The console showed `[pav-builder] … apt.dat` lines
for airports in other tiles (#1522). Patches did not load on zoom during a build (#1523). A built
tile (SPJC) read "Build this tile first". The owner also said "the whole app is sluggish next to
1.0.432".

## Attribution

1.0.433 (da85f5493) added the Airports card (#818, `o4_engine/build_airports.py`; absent at
1.0.432 cfb3f11d9). Each selection change starts an engine thread. That thread runs the build's
own tile selection (`auto_patch.selection.select_patch_airports`) for every selected tile, then a
full Custom Scenery pack scan. The boundary preflight runs on every Build or Queue press and does
the same selection. Before this fix, none of it was remembered between calls:

- `cifp.discover_cifp_airports` and `read_threshold_dicts` re-read all ~11,000 CIFP files per tile.
- `apt_dat.find_apt_dat` lists Custom Scenery (4,000+ entries) for every in-tile airport.
  `O4_Scenery_Packs.enabled_pack_names` isdir's each entry, and each pack's apt.dat is stat'ed.
  Only the per-file block index `_BLOCK_INDEX` was cached.
- `O4_Custom_Scenery.scan_packs` lists every pack's DSF folders and parses every pack apt.dat.
- An older card thread was never stopped, so the threads piled up. All of them run in the engine
  process, beside the in-process build and the read loop, where `patch_list` and `patch_load`
  answer synchronously.
- The `[pav-builder]` lines are `build_support._pick_best_apt_dat_against_osm`'s `UI.vprint`,
  printed by these preview threads. That is real repeated work, not a log oddity.
- The map's built-tile `scan` walks 2,521 tiles in 23 s. `O4_Tile_Info._imagery_date` stat'ed
  every texture twice, about 850,000 files. While the scan runs, the patch panel read "no entry
  yet" as "not built".

## Rule (no law change; RULINGS 2026-09-18b/18i boundary ask unchanged)

**Caches.** A preview ask reads from caches, which re-read when the file moves:

- `cifp._THRESHOLDS`: per file, keyed by (mtime_ns, size). Callers get copies.
- `cifp._DIRECTORY`: keyed by the directory's mtime.
- `apt_dat._SELECTION`: the ICAO → apt.dat map beside `_BLOCK_INDEX`. Its key is the identity of
  the Custom Scenery folder, `scenery_packs.ini` and the Global Airports candidates, plus the
  chosen file's own identity. Limit: an apt.dat edited in place inside an existing pack does not
  invalidate it.
- `O4_Custom_Scenery._PACK_AIRPORTS`: per pack apt.dat.

The build reads the same caches.

**Superseding and silence.**

- A newer card supersedes an older one (`build_airports._GENERATION`). The older one stops at
  its next tile; the Qt card passes `live=` too.
- Preview asks print nothing (`O4_UI_Utils.quiet_thread`). This covers the boundary preflight
  worker and `build_airports.build_airports`, which both apps call.

**Queue.** While a run is going, Queue stays live:

- A press made while a preflight is in flight waits in line (`O4BoundaryPressQueue`). It then asks
  its own question, so each press keeps one dialog.
- While idle, a second Build press is still refused.
- Qt already allowed presses during a run.

**Scan and patch panel.**

- The scan stats each texture once (`os.scandir`).
- The patch panel says "Checking which tiles are built…" while the scan runs (Swift `.checking`,
  Qt `CHECKING`). It says "Build this tile first" only after the scan.

**UI (owner 2026-10-27).** The Airports card's explanations sit behind an "i" button in both apps.

## Measurements

The probe ran from `Ortho4XP/` in one process, with the owner's real install (CIFP, Custom
Scenery) and the lane Patches copy. "Contended" means one GIL-holding Python thread, two card
threads (for 1 and 2 tiles) and one Queue preflight (for +61-151 and +61-150), all at once.
Sibling lanes were also loading the CPU. These are coarse single runs, not timing A/Bs.

| | 1.0.432 | 1.0.433 | branch |
|---|---|---|---|
| card, 1 tile, cold / warm | n/a (no card) | 14.1 s / 9.7 s | 7.3 s / **0.33 s** |
| Queue preflight, 2 tiles, idle cold / warm | 20.1 s / 7.5 s | 15.8 s / 7.5 s | 7.5 s / **1.2 s** |
| Queue preflight answered, contended | 27.0 s | 32.2 s | **6.2 s** |
| all preview threads done, contended | 27.3 s | 51.1 s | **6.9 s** |
| worst `patch_load` (read loop), contended | 1.20 s | 2.06 s | **0.39 s** |
| worst `patch_list`, contended | 0.50 s | 0.60 s | 0.47 s |
| built-tile `scan`, 2,521 tiles | 23.0 s | 22.9 s | **17.3 s** |

An earlier contended run on 1.0.433 code with two card threads took 82.7 s for all preview
threads, with a worst `patch_load` of 5.0 s.

No real airport was built for this change; it touches no geometry.

Twins:

- Engine: `tests/test_preview_responsiveness.py` (caches, quiet, supersede, bounded `patch_list`).
- Qt: `tests/test_qt_layout_parity.py`, the two new tests.
- Swift: `Tests/SceneryKitTests/BoundaryPressQueueTests.swift` and
  `Tests/XPTerrainBuilderTests/PatchAbsenceTests.swift`.
