# failmsg562 — lane notes (issue #562)

## RESUME HERE

* Branch `claude/failmsg562`, worktree `.claude/worktrees/failmsg562`, base `aed288725`.
* PHASE 1 DONE: census in `docs/briefs/failmsg562-census.md` (45 rows, proposed copy, unsure rows listed).
* PHASE 2 NEXT (nothing written yet):
  1. `Ortho4XP/src/o4_engine/failures.py` — the catalogue (code -> what/why/remedy), `code_for_exception`
     (explicit `failure_code` attribute, else class name along the MRO, else errno), `fold`.
  2. `events.py` — additive `BuildDone.failures` (list of dicts) and `AutoPatchFailed.code`; protocol 1.10.
  3. `O4_UI_Utils.tile_failure(code, detail, **params)` hook + `code=` on `exit_message_and_bottom_line`;
     session collects and composes; `parallel.py` worker death carries `worker_died`.
  4. Per-airport records carry `code` (`auto_patch/engine_v2.py`, `auto_patch/driver.py`).
  5. Swift decode + render (`OrthoEngineClient.swift`, `BuildModel.swift`), Qt render.
  6. Twins: catalogue coverage of exception classes + annotated exits, fold, unmapped fallback; Swift decode test.
* Sibling lanes (`kpdx559`, `dump560`, `demfall561`) had pushed nothing when this lane started.
