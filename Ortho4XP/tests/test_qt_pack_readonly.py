"""#2174 (RULINGS 2026-11-19d): the Qt question for a READ-ONLY airport
pack, its Modified airports row, and their parity with the mac app.

Offscreen, no engine: the event is handed to the window through
``_on_engine_event``, the seam the other Qt tests drive; the box is
non-modal, so nothing here blocks.
"""

import json
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Pack_ReadOnly as QTRO  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _event(**kw):
    base = dict(pack="KSBN - Alpine Aviation",
                pack_root="/X/Custom Scenery/KSBN - Alpine Aviation",
                lat=41, lon=-87, state="found",
                folders=["KSBN - Alpine Aviation",
                         "KSBN - Alpine Aviation/Earth nav data"])
    base.update(kw)
    return EV.PackReadOnly(**base)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        # An EXISTING prefs file: an absent one arms the onboarding
        # wizard, whose modal exec would sit there forever headless.
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(GUI.FNAMES, "Tile_dir", str(tmp_path))  # 12g
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        yield win
    finally:
        for box in list(win._pack_art_boxes):
            box.close()
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _button(box, text):
    return [b for b in box.buttons() if b.text() == text][0]


def test_the_copy(qapp):
    box, buttons = QTRO.pack_readonly_box(_event())
    assert box.text() == "“KSBN - Alpine Aviation” is read-only"
    assert box.informativeText().startswith(
        "KSBN - Alpine Aviation is read-only (as it was downloaded), so "
        "XPTerrainBuilder can't adjust it. Make it writable?\n\n")
    assert box.informativeText().endswith(
        "Read-only: KSBN - Alpine Aviation, KSBN - Alpine Aviation/Earth nav data")
    assert sorted(b.text() for b in box.buttons()) == ["Make writable", "Not now"]
    assert set(buttons) == {"writable", "not_now"}
    assert box.escapeButton().text() == "Not now"


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackReadOnly.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTRO.WRITABLE_BUTTON, QTRO.NOT_NOW_BUTTON, QTRO.ROW_STATUS,
              QTRO.ASK_AGAIN_BUTTON, QTRO.RUN_BUSY):
        assert '"%s"' % s in text

    def joined(start, end):
        return "".join(re.findall(r'"([^"]*)"', text[
            text.index(start):text.index(end, text.index(start))]))

    assert joined("func title(", "func body(").replace(
        "\\(pack)", "{pack}") == QTRO.TITLE
    assert joined("func body(", "static let detail").replace(
        "\\(pack)", "{pack}") == QTRO.BODY
    assert joined("static let detail", "func foldersLine") == QTRO.DETAIL
    assert joined("static let askAgainHelp", "static let runBusy") == QTRO.ASK_AGAIN_HELP
    assert joined("func rebuildLater", "\n    }").replace(
        "\\(tile)", "{tile}").replace("\\(pack)", "{pack}").replace(
        "\\(reason)", "{reason}") == QTRO.REBUILD_LATER


def test_the_event_is_in_the_handler_table(window):
    assert EV.PackReadOnly in window._event_handlers


def test_found_asks_once_per_pack_ask_again_asks_again(window):
    window._on_engine_event(_event())
    window._on_engine_event(_event(lat=41, lon=-86))   # its other tile
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="not_now"))
    assert len(window._pack_art_boxes) == 1, "outcomes ask nothing"
    for box in list(window._pack_art_boxes):
        box.close()
    window._pack_art_boxes.clear()
    window._on_engine_event(_event(state="ask"))
    assert len(window._pack_art_boxes) == 1


@pytest.mark.parametrize("label,action", [("Make writable", "writable"),
                                          ("Not now", "not_now")])
def test_both_answers_send_the_command(window, monkeypatch, label, action):
    sent = []
    monkeypatch.setattr(window._session, "pack_readonly",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, label).click()
    assert sent == [{"pack_root": "/X/Custom Scenery/KSBN - Alpine Aviation",
                     "action": action, "lat": 41, "lon": -87}]
    assert window._pack_art_boxes == []


def test_writable_with_rebuild_rebuilds_the_tile(window, monkeypatch):
    rebuilt, calls = [], []
    monkeypatch.setattr(window, "rebuild_patch_tile",
                        lambda t: rebuilt.append(t))
    monkeypatch.setattr(window, "_refresh_modified_airports",
                        lambda: calls.append(1))
    window._on_engine_event(_event(state="writable", rebuild=True, changed=3))
    assert rebuilt == ["+41-087"] and calls == [1]
    window._on_engine_event(_event(state="writable", rebuild=False))
    assert rebuilt == ["+41-087"] and calls == [1, 1]


def test_the_read_only_row_says_so_and_asks_again(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_readonly",
                        lambda **kw: sent.append(kw))
    monkeypatch.setattr(window.map, "active_tile", lambda: (41, -87))
    pack = {"pack_name": "KSBN - Alpine Aviation",
            "pack_path": "/X/CS/KSBN - Alpine Aviation", "objects": 0,
            "read_only": True, "tiles": ["+41-087"]}
    window._on_reanchor_ready(((41, -87), [pack]))
    labels = [w.text() for w in window.modified_airports_row.findChildren(
        GUI.QLabel)]
    assert QTRO.ROW_STATUS in labels
    buttons = window.modified_airports_row.findChildren(GUI.QToolButton)
    assert [b.text() for b in buttons] == ["Ask again"]
    buttons[0].click()
    assert sent == [{"pack_root": "/X/CS/KSBN - Alpine Aviation",
                     "action": "ask", "lat": 41, "lon": -87}]
