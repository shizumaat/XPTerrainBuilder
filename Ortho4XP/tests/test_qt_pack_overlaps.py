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


def test_a_drape_row_offers_to_hide_the_lower_packs_polygons(qapp):
    """RULINGS 2026-11-19h: the airport pack wins by default (Hide), or
    Keep both; the note is shown once."""
    row = {"key": "/CS/draped polygons +41-088/Airport | World", "kind": "drapes",
           "packs": ["Airport", "World"], "airport": "Airport", "default": "Airport",
           "winner": "", "lower": "World", "count": 9, "rows": [0, 9], "summary": "s"}
    box, _buttons = QTOVER.pack_overlaps_box(_event(items=[row]))
    (pick,) = box.pickers.values()
    assert [pick.itemText(i) for i in range(pick.count())] == [
        "Hide World's polygons inside the airport", "Keep both"]
    assert pick.currentData() == "Airport"
    assert box.answer_extra("choose") == {"items": [{"key": row["key"], "winner": "Airport"}]}


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
    assert joined("static let both", "// Two packs defining") == QTOVER.BOTH
    assert joined("static let sameAirport", "static let disablePrefix") == QTOVER.SAME_AIRPORT
    assert joined("static let disablePrefix", "static let keepEnabled") == QTOVER.DISABLE_PREFIX
    assert joined("static let keepEnabled", "static let restartNote") == QTOVER.KEEP_ENABLED
    assert joined("static let restartNote", "/// The row") == QTOVER.RESTART_NOTE
    assert joined("static let duplicateKind", "static let disable ") == QTOVER.DUPLICATE_KIND
    assert joined("static let disable ", "static let keep ") == QTOVER.DISABLE
    assert joined("static let keep ", "// A lower pack") == QTOVER.KEEP
    assert joined("static let drapesNote", "static let hidePrefix") == QTOVER.DRAPES_NOTE
    assert joined("static let hidePrefix", "static let hideSuffix") == QTOVER.HIDE_PREFIX
    assert joined("static let hideSuffix", "/// The row `kind` of a drape") == QTOVER.HIDE_SUFFIX
    assert joined("static let drapesKind", "// Reviewing") == QTOVER.DRAPES_KIND
    assert joined("static let reviewButton", "static let reviewHelp") == QTOVER.REVIEW_BUTTON
    assert joined("static let reviewHelp", "static let noPairs") == QTOVER.REVIEW_HELP
    assert joined("static let noPairs", "static let okButton") == QTOVER.NO_PAIRS
    assert joined("static let okButton", "}") == QTOVER.OK_BUTTON
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


DUPS = [{"key": "/CS/same airport/Alpha | Zeta", "kind": "duplicate",
         "packs": ["Zeta", "Alpha"], "airport": "XXXX", "default": "disable",
         "winner": "", "lower": "Alpha", "count": 1, "rows": [],
         "summary": "Zeta and Alpha both define XXXX."},
        {"key": "/CS/same airport/Beta | Gamma", "kind": "duplicate",
         "packs": ["Beta", "Gamma"], "airport": "YYYY", "default": "",
         "winner": "", "lower": "", "count": 1, "rows": [], "summary": "not listed"}]


def test_a_same_airport_pair_offers_to_disable_the_lower_pack(window, monkeypatch):
    """RULINGS 17s (23:37Z): the lower pack's disable is offered (and
    pre-selected), a report row has no picker and is never sent."""
    from PySide6.QtWidgets import QLabel
    sent = []
    monkeypatch.setattr(window._session, "pack_overlaps",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event(items=DUPS + ITEMS[:1]))
    [box] = window._pack_art_boxes
    assert list(box.pickers) == [DUPS[0]["key"], ITEMS[0]["key"]]
    pick = box.pickers[DUPS[0]["key"]]
    assert [pick.itemText(i) for i in range(pick.count())] == [
        "Disable Alpha", "Keep both enabled"]
    assert pick.currentData() == "disable"
    texts = [w.text() for w in box.findChildren(QLabel)]
    assert QTOVER.SAME_AIRPORT in texts and QTOVER.RESTART_NOTE in texts
    _button(box, "Apply").click()
    assert sent[0]["items"] == [{"key": DUPS[0]["key"], "winner": "disable"},
                                {"key": ITEMS[0]["key"], "winner": "Airport"}]


def test_the_standard_size_matches_the_mac_sheet():
    """#2180: one width; more than a few pairs scroll inside one height."""
    sheet = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "XPTerrainBuilder", "PackOverlapsSheet.swift")
    if not os.path.exists(sheet):
        pytest.skip("Swift sources not present in this tree")
    text = open(sheet, encoding="utf-8").read()
    assert "listMaxHeight: CGFloat = %d" % QTOVER.LIST_MAX_HEIGHT in text
    assert "boxWidth: CGFloat = %d" % QTOVER.BOX_WIDTH in text
    assert "unscrolledPairs = %d" % QTOVER.UNSCROLLED_PAIRS in text


def _many(n):
    return [{"key": "/CS/P%d | Airport" % i, "packs": ["P%d" % i, "Airport"],
             "airport": "Airport", "default": "Airport", "winner": "",
             "count": 3, "rows": [1, 2], "summary": "P%d and Airport both draw 3" % i}
            for i in range(n)]


def test_a_long_list_scrolls_and_the_box_keeps_its_size(qapp):
    """#2180: forty pairs fit a 13-inch screen; the buttons stay outside
    the scroll area."""
    box, _buttons = QTOVER.pack_overlaps_box(_event(items=_many(40)))
    assert box.scroll is not None
    assert box.scroll.height() == QTOVER.LIST_MAX_HEIGHT
    assert len(box.pickers) == 40
    assert all(box.scroll.widget().isAncestorOf(p) for p in box.pickers.values())
    assert not box.scroll.isAncestorOf(box.apply)
    assert box.sizeHint().height() < 760
    assert box.width() == QTOVER.BOX_WIDTH
    short, _ = QTOVER.pack_overlaps_box(_event(items=_many(QTOVER.UNSCROLLED_PAIRS)))
    assert short.scroll is None


def test_a_report_with_no_pair_says_so(window, monkeypatch):
    """#2180: the review of a tile with no pair: the words and OK, nothing
    sent."""
    from PySide6.QtWidgets import QLabel
    sent = []
    monkeypatch.setattr(window._session, "pack_overlaps",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event(state="ask", items=[]))
    [box] = window._pack_art_boxes
    assert QTOVER.NO_PAIRS in [w.text() for w in box.findChildren(QLabel)]
    assert [b.text() for b in box.buttons()] == [QTOVER.OK_BUTTON]
    _button(box, QTOVER.OK_BUTTON).click()
    assert sent == [] and window._pack_art_boxes == []


def test_pack_choices_asks_for_the_active_tiles_report(window, monkeypatch):
    """#2180: the tile pane's Pack choices... sends "ask"; the report opens
    the question again, each picker on the stored answer."""
    sent = []
    monkeypatch.setattr(window._session, "pack_overlaps",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    monkeypatch.setattr(window.map, "active_tile", lambda: (25, 55))
    assert window.pack_choices_btn.text() == QTOVER.REVIEW_BUTTON
    window.pack_choices_btn.click()
    assert sent == [{"action": "ask", "lat": 25, "lon": 55}]
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    window._on_engine_event(_event(state="ask"))
    [box] = window._pack_art_boxes
    assert box.pickers[ITEMS[1]["key"]].currentData() == "both"
