# Spec: default-airport index served by the engine (`airport_index` command)

Status: frozen (Fable, 2026-08-15). Implementer deviations are reported
back for Fable review, never decided in-flight (CLAUDE.md §1a).
Owner-law canon: `docs/RULINGS.md` — PRE-SHIP MODE is in force; a brief
violating a listed ruling is invalid.

## Why

The map search / gray default-airport marks feature needs X-Plane's
Global Airports index on every front end. The engine ALREADY owns the
shared implementation — `src/O4_Airport_Index.py` (streaming apt.dat
parse, TSV cache `.airport_index.tsv` with mtime_ns+size staleness,
ranked search) — and the Qt GUI consumes it in-process. The macOS app
grew a parallel native Swift implementation today
(`Sources/SceneryKit/GlobalAirportIndex.swift`: locate + byte-streaming
parser + JSON cache). Two parsers in two languages is the
census-wrapper defect class: they will drift. This round moves the app
onto the engine's index over the JSONL protocol and deletes the Swift
parser. UI-side concerns (marks drawing, per-keystroke match, tile
select) stay native — they are presentation, not index.

## Engine side (`Ortho4XP/`)

### 1. `src/O4_Airport_Index.py` — close the two coverage gaps

The Swift parser being deleted covered two things this module lacks;
fold them in so no coverage is lost:

a. **Water-runway fallback (row 101).** In `_iter_airports`, beside the
   existing 100/102 fallbacks: `101` rows, lat/lon at 0-based fields 4
   and 5, guard `len(row) >= 6`, same "only the FIRST fallback row,
   datum still wins" rule (share the `rwy_lat is None` gate). A
   seaplane base with only a water runway currently indexes as
   position-less and is skipped; after this it is searchable.

b. **`find_apt_dats` candidates.** Add the shipped-default fallback
   `Resources/default scenery/default apt dat/Earth nav data/apt.dat`
   as the LAST candidate, and for every candidate folder accept the
   `Earth Nav Data` spelling beside `Earth nav data` (Linux is
   case-sensitive; packs in the wild carry both). Per candidate, take
   the FIRST spelling that exists and never emit the same file twice —
   on a case-insensitive volume both spellings answer, and a duplicate
   path would stream the 380 MB file twice in `build_index`.

c. **`_CACHE_VERSION` 3 → 4.** (a) changes parse results and (b)
   changes the source set; stale v3 caches must rebuild once
   (`index_is_stale`'s `version < _CACHE_VERSION` already handles it —
   Qt and the bathymetry band's gate rebuild transparently).

Update the module docstring and the affected function docstrings; keep
the module stdlib-only, no GUI imports.

d. **Header count helper.** `index_count(cache_file) -> Optional[int]`:
   read ONLY the header line, return the recorded count, `None` on
   missing/malformed. The session command's reply uses it (never load
   40k rows onto the read loop).

### 2. `src/o4_engine/events.py` — `AirportIndexReady`

New frozen dataclass event, fields: `path: str`, `count: int`,
`error: str = ""` (empty on success). Class name IS the wire name
(Swift matches the string literal). Bump `PROTOCOL_VERSION` to "1.6"
with an additive header note in the established style, naming the
`airport_index` command and this spec.

### 3. `src/o4_engine/session.py` — `airport_index` command

Handler `airport_index(self, xplane_dir="")`, registered in
`jsonl.py`'s `_build_handlers` as `"airport_index"`. Replies (returned
dict, synchronous):

- No `xplane_dir` or `find_apt_dats` empty → `{"status": "none"}`.
- Cache fresh (`not index_is_stale(paths, cache)`) →
  `{"status": "ready", "path": cache, "count": index_count(cache)}`.
- Stale → `{"status": "building"}`, and a daemon worker thread
  (mirror the `provider_sign_in` worker pattern — the READ-LOOP HAZARD
  note in session.py applies: a 380 MB parse must never run on the
  transport read loop) runs `build_index` and emits
  `AirportIndexReady(path=cache, count=n)`; on exception,
  `AirportIndexReady(path="", count=0, error=str(e))`.
- A second `airport_index` while a build worker is running replies
  `{"status": "building"}` without starting a second worker (a plain
  flag under an existing/one new lock, cleared in the worker's
  `finally`).

Cache path: `O4_File_Names.airport_index_cache()` — never a private
spelling.

### 4. Engine tests (run ONCE, through the ledger)

Extend `tests/test_airport_index.py`:
- The SSSS seaplane fixture (documented today as "must be skipped")
  now indexes from its 101 row — update fixture comments and
  assertions; add a 101-fields test (lat field 4, lon field 5, datum
  still wins, first-fallback-only).
- `find_apt_dats`: third candidate precedence (both existing beat it),
  alternate-spelling discovery, no duplicate paths.
- v4 header written; v3 cache reported stale; `index_count` on a good
  header, missing file, junk file.

New `tests/test_engine_airport_index.py` (or extend
`tests/test_engine_session.py` if a same-file section fits better —
follow the harness style of `test_engine_provider_signin.py`): fresh →
ready reply with count; stale → building reply then AirportIndexReady
with the built cache's real count; second command during build →
building, one worker; no apt.dat → none; worker failure → error event.
Headless, `tmp_path`, no network, never the real X-Plane install.

## Swift side (`Sources/`)

### 5. `Sources/SceneryKit/GlobalAirportIndex.swift` — reader only

Delete `locate`, `parse`, `RowParser`, `defaultChunkSize`, the JSON
`FileFormat`/`cacheURL`/`signature`/`load`/`save`/`loadOrParse`. Keep
`GlobalAirport`. Add:

- `static let cacheFilename = ".airport_index.tsv"` — twin of
  `O4_File_Names.airport_index_cache()`'s basename; comment it as a
  wire constant (rename either side and the other breaks silently).
- `static func readCache(at url: URL) -> [GlobalAirport]?` — nil when
  missing or the header isn't `O4AIRPORTIDX <version> <count>` with
  version >= 3 (the reader consumes only columns 0/4/5, stable since
  v1, but pre-v3 caches predate the category column the engine now
  always writes — simplest correct gate). Skip `#SRC` lines; rows are
  TAB-separated `code name city country lat lon category` (6 or 7
  columns accepted); skip malformed rows and 0/0 positions. The file
  is a few MB — TextFile.contents + TextFile.lines is fine here.

### 6. `Sources/SceneryKit/OrthoEngineClient.swift`

`AirportIndexReady` case in the event switch (string literal, like the
others) decoding path/count/error into a typed event, and a
`requestAirportIndex(xplaneDir:completion:)` convenience following the
`auth_providers` reply pattern.

### 7. Wiring (`BuildModel.swift`, `AnalysisController.swift`, app setup)

- BuildModel: when the engine session starts (`connectIfNeeded`, beside
  the existing `rescan()`) and whenever the X-Plane path setting
  changes with a live session, send `airport_index` with the xplane
  path. On a `ready` reply, read the TSV at the REPLIED path
  (detached, off-main) and publish; on `building`, wait for the
  `AirportIndexReady` event, then read; `none`/error → publish `[]`.
- Optimistic start: before/without a session, if
  `dataRootURL/.airport_index.tsv` exists, read it immediately
  (stale-tolerant, display-grade — same philosophy as the scenery
  index's optimistic launch); the engine's answer supersedes.
- Handoff: AnalysisController gets
  `func setGlobalAirports(_ airports: [GlobalAirport])` which stores
  them (replacing the `loadOrParse` call and the root-keyed in-memory
  copy — GlobalAirportIndex is no longer reachable from the scan
  worker) and re-derives `mapOverlays.defaultAirports` via the
  existing `withDefaultAirports` for the CURRENT overlays, so airports
  arriving after a finished scan still appear. Scans keep applying the
  stored list on their three publish paths as today.
- Wire BuildModel→AnalysisController where both objects are created
  (follow how they are constructed/injected today — a simple closure
  property on BuildModel set at construction is acceptable). Search
  (`performSearch`) and the canvas drawing are already wired to
  `defaultAirports` and need no change.

### 8. `Sources/SceneryKit/InstallationScanner.swift`

Replace the TWIN comment on `parseAirports` (it names the deleted
Swift parser): this parser stays for CUSTOM packs' small apt.dats;
default airports come from the engine's `O4_Airport_Index` via the
`airport_index` command.

### 9. Swift tests

Replace `Tests/SceneryKitTests/GlobalAirportIndexTests.swift` with
reader tests: a handwritten v3 and v4 cache with `#SRC` lines, 6- and
7-column rows, malformed rows and a 0/0 row (skipped), a v2 header
(rejected), a junk file (nil). Delete the parser/locate/JSON-cache/
twin tests with the code they covered.

## Constraints and verification (pre-ship mode)

- Run `Ortho4XP/venv/bin/python tools/blast.py <file>` (from the repo
  root) before editing each existing file; events.py ↔
  OrthoEngineClient.swift is a wire-protocol edit — blast reports the
  drift hazard; both sides land in this one change-set.
- Engine tests: ONLY the files covering the change
  (`tests/test_airport_index.py`, the new/extended engine-session
  file), ONCE, via `venv/bin/python tools/run_with_ledger.py --
  python -m pytest <files>` from `Ortho4XP/`.
- Swift: `DEVELOPER_DIR=/Applications/Xcode-beta.app swift build` and
  `swift test`, once.
- Add one line to `docs/DEFERRED_VERIFICATION.md` for the skipped
  full-suite pass, per pre-ship mode.
- Build-time impact statement: ZERO on both budgets — nothing in the
  tile-build or auto-patch path changes; the index build runs only on
  UI demand off the transport read loop, exactly as the Qt map already
  does today.
- Convergence guards: no numeric targets (materiality floor N/A);
  attempt cap 2 per failing test then STOP and report; long steps
  write START/EXIT stamps to the scratch dir.
- No GUI-toolkit imports in core modules; type hints + docstrings on
  new/changed engine code; never touch the real X-Plane install or the
  shared data repo.
- Commit nothing; leave the tree for review.

## Report back

Files touched; engine + Swift test summaries; reply/event shapes as
implemented; any deviation (stop and report, do not improvise).
