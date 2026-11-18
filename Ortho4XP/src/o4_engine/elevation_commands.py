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

Issue #2119 (owner 2026-11-16: "the base elevation is what is most useful
so that someone hand editing the patch and grade shapes to match the
terrain"): the reply also carries the BASE elevation the build reads
(module ``base_elevation``) — the built tile's production DEM (``.alt``: insets
baked, smoothed) where the tile is built, else the tile DEM with the
covering airport inset feathered in (``terrain_source.authored_source``)
— with ``base_label`` naming its source (``lidar 1 m``, ``DEM 90 m``),
``base_built`` (read from the build's ``.alt``), ``mesh_m`` (the built
mesh there, or None) and ``base_pending`` while a base source loads.
``elevation_m`` / ``source`` / ``pending`` keep their meaning (the mesh,
else the DEM) for the object seat, the patch insert and the relief.
"""
from __future__ import annotations

import math
import threading
from typing import Any, Callable, Dict, Optional

import O4_File_Names as FNAMES
from auto_patch_v2.airport.apt_dat import _file_identity as _stamp  # (mtime_ns, size) or None

from . import base_elevation as _base

__all__ = ["cursor_elevation"]

_LOCK = threading.Lock()
_MESH: Dict[str, tuple] = {}        # path -> (stamp, sampler | None)
_DEM: Dict[tuple, Any] = {}         # (lat, lon[, icao]) -> z_many(la, lo) | None
_ALT: Dict[str, tuple] = {}         # path -> (stamp, AltPoints | None)
_INSETS: Dict[tuple, tuple] = {}    # (lat, lon) -> (dir stamp, [InsetFootprint])
#: Tile DEMs with an airport inset feathered in that are kept at once (an
#: inset raster is up to ~200 MB; the cursor needs the one it is over).
_KEEP_INSET_DEMS = 2
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


def _dem_source(lat0: int, lon0: int, build_dir: Optional[str], icao: str = ""):
    """``(z_many | None, pending)`` for the tile's DEM, with ``icao``'s
    cached inset feathered in when one is named."""
    key = (lat0, lon0, icao) if icao else (lat0, lon0)
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
        return _src.authored_source(lat0, lon0, icao, root, cfg).z

    def store(z) -> None:
        if icao:                   # bound the inset rasters held
            held = [k for k in _DEM if len(k) == 3]
            for old in held[:max(0, len(held) - _KEEP_INSET_DEMS + 1)]:
                _DEM.pop(old, None)
        _DEM[key] = z

    _load_in_background(("dem", key), load, store)
    return None, True


def _alt_points(path: str, lat0: int, lon0: int):
    """The built ``.alt`` point reader, or None (no build, no frame)."""
    stamp = _stamp(path)
    if stamp is None:
        return None
    with _LOCK:
        cached = _ALT.get(path)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        reader = _base.AltPoints(path, lat0, lon0)
    except Exception:              # unreadable / frameless: not this source
        reader = None
    with _LOCK:
        _ALT[path] = (stamp, reader)
    return reader


def _inset_footprints(lat0: int, lon0: int):
    """``(footprints | None, pending)`` for the tile's cached insets."""
    key = (lat0, lon0)
    stamp = _stamp(FNAMES.airport_inset_directory(lat0, lon0))
    with _LOCK:
        cached = _INSETS.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1], False

    def load():
        from auto_patch_v2.law.model import Law
        return _base.inset_footprints(lat0, lon0, Law.load())

    _load_in_background(("insets", key), load,
                        lambda f: _INSETS.__setitem__(key, (stamp, f or [])))
    return None, True


def _z_at(z_many, lat: float, lon: float) -> Optional[float]:
    import numpy as np
    if z_many is None:
        return None
    z = float(np.asarray(z_many(np.array([lat]), np.array([lon])))[0])
    return z if math.isfinite(z) else None


def _base_fields(lat: float, lon: float, folder: str,
                   build_dir: Optional[str]) -> Dict[str, Any]:
    """The base fields of the reply (module docstring, #2119)."""
    lat0, lon0 = int(math.floor(lat)), int(math.floor(lon))
    footprints, pending = _inset_footprints(lat0, lon0)
    inset = _base.covering_inset(footprints or (), lat, lon)
    alt = _alt_points(_base.alt_path(folder, lat0, lon0), lat0, lon0)
    value = alt.z(lat, lon) if alt is not None else None
    built = value is not None
    if value is None and not pending:
        z_many, dem_pending = _dem_source(lat0, lon0, build_dir,
                                          inset.icao if inset else "")
        value, pending = _z_at(z_many, lat, lon), dem_pending
    label = (_base.source_label(inset, lat0, lon0)
             if value is not None and not pending else None)
    return {"base_m": value, "base_label": label, "base_built": built,
            "base_pending": bool(pending)}


def cursor_elevation(lat: float, lon: float,
                     build_dir: Optional[str] = None) -> Dict[str, Any]:
    """``{"elevation_m": float | None, "source": "mesh" | "dem" | None,
    "pending": bool}`` at ``(lat, lon)``, plus the base fields
    (:func:`_base_fields`) and ``mesh_m``."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("cursor_elevation: lat and lon must be degrees.") from None
    if not (math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"cursor_elevation: ({lat}, {lon}) is off the globe.")
    lat0, lon0 = int(math.floor(lat)), int(math.floor(lon))
    folder = build_dir or FNAMES.build_dir(lat0, lon0, "")
    base = _base_fields(lat, lon, folder, build_dir)
    sampler, pending = _mesh_sampler(FNAMES.mesh_file(folder, lat0, lon0), lat0, lon0)
    hit = sampler.sample_at_or_none(lat, lon) if sampler is not None else None
    if hit is not None:
        mesh = float(hit.elevation_metres)
        return {"elevation_m": mesh, "source": "mesh", "pending": False,
                "mesh_m": mesh, **base}
    z_many, dem_pending = _dem_source(lat0, lon0, build_dir)
    value = _z_at(z_many, lat, lon)
    return {"elevation_m": value, "source": "dem" if value is not None else None,
            "pending": bool(pending or dem_pending), "mesh_m": None, **base}
