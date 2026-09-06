"""The planar map + a solved ``z`` -> :class:`GradedSurface` (plan §1
row 7): the ONE product every adapter projects.  Vertex identity is the
map's canonical lat/lon key; ``z`` is quantised ONCE, here, at the
materiality floor's precision (``emit.materiality.elevation_m``)."""
from __future__ import annotations

import hashlib
import json
import typing as _t

from ..law import Law
from ..law.tables import is_structure_role
from ..model.planar import PlanarMap
from ..solve.api import Solution
from .surface import GradedSurface, SurfaceBreakline, SurfaceFace, SurfaceVertex

__all__ = ["graded_surface", "z_decimals", "RIM_KIND", "VOID_ROLE"]

#: The VOID between a structure's floor and its at-grade rim (RULINGS
#: 2026-09-06b (1); ``[cutout] emit_wall_band = false``): a planar face of
#: this role is never a surface — its exterior ring is the RIM, carried as
#: a breakline of kind ``RIM_KIND`` (closed: the first vertex repeated) and
#: emitted as a constrained ring; the mesh triangulates the wall inside.
VOID_ROLE = "retaining_wall"
RIM_KIND = "structure_rim"
#: The floor roles whose vertices a void's ring may run along (a U void's
#: exterior includes the ramp's own edges — those are the ramp's, not rim).
FLOOR_ROLES = ("tunnel_ramp", "tunnel_trench")


def rim_runs(planar: PlanarMap, face) -> list[tuple[int, ...]]:
    """The RIM of a void face: its exterior ring with the floor's own
    edges (both endpoints on a ``tunnel_ramp`` / ``tunnel_trench`` face)
    removed — one closed run (the first vertex repeated) when nothing was
    removed (an O, a basin), else the open chain(s) from the floor's top
    corner round the rim and back (a U: the ramp climbs out of it)."""
    ring = list(planar.ring_vertices(face.ring))
    n = len(ring)
    if n < 3:
        return []

    def on_floor(v: int) -> bool:
        return any(planar.faces[f].role in FLOOR_ROLES for f in planar.vertices[v].incident_faces)

    keep = [not (on_floor(ring[i]) and on_floor(ring[(i + 1) % n])) for i in range(n)]
    if all(keep):
        return [tuple(ring) + (ring[0],)]
    if not any(keep):
        return []
    # start at a dropped edge so every run is contiguous
    start = next(i for i in range(n) if not keep[i])
    runs: list[list[int]] = []
    cur: list[int] = []
    for k in range(1, n + 1):
        i = (start + k) % n
        if keep[i]:
            if not cur:
                cur = [ring[i]]
            cur.append(ring[(i + 1) % n])
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [tuple(r) for r in runs if len(r) >= 2]


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
    rims = []
    for fid, f in sorted(planar.faces.items()):
        ring = tuple(ring_vertex_ids(f.ring))
        holes = tuple(tuple(ring_vertex_ids(h)) for h in f.holes)
        ring_ids[fid] = ring
        if f.role == VOID_ROLE and is_structure_role(law, f.role):
            # the void is not a surface: its rim is the product
            for run in rim_runs(planar, f):
                rims.append((fid, f.ref, run))
            continue
        faces.append(SurfaceFace(fid, f.role, f.ref, ring, holes, f.side,
                                 f.code_number, f.code_letter))
    bls = [SurfaceBreakline(bid, b.kind, b.ref, tuple(b.vertices(planar)))
           for bid, b in sorted(planar.breaklines.items())]
    nb = max([b.id for b in bls], default=-1) + 1
    for k, (fid, ref, ring) in enumerate(rims):
        bls.append(SurfaceBreakline(nb + k, RIM_KIND, f"{ref}@{fid}", ring))
    bls = tuple(bls)
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
