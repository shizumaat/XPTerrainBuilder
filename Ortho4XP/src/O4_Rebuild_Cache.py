"""Rebuild data out of the installed tile folders (owner RULINGS 2026-11-10d
(4)).

"Rebuild data (Data*.mesh/.node/.poly/.alt, cfg backups, other build
intermediates) moves out of installed tile folders into a per-tile rebuild
cache in the data folder; installed tiles hold only what X-Plane reads."

The paths are ``O4_File_Names``' (:func:`O4_File_Names.rebuild_path`, the
one resolution point every reader and writer goes through).  This module
owns the rest:

* :func:`is_rebuild_name` -- which entries of a tile folder are rebuild
  data;
* :func:`claim` -- give a tile folder its cache (``Rebuild_cache/<tile>``,
  named by a pointer record in the folder) and move the rebuild data an
  older build left there into it.  Every build step that writes rebuild
  data claims first, so a rebuild of an old tile ends with its folder
  clean.  The step record moves with the files, and ``O4_Step_Reuse``
  reads its paths where the files are now, so the steps stay reusable;
* :func:`migrate_folder` -- the explicit migration of every tile folder in
  a folder (the ``rebuild_migrate`` engine command and the CLI below).  It
  MOVES, never deletes: a file the cache already holds is left where it is
  and reported;
* :func:`remove` -- a deleted tile's cache goes with it (the Library).

A cache records the tile folder it belongs to (``owner.json``): a second
folder of the same tile (a copy, a test's temporary build folder) gets a
cache of its own (``<tile>_2``), so one folder's files are never read for
another's.

CLI: ``python src/O4_Rebuild_Cache.py [--dry-run] FOLDER [FOLDER ...]``
(each FOLDER a tiles folder -- the data folder's ``Tiles``, X-Plane's
``Custom Scenery`` -- or one tile folder).

Never raises out of :func:`claim`: a cache that cannot be made leaves the
tile's files where they are, which still builds.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys

import O4_Config_Names as CN
import O4_File_Names as FNAMES

__all__ = ["OWNER_NAME", "is_rebuild_name", "legacy_entries", "claim",
           "migrate_tile", "migrate_folder", "remove", "rebuild_migrate",
           "COMMANDS", "main"]

#: the cache's record of the tile folder it belongs to
OWNER_NAME = "owner.json"

_TILE_FOLDER_RE = re.compile(r"XP_([+-]\d{2}[+-]\d{3})$")


def is_rebuild_name(name: str, lat: int, lon: int,
                    grouped: bool = False) -> bool:
    """Whether the tile-folder entry ``name`` is the tile's rebuild data:
    its ``Data<tile>.*`` files, its step record, its tile config's backup
    and -- in a per-tile folder only, their names not carrying the tile --
    ``FNAMES.UNTAGGED_REBUILD_NAMES``."""
    short = FNAMES.short_latlon(lat, lon)
    if name.startswith("Data" + short + "."):
        return True
    step_record = os.path.basename(FNAMES.step_record_file("", lat, lon))
    if name in (step_record, CN.tile_cfg_name(lat, lon) + ".bak",
                CN.ortho4xp_tile_cfg_name(lat, lon) + ".bak"):
        return True
    return not grouped and name in FNAMES.UNTAGGED_REBUILD_NAMES


def _grouped(build_dir: str, lat: int, lon: int) -> bool:
    return os.path.basename(os.path.normpath(build_dir)) != FNAMES.tile_dir(
        lat, lon)


def legacy_entries(build_dir: str, lat: int, lon: int) -> list:
    """The rebuild files the tile folder itself holds, sorted."""
    grouped = _grouped(build_dir, lat, lon)
    try:
        names = os.listdir(build_dir)
    except OSError:
        return []
    return sorted(n for n in names if is_rebuild_name(n, lat, lon, grouped)
                  and os.path.isfile(os.path.join(build_dir, n)))


def _real(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _write_json(path: str, doc: dict) -> None:
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(temporary, path)


def _free_cache_dir(build_dir: str, lat: int, lon: int) -> str:
    """``Rebuild_cache/<tile>``, or ``<tile>_N`` when that one belongs to
    another tile folder that still exists."""
    root = FNAMES.rebuild_root()
    base = FNAMES.tile_dir(lat, lon)
    mine = _real(build_dir)
    for index in range(1, 1000):
        cache = os.path.join(root, base if index == 1 else
                             "%s_%d" % (base, index))
        owner = FNAMES.read_json_dict(os.path.join(cache, OWNER_NAME)).get(
            "build_dir")
        if (not os.path.isdir(cache) or not isinstance(owner, str)
                or _real(owner) == mine or not os.path.isdir(owner)):
            return cache
    raise OSError("no free rebuild cache folder for %s" % base)


def _cache_for(build_dir: str, lat: int, lon: int) -> str:
    """The tile folder's cache, made and pointed to when it has none."""
    cache = FNAMES.rebuild_dir(build_dir, lat, lon)
    if cache is not None:
        return cache
    cache = _free_cache_dir(build_dir, lat, lon)
    os.makedirs(cache, exist_ok=True)
    _write_json(os.path.join(cache, OWNER_NAME),
                {"build_dir": os.path.abspath(build_dir),
                 "tile": FNAMES.short_latlon(lat, lon)})
    _write_json(FNAMES.rebuild_pointer_path(build_dir, lat, lon),
                {"schema": FNAMES.REBUILD_POINTER_SCHEMA,
                 "cache": os.path.abspath(cache)})
    return cache


def _move(build_dir: str, cache: str, names, dry_run: bool) -> dict:
    moved, kept, size = [], [], 0
    for name in names:
        source = os.path.join(build_dir, name)
        if cache and os.path.exists(os.path.join(cache, name)):
            kept.append(name)       # the cache's is the newer: never replaced
            continue
        try:
            nbytes = os.path.getsize(source)
            if not dry_run:
                shutil.move(source, os.path.join(cache, name))  # a rename
        except OSError:
            kept.append(name)
            continue
        size += nbytes
        moved.append(name)
    return {"moved": moved, "kept": kept, "bytes": size}


def migrate_tile(build_dir: str, lat: int, lon: int,
                 dry_run: bool = False) -> dict:
    """Move the tile folder's rebuild data into its cache (made when it
    has none).  ``dry_run`` moves nothing and makes nothing.

    :returns: ``{"tile", "build_dir", "cache", "moved": [names],
        "kept": [names the cache already holds or that would not move],
        "bytes"}`` -- ``bytes`` moved (or that would move)
    """
    names = legacy_entries(build_dir, lat, lon)
    cache = FNAMES.rebuild_dir(build_dir, lat, lon)
    if names and not dry_run:
        cache = _cache_for(build_dir, lat, lon)
    result = _move(build_dir, cache, names, dry_run)
    return dict(result, tile=FNAMES.short_latlon(lat, lon),
                build_dir=build_dir, cache=cache)


def claim(tile) -> str | None:
    """A build step that writes rebuild data starts here: the tile folder
    gets its cache and the old files move in (:func:`migrate_tile`).
    The cache, or ``None`` when it could not be made (the step then
    writes into the tile folder, as before 10d).  Never raises."""
    build_dir = getattr(tile, "build_dir", None)
    if not build_dir or not os.path.isdir(build_dir):
        return None
    try:
        cache = _cache_for(build_dir, tile.lat, tile.lon)
        migrate_tile(build_dir, tile.lat, tile.lon)
        return cache
    except Exception:
        return None


def _tile_folders(folder: str) -> list:
    """``(build_dir, lat, lon)`` of ``folder`` itself when it is a tile
    folder, else of each tile folder in it (links not followed)."""
    match = _TILE_FOLDER_RE.search(os.path.basename(os.path.normpath(folder)))
    if match:
        return [(folder,) + FNAMES.parse_tile_key(match.group(1))]
    out = []
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name)
    except OSError:
        return []
    for entry in entries:
        match = _TILE_FOLDER_RE.search(entry.name)
        if match and entry.is_dir(follow_symlinks=False):
            out.append((entry.path,) + FNAMES.parse_tile_key(match.group(1)))
    return out


def migrate_folder(folder: str, dry_run: bool = False) -> dict:
    """:func:`migrate_tile` for every tile folder in ``folder`` (or for
    ``folder``, a tile folder).  Idempotent: a migrated tile moves
    nothing.

    :returns: ``{"folder", "tiles": [per-tile result with something to
        move or kept], "moved_files", "bytes", "dry_run"}``
    """
    rows = []
    for build_dir, lat, lon in _tile_folders(folder):
        row = migrate_tile(build_dir, lat, lon, dry_run)
        if row["moved"] or row["kept"]:
            rows.append(row)
    return {"folder": folder, "tiles": rows,
            "moved_files": sum(len(r["moved"]) for r in rows),
            "bytes": sum(r["bytes"] for r in rows), "dry_run": bool(dry_run)}


def remove(build_dir: str, lat: int, lon: int) -> int:
    """Delete the tile folder's cache (its tile is being deleted); the
    bytes it freed.  Only a cache inside the rebuild root is deleted."""
    cache = FNAMES.rebuild_dir(build_dir, lat, lon)
    if cache is None or _real(os.path.dirname(cache)) != _real(
            FNAMES.rebuild_root()):
        return 0
    import O4_Tile_Info as TINFO
    size = TINFO.tree_size(cache)
    shutil.rmtree(cache, ignore_errors=True)
    return size - TINFO.tree_size(cache)


def rebuild_migrate(folders=(), dry_run: bool = False) -> dict:
    """ENGINE COMMAND ``rebuild_migrate``: move the rebuild data of every
    tile folder in ``folders`` (default: the data folder's ``Tiles``) into
    the rebuild cache.  Moves only, never deletes; ``dry_run`` answers
    what would move.

    :returns: ``{"folders": [migrate_folder result], "moved_files",
        "bytes", "dry_run"}``
    """
    results = [migrate_folder(f, dry_run) for f in
               (list(folders or ()) or [FNAMES.Tile_dir]) if f]
    return {"folders": results,
            "moved_files": sum(r["moved_files"] for r in results),
            "bytes": sum(r["bytes"] for r in results),
            "dry_run": bool(dry_run)}


#: The commands ``o4_engine.library.start`` runs for this module (the shape
#: of ``library._COMMANDS``).
COMMANDS: dict = {"rebuild_migrate": (rebuild_migrate, None)}


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Move tile folders' rebuild data (Data*.mesh/.node/"
                    ".poly/.alt, step records, cfg backups) into the data "
                    "folder's rebuild cache (RULINGS 2026-11-10d). Moves "
                    "only; never deletes.")
    parser.add_argument("folders", nargs="*",
                        help="tiles folders or tile folders (default: the "
                             "data folder's Tiles)")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would move; move nothing")
    args = parser.parse_args(argv)
    out = rebuild_migrate(args.folders, args.dry_run)
    for folder in out["folders"]:
        for row in folder["tiles"]:
            print("%s  %s %d file(s), %.1f MB -> %s%s" % (
                row["tile"], "would move" if args.dry_run else "moved",
                len(row["moved"]), row["bytes"] / 1e6, row["cache"] or "?",
                ("  (kept: %s)" % ", ".join(row["kept"]))
                if row["kept"] else ""))
    print("%s %d file(s), %.1f GB" % (
        "would move" if args.dry_run else "moved", out["moved_files"],
        out["bytes"] / 1e9))
    return 0


if __name__ == "__main__":
    sys.exit(main())
