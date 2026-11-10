"""One on-demand landing: a finer tier of one texture fetched, converted
and landed over what is on disk (#1992 local-imagery-cache spec §4.4,
§4.7, phase P3b).

:class:`TierLander` is the follow job's real lander: called with an index
row (``O4_Imagery_OnDemand_Index``) and a tier (1, 2, 3 =
1024, 2048, 4096 px), it

* serves a FULL tier from the content-keyed ``DDS_cache`` by hard link
  when the row carries its key (no network, spec §4.4);
* else fetches the square ``drop`` zoom levels below the texture's own
  (``O4_Imagery_Utils.build_jpeg_ortho(drop=...)``: the build's own
  fetcher, AIMD window, ``Retry-After``, per-host budget, the per-file
  download lock) and converts it with the tile's frozen colour field and
  masks (``convert_texture(drop=...)``), which lands a WHOLE DDS under the
  texture's name (``O4_DDS_File.land``: partial name, ``os.replace``;
  rules R1-R3).  A full tier goes into ``DDS_cache``; 1024/2048 tiers go
  nowhere else.

It returns the facts the index records and raises :class:`LandFailed`
when nothing whole of that tier landed.  The tile objects are read once
per build folder (``O4_Config_Utils.Tile.read_from_config``).
"""
from __future__ import annotations

import os
import threading

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Disk_Usage as DISK
from O4_Imagery_Tier_Plan import TIER_WIDTH

__all__ = ["LandFailed", "TierLander", "texture_corner"]


class LandFailed(RuntimeError):
    """No whole file of the asked tier landed."""


def texture_corner(name: str) -> tuple[int, int]:
    """``(til_x_left, til_y_top)`` of ``<til_y>_<til_x>_<provider><zl>.dds``."""
    parts = os.path.basename(name).split("_", 2)
    if len(parts) < 3 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise ValueError(f"not a texture name: {name!r}")
    return int(parts[1]), int(parts[0])


def _drop(tier: int) -> int:
    """Zoom levels below the texture's own of tier ``tier`` (0..3)."""
    return TIERS.TIER_DROPS[int(tier)]       # (3, 2, 1, 0): tier 3 = full


class TierLander:
    """``lander(row, tier) -> {"tier_px", "full_bytes", "jpeg_path",
    "dds_cache_key", "network"}``; thread safe."""

    def __init__(self):
        self._tiles: dict = {}
        self._guard = threading.Lock()

    def _tile(self, row):
        """The tile object of ``row``'s build folder (read once)."""
        import O4_Config_Utils as CFG
        key = row["build_dir"]
        with self._guard:
            tile = self._tiles.get(key)
            if tile is None:
                lat, lon = _tile_latlon(row["tile"])
                tile = CFG.Tile(lat, lon, "")
                tile.build_dir = key
                tile.read_from_config()
                self._tiles[key] = tile
            return tile

    def __call__(self, row: dict, tier: int) -> dict:
        import O4_DDS_Cache as DDSCACHE
        import O4_Imagery_Utils as IMG
        final = os.path.join(row["build_dir"], "textures", row["name"])
        width = TIER_WIDTH[int(tier)]
        key = row.get("dds_cache_key")
        if width == TIERS.FULL_WIDTH and key and DDSCACHE.serve(key, final):
            return _facts(final, width, row.get("jpeg_path"), key, False)
        tile = self._tile(row)
        til_x, til_y = texture_corner(row["name"])
        attrs = (til_x, til_y, int(row["zl"]), row["provider"])
        drop = _drop(tier)
        if not IMG.build_jpeg_ortho(tile, *attrs, drop=drop):
            raise LandFailed(f"{row['name']}: the {width} px imagery did "
                             "not download")
        IMG.convert_texture(tile, *attrs, drop=drop)
        jpeg = os.path.join(*IMG._source_jpeg_location(tile, *attrs,
                                                       drop=drop))
        return _facts(final, width, jpeg, None, True)


def _tile_latlon(tile: str) -> tuple[int, int]:
    """``(+60, -136)`` from ``"+60-136"``."""
    return int(tile[:3]), int(tile[3:])


def _facts(final: str, width: int, jpeg, key, network: bool) -> dict:
    header = TIERS.texture_header(final)
    if header is None or header[0] != width or not DDS.is_whole(final):
        raise LandFailed(f"{os.path.basename(final)}: no whole {width} px "
                         "file landed")
    return {"tier_px": width, "full_bytes": DISK.freeable_bytes(final),
            "jpeg_path": jpeg, "dds_cache_key": key, "network": network}
