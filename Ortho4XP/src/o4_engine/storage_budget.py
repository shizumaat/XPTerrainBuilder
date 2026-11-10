"""ONE disk budget for everything XPTerrainBuilder stores (RULINGS
2026-11-10d, superseding 10c (2)'s separate ortho budget): the data
folder's caches, the sharp imagery, rebuild data and the built tiles.

* :data:`SETTING` -- ``storage_budget_gb`` (Settings > Storage, both
  apps); 0 is "not set": then the sharp imagery keeps its own limit
  (``imagery_on_demand_cap_gb``) and nothing else is cleared for space.
* The FLOOR, never cleared (10d (2)): the on-demand placeholders, the
  DSFs of every built tile, the user's patches and their own elevation
  files (``geotiffs``).  :func:`_recommended_bytes` is the floor plus
  WORKING ROOM: half the floor, at least 50 GB (:data:`ROOM_SHARE`,
  :data:`ROOM_MIN_BYTES`) -- room for one build's downloads and
  intermediates on top of what is kept.
* :data:`TIERS` -- what goes first over the budget, cheapest to rebuild
  first, oldest first within a tier (10d (3)): temp, logs, previews ->
  orthophotos (already converted to textures; their DDS cache with them)
  -> scenery dumps, water masks, airport pack caches -> elevation and
  map extracts -> sharp imagery (``imagery_downgrade.sweep``: cores,
  then favorites last) -> per-tile rebuild data (:data:`REBUILD_DATA`,
  a HOOK: the store lands with 10d (4) in another lane, registered in
  :data:`TIER_HOOKS`).
* :func:`status` -- the budget's figures for the Storage pane (and the
  warning when the budget is under the floor); :func:`hold` -- the
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
from .storage_installed import write_json

__all__ = ["SETTING", "ROOM_SHARE", "ROOM_MIN_BYTES", "TIERS", "REBUILD_DATA",
           "TIER_HOOKS", "status", "hold", "session_budget"]

SETTING = "storage_budget_gb"
ROOM_SHARE = 0.5
ROOM_MIN_BYTES = 50 * 10**9
#: The per-tile rebuild data tier (10d (4): another lane adds the store).
REBUILD_DATA = "rebuild_data"
#: Cheapest to rebuild first (RULINGS 2026-11-10d (3)).
TIERS: tuple = (("tmp", "logs", "previews"), ("imagery", "dds"),
                ("dsf_dumps", "masks", "airport_mod"),
                ("elevation", "osm_extracts", "osm"),
                (STORAGE.ONDEMAND,), (REBUILD_DATA,))
#: ``{tier kind: hook(over_by, sweep, now) -> bytes freed}`` for a tier
#: no ``storage.STORES`` row holds yet (the rebuild data).
TIER_HOOKS: dict = {}
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


def _last_path() -> str:
    return os.path.join(FNAMES.data_path("logs"), _LAST)


def status(rows: "list[dict]", raw: "dict | None" = None) -> dict:
    """The budget's figures from a scan's store ``rows``:
    ``{"budget_bytes", "used_bytes", "floor_bytes", "floor",
    "recommended_bytes", "under_floor", "over_budget", "sharp_bytes"}``.
    ``used`` is every store plus the placeholders (no store row counts
    them); ``under_floor``: a budget set below the floor (the warning).
    Writes nothing."""
    parts = _floor_parts(rows)
    floor = sum(parts.values())
    used = sum(int(row.get("bytes") or 0) for row in rows) + parts["placeholders"]
    sharp = sum(int(row.get("bytes") or 0) for row in rows
                if row["kind"] == STORAGE.ONDEMAND)
    budget = _budget_bytes(raw)
    out = {"budget_bytes": budget, "used_bytes": used, "floor_bytes": floor,
           "floor": parts, "recommended_bytes": _recommended_bytes(floor),
           "under_floor": bool(budget and budget < floor),
           "over_budget": bool(budget and used > budget), "sharp_bytes": sharp}
    return out


def session_budget(conn, cap_bytes: int) -> BUDGET.Budget:
    """The follow job's budget: with the total budget set, its cap and
    the last scan's bytes other than the sharp imagery; else the sharp
    imagery limit ``cap_bytes`` over the on-demand floor."""
    budget = _budget_bytes()
    if budget:
        try:
            with open(_last_path(), encoding="utf-8") as handle:
                other = int(json.load(handle).get("other_bytes") or 0)
            return BUDGET.Budget(budget, other)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return BUDGET.measure(conn, cap_bytes)


def _clear_sharp(over_by: int, cap: int, used: int, sweep, now: float) -> int:
    from . import imagery_downgrade as DOWNGRADE
    conn = _index()
    if conn is None or sweep.dry_run:
        return 0
    try:
        import O4_Imagery_OnDemand_Index as INDEX
        sharp = INDEX.capped_bytes(conn)
        result = DOWNGRADE.sweep(conn, BUDGET.Budget(cap, used - sharp),
                                 now=now, abort=sweep.abort)
        sweep.downgraded(STORAGE._BY_KIND[STORAGE.ONDEMAND], result)
        return int(result.get("freed_bytes") or 0)
    finally:
        conn.close()


def hold(sweep, now: float,
         scan: "_t.Callable[[], dict] | None" = None) -> "dict | None":
    """Over the budget, clear tier by tier until 90 % of it is used
    (``imagery_downgrade.LOW_WATER``); None when the budget is not set
    (the caller then holds the sharp imagery's own limit)."""
    from . import imagery_downgrade as DOWNGRADE
    budget = _budget_bytes()
    if not budget:
        return None
    rows = (scan or STORAGE.storage_scan)()["stores"]
    figures = status(rows)
    used = figures["used_bytes"]
    write_json(_last_path(), {"budget_bytes": budget,
                           "other_bytes": used - figures["sharp_bytes"]})
    over = used - int(budget * DOWNGRADE.LOW_WATER)
    if used <= budget:
        return figures
    for tier in TIERS:
        if over <= 0 or sweep.stopped:
            break
        if tier == (STORAGE.ONDEMAND,):
            freed = _clear_sharp(over, budget, used, sweep, now)
        elif tier[0] in TIER_HOOKS:
            freed = TIER_HOOKS[tier[0]](over, sweep, now)
        else:
            stores = [STORAGE._BY_KIND[k] for k in tier if k in STORAGE._BY_KIND]
            freed = STORAGE._evict_oldest(stores, over, sweep, now)
        over -= freed
        used -= freed
    return figures
