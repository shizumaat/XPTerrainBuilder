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

A RE-SEAT WAITS FOR THE ORIGIN'S OWN BUILD IN THE SAME RUN (#2290): when
the origin tile is still owed its mesh step in this run
(:func:`note_mesh_pending`) and its ground is not built yet, its own object
stage — later, over this tile's new mesh — places the airport, guests and
all; the re-seat is skipped without a not-fitted row.  LOWS, app 1.0.585:
``+47+013`` finished first, re-ran ``+47+012``'s plan over ``+47+012``'s
stale ground ("STALE MESH") and warned "Build the tile again" while
``+47+012`` was still building.
"""
from __future__ import annotations

import os
import traceback

__all__ = ["neighbour_meshes", "neighbour_marks", "reseat_guests", "own_ground",
           "note_mesh_pending"]

#: (path, size, mtime_ns) -> sha256 of a mesh: one read per process
_DIGESTS: dict = {}

#: (lat, lon) of a tile this process builds -> the tiles of the same run
#: (its 3x3 block) still owed their mesh step (#2290)
_MESH_PENDING: dict = {}


def note_mesh_pending(here, cells) -> None:
    """Record that the run building tile ``here`` still owes the mesh step
    of the tiles ``cells`` (``[[lat, lon], ...]``): the parallel parent
    sends it with every step (``parallel._mesh_pending_locked``), the
    in-process run lands it per tile from its queue."""
    _MESH_PENDING[(int(here[0]), int(here[1]))] = frozenset(
        (int(c[0]), int(c[1])) for c in cells or ())


def _waits_for(here, origin, other) -> bool:
    """Is ``origin`` (its tile ``other``) still to build its mesh in the
    run building ``here``, its ground not ready — so its own object stage
    places the airport over ``here``'s new mesh (module docstring)?"""
    if tuple(origin) not in _MESH_PENDING.get(tuple(here), ()):
        return False
    from .post_mesh import _mesh_is_newer_than_alt
    mesh = _tile_mesh_path(other, origin)
    return not (os.path.isfile(mesh) and _mesh_is_newer_than_alt(other, mesh))


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


def own_ground(tile, plans) -> str:
    """The ground a tile's OWN placement reads when its ``.mesh`` is gone:
    the DSF its build wrote, the very ground :func:`neighbour_meshes`
    reads for a guest, when that DSF is NEWER than every rebake plan in
    ``plans`` (written at this tile's mesh step, before its DSF step);
    ``""`` otherwise.

    #2129, EDDH 1.0.558 (lane leddh3): the storage offload moved
    ``+53+009``'s ``.mesh`` to a tier; the re-seat ``+53+010``'s build
    asked of ``+53+009``'s plan then skipped ("mesh not found"), and
    1,193 terminal and garage bodies stood on a ground 1.6 m lower to
    1.2 m higher than the one they were seated on.  A rebuild cache a
    tier holds, or the disk budget cleared, keeps the DSF X-Plane draws.
    A DSF OLDER than the plan is the previous build's (this build's mesh
    vanished mid-build): no ground — the placement waits for a build."""
    dsf = _tile_dsf_path(tile, (int(tile.lat), int(tile.lon)))
    try:
        built = os.path.getmtime(dsf)
        return dsf if all(built > os.path.getmtime(p) for p in plans) else ""
    except OSError:
        return ""


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


def reseat_guests(tile, mesh_path: str, failed: "list | None" = None) -> dict:
    """The module's re-seat for ``tile``'s build, its mesh at ``mesh_path``:
    ``{"guests_reseated": n, "guests_reseat_failed": n}`` (``{}`` when no
    record needed it).  Never raises; what it could not re-seat is
    appended to ``failed`` (#2186, ``object_stage._not_fitted`` rows: the
    objects stand on THIS tile)."""
    failed = [] if failed is None else failed
    import O4_UI_Utils as UI
    from auto_patch_v2.airport import tile_route as _route
    counts: dict = {}
    try:
        here = (int(tile.lat), int(tile.lon))
        stale = _stale(here, _route.mesh_mark(_mesh_digest(mesh_path)))
        for origin, keys in sorted(stale.items()):
            counts_one = _reseat_from(tile, here, origin, keys, UI, failed)
            for k, v in counts_one.items():
                counts[k] = counts.get(k, 0) + v
    except Exception as exc:
        UI.vprint(0, f"  [v2 rebake] guest re-seat failed ({exc}); the "
                     f"neighbours' objects on this tile are as they were")
        from .object_stage import NOT_FITTED_CODE
        failed.append({"code": NOT_FITTED_CODE,
                       "detail": f"neighbour objects not re-seated: {exc}"})
        UI.vprint(2, traceback.format_exc())
    return counts


def _reseat_from(tile, here, origin, keys, UI, failed: list) -> dict:
    """Run ``origin``'s placement of the airports ``keys`` again, unless
    ``origin``'s own build in this run will (:func:`_waits_for`)."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES

    from . import object_stage
    name = FNAMES.short_latlon(*origin)
    other = CFG.Tile(origin[0], origin[1], getattr(tile, "custom_build_dir", "") or "")
    other.read_from_config()
    if _waits_for(here, origin, other):
        UI.vprint(0, f"  [v2 rebake] {', '.join(sorted(keys))}: the objects tile "
                     f"{name} placed on this tile wait for {name}'s build in "
                     f"this run, whose plan seats them on this mesh")
        return {"guests_deferred": len(keys)}
    UI.vprint(0, f"  [v2 rebake] {', '.join(sorted(keys))}: the objects tile "
                 f"{name} placed on this tile stand on another ground than "
                 f"this mesh — re-seated by {name}'s plan")
    got = object_stage._object_stage(other, only=frozenset(keys),
                                     failed=failed)
    return {"guests_reseated": len(keys),
            "guests_reseat_failed": int(got.get("airports_failed", 0))}
