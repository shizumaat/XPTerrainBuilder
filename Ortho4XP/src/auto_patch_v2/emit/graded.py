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

__all__ = ["graded_surface", "z_decimals", "RIM_KIND", "VOID_ROLE", "CUT_RINGS_KEY"]

#: The VOID between a structure's floor and its at-grade rim (RULINGS
#: 2026-09-06b (1); ``[cutout] emit_wall_band = false``): a planar face of
#: this role is never a surface — its exterior ring is the RIM, carried as
#: a breakline of kind ``RIM_KIND`` (closed: the first vertex repeated) and
#: emitted as a constrained ring; the mesh triangulates the wall inside.
VOID_ROLE = "retaining_wall"
RIM_KIND = "structure_rim"
#: The floor roles whose vertices a void's ring may run along (a U void's
#: exterior includes the ramp's own edges — those are the ramp's, not rim).
FLOOR_ROLES = ("tunnel_ramp", "door_ramp", "wall_corridor_ramp", "garage_ramp",
               "tunnel_trench")   # door_ramp: RULINGS 2026-09-08b/c; Law C roles 2026-09-08m/n
#: #2127 R4 A2: the graded document's provenance key carrying each cut
#: piece's OUTLINE (:func:`_cut_rings`) where its rim is two runs or more
CUT_RINGS_KEY = "cut_rings"


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


def _cut_rings(planar: PlanarMap, voids: _t.Sequence) -> list[dict]:
    """#2127 R4 A1/A2: THE CUT OUTLINE of every structure piece whose rim is
    two runs or more (:func:`rim_runs`) — ``{"ref": "<ref>@<lowest void
    fid>", "ring": [vertex ids]}``.

    A piece is the void faces of one ref joined through shared edges with
    each other and with the ``FLOOR_ROLES`` faces next to them; its outline
    is the outer boundary cycle of that union with every vertex standing on
    no rim run left out: the void's rim and, between two runs, the floor's
    own outer edge (an end line, a ramp's top line) — never a chord across
    the cut; a run's vertex inside the piece (the foot of an edge two of
    its void faces share) is no outline vertex.  Topological, so the ring's
    vertices are the emitted rim vertices.  A piece whose rim is one run (a
    basin's closed ring, a U) publishes nothing, and so does one whose outline is not one simple
    cycle through every run in order (it is then read as before)."""
    by_ref: dict[str, list] = {}
    for f in voids:
        by_ref.setdefault(f.ref, []).append(f)
    out: list[dict] = []
    nbr: dict[int, set] = {}
    if by_ref:
        for e in planar.edges.values():
            if e.left_face is not None and e.right_face is not None:
                nbr.setdefault(e.left_face, set()).add(e.right_face)
                nbr.setdefault(e.right_face, set()).add(e.left_face)
    for ref, faces in sorted(by_ref.items()):
        runs = {f.id: rim_runs(planar, f) for f in faces}
        for group in _pieces(planar, nbr, {f.id for f in faces}):
            pr = [r for fid in sorted(group) if fid in runs for r in runs[fid]]
            if len(pr) < 2:
                continue
            ring = _outline(planar, group, pr)
            if ring:
                out.append({"ref": f"{ref}@{min(f for f in group if f in runs)}",
                            "ring": ring})
    return out


def _pieces(planar: PlanarMap, nbr: dict, void_ids: set) -> list[set]:
    """The void faces ``void_ids`` and the floor faces joined to them through
    shared edges (``nbr``: face -> the faces across its edges), one set per
    connected piece."""

    def member(f: int) -> bool:
        return f in void_ids or planar.faces[f].role in FLOOR_ROLES

    seen: set = set()
    out = []
    for start in sorted(void_ids):
        if start in seen:
            continue
        group, todo = set(), [start]
        while todo:
            f = todo.pop()
            if f in group:
                continue
            group.add(f)
            todo.extend(g for g in nbr.get(f, ()) if g not in group and member(g))
        seen |= group
        out.append(group)
    return out


def _outline(planar: PlanarMap, group: set, runs: list) -> list[int]:
    """The rim vertices of ``runs`` in the order the outer boundary of the
    faces ``group`` walks them, or ``[]`` when that boundary is not one
    simple cycle carrying every run contiguously."""
    nxt: dict[int, list[int]] = {}
    eids = {eid for f in group for cyc in (planar.faces[f].ring, *planar.faces[f].holes)
            for eid in cyc}
    for eid in eids:
        e = planar.edges[eid]
        lf, rf = e.left_face in group, e.right_face in group
        if lf != rf:
            a, b = (e.a, e.b) if lf else (e.b, e.a)
            nxt.setdefault(a, []).append(b)
    if any(len(v) != 1 for v in nxt.values()):
        return []                      # a pinch: not one simple cycle
    rim = {v for r in runs for v in r}
    cycles, seen = [], set()
    for v0 in nxt:
        if v0 in seen:
            continue
        cyc, v = [], v0
        while v is not None and v not in seen:
            seen.add(v)
            cyc.append(v)
            v = (nxt.get(v) or (None,))[0]
        if v == v0 and rim & set(cyc):
            cycles.append(cyc)
    if len(cycles) != 1:
        return []
    ring = [v for v in cycles[0] if v in rim]
    pos = {v: i for i, v in enumerate(ring)}
    n = len(ring)
    for r in runs:
        # a run's vertices inside the piece (the foot of the edge two void
        # faces share) are no outline; the rest must follow it in order
        on = [v for v in r if v in pos]
        if r[0] == r[-1] or len(on) < 2:
            return []
        step = {(pos[b] - pos[a]) % n for a, b in zip(on, on[1:], strict=False)}
        if step not in ({1}, {n - 1}):
            return []
    return ring


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
    voids = []
    for fid, f in sorted(planar.faces.items()):
        ring = tuple(ring_vertex_ids(f.ring))
        holes = tuple(tuple(ring_vertex_ids(h)) for h in f.holes)
        ring_ids[fid] = ring
        if f.role == VOID_ROLE and is_structure_role(law, f.role):
            # the void is not a surface: its rim is the product
            voids.append(f)
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
    # #2127 R4 A2: a cut whose rim is several runs states its OUTLINE once,
    # here; a surface with none publishes no key (and reads as before)
    outlines = _cut_rings(planar, voids)
    if outlines:
        prov[CUT_RINGS_KEY] = outlines
    # RULINGS 2026-09-08t: the design surface's ONE least-squares solve —
    # no backend to name, the active-set rounds instead
    prov.setdefault("solver", {"solve": "design_surface",
                               "rounds": sol.iterations, "status": sol.status.value,
                               "residual_m": None if sol.residual is None
                               else round(sol.residual.max_m, 6)})
    prov.setdefault("planar_sha256", hashlib.sha256(json.dumps(
        [[vid, v.key] for vid, v in sorted(planar.vertices.items())]
    ).encode()).hexdigest()[:16])
    return GradedSurface(planar.icao, law.ruleset_key, origin, crs,
                         law.tables.emit.identity.coordinate_dp, verts,
                         tuple(faces), bls, prov)
