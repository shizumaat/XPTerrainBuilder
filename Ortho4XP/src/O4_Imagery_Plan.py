"""The orthophotos a tile will use, named before its mesh exists (#2254).

``O4_DSF_Utils`` picks a texture for a mesh triangle from the block under
its centre (``zone_list_to_ortho_dico``).  A triangle draws its texture
unless it is masked water with nothing to show: open sea, or a lake large
enough to be masked like the sea (``O4_Vector_Map.cached_masked_water``).
So before any triangle exists the texture set is the assignment over every
block that is not wholly under that water.

Measured against real meshes the rule names no texture the build lacks on
land; what it can over-count is the sliver of a block a mesh happens to
leave empty.  The imagery step reports the true count (:func:`unused`).

Read-only and download-free: it works on a private copy of the tile, so
nothing it reads is memoised for the build to find.
"""
from __future__ import annotations

import copy
import os
from collections import defaultdict

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
from shapely.geometry import box
from shapely.prepared import prep

__all__ = ["predicted_textures", "unused"]

_COVERS_AIRPORTS = ("True", "ICAO")


def _water_is_on_disk(tile) -> bool:
    """Have this tile's coastline and water layers landed?"""
    return all(
        os.path.exists(custom) or os.path.isdir(custom_dir)
        or os.path.isfile(FNAMES.osm_cached(tile.lat, tile.lon, suffix))
        for suffix, custom, custom_dir in (
            ("coastline", FNAMES.custom_coastline(tile.lat, tile.lon),
             FNAMES.custom_coastline_dir(tile.lat, tile.lon)),
            ("water", FNAMES.custom_water(tile.lat, tile.lon),
             FNAMES.custom_water_dir(tile.lat, tile.lon))))


def _inputs_ready(tile) -> bool:
    """Everything the assignment and the water read is on disk."""
    if (getattr(tile, "cover_airports_with_highres", "False")
            in _COVERS_AIRPORTS and not os.path.isfile(FNAMES.apt_file(tile))):
        return False
    return _water_is_on_disk(tile)


def _block_cell(til_x, til_y, zoom, lat, lon):
    """One mesh block, clipped to the tile, tile-relative; None if empty."""
    (north, west) = GEO.gtile_to_wgs84(til_x, til_y, zoom)
    (south, east) = GEO.gtile_to_wgs84(til_x + 16, til_y + 16, zoom)
    (x0, x1) = (max(west, lon) - lon, min(east, lon + 1) - lon)
    (y0, y1) = (max(south, lat) - lat, min(north, lat + 1) - lat)
    return box(x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _blocks_by_texture(ortho_dico, is_plain) -> dict:
    """``{texture: [mesh block, ...]}`` of the plain-source textures."""
    blocks = defaultdict(list)
    for block, texture in ortho_dico.items():
        if is_plain(texture[3]):
            blocks[tuple(texture)].append(block)
    return blocks


def _shows_ground(blocks, mesh_zl, tile, covered) -> bool:
    """Does any of a texture's blocks hold something the water leaves?"""
    for (til_x, til_y) in blocks:
        cell = _block_cell(til_x, til_y, mesh_zl, tile.lat, tile.lon)
        if cell is not None and not covered(cell):
            return True
    return False


def predicted_textures(tile, imagery=None, ortho_dico=None, masked_water=None):
    """The textures this build's imagery step will use, highest zoom first;
    ``None`` while the inputs are not on disk yet, ``[]`` in a mode that
    textures no whole tile.  A twin passes ``imagery``, ``ortho_dico`` and
    ``masked_water`` (tile-relative; empty for a dry tile)."""
    if getattr(tile, "texture_mode", "full_ortho") != "full_ortho":
        return []
    if ortho_dico is None or masked_water is None:
        if not _inputs_ready(tile):
            return None
        private = copy.copy(tile)      # the readers below memoise on a tile
        if masked_water is None:
            import O4_Vector_Map as VMAP
            masked_water = VMAP.cached_masked_water(private)
            if masked_water is None:
                return None
        if ortho_dico is None:
            import O4_DSF_Utils as DSF
            ortho_dico = DSF.zone_list_to_ortho_dico(private)
    if imagery is None:
        import O4_Imagery_Utils as imagery

    def is_plain(code):
        return (code in imagery.providers_dict
                and code not in imagery.combined_providers_dict
                and code not in imagery.local_combined_providers_dict)

    covered = (prep(masked_water).contains if not masked_water.is_empty
               else (lambda _cell: False))
    mesh_zl = int(tile.mesh_zl)
    found = [texture for texture, blocks
             in _blocks_by_texture(ortho_dico, is_plain).items()
             if _shows_ground(blocks, mesh_zl, tile, covered)]
    return sorted(found, key=lambda t: (-t[2], t[1], t[0], t[3]))


def unused(fetched, used) -> list:
    """The textures fetched ahead that the imagery step never asked for."""
    return sorted(set(fetched) - set(used))
