"""Where Convert existing tiles keeps a LOCAL tile's own folder once the
World pack draws it (owner 2026-11-12T13:42Z):

    "if the folders are still there it looks like it didn't work. Can we
    not support undo/restore by moving the folders back out of the World
    folder if they want?"

A converted local entry (a real ``zOrtho4XP_<tile>`` folder in Custom
Scenery whose ``world_migrate`` journal state is ``done`` or ``dynamic``)
is MOVED into ``<work folder>/originals/<name>/`` (:func:`_put_away`: one
``os.rename``, the work folder sits beside Custom Scenery on the same
volume, so nothing is copied; the World pack's textures are hard links
and stay whole) and its ``scenery_packs.ini`` row is removed.  The
journal records ``original``; a ``config_dir`` that was the folder (the
cfg and imagery record the on-demand index, the rebuild and the Library
read) is repointed at its new place and the tile's index rows written
again there.  Undo (:func:`bring_back`) renames it back; ``world_retire``
"Free space…" deletes it from ``originals/``.  A link is never moved here.

Every step is idempotent and the place is fixed by the name, so a run
killed between the rename and the journal is finished by the next call:
the next Convert run settles every converted tile first, and
:func:`tidy` (``tools/ondemand_convert.py world-tidy-originals``) does the
same for an install converted before the folders moved.

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any, Dict, Optional

__all__ = ["ORIGINALS", "path_of", "try_put_away", "bring_back",
           "config_after_return", "home", "tidy"]

#: The folder of the work folder that keeps the converted local tiles.
ORIGINALS = "originals"
_CONVERTED = ("done", "dynamic")
_PREFIX = "zOrtho4XP_"


def path_of(work: str, name: str) -> str:
    """Where the entry ``name``'s folder is kept (fixed by its name)."""
    return os.path.join(work, ORIGINALS, name)


def _same(a: Optional[str], b: str) -> bool:
    return bool(a) and os.path.realpath(a) == os.path.realpath(b)


def home(record: dict) -> Optional[str]:
    """The folder that holds the entry's files now: its kept folder, else
    its source; ``None`` when neither is there."""
    for folder in (record.get("original"), record.get("source")):
        if folder and os.path.isdir(folder):
            return folder
    return None


def _drop_row(scenery_dir: str, name: str) -> None:
    import O4_Scenery_Packs as SP
    path = os.path.join(scenery_dir, SP.INI_FILENAME)
    if not os.path.isfile(path):
        return
    lines, newline = SP.read_ini_lines(path)
    if SP.remove_rows(lines, [name]):
        SP.write_ini_lines(path, lines, newline)


def _reindex(scenery_dir: str, name: str, folder: str,
             index: Optional[str]) -> None:
    """The tile's on-demand index rows written again from ``folder``
    (forgotten first: a row names its build folder)."""
    import O4_World_Pack as WP

    from . import imagery_ondemand as ONDEMAND
    from . import world_commands as WORLD
    from . import world_migrate as MIGRATE
    lat, lon = WP.parse_tile(name[len(_PREFIX):])
    with contextlib.suppress(Exception):     # the index is a cache
        ONDEMAND.forget_tile(WP.tile_name(lat, lon), index)
    MIGRATE._index(folder, lat, lon, WORLD.pack_dir(scenery_dir), index)


def _put_away(scenery_dir: str, name: str, journal, *,
             index: Optional[str] = None,
             lock=None) -> Optional[str]:
    """Move a converted local entry's folder into ``originals/`` and
    settle the journal, the index and the ini (module doc).  The kept
    folder, or ``None`` (a link, a tile not converted, nothing there).
    ``OSError`` when the folder cannot move (the name is taken there, or
    another volume); it then stays as it was.  ``lock`` guards the ini
    against a parallel run's writes."""
    record = journal.get(name) or {}
    if record.get("state") not in _CONVERTED or record.get("purged"):
        return None
    here = os.path.join(scenery_dir, name)
    kept = path_of(os.path.dirname(journal.path), name)
    if os.path.islink(here):
        return None
    if os.path.isdir(here):
        if os.path.lexists(kept):
            raise OSError(f"{name}: {kept} already exists; the folder stays "
                          "in Custom Scenery.")
        os.makedirs(os.path.dirname(kept), exist_ok=True)
        os.rename(here, kept)                    # same volume: no copy
    elif not os.path.isdir(kept):
        return None
    config = record.get("config_dir")
    moved = _same(config, here) and not _same(config, kept)
    journal.set(name, original=kept,
                **({"config_dir": kept} if moved else {}))
    if moved and record.get("state") == "done":
        _reindex(scenery_dir, name, kept, index)
    with (lock or contextlib.nullcontext()):
        _drop_row(scenery_dir, name)
    return kept


def try_put_away(scenery_dir: str, name: str, journal, *,
                 index: Optional[str] = None, lock=None) -> Optional[str]:
    """:func:`_put_away`; a folder that cannot move stays where it is
    (its row disabled) and the reason goes in its journal record
    (``kept_in_place``), returned."""
    try:
        _put_away(scenery_dir, name, journal, index=index, lock=lock)
    except OSError as error:
        journal.set(name, kept_in_place=str(error))
        return str(error)
    return None


def bring_back(scenery_dir: str, name: str, work: str) -> bool:
    """Undo's move: the kept folder renamed back into Custom Scenery.
    True when the entry is in Custom Scenery afterwards.  ``OSError``
    when Custom Scenery has something else of that name (nothing moves)."""
    here = os.path.join(scenery_dir, name)
    kept = path_of(work, name)
    if os.path.isdir(kept) and not os.path.islink(kept):
        if os.path.lexists(here):
            raise OSError(f"Custom Scenery already has {name}; its folder "
                          f"stays in {kept}.")
        os.rename(kept, here)
    return os.path.lexists(here)


def config_after_return(record: dict, scenery_dir: str, name: str,
                        work: str) -> Optional[str]:
    """The record's ``config_dir`` once :func:`bring_back` moved the
    folder home (it was repointed at the kept folder)."""
    config = record.get("config_dir")
    if config and _same(config, path_of(work, name)):
        return os.path.join(scenery_dir, name)
    return config


def tidy(scenery_dir: str, *, dry_run: bool = True,
         work_dir: Optional[str] = None,
         index: Optional[str] = None) -> Dict[str, Any]:
    """Move every converted local entry still in Custom Scenery into
    ``originals/`` (an install converted before the folders moved), and
    settle any a killed run left half done.  ``{"dry_run", "moved"
    (names; those that would move in the dry run), "settled" (already
    kept, journal or ini finished), "failed" ([{"name", "problems"}]),
    "summary"}``.  Refused while X-Plane runs."""
    from . import world_commands as WORLD
    from . import world_migrate as MIGRATE
    if not dry_run and MIGRATE._xplane_running():
        raise ValueError("Quit X-Plane first: tile folders move only while "
                         "it is closed.")
    WORLD.refuse_foreign(scenery_dir)
    work = work_dir or MIGRATE.work_dir_for(scenery_dir)
    journal = MIGRATE.Journal(work)
    out: Dict[str, Any] = {"dry_run": bool(dry_run), "moved": [],
                           "settled": [], "failed": []}
    import O4_Scenery_Packs as SP
    enabled, disabled = SP.parse_ini(os.path.join(scenery_dir,
                                                  SP.INI_FILENAME))
    rows = set(enabled) | disabled
    with MIGRATE.active_run():
        for name, record in sorted(journal.records.items()):
            if record.get("state") not in _CONVERTED or record.get("purged"):
                continue
            here = os.path.join(scenery_dir, name)
            if os.path.isdir(here) and not os.path.islink(here):
                key = "moved"
            elif os.path.isdir(path_of(work, name)) and (
                    record.get("original") != path_of(work, name)
                    or name in rows):
                key = "settled"
            else:
                continue
            if not dry_run:
                try:
                    _put_away(scenery_dir, name, journal, index=index)
                except OSError as error:
                    out["failed"].append({"name": name,
                                          "problems": [str(error)]})
                    continue
            out[key].append(name)
    if not dry_run:
        WORLD.write_log({"tidy_originals": len(out["moved"]),
                         "failed": len(out["failed"])})
    return {**out, "summary": _summary(out, work)}


def _summary(out: Dict[str, Any], work: str) -> str:
    verb = "Would move" if out["dry_run"] else "Moved"
    text = (f"{verb} {len(out['moved']):,} converted tile folders out of "
            f"Custom Scenery into {os.path.join(work, ORIGINALS)}")
    if out["settled"]:
        text += f"; {len(out['settled']):,} already there finished"
    text += "."
    if out["failed"]:
        text += (f" {len(out['failed']):,} stay where they are: "
                 + "; ".join(f"{f['name']} ({f['problems'][0]})"
                             for f in out["failed"][:5]) + ".")
    return text
