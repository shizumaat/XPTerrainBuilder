"""#2110 R3 (owner RULINGS 2026-11-16k/u/v; spec 2110-R3 §5 step 1):
touching buildings form ONE group moved by ONE rigid seat, at the LOWER.

Synthetic frames: square buildings in metres about one anchor, each body
its own placement record, every record logged as written
(``placement_file._cut_and_file``'s ``cut_log``) so the pass may re-cut.
"""
from __future__ import annotations

import math
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import touch_seat as TS
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model.rebake import Part

LA0, LO0 = 47.0, 13.0
LAW = TS._TouchLaw(touch_m=0.1, tol_m=0.05, min_share=0.10, walled_m=2.5)
SURFACE = 430.0


def _ll(x: float, y: float) -> tuple[float, float]:
    return (LA0 + y / 111132.0, LO0 + x / (111320.0 * math.cos(math.radians(LA0))))


def _ring(x0, y0, x1, y1):
    return tuple(_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


class _World:
    """A plan of one-member placements and their records."""

    def __init__(self):
        self.units: dict[str, list] = {}
        self.records: list[Split] = []
        self.pid = 0

    def body(self, name, box, zero, *, h=8.0, base=0.0, feet=True, frame="unit:1",
             merged_into="", reason="§16g unit", plate_kind="", line=False):
        """One body (one placement): plan ``box`` (x0, y0, x1, y1) metres,
        seated at ``zero``; returns its record index."""
        self.pid += 1
        la, lo = _ll((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        part = Part(self.pid, 0, la, lo, base, 1.0, (0, 0, 0, 0),
                    rings=(_ring(*box),), height_m=h, line=line)
        m = types.SimpleNamespace(id=f"dsf:{name}", resource=f"objects/{name}.obj",
                                  zero_y=0.0, plate_kind=plate_kind, parts=(part,))
        self.units.setdefault(frame, []).append(m)
        y0 = SURFACE - zero
        a = AR.Anchor(AR.BUILDING, la, lo, y0, reason, SURFACE, offset=(0.0, y0, 0.0))
        b = Body(0, AR.BUILDING, (0,), a, f"objects/{name}__b0.obj", pids=(self.pid,),
                 merged_into=merged_into, feet=((la, lo, zero),) if feet else ())
        self.records.append(Split(len(self.records), m.id, m.resource, "", la, lo, 0.0, (b,)))
        return len(self.records) - 1

    def run(self, law=LAW, fixed=None, plan_wide=None):
        plan = types.SimpleNamespace(units=[
            types.SimpleNamespace(id=k, members=tuple(v)) for k, v in self.units.items()])
        members = {m.id: m for v in self.units.values() for m in v}
        log = {i: (members[r.placement_id], True, frozenset(), None)
               for i, r in enumerate(self.records)}
        counts: dict = {}
        out, table = TS.seat_touching(self.records, plan, plan_wide or {}, counts,
                                      law=law, fixed=fixed, cut_log=log, write=False)
        return out, table, counts


def _zero(rec):
    a = rec.bodies[0].anchor
    return round(a.surface_z - a.y_zero, 3)


def test_two_touching_buildings_0_6_apart_seat_at_the_lower():
    """16v: under 1 m, the group seats at its lower member; nothing rises
    (I1) and the touching pair ends within tol (I2)."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 431.6)
    out, table, counts = w.run()
    assert (_zero(out[a]), _zero(out[b])) == (431.0, 431.0)
    assert counts["touch_groups_seat"] == 1 and counts["touch_bodies_moved"] == 1
    assert "one touching group" in out[b].bodies[0].anchor.reason
    assert out[b].bodies[0].new_resource != w.records[b].bodies[0].new_resource
    assert table["inside_steps"] == []                                    # I2


def test_1_5_and_2_5_are_left_and_listed():
    """16v: 1-2 m is a case-by-case reading, over 2 m separate pads —
    neither moves; both are listed (the pads with the level each needs)."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 432.5)
    c = w.body("c", (100, 0, 120, 20), 431.0, frame="unit:2")
    d = w.body("d", (120.05, 0, 140, 20), 433.5, base=-0.5, frame="unit:2")
    out, table, counts = w.run()
    assert [_zero(out[i]) for i in (a, b, c, d)] == [431.0, 432.5, 431.0, 433.5]
    cls = {g["class"]: g for g in table["groups"]}
    assert cls["judge"]["S"] == 1.5 and cls["pads"]["S"] == 2.5
    assert sorted(z for _n, z in cls["pads"]["pads"]) == [430.5, 431.0]
    assert counts.get("touch_bodies_moved", 0) == 0


def test_a_fence_between_joins_nothing():
    """16u: "a fence does not join them" — a line part touches nothing."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    w.body("fence", (20.0, 0, 21.0, 20), 431.3, h=2.0, line=True)
    b = w.body("b", (21.0, 0, 40, 20), 431.6)
    out, table, _c = w.run()
    assert (_zero(out[a]), _zero(out[b])) == (431.0, 431.6)
    assert not table["groups"]


def test_a_roof_over_two_walls_makes_one_group():
    """16u: a shared roof connects them — a footless connector with no
    carrier joins the buildings its rings touch."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (25, 0, 45, 20), 431.4)
    r = w.body("roof", (0, 0, 45, 20), 431.4, h=1.0, base=7.5, feet=False)
    out, _t, _c = w.run()
    assert [_zero(out[i]) for i in (a, b, r)] == [431.0, 431.0, 431.0]


def test_a_truck_under_a_canopy_is_vetoed():
    """§1.2: parts whose authored spans lie more than 1 m apart do not
    touch — a 3 m truck under a canopy 5 m up is not its group."""
    w = _World()
    t = w.body("truck", (5, 5, 10, 8), 431.0, h=3.0)
    hall = w.body("hall", (20.05, 0, 40, 20), 431.6, h=10.0)
    w.body("canopy", (0, 0, 20.05, 20), 431.6, h=1.0, base=5.0, feet=False)
    out, _t, _c = w.run()
    assert (_zero(out[t]), _zero(out[hall])) == (431.0, 431.6)


def test_a_small_low_member_keeps_its_seat_and_does_not_vote():
    """§2.2: a shed under 10 % of the group's footprint, alone at the
    lowest level, keeps its seat; the terminal does not sink to it."""
    w = _World()
    big = w.body("terminal", (0, 0, 100, 100), 431.0)
    shed = w.body("shed", (100.05, 0, 105, 5), 430.5, h=3.0)
    out, table, counts = w.run()
    assert (_zero(out[big]), _zero(out[shed])) == (431.0, 430.5)
    assert counts["touch_small_low"] == 1
    assert table["groups"][0]["small_low"] == ["objects/shed__b0.obj"]


def test_a_rider_follows_its_carrier_and_names_its_new_file():
    """§2.3: a body in no group riding a moved body moves by the same
    amount; its ``merged_into`` names the carrier's new file."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 431.6)
    r = w.body("sign", (60, 0, 61, 1), 433.6, feet=False,
               merged_into="objects/b__b0.obj",
               reason="carried by objects/b__b0.obj (nearest footed body of the unit)")
    out, _t, counts = w.run()
    assert _zero(out[r]) == 433.0
    assert out[r].bodies[0].merged_into == out[b].bodies[0].new_resource
    assert counts["touch_riders_moved"] == 1


def test_an_evidence_rider_is_its_carriers_group():
    """§1.3 (b): a connector carried with evidence belongs to its carrier's
    group, and its touches to buildings are edges (a sky bridge)."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (40, 0, 60, 20), 431.6)
    sky = w.body("sky", (20.05, 5, 39.95, 10), 431.6, h=3.0, base=4.0, feet=False,
                 merged_into="objects/b__b0.obj",
                 reason="carried by objects/b__b0.obj (largest plan overlap)")
    out, _t, _c = w.run()
    assert [_zero(out[i]) for i in (a, b, sky)] == [431.0, 431.0, 431.0]


def test_fixed_kinds_are_never_moved():
    """§1.3 FIXED: a plate member and a gated frame keep their seats; a
    group needs a non-fixed partner."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    p = w.body("plate", (20.05, 0, 40, 20), 431.6, plate_kind="wall_top")
    w.body("c", (100, 0, 120, 20), 431.0, frame="unit:2")
    d = w.body("d", (120.05, 0, 140, 20), 431.6, frame="unit:2")
    out, _t, counts = w.run(fixed=TS.Fixed(frames={"unit:2": "open_frame"}))
    assert (_zero(out[p]), _zero(out[d])) == (431.6, 431.6)
    assert counts["touch_fixed_plate_wall_top"] == 1
    assert counts["touch_fixed_open_frame"] == 2


def test_one_unit_is_one_group_and_a_foot_never_rises():
    """§1.3 (d) + I1: the bodies of one §16g unit are one group even apart;
    a footed GROUND item of the unit under the seat keeps its seat."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.6)
    b = w.body("b", (50, 0, 70, 20), 431.0)
    g = w.body("kerb", (80, 0, 81, 1), 430.8, h=0.2)
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:1", 0.0), 3: ("fu:1:1", 0.0)}
    out, table, counts = w.run(plan_wide=pw)
    assert [_zero(out[i]) for i in (a, b, g)] == [431.0, 431.0, 430.8]
    assert counts["touch_follower_kept_low"] == 1
    assert table["groups"][0]["root"] == "fu:1:1"


def test_no_touch_no_change():
    """No moved body: the records come back as they were."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (30, 0, 50, 20), 431.6)
    out, table, counts = w.run()
    assert all(x is y for x, y in zip(out, w.records, strict=True))
    assert not table["groups"] and not counts


def test_a_ring_less_scatter_piece_is_read_by_its_box():
    """A scatter piece carries no ring (§B.2 (4)) and §16g reads it by its
    box: LOWS's Terminal_LOWS_46 b1 (76 such pieces) touches its roof."""
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("pieces", (20.05, 0, 40, 20), 431.6)
    m = w.units["unit:1"][1]
    p = m.parts[0]
    (la0, lo0), (la1, lo1) = _ll(20.05, 0), _ll(40, 20)
    m.parts = (Part(p.pid, 0, p.lat, p.lon, 0.0, 1.0, (la0, lo0, la1, lo1), rings=(),
                    height_m=8.0),)
    out, _t, _c = w.run()
    assert (_zero(out[a]), _zero(out[b])) == (431.0, 431.0)


def test_a_ground_follower_a_metre_over_the_seat_keeps_it_with_its_riders():
    """B2: a vehicle of the unit seated on its own ground 1.5 m over the
    group's seat is never buried with it; what rests on it stays too."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (20.05, 0, 40, 20), 431.4)
    v = w.body("van", (60, 0, 65, 2), 432.5, h=2.0)
    r = w.body("rack", (60, 0, 65, 2), 432.5, h=0.5, base=2.0, feet=False,
               merged_into="objects/van__b0.obj",
               reason="carried by objects/van__b0.obj (rests on it)")
    pw = {1: ("fu:1:1", 0.0), 2: ("fu:1:1", 0.0), 3: ("fu:1:1", 0.0), 4: ("fu:1:1", 0.0)}
    out, _t, counts = w.run(plan_wide=pw)
    assert (_zero(out[v]), _zero(out[r])) == (432.5, 432.5)
    assert counts["touch_follower_kept_high"] == 1


def test_a_rider_of_orphan_geometry_follows_its_carrier():
    """§2.3: a carried file holding no plan part (orphan geometry, LOWS
    ``domiki_lows_40`` b44) is no node, and still rides its carrier."""
    import dataclasses
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 431.6)
    r = w.body("slab", (60, 0, 61, 1), 431.6, feet=False, merged_into="objects/b__b0.obj",
               reason="carried by objects/b__b0.obj (rests on it)")
    rec = w.records[r]
    w.records[r] = dataclasses.replace(
        rec, bodies=(dataclasses.replace(rec.bodies[0], components=(), pids=()),))
    out, _t, _c = w.run()
    assert _zero(out[r]) == 431.0
    assert out[r].bodies[0].merged_into == out[b].bodies[0].new_resource


def test_a_body_seated_in_another_unit_keeps_with_it():
    """§1.3 (d), 22o: a body whose seat names a unit (a §16c (7) bind) is
    that unit's, whatever unit most of its parts read — never torn off."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    b = w.body("b", (20.05, 0, 40, 20), 431.6, reason="§16c (7) bound")
    c = w.body("c", (60, 0, 80, 20), 431.6)
    rec = w.records[b]
    import dataclasses
    a2 = dataclasses.replace(rec.bodies[0].anchor, family="fu:9:9@ground")
    w.records[b] = dataclasses.replace(
        rec, bodies=(dataclasses.replace(rec.bodies[0], anchor=a2),))
    pw = {3: ("fu:9:9", 0.0)}
    out, _t, _c = w.run(plan_wide=pw)
    assert (_zero(out[b]), _zero(out[c])) == (431.0, 431.0)


def test_no_member_rises_a_connector_under_the_seat_keeps_it():
    """§2.2: "no member rises" — a footless piece of the group seated under
    the lowest vote is never lifted to it (LOWS domiki_lows_37 b38 would
    have floated 6.3 m)."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (20.05, 0, 40, 20), 431.6)
    c = w.body("canopy", (0, 0, 40, 20), 425.0, h=1.0, base=7.5, feet=False)
    out, table, counts = w.run()
    assert _zero(out[c]) == 425.0
    assert counts["touch_follower_kept_low"] == 1


def test_a_shared_file_name_is_read_in_its_riders_frame():
    """One file is shared by every placement baking the same offset (KDEN's
    escalators): a rider follows the carrier OF ITS FRAME, never a body of
    another frame that happens to bake the same file."""
    w = _World()
    w.body("a", (0, 0, 20, 20), 431.0)
    w.body("b", (20.05, 0, 40, 20), 431.6)
    w.body("b2", (200, 0, 220, 20), 431.6, frame="unit:2")
    import dataclasses
    i = len(w.records) - 1
    rec = w.records[i]
    w.records[i] = dataclasses.replace(rec, bodies=(dataclasses.replace(
        rec.bodies[0], new_resource="objects/b__b0.obj"),))
    r = w.body("sign", (260, 0, 261, 1), 433.6, feet=False, frame="unit:2",
               merged_into="objects/b__b0.obj",
               reason="carried by objects/b__b0.obj (nearest footed body of the unit)")
    out, _t, _c = w.run()
    assert _zero(out[r]) == 433.6
    assert out[r].bodies[0].merged_into == "objects/b__b0.obj"


# ── RULINGS 2026-11-18h (#2129): a building group is never tilted ──────

def _tilted(w, i, drop=0.1):
    """record ``i``'s body written seat-TILTED (an applied 10-01k Q1 seat
    whose no-float sink lowered its zero by ``drop``)."""
    import dataclasses as dc

    from auto_patch_v2.airport import placement_seat_tilt as PST
    rec = w.records[i]
    b = rec.bodies[0]
    a = b.anchor
    seat = PST.SeatTilt(tilt_deg=0.4, total_deg=0.4, applied=True,
                        grad=(0.0, 0.007), drop_m=drop, residual_before_m=0.5)
    a2 = dc.replace(a, y_zero=a.y_zero + drop, offset=(0.0, a.y_zero + drop, 0.0))
    w.records[i] = dc.replace(rec, bodies=(dc.replace(b, anchor=a2, seat=seat),))


def _ground(la, lo):
    """the ground falls 1 m west to east over the first 40 m"""
    x = (lo - LO0) * 111320.0 * math.cos(math.radians(LA0))
    return SURFACE - min(max(x, 0.0), 40.0) / 40.0


def test_a_tilted_garage_and_its_stacked_deck_seat_level_where_no_foot_floats():
    """EDDH's car park (53.625561, 10.006926): the walls seat-tilted, the
    top deck 1.40 m higher on its own unit.  The walls are written level
    again, and the group takes ONE zero -- the deck at its authored
    height over the walls -- where its lowest foot meets the ground."""
    import dataclasses as dc
    w = _World()
    walls = w.body("walls", (0, 0, 20, 20), 430.0)
    deck = w.body("deck", (20.05, 0, 40, 20), 431.4, base=0.0)
    _tilted(w, walls)
    for i, xs in ((walls, (0.0, 20.0)), (deck, (20.05, 40.0))):
        rec = w.records[i]
        feet = tuple((*_ll(x, 10.0), 0.0) for x in xs)
        w.records[i] = dc.replace(rec, bodies=(dc.replace(rec.bodies[0], feet=feet),))
    law = dc.replace(LAW, band_m=1.0, contact_tol_m=0.3)
    plan = types.SimpleNamespace(units=[
        types.SimpleNamespace(id=k, members=tuple(v)) for k, v in w.units.items()])
    members = {m.id: m for v in w.units.values() for m in v}
    log = {i: (members[r.placement_id], True, frozenset(), None)
           for i, r in enumerate(w.records)}
    counts: dict = {}
    out, table = TS.seat_touching(w.records, plan, {}, counts, law=law, cut_log=log,
                                  write=False, surface=_ground)
    z = round(SURFACE - 1.0, 3)              # the deck's far foot, the lowest ground
    assert (_zero(out[walls]), _zero(out[deck])) == (z, z)
    assert not out[walls].bodies[0].seat.applied and out[walls].bodies[0].seat.levelled
    assert counts["touch_tilt_levelled"] == 1 and counts["touch_groups_level"] == 1
    assert [g["class"] for g in table["groups"]] == ["level"]


def test_a_tilted_body_touching_nothing_keeps_its_tilt():
    w = _World()
    a = w.body("a", (0, 0, 20, 20), 430.0)
    w.body("b", (50, 0, 70, 20), 431.4)
    _tilted(w, a)
    out, _table, counts = w.run()
    assert out[a].bodies[0].seat.applied and "touch_tilt_levelled" not in counts
