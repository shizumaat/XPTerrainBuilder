# Release distributions plan — Mac, Windows, Linux

Goal: every release ships three self-contained downloads. A user downloads
one artifact, launches a binary, and on first run picks (1) where downloads
and built tiles live and (2) their X-Plane folder. No Python install, no
install scripts, no terminal.

## What each platform ships

| Platform | Artifact | GUI | Features |
|---|---|---|---|
| macOS | `XPScenerySmith-<v>-mac.dmg` (or .zip) | Native SwiftUI app | Doctor (analysis/fixes) + Build mode, frozen engine embedded |
| Windows | `XPScenerySmith-<v>-win.zip` (portable) | Qt map-first GUI (`Ortho4XP_Qt`), branded XPScenery Smith | Build only (engine + its GUI, frozen) |
| Linux | `XPScenerySmith-<v>-linux.AppImage` (tar.gz fallback) | same as Windows | Build only |

**Can the engine be bundled on all platforms, or only Mac?** All three.
The engine is Python + per-platform helper binaries, and `Utils/` already
vendors `mac/`, `win/`, and `lin/` builds of Triangle4XP, DSFTool,
nvcompress, etc.; `requirements.txt` pins GDAL per-platform (with the
Windows wheel vendored). PyInstaller freezes it into a launchable binary on
each OS — the specs (`Ortho4XP.spec`, `Ortho4XP_Qt.spec`,
`build_mac_app.sh`) already exist in `Ortho4XP/`.

What is *not* portable is the XPScenery Smith GUI itself: SwiftUI/AppKit is
Apple-only. So the honest shape of "three distributions" is: the full app
on macOS; on Windows/Linux the distribution *is* the frozen engine with its
own Qt GUI, branded XPScenery Smith. (Bringing the Doctor analysis features
cross-platform later means either building `SceneryKit`/`xpsmith-cli` with
Swift-on-Windows/Linux or porting the analyzers into the Qt app — out of
scope for the first release cycle.)

## Already in place (engine `dev`)

- `O4_File_Names.py` splits **read-only resources** (inside the PyInstaller
  bundle via `sys._MEIPASS`; never written, so macOS code signatures and
  read-only mounts survive) from a **writable data root** (downloads,
  OSM/elevation caches, masks, orthophotos, Tiles, config).
- First-launch data-root chooser semantics: `ORTHO4XP_DATA_ROOT` env var >
  remembered choice in `~/.ortho4xp/data_root.txt` > platform default
  (macOS: `~/Ortho4XP`, because Gatekeeper translocation makes
  "next to the app" unreliable; Windows/Linux: next to the executable —
  portable layout).
- `set_data_root()` + `seed_shipped_patches()` for pointing a fresh data
  root and seeding shipped `Patches/`.
- The JSON-lines engine transport (`--engine-jsonl`) the Mac app drives,
  with a parent-death watchdog (`O4_PARENT_PROCESS_ID`).

## Workstreams

### A. Engine-only freeze (feeds the Mac app; shared plumbing for all)

1. New `Ortho4XP_Engine.spec`: console, one-dir freeze of `Ortho4XP.py`
   restricted to the `--engine-jsonl` path. Excludes PySide6 and Tkinter
   (the Mac app is the GUI; saves ~250 MB), includes `src/`, `Providers/`,
   `Filters/`, `Extents/`, shipped `Patches/`, `Utils/<platform>/` only,
   GDAL/pyproj data files (proj.db resolution already handled in the specs).
2. Add `--schema-dump` to the frozen entry so the app's config-schema
   introspection works without a python interpreter (bundled snapshot
   remains the fallback — already implemented).

### B. macOS: XPScenerySmith.app with embedded engine

1. `OrthoEngine` grows a **frozen flavor**: a root is valid if it contains
   either `Ortho4XP.py` + `src/` (checkout — current behavior, kept for
   development) or a frozen `Ortho4XP` executable. For frozen engines,
   launch the executable directly instead of `python3 -u Ortho4XP.py`
   (`OrthoEngineClient.launch` and `OrthoBuildRunner` both).
2. `make_app.sh` (release mode) embeds the frozen engine at
   `XPScenerySmith.app/Contents/Resources/Engine/`. `BuildModel` defaults
   to the bundled engine when the user hasn't pointed Settings at a
   checkout; the Settings override stays for developers and for engine
   upgrades without an app update.
3. First-run wizard (Swift): one sheet, two choices — data folder
   (default `~/Ortho4XP`) and X-Plane folder (the app already knows how to
   pick/validate X-Plane roots for analysis; reuse it). Persist; export
   `ORTHO4XP_DATA_ROOT` when spawning the engine and write
   `custom_scenery_dir` into the engine config so builds land linkable to
   Custom Scenery.
4. Signing/notarization: Developer ID Application cert + notarytool API key
   as GitHub secrets; hardened runtime on app + every Mach-O in the frozen
   engine (PyInstaller output must be signed inner-first). Without secrets,
   CI still produces an ad-hoc-signed zip (users right-click → Open once).
5. Architecture: ship arm64 first (the vendored numpy wheel in `Utils/mac`
   is arm64-only). A separate x86_64 artifact later if there's demand;
   universal2 for a frozen Python tree is not worth the pain.

### C. Windows portable zip

1. Brand pass on the frozen Qt app: `XPScenerySmith.exe` name, window
   title, `.ico` derived from the app icon (see E), version resource.
2. Prune `Utils/` to `win/` at build time; verify the vendored GDAL and
   scikit-fmm wheels install in CI.
3. Portable zip (no installer, per goal): unzip anywhere, run the exe; the
   existing next-to-exe data-root default makes it a true portable app.
   First launch shows the (existing) data-root chooser + an X-Plane folder
   page (new; writes `custom_scenery_dir`).
4. Note in release notes: unsigned exe triggers SmartScreen "More info →
   Run anyway"; Authenticode signing is optional later.

### D. Linux

1. Same frozen Qt app; build on the oldest supported LTS runner
   (ubuntu-22.04) so the glibc floor is low.
2. Package as AppImage (single-file, double-clickable, matches the goal)
   with `.desktop` entry + icon; also upload the plain tar.gz.
3. Prune `Utils/` to `lin/`; keep the next-to-exe portable default but
   AppImages are read-only mounts, so the chooser must default to
   `~/Ortho4XP` when `is_frozen_app()` and the exe dir is unwritable.

### E. Icon for Windows/Linux

`scripts/make_icon.swift` is CoreGraphics (mac-only). Add
`scripts/make_icon.py` (Pillow port of the same design — the geometry
already exists from the redesign) emitting `icon.ico` + PNG sizes, so the
Qt app and AppImage brand identically without a Mac in the loop.

### F. Release CI

`.github/workflows/release.yml`, triggered by `v*` tags:

- `mac` (macos-15): swift build -c release → freeze engine → assemble app →
  sign/notarize (if secrets) → dmg/zip → upload.
- `win` (windows-latest): pip install → pyinstaller `Ortho4XP_Qt.spec`
  (branded) → prune → zip → upload.
- `linux` (ubuntu-22.04): same → AppImage + tar.gz → upload.
- A final job drafts the GitHub Release with all three artifacts and a
  source archive (see G).
- Version single-sourced from the tag: stamp `src/O4_Version.py`, the app's
  `CFBundleShortVersionString`, and the exe version resource in CI.
- Artifacts are large (roughly 300–500 MB each: Qt, scipy, GDAL, Utils);
  fine for GitHub Releases (2 GB/file limit).

### G. License obligation (do not skip)

The engine is **GPL v3** (`Ortho4XP/Licence/`). Distributing frozen engine
binaries obliges us to make the corresponding source available. The repo is
currently private, so each release must attach a source archive of the
`Ortho4XP/` tree (CI can do this automatically), or the repo goes public by
release time. The Swift app only *spawns* the engine over a pipe protocol
(separate process, no linking), so the app itself can remain closed; the
combined download is aggregation, but the engine's source offer must be
real.

## First-run flow (all platforms)

1. Launch binary. No engine/python setup ever shown.
2. Wizard: "Where should downloads and built scenery live?" (default
   `~/Ortho4XP`, or next-to-exe on Win/portable) + "Where is X-Plane?"
   (validated folder pick).
3. Data root is seeded (`Patches/`, folder skeleton); choice remembered
   (`~/.ortho4xp/data_root.txt` / app prefs).
4. Main window opens ready to select tiles and build.
5. Settings can later move the data root (offer to move/copy existing data)
   or re-pick X-Plane.

## Suggested order

1. A + B1/B2 (frozen engine + app launches it) — the Mac self-contained
   story end-to-end, since it's the flagship.
2. B3 first-run wizard, E icon port.
3. C Windows zip, D Linux AppImage (mostly CI + branding on existing spec).
4. F release workflow, G source archive, then tag `v0.2.0` as the first
   three-platform release.
