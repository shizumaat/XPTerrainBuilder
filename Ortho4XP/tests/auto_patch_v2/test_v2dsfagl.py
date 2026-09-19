"""THE DSF WRITE HALF (spec ``object-placement-spec.md`` §2, §3, §5):
the pure text edit, the backup/idempotence discipline, and ONE REAL
round trip through DSFTool on a COPY of a shipped pack.

The synthetic twins pin the edit; the real round trip pins what
"identical" MEANS — the encoder requantises every coordinate and
reorders whole classes of row, so a byte diff is noise 25,656 lines
deep (``dsf_write``'s module docstring carries the measurement).

A lane NEVER writes ``/Users/noah/X-Plane 12``: every write here lands
in ``tmp_path``, and ``write_pack`` refuses a live install without an
explicit opt-in (twin below)."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.model.placement import (Anchor, Body, Conversion, Kept,
                                           PlacementPlan, PlacementRef,
                                           Provenance, Split)

# ── a synthetic dump ────────────────────────────────────────────────────

DUMP = """A
800 written by DSFTool 2.4.0-b1
DSF2TEXT

# file: /nowhere/+39-095.dsf
# pool  0: p=3 s=  551  0.03125 -94.75000  0.03125 39.28125
PROPERTY sim/west -95
PROPERTY sim/overlay 1
OBJECT_DEF objects/tower.obj
OBJECT_DEF lib/cars/car_static_invar.obj
OBJECT_DEF objects/hangar.obj
POLYGON_DEF pavement/asphalt.pol
OBJECT 1 -94.715004864 39.296891928 194.027008
OBJECT_MSL 0 -94.719717041 39.294637407 303.799313344 352.787366
OBJECT_AGL 2 -94.716857881 39.298726825 24.999816892 102.026093
OBJECT_MSL 1 -94.720003624 39.295011730 303.799313344 262.494850
BEGIN_POLYGON 0 65535 4
BEGIN_WINDING
POLYGON_POINT -94.7 39.2 0.0 0.0
POLYGON_POINT -94.6 39.2 1.0 0.0
POLYGON_POINT -94.6 39.3 1.0 1.0
END_WINDING
END_POLYGON
"""


def _plan(tmp_path: Path, **kw) -> PlacementPlan:
    d = dict(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
             dsf_path=str(tmp_path / "t.dsf"),
             dsf_backup_path=str(tmp_path / "t.dsf.anchor_bak"),
             provenance=Provenance("sha", "1.0", "digest"))
    d.update(kw)
    return PlacementPlan(**d)


def test_placement_ordinals_are_read_dump_order(tmp_path):
    """The plan's ``index`` IS ``read_dump``'s placement ordinal — the
    two must count the same rows or every edit lands on the wrong one."""
    p = tmp_path / "d.text"
    p.write_text(DUMP)
    dump = D.read_dump(p.name and str(p))
    rows = W.placement_rows(DUMP.splitlines(keepends=True))
    assert len(rows) == len(dump.placements)
    for (o, _i, toks), pl in zip(rows, dump.placements):
        assert toks[0] == pl.kind
        assert dump.object_defs[int(toks[1])] == pl.def_path
        assert o == rows.index((o, _i, toks))


def test_msl_and_agl_convert_and_every_other_line_is_byte_identical(tmp_path):
    plan = _plan(tmp_path, conversions=(
        Conversion(1, "objects/tower.obj", -94.719717041, 39.294637407,
                   352.787366, "OBJECT_MSL", 303.799313344),
        Conversion(2, "objects/hangar.obj", -94.716857881, 39.298726825,
                   102.026093, "OBJECT_AGL", 24.999816892),
    ), kept=(Kept(3, "lib/cars/car_static_invar.obj", "stock library resource"),))
    out = W.edit_dump(DUMP, plan, "1.0.352")
    a, b = DUMP.splitlines(), out.splitlines()
    # §12a: ONE row is added — the in-band ownership mark, after the last
    # PROPERTY.  Everything else is still line-for-line the authored dump.
    assert len(b) == len(a) + 1
    mark = b.index("PROPERTY o4/placement_rewrite 1.0.352")
    assert b[mark - 1].startswith("PROPERTY ")
    assert not b[mark + 1].startswith("PROPERTY ")
    del b[mark]
    changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert len(changed) == 2
    assert b[changed[0]] == "OBJECT 0 -94.719717041 39.294637407 352.787366"
    assert b[changed[1]] == "OBJECT 2 -94.716857881 39.298726825 102.026093"
    # the stock MSL row (index 3) is untouched, coordinates spelled as authored
    assert "OBJECT_MSL 1 -94.720003624 39.295011730 303.799313344 262.494850" in b


def test_split_appends_defs_without_renumbering(tmp_path):
    bodies = tuple(Body(f"b{k}", "building", (k,), Anchor(-94.71 - k / 1000, 39.29, 12.5),
                        "pad point", f"objects/hangar__b{k}.obj", (1.0, 2.0, 3.0))
                   for k in range(3))
    plan = _plan(tmp_path, splits=(
        Split(PlacementRef(2, "objects/hangar.obj", -94.716857881, 39.298726825,
                           102.026093), bodies),))
    out = W.edit_dump(DUMP, plan).splitlines()
    defs = [ln for ln in out if ln.startswith("OBJECT_DEF")]
    assert defs[:3] == ["OBJECT_DEF objects/tower.obj",
                        "OBJECT_DEF lib/cars/car_static_invar.obj",
                        "OBJECT_DEF objects/hangar.obj"]
    assert defs[3:] == [f"OBJECT_DEF objects/hangar__b{k}.obj" for k in range(3)]
    # the split row became three OBJECT rows on the NEW def indices 3, 4, 5
    rows = [ln for ln in out if ln.startswith("OBJECT ")]
    assert [ln.split()[1] for ln in rows[-3:]] == ["3", "4", "5"]
    assert "OBJECT_AGL" not in "\n".join(out)
    # ...and every remaining row is as authored
    assert "OBJECT 1 -94.715004864 39.296891928 194.027008" in out


def test_edit_refuses_a_stale_plan(tmp_path):
    with pytest.raises(ValueError, match="does not have"):
        W.edit_dump(DUMP, _plan(tmp_path, conversions=(
            Conversion(99, "x", 0, 0, 0, "OBJECT_MSL", 1.0),)))
    with pytest.raises(ValueError, match="dump row is"):
        W.edit_dump(DUMP, _plan(tmp_path, conversions=(
            Conversion(0, "objects/tower.obj", 0, 0, 0, "OBJECT_MSL", 1.0),)))
    with pytest.raises(ValueError, match="dump resource"):
        W.edit_dump(DUMP, _plan(tmp_path, conversions=(
            Conversion(1, "objects/WRONG.obj", 0, 0, 0, "OBJECT_MSL", 1.0),)))
    with pytest.raises(ValueError, match="both converted and split"):
        W.edit_dump(DUMP, _plan(
            tmp_path,
            conversions=(Conversion(1, "objects/tower.obj", 0, 0, 0,
                                    "OBJECT_MSL", 1.0),),
            splits=(Split(PlacementRef(1, "objects/tower.obj", 0, 0, 0),
                          (Body("b", "other", (0,), Anchor(0, 0, 0), "r",
                                "objects/t__b0.obj"),)),)))


def test_conversions_for_dump_converts_stock_too(tmp_path):
    """§5 as RE-SCOPED by owner RULINGS 2026-09-11d: a ``lib/…`` placement
    converts like a pack resource (a placement edit modifies no object);
    a plain ``OBJECT`` row is listed by neither."""
    p = tmp_path / "d.text"
    p.write_text(DUMP)
    (tmp_path / "objects").mkdir()
    for n in ("tower.obj", "hangar.obj"):
        (tmp_path / "objects" / n).write_text("I\n800\nOBJ\n")
    conv, kept = W.conversions_for_dump(D.read_dump(str(p)), str(tmp_path))
    assert [c.index for c in conv] == [1, 2, 3]
    assert [c.kind_before for c in conv] == ["OBJECT_MSL", "OBJECT_AGL", "OBJECT_MSL"]
    assert kept == []


def test_live_install_is_refused(tmp_path):
    assert W.live_install_roots("/Users/noah/X-Plane 12/Custom Scenery/x/a.dsf")
    assert not W.live_install_roots(str(tmp_path))


# ── the real round trip (a COPY of a shipped pack) ──────────────────────

PACKS = [
    ("KMCI", "KMCI Kansas City (Taimodels)", "+30-100/+39-095.dsf"),
    ("KBNA", "US-KBNA Nashville Airport", "+30-090/+36-087.dsf"),
]
XP = "/Users/noah/X-Plane 12/Custom Scenery"


def _first_pack():
    for icao, pack, rel in PACKS:
        src = os.path.join(XP, pack, "Earth nav data", rel)
        if os.path.isfile(src):
            return icao, os.path.join(XP, pack), src
    return None


@pytest.mark.skipif(_first_pack() is None or _dsftool_path() is None,
                    reason="no shipped pack / no DSFTool on this machine")
def test_real_pack_roundtrip_and_idempotent_write(tmp_path):
    icao, real_pack, src = _first_pack()
    pack = tmp_path / "pack"
    (pack / "Earth nav data" / "blk").mkdir(parents=True)
    dsf = pack / "Earth nav data" / "blk" / os.path.basename(src)
    shutil.copy2(src, dsf)

    tool = _dsftool_path()
    text = W.dump(str(dsf), str(tmp_path / "pristine.text"), tool)
    dump = D.read_dump(text)
    conv, kept = W.conversions_for_dump(dump, real_pack)
    assert conv, "the pack has convertible MSL/AGL placements"

    plan = PlacementPlan(icao=icao, pack_name="pack", pack_root=str(pack),
                         dsf_path=str(dsf),
                         dsf_backup_path=str(dsf) + ".anchor_bak",
                         provenance=Provenance("", "test", ""),
                         conversions=tuple(conv), kept=tuple(kept))
    res = W.write_pack(str(pack), plan, tool, work_dir=str(tmp_path / "w"))
    assert res.backup_created and os.path.isfile(res.backup_path)
    assert res.report.ok, res.report.findings
    assert res.report.max_deg <= W.TOL_DEG

    # The encoder REORDERS OBJECT rows, so an ordinal does not survive
    # the write: the invariant is per (resource, kind) COUNT.  Every
    # converted placement reads back as an on-ground OBJECT; the kept
    # (stock) rows keep their authored kind exactly.
    after = D.read_dump(W.dump(str(dsf), str(tmp_path / "after.text"), tool))
    assert len(after.placements) == len(dump.placements)

    def tally(placements):
        out: dict[tuple[str, str], int] = {}
        for pl in placements:
            k = (pl.def_path, pl.kind)
            out[k] = out.get(k, 0) + 1
        return out

    want = tally(dump.placements)
    for c in conv:
        want[(c.resource, c.kind_before)] -= 1
        want[(c.resource, "OBJECT")] = want.get((c.resource, "OBJECT"), 0) + 1
    want = {k: v for k, v in want.items() if v}
    assert tally(after.placements) == want
    assert all(pl.elevation is None for pl in after.placements
               if pl.kind == "OBJECT")
    assert sum(1 for pl in after.placements if pl.kind != "OBJECT") == len(kept)

    prov = json.loads(Path(res.provenance_path).read_text())
    assert prov["counts"]["conversions"] == len(conv)
    first = Path(dsf).read_bytes()
    backup_sha = prov["backup_sha256"]

    # IDEMPOTENCE: the rerun reads the BACKUP, not the edited DSF
    res2 = W.write_pack(str(pack), plan, tool, work_dir=str(tmp_path / "w2"))
    assert not res2.backup_created
    assert Path(dsf).read_bytes() == first
    assert json.loads(Path(res2.provenance_path).read_text())["backup_sha256"] \
        == backup_sha


@pytest.mark.skipif(_first_pack() is None, reason="no shipped pack")
def test_write_pack_refuses_the_live_install(tmp_path):
    icao, real_pack, src = _first_pack()
    plan = PlacementPlan(icao=icao, pack_name="p", pack_root=real_pack,
                         dsf_path=src, dsf_backup_path=src + ".anchor_bak",
                         provenance=Provenance("", "", ""))
    with pytest.raises(PermissionError, match="live X-Plane"):
        W.write_pack(real_pack, plan, _dsftool_path() or "/nonexistent")


# ── the tool's twin ─────────────────────────────────────────────────────

def test_dsf_placement_diff_tool_reports_the_same_edit(tmp_path, capsys):
    """``tools/dsf_placement_diff.py`` is a view of the writer, not a
    second implementation: its per-resource counts and its old -> new
    rows are ``edit_dump``'s."""
    import importlib.util
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "dsf_placement_diff", root / "tools" / "dsf_placement_diff.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dump_path = tmp_path / "d.text"
    dump_path.write_text(DUMP)
    (tmp_path / "objects").mkdir()
    for n in ("tower.obj", "hangar.obj"):
        (tmp_path / "objects" / n).write_text("I\n800\nOBJ\n")
    rc = mod.main(["--dump", str(dump_path), "--pack-root", str(tmp_path),
                   "--icao", "TEST", "--json"])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["counts"]["conversions"] == 3          # 11d: stock converts too
    assert rep["kept_by_reason"] == {}
    assert rep["per_resource"] == {"objects/tower.obj": 1,
                                   "objects/hangar.obj": 1,
                                   "lib/cars/car_static_invar.obj": 1}
    # §12a: the one added row is the ownership mark
    assert rep["lines_after"] == rep["lines_before"] + 1
    news = {c["index"]: c["new"] for c in rep["changes"]}
    assert news[1] == "OBJECT 0 -94.719717041 39.294637407 352.787366"
    assert news[2] == "OBJECT 2 -94.716857881 39.298726825 102.026093"
