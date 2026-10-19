# #843 step 9c (B3-11e, part 3 of 3): emit and verify records

Branch `claude/project-thread-g7d6rw-843-emit`, worktree `/home/user/wt-843-emit`, on top of
step 9a (head 945798e). Read 9a's API first: `pipeline/back_cache.record(fc, stage, inputs, fn,
*, code=None, codec=PICKLE, check=None)`, `pipeline/constraint_records.py`, `front_cache.py`,
`stage_cache.py`. Use `record()` for every new record; do not add a second record mechanism.
Spec: `v2-stage-cache-spec.md` §4b.6 (emit: the FILE BODIES + sha, `surf`/`pub`, emit-side
report keys; the `header_extra` split — `write_patch` takes the rendered body and the header,
header applied on every write, hit or miss; if the split is not clean, `header_extra` joins the
key and you report it), §4b.7 (verify: report + DEFECT/under-floor lines re-printed verbatim on
a hit, the body witness: patch + sidecar on disk re-hash to the bodies it judged; RULINGS 18c(2)
cached under that witness), §4b.8 report.json, §7 (`cfg.verify=False` → neither run nor served
nor written), §8 T8 (emit-only / verify-only miss arms), T9 (d) (e), T10 for emit + verify.
Stage functions are `pipeline/emit_stage.emit` and `pipeline/verify_stage.verify` (step 8).
- `stage_code.ENTRY_MODULES`: `emit`, `verify` with their declared closures.
- Emit's inputs: until step 9b lands (in parallel, on `claude/project-thread-g7d6rw-843-backhalf`)
  the solve is not a record, so digest the final `pm`, `z`, `design`, constraint set (by the
  assembly KEY from 9a when there is no late stage), strips, hard_conflict, runway_flex,
  hold_report, Airport digest, `cfg.feather_m` directly as §4b.6 lists. Keep your build.py /
  stage_code.py diff local to the emit and verify calls so the two branches merge cleanly.
Gate (master, corpus): HECA + CYXY cold vs full hit vs emit-only-miss vs verify-only-miss
byte-identical (patch, sidecar, tile pieces, graded, rebake screen).
