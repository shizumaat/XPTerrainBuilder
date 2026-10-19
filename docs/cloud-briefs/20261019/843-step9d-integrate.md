# #843 step 9d: integrate 9b (solve + late) and 9c (emit + verify), close #843

Branch `claude/project-thread-g7d6rw-843-backhalf`, worktree `/home/user/wt-843-backhalf`.
The worktree is MID-MERGE: 9b's head db80304 with 9c's branch
`origin/claude/project-thread-g7d6rw-843-emit` (55e01ce) merged in; conflicts in
`pipeline/build.py`, `pipeline/prefix.py`, `pipeline/stage_code.py`,
`tests/auto_patch_v2/test_stage_code_closure.py`. Read the 9a/9b/9c briefs beside this file.
1. Resolve: both sides' records stand. Closures in `stage_code.py` are REGENERATED from the
   code, never hand-merged (`test_stage_code_closure` is the arbiter; same for
   `O4_Step_Code`).
2. Wire emit to 9b's records. 9c had to digest the whole late `cs_full` with the codec
   digest because it was not a record (cost on every HECA build, hits included). Now the
   late solve is a record: name the final constraint set (and the final `pm`/`z`/`design`)
   by the late record's KEY / output digest, as §4b.6 lists, and drop the whole-set digest
   path. Likewise the solve's design report can be named by the solve record instead of
   9c's `_untimed` digest of `design_rep.as_dict()` where that is cleaner — keep whichever
   keeps a full hit byte-identical; say which.
3. One synthetic test that runs the records end to end in order (constraints → jetway →
   solve → late if the fixture has one → emit → verify) with a full-hit arm byte-identical
   to cold, if the existing fixtures allow it without a corpus; else say why not.
4. Merge current `origin/main`. Full common-rules test set + every test file importing the
   touched modules + ratchets. Push.
5. Default: the cache stays ON by default as the front half already is (spec §6: on once
   twins and the closing build are green — the closing build is the master's).
Report as the common rules say, plus a consolidated "for the master" command list covering
9a/9b/9c (cold, full hit, the six single-miss arms of T8, T7, `--runs 3`).
