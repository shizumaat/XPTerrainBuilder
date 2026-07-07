# XPSceneryDoctor — Session Handover

Last updated: 2026-07-06 (commit `a4e0c09`). Repo: https://github.com/shizumaat/XPSceneryDoctor (private).

## What this is

A native macOS app (SwiftUI, SwiftPM — no .xcodeproj) that inspects an
X-Plane installation for scenery problems and fixes what it safely can.
Owner: Noah (noahplieberman@gmail.com, GitHub `shizumaat`). His install:
`/Users/noah/X-Plane 12` — 2 TB, ~4,200 packs (2,508 of them symlinked),
164k+ DSF tiles. It is the reference/validation corpus for everything.

## Current state (all shipped and pushed)

- **v2 plan Phases 0–2 complete** (docs/PLAN-V2.md). Main window is the
  map: zoomable night-chart world view (offline Natural Earth 110m + 50m
  coastlines), X-Plane 1° tile grid with coordinates labels at zoom,
  coverage tints (ortho/mesh/landmark), sectional-style airport marks,
  tile selection (click / ⌘-click / ⇧-drag), package inspector right
  (viewport-tracking, context-aware actions), results bottom pane
  (viewport-filtered). Scroll/pinch zoom anchored at cursor. Scoped
  analysis (⌘R = selection, ⇧⌘R = everything).
- **Engine** (SceneryKit, UI-free, 50 tests): proactive missing-resource
  audit (RES-01..04, uncapped) resolving every DSF DEFN entry against
  pack files + installed libraries + default libraries; unused-resource
  detection via reachability BFS; Log.txt corroboration (LOG-*);
  duplicates with sizes/status; package health checks (C-02..C-12, see
  docs/PITFALLS.md for sourced rationale); system-aware VRAM thresholds
  (Metal working-set); pack kinds from DSF sim/overlay property.
- **Fixes** (FixEngine, all backed up + revertible via Window ▸
  Modifications, grouped by package): far-cull ATTR_LOD sized from OBJ
  bounding box; mojibake/case rename (PathRepair — ASCII never guessed);
  PNG→DDS (in-app BC1/BC3 encoder, mips, non-POT resample);
  GLOBAL_no_blend promotion; pack actions enable/disable/install/
  uninstall/trash (Finder Trash). Content-edit backups are sidecars
  (`<file>.xpsd-backup`) — user explicitly prefers this; renames/trash
  record without copies (dialogs describe each honestly).
- **Categories**: Installation, Missing Resources, Redundant Packages,
  Package Health, Performance, Developer Debug (author-only issues,
  fixability .manual; incl. RES-05 deprecated-library-asset refs),
  Unused Resources. Reports persist to Application Support and reload
  at launch.
- **Inspector drag-reorder**: packages listed in scenery_packs.ini load
  order with kind icons; drag rewrites the ini by permuting packs among
  the line slots they already occupy (never hauls a pack across the
  ini's airport/library/ortho regions — Noah's explicit requirement);
  iniOrderOverride shows the new order while the rescan catches up.
- **Icon**: v9 — VFR sectional airport symbol under a handleless graphite
  loupe on a night IFR chart, true continuous radial lens distortion.
  Fully parametric in scripts/make_icon.swift (render → iconutil).

## Hard-won correctness lore (do not regress)

1. **CRLF**: Swift treats `"\r\n"` as ONE grapheme; `split(separator:
   "\n")` does not split CRLF files. ALL line parsing must go through
   `TextFile.lines()`. This bug zeroed every Windows-authored library
   index (regression test exists).
2. **Separators**: library.txt EXPORT lines may be tab-separated AND use
   backslash paths (RD_Library). LibraryIndex normalizes both. EXPORT
   keywords with extra leading args: EXPORT_RATIO (ratio) and
   EXPORT_SEASON / EXPORT_EXCLUDE_SEASON (season list) — XP12's default
   libraries remap legacy XP8–11 paths (lib/g8/*) through the season
   forms; mis-parsing them false-alarmed RES-01 (regression test).
3. **Symlinks**: `isDirectoryKey` is false for symlinked packs — 60% of
   Noah's install. `packDirectories` resolves via `fileExists`.
4. **FD limits**: GUI apps get 256 fds; abandoned directory enumerators
   are autoreleased. Read Log.txt BEFORE scanning; wrap per-pack work in
   `autoreleasepool`.
5. **strtod takes a process-wide locale lock** — the hand-rolled float
   parser in ObjParser exists for that reason (10-thread parsing went
   50s → 4:42 with strtod).
6. **Library virtual paths ≠ folder names** (defined by library.txt);
   default libraries live in `Resources/default scenery/*` and MUST be
   indexed or lib/… references false-alarm.
7. **X-Plane resolves textures extension-blind** (foo.png ↔ foo.dds) and
   falls back to the referencing file's own folder; `_LIT/_NML` and
   seasonal companions follow their base texture.
8. **Unused-resource guards**: DSF-driven packs only; plugin markers
   (.xpl/.wt/.lua/.acf, xsb_aircraft.txt, plugins/) skip the pack;
   seasonal/options folders protected; unreadable DSFs skip loudly.
   Deletion-grade: per-pack orphans are only CANDIDATES until
   verifyUnused sweeps every pack for ../-escaping refs (chains kept:
   an externally-referenced .ter protects its own textures). Library
   roots parse via LibraryIndex over ALL root library*.txt files —
   the old space-split parser dropped simHeaven's tab+CRLF exports
   and flagged its whole export set (3,464 files) unused.
9. **Foundation path canonicalization is inconsistent**:
   standardizedFileURL adds /private when collapsing ".." while
   resolvingSymlinksInPath strips it only for EXISTING paths — never
   compare file paths without one canonical form (see canonical() in
   verifyUnused; it also unifies symlinked-pack spellings).
10. **7z DSFs exist on the reference install** (Global_Forests_v2:
   all 37,632 tiles) — DSFReader decodes them in-process via
   /usr/lib/libarchive.2.dylib (dlopen; SevenZip.swift). Only the
   stream head is decompressed (DEFN sits at the front).
11. **DSF geometry spec traps** (DSFGeometryReader, validated 100%
   in-bounds on 40+ real tiles incl. a 3.5M-point simHeaven NY tile):
   NESTED POLYGON RANGE's count byte is the WINDING count followed by
   count+1 uint16 fence posts (the spec's wording misleads); empty
   pools (count=0, even depth=0) exist and carry no per-plane data;
   scaling is offset + raw × multiplier / 65535 (2^32−1 for PO32),
   multiplier 0 = raw passthrough; POOL SELECT indexes 16- and 32-bit
   pools in one combined file-order space.
12. **Analysis cache**: per-pack, keyed by content signature (depth-2
   names/sizes/mtimes + every DSF's mtime). Bump
   AnalysisCache.schemaVersion whenever any analyzer's findings
   change shape or meaning — stale caches otherwise serve old
   results. Blind spot: in-place edits of non-DSF files deeper than
   2 levels (own fixes invalidate explicitly; ⌘R bypasses).
13. **Pack names are NOT unique**: the same-named pack can sit in
   Custom Scenery and Custom Scenery (Disabled) simultaneously
   (uninstall + fresh re-download — real state on Noah's install:
   Aerosoft LFMN). Both are scanned. Never Dictionary(
   uniqueKeysWithValues:) on pack names, never use bare names as
   SwiftUI ids — key by path (regression test exists; this crashed
   the app on search).
14. **ATC "lost some controllers" (LOG-91/92)**: X-Plane drops named
   controllers whose every apt.dat frequency is outside 118.000–
   136.990 MHz (military UHF fields). Its exact grouping rule resists
   reverse-engineering — name-grouping reproduced only 12 of 18
   Global Airports complaints (KAGC/KAFW/KTRI have valid VHF in every
   model tried; 3A2 has a UHF-only Departure yet no complaint) — so
   we anchor on the log lines as ground truth and only DIAGNOSE the
   owning pack's apt.dat (whitespace-sensitive name grouping: "Ämari
    Tower" double-space is a real GA bug pattern). Frequency lookup:
   airnav.com/airport/<id> (US, rich VHF+UHF per controller with
   sectors); ourairports.com/airports/<icao>/frequencies.html
   (worldwide, sparse for military). LOG-91 is now auto-fixable
   (Noah sanctioned it): FixEngine.repairControllerFrequencies
   fetches at FIX time (analysis stays offline; frequencyProvider is
   injectable for tests), adds a VHF row per dropped controller —
   published freq preferred, collision-avoidance per CODE only
   (approach + departure legitimately share TRACON freqs; KBNA WEST
   = 119.35 for both), unused in-band channel as fallback (legacy
   2-digit rows need 10 kHz-representable values). UHF rows stay.
   CLI: --lookup-freq <icao>, --repair-freq <apt.dat> <icao>.

## Environment quirks (Noah's machine)

- **Toolchain**: Command Line Tools only ACTIVE (`xcode-select -p` →
  CLT) even though Xcode is installed. Consequences: SwiftUI `@State`
  macro unavailable → use `ViewState<T>` + `@StateObject` (see
  Sources/XPSceneryDoctor/ViewState.swift); XCTest unavailable → swift-
  testing; run tests via `scripts/test.sh` (rpath workarounds baked in);
  builds use `swift build --build-system native` (the default swiftbuild
  drops macro plugin paths on incremental rebuilds).
- **App bundle**: `scripts/make_app.sh release` → dist/XPSceneryDoctor.app
  (copies SwiftPM resource bundle + AppIcon.icns; bundle id
  com.novemberlima.XPSceneryDoctor).
- **CLI harness**: `swift run xpdoctor-cli "/Users/noah/X-Plane 12"
  [--json] [--scope <pack-name>]...` (plus debug flags `--query-lib
  <vpath>`, `--parse-lib <dir> <vpath>`). Use it to validate engine
  changes against the real install before shipping; full run ≈ 5 min,
  --scope makes spot checks seconds.
- Host cannot screenshot (no Screen Recording permission) — UI changes
  need Noah's eyes; expect polish iterations.
- Memory dir has `toolchain-clt-only.md` with the same toolchain facts.

## Workflow conventions (established with Noah)

- Ship in slices: build → `scripts/test.sh` → validate on the real
  install via CLI → `make_app.sh` → relaunch app (quit + open) → commit
  (detailed message, Co-Authored-By: Claude Fable 5) → push.
- Findings philosophy: "never guess" — false positives are worse than
  false negatives; severity means actionability (unfixable → info or
  Developer Debug); every mutation revertible and recorded.
- Noah gives batched, specific feedback; verify claims empirically on
  his install before assuming the code is right OR wrong (two of his
  bug reports were real engine bugs; one was already fixed on disk).

## Known gaps / next candidates

- **Runtime**: full-install analysis ~5 min *before* the symlink fix
  more than doubled the visible pack count — first full run since will
  be slower. Scoped (map-selection) analysis is the everyday path.
- **Phase 2 leftovers**: libraries aren't listed in the inspector for a
  tile selection (no tiles); DuplicatesView/UnusedResourcesView tables
  embedded in the results pane are fixed-height (300pt).
- **Researched but unbuilt** (docs/PITFALLS.md, ranked): spill-light
  radius reduction fix ("tame night lighting"); legacy-light → XP12
  photometric modernization (named/param light swaps); facade stretch;
  apt.dat overlap lint; exclusion-zone detection; dead-alpha stripping;
  per-def placement COUNTS (geometry reader already collects them —
  could upgrade C-09 severity when an animated object is placed 100×).
- **Low-poly LOD generation** (QEM decimation for static single-texture
  OBJs): assessed as feasible; Noah interested but not yet green-lit —
  needs preview-then-apply UX, not one-click.
- 7z-compressed DSFs are skipped (none exist on the reference install).
- Old report JSONs predating enum changes fail decode silently → user
  just re-analyzes; harmless.

## File map (orientation)

- `Sources/SceneryKit/` — engine: Analyzer (orchestration/streaming),
  InstallationScanner, LibraryIndex, LogAnalyzer, ResourceAuditAnalyzer
  (missing+unused), PackageHealthAnalyzer, DuplicateAnalyzer, DSFReader,
  ObjParser, TextureInspector, DDSEncoder, FixEngine, PackActions,
  PathRepair, TextFile, TileMath, SystemInfo, Models.
- `Sources/XPSceneryDoctor/` — app: MapMainView, MapCanvasView,
  MapModel, ScrollZoomCatcher, PackInspectorView, ResultsPane,
  ReportWindow (secondary, ⌥⌘1), DuplicatesView, UnusedResourcesView,
  ModificationsWindow, AnalysisController, SettingsView, ViewState.
- `Tests/SceneryKitTests/` — 50 tests incl. fixture fake install +
  synthetic DSFs. `scripts/` — test.sh, make_app.sh, make_icon.swift.
- `docs/` — PLAN-V2.md (roadmap), PITFALLS.md (sourced check catalog),
  HANDOVER.md (this), xpsan_spec.docx (original brief).
