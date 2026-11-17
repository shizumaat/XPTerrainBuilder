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

__all__ = ["neighbour_meshes", "neighbour_marks", "reseat_guests", "mesh_digest"]

#: (path, size, mtime_ns) -> sha256 of a mesh: one read per process
_DIGESTS: dict = {}


def mesh_digest(path: str) -> str:
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


def neighbour_meshes(tile, bounds):
    """``tile_route.neighbour_ground``'s ``meshes``: a neighbour tile's
    built mesh as the placement reads it (``object_stage.
    mesh_placement_sampler`` over ``bounds`` — ``(w, s, e, n)`` — clipped
    to that tile) and its ground mark; ``None`` where that tile has no
    mesh on disk."""
    from auto_patch_v2.airport import tile_route as _route

    from .object_stage import mesh_placement_sampler

    def meshes(there):
        path = _tile_mesh_path(tile, there)
        if not os.path.isfile(path):
            return None
        lat, lon = int(there[0]), int(there[1])
        w, s, e, n = bounds if bounds else (lon, lat, lon + 1, lat + 1)
        box = (max(w, lon), max(s, lat), min(e, lon + 1), min(n, lat + 1))
        return mesh_placement_sampler(path, box), _route.mesh_mark(mesh_digest(path))
    return meshes


def neighbour_marks(tile, bounds) -> dict:
    """``{"+53+010": mark}`` for every OTHER tile ``bounds`` (``(w, s, e,
    n)``) touch — the ground a guest body there is seated on; ``{}`` for
    an airport on one tile (its reuse key is the one it had)."""
    import math

    from auto_patch_v2.airport import tile_route as _route
    if not bounds:
        return {}
    w, s, e, n = bounds
    out = {}
    for lat in range(int(math.floor(s)), int(math.floor(n)) + 1):
        for lon in range(int(math.floor(w)), int(math.floor(e)) + 1):
            if (lat, lon) == (int(tile.lat), int(tile.lon)):
                continue
            path = _tile_mesh_path(tile, (lat, lon))
            out[f"{lat:+03d}{lon:+04d}"] = (
                _route.mesh_mark(mesh_digest(path)) if os.path.isfile(path)
                else _route.DEM_MARK)
    return out


def _stale(here, now: str) -> dict:
    """``{origin tile: {plan key}}``: every placement plan of a neighbour
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
                    stale.setdefault(origin, set()).add(key)
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
        stale = _stale(here, _route.mesh_mark(mesh_digest(mesh_path)))
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
    """Run ``origin``'s placement of the plans ``keys`` again."""
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
