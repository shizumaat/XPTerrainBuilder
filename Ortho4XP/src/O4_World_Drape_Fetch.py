"""The imagery of a draped World-pack tile (``O4_World_Drape``): every
texture square of the tile fetched and converted to DDS by the engine's
own step-3 machinery, at the drape's photo tier, with no mesh.

A tile build learns its textures from the mesh (``build_dsf`` walks the
triangles); a drape has no mesh, so the square list is the tile's whole
grid (``O4_World_Drape.texture_squares``) and is fed straight into
``O4_Tile_Utils.download_textures`` (threads, retries, the provider's
request budget) and then ``O4_Imagery_Utils.convert_texture`` workers.
The tier is the user's ``drape_photo_px`` (:data:`PX_DROPS`): 512 px
(each ZL16 square a 2 x 2 ZL13 fetch, the placeholder tier of
``O4_Imagery_Placeholder``), 1024 px (ZL14) or 4096 px (the square at
its own zoom, as a normal build fetches it).  The tile's on-demand
region setting is not consulted: a drape is always fetched at its tier.

Run as a process (it sets up the engine's module globals, which a
long-lived caller should not inherit)::

    cd ENGINE && ORTHO4XP_DATA_ROOT=ROOT venv/bin/python \\
        .../O4_World_Drape_Fetch.py LAT LON BUILD_PARENT/ [--zl 16] \\
        [--provider BI] [--px 512] [--water-alpha]

With ``--water-alpha`` every square that touches the tile's water gets
the regular build's shore mask in its DDS alpha (DXT5,
``O4_World_Drape_Water``) for the drape's water layer; the water layers
are fetched on a thread WHILE the photos download.

``near=(lat, lon, radius_s)`` (:func:`core_squares`) fetches only the
squares whose centre lies within ``radius_s`` square sizes of that point,
replacing their DDS: the airport core under a parked aircraft at full
resolution over a drape already fetched (RULINGS 2026-11-12c (3), #2019).

The DDS land in ``BUILD_PARENT/zOrtho4XP_<tile>/textures/``.  The last
stdout line is a JSON record: squares, downloaded, failed, dds, and the
download and convert seconds.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import queue
import sys
import threading
import time

__all__ = ["PX_DROPS", "core_squares", "drop_for_px", "fetch", "main"]

_INIT = threading.Lock()
#: The drape photo tiers (setting ``drape_photo_px``): width -> zoom
#: levels below the square's own (``O4_DDS_Tiers.tier_width``).
PX_DROPS = {512: 3, 1024: 2, 4096: 0}


def drop_for_px(px) -> int:
    """The drop of a ``drape_photo_px`` value (512 px for anything else)."""
    try:
        return PX_DROPS.get(int(px), PX_DROPS[512])
    except (TypeError, ValueError):
        return PX_DROPS[512]


def core_squares(squares, zl: int, lat: float, lon: float,
                 radius_s: float) -> list:
    """The ``(til_x, til_y)`` of ``squares`` whose centre lies within
    ``radius_s`` square sizes of ``(lat, lon)`` (a flat local frame: a
    core is a few squares across)."""
    import math

    import O4_World_Drape as DRAPE
    out = []
    for x, y in squares:
        south, west, north, east = DRAPE._bounds(x, y, zl)
        size = north - south
        dlat = (south + north) / 2.0 - lat
        dlon = ((west + east) / 2.0 - lon) * math.cos(math.radians(lat))
        if math.hypot(dlat, dlon) <= radius_s * size:
            out.append((x, y))
    return out


def _engine_imports(engine: str):
    src = os.path.join(engine, "src")
    if src not in sys.path:
        sys.path.insert(1, src)
    import O4_File_Names as FNAMES
    if FNAMES.Provider_dir not in sys.path:
        sys.path.append(FNAMES.Provider_dir)
    import O4_Config_Utils as CFG
    import O4_Imagery_Progress as IMGPROGRESS
    import O4_Imagery_Regions as REGIONS
    import O4_Imagery_Utils as IMG
    import O4_Parallel_Utils as PAR
    import O4_Tile_Utils as TILE
    return FNAMES, CFG, IMG, IMGPROGRESS, PAR, REGIONS, TILE


def fetch(engine: str, lat: int, lon: int, build_parent: str, zl: int,
          provider: str, drop: int, convert_workers: int = 4,
          water_alpha: bool = False, water_wait_s=None, near=None,
          blend=None) -> dict:
    """Fetch and convert every texture square of tile (lat, lon); returns
    the record :func:`main` prints.  ``water_wait_s``: the water copy is
    dropped (``water_late``) when the tile's water and masks are not done
    within that many seconds of the fetch's start
    (``O4_World_Drape_Water.start_masks``).  ``blend``: a zero-argument
    callable giving the tile's provider blend
    (``O4_Imagery_Provider_Blend.Blend`` or None, #2018), called once the
    provider registries are loaded; every square is converted with it."""
    FNAMES, CFG, IMG, IMGPROGRESS, PAR, REGIONS, TILE = _engine_imports(engine)
    import O4_World_Drape as DRAPE
    with _INIT:                 # once per process: the World job runs
        if not IMG.providers_dict:  # several fetches on threads
            IMG.initialize_extents_dict()
            IMG.initialize_color_filters_dict()
            IMG.initialize_providers_dict()
            IMG.initialize_combined_providers_dict()
    if provider not in IMG.providers_dict:
        raise SystemExit(f"unknown imagery provider {provider!r}")
    tile = CFG.Tile(lat, lon, os.path.join(build_parent, ""))
    tile.read_from_config()
    tile.default_website, tile.default_zl = provider, zl
    tile.imagery_on_demand, tile.placeholder_zl_drop = drop > 0, drop
    # the tier is the drape's own, whatever the region's on-demand switch
    setattr(tile, REGIONS.setting_name(REGIONS.region_of(lat, lon)), True)
    tile.color_harmonization = False
    tile.provider_blend = blend() if blend is not None else None
    os.makedirs(os.path.join(tile.build_dir, "textures"), exist_ok=True)
    squares = [sq for sq in DRAPE.texture_squares(lat, lon, zl)
               if DRAPE.drape_quad(lat, lon, *sq, zl) is not None]
    if near is not None:            # the core again, finer: its DDS replaced
        squares = core_squares(squares, zl, *near)
        for x, y in squares:
            name = FNAMES.dds_file_name_from_attributes(x, y, zl, provider)
            with contextlib.suppress(OSError):
                os.remove(os.path.join(tile.build_dir, "textures", name))
    downloads, converts = queue.Queue(), queue.Queue()
    for til_x, til_y in squares:
        downloads.put((til_x, til_y, zl, provider))
    IMGPROGRESS.begin(tile)
    stats: dict = {}
    water, masks = {}, None
    t0 = time.time()
    if water_alpha:                 # water read + masks overlap the download
        import O4_World_Drape_Water as WATER
        masks = WATER.start_masks(tile, squares, zl, provider, 4096 >> drop)
    TILE.download_textures(tile, downloads, converts, stats=stats)
    t1 = time.time()
    if masks is not None:
        left = (None if water_wait_s is None
                else max(0.0, float(water_wait_s) - (time.time() - t0)))
        water = masks(left) or {"water_late": True, "masked": 0}
        water.setdefault("water_late", False)
        water["masks_wait_s"] = round(time.time() - t1, 1)
        tile.imprint_masks_to_dds = not water["water_late"]
    t_conv = time.time()
    workers = PAR.parallel_launch(IMG.convert_texture, converts,
                                  convert_workers, progress={"done": 0, "bar": 3})
    for _ in workers:
        converts.put("quit")
    PAR.parallel_join(workers)
    t2 = time.time()
    tex = os.path.join(tile.build_dir, "textures")
    dds = sum(1 for x, y in squares if DRAPE.dds_width(os.path.join(
        tex, FNAMES.dds_file_name_from_attributes(x, y, zl, provider))))
    return {"tile": tile.build_dir, "textures": tex, "squares": len(squares),
            "downloaded": getattr(tile, "imagery_downloads", None),
            "done": stats.get("done"), "failed": stats.get("failed"),
            "dds": dds, "download_s": round(t1 - t0, 1),
            "convert_s": round(t2 - t_conv, 1), **water}


def main(argv=None) -> int:
    src = os.path.join(os.getcwd(), "src")      # run with cwd = the engine
    if src not in sys.path:
        sys.path.insert(1, src)
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("lat", type=int)
    p.add_argument("lon", type=int)
    p.add_argument("build_parent")
    p.add_argument("--zl", type=int, default=16)
    p.add_argument("--provider", default="BI")
    p.add_argument("--px", type=int, default=512, choices=sorted(PX_DROPS))
    p.add_argument("--engine", default=os.getcwd())
    p.add_argument("--convert-workers", type=int, default=4)
    p.add_argument("--water-alpha", action="store_true")
    a = p.parse_args(argv)
    rec = fetch(os.path.abspath(a.engine), a.lat, a.lon,
                os.path.abspath(a.build_parent), a.zl, a.provider,
                drop_for_px(a.px),
                a.convert_workers, a.water_alpha)
    print(json.dumps(rec), flush=True)
    return 0 if rec["dds"] == rec["squares"] else 1


if __name__ == "__main__":
    sys.exit(main())
