# CLAUDE.md history and precedents

Read on demand. The two `CLAUDE.md` files carry only the rules in force,
tersely. This file keeps what was moved out of them on 2026-11-17 (owner
yes 2026-11-17T21:02Z: "tighten the two CLAUDE.md files"): the precedents,
the "why" stories, superseded versions, amendment dates and the
pre-ship / build-economy narrative. Nothing was deleted: below is the full
text of each file as it stood before the trim (root at `7c700214e`-era
main), verbatim. Canonical law stays in `Ortho4XP/docs/RULINGS.md`.

Superseded in the trim (kept here only):
- `Ortho4XP/CLAUDE.md` 1a "Fable is design and review only / Fable writes
  ALL specs / deviations reviewed by a Fable agent" (owner 2026-07-30):
  superseded by root "Lanes" MODEL rule (RULINGS 13c, 2026-10-13: specs and
  review on Opus; Fable per approved launch or the one-miss review).
- `Ortho4XP/CLAUDE.md` 2 "Delegate mechanical work to Opus" and 1 "the
  lead writes judgment-heavy code itself": superseded by root "Lanes"
  (2026-09-03) and "Single master" (2026-10-02): the master dispatches.
- Two-round cap (RULINGS 2026-10-20b): replaced by the one-miss cap
  (RULINGS 2026-11-11c); the hook marker keeps the old name.
- Fable 5 per-change build-time review: suspended (RULINGS 2026-08-04).

---

## Root `CLAUDE.md` before the trim

## XPTerrainBuilder

macOS Swift app + vendored Python engine that builds X-Plane ortho scenery.

- `Sources/` — SwiftPM targets: `SceneryKit` (engine client + models),
  `XPTerrainBuilder` (app). Build: `swift build`; app bundle:
  `./scripts/make_app.sh`; bundled engine: `./scripts/make_engine.sh`.
- `Ortho4XP/` — the Python engine. It has its own `CLAUDE.md`, and
  `src/auto_patch/` another; read them before engine work (the hard
  build-time law lives there). Python is `Ortho4XP/venv/bin/python`
  (no system python; `venv/bin/pip` is broken — use `python -m pip`).

### Lanes (owner standing 2026-09-03)

The session is the project manager (the model the owner set for the
session — Opus 5.5 since 2026-10-12; never switched by the session). Work is
dispatched to subagents via the project definitions in `.claude/agents/`
(default effort medium). EFFORT (owner ruling 2026-10-20, RULINGS
2026-10-20a): lane effort is set per task at launch: low for landing,
rebases, ratchets, census/replay runs and cleanup; medium for fixes with
a spec; high for geometry/solver design and spec writing; xhigh only for
architecture work (e.g. #412 cold patch). The definitions are: `lane` (implementation, all tools) and `scout`
(read-only research). MODEL (owner standing 2026-10-13, RULINGS 13c;
replaces the 2026-09-03 evening amendment): lanes and scouts run on
**Opus** (`model: "opus"`) — implementation, measurement, attribution,
audits, specs and review alike. **Fable 5.1 (`model: "fable"`) is launched
only after the owner has approved THAT launch in chat**: the master names
the brief and why Opus is not enough, and waits for the yes. "The brief
needs judgement" is not a reason; a brief with law in it is still an Opus
brief. The approved launch's prompt carries the line
`OWNER-APPROVED-FABLE: <date> "<the owner's words>"`, without which the
hook refuses it. ONE-MISS CAP (owner 2026-11-11, RULINGS 2026-11-11c; replaces the
two-round cap of 2026-10-20b): the FIRST time an Opus round on a task
fails to deliver, the master stops that lane and launches a Fable 5.1
reviewer at once — `subagent_type: "scout"` (read-only), prompt carrying
`TWO-ROUND-CAP-REVIEW: <issue> <the failed round(s)>` (the hook's marker
keeps its old name) — that reviews the failed round and writes a new
spec; it NEVER implements. Opus never retries a missed round on its own.
A fresh Opus lane then runs the next round from that spec; if that round
also misses, the task goes to the owner (park / ship / redesign) — never
another attempt (owner 2026-11-03, RULINGS 2026-11-03d).
This is the only Fable use that needs no per-launch yes. A Fable lane is
never resumed (`SendMessage`) for a new
piece of work — each round re-reads its whole context at Fable price; its
follow-up goes to a fresh Opus lane on its branch. The master reads
`get_usage` (Weekly · Fable) at session start and before asking for a
Fable launch, and reports the figure with the request. Precedent: on
2026-10-12/13 nine of 32 lanes were launched on Fable for implementation
briefs and used 50 % of the weekly Fable allowance in under a day.
EFFICIENCY (owner 2026-11-03, RULINGS 2026-11-03d): at most 8 lanes run
at once (builds compete for CPU); the worktree cap is 16 and a new lane
reuses a merged worktree (`lane_worktree.sh up`); anything that needs a
permission (close, delete, a public create) is asked in the owner's own
thread, not relayed; each morning starts a fresh master from a short
handoff note; every lane report ends with a "Process" line when friction
cost time or usage; a sim read is diagnosed only after checking the app
version in its build log, and a test app is handed over as "quit the app
and open XPTerrainBuilder-<v>.app".
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

**Time (owner standing 2026-10-17), for managing subagents:** Time matters
here: do not spend time that can be avoided, and the earlier a correct
result is obtained, the better.

### Lane cap, cleanup and disk (owner HARD RULE 2026-11-06)

The disk filled (ENOSPC) on 2026-11-06: the master told lanes to raise
the worktree cap (41 trees against 16) and ran many tile builds at once,
and every session stalled until the owner cleaned up by hand. Never again:

- At most 16 lane worktrees and about 8 running lanes. Never raise the cap
  (`lane_worktree.sh` now ignores an `O4_LANE_CAP` above 16). When it
  refuses, the master cleans up first.
- The moment a lane reports, the master pushes its branch, then removes
  its worktree and deletes its scratch builds (tile dirs, pack copies).
- Before launching a lane that builds, check `df -h` (30 GB free or more).
  At most 4 builds run at once (owner 2026-11-06T05:06Z). `build_airport.py` refuses a tile
  build under 30 GB free and a patch build under 5 GB, with no override.
- Every lane brief says: "never raise the lane cap; delete your scratch
  builds when you report".

### Single master (owner standing 2026-10-02)

ONE session is the project master: it alone talks to the owner, dispatches,
measures, merges and records rulings. Lanes — local (`Agent`, needs the
corpus) and cloud (`RemoteTrigger` routines, code + twins only; briefs live
in `docs/cloud-briefs/<date>/` and the trigger prompt just points at the
file) — report ONLY to the master: a local lane through its final report, a
cloud lane through its PR body. Lanes NEVER comment on issues, NEVER merge,
NEVER create a routine/trigger or follow-up, NEVER notify the owner. The
master lands PRs in batches (owner standing 2026-10-20T00:34:25Z: "If we
did say 10 at a time, we would only need to revert and test one at a time
if something failed"): it merges up to ~10 ready PRs onto one integration
branch from main and runs CI and the landing check ONCE on the batch (all
of `tests/auto_patch_v2`, the closure and registry twins, `test_v1_retired`,
and each PR's own site gate on one merged build). Green lands the batch;
red is bisected and only the PR that broke it is dropped. It posts the one
evidence comment per issue, and messages the owner once per decision or
ready build (PushNotification when Remote Control is on). Handoff between
master sessions is the memory checkpoint + `Ortho4XP/docs/RULINGS.md` + the
issue tracker.

### Beta 2 gate (owner standing 2026-09-18)

`docs/BETA2-BLOCKERS.md` is the beta 1 feedback list (23 rows). ANY attempt
to cut beta 2 — tag, release notes, app build for release — first runs
`bash scripts/check_beta_blockers.sh` and stops on a refusal; the release
workflow enforces the same through `scripts/check_tag_version.sh`. Rows are
never deleted; only the owner moves a row to `CLOSED` (sim read) or
`WAIVED` (ruling). Lanes working a row cite its ID and update its
Status/Notes in the same commit as the evidence.

### Issue tracker (owner 2026-09-18)

GitHub Issues on `shizumaat/XPTerrainBuilder` is THE tracker for bugs and
features (`gh issue list`, `gh issue view N`). It is PUBLIC.

- Start of session: `gh issue list --label blocker` and
  `gh issue list --milestone "Beta 2"` — before trusting a memory note.
- A lane FIXES a bug it finds in its own PR and lists it in its report
  (owner 2026-11-03, RULINGS 2026-11-03c). It gets an issue only when it needs
  an owner decision or review, lies in files another running lane is
  changing, or is too large for that change.
- A bug or feature the owner mentions, or a defect that falls under one of
  those three, gets an issue the same turn: labels `bug`/`feature`, one or more
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

### Blast-radius index (check before editing)

Before editing anything under `Ortho4XP/src/` or `Sources/`, run:

    Ortho4XP/venv/bin/python tools/blast.py <file>

~100-token answer: direct importers, tests to run, role-literal / env-flag /
wire-protocol hazards, co-change neighbors. Self-rebuilds when stale (~2 s).
`tools/blast.py --audit` verifies index recall against grep ground truth.

Before ADDING a function, class or module, look for the existing one:

    Ortho4XP/venv/bin/python tools/blast.py --find <keyword> [<keyword>…]
    Ortho4XP/venv/bin/python tools/blast.py --map [<package>]

`--find` answers "does it exist?" (`name(args)`, `file:line`; `[shared N]`
marks the one N other modules already use — extend that one). `--map` is one
line per module of a package, or one line per package with no argument. The
map is generated from docstrings and `__all__`, never hand-written;
`tools/brief_pack.py --map <package>` puts it in a lane's brief.
`tools/ratchets.py layers` gates `auto_patch_v2`'s package order.

### Reuse and readable modules (owner RULINGS 2026-10-04 "FILE SIZE…" a/b/c)

The goal is clean, human-readable code that the next session can fix and add
to cheaply: small modules with one responsibility, and no second
implementation of a thing that exists. Extend what is there; a new family
member (provider, constraint, emit adapter) is a new file in its package,
never an append. 1,000 lines is a GUIDE and a warning, never a gate:
`tools/ratchets.py` reports long and growing files (and long functions) for
the master to read at merge. Split because a file holds two
responsibilities — never fold comments or cut a file at 999 to make a number.
What IS gated: the identical-duplicate count, the near-duplicate count
(`tools/ratchets.py dupes --near`) and the unused-definition count
(`tools/ratchets.py unused`, #740; dynamic use goes in
`tools/unused_allowlist.json` with a reason) may fall, never rise.
Every lane report carries net lines added/removed and new public symbols.

### No airport-specific code (owner standing 2026-10-05, RULINGS 05e)

An airport is a TEST CASE. It shows a defect; the fix is a GENERAL rule that
every airport is read by. No engine, app or law-table code may ask which
airport it is building: no ICAO literal, no table or key named for an
airport, no pack name, no coordinate window, no threshold tuned so that one
named airport passes. If no witness in the geometry or the map separates two
cases, that is a finding for the owner — never a switch. Briefs name an
airport as the place a defect was found and as the closing test, never as
the scope of the fix. `Ortho4XP/tests/test_no_airport_specific_code.py`
gates it; its RECORDED set is empty since RULINGS 2026-10-05g and may never
rise.

### Two UIs, one layout (owner 2026-10-22, #1244)

The Mac app (`Sources/XPTerrainBuilder`) is the layout authority; the Qt
window (`Ortho4XP/src/O4_Qt_*.py`, what Windows and Linux users run)
mirrors it. A change to either app's toolbar, build box or Settings lands
in BOTH in the same PR, or records an owner-ruled exception in the
manifest of `Ortho4XP/tests/test_qt_layout_parity.py`, which fails when
the two differ. A spec that adds a control names its home in both apps.

### Cross-language wire protocol (silent-break hazard)

`Ortho4XP/src/o4_engine/events.py` class names ARE the JSONL wire names
(`type(self).__name__`); `Sources/SceneryKit/OrthoEngineClient.swift` matches
them as string literals. Renaming either side breaks the other silently —
the string never appears in Python source. `blast.py` reports drift.

### Doc landmines

- `docs/HANDOVER.md` and `docs/PITFALLS.md` describe the retired
  XPSceneryDoctor app: their file maps are wrong; the numbered gotcha
  lore is still valid.
- `Ortho4XP/STATUS.md`: only the TOP dated block is current; the rest is
  history. Never load it whole (~90k tokens).

### The standard test harness (build and measure ONLY through this)

Five entries, run from `Ortho4XP/`. They are THE way to build and measure;
a lane-private build or census wrapper is a **defect**, not a shortcut.

    venv/bin/python tools/harness/build_airport.py ICAO [--tile LAT LON] [--dem M]
    venv/bin/python tools/harness/census.py PATCH.osm [PATCH.osm ...]
    venv/bin/python tools/harness/oracle.py ICAO
    venv/bin/python tools/harness/drawn_gate.py ICAO --tag T [--site NAME=LAT,LON[,R]] [--against BASE.json]
    tools/harness/lane_worktree.sh {up|check|down} NAME [REF]
    tools/harness/lane_worktree.sh data          # who is on which corpus

**Drawn gate (owner 2026-11-13T03:17Z, RULINGS 2026-11-13g, #1903).** A
lane's closing tile build runs with `--pack-copy`, and its closing bar is
`drawn_gate.py` PASS at the round's `--site`s and `--against` the control
(no MOVED): the gate reads the mesh, patch and objects as X-Plane draws
them. `build_airport.py --tile` runs it and writes `<tag>.drawn.json`. A
replay or census pass alone is not a lane pass (LOWS/LGAV/KIAH/KLAX passed
those bars while the drawn objects were unchanged). A one-tile build cannot
measure claims that live on the neighbour tile: build both, or say so.

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

#### Traps the harness now makes impossible (stop hand-checking these)

The list (wrong cwd, cold DEM, missing sidecar, private corpus, implicit
downloads, suite writes, Qt under xdist, network in tests, unbounded
waiters) lives in `Ortho4XP/tools/harness/CLAUDE.md`. Each is a refusal
that names itself; read that file when one fires.

#### Traps still on you

- Single-run wall times swing ±25%: never A/B one run per side (use the
  build-time checker's `--runs N`), and never let a timing run through the
  ledger (`build_airport.py --no-ledger`).
- Background / `nohup` builds inherit nice 5 and land on efficiency cores:
  foreground only for anything timed.

---

## `Ortho4XP/CLAUDE.md` before the trim

## CLAUDE.md

### Project

Ortho4XP — scenery generation tool for X-Plane: builds base mesh, water masks,
and orthophoto textures per 1°×1° tile.

- **Entry points:** `Ortho4XP.py` (engine + CLI only: `--engine-jsonl` protocol
  and tile builds; the Tkinter GUI was retired 2026-07-26), `Ortho4XP_Qt.py`
  (PySide6 map-first GUI).
- **Pipeline:** `src/O4_Vector_Map` → `O4_Mesh_Utils` → `O4_Mask_Utils` →
  `O4_Tile_Utils`. The GUI↔core contract is `src/O4_UI_Utils.py` only:
  `progress_bar(nbr, pct)`, the polled `red_flag` cancellation flag, and
  stdout prints. Core modules must never import a GUI toolkit.
- **Settings registry:** `src/O4_Cfg_Vars.py` (types, defaults, hints);
  config files are flat `key=value` (`Ortho4XP.cfg`, per-tile
  `Ortho4XP_+XX+YYY.cfg`).
- **Tests:** pytest, `tests/` (`pytest.ini`; use `-n0` for serial debugging).
- **Design docs:** `docs/UI_MODERNIZATION.md` (plan + revisions),
  `docs/specs/` (feature specs), `docs/mockups/` (reviewable HTML mockups).
- The `src/auto_patch/` subsystem has its own `CLAUDE.md`; defer to it there.

### Working style — agent delegation model (token policy)

**PRE-SHIP MODE IS IN FORCE (owner 2026-08-09; canonical text in
`docs/RULINGS.md` "PRE-SHIP DEVELOPMENT MODE" — read it before
writing any implementation brief).**

**BUILD ECONOMY + GATES (owner 2026-08-29e/f — BRIEFS MUST NOT
RE-IMPOSE SUSPENDED RITUAL; a brief demanding more verification than
this section is INVALID, same as one violating a ruling):**
- Iteration is SYNTHETIC-FIRST: mechanisms iterate on captures and
  stage replays (`tools/v2_solve_replay.py --capture ICAO` once, then
  `--replay --from STAGE` per change; `--why-hard`, `--probe-site`,
  `--emit`, `--verify` — see its `tools/INDEX.md` row), offline replays
  and synthetic twins; the v1 `repro_cut.py` / `solve_cut.py` are retired
  (stage B, 2026-09-17). The real airport builds ONCE, as the closing test.
- ONE REPRESENTATIVE AIRPORT per round's acceptance — the airport
  carrying the owner's site. The five-airport sweep runs once per
  merged batch at app-build time, never per lane.
- CONTROLS ARE SHARED: one control per (airport, base-sha)
  machine-wide via the artifact ledger (`build_airport --base-arm`);
  never rebuild a control that exists.
- FIXES SHIP UNGATED; rollback is `git revert`. Gates only for a
  mechanism awaiting the owner's sim adjudication or an active round's
  experiment knob, REMOVED once adjudicated. No routine OFF-arm
  byte-identity builds (only for shared solve/emit-path changes), no
  default-pinning twins. REFUTED MECHANISMS ARE DELETED, not
  retired-kept-gated — the refutation record is the spec and git.
- SITE-FIRST REPORTING: every report quotes the owner-site numbers in
  the CURRENT configuration first; a below-bar merge requires the
  owner's sign-off with the residual quoted.
- CHIP/SESSION BRANCHES MERGE SAME-DAY, AND THE SPAWNER OWNS THE
  MERGE (owner 2026-08-29): whoever spawns a chip or lane merges its
  result branch when the completion lands — a fix on a `claude/*`
  branch is not fixed until it is on main. Chips spawned from inside
  chip sessions do not reach the owner's surface; a chip session's
  follow-up work items are REPORTED BACK to the spawner, never
  chip-spawned onward. (2026-08-29: a dozen finished chip fixes were
  found stranded, including the standing test_harness red.)

Until the first official
release, most verification weight below is SUSPENDED: no per-edit
blast-radius or full-suite runs (only the test files directly
covering the change, once), no per-lane acceptance builds/censuses/
battery proofs, short reports, ONE implementer per coupled
change-set. KEPT: root cause first, written specs, the shared-repo
guard + harness entries, never writing the real X-Plane install,
per-change unit tests run once, convergence guards. The owner's
in-sim pass is acceptance; each skipped verification gets a line in
`docs/DEFERRED_VERIFICATION.md`, all paid in one hardening round at
the ship gate.

This repo is worked with a lead-session + subagent model to spend
top-tier-model tokens only where judgment is required:

1. **The lead session is architect and reviewer.** It owns
   architecture, public interfaces, UX decisions, integration, and final
   review. It writes the judgment-heavy code itself (core widgets, wiring,
   anything user-facing in copy or behavior).
1a. **Fable is DESIGN AND REVIEW ONLY — never implementation** (owner
   2026-07-30). A Fable agent's brief stops at the design artifact; it
   must never be told to "write the spec, then implement it."
   Corollaries, both standing owner rulings:
   * **Fable writes ALL specs.** No spec is authored by an Opus agent or
     improvised inside an implementation brief.
   * **Any mid-implementation deviation from the spec must be reviewed
     and approved by a Fable agent** before it lands — implementers stop
     and report the deviation rather than deciding it themselves. Resume
     the spec's Fable author for the ruling so it is judged against the
     design intent.
   The one Fable exception the hard law below requires — the Fable-5
   whole-pipeline optimisation review — is review, so it fits the rule.
   If a Fable agent has already written code when this surfaces, stop it
   writing more but **keep the code** (owner: do not throw away work);
   require a handoff inventory naming each path's state as COMPLETE /
   PARTIAL / EXPERIMENTAL instead.
2. **Delegate mechanical, well-specified work to Opus subagents** (Agent tool
   with `model: "opus"`): leaf-module implementations against a frozen
   interface, test authoring, migrations and sweeps, doc formatting,
   large-file reconnaissance. Every Agent launch passes an explicit
   `model` — Opus by default, never left to inherit the session model.
3. **Every delegation prompt must include:** exact file paths, the frozen
   public API, acceptance criteria (tests that must pass), constraints
   (no GUI-toolkit imports in core modules, keep imports light), and a link
   to `docs/RULINGS.md` (canonical owner rulings — a brief that would
   violate a listed ruling is invalid; deviations are ruled by the owner,
   never decided by the agent). Agents may not change a public interface;
   if blocked, they report back rather than improvise.
   **Convergence guards (owner 2026-08-02, mandatory in every
   implementation brief):** (a) a MATERIALITY FLOOR per target — a
   residual below it (default 0.01 m for elevation classes, 0.01 pp for
   grades unless the spec says otherwise) is reported as PASS-with-
   residual, never iterated on; (b) an ATTEMPT CAP — at most 2 fix
   iterations per pre-registered target; a second miss is a STOP-and-
   report, not a third attempt; (c) a PROGRESS HEARTBEAT — long-running
   work writes START/step/EXIT stamps to its scratch dir (the
   `.progress` convention) so the lead can audit liveness without
   touching the agent.
4. **Run independent agents in parallel** (single message, multiple Agent
   calls). Verify all agent output by running its tests before integrating.
5. **Never delegate:** interface design, UX copy, destructive operations,
   security-sensitive code, or the final review.
6. **HARD LAW — build-time regressions (owner rulings 2026-07-18; this
   is the canonical text — other documents point here).**
   **[SUSPENDED IN PART, owner 2026-08-04 (RULINGS.md "Per-change
   timing gates SUSPENDED"): during the architectural campaign, no
   per-change 1% evaluations, exclusive timing runs, or per-change
   Fable-5 reviews — the free ledger tripwire (~2x anomaly ⇒
   investigate) replaces them; the budgets below remain law and are
   adjudicated once, in the final-design profiling round.]** Two budgets,
   both COLD and EXCLUDING download time: (a) per-airport auto-patch
   wall ≤ **60 s** (docs/specs/flat-airport-fast-path-spec.md §3.5);
   (b) whole-tile compute ≤ **300 s** (provisional figure, owner may
   revise). Any new code costing ≥ **1 % of the relevant budget**
   (0.6 s / 3 s) must be evaluated by a **Fable 5 optimization agent**
   (lead-session-class model — spawned inheriting a Fable lead's
   session model, never Opus) that considers the WHOLE pipeline and
   whether the increase can be avoided or offset. A change that moves
   a build across its budget — or regresses an already-over-budget
   build by ≥1 % — additionally requires a written explanation and
   **explicit owner approval** before landing. Gated-but-default-on
   code is not exempt. Every implementation-agent brief must include a
   build-time impact statement. Executable check:
   `venv/bin/python tools/check_build_time.py` (baselines:
   `tools/build_time_baselines.json`; owner approvals:
   `tools/build_time_approvals.json`).

### Conventions

- New modules: type hints, docstrings, no `exec`/`eval` (legacy code still
  has them; don't add more).
- All UI work targets the PySide6 app (Tkinter GUI removed 2026-07-26, owner
  ruling).
- Tests for new modules are mandatory and must run headless
  (`tmp_path`-based, no network, no X-Plane install required).
- **Run ledger (owner 2026-07-18):** correctness verification (pytest,
  airport builds, `check_grade`) goes through `venv/bin/python
  tools/run_with_ledger.py -- <command>`. Results persist across
  sessions in a gitignored ledger keyed by code-tree hash + argv +
  `O4_*` env; an identical already-passing run is reported from the
  ledger instead of re-executed. Check `--history` before repeating an
  expensive run another session may have done. Never wrap wall-time
  benchmarks (`tools/check_build_time.py --run`, profilers) — timing
  must always be measured fresh.
