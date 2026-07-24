# XPTerrainBuilder

A native macOS app that builds X-Plane photoscenery by driving the
Ortho4XP engine bundled in this repository: pick tiles on a map, tune the
build options, and watch the build run — no Python setup required.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue) ![Swift 5.10](https://img.shields.io/badge/Swift-5.10-orange)

This repo merges what used to be two projects:

- **XPTerrainBuilder** — the SwiftUI app and its `SceneryKit` support
  library (repo root).
- **Ortho4XP** — vendored as a squashed snapshot under `Ortho4XP/`,
  taken from the `dev` branch of
  [shizumaat/Ortho4XP-novemberlima](https://github.com/shizumaat/Ortho4XP-novemberlima)
  (itself a fork of [shred86/Ortho4XP](https://github.com/shred86/Ortho4XP),
  which forks the original
  [oscarpilote/Ortho4XP](https://github.com/oscarpilote/Ortho4XP)).
  The snapshot's source commit is recorded in the vendoring commit
  message. **Since the vendoring (2026-07-22), the copy in this repo is
  the canonical engine tree** — all engine development happens here and
  the app's release builds freeze from it; the novemberlima repository
  holds the pre-vendoring history and is no longer updated.

The app is focused on terrain building only. The scenery-analysis
functionality of the former XPSceneryDoctor project (missing-resource
diagnosis, redundant-pack detection, package health checks, …) is **not
part of this app** — it is planned as a separate app. Some of its code
still lives in `SceneryKit` and the `xptb-cli` target but is not surfaced
in the app.

## What it does

The app drives the bundled Ortho4XP engine over its JSON-lines session
protocol (`Ortho4XP.py --engine-jsonl`) with a native GUI:

- **Map-based tile picking** — select the 1°×1° tiles to build directly
  on the map.
- **Native build configuration** — the engine's own config schema is
  introspected at runtime, so new engine options appear in the UI without
  an app update. Per-tile overrides, imagery provider selection, and
  provider API keys (stored in the keychain) are all handled in-app.
- **Build console** — live progress and engine output for each build
  step, with cancellation.
- **Self-contained engine** — release builds embed a frozen engine
  (bundled Python runtime and packages); there is nothing for the user to
  install. Settings can point at any other engine checkout instead to run
  a custom version.

All writable engine data (downloads, elevation data, masks, finished
tiles, config) goes to a user-chosen data folder via
`ORTHO4XP_DATA_ROOT`; the engine copy inside the app bundle stays
read-only.

## Beyond stock Ortho4XP

Relative to the shred86 base it forked from, the engine in this repo
adds (see `Ortho4XP/docs/specs/` for the individual specifications):

**Airport terrain grading (`auto_patch`)**
- FAA / EASA / ICAO-compliant regrading of every airport's paved
  surfaces: runway vertical profiles reconciled against CIFP threshold
  data, taxiway/apron/junction elevation solving with per-role grade
  caps, RESA and wingtip-clearance cuts, boundary ribbons, retaining
  walls, and tunnel/bridge handling for scenery objects — instead of
  draping pavement over raw DEM terrain.
- Custom airport packages can be *reseated*: after a mesh rebuild, the
  3-D objects of installed airport packs are rewritten in place to sit
  on the new ground (originals kept as `.anchor_bak` backups, with
  provenance sidecars and one-click revert from both front ends).

**Elevation**
- **Airport elevation insets**: per-airport meter-class DEM patches
  fetched from a registry of ~80 providers
  (`Ortho4XP/Providers/Elevation/*.elv`) — national lidar (SwissALTI3D,
  USGS 3DEP, France 50 cm, England 1 m, Japan 5 m, Australia 5 m, a
  dozen German states, and many more), bathymetry (GEBCO, EMODnet, the
  NOAA CUDEM series, Allen Coral Atlas), and tidal-datum variants —
  blended into the tile DEM with feathering and acceptance probes.
- **Tile elevation detail level**: a per-tile setting (`auto`, 90, 30,
  10, 5, 1 m classes) controlling the whole tile's working grid, with
  registry-driven tile-wide base sources beyond the classic
  Viewfinderpanoramas set.
- Coastal bathymetry bands (depth-graded water masks from real
  bathymetry).

**Pipeline & tooling**
- A JSON-lines engine session protocol (`--engine-jsonl`) that GUI
  front ends drive: scan, per-tile enqueue/cancel, config-schema
  introspection, scenery links, reseat status/revert — this is what the
  mac app (and the Qt app) speak.
- Parallel tile builds with per-provider download slots and a
  background OSM prefetch; OSM regional extracts clipped by CI-built
  `osmium` binaries bundled for macOS/Windows/Linux.
- A new PySide6 map-first GUI for Windows/Linux (`Ortho4XP_Qt.py`)
  alongside the legacy Tkinter app, sharing the engine protocol
  semantics with the mac app.
- Texture modes, color harmonization, default-landclass terrain mode,
  an MSFS→X-Plane airport package converter, and PyInstaller freeze
  specs used for the self-contained releases.

## Building the app

Requires macOS 14+ and the Swift toolchain (full Xcode not required).

```sh
swift build                  # debug build
scripts/make_engine.sh       # freeze the engine (self-contained python runtime)
scripts/make_app.sh          # release build -> dist.nosync/XPTerrainBuilder.app
                             # embeds the frozen engine when present, else the source tree
scripts/test.sh              # run unit tests
```

To run the engine from source instead of the frozen copy (dev builds),
run `Ortho4XP/install_mac.sh` once to create the engine's Python venv;
the app prefers `Ortho4XP/venv/bin/python3` when it exists and falls back
to the system `python3`.

The X-Plane path is stored in standard macOS preferences
(`~/Library/Preferences/com.novemberlima.XPTerrainBuilder.plist`) and can be
changed anytime in **Settings** (⌘,).

## Project layout

```
Sources/SceneryKit/         Engine glue + supporting library (no UI, unit-tested);
                            also holds legacy analysis code not surfaced in the app
Sources/XPTerrainBuilder/   SwiftUI app
Sources/xptb-cli/           Headless CLI (legacy analysis; not part of the app)
Ortho4XP/                   Vendored Ortho4XP engine (Python; own README,
                            tests, and install scripts)
Tests/SceneryKitTests/      Tests + fixture fake X-Plane install + fake engine
docs/                       Design notes and build plan
scripts/                    Build/test helpers
```

## Status

Prototype, under active development. The scenery-doctor analysis features
are out of scope for this app and planned as a separate project.
