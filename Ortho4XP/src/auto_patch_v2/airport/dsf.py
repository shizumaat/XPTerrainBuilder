"""DSF objects and facades through the EXISTING DSFTool dump cache
(``Airport_mod_cache/<pack>/<tile>.dsf.<tag>.text``, user ruling
2026-07-15: Ortho4XP caches never litter pack folders) — read-only: a
missing dump is reported, never produced here (the dump is a
``--refresh-data`` act of the harness).

Read from the dump (v1 ``dsf_reader`` is the reference for the grammar):

* ``POLYGON_DEF`` / ``BEGIN_POLYGON idx param coords_per_point`` /
  ``BEGIN_WINDING`` / ``POLYGON_POINT lon lat [clon clat]`` — draped
  polygons; ``.fac`` facades whose path names a terminal / hangar /
  stock building are BUILDING footprints (v1 ``_building_role_for_def``);
* ``OBJECT_DEF`` / ``OBJECT idx lon lat heading`` (``OBJECT_MSL`` /
  ``OBJECT_AGL`` carry an elevation before the heading) — placements;
* the per-pack ``o4_object_footprints_<tile>.cache`` sidecar (a pickle of
  ``{"fingerprint", "result": [(outer, holes, role), ...]}``) — the OBJ8
  structure footprints v1 partitioned, reused as-is.

OBJ8 hardness (``ATTR_hard`` / ``ATTR_hard_deck``) is scanned only for a
PACK-RELATIVE object path; library paths (``lib/...``) need the X-Plane
library index, which M1 does not resolve (reported as ``hard_deck=None``).
"""
from __future__ import annotations

import dataclasses as _dc
import os
import pickle
import typing as _t

from .apt_dat import LonLat, _bezier, _segments_for, _sparsify, _LAT_SCALE
import math

__all__ = ["DsfPolygon", "DsfPlacement", "DsfDump", "find_text_dump",
           "read_dump", "building_role_for_def", "read_footprint_cache",
           "obj8_hardness", "mod_cache_dir"]


@_dc.dataclass(frozen=True)
class DsfPolygon:
    """One draped polygon: ``windings[0]`` outer, rest holes; rings are
    unclosed ``(lon, lat)`` tuples, beziers flattened."""

    def_path: str
    param: int
    windings: tuple[tuple[LonLat, ...], ...]


@_dc.dataclass(frozen=True)
class DsfPlacement:
    """One ``OBJECT*`` placement."""

    def_path: str
    lon: float
    lat: float
    heading_deg: float
    elevation: float | None


@_dc.dataclass(frozen=True)
class DsfDump:
    """The parts of a dump v2 reads."""

    path: str
    object_defs: tuple[str, ...]
    polygon_defs: tuple[str, ...]
    polygons: tuple[DsfPolygon, ...]
    placements: tuple[DsfPlacement, ...]


def mod_cache_dir(mod_cache_root: str, pack_name: str) -> str:
    """``<root>/<pack folder name>`` — the pack's Ortho4XP-only caches."""
    return os.path.join(mod_cache_root, pack_name)


def find_text_dump(mod_cache_root: str, pack_name: str, lat: int,
                   lon: int) -> str | None:
    """The cached ``<tile>.dsf.<tag>.text`` for the pack's tile DSF."""
    d = mod_cache_dir(mod_cache_root, pack_name)
    if not os.path.isdir(d):
        return None
    prefix = f"{lat:+03d}{lon:+04d}.dsf."
    hits = sorted(n for n in os.listdir(d)
                  if n.startswith(prefix) and n.endswith(".text"))
    return os.path.join(d, hits[-1]) if hits else None


def read_dump(path: str, accept_polygon: _t.Callable[[str], bool] | None = None
              ) -> DsfDump:
    """Parse the dump; ``accept_polygon(def_path)`` limits which polygons
    are materialised (default: facades and pavement pages only)."""
    object_defs: list[str] = []
    polygon_defs: list[str] = []
    polygons: list[DsfPolygon] = []
    placements: list[DsfPlacement] = []
    cur_def: int | None = None
    cur_param = 0
    cur_cpp = 2
    windings: list[list[list[str]]] = []
    winding: list[list[str]] | None = None
    accept = accept_polygon or (lambda p: p.lower().endswith((".fac", ".pol")))
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            if not raw or raw[0] in "#\n":
                continue
            toks = raw.split()
            kw = toks[0]
            if kw == "OBJECT_DEF":
                object_defs.append(raw[len("OBJECT_DEF"):].strip())
            elif kw == "POLYGON_DEF":
                polygon_defs.append(raw[len("POLYGON_DEF"):].strip())
            elif kw == "OBJECT" and len(toks) >= 4:
                _placement(placements, object_defs, toks, 4, None)
            elif kw in ("OBJECT_MSL", "OBJECT_AGL") and len(toks) >= 5:
                _placement(placements, object_defs, toks, 5, 4)
            elif kw == "BEGIN_POLYGON" and len(toks) >= 4:
                try:
                    idx = int(toks[1])
                    cur_param, cur_cpp = int(toks[2]), int(toks[3])
                except ValueError:
                    continue
                if 0 <= idx < len(polygon_defs) and accept(polygon_defs[idx]):
                    cur_def, windings = idx, []
                else:
                    cur_def = None
            elif kw == "BEGIN_WINDING" and cur_def is not None:
                winding = []
            elif kw == "POLYGON_POINT" and winding is not None:
                winding.append(toks[1:])
            elif kw == "END_WINDING" and winding is not None:
                windings.append(winding)
                winding = None
            elif kw == "END_POLYGON" and cur_def is not None:
                rings = tuple(r for r in (_flatten(w, cur_cpp) for w in windings)
                              if len(r) >= 3)
                if rings:
                    polygons.append(DsfPolygon(polygon_defs[cur_def],
                                               cur_param, rings))
                cur_def = None
    return DsfDump(path, tuple(object_defs), tuple(polygon_defs),
                   tuple(polygons), tuple(placements))


def _placement(out: list[DsfPlacement], defs: list[str], toks: list[str],
               hi: int, elev_i: int | None) -> None:
    try:
        oi = int(toks[1])
        lon, lat = float(toks[2]), float(toks[3])
        heading = float(toks[hi]) if len(toks) > hi else 0.0
        elev = float(toks[elev_i]) if elev_i is not None else None
    except (ValueError, IndexError):
        return
    if 0 <= oi < len(defs):
        out.append(DsfPlacement(defs[oi], lon, lat, heading, elev))


def _flatten(points: list[list[str]], cpp: int) -> tuple[LonLat, ...]:
    """A winding's points; ``cpp >= 4`` carries a control point per
    node (quadratic bezier into the NEXT node, mirrored like apt.dat)."""
    n = len(points)
    if n < 3:
        return ()
    try:
        xy = [(float(p[0]), float(p[1])) for p in points]
        # the control point is the LAST two columns: a facade point is
        # ``lon lat [wall] [ctrl_lon ctrl_lat]`` (cpp 2/3/4/5), so at cpp 5
        # columns 2-3 are ``wall ctrl_lon`` (measured SPJC: one
        # Cargo_Terminal.fac winding flattened 2,000 km wide and its union
        # swallowed 128 of 135 pads)
        ctrl = [(float(p[cpp - 2]), float(p[cpp - 1])) if cpp >= 4 and len(p) >= cpp
                else None for p in points]
    except ValueError:
        return ()
    if cpp < 4 or all(c is None or c == xy[i] for i, c in enumerate(ctrl)):
        return tuple(xy)
    lon_scale = _LAT_SCALE * math.cos(math.radians(xy[0][1]))
    out: list[LonLat] = []
    for i in range(n):
        a, b = xy[i], xy[(i + 1) % n]
        ca, cb = ctrl[i], ctrl[(i + 1) % n]
        if not out or out[-1] != a:
            out.append(a)
        if a == b:
            continue
        cs: list[LonLat] = []
        if ca is not None and ca != a:
            cs.append(ca)
        if cb is not None and cb != b:
            cs.append((2 * b[0] - cb[0], 2 * b[1] - cb[1]))
        if not cs:
            continue
        ctrls = tuple(cs)
        for p in _bezier(a, ctrls, b, _segments_for(a, ctrls, b, lon_scale))[1:-1]:
            if out[-1] != p:
                out.append(p)
    return tuple(_sparsify(out, True, lon_scale))


#: X-Plane STOCK pavement namespaces (v1 ``_PAVEMENT_PREFIXES``) and the
#: decorative sub-namespaces inside them that are NOT bulk pavement.
PAVEMENT_PREFIXES = ("lib/airport/pavement/", "lib/airport/ground/pavement/")
PAVEMENT_SKIP = ("/lines/", "/markings/", "/lights/", "/decals/", "dirsigns")
#: Third-party ``.pol`` defs are pavement when the path names a material
#: (v1 ``DSF_PAVEMENT_MATERIAL_TOKENS``) and nothing decorative/terrain.
MATERIAL_TOKENS = ("asphalt", "concrete", "asphalte", "beton", "béton",
                   "hormigon", "hormigón", "asfalto", "cemento", "calcestruzzo",
                   "betão", "concreto")
THIRD_PARTY_SKIP = PAVEMENT_SKIP + (
    "grass", "terrain", "dirt", "gravel", "soil", "mud", "snow", "paint",
    "line", "marking", "light", "decal", "sign", "logo", "grunge", "stain",
    "skid", "crack_line")


def is_pavement_def(path: str) -> bool:
    """Whether a ``POLYGON_DEF`` path is bulk pavement (v1
    ``_is_pavement_def``, name tier only — the SURFACE-attribute tier
    needs the resolved ``.pol`` file, which M1 does not read)."""
    p = path.lower()
    if p.startswith(PAVEMENT_PREFIXES):
        return not any(s in p for s in PAVEMENT_SKIP)
    if p.endswith(".pol") and any(t in p for t in MATERIAL_TOKENS):
        return not any(s in p for s in THIRD_PARTY_SKIP)
    return False


def pavement_surface_code(path: str) -> int:
    """apt.dat surface code implied by a pavement def path (concrete
    when the path says so, asphalt otherwise)."""
    p = path.lower()
    return 2 if any(t in p for t in ("concrete", "beton", "béton", "hormig",
                                     "cemento", "calcestruzzo", "betão",
                                     "concreto")) else 1


def building_role_for_def(path: str) -> str | None:
    """``terminal`` / ``hangar`` / ``bridge`` / ``building`` for a facade
    path that is a building (v1 ``_building_role_for_def``), else None."""
    p = path.lower()
    if not p.endswith(".fac"):
        return None
    if "term_bridge" in p:
        return "bridge"
    if "term_building" in p:
        return "terminal"
    if "hangar" in p:
        return "hangar"
    if "/misc_buildings/" in p or p.startswith("lib/airport/buildings/"):
        return "building"
    return None


def read_footprint_cache(path: str) -> list[tuple[tuple[LonLat, ...], str]]:
    """The OBJ8 structure footprints v1 cached for the pack's tile:
    ``[(outer_ring, role), ...]`` (rings ``(lon, lat)``, unclosed).
    Unreadable or unexpected content -> ``[]`` (reported by the caller)."""
    try:
        with open(path, "rb") as fh:
            blob = pickle.load(fh)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError,
            ValueError):
        return []
    result = blob.get("result") if isinstance(blob, dict) else blob
    out: list[tuple[tuple[LonLat, ...], str]] = []
    for item in result or []:
        try:
            outer = tuple((float(a), float(b)) for a, b in item[0])
            role = str(item[-1]) if len(item) >= 2 else "object"
        except (TypeError, ValueError, IndexError):
            continue
        if len(outer) >= 3:
            if outer[0] == outer[-1]:
                outer = outer[:-1]
            out.append((outer, role))
    return out


def obj8_hardness(obj_path: str) -> tuple[bool, bool] | None:
    """``(hard, hard_deck)`` from an OBJ8 file's attributes, ``None``
    when the file is absent (a library path M1 does not resolve)."""
    if not os.path.isfile(obj_path):
        return None
    hard = deck = False
    try:
        with open(obj_path, "r", errors="replace") as fh:
            for line in fh:
                kw = line.split(maxsplit=1)[0] if line.strip() else ""
                if kw == "ATTR_hard_deck":
                    deck = True
                elif kw == "ATTR_hard":
                    hard = True
    except OSError:
        return None
    return hard, deck
