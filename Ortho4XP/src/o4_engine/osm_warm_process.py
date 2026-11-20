"""The parallel run's OpenStreetMap warm, done in a process of its own
(lane lscale, owner 2026-11-20T18:33-18:40Z: "an active dialog should take
precedence over any builds which should be in the background").

The warmer (``parallel.ParallelBuildRun._warm_queued_tiles``) downloads a
queued tile's OSM layer caches while the run's workers are busy.  A
layer's download is an Overpass conversation plus the XML parse and the
cache write (``O4_OSM_Utils.OSM_queries_to_OSM_layer``), Python work that
holds the interpreter lock for most of it; on a thread of the engine's
COMMAND process it ran beside the app's commands and dialog answers (the
owner's 1.0.568 run of 2026-11-20: the command process at 282 % CPU while
its two build workers idled).  Here each layer runs in a spawned worker of
the engine's work pool (``command_process.CommandProcess``, set up as a
World drape's worker is: ``world_drape_process._worker_setup``), and the
warmer's thread only waits on its pipe.  The parent keeps the token, the
claim and the between-layer stop checks; the worker re-reads the tile's
configuration and its layer list itself (the same
``O4_Vector_Map.osm_layer_warm_specifications``).

:func:`open_runner` is what the warmer calls; tests substitute
:class:`InProcess` (their stubbed modules live in the test's process).
"""
from __future__ import annotations

import sys

__all__ = ["InProcess", "WarmProcess", "open_runner", "warm_layer"]

#: Seconds a layer's worker may go without answering (an Overpass layer
#: waits out its server's queue and eight attempts: tens of minutes).
STALL_S = 3600.0


def warm_layer(lat: int, lon: int, build_dir: str, index: int) -> bool:
    """Fill tile ``(lat, lon)``'s ``index``-th warm layer cache; False when
    the tile has no such layer.  Runs in the warm worker (or in process,
    :class:`InProcess`)."""
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP
    tile = CFG.Tile(lat, lon, build_dir)
    tile.read_from_config()
    specifications = VMAP.osm_layer_warm_specifications(tile)
    if index >= len(specifications):
        return False
    (suffix, queries, tags, node_tags, schema) = specifications[index]
    OSM.OSM_queries_to_OSM_layer(
        queries, OSM.OSM_layer(), lat, lon, tags, cached_suffix=suffix,
        node_tags_of_interest=node_tags, cache_schema=schema)
    return True


class WarmProcess:
    """One spawned worker for one tile's layers; :meth:`close` is bounded."""

    def __init__(self):
        import O4_File_Names as FNAMES
        import O4_Imagery_Utils as IMG

        from .command_process import CommandProcess
        from .world_drape_process import _worker_setup
        self._process = CommandProcess(
            out=lambda line: print("[warm]", line, file=sys.stderr),
            stall_s=STALL_S, setup=_worker_setup,
            setup_args=(FNAMES.current_data_root(),
                        IMG.shared_tile_cache_dir))

    def layer(self, lat: int, lon: int, build_dir: str, index: int) -> bool:
        """:func:`warm_layer` in the worker; its error is raised here."""
        return self._process.run(warm_layer, what="OpenStreetMap warm",
                                 lat=lat, lon=lon, build_dir=build_dir,
                                 index=index)

    def close(self) -> None:
        self._process.close()


class InProcess:
    """:class:`WarmProcess`'s calls, run on the calling thread."""

    def layer(self, lat: int, lon: int, build_dir: str, index: int) -> bool:
        return warm_layer(lat, lon, build_dir, index)

    def close(self) -> None:
        pass


def open_runner():
    """The warmer's runner for one tile (module level so tests substitute
    :class:`InProcess`)."""
    return WarmProcess()
