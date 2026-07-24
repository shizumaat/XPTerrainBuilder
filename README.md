# XPTerrainBuilder

A native macOS app that builds X-Plane photoscenery by driving the
Ortho4XP engine bundled in this repository: pick tiles on a map, tune the
build options, and watch the build run — no Python setup required.

![macOS 14+](https://img.shields.io/badge/macOS-14%2B-blue) ![Swift 5.10](https://img.shields.io/badge/Swift-5.10-orange)

This repo merges what used to be two projects:

- **XPTerrainBuilder** — the SwiftUI app and its `SceneryKit` support
  library (repo root).
- **Ortho4XP** (the `dev` branch of
  [shizumaat/Ortho4XP-novemberlima](https://github.com/shizumaat/Ortho4XP-novemberlima)) —
  vendored as a squashed snapshot under `Ortho4XP/`. The full engine
  history remains in that fork; the snapshot's source commit is recorded
  in the vendoring commit message.

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
