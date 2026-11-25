"""ONE SHAPE BUFFERED AT SEVERAL DISTANCES AT ONCE (#2206).

Shapely releases the GIL inside GEOS, so independent buffers of one shape
run side by side on threads.  Each thread buffers its OWN copy of the shape
(the same coordinates in the same order, read back from its WKB), so no
GEOS object is shared between threads; a buffer reads only the shape's
coordinates and the distance, so every result is the one a serial call
makes, byte for byte.  HECA's and KATL's taxi shoulder joins buffered the
whole road network once per reach, 5 and 8 reaches, the classify stage's
dearest operation.  ``geom`` imports nothing of v2.
"""
from __future__ import annotations

import typing as _t
from concurrent.futures import ThreadPoolExecutor

import shapely

__all__ = ["buffers"]

#: threads at most (the solver's own thread pools take 4, ``solve/linear``)
_WORKERS = 4


def buffers(geom, distances: _t.Iterable[float],
            repair: _t.Callable = lambda g: g) -> dict[float, _t.Any]:
    """``{d: repair(geom.buffer(d))}`` for every distinct ``d`` of
    ``distances``, the buffers taken on up to ``_WORKERS`` threads."""
    todo = sorted(set(distances))
    if len(todo) < 2:
        return {d: repair(geom.buffer(d)) for d in todo}
    wkb = shapely.to_wkb(geom)

    def one(d: float):
        return repair(shapely.from_wkb(wkb).buffer(d))

    with ThreadPoolExecutor(min(_WORKERS, len(todo)),
                            thread_name_prefix="o4-buffers") as pool:
        return dict(zip(todo, pool.map(one, todo), strict=True))
