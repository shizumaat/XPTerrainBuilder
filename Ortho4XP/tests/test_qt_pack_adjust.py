"""#1916: the Qt package adjustments question — one checkbox per row the
user chooses (ticked as the row's ``checked`` says: all but the large
ground textures of #1962), the automatic flatten row listed, the answer
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


def test_the_ground_textures_open_unticked(qapp):
    rows = ITEMS[:2] + [{"key": "ground", "count": 17, "uses": 55,
                         "automatic": False, "checked": False}] + ITEMS[2:]
    box, _buttons = QTADJ.pack_adjust_box(_event(items=rows))
    assert list(box.item_boxes) == ["trees", "drapes", "ground"]
    assert box.checked_items() == ["trees", "drapes"], \
        "never hidden without the user's tick (RULINGS 2026-11-09a (3))"
    assert QTADJ._detail(rows[2]) == (
        "17 painted ground or grass images (55 polygons) laid mostly over "
        "unpaved ground at the airport cover the tile’s imagery.")


def test_the_terrain_objects_open_as_the_engine_ticks_them(qapp):
    """RULINGS 2026-11-13i: "Hide terrain objects" is offered beside the
    drapes and the ground — ticked by default since owner
    2026-11-15T13:12Z; the box reads the engine's ``checked``
    (``adjust_stage.UNCHECKED``), never a default of its own."""
    from auto_patch import adjust_stage as AS
    rows = ITEMS[:2] + [{"key": "terrain", "count": 1, "uses": 1,
                         "automatic": False,
                         "checked": "terrain" not in AS.UNCHECKED,
                         "rebuild": True}] + ITEMS[2:]
    box, _buttons = QTADJ.pack_adjust_box(_event(items=rows))
    assert list(box.item_boxes) == ["trees", "drapes", "terrain"]
    assert box.checked_items() == ["trees", "drapes", "terrain"]
    assert QTADJ.ITEM_TITLES["terrain"] == (
        "Hide terrain objects included with the package")
    assert box.apply.text() == QTADJ.APPLY_REBUILD_BUTTON, \
        "hiding the terrain objects reshapes the tile's ground"
    box.item_boxes["terrain"].setChecked(False)
    assert box.apply.text() == QTADJ.APPLY_BUTTON
    assert QTADJ._detail(rows[2]).endswith(QTADJ.REBUILD_NOTE)


def test_the_generic_ground_names_its_hectares(qapp):
    """#2085: the stock X-Plane ground any overlay pack drapes over the
    tile is offered, ticked, with the hectares it covers."""
    row = {"key": "generic", "count": 7, "uses": 61, "automatic": False,
           "checked": True, "hectares": 4310}
    box, _buttons = QTADJ.pack_adjust_box(_event(items=[row]))
    assert box.checked_items() == ["generic"]
    assert QTADJ._detail(row) == (
        "7 stock X-Plane grass, sand or scrub textures (61 polygons, about "
        "4,310 ha) cover the tile’s imagery.")


def test_the_copy_matches_the_mac_app():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "PackAdjust.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    text = open(swift, encoding="utf-8").read()
    for s in (QTADJ.APPLY_BUTTON, QTADJ.NOT_NOW_BUTTON, QTADJ.NEVER_BUTTON,
              QTADJ.OPTIMISE_HEADING, QTADJ.APPLY_REBUILD_BUTTON,
              QTADJ.CANCEL_BUTTON, QTADJ.ADJUST_BUTTON):
        assert '"%s"' % s in text
    assert '"Adjust “\\(pack)”?"' in text
    assert '"Adjust “\\(pack)”"' in text
    for qt in (QTADJ.REBUILD_LATER, QTADJ.REBUILD_QUEUED, QTADJ.REBUILDING):
        swift_form = qt
        for name in ("tile", "pack", "reason", "change"):
            swift_form = swift_form.replace("{%s}" % name, "\\(%s)" % name)
        assert '"%s"' % swift_form in text, qt

    def joined(start, end):
        i = text.index(start)
        return "".join(re.findall(r'"([^"]*)"', text[i:text.index(end, i)]))

    assert joined("static let body", "static let itemTitles") == QTADJ.BODY
    assert joined("static let detail", "static let applyButton") == QTADJ.DETAIL
    assert joined("static let editBody", "static let optimiseHeading") == QTADJ.EDIT_BODY
    assert joined("static let rebuildNote", "static let applyRebuildButton") \
        == QTADJ.REBUILD_NOTE
    assert joined("static let adjustHelp", "public static func rebuildLater") \
        == QTADJ.ADJUST_HELP
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


# ── the pack row's Adjust… (owner 2026-11-15T13:12Z) ──────────────────────

EDIT_ITEMS = [{"key": "drapes", "count": 12, "uses": 40, "automatic": False,
               "checked": True, "applied": True, "rebuild": False},
              {"key": "terrain", "count": 1, "uses": 1, "automatic": False,
               "checked": False, "applied": False, "rebuild": True},
              {"key": "flatten", "count": 1, "uses": 0, "automatic": True}]
EDIT_STEPS = [{"key": "dedupe", "count": 4, "tris": 1000000, "mb": 0.0,
               "checked": True},
              {"key": "textures", "count": 3, "tris": 0, "mb": 12.0,
               "checked": False}]


def _edit(**kw):
    return _event(state="adjust", items=EDIT_ITEMS, steps=EDIT_STEPS, **kw)


def test_adjust_opens_as_the_pack_is_with_its_optimise_steps(qapp):
    box, buttons = QTADJ.pack_adjust_box(_edit())
    assert box.text() == "Adjust “Some Pack”"
    assert set(buttons) == {"change"} and box.never is None
    assert box.not_now.text() == QTADJ.CANCEL_BUTTON
    assert box.checked_items() == ["drapes"]
    assert {k: b.isChecked() for k, b in box.step_boxes.items()} == {
        "dedupe": True, "textures": False}
    assert box.apply.text() == QTADJ.APPLY_BUTTON, "nothing changed yet"
    box.item_boxes["terrain"].setChecked(True)
    assert box.apply.text() == QTADJ.APPLY_REBUILD_BUTTON
    box.item_boxes["drapes"].setChecked(False)
    box.step_boxes["textures"].setChecked(True)
    assert box.answer_extra("change") == {
        "shown": ["drapes", "terrain"], "items": ["terrain"],
        "steps": ["dedupe", "textures"]}


def test_adjust_asks_every_time_and_apply_sends_change(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_adjust",
                        lambda **kw: sent.append(kw) or {"status": "started"})
    window._on_engine_event(_edit())
    [box] = window._pack_art_boxes
    _button(box, "Cancel").click()
    assert sent == []
    window._on_engine_event(_edit())
    [box] = window._pack_art_boxes
    _button(box, "Apply").click()
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": "change", "lat": 29, "lon": -96,
                     "shown": ["drapes", "terrain"], "items": ["drapes"],
                     "steps": ["dedupe"]}]


def test_a_rebuild_outcome_rebuilds_the_tile(window, monkeypatch, capsys):
    asked = []
    monkeypatch.setattr(window, "_refresh_modified_airports", lambda: None)
    monkeypatch.setattr(window, "rebuild_patch_tile",
                        lambda tile: asked.append(tile) or None)
    window._on_engine_event(_event(state="applied"))
    assert asked == []
    window._on_engine_event(_event(state="applied", rebuild=True))
    assert asked == ["+29-096"]
    monkeypatch.setattr(window, "rebuild_patch_tile",
                        lambda tile: "This tile is already in this run.")
    window._on_engine_event(_event(state="applied", rebuild=True))
    assert "Rebuild tile +29-096 to finish the change" in capsys.readouterr().out


def test_the_pack_row_adjust_asks_the_engine(window, monkeypatch):
    sent = []
    monkeypatch.setattr(window._session, "pack_adjust",
                        lambda **kw: sent.append(kw))
    monkeypatch.setattr(window.map, "active_tile", lambda: (29, -96))
    window._adjust_pack_from_row({"pack_path": "/X/Custom Scenery/Some Pack"})
    assert sent == [{"pack_root": "/X/Custom Scenery/Some Pack",
                     "action": "adjust", "lat": 29, "lon": -96}]
    window._building = True
    window._run_tiles = {(29, -96)}
    window._progress_states = {(29, -96): ("active", "mesh", 10)}
    window._adjust_pack_from_row({"pack_path": "/X/Custom Scenery/Some Pack"})
    assert len(sent) == 1, "never while the run builds the pack's tile"
    # the engine answers the first command (#2200: one pending per row)
    import types
    window._pack_row_answered(types.SimpleNamespace(pack_root="/X/Custom Scenery/Some Pack"))
    window._run_tiles = {(48, 2)}
    window._adjust_pack_from_row({"pack_path": "/X/Custom Scenery/Some Pack"})
    assert len(sent) == 2, "a run on other tiles never holds it (#2168)"


def test_a_terrain_answer_during_a_run_waits_for_its_end(window, monkeypatch,
                                                         capsys):
    asked = []
    monkeypatch.setattr(window, "_refresh_modified_airports", lambda: None)
    monkeypatch.setattr(window, "rebuild_patch_tile",
                        lambda tile: asked.append(tile) or None)
    window._building = True
    window._on_engine_event(_event(state="applied", rebuild=True))
    assert asked == []
    assert "will be rebuilt when this run finishes" in capsys.readouterr().out


def test_the_tiles_still_owed_are_rebuilt_once_after_the_run(window,
                                                             monkeypatch,
                                                             capsys):
    asked = []
    monkeypatch.setattr(window, "rebuild_patch_tile",
                        lambda tile: asked.append(tile) or None)
    rows = [{"tile": "+29-096", "lat": 29, "lon": -96, "pack": "Some Pack",
             "change": "hidden", "id": "+29-096@1"},
            {"tile": "+30-096", "lat": 30, "lon": -96, "pack": "Other",
             "change": "shown", "id": "+30-096@1"}]
    window._on_engine_event(_event(state="pending", items=rows, rebuild=True))
    assert asked == ["+29-096", "+30-096"]
    out = capsys.readouterr().out
    assert ("Rebuilding tile +29-096 to match: terrain objects hidden in "
            "“Some Pack”.") in out
    assert window._pack_art_boxes == [], "no question"
    window._on_engine_event(_event(state="pending", items=rows, rebuild=True))
    assert len(asked) == 2, "a debt the window already rebuilt is not looped"
