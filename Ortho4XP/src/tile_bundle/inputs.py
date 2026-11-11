"""WHICH DOWNLOADED FILES A PACKAGE CARRIES (#2014): everything a tile's
rebuild would otherwise fetch, except imagery.

A ``.xptb`` package (:mod:`.package`) carries a tile's DATA, never its
products: measured on tile +30+031 (HECA, 2026-11-11), its inputs are
23.3 MB of xz against 33.7 MB for its mesh, masks and solved airports,
and inputs build with any engine while a mesh is reusable only by the
identical engine (``key.key_parts``' code family).  Per tile:

* ``data/OSM_data/<10°>/<tile>/…`` — the tile's OpenStreetMap layer
  caches, whole (airports, roads, water, coastline, shore layers; a
  user's ``custom_water`` too);
* ``data/Elevation_data/<10°>/<NxxEyyy>…`` — every elevation artefact of
  the tile's cell: base raster(s), airport insets, approach rings, tile
  overlay, coastline and bathymetry band cells, each with its JSON
  sidecar and stamp;
* ``data/Elevation_data/…`` — the BASE rasters of the eight neighbour
  cells: the DEM is assembled over the 3x3 neighbourhood
  (``O4_DEM_Utils.build_combined_raster``) and a missing neighbour is a
  download;
* ``patches/<tile>/…`` — the airport patches someone made by hand (any
  ``*.patch.osm`` that is not an auto patch) and their editor sidecars.

AN AIRPORT PACKAGE (owner 2026-11-11T15:35Z: "a way to export just a
specific airport") narrows two of these to the chosen airports: the
tile's airport insets (and the inset index's rows for them; the tile's
inset completion stamp is left out, since it settles the airports NOT
carried too) and its hand-made patches.  The rest is what any rebuild of
the tile reads whichever airport it grades — its OSM layers, base
rasters and approach rings (ring cells are planned per tile, not per
airport) — and is carried whole.

NOT carried, and why: imagery (the user's own); auto patches, graded
surfaces and object plans (solved again against the RECEIVING user's
pack: a patch solved against another pack would be wrong for theirs);
the mesh, masks and every build product (made again, offline, from the
inputs); band mosaics (``.vrt``: rebuilt from their cells, and a VRT can
name any file on a disk); the per-airport road-feed cache (a pickle,
derived locally — never shipped); neighbour tiles' road layers (their
absence is lawful and never downloaded, ``O4_Vector_Map.
ensure_auto_patch_road_feeds``); raw lidar point clouds (the insets
gridded from them are carried).

Only :data:`ALLOWED` file kinds go in or come out — data, never code.
"""
from __future__ import annotations

import os

import O4_File_Names as FNAMES

__all__ = ["ALLOWED", "DATA_ROOTS", "INSET_INDEX", "INSET_STAMP", "files",
           "destination"]

#: The file kinds a package may hold: OSM layers and patches, elevation
#: rasters and JSON sidecars.  Nothing executable, no pickle, no mosaic.
ALLOWED = (".osm.bz2", ".osm", ".hgt", ".tif", ".tiff", ".json")

#: Names never carried even when their kind is allowed: in-flight and
#: set-aside files of the caches and the patch folder.
_NEVER = (".lock", ".tmp", ".part", ".stale", ".disabled", ".bak")

#: ``data/<name>/…`` members and the ``O4_File_Names`` folder each lands
#: in (read at call time: the data root can move).
DATA_ROOTS = {"OSM_data": "OSM_dir", "Elevation_data": "Elevation_dir"}

#: The airport inset folder's per-airport index and its tile-wide stamp
#: (``O4_File_Names.airport_inset_index``, ``O4_Airport_Elevation_Insets.
#: inset_completion_stamp_path``), as member-name endings.
INSET_INDEX = "_airport_insets/index.json"
INSET_STAMP = "_airport_insets/complete.json"


def _allowed(name: str) -> bool:
    """Whether a member or file ``name`` is a kind a package carries."""
    low = name.lower()
    base = os.path.basename(low)
    return (low.endswith(ALLOWED) and not base.startswith(".")
            and not any(mark in base for mark in _NEVER))


def _walk(folder: str) -> list:
    """Every allowed file below ``folder``, sorted; hidden folders skipped."""
    out = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        out += [os.path.join(root, n) for n in sorted(names) if _allowed(n)]
    return out


def _data_member(path: str, root_name: str) -> str:
    root = getattr(FNAMES, DATA_ROOTS[root_name])
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return "data/%s/%s" % (root_name, rel)


def _cell_entries(lat: int, lon: int, whole: bool) -> list:
    """The elevation cache entries of one 1° cell: with ``whole`` every
    file and folder named for the cell, else only its base raster files
    (``<NxxEyyy>.hgt``, ``<NxxEyyy>_<SOURCE>.tif`` and their sidecars)."""
    stem = FNAMES.hem_latlon(lat, lon)
    block = os.path.dirname(FNAMES.base_file_name(lat, lon))
    try:
        names = sorted(os.listdir(block))
    except OSError:
        return []
    out = []
    for name in names:
        if name != stem and not name.startswith((stem + "_", stem + ".")):
            continue
        path = os.path.join(block, name)
        if os.path.isdir(path):
            if whole:
                out += _walk(path)
        elif _allowed(name):
            out.append(path)
    return out


def _neighbours(lat: int, lon: int) -> list:
    return [(lat + dlat, (lon + dlon + 180) % 360 - 180)
            for dlat in (-1, 0, 1) for dlon in (-1, 0, 1)
            if (dlat, dlon) != (0, 0) and -90 <= lat + dlat < 90]


def _airport_of_inset(name: str) -> str:
    """The airport an inset file is for (``HECA_copernicusglo30.tif`` ->
    ``HECA``); ``""`` for the folder's index and stamp."""
    base = os.path.basename(name)
    return base.rsplit("_", 1)[0] if "_" in base else ""


def _keep_inset(path: str, airports) -> bool:
    if airports is None or "_airport_insets" + os.sep not in path:
        return True
    if path.endswith(os.sep + "complete.json"):
        return False
    base = os.path.basename(path)
    return base == "index.json" or _airport_of_inset(base).upper() in airports


def _manual_patches(lat: int, lon: int, airports=None) -> list:
    """The tile's hand-made patches and their editor sidecars (of
    ``airports`` only, when given)."""
    folder = FNAMES.patch_dir(lat, lon)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    keep = []
    for name in names:
        if airports is not None and FNAMES.patch_file_icao(name) not in airports:
            continue
        if FNAMES.is_manual_patch_name(name) and _allowed(name):
            keep += [name, name + ".axes.json"]
    return [os.path.join(folder, n) for n in keep
            if os.path.isfile(os.path.join(folder, n))]


def files(lat: int, lon: int, airports=None) -> list:
    """``[(member name, local path)]`` of tile (lat, lon), sorted; with
    ``airports`` (ICAOs) an airport package's (module doc)."""
    lat, lon = int(lat), int(lon)
    if airports is not None:
        airports = {str(a).upper() for a in airports}
    out = [(_data_member(p, "OSM_data"), p)
           for p in _walk(FNAMES.osm_dir(lat, lon))]
    out += [(_data_member(p, "Elevation_data"), p)
            for p in _cell_entries(lat, lon, whole=True)
            if _keep_inset(p, airports)]
    for cell in _neighbours(lat, lon):
        out += [(_data_member(p, "Elevation_data"), p)
                for p in _cell_entries(*cell, whole=False)]
    key = FNAMES.short_latlon(lat, lon)
    out += [("patches/%s/%s" % (key, os.path.basename(p)), p)
            for p in _manual_patches(lat, lon, airports)]
    return sorted(set(out))


def destination(name: str) -> str:
    """Where the member ``name`` lands on this machine.

    :raises ValueError: a name outside ``data/<root>/`` and
        ``patches/<tile>/``, a kind no package carries, or a path that
        would leave its folder.
    """
    parts = name.split("/")
    if (not _allowed(name) or any(p in ("", ".", "..") for p in parts)
            or "\\" in name or ":" in name):
        raise ValueError("package member %r is not a data file a package "
                         "may carry" % name)
    if parts[0] == "data" and len(parts) >= 4 and parts[1] in DATA_ROOTS:
        root = getattr(FNAMES, DATA_ROOTS[parts[1]])
        return os.path.join(root, *parts[2:])
    tile = FNAMES.parse_tile_key(parts[1]) if len(parts) == 3 else None
    if parts[0] == "patches" and tile is not None:
        return os.path.join(FNAMES.patch_dir(*tile), parts[2])
    raise ValueError("package member %r is outside data/ and patches/"
                     % name)
