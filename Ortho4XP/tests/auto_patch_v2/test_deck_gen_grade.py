"""Twins of ``constraints/deck_gen_grade`` (owner 2026-11-19T16:59Z /
17:02Z): our own bridge is graded (no rigid rise) unless it carries a
runway, and each end line keeps the minimum clearance plus the slab over
the highest lidar point of its covered road -- a lower bound only, read
only where the survey shows the road in its cut."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.deck_gen_grade import clearance_rows, graded
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.model.structures import GENERATED_WITNESS

LAW = load_default()


def _deck(family="taxi", witness=GENERATED_WITNESS, deck_z=123.0):
    return types.SimpleNamespace(
        witness=witness, family=family, deck_z=deck_z,
        ring=((0, 0), (40, 0), (40, 30), (0, 30)),
        covered=(("-1", (("highway", "unclassified"),), ((20, -10), (20, 40))),))


class _Dem:
    def __init__(self, z):
        self.zz = z

    def z(self, x, y):
        return self.zz + 0.01 * y


def _ends(deck):
    end = types.SimpleNamespace
    return [end(deck=deck, terms=((1, 1.0), (2, 1.0)), line=((0, 0), (0, 30)), depth=6.0),
            end(deck=deck, terms=((3, 2.0),), line=((40, 0), (40, 30)), depth=6.0)]


def test_graded_is_ours_and_not_a_runway():
    assert graded(_deck())
    assert not graded(_deck(family="runway"))
    assert not graded(_deck(witness="hard_deck"))


def test_clearance_is_a_lower_bound_over_the_highest_road_point():
    d = _deck()
    rows = clearance_rows("o4gen_x", _ends(d), types.SimpleNamespace(dem=_Dem(115.0)),
                          LAW, "head", "gen")
    need = 115.0 + 0.30 + float(LAW.tables.structures.bridge.clearance_minimum_m) \
        + float(LAW.tables.structures.deck_gen.thickness_m)
    assert len(rows) == 2
    for r in rows:
        assert r.hi is None and abs(r.lo - need) < 1e-6
        assert abs(sum(c for _v, c in r.terms) - 1.0) < 1e-9


def test_no_clearance_row_where_the_survey_shows_no_cut():
    d = _deck(deck_z=120.0)
    assert clearance_rows("o4gen_x", _ends(d), types.SimpleNamespace(dem=_Dem(115.0)),
                          LAW, "head", "gen") == []
