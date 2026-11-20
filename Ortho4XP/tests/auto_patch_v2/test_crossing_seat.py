"""RULINGS 2026-11-20g / 20k (``airport/crossing_seat``): a pack frame's deck
spanning a mapped road under the class minimum is ONE record at the frame's
seat (its building's ground vote); a road above the soffit lists the group;
a footway is no road."""
from __future__ import annotations

import math
import types

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.crossing_seat import crossing_records, published
from auto_patch_v2.law import Law
from auto_patch_v2.model.rebake import Part

LA0, LO0 = 40.0, -80.0
ML, MO = 111132.0, 111320.0 * math.cos(math.radians(LA0))


def _to_xy(lo, la):
    return ((lo - LO0) * MO, (la - LA0) * ML)


def _ll(x, y):
    return (LA0 + y / ML, LO0 + x / MO)


def _box(x0, x1, y0, y1, z0, z1):
    """A closed box in OBJ8 axes (x east, y up, z south): 8 vertices, 12 tris."""
    vs = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = [t for a, b, c, d in q for t in ((a, b, c), (a, c, d))]
    return vs, tris


def _obj(path, boxes):
    vs, idx = [], []
    for b in boxes:
        v, t = _box(*b)
        idx += [k + len(vs) for tri in t for k in tri]
        vs += v
    with open(path, "w") as fh:
        fh.write(f"I\n800\nOBJ\n\nTEXTURE none.png\nPOINT_COUNTS {len(vs)} 0 0 {len(idx)}\n")
        for x, y, z in vs:
            fh.write(f"VT {x} {y} {z} 0 1 0 0 0\n")
        for k in range(0, len(idx), 10):
            fh.write("IDX10 " + " ".join(map(str, idx[k:k + 10])) + "\n"
                     if len(idx[k:k + 10]) == 10 else
                     "".join(f"IDX {i}\n" for i in idx[k:k + 10]))
        fh.write(f"TRIS 0 {len(idx)}\n")


def _frame(tmp_path, road_y: float, highway: str = "service", dem: float = 10.0):
    """A building (x -40..-10, walls 0..8 m) and a 6 m deck at y 3.0..3.3
    from it over x -10..30 (z -3..3); a road along x = 10 (north-south)."""
    path = str(tmp_path / "terminal.obj")
    _obj(path, [(-40, -10, 0, 8, -10, 10), (-10, 30, 3.0, 3.3, -3, 3)])
    cache = obj8.ResourceCache(0.05)
    comps = cache.components(path)
    parts = []
    for ci, c in enumerate(comps):
        xs = (-40, -10) if c.max_y > 5 else (-10, 30)
        zs = (-10, 10) if c.max_y > 5 else (-3, 3)
        ring = tuple(_ll(x, -z) for x, z in ((xs[0], zs[0]), (xs[1], zs[0]),
                                             (xs[1], zs[1]), (xs[0], zs[1])))
        feet = (tuple((*_ll(x, -z), 0.0) for x in xs for z in zs) if c.max_y > 5 else ())
        la, lo = _ll(sum(xs) / 2, -sum(zs) / 2)
        parts.append(Part(ci, ci, la, lo, float(c.min_y), (xs[1] - xs[0]) * (zs[1] - zs[0]),
                          (0, 0, 0, 0), feet=feet, rings=(ring,),
                          height_m=float(c.max_y - c.min_y)))
    m = types.SimpleNamespace(id="dsf:obj1", resource="terminal.obj", authored_path=path,
                              live_path=path, heading_deg=0.0, parts=tuple(parts),
                              origin=(LA0, LO0), scatter=False, free_bridge="",
                              deck_kind="", deck_ring=None, deck_top_y=None,
                              elevated_deck=False, plate_kind="")
    u = types.SimpleNamespace(id="unit:0", anchor=(LA0, LO0), agl_m=0.0, members=(m,))
    way = types.SimpleNamespace(id="w1", tags={"highway": highway},
                                points=[(10.0, -40.0), (10.0, 40.0)])
    ap = types.SimpleNamespace(
        partition=types.SimpleNamespace(units=(u,)), osm_ways=(way,),
        frame=types.SimpleNamespace(entry=lambda: _to_xy),
        dem=types.SimpleNamespace(z=lambda x, y: road_y if abs(x - 10.0) < 6 else dem))
    return ap, cache


@pytest.fixture(scope="module")
def law():
    return Law.load()


def test_a_deck_short_over_a_road_is_one_record_at_the_frame_seat(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=10.0)
    recs, notes = crossing_records(ap, law, cache)
    assert len(recs) == 1, notes
    r = recs[0]
    assert r["way"] == "w1" and r["need"] == 4.2 and r["zero"] == pytest.approx(10.0)
    assert r["soffit_y"] == pytest.approx(3.0) and r["least_dem"] == pytest.approx(3.0)
    assert set(published(recs)[0]) == {"unit", "member", "comp", "way", "kind", "need",
                                       "zero", "soffit_y"}


def test_a_road_over_the_soffit_lists_the_group(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=13.5)
    recs, notes = crossing_records(ap, law, cache)
    assert recs == () and any("under the road's ground" in n for n in notes)


def test_a_footway_is_no_road(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=10.0, highway="footway")
    assert crossing_records(ap, law, cache)[0] == ()
