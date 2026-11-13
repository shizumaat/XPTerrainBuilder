"""A World or flight drape's imagery fetched in a process of its own
(#2037).

A drape's fetch (``O4_World_Drape_Fetch.fetch``: the request threads,
the async fetcher's loop, the JPEG decode and paste, the DDS conversion,
the water-mask polygons) and its provider blend (``world_blend``) are
Python work that holds the interpreter lock most of the time.  On a
thread of the engine they starved the imagery follow job's fetch loop:
on the owner's CYEG flight (2026-11-13, drapes beside the follower) one
Python-heavy thread beside the follower cut its requests from 42 to 5.1
a second (``tools/follow_contention_replay.py``).  Here each drape runs
in a spawned worker of the engine's work pool
(``command_process.CommandProcess``: spawn, bounded teardown, dies with
the engine), and the engine's thread only waits on a pipe.

The worker shares the engine's budgets: the session's slot directory
(``O4_Machine_Slots.ENV_DIR``, inherited) bounds its requests per
server, and the follow job's priority marks there go first.  It gets
the engine's data root and live-map tile cache before anything else is
imported (:func:`_worker_setup`), and the engine's configuration at each
call.  Its ``print`` lines go to standard error: the engine's standard
output is the JSON-lines protocol, which a child inherits.

:func:`fetch_drape` is the work itself (the tier, then a parked
aircraft's core at full resolution); it returns the fetch's record with
``core_squares`` and the blend's World pack record (``blend``: ``None``
when the tile blends toward nothing).  :func:`run` is what the World job
calls.
"""
from __future__ import annotations

import contextlib
import os
import sys
from typing import Optional, Tuple

__all__ = ["STALL_S", "fetch_drape", "run"]

#: Seconds a drape's worker may go without answering before it is
#: declared stuck (a drape took ~90 s at 1-3x on the CYYR replay; the
#: water alone may wait ``world_job_run.WATER_WAIT_S``).
STALL_S = 1800.0


def _worker_setup(data_root: str, tile_cache: Optional[str]) -> None:
    """In the worker, first: its standard output is standard error (the
    engine's is the protocol stream), the engine's data root and its
    live-map tile cache."""
    with contextlib.suppress(Exception):
        sys.stdout.flush()
    try:                        # a windowed app may have no stderr at all
        os.dup2(sys.stderr.fileno(), 1)
        sys.stdout = sys.stderr
    except (AttributeError, OSError, ValueError):
        sink = os.open(os.devnull, os.O_WRONLY)
        with contextlib.suppress(OSError):
            os.dup2(sink, 1)
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    import O4_File_Names as FNAMES
    if data_root:
        FNAMES.set_data_root(data_root)
    if tile_cache:
        import O4_Imagery_Utils as IMG
        IMG.shared_tile_cache_dir = tile_cache


def fetch_drape(engine: str, lat: int, lon: int, parent: str,
                zoomlevel: int, provider: str, drop: int,
                scenery_dir: str, water_wait_s: float,
                core: Optional[Tuple[float, float, float]] = None) -> dict:
    """Drape tile ``(lat, lon)``'s imagery at the tier ``drop``, with its
    water masks and its provider blend, then ``core`` ``(lat, lon,
    radius_s)`` again at full resolution; the fetch's record (module
    doc)."""
    import O4_World_Drape_Fetch as FETCH

    from . import world_commands as WORLD
    made: dict = {}
    tile = (int(lat), int(lon))

    def blend():                    # #2018: toward another provider's tile
        if "blend" not in made:
            from .world_blend import blend_for
            from .world_job_run import photo_source
            made["blend"] = blend_for(tile, provider, scenery_dir,
                                      photo_source, WORLD.write_log)
        return made["blend"]
    fetched = FETCH.fetch(engine, tile[0], tile[1], parent, int(zoomlevel),
                          provider, drop=drop, water_alpha=True,
                          water_wait_s=water_wait_s, blend=blend)
    if core is not None:
        cored = FETCH.fetch(engine, tile[0], tile[1], parent, int(zoomlevel),
                            provider, drop=0, water_alpha=True,
                            water_wait_s=water_wait_s, near=tuple(core),
                            blend=blend)
        fetched["core_squares"] = cored.get("squares")
    made_blend = made.get("blend")
    fetched["blend"] = made_blend.record() if made_blend is not None else None
    return fetched


def run(task=fetch_drape, **kwargs):
    """``task(**kwargs)`` (default :func:`fetch_drape`) in a worker
    process of its own, closed when it answers.  The task's error is
    raised here; a worker that died or went silent is a ``RuntimeError``
    (the World job logs it and retries the tile once)."""
    import O4_File_Names as FNAMES
    import O4_Imagery_Utils as IMG

    from .command_process import CommandProcess
    proc = CommandProcess(
        out=lambda line: print(line, file=sys.stderr), stall_s=STALL_S,
        setup=_worker_setup,
        setup_args=(FNAMES.current_data_root(), IMG.shared_tile_cache_dir))
    try:
        return proc.run(task, what="drape", **kwargs)
    finally:
        proc.close()
