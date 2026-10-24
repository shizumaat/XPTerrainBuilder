"""``cursor_elevation`` — the elevation under the map cursor (protocol
1.14, issue #1308 part 3).

The answer is the BUILT mesh's (``Data<tile>.mesh`` in the request's
``build_dir``, else ``Tiles/``), read through the one ``.mesh`` reader,
``auto_patch.mesh_sampler.MeshElevationSampler``; a tile with no mesh, or a
point outside it, answers from the tile's DEM (``terrain_source``'s
authored reader) and says ``source: "dem"``.

The command is called on the transport's read loop, so it never loads
anything there: a mesh or DEM not yet in the cache is loaded on a daemon
thread and the reply says ``pending: true`` (with the DEM value when that
is already cached).  The client asks again while ``pending`` holds.  One
sampler per mesh path is kept, keyed by mtime and size, so a rebuild is
re-read; one DEM per tile.
"""
from __future__ import annotations

import math
import threading
from typing import Any, Callable, Dict, Optional

import O4_File_Names as FNAMES
from auto_patch_v2.airport.apt_dat import _file_identity as _stamp  # (mtime_ns, size) or None

__all__ = ["cursor_elevation"]

_LOCK = threading.Lock()
_MESH: Dict[str, tuple] = {}        # path -> (stamp, sampler | None)
_DEM: Dict[tuple, Any] = {}         # (lat, lon) -> z_many(la, lo) | None
_LOADING: set = set()


def _load_in_background(key: Any, load: Callable[[], Any],
                        store: Callable[[Any], None]) -> None:
    """``store(load())`` on a daemon thread, once per ``key`` at a time;
    a load that raises stores ``None`` (no answer from that source)."""
    with _LOCK:
        if key in _LOADING:
            return
        _LOADING.add(key)

    def work() -> None:
        try:
            value = load()
        except Exception:          # unreadable source: answer without it
            value = None
        with _LOCK:
            store(value)
            _LOADING.discard(key)

    threading.Thread(target=work, daemon=True, name="o4-cursor-elevation").start()


def _mesh_sampler(path: str, lat0: int, lon0: int):
    """``(sampler | None, pending)`` for the mesh at ``path``."""
    stamp = _stamp(path)
    if stamp is None:
        return None, False
    with _LOCK:
        cached = _MESH.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1], False

    def load():
        from auto_patch.mesh_sampler import MeshElevationSampler
        return MeshElevationSampler(path, (lon0, lat0, lon0 + 1, lat0 + 1))

    _load_in_background(("mesh", path), load,
                        lambda s: _MESH.__setitem__(path, (stamp, s)))
    return None, True


def _dem_source(lat0: int, lon0: int, build_dir: Optional[str]):
    """``(z_many | None, pending)`` for the tile's DEM."""
    key = (lat0, lon0)
    with _LOCK:
        if key in _DEM:
            return _DEM[key], False

    def load():
        from . import terrain_source as _src
        root = FNAMES.Elevation_dir
        try:
            cfg = _src.tile_config(lat0, lon0, build_dir)
        except Exception:          # a cfg the core cannot read: defaults
            cfg = None
        return _src.authored_source(lat0, lon0, "", root, cfg).z

    _load_in_background(("dem", key), load, lambda z: _DEM.__setitem__(key, z))
    return None, True


def cursor_elevation(lat: float, lon: float,
                     build_dir: Optional[str] = None) -> Dict[str, Any]:
    """``{"elevation_m": float | None, "source": "mesh" | "dem" | None,
    "pending": bool}`` at ``(lat, lon)``."""
    import numpy as np
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("cursor_elevation: lat and lon must be degrees.") from None
    if not (math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"cursor_elevation: ({lat}, {lon}) is off the globe.")
    lat0, lon0 = int(math.floor(lat)), int(math.floor(lon))
    folder = build_dir or FNAMES.build_dir(lat0, lon0, "")
    sampler, pending = _mesh_sampler(FNAMES.mesh_file(folder, lat0, lon0), lat0, lon0)
    if sampler is not None:
        hit = sampler.sample_at_or_none(lat, lon)
        if hit is not None:
            return {"elevation_m": float(hit.elevation_metres), "source": "mesh",
                    "pending": False}
    z_many, dem_pending = _dem_source(lat0, lon0, build_dir)
    value = None
    if z_many is not None:
        z = float(np.asarray(z_many(np.array([lat]), np.array([lon])))[0])
        value = z if math.isfinite(z) else None
    return {"elevation_m": value, "source": "dem" if value is not None else None,
            "pending": bool(pending or dem_pending)}
