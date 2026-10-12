# winpool570 — issue #570, Windows `teardown: process(es) still alive: [3336]`

Lane notes (2026-10-12). Branch `claude/winpool570`.

## What the log says (run 38278241886, job 114908882063, attempt 1)

Read from the whole failing section, not the summary:

| reading | value |
|---|---|
| pooled arm, in-bundle teardown read | `still alive: [3336]` after the full `LINGER_S` = 15 s poll |
| gate's outside read (after BOTH arms exited) | `after exit: 1 alive` after its own 15 s poll |
| gap between the two reads | the whole one-core arm, 13.6 s |
| so pid 3336 "alive" for | >= ~43 s after every pool had been closed, >= 28 s after the engine process that owned it had exited |
| in-bundle kill arm (parent hard-killed mid-map, 4 workers) | 0 workers alive after 0.2 s |
| outside kill arm (engine hard-killed, Manager + airport child + 3 workers) | 0 alive after 0.3 s |
| `_teardown_pool` "did not exit within" / "terminating it" lines | none |
| `FELL BACK` | none |
| wall | pooled 50.5 s (one-core 13.6 s); test 85 s = 50.5 + 13.6 + 15 + kill arm |
| suite around it | ~1,470 other tests completed on gw0–gw2 during those 85 s |

## Verdict

NOT the #140/#169 family (a read taken before a bounded teardown finished):
the read waited 15 s twice with 13.6 s between. And not a demonstrated
teardown gap: a worker that survives `terminate`, `kill` AND the death of
its parent (`pool.exit_with_parent`, proven on this same Windows run by both
kill arms in 0.2–0.3 s) for 43 s is not something the pool's code can
produce short of a process the kernel cannot end.

What the log does show is an INSTRUMENT that cannot tell: `alive(pid)`
opened "whatever process holds number 3336 now". A pid is recycled once its
holder ends — on Windows promptly — the run tracks 25 pids for 50–80 s, and
a 4-worker xdist suite was starting processes the whole time. The selfcheck
was reading a pid, not a process, and its failure text carried only the pid,
so the run could not be attributed either way. That is the finding: the
most likely reading is a recycled pid; the log cannot prove it, and the fix
makes the next occurrence decisive instead of arguable.

## What changed

1. `Ortho4XP/src/O4_Pool_Selfcheck.py` — WHO a pid is. `identity(pid)` =
   `(start time, command)` of the process holding the number now (Windows
   `GetProcessTimes` + `QueryFullProcessImageNameW`; Linux `/proc/<pid>/stat`
   field 22 + `cmdline`; macOS `libproc` — ctypes only, no child process, no
   new dependency). `stamp()` records `[born, command, role]` for every
   process the run starts WHILE it is known to run (workers in `answers()`
   with the pool open; each airport-pool child stamps itself; the victim
   stamps itself, its workers, the engine above it and its Manager).
   `alive(pid, born)` asks about THAT process. Failures name role and
   command (`named`); a pid now held by another process is printed
   (`recycled`) and is not an orphan. A process with no stamp is judged by
   pid alone, as before — never weaker.
2. `scripts/check_frozen_pool.py` — the outside reads use the stamps from the
   records (and stamp the victim engine themselves); failure text carries the
   names.
3. `Ortho4XP/src/auto_patch_v2/airport/pool.py` — `WorkPool.close` was
   bounded but not accounted for (the #140/#169 shape, never fixed here): it
   swallowed everything and returned silently whatever was left, and gave
   each worker its own second after each signal (5 + 2N s worst case). Now:
   terminate ALL, wait for all against ONE `SIGNAL_S` (2 s) deadline, kill
   the rest, wait again, and NAME any worker still running on a
   `[pool] teardown:` line. Worst case 5 + 2 + 2 s whatever the worker count.
   This is product hardening found while reading, not the cause of #570.

## Twins

- `tests/test_pool_selfcheck.py::test_a_pid_handed_to_another_process_is_not_this_runs_orphan`
  — the Windows behaviour INJECTED on every OS: a live process stands under
  the stamp of another. The blind read says alive; the identity read says
  not that process; a true survivor is still alive and named by role.
- `…::test_a_process_with_no_stamp_is_still_judged_by_its_pid`
- `tests/auto_patch_v2/test_pool.py::test_a_close_waits_out_a_slow_terminate_and_names_only_what_outlives_the_kill`
  (a worker that dies 0.3 s AFTER terminate returned is waited for, not
  killed, not named) and `…::test_a_close_is_bounded_by_the_deadlines_not_by_the_worker_count`.
- The existing source-entry run now asserts every started process carries a
  stamp with a start time and a role.

## Unverified until the PR's Windows CI

The `_windows_identity` ctypes branch has never executed: it was written
from the Win32 prototypes on macOS. The Windows job must show
`test_a_pid_handed_to_another_process…` and
`test_the_entry_runs_the_pool_from_source_and_the_gate_passes_it` green
(the second asserts `born is not None` for every stamped process, which is
`GetProcessTimes` answering). The Linux `/proc` branch is likewise first
run by CI. One green run does not prove the flake gone (it was 1 in an
unknown number of runs); what it proves is that the read is now by
identity. If a named survivor ever appears, that is a real orphan and the
line says which pool it belonged to.
