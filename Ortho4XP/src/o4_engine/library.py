"""The Library view's engine half (#824): what is built, and how much
space it and the download caches take, answered on one screen.

``library_scan`` lists every built tile of a working folder with its size
on disk, zoom level, imagery source, built date, the airports it graded,
the custom packs the build modified, whether X-Plane loads it, and who
built it.  ``cache_sizes`` sizes the three download caches, ``free_cache``
empties one, and ``library_delete`` deletes built tiles.
``library_export_bundle`` and ``library_import_bundle`` carry a built
tile to another installation (#1699 phase 1, ``tile_bundle``); since
#2014 they make and install a ``.xptb`` PACKAGE, the format the
``package_save`` / ``package_plan`` / ``package_install`` /
``package_merge`` commands behind "Export Package…", the install sheet
and combining packages read and write.  The ``library_check`` … ``library_signout`` commands
are the shared PATCH LIBRARY's airport entries (#1699 phase 2,
``patch_library``): the check when the app opens, the build box's match
list, laying an entry down, and "Publish patch" with its GitHub sign-in.

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

import contextlib
import os
import shutil
import threading
import typing as _t
from concurrent.futures import ThreadPoolExecutor

import O4_Custom_Scenery as PACKS
import O4_File_Names as FNAMES
import O4_Rebuild_Cache as REBUILD
import O4_Scenery_Links as LINKS
import O4_Tile_Info as TINFO
import O4_Tile_Staleness as _STALE

from . import storage as _storage

__all__ = ["BUILT_HERE", "BUILT_ELSEWHERE", "CACHE_KINDS", "ROW_WORKERS", "library_scan",
           "cache_sizes", "free_cache", "library_delete",
           "library_export_bundle", "library_import_bundle",
           "package_save", "package_airports", "package_estimate", "package_plan",
           "package_install", "package_merge", "package_developer",
           "PATCH_LIBRARY_COMMANDS", "COMMANDS", "patch_library_command", "start"]

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


#: Library rows built at once: each walks a tile folder (I/O bound).  On
#: 2,551 tiles (owner's library, 2026-11-11) 38 s one at a time, 17 s
#: four at a time; eight or sixteen were slower.
ROW_WORKERS = 4


def _cache_dir(kind: str) -> str:
    """The folder of one cache, read at call time (the data root can move)."""
    return {"imagery": FNAMES.Imagery_dir,
            "elevation": FNAMES.Elevation_dir,
            "osm": FNAMES.OSM_dir}[kind]


# ---------------------------------------------------------------------------
# One tile
# ---------------------------------------------------------------------------
def _built_by(build_dir: str, lat: int, lon: int) -> str:
    """``BUILT_HERE`` or ``BUILT_ELSEWHERE`` (``O4_Tile_Info.built_here``)."""
    return BUILT_HERE if TINFO.built_here(build_dir, lat, lon) else BUILT_ELSEWHERE


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
        # Imagery on demand (#1992): built low-res, and pinned sharp.
        "on_demand": bool(getattr(info, "on_demand", False)),
        "pinned": bool(getattr(info, "pinned", False)),
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
def library_scan(working_dir: str, scenery_dir: str = "", caches: bool = True,
                 infos: "dict | None" = None) -> dict:
    """ENGINE COMMAND ``library_scan``: every built tile of *working_dir*
    (the per-tile build folders' parent), its total, and the caches.

    ``infos`` -- the map's last scan of *working_dir*
    (``EngineSession.scanned_tiles``; the transport passes it), so the
    tile folders are not read twice (#2006); None reads them.  ``caches``
    False leaves the cache walk out (``"caches": []``).  The rows are
    built :data:`ROW_WORKERS` at a time (each is a folder walk).

    :returns: ``{"tiles": [row, ...], "tiles_bytes": int,
        "caches": cache_sizes()["caches"]}``, rows sorted by tile key.
    """
    packs = _packs_by_tile(scenery_dir)
    if infos is None:
        infos = TINFO.scan_tiles(working_dir)
    ordered = [info for _key, info in sorted(infos.items())]
    with ThreadPoolExecutor(ROW_WORKERS, thread_name_prefix="o4-library-row") as pool:
        rows = list(pool.map(lambda info: _row(info, scenery_dir, packs), ordered))
    return {"tiles": rows,
            "tiles_bytes": sum(row["size_bytes"] for row in rows),
            "caches": cache_sizes()["caches"] if caches else []}


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
    itself stays); the elevation and map caches write every built tile's
    package first (``o4_engine.package_first``).  Refused without
    ``confirm``.

    :returns: ``{"kind", "freed_bytes", "redownload"}``
    """
    path = _check_cache(kind, confirm)
    if kind in ("elevation", "osm"):         # the built tiles' packages first
        from . import package_first as FIRST
        first = FIRST.Pass()
        for lat, lon in sorted(FIRST.built_tiles()):
            first.tile(lat, lon, built=True)
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
    Refused without ``confirm``.  The tile's rebuild data (RULINGS
    2026-11-10d) goes with it, its package written first
    (``o4_engine.package_first``); patches (the user's airport edits) and
    the other caches stay.

    :returns: ``{"deleted": [[lat, lon], ...], "freed_bytes": int}``
    """
    from . import package_first as FIRST
    checked = _check_delete(tiles, working_dir, confirm)
    deleted, freed = [], 0
    first = FIRST.Pass()
    for lat, lon, build_dir in checked:
        # its package first (owner 2026-11-11T16:45Z, ``package_first``)
        first.tile(lat, lon, _custom_build_dir(working_dir), built=True)
        if scenery_dir:
            status = LINKS.link_status(lat, lon, build_dir, scenery_dir)
            if status in (LINKS.LinkStatus.INSTALLED, LINKS.LinkStatus.BROKEN):
                LINKS.uninstall(lat, lon, build_dir, scenery_dir)
        freed += REBUILD.remove(build_dir, lat, lon)     # its rebuild data
        size = TINFO.tree_size(build_dir)
        shutil.rmtree(build_dir, ignore_errors=True)
        freed += size - TINFO.tree_size(build_dir)
        deleted.append([lat, lon])
    return {"deleted": deleted, "freed_bytes": freed}


def _custom_build_dir(working_dir: str) -> str:
    """The ``custom_build_dir`` of a tile folder inside ``working_dir``
    (``""`` for the data root's own ``Tiles``)."""
    if not working_dir or os.path.normpath(working_dir) == os.path.normpath(
            FNAMES.Tile_dir):
        return ""
    return os.path.join(working_dir, "")


def library_export_bundle(lat, lon, working_dir: str, out_dir: str) -> dict:
    """ENGINE COMMAND ``library_export_bundle`` (#1699 phase 1; a PACKAGE
    since #2014): the built tile's ``.xptb`` package in ``out_dir``, made
    by the same code as "Export Package…" (:func:`package_save`).
    Refused for a tile another tool built.

    :returns: ``{"path", "bytes", "key", "files", "seconds", …}``
    """
    lat, lon = int(lat), int(lon)
    build_dir = FNAMES.build_dir(lat, lon, _custom_build_dir(working_dir))
    if _built_by(build_dir, lat, lon) != BUILT_HERE:
        raise ValueError("tile %s was not built by this app; it has no "
                         "package to export" % FNAMES.short_latlon(lat, lon))
    return package_save([[lat, lon]], working_dir, out_dir)


def library_import_bundle(path: str, working_dir: str) -> dict:
    """ENGINE COMMAND ``library_import_bundle`` (#1699 phase 1): install a
    package or a tile bundle into ``working_dir`` (:func:`package_install`,
    which reads both).  Nothing is downloaded but, at the next build,
    imagery.

    :returns: ``{"tile", "key", "airports", "bytes", "reused", "seconds",
        …}`` — a package's install details with its first tile and its
        airports.
    """
    done = package_install(path, working_dir)
    tiles = done.get("tiles") or [{}]
    done.setdefault("tile", tiles[0].get("tile", ""))
    done["airports"] = sorted(a["icao"] if isinstance(a, dict) else a
                              for t in tiles for a in t.get("airports") or [])
    done.setdefault("reused", [])
    done.setdefault("seconds", 0.0)
    return done


# ---------------------------------------------------------------------------
# Packages (#2014): "Export Package…", the install sheet, combining
# ---------------------------------------------------------------------------
def package_save(tiles, working_dir: str, out: str, airports=None,
                 title: str = "", creator: str = "", notes: str = "",
                 url: str = "", kind: str = "", into_pack: bool = False) -> dict:
    """ENGINE COMMAND ``package_save``: the ``.xptb`` package of ``tiles``
    (``[[lat, lon], …]``; with ``airports``, of those airports only) at
    ``out`` — a ``.xptb`` path or a folder (``tile_bundle.package``);
    ``kind`` ``"exact"`` / ``"patch"`` / ``"tile"`` (``tile_bundle.kinds``;
    empty: exact with airports, tile without); ``into_pack``: saved into
    the airport's own pack folder instead of ``out`` (RULINGS 2026-11-11m
    (3))."""
    from tile_bundle import package
    return package.save_package(tiles, out, _custom_build_dir(working_dir),
                                airports or None, kind=kind or None,
                                into_pack=bool(into_pack), title=title,
                                creator=creator, notes=notes, url=url)


def package_airports(tiles, working_dir: str = "") -> dict:
    """ENGINE COMMAND ``package_airports``: ``{"tiles": {tile key: [icao,
    …]}, "custom": {tile key: [icao, …]}, "default": icao}`` — the
    airports the export window offers for the tiles, those with the
    user's own files, and the one it opens on."""
    from tile_bundle import package
    return package.airports_of(tiles, _custom_build_dir(working_dir))


def package_estimate(tiles, working_dir: str = "", airport: str = "") -> dict:
    """ENGINE COMMAND ``package_estimate``: per package kind, the
    estimated size, the recipient's downloads and build time of exporting
    ``airport`` (``tile_bundle.estimate``).  Writes nothing."""
    from tile_bundle import estimate, package
    pairs = sorted({(int(a), int(b)) for a, b in tiles or ()})
    if airport:
        held = package.airports_of(pairs, _custom_build_dir(working_dir))["tiles"]
        pairs = [p for p in pairs if str(airport).upper()
                 in held.get(FNAMES.short_latlon(*p), [])] or pairs
    return estimate.estimate(pairs, airport)


def package_plan(path: str, working_dir: str = "", choices=None) -> dict:
    """ENGINE COMMAND ``package_plan``: what installing ``path`` would do —
    its tiles, airports and packs, sources and terms, what it adds and
    replaces, and the questions to ask (``tile_bundle.install.plan``).
    Writes nothing; refused for a damaged or incompatible package."""
    from tile_bundle import install
    return install.plan(path, _custom_build_dir(working_dir), choices)


def package_install(path: str, working_dir: str = "", choices=None) -> dict:
    """ENGINE COMMAND ``package_install``: install ``path``
    (``tile_bundle.install.install``); ``choices`` ``{icao: "keep" |
    "replace"}`` answers the plan's questions."""
    from tile_bundle import install
    return install.install(path, _custom_build_dir(working_dir), choices)


def package_developer(icao: str, tiles, working_dir: str = "",
                      action: str = "read") -> dict:
    """ENGINE COMMAND ``package_developer`` (RULINGS 2026-11-11m (3)):
    the airport's pack and its author's choice for its objects —
    ``action`` ``"read"``, ``"final"`` ("Objects are final"),
    ``"default"`` or ``"apply"`` ("Apply XPTerrainBuilder's object fixes
    into my pack"), ``tile_bundle.pack_apply.developer``."""
    from tile_bundle import pack_apply
    return pack_apply.developer(icao, tiles, _custom_build_dir(working_dir), action)


def package_merge(paths, out: str, title: str = "", creator: str = "",
                  notes: str = "", url: str = "") -> dict:
    """ENGINE COMMAND ``package_merge``: several packages combined into one
    at ``out`` (``tile_bundle.merge``)."""
    from tile_bundle import merge
    return merge.merge_packages(paths, out, title=title, creator=creator,
                                notes=notes, url=url)


def _patch_library_commands() -> dict:
    """The patch library's commands (#1699 phase 2), imported when run."""
    from patch_library import apply as _apply
    from patch_library import github as _github
    from patch_library import publish as _publish
    from patch_library import scan as _scan

    def check(working_dir: str = "", force: bool = False) -> dict:
        return _scan.check(_custom_or_tiles(working_dir), bool(force))

    def matches(cells, working_dir: str = "") -> dict:
        return _scan.matches(cells, working_dir)

    def apply(entry: str, working_dir: str = "") -> dict:
        return _apply.apply_entry(entry, working_dir)

    def publish_preview(lat, lon, icao: str, working_dir: str = "",
                        kind: str = "", notes: str = "") -> dict:
        return _publish.preview(lat, lon, icao, working_dir, kind, notes)

    def publish(lat, lon, icao: str, working_dir: str = "", kind: str = "",
                notes: str = "", accept: bool = False) -> dict:
        return _publish.publish(lat, lon, icao, working_dir, kind, notes,
                                bool(accept))

    return {"library_check": check, "library_matches": matches,
            "library_apply": apply, "library_ignore": _scan.ignore,
            "library_publish_preview": publish_preview,
            "library_publish": publish,
            "library_signin_start": _github.device_start,
            "library_signin_poll": _github.device_poll,
            "library_signout": _github.forget_token}


def _custom_or_tiles(working_dir: str) -> str:
    return working_dir or FNAMES.Tile_dir


#: The patch library's commands, in the order the apps meet them.
PATCH_LIBRARY_COMMANDS = ("library_check", "library_matches", "library_apply",
                          "library_ignore", "library_publish_preview",
                          "library_publish", "library_signin_start",
                          "library_signin_poll", "library_signout")


def patch_library_command(name: str) -> _t.Callable:
    """The patch library command ``name`` as a function of its keywords —
    what the transport runs, and what the Qt window calls in process."""
    def run(**kwargs):
        return _patch_library_commands()[name](**kwargs)
    return run


#: What a command must not do while a build runs (:func:`start`).
_REFUSED_WHILE_BUILDING = {
    "free_cache": "deleting anything", "library_delete": "deleting anything",
    "library_export_bundle": "exporting a tile",
    "library_import_bundle": "importing a tile",
    "package_install": "installing a package",
    "package_developer": "changing an airport pack",
    "library_apply": "laying a library patch down",
    "rebuild_migrate": "moving tiles' rebuild data"}

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
    "library_export_bundle": (library_export_bundle, None),
    "library_import_bundle": (library_import_bundle, None),
    "package_save": (package_save, None),
    "package_airports": (package_airports, None),
    "package_estimate": (package_estimate, None),
    "package_plan": (package_plan, None),
    "package_install": (package_install, None),
    "package_merge": (package_merge, None),
    "package_developer": (package_developer, None),
    **{name: (patch_library_command(name), None) for name in PATCH_LIBRARY_COMMANDS},
}
# Settings > Storage (#1724) runs through the same worker and refusals.
_COMMANDS.update(_storage.COMMANDS)
# Moving old tiles' rebuild data into the cache (RULINGS 2026-11-10d).
_COMMANDS.update(REBUILD.COMMANDS)
# The map's stale-tile check (#1958) runs through the same worker.
_COMMANDS.update(_STALE.COMMANDS)
_REFUSED_WHILE_BUILDING.update(_storage.REFUSED_WHILE_BUILDING)

#: Every command :func:`start` runs (the transport registers these).
COMMANDS = tuple(_COMMANDS)


def start(emit: _t.Callable[[_t.Any], None], command: str,
          request: _t.Any = None, busy: _t.Callable[[], bool] = lambda: False,
          **kwargs) -> dict:
    """Run one command on a worker thread; ``LibraryReady`` with
    ``request`` = the command's id completes it.  A refusal (bad
    arguments, no ``confirm``, a deletion while a build runs) raises here,
    on the read loop, and is the command's ``ok: false`` reply."""
    from .events import LibraryReady
    function, check = _COMMANDS[command]
    reading = command == "package_developer" and kwargs.get("action", "read") == "read"
    if command in _REFUSED_WHILE_BUILDING and not reading and busy():
        raise ValueError("A build is running; stop it or let it finish "
                         "before %s." % _REFUSED_WHILE_BUILDING[command])
    if check is not None:
        check(kwargs)

    def work() -> None:
        # A command that changes tiles holds the imagery follow job's
        # fetches off them (#1992 P3b), as a build does.
        from .imagery_follow import paused
        hold = (paused(command) if command in _REFUSED_WHILE_BUILDING
                else contextlib.nullcontext())
        try:
            with hold:
                result = function(**kwargs)
            event = LibraryReady(request=request, command=command,
                                 result=result)
        except Exception as error:      # the event carries it; the session lives on
            event = LibraryReady(request=request, command=command,
                                 error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-library").start()
    return {"status": "started"}
