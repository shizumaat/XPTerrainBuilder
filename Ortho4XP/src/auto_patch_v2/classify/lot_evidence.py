"""A LOT ONLY ON EVIDENCE; GROUNDSIDE PAVEMENT DEFAULTS TO ROAD (owner
2026-11-26T23:48Z, #2283 EKVG: "Probably we should default to road, and
only go to the more strict lot grading when we have more evidence to be
sure an area is a lot"; spec ``Ortho4XP/docs/specs/lot-evidence-default-road-20261126.md``).

A groundside face is graded under the LOT law (``parking_lot``, 5 %) only
when something says cars park on it.  The witnesses, strongest first:

* ``E1`` a mapped car park: OSM ``amenity=parking`` over at least
  ``[lot] parking_cover_fraction`` of the source page (``sources``);
* ``E2`` a mapped parking aisle inside the page (``sources``);
* ``E3`` parked cars: at least ``[car_lots] min_cars`` of the pack's
  parked-car objects seated on the ground inside the face (owner RULINGS
  2026-11-16p "use cars to identify lots"; ``car_lot.seated_cars``).

A road reaching a page, a road centreline inside it, or no reading at all
(§110) is NOT a witness: those faces are the DEFAULT ROAD
(``open_default.unclassified_groundside_role``) -- a ribbon by its
proportions is ``service_road``, any other shape the road-law plate
``groundside_pavement`` (10 %, 2 % across).  MEASURED EKVG ``dsf:pol23``
(the access road and its roundabout, 324 m over DEM 78.8-93.4 m, no car,
no OSM parking): §110 made it a 5 % lot that could not meet its ground."""
from __future__ import annotations

import numpy as np
import shapely

from .rules import Rules

__all__ = ["LotCars", "cars_evidence"]


class LotCars:
    """The pack's ground-seated parked cars, read once per classification."""

    def __init__(self, anchors: np.ndarray, min_cars: int) -> None:
        self.anchors = np.asarray(anchors, dtype=float).reshape(-1, 2)
        self.min_cars = max(int(min_cars), 1)

    @classmethod
    def of(cls, airport, rules: Rules) -> "LotCars":
        """The cars of ``airport`` (``car_lot.seated_cars``)."""
        from .car_lot import seated_cars
        return cls(seated_cars(airport, rules), rules.car_lots.min_cars)

    def on(self, face) -> int:
        """How many of the cars stand inside ``face``."""
        if not len(self.anchors) or face is None or face.is_empty:
            return 0
        return int(shapely.contains_xy(face, self.anchors[:, 0], self.anchors[:, 1]).sum())


def cars_evidence(face, cars: "LotCars | None") -> str:
    """``E3``: the witness string when at least ``min_cars`` parked cars
    stand on ``face``, else ``""``."""
    if cars is None:
        return ""
    n = cars.on(face)
    return f"E3: {n} parked cars on it" if n >= cars.min_cars else ""
