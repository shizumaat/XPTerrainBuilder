# #843 step 6 (B3-11b): the solve's side channels become record fields

Branch `claude/project-thread-g7d6rw`, worktree `/home/user/XPTerrainBuilder`.
Spec: `v2-stage-cache-spec.md` §3b rows `HARD_CONFLICT`, `RUNWAY_FLEX`, hold
report; §4b.4 output record; §10 step 6; §13 blast table.

Do:
- Delete the module globals `solve/feasibility.HARD_CONFLICT` and
  `constraints/no_step.RUNWAY_FLEX`. `solve_design` returns them (fields on
  `DesignReport`: `hard_conflict`, `runway_flex`), and returns the hold report
  (`model.platform.hold_report(pm.registries.held)` after the solve) as a field
  too, while still writing `registries.held` as today.
- `pipeline/late_stage.run_last_stages` / `run_late_stage` take the base
  `hard_conflict` and return the merged one (base + late solve), as lines
  379–441 do today through the global.
- `pipeline/publication` takes `hard_conflict` and `runway_flex` as arguments
  (delete `_hard_conflict()` / `_runway_flex()` global readers).
- `pipeline/build.py` and `tools/v2_solve_replay.py` thread them through.
- Update `pipeline/capture_state.py`'s census rows and T1's allow-list
  (`tests/auto_patch_v2/test_stage_registries.py`): both globals leave it.
- Twins: a synthetic case where the solve has a hard conflict and a runway flex
  shows both arriving in publication through the record (no global). Existing
  twins of design/feasibility/no_step/late_stage/publication green.
Gate (master, corpus): HECA + CYXY patch and sidecar byte-identical vs main
(BUILD ECONOMY: shared solve/emit-path change).
Do not touch `pipeline/build.py` beyond the threading (another lane is
splitting it into `prefix.py` / `emit_stage.py` / `verify_stage.py` in
parallel; keep your build.py diff small and local).
