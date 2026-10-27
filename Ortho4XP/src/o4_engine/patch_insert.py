""""Insert shape" on the map (issue #1314, protocol 1.20): a square of
:data:`SQUARE_SIDE_M` centred at the right-click, its corners at the
elevation under them, added to the patch of the airport the point is in.

Two engine commands, both synchronous on the read loop like the other
patch commands:

* ``patch_insert_shape(lat, lon, build_dir=None)`` — the plan, nothing
  written: the airport (:func:`insert_target`), the square's corners
  (:func:`square_ring`) and each corner's elevation from
  ``cursor_elevation`` (the built mesh, else the DEM).  While a source is
  still loading the reply is ``{"pending": true}`` and the app asks again,
  as the cursor readout does.
* ``patch_add_shape(tile, icao, corners)`` — for an airport whose patch
  is NOT the one open in the editor: the shape is appended to the patch
  the build applies and saved as ``patch_save`` saves (the editor's own
  ``<ICAO>_edited.patch.osm``), or, when the airport has no patch at all,
  written as a new ``<ICAO>_edited.patch.osm``.  The open patch takes the
  shape as an ordinary undoable edit in the app (``patch_edit.add_shape``)
  instead.

The airport is the one whose extent holds the point: a patch's own node
box in the tile first (a hand-made patch's airport may not be in the
index), else the default-airport index's extent (boundary, runways,
helipads, datum; ``O4_Airport_Index``).  Several: the smallest box, then
the ICAO.  None: refused with the user's sentence.
"""
from __future__ import annotations

import math
import os
import threading
import typing as _t

import O4_File_Names as FNAMES

from . import patch_commands as PC
from . import patch_edit as PE
from . import patch_file as PF
from .elevation_commands import cursor_elevation

__all__ = ["SQUARE_SIDE_M", "patch_insert_shape",
           "patch_add_shape"]

#: The inserted square's side, metres (#1314).
SQUARE_SIDE_M = 20.0

_INDEX_LOCK = threading.Lock()
_INDEX: dict = {}          # cache path -> ((mtime_ns, size), [(code, extent)])


def square_ring(lat: float, lon: float, side_m: float = SQUARE_SIDE_M
                ) -> list[tuple[float, float]]:
    """The four corners ``(lat, lon)`` of a north-up square of ``side_m``
    centred at ``(lat, lon)``, counter-clockwise from the south-west
    corner (east is +lon, north +lat), not closed."""
    from auto_patch_v2.model.frame import m_per_deg_exact
    m_lat, m_lon = m_per_deg_exact(lat)
    h_lat, h_lon = side_m / 2 / m_lat, side_m / 2 / m_lon
    return [(lat - h_lat, lon - h_lon), (lat - h_lat, lon + h_lon),
            (lat + h_lat, lon + h_lon), (lat + h_lat, lon - h_lon)]


def _index_airports() -> list[tuple[str, tuple[float, float, float, float]]]:
    """``(code, extent)`` of the index's land airports, read once per
    cache file version; ``[]`` when there is no index (never built here:
    the map window builds it)."""
    import O4_Airport_Apt_Identity as IDENTITY
    import O4_Airport_Index as INDEX
    path = FNAMES.airport_index_cache()
    try:
        st = os.stat(path)
    except OSError:
        return []
    stamp = (st.st_mtime_ns, st.st_size)
    with _INDEX_LOCK:
        cached = _INDEX.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    try:
        entries = INDEX.load_index(path)
    except (OSError, ValueError):
        entries = []
    rows = [(e.code.upper(), e.extent or (e.lat, e.lon, e.lat, e.lon)) for e in entries
            if e.category in IDENTITY.IDENTITY_CATEGORIES]
    with _INDEX_LOCK:
        _INDEX[path] = (stamp, rows)
    return rows


def _holds(box: _t.Sequence[float], lat: float, lon: float) -> bool:
    return box[0] <= lat <= box[2] and box[1] <= lon <= box[3]


def _smallest(found: list[tuple[str, _t.Sequence[float], dict | None]]):
    return min(found, key=lambda f: ((f[1][2] - f[1][0]) * (f[1][3] - f[1][1]), f[0]))


def insert_target(lat: float, lon: float) -> dict:
    """``{"tile", "icao", "path", "source"}`` of the airport whose extent
    holds ``(lat, lon)`` (module doc); ``path`` / ``source`` are the patch
    the build applies, ``None`` when the airport has none yet."""
    lat0, lon0 = math.floor(lat), math.floor(lon)
    tile = FNAMES.short_latlon(lat0, lon0)
    patched = [(a["icao"], a["bbox"], a) for a in PC.patch_list(tile)["airports"]
               if _holds(a["bbox"], lat, lon)]
    if patched:
        icao, _box, entry = _smallest(patched)
        return {"tile": tile, "icao": icao, "path": entry["path"], "source": entry["source"]}
    indexed = [(code, box, None) for code, box in _index_airports() if _holds(box, lat, lon)]
    if not indexed:
        raise ValueError(
            f"No airport's boundary holds {lat:.9f}, {lon:.9f}. Insert shape adds "
            f"the shape to an airport's patch: right-click inside an airport.")
    icao = _smallest(indexed)[0]
    found = PC._effective_patch(PC._patch_dir(tile), icao)
    source, path = found if found else (None, None)
    return {"tile": tile, "icao": icao, "path": path, "source": source}


def patch_insert_shape(lat: float, lon: float, build_dir: str | None = None) -> dict:
    """ENGINE COMMAND ``patch_insert_shape`` (module doc): ``{"pending":
    true}`` while an elevation source loads, else ``{"pending": false,
    "tile", "icao", "path", "source", "side_m", "corners": [[lat, lon,
    alt]…]}``."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("patch_insert_shape: lat and lon must be degrees.") from None
    if not (math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"patch_insert_shape: ({lat}, {lon}) is off the globe.")
    target = insert_target(lat, lon)
    corners = []
    for c_lat, c_lon in square_ring(lat, lon):
        reply = cursor_elevation(c_lat, c_lon, build_dir)
        if reply["pending"]:
            return {"pending": True}
        if reply["elevation_m"] is None:
            raise ValueError(
                f"There is no elevation at {c_lat:.9f}, {c_lon:.9f} (no built mesh "
                f"and no DEM for this tile): build the tile first.")
        corners.append([c_lat, c_lon, reply["elevation_m"]])
    return {"pending": False, **target, "side_m": SQUARE_SIDE_M, "corners": corners}


def _new_patch(directory: str, icao: str) -> str:
    """Write an empty ``<ICAO>_edited.patch.osm`` (the editor's header,
    no stamps: nothing was built from) and return its path."""
    from auto_patch.build_support import USER_EDITED_ATTR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, FNAMES.edited_patch_name(icao))
    header = [("version", "'", "0.6"), ("generator", "'", "XPTerrainBuilder patch editor"),
              (USER_EDITED_ATTR, "'", "1")]
    _spacing, dp = PC.law_identity()
    PF.write_atomic(path, PF.render(header, [], [], identity_dp=dp, z_dp=2))
    return path


def patch_add_shape(tile: str, icao: str, corners: _t.Sequence[_t.Sequence]) -> dict:
    """ENGINE COMMAND ``patch_add_shape`` (module doc): ``{"path", "way_id",
    "created", "message"}`` — the file written, the new way's id, whether
    the airport had no patch before, and the sentence both apps show."""
    icao = str(icao).upper()
    directory = PC._patch_dir(tile)
    found = PC._effective_patch(directory, icao)
    created = found is None
    base_path = _new_patch(directory, icao) if created else found[1]
    try:
        base = PF.read_patch(base_path)
        doc = PE.add_shape(PE.PatchDoc.from_wire(base.nodes, base.ways), corners)
        saved = PC.patch_save(tile, icao, base_path, **doc.to_wire())
    except Exception:
        if created:                   # never leave an empty patch behind
            os.remove(base_path)
        raise
    name = os.path.basename(saved["path"])
    side = "a %g m square" % SQUARE_SIDE_M
    message = (f"Started {icao}'s custom patch {name} with {side}. The next build of "
               f"tile {tile} uses it instead of an auto patch (\"Use auto patch\" in the "
               f"tile info sets it aside)." if created else
               f"Added {side} to {icao}'s patch, saved as {name}. Rebuild tile {tile} "
               f"to see it in X-Plane.")
    return {"path": saved["path"], "way_id": doc.ways[-1].id, "created": created,
            "message": message}
