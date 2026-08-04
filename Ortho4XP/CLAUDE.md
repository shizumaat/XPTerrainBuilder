# CLAUDE.md

## Project

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

## Working style — agent delegation model (token policy)

This repo is worked with a lead-session + subagent model to spend
top-tier-model tokens only where judgment is required:

1. **The lead session (Fable) is architect and reviewer.** It owns
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

## Conventions

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
