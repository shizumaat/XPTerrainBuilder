"""The tile's customized settings (#1350): the engine's answer and its
wire command.  A temporary data folder only: no corpus, no network.  The
Qt badge and tile pane: ``test_qt_tile_customizations.py``."""
import json
import os

import O4_Cfg_Vars
import O4_Settings_Model as SM
import O4_Tile_Customizations as TC
import pytest


def make_data(tmp_path, monkeypatch):
    """A global cfg setting ``road_level=4`` and an empty tiles folder."""
    global_cfg = tmp_path / "Ortho4XP.cfg"
    global_cfg.write_text("road_level=4\n", encoding="utf-8", newline="")
    monkeypatch.setattr(SM, "_default_global_cfg", lambda: str(global_cfg))
    tiles = tmp_path / "Tiles"
    tiles.mkdir()
    return str(tiles)


@pytest.fixture
def data(tmp_path, monkeypatch):
    return make_data(tmp_path, monkeypatch)


def _write_tile(tiles, lines):
    folder = os.path.join(tiles, "zOrtho4XP_+45+005")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "Ortho4XP_+45+005.cfg")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(SM.tile_cfg_stamp_line())
        handle.write("".join(line + "\n" for line in lines))
    return path


def test_no_cfg_and_no_overrides_are_empty(data):
    assert TC.tile_customizations(45, 5, data)["customizations"] == []
    assert TC.customized_tiles([(45, 5), (46, 5)], data) == set()
    # Values equal to the inherited ones are not customizations.
    _write_tile(data, ["road_level=4", "masks_width=%s"
                       % O4_Cfg_Vars.cfg_vars["masks_width"]["default"]])
    assert TC.tile_customizations(45, 5, data)["customizations"] == []


def test_two_overrides_are_two_rows_with_their_defaults(data):
    assert O4_Cfg_Vars.cfg_vars["approach_rings"]["default"] == "auto"
    _write_tile(data, ["road_level=5", "approach_rings=off",
                       "texture_mode=" + str(
                           O4_Cfg_Vars.cfg_vars["texture_mode"]["default"])])
    result = TC.tile_customizations(45, 5, data)
    assert (result["lat"], result["lon"]) == (45, 5)
    rows = {row["key"]: row for row in result["customizations"]}
    assert set(rows) == {"road_level", "approach_rings"}
    road = rows["road_level"]
    assert (road["tile_value"], road["default_value"]) == ("5", "4")
    assert road["label"] == SM.get_setting("road_level").label
    assert road["affects_output"] is True
    assert rows["approach_rings"]["default_value"] == "auto"
    assert rows["approach_rings"]["affects_output"] is True
    assert TC.customized_tiles([(45, 5), (46, 5)], data) == {(45, 5)}


def test_imagery_source_zoom_and_zones_are_not_customizations(data):
    _write_tile(data, ["default_website=BI", "default_zl=18",
                       "zone_list=[]"])
    assert TC.tile_customizations(45, 5, data)["customizations"] == []


def test_texture_only_setting_does_not_affect_the_ground(data):
    spec = O4_Cfg_Vars.cfg_vars["color_harmonization"]
    other = "False" if str(spec["default"]) == "True" else "True"
    _write_tile(data, ["color_harmonization=" + other])
    (row,) = TC.tile_customizations(45, 5, data)["customizations"]
    assert row["key"] == "color_harmonization"
    assert row["affects_output"] is False
    assert row["tile_text"] == ("On" if other == "True" else "Off")


def test_unstamped_cfg_is_retired_as_the_build_would(data):
    path = _write_tile(data, [])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("road_level=5\n")              # no stamp: pre-1.0.352
    assert TC.tile_customizations(45, 5, data)["customizations"] == []
    assert not os.path.exists(path)


def test_wire_round_trip(data):
    from unittest import mock

    from o4_engine import jsonl
    handler = jsonl._build_handlers(mock.MagicMock())["tile_customizations"]
    assert handler is TC.tile_customizations
    _write_tile(data, ["road_level=5"])
    reply = json.loads(json.dumps(handler(lat=45, lon=5, working_dir=data)))
    (row,) = reply["customizations"]
    assert set(row) == {"key", "label", "tile_value", "default_value",
                        "tile_text", "default_text", "affects_output"}
    assert row["key"] == "road_level" and row["default_value"] == "4"
