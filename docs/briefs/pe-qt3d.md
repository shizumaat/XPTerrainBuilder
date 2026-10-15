# Brief pack — lane `pe-qt3d`

Base: main `63d3e2c61` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L7: Qt 3D preview

## The brief

## Lane pe-qt3d — L7 of the patch editor (#46): the 3D preview window in the Qt app

THE SPEC IS LAW: `Ortho4XP/docs/specs/patch-editor-20261015.md` on
`claude/patch-editor` — §0 (A7–A9), §2 (`terrain_sample`, `pack_objects`
async + `PackObjectsReady`, `mesh_crop`, optional `build_dir`), §5 (ALL the
"Ruled after …" paragraphs), §6 (amended: PySide6's own Qt Quick 3D or Qt3D,
no new dependency). Behavioural reference: the Mac window —
`Sources/XPTerrainBuilder/TerrainPreview*.swift` and
`Sources/SceneryKit/{PatchTriangulator,PatchShapeAssembly…,PatchBuildingSeats,
PatchDrape,PatchLastBuildState}.swift` (read for rules: hole pairing incl.
nested faces, grid cut-out, seat = surface(anchor) + agl, yaw = −heading,
exaggeration lifts seats not heights, drape ≤ 4,096 px from the map's cached
tiles, Last build refetch on mesh date). The Qt 2D editor (L5) is merged:
`O4_Qt_Patch_*.py`, `O4_Qt_Pack_Outlines.py` — reuse its engine bridge
(`O4_Qt_Patch_Engine.py`), its model's change notifications, and the
outlines' shared `pack_objects` request (one request per box for both).
If the spec is wrong or cannot be built as written, STOP and report.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-qt3d <head sha of claude/patch-editor>`.
`git -C` only. Never commit on main, push, merge elsewhere, or comment on
issues. Touch Qt files (new modules + wiring in `O4_Qt_GUI.py`) and tests,
plus `Ortho4XP_Qt.spec` if the 3D module needs including. If an engine
change is needed, report it rather than editing the engine — EXCEPT one
small one you may make: `o4_engine/jsonl.py` gains a public
`command_table(session)` (the Qt bridge uses the private `_build_handlers`
today); switch `O4_Qt_Patch_Engine.py` to it.

### Deliver
1. Triangulation: does a Python triangulator with holes already exist in
   the engine (`tools/blast.py --find triangulat earcut`; shapely/triangle
   in the venv)? Reuse it; port the Swift rules (hole pairing, nested faces)
   only where none exists — say which.
2. A separate 3D window (Ctrl/⌘3 and a "3D" button on the Qt map toolbar),
   title "3D Preview · ICAO": terrain grid with patch faces cut out, patch
   surfaces at node elevations, orbit/zoom/pan, Reset view, vertical ×1–×10
   (default ×3), Wireframe, Buildings (grey massing from `pack_objects`),
   Imagery drape (the Qt map's cached tiles only), Preview | Last build,
   legend + chip — same words as the Mac strings.
3. Live: edits re-mesh only the touched shapes and re-seat only buildings on
   them; Last build never live.
4. Tests (offscreen; Qt-under-xdist rule in `tools/harness/CLAUDE.md`):
   triangulation area/holes on the L2 fixture face, cut-out rule, seat
   transform, change → only touched shapes rebuilt, drape tile plan, Last
   build state. If the 3D scene cannot render offscreen, test the model
   layer and say so.

Constraints: blast before edits, `--find` before adding, ratchets at the
end; no airport-specific code; no downloads; only covering tests, once;
attempt cap 2 then STOP; heartbeat `.progress`.
Report: branch + sha; toolkit chosen and why; deliverables; tests; what
differs from the Mac; strings; net lines; new public symbols; spec points.

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

