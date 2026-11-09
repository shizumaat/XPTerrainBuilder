"""THE TILE'S CLIMATE from X-Plane 12's own Global Scenery (issue #1965).

The tile's default DSF names its landclass terrains and forests with
X-Plane's climate tags; ``auto_patch_v2.airport.pack_climate`` reads
the climate from those names (:func:`tile_climate`).  Only the DSF's
DEFINITIONS are read: DSFTool streams the dump to a pipe and is stopped
at the first non-definition row (``O4_DSFTool.head``; about a second,
nothing written).  Without a Global Scenery tile, or when DSFTool cannot
read it, the latitude band stands in.  Memoised per tile and file:
the default scenery does not change under a running engine.
"""
from __future__ import annotations

import os
import typing as _t

__all__ = ["tile_climate", "global_dsf"]

#: Global Scenery packs under ``<X-Plane>/Global Scenery`` (X-Plane's
#: installer names, ``O4_Default_Terrain_Map``)
_PACKS = ("X-Plane 12 Global Scenery", "X-Plane 12 Demo Areas")
#: the dump's definition rows (and its preamble) — anything else ends them
_HEADER = ("PROPERTY", "TERRAIN_DEF", "OBJECT_DEF", "POLYGON_DEF",
           "NETWORK_DEF", "RASTER_DEF", "DIVISIONS", "HEIGHTS", "I", "A", "800",
           "DSF2TEXT", "#", "")

_MEMO: dict[tuple[str, float], _t.Any] = {}


def global_dsf(xroot: str, lat: int, lon: int) -> str | None:
    """The tile's Global Scenery DSF under the X-Plane folder ``xroot``;
    ``None`` when none is installed."""
    import O4_File_Names as FNAMES
    rel = os.path.join("Earth nav data", FNAMES.long_latlon(lat, lon) + ".dsf")
    roots = [os.path.join(xroot or "", "Global Scenery", p) for p in _PACKS]
    return next((os.path.join(r, rel) for r in roots
                 if os.path.isfile(os.path.join(r, rel))), None)


def _definitions(dsf: str) -> list[str]:
    import O4_DSFTool as _dsftool

    from .dsf_reader import _dsftool_path
    tool = _dsftool_path()
    if tool is None:
        return []
    lines = _dsftool.head([tool, "--dsf2text", dsf, "-"],
                          lambda ln: ln.split(" ", 1)[0].strip() not in _HEADER)
    return [ln.split(" ", 1)[1] for ln in lines
            if ln.endswith((".ter", ".for")) and " " in ln]


def tile_climate(xroot: str, lat: int, lon: int):
    """``pack_climate.Climate`` of the tile: X-Plane 12's own, else the
    latitude band's (module doc).  Never raises."""
    from auto_patch_v2.airport import pack_climate as _pc
    dsf = global_dsf(xroot, lat, lon)
    if dsf is None:
        return _pc.latitude_climate(lat + 0.5)
    try:
        key = (dsf, os.path.getmtime(dsf))
    except OSError:
        return _pc.latitude_climate(lat + 0.5)
    if key not in _MEMO:
        try:
            names = _definitions(dsf)
        except Exception:
            names = []
        _MEMO[key] = (_pc.climate_of_names(names)
                      or _pc.latitude_climate(lat + 0.5))
    return _MEMO[key]
