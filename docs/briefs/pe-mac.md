# Brief pack — lane `pe-mac`

Base: main `8eb28c94f` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L2: Mac read-only render

## The brief

## Lane pe-mac — L2 of the patch editor (#46): Mac read-only render

THE SPEC IS LAW FOR THIS LANE: `Ortho4XP/docs/specs/patch-editor-20261015.md`
(on branch `claude/patch-editor`). Read §0, §2, §4 and §8; the mockup is
`Ortho4XP/docs/mockups/patch-editor-20261015.html` (open it to match colours,
legend and the inspector layout). §2 is a FROZEN wire contract. Lane
pe-engine builds the engine side IN PARALLEL — you code against §2, not
against its code. If the spec is wrong or cannot be built as written, STOP
and report.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-mac claude/patch-editor`,
work and commit on the lane's branch there. Never commit on main, never push,
never merge, never comment on issues. Do not edit Python.

### Deliver (View mode only — editing is L3, not this lane)
1. `Sources/SceneryKit/OrthoEngineClient.swift`: wrappers + Codable reply
   types for all eight §2 commands (binary fields decoded from base64 LE).
   Client side of protocol 1.12: read how the client checks the engine's
   protocol version and make 1.12 accepted (an older engine simply lacks the
   commands — the patch layer then stays hidden, no error dialog).
2. `Sources/SceneryKit/PatchDocument.swift`: the document (nodes, ways, tags,
   source, stale, spacing), bbox, a spatial grid for hit-testing nodes and
   edges in metres, role → style mapping. NO edit operations yet (L3 adds them
   against the shared fixture) — but shape the type so §3's ops slot in.
3. `Sources/XPTerrainBuilder/PatchEditModel.swift` (ObservableObject: current
   tile/airport, document, load state, selection placeholder for L3, View/Edit
   mode placeholder) — it calls `patch_list` for built tiles in view and
   `patch_load` for the airport per §4 "Display".
4. `Sources/XPTerrainBuilder/PatchOverlay.swift`: drawing per §4 and the
   mockup — fills + strokes by role, nodes as small squares when ≥ 6 pt apart,
   viewport culling, legend, the bottom-left chip ("ICAO · auto patch · N
   nodes · M shapes"). `MapCanvasView.swift` gains only the few lines to call
   it. Keep the base map from redrawing more than it does today.
5. `Sources/XPTerrainBuilder/PatchInspector.swift`: the "Patch · ICAO" box in
   `BuildPane`, below Activity, View-mode content (source line, counts, stale
   note, "Build this tile first" when the zoomed airport has no patch).
6. Tests (`swift test`): decoding of a §2 `patch_list` / `patch_load` reply
   from a JSON fixture you write under `Tests/`; bbox and hit-test of the
   spatial grid; role styling of the tags in §2's example roles.

### Constraints
- `tools/blast.py <file>` before editing any file under `Sources/`; check
  `tools/blast.py --find` / existing Swift helpers before adding (e.g.
  `MapCamera`, `TileMath`, existing colour constants in `MapCanvasView`).
- Swift build: release Xcode (see memory note in the repo docs / `swift
  build`); `swift build` and `swift test` must pass. Use `Bundle.sceneryKit` /
  `Bundle.appResources`, never `Bundle.module`.
- New behaviour lives in new files; `MapCanvasView.swift` (672 lines) and
  `BuildPane.swift` (993) get wiring only.
- UX copy as in the spec/mockup; anything else user-facing, keep it short
  and list it in your report for review.
- Convergence guards: attempt cap 2 per failing target, then STOP and
  report; heartbeat START/step/EXIT stamps in your scratch dir `.progress`.

### Report (short)
Branch + head sha; per deliverable done / not done; `swift build` / `swift
test` results; the protocol-version finding; every user-facing string you
added; net lines added/removed; new public symbols; anything in the spec you
think is wrong.

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

