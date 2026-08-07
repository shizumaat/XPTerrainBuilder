# XPTerrainBuilder

macOS Swift app + vendored Python engine that builds X-Plane ortho scenery.

- `Sources/` — SwiftPM targets: `SceneryKit` (engine client + models),
  `XPTerrainBuilder` (app). Build: `swift build`; app bundle:
  `./scripts/make_app.sh`; bundled engine: `./scripts/make_engine.sh`.
- `Ortho4XP/` — the Python engine. It has its own `CLAUDE.md`, and
  `src/auto_patch/` another; read them before engine work (the hard
  build-time law lives there). Python is `Ortho4XP/venv/bin/python`
  (no system python; `venv/bin/pip` is broken — use `python -m pip`).

## Blast-radius index (check before editing)

Before editing anything under `Ortho4XP/src/` or `Sources/`, run:

    Ortho4XP/venv/bin/python tools/blast.py <file>

~100-token answer: direct importers, tests to run, role-literal / env-flag /
wire-protocol hazards, co-change neighbors. Self-rebuilds when stale (~2 s).
`tools/blast.py --audit` verifies index recall against grep ground truth.

## Cross-language wire protocol (silent-break hazard)

`Ortho4XP/src/o4_engine/events.py` class names ARE the JSONL wire names
(`type(self).__name__`); `Sources/SceneryKit/OrthoEngineClient.swift` matches
them as string literals. Renaming either side breaks the other silently —
the string never appears in Python source. `blast.py` reports drift.

## Doc landmines

- `docs/HANDOVER.md` and `docs/PITFALLS.md` describe the retired
  XPSceneryDoctor app: their file maps are wrong; the numbered gotcha
  lore is still valid.
- `Ortho4XP/STATUS.md`: only the TOP dated block is current; the rest is
  history. Never load it whole (~90k tokens).

## The standard test harness (build and measure ONLY through this)

Four entries, run from `Ortho4XP/`. They are THE way to build and measure;
a lane-private build or census wrapper is a **defect**, not a shortcut.

    venv/bin/python tools/harness/build_airport.py ICAO [--tile LAT LON] [--dem M]
    venv/bin/python tools/harness/census.py PATCH.osm [PATCH.osm ...]
    venv/bin/python tools/harness/oracle.py ICAO
    tools/harness/lane_worktree.sh {up|check|down} NAME [REF]
    tools/harness/lane_worktree.sh data          # who is on which corpus

Why: two lanes each wrote their own census wrapper. One dropped
`terrace_joints_ll` (lawful declared terraces reported as violations); the
other dropped `ruleset` (an FAA airport judged under ICAO law) and
hand-enumerated 12 of the 21 law families, reporting 9 — HEAZ came out 100
where the harness censuses 110. Both wrappers looked right.

`check_grade.py` is the harness library — `LAW_FAMILIES`,
`law_context_from_sidecar`, `run_checks(family_out=...)`,
`run_checks_law_true`, `row_side`. Its CLI, the census and the pytest
fixtures share one code path; `Ortho4XP/tests/test_harness.py` twin-asserts
that they do. Adding a check to `run_checks` without registering it in
`LAW_FAMILIES` fails there.

**One shared data repo (owner ruling, RULINGS `e9daef5`).**
`/Users/noah/XPTerrainBuilderData` is THE data repo — DEM + insets, OSM
extracts + road feeds, airport mod cache, geotiffs, masks, DSF cache,
orthophotos. Every lane MOUNTS it through the ritual; a private cache is a
second corpus that warms on its own schedule, and two lanes on two corpora
do not measure the same thing. Downloads and cache regenerations are
EXPLICIT, locked, hash-stamped events — `build_airport.py --refresh-data
<scope>`, recorded in `<repo>/.harness/refresh_ledger.jsonl` — never a
build side effect. The precedent: a KCLT road-feed refresh ran inside a
tile build on 2026-08-05 01:47–01:55 and silently changed campaign hashes.
Lane *products* (`Patches`, `Tiles`, `Previews`, `tmp`) stay lane-local —
every tile build writes its emitted patches into `Patches/`, so sharing it
would put one lane's geometry into another lane's build.

**Tool discipline (owner ruling, RULINGS `7e90032`).** Consult
`tools/INDEX.md` BEFORE writing any script that builds, measures or audits —
a tool absent from the index is treated as absent, and every new tool lands
with its index entry in the same commit. Extend a near-fit (a parameter, a
subcommand); never fork it. The second use of a lane scratchpad script is
the signal to promote it into `tools/` with an index entry and a twin. A
slightly-different duplicate is a defect: the census-wrapper precedent above
is what that costs.

### Traps the harness now makes impossible (stop hand-checking these)

- Wrong build cwd — silently smaller layout, fake speedup: the build entry
  refuses.
- Cold DEM/inset cache, or a config frame diverging from production's
  (warm-vs-cold has moved terrain 12 m): the build entry refuses;
  `--allow-degraded-dem` is the explicit, recorded override.
- A patch emitted with no `.axes.json` sidecar, after which every census
  silently degrades to the context-free frame that overcounts: refused.
- A tile built with an empty `cifp_data_path`, which skips auto_patch
  entirely and still exits 0: `--tile` refuses.
- A lane worktree missing `OSM_data`, or with a COPIED `Elevation_data` (a
  second inset cache that warms on its own): `lane_worktree.sh` builds and
  audits it.
- A build on a PRIVATE data corpus, whose numbers no other lane can be
  compared with: refused; the corpus every data dir resolved to is recorded
  in `frame.json`.
- An implicit download or cache regeneration into the shared repo (the
  KCLT road-feed precedent): refused before the build, naming the artifact
  and the `--refresh-data` scope; and a full before/after snapshot after it
  reports any write that happened anyway, marking the run CONTAMINATED.
  Note `--allow-degraded-dem` does NOT authorise a write — accepting a
  worse measurement and authorising a change to everyone's data are
  different acts.
- Two lanes racing a cache regeneration: per-scope lock in the shared repo,
  refuse-and-report, never a silent block.
- A guard-blocked write inside DEM prep silently DEGRADING the frame
  (the engine's fallback was WARN + rc 0, `dem_inset_provenance` null,
  an 18.5k-vs-36k layout): refused before any patch is written, each
  blocked write named. The engine's `.lock` coordination files have a
  narrowly-scoped allowance (the lock primitive's create/remove only,
  recorded as churn, never contamination); no-op `mkdir`/`makedirs` on
  an existing shared dir is likewise allowed (mutates nothing). Real
  data writes beside either still refuse. `--allow-degraded-dem`
  covers this class too and still authorises NO write.
- A census that omits a law family, a sidecar key, or the ruleset:
  structurally impossible — the twins fail.

### Traps still on you

- Single-run wall times swing ±25%: never A/B one run per side (use the
  build-time checker's `--runs N`), and never let a timing run through the
  ledger (`build_airport.py --no-ledger`).
- Background / `nohup` builds inherit nice 5 and land on efficiency cores:
  foreground only for anything timed.
