"""#2145: the Qt "same structures in two packs" question — one picker per
pack pair (the remembered answer, else the airport pack), the answer sent
as ``pack_overlaps`` — and its parity with the mac app's sheet.

Offscreen, no engine: the event is handed to the window through
``_on_engine_event``; the box is non-modal, so nothing blocks.
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
import O4_Qt_Pack_Overlaps as QTOVER  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ITEMS = [{"key": "/CS/Autogen | Airport", "packs": ["Autogen", "Airport"],
          "airport": "Airport", "default": "Airport", "winner": "",
          "count": 7, "rows": [5, 3], "summary": "Autogen and Airport both draw 7"},
         {"key": "/CS/Airport | Other", "packs": ["Airport", "Other"],
          "airport": "Airport", "default": "Airport", "winner": "both",
          "count": 1, "rows": [1, 1], "summary": ""}]


def _event(**kw):
    base = dict(lat=25, lon=55, items=ITEMS, state="found")
    base.update(kw)
    return EV.PackOverlaps(**base)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(GUI.FNAMES, "Tile_dir", str(tmp_path))
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


def test_each_pair_has_a_picker_on_its_answer_else_the_airport_pack(qapp):
    box, buttons = QTOVER.pack_overlaps_box(_event())
    assert box.text() == QTOVER.TITLE
    assert list(box.pickers) == [r["key"] for r in ITEMS]
    first, second = box.pickers.values()
    assert [first.itemText(i) for i in range(first.count())] == [
        "Keep Autogen", "Keep Airport", "Keep both"]
    assert first.currentData() == "Airport"
    assert second.currentData() == "both"
    assert set(buttons) == {"choose"}


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackOverlaps.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()

    def joined(start, end):
        i = text.index(start)
        return "".join(re.findall(r'"([^"]*)"', text[i:text.index(end, i)]))

    assert joined("static let title", "static let body") == QTOVER.TITLE
    assert joined("static let body", "static let keepBoth") == QTOVER.BODY
    assert joined("static let detail", "static let applyButton") == QTOVER.DETAIL
    assert joined("static let keepBoth", "static let keepPrefix") == QTOVER.KEEP_BOTH
    assert joined("static let keepPrefix", "static let detail") == QTOVER.KEEP_PREFIX
    assert joined("static let both", "}") == QTOVER.BOTH
    for s in (QTOVER.APPLY_BUTTON, QTOVER.NOT_NOW_BUTTON):
        assert '"%s"' % s in text


def test_found_asks_once_and_outcomes_ask_nothing(window):
    assert EV.PackOverlaps in window._event_handlers
    window._on_engine_event(_event())
    window._on_engine_event(_event())
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="chosen"))
    window._on_engine_event(_event(state="failed", items=[]))
    assert len(window._pack_art_boxes) == 1


def test_apply_sends_every_pick_and_not_now_nothing(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_overlaps",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    assert sent == []
    window._on_engine_event(_event(lat=24))
    [box] = window._pack_art_boxes
    first = box.pickers[ITEMS[0]["key"]]
    first.setCurrentIndex(first.findData("Autogen"))
    _button(box, "Apply").click()
    assert sent == [{"action": "choose", "lat": 24, "lon": 55, "items": [
        {"key": ITEMS[0]["key"], "winner": "Autogen"},
        {"key": ITEMS[1]["key"], "winner": "both"}]}]
