"""Move the per-tile ortho packs a Custom Scenery folder already has into
the World pack (flight manager / World spec §13 M1, phase M; capability
``world_migrate``).

Each ``zOrtho4XP_<tile>`` entry becomes a tile of the World pack
(``O4_World_Pack``: per-tile ``terrain/<tile>/`` and ``textures/<tile>/``,
the DSF's definitions given the subfolder by the BINARY relayout):

* a LINK onto a library volume gets an on-demand copy first, through the
  P1c converter (``O4_Imagery_OnDemand_Convert``: placeholders cut from
  the library's own full DDS, ``terrain/``, the manifest naming the
  library folder as the full textures' home) in this module's work
  folder.  The library volume is only read (owner 2026-11-10: "Leave
  files where they are on Thunderblade for now"); the link stays where
  it is;
* a LOCAL folder (or a P1c copy already converted in place) is laid out
  as it is: its textures are hard-linked into the pack.

A 7z-compressed DSF is unpacked first (``O4_DSF_Compress.unpack``).  The
relaid tile is staged, verified and swapped in (``O4_World_Pack``, rules
S1/S2), its on-demand index rows re-registered at the pack's folders,
and only then is the entry's ``scenery_packs.ini`` row set to
``SCENERY_PACK_DISABLED``.  The row is retired, not removed: an entry
left in Custom Scenery with no row is listed again, enabled, by X-Plane
at its next start and by the app's own tidy, which would draw the tile
twice.  The entry itself is never touched or deleted, so :func:`revert`
only enables the row again and gives the World tile back.

One tile is one step, journalled (:class:`Journal`, in the work folder):
a run killed anywhere leaves each tile drawn by its entry, or by the
World pack and (until the next run retires the row) its entry with the
same imagery -- never by none.  The next run finishes what the journal
says is half done; a finished tile is a no-op.  ``scenery_packs.ini`` is
copied into ``ini_backups/`` before a run changes a row.

X-Plane must be closed to migrate or revert (the converter's rule).  The
dry run (``world_migrate_size``) writes nothing in Custom Scenery.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

import O4_DSF_Compress as DSFC
import O4_Imagery_OnDemand_Convert as CONVERT
import O4_World_Pack as WP

from . import world_retire as RETIRE
from .imagery_convert import sibling_work_dir
from .xplane_root import xplane_running as _xplane_running

__all__ = ["WORK_DIR_NAME", "Journal", "work_dir_for", "entries",
           "classify", "migrate", "migrate_tile", "revert", "summary",
           "stop", "run_command", "start_world_migrate", "stopping",
           "STOPPED_MEASURE", "active", "active_run", "missing_from_pack",
           "pack_missing_sentence"]

#: Beside the Custom Scenery folder (same volume, so textures hard-link;
#: X-Plane does not scan it): the journal, the on-demand copies of linked
#: tiles, staging, and the ini backups.
WORK_DIR_NAME = "XPTerrainBuilder_world_migrate"
_JOURNAL = "journal.json"
_TILE_PREFIX = "zOrtho4XP_"
_STOP = threading.Event()
_RUN = threading.Lock()
#: Runs that change scenery_packs.ini or the World pack now in progress
#: (migrate, revert, Free space, ``world_rechoose``): ``tidy_scenery_packs``
#: waits for them (:func:`active`), so its read-modify-write of the ini
#: cannot undo a row this run just disabled.
_ACTIVE = [0]
_ACTIVE_LOCK = threading.Lock()
#: Journal states of a tile the World pack draws.
_CONVERTED = ("done", "dynamic")


@contextlib.contextmanager
def active_run():
    """Mark a run that changes the ini or the World pack (:func:`active`)."""
    with _ACTIVE_LOCK:
        _ACTIVE[0] += 1
    try:
        yield
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE[0] -= 1


def active() -> bool:
    """Is a migration, revert, Free space or rechoose running now?"""
    return _ACTIVE[0] > 0


def work_dir_for(scenery_dir: str) -> str:
    """The work folder of a Custom Scenery folder."""
    return sibling_work_dir(scenery_dir, WORK_DIR_NAME)


class Journal:
    """``{entry name: record}`` of the tiles a migration has touched,
    rewritten atomically on every change (``state``: ``staging`` ->
    ``swapped`` -> ``done``; ``prior``: what the World pack had there)."""

    def __init__(self, work: str):
        self.path = os.path.join(work, _JOURNAL)
        self._lock = threading.Lock()
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = {}
        self.records: Dict[str, dict] = data if isinstance(data, dict) else {}

    def get(self, name: str) -> Optional[dict]:
        return self.records.get(name)

    def set(self, name: str, **fields) -> dict:
        with self._lock:
            record = {**self.records.get(name, {}), **fields,
                      "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            self.records[name] = record
            self._save()
            return record

    def drop(self, name: str) -> None:
        with self._lock:
            self.records.pop(name, None)
            self._save()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temp = f"{self.path}.{os.getpid()}.part"
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.records, handle, indent=1, sort_keys=True)
        os.replace(temp, self.path)


def entries(scenery_dir: str, names=None) -> list:
    """The ``zOrtho4XP_<tile>`` entries (``imagery_convert``'s reading:
    kind ``link``, ``link-unmounted``, ``dir`` or ``converted``)."""
    from .imagery_convert import _entries
    return _entries(scenery_dir, names)


def classify(entry, journal: Journal, pack: str) -> str:
    """What a migration does with ``entry``: ``migrated`` (journal done),
    ``dynamic`` (made dynamic, ``world_retire``), ``resume`` (half done),
    ``copy`` (a link: on-demand copy, then stage), ``stage`` (local), or
    ``skip: <why>``."""
    record = journal.get(entry.name)
    if record:
        state = record.get("state")
        return {"done": "migrated", "dynamic": "dynamic"}.get(state, "resume")
    if entry.kind == "link-unmounted":
        return "skip: library not mounted"
    if not entry.enabled:
        return "skip: disabled in scenery_packs.ini"
    held = WP.kind_of(os.path.join(pack, WP.dsf_relpath(entry.lat, entry.lon)))
    if held not in (None, "placeholder"):
        return "skip: the World pack already has this tile"
    return "copy" if entry.kind == "link" else "stage"


# ------------------------------------------------------------ one tile


def _ondemand_copy(entry, lean_root: str, px: int, threads: int) -> dict:
    """The P1c on-demand copy of a linked tile in ``lean_root`` (kept when
    already finished), WITHOUT its DSF: the World pack gets the relaid
    DSF.  ``{"dir", "bytes_written", "problems"}``."""
    final = os.path.join(lean_root, entry.name)
    if CONVERT.is_converted(final, entry.source, px):
        CONVERT.backfill(final)         # a copy older than its masks/field
        return {"dir": final, "bytes_written": 0, "problems": []}
    staged = os.path.join(lean_root, ".staging", entry.name)
    plan = CONVERT.plan_tile(entry.source, px)
    plan.dsfs = []
    done = CONVERT.convert_tile(plan, staged, entry.tile,
                                full_source=entry.source, threads=threads)
    if not done["problems"]:
        if os.path.lexists(final):
            shutil.rmtree(final)
        os.rename(staged, final)
    return {"dir": final, **done}


def _view(folder: str, files_from: str, dsf_source: str, lat: int,
          lon: int) -> str:
    """A tile folder for ``relayout_tile``: ``terrain`` and ``textures``
    linked to ``files_from``'s, the DSF unpacked (a 7z) or linked to
    ``dsf_source`` (uncompressed)."""
    if os.path.lexists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    for sub in ("terrain", "textures"):
        if os.path.isdir(os.path.join(files_from, sub)):
            os.symlink(os.path.join(files_from, sub), os.path.join(folder, sub))
    dsf = os.path.join(folder, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf))
    if DSFC.is_compressed(dsf_source):
        DSFC.unpack(dsf_source, dsf)
    else:
        os.symlink(dsf_source, dsf)
    return folder


def _prepare(entry, work: str, px: int, threads: int) -> dict:
    """``{"view", "config_dir", "bytes_written", "problems"}``: the folder
    to relayout and the folder whose imagery manifest the index reads."""
    source_dsf = os.path.join(entry.source, WP.dsf_relpath(entry.lat, entry.lon))
    if not os.path.isfile(source_dsf):
        return {"problems": [f"no DSF in {entry.source}"]}
    files_from, written = entry.source, 0
    if entry.kind == "link":
        copy = _ondemand_copy(entry, os.path.join(work, "lean"), px, threads)
        if copy["problems"]:
            return {"problems": copy["problems"][:5]}
        files_from, written = copy["dir"], copy["bytes_written"]
    if files_from == entry.source and not DSFC.is_compressed(source_dsf):
        view = entry.source
    else:
        view = _view(os.path.join(work, "views", entry.name), files_from,
                     source_dsf, entry.lat, entry.lon)
    return {"view": view, "config_dir": files_from,
            "bytes_written": written, "problems": []}


def _manifest(folder: str, lat: int, lon: int) -> dict:
    path = os.path.join(folder,
                        f"Ortho4XP_{WP.tile_name(lat, lon)}_imagery.json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _index(config_dir: str, lat: int, lon: int, pack: Optional[str],
           index: Optional[str]) -> int:
    """Point an on-demand tile's manifest and index rows at the pack's
    folders (``pack`` None: back at its own); rows written."""
    record = _manifest(config_dir, lat, lon)
    if not (record.get("on_demand") or record.get("pinned")):
        return 0
    from . import imagery_ondemand as ONDEMAND
    from .world_publish import write_layout
    write_layout(config_dir, lat, lon, pack)
    try:
        return ONDEMAND.register_tiles([(config_dir, lat, lon)], index)
    except Exception:                       # the index is a cache
        return 0


def _set_row(scenery_dir: str, name: str, enabled: bool) -> bool:
    """The entry's row enabled or disabled; a row another program dropped
    is filed again first (a row is disabled, never removed: X-Plane lists
    an entry with no row again, ENABLED, at its next start)."""
    import O4_Scenery_Packs as SP
    path = os.path.join(scenery_dir, SP.INI_FILENAME)
    lines, newline = SP.read_ini_lines(path, missing_ok=True)
    changed = SP.set_rows_enabled(lines, [name], enabled, insert_kind="ortho")
    if changed:
        SP.write_ini_lines(path, lines, newline)
    return bool(changed)


def _stage_and_swap(entry, record: dict, *, pack: str, work: str,
                    journal: Journal, swap_lock: threading.Lock, px: int,
                    threads: int) -> dict:
    """Steps 1-3 of a tile: prepare, stage + verify, swap in (S1/S2).
    The journal's record after the swap, or ``{"problems"}``."""
    lat, lon = entry.lat, entry.lon
    prep = _prepare(entry, work, px, threads)
    if prep["problems"]:
        return {"problems": prep["problems"]}
    staging = os.path.join(work, "staging")
    staged = WP.publish(pack, prep["view"], lat, lon, staging_root=staging,
                        loaded=lambda la, lo: True)
    shutil.rmtree(os.path.join(work, "views", entry.name), ignore_errors=True)
    if staged["state"] != "staged":
        return {"problems": staged["problems"][:5]}
    folder = os.path.join(staging, WP.tile_name(lat, lon))
    with swap_lock:
        WP.swap_in(pack, folder, lat, lon)
        shutil.rmtree(folder, ignore_errors=True)
        return journal.set(entry.name, state="swapped",
                           config_dir=prep["config_dir"],
                           bytes_written=prep["bytes_written"])


def migrate_tile(entry, *, scenery_dir: str, pack: str, work: str,
                 journal: Journal, swap_lock: threading.Lock,
                 px: int = CONVERT.DEFAULT_PX, threads: int = 4,
                 ini: bool = True, index: Optional[str] = None,
                 register: bool = True) -> dict:
    """Move one entry into ``pack`` (see the module docstring); the row of
    the result.  ``ini``/``register`` False (the dry run's timing sample)
    leave ``scenery_packs.ini`` and the index alone."""
    started = time.monotonic()
    action = classify(entry, journal, pack)
    out = {"name": entry.name, "kind": entry.kind, "action": action}
    if action == "migrated" or action.startswith("skip"):
        return {**out, "status": action}
    record = journal.get(entry.name) or journal.set(
        entry.name, state="staging", kind=entry.kind, source=entry.source,
        prior=WP.kind_of(os.path.join(pack, WP.dsf_relpath(entry.lat,
                                                           entry.lon))))
    if record.get("state") == "staging":
        record = _stage_and_swap(entry, record, pack=pack, work=work,
                                 journal=journal, swap_lock=swap_lock,
                                 px=px, threads=threads)
        if "problems" in record:
            journal.set(entry.name, problems=record["problems"])
            return {**out, "status": "failed", "problems": record["problems"]}
    if register:
        out["index_rows"] = _index(record["config_dir"], entry.lat,
                                   entry.lon, pack, index)
    if ini:
        with swap_lock:
            _set_row(scenery_dir, entry.name, enabled=False)
        journal.set(entry.name, state="done", problems=[])
    return {**out, "status": "migrated",
            "bytes_written": record.get("bytes_written", 0),
            "seconds": round(time.monotonic() - started, 2)}


# ------------------------------------------------------------- the run


def _backup_ini(scenery_dir: str, work: str) -> Optional[str]:
    source = os.path.join(scenery_dir, "scenery_packs.ini")
    if not os.path.isfile(source):
        return None
    folder = os.path.join(work, "ini_backups")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, "scenery_packs.ini." + time.strftime(
        "%Y%m%dT%H%M%SZ", time.gmtime()))
    shutil.copy2(source, dest)
    return dest


def _ready_pack(scenery_dir: str) -> str:
    """The World pack, installed (``world_install``) if it is not yet."""
    from . import world_commands as WORLD
    if not WORLD.managed(scenery_dir) or not WORLD._ini_has_row(scenery_dir):
        WORLD.world_install(scenery_dir)
    return WORLD.pack_dir(scenery_dir)


def _counts(rows) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        key = row["status"].split(":")[0]
        counts[key] = counts.get(key, 0) + 1
    return counts


def _one_tile(entry, choice: str, custom, disabled, **kw) -> dict:
    """One entry under ``choice`` (``world_retire``): moved as it is,
    made dynamic, or left (``migrate_tile``'s skip row).  Refused
    (``ValueError``) once the World pack's folder is gone mid-run: a tile
    written into a folder X-Plane does not list is drawn by nothing."""
    from . import world_commands as WORLD
    if not WORLD.managed(kw["scenery_dir"]):
        raise ValueError(f"The World pack is gone ({kw['pack']}): "
                         f"{entry.name} was left as it is.")
    action = classify(entry, kw["journal"], kw["pack"])
    record = kw["journal"].get(entry.name)
    # a half-done tile finishes the way it started, whatever the choice
    if (record.get("state") in RETIRE.DYNAMIC_STATES if record
            else RETIRE.fate(entry, action, choice, custom, disabled)
            == "dynamic"):
        if action == "dynamic":
            return {"name": entry.name, "kind": entry.kind,
                    "action": action, "status": "dynamic"}
        return RETIRE.retire_tile(
            entry, scenery_dir=kw["scenery_dir"], pack=kw["pack"],
            journal=kw["journal"], swap_lock=kw["swap_lock"],
            set_row=_set_row, index=kw.get("index"))
    return migrate_tile(entry, **kw)


def migrate(scenery_dir: str, names=None, *, px: int = CONVERT.DEFAULT_PX,
            workers: int = 4, threads: int = 4, work_dir: Optional[str] = None,
            index: Optional[str] = None, choice: str = RETIRE.KEEP_ALL,
            progress: Optional[Callable[[int, int, str], None]] = None
            ) -> Dict[str, Any]:
    """Migrate every entry (or ``names``), ``workers`` tiles at a time,
    under ``choice`` (``world_retire.CHOICES``; ``keep_all`` moves every
    tile as it is).  Refused while X-Plane runs.  ``{"rows", "counts",
    "ini_backup", "seconds", "stopped", "choice", "pack_missing"}``
    (``pack_missing``: the converted tiles the World pack lacks after the
    run, :func:`missing_from_pack`; Undo gives them back).  A tile that
    fails keeps its reasons in its journal record (``problems``)."""
    if choice not in RETIRE.CHOICES:
        raise ValueError(f"world_migrate: unknown choice {choice!r}.")
    if _xplane_running():
        raise ValueError("Quit X-Plane first: tiles move into the World "
                         "pack only while it is closed.")
    from . import world_commands as WORLD
    WORLD.refuse_foreign(scenery_dir)
    _STOP.clear()
    with active_run():
        return _migrate(scenery_dir, names, px=px, workers=workers,
                        threads=threads, work_dir=work_dir, index=index,
                        choice=choice, progress=progress)


def _migrate(scenery_dir: str, names, *, px: int, workers: int,
             threads: int, work_dir: Optional[str], index: Optional[str],
             choice: str, progress) -> Dict[str, Any]:
    """The work of :func:`migrate`."""
    from . import world_commands as WORLD
    work = work_dir or work_dir_for(scenery_dir)
    os.makedirs(work, exist_ok=True)
    pack = _ready_pack(scenery_dir)
    journal, lock = Journal(work), threading.Lock()
    found = entries(scenery_dir, names)
    custom = (RETIRE.custom_airport_tiles(scenery_dir)
              if choice == RETIRE.KEEP_CUSTOM else {})
    disabled = RETIRE.disabled_names(scenery_dir)
    backup = _backup_ini(scenery_dir, work)
    started, done = time.monotonic(), [0]

    def one(entry) -> dict:
        if _STOP.is_set():
            return {"name": entry.name, "kind": entry.kind, "status": "stopped"}
        try:
            row = _one_tile(entry, choice, custom, disabled,
                            scenery_dir=scenery_dir,
                            pack=pack, work=work, journal=journal,
                            swap_lock=lock, px=px, threads=threads,
                            index=index)
        except (OSError, ValueError, DSFC.CompressError) as error:
            row = {"name": entry.name, "kind": entry.kind,
                   "status": "failed", "problems": [str(error)]}
            if journal.get(entry.name):     # the reason stays with the tile
                journal.set(entry.name, problems=row["problems"])
        with lock:
            done[0] += 1
            if progress:
                progress(done[0], len(found), entry.name)
        return row
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        rows = list(pool.map(one, found))
    missing = missing_from_pack(scenery_dir, work_dir=work)
    WORLD.write_log({"migrate": _counts(rows), "choice": choice,
                     "scenery_dir": scenery_dir, "pack_missing": len(missing)})
    return {"rows": rows, "counts": _counts(rows), "ini_backup": backup,
            "seconds": round(time.monotonic() - started, 1),
            "stopped": _STOP.is_set(), "choice": choice,
            "pack_missing": len(missing)}


def missing_from_pack(scenery_dir: str, kinds: Optional[dict] = None, *,
                      work_dir: Optional[str] = None) -> list:
    """The journalled entries the World pack should draw (state ``done``
    or ``dynamic``) whose DSF it lacks -- every one of them when the pack
    itself is gone (not :func:`world_commands.managed`).  ``kinds``: the
    pack's ``WP.world_tiles`` when the caller has it.  A tile listed here
    is drawn by nothing until Undo gives it back its own pack (the
    2026-11-11 incident: the World folder trashed mid-run)."""
    from . import world_commands as WORLD
    path = os.path.join(work_dir or work_dir_for(scenery_dir), _JOURNAL)
    if not os.path.isfile(path):
        return []
    converted = sorted(name for name, record in Journal(
        os.path.dirname(path)).records.items()
        if record.get("state") in _CONVERTED)
    if not converted:
        return []
    if not WORLD.managed(scenery_dir):
        return converted
    if kinds is None:
        kinds = WP.world_tiles(WORLD.pack_dir(scenery_dir))
    out = []
    for name in converted:
        try:
            tile = WP.parse_tile(name[len(_TILE_PREFIX):])
        except ValueError:
            continue
        if tile not in kinds:
            out.append(name)
    return out


def _give_back(pack: str, lat: int, lon: int, prior: Optional[str]) -> None:
    """The World pack as it was before the tile came: its placeholder
    (or no DSF), and its folders removed (X-Plane is closed).  A pack
    whose folder is gone is not made again by a placeholder."""
    if not os.path.isdir(pack):
        return
    if prior == "placeholder":
        WP.swap_out(pack, lat, lon)
    else:
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(pack, WP.dsf_relpath(lat, lon)))
    for sub in ("terrain", "textures"):
        shutil.rmtree(os.path.join(pack, sub, WP.tile_name(lat, lon)),
                      ignore_errors=True)


def _revert_one(scenery_dir: str, pack: str, name: str, record: dict,
                index: Optional[str]) -> bool:
    """Undo one journalled entry; False when it cannot come back (a
    dynamic local tile Free space removed)."""
    if record.get("state") in RETIRE.DYNAMIC_STATES:
        back = RETIRE.restore_tile(scenery_dir, pack, name, record, _set_row)
        if back and record.get("kind") not in ("link", "link-unmounted"):
            lat, lon = WP.parse_tile(name[len(_TILE_PREFIX):])
            _index(os.path.join(scenery_dir, name), lat, lon, None, index)
        return back
    lat, lon = WP.parse_tile(name[len(_TILE_PREFIX):])
    _set_row(scenery_dir, name, enabled=True)
    if record.get("state") in ("swapped", "done"):
        _give_back(pack, lat, lon, record.get("prior"))
    if record.get("config_dir"):
        from . import imagery_ondemand as ONDEMAND
        with contextlib.suppress(Exception):     # the index is a cache
            ONDEMAND.forget_tile(WP.tile_name(lat, lon), index)
        if record.get("kind") != "link":
            _index(record["config_dir"], lat, lon, None, index)
    return True


def revert(scenery_dir: str, names=None, *, work_dir: Optional[str] = None,
           index: Optional[str] = None) -> Dict[str, Any]:
    """Undo the migration of every journalled entry (or ``names``): its
    row enabled again, its World tile given back, its index rows at its
    own folder; a tile made dynamic gets its link or its row back
    (``world_retire.restore_tile``).  The on-demand copies stay (a later
    run reuses them).  Refused while X-Plane runs.  ``{"reverted":
    [names], "gone": [names]}`` (``gone``: dynamic local tiles Free space
    removed; they stay dynamic)."""
    if _xplane_running():
        raise ValueError("Quit X-Plane first: tiles leave the World pack "
                         "only while it is closed.")
    from . import world_commands as WORLD
    WORLD.refuse_foreign(scenery_dir)
    journal = Journal(work_dir or work_dir_for(scenery_dir))
    pack = WORLD.pack_dir(scenery_dir)
    wanted = set(names) if names else None
    reverted, gone = [], []
    with active_run():
        for name, record in sorted(journal.records.items()):
            if wanted is not None and name not in wanted:
                continue
            if _revert_one(scenery_dir, pack, name, record, index):
                journal.drop(name)
                reverted.append(name)
            else:
                gone.append(name)
    WORLD.write_log({"migrate_revert": len(reverted), "gone": len(gone)})
    return {"reverted": reverted, "gone": gone}


def _free_space(scenery_dir: str, names=None, *,
               work_dir: Optional[str] = None) -> Dict[str, Any]:
    """"Free space…": delete the local entries made dynamic
    (``world_retire.purge``); Undo can no longer bring them back.
    Refused while X-Plane runs.  ``{"removed": [names], "freed_bytes"}``."""
    if _xplane_running():
        raise ValueError("Quit X-Plane first: tiles are removed only while "
                         "it is closed.")
    from . import world_commands as WORLD
    WORLD.refuse_foreign(scenery_dir)
    journal = Journal(work_dir or work_dir_for(scenery_dir))
    with active_run():
        out = RETIRE.purge(scenery_dir, journal.records, names)
        for name in out["removed"]:
            journal.set(name, purged=True)
    WORLD.write_log({"migrate_free_space": len(out["removed"]),
                     "freed_bytes": out["freed_bytes"]})
    return out


# ------------------------------------------------------------ command


#: The dry run's sentence when Cancel stopped it (nothing was moved).
STOPPED_MEASURE = "Measuring cancelled: nothing was moved."


def _count_events(emit: Callable[[Any], None], phase: str,
                    every: float = 0.2):
    """A ``progress(done, total, name)`` that emits a
    ``WorldMigrateProgress`` of ``phase`` at most every ``every`` s (the
    first and the last always)."""
    from .events import WorldMigrateProgress
    last = [None]
    lock = threading.Lock()

    def progress(done: int, total: int, name: str) -> None:
        now = time.monotonic()
        with lock:
            if last[0] is not None and now - last[0] < every and done < total:
                return
            last[0] = now
        emit(WorldMigrateProgress(phase=phase, done=int(done),
                                  total=int(total), tile=name or ""))
    return progress


def _progress_events(emit: Callable[[Any], None], scenery_dir: str):
    """A ``progress(done, total, name)`` for a migration: the
    ``WorldMigrateProgress`` count, and a ``WorldStatus`` (state
    ``building``) at most every 2 s."""
    from . import world_commands as WORLD
    last = [0.0]
    count = _count_events(emit, "move")

    def progress(done: int, total: int, name: str) -> None:
        count(done, total, name)
        now = time.monotonic()
        if now - last[0] < 2.0 and done < total:
            return
        last[0] = now
        emit(WORLD.status_event(
            scenery_dir, state="building",
            reason=f"Moving tiles into the World pack: {done:,} of {total:,}"))
    return progress


def _duration(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 90:
        return f"about {minutes} min"
    return f"about {minutes / 60:.1f} h"


def summary(action: str, result: Dict[str, Any]) -> str:
    """The one sentence both apps show for a ``world_migrate`` result
    (``action``: ``dry_run``, ``migrate`` or ``revert``)."""
    if action == "revert":
        text = (f"Put {len(result['reverted']):,} tiles back in their own "
                "packs.")
        if result.get("gone"):
            text += (f" {len(result['gone']):,} dynamic tiles were removed by "
                     "Free space and stay dynamic.")
        return text
    if action == "free_space":
        return (f"Removed {len(result['removed']):,} dynamic tiles from this "
                f"Mac, freeing {result['freed_bytes'] / 1e9:,.1f} GB.")
    if action == "migrate":
        c = result["counts"]
        text = (f"Moved {c.get('migrated', 0):,} tiles into the World pack"
                + (f", made {c['dynamic']:,} dynamic" if c.get("dynamic")
                   else "")
                + f"; {c.get('failed', 0):,} failed, {c.get('skip', 0):,} "
                "left as they are.")
        if result.get("stopped"):
            text += " Stopped: Convert again to finish."
        if result.get("pack_missing"):
            text += " " + pack_missing_sentence(result["pack_missing"])
        return text
    t = result["totals"]
    acts = t["by_action"]
    move = acts.get("copy", 0) + acts.get("stage", 0) + acts.get("resume", 0)
    left = sum(n for a, n in acts.items() if a.startswith("skip"))
    if not move:
        return (f"Nothing to move: {acts.get('migrated', 0):,} tiles are in "
                f"the World pack, {left:,} left as they are.")
    when = (_duration(t["seconds_est"]) if t.get("seconds_per_tile")
            else "an unknown time")
    return (f"{move:,} tiles can move into the World pack "
            f"({acts.get('copy', 0):,} on another drive get a local "
            f"on-demand copy; their files stay where they are). It needs "
            f"{t['new_bytes'] / 1e9:,.1f} GB on this drive and takes {when}. "
            f"{left:,} are left as they are; {acts.get('migrated', 0):,} "
            "were moved before.")


def pack_missing_sentence(count: int) -> str:
    """Both apps' sentence for ``count`` converted tiles the World pack
    lacks (:func:`missing_from_pack`; ``O4_Storage_Text``)."""
    import O4_Storage_Text as TEXT
    return TEXT.WORLD_PACK_MISSING.format(count=f"{int(count):,}")


def stop() -> None:
    """Ask a running migration (or dry run) to stop after the tiles in
    hand."""
    _STOP.set()


def stopping() -> bool:
    """Cancel was asked (``stop``) since the run began."""
    return _STOP.is_set()


def run_command(dry_run: bool, undo: bool = False, tiles=None,
                scenery_dir: str = "", workers: int = 4,
                emit: Optional[Callable[[Any], None]] = None,
                choice: str = RETIRE.KEEP_ALL,
                purge: bool = False) -> Dict[str, Any]:
    """The work of ``world_migrate`` on the caller's thread (the Qt window
    calls it on its own worker): the result with ``action``, ``summary``
    and the ``failed`` rows only.  ``emit`` receives the progress events:
    ``WorldMigrateProgress`` of the dry run and of a migration (whose
    ``WorldStatus`` it also receives).  The dry run answers every choice
    (``choices``); the migration runs ``choice``; ``purge`` is Free
    space (:func:`_free_space`)."""
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not scenery_dir or not os.path.isdir(scenery_dir):
        raise ValueError(f"No Custom Scenery folder ({scenery_dir!r}).")
    WORLD.refuse_foreign(scenery_dir)
    if dry_run and not purge:
        from .world_migrate_size import dry_run as size
        result = size(scenery_dir, tiles, workers=max(1, int(workers)) * 2,
                      progress=(_count_events(emit, "measure")
                                if emit else None))
        action = "dry_run"
    elif purge:
        result, action = _free_space(scenery_dir, tiles), "free_space"
    elif undo:
        result, action = revert(scenery_dir, tiles), "revert"
    else:
        result = migrate(scenery_dir, tiles, workers=max(1, int(workers)),
                         choice=choice or RETIRE.KEEP_ALL,
                         progress=(_progress_events(emit, scenery_dir)
                                   if emit else None))
        action = "migrate"
    # The apps show totals and the sentence; only failed rows travel.
    failed = [r for r in result.pop("rows", ())
              if str(r.get("status", "")).startswith("failed")]
    return {**result, "failed": failed, "action": action,
            "summary": summary(action, result)}


def start_world_migrate(emit: Callable[[Any], None], request: Any = None,
                        dry_run: bool = True, tiles=None, revert: bool = False,
                        stop: bool = False, scenery_dir: str = "",
                        workers: int = 4, choice: str = RETIRE.KEEP_ALL,
                        purge: bool = False, **_ignored) -> dict:
    """ENGINE COMMAND ``world_migrate`` (spec §5.2): the dry run (default,
    with every choice's figures), the migration under ``choice``
    (``world_retire.CHOICES``), with ``revert`` its undo, or with
    ``purge`` Free space, of ``tiles`` (entry names; all when omitted).
    Replies ``{"status": "started"}``; ``WorldReady``
    (``request`` = this command's id) carries the result.  ``stop`` asks
    a running migration to stop after the tiles in hand (it resumes on
    the next run) and replies ``{"status": "stopping"}``."""
    from . import world_commands as WORLD
    from .events import WorldReady
    if stop:
        _STOP.set()
        return {"status": "stopping"}
    if not _RUN.acquire(blocking=False):
        raise ValueError("world_migrate: a migration is already running.")

    def work() -> None:
        try:
            result = run_command(bool(dry_run), bool(revert), tiles,
                                 scenery_dir, workers, emit,
                                 choice=choice, purge=bool(purge))
        except Exception as error:            # the sentence goes to the app
            emit(WorldReady(request=request, result=None,
                            error=str(error) or repr(error)))
            return
        finally:
            _RUN.release()
        emit(WorldReady(request=request, result=result))
        if not dry_run:
            emit(WORLD.status_event(scenery_dir))
    threading.Thread(target=work, daemon=True, name="o4-world-migrate").start()
    return {"status": "started"}
