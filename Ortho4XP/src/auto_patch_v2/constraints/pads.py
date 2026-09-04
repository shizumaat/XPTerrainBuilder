"""BUILDING-PAD generator (RULINGS 2026-09-03h "pads yield", 2026-09-03i
"seniority follows from being governed", 2026-09-01g "weld = value";
``law/structures.toml [building_pad]``, ``precedence.toml`` ``rigid``).

A rigid role's face (a pad) is ONE flat value: a ``Flat`` group over
every vertex of its outer ring and holes.  Its LEVEL is set by what it
touches — the shared vertices with the apron carry the apron's own law,
so the group is levelled by its contact and never a pin the apron must
climb to (03h).  A DETACHED pad (no shared governed vertex) is still a
flat group; the objective's DEM term levels it (a DEM-levelled flat
group, never an invented seat).  No seat pin exists in v2.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import is_rigid_role
from ..model.airport import Airport
from ..model.constraints import Flat, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["pad_flats", "rigid_roles"]

GEN = "pads"


def rigid_roles(law: Law) -> tuple[str, ...]:
    """Every role the register marks rigid (data, never a list here)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if is_rigid_role(law, r)))


def pad_flats(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One ``Flat`` group per rigid face."""
    vw = view(planar, law)
    rows: list[Row] = []
    for f in vw.faces_of_role(rigid_roles(law)):
        group: list[int] = []
        seen: set[int] = set()
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v not in seen:
                    seen.add(v)
                    group.append(v)
        if len(group) < 2:
            continue
        rows.append(Flat(tuple(group), Source(
            GEN, "structures.building_pad weld_to_touching_pavement (2026-09-01g, 03h)",
            (f"face:{f.id}", f.ref))))
    return rows
