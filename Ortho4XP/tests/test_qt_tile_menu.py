"""The tile right-click menu (issue #938), offscreen, and its launcher.

A right-click without a drag on the map asks for the tile's menu; a
right-drag still pans.  The menu's one item shows the tile's folder in
the platform's file manager (Finder / Explorer / the default file
manager) and is greyed out while the folder does not exist.

Headless: QT_QPA_PLATFORM=offscreen, tmp_path, no file manager started.
"""

from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Reveal as REVEAL  # noqa: E402
import pytest  # noqa: E402

# ── the launcher (no Qt) ──────────────────────────────────────────────


def test_each_platform_names_its_file_manager():
    assert REVEAL.menu_label("darwin") == "Show in Finder"
    assert REVEAL.menu_label("win32") == "Show in Explorer"
    assert REVEAL.menu_label("linux") == "Show in File Manager"


def test_the_mac_app_uses_the_same_words():
    swift = (Path(__file__).resolve().parents[2] / "Sources"
             / "XPTerrainBuilder" / "TileContextMenu.swift")
    title = re.search(r'static let revealTitle = "([^"]*)"',
                      swift.read_text(encoding="utf-8")).group(1)
    assert title == REVEAL.menu_label("darwin")


def test_each_platform_reveals_the_folder(tmp_path):
    path = str(tmp_path)
    assert REVEAL.reveal_command(path, "darwin") == ["open", "-R", path]
    assert REVEAL.reveal_command(path, "win32") == [
        "explorer", "/select,", os.path.normpath(path)]
    assert REVEAL.reveal_command(path, "linux") == ["xdg-open", path]


def test_reveal_launches_without_waiting_and_refuses_a_missing_folder(
        tmp_path):
    launched = []
    REVEAL.reveal(str(tmp_path), "darwin", launch=launched.append)
    assert launched == [["open", "-R", str(tmp_path)]]
    with pytest.raises(FileNotFoundError):
        REVEAL.reveal(str(tmp_path / "gone"), "darwin", launch=launched.append)
    assert len(launched) == 1


# ── the Qt map and menu ───────────────────────────────────────────────

pytest.importorskip("PySide6")

import O4_Geo_Utils as GEO  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
import O4_Qt_Tile_Menu as QTTILEMENU  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp):
    view = QTMAP.MapView()
    view.resize(400, 300)
    view._update_timer.stop()
    yield view
    view.deleteLater()


def _right(view, kind, pos):
    buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.RightButton
    ev = QMouseEvent(kind, pos, view.viewport().mapToGlobal(pos.toPoint()),
                     Qt.RightButton, buttons, Qt.NoModifier)
    {QEvent.MouseButtonPress: view.mousePressEvent,
     QEvent.MouseMove: view.mouseMoveEvent,
     QEvent.MouseButtonRelease: view.mouseReleaseEvent}[kind](ev)


def _tile_at(view, pos):
    scene = view.mapToScene(pos.toPoint())
    lat, lon = GEO.pix_to_wgs84(scene.x(), scene.y(), QTMAP.SCENE_ZL)
    return (math.floor(lat), math.floor(lon))


def test_a_right_click_asks_for_the_tile_menu(view):
    asked = []
    view.tile_menu_requested.connect(
        lambda lat, lon, _pos: asked.append((lat, lon)))
    pos = QPointF(200, 150)
    _right(view, QEvent.MouseButtonPress, pos)
    _right(view, QEvent.MouseButtonRelease, pos + QPointF(2, 1))
    assert asked == [_tile_at(view, pos + QPointF(2, 1))]


def test_a_right_drag_pans_and_asks_for_nothing(view):
    asked = []
    view.tile_menu_requested.connect(lambda *args: asked.append(args))
    start = QPointF(200, 150)
    _right(view, QEvent.MouseButtonPress, start)
    _right(view, QEvent.MouseMove, start + QPointF(40, 0))
    _right(view, QEvent.MouseButtonRelease, start + QPointF(40, 0))
    assert asked == []


def test_the_menu_shows_the_folder_and_greys_out_a_missing_one(
        qapp, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(REVEAL, "reveal", launched.append)
    menu = QTTILEMENU.tile_menu(None, 47, -123, str(tmp_path))
    (action,) = menu.actions()
    assert action.text() == REVEAL.menu_label()
    assert action.isEnabled()
    action.trigger()
    assert launched == [str(tmp_path)]
    missing = QTTILEMENU.tile_menu(None, 47, -123, str(tmp_path / "gone"))
    assert not missing.actions()[0].isEnabled()
