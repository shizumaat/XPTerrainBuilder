"""The on-demand imagery storage cap: downgrade sharp textures back to
their placeholders, least recently flown near first (#1992,
local-imagery-cache spec §6.2).

A DOWNGRADE is a landing, never a deletion (spec §4.7 R1-R3): the kept
placeholder (``O4_Imagery_Placeholder`` store) is hard-linked beside the
texture under a partial name and ``O4_DDS_File.land`` renames it over the
upgraded file, so the texture name always resolves to a whole DDS.  Then
the upgraded texture's ``DDS_cache`` entry (unless another build dir uses
it) and its tier JPEG are removed, and one line goes to
``logs/storage.log`` (as every Storage deletion does).

* :func:`cap_bytes` -- the ``imagery_on_demand_cap_gb`` setting (default
  100 GB) in bytes.
* :func:`_should_sweep` -- the hysteresis: at launch or after a follow
  session a sweep runs over the cap; during one only over 110 % of it;
  either way it downgrades to 90 % (:data:`LOW_WATER`, :data:`HIGH_WATER`).
* :func:`_near_camera` -- inside 2 x its tier distance of the camera
  (never downgraded while the sim runs).
* :func:`_downgrade` -- one row: land its placeholder, free what it held.
* :func:`sweep` -- the ortho budget (RULINGS 2026-11-10c (2): favorites
  count): rows in ``lru_order`` (cores next to last, favorites last)
  until the budget's total (``O4_Imagery_OnDemand_Budget.Budget``: the
  placeholders and DSFs plus the sharp bytes) is at most 90 % of it,
  skipping squares near the camera and textures landed in the last hour.
* :func:`downgrade_all` -- "Make all low-res again" (the Storage row's
  clear action): every upgraded row but the favorites, optionally of one
  tile or not near since a cutoff.
"""
from __future__ import annotations

import contextlib
import os
import time
import typing as _t

import O4_DDS_Cache as DDSC
import O4_Disk_Usage as DISK
import O4_Imagery_OnDemand_Budget as BUDGET
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Placeholder as PLACEHOLDER

__all__ = ["CAP_SETTING", "DEFAULT_CAP_GB", "HIGH_WATER", "LOW_WATER",
           "NEAR_FACTOR", "budget", "cap_bytes", "downgrade_all", "sweep"]

#: The global setting (Settings > Storage; its rows land in P4).
CAP_SETTING = "imagery_on_demand_cap_gb"
DEFAULT_CAP_GB = 100.0
#: A sweep stops at this share of the cap ...
LOW_WATER = 0.90
#: ... and starts during a follow session only above this one.
HIGH_WATER = 1.10
#: A square within this many times its tier distance of the camera stays.
NEAR_FACTOR = 2.0


def budget(conn, raw: "dict | None" = None) -> "BUDGET.Budget":
    """The ortho budget of the index ``conn``: :func:`cap_bytes`, with the
    on-demand tiles' placeholders and DSFs fixed in it."""
    return BUDGET.measure(conn, cap_bytes(raw))


def cap_bytes(raw: "dict | None" = None) -> int:
    """The cap in bytes: ``raw`` (the global config; read when ``None``),
    a value that is not a positive number reads as the default."""
    if raw is None:
        import O4_Settings_Model as SM
        raw = SM.read_global_raw()
    try:
        gigabytes = float(raw.get(CAP_SETTING, "") or DEFAULT_CAP_GB)
    except (TypeError, ValueError):
        gigabytes = DEFAULT_CAP_GB
    if gigabytes <= 0:
        gigabytes = DEFAULT_CAP_GB
    return int(gigabytes * 1e9)


def _should_sweep(total: int, cap: int, *, in_session: bool) -> bool:
    """Is ``total`` far enough over ``cap`` to start a sweep?"""
    return total > cap * (HIGH_WATER if in_session else 1.0)


def _near_camera(row: dict, camera) -> bool:
    """Inside :data:`NEAR_FACTOR` x the row's tier distance of ``camera``
    (anything with ``lat`` and ``lon``; ``None``: the sim is not
    running)."""
    if camera is None:
        return False
    reach = NEAR_FACTOR * INDEX.tier_distance_m(row)
    return INDEX.distance_m(row, camera.lat, camera.lon) <= reach


def _write_log(line: str) -> None:
    from . import storage
    storage.write_log(line)


def _remove(path: "str | None") -> int:
    """Remove ``path``; the bytes that freed (0 when it was not there)."""
    if not path:
        return 0
    try:
        size = DISK.freeable_bytes(path)
        os.remove(path)
    except OSError:
        return 0
    return size


def _free_cache_entry(row: dict, users: "dict | None") -> int:
    """Remove the row's ``DDS_cache`` entry unless another build dir's
    notes name it (a neighbour tile's shared edge texture)."""
    key = row.get("dds_cache_key")
    if not key:
        return 0
    if users is None:
        users = DDSC.key_users()
    own = os.path.abspath(row.get("build_dir") or "")
    if any(os.path.abspath(where) != own for where, _n in users.get(key, ())):
        return 0
    # A mounted storage tier with room keeps it (RULINGS 2026-11-12g): moved
    # there, not deleted; it lands back from there while mounted.
    from . import storage_tiers as TIERS
    entry = DDSC.entry_path(key)
    size = DISK.freeable_bytes(entry) if os.path.isfile(entry) else 0
    if TIERS.stash(key, entry):
        _write_log("moved %d bytes %s to a storage tier" % (size, entry))
        return size
    return _remove(entry)


def _downgrade(conn, row: dict, *, users: "dict | None" = None,
              reason: str = "on-demand cap",
              favorites: bool = False) -> "int | None":
    """Land ``row``'s placeholder over its upgraded texture and free its
    cache entry and tier JPEG; the bytes freed, or ``None`` (nothing
    changed) when the row has no whole placeholder or the landing was
    refused.  A favorite (pinned) row goes only with ``favorites`` (the
    budget sweep's last tier)."""
    if row.get("pinned") and not favorites:
        return None
    path = INDEX.texture_path(row)
    kept = row.get("placeholder_path")
    if not path or not kept or not PLACEHOLDER.land_kept(kept, path):
        return None
    freed = int(row.get("full_bytes") or 0)
    freed += _free_cache_entry(row, users)
    freed += _remove(row.get("jpeg_path"))
    INDEX.set_state(conn, row["tile"], row["name"], "low",
                    tier_px=INDEX.placeholder_width(row), full_bytes=0,
                    dds_cache_key=None, jpeg_path=None)
    _write_log("downgraded %d bytes %s (ondemand, %s)" % (freed, path, reason))
    return freed


def _recent(row: dict, now: float) -> bool:
    from .storage import IN_FLIGHT_SECONDS
    return now - float(row.get("fetched_at") or 0.0) < IN_FLIGHT_SECONDS


def sweep(conn, cap: "int | BUDGET.Budget", *, camera=None,
          in_session: bool = False, now: "float | None" = None,
          abort: "_t.Callable[[], bool] | None" = None) -> dict:
    """Hold the budget: when :func:`_should_sweep`, downgrade rows in
    ``INDEX.lru_order(favorites=True)`` until the budget's total is at
    most :data:`LOW_WATER` x its cap, skipping squares
    :func:`_near_camera` and textures landed in the last hour.  ``cap``
    is a :class:`O4_Imagery_OnDemand_Budget.Budget` (the engine's
    callers: ``BUDGET.measure``), or bare bytes with nothing fixed.

    :returns: ``{"ran", "downgraded", "freed_bytes", "total_before",
        "total_after", "cap_bytes", "floor_bytes", "over_at_floor",
        "skipped_near", "skipped_recent"}``
    """
    budget = cap if isinstance(cap, BUDGET.Budget) else BUDGET.Budget(int(cap))
    cap = budget.cap
    now = time.time() if now is None else now
    abort = abort or (lambda: False)
    total = before = budget.total(INDEX.capped_bytes(conn))
    out = {"ran": False, "downgraded": 0, "freed_bytes": 0,
           "total_before": before, "cap_bytes": int(cap),
           "floor_bytes": int(budget.fixed),
           "over_at_floor": budget.over_at_floor,
           "skipped_near": 0, "skipped_recent": 0}
    if _should_sweep(total, cap, in_session=in_session):
        out["ran"] = True
        users = DDSC.key_users()
        target = cap * LOW_WATER
        for row in INDEX.lru_order(conn, favorites=True):
            if total <= target or abort():
                break
            if _near_camera(row, camera):
                out["skipped_near"] += 1
                continue
            if _recent(row, now):
                out["skipped_recent"] += 1
                continue
            freed = _downgrade(conn, row, users=users, favorites=True)
            if freed is not None:
                total -= int(row.get("full_bytes") or 0)
                out["downgraded"] += 1
                out["freed_bytes"] += freed
    out["total_after"] = budget.total(INDEX.capped_bytes(conn))
    return out


def downgrade_all(conn, *, tile: "str | None" = None, camera=None,
                  not_near_since: "float | None" = None,
                  dry_run: bool = False, reason: str = "made low-res by hand",
                  abort: "_t.Callable[[], bool] | None" = None) -> dict:
    """Every upgraded row but the favorites (of ``tile`` when given; not flown near
    since ``not_near_since`` when given) back to its placeholder, except
    the squares :func:`_near_camera`.  ``dry_run`` changes nothing and
    answers what would be freed.

    :returns: ``{"downgraded", "freed_bytes", "skipped_near", "dry_run",
        "stopped"}``
    """
    abort = abort or (lambda: False)
    out = {"downgraded": 0, "freed_bytes": 0, "skipped_near": 0,
           "dry_run": bool(dry_run), "stopped": False}
    users = None if dry_run else DDSC.key_users()
    for row in INDEX.lru_order(conn):
        if abort():
            out["stopped"] = True
            break
        if tile is not None and row["tile"] != tile:
            continue
        if (not_near_since is not None
                and float(row.get("last_near_at") or 0.0) >= not_near_since):
            continue
        if _near_camera(row, camera):
            out["skipped_near"] += 1
            continue
        if dry_run:
            out["downgraded"] += 1
            out["freed_bytes"] += int(row.get("full_bytes") or 0)
            continue
        with contextlib.suppress(OSError):
            freed = _downgrade(conn, row, users=users, reason=reason)
            if freed is not None:
                out["downgraded"] += 1
                out["freed_bytes"] += freed
    return out
