"""#2200: the Pack choices… ask reads the selected tile's packs once and
holds the reading (``auto_patch.overlap_memo``): a second ask on an
unchanged tile opens no pack file; a pack changed on disk is read again;
an answer's own DSF rewrite keeps the reading.  Synthetic packs, no
X-Plane, no DSFTool."""
from __future__ import annotations

import builtins
import os

import pytest
from auto_patch_v2.airport import pack_choice as PC
from auto_patch_v2.airport import pack_overlap as PO

TILE = (25, 55)
_APT = ("I\n1100 Version\n\n1 10 0 0 {} Field\n100 45 1 0 0.25 0 2 1 "
        "09 25.25 55.36 0 0 2 0 0 0 27 25.25 55.37 0 0 2 0 0 0\n99\n")


def _dsf(scenery, name, tile=TILE):
    la, lo = tile
    block = f"{(la // 10) * 10:+03d}{(lo // 10) * 10:+04d}"
    return os.path.join(scenery, name, "Earth nav data", block, f"{la:+03d}{lo:+04d}.dsf")


def _pack(scenery, name, tile=TILE, apt=""):
    path = _dsf(scenery, name, tile)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"XPLNEDSF" + name.encode())
    if apt:
        with open(os.path.join(scenery, name, "Earth nav data", "apt.dat"), "w",
                  encoding="utf-8", newline="") as fh:
            fh.write(_APT.format(apt))


@pytest.fixture
def ask(tmp_path, monkeypatch):
    """``overlap_choice("ask")`` on a folder of 40 packs, two on the tile
    (an airport pack and an autogen pack found overlapping); returns
    ``(scenery, run)`` where ``run()`` is ``(rows, pack files opened,
    times the tile was read)``."""
    import O4_DSF_Header as DH
    from auto_patch import overlap_stage as OS
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    monkeypatch.setattr(OS.UI, "vprint", lambda *a, **k: None)
    monkeypatch.setattr(OS.UI, "pack_overlaps", lambda **k: None)
    monkeypatch.setattr(OS, "_context", lambda root: {})
    monkeypatch.setattr(OS, "_structures", lambda *a: [])
    monkeypatch.setattr(OS, "_grown", lambda pair, *a: pair)
    monkeypatch.setattr(DH, "dsf_is_overlay", lambda p: True)
    monkeypatch.setattr(PO, "airport_regions", lambda apt: [(None, None)])
    monkeypatch.setattr(PO, "overlaps", lambda by_pack: [
        PO.OverlapPair(("Airport", "Autogen"),
                       ((PO.HideRow("a.obj", 55.1, 25.1),),
                        (PO.HideRow("b.fac", 55.2, 25.2),)), 1, 1.0)])
    xroot = tmp_path / "X-Plane"
    scenery = str(xroot / "Custom Scenery")
    _pack(scenery, "Airport", apt="ABCD")
    _pack(scenery, "Autogen")
    for i in range(38):
        _pack(scenery, f"Elsewhere {i:02d}", tile=(40, 10 + i), apt=f"E{i:03d}" if i % 3 == 0 else "")
    reads = {"n": 0}
    real_pairs = OS._pairs

    def counted(*a, **k):
        reads["n"] += 1
        return real_pairs(*a, **k)
    monkeypatch.setattr(OS, "_pairs", counted)

    def run():
        opened = []
        real_open = builtins.open

        def spy(file, *a, **k):
            p = os.path.abspath(os.fspath(file)) if isinstance(file, (str, os.PathLike)) else ""
            if p.startswith(scenery + os.sep) and os.sep in p[len(scenery) + 1:]:
                opened.append(p)                    # a file INSIDE a pack
            return real_open(file, *a, **k)
        monkeypatch.setattr(builtins, "open", spy)
        try:
            out = OS.overlap_choice(str(xroot), "ask", (), *TILE)
        finally:
            monkeypatch.setattr(builtins, "open", real_open)
        n, reads["n"] = reads["n"], 0
        return out["items"], opened, n
    return scenery, run


def test_a_second_ask_on_an_unchanged_tile_opens_no_pack_file(ask):
    _scenery, run = ask
    rows, opened, n = run()
    assert n == 1 and opened and [r["packs"] for r in rows] == [["Airport", "Autogen"]]
    rows2, opened2, n2 = run()
    assert (n2, opened2) == (0, []) and rows2 == rows


def test_the_ask_shows_the_answer_stored_since(ask):
    from auto_patch_v2.airport import pack_overlap_choice as OVC
    _scenery, run = ask
    rows, _o, _n = run()
    OVC.STORE.remember(rows[0]["key"], "Airport")
    rows2, opened, n = run()
    assert (n, opened) == (0, []) and rows2[0]["winner"] == "Airport"


def test_a_pack_changed_on_disk_or_a_pack_installed_reads_the_tile_again(ask):
    scenery, run = ask
    run()
    with open(_dsf(scenery, "Autogen"), "ab") as fh:
        fh.write(b"updated in place")
    assert run()[2] == 1
    assert run()[2] == 0
    _pack(scenery, "New City")
    assert run()[2] == 1


def test_a_tile_link_this_app_installs_keeps_the_reading(ask):
    scenery, run = ask
    run()
    os.makedirs(os.path.join(scenery, "zOrtho4XP_+25+055"))
    assert run()[2] == 0


def test_apply_rewrites_only_the_answered_pack_and_keeps_the_reading(ask, monkeypatch):
    from auto_patch import overlap_stage as OS
    scenery, run = ask
    rows, _o, _n = run()
    written = []

    def rewrite(s, name, la, lo):
        written.append(name)
        with open(_dsf(s, name), "ab") as fh:       # our own write moves the stat
            fh.write(b"hidden rows")
        return name
    monkeypatch.setattr(OS, "_rewrite", rewrite)
    out = OS._answer(scenery, "choose", [{"key": rows[0]["key"], "winner": "Airport"}])
    assert out["state"] == "chosen" and written == ["Autogen"]
    assert run()[2] == 0


def test_the_folder_index_is_read_once_per_folder_state(tmp_path, monkeypatch):
    import O4_Custom_Scenery as CS
    scenery = str(tmp_path / "Custom Scenery")
    _pack(scenery, "A")
    _pack(scenery, "B", tile=(1, 1))
    calls = []
    real = CS._read_tile_packs
    monkeypatch.setattr(CS, "_read_tile_packs", lambda *a: calls.append(a) or real(*a))
    assert CS.tile_pack_names(scenery, *TILE) == ("A",)
    assert CS.tile_pack_names(scenery, *TILE) == ("A",) and len(calls) == 1
    os.makedirs(os.path.join(scenery, "zOrtho4XP_+25+055"))      # ours: no change
    assert CS.tile_pack_names(scenery, *TILE) == ("A",) and len(calls) == 1
    _pack(scenery, "C")
    assert CS.tile_pack_names(scenery, *TILE) == ("A", "C") and len(calls) == 2
