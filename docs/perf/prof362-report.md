# prof362 — OTHH build profile (issue #362) — PRELIMINARY (run 3 in flight)

Tree: main `56e67443`, worktree `.claude/worktrees/prof362`, quiet machine
(no other python / build / pytest; top process < 3 % CPU before each run),
foreground-equivalent (nice 0 verified), `--no-ledger`. Patch sha1 identical
in all runs and to sweep `sw1034_OTHH`: `4d59e868…`.

## Stage walls (s)

| stage | run 1 cold, cProfile | run 2 warm (partition HIT), plain | sw1034 (loaded, cold) |
|---|---|---|---|
| load | 54.2 | 24.6 | 29.4 |
| pack partition | 551.9 (MISS+WROTE) | 50.3 (HIT) | 519.2 |
| planar | 1109.9 | 982.3 | 1008.2 |
| – door wells | 612.5 | 583.0 | — |
| – sunken roads | 37.5 | — | — |
| – wall corridors | 179.5 | 120.3 | 122.3 |
| constraints | 135.7 | 71.4 | 73.9 |
| solve (incl. 2nd planar pass) | 552.0 | 380.7 | 392.1 |
| emit | 29.0 | 21.9 | 22.9 |
| rebake plan | 292.6 | 282.4 | 292.4 |
| verify | 53.6 | 26.2 | 27.2 |
| TOTAL | 2839.2 | 1894.5 | 2419.5 |

## Instrument defect found (run 1 profile is NOT usable for cumulative times)

Python 3.14 `cProfile` rides `sys.monitoring`, which fires in EVERY thread;
the engine's 1 s `o4-heartbeat` thread (`src/auto_patch/progress.py:440`)
pushes/pops on the profiler's single context stack. Result in run 1:
`pipeline/build.py:555(build)` reads 376 s cumulative for a 2,839 s build,
564 s of main-thread C time is booked to `_thread.lock.acquire`. ncalls and
short-call tottime are sound; cumulative times of long frames are not.
RUN 3 (in flight) repeats the cold profile with the heartbeat thread not
started (scratch runner, no engine edit) and observation shims on the
door-well reads.

## App vs harness (reasoned from logs, frozen engine NOT run — the app's
object stage rewrites the pack in the X-Plane install; no safe way)

App OTHH 5,204 s (`engine-stderr.log` line 66377). The same log shows the
OTHH tile interleaved with tiles −13−078 (SPJC), +30+031 (HECA), +40−004
(LEMD, 1,593 s) and +39−107 (KASE/KEGE) — mesh, masks, DSF encode and other
auto-patch builds ran at the same time, and OTBD/OTBH ran in the same tile.
App partition 487 s vs harness 519–552 s (same); app HECA 776.7 s vs sweep
711 s (1.09×). Verdict: contention, not the frozen interpreter.

(full analysis follows in the final version)
