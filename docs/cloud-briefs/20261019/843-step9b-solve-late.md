# #843 step 9b (B3-11e, part 2 of 3): solve, late_cut and late_solve records

Branch `claude/project-thread-g7d6rw-843-backhalf`, worktree `/home/user/wt-843-backhalf`,
on top of step 9a (head 945798e). Read 9a's API first: `pipeline/back_cache.record(fc, stage,
inputs, fn, *, code=None, codec=PICKLE, check=None)`, `pipeline/constraint_records.py`,
`front_cache.py`, `stage_cache.py`. Use `record()` for every new record; do not add a
second record mechanism.
Spec: `v2-stage-cache-spec.md` §4b.4 (solve: output record, inputs, code incl. the callback
modules, the four witnesses = THE CERTIFICATE via `check=`, not-cached-when, determinism),
§4b.5 (late_cut / late_solve per pass; `cs_full` and the derive's ShapeStage as REFERENCES),
§4b.3 (`hold_pass` is a solve input, never a record), §8 T7, T8 (solve-only / late-only miss
arms), T9 (c), T10 for solve + late, T12 (`Options(time_limit_s=…)` → `bypass: time_limit`),
T13 (resume after the assembly), §9 (7)–(9). RULINGS 18d: if T7 (two cold builds in two
processes byte-identical) fails, the twin becomes "a hit equals the build that wrote it" and the
difference is recorded as a finding, not a stop.
- `stage_code.ENTRY_MODULES`: `solve`, `late_cut`, `late_solve` with their declared closures.
- The solve record's inputs name the assembly by KEY (18e key chaining for constraints).
- Another lane does emit + verify in parallel on `claude/project-thread-g7d6rw-843-emit`
  (from 945798e). Keep your build.py / stage_code.py diff local to the solve and late-stage
  calls so the two merge cleanly.
Gate (master, corpus): HECA + CYXY cold vs full hit vs solve-only-miss vs late-only-miss
byte-identical; T7 on HECA (two `--no-ledger` cold builds).
