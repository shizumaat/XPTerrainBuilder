# PROJ runtime robustness in frozen builds — spec

Status: FROZEN (Fable, 2026-08-27). Deviations require Fable review
(resume the spec author), per the standing owner ruling.

## 1. Problem and confirmed mechanism

Field report (alpha 2, Windows, 2026-08-27): every airport elevation
inset fetch fails with

    WARNING: elevation inset fetch for <ICAO> from COPERNICUSGLO30 failed without a durable answer: ...
    May be caused by: PROJ: proj_create_from_database: C:\Users\...\

and the build continues silently degraded to base-DEM-only terrain.

Mechanism, confirmed in this tree:

- The frozen bundle carries TWO independent libproj copies: pyproj's
  wheel (libproj 9.5.1 + its own matched `proj.db` under
  `pyproj/proj_dir/share/proj/`) and GDAL's. The vendored Windows wheel
  `Utils/win/gdal-3.12.2-cp313-cp313-win_amd64.whl` ships
  `osgeo/proj_9.dll` AND its own matched `osgeo/data/proj/proj.db`.
- Both entry scripts (`Ortho4XP.py` lines 36–45, `Ortho4XP_Qt.py`
  lines 22–30) force the GLOBAL env var `PROJ_DATA` at pyproj's data
  dir. GDAL's libproj then opens pyproj's `proj.db`; any database
  layout-version skew between the two PROJ builds fails
  `proj_create_from_database` — deterministically, for every Windows
  user. (On macOS the same one-db-two-libproj architecture holds with
  the Homebrew-linked GDAL; it happens to work today only when the
  versions align.)
- Both PyInstaller specs additionally overlay the FREEZE MACHINE's
  system `proj.db` (`get_system_proj_db()`) over pyproj's — a third
  version source. On the Windows CI runner (no system PROJ) this
  degrades to a harmless self-copy; on any machine with
  OSGeo4W/conda/Homebrew it injects an unrelated version.
- A user machine with `PROJ_LIB`/`PROJ_DATA` set globally (QGIS,
  PostGIS, OSGeo4W installs commonly do this) can hijack the search
  path the same way.

Design principle: **each bundled libproj reads only the `proj.db` it
shipped with; the user's environment cannot redirect it; a broken PROJ
runtime refuses to build instead of degrading.**

## 2. Design decisions (frozen)

D1. **No system proj.db.** Delete `get_system_proj_db()` and the
    `(system_proj_dir, proj_dest)` datas entry from BOTH specs
    (`Ortho4XP.spec`, `Ortho4XP_Qt.spec`). pyproj's own wheel data
    (already collected by PyInstaller's pyproj hook into
    `pyproj/proj_dir/share/proj/`) is the pyproj database.

D2. **Bundle GDAL's own PROJ data, resolved at freeze time.** In both
    specs, resolve GDAL's proj data directory from the freeze venv:
    (a) `os.path.join(os.path.dirname(osgeo.__file__), "data", "proj")`
    if it contains `proj.db` (the Windows wheel case); else
    (b) the first entry of `osgeo.osr.GetPROJSearchPaths()` containing
    `proj.db` (the macOS Homebrew-linked case).
    Bundle that directory's contents to dest `osgeo/data/proj`.
    If `osgeo` is not importable in the freeze venv (the Linux job
    deliberately omits gdal), skip with a printed notice. If osgeo IS
    importable but neither (a) nor (b) finds a `proj.db`, FAIL the
    freeze with a clear message — never ship a guess.

D3. **Runtime pinning + environment scrub (frozen mode only).** New
    module `src/O4_Proj_Runtime.py` (type hints, docstrings, headless,
    imports only `os`/`sys` at module level; pyproj/osgeo imported
    inside functions):

    - `scrub_proj_env() -> None`: `os.environ.pop` of `PROJ_LIB`,
      `PROJ_DATA`, `PROJ_AUX_DB`, `GDAL_DATA`, `GDAL_DRIVER_PATH`;
      then `os.environ["PROJ_NETWORK"] = "OFF"` (determinism: no grid
      downloads).
    - `frozen_proj_dirs(meipass: str) -> tuple[str | None, str | None]`:
      returns `(pyproj_dir, gdal_dir)` where
      `pyproj_dir = <meipass>/pyproj/proj_dir/share/proj` and
      `gdal_dir = <meipass>/osgeo/data/proj`, each replaced by `None`
      when `proj.db` is absent there. Pure path logic — unit-testable
      against a `tmp_path` fake tree.
    - `pin_frozen_proj(meipass: str) -> None`: calls
      `scrub_proj_env()`; if `gdal_dir` exists, sets
      `os.environ["PROJ_DATA"] = gdal_dir` (steers GDAL's libproj —
      GDAL has no pre-import Python API for search paths); if
      `pyproj_dir` exists, imports pyproj and calls
      `pyproj.datadir.set_data_dir(pyproj_dir)` (explicit set outrides
      the env var for pyproj, so the two libraries diverge correctly).
      If `gdal_dir` is None (no-GDAL bundle), leave `PROJ_DATA` unset.
    - `preflight() -> str | None`: returns None on success, else a
      multi-line diagnostic. Checks: (1) pyproj
      `Transformer.from_crs(4326, 3857)` transforms one point; (2) if
      `osgeo` imports, `osr.SpatialReference().ImportFromEPSG(4326)`
      returns 0 (an osgeo ImportError is NOT a failure — the Linux
      build has no GDAL). The diagnostic names:
      `pyproj.__version__`, `pyproj.proj_version_str`,
      `pyproj.datadir.get_data_dir()`, `osgeo.gdal.__version__` and
      `osr.GetPROJSearchPaths()` when available, `sys.frozen`,
      and the values of any `PROJ_*`/`GDAL_*` env vars still set.
      Stores the result in module global `PREFLIGHT_ERROR: str | None`
      (also the return value).

D4. **Entry-script wiring** (`Ortho4XP.py`, `Ortho4XP_Qt.py`, kept
    symmetric):

    - Replace the current frozen PROJ blocks (the `PROJ_DATA` export,
      the `from pyproj import datadir` + `set_data_dir` dance) with:
      inside the existing `sys.frozen and hasattr(sys, "_MEIPASS")`
      guard, AFTER the `sys.path` append for `src` in Ortho4XP.py has
      been arranged to precede it (frozen mode bundles src modules, so
      importing `O4_Proj_Runtime` there is safe; in source mode the
      block does not run):
      `import O4_Proj_Runtime; O4_Proj_Runtime.pin_frozen_proj(sys._MEIPASS)`.
      The `DYLD_LIBRARY_PATH` line and `PYTHONHASHSEED` handling stay
      exactly as they are.
    - Add a `--proj-selfcheck` dispatch, under the `__name__ ==
      "__main__"` guard, BEFORE the `--engine-jsonl` dispatch and
      before any heavy import: run `preflight()`, print the diagnostic
      or `PROJ selfcheck OK`, `sys.exit(1 if error else 0)`.
    - Call `preflight()` once at process start, under the
      `__name__ == "__main__"` guard (so multiprocessing helper
      re-imports and `--engine-worker` children skip it), in BOTH
      frozen and source modes. On failure print the diagnostic
      prefixed `ERROR: PROJ runtime self-check failed` to stderr; the
      process keeps running (browsing/UI still work) — builds refuse
      per D5.

D5. **Build gate.** Every user-triggerable pipeline step entry — the
    functions using the `if UI.is_working: return 0` / `UI.is_working
    = 1` step pattern in `src/O4_Vector_Map.py`, `src/O4_Mesh_Utils.py`,
    `src/O4_Mask_Utils.py`, `src/O4_Tile_Utils.py` (`build_tile`,
    `build_all`, and their sibling steps) — refuses when
    `O4_Proj_Runtime.PREFLIGHT_ERROR` is set, using the existing
    early-abort idiom (see `build_tile`'s mesh-file check,
    `src/O4_Tile_Utils.py:316`): `UI.lvprint(0, "ERROR: PROJ runtime
    is broken — builds are disabled to avoid a silently degraded
    tile.")` + the diagnostic, `UI.exit_message_and_bottom_line("")`,
    `return 0`. Implement as one tiny shared helper
    `O4_Proj_Runtime.refuse_reason() -> str | None` consulted by each
    step. If the set of step entries is ambiguous, STOP and report —
    do not improvise.

D6. **CI smoke test (the real guard).** In
    `/Users/noah/XPTerrainBuilder/.github/workflows/release.yml`:
    after each freeze step, run the frozen executable with
    `--proj-selfcheck` and with `PROJ_LIB` and `PROJ_DATA` exported to
    a deliberately bogus directory; the step fails unless exit 0.
    - windows job: `dist/Ortho4XP_Qt/Ortho4XP_Qt.exe --proj-selfcheck`
    - linux job: `dist/Ortho4XP_Qt/Ortho4XP_Qt --proj-selfcheck`
    - mac job: the engine binary produced by `scripts/make_engine.sh`
      (locate its output path in that script) with `--proj-selfcheck`.
    Same step added to the three jobs of
    `Ortho4XP/.github/workflows/build-apps.yml`.
    The mac job's `brew install proj` step stays (macOS GDAL links
    Homebrew libproj; D2(b) reads its search paths) — update its
    comment to say why it is still needed.

## 3. Out of scope

- No new JSONL event types (wire-protocol hazard — Swift matches event
  class names as string literals). All reporting goes through existing
  `UI.vprint`/`UI.lvprint` prints and process exit codes.
- No change to source-mode (venv) environment handling beyond the
  preflight call: `scrub_proj_env` runs only via `pin_frozen_proj`.
- No sqlite-level `DATABASE.LAYOUT.VERSION` introspection — behavior
  (the preflight transform) is the check.
- No change to `O4_Airport_Elevation_Insets.py`.

## 4. Frozen public API

    O4_Proj_Runtime.scrub_proj_env() -> None
    O4_Proj_Runtime.frozen_proj_dirs(meipass: str) -> tuple[str | None, str | None]
    O4_Proj_Runtime.pin_frozen_proj(meipass: str) -> None
    O4_Proj_Runtime.preflight() -> str | None
    O4_Proj_Runtime.refuse_reason() -> str | None
    O4_Proj_Runtime.PREFLIGHT_ERROR: str | None
    CLI: --proj-selfcheck on both entry scripts (exit 0 healthy / 1 broken)

## 5. Acceptance criteria

1. `tests/test_proj_runtime.py` (new, headless, `tmp_path`-based, no
   network) passes:
   - `scrub_proj_env` removes all five vars when set, sets
     `PROJ_NETWORK=OFF`, tolerates none set (use
     `monkeypatch.setenv/delenv`).
   - `frozen_proj_dirs` on fake bundle trees: both dbs present, only
     pyproj's, only GDAL's, neither.
   - `pin_frozen_proj` against a fake tree with a real
     `pyproj`: `PROJ_DATA` lands on the fake gdal dir while
     `pyproj.datadir.get_data_dir()` reports the fake pyproj dir
     (restore the real data dir afterward with `set_data_dir`).
   - `preflight()` in the venv returns None (venv has healthy pyproj
     AND osgeo — both legs execute).
   - A monkeypatched failure (e.g. force
     `pyproj.Transformer.from_crs` to raise) yields a diagnostic
     containing the version and path lines, and sets
     `PREFLIGHT_ERROR`; `refuse_reason()` returns it.
   - Step-gate: with `PREFLIGHT_ERROR` monkeypatched non-None,
     `O4_Tile_Utils.build_tile` returns 0 without building (mock/stub
     at the level the existing tests for early aborts use, if any;
     otherwise a minimal tile stub).
2. `tests/test_version_scheme.py` still passes — the version-parser
   lines in `Ortho4XP_Qt.spec` are byte-identical (the test asserts
   the exact parser text appears in the spec file).
3. Both `.spec` files contain no `get_system_proj_db` and no reference
   to a system/OSGeo4W/conda/Homebrew proj path except via
   `osr.GetPROJSearchPaths()` per D2(b).
4. `--proj-selfcheck` from source (`venv/bin/python Ortho4XP.py
   --proj-selfcheck`, run from `Ortho4XP/`) exits 0 and prints
   `PROJ selfcheck OK`.

## 6. Constraints and hazards

- Read `docs/RULINGS.md` first; PRE-SHIP MODE is in force — run ONLY
  the test files named above, once. Skipped verification gets a line
  in `docs/DEFERRED_VERIFICATION.md`.
- Run `venv/bin/python ../tools/blast.py <file>` (from `Ortho4XP/`)
  before editing each `src/` file.
- Entry-script import ORDER is load-bearing: the scrub must run before
  the first pyproj/osgeo import in the process; the multiprocessing
  `freeze_support()` call and `__mp_main__`/`--engine-worker` guards
  in both entry scripts must not move (their comments document live
  crash classes).
- Core modules must not import a GUI toolkit; `O4_Proj_Runtime` must
  not import `UI` at module level (step gates fetch `refuse_reason()`
  and do their own printing).
- Keep `pyproj`/`osgeo` imports inside functions so importing
  `O4_Proj_Runtime` stays free.
- Do not rename any JSONL event class.

## 7. Build-time impact statement

Startup-only: one `preflight()` per top-level process (< 0.2 s,
excluded from both budgets, which measure build phases);
`--engine-worker` children and multiprocessing helpers skip it. Zero
per-airport and per-tile cost. Under the 1 % thresholds — no
optimization review required.

## 8. Deferred verification (record in docs/DEFERRED_VERIFICATION.md)

- Real frozen-app verification on Windows/macOS/Linux deferred to the
  next tagged release: the D6 CI smoke steps are the instrument; no
  local Windows machine exists.
- The alpha-2 user's exact failure string (mismatch vs missing) was
  never captured un-clipped; the fix removes both causes.
