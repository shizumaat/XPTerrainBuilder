# Brief pack — lane `betapackage`

Base: main `be53e810` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta round 3 lane betapackage

## The brief

## Lane betapackage — Linux AppImage + Windows/Linux branding (RELEASES-PLAN §C1, §D2, §E; you OWN .github/workflows/release.yml and Ortho4XP/Ortho4XP_Qt.spec this round)

STATE: the Windows artifact is a portable zip of the frozen Qt app renamed
XPTerrainBuilder.exe; the Linux artifact is a bare tar.gz. Ortho4XP_Qt.spec:154 still
brands the exe with `Utils/icons/Ortho4XP.ico` (the upstream Ortho4XP icon) and :181
the mac bundle arm with `Ortho4XP.icns`. The XPTerrainBuilder icon exists only as mac
assets: `Resources/AppIcon.png` (+ AppIcon.icns, IconSource*.png) and the CoreGraphics
generator `scripts/make_icon.swift` (mac-only). RELEASES-PLAN §E asks for a
cross-platform generator so the Qt app and the AppImage brand identically without a
Mac in the loop; §D2 asks for an AppImage (single file, double-clickable) with a
.desktop entry + icon, keeping the tar.gz; §C1 asks for the exe name, window title,
.ico and a version resource.

DO:
1. `scripts/make_icon.py` (Pillow; Pillow is already an engine dependency — verify in
   Ortho4XP/requirements.txt): from `Resources/AppIcon.png` (the design of record; do
   NOT redraw it) emit `icon.ico` (16/24/32/48/64/128/256) and PNGs 16…512 into an
   output dir. Deterministic output; a twin that checks the ico's embedded sizes and
   that every PNG has the right dimensions and an alpha channel. If AppIcon.png is
   smaller than 512 px say so and emit only the sizes it supports without upscaling
   past the source.
2. Windows: Ortho4XP_Qt.spec uses the generated .ico when present (generated in the
   release job before the freeze; fall back to the old icon in a dev tree so a local
   freeze never breaks) and carries a VERSION RESOURCE (PyInstaller `version=` file
   generated in the job from the VERSION triple: FileVersion/ProductVersion = app
   version, ProductName XPTerrainBuilder, the engine version and sha in the comments
   field). The Qt window icon (QApplication.setWindowIcon) uses the same PNG on
   Windows and Linux — that one line lives in Ortho4XP_Qt.py, which you may edit;
   do NOT edit Ortho4XP/src/O4_Qt_GUI.py (lane betawinpanel is in it).
3. Linux AppImage: build it in the linux job from the frozen onedir with appimagetool
   (download the pinned continuous/ release by exact URL + verify a sha256 you record in
   the workflow; ubuntu-22.04 has FUSE issues on runners — run appimagetool with
   `--appimage-extract-and-run`). AppDir layout: AppRun (execs the frozen binary with
   "$@"), `xpterrainbuilder.desktop` (Name=XPTerrainBuilder, Categories=Utility;,
   Terminal=false, Icon=xpterrainbuilder), the 256 px PNG at the AppDir root and under
   usr/share/icons/hicolor/256x256/apps/. The AppImage carries the same license
   payload and VERSION.txt the tar.gz does (RELEASES-PLAN §G: LICENSE, LICENSING.md,
   THIRD-PARTY-NOTICES.txt, gpl.txt, copyright.txt). Upload BOTH
   `XPTerrainBuilder-<v>-linux.AppImage` and the existing tar.gz; the release job's
   `files:` list gains the AppImage.
4. PROVE the AppImage on the runner before upload: `./X.AppImage
   --appimage-extract-and-run --proj-selfcheck` exits 0, and the frozen tile check
   (`scripts/check_frozen_tile.sh`, merged be53e810 — read it) passes when pointed at
   the AppImage run that way (if the script's binary argument cannot take extra
   leading args, run it against the AppRun inside an extracted AppDir instead and say
   so). An AppImage that cannot build a tile must not upload.
5. Release-notes template (docs/RELEASE_NOTES-TEMPLATE.md): Linux section says
   download the AppImage, `chmod +x`, double-click or run; tar.gz remains for those
   who prefer it; list the apt prerequisites once.

Lane betafrozenpatch is extending scripts/check_frozen_tile.* in parallel — do not
edit those two files; call them as they are.

EXCEPTION to no-push: you may push ONLY branch `claude/betapackage` and dispatch
Release ON THAT BRANCH ONLY (`gh workflow run Release --ref claude/betapackage`), at
most 5 rounds (~10 min each); never main, never a tag, never a PR. Read results with
gh run view / the jobs logs API (`gh api --allow-escape-sequences
repos/<owner>/<repo>/actions/jobs/<id>/logs`).

Rules: not a law lane. Worktree from Ortho4XP/: `tools/harness/lane_worktree.sh up
betapackage`; merge main first. The bash guard refuses engine test commands whose
effective cwd is not an Ortho4XP/ with venv and OSM_data, and pattern-matches
test-runner words inside heredocs — write files with the Write tool. Release Xcode
only; never quit the owner's app; never run make_engine/make_app; do not disturb the
mac signing/notarization steps or the tag/version steps in release.yml. Commit early;
do not merge. Report branch + sha, the Release run link with per-job conclusions, the
artifact names and sizes, the proof lines for step 4, and everything not done.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

