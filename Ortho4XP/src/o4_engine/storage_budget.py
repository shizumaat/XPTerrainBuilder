"""ONE disk budget for everything XPTerrainBuilder stores (RULINGS
2026-11-10d, superseding 10c (2)'s separate ortho budget): the data
folder's caches, the sharp imagery, rebuild data and the built tiles.

* :data:`SETTING` -- ``storage_budget_gb`` (Library > Disk budget, both
  apps); 0 is "not set" (not confirmed): then the DEFAULT applies
  (RULINGS 2026-11-11a, refined by 11h (1)): :func:`_default_budget_bytes`,
  the larger of :data:`DEFAULT_BUDGET_GB`, the recommended minimum and
  the HELD figure -- what was in use at the first run (installed tiles
  and caches), raised whenever more is in use (:func:`_held_bytes`, kept
  under :data:`HELD_KEY` in the budget's own state file), so nothing is
  cleared before the user confirms a budget.
* The FLOOR, never cleared (10d (2)): the on-demand placeholders, the
  DSFs of every built tile, the user's patches and their own elevation
  files (``geotiffs``).  :func:`_recommended_bytes` is the floor plus
  WORKING ROOM: half the floor, at least 50 GB (:data:`ROOM_SHARE`,
  :data:`ROOM_MIN_BYTES`) -- room for one build's downloads and
  intermediates on top of what is kept.
* the CLEAR ORDER (#2087, owner 2026-11-14T16:57Z, refining 10d (3)):
  ``storage_priority`` -- data tied to no one tile first (temp, logs,
  previews, texture cache, dumps, regional extracts), then tile by tile,
  non-favorites before favorites and the tile used longest ago first,
  each tile's data cheapest first (orthophotos, masks, elevation and map
  data -- an older airport tile shrinks to its ``.xptb`` package,
  ``storage_packages``, RULINGS 2026-11-11l item 5 -- sharp imagery,
  rebuild data).  A tile of this session or used in the last week, and
  the inputs of their builds, are never cleared; a file a mounted
  storage tier has room for moves there (``storage_tier_data``).
* :func:`status` -- the budget's figures for the Storage pane: the
  slider's range (#2022, ``storage_range``: a budget set below the
  minimum is raised to it, one above the disk's maximum follows it
  down), the stacked bar and the clearing ladder; :func:`hold` -- the
  automatic cleanup's step (``storage.storage_auto_clean``);
  :func:`session_budget` -- the follow job's budget between cleanups
  (the bytes other than sharp imagery that the last :func:`hold`
  recorded).

The orthophoto tier deletes JPEGs the on-demand index does not protect;
a JPEG of a tile that was never converted is downloaded again by its
next build (the same cost as any other cache file).  No tile or airport
is named here.
"""
from __future__ import annotations

import glob
import json
import os
import typing as _t

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Budget as BUDGET

from . import storage as STORAGE
from . import storage_priority as PRIORITY
from . import storage_range as RANGE
from .storage_installed import _read_cache, write_json

__all__ = ["SETTING", "DEFAULT_BUDGET_GB", "ROOM_SHARE", "ROOM_MIN_BYTES",
           "HELD_KEY", "status", "hold", "session_budget"]

SETTING = "storage_budget_gb"
#: The budget when none is set (RULINGS 2026-11-11a): 200 GB, or the
#: recommended minimum when that is more (:func:`_default_budget_bytes`).
DEFAULT_BUDGET_GB = 200
#: The held figure's key in the state file (RULINGS 2026-11-11h (1)).
HELD_KEY = "default_held_bytes"
ROOM_SHARE = 0.5
ROOM_MIN_BYTES = 50 * 10**9
_LAST = "storage_budget.json"


def _budget_bytes(raw: "dict | None" = None) -> int:
    """The budget in bytes; 0 when it is not set (or does not parse)."""
    if raw is None:
        import O4_Settings_Model as SM
        raw = SM.read_global_raw()
    try:
        gigabytes = float(raw.get(SETTING, "") or 0)
    except (TypeError, ValueError):
        gigabytes = 0.0
    return int(gigabytes * 1e9) if gigabytes > 0 else 0


def _index():
    return STORAGE._ondemand_index()


def _floor_parts(rows: "list[dict]") -> dict:
    """``{"placeholders", "dsf", "patches", "geotiffs"}`` bytes; ``rows``
    are :func:`storage.storage_scan`'s store rows."""
    by_kind = {row["kind"]: row for row in rows}
    folders = set(glob.glob(os.path.join(glob.escape(FNAMES.Tile_dir), "*")))
    placeholders = 0
    conn = _index()
    if conn is not None:
        try:
            placeholders = BUDGET.placeholder_bytes(conn)
            folders |= BUDGET.build_dirs(conn)
        finally:
            conn.close()
    return {"placeholders": placeholders, "dsf": BUDGET.dsf_bytes(folders),
            "patches": int(by_kind.get("patches", {}).get("bytes", 0)),
            "geotiffs": int(by_kind.get("geotiffs", {}).get("bytes", 0))}


def _recommended_bytes(floor: int) -> int:
    """The floor plus the working room."""
    return int(floor + max(ROOM_MIN_BYTES, ROOM_SHARE * floor))


def _default_budget_bytes(floor: int, held: int = 0) -> int:
    """The budget that applies when none is confirmed (RULINGS 2026-11-11a,
    11h (1)): the larger of :data:`DEFAULT_BUDGET_GB`, the recommended
    minimum and the ``held`` figure (:func:`_held_bytes`)."""
    return max(int(DEFAULT_BUDGET_GB * 1e9), _recommended_bytes(floor), int(held))


def _last_path() -> str:
    return os.path.join(FNAMES.data_path("logs"), _LAST)


def _held_bytes(in_use: int) -> int:
    """The unconfirmed default's held figure (RULINGS 2026-11-11h (1)):
    what was in use at the first run, raised to ``in_use`` when that is
    more (so the default never stands below what is installed and nothing
    is cleared unasked); recorded in the state file on change."""
    last = _read_cache(_last_path())
    held = int(last.get(HELD_KEY) or 0)
    if in_use > held:
        held = int(in_use)
        write_json(_last_path(), dict(last, **{HELD_KEY: held}))
    return held


def _scenery_dir() -> str:
    from .storage_redundant import _custom_scenery_dir
    return _custom_scenery_dir()


def status(rows: "list[dict]", raw: "dict | None" = None,
           installed_bytes: int = 0) -> dict:
    """The budget's figures from a scan's store ``rows``:
    ``{"budget_bytes", "budget_set", "chosen_bytes", "clamped",
    "default_bytes", "default_base_bytes", "held_bytes", "low_water",
    "used_bytes", "floor_bytes", "floor", "recommended_bytes",
    "minimum_bytes", "minimum", "maximum_bytes", "reserve_bytes",
    "breakdown", "ladder", "under_floor", "over_budget", "sharp_bytes"}``.
    ``budget_bytes`` is the budget that applies: the one set
    (``budget_set``, ``chosen_bytes`` as typed) kept between
    ``minimum_bytes`` and ``maximum_bytes`` (``clamped``: ``"minimum"`` or
    ``"followed"``, ``storage_range.clamp``), or the default
    (``default_bytes``); a clearing stops at ``low_water`` of it.
    ``used`` is every store plus the placeholders and the World pack's
    DSFs (no store row counts them); ``under_floor``: a budget under the
    floor (the warning).  Unconfirmed, ``held_bytes`` is
    :func:`_held_bytes` of ``used`` plus ``installed_bytes`` (the
    per-tile packs measured in Custom Scenery, ``storage_installed``) --
    the only write; 0 once a budget is set."""
    from . import imagery_downgrade as DOWNGRADE
    parts = _floor_parts(rows)
    floor = sum(parts.values())
    world = RANGE.world_parts(_scenery_dir())
    used = (sum(int(row.get("bytes") or 0) for row in rows)
            + parts["placeholders"] + world["placeholders"] + world["dsf"])
    sharp = sum(int(row.get("bytes") or 0) for row in rows
                if row["kind"] == STORAGE.ONDEMAND)
    least = RANGE.minimum_parts(parts, world)
    minimum = sum(least.values())
    maximum = RANGE.maximum_bytes(used, minimum, FNAMES.current_data_root())
    chosen = _budget_bytes(raw)
    held = 0 if chosen else _held_bytes(used + int(installed_bytes or 0))
    default = _default_budget_bytes(floor, held)
    budget, why = RANGE.clamp(chosen, minimum, maximum) if chosen else (default, "")
    split = RANGE.sharp_split()
    out = {"budget_bytes": budget, "budget_set": bool(chosen),
           "chosen_bytes": chosen, "clamped": why,
           "default_bytes": default, "default_base_bytes": int(DEFAULT_BUDGET_GB * 1e9),
           "held_bytes": held,
           "low_water": DOWNGRADE.LOW_WATER,
           "used_bytes": used, "floor_bytes": floor,
           "floor": parts, "recommended_bytes": _recommended_bytes(floor),
           "minimum_bytes": minimum, "minimum": least,
           "maximum_bytes": maximum, "reserve_bytes": RANGE.RESERVE_BYTES,
           "breakdown": RANGE.breakdown(rows, used, least),
           "ladder": RANGE.ladder(rows, split),
           "under_floor": budget < floor, "over_budget": used > budget,
           "sharp_bytes": sharp}
    return out


def session_budget(conn, cap_bytes: int) -> BUDGET.Budget:
    """The follow job's budget: with the total budget set, its cap and
    the last scan's bytes other than the sharp imagery; else the sharp
    imagery limit ``cap_bytes`` over the on-demand floor (the default
    budget clears nothing the user has not confirmed, :func:`hold`)."""
    budget = _budget_bytes()
    if budget:
        try:
            with open(_last_path(), encoding="utf-8") as handle:
                other = int(json.load(handle).get("other_bytes") or 0)
            return BUDGET.Budget(budget, other)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return BUDGET.measure(conn, cap_bytes)


def _drape_bytes() -> int:
    """The World pack's drape bytes (``world_drape_evict.pack_bytes``;
    the pack is in Custom Scenery, outside the scanned stores)."""
    from . import world_drape_evict as DRAPES
    try:
        return DRAPES.pack_bytes()
    except Exception:                       # no pack readable: none
        return 0


def hold(sweep, now: float,
         scan: "_t.Callable[[], dict] | None" = None) -> "dict | None":
    """Over a budget the user SET, clear until 90 % of it is used
    (``imagery_downgrade.LOW_WATER``) in tile priority order
    (``storage_priority.clear``: shared data, then the oldest
    non-favorite tile's data, cheapest first); the figures.  Unconfirmed
    (none set) nothing is cleared: the default holds what is in use
    (RULINGS 2026-11-11h (1)) until the user confirms a budget."""
    from . import imagery_downgrade as DOWNGRADE
    rows = (scan or STORAGE.storage_scan)()["stores"]
    figures = status(rows)
    budget = figures["budget_bytes"]
    used = figures["used_bytes"]
    write_json(_last_path(), dict(_read_cache(_last_path()), budget_bytes=budget,
                                  other_bytes=used - figures["sharp_bytes"]))
    used += _drape_bytes()          # #2142 Q3: the World pack's drapes
    over = used - int(budget * DOWNGRADE.LOW_WATER)
    if used <= budget or not figures["budget_set"]:
        return figures
    PRIORITY.clear(over, sweep, now)
    return figures
