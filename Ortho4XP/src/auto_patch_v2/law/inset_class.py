"""THE INSET'S SOURCE CLASS — the one reading of whether an airport's DEM
inset is credible lidar (spec §45 (3) (ii); flat-site detector S2).

Lives in ``law`` because three layers ask it — ``airport/flat_site`` (S2),
``planar/channel`` (§45 (19)(b): a credible inset is a depth witness only
where it reads a cut) and ``constraints/eat`` (owner RULINGS 2026-10-15e
(2): on credible lidar the EAT law is report-only) — and a reading two
packages need goes DOWN, never sideways.  The class comes from the pixel
size through :func:`law.tables.flat_source_class` (``lidar_credible_max_m``),
never a second pixel-size rule.  Duck-typed on the airport and the DEM so
``law`` imports nothing above it.
"""
from __future__ import annotations

import typing as _t

from .model import Law
from .tables import FLAT_CLASS_COARSE, FLAT_CLASS_LIDAR, flat_source_class

__all__ = ["dem_source_class", "ground_class", "lidar_credible"]


def dem_source_class(dem, law: Law) -> tuple[str | None, float | None, str]:
    """``(class, pixel_m, whence)``: the production sampler states the
    finest source that baked (``source_pixel_m``); a sampler stating
    nothing is an unknown class."""
    fn = getattr(dem, "source_pixel_m", None)
    if not callable(fn):
        return None, None, "unknown"
    pixel, whence = fn()
    if pixel is None:
        return (FLAT_CLASS_COARSE if whence == "base_tier" else None), None, whence
    return flat_source_class(law, pixel), float(pixel), whence


def ground_class(airport: _t.Any, law: Law) -> str | None:
    """THIS airport's ground source class (``lidar`` / ``fine`` /
    ``coarse``, ``None`` for a sampler stating nothing) — the flat-site
    verdict's own S2 class where the airport carries one, else the DEM's
    source class.  A refresh (``--refresh-data dem``, the owner's act)
    moves a site between classes with no law change: this is the only
    place that reading lives."""
    fv = getattr(airport, "flat_site", None)
    if fv is not None:
        klass = (fv.signals or {}).get("s2_source_class")
        if klass:
            return str(klass)
    try:
        klass, _pixel, _whence = dem_source_class(airport.dem, law)
    except Exception:                          # pragma: no cover - fixtures
        return None
    return None if klass is None else str(klass)


def lidar_credible(airport: _t.Any, law: Law) -> bool:
    """Whether THIS airport's inset is CREDIBLE lidar (:func:`ground_class`)."""
    return ground_class(airport, law) == FLAT_CLASS_LIDAR
