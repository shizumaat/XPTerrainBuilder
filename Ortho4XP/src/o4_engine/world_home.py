"""The World folder as the tiles' home (owner RULINGS 2026-11-12g/h, spec
``docs/specs/world-home-20261112.md``):

    g: "every build ... writes STRAIGHT INTO the World folder"
    h: "XPTerrainBuilder Data holds ONLY caches and downloads that would
        never hurt the user if thrown away"

Inside the app's own World pack (``world_commands.managed``, never a
foreign folder):

* ``XPTerrainBuilder_tiles/zOrtho4XP_<tile>/`` -- every build folder, its
  records with it (``FNAMES.WORLD_TILES_DIR``);
* ``XPTerrainBuilder_packages/`` -- the ``.xptb`` store
  (``FNAMES.WORLD_PACKAGES_DIR``, ``storage_packages.store_dir``);
* ``XPTerrainBuilder_home/journal.json`` -- this module's journal.

:func:`migrate` moves what the data folder still holds there -- its
``Tiles/zOrtho4XP_*``, a legacy custom build folder's ``zOrtho4XP_*``
(never Custom Scenery itself: those are per-tile packs Convert existing
tiles owns), and ``Tile_packages/*`` -- one journalled step per item,
resumable: a rename on one volume; across volumes a copy under
``<name>.part``, its bytes checked, renamed into place, and only then the
source removed.  A name the World folder already has is never
overwritten (``conflict``: the source stays).  A tile the session builds
or queues is left for the next start.  When nothing is left, the data
folder's pointer (``FNAMES.WORLD_HOME_POINTER``) names the pack and
``FNAMES.Tile_dir`` / ``store_dir`` serve the World home; until then they
stay in the data folder, so no tile is read from a half-moved home.  The
journal is backed up (``journal.json.<stamp>-before-<run>``) before a run
writes it.  Nothing of the user's is ever deleted.

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import time
from typing import Any, Callable, Dict, Iterable, List, Optional

import O4_File_Names as FNAMES

__all__ = ["HOME_DIR", "home_dirs", "describe", "migrate", "write_pointer"]

#: The journal's folder inside the World pack.
HOME_DIR = "XPTerrainBuilder_home"
_TILE = re.compile(r"zOrtho4XP_([+-]\d{2})([+-]\d{3})$")
_PART = ".part"


def home_dirs(scenery_dir: str) -> Optional[Dict[str, str]]:
    """``{"world", "tiles", "packages", "work"}`` of the World home in
    ``scenery_dir``, or ``None`` when the app has no World pack there (or
    the folder is foreign)."""
    from . import world_commands as WORLD
    if not scenery_dir or not WORLD.managed(scenery_dir):
        return None
    world = WORLD.pack_dir(scenery_dir)
    return {"world": world,
            "tiles": os.path.join(world, FNAMES.WORLD_TILES_DIR),
            "packages": os.path.join(world, FNAMES.WORLD_PACKAGES_DIR),
            "work": os.path.join(world, HOME_DIR)}


def describe() -> Dict[str, str]:
    """Where the tiles and packages live NOW (the apps' ``home``)."""
    from . import storage_packages as STORE
    return {"world": FNAMES.world_home(), "tiles_dir": FNAMES.Tile_dir,
            "packages_dir": STORE.store_dir()}


def write_pointer(world: str) -> None:
    """Name ``world`` as the tiles' home in the data folder (atomic)."""
    path = FNAMES.world_home_pointer()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + _PART
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"schema": "o4.world_home/1", "world_dir": world}, handle,
                  indent=1)
    os.replace(temp, path)


# ---------------------------------------------------------------------------
# Moving one item
# ---------------------------------------------------------------------------
def _same_volume(source: str, folder: str) -> bool:
    try:
        return os.stat(source).st_dev == os.stat(folder).st_dev
    except OSError:
        return False


def _bytes(path: str) -> tuple:
    """``(files, bytes)`` under ``path`` (a file: itself); links counted
    as links, never followed."""
    if not os.path.isdir(path) or os.path.islink(path):
        return 1, os.lstat(path).st_size
    files = size = 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            with contextlib.suppress(OSError):
                size += os.lstat(os.path.join(root, name)).st_size
                files += 1
    return files, size


def _copy(source: str, target: str) -> None:
    """Across volumes: a copy under a partial name, checked, renamed into
    place, then the source removed -- never the other way round."""
    partial = target + _PART
    if os.path.lexists(partial):
        if os.path.isdir(partial) and not os.path.islink(partial):
            shutil.rmtree(partial)          # our own half copy of a run killed
        else:
            os.remove(partial)
    if os.path.isdir(source) and not os.path.islink(source):
        shutil.copytree(source, partial, symlinks=True)
    else:
        shutil.copy2(source, partial, follow_symlinks=False)
    if _bytes(partial) != _bytes(source):
        raise OSError(f"{source}: the copy in {partial} does not match; "
                      "the source stays.")
    os.rename(partial, target)
    if os.path.isdir(source) and not os.path.islink(source):
        shutil.rmtree(source)
    else:
        os.remove(source)


def _move(source: str, target: str, journal, key: str) -> str:
    """One journalled move: ``moved``, ``conflict`` or ``error``.  A run
    killed after a cross-volume copy landed and before its source went
    (journal ``moving``, both there, the same bytes) is finished here."""
    if os.path.lexists(target):
        record = journal.get(key) or {}
        if (record.get("state") == "moving" and record.get("target") == target
                and _bytes(target) == _bytes(source)):
            try:
                if os.path.isdir(source) and not os.path.islink(source):
                    shutil.rmtree(source)
                else:
                    os.remove(source)
            except OSError as error:
                journal.set(key, state="error", error=str(error)[:300])
                return "error"
            journal.set(key, state="moved")
            return "moved"
        journal.set(key, state="conflict", source=source, target=target)
        return "conflict"
    journal.set(key, state="moving", source=source, target=target)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if _same_volume(source, os.path.dirname(target)):
            os.rename(source, target)
        else:
            _copy(source, target)
    except OSError as error:
        journal.set(key, state="error", error=str(error)[:300])
        return "error"
    journal.set(key, state="moved")
    return "moved"


# ---------------------------------------------------------------------------
# What moves
# ---------------------------------------------------------------------------
def _tile_folders(folder: str) -> List[tuple]:
    """``[(name, lat, lon)]`` of the tile build folders in ``folder``."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for name in names:
        match = _TILE.match(name)
        path = os.path.join(folder, name)
        if match and os.path.isdir(path) and not os.path.islink(path):
            out.append((name, int(match.group(1)), int(match.group(2))))
    return out


def _real(path: str) -> str:
    return os.path.normcase(os.path.realpath(path)) if path else ""


def _tile_sources(scenery_dir: str, legacy_build_dir: str,
                  dirs: Dict[str, str]) -> List[str]:
    """The folders whose tile folders move (module doc)."""
    out = [FNAMES.data_path("Tiles")]
    legacy = (legacy_build_dir or "").rstrip("/\\")
    if legacy and os.path.isdir(legacy) and _real(legacy) not in (
            _real(scenery_dir), _real(dirs["tiles"]), _real(out[0])):
        out.append(legacy)
    return out


def _reindex(moves: List[tuple]) -> int:
    """The on-demand index rows naming a moved folder name its new place
    (``[(old, new)]``; one SQL update a folder, no tile rescanned).  The
    rows changed; the index is a cache, so a failure is no error."""
    if not moves:
        return 0
    import O4_Imagery_OnDemand_Index as INDEX
    if not os.path.isfile(INDEX.index_path()):
        return 0
    try:
        conn = INDEX.open_index()
    except Exception:                       # no index: nothing names them
        return 0
    try:
        changed = sum(INDEX.repoint_folder(conn, old, new) for old, new in moves)
        conn.commit()
        return changed
    except Exception:
        return 0
    finally:
        conn.close()


def _rewrite_packaged(old_store: str, new_store: str) -> int:
    """``packaged.json``'s ``path`` fields under ``old_store`` pointed at
    ``new_store``; the rows changed."""
    from . import storage_packages as STORE
    record_path = os.path.join(new_store, STORE._RECORD)
    try:
        with open(record_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    changed = 0
    for row in data.values():
        path = row.get("path") if isinstance(row, dict) else None
        if path and _real(os.path.dirname(path)) == _real(old_store):
            row["path"] = os.path.join(new_store, os.path.basename(path))
            changed += 1
    if changed:
        temp = record_path + _PART
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
        os.replace(temp, record_path)
    return changed


def _backup(journal_path: str, run: str) -> Optional[str]:
    if not os.path.isfile(journal_path):
        return None
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = f"{journal_path}.{stamp}-before-{run}"
    shutil.copy2(journal_path, backup)
    return backup


def _plan(scenery_dir: str, legacy_build_dir: str, dirs: Dict[str, str],
          busy: Iterable) -> Dict[str, list]:
    """``{"tiles": [(source, target, lat, lon)], "packages": [(source,
    target)], "busy": [names]}``."""
    held = {str(name) for name in (busy or ())}    # "+53-064"
    tiles, waiting = [], []
    for folder in _tile_sources(scenery_dir, legacy_build_dir, dirs):
        for name, lat, lon in _tile_folders(folder):
            if FNAMES.short_latlon(lat, lon) in held:
                waiting.append(name)
                continue
            tiles.append((os.path.join(folder, name),
                          os.path.join(dirs["tiles"], name), lat, lon))
    store = FNAMES.data_path("Tile_packages")
    packages = []
    if os.path.isdir(store) and not os.path.islink(store):
        for name in sorted(os.listdir(store)):
            if not name.endswith(_PART):
                packages.append((os.path.join(store, name),
                                 os.path.join(dirs["packages"], name)))
    return {"tiles": tiles, "packages": packages, "busy": waiting}


def migrate(scenery_dir: str, legacy_build_dir: str = "",
            busy: Optional[Callable[[], Iterable]] = None,
            dry_run: bool = False) -> Dict[str, Any]:
    """Move the data folder's tiles and packages into the World home
    (module doc).  ``{"active", "moved", "conflicts", "errors", "busy",
    "left", "packages_moved", "backup", **describe()}``; ``active``: the
    pointer names the World home now."""
    from .world_migrate import Journal
    dirs = home_dirs(scenery_dir)
    if dirs is None:
        return {"active": False, "reason": "no_world_pack", **describe()}
    todo = _plan(scenery_dir, legacy_build_dir, dirs,
                 busy() if busy else ())
    out: Dict[str, Any] = {"moved": 0, "conflicts": 0, "errors": 0,
                           "busy": len(todo["busy"]), "packages_moved": 0,
                           "planned": len(todo["tiles"]) + len(todo["packages"])}
    if dry_run:
        return {**out, "active": bool(FNAMES.world_home()), **describe()}
    os.makedirs(dirs["tiles"], exist_ok=True)
    os.makedirs(dirs["packages"], exist_ok=True)
    journal = Journal(dirs["work"])
    if out["planned"]:
        out["backup"] = _backup(journal.path, "world-home")
    moved = []
    for source, target, _lat, _lon in todo["tiles"]:
        state = _move(source, target, journal, os.path.basename(source)
                      + "@" + os.path.dirname(source))
        out[{"moved": "moved", "conflict": "conflicts",
             "error": "errors"}[state]] += 1
        if state == "moved":
            moved.append((source, target))
    out["index_rows"] = _reindex(moved)
    old_store = FNAMES.data_path("Tile_packages")
    for source, target in todo["packages"]:
        state = _move(source, target, journal, "package:" + os.path.basename(source))
        if state == "moved":
            out["packages_moved"] += 1
        else:
            out[{"conflict": "conflicts", "error": "errors"}[state]] += 1
    if out["packages_moved"]:
        out["packaged_paths"] = _rewrite_packaged(old_store, dirs["packages"])
    # A conflict leaves a second copy in the data folder, never a gap: the
    # World folder already holds that tile.  An error or a busy tile is a
    # gap until the next start moves it.
    out["left"] = out["errors"] + out["busy"]
    if not out["left"]:
        write_pointer(dirs["world"])
    _log(out)
    return {**out, "active": bool(FNAMES.world_home()), **describe()}


def _log(out: Dict[str, Any]) -> None:
    from . import world_commands as WORLD
    WORLD.write_log({"world_home": {k: out.get(k) for k in (
        "planned", "moved", "packages_moved", "conflicts", "errors", "busy",
        "left")}})
