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
from auto_patch_v2.model.structures import Deck, DeckBridge, Tunnel
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


def _deck_of(tn, airport, cut="bank"):
    """The pack deck a fixture trench runs under (``PlanarMap.decks``):
    its ring, end lines and depths, its route read off the airport."""
    from auto_patch_v2.planar.deck_route import carried_route
    from shapely.geometry import Polygon
    (oid, st_a, d_a), (_o, st_b, d_b) = tn.edge_seats[:2]
    fam, route, ref = carried_route(airport, Polygon(tn.deck_ring))
    return DeckBridge(oid, "objects/deck.obj", (oid,), tuple(tn.deck_ring), tuple(st_a),
                      tuple(st_b), float(d_a), float(d_b), 0.0, 700.0, family=fam,
                      route=route, route_ref=ref, cut=cut)


def _with(pm, *tunnels, airport=None):
    decks = tuple(_deck_of(t, airport) for t in tunnels if t.deck_bridge) if airport else ()
    return _dc.replace(pm, structures=tuple(tunnels), decks=decks)


def _anchored(site, law, *tunnels):
    ap, pm, _st = site
    pm = RC.with_deck_anchors(_with(pm, *tunnels, airport=ap), law, ap)
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
    seamed = _dc.replace(_with(pm, _tunnel(), airport=ap), seam_vertices=frozenset({v_mid}))
    ys = {a.end: a for a in RC.with_deck_anchors(seamed, law, ap).deck_anchors}
    assert ys["A"].yielding and ys["B"].yielding and "seam" in ys["A"].note
    assert all(p.source.ruling.startswith(DA.YIELD_HEAD)
               for p in DA.deck_anchor_pins(_dc.replace(pm, deck_anchors=tuple(ys.values())),
                                            law, ap))
    on = _dc.replace(_with(pm, _tunnel(), airport=ap), seam_vertices=frozenset({got["A"].v}))
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
        m = _with(pm, tn, airport=ap)
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
    ring = DBR.deck_polygon(slab)
    assert r2.intersection(ring).area < 1e-6 and o2.intersection(ring).area < 1e-6
    # 16:56Z: no wall at the slab's edge — the floor stops a 1:3 bank short of it
    r3, _o3 = DBR.deck_cut(slab, moved, ramp, ramp.buffer(1.6, join_style="mitre"), 0.6,
                           bank_run=6.0)
    assert r3.distance(DBR.deck_polygon(slab)) > 5.9
    # 16:53Z: the trench beside the slab is the object's width, wall to wall
    lo, hi = DBR.project_span(slab.ring, DBR.across_dir(slab))
    u0, u1 = DBR.project_span(list(o2.exterior.coords), DBR.across_dir(slab))
    assert abs(u0 - (lo + 0.6)) < 1e-6 and abs(u1 - (hi - 0.6)) < 1e-6
    (tmp_path / "w").mkdir()
    assert not T._bridge(tmp_path / "w").slab


def test_the_rebake_plan_carries_the_zero_the_anchors_state(site, law):
    """§3: the deck member's ``anchor_zero`` is the plate zero the object
    stage reads where the surface stands at the anchors (no yield)."""
    from auto_patch_v2.constraints.deck_lines import end_lines
    from auto_patch_v2.pipeline import rebake_inputs as RI
    _ap, pm, got = _anchored(site, law, _tunnel(depth_b=7.144))
    pm = _dc.replace(pm, decks=tuple(_dc.replace(d, top_a=d.top_a + 3.0, top_b=d.top_b + 3.0,
                                                  bottom_y=3.0) for d in pm.decks))
    out: dict = {}
    tops: dict = {}
    RI._deck_plate(out, OID, end_lines(pm, law)[OID], set(), pm, tops)
    y, st, *rest = out[OID]
    y = sum(tops[OID].values()) / len(tops[OID])
    level = {v: a.z_m for a in got.values() for v in a.stations}
    near = {tuple(pm.vertices[v].xy): z for v, z in level.items()}
    plate_zero = sum(near[tuple(p)] for p in st) / len(st) - y
    assert abs(rest[2] - plate_zero) <= 1e-6


def test_the_bank_never_cuts_a_mapped_road_beside_the_cut(tmp_path):
    """Owner 2026-11-03T16:56Z: a sloping embankment from the bridge ends to
    the trench floor unless a road edge requires a vertical cut — the bank
    stops at a mapped road beside the carriageway; the carriageway (the
    floor) is never taken out."""
    from auto_patch_v2.planar import deck_bridge as DBR
    from shapely.geometry import LineString
    from shapely.geometry import box as _sbox
    from tests.auto_patch_v2 import test_deck_bridge1671 as T
    db = T._bridge(tmp_path)
    axis = LineString([(0.0, 23.0), (0.0, 120.0)])
    moved, _d = DBR.deck_mouth(axis, (0.0, -1.0), db)
    ramp = _sbox(-4.0, -10.0, 4.0, 100.0)
    outer = ramp.buffer(1.6, join_style="mitre")
    road = _sbox(8.0, -30.0, 12.0, 100.0)
    _r0, o0 = DBR.deck_cut(db, moved, ramp, outer, 0.6)
    r1, o1 = DBR.deck_cut(db, moved, ramp, outer, 0.6, roads=road.union(ramp))
    assert o0.intersection(road).area > 1.0 and o1.intersection(road).area < 1e-6
    assert r1.equals(_r0)


def test_the_end_lines_are_the_pair_the_carried_route_crosses():
    """§2 (a): a deck the pavement meets on all four sides reads as its end
    lines the pair the carried route (runway axis / taxi route) runs
    across — never the pair the road under it runs along when the two
    disagree (LFPG H18r end B read on a taxiway, ENGM Ham2)."""
    from auto_patch_v2.planar import deck_bridge as DBR
    from shapely.geometry import LineString
    to_xy = lambda lon, lat: (lon, lat)                       # noqa: E731
    along = (((0.0, 0.0), (0.0, 10.0)), ((10.0, 0.0), (10.0, 10.0)))   # y = 0 / 10
    across = (((0.0, 0.0), (10.0, 0.0)), ((0.0, 10.0), (10.0, 10.0)))  # x = 0 / 10
    route = LineString([(-5.0, 5.0), (15.0, 5.0)])
    assert DBR._end_pair([along, across], None, to_xy, [route]) is across
    assert DBR._end_pair([along, across], None, to_xy, []) is along


def test_the_slab_witness_is_the_plates_own_attribute(tmp_path):
    """Round 3 §1 (OBJ8: ``ATTR_hard_deck`` is a hard surface one passes
    under, ``ATTR_hard`` is solid from the ground up).  (A) a plate carried
    on ``ATTR_hard`` with the flag only on its edge-on sides is a SLAB; (B) a
    13 m plate-only ``ATTR_hard_deck`` deck with no frame under it (LFPG's
    H18r) is NOT: its floor is the level-B ladder under its top and the
    corridor cuts under it; (C) a slab's ring is never in the runway
    family's blade mask (``structures.deck_cover_of``)."""
    from auto_patch_v2.airport import obj8 as O
    from auto_patch_v2.planar import deck_bridge as DBR
    from auto_patch_v2.planar.structures import deck_cover_of
    from tests.auto_patch_v2 import test_deck_bridge1671 as T
    (slab,), _n = T._slab_read(tmp_path, T.AIRPORT, level_b=7.0)
    assert slab.slab and O.parse_obj8(T._slab_obj(tmp_path)).hard_plate
    (tmp_path / "b").mkdir()
    plate = T._write(tmp_path / "b" / "plate.obj",
                     [T._box(-20.0, -20.0, 40.0, 40.0, 0.01, y0=13.10)], hard=(0,))
    assert not O.parse_obj8(plate).hard_plate
    o = T._placed(plate, "dsf:obj13")
    o.deck_top_z = 113.11
    (deck,), _n = DBR.deck_bridges([o], O.ResourceCache(T.THICK), T._classification(),
                                    T.AIRPORT, T.LAW, (), level_b=7.0)
    assert not deck.slab and abs(deck.depth_m - 7.0) < 1e-6
    assert abs(deck.bottom_y - (13.11 - 7.0)) < 1e-6
    tn = _dc.replace(_tunnel(), id="t1", footprint=())
    hard = deck_cover_of([tn], {"t1": deck})
    assert abs(hard.area - DBR.deck_polygon(deck).area) < 1e-6
    assert deck_cover_of([tn], {"t1": slab}).is_empty


def test_under_a_slab_the_ground_is_the_decks_and_the_taxi_anchor_is_a_station():
    """Round 3 §3 (twin D, KIAH ``obj24551`` end B): a mapped road cell
    inside a slab's ring becomes deck ground ``deck_ground:*`` (its rows
    were the road's, lifting the seat); the taxiway's own cells stay; and a
    taxi deck's pinned vertex is the seat STATION nearest where the carried
    chain crosses the end line, never a junction vertex beside it."""
    import types

    from auto_patch_v2.planar import deck_bridge as DBR
    from shapely.geometry import Polygon
    from shapely.geometry import box as _sbox
    from tests.auto_patch_v2 import test_deck_bridge1671 as T
    ring = _sbox(-20.0, -20.0, 20.0, 20.0)
    road = T._cell(1, "service_road", _sbox(-30.0, -4.0, 30.0, 4.0))
    taxi = T._cell(0, T.TAXI, _sbox(-10.0, -100.0, 10.0, -20.0))
    slab = types.SimpleNamespace(deck_bridge="dsf:obj9", deck_slab=True,
                                 deck_ring=tuple(ring.exterior.coords)[:-1],
                                 edge_seats=(("dsf:obj9", ((-20.0, -20.0), (20.0, -20.0)), 1.0),
                                             ("dsf:obj9", ((-20.0, 20.0), (20.0, 20.0)), 1.0)))
    @_dc.dataclass(frozen=True)
    class _Cl:
        cells: tuple
    deck = types.SimpleNamespace(object_id="dsf:obj9", cut="slab", ring=slab.deck_ring)
    out, notes = DBR.deck_ground(_Cl((taxi, road)), [slab], T.LAW, [deck])
    roads = [Polygon(c.ring) for c in out.cells if c.role == "service_road"]
    assert roads and all(p.intersection(ring).area < 1e-6 for p in roads)
    assert abs(sum(p.area for p in roads) - 2 * 10.0 * 8.0) < 1e-6
    under = [Polygon(c.ring) for c in out.cells if str(c.ref).startswith("deck_ground:dsf:obj9")]
    assert abs(sum(p.intersection(ring).area for p in under) - ring.area) < 1e-6
    assert any(c.role == T.TAXI for c in out.cells) and any("SLAB" in n for n in notes)
    # the anchor: stations at x = -20..20 step 10; the chain crosses at x = 3.5
    xy = {k: (-20.0 + 10.0 * k, -20.0) for k in range(5)}
    xy.update({10: (3.5, -60.0), 11: (3.6, 5.0), 12: (4.5, -19.0)})
    vw = types.SimpleNamespace(xy=xy)
    st = [xy[k] for k in range(5)]
    assert DA._taxi_vertex(vw, (10, 11), st, list(range(5))) == 2
    assert DA._taxi_vertex(vw, None, st, list(range(5))) == 2


# ── deck redesign PR A (§1): decks on the map, one derivation for both maps ──

def test_a_deck_record_with_no_tunnel_is_read_by_anchors_rows_and_the_plate(site, law):
    """§0 / §1: the anchors, the deck rows and the object stage's plate read
    ``PlanarMap.decks`` — a deck no corridor runs under is anchored, its
    stations held ABSOLUTELY at the anchor's level (± ``deck_flush_m``),
    and its member gets a DECK plate; no ``Tunnel`` names it."""
    from auto_patch_v2.constraints import edge_deck as ED
    from auto_patch_v2.model.constraints import Band
    from auto_patch_v2.pipeline import rebake_inputs as RI
    ap, pm, _st = site
    deck = _deck_of(_tunnel(), ap, cut="none")
    m = RC.with_deck_anchors(_dc.replace(pm, structures=(), decks=(deck,)), law, ap)
    got = {a.end: a for a in m.deck_anchors}
    assert set(got) == {"A", "B"} and all(a.cut == "none" and a.line for a in got.values())
    flush = float(law.tables.structures.bridge.deck_flush_m)
    bands = [r for r in ED.edge_deck_rows(m, law, ap)
             if isinstance(r, Band) and r.source.ruling == ED.RIGID]
    level = {v: a.z_m for a in got.values() for v in a.stations}
    assert bands and {r.v for r in bands} == set(level)
    for r in bands:
        assert (r.lo, r.hi) == pytest.approx((level[r.v] - flush, level[r.v] + flush))
    y, st, _c, kind, *_zero = RI._edge_seat_plates(m, set(), law)[OID]
    assert kind == RI.DECK_PLATE and len(st) == len(level)


def test_a_yielding_anchor_keeps_the_relational_station_rows(site, law):
    """§1: only a HELD level (pinned, not yielding) is absolute — a seam
    pin on the deck makes the anchor yield, and its stations are read from
    the deck's one zero as before (a hard band would outlive the yield)."""
    from auto_patch_v2.constraints import edge_deck as ED
    from auto_patch_v2.model.constraints import Band
    ap, pm, _st = site
    v_mid = min(pm.vertices, key=lambda q: math.dist(pm.vertices[q].xy, (0.0, 0.0)))
    m = _dc.replace(_with(pm, _tunnel(), airport=ap), seam_vertices=frozenset({v_mid}))
    m = RC.with_deck_anchors(m, law, ap)
    assert all(a.yielding for a in m.deck_anchors)
    rows = [r for r in ED.edge_deck_rows(m, law, ap) if r.source.ruling == ED.RIGID
            and str(r.source.inputs[1]).startswith("station")]
    assert rows and not any(isinstance(r, Band) for r in rows)


def test_stage_one_takes_the_full_maps_anchor_levels(site, law):
    """§1 ONE DERIVATION FOR BOTH MAPS (KIAH ``obj24551``: 28.440 on the full
    map, 28.619 on stage 1's): a map derived under ``from_full`` — here one
    whose ground reads 0.3 m higher, as a ribbon-free classification inside
    a slab's ring can — takes the full map's level for every end line, on
    its own stations; outside the block it derives its own."""
    from auto_patch_v2.model.stage_one import from_full
    ap, pm, _st = site
    # no chord: an end line reads the ground at its seats, so the two maps'
    # own derivations part by the 0.3 m
    full = _with(pm, _tunnel(), airport=ap)
    full = _dc.replace(full, deck_anchors=DA.derive(full, law, ap))
    up = {v: _dc.replace(vx, dem_z=None if vx.dem_z is None else vx.dem_z + 0.3)
          for v, vx in full.vertices.items()}
    s1 = _dc.replace(full, vertices=up, deck_anchors=())
    own = {a.end: a.z_m for a in DA.derive(s1, law, ap)}
    with from_full(full):
        got = {a.end: a for a in DA.derive(s1, law, ap)}
    want = {a.end: a for a in full.deck_anchors}
    assert set(got) == set(want) == {"A", "B"}
    for e, a in got.items():
        assert a.z_m == want[e].z_m and a.v == want[e].v and a.family == want[e].family
    assert all(abs(own[e] - want[e].z_m - 0.3) < 1e-6 for e in want)


def test_the_family_is_the_decks_from_its_carried_route():
    """§1: ONE family per deck, from the most senior route it carries — a
    runway axis crossing the deck makes both end lines runway-family
    (round 3 voted per end line: LFPG ``obj13018`` end B "taxi" beside the
    runway it carries); else the row-1202 taxi edges through it, run on
    ``ROUTE_REACH_M`` each way along the straightest continuation."""
    import types

    from auto_patch_v2.planar import deck_route as DR
    from shapely.geometry import box as _sbox
    N = types.SimpleNamespace
    rw = N(id="09/27", ends=(N(xy=(-600.0, 0.0)), N(xy=(600.0, 0.0))))
    nodes = {k: N(xy=(0.0, 200.0 * (k - 5))) for k in range(10)}     # x = 0, y -1000..800
    nodes[10] = N(xy=(400.0, 800.0))                                    # a 90° turn: the stop
    edges = tuple(N(a=k, b=k + 1, is_runway=False) for k in range(10))
    ap = N(runways=(rw,), taxi_nodes=nodes, taxi_edges=edges)
    fam, route, ref = DR.carried_route(ap, _sbox(-20.0, -20.0, 20.0, 20.0))
    assert (fam, ref) == ("runway", "09/27") and route == ((-600.0, 0.0), (600.0, 0.0))
    fam, route, ref = DR.carried_route(ap, _sbox(-20.0, 280.0, 20.0, 320.0))
    # 600 m on south of the crossing edge; north it stops at the turn
    assert (fam, ref) == ("taxi", "") and route[0] == (0.0, -400.0) and route[-1] == (0.0, 800.0)
    assert DR.carried_route(ap, _sbox(900.0, 900.0, 950.0, 950.0)) == ("road", (), "")
