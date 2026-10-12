# inactive585 — lane notes (issue #585)

## RESUME HERE

* Branch `claude/inactive585` ON TOP of `origin/claude/failmsg562` (PR #584, its catalogue is needed);
  worktree `.claude/worktrees/inactive585`.
* DONE: census below; fix in `Ortho4XP/src/O4_Tile_Utils.py` (`activate_dsf`), `O4_DSF_Utils.py`
  (move-aside), `O4_Overlay_Utils.py` (`install_overlay_dsf`), `O4_Tile_Failures.py` (2 codes, 1 remedy,
  `code_for_activation`); twins `Ortho4XP/tests/test_dsf_activation.py`.
* LEFT: nothing planned. The copy is the master's to rule.

## CENSUS — file moves in a tile's final steps

| # | Site | Operation | Before | Verdict |
|---|------|-----------|--------|---------|
| 1 | `O4_Tile_Utils.build_tile` activation | `os.replace(<dsf>.tmp, <dsf>)` | bare `except:` prints "tile is not active", step returns 1 | **FALSE SUCCESS — fixed** (`activate_dsf`) |
| 2 | same site, after a Stop inside the encoder | same move, run BEFORE the red-flag check | a truncated `.dsf.tmp` (no checksum) was moved onto `<dsf>`; step returned 0 as a cancel | **wrong file activated — fixed**: only a `build_dsf` that returned 1 is activated |
| 3 | `O4_DSF_Utils.build_dsf` move-aside | `os.replace(<dsf>, <dsf>.bak)` | raised into the step's guard: named, but by exception class (`no_permission` → "check permissions") | named already; **copy fixed** — this is where a running X-Plane's hold is met first, so it now carries the activation code |
| 4 | `O4_Overlay_Utils.build_overlay` final copy | `shutil.copy(tmp, yOrtho4XP_Overlays/…dsf)` | unguarded: an exception reached the session (named by class; a missing converter output read as `file_missing` → "check Settings"); a copy cut short by a full disk left a TRUNCATED overlay over the old one | no false success; **fixed** for copy and state (`install_overlay_dsf`: staged copy + one move) |
| 5 | `O4_Overlay_Utils` L106 copy to tmp dir | `shutil.copy` | guarded, `output_folder_unwritable` | fine (failmsg562 row 38) |
| 6 | `O4_Overlay_Utils` L126 `.7z` rename in tmp dir | `os.replace` | unguarded → raises → named by class | listed, not changed (scratch file, not an activation) |
| 7 | `O4_Tile_Utils._write_imagery_manifest` | `os.replace(tmp, manifest)` | caught, logged at verbosity 2 | listed: a manifest is a record, not what X-Plane loads; by design never fails the tile |
| 8 | `O4_Tile_Utils` cleaning (`os.remove` of `.alt`, `.node`, `.poly`, `.bak`, mesh, apt; `remove_unwanted_textures`) | deletes | swallowed | listed: leftovers only, the tile loads |
| 9 | `O4_Mesh_Utils` L2640 mesh file | `os.replace(tmp, mesh)` | unguarded → raises → named by class | listed (mesh step, not activation) |
| 10 | `O4_DSF_Utils` L399 `water_transition.png`, L496/L510 Global Scenery DSF copy/rename | `shutil.copy` / `os.replace` | inside `build_dsf` → the guard names it | listed, fine |
| 11 | `O4_Scenery_Links` install/uninstall (symlink into Custom Scenery) | `os.symlink` | raises to the caller by contract; a separate user command, not a build step | listed, out of scope |

There is no texture/terrain FOLDER move in the final steps: `textures/` and `terrain/` are written in
place inside the tile's folder.

## STATE AFTER A REFUSAL

* Activation refused (row 1): no `<dsf>`; the finished `<dsf>.tmp` and the previous `<dsf>.bak` stay.
  X-Plane finds no scenery file for the tile and shows its default scenery there. The previous file is
  deliberately NOT restored — this build has already rewritten the `terrain` folder it points into, so
  putting it back can give X-Plane a scenery file with missing terrain files. The next build rewrites
  `.tmp` and activates it; nothing by hand (twin `test_the_step_fails_then_the_next_build_repairs_it`).
* Stop inside the encoder (row 2): same state, `.tmp` truncated; the next build overwrites it.
* Move-aside refused (row 3): nothing moved; the previous `<dsf>` is still the active one.
* Overlay install refused (row 4): the previous overlay is untouched; the staged `.tmp` is removed.

## COPY ADDED (for the master's ruling)

* `scenery_file_locked` — "its new scenery file could not be put in place." · "The file it replaces is
  in use or protected." · remedy `quit_xplane`.
* `scenery_file_not_activated` — same what · "The finished file could not be moved into the tile's
  folder." · remedy `retry`.
* remedy `quit_xplane` — "Quit X-Plane if it is running, then build the tile again. If it fails again,
  check that the app is allowed to write to the tile's folder."
* A full disk at these sites keeps the existing `disk_full`.

"In use or protected" and "if it is running" because the cause is not measured: Windows reports a held
file and a protected one with the same refusal (access denied).

## FOUND, NOT FIXED

* `O4_Overlay_Utils`: `fingers_crossed.returncode` is read without `wait()`/`poll()`, so it is always
  `None` — the "DSFTool crashed" exit (`overlay_tool_failed`) can never fire on the first conversion, and
  the second conversion's result is not checked at all. A failed conversion is now caught at the install
  (the output file is missing → `overlay_tool_failed`), but a converter that exits non-zero AFTER writing
  a file is still accepted.
* A cancel during the texture DOWNLOADS (encoder finished) still activates the new DSF and returns 0:
  the tile is left active with whatever textures arrived. Unchanged; whether a cancelled tile should be
  left active is an intent question.
* The Swift and Qt front ends render `what/why/remedy` from the wire, so the new codes need nothing
  there; not run in the mac app.
