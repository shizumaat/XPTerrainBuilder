"""Settings ▸ Storage, the engine half (#1724, #1725): what each folder of
the data folder holds, clearing it by hand, and the optional automatic
cleanup.

``storage_scan`` lists every STORE (one folder, or part of one) with the
bytes deleting it would give back (``O4_Disk_Usage.freeable_bytes``: an
APFS clone or a hard-linked DDS entry frees ~0, whatever ``du`` says), its
file count and when a file in it was last used.  ``storage_clear`` empties
caches, whole or only the files not used since a date; ``dry_run`` answers
what it would free, which is what the apps' confirmation shows.
``storage_auto_clean`` applies the two settings — ``storage_auto_clean_days``
(off by default) and ``storage_cache_caps_gb`` (least recently used first)
— and the apps call it at launch and after a build, never during one.

SAFETY, the rules the apps rely on:

* a store is a CACHE (re-downloadable, or rebuilt by the next build) or
  KEPT (the user's work and what X-Plane loads: built tiles, patches,
  overlays, own elevation files).  A KEPT store is sized but never cleared
  here, named or not — tiles are deleted in the Library, one confirmation
  per selection;
* inside a cache, a config, a pack backup (``*.anchor_bak``), a patch, a
  lock, a file written in the last hour (a download in flight) and every
  file of a folder holding a fresh lock are never deleted; a symlink is
  neither followed nor removed;
* nothing is deleted without ``confirm=True``, while a build runs
  (``library.start`` refuses; ``abort`` stops a sweep a new build
  overtakes), or without a line in ``logs/storage.log``.

ON-DEMAND IMAGERY (#1992 spec §6.3): the ``ondemand`` store is the sharp
imagery the follow job fetched (counted from the on-demand index, not by
walking a folder); clearing it DOWNGRADES every texture but the
favorites to its placeholder (``o4_engine.imagery_downgrade``), it never
deletes a texture name; its row carries the favorites as a second line
(inside the budget, RULINGS 2026-11-10c (2)) and the budget's floor, and
the automatic cleanup holds the ortho budget
(``imagery_on_demand_cap_gb``; favorites made low-res last).  The
``imagery`` and ``dds`` caches never
delete the source or the entry of a texture the index marks upgraded or
pinned.

Over the JSON-lines transport these are Library commands: they reply
``{"status": "started"}`` and ``LibraryReady`` completes them
(``library.start``).  The Qt app calls the functions on its own thread.
"""
from __future__ import annotations

import os
import stat
import time
import typing as _t
from dataclasses import dataclass

import O4_DDS_Cache as DDSC
import O4_Disk_Usage as DISK
import O4_File_Names as FNAMES

from . import storage_packages as _PACKAGES

__all__ = ["CACHE", "KEPT", "STORES", "cache_bytes", "AUTO_CLEAN_DAYS", "CAPS_SETTING",
           "ONDEMAND", "REBUILD", "storage_scan", "storage_clear", "storage_auto_clean",
           "parse_caps", "write_log", "COMMANDS", "REFUSED_WHILE_BUILDING"]

#: a store the user may clear: the next build downloads or rebuilds it
CACHE = "cache"
#: a store that is sized, never cleared here
KEPT = "kept"

#: the settings :func:`storage_auto_clean` reads (``O4_Cfg_Vars``)
AUTO_CLEAN_DAYS = "storage_auto_clean_days"
CAPS_SETTING = "storage_cache_caps_gb"

#: the on-demand imagery store's kind (#1992)
ONDEMAND = "ondemand"
#: the per-tile rebuild data store's kind (RULINGS 2026-11-10d (4))
REBUILD = "rebuild"

#: a file written this recently may be a download or a write in flight
IN_FLIGHT_SECONDS = 3600.0
#: a folder whose ``*.lock`` is younger than this is held by a build
LOCK_FRESH_SECONDS = 86400.0
#: the deletion log, under the data folder's ``logs``
LOG_NAME = "storage.log"

_PROTECTED_SUFFIXES = (".cfg", ".cfg.bak", ".anchor_bak", ".lock",
                       ".patch.osm", ".account.json", ".cookies.txt")
#: The rebuild data store keeps a tile's ``.cfg.bak`` with its mesh: it is
#: rebuild data, cleared with it (RULINGS 2026-11-10d (4)).
_REBUILD_PROTECTED_SUFFIXES = tuple(s for s in _PROTECTED_SUFFIXES
                                    if s != ".cfg.bak")


@dataclass(frozen=True)
class Store:
    """One row of Settings ▸ Storage."""

    kind: str
    label: str
    policy: str
    note: str
    path: _t.Callable[[], str]
    #: child names of ``path`` another store owns
    skip: tuple = ()


def _extracts_dir() -> str:
    import O4_OSM_Extracts as OSMX
    return OSMX.STORE_DIRECTORY


def _logs_dir() -> str:
    return FNAMES.data_path("logs")


def _ondemand_dir() -> str:
    import O4_Imagery_Placeholder as PLACEHOLDER
    return FNAMES.data_path(PLACEHOLDER.STORE_DIR)


def _ondemand_index():
    """The on-demand index, or ``None`` when no build made one."""
    import O4_Imagery_OnDemand_Index as INDEX
    path = INDEX.index_path()
    return INDEX.open_index(path) if os.path.isfile(path) else None


_AGAIN = " is downloaded again the next time a tile that needs it is built."
#: Every store, in the order the apps list them.
STORES: tuple = (
    Store("imagery", "Orthophotos", CACHE, "Imagery" + _AGAIN,
          lambda: FNAMES.Imagery_dir),
    Store("dds", "Texture cache (DDS)", CACHE,
          "Textures are converted again from the orthophotos when needed; "
          "an entry a built tile also holds frees nothing.",
          DDSC.cache_root),
    Store(ONDEMAND, "Sharp imagery near flown areas", CACHE,
          "Made low-res again, never deleted: sharp imagery is fetched "
          "again when you fly near. Favorites count too and are made "
          "low-res last; \"Make all low-res again\" keeps them.", _ondemand_dir),
    Store("elevation", "Elevation and airport insets", CACHE,
          "Elevation" + _AGAIN, lambda: FNAMES.Elevation_dir),
    Store("osm_extracts", "Regional map extracts", CACHE,
          "A regional extract is downloaded again only for a new tile in "
          "its region; tiles already cut keep their own map data.",
          _extracts_dir),
    Store("osm", "Map data per tile", CACHE, "Map data" + _AGAIN,
          lambda: FNAMES.OSM_dir, skip=("_regional_extracts",)),
    Store("airport_mod", "Airport pack caches", CACHE,
          "Rebuilt from the installed airport packs by the next build that "
          "reads them.", FNAMES.airport_mod_cache_root),
    Store("dsf_dumps", "X-Plane scenery dumps", CACHE,
          "Rebuilt from X-Plane's scenery by the next build that reads it.",
          lambda: FNAMES.Default_dsf_cache_dir),
    Store("masks", "Water masks", CACHE,
          "Rebuilt by the next build of the tile.", FNAMES.masks_root),
    Store("previews", "Map previews", CACHE,
          "Downloaded again when the map shows the area.",
          lambda: FNAMES.Preview_dir),
    Store("tmp", "Temporary files", CACHE,
          "Working files of finished builds.", lambda: FNAMES.Tmp_dir),
    Store("logs", "Logs", CACHE,
          "Build logs; a problem report needs the recent ones.", _logs_dir),
    # Per-tile rebuild data (RULINGS 2026-11-10d (4)): last in the clear
    # order of 10d (3) -- it is what makes a rebuild take minutes.
    Store(REBUILD, "Rebuild data", CACHE,
          "The meshes and elevation grids of built tiles: a tile without "
          "them rebuilds from its map and elevation data, which takes "
          "longer. X-Plane never reads them.", FNAMES.rebuild_root),
    # Older airport tiles shrunk to their package by the disk budget
    # (RULINGS 2026-11-11l item 5, ``storage_packages``): what rebuilds
    # them with only imagery to download; never cleared here.
    Store(_PACKAGES.KIND, "Packaged tiles", KEPT,
          "Older airport tiles kept as small packages of their map and "
          "elevation data: they rebuild with only imagery to download.",
          _PACKAGES.store_dir),
    Store("tiles", "Built tiles", KEPT,
          "Your scenery. Delete tiles in the Library.",
          lambda: FNAMES.Tile_dir),
    Store("patches", "Airport patches", KEPT,
          "Your airport edits; never deleted here.",
          lambda: FNAMES.Patch_dir),
    Store("overlays", "Overlays", KEPT,
          "X-Plane loads them; never deleted here.",
          lambda: FNAMES.Overlay_dir),
    Store("geotiffs", "Your elevation files", KEPT,
          "Never deleted here.", lambda: FNAMES.Geotiff_dir),
)
_BY_KIND = {store.kind: store for store in STORES}


# ---------------------------------------------------------------------------
# Walking a store
# ---------------------------------------------------------------------------
def _last_used(st: os.stat_result) -> float:
    return max(st.st_mtime, st.st_atime)


def _held_by_lock(names, folder: str, now: float) -> bool:
    for name in names:
        if name.endswith(".lock"):
            try:
                age = now - os.lstat(os.path.join(folder, name)).st_mtime
            except OSError:
                continue
            if age < LOCK_FRESH_SECONDS:
                return True
    return False


def _deletable(store: Store, name: str, st: os.stat_result,
               now: float) -> bool:
    """A file of a CACHE store that is no config, backup, patch, lock or
    log, and was not written in the last hour (the folder-lock test is
    the caller's)."""
    protected = (_REBUILD_PROTECTED_SUFFIXES if store.kind == REBUILD
                 else _PROTECTED_SUFFIXES)
    return (store.policy == CACHE
            and not name.endswith(protected)
            and name != LOG_NAME
            and now - st.st_mtime >= IN_FLIGHT_SECONDS)


def _ondemand_protected(store: Store) -> set:
    """The files of ``store`` the on-demand index marks upgraded or
    pinned (spec §6.3), normalised; empty for other stores."""
    if store.kind not in ("imagery", "dds"):
        return set()
    import O4_Imagery_OnDemand_Index as INDEX
    try:
        conn = _ondemand_index()
    except Exception:
        return set()
    if conn is None:
        return set()
    try:
        if store.kind == "imagery":
            return INDEX.protected_jpegs(conn)
        return {os.path.normcase(os.path.abspath(DDSC.entry_path(key)))
                for key in INDEX.protected_cache_keys(conn)}
    finally:
        conn.close()


def _files(store: Store, now: float):
    """``(path, stat, deletable)`` of every regular file of ``store``;
    a symlink is neither followed nor listed; a file the on-demand index
    protects is listed, never deletable."""
    root = store.path()
    if store.kind == ONDEMAND or not root or not os.path.isdir(root):
        return
    keep = _ondemand_protected(store)
    for folder, dirs, names in os.walk(root):
        if folder == root and store.skip:
            dirs[:] = [d for d in dirs if d not in store.skip]
        held = _held_by_lock(names, folder, now)
        for name in names:
            path = os.path.join(folder, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            yield path, st, (not held and _deletable(store, name, st, now)
                             and os.path.normcase(os.path.abspath(path))
                             not in keep)


def _measure_ondemand(store: Store) -> dict:
    """The ``ondemand`` row from the index: the sharp bytes in the ortho
    budget (favorites included, RULINGS 2026-11-10c (2)), the favorites
    line and the airport-core rows, and the budget's floor: what the
    on-demand tiles hold even low-res (``over_at_floor``: more than the
    budget, the apps warn)."""
    import O4_Imagery_OnDemand_Index as INDEX

    from . import imagery_downgrade as DOWNGRADE
    row = {"kind": store.kind, "label": store.label, "policy": store.policy,
           "note": store.note, "path": store.path(), "bytes": 0,
           "apparent_bytes": 0, "files": 0, "last_used": None,
           "pinned_bytes": 0, "pinned_files": 0, "core_files": 0,
           "floor_bytes": 0, "cap_bytes": DOWNGRADE.cap_bytes(),
           "over_at_floor": False}
    conn = _ondemand_index()
    if conn is None:
        return row
    try:
        upgraded = INDEX.rows(conn, state="upgraded")
        near = [r["last_near_at"] for r in upgraded if r["last_near_at"]]
        budget = DOWNGRADE.budget(conn)
        row.update(
            bytes=INDEX.capped_bytes(conn), apparent_bytes=sum(
                int(r["full_bytes"] or 0) for r in upgraded),
            files=len(upgraded), last_used=max(near) if near else None,
            pinned_bytes=INDEX.pinned_bytes(conn),
            pinned_files=sum(1 for r in upgraded if r["pinned"]),
            core_files=sum(1 for r in upgraded if r["core"] and not r["pinned"]),
            floor_bytes=budget.fixed, cap_bytes=budget.cap,
            over_at_floor=budget.over_at_floor)
    finally:
        conn.close()
    return row


def _measure(store: Store, now: float) -> dict:
    if store.kind == ONDEMAND:
        return _measure_ondemand(store)
    freeable = apparent = files = 0
    newest = None
    for path, st, _deletable in _files(store, now):
        files += 1
        apparent += st.st_size
        freeable += DISK.freeable_bytes(path, st)
        used = _last_used(st)
        newest = used if newest is None else max(newest, used)
    return {"kind": store.kind, "label": store.label, "policy": store.policy,
            "note": store.note, "path": store.path(), "bytes": freeable,
            "apparent_bytes": apparent, "files": files, "last_used": newest}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def parse_caps(text: str) -> dict:
    """``"imagery=100, dds=20"`` → ``{"imagery": 100e9, "dds": 20e9}``
    (bytes).  A KEPT or unknown store, or a value that is not a positive
    number, raises ``ValueError`` in the user's words."""
    caps = {}
    for part in (text or "").replace(";", ",").split(","):
        if not part.strip():
            continue
        kind, _, value = part.partition("=")
        kind = kind.strip()
        store = _BY_KIND.get(kind)
        if store is None or store.policy != CACHE:
            raise ValueError("%r is not a cache; name one of %s" % (
                kind, ", ".join(s.kind for s in STORES if s.policy == CACHE)))
        try:
            gigabytes = float(value)
        except ValueError:
            gigabytes = -1.0
        if gigabytes <= 0:
            raise ValueError("the limit for %s must be a number of GB above "
                             "0, not %r" % (kind, value.strip()))
        caps[kind] = int(gigabytes * 1e9)
    return caps


def _settings() -> tuple:
    """``(days, caps)`` from the global config, read at call time (the app
    writes the file; this process's module globals may be older)."""
    import O4_Settings_Model as SM
    raw = SM.read_global_raw()
    try:
        days = max(0.0, float(raw.get(AUTO_CLEAN_DAYS, "") or 0))
    except ValueError:
        days = 0.0
    try:
        caps = parse_caps(raw.get(CAPS_SETTING, ""))
    except ValueError:
        caps = {}
    return days, caps


# ---------------------------------------------------------------------------
# Deleting
# ---------------------------------------------------------------------------
class _Sweep:
    """One deletion pass: what it freed, per store, and its log lines."""

    def __init__(self, dry_run: bool, reason: str,
                 abort: _t.Callable[[], bool] | None) -> None:
        self.dry_run = dry_run
        self.reason = reason
        self.abort = abort or (lambda: False)
        self.freed: dict = {}
        self.files = 0
        self.stopped = False
        self._log = None
        self._first = None

    @property
    def first(self):
        """The pass's package-first record (``o4_engine.package_first``):
        a built tile's package is written before its rebuild data or
        inputs go (owner 2026-11-11T16:45Z)."""
        if self._first is None:
            from . import package_first as FIRST
            self._first = FIRST.Pass(self.dry_run)
        return self._first

    def delete(self, store: Store, path: str, st: os.stat_result) -> int:
        size = DISK.freeable_bytes(path, st)
        written = self.first.before_delete(store.kind, path)
        if written:
            self.freed[_PACKAGES.KIND] = self.freed.get(_PACKAGES.KIND, 0) - written
        if not self.dry_run:
            try:
                os.remove(path)
            except OSError:
                return 0
            self._write("deleted %d bytes %s (%s, %s)"
                        % (size, path, store.kind, self.reason))
        self.freed[store.kind] = self.freed.get(store.kind, 0) + size
        self.files += 1
        return size

    def downgraded(self, store: Store, result: dict) -> None:
        """Book an on-demand downgrade's result (its own log lines are
        written by ``imagery_downgrade``)."""
        self.freed[store.kind] = (self.freed.get(store.kind, 0)
                                  + int(result.get("freed_bytes", 0)))
        self.files += int(result.get("downgraded", 0))
        self.stopped = self.stopped or bool(result.get("stopped"))

    def _write(self, line: str) -> None:
        if self._log is None:
            os.makedirs(_logs_dir(), exist_ok=True)
            self._log = open(os.path.join(_logs_dir(), LOG_NAME), "a",
                             encoding="utf-8", newline="\n")
        self._log.write(time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime())
                        + line + "\n")

    def result(self) -> dict:
        if self._log is not None:
            self._write("freed %d bytes in %d file(s) (%s)"
                        % (sum(self.freed.values()), self.files, self.reason))
            self._log.close()
            self._log = None
        return {"freed_bytes": sum(self.freed.values()), "files": self.files,
                "kinds": dict(self.freed), "dry_run": self.dry_run,
                "stopped": self.stopped}


def write_log(line: str) -> None:
    """Append one dated line to ``logs/storage.log`` (a deletion or a
    downgrade made outside a :class:`_Sweep`)."""
    os.makedirs(_logs_dir(), exist_ok=True)
    with open(os.path.join(_logs_dir(), LOG_NAME), "a", encoding="utf-8",
              newline="\n") as log:
        log.write(time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime())
                  + line + "\n")


def _clear_ondemand(store: Store, cutoff: float | None,
                    sweep: _Sweep) -> None:
    """Clearing the ``ondemand`` store: every unpinned sharp texture (not
    flown near since ``cutoff``) made low-res again."""
    from . import imagery_downgrade as DOWNGRADE
    conn = _ondemand_index()
    if conn is None:
        return
    try:
        sweep.downgraded(store, DOWNGRADE.downgrade_all(
            conn, not_near_since=cutoff, dry_run=sweep.dry_run,
            reason=sweep.reason, abort=sweep.abort))
    finally:
        conn.close()


def _hold_ondemand_cap(sweep: _Sweep, now: float) -> "dict | None":
    """The automatic cleanup's on-demand cap (``imagery_on_demand_cap_gb``:
    over the cap, made low-res to 90 % of it); its ``{"over_at_floor",
    "floor_bytes", "cap_bytes"}`` (the apps warn when the tiles do not fit
    it even low-res).  A dry run sizes nothing here: what a sweep frees
    depends on the camera."""
    from . import imagery_downgrade as DOWNGRADE
    if sweep.dry_run:
        return None
    conn = _ondemand_index()
    if conn is None:
        return None
    try:
        result = DOWNGRADE.sweep(conn, DOWNGRADE.budget(conn), now=now,
                                 abort=sweep.abort)
        sweep.downgraded(_BY_KIND[ONDEMAND], result)
        return {key: result[key] for key in
                ("over_at_floor", "floor_bytes", "cap_bytes")}
    finally:
        conn.close()


def _prune_empty_dirs(root: str) -> None:
    for folder, _dirs, _names in os.walk(root, topdown=False):
        if folder != root:
            try:
                os.rmdir(folder)            # only an empty folder goes
            except OSError:
                pass


def _clear_store(store: Store, cutoff: float | None, sweep: _Sweep,
                 now: float) -> None:
    if store.kind == ONDEMAND:
        _clear_ondemand(store, cutoff, sweep)
        return
    for path, st, deletable in list(_files(store, now)):
        if sweep.abort():
            sweep.stopped = True
            return
        if deletable and (cutoff is None or _last_used(st) < cutoff):
            sweep.delete(store, path, st)
    if not sweep.dry_run:
        _prune_empty_dirs(store.path())


def _evict_oldest(stores, over_by: int, sweep: _Sweep, now: float,
                  keep: "set | None" = None) -> int:
    """Delete the deletable files of ``stores`` together, least recently
    used first, until ``over_by`` bytes are freed; the bytes freed.  A
    protected file is never evicted (the ONDEMAND store has no files:
    it is made low-res, ``imagery_downgrade``), nor one of ``keep``
    (``os.path.normcase`` absolute paths)."""
    keep = keep or set()
    rows = [(store, path, st) for store in stores if store.kind != ONDEMAND
            for path, st, deletable in _files(store, now) if deletable
            and os.path.normcase(os.path.abspath(path)) not in keep]
    rows.sort(key=lambda row: _last_used(row[2]))
    freed = 0
    for store, path, st in rows:
        if freed >= over_by:
            break
        if sweep.abort():
            sweep.stopped = True
            break
        freed += sweep.delete(store, path, st)
    if not sweep.dry_run:
        for store in stores:
            _prune_empty_dirs(store.path())
    return freed


def _evict_to_cap(store: Store, cap: int, sweep: _Sweep, now: float) -> None:
    """Least recently used first until what the store holds is at most
    ``cap`` bytes; a protected file counts but is never evicted."""
    if store.kind == ONDEMAND:
        return              # its cap is imagery_on_demand_cap_gb
    total = sum(DISK.freeable_bytes(path, st)
                for path, st, _d in _files(store, now))
    if total > cap:
        _evict_oldest([store], total - cap, sweep, now)


def _remove_redundant(sweep: _Sweep, now: float) -> None:
    """Delete what ``storage_redundant`` names -- texture-cache entries
    their tiles hold, caches of packs no longer installed, superseded
    pack dumps -- under the same rules as every other deletion here."""
    import o4_engine.storage_redundant as REDUNDANT
    for kind, paths in (("dds", REDUNDANT.dds_held_by_tiles()),
                        ("airport_mod", REDUNDANT.airport_pack_leftovers())):
        store = _BY_KIND[kind]
        root = os.path.join(os.path.abspath(store.path()), "")
        for path in paths:
            if sweep.abort():
                sweep.stopped = True
                return
            folder, name = os.path.split(path)
            if not os.path.abspath(path).startswith(root):
                continue
            try:
                st = os.lstat(path)
                held = _held_by_lock(os.listdir(folder), folder, now)
            except OSError:
                continue
            if (stat.S_ISREG(st.st_mode) and not held
                    and _deletable(store, name, st, now)):
                sweep.delete(store, path, st)
        if not sweep.dry_run:
            _prune_empty_dirs(store.path())
    if not sweep.dry_run:
        DDSC.forget_missing()


def _caches(kinds) -> list:
    """The stores ``kinds`` names (every cache when empty); a KEPT or
    unknown store refuses the whole call."""
    if not kinds:
        return [store for store in STORES if store.policy == CACHE]
    out = []
    for kind in kinds:
        store = _BY_KIND.get(kind)
        if store is None:
            raise ValueError("%r is not a store; send one of %s"
                             % (kind, ", ".join(_BY_KIND)))
        if store.policy != CACHE:
            raise ValueError("%s: %s" % (store.label, store.note))
        out.append(store)
    return out


def _check_clear(kwargs: dict) -> list:
    stores = _caches(kwargs.get("kinds"))
    days = kwargs.get("older_than_days")
    if days is not None and float(days) < 0:
        raise ValueError("older_than_days must be 0 or more")
    if not kwargs.get("dry_run") and not kwargs.get("confirm"):
        raise ValueError("Clearing deletes %s. Send dry_run=true to see the "
                         "space it frees, then confirm=true to clear."
                         % ", ".join(s.label.lower() for s in stores))
    return stores


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cache_bytes(rows: "list[dict]") -> int:
    """The bytes of the CACHE stores among the scan ``rows``: the
    Caches line's total and the usage bar's Caches part (owner
    2026-11-12: the two must be one figure)."""
    return sum(int(r.get("bytes") or 0) for r in rows if r["policy"] == CACHE)


def storage_scan() -> dict:
    """ENGINE COMMAND ``storage_scan``: every store with its freeable and
    apparent bytes, file count and last use (epoch seconds, None when
    empty), plus the two automatic-cleanup settings.

    :returns: ``{"root", "stores": [row, ...], "budget"
        (``storage_budget.status``), "installed"
        (``storage_installed.installed_tiles``), "cache_bytes", "kept_bytes",
        "measured", "auto_clean_days", "caps"}``
    """
    from . import storage_budget as TOTAL
    from . import storage_installed as INSTALLED
    from .storage_redundant import _custom_scenery_dir
    now = time.time()
    rows = [_measure(store, now) for store in STORES]
    days, caps = _settings()
    root = FNAMES.current_data_root()
    installed = INSTALLED.installed_tiles(_custom_scenery_dir())
    return {"root": root, "stores": rows,
            "budget": TOTAL.status(rows, installed_bytes=installed["local_bytes"]),
            "installed": installed,
            "cache_bytes": cache_bytes(rows),
            "kept_bytes": sum(r["bytes"] for r in rows if r["policy"] == KEPT),
            "measured": ("private" if DISK.private_bytes(root) is not None
                         else "allocated"),
            "auto_clean_days": days, "caps": caps}


def storage_clear(kinds=None, older_than_days=None, confirm: bool = False,
                  dry_run: bool = False,
                  abort: _t.Callable[[], bool] | None = None) -> dict:
    """ENGINE COMMAND ``storage_clear``: delete the named caches' files
    (every cache when ``kinds`` is empty — never a KEPT store), or with
    ``older_than_days`` only those not used for that long.  ``dry_run``
    deletes nothing and answers what would go; otherwise ``confirm`` is
    required.

    :returns: ``{"freed_bytes", "files", "kinds": {kind: bytes},
        "dry_run", "stopped"}``
    """
    stores = _check_clear({"kinds": kinds, "older_than_days": older_than_days,
                           "confirm": confirm, "dry_run": dry_run})
    now = time.time()
    cutoff = None if older_than_days is None else (
        now - float(older_than_days) * 86400.0)
    reason = ("cleared by hand" if cutoff is None else
              "cleared by hand, not used for %g days" % float(older_than_days))
    sweep = _Sweep(bool(dry_run), reason, abort)
    for store in stores:
        _clear_store(store, cutoff, sweep, now)
        if sweep.stopped:
            break
    return sweep.result()


def storage_auto_clean(days=None, caps=None, dry_run: bool = False,
                       abort: _t.Callable[[], bool] | None = None) -> dict:
    """ENGINE COMMAND ``storage_auto_clean``: the automatic cleanup —
    every cache file not used for ``days`` (the ``storage_auto_clean_days``
    setting; 0 is off), then each cache over its limit
    (``storage_cache_caps_gb``) evicted least recently used first, then,
    whatever the settings, the files nothing needs any more
    (``o4_engine.storage_redundant``: texture-cache copies of what built
    tiles hold, caches of airport packs no longer installed), then the
    one disk budget (``storage_budget.hold``; when it is not set, the
    sharp imagery's own limit: the default budget is only measured).

    :returns: :func:`storage_clear`'s reply plus ``"ran"`` (False when both
        settings are off and nothing was redundant), ``"budget"``
        (``storage_budget.status``) and
        ``"ondemand_floor"`` (when it is not; ``_hold_ondemand_cap``) --
        what the apps' after-build warning reads
        (``O4_Storage_Text.cleanup_warning``)
    """
    set_days, set_caps = _settings()
    days = set_days if days is None else float(days)
    caps = set_caps if caps is None else caps
    sweep = _Sweep(bool(dry_run), "automatic cleanup", abort)
    now = time.time()
    if days > 0:
        for store in _caches(()):
            _clear_store(store, now - days * 86400.0, sweep, now)
            if sweep.stopped:
                break
    for kind, cap in caps.items():
        if sweep.stopped:
            break
        _evict_to_cap(_BY_KIND[kind], int(cap), sweep, now)
    if not sweep.stopped:
        _remove_redundant(sweep, now)
    budget = ondemand = None
    if not sweep.stopped:
        # The one disk budget (RULINGS 2026-11-10d), else the sharp
        # imagery's own limit.
        from . import storage_budget as TOTAL
        budget = TOTAL.hold(sweep, now)
        # The default budget (none set) clears nothing unasked (11a).
        if budget is None or not budget.get("budget_set"):
            ondemand = _hold_ondemand_cap(sweep, now)
    out = sweep.result()
    out["budget"], out["ondemand_floor"] = budget, ondemand
    out["ran"] = bool(days > 0 or caps or out["files"])
    return out


#: The commands ``library.start`` runs for this module, and the check each
#: makes on the read loop (the shape of ``library._COMMANDS``).
COMMANDS: dict = {
    "storage_scan": (storage_scan, None),
    "storage_clear": (storage_clear, _check_clear),
    "storage_auto_clean": (storage_auto_clean, None),
}
#: What a command must not do while a build runs; these also take
#: ``abort``, which the transport points at "a build is running".
REFUSED_WHILE_BUILDING = {"storage_clear": "deleting anything",
                          "storage_auto_clean": "cleaning up storage"}
