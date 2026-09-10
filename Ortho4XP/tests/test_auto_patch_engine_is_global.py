"""``auto_patch_engine`` is a GLOBAL setting (RULINGS 2026-09-10c): a
per-tile cfg value that disagrees with the global ``Ortho4XP.cfg`` is
ignored, loudly.  Precedent: the owner's −13-077 / −13-078 tile cfgs
carried a stale ``auto_patch_engine=v1`` and SPJC / SPLP shipped on the
retired engine in app 1.0.300 while the global said v2."""
from __future__ import annotations

import types

import pytest

import O4_Config_Utils as CFG
from auto_patch import engine_v2 as E


def _global(tmp_path, monkeypatch, text):
    p = tmp_path / "Ortho4XP.cfg"
    p.write_text(text)
    monkeypatch.setattr(CFG, "global_cfg_file", str(p))
    return p


def test_tile_value_yields_to_the_global_file(tmp_path, monkeypatch, capsys):
    _global(tmp_path, monkeypatch, "auto_patch=ICAO\nauto_patch_engine=v2\n")
    tile = types.SimpleNamespace(auto_patch_engine="v1")
    assert E.resolved_auto_patch_engine(tile) == "v2"
    out = capsys.readouterr().out
    assert "IGNORED" in out and "global Ortho4XP.cfg" in out


def test_tile_value_stands_when_the_global_file_has_no_key(tmp_path, monkeypatch):
    _global(tmp_path, monkeypatch, "auto_patch=ICAO\n")
    tile = types.SimpleNamespace(auto_patch_engine="v1")
    assert E.resolved_auto_patch_engine(tile) == "v1"


def test_agreeing_values_are_silent(tmp_path, monkeypatch, capsys):
    _global(tmp_path, monkeypatch, "auto_patch_engine=v2\n")
    tile = types.SimpleNamespace(auto_patch_engine="v2")
    assert E.resolved_auto_patch_engine(tile) == "v2"
    assert "IGNORED" not in capsys.readouterr().out


def test_unregistered_value_still_refuses(tmp_path, monkeypatch):
    _global(tmp_path, monkeypatch, "auto_patch_engine=v2\n")
    with pytest.raises(ValueError):
        E.resolved_auto_patch_engine(types.SimpleNamespace(auto_patch_engine="v3"))
