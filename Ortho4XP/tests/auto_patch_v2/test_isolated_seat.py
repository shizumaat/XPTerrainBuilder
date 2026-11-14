"""§9a THE ISOLATED SEAT (#2063 round 3; RULINGS 2026-11-13y (4)/(5);
``docs/specs/2063-round3-isolated-seat-spec.md`` §9): an object standing
2 m clear of everything is seated on its LOWEST CONTACT FEET, one frame per
share, and every refusal of the certain witness keeps today's seat (13r).

Synthetic and hermetic: plans built by hand on a flat or sloping surface.
"""
from __future__ import annotations

import dataclasses as dc
import os

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import isolated_seat as I
from auto_patch_v2.airport import placement_atom as ATOM
from auto_patch_v2.airport import placement_motion as PM
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

LAT, LON = 40.0, -3.0
ML, MO = AR._m_per_deg(LAT)
LAW = dict(reach_m=2.0, span_max_m=150.0, split_tol_m=0.3, step_m=0.05)


def _ll(x: float, n: float) -> tuple[float, float]:
    """``x`` metres east, ``n`` metres north of the origin, as (lat, lon)."""
    return LAT + n / ML, LON + x / MO


def _part(pid: int, x: float, n: float, side: float = 1.0, y: float = 0.0,
          feet=None, comp=None, line: bool = False) -> Part:
    la0, lo0 = _ll(x, n)
    la1, lo1 = _ll(x + side, n + side)
    if feet is None:
        feet = ((la0, lo0, y), (la1, lo1, y))
    return Part(pid=pid, comp=pid if comp is None else comp,
                lat=(la0 + la1) / 2, lon=(lo0 + lo1) / 2, base_y=y,
                area_m2=side * side, box=(la0, lo0, la1, lo1),
                feet=tuple(feet), line=line)


def _plan(*units: tuple[tuple[Member, ...], float]) -> RebakePlan:
    return RebakePlan(icao="TEST", pack_name="p", pack_root="/nowhere",
                      units=tuple(Unit(f"u{i}", (LAT, LON), agl, ms)
                                  for i, (ms, agl) in enumerate(units)),
                      skipped=(), counts={})


def _m(mid: str, *parts: Part, **kw) -> Member:
    return Member(id=mid, resource=f"objects/{mid}.obj", authored_path="",
                  live_path="", heading_deg=0.0, parts=parts, **kw)


def _flat(z: float = 100.0):
    return lambda la, lo: z


def _slope(z0: float = 100.0, per_m: float = 0.0):
    """Ground rising ``per_m`` per metre east."""
    return lambda la, lo: z0 + (lo - LON) * MO * per_m


# ── the cluster ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("gap,n", [(1.9, 1), (2.1, 2)])
def test_parts_within_the_reach_are_one_cluster(gap, n):
    a = _part(0, 0.0, 0.0)
    b = _part(1, 1.0 + gap, 0.0)
    groups, blocked = I.clusters([a, b], 2.0, (), LAT)
    assert len(groups) == n and not blocked


def test_a_line_part_neither_links_nor_blocks():
    fence = _part(2, 1.5, 0.0, side=1.0, line=True)
    plan = _plan(((_m("a", _part(0, 0.0, 0.0)), _m("f", fence),
                   _m("b", _part(1, 3.2, 0.0))), 0.0))
    c: dict = {}
    got = I.shares(plan, _flat(), counts=c, **LAW)
    assert sorted(s.id for s in set(got.values())) == ["iso:0@0", "iso:1@0"]
    assert 2 not in got


def test_a_sibling_plans_part_within_the_reach_refuses():
    plan = _plan(((_m("a", _part(0, 0.0, 0.0)),), 0.0))
    near = ((_part(9, 2.5, 0.0).box, ()),)          # 1.5 m away
    c: dict = {}
    assert I.shares(plan, _flat(), foreign=near, counts=c, **LAW) == {}
    assert c["isolated_refused_not_isolated"] == 1
    far = ((_part(9, 6.0, 0.0).box, ()),)
    assert I.shares(plan, _flat(), foreign=far, counts={}, **LAW)


# ── the certain witness, refusal by refusal ──────────────────────────────

def test_a_structure_member_in_the_closure_refuses_the_share():
    shed = _m("shed", _part(1, 2.0, 0.0), base_profile={"planes": [{"y": 0.0}]})
    plan = _plan(((_m("cart", _part(0, 0.0, 0.0)), shed), 0.0))
    c: dict = {}
    assert I.shares(plan, _flat(), counts=c, **LAW) == {}
    assert c["isolated_parts_by_structure"] == 1    # the cart, by closure


@pytest.mark.parametrize("kw", [dict(skirted=True), dict(deck_kind="flag"),
                                dict(deck_kind="family"), dict(plate_y=1.0)])
def test_each_structure_verdict_refuses(kw):
    plan = _plan(((_m("cart", _part(5, 2.0, 0.0)),
                   _m("x", _part(0, 0.0, 0.0), **kw)), 0.0))
    c: dict = {}
    assert I.shares(plan, _flat(), counts=c, **LAW) == {}
    assert c["isolated_parts_by_structure"] == 1    # the cart, by closure


def test_a_deck_candidate_plate_is_no_deck():
    """A wing reads as a plate with no spanning evidence: no deck — unless
    every member of its frame is one (22c's open structure, one rigid group)."""
    plan = _plan(((_m("x", _part(0, 0.0, 0.0), deck_kind="candidate"),
                   _m("y", _part(1, 0.5, 0.0))), 0.0))
    assert I.shares(plan, _flat(), counts={}, **LAW)
    plan = _plan(((_m("x", _part(0, 0.0, 0.0), deck_kind="candidate"),), 0.0))
    assert I.shares(plan, _flat(), counts={}, **LAW) == {}


def test_a_cluster_wider_than_the_span_refuses():
    parts = [_part(i, 2.5 * i, 50.0, side=1.0) for i in range(2)]
    chain = [_part(10 + i, 1.5 * i, 0.0, side=1.0) for i in range(110)]
    plan = _plan(((_m("x", *chain),), 0.0), ((_m("y", *parts),), 0.0))
    c: dict = {}
    got = I.shares(plan, _flat(), counts=c, **LAW)
    assert c["isolated_refused_span"] == 1 and not any(p in got for p in range(10, 120))
    assert set(got) == {0, 1}


def test_no_feet_and_off_author_ground_refuse():
    c: dict = {}
    plan = _plan(((_m("x", _part(0, 0.0, 0.0, feet=())),), 0.0))
    assert I.shares(plan, _flat(), counts=c, **LAW) == {}
    plan = _plan(((_m("x", _part(0, 0.0, 0.0, y=-0.69)),), 0.0))  # the 13r booth
    assert I.shares(plan, _flat(), counts=c, **LAW) == {}
    plan = _plan(((_m("x", _part(0, 0.0, 0.0, y=-2.0)),), 2.0))   # lifted 2 m
    assert I.shares(plan, _flat(), counts=c, **LAW)
    assert c["isolated_refused_no_feet"] == 1
    assert c["isolated_refused_off_author_ground"] == 1


def test_off_sheet_water_pad_deck_and_rim_refuse():
    p = _part(0, 0.0, 0.0)
    ring = ((p.box[0] - 1e-4, p.box[1] - 1e-4), (p.box[0] - 1e-4, p.box[3] + 1e-4),
            (p.box[2] + 1e-4, p.box[3] + 1e-4), (p.box[2] + 1e-4, p.box[1] - 1e-4))
    plan = _plan(((_m("x", p),), 0.0))
    c: dict = {}
    assert I.shares(plan, lambda la, lo: None, counts=c, **LAW) == {}
    wet = _flat()
    wet.water = lambda la, lo: True
    surf = _flat()
    assert I.shares(plan, wet, counts=c, **LAW) == {}
    assert I.shares(plan, surf, pads=[AR.PadRing("building1", ring)], counts=c, **LAW) == {}
    assert I.shares(plan, surf, decks=[AR.DeckFace("bridge_deck:1", ring)], counts=c,
                    **LAW) == {}
    assert I.shares(plan, surf, rims=[AR.RimRing("structure_rim:1", ring)], counts=c,
                    **LAW) == {}
    for why in ("no_surface", "water", "pad", "deck", "rim"):
        assert c[f"isolated_refused_{why}"] == 1, why


def test_two_terrains_under_the_lowest_feet_refuse():
    plan = _plan(((_m("x", _part(0, 0.0, 0.0, side=4.0)),), 0.0))
    c: dict = {}
    assert I.shares(plan, _slope(per_m=0.1), counts=c, **LAW) == {}   # 0.4 m spread
    assert c["isolated_refused_spread"] == 1


# ── the seat ─────────────────────────────────────────────────────────────

def _aircraft(fall_per_m: float = 0.0):
    """Wheels at y 0 (3), gear legs at y 0.25, a belly at y 0.27 in its own
    part — the median of every foot would bury the wheels 0.27 m."""
    wheels = [_part(i, 2.0 * i, 0.0, side=0.4) for i in range(3)]
    legs = [_part(10 + i, 2.0 * i + 0.4, 0.0, side=0.3, y=0.25) for i in range(3)]
    belly = [_part(20 + i, 1.0 + i, 0.5, side=0.5, y=0.27) for i in range(4)]
    return wheels + legs + belly


def test_an_aircraft_stands_on_its_wheels_not_the_median_of_every_foot():
    parts = _aircraft()
    plan = _plan(((_m("ac", *parts),), 0.0))
    got = I.shares(plan, _flat(100.0), counts={}, **LAW)
    a = got[0].anchor
    assert a.isolated and abs((a.surface_z - a.y_zero) - 100.0) < 1e-9   # wheels at 0
    feet = [f for p in parts for f in p.feet]
    median = sorted(100.0 - f[2] for f in feet)[len(feet) // 2]
    assert median == pytest.approx(99.75)          # what today's median does


def test_a_fall_across_the_gear_buries_by_the_step_and_floats_the_rest():
    """0.2 m of fall under the wheels: the highest-ground wheel is buried
    exactly the motion step, the low side floats."""
    w = [_part(i, 0.0, 0.0, side=0.01) for i in range(1)] + \
        [_part(1, 3.0, 0.0, side=0.01), _part(2, 1.0, 0.0, side=0.01)]
    plan = _plan(((_m("ac", *w),), 0.0))
    surf = _slope(per_m=0.2 / 3.0)
    s = I.shares(plan, surf, counts={}, split_tol_m=0.3, step_m=0.05, reach_m=2.0,
                 span_max_m=150.0)[0]
    z = s.anchor.surface_z - s.anchor.y_zero
    r = [surf(f[0], f[1]) - f[2] for p in w for f in p.feet]
    assert max(r) - z == pytest.approx(0.05, abs=1e-9)   # burial exactly the step
    assert z - min(r) == pytest.approx(0.15, abs=0.002)  # the rest floats


def test_one_lowest_foot_is_enough():
    best, zero, med = I.seat([(LAT, LON, 0.0, 100.0)], 0.05)
    assert zero == med == 100.0 and best[3] == 100.0


def test_a_tailwheel_above_the_mains_keeps_the_attitude():
    mains = [_part(0, 0.0, 0.0, side=0.3), _part(1, 1.5, 0.0, side=0.3)]
    tail = _part(2, 0.75, -1.8, side=0.2, y=0.2)
    plan = _plan(((_m("cub", *mains, tail),), 0.0))
    a = I.shares(plan, _flat(), counts={}, **LAW)[0].anchor
    assert a.surface_z - a.y_zero == pytest.approx(100.0)   # mains on the ground
    assert len(PM.lowest_contact_feet([f for p in (*mains, tail) for f in p.feet],
                                      0.05)) == 4            # the tail is not one


def test_three_sheets_are_one_anchor():
    """A real aircraft is parts of 2-3 files around one shared anchor."""
    plan = _plan(((_m("ac_1", _part(0, 0.0, 0.0, side=0.4)),
                   _m("ac_2", _part(1, 0.5, 0.0, side=1.0, y=0.6)),
                   _m("ac_3", _part(2, 1.6, 0.0, side=0.4))), 0.0))
    got = I.shares(plan, _slope(per_m=0.01), counts={}, **LAW)
    assert len({id(s) for s in got.values()}) == 1 and set(got) == {0, 1, 2}


def test_lowest_contact_feet_is_the_one_band_for_seat_and_census():
    feet = [(0, 0, -0.06), (0, 0, -0.02), (0, 0, 0.3), (0, 0, 0.9)]
    assert PM.lowest_contact_feet(feet, 0.05) == feet[:2]
    assert PM.lowest_contact_feet([], 0.05) == []


def test_the_census_judges_an_isolated_body_at_its_lowest_feet():
    class Roles:
        def roles_many(self, las, los):
            return ["apron"] * len(las)
    body = {"res": "ac", "cls": "other", "anchor_z": 100.0, "y_zero": 0.0,
            "feet": [(LAT, LON, 0.0), (LAT, LON, 0.25)]}
    surf = _flat(100.0)
    kw = dict(rolled_on={"apron"}, motion_step_m=0.05, band_m=1.0, contact_tol_m=0.3)
    plain = PM.census_motion([body], surf, Roles(), **kw)
    iso = PM.census_motion([dict(body, isolated="iso:0@0")], surf, Roles(), **kw)
    assert plain["feet_on_pavement"] == 2 and iso["feet_on_pavement"] == 1


# ── the binds and the carrier search skip an isolated share ─────────────

def test_an_isolated_candidate_never_binds():
    c = type("C", (), {})()
    c.member, c.group, c.pids, c.box, c.part_boxes, c.feet = 0, 0, frozenset({1}), \
        (LAT, LON, LAT + 1e-5, LON + 1e-5), ((LAT, LON, LAT + 1e-5, LON + 1e-5),), 2
    c.body_class = AR.OTHER
    c.anchor = AR.Anchor(AR.OTHER, LAT, LON, 0.0, "", 100.0, isolated="iso:1@0")
    d = type("C", (), dict(vars(c)))()
    d.member, d.pids, d.anchor = 1, frozenset({2}), dc.replace(c.anchor, isolated="")
    _f, census = ATOM.bind_unit([c, d], [], _flat(), [(1, 2)], {})
    assert census == []                    # the contact edge bound nothing


def test_an_isolated_anchor_is_never_elevated():
    from auto_patch_v2.airport.placement_carrier import is_elevated
    a = AR.Anchor(AR.OTHER, LAT, LON, 0.6, "", 100.0)
    assert is_elevated(0.6, a, 0.5)
    assert not is_elevated(0.6, dc.replace(a, isolated="iso:1@0"), 0.5)


# ── through the plan: one frame, written, never carried or a carrier ─────

def _box(x0, z0, side=1.0, h=1.0, y0=0.0):
    v = [(x0, y0, z0), (x0 + side, y0, z0), (x0 + side, y0, z0 + side),
         (x0, y0, z0 + side), (x0, y0 + h, z0), (x0 + side, y0 + h, z0),
         (x0 + side, y0 + h, z0 + side), (x0, y0 + h, z0 + side)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _write(path, boxes):
    verts, tris = [], []
    for v, t in boxes:
        o = len(verts)
        verts += v
        tris += [(a + o, b + o, c + o) for a, b, c in t]
    idx = [i for t in tris for i in t]
    out = ["I", "800", "OBJ", "", "TEXTURE\tt.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0 1 0\t0 0" for x, y, z in verts]
    out += [f"IDX\t{i}" for i in idx] + ["", "ATTR_no_blend", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _obj_part(pid, comp, x0, z0, side=1.0, y0=0.0):
    """The plan part of an authored box at ``(x0, z0)`` (OBJ8 z is SOUTH)."""
    return _part(pid, x0, -(z0 + side), side=side, y=y0, comp=comp)


def _iso_plan(tmp_path, gap=10.0):
    """Two aircraft-like objects in one file ``gap`` m apart, each wheels at
    y 0 and a body box at y 0.3, on a slope that makes the median bury."""
    path = _write(tmp_path / "ac.obj", [_box(0, 0, 0.3), _box(1.0, 0, 0.3),
                                         _box(0, 0, 1.3, 1.0, 0.3),
                                         _box(gap, 0, 0.3), _box(gap + 1.0, 0, 0.3),
                                         _box(gap, 0, 1.3, 1.0, 0.3)])
    parts = (_obj_part(0, 0, 0, 0, 0.3), _obj_part(1, 1, 1.0, 0, 0.3),
             _obj_part(2, 2, 0, 0, 1.3, 0.3), _obj_part(3, 3, gap, 0, 0.3),
             _obj_part(4, 4, gap + 1.0, 0, 0.3), _obj_part(5, 5, gap, 0, 1.3, 0.3))
    m = Member(id="dsf:obj1", resource="objects/ac.obj", authored_path=path,
               live_path=path, heading_deg=0.0, parts=parts)
    return RebakePlan(icao="TEST", pack_name="p", pack_root=str(tmp_path),
                      units=(Unit("u0", (LAT, LON), 0.0, (m,)),), skipped=(),
                      counts={})


def _splits(plan, surf, **kw):
    return PP.build_splits(plan, surf, write=False, split_tol_m=0.3,
                           elevated_base_m=0.5, foot_band_m=1.0,
                           coarsen_reach_m=100.0, rigid_reach_m=2.0, touch_m=0.5,
                           motion_step_m=0.05, isolated_span_max_m=150.0, **kw)


def test_isolated_bodies_are_written_one_frame_each(tmp_path):
    ss = _splits(_iso_plan(tmp_path), _slope(per_m=0.03))
    assert ss.counts["isolated_shares"] == 2
    bodies = [b for s in ss.splits for b in s.bodies]
    assert {b.anchor.isolated for b in bodies} == {"iso:0@0", "iso:3@0"}
    for b in bodies:                       # its own wheels, never the body box
        assert abs(b.anchor.y_zero) < 0.05
    # A1 §3.4: today's raws were elected as without a share, then vacated
    assert ss.counts["isolated_bodies"] == 2
    assert ss.counts["isolated_raws_vacated"] >= 2
    recs, _kept = PP.to_placement_records(ss)
    assert {b.isolated_of for s in recs for b in s.bodies} == {"iso:0@0", "iso:3@0"}


def test_two_shares_merge_at_two_centimetres_not_four(tmp_path):
    for fall, files in ((0.02, 1), (0.04, 2)):
        ss = _splits(_iso_plan(tmp_path), _slope(per_m=fall / 10.0))
        assert sum(len(s.bodies) for s in ss.splits) == files, fall


def test_a_disarmed_seat_is_todays_plan(tmp_path):
    plan = _iso_plan(tmp_path)
    ss = _splits(plan, _slope(per_m=0.03), )
    off = PP.build_splits(plan, _slope(per_m=0.03), write=False, split_tol_m=0.3,
                          elevated_base_m=0.5, foot_band_m=1.0,
                          coarsen_reach_m=100.0, rigid_reach_m=2.0, touch_m=0.5)
    assert "isolated_shares" not in off.counts and ss.counts["isolated_shares"] == 2
    assert not any(b.anchor.isolated for s in off.splits for b in s.bodies)



# ── amendment A1: the walled base and the building file (I7 / I8) ────────

WALLS = dict(LAW, wall_min_h_m=2.5, base_min_fraction=0.45)


def _tall(pid: int, x: float, n: float, w: float, d: float, h: float,
          feet: "list[tuple[float, float]]", y: float = 0.0) -> Part:
    """A part ``w`` east x ``d`` north at ``(x, n)``, ``h`` m of solid
    height from ``y``, with feet at the given local ``(east, north)``."""
    la0, lo0 = _ll(x, n)
    la1, lo1 = _ll(x + w, n + d)
    ft = tuple(_ll(x + e, n + q) + (y,) for e, q in feet)
    return Part(pid=pid, comp=pid, lat=(la0 + la1) / 2, lon=(lo0 + lo1) / 2,
                base_y=y, area_m2=w * d, box=(la0, lo0, la1, lo1), feet=ft,
                height_m=h)


def _wall(pid: int, x: float, h: float) -> Part:
    """A 10 m wall slab 0.3 m thick, its feet along its whole base."""
    return _tall(pid, x, 0.0, 10.0, 0.3, h, [(0.0, 0.0), (5.0, 0.15), (10.0, 0.3)])


def _airliner(pid0: int, x: float) -> list:
    """Three wheels (nose 12 m ahead of the mains, 4 m apart), a 30 m wing
    and a fuselage whose tail stands 7.6 m: feet spread ~0.3 of the span."""
    wheels = [_tall(pid0 + i, x + e, q, 0.4, 0.4, 0.5, [(0.2, 0.2)])
                    for i, (e, q) in enumerate(((13.0, 0.0), (17.0, 0.0), (15.0, 12.0)))]
    wing = _tall(pid0 + 3, x, 1.0, 30.0, 4.0, 1.0, [(15.0, 1.5)], y=1.5)
    body = _tall(pid0 + 4, x + 13.0, -12.0, 4.0, 30.0, 7.1, [(2.0, 13.0)], y=0.5)
    return wheels + [wing, body]


@pytest.mark.parametrize("h,admitted", [(3.0, False), (2.4, True)])
def test_a_wall_slab_on_its_feet_is_refused_walled(h, admitted):
    plan = _plan(((_m("wall", _wall(0, 0.0, h)),), 0.0))
    c: dict = {}
    got = I.shares(plan, _flat(), counts=c, **WALLS)
    assert bool(got) is admitted
    assert c.get("isolated_refused_walled", 0) == (0 if admitted else 1)
    assert I.base_spread([_wall(0, 0.0, h)]) > 0.9


def test_a_three_wheel_aircraft_with_a_tall_tail_is_admitted():
    parts = _airliner(0, 0.0)
    assert I._height_m(parts) == pytest.approx(7.6)
    assert I.base_spread(parts) < 0.45            # ~0.3: wheels inside the span
    plan = _plan(((_m("b737", *parts),), 0.0))
    got = I.shares(plan, _flat(), counts={}, **WALLS)
    assert set(got) == {p.pid for p in parts}


def test_a_building_files_small_isolated_piece_is_refused():
    """The file's wall stands in a structure's closure; its small piece far
    from everything is still the BUILDING's (I7)."""
    shed = _m("shed", _part(50, 11.0, 0.0), base_profile={"planes": [{"y": 0.0}]})
    term = _m("terminal", _wall(0, 0.0, 6.0), _part(1, 40.0, 0.0))
    c: dict = {}
    assert I.shares(_plan(((term, shed), 0.0)), _flat(), counts=c, **WALLS) == {}
    assert c["isolated_refused_building_file"] == 1
    assert I.building_files((term,), 2.0, 2.5, 0.45) == frozenset({"terminal"})


def test_an_aircraft_atlas_with_one_aircraft_at_a_structure_keeps_the_rest():
    shed = _m("shed", _part(90, -1.5, 0.0), base_profile={"planes": [{"y": 0.0}]})
    atlas = _m("atlas", *_airliner(0, 0.0), *_airliner(10, 60.0), *_airliner(20, 120.0))
    c: dict = {}
    got = I.shares(_plan(((atlas, shed), 0.0)), _flat(), counts=c, **WALLS)
    assert set(got) == set(range(10, 15)) | set(range(20, 25))
    assert not c.get("isolated_refused_building_file")


def test_a_cluster_holding_a_building_files_piece_is_refused_whole():
    """A cart beside a building file's loose piece: one plan cluster, every
    share refused (the cart's too)."""
    cart = _m("cart", _part(0, 0.0, 0.0))
    term = _m("terminal", _part(1, 1.5, 0.0), _wall(2, 60.0, 6.0))
    c: dict = {}
    assert I.shares(_plan(((cart, term), 0.0)), _flat(), counts=c, **WALLS) == {}
    assert c["isolated_refused_building_file"] == 1   # the cart's one cluster
    assert c["isolated_refused_walled"] == 1          # the wall's own


@pytest.mark.parametrize("kw", [dict(wall_min_h_m=0.0), dict(base_min_fraction=0.0)])
def test_either_wall_key_at_zero_disarms_both(kw):
    plan = _plan(((_m("wall", _wall(0, 0.0, 6.0)),), 0.0))
    assert I.shares(plan, _flat(), counts={}, **dict(WALLS, **kw))


def test_a_plan_with_no_solid_heights_disarms_the_seat_and_says_so():
    plan = _plan(((_m("x", _part(0, 0.0, 0.0)),), 0.0))     # height_m 0.0
    c: dict = {}
    assert I.shares(plan, _flat(), counts=c, **WALLS) == {}
    assert c["isolated_disarmed_no_height"] == 1


# ── amendment A1 §3.4: the frozen election ───────────────────────────────

def test_a_raw_welding_a_share_to_another_part_refuses_it():
    p0, p1 = _part(0, 0.0, 0.0), _part(1, 1.0, 0.0)
    s = I.Share("iso:0@0", 0, frozenset({0}), AR.Anchor(AR.OTHER, LAT, LON, 0.0, ""))
    c = {"isolated_shares": 1}
    assert I.welded({0: s}, [([p0, p1],), ([p1],)], c) == {"iso:0@0"}
    assert c == {"isolated_shares": 0, "isolated_refused_welded": 1}
    assert I.welded({0: s}, [([p0],), ([p1],)], {}) == frozenset()
    s1 = I.Share("iso:1@0", 0, frozenset({1}), s.anchor)   # two shares, all
    assert I.welded({0: s, 1: s1}, [([p0, p1],)], {}) == frozenset()  # isolated


def test_vacate_with_no_share_is_the_identity():
    rec = object()
    assert I.vacate(rec, None, None, None, {}, {}, step_m=0.05, reach_m=100.0,
                    counts={}, by_class={}) == (rec, False)
    st = type("St", (), dict(raw=[([_part(5, 0.0, 0.0)],)], mi=0))()
    iso = {"iso:0@0": ([_part(0, 9.0, 0.0)],)}
    assert I.vacate(rec, st, None, iso, {}, {}, step_m=0.05, reach_m=100.0,
                    counts={}, by_class={}) == (rec, False)


def test_the_election_is_held_with_the_isolated_present(tmp_path):
    """The isolated group is today's coarsen SENIOR (most feet, largest
    footprint) of a body it shares with a piece at a shed: the piece keeps
    the anchor it was elected on without the share; the share is vacated
    into its own body on its lowest feet."""
    path = _write(tmp_path / "mix.obj", [_box(0, 0, 6.0, 1.0), _box(20.0, 0, 1.0, 1.0)])
    big = _part(0, 0.0, -6.0, side=6.0, comp=0, feet=(
        _ll(0.0, -6.0) + (0.0,), _ll(6.0, -6.0) + (0.0,), _ll(0.0, 0.0) + (0.0,),
        _ll(6.0, 0.0) + (0.0,)))
    piece = _obj_part(1, 1, 20.0, 0, 1.0)
    mix = Member(id="dsf:obj1", resource="objects/mix.obj", authored_path=path,
                 live_path=path, heading_deg=0.0, parts=(big, piece))
    spath = _write(tmp_path / "shed.obj", [_box(21.5, 0, 1.0, 3.0)])
    shed = Member(id="dsf:obj2", resource="objects/shed.obj", authored_path=spath,
                  live_path=spath, heading_deg=0.0,
                  parts=(_obj_part(2, 0, 21.5, 0, 1.0),),
                  base_profile={"planes": [{"y": 0.0}]})
    plan = RebakePlan(icao="TEST", pack_name="p", pack_root=str(tmp_path),
                      units=(Unit("u0", (LAT, LON), 0.0, (mix, shed)),),
                      skipped=(), counts={})
    surf = _slope(per_m=0.005)
    on = _splits(plan, surf)
    off = PP.build_splits(plan, surf, write=False, split_tol_m=0.3,
                          elevated_base_m=0.5, foot_band_m=1.0,
                          coarsen_reach_m=100.0, rigid_reach_m=2.0, touch_m=0.5)
    assert on.counts["isolated_shares"] == 1
    base = {b.pids: b.anchor for s in off.splits + off.whole for b in s.bodies
            if s.placement_id == "dsf:obj1"}
    now = {b.pids: b.anchor for s in on.splits for b in s.bodies
           if s.placement_id == "dsf:obj1"}
    assert set(base) == {(0, 1)}                    # one body, senior `big`
    assert set(now) == {(1,), (0,)}
    assert now[(1,)] == base[(0, 1)]                # the remainder: frozen
    assert now[(0,)].isolated == "iso:0@0"          # the share: its own frame
