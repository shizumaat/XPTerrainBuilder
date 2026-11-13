"""THE PATCH AS A SURFACE (#1971; spec ``interchange-levels-v2-20261113.md``
§8.2): what an emitted ``<ICAO>_auto.patch.osm`` states the ground is, as a
sampler with the drawn mesh's own interface (``elevation_at_or_none(lat,
lon)``), so ``tools/drawn_check.check_stack`` runs the SAME D rows on the
replay's patch (PREDICTED) as on the built tile (DRAWN).

* A FACE is every closed way of one ``ref`` (the emitter ships a hole as
  its own closed way under the same ref, so containment is EVEN-ODD, as
  ``tools/osm_site.py --contains`` decides it); the void band
  (``o4_feature=structure_rim``) is a face, the open breaklines are not.
* A point a face covers reads that face's OWN nodes, linearly: the face is
  triangulated on its ring vertices (constrained Delaunay, no new point) and
  the point takes the plane of the triangle it lies in.
* A point no face covers but within ``standoff`` of one (a stand-off gap
  the emitter leaves between two faces) reads the faces round it, inverse
  distance over their nearest edge points: the mesh triangulates across
  such a gap from the nodes on both sides, never from the DEM under it.
* A point further from every face reads the build's DEM (the inset the
  patch header names, bilinear) and is UNCOVERED; :meth:`PatchFaces.gap_m`
  is its distance to the nearest face (the coverage bar's stand-off).

Parsing is the harness library's (``check_grade._parse_osm``).  Only the
faces within ``radius_m`` of the centre are triangulated.
"""
from __future__ import annotations

import math
import os
import re
import sys
import urllib.parse
from pathlib import Path

import numpy
import shapely.ops

sys.path.insert(0, str(Path(__file__).resolve().parent))

M_PER_DEG = 111320.0
#: the feature rings that ARE faces of the drawn patch (the void band)
FACE_FEATURES = ("structure_rim",)

__all__ = ["PatchFaces", "inset_path"]


def inset_path(patch_path) -> "str | None":
    """The airport inset GeoTIFF the patch header's ``o4_dem`` names, found
    under this tree's ``Elevation_data`` when the named tree is gone."""
    with open(patch_path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(4096)
    m = re.search(r"o4_dem='[^']*insets:([^|']+)", head)
    if not m:
        return None
    p = urllib.parse.unquote(m.group(1))
    if os.path.isfile(p):
        return p
    rel = p.split("Elevation_data/", 1)[-1]
    here = Path(__file__).resolve().parents[1] / "Elevation_data" / rel
    return str(here) if here.is_file() else None


class _Dem:
    """Bilinear read of one GeoTIFF: ``(lat, lon) -> metres`` (nan off it)."""

    def __init__(self, path: str) -> None:
        from osgeo import gdal
        gdal.UseExceptions()
        ds = gdal.Open(path)
        self.a = ds.GetRasterBand(1).ReadAsArray().astype(float)
        nd = ds.GetRasterBand(1).GetNoDataValue()
        if nd is not None:
            self.a[self.a == nd] = numpy.nan
        self.g = ds.GetGeoTransform()

    def __call__(self, lat: float, lon: float) -> float:
        g = self.g
        c = (lon - g[0]) / g[1] - 0.5
        r = (lat - g[3]) / g[5] - 0.5
        c0, r0 = int(math.floor(c)), int(math.floor(r))
        if not (0 <= r0 < self.a.shape[0] - 1 and 0 <= c0 < self.a.shape[1] - 1):
            return float("nan")
        fc, fr = c - c0, r - r0
        q = self.a[r0:r0 + 2, c0:c0 + 2]
        return float(q[0, 0] * (1 - fc) * (1 - fr) + q[0, 1] * fc * (1 - fr)
                     + q[1, 0] * (1 - fc) * fr + q[1, 1] * fc * fr)


def _rings(patch_path, kx: float, lat0: float, lon0: float, radius_m: float) -> dict:
    """``{ref: [(role, (n, 2) local xy, [z per node])]}`` of the closed face
    rings within ``radius_m``."""
    from check_grade import _parse_osm
    feats: dict = {}
    nodes, ways = _parse_osm(Path(patch_path), feature_out=feats)
    ways = list(ways) + [w for f in FACE_FEATURES for w in feats.get(f, [])]
    groups: dict[str, list] = {}
    for w in ways:
        ids = [n for n in w.nids if n in nodes]
        if len(ids) < 4 or ids[0] != ids[-1]:
            continue
        ll = numpy.array([nodes[n] for n in ids], float)
        xy = numpy.stack([(ll[:, 1] - lon0) * kx, (ll[:, 0] - lat0) * M_PER_DEG], axis=-1)
        if numpy.hypot(xy[:, 0], xy[:, 1]).min() > radius_m:
            continue
        groups.setdefault(w.ref or f"#{w.wid}", []).append(
            (w.role or w.tags.get("o4_feature", ""), xy, list(w.elevs)))
    return groups


class PatchFaces:
    """The patch's faces about ``centre`` (lat, lon) within ``radius_m``
    (module doc).  ``dem``: ``(lat, lon) -> z`` for an uncovered point
    (default: the header's inset)."""

    def __init__(self, patch_path, centre, radius_m: float = 400.0, dem=None,
                 standoff: float = 0.0) -> None:
        import shapely
        self.lat0, self.lon0 = float(centre[0]), float(centre[1])
        self.kx = M_PER_DEG * math.cos(math.radians(self.lat0))
        self.faces: list[tuple[str, str, object]] = []
        tris, tz, owner = [], [], []
        for ref, rings in _rings(patch_path, self.kx, self.lat0, self.lon0, radius_m).items():
            poly, zs = None, {}
            for _role, xy, z in rings:
                p = shapely.make_valid(shapely.Polygon(xy))
                poly = p if poly is None else shapely.symmetric_difference(poly, p)
                for (x, y), e in zip(xy.tolist(), z, strict=False):
                    if e is not None:
                        zs[(round(x, 3), round(y, 3))] = float(e)
            if poly is None or not zs:
                continue
            poly = shapely.make_valid(poly)
            if poly.is_empty or poly.area < 1e-3:
                continue
            k = len(self.faces)
            self.faces.append((rings[0][0], ref, poly))
            for part in shapely.get_parts(poly):
                if part.geom_type != "Polygon":
                    continue
                for t in shapely.get_parts(shapely.constrained_delaunay_triangles(part)):
                    c = numpy.asarray(t.exterior.coords[:3], float)
                    tris.append(c)
                    tz.append([zs.get((round(x, 3), round(y, 3)), None) or self._nearest(zs, x, y)
                               for x, y in c.tolist()])
                    owner.append(k)
        self.tris = numpy.asarray(tris, float).reshape(-1, 3, 2)
        self.tz = numpy.asarray(tz, float).reshape(-1, 3)
        self.owner = numpy.asarray(owner, int)
        self._tree = shapely.STRtree(shapely.polygons(self.tris)) if len(self.tris) else None
        self._ftree = shapely.STRtree([f[2] for f in self.faces]) if self.faces else None
        if dem is None:
            p = inset_path(patch_path)
            dem = _Dem(p) if p else (lambda _la, _lo: float("nan"))
        self.dem = dem
        self.standoff = float(standoff)
        self.uncovered: list[tuple[float, float]] = []

    @staticmethod
    def _nearest(zs: dict, x: float, y: float) -> float:
        k = min(zs, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
        return zs[k]

    def _xy(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self.lon0) * self.kx, (lat - self.lat0) * M_PER_DEG

    def at(self, lat: float, lon: float) -> "tuple[float, str, str] | None":
        """``(z, role, ref)`` of the face covering the point, or ``None``."""
        import shapely
        if self._tree is None:
            return None
        x, y = self._xy(lat, lon)
        for i in sorted(int(i) for i in self._tree.query(shapely.Point(x, y),
                                                          predicate="intersects")):
            a, b, c = self.tris[i]
            m = numpy.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
            if abs(numpy.linalg.det(m)) < 1e-12:
                continue
            u, v = numpy.linalg.solve(m, [x - a[0], y - a[1]])
            z = self.tz[i]
            role, ref, _p = self.faces[self.owner[i]]
            return float(z[0] + u * (z[1] - z[0]) + v * (z[2] - z[0])), role, ref
        return None

    def gap_m(self, lat: float, lon: float) -> float:
        """Metres from the point to the nearest face (0 on a face)."""
        import shapely
        if self._ftree is None:
            return math.inf
        q = shapely.Point(*self._xy(lat, lon))
        return float(self.faces[int(self._ftree.nearest(q))][2].distance(q))

    def across_gap(self, lat: float, lon: float) -> "float | None":
        """A point in a stand-off gap: inverse distance over the nearest
        edge point of every face within :attr:`standoff`; ``None`` when no
        face is that near."""
        import shapely
        if self._ftree is None or self.standoff <= 0.0:
            return None
        q = shapely.Point(*self._xy(lat, lon))
        num = den = 0.0
        for k in self._ftree.query(q, predicate="dwithin", distance=self.standoff):
            poly = self.faces[int(k)][2]
            p = shapely.ops.nearest_points(poly.boundary, q)[0]
            d = max(p.distance(q), 1e-3)
            z = self._on_edge(int(k), p.x, p.y)
            if z is not None:
                num, den = num + z / d, den + 1.0 / d
        return num / den if den else None

    def _on_edge(self, k: int, x: float, y: float) -> "float | None":
        """Face ``k``'s height AT its boundary point ``(x, y)``: the plane of
        its triangle on that edge, read at the point itself -- linear along
        the edge's two ring vertices, which is what the mesh carries there.
        (A point nudged into the face read a sliver triangle's far vertex:
        KDEN round 2, 0.01 m into a 0.5 m triangle falling 5.5 m to a
        trench's run-out read the walls' top 0.11 m low.)"""
        import shapely
        best = None
        for i in self._tree.query(shapely.Point(x, y).buffer(1e-6), predicate="intersects"):
            i = int(i)
            if self.owner[i] != k:
                continue
            a, b, c = self.tris[i]
            m = numpy.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
            if abs(numpy.linalg.det(m)) < 1e-12:
                continue
            u, v = numpy.linalg.solve(m, [x - a[0], y - a[1]])
            off = -min(u, v, 1.0 - u - v)          # how far outside (<= 0 inside)
            if best is None or off < best[0]:
                z = self.tz[i]
                best = (off, float(z[0] + u * (z[1] - z[0]) + v * (z[2] - z[0])))
        return None if best is None else best[1]

    def elevation_at_or_none(self, lat: float, lon: float) -> "float | None":
        """The drawn-mesh interface: the covering face's plane, else across
        a stand-off gap (:meth:`across_gap`), else the DEM (the point is
        recorded in :attr:`uncovered`)."""
        got = self.at(lat, lon)
        if got is not None:
            return got[0]
        z = self.across_gap(lat, lon)
        if z is not None:
            return z
        self.uncovered.append((lat, lon))
        z = self.dem(lat, lon)
        return None if z != z else z
