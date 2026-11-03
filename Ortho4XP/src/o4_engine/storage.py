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

__all__ = ["CACHE", "KEPT", "STORES", "AUTO_CLEAN_DAYS", "CAPS_SETTING",
           "storage_scan", "storage_clear", "storage_auto_clean",
           "parse_caps", "COMMANDS", "REFUSED_WHILE_BUILDING"]

#: a store the user may clear: the next build downloads or rebuilds it
CACHE = "cache"
#: a store that is sized, never cleared here
KEPT = "kept"

#: the settings :func:`storage_auto_clean` reads (``O4_Cfg_Vars``)
AUTO_CLEAN_DAYS = "storage_auto_clean_days"
CAPS_SETTING = "storage_cache_caps_gb"

#: a file written this recently may be a download or a write in flight
IN_FLIGHT_SECONDS = 3600.0
#: a folder whose ``*.lock`` is younger than this is held by a build
LOCK_FRESH_SECONDS = 86400.0
#: the deletion log, under the data folder's ``logs``
LOG_NAME = "storage.log"

_PROTECTED_SUFFIXES = (".cfg", ".cfg.bak", ".anchor_bak", ".lock",
                       ".patch.osm", ".account.json", ".cookies.txt")


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


_AGAIN = " is downloaded again the next time a tile that needs it is built."
#: Every store, in the order the apps list them.
STORES: tuple = (
    Store("imagery", "Orthophotos", CACHE, "Imagery" + _AGAIN,
          lambda: FNAMES.Imagery_dir),
    Store("dds", "Texture cache (DDS)", CACHE,
          "Textures are converted again from the orthophotos when needed; "
          "an entry a built tile also holds frees nothing.",
          DDSC.cache_root),
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


def _files(store: Store, now: float):
    """``(path, stat, deletable)`` of every regular file of ``store``;
    a symlink is neither followed nor listed."""
    root = store.path()
    if not root or not os.path.isdir(root):
        return
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
            deletable = (store.policy == CACHE and not held
                         and not name.endswith(_PROTECTED_SUFFIXES)
                         and name != LOG_NAME
                         and now - st.st_mtime >= IN_FLIGHT_SECONDS)
            yield path, st, deletable


def _measure(store: Store, now: float) -> dict:
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

    def delete(self, store: Store, path: str, st: os.stat_result) -> int:
        size = DISK.freeable_bytes(path, st)
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


def _prune_empty_dirs(root: str) -> None:
    for folder, _dirs, _names in os.walk(root, topdown=False):
        if folder != root:
            try:
                os.rmdir(folder)            # only an empty folder goes
            except OSError:
                pass


def _clear_store(store: Store, cutoff: float | None, sweep: _Sweep,
                 now: float) -> None:
    for path, st, deletable in list(_files(store, now)):
        if sweep.abort():
            sweep.stopped = True
            return
        if deletable and (cutoff is None or _last_used(st) < cutoff):
            sweep.delete(store, path, st)
    if not sweep.dry_run:
        _prune_empty_dirs(store.path())


def _evict_to_cap(store: Store, cap: int, sweep: _Sweep, now: float) -> None:
    """Least recently used first until what the store holds is at most
    ``cap`` bytes; a protected file counts but is never evicted."""
    rows = list(_files(store, now))
    total = sum(DISK.freeable_bytes(path, st) for path, st, _d in rows)
    oldest_first = sorted((row for row in rows if row[2]),
                          key=lambda row: _last_used(row[1]))
    for path, st, _deletable in oldest_first:
        if total <= cap:
            break
        if sweep.abort():
            sweep.stopped = True
            break
        total -= sweep.delete(store, path, st)
    if not sweep.dry_run:
        _prune_empty_dirs(store.path())


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
def storage_scan() -> dict:
    """ENGINE COMMAND ``storage_scan``: every store with its freeable and
    apparent bytes, file count and last use (epoch seconds, None when
    empty), plus the two automatic-cleanup settings.

    :returns: ``{"root", "stores": [row, ...], "cache_bytes",
        "kept_bytes", "measured", "auto_clean_days", "caps"}``
    """
    now = time.time()
    rows = [_measure(store, now) for store in STORES]
    days, caps = _settings()
    root = FNAMES.current_data_root()
    return {"root": root, "stores": rows,
            "cache_bytes": sum(r["bytes"] for r in rows if r["policy"] == CACHE),
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
    (``storage_cache_caps_gb``) evicted least recently used first.

    :returns: :func:`storage_clear`'s reply plus ``"ran"`` (False when both
        settings are off: nothing was looked at)
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
    out = sweep.result()
    out["ran"] = bool(days > 0 or caps)
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
