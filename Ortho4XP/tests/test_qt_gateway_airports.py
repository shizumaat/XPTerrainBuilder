"""#1989: the Qt Gateway airports question — one checkbox per airport
(all checked), the answer sent as ``gateway_airports`` — and its parity
with the mac app's sheet.

Offscreen, no engine, no network: the event is handed to the window
through ``_on_engine_event``; the box is non-modal, so nothing blocks.
"""

import json
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Gateway_Airports as QTGATE  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ITEMS = [{"icao": "KEUG", "name": "Mahlon Sweet Fld", "reason": "flatten",
          "installed_id": 0, "latest_id": 0, "pack": ""},
         {"icao": "KXXX", "name": "", "reason": "update",
          "installed_id": 110181, "latest_id": 120000,
          "pack": "KXXX Gateway Airport"}]


def _event(**kw):
    base = dict(lat=44, lon=-124, items=ITEMS, state="found")
    base.update(kw)
    return EV.GatewayAirports(**base)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
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


def test_every_airport_is_checked(qapp):
    box, buttons = QTGATE.gateway_airports_box(_event())
    assert box.text() == QTGATE.TITLE
    assert list(box.item_boxes) == ["KEUG", "KXXX"]
    assert box.item_boxes["KEUG"].text() == "KEUG Mahlon Sweet Fld"
    assert all(b.isChecked() for b in box.item_boxes.values())
    assert set(buttons) == {"install", "never"}
    assert QTGATE._row_detail(ITEMS[1]) == (
        "A newer Gateway version is available (110181 → 120000); it "
        "installs without the flatten tag.")


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "GatewayAirports.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()

    def joined(start, end):
        i = text.index(start)
        return "".join(re.findall(r'"([^"]*)"', text[i:text.index(end, i)]))

    assert joined("static let title", "static let body") == QTGATE.TITLE
    assert joined("static let body", "static let reasonDetails") == QTGATE.BODY
    assert joined("static let detail", "static let installButton") == \
        QTGATE.DETAIL
    for s in (QTGATE.INSTALL_BUTTON, QTGATE.NOT_NOW_BUTTON,
              QTGATE.NEVER_BUTTON):
        assert '"%s"' % s in text
    got: dict = {}
    key = None
    block = text[text.index("static let reasonDetails"):
                 text.index("static let detail")]
    for line in block.splitlines()[1:]:
        m = re.match(r'\s*"(\w+)":(.*)', line)
        if m:
            key, line = m.group(1), m.group(2)
        if key:
            got[key] = got.get(key, "") + "".join(re.findall(r'"([^"]*)"', line))
    assert got == QTGATE.REASON_DETAILS


def test_found_asks_once_and_outcomes_ask_nothing(window):
    assert EV.GatewayAirports in window._event_handlers
    window._on_engine_event(_event())
    window._on_engine_event(_event())          # the next tile pass, same news
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="installed", items=[
        {"icao": "KEUG", "reason": "installed"}]))
    window._on_engine_event(_event(state="failed", items=[]))
    assert len(window._pack_art_boxes) == 1


def test_install_sends_the_checked_and_every_airport_shown(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "gateway_airports",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    box.item_boxes["KXXX"].setChecked(False)
    _button(box, "Install").click()
    assert sent == [{"action": "install", "lat": 44, "lon": -124,
                     "shown": ["KEUG", "KXXX"], "items": ["KEUG"]}]


def test_never_and_not_now(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "gateway_airports",
                        lambda **kw: sent.append(kw))
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    assert sent == []
    window._on_engine_event(_event(lat=45))
    [box] = window._pack_art_boxes
    _button(box, "Never for these airports").click()
    assert sent == [{"action": "never", "lat": 45, "lon": -124,
                     "shown": ["KEUG", "KXXX"]}]
