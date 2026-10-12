# failmsg562 — lane notes (issues #562, #564 wire part)

## RESUME HERE

* Branch `claude/failmsg562`, worktree `.claude/worktrees/failmsg562`; origin/main `1ff5a912a` merged in.
* DONE: census (`docs/briefs/failmsg562-census.md`, amended for RULINGS 2026-10-12a); catalogue
  `Ortho4XP/src/O4_Tile_Failures.py`; wire (protocol 1.10); session + parallel; step exits annotated;
  Qt (`O4_Qt_Tile_Failures.py`); mac (`Sources/SceneryKit/TileFailure.swift`,
  `Sources/XPTerrainBuilder/RunIssuesSheet.swift`); twins (`tests/test_tile_failures.py`,
  `tests/test_qt_tile_failures.py`, `Tests/SceneryKitTests/TileFailureTests.swift`).
* LEFT: nothing planned. Full non-Qt suite result is in the final report.

## THE WIRE CONTRACT (protocol 1.10, ONE bump: events + the `failure_report` command)

* `BuildDone.failures: list` (default `[]`) — why a tile was NOT built, one entry per cause:
  `{code, what, why, remedy, airports, detail, log_path}`.
* `BuildDone.warnings: list` (default `[]`) — same entries, for airports without a patch on a tile that
  WAS built, folded per cause.
* `BuildDone.unpatched_airports: list` (default `[]`) — the same airports ONE PER ENTRY, the same dict
  plus `stage`. Non-empty with `ok=True` = built with warnings.
* `AutoPatchFailed.code: str` (default `""`).
* `TileState(state="done", label="built with warnings")` for such a tile.
* Entries go back into `failure_report` unchanged (extra keys are ignored there).

* `BuildDone.notes: list` (default `[]`) — info-level entries of a BUILT tile, same shape plus `cells`:
  code `elevation_substituted` (RULINGS 2026-10-12e). Source: `DEM.base_substitutions`, published by
  `O4_Unpatched_Airports.record_substitutions` at the production DEM load (`O4_Vector_Map.
  compose_tile_dem_from_disk`) into the SAME sidecar as the unpatched airports (key
  `elevation_substituted`; `_write_key` keeps the other keys), read back by `read_substitutions`.
* A `pack_restore` sentence in an unpatched airport's record (RULINGS 2026-10-12d) becomes a second
  warning for that airport, code `pack_restore_unproven`; it is not a second `unpatched_airports` entry.
* The restore remedy names "Revert to default" under "Modified airports": neither app has a control
  called "Restore originals".

## WHERE THE WARNINGS COME FROM (master ruling)

`O4_Unpatched_Airports.read(tile)` at the tile's successful end (`session._build_worker`), through
`O4_Tile_Failures.from_unpatched`. `record()` there now also keeps `code` / `params`, so the last step's
process (a different child under `parallel.py`) words the warning from the sidecar alone. The closing
log lines (`O4_Tile_Failures.closing_lines`) are printed by the in-process session, or by the parallel
parent after "Tile … completed in".

A tile that is NOT built reports the session's own records: `UI.auto_patch_failed(icao, stage, error,
code=, params=)` (strict mode, `config`, an un-movable stale file), `UI.exit_message_and_bottom_line(...,
code="<key>")`, `UI.tile_failure("<key>", exc=exc)`, or the exception's class
(`O4_Tile_Failures.EXCEPTION_CODES`, or `failure_code` / `failure_params` attributes).

## For lane dump560

`auto_patch_v2/airport/load.py` now raises `PackDumpStale(pack, message)` (one line changed at the raise
plus the class). Reword the message freely. A distinct condition (dump empty / DSFTool failed) is a
subclass with `failure_code = "pack_dump_failed"` — that catalogue entry already exists.
