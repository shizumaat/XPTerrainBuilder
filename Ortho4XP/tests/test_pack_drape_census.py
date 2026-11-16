"""TWIN for ``tools/pack_drape_census.py`` (#2115): it reads the tiles of
a pack's cached dumps and diffs two runs; the witness itself is the
engine's (``tests/auto_patch_v2/test_pack_drapes.py``)."""
from __future__ import annotations

import importlib.util
import os

_TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "tools", "pack_drape_census.py")


def _load():
    spec = importlib.util.spec_from_file_location("pack_drape_census", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_tiles_of_a_pack_cache(tmp_path):
    for name in ("+39-105.dsf.3c52346a.text", "+39-105.dsf.anchor_bak.89f.text",
                 "+40-106.dsf.text", "o4_dsf_object_positions_+39-105.cache"):
        (tmp_path / name).write_text("", encoding="utf-8", newline="\n")
    assert _load()._tiles(str(tmp_path)) == {(39, -105), (40, -106)}


def test_the_diff_names_new_decal_witnesses(capsys):
    before = {"P|+39-105": {"witness": 0, "hidden": 0, "decal_named": []}}
    after = {"P|+39-105": {"witness": 2, "hidden": 2,
                           "decal_named": ["o/skid1.pol"]}}
    _load().diff(before, after)
    out = capsys.readouterr().out
    assert "+ decal-named witness: o/skid1.pol" in out
    assert "witness 0→2, offered 0→2, decal-named witness 0→1" in out
