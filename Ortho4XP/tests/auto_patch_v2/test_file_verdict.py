"""#2206: ``airport/file_verdict.FileVerdict`` -- one verdict per file
version, derived from the caller's parse; it parses only when offered none."""
from __future__ import annotations

import os

from auto_patch_v2.airport import file_verdict as FV
from auto_patch_v2.airport import obj8


def test_offered_geometry_is_read_and_none_offered_parses(tmp_path, monkeypatch):
    p = tmp_path / "a.obj"
    p.write_text("I\n800\nOBJ\nPOINT_COUNTS 0 0 0 0\n", encoding="utf-8", newline="\n")
    parsed, seen = [], []
    real = obj8.parse_obj8
    monkeypatch.setattr(obj8, "parse_obj8", lambda path: parsed.append(path) or real(path))
    memo = FV.FileVerdict(lambda path, g: seen.append(g) or len(seen))
    given = object()
    assert memo(str(p), given) == 1 and seen == [given] and parsed == []
    assert memo(str(p)) == 1 and parsed == []            # same version: the memo
    os.utime(p, ns=(1, 1))                               # a new version
    assert memo(str(p)) == 2 and parsed == [str(p)]
    assert memo(str(tmp_path / "missing.obj")) is None


def test_a_raising_derivation_reads_none(tmp_path):
    p = tmp_path / "b.obj"
    p.write_text("x", encoding="utf-8", newline="\n")

    def bad(path, g):
        raise ValueError("unreadable")
    assert FV.FileVerdict(bad)(str(p), object()) is None


def test_the_memo_is_bounded(tmp_path):
    memo = FV.FileVerdict(lambda path, g: path, maxsize=2)
    for k in range(3):
        (tmp_path / f"{k}.obj").write_text("x", encoding="utf-8", newline="\n")
        memo(str(tmp_path / f"{k}.obj"), object())
    assert len(memo._memo) == 2
