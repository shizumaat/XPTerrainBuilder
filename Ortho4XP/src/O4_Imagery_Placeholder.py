"""Placeholder build mode: every texture of a tile built from imagery a
few zoom levels coarser, under the full texture's own name (#1992,
local-imagery-cache spec §3, phase P1a).

With ``imagery_on_demand`` on, the scenery-file step names and queues its
textures as a full build does, and the DSF, the ``.ter`` files and the
masks are the full build's byte for byte (none of them reads a pixel).
Only the imagery changes: each 16 x 16-tile square at zoom ``zl`` is
fetched at ``zl - drop`` (``placeholder_zl_drop``, default 3: a 2 x 2-tile
box, 4 map requests instead of 256) and converted, colour field and masks
included, into a whole ``4096 >> drop`` px DDS (512 px by default).
X-Plane reads the header of the file it opens, so the smaller file loads
under a ``.ter`` that declares 4096 (spec §2.3); later phases land finer
tiers over it near the aircraft.

* :func:`drop` — the zoom levels a tile's textures are fetched below its
  own; 0 for a normal build.
* :func:`tilbox`, :func:`jpeg_name`, :func:`jpeg_dir` — what a
  placeholder's imagery is: the same square at the coarser zoom, cached
  under that zoom's folder with a name of its own (a ``<prov>_<zl-drop>``
  texture of a build AT that zoom covers 16 x 16 tiles, a placeholder
  2 x 2, so the two never share a name).
* :func:`needs_build` — the scenery-file step's "is the texture on disk
  current" test: whole, and at least as fine as the mode asks.
* :func:`keep` — the placeholder store (spec §6.2): one copy of each
  placeholder under ``<data>/Imagery_on_demand/placeholders/<tile>/``, a
  hard link to the tile's texture, so a later downgrade needs no network.
  A placeholder never goes into the content-keyed ``DDS_cache``.
"""
from __future__ import annotations

import contextlib
import os
import uuid

import O4_DDS_Cache as DDSCACHE
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_File_Names as FNAMES

__all__ = ["ALLOWED_DROPS", "DEFAULT_DROP", "STORE_DIR", "drop",
           "jpeg_dir", "jpeg_name", "keep", "needs_build", "tilbox"]

#: ``placeholder_zl_drop`` default: ZL13 imagery for a ZL16 texture, 512 px
#: (owner 2026-11-10: "512 as default makes sense").
DEFAULT_DROP = 3
#: The drops a placeholder may be: 4 (256 px) is refused, X-Plane
#: out-resolves it inside ~10 S (spec §2.5); 2 is 1024 px.
ALLOWED_DROPS = (2, 3)
#: Under the data root: the on-demand imagery's own folder.
STORE_DIR = "Imagery_on_demand"
#: Map tiles per side of one texture at its own zoom.
_TILES_PER_TEXTURE = 16


def drop(tile) -> int:
    """Zoom levels below its own each texture of ``tile`` is fetched at:
    0 for a normal build, else the tile's ``placeholder_zl_drop`` (an
    unknown value reads as the default)."""
    if not getattr(tile, "imagery_on_demand", False):
        return 0
    if getattr(tile, "texture_mode", "full_ortho") == "default_xplane":
        return 0
    try:
        value = int(getattr(tile, "placeholder_zl_drop", DEFAULT_DROP))
    except (TypeError, ValueError):
        return DEFAULT_DROP
    return value if value in ALLOWED_DROPS else DEFAULT_DROP


def tilbox(til_x_left, til_y_top, drop_levels):
    """``[x0, y0, x1, y1]`` map tiles at ``zl - drop_levels`` that cover the
    texture whose top-left tile is ``(til_x_left, til_y_top)`` at ``zl``."""
    step = 2 ** drop_levels
    if til_x_left % step or til_y_top % step:
        raise ValueError("a texture's corner is not on the coarser grid")
    side = _TILES_PER_TEXTURE // step
    x0, y0 = til_x_left // step, til_y_top // step
    return [x0, y0, x0 + side, y0 + side]


def jpeg_name(til_x_left, til_y_top, zoomlevel, provider_code, drop_levels):
    """The placeholder JPEG's file name: the full texture's, marked with
    the zoom it was fetched at."""
    full = FNAMES.jpeg_file_name_from_attributes(
        til_x_left, til_y_top, zoomlevel, provider_code)
    return "%s_low%d.jpg" % (full[:-4],
                             TIERS.tier_zoom(zoomlevel, drop_levels))


def jpeg_dir(lat, lon, zoomlevel, provider, drop_levels):
    """The imagery cache folder of the zoom a placeholder is fetched at."""
    return FNAMES.jpeg_file_dir_from_attributes(
        lat, lon, TIERS.tier_zoom(zoomlevel, drop_levels), provider)


def needs_build(tile, path) -> bool:
    """Must the texture at ``path`` be (re)built?  When it is not a whole
    DDS, or is a tier coarser than the mode asks: an on-demand build keeps
    any texture at least its placeholder width (a finer tier already
    landed stays), a normal build rebuilds every on-demand tier below the
    full width (512, 1024, 2048 px).  A texture of any other size is
    nobody's tier and is judged whole, as before this mode existed."""
    if not DDS.is_whole(path):
        return True
    header = TIERS.texture_header(path)
    if header is None:
        return False
    wanted = TIERS.tier_width(drop(tile))
    lower_tiers = {TIERS.tier_width(d) for d in TIERS.TIER_DROPS
                   if TIERS.tier_width(d) < wanted}
    return header[0] in lower_tiers


def _store_path(tile, dds_name) -> str:
    """Where the placeholder store keeps ``tile``'s texture ``dds_name``."""
    return os.path.join(FNAMES.data_path(STORE_DIR), "placeholders",
                        FNAMES.short_latlon(tile.lat, tile.lon), dds_name)


def keep(tile, dds_final) -> bool:
    """Put the placeholder just landed at ``dds_final`` in the store (a
    hard link where the volume allows, else a copy); ``True`` when the
    store holds it whole.  Never raises: a store that cannot be written
    only means a later downgrade fetches the placeholder again."""
    if not DDS.is_whole(dds_final):
        return False
    entry = _store_path(tile, os.path.basename(dds_final))
    temp = f"{entry}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    try:
        os.makedirs(os.path.dirname(entry), exist_ok=True)
        if not DDSCACHE.link_or_copy(dds_final, temp):
            return False
        os.replace(temp, entry)
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(temp)
        return False
    return True
