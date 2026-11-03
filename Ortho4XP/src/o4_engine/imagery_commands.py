"""Imagery commands: the launch-time liveness check (protocol 1.17, #1345)
and the tile info's imagery check (protocol 1.24, #1666).

``imagery_source_status`` replies ``{"started": true, "count": N}`` at
once; one ``ImagerySourceStatus`` event per source follows from worker
threads (``O4_Imagery_Sources.check_status``).

``imagery_freshness`` replies ``{"status": "started"}``; a worker thread
completes it with ``ImageryFreshnessReady`` carrying the command's id and
``O4_Imagery_Freshness.tile_freshness``'s answer.  ``imagery_freshness_
discard`` ("Update Imagery") removes the tile's cached orthophotos and
base textures so the rebuild the app starts next downloads them again;
synchronous file work.

A command module, not a session method, so the imagery menus stay out of
the session's import closure (the patch and step code keys,
``tests/test_patch_code_closure.py``).
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional, Sequence

import O4_Imagery_Sources as SOURCES

from .events import ImageryFreshnessReady, ImagerySourceStatus


def start_imagery_source_status(emit: Callable[[Any], None],
                                codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Start the check; ``emit`` receives each ImagerySourceStatus."""
    return SOURCES.check_status(
        lambda code, status, reason: emit(ImagerySourceStatus(
            code=code, status=status, reason=reason)), codes=codes)


def _tile_imagery(info):
    """``(build_dir, provider, zl)`` the built tile was made with, or None."""
    import O4_Tile_Info as TINFO
    imagery = TINFO.effective_imagery(info) if info is not None else None
    if imagery is None:
        return None
    return info.build_dir, imagery[0], imagery[1]


def freshness_for_info(info, force: bool = False, **options) -> Dict[str, Any]:
    """The imagery check of one scanned tile (``O4_Tile_Info.TileInfo``);
    the Qt pane's worker calls it with the tile it already has."""
    import O4_Imagery_Freshness as FRESH
    tile = _tile_imagery(info)
    if tile is None:
        return {"status": FRESH.UNKNOWN, "label": FRESH.LABELS[FRESH.UNKNOWN],
                "detail": "This tile is not built."}
    return FRESH.tile_freshness(info.lat, info.lon, *tile, force=bool(force), **options)


def _imagery_freshness(lat: int, lon: int, working_dir: str,
                      force: bool = False, **options) -> Dict[str, Any]:
    """The tile's imagery check, the tile found under ``working_dir``."""
    import O4_Tile_Info as TINFO
    return freshness_for_info(TINFO.tile_info(int(lat), int(lon), working_dir),
                              force=force, **options)


def discard_for_info(info) -> Dict[str, Any]:
    """"Update Imagery" for one scanned tile: what was removed."""
    import O4_Imagery_Freshness as FRESH
    tile = _tile_imagery(info)
    if tile is None:
        raise ValueError("imagery_freshness_discard: this tile is not built.")
    return FRESH.discard_tile_imagery(info.lat, info.lon, *tile)


def start_imagery_freshness(emit: Callable[[Any], None], lat: int, lon: int,
                            working_dir: str, force: bool = False,
                            request: Any = None) -> Dict[str, Any]:
    """The command: ``{"status": "started"}``; ImageryFreshnessReady follows."""
    def work():
        try:
            event = ImageryFreshnessReady(request=request, result=_imagery_freshness(
                lat, lon, working_dir, force=force))
        except Exception as error:      # the event carries it; the session lives on
            event = ImageryFreshnessReady(request=request, error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-imagery-freshness").start()
    return {"status": "started"}


def imagery_freshness_discard(lat: int, lon: int, working_dir: str) -> Dict[str, Any]:
    """"Update Imagery": what was removed (``jpegs``, ``textures``)."""
    import O4_Tile_Info as TINFO
    return discard_for_info(TINFO.tile_info(int(lat), int(lon), working_dir))
