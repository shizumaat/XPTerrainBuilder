"""THE WALLED-PLATE RECORD (owner RULINGS 2026-10-27t / 2026-10-27u, #1201;
spec ``docs/specs/walled-plate-rsa-spec.md``) — what the recognition
(``airport/walled_plate``) hands every reader, in the airport frame.

A model record because three layers read it and none may import the
recogniser: the end area (``model/end_area``: the safety area ends at the
plate's inner edge, 27t), the ground under the plate (``constraints/
walled_plate``) and the seat (``airport/rebake_plan`` stamps the member's
plate datum, 27u).  Plain tuples of floats: it rides the partition cache.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["WalledPlate"]

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class WalledPlate:
    """One runway-end walled plate.

    ``ids`` — every placement of its origin set (one rigid group);
    ``runway`` / ``end`` — the runway id and the index of the end it caps;
    ``plate_y`` — the plate's authored height in the object's own frame
    (the y the seat puts on the ground); ``inner_s`` — the inner edge's
    median distance past the runway end over the safety area's width (where
    the safety area now ends, 27t); ``stations`` — the seat's stations,
    ``station_inset_m`` inside the inner edge; ``inner`` / ``outer`` — the
    inner and outer edge polylines; ``footprint`` — the plate's outline (the
    ground under it stays below it); ``height_m`` / ``step_m`` — the outer
    wall's depth under the plate and the DEM's step across it."""

    ids: tuple[str, ...]
    runway: str
    end: int
    plate_y: float
    inner_s: float
    stations: tuple[XY, ...]
    inner: tuple[XY, ...]
    outer: tuple[XY, ...]
    footprint: tuple[XY, ...]
    height_m: float
    step_m: float
    #: the runway end's name (reports only)
    end_name: str = ""
