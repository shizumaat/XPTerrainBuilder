"""The imagery of a draped World-pack tile (``O4_World_Drape``): every
texture square of the tile fetched and converted to DDS by the engine's
own step-3 machinery, at the placeholder tier, with no mesh.

A tile build learns its textures from the mesh (``build_dsf`` walks the
triangles); a drape has no mesh, so the square list is the tile's whole
grid (``O4_World_Drape.texture_squares``) and is fed straight into
``O4_Tile_Utils.download_textures`` (threads, retries, the provider's
request budget) and then ``O4_Imagery_Utils.convert_texture`` workers.
With ``imagery_on_demand`` and ``placeholder_zl_drop`` 3 each ZL16
square is a 2 x 2 ZL13 fetch converted to a 512 px DDS
(``O4_Imagery_Placeholder``).

Run as a process (it sets up the engine's module globals, which a
long-lived caller should not inherit)::

    cd ENGINE && ORTHO4XP_DATA_ROOT=ROOT venv/bin/python \\
        .../O4_World_Drape_Fetch.py LAT LON BUILD_PARENT/ [--zl 16] \\
        [--provider BI] [--drop 3] [--water-alpha]

With ``--water-alpha`` every square that touches the tile's OSM water
gets the regular build's inland water mask in its DDS alpha (DXT5,
``O4_World_Drape_Water``) for the drape's water layer.

The DDS land in ``BUILD_PARENT/zOrtho4XP_<tile>/textures/``.  The last
stdout line is a JSON record: squares, downloaded, failed, dds, and the
download and convert seconds.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import time

__all__ = ["fetch", "main"]


def _engine_imports(engine: str):
    src = os.path.join(engine, "src")
    if src not in sys.path:
        sys.path.insert(1, src)
    import O4_File_Names as FNAMES
    if FNAMES.Provider_dir not in sys.path:
        sys.path.append(FNAMES.Provider_dir)
    import O4_Config_Utils as CFG
    import O4_Imagery_Progress as IMGPROGRESS
    import O4_Imagery_Utils as IMG
    import O4_Parallel_Utils as PAR
    import O4_Tile_Utils as TILE
    return FNAMES, CFG, IMG, IMGPROGRESS, PAR, TILE


def fetch(engine: str, lat: int, lon: int, build_parent: str, zl: int,
          provider: str, drop: int, convert_workers: int = 4,
          water_alpha: bool = False) -> dict:
    """Fetch and convert every texture square of tile (lat, lon); returns
    the record :func:`main` prints."""
    FNAMES, CFG, IMG, IMGPROGRESS, PAR, TILE = _engine_imports(engine)
    import O4_World_Drape as DRAPE
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
    tile.color_harmonization = False
    os.makedirs(os.path.join(tile.build_dir, "textures"), exist_ok=True)
    squares = [sq for sq in DRAPE.texture_squares(lat, lon, zl)
               if DRAPE.drape_quad(lat, lon, *sq, zl) is not None]
    downloads, converts = queue.Queue(), queue.Queue()
    for til_x, til_y in squares:
        downloads.put((til_x, til_y, zl, provider))
    IMGPROGRESS.begin(tile)
    stats: dict = {}
    t0 = time.time()
    TILE.download_textures(tile, downloads, converts, stats=stats)
    t1 = time.time()
    water = {}
    if water_alpha:
        import O4_World_Drape_Water as WATER
        water = WATER.write_masks(tile, squares, zl, provider, 4096 >> drop)
        tile.imprint_masks_to_dds = True
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
    p.add_argument("--drop", type=int, default=3)
    p.add_argument("--engine", default=os.getcwd())
    p.add_argument("--convert-workers", type=int, default=4)
    p.add_argument("--water-alpha", action="store_true")
    a = p.parse_args(argv)
    rec = fetch(os.path.abspath(a.engine), a.lat, a.lon,
                os.path.abspath(a.build_parent), a.zl, a.provider, a.drop,
                a.convert_workers, a.water_alpha)
    print(json.dumps(rec), flush=True)
    return 0 if rec["dds"] == rec["squares"] else 1


if __name__ == "__main__":
    sys.exit(main())
