"""#695: a tile that fails with a cause the user can fix (#668: its Custom
Scenery folder is a link to an unmounted drive) is asked AS SOON AS it
fails, one choice at a time, and "Remove the link…" re-queues it into the
RUNNING build; the run's box still lists it, as "Fixed and re-queued."
Twin of the mac app's ``LinkFixQueueTests`` (TileFailureTests.swift)."""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Qt_Link_Fix as QTLINK  # noqa: E402
import O4_Qt_Tile_Failures as QTFAIL  # noqa: E402
import O4_Tile_Failures as FAIL  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402


def _behind(lat, link):
    return SESSION.build_done(lat, -78, False, [FAIL.record(
        "output_link_unmounted", "x", link=link,
        target="/Volumes/Drive/t", volume="Drive")])


def _full():
    return SESSION.build_done(1, 2, False, [FAIL.record("disk_full", "d")])


def test_the_module_imports_no_qt_above_the_rule():
    source = open(QTLINK.__file__, encoding="utf-8").read()
    assert source.index("# --- Qt ---") < source.index("from PySide6")


def test_two_failures_queue_one_at_a_time():
    queue = QTLINK.LinkFixQueue()
    first, second = _behind(-12, "/a"), _behind(-13, "/b")
    assert queue.offer(first) and queue.offer(second)
    assert not queue.offer(first)           # never asked twice at once
    assert not queue.offer(_full())         # a cause not fixable here
    assert queue.current == (first, "/a") and len(queue.waiting) == 1
    assert queue.answer() == (first, "/a")
    assert queue.current == (second, "/b")
    queue.answer()
    assert queue.idle() and queue.answer() is None
    (title, text) = QTLINK.box_texts(first)
    assert title.startswith("Tile -12-078 was not built")
    assert "\n\n" in text


def test_the_run_box_marks_a_requeued_failure_and_offers_it_no_button():
    first, second = _behind(-12, "/a"), _behind(-13, "/b")
    (_title, body, _detail) = QTFAIL.box_texts([first, second], {id(first)})
    assert body.count(QTFAIL.REQUEUED_LINE) == 1
    assert body.index(QTFAIL.REQUEUED_LINE) < body.index("-13-078")
    assert [l for (_e, l) in QTFAIL.removable_links(
        [first, second], {id(first)})] == ["/b"]
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "TileFailure.swift")
    if os.path.exists(swift):
        with open(swift, encoding="utf-8") as handle:
            assert '"%s"' % QTFAIL.REQUEUED_LINE in handle.read()


# --- the window ----------------------------------------------------------
@pytest.fixture
def window(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    import O4_Qt_GUI as GUI
    import O4_UI_Utils as UI

    QApplication.instance() or QApplication([])
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def test_a_mid_run_failure_asks_at_once_and_requeues_into_the_run(
        window, monkeypatch):
    import O4_Unmounted_Links as UNMOUNTED

    removed, queued = [], []
    monkeypatch.setattr(UNMOUNTED, "remove_link", removed.append)
    monkeypatch.setattr(window, "_queue_into_running_build",
                        lambda todo, *args: queued.append((todo, args)))
    window._building = True
    settings = {"provider": "BI", "zoomlevel": 16, "do_vector": True,
                "do_imagery": True, "do_overlays": False}
    window._run_settings[(-12, -78)] = dict(settings)
    first, second = _behind(-12, "/a"), _behind(-13, "/b")
    window._on_build_done(first)
    box = window._link_fix_box
    assert box is not None and box.isVisible()       # before any RunDone
    window._on_build_done(second)
    assert window._link_fix_box is box               # no second box
    remove = next(b for b in box.buttons()
                  if b.text() == QTFAIL.REMOVE_LINK_BUTTON)
    remove.click()
    assert removed == ["/a"]
    assert queued == [([(-12, -78)], ("BI", 16, True, True, False))]
    assert window._link_fix_box is not None          # the second, now
    assert window._link_fix_box is not box
    # the run ends while the second choice is on screen: its box waits
    window._show_issues_box([first, second])
    assert window._deferred_issue_events == [first, second]
    cancel = next(b for b in window._link_fix_box.buttons()
                  if b.text() == QTLINK.CANCEL_BUTTON)
    cancel.click()
    assert window._link_fix_box is None
    assert window._deferred_issue_events is None
    run_box = window._pack_art_boxes[-1]
    assert QTFAIL.REQUEUED_LINE in run_box.informativeText()
