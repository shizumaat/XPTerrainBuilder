"""THE FRONTAGE IS A WALL AWAY FROM ITS BUILDING (RULINGS 2026-11-25g (2),
25b (5); spec ``docs/specs/terminal-frontage-split-level-20261125.md``
§3.1 and C4/C30, lane lfront2).

A terminal-sized unit the ground and its pack agree stands on two floors
(``airport/unit_storey.unit_levels``, verdict ``held``) has its
groundside frontage at the groundside floor, a storey (or more) off the
airside floor its pad stands at.  Pavements touching, the step is a wall
(25b (5)): a groundside cell touching the unit's pad along the unit's
LANDSIDE FACE is never welded to the pad's rim -- it takes the pad's
set-back knife (``roles._cut_back_groundside``'s HELD arm), so it owns its
vertices and the frontage law (``constraints/kerb_frontage``) can hold
them at the groundside floor.  A mapped road reaching the pad there is
knifed too: it ramps to the frontage, never to the airside rim (25g (3);
13a (3)'s "ramp it" now reads the frontage's level).

Read here on the classified cells (the pads stand, §27 has run): the
airside the face is read against is every airside value cell but a pad;
the face's groundside test is not asked (the ribbons are not minted
yet).  The planar stage reads the same record again on its regions
(``planar/unit_levels_read``); a unit whose storey landside lot
``classify/storey_edge`` already cut back (PHLI) is that reader's, never
this one's."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["frontage_walls"]


def frontage_walls(airport, law, cells: _t.Sequence) -> dict[str, _t.Any]:
    """``{pad ref: the landside face}`` of every pad cell under a HELD
    two-floor unit (a quarter of the smaller plan or more), but a unit a
    storey landside lot already meets (module docstring)."""
    if airport is None or getattr(airport, "partition", None) is None:
        return {}
    from ..airport.unit_storey import carried_by, frontage_held, unit_levels
    from ..law.tables import is_value_role
    from .storey_edge import STOREY_UNIT_KEY
    air = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in cells
                       if c.side == "airside" and c.role != "building"
                       and is_value_role(law, c.role) and len(c.ring) >= 3])
    if air.is_empty:
        return {}
    taken = {int(u) for c in cells for u in (c.evidence or {}).get(STOREY_UNIT_KEY, ())}
    # no groundside test on the face: the road ribbons are minted after
    # the first set-back (``roles.classify``), so the groundside is not all
    # standing yet (MEASURED LDSP: 146 m of face against the map's 1,523 m)
    recs = [r for r in unit_levels(airport, law, air, ground=None)
            if r.unit not in taken and not r.face.is_empty
            and frontage_held(r, airport, law)]
    if not recs:
        return {}
    out: dict[str, _t.Any] = {}
    for c in cells:
        if c.role != "building" or len(c.ring) < 3:
            continue
        P = Polygon(c.ring, c.holes).buffer(0.0)
        for r in recs:
            if carried_by(r, P):
                out[str(c.ref)] = r.face
                break
    return out
