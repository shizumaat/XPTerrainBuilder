"""TILE PRIORITY: what the disk budget clears first (#2087, owner
2026-11-14T16:57Z, refining RULINGS 2026-11-10d (3)):

    "Automatic cleanup, should be filling the storage budget before
    needing to remove anything, and then it should be removing things in
    priority order, so older things, tiles that are not favorites, etc.
    are removed first"

Over a budget the user set (``storage_budget.hold``), :func:`clear`
frees ``over_by`` bytes in two phases:

1. SHARED data -- every cache file that belongs to no one tile (temp,
   logs, previews, the texture cache, scenery dumps, airport pack caches,
   regional map extracts, and a tile store's file outside any tile
   folder), :data:`SHARED_TIERS` cheapest to rebuild first, least
   recently used first within a tier.
2. TILES, one at a time, in :func:`_ranked` order: non-favorites before
   favorites, then the tile used longest ago first (built, flown near or
   read: the newest of its files' times -- ``storage._last_used`` -- its
   DSFs and its sharp imagery's ``last_near_at`` / ``fetched_at`` in the
   on-demand index).  For that tile, :data:`TILE_STEPS` cheapest first:
   its orthophotos, its masks, its elevation and map data (an airport
   tile shrinks to its package there, ``storage_packages._package_tile``),
   its sharp imagery made low-res, its rebuild data -- and only then the
   next tile.

PROTECTED, never cleared (:func:`_protected`): a tile built or queued in
this engine session (:func:`note_session`, from ``session.build`` /
``enqueue_build``), a tile used in the last :data:`RECENT_DAYS` days
(that also covers a build another process is running: it writes its
tile's files now), and every input those tiles' builds read
(``tile_bundle.inputs.files``: their map data, elevation and the
neighbours' base rasters), whichever tile a file belongs to.  When what
is left to clear is protected, the budget stays over and
``storage.log`` says so.

Every deletion goes through the sweep (``storage._Sweep.delete``): a
built tile is packaged before its first file goes (``package_first``),
and a file moves to a mounted storage tier with room instead of being
deleted (``storage_tier_data``).  The floor (DSFs, placeholders,
patches, own elevation files) is in no cache store and is never read
here.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import O4_File_Names as FNAMES

from . import package_first as FIRST
from . import storage as STORAGE

__all__ = ["RECENT_DAYS", "SHARED_TIERS", "TILE_STEPS", "note_session",
           "session_tiles", "clear"]

#: A tile used this recently is never cleared: a week covers the tiles
#: being built, flown and fixed now (the owner's 2026-11-14 evidence:
#: tiles built hours earlier were packaged, a running build's inputs
#: deleted), while a tile untouched for longer is the "older thing" the
#: owner asked to go first.
RECENT_DAYS = 7
#: Phase 1, data tied to no one tile: cheapest to rebuild first.
SHARED_TIERS: tuple = (("tmp", "logs", "previews"), ("imagery", "dds"),
                       ("dsf_dumps", "masks", "airport_mod"),
                       ("elevation", "osm_extracts", "osm"),
                       (STORAGE.REBUILD,))
#: Phase 2, one tile's data: cheapest to rebuild first.
TILE_STEPS: tuple = (("imagery",), ("masks",), ("elevation", "osm"),
                     (STORAGE.ONDEMAND,), (STORAGE.REBUILD,))
_DAY = 86400.0
_SESSION: set = set()
_LOCK = threading.Lock()


def note_session(tiles) -> None:
    """Record ``tiles`` (``(lat, lon)`` pairs) as built or queued in this
    engine session: never cleared while it lives."""
    with _LOCK:
        _SESSION.update((int(t[0]), int(t[1])) for t in tiles)


def session_tiles() -> set:
    """The ``(lat, lon)`` tiles built or queued in this session."""
    with _LOCK:
        return set(_SESSION)


@dataclass
class _Tile:
    pair: tuple
    last_used: float = 0.0
    favorite: bool = False
    rows: dict = field(default_factory=dict)

    def saw(self, when: float) -> None:
        self.last_used = max(self.last_used, float(when or 0.0))


def _tile_of(store, path: str):
    """The ``(lat, lon)`` a cache file belongs to, or ``None`` (shared)."""
    if store.kind in FIRST.STORE_KINDS:
        tiles = FIRST._tiles_of(store.kind, path)
        return tiles[0] if tiles else None
    if store.kind in ("imagery", "masks"):          # <10 deg>/<tile>/...
        parts = FIRST._parts(path, store.path())
        return FNAMES.parse_tile_key(parts[1]) if len(parts) >= 3 else None
    return None


def _index_tiles(tiles: dict) -> None:
    """Each tile's sharp imagery times and favorite flag from the
    on-demand index."""
    conn = STORAGE._ondemand_index()
    if conn is None:
        return
    try:
        rows = conn.execute(
            "SELECT tile, MAX(COALESCE(last_near_at, 0)), "
            "MAX(COALESCE(fetched_at, 0)), MAX(pinned), "
            "SUM(state = 'upgraded') FROM textures GROUP BY tile").fetchall()
    except Exception:                       # an old index: none read
        rows = []
    finally:
        conn.close()
    for key, near, fetched, pinned, upgraded in rows:
        pair = FNAMES.parse_tile_key(key)
        if pair is None:
            continue
        if pair not in tiles and not upgraded:
            continue
        tile = tiles.setdefault(pair, _Tile(pair))
        tile.saw(max(near or 0, fetched or 0))
        tile.favorite = tile.favorite or bool(pinned)
        if upgraded:
            tile.rows[STORAGE.ONDEMAND] = True


def _dsf_times(tiles: dict) -> None:
    for pair, folder in FIRST.built_tiles().items():
        tile = tiles.setdefault(pair, _Tile(pair))
        for root, _dirs, names in os.walk(os.path.join(folder, "Earth nav data")):
            for name in names:
                try:
                    tile.saw(STORAGE._last_used(os.lstat(os.path.join(root, name))))
                except OSError:
                    continue


def _survey(now: float) -> tuple:
    """``(shared, tiles)``: ``{kind: [(store, path, stat)]}`` of the
    deletable shared files, and ``{(lat, lon): _Tile}``."""
    from .storage_packages import _favorites
    shared: dict = {}
    tiles: dict = {}
    for store in STORAGE.STORES:
        if store.policy != STORAGE.CACHE or store.kind == STORAGE.ONDEMAND:
            continue
        for path, st, deletable in STORAGE._files(store, now):
            pair = _tile_of(store, path)
            if pair is not None:
                tile = tiles.setdefault(pair, _Tile(pair))
                tile.saw(STORAGE._last_used(st))
                bucket = tile.rows.setdefault(store.kind, [])
            else:
                bucket = shared.setdefault(store.kind, [])
            if deletable:
                bucket.append((store, path, st))
    _dsf_times(tiles)
    _index_tiles(tiles)
    favorites = {FNAMES.parse_tile_key(k) for k in _favorites()}
    for pair, tile in tiles.items():
        tile.favorite = tile.favorite or pair in favorites
    return shared, tiles


def _protected(tiles: dict, now: float) -> set:
    """The tiles never cleared: this session's and the recently used."""
    recent = now - RECENT_DAYS * _DAY
    return session_tiles() | {p for p, t in tiles.items() if t.last_used >= recent}


def _protected_inputs(pairs) -> set:
    """Every input the builds of ``pairs`` read, normalised."""
    from tile_bundle import inputs as INPUTS
    keep = set()
    for lat, lon in pairs:
        try:
            keep |= {os.path.normcase(os.path.abspath(local))
                     for _name, local in INPUTS.files(lat, lon)}
        except OSError:
            continue
    return keep


def _ranked(tiles: dict, protected: set) -> list:
    """The clearable tiles, first to clear first."""
    return sorted((t for p, t in tiles.items() if p not in protected),
                  key=lambda t: (t.favorite, t.last_used, t.pair))


def _rows(rows, keep: set) -> list:
    return [r for r in rows
            if os.path.normcase(os.path.abspath(r[1])) not in keep
            and os.path.lexists(r[1])]


def _downgrade(tile: _Tile, sweep) -> int:
    """The tile's sharp imagery made low-res (favorites too: a favorite
    tile is cleared only after every other)."""
    from . import imagery_downgrade as DOWNGRADE
    conn = STORAGE._ondemand_index()
    if conn is None or sweep.dry_run:
        return 0
    try:
        result = DOWNGRADE.downgrade_all(
            conn, tile=FNAMES.short_latlon(*tile.pair), favorites=True,
            abort=sweep.abort, reason="disk budget, tile priority")
    finally:
        conn.close()
    sweep.downgraded(STORAGE._BY_KIND[STORAGE.ONDEMAND], result)
    return int(result.get("freed_bytes") or 0)


def _clear_tile(tile: _Tile, need: int, sweep, now: float, keep: set,
                candidate) -> int:
    """One tile's :data:`TILE_STEPS` until ``need`` bytes are freed."""
    from . import storage_packages as PACKAGES
    freed = 0
    for step in TILE_STEPS:
        if freed >= need or sweep.stopped:
            break
        if step == (STORAGE.ONDEMAND,):
            if tile.rows.get(STORAGE.ONDEMAND):
                freed += _downgrade(tile, sweep)
            continue
        if step == ("elevation", "osm") and candidate is not None:
            done = PACKAGES._package_tile(candidate, sweep, now, keep=keep)
            freed += int((done or {}).get("freed_bytes") or 0)
        rows = [r for kind in step for r in tile.rows.get(kind, ())]
        freed += STORAGE._evict_rows(_rows(rows, keep), need - freed, sweep)
    return freed


def clear(over_by: int, sweep, now: float) -> int:
    """Free ``over_by`` bytes, shared data first, then tile by tile in
    priority order (module doc); the bytes freed."""
    from . import storage_packages as PACKAGES
    shared, tiles = _survey(now)
    protected = _protected(tiles, now)
    keep = _protected_inputs(protected)
    freed = 0
    for tier in SHARED_TIERS:
        if freed >= over_by or sweep.stopped:
            break
        rows = [r for kind in tier for r in shared.get(kind, ())]
        freed += STORAGE._evict_rows(_rows(rows, keep), over_by - freed, sweep)
    candidates = None
    for tile in _ranked(tiles, protected):
        if freed >= over_by or sweep.stopped:
            break
        if sweep.abort():
            sweep.stopped = True
            break
        if candidates is None:
            candidates = {(c["lat"], c["lon"]): c for c in PACKAGES._candidates()}
        freed += _clear_tile(tile, over_by - freed, sweep, now, keep,
                             candidates.get(tile.pair))
    if not sweep.dry_run:
        for store in STORAGE.STORES:
            if store.policy == STORAGE.CACHE and store.kind != STORAGE.ONDEMAND:
                STORAGE._prune_empty_dirs(store.path())
    if freed < over_by and not sweep.stopped and not sweep.dry_run:
        STORAGE.write_log(
            "disk budget still over by %d bytes: the rest belongs to the %d "
            "tile(s) used in the last %d days or this session"
            % (over_by - freed, len(protected), RECENT_DAYS))
    return freed
