"""#433 (owner RULINGS 2026-10-06c): the Qt warning for a pack X-Plane
will not load, and its parity with the mac app.

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

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Pack_Art as QTART  # noqa: E402
from o4_engine import events as EV  # noqa: E402


def _event(**kw):
    base = dict(pack="Some Pack", pack_root="/X/Custom Scenery/Some Pack",
                lat=25, lon=51, total=108, kinds={"polygon": 108}, uses=108,
                first_paths=["Imagery/a.pol", "Imagery/b.pol"],
                can_omit=True, state="found")
    base.update(kw)
    return EV.PackMissingArt(**base)


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


def test_the_copy_is_the_owners_verbatim(qapp):
    box, primary = QTART.pack_art_box(_event())
    assert box.text() == "X-Plane will not load “Some Pack”"
    assert box.informativeText() == (
        "Its scenery file refers to 108 file(s) that are not installed "
        "(first: Imagery/a.pol). X-Plane skips a scenery pack entirely when "
        "any file it refers to is missing, so this airport’s buildings "
        "and ground would not appear in the simulator.\n\n"
        "The original scenery file is kept as a backup and can be restored.")
    labels = [b.text() for b in box.buttons()]
    assert labels == ["Build without the missing items",
                      "Leave the pack as it is"]
    assert primary is not None and primary.text() == QTART.PRIMARY_BUTTON
    assert box.defaultButton().text() == "Leave the pack as it is"


def test_terrain_shows_the_warning_without_the_primary_button(qapp):
    box, primary = QTART.pack_art_box(_event(
        can_omit=False, kinds={"terrain": 1}, total=1,
        first_paths=["terrain/gone.ter"]))
    assert primary is None
    assert [b.text() for b in box.buttons()] == ["Leave the pack as it is"]
    assert QTART.DETAIL not in box.informativeText()


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackMissingArt.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTART.PRIMARY_BUTTON, QTART.SECONDARY_BUTTON, QTART.DETAIL):
        assert '"%s"' % s in text
    assert '"X-Plane will not load “\\(pack)”"' in text
    swift_body = "".join(re.findall(
        r'"([^"]*)"', text[text.index("func body("):text.index(
            "primaryButton")]))
    assert swift_body.replace("\\(count)", "{n}").replace(
        "\\(firstPath)", "{path}") == QTART.BODY


def test_the_event_is_in_the_handler_table(window):
    assert EV.PackMissingArt in window._event_handlers


def test_found_shows_one_box_per_pack_and_set(window):
    window._on_engine_event(_event())
    window._on_engine_event(_event())          # a second airport, same news
    assert len(window._pack_art_boxes) == 1
    window._on_engine_event(_event(state="omitted"))
    assert len(window._pack_art_boxes) == 1, "completions show nothing new"


def test_the_primary_button_sends_the_command(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "omit_missing_art",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    primary = [b for b in box.buttons()
               if b.text() == QTART.PRIMARY_BUTTON][0]
    primary.click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "lat": 25, "lon": 51}]
    assert window._pack_art_boxes == []


def test_leave_sends_nothing(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "omit_missing_art",
                        lambda **kw: sent.append(kw))
    window._on_engine_event(_event())
    [box] = window._pack_art_boxes
    [b for b in box.buttons() if b.text() == QTART.SECONDARY_BUTTON][0].click()
    assert sent == [] and window._pack_art_boxes == []
