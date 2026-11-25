# XPTerrainBuilder

macOS Swift app + vendored Python engine building X-Plane ortho scenery.
Rules in force only; history and precedents: `docs/CLAUDE-history.md` — read
on demand. Canonical law: `Ortho4XP/docs/RULINGS.md`.

- `Sources/`: SwiftPM `SceneryKit` (engine client) + `XPTerrainBuilder` (app).
  `swift build`; `./scripts/make_app.sh`; engine `./scripts/make_engine.sh`.
- `Ortho4XP/`: the engine; read `Ortho4XP/CLAUDE.md` and
  `src/auto_patch/CLAUDE.md` first. Python is `Ortho4XP/venv/bin/python`
  (no system python; `python -m pip`).

## Master and lanes

- ONE master talks to the owner, dispatches, measures, merges, records
  rulings (2026-10-02). Lanes report only to it (cloud: PR body, briefs in
  `docs/cloud-briefs/<date>/`); never comment on issues, merge, create
  routines or notify the owner. Permission asks go in the owner's thread.
- Master: one message (PushNotification) per owner decision or ready build;
  each morning a fresh master from a short handoff (memory + RULINGS + issues).
- Landing: ≤ ~10 PRs on one integration branch; CI + landing check once
  (`tests/auto_patch_v2`, closure/registry twins, `test_v1_retired`, each
  PR's site gate on one merged build); bisect red. `Fixes #N` in the merge;
  closing by hand, comment the site numbers first.
- `Agent` launches pass `model` and `subagent_type` `lane`|`scout` (hook
  `.claude/hooks/agent_guard.py`). Effort (RULINGS 2026-10-20a): low =
  landing/rebase/ratchets/census/cleanup; medium = fix with spec; high =
  geometry/solver design, specs; xhigh = architecture.
- MODEL (owner 2026-11-17T21:23Z, RULINGS 2026-11-17q; replaces 13c's
  per-launch yes and the 11-13 standing yes): goal = best result, shortest
  clock time, least usage. Opus for all work, specs and reviews included.
  Fable (`scout`, never implementation, never resumed) only (a) after an
  Opus round misses (one-miss cap below), or (b) for an especially complex
  design: new architecture, or a new cross-cutting region/law that needs a
  consumer census. The master names which in the launch, with `get_usage`
  Weekly·Fable; the prompt carries
  `OWNER-APPROVED-FABLE: 2026-11-17 "use fable only for especially complex tasks or when an opus round has failed"`.
- ONE-MISS CAP (RULINGS 2026-11-11c): an Opus round misses → stop it, launch
  a Fable `scout` with `TWO-ROUND-CAP-REVIEW: <issue> <the failed round(s)>`
  to write a new spec (never implements; no per-launch yes); a fresh Opus
  lane runs it; a second miss goes to the owner.
- LANES ARE RESOURCE-AWARE (owner 2026-11-25T18:11-18:12Z, after a 217 GB
  swap-out): use all available resources but scale back when other apps
  need them — heavy jobs (capture/replay/build/census) admit by memory
  headroom and shed workers under pressure via `O4_Machine_Slots` (lane
  lmemgate), CPU at dev nice 15; never parallel captures in one lane.
- HARD RULE 2026-11-06: ≤ 8 running lanes, ≤ 16 worktrees (reuse via
  `lane_worktree.sh up`); never raise `O4_LANE_CAP`. `df -h` ≥ 30 GB before
  a build. Builds share memory machine-wide and yield to the owner's app
  build and X-Plane; never a fixed one-build limit (owner 2026-11-17T22:50Z).
  Dev processes run below running apps (owner 2026-11-18T01:01Z): the dev venv
  sets nice 15 at start (`venv/.../site-packages/o4_dev_nice.pth`;
  `O4_DEV_NICE=0` only for a timed run).
  On report: push, remove the worktree, delete
  scratch builds. Briefs say "never raise the lane cap; delete your scratch
  builds when you report".
- Lanes iterate synthetic-first and STOP at replay/capture evidence: no
  closing tile build (RULINGS 2026-11-17r). The integration builds each
  touched airport ONCE on the merged code and runs the drawn gate there at
  every lane's `--site`s; never the five-airport sweep; the spawner merges. Reports
  give net lines ± and new public symbols, plus a "Process" line on friction.
- Sim reads: check the app version in the build log; hand over as "quit the
  app and open XPTerrainBuilder-<v>.app". Time matters: earliest correct result.
- Plan of record: `Ortho4XP/docs/specs/zero-airside-plan-20260903.md`.

## Issues and beta gate

- GitHub Issues `shizumaat/XPTerrainBuilder` (PUBLIC) is the tracker; start
  with `gh issue list --label blocker` / `--milestone "Beta 2"`.
- A lane fixes bugs it finds in its PR and lists them (RULINGS 2026-11-03c);
  issue only if it needs the owner, sits in another lane's files, or is too
  large. Owner-mentioned bugs get an issue that turn: `bug`/`feature`,
  `area:*`, `blocker`/`regression`/`performance`/`needs-owner`/
  `needs-sim-read`; sites as `lat, lon` in the title. Rulings, specs,
  internal follow-ups and private notes are files, not issues.
- Release cuts first run `bash scripts/check_beta_blockers.sh` (CI:
  `scripts/check_tag_version.sh`). `docs/BETA2-BLOCKERS.md` rows are never
  deleted; only the owner closes/waives; lanes cite the row ID and update it.

## Code rules

- Before editing `Ortho4XP/src/` or `Sources/`: `tools/blast.py <file>`.
  Before adding code: `tools/blast.py --find <kw>` / `--map [<pkg>]`; extend
  the `[shared N]` one; a new family member is a new file in its package.
- GATES (may fall, never rise; RULINGS 2026-10-04): duplicates
  (`tools/ratchets.py dupes --near`), unused defs (`tools/ratchets.py unused`,
  allowlist `tools/unused_allowlist.json`); `ratchets.py layers`. 1,000 lines
  is a guide, not a gate; split by responsibility.
- No airport-specific code (RULINGS 05e/05g): no ICAO literal, per-airport
  table, pack name, coordinate window or tuned threshold; gate
  `Ortho4XP/tests/test_no_airport_specific_code.py` (RECORDED set empty).
- Two UIs (#1244): the Mac app is the layout authority; the Qt window
  (`Ortho4XP/src/O4_Qt_*.py`) mirrors toolbar/build box/Settings in the same
  PR or records an owner exception in `tests/test_qt_layout_parity.py`.
- Wire protocol: `o4_engine/events.py` class names ARE the JSONL wire names
  matched as literals in `Sources/SceneryKit/OrthoEngineClient.swift`; a
  rename on either side breaks silently.
- `docs/HANDOVER.md`/`docs/PITFALLS.md` describe the retired XPSceneryDoctor
  (gotchas valid, file maps wrong). `Ortho4XP/STATUS.md`: top block only.

## Harness (build and measure ONLY through it; from `Ortho4XP/`)

    venv/bin/python tools/harness/build_airport.py ICAO [--tile LAT LON] [--dem M]
    venv/bin/python tools/harness/census.py PATCH.osm [...]
    venv/bin/python tools/harness/oracle.py ICAO
    venv/bin/python tools/harness/drawn_gate.py ICAO --tag T [--site NAME=LAT,LON[,R]] [--against BASE.json]
    tools/harness/lane_worktree.sh {up|check|down|data} NAME [REF]

- A private build/census wrapper is a defect. `check_grade.py` is the library
  (`LAW_FAMILIES`, `run_checks`, `run_checks_law_true`, …); new checks
  register in `LAW_FAMILIES` (`tests/test_harness.py`).
- Drawn gate (RULINGS 2026-11-13g, run at integration per 17r): tile build with `--pack-copy`;
  bar = `drawn_gate.py` PASS at the `--site`s `--against` the control (no
  MOVED). Replay/census alone is not a pass; neighbour-tile claims need both tiles.
- Data repo `/Users/noah/XPTerrainBuilderData` (RULINGS `e9daef5`), mounted
  by the ritual; refresh only via `build_airport.py --refresh-data <scope>`.
  `Patches`/`Tiles`/`Previews`/`tmp` stay lane-local.
- Consumer census (RULINGS 2026-08-30l): a new region/exemption starts with
  ONE table of every pass reading it; trim at the derivation site; check
  heightfield emittability.
- Tools (RULINGS `7e90032`): consult `tools/INDEX.md` first; extend near-fits;
  new tools land with their index row; a scratch script's 2nd use → promote.
- Refusals: `Ortho4XP/tools/harness/CLAUDE.md`. Still on you: wall times
  swing ±25 % (`--runs N`, `--no-ledger`); time in the foreground only
  (background builds are niced onto efficiency cores).
