"""A DSF text dump is written atomically, and an empty one is no dump (#560).

MEASURED 2026-10-11 (owner's app, engine 1.50.1834): DSFTool 2.4.0-b1
died with SIGSEGV on a stock Global Airports tile DSF.  DSFTool creates
its output file before it reads the DSF, so each crash left a 0-byte
``<tile>.dsf.<sha>.text`` under the dump's final name; the refresh
answered ``None`` and the loader refused six airports with "the pack DSF
is newer than every cached text dump" — for a file unchanged since August.

The twins use a fake ``subprocess.run`` in place of DSFTool, so they run
on every platform and spawn nothing:

* a failed, crashed or timed-out dump leaves NOTHING under the final name
  and keeps an older good dump;
* an empty dump is absent to every reader, and the refusal says so;
* the refresh re-derives an empty dump, and raises the real cause when
  DSFTool cannot make one;
* two dumps of one DSF at once both end whole.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import types

import pytest

from auto_patch import dsf_reader, engine_v2
from auto_patch_v2.airport import dsf as dsf_v2
from auto_patch_v2.airport import dsf_write

DUMP_TEXT = "A\n800\nDSF2TEXT\n\nPROPERTY sim/west -123\nOBJECT_DEF a.obj\n"


def _fake_tool(tmp_path):
    """A file that passes ``dump``'s "is there a tool" check; never run."""
    tool = tmp_path / "DSFTool"
    tool.write_bytes(b"")
    return str(tool)


def _dsftool(monkeypatch, *, returncode=0, text=DUMP_TEXT, stderr="",
             slow_s=0.0, timeout=False):
    """Stand in for the DSFTool child: write ``text`` to the path it was
    given (``argv[3]``), then exit ``returncode``.  Returns the argv log."""
    calls = []

    def run(argv, **kwargs):
        calls.append(list(argv))
        with open(argv[3], "w", encoding="utf-8", newline="") as handle:
            half = len(text) // 2
            handle.write(text[:half])
            handle.flush()
            if slow_s:
                time.sleep(slow_s)
            if timeout:
                raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
            if returncode == 0:
                handle.write(text[half:])
        return subprocess.CompletedProcess(argv, returncode, "", stderr)

    monkeypatch.setattr(dsf_write.subprocess, "run", run)
    return calls


def _dsf(tmp_path, payload=b"XPLNEDSF-one"):
    path = tmp_path / "+47-123.dsf"
    path.write_bytes(payload)
    past = time.time() - 3600
    os.utime(path, (past, past))
    return str(path)


def _names(folder):
    return sorted(os.listdir(folder))


# ── the writer ──────────────────────────────────────────────────────────

def test_a_crashed_dump_leaves_nothing_under_the_final_name(tmp_path, monkeypatch):
    out = tmp_path / "cache" / "+47-123.dsf.abcd1234.text"
    out.parent.mkdir()
    calls = _dsftool(monkeypatch, returncode=-11)

    with pytest.raises(dsf_write.DsfToolError, match=r"crashed \(SIGSEGV\)"):
        dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path))

    assert _names(out.parent) == [], "a crashed DSFTool left a file behind"
    # DSFTool was pointed at a sibling of the dump, never at the dump itself
    assert calls[0][3] != str(out)
    assert os.path.dirname(calls[0][3]) == str(out.parent)
    assert not calls[0][3].endswith((".text", ".dsf"))


def test_a_failed_dump_keeps_the_good_dump_already_there(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    out.write_text("the good dump", encoding="utf-8", newline="")
    _dsftool(monkeypatch, returncode=1, stderr="cannot read")

    with pytest.raises(dsf_write.DsfToolError, match=r"failed \(exit 1\): cannot read"):
        dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path))

    assert out.read_text(encoding="utf-8") == "the good dump"
    assert not [n for n in _names(tmp_path) if n.endswith(".partial")]


def test_a_dump_that_wrote_nothing_is_a_failure(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    _dsftool(monkeypatch, text="")

    with pytest.raises(dsf_write.DsfToolError, match="wrote no text"):
        dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path))

    assert not out.exists()


def test_a_timed_out_dump_leaves_nothing_and_says_so(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    _dsftool(monkeypatch, timeout=True)

    with pytest.raises(dsf_write.DsfToolError, match="did not finish") as caught:
        dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path), timeout=5)

    assert caught.value.timed_out
    assert _names(tmp_path) == ["+47-123.dsf", "DSFTool"]


def test_a_good_dump_lands_whole_and_sweeps_a_killed_runs_litter(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    killed = tmp_path / (out.name + ".999.deadbeef.partial")
    killed.write_text("half", encoding="utf-8", newline="")
    old = time.time() - 2 * dsf_write._PARTIAL_DUMP_STALE_S
    os.utime(killed, (old, old))
    _dsftool(monkeypatch)

    assert dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path)) == str(out)

    assert out.read_text(encoding="utf-8") == DUMP_TEXT
    assert not killed.exists()


def test_two_dumps_of_one_dsf_at_once_both_end_whole(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    dsf, tool = _dsf(tmp_path), _fake_tool(tmp_path)
    calls = _dsftool(monkeypatch, slow_s=0.05)
    errors = []

    def one():
        try:
            dsf_write.dump(dsf, str(out), tool)
        except Exception as error:          # reported below
            errors.append(error)

    workers = [threading.Thread(target=one) for _ in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert not errors
    assert len({argv[3] for argv in calls}) == 6, "writers shared a temp file"
    assert out.read_text(encoding="utf-8") == DUMP_TEXT
    assert not [n for n in _names(tmp_path) if n.endswith(".partial")]


# ── the rename, as Windows refuses it (PR #569) ─────────────────────────

def _refusing_replace(monkeypatch, times, on_refusal=None):
    """``os.replace`` raising ``PermissionError`` its first ``times`` calls,
    as Windows does while another process holds or is replacing the
    target; ``on_refusal(src, dst)`` runs at each refusal.  No sleeping."""
    real, refused = os.replace, []

    def replace(src, dst):
        if len(refused) < times:
            refused.append((src, dst))
            if on_refusal:
                on_refusal(src, dst)
            raise PermissionError(13, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(dsf_write.os, "replace", replace)
    monkeypatch.setattr(dsf_write.time, "sleep", lambda _s: None)
    return refused


def test_a_refused_rename_is_tried_again(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    out.write_bytes(b"")                    # the empty dump being healed
    _dsftool(monkeypatch)
    refused = _refusing_replace(monkeypatch, times=1)

    assert dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path)) == str(out)

    assert len(refused) == 1
    assert out.read_text(encoding="utf-8") == DUMP_TEXT
    assert not [n for n in _names(tmp_path) if n.endswith(".partial")]


def test_a_refused_rename_uses_the_dump_another_writer_landed(tmp_path, monkeypatch):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    theirs = "A\n800\nDSF2TEXT\n\n# the other worker's whole dump\n"
    _dsftool(monkeypatch)

    def winner_lands(_src, dst):
        with open(dst, "w", encoding="utf-8", newline="") as handle:
            handle.write(theirs)

    refused = _refusing_replace(monkeypatch, times=99, on_refusal=winner_lands)

    assert dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path)) == str(out)

    assert len(refused) == 1, "a landed dump was not accepted at once"
    assert out.read_text(encoding="utf-8") == theirs
    assert not [n for n in _names(tmp_path) if n.endswith(".partial")]


@pytest.mark.parametrize("already_there", [None, b"", b"an older dump"])
def test_a_rename_refused_for_good_names_the_cause(tmp_path, monkeypatch, already_there):
    out = tmp_path / "+47-123.dsf.abcd1234.text"
    if already_there is not None:
        out.write_bytes(already_there)
        old = time.time() - 600             # there long before this dump
        os.utime(out, (old, old))
    _dsftool(monkeypatch)
    refused = _refusing_replace(monkeypatch, times=99)

    with pytest.raises(dsf_write.DsfToolError, match="could not be moved onto") as caught:
        dsf_write.dump(_dsf(tmp_path), str(out), _fake_tool(tmp_path))

    assert "Access is denied" in str(caught.value)
    assert len(refused) == 1 + len(dsf_write._LAND_RETRY_WAITS_S)
    # what was there is untouched: never a stale or empty dump served as new
    assert (out.read_bytes() if out.exists() else None) == already_there
    assert not [n for n in _names(tmp_path) if n.endswith(".partial")]


# ── the readers ─────────────────────────────────────────────────────────

def test_an_empty_dump_is_absent_and_the_reason_says_empty(tmp_path):
    dsf = _dsf(tmp_path)
    cache = tmp_path / "cache" / "Some Pack"
    cache.mkdir(parents=True)
    empty = cache / f"+47-123.dsf.{dsf_v2.text_dump_tag(dsf)}.text"
    empty.write_bytes(b"")

    assert dsf_v2.content_keyed_dump(str(cache), dsf) is None
    assert dsf_v2.find_text_dump(str(tmp_path / "cache"), "Some Pack", 47, -123,
                                 dsf_path=dsf) is None
    reason = dsf_v2.missing_dump_reason(str(cache), dsf)
    assert "EMPTY (0 bytes)" in reason and empty.name in reason


def test_the_reason_tells_no_dump_from_a_dump_of_another_version(tmp_path):
    dsf = _dsf(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()

    assert "no text dump of it" in dsf_v2.missing_dump_reason(str(cache), dsf)

    (cache / "+47-123.dsf.0000beef.text").write_text(DUMP_TEXT, encoding="utf-8", newline="")
    (cache / "+45-123.dsf.0000beef.text").write_text(DUMP_TEXT, encoding="utf-8", newline="")
    reason = dsf_v2.missing_dump_reason(str(cache), dsf)
    assert "another version" in reason and "+47-123.dsf.0000beef.text" in reason
    assert "+45-123" not in reason, "a neighbour tile's dump is not this file's"


# ── the refresh ─────────────────────────────────────────────────────────

def test_the_refresh_heals_an_empty_dump(tmp_path, monkeypatch):
    dsf = _dsf(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    empty = cache / f"+47-123.dsf.{dsf_v2.text_dump_tag(dsf)}.text"
    empty.write_bytes(b"")
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: _fake_tool(tmp_path))
    calls = _dsftool(monkeypatch)

    assert dsf_reader.ensure_dsf_text_path(dsf, str(cache)) == str(empty)

    assert len(calls) == 1, "the empty dump was not re-derived exactly once"
    assert empty.read_text(encoding="utf-8") == DUMP_TEXT
    assert dsf_v2.content_keyed_dump(str(cache), dsf) == str(empty)
    # ... and a healed dump is recycled, not dumped again
    assert dsf_reader.ensure_dsf_text_path(dsf, str(cache)) == str(empty)
    assert len(calls) == 1


def test_a_refresh_that_cannot_dump_leaves_the_cache_clean(tmp_path, monkeypatch):
    dsf = _dsf(tmp_path)
    cache = tmp_path / "cache"
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: _fake_tool(tmp_path))
    _dsftool(monkeypatch, returncode=-11)

    assert dsf_reader.ensure_dsf_text_path(dsf, str(cache)) is None
    assert _names(cache) == []

    with pytest.raises(dsf_write.DsfToolError) as caught:
        dsf_reader.ensure_dsf_text_path(dsf, str(cache), raise_on_failure=True)
    assert "crashed (SIGSEGV)" in str(caught.value) and dsf in str(caught.value)
    assert _names(cache) == []


def test_a_missing_dsftool_is_named_unless_the_dump_is_cached(tmp_path, monkeypatch):
    dsf = _dsf(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: None)

    with pytest.raises(dsf_write.DsfToolError, match="DSFTool program is missing"):
        dsf_reader.ensure_dsf_text_path(dsf, str(cache), raise_on_failure=True)

    good = cache / f"+47-123.dsf.{dsf_v2.text_dump_tag(dsf)}.text"
    good.write_text(DUMP_TEXT, encoding="utf-8", newline="")
    assert dsf_reader.ensure_dsf_text_path(
        dsf, str(cache), raise_on_failure=True) == str(good)


def _pack(tmp_path, monkeypatch):
    """A one-tile pack the driver's refresh resolves to; returns its DSF."""
    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import pack as pack_module
    root = tmp_path / "Custom Scenery" / "Some Pack"
    folder = root / "Earth nav data" / "+40-130"
    folder.mkdir(parents=True)
    dsf = _dsf(folder)
    monkeypatch.setattr(pack_module, "select_pack", lambda *_a, **_k:
                        types.SimpleNamespace(root=str(root), name="Some Pack"))
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root",
                        lambda: str(tmp_path / "cache"))
    monkeypatch.setattr(dsf_reader, "_dsftool_path", lambda: _fake_tool(tmp_path))
    return dsf


def test_the_drivers_refresh_raises_the_real_cause(tmp_path, monkeypatch):
    dsf = _pack(tmp_path, monkeypatch)
    _dsftool(monkeypatch, returncode=-11)

    with pytest.raises(dsf_write.DsfToolError) as caught:
        engine_v2.fresh_pack_dump(str(tmp_path), "XXXX", 47, -123)

    said = str(caught.value)
    assert said.startswith("XXXX: the scenery pack 'Some Pack' cannot be read")
    assert "crashed (SIGSEGV)" in said and dsf in said
    assert "newer than" not in said
    assert _names(tmp_path / "cache" / "Some Pack") == []


def test_the_drivers_refresh_heals_an_empty_dump(tmp_path, monkeypatch):
    dsf = _pack(tmp_path, monkeypatch)
    cache = tmp_path / "cache" / "Some Pack"
    cache.mkdir(parents=True)
    empty = cache / f"+47-123.dsf.{dsf_v2.text_dump_tag(dsf)}.text"
    empty.write_bytes(b"")
    _dsftool(monkeypatch)

    assert engine_v2.fresh_pack_dump(str(tmp_path), "XXXX", 47, -123) == str(empty)
    assert empty.read_text(encoding="utf-8") == DUMP_TEXT
