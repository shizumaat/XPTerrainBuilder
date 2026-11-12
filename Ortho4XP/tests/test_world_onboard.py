"""The start's World onboarding (#2007, RULINGS 2026-11-11a): the World
pack is made only when its folder is absent, the offer counts the enabled
per-tile packs Convert could move, both apps say the same words, and the
Qt dialog's Move… measures first.  All on ``tmp_path``; X-Plane reads as
not running."""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import O4_Settings_Model as SM  # noqa: E402
import pytest  # noqa: E402
from o4_engine import world_commands as WORLD  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_World_Onboard as QTONBOARD  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
         / "WorldOnboard.swift")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def scenery(tmp_path, monkeypatch):
    folder = tmp_path / "Custom Scenery"
    folder.mkdir()
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(tmp_path / "x.cfg"))
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    return folder


def test_the_world_folder_is_made_once_and_the_tiles_are_offered(scenery):
    for name in ("zOrtho4XP_+45+007", "zOrtho4XP_+46+007"):
        (scenery / name / "Earth nav data").mkdir(parents=True)
    os.symlink(str(scenery / "gone"), str(scenery / "zOrtho4XP_+47+007"))  # unmounted
    first = WORLD.world_onboard(str(scenery))
    assert first.pop("home")["planned"] == 0      # a bare call only reports
    assert first == {"created": True, "offer": 2, "restart_needed": False}
    assert os.path.isdir(WORLD.pack_dir(str(scenery)))
    again = WORLD.world_onboard(str(scenery))
    assert again["created"] is False and again["offer"] == 0          # asked once


def test_an_existing_world_folder_offers_the_tiles_once(scenery):
    """RULINGS 2026-11-11h (2): the World folder made before, per-tile packs
    never offered: asked once; "Not now" counts as offered."""
    WORLD.world_install(str(scenery))
    (scenery / "zOrtho4XP_+45+007" / "Earth nav data").mkdir(parents=True)
    done = WORLD.world_onboard(str(scenery))
    done.pop("home")                        # RULINGS 2026-11-12g/h
    assert done == {"created": False, "offer": 1, "restart_needed": False}
    assert WORLD.world_onboard(str(scenery))["offer"] == 0


def test_no_tiles_is_not_an_offer(scenery):
    WORLD.world_install(str(scenery))
    assert WORLD.world_onboard(str(scenery))["offer"] == 0
    (scenery / "zOrtho4XP_+45+007" / "Earth nav data").mkdir(parents=True)
    assert WORLD.world_onboard(str(scenery))["offer"] == 1


def test_no_custom_scenery_folder_makes_nothing(tmp_path):
    assert WORLD.world_onboard(str(tmp_path / "missing"))["created"] is False


@pytest.mark.skipif(not SWIFT.is_file(), reason="no app tree")
def test_both_apps_say_the_same():
    swift = dict(re.findall(r'public static let (\w+) = "((?:[^"\\]|\\.)*)"',
                            SWIFT.read_text(encoding="utf-8")))
    qt = {"title": QTONBOARD.TITLE, "intro": QTONBOARD.INTRO,
          "advantages": QTONBOARD.ADVANTAGES, "note": QTONBOARD.NOTE,
          "move": QTONBOARD.MOVE, "notNow": QTONBOARD.NOT_NOW, "done": QTONBOARD.DONE}
    assert swift == qt


def test_move_measures_before_anything_moves(app, monkeypatch):
    import O4_Qt_Convert_Tiles as QTCONVERT
    runs = []
    monkeypatch.setattr(QTCONVERT.ConvertTilesSection, "run",
                        lambda self, dry_run, revert=False, purge=False:
                        runs.append(dry_run))
    dialog = QTONBOARD.OnboardDialog(12, "/cs")
    dialog.move_btn.click()
    assert runs == [True] and dialog.convert_box is not None
    assert dialog.not_now_btn.text() == QTONBOARD.DONE


def test_a_foreign_world_folder_says_so_and_offers_nothing(app):
    """``world_foreign`` (a linked World folder): the sentence, no Move…."""
    import O4_Storage_Text as STORAGE_TEXT
    box = QTONBOARD._foreign_box({"reason": "world_foreign", "target": "/kit/World"})
    assert box.text() == STORAGE_TEXT.WORLD_FOREIGN.format(target="/kit/World")
    assert "/kit/World" in box.text()


def _hold_the_run(monkeypatch):
    """``run_command`` held until the test releases it, its progress
    events sent through the section's ``emit``."""
    import threading

    from o4_engine import world_migrate as MIGRATE
    from o4_engine.events import WorldMigrateProgress
    gate, calls = threading.Event(), []

    def run_command(dry_run, undo=False, tiles=None, scenery_dir="",
                    workers=4, emit=None, choice="keep_all", purge=False):
        calls.append(dry_run)
        emit(WorldMigrateProgress(phase="measure", done=3, total=12,
                                  tile="zOrtho4XP_+45+007"))
        assert gate.wait(10), "TIMED_OUT"
        return {"action": "dry_run", "summary": "3 tiles can move.",
                "totals": {"by_action": {"copy": 3}}}
    monkeypatch.setattr(MIGRATE, "run_command", run_command)
    # Measure runs on its own process (world_measure): held the same way
    from o4_engine import world_measure as MEASURE
    monkeypatch.setattr(MEASURE, "measure", lambda scenery, emit=None, **_kw:
                        run_command(True, scenery_dir=scenery, emit=emit))
    monkeypatch.setattr(MEASURE, "stop", lambda: None)
    return gate, calls


def _wait(app, predicate):
    import time
    deadline = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < deadline, "TIMED_OUT"
        app.processEvents()
        time.sleep(0.01)


def test_the_measure_shows_a_count_and_holds_done(app, monkeypatch):
    """Owner 2026-11-11T15:32Z: while Move… measures, a bar counts the
    tiles and Done (and Escape) wait; Done comes back with the result."""
    import O4_Qt_Convert_Tiles as QTCONVERT
    gate, calls = _hold_the_run(monkeypatch)
    dialog = QTONBOARD.OnboardDialog(12, "/cs")
    dialog.show()
    dialog.move_btn.click()
    box = dialog.convert_box
    _wait(app, lambda: box.bar.maximum() == 12)
    assert calls == [True] and box.running
    assert box.bar.isVisible() and box.bar.value() == 3
    assert QTCONVERT.progress_line("measure", 3, 12, "zOrtho4XP_+45+007") == \
        "Measuring: 3 of 12 tiles · zOrtho4XP_+45+007"
    assert box.status_label.text().startswith(
        "Measuring: 3 of 12 tiles · zOrtho4XP_+45+007 · 0:0")
    assert box.status_label.text().endswith(" elapsed")
    assert box.stop_btn.isVisible() and box.stop_btn.text() == "Cancel"
    assert not dialog.not_now_btn.isEnabled()
    dialog.reject()                                  # Escape: held
    assert dialog.isVisible()
    gate.set()
    _wait(app, lambda: not box.running)
    assert not box.bar.isVisible()
    assert box.status_label.text() == "3 tiles can move."
    assert dialog.not_now_btn.isEnabled() and box.convert_btn.isEnabled()
    dialog.not_now_btn.click()
    assert not dialog.isVisible()


def test_cancel_asks_the_engine_to_stop(app, monkeypatch):
    from o4_engine import world_migrate as MIGRATE
    gate, _calls = _hold_the_run(monkeypatch)
    stopped = []
    monkeypatch.setattr(MIGRATE, "stop", lambda: stopped.append(True))
    import O4_Qt_Convert_Tiles as QTCONVERT
    box = QTCONVERT.ConvertTilesSection("/cs")
    box.run(dry_run=True)
    box.stop_btn.click()
    assert stopped == [True] and not box.stop_btn.isEnabled()
    gate.set()
    _wait(app, lambda: not box.running)


def test_settings_holds_done_while_converting(app, monkeypatch, tmp_path):
    """Settings ▸ Storage's Convert holds the dialog's Done too."""
    import O4_Qt_Settings as QTSET
    gate, _calls = _hold_the_run(monkeypatch)
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(tmp_path / "x.cfg"))
    dialog = QTSET.SettingsWindow({}, [], "", None)
    try:
        box = dialog.storage_section.convert_box
        box.run(dry_run=True)
        assert not dialog.done_btn.isEnabled()
        dialog.show()
        dialog.reject()
        assert dialog.isVisible()
        gate.set()
        _wait(app, lambda: not box.running)
        assert dialog.done_btn.isEnabled()
        dialog.done_btn.click()
        assert not dialog.isVisible()
    finally:
        dialog.deleteLater()


def test_both_convert_sections_say_the_same():
    """``O4WorldMigrateText`` (SceneryKit) and ``O4_Qt_Convert_Tiles``:
    the same words, Cancel included, and the same count line."""
    import O4_Qt_Convert_Tiles as QTCONVERT
    text = (SWIFT.parent / "WorldMigrate.swift").read_text(encoding="utf-8")
    text = text[text.index("public enum O4WorldMigrateText"):]
    swift = dict(re.findall(r'public static let (\w+) = "((?:[^"\\]|\\.)*)"', text))
    qt = {"title": QTCONVERT.TITLE, "intro": QTCONVERT.INTRO,
          "measure": QTCONVERT.MEASURE, "convert": QTCONVERT.CONVERT,
          "stop": QTCONVERT.STOP, "undo": QTCONVERT.UNDO,
          "measuring": QTCONVERT.MEASURING, "converting": QTCONVERT.CONVERTING,
          "confirmTitle": QTCONVERT.CONFIRM_TITLE,
          "confirmText": QTCONVERT.CONFIRM_TEXT,
          "undoTitle": QTCONVERT.UNDO_TITLE, "undoText": QTCONVERT.UNDO_TEXT,
          "confirmDynamic": QTCONVERT.CONFIRM_DYNAMIC,
          "freeSpace": QTCONVERT.FREE_SPACE, "freeTitle": QTCONVERT.FREE_TITLE,
          "freeText": QTCONVERT.FREE_TEXT,
          "measuringBackground": QTCONVERT.MEASURING_BACKGROUND,
          "sampling": QTCONVERT.SAMPLING, "adopting": QTCONVERT.ADOPTING,
          "elapsed": QTCONVERT.ELAPSED,
          "measuredJustNow": QTCONVERT.MEASURED_JUST_NOW,
          "measuredMinutes": QTCONVERT.MEASURED_MINUTES,
          "measuredHours": QTCONVERT.MEASURED_HOURS,
          "measuredDays": QTCONVERT.MEASURED_DAYS}
    for key, title, hint in QTCONVERT.CHOICES:
        name = {"keep_all": "keepAll", "keep_custom": "keepCustom",
                "dynamic": "dynamic"}[key]
        qt[name + "Title"], qt[name + "Hint"] = title, hint
        assert '("%s", %sTitle, %sHint)' % (key, name, name) in text
    assert swift == qt
    for piece in ('"Measuring"', '"Converting"', " of ", " tiles", '" · "'):
        assert piece in text, piece
    assert QTCONVERT.progress_line("move", 1, 4) == "Converting: 1 of 4 tiles"
    # every phase, with the time since the step began (owner
    # 2026-11-12T19:08Z); WorldWireTests.swift asserts the same lines
    assert QTCONVERT.progress_line("adopt", 120, 2221, "zOrtho4XP_+45+007",
                                   elapsed=125) == (
        "Reading tiles made dynamic before: 120 of 2,221 tiles · "
        "zOrtho4XP_+45+007 · 2:05 elapsed")
    assert QTCONVERT.progress_line("sample", 1, 2) == "Timing a sample: 1 of 2 tiles"
    assert QTCONVERT.elapsed_text(3725) == "1:02:05 elapsed"
    assert [QTCONVERT.measured_ago(s) for s in (20, 725, 5 * 3600, 3 * 86400)] == [
        "Measured just now", "Measured 12 min ago", "Measured 5 h ago",
        "Measured 3 days ago"]
    for piece in ('case "sample": return sampling', 'case "adopt": return adopting',
                  '"%d:%02d:%02d"', '"%d:%02d"', "s < 2 * 86400"):
        assert piece in text, piece


def test_settings_follows_a_measure_running_elsewhere(app, monkeypatch):
    """Owner 2026-11-12T19:08Z: Measure started at launch; Settings opened
    while it runs follows its count with the time, then shows its result
    and when it was taken."""
    import time

    import O4_Qt_Convert_Tiles as QTCONVERT
    from o4_engine import world_measure as MEASURE
    state = {"running": True, "started_at": time.time() - 65,
             "progress": {"phase": "adopt", "done": 7, "total": 2221,
                          "tile": "zOrtho4XP_+45+007"},
             "result": None, "measured_at": None}
    monkeypatch.setattr(MEASURE, "state", lambda scenery="": dict(state))
    monkeypatch.setattr(MEASURE, "live", lambda: {
        k: state[k] for k in ("running", "started_at", "progress")})
    box = QTCONVERT.ConvertTilesSection("/cs")
    assert box.running and box.following and box.bar.maximum() == 2221
    assert box.status_label.text().startswith(
        "Reading tiles made dynamic before: 7 of 2,221 tiles · zOrtho4XP_+45+007 · 1:0")
    assert not box.measure_btn.isEnabled()
    state.update(running=False, measured_at=time.time() - 725,
                 result={"action": "dry_run", "summary": "2,221 tiles can move.",
                         "choices": [{"id": "keep_all", "line": "Keeps 2,221 tiles.",
                                      "kept": 0, "dynamic": 0, "again": 2221}]})
    box._tick()
    assert not box.running and not box.following and box.has_result
    assert box.status_label.text() == "2,221 tiles can move."
    assert box.measured_label.text() == "Measured 12 min ago"
    assert box.choice_notes["keep_all"].text() == "Keeps 2,221 tiles."
    assert box.convert_btn.isEnabled()
