"""A DSF whose commands read a pool before selecting one still dumps (#568).

MEASURED 2026-10-12, DSFTool 2.4.0-b1 (``tools/dsftool_dump_census.py``):
8 of the 7,077 stock Global Airports DSFs die with SIGSEGV on
``--dsf2text`` — exactly the 8 overlay files whose command stream sets a
16-bit definition before its first ``PoolSelect`` (DSFTool's pool census
then reads ``planeScales[0xFFFF][3]``).  ``dsf_commands.select_pool_first``
makes the copy that dumps, and ``dsf_write.dump`` retries a crash on it.

The twins build DSF bytes by hand and stand a fake ``subprocess.run`` in
for DSFTool: no binary, no network, no X-Plane install.
"""
from __future__ import annotations

import hashlib
import os
import struct
import subprocess

import pytest

from auto_patch_v2.airport import dsf_commands, dsf_write

POOL_SELECT, DEF8, DEF16, OBJECT, OBJECT_RANGE = 1, 3, 4, 7, 8


def _atom(name: bytes, payload: bytes) -> bytes:
    return struct.pack("<4sI", name[::-1], 8 + len(payload)) + payload


def _cmd(command: int, fmt: str = "", *operands: int) -> bytes:
    return struct.pack("<B" + fmt, command, *operands)


#: definition 292, THEN pool 19, then two objects: the stock file's opening.
TRAIT = (_cmd(2, "I", 0) + _cmd(32, "B", 2) + b"hi" + _cmd(DEF16, "H", 292)
         + _cmd(POOL_SELECT, "H", 19) + _cmd(OBJECT, "H", 0)
         + _cmd(OBJECT_RANGE, "HH", 1, 5))


def _dsf(cmds: bytes, *, overlay: bytes | None = b"1") -> bytes:
    props = b"sim/west\0-123\0"
    if overlay is not None:
        props += b"sim/overlay\0" + overlay + b"\0"
    body = (b"XPLNEDSF" + struct.pack("<I", 1)
            + _atom(b"HEAD", _atom(b"PROP", props))
            + _atom(b"DEFN", _atom(b"OBJT", b"a.obj\0"))
            + _atom(b"CMDS", cmds)
            + _atom(b"GEOD", b""))
    return body + hashlib.md5(body).digest()


def _commands_of(buf: bytes) -> bytes:
    (_aid, off, length), = [a for a in dsf_commands.atoms(buf, 12, len(buf) - 16)
                            if a[0] == b"SDMC"]
    return buf[off + 8:off + length]


# ── the repair ──────────────────────────────────────────────────────────

def test_the_pool_the_file_reads_first_is_selected_first():
    source = _dsf(TRAIT)

    repaired = dsf_commands.select_pool_first(source)

    assert _commands_of(repaired) == _cmd(POOL_SELECT, "H", 19) + TRAIT
    assert repaired[-16:] == hashlib.md5(repaired[:-16]).digest()
    # nothing else moved: the atoms before and after the commands are equal
    before, after = source.index(TRAIT) - 8, source.index(TRAIT) + len(TRAIT)
    assert repaired[:before] == source[:before]
    assert repaired[after + 3:-16] == source[after:-16]


def test_the_walk_steps_over_every_command_family_ahead_of_the_read():
    ahead = (_cmd(9, "BHH", 2, 1, 2)                       # network chain
             + _cmd(11, "BI", 1, 7)                        # 32-bit chain
             + _cmd(12, "HBHH", 0, 2, 1, 2)                # polygon
             + _cmd(13, "HHH", 0, 1, 2)                    # polygon range
             + _cmd(14, "HBBHBHH", 0, 2, 1, 9, 2, 8, 7)    # nested polygon
             + _cmd(15, "HBHHH", 0, 2, 1, 4, 6)            # nested range
             + _cmd(33, "H", 3) + b"abc" + _cmd(34, "I", 1) + b"z"
             + _cmd(DEF8, "B", 7) + _cmd(5, "I", 70000) + _cmd(6, "B", 1))
    repaired = dsf_commands.select_pool_first(_dsf(ahead + TRAIT))

    assert _commands_of(repaired) == _cmd(POOL_SELECT, "H", 19) + ahead + TRAIT


@pytest.mark.parametrize("why, buf", [
    ("a pool is selected before the first read",
     _dsf(_cmd(POOL_SELECT, "H", 3) + TRAIT)),
    ("8-bit definitions are not read by the census",
     _dsf(_cmd(DEF8, "B", 9) + _cmd(POOL_SELECT, "H", 3) + _cmd(OBJECT, "H", 0))),
    ("not an overlay: the census reads terrain patches", _dsf(TRAIT, overlay=None)),
    ("sim/overlay 0", _dsf(TRAIT, overlay=b"0")),
    ("no selected pool is ever read", _dsf(_cmd(DEF16, "H", 292))),
    ("the census stops at an unknown command", _dsf(_cmd(99) + TRAIT)),
    ("a compressed DSF", b"7z\xbc\xaf\x27\x1c" + _dsf(TRAIT)),
    ("a cut command stream", _dsf(TRAIT[:8] + _cmd(12, "H", 0))),
    ("not a DSF", b"XPLNEDSF"),
])
def test_a_file_without_the_trait_is_left_alone(why, buf):
    assert dsf_commands.select_pool_first(buf) is None, why


# ── the dump ────────────────────────────────────────────────────────────

DUMP_TEXT = "A\n800\nDSF2TEXT\n\nPROPERTY sim/overlay 1\nOBJECT_DEF a.obj\n"


def _dsftool(monkeypatch, *, heals: bool = True):
    """DSFTool as measured: it creates its output, then crashes on a
    command stream that does not open with a ``PoolSelect``."""
    calls = []

    def run(argv, **_kwargs):
        with open(argv[2], "rb") as handle:
            opens_with_select = _commands_of(handle.read())[:1] == b"\x01"
        calls.append((argv[2], argv[3], os.path.dirname(argv[2])))
        with open(argv[3], "w", encoding="utf-8", newline="") as handle:
            if not (opens_with_select and heals):
                return subprocess.CompletedProcess(argv, -11, "", "")
            handle.write(DUMP_TEXT)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(dsf_write.subprocess, "run", run)
    return calls


def _on_disk(tmp_path, buf: bytes):
    tool = tmp_path / "DSFTool"
    tool.write_bytes(b"")
    dsf = tmp_path / "pack" / "+47-123.dsf"
    dsf.parent.mkdir()
    dsf.write_bytes(buf)
    out = tmp_path / "cache" / "+47-123.dsf.abcd1234.text"
    out.parent.mkdir()
    return str(dsf), str(out), str(tool)


def test_a_crash_on_the_trait_is_retried_on_a_copy_and_dumps(tmp_path, monkeypatch):
    source = _dsf(TRAIT)
    dsf, out, tool = _on_disk(tmp_path, source)
    calls = _dsftool(monkeypatch)

    assert dsf_write.dump(dsf, out, tool) == out

    with open(out, encoding="utf-8", newline="") as handle:
        assert handle.read() == DUMP_TEXT
    assert [c[0] == dsf for c in calls] == [True, False]
    copy, copy_folder = calls[1][0], calls[1][2]
    assert os.path.basename(copy) == "+47-123.dsf"
    assert not os.path.exists(copy_folder), "the temp copy outlived the dump"
    # the pack is never written, and the cache holds the dump and no litter
    with open(dsf, "rb") as handle:
        assert handle.read() == source
    assert os.listdir(os.path.dirname(dsf)) == ["+47-123.dsf"]
    assert os.listdir(os.path.dirname(out)) == [os.path.basename(out)]


def test_a_crash_without_the_trait_stands(tmp_path, monkeypatch):
    dsf, out, tool = _on_disk(tmp_path, _dsf(_cmd(DEF8, "B", 9) + TRAIT[12:]))
    calls = _dsftool(monkeypatch)

    with pytest.raises(dsf_write.DsfToolError, match=r"crashed \(SIGSEGV\)") as caught:
        dsf_write.dump(dsf, out, tool)

    assert caught.value.crashed
    assert len(calls) == 1
    assert os.listdir(os.path.dirname(out)) == []


def test_a_crash_of_the_retry_is_the_failure_and_leaves_nothing(tmp_path, monkeypatch):
    dsf, out, tool = _on_disk(tmp_path, _dsf(TRAIT))
    calls = _dsftool(monkeypatch, heals=False)

    with pytest.raises(dsf_write.DsfToolError, match=r"crashed \(SIGSEGV\)"):
        dsf_write.dump(dsf, out, tool)

    assert len(calls) == 2
    assert not os.path.exists(calls[1][2])
    assert os.listdir(os.path.dirname(out)) == []


def test_a_failure_that_is_not_a_crash_is_not_retried(tmp_path, monkeypatch):
    dsf, out, tool = _on_disk(tmp_path, _dsf(TRAIT))
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "cannot read")

    monkeypatch.setattr(dsf_write.subprocess, "run", run)

    with pytest.raises(dsf_write.DsfToolError, match=r"failed \(exit 1\)") as caught:
        dsf_write.dump(dsf, out, tool)

    assert not caught.value.crashed
    assert len(calls) == 1
