"""§45 THE OPEN CHANNEL — the eight twins (spec §45.2; owner RULINGS
2026-09-15i), lane ``v2channel``.

ONE synthetic airfield per twin: an apt.dat pavement with an UNPAVED
CORRIDOR cut through it and PAVED NECKS bridging it, a road way along the
corridor, and whatever witness the twin is about (a lidar cut, a pack
wall/floor object, a second neck 58 m away).  Law values are read from
the tables inside the tests, never retyped.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, OsmWay, Pavement, Runway,
                                         RunwayEnd, SceneryPack, Surface)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.structures import CREST_DESIGN
from auto_patch_v2.planar.channel import (DATUM_CLEARANCE, DATUM_LIDAR, DATUM_PACK,
                                          WITNESS_NECK, WITNESS_PACK,
                                          identify_channels)
from auto_patch_v2.planar.channel_claims import (channel_cells, channel_claiming,
                                                 channel_ways, channel_yields,
                                                 claimed_crossing_ways,
                                                 in_any_corridor)
from auto_patch_v2.planar.structures import build_structures


# ── the synthetic ground ─────────────────────────────────────────────────

class _PlaneDem:
    """Flat ground at 100 m — the DEM sees NOTHING of the cut (LGAV /
    KPHX's 30 m Copernicus)."""

    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 100.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _CutDem(_PlaneDem):
    """A 9 m cut along ``x = 0`` with 1:4 banks — KDFW's 1 m 3DEP DTM."""

    provenance = {"synthetic": "a 9 m cut with 1:4 banks"}

    def z(self, x: float, y: float) -> float:
        d = abs(float(x))
        if d >= 46.0:
            return 100.0
        return max(91.0, 100.0 - (46.0 - d) * 0.25)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _pavement_with_corridor(x0=-20.0, x1=20.0,
                            necks=((-40.0, -10.0), (120.0, 150.0))):
    """The apt.dat airside pavement union: one 900 x 800 m slab with a
    CORRIDOR (``x0 <= x <= x1``, ``|y| <= 350``) cut out of it as a HOLE,
    and a PAVED NECK across the corridor at each ``(y0, y1)``.

    The corridor stops SHORT of the slab's edge on purpose: KDFW's is an
    INTERIOR ring (``ring69``, lat 32.886…32.909 inside ``ring0``'s
    32.871…32.923 — scout `channelscout` §4a), and a notch cut edge to
    edge would be part of the exterior instead, which is not the shape
    §45 (1) (b) reads."""
    outer = Polygon(_rect(-450.0, -400.0, 450.0, 400.0))
    corridor = Polygon(_rect(x0, -350.0, x1, 350.0))
    for y0, y1 in necks:
        corridor = corridor.difference(Polygon(_rect(x0 - 1.0, y0, x1 + 1.0, y1)))
    holes = [tuple(g.exterior.coords)[:-1]
             for g in getattr(corridor, "geoms", [corridor]) if not g.is_empty]
    return Pavement("pav0", Surface.ASPHALT, tuple(outer.exterior.coords)[:-1],
                    tuple(holes), "fixture", "")


def _road(wid=-500, tags=None):
    return OsmWay(wid, "big_roads",
                  tuple((0.0, y) for y in range(-400, 401, 20)), False,
                  dict(tags or {"highway": "motorway", "lanes": "3"}))


def _airport(law, pavements, ways, dem=None, dsf=()):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 1000.0), (60.5, -135.5), 0.0, 0.0, 100.0, "fixture"),
            RunwayEnd("27", (600.0, 1000.0), (60.5, -135.5), 0.0, 0.0, 100.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 100.0, (rw,), tuple(pavements), (), {},
                   (), (), (), (), tuple(ways), (), tuple(dsf), pack,
                   dem or _PlaneDem(), law.ruleset_key)


def _cells():
    return [
        Cell(0, "runway", "09/27", _rect(-600, 980, 600, 1025), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronW", _rect(-450, -400, -20, 400), (), None, None,
             "airside", "apron", {}),
        Cell(2, "apron", "apronE", _rect(20, -400, 450, 400), (), None, None,
             "airside", "apron", {}),
        # the NECK: apt.dat pavement bridging the corridor.  ``apron`` and
        # not ``taxiway`` only because ``taxiway`` is not a precedence role
        # in this repo's register (``law/precedence.toml``); §45 (4)'s
        # point is that the neck keeps its own AIRSIDE role and law, which
        # ``apron`` carries exactly as a taxi cell would.
        Cell(3, "apron", "neck0", _rect(-20, -40, 20, -10), (), None, None,
             "airside", "apron", {}),
    ]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── (a) the hole-and-neck fixture ────────────────────────────────────────

def test_a_hole_and_neck_states_one_channel_with_no_mouths(law):
    """(a) One channel, a deck at the neck, floor = deck top − 5.1 m,
    bank 1:2, NO mouths and no ``tunnel_mouth_canonical`` population."""
    ch = law.tables.structures.channel
    br = law.tables.structures.bridge
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert len(chans) == 1, (st.refused, st.notes)
    c = chans[0]
    assert WITNESS_NECK in c.witnesses
    assert c.crest == CREST_DESIGN
    assert c.bank_slope == pytest.approx(ch.bank_slope)
    # TWO crossings: §45 (12) refuses a neck-only channel with one
    # (``min_decks_without_depth``) — a single neck is a CROSSING
    assert len(c.decks) == 2 and c.decks[0].datum == CREST_DESIGN
    # §45 (3) (iii) CUT THE ROAD DOWN: the DEM is flat at 100, so the
    # floor under the deck is exactly the clearance below it
    assert c.datum_source == DATUM_CLEARANCE
    mid = (c.decks[0].s0 + c.decks[0].s1) / 2.0
    assert c.floor_z(mid) == pytest.approx(100.0 - br.clearance_m, abs=1e-6)
    # §45 (6): NO MOUTH — the record says so and the way is the channel's
    assert any("NO MOUTH" in n for n in c.notes)
    assert -500 in c.ways


def test_a_the_channel_emits_a_floor_and_a_bank_and_never_the_deck(law):
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    cells, knives = channel_cells(chans, law)
    roles = {r for r, _ref, _p, _cid in cells}
    assert roles == {"tunnel_trench", "retaining_wall"}, roles
    assert knives
    # EMITTABLE IN A HEIGHTFIELD (§45 (8)): floor and bank never overlap,
    # and neither covers the deck
    floor = [p for r, _ref, p, _cid in cells if r == "tunnel_trench"]
    bank = [p for r, _ref, p, _cid in cells if r == "retaining_wall"]
    for f in floor:
        for b in bank:
            assert f.intersection(b).area < 1e-6
    for d in chans[0].decks:
        deck = Polygon(d.ring)
        for f in floor + bank:
            assert f.intersection(deck).area < 1.0


# ── (b) the same with a 9 m lidar cut ────────────────────────────────────

def test_b_a_credible_lidar_inset_supplies_the_floor(law, monkeypatch):
    """(b) With a credible lidar inset the floor is the DTM floor, not the
    clearance datum — the SAME replay, no code change (§45 (3) (ii))."""
    import auto_patch_v2.planar.channel as chmod
    monkeypatch.setattr(chmod, "_lidar_credible", lambda _a, _l: True)
    ap = _airport(law, [_pavement_with_corridor()], [_road()], dem=_CutDem())
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert len(chans) == 1, (st.refused, st.notes)
    c = chans[0]
    assert c.datum_source == DATUM_LIDAR
    zs = [z for _s, z in c.profile]
    assert min(zs) == pytest.approx(91.0, abs=0.2), zs[:5]
    # and the decks are unchanged by the datum
    assert len(c.decks) == 2


class _SlopeDem(_PlaneDem):
    """Ordinary sloping ground — a credible lidar inset that sees NO cut
    (CYXY / KCLT: the round-8 arm read them as 120 m channels)."""

    provenance = {"synthetic": "a 1:20 hillside"}

    def z(self, x: float, y: float) -> float:
        return 100.0 + float(x) * 0.05


def test_3ii_a_credible_inset_is_no_depth_witness_without_a_cut(law, monkeypatch):
    """§45 (3) (ii)/(7): "Where the DEM DOES see the cut (KDFW) it is the
    floor witness".  A credible inset over a HILLSIDE is not a depth
    witness — measured on the round-8 arm at CYXY, KCLT and KPHX, where
    it made the bank toes walk to ``corridor_max_half_width_m`` and gave
    a road crossing a taxiway a 120 m corridor on a floor that was just
    the terrain."""
    import auto_patch_v2.planar.channel as chmod
    monkeypatch.setattr(chmod, "_lidar_credible", lambda _a, _l: True)
    ap = _airport(law, [_pavement_with_corridor()], [_road()], dem=_SlopeDem())
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert len(chans) == 1, (st.refused, st.notes)
    assert chans[0].datum_source == DATUM_CLEARANCE
    assert "lidar" not in chans[0].width_source


# ── (c) the pack's wall / floor objects ──────────────────────────────────

class _Placed:
    """The two fields :func:`planar.channel._pack_witnesses` reads off a
    ``PlacedObject`` — its below-grade footprint and its deepest genuine
    solid."""

    def __init__(self, oid, poly, z):
        self.id = oid
        self.below_grade = poly
        self.plan_bbox = poly
        self.solid_min_z = z
        self.witnesses = ()


def test_c_a_pack_wall_object_along_the_axis_is_the_witness_not_a_seed(law):
    """(c) A wall/floor object along the axis gives the floor (§45 (3) (i))
    and is the channel's witness (1) (c) — never a basin seed, a sunken
    road or a tunnel-object corridor (§45 (7))."""
    obj = _Placed("dsf:obj1", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()),
                                  law, [obj])
    assert len(chans) == 1, (st.refused, st.notes)
    c = chans[0]
    assert c.datum_source == DATUM_PACK and WITNESS_PACK in c.witnesses
    assert c.floor_z(0.0) == pytest.approx(88.0)
    assert all(w.shape == "face" for w in c.walls)
    assert "dsf:obj1" in "".join(w.witness for w in c.walls)


def test_c_the_object_is_dropped_from_the_basin_seeds(law):
    obj = _Placed("dsf:obj1", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()),
                                   law, [obj])
    assert in_any_corridor(chans, obj.below_grade) == chans[0].id
    # ...and something 300 m away is not the channel's
    assert in_any_corridor(chans, Polygon(_rect(300.0, 0.0, 320.0, 20.0))) == ""


# ── (d) two decks 58 m apart ─────────────────────────────────────────────

def test_d_two_decks_58_m_apart_keep_the_floor_down_between_them(law):
    """(d) KPHX: two decks closer than ``2 x clearance / ramp_max_grade``
    keep the floor at the datum between them — the road never climbs
    between the terminals."""
    br = law.tables.structures.bridge
    tn = law.tables.structures.tunnel
    necks = ((-40.0, -18.0), (40.0, 62.0))       # 58 m of corridor between
    ap = _airport(law, [_pavement_with_corridor(necks=necks)], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert len(chans) == 1, (st.refused, st.notes)
    c = chans[0]
    assert len(c.decks) == 2, [d.ref for d in c.decks]
    assert c.datum_source == DATUM_CLEARANCE
    reach = 2.0 * br.clearance_m / tn.ramp_max_grade
    assert 58.0 < reach                      # the premise the twin rests on
    mids = sorted((d.s0 + d.s1) / 2.0 for d in c.decks)
    between = (mids[0] + mids[1]) / 2.0
    datum = 100.0 - br.clearance_m
    rise = c.floor_z(between) - datum
    assert rise <= (mids[1] - mids[0]) / 2.0 * tn.ramp_max_grade + 1e-6
    assert rise < br.clearance_m             # it never climbs back to grade


# ── (e) the existing bores are byte-identical ────────────────────────────

def test_e_a_plain_bore_fixture_is_untouched_by_the_channel_pass(law):
    """(e) A ``tunnel=yes`` way with two mouths and no pavement hole
    produces the SAME ``Tunnel`` records with and without the channel
    argument — a channel that does not exist changes nothing."""
    tags_t = {"highway": "secondary", "tunnel": "yes", "lanes": "2"}
    tags_r = {"highway": "secondary", "lanes": "2"}
    ways = (OsmWay(-101, "big_roads", ((-80.0, 0.0), (80.0, 0.0)), False, tags_t),
            OsmWay(-201, "big_roads", ((80.0, 0.0), (700.0, 0.0)), False, tags_r),
            OsmWay(-202, "big_roads", ((-80.0, 0.0), (-700.0, 0.0)), False, tags_r))
    cells = [Cell(0, "apron", "apron1", _rect(-120, -80, 120, 80), (), None, None,
                  "airside", "apron", {})]
    ap = _airport(law, [], ways)
    cl = Classification(tuple(cells), (), {}, ())
    _c1, t_none, s_none = build_structures(ap, cl, law)
    _c2, t_empty, s_empty = build_structures(ap, cl, law, channels=())
    assert [t.id for t in t_none] == [t.id for t in t_empty]
    assert [(t.mouth_z, t.top_s, t.climb_from_s, t.half_width_m) for t in t_none] == \
           [(t.mouth_z, t.top_s, t.climb_from_s, t.half_width_m) for t in t_empty]
    assert s_none.refused == s_empty.refused
    assert s_none.tunnels == s_empty.tunnels


def test_e_a_way_inside_a_corridor_never_becomes_a_bore(law):
    """§45 (1)/(6): the road the channel owns is refused as a bore seed by
    NAME — this is what removes KPHX's eight "the mouth stands against
    building pad building16" refusals by construction."""
    road = _road(tags={"highway": "motorway", "lanes": "3", "tunnel": "yes"})
    ap = _airport(law, [_pavement_with_corridor()], [road])
    cl = Classification(tuple(_cells()), (), {}, ())
    chans, _st = identify_channels(ap, cl, law)
    assert chans
    _cl2, tunnels, st = build_structures(ap, cl, law, channels=chans)
    assert not [t for t in tunnels if -500 in t.ways], [t.id for t in tunnels]
    assert any("NEVER a bore with mouths" in r for r in st.refused), st.refused


# ── (f) beyond an end ────────────────────────────────────────────────────

def test_f_the_channel_stops_at_its_ends(law):
    """(f) The channel's own faces exist only BETWEEN the ends.  Beyond
    them §37 governs and the floor rejoins the road's own profile: this
    lane emits nothing there."""
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    c = chans[0]
    s0, s1 = c.ends
    assert s1 > s0
    # every axis station stands inside the ends, and the profile with it
    assert c.profile[0][0] >= s0 - 1e-6 and c.profile[-1][0] <= s1 + 1e-6
    assert c.axis[0] == pytest.approx(tuple(_axis_at(c, s0)), abs=1e-6)


def _axis_at(c, s):
    from shapely.geometry import LineString as _LS
    p = _LS([(0.0, y) for y in range(-400, 401, 20)]).interpolate(s)
    return (p.x, p.y)


# ── (16) THE ENDS ────────────────────────────────────────────────────────

def test_16_the_ends_are_the_outermost_crossings(law):
    """§45 (16) (owner RULINGS 2026-09-15bo): the corridor's two ENDS are
    its OUTERMOST CROSSINGS, each extended by ONE DECK WIDTH — never the
    field boundary.  Round 7 measured the alternative once (14) admitted
    a notch: KPHX 5,750 m, HECA 14,562 m, CYXY 5,646 m of corridor."""
    necks = ((-40.0, -10.0), (120.0, 150.0))
    ap = _airport(law, [_pavement_with_corridor(necks=necks)], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert len(chans) == 1, (st.refused, st.notes)
    c = chans[0]
    s0, s1 = c.ends
    d0 = min(c.decks, key=lambda d: d.s0)
    d1 = max(c.decks, key=lambda d: d.s1)
    assert s0 == pytest.approx(d0.s0 - (d0.s1 - d0.s0), abs=1e-6)
    assert s1 == pytest.approx(d1.s1 + (d1.s1 - d1.s0), abs=1e-6)
    # …and that is a small fraction of the 800 m way the ends used to run
    assert (s1 - s0) < 260.0, (s0, s1)
    assert Polygon(c.region).bounds[3] < 200.0


def test_16_a_depth_witness_extends_the_ends(law):
    """§45 (16): "…and where a depth witness reaches further along the
    way, to the end of that witness" — the pack walls of (1) (c)."""
    necks = ((-40.0, -10.0), (120.0, 150.0))
    obj = _Placed("dsf:obj1", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    ap = _airport(law, [_pavement_with_corridor(necks=necks)], [_road()])
    cl = Classification(tuple(_cells()), (), {}, ())
    bare, _s = identify_channels(ap, cl, law)
    withw, _s2 = identify_channels(ap, cl, law, [obj])
    assert withw[0].datum_source == DATUM_PACK
    # the Trench-class wall runs 300 m past both crossings, so it does
    assert withw[0].ends[0] < bare[0].ends[0] - 100.0
    assert withw[0].ends[1] > bare[0].ends[1] + 100.0


def test_16_a_synthesised_underpass_bore_is_in_the_claimed_set(law):
    """§45 (16): the (13) (b) claimed set includes the §34 (5)
    SYNTHESISED underpass bores — every way a bore of ANY provenance
    names.  Round 7 measured their absence: wiring (14) took KCLT
    taxiway U's four bores (tunnels 23 -> 19)."""
    # a taxiway bridge over a road, with a taxi cell stating the deck:
    # §34 (5) bores the road under it, and that bore's way is claimed
    bridge = OsmWay(-900, "airports", ((-60.0, 0.0), (60.0, 0.0)), False,
                    {"aeroway": "taxiway", "bridge": "yes", "layer": "1",
                     "width": "40"})
    ap = _airport(law, [_pavement_with_corridor()], [_road(), bridge])
    cl = Classification(tuple(_cells()), (), {}, ())
    with_cl = claimed_crossing_ways(ap, law, (), cl)
    without = claimed_crossing_ways(ap, law, ())
    assert ("big_roads", -500) in with_cl, with_cl
    assert ("big_roads", -500) not in without
    # and the channel pass then never takes that way
    chans, st = identify_channels(ap, cl, law, (), with_cl)
    assert chans == [], [c.id for c in chans]
    assert any("already models them" in n for n in st.notes), st.notes


# ── (17) THE FLOOR AND THE AIRSIDE SURFACE NEVER SHARE A VERTEX ─────────

def test_17_the_band_is_never_thinner_than_a_bores(law):
    """§45 (17) (owner RULINGS 2026-09-15bo): the channel's wall band is
    the bore's own stand-off at the least — ``[tunnel] wall_gap_m +
    wall_band_width_m``, the ``rim_off`` ``planar/structures`` mints its
    ``retaining_wall`` void with."""
    tn = law.tables.structures.tunnel
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    c = chans[0]
    assert c.wall_band_m >= tn.wall_gap_m + tn.wall_band_width_m - 1e-9
    # the crest ring stands the band outside the floor ring, both sides
    assert (Polygon(c.crest_ring).bounds[2] - Polygon(c.region).bounds[2]) \
        == pytest.approx(c.wall_band_m, abs=1e-6)


def test_17_the_floor_never_touches_a_deck(law):
    """§45 (17): the floor stands the band back from every DECK too — a
    deck's faces are AIRSIDE and meet the band's CREST, never the floor.
    The KDFW measurement: 378 ``channel_floor_at_declaration`` rows,
    worst 12.626 m, on vertices the floor shared with an airside cell."""
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    c = chans[0]
    cells, _knives = channel_cells(chans, law)
    floor = [p for r, _ref, p, _cid in cells if r == "tunnel_trench"]
    bank = [p for r, _ref, p, _cid in cells if r == "retaining_wall"]
    assert floor and bank
    for d in c.decks:
        deck = Polygon(d.ring)
        for f in floor:
            assert f.distance(deck) >= c.wall_band_m - 1e-6, (f.bounds, deck.bounds)
        # …and the band DOES reach the deck: the crest is what it meets
        assert min(b.distance(deck) for b in bank) < 1e-6


def test_17_declared_at_reads_the_profile_at_the_axis_station(law):
    """§45 (17): ``verify/channel._declared_at`` reads the floor the way
    the floor was STATED — the profile's ``z(s)`` at the vertex's own
    axis station.  The first arm interpolated between the two NEAREST
    stations, which off the centreline picks two on the same side and
    answers a different number (RULINGS 2026-09-15bm)."""
    from auto_patch_v2.verify.channel import _declared_at

    class _P:                       # the two Patch members _declared_at reads
        @staticmethod
        def to_m(la, lo):
            return (float(lo), float(la))

    # an axis along +lat with a 1 m/station ramp
    prof = [(0.0, 0.0, 10.0), (10.0, 0.0, 11.0), (20.0, 0.0, 12.0)]
    # ON the axis: the station's own value
    assert _declared_at(_P, prof, 10.0, 0.0) == pytest.approx(11.0)
    assert _declared_at(_P, prof, 5.0, 0.0) == pytest.approx(10.5)
    # OFF the axis by 40 m — the station is unchanged, so the value is
    assert _declared_at(_P, prof, 5.0, 40.0) == pytest.approx(10.5)
    assert _declared_at(_P, prof, 15.0, -40.0) == pytest.approx(11.5)
    # beyond either end it clamps to that end's declaration
    assert _declared_at(_P, prof, -30.0, 0.0) == pytest.approx(10.0)
    assert _declared_at(_P, prof, 60.0, 5.0) == pytest.approx(12.0)


# ── (g) the flat-site region ─────────────────────────────────────────────

def test_g_the_flat_site_region_excludes_the_corridor(law):
    """(g) §45 (8): "a channel is never flattened"."""
    from shapely.ops import unary_union
    from auto_patch_v2.constraints.flat_site import region_geometry
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    region = region_geometry(((_rect(-450.0, -400.0, 450.0, 400.0), ()),))
    cut = unary_union([Polygon(c.crest_ring or c.region) for c in chans])
    assert not cut.is_empty
    minus = region.difference(cut)
    assert minus.area < region.area
    # and nothing of the corridor survives in it
    assert minus.intersection(cut).area < 1.0


# ── (h) the register carries both families ───────────────────────────────

def test_h_law_families_carries_the_two_channel_families():
    """(h) The harness twin's own assertion, made here too so the lane's
    suite fails on its own if the register drifts."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "tools"))
    import check_grade as cg
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert "channel_floor_at_declaration" in keys
    assert "channel_crest_at_edge" in keys
    from auto_patch_v2.verify.census import READERS
    assert "channel_floor_at_declaration" in READERS
    assert "channel_crest_at_edge" in READERS
    from auto_patch_v2.law.tables import load_default
    fams = set(load_default().tables.families)
    assert {"channel_floor_at_declaration", "channel_crest_at_edge"} <= fams


# ── §45 (12): a single neck is a CROSSING, not a channel ─────────────────

def test_a_neck_only_channel_with_one_crossing_is_refused_by_name(law):
    """§45 (12), the lane's reading of "name it or refuse it" for LGAV's
    way −4003: a channel witnessed by a paved neck ALONE, whose floor
    therefore comes from (3) (iii), needs more than one crossing.  With
    one anchor "Cut the road down" ramps the floor away at
    ``ramp_max_grade`` for the whole axis — at LGAV that read 80.24…103.44 m
    under a 416 m ``highway=service`` road crossing a borrowed Global
    apron."""
    ch = law.tables.structures.channel
    assert ch.min_decks_without_depth >= 2
    ap = _airport(law, [_pavement_with_corridor(necks=((-40.0, -10.0),))], [_road()])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert chans == [], [c.id for c in chans]
    assert any("a single neck is a CROSSING" in r for r in st.refused), st.refused


def test_a_pack_witness_is_judged_against_its_OWN_local_ground(law):
    """§45 (1) (c) as round 2 measured it: the depth gate reads the
    placement's own ``solid_min_depth_m`` — the terrain over THAT
    component — not the mean DEM of the whole axis.  LGAV's axis is
    1,954 m over 12.6 m of relief, so its mean read 67.48 while
    ``Trench_07`` (own depth −11.03 m) scored 1.02 and was refused at
    ``object_min_depth_m`` 3.0."""
    from auto_patch_v2.planar.channel import _depth_under_crest

    class _O:
        solid_min_depth_m = -11.03
        solid_min_z = 66.47
    assert _depth_under_crest(_O(), 67.48) == pytest.approx(11.03)

    class _NoLocal:
        solid_min_depth_m = None
        solid_min_z = 60.0
    assert _depth_under_crest(_NoLocal(), 67.48) == pytest.approx(7.48)


# ── §45 (13) A CHANNEL NEVER TAKES A MODELLED CROSSING ───────────────────

def test_13a_a_bridge_only_witness_is_an_underpass_not_a_channel(law):
    """§45 (13) (a) (owner RULINGS 2026-09-15aa): a crossing witnessed by
    an aeroway ``bridge=yes`` way ALONE keeps §34 (5)'s bore-with-mouths
    model.  Measured at KCLT — on a bridge witness alone the pass took
    taxiway U's crossing and deleted the four bores
    ``tunnel:-14074@0..3`` the underpass pass had built."""
    # a real corridor but NO neck anywhere, so nothing but the taxiway
    # bridge can witness the crossing
    bridge = OsmWay(-900, "airports", ((-60.0, 0.0), (60.0, 0.0)), False,
                    {"aeroway": "taxiway", "bridge": "yes", "layer": "1"})
    ap = _airport(law, [_pavement_with_corridor(necks=())], [_road(), bridge])
    chans, st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    assert chans == [], [c.id for c in chans]
    assert any("witnessed by an aeroway bridge ALONE" in r for r in st.refused), st.refused


def test_13b_a_way_the_engine_already_models_is_never_a_channel_candidate(law):
    """§45 (13) (b): a way a mapped ``tunnel=yes`` bore or a 05k-1 object
    corridor claims is excluded from EVERY channel candidate, and a pack
    witness does not override it."""
    obj = _Placed("dsf:obj1", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    # unclaimed: the channel stands
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()),
                                   law, [obj])
    assert len(chans) == 1 and chans[0].datum_source == DATUM_PACK
    # claimed: nothing is left to witness, pack witness notwithstanding
    chans2, st2 = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()),
                                    law, [obj], claimed_ways={-500})
    assert chans2 == [], [c.id for c in chans2]
    assert any("already models them" in n for n in st2.notes), st2.notes


def test_a_colliding_negative_id_in_two_feeds_is_two_ways(law):
    """THE FEEDS' NEGATIVE IDS COLLIDE (owner addendum 2026-09-15,
    measured by the schema session: 8 of 11 LEMD deck ids carry two
    ways — one from a road feed, one from the airports feed).  So every
    cross-pass join carries the FEED.  Here the SAME id ``-500`` names
    the channel's motorway (``big_roads``) and an unrelated airports-feed
    way tagged ``tunnel=yes``: under a bare-id join the airports way's
    claim would delete the road's channel.
    """
    obj = _Placed("dsf:obj1", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    twin = OsmWay(-500, "airports", ((200.0, -50.0), (200.0, 50.0)), False,
                  {"highway": "service", "tunnel": "yes"})
    ap = _airport(law, [_pavement_with_corridor()], [_road(), twin])
    cl = Classification(tuple(_cells()), (), {}, ())

    # the claimed set is the airports way ALONE …
    claimed = claimed_crossing_ways(ap, law, ())
    assert ("airports", -500) in claimed
    assert ("big_roads", -500) not in claimed

    # … so the road-feed way of the same id keeps its channel
    chans, st = identify_channels(ap, cl, law, [obj], claimed)
    assert len(chans) == 1, [c.id for c in chans]
    assert chans[0].way_keys == (("big_roads", -500),)
    # the airports way IS excluded (it is the claimed one) — exactly one,
    # and not the road that shares its id
    assert any("1 way(s) excluded" in n for n in st.notes), st.notes

    # and the channel's OWN way, joined by key, never yields the other
    # feed's bore: channel_ways is keys, so -500@airports is not owned
    assert channel_ways(chans) == {("big_roads", -500)}
    refused: list[str] = []
    kept, _c, _g = channel_yields(chans, [twin], (), (), refused)
    assert [w.kind for w in kept] == ["airports"], refused
    assert refused == []


def test_1a_reads_decks_through_section_34s_own_deck_read(law):
    """§45 (1) (a) asks §34 (5)'s question, so it calls §34 (5)'s
    function (owner addendum 2026-09-15).  The channel pass holds no
    copy of the tag predicate or the layer parse — which is what lets
    §34 (12) (4)'s below-grade witness reach the channel the day
    ``v2vmmcshore`` r6 lands it in ``aeroway_decks``."""
    import inspect
    from auto_patch_v2.planar import channel as _ch
    from auto_patch_v2.planar.structure_underpass import aeroway_decks
    src = inspect.getsource(_ch._aeroway_bridges)
    assert "aeroway_decks(" in src
    body = src.split('"""')[-1]            # the code, not the citation
    assert "is_aeroway_bridge(" not in body and "underpass_min_layer" not in body
    assert "underpass_min_layer" in inspect.getsource(aeroway_decks)


def test_13b_the_claimed_set_is_read_off_the_passes_own_outputs(law):
    """§45 (13) (b): ``claimed_crossing_ways`` is the ONE derivation and
    it reads the existing outputs — the mapped bores' own predicate and
    each object corridor's ``bore_ways`` — never a second rule."""
    bore = OsmWay(-701, "big_roads", ((0.0, -50.0), (0.0, 50.0)), False,
                  {"highway": "secondary", "tunnel": "yes"})
    plain = OsmWay(-702, "big_roads", ((5.0, -50.0), (5.0, 50.0)), False,
                   {"highway": "secondary"})
    ap = _airport(law, [], [bore, plain])

    class _Cor:
        bore_ways = (-702, -999)
    got = claimed_crossing_ways(ap, law, [_Cor()])
    # EVERY claim carries its FEED (owner addendum 2026-09-15: the feeds'
    # negative ids collide), so the set is ``(feed, id)`` keys
    assert ("big_roads", -701) in got   # the mapped bore, by the tunnel predicate
    assert ("big_roads", -702) in got   # the object corridor's own claim, qualified
    assert ("*", -999) in got           # …and one no feed carries, kept as ANY_FEED
    assert all(isinstance(k, tuple) for k in got), got


def test_channel_claiming_is_callable_from_its_own_module(law):
    """A REGRESSION TWIN, and the measurement that earned it: splitting
    ``planar/channel.py`` moved ``channel_claiming`` into
    ``planar/channel_claims.py`` while its ``_depth_under_crest`` helper
    stayed behind, and nothing caught it until LEMD's round-4 replay died
    with ``NameError: name '_depth_under_crest' is not defined`` inside
    ``build_basins``.  Every other twin reached ``in_any_corridor``
    instead, so the real basin-intake call had no cover at all."""
    from shapely.geometry import Polygon as _P
    from auto_patch_v2.model.structures import Channel as _C

    class _O:
        below_grade = _P(_rect(0.0, 0.0, 10.0, 10.0))
        solid_min_z = 80.0

    c = _C(id="channel:0", ways=(), axis=((0.0, 0.0), (1.0, 1.0)),
           profile=((0.0, 80.0),), region=_rect(-50.0, -50.0, 50.0, 50.0),
           crest_estimate_m=100.0)
    assert channel_claiming([c], _O(), law) == "channel:0"

    class _Shallow(_O):
        solid_min_z = 99.0          # 1 m under the crest, under the 3 m gate
    assert channel_claiming([c], _Shallow(), law) == ""


# ── §45 (13) (d) A BASIN'S OWN SHELL IS NEVER A CHANNEL'S WALL ───────────

def test_13d_a_basin_shell_beside_a_neck_is_no_channel_witness(law):
    """§45 (13) (d) (owner RULINGS 2026-09-15ac).  The SAME placement,
    at the same place, with the same depth: admitted as a (1) (c)
    wall/floor witness when it is not a pit, refused when the basin
    pass's own ``basin_member_ids`` says it carries a floor witness.
    And with it goes the channel's only depth witness, so (13) (c) then
    refuses the channel outright — which is what leaves LEMD's T4S
    ``basin:0`` its three members.
    """
    shell = _Placed("dsf:obj7", Polygon(_rect(-8.0, -300.0, 8.0, 300.0)), 88.0)
    # ONE neck only, so the channel's admission rests on the pack witness
    ap = _airport(law, [_pavement_with_corridor(necks=((-40.0, -10.0),))], [_road()])
    cl = Classification(tuple(_cells()), (), {}, ())

    # not a pit: the pack witness carries the channel (datum "pack")
    chans, _st = identify_channels(ap, cl, law, [shell])
    assert len(chans) == 1, [c.id for c in chans]
    assert chans[0].datum_source == DATUM_PACK
    assert "dsf:obj7" in chans[0].witness_ids

    # a pit shell: no (1) (c) witness, and with no depth witness left the
    # one-neck channel falls to (13) (c)
    chans2, st2 = identify_channels(ap, cl, law, [shell],
                                    pit_shell_ids={"dsf:obj7"})
    assert chans2 == [], [c.id for c in chans2]
    assert any("a single neck is a CROSSING" in r for r in st2.refused), st2.refused
    # and the drop NAMES the placement it lost — a refused channel writes
    # no record of its own, so without this line the only way to learn
    # WHICH object the pit test took is a full airport load (the LGAV
    # round-5 arm paid that twice)
    assert any("(13) (d) dropped" in n and "dsf:obj7" in n for n in st2.notes), st2.notes


def test_14_a_notch_is_a_corridor_too(law):
    """§45 (14) (owner RULINGS 2026-09-15bk).  The SAME corridor, once
    closed by the airfield (an interior hole) and once open to the edge
    (a notch): both are the complement of the pavement union inside the
    field, so both carry necks.  KPHX measured the difference — two
    taxiway decks over E Sky Harbor Blvd and ``necks = 0`` because the
    corridor reaches the boundary."""
    from shapely.geometry import Polygon as _P
    from auto_patch_v2.planar.channel_geometry import _field_region, _hole_region

    # a slab with a corridor cut IN FROM THE EDGE: |y| >= 350 is open
    notched = _P(_rect(-400.0, -400.0, 400.0, 400.0)).difference(
        _P(_rect(-40.0, -400.0, 40.0, 350.0)))
    assert _hole_region(notched) is None            # no interior ring at all
    field = _field_region(_airport(law, [], []), notched, law)
    reg = _hole_region(notched, field)
    assert reg is not None and not reg.is_empty
    # the corridor itself is in the region …
    assert reg.contains(_P(_rect(-20.0, -100.0, 20.0, 100.0)).centroid)
    # … and the pavement is not
    assert not reg.intersects(_P(_rect(100.0, -100.0, 200.0, 100.0)))


def test_13d_the_decision_pass_is_skipped_when_no_channel_has_a_pack_witness(law):
    """The ordering costs an extra structure+basin pass, so it is only
    paid where it can matter: with no pack wall/floor witness anywhere,
    no pit test can change the reading and the decision pair is not run
    (OTHH, KCLT, CYXY, SPJC)."""
    import inspect
    from auto_patch_v2.planar.build import channels_after_basins
    src = inspect.getsource(channels_after_basins)
    # the short circuit precedes the decision pair in the source
    assert src.index("if not any(c.witness_ids") < src.index("build_structures(")


def test_45_7_is_a_post_filter_on_a_built_basin(law):
    """§45 (7)/(11) AMENDED: a basin is swallowed only when its region
    lies inside the corridor AND every member is one of that channel's
    own witnesses — and a pit BESIDE the corridor, or one inside it made
    of placements the channel never witnessed, keeps its basin."""
    from shapely.geometry import Polygon as _P
    from auto_patch_v2.planar.channel_claims import channel_swallowing

    class _C:
        id = "channel:0"
        region = tuple(_rect(-60.0, -300.0, 60.0, 300.0))
        crest_ring = ()
        witness_ids = ("dsf:objA", "dsf:objB")

    inside = _P(_rect(-10.0, -10.0, 10.0, 10.0))
    beside = _P(_rect(200.0, -10.0, 220.0, 10.0))
    assert channel_swallowing([_C()], inside, ["dsf:objA"]) == "channel:0"
    assert channel_swallowing([_C()], beside, ["dsf:objA"]) == ""      # §45 (11)
    assert channel_swallowing([_C()], inside, ["dsf:objZ"]) == ""      # not its wall
    assert channel_swallowing([_C()], inside, ["dsf:objA", "dsf:objZ"]) == ""
    assert channel_swallowing([], inside, ["dsf:objA"]) == ""


def test_13d_reuses_the_basin_passs_own_derivation(law):
    """The pit test is NOT re-derived in the channel pass: the exclusion
    is handed in, and under §45 (13) (d) AMENDED (RULINGS 2026-09-15aw)
    it comes from the BASIN PASS ITSELF — the ``member_ids`` of the
    basins ``build_basins`` actually built, never a second pit test."""
    import inspect
    from auto_patch_v2.planar import channel as _ch
    # NB ``from auto_patch_v2.planar import build`` is the FUNCTION
    # (re-exported by the package), not this module
    from auto_patch_v2.planar.build import channels_after_basins
    src_b = inspect.getsource(channels_after_basins)
    assert "build_basins(" in src_b and "member_ids" in src_b
    # the candidate set is NOT what keys it any more
    assert "basin_member_ids(" not in src_b   # the CALL, not the citation
    # the channel pass only CONSUMES the set — it never CALLS the
    # derivation (the name appears in its citation comment, which is the
    # point: one site, cited where it is used)
    src = inspect.getsource(_ch)
    assert "pit_shells" in src
    assert "basin_member_ids(" not in src
    assert "read_objects(" not in src
