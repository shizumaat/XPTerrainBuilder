# Brief pack — lane `betasign`

Base: main `46085b46` · generated 2026-09-16 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Sign (hardened, inner-first) and notarize the mac app; CI signing in release.yml

## The brief

## Lane betasign — sign and notarize the mac app (docs/BETA-PLAN-20260916.md §1 B1)

NOT an engine-law lane: no airport build, no census, no RULINGS reading. Files
in scope: `scripts/make_app.sh` (signing at :139-153), NEW `scripts/sign_app.sh`,
NEW `scripts/notarize_app.sh`, NEW `Resources/XPTerrainBuilder.entitlements`
(or `scripts/` — pick one, say where), `.github/workflows/release.yml` (mac job
only), `docs/RELEASE_NOTES-*` template text on Gatekeeper, `docs/RELEASES-PLAN.md`
§B4 marked DONE. Run `Ortho4XP/venv/bin/python tools/blast.py <file>` before
editing anything under `Sources/` (you should not need to).

### Facts established by the session (2026-09-16)
- Identity in the owner's login keychain, proven working by the session
  (test signature: flags=runtime, secure timestamp, chain to Apple Root CA,
  no keychain prompt pending):
      Developer ID Application: Noah Phillip Lieberman (5MVM7P5WDJ)
  Team ID 5MVM7P5WDJ. Never print or commit the cert hash, never export keys.
- Today `make_app.sh` signs ONLY the outer bundle, ad-hoc unless
  `XPTB_SIGN_IDENTITY` is set or a cert named "XPTerrainBuilder Dev" exists;
  no `--options runtime`, no `--timestamp`, no entitlements, no inner signing.
- The frozen engine is embedded at `XPTerrainBuilder.app/Contents/Resources/
  Engine/` (PyInstaller onedir: `Ortho4XP` + `_internal/`), helper binaries
  under `_internal/Ortho4XP_Data/Utils/mac/` (DSFTool, Triangle4XP, osmium,
  7zz, nvcompress, DDSTool, triangle …). Build app: `DEVELOPER_DIR=
  /Applications/Xcode-beta.app ./scripts/make_app.sh release` (needs the app
  NOT running; it refuses otherwise — do NOT quit the owner's app; work on a
  COPY of `dist.nosync/XPTerrainBuilder.app` in your scratchpad instead and
  only run make_app.sh if the app is not running).
- Repo lives in iCloud-synced Documents: xattrs appear mid-build and codesign
  rejects "detritus" — `xattr -cr` before signing (make_app.sh:140 already
  does for the stage). Chain scripts with `&&`, never `;`; never pipe a
  script's output through `tail`/`head` under pipefail and trust the rc.
- The notarization API key and GitHub secrets DO NOT EXIST YET (owner-owed).
  Secret names are fixed: MACOS_CERT_P12 (base64 .p12), MACOS_CERT_PASSWORD,
  NOTARY_KEY_P8 (base64 .p8), NOTARY_KEY_ID, NOTARY_ISSUER_ID.

### Deliverables
1. `scripts/sign_app.sh APP [IDENTITY]` — INNER-FIRST: discover every Mach-O
   under the bundle with `find` + `file` (never a hand list; include `.so`,
   `.dylib`, bare executables, and any nested `.framework`/`Python` binary),
   sign each with `--force --options runtime --timestamp --entitlements E`,
   deepest paths first, then `Engine/Ortho4XP`, then the app. NEVER
   `codesign --deep` to sign. Closing checks inside the script, rc ≠ 0 on
   failure: `codesign --verify --deep --strict --verbose=2 APP`; every Mach-O
   reports TeamIdentifier=5MVM7P5WDJ and flags runtime (count them, print
   N signed / N found, refuse on mismatch).
2. Entitlements: start from `com.apple.security.cs.allow-unsigned-executable-
   memory` + `com.apple.security.cs.disable-library-validation`. Add another
   ONLY on a measured failure, and record the failing command in the commit.
3. `make_app.sh`: when the resolved identity starts with "Developer ID
   Application", call sign_app.sh (hardened); otherwise keep today's ad-hoc /
   dev-cert path unchanged (local dev builds must not slow down or break).
4. `scripts/notarize_app.sh APP` — ditto zip, `xcrun notarytool submit --wait`
   with `--key/--key-id/--issuer` from env (NOTARY_KEY_PATH, NOTARY_KEY_ID,
   NOTARY_ISSUER_ID), refuse unless status Accepted (print `notarytool log`
   on failure), `xcrun stapler staple`, `stapler validate`, `spctl -a -t exec
   -vv` must say "Notarized Developer ID". With the env absent it REFUSES by
   name (rc ≠ 0) — it never silently skips.
5. `release.yml` mac job: throwaway keychain (create, unlock, import p12,
   `security set-key-partition-list`, delete in an `if: always()` step), sign
   via make_app.sh with XPTB_SIGN_IDENTITY, notarize, staple, zip the STAPLED
   app. On a `v*` TAG with any of the five secrets empty the job FAILS naming
   the missing secret; on `workflow_dispatch` without secrets it builds ad-hoc
   and names the artifact `...-mac-UNSIGNED.zip`.
6. Release-notes template text: replace the right-click instruction.

### Closing test (what you can prove without the notary key)
On a scratch COPY of the current `dist.nosync/XPTerrainBuilder.app`: run
sign_app.sh; then UNDER THE HARDENED RUNTIME run from the signed copy:
`Engine/Ortho4XP --proj-selfcheck` (rc 0), `bash scripts/check_frozen_lerc.sh
<signed Engine/Ortho4XP> <python>` (rc 0), and each helper binary's version/
usage call (DSFTool, Triangle4XP, osmium --version, 7zz, DDSTool, nvcompress)
— a library-validation or JIT kill shows up here as SIGKILL / "code signature
invalid" in `log show --last 2m --predicate 'eventMessage CONTAINS "AMFI"'`.
Also start the signed engine in JSONL mode (`Engine/Ortho4XP --engine-jsonl`,
close stdin) and confirm the EngineHello line. `spctl` WILL say "Unnotarized
Developer ID" — expected, say so. Validate the workflow YAML parses
(`python -c 'import yaml…'`), do NOT push, do NOT dispatch a workflow.
Report: branch + sha, the N signed / N found line, each check's rc, every
entitlement added and why, and the exact one-line command the owner runs to
notarize locally once the .p8 exists.

## Files

Yours: `scripts/make_app.sh`, `.github/workflows/release.yml`, `docs/RELEASES-PLAN.md`

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

