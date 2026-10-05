# auto_patch — the tile driver, the readers and the object stage

## What this package is now
`auto_patch` is what SURVIVED the v1 engine. The v1 pavement builder — its geometry
phase, per-surface solver, pair law, emitter and feature passes (104 modules, 185k
lines) — was deleted in stage B of the v1 retirement (round 1 2026-09-17 cut the import
seams; round 2 2026-10-04 deleted the tree). **v2 (`src/auto_patch_v2/`) is the only
engine** (RULINGS 2026-09-13au): it builds the planar map, generates the law
constraints from TOML tables, solves the airport's design surface in one staged solve
and emits the patch. Do not look here for surface construction, the solve or the law.

What is here is 28 modules, declared one by one in `tests/test_v1_retired.py` (`KEEP`).
That twin asserts three things: the production import closure reaches nothing under
`auto_patch/` outside `KEEP`; the modules on disk ARE `KEEP`, exactly; and no production
module names an `auto_patch` module outside `KEEP` as a string (the `__import__` blind
spot — see Gotchas). **A new module here is a visible edit to `KEEP`; new engine work
belongs in `auto_patch_v2`.**

This is an orientation map, not a manual. For in-flight state read only the TOP dated
block of `STATUS.md` (~90k tokens of append-only history; never load it whole).

## The modules
- **Drivers.** `driver.py` — `generate_auto_patches(tile, …)`, the per-tile entry point
  `O4_Vector_Map` calls: airport selection, the freshness gate
  (`_auto_patch_is_current`), parallel dispatch, placement. `engine_v2.py` — the
  per-airport v2 adapter (`build_write_verify_one_v2`: build, stamp the `<osm>` header,
  verify, place; `rebake_after_mesh`). `selection.py` — which airports a tile builds and
  the boundary policy. `progress.py`, `provenance.py` (freshness stamps, the config-gate
  inventory, `config_digest`).
- **Readers.** `apt_dat_reader.py`, `cifp_reader.py`, `dsf_reader.py`, `agp_reader.py`,
  `obj8_reader.py`, `osm_aeroway.py`.
- **Flat-site detector.** `flat_site.py` (the detector), `flat_site_mode.py` (production
  DEM prep's caller).
- **Object stage (post-mesh).** `post_mesh.py`, `object_rebake.py`, `object_anchor.py`,
  `object_frame.py`, `object_clusters.py`, `object_footprints.py`,
  `object_terrain_features.py`, `object_terrain_kinds.py`, `obj8_partition.py`,
  `mesh_sampler.py`. It re-seats scenery-pack objects onto the built mesh. Parts of
  `post_mesh` still accept v1-shaped facility records nothing constructs any more;
  they are BELIEVED unreached (not verified). The object-stage suites lost most of
  their tests with v1 (their inputs were built from deleted v1 record classes —
  `test_object_bridge_terrain` 148 → 9, `test_object_pads` 42 → 1), so coverage here
  is thin: add a test with any change, and trim an arm only after proving nothing
  reaches it.
- **Shared support.** `build_support.py` (apt.dat selection, the airports-OSM prefetch
  and its `is_cached` fetch predicate, `read_patch_source`, the local-metre frame,
  runway pairing), `config.py`, `geom_safe.py`.

## config.py
`config.py` holds the v1-era constants that something still READS (about 350 top-level
names; 325 that nothing named went with the deletion). Its readers are the modules above,
`auto_patch_v2`, and the CENSUS — `tools/check_grade.py` and
`tools/harness/law_support/` price a patch against the FAA / ICAO `Ruleset`s defined
there. v2's own law is DATA in `auto_patch_v2/law/*.toml`;
`tests/auto_patch_v2/test_law_tables.py` holds the tables against `config.py` while both
exist. `provenance.config_digest` hashes every public constant into the patch freshness
stamp, so adding or removing one invalidates built patches once. The rule → citation →
constant index is `docs/STANDARDS.md`; never hard-code a rule number at a call site.

## HARD LAW — build time
The canonical text is `Ortho4XP/CLAUDE.md` working-style item 6 (owner rulings
2026-07-18; partly suspended 2026-08-04 — the budgets stand, the per-change gates do
not). Both budgets are COLD and exclude download time: **per-airport auto-patch wall
≤ 60 s; whole-tile compute ≤ 300 s.** New code costing ≥ 1 % of the relevant budget is
evaluated against the whole pipeline; a change that moves a build across its budget
needs a written explanation and explicit owner approval. Every implementation brief
carries a build-time impact statement. Never A/B one run per side (single-run wall
times swing ±25 %); the checker is `tools/check_build_time.py` (`--runs N`), which
builds through the harness entry with `--no-ledger` and reads v2's stage clocks from
`<ICAO>.report.json`.

## Build & test workflow
- Repo: `/Users/noah/XPTerrainBuilder/Ortho4XP`. Use the venv: `venv/bin/python` (there
  is no system `python`). `venv/bin/pip` is broken — use `venv/bin/python -m pip`.
- Build, census and grade checks go ONLY through the harness entries in the root
  `CLAUDE.md` ("The standard test harness"): `tools/harness/build_airport.py`,
  `census.py`. A bare `tools/check_grade.py` run is a lane-private measurement, not
  evidence. `tools/harness/oracle.py` and `who_wrote.py`'s build mode were v1
  instruments and REFUSE BY NAME; v2's are `tools/v2_solve_replay.py` (`--capture`,
  `--replay --from STAGE`, `--why-hard`, `--probe-site`).
- Tests: Qt files serial first (`-n0 tests/test_qt_*.py`), then
  `--ignore-glob='tests/test_qt_*.py' tests`.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing a file here.

## Gotchas (these still bite)
- **A module NAMED in a string is invisible to the import closure.**
  `o4_engine/parallel.py` resolves its fetch predicates with `__import__` from a table
  of module names; one of them was `auto_patch.osm_load`, which no `import` statement
  reached after round 1. `is_cached` now lives in `build_support`, and
  `test_v1_retired` holds every such name inside `KEEP`. The same blind spot applies to
  the FREEZER: PyInstaller finds a module only through `import` statements, never
  through a name handed to `__import__` / `importlib` — such a module needs a
  `hiddenimports` entry in BOTH `Ortho4XP.spec` and `Ortho4XP_Qt.spec`. (A lazily
  imported THIRD-PARTY module must also be pinned in `requirements.txt`: the freeze
  venv is separate, and the suite cannot see the gap.)
- **Ortho4XP caches `auto_patch` imports.** The long-running app imports `auto_patch.*`
  lazily into `sys.modules` and never reloads. After editing source, a running app keeps
  the OLD modules (symptom: unexpected-keyword errors from a new+stale module mix).
  **Fix = restart.** A fresh `venv/bin/python` build always reflects HEAD.
- **The freshness stamp.** `engine_v2._stamp_header` is the ONE writer of the `<osm>`
  header `build_support.read_patch_source` / `driver._auto_patch_is_current` read back.
  A new build input that should invalidate a patch goes into `provenance.FRESHNESS_KEYS`
  and that stamp, never into a second header writer.
- **The wire protocol.** `driver` and `engine_v2` emit `o4_engine/events.py` events
  whose CLASS NAMES are the JSONL wire names the Swift client matches as string
  literals. Renaming one breaks the app silently (`tools/blast.py` reports drift).
- **DEM frame.** Production hands the build Ortho4XP's airport-SMOOTHED `tile.dem`. A
  standalone build must read the same frame — the harness refuses a cold or diverging
  DEM/inset cache rather than build on it. Do NOT add smoothing in production.
- **Temp/debug scripts and generated OSM dumps go in the session scratchpad or `/tmp`**,
  not the working tree.

## Other resources
- `docs/RULINGS.md` — canonical owner rulings (every brief links it; a brief violating
  a ruling is invalid). Read one entry with `tools/docq.py ruling <key>`.
- `docs/STANDARDS.md` — the FAA/EASA/ICAO rule index (rule → citation → constant).
- `docs/specs/auto-patch-v2-plan.md` and
  `docs/specs/auto-patch-v2/design-surface-spec.md` — the v2 engine (read one section
  with `tools/docq.py spec '§N'`, never the whole file).
- Reuse before new, and file size as a warning: root `CLAUDE.md` "Reuse and readable
  modules".
- `docs/v1-retirement/` (repo root) — the retirement inventory and its closure script (`g2.py`).
- `docs/elevation_solver.md`, `docs/auto_patch_tier2_plan.md`,
  `docs/TEST_PLAN_SPJC.md`, `docs/archive/README.md` — ⚠ HISTORICAL: they describe the
  deleted v1 engine.
