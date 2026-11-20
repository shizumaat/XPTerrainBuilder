"""RULINGS 2026-11-20g / 20k / 20s (``airport/crossing_seat``): a pack frame's
deck spanning a mapped road is ONE group record, its building the seat
witness; the seat plan lifts the group to its anchor less the O1 cap (no
member on airside floats past the bar), lists members floating already (O3),
and a crossing short at the planned seat carries its planned floor."""
from __future__ import annotations

import math
import types

import pytest
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.crossing_seat import crossing_records, seat_plan, short_crossings
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
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
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


def _ground(kind="raisable", z=10.0):
    return lambda x, y: (kind, z)


def _near(_poly):
    return False


def test_a_deck_over_a_road_is_one_group_its_building_the_anchor(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=10.0)
    recs, notes = crossing_records(ap, law, cache)
    assert len(recs) == 1, notes
    r = recs[0]
    assert r["class"] == "" and r["anchor"] == ("dsf:obj1", 0)
    assert r["vote_anchor"] == pytest.approx(10.0)
    (c,) = r["crossings"]
    assert c["way"] == "w1" and c["need"] == 4.2 and c["class"] == ""
    assert c["soffit_y"] == pytest.approx(3.0) and c["least_m"] == pytest.approx(-7.0)
    plan = seat_plan(r, law, _ground(), _near)
    assert plan["lift"] is False and plan["dz"] == 0.0     # one building: no lift over itself
    (short,) = short_crossings(r, plan, 0.1, _ground())
    assert short["short"] == pytest.approx(1.2)
    # laid out at the seat less the ground bar it may solve under
    bar = law.tables.structures.placement.split_bar_m
    assert short["floor"] == pytest.approx(10.0 - bar + 3.0 - 4.2 - 0.1)


def test_a_road_over_the_soffit_is_short_past_the_cap(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=13.5)
    (r,), _n = crossing_records(ap, law, cache)
    plan = seat_plan(r, law, _ground(), _near)
    (c,) = short_crossings(r, plan, 0.1, lambda x, y: ("raisable", 13.5 if abs(x - 10.0) < 6
                                                       else 10.0))
    assert c["short"] == pytest.approx(4.2 - (10.0 + 3.0 - 13.5))


def test_a_footway_is_no_road(tmp_path, law):
    ap, cache = _frame(tmp_path, road_y=10.0, highway="footway")
    assert crossing_records(ap, law, cache)[0] == ()


def _group(votes, kinds, near=()):
    """A synthetic group record: one building part per vote."""
    parts = [{"member": f"m{i}", "comp": 0, "vote": v, "area": 100.0, "building": True,
              "feet": [(0.0, float(i), 0.0)], "fxy": [(float(i), 0.0, 0.0)],
              "plan": f"p{i}"} for i, v in enumerate(votes)]
    rec = {"unit": "u", "parts": parts, "anchor": (f"m{votes.index(max(votes))}", 0),
           "crossings": [], "class": ""}

    def ground(x, y):
        return kinds[int(x)], votes[int(x)]
    return rec, ground, (lambda poly: poly in near)


def test_the_lift_is_capped_by_a_member_on_airside(law):
    """O1: no member on airside ground floats past the bar: the seat stands
    at most ``split_bar_m`` over the lowest such member."""
    votes = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 12.0]
    kinds = ["airside"] + ["raisable"] * 9
    rec, ground, near = _group(votes, kinds)
    plan = seat_plan(rec, law, ground, near)
    bar = law.tables.structures.placement.split_bar_m
    assert plan["seat"] == pytest.approx(votes[0] + bar, abs=1e-6)
    assert plan["lift"] and plan["anchor"] != ("m0", 0)
    assert ("m1", 0) in plan["ties"] and ("m0", 0) not in plan["ties"]


def test_an_unraisable_low_member_zeroes_the_lift(law):
    """A member on airside stands (nearly) a bar under the control seat:
    no lift is left, and the seat plan is the control (the touch pass's)."""
    votes = [10.0] + [10.48] * 20 + [11.0]
    rec, ground, near = _group(votes, ["airside"] + ["raisable"] * 21)
    plan = seat_plan(rec, law, ground, near)
    assert plan["lift"] is False and plan["ties"] == []
    assert plan["seat"] == pytest.approx(plan["control"])


def test_a_member_floating_already_is_listed_never_capping(law):
    """O3: a member floating past the bar at the control seat is listed."""
    votes = [8.0] + [10.0 + 0.1 * k for k in range(20)]
    rec, ground, near = _group(votes, ["airside"] + ["raisable"] * 20)
    plan = seat_plan(rec, law, ground, near)
    assert ("m0", 0) in [p[:2] for p in plan["prior_float"]]
    assert plan["lift"] and plan["dz"] == 0.0
