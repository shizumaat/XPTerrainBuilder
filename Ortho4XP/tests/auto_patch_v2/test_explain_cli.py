"""``auto_patch_v2 explain`` CLI twins (RULINGS 2026-09-13cs chip, scout
``v2heca329``): the default patch is the one the DATA-ROOT RESOLUTION
lands a tile build's product at — never silently the engine tree's
days-stale ``Patches/`` clone — the resolved path and its mtime are
printed on every run, and ``--shape`` parses before or after the ICAO.

No network, no DEM, no X-Plane install: the parser and the resolver are
exercised on ``tmp_path`` roots; the classification is not run.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import auto_patch_v2.pipeline.__main__ as M  # noqa: E402

REL = Path("Patches") / "+30+030" / "+30+031" / "HECA_auto.patch.osm"


@pytest.mark.parametrize("argv", [
    ["explain", "--shape", "5", "HECA"],
    ["explain", "HECA", "--shape", "5"],
    ["explain", "HECA", "--patch", "p.osm", "--shape", "5"],
    ["explain", "--shape", "5", "--patch", "p.osm", "HECA"],
])
def test_shape_parses_in_either_position(argv):
    """The chip said ``--shape`` was accepted only before the ICAO; the
    parser takes it on either side of the positional (and after
    ``--patch``), and the twin pins that it stays so."""
    a = M.build_parser().parse_args(argv)
    assert a.cmd == "explain" and a.icao == "HECA" and a.shape == 5
    assert a.patch == ("p.osm" if "--patch" in argv else None)


def _roots(tmp_path, monkeypatch, *, engine_has=False, default_has=False,
           env_root=None, env_has=False):
    """Three fake roots — engine tree, default data root, an explicit
    ORTHO4XP_DATA_ROOT — each optionally holding the HECA patch."""
    import O4_File_Names as FNAMES
    engine = tmp_path / "engine"
    default = tmp_path / "XPTerrainBuilderData"
    env = tmp_path / "chosen"
    for d in (engine, default, env):
        d.mkdir()
    monkeypatch.setattr(M, "ENGINE_DIR", engine)
    monkeypatch.setattr(FNAMES, "default_data_root", lambda: str(default))
    monkeypatch.chdir(engine)           # a source checkout: cwd IS the root
    if env_root:
        monkeypatch.setenv("ORTHO4XP_DATA_ROOT", str(env))
    else:
        monkeypatch.delenv("ORTHO4XP_DATA_ROOT", raising=False)
    for d, has in ((engine, engine_has), (default, default_has), (env, env_has)):
        if has:
            (d / REL).parent.mkdir(parents=True)
            (d / REL).write_text("<osm/>")
    return engine, default, env


def test_default_patch_is_the_data_roots_not_the_engine_trees(tmp_path, monkeypatch):
    """The defect: the engine tree's clone (Sep 9) was THE default while
    the product the sim ran (Sep 13) sat under the data root."""
    engine, default, _ = _roots(tmp_path, monkeypatch, engine_has=True,
                                default_has=True)
    path, source, exists = M.resolve_default_patch("HECA", 30, 31)
    assert exists and Path(path) == default / REL
    assert "default data root" in source


def test_engine_tree_is_the_last_resort(tmp_path, monkeypatch):
    engine, default, _ = _roots(tmp_path, monkeypatch, engine_has=True)
    path, source, exists = M.resolve_default_patch("HECA", 30, 31)
    assert exists and Path(path) == engine / REL and source == "the engine tree"
    cands = M.default_patch_candidates("HECA", 30, 31)
    assert [Path(p) for _s, p in cands] == [default / REL, engine / REL]


def test_a_chosen_data_root_is_the_more_specific_instruction(tmp_path, monkeypatch):
    """``ORTHO4XP_DATA_ROOT`` (what the app hands every engine process)
    outranks the default root, as the accessor's own rule says."""
    _, default, env = _roots(tmp_path, monkeypatch, default_has=True,
                             env_root=True, env_has=True)
    path, source, exists = M.resolve_default_patch("HECA", 30, 31)
    assert exists and Path(path) == env / REL and "ORTHO4XP_DATA_ROOT" in source


def test_an_explicit_data_root_is_the_only_candidate(tmp_path, monkeypatch):
    _roots(tmp_path, monkeypatch, engine_has=True, default_has=True)
    other = tmp_path / "other"
    cands = M.default_patch_candidates("HECA", 30, 31, data_root=str(other))
    assert cands == [("--data-root", str(other / REL))]
    path, source, exists = M.resolve_default_patch("HECA", 30, 31, str(other))
    assert not exists and source == "--data-root"


def test_the_provenance_line_names_path_source_and_mtime(tmp_path, monkeypatch):
    """Printed on EVERY run: the path, where it came from, its mtime."""
    _, default, _ = _roots(tmp_path, monkeypatch, default_has=True)
    path, source, _ = M.resolve_default_patch("HECA", 30, 31)
    os.utime(path, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    line = M.patch_provenance_line(path, source)
    assert path in line and source in line
    assert "modified 20" in line and "days ago" in line
    missing = M.patch_provenance_line(str(tmp_path / "nope.osm"), "--patch")
    assert "DOES NOT EXIST" in missing


def test_the_tile_spelling_is_the_tile_builds_own():
    """One spelling of ``Patches/<block>/<tile>/`` — ``O4_File_Names``'s."""
    assert M._patch_rel("heca", 30, 31) == str(REL)
    assert M._patch_rel("LEMD", 40, -4) == str(
        Path("Patches") / "+40-010" / "+40-004" / "LEMD_auto.patch.osm")
