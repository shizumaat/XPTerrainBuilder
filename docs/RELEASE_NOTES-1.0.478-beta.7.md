# XPTerrainBuilder 1.0.478-beta.7

**Beta 7 — a prerelease for outside testers.** This round is about **reading
custom airport packs more faithfully**: tunnels, trenches, split-level
terminals and decks are measured against what X-Plane actually draws, a
runway's design letter now comes from the airport's own data, and the app can
tidy a pack (old X-Plane 11 trees, flattening, draped photos that hide our
imagery) from one checked list. It also adds elevation sources for the Arctic
and Iceland and a set of patch-editor tools. What needs testing most is still
**airport terrain around bridges, tunnels and walls** — read *Known issues*
first, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.478-beta.7/docs/TESTING-GUIDE.md)
for a first build, step by step.

## Before your first build

1. **First downloads take longer.** Where available, XPTerrainBuilder downloads high-resolution lidar elevation for airports, and bathymetry along coastlines so reefs and atolls are covered automatically. Both are cached, so only the first build of an area waits for them.
2. **OSM data comes from regional extracts.** The public OSM servers have been busy and slow, so XPTerrainBuilder downloads a regional OSM extract and pulls out what each airport needs. This is more reliable, but the first download depends on your connection speed.
3. **A big airport's first auto-patch can take up to 30 minutes.** On tiles with large airports and detailed scenery packs installed, auto-patch reads every object and polygon, and grades all the airport's pavement to FAA or ICAO rules.
4. **Edit the patch from the map.** Once a tile is built, zoom in on the airport in the map view to see the generated patch, then adjust its elevations or shapes.

## What this is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs. It additionally
regrades paved airport surfaces to FAA/EASA/ICAO geometry instead of draping
them over raw elevation data, and reseats custom airport objects onto the
surface it built.

It is a fork and derivative of
**[Ortho4XP](https://github.com/oscarpilote/Ortho4XP) by Oscar Pilote**.

## What changed since beta 6

**Custom airport packs**

- A pack's below-grade objects (trenches, pits, split-level terminals) are
  judged against the pack author's own ground, so flat apron tiles are no
  longer read as trench floors (Kansas City: 148 false trench cells → 0).
- Tunnel mouths are seated as entrances, with no pad minted from the mouth
  object (Vienna).
- Cut shells a pack uses to represent a trench are hidden and kept out of the
  surface solve (Athens).
- **Pack adjustments** — one checked list in both apps: remove a pack's
  flattening, hide draped photos that cover our imagery (only a grid of
  similarly named photo tiles that extends past the airport boundary is
  hidden; everything else is kept), and upgrade old flat X-Plane 11 trees to
  X-Plane 12 3D trees and ground planters, with nothing over 1 m in runway
  and taxiway strips.
- Packs whose DSF named object files that did not exist ("torn" packs) are
  repaired; definitions with a leading-slash path are kept.

**Airport terrain**

- A runway's design letter (strip and safety-area width) comes from the
  airport's own apt.dat markings and ramp sizes instead of its pavement width
  (Steamboat Springs: ±76 m → ±23 m).
- Runway ends stand near the published field elevation where the elevation
  data is old (St Helena, BGGH); old-DEM fill gets road terraces.
- Lidar is never treated as old elevation data (fixes a Whitehorse / Los
  Angeles regression in an earlier test build).
- Los Angeles: split-level pits follow the terminal's building plan.
- Inset elevation is stacked by provider priority; coastal coverage no longer
  counts open sea.

**Elevation sources**

- ArcticDEM 2 m (Greenland, Svalbard, Faroes and the Arctic), IslandsDEM 2 m
  (Iceland), Hamburg 1 m automatic, Schleswig-Holstein 1 m fixed.

**The app**

- Patch editor: insert a tunnel ramp from the map, rotate a shape with
  Option-drag, change a pavement shape's class and regrade, and an object
  inspector with top and bottom elevations.
- "Use auto patch" is disabled only for the tile being built.
- A warning when another pack's base mesh hides one of our tiles in
  `scenery_packs.ini`.

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild, so
  any other edits you made to a pack's DSF are replaced. **Restart X-Plane
  after a build** — it caches objects. A copy of X-Plane's `Custom Scenery`
  is the safe setup for this beta. **Restore originals** in the library puts
  a pack back.
- **Bridges and tunnels are better but not finished.** Athens and Los Angeles
  still have trench and tunnel cuts that do not match the pack's objects.
- **Kansas City:** a pit at the south border trim and a basin beside one
  retaining wall are cut too deep, and small hanging art pieces in the main
  terminal float above it. The airport also takes about 25 minutes to
  auto-patch, much longer than airports of its size.
- **Calvi (Aerosoft, 2016):** two of the pack's own lights are malformed and
  turn the valley white in X-Plane 12. This is in the pack, not the build;
  repairing it automatically is planned.
- **The largest airports take a while.** The airport stage runs a few seconds
  for a small field and up to about an hour for the largest; the surface
  solve is the longest step. The progress line names the airport and its
  step; it has not hung.
- First builds download imagery, elevation and map data and are much slower
  than rebuilds.
- Windows and Linux builds are not code-signed; see the SmartScreen note
  below. macOS is Apple Silicon only.

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.478-beta.7-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.478-beta.7-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.478-beta.7-linux.AppImage` (or `…-linux.tar.gz`) |

**macOS.** The app is signed with a Developer ID and notarized by Apple, so
there is nothing to bypass.

1. Unzip the download.
2. Move `XPTerrainBuilder.app` where you want it (e.g. `/Applications`).
3. Double-click it. **No Gatekeeper dialog is expected.**

If a dialog does appear — "cannot be opened because the developer cannot be
verified", "damaged", or any unverified-developer warning — the build you
have is not the signed one. **Report it** with the exact file name you
downloaded, rather than working around it.

macOS builds are **arm64 (Apple Silicon) only**. There is no Intel build.
macOS will ask once for access to removable volumes if your X-Plane or data
folder is on an external drive; allow it, or the build waits forever.

**Windows.** Unzip anywhere and run `XPTerrainBuilder.exe`. The app is not
code-signed yet, so SmartScreen warns about an unrecognized app: click
**More info → Run anyway**. Keep the folder contents together — the app is
portable, not installed.

**Linux.** Download the **AppImage**, make it executable, and run it:

```sh
chmod +x XPTerrainBuilder-1.0.478-beta.7-linux.AppImage
./XPTerrainBuilder-1.0.478-beta.7-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.478-beta.7-linux.tar.gz
cd XPTerrainBuilder && chmod +x XPTerrainBuilder && ./XPTerrainBuilder
```

On a minimal system install the prerequisites first (both artifacts need
them):

```sh
sudo apt-get install -y libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
  libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 p7zip-full
```

`p7zip-full` is required, not optional: installing scenery overlays
extracts 7-Zip archives, and the app refuses that step without it.

## The two folders

XPTerrainBuilder keeps everything writable in **one data folder**, and
installs finished scenery into **your X-Plane folder**. It asks for both on
first run.

- **Data folder** — imagery downloads, elevation and OSM caches, masks,
  built tiles, configuration, logs. Default `~/XPTerrainBuilderData` on
  every platform, deliberately outside the app so that updating the app is
  just replacing the app. Already have a folder from alpha 1/2 or from
  Ortho4XP? Point the chooser at it; existing downloads and tiles are used
  as they are.
- **X-Plane folder** — your X-Plane 12 installation. It must contain
  `Custom Scenery` and `Resources/default data/CIFP`; the app checks and
  tells you what is missing. Finished tiles are installed into
  `Custom Scenery`, and the airport data there is what the grading is
  computed against.

**Disk space.** Budget **3–8 GB per 1°×1° tile at zoom level 16** (measured:
2.5 GB for a mostly-water tile, 7.5 GB for a dense land tile), more at
higher zoom, plus several GB of shared elevation and OSM cache and a few GB
of temporary space while a build runs. Put the data folder on a drive with
room to grow.

## How to report a problem

On a failed tile, **Report this problem** fills most of this in for you. Otherwise open an issue at <https://github.com/shizumaat/XPTerrainBuilder/issues> and
include, in this order:

1. **The version triple.** `VERSION.txt` at the root of your download has
   three lines — `app=`, `engine=`, `sha=`. Paste all three. The same three
   are in the app: **XPTerrainBuilder ▸ About XPTerrainBuilder** on macOS,
   **Help ▸ About** on Windows and Linux.
2. **Your platform** (macOS / Windows / Linux and version), **what you
   did**, which airport (ICAO) or tile coordinates, the imagery provider,
   and which custom scenery pack the airport comes from, if any.
3. **The log.**
   - macOS: `~/Library/Logs/XPTerrainBuilder/engine-stderr.log`
   - Windows and Linux: `<data folder>/logs/engine-stderr.log`
   - plus the build console pane, copied (it has a copy button).
4. **Screenshots** from the sim of anything visibly wrong, with the airport
   and the rough position (latitude/longitude from the map, or the taxiway
   or stand name).
