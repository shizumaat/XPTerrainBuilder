#!/usr/bin/env python3
"""THE TERRAIN COMPOSITES AS X-PLANE DRAWS THEM (#2077, spec
``docs/specs/2077-terrain-composites-spec.md`` 9.4 / 9.5).

A terrain composite (``auto_patch_v2.airport.terrain_fill``: a terrain
model's rim fill, a relief skin's zero plane) is judged on what X-Plane
draws: the build's rebake plan names the composites (its seat records with
``cut`` carrying ``fill`` / ``plane``), the pack copy's WRITTEN rows place
their sets, and the build's tile DSF is the drawn mesh
(``drawn_site.DrawnMesh``).  Per build:

* RIM -- every fill record's outer-rim cell bottom against the drawn
  ground; JUDGED outside the exemption (within ``W`` of another
  composite's plan or zero footprint: that composite owns the ground).
* FEET -- a relief skin's set (the rows at the skin's origin): a
  ZERO-LEVEL CELL is a :data:`CELL_M` cell whose lowest wall vertex
  (``|n_y|`` < 0.5) over ALL non-skin members lies within
  :data:`ZERO_TOL_M` of the frame zero.  JUDGED: zero-level cells inside
  the zero footprint, farther than ``QUAY_M`` + :data:`QUAY_PAD_M` from
  mapped water, not on the set's own near-horizontal face
  (:data:`DECK_DY` of the foot, same or 4-adjacent cell), not under a
  terrain member's top.  A judged foot FAILS where the drawn ground stands
  more than :data:`UNDER_BAR_M` under the zero plane (``z0 - UNDER_M``).
  LISTED, never judged: feet on decks over water and on land, feet in the
  quay metre, zero-level feet outside the footprint, feet authored at or
  under :data:`TERRACE_M` on land (their burial), zero-level feet over
  water without a deck.
* LAND -- the zero footprint less mapped water grown by
  :data:`LAND_PAD_M`, sampled every :data:`LAND_STEP_M`: drawn minus the
  plane, over / under :data:`UNDER_BAR_M`.
* WATER -- the drawn surface at each ``--water`` point (the control's
  through ``--against``).
* SITES -- each ``--site``: the drawn ground and the feet within
  :data:`SITE_R_M` (foot minus ground).
* ROWS -- each composite resource's written kind and elevation, the
  set's zeros, and the pack's split files of its members.

Mapped water is the mesh's own derivation
(``O4_Vector_Map.cached_tile_water``).  ``--frames-out DIR`` writes the
review frame: the built ``.mesh`` clipped to ``--box`` (vertices,
triangles, attributes), the ``.alt`` window with its frame, the
``.alt``'s terrain-fill sidecar and the build's plans, so a review
measures instead of replaying.

Usage (from Ortho4XP/)::

    venv/bin/python tools/composite_bars.py ICAO --tag T [--out DIR]
        [--water NAME=LAT,LON ...] [--site NAME=LAT,LON ...]
        [--box W,S,E,N] [--frames-out DIR] [--json OUT] [--against BASE.json]

Read-only (temp dumps).  It derives no law.  Twin:
``tests/test_composite_bars.py``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import tempfile

import numpy as np

_TOOLS = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(os.path.dirname(_TOOLS), "src"), _TOOLS, os.path.join(_TOOLS, "harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import O4_Console_Encoding as _o4console  # noqa: E402, I001

_o4console.configure_console_streams()

__all__ = ["CELL_M", "ZERO_TOL_M", "DECK_DY", "UNDER_BAR_M", "QUAY_PAD_M", "TERRACE_M",
           "foot_cells", "deck_index", "on_deck", "classify_feet", "judge_feet", "run",
           "main"]

#: the foot grid (the spec's 5 m cells, object frame)
CELL_M = 5.0
#: a cell is zero-level when its lowest wall vertex lies this near the zero
ZERO_TOL_M = 0.5
#: a near-horizontal face of the set this far (lo, hi) from a foot carries it
DECK_DY = (-1.5, 0.3)
#: a judged foot fails when the drawn ground stands this far under the plane
UNDER_BAR_M = 0.5
#: judged feet stand farther than ``QUAY_M`` + this from mapped water
QUAY_PAD_M = 0.5
#: the land samples keep this far off mapped water
LAND_PAD_M = 1.5
#: the land sample step (m)
LAND_STEP_M = 3.0
#: a foot authored at or under this (m) is the author's terrace, listed
TERRACE_M = -3.0
#: feet within this of a ``--site`` are listed (m)
SITE_R_M = 12.0


# -- the set's feet (pure: the twin's surface) -----------------------------

def _normal_y(tris: np.ndarray) -> np.ndarray:
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    return np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)


def foot_cells(solids: list, cell: float = CELL_M) -> dict[str, np.ndarray]:
    """Per ``cell`` cell of the object frame (x, z), the LOWEST wall vertex
    (a vertex of a face with ``|n_y|`` < 0.5) over every member's static
    solid in ``solids`` (``(n, 3, 3)`` each, ``None`` skipped):
    ``{"i", "j", "x", "y", "z", "member"}``."""
    xs, ys, zs, ms = [], [], [], []
    for k, sol in enumerate(solids):
        if sol is None or not len(sol):
            continue
        t = np.asarray(sol, float)
        v = t[_normal_y(t) < 0.5].reshape(-1, 3)
        xs.append(v[:, 0])
        ys.append(v[:, 1])
        zs.append(v[:, 2])
        ms.append(np.full(len(v), k))
    if not xs:
        e = np.zeros(0)
        return {"i": e.astype(int), "j": e.astype(int), "x": e, "y": e, "z": e,
                "member": e.astype(int)}
    x, y, z, m = (np.concatenate(a) for a in (xs, ys, zs, ms))
    i, j = np.floor(x / cell).astype(np.int64), np.floor(z / cell).astype(np.int64)
    order = np.lexsort((y, j, i))
    si, sj = i[order], j[order]
    first = np.r_[True, (np.diff(si) != 0) | (np.diff(sj) != 0)]
    o = order[first]
    return {"i": si[first], "j": sj[first], "x": x[o], "y": y[o], "z": z[o], "member": m[o]}


def deck_index(solids: list, cell: float = CELL_M) -> dict[tuple[int, int], np.ndarray]:
    """The heights of the set's near-horizontal faces (``|n_y|`` > 0.9,
    area > 0.5 m2) per cell, sampled at each face's centroid and three
    inner points."""
    w = np.array([(1 / 3, 1 / 3, 1 / 3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6)])
    out: dict[tuple[int, int], list] = {}
    for sol in solids:
        if sol is None or not len(sol):
            continue
        t = np.asarray(sol, float)
        area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
        t = t[(_normal_y(t) > 0.9) & (area > 0.5)]
        if not len(t):
            continue
        p = np.einsum("wk,nkd->nwd", w, t).reshape(-1, 3)
        for a, b, y in zip(np.floor(p[:, 0] / cell).astype(int),
                           np.floor(p[:, 2] / cell).astype(int), p[:, 1], strict=True):
            out.setdefault((int(a), int(b)), []).append(float(y))
    return {k: np.asarray(v) for k, v in out.items()}


def on_deck(i: np.ndarray, j: np.ndarray, y: np.ndarray, decks: dict) -> np.ndarray:
    """Feet (cell ``i, j``, authored ``y``) standing on a deck of the set:
    a near-horizontal face :data:`DECK_DY` of the foot in its cell or a
    4-adjacent one."""
    out = np.zeros(len(y), bool)
    for k, (a, b, h) in enumerate(zip(i, j, y, strict=True)):
        for da, db in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            d = decks.get((int(a) + da, int(b) + db))
            if d is not None and np.any((d - h >= DECK_DY[0]) & (d - h <= DECK_DY[1])):
                out[k] = True
                break
    return out


def classify_feet(y: np.ndarray, deck: np.ndarray, in_footprint: np.ndarray,
                  water_d: np.ndarray, under_terrain: np.ndarray, quay_m: float) -> np.ndarray:
    """One label per foot cell (spec 9.4): ``judged``; listed
    ``deck_water``, ``deck_land``, ``quay`` (the quay metre), ``outside``
    (the footprint), ``water`` (no deck), ``under_terrain``, ``terrace``
    (authored at or under :data:`TERRACE_M`, on land), or ``other`` (not
    zero-level).  ``water_d`` the distance to mapped water (0 in it)."""
    y = np.asarray(y, float)
    deck, infp, under = (np.asarray(a, bool) for a in (deck, in_footprint, under_terrain))
    wd = np.asarray(water_d, float)
    zl = np.abs(y) <= ZERO_TOL_M
    wet = wd <= 0.0
    lab = np.full(len(y), "other", dtype=object)
    lab[(y <= TERRACE_M) & ~wet] = "terrace"
    lab[zl & ~infp] = "outside"
    lab[zl & infp & wet] = "water"
    lab[zl & infp & ~wet & (wd <= quay_m + QUAY_PAD_M)] = "quay"
    rest = zl & infp & (wd > quay_m + QUAY_PAD_M)
    lab[rest & under] = "under_terrain"
    lab[rest & ~under & deck] = "deck_land"
    lab[rest & ~under & ~deck] = "judged"
    lab[zl & deck & wet] = "deck_water"
    return lab


def judge_feet(labels: np.ndarray, ground: np.ndarray, plane_z: float) -> np.ndarray:
    """The judged feet that FAIL: drawn ``ground`` more than
    :data:`UNDER_BAR_M` under ``plane_z`` (a foot authored over the zero on
    a perfect plane passes)."""
    g = np.asarray(ground, float)
    return (np.asarray(labels) == "judged") & np.isfinite(g) & (plane_z - g > UNDER_BAR_M)


# -- the build's composites ---------------------------------------------------

def _pt(text: str) -> tuple[str, float, float]:
    name, ll = text.split("=", 1)
    lat, lon = (float(v) for v in ll.split(",")[:2])
    return name, lat, lon


def _rnd(x) -> float | None:
    x = float(x)
    return round(x, 3) if math.isfinite(x) else None


def _products(args) -> dict:
    import drawn_check as DC
    patch_dir, tile_dsfs = DC.resolve(args)
    tile = os.path.basename(patch_dir)
    with open(os.path.join(args.out, f"{args.tag}.result.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    with open(os.path.join(patch_dir, f"o4_v2_rebake_{args.icao}.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    # the WRITTEN pack (the placement plan's: the build's copy), not the
    # rebake plan's source pack
    placement = DC.load_plans(patch_dir, args.icao).get(tile) or {}
    pack_root = str(placement.get("pack_root") or "")
    if not DC.pack_is_build_product(args, pack_root):
        raise SystemExit("NOT MEASURED: no --pack-copy -- the pack on disk is not this "
                         "build's objects")
    mine = [d for d in tile_dsfs if os.path.basename(d) == f"{tile}.dsf"]
    if not mine:
        raise SystemExit(f"NOT MEASURED: no drawn {tile}.dsf in the build")
    return {"tile": tile, "tile_dsf": mine[0], "pack_root": pack_root, "plan": plan,
            "patch_dir": patch_dir, "build_dir": res["build_dir"],
            "lat": int(tile[:3]), "lon": int(tile[3:])}


def _records(plan) -> list[dict]:
    return [dict(r, icao=plan.get("icao", "")) for r in plan.get("authored_seats") or ()
            if isinstance(r, dict) and isinstance(r.get("cut"), dict)
            and (r["cut"].get("fill") or r["cut"].get("plane"))]


def _alt(prod) -> tuple:
    """The build's ``.alt`` (memory-mapped) and its frame, or ``(None, None)``."""
    import O4_File_Names as FNAMES
    path = FNAMES.rebuild_path(prod["build_dir"], prod["lat"], prod["lon"],
                               f"Data{prod['tile']}.alt")
    if not os.path.isfile(path):
        return None, None
    n = int(round(math.sqrt(os.path.getsize(path) / 4)))
    frame = {"x0": -0.01, "y0": -0.01, "x1": 1.01, "y1": 1.01, "nxdem": n, "nydem": n}
    import O4_DEM_Utils as DEM
    try:
        with open(DEM.alt_frame_sidecar_path(path), encoding="utf-8") as fh:
            frame.update({k: v for k, v in json.load(fh).items()
                          if k in ("x0", "y0", "x1", "y1", "nxdem", "nydem")})
    except (OSError, ValueError):
        pass
    frame["path"] = path
    return (np.memmap(path, dtype=np.float32, mode="r",
                      shape=(int(frame["nydem"]), int(frame["nxdem"]))), frame)


def _shoulder(frame, lat: float) -> tuple[float, float, float]:
    """``(W, W + s, d)`` of the tile raster (``terrain_fill``)."""
    from auto_patch_v2.airport import terrain_fill as TF
    nx, ny = int(frame["nxdem"]), int(frame["nydem"])
    r = TF.Raster(np.zeros((ny, 2)), 0.0, lat + float(frame["y1"]),
                  (frame["x1"] - frame["x0"]) / (nx - 1), (frame["y1"] - frame["y0"]) / (ny - 1))
    dx, dy = r.posting_m()
    return r.shoulder_m(), r.shoulder_m() + max(dx, dy), math.hypot(dx, dy)


def _rim(recs, comps, mesh, w) -> list[dict]:
    """RIM (module doc) of every fill record."""
    from auto_patch_v2.airport import terrain_fill as TF
    from auto_patch_v2.airport import terrain_model as TM
    out = []
    for r in recs:
        c = comps.get(r["id"])
        if c is None or not r["cut"].get("fill"):
            continue
        g = TM.plan_grid(str(r["cut"]["file"]))
        ri, rj = np.nonzero(TM.outer_rim(g.covered))
        sx, sy = TM._world(g, ri, rj, (0.0, 0.0), float(r["cut"]["heading"]))
        lo, la = c.to_ll(sx, sy)
        fl = float(r["elevation"]) + g.bot[ri, rj] - mesh.z(la, lo)
        near = TF._owned_mask([o.owned for k, o in comps.items() if k != r["id"]], c.to_xy,
                              sx, sy, w)
        bad = np.flatnonzero((fl > UNDER_BAR_M) & ~near)
        out.append({"resource": r.get("resource"), "rim_cells": int(len(fl)),
                    "over_bar_judged": int(len(bad)),
                    "over_bar_exempt": int(np.sum((fl > UNDER_BAR_M) & near)),
                    "max_judged_m": _rnd(np.nanmax(np.where(~near, fl, -np.inf))),
                    "worst": [[round(float(la[k]), 6), round(float(lo[k]), 6), _rnd(fl[k])]
                              for k in bad[np.argsort(-fl[bad])][:8]]})
    return out


def _members(rows, rec) -> list:
    """The written rows of a relief skin's set (its origin and heading)."""
    c = rec["cut"]
    return [p for _i, p, _root, _t in rows
            if abs(p.lat - float(c["lat"])) < 1e-7 and abs(p.lon - float(c["lon"])) < 1e-7
            and abs((p.heading_deg - float(c["heading"]) + 180.0) % 360.0 - 180.0) < 1e-3]


def _solid(pack_root, def_path):
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.airport.obj8 import parse_obj8
    path = os.path.join(pack_root, def_path)
    return TM._solid(parse_obj8(path)) if os.path.isfile(path) else None


def _under_terrain(recs, comps, lon, lat, foot_z) -> np.ndarray:
    """Feet under a terrain member's top (its own plan grid, any record)."""
    from auto_patch_v2.airport import terrain_cut as TC
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.geom.terrain_deck import UNDER_M, TerrainFit
    out = np.zeros(len(lon), bool)
    for r in recs:
        c = comps.get(r["id"])
        g = TM.plan_grid(str(r["cut"]["file"]))
        if c is None or g is None:
            continue
        fit = TerrainFit("top", "", (0.0, 0.0), float(r["cut"]["heading"]),
                         float(r["elevation"]), 1.0, 0.0, 0.0, g, fill=False)
        z, inside = TC.cut_heights(fit, c.to_xy, lon, lat, np.full(len(lon), np.inf))
        out |= inside & (foot_z < z + UNDER_M - 0.05)
    return out


def _land(fp, water_xy, to_ll, mesh, plane_z) -> dict:
    import shapely
    land = fp if water_xy is None else fp.difference(water_xy.buffer(LAND_PAD_M))
    x0, y0, x1, y1 = land.bounds
    gx, gy = np.meshgrid(np.arange(x0, x1, LAND_STEP_M), np.arange(y0, y1, LAND_STEP_M))
    ins = shapely.contains_xy(land, gx.ravel(), gy.ravel())
    lo, la = to_ll(gx.ravel()[ins], gy.ravel()[ins])
    off = mesh.z(la, lo) - plane_z
    if not len(off):
        return {"samples": 0, "over": 0, "under": 0}
    return {"samples": int(len(off)), "over": int(np.sum(off > UNDER_BAR_M)),
            "under": int(np.sum(off < -UNDER_BAR_M)), "max_over_m": _rnd(np.nanmax(off)),
            "max_under_m": _rnd(-np.nanmin(off)), "off_mesh": int(np.sum(~np.isfinite(off)))}


def _feet(rec, comp, recs, comps, rows, pack_root, mesh, water_xy, sites) -> dict:
    """FEET, LAND and SITES (module doc) of one relief skin."""
    import shapely
    from auto_patch_v2.airport import terrain_fill as TF
    c = rec["cut"]
    z0, plane_z = float(rec["elevation"]), float(c["plane"]["z"])
    members = _members(rows, rec)
    others = [p for p in members if p.def_path != rec.get("resource")]
    cells = foot_cells([_solid(pack_root, p.def_path) for p in others])
    decks = deck_index([_solid(pack_root, p.def_path) for p in members])
    h = math.radians(float(c["heading"]))
    e = cells["x"] * math.cos(h) - cells["z"] * math.sin(h)
    n = -(cells["x"] * math.sin(h) + cells["z"] * math.cos(h))
    lon, lat = comp.to_ll(e, n)
    foot_z = z0 + cells["y"]
    ground = mesh.z(lat, lon)
    fp = TF._polygon([np.c_[comp.to_xy(q[:, 0], q[:, 1])] for q in
                      (np.asarray(r, float) for r in c["plane"]["rings"]) if len(q) >= 4])
    wd = (np.full(len(e), np.inf) if water_xy is None else
          np.where(shapely.contains_xy(water_xy, e, n), 0.0,
                   shapely.distance(water_xy, shapely.points(np.c_[e, n]))))
    lab = classify_feet(cells["y"], on_deck(cells["i"], cells["j"], cells["y"], decks),
                        shapely.contains_xy(fp, e, n), wd,
                        _under_terrain(recs, comps, lon, lat, foot_z), TF.QUAY_M)
    fail = np.flatnonzero(judge_feet(lab, ground, plane_z))
    terr = lab == "terrace"
    near_sites = {}
    for name, plat, plon in sites:
        qe, qn = comp.to_xy(np.array([plon]), np.array([plat]))
        k = np.hypot(e - qe[0], n - qn[0]) < SITE_R_M
        near_sites[name] = {"at": [plat, plon], "drawn_m": _rnd(mesh.z([plat], [plon])[0]),
                            "feet_minus_ground": np.round(foot_z[k] - ground[k], 2).tolist()[:12],
                            "authored_y": np.round(cells["y"][k], 2).tolist()[:12]}
    stems = {os.path.splitext(os.path.basename(p.def_path))[0] for p in members}
    obj_dir = os.path.join(pack_root, "objects")
    split = (sum(1 for f in os.listdir(obj_dir) if "__b" in f and f.split("__b")[0] in stems)
             if os.path.isdir(obj_dir) else 0)
    burial = ground[terr] - foot_z[terr]
    return {"resource": rec.get("resource"), "z0": z0, "plane_z": plane_z,
            "rows": len(members), "kinds": sorted({p.kind for p in members}),
            "zeros": sorted({round(float(p.elevation), 3) for p in members}),
            "split_files": split, "cells": int(len(lab)),
            "labels": {k: int(np.sum(lab == k)) for k in sorted(set(lab.tolist()))},
            "judged_fail": int(len(fail)),
            "fails": [[round(float(lat[k]), 6), round(float(lon[k]), 6), _rnd(cells["y"][k]),
                       _rnd(plane_z - ground[k])] for k in fail[np.argsort(ground[fail])][:20]],
            "deck_water_feet_minus_ground": _span(foot_z, ground, lab == "deck_water"),
            "quay_feet_minus_ground": _span(foot_z, ground, lab == "quay"),
            "terrace_burial_m": [_rnd(np.nanmin(burial)), _rnd(np.nanmax(burial))]
            if terr.any() else None,
            "land": _land(fp, water_xy, comp.to_ll, mesh, plane_z), "sites": near_sites}


def _span(foot_z, ground, sel) -> list | None:
    d = (foot_z - ground)[sel]
    d = d[np.isfinite(d)]
    return [_rnd(d.min()), _rnd(d.max())] if len(d) else None


def _water(points, mesh, against) -> dict:
    base = (against or {}).get("water") or {}
    out = {}
    for name, lat, lon in points:
        z = _rnd(mesh.z([lat], [lon])[0])
        b = (base.get(name) or {}).get("drawn_m")
        out[name] = {"at": [lat, lon], "drawn_m": z, "control_m": b,
                     "moved_m": None if z is None or b is None else round(z - b, 3)}
    return out


def _rows(rows, recs) -> dict:
    want = {r.get("resource") for r in recs}
    return {p.def_path: [p.kind, round(float(p.elevation), 3)] for _i, p, _r, _t in rows
            if p.def_path in want}


def _frames(prod, box, out_dir) -> dict:
    """The review frame (module doc): clipped mesh, ``.alt`` window,
    sidecar, plans."""
    import O4_File_Names as FNAMES
    import O4_Mesh_IO as MIO
    os.makedirs(out_dir, exist_ok=True)
    tile, (w, s, e, n) = prod["tile"], box
    rep = {}
    mesh_path = FNAMES.mesh_file(prod["build_dir"], prod["lat"], prod["lon"])
    if os.path.isfile(mesh_path):
        m = MIO.read_mesh(mesh_path)
        co = np.asarray(m.coords)
        tri, att = np.asarray(m.triangles, np.int64), np.asarray(m.attributes)
        lon, lat = co[:, 0], co[:, 1]
        if lon.max() < 2:
            lon, lat = lon + prod["lon"], lat + prod["lat"]
        cx, cy = lon[tri].mean(1), lat[tri].mean(1)
        sel = (cx >= w) & (cx <= e) & (cy >= s) & (cy <= n)
        used, inv = np.unique(tri[sel], return_inverse=True)
        np.savez_compressed(os.path.join(out_dir, f"mesh_{tile}.npz"), lon=lon[used],
                            lat=lat[used], z=co[used, 2], triangles=inv.reshape(-1, 3),
                            attributes=att[sel], box=np.asarray(box, float))
        rep["mesh"] = {"triangles": int(sel.sum()), "vertices": int(len(used))}
    alt, frame = _alt(prod)
    if alt is not None:
        nx, ny = int(frame["nxdem"]), int(frame["nydem"])
        dx, dy = (frame["x1"] - frame["x0"]) / (nx - 1), (frame["y1"] - frame["y0"]) / (ny - 1)
        c0 = max(0, int((w - prod["lon"] - frame["x0"]) / dx))
        c1 = min(nx - 1, int((e - prod["lon"] - frame["x0"]) / dx) + 1)
        r0 = max(0, int((frame["y1"] - (n - prod["lat"])) / dy))
        r1 = min(ny - 1, int((frame["y1"] - (s - prod["lat"])) / dy) + 1)
        np.savez_compressed(os.path.join(out_dir, f"alt_{tile}.npz"),
                            alt=np.array(alt[r0:r1 + 1, c0:c1 + 1]), r0=r0, c0=c0, nx=nx, ny=ny,
                            frame=np.array([frame["x0"], frame["y0"], frame["x1"], frame["y1"]]))
        rep["alt"] = {"rows": [r0, r1], "cols": [c0, c1]}
        side = frame["path"] + ".unfill.npz"
        if os.path.isfile(side):
            shutil.copy2(side, os.path.join(out_dir, os.path.basename(side)))
            rep["unfill"] = os.path.basename(side)
    icao = prod["plan"].get("icao")
    for name in (f"o4_v2_rebake_{icao}.json", f"o4_v2_placement_{icao}.json"):
        src = os.path.join(prod["patch_dir"], name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, name))
    return rep


def _water_xy(water, box, prod, comp):
    import shapely
    if water is None:
        return None
    near = water.intersection(shapely.box(box[0] - prod["lon"], box[1] - prod["lat"],
                                          box[2] - prod["lon"], box[3] - prod["lat"]))
    return shapely.transform(near, lambda q: np.c_[comp.to_xy(q[:, 0] + prod["lon"],
                                                              q[:, 1] + prod["lat"])])


def run(args) -> dict:
    work = tempfile.mkdtemp(prefix="composite_bars_")
    try:
        return _run(args, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run(args, work: str) -> dict:
    import auto_patch.terrain_cut_stage as TCS
    import drawn_site as DS
    import O4_Config_Utils as CFG
    prod = _products(args)
    recs = _records(prod["plan"])
    if not recs:
        raise SystemExit("NOT MEASURED: the plan names no terrain composite")
    _alt_mm, frame = _alt(prod)
    if frame is None:
        raise SystemExit("NOT MEASURED: no .alt in the build (its posting sets W)")
    w, band, diag = _shoulder(frame, prod["lat"] + 0.5 * (frame["y0"] + frame["y1"]))
    comps = {r["id"]: TCS._composite(r, (band, diag)) for r in recs}
    comps = {k: v for k, v in comps.items() if v is not None}
    b = np.asarray([(q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max())
                    for c in comps.values() for q in c.owned.rings])
    box = (tuple(float(v) for v in args.box.split(",")) if args.box else
           (b[:, 0].min() - 0.001, b[:, 1].min() - 0.001, b[:, 2].max() + 0.001,
            b[:, 3].max() + 0.001))
    tool = DS.dsftool()
    mesh = DS.DrawnMesh(box, "", tool, prod["tile_dsf"], work)
    rows = DS.pack_rows(prod["pack_root"], {prod["tile"]}, work, tool)
    try:
        water = TCS._tile_water(CFG.Tile(prod["lat"], prod["lon"], ""))
    except Exception:
        water = None
    against = None
    if args.against:
        with open(args.against, encoding="utf-8") as fh:
            against = json.load(fh)
    sites = [_pt(t) for t in args.site or ()]
    feet = [_feet(r, comps[r["id"]], recs, comps, rows, prod["pack_root"], mesh,
                  _water_xy(water, box, prod, comps[r["id"]]), sites)
            for r in recs if r["id"] in comps and (r["cut"].get("plane") or {}).get("rings")]
    rep = {"icao": args.icao, "tag": args.tag, "tile_dsf": prod["tile_dsf"],
           "W_m": round(w, 2), "band_m": round(band, 2), "mapped_water": water is not None,
           "box": list(box), "rows": _rows(rows, recs), "rim": _rim(recs, comps, mesh, w),
           "feet": feet, "water": _water([_pt(t) for t in args.water or ()], mesh, against)}
    if args.frames_out:
        rep["frames"] = _frames(prod, box, args.frames_out)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--tag", required=True, help="a harness build: <out>/<tag>.result.json")
    ap.add_argument("--out", default="/tmp/harness", help="harness --out dir")
    ap.add_argument("--water", action="append", metavar="NAME=LAT,LON")
    ap.add_argument("--site", action="append", metavar="NAME=LAT,LON")
    ap.add_argument("--box", default=None, metavar="W,S,E,N")
    ap.add_argument("--frames-out", default=None, metavar="DIR")
    ap.add_argument("--json", default=None)
    ap.add_argument("--against", default=None, metavar="BASE.json")
    args = ap.parse_args(argv)
    args.tile = None
    rep = run(args)
    text = json.dumps(rep, indent=1, default=str)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(text)
    bad = (sum(r["over_bar_judged"] for r in rep["rim"])
           + sum(f["judged_fail"] + f["land"]["over"] + f["land"]["under"] for f in rep["feet"]))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
