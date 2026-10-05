"""THE BUILD'S DEM, READ BY A WORK-POOL WORKER (issue #362; owner RULINGS
2026-10-04x (4)).

A pack reader samples the terrain (``airport.dem.z``) and nothing else of
the DEM.  The production DEM is one composed raster per 1° tile — ~1 GB at
OTHH — so it is never pickled to a worker: :func:`share` puts the tiles the
build has ALREADY composed in shared memory (``pool.SharedArrays``, one
copy) and returns a small token; :func:`revive` builds, in the worker, a
:class:`WarmDem` over the same pages.

The worker's sampler IS the build's: :class:`WarmDem` is a
``ProductionDem`` whose only difference is that it never composes.  A tile
the build had not composed when the token was cut is a tile whose
composition (its provenance note, its log line) belongs to the build's own
process, so a sample there raises :class:`ColdTile` and the caller runs
that reader on one core instead — never a second composition, never a
different answer.

A DEM that is not a ``ProductionDem`` (a twin's analytic surface) crosses
as itself.
"""
from __future__ import annotations

import typing as _t

from pyproj import Transformer

from .dem_production import ProductionDem, _BakedTile
from .pool import SharedArrays, attach

__all__ = ["ColdTile", "WarmDem", "share", "revive"]


class ColdTile(LookupError):
    """A worker sampled a tile the build had not composed (module doc)."""


class WarmDem(ProductionDem):
    """``ProductionDem.z`` / ``z_many`` over tiles composed elsewhere."""

    def __init__(self, frame, icao: str, tiles: dict) -> None:   # no corpus, no compose
        self.frame, self.icao = frame, icao
        self.provenance = {"frame": "production (shared with a pool worker)"}
        self._tiles = tiles
        self._inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)

    def tile(self, lat: int, lon: int):
        try:
            return self._tiles[(lat, lon)]
        except KeyError:
            raise ColdTile(f"DEM tile {lat:+03d}{lon:+04d} was not composed "
                           f"when the readers were handed out") from None


def _name(key: tuple[int, int]) -> str:
    return f"{key[0]},{key[1]}"


def share(dem) -> tuple[SharedArrays | None, tuple]:
    """``(the shared block to close when the workers are done, token)``.
    Raises ``OSError`` when the machine will not give the memory."""
    if not isinstance(dem, ProductionDem):
        return None, ("as_is", dem)
    tiles = dict(dem._tiles)
    shared = SharedArrays({_name(k): t.alt for k, t in tiles.items() if t is not None})
    rows = {k: None if t is None else (t.x0, t.x1, t.y0, t.y1) for k, t in tiles.items()}
    return shared, ("production", dem.frame, dem.icao, rows, shared.spec)


def revive(token: tuple) -> _t.Any:
    """The worker's sampler for a :func:`share` token."""
    if token[0] == "as_is":
        return token[1]
    _kind, frame, icao, rows, spec = token
    arrays = attach(spec) if spec else {}
    tiles = {k: None if r is None else _BakedTile(k[0], k[1], arrays[_name(k)], *r)
             for k, r in rows.items()}
    return WarmDem(frame, icao, tiles)
