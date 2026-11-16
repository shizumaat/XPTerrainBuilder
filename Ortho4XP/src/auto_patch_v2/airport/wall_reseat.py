"""A RETAINING WALL THE ENTRANCE READER RE-SEATS HAS ONE SEAT (#2099 F2 P4a;
owner RULINGS 2026-11-16a, 2026-11-06c (3)/(5), 2026-10-29a Q299 (a); spec
``docs/specs/2099-F2.md`` §5).

An entrance face whose opening was misread and whose own read did not wall
it is walled and SEATED by the re-read (``trench_objects.mouth_portals``,
``Portal.wall_reseat``): its zero on the ground its walls retain, the
floor that zero plus its bottom.  The same placement may be a retaining
wall of record (``airport/wall_class``: graded by ``planar/wall_slope``
and ``constraints/road_ramp``), whose seat is its DEM at the anchor -- two
seats for one wall (MEASURED CYYZ ``Tx_E``: the wall read at 167.89, the
mouth at 172.02).  ONE seat, at the derivation: where the pack's objects
are read (``pipeline/build`` pack stage, the replay), the pins are read
once (``entrance_shade.entrance_pins``) and every pin walled by the re-read
attaches ``placement id -> zero`` (``floor - bottom``) as
``Airport.wall_reseats``; ``wall_class._seat_z`` returns it for that
member.  Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["attach_wall_reseats"]


def _reseats(pins: _t.Sequence) -> dict[str, float]:
    """``placement id -> zero`` for every pin walled by the re-read (module
    doc); the lowest zero where one placement has two such ends."""
    out: dict[str, float] = {}
    for p in pins:
        if getattr(p, "wall_reseat", False) and p.bottom_y is not None and p.floor_z is not None:
            z = float(p.floor_z) - float(p.bottom_y)
            out[str(p.object_id)] = min(z, out.get(str(p.object_id), z))
    return out


def attach_wall_reseats(airport, pins: _t.Sequence):
    """``airport`` with :attr:`Airport.wall_reseats` from ``pins``
    (``entrance_shade.entrance_pins``) -- called once, before the wall
    class is read (``attach_wall_shade``)."""
    return _dc.replace(airport, wall_reseats=_reseats(pins))
