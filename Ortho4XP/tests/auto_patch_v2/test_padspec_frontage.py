"""Spec §56 (11) R-W — THE FRONTAGE IS NOT SIMPLIFIED (issue #452): a
rule-2 outline standing on airside ground is PINNED through rule 2b
(``geom.outline_pin.Frontage``).  The pad's shared vertices with an airside
face are its weld rows (02ah); a close or a chord there re-populates them
and the apron and the taxiways follow (measured by intervention, KCLT and
KASE).  The owner's straight chords are the groundside and road sides.

Synthetic twins only: a pad crenellated on both faces keeps rule 2's ring
on the airside one and closes the other; a re-entrant whose mouth is half
airside is not filled; a chord is never laid INTO the frontage; the mint
and the census pin against the same ground; WKB-identical at 1 and 4
workers."""
from __future__ import annotations

import concurrent.futures as _cf

from shapely import wkb
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from auto_patch_v2.geom.cluster_outline import (_parts, cluster_outlines,
                                                simplified_outline)
from auto_patch_v2.geom.outline_pin import Frontage
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline

from test_v2padcluster import _AP, _Cl, _sq  # noqa: E402

LAW = pad_outline(Law.for_airport("ZZZZ"))

#: a 202 x 36 m body with 34 towers (4 m wide, 2 m crenels) on BOTH long
#: faces; the apron's rim runs along the tips of the lower ones
_TEETH = [(6.0 * k, 6.0 * k + 4.0) for k in range(34)]
_PAD = unary_union([box(0.0, 0.0, 202.0, 36.0)]
                   + [box(a, 36.0, b, 40.0) for a, b in _TEETH]
                   + [box(a, -4.0, b, 0.0) for a, b in _TEETH])
_APRON = box(-50.0, -80.0, 250.0, -4.0)


def _verts(g) -> set:
    return {(round(x, 6), round(y, 6)) for p in _parts(g)
            for r in (p.exterior, *p.interiors) for x, y in r.coords}


def _pinned(g, airside):
    return simplified_outline(
        g, LAW.close_m, LAW.chord_m, LAW.hole_min_m2,
        Frontage.near(g, airside, LAW.pin_m, LAW.close_m + LAW.chord_m))


def test_the_pin_distance_is_the_identity_spacing():
    law = Law.for_airport("ZZZZ")
    assert LAW.pin_m == law.tables.emit.identity.min_distinct_spacing_m > 0.0


def test_the_airside_face_keeps_rule_2s_ring_and_the_groundside_closes():
    free = simplified_outline(_PAD, LAW.close_m, LAW.chord_m, LAW.hole_min_m2)
    got = _pinned(_PAD, _APRON)
    assert len(_verts(free)) == 4                 # no frontage: four corners
    low = {v for v in _verts(_PAD) if v[1] <= 0.0}
    assert len(low) == 4 * len(_TEETH)
    # the airside ring is vertex-identical to rule 2
    assert {v for v in _verts(got) if v[1] <= 0.0} == low
    # the groundside closes and straightens as before
    assert {v for v in _verts(got) if v[1] > 0.0} \
        == {v for v in _verts(free) if v[1] > 0.0} == {(0.0, 40.0), (202.0, 40.0)}
    assert got.is_valid and got.geom_type == "Polygon"
    # nothing was taken or left within the pin distance of the apron
    zone = _APRON.buffer(LAW.pin_m)
    assert got.intersection(zone).symmetric_difference(
        _PAD.intersection(zone)).area < 1e-6


def test_a_re_entrant_whose_mouth_is_half_airside_is_not_filled():
    pad = box(0.0, 0.0, 100.0, 40.0).difference(box(40.0, 0.0, 45.0, 10.0))
    free = simplified_outline(pad, LAW.close_m, LAW.chord_m, LAW.hole_min_m2)
    assert free.area > pad.area + 45.0            # a 5 m mouth fills
    half = box(-50.0, -50.0, 42.5, 0.0)           # the rim ends mid-mouth
    got = _pinned(pad, half)
    assert abs(got.area - pad.area) < 1e-6
    assert _verts(got) == _verts(pad)
    # the same bay with the airside 20 m along the face fills as before,
    # and the frontage vertices beside it stand
    away = _pinned(pad, box(-50.0, -50.0, 20.0, 0.0))
    assert abs(away.area - free.area) < 1e-6
    assert {(0.0, 0.0), (40.0, 0.0)} <= _verts(away)


def test_no_chord_is_laid_into_the_frontage():
    """Neither end of the run is on the frontage, but the chord between
    them would cut the apron's corner: the run stands as drawn."""
    pad = Polygon([(0.0, 0.0), (50.0, 0.9), (100.0, 0.0), (100.0, 40.0),
                   (0.0, 40.0)])
    free = simplified_outline(pad, LAW.close_m, LAW.chord_m, LAW.hole_min_m2)
    assert (50.0, 0.9) not in _verts(free)
    tip = Polygon([(50.0, 0.35), (60.0, -30.0), (40.0, -30.0)])
    front = Frontage.near(pad, tip, LAW.pin_m, LAW.close_m + LAW.chord_m)
    assert not front.on(pad)                      # 0.55 m off: not on it
    got = simplified_outline(pad, LAW.close_m, LAW.chord_m, LAW.hole_min_m2,
                             front)
    assert (50.0, 0.9) in _verts(got)
    assert not got.intersects(tip)


def test_a_light_well_on_the_frontage_stays_open():
    pad = box(0.0, 0.0, 100.0, 40.0).difference(box(40.0, 10.0, 50.0, 20.0))
    free = simplified_outline(pad, LAW.close_m, LAW.chord_m, LAW.hole_min_m2)
    assert not free.interiors                     # 100 m2: a light well
    got = _pinned(pad, box(44.0, 14.0, 46.0, 16.0))   # apron inside it
    assert len(got.interiors) == 1


def test_no_airside_near_is_the_unpinned_outline_byte_for_byte():
    far = box(1000.0, 1000.0, 1100.0, 1100.0)
    assert Frontage.near(_PAD, far, LAW.pin_m, 4.0) is None
    assert Frontage.near(_PAD, _APRON, 0.0, 4.0) is None
    assert wkb.dumps(_pinned(_PAD, far)) == wkb.dumps(
        simplified_outline(_PAD, LAW.close_m, LAW.chord_m, LAW.hole_min_m2))


def _wkb_pinned(args):
    pad, airside = args
    return wkb.dumps(_pinned(pad, airside))


def test_wkb_identical_at_1_and_4_workers():
    jobs = [(_PAD, _APRON),
            (_PAD, box(-50.0, -80.0, 90.0, -4.0)),
            (box(0.0, 0.0, 100.0, 40.0).difference(box(40.0, 0.0, 45.0, 10.0)),
             box(-50.0, -50.0, 42.5, 0.0))]
    serial = [_wkb_pinned(j) for j in jobs]
    for workers in (1, 4):
        with _cf.ProcessPoolExecutor(max_workers=workers) as ex:
            assert list(ex.map(_wkb_pinned, jobs)) == serial


def _cluster():
    return _Cl("unit:0#0", [_sq(0.0, 0.0, 202.0, 36.0)]
               + [_sq(a, 36.0, b, 40.0) for a, b in _TEETH]
               + [_sq(a, -4.0, b, 0.0) for a, b in _TEETH], area=8000.0)


def test_rule_2b_pins_the_frontage_and_counts_it():
    cl = _cluster()
    xy = _AP([cl]).frame.entry()
    base, _c0 = cluster_outlines([cl], xy, 0.5)
    free, c1 = cluster_outlines([cl], xy, 0.5, outline=LAW)
    air = Polygon([xy(lo, la) for la, lo in _sq(-50.0, -80.0, 250.0, -4.0)])
    got, c2 = cluster_outlines([cl], xy, 0.5, outline=LAW, frontage=air)
    assert c1["outline_frontage"] == 0 and c1["outline_vertices_out"] == 4
    assert c2["outline_frontage"] == 1
    assert c2["outline_fills_refused"] >= len(_TEETH) - 1
    assert c2["outline_vertices_pinned"] >= 4 * len(_TEETH)
    assert c2["outline_vertices_in"] > c2["outline_vertices_out"] \
        > c1["outline_vertices_out"]
    zone = air.buffer(LAW.pin_m)
    assert got[0][2].intersection(zone).symmetric_difference(
        base[0][2].intersection(zone)).area < 1e-3


def test_the_mint_and_the_census_pin_against_the_same_ground():
    """The census re-draws the outline (``cluster_polys``); it takes the
    frontage the MINT recorded, so the two rings are one."""
    from auto_patch_v2.classify.evidence import _cluster_pads
    from auto_patch_v2.geom.outline_pin import minted_frontage
    from auto_patch_v2.constraints import cluster_pad as cp
    law = Law.for_airport("ZZZZ")
    cl = _cluster()
    ap = _AP([cl])
    xy = ap.frame.entry()
    air = Polygon([xy(lo, la) for la, lo in _sq(-50.0, -80.0, 250.0, -4.0)])
    minted = _cluster_pads(ap, law, air)
    assert minted_frontage(ap) is air
    assert minted_frontage(object(), "none") == "none"
    assert len(minted) == 1 and len(_verts(minted[0])) > 100
    st = law.tables.structures.placement
    census = cp.cluster_polys(ap, float(st.cluster_pad_min_m2),
                              float(st.footprint_touch_m), None,
                              float(st.post_bridge_gap_m), None,
                              pad_outline(law), minted_frontage(ap))
    assert [wkb.dumps(g) for _i, _c, g in census] == [wkb.dumps(minted[0])]


# ── the near-road absorption re-closes with the same pin (§56 (2) 5) ──

def _absorb_scene(road_x1: float):
    from auto_patch_v2.classify.roles import Cell

    def cell(i, role, ref, poly, side):
        return Cell(i, role, ref, tuple(poly.exterior.coords)[:-1], (), None,
                    None, side, role, {})
    return [cell(0, "building", "building1", box(0, 0, 60, 40), "airside"),
            cell(1, "service_road", "route7",
                 box(5, 41.1, road_x1, 47.1), "groundside"),
            cell(2, "apron", "pav1", box(60, -20, 120, 60), "airside")]


def test_a_road_is_absorbed_off_the_frontage_and_the_weld_vertices_stand():
    from auto_patch_v2.classify import road_absorb as ra
    from auto_patch_v2.law import load_default
    law = load_default()
    out, absorbed = ra.absorb_near_roads(_absorb_scene(55.0), law,
                                         pad_outline(law))
    assert absorbed == {"building1": ["route7"]}
    pad = Polygon(out[0].ring, out[0].holes)
    # the pad's face on the apron is as it was: the same two weld vertices
    assert {(60.0, 0.0), (60.0, 40.0)} <= _verts(pad)
    assert pad.intersection(box(59.5, -1, 60.5, 61)).symmetric_difference(
        box(0, 0, 60, 40).intersection(box(59.5, -1, 60.5, 61))).area < 1e-6


def test_a_road_whose_stand_off_opens_on_the_apron_keeps_its_shape():
    """The strip between the pad and this road runs out ONTO the apron's
    rim: filling it would put new pad ground — new weld rows — on the
    airside frontage, so it is not filled and the road stays a road."""
    from auto_patch_v2.classify import road_absorb as ra
    from auto_patch_v2.law import load_default
    law = load_default()
    cells = _absorb_scene(60.0)
    out, absorbed = ra.absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {} and out == cells
    assert ("route7", "building1", ra.KEPT_PIECES) in ra.ROADS_KEPT
