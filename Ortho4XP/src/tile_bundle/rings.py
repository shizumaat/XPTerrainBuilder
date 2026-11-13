"""THE APPROACH RINGS AN AIRPORT USES (#2014 follow-up; owner 2026-11-11T16:10Z:
"bundle the whole tile for an exact match, or only a specific airport
patch"): an exact-match airport package carries only the ring cells that
airport's grading reads.

A tile's ring cells are planned for EVERY airport on (and next to) it
(``O4_Elevation_Level.resolve_approach_ring_plan``): a 0.1 degree cell is
fetched when the union of the aerodrome boundaries, buffered by the
outermost rung's reach (:data:`O4_Elevation_Level.APPROACH_RING_2_REACH_M`),
touches it.  The cells one airport uses are the ones ITS buffered boundary
touches; the rest are the other airports' and stay out of its package (on
KLAX's tile +33-119 the rings are 53 MB, a quarter of the tile's data).

The boundary is read through the airport's INSET box (the inset index's
``bounding_box`` row, else its sidecar's ``bounding_box_wgs84``): the
inset is fetched over the boundary plus a margin
(``inset_fetch_margin_m``), so the box buffered by the reach holds the
buffered boundary — a superset, never a hole.  A cell kept is the same
file the recipient's own plan names (the plan is a function of the same
map data), so the recipient's ring layer is identical over the airport;
the cells left out are fetched by the recipient's build for the other
airports.  An airport with no inset box keeps every cell (nothing to
trim by is not a reason to drop data).
"""
from __future__ import annotations

import json
import math
import os
import re

import O4_File_Names as FNAMES

__all__ = ["CELL_RE", "airport_boxes", "reach_boxes", "keep_cell"]

#: ``cell_<column>_<row>_…`` — a ring cell's raster or sidecar.
CELL_RE = re.compile(r"^cell_(\d{2})_(\d{2})_")

_METRES_PER_DEGREE = 111_320.0


def _reach_m() -> float:
    import O4_Elevation_Level as LEVEL
    return float(max(r.reach_m for r in LEVEL.approach_rung_ladder()))


def _cell_degrees() -> float:
    import O4_Elevation_Level as LEVEL
    return float(LEVEL.COASTLINE_CELL_DEGREES)


def _box_of(row) -> tuple | None:
    if not isinstance(row, dict):
        return None
    box = row.get("bounding_box") or row.get("bounding_box_wgs84")
    try:
        west, south, east, north = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    return (west, south, east, north)


def airport_boxes(lat: int, lon: int, airports) -> dict:
    """``{icao: (west, south, east, north)}`` of the tile's insets of
    ``airports``: the inset index's row, else the inset's sidecar."""
    folder = FNAMES.airport_inset_directory(lat, lon)
    index = FNAMES.read_json_dict(FNAMES.airport_inset_index(lat, lon))
    out = {}
    for icao in sorted({str(a).upper() for a in airports}):
        box = _box_of(index.get(icao) or {})
        if box is None:
            box = _sidecar_box(folder, icao)
        if box is not None:
            out[icao] = box
    return out


def _sidecar_box(folder: str, icao: str) -> tuple | None:
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in names:
        if name.upper().startswith(icao + "_") and name.endswith(".json"):
            try:
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    box = _box_of(json.load(handle))
            except (OSError, ValueError):
                continue
            if box is not None:
                return box
    return None


def reach_boxes(boxes) -> list:
    """Each box grown by the outermost rung's reach, in degrees."""
    reach = _reach_m()
    out = []
    for west, south, east, north in boxes:
        dlat = reach / _METRES_PER_DEGREE
        widest = max(abs(south), abs(north))
        dlon = reach / (_METRES_PER_DEGREE * max(0.01, math.cos(math.radians(min(89.9, widest)))))
        out.append((west - dlon, south - dlat, east + dlon, north + dlat))
    return out


def _cell_box(lat: int, lon: int, name: str) -> tuple | None:
    """The degree box of the ring cell ``name`` of tile (lat, lon)."""
    match = CELL_RE.match(os.path.basename(name))
    if not match:
        return None
    step = _cell_degrees()
    column, row = int(match.group(1)), int(match.group(2))
    return (lon + column * step, lat + row * step,
            lon + (column + 1) * step, lat + (row + 1) * step)


def keep_cell(lat: int, lon: int, name: str, regions) -> bool:
    """Whether ring file ``name`` is one an airport whose grown boxes are
    ``regions`` uses (``None`` regions: keep everything; a file that is
    not a cell — the ring stamp — is kept)."""
    if regions is None:
        return True
    box = _cell_box(lat, lon, name)
    if box is None:
        return True
    west, south, east, north = box
    return any(w < east and west < e and s < north and south < n
               for w, s, e, n in regions)
