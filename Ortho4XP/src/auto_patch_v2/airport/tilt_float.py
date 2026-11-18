"""A SEAT TILT THAT FLOATS A FOOT IS UNDONE: THE FRAME SEATS LEVEL AT ITS
NO-FLOAT ZERO (owner RULINGS 2026-11-18h (4), #2129).

Owner 2026-11-18T18:09Z: "So far things have been looking mostly fine, so
maybe there's a more specific ruleset we could use to only fix problem
spots."  Rule (4): a seat tilt (``placement_seat_tilt``, capped by
``[placement] seat_tilt_max_deg`` / ``frame_tilt_max_deg``) applies only
if no ground-contact foot of the tilted body floats afterwards by more
than the materiality tolerance (``[placement] authored_keep_tol_m``,
0.05 m); otherwise the body seats LEVEL at the no-float zero.

WHY AT THE END.  The tilt is fitted when a body is formed, at the zero it
has then; later passes (the 22o group zero, ``open_frame_seat``) move the
body's zero and keep its rotation.  EDDH ``park_03__b0`` was fitted at its
own low-side zero and re-zeroed by its connected group: its plane then
stood 0.34-0.43 m over the ground at every foot (the columns the owner
read floating ~0.5 m).  So the test is read once, over the FINAL bodies,
as they will be written: every ground-contact foot rotated by the seat's
own gradients (``obj8_split.tilt_matrix``) about the body's own offset, at
its final zero, against the ground the plan seats on.

THE FRAME.  The bodies written in one tilted frame -- one plan unit, one
zero, one pair of gradients (a §16c (7) bound sibling, a body carried on
it, a rider tilted with its carrier: ``placement_seat_tilt.frame_tilts``
/ ``rider_seat``) -- are ONE rigid body: a foot of any of them floating
undoes the tilt of all of them, and they take ONE level zero, the highest
at which no ground-contact foot of the frame floats (``min(ground -
authored y)``; the rest is buried, 16v "better than floating") -- when
that sink is at most ``sink_max_m`` (16v's "less than a meter", ``touch_seat.
SEAT_MAX_M``).  A frame whose LEVEL seat floats more than that is no tilt
problem: the tilt is not what floats it, and rule (1) keeps it exactly as
it is (listed, ``unreached``; HECA's ``Hangar_Tower`` frame floats 11.2 m
level at its 22o group zero, EDDH's fire station 2.1 m).  The other
bodies of the connected group it was seated in (22o) are not moved here:
the touch pass after it seats the bodies that TOUCH it (16u/v), so a
group mate standing apart is not dragged down with it (EDDH
``park_04__b0`` shares its 22o group with the terminal, which it does not
touch).  A frame
with no foot on the ground keeps its zero.  What rides a levelled body is
the caller's (``touch_seat`` moves it by the same amount).

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from . import obj8_split as _split
from .placement_motion import foot_float, ground_contact_feet
from .placement_targets import _zero

__all__ = ["untilt_floating"]

#: the levelled body's reason
_REASON = ("seat tilt REFUSED: it floated a foot {f:.2f} m (RULINGS 2026-11-18h (4)); "
          "level at {z:.2f}")


def _floats_as_written(body: _t.Any, u: _t.Any, m: _t.Any, surface: _t.Any,
                      band_m: float, contact_tol_m: float) -> list[tuple]:
    """``[(lat, lon, authored y, level float, written float)]`` of
    ``body``'s ground-contact feet at its zero: LEVEL, and as WRITTEN --
    rotated by its applied seat about its offset (``+`` floats, ``-``
    buried); a foot off the surface is left out."""
    from .placement_plan import authored_offset  # circular at import time
    a = body.anchor
    seat = getattr(body, "seat", None)
    grad = (tuple(seat.grad) if seat is not None and getattr(seat, "applied", False)
            else _split.NO_TILT)
    rot = np.asarray(_split.tilt_matrix(grad), float)
    dx, dy, dz = (float(q) for q in a.offset)
    za, y0 = float(a.surface_z), float(a.y_zero)
    out = []
    for f in ground_contact_feet(body.feet or (), band_m, contact_tol_m):
        la, lo, fy = float(f[0]), float(f[1]), float(f[2])
        g = surface(la, lo)
        if g is None:
            continue
        ax, _ay, az = authored_offset(la, lo, fy, u.anchor[0], u.anchor[1], m.heading_deg)
        p = np.asarray([ax - dx, fy - dy, az - dz])
        level = -foot_float(float(g), za, fy, y0)
        out.append((la, lo, fy, level, level + float((rot @ p)[1] - p[1])))
    return out


def _level(body: _t.Any, m: _t.Any, z: float, worst: float) -> _t.Any:
    """``body`` written LEVEL at zero ``z``, its seat kept as the record of
    the refused tilt (``applied`` False, no gradient), its file renamed."""
    from .placement_file import named_body  # R1: the one file-name rule
    a = body.anchor
    y0 = float(a.surface_z) - z
    off = tuple(a.offset)
    why = _REASON.format(f=worst, z=z)
    seat = body.seat
    if getattr(seat, "applied", False):
        seat = _dc.replace(seat, applied=False, grad=_split.NO_TILT, drop_m=0.0,
                           residual_max_m=seat.residual_before_m,
                           reason=f"{why}; the fit read: {seat.reason}")
    return named_body(m, body, seat=seat, anchor=_dc.replace(
        a, y_zero=y0, offset=(off[0], y0, off[2]), reason=f"{why}; was: {a.reason}"))


def _frames(splits: _t.Sequence[_t.Any], members: _t.Mapping) -> dict[tuple, list]:
    """``{(unit, zero, gradients): [(record, body)]}`` of every tilted body."""
    out: dict[tuple, list] = {}
    for ri, rec in enumerate(splits):
        um = members.get(rec.placement_id)
        if um is None:
            continue
        for j, b in enumerate(rec.bodies):
            s = getattr(b, "seat", None)
            if s is None or not getattr(s, "applied", False) or b.anchor.surface_z is None:
                continue
            key = (str(um[0].id), round(_zero(b), 3),
                   tuple(round(float(g), 9) for g in s.grad))
            out.setdefault(key, []).append((ri, j))
    return out


def untilt_floating(splits: list, members: _t.Mapping, surface: _t.Any, *,
                    band_m: float, contact_tol_m: float, tol_m: float,
                    sink_max_m: float, counts: dict) -> tuple[dict, list]:
    """Rule (4) over the final bodies, in place on ``splits``: every tilted
    frame floating a foot more than ``tol_m`` as written, written level at
    its no-float zero, unless that sinks it more than ``sink_max_m``.
    Returns ``({(record, body): new zero}, listing)``, one listing row per
    frame that floats: ``(unit, worst float, old zero, new zero | None
    (unreached), files)``."""
    if surface is None:
        return {}, []
    moved: dict = {}
    listing: list = []
    for key, slots in sorted(_frames(splits, members).items()):
        rows = []
        for ri, j in slots:
            u, m = members[splits[ri].placement_id]
            b = splits[ri].bodies[j]
            rows.append((ri, j, b, m, _floats_as_written(b, u, m, surface, band_m,
                                                       contact_tol_m)))
        worst = max((f[4] for *_r, fs in rows for f in fs), default=0.0)
        if worst <= tol_m:
            continue
        sink = max(f[3] for *_r, fs in rows for f in fs)
        files = [str(b.new_resource) for _ri, _j, b, _m, _f in rows]
        if sink > sink_max_m:
            listing.append((key[0], round(worst, 3), key[1], None, files))
            counts["seat_tilt_float_unreached"] = (
                counts.get("seat_tilt_float_unreached", 0) + 1)
            continue
        z_new = key[1] - sink
        for ri, j, b, m, _fs in rows:
            rec = splits[ri]
            bs = list(rec.bodies)
            bs[j] = _level(b, m, z_new, worst)
            splits[ri] = _dc.replace(rec, bodies=tuple(bs))
            moved[(ri, j)] = z_new
        listing.append((key[0], round(worst, 3), key[1], round(z_new, 3), files))
    if moved:
        counts["seat_tilt_refused_floats"] = (counts.get("seat_tilt_refused_floats", 0)
                                              + len(moved))
    return moved, listing
