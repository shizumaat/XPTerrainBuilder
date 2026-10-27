"""The Settings window's selection rule (#1549, RULINGS 2026-10-28i/j).

``O4_Settings_Selection`` is the rule the Qt window reads; the Mac app
mirrors it in ``Sources/SceneryKit/SettingsSelection.swift``.  This twin
pins the rule (no selection, one tile, matching tiles, conflicting tiles,
a never-built tile counting as the defaults, app-wide settings staying
global) and holds the two apps to the same words.  No Qt, no engine.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Settings_Presets as PRESETS  # noqa: E402
import O4_Settings_Selection as SEL  # noqa: E402

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
         / "SettingsSelection.swift")


def _swift_constant(name):
    text = SWIFT.read_text(encoding="utf-8")
    return re.search(r'static let %s = "((?:[^"\\]|\\.)*)"' % name,
                     text).group(1)


def test_both_apps_say_the_same_words():
    assert _swift_constant("conflictText") == SEL.CONFLICT_TEXT
    assert _swift_constant("confirmTitle") == SEL.CONFIRM_TITLE
    assert _swift_constant("confirmButton") == SEL.CONFIRM_BUTTON
    assert _swift_constant("tilesNote") == SEL.TILES_NOTE
    text = SWIFT.read_text(encoding="utf-8")
    # The two sentences built from a count/name, word for word.
    assert '"Editing the global defaults for new tiles"' in text
    assert SEL.scope_text([]) == "Editing the global defaults for new tiles"
    assert ('"The \\(tileCount) selected tiles have different settings. '
            'Apply this change to all of them?"') in text
    assert SEL.confirm_text(3) == ("The 3 selected tiles have different "
                                   "settings. Apply this change to all of them?")


def test_no_selection_is_the_defaults():
    assert SEL.tile_value([], "road_level", "3") is None
    assert SEL.selection_zoom([], 16) == 16
    assert not SEL.edits_tiles("tile", 0)       # an edit: new tiles only


def test_one_tile_shows_its_own_value():
    assert SEL.tile_value([{"road_level": "5"}], "road_level", "3") == "5"
    assert SEL.selection_zoom([17], 16) == 17
    assert SEL.edits_tiles("tile", 1)


def test_matching_tiles_look_like_one():
    tiles = [{"road_level": "5"}, {"road_level": "5"}]
    assert SEL.tile_value(tiles, "road_level", "3") == "5"
    assert SEL.selection_zoom([17, 17], 16) == 17
    assert not SEL.any_conflict([SEL.tile_value(tiles, "road_level", "3")])


def test_conflicting_tiles_conflict():
    tiles = [{"road_level": "5"}, {}]
    assert SEL.tile_value(tiles, "road_level", "3") is SEL.CONFLICT
    assert SEL.selection_zoom([16, 17], 16) is SEL.CONFLICT
    assert SEL.any_conflict([None, SEL.CONFLICT])
    assert SEL.scope_text(["+48-006", "+49-006"], True) == (
        "Editing 2 tiles · conflicting values")
    assert SEL.scope_text(["+48-006"]) == "Editing tile +48-006"


def test_a_never_built_tile_counts_as_the_defaults():
    # A tile with nothing saved inherits the global value (28j 2) ...
    assert SEL.tile_value([{"road_level": "3"}, {}], "road_level", "3") == "3"
    assert SEL.tile_value([{"road_level": "4"}, {}], "road_level",
                          "3") is SEL.CONFLICT
    # ... and the default detail level.
    assert SEL.selection_zoom([16, None], 16) == 16
    assert SEL.selection_zoom([17, None], 16) is SEL.CONFLICT


def test_app_wide_settings_stay_global():
    for scope in ("app", "pref"):
        assert not SEL.edits_tiles(scope, 3)


def test_a_conflicting_key_matches_no_preset():
    sharper = dict(PRESETS.preset("sharper_airports").values)
    current = dict(sharper)
    assert PRESETS.matching_preset(SEL.preset_values(current)).key == (
        "sharper_airports")
    current["cover_airports_with_highres"] = SEL.CONFLICT
    assert PRESETS.matching_preset(SEL.preset_values(current)) is None
