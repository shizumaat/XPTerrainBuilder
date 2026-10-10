"""Every shipped ``.elv`` file becomes a provider on every machine (#510).

The ``.elv`` parser read with the machine's default text encoding.  On a
Windows whose ANSI code page is double-byte (cp932 / 936 / 949 / 950) nine
shipped files do not decode and were "skipped" -- gone from the ladder with
one warning line; on cp1252 they parse with garbled attributions.  The
parser now names UTF-8, and ``--import-selfcheck`` makes the frozen binary
count its own provider files.  No network."""

import builtins
import os

import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_Proj_Runtime as runtime

SHIPPED = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "Providers",
    "Elevation"))
SHIPPED_CODES = sorted(name[:-4] for name in os.listdir(SHIPPED)
                       if name.endswith(".elv"))


def _a_machine_whose_default_text_encoding_is(monkeypatch, code_page):
    """Text-mode ``open`` without ``encoding=`` reads in ``code_page``, as
    it does on a Windows with that ANSI code page."""
    def open_(file, mode="r", *args, **kwargs):
        if "b" not in mode and not args[1:] and not kwargs.get("encoding"):
            kwargs["encoding"] = code_page
        return builtins.open(file, mode, *args, **kwargs)
    monkeypatch.setattr(INSETS, "open", open_, raising=False)


def _write_elv(directory, code, body, encoding="utf-8"):
    with open(os.path.join(str(directory), code + ".elv"), "w",
              encoding=encoding, newline="\n") as handle:
        handle.write(body)


@pytest.mark.parametrize("code_page", ["cp932", "cp936", "cp949", "cp950",
                                       "cp1250", "cp1252"])
def test_every_shipped_file_parses_whatever_the_ansi_code_page(
        monkeypatch, code_page):
    _a_machine_whose_default_text_encoding_is(monkeypatch, code_page)
    registry = INSETS.initialize_elevation_providers_dict(SHIPPED)
    assert sorted(registry) == SHIPPED_CODES
    for definition in registry.values():
        for rung in definition.get("resolution_ladder_rungs", ()):
            assert rung.get("provider", definition["code"]) in registry
    assert INSETS.provider_registry_selfcheck(SHIPPED) == (
        True, "elevation provider registry: ok %d providers"
        % len(SHIPPED_CODES))


def test_a_value_is_the_files_utf8_text_and_a_byte_order_mark_is_dropped(
        tmp_path):
    _write_elv(tmp_path, "DASHED", "access_strategy=wcs_kvp\n"
               "attribution=Survey — 2019 lidar (內政部)\n",
               encoding="utf-8-sig")
    registry = INSETS.initialize_elevation_providers_dict(str(tmp_path))
    assert registry["DASHED"]["attribution"] == (
        "Survey — 2019 lidar (內政部)")
    assert registry["DASHED"]["access_strategy"] == "wcs_kvp"


def test_the_selfcheck_names_what_is_missing_from_the_registry(tmp_path):
    _write_elv(tmp_path, "GOOD", "access_strategy=wcs_kvp\n"
               "resolution_ladder=1|other|provider:NOWHERE\n")
    _write_elv(tmp_path, "NOSTRATEGY", "priority=1\n")
    _write_elv(tmp_path, "LATIN", "access_strategy=wcs_kvp\n"
               "attribution=Survey — lidar\n", encoding="cp1252")
    in_force = INSETS.elevation_providers_dict
    (ok, line) = INSETS.provider_registry_selfcheck(str(tmp_path))
    assert INSETS.elevation_providers_dict is in_force
    assert not ok
    assert line == ("elevation provider registry: FAIL 1 of 3 files; "
                    "not parsed LATIN,NOSTRATEGY; "
                    "ladder rung names no provider GOOD>NOWHERE")


def test_the_selfcheck_names_a_file_read_in_another_encoding(
        tmp_path, monkeypatch):
    _write_elv(tmp_path, "DASHED", "access_strategy=wcs_kvp\n"
               "attribution=Survey — lidar\n")
    monkeypatch.setattr(INSETS, "ELV_ENCODING", "cp1252")
    registry = INSETS.initialize_elevation_providers_dict(str(tmp_path))
    assert "—" not in registry["DASHED"]["attribution"]
    monkeypatch.setattr(INSETS, "ELV_ENCODING", "utf-8-sig")
    monkeypatch.setattr(INSETS, "initialize_elevation_providers_dict",
                        lambda directory=None: registry)
    assert INSETS.provider_registry_selfcheck(str(tmp_path)) == (
        False, "elevation provider registry: FAIL 1 of 1 files; "
               "not read as UTF-8 DASHED")


def test_the_engine_entry_fails_when_the_bundle_has_no_provider_files(
        tmp_path, monkeypatch, capsys):
    assert runtime.import_selfcheck_main(
        ["Ortho4XP", "--import-selfcheck", "json"]) == 0
    assert ("elevation provider registry: ok %d providers"
            % len(SHIPPED_CODES)) in capsys.readouterr().out
    monkeypatch.setattr(FNAMES, "Provider_dir", str(tmp_path))
    assert runtime.import_selfcheck_main(
        ["Ortho4XP", "--import-selfcheck", "json"]) == 1
    assert "elevation provider registry: FAIL no directory" in (
        capsys.readouterr().out)
    os.mkdir(os.path.join(str(tmp_path), "Elevation"))
    assert runtime.import_selfcheck_main(
        ["Ortho4XP", "--import-selfcheck", "json"]) == 1
    assert "FAIL 0 of 0 files" in capsys.readouterr().out
