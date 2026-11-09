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
from test_deck_bridge1671 import (FRAME, LAW, THICK, _box, _cell, _classification, _placed,
                                  _write)
from test_portal_objects1343 import BORE, _placed as _portal_placed, _portal


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
