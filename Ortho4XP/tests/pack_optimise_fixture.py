"""The synthetic pack the "Optimise pack" twins (#1707) write: a tile DSF
whose text IS the file (a byte-copy DSFTool), two pack objects with
duplicate placements, one flat forest.  Shared by
``tests/test_pack_optimise.py`` and ``tests/test_pack_optimise_write.py``."""
from __future__ import annotations

import sys
import types

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.model import placement as PM

DUMP = ("PROPERTY sim/west 51\n"
        "PROPERTY sim/east 52\n"
        "PROPERTY sim/south 25\n"
        "PROPERTY sim/north 26\n"
        "OBJECT_DEF objects/car.obj\n"
        "OBJECT_DEF objects/van.obj\n"
        "POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\n"
        "OBJECT 0 51.500000000 25.500000000 90.000000\n"        # 0
        "OBJECT 0 51.500001000 25.500000000 90.500000\n"        # 1: 0.10 m, 0.5°
        "OBJECT 0 51.500003000 25.500000000 90.000000\n"        # 2: 0.30 m
        "OBJECT_AGL 1 51.600000000 25.600000000 2.000000 10.000000\n"  # 3
        "OBJECT_AGL 1 51.600000000 25.600000000 2.000000 10.000000\n"  # 4: exact
        "OBJECT_AGL 1 51.600000000 25.600000000 3.000000 10.000000\n"  # 5: higher
        "BEGIN_POLYGON 0 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.0 25.0\nEND_WINDING\n"
        "END_POLYGON\n")
RENAMES = {"lib/g8/terrain/wet_hot_flat.for": "lib/g8/broad_vhot_wet.for"}
OBJ = "I\n800\nOBJ\n\nTEXTURE car.png\nPOINT_COUNTS 4 0 0 {idx}\nVT 0 0 0 0 1 0 0 0\n"


def make_pack(tmp_path, monkeypatch):
    """The pack, with DSFTool replaced by a byte copy."""
    import O4_UI_Utils as UI
    from auto_patch import dsf_reader as DSFR
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n",
                    encoding="utf-8", newline="")
    real_run = W.subprocess.run
    monkeypatch.setattr(W.subprocess, "run", lambda args, **kw: real_run(
        [sys.executable, str(tool)] + list(args[1:]), **kw))
    monkeypatch.setattr(DSFR, "_dsftool_path", lambda: str(tool))
    monkeypatch.setattr(DSFR, "ensure_dsf_text_path", lambda *a, **k: None)
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    B.invalidate_memo()
    pack = tmp_path / "Custom Scenery" / "Some Pack"
    dsf = pack / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(DUMP.encode("utf-8"))
    (pack / "objects").mkdir()
    (pack / "objects" / "car.obj").write_text(OBJ.format(idx=3000), encoding="utf-8",
                                              newline="")
    (pack / "objects" / "van.obj").write_text(OBJ.format(idx=600), encoding="utf-8",
                                              newline="")
    return types.SimpleNamespace(pack=pack, dsf=dsf, tool=str(tool))


def plan(rp, icao="", **kw):
    return PM.PlacementPlan(icao, rp.pack.name, str(rp.pack), str(rp.dsf),
                            str(rp.dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}), **kw)


def write(rp, icao="", **kw):
    """``write_pack`` of an airport plan (``conversions=`` etc. in ``kw``
    go to the plan, ``forests=`` / ``optimise=`` to the write)."""
    choice = {k: kw.pop(k) for k in ("forests", "optimise", "drop") if k in kw}
    return W.write_pack(str(rp.pack), plan(rp, icao, **kw), rp.tool,
                        allow_live_install=True, **choice)


def rows(rp) -> list[str]:
    return [ln for ln in rp.dsf.read_text(encoding="utf-8").splitlines()
            if ln.startswith("OBJECT ") or ln.startswith("OBJECT_AGL ")]


def entry(rp) -> dict:
    return B.dsf_entry(B.read_record(str(rp.dsf)), rp.dsf.name)
