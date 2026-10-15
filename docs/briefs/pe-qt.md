# Brief pack — lane `pe-qt`

Base: main `80bc504ee` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L5: Qt parity (2D)

## The brief

## Lane pe-qt — L5 of the patch editor (#46): Qt parity (2D editor)

THE SPEC IS LAW: `Ortho4XP/docs/specs/patch-editor-20261015.md` on
`claude/patch-editor` — read ALL of it (§0 owner answers incl. A10 snap:
8 px on screen, merge only on release while snapped; §3 ops; §4 behaviour;
§6 Qt). Mockup: `Ortho4XP/docs/mockups/patch-editor-20261015.html`. The Mac
implementation (L2/L3) is the behavioural reference: `Sources/XPTerrainBuilder/
Patch*.swift`, `Sources/SceneryKit/Patch*.swift`. If the spec is wrong or
cannot be built as written, STOP and report.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-qt <head sha of claude/patch-editor>`.
`git -C <worktree>` only. Merge main + `claude/patch-editor` before the final
test run. Never commit on main, push, merge elsewhere, or comment on issues.
PARALLEL LANES: pe-outlines (engine `pack_outlines`, Mac files) and pe-3d
(3D window, `mesh_crop`). You touch ONLY Qt files (`O4_Qt_*.py` and NEW Qt
modules) and tests; NO engine module edits (report what the engine should
change instead), NO Swift.

### Deliver (2D only — the Qt 3D window is L7, not this lane)
1. Read how the Qt app reaches the engine (`O4_Qt_GUI.py` uses an in-process
   `EngineSession`) and call the same command functions the JSONL table maps
   (`o4_engine/patch_commands.py`, `pack_objects` async with its event, and
   `pack_outlines` per the amended §2 — pe-outlines is adding it; code
   against §2 and guard its absence). Edit ops: import
   `o4_engine/patch_edit.py` directly — never re-implement them.
2. New modules (not appends to `O4_Qt_Map.py`, which is 1,340 lines; wiring
   only there): patch overlay layer on the Qt map (styles by role as the
   mockup, node squares ≥ 6 px apart, viewport culling), View/Edit toggle,
   selection (click 8 px, Shift-click, Shift-drag box, Esc), drag-move with the
   8 px snap preview and merge-on-release, "+" insert handles, Delete/Backspace,
   `QUndoStack` (Ctrl/⌘Z, Shift+Ctrl/⌘Z; a drag = one step), the Patch panel
   below the build activity (node / multi inspectors, Set to / Offset,
   save bar, Revert with in-panel confirmation, Rebuild tile through the
   existing Qt build path, hand-made rule by file name, stale note),
   unsaved-edits prompt on airport switch and quit, pack outlines layer +
   toggle (pavement/boundary; building footprints from the `pack_objects`
   result).
3. Tests headless (`QT_QPA_PLATFORM=offscreen`; read
   `Ortho4XP/tools/harness/CLAUDE.md` for the Qt-under-xdist rule): the snap
   target function, undo/redo of each op through the QUndoStack, save →
   reload through `patch_commands` in `tmp_path`, the hand-made rule.

Constraints: blast before edits, `--find` before adding, ratchets at the end;
user-facing copy = the Mac strings (same words); no airport-specific code; no
downloads; only the covering tests, once; attempt cap 2 then STOP; heartbeat
`.progress`.
Report: branch + sha; deliverables; tests; anything you could not match to
the Mac behaviour; net lines; new public symbols; spec points.

## RULINGS

## 2026-09-05e — pad-flat blocker refuted and closed; `pad_flat` verify; app 1.0.283

* `lane/v2padflat` 998a8c47 merged. The red M5 twin was the PINNED-runway fixture in relaxed mode: the 04t(1) last resort made one pad a plane (slope 2.27 %, residual 0) by design; the hard fixture is green and pads are one `Flat` each (`constraints/pads.py:40`). Landed: bands on a detached pad act on the group's single level (the per-vertex form was hard-infeasible on a 100 m pad along a 1.5 % lip — KCLT's class); `verify/pads.py` `pad_flat` (unrelaxed pad spread > elevation materiality, relaxed pad plane residual > relaxation materiality) registered as a DEFECT that fails the airport by name in the driver and the harness. CYXY 0/0 pads 10/10 flat (`bd78e2c034b4`), SPJC 0/0 53/53 (`d7ca6dc04663`), KCLT 143/143.
* OWNER (intent): how much may a relaxed pad slope — `[relaxation] pad_slope_max`; spawner default until ruled: 1 % (a 2.27 % floor is a visible tilt).

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file. SIZE (owner 2026-10-04c, `tools/ratchets.py`): 1,000 lines is a guide and a
  warning, never a gate — the report (files past 1,000, files that grew, functions of
  200+ lines) is read by the master at merge. Split by responsibility, never to make a
  number. THE PRIORITY IS REUSE: small one-responsibility modules, no second
  implementation of a thing that exists (the identical-body duplicate count IS a gate:
  it may fall, never rise; `dupes --near` is reported).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`.
  Do NOT set `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR`: the harness makes its own
  overlay, and with them set a build refuses ("pack DSF dump MISSING", #342) — they are
  the pytest suite's mechanism, set by `tests/conftest.py`.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched; net lines added/removed
  + new public symbols (owner 2026-10-04a (5)).

