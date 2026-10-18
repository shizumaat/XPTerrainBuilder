"""Does this interpreter fetch one orthophoto texture? (``--imagery-fetch-selfcheck``)

The frozen binary's smoke test for the imagery fetchers (imagery-fetch-spec §5): the
async HTTP/2 path (``O4_IMAGERY_FETCHER=async``) rides on ``curl_cffi``, imported
lazily, so a bundle without it is no error until a user picks it. This downloads ONE
texture through the full ``download_jpeg_ortho`` chain with whichever fetcher the
environment selects and prints one line: the fetcher, the wall time, whether every part
arrived, and the sha256 of the saved JPEG (equal across fetchers for the same texture).

    Ortho4XP --imagery-fetch-selfcheck PROVIDER ZOOMLEVEL LAT LON OUTDIR

Exit 0 when the texture was saved with every part, 1 otherwise. Needs the network.
"""

from __future__ import annotations

import hashlib
import os
import time

__all__ = ["main"]


def main(argv: list[str]) -> int:
    """Run the selfcheck on ``argv`` (the process's); returns the exit code."""
    import O4_Geo_Utils as GEO
    import O4_Imagery_Async as FETCH_ASYNC
    import O4_Imagery_Utils as IMG

    try:
        at = argv.index("--imagery-fetch-selfcheck")
        provider_code, zoom, lat, lon, outdir = argv[at + 1 : at + 6]
        zoom, lat, lon = int(zoom), float(lat), float(lon)
    except ValueError:
        print("usage: --imagery-fetch-selfcheck PROVIDER ZOOMLEVEL LAT LON OUTDIR")
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
    return 0 if complete else 1
