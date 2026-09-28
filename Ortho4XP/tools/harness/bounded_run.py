#!/usr/bin/env python3
"""THE BOUNDED RUN — a deadline that kills the WHOLE command, children too.

    venv/bin/python tools/harness/bounded_run.py --deadline 3600 -- \\
        /usr/bin/time -l venv/bin/python tools/v2_solve_replay.py --capture OTHH --out X.pkl

WHY (#64, lane ``othhjunction`` 2026-09-25).  macOS ships no ``timeout``
binary, so lanes bounded long runs with ``perl -e 'alarm N; exec @ARGV'``.
Placed BEFORE ``/usr/bin/time`` the alarm is delivered to ``time`` (perl
exec'd into it): ``time`` dies, and the python it forked keeps running,
orphaned — a killed "dry" capture that is not dead.  An alarm only reaches
the process that exec'd; this tool does not depend on the order at all:
the command runs in its OWN SESSION (a new process group), and at the
deadline the whole group gets SIGTERM, then SIGKILL after ``--grace``
seconds.  ``time``, python and any subprocess python started (DSFTool, a
worker pool) share that group and die together.

Exit status: the command's own; ``124`` on a deadline (GNU ``timeout``'s
code), with ``TIMED_OUT after N s`` on stderr so an empty result is never
mistaken for a finished one.  SIGINT / SIGTERM to this wrapper are
forwarded to the group, so a cancelled wrapper leaves no orphan either.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

TIMED_OUT_RC = 124


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        # BSD/macOS returns EPERM where Linux returns ESRCH: the group is
        # still there but holds a process this uid may not signal.  There
        # is nothing to do about it and nothing to raise — the bounder's
        # job is to bound, not to guarantee the kill (#76).
        pass


def run_bounded(cmd: list[str], deadline_s: float, grace_s: float = 10.0,
                label: str = "") -> int:
    """Run ``cmd`` in its own process group; kill the GROUP at the deadline.

    Returns the command's exit status, or :data:`TIMED_OUT_RC`."""
    proc = subprocess.Popen(cmd, start_new_session=True)
    pgid = proc.pid                      # session leader: pgid == pid

    def _forward(signum, _frame):
        _signal_group(pgid, signum)

    old = {s: signal.signal(s, _forward) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            return proc.wait(timeout=deadline_s)
        except subprocess.TimeoutExpired:
            pass
        tag = f"[{label}] " if label else ""
        print(f"{tag}TIMED_OUT after {deadline_s:g} s — SIGTERM to process "
              f"group {pgid}", file=sys.stderr, flush=True)
        _signal_group(pgid, signal.SIGTERM)
        end = time.monotonic() + grace_s
        try:
            proc.wait(timeout=grace_s)
        except subprocess.TimeoutExpired:
            pass
        # the leader may be gone while a child still runs: probe the GROUP
        while time.monotonic() < end:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                break                    # ESRCH: the group is gone
            except PermissionError:
                # EPERM: the group EXISTS and we may not signal it, which
                # for a liveness probe reads ALIVE.  Linux raises ESRCH
                # here, so this arm only ever fires on BSD/macOS — where
                # letting it escape turned a correct TIMED_OUT into an
                # unhandled traceback and rc 1 instead of 124 (#76).
                pass
            time.sleep(0.05)
        _signal_group(pgid, signal.SIGKILL)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            pass
        return TIMED_OUT_RC
    finally:
        for s, h in old.items():
            signal.signal(s, h)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--deadline", type=float, required=True, metavar="SECONDS",
                    help="wall-clock bound; size it to the thing you run "
                         "(a build <= 900, a suite <= 600)")
    ap.add_argument("--grace", type=float, default=10.0, metavar="SECONDS",
                    help="SIGTERM -> SIGKILL grace (default 10)")
    ap.add_argument("--label", default="", help="prefix for the TIMED_OUT line")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="-- COMMAND [ARGS...]")
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        ap.error("no command: bounded_run.py --deadline N -- COMMAND ...")
    return run_bounded(cmd, a.deadline, a.grace, a.label)


if __name__ == "__main__":
    sys.exit(main())
