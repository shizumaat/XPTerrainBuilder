"""A custom patch new to a tile turns "Fit custom airport buildings" off;
turning it on asks first (owner RULINGS 2026-11-18l, #2172).  Engine
twin: synthetic Patches and build folders only — no corpus, no build."""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Custom_Patches as CP  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture
def tile(tmp_path, monkeypatch):
    patches = tmp_path / "Patches"
    patches.mkdir()
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(patches))
    writes = []
    monkeypatch.setattr(SM, "write_tile",
                        lambda lat, lon, folder, values: writes.append(values))
    t = types.SimpleNamespace(lat=39, lon=-107, custom_build_dir="",
                              build_dir=str(tmp_path / "tile"),
                              modify_custom_airports=True)
    t.patches, t.writes = patches, writes
    return t


def _patch(tile, name, text="<osm/>"):
    (tile.patches / name).write_text(text, encoding="utf-8", newline="")


def test_a_new_custom_patch_turns_fitting_off_once(tile):
    _patch(tile, "KASE_custom.patch.osm")
    _patch(tile, "KEGE_auto.patch.osm")          # the auto patch: not custom
    _patch(tile, "KRIL_edited.patch.osm")        # the editor's own: refitted
    assert CP.fit_state(tile) == (["KASE"], False)
    assert CP.stand_down_new(tile) == ["KASE"]
    assert tile.modify_custom_airports is False
    assert tile.writes == [{"modify_custom_airports": False}]
    # seen: the user's later "on" stays on, build after build
    tile.modify_custom_airports = True
    assert CP.stand_down_new(tile) == []
    assert tile.modify_custom_airports is True
    assert CP.fit_state(tile) == (["KASE"], True)


def test_a_changed_patch_is_new_again(tile):
    _patch(tile, "KASE_custom.patch.osm")
    CP.stand_down_new(tile)
    tile.modify_custom_airports = True
    _patch(tile, "KASE_custom.patch.osm", "<osm>changed</osm>")
    assert CP.stand_down_new(tile) == ["KASE"]
    assert tile.modify_custom_airports is False


def test_no_custom_patch_writes_nothing(tile):
    assert CP.stand_down_new(tile) == []
    assert not os.path.exists(tile.build_dir)
    assert tile.writes == [] and tile.modify_custom_airports is True
    assert CP.fit_confirm_text([]) == ""


def test_the_question_names_the_airports():
    text = CP.fit_confirm_text(["KASE", "KEGE"])
    assert text.startswith("Custom patches are installed for KASE, KEGE.")
    assert text.endswith("Continue?")
