"""Issue #708: a body whose written FRAME another body shares is never
seat-tilted alone (``placement_seat_tilt.shared_frames``).

KASE 1.0.394: the seat tilt (10-01k Q1, #162) rotated a hangar's senior
body by 1.16 deg about its own anchor while the walls bound to it and the
roofs carried on it stayed level on the same anchor and zero — 1.48 m of
separation at the far end of a 73 m body; 12 airport bodies so tilted.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_seat_tilt as PST

from test_objtilt162 import _body, _feet, _seat


def _anchor(lat: float, lon: float, z: float = 2356.0, y0: float = 0.0):
    return AR.Anchor(AR.BUILDING, lat, lon, y0, "median foot", z)


def _raw(anchor, feet: int = 4):
    # (parts, class, anchor, feet, elevated, ...) — what senior_of reads
    return ([object()], AR.BUILDING, anchor, tuple(range(feet)), False)


def _staged(mi: int, anchors, carried=()):
    return types.SimpleNamespace(
        mi=mi, raw=[_raw(a) for a in anchors],
        groups=[[i] for i in range(len(anchors))], carried=list(carried))


def test_a_shared_frame_body_is_not_rotated_and_is_counted():
    """The post-feet body the #162 twin tilts is left exactly as it was
    when its frame is shared."""
    tilted, _c = _seat()
    assert tilted.seat is not None and tilted.seat.applied
    counts: dict[str, int] = {}
    b = _body(_feet())
    from test_objtilt162 import (BAND_M, CAP_DEG, TOL_M, _M, _U,
                                 _surface)
    out = PST.seat_tilt(b, _U(), _M(), surface=_surface(),
                        max_total_deg=CAP_DEG, foot_tol_m=TOL_M,
                        band_m=BAND_M, counts=counts, shared=True)
    assert out is b
    assert counts == {"seat_tilt_shared_frame": 1}


def test_a_bind_shares_the_seniors_frame_across_members():
    """A §16c (7) bind copies the senior's whole anchor: both slots share."""
    hangar = _anchor(39.2243398, -106.8675213)
    other = _anchor(39.2250000, -106.8680000)
    staged = [_staged(0, [hangar, other]), _staged(1, [hangar])]
    shared = PST.shared_frames(staged)
    assert shared == {(0, 0), (1, 0)}


def test_a_carrier_shares_its_frame_with_what_it_carries():
    tank = _anchor(39.2247058, -106.8675622)
    carrier = types.SimpleNamespace(member=0, group=0)
    staged = [_staged(0, [tank]), _staged(1, [], carried=[([0], carrier, "rests on it")])]
    assert PST.shared_frames(staged) == {(0, 0)}


def test_a_lone_body_keeps_its_tilt_the_shelters_case():
    """The site 10-01k Q1 was ruled on (KASE's shelters) shares nothing."""
    staged = [_staged(0, [_anchor(39.2283684, -106.8688225)]),
              _staged(1, [_anchor(39.2283684, -106.8688225, y0=-0.5)])]
    # one point, two zeros: two frames, neither shared
    assert PST.shared_frames(staged) == frozenset()


# ── RULINGS 2026-10-14p (1): the shared frame tilts AS ONE, gently ──────

def _frame_staged(grade_feet):
    """Two members bound into ONE frame (a senior and a sibling sharing its
    whole anchor): each a post base whose feet span the shelter's length."""
    from test_objtilt162 import FOOT_Y, LAT, LON, Z0
    from auto_patch_v2.airport import obj8_grade as OG
    a = AR.Anchor(AR.BUILDING, LAT, LON, FOOT_Y, "median foot", Z0)
    sts = []
    for mi in (0, 1):
        m = types.SimpleNamespace(heading_deg=0.0, resource=f"objects/x{mi}.obj",
                                  base_profile={"verdict": OG.FEET})
        sts.append(types.SimpleNamespace(
            mi=mi, m=m, raw=[([object()], AR.BUILDING, a, grade_feet[mi], False)],
            groups=[[0]], carried=[]))
    return sts


def _frame(grade: float, frame_max: float):
    from test_objtilt162 import BAND_M, CAP_DEG, TOL_M, _U, _feet, _surface
    feet = _feet()
    half = len(feet) // 2
    sts = _frame_staged([feet[:half], feet[half:]])      # each its own half
    counts: dict[str, int] = {}
    seats = PST.frame_tilts(sts, _U(), _surface(grade), max_total_deg=CAP_DEG,
                            frame_max_deg=frame_max, foot_tol_m=TOL_M,
                            band_m=BAND_M, counts=counts)
    return seats, counts


def test_a_gentle_shared_frame_tilts_as_one_by_the_whole_groups_plane():
    """1.36 % = 0.78 deg, under the 1.0 deg frame cap: ONE seat for the
    frame, fitted to BOTH members' feet, every foot within tolerance."""
    import math
    from test_objtilt162 import APRON_GRADE, TOL_M
    seats, counts = _frame(APRON_GRADE, 1.0)
    assert len(seats) == 1 and counts["frame_tilt_applied"] == 1
    (seat,) = seats.values()
    assert seat.applied and seat.feet == 44            # both halves' feet
    assert abs(seat.total_deg - math.degrees(math.atan(APRON_GRADE))) < 1e-6
    assert seat.residual_max_m <= TOL_M


def test_a_steep_shared_frame_stays_level_and_rigid():
    """Past ``frame_tilt_max_deg`` nothing tilts: the group stays level."""
    seats, counts = _frame(0.0136, 0.5)
    assert seats == {} and counts["frame_tilt_over_cap"] == 1
    seats, _c = _frame(0.0136, 0.0)                    # 0 keeps every frame level
    assert seats == {}


def test_every_body_of_the_frame_takes_the_one_seat():
    from test_objtilt162 import _body, _feet, _M, _U, _surface, BAND_M, TOL_M
    seats, _c = _frame(0.0136, 1.0)
    (seat,) = seats.values()
    b = _body(_feet())
    out = PST.seat_tilt(b, _U(), _M(), surface=_surface(), max_total_deg=1.5,
                        foot_tol_m=TOL_M, band_m=BAND_M, counts={},
                        shared=True, frame_seat=seat)
    assert out.seat is seat and out.new_resource != b.new_resource
    assert PST.with_frame_seat(b, _M(), None) is b
