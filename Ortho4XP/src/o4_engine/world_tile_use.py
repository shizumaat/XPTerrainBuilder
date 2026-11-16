"""ENGINE COMMAND ``world_tile_use``: the map's tile menu "Use
XPTerrainBuilder here" on or off (#2100, owner 2026-11-15T19:19Z;
capability ``world_tile_use``).

Off: X-Plane draws its own scenery on the tile; the tile's built files
are kept aside in the World pack (``O4_World_Pack_Off``), so on again is
instant, with no rebuild.  While X-Plane may hold the tile (rule S3,
``world_commands.tile_loaded``, less ``O4_World_Pack.nothing_held``) the
change waits (``turning_off`` / ``turning_on``) and :func:`settle`
completes it: after each publish (``world_publish._swap_waiting``), on
the build-ahead job's status beat, at the apps' start (``world_onboard``)
and before each ``world_tile_use``.

While a tile is off nothing of ours draws it or works on it:

* the pack's ``world_tiles`` says ``off``: build-ahead never builds it
  (``world_job_run._Wanted`` builds placeholders only), a flight leaves it
  to X-Plane (``flight_manager._job_for``), Convert does not count it
  missing (``world_migrate.missing_from_pack``);
* a build the user asks for goes into its kept folder
  (``O4_World_Pack.swap_in`` / ``publish``), never into the pack, and its
  after-swap work (index rows, layout, links) waits for on
  (``world_publish._after_swap``);
* the follow job fetches no imagery for it (:func:`off_names`, read by
  ``imagery_follow.FollowJob._held``);
* no ``zOrtho4XP_<tile>`` link is made for it (``O4_Scenery_Links.install``);
* the map and Library read state ``off`` (``world_state``).

Sync: a few renames.  Every change is a line of ``logs/world_pack.log``.
No tile or airport is named here.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, Optional

import O4_World_Pack as WP
import O4_World_Pack_Off as OFF

__all__ = ["world_tile_use", "settle", "off_names", "OFF_NAMES_EVERY_S"]

#: How long :func:`off_names` keeps its answer (the follow job asks once a
#: second).
OFF_NAMES_EVERY_S = 5.0
_CACHE: Dict[str, object] = {"at": -1e18, "names": frozenset()}
_CACHE_GUARD = threading.Lock()


def _held(scenery_dir: str, pack: str,
          loaded: Optional[Callable[[int, int], bool]] = None
          ) -> Callable[[int, int], bool]:
    from . import world_commands as WORLD
    return WP.held_by_xplane(pack, loaded or WORLD.tile_loaded(scenery_dir))


def _forget_cache() -> None:
    with _CACHE_GUARD:
        _CACHE["at"] = -1e18


def settle(scenery_dir: str,
           loaded: Optional[Callable[[int, int], bool]] = None) -> list:
    """Complete every tile turning off or on that X-Plane now lets go of;
    ``[(tile name, "off" | "on")]``.  Reads one small file when nothing
    waits."""
    from . import imagery_follow as FOLLOW
    from . import world_commands as WORLD
    if not scenery_dir or not WORLD.managed(scenery_dir):
        return []
    pack = WORLD.pack_dir(scenery_dir)
    waiting = [key for key, state in OFF.off_tiles(pack).items()
               if state != OFF.OFF]
    if not waiting:
        return []
    names = [WP.tile_name(*key) for key in waiting]
    with FOLLOW.paused("world tile use", tiles=names):
        done = OFF.apply_pending(pack, _held(scenery_dir, pack, loaded))
    for name, state in done:
        WORLD.write_log({"tile_use": name, "state": state, "from": "pending"})
    if done:
        _forget_cache()
    return done


def world_tile_use(lat, lon, use: bool = True, scenery_dir: str = "",
                   **_ignored) -> Dict[str, object]:
    """ENGINE COMMAND: XPTerrainBuilder on (``use`` true) or off on tile
    ``(lat, lon)`` of the World pack.

    :returns: ``{"tile", "use", "state"}`` -- ``state`` ``on``, ``off``,
        ``turning_off`` or ``turning_on`` (``O4_World_Pack_Off``).
    :raises ValueError: no World pack, or (off) no DSF of the tile in it.
    """
    from . import imagery_follow as FOLLOW
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not WORLD.managed(scenery_dir):
        raise ValueError("The World pack is not installed.")
    lat, lon = int(lat), int(lon)
    settle(scenery_dir)
    pack = WORLD.pack_dir(scenery_dir)
    held = _held(scenery_dir, pack)
    with FOLLOW.paused("world tile use", tiles=[WP.tile_name(lat, lon)]):
        state = (OFF.turn_on(pack, lat, lon, held) if use
                 else OFF.turn_off(pack, lat, lon, held))
    _forget_cache()
    WORLD.write_log({"tile_use": WP.tile_name(lat, lon), "use": bool(use),
                     "state": state})
    return {"tile": WP.tile_name(lat, lon), "use": bool(use), "state": state}


def off_names(clock: Callable[[], float] = time.monotonic) -> frozenset:
    """The names (``+53-063``) of the World pack's tiles off, read at most
    every :data:`OFF_NAMES_EVERY_S` (the follow job holds them)."""
    now = clock()
    with _CACHE_GUARD:
        if now - float(_CACHE["at"]) < OFF_NAMES_EVERY_S:
            return _CACHE["names"]          # type: ignore[return-value]
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default()
    names = frozenset()
    if scenery_dir and WORLD.managed(scenery_dir):
        names = frozenset(WP.tile_name(*key) for key in
                          OFF.off_tiles(WORLD.pack_dir(scenery_dir)))
    with _CACHE_GUARD:
        _CACHE["at"], _CACHE["names"] = now, names
    return names
