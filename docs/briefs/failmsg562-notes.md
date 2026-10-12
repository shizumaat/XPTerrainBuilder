# failmsg562 — lane notes (issues #562, #564 wire part)

## RESUME HERE

* Branch `claude/failmsg562`, worktree `.claude/worktrees/failmsg562`; origin/main `1ff5a912a` merged in.
* DONE: census (`docs/briefs/failmsg562-census.md`, amended for RULINGS 2026-10-12a); catalogue
  `Ortho4XP/src/O4_Tile_Failures.py`; wire (protocol 1.10); session + parallel; step exits annotated;
  Qt (`O4_Qt_Tile_Failures.py`); mac (`Sources/SceneryKit/TileFailure.swift`,
  `Sources/XPTerrainBuilder/RunIssuesSheet.swift`); twins (`tests/test_tile_failures.py`,
  `tests/test_qt_tile_failures.py`, `Tests/SceneryKitTests/TileFailureTests.swift`).
* LEFT: nothing planned. Full non-Qt suite result is in the final report.

## THE WIRE CONTRACT (for lane tilecont564 and the master)

`origin/claude/tilecont564` did not exist when this was written, so the field is defined HERE.

* `BuildDone.warnings: list` (default `[]`) — airports without a patch on a tile that WAS built. Each entry
  is the same dict as `BuildDone.failures`: `{code, what, why, remedy, airports: [icao…], detail, log_path}`.
  The unpatched airports are `[a for w in warnings for a in w["airports"]]`.
* `BuildDone.failures: list` (default `[]`) — why a tile was NOT built.
* `AutoPatchFailed.code: str` (default `""`).
* `TileState(state="done", label="built with warnings")` for such a tile.
* Protocol `1.10`. Old peers ignore the new keys; `BuildDone.error` is now the plain message as one line.

## THE ONE SESSION-SIDE HOOK (what tilecont564 calls — it already does)

    UI.auto_patch_failed(icao, stage, error, code="", params=None)

`auto_patch/driver._fail_build_tasks` already makes this call for every failed airport. Nothing else is
needed: when `O4_Vector_Map.build_poly_file` carries on and the tile's last step succeeds, the session
emits `BuildDone(ok=True, warnings=…)` from those records. If the vector step still returns 0, the same
records are reported as failures. `code` / `params` are optional (the `stage` decides otherwise).

A step that ends the tile names its cause with
`UI.exit_message_and_bottom_line(..., code="<catalogue key>")` or `UI.tile_failure("<key>", exc=exc)`.
An exception names it by class (`O4_Tile_Failures.EXCEPTION_CODES`) or by `failure_code` /
`failure_params` attributes.

## For lane dump560

`auto_patch_v2/airport/load.py` now raises `PackDumpStale(pack, message)` (one line changed at the raise
plus the class). Reword the message freely. A distinct condition (dump empty / DSFTool failed) is a
subclass with `failure_code = "pack_dump_failed"` — that catalogue entry already exists.
