"""#1246: a split DSFTool cannot place never fails the whole pack write.

A stand-in DSFTool copies bytes but, like the real ``--text2dsf``,
refuses the file with ``ERROR: could not place object LON, LAT`` when a
row lies outside the tile.  Synthetic ``tmp_path`` packs only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import split_guard as SG
from auto_patch_v2.model import placement as PM

DUMP = ("PROPERTY sim/west 51\nPROPERTY sim/east 52\n"
        "PROPERTY sim/south 25\nPROPERTY sim/north 26\n"
        "OBJECT_DEF objects/a.obj\nOBJECT_DEF objects/b.obj\n"
        "OBJECT_MSL 0 51.5 25.5 10.0 0.0\n"
        "OBJECT_MSL 1 51.9 25.2 12.0 45.0\n")

#: refuses the first object row whose lon is past 51.95 (a test-only
#: "tile edge" inside the box, so the retry path is exercised too)
_TOOL = ("import shutil, sys\n"
         "if sys.argv[1] == '--text2dsf':\n"
         "    for r in open(sys.argv[2]):\n"
         "        t = r.split()\n"
         "        if t and t[0].startswith('OBJECT') and t[0] != 'OBJECT_DEF'"
         " and float(t[2]) > {edge}:\n"
         "            print('ERROR: could not place object %s, %s'"
         " % (t[2], t[3]), file=sys.stderr); sys.exit(1)\n"
         "shutil.copyfile(sys.argv[2], sys.argv[3])\n")


@pytest.fixture
def pack(tmp_path):
    B.invalidate_memo()
    root = tmp_path / "Pack"
    for rel in ("objects/a.obj", "objects/b.obj"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8", newline="")
    dsf = root / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_text(DUMP, encoding="utf-8", newline="")
    yield root, dsf
    B.invalidate_memo()


def _tool(tmp_path, monkeypatch, edge: float) -> str:
    tool = tmp_path / "dsftool.py"
    tool.write_text(_TOOL.format(edge=edge), encoding="utf-8", newline="")
    real = W.subprocess.run
    monkeypatch.setattr(W.subprocess, "run", lambda a, **kw: real(
        [sys.executable, str(tool)] + list(a[1:]), **kw))
    return str(tool)


def _plan(root: Path, dsf: Path, lons) -> PM.PlacementPlan:
    split = PM.Split(PM.PlacementRef(1, "objects/b.obj", 51.9, 25.2, 45.0),
                     tuple(PM.Body(f"b{k}", "other", (k,),
                                   PM.Anchor(lon, 25.2, 45.0), "test",
                                   f"objects/b__b{k}.obj")
                           for k, lon in enumerate(lons)))
    conv = PM.Conversion(0, "objects/a.obj", 51.5, 25.5, 0.0, PM.KIND_MSL, 10.0)
    return PM.PlacementPlan("TEST", root.name, str(root), str(dsf),
                            str(dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}),
                            conversions=(conv,), splits=(split,))


def test_tile_box_and_refused_point():
    assert SG.tile_box(DUMP) == (51.0, 25.0, 52.0, 26.0)
    assert SG.tile_box("PROPERTY sim/west 51\n") is None
    assert SG.refused_point("x ERROR: could not place object -96.997196, "
                            "32.891771") == (-96.997196, 32.891771)
    assert SG.refused_point("DSFTool crashed") is None


@pytest.mark.parametrize("lons,edge", [((51.9, 52.1), 99.0),   # off the tile
                                       ((51.9, 51.97), 51.95)])  # refused
def test_an_unplaceable_split_is_written_whole(pack, tmp_path, monkeypatch,
                                               lons, edge):
    root, dsf = pack
    for k in range(len(lons)):
        (root / f"objects/b__b{k}.obj").write_text(PM.CUT_MARK + "\n", encoding="utf-8",
                                                    newline="")
    res = W.write_pack(str(root), _plan(root, dsf, lons),
                       _tool(tmp_path, monkeypatch, edge),
                       work_dir=str(tmp_path / "w"),
                       body_files=[str(root / f"objects/b__b{k}.obj")
                                   for k in range(len(lons))])
    live = dsf.read_text(encoding="utf-8")
    assert "OBJECT 0 51.5 25.5 0.0" in live, "the rest of the pack is written"
    assert "OBJECT_MSL 1 51.9 25.2 12.0 45.0" in live, "written whole"
    assert "b__b" not in live
    assert [s.placement.index for s in res.plan.splits] == []
    assert [k.index for k in res.plan.kept] == [1]
    assert any("TEST" in n and "objects/b.obj" in n for n in res.notes)
    assert not (root / "objects/b__b0.obj").exists(), "orphan body removed"
