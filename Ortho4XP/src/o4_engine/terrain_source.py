"""Which DEM the 3D preview's ``terrain_sample`` reads (patch-editor spec
§5, ruling 3 after L6a): the terrain the mesh drapes on when it can be
read from cache, else the authored one.

* ``production`` — the tile's composed production DEM as the last build
  wrote it: ``Data<tile>.alt`` in the tile's build folder (the request's
  ``build_dir``, else ``Tiles/``) with its frame
  sidecar (``O4_DEM_Utils.resolve_alt_frame``, #238), queried with the
  mesh's own bilinear (``dem_production._BakedTile.sample``, which is
  ``DEM.alt_vec_baked``).  Composing the production DEM afresh is a
  build's work (seconds to minutes) and is never done here.
* ``authored`` — ``dem.load_dem`` (the tile ``.hgt`` + the airport's
  inset), with the inset feather the tile's cfg resolves
  (``airport_elevation_inset_feather_m``, layered tile → global → default).

Read-only either way; nothing is downloaded or regenerated.
"""
from __future__ import annotations

import os
import typing as _t

import numpy as np

import O4_File_Names as FNAMES

__all__ = ["TerrainSource", "tile_config", "production_source", "authored_source"]


class TerrainSource(_t.NamedTuple):
    """``z(lat, lon)`` arrays → metres MSL (NaN where nothing covers);
    ``sources`` is the reply's ``{base, inset, frame}``."""

    z: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
    sources: dict


def tile_config(lat: int, lon: int, build_dir: str | None = None):
    """The tile's layered settings (the same reader a build uses), its
    ``build_dir`` the folder the app says the tile was built in (spec §2
    amendment (b)) or, absent, the default ``Tiles/`` one."""
    import O4_Config_Utils as CFG
    tile = CFG.Tile(lat, lon, build_dir or "")
    tile.read_from_config()
    return tile


def production_source(lat: int, lon: int, tile=None) -> TerrainSource | None:
    """The last build's ``.alt`` raster, or ``None`` when it is not on disk
    or its frame cannot be established."""
    import O4_DEM_Utils as DEM_UTILS
    from auto_patch_v2.airport.dem_production import _BakedTile
    try:
        tile = tile if tile is not None else tile_config(lat, lon)
        path = FNAMES.alt_file(tile)
    except Exception:              # no readable cfg: no build to read either
        return None
    if not os.path.isfile(path):
        return None
    raw = np.fromfile(path, dtype=np.float32)
    side = int(round(np.sqrt(raw.size)))
    if side < 2 or side * side != raw.size:
        return None
    try:
        frame = DEM_UTILS.resolve_alt_frame(path, side, lat, lon)
    except DEM_UTILS.AltFrameRefused:
        return None
    baked = _BakedTile(lat, lon, raw.reshape(side, side), frame["x0"], frame["x1"],
                       frame["y0"], frame["y1"])
    inside = (frame["x0"], frame["x1"], frame["y0"], frame["y1"])

    def z(la: np.ndarray, lo: np.ndarray) -> np.ndarray:
        out = baked.sample(la, lo)
        # the mesh's query clamps to the frame; outside it is not this tile
        x, y = lo - lon, la - lat
        off = (x < inside[0]) | (x > inside[1]) | (y < inside[2]) | (y > inside[3])
        out[off] = np.nan
        return out

    return TerrainSource(z, {"base": path, "inset": None, "frame": "production"})


def authored_source(lat: int, lon: int, icao: str, root: str,
                    tile=None) -> TerrainSource:
    """``dem.load_dem`` with the tile cfg's inset feather."""
    from auto_patch_v2.airport import dem as _dem
    from auto_patch_v2.model.frame import Frame
    feather = 60.0
    try:
        tile = tile if tile is not None else tile_config(lat, lon)
        feather = float(getattr(tile, "airport_elevation_inset_feather_m", feather))
    except Exception:              # a cfg the core cannot read: the default
        pass
    frame = Frame(str(icao), (lat + 0.5, lon + 0.5), identity_dp=9)
    sampler = _dem.load_dem(frame, root, str(icao), feather)
    return TerrainSource(sampler.z_many_ll, {"base": sampler.provenance.get("base"),
                                             "inset": sampler.provenance.get("inset"),
                                             "frame": "authored"})

