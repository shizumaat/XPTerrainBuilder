"""Grey massing of a pack's objects for the 3D preview (patch-editor spec
§5, ruled after 6b's size stop and after the massing measurement).

A model is sent as the CONVEX HULL of each of its solid, non-animated
connected components (``airport/obj8.solid_components`` through
``ResourceCache.components`` — already position-welded to 1 mm, so no
second weld here). A component under :data:`MIN_COMPONENT_M` in every
dimension is clutter and is dropped. If a whole reply would exceed
:data:`MAX_REPLY_BYTES`, the smallest remaining components go first until
it fits (:func:`fit_to_cap`).
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np

__all__ = ["MIN_COMPONENT_M", "MAX_REPLY_BYTES", "Hull", "component_hull",
           "model_hulls", "fit_to_cap", "pack_model", "plan_hull"]

#: A component under this size in EVERY dimension is not sent.
MIN_COMPONENT_M = 2.0
#: The reply cap (spec §5): over it, the smallest components are dropped.
MAX_REPLY_BYTES = 50_000_000


@_dc.dataclass(frozen=True)
class Hull:
    """One component's hull in the model's authored frame."""

    vertices: np.ndarray          # (k, 3) float64
    triangles: np.ndarray         # (m, 3) int, wound outward
    size_m: float                 # the component's largest extent

    @property
    def wire_bytes(self) -> int:
        """Its share of the reply: float32 + uint32 triples, base64."""
        return (self.vertices.shape[0] + self.triangles.shape[0]) * 12 * 4 // 3


def component_hull(points: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """The 3-D convex hull of a point cloud: ``(vertices, triangles)``
    wound outward, or ``None`` when no hull exists. A flat component (a
    wall plate) is joggled into a thin hull."""
    from scipy.spatial import ConvexHull, QhullError
    pts = np.unique(np.asarray(points, dtype=np.float64), axis=0)
    if pts.shape[0] < 4:
        return None
    try:
        hull = ConvexHull(pts)
    except QhullError:
        try:
            hull = ConvexHull(pts, qhull_options="QJ")
        except QhullError:
            return None
    used, inverse = np.unique(hull.simplices.reshape(-1), return_inverse=True)
    verts = pts[used]
    tris = inverse.reshape(-1, 3)
    centre = verts.mean(axis=0)
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    inward = np.einsum("ij,ij->i", np.cross(b - a, c - a), a - centre) < 0
    tris[inward] = tris[inward][:, [0, 2, 1]]
    return verts, tris


def model_hulls(cache, path: str) -> tuple[list[Hull], int] | None:
    """``(hulls, components dropped as clutter)`` of one resource, or
    ``None`` when it cannot be read."""
    geom = cache.geometry(path)
    if geom is None:
        return None
    hulls: list[Hull] = []
    dropped = 0
    for comp in cache.components(path):
        if comp.animated:
            continue
        pts = geom.vertices[comp.tris.reshape(-1)]
        extent = pts.max(axis=0) - pts.min(axis=0)
        if (extent < MIN_COMPONENT_M).all():
            dropped += 1
            continue
        hull = component_hull(pts)
        if hull is None:
            dropped += 1
            continue
        hulls.append(Hull(hull[0], hull[1], float(extent.max())))
    return hulls, dropped


def fit_to_cap(hulls_by_model: dict[str, list[Hull]], other_bytes: int,
               cap: int = MAX_REPLY_BYTES) -> int:
    """Drop the smallest components, across all models, until the reply
    fits ``cap``; returns how many were dropped (the lists are edited in
    place)."""
    total = other_bytes + sum(h.wire_bytes for hs in hulls_by_model.values() for h in hs)
    if total <= cap:
        return 0
    ranked = sorted(((h.size_m, key, i) for key, hs in hulls_by_model.items()
                     for i, h in enumerate(hs)))
    gone: dict[str, set[int]] = {}
    n = 0
    for _size, key, i in ranked:
        if total <= cap:
            break
        total -= hulls_by_model[key][i].wire_bytes
        gone.setdefault(key, set()).add(i)
        n += 1
    for key, idx in gone.items():
        hulls_by_model[key] = [h for i, h in enumerate(hulls_by_model[key]) if i not in idx]
    return n


def pack_model(hulls: list[Hull]) -> tuple[np.ndarray, np.ndarray]:
    """One model's hulls as a single vertex/triangle list (float32, uint32)."""
    verts, tris, base = [], [], 0
    for h in hulls:
        verts.append(h.vertices)
        tris.append(h.triangles + base)
        base += h.vertices.shape[0]
    return (np.concatenate(verts).astype(np.float32),
            np.concatenate(tris).astype(np.uint32))


def plan_hull(hulls: list[Hull]) -> np.ndarray:
    """The model's PLAN OUTLINE (issue #797): the 2-D convex hull of every
    component hull's vertices as authored ``(x, z)`` pairs (x east, z south
    at heading 0), float32, counter-clockwise; empty when the plan has no
    area.  What the map's footprints draw — the same outline the clients
    took from the full massing (``PackFootprints.planHull``), sent as a
    few points instead of every triangle."""
    from scipy.spatial import ConvexHull, QhullError
    if not hulls:
        return np.zeros((0, 2), np.float32)
    pts = np.unique(np.concatenate([h.vertices[:, [0, 2]] for h in hulls]), axis=0)
    if pts.shape[0] < 3:
        return np.zeros((0, 2), np.float32)
    try:
        ring = pts[ConvexHull(pts).vertices]
    except QhullError:                  # collinear: no area, no outline
        return np.zeros((0, 2), np.float32)
    return ring.astype(np.float32)
