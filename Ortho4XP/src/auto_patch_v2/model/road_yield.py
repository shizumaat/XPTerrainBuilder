"""THE ROAD'S YIELD FROM ZONE 2, AS A RECORD (owner RULINGS 2026-10-20c, 39;
issue #951).

``planar/zones`` cuts every mapped carriageway running through a runway or
taxi band's zone 2 out of it (``planar/road_yield.BandYield``);
``planar/build`` records, per cut, the RIBBON vertices that stand in it and
the band it was cut from.  Those vertices are the band's kerb
(``PlanarMap.band_kerb_vertices``): no road target pulls them, and the zone
law holds them under that band's ceiling only (``constraints/zones``) — the
road follows its own ground below the band's grade.

No shapely here: the record is ids and the band's key."""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["RoadYield", "is_band_zone_ref"]

#: the zone families whose bands a road through zone 2 is cut from
_BAND_FAMILIES = ("runway", "taxi")


def is_band_zone_ref(ref) -> bool:
    """A runway / taxi adjacent-ground zone face's ref."""
    parts = str(ref or "").split(":")
    return len(parts) > 2 and parts[0] == "adjacent_ground" and parts[1] in _BAND_FAMILIES


@_dc.dataclass(frozen=True)
class RoadYield:
    """One carriageway's cut out of one band's zone 2."""

    #: the ribbon vertices standing in the cut, and the zone-1 lip's where
    #: the road crosses it
    kerb: frozenset[int]
    #: the band's key: ``"runway"`` / ``"taxi"``, code number, code letter
    family: str
    code_number: int | None
    code_letter: str | None
    #: a runway band's runway (``ZoneRegion.runway_ref``)
    runway_ref: str | None = None
    #: THE SEAM BESIDE THE ROAD (owner Q53 (1), 2026-10-20): the vertices
    #: where a runway band and a taxi band meet beside the cut — the taxi
    #: band's lift (its floor) yields there (``constraints/zones``)
    beside: frozenset[int] = frozenset()
