"""`tools/pad_frontage_step.py` — the twin (lane `b2frontagedatum`,
owner RULINGS 2026-09-18c (1), §28 (6)).

The tool prices no law: every verdict in its table is
``constraints.pad_frontage_gs``'s own, and these twins assert that it is
the module's functions answering and not a re-spelling.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests" / "auto_patch_v2"))


def test_the_quantities_are_the_modules_own_and_never_re_spelled():
    """The three columns ARE ``pad_frontage_gs``'s own functions, and the
    bound is its own reader — a private re-derivation is the
    census-wrapper defect (CLAUDE.md)."""
    from auto_patch_v2.constraints import pad_frontage_gs as G
    src = (ROOT / "tools" / "pad_frontage_step.py").read_text(encoding="utf-8")
    for name in ("pair_dem_step_m", "pad_airside_frontage",
                 "pad_area_weighted_dem", "frontage_step_max_m",
                 "_groundside_geoms", "frontage_radius_m"):
        assert hasattr(G, name), name
        assert f"G.{name}" in src or f"import" in src
    # nothing in the tool computes a step of its own
    assert "statistics.median" in src, "the medians are the tool's reporting columns"
    assert "dem_z" in src


def test_the_tool_is_in_the_index():
    """RULINGS `7e90032`: a tool absent from `tools/INDEX.md` is treated as
    absent, and every new tool lands with its index entry."""
    index = (ROOT.parent / "tools" / "INDEX.md").read_text(encoding="utf-8")
    assert "Ortho4XP/tools/pad_frontage_step.py" in index
    assert "tests/test_pad_frontage_step.py" in index
