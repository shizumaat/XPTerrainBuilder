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
* :func:`min_source_zl`, :func:`fetch_zoom` — a provider's coarsest
  zoom serving the same capture as its full zoom (``min_source_zl`` in
  its ``.lay``, #2017: Bing serves an older, greener capture at ZL12 and
  coarser) and the zoom a texture is therefore fetched at: never below
  that floor (``O4_Imagery_Utils.download_jpeg_ortho`` fetches the
  floor and shrinks), and the names say the zoom actually fetched.
* :func:`needs_build` — the scenery-file step's "is the texture on disk
  current" test: whole, and at least as fine as the mode asks.
* :func:`keep` — the placeholder store (spec §6.2): one copy of each
  placeholder under ``<data>/Imagery_on_demand/placeholders/<tile>/``, a
  hard link to the tile's texture, so a later downgrade needs no network.
  A placeholder never goes into the content-keyed ``DDS_cache``.
* :func:`land_kept` -- land a kept placeholder over a texture (a
  downgrade, spec §6.2: a new inode under the old name, never a delete);
  :func:`kept_path` / :func:`forget` -- the store's copy of one texture,
  and dropping it so the next build makes the placeholder again ("Update
  Imagery" on an on-demand tile).
"""
from __future__ import annotations

import contextlib
import os
import uuid

import O4_DDS_Cache as DDSCACHE
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_File_Names as FNAMES
import O4_Imagery_Regions as REGIONS

__all__ = ["ALLOWED_DROPS", "DEFAULT_DROP", "MIN_SOURCE_KEY", "STORE_DIR",
           "drop", "fetch_zoom", "forget", "jpeg_dir", "jpeg_name", "keep",
           "kept_path", "land_kept", "min_source_zl", "needs_build", "tilbox"]

#: ``placeholder_zl_drop`` default: ZL13 imagery for a ZL16 texture, 512 px
#: (owner 2026-11-10: "512 as default makes sense").
DEFAULT_DROP = 3
#: The drops a placeholder may be: 4 (256 px) is refused, X-Plane
#: out-resolves it inside ~10 S (spec §2.5); 2 is 1024 px.
ALLOWED_DROPS = (2, 3)
#: Under the data root: the on-demand imagery's own folder.
STORE_DIR = "Imagery_on_demand"
#: The ``.lay`` key of a provider's coarsest trustworthy source zoom.
MIN_SOURCE_KEY = "min_source_zl"
#: Map tiles per side of one texture at its own zoom.
_TILES_PER_TEXTURE = 16


def drop(tile) -> int:
    """Zoom levels below its own each texture of ``tile`` is fetched at:
    0 for a normal build or a tile outside the regions on demand is on
    for (RULINGS 2026-11-10e (3)), else the tile's ``placeholder_zl_drop``
    (an unknown value reads as the default)."""
    if not getattr(tile, "imagery_on_demand", False):
        return 0
    if not REGIONS.tile_on_demand(tile):
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


def min_source_zl(provider):
    """The coarsest zoom ``provider`` (its ``.lay`` dict) serves the same
    capture at as at full zoom, or None (no floor measured)."""
    value = (provider or {}).get(MIN_SOURCE_KEY)
    try:
        return None if value in (None, "") else int(value)
    except (TypeError, ValueError):
        return None


def fetch_zoom(zoomlevel, drop_levels, provider):
    """The zoom the imagery of a texture at ``zoomlevel``, ``drop_levels``
    coarser, comes from: ``zoomlevel - drop_levels``, raised to the
    provider's floor (:func:`min_source_zl`) but never past ``zoomlevel``."""
    zoom = int(zoomlevel) - int(drop_levels)
    floor = min_source_zl(provider)
    if floor is not None and zoom < floor:
        zoom = min(floor, int(zoomlevel))
    return zoom


def jpeg_name(til_x_left, til_y_top, zoomlevel, provider_code, drop_levels,
              provider):
    """The placeholder JPEG's file name: the full texture's, marked with
    the zoom it was fetched at (``provider``: its ``.lay`` dict, whose
    floor can raise that zoom, :func:`fetch_zoom`)."""
    full = FNAMES.jpeg_file_name_from_attributes(
        til_x_left, til_y_top, zoomlevel, provider_code)
    TIERS.tier_width(drop_levels)
    return "%s_low%d.jpg" % (full[:-4],
                             fetch_zoom(zoomlevel, drop_levels, provider))


def jpeg_dir(lat, lon, zoomlevel, provider, drop_levels):
    """The imagery cache folder of the zoom a placeholder is fetched at."""
    TIERS.tier_width(drop_levels)
    return FNAMES.jpeg_file_dir_from_attributes(
        lat, lon, fetch_zoom(zoomlevel, drop_levels, provider), provider)


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
    if (drop(tile) and header[0] == wanted
            and not os.path.isfile(kept_path(tile, os.path.basename(path)))):
        return True         # its kept copy was dropped (forget): make it anew
    lower_tiers = {TIERS.tier_width(d) for d in TIERS.TIER_DROPS
                   if TIERS.tier_width(d) < wanted}
    return header[0] in lower_tiers


def kept_path(tile, dds_name) -> str:
    """Where the placeholder store keeps ``tile``'s texture ``dds_name``
    (``tile``: anything with ``lat`` and ``lon``)."""
    return os.path.join(FNAMES.data_path(STORE_DIR), "placeholders",
                        FNAMES.short_latlon(tile.lat, tile.lon), dds_name)


def keep(tile, dds_final) -> bool:
    """Put the placeholder just landed at ``dds_final`` in the store (a
    hard link where the volume allows, else a copy); ``True`` when the
    store holds it whole.  Never raises: a store that cannot be written
    only means a later downgrade fetches the placeholder again."""
    if not DDS.is_whole(dds_final):
        return False
    entry = kept_path(tile, os.path.basename(dds_final))
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


def land_kept(kept: str, dds_final: str) -> bool:
    """Land the kept placeholder ``kept`` over ``dds_final``: hard-linked
    (or copied) beside it under a partial name, then renamed onto it
    (``O4_DDS_File.land``).  ``False`` -- ``dds_final`` untouched -- when
    the kept file is not whole or the landing was refused."""
    if not DDS.is_whole(kept):
        return False
    partial = DDS.partial_name(dds_final)
    if not DDSCACHE.link_or_copy(kept, partial):
        return False
    return DDS.land(partial, dds_final)


def forget(tile, dds_name) -> bool:
    """Drop the store's copy of ``tile``'s texture ``dds_name``; the next
    on-demand build makes that placeholder again (:func:`needs_build`).
    ``True`` when a copy was removed."""
    try:
        os.remove(kept_path(tile, dds_name))
    except OSError:
        return False
    return True
