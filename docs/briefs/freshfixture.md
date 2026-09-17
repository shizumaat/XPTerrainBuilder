# Brief pack — lane `freshfixture`

Base: main `d5158ae0` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Repair the three rotted freshness tests and put the file in the standing suite

## The brief

## Lane freshfixture — three RED tests on main are FIXTURE ROT (scout 2026-09-17, measured)

Run from Ortho4XP/: `venv/bin/python -m pytest tests/test_auto_patch_freshness.py -q -p no:cacheprovider -rfE` → 3 failed, 71 passed:
test_generate_then_regenerate_reuses, test_lazy_inputs_resolved_once_on_rebuild,
test_no_apt_dat_neighbour_does_not_block_a_buildable_airport — all
"AutoPatchBuildFailure … KFAK (build): [v2] KFAK: no apt.dat under xp_root" (driver.py:1221).

First red: 3bf14c5f (2026-09-13, v1 retirement stage A). It removed the engine
guard, leaving an unconditional `return _engine_v2.build_write_verify_one_v2(task,
_WORKER_DEM)` at src/auto_patch/driver.py:732; everything below it (incl. the
`pipeline.build_airport_pavement` import the tests stub, driver.py:746-747) is dead
code. The helper `_drive_generate` (tests/test_auto_patch_freshness.py:800-849) stubs
that dead v1 entry and hands v2 the literal string "xp_root". The LAW is intact: the
failing neighbour test's own stdout shows KNON "skipped, not built", and
test_no_apt_dat_airport_is_skipped_not_fatal (:951) passes.

Do:
1. In `_drive_generate` (:828-836) and the neighbour test (:986-993) stub the v2 step
   instead — `monkeypatch.setattr(driver._engine_v2, "build_write_verify_one_v2",
   _stub)` where `_stub(task, dem)` writes the patch via
   `PavementLayout(...).to_osm(task["auto_patch_file"])` with `layout.freshness =
   task["freshness"]` (to_osm also writes the .axes.json sidecar) and returns
   {"icao": icao, "ok": True, "summary": "stub"}. tests/test_auto_patch_engine_dispatch.py:92
   `_stub_v2` is the richer donor pattern if you want the real adapter in the loop —
   your call, say which and why. The three tests' ASSERTIONS must not be weakened.
2. Add tests/test_auto_patch_freshness.py to the STANDING SUITE wherever it is
   defined (find the ONE definition: grep "test_role_edge_census" across the CLAUDE.md
   files, tools/, docs/ and any runner script; extend that list, never fork it) so the
   file cannot rot unseen again.
3. If the dead code below driver.py:732 has no other caller (census: grep every symbol
   it imports or defines), delete it in its own commit; if anything still reaches it,
   leave it and report what.

Closing: the file 74 passed; tests/test_auto_patch_engine_dispatch.py green; whatever
`tools/blast.py src/auto_patch/driver.py` names; the standing suite once, FAILED lines
verbatim. Not a law lane: no airport build. Worktree: from Ortho4XP/,
`tools/harness/lane_worktree.sh up freshfixture`. Release Xcode only; never quit the
owner's app, never run make_app/make_engine. Commit early; no merge, no push. Do not
touch .github/workflows/ci.yml (lane betaci owns it) — if the standing suite turns out
to be defined there, report instead of editing.

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

