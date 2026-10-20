"""A CONVERTED ``OBJECT_MSL`` ROW IS SEATED BY ITS GEOMETRY'S FEET, NOT BY
ITS ORIGIN (owner answer 48, 2026-10-20, extending 14br (2) "the design
surface at its own feet"; issue #1102).

The 11d conversion turns every ``OBJECT_MSL`` row into an on-ground
``OBJECT`` row: X-Plane then puts the object's ORIGIN on the mesh.  That
is the author's seat only when the geometry stands on its origin.  A pack
that authored its objects against a datum away from them floats once the
elevation column is dropped: the whole model modelled metres above
``y = 0`` (LPHR: the tower, the terminal annexes, the cars and vans,
5.6–6.3 m), or the origin metres away from the geometry, on ground of
another height (LPHR's apron vehicles: the drape at their origin 31.5 m,
the ground under their wheels 27.5 m).

So a converted row that stands on no unit pad is seated by its ROW at
``surface − y``: ``y`` its geometry's lowest static feet, ``surface`` the
design surface UNDER them.

THE RULE'S LIMITS, each a witness in the geometry, none an airport:

* ROWS SHARING ONE ORIGIN ARE ONE RIGID SET.  An author who splits a
  model into files (by texture, by part: LPHR's cars are bodies, wheels
  and mirrors in seven files) places them all at one ``(lat, lon,
  heading, elevation)``; seating each by its own feet would pull the
  model apart.  Every row of the set takes ONE elevation — the one that
  centres the span of its feet's needs on the surface (the minimax: the
  worst foot is as far above as the worst below).
* GEOMETRY REACHING BELOW ITS ORIGIN (by more than ``tol``) keeps the
  on-ground conversion, and so does every row of its set: the author
  built that model around its origin (a skirt, a footing, a hillside
  building, a light mast's pole), and raising it onto its lowest vertex
  would float everything above the buried part.
* A set at a footprint unit's pad (the surface at its origin IS the
  unit's datum) or in a DECK unit is the unit's to seat.
* No graded face under its feet: the rows stay converted, X-Plane drapes
  them, and nothing is guessed.
* A resource that does not resolve inside the pack (a stock library
  object, an unreadable file): unchanged, counted.
* A seat equal to the drape at the origin within ``drape_tol`` is left to
  the drape: a written row would only freeze it.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

from ..model.placement import KIND_MSL

__all__ = ["static_vertices", "lowest_feet", "origin_set_lifts", "origin_key",
           "feet_seats"]

Surface = _t.Callable[[float, float], "float | None"]

#: one origin, to the DSF's own precision (1e-8° ≈ 1 mm; 1 mm of elevation)
_ORIGIN_DP = 8


def static_vertices(g: _t.Any) -> "np.ndarray | None":
    """The vertices of an ``obj8.ObjGeometry``'s STATIC solid triangles
    (an animated part never witnesses — issue #612); ``None`` when it has
    none."""
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    if not tris.shape[0]:
        return None
    return g.vertices[np.unique(tris.reshape(-1))]


def lowest_feet(path: str, band_m: float) -> "np.ndarray | None":
    """``(n, 3)`` authored ``(x, y, z)`` of the static solid vertices of the
    OBJ8 at ``path`` within ``band_m`` of its lowest one; ``None`` when the
    file has no static solid or cannot be read."""
    from . import obj8 as _obj8
    try:
        v = static_vertices(_obj8.parse_obj8(path))
    except (OSError, ValueError):
        return None
    if v is None:
        return None
    return v[v[:, 1] <= float(v[:, 1].min()) + band_m]


def origin_set_lifts(items: _t.Iterable[tuple[str, tuple, _t.Any]],
                     tol_m: float) -> dict[str, "float | None"]:
    """THE GUARD AND THE READ (owner Q54, 2026-10-20: "yes with the
    guard"), per ``OBJECT_MSL`` placement: ``items`` are ``(id, origin
    key, parsed geometry or None)``.  The rows of one origin are one set;
    a set holding a member whose static geometry reaches more than
    ``tol_m`` below its origin — or one that cannot be read — is GUARDED
    (``None`` for every member): the author built it around its origin,
    it keeps the on-ground conversion and is never split.  Every other
    member reads at the lift ``−y_min`` that stands its own lowest static
    feet on the ground at its origin, so the partition finds its feet and
    the split anchors each body on them."""
    sets: dict[tuple, list] = {}
    for oid, key, g in items:
        v = static_vertices(g) if g is not None else None
        sets.setdefault(key, []).append((oid, None if v is None else float(v[:, 1].min())))
    out: dict[str, "float | None"] = {}
    for members in sets.values():
        guarded = any(y is None or y < -tol_m for _i, y in members)
        for oid, y in members:
            out[oid] = None if guarded else -_t.cast(float, y)
    return out


def origin_key(xy: _t.Sequence[float], heading_deg: float) -> tuple:
    """One origin in the airport frame (mm) and heading (1e-3°)."""
    return (round(float(xy[0]), 3), round(float(xy[1]), 3), round(float(heading_deg), 3))


def _origin(p: _t.Any) -> tuple:
    return (round(float(p.lat), _ORIGIN_DP), round(float(p.lon), _ORIGIN_DP),
            round(float(p.heading_deg), 3),
            round(float(p.elevation or 0.0), 3))


def _foot_needs(p: _t.Any, feet: np.ndarray, surface: Surface) -> list[float]:
    """Per foot placed by row ``p``: the row elevation that puts THAT foot
    on the design surface under it (``surface − y``); a foot on no face
    gives nothing.  OBJ8's frame rotated by the heading
    (``obj8.placement_affine``'s convention): ``east = x·cos h − z·sin h``,
    ``north = −(x·sin h + z·cos h)``."""
    from .anchor_rule import _m_per_deg
    h = math.radians(float(p.heading_deg))
    c, s = math.cos(h), math.sin(h)
    ml, mo = _m_per_deg(float(p.lat))
    out = []
    for x, y, z in feet:
        e, n = x * c - z * s, -(x * s + z * c)
        got = surface(float(p.lat) + n / ml, float(p.lon) + e / mo)
        if got is not None:
            out.append(float(got) - float(y))
    return out


def _on_unit_pad(unit_seats: _t.Sequence[tuple], lat: float, lon: float,
                 z: "float | None", tol_m: float) -> bool:
    """Whether the point stands on a footprint unit's pad: inside the
    smallest unit box containing it, whose datum the surface there equals
    within ``tol_m`` — or whose datum is a DECK (§16g (5)'s own reading)."""
    boxes = sorted(unit_seats, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    for la0, lo0, la1, lo1, zero, src in boxes:
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return src == "deck" or (z is not None and abs(z - zero) <= tol_m)
    return False


def _bump(c: dict, key: str, n: int = 1) -> None:
    c[key] = c.get(key, 0) + n


def feet_seats(dump: _t.Any, conversions: _t.Sequence[_t.Any], surface: Surface,
               pack_root: str, unit_seats: _t.Sequence[tuple] = (), *,
               tol_m: float = 0.3, drape_tol_m: float = 0.02,
               counts: "dict[str, int] | None" = None) -> tuple[tuple, tuple]:
    """``(msl seats, conversions left)``: the converted ``OBJECT_MSL`` rows
    re-seated by their ROW with their feet on the surface (the module
    docstring); every other conversion is returned as it was."""
    c = counts if counts is not None else {}
    rows = list(getattr(dump, "placements", ()) or ())
    sets: dict[tuple, list] = {}
    for cv in conversions:
        if cv.kind_before == KIND_MSL and 0 <= cv.index < len(rows):
            sets.setdefault(_origin(rows[cv.index]), []).append(cv)
    memo: dict[str, "np.ndarray | None"] = {}

    def feet(res: str) -> "np.ndarray | None":
        if res not in memo:
            phys = os.path.join(pack_root or "", res)
            memo[res] = (lowest_feet(phys, tol_m)
                         if pack_root and os.path.isfile(phys) else None)
        return memo[res]

    seats: list = []
    for members in sets.values():
        seats += _seat_set(members, [feet(m.resource) for m in members], rows,
                           surface, unit_seats, tol_m, drape_tol_m, c)
    _bump(c, "msl_feet_seated", len(seats))
    moved = {s.index for s in seats}
    return tuple(seats), tuple(cv for cv in conversions if cv.index not in moved)


def _seat_set(members: list, feet: list, rows: list, surface: Surface,
              unit_seats: _t.Sequence[tuple], tol_m: float, drape_tol_m: float,
              c: dict) -> list:
    """The seats of ONE origin's rigid set: every member at the one
    elevation centring its feet's needs on the surface — or none."""
    from ..model.placement import MslSeat
    if any(f is None for f in feet):
        _bump(c, "msl_feet_unresolved", len(members))
        return []
    if min(float(f[:, 1].min()) for f in feet) < -tol_m:
        _bump(c, "msl_feet_below_origin", len(members))
        return []
    p = rows[members[0].index]
    z0 = surface(float(p.lat), float(p.lon))
    if _on_unit_pad(unit_seats, float(p.lat), float(p.lon), z0, tol_m):
        _bump(c, "msl_feet_on_unit_pad", len(members))
        return []
    needs = [n for m, f in zip(members, feet, strict=True)
             for n in _foot_needs(rows[m.index], f, surface)]
    if not needs:
        _bump(c, "msl_feet_off_sheet", len(members))
        return []
    elev = (min(needs) + max(needs)) / 2.0
    if z0 is not None and abs(elev - float(z0)) <= drape_tol_m:
        _bump(c, "msl_feet_left_to_the_drape", len(members))
        return []
    _bump(c, "msl_feet_sets")
    return [MslSeat(m.index, m.resource, float(rows[m.index].lon),
                    float(rows[m.index].lat), float(rows[m.index].heading_deg),
                    elev, "geometry_feet") for m in members]
