"""#1916: the Qt package adjustments question — one checkbox per row the
user chooses (all checked), the automatic flatten row listed, the answer
sent as ``pack_adjust`` — and its parity with the mac app's sheet.

Offscreen, no engine: the event is handed to the window through
``_on_engine_event``; the box is non-modal, so nothing here blocks.
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
import O4_Qt_Pack_Adjust as QTADJ  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ITEMS = [{"key": "trees", "count": 3, "uses": 9, "automatic": False},
         {"key": "drapes", "count": 12, "uses": 40, "automatic": False},
         {"key": "flatten", "count": 1, "uses": 0, "automatic": True}]


def _event(**kw):
    base = dict(pack="Some Pack", pack_root="/X/Custom Scenery/Some Pack",
                lat=29, lon=-96, items=ITEMS, state="found")
    base.update(kw)
    return EV.PackAdjust(**base)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
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


def test_every_choice_is_checked_and_flatten_is_listed(qapp):
    box, buttons = QTADJ.pack_adjust_box(_event())
    assert box.text() == "Adjust “Some Pack”?"
    assert list(box.item_boxes) == ["trees", "drapes"]
    assert all(b.isChecked() for b in box.item_boxes.values())
    assert box.automatic == ["flatten"]
    assert set(buttons) == {"update", "never"}
    assert QTADJ._detail(ITEMS[1]) == (
        "12 photo images (40 polygons) laid over the airport cover the "
        "tile’s imagery.")


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackAdjust.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTADJ.APPLY_BUTTON, QTADJ.NOT_NOW_BUTTON, QTADJ.NEVER_BUTTON):
        assert '"%s"' % s in text
    assert '"Adjust “\\(pack)”?"' in text

    def joined(start, end):
        i = text.index(start)
        return "".join(re.findall(r'"([^"]*)"', text[i:text.index(end, i)]))

    assert joined("static let body", "static let itemTitles") == QTADJ.BODY
    assert joined("static let detail", "static let applyButton") == QTADJ.DETAIL
    for key in QTADJ.ITEM_TITLES:
        assert '"%s": "%s"' % (key, QTADJ.ITEM_TITLES[key]) in text
    got: dict = {}
    key = None
    block = text[text.index("static let itemDetails"):text.index("static let detail")]
    for line in block.splitlines()[1:]:
        m = re.match(r'\s*"(\w+)":(.*)', line)
        if m:
            key, line = m.group(1), m.group(2)
        if key:
            got[key] = got.get(key, "") + "".join(re.findall(r'"([^"]*)"', line))
    assert got == QTADJ.ITEM_DETAILS


def test_found_asks_once_and_outcomes_ask_nothing(window):
    assert EV.PackAdjust in window._event_handlers
    window._on_engine_event(_event())
    window._on_engine_event(_event())          # a second airport, same news
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="never"))
    window._on_engine_event(_event(pack_root="/Y", items=ITEMS[2:]))
    assert len(window._pack_art_boxes) == 1, "flatten alone asks nothing"


def test_apply_sends_the_checked_rows_and_every_row_shown(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_adjust",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    box.item_boxes["drapes"].setChecked(False)
    _button(box, "Apply").click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": "update", "lat": 29, "lon": -96,
                     "shown": ["trees", "drapes"], "items": ["trees"]}]


def test_never_and_not_now(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_adjust",
                        lambda **kw: sent.append(kw))
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    assert sent == []
    window._on_engine_event(_event(lat=30))
    [box] = window._pack_art_boxes
    _button(box, "Never for this pack").click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": "never", "lat": 30, "lon": -96,
                     "shown": ["trees", "drapes"]}]


def test_an_applied_answer_refreshes_the_pack_rows(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_refresh_modified_airports",
                        lambda: calls.append(1))
    window._on_engine_event(_event(state="applied"))
    assert calls == [1] and window._pack_art_boxes == []
