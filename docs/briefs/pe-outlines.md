# Brief pack — lane `pe-outlines`

Base: main `80bc504ee` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L4: pack reference outlines

## The brief

## Lane pe-outlines — L4 of the patch editor (#46): pack reference outlines (engine + Mac)

THE SPEC IS LAW: `Ortho4XP/docs/specs/patch-editor-20261015.md` on
`claude/patch-editor` — §0 (A4), §2 (`pack_outlines` and the "Amended …
before L4/6c" paragraph: NO `footprints` key), §4, §8. Mockup: the dashed
"pack apt.dat" outlines and the "Pack outlines" toggle. If the spec is wrong
or cannot be built as written, STOP and report.

Already on the branch: L1–L3 and 3D rounds 6a/6b. Read
`o4_engine/pack_objects.py` / `pack_massing.py` (how the airport's pack is
found — `select_pack` — and the async `PackObjectsReady` + session cache),
`Sources/SceneryKit/PatchWire.swift` (`O4PackOutlines` exists — adjust it to
the amended §2), `Sources/XPTerrainBuilder/PatchOverlay.swift`,
`PatchModeToolbar.swift`, `TerrainPreviewBuildings.swift`.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-outlines <head sha of claude/patch-editor>`.
`git -C <worktree>` only. Merge main + `claude/patch-editor` before the final
test run. Never commit on main, push, merge elsewhere, or comment on issues.
PARALLEL LANES: pe-3d (6c: 3D window, `mesh_crop`, `terrain_sample`) and
pe-qt (Qt files only). Touch only your own jsonl row; do not edit the 3D
window files or `PatchEditModel` beyond wiring you list in the report.

### Deliver
1. Engine `pack_outlines {tile, icao}` in a new module, registered in the
   jsonl table, synchronous: the airport's pack found exactly as
   `pack_objects` finds it; rows 110 + 130 from the pack's apt.dat for that
   ICAO through `auto_patch_v2/airport/apt_dat.py` (its bezier flattening —
   no second parser); holes kept as extra rings. Cache-only; problems as
   `missing` sentences. If the parse of a big apt.dat takes > 1 s, measure
   and report (HECA and one large pack), don't optimise blindly.
2. Mac: a "Pack outlines" toggle in the map toolbar (persisted per user,
   default on); dashed grey pavement + boundary under the patch; building
   footprints = the plan outline (2D convex hull) of each placed model's
   hulls from the `pack_objects` result — request it through the existing
   wrapper/cache when outlines are on and a patch is shown (it is shared
   with the 3D window: one request, one cached result in the app — put that
   shared result where both can read it, e.g. a small `PackBuildingsStore`,
   and make the 3D window use it too). Legend row "pack apt.dat" as the
   mockup. Drawing must not slow the drag path (static layer).
3. Tests: pytest for `pack_outlines` on a synthetic pack apt.dat with a
   bezier ring and a hole; `swift test` for footprint outline of a rotated
   placement and for the shared store (one request for two consumers).

Constraints: blast before edits, `--find` before adding, ratchets at the end;
no airport-specific code; no downloads; only the covering tests, once;
attempt cap 2 then STOP; heartbeat `.progress`.
Report: branch + sha; deliverables; HECA numbers first (rings, time); tests;
user-facing strings; net lines; new public symbols; spec points.

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

