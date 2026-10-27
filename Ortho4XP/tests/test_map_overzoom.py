"""Twin of ``Tests/SceneryKitTests/MapOverzoomTests.swift`` (#1315).

Both run ``fixtures/map_overzoom_cases.json`` -- the ancestor tile and
sub-square that draw a view tile past the source's ceiling, the zoom
badge, and the server's "no imagery here" tile the maps draw a coarser
ancestor in place of (#1540) -- so the Qt and Mac maps overzoom alike.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Imagery_Utils as IMG  # noqa: E402
import O4_Map_Overzoom as OVERZOOM  # noqa: E402
import pytest  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), "fixtures",
                       "map_overzoom_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


def test_view_ceiling():
    assert OVERZOOM.MAX_VIEW_ZL == CASES["max_view_zl"]


@pytest.mark.parametrize("case", CASES["ancestor"])
def test_ancestor(case):
    got = OVERZOOM.ancestor(case["z"], case["x"], case["y"], case["max_z"])
    assert [got.z, got.x, got.y] == case["ancestor"]
    assert [got.sub_x, got.sub_y, got.sub_size] == case["sub"]


@pytest.mark.parametrize("case", CASES["ancestor"])
def test_ancestor_covers_the_view_tile(case):
    """The sub-square, scaled back to the view zoom, is the view tile."""
    got = OVERZOOM.ancestor(case["z"], case["x"], case["y"], case["max_z"])
    span = 2 ** (case["z"] - got.z)
    assert got.z == min(case["z"], case["max_z"])
    assert (got.x + got.sub_x) * span == case["x"]
    assert (got.y + got.sub_y) * span == case["y"]
    assert got.sub_size * span == 1


@pytest.mark.parametrize("case", CASES["badge"])
def test_badge(case):
    if case["max_zl"] is not None:
        assert OVERZOOM.overzoom_factor(
            case["view_zl"], case["max_zl"]) == case["factor"]
    assert OVERZOOM.badge_text(
        case["view_zl"], case["source"], case["max_zl"]) == case["text"]


@pytest.mark.parametrize("case", CASES["placeholder"])
def test_placeholder_tile(case):
    """The engine's download test is the rule the Mac map's
    ``MapOverzoom.isPlaceholderTile`` twins (#1540)."""
    assert IMG.is_placeholder_tile(case["url"], case["headers"]) is case["placeholder"]
