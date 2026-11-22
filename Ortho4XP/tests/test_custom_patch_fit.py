"""A custom patch new to a tile turns "Fit custom airport buildings" off
FOR ITS AIRPORT (#2182: per airport, the tile's other airports keep
theirs); turning it on asks first (owner RULINGS 2026-11-18l, #2172).  Engine
twin: synthetic Patches and build folders only — no corpus, no build."""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Airport_Fit as FIT  # noqa: E402
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


def test_a_new_custom_patch_turns_its_airport_off_once(tile):
    _patch(tile, "KASE_custom.patch.osm")
    _patch(tile, "KEGE_auto.patch.osm")          # the auto patch: not custom
    _patch(tile, "KRIL_edited.patch.osm")        # the editor's own: refitted
    assert CP.fit_state(tile) == (["KASE"], False)
    assert CP.airport_fits(tile, ["KASE", "KEGE"]) == {"KASE": False,
                                                      "KEGE": True}
    assert CP.stand_down_new(tile) == ["KASE"]
    # per airport: the tile's setting is untouched, KEGE still fits
    assert tile.modify_custom_airports is True and tile.writes == []
    assert FIT.read(tile.build_dir) == {"KASE": False}
    assert not FIT.fits(tile, "KASE") and FIT.fits(tile, "KEGE")
    # seen: the user's later "on" for KASE stays on, build after build
    FIT.set_fit(tile.build_dir, "KASE", True)
    assert CP.stand_down_new(tile) == []
    assert FIT.fits(tile, "KASE")
    assert CP.fit_state(tile) == (["KASE"], True)


def test_a_changed_patch_is_new_again(tile):
    _patch(tile, "KASE_custom.patch.osm")
    CP.stand_down_new(tile)
    FIT.set_fit(tile.build_dir, "KASE", True)
    _patch(tile, "KASE_custom.patch.osm", "<osm>changed</osm>")
    assert CP.stand_down_new(tile) == ["KASE"]
    assert not FIT.fits(tile, "KASE")


def test_no_custom_patch_writes_nothing(tile):
    assert CP.stand_down_new(tile) == []
    assert not os.path.exists(tile.build_dir)
    assert tile.writes == [] and tile.modify_custom_airports is True
    assert CP.fit_confirm_text([]) == ""


def test_an_airport_without_its_own_value_takes_the_tiles(tile):
    """The migration: the former per-tile value is every airport's until
    its own switch changes; a per-build switch wins for every airport."""
    tile.modify_custom_airports = False
    assert not FIT.fits(tile, "KEGE") and not FIT.any_fits(tile)
    FIT.set_fit(tile.build_dir, "KEGE", True)
    assert FIT.fits(tile, "KEGE") and FIT.any_fits(tile)
    assert not FIT.fits(tile, "KASE")
    tile._build_override_saved = {"modify_custom_airports": True}
    assert not FIT.fits(tile, "KEGE") and not FIT.any_fits(tile)
    tile.modify_custom_airports = True
    assert FIT.fits(tile, "KASE") and FIT.any_fits(tile)


def test_the_question_names_the_airports():
    text = CP.fit_confirm_text(["KASE", "KEGE"])
    assert text.startswith("Custom patches are installed for KASE, KEGE.")
    assert text.endswith("Continue?")
