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
  download lock) and converts it with the tile's frozen colour field
  (loaded with the tile object, :func:`_frozen_colour_field`) and masks
  (``convert_texture(drop=...)``), which lands a WHOLE DDS under the
  texture's name (``O4_DDS_File.land``: partial name, ``os.replace``;
  rules R1-R3).  A full tier goes into ``DDS_cache``; 1024/2048 tiers go
  nowhere else.

It returns the facts the index records and raises ``RuntimeError`` when
nothing whole of that tier landed (the job counts it as a failure).  The tile objects are read once
per build folder (``O4_Config_Utils.Tile.read_from_config``), and for a
tile another tool built (owner 2026-11-12T14:19Z, adopted tiles):

* the mask and imagery settings its own tool's cfg carries
  (:data:`OWN_KEYS`, ``Ortho4XP_<tile>.cfg`` beside it) over the global
  ones -- this app's tile layer never reads that file (RULINGS
  2026-10-26c);
* whatever any cfg says, a tile whose ``.ter`` files name mask PNGs
  (``BORDER_TEX ../textures/<y>_<x>_ZL<zl>.png``) is NEVER imprinted:
  imprinting writes the mask into the DDS alpha and deletes the PNG the
  ``.ter`` still names (:func:`_masks_named`).

A COMBINED provider (``Providers/*.comb``: its layers composited, no
cached JPEG of its own) is landed from the tile's own layers
(``O4_Imagery_Utils.initialize_local_combined_providers_dict(only=)``,
never the module's dict a build may be using): the full square is
composited and converted, and a lower tier is cut from it
(``O4_DDS_Tiers.tier_from_file``) -- the composite has no coarser fetch.

``TierLander(source_only=True)`` lands only from the row's source (no
cache, no network): Convert existing tiles keeps the imagery a tile
already has near custom airports (``world_adopt.keep_cores``).

:meth:`TierLander.local` says a landing needs NO download (the full
tier's ``DDS_cache`` entry, or the tier's source JPEG, is on disk): at a
spawn or jump the follow job lands those first, inside X-Plane's
flight-start window (spec §4.5).
"""
from __future__ import annotations

import contextlib
import os
import shutil
import threading

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Disk_Usage as DISK
import O4_Imagery_OnDemand_Index as INDEX
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


#: A tile another tool built: what its own cfg says of its masks and
#: imagery, read over the global settings.
OWN_KEYS = ("imprint_masks_to_dds", "mask_zl", "default_website",
            "zone_list")
#: A combined provider's landing composites under the module's dict.
_COMBINED = threading.Lock()


class TierLander:
    """``lander(row, tier) -> {"tier_px", "full_bytes", "jpeg_path",
    "dds_cache_key", "network"}``; thread safe."""

    def __init__(self, source_only: bool = False):
        self._tiles: dict = {}
        self._guard = threading.Lock()
        self.source_only = bool(source_only)

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
                _own_settings(tile)
                if _masks_named(row):
                    tile.imprint_masks_to_dds = False
                _frozen_colour_field(tile)
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
        final = INDEX.texture_path(row)
        width = TIER_WIDTH[int(tier)]
        if _land_from_source(row.get("source_path"), final, width):
            return _facts(final, width, None, None, False)
        if self.source_only:
            raise RuntimeError(f"{row['name']}: its source is not here")
        key = row.get("dds_cache_key")
        if width == TIERS.FULL_WIDTH and key and DDSCACHE.serve(key, final):
            return _facts(final, width, row.get("jpeg_path"), key, False)
        tile = self._tile(row)
        til_x, til_y = texture_corner(row["name"])
        attrs = (til_x, til_y, int(row["zl"]), row["provider"])
        if row["provider"] in IMG.combined_providers_dict:
            _land_combined(tile, attrs, final, width)
            return _facts(final, width, None, None, True)
        drop = _drop(tier)
        jpeg = self._source_jpeg(row, tier)
        cached = bool(jpeg) and os.path.isfile(jpeg)
        if not IMG.build_jpeg_ortho(tile, *attrs, drop=drop):
            raise RuntimeError(f"{row['name']}: the {width} px imagery did "
                             "not download")
        IMG.convert_texture(tile, *attrs, drop=drop)
        _mirror(os.path.join(row["build_dir"], "textures", row["name"]), final)
        return _facts(final, width, jpeg, None, not cached)


def _own_settings(tile) -> None:
    """A tile this app did not build: the :data:`OWN_KEYS` its own tool's
    cfg carries, over the global settings (each read as the type the tile
    already holds; a value that does not read is left)."""
    import ast

    import O4_Config_Names as CN
    import O4_Tile_Info as TINFO
    if TINFO.built_here(tile.build_dir, tile.lat, tile.lon):
        return
    path = os.path.join(tile.build_dir,
                        CN.ortho4xp_tile_cfg_name(tile.lat, tile.lon))
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return
    for line in lines:
        key, _eq, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key not in OWN_KEYS or not _eq:
            continue
        held = getattr(tile, key, None)
        try:
            if isinstance(held, bool):
                setattr(tile, key, value.lower() in ("true", "1", "yes"))
            elif isinstance(held, int):
                setattr(tile, key, int(value))
            elif isinstance(held, list):
                setattr(tile, key, list(ast.literal_eval(value or "[]")))
            else:
                setattr(tile, key, value)
        except (ValueError, SyntaxError, TypeError):
            continue


def _masks_named(row: dict) -> bool:
    """Do the tile's ``.ter`` files name a mask PNG (``<y>_<x>_ZL<zl>.png``,
    ``O4_File_Names.mask_file``)?  Its terrain folder: the row's, else
    its build folder's."""
    import re
    mask = re.compile(r"BORDER_TEX\s+\S*?\d+_\d+_ZL\d+\.png\s*$")
    for folder in (row.get("terrain_dir"),
                   os.path.join(row.get("build_dir") or "", "terrain")):
        try:
            names = os.listdir(folder) if folder else ()
        except OSError:
            continue
        for name in names:
            if not name.endswith(".ter"):
                continue
            with contextlib.suppress(OSError):
                with open(os.path.join(folder, name), encoding="utf-8",
                          errors="replace") as handle:
                    if any(mask.match(line.strip()) for line in handle):
                        return True
    return False


def _combined_layers(tile, provider: str) -> dict:
    """The tile's own layers of the combined ``provider`` (read once per
    tile object): ``{provider: [layer, ...]}``, ``{}`` when it has none
    there."""
    import O4_Imagery_Utils as IMG
    held = getattr(tile, "_o4_combined_layers", None)
    if held is None:
        held = {}
    if provider not in held:
        found = IMG.initialize_local_combined_providers_dict(
            tile, only=[provider]) or {}
        held[provider] = found.get(provider) or []
        tile._o4_combined_layers = held
    return {provider: held[provider]} if held[provider] else {}


def _land_combined(tile, attrs, final: str, width: int) -> None:
    """A combined provider's square: composited at full size and
    converted under the module's dict with the tile's own layers (the
    provider added for the landing and taken out after, unless a build
    put it there), the ``width`` tier cut from it and landed at
    ``final``."""
    import O4_Imagery_Utils as IMG
    provider = attrs[3]
    with _COMBINED:
        layers = _combined_layers(tile, provider)
        if not layers:
            raise RuntimeError(f"{provider} has no imagery on this tile")
        table = IMG.local_combined_providers_dict
        added = provider not in table
        if added:
            table.update(layers)
        try:
            if not IMG.build_jpeg_ortho(tile, *attrs):
                raise RuntimeError(f"the {provider} imagery did not download")
            IMG.convert_texture(tile, *attrs, drop=0)
        finally:
            if added and table.get(provider) is layers[provider]:
                table.pop(provider, None)
    built = os.path.join(tile.build_dir, "textures",
                         os.path.basename(final))
    if width == TIERS.FULL_WIDTH:
        _mirror(built, final)
    elif not _land_from_source(built, final, width):
        raise RuntimeError(f"{os.path.basename(final)}: no {width} px tier")


def _frozen_colour_field(tile) -> None:
    """The colour field the tile's build froze (``color_field.json``,
    ``O4_Imagery_Utils.read_color_field``) on the tile object, so a tier
    fetched from the provider is shifted as the build's textures were;
    none when the tile does not harmonize or kept no field."""
    if not getattr(tile, "color_harmonization", False):
        return
    import O4_Imagery_Utils as IMG
    fields, land, _record = IMG.read_color_field(tile)
    if fields:
        tile.color_harmonization_fields = fields
        tile.color_harmonization_land = land


def _mirror(built: str, final: str) -> None:
    """The texture the converter wrote in the build folder, put over
    ``final`` when the row's textures live elsewhere (a World-pack tile,
    spec §7.3): hard-linked (copied across volumes) beside it and renamed
    over it in one step."""
    if os.path.abspath(built) == os.path.abspath(final):
        return
    partial = final + ".landing"
    with contextlib.suppress(OSError):
        os.remove(partial)
    try:
        os.link(built, partial)
    except OSError:
        shutil.copy2(built, partial)
    os.replace(partial, final)


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
