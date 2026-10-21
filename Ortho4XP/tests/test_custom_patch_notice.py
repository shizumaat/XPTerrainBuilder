"""#1229: a custom patch is always honoured, and the build log says so at
verbosity 0 even when no auto patch file exists beside it (before, the only
trace of a custom patch replacing the auto patch was printed when an old
``<ICAO>_auto.patch.osm`` also sat in the folder)."""
import types

import pytest

import O4_File_Names as FNAMES
import O4_Vector_Map as VMAP


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
    assert "ZZZZ: using the CUSTOM patch ZZZZ.patch.osm" in out
    assert "not auto-patched" in out


def test_custom_patch_beside_auto_is_announced_once(tmp_path, monkeypatch,
                                                    capsys):
    _include(tmp_path, monkeypatch, ["ZZZZ.patch.osm", "ZZZZ_auto.patch.osm"])
    assert capsys.readouterr().out.count("using the CUSTOM patch") == 1


def test_auto_patch_alone_is_not_announced(tmp_path, monkeypatch, capsys):
    _include(tmp_path, monkeypatch, ["ZZZZ_auto.patch.osm"])
    assert "CUSTOM patch" not in capsys.readouterr().out
