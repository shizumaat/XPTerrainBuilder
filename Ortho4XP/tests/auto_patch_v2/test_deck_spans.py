"""RULINGS 2026-11-18i: a pack deck lying at grade on the airport's pavement
is cut to its spans (``geom/deck_spans``, ``planar/deck_span_cut``) and the
object stage keeps only the span bands (``airport/deck_plates``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import deck_plates as dp
from auto_patch_v2.geom.deck_spans import _profile_spans, span_cut, span_pieces
from shapely.geometry import Polygon


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
    assert [s is None for _d, s, _w in seats] == [True, False, True, False, True]
    assert all(not w for _d, _s, w in seats)       # no cap stated: every band flat


def _span_member(cap):
    lat0, lon0 = 35.0, -78.0
    ml, mo = 110950.0, 91290.0

    def ll(x: float, y: float) -> tuple[float, float]:
        return lat0 + y / ml, lon0 + x / mo
    st = (ll(150.0, -5.0), ll(150.0, 5.0), ll(190.0, -5.0), ll(190.0, 5.0),
          ll(585.0, 0.0), ll(605.0, 0.0))
    return types.SimpleNamespace(
        id="o", deck_kind="flag", origin=(lat0, lon0), heading_deg=0.0, plate_stations=st,
        deck_spans=(ll(0.0, 0.0), ll(700.0, 0.0), ((150.0, 190.0), (585.0, 605.0)), cap)), \
        lambda la, lo: 100.0 + 0.01 * (lo - lon0) * mo


def test_a_kept_span_takes_its_own_grade_up_to_the_cap():
    """RULINGS 2026-11-18i (b): each kept span band is warped straight
    between its two end lines' ground (``obj8_warp.Track``), held to the
    cap; a span on level ground stays flat."""
    m, ground = _span_member(0.015)
    fp = dp.frame_plates([m], 2.0, {})
    counts: dict = {}
    seats = dp._band_seats(fp, ground, counts)
    (_d, _s, w1), (_d3, _s3, w3) = seats[1], seats[3]
    kind, ((xa, _za, da), (xb, _zb, db)) = w1[0]
    assert kind == "track" and abs(abs(xb - xa) - 40.0) < 0.5
    assert abs(abs(db - da) - 0.40) < 0.02          # 1 % over 40 m: its own grade
    assert abs(abs(w3[0][1][1][2] - w3[0][1][0][2]) - 0.20) < 0.02
    assert counts["deck_span_graded"] == 2 and "deck_span_over_cap" not in counts
    m, _g = _span_member(0.005)
    counts = {}
    seats = dp._band_seats(dp.frame_plates([m], 2.0, {}), ground, counts)
    (_xa, _za, da), (_xb, _zb, db) = seats[1][2][0][1]
    assert abs(abs(db - da) - 0.20) < 0.02          # held to 0.5 % over 40 m
    assert counts["deck_span_over_cap"] == 2
    flat = dp._band_seats(dp.frame_plates([m], 2.0, {}), lambda la, lo: 120.0, {})
    assert all(not w for _d, _s, w in flat)


def test_a_span_reads_its_ground_less_each_station_top():
    """A deck whose authored top differs between its end lines: the band's
    grade is the ground less each station's top (``Member.deck_spans``'
    station tops), so level pavement under a deck top 0.4 m lower at its
    far end grades the body 0.4 m up there, and the seat keeps the ground."""
    m, _g = _span_member(0.015)
    tops = (0.2, 0.2, -0.2, -0.2, 0.0, 0.0)
    m.deck_spans = (*m.deck_spans, tops)
    seats = dp._band_seats(dp.frame_plates([m], 2.0, {}), lambda la, lo: 120.0, {})
    (_xa, _za, da), (_xb, _zb, db) = seats[1][2][0][1]
    assert abs((db - da) - 0.40) < 0.01
    assert seats[1][1][2] == 120.0


def test_the_cap_holds_the_pavement_grade_never_the_bend():
    """Owner 2026-11-18T23:04Z (RULINGS 2026-11-18i (7), #2157 KRDU): the
    cap is the PAVEMENT's grade.  Ground rising 1 % under a deck top that
    falls 1.6 m over the 40 m band bends the body 0.4 + 1.6 = 2.0 m (5 %),
    unheld; ground rising 2 % is held to the 1.5 % cap and the bend is
    what that leaves."""
    m, ground = _span_member(0.015)
    m.deck_spans = (*m.deck_spans, (0.8, 0.8, -0.8, -0.8, 0.0, 0.0))
    counts: dict = {}
    (_xa, _za, da), (_xb, _zb, db) = dp._band_seats(
        dp.frame_plates([m], 2.0, {}), ground, counts)[1][2][0][1]
    assert abs((db - da) - 2.0) < 0.02 and "deck_span_over_cap" not in counts

    def steep(_la: float, lo: float) -> float:
        return 100.0 + 0.02 * (lo - (-78.0)) * 91290.0
    counts = {}
    (_xa, _za, da), (_xb, _zb, db) = dp._band_seats(
        dp.frame_plates([m], 2.0, {}), steep, counts)[1][2][0][1]
    assert abs((db - da) - (0.6 + 1.6)) < 0.02 and counts["deck_span_over_cap"] == 2


def test_the_graded_row_bounds_the_pavement_difference():
    """``edge_deck._graded_rows``: ``|mean z[S_B] - mean z[S_A]| <= cap *
    L``, whatever the two end lines' authored tops."""
    from auto_patch_v2.constraints.edge_deck import _graded_rows
    ends = [(((1, 0.5), (2, 0.5)), 8.7), (((3, 0.5), (4, 0.5)), 7.5)]
    lines = [((0.0, -5.0), (0.0, 5.0)), ((70.0, -5.0), (70.0, 5.0))]
    (row,) = _graded_rows("o", ends, lines, 0.015)
    assert abs(row.lo + 1.05) < 1e-9 and abs(row.hi - 1.05) < 1e-9
