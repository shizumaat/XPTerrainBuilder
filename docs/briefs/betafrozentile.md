# Brief pack — lane `betafrozentile`

Base: main `bff0919b` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Beta round 2 lane betafrozentile

## The brief

## Lane betafrozentile — the release jobs BUILD A TILE with the frozen bundle (beta plan B4 round 2; you OWN .github/workflows/release.yml this round)

WHY: the release jobs prove only that the frozen bundle imports (PROJ + LERC
self-checks). The class that has actually shipped broken is a function-level
third-party import invisible to PyInstaller AND to the suite (highspy, 2026-09-10), a
data file missing from the .spec, or a wrong data-root/cwd inside the bundle. Those
appear only on a code path a real build walks.

DESIGN (lane betaci, accepted by the session):
- ONE script `scripts/check_frozen_tile.sh <frozen-binary> [python]`, same contract as
  `scripts/check_frozen_lerc.sh` (the binary under test; a separate interpreter that
  only builds the fixture and checks the result). Called by all three release jobs.
- Placement: right after the PROJ/LERC self-checks — on mac BEFORE signing and
  notarizing (a bundle that cannot build a tile must never be notarized), on
  Windows/Linux before branding and zipping. NOTE the mac job has NO separate LERC
  step: `scripts/make_engine.sh` runs it fatally inside "Freeze engine" with the freeze
  venv's python; the job's bare `python3` has NO numpy (a redundant step died on that,
  removed 649452b3). So on mac your script must either need no third-party package in
  its helper interpreter (preferred: stdlib only) or use the freeze venv's python —
  find how make_engine.sh names it.
- Fixture generated at run time into a temp dir, never committed: a synthetic data
  root, one small elevation source, a minimal Ortho4XP.cfg, imagery OFF (no network,
  no provider key), no X-Plane install, no shared corpus. Since lane betafirstrun
  merged (d5158ae0) the engine REFUSES auto-patch with no CIFP: either build with
  auto_patch disabled (the explicit opt-out still builds) or give the fixture a stub
  X-Plane tree with a CIFP dir and one synthetic airport — prefer the second if it is
  cheap, because auto_patch_v2 + highspy is exactly the lazy-import class; if it is
  not cheap, do the first and say so.
- Drive it through the SHIPPED interface, never an import: the engine's JSONL protocol
  on stdin/stdout (`--engine-jsonl`; read Ortho4XP/src/o4_engine/ for the command
  shapes and tests/test_engine_jsonl.py / test_engine_session.py for working
  examples). Assert EngineHello, step progress, BuildDone ok=true, RunDone, and on
  disk a non-empty .dsf (and the emitted patch + its .axes.json sidecar if auto-patch
  ran). Any miss exits non-zero and prints the child's stderr tail.
- Bounds: the whole check under a deadline (≤ 5 min; coreutils `timeout` does not
  exist on the mac runner or the owner's mac — implement the deadline in the helper
  interpreter). On failure upload the JSONL stream + stderr as an artifact.

OPEN QUESTION you must answer FIRST (it may BE the finding): on Windows and Linux the
shipped binary is `Ortho4XP_Qt` (Ortho4XP_Qt.py / Ortho4XP_Qt.spec). Does it expose a
headless build entry at all (`--engine-jsonl`, or a CLI tile path)? It does answer
`--proj-selfcheck`. If it exposes none, STOP and report that gap with the minimal
change that would add one (the engine owns cross-platform features; the UIs only
expose them) — do not work around it with an import.

Prove it locally on the mac frozen engine at
/Users/noah/XPTerrainBuilder/Ortho4XP/dist/Ortho4XP/Ortho4XP (read-only use; it is the
engine 1.50.1793 freeze; do NOT run make_engine.sh or make_app.sh, do NOT touch
dist.nosync/). Add the script's row to Ortho4XP/tools/INDEX.md only if the index
covers repo-root scripts/ (check_frozen_lerc.sh is the precedent — follow it).

You have ONE exception to the no-push rule: you may push ONLY branch
`claude/betafrozentile` and you may dispatch the Release workflow ON THAT BRANCH ONLY
(`gh workflow run Release --ref claude/betafrozentile`) to see the three jobs run your
check — a dispatch is not a tag, publishes nothing, and signs/notarizes the mac job
with the repo secrets (that is fine). At most 4 Release rounds (each ~10 min). Never
push main, never tag, never open a PR.

Rules: not a law lane (no airport build through the harness, no census). Worktree from
Ortho4XP/: `tools/harness/lane_worktree.sh up betafrozentile`; merge main first. The
bash guard refuses engine test commands whose effective cwd is not an Ortho4XP/ with
venv and OSM_data, and pattern-matches test-runner words inside heredocs — write files
with the Write tool. Release Xcode only; never quit the owner's app. Do not edit
ci.yml or O4_Qt_GUI.py (other lanes). Commit early; do not merge. Report branch + sha,
the answer to the open question, the local proof (rc + the asserted events), the
Release run link with per-job conclusions, and everything not done.

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

