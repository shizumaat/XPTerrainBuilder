"""Where a provider really has data: its footprint, not its coverage box.

A ``coverage_bbox`` is a rectangle, and a national provider's rectangle
reaches into its neighbours (#1466: SWISSALTI3D's box spans France and
Germany on +47+007).  :func:`covers_box` is the box test AND the
footprint, when one is known:

1. the strategy's own catalogue already on disk
   (``cached_source_boxes(definition)``: a tile index's source boxes);
2. a per-tile map of 0.1 degree cells written once by a PROBE
   (``probe_cell_coverage(definition, cell_boxes)`` on the strategy) into
   ``Elevation_data/footprints/<code>/<tile>.json``;
3. else unknown, and the box alone decides (the old behaviour).

Reading is offline; only :func:`ensure_tile_footprints` asks a server.
"""

import datetime
import json
import math
import os
import threading

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.definitions import _coverage_bbox_intersects

__all__ = [
    "FOOTPRINT_CELL_DEGREES",
    "covers_box",
    "ensure_tile_footprints",
    "footprint_answer",
    "forget_tile_footprints",
    "read_cached_json",
    "tile_cell_boxes",
]

#: The probe's cell: the ring and band cell (``COASTLINE_CELL_DEGREES``).
FOOTPRINT_CELL_DEGREES = 0.1

_CELLS_PER_DEGREE = int(round(1.0 / FOOTPRINT_CELL_DEGREES))

#: Overlap smaller than this (degrees) is an edge touch, not data.
_EDGE_EPSILON = 1e-9

_cache_lock = threading.Lock()
_json_cache: dict = {}


def tile_cell_boxes(lat, lon):
    """``{(column, row): (west, south, east, north)}`` of a tile's cells,
    the ring plan's own indexing (column along longitude)."""
    return {
        (column, row): (
            lon + column * FOOTPRINT_CELL_DEGREES,
            lat + row * FOOTPRINT_CELL_DEGREES,
            lon + (column + 1) * FOOTPRINT_CELL_DEGREES,
            lat + (row + 1) * FOOTPRINT_CELL_DEGREES,
        )
        for column in range(_CELLS_PER_DEGREE)
        for row in range(_CELLS_PER_DEGREE)
    }


def _interiors_overlap(box_a, box_b):
    (west_a, south_a, east_a, north_a) = box_a[:4]
    (west_b, south_b, east_b, north_b) = box_b[:4]
    return (min(east_a, east_b) - max(west_a, west_b) > _EDGE_EPSILON
            and min(north_a, north_b) - max(south_a, south_b)
            > _EDGE_EPSILON)


def footprint_path(code, lat, lon):
    """The probed cell map of one provider on one tile."""
    return os.path.join(
        FNAMES.Elevation_dir, "footprints", str(code).lower(),
        "%+03d%+04d.json" % (lat, lon))


def read_cached_json(path):
    """A JSON file, memoised on its mtime; ``None`` when absent or bad."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    with _cache_lock:
        cached = _json_cache.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError):
        value = None
    with _cache_lock:
        _json_cache[path] = (stamp, value)
    return value


def _strategy(definition):
    from elevation_access import registry as ea_registry

    factory = ea_registry.ACCESS_STRATEGIES.get(
        (definition or {}).get("access_strategy"))
    return factory() if factory is not None else None


def _catalogue_answer(strategy, definition, box):
    reader = getattr(strategy, "cached_source_boxes", None)
    if reader is None:
        return None
    boxes = reader(definition)
    if boxes is None:
        return None
    return any(_interiors_overlap(source, box) for source in boxes)


def _probed_answer(definition, box):
    (west, south, east, north) = box[:4]
    known_everywhere = True
    for lat in range(int(math.floor(south)), int(math.ceil(north))):
        for lon in range(int(math.floor(west)), int(math.ceil(east))):
            record = read_cached_json(footprint_path(definition["code"], lat, lon))
            if not isinstance(record, dict):
                known_everywhere = False
                continue
            cells = tile_cell_boxes(lat, lon)
            for (column, row) in record.get("covered") or []:
                cell = cells.get((int(column), int(row)))
                if cell is not None and _interiors_overlap(cell, box):
                    return True
    return False if known_everywhere else None


def footprint_answer(definition, box):
    """``True`` / ``False`` when the provider's footprint is known to
    overlap / miss ``box``; ``None`` when it is not known (offline)."""
    strategy = _strategy(definition)
    if strategy is not None:
        answer = _catalogue_answer(strategy, definition, box)
        if answer is not None:
            return answer
    if not (definition or {}).get("code"):
        return None
    return _probed_answer(definition, box)


def covers_box(definition, box):
    """Does the provider reach ``box``: its declared box AND, when known,
    its footprint (#1466)."""
    if not _coverage_bbox_intersects(definition, box):
        return False
    return footprint_answer(definition, box) is not False


def _probe_tile(strategy, definition, lat, lon):
    cells = tile_cell_boxes(lat, lon)
    wanted = {key: cell for (key, cell) in cells.items()
              if _coverage_bbox_intersects(definition, cell)}
    keys = sorted(wanted)
    answers = strategy.probe_cell_coverage(
        definition, [wanted[key] for key in keys]) if keys else []
    if answers is None:
        return None
    return {
        "provider": definition["code"],
        "cell_degrees": FOOTPRINT_CELL_DEGREES,
        "covered": [list(key) for (key, hit) in zip(keys, answers) if hit],
        "probed_cells": len(keys),
        "probed": datetime.date.today().isoformat(),
    }


def forget_tile_footprints(lat, lon):
    """Drop every provider's probed map of the tile (a deliberate refresh:
    a provider the old map excluded is a candidate again)."""
    root = os.path.join(FNAMES.Elevation_dir, "footprints")
    name = "%+03d%+04d.json" % (lat, lon)
    try:
        codes = os.listdir(root)
    except OSError:
        return
    for code in codes:
        try:
            os.remove(os.path.join(root, code, name))
        except OSError:
            pass


def ensure_tile_footprints(definitions, lat, lon, refresh=False):
    """Probe every definition whose footprint on the tile is not known yet
    (and whose strategy can probe); returns the codes probed.  A transient
    failure writes nothing, so the next run asks again."""
    tile_box = (lon, lat, lon + 1, lat + 1)
    probed = []
    for definition in definitions:
        strategy = _strategy(definition)
        if strategy is None or not hasattr(strategy, "probe_cell_coverage"):
            continue
        if _catalogue_answer(strategy, definition, tile_box) is not None:
            continue
        path = footprint_path(definition["code"], lat, lon)
        if os.path.isfile(path) and not refresh:
            continue
        try:
            record = _probe_tile(strategy, definition, lat, lon)
        except TransientFetchError as error:
            UI.vprint(1, "   Footprint probe of", definition["code"],
                      "on %+03d%+04d failed (%s); its coverage box decides"
                      " until the next run." % (lat, lon, error))
            continue
        if record is None:
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        scratch = path + ".part"
        with open(scratch, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(record, handle)
        os.replace(scratch, path)
        UI.vprint(1, "   Footprint of", definition["code"],
                  "on %+03d%+04d: %d of %d cell(s) hold data."
                  % (lat, lon, len(record["covered"]),
                     record["probed_cells"]))
        probed.append(definition["code"])
    return probed
