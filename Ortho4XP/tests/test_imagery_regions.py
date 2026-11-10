"""On demand region by region (RULINGS 2026-11-10e (3)).

The generated region table (simHeaven's X-World regions) holds every 1°
tile in exactly one region and is current with its generator; a tile's
on-demand decision reads its region's switch; a first run keeps on the
regions holding built tiles; Settings carries one switch per region.
Hermetic: no network, no Qt.
"""

from __future__ import annotations

import os
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
sys.path.insert(0, str(HERE.parent / "tools"))

import gen_imagery_regions as GEN  # noqa: E402
import O4_Cfg_Migrations as MIG  # noqa: E402
import O4_Cfg_Vars as CV  # noqa: E402
import O4_Glossary as GLOSSARY  # noqa: E402
import O4_Imagery_Placeholder as PLACEHOLDER  # noqa: E402
import O4_Imagery_Regions as REGIONS  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
from O4_Imagery_Regions_Table import ROWS  # noqa: E402

CODES = [code for code, _label in REGIONS.REGIONS]

#: Tiles (south-west corner) and the region the map puts them in.
LANDMARKS = {
    (48, 2): "europe",              # Paris
    (64, -22): "europe",            # Reykjavik
    (78, 15): "europe",             # Svalbard
    (41, 28): "europe",             # Istanbul
    (40, -74): "america",           # New York
    (64, -52): "america",           # Nuuk, Greenland
    (21, -158): "america",          # Honolulu
    (51, -177): "america",          # Adak, Aleutians
    (-55, -69): "america",          # Ushuaia
    (35, 139): "asia",              # Tokyo
    (-7, 106): "asia",              # Jakarta
    (64, -174): "asia",             # Provideniya, Chukotka
    (32, 34): "asia",               # Tel Aviv
    (30, 31): "africa",             # Cairo
    (36, 3): "africa",              # Algiers
    (28, -16): "africa",            # Canary Islands
    (-21, 57): "africa",            # Mauritius
    (-34, 151): "australia_oceania",  # Sydney
    (-10, 147): "australia_oceania",  # Port Moresby
    (-37, 174): "australia_oceania",  # Auckland
    (-78, 166): "antarctica",       # McMurdo
}


def test_the_table_is_current_with_its_generator():
    table = HERE.parent / "src" / "O4_Imagery_Regions_Table.py"
    assert table.read_text(encoding="utf-8") == GEN.render()
    assert tuple(GEN.REGION_CODES) == tuple(CODES)


def test_every_tile_is_in_exactly_one_region():
    assert sorted(ROWS) == list(range(-90, 90))
    seen = set()
    for lat, runs in ROWS.items():
        starts = [lon for lon, _code in runs]
        assert starts[0] == -180 and starts == sorted(set(starts)), lat
        assert all(a[1] != b[1] for a, b in zip(runs, runs[1:])), lat
        for lon in range(-180, 180):
            seen.add(REGIONS.region_of(lat, lon))
    assert seen == set(CODES)


def test_landmarks():
    for (lat, lon), code in LANDMARKS.items():
        assert REGIONS.region_of(lat, lon) == code, (lat, lon)
    assert REGIONS.region_of(10, 180) == REGIONS.region_of(10, -180)


def _tile(lat, lon, **switches):
    return types.SimpleNamespace(lat=lat, lon=lon, imagery_on_demand=True,
                                 texture_mode="full_ortho",
                                 placeholder_zl_drop=3, **switches)


def test_a_tile_outside_the_chosen_regions_builds_full_imagery():
    assert PLACEHOLDER.drop(_tile(48, 2)) == 3
    assert PLACEHOLDER.drop(_tile(48, 2, imagery_on_demand_europe=False)) == 0
    assert PLACEHOLDER.drop(_tile(40, -74, imagery_on_demand_europe=False)) == 3
    assert PLACEHOLDER.drop(_tile(40, -74, imagery_on_demand_america=False)) == 0


def test_the_switches_are_registered_and_reach_tiles():
    for code, label in REGIONS.REGIONS:
        name = REGIONS.setting_name(code)
        assert CV.cfg_vars[name]["type"] is bool
        assert CV.cfg_vars[name]["default"] is True
        assert name in CV.list_tile_vars
        row = SM.get_setting(name)
        assert row.scope == "app" and not row.advanced
        assert row.label == GLOSSARY.TERMS["ondemand_region"].format(region=label)


def test_default_settings_follow_the_built_tiles():
    every = REGIONS.default_settings([])
    assert set(every.values()) == {True} and len(every) == len(CODES)
    europe = REGIONS.default_settings([(48, 2), (50, 8)])
    assert [n for n, on in europe.items() if on] == ["imagery_on_demand_europe"]


def _cfg(tmp_path, text="imagery_on_demand=True\n"):
    path = tmp_path / "XPTerrainBuilder.cfg"
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def test_first_run_keeps_on_the_regions_with_built_tiles(tmp_path, monkeypatch):
    monkeypatch.setattr(MIG, "_built_tiles", lambda raw: {(35, 139)})
    path = _cfg(tmp_path)
    lines = MIG._migrate_ondemand_regions(path)
    data = SM._parse_cfg(path, strip_quotes=False)
    assert data["imagery_on_demand_asia"] == "True"
    assert data["imagery_on_demand_europe"] == "False"
    assert len(lines) == len(CODES)
    assert MIG._migrate_ondemand_regions(path) == []      # once


def test_first_run_leaves_a_chosen_region_or_no_tiles_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(MIG, "_built_tiles", lambda raw: {(35, 139)})
    path = _cfg(tmp_path, "imagery_on_demand_europe=False\n")
    assert MIG._migrate_ondemand_regions(path) == []
    monkeypatch.setattr(MIG, "_built_tiles", lambda raw: set())
    other = tmp_path / "other"
    other.mkdir()
    assert MIG._migrate_ondemand_regions(_cfg(other)) == []
    assert "imagery_on_demand_asia" not in SM._parse_cfg(
        os.path.join(other, "XPTerrainBuilder.cfg"))


def test_a_fresh_data_root_starts_with_every_region(tmp_path, monkeypatch):
    monkeypatch.setattr(MIG, "_built_tiles", lambda raw: {(35, 139)})
    path = str(tmp_path / "XPTerrainBuilder.cfg")
    assert MIG._migrate_ondemand_regions(path) == []
    assert MIG.REGIONS_ENTRY in CV._read_register(path)
    assert not os.path.exists(path)
