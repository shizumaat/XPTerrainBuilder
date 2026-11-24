"""#1229 / #2179: the build log says at verbosity 0, once per airport, how
a custom patch is used -- as made (with the higher-resolution warning,
RULINGS 2026-11-23f) or kept while our auto patch builds the airport --
even when no auto patch file exists beside it."""
import types

import O4_File_Names as FNAMES
import O4_Vector_Map as VMAP
import pytest


class _Stop(Exception):
    pass


def _include(tmp_path, monkeypatch, names):
    for name in names:
        (tmp_path / name).write_text("<osm version='0.6'></osm>\n",
                                     encoding="utf-8", newline="")
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(tmp_path))

    def stop():
        raise _Stop

    monkeypatch.setattr(VMAP.OSM, "OSM_layer", stop)
    tile = types.SimpleNamespace(lat=40, lon=-4, auto_patch="ICAO",
                                 auto_patch_selection=())
    with pytest.raises(_Stop):
        VMAP.include_patches(None, tile)


def test_custom_patch_alone_is_announced(tmp_path, monkeypatch, capsys):
    _include(tmp_path, monkeypatch, ["ZZZZ.patch.osm"])
    out = capsys.readouterr().out
    assert "ZZZZ: custom patch ZZZZ.patch.osm used as made" in out
    assert "requires our auto patch" in out


def test_custom_patch_beside_auto_is_announced_once(tmp_path, monkeypatch,
                                                    capsys):
    _include(tmp_path, monkeypatch, ["ZZZZ.patch.osm", "ZZZZ_auto.patch.osm"])
    assert capsys.readouterr().out.count("custom patch ZZZZ.patch.osm") == 1


def test_our_auto_patch_is_announced_and_the_file_not_read(
        tmp_path, monkeypatch, capsys):
    import O4_Custom_Patch_Use as USE

    USE.set_use(str(tmp_path), "ZZZZ", USE.AUTO_PATCH)
    _include(tmp_path, monkeypatch, ["ZZZZ.patch.osm", "ZZZZ_auto.patch.osm"])
    out = capsys.readouterr().out
    assert ("ZZZZ: our auto patch is used; your custom patch ZZZZ.patch.osm "
            "is kept, not applied.") in out
    assert "Patching ZZZZ.patch.osm" not in out
    assert "used as made" not in out


def test_auto_patch_alone_is_not_announced(tmp_path, monkeypatch, capsys):
    _include(tmp_path, monkeypatch, ["ZZZZ_auto.patch.osm"])
    assert "custom patch" not in capsys.readouterr().out


def _edited(tmp_path, monkeypatch, made, running):
    (tmp_path / "ZZZZ_edited.patch.osm").write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        f"<osm version='0.6' o4_edited_from_engine='{made}' "
        "o4_user_edited='1'>\n</osm>\n", encoding="utf-8", newline="")
    import auto_patch.provenance as PROV
    monkeypatch.setattr(PROV, "engine_version", lambda: running)
    _include(tmp_path, monkeypatch, [])


def test_edited_patch_older_than_engine_is_named(tmp_path, monkeypatch,
                                                 capsys):
    """#1637: an edited patch made by an older engine says so — it does
    not carry the fixes since."""
    _edited(tmp_path, monkeypatch, "1.50.1874", "1.50.1901")
    out = capsys.readouterr().out
    assert "(user-edited)" in out
    assert "made by engine 1.50.1874, older than this engine 1.50.1901" in out


@pytest.mark.parametrize("running", ["1.50.1874", "1.50.900", "absent"])
def test_edited_patch_not_older_is_not_named(tmp_path, monkeypatch, capsys,
                                             running):
    _edited(tmp_path, monkeypatch, "1.50.1874", running)
    out = capsys.readouterr().out
    assert "(user-edited)" in out and "made by engine" not in out
