#!/usr/bin/env python3
"""DOES THE DRAWN GROUND STAY UNDER AN OBJECT? (#2053 round 3).

A ground object the tile build cuts the ground under (``auto_patch_v2.
airport.terrain_cut``, THE HOLD) is judged on what X-Plane draws: the
object as WRITTEN in the harness build's pack copy (its row placed the way
X-Plane places it, ``drawn_site.row_base``), binned at 1 m in plan, and the
tile DSF's drawn mesh at every covered sample centre (``drawn_site``'s
loose-triangle sampler).  Per sample ``mesh - (base + top)``:

* OPEN (``top - low`` < :data:`ROOF_M`; a floorless roof falls here) is
  JUDGED: over ``--bar`` the ground pokes through the object;
* ROOFED (a roof a storey or more over a floor) is reported against its
  FLOOR, never judged;
* BAND (within :data:`BAND_M` of the plan's edge) / INNER, ON-PATCH (a
  face of ``--patch`` covers the sample, ``tools/patch_faces``) / OFF.

Every OPEN sample over the bar names the HIGHEST corner of its drawn
triangle: a ``patch node`` (an ``alt_abs`` node of the patch), ``water``
(at the 0 m datum), the ``plan edge`` (within :data:`EDGE_M` of the
outline), ``inner`` or ``outside``.

Reported, not judged: SINK -- the OPEN share drawn more than
:data:`SINK_M` under the top (riders draped on the ground sink there);
RIDERS -- every other pack row anchored on the plan, the mesh at its
anchor against the object's top (and floor), listed over :data:`RIDER_M`;
RIM -- the drawn ground :data:`drawn_site.OUTSIDE_M` outside each run of
the outline against the edge's top.

Exit 0 only when no OFF-patch OPEN sample stands over ``--bar``.

Usage (from Ortho4XP/)::

    venv/bin/python tools/drawn_cover.py SBRJ --tag T --object colegioNavalBase \\
        [--out DIR] [--patch P.osm] [--bar 0.05] [--json OUT] [--against BASE.json]

``drawn_site.py --cover ...`` hands over here.  Read-only (temp dumps).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

import numpy as np

_TOOLS = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(os.path.dirname(_TOOLS), "src"), _TOOLS, os.path.join(_TOOLS, "harness")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The console is UTF-8 before anything prints (#171, #125): ONE derivation
# site, ``src/O4_Console_Encoding.py``.  Twin: ``tests/test_console_encoding.py``.
import O4_Console_Encoding as _o4console  # noqa: E402, I001

_o4console.configure_console_streams()

import drawn_site as DS  # noqa: E402

__all__ = ["ROOF_M", "BAND_M", "SINK_M", "RIDER_M", "EDGE_M", "CELL_M", "cover_raster",
           "classes", "judge", "corner_label", "sink", "rim", "run", "main"]

#: a roof this far or more over the floor of a cell makes it ROOFED
ROOF_M = 3.0
#: the edge band (``terrain_cut.BAND_M``)
BAND_M = 10.0
#: drawn this far under the top, an OPEN sample SINKS (the ground bar)
SINK_M = DS.GROUND_BAR_M
#: a rider whose ground stands this far off the object's top is listed
RIDER_M = DS.GROUND_BAR_M
#: a drawn corner this near the outline is the plan edge's
EDGE_M = 1.5
#: the sample grid (``terrain_cut.HOLD_CELL_M``)
CELL_M = 1.0
#: the water datum a drawn corner at it names
WATER_TOL_M = 0.01
#: a drawn corner this near a patch node (plan) is that node
NODE_TOL_M = 0.1


# -- the object on a 1 m grid -------------------------------------------------

def cover_raster(p: np.ndarray):
    """The placed plan triangles ``p`` (site frame ``(east, north, z)``) on
    the :data:`CELL_M` grid (``geom.shape_class.Raster``)."""
    from auto_patch_v2.geom import shape_class
    return shape_class.rasterise(p, max_cells=10 ** 9, min_step=CELL_M)


def classes(r) -> dict:
    """Per covered cell (row-major ``ij``): OPEN, its distance to the edge
    and the edge distance of every grid cell (negative outside)."""
    from scipy import ndimage
    cov = np.isfinite(r.top)
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    inside = ndimage.distance_transform_edt(~rim) * r.step
    outside = ndimage.distance_transform_edt(~cov) * r.step
    edge = np.where(cov, inside, -outside)
    ij = np.argwhere(cov)
    top, low = r.top[cov], r.low[cov]
    return {"ij": ij, "open": (top - low) < ROOF_M, "edge": edge[cov], "edge_grid": edge,
            "top": top, "low": low}


def judge(d: np.ndarray, is_open: np.ndarray, on_patch: np.ndarray, bar: float) -> dict:
    """The counts of OPEN samples over ``bar`` (off / on the patch) and over
    the ground bar on the patch."""
    over = is_open & np.isfinite(d) & (d > bar)
    return {"open_off_over": int((over & ~on_patch).sum()),
            "open_on_over": int((over & on_patch).sum()),
            "open_on_over_ground": int((over & on_patch & (d > DS.GROUND_BAR_M)).sum()),
            "worst_m": float(np.nanmax(np.where(is_open, d, np.nan)))
            if is_open.any() and np.isfinite(d[is_open]).any() else None}


def corner_label(corner_en: np.ndarray, corner_z: float, edge_at, node_near) -> str:
    """What the highest corner of a drawn triangle is (module doc)."""
    if node_near(corner_en):
        return "patch node"
    if abs(corner_z) <= WATER_TOL_M:
        return "water"
    e = edge_at(corner_en)
    if e is None or e < -EDGE_M:
        return "outside"
    return "plan edge" if abs(e) <= EDGE_M else "inner"


def sink(d: np.ndarray, is_open: np.ndarray, band: np.ndarray) -> dict:
    """The OPEN share drawn more than :data:`SINK_M` under the top."""
    def share(m):
        n = int(m.sum())
        return round(100.0 * float((d[m] < -SINK_M).sum()) / n, 2) if n else None
    ok = is_open & np.isfinite(d)
    return {"open_pct": share(ok), "band_pct": share(ok & band), "inner_pct": share(ok & ~band)}


def rim(r, frame, mesh, top_n: int = 0) -> list[dict]:
    """The drawn ground :data:`drawn_site.OUTSIDE_M` outside each run of
    the outline against the edge's top (``mesh - top``)."""
    ij, dirs = DS.boundary_cells(r)
    if not len(ij):
        return []
    e, n = r.centres(ij)
    side = DS.sides_of(dirs, DS.principal_axis(e, n))
    out = []
    for run_ in DS.runs_of(ij, side):
        oe = e[run_] + DS.OUTSIDE_M * dirs[run_, 0]
        on = n[run_] + DS.OUTSIDE_M * dirs[run_, 1]
        z = mesh.z(*frame.leave(oe, on))
        d = z - r.top[ij[run_, 0], ij[run_, 1]]
        if not np.isfinite(d).any():
            continue
        lat, lon = frame.leave(float(e[run_].mean()), float(n[run_].mean()))
        out.append({"cells": int(len(run_)), "at": [round(float(lat), 7), round(float(lon), 7)],
                    "median_m": round(float(np.nanmedian(d)), 3),
                    "max_m": round(float(np.nanmax(d)), 3), "min_m": round(float(np.nanmin(d)), 3)})
    out.sort(key=lambda x: -abs(x["median_m"]))
    return out[:top_n] if top_n else out


# -- the products -------------------------------------------------------------

def products(args) -> dict:
    """Patch, tile DSF and written pack of a harness build ``--tag``."""
    import drawn_check as DC
    patch_dir, tile_dsfs = DC.resolve(args)
    tile = os.path.basename(patch_dir)
    plans = DC.load_plans(patch_dir, args.icao)
    if tile not in plans:
        raise SystemExit(f"NOT MEASURED: no o4_v2_placement_{args.icao}.json for {tile}")
    pack_root = plans[tile]["pack_root"]
    if not DC.pack_is_build_product(args, pack_root):
        raise SystemExit("NOT MEASURED: no --pack-copy -- the pack on disk is not this "
                         "build's objects")
    mine = [d for d in tile_dsfs if os.path.basename(d) == f"{tile}.dsf"]
    if not mine:
        raise SystemExit(f"NOT MEASURED: no drawn {tile}.dsf in the build")
    patch = args.patch or os.path.join(patch_dir, f"{args.icao}_auto.patch.osm")
    return {"tile": tile, "tile_dsf": mine[0], "pack_root": pack_root,
            "patch": patch if os.path.isfile(patch) else None}


def _placed(q, mesh) -> tuple:
    """``(frame, base, (m, 3, 3) site-frame plan triangles)`` of a picked row."""
    p, g = q["p"], q["g"]
    frame = DS.Frame(p.lat, p.lon)
    base = DS.row_base(p, float(mesh.z([p.lat], [p.lon])[0]))
    V = DS.placed_vertices(g, 0.0, 0.0, p.heading_deg, base)
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    return frame, base, DS.plan_triangles(V, tris)


def _on_patch(patch, frame, lat, lon, radius_m) -> np.ndarray:
    if not patch:
        return np.zeros(len(lat), bool)
    import shapely
    from patch_faces import PatchFaces
    pf = PatchFaces(patch, (frame.lat0, frame.lon0), radius_m)
    if not pf.faces:
        return np.zeros(len(lat), bool)
    x, y = pf._xy(np.asarray(lat), np.asarray(lon))
    return shapely.contains_xy(shapely.union_all([f[2] for f in pf.faces]), x, y)


def _node_near(patch, frame):
    if not patch:
        return lambda _en: False
    from drawn_gate import patch_nodes
    from scipy.spatial import cKDTree
    nodes = patch_nodes(patch)
    if not nodes:
        return lambda _en: False
    e, n = frame.enter(np.array([r[2] for r in nodes]), np.array([r[1] for r in nodes]))
    tree = cKDTree(np.c_[e, n])
    return lambda en: bool(tree.query(en, distance_upper_bound=NODE_TOL_M)[0] <= NODE_TOL_M)


def _edge_at(r, cls):
    grid = cls["edge_grid"]

    def at(en):
        j = int((en[0] - r.e0) // r.step)
        i = int((en[1] - r.n0) // r.step)
        if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1]:
            return float(grid[i, j])
        return None
    return at


def _attribute(lat, lon, corners, frame, edge_at, node_near) -> list[str]:
    """The highest corner's label of the drawn triangle under each point."""
    out = []
    for la, lo in zip(lat, lon, strict=True):
        t = corners
        a, b, c = t[:, 0, :2], t[:, 1, :2], t[:, 2, :2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        with np.errstate(divide="ignore", invalid="ignore"):
            l0 = ((b[:, 1] - c[:, 1]) * (lo - c[:, 0]) + (c[:, 0] - b[:, 0]) * (la - c[:, 1])) / d
            l1 = ((c[:, 1] - a[:, 1]) * (lo - c[:, 0]) + (a[:, 0] - c[:, 0]) * (la - c[:, 1])) / d
        hit = np.flatnonzero((l0 >= -1e-9) & (l1 >= -1e-9) & (1 - l0 - l1 >= -1e-9))
        if not len(hit):
            out.append("off mesh")
            continue
        tri = t[hit[0]]
        k = int(np.argmax(tri[:, 2]))
        en = np.array(frame.enter(tri[k, 1], tri[k, 0]), float)
        out.append(corner_label(en, float(tri[k, 2]), edge_at, node_near))
    return out


def _riders(rows, q, r, cls, frame, mesh, substr) -> list[dict]:
    covered = np.isfinite(r.top)
    out = []
    for row, p, _root, tile in rows:
        if substr.lower() in p.def_path.lower():
            continue
        e, n = frame.enter(p.lat, p.lon)
        j, i = int((e - r.e0) // r.step), int((n - r.n0) // r.step)
        if not (0 <= i < covered.shape[0] and 0 <= j < covered.shape[1]) or not covered[i, j]:
            continue
        z = float(mesh.z([p.lat], [p.lon])[0])
        d_top, d_low = z - float(r.top[i, j]), z - float(r.low[i, j])
        out.append({"row": f"{tile} obj{row}", "def": p.def_path, "kind": p.kind,
                    "at": [round(p.lat, 7), round(p.lon, 7)], "mesh_m": DS.rnd(z),
                    "vs_top_m": DS.rnd(d_top), "vs_floor_m": DS.rnd(d_low)})
    return out


# -- the reading ----------------------------------------------------------------

def run(args) -> dict:
    tool = DS.dsftool()
    work = tempfile.mkdtemp(prefix="drawn_cover_")
    try:
        return _run(args, tool, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run(args, tool: str, work: str) -> dict:
    import O4_Config_Utils  # noqa: F401
    import O4_File_Names as FNAMES
    from auto_patch_v2.planar.__main__ import _cfg_value
    prod = products(args)
    scenery = _cfg_value("custom_scenery_dir") or os.path.expanduser(
        "~/X-Plane 12/Custom Scenery")
    res = DS.Resources(os.path.dirname(scenery.rstrip("/")), FNAMES.airport_mod_cache_root())
    rows = DS.pack_rows(prod["pack_root"], {prod["tile"]}, work, tool)
    picked = DS.select(rows, [], [args.object], {}, res, 0.0)
    if not picked:
        raise SystemExit(f"NOT MEASURED: no written row of {args.object!r}")
    q = picked[0]
    box = DS.mesh_box([], [q])
    mesh = DS.DrawnMesh(box, "", tool, prod["tile_dsf"], work)
    corners = DS.tile_triangles(prod["tile_dsf"], box, tool, work)
    frame, base, p = _placed(q, mesh)
    r = cover_raster(p)
    cls = classes(r)
    e, n = r.centres(cls["ij"])
    lat, lon = frame.leave(e, n)
    z = mesh.z(lat, lon)
    d, d_floor = z - cls["top"], z - cls["low"]
    band = cls["edge"] <= BAND_M
    on = _on_patch(prod["patch"], frame, lat, lon, q["reach"] + 100.0)
    verdict = judge(d, cls["open"], on, args.bar)
    over = np.flatnonzero(cls["open"] & np.isfinite(d) & (d > args.bar))
    labels = _attribute(lat[over], lon[over], corners, frame, _edge_at(r, cls),
                        _node_near(prod["patch"], frame))
    listed = [{"at": [round(float(lat[k]), 7), round(float(lon[k]), 7)], "over_m": DS.rnd(d[k]),
               "band": bool(band[k]), "on_patch": bool(on[k]), "corner": lab}
              for k, lab in zip(over, labels, strict=True)]
    listed.sort(key=lambda x: -x["over_m"])
    roofed = ~cls["open"] & np.isfinite(d_floor)
    return {"icao": args.icao, "tag": args.tag, "object": args.object, "row": q["row"],
            "def": q["p"].def_path, "kind": q["p"].kind, "base_m": DS.rnd(base),
            "tile_dsf": prod["tile_dsf"], "patch": prod["patch"], "bar_m": args.bar,
            "samples": int(len(d)), "open": int(cls["open"].sum()),
            "roofed": int((~cls["open"]).sum()), "band": int(band.sum()),
            "on_patch": int(on.sum()), "off_mesh": int((~np.isfinite(d)).sum()),
            "verdict": verdict,
            "by_corner": {k: labels.count(k) for k in sorted(set(labels))},
            "over": listed,
            "roofed_vs_floor": {"median_m": DS.rnd(np.median(d_floor[roofed]))
                                if roofed.any() else None,
                                "over_ground_bar": int((d_floor[roofed] > DS.GROUND_BAR_M).sum())},
            "sink": sink(d, cls["open"], band),
            "riders": [x for x in _riders(rows, q, r, cls, frame, mesh, args.object)
                       if abs(x["vs_top_m"]) > RIDER_M],
            "rim": rim(r, frame, mesh)}


def print_report(rep: dict, top_n: int = 20) -> None:
    v = rep["verdict"]
    print(f"DRAWN COVER {rep['icao']} {rep['tag']} {rep['def']} ({rep['kind']} "
          f"base {rep['base_m']}): {rep['samples']} samples ({rep['open']} OPEN, "
          f"{rep['roofed']} ROOFED; {rep['band']} band; {rep['on_patch']} on-patch; "
          f"{rep['off_mesh']} off mesh)")
    print(f"  B1 off-patch OPEN over {rep['bar_m']} m: {v['open_off_over']}; "
          f"B2 on-patch OPEN over {rep['bar_m']} m: {v['open_on_over']} "
          f"(over {DS.GROUND_BAR_M} m: {v['open_on_over_ground']}); worst {v['worst_m']}")
    print(f"  over-bar corners: {rep['by_corner']}")
    for x in rep["over"][:top_n]:
        print(f"    {x['over_m']:+.3f} m at {x['at'][0]}, {x['at'][1]} "
              f"{'band' if x['band'] else 'inner'} {'on' if x['on_patch'] else 'off'}-patch "
              f"corner: {x['corner']}")
    print(f"  ROOFED vs floor: {rep['roofed_vs_floor']}")
    print(f"  SINK: {rep['sink']}")
    print(f"  RIDERS over {RIDER_M} m off the top: {len(rep['riders'])}")
    for x in rep["riders"][:top_n]:
        print(f"    {x['row']} {x['def']} ({x['kind']}) at {x['at']}: vs top {x['vs_top_m']:+} m"
              f", vs floor {x['vs_floor_m']:+} m")
    print(f"  RIM (drawn {DS.OUTSIDE_M} m outside - edge top), {len(rep['rim'])} run(s):")
    for x in rep["rim"][:top_n]:
        print(f"    {x['cells']} cells at {x['at']}: median {x['median_m']:+} "
              f"(min {x['min_m']:+}, max {x['max_m']:+})")


def _against(rep: dict, base_path: str) -> None:
    base = json.load(open(base_path, encoding="utf-8"))
    for k in ("open_off_over", "open_on_over", "open_on_over_ground"):
        print(f"  AGAINST {k}: {base['verdict'][k]} -> {rep['verdict'][k]}")
    print(f"  AGAINST sink open %: {base['sink']['open_pct']} -> {rep['sink']['open_pct']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("icao")
    ap.add_argument("--tag", required=True, help="a harness build: <out>/<tag>.result.json")
    ap.add_argument("--out", default="/tmp/harness", help="harness --out dir")
    ap.add_argument("--object", required=True, help="the written row whose resource contains this")
    ap.add_argument("--patch", default=None, help="the patch (default: the build's)")
    ap.add_argument("--bar", type=float, default=DS.PAVEMENT_BAR_M, help="OPEN bar, m")
    ap.add_argument("--json", default=None, help="write the full report here")
    ap.add_argument("--against", default=None, metavar="BASE.json", help="a control's --json")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args(argv)
    rep = run(args)
    print_report(rep, args.top)
    if args.against:
        _against(rep, args.against)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=1)
    return 0 if rep["verdict"]["open_off_over"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
