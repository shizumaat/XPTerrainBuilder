"""The aircraft's own tile, the facts behind the Fly pane's "Preparing
imagery at ..." with no plan (#2020, owner 2026-11-12T14:38Z: open X-Plane
at an airport with no scenery, and the app says imagery is being
prepared there, low resolution first, then the airport at high
resolution).

:func:`describe` completes ``world_job.WorldJob.here`` (the job's view of
the tile: its pack kind and build) with what lies on disk and around it:

* ``airport`` -- the nearest airport of the engine's airport index
  (``O4_Airport_Index``, built by ``airport_index``) within
  :data:`NEAR_KM` of the aircraft, "" none (a heliport or seaplane base
  only when nothing else is near);
* ``squares`` / ``sharp`` -- the texture squares installed for the tile
  (where X-Plane reads them, ``live_preview_commands.tile_folders``)
  whose centre lies within the full tier's crossing
  (``O4_Imagery_Tier_Plan.CROSSING_S[-1]`` square sizes: the core a
  parked aircraft is given, ``O4_World_Drape_Fetch.core_squares``) of the
  aircraft, and how many of them are at full resolution
  (``O4_DDS_Tiers.FULL_WIDTH``);
* ``reload_offer`` -- the pending reload offer (``reload_offer.current``),
  so the pane offers it although the follow job does not run.

The words are ``O4_Fly_Text.here_lines`` / SceneryKit
``FlyText.hereLines``.  General: no airport or tile is named.
"""
from __future__ import annotations

import contextlib
import math
import os
import threading
from typing import Optional

import O4_DDS_Tiers as TIERS
import O4_Imagery_Tier_Plan as PLAN
import O4_Live_Preview as LIVE
import O4_World_Drape_Fetch as FETCH

__all__ = ["NEAR_KM", "describe"]

#: An airport is "here" within this distance of the aircraft.
NEAR_KM = 8.0
_KM_PER_DEG = 111.32
_SIDE = ("heliport", "seaplane_base")
_INDEX: dict = {"key": None, "rows": ()}
_LOCK = threading.Lock()


def _airports() -> tuple:
    """``(code, lat, lon, category)`` of the airport index, reread when
    its file changes."""
    import O4_Airport_Index as INDEX
    import O4_File_Names as FNAMES
    path = FNAMES.airport_index_cache()
    try:
        st = os.stat(path)
    except OSError:
        return ()
    key = (path, st.st_mtime_ns, st.st_size)
    with _LOCK:
        if _INDEX["key"] != key:
            _INDEX["rows"] = tuple((e.code, e.lat, e.lon, e.category)
                                   for e in INDEX.load_index(path))
            _INDEX["key"] = key
        return _INDEX["rows"]


def nearest_airport(lat: float, lon: float, rows=None) -> str:
    """The code of the airport nearest ``(lat, lon)`` within
    :data:`NEAR_KM` (see the module), "" none.  ``rows``: ``(code, lat,
    lon, category)`` (default: the engine's airport index)."""
    rows = _airports() if rows is None else rows
    span = NEAR_KM / _KM_PER_DEG
    scale = math.cos(math.radians(lat))
    best: dict = {}
    for code, a_lat, a_lon, category in rows:
        if abs(a_lat - lat) > span or abs(a_lon - lon) * scale > span:
            continue
        km = math.hypot(a_lat - lat, (a_lon - lon) * scale) * _KM_PER_DEG
        side = category in _SIDE
        if km <= NEAR_KM and (side not in best or km < best[side][0]):
            best[side] = (km, code)
    found = best.get(False) or best.get(True)
    return found[1] if found else ""


def core_counts(folders, lat: float, lon: float) -> tuple:
    """``(squares, sharp)``: the squares of ``folders`` (a tile's texture
    folders) in the full-resolution core around ``(lat, lon)``, and how
    many of them are at full resolution."""
    by_zl: dict = {}
    for square in LIVE.tile_squares(folders):
        by_zl.setdefault(square["zl"], {})[
            (square["col"], square["row"])] = square["path"]
    total = sharp = 0
    for zl, paths in by_zl.items():
        for xy in FETCH.core_squares(list(paths), zl, lat, lon,
                                     PLAN.CROSSING_S[-1]):
            total += 1
            header = TIERS.texture_header(paths[xy])
            sharp += bool(header and header[0] >= TIERS.FULL_WIDTH)
    return total, sharp


def describe(here: Optional[dict], scenery_dir: str) -> Optional[dict]:
    """``here`` with ``airport``, ``squares``, ``sharp`` and
    ``reload_offer`` (see the module); None stays None.  A fact that
    cannot be read keeps its empty value."""
    if not here:
        return here
    from . import reload_offer as RELOAD
    out = dict(here, airport="", squares=0, sharp=0,
               reload_offer=RELOAD.current())
    lat, lon = float(here["lat"]), float(here["lon"])
    with contextlib.suppress(Exception):
        out["airport"] = nearest_airport(lat, lon)
    with contextlib.suppress(Exception):
        from .live_preview_commands import tile_folders
        from .world_commands import scenery_dir_or_default
        folders = tile_folders(scenery_dir_or_default(scenery_dir))(
            math.floor(lat), math.floor(lon))
        out["squares"], out["sharp"] = core_counts(folders, lat, lon)
    return out
