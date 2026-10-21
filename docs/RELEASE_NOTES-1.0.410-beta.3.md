# XPTerrainBuilder 1.0.410-beta.3

**Beta 3 — a prerelease for outside testers.** This round follows the owner's
sim reads of betas 1–2 at a dozen custom airports: buildings stand where their
scenery authors put them, retaining walls and terminal storeys are read from
the scenery, tunnels and roads near runways behave, and several airports that
previously got no graded patch now build. What needs testing most is still
**airport terrain**: build a tile that contains an airport you know well, taxi
around it in X-Plane 12, and tell us where the ground or the buildings look
wrong. Read *Known issues* before you start, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.410-beta.3/docs/TESTING-GUIDE.md)
for a first build, step by step.

## What this is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs. It additionally
regrades paved airport surfaces to FAA/EASA/ICAO geometry instead of draping
them over raw elevation data, and reseats custom airport objects onto the
surface it built.

It is a fork and derivative of
**[Ortho4XP](https://github.com/oscarpilote/Ortho4XP) by Oscar Pilote**.

## What changed since beta 2

**Buildings and scenery objects**

- Multi-level terminals: a terminal built into a slope (groundside a storey
  higher than airside) is read from the pack's objects, and the forecourt
  meets the terminal's upper level (Horta LPHR).
- Parking-garage decks and terminal interiors that stand on the terminal's own
  lower structure stay with the terminal instead of dropping to the ground;
  an elevated roadway's lower deck sits at ground level (Atlanta east terminal).
- Objects placed at absolute altitudes (OBJECT_MSL) are seated by their own
  feet, one body at a time.
- Retaining walls supplied by a pack are read as vertical cuts: the lower
  level runs flat to the foot of the wall and the upper level stays flat at
  its top (Atlanta east terminal).
- The draped apron, taxiway and shoulder layers some packs author (FS2XPlane
  conversions) are read as pavement; a fully transparent "hard surface"
  polygon some packs lay over the whole field for wheel physics is no longer
  taken for pavement (Lisbon LPPT).

**Airport terrain**

- Runway shoulders take their width from the airport data; taxiway entrances
  across the shoulder are graded as taxiway.
- A road through the outer graded band is cut out of it and follows its own
  ground (Los Angeles runway 06R end).
- Runway-end graded zones and adjacent ground stop at the water's edge
  (Kotzebue KOTH).
- Flat-airport levelling no longer flattens hills beyond the airport: ground
  more than 5 m above the airport outside its own surfaces keeps its real
  height (Macau VMMC, Hong Kong VHHH).
- Frankfurt (EDDF) terminal 1 no longer mints a spurious lower level.

**Reliability**

- Airports that previously got no patch now build: Frankfurt (EDDF), Cairo
  Almaza (HEAZ), Charlotte (KCLT), Karlsruhe/Baden-Baden (EDTK).
- When the configured base elevation source has no data for a land cell
  (Viewfinder has no file for mainland Shetland), the next-ranked source is
  used and the log says so, instead of refusing the tile (Sumburgh EGPB).

**Speed**

- Large airports build faster: road-height answers are computed in one pass,
  the pad roads' derive runs beside the gap stage, and Doha's (OTHH) contact
  tests run batched.

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild.
  **Restart X-Plane after a build** — it caches objects. A copy of X-Plane's
  `Custom Scenery` is the safe setup for this beta.
- **Taxiway bridges over roads supplied as pack objects** (Atlanta, Frankfurt,
  Los Angeles) are not yet cut as a full trench: the road under them can pull
  the bridge down, or a short ramp shows at the bridge face.
- **Where an airport pack ships no pavement in its airport data** (Atlanta's
  Nimbus pack), the app borrows X-Plane's global pavement outlines, which can
  cross the pack's walls; a sliver of pavement then stays at the upper level
  past a retaining wall.
- Elevated rail pieces at Los Angeles can sit at slightly different heights.
- **The largest airports take a while.** The airport stage runs a few seconds
  for a small field and up to about 20 minutes for the largest (Cairo). The
  progress line names the airport and its step; it has not hung.
- First builds download imagery, elevation and map data and are much slower
  than rebuilds.
- Windows and Linux builds are not code-signed; see the SmartScreen note
  below. macOS is Apple Silicon only.

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.410-beta.3-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.410-beta.3-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.410-beta.3-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.410-beta.3-linux.AppImage
./XPTerrainBuilder-1.0.410-beta.3-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.410-beta.3-linux.tar.gz
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

## Known issues

- **A build edits custom airport scenery packs.** To stand a pack's objects
  on the graded surface, the app rewrites object placements inside that
  pack's folder under `Custom Scenery`. It keeps the originals beside them
  as `.anchor_bak` files and restores from them before every rebuild.
  **Restart X-Plane after a build** — it caches objects. A copy of X-Plane's
  `Custom Scenery` is the safe setup for this beta.
- **Some buildings still float on one side or come apart slightly**, most
  visibly at Aspen (KASE): a few buildings on sloping ground have no pad, the
  tower top and one hangar separate a little, and the Atlantic FBO's
  forecourt does not yet slope up to meet it. Some flat slabs around large
  terminals still float (Cairo).
- **Landside areas below retaining walls** (Atlanta's east terminal) and some
  roads classed as apron (Charlotte) are not yet graded to their lower level.
- **The largest airports take a while.** The airport stage runs a few seconds
  for a small field and up to about 20 minutes for the largest (Cairo). The
  progress line names the airport and its step; it has not hung.
- Opening the patch editor at a very large airport can pause while the pack's
  buildings load.
- First builds download imagery, elevation and map data and are much slower
  than rebuilds.
- Windows and Linux builds are not code-signed; see the SmartScreen note
  above. macOS is Apple Silicon only.
