# Lane lqueue handoff (1.0.433 sluggishness: Queue disabled, apt.dat log spam, patches not loading, "Build this tile first") — WIP, paused 2026-10-27 by owner order

Issue: **needs issue** (master files it; four owner reports folded in: Queue disabled,
`[pav-builder]` lines in the console, patches not loading on zoom, SPJC "Build this tile first",
plus "the whole app is sluggish vs 1.0.432").

## Root cause (measured)

1.0.433 (da85f5493) added the #818/#1414 Airports card (`o4_engine/build_airports.py`, new
since 1.0.432 cfb3f11d9). On EVERY selection change (Swift: 300 ms debounce, `.task` cancels the
Swift side only) the engine starts a NEW thread that runs the build's own tile selection
(`auto_patch.selection.select_patch_airports`) for every selected tile, plus a full Custom
Scenery pack walk (`O4_Custom_Scenery.scan_packs`). The boundary preflight (`boundary_airports`,
every Queue press) runs the same selection. None of it was cached across calls:

- `discover_cifp_airports` + `read_threshold_dicts`: re-read all ~11,000 CIFP files per tile per call;
- `find_apt_dat` (apt.dat selection): lists Custom Scenery (~4,236 entries) and stats each
  pack's apt.dat per in-tile airport per call (`O4_Scenery_Packs.enabled_pack_names` also
  listdir+isdir's every entry per call); only the per-file block index `_BLOCK_INDEX` was cached;
- `scan_packs` for the card: listdir of every pack's Earth nav data (11,080 listdirs) and an
  apt.dat parse per pack, per call;
- old card threads were never superseded, so they piled up; all run in the engine process and
  compete for the GIL/CPU with the in-process build and with the synchronous read-loop commands
  (patch_list / patch_load / pack_outlines run ON the read loop).
- The `[pav-builder] ICAO: apt.dat …` lines are `build_support._pick_best_apt_dat_against_osm`'s
  `UI.vprint`, printed by these preview threads (no `[tile]` tag) — real repeated work, not a log oddity.
- SPJC "Build this tile first": the patch panel reads `built[coord] == nil` as not built even while
  the `scan` is still running; `scan` over the owner's 2,521-tile Custom Scenery costs 42 s profiled,
  29 s of it in `O4_Tile_Info._imagery_date` (isfile + getmtime = 2 stats × ~850,000 textures).

### Measurements (this Mac, sibling lanes loading the CPU; "contended" = 1 GIL-spinning thread
+ 2 card threads + 1 preflight in one process, probe `queue-lqueue-probes/latency_probe.py`,
run from `Ortho4XP/` as `PROBE_SPIN=1 PROBE_CARDS=2 venv/bin/python <probe> +45-123 KHIO <label>`)

| what | 1.0.433 code (main) | branch so far |
|---|---|---|
| preflight 2 tiles (+61-151,+61-150), cold, idle | 31.5 s profiled / 14.6 s plain | — |
| preflight 2 tiles warm, idle | 6.7 s profiled | 4.1 s profiled (CIFP memo only) |
| preflight warm + 1 GIL spinner | 24.2 s | — |
| card 1 tile warm, idle | 4.5–5.8 s | 0.25–0.47 s |
| contended: all preview threads done | 82.7 s | 30.6 s (memo + pack memo) / 52.9 s (noisy rerun) |
| contended: worst patch_load (read loop) | 5.0 s | 4.7 s / 0.66 s |
| contended: worst patch_list | 0.70 s | 0.72 / 0.97 s |
| card warm profile | 10.5 s (listdir 3.4 s, apt.dat parse 4.5 s) | 2.2 s |
| `scan` 2,521 tiles (Custom Scenery) | 42 s profiled (stat 29 s) | not re-measured after scandir fix |

Not yet measured: the branch with the apt.dat selection map + CIFP dir index (last edits), the
1.0.432 control (worktree ready: scratchpad `w432`, recreate with
`git worktree add --detach <dir> cfb3f11d9` and symlink venv/cfg/Patches from a lane tree; 432 has
no card, so `latency_probe.py` measures preflight + patch commands only), the Queue latency line
(probe now prints "Queue preflight answered in N s"), and library_scan under load.

## Done (uncommitted until this WIP commit; NOT yet tested — run the suites)

- `O4_UI_Utils.quiet_thread()` / `thread_is_quiet()`: thread-local mute of vprint/lvprint.
- `session.boundary_airports` worker and `build_airports.build_airports` run inside `quiet_thread()`
  (the build's own selector lines unchanged).
- `cifp.read_threshold_dicts`: memo `_THRESHOLDS` by file (mtime_ns, size), returns copies.
- `cifp.discover_cifp_airports`: memo `_DIRECTORY` by CIFP dir mtime_ns.
- `apt_dat.find_apt_dat`: selection map `_SELECTION` keyed by (Custom Scenery dir identity,
  scenery_packs.ini identity, Global Airports candidates' identities) + the chosen file's identity;
  old body is `_find_apt_dat`. KNOWN LIMIT (coordinator-directed key): an apt.dat edited in place
  inside an existing pack does not invalidate; check tests that create packs after a first call.
- `O4_Custom_Scenery._pack_airports`: memo `_PACK_AIRPORTS` by apt.dat identity; new
  `iter_airport_packs(scenery_dir)` (apt.dat only); `build_airports.airport_packs` uses it.
- `build_airports.start_build_airports`: generation counter `_GENERATION`; a newer ask supersedes
  (`Superseded` raised between tiles → BuildAirportsReady error). Qt card already drops stale
  answers by generation but does not stop the thread — pass `live=` there too.
- `O4_Tile_Info._imagery_date`: os.scandir, one stat per file (same result).
- Swift: new `Sources/SceneryKit/BoundaryPressQueue.swift` (`O4BoundaryPressQueue`) — NOT wired yet;
  drop the `where Press: Sendable` constraint (make Sendable conditional) because `BuildBatch` is not Sendable.

## Exact next step

1. Run `tests/test_boundary_*`, `test_build_airports.py`, `test_auto_patch_freshness.py`,
   `test_cifp_tile_selection.py`, `test_patch_selection.py`, `test_airport_identity_heliport.py`,
   `test_post_mesh.py`, `tests/auto_patch_v2/test_airport_load.py`, the Custom Scenery / tile-info
   tests (blast.py on each changed file) — fix fallout from the memos (tests that mutate files
   between calls may need the caches cleared; prefer an autouse fixture clearing `_SELECTION`,
   `_DIRECTORY`, `_THRESHOLDS`, `_PACK_AIRPORTS`).
2. Wire the Swift press FIFO in `BuildModel.startProtocolBuild` (`BuildModel.swift` ~1991):
   submit → begin preflight or wait; on `finishBoundary` / cancel → `settle()` and begin the next;
   `canBuild` uses `acceptsPress(isPreflighting:isBuilding:)` (Queue live during a build; Build
   still blocked when idle — Qt already behaves so: `O4_Qt_GUI.start_build` ~3640).
3. "Checking" state: Swift `PatchEditModel.evaluate` (~206) → when `build.built[coord] == nil &&
   build.isScanning` show "Checking which tiles are built…" (subscribe to `$isScanning`);
   Qt `O4_Qt_Patch_Controller.evaluate` (~176) + `O4_Qt_Patch_Panel.refresh` (~350) with an
   `is_scanning` callable wired like `is_building` (`O4_Qt_GUI.py:1083`, `self._scanning`).
4. Owner UI ask: Airports section's detailed explanation behind a small "i" button, both apps
   (`BuildAirportsCard.swift`, `O4_Qt_Build_Airports.py`), keep `test_qt_layout_parity.py` green.
5. Twins: no `[pav-builder]` line from `build_airports` / `boundary_airports` (capture stdout);
   the memos invalidate on mtime; supersede; bounded patch_load latency while card threads run;
   Swift `O4BoundaryPressQueue` tests in SceneryKitTests.
6. Re-measure the table (432 / 433 / branch), ratchets, ruff I001, registry + closure twins, PR.

## Open questions

- library_scan "partial results": the map's built set comes from `scan` (already streams, off the
  loop); `library_scan` feeds only the Library view. Is scandir speed enough, or should
  library_scan stream rows (protocol change, both apps)?
- `plan_estimate` debounce not yet checked.
