"""Shipped and supplied text files read the same on every Windows (#539).

``open(path, "r")`` with no ``encoding=`` reads in the machine's ANSI code
page.  The imagery provider reader did, with no ``except`` around it: on a
double-byte page (cp932 / 936 / 949 / 950) the first shipped file with a
non-ASCII byte (``Providers/Albania/AL.lay``) raised out of
``initialize_providers_dict`` -- the Qt app's start-up, and the whole
imagery registry of the JSONL engine.  The config writers named no
encoding either, so a path outside the code page could not be saved.

The twins emulate a machine's default text encoding the way
``test_provider_registry_selfcheck`` does: a text-mode ``open`` that names
no encoding gets the code page.  No network.
"""

import builtins
import os

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_Imagery_Selfcheck as SELFCHECK
import O4_Imagery_Utils as IMG
import O4_OSM_Extracts as EXTRACTS
import O4_Import_Selfcheck as IMPORT_SELFCHECK
import O4_Settings_Model as SM
import O4_Text_Files as TEXT
import O4_UI_Utils as UI

CODE_PAGES = ["cp932", "cp936", "cp949", "cp950", "cp1250", "cp1252",
              "utf-8"]
REGISTRIES = ("providers_dict", "combined_providers_dict", "extents_dict",
              "color_filters_dict")


def _a_machine_whose_default_text_encoding_is(monkeypatch, code_page,
                                              *modules):
    """Text-mode ``open`` without ``encoding=`` reads and writes in
    ``code_page`` in the named modules, as on a Windows with that ANSI
    code page."""
    def open_(file, mode="r", *args, **kwargs):
        if "b" not in mode and not args[1:] and not kwargs.get("encoding"):
            kwargs["encoding"] = code_page
        return builtins.open(file, mode, *args, **kwargs)
    for module in modules + (TEXT,):
        monkeypatch.setattr(module, "open", open_, raising=False)


def _plain(value):
    if isinstance(value, numpy.ndarray):
        return ("ndarray", value.tolist())
    if isinstance(value, dict):
        return {key: _plain(item) for (key, item) in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _parse_the_imagery_registries():
    """A fresh parse of the directories in force, as plain data; the
    registries in force are put back."""
    in_force = {name: dict(getattr(IMG, name)) for name in REGISTRIES}
    try:
        for name in ("providers_dict", "combined_providers_dict"):
            getattr(IMG, name).clear()
        IMG.initialize_extents_dict()
        IMG.initialize_color_filters_dict()
        IMG.initialize_providers_dict()
        IMG.initialize_combined_providers_dict()
        return {name: _plain(getattr(IMG, name)) for name in REGISTRIES}
    finally:
        for name in REGISTRIES:
            getattr(IMG, name).clear()
            getattr(IMG, name).update(in_force[name])


def _shipped(directory, extension, nested):
    folders = [directory]
    if nested:
        folders = [os.path.join(directory, name)
                   for name in os.listdir(directory)
                   if os.path.isdir(os.path.join(directory, name))]
    return sorted(name.split(".")[0] for folder in folders
                  for name in os.listdir(folder)
                  if name.endswith("." + extension))


def _write(path, body, encoding="utf-8"):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w", encoding=encoding, newline="\n") as handle:
        handle.write(body)


LAYER = "request_type=wms\nwms_size=512\nepsg_code=3857\nurl_prefix=x?\n"


def _scratch_registry(tmp_path, monkeypatch):
    for (name, folder) in (("Provider_dir", "Providers"),
                           ("Extent_dir", "Extents"),
                           ("Filter_dir", "Filters")):
        os.makedirs(str(tmp_path / folder))
        monkeypatch.setattr(FNAMES, name, str(tmp_path / folder))
    return tmp_path / "Providers"


# -- the shipped files -------------------------------------------------

UNDER_UTF8 = {}


@pytest.mark.parametrize("code_page", CODE_PAGES)
def test_every_shipped_imagery_file_parses_whatever_the_ansi_code_page(
        monkeypatch, code_page):
    if not UNDER_UTF8:
        UNDER_UTF8.update(_parse_the_imagery_registries())
    _a_machine_whose_default_text_encoding_is(monkeypatch, code_page, IMG)
    parsed = _parse_the_imagery_registries()
    assert sorted(parsed["providers_dict"]) == _shipped(
        FNAMES.Provider_dir, "lay", True)
    assert sorted(parsed["combined_providers_dict"]) == _shipped(
        FNAMES.Provider_dir, "comb", False)
    assert sorted(set(parsed["extents_dict"]) - {"global"}) == _shipped(
        FNAMES.Extent_dir, "ext", True)
    assert sorted(set(parsed["color_filters_dict"]) - {"none"}) == _shipped(
        FNAMES.Filter_dir, "flt", False)
    assert parsed == UNDER_UTF8
    (ok, line) = SELFCHECK.imagery_registry_selfcheck()
    assert ok and line == (
        "imagery provider registry: ok %d providers, %d combined, "
        "%d extents, %d filters" % (
            len(parsed["providers_dict"]),
            len(parsed["combined_providers_dict"]),
            len(parsed["extents_dict"]) - 1,
            len(parsed["color_filters_dict"]) - 1))


def test_a_shipped_file_is_not_ascii_so_the_twin_above_bites():
    with open(os.path.join(FNAMES.Provider_dir, "Albania", "AL.lay"),
              "rb") as handle:
        raw = handle.read()
    assert not raw.isascii()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("cp932")


def test_the_selfcheck_leaves_the_registries_in_force(monkeypatch):
    before = {name: dict(getattr(IMG, name)) for name in REGISTRIES}
    directories = (FNAMES.Provider_dir, FNAMES.Extent_dir, FNAMES.Filter_dir)
    SELFCHECK.imagery_registry_selfcheck()
    assert {name: dict(getattr(IMG, name)) for name in REGISTRIES} == before
    assert directories == (FNAMES.Provider_dir, FNAMES.Extent_dir,
                           FNAMES.Filter_dir)


def test_the_engine_entry_prints_the_imagery_line(capsys):
    assert IMPORT_SELFCHECK.import_selfcheck_main(
        ["Ortho4XP", "--import-selfcheck", "json"]) == 0
    assert "imagery provider registry: ok %d providers, " % len(_shipped(
        FNAMES.Provider_dir, "lay", True)) in capsys.readouterr().out


# -- dotfiles, files in another encoding -------------------------------

def test_a_dotfile_beside_a_definition_is_no_provider(tmp_path, monkeypatch):
    providers = _scratch_registry(tmp_path, monkeypatch)
    _write(providers / "Land" / "REAL.lay", LAYER)
    for junk in (".REAL.lay.swp", "._REAL.lay", ".lay"):
        with open(str(providers / "Land" / junk), "wb") as handle:
            handle.write(b"b0VIM 8.1\x00\x80\x81\xfe\xff")
    with open(str(providers / "._EUR.comb"), "wb") as handle:
        handle.write(b"\x00\x05\x16\x07\x80")
    parsed = _parse_the_imagery_registries()
    assert sorted(parsed["providers_dict"]) == ["REAL"]
    assert parsed["combined_providers_dict"] == {}
    assert SELFCHECK.imagery_registry_selfcheck() == (
        True, "imagery provider registry: ok 1 providers, 0 combined, "
              "0 extents, 0 filters")
    elevation = tmp_path / "Elevation"
    _write(elevation / "REAL.elv", "access_strategy=wcs_kvp\n")
    with open(str(elevation / "._REAL.elv"), "wb") as handle:
        handle.write(b"\x00\x05\x16\x07\x80")
    assert sorted(INSETS.initialize_elevation_providers_dict(
        str(elevation))) == ["REAL"]
    assert INSETS.provider_registry_selfcheck(str(elevation)) == (
        True, "elevation provider registry: ok 1 providers")


def test_a_supplied_file_with_a_latin1_byte_neither_raises_nor_drops(
        tmp_path, monkeypatch):
    providers = _scratch_registry(tmp_path, monkeypatch)
    _write(providers / "Land" / "LATIN.lay",
           "# orthophoto de la région\n" + LAYER + "layers=Orthophotos-été\n",
           encoding="latin-1")
    _write(providers / "Land" / "PLAIN.lay", LAYER)
    parsed = _parse_the_imagery_registries()
    assert sorted(parsed["providers_dict"]) == ["LATIN", "PLAIN"]
    assert parsed["providers_dict"]["LATIN"]["layers"] == "Orthophotos-été"
    assert parsed["providers_dict"]["LATIN"]["wms_size"] == 512
    # ... and the bundle's own check still names it: OUR files are UTF-8.
    assert SELFCHECK.imagery_registry_selfcheck() == (
        False, "imagery provider registry: FAIL 2 of 2 files; "
               "not read as UTF-8 LATIN.lay")


def test_the_selfcheck_names_a_definition_that_did_not_parse(
        tmp_path, monkeypatch):
    providers = _scratch_registry(tmp_path, monkeypatch)
    _write(providers / "Land" / "GOOD.lay", LAYER)
    _write(providers / "Land" / "BAD.lay", "request_type=carrier_pigeon\n")
    _write(providers / "ALL.comb", "NOWHERE default default medium\n")
    assert SELFCHECK.imagery_registry_selfcheck() == (
        False, "imagery provider registry: FAIL 1 of 3 files; "
               "not parsed BAD.lay,ALL.comb")
    assert SELFCHECK.imagery_registry_selfcheck(
        provider_dir=str(tmp_path / "absent"))[1].startswith(
            "imagery provider registry: FAIL no directory ")


def test_supplied_text_is_utf8_then_the_legacy_code_page_then_any_byte(
        tmp_path, monkeypatch):
    path = str(tmp_path / "file.txt")
    with open(path, "wb") as handle:
        handle.write("\ufeffa=Zürich — 東京\r\nb=2\n".encode("utf-8"))
    assert TEXT.open_supplied(path).readlines() == [
        "a=Zürich — 東京\n", "b=2\n"]
    with open(path, "wb") as handle:
        handle.write("dir=C:\\Users\\José\n".encode("cp1252"))
    assert TEXT.open_supplied(path).read() == "dir=C:\\Users\\José\n"
    with open(path, "wb") as handle:
        handle.write("dir=C:\\Users\\東京\n".encode("cp932"))
    monkeypatch.setattr(TEXT, "_ansi_code_page", lambda: "cp932")
    assert TEXT.open_supplied(path, legacy_ansi=True).read() == (
        "dir=C:\\Users\\東京\n")
    assert "\\Users\\" in TEXT.open_supplied(path).read()       # no raise
    assert TEXT.decode_supplied(bytes(range(256)), legacy_ansi=True)


# -- what the engine writes and reads back ------------------------------

@pytest.mark.parametrize("code_page", ["cp1252", "cp932"])
def test_a_config_round_trips_a_path_outside_the_code_page(
        tmp_path, monkeypatch, code_page):
    _a_machine_whose_default_text_encoding_is(monkeypatch, code_page, SM)
    path = str(tmp_path / "Ortho4XP.cfg")
    values = {"custom_scenery_dir": "C:/Users/José/東京/Ελλάδα/Custom Scenery",
              "default_website": "BI"}
    SM._write_atomic_with_backup(path, values)
    assert SM._parse_cfg(path) == values
    with open(path, "rb") as handle:
        assert handle.read().decode("utf-8").startswith(
            "custom_scenery_dir=C:/Users/José/東京/Ελλάδα/Custom Scenery\n")


def test_a_config_an_older_build_wrote_in_the_code_page_still_reads(
        tmp_path, monkeypatch):
    path = str(tmp_path / "Ortho4XP.cfg")
    with open(path, "wb") as handle:
        handle.write("custom_scenery_dir=C:/Users/José/X-Plane\n"
                     .encode("cp1252"))
    monkeypatch.setattr(TEXT, "_ansi_code_page", lambda: "cp1252")
    assert SM._parse_cfg(path) == {
        "custom_scenery_dir": "C:/Users/José/X-Plane"}


def test_a_json_index_round_trips_a_name_under_a_cp1252_default(
        tmp_path, monkeypatch):
    # json.dump escapes to ASCII (no writer in src passes ensure_ascii=
    # False), which is why the engine's JSON sidecars are safe unnamed.
    _a_machine_whose_default_text_encoding_is(monkeypatch, "cp1252", EXTRACTS)
    path = str(tmp_path / "index.json")
    payload = {"name": "Adolfo Suárez Madrid–Barajas 東京", "ε": [1, 2]}
    EXTRACTS._write_json_atomic(path, payload)
    assert EXTRACTS._read_json(path) == payload
    with open(path, "rb") as handle:
        assert handle.read().isascii()


def test_the_log_takes_a_character_the_code_page_lacks(tmp_path, monkeypatch):
    _a_machine_whose_default_text_encoding_is(monkeypatch, "cp1252", UI)
    monkeypatch.setattr(UI.FNAMES, "data_path",
                        lambda name: str(tmp_path / name))
    UI.logprint("Δ = 3 m ≥ ε", "東京")
    with open(str(tmp_path / "Ortho4XP.log"), "rb") as handle:
        assert "Δ = 3 m ≥ ε 東京\n" in handle.read().decode("utf-8")
