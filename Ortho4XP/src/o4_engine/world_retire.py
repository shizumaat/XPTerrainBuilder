"""The three choices of Convert existing tiles (owner 2026-11-11T15:32Z,
RULINGS 2026-11-11l item 4): keep every existing tile, keep the tiles
that hold a custom airport, or make everything DYNAMIC.

    "I would also like the option to retire the external drive in favor
    of our new on the fly tile creation ... keep all existing tiles - and
    require external drive (if applicable), keep full tiles that have
    custom airports, make everything dynamic."

* :data:`CHOICES` -- ``keep_all`` (every tile moves into the World pack
  as it is, ``world_migrate``; a tile on another drive keeps its full
  imagery there, so that drive stays required), ``keep_custom`` (the
  tiles with a custom airport move so, the rest become dynamic) and
  ``dynamic`` (every tile becomes dynamic).
* A CUSTOM AIRPORT tile (:func:`custom_airport_tiles`) is a tile holding
  an airport of an ENABLED installed airport pack in Custom Scenery
  (``O4_Custom_Scenery.iter_airport_packs``, the reading the Airports
  card and the patch library use; Global Airports is not one).
* A DYNAMIC tile (:func:`retire_tile`) is a World pack placeholder: the
  World job drapes it ahead in flight and the flight manager builds it on
  demand (spec §7, §8).  Its entry's ``scenery_packs.ini`` row is
  disabled, never removed (spec §13 M1).  A LINK entry (a tile on another
  drive) is removed from Custom Scenery -- the choice retires it, the
  dialog says so -- and its target is journalled, so Undo makes it again;
  the drive's files are never touched.  A LOCAL entry stays where it is
  (disabled) until :func:`purge` ("Free space…") deletes it; Undo brings
  it back until then.
* :func:`choice_totals` -- the dry run's figures for each choice, before
  anything moves: tiles kept and made dynamic, bytes this Mac gains back
  and bytes on each other drive no longer needed, the drives still
  needed and by how many tiles, and the dynamic tiles another tool built
  (they become our drape or build, not the same tile).

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import os
import shutil
from typing import Dict, Iterable, Optional

import O4_World_Pack as WP

__all__ = ["CHOICES", "KEEP_ALL", "KEEP_CUSTOM", "DYNAMIC", "DYNAMIC_STATES",
           "custom_airport_tiles", "disabled_names", "fate",
           "choice_totals",
           "choice_line", "retire_tile", "restore_tile", "purge"]

KEEP_ALL = "keep_all"
KEEP_CUSTOM = "keep_custom"
DYNAMIC = "dynamic"
#: The choices, in the order both apps list them.
CHOICES = (KEEP_ALL, KEEP_CUSTOM, DYNAMIC)
#: Journal states of a tile made dynamic (``retiring`` is half done).
DYNAMIC_STATES = ("retiring", "dynamic")
_MOVES = ("copy", "stage", "resume")
_LINKS = ("link", "link-unmounted")
_UNMOUNTED = "skip: library not mounted"


def custom_airport_tiles(scenery_dir: str) -> Dict[tuple, list]:
    """``{(lat, lon): [icao, …]}``: the tiles holding an airport of an
    enabled custom airport pack of ``scenery_dir``."""
    import O4_Custom_Scenery as SCENERY
    out: Dict[tuple, set] = {}
    for _name, _path, _root, enabled, airports in (
            SCENERY.iter_airport_packs(scenery_dir or "")):
        if not enabled:
            continue
        for apt in airports:
            if apt.lat is None or apt.lon is None:
                continue
            tile = (int(apt.lat // 1), int(apt.lon // 1))
            out.setdefault(tile, set()).add((apt.icao or "").upper())
    return {tile: sorted(codes) for tile, codes in out.items()}


def disabled_names(scenery_dir: str) -> set:
    """The entries whose ``scenery_packs.ini`` row is disabled (a link to
    a drive that is not connected included)."""
    import O4_Scenery_Packs as SP
    return SP.disabled_pack_names(scenery_dir)


def _drive_of(path: str) -> str:
    """The name of the volume ``path`` lies on (its mount point's name;
    for a volume that is not mounted, the first missing folder under the
    deepest one that exists -- ``/Volumes/<name>``); ``""`` for the
    system volume (this Mac)."""
    probe = os.path.abspath(path)
    while not os.path.exists(probe) and os.path.dirname(probe) != probe:
        child, probe = probe, os.path.dirname(probe)
        if os.path.exists(probe):
            return os.path.basename(child)
    while not os.path.ismount(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    return os.path.basename(probe)


def fate(entry, action: str, choice: str, custom,
         disabled=frozenset()) -> Optional[str]:
    """What ``choice`` does with one entry whose ``world_migrate`` action
    is ``action``: ``keep`` (moves into the World pack as it is),
    ``dynamic``, or ``None`` (left as it is: a row disabled in
    ``disabled``, or nothing to move)."""
    movable = action in _MOVES
    if not (movable or action == _UNMOUNTED) or entry.name in disabled:
        return None
    if choice == DYNAMIC or (choice == KEEP_CUSTOM
                             and (entry.lat, entry.lon) not in custom):
        return "dynamic"
    return "keep" if movable else None


def _entry_bytes(row: dict) -> int:
    """What the entry holds on its own drive: the DSF and the textures."""
    textures = row.get("library_texture_bytes" if row["kind"] == "link"
                       else "texture_bytes", 0)
    return int(textures or 0) + int(row.get("dsf_bytes") or 0)


def _built_here(entry) -> bool:
    import O4_Tile_Info as TINFO
    try:
        return TINFO.built_here(entry.source, entry.lat, entry.lon)
    except Exception:                     # an unreadable folder: not ours
        return False


def _add(table: dict, key: str, value: int) -> None:
    table[key] = table.get(key, 0) + value


def _tally_dynamic(t: dict, row: dict, entry, ours: dict) -> None:
    t["dynamic"] += 1
    if entry.kind in _LINKS:
        t["links_removed"] += 1
        drive = _drive_of(entry.source)
        if drive:
            _add(t["released"], drive, _entry_bytes(row))
    else:
        t["freed_bytes"] += _entry_bytes(row)
    if entry.name not in ours:
        ours[entry.name] = _built_here(entry)
    t["not_ours"] += not ours[entry.name]


def choice_totals(rows: list, found: list, custom,
                  disabled=frozenset()) -> Dict[str, dict]:
    """``{choice: figures}`` of the dry run's ``rows`` (``found`` the
    entries, in step): ``kept``, ``dynamic``, ``left``, ``new_bytes``
    (this drive gains the kept tiles' copies), ``freed_bytes`` (this drive
    gives back the dynamic local tiles, after Free space…),
    ``released`` (``{drive: bytes}`` on other drives no longer needed),
    ``links_removed``, ``drives_needed`` (``{drive: tiles}`` still
    reading their imagery there), ``not_ours`` (dynamic tiles another
    tool built) and ``custom_tiles``.  ``disabled``: :func:`disabled_names`."""
    ours: Dict[str, bool] = {}
    out = {}
    for choice in CHOICES:
        t = {"kept": 0, "dynamic": 0, "left": 0, "new_bytes": 0,
             "freed_bytes": 0, "released": {}, "links_removed": 0,
             "drives_needed": {}, "not_ours": 0, "custom_tiles": len(custom)}
        for row, entry in zip(rows, found, strict=False):
            what = fate(entry, row["action"], choice, custom, disabled)
            if what == "dynamic":
                _tally_dynamic(t, row, entry, ours)
                continue
            t["kept" if what == "keep" else "left"] += 1
            if what == "keep":
                t["new_bytes"] += int(row.get("new_bytes") or 0)
            drive = _drive_of(entry.source) if entry.kind in _LINKS else ""
            if drive and entry.name not in disabled:
                _add(t["drives_needed"], drive, 1)
        out[choice] = t
    return out


def _gb(n: int) -> str:
    return f"{n / 1e12:,.1f} TB" if n >= 1e12 else f"{n / 1e9:,.1f} GB"


def _dynamic_words(choice: str, t: dict) -> str:
    head = (f"Keeps the {t['kept']:,} tiles with a custom airport and makes "
            f"{t['dynamic']:,} dynamic" if choice == KEEP_CUSTOM
            else f"Makes all {t['dynamic']:,} tiles dynamic")
    text = (f"{head}: X-Plane draws them from the World pack, draped ahead "
            f"in flight or built when you fly there. Free space then gives "
            f"back {_gb(t['freed_bytes'])} on this Mac")
    if t["kept"]:
        text += f"; the kept tiles need {_gb(t['new_bytes'])}"
    text += "."
    for drive, size in sorted(t["released"].items()):
        text += (f" {_gb(size)} on {drive} is no longer needed (its files "
                 "are never deleted).")
    if t["links_removed"]:
        text += (f" {t['links_removed']:,} links to another drive are "
                 "removed from Custom Scenery; Undo puts them back.")
    if t["not_ours"]:
        text += (f" {t['not_ours']:,} of the dynamic tiles were not built by "
                 "XPTerrainBuilder (or their drive is not connected): they "
                 "become our drape or build, not the same tile.")
    return text


def choice_line(choice: str, t: dict) -> str:
    """The sentence both apps show beside a choice (its dry-run figures)."""
    if choice == KEEP_ALL:
        text = (f"Keeps {t['kept']:,} tiles: they move into the World pack as "
                f"they are, needing {_gb(t['new_bytes'])} on this Mac.")
    else:
        text = _dynamic_words(choice, t)
    needed = t["drives_needed"]
    if needed:
        text += " Still needs " + ", ".join(
            f"{drive} ({n:,} tile{'' if n == 1 else 's'})"
            for drive, n in sorted(needed.items())) + "."
    elif choice != KEEP_ALL:
        text += " No other drive is needed afterwards."
    return text


# ------------------------------------------------------------ one tile


def retire_tile(entry, *, scenery_dir: str, pack: str, journal,
                swap_lock, set_row, index: Optional[str] = None) -> dict:
    """Make one entry DYNAMIC (module doc), resumable: the journal record
    goes ``retiring`` -> ``dynamic``; each step is idempotent.  ``set_row``
    is ``world_migrate._set_row``."""
    dsf = os.path.join(pack, WP.dsf_relpath(entry.lat, entry.lon))
    record = journal.get(entry.name)
    if not record or record.get("state") not in DYNAMIC_STATES:
        record = journal.set(
            entry.name, state="retiring", kind=entry.kind, source=entry.source,
            prior=WP.kind_of(dsf),
            link_target=(os.readlink(entry.path) if os.path.islink(entry.path)
                         else None))
    if record["state"] == "retiring":
        with swap_lock:
            if not os.path.exists(dsf):
                WP.write_placeholder(pack, entry.lat, entry.lon)
            set_row(scenery_dir, entry.name, enabled=False)
        _forget(entry.lat, entry.lon, index)
        if record.get("link_target") and os.path.islink(entry.path):
            os.unlink(entry.path)       # the link only, never its target
        journal.set(entry.name, state="dynamic")
    return {"name": entry.name, "kind": entry.kind, "action": "dynamic",
            "status": "dynamic"}


def _forget(lat: int, lon: int, index: Optional[str]) -> None:
    from . import imagery_ondemand as ONDEMAND
    with contextlib.suppress(Exception):     # the index is a cache
        ONDEMAND.forget_tile(WP.tile_name(lat, lon), index)


def restore_tile(scenery_dir: str, pack: str, name: str, record: dict,
                 set_row) -> bool:
    """Undo :func:`retire_tile`: the link made again (its target as it
    was), the row enabled, the World pack's placeholder removed when this
    put it there.  False when a local entry was purged (nothing to bring
    back: the tile stays dynamic)."""
    path = os.path.join(scenery_dir, name)
    target = record.get("link_target")
    if target and not os.path.lexists(path):
        os.symlink(target, path)
    if not os.path.lexists(path):
        return False
    set_row(scenery_dir, name, enabled=True)
    lat, lon = WP.parse_tile(name[len("zOrtho4XP_"):])
    dsf = os.path.join(pack, WP.dsf_relpath(lat, lon))
    if record.get("prior") is None and WP.is_placeholder(dsf):
        with contextlib.suppress(FileNotFoundError):
            os.remove(dsf)
    return True


def purge(scenery_dir: str, records: Dict[str, dict],
          names: Optional[Iterable[str]] = None) -> Dict[str, object]:
    """"Free space…": delete the LOCAL entries made dynamic (a real
    folder directly in ``scenery_dir``, never a link).  ``{"removed":
    [names], "freed_bytes"}``; the caller marks their records purged."""
    import O4_Tile_Info as TINFO
    wanted = set(names) if names else None
    root = os.path.realpath(scenery_dir)
    out: Dict[str, object] = {"removed": [], "freed_bytes": 0}
    for name, record in sorted(records.items()):
        if record.get("state") != "dynamic" or record.get("purged"):
            continue
        if wanted is not None and name not in wanted:
            continue
        path = os.path.join(scenery_dir, name)
        if (os.path.islink(path) or not os.path.isdir(path)
                or os.path.dirname(os.path.realpath(path)) != root):
            continue
        size = TINFO.tree_size(path)
        shutil.rmtree(path)
        out["removed"].append(name)
        out["freed_bytes"] += size
    return out
