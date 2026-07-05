# XPScenery Doctor

A small native macOS app that inspects an X-Plane installation for scenery
problems and proposes solutions.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue) ![Swift 5.10](https://img.shields.io/badge/Swift-5.10-orange)

## What it does

Point it at your X-Plane folder, press **Analyze**, and it reports:

**Missing resources (from Log.txt)**
- Parses `Log.txt` for `Failed to find resource …` and other scenery errors.
- Builds an index of every `library.txt` export in Custom Scenery, then figures
  out *why* each resource is missing:
  - **Case mismatch** — the file exists but the reference differs only in
    letter case (breaks on case-sensitive volumes and some library versions).
  - **Typo** — a near-identical export exists in the installed library; the
    closest match is suggested.
  - **Broken library install** — the library promises the file but it's not on disk.
  - **Library not installed** — links directly to the download page for
    well-known libraries (OpenSceneryX, MisterX, SAM, ZDP, CDB, …) or to an
    x-plane.org search for unknown ones.

**Redundant packages**
- Finds airports provided by two or more custom packs (double buildings,
  z-fighting, wasted disk), says which pack wins per `scenery_packs.ini`
  priority, and flags disabled packs and double-installed folders.

**Package health & performance** (based on Laminar's scenery performance
guidance; check IDs follow the xpsan spec in `docs/`)
- `C-02` Heavy objects with no LOD — drawn at full detail at any distance.
- `C-03` Instancing-hostile ATTR state and blend ping-pong in OBJ8 files.
- `C-04` Texture problems: large PNGs that stutter at load (should be DDS),
  DDS without mipmaps, oversized and non-power-of-two textures.
- `C-05` Packs dominated by tiny objects (draw-call overhead).
- `PERF-01` Estimated VRAM footprint per pack, warning when a pack is likely
  to be performance-intensive, with concrete suggestions.

Findings are severity-tagged (error / warning / info), grouped by category,
filterable, revealable in Finder, and exportable as JSON.

## Building

Requires macOS 14+ and the Swift toolchain (full Xcode not required).

```sh
swift build                  # debug build
scripts/make_app.sh          # release build -> dist/XPSceneryDoctor.app
scripts/test.sh              # run unit tests
```

The X-Plane path is stored in standard macOS preferences
(`~/Library/Preferences/com.novemberlima.XPSceneryDoctor.plist`) and can be
changed anytime in **Settings** (⌘,).

## Project layout

```
Sources/SceneryKit/         Analysis engine (no UI, unit-tested)
Sources/XPSceneryDoctor/    SwiftUI app
Tests/SceneryKitTests/      Tests + a fixture fake X-Plane install
docs/                       Original xpsan spec + build plan
scripts/                    Build/test helpers
```

## Status

Prototype. Read-only by design — it never modifies your scenery; it reports
and recommends. See `docs/PLAN.md` for the roadmap (auto-fixes, DSF parsing,
overlap detection, deeper apt.dat checks).
