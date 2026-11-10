"""One on-demand landing: a finer tier of one texture fetched, converted
and landed over what is on disk (#1992 local-imagery-cache spec §4.4,
§4.7, phase P3b).

:class:`TierLander` is the follow job's real lander: called with an index
row (``O4_Imagery_OnDemand_Index``) and a tier (1, 2, 3 =
1024, 2048, 4096 px), it

* lands the tier from the row's ``source_path`` -- the full DDS of a
  built tile converted to on-demand form (P1c), on a library volume --
  while that file is there and whole: the full file copied, a lower tier
  cut from its levels (``O4_DDS_Tiers.tier_from_file``); no network;
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

It returns the facts the index records and raises ``RuntimeError`` when
nothing whole of that tier landed (the job counts it as a failure).  The tile objects are read once
per build folder (``O4_Config_Utils.Tile.read_from_config``).

:meth:`TierLander.local` says a landing needs NO download (the full
tier's ``DDS_cache`` entry, or the tier's source JPEG, is on disk): at a
spawn or jump the follow job lands those first, inside X-Plane's
flight-start window (spec §4.5).
"""
from __future__ import annotations

import contextlib
import os
import threading

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Disk_Usage as DISK
from O4_Imagery_Tier_Plan import TIER_WIDTH

__all__ = ["TierLander"]


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

    def _source_jpeg(self, row: dict, tier: int) -> "str | None":
        """Where the tier's source JPEG is cached, for a provider with
        imagery of its own (a combined provider has no single file)."""
        import O4_Imagery_Utils as IMG
        if row["provider"] not in IMG.providers_dict:
            return None
        til_x, til_y = texture_corner(row["name"])
        return os.path.join(*IMG._source_jpeg_location(
            self._tile(row), til_x, til_y, int(row["zl"]), row["provider"],
            drop=_drop(tier)))

    def local(self, row: dict, tier: int) -> bool:
        """Can ``tier`` of ``row`` land with no download?  Never raises."""
        import O4_DDS_Cache as DDSCACHE
        try:
            key = row.get("dds_cache_key")
            if (TIER_WIDTH[int(tier)] == TIERS.FULL_WIDTH and key
                    and os.path.isfile(DDSCACHE.entry_path(key))):
                return True
            jpeg = self._source_jpeg(row, tier)
            return bool(jpeg) and os.path.isfile(jpeg)
        except Exception:               # unreadable tile: not local
            return False

    def __call__(self, row: dict, tier: int) -> dict:
        import O4_DDS_Cache as DDSCACHE
        import O4_Imagery_Utils as IMG
        final = os.path.join(row["build_dir"], "textures", row["name"])
        width = TIER_WIDTH[int(tier)]
        if _land_from_source(row.get("source_path"), final, width):
            return _facts(final, width, None, None, False)
        key = row.get("dds_cache_key")
        if width == TIERS.FULL_WIDTH and key and DDSCACHE.serve(key, final):
            return _facts(final, width, row.get("jpeg_path"), key, False)
        tile = self._tile(row)
        til_x, til_y = texture_corner(row["name"])
        attrs = (til_x, til_y, int(row["zl"]), row["provider"])
        drop = _drop(tier)
        jpeg = self._source_jpeg(row, tier)
        cached = bool(jpeg) and os.path.isfile(jpeg)
        if not IMG.build_jpeg_ortho(tile, *attrs, drop=drop):
            raise RuntimeError(f"{row['name']}: the {width} px imagery did "
                             "not download")
        IMG.convert_texture(tile, *attrs, drop=drop)
        return _facts(final, width, jpeg, None, not cached)


def _land_from_source(source, final: str, width: int) -> bool:
    """Land the ``width`` px tier of the full DDS ``source`` over ``final``
    (partial name, then ``O4_DDS_File.land``); ``False`` -- nothing
    written -- when there is no source, it is not mounted or not whole, or
    it holds no ``width`` px level."""
    import shutil
    if not source or not DDS.is_whole(source):
        return False
    header = TIERS.texture_header(source)
    if header is None or header[0] < width:
        return False
    partial = DDS.partial_name(final)
    try:
        if header[0] == width:
            shutil.copyfile(source, partial)
        else:
            data = TIERS.tier_from_file(source, width)
            if data is None:
                return False
            with open(partial, "wb") as handle:
                handle.write(data)
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(partial)
        return False
    return DDS.land(partial, final)


def _tile_latlon(tile: str) -> tuple[int, int]:
    """``(+60, -136)`` from ``"+60-136"``."""
    return int(tile[:3]), int(tile[3:])


def _facts(final: str, width: int, jpeg, key, network: bool) -> dict:
    header = TIERS.texture_header(final)
    if header is None or header[0] != width or not DDS.is_whole(final):
        raise RuntimeError(f"{os.path.basename(final)}: no whole {width} px "
                         "file landed")
    return {"tier_px": width, "full_bytes": DISK.freeable_bytes(final),
            "jpeg_path": jpeg, "dds_cache_key": key, "network": network}
