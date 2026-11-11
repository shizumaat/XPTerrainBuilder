"""Older airport tiles shrunk to their PACKAGE when the disk budget is
full (owner 2026-11-11T15:32Z, RULINGS 2026-11-11l item 5):

    "we could use our package files to bundle/compress older airports
    when the disk budget is full and drop their imagery so they can be
    quickly rebuilt on demand"

The per-tile rebuild data tier of the one disk budget (RULINGS 2026-11-10d
(3), the last tier: ``storage_budget.TIERS``) runs :func:`evict` as its
``TIER_HOOKS`` entry.  Within it, oldest first and favorites last (10d,
10c), a BUILT tile that grades an airport is shrunk to its ``.xptb``
package (``tile_bundle.package.save_package``: its downloaded inputs, no
imagery) in the local package store (:func:`store_dir`) instead of
simply losing its rebuild data: the package is written, then the tile's
rebuild data, its own downloaded inputs (now in the package) and its
sharp imagery go.  The tile's DSF and its patches stay (the floor,
10d (2)).  A tile that cannot be packaged (its inputs are gone) loses
its rebuild data as before, and the rest of the tier is the rebuild
store's oldest-first eviction.

So that the inputs are still there when the rebuild tier comes, the
elevation and map extract tier (earlier in 10d's order) keeps the own
inputs of those tiles (:func:`guarded_inputs`): they leave compressed,
in the package, rather than one by one.

:func:`packaged` is the record of which tiles are packaged
(``<store>/packaged.json``); :func:`restore` installs a tile's package
before a build of it (the World job and the flight manager build through
``world_job_run._SessionBuilder``), so the rebuild downloads nothing but
imagery (``tile_bundle.install``'s ``downloads_left``).

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
import typing as _t

import O4_File_Names as FNAMES

__all__ = ["KIND", "STORE_DIR", "store_dir", "packaged", "candidates",
           "guarded_inputs", "package_tile", "evict", "restore"]

#: The store row of the packages (``storage.STORES``).
KIND = "tile_packages"
#: The package store, in the data folder.
STORE_DIR = "Tile_packages"
_RECORD = "packaged.json"


def store_dir() -> str:
    """The local package store (read at call time: the data root moves)."""
    return FNAMES.data_path(STORE_DIR)


def _record_path() -> str:
    return os.path.join(store_dir(), _RECORD)


def packaged() -> dict:
    """``{tile key: {"path", "package_bytes", "freed_bytes", "airports",
    "utc", "restored"}}`` of the tiles shrunk to their package."""
    try:
        with open(_record_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_record(data: dict) -> None:
    os.makedirs(store_dir(), exist_ok=True)
    temp = _record_path() + ".part"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=1, sort_keys=True)
    os.replace(temp, _record_path())


def _favorites() -> set:
    """The favorite (pinned) tiles' keys of the on-demand index."""
    from . import storage as STORAGE
    conn = STORAGE._ondemand_index()
    if conn is None:
        return set()
    try:
        return {row[0] for row in conn.execute(
            "SELECT DISTINCT tile FROM textures WHERE pinned = 1")}
    except Exception:                       # an old index: no favorites
        return set()
    finally:
        conn.close()


def _graded_airports(lat: int, lon: int) -> list:
    try:
        names = os.listdir(FNAMES.patch_dir(lat, lon))
    except OSError:
        return []
    return sorted({icao for icao in map(FNAMES.patch_file_icao, names) if icao})


def _last_used(folder: str) -> float:
    newest = 0.0
    for root, _dirs, names in os.walk(folder):
        for name in names:
            with contextlib.suppress(OSError):
                st = os.lstat(os.path.join(root, name))
                newest = max(newest, st.st_mtime, st.st_atime)
    return newest


def candidates() -> list:
    """``[{"lat", "lon", "build_dir", "cache", "airports", "favorite",
    "last_used"}]``: the tiles of the data folder this app built that
    grade an airport and still hold rebuild data, not packaged yet;
    non-favorites oldest first, then the favorites oldest first."""
    import O4_Tile_Info as TINFO
    done, favorites = packaged(), _favorites()
    out = []
    for (lat, lon), info in TINFO.scan_tiles(FNAMES.Tile_dir).items():
        key = FNAMES.short_latlon(lat, lon)
        cache = FNAMES.rebuild_dir(info.build_dir, lat, lon)
        airports = _graded_airports(lat, lon)
        if (key in done and not done[key].get("restored")) or not airports \
                or not cache or not TINFO.built_here(info.build_dir, lat, lon):
            continue
        out.append({"lat": lat, "lon": lon, "build_dir": info.build_dir,
                    "cache": cache, "airports": airports,
                    "favorite": key in favorites,
                    "last_used": _last_used(cache)})
    out.sort(key=lambda c: (c["favorite"], c["last_used"], c["lat"], c["lon"]))
    return out


def guarded_inputs() -> set:
    """The own downloaded inputs of every :func:`candidates` tile, as
    ``os.path.normcase`` absolute paths: the elevation and map extract
    tier leaves them for the package."""
    from tile_bundle import inputs as INPUTS
    keep = set()
    for c in candidates():
        keep |= {os.path.normcase(os.path.abspath(p))
                 for p in INPUTS.own_files(c["lat"], c["lon"])}
    return keep


def _store_of(path: str):
    """The ``storage`` store a cache file lies in (``None`` outside)."""
    from . import storage as STORAGE
    path = os.path.normcase(os.path.abspath(path))
    best = None
    for store in STORAGE.STORES:
        root = store.path()
        if not root:
            continue
        root = os.path.join(os.path.normcase(os.path.abspath(root)), "")
        if path.startswith(root) and (best is None
                                      or len(root) > len(best[0])):
            best = (root, store)
    return best[1] if best else None


def _drop(paths, sweep, now: float) -> int:
    """Delete ``paths`` through ``sweep``, each booked on its store and
    under its store's rules (``storage._deletable``: no config, lock or
    patch, nothing written in the last hour)."""
    from . import storage as STORAGE
    freed = 0
    for path in paths:
        store = _store_of(path)
        try:
            st = os.lstat(path)
        except OSError:
            continue
        if (store is not None and os.path.isfile(path)
                and STORAGE._deletable(store, os.path.basename(path), st, now)):
            freed += sweep.delete(store, path, st)
    return freed


def _rebuild_files(cache: str) -> list:
    return [os.path.join(root, name) for root, _d, names in os.walk(cache)
            for name in names]


def _drop_sharp(lat: int, lon: int, sweep, now: float) -> int:
    """The tile's sharp imagery made low-res (``imagery_downgrade``)."""
    from . import imagery_downgrade as DOWNGRADE
    from . import storage as STORAGE
    conn = STORAGE._ondemand_index()
    if conn is None or sweep.dry_run:
        return 0
    try:
        result = DOWNGRADE.downgrade_all(
            conn, tile=FNAMES.short_latlon(lat, lon), abort=sweep.abort,
            reason="tile packaged (disk budget)")
    finally:
        conn.close()
    sweep.downgraded(STORAGE._BY_KIND[STORAGE.ONDEMAND], result)
    return int(result.get("freed_bytes") or 0)


def package_tile(candidate: dict, sweep, now: float) -> "dict | None":
    """Shrink one :func:`candidates` tile to its package (module doc);
    ``{"freed_bytes", "package_bytes", "path"}``, or ``None`` when it
    cannot be packaged (nothing is dropped then)."""
    from tile_bundle import BundleRefused
    from tile_bundle import inputs as INPUTS
    from tile_bundle import package as PACKAGE

    from . import storage as STORAGE
    lat, lon = candidate["lat"], candidate["lon"]
    key = FNAMES.short_latlon(lat, lon)
    path, size = os.path.join(store_dir(), key + ".xptb"), 0
    if not sweep.dry_run:
        try:
            done = PACKAGE.save_package([(lat, lon)], path)
        except (BundleRefused, OSError, ValueError) as error:
            STORAGE.write_log("not packaged %s: %s" % (key, error))
            return None
        path, size = done["path"], int(done["bytes"])
        sweep.freed[KIND] = sweep.freed.get(KIND, 0) - size
    freed = _drop(_rebuild_files(candidate["cache"]), sweep, now)
    freed += _drop(INPUTS.own_files(lat, lon), sweep, now)
    freed += _drop_sharp(lat, lon, sweep, now)
    if not sweep.dry_run:
        record = packaged()
        record[key] = {"path": path, "package_bytes": size,
                       "freed_bytes": freed, "airports": candidate["airports"],
                       "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "restored": False}
        _write_record(record)
        STORAGE.write_log("packaged %s: %d bytes freed, package %d bytes"
                          % (key, freed, size))
    return {"freed_bytes": freed - size, "package_bytes": size, "path": path}


def evict(over_by: int, sweep, now: float) -> int:
    """The rebuild data tier (``storage_budget.TIER_HOOKS``): package
    candidates until ``over_by`` bytes are freed, then the rebuild
    store's own oldest-first eviction for the rest; the bytes freed."""
    from . import storage as STORAGE
    freed = 0
    for candidate in candidates():
        if freed >= over_by:
            break
        if sweep.abort():
            sweep.stopped = True
            return freed
        done = package_tile(candidate, sweep, now)
        if done is not None:
            freed += done["freed_bytes"]
    if freed < over_by:
        freed += STORAGE._evict_oldest([STORAGE._BY_KIND[STORAGE.REBUILD]],
                                       over_by - freed, sweep, now)
    return freed


def restore(lat: int, lon: int,
            install: "_t.Callable[[str], dict] | None" = None) -> "dict | None":
    """Install a packaged tile's package before a build of it (its inputs
    laid back; only imagery left to download); its record is marked
    restored.  ``None`` when the tile is not packaged (or its package is
    gone)."""
    key = FNAMES.short_latlon(int(lat), int(lon))
    record = packaged()
    row = record.get(key)
    if not row or row.get("restored") or not os.path.isfile(row.get("path", "")):
        return None
    if install is None:
        from tile_bundle.install import install
    details = install(row["path"])
    row["restored"] = True
    _write_record(record)
    return details
