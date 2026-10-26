"""``pack_objects`` — the airport pack's buildings for the patch editor's
3D preview (protocol 1.12, ``docs/specs/patch-editor-20261015.md`` §2, §5).

Reuses the object stage's readers, read-only:

* the pack: ``airport/pack.select_pack`` (the one picker — the same call
  ``auto_patch/engine_v2`` makes for the pack dump);
* the placements: the cached text dump of the pack's tile DSF, located by
  ``airport/dsf.find_text_dump`` in the object stage's read frame
  (``dsf_write.pristine_dsf_path``, ruled right for an edited patch) and
  parsed by ``dsf.read_dump``;
* the models: ``airport/obj8.resolve_resource`` (pack-relative, then the
  cached library index) and ``ResourceCache``, sent as GREY MASSING
  (``pack_massing``: one convex hull per solid component);
* the facades: ``airport/facade.read_facade`` and ``floor_for``.

Placements carry ``agl_m`` (``OBJECT`` = 0, ``OBJECT_AGL`` = its offset).
Nothing is regenerated: a missing dump, library index or file is a
sentence in ``missing``.

ASYNCHRONOUS (spec §5): reading a pack takes seconds, and a command
handler runs on the transport's read loop, so the command replies
``{"status": "started"}`` and a worker thread completes it with ONE
:class:`~o4_engine.events.PackObjectsReady` carrying the command's id.
The worker touches no secret store (the ``secret_broker`` threading
contract only forbids blocking the read loop).  Results are kept for the
session, keyed by the pack DSF's path and mtime (and the request), so
reopening the 3D window answers at once.
"""
from __future__ import annotations

import base64
import os
import threading
import typing as _t

import numpy as np

import O4_File_Names as FNAMES

from . import pack_massing as _mass

__all__ = ["pack_objects", "start_pack_objects", "b64_array"]

#: Session cache: (dsf path, dsf mtime, dump path, icao, bbox) -> reply.
_CACHE: dict[tuple, dict] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_SIZE = 4


def _box(bbox: _t.Any) -> tuple[float, float, float, float]:
    try:
        s, w, n, e = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise ValueError("pack_objects: bbox must be [min_lat, min_lon, max_lat, "
                         "max_lon] in degrees.") from None
    if not (s < n and w < e):
        raise ValueError(f"pack_objects: bbox {[s, w, n, e]} is empty.")
    return s, w, n, e


def _tile(tile: _t.Any) -> tuple[int, int]:
    parsed = FNAMES.parse_tile_key(tile)
    if parsed is None:
        raise ValueError(f"pack_objects: {tile!r} is not a tile key like +45-123.")
    return parsed


def b64_array(a: np.ndarray, dtype: str) -> str:
    """A packed little-endian array as the wire's base64 (spec §2)."""
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode("ascii")


def xplane_root_for(lat: int, lon: int) -> str | None:
    """The X-Plane install the tile's build reads (its CIFP folder's
    install — ``patch_commands`` and the tile driver resolve it so)."""
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    from auto_patch_v2.airport.cifp import xplane_root_from_cifp_path
    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    cifp_dir = VMAP.resolve_cifp_dir_for_tile(tile)
    return xplane_root_from_cifp_path(cifp_dir) if cifp_dir else None


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


def _list(names: set[str]) -> str:
    return ", ".join(sorted(names)[:5]) + (", …" if len(names) > 5 else "")


def pack_objects(tile: str, icao: str, bbox: _t.Sequence[float],
                 footprints_only: bool = False) -> dict:
    """The §2 result for the placements inside ``bbox`` (synchronous; the
    command runs it through :func:`start_pack_objects`).

    ``footprints_only`` (issue #797) is the 2-D map's answer: each model is
    ``{key, plan_hull_f32_b64}`` — its plan outline as ``(x, z)`` pairs
    (:func:`pack_massing.plan_hull`) — instead of the massing's vertices
    and triangles, which the map never draws (OTHH: 47.0 MB, 61 % of it
    triangles).  Nothing is dropped to fit a cap in this mode: an outline
    is a few points.  Placements, facades and ``missing`` are the same."""
    from auto_patch_v2.airport import dsf as _dsf
    from auto_patch_v2.airport import dsf_write as _dw
    from auto_patch_v2.airport import obj8 as _obj8
    from auto_patch_v2.airport import pack as _pack

    lat, lon = _tile(tile)
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
    key = (pristine, os.path.getmtime(pristine), dump_path, str(icao).upper(),
           tuple(round(v, 7) for v in (s, w, n, e)), bool(footprints_only))
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return hit

    index = _obj8.read_library_index(_obj8.library_index_path(mod_root, xroot))
    if index is None:
        missing.append("The X-Plane library index is not cached yet, so objects from "
                       "the X-Plane library are not shown. Building a tile makes it.")
    dump = _dsf.read_dump(dump_path, lambda p: p.lower().endswith(".fac"))

    def inside(la: float, lo: float) -> bool:
        return s <= la <= n and w <= lo <= e

    # The build reads packs through the §51 (6) input quantum; the preview
    # shows what the build reads, so it enters through the same one.
    from auto_patch_v2.airport import frame_entry as _fe
    from auto_patch_v2.law.tables import load_default
    cache = _obj8.ResourceCache(0.0, _fe.quantum(load_default()))
    hulls: dict[str, list[_mass.Hull]] = {}
    unresolved: set[str] = set()
    seen: set[str] = set()
    placements: list[dict] = []
    msl = clutter = 0
    for pl in dump.placements:
        if not pl.def_path.lower().endswith(".obj") or not inside(pl.lat, pl.lon):
            continue
        if pl.kind == "OBJECT_MSL":
            msl += 1
            continue
        if pl.def_path not in seen:
            seen.add(pl.def_path)
            phys = _obj8.resolve_resource(pl.def_path, sel.root, index)
            read = _mass.model_hulls(cache, phys) if phys else None
            if read is None:
                unresolved.add(pl.def_path)
            else:
                hulls[pl.def_path], dropped = read
                clutter += dropped
        agl = float(pl.elevation) if pl.kind == "OBJECT_AGL" and pl.elevation is not None else 0.0
        placements.append({"model": pl.def_path, "lat": pl.lat, "lon": pl.lon,
                           "heading_deg": pl.heading_deg, "agl_m": agl})

    heightless: set[str] = set()
    for poly in dump.polygons:
        ring = poly.windings[0]
        if not inside(sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)):
            continue
        h = facade_height(poly.def_path, poly.param, sel.root, index)
        if h is None:
            heightless.add(poly.def_path)
            continue
        out["facades"].append({"ring": [[p[1], p[0]] for p in ring], "height_m": h,
                               "def": poly.def_path})

    capped = 0 if footprints_only else _mass.fit_to_cap(
        hulls, 120 * len(placements)
        + sum(40 * len(f["ring"]) + 40 for f in out["facades"]))
    for path, hs in hulls.items():
        if hs and footprints_only:
            ring = _mass.plan_hull(hs)
            if len(ring) >= 3:
                out["models"].append({"key": path,
                                      "plan_hull_f32_b64": b64_array(ring, "<f4")})
        elif hs:
            v, t = _mass.pack_model(hs)
            out["models"].append({"key": path, "vertices_f32_b64": b64_array(v, "<f4"),
                                  "triangles_u32_b64": b64_array(t, "<u4")})
    drawn = {m["key"] for m in out["models"]}
    out["placements"] = [p for p in placements if p["model"] in drawn]

    if unresolved:
        missing.append(f"{len(unresolved)} object file(s) could not be found or read: "
                       + _list(unresolved))
    if clutter:
        missing.append(f"{clutter} object part(s) smaller than {_mass.MIN_COMPONENT_M:g} m in "
                       "every direction are left out of the grey massing.")
    if capped:
        missing.append(f"{capped} of the smallest object part(s) are left out to keep the "
                       f"buildings under {_mass.MAX_REPLY_BYTES // 1_000_000} MB.")
    if msl:
        missing.append(f"{msl} object(s) placed at a fixed sea-level elevation are not shown.")
    if heightless:
        missing.append(f"{len(heightless)} facade type(s) have no readable building height "
                       "(fences, open lots or unreadable files) and are not shown: "
                       + _list(heightless))
    with _CACHE_LOCK:
        _CACHE[key] = out
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return out


def start_pack_objects(emit: _t.Callable[[_t.Any], None], tile: str, icao: str,
                       bbox: _t.Sequence[float], request: _t.Any = None,
                       footprints_only: bool = False) -> dict:
    """The command: arguments are checked here (a bad one is an ``ok:false``
    reply), the pack is read on a worker thread, and ``PackObjectsReady``
    with ``request`` = the command's id completes it."""
    from .events import PackObjectsReady
    _tile(tile)
    _box(bbox)

    def work() -> None:
        try:
            event = PackObjectsReady(request=request, result=pack_objects(
                tile, icao, bbox, footprints_only=bool(footprints_only)))
        except Exception as error:      # the event carries it; the session lives on
            event = PackObjectsReady(request=request, error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-pack-objects").start()
    return {"status": "started"}
