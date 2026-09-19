"""IS THE BACKUP STILL THE PACK'S? — the §12a tables, row by row.

Every row id of the DSF table (D1-D8) and the object table (O1-O7)
appears in a test name, plus the partial states, the owner's Q2
copy-then-rebuild path, the superseded rename that never overwrites, the
per-DSF record, the dump-cache fallback, the disabled pack, and the one
REAL DSFTool round trip that pins the ownership mark.

THE MATERIALITY FLOOR HERE IS BYTES: any state in which a file the
engine cannot prove is its own loses bytes is a FAIL, never a residual.
Every pack is a ``tmp_path`` fake; the owner's X-Plane install is READ
in exactly one test (a ``copy2`` of one small pack DSF into ``tmp_path``)
and written never."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import pack as PK
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.model import placement as PM

DUMP = ("PROPERTY sim/west -4\n"
        "PROPERTY sim/overlay 1\n"
        "OBJECT_DEF objects/a.obj\n"
        "OBJECT_DEF objects/b.obj\n"
        "OBJECT_MSL 0 -3.5 40.5 601.0 12.5\n"
        "OBJECT 1 -3.6 40.6 90.0\n")


# ── scaffolding ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _pack(tmp_path, *, dsf_text: str = DUMP, name: str = "+40-004.dsf"):
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True, exist_ok=True)
    nav = pack / "Earth nav data" / "+40-010"
    nav.mkdir(parents=True, exist_ok=True)
    dsf = nav / name
    dsf.write_text(dsf_text)
    return pack, dsf


def _snapshot(root: Path) -> dict:
    """names -> (size, mtime_ns): what "the classifier wrote NOTHING"
    means."""
    out = {}
    for d, _sub, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            st = os.stat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return out


def _record(dsf: Path, entry: dict, *, version: int = 2,
            top: dict | None = None) -> None:
    doc = dict(top or {})
    doc["version"] = version
    if version == 2:
        doc["dsfs"] = {dsf.name: entry}
    else:
        doc["dsf"] = dsf.name
        doc.update(entry)
    (dsf.parent / "o4_placement_provenance.json").write_text(json.dumps(doc))


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _stand_in_dsftool(tmp_path, monkeypatch):
    """``--dsf2text`` / ``--text2dsf`` as a byte copy (the encoder has its
    own twin in ``test_v2dsfagl``)."""
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n")
    real_run = W.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    return str(tool)


def _plan(pack: Path, dsf: Path, **kw) -> PM.PlacementPlan:
    d = dict(icao="TEST", pack_name="pack", pack_root=str(pack),
             dsf_path=str(dsf), dsf_backup_path=str(dsf) + ".anchor_bak",
             provenance=PM.Provenance("", "1.0.352", ""),
             conversions=(PM.Conversion(0, "objects/a.obj", -3.5, 40.5, 12.5,
                                        "OBJECT_MSL", 601.0),))
    d.update(kw)
    return PM.PlacementPlan(**d)


# ── D1-D8: the DSF table, and the classifier writes NOTHING ─────────────

def test_D1_no_backup_is_the_pack_as_installed(tmp_path):
    pack, dsf = _pack(tmp_path)
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.NO_BACKUP and v.row == "D1"
    assert v.read_path == str(dsf) and v.may_write
    assert _snapshot(pack) == before


def test_D2_original_lost_stands_the_write_down(tmp_path):
    pack, dsf = _pack(tmp_path)
    # our own output (it carries the mark), and the backup is GONE
    dsf.write_text(DUMP + f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0.352\n")
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.ORIGINAL_LOST and v.row == "D2"
    assert v.witness == "mark"
    assert v.read_path == str(dsf) and not v.may_write
    assert _snapshot(pack) == before


def test_D3_pristine_reads_the_backup(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.PRISTINE and v.row == "D3"
    assert v.read_path == str(bak) and v.may_write and v.witness == "stat"
    assert _snapshot(pack) == before


def test_D4_ours_is_the_normal_path_and_costs_no_hash(tmp_path,
                                                      monkeypatch):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    dsf.write_text(DUMP + "OBJECT 1 -3.7 40.7 0.0\n")      # our rewrite
    st = os.stat(dsf)
    _record(dsf, {"written_sha256": _sha(dsf), "written_size": st.st_size,
                  "written_mtime_ns": st.st_mtime_ns})
    before = _snapshot(pack)

    opened: list = []
    real_open = open

    def counting_open(p, *a, **kw):
        opened.append(str(p))
        return real_open(p, *a, **kw)

    monkeypatch.setattr("builtins.open", counting_open)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.OURS and v.row == "D4"
    assert v.read_path == str(bak) and v.may_write and v.witness == "stat"
    # the record is read; NEITHER the DSF NOR the backup is opened
    assert str(dsf) not in opened and str(bak) not in opened
    assert _snapshot(pack) == before


def test_D5_replaced_reads_the_users_new_file(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    _record(dsf, {"written_sha256": "0" * 64, "backup_sha256": _sha(bak)})
    dsf.write_text(DUMP + "OBJECT 1 -9.9 40.9 0.0\n")      # THE USER'S
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.REPLACED and v.row == "D5"
    assert v.read_path == str(dsf) and v.may_write
    assert _snapshot(pack) == before


def test_D6_unproven_assumes_ours_and_keeps_a_copy_owner_Q2(tmp_path):
    """OWNER Q2 (RULINGS 2026-09-18l) overrides the spec default: the app
    does NOT stand down — it assumes the file is its own, keeps a stamped
    copy, and rebuilds from the old backup."""
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    dsf.write_text(DUMP + "OBJECT 1 -9.9 40.9 0.0\n")      # no record at all
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.UNPROVEN and v.row == "D6"
    assert v.read_path == str(bak), "it rebuilds from the old backup"
    assert v.may_write, "Q2: it keeps working"
    assert v.witness == ""
    assert _snapshot(pack) == before, "classifying still writes nothing"


def test_D7_live_missing_touches_nothing(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    dsf.unlink()
    before = _snapshot(pack)
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.LIVE_MISSING and v.row == "D7"
    assert not v.may_write
    assert not os.path.isfile(v.read_path), "every caller's isfile skips"
    assert _snapshot(pack) == before


def test_D8_unreadable_backup_stands_down(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    os.chmod(bak, 0o000)
    try:
        v = B.classify_dsf(str(dsf))
        assert v.state is B.State.UNPROVEN and v.row == "D8"
        assert v.read_path == str(dsf) and not v.may_write
    finally:
        os.chmod(bak, 0o644)


def test_D4_a_backup_that_left_its_record_is_still_built_from(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    dsf.write_text(DUMP + "OBJECT 1 -3.7 40.7 0.0\n")
    st = os.stat(dsf)
    _record(dsf, {"written_sha256": _sha(dsf), "written_size": st.st_size,
                  "written_mtime_ns": st.st_mtime_ns,
                  "backup_sha256": "f" * 64})
    assert B.classify_dsf(str(dsf)).state is B.State.OURS
    assert not B.backup_matches_record(str(dsf)), "a user act on the backup"


def test_a_path_that_is_already_a_backup_is_returned_unchanged(tmp_path):
    p = str(tmp_path / "x.dsf.anchor_bak")
    assert W.pristine_dsf_path(p) == p
    assert B.classify_dsf(p).read_path == p


# ── the ownership mark and the body-name witness ────────────────────────

def test_the_mark_is_found_by_a_raw_byte_scan(tmp_path):
    p = tmp_path / "m.dsf"
    p.write_bytes(b"\x00\x01binary" + B.OWNERSHIP_PROPERTY.encode() + b"\x02")
    assert B.carries_our_mark(str(p))
    q = tmp_path / "n.dsf"
    q.write_bytes(b"nothing of ours here")
    assert not B.carries_our_mark(str(q))


def test_the_body_name_witness_covers_marks_written_before_1_0_352(tmp_path):
    pack, dsf = _pack(tmp_path)
    dsf.write_text(DUMP + "OBJECT_DEF objects/b__b3.obj\n")
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.ORIGINAL_LOST and v.witness == "body-names"


# ── O1-O7: the object table ─────────────────────────────────────────────

def _obj(pack: Path, name: str, text: str) -> Path:
    p = pack / "objects" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


OBJ = "I\n800\nOBJ\nVT 1.0 0.0 2.0\nVT 3.0 0.0 4.0\n"


def test_O1_no_backup(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.NO_BACKUP and v.read_path == str(o)
    assert not v.may_write


def test_O2_pristine_on_two_stats_reads_no_file(tmp_path, monkeypatch):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    opened: list = []
    real_open = open
    monkeypatch.setattr("builtins.open",
                        lambda p, *a, **k: (opened.append(str(p)),
                                            real_open(p, *a, **k))[1])
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.PRISTINE and v.witness == "stat"
    assert v.read_path == str(bak) and not v.may_write
    assert str(o) not in opened and str(bak) not in opened


def test_O3_same_bytes_moved_mtime_syncs_then_is_O2(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    st = os.stat(bak)
    os.utime(o, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.PRISTINE and v.witness == "sha256" and v.may_write
    PW.restore_pack_objects(str(pack))
    assert o.read_text() == OBJ
    B.invalidate_memo()
    assert B.classify_object(str(o), str(pack)).witness == "stat"


def test_O4_ours_by_the_v1_sidecar_is_restored(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    o.write_text("I\n800\nOBJ\nVT 1.0 -7.0 2.0\nVT 3.0 -7.0 4.0\nX\n")
    (pack / ".o4_reanchor_provenance.json").write_text(json.dumps(
        {"objects": {"objects/a.obj": {"written_sha256": _sha(o)}}}))
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.OURS and v.witness == "sha256" and v.may_write
    res = PW.restore_pack_objects(str(pack))
    assert o.read_text() == OBJ and str(o) in res.restored
    assert os.stat(o).st_mtime_ns == os.stat(bak).st_mtime_ns   # O3 next time


def test_O5_y_only_witness_keeps_the_live_bytes_first(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    baked = "I\n800\nOBJ\nVT 1.0 -7.5 2.0\nVT 3.0 -7.5 4.0\n"
    o.write_text(baked)
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.OURS and v.witness == "y-only"
    res = PW.restore_pack_objects(str(pack))
    assert o.read_text() == OBJ
    assert len(res.unproven) == 1
    kept = Path(res.unproven[0])
    assert B.UNRECOGNISED_INFIX in kept.name
    assert kept.read_text() == baked, "a witness is not a proof"


def test_O6_replaced_is_never_overwritten_and_retires_the_backup(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    new = "I\n800\nOBJ\nTRIS 0 3\nA COMPLETELY NEW VERSION\n"
    o.write_text(new)
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.REPLACED and v.read_path == str(o)
    assert not v.may_write
    res = PW.restore_pack_objects(str(pack))
    assert o.read_text() == new, "THE USER'S FILE LOSES NO BYTES"
    assert not bak.exists()
    assert len(res.adopted) == 1
    kept = Path(res.adopted[0])
    assert B.SUPERSEDED_INFIX in kept.name and kept.read_text() == OBJ


def test_O7_a_dropped_object_is_never_resurrected(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    o.unlink()
    v = B.classify_object(str(o), str(pack))
    assert v.state is B.State.LIVE_MISSING
    res = PW.restore_pack_objects(str(pack))
    assert not o.exists(), "the new version dropped it; it stays dropped"
    assert len(res.adopted) == 1 and not bak.exists()


def test_authored_source_takes_the_object_tables_read_frame(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    assert PK.authored_source(str(o), str(pack)) == (str(o), False)   # O1
    bak = Path(str(o) + ".anchor_bak")
    shutil.copy2(o, bak)
    assert PK.authored_source(str(o), str(pack)) == (str(bak), True)  # O2
    o.write_text("I\n800\nOBJ\nA NEW VERSION ENTIRELY\n")
    B.invalidate_memo()
    assert PK.authored_source(str(o), str(pack)) == (str(o), False)   # O6


# ── the superseded rename ───────────────────────────────────────────────

def test_a_second_adoption_never_overwrites_the_first(tmp_path):
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    bak = Path(str(o) + ".anchor_bak")
    for k, body in enumerate(("first original\n", "second original\n")):
        bak.write_text(body)
        v = B.classify_object(str(o), str(pack))
        B.adopt(v, now=None)
        B.invalidate_memo()
    kept = sorted(p.name for p in (pack / "objects").iterdir()
                  if B.SUPERSEDED_INFIX in p.name)
    assert len(kept) == 2, kept
    bodies = sorted((pack / "objects" / n).read_text() for n in kept)
    assert bodies == ["first original\n", "second original\n"]


def test_the_superseded_name_is_read_by_no_walker(tmp_path):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    _record(dsf, {"written_sha256": "0" * 64})
    dsf.write_text(DUMP + "OBJECT 1 -9.9 40.9 0.0\n")
    name = B.adopt(B.classify_dsf(str(dsf)))
    assert not name.endswith((".anchor_bak", ".dsf", ".obj"))
    assert ".anchor_bak." in os.path.basename(name)


# ── the record (§12a (2)) ───────────────────────────────────────────────

def test_two_dsfs_in_one_bucket_keep_two_entries(tmp_path, monkeypatch):
    pack, dsf_a = _pack(tmp_path, name="+40-004.dsf")
    dsf_b = dsf_a.parent / "+40-005.dsf"
    dsf_b.write_text(DUMP)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf_a), tool,
                 work_dir=str(tmp_path / "wa"), body_files=[])
    W.write_pack(str(pack), _plan(pack, dsf_b), tool,
                 work_dir=str(tmp_path / "wb"), body_files=[])
    doc = json.loads((dsf_a.parent / "o4_placement_provenance.json").read_text())
    assert doc["version"] == 2
    assert set(doc["dsfs"]) == {"+40-004.dsf", "+40-005.dsf"}
    assert doc["dsf"] == "+40-005.dsf", "the LAST write's top level, as today"


def test_writing_dsf_B_leaves_dsf_As_body_files_on_disk(tmp_path,
                                                        monkeypatch):
    """RED ON BASE: the version-1 record held ONE ``body_files`` list for
    the whole 10-degree bucket, so writing B removed A's bodies while A's
    live DSF still referenced them."""
    pack, dsf_a = _pack(tmp_path, name="+40-004.dsf")
    dsf_b = dsf_a.parent / "+40-005.dsf"
    dsf_b.write_text(DUMP)
    body_a = pack / "objects" / "a__b0.obj"
    body_a.write_text(f"I\n800\nOBJ\n{PW.CUT_MARK}a body 0\n")
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf_a), tool,
                 work_dir=str(tmp_path / "wa"), body_files=[str(body_a)])
    assert W.written_body_files(str(pack), str(dsf_a)) == (str(body_a),)
    assert W.written_body_files(str(pack), str(dsf_b)) == ()
    W.write_pack(str(pack), _plan(pack, dsf_b), tool,
                 work_dir=str(tmp_path / "wb"), body_files=[])
    PW.restore_pack_objects(str(pack), dsf_path=str(dsf_b))
    assert body_a.is_file(), "DSF B's write must not remove DSF A's bodies"


def test_a_version_1_record_for_a_sibling_dsf_names_no_body(tmp_path):
    pack, dsf = _pack(tmp_path, name="+40-004.dsf")
    sib = dsf.parent / "+40-005.dsf"
    sib.write_text(DUMP)
    _record(sib, {"body_files": ["objects/a__b0.obj"]}, version=1)
    assert W.written_body_files(str(pack), str(sib)) == (
        str(pack / "objects" / "a__b0.obj"),)
    assert W.written_body_files(str(pack), str(dsf)) == ()


def test_the_record_is_written_before_the_move_and_again_after(tmp_path,
                                                               monkeypatch):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    res = W.write_pack(str(pack), _plan(pack, dsf), tool,
                       work_dir=str(tmp_path / "w"), body_files=[])
    e = json.loads(Path(res.provenance_path).read_text())["dsfs"][dsf.name]
    st = os.stat(dsf)
    assert e["written_sha256"] == _sha(dsf)
    assert e["written_size"] == st.st_size
    assert e["written_mtime_ns"] == st.st_mtime_ns
    assert e["backup_size"] == os.stat(str(dsf) + ".anchor_bak").st_size


# ── crash safety: never D5 on our own output ────────────────────────────

def test_crash_before_the_move_classifies_D4_not_D5(tmp_path, monkeypatch):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf), tool,
                 work_dir=str(tmp_path / "w"), body_files=[])

    def boom(*a, **kw):
        raise OSError("crash between the record and the move")

    monkeypatch.setattr(W.shutil, "move", boom)
    with pytest.raises(OSError):
        W.write_pack(str(pack), _plan(pack, dsf), tool,
                     work_dir=str(tmp_path / "w2"), body_files=[])
    B.invalidate_memo()
    assert B.classify_dsf(str(dsf)).state is B.State.OURS


def test_crash_before_the_second_record_write_classifies_D4(tmp_path,
                                                            monkeypatch):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    calls = {"n": 0}
    real = B.update_dsf_entry

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("crash after the move, before the stat record")
        return real(*a, **kw)

    monkeypatch.setattr(W._bs, "update_dsf_entry", flaky)
    with pytest.raises(OSError):
        W.write_pack(str(pack), _plan(pack, dsf), tool,
                     work_dir=str(tmp_path / "w"), body_files=[])
    B.invalidate_memo()
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.OURS and v.witness in ("sha256", "mark")


def test_a_deleted_record_after_a_marked_write_is_still_D4(tmp_path,
                                                           monkeypatch):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    res = W.write_pack(str(pack), _plan(pack, dsf), tool,
                       work_dir=str(tmp_path / "w"), body_files=[])
    os.remove(res.provenance_path)
    B.invalidate_memo()
    v = B.classify_dsf(str(dsf))
    assert v.state is B.State.OURS and v.witness == "mark"
    assert B.carries_our_mark(str(dsf))


# ── D5 end to end, through write_pack ───────────────────────────────────

def test_D5_through_write_pack_adopts_exactly_once(tmp_path, monkeypatch):
    pack, dsf = _pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf), tool,
                 work_dir=str(tmp_path / "w1"), body_files=[])
    old_backup = Path(str(dsf) + ".anchor_bak").read_text()

    new_dump = DUMP.replace("-3.6 40.6", "-3.8 40.8")
    dsf.write_text(new_dump)                       # the user's in-place update
    B.invalidate_memo()
    assert B.classify_dsf(str(dsf)).state is B.State.REPLACED

    res = W.write_pack(str(pack), _plan(pack, dsf), tool,
                       work_dir=str(tmp_path / "w2"), body_files=[])
    assert res.state == "replaced" and res.superseded_path
    sup = Path(res.superseded_path)
    assert B.SUPERSEDED_INFIX in sup.name and sup.read_text() == old_backup
    bak = Path(str(dsf) + ".anchor_bak")
    assert bak.read_text() == new_dump, "the user's file is the new original"
    assert "-3.8 40.8" in dsf.read_text()
    e = json.loads(Path(res.provenance_path).read_text())["dsfs"][dsf.name]
    assert len(e["adopted"]) == 1

    # ...and a SECOND adoption makes a SECOND superseded file
    dsf.write_text(DUMP.replace("-3.6 40.6", "-4.4 41.4"))
    B.invalidate_memo()
    res2 = W.write_pack(str(pack), _plan(pack, dsf), tool,
                        work_dir=str(tmp_path / "w3"), body_files=[])
    assert res2.superseded_path != res.superseded_path
    assert sup.read_text() == old_backup, "the first is untouched"


def test_D6_through_write_pack_keeps_a_copy_then_rebuilds(tmp_path,
                                                          monkeypatch):
    """OWNER Q2: the pack keeps working, and the bytes of the file we
    could not prove are still in the folder."""
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    mystery = DUMP + "OBJECT 1 -9.9 40.9 0.0\n"
    dsf.write_text(mystery)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    res = W.write_pack(str(pack), _plan(pack, dsf), tool,
                       work_dir=str(tmp_path / "w"), body_files=[])
    assert res.state == "unproven" and res.preserved_path
    kept = Path(res.preserved_path)
    assert B.UNRECOGNISED_INFIX in kept.name and kept.read_text() == mystery
    assert "-9.9 40.9" not in dsf.read_text(), "rebuilt from the old backup"
    assert res.notes and "copy of the installed file" in res.notes[0]


@pytest.mark.parametrize("state", ["D2", "D8"])
def test_apply_plan_touches_NOTHING_when_the_dsf_stands_down(tmp_path,
                                                             monkeypatch,
                                                             state):
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    if state == "D2":
        dsf.write_text(DUMP + f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0.352\n")
    else:
        shutil.copy2(dsf, bak)
        os.chmod(bak, 0o000)
    o = _obj(pack, "a.obj", OBJ)
    shutil.copy2(o, str(o) + ".anchor_bak")
    o.write_text("I\n800\nOBJ\nA NEW VERSION\n")
    tool = _stand_in_dsftool(tmp_path, monkeypatch)

    class _F:
        resource = "objects/x__b0.obj"
        text = f"I\n800\nOBJ\n{PW.CUT_MARK}x body 0\n"

    before = _snapshot(pack)
    try:
        with pytest.raises(B.BackupUnproven) as exc:
            PW.apply_plan(_plan(pack, dsf), [_F()], tool,
                          patch_dir=str(tmp_path / "patch"))
        assert "Reinstall the pack" in str(exc.value) or \
               "reinstall the pack" in str(exc.value)
        assert _snapshot(pack) == before, "no restore, no cut file, no record"
    finally:
        if bak.exists():
            os.chmod(bak, 0o644)


# ── partial states ──────────────────────────────────────────────────────

def test_partial_D5_plus_O2(tmp_path):
    pack, dsf = _pack(tmp_path)
    shutil.copy2(dsf, str(dsf) + ".anchor_bak")
    _record(dsf, {"written_sha256": "0" * 64})
    dsf.write_text(DUMP + "OBJECT 1 -9.9 40.9 0.0\n")
    o = _obj(pack, "a.obj", OBJ)
    shutil.copy2(o, str(o) + ".anchor_bak")
    assert B.classify_dsf(str(dsf)).state is B.State.REPLACED
    assert B.classify_object(str(o), str(pack)).state is B.State.PRISTINE


def test_partial_D4_plus_O6_rebuilds_the_dsf_from_its_valid_backup(tmp_path):
    pack, dsf = _pack(tmp_path)
    shutil.copy2(dsf, str(dsf) + ".anchor_bak")
    dsf.write_text(DUMP + f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0.352\n")
    o = _obj(pack, "a.obj", OBJ)
    shutil.copy2(o, str(o) + ".anchor_bak")
    new = "I\n800\nOBJ\nTHE USER'S NEW OBJECT\n"
    o.write_text(new)
    assert B.classify_dsf(str(dsf)).state is B.State.OURS
    assert B.classify_object(str(o), str(pack)).state is B.State.REPLACED
    PW.restore_pack_objects(str(pack))
    assert o.read_text() == new


def test_an_added_obj_is_O1_and_a_removed_one_is_O7(tmp_path):
    pack, _dsf = _pack(tmp_path)
    added = _obj(pack, "new.obj", OBJ)
    gone = pack / "objects" / "gone.obj"
    Path(str(gone) + ".anchor_bak").write_text(OBJ)
    assert B.classify_object(str(added), str(pack)).state is B.State.NO_BACKUP
    assert B.classify_object(str(gone), str(pack)).state is B.State.LIVE_MISSING
    PW.restore_pack_objects(str(pack))
    assert added.read_text() == OBJ and not gone.exists()


def test_minted_bodies_are_removed_after_adoption_and_a_foreign_b_name_is_not(
        tmp_path, monkeypatch):
    pack, dsf = _pack(tmp_path)
    ours = pack / "objects" / "a__b0.obj"
    ours.write_text(f"I\n800\nOBJ\n{PW.CUT_MARK}a body 0\n")
    theirs = pack / "objects" / "z__b9.obj"
    theirs.write_text("I\n800\nOBJ\nauthored by the pack, honestly\n")
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    W.write_pack(str(pack), _plan(pack, dsf), tool,
                 work_dir=str(tmp_path / "w"),
                 body_files=[str(ours), str(theirs)])
    dsf.write_text(DUMP.replace("-3.6 40.6", "-3.8 40.8"))
    B.invalidate_memo()
    PW.restore_pack_objects(str(pack), dsf_path=str(dsf))
    assert not ours.exists(), "our own previous bodies go"
    assert theirs.is_file(), "a file without the cut mark is never removed"


# ── the dump cache (§12a (3) rows 10 and 11) ────────────────────────────

def test_find_text_dump_never_serves_another_tags_dump(tmp_path):
    """RED ON BASE: ``max(fresh)`` across tags served the OLD backup's
    dump for an ADOPTED DSF, which carries its author's older mtime."""
    from auto_patch_v2.airport import dsf as D
    root = tmp_path / "mod_cache"
    d = root / "pack"
    d.mkdir(parents=True)
    pack, dsf = _pack(tmp_path)
    old = d / (dsf.name + ".deadbeef.text")
    old.write_text("the previous version's dump")
    st = os.stat(dsf)
    os.utime(old, (st.st_atime + 600, st.st_mtime + 600))
    assert D.find_text_dump(str(root), "pack", 40, -4, str(dsf)) is None
    keyed = d / f"{dsf.name}.{D.text_dump_tag(str(dsf))}.text"
    keyed.write_text("the right one")
    os.utime(keyed, (st.st_atime + 600, st.st_mtime + 600))
    assert D.find_text_dump(str(root), "pack", 40, -4, str(dsf)) == str(keyed)


def test_after_adoption_the_dump_is_keyed_on_the_new_bytes(tmp_path):
    from auto_patch_v2.airport import dsf as D
    pack, dsf = _pack(tmp_path)
    bak = Path(str(dsf) + ".anchor_bak")
    shutil.copy2(dsf, bak)
    tag_before = D.text_dump_tag(W.pristine_dsf_path(str(dsf)))
    _record(dsf, {"written_sha256": "0" * 64})
    dsf.write_text(DUMP + "OBJECT 1 -9.9 40.9 0.0\n")
    B.invalidate_memo()
    B.adopt(B.classify_dsf(str(dsf)))
    B.invalidate_memo()
    assert D.text_dump_tag(W.pristine_dsf_path(str(dsf))) != tag_before


# ── the UI restore (§12a (3) row 13) ────────────────────────────────────

def test_ui_restore_restores_ours_and_keeps_the_users_file(tmp_path):
    from auto_patch import object_rebake
    pack, _dsf = _pack(tmp_path)
    mine = _obj(pack, "mine.obj", OBJ)
    shutil.copy2(mine, str(mine) + ".anchor_bak")
    mine.write_text("I\n800\nOBJ\nVT 1.0 -3.0 2.0\nVT 3.0 -3.0 4.0\n")
    yours = _obj(pack, "yours.obj", OBJ)
    shutil.copy2(yours, str(yours) + ".anchor_bak")
    new = "I\n800\nOBJ\nA WHOLE NEW OBJECT FROM THE NEW PACK VERSION\n"
    yours.write_text(new)
    out = object_rebake.restore_detail(str(pack))
    assert out == {"restored": 1, "kept_changed": 1}
    assert mine.read_text() == OBJ
    assert yours.read_text() == new, "THE USER'S FILE LOSES NO BYTES"
    assert object_rebake.restore(str(pack)) == 0        # idempotent, int reply


def test_the_session_reply_carries_restored_and_kept_changed(tmp_path):
    from o4_engine.session import EngineSession
    pack, _dsf = _pack(tmp_path)
    o = _obj(pack, "a.obj", OBJ)
    shutil.copy2(o, str(o) + ".anchor_bak")
    o.write_text("I\n800\nOBJ\nTHE USER'S OWN\n")
    reply = EngineSession.reanchor_restore(
        object.__new__(EngineSession), str(pack))
    assert reply["restored"] == 0 and reply["kept_changed"] == 1


# ── the disabled pack (§12a (3) row 15) ─────────────────────────────────

def test_a_disabled_pack_is_never_classified_or_written(tmp_path,
                                                        monkeypatch):
    import O4_Scenery_Packs as SP
    from auto_patch import engine_v2

    seen: list = []
    monkeypatch.setattr(SP, "pack_enabled", lambda p, d=None: False)
    monkeypatch.setattr(engine_v2, "_place_objects",
                        lambda *a, **kw: seen.append(a) or {})

    pack, dsf = _pack(tmp_path)
    plan_dir = tmp_path / "patch"
    plan_dir.mkdir()
    monkeypatch.setattr(B, "classify_dsf",
                        lambda p: pytest.fail("a disabled pack was classified"))
    assert SP.pack_enabled(str(pack)) is False
    assert not seen


# ── THE MARK TWIN: a real DSFTool round trip ────────────────────────────

_XP = "/Users/noah/X-Plane 12/Custom Scenery"
_REAL = [
    "c_FRA - 100_airport - TFFJ_1_Apt/Earth nav data/+10-070/+17-064.dsf",
    "KMCI Kansas City (Taimodels)/Earth nav data/+30-100/+39-095.dsf",
]


def _real_dsf() -> str | None:
    for rel in _REAL:
        p = os.path.join(_XP, rel)
        if os.path.isfile(p):
            return p
    return None


def _tool() -> str | None:
    from auto_patch.dsf_reader import _dsftool_path
    return _dsftool_path()


@pytest.mark.skipif(_real_dsf() is None or _tool() is None,
                    reason="no shipped pack / no DSFTool on this machine")
def test_the_ownership_mark_round_trips_through_dsftool(tmp_path):
    """THE FIRST TWIN.  READ-ONLY on the owner's install: the DSF is
    ``copy2``'d into ``tmp_path`` and every write lands there."""
    from auto_patch_v2.airport import dsf as D
    tool = _tool()
    src = _real_dsf()
    pack, dsf = _pack(tmp_path)
    shutil.copy2(src, dsf)

    pristine_text = W.dump(str(dsf), str(tmp_path / "p.text"), tool)
    text = Path(pristine_text).read_text(errors="replace")
    assert B.OWNERSHIP_PROPERTY not in text
    assert not B.carries_our_mark(str(dsf))

    plan = _plan(pack, dsf, conversions=())
    edited = W.edit_dump(text, plan, "1.0.352")
    assert edited.count(f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0.352") == 1
    (tmp_path / "e.text").write_text(edited)
    out = W.encode(str(tmp_path / "e.text"), str(tmp_path / "out.dsf"), tool)

    # the property survives text -> dsf -> text ...
    again = Path(W.dump(out, str(tmp_path / "a.text"), tool)).read_text(
        errors="replace")
    assert f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0.352" in again
    # ... the byte scan finds it in the ENCODED file ...
    assert B.carries_our_mark(out)
    assert not B.carries_our_mark(str(dsf))
    # ... and the round-trip verification still passes with it there
    rep = W.compare_dumps(edited, again)
    assert rep.ok, rep.findings
    assert D.read_dump(str(tmp_path / "a.text")).placements


# ── THE CLOSING TWIN: a real pack folder, written twice ─────────────────

@pytest.mark.skipif(_real_dsf() is None or _tool() is None,
                    reason="no shipped pack / no DSFTool on this machine")
def test_a_real_pack_updated_in_place_between_two_builds(tmp_path):
    """END TO END on a COPY of a real pack folder (the harness stands
    every pack write down, so this IS the closing evidence).

    Build 1 writes the pack.  The user then updates the pack IN PLACE —
    a new DSF over ours, our ``.anchor_bak`` left behind.  Build 2 must:
    keep the NEW DSF's content as the new original, retire the old backup
    under a stamped name, and move the freshness identity EXACTLY ONCE."""
    from auto_patch import provenance
    tool = _tool()
    src = _real_dsf()
    pack, dsf = _pack(tmp_path)
    shutil.copy2(src, dsf)

    dump_path = W.dump(str(dsf), str(tmp_path / "d0.text"), tool)
    from auto_patch_v2.airport import dsf as D
    conv, kept = W.conversions_for_dump(D.read_dump(dump_path), str(pack))
    plan = _plan(pack, dsf, conversions=tuple(conv), kept=tuple(kept))

    import time
    t0 = time.perf_counter()
    r1 = W.write_pack(str(pack), plan, tool, work_dir=str(tmp_path / "w1"),
                      engine_version="1.0.352", body_files=[])
    t_build1 = time.perf_counter() - t0
    assert r1.backup_created and r1.state == "no_backup"
    assert B.carries_our_mark(str(dsf))
    bak = Path(str(dsf) + ".anchor_bak")
    id_after_1 = provenance.pack_dsf_input_identity(str(dsf))

    # ── the user installs a new version of the pack, IN PLACE ──────────
    new_bytes = Path(src).read_bytes() + b"\x00new-version-tail"
    dsf.write_bytes(new_bytes)
    os.utime(dsf, (os.path.getatime(dsf), os.path.getmtime(dsf) + 4242))
    B.invalidate_memo()
    id_replaced = provenance.pack_dsf_input_identity(str(dsf))
    assert id_replaced != id_after_1, "the patch rebuilds: the input moved"
    assert B.classify_dsf(str(dsf)).state is B.State.REPLACED

    # build 2 re-plans against the NEW file, as the read frame now says
    dump2 = W.dump(W.pristine_dsf_path(str(dsf)), str(tmp_path / "d1.text"),
                   tool)
    assert Path(W.pristine_dsf_path(str(dsf))).read_bytes() == new_bytes
    conv2, kept2 = W.conversions_for_dump(D.read_dump(dump2), str(pack))
    plan2 = _plan(pack, dsf, conversions=tuple(conv2), kept=tuple(kept2))
    t0 = time.perf_counter()
    r2 = W.write_pack(str(pack), plan2, tool, work_dir=str(tmp_path / "w2"),
                      engine_version="1.0.352", body_files=[])
    t_build2 = time.perf_counter() - t0

    # 1. the new DSF survives — it IS the new original
    assert r2.state == "replaced"
    assert bak.read_bytes() == new_bytes
    # 2. the old backup was renamed, never deleted, and still holds the
    #    bytes the pack shipped before the update
    sup = Path(r2.superseded_path)
    assert B.SUPERSEDED_INFIX in sup.name
    assert sup.read_bytes() == Path(src).read_bytes()
    # 3. the identity changes EXACTLY ONCE: after the adopting build the
    #    gate reads current again (copy2 preserved size+mtime)
    B.invalidate_memo()
    id_after_2 = provenance.pack_dsf_input_identity(str(dsf))
    assert id_after_2 == id_replaced
    B.invalidate_memo()
    assert provenance.pack_dsf_input_identity(str(dsf)) == id_after_2
    assert B.classify_dsf(str(dsf)).state is B.State.OURS

    # BUILD-TIME IMPACT (§12a (6)): the NORMAL path costs stats only.
    B.invalidate_memo()
    t0 = time.perf_counter()
    for _ in range(50):
        B.invalidate_memo()
        assert B.classify_dsf(str(dsf)).witness == "stat"
    per_call = (time.perf_counter() - t0) / 50
    print(f"\n[§12a (6)] {os.path.basename(src)} "
          f"({os.path.getsize(src)} bytes): classify_dsf on the NORMAL path "
          f"{per_call * 1e3:.3f} ms/call (cold memo); write_pack "
          f"{t_build1:.2f} s (D1) / {t_build2:.2f} s (D5, one adoption)")
    assert per_call < 0.005, "the normal path must not hash the DSF"
