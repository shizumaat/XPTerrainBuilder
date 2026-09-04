"""The planar map + a solved ``z`` -> :class:`GradedSurface` (plan §1
row 7): the ONE product every adapter projects.  Vertex identity is the
map's canonical lat/lon key; ``z`` is quantised ONCE, here, at the
materiality floor's precision (``emit.materiality.elevation_m``)."""
from __future__ import annotations

import hashlib
import json
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap
from ..solve.api import Solution
from .surface import GradedSurface, SurfaceBreakline, SurfaceFace, SurfaceVertex

__all__ = ["graded_surface", "z_decimals"]


def z_decimals(law: Law) -> int:
    """Decimal places of the ONE elevation quantisation."""
    m = law.tables.emit.materiality.elevation_m
    dp = 0
    while dp < 9 and round(m * 10 ** dp) < 1:
        dp += 1
    return dp


def graded_surface(planar: PlanarMap, law: Law, sol: Solution,
                   origin: tuple[float, float], crs: str = "",
                   provenance: _t.Mapping[str, _t.Any] | None = None
                   ) -> GradedSurface:
    """The product; ``z`` rounded once to the materiality precision."""
    dp = z_decimals(law)
    ring_ids = {}
    ring_vertex_ids = planar.ring_vertices
    verts = tuple(SurfaceVertex(vid, v.key, round(sol.z[vid], dp))
                  for vid, v in sorted(planar.vertices.items()))
    faces = []
    for fid, f in sorted(planar.faces.items()):
        ring = tuple(ring_vertex_ids(f.ring))
        holes = tuple(tuple(ring_vertex_ids(h)) for h in f.holes)
        ring_ids[fid] = ring
        faces.append(SurfaceFace(fid, f.role, f.ref, ring, holes, f.side,
                                 f.code_number, f.code_letter))
    bls = tuple(SurfaceBreakline(bid, b.kind, b.ref, tuple(b.vertices(planar)))
                for bid, b in sorted(planar.breaklines.items()))
    prov = dict(provenance or {})
    prov.setdefault("solver", {"backend": sol.backend.value, "status": sol.status.value,
                               "residual_m": None if sol.residual is None
                               else round(sol.residual.max_m, 6)})
    prov.setdefault("planar_sha256", hashlib.sha256(json.dumps(
        [[vid, v.key] for vid, v in sorted(planar.vertices.items())]
    ).encode()).hexdigest()[:16])
    return GradedSurface(planar.icao, law.ruleset_key, origin, crs,
                         law.tables.emit.identity.coordinate_dp, verts,
                         tuple(faces), bls, prov)
