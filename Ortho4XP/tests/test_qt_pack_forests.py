"""#1360: the Qt "3D trees" question for an airport pack with old flat
(X-Plane 11) forests, and its parity with the mac app.

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
import O4_Qt_Pack_Forests as QTFOREST  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _event(**kw):
    base = dict(pack="Some Pack", pack_root="/X/Custom Scenery/Some Pack",
                lat=25, lon=51, total=3, mapped=2, uses=14,
                first_paths=["lib/g8/terrain/wet_hot_flat.for"],
                unmapped=1, first_unmapped=["forests/local.for"],
                can_update=True, state="found")
    base.update(kw)
    return EV.PackOldForests(**base)


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
    box, buttons = QTFOREST.pack_forests_box(_event())
    assert box.text() == "3D trees for “Some Pack”"
    assert box.informativeText() == (
        "This airport’s scenery uses 2 old flat (X-Plane 11) tree resources. "
        "Switch them to the X-Plane 12 3D trees?\n\n"
        "The original scenery file is kept as a backup. Undo is on the "
        "pack’s row under Modified airports.\n\n"
        "1 other flat tree resource(s) have no X-Plane 12 3D equivalent and "
        "stay as they are (first: forests/local.for).")
    assert sorted(b.text() for b in box.buttons()) == sorted(
        ["Update", "Never for this pack", "Not now"])
    assert set(buttons) == {"update", "never"}
    assert box.defaultButton().text() == "Update"
    assert box.escapeButton().text() == "Not now"


def test_without_unmapped_there_is_no_unmapped_line(qapp):
    box, _ = QTFOREST.pack_forests_box(_event(unmapped=0, first_unmapped=[]))
    assert "no X-Plane 12 3D equivalent" not in box.informativeText()


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackOldForests.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTFOREST.UPDATE_BUTTON, QTFOREST.NOT_NOW_BUTTON,
              QTFOREST.NEVER_BUTTON):
        assert '"%s"' % s in text
    assert '"3D trees for “\\(pack)”"' in text

    def joined(start, end):
        return "".join(re.findall(r'"([^"]*)"', text[
            text.index(start):text.index(end, text.index(start))]))

    assert joined("func body(", "static let detail").replace(
        "\\(count)", "{n}") == QTFOREST.BODY
    assert joined("static let detail", "func unmappedLine") == QTFOREST.DETAIL
    assert joined("func unmappedLine", "updateButton").replace(
        "\\(count)", "{n}").replace("\\(firstPath)", "{path}") \
        == QTFOREST.UNMAPPED
    assert joined("static let undoHelp", "\n}") == QTFOREST.UNDO_HELP


def test_the_event_is_in_the_handler_table(window):
    assert EV.PackOldForests in window._event_handlers


def test_found_asks_once_per_pack_and_set(window):
    window._on_engine_event(_event())
    window._on_engine_event(_event())          # a second airport, same news
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="never"))
    assert len(window._pack_art_boxes) == 1, "outcomes ask nothing"
    window._on_engine_event(_event(pack_root="/Y", can_update=False))
    assert len(window._pack_art_boxes) == 1, "no question without a yes"


@pytest.mark.parametrize("label,action", [("Update", "update"),
                                          ("Never for this pack", "never")])
def test_the_answers_send_the_command(window, monkeypatch, label, action):
    sent = []
    monkeypatch.setattr(window._session, "pack_forests",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, label).click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": action, "lat": 25, "lon": 51}]
    assert window._pack_art_boxes == []


def test_not_now_sends_nothing(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_forests",
                        lambda **kw: sent.append(kw))
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    assert sent == [] and window._pack_art_boxes == []


def test_an_upgrade_refreshes_the_pack_rows(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_refresh_modified_airports",
                        lambda: calls.append(1))
    window._on_engine_event(_event(state="upgraded"))
    window._on_engine_event(_event(state="undone"))
    assert calls == [1, 1] and window._pack_art_boxes == []


def test_the_pack_row_offers_undo_only_with_an_upgrade(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_forests",
                        lambda **kw: sent.append(kw))
    monkeypatch.setattr(window.map, "active_tile", lambda: (25, 51))
    pack = {"pack_name": "Some Pack", "pack_path": "/X/CS/Some Pack",
            "objects": 3, "forests": 2}
    window._on_reanchor_ready(((25, 51), [pack, dict(pack, forests=0,
                                                     pack_path="/X/CS/B")]))
    trees = [b for b in window.modified_airports_row.findChildren(
        GUI.QToolButton) if b.toolTip() == QTFOREST.UNDO_HELP]
    assert len(trees) == 1
    trees[0].click()
    assert sent == [{"pack_root": "/X/CS/Some Pack", "action": "undo"}]
