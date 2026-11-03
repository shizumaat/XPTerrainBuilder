"""#1707: the Qt "Optimise pack" question for a heavy airport pack, the
pack row's Optimise / Undo optimise button, and their parity with the mac
app.

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
import O4_Qt_Pack_Optimise as QTOPT  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def _event(**kw):
    base = dict(pack="Some Pack", pack_root="/X/Custom Scenery/Some Pack",
                lat=29, lon=-96, dedupe=2720, est_tris_before=275_462_078,
                est_tris_after=222_000_000, can_optimise=True, state="found")
    base.update(kw)
    return EV.PackOptimise(**base)


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
    box, buttons = QTOPT.pack_optimise_box(_event())
    assert box.text() == "Optimise “Some Pack”?"
    assert box.informativeText() == (
        "This airport’s objects draw 275.5 million triangles on this tile, "
        "enough to cost frame rate. 2720 of its object placements repeat "
        "another on the same spot. Optimise removes them (222.0 million "
        "triangles).\n\n"
        "The original scenery file is kept as a backup, and the "
        "optimisation is applied again whenever the app rewrites this pack. "
        "Undo is on the pack’s row under Modified airports.")
    assert sorted(b.text() for b in box.buttons()) == sorted(
        ["Optimise", "Never for this pack", "Not now"])
    assert set(buttons) == {"update", "never"}
    assert box.defaultButton().text() == "Optimise"
    assert box.escapeButton().text() == "Not now"


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackOptimise.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTOPT.OPTIMISE_BUTTON, QTOPT.NOT_NOW_BUTTON, QTOPT.NEVER_BUTTON):
        assert '"%s"' % s in text
    assert '"Optimise “\\(pack)”?"' in text

    def joined(start, end):
        return "".join(re.findall(r'"([^"]*)"', text[
            text.index(start):text.index(end, text.index(start))]))

    assert joined("func body(", "static let detail").replace(
        "\\(millions(before))", "{before}").replace(
        "\\(count)", "{n}").replace("\\(millions(after))", "{after}") \
        == QTOPT.BODY
    assert joined("static let detail", "static let optimiseButton") == QTOPT.DETAIL
    assert joined("static let optimiseHelp", "static let undoHelp") \
        == QTOPT.OPTIMISE_HELP
    assert joined("static let undoHelp", "\n}") == QTOPT.UNDO_HELP


def test_the_event_is_in_the_handler_table(window):
    assert EV.PackOptimise in window._event_handlers


def test_found_asks_once_per_pack_and_count(window):
    window._on_engine_event(_event())
    window._on_engine_event(_event())          # a second airport, same news
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="never"))
    assert len(window._pack_art_boxes) == 1, "outcomes ask nothing"
    window._on_engine_event(_event(pack_root="/Y", can_optimise=False))
    assert len(window._pack_art_boxes) == 1, "no question without a yes"


@pytest.mark.parametrize("label,action", [("Optimise", "update"),
                                          ("Never for this pack", "never")])
def test_the_answers_send_the_command(window, monkeypatch, label, action):
    sent = []
    monkeypatch.setattr(window._session, "pack_optimise",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, label).click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": action, "lat": 29, "lon": -96}]
    assert window._pack_art_boxes == []


def test_not_now_sends_nothing(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_optimise",
                        lambda **kw: sent.append(kw))
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    _button(box, "Not now").click()
    assert sent == [] and window._pack_art_boxes == []


def test_an_optimise_refreshes_the_pack_rows(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_refresh_modified_airports",
                        lambda: calls.append(1))
    window._on_engine_event(_event(state="optimised"))
    window._on_engine_event(_event(state="undone"))
    assert calls == [1, 1] and window._pack_art_boxes == []


def test_the_pack_row_optimises_or_undoes(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_optimise",
                        lambda **kw: sent.append(kw))
    monkeypatch.setattr(window.map, "active_tile", lambda: (29, -96))
    pack = {"pack_name": "Some Pack", "pack_path": "/X/CS/Some Pack",
            "objects": 3, "forests": 0, "optimised": 0}
    window._on_reanchor_ready(((29, -96), [pack, dict(pack, optimised=7,
                                                      pack_path="/X/CS/B")]))
    buttons = window.modified_airports_row.findChildren(GUI.QToolButton)
    [opt] = [b for b in buttons if b.toolTip() == QTOPT.OPTIMISE_HELP]
    [undo] = [b for b in buttons if b.toolTip() == QTOPT.UNDO_HELP]
    opt.click()
    undo.click()
    assert sent == [{"pack_root": "/X/CS/Some Pack", "action": "update",
                     "lat": 29, "lon": -96},
                    {"pack_root": "/X/CS/B", "action": "undo"}]
