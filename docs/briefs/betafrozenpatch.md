# Brief pack — lane `betafrozenpatch`

Base: main `be53e810` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta round 3 lane betafrozenpatch

## The brief

## Lane betafrozenpatch — the frozen-bundle release check also SOLVES ONE AIRPORT (closes lane betafrozentile's stated gap)

STATE (merged be53e810): `scripts/check_frozen_tile.sh` + stdlib-only
`scripts/check_frozen_tile.py` drive the frozen binary over `--engine-jsonl` and build
one synthetic tile in every release job (mac before signing; Windows/Linux before
zipping). Release run 35259947732: mac 13 s, Windows 22 s, Linux 20 s, identical
470,460-byte DSF. BUT it builds with `auto_patch=None`, because the engine refuses
auto-patch with no CIFP (lane betafirstrun, d5158ae0). So the class that actually
shipped broken — a FUNCTION-LEVEL third-party import inside the airport solver,
invisible to PyInstaller and to the suite (highspy, 2026-09-10; memory
`frozen-engine-lazy-imports`) — is still unguarded at release time.

DO: add a SECOND pass (or a second mode of the same script — one tool, a parameter;
never a fork) that runs auto_patch_v2 inside the frozen bundle on ONE real small
airport, derived from the existing fixture `Ortho4XP/tests/auto_patch_v2/fixtures/CYXY`
(220 KB: CIFP, Custom Scenery, Elevation_data, OSM_data, Airport_mod_cache — a complete
mini-world; read how the tests consume it, e.g. grep "fixtures/CYXY" and "CYXY" under
tests/auto_patch_v2/ and conftest). The helper stays STDLIB-ONLY (the mac job's bare
python3 has no numpy): it may copy/arrange fixture files and write configs, nothing
more.
- Arrange a temp X-Plane-like root + data root from the fixture so the engine's own
  predicate (O4_Settings_Model.xplane_install_problem / resolve_cifp_dir) accepts it,
  with auto_patch ON for that airport; no network, no provider key, no shared corpus.
- Drive it through the same JSONL interface. Assert: the AutoPatch events arrive
  (AutoPatchBegin/Progress are emitted by the engine even though UIs fold them), NO
  AutoPatchFailed, BuildDone ok=true, and on disk the emitted `CYXY_auto.patch.osm`
  with its `.axes.json` sidecar, the sidecar reporting a solved status (find the key
  the harness reads — `solve=optimal|feasible` in the provenance line) — i.e. HiGHS
  actually ran inside the bundle.
- Mechanism check that the guard has TEETH (mandatory, this is the point): prove
  locally that the pass FAILS when highspy is absent. You may not re-freeze; instead
  run the pass against the existing mac freeze
  /Users/noah/XPTerrainBuilder/Ortho4XP/dist/Ortho4XP/Ortho4XP (read-only — copy the
  whole dist dir into your scratchpad first, then in the COPY rename/remove the highspy
  extension module under _internal/ and show the pass goes red with a message naming
  the import). Never modify the original dist, never touch dist.nosync/.
- Budget: the airport pass ≤ 5 min on a runner (CYXY builds in ~35 s on the owner's
  mac through the harness). Deadline enforced in the helper, not by coreutils timeout.
  On failure the JSONL stream + stderr are uploaded (the existing `if: failure()` step
  should already cover it — extend its paths if needed).
- If the fixture cannot be arranged into a tree the engine accepts without editing
  engine code, STOP and report exactly which predicate/file is missing — do not weaken
  the engine's refusal.

FILES YOU OWN: scripts/check_frozen_tile.sh, scripts/check_frozen_tile.py. You MAY add
at most ONE step line per job to .github/workflows/release.yml ONLY if the new pass is
not reachable through the existing call (prefer making the existing call run both
passes, so release.yml is untouched — another lane, betapackage, is editing release.yml
this round). Do not touch ci.yml, O4_Qt_GUI.py, the specs.

EXCEPTION to no-push: you may push ONLY branch `claude/betafrozenpatch` and dispatch
Release ON THAT BRANCH ONLY (`gh workflow run Release --ref claude/betafrozenpatch`),
at most 4 rounds; never main, never a tag, never a PR.

Rules: not a law lane (no harness airport build, no census, no shared-repo write).
Worktree from Ortho4XP/: `tools/harness/lane_worktree.sh up betafrozenpatch`; merge
main first. The bash guard refuses engine test commands whose effective cwd is not an
Ortho4XP/ with venv and OSM_data, and pattern-matches test-runner words inside
heredocs — write files with the Write tool. Release Xcode only; never quit the owner's
app; never run make_engine/make_app. Commit early; do not merge. Report branch + sha,
the local green proof, the local RED proof with highspy removed (the exact message),
the Release run link with per-job conclusions and timings, and everything not done.

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

