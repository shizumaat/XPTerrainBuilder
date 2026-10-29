"""#1624: ``RunDone`` counts each tile by its LAST attempt.  A tile that
failed on an unmounted-drive link, was re-queued after the user replaced
the link (#695), and then built is built — not also failed."""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import events as EV  # noqa: E402
from o4_engine import parallel  # noqa: E402
from o4_engine.session import last_outcome_counts  # noqa: E402


def test_retried_tile_that_builds_is_not_counted_failed():
    last_ok = {}
    for tile in [(30, 31), (30, 32)]:
        last_ok[tile] = False          # first attempt: the link fails
    for tile in [(30, 31), (30, 32)]:
        last_ok[tile] = True           # the retry builds
    last_ok[(29, 31)] = False          # a tile whose last attempt failed
    assert last_outcome_counts(last_ok) == (2, 1)


def test_parallel_run_done_reports_last_outcomes():
    emitted = []
    session = SimpleNamespace(_emit=emitted.append,
                              _run_finished=lambda: None)
    run = parallel.ParallelBuildRun.__new__(parallel.ParallelBuildRun)
    run._lock = parallel.threading.Lock()
    run._finished = False
    run._queue = []
    run._children = []
    run._cancel_all = False
    run._session = session
    run._done, run._errors = 6, 6      # six failures, six retries built
    run._last_ok = {(30, lon): True for lon in range(6)}
    run._maybe_finish()
    done = [e for e in emitted if isinstance(e, EV.RunDone)][-1]
    assert (done.done_count, done.error_count) == (6, 0)


def test_qt_box_title_skips_requeued_failures():
    """Twin of the Mac report title (TileFailureTests)."""
    import O4_Qt_Tile_Failures as QTFAIL
    import O4_Tile_Failures as FAIL
    from o4_engine import session as SESSION

    def failed(lon):
        return SESSION.build_done(30, lon, False, [FAIL.record(
            "elevation_download_failed", "refused")])

    fixed = [failed(lon) for lon in range(6)]
    still = failed(9)
    title = QTFAIL.box_texts(fixed + [still],
                             requeued={id(e) for e in fixed})[0]
    assert title == "1 tile was not built"
    title = QTFAIL.box_texts(fixed, requeued={id(e) for e in fixed})[0]
    assert title == "Every tile was built"
