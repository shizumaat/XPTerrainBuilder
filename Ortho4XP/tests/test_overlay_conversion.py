"""The overlay step waits for its converter and reads its result (#591).

``build_overlay`` read ``Popen.returncode`` without waiting, so it was
always ``None``: a DSFTool that crashed, or exited non-zero after writing
a file, was accepted, and one that hung held the step for ever.  A fake
``subprocess.run`` stands in for DSFTool — nothing is spawned.
"""
from __future__ import annotations

import os
import subprocess

import pytest

import O4_File_Names as FNAMES
import O4_Overlay_Utils as OVL
import O4_UI_Utils as UI

(LAT, LON) = (22, 113)
DUMP = ("PROPERTY sim/west 113\nPOLYGON_DEF lib/a.for\n"
        "BEGIN_POLYGON 0 255 2\nEND_POLYGON\n")


class _Recorder:
    """Stands in for the engine session: keeps what the step names."""

    def __init__(self):
        self.named = []
        self.detail = []

    def tile_failure(self, code, detail="", exc=None, **params):
        self.named.append(code)
        self.detail.append(detail)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def step(tmp_path, monkeypatch):
    """A tile whose overlay source exists; returns (recorder, final path)."""
    source = tmp_path / "Global Scenery"
    dsf = source / "Earth nav data" / (FNAMES.long_latlon(LAT, LON) + ".dsf")
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(OVL, "custom_overlay_src", str(source))
    monkeypatch.setattr(OVL, "custom_overlay_src_alternate", "")
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"))
    monkeypatch.setattr(FNAMES, "Overlay_dir", str(tmp_path / "Overlays"))
    recorder = _Recorder()
    monkeypatch.setattr(UI, "engine_session", recorder)
    monkeypatch.setattr(UI, "is_working", 0)
    final = (tmp_path / "Overlays" / "Earth nav data"
             / FNAMES.round_latlon(LAT, LON)
             / (FNAMES.short_latlon(LAT, LON) + ".dsf"))
    return recorder, final


def _dsftool(monkeypatch, **per_direction):
    """Fake DSFTool: per direction (``dsf2text`` / ``text2dsf``) a dict of
    ``returncode``, ``writes`` (False: no output file) and ``hangs``."""
    calls = []

    def run(argv, **kwargs):
        direction = argv[1].lstrip("-")
        how = per_direction.get(direction, {})
        calls.append((direction, kwargs.get("timeout")))
        if how.get("hangs"):
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        if how.get("writes", True):
            with open(argv[3], "wb") as handle:
                handle.write(DUMP.encode("utf-8") if direction == "dsf2text"
                             else b"XPLNEDSF-overlay")
        return subprocess.CompletedProcess(
            argv, how.get("returncode", 0), "converted\n", "")

    monkeypatch.setattr(OVL.DSFTOOL.subprocess, "run", run)
    return calls


def test_a_conversion_that_works_installs_the_overlay(step, monkeypatch):
    recorder, final = step
    calls = _dsftool(monkeypatch)

    assert OVL.build_overlay(LAT, LON) == 1

    assert final.read_bytes() == b"XPLNEDSF-overlay"
    assert recorder.named == []
    assert calls == [("dsf2text", OVL.OVERLAY_CONVERSION_TIMEOUT_S),
                     ("text2dsf", OVL.OVERLAY_CONVERSION_TIMEOUT_S)]
    assert UI.is_working == 0


def test_a_crash_of_the_first_conversion_ends_the_step_by_name(
        step, monkeypatch):
    recorder, final = step
    calls = _dsftool(monkeypatch, dsf2text={"returncode": -11,
                                            "writes": False})

    assert OVL.build_overlay(LAT, LON) == 0

    assert recorder.named == ["overlay_tool_failed"]
    assert "crashed (SIGSEGV)" in recorder.detail[0]
    assert [direction for direction, _limit in calls] == ["dsf2text"]
    assert not final.exists()
    assert UI.is_working == 0


@pytest.mark.parametrize("direction", ["dsf2text", "text2dsf"])
def test_a_non_zero_exit_after_writing_a_file_is_not_accepted(
        step, monkeypatch, direction):
    recorder, final = step
    _dsftool(monkeypatch, **{direction: {"returncode": 1}})

    assert OVL.build_overlay(LAT, LON) == 0

    assert recorder.named == ["overlay_tool_failed"]
    assert "failed (exit 1)" in recorder.detail[0]
    assert not final.exists()


@pytest.mark.parametrize("direction", ["dsf2text", "text2dsf"])
def test_a_converter_past_its_time_limit_is_a_named_failure(
        step, monkeypatch, direction):
    recorder, final = step
    _dsftool(monkeypatch, **{direction: {"hangs": True}})

    assert OVL.build_overlay(LAT, LON) == 0

    assert recorder.named == ["overlay_tool_failed"]
    assert "did not finish within" in recorder.detail[0]
    assert not final.exists()
    assert UI.is_working == 0


def test_an_exit_zero_that_wrote_nothing_does_not_reuse_an_older_file(
        step, monkeypatch, tmp_path):
    """A file an EARLIER run left under the converter's output name is not
    this run's result."""
    recorder, final = step
    stale = os.path.join(FNAMES.Tmp_dir,
                         FNAMES.short_latlon(LAT, LON) + "_tmp_dsf.txt")
    with open(stale, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(DUMP)
    _dsftool(monkeypatch, dsf2text={"writes": False})

    assert OVL.build_overlay(LAT, LON) == 0

    assert recorder.named == ["overlay_tool_failed"]
    assert "wrote nothing" in recorder.detail[0]
    assert not final.exists()
