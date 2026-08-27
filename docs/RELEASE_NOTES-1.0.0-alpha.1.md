# XPTerrainBuilder 1.0.0-alpha.1

**First public prerelease.** This is an alpha: it is not signed, not
notarized, and not feature-complete. Expect rough edges, and please report
what breaks.

## What XPTerrainBuilder is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs.

It is a fork and derivative of **[Ortho4XP](https://github.com/oscarpilote/Ortho4XP)
by Oscar Pilote**, whose engine does the actual scenery building and is
vendored here under `Ortho4XP/`. On top of it this project adds airport
terrain grading (FAA/EASA/ICAO-compliant regrading of paved surfaces
instead of draping them over raw DEM), meter-class airport elevation
insets from ~80 national lidar and bathymetry providers, per-tile
elevation detail levels, parallel tile builds, and a native macOS
front end.

## Platforms in Alpha 1

| Platform | Artifact | What you get |
| --- | --- | --- |
| **macOS** (Apple Silicon) | `XPTerrainBuilder-1.0.0-alpha.1-mac.zip` | Native SwiftUI app with the engine embedded (frozen, self-contained — no Python to install). Map-based tile picking, native build configuration, per-tile overrides, keychain-stored provider API keys, live build console. |
| **Windows** (x64) | `XPTerrainBuilder-1.0.0-alpha.1-win.zip` | Portable frozen Qt app. Build only. No installer — unzip and run. |
| **Linux** (x86_64) | `XPTerrainBuilder-1.0.0-alpha.1-linux.tar.gz` | Portable frozen Qt app. Build only. No installer, no package — untar and run. |

The Windows and Linux downloads are the engine's own PySide6 map-first GUI,
branded XPTerrainBuilder. The macOS-only SwiftUI front end is Apple-only
(SwiftUI/AppKit), so the two GUIs are not identical — see the limitations
below.

## Download and run

**macOS** — the app is **unsigned and not notarized**, so Gatekeeper will
refuse a normal double-click:

1. Unzip `XPTerrainBuilder-1.0.0-alpha.1-mac.zip`.
2. Move `XPTerrainBuilder.app` where you want it (e.g. `/Applications`).
3. **Right-click (or Control-click) the app → Open**, then confirm **Open**
   in the dialog. You only need to do this the first time; afterwards it
   launches normally.

Requires macOS 14 or later on an Apple Silicon Mac.

**Windows** — unzip anywhere and run `XPTerrainBuilder.exe`. SmartScreen
will warn about an unrecognized app: click **More info → Run anyway**. Keep
the folder contents together; the app is portable, not installed.

**Linux** — untar and run the launcher:

```sh
tar xzf XPTerrainBuilder-1.0.0-alpha.1-linux.tar.gz
cd XPTerrainBuilder
./XPTerrainBuilder
```

Built on Ubuntu 22.04. If Qt fails to start on a minimal system you may
need the usual X libraries (`libgl1`, `libegl1`, `libxkbcommon-x11-0`,
`libxcb-cursor0`).

## First run: choosing a data folder

On first launch you are asked where downloads and built scenery should
live. Everything writable — imagery downloads, elevation and OSM caches,
masks, finished tiles, config — goes there; the engine inside the app
bundle stays read-only. The default is `~/Ortho4XP` on macOS, and next to
the executable on Windows and Linux (portable layout). The choice is
remembered in `~/.ortho4xp/data_root.txt` and can be overridden with the
`ORTHO4XP_DATA_ROOT` environment variable.

Pick a folder with plenty of free space — ortho tiles are large.

## Known alpha limitations

- **No code signing or notarization** on any platform. Hence the
  right-click-Open dance on macOS and the SmartScreen warning on Windows.
- **macOS is Apple Silicon only.** No x86_64 (Intel) Mac build ships in
  this alpha.
- **No Linux AppImage yet** — only the portable tarball.
- **The Windows/Linux GUI is the Qt engine UI**, not the macOS app. It
  builds scenery, but it does not have the macOS app's native front-end
  features (its own map-based tile picker UI, in-app config-schema
  introspection, keychain key storage, and the app-side Doctor-style
  package tooling). Cross-platform parity is out of scope for this
  release cycle.
- **`moulinette` is gone.** The GUI's per-step mesh re-sort was an
  upstream binary shipped with no license terms at all; it has been
  removed from the tree, and that one step now reports that it is
  unavailable. Full tile builds are unaffected — `build_all` never used
  it. Likewise the unused proprietary `medit` mesh viewer has been
  dropped.
- Alpha means alpha: builds are long-running and defect reports on the
  generated terrain are welcome.

## Imagery terms — read this

XPTerrainBuilder ships tile templates for Esri World Imagery, Google,
Bing/VirtualEarth and Here. It does not, and cannot, grant you any right
to that imagery:

> XPTerrainBuilder downloads imagery from the provider you select. You are
> responsible for complying with that provider's terms of service. Most
> commercial providers prohibit bulk download and redistribution of derived
> imagery. Scenery you build is for your own use unless the provider's
> license says otherwise.

## Licensing

XPTerrainBuilder is not under a single license.

- The **application code** (the macOS SwiftUI app and its support library)
  is **MIT**.
- The **Ortho4XP engine** — the whole `Ortho4XP/` tree, including this
  project's `auto_patch/` and `o4_engine/` additions — is **GPL v3**. The
  full GPL text ships as `gpl.txt` in every artifact.
- Every download contains, at its root, `LICENSE`, `LICENSING.md`,
  `THIRD-PARTY-NOTICES.txt` (generated from `LICENSING.md`, covering
  Triangle, DSFTool, 7-Zip, nvcompress, osmium-tool, PySide6/Qt and the
  bundled Python packages), `gpl.txt` and `copyright.txt`.
- A **source archive** of the exact tagged tree the binaries were built
  from is attached to this release, satisfying the GPL v3 source offer
  independently of this repository's continued availability.
- **Free-of-charge distribution only.** The bundled Triangle mesh
  generator (Jonathan Shewchuk) permits redistribution only where no
  compensation is received; commercial distribution requires direct
  arrangement with its author. You may redistribute this release, but only
  free of charge. Triangle's sources ship with each artifact
  (`Triangle-src/` on macOS, `_internal/Ortho4XP_Data/Utils/src/` on
  Windows and Linux) and are modified — `Triangle4XP` is Oscar Pilote's
  adaptation.

Full per-component detail: **[LICENSING.md](../LICENSING.md)**
([on GitHub](https://github.com/shizumaat/XPTerrainBuilder/blob/main/LICENSING.md)).

Scenery you build is **not** a covered work — your `.dsf` and mesh output
is yours. Per Oscar Pilote's statement, please credit Ortho4XP if you
distribute scenery commercially. The binding constraint on your output is
the imagery provider's terms, above, not this license.
