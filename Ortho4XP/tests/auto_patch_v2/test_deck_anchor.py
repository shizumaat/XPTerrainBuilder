"""THE DECK END LINE IS AN ANCHOR (spec ``deck-end-anchors-20261103``; owner
RULINGS 2026-11-03c, Q2 as answered 2026-11-03T16:20Z: seam > CIFP
threshold > deck anchor).  Synthetic: a 1,200 m runway on a 0.6 % ground,
a hard deck 48 m across it (end lines on two ridge stations)."""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from auto_patch_v2.constraints import deck_anchor as DA
from auto_patch_v2.constraints import runway_chord as RC
from auto_patch_v2.constraints.runway_profile import runway_crown
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Pin
from auto_patch_v2.model.structures import Deck, Tunnel
from tests.auto_patch_v2.test_v2chord import RUNWAY, _airport

OID = "dsf:obj7"


class _Slope:
    provenance = {"synthetic": "0.6 % along x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.006 * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def site(law):
    return _airport(law, [RUNWAY], [], _Slope(), thresholds=(700.0 - 3.6, 700.0 + 3.6))


def _tunnel(x0=-24.0, x1=24.0, depth_a=7.0, depth_b=7.0, deck=OID, **kw):
    ring = ((x0, -30.0), (x1, -30.0), (x1, 30.0), (x0, 30.0))
    st_a = tuple((x0, y) for y in (-22.5, 0.0, 22.5))
    st_b = tuple((x1, y) for y in (-22.5, 0.0, 22.5))
    seats = ((deck or "dsf:edge", st_a, depth_a), (deck or "dsf:edge", st_b, depth_b))
    base = dict(id="t1", ways=(1,), axis=((0.0, -60.0), (0.0, 60.0)), half_width_m=8.0,
                mouth_dem_z=700.0, mouth_z=693.0, top_s=40.0, climb_from_s=0.0,
                ramp_refs=(), wall_ref="", wall_path=(), edge_seats=seats,
                deck_bridge=deck, deck_ring=ring if deck else ())
    base.update(kw)
    return Tunnel(**base)


def _with(pm, *tunnels):
    return _dc.replace(pm, structures=tuple(tunnels))


def _anchored(site, law, *tunnels):
    ap, pm, _st = site
    pm = RC.with_deck_anchors(_with(pm, *tunnels), law, ap)
    return ap, pm, {a.end: a for a in pm.deck_anchors}


def test_a_flat_deck_on_a_sloping_runway_is_anchored_at_the_profile_mean(site, law):
    """Q1 a: the deck never tilts — both ends at ½(p_A + p_B), one hard pin
    each on the ridge where the runway leaves the deck."""
    ap, pm, got = _anchored(site, law, _tunnel())
    a, b = got["A"], got["B"]
    assert a.family == b.family == "runway" and a.ref == "09/27"
    assert a.pinned and b.pinned and not a.yielding and not b.yielding
    assert pm.vertices[a.v].xy == pytest.approx((-24.0, 0.0))
    assert pm.vertices[b.v].xy == pytest.approx((24.0, 0.0))
    assert a.z_m == pytest.approx(b.z_m)
    assert a.z_m == pytest.approx(0.5 * (a.profile_z_m + b.profile_z_m))
    pins = DA.deck_anchor_pins(pm, law, ap)
    assert {(p.v, round(p.z, 6)) for p in pins} == {(a.v, a.z_m), (b.v, b.z_m)}
    assert all(isinstance(p, Pin) and p.source.ruling == DA.RULING for p in pins)


def test_a_sloping_deck_keeps_its_authored_rise(site, law):
    """r = top_B − top_A: z_A = ½(p_A + p_B − r), z_B = z_A + r."""
    _ap, _pm, got = _anchored(site, law, _tunnel(depth_b=7.144))      # 0.3 % over 48 m
    a, b = got["A"], got["B"]
    assert b.z_m - a.z_m == pytest.approx(0.144)
    assert a.z_m == pytest.approx(0.5 * (a.profile_z_m + b.profile_z_m - 0.144))
    assert b.rise_m == pytest.approx(0.144)


def test_the_chord_passes_through_the_anchors_and_the_crown_stands_down(site, law):
    """§4: the anchors are knots of the runway's target; Q3 a: no crown
    floor over the run into the deck."""
    ap, pm, got = _anchored(site, law, _tunnel(x0=-60.0, x1=60.0, depth_b=7.36))
    targets = RC.runway_chord_targets(pm, law, ap)
    for a in got.values():
        assert targets[a.v] == pytest.approx(a.z_m, abs=1e-6)
    near = {r.terms[0][0] for r in runway_crown(pm, law, ap)
            if any(v in (got["A"].v, got["B"].v) for v, _c in r.terms[1:])}
    assert not near
    plain = {r.terms[0][0] for r in runway_crown(_dc.replace(pm, deck_anchors=()), law, ap)
             if any(v in (got["A"].v, got["B"].v) for v, _c in r.terms[1:])}
    assert plain


def test_a_threshold_on_the_deck_governs_it(site, law):
    """Q2 as answered (LPMA): a CIFP threshold on the deck sets the deck top
    at its station to the CIFP value; the other end follows the rise."""
    _ap, _pm, got = _anchored(site, law, _tunnel(x0=576.0, x1=612.0, depth_b=7.036))
    a = got["A"]
    assert "governs" in a.note
    # the threshold at x = 600 is 2/3 of the way from A (576) to B (612)
    top_at = 7.0 + (600.0 - 576.0) / 36.0 * 0.036
    assert a.z_m - 7.0 + top_at == pytest.approx(700.0 + 3.6, abs=1e-6)


def test_a_seam_pin_inside_the_deck_makes_the_anchor_yield(site, law):
    """Q2: the tile seam is senior to everything — an anchor within its
    reach yields; a seam pin ON the anchor vertex takes it (no pin)."""
    ap, pm, got = _anchored(site, law, _tunnel())
    v_mid = min(pm.vertices, key=lambda q: math.dist(pm.vertices[q].xy, (0.0, 0.0)))
    seamed = _dc.replace(_with(pm, _tunnel()), seam_vertices=frozenset({v_mid}))
    ys = {a.end: a for a in RC.with_deck_anchors(seamed, law, ap).deck_anchors}
    assert ys["A"].yielding and ys["B"].yielding and "seam" in ys["A"].note
    assert all(p.source.ruling.startswith(DA.YIELD_HEAD)
               for p in DA.deck_anchor_pins(_dc.replace(pm, deck_anchors=tuple(ys.values())),
                                            law, ap))
    on = _dc.replace(_with(pm, _tunnel()), seam_vertices=frozenset({got["A"].v}))
    held = {a.end: a for a in RC.with_deck_anchors(on, law, ap).deck_anchors}
    assert not held["A"].pinned and "seam" in held["A"].note
    assert DA.YIELD_HEAD in law.tables.emit.design.yielding_pin_rulings


def test_no_pack_hard_deck_mints_no_anchor(site, law):
    """§2.0 twins (i)-(iii): an OSM tunnel, an OSM bridge deck and an edge-
    wall-only pack bridge mint nothing — the map is returned untouched."""
    ap, pm, _st = site
    osm_tunnel = _tunnel(deck="", edge_seats=())
    osm_bridge = _tunnel(deck="", edge_seats=(),
                         decks=(Deck("osm:9", 9, 0.0, 10.0, ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0)),
                                       "dem"),))
    edge_only = _tunnel(deck="", edge_back=((-24.0, 30.0), (24.0, 30.0)))
    for tn in (osm_tunnel, osm_bridge, edge_only):
        m = _with(pm, tn)
        assert RC.with_deck_anchors(m, law, ap) is m
        assert DA.derive(m, law, ap) == ()
    # (iv) the same geometry under a flagged hard deck: two anchor pins
    _ap, m, got = _anchored(site, law, _tunnel())
    assert len(DA.deck_anchor_pins(m, law, ap)) == 2


def test_the_census_reads_a_station_off_the_one_zero():
    """§6 ``deck_end_flush``: a station 0.05 m off the deck's one zero is a
    row; a held anchor off its level is a row; a yielding one is not."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from check_grade_lib.families.deck_end_flush import check_deck_end_flush
    from check_grade_lib.rows import Way
    nodes = {1: (1.0, 1.0), 2: (1.0, 1.1), 3: (2.0, 1.0), 4: (2.0, 1.1)}
    w = Way("9", "runway", "09/27", "runway", [1, 2, 3, 4], [100.0, 100.0, 100.1, 100.0], {})
    recs = [{"object": OID, "end": "A", "pinned": True, "yielding": False, "at": [1.0, 1.0],
             "z_m": 100.0, "top_y": 7.0, "stations": [[1.0, 1.0], [1.0, 1.1]]},
            {"object": OID, "end": "B", "pinned": True, "yielding": True, "at": [2.0, 1.0],
             "z_m": 99.0, "top_y": 7.0, "stations": [[2.0, 1.0], [2.0, 1.1]]}]
    rows = check_deck_end_flush(recs, nodes, [w])
    assert [(r.lat, r.lon) for r in rows] == [(2.0, 1.0)]
    assert check_deck_end_flush(None, nodes, [w]) == []


def test_a_slab_keeps_its_ground_and_the_cut_stops_at_its_edges(tmp_path):
    """Owner 2026-11-03T16:39:23Z: a deck aircraft cannot drive UNDER (a
    slab: the frame stops short of the road, nothing below the plate) keeps
    the terrain under it — the mouth stands at the deck's edge and the cut
    takes nothing inside the ring; a deck reaching the road is unchanged."""
    from auto_patch_v2.planar import deck_bridge as DBR
    from shapely.geometry import LineString
    from shapely.geometry import box as _sbox
    from tests.auto_patch_v2 import test_deck_bridge1671 as T
    (slab,), _n = T._slab_read(tmp_path, T.AIRPORT)
    assert slab.slab
    axis = LineString([(0.0, 23.0), (0.0, 120.0)])
    moved, _d = DBR.deck_mouth(axis, (0.0, -1.0), slab)
    assert abs(moved.coords[0][1] - 20.0) < 0.5        # the slab's edge, not its midline
    ramp = _sbox(-4.0, -30.0, 4.0, 100.0)
    r2, o2 = DBR.deck_cut(slab, moved, ramp, ramp.buffer(1.6, join_style="mitre"), 0.6)
    assert r2.intersection(slab.polygon).area < 1e-6 and o2.intersection(slab.polygon).area < 1e-6
    # 16:56Z: no wall at the slab's edge — the floor stops a 1:3 bank short of it
    r3, _o3 = DBR.deck_cut(slab, moved, ramp, ramp.buffer(1.6, join_style="mitre"), 0.6,
                           bank_run=6.0)
    assert r3.distance(slab.polygon) > 5.9
    # 16:53Z: the trench beside the slab is the object's width, wall to wall
    lo, hi = DBR.project_span(slab.ring, DBR.across_dir(slab))
    u0, u1 = DBR.project_span(list(o2.exterior.coords), DBR.across_dir(slab))
    assert abs(u0 - (lo + 0.6)) < 1e-6 and abs(u1 - (hi - 0.6)) < 1e-6
    (tmp_path / "w").mkdir()
    assert not T._bridge(tmp_path / "w").slab
