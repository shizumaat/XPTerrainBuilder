"""The Mac and Qt imagery menus are built by one rule from one list
(#1345).  ``Tests/SceneryKitTests/Fixtures/Imagery/imagery_menu.json`` is
read here by the Qt rule (``O4_Qt_Imagery_Menu.menu_entries``) and the
engine's URL expander, and by ``ImagerySourcesTests.swift`` through
``ImageryMenu.entries`` and ``O4ImageryPreview.url``: both must produce
the fixture's expectations, so the two apps cannot drift.
"""
import json
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIXTURE = os.path.join(REPO_ROOT, "..", "Tests", "SceneryKitTests", "Fixtures",
                       "Imagery", "imagery_menu.json")

pytest.importorskip("PySide6")
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

import O4_Imagery_Sources as SOURCES  # noqa: E402
import O4_Qt_Imagery_Menu as QTIMENU  # noqa: E402


@pytest.fixture(scope="module")
def fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def _statuses(fixture):
    return {code: tuple(value) for code, value in fixture["statuses"].items()}


def test_qt_menus_match_the_shared_fixture(fixture):
    assert QTIMENU.menu_entries(fixture["rows"], _statuses(fixture), for_map=False) \
        == fixture["build"]
    assert QTIMENU.menu_entries(fixture["rows"], _statuses(fixture), for_map=True) \
        == fixture["map"]


def test_engine_expander_matches_the_shared_fixture(fixture):
    rows = {row["code"]: row for row in fixture["rows"]}
    for case in fixture["urls"]:
        preview = rows[case["code"]]["preview"]
        assert SOURCES.expand_preview(preview, case["z"], case["x"], case["y"]) \
            == case["url"], case


def test_qt_combo_follows_the_entries(fixture):
    from PySide6.QtWidgets import QApplication, QComboBox

    QApplication.instance() or QApplication([])
    combo = QComboBox()
    QTIMENU.fill_combo(combo, fixture["map"])
    offered = QTIMENU.offered_codes(combo)
    assert offered == [e["code"] for e in fixture["map"] if e["enabled"]]
    arc = combo.findData("Arc")
    assert combo.itemText(arc) == "Arc (offline)"
    assert combo.findText("BI") >= 0          # selectable items keep the code as text
    online = [dict(e, enabled=True, label=e["code"], tooltip="") for e in fixture["map"]]
    QTIMENU.apply_status(combo, online)
    assert combo.itemText(arc) == "Arc" and "Arc" in QTIMENU.offered_codes(combo)
