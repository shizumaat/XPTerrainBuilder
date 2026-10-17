# XPTerrainBuilder 1.0.400-beta.2

**Beta 2 — a prerelease for outside testers.** The airport terrain now follows
the published runway and taxiway design standards (FAA AC 150/5300-13B, ICAO
Annex 14), and there is an in-app editor for the airport patches the app
builds. What needs testing most is still **airport terrain**: build a tile that
contains an airport you know well, fly or taxi there in X-Plane 12, and tell us
where the ground or the buildings look wrong. Read *Known issues* before you
start, and the
[testing guide](https://github.com/shizumaat/XPTerrainBuilder/blob/v1.0.400-beta.2/docs/TESTING-GUIDE.md)
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

## What changed since beta 1

**Airport terrain follows the design standards**

- The graded ground around each runway (the runway strip and the safety area
  past each end) now has the size and slopes the FAA and ICAO standards give
  for that runway's size and approach type. Approach type is read from the
  scenery's runway markings and the navigation data, so the ground past a
  precision runway's end is graded to the stricter rules.
- Past a runway end the graded area runs the full safety-area length, but it
  stops at the top of a real drop (an escarpment) instead of filling over it.
  The edge of the graded area meets the natural ground directly; a steep edge
  there is how real runway fills look.
- Taxiway strips are measured from the taxiway centreline, as the standards
  do, so the graded band beside a taxiway is the right width. Ground beside
  an apron edge now meets that edge flush.
- Taxiway slopes and how sharply they change grade follow the standards by
  taxiway size; taxiways meet runways and held-level aprons without steps.
- The ground past an FAA runway end stays under the approach surface.
- End-around taxiways are recognised by the FAA 1,500 ft rule and sit where
  good lidar shows them.
- Terminal buildings served by jetways have their pads extended under the
  jetways.

**Airport terrain: other improvements**

- Building pads are flat right out to the building's outline, and several
  buildings standing on one apron sit at that apron's level.
- Roads and parking lots that touch a building are joined to its pad; a road
  that cannot reach a pad within its slope limit steepens instead of leaving
  a step.
- Paved areas a scenery pack draws only as a ground texture or object —
  parking lots, cargo aprons, paving between buildings — are recognised and
  graded. Pavement from more than one scenery pack at one airport is graded as
  one airport.
- Elevated ramps carry their road grade past the landing, so the ground no
  longer drops away right after a ramp meets it. Tunnel mouths are cut 7.5 m
  deep. Covered ground under a runway over a road cut, walled tunnel mouths
  and a pack's retaining walls are kept as real steps.
- Canopies on posts, roofs, multi-part buildings and covered parking hold
  together at one level instead of separating into floating pieces.
- The surface solve is more stable: a fix in one place no longer shifts the
  ground elsewhere, and concave pavement shapes are triangulated exactly.

**Elevation data**

- Elevation is layered around each airport: 1 m at the airport where it
  exists, 10 m out to 10 km, 30 m out to 20 km, base data beyond.
- More US lidar: point-cloud survey data is used where USGS holds it and no
  1 m raster exists.

**The apps**

- **Patch editor and 3D preview** (macOS and Windows/Linux): open an airport
  patch the app built, move or raise nodes and shapes, and save it as your own
  edited patch, which the next build uses. A separate 3D window shows the
  patch with the pack's buildings as grey massing; drag to look around, and use
  X-Plane's view keys to move. Saving is instant.
- **Report this problem** on a failed tile copies a redacted report and opens a
  prefilled GitHub issue; **Save report file** writes it for sending by other
  means.
- A tile that fails shows its options straight away, without waiting for the
  others. A Custom Scenery link that points at an unmounted drive is named,
  and you are offered a local build instead.
- The progress list shows which airport search picked each tile; Stop stops.

**Fixes**

- The app could fail to start, or lose elevation and imagery providers, on
  Windows set to Japanese, Chinese, Korean and some other languages.
- Elevation downloads that failed on Windows in beta 1 are fixed.
- Tunnels built where none exist are no longer cut; missing real tunnel mouths
  are back.
- The colour harmoniser no longer draws straight seam lines between textures.

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.400-beta.2-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.400-beta.2-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.400-beta.2-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.400-beta.2-linux.AppImage
./XPTerrainBuilder-1.0.400-beta.2-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.400-beta.2-linux.tar.gz
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
