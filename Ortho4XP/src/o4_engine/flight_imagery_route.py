"""The photo provider of a tile on a planned flight (#2048, RULINGS
2026-11-13n; owner 2026-11-13T13:53Z/13:55Z).

On a flight with a route, under the Fly pane's Automatic photo source,
every new tile -- the corridor's drapes, track mode's beside it, a full
build -- takes the DEPARTURE tile's provider up to the route's midpoint
and the DESTINATION tile's after it: no third (region-auto) provider in
between.  The one-tile blend of #2018 (``O4_Imagery_Provider_Blend``)
then sits at the one seam where the two sides meet.  Without a route
(free flight, build-ahead, a departure-only flight) the region-auto
choice of RULINGS 2026-11-13d stands (``O4_Imagery_Auto``).

* :func:`endpoint_provider` -- an endpoint's provider is its built
  tile's: the World pack's imagery record (``O4_World_Imagery_Record``),
  else the DDS names of the pack that draws it (an adopted or external
  tile); ``None`` when no tile is built there (the caller uses
  region-auto).
* :class:`RouteSplit` -- the two providers and the densified route; a
  tile goes to the side its centre's nearest route point lies on,
  measured along the route.  Plain data (:meth:`RouteSplit.to_dict`), so
  a drape's worker process (``world_drape_process``) carries it.
* :func:`set_active` / :func:`active` -- the running flight's split,
  read by ``world_job_run.photo_source``.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import O4_Flight_Plan as FP
import O4_World_Imagery_Record as IREC

__all__ = ["RouteSplit", "endpoint_provider", "split_for", "set_active",
           "active"]

Tile = Tuple[int, int]
_LOCK = threading.Lock()
_ACTIVE: "Optional[RouteSplit]" = None


@dataclass
class RouteSplit:
    """``departure`` / ``destination``: the providers of the two halves;
    ``samples``: the densified route ``[(lat, lon)]``."""

    departure: str
    destination: str
    samples: List[Tuple[float, float]]
    _along: List[float] = field(default_factory=list, repr=False)
    _sides: Dict[Tile, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.samples = [(float(a), float(b)) for a, b in self.samples]
        along, total = [0.0], 0.0
        for p, q in zip(self.samples, self.samples[1:]):
            total += FP.route_length_km([p, q])
            along.append(total)
        self._along = along

    @property
    def half_km(self) -> float:
        return self._along[-1] / 2.0 if self._along else 0.0

    def along_km(self, tile: Tile) -> float:
        """How far along the route the nearest route point to the tile's
        centre lies, km."""
        centre = (int(tile[0]) + 0.5, int(tile[1]) + 0.5)
        best = min(range(len(self.samples)),
                   key=lambda i: FP.route_length_km([centre, self.samples[i]]))
        return self._along[best]

    def side(self, tile: Tile) -> str:
        """``"departure"`` up to the midpoint (inclusive), else
        ``"destination"``."""
        key = (int(tile[0]), int(tile[1]))
        if key not in self._sides:
            self._sides[key] = ("departure" if self.along_km(key) <= self.half_km
                                else "destination")
        return self._sides[key]

    def provider(self, tile: Tile) -> str:
        return self.departure if self.side(tile) == "departure" else self.destination

    def to_dict(self) -> dict:
        return {"departure": self.departure, "destination": self.destination,
                "samples": [list(p) for p in self.samples]}

    @classmethod
    def from_dict(cls, data: dict) -> "RouteSplit":
        return cls(str(data["departure"]), str(data["destination"]),
                   [tuple(p) for p in data["samples"]])


def endpoint_provider(scenery_dir: str, tile: Tile,
                      drawn_dir: Optional[Callable[[Tile], Optional[str]]] = None
                      ) -> Optional[str]:
    """The provider of the built tile at an endpoint (module docstring);
    ``drawn_dir(tile)``: the folder of the pack drawing an external tile
    (``flight_job_run.drawn_build_dir``)."""
    import O4_World_Pack as WP

    from . import world_commands as WORLD
    lat, lon = int(tile[0]), int(tile[1])
    if scenery_dir and WP.holds_tile(scenery_dir, lat, lon):
        found = IREC.read(WORLD.pack_dir(scenery_dir), lat, lon).get("provider")
        if found:
            return str(found)
    folder = drawn_dir(tile) if drawn_dir is not None else None
    if folder and os.path.isdir(folder):
        found = IREC.from_folder(os.path.join(folder, "textures")).get("provider")
        if found:
            return str(found)
    return None


def split_for(points: Sequence[Tuple[float, float]],
              provider_of: Callable[[Tile], str]) -> Optional[RouteSplit]:
    """The split of the route through ``points`` (lat, lon), each
    endpoint's provider ``provider_of(tile)``; None for a route that
    goes nowhere (one tile, a departure-only plan)."""
    if len(points) < 2:
        return None
    if FP.route_length_km(points) <= 0.0:
        return None
    first, last = FP.tile_of(*points[0]), FP.tile_of(*points[-1])
    return RouteSplit(provider_of(first), provider_of(last), FP.densify(points))


def set_active(split: Optional[RouteSplit]) -> None:
    global _ACTIVE
    with _LOCK:
        _ACTIVE = split


def active() -> Optional[RouteSplit]:
    return _ACTIVE
