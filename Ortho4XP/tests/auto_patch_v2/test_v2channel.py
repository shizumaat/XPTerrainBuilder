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
                                          channel_cells, identify_channels)
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
    from auto_patch_v2.planar.channel import in_any_corridor
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
    """(f) The channel's own faces exist only BETWEEN the ends — the two
    stations where the corridor leaves the pavement union ⊕
    ``mouth_standoff_m``.  Beyond them §37 governs and the floor rejoins
    the road's own profile: this lane emits nothing there."""
    tn = law.tables.structures.tunnel
    ap = _airport(law, [_pavement_with_corridor()], [_road()])
    chans, _st = identify_channels(ap, Classification(tuple(_cells()), (), {}, ()), law)
    c = chans[0]
    s0, s1 = c.ends
    assert s1 > s0
    # every axis station stands inside the ends, and the profile with it
    assert c.profile[0][0] >= s0 - 1e-6 and c.profile[-1][0] <= s1 + 1e-6
    # the corridor reaches no further than the field ⊕ the standoff
    region = Polygon(c.region)
    assert region.bounds[1] >= -400.0 - tn.mouth_standoff_m - 1.0
    assert region.bounds[3] <= 400.0 + tn.mouth_standoff_m + 1.0


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
