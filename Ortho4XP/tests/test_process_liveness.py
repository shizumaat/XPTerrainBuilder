"""#83: the pid-liveness probe is a probe on every platform.

``os.kill(pid, 0)`` on Windows is ``GenerateConsoleCtrlEvent`` (CTRL_C_EVENT
is 0): it raised for a dead pid, the band lock never read its owner dead,
and the stale-lock test polled until pytest-timeout killed the xdist worker.
"""

import os
import subprocess
import sys

import O4_Process_Liveness as PROC


def test_own_process_is_alive():
    assert PROC.pid_is_alive(os.getpid()) is True


def test_a_reaped_child_is_dead():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    # The Popen still holds its handle on Windows: the process OBJECT
    # exists, the process does not.  Must read dead, not undeterminable.
    assert PROC.pid_is_alive(child.pid) is False


def test_a_running_child_is_alive_and_is_not_signalled():
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert PROC.pid_is_alive(child.pid) is True
        assert child.poll() is None, "the probe must not kill its target"
    finally:
        child.kill()
        child.wait()


def test_nonsense_pids_are_undeterminable():
    assert PROC.pid_is_alive(0) is None
    assert PROC.pid_is_alive(-5) is None
    assert PROC.pid_is_alive("not a pid") is None


def test_no_engine_liveness_probe_uses_os_kill_signal_zero():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("src/O4_Bathymetry_Band.py", "src/o4_engine/jsonl.py"):
        with open(os.path.join(here, rel), encoding="utf-8") as handle:
            source = handle.read()
        assert ", 0)" not in "".join(
            line for line in source.splitlines()
            if "os.kill(" in line and not line.lstrip().startswith("#")), rel
