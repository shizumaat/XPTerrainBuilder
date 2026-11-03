"""#1799: a #25 sibling record names its pristine dump by CONTENT, so a
renamed, moved or copied pack keeps every recorded airport's seating.

DSFTool's ``--dsf2text`` opens with ``# file: <absolute path>``.  The
#1584 key kept that line, so after the pack folder moved the next
choice-only rewrite (3D trees, optimise, omission, Undo outside a build
— a plan with no ICAO) read every recorded airport as "built against
another version of this DSF" and dropped its seats.  Rows keyed before
the fix are migrated on read, never forced to a rebuild."""
from __future__ import annotations

import json
import shutil
import sys

import pytest
from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_dump_key as K
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.model.placement import BACKUP_SUFFIX, PlacementPlan, Provenance
from tests.auto_patch_v2.test_backup_state import DUMP4, _objs, _pack, _record_doc, _tffg, _tncm

DSF = "+18-064.dsf"


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _path_naming_dsftool(tmp_path, monkeypatch):
    """``--dsf2text`` heads the text with ``# file: <input path>`` as
    DSFTool does; ``--text2dsf`` is a byte copy."""
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import os, pathlib, sys\n"
        "src, out = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])\n"
        "body = [l for l in src.read_text().splitlines(True)\n"
        "        if not l.startswith('# file:')]\n"
        "if sys.argv[1] == '--dsf2text':\n"
        "    body = [f'# file: {os.path.abspath(src)}\\n'] + body\n"
        "out.write_text(''.join(body))\n",
        encoding="utf-8", newline="")
    real_run = W.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    return str(tool)


def _two_airports(tmp_path, monkeypatch):
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name=DSF)
    tool = _path_naming_dsftool(tmp_path, monkeypatch)
    patch = str(tmp_path / "patch")
    for n, (plan, cuts) in enumerate((_tncm(pack, dsf), _tffg(pack, dsf))):
        PW.apply_plan(plan, cuts, tool, patch_dir=patch,
                      work_dir=str(tmp_path / f"w{n}"))
    return pack, tool


def _moved(tmp_path, pack, how: str):
    new = tmp_path / "renamed pack"
    (shutil.copytree if how == "copy" else shutil.move)(str(pack), str(new))
    B.invalidate_memo()
    return new, new / "Earth nav data" / "+40-010" / DSF


def _choice_only_rewrite(pack, dsf, tool, tmp_path):
    """What ``forest_stage._write`` / Undo do: a plan with no ICAO."""
    plan = PlacementPlan("", pack.name, str(pack), str(dsf),
                         str(dsf) + BACKUP_SUFFIX, Provenance("", "t", "", {}))
    return W.write_pack(str(pack), plan, tool, allow_live_install=True,
                        work_dir=str(tmp_path / "choice"))


def _seated(dsf) -> set[str]:
    return set(_record_doc(dsf)["dsfs"][DSF]["airports"])


@pytest.mark.parametrize("how", ["rename", "copy"])
def test_a_moved_pack_keeps_every_airports_seats(tmp_path, monkeypatch, how):
    """RED ON BASE: the dump of the moved pack names another path."""
    pack, tool = _two_airports(tmp_path, monkeypatch)
    new, dsf = _moved(tmp_path, pack, how)
    res = _choice_only_rewrite(new, dsf, tool, tmp_path)
    assert res.composed_airports == ("TFFG", "TNCM")
    assert not any("built against another version" in n for n in res.notes)
    assert _seated(dsf) == {"TFFG", "TNCM"}
    assert _objs(new) == ["b__b0.obj", "b__b1.obj", "d__b0.obj"]
    text = dsf.read_text(encoding="utf-8")
    assert "objects/b__b0.obj" in text and "objects/d__b0.obj" in text


def test_a_pre_1799_record_of_a_moved_pack_is_migrated(tmp_path, monkeypatch):
    """Rows keyed with the path in the key (and no entry key) against the
    SAME backup are re-applied after the move and re-keyed by content."""
    pack, tool = _two_airports(tmp_path, monkeypatch)
    dsf = pack / "Earth nav data" / "+40-010" / DSF
    old_text = f"# file: {dsf}{BACKUP_SUFFIX}\n" + DUMP4
    doc = _record_doc(dsf)
    entry = doc["dsfs"][DSF]
    del entry[K.KEY_FIELD]
    for row in entry["airports"].values():
        row[K.KEY_FIELD] = K.path_dump_key(old_text)
    (dsf.parent / "o4_placement_provenance.json").write_text(
        json.dumps(doc), encoding="utf-8", newline="")
    new, dsf = _moved(tmp_path, pack, "rename")
    res = _choice_only_rewrite(new, dsf, tool, tmp_path)
    assert res.composed_airports == ("TFFG", "TNCM")
    rows = _record_doc(dsf)["dsfs"][DSF]
    assert rows[K.KEY_FIELD] == K.dump_key(DUMP4)
    assert {r[K.KEY_FIELD] for r in rows["airports"].values()} \
        == {K.dump_key(DUMP4)}


def test_a_pre_1799_row_of_another_dump_is_still_dropped(tmp_path, monkeypatch):
    """The migration reads the row's key against its entry's: a row that
    disagrees with the write that kept it is not re-applied."""
    pack, tool = _two_airports(tmp_path, monkeypatch)
    dsf = pack / "Earth nav data" / "+40-010" / DSF
    doc = _record_doc(dsf)
    entry = doc["dsfs"][DSF]
    del entry[K.KEY_FIELD]
    entry["airports"]["TNCM"][K.KEY_FIELD] = "1" * 64
    entry["airports"]["TFFG"][K.KEY_FIELD] = "2" * 64
    (dsf.parent / "o4_placement_provenance.json").write_text(
        json.dumps(doc), encoding="utf-8", newline="")
    new, dsf = _moved(tmp_path, pack, "rename")
    res = _choice_only_rewrite(new, dsf, tool, tmp_path)
    assert res.composed_airports == ()
    assert _seated(dsf) == set()


def test_the_key_ignores_the_file_comment_and_heights_row():
    a = "# file: /a/pack/x.dsf\nHEIGHTS 1.0 -1.0\n" + DUMP4
    b = "# file: /b/other pack/x.dsf.anchor_bak\r\n" + DUMP4
    assert K.dump_key(a) == K.dump_key(b) == K.dump_key(DUMP4)
    assert K.path_dump_key(a) != K.path_dump_key(b)
