#!/usr/bin/env python3
"""WHAT X-PLANE DRAWS AT A SITE (#1903): the pack's OBJ geometry as the
WRITTEN DSF places it, against the terrain the TILE DSF draws under it.

Every earlier bar compared the engine's own numbers with each other (the
patch floor with itself, the plan seat with the plan).  This reads only
what the sim reads:

* the airport pack(s)' DSF as installed -- each ``OBJECT`` / ``OBJECT_AGL``
  / ``OBJECT_MSL`` row, its resource resolved as X-Plane does (pack path,
  then the library index), its OBJ8 solid triangles placed by the row:
  ``OBJECT`` puts y = 0 on the DRAWN mesh under the anchor, ``OBJECT_AGL``
  that plus the row's offset, ``OBJECT_MSL`` the row's own elevation;
* the tile DSF's physical terrain triangles
  (``auto_patch_v2.airport.dsf_mesh``), sampled barycentrically
  (``auto_patch.mesh_sampler``) -- never the patch, sidecars or plan.

Per solid component of every placement reaching a site it reports, in the
owner's terms (visibility bars: pavement 0.05 m, ground 0.5 m):

* BOTTOM -- the component's LOWEST surface at every plan point against the
  mesh there: ``+`` floats over the ground, ``-`` is buried;
* OPEN EDGES -- each run of the plan outline with no wall rising from it
  (a deck end, a mouth, a ramp end): its top surface and its floor against
  the drawn surface just outside (the mesh, or another object's surface
  nearer the edge's levels) -- the seam step a pilot sees; for a run that
  is a mouth (a floor under a roof, or a floor that meets the ground) the
  opening width against the width of drawn ground at the floor's level in
  front of it (the ramp);
* SHAPE -- whether the component is a CONCAVE CUT SHELL (an open-top
  hollow: its top surface stands under its own rim over most of its plan,
  nothing over it), COVERED (a deck or roof over a floor) or a CONVEX BODY,
  read from the OBJ geometry alone (#1914).

It writes nothing outside a temp directory (and ``--cache``): the pack DSF
is dumped to temp text, the tile DSF streamed through a FIFO.  It derives
no law; a point off every tile triangle reads missing, never zero.

Usage::

    venv/bin/python tools/drawn_check.py \\
        --pack "<Custom Scenery>/<airport pack>" [--pack ...] \\
        --site NAME=LAT,LON[,RADIUS_M] [--site ...] [--object SUBSTR] \\
        [--custom-scenery DIR] [--tile-dsf PATH] [--cache DIR] [--json OUT]
"""
from __future__ import annotations

import os as _o4os, sys as _o4sys                                    # noqa: E402
_o4sys.path.insert(0, _o4os.path.join(_o4os.path.dirname(_o4os.path.dirname(
    _o4os.path.abspath(__file__))), "src"))
import O4_Console_Encoding as _o4console                             # noqa: E402
_o4console.configure_console_streams()

import argparse
import dataclasses as dc
import glob
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile

import numpy as np

#: owner visibility bars (memory judge-by-visibility-bars, 2026-10-15)
PAVEMENT_BAR_M = 0.05
GROUND_BAR_M = 0.5
#: metres per degree of latitude (obj8_reader's constant)
K_LAT = 111320.0
#: a vertex this far over an edge's surface, this close in plan, is a wall
WALL_RISE_M = 0.4
WALL_REACH_M = 0.75
#: the drawn surface is read this far outside an open edge
OUTSIDE_M = 1.5
#: two surfaces this far apart at one plan point are a roof over a floor
STACKED_M = 1.5
#: a component with less plan than this is a pole, a light, a sign
MIN_PLAN_M2 = 4.0
#: a hollow: the top surface this far under the component's own rim
HOLLOW_M = 1.0
#: an outline cell faces away from the covered plan within this radius
NORMAL_M = 3.0
#: a component whose surfaces span less height than this is a flat plate
FLAT_PLATE_M = 1.0
#: unresolved rows are listed this far past a site's radius
MISSING_PAD_M = 50.0
#: open edges shorter than this are listed in the JSON only
PRINT_RUN_M = 3.0
#: the width of the outline band the rim is read on
RIM_BAND_M = 1.0
#: a long component's bottom is also read in stretches this long
STRETCH_M = 50.0


# ── inputs ───────────────────────────────────────────────────────────────

@dc.dataclass(frozen=True)
class Site:
    name: str
    lat: float
    lon: float
    radius_m: float


def parse_site(text: str, radius_m: float) -> Site:
    """``NAME=LAT,LON[,R]`` (``NAME=`` optional)."""
    name, _, rest = text.rpartition("=")
    parts = [float(p) for p in rest.split(",")]
    if len(parts) not in (2, 3):
        raise SystemExit(f"--site {text!r}: want NAME=LAT,LON[,R]")
    return Site(name or rest, parts[0], parts[1], parts[2] if len(parts) == 3 else radius_m)


def tile_of(lat: float, lon: float) -> str:
    return f"{int(math.floor(lat)):+03d}{int(math.floor(lon)):+04d}"


def tile_dsf(custom_scenery: str, tile: str) -> str | None:
    """The base-mesh DSF X-Plane draws for ``tile`` (``O4_Mesh_Order``:
    the first non-overlay DSF in the load order)."""
    import O4_Mesh_Order
    return O4_Mesh_Order.drawn_mesh_dsf(custom_scenery, int(tile[:3]), int(tile[3:]))


def dsftool() -> str:
    from auto_patch.dsf_reader import _dsftool_path
    tool = _dsftool_path()
    if not tool:
        raise SystemExit("drawn_check: the bundled DSFTool is missing")
    return tool


def pack_rows(pack_root: str, tiles: set[str], work: str, tool: str) -> list[tuple]:
    """``(row, DsfPlacement, pack_root, tile)`` of every object row of the
    pack's WRITTEN DSFs over ``tiles`` (dumped into ``work``)."""
    from auto_patch_v2.airport.dsf import read_dump
    from auto_patch_v2.airport.dsf_write import dump
    out = []
    for tile in sorted(tiles):
        for dsf in sorted(glob.glob(os.path.join(pack_root, "Earth nav data", "*", f"{tile}.dsf"))):
            text = os.path.join(work, hashlib.sha1(dsf.encode()).hexdigest()[:12] + ".txt")
            dump(dsf, text, tool)
            for i, p in enumerate(read_dump(text, accept_polygon=lambda _p: False).placements):
                out.append((i, p, pack_root, tile))
    return out


# ── the drawn mesh ───────────────────────────────────────────────────────

class DrawnMesh:
    """The tile DSFs' physical triangles over a lon/lat box ``(west,
    south, east, north)``, one sampler per tile."""

    def __init__(self, box, custom_scenery: str, tool: str,
                 override: str | None = None, cache: str | None = None):
        from auto_patch.mesh_sampler import MeshElevationSampler
        self.samplers: dict = {}
        self.sources: dict[str, str] = {}
        w, s, e, n = box
        for tile in sorted({tile_of(la, lo) for la in (s, n) for lo in (w, e)}):
            path = override or tile_dsf(custom_scenery, tile)
            if not path or not os.path.isfile(path):
                self.sources[tile] = "NO tile DSF installed: points there read missing"
                continue
            corners = tile_triangles(path, box, tool, cache)
            self.sources[tile] = f"{path} ({len(corners)} physical triangles in the box)"
            if len(corners):
                self.samplers[tile] = MeshElevationSampler.from_triangles(corners, box)

    def z(self, lat, lon) -> np.ndarray:
        lat = np.asarray(lat, float).reshape(-1)
        lon = np.asarray(lon, float).reshape(-1)
        out = np.full(lat.shape, np.nan)
        if not lat.size:
            return out
        keys = np.array([tile_of(a, o) for a, o in zip(lat, lon)])
        for tile, smp in self.samplers.items():
            m = keys == tile
            if m.any():
                ans = smp.sample_many(lat[m], lon[m])
                out[np.flatnonzero(m)] = [a.elevation_metres if a is not None else np.nan
                                          for a in ans]
        return out


def tile_triangles(path: str, box, tool: str, cache: str | None) -> np.ndarray:
    """The tile DSF's physical triangles in ``box``, through ``cache``
    (keyed by the DSF's path, size, mtime and the box) when given."""
    from auto_patch_v2.airport.dsf_mesh import physical_triangles, stream_text
    st = os.stat(path)
    key = hashlib.sha1(repr((os.path.abspath(path), st.st_size, st.st_mtime_ns,
                             tuple(round(b, 6) for b in box))).encode()).hexdigest()[:16]
    hit = os.path.join(cache, f"drawn_{key}.npy") if cache else None
    if hit and os.path.isfile(hit):
        return np.load(hit)
    with stream_text(path, tool) as fh:
        corners = physical_triangles(fh, box)
    if hit:
        os.makedirs(cache, exist_ok=True)
        np.save(hit, corners)
    return corners


# ── placed geometry ──────────────────────────────────────────────────────

class Frame:
    """A local metric frame (east, north) about a site."""

    def __init__(self, lat: float, lon: float):
        self.lat0, self.lon0 = lat, lon
        self.kx = K_LAT * math.cos(math.radians(lat))

    def enter(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * K_LAT

    def leave(self, e, n):
        return self.lat0 + np.asarray(n) / K_LAT, self.lon0 + np.asarray(e) / self.kx


class Resources:
    """Parsed OBJ8 per resolved file (``airport/obj8``): ``(path, geometry,
    solid components, horizontal reach)`` or ``None``."""

    def __init__(self, xplane_root: str, mod_cache_root: str):
        from auto_patch_v2.airport import obj8
        self._obj8 = obj8
        self.index = obj8.read_library_index(obj8.library_index_path(mod_cache_root, xplane_root))
        self._memo: dict = {}

    def unresolved(self, def_path: str, pack_root: str) -> bool:
        """A ``.obj`` row whose file X-Plane cannot find (it draws nothing)."""
        return (def_path.lower().endswith(".obj")
                and self._obj8.resolve_resource(def_path, pack_root, self.index) is None)

    def get(self, def_path: str, pack_root: str):
        phys = self._obj8.resolve_resource(def_path, pack_root, self.index)
        if not phys or not phys.lower().endswith(".obj"):
            return None
        if phys not in self._memo:
            try:
                g = self._obj8.parse_obj8(phys)
            except (OSError, ValueError):
                g = None
            if g is None or not g.solid.shape[0]:
                self._memo[phys] = None
            else:
                used = np.unique(g.solid.reshape(-1))
                reach = float(np.hypot(g.vertices[used, 0], g.vertices[used, 2]).max())
                self._memo[phys] = (phys, g, self._obj8.solid_components(g), reach)
        return self._memo[phys]


def placed_vertices(g, e0: float, n0: float, heading: float, base: float) -> np.ndarray:
    """OBJ8 vertices in the site frame ``(east, north, z)``: x east, z
    south, turned by the heading (the ``airport/obj8`` frame law)."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    x, y, z = g.vertices[:, 0], g.vertices[:, 1], g.vertices[:, 2]
    return np.column_stack([e0 + x * c - z * s, n0 - (x * s + z * c), base + y])


def row_base(p, mesh_at_anchor: float) -> float:
    """Where the row puts y = 0: the drawn mesh under the anchor
    (``OBJECT``), plus the offset (``OBJECT_AGL``), or the row's own
    elevation (``OBJECT_MSL``)."""
    if p.kind == "OBJECT_MSL":
        return float(p.elevation)
    if p.kind == "OBJECT_AGL":
        return mesh_at_anchor + float(p.elevation or 0.0)
    return mesh_at_anchor


def plan_triangles(V: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """``(m, 3, 3)`` corners of the triangles that cover plan (a vertical
    face covers none)."""
    p = V[tris]
    a, b = p[:, 1, :2] - p[:, 0, :2], p[:, 2, :2] - p[:, 0, :2]
    return p[0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) > 1e-3]


# ── one component, rasterised in plan ────────────────────────────────────

@dc.dataclass
class Raster:
    """The component's plan on a grid: per cell its top and lowest surface
    z (``nan`` where uncovered)."""

    e0: float
    n0: float
    step: float
    top: np.ndarray
    low: np.ndarray

    def centres(self, ij: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.e0 + (ij[:, 1] + 0.5) * self.step, self.n0 + (ij[:, 0] + 0.5) * self.step


def in_square(p: np.ndarray, clip_m: float) -> np.ndarray:
    """Which triangles ``(m, 3, 3)`` reach the site's square (the clip
    radius, out past the edge reading)."""
    reach = clip_m + OUTSIDE_M + 3.0
    lo, hi = p[:, :, :2].min(1), p[:, :, :2].max(1)
    return (lo.max(1) <= reach) & (hi.min(1) >= -reach)


def rasterise(p: np.ndarray, max_cells: int = 160000) -> Raster | None:
    """Top and lowest surface of plan triangles ``p`` per grid cell."""
    if not p.shape[0]:
        return None
    lo, hi = p[:, :, :2].reshape(-1, 2).min(0), p[:, :, :2].reshape(-1, 2).max(0)
    span = hi - lo
    step = max(0.5, math.sqrt(max(span[0] * span[1], 1.0) / max_cells))
    ncol, nrow = int(span[0] // step) + 1, int(span[1] // step) + 1
    top = np.full(nrow * ncol, -np.inf)
    low = np.full(nrow * ncol, np.inf)
    for t in p:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
        c0, c1 = int((min(x1, x2, x3) - lo[0]) // step), int((max(x1, x2, x3) - lo[0]) // step)
        r0, r1 = int((min(y1, y2, y3) - lo[1]) // step), int((max(y1, y2, y3) - lo[1]) // step)
        cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
        cc, rr = cc.ravel(), rr.ravel()
        cx, cy = lo[0] + (cc + 0.5) * step, lo[1] + (rr + 0.5) * step
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        w1 = ((y2 - y3) * (cx - x3) + (x3 - x2) * (cy - y3)) / d
        w2 = ((y3 - y1) * (cx - x3) + (x1 - x3) * (cy - y3)) / d
        w3 = 1.0 - w1 - w2
        m = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
        if m.any():
            zz = w1[m] * z1 + w2[m] * z2 + w3[m] * z3
            k = rr[m] * ncol + cc[m]
            np.maximum.at(top, k, zz)
            np.minimum.at(low, k, zz)
    top[~np.isfinite(top)] = np.nan
    low[~np.isfinite(low)] = np.nan
    return Raster(float(lo[0]), float(lo[1]), step, top.reshape(nrow, ncol), low.reshape(nrow, ncol))


def boundary_cells(r: Raster) -> tuple[np.ndarray, np.ndarray]:
    """Covered cells with an uncovered 4-neighbour, and per cell the unit
    outward direction ``(east, north)``: away from the covered cells within
    :data:`NORMAL_M` (a staircase outline of a slanted edge still faces one
    way)."""
    from scipy.ndimage import correlate
    cov = ~np.isnan(r.top)
    pad = np.pad(cov, 1, constant_values=False)
    edge = cov & (~pad[1:-1, 2:] | ~pad[1:-1, :-2] | ~pad[2:, 1:-1] | ~pad[:-2, 1:-1])
    k = max(2, int(round(NORMAL_M / r.step)))
    off = np.arange(-k, k + 1, dtype=float)
    disk = (off[None, :] ** 2 + off[:, None] ** 2) <= k * k
    f = cov.astype(float)
    de = -correlate(f, np.where(disk, off[None, :], 0.0), mode="constant")
    dn = -correlate(f, np.where(disk, off[:, None], 0.0), mode="constant")
    ij = np.argwhere(edge)
    d = np.column_stack([de[edge], dn[edge]])
    norm = np.hypot(d[:, 0], d[:, 1])
    keep = norm > 1e-9
    return ij[keep], d[keep] / norm[keep, None]


def sides_of(d: np.ndarray, axis: np.ndarray) -> np.ndarray:
    """Per outline cell, which of the plan's four sides it faces (0..3):
    the nearest of ``+axis``, ``-axis`` and their normals."""
    dirs = np.array([axis, -axis, [-axis[1], axis[0]], [axis[1], -axis[0]]])
    return np.argmax(d @ dirs.T, axis=1)


def runs_of(ij: np.ndarray, side: np.ndarray) -> list[np.ndarray]:
    """8-connected groups of outline cells facing the same side (indices
    into ``ij``): a rectangle's outline is four runs, not one ring."""
    if not len(ij):
        return []
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    key = {(int(a), int(b)): k for k, (a, b) in enumerate(ij)}
    rows, cols = [], []
    for k, (a, b) in enumerate(ij):
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                j = key.get((int(a) + da, int(b) + db))
                if j is not None and j != k and side[j] == side[k]:
                    rows.append(k)
                    cols.append(j)
    n = len(ij)
    _c, lab = connected_components(coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)),
                                   directed=False)
    return [np.flatnonzero(lab == L) for L in range(int(lab.max()) + 1)]


def stats(d: np.ndarray) -> dict:
    """Spread of one signed difference, with the share over the ground bar."""
    d = d[np.isfinite(d)]
    if not d.size:
        return {"n": 0}
    q = np.percentile(d, [5, 50, 95])
    return {"n": int(d.size), "min": rnd(d.min()), "p05": rnd(q[0]), "p50": rnd(q[1]),
            "p95": rnd(q[2]), "max": rnd(d.max()),
            "floating_pct": round(100.0 * float((d > GROUND_BAR_M).mean()), 1),
            "buried_pct": round(100.0 * float((d < -GROUND_BAR_M).mean()), 1)}


def rnd(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 2)


def measure(V: np.ndarray, comp, frame: Frame, mesh: DrawnMesh, others,
            clip_m: float | None = None) -> dict | None:
    """Every reading of one placed component (the module docstring); with
    ``clip_m`` the bottom and edge readings keep only the plan within that
    distance of the frame's origin (the site) -- the shape reads it whole."""
    tv = np.unique(comp.tris.reshape(-1))
    plan = plan_triangles(V, comp.tris)
    whole = rasterise(plan, 40000)
    if whole is None:
        return None
    plan_m2 = float((~np.isnan(whole.top)).sum()) * whole.step ** 2
    if plan_m2 < MIN_PLAN_M2:
        return None
    tris = comp.tris
    if clip_m is not None:          # the site's square, out past the edge reading
        plan, tris = plan[in_square(plan, clip_m)], tris[in_square(V[tris], clip_m)]
    r = rasterise(plan)
    if r is None:
        return None
    cov = ~np.isnan(r.top)
    ce, cn = r.centres(np.argwhere(cov))
    near = np.ones(len(ce), dtype=bool) if clip_m is None else np.hypot(ce, cn) <= clip_m
    if not near.any():
        return None
    mz = mesh.z(*frame.leave(ce[near], cn[near]))
    top, low = r.top[cov][near], r.low[cov][near]
    stacked = (top - low) > STACKED_M
    rec = {"plan_m2": round(plan_m2, 1), "cell_m": round(r.step, 2),
           "plan_read_m2": round(float(near.sum()) * r.step ** 2, 1),
           "centre": [round(float(x), 6) for x in frame.leave(ce[near].mean(), cn[near].mean())],
           "bottom_z": rnd(V[tv, 2].min()), "top_z": rnd(V[tv, 2].max()),
           "bottom_minus_mesh": stats(low - mz),
           "open_floor_minus_mesh": stats((low - mz)[~stacked]),
           "covered_pct": round(100.0 * float(stacked.mean()), 1)}
    bij, bdir = boundary_cells(r)
    be, bn = r.centres(bij)
    if clip_m is not None:
        keep = np.hypot(be, bn) <= clip_m
        bij, bdir, be, bn = bij[keep], bdir[keep], be[keep], bn[keep]
    btop, blow = r.top[bij[:, 0], bij[:, 1]], r.low[bij[:, 0], bij[:, 1]]
    axis = principal_axis(*whole.centres(np.argwhere(~np.isnan(whole.top))))
    foot, crest = outline_reach(edge_points(V, tris, max(0.5, r.step / 2)), be, bn, r.step)
    walled = crest > btop + WALL_RISE_M
    in_mesh = mesh.z(*frame.leave(be, bn))
    off = OUTSIDE_M + r.step / 2
    oe, on = be + bdir[:, 0] * off, bn + bdir[:, 1] * off
    out_mesh = mesh.z(*frame.leave(oe, on))
    outside, from_obj = drawn_outside(out_mesh, others(oe, on))
    rim_ground = float(np.nanmedian(out_mesh)) if np.isfinite(out_mesh).any() else float("nan")
    runs = []
    open_idx = np.flatnonzero(~walled)
    for g in runs_of(bij[open_idx], sides_of(bdir[open_idx], axis)):
        sel = open_idx[g]
        if len(sel) * r.step < 2.0:            # a corner cell, not a run
            continue
        runs.append(edge_run(sel, be, bn, bdir, btop, blow, outside, from_obj, r.step,
                             frame, mesh))
    rec["open_runs"] = sorted(runs, key=lambda q: -q["length_m"])
    rec["stretches"] = stretches(ce[near][~stacked], cn[near][~stacked], (low - mz)[~stacked], frame)
    rec["walled_outline_pct"] = round(100.0 * float(walled.mean()), 1) if len(walled) else 0.0
    rec["outline_sides"] = outline_sides(foot - in_mesh, sides_of(bdir, axis), bdir, be, bn, frame)
    rec["mesh_under_minus_rim"] = stats(mz - rim_ground)
    rec["shape"] = shape_witness(whole, edge_points(V, comp.tris, max(0.5, whole.step / 2)),
                                 rim_ground, float(np.ptp(V[tv, 2])))
    return rec


def stretches(e: np.ndarray, n: np.ndarray, d: np.ndarray, frame: Frame) -> list[dict]:
    """The open-floor bottom - mesh of a long component, per
    :data:`STRETCH_M` along its principal axis: where it floats or is
    buried, stretch by stretch (a whole-object median hides a corridor
    that floats at one end and is buried at the other)."""
    ok = np.isfinite(d)
    e, n, d = e[ok], n[ok], d[ok]
    if len(d) < 10:
        return []
    t = np.column_stack([e, n]) @ principal_axis(e, n)
    if t.max() - t.min() < 2 * STRETCH_M:
        return []
    out = []
    for b in np.unique(np.floor((t - t.min()) / STRETCH_M)):
        m = np.floor((t - t.min()) / STRETCH_M) == b
        if m.sum() < 5:
            continue
        out.append({"at": [round(float(x), 6) for x in frame.leave(e[m].mean(), n[m].mean())],
                    "station_m": round(float(b * STRETCH_M), 0), "n": int(m.sum()),
                    "p50": rnd(np.median(d[m])), "p05": rnd(np.percentile(d[m], 5)),
                    "p95": rnd(np.percentile(d[m], 95))})
    return out


def edge_points(V: np.ndarray, tris: np.ndarray, spacing: float) -> np.ndarray:
    """Every triangle edge of a component densified to ``spacing`` in 3D:
    ``(n, 3)`` points.  A wall's face has corners only at its ends; its
    densified edges say where the wall stands and how low and high it
    reaches all along it."""
    a = V[tris[:, [0, 1, 2]]].reshape(-1, 3)
    b = V[tris[:, [1, 2, 0]]].reshape(-1, 3)
    n = np.maximum(1, np.ceil(np.linalg.norm(b - a, axis=1) / spacing).astype(int))
    rep_ = np.repeat(np.arange(len(a)), n + 1)
    t = np.concatenate([np.linspace(0.0, 1.0, k + 1) for k in n])
    return a[rep_] + (b - a)[rep_] * t[:, None]


def outline_reach(P: np.ndarray, be, bn, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Per outline cell, the lowest and highest geometry within
    :data:`WALL_REACH_M` in plan (``nan`` where none): a wall's foot and
    top."""
    from scipy.spatial import cKDTree
    tree = cKDTree(P[:, :2])
    lo, hi = np.full(len(be), np.nan), np.full(len(be), np.nan)
    for k, nb in enumerate(tree.query_ball_point(np.column_stack([be, bn]), WALL_REACH_M + step / 2)):
        if nb:
            lo[k], hi[k] = P[nb, 2].min(), P[nb, 2].max()
    return lo, hi


def outline_sides(d: np.ndarray, side: np.ndarray, bdir, be, bn, frame: Frame) -> list[dict]:
    """The outline's lowest geometry (a wall's foot) - the mesh there, per
    side of the plan: ``+`` a gap under the wall, ``-`` the wall runs into
    the ground.  A split-level building reads its low side here."""
    out = []
    for k in range(4):
        m = (side == k) & np.isfinite(d)
        if m.sum() < 3:
            continue
        dirn = bdir[m].mean(0)
        out.append({"faces_deg": round(float(np.degrees(np.arctan2(dirn[0], dirn[1]))) % 360.0),
                    "at": [round(float(x), 6) for x in frame.leave(be[m].mean(), bn[m].mean())],
                    "foot_minus_mesh": stats(d[m])})
    return out


def drawn_outside(out_mesh, out_obj):
    """The surface drawn outside each edge cell: the higher of the mesh and
    another object's hard surface there (the lower one is hidden)."""
    from_obj = np.isfinite(out_obj) & ~(out_obj <= out_mesh)
    return np.where(from_obj, out_obj, out_mesh), from_obj


def edge_run(sel, be, bn, bdir, btop, blow, outside, from_obj, step, frame, mesh) -> dict:
    """One open run of the outline: where it is, its levels, the steps to
    the drawn surface outside, and -- for a mouth -- the ramp in front."""
    length = run_length(be[sel], bn[sel], step)
    roofed = float(np.nanmedian(btop[sel] - blow[sel])) > STACKED_M
    run = {"cells": int(len(sel)), "length_m": round(length, 1),
           "at": [round(float(x), 6) for x in frame.leave(be[sel].mean(), bn[sel].mean())],
           "top_z": rnd(np.nanmedian(btop[sel])), "floor_z": rnd(np.nanmedian(blow[sel])),
           "outside_z": rnd(np.nanmedian(outside[sel])),
           "outside_is_object_pct": round(100.0 * float(from_obj[sel].mean())),
           "top_step": stats(btop[sel] - outside[sel]),
           "floor_step": stats(blow[sel] - outside[sel]), "roofed": roofed}
    run["joins"], run["step_m"] = joins(run)
    if roofed or run["joins"] == "floor":
        run["mouth"] = mouth(be[sel], bn[sel], bdir[sel], float(np.nanmedian(blow[sel])),
                             length, frame, mesh)
    return run


def principal_axis(e: np.ndarray, n: np.ndarray) -> np.ndarray:
    """The unit direction of a plan's longest extent."""
    c = np.column_stack([e, n])
    c = c - c.mean(0)
    return np.linalg.svd(c, full_matrices=False)[2][0] if len(c) > 1 else np.array([1.0, 0.0])


def run_length(e: np.ndarray, n: np.ndarray, step: float) -> float:
    """Extent of a run of cells along its principal direction."""
    if len(e) < 2:
        return step
    t = np.column_stack([e, n]) @ principal_axis(e, n)
    return float(t.max() - t.min() + step)


def joins(run: dict) -> tuple[str, float | None]:
    """The edge surface (top or floor) whose median step to the drawn
    surface outside is smaller, and that step."""
    t, f = run["top_step"].get("p50"), run["floor_step"].get("p50")
    if t is None and f is None:
        return "unread", None
    if f is None or (t is not None and abs(t) <= abs(f)):
        return "top", t
    return "floor", f


def mouth(e, n, d, floor_z: float, opening: float, frame: Frame, mesh: DrawnMesh) -> dict:
    """The ground in front of a mouth: on the line 3 m out, parallel to the
    opening, the contiguous width about its centre where the drawn mesh
    stands no more than the ground bar over the floor."""
    dirn = d.mean(0)
    dirn = dirn / (float(np.hypot(*dirn)) or 1.0)
    along = np.array([-dirn[1], dirn[0]])
    c = np.array([e.mean(), n.mean()]) + dirn * 3.0
    s = np.arange(-opening - 20.0, opening + 20.25, 0.5)
    pts = c[None, :] + s[:, None] * along[None, :]
    z = mesh.z(*frame.leave(pts[:, 0], pts[:, 1]))
    ok = np.isfinite(z) & (z <= floor_z + GROUND_BAR_M)
    a = b = len(s) // 2
    width = 0.0
    if ok[a]:
        while a > 0 and ok[a - 1]:
            a -= 1
        while b < len(s) - 1 and ok[b + 1]:
            b += 1
        width = float(s[b] - s[a] + 0.5)
    ramp3 = float(mesh.z(*frame.leave(c[0], c[1]))[0])
    return {"opening_m": round(opening, 1), "ramp_width_m": round(width, 1),
            "ramp_z_3m": rnd(ramp3), "mouth_floor_z": round(floor_z, 2),
            "floor_minus_ramp_3m": rnd(floor_z - ramp3)}


def shape_witness(r: Raster, P: np.ndarray, rim_ground: float, relief: float) -> dict:
    """CONCAVE CUT SHELL / COVERED / CONVEX BODY from the OBJ alone (#1914).

    The witness is the TOP SURFACE against the component's OWN RIM (the
    90th percentile of the highest geometry -- surface or wall crest, from
    the densified edges ``P`` -- on its outline band, :data:`RIM_BAND_M`
    wide): a cut shell is an OPEN-TOP HOLLOW -- over at least half its
    inner plan the top surface stands :data:`HOLLOW_M` or more under the
    rim with nothing over it (one surface per plan point); COVERED is a
    deck or roof over a floor over half its plan; anything else is a
    convex body (its top is its highest part).  ``rim_minus_ground`` (the
    drawn mesh just outside) says whether that rim stands at grade -- a
    cut shell's wall tops meet the ground -- and is reported, not used."""
    cov = ~np.isnan(r.top)
    k = max(1, int(round(RIM_BAND_M / r.step)))
    pad = np.pad(cov, k, constant_values=False)
    inner = cov.copy()
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            inner &= pad[k + di:k + di + cov.shape[0], k + dj:k + dj + cov.shape[1]]
    band = cov & ~inner
    if relief < FLAT_PLATE_M:
        return {"class": "flat plate (deck / pad)", "hollow_pct": 0.0, "covered_pct": 0.0,
                "own_rim_z": rnd(np.nanmax(r.top)), "inner_top_p50": rnd(np.nanmedian(r.top)),
                "rim_minus_ground": rnd(np.nanmax(r.top) - rim_ground)}
    if not band.any() or not inner.any():
        return {"class": "thin (no inner plan)", "hollow_pct": None, "covered_pct": None,
                "own_rim_z": None, "inner_top_p50": None, "rim_minus_ground": None}
    bij = np.argwhere(band)
    _foot, crest = outline_reach(P, *r.centres(bij), r.step)
    rim = float(np.percentile(np.fmax(r.top[band], crest), 90))
    top_in = r.top[inner]
    single = (top_in - r.low[inner]) <= STACKED_M
    hollow_pct = 100.0 * float(((top_in < rim - HOLLOW_M) & single).mean())
    covered_pct = 100.0 * float((~single).mean())
    cls = ("concave cut shell" if hollow_pct >= 50.0 else
           "covered (deck/roof over floor)" if covered_pct >= 50.0 else "convex body")
    return {"class": cls, "hollow_pct": round(hollow_pct, 1), "covered_pct": round(covered_pct, 1),
            "own_rim_z": rnd(rim), "inner_top_p50": rnd(np.median(top_in)),
            "rim_minus_ground": rnd(rim - rim_ground)}


class OtherSurfaces:
    """The HARD plan surfaces (``ATTR_hard`` / ``ATTR_hard_deck``: what a
    wheel stands on) of every component placed at a site, so the surface
    drawn outside an edge can be another object's rather than the mesh."""

    def __init__(self, placed):
        self.parts = []
        for pl in placed:
            g = pl["g"]
            for ci, comp in enumerate(pl["comps"]):
                if comp.animated or comp.idx is None:
                    continue
                hard = g.hardness[comp.idx] > 0
                if hard.any():
                    t = plan_triangles(pl["V"], comp.tris[hard])
                    if t.shape[0]:
                        self.parts.append(((pl["key"], ci), t))

    def excluding(self, key, ci):
        parts = [t for k, t in self.parts if k != (key, ci)]
        tris = np.concatenate(parts) if parts else np.zeros((0, 3, 3))
        mn = tris[:, :, :2].min(1) if tris.shape[0] else None
        mx = tris[:, :, :2].max(1) if tris.shape[0] else None

        def at(e, n):
            """Per point, the highest other-object hard surface; ``nan``
            where none covers the point."""
            out = np.full(len(e), np.nan)
            if mn is None:
                return out
            for k in range(len(e)):
                m = (mn[:, 0] <= e[k]) & (mx[:, 0] >= e[k]) & (mn[:, 1] <= n[k]) & (mx[:, 1] >= n[k])
                if not m.any():
                    continue
                t = tris[m]
                x1, y1, z1 = t[:, 0].T
                x2, y2, z2 = t[:, 1].T
                x3, y3, z3 = t[:, 2].T
                d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
                w1 = ((y2 - y3) * (e[k] - x3) + (x3 - x2) * (n[k] - y3)) / d
                w2 = ((y3 - y1) * (e[k] - x3) + (x1 - x3) * (n[k] - y3)) / d
                w3 = 1 - w1 - w2
                ins = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
                if ins.any():
                    out[k] = float((w1 * z1 + w2 * z2 + w3 * z3)[ins].max())
            return out
        return at


# ── the run ──────────────────────────────────────────────────────────────

def unresolved_near(rows, s: Site, frame: Frame, res: Resources) -> list[str]:
    """``.obj`` rows anchored within the site radius (+ :data:`MISSING_PAD_M`)
    whose file does not resolve -- a torn pack draws nothing there."""
    out = []
    for row, p, root, tile in rows:
        if math.hypot(*frame.enter(p.lat, p.lon)) <= s.radius_m + MISSING_PAD_M \
                and res.unresolved(p.def_path, root):
            out.append(f"{tile} obj{row} {p.def_path}")
    return out


def select(rows, sites, objects, frames, res: Resources, search_m: float) -> list[dict]:
    """Placements whose solids reach a site (its radius), or whose
    resource path contains one of ``objects``."""
    picked = []
    for row, p, root, tile in rows:
        hit = [s for s in sites if abs(p.lat - s.lat) * K_LAT < search_m
               and abs(p.lon - s.lon) * frames[s].kx < search_m]
        named = any(o.lower() in p.def_path.lower() for o in objects)
        if not hit and not named:
            continue
        got = res.get(p.def_path, root)
        if got is None:
            continue
        near = [s for s in hit if math.hypot(*frames[s].enter(p.lat, p.lon)) <= got[3] + s.radius_m]
        if near or named:
            picked.append({"key": (root, tile, row), "row": row, "p": p, "root": root,
                           "tile": tile, "phys": got[0], "g": got[1], "comps": got[2],
                           "reach": got[3], "sites": near, "named": named})
    return picked


def mesh_box(sites, picked) -> tuple[float, float, float, float]:
    """Every site and every picked anchor, out by the largest reach."""
    lats = [s.lat for s in sites] + [q["p"].lat for q in picked]
    lons = [s.lon for s in sites] + [q["p"].lon for q in picked]
    pad = 0.0015 + max([q["reach"] for q in picked] + [0.0]) / K_LAT
    return min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad


def measure_site(s: Site, items: list[dict], mesh: DrawnMesh) -> dict:
    """Every component of ``items`` reaching ``s`` (all, for an object
    group), measured in the site's frame."""
    fr = Frame(s.lat, s.lon)
    placed = []
    for q in items:
        p = q["p"]
        g0 = float(mesh.z([p.lat], [p.lon])[0])
        base = row_base(p, g0)
        e0, n0 = fr.enter(p.lat, p.lon)
        placed.append(dict(q, V=placed_vertices(q["g"], float(e0), float(n0), p.heading_deg, base),
                           base=base, g0=g0))
    others = OtherSurfaces(placed)
    comps_out = []
    for pl in placed:
        V, p = pl["V"], pl["p"]
        for ci, comp in enumerate(pl["comps"]):
            if comp.animated:
                continue
            tv = np.unique(comp.tris.reshape(-1))
            lo, hi = V[tv, :2].min(0), V[tv, :2].max(0)
            if not pl["named"] and (lo.max() > s.radius_m or hi.min() < -s.radius_m):
                continue
            rec = measure(V, comp, fr, mesh, others.excluding(pl["key"], ci),
                          None if pl["named"] else s.radius_m)
            if rec is None:
                continue
            rec.update({"row": pl["row"], "tile": pl["tile"],
                        "pack": os.path.basename(pl["root"].rstrip("/")), "def": p.def_path,
                        "kind": p.kind, "component": ci, "anchor": [round(p.lat, 7), round(p.lon, 7)],
                        "anchor_dist_m": round(float(math.hypot(*fr.enter(p.lat, p.lon))), 1),
                        "heading": p.heading_deg, "base_z": rnd(pl["base"]),
                        "mesh_at_anchor": rnd(pl["g0"]), "deck": bool(comp.deck),
                        "dist_m": round(float(np.hypot(*np.clip(0.0, lo, hi))), 1)})
            comps_out.append(rec)
    return {"name": s.name, "lat": s.lat, "lon": s.lon, "radius_m": s.radius_m,
            "mesh_z": rnd(mesh.z([s.lat], [s.lon])[0]), "components": comps_out}


def run(args) -> dict:
    sites = [parse_site(s, args.radius) for s in args.site]
    if not sites and not args.object:
        raise SystemExit("drawn_check: give at least one --site or --object")
    tool = dsftool()
    work = tempfile.mkdtemp(prefix="drawn_check_")
    try:
        return _run(args, sites, tool, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run(args, sites, tool: str, work: str) -> dict:
    """:func:`run` with its temp folder for the pack dumps."""
    res = Resources(os.path.dirname(args.custom_scenery.rstrip("/")), args.mod_cache)
    tiles = set(args.tiles)
    for s in sites:
        for dla in (-0.03, 0.0, 0.03):
            for dlo in (-0.04, 0.0, 0.04):
                tiles.add(tile_of(s.lat + dla, s.lon + dlo))
    rows = []
    for pack in args.pack:
        rows += pack_rows(pack, tiles, work, tool)
    frames = {s: Frame(s.lat, s.lon) for s in sites}
    picked = select(rows, sites, args.object, frames, res, args.search_m)
    if not picked:
        raise SystemExit("drawn_check: no placed solid reaches any site")
    mesh = DrawnMesh(mesh_box(sites, picked), args.custom_scenery, tool, args.tile_dsf, args.cache)
    report = {"mesh": mesh.sources, "packs": args.pack, "sites": []}
    for s in sites:
        rec = measure_site(s, [q for q in picked if s in q["sites"]], mesh)
        rec["unresolved"] = unresolved_near(rows, s, frames[s], res)
        report["sites"].append(rec)
    named = [dict(q, named=True) for q in picked if q["named"]]
    if named:
        p0 = named[0]["p"]
        report["sites"].append(measure_site(Site("objects: " + ", ".join(args.object),
                                                 p0.lat, p0.lon, 0.0), named, mesh))
    return report


# ── the report ───────────────────────────────────────────────────────────

def verdict_lines(rec: dict) -> list[str]:
    """The owner's readings of one component, one line each."""
    out = []
    use_open = bool(rec["open_floor_minus_mesh"].get("n"))
    fp = rec["open_floor_minus_mesh"] if use_open else rec["bottom_minus_mesh"]
    if fp.get("n"):
        tag = ("FLOATING" if fp["p50"] > GROUND_BAR_M else
               "BURIED" if fp["p50"] < -GROUND_BAR_M else "on mesh")
        out.append(f"    bottom - mesh ({'open floor' if use_open else 'under cover'}, {fp['n']} pts): "
                   f"p05 {fp['p05']:+.2f} p50 {fp['p50']:+.2f} p95 {fp['p95']:+.2f}  "
                   f"floating {fp['floating_pct']}% buried {fp['buried_pct']}% -> {tag}")
    bad = [q for q in rec.get("stretches", []) if abs(q["p50"]) > GROUND_BAR_M]
    if bad:
        out.append(f"    stretches off the mesh ({len(bad)} of {len(rec['stretches'])} x {STRETCH_M:g} m): " +
                   "; ".join(f"{q['p50']:+.2f} @{q['at'][0]:.5f},{q['at'][1]:.5f}"
                             for q in sorted(bad, key=lambda q: -abs(q["p50"]))[:6]))
    for run in [q for q in rec["open_runs"] if q["length_m"] >= PRINT_RUN_M][:8]:
        st = run["step_m"]
        if st is None:
            continue
        tag = ("flush" if abs(st) <= PAVEMENT_BAR_M else "EDGE BELOW OUTSIDE (buried)" if st < 0 else "EDGE ABOVE OUTSIDE (step/drop)")
        line = (f"    open edge {run['length_m']:.1f} m @{run['at'][0]:.6f},{run['at'][1]:.6f}: "
                f"top {run['top_z']} floor {run['floor_z']} outside {run['outside_z']}"
                f"{' (object)' if run['outside_is_object_pct'] > 50 else ''}"
                f" -> {run['joins']} step {st:+.2f} {tag}")
        m = run.get("mouth")
        if m and m["floor_minus_ramp_3m"] is not None:
            line += (f" | mouth floor {m['mouth_floor_z']} - ramp(3 m) {m['ramp_z_3m']} = "
                     f"{m['floor_minus_ramp_3m']:+.2f}; opening {m['opening_m']} m, "
                     f"ramp width {m['ramp_width_m']} m")
        out.append(line)
    for sd in rec.get("outline_sides", []):
        f = sd["foot_minus_mesh"]
        out.append(f"    outline facing {sd['faces_deg']:3.0f} deg @{sd['at'][0]:.6f},{sd['at'][1]:.6f}: "
                   f"wall foot - mesh p05 {f['p05']:+.2f} p50 {f['p50']:+.2f} p95 {f['p95']:+.2f}")
    mu = rec.get("mesh_under_minus_rim", {})
    if mu.get("n"):
        out.append(f"    mesh under the plan - mesh just outside: p05 {mu['p05']:+.2f} p50 {mu['p50']:+.2f} "
                   f"p95 {mu['p95']:+.2f} (a cut under it reads negative)")
    sh = rec["shape"]
    out.append(f"    shape: {sh['class']} (hollow {sh['hollow_pct']}%, covered {sh['covered_pct']}%, "
               f"own rim {sh['own_rim_z']}, inner top p50 {sh['inner_top_p50']}, "
               f"rim - ground {sh['rim_minus_ground']})")
    return out


def print_report(rep: dict, top_n: int) -> None:
    for tile, src in rep["mesh"].items():
        print(f"[mesh] {tile}: {src}")
    for s in rep["sites"]:
        print(f"\nSITE {s['name']} @{s['lat']:.6f},{s['lon']:.6f} r {s['radius_m']:g} m"
              f" -- drawn mesh {s['mesh_z']}")
        for miss in s.get("unresolved", [])[:10]:
            print(f"  UNRESOLVED (drawn as nothing): {miss}")
        for rec in sorted(s["components"], key=lambda q: -q["plan_m2"])[:top_n]:
            print(f"  {rec['pack'][:34]} {rec['tile']} obj{rec['row']} {rec['def']} c{rec['component']}"
                  f" {rec['kind']} base {rec['base_z']} (mesh@anchor {rec['mesh_at_anchor']},"
                  f" anchor {rec['anchor_dist_m']:.0f} m off){' DECK' if rec['deck'] else ''}"
                  f" | {rec['dist_m']} m from site, plan {rec['plan_m2']} m2,"
                  f" z {rec['bottom_z']}..{rec['top_z']}")
            for line in verdict_lines(rec):
                print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", action="append", required=True,
                    help="an installed airport pack folder (repeat for every pack drawing there)")
    ap.add_argument("--site", action="append", default=[], help="NAME=LAT,LON[,RADIUS_M]")
    ap.add_argument("--object", action="append", default=[],
                    help="also every placement whose resource path contains this text")
    ap.add_argument("--tiles", nargs="*", default=[],
                    help="pack tiles to read when --object is given alone (e.g. +37+023)")
    ap.add_argument("--radius", type=float, default=25.0, help="default site radius, m")
    ap.add_argument("--search-m", type=float, default=3000.0,
                    help="anchors this far from a site are considered (shared-datum packs)")
    ap.add_argument("--custom-scenery", default=None,
                    help="X-Plane Custom Scenery (default: the cfg's custom_scenery_dir)")
    ap.add_argument("--mod-cache", default=None,
                    help="Airport_mod_cache holding the library index (default: the cfg's)")
    ap.add_argument("--tile-dsf", default=None, help="read the drawn mesh from this DSF instead")
    ap.add_argument("--cache", default=None, help="keep the box's tile triangles here (.npy)")
    ap.add_argument("--top", type=int, default=40, help="components printed per site")
    ap.add_argument("--json", default=None, help="write the full report here")
    args = ap.parse_args(argv)
    if args.custom_scenery is None or args.mod_cache is None:
        import O4_Config_Utils                                    # noqa: F401
        from auto_patch_v2.planar.__main__ import _cfg_value
        import O4_File_Names as FNAMES
        args.custom_scenery = args.custom_scenery or _cfg_value("custom_scenery_dir") \
            or os.path.expanduser("~/X-Plane 12/Custom Scenery")
        args.mod_cache = args.mod_cache or FNAMES.airport_mod_cache_root()
    rep = run(args)
    print_report(rep, args.top)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
