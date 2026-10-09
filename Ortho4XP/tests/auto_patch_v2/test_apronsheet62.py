"""Spec §62 (4) R-E — AN APRON SHEET IS ONE BODY ACROSS ITS HOLES (issue #492;
owner RULINGS 2026-10-08c (4) / 09c / 09d (1): a pad takes the level of the
pavement it stands in, and the apron law holds across the whole sheet;
``constraints/apron.apron_within_shape``).

The shape it stands for: one apron sheet carrying a row of terminal pads as
holes, 6 m apart.  The within-shape law paired vertices of ONE ring only, so
no row joined one hole rim to the next and each pad was seated alone — 6-8 m
steps between pads 6 m apart.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v2frontage import (HALF_W, RUN_LEN, Y0, _built, _rect,  # noqa: E402
                             _verts)

from auto_patch_v2.classify.roles import Cell  # noqa: E402
from auto_patch_v2.constraints.apron import STATS, apron_within_shape  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.solve.design import hard_rulings  # noqa: E402
from auto_patch_v2.solve.design_roles import ruling_head  # noqa: E402

#: three pads in a row on one sheet: A and B 6 m apart, B taller than its
#: neighbours so every straight line from A to C crosses B
PAD_A = _rect(-50.0, 190.0, -3.0, 240.0)
PAD_B = _rect(3.0, 180.0, 20.0, 250.0)
PAD_C = _rect(26.0, 190.0, 70.0, 240.0)


def _cells(holes=True):
    pads = (PAD_A, PAD_B, PAD_C)
    out = [Cell(0, "runway", "09/27",
                _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                (), 3, "D", "airside", "runway", {}),
           Cell(1, "apron", "sheet", _rect(-260.0, Y0, 260.0, 300.0),
                pads if holes else (), None, None, "airside", "apron", {})]
    if holes:
        out += [Cell(2 + i, "building", f"pad{n}", ring, (), None, None,
                     "airside", "pad", {}) for i, (n, ring) in enumerate(zip("ABC", pads))]
    return out


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cross(rows):
    return [r for r in rows if "across the rings of one face" in r.source.ruling]


def test_two_hole_rims_of_one_sheet_share_a_hard_apron_row(law):
    """A hole rim pairs with the next hole rim and with the outer ring under
    the apron's ring-edge head — HARD, and the head the pair graph reads."""
    pm, airport = _built(law, _cells())
    rows = _cross(apron_within_shape(pm, law, airport))
    assert rows and STATS["apron_within_shape"]["cross_ring_pairs"] > 0
    assert {ruling_head(r) for r in rows} <= hard_rulings(law) | {
        "common.roles.apron ring edge"} and any(
        ruling_head(r) in hard_rulings(law) for r in rows)
    a, b = _verts(pm, "padA"), _verts(pm, "padB")
    sheet = _verts(pm, "sheet")
    feet = [{v for v in (getattr(r, "a", None), getattr(r, "b", None)) if v is not None}
            for r in rows]
    assert any(f & a and f & b for f in feet), "hole rim to hole rim"
    assert any(f & a and f & (sheet - a - b - _verts(pm, "padC")) for f in feet), (
        "hole rim to the outer ring")


def test_no_row_crosses_a_third_hole(law):
    """The face cover is the chords' own: a line from A's rim to C's rim
    runs through B and is no path across the pavement."""
    pm, airport = _built(law, _cells())
    a, c = _verts(pm, "padA"), _verts(pm, "padC")
    for r in _cross(apron_within_shape(pm, law, airport)):
        feet = {getattr(r, "a", None), getattr(r, "b", None)}
        assert not (feet & a and feet & c), r


def test_a_sheet_without_holes_mints_nothing_new(law):
    pm, airport = _built(law, _cells(holes=False))
    assert _cross(apron_within_shape(pm, law, airport)) == []
    assert STATS["apron_within_shape"]["cross_ring_pairs"] == 0
