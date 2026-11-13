"""Was an airport patched in the Ortho4XP build of an adopted tile (#2025)?

:func:`patched` answers ``yes`` / ``no`` / ``unknown`` for a tile, and
for one airport of it when ``icao`` is given.  A manual Ortho4XP patch
leaves no mark in the scenery itself; three witnesses read it, in order:

1. a file naming the patch: the source's Ortho4XP install
   (:func:`_ortho4xp_root`) holding ``Patches/<10 deg>/<1 deg>/*.patch.osm``
   -- one named for the airport answers for it -- or a cfg / log of the
   tile's folder naming a ``.patch.osm``;
2. the build's own data (:func:`_airport_encoded`), which Ortho4XP leaves
   in the tile folder: ``Data<tile>.apt`` lists every airport the build
   knew, and ``Data<tile>.poly`` carries a ``RUNWAY``-marked constraint
   edge on each runway the build flattened itself.  Ortho4XP skips that
   for an airport a patch covers, so an airport it knew whose runways
   carry no such edge was patched (owner tiles 2026-11-13: the two
   airports whose packs ship Ortho4XP patches carry 0; every other ICAO
   airport of their tiles 100 or more).  Only a build whose markers
   include the taxiway / hangar ones is read: an older build's 16 is no
   runway;
3. the install known with no patch for the tile: ``no``.

``Data<tile>.apt`` is a pickle: it is read with an unpickler that admits
only the shapely geometry and numpy array classes it holds.

No tile, airport or install is named here.
"""
from __future__ import annotations

import os
import pickle
import warnings
from typing import Iterable, Optional, Set, Tuple

import O4_File_Names as FNAMES

__all__ = ["PATCHED_YES", "PATCHED_NO", "PATCHED_UNKNOWN", "patched"]

PATCHED_YES, PATCHED_NO, PATCHED_UNKNOWN = "yes", "no", "unknown"
#: An Ortho4XP install holds one of these at its top.
_INSTALL_MARKS = ("Ortho4XP.cfg", "Patches")
#: Files of a tile folder read for a named patch, and the most read of one.
_NOTE_SUFFIXES = (".cfg", ".log", ".txt")
_NOTE_MAX_BYTES = 1 << 20
#: Ortho4XP's ``.poly`` edge marker of a runway (``Vector_Map.dico_attributes``),
#: and the taxiway / hangar markers of the same set: a build marking
#: neither is older (Ortho4XP 1.30's 16 is not a runway) and is not read.
_RUNWAY_MARKER = 16
_AIRPORT_SET_MARKERS = 32 | 128
_APT_MAX_BYTES = 64 << 20
#: What ``Data<tile>.apt`` may name: shapely geometries, numpy arrays.
_APT_GLOBALS = {
    ("shapely.io", "from_wkb"), ("shapely.wkb", "loads"),
    ("numpy", "ndarray"), ("numpy", "dtype"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy.core.multiarray", "scalar"),
    ("numpy._core.multiarray", "_reconstruct"),
    ("numpy._core.multiarray", "scalar"),
    ("numpy.core.numeric", "_frombuffer"),
    ("numpy._core.numeric", "_frombuffer"),
}
_APT_GEOMETRY_MODULE = "shapely.geometry."


def _ortho4xp_root(tile_dir: str) -> Optional[str]:
    """The Ortho4XP install a tile folder was built in: the folder's
    parent's parent (``<install>/Tiles/zOrtho4XP_<tile>``), when it holds
    ``Ortho4XP.cfg`` or a ``Patches`` folder; else None."""
    if not tile_dir:
        return None
    root = os.path.dirname(os.path.dirname(os.path.realpath(tile_dir)))
    if any(os.path.exists(os.path.join(root, mark)) for mark in _INSTALL_MARKS):
        return root
    return None


def _notes_name_patch(tile_dir: str) -> bool:
    """Does a cfg / log file of the tile's folder name a ``.patch.osm``?"""
    try:
        entries = list(os.scandir(tile_dir))
    except OSError:
        return False
    for entry in entries:
        if not entry.name.lower().endswith(_NOTE_SUFFIXES):
            continue
        try:
            if not entry.is_file() or entry.stat().st_size > _NOTE_MAX_BYTES:
                continue
            with open(entry.path, encoding="utf-8", errors="replace") as fh:
                if FNAMES.PATCH_SUFFIX in fh.read().lower():
                    return True
        except OSError:
            continue
    return False


def _install_patches(root: str, lat: int, lon: int) -> list:
    """The ``.patch.osm`` names of the install's folder for the tile."""
    folder = os.path.join(root, "Patches", FNAMES.long_latlon(lat, lon))
    try:
        return [name for name in os.listdir(folder)
                if name.lower().endswith(FNAMES.PATCH_SUFFIX)]
    except OSError:
        return []


class _AptUnpickler(pickle.Unpickler):
    """``Data<tile>.apt``'s classes only (the module docstring)."""

    def find_class(self, module, name):
        if ((module, name) in _APT_GLOBALS
                or module.startswith(_APT_GEOMETRY_MODULE)):
            return super().find_class(module, name)
        raise pickle.UnpicklingError("not an airport file: %s.%s"
                                     % (module, name))


def _runway_area(tile_dir: str, stem: str, icao: str):
    """The airport ``icao``'s runway area in ``Data<tile>.apt`` (tile
    local coordinates), or None: no file, unread, or not listed."""
    path = os.path.join(tile_dir, stem + ".apt")
    try:
        if os.path.getsize(path) > _APT_MAX_BYTES:
            return None
        with open(path, "rb") as fh, warnings.catch_warnings():
            warnings.simplefilter("ignore")     # shapely < 2 pickles
            airports = _AptUnpickler(fh).load()
    except Exception:                           # unread: the witness is silent
        return None
    if not isinstance(airports, dict):
        return None
    for key, airport in airports.items():
        if isinstance(key, str) and key.upper() == icao:
            try:
                area = airport["runway"][0]
                return None if area is None or area.is_empty else area
            except Exception:
                return None
    return None


def _runway_edges(poly_path: str) -> Tuple[list, Set[int]]:
    """The ``RUNWAY``-marked edges ``(node, node)`` of an Ortho4XP
    ``.poly`` file, and their node ids; none for a file of an older
    marker set (:data:`_AIRPORT_SET_MARKERS`)."""
    edges, ids, airport_set = [], set(), False
    with open(poly_path, encoding="ascii", errors="replace") as fh:
        for _ in range(3):              # nodes header, blank, edges header
            fh.readline()
        for line in fh:
            parts = line.split()
            if len(parts) != 4:
                break
            marker = int(parts[3])
            airport_set = airport_set or bool(marker & _AIRPORT_SET_MARKERS)
            if marker & _RUNWAY_MARKER:
                a, b = int(parts[1]), int(parts[2])
                edges.append((a, b))
                ids.update((a, b))
    return (edges, ids) if airport_set else ([], set())


def _node_xy(node_path: str, ids: Set[int]) -> dict:
    """``{id: (x, y)}`` of the named nodes of an Ortho4XP ``.node`` file."""
    xy = {}
    with open(node_path, encoding="ascii", errors="replace") as fh:
        fh.readline()
        for line in fh:
            head, _, rest = line.partition(" ")
            try:
                node = int(head)
            except ValueError:
                continue
            if node in ids:
                x, y = rest.split()[:2]
                xy[node] = (float(x), float(y))
    return xy


def _airport_encoded(tile_dir: str, lat: int, lon: int,
                    icao: str) -> Optional[bool]:
    """Did the Ortho4XP build in ``tile_dir`` flatten the airport's
    runways itself (True), or skip them for a patch (False)?  None when
    the folder has no build data, the build did not know the airport, or
    marks no runway anywhere in the marker set read here (the witness is
    silent)."""
    icao = (icao or "").strip().upper()
    if not (tile_dir and icao):
        return None
    stem = "Data" + FNAMES.short_latlon(lat, lon)
    area = _runway_area(tile_dir, stem, icao)
    if area is None:
        return None
    try:
        edges, ids = _runway_edges(os.path.join(tile_dir, stem + ".poly"))
        if not edges:
            return None
        xy = _node_xy(os.path.join(tile_dir, stem + ".node"), ids)
    except (OSError, ValueError):
        return None
    from shapely import geometry, prepared
    inside = prepared.prep(area)
    for a, b in edges:
        if a in xy and b in xy and inside.contains(geometry.Point(
                (xy[a][0] + xy[b][0]) / 2, (xy[a][1] + xy[b][1]) / 2)):
            return True
    return False


def patched(tile_dirs: Iterable[str], lat: int, lon: int,
            icao: str = "") -> str:
    """:data:`PATCHED_YES` / :data:`PATCHED_NO` / :data:`PATCHED_UNKNOWN`
    for the tile built in ``tile_dirs`` (its own folders), or for its
    airport ``icao`` (the module docstring)."""
    dirs = [d for d in tile_dirs if d]
    wanted = (icao or "").strip().upper()
    roots = [r for r in (_ortho4xp_root(d) for d in dirs) if r is not None]
    names = [n for r in roots for n in _install_patches(r, lat, lon)]
    if wanted and any(n.upper().startswith(wanted) for n in names):
        return PATCHED_YES
    if wanted:
        for folder in dirs:
            encoded = _airport_encoded(folder, lat, lon, wanted)
            if encoded is not None:
                return PATCHED_NO if encoded else PATCHED_YES
    if names or any(_notes_name_patch(d) for d in dirs):
        return PATCHED_YES
    return PATCHED_NO if roots else PATCHED_UNKNOWN
