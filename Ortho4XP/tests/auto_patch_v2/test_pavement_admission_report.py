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


def test_cli_renders_every_subcommand():
    for sub in ("refused", "diff", "sheets"):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "pavement_admission_report.py"),
                            sub, "--help"], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "--json" in r.stdout


def test_piece_overlap_is_the_area_of_piece_on_standing_cells():
    """THE §60 BAR's reader: a piece beside a runway cell reads 0, a piece
    lapping it reads the lap."""
    from shapely.geometry import box
    standing = {"runway": [box(0, 0, 100, 45)], "apron": [box(0, 100, 50, 150)], "taxi": []}
    assert T.piece_overlap([box(0, 45, 100, 100)], standing) == {
        "runway": 0.0, "apron": 0.0, "taxi": 0.0}
    got = T.piece_overlap([box(0, 40, 100, 110)], standing)
    assert got["runway"] == 500.0 and got["apron"] == 500.0
    assert T.piece_overlap([], standing)["runway"] == 0.0


def test_a_refused_hard_surface_def_names_its_reason():
    assert T.why_refused("lib/airport/lines/safety_area_red.pol", "paint") == "decorative namespace"
    assert T.why_refused("Ground/Poly/Grass3.pol", "shoulders") == "terrain word in the name"
    assert T.why_refused("ground_marks/mark_dir_amarillo.pol", "paint") == "paint layer group"
    assert T.why_refused("g/apron_signs.pol", None) == "paint/sign word, file names no layer"
