# Brief pack — lane `betaappimagert`

Base: main `5f68c961` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Round 4 lane betaappimagert

## The brief

## Lane betaappimagert — the AppImage is built from a VENDORED, checksum-verified runtime (owner decision 2026-09-17)

STATE: the session has already downloaded and committed the file, on the owner's
explicit approval: `scripts/appimage/runtime-x86_64` (944,632 bytes, static-pie ELF
x86-64, sha256 `1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf`,
upstream commit 75849dce, asset dated 2026-06-23) with its provenance record
`scripts/appimage/README.md` — READ IT. You download NOTHING.

WHY: `appimagetool` (pinned 1.9.1 by sha256 in release.yml, lane betapackage merge
705afca9) fetches the type-2 runtime at build time from upstream's mutable
`continuous` tag; those bytes become the first code a Linux tester runs.

DO:
1. `scripts/make_appimage.sh`: pass `--runtime-file scripts/appimage/runtime-x86_64`
   to appimagetool (resolve the path from the script's own location, never the cwd).
   BEFORE building, verify the file's sha256 against ONE pinned value in the script
   (the README table documents it; the script is the enforcement) and REFUSE by name
   on mismatch or absence (`sha256sum` on the Linux runner; fall back to `shasum -a 256`
   so the script still runs on a mac for local checks). Confirm in appimagetool's
   own output/log that it used the supplied runtime and made NO download (grep its
   log for the download line and fail the step if it appears) — a silent fallback to
   the network would defeat the purpose.
2. PROVE the shipped artifact carries it: after the build, extract the runtime region
   of the AppImage (the ELF before the squashfs offset: `./X.AppImage
   --appimage-offset` gives the offset; `head -c <offset>`) and assert its sha256 —
   note appimagetool may patch a few bytes of the runtime (the AppImage type magic at
   offset 8, and digest/signature sections): if the embedded prefix is NOT
   byte-identical to the vendored file, MEASURE what differs (offsets and lengths),
   and assert on the rest; say exactly what you found. Do not weaken this to "the
   file exists".
3. Licensing (LICENSING.md is the source of truth; `scripts/make_notices.py`
   generates THIRD-PARTY-NOTICES.txt from it; RELEASES-PLAN §G): add the runtime —
   MIT, © 2004-23 probonopd — AND the components it statically links. Establish that
   list from upstream's own build files/README at commit 75849dce
   (`gh api repos/AppImage/type2-runtime/contents/...` — reading is fine; expect
   squashfuse, libfuse, zstd, zlib, musl — VERIFY, do not copy my guess), each with
   its licence. It ships only inside the Linux AppImage; say so in LICENSING.md.
   Run whatever test pins the notices (grep tests/ for make_notices / LICENSING).
4. Twins in `Ortho4XP/tests/test_release_packaging.py`: the script pins the same
   sha256 the README records; the vendored file on disk has that sha256 and is a
   944,632-byte ELF; release.yml's linux job still verifies appimagetool's own pin;
   the script contains the refusal path. Keep the existing 8 tests green.
5. The file must NOT enter any frozen bundle: it lives under `scripts/`, which no
   .spec bundles — assert that in a twin (neither spec's datas reach `scripts/`).

You OWN `scripts/make_appimage.sh` and may edit `.github/workflows/release.yml`'s
LINUX job only where the AppImage steps need it; do not disturb mac signing, the
tag/version steps, the frozen tile/airport check, or the Windows job.

EXCEPTION to no-push: push ONLY branch `claude/betaappimagert`; dispatch Release ON
THAT BRANCH ONLY (`gh workflow run Release --ref claude/betaappimagert`), at most 4
rounds (~10 min each); never main, never a tag, never a PR. Closing test: a green
Release run whose Linux job shows the sha256 verification line, no runtime download,
the embedded-runtime proof, `AppImage PROJ self-check: OK` and `AppImage tile build:
OK` (both passes), plus the artifact sizes.

Rules: not a law lane. Worktree from Ortho4XP/: `tools/harness/lane_worktree.sh up
betaappimagert`; merge main first. The bash guard refuses engine test commands whose
effective cwd is not an Ortho4XP/ with venv and OSM_data (run tests from your
worktree's Ortho4XP/ in their own call), pattern-matches test-runner words inside
heredocs (write files with the Write tool) and refuses `git stash`. Release Xcode
only; never quit the owner's app; never run make_app/make_engine. Commit early; do
not merge. Report branch + sha, the run link with per-job conclusions, the proof
lines, what (if anything) appimagetool patches in the runtime, the verified list of
statically linked components, and everything not done.

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

