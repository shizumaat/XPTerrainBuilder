# XPScenery Doctor — Prototype Plan

Goal: a simple, native Mac app that inspects an X-Plane installation for
scenery issues and proposes solutions. This adapts the `xpsan` CLI spec
(`docs/xpsan_spec.docx`) into a GUI app and adds two feature areas the spec
didn't cover: Log.txt missing-resource forensics and redundant-package
detection.

## Architecture

Two SwiftPM targets, so the analysis engine stays UI-free and testable:

| Target | Role |
|---|---|
| `SceneryKit` | Pure-Swift analysis engine. No AppKit/SwiftUI imports. |
| `XPSceneryDoctor` | SwiftUI app: small main window, Settings scene, results sheet. |

The app is bundled by `scripts/make_app.sh` (SwiftPM binary + Info.plist +
ad-hoc codesign) because the machine builds with Command Line Tools, not
Xcode. The bundle id `com.novemberlima.XPSceneryDoctor` gives the standard
preferences plist. The app is not sandboxed (a prototype that reads an
arbitrary user-chosen folder tree; sandboxing would need security-scoped
bookmarks — noted as future work).

### Engine pipeline (`Analyzer.run`)

1. **InstallationScanner** — walk `Custom Scenery/`, parse
   `scenery_packs.ini` (priority + enabled state) and each pack's `apt.dat`
   (row codes 1/16/17 + `1302 icao_code`), detect library packs and index
   every `library.txt` EXPORT into a `LibraryIndex`.
2. **LogAnalyzer** — regex-scan `Log.txt` for missing-resource lines and
   generic scenery errors. Each missing virtual path is diagnosed against the
   LibraryIndex in order:
   - exact case-insensitive export match → **case mismatch** (LOG-01)
   - export exists but backing file absent → **broken install** (LOG-02)
   - export + file exist → stale log note (LOG-03)
   - library prefix installed, near-miss export within edit distance →
     **typo, suggest closest path** (LOG-04)
   - prefix installed, nothing close → **version mismatch** (LOG-05)
   - prefix not installed → **missing library**, link via `KnownLibraries`
     table or x-plane.org search URL (LOG-06/07)
3. **DuplicateAnalyzer** — group airports by ICAO across packs (excluding
   Laminar packs and libraries), report conflicts with the ini-priority
   winner (DUP-01), disabled packs (DUP-02), double-installed folders (DUP-03).
4. **PackageHealthAnalyzer** — per pack (Laminar packs skipped), a pragmatic
   subset of the xpsan check catalog:
   - C-02 heavy OBJ (≥10k verts) without ATTR_LOD
   - C-03 promotable ATTR_no_blend → GLOBAL_no_blend; blend ping-pong
   - C-04 large PNGs, DDS without mips, non-POT, oversized textures
     (header-only inspection of PNG IHDR / DDS header — no image decoding)
   - C-05 tiny-object-dominated packs
   - PERF-01 estimated texture VRAM per pack with a warning threshold
5. Findings (spec §4 schema: check id, severity, bottleneck-ish category,
   fixability, suggestion, URL) are sorted and returned with stats; the UI
   groups them and can export canonical JSON.

### UI

- **Main window**: fixed-size ~340pt card. Path status (valid/invalid icon),
  folder picker on first launch, prominent **Analyze** button, progress label
  while scanning, link to reopen the last report.
- **Settings** (⌘,): view/change the X-Plane folder; stored via `@AppStorage`.
- **Results sheet**: severity filter (segmented), findings grouped by
  category in disclosure rows with detail, suggestion, "Reveal in Finder",
  library download link, and JSON export.

### Testing

`Tests/SceneryKitTests` runs against `Fixtures/FakeXP`, a miniature X-Plane
install with seeded bugs: a case-mismatched reference, a typo'd reference, a
missing known library, an unknown library, a broken export, duplicate KSEA
packs, a 10.5k-vert OBJ with no LOD + per-mesh ATTR_no_blend, and an 8192-px
non-POT PNG. 13 tests cover each parser plus an end-to-end run.

## Out of scope for the prototype (roadmap)

- DSF parsing (placements, draped-poly windings) → C-01 overdraw area checks
  and real placement counts for C-02. Needs DSF2Text or a native reader
  (7-zip + custom binary parser).
- Auto-fix mode (spec phase 2): PNG→DDS conversion, GLOBAL_ promotion,
  far-cull LOD insertion — always to a copy, with a change manifest.
- apt.dat geometry checks (overlapping pavement, runway conflicts).
- Forest density estimation (C-07) and facade checks.
- Sandboxing + security-scoped bookmarks for App Store distribution.
- Live x-plane.org search API integration instead of the static
  `KnownLibraries` table.
