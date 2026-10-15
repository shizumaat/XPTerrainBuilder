"""``pack_objects`` — the airport pack's buildings for the patch editor's
3D preview (protocol 1.12, ``docs/specs/patch-editor-20261015.md`` §2, §5).

Reuses the object stage's readers, read-only:

* the pack: ``airport/pack.select_pack`` (the one picker — the same call
  ``auto_patch/engine_v2`` makes for the pack dump);
* the placements: the cached text dump of the pack's tile DSF, located by
  ``airport/dsf.find_text_dump`` in the object stage's read frame
  (``dsf_write.pristine_dsf_path``) and parsed by ``dsf.read_dump``;
* the models: ``airport/obj8`` — ``resolve_resource`` (pack-relative,
  then the cached library index), ``ResourceCache.geometry``
  (``parse_obj8``);
* the facades: ``airport/facade.read_facade`` and ``floor_for``.

Each model is sent once, solid NON-ANIMATED triangles only (draped
decals and moving parts dropped), its vertices compacted to the ones
those triangles use.  Placements carry ``agl_m`` (``OBJECT`` = 0,
``OBJECT_AGL`` = its offset).  Nothing is regenerated: a missing dump,
library index or file is a sentence in ``missing``.
"""
from __future__ import annotations

import base64
import os
import typing as _t

import numpy as np

import O4_File_Names as FNAMES

__all__ = ["pack_objects"]


def _box(bbox: _t.Any) -> tuple[float, float, float, float]:
    try:
        s, w, n, e = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise ValueError("pack_objects: bbox must be [min_lat, min_lon, max_lat, "
                         "max_lon] in degrees.") from None
    if not (s < n and w < e):
        raise ValueError(f"pack_objects: bbox {[s, w, n, e]} is empty.")
    return s, w, n, e


def _b64(a: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")


def xplane_root_for(lat: int, lon: int) -> str | None:
    """The X-Plane install the tile's build reads (its CIFP folder's
    install — ``patch_commands`` and the tile driver resolve it so)."""
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    from auto_patch.cifp_reader import xplane_root_from_cifp_path
    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    cifp_dir = VMAP.resolve_cifp_dir_for_tile(tile)
    return xplane_root_from_cifp_path(cifp_dir) if cifp_dir else None


#: Spec §5 (ruled after 6b): a component under this size in EVERY
#: dimension is clutter, not massing, and is not sent.
MIN_COMPONENT_M = 2.0


def component_hull(points: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """The 3-D convex hull of one component's points: ``(vertices,
    triangles)`` wound outward, or ``None`` when no hull exists.  A flat
    component (a wall plate) is joggled into a thin hull."""
    from scipy.spatial import ConvexHull, QhullError
    pts = np.unique(np.asarray(points, dtype=np.float64), axis=0)
    if pts.shape[0] < 4:
        return None
    try:
        hull = ConvexHull(pts)
    except QhullError:
        try:
            hull = ConvexHull(pts, qhull_options="QJ")
        except QhullError:
            return None
    used, inverse = np.unique(hull.simplices.reshape(-1), return_inverse=True)
    verts = pts[used]
    tris = inverse.reshape(-1, 3)
    # outward: each face's normal points away from the hull's centre
    centre = verts.mean(axis=0)
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    inward = np.einsum("ij,ij->i", np.cross(b - a, c - a), a - centre) < 0
    tris[inward] = tris[inward][:, [0, 2, 1]]
    return verts, tris


def model_payload(cache, path: str) -> tuple[np.ndarray, np.ndarray, int] | None:
    """Grey massing of one model (spec §5, ruled after 6b): the convex hull
    of each solid, non-animated connected component
    (``obj8.solid_components``, welded to 1 mm), components under
    :data:`MIN_COMPONENT_M` in every dimension dropped.  ``(vertices (k, 3)
    float32, triangles (m, 3) uint32, components dropped)``, or ``None``
    when nothing is left."""
    geom = cache.geometry(path)
    if geom is None:
        return None
    verts: list[np.ndarray] = []
    tris: list[np.ndarray] = []
    dropped = 0
    base = 0
    for comp in cache.components(path):
        if comp.animated:
            continue
        pts = geom.vertices[comp.tris.reshape(-1)]
        if (pts.max(axis=0) - pts.min(axis=0) < MIN_COMPONENT_M).all():
            dropped += 1
            continue
        hull = component_hull(pts)
        if hull is None:
            dropped += 1
            continue
        verts.append(hull[0])
        tris.append(hull[1] + base)
        base += hull[0].shape[0]
    if not verts:
        return None if not dropped else (np.zeros((0, 3), np.float32),
                                         np.zeros((0, 3), np.uint32), dropped)
    return (np.concatenate(verts).astype(np.float32),
            np.concatenate(tris).astype(np.uint32), dropped)


def facade_height(def_path: str, param: int, root: str, index) -> float | None:
    """A roofed facade's wall height (the floor X-Plane picks for the
    DSF's height param), ``None`` when the file gives none."""
    from auto_patch_v2.airport import facade as _facade
    fac = _facade.read_facade(def_path, root, index)
    if fac is None or _facade.facade_class(fac) not in (_facade.ROOFED,
                                                       _facade.PARKING_STRUCTURE):
        return None
    if fac.version < 1000:
        return float(param) if param > 0 else None     # v800: the param IS the height
    floor = _facade.floor_for(fac, float(param))
    return floor.top if floor is not None and floor.top > 0 else None


def pack_objects(tile: str, icao: str, bbox: _t.Sequence[float]) -> dict:
    """The §2 reply for the placements inside ``bbox``."""
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import obj8 as _obj8
    from auto_patch_v2.airport import pack as _pack

    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"pack_objects: {tile!r} is not a tile key like +45-123.")
    lat, lon = parsed
    s, w, n, e = _box(bbox)
    out: dict = {"models": [], "placements": [], "facades": [], "missing": []}
    missing: list[str] = out["missing"]

    xroot = xplane_root_for(lat, lon)
    if not xroot:
        missing.append("No X-Plane folder is set for this tile, so its airport pack "
                       "cannot be found.")
        return out
    sel = _pack.select_pack(xroot, str(icao))
    if sel is None:
        missing.append(f"No scenery pack serves {icao} under {xroot}.")
        return out
    dsf_path = _dsf.dsf_path_in_pack(sel.root, lat, lon)
    if not os.path.isfile(dsf_path):
        missing.append(f"The pack {sel.name} places no objects on tile {tile} "
                       "(it has no DSF for it).")
        return out
    mod_root = FNAMES.airport_mod_cache_root()
    pristine = _dw.pristine_dsf_path(dsf_path)
    dump_path = _dsf.find_text_dump(mod_root, sel.name, lat, lon, dsf_path=pristine)
    if not dump_path:
        reason = _dsf.missing_dump_reason(_dsf.mod_cache_dir(mod_root, sel.name), pristine)
        missing.append(f"The buildings of {sel.name} cannot be shown: the pack file "
                       f"{os.path.basename(pristine)} has no readable cached dump "
                       f"({reason}). Building the tile makes it.")
        return out
    index = _obj8.read_library_index(_obj8.library_index_path(mod_root, xroot))
    if index is None:
        missing.append("The X-Plane library index is not cached yet, so objects from "
                       "the X-Plane library are not shown. Building a tile makes it.")
    dump = _dsf.read_dump(dump_path, lambda p: p.lower().endswith(".fac"))

    def inside(la: float, lo: float) -> bool:
        return s <= la <= n and w <= lo <= e

    cache = _obj8.ResourceCache(0.0)
    keys: dict[str, str | None] = {}      # def path -> model key (None = not drawn)
    unresolved: set[str] = set()
    msl = 0
    dropped = 0
    for pl in dump.placements:
        if not pl.def_path.lower().endswith(".obj") or not inside(pl.lat, pl.lon):
            continue
        if pl.kind == "OBJECT_MSL":
            msl += 1
            continue
        if pl.def_path not in keys:
            keys[pl.def_path] = None
            phys = _obj8.resolve_resource(pl.def_path, sel.root, index)
            payload = model_payload(cache, phys) if phys else None
            if phys is None or cache.geometry(phys) is None:
                unresolved.add(pl.def_path)
            elif payload is not None:
                dropped += payload[2]
            if payload is not None and payload[0].shape[0]:
                keys[pl.def_path] = pl.def_path
                out["models"].append({"key": pl.def_path,
                                      "vertices_f32_b64": _b64(payload[0], "<f4"),
                                      "triangles_u32_b64": _b64(payload[1], "<u4")})
        if keys[pl.def_path] is None:
            continue
        agl = float(pl.elevation) if pl.kind == "OBJECT_AGL" and pl.elevation is not None else 0.0
        out["placements"].append({"model": pl.def_path, "lat": pl.lat, "lon": pl.lon,
                                  "heading_deg": pl.heading_deg, "agl_m": agl})
    if unresolved:
        missing.append(f"{len(unresolved)} object file(s) could not be found or read: "
                       + ", ".join(sorted(unresolved)[:5])
                       + (", …" if len(unresolved) > 5 else ""))
    if dropped:
        missing.append(f"{dropped} object part(s) smaller than {MIN_COMPONENT_M:g} m in every "
                       "direction are left out of the grey massing.")
    if msl:
        missing.append(f"{msl} object(s) placed at a fixed sea-level elevation are not shown.")

    heightless: set[str] = set()
    for poly in dump.polygons:
        ring = poly.windings[0]
        clat = sum(p[1] for p in ring) / len(ring)
        clon = sum(p[0] for p in ring) / len(ring)
        if not inside(clat, clon):
            continue
        h = facade_height(poly.def_path, poly.param, sel.root, index)
        if h is None:
            heightless.add(poly.def_path)
            continue
        out["facades"].append({"ring": [[p[1], p[0]] for p in ring], "height_m": h})
    if heightless:
        missing.append(f"{len(heightless)} facade type(s) have no readable building height "
                       "(fences, open lots or unreadable files) and are not shown: "
                       + ", ".join(sorted(heightless)[:5])
                       + (", …" if len(heightless) > 5 else ""))
    return out

