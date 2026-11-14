"""#2060 (owner sim read CYLW 1.0.510, 49.955886, -119.380657: "the
hangar here ... is floating").

Attributed on the owner's own plan: ``Hangar_9`` body b0 is a post-feet
body on a 1.4 m slope, seated by the SEAT TILT (10-01k Q1) about its
low corner, then moved +0.78 m by its connected group's zero (22o) — the
pad's median, a LEVEL body's zero.  Every wall stood 1.1-1.4 m over the
drawn mesh.  Two defects, two twins:

* a tilted body ALONE in its group share keeps its own zero
  (``open_frame_seat.group_zero``): moving the pinned origin lifts the
  whole tilted plane; a share with other objects still moves as one (22o);
* the tilt is fitted to the GROUND-CONTACT feet (``ground_contact_feet``),
  not the whole metre band: the door bottoms at y +0.89 pulled the plane
  1.3x too steep and left the walls 0.3-0.6 m up even on the tilt's zero.
"""
from __future__ import annotations

import dataclasses as dc
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8_grade as OG
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport import placement_seat_tilt as PST
from auto_patch_v2.airport.placement_record import Body, Split

LAT, LON = 49.9556, -119.3815
ML, MO = AR._m_per_deg(LAT)
GRADE = 0.015
Z0 = 417.10


def _ll(x_m: float, z_m: float) -> tuple[float, float]:
    return (LAT - z_m / ML, LON + x_m / MO)


def _surface(la: float, lo: float) -> float:
    return Z0 + GRADE * ((lo - LON) * MO)


class _U:
    anchor = (LAT, LON)


class _M:
    heading_deg = 0.0
    resource = "objects/hangar.obj"
    base_profile = {"verdict": OG.FEET}


def _body(feet, zero: float = Z0) -> Body:
    a = AR.Anchor(AR.BUILDING, LAT, LON, 0.0, "low-side foot", zero,
                  offset=(0.0, 0.0, 0.0))
    return Body(0, AR.BUILDING, (0,), a, "objects/hangar__b0.obj",
                feet=tuple(feet), pids=(1,))


def _walls():
    """a 60 m hangar's wall feet at authored y 0 along both long sides"""
    return [(*_ll(x, z), 0.0) for x in range(0, 61, 10) for z in (0.0, -40.0)]


def _doors():
    """door bottoms hanging 0.89 m over the floor near the low end"""
    return [(*_ll(x, -20.0), 0.885) for x in (5.0, 10.0, 15.0, 20.0)]


def _seat(feet):
    counts: dict = {}
    out = PST.seat_tilt(_body(feet), _U(), _M(), surface=_surface,
                        max_total_deg=1.5, foot_tol_m=0.3, band_m=1.0,
                        counts=counts)
    return out.seat


def test_the_tilt_fits_the_ground_contact_feet_not_the_door_bottoms():
    alone = _seat(_walls())
    mixed = _seat(_walls() + _doors())
    assert alone.applied and mixed.applied
    # the door bottoms change nothing: the plane is the walls' own
    assert abs(mixed.grad[0] - alone.grad[0]) < 1e-9
    assert abs(mixed.grad[0] - GRADE) < 1e-6
    assert mixed.residual_max_m < 0.01


def _split(*bodies):
    return Split(0, "dsf:obj0", _M.resource, "/x/" + _M.resource,
                 LAT, LON, 0.0, tuple(bodies))


def _plan(*members):
    return types.SimpleNamespace(units=(types.SimpleNamespace(
        id="unit:24", agl_m=0.0,
        members=tuple(types.SimpleNamespace(id=mid, parts=tuple(
            types.SimpleNamespace(pid=q) for q in pids)) for mid, pids in members)),))


def _z(rec):
    b = rec.bodies[0]
    return round(b.anchor.surface_z - b.anchor.y_zero, 3)


def test_a_tilted_body_alone_in_its_share_keeps_its_own_zero():
    pw = {1: ("fu:24:559/host", 417.877)}
    solo: set = set()
    zeros = OFS.root_zeros(pw, _plan(("dsf:obj563", (1,))), solo_out=solo)
    assert solo == {"fu:24:559|unit:24"}
    level = _body(_walls())
    tilted = dc.replace(level, seat=_seat(_walls()))
    assert tilted.seat.applied
    counts: dict = {}
    out = OFS.group_zero(_split(tilted), _M, pw, zeros, counts, "unit:24", solo=solo)
    assert _z(out) == Z0
    assert counts.get("group_zero_tilted_kept") == 1
    assert "group_zero_bodies" not in counts
    # a LEVEL body of the same share still takes the group's zero (22o)
    assert _z(OFS.group_zero(_split(level), _M, pw, zeros, {}, "unit:24", solo=solo)) == 417.877


def test_a_tilted_body_sharing_its_group_with_another_object_takes_the_group_zero():
    """22o: connected objects stay one group -- the keep is for a share
    with nothing else in it (HECA's material-split terminal pieces)."""
    pw = {1: ("fu:24:559/host", 417.877), 2: ("fu:24:559/host", 417.877)}
    solo: set = set()
    zeros = OFS.root_zeros(pw, _plan(("dsf:obj563", (1,)), ("dsf:obj564", (2,))),
                           solo_out=solo)
    assert not solo
    tilted = dc.replace(_body(_walls()), seat=_seat(_walls()))
    out = OFS.group_zero(_split(tilted), _M, pw, zeros, {}, "unit:24", solo=solo)
    assert _z(out) == 417.877


# ── round 2 (spec 2060-round2): tilt and zero belong to the FRAME, its
# carried riders included (14p (1): a shared frame tilts as one rigid group)

CARRIER = "objects/hangar__b0_tilted.obj"


def _rider(merged_into: str = CARRIER, body_id: int = 1, resource: str = "objects/roof.obj"):
    """A footless piece carried on the hangar: its carrier's anchor, no feet."""
    a = AR.Anchor(AR.BUILDING, LAT, LON, 0.0, f"carried by {merged_into} (rests on it)",
                  Z0, offset=(0.0, 0.0, 0.0))
    return Body(body_id, AR.BUILDING, (1,), a, f"{resource[:-4]}__b{body_id}.obj",
                feet=(), merged_into=merged_into, merged_into_written=True, elevated=True)


class _MR:
    heading_deg = 0.0
    resource = "objects/roof.obj"
    zero_y = 0.0


def _tilted_carrier():
    b = dc.replace(_body(_walls()), seat=_seat(_walls()))
    from auto_patch_v2.airport.placement_file import named_body
    return named_body(_M, b)


def test_a_cross_member_rider_takes_its_carriers_tilt_and_its_hash_follows():
    seat = _seat(_walls())
    seats = {(0, 0): seat}
    level = _rider()
    out = PST.rider_seat(level, _MR, seats, (0, 0), written=True)
    assert out.seat is seat and out.seat.grad == seat.grad
    assert out.new_resource != level.new_resource
    # the carrier's own file name moves by the same tilt: one hash
    carrier = _body(_walls())
    from auto_patch_v2.airport.placement_file import baked_name
    assert (baked_name(_M, carrier, seat).rsplit("_", 1)[1]
            == out.new_resource.rsplit("_", 1)[1])
    counts: dict = {}
    PST.rider_census([(out, (0, 0), True, False, None)],
                     {(0, 0): dc.replace(carrier, seat=seat)}, counts)
    assert counts == {"seat_tilt_rider_followed": 1}


def test_a_carrier_kept_whole_bakes_no_tilt_so_its_rider_takes_none():
    seats = {(0, 0): _seat(_walls())}
    level = _rider()
    assert PST.rider_seat(level, _MR, seats, (0, 0), written=False) is level
    assert PST.rider_seat(level, _MR, {(0, 0): None}, (0, 0), written=True) is level


def test_a_rider_left_level_on_a_tilted_carrier_is_counted():
    counts: dict = {}
    PST.rider_census([(_rider(), (0, 0), True, False, None)],
                     {(0, 0): _tilted_carrier()}, counts)
    assert counts == {"seat_tilt_level_rider": 1}


def _frame_with_rider(rider_heading: float):
    """One post-feet member whose body frame carries a footless piece of
    ANOTHER member placed at ``rider_heading``."""
    from test_seat_tilt_shared708 import _frame_staged
    from test_objtilt162 import _feet
    sts = _frame_staged([_feet(), _feet()])[:1]
    rider_m = types.SimpleNamespace(heading_deg=rider_heading, resource="objects/r.obj",
                                    base_profile={})
    carrier = types.SimpleNamespace(member=0, group=0)
    sts.append(types.SimpleNamespace(mi=1, m=rider_m, raw=[], groups=[],
                                     carried=[([0], carrier, "rests on it")]))
    return sts


def _frame_seats(sts):
    from test_objtilt162 import BAND_M, CAP_DEG, TOL_M, _U, _surface
    counts: dict = {}
    seats = PST.frame_tilts(sts, _U(), _surface(0.0136), max_total_deg=CAP_DEG,
                            frame_max_deg=1.0, foot_tol_m=TOL_M, band_m=BAND_M,
                            counts=counts)
    return seats, counts


def test_a_rider_at_another_heading_keeps_the_frame_level():
    """One rotation is one gradient pair only in one authored frame: a
    rider placed at another heading would bake another plane."""
    seats, counts = _frame_seats(_frame_with_rider(0.0))
    assert len(seats) == 1 and "frame_tilt_mixed_heading" not in counts
    seats, counts = _frame_seats(_frame_with_rider(90.0))
    assert seats == {} and counts["frame_tilt_mixed_heading"] == 1


def _solo():
    pw = {1: ("fu:24:559/host", 417.877)}
    solo: set = set()
    zeros = OFS.root_zeros(pw, _plan(("dsf:obj563", (1,))), solo_out=solo)
    return pw, zeros, solo


def _zero_of(b):
    return round(b.anchor.surface_z - b.anchor.y_zero, 3)


def test_a_solo_tilted_carrier_and_its_cross_member_rider_keep_the_carriers_zero():
    pw, zeros, solo = _solo()
    carrier = _tilted_carrier()
    led: set = set()
    counts: dict = {}
    out = OFS.group_zero(_split(carrier), _M, pw, zeros, counts, "unit:24",
                         solo=solo, led=led)
    assert _zero_of(out.bodies[0]) == Z0
    assert led == {"fu:24:559|unit:24"}
    # the rider is another member's record, cut AFTER its carrier: its root
    # is its carrier's (``file_root``), and it follows the kept zero
    rider = PST.rider_seat(_rider(carrier.new_resource), _MR,
                           {(0, 0): carrier.seat}, (0, 0), written=True)
    rec = Split(1, "dsf:obj1", _MR.resource, "/x/roof.obj", LAT, LON, 0.0, (rider,))
    out = OFS.group_zero(rec, _MR, pw, zeros, counts, "unit:24",
                         file_root={carrier.new_resource: "fu:24:559"}, solo=solo, led=led)
    assert _zero_of(out.bodies[0]) == Z0
    assert counts["group_zero_rider_kept"] == 1
    assert "group_zero_bodies" not in counts
    rc: dict = {}
    PST.rider_census([(rider, (0, 0), True, False, None)], {(0, 0): carrier}, rc)
    assert "seat_tilt_level_rider" not in rc


def test_a_solo_tilted_carrier_and_its_same_member_rider_keep_its_zero():
    pw, zeros, solo = _solo()
    carrier = _tilted_carrier()
    rider = PST.rider_seat(_rider(carrier.new_resource), _M,
                           {(0, 0): carrier.seat}, (0, 0), written=True)
    counts: dict = {}
    out = OFS.group_zero(_split(carrier, rider), _M, pw, zeros, counts, "unit:24",
                         file_root={carrier.new_resource: "fu:24:559"}, solo=solo,
                         led=set())
    assert [_zero_of(b) for b in out.bodies] == [Z0, Z0]
    assert counts.get("group_zero_tilted_kept") == 1
    assert counts.get("group_zero_rider_kept") == 1
    assert "group_zero_bodies" not in counts


def test_a_tilted_body_in_a_two_member_share_takes_the_group_zero_counted():
    pw = {1: ("fu:24:559/host", 417.877), 2: ("fu:24:559/host", 417.877)}
    solo: set = set()
    zeros = OFS.root_zeros(pw, _plan(("dsf:obj563", (1,)), ("dsf:obj564", (2,))),
                           solo_out=solo)
    led: set = set()
    counts: dict = {}
    out = OFS.group_zero(_split(_tilted_carrier()), _M, pw, zeros, counts, "unit:24",
                         solo=solo, led=led)
    assert _zero_of(out.bodies[0]) == 417.877 and not led
    assert counts["group_zero_tilted_moved"] == 1


def test_a_cut_deck_seat_clears_the_seat_it_no_longer_bakes(tmp_path):
    from test_cut_deck_seat1331 import _cut, _deck_obj, _member, _record, _surface
    from auto_patch_v2.airport import cut_deck_seat as CDS
    rec = _record()
    rec = dc.replace(rec, bodies=(dc.replace(rec.bodies[0], seat=_seat(_walls())),))
    out = CDS.seat_cut_decks(rec, _member(_deck_obj(tmp_path)), (40.0, -3.0), _surface(),
                             (_cut(),), 2.0, 0.5, {})
    assert out.bodies[0].seat is None and not out.bodies[0].merged_into
