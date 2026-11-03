"""DECK REDESIGN PR B (#1717; owner 2026-11-03T21:16Z Q1 "yes", Q2 "the
bridge ends need to be treated like a building pad"): the cut at a deck, the
pavement rim and the taxi deck's level.  Synthetic throughout."""
from __future__ import annotations

import dataclasses as _dc
import types

import pytest
from auto_patch_v2.constraints import deck_anchor as DA

from auto_patch_v2.model.structures import DeckAnchor, DeckBridge
from auto_patch_v2.planar import deck_bridge as DB
from shapely.geometry import LineString, Point
from shapely.geometry import box as _sbox

OID = "dsf:obj9"
RIM = 1.6


def _deck(depth=6.0):
    """An 80 m deck (end lines at x = -40 / +40) over a road along y,
    40 m along it (y -20..20), ``depth`` from its top to the frame's bottom."""
    ring = ((-40.0, -20.0), (40.0, -20.0), (40.0, 20.0), (-40.0, 20.0))
    a = tuple((-40.0, y) for y in (-15.0, 0.0, 15.0))
    b = tuple((40.0, y) for y in (-15.0, 0.0, 15.0))
    return DeckBridge(OID, "objects/deck.obj", (OID,), ring, a, b, depth, depth, 0.0, 100.0)


def _north_half(db):
    axis, _d = DB.deck_mouth(LineString([(0.0, 25.0), (0.0, 120.0)]), (0.0, -1.0), db)
    ramp = _sbox(-4.0, -10.0, 4.0, 100.0)
    return axis, ramp, ramp.buffer(RIM, join_style="mitre")


def test_a_wall_less_decks_cut_takes_the_whole_ring_to_the_bank_toes():
    """§3 (a), Q343 a: the cut takes the whole ring ``wall_gap_m`` inside
    its edge, the floor at level B out to the toe of a 1:3 bank from each
    end line (the road's own width where that is wider)."""
    db = _deck()
    axis, ramp, outer = _north_half(db)
    run = db.depth_m / 0.33
    r, o = DB.deck_cut(db, axis, ramp, outer, 0.6, bank_run=run)
    assert o.bounds[0] == pytest.approx(-39.4) and o.bounds[2] == pytest.approx(39.4)
    assert r.bounds[0] == pytest.approx(-(40.0 - run), abs=1e-6)
    assert r.bounds[2] == pytest.approx(40.0 - run, abs=1e-6)
    assert r.contains(Point(0.0, 10.0)) and r.contains(Point(0.0, 60.0))   # the road climbs on
    wide = _deck(depth=13.0)                                              # banks meet: the road
    r2, _o2 = DB.deck_cut(wide, axis, ramp, outer, 0.6, bank_run=wide.depth_m / 0.33)
    assert r2.bounds[0] == pytest.approx(-4.0) and r2.bounds[2] == pytest.approx(4.0)


def test_runway_pavement_the_deck_does_not_carry_is_a_rim():
    """§3 (b)/(c), owner Q1: the runway beyond the ring is never cut or
    banked — the cut stops at its edge and the floor ``rim_off`` short, so
    no floor vertex stands on the runway (the void is the vertical step)."""
    db = _deck()
    axis, ramp, outer = _north_half(db)
    runway = _sbox(-60.0, 40.0, 60.0, 70.0)
    r, o = DB.deck_cut(db, axis, ramp, outer, 0.6, bank_run=18.0, uncut=runway, rim_off=RIM)
    assert o.intersection(runway).area < 1e-6
    assert r.distance(runway) >= RIM - 1e-6
    assert r.intersection(o).area == pytest.approx(r.area)


def test_the_blade_mask_is_the_deck_ring_alone():
    """§3 (b): round 2's corridor-footprint term is retracted — a corridor
    reaching past the ring adds nothing to the runway's blade mask."""
    from auto_patch_v2.planar.structures import deck_cover_of
    db = _deck()
    tn = types.SimpleNamespace(id="t1", decks=(), footprint=((0.0, 0.0), (0.0, 500.0),
                                                            (10.0, 500.0)))
    assert deck_cover_of([tn], {"t1": db}).equals(DB.deck_polygon(db))


def _anchor(end, v, stations, top, note=DA.SOLVED_NOTE, pinned=False, family="taxi"):
    return DeckAnchor(OID, end, v, tuple(stations), 50.0 + top, top, top, family, "", 50.0,
                      pinned=pinned, note=note, cut="bank")


def test_a_taxi_deck_takes_the_level_the_airside_solve_built():
    """§5 (b), owner Q2: no pre-solve pin — the solved stations' one zero
    (mean of ``z − top``) is published as the anchors' level (a published
    level, never a pin); a runway deck's anchors are untouched."""
    pm = types.SimpleNamespace(deck_anchors=(
        _anchor("A", 0, (0, 1), 6.0), _anchor("B", 2, (2, 3), 6.2),
        _dc.replace(_anchor("A", 4, (4,), 7.0, note="", pinned=True, family="runway"),
                    object_id="dsf:obj10")))
    z = [106.30, 106.34, 106.52, 106.56, 120.0]
    got = DA.settle(_FakeMap(pm.deck_anchors), z)
    a, b, rw = got.deck_anchors
    zero = (0.30 + 0.34 + 0.32 + 0.36) / 4.0 + 100.0
    assert a.z_m == pytest.approx(zero + 6.0) and b.z_m == pytest.approx(zero + 6.2)
    assert not a.pinned and not b.pinned and rw == pm.deck_anchors[2]


@_dc.dataclass(frozen=True)
class _FakeMap:
    deck_anchors: tuple = ()


def test_a_derived_taxi_anchor_is_no_pin_and_a_runway_anchor_is():
    """§5 (b): ``derive`` mints no pin for a taxi deck; runway decks keep
    their pre-solve pin on the window-blind chord (owner 18:10Z)."""
    taxi = _dc.replace(_anchor("A", 0, (0,), 6.0, note="", pinned=True), family="taxi")
    run = _dc.replace(taxi, family="runway")
    assert not DA._solved_level(taxi).pinned
    assert DA._solved_level(taxi).note.startswith(DA.SOLVED_NOTE)
    assert DA._solved_level(run) == run


def test_a_deck_no_apt_dat_route_crosses_is_a_road_deck_levelled_by_the_solve():
    """Owner 2026-11-03T23:02Z / 23:07Z (KLAX ``Misc/Road_Bridge.obj``, a
    service road crossing over Sepulveda; LFPG ``H16.obj``): a deck with no
    carried runway or taxi route is a ROAD deck, never refused and never a
    taxi bridge; its top stays flush with the airside service road at both
    end lines — the solve's level there, no pre-solve pin."""
    from auto_patch_v2.planar import deck_route as DR
    ap = types.SimpleNamespace(runways=(), taxi_nodes={}, taxi_edges=())
    fam, route, ref = DR.carried_route(ap, _sbox(-20.0, -20.0, 20.0, 20.0))
    assert (fam, route, ref) == ("road", (), "")
    road = _dc.replace(_anchor("A", 0, (0, 1), 6.0, note="", pinned=True), family="road")
    assert not DA._solved_level(road).pinned
    got = DA.settle(_FakeMap((road,)), [106.3, 106.5])
    assert got.deck_anchors[0].z_m == pytest.approx(106.4)


def test_the_faces_of_a_cut_naming_a_deck_are_bridge_windows():
    """§2 row 16: ``deck_holes`` holds every deck ring and the floor and
    void faces of each cut naming a deck — an OSM bore has no footprint."""
    V = types.SimpleNamespace
    verts = {k: V(xy=xy) for k, xy in enumerate(
        [(-4.0, 20.0), (4.0, 20.0), (4.0, 80.0), (-4.0, 80.0),
         (500.0, 500.0), (510.0, 500.0), (510.0, 510.0)])}
    faces = {0: V(role="tunnel_ramp", ring=(0, 1, 2, 3)),
             1: V(role="tunnel_ramp", ring=(4, 5, 6))}
    tn = V(deck_bridge=OID, footprint=(), wall_path=((-6.0, 0.0), (6.0, 0.0), (6.0, 90.0),
                                                     (-6.0, 90.0)),
           axis=((0.0, 0.0), (0.0, 90.0)), half_width_m=4.0)
    pm = types.SimpleNamespace(decks=(_deck(),), structures=(tn,), faces=faces,
                               vertices=verts, ring_vertices=lambda ring: list(ring))
    holes = DA.deck_holes(pm)
    assert len(holes) == 2 and holes[1] == tuple(verts[k].xy for k in (0, 1, 2, 3))


def test_the_placements_co_placed_with_a_deck_seat_at_its_one_zero():
    """Owner 2026-11-03T23:21Z (EDDF ``Bridge_4_hard`` + ``_asph`` /
    ``_asph_dark``, #1663): every member of a deck's frame takes the deck's
    own plate — one zero per unit; a member another seat keeps is left."""
    from auto_patch_v2.pipeline import rebake_inputs as RI
    db = _dc.replace(_deck(), members=(OID, "dsf:obj10", "dsf:obj11"))
    plate = (6.0, [(-40.0, 0.0)], 0.0, RI.DECK_PLATE, 100.0)
    out = {OID: plate}
    RI._unit_members(out, types.SimpleNamespace(decks=(db,)), {"dsf:obj11"})
    assert out == {OID: plate, "dsf:obj10": plate}
