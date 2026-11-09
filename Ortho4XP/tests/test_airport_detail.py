"""The airport Detail choice, one table in two apps (issue #1985).

``src/O4_Airport_Detail`` is the table; the Mac app mirrors it in
``Sources/XPTerrainBuilder/AirportDetail.swift``.  This twin requires the
two to be equal, every scope key to be an existing setting with a lawful
value, the choices to be told apart, and the one-time migration of an
existing config to change only keys still at their old defaults.

Hermetic: the repo's own files and tmp_path, no Qt, no network.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Airport_Detail as DETAIL  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402

SWIFT = (Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"
         / "AirportDetail.swift")
_LITERAL = r'"((?:[^"\\]|\\.)*)"'


def _swift():
    return SWIFT.read_text(encoding="utf-8", newline="\n")


def _swift_constant(name):
    return re.search(r"static let %s = (.+)\n" % name, _swift()).group(1)


def test_swift_choices_equal_python():
    found = re.findall(r"AirportDetailChoice\(" + _LITERAL + ", " + _LITERAL
                       + r",\s*scope: \[([^\]]*)\]\)", _swift())
    swift = [(key, title, dict(re.findall(_LITERAL + ": " + _LITERAL, scope)))
             for key, title, scope in found]
    python = [(key, title, DETAIL.scope_values(key))
              for key, title in DETAIL.CHOICES]
    assert swift == python


def test_swift_constants_equal_python():
    assert _swift_constant("title") == '"%s"' % DETAIL.TITLE
    assert _swift_constant("summary") == '"%s"' % DETAIL.SUMMARY
    assert _swift_constant("customTitle") == '"%s"' % DETAIL.CUSTOM_TITLE
    assert _swift_constant("defaultKey") == '"%s"' % DETAIL.DEFAULT
    assert int(_swift_constant("outsideZL")) == DETAIL.OUTSIDE_ZL
    assert int(_swift_constant("airportZL")) == DETAIL.AIRPORT_ZL
    keys = re.search(r"static let scopeKeys = \[([^\]]*)\]", _swift()).group(1)
    assert tuple(re.findall(_LITERAL, keys)) == DETAIL.SCOPE_KEYS


def test_every_value_is_a_stored_cfg_form():
    for key, _title in DETAIL.CHOICES:
        for name, value in DETAIL.values(key).items():
            ok, normalized, error = SM.coerce(name, value)
            assert ok, (key, name, error)
            assert normalized == value, (key, name)


def test_swift_features_equal_python():
    found = re.search(r"static let features = \[(.*)\]\n", _swift()).group(1)
    groups = re.findall(r"\[([^\]]*)\]", found)
    assert tuple(tuple(re.findall(_LITERAL, g)) for g in groups) == \
        DETAIL.FEATURES
    assert sum(DETAIL.FEATURES, ()) == DETAIL.SCOPE_KEYS


def test_the_owner_choices():
    # Owner, #1985: None / ICAO airports (default) / All airports; ICAO or
    # All chosen from None is ZL16 outside airports and ZL18 at them.
    assert [title for _k, title in DETAIL.CHOICES] == [
        "None", "ICAO airports", "All airports"]
    assert DETAIL.DEFAULT == "icao"
    assert DETAIL.zoom("none") is None
    for key in ("icao", "all"):
        assert DETAIL.zoom(key) == 16
        assert DETAIL.values(key)["cover_zl"] == "18"
        assert DETAIL.zoom(key, "icao") is None
    assert "cover_zl" not in DETAIL.values("none")


def test_each_choice_is_recognised():
    for key, _title in DETAIL.CHOICES:
        values = dict(DETAIL.values(key), road_level="4", cover_zl="19")
        assert DETAIL._matching(values, same=SM.values_equivalent) == key
    icao = DETAIL.scope_values("icao")
    assert DETAIL._matching(dict(icao, auto_patch="All")) is None
    assert DETAIL._matching({"auto_patch": "ICAO"}) is None
    assert DETAIL._matching(dict(icao, bathymetry_near_icao_airports="true")) \
        == "icao"
    # Depth on for small fields but not ICAO ones is neither choice.
    assert DETAIL._matching(dict(icao, bathymetry_near_icao_airports="False",
                                bathymetry_near_other_airports="True")) is None


def test_a_feature_that_is_off_keeps_the_choice():
    # Owner 2026-11-09T17:01Z: Balanced is Detail ICAO with the sharper
    # airport imagery off.
    balanced = dict(DETAIL.scope_values("icao"),
                    cover_airports_with_highres="False")
    assert DETAIL._matching(balanced) == "icao"
    assert DETAIL._matching(dict(DETAIL.scope_values("all"),
                                airport_elevation_insets="None")) == "all"


def test_switching_scope_keeps_off_features_off():
    balanced = dict(DETAIL.scope_values("icao"),
                    cover_airports_with_highres="False")
    states = DETAIL.feature_states(balanced)
    assert states == ["none", "icao", "icao", "icao"]
    assert DETAIL.values("all", "icao", states) == {
        "auto_patch": "All", "airport_elevation_insets": "All",
        "bathymetry_near_icao_airports": "True",
        "bathymetry_near_other_airports": "True"}
    assert DETAIL.zoom("all", "icao") is None
    assert DETAIL.values("none", "icao", states) == \
        DETAIL.scope_values("none")
    # From None (or Custom) a choice turns everything on, zooms included.
    assert DETAIL.values("icao", "none", DETAIL.feature_states(
        DETAIL.scope_values("none")))["cover_airports_with_highres"] == "ICAO"
    assert DETAIL.zoom("icao", None) == 16


def test_migration_carries_old_configs_over():
    old = {"cover_airports_with_highres": "ICAO", "auto_patch": "ICAO",
           "airport_elevation_insets": "ICAO",
           "bathymetry_near_icao_airports": "True",
           "bathymetry_near_other_airports": "True"}
    assert DETAIL._migrate(old) == {"bathymetry_near_other_airports": "False"}
    assert DETAIL._migrate(dict(old, cover_airports_with_highres="True")) \
        == {"auto_patch": "All", "airport_elevation_insets": "All"}
    # Sharper imagery off: the grading's scope decides (old Balanced).
    assert DETAIL._migrate(dict(old, cover_airports_with_highres="False")) \
        == {"bathymetry_near_other_airports": "False"}


def test_migration_never_changes_a_chosen_value_or_turns_one_on():
    chosen = {"cover_airports_with_highres": "ICAO", "auto_patch": "None",
              "bathymetry_near_other_airports": "False"}
    assert DETAIL._migrate(chosen) == {}
    assert DETAIL._migrate({"cover_airports_with_highres": "False",
                           "auto_patch": "None"}) == {}
    assert DETAIL._migrate({"road_level": "4"}) == {}
    # A sparse tile cfg inherits the global's values.
    tile = {"cover_airports_with_highres": "True"}
    assert DETAIL._migrate(tile, {"auto_patch": "None",
                                 "airport_elevation_insets": "ICAO"}) == {
        "airport_elevation_insets": "All"}


def test_migrate_cfg_runs_once_per_file(tmp_path):
    cfg = tmp_path / "XPTerrainBuilder.cfg"
    cfg.write_text("cover_airports_with_highres=ICAO\n"
                   "bathymetry_near_other_airports=True\n", encoding="utf-8", newline="\n")
    lines = DETAIL.migrate_cfg(str(cfg))
    assert len(lines) == 1 and "bathymetry_near_other_airports" in lines[0]
    assert SM._parse_cfg(str(cfg))["bathymetry_near_other_airports"] == "False"
    # A value set by hand afterwards is never touched again.
    cfg.write_text("cover_airports_with_highres=ICAO\n"
                   "bathymetry_near_other_airports=True\n", encoding="utf-8", newline="\n")
    assert DETAIL.migrate_cfg(str(cfg)) == []
    assert SM._parse_cfg(str(cfg))["bathymetry_near_other_airports"] == "True"
    assert DETAIL.migrate_cfg(str(tmp_path / "missing.cfg")) == []


def test_a_tile_cfg_migrates_against_its_global(tmp_path):
    glob = tmp_path / "global.cfg"
    glob.write_text("auto_patch=ICAO\nairport_elevation_insets=None\n",
                    encoding="utf-8", newline="\n")
    tile = tmp_path / "tile.cfg"
    tile.write_text("cover_airports_with_highres=True\n", encoding="utf-8",
                    newline="\n")
    DETAIL.migrate_cfg(str(tile), inherited_cfg=str(glob))
    assert SM._parse_cfg(str(tile)) == {
        "cover_airports_with_highres": "True", "auto_patch": "All"}
