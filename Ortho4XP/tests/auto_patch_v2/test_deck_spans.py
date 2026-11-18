"""RULINGS 2026-11-18i: a pack deck lying at grade on the airport's pavement
is cut to its spans (``geom/deck_spans``, ``planar/deck_span_cut``) and the
object stage keeps only the span bands (``airport/deck_plates``)."""
from __future__ import annotations

import types

from shapely.geometry import Polygon

from auto_patch_v2.airport import deck_plates as dp
from auto_patch_v2.geom.deck_spans import _profile_spans, span_cut, span_pieces


def _ground(x: float, _y: float) -> float:
    """A 1.5 % grade with two roads cut 7 m under it (x 150-190, 585-605)."""
    z = 113.0 + 0.015 * x
    if 150.0 <= x <= 190.0 or 585.0 <= x <= 605.0:
        z -= 7.0
    return z


def test_two_spans_on_a_grade():
    deck = Polygon([(0, -10), (700, -10), (700, 10), (0, 10)])
    cut = span_cut(deck, _ground, drop_m=3.0, rise_grade=0.03)
    assert cut is not None and len(cut.spans) == 2
    (a1, b1), (a2, b2) = cut.spans
    assert 140 <= a1 <= 150 and 190 <= b1 <= 200
    assert 575 <= a2 <= 585 and 605 <= b2 <= 615
    runs = cut.at_grade()
    assert len(runs) == 3 and runs[1][1] - runs[1][0] > 300
    parts = span_pieces(deck, cut)
    assert len(parts) == 2
    assert all(abs(p.bounds[3] - p.bounds[1] - 20.0) < 1e-6 for p in parts)


def test_all_bridge_has_one_span_and_no_long_at_grade():
    deck = Polygon([(140, -10), (200, -10), (200, 10), (140, 10)])
    cut = span_cut(deck, _ground, drop_m=3.0, rise_grade=0.03)
    assert cut is not None and len(cut.spans) == 1
    width = deck.area / cut.length
    assert all(s1 - s0 <= width for s0, s1 in cut.at_grade())


def test_flat_ground_has_no_span():
    assert _profile_spans([0, 2, 4, 6, 8], [10, 10.03, 10.06, 10.09, 10.12], 3.0, 0.03) == []


def test_span_frame_keeps_span_bands_and_drops_the_rest():
    lat0, lon0 = 35.0, -78.0
    ml, mo = 110950.0, 91290.0

    def ll(x: float, y: float) -> tuple[float, float]:
        return lat0 + y / ml, lon0 + x / mo
    st = (ll(150.0, 0.0), ll(190.0, 0.0), ll(585.0, 0.0), ll(605.0, 0.0))
    m = types.SimpleNamespace(id="o", deck_kind="flag", origin=(lat0, lon0), heading_deg=0.0,
                              plate_stations=st,
                              deck_spans=(ll(0.0, 0.0), ll(700.0, 0.0),
                                          ((150.0, 190.0), (585.0, 605.0))))
    counts: dict = {}
    fp = dp.frame_plates([m], 2.0, counts)
    assert fp is not None and counts["deck_span_frames"] == 1
    assert fp.keep == (False, True, False, True, False)
    assert fp.band_of_ll(*ll(100.0, 0.0)) == 0
    assert fp.band_of_ll(*ll(170.0, 0.0)) == 1
    assert fp.band_of_ll(*ll(400.0, 0.0)) == 2
    assert fp.band_of_ll(*ll(595.0, 0.0)) == 3
    seats = dp._band_seats(fp, lambda la, lo: 120.0)
    assert [s is None for _d, s in seats] == [True, False, True, False, True]
