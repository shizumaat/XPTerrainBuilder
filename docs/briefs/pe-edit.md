# Brief pack — lane `pe-edit`

Base: main `6f9ce4d24` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L3: Mac Edit mode

## The brief

## Lane pe-edit — L3 of the patch editor (#46): Mac Edit mode

THE SPEC IS LAW FOR THIS LANE: `Ortho4XP/docs/specs/patch-editor-20261015.md`
on branch `claude/patch-editor` — read §0 (A6, A10 and the owner's snap
quotes), §1.2, §3 (all), §4 (all), §8. Mockup:
`Ortho4XP/docs/mockups/patch-editor-20261015.html` (inspector states,
interaction table, save bar). If the spec is wrong or cannot be built as
written, STOP and report.

Already on the branch — read before writing anything:
- L2 (Mac View mode): `Sources/SceneryKit/PatchWire.swift`,
  `PatchDocument.swift`, `PatchSpatialGrid.swift`;
  `Sources/XPTerrainBuilder/PatchEditModel.swift`, `PatchOverlay.swift`,
  `PatchInspector.swift`, `PatchChange.swift`.
- L1 (engine): `Ortho4XP/src/o4_engine/patch_edit.py` (the reference
  implementation of the §3 ops), the twin fixture
  `Ortho4XP/tests/fixtures/patch_edit_ops.json` (22 cases + a
  `ui_snap_reference` note), `patch_commands.py` (save/revert behaviour:
  hand-made files save back to themselves, revert refuses them).

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-edit <sha of claude/patch-editor>`
(the branch name is checked out elsewhere, so pass its head sha). Run git as
`git -C <worktree> …`, never cd + git. Merge main and `claude/patch-editor`
into your branch before your final test run. Never commit on main, never
push, never merge into another branch, never comment on issues.

PARALLEL LANE: pe-3d (3D preview window) observes `PatchEditModel.changes`.
You OWN `PatchEditModel`; pe-3d only subscribes. Every edit, undo and redo
MUST call `documentChanged(_:)` with a precise `PatchChange` (nodes moved or
re-elevated, ways whose refs changed + `topology`). Do not rename or remove
`changes`, `PatchChange` or `documentChanged(_:)`.

### Deliver
1. Swift §3 ops on `PatchDocument` (move, set_position, set_alt, offset_alt,
   delete_nodes, insert_on_edge, merge_nodes, new-node ids below the min),
   matching `patch_edit.py`. A `swift test` suite runs EVERY case of
   `Ortho4XP/tests/fixtures/patch_edit_ops.json` (locate it from `#filePath`;
   do not copy it) with the file's stated tolerance.
2. Edit mode per §4 / mockup: View|Edit segmented control on the map; click
   select (8 pt), ⇧-click toggle, ⇧-drag box select, Esc clears; drag on a
   node moves the selection, drag on empty map pans (Edit mode must not
   break tile selection in View mode); "+" handles on the selected nodes'
   shapes' edges and on hover → `insert_on_edge`; ⌫/⌦ → `delete_nodes`.
3. SNAP (§3.3, owner's words): while dragging, when the POINTER is within
   8 pt on screen of a non-dragged node, the grabbed node is drawn AT that
   node with a snap highlight (the rest of the selection follows the pointer
   delta); dragging out releases it; on mouse-up while snapped → one undo
   step = move + `merge_nodes(grabbed, target)`; otherwise move only.
   Nearest on screen wins; ties by `survivor_key` (fixture note).
4. Undo/redo through the window's `UndoManager` (SwiftUI
   `@Environment(\.undoManager)`), so Edit ▸ Undo / Redo and ⌘Z / ⇧⌘Z work;
   a drag is ONE step; history survives a save; cleared on loading another
   airport. Drag frames must stay smooth on a 30k-node patch: do not rebuild
   the whole spatial grid / map geometry per frame (update the moved nodes'
   shapes during the drag, commit once on mouse-up).
5. Inspector (Edit mode): single node — lat/lon, elevation field in m with ft
   and the loaded value, "Used by" roles, Delete; multi — range, "Set to",
   "Offset", Delete N. Save bar: "● N unsaved edits", "Revert to auto…" with
   the confirmation INSIDE the pane (no NSAlert), Save (⌘S) → `patch_save`
   with the full document; after save: source line "Edited · <file>", the
   "Rebuild tile" button (call the existing BuildModel path for building that
   tile — find it, don't add a second one) and the re-seating note; hand-made
   file → no Revert, the "made outside the editor" line. Unsaved edits prompt
   (in-app confirmation) on switching airport and on quit.
6. Tests: the fixture suite; undo/redo round-trips of each op on a small doc;
   snap target choice (nearest, tie) as a pure function of screen points.

### Constraints
- `tools/blast.py <file>` before editing under `Sources/`; reuse existing
  helpers. New behaviour in new files (e.g. `PatchEditOps.swift`,
  `PatchEditGestures.swift`, `PatchSaveBar.swift`); `MapCanvasView.swift`,
  `BuildPane.swift`, `BuildModel.swift` get wiring only.
- UX copy from the spec/mockup; list every new user-facing string.
- `swift build` + `swift test` must pass; `tools/ratchets.py` at the end.
- No Python edits (report anything the engine should change instead).
- Convergence guards: attempt cap 2 per failing target, then STOP and report;
  heartbeat START/step/EXIT stamps in your scratch dir `.progress`.

### Closing check
Run the app against the engine on your branch on one built tile that has an
auto patch (the `run` skill / `scripts/make_app.sh`; read the memory notes on
TCC prompts and LaunchServices if the app hangs). Edit a few nodes, snap one,
undo/redo, save to a COPY of the patch dir you own — never the shared data
repo or another lane's tree — and confirm `<ICAO>_edited.patch.osm` holds the
edits. If you cannot run the app, say exactly why.

### Report (short)
Branch + head sha; per deliverable done / not done; test results; the closing
check result (with a screenshot path if you took one); every user-facing
string added; net lines; new public symbols; spec points to rule on.

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

