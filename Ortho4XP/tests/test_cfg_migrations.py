"""Twin of O4_Cfg_Migrations: the global cfg's one-time migrations.

The 1.0.480 report (owner 2026-11-10): a global cfg from before the
2026-11-09 presets showed "Custom" for Start-from AND for Detail.  Detail
read Custom because the Mac app read the cfg before the JSONL engine ran
the airport Detail hand-over (lazily, at its first config import) and
never re-read it; Start-from read Custom because every old preset wrote
``cover_extent=1.0`` and every preset now writes 0.0.  Synthetic cfgs
only (tmp_path) — never the user's real config.
"""

import pathlib

import O4_Airport_Detail as DETAIL
import O4_Cfg_Migrations as MIG
import O4_Settings_Model as SM
import O4_Settings_Presets as PRESETS

#: The key set of the reported global cfg, before any migration.
OWNER_KEYS = ("cover_airports_with_highres=ICAO\ncover_extent=1.0\n"
              "cover_zl=18\nmasks_width=500\nimagery_on_demand=True\n")


def _cfg(tmp_path, body):
    path = tmp_path / "XPTerrainBuilder.cfg"
    path.write_text(body, encoding="utf-8", newline="\n")
    return str(path)


def _current(path):
    raw = SM._parse_cfg(path, strip_quotes=False)
    return {name: raw.get(name, SM.global_effective_value(name, {}))
            for name in PRESETS.PRESET_KEYS[1:]}


def test_owner_key_set_reads_detail_icao_and_a_preset(tmp_path):
    path = _cfg(tmp_path, OWNER_KEYS)
    MIG.migrate_global(path)
    current = _current(path)
    states = DETAIL.feature_states(current, same=SM.values_equivalent)
    assert DETAIL.from_states(states) == "icao"
    current[PRESETS.ZOOM_PREF] = "16"
    assert PRESETS.matching_preset(current).key == "sharper_airports"


def test_unmigrated_owner_key_set_is_detail_custom(tmp_path):
    """The defect's witness: read BEFORE the hand-over, Detail is Custom
    (imagery at ICAO airports, sea depth at all)."""
    current = _current(_cfg(tmp_path, OWNER_KEYS))
    states = DETAIL.feature_states(current, same=SM.values_equivalent)
    assert DETAIL.from_states(states) is None


def test_old_preset_extent_moves_when_the_rest_is_a_preset(tmp_path):
    body = "".join("%s=%s\n" % (name, value) for name, value in
                   PRESETS.cfg_values(PRESETS.preset("balanced")).items())
    path = _cfg(tmp_path, body.replace("cover_extent=0.0", "cover_extent=1.0"))
    lines = MIG._migrate_preset_extent(path)
    assert lines and "cover_extent=0.0" in lines[0]
    assert SM._parse_cfg(path)["cover_extent"] == "0.0"
    assert MIG.PRESET_EXTENT_ENTRY in pathlib.Path(
        path + ".defaults").read_text(encoding="utf-8")


def test_hand_changed_key_keeps_the_extent(tmp_path):
    body = "".join("%s=%s\n" % (name, value) for name, value in
                   PRESETS.cfg_values(PRESETS.preset("balanced")).items())
    body = body.replace("cover_extent=0.0", "cover_extent=1.0")
    path = _cfg(tmp_path, body.replace("elevation_level=auto",
                                       "elevation_level=30", 1))
    assert MIG._migrate_preset_extent(path) == []
    assert SM._parse_cfg(path)["cover_extent"] == "1.0"
    # Registered: a later match is never migrated (the 1.0 is the user's).
    path = _cfg(tmp_path, body)
    assert MIG._migrate_preset_extent(path) == []
    assert SM._parse_cfg(path)["cover_extent"] == "1.0"


def test_other_extent_never_moves(tmp_path):
    path = _cfg(tmp_path, OWNER_KEYS.replace("cover_extent=1.0",
                                             "cover_extent=2.0"))
    MIG.migrate_global(path)
    assert SM._parse_cfg(path)["cover_extent"] == "2.0"


def test_mac_app_rereads_the_global_cfg_on_the_engine_hello():
    """The engine migrates before its hello (``jsonl.serve``); the Mac app
    must re-read the global cfg there, or it keeps the values it read
    before the migration for the whole session."""
    root = pathlib.Path(__file__).resolve().parents[2]
    swift = (root / "Sources/XPTerrainBuilder/BuildModel.swift").read_text(
        encoding="utf-8")
    hello = swift.split("case .hello(", 1)[1].split("case .", 1)[0]
    assert "reloadGlobalConfig()" in hello
    jsonl = (root / "Ortho4XP/src/o4_engine/jsonl.py").read_text(
        encoding="utf-8")
    assert jsonl.index("CFG_MIGRATIONS.migrate_global()") < jsonl.index(
        "write_obj(serialize_event(EngineHello(")
