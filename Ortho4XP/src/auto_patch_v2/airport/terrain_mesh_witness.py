"""A COMPANION TERRAIN MESH IS A WITNESS OF CUTS (owner RULINGS 2026-11-03,
answer 4 to Q-D; spec ``docs/specs/rail-piece-ends-station-spec.md`` R6).

Owner, 2026-11-03: "Look at the package provided ENGM mesh, that will tell
you exactly what the developer intended".  An installed scenery pack OTHER
than the airport's own may carry the airport's terrain: a DSF over the
airport's tile whose PHYSICAL patches hold EXPLICIT vertex elevations inside
the airport boundary (a hand-made mesh; the base mesh's vertices read the
tile's elevation raster, sentinel :data:`RASTER_Z`).  Where one is installed
its BELOW-GRADE regions -- triangles standing at least ``[q5]
portal_depth_min_m`` under the mesh's own FIELD level (the explicit
elevation holding the most plan area inside the boundary) -- state where the ground is open and how
deep, measured under that field.  An OVERLAY DSF (``sim/overlay 1``) carries
no terrain, and a DSF written by this engine is never a companion (its
``sim/creation_agent`` names it): the witness is the developer's, not our own
last build.  Limit: a 7z-compressed DSF's header cannot be read without a
dump, so it is not _screened in.

The pack is found by COVERAGE alone (``airport/pack_local.tile_candidates``:
an enabled pack beside the airport's with no apt.dat and the tile's DSF),
never by name.  The pre-build refresh dumps it (``engine_v2.
fresh_pack_dump``, :func:`dump_candidates`); the load stage reads the made
dump from the mod cache (``airport/dsf.content_keyed_dump``) and never runs
DSFTool.  Below the objects in the
depth ladder (answer 4): this module answers "is it open here, how deep";
the pack's own objects still set a depth where they state one.

MEASURED ENGM (zzz mesh over +60+011): the field flat at 207.0 m with three
cuts -- the station slot (floor 192.0), the north rail portal box (197.0)
and a hole beside a service-tunnel portal (192.0); every false rail ramp of
#1738 and every airside service mouth is flat in it.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from . import dsf as _dsf
from .dsf_commands import header_properties

__all__ = ["RASTER_Z", "dump_candidates", "log_line", "read"]

#: a DSF vertex elevation that defers to the tile's elevation raster
RASTER_Z = -32768.0
#: creation-agent fragments of a DSF this engine wrote (``O4_Tile_Build_Log.
#: creation_agent``; older tiles and patched DSFs say ``Ortho4XP``)
_OWN_AGENTS = ("ortho4xp", "xpterrainbuilder")
_PHYSICAL = 1
#: a cut's rim: the mesh this far outside its outline stands the depth over its floor
_RIM_M = 10.0
#: a below-grade sliver under this plan area is no cut
_MIN_CUT_M2 = 10.0
#: a cut is a trench or a portal box: its mean width (2 x area / perimeter) is
#: at most this; a broad lowered terrace is no cut (MEASURED ENGM: the cuts
#: read 17-57 m, a lowered terrace west of the runways about 1 km)
_MAX_WIDTH_M = 150.0


@_dc.dataclass(frozen=True)
class _MeshCut:
    """One below-grade region of a companion mesh, in the airport frame."""

    polygon: Polygon
    floor_z: float
    depth_m: float


@_dc.dataclass(frozen=True)
class _MeshWitness:
    """The companion mesh's cuts and the field level they are measured under."""

    dsf_path: str
    field_z: float
    cuts: tuple[_MeshCut, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_tree", STRtree([c.polygon for c in self.cuts])
                           if self.cuts else None)

    def at(self, xy: tuple[float, float], tol_m: float) -> "_MeshCut | None":
        """The deepest cut within ``tol_m`` of the frame point ``xy``."""
        if self._tree is None:
            return None
        p = Point(xy)
        hits = [self.cuts[int(j)] for j in self._tree.query(p.buffer(tol_m))]
        hits = [c for c in hits if c.polygon.distance(p) <= tol_m]
        return max(hits, key=lambda c: c.depth_m) if hits else None


def _read_cuts(text_lines: _t.Iterable[str], raster: "_t.Callable[[float, float], float] | None",
              boundary: Polygon, enter: _t.Callable[[float, float], tuple],
              ll_box: tuple[float, float, float, float],
              min_depth_m: float) -> "tuple[float, list[_MeshCut]] | None":
    """``(field_z, cuts)`` from a DSFTool text dump, or ``None`` when the
    dump is this engine's own or holds no explicit physical elevation inside
    ``boundary`` (the airport frame).  ``enter(lon, lat)`` is the frame and
    ``ll_box`` = ``(west, south, east, north)`` the boundary's lon/lat box."""
    x0, y0, x1, y1 = ll_box
    tris: list = []
    phys, ptype, verts = False, -1, []
    for line in text_lines:
        if line.startswith("PATCH_VERTEX"):
            if ptype >= 0 and phys:
                t = line.split()
                verts.append((float(t[1]), float(t[2]), float(t[3])))
            continue
        if line.startswith("PROPERTY sim/creation_agent") and _own(line):
            return None
        if line.startswith("BEGIN_PATCH"):
            t = line.split()
            phys, ptype, verts = bool(int(t[4]) & _PHYSICAL), -1, []
        elif line.startswith("BEGIN_PRIMITIVE"):
            ptype, verts = int(line.split()[1]), []
        elif line.startswith("END_PRIMITIVE"):
            if verts and any(x0 <= v[0] <= x1 and y0 <= v[1] <= y1 for v in verts):
                tris.extend(_expand(ptype, verts))
            ptype, verts = -1, []
    from shapely.prepared import prep
    fence = prep(boundary)
    inside = []
    for t in tris:
        xy = [enter(v[0], v[1]) for v in t]
        if all(fence.covers(Point(p)) for p in xy):
            inside.append((t, xy))
    # the FIELD: the explicit elevation holding the most plan area
    area: dict = {}
    for t, xy in inside:
        a = Polygon(xy).area / 3.0
        for v in t:
            if v[2] > RASTER_Z + 1.0:
                area[round(v[2], 1)] = area.get(round(v[2], 1), 0.0) + a
    if not area:
        return None
    field = max(area, key=area.__getitem__)
    low: list = []
    for t, xy in inside:
        tz = [v[2] if v[2] > RASTER_Z + 1.0 else (raster(v[0], v[1]) if raster else field)
              for v in t]
        if max(tz) <= field - min_depth_m:
            low.append((Polygon(xy), min(tz)))
    cuts = []
    if low:
        merged = unary_union([p.buffer(0.05) for p, _z in low]).buffer(-0.05)
        surface = _Surface(inside, raster, field)
        for g in getattr(merged, "geoms", [merged]):
            if g.is_empty or g.geom_type != "Polygon" or g.area < _MIN_CUT_M2 \
                    or 2.0 * g.area / g.length > _MAX_WIDTH_M:
                continue
            zs_in = [z for p, z in low if p.intersects(g.buffer(0.1))]
            if not zs_in:
                continue
            fl = min(zs_in)
            # A CUT HAS A RIM: the mesh just outside it stands the depth over
            # its floor.  A broad natural low (a valley, a lower runway's
            # level) slopes up to its surround and is no cut.
            ring = g.buffer(_RIM_M).exterior
            n = max(8, int(ring.length // _RIM_M))
            rim = [z for k in range(n) for q in (ring.interpolate(k / n, normalized=True),)
                   if (z := surface.z(q.x, q.y)) is not None]
            if not rim or sorted(rim)[len(rim) // 2] - fl < min_depth_m:
                continue
            cuts.append(_MeshCut(g, float(fl), float(field - fl)))
    return float(field), cuts


def _expand(ptype: int, v: list) -> list:
    """A DSF primitive's triangles by vertex index: 0 a list of triangles,
    1 a strip (every other one turned so all wind alike), 2 a fan.  The
    winding is immaterial here (a plan footprint and a barycentric z)."""
    if ptype == 0:
        idx = [(k, k + 1, k + 2) for k in range(0, len(v) - 2, 3)]
    elif ptype == 1:
        idx = [(k, k + 1, k + 2) for k in range(len(v) - 2)]
    elif ptype == 2:
        idx = [(0, k, k + 1) for k in range(1, len(v) - 1)]
    else:
        idx = []
    return [(v[a], v[b], v[c]) for a, b, c in idx
            if v[a][:2] != v[b][:2] and v[b][:2] != v[c][:2] and v[a][:2] != v[c][:2]]


class _Surface:
    """The mesh's own surface over the frame (barycentric in its triangles)."""

    def __init__(self, inside, raster, field: float) -> None:
        self._tris = []
        for t, xy in inside:
            z = [v[2] if v[2] > RASTER_Z + 1.0 else (raster(v[0], v[1]) if raster else field)
                 for v in t]
            self._tris.append((xy, z))
        self._tree = STRtree([Polygon(xy) for xy, _z in self._tris]) if self._tris else None

    def z(self, x: float, y: float) -> "float | None":
        if self._tree is None:
            return None
        for j in self._tree.query(Point(x, y), predicate="intersects"):
            (x1, y1), (x2, y2), (x3, y3) = self._tris[int(j)][0]
            z1, z2, z3 = self._tris[int(j)][1]
            d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
            if d == 0:
                continue
            w1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
            w2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
            return w1 * z1 + w2 * z2 + (1.0 - w1 - w2) * z3
        return None


def _own(agent: str) -> bool:
    return any(a in agent.lower() for a in _OWN_AGENTS)


def _screened(path: str) -> bool:
    """Whether the DSF at ``path`` may be a companion mesh: its header reads
    (an uncompressed DSF), it is no overlay and this engine did not write it.
    A 7z-compressed DSF is not _screened in (its header cannot be read without
    the dump; named in the module's limits)."""
    pr = header_properties(path)
    if pr is None:
        return False
    return pr.get("sim/overlay", "0").strip() != "1" and not _own(pr.get("sim/creation_agent", ""))


def dump_candidates(main_root: str, lat: int, lon: int) -> list[str]:
    """The installed packs whose tile DSF may be a companion mesh
    (``pack_local.tile_candidates``, then :func:`_screened`): the packs whose
    DSF the pre-build refresh dumps (``engine_v2.fresh_pack_dump``) so
    :func:`read` finds the dump -- the load stage never runs DSFTool."""
    from .pack_local import tile_candidates
    return [r for r in tile_candidates(main_root, lat, lon)
            if _screened(_dsf.dsf_path_in_pack(r, lat, lon))]


def read(airport, law, mod_cache_root: str) -> "_MeshWitness | None":
    """The companion mesh witness for ``airport`` (module doc), or ``None``:
    no pack, no boundary, no candidate, no made dump, or no explicit
    elevation inside the boundary."""
    import math
    pack = getattr(airport, "pack", None)
    bounds = getattr(airport, "boundaries", ()) or ()
    if pack is None or not bounds or not mod_cache_root or not pack.pack_root:
        return None
    lat0, lon0 = airport.frame.origin
    lat, lon = int(math.floor(lat0)), int(math.floor(lon0))
    polys = []
    for b in bounds:
        try:
            p = Polygon(b.outer, list(b.holes))
        except (ValueError, TypeError):
            continue
        p = p if p.is_valid else p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    boundary = unary_union(polys)
    enter = airport.frame.entry()
    to_ll = airport.frame.transformers()[1]
    bx0, by0, bx1, by1 = boundary.bounds
    lls = [to_ll(x, y) for x, y in ((bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1))]
    ll_box = (min(c[1] for c in lls), min(c[0] for c in lls),
              max(c[1] for c in lls), max(c[0] for c in lls))
    depth = float(law.tables.terrain_witness.q5.portal_depth_min_m)
    for root in dump_candidates(pack.pack_root, lat, lon):
        path = _dsf.dsf_path_in_pack(root, lat, lon)
        text = _dsf.content_keyed_dump(
            _dsf.mod_cache_dir(mod_cache_root, os.path.basename(os.path.normpath(root))), path)
        if text is None:
            continue
        got = _read(path, text, boundary, enter, ll_box, depth)
        if got is not None:
            return got
    return None


def log_line(icao: str, w) -> str:
    """The build log's one line for the witness."""
    if w is None:
        return f"[terrain-mesh] {icao}: no companion terrain mesh"
    pack = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(w.dsf_path))))
    return (f"[terrain-mesh] {icao}: {pack} field {w.field_z:.1f} m, {len(w.cuts)} cut(s): "
            + ", ".join(f"{c.depth_m:.1f} m over {c.polygon.area:,.0f} m2" for c in w.cuts))


def _read(path, text, boundary, enter, ll_box, depth) -> "_MeshWitness | None":
    raster = _raster_reader(text)
    with open(text, encoding="utf-8", errors="replace") as fh:
        got = _read_cuts(fh, raster, boundary, enter, ll_box, depth)
    if got is None:
        return None
    field, cuts = got
    return _MeshWitness(path, field, tuple(cuts))


def _raster_reader(text_path: str):
    """The dump's ``elevation`` raster as ``f(lon, lat)`` (bilinear; rows
    stored south first), or ``None``."""
    import numpy as np
    names, data, west, south = [], None, None, None
    with open(text_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("PROPERTY sim/west"):
                west = int(line.split()[2])
            elif line.startswith("PROPERTY sim/south"):
                south = int(line.split()[2])
            elif line.startswith("RASTER_DEF"):
                names.append(line.split()[1])
            elif line.startswith("RASTER_DATA") and data is None and names[:1] == ["elevation"]:
                kv = dict(t.split("=", 1) for t in line.split()[1:6] if "=" in t)
                path = line.split(None, 6)[6].strip() if len(line.split()) > 6 else ""
                w, h = int(kv["width"]), int(kv["height"])
                if os.path.isfile(path):
                    data = np.fromfile(path, dtype="<i2")[: w * h].reshape(h, w).astype(float)
                    data = data * float(kv.get("scale", 1.0)) + float(kv.get("offset", 0.0))
            elif line.startswith("BEGIN_PATCH"):
                break
    if data is None or west is None or south is None:
        return None
    n = data.shape[0]

    def z(lon: float, lat: float) -> float:
        fx = min(max((lon - west) * (n - 1), 0.0), n - 1.001)
        fy = min(max((lat - south) * (n - 1), 0.0), n - 1.001)
        i, j = int(fy), int(fx)
        a, b = fy - i, fx - j
        return float(data[i, j] * (1 - a) * (1 - b) + data[i, j + 1] * (1 - a) * b
                     + data[i + 1, j] * a * (1 - b) + data[i + 1, j + 1] * a * b)
    return z
