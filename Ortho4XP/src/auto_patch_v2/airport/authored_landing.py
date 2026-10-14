"""THE AUTHORED PLACEMENT IS KEPT WHERE OUR GROUND ASKS NOTHING OF IT
(owner RULINGS 2026-10-14g (1)-(3); refs #662, #678).

A pack's DSF row is the author's statement about where his object
stands.  The placement law changes a row only where OUR ground requires
it; this module holds the three readings that say it does not:

1. an ``OBJECT_AGL`` row is KEPT AS AUTHORED — its height above ground is
   the author's statement about our terrain, so it is never converted to
   on-ground (only an ``OBJECT_MSL`` row, a hard-coded absolute, is —
   09-11b / 09-11d as narrowed by 14g (1)); a split of an AGL row keeps
   the lift on every body row (:func:`body_lift`).  A NEGATIVE column is a
   sink, not a lift (:func:`is_sink`): it converts as before, pending the
   owner's reading;
2. an ``OBJECT_AGL`` row is not re-expressed as ``OBJECT_MSL`` when the
   written elevation equals the drape within ``tol_m``
   (:func:`msl_changes_nothing`);
3. a placement is not split when every body would land within ``tol_m``
   of its authored seat (:func:`lands_on_authored_seat`) — it stays one
   placement of the original object.

The witness is the design surface (the ground X-Plane drapes on) at the
row and at each body's anchor — never a pack, an airport or a
coordinate.  Pure arithmetic; the callers hand the rows and the surface in.
"""
from __future__ import annotations

import typing as _t

from ..model.placement import KIND_AGL, KIND_MSL
from .basin_ring import REASON_RIM as _REASON_RIM

__all__ = ["is_sink", "body_lift", "authored_zero", "body_zero",
           "lands_on_authored_seat", "msl_changes_nothing"]

Surface = _t.Callable[[float, float], "float | None"]


def is_sink(row: _t.Any) -> bool:
    """An ``OBJECT_AGL`` row with a NEGATIVE column: a SINK, not a lift.
    14g (1) keeps the author's LIFT ("the AGL-lifted members", its cases
    lifts on decks, racks, masts and over water); a sunk row is converted
    and seated as before (09-11b) until the owner reads the sunk case
    (refs #678) — one predicate, read by the conversion and the split."""
    return (getattr(row, "kind", "OBJECT") == KIND_AGL
            and float(getattr(row, "elevation", 0.0) or 0.0) < 0.0)


def body_lift(row: _t.Any, anchor: _t.Any = None, *,
              reseated: bool = False) -> float:
    """14g (1): the lift a body row of this placement KEEPS — the AGL
    row's own column.  0 for a plain or ``OBJECT_MSL`` row (an MSL split
    is written on-ground, the 09-11b conversion), for a §18 RE-SEATED row
    (its seat is the law's, "§18 walls/pits stay as they are"), and for a
    body whose anchor puts its zero at a height the LAW states — a §16e
    DATUM (a crest plate, a deck top) or a basin RIM (§14: "the object's
    zero is the rim").  And 0 for a SINK (:func:`is_sink`)."""
    if getattr(row, "kind", "OBJECT") != KIND_AGL or reseated or is_sink(row):
        return 0.0
    if anchor is not None and (getattr(anchor, "datum", False)
                               or str(getattr(anchor, "reason", "")).startswith(
                                   _REASON_RIM)):
        return 0.0
    return float(getattr(row, "elevation", 0.0) or 0.0)


def authored_zero(row: _t.Any, surface: Surface) -> "float | None":
    """The height the AUTHORED row puts the object's zero at over our
    ground: the drape at the row (+ its lift for ``OBJECT_AGL``), or the
    ``OBJECT_MSL`` absolute.  ``None`` where no surface reads."""
    if getattr(row, "kind", "OBJECT") == KIND_MSL:
        z = getattr(row, "elevation", None)
        return None if z is None else float(z)
    g = surface(float(row.lat), float(row.lon))
    if g is None:
        return None
    lift = (float(getattr(row, "elevation", 0.0) or 0.0)
            if getattr(row, "kind", "OBJECT") == KIND_AGL else 0.0)
    return float(g) + lift


def body_zero(body: _t.Any, surface: Surface) -> "float | None":
    """Where a written body puts the AUTHORED zero: the drape at its
    anchor, plus the lift its row keeps (``body.lift_m``), minus the
    authored-frame ``y`` offset the cut subtracts.  ``None`` where the
    body is not a rigid translation of the authored object (a seat tilt
    is baked into its vertices) or no surface reads at its anchor."""
    seat = getattr(body, "seat", None)
    if seat is not None and getattr(seat, "applied", False):
        return None
    a = body.anchor
    g = surface(float(a.lat), float(a.lon))
    if g is None:
        return None
    return float(g) + float(getattr(body, "lift_m", 0.0) or 0.0) - float(a.offset[1])


def lands_on_authored_seat(bodies: _t.Sequence[_t.Any], row: _t.Any,
                           surface: Surface, tol_m: float) -> bool:
    """14g (3): does EVERY body land within ``tol_m`` of its authored
    seat?  Then the split moves nothing and the placement stays one
    placement of the original object.  ``tol_m`` 0, no body, no row or an
    unreadable surface answer ``False`` — the split stands."""
    if tol_m <= 0.0 or row is None or not bodies:
        return False
    z0 = authored_zero(row, surface)
    if z0 is None:
        return False
    for b in bodies:
        zb = body_zero(b, surface)
        if zb is None or abs(zb - z0) > tol_m:
            return False
    return True


def msl_changes_nothing(row: _t.Any, elevation: float, surface: Surface,
                        tol_m: float) -> bool:
    """14g (2): would writing ``OBJECT_MSL elevation`` for this AGL row
    change nothing — the drape at the row plus its lift equals it within
    ``tol_m``?  Then the row stays ``OBJECT_AGL`` and keeps following the
    mesh.  Only an AGL row is asked; ``tol_m`` 0 answers ``False``."""
    if tol_m <= 0.0 or getattr(row, "kind", "OBJECT") != KIND_AGL:
        return False
    z0 = authored_zero(row, surface)
    return z0 is not None and abs(float(elevation) - z0) <= tol_m
