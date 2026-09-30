"""Issue #122 probe plugin: a per-test stack dump written to a FILE.

Loaded by .github/workflows/win-hang-122.yml as ``-p hangdump122``.  An
xdist worker's stderr never reaches the Windows job log, so pytest-timeout's
dump of a hung worker is lost; this writes the same evidence to
``$HANGDUMP_DIR/hangdump-<worker>-<pid>.log``:

* ``faulthandler.dump_traceback_later(HANGDUMP_AFTER, repeat=True)`` — C-level,
  fires even when the GIL is held by a wedged extension call;
* a watchdog thread at ``HANGDUMP_AFTER + 5`` s — thread NAMES, Python stacks,
  the process's open files and its child processes (psutil, when present).
"""
import faulthandler
import os
import sys
import threading
import time
import traceback

import pytest

_DIR = os.environ.get("HANGDUMP_DIR", ".")
_AFTER = float(os.environ.get("HANGDUMP_AFTER", "240"))
_FILE = []


def _f():
    if not _FILE:
        wid = os.environ.get("PYTEST_XDIST_WORKER", "main")
        path = os.path.join(_DIR, "hangdump-%s-%d.log" % (wid, os.getpid()))
        _FILE.append(open(path, "a", buffering=1, encoding="utf-8"))
    return _FILE[0]


def _watch(nodeid):
    f = _f()
    f.write("\n=== WATCHDOG %s still in %s\n" % (time.strftime("%H:%M:%S"), nodeid))
    names = {t.ident: (t.name, t.daemon) for t in threading.enumerate()}
    for ident, frame in sys._current_frames().items():
        f.write("--- thread %s %r\n" % (hex(ident), names.get(ident)))
        f.write("".join(traceback.format_stack(frame)))
    try:
        import psutil

        me = psutil.Process()
        f.write("--- open files: %r\n" % (me.open_files(),))
        for child in me.children(recursive=True):
            try:
                f.write("--- child %d %s %r status=%s cpu=%r\n" % (
                    child.pid, child.name(), child.cmdline(), child.status(),
                    child.cpu_times()))
            except Exception as exc:
                f.write("--- child %d: %r\n" % (child.pid, exc))
    except Exception as exc:
        f.write("--- psutil: %r\n" % (exc,))
    f.flush()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    f = _f()
    f.write("START %s %s\n" % (time.strftime("%H:%M:%S"), item.nodeid))
    f.flush()
    faulthandler.dump_traceback_later(_AFTER, repeat=True, file=f)
    timer = threading.Timer(_AFTER + 5, _watch, args=(item.nodeid,))
    timer.daemon = True
    timer.name = "hangdump122-watchdog"
    timer.start()
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
        timer.cancel()
        f.write("END   %s %s\n" % (time.strftime("%H:%M:%S"), item.nodeid))
        f.flush()
