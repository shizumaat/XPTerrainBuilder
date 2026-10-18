"""Does this interpreter fetch (and convert) orthophoto textures? (``--imagery-fetch-selfcheck``)

The frozen binary's smoke test for the imagery fetchers (imagery-fetch-spec §5): the
async HTTP/2 path (``O4_IMAGERY_FETCHER=async``) rides on ``curl_cffi``, imported
lazily, so a bundle without it is no error until a user picks it. This downloads ONE
texture through the full ``download_jpeg_ortho`` chain with whichever fetcher the
environment selects and prints one line: the fetcher, the wall time, whether every part
arrived, and the sha256 of the saved JPEG (equal across fetchers for the same texture).

    Ortho4XP --imagery-fetch-selfcheck PROVIDER ZOOMLEVEL LAT LON OUTDIR
             [--convert N [--imagery-dir DIR]]

``--convert N`` then converts N textures to DDS CONCURRENTLY through the production
convert path — ``IMG.convert_texture`` run by the tile build's own convert workers
(``parallel_launch``, N of them) with the encoder ``O4_DDS_ENCODER`` selects — the
frozen bundle's proof that the encoder works there (#900: its process pool crashed only
frozen). The N textures are the block of ceil(sqrt(N)) columns starting at the one
holding LAT, LON; each JPEG is copied from ``--imagery-dir`` (an Orthophotos folder,
read only) when it is there, else downloaded. Everything is written under OUTDIR.

Exit 0 when the texture was saved with every part (and, with ``--convert``, every DDS
landed whole), 1 otherwise. Needs the network unless every JPEG is cached.
"""

from __future__ import annotations

import hashlib
import math
import os
import queue
import shutil
import time
import types

__all__ = ["main"]

USAGE = ("usage: --imagery-fetch-selfcheck PROVIDER ZOOMLEVEL LAT LON OUTDIR"
         " [--convert N [--imagery-dir DIR]]")


def _option(argv: list[str], name: str, default=None):
    """The value after ``name`` in ``argv``, else ``default``."""
    if name not in argv:
        return default
    return argv[argv.index(name) + 1]


def main(argv: list[str]) -> int:
    """Run the selfcheck on ``argv`` (the process's); returns the exit code."""
    import O4_Geo_Utils as GEO
    import O4_Imagery_Async as FETCH_ASYNC
    import O4_Imagery_Utils as IMG

    try:
        at = argv.index("--imagery-fetch-selfcheck")
        provider_code, zoom, lat, lon, outdir = argv[at + 1 : at + 6]
        zoom, lat, lon = int(zoom), float(lat), float(lon)
        convert = int(_option(argv, "--convert", 0))
        imagery_dir = _option(argv, "--imagery-dir", "")
    except (ValueError, IndexError):
        print(USAGE)
        return 2
    IMG.initialize_providers_dict()
    if provider_code not in IMG.providers_dict:
        print("imagery fetch selfcheck: unknown provider %r" % provider_code)
        return 2
    til_x, til_y = GEO.wgs84_to_orthogrid(lat, lon, zoom)
    texture_dir = os.path.join(outdir, "selfcheck", "textures")
    name = "%d_%d_%s%d.jpg" % (til_y, til_x, provider_code, zoom)
    t0 = time.monotonic()
    IMG.download_jpeg_ortho(texture_dir, name, til_x, til_y, zoom, provider_code)
    wall = time.monotonic() - t0
    path = os.path.join(texture_dir, name)
    complete = os.path.isfile(path) and not IMG.incomplete_imgs.get("selfcheck")
    digest = ""
    if os.path.isfile(path):
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    print(
        "imagery fetch selfcheck: fetcher=%s wall=%.2fs complete=%s sha256=%s"
        % (FETCH_ASYNC.fetcher_choice(), wall, complete, digest or "-")
    )
    if convert > 0:
        tile = _convert_tile(outdir, lat, lon)
        textures = _texture_block(til_x, til_y, convert)
        whole = _convert_textures(tile, textures, zoom, provider_code, imagery_dir)
        complete = complete and whole == len(textures)
    return 0 if complete else 1


def _convert_tile(outdir: str, lat: float, lon: float):
    """The stand-in tile ``convert_texture`` reads: its own build folder under OUTDIR,
    no masks, no colour harmonization; the imagery and temp folders point under OUTDIR."""
    import O4_File_Names as FNAMES

    FNAMES.Imagery_dir = os.path.join(outdir, "selfcheck", "Orthophotos")
    FNAMES.Tmp_dir = os.path.join(outdir, "selfcheck", "tmp")
    tile = types.SimpleNamespace(
        lat=math.floor(lat), lon=math.floor(lon), imprint_masks_to_dds=False,
        build_dir=os.path.join(outdir, "selfcheck", "build"))
    os.makedirs(os.path.join(tile.build_dir, "textures"), exist_ok=True)
    return tile


def _texture_block(til_x: int, til_y: int, count: int) -> list:
    """``count`` texture corners, row by row, ceil(sqrt(count)) to a row."""
    side = math.ceil(math.sqrt(count))
    return [(til_x + 16 * (i % side), til_y + 16 * (i // side)) for i in range(count)]


def _stage_jpeg(tile, til_x, til_y, zoom, provider_code, imagery_dir) -> None:
    """Put one texture's JPEG where ``convert_texture`` reads it: a copy from the
    read-only ``imagery_dir`` when cached there, else a download."""
    import O4_File_Names as FNAMES
    import O4_Imagery_Utils as IMG

    name = FNAMES.jpeg_file_name_from_attributes(til_x, til_y, zoom, provider_code)
    target_dir = FNAMES.jpeg_file_dir_from_attributes(
        tile.lat, tile.lon, zoom, IMG.providers_dict[provider_code])
    os.makedirs(target_dir, exist_ok=True)
    if imagery_dir:
        cached = os.path.join(imagery_dir,
                              os.path.relpath(target_dir, FNAMES.Imagery_dir), name)
        if os.path.isfile(cached):
            shutil.copyfile(cached, os.path.join(target_dir, name))
            return
    IMG.download_jpeg_ortho(target_dir, name, til_x, til_y, zoom, provider_code)


def _convert_textures(tile, textures, zoom, provider_code, imagery_dir="") -> int:
    """Convert ``textures`` (corner pairs) concurrently through the tile build's convert
    workers, one per texture; print one line and return how many landed whole."""
    import O4_DDS_Encode as DDSENC
    import O4_DDS_File as DDS
    import O4_File_Names as FNAMES
    import O4_Imagery_Utils as IMG
    from O4_Parallel_Utils import parallel_join, parallel_launch

    for til_x, til_y in textures:
        _stage_jpeg(tile, til_x, til_y, zoom, provider_code, imagery_dir)
    jobs = queue.Queue()
    for til_x, til_y in textures:
        jobs.put((tile, til_x, til_y, zoom, provider_code))
    t0 = time.monotonic()
    workers = parallel_launch(IMG.convert_texture, jobs, len(textures))
    for _ in workers:
        jobs.put("quit")
    parallel_join(workers)
    wall = time.monotonic() - t0
    whole = sum(
        DDS.is_whole(os.path.join(tile.build_dir, "textures",
                                  FNAMES.dds_file_name_from_attributes(
                                      til_x, til_y, zoom, provider_code)))
        for til_x, til_y in textures)
    print("imagery convert selfcheck: encoder=%s textures=%d whole=%d failed=%d wall=%.2fs"
          % (DDSENC.chosen_encoder(), len(textures), whole, len(textures) - whole, wall))
    return whole
