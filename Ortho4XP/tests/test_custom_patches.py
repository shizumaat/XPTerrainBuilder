"""#1229 / #2179, owner RULINGS 2026-10-26c, 2026-11-23d/f: a custom patch
is shown (the map band, the tile info line) and used per airport "As made"
(the default, with a warning) or by "Our auto patch" — never renamed
(``O4_Custom_Patches``; the engine commands ``custom_patches`` /
``custom_patch_use``)."""

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


def _row(icao, files, use="as_made", chosen=False, tile=(30, 31)):
    return {"icao": icao, "tile": list(tile), "files": files, "use": use,
            "chosen": chosen,
            "warning": CUSTOM.AS_MADE_WARNING if use == "as_made" else ""}


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
        {"lat": 30, "lon": 31, "files": ["HECA.patch.osm"], "notices": [],
         "airports": [_row("HECA", ["HECA.patch.osm"])]},
        {"lat": 47, "lon": -122, "files": ["KSEA_mine.patch.osm"],
         "notices": [], "airports": [_row("KSEA", ["KSEA_mine.patch.osm"],
                                          tile=(47, -122))]},
    ]}
    session = object.__new__(jsonl.EngineSession)
    handlers = jsonl._build_handlers(session)
    assert handlers["custom_patches"] is PC.custom_patches
    assert handlers["custom_patch_use"] is PC.custom_patch_use
    assert "use_auto_patch" not in handlers


def test_as_made_is_the_default_with_its_warning(patches):
    """RULINGS 2026-11-23f: an installed custom patch is used as made, and
    the user is told higher-resolution elevation needs our auto patch.
    The editor's own patch takes no picker."""
    _write(patches, "HECA.patch.osm")
    _write(patches, "HEAZ_edited.patch.osm")
    assert CUSTOM.airport_uses(30, 31) == [_row("HECA", ["HECA.patch.osm"])]
    assert "requires our auto patch" in CUSTOM.AS_MADE_WARNING


def test_our_auto_patch_keeps_the_file_and_is_never_a_rename(patches):
    custom = _write(patches, "HECA.patch.osm", "mine")
    auto = _write(patches, "HECA_auto.patch.osm", "auto")

    out = PC.custom_patch_use("+30+031", "heca", "auto_patch")

    assert out == _row("HECA", ["HECA.patch.osm"], "auto_patch", True)
    with open(custom, encoding="utf-8") as handle:
        assert handle.read() == "mine"
    with open(auto, encoding="utf-8") as handle:
        assert handle.read() == "auto"
    assert sorted(os.listdir(patches)) == [
        "HECA.patch.osm", "HECA_auto.patch.osm", "custom_patch_use.json"]
    assert CUSTOM.custom_patches(30, 31) == ["HECA.patch.osm"]
    assert PC.custom_patch_use("+30+031", "HECA", "default") == _row(
        "HECA", ["HECA.patch.osm"])


def test_one_airport_s_choice_leaves_the_others(patches):
    _write(patches, "HECA.patch.osm")
    _write(patches, "HEAZ.patch.osm")
    PC.custom_patch_use("+30+031", "HECA", "auto_patch")
    assert [(r["icao"], r["use"]) for r in CUSTOM.airport_uses(30, 31)] == [
        ("HEAZ", "as_made"), ("HECA", "auto_patch")]


def test_a_refusal_is_the_users_sentence(patches):
    with pytest.raises(ValueError, match="no custom patch for HECA"):
        PC.custom_patch_use("+30+031", "HECA", "auto_patch")
    _write(patches, "HECA.patch.osm")
    with pytest.raises(ValueError, match="as_made"):
        PC.custom_patch_use("+30+031", "HECA", "blend")


def test_every_decider_follows_the_choice(patches):
    """ONE reader (``O4_Custom_Patch_Use``): the mesh's manual set, the
    selector's, the admission test and the object stage's custom list all
    move together; the editor's own patch always applies."""
    import O4_Custom_Patch_Use as USE
    from auto_patch import object_stage
    from auto_patch import selection as SELECTION

    _write(patches, "HECA.patch.osm")
    _write(patches, "HEAZ_edited.patch.osm")
    assert SELECTION.manual_patch_files_for(patches, "HECA")
    assert FNAMES.manual_patch_icaos_in(patches) == {"HECA", "HEAZ"}
    assert set(object_stage._custom_patch_airports(patches)) == {"HECA"}
    assert CUSTOM.unmodified_airports(30, 31) == ["HECA"]
    PC.custom_patch_use("+30+031", "HECA", "auto_patch")
    assert SELECTION.manual_patch_files_for(patches, "HECA") == []
    assert FNAMES.manual_patch_icaos_in(patches) == {"HEAZ"}
    assert USE.applied_manual_files(patches) == ["HEAZ_edited.patch.osm"]
    assert object_stage._custom_patch_airports(patches) == {}
    assert CUSTOM.unmodified_airports(30, 31) == []


def test_the_info_line_names_the_files():
    assert CUSTOM.info_text(["A.patch.osm", "B.patch.osm"]) == (
        "A.patch.osm, B.patch.osm")


def test_the_mac_app_uses_the_same_words():
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "SceneryKit", "CustomPatches.swift")
    with open(swift, encoding="utf-8") as handle:
        text = handle.read()
    for words in (CUSTOM.CUSTOM_PATCH_TITLE, CUSTOM.USE_AUTO_PATCH_TITLE,
                  CUSTOM.KEEP_CUSTOM_PATCH_TITLE, CUSTOM.AS_MADE_TITLE,
                  CUSTOM.AUTO_PATCH_TITLE, CUSTOM.AS_MADE_HELP,
                  CUSTOM.AUTO_PATCH_HELP, CUSTOM.AS_MADE_WARNING):
        assert '"%s"' % words in text, words
    import O4_Custom_Patch_Use as USE
    for mode in USE.MODES:
        assert '"%s"' % mode in text, mode


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
    import O4_Custom_Patch_Source as REBASE

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
                "Viewfinderpanoramas (the Ortho4XP default) and is used as "
                "made. Higher-resolution elevation is available for this "
                "airport, but it requires our auto patch."}

    assert PC.custom_patch_notice_seen("+30+031", "HECA.patch.osm") == {
        "tile": "+30+031", "file": "HECA.patch.osm"}
    assert CUSTOM._elevation_notices(30, 31) == []     # answered: remembered
    # a changed patch is asked about again, once a build identified it
    _write(patches, "HECA.patch.osm", "mine, changed")
    assert CUSTOM._elevation_notices(30, 31) == []
    _remembered(built, "HECA.patch.osm", "KASE_usgs3dep.tif")
    assert "built for KASE_usgs3dep.tif and" in \
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
    import O4_Custom_Patch_Source as REBASE

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


def test_the_source_is_identified_as_the_mesh_reads_the_patch(
        patches, built, monkeypatch):
    """``include_patches`` records the fit for each custom patch it
    applies (``remember_source``); an airport on our auto patch gets no
    notice."""
    import O4_Custom_Patch_Source as SOURCE

    _write(patches, "HECA.patch.osm")
    monkeypatch.setattr(SOURCE, "_ground_record", lambda *_a: None)
    monkeypatch.setattr(SOURCE, "_fit", lambda tile, path: ("SRTM.tif", {}))
    SOURCE.remember_source(built, patches, "HECA.patch.osm")
    assert CUSTOM._elevation_notices(30, 31)[0]["source"] == "SRTM.tif"
    PC.custom_patch_use("+30+031", "HECA", "auto_patch")
    assert CUSTOM._elevation_notices(30, 31) == []
