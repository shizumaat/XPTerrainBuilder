"""The on-demand imagery commands (#1992, local-imagery-cache spec §5,
§6, §7 pins; capability ``imagery_ondemand``).

* :func:`imagery_ondemand_scan` -- (re)build the index for every
  on-demand tile under a working dir: rows from the tiles' textures,
  ``.ter`` files and manifests (``O4_Imagery_OnDemand_Index.rebuild``),
  the airport cores (``O4_Imagery_OnDemand_Cores``), interrupted fetches
  reset; answers the Storage figures.
* :func:`imagery_pin` -- "Always keep full resolution" / "Let it go
  low-res again" for one tile: the tile record (``pinned`` in its imagery
  manifest) and the index; pinning lands every full texture the
  ``DDS_cache`` still holds for the tile (``O4_DDS_Cache.serve``) and
  answers how many are still to fetch (the follow job fetches them).
* :func:`imagery_ondemand_sweep` -- hold the cap now (the sweep the
  automatic cleanup runs at launch, and the follow job above 110 %),
  optionally with the camera's position and a cap other than the
  setting's (the P2 verification flight sets 1 GB).
* :func:`imagery_ondemand_downgrade_all` -- "Make all low-res again":
  every unpinned sharp texture back to its placeholder
  (``imagery_downgrade.downgrade_all``); ``dry_run`` answers the space
  it would free, which the apps' confirmation names.

Tile identity comes from the scan (``O4_Tile_Info``); no airport and no
tile is named here.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import O4_DDS_Cache as DDSC
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_Disk_Usage as DISK
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Budget as BUDGET
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Placeholder as PLACEHOLDER

from . import imagery_downgrade as DOWNGRADE

__all__ = ["forget_tile", "on_demand_tiles", "imagery_ondemand_scan", "imagery_pin",
           "imagery_ondemand_sweep", "imagery_ondemand_downgrade_all",
           "register_tiles"]


def _set_manifest_pin(build_dir: str, lat: int, lon: int, pinned: bool) -> None:
    """Write ``pinned`` into the tile record (atomic replace)."""
    import O4_Tile_Info as TINFO
    path = TINFO.imagery_record_path(build_dir, lat, lon)
    data = TINFO.read_imagery_record(build_dir, lat, lon)
    data["pinned"] = bool(pinned)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    os.replace(temporary, path)


def _placeholder_root() -> str:
    return os.path.join(FNAMES.data_path(PLACEHOLDER.STORE_DIR), "placeholders")


def _keys_by_texture(users: dict) -> dict:
    """``{(build dir, name): [key, ...]}`` from ``O4_DDS_Cache.key_users``."""
    out: dict = {}
    for key, where in users.items():
        for build_dir, name in where:
            out.setdefault((os.path.abspath(build_dir), name), []).append(key)
    return out


def _tile_roots(working_dir: str = "") -> "list[str]":
    """Every folder a built tile may live in: ``working_dir`` (the apps'
    build folder, a custom build dir among them), the Tiles folder, and
    Custom Scenery (a tile built straight into it, or linked there);
    each once."""
    from . import storage_redundant
    out: list = []
    for folder in (working_dir, FNAMES.Tile_dir,
                   storage_redundant._custom_scenery_dir()):
        if folder and os.path.isdir(folder) and all(
                os.path.realpath(folder) != os.path.realpath(o) for o in out):
            out.append(folder)
    return out


def on_demand_tiles(working_dir: str = ""):
    """``(build_dir, lat, lon)`` of every tile under :func:`_tile_roots`
    whose imagery record says on demand or pinned, then every built tile
    converted to on-demand form (``imagery_convert.converted_tiles``);
    a tile reached twice (a Custom Scenery link to the Tiles folder) and
    a second copy of one tile are given once, the first root's."""
    import O4_Tile_Info as TINFO

    from .imagery_convert import converted_tiles
    seen, keys = set(), set()
    for root in _tile_roots(working_dir):
        for (lat, lon), info in sorted(TINFO.scan_tiles(root).items()):
            real = os.path.realpath(info.build_dir)
            if real in seen or (lat, lon) in keys:
                continue
            record = TINFO.read_imagery_record(info.build_dir, lat, lon)
            if record.get("on_demand") or record.get("pinned"):
                seen.add(real)
                keys.add((lat, lon))
                yield info.build_dir, lat, lon
    for folder, lat, lon in converted_tiles():
        if os.path.realpath(folder) not in seen and (lat, lon) not in keys:
            yield folder, lat, lon


def _figures(conn) -> Dict[str, Any]:
    budget = DOWNGRADE.budget(conn)
    return {"capped_bytes": INDEX.capped_bytes(conn),
            "pinned_bytes": INDEX.pinned_bytes(conn),
            "cap_bytes": budget.cap, "floor_bytes": budget.fixed,
            "over_at_floor": budget.over_at_floor,
            "core_rows": len(INDEX.rows(conn, core=True)),
            "rows": len(INDEX.rows(conn))}


def _cache_keys():
    """``build_dir -> {texture name: DDS_cache key}`` from the store's
    notes (the full textures a build left in ``DDS_cache``)."""
    users = _keys_by_texture(DDSC.key_users())

    def keys(build_dir):
        own = os.path.abspath(build_dir)
        return {name: found[-1] for (where, name), found in users.items()
                if where == own}
    return keys


def _rebuild_rows(conn, tiles, cache_keys=None) -> None:
    """The index rows of ``tiles`` (``(build_dir, lat, lon)``) rebuilt from
    disk, and their airport cores marked."""
    INDEX.rebuild(conn, tiles, placeholder_root=_placeholder_root(),
                  cache_keys=cache_keys)
    for build_dir, lat, lon in tiles:
        tile = FNAMES.short_latlon(lat, lon)
        INDEX.set_core(conn, tile, CORES.core_names(
            INDEX.rows(conn, tile=tile), CORES.airport_points(lat, lon),
            CORES.base_zoom(build_dir, lat, lon)))


def register_tiles(tiles, index: Optional[str] = None) -> int:
    """Write the index rows of ``tiles`` just converted to on-demand form
    (``imagery_convert``) or just built in on-demand mode
    (``imagery_after_build``): the scan's rebuild for those tiles only.
    Returns their rows."""
    conn = INDEX.open_index(index)
    try:
        _rebuild_rows(conn, list(tiles), _cache_keys())
        return sum(len(INDEX.rows(conn, tile=FNAMES.short_latlon(lat, lon)))
                   for (_d, lat, lon) in tiles)
    finally:
        conn.close()


def forget_tile(tile: str, index: Optional[str] = None) -> int:
    """Drop every index row of ``tile`` (a converted entry swapped back);
    the rows removed."""
    conn = INDEX.open_index(index)
    try:
        return INDEX.forget_tile(conn, tile)
    finally:
        conn.close()


def imagery_ondemand_scan(working_dir: str = "",
                          index: Optional[str] = None) -> Dict[str, Any]:
    """ENGINE COMMAND ``imagery_ondemand_scan``: rebuild the index rows of
    every on-demand tile under ``working_dir`` (default: the Tiles
    folder), mark the airport cores, reset interrupted fetches.

    :returns: ``{"tiles", "rows", "capped_bytes", "pinned_bytes",
        "cap_bytes", "core_rows", "reset"}``
    """
    tiles = list(on_demand_tiles(working_dir or FNAMES.Tile_dir))
    conn = INDEX.open_index(index)
    try:
        _rebuild_rows(conn, tiles, _cache_keys())
        reset = INDEX.reset_upgrading(conn)
        return {"tiles": len(tiles), "reset": reset, **_figures(conn)}
    finally:
        conn.close()


def _full_entry(keys) -> "Optional[tuple[str, str]]":
    """The first ``(key, entry)`` of ``keys`` the store holds as a whole
    full-width texture."""
    for key in reversed(keys or ()):
        entry = DDSC.entry_path(key)
        header = TIERS.texture_header(entry)
        if header and header[0] == TIERS.FULL_WIDTH and DDS.is_whole(entry):
            return key, entry
    return None


def _serve_full(conn, row: dict, keys) -> bool:
    """Land the full texture the cache holds for ``row``."""
    found = _full_entry(keys)
    path = INDEX.texture_path(row)
    if found is None or not path or not DDSC.serve(found[0], path):
        return False
    INDEX.set_state(conn, row["tile"], row["name"], "upgraded",
                    tier_px=TIERS.FULL_WIDTH,
                    full_bytes=DISK.counted_once_bytes(path),
                    dds_cache_key=found[0], fetched_at=time.time())
    return True


def imagery_pin(lat: int, lon: int, working_dir: str = "",
                pinned: bool = True,
                index: Optional[str] = None) -> Dict[str, Any]:
    """ENGINE COMMAND ``imagery_pin``: pin (or unpin) tile ``(lat, lon)``.
    A favorite (pinned) tile counts in the ortho budget and is made
    low-res last (RULINGS 2026-11-10c (2)); pinning
    lands every full texture the ``DDS_cache`` holds for it.

    :returns: ``{"tile", "pinned", "served", "to_fetch", "rows",
        "pinned_bytes"}``
    """
    from .world_built import tile_info
    # the one "is it built" answer: a World pack tile whose records are in
    # the data folder's Tiles/ is built whatever the working folder (#2027)
    info = tile_info(int(lat), int(lon), working_dir or FNAMES.Tile_dir)
    if info is None:
        raise ValueError("imagery_pin: this tile is not built.")
    _set_manifest_pin(info.build_dir, int(lat), int(lon), pinned)
    tile = FNAMES.short_latlon(int(lat), int(lon))
    conn = INDEX.open_index(index)
    try:
        if not INDEX.rows(conn, tile=tile):
            INDEX.rebuild(conn, [(info.build_dir, int(lat), int(lon))],
                          placeholder_root=_placeholder_root())
        INDEX.set_pinned(conn, tile, pinned)
        served = to_fetch = 0
        if pinned:
            users = _keys_by_texture(DDSC.key_users())
            own = os.path.abspath(info.build_dir)
            for row in INDEX.rows(conn, tile=tile):
                if row["tier_px"] >= TIERS.FULL_WIDTH:
                    continue
                if _serve_full(conn, row, users.get((own, row["name"]))):
                    served += 1
                else:
                    to_fetch += 1
        return {"tile": tile, "pinned": bool(pinned), "served": served,
                "to_fetch": to_fetch, "rows": len(INDEX.rows(conn, tile=tile)),
                "pinned_bytes": INDEX.pinned_bytes(conn)}
    finally:
        conn.close()


def _camera(camera_lat, camera_lon):
    if camera_lat is None or camera_lon is None:
        return None
    from types import SimpleNamespace
    return SimpleNamespace(lat=float(camera_lat), lon=float(camera_lon))


def imagery_ondemand_sweep(cap_gb: Optional[float] = None,
                           camera_lat: Optional[float] = None,
                           camera_lon: Optional[float] = None,
                           in_session: bool = False,
                           index: Optional[str] = None) -> Dict[str, Any]:
    """ENGINE COMMAND ``imagery_ondemand_sweep``: the cap sweep
    (``imagery_downgrade.sweep``) now, with ``cap_gb`` in place of the
    ``imagery_on_demand_cap_gb`` setting when given, sparing the squares
    near ``camera_lat`` / ``camera_lon`` when given.

    :returns: ``imagery_downgrade.sweep``'s reply
    """
    cap = (int(float(cap_gb) * 1e9) if cap_gb is not None
           else DOWNGRADE.cap_bytes())
    conn = INDEX.open_index(index)
    try:
        return DOWNGRADE.sweep(conn, BUDGET.measure(conn, cap),
                               camera=_camera(camera_lat, camera_lon),
                               in_session=bool(in_session))
    finally:
        conn.close()


def imagery_ondemand_downgrade_all(confirm: bool = False, dry_run: bool = False,
                                   lat: Optional[int] = None,
                                   lon: Optional[int] = None,
                                   camera_lat: Optional[float] = None,
                                   camera_lon: Optional[float] = None,
                                   index: Optional[str] = None) -> Dict[str, Any]:
    """ENGINE COMMAND ``imagery_ondemand_downgrade_all``: "Make all
    low-res again" -- every unpinned sharp texture (of tile ``(lat,
    lon)`` when given) back to its placeholder, except the squares near
    the camera when ``camera_lat`` / ``camera_lon`` are given.  Needs
    ``confirm=true`` or ``dry_run=true``.

    :returns: ``imagery_downgrade.downgrade_all``'s reply plus
        ``capped_bytes``
    """
    if not dry_run and not confirm:
        raise ValueError("Making imagery low-res again frees its space. Send "
                         "dry_run=true to see how much, then confirm=true.")
    camera = _camera(camera_lat, camera_lon)
    tile = (FNAMES.short_latlon(int(lat), int(lon))
            if lat is not None and lon is not None else None)
    conn = INDEX.open_index(index)
    try:
        out = DOWNGRADE.downgrade_all(conn, tile=tile, camera=camera,
                                      dry_run=bool(dry_run))
        out["capped_bytes"] = INDEX.capped_bytes(conn)
        return out
    finally:
        conn.close()
