# #843 step 8 (B3-11d): named stage functions

Branch `claude/project-thread-g7d6rw-843-stages`, worktree `/home/user/wt-843-stages`.
Spec: `v2-stage-cache-spec.md` §4b.3 (prefix), §4b.5 (late stage split),
§4b.6/§4b.7 (emit/verify stages), §4b.1 (assembly module), §10 step 8, §13.

Do (byte-identical refactor, no behaviour change):
- `pipeline/prefix.py` `run_prefix(airport, cl, law, inputs, pack, cache) ->
  PrefixRecord`: the build's prefix (`build_planar` → `flat_site` →
  `preferred_road_z` → target channels → `shape_stage` → `shape_constraints` →
  `jetway_strips` → `hold_pass`) as ONE named function, replacing `build()`'s
  `_ribbon_free` closure (`build.py:1205`) and the replay tool's copy
  (`tools/v2_solve_replay.py:2326`); the main build's own prefix, the ribbon-free
  pass (`stage_one_problem`), the late stage's derives and the replay tool all
  call it. Keep front-cache reads/writes (`pipeline/front_cache.py`, #928)
  exactly where they happen today, i.e. the main pass still hits/misses the
  front cache identically; the prefix re-runs keep whatever cache behaviour
  they have today (making them go through the cache is step 9).
- `pipeline/emit_stage.py`: the post-solve glue in `build.py`
  (`with_pin_yield`, `displacement_by_role`, ground envelope, runway profile,
  road agreement, shore weld, natural shore) and emit (graded_surface,
  publication, write_patch, tile pieces, rebake screen).
- `pipeline/verify_stage.py`: the in-build census call and its report lines.
- `late_stage.run_last_stages` split into cut / derive / solve functions (its
  docstring (i)–(iii)); `run_last_stages` stays as the sequence.
- `water_exempt` / `seam_exempt` (+ the other post-passes if clean) move from
  `constraints/__init__.py` to `constraints/assembly.py`; `generate()` keeps
  its signature and result.
- `build.py` shrinks to the stage sequence. Update `stage_code.py`
  ENTRY_MODULES / CODE_MODULES only where an existing stage's closure moves.
- Proof: every existing build / replay / late-stage / publication twin green,
  plus a synthetic-airport build before vs after with byte-identical patch,
  sidecar and report (minus clocks). Report `build.py` before/after line count.
Another lane is, in parallel on `claude/project-thread-g7d6rw`, removing the
globals `feasibility.HARD_CONFLICT` / `no_step.RUNWAY_FLEX` (threading them as
arguments through late_stage / publication / build). Do not do that part; move
the code as it is, and expect a merge with it later.
Gate (master, corpus): HECA + CYXY byte-identical vs main; replay twins.
