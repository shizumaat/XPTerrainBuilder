"""Every finished build published into the World pack (flight manager /
World spec §4.1, §7.3), when there is one.

The build runs in its ordinary build folder; when it is done
(``BuildDone`` ok) and the app's World pack (made by ``world_install``,
``world_commands.managed``) is in the Custom Scenery folder and the tile
was built with imagery on demand, :func:`_publish_built` stages it
in the pack's shape (``O4_World_Pack.publish``: binary rewrite, verify)
and swaps it in, unless X-Plane may hold the tile (rule S3/S4): then it
waits staged and :func:`_swap_waiting` swaps it later.  After the swap:

* the tile's imagery manifest names the pack's folders
  (:data:`LAYOUT_KEY`), so the on-demand index rows read and land
  textures there (``O4_Imagery_OnDemand_Index`` resolves every texture
  path through them) and the tile's rows are re-registered;
* the tile's own ``zOrtho4XP_<tile>`` link to the same build folder is
  removed: the World pack draws the tile ("instead of a new
  ``zOrtho4XP_<tile>`` folder", §4.1); ``O4_Scenery_Links.install``
  links no tile the pack holds (``O4_World_Pack.holds_tile``).

The build folder stays (its rebuild data, record and the consumers of
spec §18 that read a build folder); removing it is a later phase.
"""
from __future__ import annotations

import contextlib
import json
import os
import queue
import threading
from typing import Any, Callable, Optional

import O4_Build_Profile as PROFILE
import O4_Imagery_OnDemand_Index as INDEX
import O4_World_Pack as WP

from . import imagery_follow as FOLLOW
from . import world_commands as WORLD

__all__ = ["LAYOUT_KEY", "watch", "write_layout"]

#: The imagery-manifest key naming a published tile's pack folders (the
#: index's reader owns the name).
LAYOUT_KEY = INDEX.LAYOUT_KEY


def _manifest_path(build_dir: str, lat: int, lon: int) -> str:
    return os.path.join(build_dir, "Ortho4XP_%s_imagery.json"
                        % WP.tile_name(lat, lon))


def write_layout(build_dir: str, lat: int, lon: int,
                 pack: Optional[str]) -> bool:
    """Name the pack's folders of the tile in its imagery manifest
    (``pack`` None: remove the name).  ``False`` without a manifest."""
    path = _manifest_path(build_dir, lat, lon)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    tile = WP.tile_name(lat, lon)
    if pack:
        data[LAYOUT_KEY] = {
            "textures_dir": os.path.join(pack, "textures", tile),
            "terrain_dir": os.path.join(pack, "terrain", tile)}
    else:
        data.pop(LAYOUT_KEY, None)
    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=1)
    os.replace(partial, path)
    return True


def _on_demand(build_dir: str, lat: int, lon: int) -> bool:
    from .imagery_after_build import _on_demand as on_demand
    return on_demand(build_dir, lat, lon)


def _after_swap(scenery_dir: str, build_dir: str, lat: int, lon: int) -> None:
    import O4_Scenery_Links as LINKS

    from . import imagery_ondemand as ONDEMAND
    write_layout(build_dir, lat, lon, WORLD.pack_dir(scenery_dir))
    with contextlib.suppress(Exception):     # the index is a cache
        ONDEMAND.register_tiles([(build_dir, lat, lon)])
    with contextlib.suppress(ValueError, OSError):
        LINKS.uninstall(lat, lon, build_dir, scenery_dir)


def _publish_built(scenery_dir: str, build_dir: str, lat: int, lon: int,
                  kind: str = "full",
                  loaded: Optional[Callable[[int, int], bool]] = None
                  ) -> Optional[dict]:
    """Publish one built tile (see the module docstring); ``None`` when
    there is no World pack or the tile was not built on demand."""
    if not WORLD.managed(scenery_dir) or not _on_demand(build_dir, lat, lon):
        return None
    pack = WORLD.pack_dir(scenery_dir)
    if loaded is None:
        loaded = WORLD.tile_loaded(scenery_dir)
    # S7: the follow job waits for THIS tile only while it is swapped.
    with FOLLOW.paused("world publish", tiles=[WP.tile_name(lat, lon)]):
        result = WP.publish(pack, build_dir, lat, lon,
                            staging_root=WORLD.staging_root(), kind=kind,
                            loaded=loaded)
    if result["state"] == "swapped":
        _after_swap(scenery_dir, build_dir, lat, lon)
    WORLD.write_log({"publish": result["tile"], "kind": kind,
                     "state": result["state"], "build_dir": build_dir,
                     "problems": result["problems"][:5]})
    return result


def _swap_waiting(scenery_dir: str, build_dir_of: Callable[[int, int], str],
                 loaded: Optional[Callable[[int, int], bool]] = None) -> list:
    """Swap in every staged tile X-Plane can no longer hold; the tiles."""
    if not WORLD.managed(scenery_dir):
        return []
    pack = WORLD.pack_dir(scenery_dir)
    done = WP.swap_staged(pack, WORLD.staging_root(),
                          loaded or WORLD.tile_loaded(scenery_dir))
    for name in done:
        lat, lon = WP.parse_tile(name)
        _after_swap(scenery_dir, build_dir_of(lat, lon), lat, lon)
        WORLD.write_log({"swap_in": name, "from": "staged"})
    return done


def watch(session: Any,
          scenery_dir: Callable[[], str] = WORLD.scenery_dir_or_default
          ) -> None:
    """Subscribe to ``session``: each tile built ok is published on one
    worker thread, in build order, and the tiles still staged are retried;
    a ``WorldStatus`` follows each."""
    jobs: "queue.Queue[tuple]" = queue.Queue()

    def work() -> None:
        while True:
            lat, lon, where, kind = jobs.get()
            try:
                result = _publish_built(where, session.tile_build_dir(lat, lon),
                                       lat, lon, kind)
                if result is not None:
                    swap = ((result["tile"], kind, _utc())
                            if result["state"] == "swapped" else ())
                    # Tiles staged earlier swap in now if they may (S3);
                    # the build-ahead job (W2) retries them on its own.
                    _swap_waiting(where, session.tile_build_dir)
                    session._emit(WORLD.status_event(where, last_swap=swap))
            except Exception as error:      # logged; the build is done
                WORLD.write_log({"publish_error": repr(error)[:300],
                                 "tile": WP.tile_name(lat, lon)})

    # The worker starts with the first job, not at subscription: a
    # window that never builds holds no thread (CI leaked one per test
    # window, 98 at #2004's crash, hiding the faulting thread's stack).
    started = threading.Lock()
    worker: list = []

    def enqueue(job: tuple) -> None:
        jobs.put(job)
        with started:
            if not worker:
                worker.append(threading.Thread(
                    target=work, daemon=True, name="o4-world-publish"))
                worker[0].start()

    def on_event(event) -> None:
        if (type(event).__name__ == "BuildDone" and event.ok
                and not getattr(session, "_stepwise_run", False)):
            # The Custom Scenery folder as configured NOW, on the
            # emitting thread (not when the worker gets to it), and the
            # kind the build's profile makes (a light tile, World spec
            # §8.4), read while the run still holds its overrides.
            lat, lon = int(event.lat), int(event.lon)
            overrides = getattr(session, "tile_overrides",
                                lambda la, lo: {})(lat, lon)
            enqueue((lat, lon, scenery_dir(), PROFILE.profile_of(overrides)))
    session.subscribe(on_event)


def _utc() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
