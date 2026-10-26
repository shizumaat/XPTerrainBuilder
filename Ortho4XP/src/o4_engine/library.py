"""The Library view's engine half (#824): what is built, and how much
space it and the download caches take, answered on one screen.

``library_scan`` lists every built tile of a working folder with its size
on disk, zoom level, imagery source, built date, the airports it graded,
the custom packs the build modified, whether X-Plane loads it, and who
built it.  ``cache_sizes`` sizes the three download caches, ``free_cache``
empties one, and ``library_delete`` deletes built tiles.

TWO RULES THE APPS RELY ON.  A tile built by another tool (no stamped
tile config and no step record of this app in its folder) is listed
READ-ONLY: it is never deleted here, whatever the caller sends.  And
nothing is deleted without ``confirm=True``: the unconfirmed call is an
``ok: false`` reply whose sentence says what would go and what will be
downloaded again, which is what the app's confirmation shows.

Sizing walks whole folders (an imagery cache holds hundreds of thousands
of files), so over the JSON-lines transport every command here replies
``{"status": "started"}`` and a worker thread completes it with
``LibraryReady`` carrying the command's id (:func:`start`).  The Qt app
calls the same functions on its own thread.
"""
from __future__ import annotations

import os
import shutil
import threading
import typing as _t

import O4_Custom_Scenery as PACKS
import O4_File_Names as FNAMES
import O4_Scenery_Links as LINKS
import O4_Settings_Model as SM
import O4_Text_Files as TEXT
import O4_Tile_Info as TINFO

__all__ = ["BUILT_HERE", "BUILT_ELSEWHERE", "CACHE_KINDS", "library_scan",
           "cache_sizes", "free_cache", "library_delete", "start"]

#: ``built_by`` of a tile this app built
BUILT_HERE = "XPTerrainBuilder"
#: ``built_by`` of a tile another tool built (listed read-only)
BUILT_ELSEWHERE = "other"

#: The download caches, in the order the apps list them:
#: kind -> (label, what freeing it costs later).
CACHE_KINDS = {
    "imagery": ("Imagery", "Orthophotos are downloaded again the next time "
                "a tile that uses them is built."),
    "elevation": ("Elevation", "Elevation data is downloaded again the next "
                  "time a tile that uses it is built."),
    "osm": ("Map data", "OpenStreetMap data is downloaded again the next "
            "time a tile that uses it is built."),
}


def _cache_dir(kind: str) -> str:
    """The folder of one cache, read at call time (the data root can move)."""
    return {"imagery": FNAMES.Imagery_dir,
            "elevation": FNAMES.Elevation_dir,
            "osm": FNAMES.OSM_dir}[kind]


# ---------------------------------------------------------------------------
# One tile
# ---------------------------------------------------------------------------
def _built_by(build_dir: str, lat: int, lon: int) -> str:
    """This app stamps every tile cfg it writes and records its build
    steps beside it; a folder with neither was built by another tool."""
    short = FNAMES.short_latlon(lat, lon)
    if os.path.isfile(os.path.join(build_dir, "Ortho4XP_" + short + "_steps.json")):
        return BUILT_HERE
    cfg = os.path.join(build_dir, "Ortho4XP_" + short + ".cfg")
    try:
        with TEXT.open_supplied(cfg) as handle:
            for line in handle:
                if line.split("=", 1)[0].strip() == SM.CFG_STAMP_KEY:
                    return BUILT_HERE
    except OSError:
        pass
    return BUILT_ELSEWHERE


def _graded_airports(lat: int, lon: int) -> list:
    """The airports with a patch in the tile's Patches folder."""
    try:
        names = os.listdir(FNAMES.patch_dir(lat, lon))
    except OSError:
        return []
    return sorted({icao for icao in map(FNAMES.patch_file_icao, names) if icao})


def _detected_imagery(build_dir: str) -> tuple:
    """``(provider, zl)`` read from the texture names, ``("", None)`` when
    none parses — for a tile whose config does not say."""
    try:
        names = os.listdir(os.path.join(build_dir, "textures"))
    except OSError:
        return "", None
    found = PACKS.imagery_from_file_names(names)
    return found if found else ("", None)


def _row(info, scenery_dir: str, packs_by_tile: dict) -> dict:
    key = FNAMES.short_latlon(info.lat, info.lon)
    provider, zl = info.provider, info.zl
    if not provider or zl is None:
        detected_provider, detected_zl = _detected_imagery(info.build_dir)
        provider = provider or detected_provider
        zl = zl if zl is not None else detected_zl
    status = LINKS.link_status(info.lat, info.lon, info.build_dir, scenery_dir)
    built_by = _built_by(info.build_dir, info.lat, info.lon)
    dates = [d for d in (info.mesh_date, info.imagery_date) if d is not None]
    return {
        "tile": key,
        "lat": info.lat,
        "lon": info.lon,
        "build_dir": info.build_dir,
        "size_bytes": TINFO.compute_size(info),
        "zl": zl,
        "provider": provider,
        "built": max(dates) if dates else None,
        "airports": _graded_airports(info.lat, info.lon),
        "packs_modified": packs_by_tile.get(key, []),
        "link_status": status.value,
        "in_xplane": status in (LINKS.LinkStatus.INSTALLED,
                                LINKS.LinkStatus.PHYSICAL),
        "built_by": built_by,
        "read_only": built_by != BUILT_HERE,
    }


def _packs_by_tile(scenery_dir: str) -> dict:
    """``{tile key: [{pack_name, pack_path, objects}]}`` from the packs'
    own provenance (``object_rebake.modified_packs``: one stat per pack)."""
    if not scenery_dir or not os.path.isdir(scenery_dir):
        return {}
    from auto_patch import object_rebake
    out: dict = {}
    for pack in object_rebake.modified_packs(scenery_dir):
        entry = {"pack_name": pack["pack_name"], "pack_path": pack["pack_path"],
                 "objects": pack["objects"]}
        for tile in pack["tiles"]:
            out.setdefault(tile, []).append(entry)
    return out


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def library_scan(working_dir: str, scenery_dir: str = "") -> dict:
    """ENGINE COMMAND ``library_scan``: every built tile of *working_dir*
    (the per-tile build folders' parent), its total, and the caches.

    :returns: ``{"tiles": [row, ...], "tiles_bytes": int,
        "caches": cache_sizes()["caches"]}``, rows sorted by tile key.
    """
    packs = _packs_by_tile(scenery_dir)
    rows = [_row(info, scenery_dir, packs)
            for _key, info in sorted(TINFO.scan_tiles(working_dir).items())]
    return {"tiles": rows,
            "tiles_bytes": sum(row["size_bytes"] for row in rows),
            "caches": cache_sizes()["caches"]}


def cache_sizes() -> dict:
    """ENGINE COMMAND ``cache_sizes``: each download cache's folder, size
    and what freeing it costs later."""
    caches = []
    for kind, (label, redownload) in CACHE_KINDS.items():
        path = _cache_dir(kind)
        caches.append({"kind": kind, "label": label, "path": path,
                       "bytes": TINFO.tree_size(path) if path else 0,
                       "redownload": redownload})
    return {"caches": caches}


def _check_cache(kind: str, confirm: bool) -> str:
    if kind not in CACHE_KINDS:
        raise ValueError("%r is not a cache; send one of %s"
                         % (kind, ", ".join(CACHE_KINDS)))
    path = _cache_dir(kind)
    if not confirm:
        raise ValueError("Freeing the %s cache deletes everything in %s. %s "
                         "Send confirm=true to free it."
                         % (CACHE_KINDS[kind][0].lower(), path,
                            CACHE_KINDS[kind][1]))
    return path


def free_cache(kind: str, confirm: bool = False) -> dict:
    """ENGINE COMMAND ``free_cache``: empty one download cache (the folder
    itself stays).  Refused without ``confirm``.

    :returns: ``{"kind", "freed_bytes", "redownload"}``
    """
    path = _check_cache(kind, confirm)
    freed = 0
    try:
        names = os.listdir(path)
    except OSError:
        names = []
    for name in names:
        child = os.path.join(path, name)
        if os.path.isdir(child) and not os.path.islink(child):
            size = TINFO.tree_size(child)
            shutil.rmtree(child, ignore_errors=True)
            freed += size - TINFO.tree_size(child)
        else:
            try:
                size = os.lstat(child).st_size
                os.unlink(child)
                freed += size
            except OSError:
                pass
    return {"kind": kind, "freed_bytes": freed,
            "redownload": CACHE_KINDS[kind][1]}


def _deletable(working_dir: str, pair) -> tuple:
    """``(lat, lon, build_dir)`` of a tile this app may delete, or raise
    ``ValueError`` with the reason in the user's words."""
    lat, lon = int(pair[0]), int(pair[1])
    key = FNAMES.short_latlon(lat, lon)
    info = TINFO.scan_tiles(working_dir).get((lat, lon))
    if info is None:
        raise ValueError("tile %s is not built in %s" % (key, working_dir))
    build_dir = info.build_dir
    if os.path.islink(build_dir) or os.path.realpath(
            os.path.dirname(build_dir)) != os.path.realpath(working_dir):
        raise ValueError("tile %s's folder %s is a link or lies outside the "
                         "tiles folder; it is not deleted" % (key, build_dir))
    if _built_by(build_dir, lat, lon) != BUILT_HERE:
        raise ValueError("tile %s was built by another tool; the Library "
                         "never deletes it" % key)
    return lat, lon, build_dir


def _check_delete(tiles, working_dir: str, confirm: bool) -> list:
    checked = [_deletable(working_dir, pair) for pair in tiles or []]
    if not confirm:
        raise ValueError("Deleting %d tile(s) removes their folders and "
                         "takes them out of X-Plane. Send confirm=true to "
                         "delete." % len(checked))
    return checked


def library_delete(tiles, working_dir: str, scenery_dir: str = "",
                   confirm: bool = False) -> dict:
    """ENGINE COMMAND ``library_delete``: delete built tiles' folders,
    removing their X-Plane link first.  Every tile is checked before any
    is deleted: one tile built by another tool refuses the whole call.
    Refused without ``confirm``.  Patches (the user's airport edits) and
    the caches stay.

    :returns: ``{"deleted": [[lat, lon], ...], "freed_bytes": int}``
    """
    checked = _check_delete(tiles, working_dir, confirm)
    deleted, freed = [], 0
    for lat, lon, build_dir in checked:
        if scenery_dir:
            status = LINKS.link_status(lat, lon, build_dir, scenery_dir)
            if status in (LINKS.LinkStatus.INSTALLED, LINKS.LinkStatus.BROKEN):
                LINKS.uninstall(lat, lon, build_dir, scenery_dir)
        size = TINFO.tree_size(build_dir)
        shutil.rmtree(build_dir, ignore_errors=True)
        freed += size - TINFO.tree_size(build_dir)
        deleted.append([lat, lon])
    return {"deleted": deleted, "freed_bytes": freed}


#: The commands :func:`start` runs, and the checks each makes on the read
#: loop so a refusal is the command's own ``ok: false`` reply.
_COMMANDS: dict = {
    "library_scan": (library_scan, None),
    "cache_sizes": (cache_sizes, None),
    "free_cache": (free_cache,
                   lambda kw: _check_cache(kw.get("kind", ""),
                                           bool(kw.get("confirm")))),
    "library_delete": (library_delete,
                       lambda kw: _check_delete(kw.get("tiles"),
                                                kw.get("working_dir", ""),
                                                bool(kw.get("confirm")))),
}


def start(emit: _t.Callable[[_t.Any], None], command: str,
          request: _t.Any = None, busy: _t.Callable[[], bool] = lambda: False,
          **kwargs) -> dict:
    """Run one command on a worker thread; ``LibraryReady`` with
    ``request`` = the command's id completes it.  A refusal (bad
    arguments, no ``confirm``, a deletion while a build runs) raises here,
    on the read loop, and is the command's ``ok: false`` reply."""
    from .events import LibraryReady
    function, check = _COMMANDS[command]
    if command in ("free_cache", "library_delete") and busy():
        raise ValueError("A build is running; stop it or let it finish "
                         "before deleting anything.")
    if check is not None:
        check(kwargs)

    def work() -> None:
        try:
            event = LibraryReady(request=request, command=command,
                                 result=function(**kwargs))
        except Exception as error:      # the event carries it; the session lives on
            event = LibraryReady(request=request, command=command,
                                 error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-library").start()
    return {"status": "started"}
