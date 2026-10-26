"""What a build will cost before it starts: download, disk and time (#820).

The ``plan_estimate`` command answers, for the tiles a front end is about
to build, three RANGES per tile — gigabytes to download, gigabytes the
build adds on disk, seconds of wall time — plus their totals and the free
space on the tile folder's volume.  Ranges, never single numbers: the
inputs are learned or counted, and a figure to the megabyte would be
false precision (issue #820 acceptance).

Inputs, all local (no network, so it answers in well under a second):

* the texture count at the build's zoom level — this tile's own history
  (``tile_time_model.estimate_texture_features``), else the zoom level's
  texture grid over the tile, widened downward because water and masks
  leave part of a tile without imagery, plus the user's drawn zones;
* the image cache — a texture already converted (``.dds`` in the tile's
  ``textures`` folder) or cached as an orthophoto (``_imagery_cache_
  directory``) is not downloaded again;
* bytes per texture measured from the files already in those folders,
  else the constants below;
* elevation and map data, counted only when the tile has none cached;
* the tile time model (``predict_step_seconds``, whose terrain step learns
  the airport grading and object fitting it carries) and the measured
  per-texture download time (#622), with the live throughput
  (``download_meter``) as a second opinion on the download share.

Never raises for one tile: a tile it cannot read is priced from the
constants.  The command runs on a worker thread and completes through
:class:`~o4_engine.events.PlanEstimateReady` (the ``pack_objects``
pattern), so the transport's read loop is never held.
"""

from __future__ import annotations

import math
import os
import shutil
import statistics
import threading

import O4_File_Names as FNAMES

__all__ = ["plan_estimate", "start_plan_estimate", "texture_grid_count",
           "disk_verdict"]

GB = 1024.0 ** 3
MB = 1024.0 ** 2

#: One orthophoto of one texture (4096 px square JPEG) in the image cache,
#: when no cached file of this source and zoom level can be measured.
JPEG_BYTES_PER_TEXTURE = (4.0 * MB, 9.0 * MB)
#: One converted texture: BC1 with mipmaps (~10.7 MB) up to BC3 for the
#: textures that carry a water mask (~21.3 MB).
DDS_BYTES_PER_TEXTURE = (10.7 * MB, 21.3 * MB)
#: Elevation and OpenStreetMap data for a tile that has none cached yet.
TERRAIN_DATA_BYTES = (0.05 * GB, 0.6 * GB)
#: The rest of a built tile: the scenery file, the mesh, its working files.
BUILD_FILES_BYTES = (0.1 * GB, 1.0 * GB)
#: A tile with no history of its own: share of the texture grid that ends
#: up with imagery (water outside the masks takes none).
UNKNOWN_COVERAGE_FLOOR = 0.5
#: The time model's point estimate, widened into a range: with this
#: tile's own history, and without it (cross-tile rates or constants).
TIME_SPREAD_KNOWN = (0.75, 1.5)
TIME_SPREAD_UNKNOWN = (0.5, 2.5)
#: Files sampled when a folder's per-texture size is measured.
_SIZE_SAMPLE = 32


def texture_grid_count(lat, lon, zoomlevel):
    """Textures of the zoom level's grid that touch the 1 degree tile.

    The grid is 16 web-mercator tiles square per texture
    (``O4_Geo_Utils.wgs84_to_orthogrid``); this counts the grid blocks
    between the tile's corners, edges included.
    """
    zoomlevel = int(zoomlevel)

    def orthogrid(la, lo):
        ratio_x = lo / 180.0
        la = max(min(la, 85.0), -85.0)
        ratio_y = math.log(math.tan((90.0 + la) * math.pi / 360.0)) / math.pi
        mult = 2 ** (zoomlevel - 5)
        return (int((ratio_x + 1) * mult), int((1 - ratio_y) * mult))

    (x0, y0) = orthogrid(lat + 1, lon)
    (x1, y1) = orthogrid(lat, min(lon + 1, 180) - 1e-9)
    return (abs(x1 - x0) + 1) * (abs(y1 - y0) + 1)


def _zone_textures(tile, base_zoomlevel):
    """Extra textures the user's drawn zones add above the base zoom:
    each zone's share of the tile times its own zoom level's grid."""
    extra = 0.0
    for zone in getattr(tile, "zone_list", None) or ():
        try:
            coords, zoomlevel = zone[0], int(zone[1])
            if zoomlevel <= base_zoomlevel or len(coords) < 6:
                continue
            points = list(zip(coords[0::2], coords[1::2], strict=False))
            area = 0.5 * abs(sum(
                a[1] * b[0] - b[1] * a[0]
                for a, b in zip(points, points[1:] + points[:1], strict=True)))
            share = min(max(area, 0.0), 1.0)
            extra += share * texture_grid_count(tile.lat, tile.lon, zoomlevel)
        except Exception:
            continue
    return extra


def _files_with_suffix(directory, suffix):
    """``(count, [sample sizes])`` of the files in ``directory`` ending in
    ``suffix``; ``(0, [])`` for a folder that is not there."""
    count, sizes = 0, []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if not entry.name.endswith(suffix):
                    continue
                count += 1
                if len(sizes) < _SIZE_SAMPLE:
                    try:
                        sizes.append(entry.stat().st_size)
                    except OSError:
                        pass
    except (OSError, TypeError):
        pass
    return count, sizes


def _bytes_per_texture(sizes, fallback):
    """A measured per-file size widened by a fifth each way, else the
    constant range."""
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        return fallback
    median = statistics.median(sizes)
    return (0.8 * median, 1.25 * median)


def _terrain_data_cached(lat, lon):
    """Has this tile elevation AND map data in the data folder already?"""
    def any_prefixed(directory, prefix):
        try:
            return any(name.startswith(prefix) for name in os.listdir(directory))
        except OSError:
            return False

    elevation = any_prefixed(
        os.path.dirname(FNAMES.base_file_name(lat, lon)),
        FNAMES.hem_latlon(lat, lon))
    osm = any_prefixed(FNAMES.osm_dir(lat, lon), FNAMES.short_latlon(lat, lon))
    return elevation and osm


def _volume_key(path):
    """The device of the nearest existing folder above ``path``."""
    probe = os.path.abspath(path or ".")
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return probe, os.stat(probe).st_dev
    except OSError:
        return probe, None


def _free_bytes(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _range(lo, hi):
    lo, hi = float(lo), float(hi)
    return [min(lo, hi), max(lo, hi)]


def _gb(pair):
    return [round(pair[0] / GB, 2), round(pair[1] / GB, 2)]


def _tile_settings(lat, lon, provider, zoomlevel, custom_build_dir):
    """The tile's config, and the provider / zoom level the build uses
    (``""`` / 0 mean the tile's own, as ``enqueue_build`` reads them)."""
    tile = None
    try:
        import O4_Config_Utils as CFG
        tile = CFG.Tile(lat, lon, custom_build_dir)
        tile.read_from_config()
    except Exception:
        tile = None
    provider = provider or str(getattr(tile, "default_website", "") or "")
    zoomlevel = int(zoomlevel or getattr(tile, "default_zl", 0) or 16)
    return tile, provider, zoomlevel


def tile_estimate(lat, lon, provider, zoomlevel, custom_build_dir,
                  do_vector=True, do_imagery=True, do_overlays=False):
    """One tile's ``{download_gb, disk_gb, cache_gb, time_s}`` ranges and
    the counts behind them (bytes internally, GB on the wire)."""
    from . import session as SESSION
    from . import tile_time_model as TTM

    tile, provider, zoomlevel = _tile_settings(
        lat, lon, provider, zoomlevel, custom_build_dir)
    build_dir = FNAMES.build_dir(lat, lon, custom_build_dir)
    features = SESSION.prediction_features(
        lat, lon, provider, zoomlevel, custom_build_dir)
    download = [0.0, 0.0]
    tile_disk = [0.0, 0.0]
    cache_disk = [0.0, 0.0]
    textures = {"count": [0, 0], "on_disk": 0, "cached": 0,
                "to_download": [0, 0]}

    if do_imagery and getattr(tile, "texture_mode", "") != "default_xplane":
        known = int(features.get("textures_total") or 0)
        if known:
            count = (known, known)
        else:
            grid = texture_grid_count(lat, lon, zoomlevel) \
                + _zone_textures(tile, zoomlevel)
            count = (UNKNOWN_COVERAGE_FLOOR * grid, grid)
        on_disk, dds_sizes = _files_with_suffix(
            os.path.join(build_dir, "textures"),
            "_%s%d.dds" % (provider, zoomlevel))
        cached, jpeg_sizes = _files_with_suffix(
            SESSION._imagery_cache_directory(lat, lon, zoomlevel, provider),
            "_%s%d.jpg" % (provider, zoomlevel))
        have = max(on_disk, cached)
        to_download = [max(c - have, 0.0) for c in count]
        to_convert = [max(c - on_disk, 0.0) for c in count]
        jpeg = _bytes_per_texture(jpeg_sizes, JPEG_BYTES_PER_TEXTURE)
        dds = _bytes_per_texture(dds_sizes, DDS_BYTES_PER_TEXTURE)
        download = [to_download[0] * jpeg[0], to_download[1] * jpeg[1]]
        cache_disk = list(download)
        tile_disk = [to_convert[0] * dds[0], to_convert[1] * dds[1]]
        textures = {"count": [int(round(c)) for c in count],
                    "on_disk": on_disk, "cached": cached,
                    "to_download": [int(round(c)) for c in to_download]}
        features["textures_total"] = int(round(count[1]))
        features["textures_missing"] = int(round(to_convert[1]))
        features["textures_to_download"] = int(round(to_download[1]))

    terrain_cached = True
    if do_vector:
        terrain_cached = _terrain_data_cached(lat, lon)
        if not terrain_cached:
            download = [d + t for d, t in zip(download, TERRAIN_DATA_BYTES, strict=True)]
            cache_disk = [d + t for d, t in zip(cache_disk, TERRAIN_DATA_BYTES, strict=True)]
    if do_vector or do_imagery:
        tile_disk = [d + b for d, b in zip(tile_disk, BUILD_FILES_BYTES, strict=True)]

    steps = [key for key, _base, _width in SESSION.plan_steps(
        do_vector, do_imagery, do_overlays)] if (
            do_vector or do_imagery or do_overlays) else []
    seconds = sum(SESSION._predict_step_seconds(
        lat, lon, features, steps).values()) if steps else 0.0
    has_history = bool(TTM._load_tile_records(lat, lon))
    spread = TIME_SPREAD_KNOWN if has_history else TIME_SPREAD_UNKNOWN
    time_s = [seconds * spread[0], seconds * spread[1]]
    rate = _throughput()
    if rate and download[1] > 0 and "imagery" in steps:
        # The live throughput's view of the download share: the range
        # stretches to hold it when it disagrees with the learned rate.
        learned = (TTM.imagery_components(lat, lon, features) or {}).get(
            "download", 0.0)
        other = max(seconds - float(learned), 0.0)
        time_s = [min(time_s[0], other + download[0] / rate),
                  max(time_s[1], other + download[1] / rate)]
    return {
        "lat": int(lat), "lon": int(lon),
        "provider": provider, "zoomlevel": zoomlevel,
        "download_bytes": _range(*download),
        "tile_bytes": _range(*tile_disk),
        "cache_bytes": _range(*cache_disk),
        "time_s": [int(round(t)) for t in _range(*time_s)],
        "textures": textures,
        "terrain_data_cached": terrain_cached,
        "has_history": has_history,
        "build_dir": build_dir,
    }


def _throughput():
    try:
        from . import download_meter
        return download_meter.throughput_bytes_per_second()
    except Exception:
        return None


def disk_verdict(need_bytes, free_bytes, where):
    """``("ok" | "warn" | "refuse", reason)`` for one volume: refuse when
    even the low end of the need exceeds the free space, warn when the
    high end does."""
    if free_bytes is None:
        return "ok", ""
    lo, hi = need_bytes
    if lo > free_bytes:
        return "refuse", (
            "This build needs at least %.1f GB on %s, which has %.1f GB free."
            " Free some space or choose another tile folder."
            % (lo / GB, where, free_bytes / GB))
    if hi > free_bytes:
        return "warn", (
            "This build may need up to %.1f GB on %s, which has %.1f GB free."
            % (hi / GB, where, free_bytes / GB))
    return "ok", ""


def plan_estimate(tiles, provider="", zoomlevel=0, custom_build_dir="",
                  do_vector=True, do_imagery=True, do_overlays=False):
    """The whole command's answer (see the module docstring)::

        {"tiles": [{"lat", "lon", "download_gb": [lo, hi],
                    "disk_gb": [lo, hi], "time_s": [lo, hi], ...}],
         "total": {"download_gb", "disk_gb", "time_s"},
         "free_gb": float | None, "cache_free_gb": float | None,
         "verdict": "ok" | "warn" | "refuse", "reason": str}

    ``disk_gb`` is what lands on the tile folder's volume — the tile's
    own files plus the image and data cache when that lives on the same
    volume; a cache on another volume is checked against its own free
    space (``cache_free_gb``).  ``time_s`` of the total is the sum, an
    upper bound for a parallel run.
    """
    from . import tile_time_model as TTM

    rows = []
    with TTM.batch_reads():
        for cell in tiles or ():
            (lat, lon) = (int(cell[0]), int(cell[1]))
            try:
                rows.append(tile_estimate(
                    lat, lon, provider, zoomlevel, custom_build_dir,
                    do_vector, do_imagery, do_overlays))
            except Exception:
                rows.append(_constant_estimate(lat, lon, do_vector, do_imagery))
    tile_root = (os.path.dirname(rows[0]["build_dir"]) if rows
                 else (custom_build_dir or FNAMES.Tile_dir))
    tile_probe, tile_device = _volume_key(tile_root)
    cache_probe, cache_device = _volume_key(
        FNAMES.Imagery_dir or FNAMES.data_path(""))
    same_volume = tile_device is not None and tile_device == cache_device
    total = {"download": [0.0, 0.0], "disk": [0.0, 0.0],
             "cache": [0.0, 0.0], "time": [0, 0]}
    wire_rows = []
    for row in rows:
        disk = [t + (c if same_volume else 0.0)
                for t, c in zip(row["tile_bytes"], row["cache_bytes"], strict=True)]
        for key, pair in (("download", row["download_bytes"]),
                          ("disk", disk), ("cache", row["cache_bytes"]),
                          ("time", row["time_s"])):
            total[key] = [total[key][0] + pair[0], total[key][1] + pair[1]]
        wire_rows.append({
            "lat": row["lat"], "lon": row["lon"],
            "download_gb": _gb(row["download_bytes"]),
            "disk_gb": _gb(disk),
            "time_s": row["time_s"],
            "textures": row["textures"],
            "terrain_data_cached": row["terrain_data_cached"],
            "has_history": row["has_history"],
        })
    free = _free_bytes(tile_probe)
    verdict, reason = disk_verdict(total["disk"], free, "the tile folder's drive")
    cache_free = None
    if not same_volume:
        cache_free = _free_bytes(cache_probe)
        cache_verdict = disk_verdict(total["cache"], cache_free,
                                     "the data folder's drive")
        order = ("ok", "warn", "refuse")
        if order.index(cache_verdict[0]) > order.index(verdict):
            verdict, reason = cache_verdict
    return {
        "tiles": wire_rows,
        "total": {"download_gb": _gb(total["download"]),
                  "disk_gb": _gb(total["disk"]),
                  "time_s": [int(t) for t in total["time"]]},
        "free_gb": None if free is None else round(free / GB, 1),
        "cache_free_gb": (None if cache_free is None
                          else round(cache_free / GB, 1)),
        "verdict": verdict,
        "reason": reason,
    }


def _constant_estimate(lat, lon, do_vector, do_imagery):
    """A tile the estimate could not read, priced from the constants."""
    zero = [0.0, 0.0]
    return {"lat": lat, "lon": lon,
            "download_bytes": list(TERRAIN_DATA_BYTES) if do_vector else zero,
            "tile_bytes": list(BUILD_FILES_BYTES) if (do_vector or do_imagery)
            else zero,
            "cache_bytes": list(TERRAIN_DATA_BYTES) if do_vector else zero,
            "time_s": [0, 0],
            "textures": {"count": [0, 0], "on_disk": 0, "cached": 0,
                         "to_download": [0, 0]},
            "terrain_data_cached": not do_vector, "has_history": False,
            "build_dir": FNAMES.build_dir(lat, lon, "")}


def start_plan_estimate(emit, tiles, provider="", zoomlevel=0,
                        custom_build_dir="", do_vector=True,
                        do_imagery=True, do_overlays=False, request=None):
    """The command: replies ``{"status": "started"}`` and a worker thread
    completes it with ``PlanEstimateReady`` carrying ``request``."""
    from .events import PlanEstimateReady
    cells = [(int(t[0]), int(t[1])) for t in (tiles or ())]

    def work():
        try:
            event = PlanEstimateReady(request=request, result=plan_estimate(
                cells, provider, zoomlevel, custom_build_dir,
                bool(do_vector), bool(do_imagery), bool(do_overlays)))
        except Exception as error:      # the event carries it; the session lives on
            event = PlanEstimateReady(request=request, error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-plan-estimate").start()
    return {"status": "started"}
