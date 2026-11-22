"""Airside-first generated bridges (``docs/specs/airside-first-bridges-
spec.md``; owner RULINGS 2026-11-19s): the deck top is the no-bridge
surface, flush by construction; one deck per taxiway at its letter's TSA;
the carve never fixes or frees an airside level it should not; the lip
runs on the sides only.  Headless, synthetic."""
from __future__ import annotations

import math
import types

import pytest
from auto_patch_v2.geom.coons_patch import CoonsPatch, edge_profiles
from auto_patch_v2.geom.coons_patch import _profile_at as profile_at
from shapely.geometry import Polygon


def _patch():
    # a 10 x 20 parallelogram: u along the route (y), w across it (x)
    a = ((0.0, 10.0), (0.5, 10.2), (1.0, 10.0))       # end A, crowned
    b = ((0.0, 11.0), (0.5, 11.2), (1.0, 11.0))       # end B, 1 m higher
    s0 = ((0.0, 10.0), (0.5, 10.6), (1.0, 11.0))      # a vertical curve
    s1 = ((0.0, 10.0), (1.0, 11.0))
    return CoonsPatch((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), a, b, s0, s1)


def test_coons_patch_is_exact_on_every_edge():
    p = _patch()
    for t in (0.0, 0.25, 0.5, 0.8, 1.0):
        assert p.z(10.0 * t, 0.0) == pytest.approx(profile_at(p.a, t))
        assert p.z(10.0 * t, 20.0) == pytest.approx(profile_at(p.b, t))
    for s in (0.0, 0.3, 0.5, 1.0):
        assert p.z(0.0, 20.0 * s) == pytest.approx(profile_at(p.s0, s))
        assert p.z(10.0, 20.0 * s) == pytest.approx(profile_at(p.s1, s))
    # the crown carries across the span
    assert p.z(5.0, 10.0) > p.z(9.0, 10.0)
    assert p.low() == pytest.approx(10.0)


def test_edge_profiles_reads_samples_on_the_edges_only():
    smp = [(0.0, 0.0, 1.0), (10.0, 0.0, 1.2), (5.0, 0.02, 1.4),     # end A
           (0.0, 20.0, 2.0), (10.0, 20.0, 2.2),                      # end B
           (5.0, 10.0, 99.0)]                                        # interior: ignored
    p = edge_profiles((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), smp, tol=0.05)
    assert p is not None
    assert p.z(5.0, 0.0) == pytest.approx(1.4)
    assert p.z(5.0, 10.0) < 50.0
    assert edge_profiles((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), smp[3:5]) is None


def _law(**kw):
    from auto_patch_v2.law.deck_gen_schema import DeckGenLaw
    g = DeckGenLaw(**kw)
    return types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(deck_gen=g)))


def route_decks(piece, road_dir, airport, law, pave_at=None, cover=None, avoid=None):
    """``(ring, note)`` per route deck of one piece, parted."""
    from auto_patch_v2.planar.deck_width import parted, rings, route_specs
    return rings(parted(route_specs(piece, road_dir, airport, law, pave_at, cover, avoid), law))


def test_one_deck_per_taxiway_at_its_tsa_width():
    nodes = {k: types.SimpleNamespace(xy=xy) for k, xy in
             {1: (0.0, -100.0), 2: (0.0, 100.0), 3: (90.0, -100.0), 4: (90.0, 100.0)}.items()}
    def edge(a, b, c, name):
        return types.SimpleNamespace(a=a, b=b, name=name, is_runway=False, width_class=c)
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[edge(1, 2, "C", "A"),
                                                                  edge(3, 4, "E", "B")])
    # the pavement over a road running along x: one piece spanning both taxiways
    piece = Polygon([(-40, -15), (130, -15), (130, 15), (-40, 15)])
    got = route_decks(piece, (1.0, 0.0), airport, _law())
    assert len(got) == 2
    # RULINGS 2026-11-21c: the FAA taxiway safety area of each letter
    # (C -> ADG III 36.0 m, E -> ADG V 65.2 m)
    widths = sorted(round(r.bounds[2] - r.bounds[0], 6) for r, _n in got)
    assert widths == [36.0, 65.2]
    for r, _n in got:
        assert r.bounds[1] == pytest.approx(-15.0) and r.bounds[3] == pytest.approx(15.0)
    # the gap between them stays open
    (r0, _), (r1, _) = got
    assert r0.intersection(r1).area == 0.0


def test_lip_runs_on_the_sides_only():
    from auto_patch_v2.airport.deck_structure import end_edges
    ring = Polygon([(-5, -10), (5, -10), (5, 10), (-5, 10)])     # route along z
    # end lines read far off the ring (KBNA 1.0.565): the ends are still ends
    ends = end_edges(ring, [[(-50.0, 0.0), (-49.0, 0.0)]], 4.0, 25.0)
    assert len(ends) == 2
    assert all(abs(a[1] - b[1]) < 1e-9 for a, b in ends)


def test_the_carve_fixes_unmapped_airside_and_frees_ground(monkeypatch):
    from auto_patch_v2.constraints import deck_floor_follow as dff
    from auto_patch_v2.constraints.edge_floor import DECK_FLOOR
    from auto_patch_v2.model import platform
    from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
    from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 20.0), (0.0, 20.0))
    db = DeckBridge("o4gen_t", "objects/o4_generated/deck_t.obj", (), ring,
                    ((0.0, 0.0), (10.0, 0.0)), ((0.0, 20.0), (10.0, 20.0)), 0.0, 0.0,
                    -6.0, 100.0, witness=GENERATED_WITNESS, floor_min_m=6.0)
    def V(x, y):
        return types.SimpleNamespace(xy=(x, y), incident_faces=())
    # stage 1: the filled ring's corners and a crowned end line
    s1pm = types.SimpleNamespace(vertices={0: V(0, 0), 1: V(5, 0), 2: V(10, 0),
                                           3: V(0, 20), 4: V(10, 20)})
    stage1 = types.SimpleNamespace(pm=s1pm, solved={0: 100.0, 1: 100.2, 2: 100.0,
                                                    3: 101.0, 4: 101.0})
    # the full map: 10 an end-line station stage 1 lacks (airside), 11 the
    # bank's crest on a side the join fixed (ground), 12 a floor vertex
    pm = types.SimpleNamespace(decks=(db,), vertices={10: V(2.5, 0.0), 11: V(0.0, 10.0),
                                                      12: V(5.0, 10.0)}, faces={},
                               structures=(types.SimpleNamespace(id="tn", deck_bridge="o4gen_t"),))
    monkeypatch.setattr(platform, "stage_air_vertices", lambda _pm, _law: {10})
    cs = ConstraintSet.from_rows([Pin(12, 99.0, Source("structures", DECK_FLOOR, ("tn",)))])
    from auto_patch_v2.law import Law
    cs2, s2 = dff.floor_follow_rewrite(pm, cs, {11: 100.5}, stage1, law=Law.load())
    assert s2.fixed == {10: pytest.approx(100.1)}
    assert s2.free == frozenset({11})
    assert cs2.pins[0].z == pytest.approx(100.0 - 6.0)
    keys = s2.stage_two({"stage2_free": {7}})
    assert keys["stage2_free"] == frozenset({7, 11})
    assert set(keys["generated_tops"]["o4gen_t"]) == {"o", "u", "w", "a", "b", "s0", "s1"}


def test_one_taxiway_of_many_edges_is_one_deck_and_its_ends_are_read():
    from auto_patch_v2.planar.deck_width import route_ends
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.5, 0.0)),
             3: types.SimpleNamespace(xy=(6.0, 100.0))}
    def edge(a, b):
        return types.SimpleNamespace(a=a, b=b, name="L", is_runway=False, width_class="C")
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[edge(1, 2), edge(2, 3)])
    piece = Polygon([(-40, -15), (40, -15), (40, 15), (-40, 15)])
    got = route_decks(piece, (1.0, 0.0), airport, _law())
    assert len(got) == 1
    ring = got[0][0]
    # a deck inside a wider pavement: its ends are its own edges along the road
    wide = Polygon([(-60, -60), (60, -60), (60, 60), (-60, 60)])
    ends = route_ends(ring, (1.0, 0.0), lambda xy: "taxiway" if wide.contains(
        Polygon([(xy[0] - .1, xy[1] - .1), (xy[0] + .1, xy[1] - .1), (xy[0] + .1, xy[1] + .1)]))
        else None, lambda r: r == "taxiway", 2.0, lambda x, y: (y, x))
    assert ends is not None
    for e in ends:
        assert len({round(lat, 6) for lat, _lon in e}) == 1     # one edge each, along the road


def test_the_roads_cover_never_widens_the_deck():
    """RULINGS 2026-11-20w / 21c ("the drawn deck equals this width"): a road
    that runs on under pavement past the deck's side (lane lcarve2's cover)
    never widens the deck across its route -- the letter's TSA holds."""
    from shapely.geometry import LineString

    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.0, 100.0))}
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[types.SimpleNamespace(
        a=1, b=2, name="A", is_runway=False, width_class="C")])
    piece = Polygon([(-40, -15), (40, -15), (40, 15), (-40, 15)])
    # the road runs along x and stays covered to x = 40 (the apron past the
    # piece); the deck is 36 m wide (C: ADG III's TSA)
    cover = LineString([(-10.0, 0.0), (40.0, 0.0)]).buffer(5.0, cap_style="flat")
    (ring, note), = route_decks(piece, (1.0, 0.0), airport, _law(), None,
                                cover.difference(Polygon([(-18, -15), (18, -15),
                                                          (18, 15), (-18, 15)])))
    assert ring.bounds[2] == pytest.approx(18.0)
    assert ring.bounds[0] == pytest.approx(-18.0)
    assert "whole cover" not in note
    (plain, _n), = route_decks(piece, (1.0, 0.0), airport, _law())
    assert plain.bounds[2] == pytest.approx(18.0)


def test_the_stage_two_airside_is_held_at_the_solve_without_the_cut():
    """lane lcarve2 (RULINGS 2026-11-19s (1)): every airside vertex stage 2
    solves is a constant at the shadow's level -- the set with the pins and
    flats as before the cut, every other row kept; a fixed one stays."""
    import dataclasses

    from auto_patch_v2.solve.stage_shadow import held_levels
    cs = types.SimpleNamespace(pins=("cut pin",), flats=("cut flat",), bands=("door band",))
    seen: dict = {}

    def solve(cs_x, fixed):
        seen.update(pins=cs_x.pins, flats=cs_x.flats, bands=cs_x.bands, fixed=dict(fixed))
        return types.SimpleNamespace(z=[10.0, 11.0, 12.0, 13.0]), None
    shadow = {"pins": ("pin",), "flats": (), "fixed": {0: 10.0}, "free": frozenset({1}),
              "hold": {1, 2, 3}}
    rep: dict = {}

    @dataclasses.dataclass(frozen=True)
    class CS:
        pins: tuple
        flats: tuple
        bands: tuple
    got = held_levels(shadow, CS(cs.pins, cs.flats, cs.bands), {1: 5.0, 3: 7.0},
                      {3: 7.5}, lambda c, free: c, solve, rep)
    assert seen["pins"] == ("pin",) and seen["flats"] == () and seen["bands"] == ("door band",)
    assert seen["fixed"] == {0: 10.0, 3: 7.0}            # stage 1's, less the freed
    assert got == {3: 7.5, 1: 11.0, 2: 12.0}             # held; the fixed one kept
    assert rep["stage2_shadow"]["held"] == 2


def test_the_deck_axis_runs_along_its_route_whatever_its_seats_say():
    """RULINGS 2026-11-19s (8) (b): the axis is the carried route's direction
    -- seats read on a side edge (a deck at a junction) never turn it, and
    the object frame reads the route before a dropped centreline."""
    from auto_patch_v2.constraints.deck_floor_follow import _deck_frame
    from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
    ring = ((0.0, 0.0), (50.0, 0.0), (50.0, 30.0), (0.0, 30.0))     # 50 along x, 30 across
    side = ((0.0, 0.0), (50.0, 0.0))                                # seats on a SIDE edge
    db = DeckBridge("o4gen_t", "x.obj", (), ring, side, ((0.0, 30.0), (50.0, 30.0)), 0.0, 0.0,
                    -6.0, 100.0, witness=GENERATED_WITNESS, floor_min_m=6.0,
                    route=((-100.0, 15.0), (150.0, 15.0)))           # the taxiway runs along x
    o, u, w = _deck_frame(db)
    assert abs(u[1]) < 1e-9 and abs(abs(u[0]) - 50.0) < 1e-9
    from auto_patch_v2.airport import deck_objects as dob
    ll = [[x * 1e-5, y * 1e-5] for x, y in ring]
    rec = {"ring": ll, "seats_a": [ll[0], ll[3]], "seats_b": [ll[1], ll[2]],
           "route": [[-100e-5, 15e-5], [150e-5, 15e-5]]}
    centre = types.SimpleNamespace(line=1, light=0, points=[(40e-5, -50e-5), (40e-5, 80e-5)])
    fr = dob._deck_frame(rec, [centre])
    assert abs(fr.heading_deg % 180.0 - 90.0) < 1.0     # along the route, not the centreline


def test_the_ground_past_each_deck_end_lands_at_its_level():
    """RULINGS 2026-11-19s (8) (d): past an end line, across the deck's
    width, the ground stands at the end's level for ``end_landing_m``, then
    falls at the bank's slope; beside the deck (over the cut) it asks nothing."""
    from auto_patch_v2.constraints.deck_carve import _landing
    flat = ((0.0, 100.0), (1.0, 100.0))
    top = CoonsPatch((0.0, 0.0), (0.0, 50.0), (40.0, 0.0), flat, ((0.0, 101.0), (1.0, 101.0)),
                     ((0.0, 100.0), (1.0, 101.0)), ((0.0, 100.0), (1.0, 101.0)))
    rings = [(None, top, 94.0)]
    assert _landing(rings, (20.0, -2.0), 0.5, 3.0) == pytest.approx(100.0)
    assert _landing(rings, (20.0, -5.0), 0.5, 3.0) == pytest.approx(99.0)
    assert _landing(rings, (20.0, 52.0), 0.5, 3.0) == pytest.approx(101.0)
    assert _landing(rings, (-4.0, -2.0), 0.5, 3.0) == pytest.approx(98.0)    # its corner
    assert _landing(rings, (-5.0, 20.0), 0.5, 3.0) == -math.inf     # beside: the cut
    assert _landing(rings, (20.0, 25.0), 0.5, 3.0) == -math.inf     # under the deck


def test_neighbouring_decks_give_up_their_shoulders_to_stay_apart():
    """RULINGS 2026-11-19s (3) (b), kept by 21c: two C taxiways 36 m apart
    (their 36 m TSA decks touching): both narrow on their FACING sides to
    ``parallel_gap_m`` apart, never inside their paved band (20f)."""
    from auto_patch_v2.planar.deck_width import parted, rings, route_specs
    nodes = {k: types.SimpleNamespace(xy=xy) for k, xy in
             {1: (0.0, -100.0), 2: (0.0, 100.0), 3: (36.0, -100.0), 4: (36.0, 100.0)}.items()}
    def edge(a, b, name):
        return types.SimpleNamespace(a=a, b=b, name=name, is_runway=False, width_class="C")
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[edge(1, 2, "A"),
                                                                  edge(3, 4, "B")])
    law = _law()
    left = route_specs(Polygon([(-30, -15), (18, -15), (18, 15), (-30, 15)]), (1.0, 0.0),
                       airport, law)
    right = route_specs(Polygon([(18, -15), (70, -15), (70, 15), (18, 15)]), (1.0, 0.0),
                        airport, law)
    (ra, _), (rb, _) = rings(parted(left + right, law))
    gap = float(law.tables.structures.deck_gen.parallel_gap_m)
    assert ra.distance(rb) == pytest.approx(gap, abs=1.0)
    # owner RULINGS 2026-11-20f: only the FACING sides give way; the outer
    # sides keep their shoulders, and never inside the paved band
    assert ra.bounds[0] == pytest.approx(-18.0) and rb.bounds[2] == pytest.approx(54.0)
    assert ra.bounds[2] >= 12.5 - 1e-6 and rb.bounds[0] <= 36.0 - 12.5 + 1e-6


def test_a_deck_gives_up_shoulder_over_a_structure_beside_it():
    """A shoulder never stands over a corridor or pack frame its taxiway
    does not (KRDU ``o4gen_c18ee4b1``: a tunnel ramp 7.9 m under it)."""
    from auto_patch_v2.planar.deck_width import parted, rings, route_specs
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.0, 100.0))}
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[types.SimpleNamespace(
        a=1, b=2, name="A", is_runway=False, width_class="C")])
    law = _law()
    piece = Polygon([(-40, -15), (40, -15), (40, 15), (-40, 15)])
    ramp = Polygon([(15, 5), (40, 5), (40, 30), (15, 30)])          # beside the taxiway
    road = Polygon([(-200, -3), (200, -3), (200, 3), (-200, 3)])    # its own road's corridor
    (ring, note), = rings(parted(route_specs(piece, (1.0, 0.0), airport, law), law,
                                 ramp.union(road)))
    assert ring.bounds[2] <= 15.0 + 1e-6 and ring.bounds[0] == pytest.approx(-ring.bounds[2])
    assert ring.bounds[2] >= 12.5 - 1e-6 and "narrowed" in note


def test_the_ground_past_a_road_decks_end_lands_at_the_taxiway_level():
    """RULINGS 2026-11-19s (8) (d): a road deck spanning a deck's cut ends at
    the taxiway deck's end level, and the ground past it lands there."""
    from auto_patch_v2.constraints.deck_carve import _road_landing
    ends = [((60.0, -25.0), (0.0, -1.0), 5.0, 100.0)]          # its end A, outward -y
    assert _road_landing(ends, (60.0, -27.0), 0.5, 3.0) == pytest.approx(100.0)
    assert _road_landing(ends, (60.0, -30.0), 0.5, 3.0) == pytest.approx(99.0)
    assert _road_landing(ends, (68.0, -26.0), 0.5, 3.0) == pytest.approx(98.5)   # beside
    assert _road_landing(ends, (60.0, -20.0), 0.5, 3.0) == -math.inf             # its span


def test_the_deck_end_landing_is_a_flush_constant_up_or_down():
    """Lane lcross20 (KRDU 1.0.567 ``o4gen_2011dcf6``: a vertex 1 m past end
    A left free, pulled 5.9 m down): within ``end_landing_m`` past an end
    and the deck's width (its snap at the corners) the ground IS the end's
    level; under the deck, beside it or farther out, no flat landing."""
    from auto_patch_v2.constraints.deck_carve import _flat_landing
    flat = ((0.0, 100.0), (1.0, 100.0))
    top = CoonsPatch((0.0, 0.0), (0.0, 50.0), (40.0, 0.0), flat, ((0.0, 101.0), (1.0, 101.0)),
                     ((0.0, 100.0), (1.0, 101.0)), ((0.0, 100.0), (1.0, 101.0)))
    rings = [(None, top, 94.0)]
    assert _flat_landing(rings, (20.0, -1.0), 3.0) == pytest.approx(100.0)
    assert _flat_landing(rings, (20.0, 52.0), 3.0) == pytest.approx(101.0)
    assert _flat_landing(rings, (40.3, -1.0), 3.0) == pytest.approx(100.0)   # the corner
    assert _flat_landing(rings, (20.0, -5.0), 3.0) is None                   # past it
    assert _flat_landing(rings, (45.0, -1.0), 3.0) is None                   # beside
    assert _flat_landing(rings, (20.0, 25.0), 3.0) is None                   # under


def test_a_rider_widens_the_deck_on_its_own_side_only():
    """Owner 2026-11-20T15:17Z (item 9): a service road riding a taxiway
    deck widens it on the road's side; the other side keeps the standard
    shoulder -- the taxiway stands off-centre on the deck."""
    from auto_patch_v2.law.tables import load_default
    from auto_patch_v2.planar.deck_gen_pairs import riders
    piece = Polygon([(-38, -20), (38, -20), (38, 20), (-38, 20)])   # 76 m: E twice
    rider = {"id": "-1", "over": ["r"], "axis_xy": [(44.0, -30.0), (44.0, 30.0)],
             "half_m": 3.5}
    grown, ids, _n = riders(piece, piece, {"r"}, [rider], load_default())
    assert ids == ("-1",)
    x0, _y0, x1, _y1 = grown.bounds
    assert x0 == pytest.approx(-38.0) and x1 == pytest.approx(44.0 + 3.5 + 1.5)


def test_a_skewed_deck_is_squared_on_its_own_axes_never_widened():
    """KRDU o4gen_476a2069 (32.5 m note, 51.3 m drawn): the route deck's
    parallelogram squared again on another route's direction grew; on its
    own axes (``deck_generated._own_axes``) it comes back unchanged."""
    import math as _m

    from auto_patch_v2.planar.deck_generated import _own_axes, _straight_sided
    u, w = (1.0, 0.0), (_m.cos(_m.radians(60)), _m.sin(_m.radians(60)))
    quad = Polygon([(a * u[0] + b * w[0], a * u[1] + b * w[1])
                    for a, b in ((-16.0, -20.0), (16.0, -20.0), (16.0, 20.0), (-16.0, 20.0))])
    road = (_m.cos(_m.radians(5)), _m.sin(_m.radians(5)))          # the mean road read
    axes = _own_axes(quad, road)
    assert axes is not None
    again = _straight_sided(quad, *axes)
    assert again.symmetric_difference(quad).area < 1e-6
    # the old squaring, square to the road: larger
    assert _straight_sided(quad, road).area > quad.area + 50.0


def _krdu_route(letter="E"):
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.0, 100.0))}
    return types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[types.SimpleNamespace(
        a=1, b=2, name="K", is_runway=False, width_class=letter)])


@pytest.mark.parametrize("letter, tsa", [("A", 14.9), ("B", 24.1), ("C", 36.0), ("D", 52.1),
                                         ("E", 65.2), ("F", 79.9)])
def test_the_deck_is_the_faa_tsa_of_its_letter(letter, tsa):
    """Owner RULINGS 2026-11-21c: FAA AC 150/5300-13B Chg 1 Table 4-1 TSA of
    the route's ADG (A -> I ... F -> VI), centred on its centreline."""
    from auto_patch_v2.planar.deck_width import rings, route_specs
    piece = Polygon([(-60, -15), (60, -15), (60, 15), (-60, 15)])
    (r, note), = rings(route_specs(piece, (1.0, 0.0), _krdu_route(letter), _law()))
    assert round(r.bounds[2] - r.bounds[0], 1) == tsa
    assert r.bounds[0] == pytest.approx(-r.bounds[2])
    assert "safety area" in note


def test_a_route_of_no_letter_takes_the_airport_common():
    from auto_patch_v2.planar.deck_width import rings, route_specs
    ap = _krdu_route(None)
    nodes = {**ap.taxi_nodes, 3: types.SimpleNamespace(xy=(500.0, -100.0)),
             4: types.SimpleNamespace(xy=(500.0, 100.0))}
    far = [types.SimpleNamespace(a=3, b=4, name="Z", is_runway=False, width_class="D")] * 3
    ap = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=ap.taxi_edges + far)
    piece = Polygon([(-60, -15), (60, -15), (60, 15), (-60, 15)])
    (r, note), = rings(route_specs(piece, (1.0, 0.0), ap, _law()))
    assert round(r.bounds[2] - r.bounds[0], 1) == 52.1 and "airport common" in note


@pytest.mark.parametrize("paved", [lambda xy: False, lambda xy: abs(xy[1]) > 15.0,
                                   lambda xy: abs(xy[1]) > 15.0 and -45.0 <= xy[0] <= 2.0,
                                   lambda xy: abs(xy[1]) > 15.0 and abs(xy[0]) <= 8.0])
def test_the_pavement_never_moves_or_narrows_the_deck(paved):
    """RULINGS 2026-11-21c: no measuring.  No pavement past the ends, an
    apron, pavement lying off to one side (KRDU 35.880343,-78.788838: a
    deck read off the pavement beside taxiway D stood wholly off its
    centreline, #2215 item 1), a narrow strip: the E deck is 65.2 m,
    centred on its taxiway, every time."""
    from auto_patch_v2.planar.deck_width import rings, route_specs
    piece = Polygon([(-60, -15), (60, -15), (60, 15), (-60, 15)])
    (r, _n), = rings(route_specs(piece, (1.0, 0.0), _krdu_route("E"), _law(), paved))
    assert r.bounds[0] == pytest.approx(-32.6) and r.bounds[2] == pytest.approx(32.6)


def test_the_end_lines_run_the_decks_whole_end():
    """Owner 2026-11-21T07:36Z ("grade the terrain to the full end width of
    the bridges ... calculated from the bridge sides"): the pavement's crest
    (a 20 m run of a 65 m end) is carried out to the ring's end edge, corner
    to corner, in its own direction -- the bank, the cut cover and the
    landings stand on the TSA deck's ends."""
    from auto_patch_v2.planar.deck_width import full_ends
    ring = Polygon([(0.0, 0.0), (65.0, 0.0), (65.0, 30.0), (0.0, 30.0)])
    sa = ((40.0, 0.0), (30.0, 0.0), (20.0, 0.0))
    sb = ((20.0, 30.0), (40.0, 30.0))
    fa, fb = full_ends(ring, sa, sb, 5.0)
    assert fa[0] == (65.0, 0.0) and fa[-1] == (0.0, 0.0) and len(fa) == 14
    assert fb[0] == (0.0, 30.0) and fb[-1] == (65.0, 30.0)
    assert all(y == 0.0 for _x, y in fa) and all(y == 30.0 for _x, y in fb)
    # a ring of other than four corners keeps its crests
    five = Polygon([(0, 0), (65, 0), (65, 30), (30, 35), (0, 30)])
    assert full_ends(five, sa, sb, 5.0) == (sa, sb)
