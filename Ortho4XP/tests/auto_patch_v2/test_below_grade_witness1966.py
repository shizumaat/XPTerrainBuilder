"""THE BELOW-GRADE WITNESS (owner RULINGS 2026-11-07b (1); #1966 KEYW, #1972
KDEN): a cut stands only where something stands below the AUTHOR'S ground
(``airport/below_grade_witness``) — a hard deck whose top already clears a road over
that ground is an elevated deck (a garage roof), and a roofed object over a
bore end whose bottom stands on that ground is a building over the road at
grade (a toll booth), not a portal; the bore that ends in it is no terrain
tunnel.
"""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import below_grade_witness as BG
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.planar import deck_bridge as DB
from test_deck_bridge1671 import FRAME, LAW, THICK, _box, _cell, _classification, _placed, _write
from test_portal_objects1343 import BORE, _portal
from test_portal_objects1343 import _placed as _portal_placed


class _Dem:
    """A flat ground at ``z``, or one ``rise`` m higher beyond ``r`` m of
    the origin (the ground a portal's road runs down into)."""

    def __init__(self, z=100.0, rise=0.0, r=12.0):
        self.zz, self.rise, self.r = z, rise, r

    def z(self, x, y):
        return self.zz + (self.rise if np.hypot(x, y) > self.r else 0.0)

    def z_many(self, xs, ys):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        return self.zz + np.where(np.hypot(xs, ys) > self.r, self.rise, 0.0)


def _airport(dem):
    return types.SimpleNamespace(frame=FRAME, dem=dem, dsf_objects=())


def _garage(tmp_path, roof=12.3):
    """A 40 x 40 m roof deck ``roof`` m over the zero on walls from the
    ground (y 0) up — a garage's top level, its zero on the ground."""
    legs = [_box(-20.0, -20.0, 3.0, 40.0, roof - 0.3), _box(17.0, -20.0, 3.0, 40.0, roof - 0.3)]
    return _write(tmp_path / "garage.obj",
                  [_box(-20.0, -20.0, 40.0, 40.0, 0.3, y0=roof - 0.3)] + legs, hard=(0,))


def _road_cells():
    """An apron running E-W across the deck, on both sides of it — no taxi
    route: the deck carries no movement (KEYW's garage abuts apron)."""
    from shapely.geometry import box as _b
    return types.SimpleNamespace(cells=tuple(
        _cell(i, "apron", _b(*xs)) for i, xs in
        enumerate(((-100.0, -10.0, -20.0, 10.0), (20.0, -10.0, 100.0, 10.0)))))


def _decks(tmp_path, path, dem, top, cl=None):
    o = _placed(path, "dsf:obj7")
    o.deck_top_z = 100.0 + top
    return DB.deck_bridges([o], O.ResourceCache(THICK), cl or _road_cells(), _airport(dem),
                           LAW, ())


def test_depth_under_reads_the_author_ground_else_the_dem(tmp_path):
    from shapely.geometry import box
    g = BG._Ground(BG.author_ground([], O.ResourceCache(THICK), LAW, {}), _Dem().z_many, {})
    b = BG.depth_under(95.0, box(-5, -5, 5, 5), set(), g, LAW)
    assert abs(b.depth - 5.0) < 1e-9 and "NO PLATES: the DEM 100.00" in b.why


def test_a_garage_roof_over_flat_ground_is_an_elevated_deck_not_a_bridge(tmp_path):
    got, notes = _decks(tmp_path, _garage(tmp_path), _Dem(), 12.3)
    assert got == () and "an ELEVATED deck" in notes[0] and "#1966" in notes[0]


def test_a_bridge_deck_at_the_ground_still_bridges_the_road_under_it(tmp_path):
    """KBNA: the road the frame stands on runs under the author's ground
    round the deck — a bridge."""
    from test_deck_bridge1671 import _deck
    got, notes = _decks(tmp_path, _deck(tmp_path), _Dem(z=106.0), 6.0)
    assert len(got) == 1 and not notes


def test_a_taxiway_across_a_deck_is_its_own_witness(tmp_path):
    """LFPG / EDDF: a taxiway across the deck — an aircraft never climbs an
    elevated deck, so the deck is the airside ground however flat the DEM."""
    got, notes = _decks(tmp_path, _garage(tmp_path), _Dem(), 12.3, cl=_classification())
    assert len(got) == 1 and not any("ELEVATED" in n for n in notes)


def _portals(tmp_path, dem):
    ground = BG.ground_of(_airport(dem), [], O.ResourceCache(THICK), LAW)
    o = _portal_placed(_portal(tmp_path))
    o.kind, o.anchor_z, o.agl_m = "OBJECT", 100.0, 0.0
    grade: list = []
    got, refused = P.read_portals([o], O.ResourceCache(THICK), LAW, [BORE], ground=ground,
                                  at_grade=grade)
    return got, refused, grade


def test_a_roofed_box_over_a_bore_end_on_flat_ground_is_a_building_at_grade(tmp_path):
    """KDEN's toll booths: the roof over the road, the ground round it at
    its zero — no portal, and the bore end is recorded as standing in it."""
    got, refused, grade = _portals(tmp_path, _Dem())
    assert got == [] and "a building over the road at grade" in refused[0]
    assert len(grade) == 1 and grade[0].way_id == -756 and grade[0].end_xy == (0.0, 0.5)


def test_a_portal_the_ground_stands_over_is_still_a_portal(tmp_path):
    """KBUF: the road at the portal's zero runs under the ground round it."""
    got, refused, grade = _portals(tmp_path, _Dem(rise=6.0, r=3.0))
    assert len(got) == 1 and not refused and grade == []


def test_an_agl_row_states_its_own_depth_over_an_anchor_bump(tmp_path):
    """#1949 OMDB ``tunner_5_1``: an AGL -4.8 portal whose anchor stands on
    a surface-model bump (the DEM there 8.43 over a 4.21 ground round it)
    still states its road 4.8 m under the ground it is drawn on — a portal,
    not a building at grade."""
    ground = BG.ground_of(_airport(_Dem()), [], O.ResourceCache(THICK), LAW)
    o = _portal_placed(_portal(tmp_path))
    o.kind, o.anchor_z, o.agl_m = "OBJECT_AGL", 104.0, -4.8
    got, refused = P.read_portals([o], O.ResourceCache(THICK), LAW, [BORE], ground=ground)
    assert len(got) == 1 and not refused


def test_an_agl_zero_row_in_a_dem_trench_still_reads_the_trench(tmp_path):
    """The deeper reading counts: an AGL-0 portal whose anchor stands in a
    trench the DEM itself sees (the ground round it 6 m higher) is a portal."""
    from shapely.geometry import box
    g = BG._Ground(BG.author_ground([], O.ResourceCache(THICK), LAW, {}),
                   _Dem(rise=6.0, r=3.0).z_many, {})
    o = types.SimpleNamespace(kind="OBJECT", anchor_z=100.0, agl_m=0.0)
    b = BG.row_depth_under(o, 0.0, box(-1, -1, 1, 1), set(), g, LAW)
    assert abs(b.depth - 6.0) < 1e-9
    o.agl_m = -3.0     # the anchor reading (9 m) is deeper than the statement (3 m)
    assert abs(BG.row_depth_under(o, 0.0, box(-1, -1, 1, 1), set(), g, LAW).depth - 9.0) < 1e-9
    o.anchor_z, o.agl_m = 110.0, -8.0     # an anchor bump: the statement is deeper
    b = BG.row_depth_under(o, 0.1, box(-1, -1, 1, 1), set(), g, LAW)
    assert abs(b.depth - 7.9) < 1e-9 and "its AGL -8.00" in b.why


def test_an_msl_row_states_no_ground(tmp_path):
    from shapely.geometry import box
    g = BG._Ground(BG.author_ground([], O.ResourceCache(THICK), LAW, {}), _Dem().z_many,
                   {"m": 99.0})
    o = types.SimpleNamespace(kind="OBJECT_MSL", id="m", anchor_z=0.0, agl_m=-50.0)
    assert abs(BG.row_depth_under(o, 0.0, box(-1, -1, 1, 1), set(), g, LAW).depth - 1.0) < 1e-9


def test_an_agl_zero_row_states_no_depth_from_its_buried_skirts():
    """#2010 EGKK ``S_PAVEMENT_1``: a row drawn ON the ground (AGL 0) whose
    solid runs 2 m under its zero (its skirts) states no depth: the anchor
    reading counts (1.7 m under a ground 0.3 m lower around it), never the
    2.0 m its skirts would state."""
    from shapely.geometry import box
    g = BG._Ground(BG.author_ground([], O.ResourceCache(THICK), LAW, {}),
                   _Dem(z=100.0, rise=-0.3, r=3.0).z_many, {})
    o = types.SimpleNamespace(kind="OBJECT", anchor_z=100.0, agl_m=0.0)
    b = BG.row_depth_under(o, -2.0, box(-1, -1, 1, 1), set(), g, LAW)
    assert abs(b.depth - 1.7) < 1e-9 and "AGL" not in b.why
    o.agl_m = -0.5     # a SUNK row states its depth: 0.5 + 2.0 under the ground
    assert abs(BG.row_depth_under(o, -2.0, box(-1, -1, 1, 1), set(), g, LAW).depth - 2.5) < 1e-9


class _EastRise(_Dem):
    """Flat ground at the bore end; the ground ``rise`` m higher east of
    x = 150 (the far end of a long object's plan)."""

    def z_many(self, xs, ys):
        xs = np.asarray(xs, float)
        return self.zz + np.where(xs > 150.0, self.rise, 0.0)


def test_the_ground_is_read_round_the_roof_over_the_bore_end(tmp_path):
    """#2086 LEMG ``LEMGterminalMagenta-LEMG62.obj``: a long object roofed in
    many places — the ground stands on its roof only far from the bore end,
    where the road runs at grade under it: a building over the road at
    grade, never a portal read off its farthest roofs."""
    from shapely.geometry import MultiPolygon, box
    ground = BG.ground_of(_airport(_EastRise(rise=6.0)), [], O.ResourceCache(THICK), LAW)
    o = _portal_placed(_portal(tmp_path))
    o.kind, o.anchor_z, o.agl_m = "OBJECT", 100.0, 0.0
    near, far = box(-5.0, -5.0, 5.0, 5.0), box(240.0, -60.0, 360.0, 60.0)
    roof = MultiPolygon([near, far])
    cache = O.ResourceCache(THICK)
    assert P._at_grade(o, cache, roof, LAW, ground) == ""     # read round every roof
    over = P._roof_over(roof, [(0.0, 0.5)], 5.0)
    assert over.equals(near)
    assert "a building over the road at grade" in P._at_grade(o, cache, over, LAW, ground)
    assert P._roof_over(near, [(0.0, 0.5)], 5.0) is near


def _mouth_portals(tmp_path, bores):
    ground = BG.ground_of(_airport(_Dem()), [], O.ResourceCache(THICK), LAW)
    o = _portal_placed(_portal(tmp_path))
    o.kind, o.anchor_z, o.agl_m = "OBJECT", 100.0, 0.0
    grade: list = []
    got, refused = P.read_portals([o], O.ResourceCache(THICK), LAW, bores, ground=ground,
                                  at_grade=grade)
    return got, refused, grade


def test_a_roofed_object_at_grade_on_a_long_bore_is_its_tunnel_mouth(tmp_path):
    """KBUF ``Road_Tunnel.obj`` (owner RULINGS 2026-11-21d, #2221): a mouth
    object at grade on the uncut ground over the end of a bore that runs
    far past it — the bore drawn as two ways joined end to end — is that
    tunnel's portal, and its end stands at grade in no building."""
    far = types.SimpleNamespace(id=-757, points=[(0.0, 60.0), (0.0, 240.0)])
    got, refused, grade = _mouth_portals(tmp_path, [BORE, far])
    assert [p.way_id for p in got] == [-756] and grade == []
    assert got[0].at_grade
    assert "a tunnel mouth (RULINGS 2026-11-21d)" in refused[0]


def test_a_roofed_object_at_grade_on_a_stub_its_own_length_stays_at_grade(tmp_path):
    """KDEN's booths: the stub runs about the booth's own length — the
    booth stays a building over the road at grade (2026-11-21d)."""
    stub = types.SimpleNamespace(id=-758, points=[(0.0, 0.5), (0.0, 30.0)])
    got, refused, grade = _mouth_portals(tmp_path, [stub])
    assert got == [] and [g.way_id for g in grade] == [-758]
    assert "a building over the road at grade" in refused[0]


def test_bore_runs_join_ways_end_to_end():
    a = types.SimpleNamespace(id=1, points=[(0.0, 0.0), (0.0, 10.0)])
    b = types.SimpleNamespace(id=2, points=[(0.0, 10.0), (0.0, 40.0)])
    c = types.SimpleNamespace(id=3, points=[(50.0, 0.0), (55.0, 0.0)])
    assert P._bore_runs([a, b, c]) == {1: 40.0, 2: 40.0, 3: 5.0}
