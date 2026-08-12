"""Sample elevations from a built Ortho4XP ``Data<tile>.mesh``.

This is the terrain the simulator actually renders, *after* auto_patch's
runway/apron/taxiway grading.  Sampling the source DEM instead would
report the pre-grading surface and mislead by several metres anywhere
the pavement builder has moved the ground.

Mesh format, as written by ``O4_Mesh_Utils.write_mesh_file``::

    MeshVersionFormatted 2
    Dimension 3

    Vertices
    <count>
    <longitude> <latitude> <elevation/100000> <tag>
    ...
    Normals
    <count>
    ...
    Triangles
    <count>
    <vertex_a> <vertex_b> <vertex_c> <tag>

Note the ``/ 100000`` scaling on the elevation column, and that the
triangle vertex indices are 1-based (they come straight from Triangle's
``.ele`` output).
"""

from __future__ import annotations

import math

import numpy

# O4_Mesh_Utils writes elevation divided by this constant.
MESH_ELEVATION_SCALE = 100000.0


class MeshElevationSampler:
    """Point-in-triangle elevation lookup over a built Ortho4XP mesh.

    Only triangles overlapping ``bounds`` are retained, which keeps a
    3-million-triangle tile down to something a probe can hold and scan.
    """

    def __init__(
        self,
        mesh_path: str,
        bounds: tuple[float, float, float, float],
        margin_degrees: float = 0.002,
    ) -> None:
        """``bounds`` is ``(min_lon, min_lat, max_lon, max_lat)``."""
        min_lon, min_lat, max_lon, max_lat = bounds
        min_lon -= margin_degrees
        min_lat -= margin_degrees
        max_lon += margin_degrees
        max_lat += margin_degrees

        vertices, triangles = self._read_mesh(mesh_path)

        inside = (
            (vertices[:, 0] >= min_lon)
            & (vertices[:, 0] <= max_lon)
            & (vertices[:, 1] >= min_lat)
            & (vertices[:, 1] <= max_lat)
        )
        keep = inside[triangles].any(axis=1)
        self._triangles = triangles[keep]
        if not len(self._triangles):
            raise ValueError(
                f"no mesh triangles inside {bounds} — wrong tile?"
            )
        self._vertices = vertices

        corners = vertices[self._triangles]
        self._corner_a = corners[:, 0, :]
        self._corner_b = corners[:, 1, :]
        self._corner_c = corners[:, 2, :]
        self._triangle_min = corners[:, :, :2].min(axis=1)
        self._triangle_max = corners[:, :, :2].max(axis=1)

    @staticmethod
    def _read_mesh(
        mesh_path: str,
    ) -> tuple[numpy.ndarray, numpy.ndarray]:
        with open(mesh_path) as handle:
            while True:
                line = handle.readline()
                if not line:
                    raise ValueError(f"{mesh_path}: no Vertices section")
                if line.strip() == "Vertices":
                    break
            vertex_count = int(handle.readline())
            block = [handle.readline() for _ in range(vertex_count)]
            vertices = numpy.array(
                " ".join(block).split(), dtype=numpy.float64
            ).reshape(vertex_count, 4)[:, :3]
            vertices[:, 2] *= MESH_ELEVATION_SCALE

            while True:
                line = handle.readline()
                if not line:
                    raise ValueError(f"{mesh_path}: no Triangles section")
                if line.strip() == "Triangles":
                    break
            triangle_count = int(handle.readline())
            block = [handle.readline() for _ in range(triangle_count)]
            triangles = numpy.array(
                " ".join(block).split(), dtype=numpy.int64
            ).reshape(triangle_count, -1)[:, :3]

        # Triangle emits 1-based indices; normalise and verify.
        if triangles.min() >= 1:
            triangles = triangles - 1
        if triangles.max() >= len(vertices):
            raise ValueError(f"{mesh_path}: triangle index out of range")
        return vertices, triangles

    def elevation_at(self, latitude: float, longitude: float) -> float:
        """Barycentric-interpolated elevation, in metres.

        Falls back to the nearest mesh vertex when the point lands
        outside every retained triangle (which happens only outside the
        requested bounds).
        """
        candidates = numpy.nonzero(
            (self._triangle_min[:, 0] <= longitude)
            & (self._triangle_max[:, 0] >= longitude)
            & (self._triangle_min[:, 1] <= latitude)
            & (self._triangle_max[:, 1] >= latitude)
        )[0]

        for index in candidates:
            a = self._corner_a[index]
            b = self._corner_b[index]
            c = self._corner_c[index]
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (
                a[1] - c[1]
            )
            if abs(denominator) < 1e-18:
                continue
            weight_a = (
                (b[1] - c[1]) * (longitude - c[0])
                + (c[0] - b[0]) * (latitude - c[1])
            ) / denominator
            weight_b = (
                (c[1] - a[1]) * (longitude - c[0])
                + (a[0] - c[0]) * (latitude - c[1])
            ) / denominator
            weight_c = 1.0 - weight_a - weight_b
            if weight_a >= -1e-9 and weight_b >= -1e-9 and weight_c >= -1e-9:
                return float(
                    weight_a * a[2] + weight_b * b[2] + weight_c * c[2]
                )

        distances = numpy.hypot(
            self._vertices[:, 0] - longitude, self._vertices[:, 1] - latitude
        )
        return float(self._vertices[int(distances.argmin()), 2])


# ── CLI: TRANSECTS (round 17c) ────────────────────────────────────────
#
# The shore/canyon acceptance in rounds 17, 17b and 17c is a PROFILE
# across the built mesh — "does the north shore read Z0 to the wall and
# then sea, or a 40 m ramp?".  r17b answered it from a scratchpad
# script; this is that script's SECOND use, which is the signal to
# promote it into the tool that already owns the question (tool
# discipline, RULINGS 7e90032 — extend the near-fit, never fork it).
#
#   venv/bin/python tools/mesh_elevation_sampler.py MESH \
#       --lon 113.9200 --lat-range 22.3260 22.3400 --step 0.0001
#   venv/bin/python tools/mesh_elevation_sampler.py MESH \
#       --lat 22.3100 --lon-range 113.8930 113.9070 --step 0.0001
#   venv/bin/python tools/mesh_elevation_sampler.py MESH \
#       --point 22.3089 113.9147
#
# ``--step-flag M`` annotates any sample-to-sample jump of at least M
# metres, which is how a FACE (one step) is told from a RAMP (several).

def _transect(sampler, points, fmt, step_flag):
    rows = [(lon, lat, sampler.elevation_at(lat, lon))
            for (lon, lat) in points]
    previous = None
    for (lon, lat, z) in rows:
        note = ""
        if previous is not None and z is not None:
            delta = z - previous
            if abs(delta) >= step_flag:
                note = "   <-- STEP {:+.2f} m".format(delta)
        print(fmt.format(lon=lon, lat=lat,
                         z=("None" if z is None else "{:8.3f}".format(z)))
              + note)
        previous = z
    return rows


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Sample or transect a built Data<tile>.mesh.")
    parser.add_argument("mesh")
    parser.add_argument("--lon", type=float,
                        help="fixed longitude for a latitude sweep")
    parser.add_argument("--lat-range", nargs=2, type=float,
                        metavar=("LAT0", "LAT1"))
    parser.add_argument("--lat", type=float,
                        help="fixed latitude for a longitude sweep")
    parser.add_argument("--lon-range", nargs=2, type=float,
                        metavar=("LON0", "LON1"))
    parser.add_argument("--step", type=float, default=0.0001,
                        help="sweep step in degrees (default 0.0001)")
    parser.add_argument("--step-flag", type=float, default=1.0,
                        help="annotate jumps of at least this many metres")
    parser.add_argument("--point", nargs=2, type=float, action="append",
                        default=[], metavar=("LAT", "LON"),
                        help="one point (repeatable)")
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    margin = 0.001
    if args.lon is not None and args.lat_range:
        lat0, lat1 = sorted(args.lat_range)
        values = []
        v = lat0
        while v <= lat1 + 1e-12:
            values.append(v)
            v += args.step
        bounds = (args.lon - margin, lat0 - margin,
                  args.lon + margin, lat1 + margin)
        sampler = MeshElevationSampler(args.mesh, bounds)
        print("=== {} lon {:.5f} (lat sweep, {} sample(s)) ===".format(
            args.label or "TRANSECT", args.lon, len(values)))
        _transect(sampler, [(args.lon, v) for v in values],
                  "  lat {lat:.5f}  z {z}", args.step_flag)
    elif args.lat is not None and args.lon_range:
        lon0, lon1 = sorted(args.lon_range)
        values = []
        v = lon0
        while v <= lon1 + 1e-12:
            values.append(v)
            v += args.step
        bounds = (lon0 - margin, args.lat - margin,
                  lon1 + margin, args.lat + margin)
        sampler = MeshElevationSampler(args.mesh, bounds)
        print("=== {} lat {:.5f} (lon sweep, {} sample(s)) ===".format(
            args.label or "TRANSECT", args.lat, len(values)))
        _transect(sampler, [(v, args.lat) for v in values],
                  "  lon {lon:.5f}  z {z}", args.step_flag)
    elif args.point:
        lats = [p[0] for p in args.point]
        lons = [p[1] for p in args.point]
        sampler = MeshElevationSampler(
            args.mesh, (min(lons) - margin, min(lats) - margin,
                        max(lons) + margin, max(lats) + margin))
        for (lat, lon) in args.point:
            z = sampler.elevation_at(lat, lon)
            print("  {:.6f} {:.6f}  z {}".format(
                lat, lon, "None" if z is None else "{:.3f}".format(z)))
    else:
        parser.error("give --lon/--lat-range, --lat/--lon-range, or --point")
    return 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
