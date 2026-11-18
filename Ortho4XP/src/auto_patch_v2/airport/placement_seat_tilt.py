"""THE SEAT TILT: a POST-FEET body is seated by rotating the body, not by
cutting the terrain (owner RULINGS 2026-10-01k Q1; ``building-base-profile
-spec.md`` §8a Q1; issue #162).

The owner's words, verbatim: *"Apron grade under a structure with only
post feet, adjust angle of object if necessary to seat all the feet"*.

WHAT THE SITE IS
----------------

KASE's ``objects/airport/Shelters.OBJ`` is 247 × 46 m of shelter on
1,752 column feet, every one of them authored at ``y −0.10`` on a base
that fits a plane at 0.000 % — a FLAT post base with NO floor plate
(``obj8_grade.base_profile`` verdict :data:`obj8_grade.FEET`).  It stands
inside apron ``pav7``, where the hard 1.5 % grade cap carries the
hillside at 1.36 %, so the design surface runs 2353.4 → 2356.6 m along
the rows while the object's origin drapes at 2354.90: the NW end FLOATS
1.64 m and the SE end is BURIED 1.88 m.  That is the symptom the owner
read in the sim.

WHAT THE LAW DOES ABOUT IT
--------------------------

The terrain STAYS AT THE APRON GRADE — there is no block cut, and the
1.5 % cap is not bent.  A DSF ``OBJECT`` row carries HEADING only — the
only pitch X-Plane can apply is the OBJ8 header's own ``TILTED``, which
rotates the whole object to the terrain normal it samples under the
anchor, a seat NOTHING here can aim (it is read from the mesh, not from
the design surface, and under a split it differs body by body; #232 is
what it costs, and :data:`obj8_split.SEAT_OWNED_DIRECTIVES` is why no
file this stage writes carries it).  So the only thing left that can seat
the feet is the body's own geometry, and the object stage already
re-authors body files.  So:

1. fit a plane, by LEAST SQUARES, through the design-surface reads at the
   body's own ground-contact feet;
2. rotate the body about ITS ORIGIN by that plane's TILT — the rotation is
   baked into the written ``.obj`` vertices AND normals by
   ``obj8_split.split_obj8`` (rule 5), which is the only place a rotation
   can live;
2a. sink the body's zero until the tilt floats no foot further than the
   level seat did (:func:`_no_float_drop`, #2060 round 4) -- the rotation
   turns about the origin, not through the plane's intercept;
3. re-check every foot's residual against the EXISTING foot tolerance
   (``[placement] split_tol_m``, the 0.3 m the feet census already judges
   a body at) — nothing new is invented to judge it with;
4. record ``seat.tilt_deg`` / ``seat.roll_deg`` / ``seat.residual_max_m``
   in the object record, so the next read sees what was baked and why.

A body whose residual STILL exceeds tolerance after the tilt is
REPORTED — never a block cut (10-01k Q1's own sentence).  A tilt past
``[placement] seat_tilt_max_deg`` is likewise reported and NOT applied:
past that angle the surface under the feet is not an apron grade at all
but a riser or a bank, and pitching a 247 m structure to match one would
be the louder defect.

WHAT IS NEVER TILTED
--------------------

* A body whose base has a FLOOR PLANE (``base_profile`` verdict FLAT,
  STEPPED or SLOPED).  10-01k Q1 is about posts; a floor plane is seated
  by the pad law (Q2–Q5) and tilting it would lift one corner of a slab
  off its own pad.
* The STRUCTURE-SEATED classes — a basin, a deck, a plate — whose
  elevation another law governs, and an ELEVATED or CARRIED body, which
  lives in its carrier's frame (§16a) and cannot rotate alone.
* A LINE SEGMENT: a fence's drape is the segment cut's law (§10), station
  by station, and a rotation would fight it.
* A body on a DATUM, a unit seat or a connector (§16e / §16g): its zero is
  another body's and the rotation would break the pair.
* A body of a BUILDING GROUP (owner RULINGS 2026-11-18h, #2129): a body
  whose FRAME IS SHARED (issue #708) -- a §16c (7) bound sibling, the
  senior it is bound to, a body carried on it (§14 / §16a) -- and, read
  after every body is formed, a body that TOUCHES another of its frame
  (``touch_seat``).  The owner: "Why is the building tilted?  It should be
  flat."  A group seats LEVEL and rigid as one unit, every member at its
  authored relative height; the tilt is for a STANDALONE post-feet body
  only.  Where the fit WOULD rotate such a body, its seat records it
  (:attr:`SeatTilt.levelled`) and ``touch_seat`` seats the group where
  its lowest drawn edge meets the ground.  14p (1)'s shared-frame tilt
  and #2060's riders that followed it are retired with it.
* A body with fewer than three feet on the surface — three points is what
  a plane takes — or one every foot of which already stands within
  tolerance (there is nothing to seat).

This module DECIDES the tilt and nothing else; ``obj8_split.tilt_matrix``
is the one derivation of the rotation itself, so the residual this module
re-checks and the geometry the writer bakes cannot drift apart.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from . import anchor_rule as _ar
from . import obj8_grade as _og
from . import obj8_split as _split
from . import placement_carrier as _pc
from .placement_motion import foot_float, ground_contact_feet

__all__ = ["SeatTilt", "SEAT_REASON", "SEAT_TILT_MIN_DEG", "fit",
           "seat_tilt", "shared_frames", "frame_key", "applied_seat", "levelled"]

#: The prefix an anchor-reason-style note carries so a reader can tell the
#: seat tilt from every other reason without parsing a number.
SEAT_REASON = "seat tilt"
#: RULINGS 2026-11-18h: the note a building-group member's seat carries
#: where the fit would have rotated it
_LEVEL_REASON = "level: a building group seats level and rigid (RULINGS 2026-11-18h)"

#: Below this total angle nothing is baked (degrees).  It is a NUMERICAL
#: guard, not a law: the writer prints vertices to the millimetre, and
#: 1e-4° over a 250 m reach moves a vertex by 0.4 mm — under the
#: precision of the file it would be written into.  The real "is there
#: anything to seat" test is the foot tolerance, applied before the fit.
SEAT_TILT_MIN_DEG = 1.0e-4

#: The classes whose elevation another law owns: a basin rides its rim, a
#: deck its deck top, a plate its wall-plate seat, and a line segment its
#: own station drape.  None of them is a post-feet base.
_NEVER = frozenset({_ar.BASIN, _ar.DECK, _ar.PLATE_ONLY, _ar.LINE_SEGMENT})

#: The verdicts that mean THERE IS A FLOOR PLANE (base-profile spec §1
#: (2)); 10-01k Q1 tilts none of them.
_FLOOR_VERDICTS = frozenset({_og.FLAT, _og.STEPPED, _og.SLOPED})


@_dc.dataclass(frozen=True)
class SeatTilt:
    """What the seat decided for ONE body — the record 10-01k Q1 asks for.

    ``tilt_deg`` and ``roll_deg`` are defined by the fitted GRADIENTS and
    not by an Euler convention, so there is no sign to misread: the
    authored ``+z`` end of the body rises by ``tan(tilt_deg)`` per metre
    and its ``+x`` end by ``tan(roll_deg)``.  ``total_deg`` is the angle
    between the authored up axis and the fitted plane's normal — the one
    the cap governs, since a pitch and a roll together tilt the body by
    more than either.
    """

    #: the rise of the authored ``+z`` end, degrees (``atan(dy/dz)``)
    tilt_deg: float = 0.0
    #: the rise of the authored ``+x`` end, degrees (``atan(dy/dx)``)
    roll_deg: float = 0.0
    #: the total tilt of the body, degrees — what ``seat_tilt_max_deg`` caps
    total_deg: float = 0.0
    #: the worst |foot residual| AS THE BODY WILL BE WRITTEN: after the
    #: tilt where it was applied, before it where it was not
    residual_max_m: float = 0.0
    #: the worst |foot residual| with no tilt at all — the float/burial
    #: the owner read
    residual_before_m: float = 0.0
    #: the least-squares plane's own rms over the feet (metres)
    plane_rms_m: float = 0.0
    #: how many feet the fit saw (those on the surface, in the foot band)
    feet: int = 0
    #: was the rotation BAKED?  False with a non-zero ``total_deg`` is the
    #: capped case: reported, never applied.
    applied: bool = False
    #: ``True`` where the body is written with a worst foot still outside
    #: the foot tolerance — 10-01k Q1's REPORTED case, never a block cut
    over_tolerance: bool = False
    #: why, in one line, for the report and the record
    reason: str = ""
    #: the two AUTHORED-frame gradients the writer bakes
    #: (``obj8_split.BodyCut.tilt``); :data:`obj8_split.NO_TILT` when the
    #: tilt was not applied
    grad: tuple[float, float] = _split.NO_TILT
    #: #2060 round 4: how far the tilted body's ZERO is sunk so the tilt
    #: floats no foot further than the level seat did (:func:`_no_float_drop`)
    drop_m: float = 0.0
    #: RULINGS 2026-11-18h: the fit WOULD rotate this body, but it belongs to
    #: a building group, so it is written level (``applied`` False) and
    #: ``touch_seat`` seats its group where no edge floats
    levelled: bool = False

    def to_dict(self) -> dict[str, _t.Any]:
        return {"tilt_deg": round(self.tilt_deg, 4),
                "roll_deg": round(self.roll_deg, 4),
                "total_deg": round(self.total_deg, 4),
                "residual_max_m": round(self.residual_max_m, 4),
                "residual_before_m": round(self.residual_before_m, 4),
                "plane_rms_m": round(self.plane_rms_m, 4),
                "feet": int(self.feet),
                "applied": bool(self.applied),
                "over_tolerance": bool(self.over_tolerance),
                "grad": [self.grad[0], self.grad[1]],
                "drop_m": round(self.drop_m, 4),
                "levelled": bool(self.levelled),
                "reason": self.reason}


def fit(pts: _t.Sequence[_t.Tuple[float, float, float]],
        rise: _t.Sequence[float], *,
        max_total_deg: float, foot_tol_m: float) -> SeatTilt:
    """THE FIT (step 1–3 of the module doc), on numbers alone.

    ``pts`` are the feet in the body's OWN authored frame — ``(x, y, z)``
    after the split writer's translation, which is the frame the rotation
    is about — and ``rise[i]`` is how much higher foot ``i`` must render
    for it to meet the design surface (``placement_motion.foot_float``,
    the one reading §7's census uses, so the seat and the census cannot
    disagree about what a float is).

    The plane is the ordinary least-squares ``rise = c + gx·x + gz·z``.
    The INTERCEPT is fitted and then NOT applied: a rotation about the
    origin cannot translate the body, and the origin's height is already
    pinned to the design surface under the anchor.  Fitting it anyway is
    what makes ``gx`` / ``gz`` the plane's true gradients rather than a
    through-the-origin compromise — 10-01k Q1 says *the plane's tilt* —
    and whatever the intercept was shows up honestly in
    ``residual_max_m``, which is measured against the geometry as it will
    actually be written.

    ``np.linalg.lstsq`` is minimum-norm, so a single ROW of posts (the
    shelters: 247 m long, 46 m wide, every foot within a few metres of one
    line in the across direction) fits the gradient it can see and leaves
    the one it cannot at zero, instead of producing a wild cross-slope.
    """
    p = np.asarray(pts, dtype=float).reshape(-1, 3)
    d = np.asarray(rise, dtype=float).reshape(-1)
    n = int(min(p.shape[0], d.shape[0]))
    before = float(np.max(np.abs(d[:n]))) if n else 0.0
    if n < 3:
        return SeatTilt(residual_max_m=before, residual_before_m=before,
                        feet=n, reason=f"{SEAT_REASON}: {n} feet on the "
                                       f"surface, a plane takes three")
    p, d = p[:n], d[:n]
    if before <= float(foot_tol_m):
        return SeatTilt(residual_max_m=before, residual_before_m=before,
                        feet=n,
                        reason=f"{SEAT_REASON}: every foot within "
                               f"{float(foot_tol_m):g} m, nothing to seat")
    a = np.column_stack((p[:, 0], p[:, 2], np.ones(n)))
    sol, *_ = np.linalg.lstsq(a, d, rcond=None)
    gx, gz, c = (float(sol[0]), float(sol[1]), float(sol[2]))
    rms = float(np.sqrt(np.mean((a @ sol - d) ** 2)))
    total = math.degrees(math.atan(math.hypot(gx, gz)))
    tilt = SeatTilt(tilt_deg=math.degrees(math.atan(gz)),
                    roll_deg=math.degrees(math.atan(gx)),
                    total_deg=total, residual_before_m=before,
                    plane_rms_m=rms, feet=n)
    if total < SEAT_TILT_MIN_DEG:
        return _dc.replace(
            tilt, residual_max_m=before,
            reason=f"{SEAT_REASON}: {total:.5f} deg is below the "
                   f"{SEAT_TILT_MIN_DEG:g} deg the written file can carry")
    if total > float(max_total_deg):
        # 10-01k Q1: a tilt past the cap is REPORTED, not applied
        return _dc.replace(
            tilt, residual_max_m=before, over_tolerance=True,
            reason=f"{SEAT_REASON} REPORTED NOT APPLIED: {total:.3f} deg "
                   f"over the {float(max_total_deg):g} deg cap; worst foot "
                   f"{before:+.2f} m over {n} feet (intercept {c:+.2f} m)")
    rot = _split.tilt_matrix((gx, gz))
    after = p @ np.asarray(rot).T                    # the seated feet
    res = d + p[:, 1] - after[:, 1]
    drop = _no_float_drop(d, res)
    res = res + drop
    worst = float(np.max(np.abs(res)))
    over = worst > float(foot_tol_m)
    return _dc.replace(
        tilt, residual_max_m=worst, applied=True, over_tolerance=over,
        grad=(gx, gz), drop_m=drop,
        reason=(f"{SEAT_REASON} {total:.3f} deg (pitch {tilt.tilt_deg:+.3f}, "
                f"roll {tilt.roll_deg:+.3f}) seats {n} feet: worst "
                f"{before:+.2f} -> {worst:+.2f} m"
                + (f", zero sunk {drop:.2f} m so no foot floats (#2060)"
                   if drop else "")
                + (f", STILL over the {float(foot_tol_m):g} m foot "
                   f"tolerance (REPORTED, no block cut)" if over else "")))


def _no_float_drop(level: np.ndarray, tilted: np.ndarray) -> float:
    """#2060 round 4: THE TILT FLOATS NO FOOT (owner 2026-10-20f #1086,
    "so nothing floats"; 2026-10-22c, no support floats).  The rotation
    turns about the body's ORIGIN, pinned to the surface under its
    anchor, and the least-squares plane's intercept is dropped
    (:func:`fit`), so the fitted gradient lifts feet off their ground
    wherever the origin is not on that plane (CYLW ``Hangar_9`` b0: the
    level seat floats one foot 0.06 m, the full tilt one 0.45 m).
    ``level`` / ``tilted`` are each foot's rise owed (``foot_float``'s
    sign: ``-`` floats) before and after the tilt; returns how far the
    zero sinks so the tilted body floats no foot further than the level
    one did -- ``0.0`` when it already does not."""
    def floats(r: np.ndarray) -> float:
        return float(max(0.0, -float(np.min(r)))) if len(r) else 0.0
    drop = floats(tilted) - floats(level)
    # the rotation's rounding is no float: a sub-micron drop (6e-17 m on
    # Linux/Windows, 0 on macOS) renamed an unmoved rider's file per platform
    return drop if drop > _DROP_NOISE_M else 0.0


#: a :func:`_no_float_drop` under this is the rotation's float rounding
_DROP_NOISE_M = 1.0e-6


def _sunk(body: _t.Any, seat: "SeatTilt | None") -> _t.Any:
    """``body`` with its zero sunk by ``seat.drop_m`` (its anchor's
    ``y_zero`` and the offset's ``y`` raised by it); :func:`levelled`
    raises it back."""
    drop = float(getattr(seat, "drop_m", 0.0) or 0.0) if seat is not None else 0.0
    if drop <= 0.0 or not getattr(seat, "applied", False):
        return body
    a = body.anchor
    o = tuple(a.offset)
    return _dc.replace(body, anchor=_dc.replace(
        a, y_zero=float(a.y_zero) + drop, offset=(o[0], o[1] + drop, o[2])))


def frame_key(a: _t.Any) -> "tuple | None":
    """The written FRAME of an anchor: the point its row stands on and the
    zero its file's authored origin renders at (``surface_z - y_zero``).
    Two bodies with one key move as one; ``None`` off the surface."""
    if a.surface_z is None:
        return None
    return (round(float(a.lat), 9), round(float(a.lon), 9),
            round(float(a.surface_z) - float(a.y_zero), 3))


def shared_frames(staged: _t.Iterable[_t.Any]) -> frozenset[tuple[int, int]]:
    """``(member, body)`` slots of one unit whose frame another body shares
    (issue #708), read before any body is cut so the carrier — cut first —
    already knows it carries.

    ``staged`` are the unit's :class:`placement_record.Staged` members
    after the binds (pass 3): body ``k`` of a member takes the anchor of
    its group's senior, exactly as ``placement_file._group_bodies``
    forms it.  A slot is shared when another slot has its frame key (a
    §16c (7) bind copies the senior's whole anchor) or when any body is
    carried on it (``Staged.carried``'s candidate names the carrier's
    member and group)."""
    keys: dict[tuple, list[tuple[int, int]]] = {}
    shared: set[tuple[int, int]] = set()
    for st in staged:
        for k, grp in enumerate(st.groups):
            if grp:
                key = frame_key(st.raw[_pc.senior_of(st.raw, grp)][2])
                if key is not None:
                    keys.setdefault(key, []).append((st.mi, k))
        for _grp, c, _why in st.carried:
            shared.add((c.member, c.group))
    for slots in keys.values():
        if len(slots) > 1:
            shared.update(slots)
    return frozenset(shared)


def _excluded(body_class: str, a: _t.Any, merged: bool, elevated: bool) -> bool:
    """The bodies 10-01k Q1 never rotates (module doc)."""
    return bool(body_class in _NEVER or merged or elevated or a.datum
                or a.family or a.connector_of or a.unit_seat
                # §9a: an isolated share stays level (I6, #2063 round 3)
                or getattr(a, "isolated", ""))


def _verdict(m: _t.Any) -> str:
    return str((getattr(m, "base_profile", None) or {}).get("verdict") or "")


def _foot_rows(feet: _t.Iterable, a: _t.Any, offset: _t.Sequence[float],
               u: _t.Any, m: _t.Any, surface: _t.Any, band_m: float,
               contact_tol_m: float = 0.0) -> tuple[list, list, int]:
    """``(pts, rise, off_surface)``: the feet in the body's own authored
    frame (after the writer's translation by ``offset``) and how much
    higher each must render to meet the surface — :func:`fit`'s input.

    #2060: the feet are the GROUND-CONTACT feet (``ground_contact_feet``:
    within ``contact_tol_m`` of the lowest, the set §17 judges), not the
    whole metre band — CYLW's hangar door bottoms at y +0.89 read as feet
    and pulled the plane 1.3x too steep, floating its walls 0.3-0.6 m."""
    from .placement_plan import authored_offset  # circular at import time
    za, y0 = float(a.surface_z), float(a.y_zero)
    dx, dy, dz = (float(q) for q in offset)
    pts: list[tuple[float, float, float]] = []
    rise: list[float] = []
    off = 0
    for f in ground_contact_feet(feet, band_m, contact_tol_m):
        lat, lon, fy = float(f[0]), float(f[1]), float(f[2])
        zf = surface(lat, lon)
        if zf is None:
            off += 1
            continue
        ax, _ay, az = authored_offset(lat, lon, fy, u.anchor[0], u.anchor[1],
                                      m.heading_deg)
        pts.append((ax - dx, fy - dy, az - dz))
        rise.append(foot_float(float(zf), za, fy, y0))
    return pts, rise, off


def applied_seat(b: _t.Any) -> "SeatTilt | None":
    """``b``'s seat when its tilt is APPLIED (baked), else None (#2060 r2)."""
    s = getattr(b, "seat", None)
    return s if s is not None and getattr(s, "applied", False) else None


def seat_tilt(body: _t.Any, u: _t.Any, m: _t.Any, *,
              surface: "_ar.Surface | None",
              max_total_deg: float, foot_tol_m: float, band_m: float,
              counts: dict[str, int], shared: bool = False) -> _t.Any:
    """The body with its :class:`SeatTilt` decided, or the body unchanged.

    ``u`` / ``m`` are the plan's Unit / Member — the authored frame the
    offset is spelled in and the carrier of the member's own
    ``base_profile`` verdict.  Mirrors ``placement_deck.deck_seat``: one
    pure per-body step the plan applies after the bodies are formed, so
    nothing upstream has to know about the seat.  ``shared``: this body's
    frame is another body's too (:func:`shared_frames`) — a member of a
    building group, never rotated (RULINGS 2026-11-18h): where the fit
    would rotate it, it is written level with its seat marked
    :attr:`SeatTilt.levelled`.
    """
    if max_total_deg <= 0.0 or surface is None or not body.feet:
        return body
    a = body.anchor
    if _excluded(body.body_class, a, bool(body.merged_into), body.elevated):
        return body
    verdict = _verdict(m)
    if verdict in _FLOOR_VERDICTS:
        # 10-01k Q1 tilts a POST base; a floor plane is the pad law's
        counts["seat_tilt_floor_plane"] = \
            counts.get("seat_tilt_floor_plane", 0) + 1
        return body
    if verdict != _og.FEET:
        return body
    if a.surface_z is None:
        counts["seat_tilt_anchor_off_surface"] = \
            counts.get("seat_tilt_anchor_off_surface", 0) + 1
        return body
    pts, rise, off_surface = _foot_rows(body.feet, a, a.offset, u, m,
                                        surface, band_m, foot_tol_m)
    if off_surface:
        counts["seat_tilt_feet_off_surface"] = \
            counts.get("seat_tilt_feet_off_surface", 0) + off_surface
    seat = fit(pts, rise, max_total_deg=max_total_deg, foot_tol_m=foot_tol_m)
    if shared:
        counts["seat_tilt_shared_frame"] = \
            counts.get("seat_tilt_shared_frame", 0) + 1
        return _level(body, m, seat) if seat.applied else body
    if seat.applied:
        counts["seat_tilt_applied"] = counts.get("seat_tilt_applied", 0) + 1
        if seat.over_tolerance:
            counts["seat_tilt_residual_over_tol"] = \
                counts.get("seat_tilt_residual_over_tol", 0) + 1
    elif seat.over_tolerance:
        counts["seat_tilt_over_cap"] = counts.get("seat_tilt_over_cap", 0) + 1
    elif seat.feet < 3:
        counts["seat_tilt_too_few_feet"] = \
            counts.get("seat_tilt_too_few_feet", 0) + 1
    # §4.5 / 14at: the FILE IS KEYED ON WHAT IT BAKES, so a tilted body's
    # resource name must carry the tilt as it carries the offset
    from .placement_file import named_body  # R1: the one file-name rule
    return named_body(m, _sunk(body, seat), seat=seat)


def _level(body: _t.Any, m: _t.Any, seat: SeatTilt) -> _t.Any:
    """``body`` written LEVEL with ``seat`` marked levelled (18h)."""
    from .placement_file import named_body  # R1: the one file-name rule
    return named_body(m, body, seat=_dc.replace(
        seat, applied=False, over_tolerance=False, grad=_split.NO_TILT,
        drop_m=0.0, residual_max_m=seat.residual_before_m, levelled=True,
        reason=f"{_LEVEL_REASON}; the fit read: {seat.reason}"))


def levelled(body: _t.Any, m: _t.Any) -> _t.Any:
    """RULINGS 2026-11-18h: a TILTED ``body`` found in a building group
    after it was formed (``touch_seat``: it touches another body of its
    frame) written level again — its zero raised back by the tilt's
    :func:`_no_float_drop` sink, its seat marked levelled, its file
    renamed.  A body with no applied tilt is returned as it is."""
    seat = applied_seat(body)
    if seat is None:
        return body
    a = body.anchor
    o = tuple(a.offset)
    drop = float(seat.drop_m or 0.0)
    up = _dc.replace(body, anchor=_dc.replace(
        a, y_zero=float(a.y_zero) - drop, offset=(o[0], o[1] - drop, o[2])))
    return _level(up, m, seat)
