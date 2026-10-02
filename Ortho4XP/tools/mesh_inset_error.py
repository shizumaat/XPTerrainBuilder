"""How closely does a BUILT MESH follow an airport's elevation INSET?

The owner's question at KASE (issue #233, sim read of 1.0.368): "terrain
still looks low resolution" under a 1 m lidar inset.  The working grid
was fine; the MESH was the limiter.  This is the instrument that says so,
promoted from lane kaseread368's scratch reads (``a_read.py`` / ``a2.py``
/ ``a3.py``) on their second use (lane meshbox233).

For one mesh and one inset raster it reports, over the inset's DELIVERED
box and OUTSIDE the patch rings (``--graded``, the patch's own
``<ICAO>.graded.json``; +``--patch-buffer-m``):

* triangles, triangles / km^2, edge lengths, and the share of GROUND AREA
  in triangles whose longest edge exceeds 30 / 60 / 100 m;
* ``|mesh - inset|`` at triangle CENTROIDS (the flat-facet error the eye
  reads: the mean of the three corner altitudes against the inset's
  bilinear value there) and at mesh VERTICES (what the grid delivered);
* the same by distance band from the patch hull (``--bands``, metres,
  default ``100,1000,3000`` = the 0.1-1 km and 1-3 km rows of #233);
* ``patch_vertices``: the count and a sha256 over the sorted
  ``(lon, lat, z)`` of every mesh vertex INSIDE the patch rings — two
  meshes whose digests agree carry the same airside vertices and
  altitudes (the "patch unaffected" check of a mesh-density A/B);
* ``--compare-patch CONTROL.mesh``: when the digests differ, WHY — the
  control's patch vertices missing or re-levelled, and each added
  vertex's distance from the control surface (a split puts a vertex ON
  the control surface; a moved one is a defect).

It reads the inset raster itself (bilinear, nodata-aware) and never the
tile's ``.alt``: ``mesh_elevation_sampler.AltRaster`` assumes the
viewfinder extent [-0.01, 1.01] and misreads a NED1-based ``.alt``.
It prices no law and builds nothing.

Usage (from ``Ortho4XP/``)::

    venv/bin/python tools/mesh_inset_error.py --mesh Data+39-107.mesh \
        --inset Elevation_data/.../KASE_usgs3dep.tif \
        --graded Patches/.../KASE.graded.json [--json OUT.json]
"""
import argparse
import hashlib
import json
import math
import os
import sys

import numpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

LAT_M = 111132.0
LONG_EDGE_CLASSES_M = (30.0, 60.0, 100.0)
PERCENTILES = (50, 90, 95, 99)


def read_mesh(path):
    """``(vertices[n, 3] lon/lat/metres, triangles[m, 3])``."""
    from auto_patch.mesh_sampler import _read_mesh_cached
    arrays = _read_mesh_cached(path)
    return (numpy.array(arrays[0], dtype=numpy.float64),
            numpy.asarray(arrays[1]))


class InsetRaster:
    """Bilinear, nodata-aware reader of one inset GeoTIFF (EPSG:4326)."""

    def __init__(self, path):
        from osgeo import gdal
        gdal.UseExceptions()
        dataset = gdal.Open(path)
        self.gt = dataset.GetGeoTransform()
        band = dataset.GetRasterBand(1)
        self.data = band.ReadAsArray().astype(numpy.float32)
        self.nodata = band.GetNoDataValue()
        (rows, columns) = self.data.shape
        self.box = (self.gt[0], self.gt[3] + rows * self.gt[5],
                    self.gt[0] + columns * self.gt[1], self.gt[3])

    def contains(self, lon, lat):
        (west, south, east, north) = self.box
        return (lon > west) & (lon < east) & (lat > south) & (lat < north)

    def __call__(self, lon, lat):
        data = self.data
        fx = (lon - self.gt[0]) / self.gt[1] - 0.5
        fy = (lat - self.gt[3]) / self.gt[5] - 0.5
        ix = numpy.floor(fx).astype(int)
        iy = numpy.floor(fy).astype(int)
        ok = ((ix >= 0) & (iy >= 0) & (ix < data.shape[1] - 1)
              & (iy < data.shape[0] - 1))
        ix = numpy.clip(ix, 0, data.shape[1] - 2)
        iy = numpy.clip(iy, 0, data.shape[0] - 2)
        tx = fx - ix
        ty = fy - iy
        corners = (data[iy, ix], data[iy, ix + 1],
                   data[iy + 1, ix], data[iy + 1, ix + 1])
        for corner in corners:
            ok &= numpy.isfinite(corner) & (corner > -1000.0)
            if self.nodata is not None:
                ok &= corner != self.nodata
        value = (corners[0] * (1 - tx) * (1 - ty) + corners[1] * tx * (1 - ty)
                 + corners[2] * (1 - tx) * ty + corners[3] * tx * ty)
        return numpy.where(ok, value, numpy.nan)


def patch_union(graded_paths):
    """Union of every face ring of the given ``*.graded.json`` files
    (lon/lat), or ``None`` when no path is given."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polygons = []
    for path in graded_paths:
        with open(path, "r", encoding="utf-8") as handle:
            graded = json.load(handle)
        position = {v[0]: (v[2], v[1]) for v in graded["vertices"]}
        for face in graded["faces"]:
            ring = [position[i] for i in face["ring"]]
            if len(ring) >= 3:
                polygons.append(Polygon(ring).buffer(0))
    return unary_union(polygons) if polygons else None


def _quantiles(values):
    values = values[numpy.isfinite(values)]
    if not len(values):
        return None
    out = {"n": int(len(values)), "max": round(float(values.max()), 3)}
    for p in PERCENTILES:
        out["p%d" % p] = round(float(numpy.percentile(values, p)), 3)
    return out


def measure(mesh_path, inset_path, graded_paths=(), patch_buffer_m=15.0,
            bands=(100.0, 1000.0, 3000.0)):
    import shapely
    (vertices, triangles) = read_mesh(mesh_path)
    inset = InsetRaster(inset_path)
    (west, south, east, north) = inset.box
    lat0 = 0.5 * (south + north)
    lon0 = 0.5 * (west + east)
    lon_m = 111320.0 * math.cos(math.radians(lat0))

    def to_m(geometry):
        return shapely.transform(
            geometry, lambda a: numpy.column_stack(
                ((a[:, 0] - lon0) * lon_m, (a[:, 1] - lat0) * LAT_M)))

    patch = patch_union(graded_paths)
    patch_m = to_m(patch) if patch is not None else None
    hull_m = patch_m.convex_hull if patch_m is not None else None
    keep_out = patch_m.buffer(patch_buffer_m) if patch_m is not None else None

    a = vertices[triangles[:, 0]]
    b = vertices[triangles[:, 1]]
    c = vertices[triangles[:, 2]]
    cx = (a[:, 0] + b[:, 0] + c[:, 0]) / 3
    cy = (a[:, 1] + b[:, 1] + c[:, 1]) / 3
    index = numpy.nonzero(inset.contains(cx, cy))[0]
    (a, b, c, cx, cy) = (a[index], b[index], c[index], cx[index], cy[index])
    points = shapely.points((cx - lon0) * lon_m, (cy - lat0) * LAT_M)
    if patch_m is not None:
        in_patch = shapely.contains(keep_out, points)
        distance = shapely.distance(hull_m, points)
    else:
        in_patch = numpy.zeros(len(index), dtype=bool)
        distance = numpy.zeros(len(index))

    def edge(p, q):
        return numpy.hypot((p[:, 0] - q[:, 0]) * lon_m,
                           (p[:, 1] - q[:, 1]) * LAT_M)

    edges = numpy.stack([edge(a, b), edge(b, c), edge(c, a)], 1)
    area = 0.5 * numpy.abs(
        (b[:, 0] - a[:, 0]) * lon_m * (c[:, 1] - a[:, 1]) * LAT_M
        - (c[:, 0] - a[:, 0]) * lon_m * (b[:, 1] - a[:, 1]) * LAT_M)
    centroid_error = numpy.abs(
        (a[:, 2] + b[:, 2] + c[:, 2]) / 3 - inset(cx, cy))

    def region(mask):
        count = int(mask.sum())
        if not count:
            return {"triangles": 0}
        weights = area[mask]
        longest = edges[mask].max(1)
        return {
            "triangles": count,
            "area_km2": round(float(weights.sum()) / 1e6, 3),
            "triangles_per_km2": round(count / (weights.sum() / 1e6), 1),
            "edge_m": _quantiles(edges[mask].ravel()),
            "longest_edge_m": _quantiles(longest),
            "area_share_longest_edge_over_m": {
                "%g" % limit: round(
                    float(weights[longest > limit].sum() / weights.sum()), 4)
                for limit in LONG_EDGE_CLASSES_M},
            "centroid_abs_error_m": _quantiles(centroid_error[mask]),
        }

    report = {
        "mesh": mesh_path, "inset": inset_path,
        "inset_box": [round(v, 7) for v in inset.box],
        "mesh_triangles": int(len(triangles)),
        "mesh_vertices": int(len(vertices)),
        "triangles_in_box": int(len(index)),
        "regions": {"box_outside_patch": region(~in_patch)},
    }
    if patch_m is not None:
        for (low, high) in zip(bands[:-1], bands[1:]):
            report["regions"]["band_%g_%g_m" % (low, high)] = region(
                (distance > low) & (distance <= high) & ~in_patch)

    # Vertices: what the mesh holds AT its nodes, and the airside digest.
    in_box = numpy.nonzero(inset.contains(vertices[:, 0], vertices[:, 1]))[0]
    box_vertices = vertices[in_box]
    vertex_error = numpy.abs(
        box_vertices[:, 2] - inset(box_vertices[:, 0], box_vertices[:, 1]))
    if patch_m is not None:
        vertex_points = shapely.points((box_vertices[:, 0] - lon0) * lon_m,
                                       (box_vertices[:, 1] - lat0) * LAT_M)
        outside = ~shapely.contains(keep_out, vertex_points)
        inside = shapely.intersects(patch_m, vertex_points)
        airside = box_vertices[inside]
        order = numpy.lexsort((airside[:, 2], airside[:, 1], airside[:, 0]))
        digest = hashlib.sha256(
            numpy.round(airside[order], 9).tobytes()).hexdigest()
        report["patch_vertices"] = {"n": int(len(airside)), "sha256": digest}
    else:
        outside = numpy.ones(len(in_box), dtype=bool)
    report["regions"]["box_outside_patch"]["vertex_abs_error_m"] = _quantiles(
        vertex_error[outside])
    return report


def _surface_at(vertices, triangles, lon, lat):
    """Barycentric altitude of the mesh at one point (``nan`` outside)."""
    a = vertices[triangles[:, 0]]
    b = vertices[triangles[:, 1]]
    c = vertices[triangles[:, 2]]
    den = ((b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0])
           + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1]))
    with numpy.errstate(divide="ignore", invalid="ignore"):
        wa = ((b[:, 1] - c[:, 1]) * (lon - c[:, 0])
              + (c[:, 0] - b[:, 0]) * (lat - c[:, 1])) / den
        wb = ((c[:, 1] - a[:, 1]) * (lon - c[:, 0])
              + (a[:, 0] - c[:, 0]) * (lat - c[:, 1])) / den
    wc = 1.0 - wa - wb
    hit = numpy.nonzero((wa >= -1e-9) & (wb >= -1e-9) & (wc >= -1e-9))[0]
    if not len(hit):
        return float("nan")
    i = hit[0]
    return float(wa[i] * a[i, 2] + wb[i] * b[i, 2] + wc[i] * c[i, 2])


def compare_patch(mesh_path, control_path, graded_paths):
    """THE AIRSIDE A/B: is the patch surface of ``mesh_path`` the surface
    of ``control_path``?  A density change next to a patch may SPLIT a
    patch boundary segment or a patch face (a new vertex ON the control's
    surface); it must never MOVE one.  Reports the control's patch
    vertices missing or re-levelled in the mesh, and every added vertex's
    distance from the control surface at its own position."""
    import shapely
    patch = patch_union(graded_paths)
    (west, south, east, north) = patch.bounds

    def airside(path):
        (vertices, triangles) = read_mesh(path)
        box = ((vertices[:, 0] >= west) & (vertices[:, 0] <= east)
               & (vertices[:, 1] >= south) & (vertices[:, 1] <= north))
        candidates = vertices[box]
        inside = shapely.intersects(
            patch, shapely.points(candidates[:, 0], candidates[:, 1]))
        return (vertices, triangles, candidates[inside])

    (_v, _t, mine) = airside(mesh_path)
    (control_vertices, control_triangles, theirs) = airside(control_path)
    key = lambda row: (round(row[0], 9), round(row[1], 9))   # noqa: E731
    control = {key(row): row[2] for row in theirs}
    seen = {key(row): row[2] for row in mine}
    missing = [k for k in control if k not in seen]
    moved = [abs(seen[k] - control[k]) for k in control if k in seen]
    added = [row for row in mine if key(row) not in control]
    near = ((control_vertices[control_triangles[:, 0], 0] >= west - 0.01)
            & (control_vertices[control_triangles[:, 0], 0] <= east + 0.01)
            & (control_vertices[control_triangles[:, 0], 1] >= south - 0.01)
            & (control_vertices[control_triangles[:, 0], 1] <= north + 0.01))
    local = control_triangles[near]
    off = numpy.array([abs(row[2] - _surface_at(
        control_vertices, local, row[0], row[1])) for row in added])
    interior = int(sum(
        patch.boundary.distance(shapely.Point(row[0], row[1])) > 1e-7
        for row in added))
    return {
        "control": control_path,
        "control_patch_vertices": len(control), "patch_vertices": len(seen),
        "control_vertices_missing": len(missing),
        "common_max_abs_dz_m": round(float(max(moved)), 4) if moved else 0.0,
        "added_vertices": len(added), "added_interior": interior,
        "added_max_abs_dz_vs_control_surface_m":
            round(float(numpy.nanmax(off)), 4) if len(off) else 0.0,
    }


def format_report(report):
    lines = ["mesh %s: %d triangles, %d in the inset box %s" % (
        os.path.basename(report["mesh"]), report["mesh_triangles"],
        report["triangles_in_box"], report["inset_box"])]
    for (name, row) in report["regions"].items():
        if not row.get("triangles"):
            lines.append("%s: no triangles" % name)
            continue
        share = row["area_share_longest_edge_over_m"]
        lines.append(
            "%s: tris=%d (%.0f/km2 over %.2f km2) edge p50=%.1f p95=%.1f m; "
            "area share longest edge >30/60/100 m = %.2f/%.2f/%.2f" % (
                name, row["triangles"], row["triangles_per_km2"],
                row["area_km2"], row["edge_m"]["p50"], row["edge_m"]["p95"],
                share["30"], share["60"], share["100"]))
        for key in ("centroid_abs_error_m", "vertex_abs_error_m"):
            q = row.get(key)
            if q:
                lines.append(
                    "    %s: n=%d p50=%.2f p90=%.2f p95=%.2f p99=%.2f "
                    "max=%.2f" % (key, q["n"], q["p50"], q["p90"], q["p95"],
                                  q["p99"], q["max"]))
    if "patch_vertices" in report:
        lines.append("patch_vertices: n=%d sha256=%s" % (
            report["patch_vertices"]["n"],
            report["patch_vertices"]["sha256"][:16]))
    if "patch_compare" in report:
        lines.append("patch_compare: %s" % json.dumps(
            report["patch_compare"], sort_keys=True))
    return "\n".join(lines)


def main(argv=None):
    import O4_Console_Encoding as console

    console.configure_console_streams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--inset", required=True)
    parser.add_argument("--graded", action="append", default=[])
    parser.add_argument("--patch-buffer-m", type=float, default=15.0)
    parser.add_argument("--bands", default="100,1000,3000")
    parser.add_argument("--compare-patch", metavar="CONTROL.mesh",
                        help="the airside A/B against a control mesh")
    parser.add_argument("--json")
    args = parser.parse_args(argv)
    report = measure(
        args.mesh, args.inset, args.graded, args.patch_buffer_m,
        tuple(float(v) for v in args.bands.split(",")))
    if args.compare_patch:
        report["patch_compare"] = compare_patch(
            args.mesh, args.compare_patch, args.graded)
    print(format_report(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
