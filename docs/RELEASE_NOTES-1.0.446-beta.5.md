# XPTerrainBuilder 1.0.446-beta.5

**Beta 5 — a prerelease for outside testers.** This round follows the owner's
sim reads of beta 4 at Atlanta, Seattle, Kansas City, Paris CDG, Lyon,
Frankfurt, Wellington, Hamad, Melbourne, Renton and Idaho Falls. Airside and
pavement grading is now solid almost everywhere; most of what remains is
fitting the terrain to custom scenery objects — bridges, tunnels, retaining
walls and multi-level stations. What needs testing most is still **airport
terrain and buildings**: build a tile with an airport you know well, taxi
around it in X-Plane 12, and tell us where the ground or the buildings look
wrong. Read *Known issues* before you start, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.446-beta.5/docs/TESTING-GUIDE.md)
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

## What changed since beta 4

**Buildings and scenery objects**

- Every object a scenery pack places at the airport is now read, not only
  those within a few kilometres of the airport's centre (Paris CDG,
  Frankfurt, Denver).
- A pack that places objects at an airport its own airport file does not
  list is now used for that airport (Paine Field KPAE from the Seattle pack).
- Companion packs read the airport's stands, so terminals stand on the apron
  (Paris CDG Terminal 1 no longer floats).
- One building's parts share one height (a Lyon roof no longer floats over
  its walls).
- Lyon's TGV station cut takes its floor from the pack's own track bed, and
  the station stays with the terminal.

**Tunnels, bridges and walls**

- Tunnel mouths stop just short of a road that crosses over them, and two
  carriageways merging into one tunnel get one ramp (Seattle S 188th St).
- Bridge edges over Atlanta's I-285 sit flush with the taxiway and runway
  beside them, and the floor between two bridges slopes from one to the other.
- Retaining walls: roads are cut back at a wall's faces and keep their own
  side's ground; the safety area no longer forms a cliff at the wall
  (Atlanta 27R).
- Paris CDG: road cuts and tunnels under taxiways and runways, with rail
  ramps at rail grades.
- Frankfurt: covered roads with a surveyed cut or a pack tunnel become
  tunnels.

**Airport terrain**

- Roads beside a runway are no longer lifted to the runway's height when the
  ground says otherwise (Atlanta).
- Lot fill along a lower level is cut away so the ground beside it sits at
  its own level (Kansas City).
- Coastline, base-raster gaps and apt.dat-only runways are handled at
  Hong Kong, Buffalo and others.

**Building many tiles**

- An airport that crosses two tiles built in the same run is now patched
  (Frankfurt was skipped).
- A tile that fails on a missing link and then builds on the retry is
  counted as built.

**The apps (Mac and the Qt app on Windows/Linux)**

- The Activity list is its own pane under the build boxes, with a standard
  divider you can drag; its height is remembered. The first tile queued is
  at the top.
- The map preview shows every tile's patch of an airport that spans tiles.
- Native Activity rows on the Mac, with per-tile progress.

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild.
  **Restart X-Plane after a build** — it caches objects. A copy of X-Plane's
  `Custom Scenery` is the safe setup for this beta.
- **A hand-edited patch keeps the pack's old object placement.** If you
  build with an edited patch, the pack's objects are not re-seated against
  the new ground and can float or sink. Switch the airport back to the
  auto patch to re-seat them.
- **Bridges over trenches are not finished.** Taxiway bridges can stand
  above the pavement or leave gaps at their edges, and some roads under them
  are not cut (Frankfurt, Atlanta I-285 edges, Paris CDG north of the T1
  road tunnels).
- **Frankfurt** is rougher than other large airports in this build: a
  highway under two taxiways is not yet in one cut, and one large
  bridge-and-tunnel object near the west of the field sits too high.
- **A divided road that crosses an airport** is not yet cut as one
  continuous trench (Paris CDG Terminal 2 road, Phoenix Sky Harbor Blvd).
- **Tunnel-mouth objects** are not yet graded into on three sides, and some
  pack ramp objects are not cut (Lyon between the station and the terminal).
- **Retaining walls:** the hill above a wall can stop short of the wall's
  top, and pavement can show at a wall's foot (Atlanta 27R).
- **Airports across a tile edge** can show a small step at the edge where
  the edge strip follows the raw elevation (Phoenix).
- Public roads on hills steeper than 10 % can end slightly above the ground
  where the graded area meets the surrounding terrain.
- **The largest airports take a while.** The airport stage runs a few seconds
  for a small field and up to about 30 minutes for the largest; the surface
  solve is the longest step. The progress line names the airport and its
  step; it has not hung.
- First builds download imagery, elevation and map data and are much slower
  than rebuilds.
- Windows and Linux builds are not code-signed; see the SmartScreen note
  below. macOS is Apple Silicon only.

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.446-beta.5-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.446-beta.5-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.446-beta.5-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.446-beta.5-linux.AppImage
./XPTerrainBuilder-1.0.446-beta.5-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.446-beta.5-linux.tar.gz
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
