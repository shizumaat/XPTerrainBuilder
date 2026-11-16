"""A build's photos, small, for the cliff overlay's shadow read (#2102).

``O4_Cliff_Shade`` needs the luminance of the photo under and around each
cliff region while the DSF is built, before the photos are converted.  This
module gives one photo's pixels at a small size, from the first source on
disk:

1. the build's converted texture (``textures/<name>.dds``): one mip of
   about ``SAMPLE_PX``, read alone (``O4_DDS_File.read_level``);
2. the orthophoto JPEG the converter reads, decoded at 1/8 scale
   (``Image.draft``);
3. when the build downloads imagery, that JPEG fetched now through the
   imagery step's own locked download (``O4_Imagery_Utils
   .build_jpeg_ortho``): the step finds it present and does not fetch it
   twice.  With ``skip_downloads`` nothing is fetched.

None when no source gives it: the photo is not sampled.
"""
from __future__ import annotations

import os
import sys

import numpy
import O4_DDS_File as DDS
import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO

__all__ = ["SAMPLE_PX", "photo_lookup", "photo_reader"]

#: The size (pixels) photos are read at: 9.5 m a pixel at ZL16.
SAMPLE_PX = 256


def photo_lookup(dico_customzl, mesh_zl):
    """``photo_at(lonlat (k, 2))``: each point's photo attributes, as the
    DSF's triangles take them (None off the dictionary)."""
    def photo_at(lonlat):
        return [dico_customzl.get(GEO.wgs84_to_orthogrid(lat, lon, mesh_zl))
                for lon, lat in lonlat]
    return photo_at


def _from_dds(path):
    from O4_DDS_Decode import decode_blocks
    width, height, fmt, blocks = DDS.read_level(path, SAMPLE_PX)
    return decode_blocks(blocks, width, height, fmt)[..., :3]


def _from_jpeg(path):
    from PIL import Image
    with Image.open(path) as im:
        im.draft("RGB", (SAMPLE_PX, SAMPLE_PX))
        return numpy.asarray(im.convert("RGB").resize((SAMPLE_PX,
                                                        SAMPLE_PX)))


def _jpeg_path(tile, attrs):
    import O4_Imagery_Utils as IMG
    try:
        folder, name = IMG._source_jpeg_location(tile, *attrs)
    except (KeyError, TypeError):       # a combined or unknown provider
        return None
    return os.path.join(folder, name)


def _downloads_on():
    """True when the running tile build downloads imagery."""
    tile_utils = sys.modules.get("O4_Tile_Utils")
    return tile_utils is not None and not getattr(tile_utils,
                                                  "skip_downloads", True)


def photo_reader(tile, fetch=None):
    """``read_photo(attrs)``: the photo's (s, s, 3) pixels or None.
    ``fetch`` (default: the build downloads imagery) allows source 3."""
    fetch = _downloads_on() if fetch is None else fetch

    def read_photo(attrs):
        dds = os.path.join(tile.build_dir, "textures",
                           FNAMES.dds_file_name_from_attributes(*attrs))
        try:
            if DDS.is_whole(dds):
                return _from_dds(dds)
        except (OSError, ValueError):
            pass
        jpeg = _jpeg_path(tile, attrs)
        if jpeg is None:
            return None
        if not os.path.isfile(jpeg) and fetch:
            import O4_Imagery_Utils as IMG
            try:
                IMG.build_jpeg_ortho(tile, *attrs)
            except Exception:       # the imagery step retries and reports
                return None
        try:
            return _from_jpeg(jpeg)
        except OSError:
            return None
    return read_photo
