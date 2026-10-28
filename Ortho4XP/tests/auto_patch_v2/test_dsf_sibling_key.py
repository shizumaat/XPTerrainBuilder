"""#1584: a #25 sibling record names its pristine dump by a key that the
printed ``HEIGHTS`` row does not move (``dsf_dump_key``).

DSFTool's ``--dsf2text`` prints that row from memory it over-reads
(``dsf_heights``), so two dumps of one DSF can differ in it alone.  Keyed
on the printed text, a multi-airport DSF (TNCM + TFFG) read its
sibling's edits as stale and dropped them.  Rows recorded before the key
existed are re-keyed, never silently dropped."""
from __future__ import annotations

import json
import sys

import pytest

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_dump_key as K
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import placement_write as PW
from tests.auto_patch_v2.test_backup_state import (
    DUMP4, _objs, _pack, _record_doc, _tffg, _tncm)


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _redumping_dsftool(tmp_path, monkeypatch):
    """``--dsf2text`` prints a DIFFERENT ``HEIGHTS`` row on every call
    (DSFTool's over-read); ``--text2dsf`` is a byte copy."""
    tool = tmp_path / "dsftool.py"
    count = tmp_path / "dumps"
    tool.write_text(
        "import pathlib, shutil, sys\n"
        f"c = pathlib.Path({str(count)!r})\n"
        "n = int(c.read_text()) + 1 if c.exists() else 0\n"
        "if sys.argv[1] == '--dsf2text':\n"
        "    c.write_text(str(n))\n"
        "    body = ''.join(l for l in pathlib.Path(sys.argv[2]).read_text()\n"
        "                   .splitlines(True) if not l.startswith('HEIGHTS'))\n"
        "    pathlib.Path(sys.argv[3]).write_text(\n"
        "        f'HEIGHTS 1.00000 -{n}.0  # max encodeable 1.0\\n' + body)\n"
        "else:\n"
        "    shutil.copyfile(sys.argv[2], sys.argv[3])\n",
        encoding="utf-8", newline="")
    real_run = W.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    return str(tool)


def _write(dsf, doc) -> None:
    (dsf.parent / "o4_placement_provenance.json").write_text(
        json.dumps(doc), encoding="utf-8", newline="")
    B.invalidate_memo()


def test_two_dumps_differing_only_in_the_heights_row_share_one_key():
    a = "HEIGHTS 1.00000 -1.0  # max encodeable 65534.0\n" + DUMP4
    b = "HEIGHTS 1.00000 0.0  # max encodeable 65535.0\r\n" + DUMP4
    assert K.printed_sha(a) != K.printed_sha(b)
    assert K.dump_key(a) == K.dump_key(b) == K.dump_key(DUMP4)
    assert K.dump_key(DUMP4.replace("OBJECT_MSL 3", "OBJECT_MSL 2")) != K.dump_key(a)


def test_a_siblings_edits_survive_a_redump(tmp_path, monkeypatch):
    """RED ON BASE: TFFG's dump printed another HEIGHTS row than TNCM's,
    so TNCM's row (keyed on the printed text) read as stale."""
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name="+18-064.dsf")
    tool = _redumping_dsftool(tmp_path, monkeypatch)
    patch = str(tmp_path / "patch")
    p1, f1 = _tncm(pack, dsf)
    PW.apply_plan(p1, f1, tool, patch_dir=patch, work_dir=str(tmp_path / "w1"))
    first = _record_doc(dsf)["dsfs"]["+18-064.dsf"]["airports"]["TNCM"]
    p2, f2 = _tffg(pack, dsf)
    second = PW.apply_plan(p2, f2, tool, patch_dir=patch,
                           work_dir=str(tmp_path / "w2"))
    assert second.dsf.composed_airports == ("TNCM",)
    assert _objs(pack) == ["b__b0.obj", "b__b1.obj", "d__b0.obj"]
    rows = _record_doc(dsf)["dsfs"]["+18-064.dsf"]["airports"]
    assert rows["TFFG"]["dump_sha256"] != first["dump_sha256"], \
        "the two dumps printed different HEIGHTS rows"
    assert rows["TFFG"][K.KEY_FIELD] == rows["TNCM"][K.KEY_FIELD] \
        == K.dump_key(DUMP4)


def test_an_old_keyed_record_is_migrated_not_dropped(tmp_path, monkeypatch):
    """A row from before the key (printed hash only, from a dump whose
    HEIGHTS row this dump does not repeat) against the SAME backup is
    re-applied and re-keyed."""
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name="+18-064.dsf")
    tool = _redumping_dsftool(tmp_path, monkeypatch)
    patch = str(tmp_path / "patch")
    p1, f1 = _tncm(pack, dsf)
    PW.apply_plan(p1, f1, tool, patch_dir=patch, work_dir=str(tmp_path / "w1"))
    doc = _record_doc(dsf)
    entry = doc["dsfs"]["+18-064.dsf"]
    row = entry["airports"]["TNCM"]
    del row[K.KEY_FIELD]
    row["dump_sha256"] = entry["dump_sha256"] = "a" * 64
    _write(dsf, doc)
    p2, f2 = _tffg(pack, dsf)
    second = PW.apply_plan(p2, f2, tool, patch_dir=patch,
                           work_dir=str(tmp_path / "w2"))
    assert second.dsf.composed_airports == ("TNCM",)
    assert _objs(pack) == ["b__b0.obj", "b__b1.obj", "d__b0.obj"]
    tncm = _record_doc(dsf)["dsfs"]["+18-064.dsf"]["airports"]["TNCM"]
    assert tncm[K.KEY_FIELD] == K.dump_key(DUMP4)


def test_an_old_keyed_record_of_another_backup_is_dropped_with_a_note(
        tmp_path, monkeypatch):
    pack, dsf = _pack(tmp_path, dsf_text=DUMP4, name="+18-064.dsf")
    tool = _redumping_dsftool(tmp_path, monkeypatch)
    patch = str(tmp_path / "patch")
    p1, f1 = _tncm(pack, dsf)
    PW.apply_plan(p1, f1, tool, patch_dir=patch, work_dir=str(tmp_path / "w1"))
    doc = _record_doc(dsf)
    entry = doc["dsfs"]["+18-064.dsf"]
    del entry["airports"]["TNCM"][K.KEY_FIELD]
    entry["airports"]["TNCM"]["dump_sha256"] = "a" * 64
    _write(dsf, doc)
    p2, f2 = _tffg(pack, dsf)
    second = PW.apply_plan(p2, f2, tool, patch_dir=patch,
                           work_dir=str(tmp_path / "w2"))
    assert second.dsf.composed_airports == ()
    assert any(n.startswith("TNCM: its recorded edits") for n in second.dsf.notes)
