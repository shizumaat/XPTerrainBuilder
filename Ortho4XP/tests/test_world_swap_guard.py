"""#2247: a World tile goes into the pack only whole.

A drape's DSF names a ``.pol`` per texture square (and a ``_water.pol``
per masked one); X-Plane cancels the whole DSF when one is missing.
``O4_World_Pack.swap_in`` refuses a tile whose staged or placed copy
lacks a file its DSF names, leaving the pack's previous DSF; a build
worker child never runs the app engine's World sweep (the owner's
+35-112: a worker's sweep and the parent's swap raced on one tile and
139 of 341 ``.pol`` never reached the pack).  Synthetic drapes, no
DSFTool."""
from __future__ import annotations

import os
import shutil
import sys

import O4_DSF_Binary as DSFB
import O4_World_Pack as WP
import pytest

LAT, LON, TILE = 35, -112, "+35-112"


def _drape_dsf(pols: list) -> bytes:
    """A DSF whose only definitions are ``pols`` (POLY table)."""
    head = DSFB._atom("HEAD", DSFB._atom("PROP", DSFB._prop_bytes([
        ("sim/overlay", "1"),
        ("sim/creation_agent", "XPTerrainBuilder world drape")])))
    defn = DSFB._atom("DEFN", b"".join(
        DSFB._atom(t, DSFB._table(pols) if t == "POLY" else b"")
        for t in DSFB.DEFN_TABLES))
    return DSFB._dsf_file([head, defn])


def _staged_drape(root: str, squares: int = 6) -> list:
    """A staged drape of ``squares`` squares, each a plain and a water
    ``.pol`` and one DDS; the pack-relative ``.pol`` names."""
    ter = os.path.join(root, "terrain", TILE)
    tex = os.path.join(root, "textures", TILE)
    os.makedirs(ter)
    os.makedirs(tex)
    refs = []
    for i in range(squares):
        for pol in (f"{i}_X16.pol", f"{i}_X16_water.pol"):
            with open(os.path.join(ter, pol), "w", encoding="utf-8",
                      newline="\n") as h:
                h.write(f"TEXTURE_NOWRAP ../../textures/{TILE}/{i}_X16.dds\n")
            refs.append(f"terrain/{TILE}/{pol}")
        with open(os.path.join(tex, f"{i}_X16.dds"), "wb") as h:
            h.write(b"DDS ")
    dsf = os.path.join(root, WP.dsf_relpath(LAT, LON))
    os.makedirs(os.path.dirname(dsf))
    with open(dsf, "wb") as h:
        h.write(_drape_dsf(refs))
    return refs


def _pack_with_placeholder(pack: str) -> str:
    WP.write_placeholder(pack, LAT, LON)
    return os.path.join(pack, WP.dsf_relpath(LAT, LON))


def test_missing_defs_names_a_drapes_absent_pols(tmp_path):
    staged = str(tmp_path / "staged")
    refs = _staged_drape(staged)
    assert WP._missing_defs(staged, LAT, LON) == []
    os.remove(os.path.join(staged, refs[3]))
    assert WP._missing_defs(staged, LAT, LON) == [refs[3]]
    # verify_tile (the publish and leftover check) reads POLY too now
    assert any(refs[3] in p for p in WP.verify_tile(staged, LAT, LON)["problems"])


def test_a_whole_drape_swaps_in(tmp_path):
    pack, staged = str(tmp_path / "pack"), str(tmp_path / "staged")
    refs = _staged_drape(staged)
    dsf = _pack_with_placeholder(pack)
    WP.swap_in(pack, staged, LAT, LON)
    assert not WP.is_placeholder(dsf)
    assert all(os.path.isfile(os.path.join(pack, r)) for r in refs)


def test_a_short_staged_drape_is_refused_and_the_pack_kept(tmp_path):
    pack, staged = str(tmp_path / "pack"), str(tmp_path / "staged")
    refs = _staged_drape(staged)
    os.remove(os.path.join(staged, refs[0]))
    dsf = _pack_with_placeholder(pack)
    with pytest.raises(WP.IncompleteTile) as caught:
        WP.swap_in(pack, staged, LAT, LON)
    assert caught.value.where == "staged" and caught.value.missing == [refs[0]]
    assert WP.is_placeholder(dsf)
    assert not os.path.exists(os.path.join(pack, "terrain", TILE))
    with pytest.raises(WP.IncompleteTile):  # a merge refuses it too
        WP.swap_in(pack, staged, LAT, LON, merge=True)
    assert WP.is_placeholder(dsf)


def test_a_copy_cut_short_keeps_the_previous_tile(tmp_path, monkeypatch):
    """Another writer removing files from the incoming folder mid-copy
    (the #2247 race) leaves the previous folder and DSF in place."""
    pack, staged = str(tmp_path / "pack"), str(tmp_path / "staged")
    refs = _staged_drape(staged)
    WP.swap_in(pack, staged, LAT, LON)                 # a whole earlier drape
    dsf = os.path.join(pack, WP.dsf_relpath(LAT, LON))
    with open(dsf, "rb") as h:
        before = h.read()
    real = shutil.copytree

    def cut(src, dst, **kw):
        out = real(src, dst, **kw)
        if os.path.basename(src) == TILE and "terrain" in src:
            os.remove(os.path.join(dst, os.path.basename(refs[1])))
        return out
    monkeypatch.setattr(WP.shutil, "copytree", cut)
    with pytest.raises(WP.IncompleteTile) as caught:
        WP.swap_in(pack, staged, LAT, LON)
    assert caught.value.where == "pack"
    with open(dsf, "rb") as h:
        assert h.read() == before
    assert all(os.path.isfile(os.path.join(pack, r)) for r in refs)
    assert not os.path.exists(os.path.join(pack, "terrain", f".{TILE}.incoming"))


def test_swap_staged_records_a_refusal_and_drops_the_short_tile(tmp_path):
    pack, root = str(tmp_path / "pack"), str(tmp_path / "staging")
    staged = os.path.join(root, TILE)
    refs = _staged_drape(staged)
    os.remove(os.path.join(staged, refs[-1]))
    dsf = _pack_with_placeholder(pack)
    refused: list = []
    assert WP.swap_staged(pack, root, refused=refused) == []
    assert [e.tile for e in refused] == [TILE] and WP.is_placeholder(dsf)
    assert not os.path.exists(staged)      # never goes in: made again


def test_a_build_worker_runs_no_app_watch(monkeypatch):
    from o4_engine import jsonl
    monkeypatch.setattr(sys, "argv", ["engine", "--engine-jsonl"])
    assert not jsonl._is_build_worker()
    monkeypatch.setattr(sys, "argv",
                        ["engine", "--engine-jsonl", "--engine-worker"])
    assert jsonl._is_build_worker()


def test_a_drape_is_staged_only_once_it_verifies(tmp_path, monkeypatch):
    """``world_job_run._stage_verified``: the drape is written in a hidden
    folder no sweep reads and renamed in whole once it verifies; a drape
    that does not verify never appears staged."""
    import O4_World_Drape as DRAPE
    from o4_engine import world_job_run as RUN
    root = str(tmp_path / "staging")
    staged = os.path.join(root, TILE)
    work = RUN._work_dir(staged)
    assert os.path.basename(work).startswith(".")
    _staged_drape(work)
    monkeypatch.setattr(DRAPE, "verify_drape",
                        lambda r, la, lo, t: {"problems": ["short"]})
    assert RUN._stage_verified(work, staged, (LAT, LON), "tool") is False
    assert not os.path.exists(staged) and not os.path.exists(work)
    _staged_drape(work)
    monkeypatch.setattr(DRAPE, "verify_drape",
                        lambda r, la, lo, t: {"problems": []})
    assert RUN._stage_verified(work, staged, (LAT, LON), "tool") is True
    assert os.path.isfile(os.path.join(staged, WP.dsf_relpath(LAT, LON)))
    assert not os.path.exists(work)
