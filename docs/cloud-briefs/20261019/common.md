## Common rules (every stage-cache cloud lane, 2026-10-19)

Owner approval: Noah approved the v2 stage-cache work (#842 → #843 → #844 → #879/#880)
in the project chat on 2026-10-19 ("All your recommendations for queued bugs and
features to start on when the usage resets are approved").

- Read first: root `CLAUDE.md`, `Ortho4XP/CLAUDE.md` (BUILD ECONOMY is law),
  `Ortho4XP/src/auto_patch/CLAUDE.md` if you touch the engine,
  `docs/cloud-briefs/20261018/coordination.md`, and the spec
  `Ortho4XP/docs/specs/v2-stage-cache-spec.md` (the sections named below).
  Rulings: `Ortho4XP/tools/docq.py ruling 2026-10-18b` … `18g` (18e: constraint
  records use the PR #918 codec, never pickle; 18d: if two cold builds differ,
  a hit equals the build that wrote it).
- This is a CLOUD container: no corpus, no `/Users/noah/XPTerrainBuilderData`,
  no airport builds. Work code + synthetic twins only. Every closing build the
  spec names (HECA, CYXY byte-identity, `check_build_time.py --runs 3`) is the
  Mac master's: list each one, exactly as a command, in the PR body section
  "For the master (corpus)". Never fake or estimate a corpus number.
- Python: `Ortho4XP/venv/bin/python` (run from `Ortho4XP/`). Before editing a
  file under `src/`: `venv/bin/python ../tools/blast.py <file>` (root `tools/`).
  Before adding a function: `blast.py --find <kw>`.
- Byte-identical refactor = no behaviour change. Prove it with the existing
  twins of every module you touch plus a synthetic-airport build twin where
  one exists (`grep -rln "synthetic" tests/auto_patch_v2 | head`).
- Before you report done: merge current `origin/main`; run
  `venv/bin/python ../tools/ratchets.py` (all, lint included) — it must not
  regress; run the whole-tree twins: `test_windows_text_io`,
  `test_patch_env_classification`, `test_tile_failures`,
  `test_console_encoding`, `test_stage_code_closure`, `test_step_code_closure`,
  `test_stage_registries`, `test_no_airport_specific_code`; plus every test file
  blast lists for the files you changed. Grep every caller of a signature you
  change, corpus-skipped twins included.
- A new import inside a stage changes that stage's code closure:
  update `pipeline/stage_code.py` and re-run `test_stage_code_closure`.
- Commit on your branch with clear messages ending with:
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01DPnKBPzSYzKsjq4UHSMHXG`
  Push with `git push -u origin <branch>` (retry on network error 2/4/8/16 s).
- NEVER: merge, open or edit PRs, comment on issues, create triggers/routines,
  call any `mcp__hearthbot__*` tool, or contact the owner. Report only to the
  session that launched you.
- A spec deviation you need is STOP-and-report (name it, why, the alternative),
  never decided by you. Convergence guards: at most 2 fix iterations per target.
- Final report (short): what landed (commits), tests run with pass counts,
  ratchets result, net lines added/removed, new public symbols, deviations,
  and the exact corpus commands for the master.
