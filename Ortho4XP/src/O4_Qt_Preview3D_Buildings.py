"""Where the pack's buildings stand in the 3D preview (spec
patch-editor-20261015 §5 BUILDINGS and its "Ruled after 6b"/"after the
massing measurement"; the Mac app's ``PatchSurfaceLocator``,
``PatchBuildingPose`` and ``PatchBuildingSeats``).

Each placement stands at ``preview_surface(anchor) + agl + y``, turned by
its heading — X-Plane's own drape at the anchor, so ground lowered under a
building leaves it floating as it would in the sim (re-seating is off for
an edited patch).  The preview surface is the patch surface where the
anchor lies on a patch shape, else the terrain grid; in "Last build" it is
the last build's mesh.  Vertical exaggeration lifts the SEAT only:
buildings keep their true height.

Pure numpy, no widgets.
"""
from __future__ import annotations

import base64
import dataclasses as _dc
import math
import typing as _t

import numpy as np

from O4_Qt_Preview3D_Terrain import PreviewSpace, vertex_normals

__all__ = ["SurfaceLocator", "Pose", "BuildingSeats", "model_mesh", "facade_mesh",
           "instance_table"]


def _barycentric(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray):
    """Weights ``(T, 3)`` of point ``p`` in each triangle, and which hold it."""
    v0, v1, v2 = b - a, c - a, p - a
    d = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    ok = np.abs(d) > 1e-12
    d = np.where(ok, d, 1.0)
    u = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / d
    v = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / d
    eps = -1e-9
    inside = ok & (u >= eps) & (v >= eps) & (u + v <= 1 - eps)
    return np.column_stack([1 - u - v, u, v]), inside


@_dc.dataclass
class _Entry:
    way: int | None                 # the patch shape, or None for a mesh cell
    lo: np.ndarray
    hi: np.ndarray
    corners: np.ndarray             # (T, 3, 2) metric corners
    z: np.ndarray                   # (T, 3) elevations, NaN = the terrain's


class SurfaceLocator:
    """The preview surface under a point: which patch shape (if any) and
    its elevation there."""

    def __init__(self, frame, entries: list[_Entry]):
        self.frame = frame
        self.entries = entries
        self._lo = np.array([e.lo for e in entries], float).reshape(-1, 2)
        self._hi = np.array([e.hi for e in entries], float).reshape(-1, 2)

    def _boxes_at(self, lat: float, lon: float) -> tuple[np.ndarray, np.ndarray]:
        x, y = self.frame.metres(lat, lon)
        p = np.array([float(x), float(y)])
        return p, np.nonzero(((self._lo <= p) & (self._hi >= p)).all(axis=1))[0]

    @classmethod
    def of_shapes(cls, meshes: _t.Mapping, nodes: _t.Mapping[int, tuple], frame) -> "SurfaceLocator":
        """The patch surfaces (each shape's triangles at its node elevations)."""
        out = []
        for way in sorted(meshes):
            m = meshes[way]
            if not len(m.indices) or any(i not in nodes for i in m.vertex_ids):
                continue
            rows = [nodes[i] for i in m.vertex_ids]
            x, y = frame.metres([n[1] for n in rows], [n[2] for n in rows])
            xy = np.column_stack([x, y])
            z = np.array([np.nan if n[3] is None else n[3] for n in rows], float)
            t = m.indices.reshape(-1, 3).astype(np.int64)
            out.append(_Entry(way, xy.min(axis=0), xy.max(axis=0), xy[t], z[t]))
        return cls(frame, out)

    @classmethod
    def of_mesh(cls, vertices: np.ndarray, triangles: np.ndarray, frame,
                cells: int = 64) -> "SurfaceLocator":
        """The last build's mesh (lon, lat, elev rows; triangle rows),
        bucketed into a grid of cells by triangle centre."""
        if not len(vertices) or not len(triangles):
            return cls(frame, [])
        x, y = frame.metres(vertices[:, 1], vertices[:, 0])
        xy = np.column_stack([x, y])
        t = triangles.astype(np.int64)
        corners, z = xy[t], vertices[:, 2][t]
        centre = corners.mean(axis=1)
        lo, hi = xy.min(axis=0), xy.max(axis=0)
        size = np.maximum((hi - lo) / cells, 1e-6)
        cell = np.clip(((centre - lo) / size).astype(int), 0, cells - 1)
        key = cell[:, 1] * cells + cell[:, 0]
        out = []
        for k in np.unique(key):
            sel = key == k
            c = corners[sel]
            out.append(_Entry(None, c.reshape(-1, 2).min(axis=0), c.reshape(-1, 2).max(axis=0),
                              c, z[sel]))
        return cls(frame, out)

    def surface(self, lat: float, lon: float, space: PreviewSpace) -> tuple[int | None, float]:
        """The shape under (lat, lon) and the surface elevation there; off
        the patch, the terrain's (or ``space.base`` before it arrives)."""
        p, hits = self._boxes_at(lat, lon)
        ground = float(space.ground(np.array([lat]), np.array([lon]))[0])
        for k in hits:
            e = self.entries[k]
            w, inside = _barycentric(p, e.corners[:, 0], e.corners[:, 1], e.corners[:, 2])
            hit = np.nonzero(inside)[0]
            if len(hit):
                t = hit[0]
                z = np.where(np.isnan(e.z[t]), ground, e.z[t])
                return e.way, float(w[t] @ z)
        return None, ground

    def near_any(self, ways: _t.Collection[int], lat: float, lon: float) -> bool:
        """Whether (lat, lon) lies in the bounding box of one of ``ways``."""
        _p, hits = self._boxes_at(lat, lon)
        return any(self.entries[k].way in ways for k in hits)


@_dc.dataclass(frozen=True)
class Pose:
    """One placement's pose in preview space (unexaggerated metres): the
    model's authored frame (x east at heading 0, y up, z south) turned by
    −heading about y, because X-Plane's heading is clockwise from north
    seen from above."""

    x: float
    y: float
    z: float
    yaw: float                      # radians about +y

    @classmethod
    def seat(cls, lat: float, lon: float, heading_deg: float, agl_m: float,
             surface_z: float, space: PreviewSpace) -> "Pose":
        p = space.position(lat, lon, surface_z + agl_m)[0]
        return cls(float(p[0]), float(p[1]), float(p[2]), -math.radians(heading_deg))

    def place(self, authored: _t.Sequence[float], exaggeration: float = 1.0) -> tuple:
        """An authored point in preview space; the exaggeration lifts the
        seat only."""
        ax, ay, az = authored
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return (self.x + c * ax + s * az, self.y * exaggeration + ay, self.z - s * ax + c * az)


def instance_table(poses: _t.Sequence[Pose], exaggeration: float) -> np.ndarray:
    """Qt Quick 3D instance rows (``InstanceTableEntry``: a 3×4 transform,
    colour, custom data — 20 float32 each) for these poses, as
    :meth:`Pose.place` places a point."""
    t = np.zeros((len(poses), 20), dtype=np.float32)
    for i, p in enumerate(poses):
        c, s = math.cos(p.yaw), math.sin(p.yaw)
        t[i, 0:4] = (c, 0, s, p.x)
        t[i, 4:8] = (0, 1, 0, p.y * exaggeration)
        t[i, 8:12] = (-s, 0, c, p.z)
        t[i, 12:16] = 1.0
    return t


class BuildingSeats:
    """The seats of every placement, and the re-seat after an edit: only
    placements whose anchor lay on a changed shape, or now falls within one."""

    def __init__(self, placements: _t.Sequence[_t.Mapping], locator: SurfaceLocator,
                 space: PreviewSpace):
        self.placements = list(placements)
        self.poses: list[Pose] = []
        self.shape_of: list[int | None] = []
        for p in self.placements:
            way, z = locator.surface(float(p["lat"]), float(p["lon"]), space)
            self.shape_of.append(way)
            self.poses.append(self._pose(p, z, space))

    @staticmethod
    def _pose(p: _t.Mapping, surface_z: float, space: PreviewSpace) -> Pose:
        return Pose.seat(float(p["lat"]), float(p["lon"]), float(p.get("heading_deg") or 0.0),
                         float(p.get("agl_m") or 0.0), surface_z, space)

    def _reseat(self, i: int, locator: SurfaceLocator, space: PreviewSpace) -> bool:
        p = self.placements[i]
        way, z = locator.surface(float(p["lat"]), float(p["lon"]), space)
        self.shape_of[i] = way
        pose = self._pose(p, z, space)
        if pose == self.poses[i]:
            return False
        self.poses[i] = pose
        return True

    def reseat_all(self, locator: SurfaceLocator, space: PreviewSpace) -> list[int]:
        """Seat every placement on another surface (Preview ↔ Last build);
        the indices moved."""
        return [i for i in range(len(self.placements)) if self._reseat(i, locator, space)]

    def reseat(self, changed: _t.Collection[int], locator: SurfaceLocator,
               space: PreviewSpace) -> list[int]:
        """Re-seat after ``changed`` shapes changed; the indices moved."""
        if not changed:
            return []
        moved = []
        for i, p in enumerate(self.placements):
            if self.shape_of[i] in changed or locator.near_any(changed, float(p["lat"]),
                                                               float(p["lon"])):
                if self._reseat(i, locator, space):
                    moved.append(i)
        return moved


def model_mesh(model: _t.Mapping) -> tuple[np.ndarray, np.ndarray]:
    """A model's grey massing (``pack_objects`` hull triangles) flat-shaded:
    ``(positions, normals)``, three un-shared vertices per triangle."""
    v = np.frombuffer(base64.b64decode(model["vertices_f32_b64"]), dtype="<f4").reshape(-1, 3)
    t = np.frombuffer(base64.b64decode(model["triangles_u32_b64"]), dtype="<u4")
    t = t[t < len(v)][: len(t) // 3 * 3] if len(v) else t[:0]
    p = v[t].astype(np.float32).reshape(-1, 3)
    return p, vertex_normals(p, np.arange(len(p), dtype=np.uint32))


def facade_mesh(ring_xz: np.ndarray, height: float, base_y: float) -> np.ndarray:
    """A facade as a prism over its ring (preview x, z): walls from
    ``base_y`` to ``base_y + height`` and a flat roof; positions only, three
    per triangle."""
    from O4_Qt_Preview3D_Shapes import triangulate
    out = []
    n = len(ring_xz)
    for i in range(n):
        (ax, az), (bx, bz) = ring_xz[i], ring_xz[(i + 1) % n]
        q = [(ax, base_y, az), (bx, base_y, bz), (bx, base_y + height, bz), (ax, base_y + height, az)]
        out += [q[0], q[1], q[2], q[0], q[2], q[3]]
    xy = {i: (float(x), float(-z)) for i, (x, z) in enumerate(ring_xz)}
    for tri in triangulate(xy, list(range(n))):
        out += [(ring_xz[i][0], base_y + height, ring_xz[i][1]) for i in tri]
    return np.asarray(out, dtype=np.float32).reshape(-1, 3)
