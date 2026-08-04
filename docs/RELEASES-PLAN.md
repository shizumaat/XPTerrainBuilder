# Release distributions plan — Mac, Windows, Linux

Goal: every release ships three self-contained downloads. A user downloads
one artifact, launches a binary, and on first run picks (1) where downloads
and built tiles live and (2) their X-Plane folder. No Python install, no
install scripts, no terminal.

## What each platform ships

| Platform | Artifact | GUI | Features |
|---|---|---|---|
| macOS | `XPTerrainBuilder-<v>-mac.dmg` (or .zip) | Native SwiftUI app | Doctor (analysis/fixes) + Build mode, frozen engine embedded |
| Windows | `XPTerrainBuilder-<v>-win.zip` (portable) | Qt map-first GUI (`Ortho4XP_Qt`), branded XPTerrainBuilder | Build only (engine + its GUI, frozen) |
| Linux | `XPTerrainBuilder-<v>-linux.AppImage` (tar.gz fallback) | same as Windows | Build only |

**Can the engine be bundled on all platforms, or only Mac?** All three.
The engine is Python + per-platform helper binaries, and `Utils/` already
vendors `mac/`, `win/`, and `lin/` builds of Triangle4XP, DSFTool,
nvcompress, etc.; `requirements.txt` pins GDAL per-platform (with the
Windows wheel vendored). PyInstaller freezes it into a launchable binary on
each OS — the specs (`Ortho4XP.spec`, `Ortho4XP_Qt.spec`,
`build_mac_app.sh`) already exist in `Ortho4XP/`.

What is *not* portable is the XPTerrainBuilder GUI itself: SwiftUI/AppKit is
Apple-only. So the honest shape of "three distributions" is: the full app
on macOS; on Windows/Linux the distribution *is* the frozen engine with its
own Qt GUI, branded XPTerrainBuilder. (Bringing the Doctor analysis features
cross-platform later means either building `SceneryKit`/`xptb-cli` with
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

1. **DONE (via existing spec):** `scripts/make_engine.sh` freezes the
   engine with the stock `Ortho4XP.spec` (one-dir, console) into
   `Ortho4XP/dist/Ortho4XP/` — own Python runtime, all packages, GDAL
   best-effort (optional at runtime), `VERSION.txt` stamped for the app.
   Still open: a dedicated `Ortho4XP_Engine.spec` that excludes
   Tkinter/Previews to shave the jsonl-only payload.
2. Add `--schema-dump` to the frozen entry so the app's config-schema
   introspection works without a python interpreter (bundled snapshot
   remains the fallback — already implemented and used for frozen engines).

### B. macOS: XPTerrainBuilder.app with embedded engine

1. **DONE:** `OrthoEngine` has the **frozen flavor**: a root is valid if it
   contains either `Ortho4XP.py` + `src/` (checkout) or a frozen
   `Ortho4XP` executable + `_internal/Ortho4XP_Data`. Frozen engines
   launch the executable directly, always speak the session protocol,
   skip the python-package probe, and read Providers/Extents from the
   PyInstaller data dir. Settings shows "Self-contained" instead of the
   python setup section. `.github/workflows/release.yml` builds all three
   platform artifacts.
2. **DONE (source-tree flavor):** `make_app.sh` embeds the engine source
   tree at `XPTerrainBuilder.app/Contents/Resources/Engine/` (tests, docs,
   Previews, tools pruned). `BuildModel` defaults to the bundled engine
   when the user hasn't pointed Settings at a checkout; the Settings
   override stays for developers and for engine upgrades without an app
   update. On Windows/Linux the engine lives in `Engine/` next to the
   executable (`OrthoEngine.bundled()` already probes there). Swapping the
   embedded source tree for the frozen engine (step 1) remains.
3. **DONE:** First-run sheet (Swift) asks for the data folder (default
   `~/XPTerrainBuilder`), changeable in Settings ▸ General; every engine
   process gets `ORTHO4XP_DATA_ROOT`, so downloads, caches, tiles and
   `Ortho4XP.cfg` land there, never inside the bundle. Still open from the
   original plan: folding the X-Plane folder pick into the same sheet and
   writing `custom_scenery_dir` into the engine config.
4. Signing/notarization: Developer ID Application cert + notarytool API key
   as GitHub secrets; hardened runtime on app + every Mach-O in the frozen
   engine (PyInstaller output must be signed inner-first). Without secrets,
   CI still produces an ad-hoc-signed zip (users right-click → Open once).
5. Architecture: ship arm64 first (the vendored numpy wheel in `Utils/mac`
   is arm64-only). A separate x86_64 artifact later if there's demand;
   universal2 for a frozen Python tree is not worth the pain.

### C. Windows portable zip

1. Brand pass on the frozen Qt app: `XPTerrainBuilder.exe` name, window
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

Full per-component breakdown: [`LICENSING.md`](../LICENSING.md). This
section is the release-time checklist only.

**Premise: the release is free of charge.** Triangle
(`Utils/{mac,win,lin}/{triangle,Triangle4XP}`) permits redistribution only
where "no compensation is received"; commercial distribution requires direct
arrangement with Jonathan Shewchuk. A paid release — including a paid tier,
paid feature unlock, or bundling into anything sold — is blocked until
Triangle is replaced or licensed. See `LICENSING.md` §6(a).

**Source availability (GPL v3).** The repo is now **public**
(`shizumaat/XPTerrainBuilder`), which satisfies the GPL v3 source offer for
the engine, `auto_patch`, and `o4_engine`. Still attach a source archive of
the `Ortho4XP/` tree to each release: a public repo can be renamed, moved,
or taken private, and the offer must survive the binary. CI does this in the
final draft-release job. The tag must be the exact tree the binaries were
frozen from.

**Boundary that keeps the Swift app MIT.** The app *spawns* the engine as a
separate process over the JSONL pipe protocol — no linking, no shared
address space. The combined download is mere aggregation. Do not introduce
in-process linkage (embedded CPython, a shared library, FFI into engine
code) without re-deciding the app's license.

**PySide6 is LGPL v3** and is frozen into the Windows and Linux Qt builds.
Keep those builds **onedir, never onefile**, so the Qt libraries stay
separate relinkable files, and publish the exact PySide6/Qt versions plus
the freeze recipe. The macOS app does not link Qt and is unaffected.

**Per-artifact checklist.** Every uploaded artifact must contain, at its
root:

1. `LICENSE` (the scope notice + MIT text)
2. `LICENSING.md`
3. `Ortho4XP/Licence/gpl.txt` and `Ortho4XP/Licence/copyright.txt`
4. `THIRD-PARTY-NOTICES.txt` — generated in CI from `LICENSING.md` §3–§4.
   Must cover what we actually ship, not what upstream documented in 2018:
   upstream's `copyright.txt` predates DDSTool, osmium, and the bundled
   wheels, and gives moulinette no terms at all. The 7-Zip block must be
   reproduced verbatim (its license requires it). Prune per platform to
   match the pruned `Utils/` directory.
5. `Utils/src/` (Triangle sources) — Triangle requires source *and* object
   code be available without charge, with clear notice of modification.
   Do not prune `Utils/src/` out of release artifacts.

**Imagery disclosure.** Release notes and first-run must carry the provider
terms-of-service notice from `LICENSING.md` §5. The providers we ship
templates for (Esri, Google, Bing, Here) prohibit bulk download and
redistribution of derived imagery; that is a user obligation we must
surface, not one we can grant away.

**Before the first release**, close the two open items in `LICENSING.md` §6:
drop the unused proprietary `medit` binaries (b), and resolve moulinette's
missing license (c).

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
