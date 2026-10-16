"""The 3D preview's ground (spec patch-editor-20261015 §5, A9 and the
"Ruled after L6a" (2)–(3); the Mac app's ``PatchTerrainGrid``,
``PatchTerrainCut``, ``PatchTerrainSurface``, ``PatchPreviewSpace``,
``PatchTerrainMesh`` and ``TerrainPreviewModel.terrainRequest/chipText``).

Pure numpy, no widgets.  Preview SPACE is the document's metric frame with
x = east, y = metres above ``base``, z = SOUTH (Qt Quick 3D is right-handed
and y-up, so north is −z).  Vertical exaggeration is the scene's scale,
never baked in here.

The ``terrain_sample`` grid (row 0 = south edge, row-major) is drawn as two
triangles per cell; the patch is CUT OUT of it: a grid triangle whose
centroid lies inside a patch surface (even-odd over its outer ring and
holes) is dropped.
"""
from __future__ import annotations

import base64
import dataclasses as _dc
import math
import typing as _t

import numpy as np

from O4_Qt_Pack_Outlines import METRES_PER_DEG_LAT, request_bbox
from O4_Qt_Preview3D_Shapes import LocalFrame, PreviewShape

__all__ = ["SPACING_M", "MAX_SAMPLES", "terrain_request", "TerrainGrid", "TerrainSurface",
           "PreviewSpace", "covered_triangles", "kept_indices", "terrain_vertices",
           "vertex_normals", "chip_text"]

#: A9: the terrain reaches 500 m past the patch bbox (``request_bbox``) …
SPACING_M = 5.0
#: … and one ``terrain_sample`` carries at most this many points (§2).
MAX_SAMPLES = 4_000_000


def terrain_request(nodes: _t.Iterable[tuple]) -> tuple[list[float], float] | None:
    """A9's box (the patch bbox + 500 m, the same box ``pack_objects`` is
    asked for) and the spacing: 5 m unless that is over the engine's cap,
    then the finest 0.5 m step under it (§5 ruling (2))."""
    box = request_bbox(nodes)
    if box is None:
        return None
    s, w, n, e = box
    m_lon = METRES_PER_DEG_LAT * max(math.cos(math.radians((s + n) / 2)), 1e-6)
    width, height = (e - w) * m_lon, (n - s) * METRES_PER_DEG_LAT
    spacing = SPACING_M
    while (width / spacing + 2) * (height / spacing + 2) > MAX_SAMPLES:
        spacing += 0.5
    return box, spacing


@_dc.dataclass(frozen=True)
class TerrainGrid:
    """The grid in degrees: vertex (r, c) is at (south + r·dlat,
    west + c·dlon) and has index r·cols + c."""

    rows: int
    cols: int
    south: float
    west: float
    dlat: float
    dlon: float

    #: (row, column) offsets of the k = 0 and k = 1 centroids in a cell.
    CENTROIDS: _t.ClassVar = ((1 / 3, 2 / 3), (2 / 3, 1 / 3))

    @property
    def triangle_count(self) -> int:
        return 2 * (self.rows - 1) * (self.cols - 1) if self.rows > 1 and self.cols > 1 else 0

    def triangles(self) -> np.ndarray:
        """``(T, 3)`` vertex indices: triangle ``2·(r·(cols−1) + c) + k`` of
        cell (r, c) is (r,c) (r,c+1) (r+1,c+1) for k = 0 and (r,c)
        (r+1,c+1) (r+1,c) for k = 1 — counter-clockwise from above."""
        r, c = np.meshgrid(np.arange(self.rows - 1), np.arange(self.cols - 1), indexing="ij")
        v00 = (r * self.cols + c).ravel().astype(np.uint32)
        v01, v10 = v00 + 1, v00 + self.cols
        v11 = v10 + 1
        out = np.empty((v00.size, 2, 3), dtype=np.uint32)
        out[:, 0] = np.column_stack([v00, v01, v11])
        out[:, 1] = np.column_stack([v00, v11, v10])
        return out.reshape(-1, 3)

    def centroid(self, t: int) -> tuple[float, float]:
        """(lat, lon) of triangle t's centroid."""
        cell, k = divmod(t, 2)
        r, c = divmod(cell, self.cols - 1)
        fr, fc = self.CENTROIDS[k]
        return self.south + (r + fr) * self.dlat, self.west + (c + fc) * self.dlon

    @classmethod
    def of(cls, sample: _t.Mapping) -> "TerrainGrid":
        return cls(int(sample["rows"]), int(sample["cols"]), float(sample["bbox"][0]),
                   float(sample["bbox"][1]), float(sample["dlat"]), float(sample["dlon"]))

    def lat_lon(self) -> tuple[np.ndarray, np.ndarray]:
        """Every vertex's (lat, lon), row-major."""
        lat = self.south + np.arange(self.rows) * self.dlat
        lon = self.west + np.arange(self.cols) * self.dlon
        la, lo = np.meshgrid(lat, lon, indexing="ij")
        return la.ravel(), lo.ravel()


class TerrainSurface:
    """The grid with its elevations, NaN filled with the mean, for the
    ground under a node without elevation (§4 "elevation from the mesh")."""

    def __init__(self, sample: _t.Mapping):
        self.grid = TerrainGrid.of(sample)
        z = np.frombuffer(base64.b64decode(sample["elev_f32_b64"]), dtype="<f4").astype(np.float32)
        finite = np.isfinite(z)
        fill = float(z[finite].mean()) if finite.any() else 0.0
        self.elevations = np.where(finite, z, np.float32(fill))
        self.min_elevation = float(z[finite].min()) if finite.any() else 0.0
        self.sample = sample

    def elevation(self, lat, lon):
        """Bilinear elevation, clamped to the grid; arrays welcome."""
        g = self.grid
        fr = np.clip((np.asarray(lat, float) - g.south) / g.dlat, 0, g.rows - 1)
        fc = np.clip((np.asarray(lon, float) - g.west) / g.dlon, 0, g.cols - 1)
        r0 = np.minimum(fr.astype(int), g.rows - 2)
        c0 = np.minimum(fc.astype(int), g.cols - 2)
        tr, tc = fr - r0, fc - c0
        z = self.elevations

        def at(r, c):
            return z[r * g.cols + c].astype(np.float64)
        return ((1 - tr) * ((1 - tc) * at(r0, c0) + tc * at(r0, c0 + 1))
                + tr * ((1 - tc) * at(r0 + 1, c0) + tc * at(r0 + 1, c0 + 1)))


@_dc.dataclass
class PreviewSpace:
    """Where the preview's origin sits: the document frame and the
    elevation that maps to y = 0."""

    frame: LocalFrame
    base: float
    terrain: TerrainSurface | None = None

    def position(self, lat, lon, elevation) -> np.ndarray:
        """``(N, 3)`` float32 preview positions (x east, y up, z south)."""
        x, y = self.frame.metres(lat, lon)
        x, y = np.atleast_1d(x), np.atleast_1d(y)
        up = np.broadcast_to(np.asarray(elevation, float) - self.base, x.shape)
        return np.column_stack([x, up, -y]).astype(np.float32)

    def ground(self, lat, lon):
        """The terrain under a point, or ``base`` before the terrain arrives."""
        if self.terrain is None:
            return np.full(np.shape(lat), self.base, dtype=float)
        return self.terrain.elevation(lat, lon)

    def ground_y(self, x: float, z: float) -> float | None:
        """The terrain's y (metres above ``base``, before exaggeration)
        under a preview (x, z), or None before the terrain — the 3D
        camera's floor."""
        if self.terrain is None:
            return None
        lat, lon = self.frame.lat_lon(x, -z)
        return float(self.terrain.elevation(lat, lon)) - self.base

    def node_positions(self, nodes: _t.Sequence[tuple]) -> np.ndarray:
        """Node tuples ``(id, lat, lon, alt|None)``: a node without elevation
        stands on the terrain."""
        if not nodes:
            return np.zeros((0, 3), dtype=np.float32)
        lat = np.array([n[1] for n in nodes], float)
        lon = np.array([n[2] for n in nodes], float)
        alt = np.array([np.nan if n[3] is None else n[3] for n in nodes], float)
        missing = np.isnan(alt)
        if missing.any():
            alt[missing] = self.ground(lat[missing], lon[missing])
        return self.position(lat, lon, alt)


def covered_triangles(grid: TerrainGrid, shapes: _t.Iterable[PreviewShape],
                      nodes: _t.Mapping[int, tuple]) -> np.ndarray:
    """``covered[t]``: grid triangle t's centroid lies inside a patch
    surface (even-odd over its outer ring and holes).  One scanline per
    centroid row the surface spans."""
    covered = np.zeros(grid.triangle_count, dtype=bool)
    if covered.size == 0:
        return covered
    stride = 2 * (grid.cols - 1)
    for shape in shapes:
        rings = []
        for ring in (shape.outer, *shape.holes):
            pts = np.array([(nodes[i][1], nodes[i][2]) for i in ring if i in nodes], float)
            if len(pts) >= 3:
                rings.append(pts)
        if not rings or len(rings[0]) < 3 or len(rings[0]) != len(shape.outer):
            continue
        a = np.vstack(rings)                                   # edge starts (lat, lon)
        b = np.vstack([np.roll(r, -1, axis=0) for r in rings])  # edge ends
        lo_lat, hi_lat = rings[0][:, 0].min(), rings[0][:, 0].max()
        for k, (fr, fc) in enumerate(grid.CENTROIDS):
            r0 = max(0, math.ceil((lo_lat - grid.south) / grid.dlat - fr))
            r1 = min(grid.rows - 2, math.floor((hi_lat - grid.south) / grid.dlat - fr))
            if r0 > r1:
                continue
            ys = grid.south + (np.arange(r0, r1 + 1) + fr) * grid.dlat
            straddle = (a[:, 0][None, :] > ys[:, None]) != (b[:, 0][None, :] > ys[:, None])
            with np.errstate(invalid="ignore", divide="ignore"):
                xs = a[:, 1] + (ys[:, None] - a[:, 0]) * (b[:, 1] - a[:, 1]) / (b[:, 0] - a[:, 0])
            for row, (hit, x) in enumerate(zip(straddle, xs)):
                cross = np.sort(x[hit])
                base = (r0 + row) * stride + k
                for s in range(0, len(cross) - 1, 2):
                    c0 = max(0, math.ceil((cross[s] - grid.west) / grid.dlon - fc))
                    c1 = min(grid.cols - 2, math.ceil((cross[s + 1] - grid.west) / grid.dlon - fc) - 1)
                    if c0 <= c1:
                        covered[base + 2 * c0: base + 2 * c1 + 1: 2] = True
    return covered


def kept_indices(grid: TerrainGrid, covered: np.ndarray) -> np.ndarray:
    """The index buffer (uint32) of the triangles NOT covered."""
    return grid.triangles()[~covered].ravel()


def vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Area-weighted vertex normals of an indexed triangle list (y up)."""
    n = np.zeros_like(positions, dtype=np.float32)
    if len(indices) >= 3:
        t = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
        p = positions.astype(np.float32)
        f = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
        for k in range(3):
            np.add.at(n, t[:, k], f)
    length = np.linalg.norm(n, axis=1)
    out = np.tile(np.float32([0, 1, 0]), (len(n), 1))
    ok = length > 0
    out[ok] = n[ok] / length[ok, None]
    return out


def terrain_vertices(surface: TerrainSurface, space: PreviewSpace) -> tuple[np.ndarray, np.ndarray]:
    """The grid's positions and smooth normals (central differences)."""
    g = surface.grid
    lat, lon = g.lat_lon()
    p = space.position(lat, lon, surface.elevations.astype(np.float64)).reshape(g.rows, g.cols, 3)
    east = p[:, np.minimum(np.arange(g.cols) + 1, g.cols - 1)] - p[:, np.maximum(np.arange(g.cols) - 1, 0)]
    north = p[np.minimum(np.arange(g.rows) + 1, g.rows - 1)] - p[np.maximum(np.arange(g.rows) - 1, 0)]
    n = np.cross(east, north).reshape(-1, 3)        # east × north (−z) points up
    length = np.linalg.norm(n, axis=1)
    n = np.where(length[:, None] > 0, n / np.maximum(length, 1e-12)[:, None], np.float32([0, 1, 0]))
    return p.reshape(-1, 3), n.astype(np.float32)


def chip_text(sample: _t.Mapping) -> str:
    """"Preview · 3.0 km × 2.2 km · DEM of the last build · 5 m grid" (or
    "DEM base + airport inset" / "DEM base only")."""
    s, w, n, e = (float(v) for v in sample["bbox"])
    width = (e - w) * METRES_PER_DEG_LAT * math.cos(math.radians((s + n) / 2))
    height = (n - s) * METRES_PER_DEG_LAT
    sources = sample.get("sources") or {}
    dem = ("DEM of the last build" if sources.get("frame") == "production"
           else "DEM base + airport inset" if sources.get("inset") else "DEM base only")
    spacing = float(sample["spacing_m"])
    spacing_text = str(int(spacing)) if spacing == int(spacing) else "%.1f" % spacing
    return "Preview · %.1f km × %.1f km · %s · %s m grid" % (width / 1000, height / 1000, dem,
                                                             spacing_text)
