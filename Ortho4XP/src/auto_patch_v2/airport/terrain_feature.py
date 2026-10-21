"""TERRAIN-FEATURE OBJECTS keep the author's placement (owner RULINGS
2026-10-20aq, issue #1169): "a large object to represent detailed terrain
features like a whole mountain or rocky point ... should be seated as the
author intended not reseated on top of new terrain, since it's meant to
cover terrain."

The rule reads GEOMETRY only (RULINGS 05e — no names).  A resource is a
terrain feature when its static solid geometry, binned on a ``CELL_M``
grid in its own plan frame, shows all three:

* a footprint far beyond a building's — at least ``MIN_AREA_M2`` of
  occupied cells;
* an underside that follows a slope — the lowest point per cell spans
  at least ``MIN_UNDERSIDE_SPAN_M`` (5th to 95th percentile);
* no floor plane — at most ``MAX_FLOOR_SHARE`` of the cells have their
  lowest point within ``FLOOR_BAND_M`` of the underside's 5th percentile.

The dry census (#1169) over six big packs: LXGB's rock, its detail mesh
and its tree cover (0.87–3.8 km2, underside 319–396 m, floor 0.05–0.06)
pass; the largest buildings of HECA / KATL / EDDF / OTHH / LFLL top out
at 0.44 km2 with an underside of 28 m, and none passes.

A terrain feature's ORIGIN SET — every row sharing its origin (the
author's one frame) — is kept as authored: never converted, never
re-seated, never split, and never read as ground the patch grades to.
"""
from __future__ import annotations

import functools
import os
import typing as _t

import numpy as np

__all__ = ["CELL_M", "MIN_AREA_M2", "MIN_UNDERSIDE_SPAN_M", "MAX_FLOOR_SHARE",
           "FLOOR_BAND_M", "underside", "is_terrain_feature",
           "file_is_terrain_feature", "feature_rows", "feature_ids"]

CELL_M = 10.0
MIN_AREA_M2 = 250_000.0
MIN_UNDERSIDE_SPAN_M = 50.0
MAX_FLOOR_SHARE = 0.25
FLOOR_BAND_M = 1.0


def underside(g: _t.Any) -> "tuple[float, float, float] | None":
    """``(occupied area m2, underside span m, floor share)`` of an
    ``obj8.ObjGeometry``'s static solid, or ``None`` when it has none."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    if v is None or len(v) < 3:
        return None
    ix = np.floor(v[:, 0] / CELL_M).astype(np.int64)
    iz = np.floor(v[:, 2] / CELL_M).astype(np.int64)
    key = (ix - ix.min()) * (int(iz.max() - iz.min()) + 1) + (iz - iz.min())
    order = np.argsort(key, kind="stable")
    k, y = key[order], v[order, 1]
    starts = np.r_[0, np.flatnonzero(np.diff(k)) + 1]
    cell_min = np.minimum.reduceat(y, starts)
    lo, hi = np.percentile(cell_min, [5.0, 95.0])
    return (len(starts) * CELL_M * CELL_M, float(hi - lo),
            float(np.mean(cell_min <= lo + FLOOR_BAND_M)))


def is_terrain_feature(g: _t.Any) -> bool:
    """The module rule on one parsed geometry."""
    u = underside(g)
    return u is not None and (u[0] >= MIN_AREA_M2 and u[1] >= MIN_UNDERSIDE_SPAN_M
                              and u[2] <= MAX_FLOOR_SHARE)


@functools.lru_cache(maxsize=4096)
def _file_verdict(path: str, mtime_ns: int, size: int) -> bool:
    from .obj8 import parse_obj8
    try:
        return is_terrain_feature(parse_obj8(path))
    except (OSError, ValueError):
        return False


def file_is_terrain_feature(path: str) -> bool:
    """The rule on an OBJ8 file (one verdict per file version)."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    return _file_verdict(path, st.st_mtime_ns, st.st_size)


def feature_rows(dump: _t.Any, pack_root: str) -> frozenset[int]:
    """The dump rows (ordinals) a terrain feature holds: every row of a
    pack resource that is one, and every row sharing its origin (lat,
    lon, heading, elevation)."""
    from .msl_feet import origin_of_row
    from .obj8 import is_stock_library_resource
    rows = list(getattr(dump, "placements", ()) or ())
    if not pack_root or not rows:
        return frozenset()
    seeds = {origin_of_row(p) for p in rows
             if getattr(p, "def_path", "")
             and not is_stock_library_resource(p.def_path)
             and file_is_terrain_feature(os.path.join(pack_root, p.def_path))}
    return frozenset(i for i, p in enumerate(rows) if seeds and origin_of_row(p) in seeds)


def feature_ids(placements: _t.Sequence[tuple], geometry: _t.Callable[[str], _t.Any]
                ) -> frozenset[str]:
    """The obj8 reader's half: ``placements`` are ``(id, def path, xy,
    heading, elevation, kind)``; ``geometry(def path)`` is the parsed
    geometry or ``None``.  The ids of every placement sharing an origin
    (xy, heading, elevation) with a terrain feature."""
    from .msl_feet import origin_key
    from .obj8 import is_stock_library_resource

    def key(xy: _t.Any, heading: float, elev: _t.Any) -> tuple:
        return origin_key(xy, heading) + (round(float(elev or 0.0), 3),)
    verdict: dict[str, bool] = {}
    for _i, d, _xy, _h, _e, _k in placements:
        if d not in verdict:
            verdict[d] = (not is_stock_library_resource(d)
                          and is_terrain_feature(geometry(d)))
    seeds = {key(xy, h, e) for _i, d, xy, h, e, _k in placements if verdict[d]}
    return frozenset(i for i, _d, xy, h, e, _k in placements
                     if seeds and key(xy, h, e) in seeds)
