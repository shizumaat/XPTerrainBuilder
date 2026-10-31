# XPTerrainBuilder 1.0.454-beta.6

**Beta 6 — a small prerelease for outside testers.** This round is mostly about
**bridges**: taxiway bridges whose deck you drive on ("hard decks") now sit
flush with the taxiway, and the road beneath them is cut down to pass under.
It also fixes several regressions found after beta 5 and makes large
multi-airport tiles build faster. What needs testing most is still **airport
terrain around bridges, tunnels and walls**: taxi across a bridge in X-Plane 12
and tell us where the ground or the road beneath looks wrong. Read *Known
issues* before you start, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.454-beta.6/docs/TESTING-GUIDE.md)
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

## What changed since beta 5

**Bridges and tunnels**

- A taxiway bridge with a hard deck now sits flush with the taxiway at both
  ends (within a few centimetres), and the road under it is cut down to pass
  beneath it (Nashville taxiway L).
- Where the bridge object has its own walls, the trench is cut wall to wall
  so the walls are fully exposed. Bridges without walls get a road-width cut
  with banks.
- The road under a flat deck gets at least 5 m of clearance, or the surveyed
  road where that is deeper.
- Bridges are read before the surface is solved, including road overpasses,
  which now sit on the road beneath them instead of floating.
- Flat slab bridges whose authors flagged only the slab's edges are now
  recognised (Houston).
- A runway over a road trench keeps its cross-slope (fixes a Paris CDG
  regression that dropped the whole airport patch).

**Airport terrain**

- Grand Canyon: a road no longer cuts deep below the terrain.
- A runway strip follows the runway's adjusted grade (1Z1).
- Houston: a stray part of one scenery object far below ground no longer
  drags the terrain down.

**Speed and the app**

- On tiles with many airports, a large airport gets the machine's cores back
  once its smaller neighbours finish (Frankfurt), and building the airport
  map is faster. The finished scenery is unchanged.
- The app download is smaller: about 394 MB instead of 1.2 GB.
- Re-signing the app no longer forces every airport patch to rebuild.
- The tile info pane's "Built by" shows the app version.
- Patch editing: selecting a node takes focus from the search field, so
  Delete removes it; ⌘S / Ctrl+S saves the patch.

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild, so
  any other edits you made to a pack's DSF are replaced. **Restart X-Plane
  after a build** — it caches objects. A copy of X-Plane's `Custom Scenery`
  is the safe setup for this beta.
- **A hand-edited patch keeps the pack's old object placement.** Switch the
  airport back to the auto patch to re-seat its objects.
- **Bridges are better but not finished.** At Nashville only the taxiway L
  pair is signed off; other bridges there still need work. At Houston every
  taxiway bridge is now recognised, but the ground around them still has
  problems. At Paris CDG the bridges are seated, but under several of them
  the cut does not run all the way through, and the central corridor is not
  yet one straight cut down to the lower level.
- **Frankfurt** is still rough around its highway and rail bridges.
- **Tunnel-mouth objects** are not yet graded into on three sides
  (Nashville, Lyon).
- **Retaining walls:** the hill above a wall can stop short of the wall's
  top (Atlanta 27R).
- **Airports across a tile edge** can show a small step at the edge (Phoenix).
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
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.454-beta.6-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.454-beta.6-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.454-beta.6-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.454-beta.6-linux.AppImage
./XPTerrainBuilder-1.0.454-beta.6-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.454-beta.6-linux.tar.gz
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
