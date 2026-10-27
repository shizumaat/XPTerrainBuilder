# XPTerrainBuilder 1.0.428-beta.4

**Beta 4 — a prerelease for outside testers.** This round follows the owner's
sim reads of beta 3 at Kansas City, Paris CDG, Atlanta, Lima, Cairo and
Victoria: multi-level terminals sit on their apron with a lower pad for the
groundside storey, bridges are recognised and seated by class, every road in
the airport area is graded, and building many tiles at once no longer
freezes the Mac. What needs testing most is still **airport terrain and
buildings**: build a tile with an airport you know well, taxi around it in
X-Plane 12, and tell us where the ground or the buildings look wrong. Read
*Known issues* before you start, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.428-beta.4/docs/TESTING-GUIDE.md)
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

## What changed since beta 3

**Buildings and scenery objects**

- Connected buildings, roads and bridges move as one group. A group that
  touches airside is seated by its airside edge nearest the jetways and
  stands, so the terminal sits on the apron; when parts of a group must give
  way, airside wins (Kansas City, Paris CDG Terminal 2, Atlanta east terminal).
- Two-level terminals get two pads: the groundside storey stands on its own
  lower pad, and roads over that lower level follow it (Kansas City, Paris CDG).
- Bridges are seated by class: taxiway and runway hard decks sit flush with the
  apron; road overpasses meet the ground at the end nearer it (Paris CDG,
  Kansas City).
- Interior and contents objects stay inside their building; decks and their
  edge pieces no longer separate.
- A pack's objects are now always written: an object split across a tile edge
  no longer makes the whole pack fail to update (Dallas–Fort Worth).
- Ground plates on real slopes are free-standing, each piece on its own ground
  (Lyon LFLL).

**Airport terrain**

- Every mapped road inside the airport boundary, plus 50 m outside it, is
  graded and blends into the terrain at the edge, without moving runways,
  taxiways or aprons.
- Runway thresholds come from the airport data at any displaced length; an
  end with no matching CIFP record follows the elevation data, never 0 m
  (Victoria CYYJ runway 32).
- National elevation data is used only inside its own country; elsewhere the
  best global data is used (Victoria CYYJ now uses Canada's HRDEM; France uses
  IGN RGE ALTI 1 m).
- A narrow gap between a runway and an adjoining apron is no longer graded as
  runway shoulder, removing small runway steps (Cairo HECA).
- Pad and apron shapes can no longer fold over themselves and be silently
  dropped from the mesh (the Kansas City apron ridge).
- A patch that crosses a tile edge no longer leaves raw-elevation bumps inside
  the airport (Lima SPJC taxiway).
- Points closer than half a metre are now measured in metres when merged.

**Building many tiles**

- One resource manager for the whole machine: tiles start only as cores and
  memory allow, the rest wait in the queue, and the build runs at normal
  priority. Selecting a whole continent no longer freezes the Mac.

**The apps (Mac and the Qt app on Windows/Linux)**

- One layout in both apps: Detail lives in Settings, "Sharper airports" is the
  default preset, and Custom Scenery changes are picked up automatically (the
  refresh button is gone).
- The Qt app shares the Mac app's data folder and gains Data Folder,
  Application, Build Engine and Provider Accounts settings.
- The map shows the cursor's `lat, lon` and the height under it (the built
  mesh, or the elevation data on unbuilt tiles).
- Airport markers appear at launch; one empty patch file no longer hides every
  patch on its tile; built tiles show their imagery provider.
- The Activity panel shows each tile's progress bar right under its title; the
  patch editor's buttons read "Undo" and "Save".

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild.
  **Restart X-Plane after a build** — it caches objects. A copy of X-Plane's
  `Custom Scenery` is the safe setup for this beta.
- **Bridge approaches are not yet graded.** A bridge deck is seated correctly,
  but the ground at its far end is not yet raised or lowered to meet it, and
  the trench under taxiway bridges is not yet cut everywhere (Paris CDG,
  Kansas City).
- **Roofed (cut-and-cover) pack tunnels are not yet recognised**, so the cut
  follows the map's tunnel line instead of the pack's tunnel (London Heathrow
  apron tunnels, Luton).
- **Two-level terminals:** the lower level does not yet extend across every
  road corridor or to the end of every retaining wall (Paris CDG Terminal 2,
  Atlanta east terminal). A few buildings still float, and one garage ramp at
  Kansas City sits slightly above its garage.
- Only an airport's own scenery pack is reseated; other packs that place
  objects at the airport (parked cars, interiors) are not yet adjusted.
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
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.428-beta.4-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.428-beta.4-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.428-beta.4-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.428-beta.4-linux.AppImage
./XPTerrainBuilder-1.0.428-beta.4-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.428-beta.4-linux.tar.gz
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
