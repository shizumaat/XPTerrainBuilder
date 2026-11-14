"""#2060 round 3 (spec ``2060-r3-carrier-seat.md``): the carrier seat is
ORDER-FREE, and only an ATTACHED rider tilts with its carrier.

* T1: every carrier slot is formed before any member is cut, so a rider
  cut before its carrier — inside a member cycle, or downstream of one —
  bakes the seat its carrier is written with (HECA's ``building__b44``
  rode ``concrete_3__b1`` level, +0.89 m at its far wall).
* T2: a rider whose part boxes do not come within ``TOUCH_M`` of its
  carrier's is not part of the carrier's rigid frame: it stays level on
  the carrier's zero and sets no heading (HECA's grass 56 m off its
  carrier, rotated about that far pivot).
* T3: the rider census is read once the whole unit is cut.
"""
from __future__ import annotations

import dataclasses as dc
import os
import re
import types

import test_tilted_group2060 as TG
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8_grade as OG
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport import placement_seat_tilt as PST

LAT, LON = 40.0, -3.0
ML, MO = AR._m_per_deg(LAT)
GRADE = 0.015                       # 0.86 deg, under both caps
Z0 = 100.0


def _surface(la: float, lo: float) -> float:
    return Z0 + GRADE * ((lo - LON) * MO)


def _box(x0, z0, y0, sx, sz, h):
    v = [(x0, y0, z0), (x0 + sx, y0, z0), (x0 + sx, y0, z0 + sz),
         (x0, y0, z0 + sz), (x0, y0 + h, z0), (x0 + sx, y0 + h, z0),
         (x0 + sx, y0 + h, z0 + sz), (x0, y0 + h, z0 + sz)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _obj(path, boxes):
    v: list = []
    t: list = []
    for b in boxes:
        bv, bt = _box(*b)
        t += [(p + len(v), q + len(v), r + len(v)) for p, q, r in bt]
        v += bv
    idx = [i for tri in t for i in tri]
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(v)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0" for x, y, z in v]
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(q) for q in idx[i:i + 10]))
    out += [f"IDX\t{q}" for q in idx[len(idx) - len(idx) % 10:]]
    out += ["", "ATTR_no_blend", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _part(pid, comp, box, footed):
    """``box`` = (x0, z0, y0, sx, sz, h) in the unit's authored frame."""
    from auto_patch_v2.model.rebake import Part
    x0, z0, y0, sx, sz, _h = box
    la0, la1 = LAT - (z0 + sz) / ML, LAT - z0 / ML
    lo0, lo1 = LON + x0 / MO, LON + (x0 + sx) / MO
    feet = (tuple((la, lo, y0) for la in (la0, 0.5 * (la0 + la1), la1)
                  for lo in (lo0, 0.5 * (lo0 + lo1), lo1)) if footed else ())
    return Part(pid=pid, comp=comp, lat=0.5 * (la0 + la1), lon=0.5 * (lo0 + lo1),
                base_y=y0, area_m2=sx * sz, box=(la0, lo0, la1, lo1), feet=feet)


def _hall(x0):
    """a footed 60 m hall (+-0.45 m about its anchor: over the foot tolerance)"""
    return (x0, 0.0, 0.0, 60.0, 20.0, 3.0)


def _roof(x0):
    """a roof slab resting on the hall at ``x0``"""
    return (x0 + 2.0, 2.0, 3.0, 16.0, 16.0, 0.3)


def _plan(tmp_path, spec):
    """``spec``: ``(name, own hall x0, x0 of the hall its roof rests on)``."""
    from auto_patch_v2.model.rebake import Member, RebakePlan, Unit
    mem = []
    pid = 0
    for name, hall_x, roof_x in spec:
        hall, roof = _hall(hall_x), _roof(roof_x)
        # the reader numbers the components west to east
        boxes = sorted([hall, roof])
        p = _obj(tmp_path / f"{name}.obj", boxes)
        parts = (_part(pid, boxes.index(hall), hall, True),
                 _part(pid + 1, boxes.index(roof), roof, False))
        pid += 2
        mem.append(Member(id=f"dsf:{name}", resource=f"objects/{name}.obj",
                          authored_path=p, live_path=p, heading_deg=0.0,
                          parts=parts, base_profile={"verdict": OG.FEET}))
    return RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                      units=(Unit("u0", (LAT, LON), 0.0, tuple(mem)),),
                      skipped=(), counts={}, contacts=())


def _build(tmp_path, spec):
    return PP.build_splits(_plan(tmp_path, spec), _surface, write=False,
                           split_tol_m=0.3, elevated_base_m=0.5, foot_band_m=1.0,
                           bind_ground_m=0.5, seat_tilt_max_deg=1.5,
                           frame_tilt_max_deg=1.0)


def _bodies(ss):
    """``{(resource basename, body id): body}`` of every written body."""
    return {(os.path.basename(s.resource), b.body_id): b
            for s in ss.splits for b in s.bodies}


def _slot(f: str) -> str:
    return re.sub(r"_[0-9a-f]{8}\.obj$", ".obj", f)


def _hash(b) -> str:
    return b.new_resource.rsplit("_", 1)[1]


def _grads(ss):
    """each written rider's grad and its WRITTEN carrier's, by resource"""
    by_file = {b.new_resource: b for b in _bodies(ss).values()}
    # a rider cut before its carrier names the carrier's SLOT id
    # (merged_into is never refreshed): x__b0.obj for x__b0_<hash>.obj
    by_file.update({_slot(f): b for f, b in list(by_file.items())})
    out = {}
    for (res, _k), b in _bodies(ss).items():
        if b.merged_into:
            c = by_file.get(b.merged_into)
            out[res] = (b.seat.grad if b.seat and b.seat.applied else None,
                        c.seat.grad if c is not None and c.seat and c.seat.applied
                        else None)
            # ... and its file bakes the carrier's tilt: one hash
            assert c is not None and _hash(b) == _hash(c), (res, b.new_resource)
    return out


CYCLE = [("a", 0.0, 80.0), ("b", 80.0, 0.0)]


def _assert_every_rider_follows(ss):
    g = _grads(ss)
    assert g, "no rider"
    for res, (rider, carrier) in g.items():
        assert carrier is not None, (res, ss.counts)
        assert rider == carrier, (res, rider, carrier)
    assert ss.counts.get("seat_tilt_level_rider", 0) == 0
    assert ss.counts.get("seat_tilt_rider_orphan", 0) == 0


def test_a_member_cycle_bakes_each_carriers_tilt_in_either_order(tmp_path):
    (tmp_path / "ab").mkdir()
    (tmp_path / "ba").mkdir()
    ab = _build(tmp_path / "ab", CYCLE)
    ba = _build(tmp_path / "ba", CYCLE[::-1])
    for ss in (ab, ba):
        _assert_every_rider_follows(ss)
        assert ss.counts.get("rider_before_carrier") == 1
        assert ss.counts["seat_tilt_rider_followed"] == 2
    # identically in either member order
    assert _grads(ab) == _grads(ba)


def test_a_member_downstream_of_a_cycle_cut_first_follows_too(tmp_path):
    ss = _build(tmp_path, [("c", 160.0, 0.0)] + CYCLE)
    _assert_every_rider_follows(ss)
    assert ss.counts["seat_tilt_rider_followed"] == 3
    assert ss.counts.get("rider_before_carrier") == 2


# ── T2: only an attached rider rotates ─────────────────────────────────

def _box_ll(x0, z0, sx, sz):
    return (LAT - (z0 + sz) / ML, LON + x0 / MO, LAT - z0 / ML, LON + (x0 + sx) / MO)


def test_a_rider_79_m_off_its_tilting_carrier_stays_level_and_counted():
    seat = TG._seat(TG._walls())
    carrier = types.SimpleNamespace(member=0, group=0,
                                    part_boxes=(_box_ll(0.0, 0.0, 20.0, 20.0),))
    far = [_box_ll(99.0, 0.0, 10.0, 10.0)]          # 79 m east of the hall
    assert not PST.attached(far, carrier)
    assert PST.attached([_box_ll(20.5, 0.0, 10.0, 10.0)], carrier)
    level = TG._rider()
    counts: dict = {}
    out = PST.rider_seat(level, TG._MR, {(0, 0): seat}, (0, 0), True,
                         is_attached=False, counts=counts)
    assert out is level and out.seat is None
    assert out.new_resource == level.new_resource
    assert counts == {"seat_tilt_rider_unattached": 1}


def _frame_with_far_rider(rider_heading: float):
    from test_objtilt162 import _feet
    from test_seat_tilt_shared708 import _frame_staged
    sts = _frame_staged([_feet(), _feet()])[:1]
    rider_m = types.SimpleNamespace(heading_deg=rider_heading, resource="objects/r.obj",
                                    base_profile={})
    carrier = types.SimpleNamespace(member=0, group=0,
                                    part_boxes=(_box_ll(0.0, 0.0, 20.0, 20.0),))
    sts.append(types.SimpleNamespace(mi=1, m=rider_m, raw=[None], groups=[],
                                     part_boxes=[[_box_ll(99.0, 0.0, 10.0, 10.0)]],
                                     carried=[([0], carrier, "rests on it")]))
    return sts


def test_an_unattached_rider_at_another_heading_does_not_keep_the_frame_level():
    seats, counts = TG._frame_seats(_frame_with_far_rider(90.0))
    assert len(seats) == 1
    assert counts.get("frame_tilt_mixed_heading", 0) == 0


# ── T3: the order-free census ──────────────────────────────────────────

def test_a_level_rider_named_by_a_stale_slot_id_is_counted():
    carrier = TG._tilted_carrier()
    rider = TG._rider("objects/hangar__b0.obj")      # the slot id, never refreshed
    counts: dict = {}
    PST.rider_census([(rider, (0, 0), True, True, None)], {(0, 0): carrier}, counts)
    assert counts["seat_tilt_level_rider"] == 1
    assert counts["rider_before_carrier"] == 1


def test_a_rider_tilted_on_a_carrier_later_kept_whole_is_an_orphan():
    seat = TG._seat(TG._walls())
    rider = PST.rider_seat(TG._rider(), TG._MR, {(0, 0): seat}, (0, 0), True)
    counts: dict = {}
    PST.rider_census([(rider, (0, 0), True, True, TG._body(TG._walls()).anchor)],
                     {}, counts)
    assert counts["seat_tilt_rider_orphan"] == 1
    # ... and on a carrier written LEVEL
    counts = {}
    PST.rider_census([(rider, (0, 0), True, False, None)],
                     {(0, 0): TG._body(TG._walls())}, counts)
    assert counts == {"seat_tilt_rider_orphan": 1}


# ── R3 stands: Hangar_8's shape ────────────────────────────────────────

def test_a_far_rider_with_its_own_unit_takes_that_units_zero_level():
    """A footless rider whose parts are another unit's (CYLW Hangar_8__b1,
    29-200 m off Hangar_9__b0) takes that unit's zero (22o), bakes no tilt,
    and the tilted carrier alone in its share keeps its own zero."""
    pw = {1: ("fu:24:559/host", 417.877), 2: ("fu:24:558/pad", 416.807)}
    solo: set = set()
    zeros = OFS.root_zeros(pw, TG._plan(("dsf:obj563", (1,)), ("dsf:obj564", (2,))),
                           solo_out=solo)
    carrier = TG._tilted_carrier()
    counts: dict = {}
    led: set = set()
    out = OFS.group_zero(TG._split(carrier), TG._M, pw, zeros, counts, "unit:24",
                         solo=solo, led=led)
    assert TG._zero_of(out.bodies[0]) == TG.Z0
    rider = PST.rider_seat(dc.replace(TG._rider(carrier.new_resource), pids=(2,)),
                           TG._MR, {(0, 0): carrier.seat}, (0, 0), True,
                           is_attached=False, counts=counts)
    assert rider.seat is None
    rec = TG.Split(1, "dsf:obj564", TG._MR.resource, "/x/roof.obj", TG.LAT, TG.LON,
                   0.0, (rider,))
    out = OFS.group_zero(rec, TG._MR, pw, zeros, counts, "unit:24",
                         file_root={carrier.new_resource: "fu:24:559"}, solo=solo,
                         led=led)
    assert TG._zero_of(out.bodies[0]) == 416.807
    assert out.bodies[0].seat is None
