"""#1229 / owner RULINGS 2026-10-26c: a custom patch is honoured, shown
(the map band, the tile info line) and can be set aside — never deleted —
with "Use auto patch" (``O4_Custom_Patches``; the engine commands
``custom_patches`` / ``use_auto_patch``)."""

import os
import sys
import types

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
    with open(path, "w", encoding="utf-8", newline="") as handle:
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
        {"lat": 30, "lon": 31, "files": ["HECA.patch.osm"], "notices": []},
        {"lat": 47, "lon": -122, "files": ["KSEA_mine.patch.osm"],
         "notices": []},
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
                  CUSTOM.KEEP_CUSTOM_PATCH_TITLE,
                  " — the auto patch does not run for ", "this airport",
                  "these airports"):
        assert '"%s"' % words in text or words in text, words
    help_text = CUSTOM.use_auto_patch_help()
    assert help_text.split(" (")[0] in text


# ── which elevation a custom patch was built for (#2179) ─────────────
@pytest.fixture
def built(patches, tmp_path, monkeypatch):
    """A tile whose build folder the fit's record goes to."""
    folder = tmp_path / "tile"
    monkeypatch.setattr(FNAMES, "build_dir",
                        lambda lat, lon, custom="": str(folder))
    return types.SimpleNamespace(lat=30, lon=31, build_dir=str(folder),
                                 dem=types.SimpleNamespace(subdems=()))


def _remembered(built, name, source):
    import O4_Patch_Rebase as REBASE

    REBASE._remember(built, name, os.path.join(
        FNAMES.patch_dir(30, 31), name), source)


def test_the_notice_names_the_elevation_once_per_patch(patches, built):
    _write(patches, "HECA.patch.osm", "mine")
    _write(patches, "HEAZ_edited.patch.osm")         # the editor's own: none
    _remembered(built, "HECA.patch.osm",
                "base elevation (Viewfinderpanoramas)")
    _remembered(built, "HEAZ_edited.patch.osm", "build DEM")

    [notice] = PC.custom_patches()["tiles"][0]["notices"]
    assert notice == {
        "icao": "HECA", "file": "HECA.patch.osm",
        "source": "base elevation (Viewfinderpanoramas)",
        "text": "This custom patch (HECA.patch.osm) was built for "
                "Viewfinderpanoramas (the Ortho4XP default). For "
                "higher-resolution elevation data at this airport, use the "
                "auto patch."}

    assert PC.custom_patch_notice_seen("+30+031", "HECA.patch.osm") == {
        "tile": "+30+031", "file": "HECA.patch.osm"}
    assert CUSTOM._elevation_notices(30, 31) == []     # answered: remembered
    # a changed patch is asked about again, once a build identified it
    _write(patches, "HECA.patch.osm", "mine, changed")
    assert CUSTOM._elevation_notices(30, 31) == []
    _remembered(built, "HECA.patch.osm", "KASE_usgs3dep.tif")
    assert "built for KASE_usgs3dep.tif." in \
        CUSTOM._elevation_notices(30, 31)[0]["text"]
    session = object.__new__(jsonl.EngineSession)
    assert jsonl._build_handlers(session)["custom_patch_notice_seen"] is \
        PC.custom_patch_notice_seen
    with pytest.raises(ValueError, match="no custom patch"):
        PC.custom_patch_notice_seen("+30+031", "KJFK.patch.osm")


def test_a_build_dem_that_is_only_the_base_goes_by_the_base(patches, built,
                                                           monkeypatch):
    """No inset at the airport: the build DEM IS the base raster, and the
    notice names it (the build DEM wins the fit's tie)."""
    import O4_DEM_Utils as DEM
    import O4_Patch_Rebase as REBASE

    monkeypatch.setattr(DEM, "base_source_label",
                        lambda dem: "Viewfinderpanoramas")
    _write(patches, "HECA.patch.osm")
    _remembered(built, "HECA.patch.osm", REBASE.BUILD_SOURCE)
    assert CUSTOM._elevation_notices(30, 31)[0]["source"] == \
        "base elevation (Viewfinderpanoramas)"
    built.dem.subdems = ("an inset",)
    _remembered(built, "HECA.patch.osm", REBASE.BUILD_SOURCE)
    assert "high-resolution elevation" in \
        CUSTOM._elevation_notices(30, 31)[0]["text"]


def test_the_source_is_identified_with_the_rebase_off(patches, built,
                                                      monkeypatch):
    """The setting that turns the re-base off does not turn the notice
    off: ``mesh_path`` still runs the fit and records it."""
    import O4_Patch_Rebase as REBASE

    _write(patches, "HECA.patch.osm")
    monkeypatch.setattr(REBASE, "_fit", lambda tile, path: (
        None, None, None, None, None, "SRTM.tif", {}))
    setattr(built, REBASE.SETTING_KEY, False)
    path = REBASE.mesh_path(built, patches, "HECA.patch.osm")
    assert path == os.path.join(patches, "HECA.patch.osm")
    assert CUSTOM._elevation_notices(30, 31)[0]["source"] == "SRTM.tif"
