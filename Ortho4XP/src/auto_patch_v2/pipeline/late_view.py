"""THE LATE MAP AS ONE STAGE SEES IT (#2206; ``late_stage.run_last_stages``).

The last stages (the gap pieces, then the pad roads, then the car lots) are
solved in order on ONE derived map.  A stage solves on that map WITHOUT the
faces the later stages own (:func:`withheld_view`): the face table less
them, each edge's side faces and each vertex's ``incident_faces`` read past
them.  Ids are kept, so a solution of the view indexes the full map.

THE NODES THEY MINTED GO TOO.  Pass C nodes a later stage's face INTO the
rings it meets (a pad road's corner on a gap part's or a pad's ring, its
stand-off notch): the map an earlier stage was derived on alone never had
those nodes.  Each one the view can lift — a vertex no base map carries,
on exactly two ring edges of the faces that stay, which those two edges
alone hold — is DISSOLVED: its two edges become one, so the rings the stage
solves are the ones it had on its own map, and the node takes its level on
that edge after the solve (:func:`dissolved_levels`), as the next stage's
rim node took it off the stage before.  MEASURED (LGAV, lane lonesolve):
with the nodes left on the rings, ``gap:2`` moved 72 of 106 nodes, worst
1.10 m, against the old gap derive."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..model.planar import face_vertex_set
from .stage_one_map import _items

__all__ = ["VIEW_FIELDS", "withheld_vertices", "withheld_view", "dissolved_levels"]

#: the PlanarMap fields a withheld view replaces
VIEW_FIELDS = ("faces", "edges", "vertices")


def withheld_vertices(pm, faces: _t.AbstractSet[int]) -> frozenset[int]:
    """The vertices ONLY ``faces`` carry: every vertex of one of them that
    no other face carries.  The stage holds them at the survey with no row
    and no face of its own on them (``late_stage.late_solve``)."""
    if not faces:
        return frozenset()
    own: set[int] = set()
    other: set[int] = set()
    for f in pm.faces.values():
        (own if f.id in faces else other).update(face_vertex_set(pm, f))
    return frozenset(own - other)


def withheld_view(pm, faces: _t.AbstractSet[int],
                  standing_xy: _t.AbstractSet[tuple] = frozenset()
                  ) -> tuple[_t.Any, dict[int, tuple[int, int, float]]]:
    """``(pm without faces, the dissolved nodes)`` — module docstring.
    ``standing_xy``: the coordinates the base map carries (a base vertex is
    never dissolved).  The dissolved map is ``{node: (u, w, t)}``, the node
    at ``t`` along the edge ``u -> w`` it was lifted onto.  ``(pm, {})``
    when ``faces`` is empty."""
    if not faces:
        return pm, {}
    gone = frozenset(faces)
    kept = {i: f for i, f in pm.faces.items() if i not in gone}

    def side(f):
        return None if f in gone else f
    edges = {i: (e if e.left_face not in gone and e.right_face not in gone
                 else _dc.replace(e, left_face=side(e.left_face),
                                  right_face=side(e.right_face)))
             for i, e in pm.edges.items()}
    rings = {fid: [list(f.ring), *(list(h) for h in f.holes)] for fid, f in kept.items()}
    dissolved = _dissolve(pm, gone, edges, rings, standing_xy)
    faces_v = {fid: (f if rings[fid] == [list(f.ring), *(list(h) for h in f.holes)]
                     else _dc.replace(f, ring=tuple(rings[fid][0]),
                                      holes=tuple(tuple(h) for h in rings[fid][1:])))
               for fid, f in kept.items()}
    lifted = set(dissolved)
    verts = {i: (v if not (gone.intersection(v.incident_faces) or i in lifted)
                 else _dc.replace(v, incident_faces=() if i in lifted else tuple(
                     f for f in v.incident_faces if f not in gone)))
             for i, v in _items(pm.vertices)}
    return _dc.replace(pm, faces=faces_v, edges=edges, vertices=verts), dissolved


def _dissolve(pm, gone, edges: dict, rings: dict,
              standing_xy) -> dict[int, tuple[int, int, float]]:
    """Lift every node the withheld faces minted off the kept rings (in
    place on ``edges`` / ``rings``); ``{node: (u, w, t)}``."""
    cand = sorted(v for f in gone if f in pm.faces for v in face_vertex_set(pm, pm.faces[f])
                  if tuple(pm.vertices[v].xy) not in standing_xy)
    at: dict[int, set[int]] = {}                 # vertex -> kept ring edges at it
    for cycs in rings.values():
        for cyc in cycs:
            for e in cyc:
                at.setdefault(edges[e].a, set()).add(e)
                at.setdefault(edges[e].b, set()).add(e)
    nid = max(edges, default=-1) + 1
    out: dict[int, tuple[int, int, float]] = {}
    for v in cand:
        es = sorted(at.get(v, ()))
        if len(es) != 2:
            continue
        e1, e2 = edges[es[0]], edges[es[1]]
        sides1 = {e1.left_face, e1.right_face} - {None}
        sides2 = {e2.left_face, e2.right_face} - {None}
        u = e1.b if e1.a == v else e1.a
        w = e2.b if e2.a == v else e2.a
        if sides1 != sides2 or not sides1 or u == w or (at.get(u, set()) & at.get(w, set())):
            continue
        new = _dc.replace(e1, id=nid, a=u, b=w)
        if e1.a == v:                          # u is e1's b: the sides flip with the walk
            new = _dc.replace(new, left_face=e1.right_face, right_face=e1.left_face)
        edges[nid] = new
        for fid in sides1:
            rings[fid] = [_splice(cyc, es[0], es[1], nid) for cyc in rings[fid]]
        for x in (u, w):
            at[x] -= {es[0], es[1]}
            at[x].add(nid)
        at.pop(v, None)
        (ux, uy), (wx, wy), (vx, vy) = pm.vertices[u].xy, pm.vertices[w].xy, pm.vertices[v].xy
        dd = (wx - ux) ** 2 + (wy - uy) ** 2
        t = ((vx - ux) * (wx - ux) + (vy - uy) * (wy - uy)) / dd if dd else 0.0
        out[v] = (u, w, min(1.0, max(0.0, t)))
        nid += 1
    return out


def _splice(cyc: list[int], a: int, b: int, new: int) -> list[int]:
    """``cyc`` with its consecutive edges ``a`` and ``b`` (either order,
    cyclically) replaced by ``new``."""
    n = len(cyc)
    for k in range(n):
        if {cyc[k], cyc[(k + 1) % n]} == {a, b}:
            if k + 1 < n:
                return cyc[:k] + [new] + cyc[k + 2:]
            return [new] + cyc[1:-1]
    return cyc


def dissolved_levels(z: _t.Sequence[float],
                     dissolved: _t.Mapping[int, tuple[int, int, float]],
                     standing: _t.Mapping[int, float] | None = None) -> list[float]:
    """``z`` with every dissolved node at its level: ``standing``'s where it
    has one (a node on a standing cell's rim takes that cell's base edge,
    ``stage_one_map.late_rim_levels`` — the rule the next stage's rim nodes
    were levelled by), else on the edge it was lifted onto (a node lifted
    onto an edge whose end was itself lifted is read after it: the map is
    applied in lifting order, reversed)."""
    out = list(z)
    standing = standing or {}
    for v, (u, w, t) in reversed(list(dissolved.items())):
        out[v] = float(standing[v]) if v in standing else \
            (1.0 - t) * float(out[u]) + t * float(out[w])
    return out
