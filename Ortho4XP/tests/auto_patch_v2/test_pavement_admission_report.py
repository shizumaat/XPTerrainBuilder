"""``tools/pavement_admission_report.py`` — the source-family join and the
CLI surface (the report itself reads captures; lanes ``conc333`` /
``surface337``, RULINGS 2026-10-04d (2) / 04e (1))."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import pavement_admission_report as T                    # noqa: E402


def test_source_family_joins_refs_whose_dump_index_shifts():
    assert T._family("dsf:pol50#12") == T._family("dsf:pol211") == "dsf"
    assert T._family("dsf:objpav92") == "dsf"
    assert T._family("pav6") == "apt"
    assert T._family("route12") == T._family("route3") == "route"
    assert T._family("small_roads:-7811#3") == "small_roads"
    assert T._family("16R/34L") == "16R/34L"


def test_cli_renders_both_subcommands():
    for sub in ("refused", "diff"):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "pavement_admission_report.py"),
                            sub, "--help"], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "--json" in r.stdout
