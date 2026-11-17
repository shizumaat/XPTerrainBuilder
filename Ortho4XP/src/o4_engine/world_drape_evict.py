"""World drapes the disk budget gives back (#2142 Q3; owner 2026-11-17
18:47Z: "Yes, disk budget should turn least recently flown drapes back
into placeholders (with first option to offload to external volume
storage if available)").

A drape (``O4_World_Drape``) is re-made from the network in about a
minute and a half, so it is the first FLYABLE thing the budget gives
back -- after the shared caches, before any built tile's own data
(``storage_priority.clear``):

* :func:`_drapes` -- the pack's drape tiles with their bytes and when each
  was last FLOWN: the newest ``last_near_at`` / ``fetched_at`` of its
  rows in the on-demand index (the follow job stamps a row when the
  camera comes near it), else its DSF's time (when it was swapped in).
* :func:`_keep_now` -- never given back: the tiles of X-Plane's window now
  and the spawn set around the aircraft (``world_job_run``'s running job,
  ``world_spawn_window.spawn_set``), and every tile X-Plane loaded this
  session (rule S4: it may hold the files).
* :func:`_evict` -- least recently flown first: the tile's files (DSF,
  ``terrain/<tile>/``, ``textures/<tile>/``, its imagery record) are
  first COPIED to a mounted storage tier with room
  (``<mount>/XPTerrainBuilder Tier/World_drapes/<tile>/``, the pack's own
  layout; ``storage_tiers``), then the placeholder goes over the DSF and
  the local files go.  Only when no tier is mounted, or none has room,
  is the drape simply reverted.  A ``tier_only`` sweep (the free-space
  floor's offload pass) reverts nothing.  The tile's index rows go
  (``imagery_follow_drape.forget``).
* :func:`recall` -- the World job about to drape a placeholder first
  asks here: a tier copy is laid into the staging folder (the job then
  verifies and swaps it as any drape) and leaves the tier.

No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import time
from typing import Callable, Iterable, Optional

import O4_World_Imagery_Record as IREC
import O4_World_Pack as WP

from . import storage_tiers as TIERS

__all__ = ["TIER_SUBDIR", "recall",
           "budget_step", "pack_bytes"]

#: The drapes' folder in a tier (beside ``DDS_cache``).
TIER_SUBDIR = "World_drapes"

Tile = tuple[int, int]


def _own(root: str, tile: Tile) -> list:
    """The tile's DSF, folders and imagery record under a pack-shaped
    ``root``, the DSF first (``O4_World_Pack_Off``'s layout)."""
    name = WP.tile_name(*tile)
    return [os.path.join(root, WP.dsf_relpath(*tile)),
            os.path.join(root, "terrain", name),
            os.path.join(root, "textures", name),
            IREC.record_path(root, *tile)]


def _size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for folder, _dirs, names in os.walk(path):
        for name in names:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(folder, name)).st_size
    return total


def _flown_times() -> dict:
    """``{tile: newest last_near_at / fetched_at}`` from the index."""
    import O4_File_Names as FNAMES

    from . import storage as STORAGE
    conn = STORAGE._ondemand_index()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT tile, MAX(MAX(COALESCE(last_near_at, 0)), "
            "MAX(COALESCE(fetched_at, 0))) FROM textures GROUP BY tile"
        ).fetchall()
    except Exception:                       # an old index: none read
        rows = []
    finally:
        conn.close()
    out = {}
    for key, when in rows:
        pair = FNAMES.parse_tile_key(key)
        if pair is not None:
            out[tuple(pair)] = float(when or 0.0)
    return out


def _drapes(pack: str, flown: Optional[dict] = None) -> list:
    """``[(last flown, bytes, tile)]`` of the pack's drape tiles."""
    flown = _flown_times() if flown is None else flown
    out = []
    for tile, kind in WP.world_tiles(pack).items():
        if kind != "drape":
            continue
        files = _own(pack, tile)
        with contextlib.suppress(OSError):
            when = max(flown.get(tile, 0.0), os.path.getmtime(files[0]))
            out.append((when, sum(_size(p) for p in files), tile))
    return out


def _order(rows: Iterable, keep: set) -> list:
    """``rows`` (:func:`_drapes`) least recently flown first, ``keep``
    left out."""
    return sorted(r for r in rows if r[2] not in keep)


def _keep_now(scenery_dir: str) -> set:
    """The tiles never given back now (see the module)."""
    from . import world_commands as WORLD
    from . import world_job_run as RUN
    from . import world_spawn_window as SPAWN
    keep: set = set()
    with contextlib.suppress(Exception):
        keep |= set(WORLD._witness(scenery_dir)[0])
    runner = RUN._RUNNER
    if runner is not None:
        job = runner.job
        keep |= set(job.tracker.window())
        if job.position is not None:
            keep |= SPAWN.spawn_set(*job.position)
    return keep


def _tier_home(mount: str, tile: Tile) -> str:
    return os.path.join(mount, TIERS.TIER_DIR, TIER_SUBDIR,
                        WP.tile_name(*tile))


def _copy_out(pack: str, tile: Tile, size: int) -> str:
    """The tile's files copied to the first mounted tier with room, its
    tier folder (``""``: none took it).  Copied under a partial folder,
    checked, then renamed."""
    for mount, gigabytes in TIERS._configured().items():
        if not TIERS._mounted(mount):
            continue
        if TIERS._used(mount) + size > gigabytes * TIERS._GB:
            continue                        # full: the next tier, or revert
        home = _tier_home(mount, tile)
        partial = home + ".part"
        try:
            shutil.rmtree(partial, ignore_errors=True)
            for src, dst in zip(_own(pack, tile), _own(partial, tile),
                                strict=True):
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                elif os.path.isfile(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            if _size(partial) != size:
                raise OSError("short copy")
            shutil.rmtree(home, ignore_errors=True)
            os.replace(partial, home)
        except OSError:
            shutil.rmtree(partial, ignore_errors=True)
            continue
        TIERS._add_used(mount, size)
        return home
    return ""


def _revert(pack: str, tile: Tile) -> None:
    """The placeholder over the DSF first, then the tile's files gone."""
    from . import imagery_follow_drape as DRAPE_ROWS
    _dsf, *rest = _own(pack, tile)
    WP.write_placeholder(pack, *tile)
    for path in rest:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)
    with contextlib.suppress(Exception):    # the index is a cache
        DRAPE_ROWS.forget(*tile)


def _evict(need: int, pack: str, keep: set, *, dry_run: bool = False,
          tier_only: bool = False, flown: Optional[dict] = None,
          log: Callable[[dict], None] = lambda r: None) -> dict:
    """Give back drapes until ``need`` bytes are freed (see the module):
    ``{"freed", "offloaded", "reverted"}`` (tile names)."""
    done = {"freed": 0, "offloaded": [], "reverted": []}
    for _when, size, tile in _order(_drapes(pack, flown), keep):
        if done["freed"] >= need:
            break
        name = WP.tile_name(*tile)
        if dry_run:
            done["freed"] += size
            continue
        home = _copy_out(pack, tile, size)
        if not home and tier_only:
            continue
        _revert(pack, tile)
        done["freed"] += size
        done["offloaded" if home else "reverted"].append(name)
        log({"drape_evicted": name, "bytes": size, "tier": home or None})
    return done


def recall(tile: Tile, staged: str) -> bool:
    """Lay a tier's copy of ``tile`` out as the staged folder ``staged``
    (it must not exist) and drop it from the tier; whether one was there.
    The caller verifies and swaps it as a fresh drape."""
    for mount in TIERS._configured():
        home = _tier_home(mount, tile)
        if not TIERS._mounted(mount) or not os.path.isfile(
                _own(home, tile)[0]):
            continue
        size = _size(home)
        try:
            shutil.copytree(home, staged)
        except OSError:
            shutil.rmtree(staged, ignore_errors=True)
            continue
        shutil.rmtree(home, ignore_errors=True)
        TIERS._add_used(mount, -size)
        return True
    return False


def budget_step(need: int, sweep, now: Optional[float] = None) -> int:
    """``storage_priority``'s drape phase: :func:`_evict` on the World
    pack the app uses, as ``sweep`` asks (dry run, offload only); the
    bytes freed.  Nothing when no World pack is installed."""
    from . import world_commands as WORLD
    del now
    scenery_dir = WORLD.scenery_dir_or_default()
    if need <= 0 or not WORLD.managed(scenery_dir):
        return 0
    pack = WORLD.pack_dir(scenery_dir)
    started = time.monotonic()
    done = _evict(need, pack, _keep_now(scenery_dir), dry_run=sweep.dry_run,
                 tier_only=bool(getattr(sweep, "tier_only", False)),
                 log=WORLD.write_log)
    if done["offloaded"] or done["reverted"]:
        WORLD.write_log({"drapes_given_back": done,
                         "s": round(time.monotonic() - started, 1)})
    return int(done["freed"])


def pack_bytes() -> int:
    """Bytes the World pack's drapes hold (the budget counts them)."""
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default()
    if not WORLD.managed(scenery_dir):
        return 0
    return sum(r[1] for r in _drapes(WORLD.pack_dir(scenery_dir), flown={}))
