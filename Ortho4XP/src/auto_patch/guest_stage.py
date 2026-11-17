"""THE GROUND A GUEST BODY STANDS ON (issue #2129; #1884 guest rows).

A placement of one tile's pack DSF may have bodies standing on a
neighbour tile; they are written as on-ground ``OBJECT`` rows of THAT
tile's DSF (``auto_patch_v2.airport.tile_route``), so X-Plane seats each
on the neighbour's DRAWN mesh.  The object stage therefore cuts and
anchors them on that mesh when its build is on disk
(:func:`neighbour_meshes`, read through ``tile_route.neighbour_ground``),
and on the airport's DEM only where it is not — the guest record says
which (``tile_route.mesh_mark`` / ``DEM_MARK``).  EDDH, before this:
1,190 terminal bodies past 10°E cut on the DEM, drawn on the ``+53+010``
mesh, −11.7..+3.0 m off their plan, the rigid group split.

A LATER BUILD OF THAT TILE RE-SEATS THEM (:func:`reseat_guests`): every
guest record in its DSFs whose ground is not its new mesh's runs the
ORIGIN tile's placement of that plan again — one decomposition, the
origin's (#1884), now on this mesh — in this build's pack journal.

The reuse key (#879) carries the neighbour grounds (:func:`neighbour_marks`),
so an origin build never serves a placement seated on a ground that moved.
"""
from __future__ import annotations

import os
import traceback

__all__ = ["neighbour_meshes", "neighbour_marks", "reseat_guests"]

#: (path, size, mtime_ns) -> sha256 of a mesh: one read per process
_DIGESTS: dict = {}


def _mesh_digest(path: str) -> str:
    """sha256 of the mesh at ``path``, memoised on its stat."""
    from auto_patch_v2.airport.file_hash import sha256_file
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _DIGESTS:
        _DIGESTS[key] = sha256_file(path)
    return _DIGESTS[key]


def _tile_mesh_path(tile, there) -> str:
    """Where the build of tile ``there`` keeps its mesh, beside ``tile``'s
    (the same build-folder rule, ``O4_File_Names.build_dir``)."""
    import O4_File_Names as FNAMES
    lat, lon = int(there[0]), int(there[1])
    return FNAMES.mesh_file(FNAMES.build_dir(
        lat, lon, getattr(tile, "custom_build_dir", "") or ""), lat, lon)


def _tile_dsf_path(tile, there) -> str:
    """The base-mesh DSF the build of tile ``there`` wrote, beside
    ``tile``'s build (``O4_File_Names.dsf_file``)."""
    import O4_File_Names as FNAMES
    lat, lon = int(there[0]), int(there[1])
    return FNAMES.dsf_file(FNAMES.build_dir(
        lat, lon, getattr(tile, "custom_build_dir", "") or ""), lat, lon)


def _dsf_sampler(path: str, box):
    """A ``MeshElevationSampler`` over the tile DSF's drawn triangles in
    ``box`` (``dsf_mesh``, as ``tools/drawn_site.py`` reads it); a
    raster-deferred vertex (no height of its own) is no ground."""
    import numpy as np
    from auto_patch_v2.airport.dsf_mesh import physical_triangles, stream_text

    from .dsf_reader import _dsftool_path
    from .mesh_sampler import MeshElevationSampler
    with stream_text(path, _dsftool_path() or "DSFTool") as fh:
        corners = physical_triangles(fh, box)
    corners = np.asarray(corners, dtype=float).reshape(-1, 3, 3)
    corners = corners[(corners[:, :, 2] > -32000.0).all(axis=1)]
    return MeshElevationSampler.from_triangles(corners, box)


def neighbour_meshes(tile, bounds):
    """``tile_route.neighbour_ground``'s ``meshes``: a neighbour tile's
    built mesh as the placement reads it (``object_stage.
    mesh_placement_sampler`` over ``bounds`` — ``(w, s, e, n)`` — clipped
    to that tile) and its ground mark — its ``.mesh``, else the DSF its
    build wrote (a pruned rebuild cache keeps the DSF X-Plane draws);
    ``None`` where that tile has neither on disk."""
    from auto_patch_v2.airport import tile_route as _route

    from .object_stage import mesh_placement_sampler

    def meshes(there):
        lat, lon = int(there[0]), int(there[1])
        w, s, e, n = bounds if bounds else (lon, lat, lon + 1, lat + 1)
        box = (max(w, lon), max(s, lat), min(e, lon + 1), min(n, lat + 1))
        path = _tile_mesh_path(tile, there)
        if os.path.isfile(path):
            return (mesh_placement_sampler(path, box),
                    _route.mesh_mark(_mesh_digest(path)))
        dsf = _tile_dsf_path(tile, there)
        if not os.path.isfile(dsf):
            return None
        return (mesh_placement_sampler(dsf, box, sampler=_dsf_sampler(dsf, box)),
                _route.mesh_mark(_mesh_digest(dsf), "dsf"))
    return meshes


def _ground_mark(tile, there) -> str:
    """The ground mark a guest on ``there`` reads from ``tile``'s build
    (:func:`neighbour_meshes`' order), without building a sampler."""
    from auto_patch_v2.airport import tile_route as _route
    path = _tile_mesh_path(tile, there)
    if os.path.isfile(path):
        return _route.mesh_mark(_mesh_digest(path))
    dsf = _tile_dsf_path(tile, there)
    if os.path.isfile(dsf):
        return _route.mesh_mark(_mesh_digest(dsf), "dsf")
    return _route.DEM_MARK


def neighbour_marks(tile, bounds) -> dict:
    """``{"+53+010": mark}`` for every OTHER tile ``bounds`` (``(w, s, e,
    n)``) touch — the ground a guest body there is seated on; ``{}`` for
    an airport on one tile (its reuse key is the one it had)."""
    import math
    if not bounds:
        return {}
    w, s, e, n = bounds
    out = {}
    for lat in range(int(math.floor(s)), int(math.floor(n)) + 1):
        for lon in range(int(math.floor(w)), int(math.floor(e)) + 1):
            if (lat, lon) != (int(tile.lat), int(tile.lon)):
                out[f"{lat:+03d}{lon:+04d}"] = _ground_mark(tile, (lat, lon))
    return out


def _stale(here, now: str) -> dict:
    """``{origin tile: {ICAO}}``: the airport of every placement plan of a neighbour
    tile (``o4_v2_placement_<key>.json`` beside its patches) whose guest
    record in ``here``'s DSF of its pack is seated on another ground than
    ``now``."""
    import glob
    import json

    import O4_File_Names as FNAMES
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import tile_route as _route
    stale: dict = {}
    for dl in (-1, 0, 1):
        for dn in (-1, 0, 1):
            origin = (here[0] + dl, here[1] + dn)
            if origin == here:
                continue
            pattern = os.path.join(glob.escape(FNAMES.patch_dir(*origin)),
                                   "o4_v2_placement_*.json")
            for path in sorted(glob.glob(pattern)):
                try:
                    with open(path, encoding="utf-8") as fh:
                        doc = json.load(fh)
                except (OSError, ValueError):
                    continue
                key = os.path.basename(path)[len("o4_v2_placement_"):-len(".json")]
                mark = _route.guest_mark(
                    str(doc.get("pack_root") or ""), here,
                    _dsf.guest_key(str(doc.get("icao") or key), origin))
                if mark is not None and mark != now:
                    stale.setdefault(origin, set()).add(key.split("~", 1)[0])
    return stale


def reseat_guests(tile, mesh_path: str) -> dict:
    """The module's re-seat for ``tile``'s build, its mesh at ``mesh_path``:
    ``{"guests_reseated": n, "guests_reseat_failed": n}`` (``{}`` when no
    record needed it).  Never raises."""
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import tile_route as _route
    counts: dict = {}
    try:
        here = (int(tile.lat), int(tile.lon))
        stale = _stale(here, _route.mesh_mark(_mesh_digest(mesh_path)))
        for origin, keys in sorted(stale.items()):
            counts_one = _reseat_from(tile, origin, keys, UI)
            for k, v in counts_one.items():
                counts[k] = counts.get(k, 0) + v
    except Exception as exc:
        UI.vprint(0, f"  [v2 rebake] guest re-seat failed ({exc}); the "
                     f"neighbours' objects on this tile are as they were")
        UI.vprint(2, traceback.format_exc())
    return counts


def _reseat_from(tile, origin, keys, UI) -> dict:
    """Run ``origin``'s placement of the airports ``keys`` again."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES

    from . import object_stage
    name = FNAMES.short_latlon(*origin)
    UI.vprint(0, f"  [v2 rebake] {', '.join(sorted(keys))}: the objects tile "
                 f"{name} placed on this tile stand on another ground than "
                 f"this mesh — re-seated by {name}'s plan")
    other = CFG.Tile(origin[0], origin[1], getattr(tile, "custom_build_dir", "") or "")
    other.read_from_config()
    got = object_stage._object_stage(other, only=frozenset(keys))
    return {"guests_reseated": len(keys),
            "guests_reseat_failed": int(got.get("airports_failed", 0))}
