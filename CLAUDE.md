# XPTerrainBuilder

macOS Swift app + vendored Python engine that builds X-Plane ortho scenery.

- `Sources/` — SwiftPM targets: `SceneryKit` (engine client + models),
  `XPTerrainBuilder` (app). Build: `swift build`; app bundle:
  `./scripts/make_app.sh`; bundled engine: `./scripts/make_engine.sh`.
- `Ortho4XP/` — the Python engine. It has its own `CLAUDE.md`, and
  `src/auto_patch/` another; read them before engine work (the hard
  build-time law lives there). Python is `Ortho4XP/venv/bin/python`
  (no system python; `venv/bin/pip` is broken — use `python -m pip`).

## Lanes (owner standing 2026-09-03)

The session is the project manager (Fable 5.1, high effort). Work is
dispatched to subagents at MODERATE effort via the project definitions
in `.claude/agents/`: `lane` (implementation, all tools) and `scout`
(read-only research). MODEL (owner amendment 2026-09-03 evening, Fable
limits are finite): lanes and scouts run on **Opus by default**
(`model: "opus"`); Fable 5.1 (`model: "fable"`) is reserved for briefs
where the judgement is the deliverable — spec authoring, attribution
that will become an owner ruling, and review — or when the owner asks.
Every `Agent` launch passes the model explicitly and one of those
`subagent_type`s — the PreToolUse hook `.claude/hooks/agent_guard.py`
refuses anything else (built-in types inherit the session's high
effort; definitions load at session start).
Lanes iterate synthetic-first on `tools/v2_solve_replay.py` captures and
stage replays (`--capture`, `--replay --from STAGE`, `--why-hard`,
`--probe-site`, `--emit`, `--verify`; the v1 `repro_cut.py` / `solve_cut.py`
were retired with the v1 engine, stage B 2026-09-17), build ONE
representative airport once as
the closing test, and never run the five-airport sweep (orchestrator,
once per merged batch — `Ortho4XP/CLAUDE.md` BUILD ECONOMY). The
spawner owns the merge. Current plan of record:
`Ortho4XP/docs/specs/zero-airside-plan-20260903.md`.

## Single master (owner standing 2026-10-02)

ONE session is the project master: it alone talks to the owner, dispatches,
measures, merges and records rulings. Lanes — local (`Agent`, needs the
corpus) and cloud (`RemoteTrigger` routines, code + twins only; briefs live
in `docs/cloud-briefs/<date>/` and the trigger prompt just points at the
file) — report ONLY to the master: a local lane through its final report, a
cloud lane through its PR body. Lanes NEVER comment on issues, NEVER merge,
NEVER create a routine/trigger or follow-up, NEVER notify the owner. The
master merges one PR at a time with a sweep after each, posts the one
evidence comment per issue, and messages the owner once per decision or
ready build (PushNotification when Remote Control is on). Handoff between
master sessions is the memory checkpoint + `Ortho4XP/docs/RULINGS.md` + the
issue tracker.

## Beta 2 gate (owner standing 2026-09-18)

`docs/BETA2-BLOCKERS.md` is the beta 1 feedback list (23 rows). ANY attempt
to cut beta 2 — tag, release notes, app build for release — first runs
`bash scripts/check_beta_blockers.sh` and stops on a refusal; the release
workflow enforces the same through `scripts/check_tag_version.sh`. Rows are
never deleted; only the owner moves a row to `CLOSED` (sim read) or
`WAIVED` (ruling). Lanes working a row cite its ID and update its
Status/Notes in the same commit as the evidence.

## Issue tracker (owner 2026-09-18)

GitHub Issues on `shizumaat/XPTerrainBuilder` is THE tracker for bugs and
features (`gh issue list`, `gh issue view N`). It is PUBLIC.

- Start of session: `gh issue list --label blocker` and
  `gh issue list --milestone "Beta 2"` — before trusting a memory note.
- A bug or feature the owner mentions, or a defect a lane finds and does not
  fix, gets an issue the same turn: labels `bug`/`feature`, one or more
  `area:*`, plus `blocker` / `regression` / `performance` / `needs-owner` /
  `needs-sim-read` as they apply; owner sites as `lat, lon` in the title.
- A merge that fixes one says `Fixes #N` in its merge commit (closes on push);
  comment the measured result (site numbers first) when closing by hand.
- NOT issues: owner rulings and law (`Ortho4XP/docs/RULINGS.md` stays canonical
  — issues LINK to the ruling), specs and findings (files; the issue links them),
  internal follow-ups (spec-author reviews of lane deviations, harness controls,
  `docs/DEFERRED_VERIFICATION.md`), and anything private (half-formed ideas,
  licensing questions) — those stay in `docs/`.
- `docs/BETA2-BLOCKERS.md` rows were migrated (#1–#20); the gate is now
  "milestone Beta 2 has no open `blocker`".

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

**Consumer census before cross-cutting geometry law (owner ruling,
RULINGS 2026-08-30l).** A change introducing a new shape class,
exemption, or region into the layout (a deck, mask, claim, protected
union) starts AT SPEC TIME with a census of EVERY pass that reads the
affected geometry — grep the region's accessors and roles/refs, seam-
probe where static reading isn't decisive — and rules each interaction
in ONE table before any consumer is edited. Prefer trimming a region
at its single derivation site over per-consumer vetoes. Precedent: the
bridge deck's vertical exemption was discovered against five consumers
one ~27-min build at a time (~8 rounds) when one table was 1–2 rounds.
The spec author also checks the model is emittable in a heightfield
mesh before seeking ratification.

**Tool discipline (owner ruling, RULINGS `7e90032`).** Consult
`tools/INDEX.md` BEFORE writing any script that builds, measures or audits —
a tool absent from the index is treated as absent, and every new tool lands
with its index entry in the same commit. Extend a near-fit (a parameter, a
subcommand); never fork it. The second use of a lane scratchpad script is
the signal to promote it into `tools/` with an index entry and a twin. A
slightly-different duplicate is a defect: the census-wrapper precedent above
is what that costs.

### Traps the harness now makes impossible (stop hand-checking these)

The list (wrong cwd, cold DEM, missing sidecar, private corpus, implicit
downloads, suite writes, Qt under xdist, network in tests, unbounded
waiters) lives in `Ortho4XP/tools/harness/CLAUDE.md`. Each is a refusal
that names itself; read that file when one fires.

### Traps still on you

- Single-run wall times swing ±25%: never A/B one run per side (use the
  build-time checker's `--runs N`), and never let a timing run through the
  ledger (`build_airport.py --no-ledger`).
- Background / `nohup` builds inherit nice 5 and land on efficiency cores:
  foreground only for anything timed.
