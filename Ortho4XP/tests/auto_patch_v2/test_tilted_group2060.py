"""#2060 (owner sim read CYLW 1.0.510, 49.955886, -119.380657: "the
hangar here ... is floating").

Attributed on the owner's own plan: ``Hangar_9`` body b0 is a post-feet
body on a 1.4 m slope, seated by the SEAT TILT (10-01k Q1) about its
low corner, then moved +0.78 m by its connected group's zero (22o) — the
pad's median, a LEVEL body's zero.  Every wall stood 1.1-1.4 m over the
drawn mesh.  Two defects, two twins:

* a tilted body keeps its own zero in its group (``open_frame_seat.
  group_zero``): moving the pinned origin lifts the whole tilted plane;
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


def test_a_tilted_body_keeps_its_own_zero_in_its_group():
    pw = {1: ("fu:24:559/host", 417.877)}
    plan = types.SimpleNamespace(units=(types.SimpleNamespace(
        id="unit:24", agl_m=0.0,
        members=(types.SimpleNamespace(parts=(types.SimpleNamespace(pid=1),)),)),))
    zeros = OFS.root_zeros(pw, plan)
    level = _body(_walls())
    tilted = dc.replace(level, seat=_seat(_walls()))
    assert tilted.seat.applied
    counts: dict = {}
    out = OFS.group_zero(_split(tilted), _M, pw, zeros, counts, "unit:24")
    b = out.bodies[0]
    assert b.anchor.surface_z - b.anchor.y_zero == Z0
    assert counts.get("group_zero_tilted_kept") == 1
    assert "group_zero_bodies" not in counts
    # a LEVEL body of the same group still takes the group's zero (22o)
    lv = OFS.group_zero(_split(level), _M, pw, zeros, {}, "unit:24").bodies[0]
    assert round(lv.anchor.surface_z - lv.anchor.y_zero, 3) == 417.877
