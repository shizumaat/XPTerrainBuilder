# Brief pack — lane `pe-engine`

Base: main `8eb28c94f` · generated 2026-10-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Patch editor L1: engine commands + edit ops

## The brief

## Lane pe-engine — L1 of the patch editor (#46)

THE SPEC IS LAW FOR THIS LANE: `Ortho4XP/docs/specs/patch-editor-20261015.md`
(on branch `claude/patch-editor`). Read §0–§3 and §8 in full. §2 is a FROZEN
interface: do not change a command name, argument or reply key. If the spec is
wrong or cannot be built as written, STOP and report — do not improvise.

Set up: `Ortho4XP/tools/harness/lane_worktree.sh up pe-engine claude/patch-editor`,
work and commit on the lane's branch there. Never commit on main, never push,
never merge, never comment on issues.

### Deliver
1. `PROTOCOL_VERSION` "1.11" → "1.12" (`o4_engine/events.py`). Before bumping,
   read how `Sources/SceneryKit/OrthoEngineClient.swift` compares the version;
   if an exact-match check would refuse 1.12, report it (lane pe-mac owns the
   Swift side) — do not edit Swift.
2. Commands `patch_list`, `patch_load`, `patch_save`, `patch_revert` in a NEW
   module (e.g. `o4_engine/patch_commands.py`) registered in the
   `o4_engine/jsonl.py` command table. Not an append to `session.py`.
   Reuse, never re-implement: patch dir naming (`O4_File_Names`), manual-patch
   detection (the same function `include_patches` / `driver.py` use — extract a
   shared helper if they each inline it), the stamp computation of
   `driver._auto_patch_is_current` (§1.4), the OSM writer conventions of
   `emit/osm_adapter.render_patch` for node/way output.
3. `o4_engine/patch_edit.py`: §3.1 operations, §3.2 topology rules, §3.3 snap,
   pure functions over a small document type, no I/O.
4. §3.3: `patch_edit.py` imports `survivor_key` and reads the spacing from
   the law table (`emit.identity.min_distinct_spacing_m`); it never copies
   them. There is NO merge pass at save (owner, 2026-10-15: snapping is only
   for nodes being moved in the editor).
5. Twin fixture `Ortho4XP/tests/fixtures/patch_edit_ops.json`: ≥ 12 cases —
   move, set/offset alt (single + multi), delete inside a ring, delete
   collapsing a closed way below 3 distinct and an open way below 2,
   insert on an edge shared by two ways (both get it), insert with a null
   alt end, live move-snap onto a neighbour (survivor keeps position + alt),
   snap tie broken by `survivor_key`, an insert and an alt edit that do NOT snap, consecutive-duplicate collapse. Schema:
   `{cases: [{name, doc: {nodes, ways}, ops: [{op, args}], expect: {nodes, ways}}]}`
   with nodes as `[id, lat, lon, alt|null]` exactly as §2. Lane pe-mac's
   successor (L3) will run the same file from `swift test`, so keep it
   self-describing and platform-neutral (no float formatting tricks: compare
   with an absolute tolerance of 1e-9 deg / 1e-6 m stated in the file).
6. A5 (§1.3): find how a build treats a MANUAL patch's grade violations today
   (census / acceptance / any refusal in the app build path). Make it: report,
   never fail, labelled "user-edited" when the patch header has
   `o4_user_edited="1"`. If today nothing censuses a manual patch, the work is
   the label only — say so. If it needs a law change beyond that, STOP and report.
7. Tests (headless, `tmp_path`, no network): the fixture cases; `patch_load` →
   `patch_save` with no edits on a real auto patch from the data repo
   (`/Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/HECA_auto.patch.osm`
   — copy it into `tmp_path`, never write the data repo) rewrites the same
   nodes and ways (header may differ) — HECA carries 1,003 node pairs at
   0.499–0.500 m that must stay as they are; `patch_save` writes
   `<ICAO>_edited.patch.osm` that the existing manual detection picks up;
   `patch_revert` renames to `.disabled`; JSONL round trip of each command
   through the jsonl dispatcher.

### Constraints
- `tools/blast.py <file>` before editing any file under `Ortho4XP/src/`;
  `tools/blast.py --find` before adding a function. `tools/ratchets.py` at the
  end (identical duplicates and upward imports are gates).
- No GUI imports in core; no airport-specific code (05e) — HECA is a test
  input only; no downloads; never write the shared data repo.
- Run only the test files covering the change, once (pre-ship mode).
- Build-time impact: none on the tile-build path except reading one header
  attribute for the A5 label. Say so in the report, with evidence.
- Convergence guards: materiality floor 1e-6 m / 1e-9 deg for the twin;
  attempt cap 2 per failing target, then STOP and report; heartbeat
  START/step/EXIT stamps in your scratch dir `.progress`.

### Report (short)
Branch + head sha; per deliverable done / not done; A5 finding (file:line);
tests run and results; the version-check finding for Swift; net lines
added/removed; new public symbols; anything in the spec you think is wrong.

## RULINGS

## 2026-09-13cg — v2hairline's VMMC MEASUREMENT (branch 8e566c17, merged 8c58e1a7 — frames only; the code was 13cd's) and RULED (Fable, §39 (6) restated): the VMMC tile built in the lane (3,845 s — the VHHH cost) reads bent chords 369 → 166 with NO sea/bank triple left (the 2 under 0.5 mm are water-vs-water), unmeshable pairs 419 → 119, the two 60 m boxes' slivers 677,820 → 406,393, the latent `bank:4` site CLEAN — PARTIAL, and the residual is the finding: a `bank_foot`-vs-`SEA` vertex at 0.0025 mm survives at 22.155210945, 113.576646308 (slenderness 4,004,066) and box A got WORSE (137,718 → 296,037) because the emit-side weld reads `TileWater` (`sea_area_from_coastline`) while the mesh constrains `include_sea`'s OWN sea edges — the two differ by micrometres: 13bt's two-witness shore lives in the MESH's own inputs, and the emitter cannot close it; only the vector map can. Six VMMC stations stay 481–501 mm from a SEAWALL breakline (a mesh-side construct absent from `shore_edges`). The VMMC arm is not single-variable (it carries the day's main incl. v2zonebank's `_foot_piece`). RULED: (i) ONE WITNESS — the emitter's `shore_edges` are built from the SAME sea polygons the mesh will constrain (the vector map's `include_sea` product, not a second derivation from the coastline), so the emit weld and the mesh agree to the 11-dp identity; the `SEAWALL` breakline (`O4_Vector_Map.py:157`, the 0.5 m inland limb) joins `shore_edges` so no station can sit astride the bar; (ii) THE VECTOR-MAP WELD WITH A RE-NODING PASS — the refuted post-snap weld (13cd) is re-armed only as weld + re-node: after moving a junior node onto its senior, every edge that passed within the radius of the junior is re-noded against the senior's edges (the `insert_edge` split machinery, now metric), so Triangle4XP's "topological inconsistency" cannot arise; the twin is LEMD's arm-2 `.poly` (the one that refused) meshing clean; (iii) `v2shortseg` folded in: the identity join must MERGE, never write, a sub-spacing constrained segment (LEMD 932, KCLT 1,635, VMMC 1,631; shortest 5.6 µm). Round 2 on the SAME lane (resumed). Bars: VMMC bent chords 166 → 0 sea/bank and box slivers → CYXY's class, the 0.0025 mm pair gone, the 6 seawall stations resolved; LEMD held at 1,641; the LEMD arm-2 `.poly` meshes; emitted sub-spacing segments 0 at LEMD / KCLT / VMMC; KCLT tile still needs the owner's `--refresh-data dem`.

## 2026-09-05e — pad-flat blocker refuted and closed; `pad_flat` verify; app 1.0.283

* `lane/v2padflat` 998a8c47 merged. The red M5 twin was the PINNED-runway fixture in relaxed mode: the 04t(1) last resort made one pad a plane (slope 2.27 %, residual 0) by design; the hard fixture is green and pads are one `Flat` each (`constraints/pads.py:40`). Landed: bands on a detached pad act on the group's single level (the per-vertex form was hard-infeasible on a 100 m pad along a 1.5 % lip — KCLT's class); `verify/pads.py` `pad_flat` (unrelaxed pad spread > elevation materiality, relaxed pad plane residual > relaxation materiality) registered as a DEFECT that fails the airport by name in the driver and the harness. CYXY 0/0 pads 10/10 flat (`bd78e2c034b4`), SPJC 0/0 53/53 (`d7ca6dc04663`), KCLT 143/143.
* OWNER (intent): how much may a relaxed pad slope — `[relaxation] pad_slope_max`; spawner default until ruled: 1 % (a 2.27 % floor is a visible tilt).

## Map: o4_engine

Generated by `tools/blast.py --map` — what already exists here. `tools/blast.py --find <keyword>` before adding a function.

```
src/o4_engine — the Controller layer of Ortho4XP's one-engine / many-views architecture
10 modules | exports another module uses, most used first (36 unused exports not shown)
download_meter  Process-wide download telemetry for build-t… | record begin update +1
events  Typed events — the engine protocol's vocabu… | ScanBatch TileState StepProgress +19
failure_report  The failure report a user sends us: redacte…
jsonl  JSON-lines standard-input/output transport…
parallel  Parallel tile builds: the phase-aware subpr… | ParallelBuildRun
redaction  Redaction of text that leaves the user's ma… | RULES KEPT Redactor
secret_broker  Secret-store brokerage: route platform-secr… | SecretBroker
session  EngineSession — the Controller of the one-e… | EngineSession build_done plan_steps +3
task_meter  Process-wide pacing telemetry for countable… | begin advance end
tile_time_model  Learned per-step wall-clock estimates for w… | remaining_step_seconds estimate_texture_features record_build +2
```

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

