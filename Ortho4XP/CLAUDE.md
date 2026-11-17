# CLAUDE.md (engine)

Rules in force only; history and precedents: `../docs/CLAUDE-history.md` —
read on demand. Owner law: `docs/RULINGS.md`; lane/master rules: root `CLAUDE.md`.

## Project

Ortho4XP builds X-Plane base mesh, water masks and orthophoto textures per
1°×1° tile.
- Entry points: `Ortho4XP.py` (engine + CLI: `--engine-jsonl`, tile builds;
  Tkinter GUI retired 2026-07-26), `Ortho4XP_Qt.py` (PySide6 GUI; all UI work
  targets it).
- Pipeline `src/O4_Vector_Map` → `O4_Mesh_Utils` → `O4_Mask_Utils` →
  `O4_Tile_Utils`. GUI↔core contract is `src/O4_UI_Utils.py` only
  (`progress_bar`, polled `red_flag`, stdout); core never imports a GUI toolkit.
- Settings registry `src/O4_Cfg_Vars.py`; configs are flat `key=value`.
- Tests: pytest in `tests/` (`-n0` to debug serially). Design docs:
  `docs/UI_MODERNIZATION.md`, `docs/specs/`, `docs/mockups/`.
- `src/auto_patch/` has its own `CLAUDE.md`; defer to it there.

## Working rules (PRE-SHIP MODE, RULINGS 2026-08-09; BUILD ECONOMY 2026-08-29e/f)

A brief demanding more verification than this section is invalid.
- Synthetic-first: iterate on `tools/v2_solve_replay.py --capture ICAO`, then
  `--replay --from STAGE` (`--why-hard`, `--probe-site`, `--emit`, `--verify`;
  `tools/INDEX.md` row), offline replays and twins. The real airport builds
  ONCE, as the closing test: ONE representative airport (the owner's site).
  The five-airport sweep runs once per merged batch at app-build time.
- Controls are shared via the artifact ledger (`build_airport --base-arm`);
  never rebuild one that exists.
- Fixes ship ungated; rollback is `git revert`. Gates only for a mechanism
  awaiting sim adjudication or an active experiment knob, removed once
  adjudicated. No routine OFF-arm byte-identity builds (only shared
  solve/emit-path changes); no default-pinning twins. Refuted mechanisms are
  deleted.
- Site-first reporting: owner-site numbers in the current configuration
  first; a below-bar merge needs owner sign-off with the residual quoted.
- The spawner owns the merge, same day; follow-ups are reported back, never
  spawned onward.
- Suspended until the first official release: per-edit blast-radius and full
  suites (run only the tests covering the change, once), per-lane acceptance
  batteries. Kept: root cause first, written specs, shared-repo guard +
  harness, never writing the real X-Plane install, per-change unit tests,
  convergence guards. Each skipped verification gets a line in
  `docs/DEFERRED_VERIFICATION.md`.
- Every brief carries exact paths, the frozen public API, acceptance tests,
  constraints, a link to `docs/RULINGS.md` (a brief violating a ruling is
  invalid; deviations are ruled by the owner), and a build-time impact
  statement. Agents never change a public interface; blocked → report.
- Convergence guards (2026-08-02): materiality floor (default 0.01 m /
  0.01 pp → PASS-with-residual); at most 2 fix iterations per target, then
  stop and report; long work writes `.progress` START/step/EXIT stamps.
- Never delegate interface design, UX copy, destructive operations,
  security-sensitive code, or the final review.

## 6. Build-time hard law (2026-07-18; per-change part SUSPENDED 2026-08-04)

Budgets, cold, excluding downloads: per-airport auto-patch ≤ 60 s; whole-tile
compute ≤ 300 s (provisional). During the campaign the free ledger tripwire
(~2× anomaly ⇒ investigate) replaces per-change 1 % evaluations and Fable-5
reviews; budgets are adjudicated in the final profiling round. Crossing a
budget, or regressing an over-budget build ≥ 1 %, needs a written
explanation and explicit owner approval. Check:
`venv/bin/python tools/check_build_time.py` (`tools/build_time_baselines.json`,
`tools/build_time_approvals.json`).

## Conventions

- New modules: type hints, docstrings, no `exec`/`eval`. Tests for new
  modules are mandatory and headless (`tmp_path`, no network, no X-Plane).
- Run ledger (2026-07-18): correctness runs (pytest, builds, `check_grade`) go
  through `venv/bin/python tools/run_with_ledger.py -- <cmd>`; check
  `--history` first. Never wrap wall-time benchmarks.
