"""THE DEM SAMPLES A CACHED READING TOOK, kept so a later run can ask its
own DEM the same questions (issue #382).

The pack reading stores ground it sampled: ``anchor_z`` on every placed
object, the witness depths and the part boxes built on it.  Its cache key
named no DEM, so a changed elevation inset or provider was a HIT carrying
the old ground (measured at HECA: every sample of the DEM moved 7.000 m,
3,199 placements served at the old ``anchor_z``).

WHY THE SAMPLES AND NOT A NAME FOR THE DEM.  The reading asks the DEM a
few thousand questions, all through ``DemSample.z`` — every anchor, the
four corners of a placement's extent, its component centroids.  Which
points they are is only known once the pack is parsed, so they cannot be
in the key that is taken before the read; they are RECORDED while the
reading runs (:class:`DemWitness`), stored in the cache file's header, and
a later read holds only if this run's DEM answers every one of them with
the same bits (:func:`holds`) — the §12a pattern the pack's own files
follow (size in the key, content in the header).  That is exact where a
name is not: the freshness gate's ``o4_dem`` stamp
(the tile driver's ``provenance.dem_fingerprint``) is built from a core tile
object only the tile driver holds, names files by size and mtime, and is
tile-wide — it would cold-start this airport for an inset fetched at
another one that moved none of these samples.  The cost is one batched
sample of the stored points on a HIT (milliseconds), nothing on a miss.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["DemWitness", "holds"]


class DemWitness:
    """A ``DemSample`` that answers exactly as ``dem`` does and remembers
    every question asked through :meth:`z` / :meth:`z_many`.  Everything
    else is ``dem``'s own attribute."""

    def __init__(self, dem: _t.Any) -> None:
        self._dem = dem
        self._xs: list[float] = []
        self._ys: list[float] = []
        self._zs: list[float] = []

    def z(self, x: float, y: float) -> float:
        v = self._dem.z(x, y)
        self._xs.append(float(x)); self._ys.append(float(y))
        self._zs.append(float("nan") if v is None else float(v))
        return v

    def z_many(self, xs: _t.Any, ys: _t.Any) -> np.ndarray:
        out = self._dem.z_many(xs, ys)
        self._xs.extend(np.asarray(xs, dtype=np.float64).ravel().tolist())
        self._ys.extend(np.asarray(ys, dtype=np.float64).ravel().tolist())
        self._zs.extend(np.asarray(out, dtype=np.float64).ravel().tolist())
        return out

    def __getattr__(self, name: str) -> _t.Any:
        return getattr(self._dem, name)

    def record(self) -> dict:
        """``{"xy": (N, 2) float64, "z": (N,) float64}`` — the questions in
        the order asked and the answers given."""
        return {"xy": np.column_stack([np.asarray(self._xs, dtype=np.float64),
                                       np.asarray(self._ys, dtype=np.float64)]),
                "z": np.asarray(self._zs, dtype=np.float64)}


def _sample(dem: _t.Any, xy: np.ndarray) -> np.ndarray:
    """``dem`` at every row of ``xy``: one batched call where the DEM has
    one, the scalar the reading itself used otherwise."""
    many = getattr(dem, "z_many", None)
    if many is not None:
        return np.asarray(many(xy[:, 0], xy[:, 1]), dtype=np.float64)
    out = np.empty(xy.shape[0], dtype=np.float64)
    for k, (x, y) in enumerate(xy.tolist()):
        v = dem.z(x, y)
        out[k] = np.nan if v is None else float(v)
    return out


def holds(dem: _t.Any, record: _t.Any) -> bool:
    """Whether ``dem`` gives every answer in ``record`` again, bit for bit
    (a NaN — outside the raster — must be a NaN again).

    A reading that recorded no DEM (``record`` is ``None``) or asked it
    nothing holds on any ground.  One that did never holds without a DEM,
    with an unreadable record, or on a DEM that raises."""
    if record is None:
        return True
    try:
        xy = np.asarray(record["xy"], dtype=np.float64).reshape(-1, 2)
        z = np.asarray(record["z"], dtype=np.float64).ravel()
        if z.shape[0] != xy.shape[0]:
            return False
        if not z.shape[0]:
            return True
        if dem is None:
            return False
        return bool(np.array_equal(_sample(dem, xy), z, equal_nan=True))
    except Exception:
        return False
