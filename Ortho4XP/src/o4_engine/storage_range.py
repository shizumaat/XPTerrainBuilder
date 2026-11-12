"""The disk budget's RANGE for Settings ▸ Storage's slider (#2022, owner
2026-11-12): the least it can be, the most it can be, what is in use by
kind (the stacked bar), and what a clearing frees step by step (the
preview line).

* :func:`world_parts` -- the World pack's placeholder DSFs and tile DSFs
  (kept and adopted tiles) in Custom Scenery.
* :func:`minimum_parts` -- what is always kept (RULINGS 2026-11-10d (2):
  DSFs and placeholders are never cleared): the budget's floor
  (``storage_budget._floor_parts``: imagery placeholders, the DSFs of
  built tiles, patches, own elevation files), the World pack's parts and
  the packages of the airport tiles (``storage_packages.packaged``).
* :func:`maximum_bytes` -- what is in use plus the free space of the disk
  holding the data folder, less :data:`RESERVE_BYTES` (50 GB kept free);
  never under the minimum.
* :func:`clamp` -- a budget kept between the two: below the minimum it is
  the minimum, above the maximum it follows the disk down.
* :func:`sharp_split` -- the sharp imagery by what the sweep clears
  first: ordinary, airport cores, favorites.
* :func:`breakdown` -- the stacked bar's parts (:data:`BAR_PARTS`).
* :func:`ladder` -- the bytes each step of a clearing frees, in order
  (:data:`LADDER_STEPS`, ``storage_budget.TIERS``).  The apps turn it
  into the preview sentence while the slider moves
  (``O4_Storage_Text.preview_text`` and its Swift mirror).

No tile or airport is named here.
"""
from __future__ import annotations

import os

import O4_World_Pack as WP

__all__ = ["RESERVE_BYTES", "BAR_PARTS", "LADDER_STEPS", "world_parts",
           "minimum_parts", "maximum_bytes", "clamp", "sharp_split",
           "breakdown", "ladder"]

#: Kept free on the disk at the slider's right end (owner 2026-11-12).
RESERVE_BYTES = 50 * 10**9
#: The stacked bar, left to right.
BAR_PARTS = ("placeholders", "tiles", "airport_imagery", "other_imagery",
             "packages", "other")
#: A clearing's steps, first to last (``storage_budget.TIERS``).
LADDER_STEPS = ("caches", "imagery", "airport_imagery", "favorites",
                "rebuild")
#: The cache stores of the tiers before the sharp imagery.
_CACHE_KINDS = ("tmp", "logs", "previews", "imagery", "dds", "dsf_dumps",
                "masks", "airport_mod", "elevation", "osm_extracts", "osm")


def _free_bytes(folder: str) -> "int | None":
    """The free bytes of ``folder``'s disk (``None``: unreadable)."""
    from .plan_estimate import _free_bytes as free
    return free(folder)


def world_parts(scenery_dir: str) -> dict:
    """``{"placeholders", "dsf"}``: the bytes of the World pack's
    placeholder DSFs and of its tile DSFs in Custom Scenery folder
    ``scenery_dir``; zeros without one."""
    out = {"placeholders": 0, "dsf": 0}
    if not scenery_dir:
        return out
    for _key, path, size in WP.pack_dsfs(os.path.join(scenery_dir, WP.PACK_NAME)):
        out["placeholders" if WP.is_placeholder(path, size) else "dsf"] += size
    return out


def _airport_packages() -> int:
    """The bytes of the packages of airport tiles."""
    from . import storage_packages as PACKAGES
    total = 0
    for row in PACKAGES.packaged().values():
        path = (row or {}).get("path") or ""
        if row.get("airports") and os.path.isfile(path):
            total += os.path.getsize(path)
    return total


def minimum_parts(floor: dict, world: dict) -> dict:
    """The minimum's parts: the budget's ``floor`` parts, the World
    pack's (:func:`world_parts`) and the airport packages."""
    return dict(floor, world_placeholders=int(world.get("placeholders", 0)),
                world_dsf=int(world.get("dsf", 0)),
                packages=_airport_packages())


def maximum_bytes(used: int, minimum: int, folder: str) -> int:
    """``used`` plus the free space of ``folder``'s disk less
    :data:`RESERVE_BYTES`, never under ``minimum``; with an unreadable
    disk, ``used`` (or ``minimum``)."""
    free = _free_bytes(folder)
    if free is None:
        return max(int(used), int(minimum))
    return max(int(minimum), int(used) + int(free) - RESERVE_BYTES)


def clamp(chosen: int, minimum: int, maximum: int) -> "tuple[int, str]":
    """``(budget, why)``: ``chosen`` kept in ``[minimum, maximum]``;
    ``why`` is ``"minimum"`` (raised to it), ``"followed"`` (lowered to
    the disk's maximum) or ``""``."""
    if chosen < minimum:
        return int(minimum), "minimum"
    if chosen > maximum:
        return int(maximum), "followed"
    return int(chosen), ""


def _split(conn) -> dict:
    out = {"ordinary": 0, "airport_imagery": 0, "favorites": 0}
    if conn is not None:
        for core, pinned, nbytes in conn.execute(
                "SELECT core, pinned, COALESCE(SUM(full_bytes), 0) FROM textures "
                "WHERE state = 'upgraded' GROUP BY core, pinned"):
            key = "favorites" if pinned else ("airport_imagery" if core else "ordinary")
            out[key] += int(nbytes or 0)
    return out


def sharp_split() -> dict:
    """``{"ordinary", "airport_imagery", "favorites"}``: the sharp bytes
    of the on-demand index, as the sweep clears them (zeros without one)."""
    from . import storage as STORAGE
    conn = STORAGE._ondemand_index()
    try:
        return _split(conn)
    finally:
        if conn is not None:
            conn.close()


def breakdown(rows: "list[dict]", used: int, minimum: dict, sharp: dict) -> dict:
    """The stacked bar (:data:`BAR_PARTS`) of ``used`` bytes, from the
    scan ``rows``, the ``minimum`` parts and the ``sharp`` split;
    ``other`` is the rest (caches, patches, own elevation files)."""
    from . import storage_packages as PACKAGES
    by_kind = {row["kind"]: int(row.get("bytes") or 0) for row in rows}
    parts = {
        "placeholders": int(minimum.get("placeholders", 0))
        + int(minimum.get("world_placeholders", 0)),
        "tiles": by_kind.get("tiles", 0) + by_kind.get("rebuild", 0)
        + int(minimum.get("world_dsf", 0)),
        "airport_imagery": int(sharp.get("airport_imagery", 0)),
        "other_imagery": int(sharp.get("ordinary", 0))
        + int(sharp.get("favorites", 0))
        + by_kind.get("imagery", 0) + by_kind.get("dds", 0),
        "packages": by_kind.get(PACKAGES.KIND, 0),
    }
    parts["other"] = max(0, int(used) - sum(parts.values()))
    return parts


def ladder(rows: "list[dict]", sharp: dict) -> dict:
    """``{step: bytes}`` a clearing frees, :data:`LADDER_STEPS` in order."""
    by_kind = {row["kind"]: int(row.get("bytes") or 0) for row in rows}
    return {"caches": sum(by_kind.get(k, 0) for k in _CACHE_KINDS),
            "imagery": int(sharp.get("ordinary", 0)),
            "airport_imagery": int(sharp.get("airport_imagery", 0)),
            "favorites": int(sharp.get("favorites", 0)),
            "rebuild": by_kind.get("rebuild", 0)}
