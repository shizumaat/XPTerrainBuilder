"""THE TILE-WIDE NUMERIC LEVEL, CELL BY CELL ON A BORDER TILE (owner
RULINGS 2026-11-27e: "Everything should use the same list and fallbacks").

A numeric ``elevation_level`` fetches the whole tile in ONE request from
the ladder's first windowed provider
(:func:`O4_Elevation_Level.select_tile_overlay_definition`) -- unchanged,
byte for byte, while that provider is also the first windowed provider of
every 0.1 degree cell of the tile.  Where it is not -- a BORDER tile whose
cells the ladder hands to different providers -- or once the whole-tile
request answered no coverage, the overlay is fetched PER CELL through the
coastline band's own walk (:func:`O4_Elevation_Level._band_cell_sources`,
:func:`O4_Elevation_Level._band_cell_answered`): each cell asks the ladder
in order and falls through on no coverage, a fill or a failure, exactly
as the band and the airport insets do, and the answered cells are
mosaicked into one VRT the bake reads like the single raster.  The level
still chooses only the resolution.

Import discipline: :mod:`O4_Elevation_Level` imports this module lazily
(inside functions); this module imports it at the top.
"""

from __future__ import annotations

import collections
import datetime
import json
import os

import O4_Elevation_Level as ELEVATION_LEVEL
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

#: A 1 degree tile is a 10 x 10 grid of 0.1 degree cells.
_CELL_COUNT = 10


def cellular_overlay_path(lat, lon, definition, candidates,
                          target_resolution_m, single_path):
    """The cellular overlay's VRT path, or ``None`` for the single fetch.

    Cellular when some cell's first windowed ladder provider is not the
    tile's (``definition``), or when the whole-tile request is a recorded
    no-coverage negative in the overlay index.  Offline: the registry,
    the known footprints and the index -- the fetch and the bake agree.
    """
    import O4_Airport_Elevation_Insets as INSETS

    index = ELEVATION_LEVEL._read_overlay_index(
        FNAMES.tile_overlay_index(lat, lon))
    single_key = os.path.splitext(os.path.basename(single_path))[0]
    if index.get(single_key) != INSETS.NO_COVERAGE and not _is_border_tile(
            lat, lon, definition, candidates):
        return None
    return FNAMES.tile_overlay_cells_vrt(lat, lon, target_resolution_m)


def _is_border_tile(lat, lon, definition, candidates):
    """True when the ladder's first windowed provider of some cell is not
    the tile's ``definition`` (a cell no candidate reaches is no border)."""
    for column in range(_CELL_COUNT):
        for row in range(_CELL_COUNT):
            box = ELEVATION_LEVEL.approach_ring_cell_box(lat, lon, column, row)
            first = next(
                (candidate for candidate in candidates
                 if ELEVATION_LEVEL._definition_covers_box(candidate, box)),
                None,
            )
            if first is not None and first["code"] != definition["code"]:
                return True
    return False


def ensure_cellular_overlay(tile, plan):
    """Fetch (or recycle) every cell of a cellular overlay ``plan`` and
    mosaic the answered cells into ``plan["path"]``.  Per-cell outcomes
    live in the overlay index under each cell's stem (a durable negative
    is never re-asked; a raised failure is).  Returns the VRT path, or
    ``None`` when no cell could be fetched (the base stands)."""
    import O4_Airport_Elevation_Insets as INSETS

    lat, lon = tile.lat, tile.lon
    index_path = FNAMES.tile_overlay_index(lat, lon)
    index = ELEVATION_LEVEL._read_overlay_index(index_path)
    target_m = plan["target_resolution_m"]
    rung = ELEVATION_LEVEL.ApproachRung(
        float("inf"), target_m, ELEVATION_LEVEL.COASTLINE_FIXED_TIER)
    providers_config = getattr(tile, "airport_elevation_providers", "auto")

    def _discard(path, stem):
        try:
            os.remove(path)
        except OSError:
            pass
        index[stem] = INSETS.NO_COVERAGE
        UI.vprint(1, "   INFO: tile overlay cell", stem, "is one constant"
                  " value everywhere (a fill served beyond the provider's"
                  " true extent); recording no coverage.")

    answered = []
    for column in range(_CELL_COUNT):
        for row in range(_CELL_COUNT):
            cell = {"column": column, "row": row}
            for source in ELEVATION_LEVEL._band_cell_sources(
                lat, lon, column, row, rung, target_m, providers_config,
                cell_path=FNAMES.tile_overlay_cell_dem,
            ):
                if ELEVATION_LEVEL._band_cell_answered(
                    source, cell, lat, lon, index, _discard,
                    label="Tile overlay cell",
                ):
                    answered.append(dict(cell, **source))
                    break
    ELEVATION_LEVEL._write_overlay_index(index_path, index)
    if not answered:
        UI.lvprint(0, "   WARNING: elevation_level was requested but no"
                   " cell of the tile-wide elevation overlay could be"
                   " fetched; the build continues on the base elevation"
                   " source.")
        return None
    vrt_path = plan["path"]
    # The handle is released at the end of the statement: the virtual
    # mosaic is flushed to disk.
    ELEVATION_LEVEL.gdal.BuildVRT(
        vrt_path,
        [cell["path"] for cell in answered],
        options=ELEVATION_LEVEL.gdal.BuildVRTOptions(
            resolution="highest", resampleAlg="bilinear",
            srcNodata=-32768, VRTNodata=-32768,
        ),
    )
    providers = _cell_providers_count(answered)
    with open(_sidecar_path(vrt_path), "w", encoding="utf-8", newline="\n") as handle:
        json.dump({
            "cells": {cell["stem"]: cell["code"] for cell in answered},
            "providers": providers,
            "target_resolution_m": target_m,
            "fetch_date": datetime.date.today().isoformat(),
        }, handle, indent=2, sort_keys=True)
    index[os.path.splitext(os.path.basename(vrt_path))[0]] = "ok"
    ELEVATION_LEVEL._write_overlay_index(index_path, index)
    UI.vprint(1, "   Tile elevation overlay fetched per cell (a border"
              " tile):", len(answered), "cell(s),", providers)
    return vrt_path


def _cell_providers_count(cells):
    """``{provider code: cells}`` of a cellular overlay's answered cells."""
    return dict(collections.Counter(cell["code"] for cell in cells))


def recorded_cell_providers(vrt_path):
    """The ``{provider: cells}`` record beside a cellular overlay VRT, or
    ``None`` when none was written."""
    try:
        with open(_sidecar_path(vrt_path), "r", encoding="utf-8") as handle:
            return json.load(handle).get("providers")
    except (OSError, ValueError):
        return None


def _sidecar_path(vrt_path):
    return os.path.splitext(vrt_path)[0] + ".json"
