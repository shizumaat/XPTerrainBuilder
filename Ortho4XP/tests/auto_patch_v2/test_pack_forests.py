"""OLD FLAT FORESTS (issue #1360): the check, the map, the rename and the
write that carries it.

Every pack and every X-Plane install here is a synthetic ``tmp_path``
fake; DSFTool is a byte-copy stand-in (the real encoder has its own twin
in ``test_v2dsfagl``).  No network, no corpus, no X-Plane.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import pack_forests as PF
from auto_patch_v2.airport import unpatched_pack as UP
from auto_patch_v2.airport.pack_forests_map import FOREST_MAP
from auto_patch_v2.model import placement as PM

FLAT = "A\n800\nFOREST\nTEXTURE trees.png\nTREE 0 0 64 64 32 50 8 12 2 0 oak\n"
SOLID = ("A\n1000\nFOREST\nTEXTURE trees.dds\nSHADER_3D\n"
         "TREE 0 0 64 64 32 50 8 12 2 0 oak\nMESH 0 3 3\n")

#: polygon 0 a flat library forest the map names, 1 a 3D one, 2 the pack's
#: own flat forest, 3 a flat library forest the map leaves out, 4 a
#: draped polygon, 5 a virtual path no library provides
DUMP = ("PROPERTY sim/west 51\n"
        "OBJECT_DEF objects/a.obj\n"
        "POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\n"
        "POLYGON_DEF lib/g8/broad_vhot_wet.for\n"
        "POLYGON_DEF forests/local.for\n"
        "POLYGON_DEF lib/g8/terrain/dry_hot_flat.for\n"
        "POLYGON_DEF draped/ok.pol\n"
        "POLYGON_DEF lib/g8/broad_cld_dry.for\n"
        "OBJECT 0 51.1 25.1 90.0\n"
        "BEGIN_POLYGON 0 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.0 25.0\nEND_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 0 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.1 25.0\nEND_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 2 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.2 25.0\nEND_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 3 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.3 25.0\nEND_WINDING\n"
        "END_POLYGON\n"
        "BEGIN_POLYGON 4 65535 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT 51.4 25.0\nEND_WINDING\n"
        "END_POLYGON\n")


def _write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _install(tmp_path: Path, target_kind: str = SOLID):
    """A fake X-Plane root with a pack in Custom Scenery; returns
    ``(pack, dsf, index, default_scenery)``."""
    xp = tmp_path / "X-Plane 12"
    ds = xp / "Resources" / "default scenery"
    tropical = _write(ds / "900 forests" / "tropical.for", FLAT)
    palms = _write(ds / "900 forests" / "palms.for", FLAT)
    solid = _write(ds / "1200 forests" / "sum" / "broad_vhot.for", target_kind)
    index = {"lib/g8/terrain/wet_hot_flat.for": str(tropical),
             "lib/g8/terrain/dry_hot_flat.for": str(palms),
             "lib/g8/broad_vhot_wet.for": str(solid)}
    pack = xp / "Custom Scenery" / "Some Pack"
    _write(pack / "objects" / "a.obj")
    _write(pack / "draped" / "ok.pol")
    _write(pack / "forests" / "local.for", FLAT)
    dsf = _write(pack / "Earth nav data" / "+20+050" / "+25+051.dsf", DUMP)
    return pack, dsf, index, str(ds)


def _old(pack, index, ds, also=None):
    return PF.old_forests(str(pack), DUMP.splitlines(True), index, ds, also)


# ── THE KIND OF A .for ──────────────────────────────────────────────────

@pytest.mark.parametrize("text,kind", [
    (FLAT, "flat"),
    (SOLID, "3d"),                     # a 3D file may carry TREE lines too
    ("A\n800\nFOREST\nMESH 0 3 3\n", "3d"),
    ("A\n800\nFOREST\nTEXTURE t.png\n", None),
])
def test_the_kind_is_any_3d_line_else_any_tree(tmp_path, text, kind):
    assert PF.for_kind(str(_write(tmp_path / "f.for", text))) == kind


def test_an_unreadable_for_is_no_kind(tmp_path):
    assert PF.for_kind(str(tmp_path / "absent.for")) is None


# ── THE CHECK AND THE MAP ───────────────────────────────────────────────

def test_the_check_names_every_flat_forest_with_its_target(tmp_path):
    pack, _dsf, index, ds = _install(tmp_path)
    got = _old(pack, index, ds)
    assert got == (
        PF.OldForest(0, "lib/g8/terrain/wet_hot_flat.for", 2,
                     "lib/g8/broad_vhot_wet.for", False),
        PF.OldForest(2, "forests/local.for", 1, "", True),
        PF.OldForest(3, "lib/g8/terrain/dry_hot_flat.for", 1, "", False),
    ), "3D, draped and unresolved definitions are not judged"
    assert PF.renames_of(got) == {
        "lib/g8/terrain/wet_hot_flat.for": "lib/g8/broad_vhot_wet.for"}


def test_without_an_index_nothing_is_said(tmp_path):
    pack, _dsf, _index, ds = _install(tmp_path)
    assert _old(pack, None, ds) is None


def test_a_target_that_is_flat_here_is_unmapped(tmp_path):
    """An X-Plane 11 install exports the same virtual path to a flat file:
    nothing is offered."""
    pack, _dsf, index, ds = _install(tmp_path, target_kind=FLAT)
    assert PF.renames_of(_old(pack, index, ds)) == {}


def test_a_target_only_a_seasonal_export_provides_is_mapped(tmp_path):
    pack, _dsf, index, ds = _install(tmp_path)
    del index["lib/g8/broad_vhot_wet.for"]
    assert PF.renames_of(_old(pack, index, ds)) == {}
    asked = []

    def also():
        asked.append(1)
        return frozenset({"lib/g8/broad_vhot_wet.for"})

    assert PF.renames_of(_old(pack, index, ds, also)) == {
        "lib/g8/terrain/wet_hot_flat.for": "lib/g8/broad_vhot_wet.for"}
    assert asked, "asked only for a target the index lacks"


def test_no_forest_is_nothing(tmp_path):
    pack, _dsf, index, ds = _install(tmp_path)
    rows = ["POLYGON_DEF draped/ok.pol\n", "BEGIN_POLYGON 0 65535 2\n"]
    assert PF.old_forests(str(pack), rows, index, ds) == ()


def test_the_key_is_the_file_under_default_scenery(tmp_path):
    ds = tmp_path / "Resources" / "default scenery"
    assert PF.forest_key(str(ds / "900 forests" / "tropical.for"),
                         str(ds)) == "900 forests/tropical.for"
    assert PF.forest_key(str(tmp_path / "pack" / "x.for"), str(ds)) == ""


def test_the_summary_and_log_line(tmp_path):
    pack, _dsf, index, ds = _install(tmp_path)
    old = _old(pack, index, ds)
    assert PF.summary(old) == {
        "total": 3, "mapped": 1, "uses": 2,
        "first_paths": ["lib/g8/terrain/wet_hot_flat.for"], "unmapped": 2,
        "first_unmapped": ["forests/local.for",
                           "lib/g8/terrain/dry_hot_flat.for"]}
    line = PF.log_line("Some Pack", old)
    assert line.startswith("[pack] Some Pack: 3 old flat (X-Plane 11) forest")
    assert "first: forests/local.for" in line


# ── THE MAP IS DATA, CITED (docs/findings/xp12-forest-exports-20261027.md)

def _listing() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "docs" / "findings" \
        / "xp12-forest-exports-20261027.md"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 9 and cells[1].startswith("EXPORT"):
            rows.append(dict(zip(("library", "directive", "season", "region",
                                  "virtual", "file", "kind"), cells[:7],
                                 strict=True)))
    return rows


def test_every_key_is_a_flat_file_and_every_target_only_3d():
    rows = _listing()
    assert len(rows) > 1000
    flat_files = {f"{r['library']}/{r['file']}" for r in rows
                  if r["kind"] == "flat"}
    kinds: dict[str, set] = {}
    for r in rows:
        kinds.setdefault(r["virtual"], set()).add(r["kind"])
    for key, target in FOREST_MAP.items():
        assert key in flat_files, key
        assert kinds.get(target) == {"3D"}, (key, target, kinds.get(target))


def test_the_map_names_no_airport():
    for key, target in FOREST_MAP.items():
        assert re.match(r"^(900 forests|1000 autogen)/", key), key
        assert target.startswith("lib/"), target


# ── THE RENAME ──────────────────────────────────────────────────────────

def test_the_rename_changes_only_the_named_definitions():
    renames = {"lib/g8/terrain/wet_hot_flat.for": "lib/g8/broad_vhot_wet.for"}
    out, n = PF.rename_definitions(DUMP, renames)
    assert n == 1
    before, after = DUMP.splitlines(True), out.splitlines(True)
    assert len(before) == len(after)
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert changed == [("POLYGON_DEF lib/g8/terrain/wet_hot_flat.for\n",
                        "POLYGON_DEF lib/g8/broad_vhot_wet.for\n")]
    assert PF.rename_definitions(DUMP, {}) == (DUMP, 0)


def test_the_record_reads_back_only_for_its_pristine_file():
    renames = {"a.for": "lib/b.for"}
    entry = {PF.RECORD_KEY: PF.record("aa", renames, 1, "t")}
    assert PF.recorded(entry, "aa") == renames
    assert PF.recorded(entry, "bb") == {}
    assert PF.recorded({}, "aa") == {}
    entry[PF.RECORD_KEY]["renames"][0]["target"] = "lib/c.for"
    assert PF.recorded(entry, "aa") == {}, "a row that no longer reads as written"
    assert PF.decision_key("aa", renames) != PF.decision_key("aa", {})


# ── THE WRITE (dsf_write.write_pack(..., forests=)) ─────────────────────

@pytest.fixture
def _memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _stand_in_dsftool(tmp_path, monkeypatch):
    """``--dsf2text`` / ``--text2dsf`` as a byte copy."""
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n",
                    encoding="utf-8", newline="")
    real_run = W.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    return str(tool)


def _plan(pack: Path, dsf: Path, icao: str = "") -> PM.PlacementPlan:
    return PM.PlacementPlan(icao, pack.name, str(pack), str(dsf),
                            str(dsf) + PM.BACKUP_SUFFIX,
                            PM.Provenance("", "1.0.test", "", {}))


def _live(dsf: Path) -> str:
    return "".join(r for r in dsf.read_text(encoding="utf-8")
                   .splitlines(True) if not r.startswith("PROPERTY o4/"))


def _entry(dsf: Path) -> dict:
    doc = json.loads((dsf.parent / PM.PROVENANCE_FILENAME)
                     .read_text(encoding="utf-8"))
    return doc["dsfs"][dsf.name]


RENAMES = {"lib/g8/terrain/wet_hot_flat.for": "lib/g8/broad_vhot_wet.for"}


def test_the_write_renames_records_and_keeps_the_pristine(tmp_path, monkeypatch,
                                                         _memo):
    pack, dsf, _index, _ds = _install(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf), tool, allow_live_install=True,
                 work_dir=str(tmp_path / "w"), forests=RENAMES)
    assert _live(dsf) == PF.rename_definitions(DUMP, RENAMES)[0]
    bak = Path(str(dsf) + PM.BACKUP_SUFFIX)
    assert bak.read_text(encoding="utf-8") == DUMP, "the pristine, untouched"
    row = _entry(dsf)[PF.RECORD_KEY]
    assert row["renamed"] == 1 and row["renames"] == [
        {"path": "lib/g8/terrain/wet_hot_flat.for",
         "target": "lib/g8/broad_vhot_wet.for"}]
    assert PF.recorded(_entry(dsf), hashlib.sha256(
        bak.read_bytes()).hexdigest()) == RENAMES


def test_a_later_write_keeps_the_upgrade_and_undo_drops_it(tmp_path,
                                                          monkeypatch, _memo):
    pack, dsf, _index, _ds = _install(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf), tool, allow_live_install=True,
                 work_dir=str(tmp_path / "w1"), forests=RENAMES)
    # a placement write that knows nothing of forests
    W.write_pack(str(pack), _plan(pack, dsf), tool, allow_live_install=True,
                 work_dir=str(tmp_path / "w2"))
    assert _live(dsf) == PF.rename_definitions(DUMP, RENAMES)[0]
    assert _entry(dsf)[PF.RECORD_KEY]["renamed"] == 1
    W.write_pack(str(pack), _plan(pack, dsf), tool, allow_live_install=True,
                 work_dir=str(tmp_path / "w3"), forests={})
    assert _live(dsf) == DUMP
    assert _entry(dsf)[PF.RECORD_KEY] is None


def test_an_unpatched_restore_keeps_the_upgrade(tmp_path, monkeypatch, _memo):
    """An airport left without a patch gets its seating undone, never the
    user's 3D trees: no bare copy while an upgrade is recorded."""
    pack, dsf, _index, _ds = _install(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf, "OTST"), tool, allow_live_install=True,
                 work_dir=str(tmp_path / "w1"), forests=RENAMES)
    out = UP.restore_airport(str(pack), str(dsf), "OTST", tool,
                             allow_live_install=True,
                             work_dir=str(tmp_path / "w2"))
    assert out.state == UP.RESTORED
    assert _live(dsf) == PF.rename_definitions(DUMP, RENAMES)[0]
    assert "OTST" not in (_entry(dsf).get("airports") or {})
    assert os.path.isfile(str(dsf) + PM.BACKUP_SUFFIX)
