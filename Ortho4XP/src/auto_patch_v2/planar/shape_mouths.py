"""ONE CONNECTED APRON IS ONE SHAPE (owner RULINGS 2026-09-30bk, Q-152 (a))
— the mouth weld ``planar/shapes.build_shapes`` runs after the strip weld,
split out of ``shapes.py`` by the planar layer's 1,000-line budget."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["weld_same_role_mouths"]


def weld_same_role_mouths(pm: PlanarMap, law: Law, label: dict[int, int],
                           N: frozenset[int], uf: _t.Any, stats: _t.Any) -> None:
    """ONE CONNECTED APRON IS ONE SHAPE (owner RULINGS 2026-09-30bk, Q-152
    (a)).  Two labels meet at a MOUTH: the planar edges whose two vertices
    carry them.  The mouth's two SIDES are PAVEMENT faces (value roles,
    rigid pads excepted — a pad never parts pavement, RULINGS 2026-09-03h;
    a zone strip or the open boundary is no side): the faces flanking each
    mouth edge, and at each end of it the faces whose MAJORITY label is
    that end's own (a class change at the end of a neck shows there, not on
    the neck's own ring edge).  Where every side face of every mouth edge
    between the two labels is a ``terrace.one_shape_roles`` role — two
    parts of one apron — the labels WELD (one such edge suffices: see the
    mixed case below): no contour joint is drawn, no row
    dropped, the apron grades through and the terrain is cut / filled.
    A pair whose every mouth edge has another role on a side (apron ->
    service road / lot / taxiway: a road leaving an apron) keeps its
    separation and 08k's joint — and no chain of welds may merge such a
    pair either.  The
    test reads roles only, never the DEM."""
    roles = frozenset(law.tables.emit.terrace.one_shape_roles)
    if not roles:
        return
    spec = law.tables.precedence.roles
    paved = frozenset(r for r, sp_ in spec.items() if sp_.value and not sp_.rigid)
    major: dict[int, int] = {}
    for fid, f in pm.faces.items():
        if f.role in paved:
            ls = [label[v] for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc) if v in label]
            if ls:
                major[fid] = max(set(ls), key=lambda l: (ls.count(l), -l))
    verdict: dict[tuple[int, int], tuple[bool, bool]] = {}
    for e in pm.edges.values():
        if e.a in N or e.b in N:
            continue
        la, lb = label.get(e.a), label.get(e.b)
        if la is None or lb is None or la == lb:
            continue
        fs = {f for f in (e.left_face, e.right_face) if f is not None}
        fs |= {f for v, l in ((e.a, la), (e.b, lb))
               for f in pm.vertices[v].incident_faces if major.get(f) == l}
        side = {pm.faces[f].role for f in fs if pm.faces[f].role in paved}
        k = (min(la, lb), max(la, lb))
        has_same, has_other = verdict.get(k, (False, False))
        same = bool(side) and side <= roles
        verdict[k] = (has_same or same, has_other or not same)
    # a pair welds only where EVERY mouth edge between it is one class; a
    # pair that also meets at a class change keeps its separation (counted
    # ``mouths_mixed`` when it has same-class edges too), and no chain of
    # welds merges a kept pair
    kept = [k for k, (_hs, ho) in verdict.items() if ho]
    stats.mouths_kept += len(kept)
    stats.mouths_mixed += sum(1 for hs, ho in verdict.values() if hs and ho)
    for (la, lb), (same, other) in sorted(verdict.items()):
        if other or not same:
            continue
        ra, rb = uf.find(la), uf.find(lb)
        if ra == rb or any({uf.find(x), uf.find(y)} == {ra, rb} for x, y in kept):
            continue
        uf.union(ra, rb)
        stats.welded_same_role_mouths += 1
    for v in label:
        label[v] = uf.find(label[v])
