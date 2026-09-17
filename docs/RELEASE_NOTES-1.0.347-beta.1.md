<!--
DRAFT (session, 2026-09-17) for the owner to edit. This comment is not rendered.
The release job REQUIRES this file for the tag v1.0.347-beta.1 and refuses a tag
whose number differs from Sources/XPTerrainBuilder/Resources/VERSION. If a new
local app build moves VERSION before tagging, rename this file to match
(docs/RELEASE_NOTES-<app-build>-beta.1.md) and update the artifact names below.
-->
# XPTerrainBuilder 1.0.347-beta.1

**Beta 1 — a prerelease for outside testers.** This is the first build meant
for people other than its author. It runs on macOS, Windows and Linux. What
needs testing most is the part no other ortho tool does: **airport terrain**.
Build a tile that contains an airport you know well, fly or taxi there in
X-Plane 12, and tell us where the ground looks wrong. Expect rough edges; see
*Known issues* before you start, and read the
[testing guide](TESTING-GUIDE.md) for a first build, step by step.

## What this is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs. It additionally
regrades paved airport surfaces to FAA/EASA/ICAO geometry instead of draping
them over raw elevation data, and reseats custom airport objects onto the
surface it built.

It is a fork and derivative of
**[Ortho4XP](https://github.com/oscarpilote/Ortho4XP) by Oscar Pilote**.

## What changed since alpha 2

**Airports**

- A new airport grading engine. Runways, taxiways and aprons are solved as
  one surface under the published slope and step limits for the airport's
  rule set (FAA or ICAO), following the real ground's long-wave shape rather
  than flattening it. Runways keep their crown; taxiways climbing a hill are
  cut into it instead of being filled above it.
- Custom scenery objects are reseated on the surface that was built:
  terminals, hangars, jetways, fences and light poles stand on their own
  ground instead of floating or sinking. Sunken features modelled by a
  scenery pack — basements, underpasses, road tunnels under taxiways,
  bridge decks, sea walls — are cut or carried accordingly.
- Airports with no meaningful relief are built as a clean flat site; open
  water beside an airport stays water.
- An airport that cannot be graded no longer takes the tile down with it
  silently: the app names the airport and the stage the moment it fails.

**Building tiles**

- The app now asks for your **X-Plane folder** on first run and will not
  start a build without a valid one. Previously a build could "succeed" with
  every airport draped on raw elevation because the airport data folder was
  never found.
- New elevation sources, including 1 m lidar where national services offer
  it, decoded correctly in the packaged app on all three platforms.
- Stop and resume individual tiles in a running batch; finished tiles can be
  installed into X-Plane automatically.
- A tile folder that points at an unplugged drive is now reported as exactly
  that, not as a permissions problem.
- Missing or failed imagery downloads are stated at the end of a tile with a
  count, instead of leaving blank textures without a word.

**The apps**

- **macOS:** signed with a Developer ID and notarized by Apple. It opens
  with no security dialog.
- **Windows and Linux:** the same engine and the same settings as the Mac
  app, a live per-airport failure line, a persistent engine log for bug
  reports, and an About box that identifies the build. The tile-details
  panel no longer clips on Windows. **Linux** now ships as a single
  AppImage (the tar.gz remains).
- Every download identifies itself: `VERSION.txt` at its root carries the
  app version, the engine version and the commit.

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-1.0.347-beta.1-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-1.0.347-beta.1-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-1.0.347-beta.1-linux.AppImage` (or `…-linux.tar.gz`) |

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
chmod +x XPTerrainBuilder-1.0.347-beta.1-linux.AppImage
./XPTerrainBuilder-1.0.347-beta.1-linux.AppImage
```

If your system has no working FUSE, add `--appimage-extract-and-run`. The
**tar.gz** is the same build as a plain folder:

```sh
tar xzf XPTerrainBuilder-1.0.347-beta.1-linux.tar.gz
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

Open an issue at <https://github.com/shizumaat/XPTerrainBuilder/issues> and
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
  **Restart X-Plane after a build** — it caches objects. If you would rather
  your packs were never touched, do not test on an install you cannot
  restore; a copy of X-Plane's `Custom Scenery` is the safe setup for this
  beta.
- **The same airport can come out slightly differently on macOS, Windows
  and Linux.** The surface is equally lawful on each, but not identical.
  Say which platform you built on.
- **Scenery packs you disabled in X-Plane still influence the build.** A
  pack marked disabled in `scenery_packs.ini` still supplies its airport
  layout. A fix is in progress; until then, move a pack out of
  `Custom Scenery` if you do not want it used.
- **Windows:** the Settings window is wider than a 1280-pixel screen on
  some font setups. A fix is in progress; until then maximise the window,
  and note that every setting also lives in `Ortho4XP.cfg` in the data
  folder.
- **Large airports take a while.** The airport stage runs a few seconds for
  a small field and around ten minutes for a large hub. The progress line
  names the airport and its step; it has not hung.
- First builds download imagery, elevation and map data and are much slower
  than rebuilds. A build with no network completes with missing textures
  and says so at the end of the tile.
- Windows and Linux builds are not code-signed; see the SmartScreen note
  above. macOS is Apple Silicon only.
- Nobody but the author has used the Windows and Linux apps yet. Layout
  glitches there are exactly the reports we want.
