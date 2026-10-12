"""``tools/dsftool_dump_census.py`` rows (#568): one per DSF, the exit
status as DSFTool gave it, and no text left behind.  Fake ``subprocess``."""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import dsftool_dump_census as census  # noqa: E402


def _pack(tmp_path):
    folder = tmp_path / "pack" / "Earth nav data" / "+40-130"
    folder.mkdir(parents=True)
    (folder / "+47-123.dsf").write_bytes(b"crash")
    (folder / "+45-123.dsf").write_bytes(b"fine")
    (folder / "notes.txt").write_bytes(b"")
    return str(tmp_path / "pack")


def _dsftool(monkeypatch):
    def run(argv, **_kwargs):
        with open(argv[2], "rb") as handle:
            crash = handle.read() == b"crash"
        with open(argv[3], "w", encoding="utf-8") as handle:
            handle.write("" if crash else "DSF2TEXT\n")
        return subprocess.CompletedProcess(argv, -11 if crash else 0, b"",
                                           b"" if crash else b"Converted\n")
    monkeypatch.setattr(census.subprocess, "run", run)


def test_one_row_per_dsf_and_a_second_run_resumes(tmp_path, monkeypatch, capsys):
    _dsftool(monkeypatch)
    out = tmp_path / "rows.jsonl"
    keep = tmp_path / "kept"
    argv = [_pack(tmp_path), "--out", str(out), "--tool", "DSFTool",
            "--jobs", "2", "--keep-text", str(keep)]

    assert census.main(argv) == 0
    said = capsys.readouterr().out
    assert "2 dumped now (0 already" in said and "1 failed" in said

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    by_name = {os.path.basename(r["path"]): r for r in rows}
    assert sorted(by_name) == ["+45-123.dsf", "+47-123.dsf"]
    assert (by_name["+47-123.dsf"]["rc"], by_name["+47-123.dsf"]["bytes"]) == (-11, 0)
    assert (by_name["+45-123.dsf"]["rc"], by_name["+45-123.dsf"]["said"]) == (0, "Converted")
    assert os.listdir(keep) == ["+45-123.dsf.text"]

    assert census.main(argv) == 0
    assert "0 dumped now (2 already" in capsys.readouterr().out
