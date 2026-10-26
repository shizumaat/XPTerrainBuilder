"""#1229 / owner RULINGS 2026-10-26c: a custom patch is honoured, shown
(the map band, the tile info line) and can be set aside — never deleted —
with "Use auto patch" (``O4_Custom_Patches``; the engine commands
``custom_patches`` / ``use_auto_patch``)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Custom_Patches as CUSTOM  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine import patch_commands as PC  # noqa: E402


@pytest.fixture
def patches(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    directory = FNAMES.patch_dir(30, 31)
    os.makedirs(directory)
    return directory


def _write(directory, name, text="<osm/>"):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def test_only_custom_patches_are_reported(patches):
    _write(patches, "HECA_auto.patch.osm")
    _write(patches, "HECA.patch.osm")
    _write(patches, "HEAZ_edited.patch.osm")
    _write(patches, "HEAX.patch.osm.disabled")
    _write(patches, "notes.txt")

    assert CUSTOM.custom_patches(30, 31) == ["HEAZ_edited.patch.osm",
                                             "HECA.patch.osm"]


def test_the_engine_reports_every_tile_with_one(patches):
    """The band flag comes from the engine: the Mac app reads
    ``custom_patches``, the Qt app the same function in process."""
    _write(patches, "HECA.patch.osm")
    other = FNAMES.patch_dir(-34, 18)
    os.makedirs(other)
    _write(other, "FACT_auto.patch.osm")         # auto only: no band
    third = FNAMES.patch_dir(47, -122)
    os.makedirs(third)
    _write(third, "KSEA_mine.patch.osm")

    assert PC.custom_patches() == {"tiles": [
        {"lat": 30, "lon": 31, "files": ["HECA.patch.osm"]},
        {"lat": 47, "lon": -122, "files": ["KSEA_mine.patch.osm"]},
    ]}
    session = object.__new__(jsonl.EngineSession)
    handlers = jsonl._build_handlers(session)
    assert handlers["custom_patches"] is PC.custom_patches
    assert handlers["use_auto_patch"] is PC.use_auto_patch


def test_use_auto_patch_sets_aside_and_never_deletes(patches):
    custom = _write(patches, "HECA.patch.osm", "mine")
    _write(patches, "HECA.patch.osm.disabled", "an earlier one")
    auto = _write(patches, "HECA_auto.patch.osm", "auto")

    out = PC.use_auto_patch("+30+031")

    assert out == {"set_aside": [custom + ".disabled.2"]}
    assert not os.path.exists(custom)
    with open(custom + ".disabled.2", encoding="utf-8") as handle:
        assert handle.read() == "mine"
    with open(custom + ".disabled", encoding="utf-8") as handle:
        assert handle.read() == "an earlier one"
    with open(auto, encoding="utf-8") as handle:
        assert handle.read() == "auto"
    assert CUSTOM.custom_patches(30, 31) == []
    assert PC.custom_patches() == {"tiles": []}


def test_use_auto_patch_can_name_one_airport(patches):
    _write(patches, "HECA.patch.osm")
    keep = _write(patches, "HEAZ.patch.osm")

    out = PC.use_auto_patch("+30+031", icao="heca")

    assert len(out["set_aside"]) == 1
    assert os.path.isfile(keep)


def test_nothing_to_set_aside_is_the_users_sentence(patches):
    with pytest.raises(ValueError, match="no custom patch"):
        PC.use_auto_patch("+30+031")


def test_the_build_then_admits_the_auto_patch(patches):
    """After "Use auto patch" the build's own admission test sees no
    custom patch for the airport any more."""
    from auto_patch import selection as SELECTION

    _write(patches, "HECA.patch.osm")
    assert SELECTION.manual_patch_files_for(patches, "HECA")
    PC.use_auto_patch("+30+031")
    assert SELECTION.manual_patch_files_for(patches, "HECA") == []


def test_the_info_line_names_the_files():
    assert CUSTOM.info_text(["HECA.patch.osm"]) == (
        "HECA.patch.osm — the auto patch does not run for this airport")
    assert CUSTOM.info_text(["A.patch.osm", "B.patch.osm"]).endswith(
        "these airports")


def test_the_mac_app_uses_the_same_words():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "CustomPatches.swift")
    with open(swift, encoding="utf-8") as handle:
        text = handle.read()
    for words in (CUSTOM.CUSTOM_PATCH_TITLE, CUSTOM.USE_AUTO_PATCH_TITLE,
                  " — the auto patch does not run for ", "this airport",
                  "these airports"):
        assert '"%s"' % words in text or words in text, words
    help_text = CUSTOM.use_auto_patch_help()
    assert help_text.split(" (")[0] in text
