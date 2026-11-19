"""Owner RULINGS 2026-11-19j: a placement is split into bodies only where
its bodies' seats would differ by more than the 0.5 m ground bar;
otherwise it is written whole, as authored, at one zero, and a terminal or
cluster group (a touching group, a shared unit) always seats as one.

Synthetic frames in the shape of ``test_touch_seat2110``: square buildings
in metres about one anchor; a placement is ONE member whose bodies are the
given boxes, every record logged as written so the pass may re-cut.
"""
from __future__ import annotations

import dataclasses as dc
import types

from test_touch_seat2110 import LAW as TOUCH, SURFACE, _ll, _ring

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import split_bar as SB
from auto_patch_v2.airport import touch_seat as TS
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model.rebake import Part

BAR = SB._BarLaw(bar_m=0.5, contact_tol_m=0.3)


class _Plan:
    """Placements of several bodies each, in one frame."""

    def __init__(self):
        self.members: list = []
        self.records: list[Split] = []
        self.pid = 0

    def placement(self, name, bodies, *, family=""):
        """``bodies``: ``[(box, zero)]`` -- one body per box, seated at its
        zero, the first with two feet (the senior); returns the record."""
        parts, out = [], []
        for k, (box, zero) in enumerate(bodies):
            self.pid += 1
            la, lo = _ll((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            parts.append(Part(self.pid, k, la, lo, 0.0, 1.0, (0, 0, 0, 0),
                              rings=(_ring(*box),), height_m=8.0))
            y0 = SURFACE - zero
            a = AR.Anchor(AR.BUILDING, la, lo, y0, "§16g unit", SURFACE,
                          offset=(float(k), y0, 0.0), family=family)
            feet = ((la, lo, 0.0),) * (2 if k == 0 else 1)
            out.append(Body(k, AR.BUILDING, (k,), a, f"objects/{name}__b{k}.obj",
                            pids=(self.pid,), feet=feet, cut_components=(k,),
                            plan_box=(la, lo, la, lo)))
        m = types.SimpleNamespace(id=f"dsf:{name}", resource=f"objects/{name}.obj",
                                  zero_y=0.0, plate_kind="", parts=tuple(parts))
        self.members.append(m)
        la, lo = out[0].anchor.lat, out[0].anchor.lon
        self.records.append(Split(len(self.records), m.id, m.resource, "", la, lo,
                                  0.0, tuple(out)))
        return len(self.records) - 1

    def plan(self):
        return types.SimpleNamespace(units=[types.SimpleNamespace(
            id="unit:1", anchor=(_ll(0, 0)), members=tuple(self.members))])

    def log(self):
        by = {m.id: m for m in self.members}
        return {i: (by[r.placement_id], False, frozenset(), None)
                for i, r in enumerate(self.records)}

    def run(self, touch=False, surface=None):
        counts: dict = {}
        recs, shared = self.records, ()
        if touch:
            recs, t = TS.seat_touching(recs, self.plan(), {}, counts, law=TOUCH,
                                       cut_log=self.log(), write=False)
            shared = t["shared_bodies"]
        out, table = SB.keep_whole(recs, self.plan(), counts, law=BAR, cut_log=self.log(),
                                   write=False, shared=shared,
                                   surface=surface or (lambda la, lo: SURFACE),
                                   band_m=1.0)
        return out, table, counts


def _zeros(rec):
    return [round(b.anchor.surface_z - b.anchor.y_zero, 3) for b in rec.bodies]


def test_a_0_3_m_spread_is_written_whole_at_its_senior_body():
    p = _Plan()
    r = p.placement("hangar", [((0, 0, 20, 20), 431.0), ((40, 0, 60, 20), 431.3)])
    out, table, counts = p.run()
    (b,) = out[r].bodies
    assert _zeros(out[r]) == [431.0]
    assert b.components == (0, 1) and b.cut_components == (0, 1) and len(b.feet) == 3
    assert "RULINGS 2026-11-19j" in b.anchor.reason
    assert counts["split_bar_whole"] == 1 and counts["split_bar_bodies_joined"] == 1
    assert table["moved"] == [(0, 1, "objects/hangar__b1.obj", 431.3, 431.0)]
    assert table["ground"] == []           # 0.3 m buried: inside the bar


def test_a_0_8_m_spread_stays_split():
    p = _Plan()
    r = p.placement("hangar", [((0, 0, 20, 20), 431.0), ((40, 0, 60, 20), 431.8)])
    out, table, counts = p.run()
    assert out[r] is p.records[r] and _zeros(out[r]) == [431.0, 431.8]
    assert counts == {"split_bar_split": 1} and not table["whole"]


def test_a_terminal_group_seats_as_one_and_names_the_zero():
    """The terminal's wing touches a pier of ANOTHER placement: the touch
    pass seats them as one group at the lower (431.2); the terminal is
    written whole at that group's zero though its other body is senior,
    and the pier keeps it."""
    p = _Plan()
    t = p.placement("terminal", [((0, 0, 30, 30), 431.4), ((60, 0, 80, 20), 431.2)])
    q = p.placement("pier", [((80.05, 0, 100, 20), 431.2)])
    out, _table, counts = p.run(touch=True)
    assert _zeros(out[t]) == [431.2] and _zeros(out[q]) == [431.2]
    assert counts["split_bar_whole"] == 1


def test_a_placement_in_two_groups_at_two_zeros_stays_split():
    p = _Plan()
    t = p.placement("terminal", [((0, 0, 20, 20), 431.0), ((60, 0, 80, 20), 431.2)])
    a = p.placement("west", [((-20, 0, -0.05, 20), 431.0)])
    b = p.placement("east", [((80.05, 0, 100, 20), 431.2)])
    out, table, counts = p.run(touch=True)
    assert _zeros(out[t]) == [431.0, 431.2]
    assert (_zeros(out[a]), _zeros(out[b])) == ([431.0], [431.2])
    assert counts["split_bar_held_disagree"] == 1
    assert table["held_disagree"] == [(0, "objects/terminal.obj", 0.2)]


def test_a_shared_unit_names_the_zero():
    """A §16g unit seating a body of another placement holds its zero."""
    p = _Plan()
    t = p.placement("hall", [((0, 0, 20, 20), 431.3), ((60, 0, 80, 20), 431.0)],
                    family="fu:1:1")
    p.placement("annex", [((200, 0, 220, 20), 431.0)], family="fu:1:1")
    rec = p.records[t]
    free = dc.replace(rec.bodies[0], anchor=dc.replace(rec.bodies[0].anchor, family=""))
    p.records[t] = dc.replace(rec, bodies=(free, rec.bodies[1]))
    out, _t, _c = p.run()
    # its b1 is seated in the unit with the annex: the hall takes b1's zero,
    # though b0 is senior
    assert _zeros(out[t]) == [431.0]
    # ... and with both bodies in the unit at two zeros it stays split
    p.records[t] = rec
    out, _t, counts = p.run()
    assert _zeros(out[t]) == [431.3, 431.0] and counts["split_bar_held_disagree"] == 1


def test_a_tilted_body_keeps_its_split_and_a_rider_follows_the_whole_file():
    p = _Plan()
    tilt = p.placement("shelter", [((0, 0, 20, 20), 431.0), ((40, 0, 60, 20), 431.1)])
    whole = p.placement("shed", [((200, 0, 220, 20), 431.0), ((240, 0, 260, 20), 431.1)])
    rider = p.placement("sign", [((205, 5, 206, 6), 431.1)])
    seat = types.SimpleNamespace(applied=True, grad=(0.01, 0.0))
    rec = p.records[tilt]
    p.records[tilt] = dc.replace(rec, bodies=(dc.replace(rec.bodies[0], seat=seat),
                                              rec.bodies[1]))
    rr = p.records[rider]
    p.records[rider] = dc.replace(rr, bodies=(dc.replace(
        rr.bodies[0], merged_into="objects/shed__b1.obj"),))
    out, _t, counts = p.run()
    assert len(out[tilt].bodies) == 2 and counts["split_bar_tilt"] == 1
    # the shed's b1 carries the sign: held, so the shed is whole at 431.1
    assert _zeros(out[whole]) == [431.1]
    assert out[rider].bodies[0].merged_into == out[whole].bodies[0].new_resource
    assert counts["split_bar_riders_renamed"] == 1


def test_disarmed_without_the_key():
    assert SB.law_of(types.SimpleNamespace(split_bar_m=0.0)) is None
    assert SB.law_of(types.SimpleNamespace(split_bar_m=0.5, split_tol_m=0.3)) == BAR


def test_a_whole_seat_the_ground_cannot_absorb_stays_split():
    """b1 stands 0.1 m over its own ground; at the senior's zero it would
    float 0.55 m -- past the bar, so the split stands and is listed."""
    p = _Plan()
    r = p.placement("hangar", [((0, 0, 20, 20), 431.0), ((40, 0, 60, 20), 430.55)])
    lo_b1 = _ll(50, 10)[1]

    def ground(la, lo):
        return 430.45 if abs(lo - lo_b1) < 1e-9 else 431.0
    out, table, counts = p.run(surface=ground)
    assert _zeros(out[r]) == [431.0, 430.55] and counts == {"split_bar_ground": 1}
    assert table["ground"] == [(0, "objects/hangar.obj", 0.1, 0.55, 0.0, 0.0)]
