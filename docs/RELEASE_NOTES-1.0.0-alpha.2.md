# XPTerrainBuilder 1.0.0-alpha.2

**Second public prerelease.** This is an alpha: it is not signed, not
notarized, and not feature-complete. Expect rough edges, and please report
what breaks.

## Changes since alpha.1

- **All three platforms now ask where your data should live on first run**,
  defaulting to `~/XPTerrainBuilderData`. Windows and Linux previously kept
  their data next to the executable; they no longer do. Your imagery,
  elevation and OSM caches, masks and built tiles now sit outside the app
  folder on every platform, so updating XPTerrainBuilder is a drop-in
  replacement of the app — nothing you downloaded or built is disturbed.
- **The Windows/Linux app catches up to the macOS app**: airport markers
  on the map (Global Airports plus your custom packs, with install
  status), awareness of other installed scenery (coverage outlines on the
  map, per-tile info, a View ▸ Scenery filter), one-click cleanup of
  mixed imagery sources (moves foreign files to the trash after
  confirmation), a map basemap provider chosen independently of the build
  imagery, one-click migration of legacy per-tile configs to current
  defaults (imagery, zoom and zones kept), and an auto-install toggle
  that installs finished tiles into X-Plane as they complete.

## What XPTerrainBuilder is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs.

It is a fork and derivative of **[Ortho4XP](https://github.com/oscarpilote/Ortho4XP)
by Oscar Pilote**.

## Key Features
- New UI that brings all functionality into a single window, along with a reorganized and searchable config window
- Terrain grading (FAA/EASA/ICAO-compliant regrading of paved surfaces
instead of draping them over raw DEM) to create highly detailed OSM patch files automatically tailored specifically to the airports installed in your X-Plane Custom Scenery. 
- Custom airport modification: for airports with custom objects, XPTerrainBuilder will automatically split and reseat objects to try and ensure there are no floating or sunken buildings. 
- Improved OSM data downloads and caching
- Meter-class airport elevation insets from ~80 national lidar and bathymetry providers
- Per-tile elevation detail levels
- parallel tile builds
- Native macOS app with everything included bundled for download and double-click to run.


## Platforms in Alpha 2

| Platform | Artifact | What you get |
| --- | --- | --- |
| **macOS** (Apple Silicon) | `XPTerrainBuilder-1.0.0-alpha.2-mac.zip` | Native SwiftUI app with the engine embedded (frozen, self-contained — no Python to install). Map-based tile picking, native build configuration, per-tile overrides, keychain-stored provider API keys, live build console. |
| **Windows** (x64) | `XPTerrainBuilder-1.0.0-alpha.2-win.zip` | Portable frozen Qt app (self-contained — no Python to install). Map-based tile picking, per-tile overrides, searchable settings, setup wizard, live build console. No installer — unzip and run. |
| **Linux** (x86_64) | `XPTerrainBuilder-1.0.0-alpha.2-linux.tar.gz` | Same Qt app as Windows. No installer, no package — untar and run. |

The Windows and Linux downloads are the engine's own PySide6 map-first GUI,
branded XPTerrainBuilder. It is maintained alongside the macOS app and the
two are close to feature parity — the remaining differences are listed in
the limitations below.

## Download and run

**macOS** — the app is **unsigned and not notarized**, so Gatekeeper will
refuse a normal double-click:

1. Unzip `XPTerrainBuilder-1.0.0-alpha.2-mac.zip`.
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
tar xzf XPTerrainBuilder-1.0.0-alpha.2-linux.tar.gz
cd XPTerrainBuilder
./XPTerrainBuilder
```

Built on Ubuntu 22.04. If Qt fails to start on a minimal system you may
need the usual X libraries (`libgl1`, `libegl1`, `libxkbcommon-x11-0`,
`libxcb-cursor0`).

## First run: choosing a data folder

On first launch — on macOS, Windows and Linux alike — you are asked where
downloads and built scenery should live. Everything writable — imagery
downloads, elevation and OSM caches, masks, finished tiles, config — goes
there; the engine that ships inside the app stays read-only. The default is
`~/XPTerrainBuilderData` on every platform, deliberately outside the app
folder so that installing a new version is just a matter of replacing the
app. The choice is remembered in `~/.ortho4xp/data_root.txt` and can be
overridden with the `ORTHO4XP_DATA_ROOT` environment variable, which wins
over both.

Already have a folder from a previous run (or from Ortho4XP itself)? Point
the chooser at it — existing downloads, tiles and settings are used as-is.

Pick a folder with plenty of free space — ortho tiles are large.

## Known alpha limitations

- **No code signing or notarization** on any platform. Hence the
  right-click-Open dance on macOS and the SmartScreen warning on Windows.
- **macOS is Apple Silicon only.** No x86_64 (Intel) Mac build ships in
  this alpha.
- **No Linux AppImage yet** — only the portable tarball.
- **The Windows/Linux GUI is the engine's own Qt app**, maintained in
  parallel with the macOS app and at feature parity on everything that
  matters: the same map-based tile picking with airport markers and
  scenery awareness, single-window layout, searchable settings (the two
  UIs share one settings registry), per-tile overrides, batch queueing
  into a live run, build ETA, secure API-key storage (Credential Locker /
  Secret Service), custom-airport handling, imagery cleanup and
  auto-install. It also has a few tools of its own the macOS app doesn't
  (setup wizard, coral-reef bathymetry download, X-Plane overlay-folder
  link). Zone editing is not available in either UI yet.
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
is yours. If you distribute that scenery commercially, please credit
**Ortho4XP** (per Oscar Pilote's statement) **and XPTerrainBuilder** — the
XPTerrainBuilder credit applies whenever the scenery includes our
auto-patch custom airport terrain, i.e. the graded airport surfaces. The
binding constraint on your output is the imagery provider's terms, above,
not this license.
