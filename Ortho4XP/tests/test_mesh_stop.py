"""Cancellation tests for the Triangle4XP mesh subprocess driver.

Regression: a Stop click during Step 2 did nothing until triangulation
finished, because the stdout ``readline`` loops in ``O4_Mesh_Utils``
blocked until the external ``Triangle4XP`` / ``moulinette`` child exited;
``UI.red_flag`` was only checked afterwards.  ``_run_triangulation_process``
now polls ``UI.red_flag`` once per output line and terminates the child
mid-run.

Headless: the "triangulation" is a plain ``sys.executable -c`` dummy that
prints lines in a sleep loop — no network, no Triangle4XP binary.  The
cancellation flag is raised from a timer thread, exactly as a GUI Stop
click sets it from the main thread while the build worker is blocked in
the driver.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Mesh_Utils as MESH  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

# A child that prints a line every 50 ms forever (until terminated).  The
# explicit flush makes each line reach the parent's readline promptly so a
# raised red_flag is observed within one interval.
_SLOW_CHILD = (
    "import sys, time\n"
    "while True:\n"
    "    sys.stdout.write('tick\\n')\n"
    "    sys.stdout.flush()\n"
    "    time.sleep(0.05)\n"
)

# A child that prints a few lines and exits cleanly.
_QUICK_CHILD = (
    "import sys\n"
    "for i in range(3):\n"
    "    sys.stdout.write('line %d\\n' % i)\n"
    "sys.stdout.flush()\n"
)


@pytest.fixture(autouse=True)
def _reset_red_flag():
    """``UI.red_flag`` is a module global shared by every test; leave it
    False on the way in and out so a set flag here cannot leak into
    another test."""
    UI.red_flag = False
    yield
    UI.red_flag = False


def test_run_triangulation_process_stops_on_red_flag():
    """A red_flag raised mid-run terminates the child and returns promptly,
    long before the (otherwise endless) child would have finished."""
    mesh_cmd = [sys.executable, "-c", _SLOW_CHILD]

    timer = threading.Timer(0.5, lambda: setattr(UI, "red_flag", True))
    timer.start()
    try:
        started = time.time()
        process = MESH._run_triangulation_process(mesh_cmd)
        elapsed = time.time() - started
    finally:
        timer.cancel()

    assert UI.red_flag is True
    # Returned quickly after the flag (0.5 s timer + up to a 2 s
    # terminate grace period), NOT after the endless child ran out.
    assert elapsed < 5, f"driver blocked for {elapsed:.2f}s after Stop"
    # The child is dead, not merely detached.
    assert process.poll() is not None


def test_run_triangulation_process_completes_normally():
    """With no Stop request the driver drains the child to EOF and the
    child exits successfully — the pre-existing non-cancelled behaviour."""
    mesh_cmd = [sys.executable, "-c", _QUICK_CHILD]

    process = MESH._run_triangulation_process(mesh_cmd)

    assert process.wait(timeout=5) == 0
    assert UI.red_flag is False


def test_terminate_mesh_process_is_idempotent_on_dead_child():
    """Terminating an already-exited child is a harmless no-op."""
    process = MESH.subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdout=MESH.subprocess.PIPE,
        **UI.external_tool_keyword_arguments(),
    )
    assert process.wait(timeout=5) == 0
    # Must not raise even though the child is already gone.
    MESH._terminate_mesh_process(process)
    assert process.poll() is not None
