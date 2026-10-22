"""Custom Scenery changes rescan the Qt map by themselves (#1258), as the
Mac app's FileSystemWatcher does; neither app has a refresh button.

Offscreen; the watcher's debounce is shortened for the test.
"""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Scenery_Watcher as QTSCW  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _scenery(tmp_path):
    root = tmp_path / "X-Plane" / "Custom Scenery"
    root.mkdir(parents=True)
    (root / "scenery_packs.ini").write_text("I\n", encoding="utf-8", newline="")
    return root


def test_watched_paths_are_the_macs(tmp_path):
    root = _scenery(tmp_path)
    assert QTSCW.watched_paths(str(root)) == [
        str(root), str(root / "scenery_packs.ini")]
    disabled = root.parent / "Custom Scenery (Disabled)"
    disabled.mkdir()
    assert str(disabled) in QTSCW.watched_paths(str(root))
    assert QTSCW.watched_paths("") == []


def _wait_for(qapp, predicate, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not predicate():
        qapp.processEvents()
        time.sleep(0.01)
    return predicate()


def test_a_change_on_disk_fires(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QTSCW, "DEBOUNCE_MS", 100)
    root = _scenery(tmp_path)
    fired = []
    watcher = QTSCW.SceneryWatcher(lambda: fired.append(1))
    try:
        watcher.watch(str(root))
        (root / "zOrtho_A").mkdir()
        assert _wait_for(qapp, lambda: fired)
    finally:
        watcher.deleteLater()


def test_a_burst_of_changes_fires_once(qapp, monkeypatch):
    """The debounce itself, without the platform's event timing (macOS
    delivers a burst's events spread over more than a short debounce)."""
    monkeypatch.setattr(QTSCW, "DEBOUNCE_MS", 100)
    fired = []
    watcher = QTSCW.SceneryWatcher(lambda: fired.append(1))
    try:
        for _ in range(3):
            watcher._bump()
            qapp.processEvents()
        assert _wait_for(qapp, lambda: fired)
        _wait_for(qapp, lambda: len(fired) > 1, seconds=0.5)
        assert fired == [1]
    finally:
        watcher.deleteLater()
