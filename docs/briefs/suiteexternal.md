# Brief pack — lane `suiteexternal`

Base: main `0e2a7c29` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

suiteexternal: the pytest session detector names ledgered/redirected shared-repo deltas as EXTERNAL

## The brief

# suiteexternal — the suite's session detector gets the build audit's EXTERNAL downgrade

## The defect (RULINGS 15ay tail, 15n)
`tests/conftest.py::_the_shared_data_repo_survives_the_suite` (the session-scope
before/after snapshot) fails the WHOLE session (pytest reports it as a teardown
ERROR on the last collected test / every worker) whenever ANY shared-repo path
changed during the suite. Today 13:26:13 and 13:29:27 another session's
authorised, ledgered `--refresh-data` wrote
`OSM_data/+30-100/+32-098/+32-098_big_roads.osm.bz2` and
`OSM_data/+30-110/+33-113/+33-113_big_roads.osm.bz2` (both entries in
`/Users/noah/XPTerrainBuilderData/.harness/refresh_ledger.jsonl`) and every test
in two suites got a teardown ERROR. The build audit already downgrades exactly
this class: `tools/harness/shared_repo_guard.py::report_unauthorised_writes(...,
input_scope=BuildInputScope, redirected=)` labels a delta EXTERNAL-CANDIDATE
(named, never contaminating) — the suite detector has NO such door.

## The mechanism — ONE, in the guard module, imported by conftest (never copied)
1. `Ortho4XP/tools/harness/shared_repo_guard.py`: ONE new pure predicate,
   `ledgered_refresh_paths(window_start: str, window_end: str, *, ledger=None) -> dict[str, dict]`
   (`ledger=None` means `REFRESH_LEDGER`), mapping relpath -> {"ts", "scope"} for
   every `files[].path` AND every `removed[]` entry of a ledger record whose `ts`
   (format `%Y-%m-%dT%H:%M:%S`, written by `record_refresh`) satisfies
   `window_start <= ts <= window_end` (string compare is correct for that
   format). Tolerates a missing ledger and malformed lines (skip, never raise).
   Read-only; never writes the ledger.
2. `Ortho4XP/tools/harness/build_airport.py`: add the new name to the existing
   `from shared_repo_guard import (...)` re-export list (line ~258) — conftest
   reaches the harness through `_harness_build_module()` and nothing else.
3. `Ortho4XP/tests/conftest.py`: the detector stamps
   `window_start = time.strftime(fmt)` BEFORE the before-snapshot and
   `window_end` AFTER the after-snapshot; at teardown each touched path (already
   minus lock churn) is classified in ONE walk:
   - EXTERNAL, reason `ledgered <ts> <scope>`: its relpath is in
     `ledgered_refresh_paths(window_start, window_end)`;
   - EXTERNAL, reason `redirected`: `scope_of(path)` is in the guard's
     `redirected_scopes()` (import it through the harness module; do NOT extend
     `_REDIRECTABLE_SCOPES`; REPORT whether the suite's OSM regional-extract
     overlay scope is covered by it — if not, that is a reported residual, not a
     lane edit);
   - otherwise UNLAWFUL — fails the suite exactly as today (same message).
   EXTERNAL deltas are PRINTED under their own heading (path, scope, reason),
   never `pytest.fail`. Keep `unauthorised_shared_writes(changes, scope_of)`
   working unchanged for its existing twin
   (`test_the_shared_repo_detector_flags_a_test_written_cache`); add the
   classification as a new pure function taking the external knowledge as
   ARGUMENTS (`ledgered: dict`, `redirected: set`) so it twins offline; the
   fixture is the only caller that asks the real ledger/engine.
   `O4_ALLOW_SHARED_REPO_WRITES=1` behaviour unchanged.
4. Twins in `Ortho4XP/tests/test_harness.py`, beside the existing detector
   twins (~L5540): (a) tmp ledger (write 3 JSONL records by hand: one inside
   the window, one before, one after; the in-window one carries a `removed`
   path) + tmp root: in-window paths (files AND removed) -> EXTERNAL with
   ts+scope; the out-of-window record's path -> UNLAWFUL; (b) a redirected
   scope -> EXTERNAL reason redirected, passing an explicit `redirected={...}`
   (never asking the engine in the twin); (c) `.lock` churn still churn, never
   in either list; (d) a source-text twin that conftest IMPORTS the predicate
   through the harness module and defines no second copy (pattern of
   `test_the_detector_uses_the_harness_snapshot_not_a_copy`); (e) missing
   ledger file -> empty dict; a malformed line is skipped.
5. Convergence guards: materiality n/a (boolean); attempt cap 2 per target;
   `.progress` START/step/EXIT stamps in your scratch dir.

## Stated residual (write it in the docstring, do not solve it)
A refresh whose file write landed inside the window but whose ledger record is
appended AFTER the suite's after-snapshot (refresh still running at teardown)
still fails the suite. The ledger is written by `record_refresh` after the
refresh's own after-snapshot, so this is only the in-flight case.

## Build-time impact statement
None: test-time only (one read of a few-KB JSONL at session teardown).

## HARD LIMITS
- NO builds, NO downloads, NO writes anywhere under /Users/noah/XPTerrainBuilderData
  (the twins use tmp_path ledgers and roots ONLY).
- Run `venv/bin/python ../tools/blast.py <file>` (from `Ortho4XP/`; the bash
  guard refuses engine python from the repo root) before each edit:
  conftest.py, shared_repo_guard.py, build_airport.py, test_harness.py.
- Work IN THIS worktree (`/Users/noah/XPTerrainBuilder/.claude/worktrees/upbeat-austin-58f4f6`,
  already mounted by the lane ritual) on branch `claude/upbeat-austin-58f4f6`;
  commit there; do NOT merge main yourself, do NOT touch main or any other
  worktree. The spawner merges.
- Do NOT append to RULINGS.md (the session writes the ruling from your report).
- Suite, from `Ortho4XP/`: `venv/bin/python -m pytest tests/test_harness.py tests/auto_patch_v2 -q`
  — `python -m pytest`, NEVER bare `venv/bin/pytest` (15n). Run it ONCE at the
  end (plus the two test files' targeted runs while iterating). Quote the full
  summary line AND every `FAILED` / `ERROR` line verbatim. Bound every wait
  (`timeout 900`).
- If the closing suite shows teardown ERRORs naming a shared-repo path, check
  the ledger for a concurrent refresh in the window and say so — a peer session
  merges and refreshes on main concurrently today; with this lane's mechanism a
  ledgered one must print as EXTERNAL instead.

## Files

Yours: `Ortho4XP/tests/conftest.py`, `Ortho4XP/tools/harness/shared_repo_guard.py`, `Ortho4XP/tools/harness/build_airport.py`, `Ortho4XP/tests/test_harness.py`

## RULINGS

## 2026-09-15ay v2insetreprobe MERGED (5b4ea55e): a capability-free provider's `no-coverage` is re-probed ONCE PER ENGINE VERSION (owner 15aq (4)); 19 stale Phoenix negatives named; the harness names them under `dem` and never fetches

Lane `v2insetreprobe` (2811624a). One predicate,
`negative_is_version_stale(record, code, definition, bbox)`: true only
for a `no-coverage` of a provider with NO required capability, whose
declared coverage box reaches the airport, recorded under a version ≠
the running one (an out-of-box negative is re-derived from the boxes
and never re-asked, so a release churns no index). `run_capability_
record` now stamps capability-free providers too (`{"engine": v,
"capabilities": []}` in the index's existing `capabilities` JSON — no
new file, no new key; the unstampable record was WHY the negative was
permanent). The provider loop's third door beside `refresh` and
`unverified` logs both versions and re-stamps whatever the answer;
13b's door untouched; `is_cached` is False for a tile carrying one;
`engine_version()` public. Harness: `unverified_inset_negatives` names
a version-stale capability-free negative under `dem` with both
versions and `--refresh-data dem`, never fetching (imported predicate).
Measured read-only at engine 1.50.1788: +33-113 16, +33-112 3 (the 19 of
15q's 20 not already cleared by 15au's KPHX refresh). Twins (a)–(f);
`test_legacy_caches_without_recorded_box_are_reused` re-stamped (its
unstamped negative was re-asked once — the law working). Merge conflict
in `tests/test_harness.py` (both sessions append twins; kept both).
Suite ON MAIN: `1877 passed, 1 skipped, 1 xpassed`, 0 failed. NOTED,
not mine: the SUITE's session detector has no external-candidate
downgrade (unlike the build audit's `BuildInputScope`), so a concurrent
authorised refresh lands as teardown ERRORs in any suite running at the
time (18 today, twice) — chip-worthy.

## 2026-09-15n v2drapedbind MERGED (32f338a3): the object stage no longer dies on a draped page beside a solid body — `placement_geom._draped_components` was never bound to `_LineCutter`

The owner's LGAV tile build (2026-09-14 23:14, engine 1.50.1785; the bug
is in 1.0.340 too) logged `[v2 rebake] LGAV: placement failed
('_LineCutter' object has no attribute '_draped_components'); continuing`
and skipped the whole object stage. Mechanism: the §16d (1) readings
were moved from `placement_cut._LineCutter` to `placement_geom.py`; three
were re-bound as delegates, the fourth (`_draped_components(self, drp)`,
:202) was not, and `written_components` :157 called it as a method. Lane
`v2drapedbind` (b23a0c6f): the direct module call at :157 (a private
helper with one caller); reachability census of every `def name(self`
in the file; twin `test_16d_1_written_components_reads_a_draped_page_
beside_a_solid_body` (fails with the owner's exact AttributeError when
reverted). Offline proof on the owner's own LGAV rebake plan through
`tools/obj8_split_report.py`: main arm rc 1 at the AttributeError; the
branch rc 0, 184 placements, 166 split into 1,095 files, plan stage
8.16 s, shared repo UNCHANGED (frames registered). Suite ON MAIN after
the merge (`venv/bin/python -m pytest tests/auto_patch_v2
tests/test_harness.py`): `1571 passed, 1 skipped, 42 warnings, 2 errors`
— the two are `test_harness.py` TEARDOWN errors from the shared-repo
write detector naming `Airport_mod_cache/Global Airports/o4_v2_partition
_+33-112.cache`, written by the owner's app worker building KPHX at that
moment (pid 52401 at 98 % CPU); `tests/test_harness.py` alone: `358
passed`, 0 errors (the known app-builds-cross-attribute class). NOTE: the
bare `venv/bin/pytest` entry does not put the cwd on `sys.path` and 23
modules fail collection with `No module named 'tests'`; the working
invocation is `venv/bin/python -m pytest`.

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

