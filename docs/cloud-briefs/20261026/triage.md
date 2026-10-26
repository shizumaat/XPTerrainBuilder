# Open-issue triage: shizumaat/XPTerrainBuilder, 2026-10-26

Read-only. Source: `gh issue list --state open --limit 500` (116 open issues) plus every body and comment (`gh issue list --json number,title,body,comments`). The repo was checked at `claude/batch-y-beta5-b1` c67fd2a95. Severity and difficulty are triage judgements, not measurements.

## Summary

| Measure | Count |
|---|---|
| Open issues | 116 |
| In flight, excluded (#1340, #1346, #1352, #1353, #1354; PR #1368) | 5 |
| Type (all 116) | bug: 53 · feature: 41 · performance: 11 · app-report: 9 · tracking: 2 |
| Severity (all 116) | S1: 5 · S2: 59 · S3: 52 |
| Difficulty (all 116) | S: 22 · M: 62 · L: 27 · —: 5 |
| Local-only (111 not in flight) | YES: 70 · NO: 36 · PARTIAL: 2 · n/a (tracking/deferred): 3 |
| Cloud-able NO/PARTIAL rows | 38 (37 specs: #1220 folds into #1328) |
| … ready now | 33: #740, #818, #820, #824, #825, #1223, #1224, #1236, #1248, #1261, #1281, #1314, #1315, #1316, #1317, #1318, #1319, #1320, #1321, #1322, #1323, #1325, #1326, #1327, #1328, #1329, #1334, #1339, #1341, #1345, #1350, #1351, #1357 |
| … owner-gated (spec written, implement on the yes) | 4: #39, #566, #1226, #1229 |
| App-reports that duplicate an engineering issue | #1324→#1340, #1347→#1346, #1348→#1346+#1363 |
| Engineering duplicates | #1220 = #1328; #1279 ≈ #1301 (one cluster); #1302 ≈ #1306 (same class); #1331 ≈ #1337 (same class); #1335 ≈ #1349 (same class); #1355 ≈ #1356 (same class) |

Notes: #742 and #669 are met engine-side and wait only on the owner's sim read, so they are candidates to close. #1093 has had two failed rounds, so the two-round-cap review (RULINGS 2026-10-20b) is due. #1342 was ruled by the owner on 2026-10-26 (source order) but still carries `needs-owner`. #483 is out of scope by RULINGS 09c and its work sits in another repo, so it has no spec.

## Per-issue table

| # | Short title | Type | Sev | Diff | Local-only? | Dup / linked | Owner ruling first? |
|---|---|---|---|---|---|---|---|
| #39 | Code-sign the Windows build | feature | S3 | M | NO | — | YES: signing certificate / Trusted Signing account and its secret |
| #41 | Adopt a custom airport's own mesh into our patch | feature | S2 | L | YES | — | YES: FUTURE-FEATURES questions; Post 1.0 |
| #359 | HECA lot around shapeID 1308 hilly | bug | S2 | L | YES | #712 | no (two measured attempts failed; RULINGS 04s(4)) |
| #412 | Airport patch build < 300 s | performance | S3 | L | YES | #803 #1270 #1264 | no |
| #414 | OTHH corridor end test reads beyond shorter wall | bug | S2 | M | YES | — | YES (needs-owner label; re-ruling doc) |
| #473 | Patch simplification: fewest shapes/nodes | feature | S3 | L | YES | — | no (spec §58 on claude/emitspec) |
| #483 | MSFS → X-Plane converter (future) | feature | S3 | L | n/a | — | YES: RULINGS 09c out of scope; work lives in another repo |
| #507 | Step across pack-wall terrace exceeds wall height | bug | S2 | M | YES | — | no |
| #517 | SPJC taxiway smoother profile | feature | S3 | M | YES | — | no |
| #535 | Refine when a tagged in-airport tunnel is built | feature | S3 | M | YES | #522 | no (exploration) |
| #566 | Relay endpoint files reports for users without GitHub | feature | S3 | L | NO | #565 | YES: hosting, GitHub App credential, privacy note |
| #669 | KCLT departures ramp cliff | bug | S2 | M | YES | #1093 | no (engine met; sim read owed) |
| #684 | Roads inside a lot are the lot (OSM ribbons) | feature | S3 | L | YES | #683 | YES: gated on stage-1 insulation (owner 10-14) |
| #712 | HECA parking lot must weld to slab | bug | S2 | M | YES | #359 | no |
| #740 | Unused-code clean-up | feature | S3 | L | PARTIAL | #852 #857 | no (step 2 gate is cloud-able; waves need sweep) |
| #742 | KDEN service road treated as tunnel; shape 1048 cliff | bug | S2 | M | YES | #710 #748 | no (engine met; sim read owed) |
| #803 | HECA patch build 1,166 s | performance | S3 | L | YES | #412 #768 | no |
| #805 | KCLT end-around taxiway T | feature | S2 | M | YES | — | no (RULINGS 16d) |
| #807 | KCLT two tunnel ramps don't follow roads | bug | S2 | M | YES | — | no (north met; south remaining) |
| #810 | KATL bridge-edge objects witness the cut | feature | S2 | L | YES | #1138 #715 | no |
| #818 | Build pane redesign | feature | S3 | L | NO | #832 #820 #825 | no |
| #820 | Show cost before building | feature | S3 | M | NO | #832 #818 | no |
| #824 | Library view + cache cleanup | feature | S3 | L | NO | #832 | no |
| #825 | Per-step progress strip | feature | S3 | M | NO | #832 | no |
| #832 | Beta 3 usability pass (tracking) | tracking | S3 | — | n/a | #818 #820 #824 #825 | — |
| #847 | In-process BC1/BC3 encoder | performance | S3 | M | YES | #858 | no (owner sim read gates the byte change) |
| #850 | DSF encoder profile/vectorise | performance | S3 | M | YES | #858 #740 | no |
| #858 | Beta 3 build speed (tracking) | tracking | S3 | — | n/a | #847 #850 #1223 #1248 | — |
| #883 | KBOI 97 adjudicated grade rows | bug | S2 | M | YES | #877 #882 | no (answer 44 given) |
| #947 | Roads around airports bumpy / sharp drops | bug | S2 | M | YES | #944 #1254 #1358 | no |
| #953 | KTVL: X-Plane crashes on load | bug | S1 | M | YES | #950 | no |
| #1003 | HECA deep cuts by train terminal | bug | S2 | M | YES | #710 | no |
| #1028 | EDDF tunnels: mouth placement / width | feature | S2 | L | YES | #1011 | no |
| #1093 | KCLT ramp run-out off design rows | bug | S2 | M | YES | #669 | no (two failed rounds → two-round-cap review due) |
| #1138 | Pack bridge deck edges: full trench, shoulders at floor | bug | S2 | L | YES | #810 | YES: owner 10-21 rulings recorded as pending |
| #1146 | KLAX elevated rail seated as one group | bug | S2 | M | YES | #1288 #1141 | no |
| #1158 | Pavement must not cross pack retaining wall | bug | S2 | M | YES | #1160 #1197 | no (RULINGS 20al) |
| #1160 | Read pack's own draped pavement first | feature | S2 | L | YES | #1158 | no (RULINGS 20al) |
| #1197 | Retaining-wall classifier misfires | bug | S2 | M | YES | #1158 #1201 | no |
| #1201 | KSEA runway-end retaining walls | bug | S2 | M | YES | #1197 | no |
| #1207 | Investigate OSM fetch/cache strategy | performance | S3 | M | YES | #1329 | no |
| #1208 | Flat-airport handling: fill, not cut | feature | S2 | L | YES | #1340 | YES (needs-owner) |
| #1210 | KFHR USGSLPC 'tile declares no CRS' | bug | S3 | S | YES | — | no |
| #1218 | LFPG tunnels under taxiways; T1 bowl | bug | S2 | L | YES | #1280 #1302 | no |
| #1220 | FRANCE50CM WFS HTTP 400 → no-coverage (LFPG) | bug | S2 | S | NO | DUP of #1328 | no |
| #1223 | DDS cache misses: colour field not bit-exact | bug | S3 | S | NO | #858 #1015 | no |
| #1224 | Toolbar search field clips long text | bug | S3 | S | NO | — | no |
| #1226 | Per-tile build console logs + history | feature | S3 | M | NO | #1341 | YES: design posted, awaiting approval |
| #1229 | Leave an Ortho4XP folder's configs untouched | feature | S2 | M | NO | — | YES: go-ahead + RULINGS 18c amendment |
| #1236 | Machine-wide download coordination | performance | S3 | M | NO | #1327 #1235 | no |
| #1248 | Step reuse keys on engine version | performance | S3 | S | NO | #1321 | no |
| #1252 | Reseat sibling packs' OBJECT_MSL rows | feature | S2 | M | YES | #1246 | no |
| #1254 | Public roads follow terrain > road_max_grade | feature | S2 | L | YES | #947 | no (RULINGS 22h; consumer census first) |
| #1261 | Windows CI flake: worker liveness after close | bug | S3 | S | NO | #118 #140 #169 #194 | no |
| #1264 | One tile uses ~1–3 cores | performance | S3 | L | YES | #412 #1270 | no |
| #1270 | HiGHS surface solve on one core | performance | S3 | M | YES | #412 | no |
| #1279 | LFPG building floating (1.0.420) | bug | S2 | M | YES | #1301 | no |
| #1280 | LFPG unwanted tunnel ramp (taxiway on berm) | bug | S2 | M | YES | #1218 #1138 | no |
| #1281 | Patch view: copy coordinates / shape reference | feature | S3 | S | NO | #1314 #1317 | no |
| #1288 | KMCI garage ramp island not chained | bug | S2 | M | YES | #1146 | no |
| #1298 | Roofed pack tunnel objects not recognised | bug | S2 | L | YES | #1343 | no |
| #1300 | [airport_verify] KPIE ring_fold | app-report | S2 | M | YES | #1275 | no |
| #1301 | LFPG building floating (1.0.425) | bug | S2 | M | YES | same cluster as #1279 | no |
| #1302 | LFPG T2 lower level stops under roads | bug | S2 | M | YES | #1306 | no |
| #1305 | SPJC mesher-inserted vertices differ | bug | S3 | M | YES | #1296 | no |
| #1306 | KATL east terminal lower level | bug | S2 | M | YES | #1302 | no |
| #1314 | Map right-click: Insert shape / Copy coordinates | feature | S3 | M | NO | #1281 #1309 | no |
| #1315 | Map overzoom past provider max | feature | S3 | S | NO | — | no |
| #1316 | Pack outlines more visible + labels | feature | S3 | S | NO | #1281 | no |
| #1317 | Search accepts lat/lon formats | feature | S3 | S | NO | #1281 #1314 | no |
| #1318 | Patch editor: Slice | feature | S3 | M | NO | — | no (Q130–Q133 answered) |
| #1319 | Patch view: hatch below-grade shapes | feature | S3 | S | NO | — | no |
| #1320 | Patch view: hillshade + contours | feature | S3 | M | NO | #1309 | no (Q134 answered) |
| #1321 | Qt-built patches always rebuilt by Mac app (o4_cfg) | bug | S3 | S | NO | #1248 | no |
| #1322 | "Rebuild tile" disabled during a build | bug | S3 | S | NO | #1326 | no (owner ruled) |
| #1323 | Investigate incremental patch-edit apply | feature | S3 | L | NO | #412 #615 | YES after the spec (spec itself is cloud work) |
| #1324 | [airport_verify] YMML | app-report | S2 | — | YES | DUP of #1340 (in flight) | — |
| #1325 | Map: single-click drag pans; cursors | feature | S3 | S | NO | #1314 | no (owner ruled) |
| #1326 | Activity row: resume after stop does nothing | bug | S2 | M | NO | #1322 | no |
| #1327 | Approach-ring cells fetched serially from 0.5 m lidar | performance | S3 | M | PARTIAL | #1330 #1351 #1236 | YES for the rung change only (RULINGS 02f) |
| #1328 | FRANCE50CM WFS HTTP 400 → durable no-coverage | bug | S2 | S | NO | #1220 (dup) | no |
| #1329 | OSM warm-up writes before tile OSM dir exists | bug | S3 | S | NO | — | no |
| #1330 | 0.5 m insets 200–500 MB: trim footprint | performance | S3 | L | YES | #1327 | YES (needs-owner) |
| #1331 | LGAV taxiway sunk ~6 m in tunnel_ramp pit | bug | S2 | M | YES | #1337 | no |
| #1332 | GLCA rwy 36: no standard RSA | bug | S2 | M | YES | — | maybe (what witnesses "no RSA") |
| #1333 | LFLL skybridge group / rail cut | feature | S2 | L | YES | — | no |
| #1334 | Build box doesn't adopt detected imagery | bug | S3 | S | NO | #1339 #1345 | no |
| #1335 | [airport_geometry] KOUN TopologyException | app-report | S2 | M | YES | #1349 (same class), #877 | no |
| #1336 | Small ponds render as water-textured hole | bug | S2 | M | YES | — | no |
| #1337 | NZWN phantom tunnel ramps | bug | S2 | M | YES | #1331 | no |
| #1338 | NZWN car parks as apron; garage sunk | bug | S2 | M | YES | — | no |
| #1339 | NZ imagery: add LINZ Basemaps | feature | S2 | S | NO | #1345 #1334 | minor: how the API key is supplied (reuse existing API-key credential flow) |
| #1340 | YMML in a 0 m pit (AUSTRALIA5M zeros) | bug | S1 | M | YES | #1324 | IN FLIGHT — excluded |
| #1341 | Activity list retention/order/gold status | feature | S3 | M | NO | #1226 | no |
| #1342 | VNLK runway flat: placeholder CIFP | bug | S2 | L | YES | #1358 | ruled 10-26 (source order); label still needs-owner |
| #1343 | KBUF tunnel mouth objects | bug | S2 | M | YES | #1298 | no |
| #1344 | KBUF terminal floating | bug | S2 | M | YES | — | no |
| #1345 | Map vs Build imagery menus differ | bug | S3 | M | NO | #1339 #1334 | no (owner ruled 10-25) |
| #1346 | PANC verify fails: rwy profile pinned at tile edge | bug | S1 | M | YES | #1347 #1348 | IN FLIGHT (owner ruling) — excluded |
| #1347 | [airport_verify] PANC +61-151 | app-report | S2 | — | YES | DUP of #1346 | — |
| #1348 | [airport_verify] PAAQ, PANC +61-150 | app-report | S2 | — | YES | DUP of #1346 + #1363 | — |
| #1349 | [airport_geometry] KSEE TopologyException | app-report | S2 | M | YES | #1335 (same class) | no |
| #1350 | Badge tiles with customized settings | feature | S3 | M | NO | #1229 | no |
| #1351 | Slow-step alert (> 5 min) | feature | S3 | L | NO | #1327 #1330 | no |
| #1352 | Airports outside inset selection refuse to patch | bug | S1 | M | YES | PR #1368 | IN FLIGHT — excluded |
| #1353 | Unnamed aerodromes skipped: give every airport an ID | feature | S2 | M | NO | PR #1368 | IN FLIGHT — excluded |
| #1354 | KWYS stray coastline floods tile | bug | S1 | M | YES | PR #1368 | IN FLIGHT — excluded |
| #1355 | [airport_failed] OR01 no reference point | app-report | S2 | S | YES | #1356 (same class) | no |
| #1356 | [airport_failed] ID31 no reference point | app-report | S2 | S | YES | #1355 (same class) | no |
| #1357 | Patch editor: Set elevation on shapes | feature | S3 | S | NO | #1314 #1322 | no |
| #1358 | KDIJ rwy 04 pinned 5 m above lidar | bug | S2 | M | YES | #1342 #1359 #947 | no |
| #1359 | Feasibility: cut/fill edges from ortho + lidar | feature | S3 | L | YES | #1358 #1298 #1343 | YES (needs-owner) |
| #1360 | Upgrade XP11 flat .for forests to XP12 3D | feature | S3 | M | YES | — | maybe (rewrite-a-pack consent model) |
| #1361 | [airport_failed] CYYC MultiPolygon.exterior | app-report | S2 | S | YES | — | no |
| #1362 | PAKT pack ships ground as objects + HD mesh | bug | S2 | L | YES | #41 | likely (pack-supplied ground rule) |
| #1363 | PAAQ runway_transverse with empty hard set | bug | S2 | M | YES | #1348 | no |

Local-only YES means the work needs the Mac corpus (`/Users/noah/XPTerrainBuilderData`), a local airport/tile build, or a sim read to verify. PARTIAL (#740, #1327) means the spec covers only the cloud-able part; the rest stays local.

# Cloud specs (NO rows)

Every spec is self-contained. Paths are from the repo root and were checked with grep on
`claude/batch-y-beta5-b1` at c67fd2a95 (2026-10-26). Line numbers drift, so find each symbol by name.
"PY GATES" in a spec means: from `Ortho4XP/`, run
`python -m pytest tests/test_windows_text_io.py tests/test_patch_env_classification.py tests/test_auto_patch_freshness.py tests/test_tile_failures.py tests/test_console_encoding.py tests/test_v1_retired.py tests/test_step_code_closure.py tests/test_patch_code_closure.py`,
then from the repo root `python tools/ratchets.py` (the identical-duplicate count may not rise). A NEW module that a build step imports must be registered in
`Ortho4XP/src/O4_Step_Code.py` `_SHARED` / `_BEYOND_SHARED` and, when auto-patch imports it, in `Ortho4XP/src/auto_patch/provenance_code.py` `PATCH_CODE_MODULES`.
"UI GATES" means PY GATES plus `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_qt_layout_parity.py` and the PR's macOS CI job (`swift build`, `swift test`, `.github/workflows/ci.yml`).
**Two UIs, one layout (CLAUDE.md, #1244):** a change to the Mac app's toolbar, build box, Settings, map or patch editor lands in the Qt window (`Ortho4XP/src/O4_Qt_*.py`) in the SAME PR,
or records an owner-ruled exception in the manifest of `Ortho4XP/tests/test_qt_layout_parity.py`. **Wire protocol:** an event class in `Ortho4XP/src/o4_engine/events.py` is its JSONL name and
`Sources/SceneryKit/OrthoEngineClient.swift` matches it as a string, so both sides change in one PR. The PR body reports net lines added/removed and new public symbols, and says `Refs #N` (the master writes `Fixes`).

## #1223
DDS cache misses on the first rebuild because the persisted colour field is lossy.
- Cause, verified: `OffsetField.to_json` (`Ortho4XP/src/O4_Color_Harmonization.py`, ~l.267) writes `numpy.round(self.values, 3)`, and `from_json` reads float32. A freshly solved field is unrounded, so T1 (solved) and T2 (reused from `color_field.json`, `O4_Imagery_Utils.read_color_field`) apply different offsets.
- Fix (choose one, say which in the PR): (a) write the values losslessly (float32 values as `float(v)` reprs, which round-trip exactly) and bump `COLOR_FIELD_VERSION` in `O4_Imagery_Utils.py` so old sidecars are re-solved; or (b) quantise the solved field through the same to_json/from_json path before it is first applied, so solved and reused are identical by construction.
- Do not change the field solve itself or `apply_color_field`.
- Tests (extend `Ortho4XP/tests/test_color_harmonization.py`): a synthetic `OffsetField` with values like 0.12345678 survives `from_json(to_json(f))` bit-for-bit (`numpy.array_equal`); and `apply_color_field` gives byte-identical output for the solved field and the round-tripped one on a small synthetic PIL image.
- Gates: PY GATES. Closing check (master, local): a cold tile build, clear `textures/`, rebuild, and the DDS cache hits 182/182.

## #1248
Step reuse must not key on the engine version.
- `Ortho4XP/src/O4_Step_Reuse.py` `_code_identity(step)` returns `{"engine": provenance.engine_version(), "code": ..., "auto_patch_cfg": ...}`. Drop `"engine"`: the per-step `code` digest (`O4_Step_Code.step_digest`) already covers code changes.
- Keep the reason text table (`"engine": "the engine version changed"`, ~l.418) so a stamp written by an older engine still reads, but an `engine`-only difference must no longer make a step stale. A stamp whose stored inputs still hold `engine` is compared without that key (migration, no forced rebuild).
- Audit the airport-level reuse for the same problem and list what you find in the PR: `Ortho4XP/src/O4_Airport_Elevation_Insets.py` (`recorded_engine_version(...) != _engine_version()`, ~l.845) and the per-airport `o4_cfg` path in `Ortho4XP/src/auto_patch/driver.py`. Change only the step key in this PR; report the others as findings.
- Tests (`Ortho4XP/tests/test_step_reuse.py`): monkeypatch `provenance.engine_version` to two values with code, inputs and cfg unchanged, and the step is reused. Change the step's code digest and it is stale, with the existing reason. An old stamp that still carries `engine` is reused.
- Gates: PY GATES (`test_step_code_closure`, `test_auto_patch_freshness` matter most here).

## #1321
Frozen and source engines must compute the same `o4_cfg` digest.
- Cause, verified: `Ortho4XP/src/auto_patch/provenance.py` `config_digest()` calls `introspect_config_gates()`, which parses the `auto_patch/config.py` SOURCE (`_config_source_path`, `_gate_defaults`). The frozen bundle ships no source, so it returns `{}` and records `introspect:unavailable`.
- Fix: generate the gate table as data at freeze time, e.g. `auto_patch/config_gates.json` written by a small function in `provenance.py` and called from `scripts/make_engine.sh` before PyInstaller. Add it to the `datas` of BOTH `Ortho4XP/Ortho4XP.spec` and `Ortho4XP/Ortho4XP_Qt.spec`. `introspect_config_gates()` reads the source when it can, else the JSON. It returns `{}` (and `introspect:unavailable` stays) only when both fail.
- The JSON must be regenerated from source at build time, never hand-edited. A twin fails when the committed or generated JSON differs from a fresh source parse.
- Tests (new `Ortho4XP/tests/test_config_digest_frozen_parity.py`, or extend `test_patch_provenance.py`): `config_digest()` with the source path equals `config_digest()` with `_config_source_path` monkeypatched to None and the JSON present. With neither present, the digest still contains `introspect:unavailable`.
- Gates: PY GATES. Closing check (master, local): build a tile in the Qt window, then in the Mac app; the second build reuses every unchanged airport.

## #1329
OSM warm-up writes into a tile OSM folder that does not exist yet.
- Verified: `Ortho4XP/src/O4_OSM_Utils.py` `OSM_layer.write_to_file` opens the file and prints `Could not open … for writing.` on failure. The warmer, `o4_engine/parallel.py` `_warm_queued_tiles`, calls `OSM.OSM_queries_to_OSM_layer(..., cached_suffix=...)` before the build has run `os.makedirs(FNAMES.osm_dir(...))` (`O4_Vector_Map.py`, ~l.1280).
- Fix: in `write_to_file`, `os.makedirs(os.path.dirname(filename), exist_ok=True)` when the dirname is non-empty, before opening. Keep the failure message for real failures. Alternatively the warmer creates `FNAMES.osm_dir(lat, lon)` first; the write_to_file guard is preferred because it covers every caller.
- Tests: a tmp_path test calls `write_to_file` into a non-existent nested folder (plain and `.bz2`) and the file exists. A warmer-level test stubs the Overpass query and asserts that the layer file lands and no "Could not open" line is printed (capsys).
- `test_windows_text_io.py` gates `open()` calls: keep `encoding="utf-8", newline="\n"`.
- Gates: PY GATES.

## #1261
Windows CI flake in `Ortho4XP/tests/test_qt_command_process.py`.
- `_alive(pid)` (~l.59) is sampled once, the instant `close()` returns (`test_the_worker_is_gone_after_close`, ~l.117; the same assert at ~l.180). On Windows, `os.kill(pid, 0)` is not a probe: it calls TerminateProcess.
- Fix, test-only: add `_gone_within(pids, timeout_s=5.0)` that polls `_alive` with a bounded deadline (time.monotonic, sleep 0.05) and use it at both asserts. On Windows, `_alive` uses `psutil.pid_exists` plus `psutil.Process(pid).status() != STATUS_ZOMBIE` when psutil imports, else ctypes `OpenProcess` + `GetExitCodeProcess` (STILL_ACTIVE = 259). POSIX keeps `os.kill(pid, 0)` with a waitpid reap.
- No change to `o4_engine/command_process.py`. If you find `close()` returning before the worker is reaped, report it; don't fix it here.
- Acceptance: the test passes 50 times in a row (a loop bounded to 50 runs); `windows-latest` CI is green on the PR.
- Gates: PY GATES (the Qt tests do not run under xdist).

## #1224
The toolbar search field clips long text instead of scrolling.
- `Sources/XPTerrainBuilder/MapMainView.swift` `struct ToolbarSearchField: NSViewRepresentable` (~l.479); `makeNSView` builds `NSSearchField()` (~l.488).
- Fix in `makeNSView`: `field.cell?.isScrollable = true; field.cell?.wraps = false; field.usesSingleLineMode = true; field.lineBreakMode = .byClipping`. Leave `updateNSView`'s stringValue guard as it is unless a test shows it resets the scroll position.
- Qt: `O4_Qt_GUI.py` `self.search_edit = QLineEdit()` already scrolls; no Qt change is needed. Say so in the PR so the parity rule is visibly satisfied.
- Test: a SwiftPM unit test in `Tests/XPTerrainBuilderTests` that calls the representable's NSView factory (factor a static `makeField()` if needed) and asserts `cell.isScrollable == true` and `cell.wraps == false`.
- Gates: UI GATES. Owner verifies typing on device.

## #1322
"Rebuild tile" in the patch box should queue during a build.
- Mac: `Sources/XPTerrainBuilder/PatchSaveBar.swift` has `Button("Rebuild tile") { model.rebuildTile() }.disabled(model.build?.isBuilding ?? false)`. Remove the disable. `rebuildTile()` (`Sources/XPTerrainBuilder/PatchEditActions.swift` ~l.196) must enqueue through `BuildModel.startBuild(batches:)` → the protocol `enqueue_build` path with the tile's recorded provider and ZL. When the tile is already queued or building (`selectedInRun`), show a note ("already in this run") instead of queuing twice.
- Qt: `Ortho4XP/src/O4_Qt_Patch_Panel.py` `self.rebuild_button.setEnabled(not c.is_building())` (~l.436). Same change; `O4_Qt_Patch_Controller.rebuild_tile` enqueues through the window's existing enqueue path in `O4_Qt_GUI.py` (~l.4306).
- Tests: a Qt offscreen test with the panel's controller reporting `is_building() == True` and the button enabled; clicking it calls the enqueue path once, and a second click on an already-queued tile does not. A Swift unit test on the model's rebuild decision (queued / already-in-run / start).
- Coordinate with #1326 (same enqueue path and row-reset rule).
- Gates: UI GATES.

## #1326
Resume after stopping a tile does nothing while other tiles build (three faults in the issue comments).
- Mac `Sources/XPTerrainBuilder/BuildModel.swift`: `cancelTile` (~l.1871), `resumeTile` (~l.1889; parks the tile in client-side `resumeQueue` when `isBuilding`), `startResumeQueue` (~l.1905), `selectedInRun` (~l.1145; counts `.queued` as in-run), `mayOverwriteStopped` / `resolving(_:over:)` (~l.1989–2000; drops a stopped row's non-terminal events).
- Qt `Ortho4XP/src/O4_Qt_GUI.py`: `_cancel_tile_clicked` (~l.3874), `_resume_tile_clicked` (~l.3901; `enqueue_resume` into `_resume_queue`), `_start_resume_queue` (~l.3948).
- Fix, both apps: (1) Resume enqueues into the RUNNING build via the enqueue path with the tile's run settings. If the engine has not acknowledged the cancel yet, wait for its `TileState` stopped event (or let the engine reject the duplicate and re-queue it). Never run two copies of one tile. (2) Every enqueue (Build, Queue, Resume) resets the row to queued and its clock to nil. (3) Stale events from the stopped attempt are told apart by an attempt/run id on the events or the enqueue acknowledgement, not by the row's displayed state. (4) A stopped or queued row runs no clock. (5) Client-held-only tiles do not count as in-run.
- An attempt id added to a `TileState` / `StepProgress` event is a wire change: `events.py` and `OrthoEngineClient.swift` change in this PR.
- Tests: Swift unit tests on `resolving` with an attempt id (old attempt dropped, new attempt shown) and on resume-while-building (enqueue called, no `resumeQueue`). A Qt offscreen test of the same sequence with a stub engine. An engine test showing that a duplicate enqueue of a building tile is refused or deferred.
- Gates: UI GATES. Closing check (owner): stop one tile of a two-tile run, resume it, and it builds while the other is still running.

## #1334
Selecting a built tile with no saved cfg does not adopt its detected imagery.
- Mac: `BuildModel.adoptActiveTileConfig` (`Sources/XPTerrainBuilder/BuildModel.swift` ~l.243) adopts `built[coord].provider` only `if !info.provider.isEmpty` (that value comes from the cfg). Detection exists: `Sources/SceneryKit/PackImagery.swift` `fromFileNames` (dominant provider and ZL from `{y}_{x}_{provider}{zl}.dds|.ter`), with `fromConfig` as the fallback.
- Fix: one resolver, `cfg if it names provider/ZL, else detected`, carrying its source (`.config` / `.detected`). Adoption, the provider-mismatch warning and `rebuildTile()` all read it.
- Qt: `O4_Qt_GUI.py` `_sync_build_controls_to_selection` (~l.2458) gets the same rule. Preferably the engine owns detection (a small pure function over texture names, unit-tested in Python) and both apps call it. If you keep the Swift `PackImagery`, add a Python twin with shared fixture names so the two can't drift.
- When #1345's liveness data exists, an offline detected source is not adopted. Leave a TODO naming #1345 if that data has not landed yet.
- Tests: Swift `PackImagery`/resolver tests (cfg wins; no cfg → detected; mixed names → dominant). A Qt offscreen test: a fake built tile with only `_BI16.dds` names selects BI/16.
- Gates: UI GATES.

## #1328
(Also covers #1220, a duplicate.) FRANCE50CM WFS replies with HTTP 400 and it is recorded as durable no-coverage.
- Verified: `Ortho4XP/src/elevation_access/discovery.py`: only `discovery_status_is_transient(status)` (~l.50) codes raise `TransientFetchError`. Any other non-2xx prints `- durable, recorded as no-coverage.` and returns None (~l.190–199).
- Fix: (1) A 4xx other than 404 (and 410) on a tile-index/discovery query is a named PROVIDER error (a new `ProviderQueryError`, or a reuse of the transient class), logged loudly with the URL minus credentials, and never recorded as no-coverage. 404/410 and an empty valid answer stay durable. (2) Records already written by a 400 are cleared: store the status with each no-coverage record, and a record without one, or with a 4xx≠404 status, is not durable on read. Find the writer by grepping the no-coverage record in `elevation_access/`. (3) If the cloud environment can reach `data.geopf.fr`, reproduce the `IGNF_MNT-LIDAR-HD:dalle` query in the provider definition (`Ortho4XP/Providers/Elevation/FRANCE50CM.elv` or its strategy) and correct it. Otherwise leave the query alone and say so.
- Tests: a mocked `response.status_code` of 400/403 raises or returns the provider error, not None. 404 returns None (durable). A stored 400 record reads as not durable. No network in tests (the harness refuses it).
- Gates: PY GATES. Closing check (master): a cold LFSB inset fetch uses FRANCE50CM, or names the query error.

## #1236
Machine-wide download coordination across tile processes.
- Today: `Ortho4XP/src/O4_File_Lock.py` dedupes insets and OSM extracts. Base DEM cells (`O4_DEM_Utils.py`) and orthophoto tiles (`O4_Imagery_Fetch.py`, per-process AIMD window per provider) have no cross-process lock. The session resource manager is `O4_Machine_Slots.py` (`ensure_session`, `take`, `try_take`, file-lock based).
- Fix: (1) A per-server request budget shared by the build session: extend `O4_Machine_Slots` with a named-class budget keyed by host (e.g. `take_class("net:" + host, n)`), so the imagery fetcher and the inset/DEM fetch acquire from one machine-wide pool. Default per-host limits come from the existing per-process values. (2) A shared in-flight download lock per target file for base DEM cells and imagery tiles, using `O4_File_Lock`. The second process waits, then reuses the finished file.
- Bounded waits only (the guard refuses unbounded loops); a crashed holder's lock is reaped the way `O4_Machine_Slots` reaps.
- Tests: two `multiprocessing` workers on tmp_path, with the network stubbed by a local function that counts calls: the same DEM cell is fetched once. With a host budget of 2, 4 workers never exceed 2 concurrent stubs. Lock reaping works after a killed holder.
- New module? Register it in `O4_Step_Code._SHARED` if a build step imports it.
- Gates: PY GATES.

## #1327
Partial: parallel ring cells and progress lines only. The rung choice is RULINGS 2026-10-02f and stays an owner call.
- `Ortho4XP/src/O4_Elevation_Level.py` `ensure_approach_rings(tile, dico_airports, refresh=False)` (~l.2287) fetches cells serially; `_approach_ring_cell` (~l.2018) does one cell. `_approach_ring_candidates` (~l.1656) ranks the candidates; do NOT change it.
- Fix: (1) Fetch cells in a bounded pool (ThreadPoolExecutor, default 4, the same cap the inset fetch uses; an env/cfg knob is optional). Results, stamps (`write_approach_ring_stamp`) and outcome ordering stay deterministic: sort by cell stem before writing. (2) Print one progress line every N cells (`approach rings: 12/40 cells`) and emit a `StepProgress` update if the step already has one. (3) Check that the warp uses overviews (`-ovr AUTO`, not forced full resolution) and report the finding; change it only if byte-identical.
- Tests: stub `_approach_ring_cell` to sleep and record concurrency: max in-flight ≤ cap, every cell present, and the stamp is identical to the serial run's. Progress lines appear (capsys).
- If #1236 lands first, take ring-cell fetches from its per-host budget.
- Gates: PY GATES (`test_step_code_closure`: the ring step's code digest changes, which is expected). Closing check (master): +55-004 ring wall time before/after, cells byte-identical.

## #1281
Patch view: copy coordinates, plus a "Copy shape reference".
- Mac: `Sources/XPTerrainBuilder/PatchNodeInspector.swift` already has `static func latLon(lat:lon:)` (`%.9f`). Make the coordinate text a borderless button that copies it (NSPasteboard, as `RunIssuesSheet.swift` does) and shows "Copied" for ~1.5 s. Add a right-click node menu, "Copy coordinates" (`PatchEditGestures.swift` / `PatchEditActions.swift`), and on a selected shape, "Copy shape reference" (`PatchShapeInspector.swift`).
- Shape reference text block: tile, ICAO, patch file name, engine version, way id, ref/role/name tags, centroid `lat, lon`, vertex count, area m², min/max elevation, first 5 vertices. Put one pure formatter in SceneryKit, with a Python twin used by Qt, and identical output for a fixture.
- Qt: `O4_Qt_Patch_Panel.py` / `O4_Qt_Patch_Gestures.py` / `O4_Qt_Patch_ShapePick.py`: the same menu items and clickable coordinates (QApplication.clipboard()).
- Tests: a formatter twin (Swift test plus Python test on the same fixture produce the same string). A Qt offscreen test: right-click a node and the clipboard holds `lat, lon`.
- Gates: UI GATES.

## #1314
Map right-click: "Insert shape" and "Copy coordinates" (both apps).
- Copy coordinates: the `lat, lon` at the cursor with 9 decimals; reuse `PatchNodeInspector.latLon` (Mac) and its Qt twin from #1281 (if #1281 has not landed, add the formatter here).
- Insert shape: a square of side 20 m (state it in the PR; a constant) centred at the cursor. Each node's elevation comes from the `cursor_elevation` engine command (`Ortho4XP/src/o4_engine/elevation_commands.py` `cursor_elevation`, registered in `jsonl.py`; client in `OrthoEngineClient.swift`). The shape is added to the tile's open/existing patch through the patch editor's add-shape path, or a new `<ICAO>_edited.patch.osm` when there is none. Find the save path in `PatchEditModel.swift` / `O4_Qt_Patch_Model.py`. Pick the airport whose boundary contains the point; refuse with a message when none does.
- Menus: Mac `TileContextMenu.swift` / the map canvas context menu; Qt `O4_Qt_Tile_Menu.py` / `O4_Qt_Map.py`.
- Tests: pure geometry (a square ring of 4 nodes, closed, CCW, side 20 m ± 1 cm at several latitudes) in both languages. A Qt offscreen test with a stubbed engine returning elevations: Insert adds one way with 4 nodes carrying those elevations and marks the patch dirty.
- Gates: UI GATES.

## #1315
Map overzoom past the provider's maximum detail.
- The provider ceiling is known: Mac `Sources/XPTerrainBuilder/ImageryModel.swift` `maxZL` (default 21 when `max_zl` is absent); Qt `O4_Qt_Map.py` `self._provider_max_zl`.
- Fix: the map zoom limit becomes independent of the provider (allow, e.g., ZL 23). Tiles above the provider's `maxZL` are drawn by scaling up the deepest available ancestor tile (crop the 2^(z−max) sub-square and scale). Never request a URL above `maxZL`. The zoom badge says "overzoom ×N".
- Tests: a pure function `ancestor(z, x, y, maxZ) -> (z', x', y', subrect)` in Swift and Python, with the same fixture cases. A Qt offscreen test: at ZL 22 with maxZL 19, the fetch stub sees only ZL 19 requests.
- Gates: UI GATES.

## #1316
Scenery-pack outlines: more visible, a translucent fill and labels.
- Mac `Sources/XPTerrainBuilder/PatchPackOutlines.swift` `draw(_:camera:...)`; Qt `Ortho4XP/src/O4_Qt_Pack_Outlines.py` (`_path`, footprints). Change the pack outlines ONLY: tile overlays stay stroke-only (#1256's no-green-tint fix).
- Darker colour, 1.5–2 pt solid or long-dash stroke, fill at ~12 % alpha. Labels (object file name, or pavement role/ref) appear at ZL ≥ 18 only, with collision skipping, plus a hover tooltip / click hit-test that reports the same text.
- Put the styling constants in one place per app, with the same values (a parity test reads both).
- Tests: a parity test asserting the Swift and Qt stroke/fill constants match (parse the Swift literal as `test_qt_layout_parity.py` does). A Qt offscreen render test: a filled pixel inside a footprint has non-zero alpha; a tile-overlay interior pixel is unchanged.
- Gates: UI GATES.

## #1317
Search accepts lat/lon in common formats; Return centres at ZL19 and draws a reticle.
- Mac: `Sources/XPTerrainBuilder/MapMainView.swift`, `searchHandledElsewhere` / submit path (`TileMath.parse` for tile keys). Qt: `O4_Qt_GUI.py` `_search_accept_first` / `_update_search_popup` (~l.1780–1866).
- Add ONE parser per language, the same cases: decimal `lat, lon` with or without a comma; signed; N/S/E/W prefix or suffix; DMS (`49°00'45.6"N 2°33'29.4"E`, also `d m s` with spaces and ASCII `'`/`"`); degrees + decimal minutes. Reject out-of-range values. A tile key (`+49+002`) keeps working and wins when the text is a tile key.
- Return: centre at ZL 19 and draw a reticle overlay that stays until the next search or Esc/clear.
- Tests: a shared fixture file (e.g. `Ortho4XP/tests/fixtures/latlon_search_cases.json`) read by a Python test and a Swift test (copy it into the Swift test bundle, or embed it with a twin check that the two copies are equal).
- Gates: UI GATES.

## #1318
Patch editor "Slice" (owner Q130–Q133 answered).
- Rules: only when two NON-adjacent nodes of the same shape are selected. The result is two shapes. Each selected node becomes two nodes 0.5 m apart, perpendicular to the cut line, and each copy keeps the original node's height. Refuse when the cut line leaves the shape. When it crosses a hole and re-enters the same shape, slice the hole too, adding nodes at the cut points with interpolated height. Both halves keep the original tags and role; one keeps the original id.
- Implement the geometry ONCE in the engine as a pure function over a polygon-with-holes (a new module under `Ortho4XP/src/` with no auto_patch import, so no PATCH_CODE_MODULES entry; register it in `O4_Step_Code` only if a build step imports it), exposed to both apps through a JSONL command (wire change: `events.py` / `jsonl.py` ↔ `OrthoEngineClient.swift`). Or implement it in each app with a shared fixture twin. State the choice.
- UI: Mac `PatchEditActions.swift` / `PatchEditGestures.swift` context menu; Qt `O4_Qt_Patch_Gestures.py` / `O4_Qt_Patch_Controller.py`. One undoable edit.
- Tests: shapely-based unit tests (a convex square; a concave L; a shape with a hole crossed; a refused cut outside; the ids/tags rule; 0.5 m ± 1 mm gap). An undo test in Qt offscreen.
- Gates: UI GATES.

## #1319
Patch view: hatch the fill of below-grade shapes.
- Neither app has a striping style today (grep finds none in `PatchOverlay.swift` / `O4_Qt_Patch_Overlay.py`), so add one. "Below grade" is by role: `tunnel_ramp`, `tunnel_trench`, the wall-corridor ramp and the lower-level/basin roles. Take the exact role strings from the engine's role table (grep `tunnel_ramp` in `Ortho4XP/src/auto_patch_v2`) and keep them in one list per app with a parity test.
- Draw 45° alternating bands (e.g. 4 px band/gap in the role's colour at two alphas) clipped to the shape, beneath the stroke. Show it in the legend.
- Mac `Sources/XPTerrainBuilder/PatchOverlay.swift` (fills by role); Qt `Ortho4XP/src/O4_Qt_Patch_Overlay.py` (QBrush pattern or a clipped path).
- Tests: a role-list parity test (Swift literal vs Python list). A Qt offscreen render: two pixels a half-band apart inside a tunnel_ramp shape differ in alpha; an apron shape's do not.
- Gates: UI GATES.

## #1320
Patch view: hillshade plus 1 m contours (owner Q134 = hillshade + contours).
- Engine: a new JSONL command `terrain_relief(tile, bbox, px_w, px_h, contour_m)` returning a PNG (base64) plus a legend (min/max elevation, contour step). Source: the built mesh via the sampler used by `cursor_elevation` (`Ortho4XP/src/o4_engine/elevation_commands.py` `_mesh_sampler`, `_dem_source`), else the DEM. Rasterise with numpy: hillshade (azimuth 315°, altitude 45°) and contour lines every `contour_m` (1 m by default, 0.5 m when the pixel size is < 0.25 m). Cache per (tile, bbox, size) in memory, bounded.
- Wire: a request/response pair in `events.py` / `jsonl.py` and `OrthoEngineClient.swift` in this PR.
- UI: a toggle and an opacity slider in the patch view of both apps (Mac `PatchModeToolbar.swift` / `PatchOverlay.swift`; Qt `O4_Qt_Patch_Toolbar.py` / `O4_Qt_Patch_Overlay.py`). Add them to the parity manifest if they're toolbar items.
- Tests: an engine unit test on a synthetic plane plus a hill (a sampler stub): PNG size, the contour count over a known relief, and hillshade monotone on a slope. A JSONL round-trip test. A Qt offscreen toggle test with a stubbed engine.
- Gates: UI GATES (also `test_console_encoding`: no non-ASCII prints).

## #1325
Map: single-click drag pans in both apps; hand/pointer cursors (owner ruling 2026-10-25).
- Mac: `Sources/XPTerrainBuilder/MapCanvasView.swift` `pan(size:)` (~l.534) and the patch editor `.pan` in `PatchEditGestures.swift` already pan on a left drag. Add cursors: `NSCursor.openHand` over open map, `.closedHand` while panning, `.pointingHand` over hit-testable items (nodes, edges, handles, tiles) on hover (an NSTrackingArea or `.onContinuousHover` with the existing hit test).
- Qt: `Ortho4XP/src/O4_Qt_Map.py` `mousePressEvent` (~l.700): a left drag on open map pans; REMOVE the right-button drag pan (middle may stay). Hover sets `Qt.OpenHandCursor` / `Qt.PointingHandCursor` using `O4_Qt_Patch_Gestures.py` hit tests. A right click without a drag always opens the context menu.
- Unchanged: Shift-drag box-select, scroll/pinch zoom, node/edge drag.
- Update `MapHintOverlay.swift` / `O4_Qt_Map_Hint.py` text and the gesture tables in both gesture modules' docstrings.
- Tests: Qt offscreen QTest mouse sequences (a left drag moves the centre; a right press/release opens the menu and does not pan; hover over a node gives PointingHandCursor). A Swift unit test on the gesture classification function (factor it out if needed).
- Gates: UI GATES.

## #1341
Activity list: keep finished rows until quit, live rows on top, finished rows dimmed, gold "built with errors" status that reopens the warning dialog.
- Mac: `Sources/XPTerrainBuilder/BuildPane.swift`, `TileProgressRowLines.swift`, and the row store in `BuildModel.swift`; the end-of-run warning is `RunIssuesSheet.swift`. Qt: `O4_Qt_GUI.py` `_add_progress_rows` (~l.3614), `_render_row_state` (~l.3805), and `O4_Qt_Tile_Failures.py` for the dialog.
- Rules: finished rows (done / errors / failed / stopped) are never cleared by a run end or a new run. Order: live rows on top with the newest queued first, then finished rows in finish order (the first finished directly under the live block). A finished row's title is secondary/grey and its status keeps its colour: warnings gold, failures red. Clicking a warning status reopens that tile's dialog from data kept on the row (`o4_unpatched_airports.json` / the run summary), including "Report this problem". A click elsewhere keeps select-and-zoom (#816).
- Put the ordering in one pure function per app, with a shared fixture twin.
- Tests: ordering-function tests (Swift + Python, same fixture). A Qt offscreen test: after a 3-tile run with one errors tile, 3 rows remain, the errors status is clickable, and it opens the dialog with a Report button. A newly queued tile appears at index 0.
- Gates: UI GATES (also `test_tile_failures.py`, `test_qt_tile_failures.py`).

## #1345
One imagery source list for both menus, wider preview support, and a background liveness check at launch (owner ruling 2026-10-25T22:11Z).
- Today: the Build box reads `OrthoEngine.providers()` (`Sources/SceneryKit/OrthoEngine.swift` ~l.156; .comb plus .lay without `in_GUI=False`). The map toolbar reads `ImageryModel.availableProviders` (`Sources/XPTerrainBuilder/ImageryModel.swift` ~l.183; webmercator with url_template only). Qt uses `O4_Qt_GUI.map_preview_codes()` (~l.644).
- Engine: a JSONL command `imagery_sources` → one list: code, region, display name, combined members, max_zl, previewable, and the reason when it isn't. Grouped by region, combined sources first. Also `imagery_source_status`: one sample tile per source at a covered point, bounded concurrency (4), a 5 s timeout, run in the background at app launch; results stream back as events, and unknown counts as enabled. Wire change on both sides in this PR.
- Apps: both menus come from the engine list in the same order. Offline sources are disabled and shown as `<name> (offline)` with the reason as a tooltip. Non-previewable sources show greyed in the map menu with their reason. Preview URLs for WMTS/TMS/WMS (EPSG:3857) come from the engine (a `preview_tile_url` command) instead of Swift/Qt URL building.
- Tests: an engine test over the vendored `Ortho4XP/Providers` tree (count, ordering, previewable flags for PDOK/FIN/QC/PT/AL). A status test with the HTTP layer stubbed (no network). A parity test: Swift and Qt build their menus from the same fixture list.
- Gates: UI GATES.

## #1350
Badge tiles that have customized settings; info-pane summary and an "Edit settings…" button.
- Engine owns the diff: a JSONL command `tile_customizations(lat, lon)` → `[{key, tile_value, default_value, affects_output}]`, comparing the tile cfg to the global/default values from `Ortho4XP/src/O4_Settings_Model.py` / `O4_Cfg_Vars.py`. Imagery source and ZL are excluded (the Build box sets them per build), and legacy keys are handled as the settings model does. `affects_output` is true for auto-patch/elevation/mask keys (list them from `O4_Cfg_Vars` scope data, not by hand where possible).
- Mac: a badge in the map tile overlay (`MapCanvasView.swift` / `MapCanvasLabels.swift`) and a "Custom settings" section with an "Edit settings…" button opening `SettingsView` scoped to the tile (BuildPane tile inspector). Plain names via `O4Glossary`.
- Qt: the same in `O4_Qt_Map.py` tile painting and the `O4_Qt_GUI.py` info pane; the button opens `O4_Qt_Settings` scoped to the tile.
- Tests: engine tests with a tmp data folder (no overrides → []; two overrides → two rows with defaults; provider/ZL ignored). A wire round-trip. A Qt offscreen test: the badge is drawn and clearing the overrides removes it.
- Gates: UI GATES.

## #1351
Slow-step alert after 5 minutes: what, why, ETA, and the options.
- Engine: (1) Long steps emit progress with done/total units and a rate. Extend `StepProgress` in `Ortho4XP/src/o4_engine/events.py` with optional `units_done`, `units_total`, `unit`, `reason_code`. The ring-cell loop (`O4_Elevation_Level.ensure_approach_rings`) and the inset fetch emit it. (2) The engine owns the threshold (default 300 s; a setting can raise it or turn it off) and emits a `SlowStep` event with `step`, plain-words `what`, `why` (from a reason-code table), `eta_s` and `options` (`continue`, `coarser`, `cancel`). Offer only the options the step supports. (3) A `slow_step_choice` command: `coarser` switches the remaining ring cells to the next coarser rung or the base DEM, and records `elevation_substituted` in `o4_unpatched_airports.json` `degraded`. `cancel` reuses the per-tile stop.
- Apps: a non-modal per-tile alert in both apps (Mac `BuildPane.swift` row / a sheet; Qt `O4_Qt_GUI.py` row). Wire change on both sides.
- Do not change the ring rung ranking itself (RULINGS 02f): "coarser" is a per-build user choice that is recorded, never a default.
- Tests: engine tests with a fake clock (no SlowStep before 300 s; one after; ETA = remaining/rate); `coarser` with the fetch stubbed records the substitution. A wire round-trip. Qt offscreen: the alert shows and Continue suppresses repeats for that step.
- Gates: UI GATES (also `test_tile_failures.py` for the degraded record). Closing check (owner/master): a cold Scotland tile.

## #1357
Patch editor: "Set elevation…" on the selected shape(s).
- Mac: `Sources/XPTerrainBuilder/PatchEditActions.swift` / `PatchShapeInspector.swift` (plus the right-click menu). Qt: `O4_Qt_Patch_Controller.py` / `O4_Qt_Patch_Panel.py`.
- A field in display units (m/ft, as the app shows elevations), prefilled with the mean `alt_abs` of the selection. Apply sets `alt_abs` on every node of the selected shapes, outer rings and holes. Shared nodes move too (default ON). The dialog first states "N shared nodes, M neighbouring shapes affected". One undoable edit that counts toward "N unsaved edits" and saves through the normal path to `<ICAO>_edited.patch.osm`.
- Optional, behind its own menu item: "Set elevation from point…".
- Tests: pure model tests in both languages (set on a 2-shape fixture sharing 2 nodes: all nodes equal; the neighbour's shared nodes change; undo restores; the ft→m conversion is exact to 1 mm). A Qt offscreen test of Apply plus Undo.
- Gates: UI GATES.

## #1339
New Zealand imagery: add a working LINZ Basemaps source and retire the dead `NZ.lay`.
- `Ortho4XP/Providers/New_Zealand/NZ.lay` (dead koordinates/fastly endpoint, `in_GUI=False`). Add `LINZ.lay` (WebMercator: `https://basemaps.linz.govt.nz/v1/tiles/aerial/WebMercatorQuad/{zoom}/{x}/{y}.webp?api={key}`; check the placeholder syntax against how the fetcher expands url_template in `Ortho4XP/src/O4_Imagery_Utils.py` / `O4_Imagery_Fetch.py`; decode webp with PIL), with max_zl and attribution "CC BY 4.0 Toitū Te Whenua LINZ". Mask it to NZ with a `.comb` or the provider extent so it is offered only for NZ tiles.
- Key: reuse the existing API-key credential flow (`O4_Authenticated_Sessions.py` `CREDENTIAL_KIND_API_KEY`, keyring storage; Qt settings prompt in `O4_Qt_Settings.py` ~l.381–414, Mac equivalent via the `SecretRequest` event). Never write the key into the .lay, the cfg or logs.
- Mark `NZ.lay` retired (remove it, or keep it as a provider that is never offered and say why in the PR). A tile whose detected source is NZ is offered LINZ (ties to #1334).
- Tests: a provider-parse test (LINZ listed for an NZ tile, absent for a non-NZ one); URL expansion with a dummy key; a redaction test (the key is absent from the log line). No network.
- Gates: UI GATES. Live check (owner): a ZL16 rebuild of one NZ tile with the owner's key.

## #740
Step 2 only: gate dead code with an `unused` ratchet. Waves 3–4 need byte-identical sweep builds and stay local.
- Plan of record: `Ortho4XP/docs/specs/unused-code-plan-20261015.md` (step 2). `tools/ratchets.py` has the subcommands size/funcs/dupes/layers/lint, with its baseline in `tools/ratchet_baseline.json`. `tools/archmap.py` (`scan`, `load`) has the used-by-another-module facts.
- Add a `tools/ratchets.py unused` subcommand: count public definitions in `Ortho4XP/src` with no reference from another module (production plus tests reported separately; an explicit allow-list file for dynamic use: JSONL command tables, `getattr` registries, entry points). The baseline is recorded and the count may fall, never rise (the same mechanics as the duplicate gate). Also make the near-duplicate count (`dupes --near`) a ratchet at its current value, and refuse a new module under `Ortho4XP/src/auto_patch/` outside the KEEP list the plan names.
- Index: add the tool's row to `tools/INDEX.md` in the same commit (tool discipline law).
- Tests: extend `Ortho4XP/tests/test_ratchets.py` with a synthetic two-module tree (a used def is not counted; an unused one is; an allow-listed one is not; rising above the baseline fails).
- Gates: PY GATES.

## #818
Build pane redesign: airport grading and custom-airport object fitting front and centre.
- The full layout is in the issue body (sections 1–2 and on). The references there are dated, so find by grep: the Mac build box is `Sources/XPTerrainBuilder/BuildPane.swift`, with the `auto_patch` setting row in `SettingsLayout.swift` and the "Modify custom airports" toggle in BuildPane; Qt is `Ortho4XP/src/O4_Qt_GUI.py` (`chk_vector`, `chk_imagery`, `chk_overlays`, the custom-airport checkbox) and the BUILD_BOX manifest in `Ortho4XP/tests/test_qt_layout_parity.py`.
- Deliver: (1) a one-line "what you're building" summary; (2) an Airports card with a per-build toggle "Grade airports to official standards", the airport list (ICAO, name, ruleset FAA/ICAO/EASA, "about N min" from `o4_engine/tile_time_model.py` or the last `wall_s`) and a total line; (3) a "Fit custom airport buildings" toggle listing the packs (name, object count) and the backup/restore note (`auto_patch_v2/airport/pack_journal.py`); (4) plumbing toggles collapsed under "Advanced". The per-build toggles override the tile setting for this build only, carried in the enqueue batch.
- Engine: if the airport list or estimates need a query, add one JSONL request/event (both sides in this PR).
- Update the parity manifest to the new BUILD_BOX order in both apps.
- Tests: the parity test is updated and green. A Qt offscreen test: toggling grading off sends `auto_patch` false in the batch and leaves the tile cfg alone. An engine estimate test on synthetic time records (a range, never a single number).
- Gates: UI GATES.

## #820
Show the cost before building: download GB, disk need vs free, and a time range.
- Engine: a JSONL request `plan_estimate(tiles, provider, zl, flags)` → per tile `{download_gb:[lo,hi], disk_gb:[lo,hi], time_s:[lo,hi]}` plus a total and `free_gb` of the tile folder's volume (shutil.disk_usage). Inputs: texture counts per ZL (`tile_time_model.estimate_texture_features`), the image cache check (`o4_engine/session.py` `_imagery_cache_directory`), the measured download rate (#622) and the tile time model (`remaining_step_seconds`, `_fit_imagery_rates`). Airport time comes from the #818 estimate. Respond within ~1 s (no network).
- Apps: a panel above Build in both apps, with a total line and an expandable per-tile table. When disk need > free, warn; refuse with the reason when the lower bound alone exceeds free space.
- Wire change: `events.py` and `OrthoEngineClient.swift` in this PR.
- Tests: an engine test with a tmp cache (half of the textures cached → download_lo halves); ranges have lo ≤ hi; a disk_usage stub triggers the refusal. A wire round-trip. Qt offscreen: the panel shows and Build is disabled with the reason when over.
- Gates: UI GATES.

## #824
Library view: every built tile with size, ZL, imagery source and an "In X-Plane" switch, plus cache cleanup.
- Today: the Mac per-tile inspector is in `Sources/XPTerrainBuilder/BuildPane.swift`; Qt shows "Size on disk" (`O4_Qt_GUI.py` ~l.1079 `info_size`). Build dates come from the tile scan (`O4TileInfo` meshDate/imageryDate; `TileScanCache.swift`).
- Engine: a `library_scan` JSONL command → per tile: size on disk, ZL, provider (cfg or detected, the #1334 resolver), built date, airports graded, packs modified (pack journal), `in_xplane`, `built_by` (XPTerrainBuilder / other tool). Plus `cache_sizes` (imagery, elevation, OSM) and `free_cache(kind)`, which reports what will be re-downloaded and needs a confirmation flag. Tiles built by other tools are read-only and never deleted.
- Apps: a sortable/searchable Library view in both apps, with multi-select install/uninstall/rebuild/delete (delete asks first) and "Restore originals" via the pack journal.
- Wire change on both sides. Deleting is a user action behind a confirmation; tests use tmp folders only.
- Tests: engine tests on a synthetic data folder (sizes summed, an other-tool tile flagged read-only, `free_cache` refuses without confirm). Qt offscreen: the list populates and sorts by size.
- Gates: UI GATES.

## #825
Per-step progress strip in each tile's row.
- Data is already on the wire: `StepProgress`, `AutoPatchProgress`, `TileClocks` (`Ortho4XP/src/o4_engine/events.py`), with `plan_steps` / `step_progress` in `o4_engine/session.py`. No protocol change is expected; if one is needed, both sides change in this PR.
- Mac: `Sources/XPTerrainBuilder/TileProgressRowLines.swift` / `BuildPane.swift` row: pills Map data → Airports → Ground → Water → Imagery → Install, each waiting/running/done, with the time when done. The Airports pill shows "KSEA — shaping runways (65 %)" from `AutoPatchProgress` (a plain-words stage table).
- Qt: `O4_Qt_GUI.py` row rendering (`_update_tile_row`, `_render_row_state`).
- Put the event→pill-state mapping in one pure function per app, with a shared fixture of event sequences.
- Tests: mapping tests (Swift + Python, same fixture). Qt offscreen: a fed event sequence shows the right pill states.
- Gates: UI GATES.

## #1323
Write a SPEC (no code): apply a small patch edit to an already-built mesh without a full rebuild.
- Deliverable: `Ortho4XP/docs/specs/incremental-patch-edit-spec.md`, answering each bullet of the issue: the diff of saved vs built patch; local re-mesh with fixed boundary edges; the height-only fast path (re-seat vertices); what forces a full rebuild; the step artefacts to keep and how `O4_Step_Reuse` stamps prove nothing else changed (#615); and the equivalence check against a full rebuild on a fixture.
- Read from code only: `O4_Step_Reuse.py`, `O4_Step_Code.py`, the mesh step (`O4_Mesh_Utils.py` / `O4_Tile_Utils.py`), the DSF writer (`O4_DSF_Utils.py` `build_dsf`), and the patch reader in the vector step. Run the consumer census (RULINGS 2026-08-30l) as a table of every pass that reads patch geometry, with file:line.
- Give the expected time for a few-node edit as a range from recorded phase times if they are in the repo; otherwise say what measurement the master must run (`tools/harness/build_airport.py`) and do not invent a number.
- End with the open owner questions. Changes no code; gates: `python tools/ratchets.py` only.

## #1226
OWNER-GATED: implement only after the owner approves the design in the issue's comment (2026-10-21).
- Engine: an optional `tile: [lat, lon]` on the `Log` event (`events.py` `class Log`), set by `o4_engine/parallel.py` `_drain_stderr` (which already knows the tile) and by the in-process session for 1-slot builds. Run-level lines stay untagged. Decode it in `OrthoEngineClient.swift` in the same PR.
- Engine writes `<tile build dir>/build_logs/<UTC>.log` (keep the newest 3) and `build_record.json` (start, end, outcome, duration, warnings, log name, builder `{tool, version}`), twinned the way `EngineStderrLog` is.
- Apps: the console filters by map selection (no tabs); one date filter (Today/48 h/7 d/30 d/All, default All) drives a Build History list and the map. Older tiles show "Log not saved". Mac: `BuildConsoleView.swift`, `BuildModel.swift`; Qt: the console widget in `O4_Qt_GUI.py`.
- Tests: tagging in parallel and in-process mode (stubbed workers); retention keeps 3; a record schema round-trip; the console filter in Qt offscreen.
- Gates: UI GATES (also `test_windows_text_io.py` for the new log writes).

## #1229
OWNER-GATED: the rulings are complete, but the issue waits on the owner's go-ahead and on the master recording the amendment to RULINGS 2026-09-18c.
- Configs: `Ortho4XP/src/O4_Settings_Model.py` `retire_unstamped_tile_cfg` (~l.692) stops moving files. XPTerrainBuilder reads and writes its own names (e.g. `XPTerrainBuilder_+XX+YYY.cfg`, plus a distinct global name instead of `<data>/Ortho4XP.cfg`) and ignores Ortho4XP's files. A one-time restore renames `Ortho4XP_+XX+YYY.cfg.pre352.bak` (the oldest) back when no file has that name; never overwrite.
- Patches: a custom patch still overrides the auto patch (`O4_File_Names.is_manual_patch_name`). The build log and tile info name it. Both apps draw a visible band around tiles with a custom patch, and the tile info offers "Use auto patch", which moves the custom patch aside and never deletes it.
- Bundle: on c67fd2a95 neither `Ortho4XP/Patches/+39-078/2W2_runways.patch.osm` nor `seed_shipped_patches` exists any more (grep finds no reference in `Ortho4XP/src`, the `.spec` files, `Sources` or `scripts`), so this item looks done. Confirm it and say so in the PR.
- Find every reader of the old cfg names by grep (`Ortho4XP.cfg`, `.cfg.pre352.bak`) and list them in the PR (consumer census).
- Tests: tmp data folder (an Ortho4XP cfg is untouched, byte-identical, after a build-settings write; the restore happens once and never overwrites; the custom-patch band flag is reported by the engine; switching back moves the file aside).
- Gates: UI GATES.

## #39
OWNER-GATED: needs a code-signing certificate or an Azure Trusted Signing account, held as repo secrets.
- `.github/workflows/release.yml` Windows job (`runs-on: windows-latest`, ~l.265): after PyInstaller and before packaging, sign the exe(s) and the installer with `signtool` (or `azure/trusted-signing-action`) using secrets. Skip with a loud notice when the secrets are absent, so forks and PR CI still pass. Verify with `signtool verify /pa`.
- Tests: a workflow lint (actionlint) in CI. A dry run on a branch with no secrets shows the skip notice.
- Do not commit any certificate material. The owner supplies the secrets; the master runs the first signed release.

## #566
OWNER-GATED: hosting, a GitHub App credential and the privacy note are owner decisions (RULINGS 2026-10-12b).
- Code once approved: a small HTTPS relay in its own top-level folder (e.g. `relay/`, not imported by the engine). It takes the app's redacted report JSON, folds duplicates by failure code + engine version, rate-limits per IP/day, files or updates the issue via a GitHub App installation token held server-side, and stores full logs privately with only a summary public. App side: "Report this problem" posts to the relay when the user has no GitHub sign-in (Mac `RunIssuesSheet.swift`, Qt `O4_Qt_Tile_Failures.py`), with a privacy note.
- Tests: relay unit tests with the GitHub API mocked (dedupe, rate limit, redaction kept). Both apps get the same new button (UI GATES).
