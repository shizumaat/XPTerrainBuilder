"""ONE local metric frame per airport (plan §1 row 1).

Every v2 coordinate is ``(x, y)`` metres in a transverse-Mercator frame
whose origin is the airport reference point; the frame carries the
``pyproj`` transformer factory so the loaders (M1) and the emit adapters
are the only places that touch lat/lon.  The canonical vertex identity is
the lat/lon rounded to ``law.emit.identity.coordinate_dp`` places (memory
``canonical-identity-join``) — computed here, once, so every producer
keys the same way.

No shapely / numpy: the frame is arithmetic over floats.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

XY = tuple[float, float]
LL = tuple[float, float]
Key = tuple[float, float]

__all__ = ["XY", "LL", "Key", "Frame", "identity_key"]


def identity_key(lat: float, lon: float, dp: int) -> Key:
    """Canonical identity of a coordinate: ``(round(lat, dp),
    round(lon, dp))``.  Two vertices with equal keys ARE one vertex;
    proximity never joins (RULINGS 2026-08-21 :1708)."""
    return (round(float(lat), dp), round(float(lon), dp))


@_dc.dataclass(frozen=True)
class Frame:
    """The airport's metric frame.

    ``icao``            the airport it serves;
    ``origin``          ``(lat, lon)`` of the frame origin (x = y = 0);
    ``identity_dp``     decimals of the canonical lat/lon key (from law);
    ``crs``             the PROJ string of the local frame (transverse
                        Mercator centred on the origin, metres).

    The transformers are built lazily from ``pyproj`` and cached on the
    instance; a frame is otherwise a plain value and pickles as one.
    """

    icao: str
    origin: LL
    identity_dp: int
    crs: str = ""

    def __post_init__(self) -> None:
        if not self.crs:
            lat, lon = self.origin
            object.__setattr__(
                self, "crs",
                f"+proj=tmerc +lat_0={lat:.9f} +lon_0={lon:.9f} "
                "+k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs")

    def transformers(self) -> tuple[_t.Callable[[float, float], XY],
                                    _t.Callable[[float, float], LL]]:
        """``(to_xy(lon, lat) -> (x, y), to_ll(x, y) -> (lat, lon))``.
        Imported here so ``model`` stays importable without pyproj."""
        from pyproj import Transformer  # local: the only geodesy import
        fwd = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        inv = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

        def to_xy(lon: float, lat: float) -> XY:
            x, y = fwd.transform(lon, lat)
            return (float(x), float(y))

        def to_ll(x: float, y: float) -> LL:
            lon, lat = inv.transform(x, y)
            return (float(lat), float(lon))

        return to_xy, to_ll

    def key(self, lat: float, lon: float) -> Key:
        """Canonical identity of a lat/lon in this frame's law."""
        return identity_key(lat, lon, self.identity_dp)
