"""#2072 / #1902 round 2 twins (spec ``docs/specs/2072-kiah-deck-trench-spec.md``):
a hard-deck trench is self-contained -- it never ends on airside pavement
(rule A), its ladder floor is a pinned level linear between two decks (B1),
its lanes are its roads' levels (B2) and no void wider than a wall band
stands inside the deck's reach (C).  One synthetic airport: a 100 x 30 m
taxiway deck (floor 7.5 m under it, the ladder's 5 m least depth) over a
north-south road, an apron 12 m beyond its north edge."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry import box as _sbox

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_m4b as M4B                                         # noqa: E402
from auto_patch_v2.classify.roles import Cell, Classification  # noqa: E402
from auto_patch_v2.constraints import generate                 # noqa: E402
from auto_patch_v2.constraints.edge_floor import DECK_FLOOR     # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.model.airport import OsmWay                 # noqa: E402
from auto_patch_v2.model.constraints import Pin                # noqa: E402
from auto_patch_v2.model.structures import DECK_GROUND_REF, DeckBridge, deck_floor_z  # noqa: E402
from auto_patch_v2.planar import deck_bores as DBO             # noqa: E402
from auto_patch_v2.planar import deck_bridge as DB             # noqa: E402
from auto_patch_v2.planar.structures import build_structures   # noqa: E402

LAW = Law.for_airport("ZZZZ")
TN = LAW.tables.structures.tunnel
RIM = TN.wall_gap_m + TN.wall_band_width_m
APRON_Y = 27.0                     # 12 m beyond the deck's north edge (y = 15)


def _deck():
    ring = tuple(_sbox(-50.0, -15.0, 50.0, 15.0).exterior.coords[:-1])
    a = tuple((-50.0, y) for y in (-10.0, 0.0, 10.0))
    b = tuple((50.0, y) for y in (-10.0, 0.0, 10.0))
    return DeckBridge("dsf:obj1", "objects/deck.obj", ("dsf:obj1",), ring, a, b, 0.0, 0.0,
                      -7.5, 700.0, floor_min_m=5.0, family="taxi")


def _cells():
    return [Cell(0, "runway", "09/27", M4B._rect(-600, 500, 600, 545), (), 3, "D", "airside",
                 "runway", {}),
            Cell(1, "primary_parallel", "taxi1", M4B._rect(-300, -15, 300, 15), (), None, "C",
                 "airside", "taxiway", {}),
            Cell(2, "apron", "apron1", M4B._rect(-100, APRON_Y, 100, 120), (), None, None,
                 "airside", "apron", {})]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    road = OsmWay(-1, "big_roads", ((0.0, -400.0), (0.0, 400.0)), False,
                  {"highway": "primary", "lanes": "2"})
    airport = M4B._airport({"dir": d}, LAW, [], (road,))
    db = _deck()
    cl, tunnels, st = build_structures(airport, Classification(tuple(_cells()), (), {}, ()),
                                       LAW, deck_bridges=(db,))
    pb = importlib.import_module("auto_patch_v2.planar.build")
    real = pb.deck_bridges
    pb.deck_bridges = lambda *a, **k: ((db,), [])
    try:
        pm, _stats = pb.build(airport, Classification(tuple(_cells()), (), {}, ()), LAW)
    finally:
        pb.deck_bridges = real
    cs, _counts, _w = generate(pm, LAW, airport)
    return types.SimpleNamespace(airport=airport, db=db, cl=cl, tunnels=tunnels, st=st,
                                 pm=pm, cs=cs)


def _north(tunnels):
    return next(t for t in tunnels if t.axis[-1][1] > 0.0)


def _polys(cl, role):
    return [Polygon(c.ring, c.holes) for c in cl.cells if c.role == role]


def _row_vertices(r):
    terms = getattr(r, "terms", None)
    if terms:
        return {v for v, _c in terms}
    return {getattr(r, k) for k in ("v", "a", "b") if isinstance(getattr(r, k, None), int)} \
        | set(getattr(r, "group", ()) or ())


# -- A: a trench never ends on airside pavement -----------------------------

def test_a_dead_end_trench_is_level_to_the_apron_and_walled_at_its_edge(site):
    """A1-A3: the apron 12 m out stops the run-out before any ramp up to the
    cap tops out (7.5 m at 10 % needs 75 m): the north trench is not
    refused, level at its floor to the stop with no top pin; the cut's rim
    stands on the apron edge, the floor ``rim_off`` short of it and the void
    between them is the wall."""
    assert not site.st.refused
    tn = _north(site.tunnels)
    assert tn.climb_from_s == pytest.approx(tn.top_s) and not tn.top_pinned
    assert any("#2072 A" in n for n in tn.notes)
    apron = next(Polygon(c.ring) for c in site.cl.cells if c.ref == "apron1")
    assert apron.area == pytest.approx(200.0 * 93.0)              # never cut
    ramps = [p for p in _polys(site.cl, "tunnel_ramp") if p.centroid.y > 0.0]
    walls = [p for p in _polys(site.cl, "retaining_wall") if p.bounds[3] > 15.0]
    assert min(p.distance(apron) for p in ramps) >= RIM - 1e-6
    assert any(w.distance(apron) < 1e-6 and w.bounds[3] == pytest.approx(APRON_Y) for w in walls)


def test_no_floor_vertex_stands_in_an_airside_column(site):
    """The floor never shares a column with the airside: every floor
    vertex is pinned (a constant) and no row joins one to an airside
    vertex for stage 1 to read."""
    from auto_patch_v2.solve.design_roles import airside_stage_vertices
    pm, cs = site.pm, site.cs
    pins = {p.v for p in cs.pins if p.source.ruling == DECK_FLOOR}
    air = airside_stage_vertices(pm, LAW)
    assert pins and not pins & air
    for r in cs.rows():
        vs = _row_vertices(r)
        if vs & pins:
            assert not vs & air, r


# -- B1: the ladder floor is a pinned level ---------------------------------

def test_the_ladder_floor_is_pinned_at_its_target_and_no_seat_row_is_minted(site):
    """B1: every datum station group is pinned (senior, ``DECK_FLOOR``) at
    the ramp's own target; the one-sided seat row is gone."""
    pins = [p for p in site.cs.pins if p.source.ruling == DECK_FLOOR]
    assert pins
    targets = getattr(site.pm, "targets", None) or {}
    for p in pins:
        assert p.z == pytest.approx(site.db.deck_z - site.db.depth_m)
        if p.v in targets:
            assert targets[p.v] == pytest.approx(p.z, abs=0.01)
    assert not [r for r in site.cs.rows() if r.source.ruling == DECK_FLOOR
                and not isinstance(r, Pin)]


def test_the_floor_between_two_decks_is_linear_and_meets_at_one_level():
    """B1 / Q271 (b): along the open stretch the floor runs from this deck's
    floor at ``s0`` to the other's at ``s1``; the two halves agree at the
    stop."""
    mk = types.SimpleNamespace
    a = mk(mouth_z=20.0, deck_bridge="dA", edge_floor_s=(15.0, 65.0),
           edge_seats=(("dA", (), 7.5), ("dA", (), 7.5), ("dB", (), 7.5), ("dB", (), 7.5)))
    b = mk(mouth_z=22.0, deck_bridge="dB", edge_floor_s=(15.0, 65.0),
           edge_seats=(("dB", (), 7.5), ("dB", (), 7.5), ("dA", (), 7.5), ("dA", (), 7.5)))
    assert deck_floor_z(a, 0.0, [a, b]) == 20.0 and deck_floor_z(a, 65.0, [a, b]) == 22.0
    assert deck_floor_z(a, 40.0, [a, b]) == pytest.approx(21.0)
    assert deck_floor_z(b, 40.0, [a, b]) == pytest.approx(21.0)     # one level at the stop
    assert deck_floor_z(a, 40.0, [a]) == 20.0                         # no partner: flat
    lone = mk(mouth_z=19.0, deck_bridge="", edge_floor_s=(0.0, 10.0), edge_seats=())
    assert deck_floor_z(lone, 5.0, []) == 19.0


def test_a_low_deck_lifts_nothing(site):
    """B1: the floor's pins are constants -- a deck solved low against them
    is reported (``publication.tunnel_mouth_depths``), never lifted."""
    from auto_patch_v2.pipeline.publication import _deck_clearance
    tn = _north(site.tunnels)

    def anchors(dz):
        return types.SimpleNamespace(deck_anchors=tuple(
            types.SimpleNamespace(object_id="dsf:obj1", z_m=tn.mouth_z + dz) for _ in range(2)))
    rec = _deck_clearance(anchors(4.0), tn)
    assert rec["clearance_m"] == pytest.approx(4.0)
    assert rec["clearance_short_m"] == pytest.approx(1.0)
    assert "clearance_short_m" not in _deck_clearance(anchors(7.5), tn)


# -- B2: lanes by level ----------------------------------------------------

def test_two_roads_at_two_levels_under_one_deck_side_are_two_lanes():
    """B2: a trunk pair and a road 4 m higher within the dual separation are
    two lanes; a dual whose carriageways stand 0.2 m apart stays one."""
    db = _deck()
    sep = TN.dual_carriageway_max_separation_m

    def mouth(x):
        return types.SimpleNamespace(xy=(x, 0.0), inward=(0.0, 1.0))
    ms = [mouth(-10.0), mouth(-2.0), mouth(8.0)]
    lv = {id(ms[0]): 20.0, id(ms[1]): 20.2, id(ms[2]): 24.0}
    lane_of, _c = DBO.deck_lanes(ms, {id(m): db for m in ms}, sep, lv, 0.5)
    assert [lane_of[id(m)] for m in ms] == [0, 0, 1]
    lane_of, _c = DBO.deck_lanes(ms, {id(m): db for m in ms}, sep)
    assert [lane_of[id(m)] for m in ms] == [0, 0, 0]               # no levels: by separation


def test_a_roads_level_is_read_beyond_the_deck_over_one_ramp_length():
    """B2: the median DEM along the mouth's own road, from the deck edge +
    the gap, over one design ramp length."""
    db = _deck()
    approach = ((0.0, 0.0), (0.0, 300.0))
    z = DBO.road_level(approach, db, lambda x, y: 100.0 if y < 15.6 else 20.0 + 0.01 * y,
                       0.6, 150.0, 12.0)
    assert 20.15 < z < 21.0
    assert DBO.road_level((), db, lambda x, y: 0.0, 0.6, 150.0, 12.0) is None


# -- C: no void wider than a wall band inside the deck's reach -------------

def test_the_banks_under_the_deck_are_its_own_ground_with_the_toe_on_the_floor(site):
    """C: the cut takes the floor only; the banks are ``deck_ground`` faces
    whose toe vertices are floor (no span row) and whose head is spanned
    at the deck; no void inside the deck's reach is wider than a wall
    band."""
    pm, cs = site.pm, site.cs
    ring = Polygon(site.db.ring)
    grounds = [f for f in pm.faces.values() if str(f.ref).startswith(DECK_GROUND_REF + ":")]
    assert grounds
    spanned = {r.terms[0][0] for r in cs.rows()
               if r.source.generator == "edge_deck" and getattr(r, "terms", None)}
    toe = head = 0
    for f in grounds:
        for v in set(pm.ring_vertices(f.ring)):
            if "tunnel_ramp" in set(pm.roles_at(v)):
                toe += 1
                assert v not in spanned
            elif v in spanned:
                head += 1
    assert toe and head
    for f in pm.faces.values():
        if f.role != "retaining_wall":
            continue
        p = Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]).buffer(0.0)
        inner = p.intersection(ring.buffer(-0.1))
        assert inner.is_empty or inner.buffer(-RIM).is_empty      # within a band of its edge


def test_deck_banks_are_the_ring_less_the_floor_on_the_corridors_side():
    db = _deck()
    axis = LineString([(0.0, 0.0), (0.0, 200.0)])
    run = db.depth_m / float(LAW.tables.emit.design.bank_slope)
    banks = DB.deck_banks(db, axis, 0.6, bank_run=run)
    assert banks is not None and banks.bounds[1] == pytest.approx(0.0)
    assert banks.bounds[0] == pytest.approx(-49.4) and banks.bounds[3] == pytest.approx(14.4)
    floor = DB._floor_under(db, DB.deck_polygon(db).buffer(-0.6, join_style="mitre"), run)
    assert banks.intersection(floor).area < 1e-6


def test_the_decks_airside_edge_band_is_uncut_beside_the_corridor():
    """The taxiway pavement left in the ring's edge band (``inset`` wide) is
    airside the cut never takes: it joins ``uncut`` beside the corridor,
    never across the corridor's own mouth."""
    db = _deck()
    paved = _sbox(-300.0, -15.0, 300.0, 15.0)
    outer = _sbox(-5.5, -200.0, 5.5, 0.0)
    edge = DB.deck_edge_pavement(db, 0.6, paved, outer)
    assert edge is not None and edge.intersection(outer).area < 1e-9
    assert edge.area == pytest.approx(2 * (100.0 + 30.0 - 1.2) * 0.6 - 11.0 * 0.6, rel=0.02)
    assert DB.deck_edge_pavement(db, 0.6, None, outer) is None


def test_the_census_names_a_tear_on_the_decks_ground_and_never_adjudicates_it():
    """Census row of the spec: a seam tear one of whose ways is a hard
    deck's own ground (``deck_ground:*``) is the cut's step -- stamped
    out of scope; a tear between two other strips is not."""
    tools = Path(__file__).resolve().parents[2] / "tools"
    sys.path.insert(0, str(tools))
    import check_grade as CG                                   # noqa: E402
    mk = types.SimpleNamespace
    on = mk(way_a=mk(ref="deck_ground:dsf:obj1#2"), way_b=mk(ref="tunnel_ramp"),
            out_of_scope=None)
    off = mk(way_a=mk(ref="zone:1"), way_b=mk(ref="zone:2"), out_of_scope=None)
    assert CG.stamp_deck_ground_tears([on, off]) == 1
    assert on.out_of_scope == CG.DECK_GROUND_TEAR_OUT_OF_SCOPE and off.out_of_scope is None
    assert CG.DECK_GROUND_TEAR_OUT_OF_SCOPE in CG.OUT_OF_SCOPE_CLASSES
    assert CG.DECK_GROUND_REF_PREFIX == DECK_GROUND_REF + ":"
