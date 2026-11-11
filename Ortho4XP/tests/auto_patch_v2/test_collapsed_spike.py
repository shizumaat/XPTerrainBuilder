"""A ZERO-WIDTH SPIKE NEVER LEAVES THE BEYOND SPLIT (measured EGKK,
2026-11-10: ``geom/collapsed_spike``; the plateau cut's densify carried an
8.8e-14 m wide fold across itself and GEOS refused the difference with
``side location conflict``, losing the airport's patch).
"""
from __future__ import annotations

from auto_patch_v2.geom.collapsed_spike import without_collapsed_spikes
from auto_patch_v2.pipeline.raised_at import raised_at
from auto_patch_v2.planar.chords import densify
from shapely.geometry import Polygon

#: the EGKK shape in the abstract: a page whose ring runs up its east edge,
#: on past a vertex standing a hair off the edge it folds back down
FOLD_V = (100.0 + 1e-13, 50.0)
SPIKED = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 40.0), FOLD_V,
                  (100.0, 90.0), (100.0, 10.0), (100.0 - 1e-13, 5.0), (0.0, 5.0)])


def _densified(g: Polygon, cap: float) -> Polygon:
    return Polygon(densify(list(g.exterior.coords)[:-1], cap, closed=True))


def test_the_fold_is_dropped_and_nothing_else_moves():
    clean = without_collapsed_spikes(SPIKED)
    assert (100.0, 90.0) not in list(clean.exterior.coords)
    assert clean.is_valid and abs(clean.area - SPIKED.area) < 1e-9
    kept = set(SPIKED.exterior.coords) - {(100.0, 90.0)}
    assert set(clean.exterior.coords) <= kept


def test_a_clean_ring_is_the_same_object():
    sq = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    assert without_collapsed_spikes(sq) is sq


def test_the_cleaned_page_densifies_valid():
    clean = without_collapsed_spikes(SPIKED)
    for cap in (3.0, 7.0, 13.0):
        assert _densified(clean, cap).is_valid


def test_a_build_failure_names_its_stage_and_regions():
    class _Region:
        ref = "dsf:pol43"

    def _stage():
        r = _Region()                         # noqa: F841 -- read by raised_at
        raise ValueError("side location conflict")

    _stage.__code__ = _stage.__code__.replace(
        co_filename="/x/auto_patch_v2/planar/pad_cut.py")
    try:
        _stage()
    except ValueError as exc:
        note = raised_at(exc)
    assert "planar/pad_cut.py" in note and "_stage" in note
    assert "dsf:pol43" in note
    assert raised_at(ValueError("outside")) == ""
