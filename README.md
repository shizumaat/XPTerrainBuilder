# XPScenery Doctor

A small native macOS app that inspects an X-Plane installation for scenery
problems and proposes solutions.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue) ![Swift 5.10](https://img.shields.io/badge/Swift-5.10-orange)

## What it does

Point it at your X-Plane folder, press **Analyze**, and it reports:

**Missing resources (from Log.txt)**
- **Damaged file names**: when a "missing" file is actually on disk under an
  encoding-mangled name ("baños" shipped as "ba§os" or "baÃ±os" by a broken
  archive tool), the case/normalization/mojibake-tolerant matcher finds it
  and Apply Fix renames it to the exact referenced spelling (ASCII typos are
  never guessed at). Renames are tracked in Modifications and revertible.
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
- The report's Redundant Packages view is actionable: multi-select packages
  (with size on disk shown per pack) and apply **Disable/Enable** (rewrites
  `scenery_packs.ini`, like X-Plane's own UI), **Move to Disabled Folder**
  (`Custom Scenery (Disabled)/`), or **Move to Trash** (Finder Trash,
  recoverable, with confirmation) — from the Actions button, the context
  menu, or the Delete key.

**Unused resources**
- Parses every DSF tile's definition tables (header-seeking reader — no
  whole-file loads even across 150k+ tiles) plus all `.ter/.obj/.pol/.fac/…`
  texture references and `library.txt` exports to build a reachability set.
- Flags `.ter` files no DSF references (the signature of a leftover
  Ortho4XP imagery source) and images nothing references at all — matched
  extension-blind (`foo.png` ↔ `foo.dds`), with `_LIT`/`_NML` companions and
  docs/preview art excluded, and packs with unreadable DSFs skipped rather
  than guessed at.
- The Unused Resources view lists them per pack with sizes; Trash Selected /
  Trash All moves them to the Finder Trash, tracked in Modifications for
  one-click restore.

**Package health & performance** (based on Laminar's scenery performance
guidance; check IDs follow the xpsan spec in `docs/`)
- `C-02` Heavy objects with no LOD — drawn at full detail at any distance.
  The object's physical size is measured from its geometry, and a one-click
  **Apply Fix** inserts a far-cull `ATTR_LOD` scaled to it (a 150 m terminal
  culls at 15 km, a 2 m person at 300 m). Fixes can be applied to a
  selection or a whole category.
- `C-03` Instancing-hostile ATTR state and blend ping-pong in OBJ8 files.
- `C-04` Texture problems: large PNGs that stutter at load (should be DDS),
  DDS without mipmaps, oversized and non-power-of-two textures.
- `C-05` Packs dominated by tiny objects (draw-call overhead).
- `C-09` Animation/`ATTR_light_level` on heavy objects (blocks instancing).
- `C-10` Spill-light census (the "FPS tanks at night" signature).
- `C-12` Objects spanning >1 km (Laminar's culling guidance).
- `C-04` large PNGs get a one-click **Convert to DDS** fix: in-app BC1/BC3
  encoder with full mip chains; dead alpha channels are stripped (DXT1).
- `PERF-01/02/03` VRAM warnings judged against **this Mac's actual hardware**
  (Metal working-set size, shown in the main window): per-pack footprints,
  packs that co-load in the same tile region, and libraries treated
  correctly (only placed assets load — a big library is not a warning).
  Performance findings are grouped by Airports / Overlays / Ortho / Libraries.
  Sources for the check catalog: `docs/PITFALLS.md`.

Findings open in a dedicated report window: category sidebar with counts,
toolbar search and severity filter, Reveal in Finder, library download links,
and JSON export (⇧⌘E). Analyze is ⌘R.

**Safe by construction:** before any file is edited, the original is saved
beside it as `<file>.xpsd-backup` and recorded in a manifest. Window ▸
Modifications (⌥⌘2) lists every file the app has changed, with Revert
Selected / Revert All restoring the originals byte-for-byte. Edited OBJs are
re-parsed after the edit and rolled back automatically if validation fails.

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
