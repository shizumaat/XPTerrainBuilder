"""A CONVERTED ``OBJECT_MSL`` ROW IS SEATED BY ITS GEOMETRY'S FEET, NOT BY
ITS ORIGIN (owner answer 48, 2026-10-20, extending 14br (2) "the design
surface at its own feet"; issue #1102).

The 11d conversion turns every ``OBJECT_MSL`` row into an on-ground
``OBJECT`` row: X-Plane then puts the object's ORIGIN on the mesh.  That
is the author's seat only when the geometry stands on its origin.  A pack
that authored its objects against a datum below them — the whole object
modelled some metres above ``y = 0`` and the row's absolute elevation
lowering it back onto its ground — floats by exactly that height once
the elevation column is dropped (LPHR: the tower, the terminal annexes,
the cars and vans, 5.6–6.3 m).

So a converted row that stands on no unit pad is instead seated by its
ROW at ``surface − y_min``: the design surface at the placement minus the
lowest static vertex of its geometry, which puts the geometry's feet on
the surface.

THE RULE'S LIMITS, each a witness in the geometry, none an airport:

* ROWS SHARING ONE ORIGIN ARE ONE OBJECT.  An author who splits a model
  into several files places them all at one ``(lat, lon, heading,
  elevation)``; seating each piece by its own feet would pull the pieces
  apart.  The group's ``y_min`` is the lowest over its members, and every
  member takes the same seat.
* ONLY A LIFTED GEOMETRY MOVES (``y_min > tol``): geometry reaching BELOW
  its origin (a skirt, a footing, a hillside building, a light mast's
  pole) keeps the on-ground conversion — raising it to its lowest vertex
  would float everything above the buried part.
* A row in a footprint unit whose surface there IS the unit's datum
  (``tol``) stands on the unit's pad and is the unit's to seat; so is a
  row in a DECK unit.
* No graded face at the placement (``surface`` is ``None``): the row
  stays converted, X-Plane drapes it, and nothing is guessed.
* A resource that does not resolve inside the pack (a stock library
  object, an unreadable file): unchanged, counted.
"""
from __future__ import annotations

import os
import typing as _t

from ..model.placement import KIND_MSL

__all__ = ["lowest_static_foot", "feet_seats"]

#: one origin, to the DSF's own precision (1e-8° ≈ 1 mm; 1 mm of elevation)
_ORIGIN_DP = 8


def lowest_static_foot(path: str) -> "float | None":
    """The lowest authored ``y`` over the STATIC solid triangles of the
    OBJ8 at ``path`` (an animated part never witnesses — issue #612);
    ``None`` when the file has none or cannot be read."""
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return None
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    if not tris.shape[0]:
        return None
    return float(g.vertices[tris.reshape(-1), 1].min())


def _origin(p: _t.Any) -> tuple:
    return (round(float(p.lat), _ORIGIN_DP), round(float(p.lon), _ORIGIN_DP),
            round(float(p.heading_deg), 3),
            round(float(p.elevation or 0.0), 3))


def _on_unit_pad(unit_seats: _t.Sequence[tuple], lat: float, lon: float,
                 z: float, tol_m: float) -> bool:
    """Whether the point stands on a footprint unit's pad: inside the
    smallest unit box containing it, whose datum the surface there equals
    within ``tol_m`` — or whose datum is a DECK (§16g (5)'s own reading)."""
    boxes = sorted(unit_seats, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    for la0, lo0, la1, lo1, zero, src in boxes:
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return src == "deck" or abs(z - zero) <= tol_m
    return False


def feet_seats(dump: _t.Any, conversions: _t.Sequence[_t.Any],
               surface: _t.Callable[[float, float], "float | None"],
               pack_root: str, unit_seats: _t.Sequence[tuple] = (), *,
               tol_m: float = 0.02,
               counts: "dict[str, int] | None" = None,
               foot: _t.Callable[[str], "float | None"] = lowest_static_foot
               ) -> tuple[tuple, tuple]:
    """``(msl seats, conversions left)``: the converted ``OBJECT_MSL``
    rows whose geometry stands above its origin, re-seated by their ROW
    at ``surface − y_min`` (the module docstring); every other conversion
    is returned as it was."""
    from ..model.placement import MslSeat
    c = counts if counts is not None else {}
    rows = list(getattr(dump, "placements", ()) or ())
    groups: dict[tuple, list] = {}
    for cv in conversions:
        if cv.kind_before != KIND_MSL or not 0 <= cv.index < len(rows):
            continue
        groups.setdefault(_origin(rows[cv.index]), []).append(cv)
    memo: dict[str, "float | None"] = {}

    def y_min(res: str) -> "float | None":
        if res not in memo:
            phys = os.path.join(pack_root or "", res)
            memo[res] = foot(phys) if (pack_root and os.path.isfile(phys)) else None
        return memo[res]

    seats: list = []
    for key, members in groups.items():
        ys = [y_min(m.resource) for m in members]
        if any(y is None for y in ys):
            c["msl_feet_unresolved"] = c.get("msl_feet_unresolved", 0) + len(members)
            continue
        low = min(_t.cast("list[float]", ys))
        if low <= tol_m:
            continue                      # stands on (or reaches below) its origin
        z = surface(key[0], key[1])
        if z is None:
            c["msl_feet_off_sheet"] = c.get("msl_feet_off_sheet", 0) + len(members)
            continue
        if _on_unit_pad(unit_seats, key[0], key[1], float(z), tol_m):
            c["msl_feet_on_unit_pad"] = c.get("msl_feet_on_unit_pad", 0) + len(members)
            continue
        for m in members:
            p = rows[m.index]
            seats.append(MslSeat(m.index, m.resource, float(p.lon), float(p.lat),
                                 float(p.heading_deg), float(z) - low,
                                 "geometry_feet"))
        c["msl_feet_groups"] = c.get("msl_feet_groups", 0) + 1
    c["msl_feet_seated"] = c.get("msl_feet_seated", 0) + len(seats)
    moved = {s.index for s in seats}
    return tuple(seats), tuple(cv for cv in conversions if cv.index not in moved)
