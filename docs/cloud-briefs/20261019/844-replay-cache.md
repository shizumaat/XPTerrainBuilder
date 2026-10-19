# #844 (B3-12): v2_solve_replay reads and writes the v2 stage cache

Branch `claude/project-thread-g7d6rw-844`, worktree `/home/user/wt-844`.
Spec: `v2-stage-cache-spec.md` §7 (`tools/v2_solve_replay.py` bullets, both),
§8 replay twin, §9 (6); issue #844. Front-half cache: `pipeline/front_cache.py`,
`airport/stage_cache.py` (#928).

Do:
- `--capture` writes the front-half stage entries (classify, planar, flat_site,
  road_profile, shapes) into the stage cache as the build does, through the same
  functions (`front_cache`), never a second writer. `write_cache=False` paths
  stay read-only (the topology_cache rule); capture is the one replay path that
  writes, behind an explicit flag if the spec's "MAY" leaves it open (say which).
- `--replay --from constraints` can be served its inputs from the stage cache
  (by airport + key) when no pickle is given / when asked; the
  `capture_state.missing/refusal` refusals by field name are kept — a cache
  entry without the registries record is a `missing()` refusal.
- `--why-miss`: per record, the first recipe field that differs from the
  requested key, extending `partition_cache.peek` / `stage_cache` peek (one
  implementation; do not fork peek).
- `tools/INDEX.md` row for `v2_solve_replay.py` updated in the same commit.
- Twins (synthetic, no corpus): capture writes entries, a second capture or a
  replay is served them; `--why-miss` names the changed field (code digest, law,
  input); a stripped registries record refuses by field name.
Do NOT touch the replay tool's `_ribbon_free` prefix copy (~line 2326): another
lane replaces it with `pipeline/prefix.run_prefix` in parallel. Keep your diff
out of that function.
Gate (master, corpus): a registered HECA capture (`tools/harness/frames.py list
HECA`) replayed `--from constraints` with and without the cache gives identical
rows/columns.
