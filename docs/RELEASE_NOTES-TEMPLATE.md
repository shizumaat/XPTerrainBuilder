# Release notes template

Copy this file to `docs/RELEASE_NOTES-<version>.md` (the version exactly as
the tag spells it without the leading `v` — `1.0.347-beta.1`), fill in every
`<…>`, delete this header block, commit it, and only then move the tag. The
release job REFUSES a tag with no notes file: this page is the whole of what a
first-time beta tester is handed, and a bare auto-generated body is not it.

Keep every section below. Remove a bullet only when it has stopped being
true, not because nothing changed in it.

---

# XPTerrainBuilder <version>

**<Beta N / prerelease>.** <One paragraph: what this build is for, what you
want tested, and that it is a prerelease.>

## What this is

XPTerrainBuilder builds X-Plane photoscenery ("ortho" scenery): you pick
1°×1° tiles on a map, choose an imagery provider and build options, and it
produces the mesh, textures and DSF files X-Plane needs. It additionally
regrades paved airport surfaces to FAA/EASA/ICAO geometry instead of draping
them over raw elevation data, and reseats custom airport objects onto the
surface it built.

It is a fork and derivative of
**[Ortho4XP](https://github.com/oscarpilote/Ortho4XP) by Oscar Pilote**.

## What changed in this build

- <Change, in the user's words — what they can now do, or what stopped
  going wrong.>
- <…>

## Download and first launch

| Platform | Artifact |
| --- | --- |
| macOS 14+, **Apple Silicon only** | `XPTerrainBuilder-<version>-mac.zip` |
| Windows 10/11 x64 | `XPTerrainBuilder-<version>-win.zip` |
| Linux x86_64 (built on Ubuntu 22.04) | `XPTerrainBuilder-<version>-linux.AppImage` (or `…-linux.tar.gz`) |

**macOS.** The app is signed with a Developer ID and notarized by Apple, so
there is nothing to bypass.

1. Unzip the download.
2. Move `XPTerrainBuilder.app` where you want it (e.g. `/Applications`).
3. Double-click it. **No Gatekeeper dialog is expected.**

If a dialog does appear — "cannot be opened because the developer cannot be
verified", "damaged", or any unverified-developer warning — the build you
have is not the signed one. **Report it** with the exact file name you
downloaded, rather than working around it. Do not use right-click → Open:
current macOS no longer offers that bypass, and here it would only hide a
bad download.

macOS builds are **arm64 (Apple Silicon) only**. There is no Intel build.

**Windows.** Unzip anywhere and run `XPTerrainBuilder.exe`. The app is not
code-signed yet, so SmartScreen warns about an unrecognized app: click
**More info → Run anyway**. Keep the folder contents together — the app is
portable, not installed.

**Linux.** Download the **AppImage**, make it executable, and run it — one
file, nothing to install:

```sh
chmod +x XPTerrainBuilder-<version>-linux.AppImage
./XPTerrainBuilder-<version>-linux.AppImage
```

Double-clicking it in a file manager works too, once it is executable
(some desktops offer "Allow executing file as program" in its Properties).
If your system has no working FUSE, run it as
`./XPTerrainBuilder-<version>-linux.AppImage --appimage-extract-and-run`.

The **tar.gz** remains for anyone who prefers a plain folder — same build,
unpacked:

```sh
tar xzf XPTerrainBuilder-<version>-linux.tar.gz
cd XPTerrainBuilder
chmod +x XPTerrainBuilder
./XPTerrainBuilder
```

On a minimal system, install the Qt and archive prerequisites first (both
artifacts need them):

```sh
sudo apt-get install -y libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
  libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 p7zip-full
```

`p7zip-full` is required, not optional: the build extracts 7-Zip archives
when it installs scenery overlays, and without it that step stops.

Both Linux artifacts carry the licenses and `VERSION.txt` at their root;
inside the AppImage they are reachable with
`./XPTerrainBuilder-<version>-linux.AppImage --appimage-extract`.

## The two folders

XPTerrainBuilder keeps everything writable in **one data folder**, and
installs finished scenery into **your X-Plane folder**. They are different
folders and it asks for both.

- **Data folder** — imagery downloads, elevation and OSM caches, masks,
  built tiles, configuration. Default `~/XPTerrainBuilderData` on every
  platform, deliberately outside the app so that updating the app is just
  replacing the app. Remembered in `~/.ortho4xp/data_root.txt`; the
  `ORTHO4XP_DATA_ROOT` environment variable overrides it. Already have a
  folder from a previous run or from Ortho4XP? Point the chooser at it —
  existing downloads, tiles and settings are used as they are.
- **X-Plane folder** — your X-Plane 12 installation. Finished tiles are
  installed into its `Custom Scenery`, and the airport data there is what
  the grading is computed against.

**Disk space.** Ortho tiles are large: budget roughly <N> GB per 1°×1° tile
at the default zoom level, more at higher zoom, plus a few GB of shared
elevation and OSM cache. A build also needs several GB of temporary space in
the data folder while it runs. Put the data folder on a drive with room to
grow.

## How to report a problem

Open an issue at <issue tracker URL> and include, in this order:

1. **The version triple.** Every download carries `VERSION.txt` at its root
   with three lines — `app=`, `engine=` and `sha=`. Paste all three. The
   same three are in the app: **XPTerrainBuilder ▸ About XPTerrainBuilder**
   on macOS, **Help ▸ About** on Windows and Linux.
2. **What you did**, which airport or tile coordinates, and which imagery
   provider.
3. **The log.**
   - macOS: `~/Library/Logs/XPTerrainBuilder/engine-stderr.log`, plus the
     build console pane (it has a copy button).
   - Windows and Linux: `<data folder>/logs/engine-stderr.log` (20 MB
     rotation, same rule as the mac log), plus the build console pane,
     copied.
4. **Screenshots** of anything visibly wrong in the sim, with the airport
   and the rough position.

## Known issues

- <Known issue, with what it looks like and any workaround.>
- Windows and Linux builds are not code-signed; see the SmartScreen note
  above.
- macOS is Apple Silicon only.
- <…>
