"""Spec §56 (1) — THE SIMPLIFIED BUILDING OUTLINE (owner RULINGS 2026-10-07a
(6), 07b (4); issue #452): ``geom.cluster_outline.simplified_outline`` and
rule 2b of ``cluster_outlines``, with the law read ONCE
(``law.tables.pad_outline``) by the mint and the census alike.

Synthetic twins only (bar 7 of §56 (8)): a crenellated rectangle closes to
its four corners, a 5 m bay fills and a 7 m bay stays, a 150 m2 light well
fills and a 250 m2 courtyard stays, a crescent is not hulled, the round
close keeps a thin wing the mitred close severs, and the output is
WKB-identical at any worker count."""
from __future__ import annotations

import concurrent.futures as _cf
import dataclasses as _dc

from shapely import wkb
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from auto_patch_v2.geom.cluster_outline import (_parts, cluster_outlines,
                                                simplified_outline)
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import PadOutline, pad_outline

from test_v2padcluster import _AP, _Cl, _sq  # noqa: E402

LAW = pad_outline(Law.for_airport("ZZZZ"))


def _simple(g):
    return simplified_outline(g, LAW.close_m, LAW.chord_m, LAW.hole_min_m2)


def _nverts(g) -> int:
    return sum(len(p.exterior.coords) - 1
               + sum(len(h.coords) - 1 for h in p.interiors)
               for p in _parts(g))


def test_the_law_values_are_the_specs():
    """§56 (1) law table: 3.0 / 1.0 / 200.0 in ``[building_pad]``."""
    assert (LAW.close_m, LAW.chord_m, LAW.hole_min_m2) == (3.0, 1.0, 200.0)


def test_a_crenellated_rectangle_closes_to_its_four_corners():
    """30 notches 2 m wide and 4 m deep along one 200 x 40 m face: every
    mouth is under 2 x 3 m, so all fill, and the straightened outline is
    the rectangle — 4 vertices, the footprint contained exactly."""
    body = box(0.0, 0.0, 200.0, 40.0)
    notches = [box(5.0 + 6.0 * k, 36.0, 7.0 + 6.0 * k, 40.0) for k in range(30)]
    cren = body.difference(unary_union(notches))
    assert _nverts(cren) > 100
    got = _simple(cren)
    assert len(_parts(got)) == 1
    assert _nverts(got) == 4, got.wkt
    assert got.equals(body)
    assert got.covers(cren)


def test_a_5_m_bay_fills_and_a_7_m_bay_stays():
    """The close fills a re-entrant whose mouth is narrower than 6 m; a
    wider bay (a loading dock, the gap between two piers) is a real
    concavity and stays."""
    body = box(0.0, 0.0, 100.0, 60.0)
    for mouth, fills in ((5.0, True), (7.0, False)):
        bay = box(50.0 - mouth / 2.0, 40.0, 50.0 + mouth / 2.0, 60.0)
        got = _simple(body.difference(bay))
        left = bay.difference(got).area
        if fills:
            # the whole depth fills; a true closing leaves only a mouth
            # dimple C - sqrt(C^2 - (w/2)^2) deep (1.34 m here; under the
            # 1 m chord, so straightened away, for a mouth under 4.47 m)
            dimple = LAW.close_m - (LAW.close_m ** 2 - (mouth / 2.0) ** 2) ** 0.5
            assert left < 0.05 * bay.area, (mouth, left)
            assert bay.difference(got).bounds[1] >= 60.0 - dimple - 1e-6
        else:
            # the bay stands; only its two inner corners take the
            # closing's fillet (radius 3 m, straightened to a chord)
            assert left > 0.9 * bay.area, (mouth, left)


def test_a_light_well_fills_and_a_courtyard_stays():
    """A hole under ``outline_hole_min_m2`` (200 m2) is filled; a courtyard
    at or over it stays a hole (``model/islands`` courtyard)."""
    body = box(0.0, 0.0, 120.0, 80.0)
    well = box(20.0, 20.0, 32.5, 32.0)            # 150 m2
    yard = box(60.0, 20.0, 76.0, 35.625)          # 250 m2
    assert abs(well.area - 150.0) < 1e-9 and abs(yard.area - 250.0) < 1e-9
    got = _simple(body.difference(well).difference(yard))
    (p,) = _parts(got)
    assert len(p.interiors) == 1
    hole = Polygon(p.interiors[0])
    assert hole.intersects(yard) and not hole.intersects(well)
    assert 200.0 <= hole.area <= 250.0
    assert got.covers(well)


def test_a_crescent_is_followed_not_hulled():
    """§56 (7): the convex hull was REFUTED (+1,167,519 m2 at OTHH, the
    whole apron); the outline follows a curved building within +2 %."""
    cres = Point(0.0, 0.0).buffer(100.0, quad_segs=32).difference(
        Point(40.0, 0.0).buffer(85.0, quad_segs=32))
    got = _simple(cres)
    assert len(_parts(got)) == 1
    assert got.area <= 1.02 * cres.area, (got.area, cres.area)
    assert got.area < 0.5 * cres.convex_hull.area
    assert _nverts(got) < _nverts(cres)


# A body with a 1 m wing at a shallow angle off another (found by a seeded
# search; coordinates rounded to the millimetre).  The mitred close cuts it
# into two pieces; the round close keeps the one building.
_WING = Polygon([
    (63.536, 33.128), (64.957, 30.486), (36.702, 15.286), (38.074, 6.327),
    (35.108, 5.873), (33.616, 15.616), (33.025, 16.715), (33.416, 16.925),
    (32.331, 24.012), (28.911, 26.318), (31.410, 30.025), (28.117, 51.526),
    (31.082, 51.980), (33.883, 33.693), (35.041, 35.411), (41.675, 30.939),
    (35.669, 22.031), (36.220, 18.434)])


def test_round_joins_keep_one_piece_where_mitred_joins_sever_a_wing():
    """§56 (1) 1: round, not mitred — the mitred form was probed and
    REFUTED (OTHH ``unit:28#8/0`` fell into 3 pieces)."""
    assert _WING.is_valid and len(_parts(_WING)) == 1
    mitred = _WING.buffer(3.0, join_style=2, mitre_limit=5.0).buffer(
        -3.0, join_style=2, mitre_limit=5.0)
    assert len(_parts(mitred)) >= 2
    got = _simple(_WING)
    assert len(_parts(got)) == 1
    # the closing contains its input; the straightening moves no point
    # more than the chord tolerance
    assert _WING.difference(got.buffer(LAW.chord_m)).area < 1e-6


def test_zero_disarms_every_step():
    cren = box(0.0, 0.0, 60.0, 30.0).difference(box(10.0, 28.0, 12.0, 30.0))
    assert simplified_outline(cren, 0.0, 0.0, 0.0).equals(cren)


def _wkbs(polys):
    return [wkb.dumps(_simple(p)) for p in polys]


def test_wkb_identical_at_any_worker_count():
    """§56 (1) 7: one GEOS operation chain on one polygon — the output is
    byte-identical whether one worker or four compute it."""
    polys = [_WING, Point(0.0, 0.0).buffer(50.0).difference(box(-5, 40, 5, 60)),
             box(0, 0, 200, 40).difference(unary_union(
                 [box(5.0 + 6.0 * k, 36.0, 7.0 + 6.0 * k, 40.0)
                  for k in range(30)]))]
    serial = _wkbs(polys)
    for workers in (1, 4):
        with _cf.ProcessPoolExecutor(max_workers=workers) as ex:
            chunks = list(ex.map(_wkbs, [[p] for p in polys]))
        assert [c[0] for c in chunks] == serial


# ── rule 2b inside ``cluster_outlines``, and the one reading of the law ──

def _crenellated_cluster(cid="unit:0#0"):
    # 34 towers 4 m wide over a 202 x 36 m body, 2 m crenels between them
    rings = [_sq(0.0, 0.0, 202.0, 36.0)] + [
        _sq(6.0 * k, 36.0, 6.0 * k + 4.0, 40.0) for k in range(34)]
    return _Cl(cid, rings, area=8000.0)


def test_rule_2b_simplifies_the_cluster_outline_and_counts_it():
    cl = _crenellated_cluster()
    xy = _AP([cl]).frame.entry()
    base, c0 = cluster_outlines([cl], xy, 0.5)
    got, c1 = cluster_outlines([cl], xy, 0.5, outline=LAW)
    assert c0["outline_simplified"] == 0
    assert c1["outline_simplified"] == 1
    assert c1["outline_vertices_in"] == _nverts(base[0][2]) > 100
    assert c1["outline_vertices_out"] == _nverts(got[0][2]) == 4
    assert got[0][0] == base[0][0] == "unit:0#0"
    assert got[0][2].covers(base[0][2])


def test_the_pieces_the_close_joined_are_named():
    """§56 (1) 9: the pad count moves, and every change is NAMED — two
    halls of one cluster 4 m apart are two pads under rule 2 and ONE under
    2b, which says which ids it took (``outline_joined_from``)."""
    cl = _Cl("unit:0#0", [_sq(0.0, 0.0, 60.0, 40.0),
                          _sq(64.0, 0.0, 124.0, 40.0)], area=4800.0)
    xy = _AP([cl]).frame.entry()
    base, _c = cluster_outlines([cl], xy, 0.5)
    stats: dict = {}
    got, c1 = cluster_outlines([cl], xy, 0.5, outline=LAW, stats=stats)
    assert [i for i, _c, _g in base] == ["unit:0#0/0", "unit:0#0/1"]
    assert [i for i, _c, _g in got] == ["unit:0#0"]
    assert c1["still_in_pieces"] == 0
    row = stats["unit:0#0"]
    assert row["outline_joined_from"] == ["unit:0#0/0", "unit:0#0/1"]
    assert row["outline_simplified_from"] == 8
    assert row["outline_vertices"] == _nverts(got[0][2])
    # §56 (1) 10: the growth is NAMED and sums to the added area
    g = row["outline_growth_m2"]
    assert g["join"] == 2400.0 and g["well"] == g["thin_kept"] == 0.0
    assert g["close"] > 150.0 and abs(g["close"] + g["chord"] - 160.0) <= 0.2
    # a cluster the close leaves alone names nothing
    solo: dict = {}
    cluster_outlines([_crenellated_cluster()], xy, 0.5, outline=LAW, stats=solo)
    assert solo["unit:0#0"]["outline_joined_from"] == []
    assert solo["unit:0#0"]["outline_vertices"] == 4
    sg = solo["unit:0#0"]["outline_growth_m2"]
    assert sg["join"] == sg["well"] == sg["thin_kept"] == 0.0
    assert sg["close"] + sg["chord"] > 0.0


def test_the_mint_and_the_census_draw_the_same_outline():
    """The census-wrapper defect in geometry: ``constraints/cluster_pad``
    re-reads the ONE derivation, so it must take the SAME outline law the
    mint took (``law.tables.pad_outline``) or ``pad_cluster_mismatch``
    would be measuring the drift."""
    from auto_patch_v2.classify.evidence import _cluster_pads
    from auto_patch_v2.constraints import cluster_pad as cp
    law = Law.for_airport("ZZZZ")
    ap = _AP([_crenellated_cluster()])
    minted = _cluster_pads(ap, law)
    assert len(minted) == 1 and _nverts(minted[0]) == 4
    st = law.tables.structures.placement
    census = cp.cluster_polys(ap, float(st.cluster_pad_min_m2),
                              float(st.footprint_touch_m), None,
                              float(st.post_bridge_gap_m), None,
                              pad_outline(law))
    assert [wkb.dumps(g) for _i, _c, g in census] == [wkb.dumps(minted[0])]


def test_disarmed_law_is_todays_outline():
    """``0`` disarms (the measurement arm): the pad is rule 2's outline."""
    law = Law.for_airport("ZZZZ")
    bp = _dc.replace(law.tables.structures.building_pad, outline_close_m=0.0,
                     outline_chord_m=0.0, outline_hole_min_m2=0.0)
    off = _dc.replace(law, tables=_dc.replace(
        law.tables, structures=_dc.replace(law.tables.structures,
                                           building_pad=bp)))
    from auto_patch_v2.classify.evidence import _cluster_pads
    ap = _AP([_crenellated_cluster()])
    (g,) = _cluster_pads(ap, off)
    assert _nverts(g) > 100
