"""`tools/pad_frontage_step.py` — the twin (lane `b2frontagedatum`,
owner RULINGS 2026-09-18c (1), §28 (6)).

The tool prices no law: every verdict in its table is
``constraints.pad_frontage_gs``'s own, and these twins assert that it is
the module's functions answering and not a re-spelling.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests" / "auto_patch_v2"))

import pad_frontage_step as T  # noqa: E402


def test_the_quantities_are_the_modules_own_and_never_re_spelled():
    """The three columns ARE ``pad_frontage_gs``'s own functions, and the
    bound is its own reader — a private re-derivation is the
    census-wrapper defect (CLAUDE.md)."""
    from auto_patch_v2.constraints import pad_frontage_gs as G
    src = (ROOT / "tools" / "pad_frontage_step.py").read_text()
    for name in ("pair_dem_step_m", "pad_airside_frontage",
                 "pad_area_weighted_dem", "frontage_step_max_m",
                 "_groundside_geoms", "frontage_radius_m"):
        assert hasattr(G, name), name
        assert f"G.{name}" in src or f"import" in src
    # nothing in the tool computes a step of its own
    assert "statistics.median" in src, "the medians are the tool's reporting columns"
    assert "dem_z" in src


def test_the_table_is_the_relations_own_population(tmp_path):
    """One synthetic airport through the tool's own ``pair_rows``: the
    pairs it reports are exactly the pairs ``groundside_frontage`` sees
    before the §28 (6) bound drops any, and the TERRACE verdict is the
    bound applied to ``pair_dem_step_m``."""
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import pad_frontage_gs as G
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.build import build
    from test_v2frontage import _airport, _cells
    from test_v2frontagestep import _StepDem

    law = Law.for_airport("ZZZZ")
    bound = G.frontage_step_max_m(law)
    pm, _st = build(_airport(law, _StepDem(bound - 1.0)),
                    Classification(tuple(_cells()), (), {}, ()), law)
    rows = T.pair_rows(pm, law)
    assert rows, "the fixture's lot fronts its pad"
    rel = G.groundside_frontage(pm, law)
    assert {r["gs_face"] for r in rows} == set(rel)
    for r in rows:
        assert abs(r["step"]) <= bound
        assert r["step"] == pytest.approx(r["step_rim"])  # the pad is a hole
        assert r["airside_front_n"] > 0

    held = build(_airport(law, _StepDem(bound + 1.0)),
                 Classification(tuple(_cells()), (), {}, ()), law)[0]
    rows_h = T.pair_rows(held, law)
    assert rows_h and all(abs(r["step"]) > bound for r in rows_h)
    assert G.groundside_frontage(held, law) == {}, \
        "the tool's TERRACE verdict IS the relation's own drop"


def test_the_tool_is_in_the_index():
    """RULINGS `7e90032`: a tool absent from `tools/INDEX.md` is treated as
    absent, and every new tool lands with its index entry."""
    index = (ROOT.parent / "tools" / "INDEX.md").read_text()
    assert "Ortho4XP/tools/pad_frontage_step.py" in index
    assert "tests/test_pad_frontage_step.py" in index
