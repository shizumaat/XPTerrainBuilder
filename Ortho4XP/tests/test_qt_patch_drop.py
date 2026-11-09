"""#1979 in the Qt window: a patch dropped on the map is offered and, on
"Install", installed into its tile's Patches folder and banded on the map.
Offscreen, no network; the confirmation is answered by a stub."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_File_Names as FNAMES  # noqa: E402
import O4_Qt_Patch_Drop as QTDROP  # noqa: E402
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from test_qt_tile_customizations import window  # noqa: E402,F401
from test_tile_customizations import make_data  # noqa: E402

PATCH = ("<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6' "
         "o4_icao='LFLS' o4_dsf_tiles='45,5'>\n  <node id='-1' lat='45.36' "
         "lon='5.33'>\n    <tag k='alt_abs' v='400.0' />\n  </node>\n</osm>\n")


@pytest.fixture
def tiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    return make_data(tmp_path, monkeypatch)


@pytest.fixture
def dropped(tiles_dir, tmp_path):
    path = tmp_path / "drop" / "LFLS.patch.osm"
    path.parent.mkdir()
    path.write_text(PATCH, encoding="utf-8", newline="")
    return str(path)


class _Box:
    """QMessageBox stand-in: answers with the button named ``answer``."""
    answer = QTDROP.INSTALL
    shown = []
    Question = Cancel = AcceptRole = 0

    def __init__(self, icon, title, text, buttons, parent):
        _Box.shown.append(text)
        self._buttons = {}

    def addButton(self, label, role):            # noqa: N802
        self._buttons[label] = object()
        return self._buttons[label]

    def setDefaultButton(self, button):          # noqa: N802
        pass

    def exec(self):
        pass

    def clickedButton(self):                     # noqa: N802
        return self._buttons.get(_Box.answer)


def _drop(widget, path):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path)])
    event = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton,
                       Qt.NoModifier)
    return widget.window().patch_drop.eventFilter(widget, event)


def test_a_drop_on_the_map_installs_on_install(window, dropped, monkeypatch):  # noqa: F811
    monkeypatch.setattr(QTDROP, "QMessageBox", _Box)
    _Box.shown = []
    _Box.answer = "Cancel"
    assert _drop(window.map.viewport(), dropped) is True
    assert _Box.shown == ["LFLS.patch.osm → LFLS, tile +45+005"]
    target = os.path.join(FNAMES.patch_dir(45, 5), "LFLS.patch.osm")
    assert not os.path.exists(target)

    _Box.answer = QTDROP.INSTALL
    _drop(window.map.viewport(), dropped)
    assert os.path.isfile(target)
    assert window.map.custom_patched() == {(45, 5)}


def test_launch_arguments_are_paths_only(dropped):
    assert QTDROP.launch_paths(["app", "--x", dropped, "/no/such"]) == [dropped]
