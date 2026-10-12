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
        with open(argv[3], "w", encoding="utf-8", newline="") as handle:
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


def test_two_tools_dumps_are_compared_by_row_class(tmp_path, capsys):
    """``--diff-text`` (#587): what a replacement DSFTool changes."""
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    body = "PROPERTY sim/overlay 1\nOBJECT_DEF a.obj\nOBJECT 0 1.0 2.0 3.0\n"
    for folder, file_row, pools, heights in (
            (old, "# file: /a/x.dsf", 16, "-82.0"), (new, "# file: /b/x.dsf", 12, "-22.0")):
        (folder / "same.dsf.text").write_text(file_row + "\n" + body, encoding="utf-8", newline="\n")
        (folder / "moved.dsf.text").write_text(
            f"{file_row}\n# pool 64: # obj_pools found: {pools}\n"
            f"HEIGHTS 0.03125 {heights}\n{body}", encoding="utf-8", newline="\n")
    (old / "shorter.dsf.text").write_text(body, encoding="utf-8", newline="\n")
    (new / "shorter.dsf.text").write_text(body + "OBJECT 0 4.0 5.0 6.0\n", encoding="utf-8", newline="\n")
    (new / "crasher.dsf.text").write_text(body, encoding="utf-8", newline="\n")
    report_path = tmp_path / "report.json"

    assert census.main(["--diff-text", str(old), str(new),
                        "--json", str(report_path)]) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert (report["identical"], report["differ"]) == (1, 2)
    assert (report["only_old"], report["only_new"]) == ([], ["crasher.dsf.text"])
    assert {k: (v["rows"], v["files"]) for k, v in report["classes"].items()} == {
        "# pool": (1, ["moved.dsf.text"]), "HEIGHTS": (1, ["moved.dsf.text"]),
        "LINE COUNT": (1, ["shorter.dsf.text"])}
    assert "1 dumps identical, 2 differ; only in OLD 0, only in NEW 1" in capsys.readouterr().out
