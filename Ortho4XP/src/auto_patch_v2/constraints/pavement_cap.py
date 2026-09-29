"""THE UNIVERSAL PAVEMENT CAP (owner RULINGS 2026-09-29ac, issue #105).

"No pavement of any class may be steeper than the road grade cap (the
steepest cap in the law).  Class caps that are lower still apply; where a
class cap is absent, not applied, or a pavement pair is otherwise unpriced
(a step, a cliff 'judged as if welded', a corridor read as ground, an exit
mouth) the road cap binds as a HARD row."

The cap is ONE accessor, :func:`law.tables.pavement_fallback_cap` — the
``[common] road_max_grade`` itself, never a second number.

THE POPULATION IS GEOMETRIC, NOT THE LAW SET.  ``constraints/ceiling.py``
twins every pair a family already PRICES; the ruling's subject is the
pairs nobody prices, so this reads the planar map:

* every consecutive pair of one pavement face's ring (outer and holes) —
  the ring edges a pad, lot or apron ring carries with no family on them;
* every pair of vertices of two DIFFERENT pavement faces standing within
  ``WELD_M`` of each other without sharing the vertex (a shared vertex is
  one unknown) — the welded neighbours §31 (7) judges as if welded.

Pavement is :func:`law.tables.pavement_roles` (the value, non-structure
roles).  Two exclusions, each a ruling: a platform COLLAR face
(``model.planar.is_collar_ref``) is a 1:3 bank (RULINGS 2026-09-28a (1))
— ground, not pavement — and a pair touching a collar vertex crosses that
bank; structure ramps carry their own ruled caps and are not pavement.

A pair ALREADY capped at or under the fallback by a hard ``Diff`` over the
same two vertices (the ceiling's twins, the road cross-section, …) mints
nothing — "one hard row family over every pavement pair not already capped
lower".  A pair whose two vertices are both PINNED mints nothing: two pins
are the law's own values, and a row between them constrains nothing the
solve can move.  A pair at zero plan distance (two stacked vertices) is a
weld the emitter owns, not a grade, and mints nothing.

HARD: the ruling head is in ``emit.toml [design] hard_rulings``.  Two-way
(a grade cap has no leader); AIRSIDE IS KING is kept by the staged solve —
stage 1 drops every row touching a groundside vertex, and stage 2 solves
the groundside against the airside's fixed values.
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import pavement_fallback_cap, pavement_roles
from ..model.constraints import Diff, Pin, Row, Source
from ..model.planar import PlanarMap, is_collar_ref

__all__ = ["pavement_road_cap", "GEN", "RULING", "WELD_M"]

GEN = "pavement_road_cap"
#: The ruling HEAD ``[design] hard_rulings`` names (everything before the
#: first parenthesis, ``solve.design.ruling_head``).
RULING = ("rulesets.common.road_max_grade pavement fallback "
          "(owner RULINGS 2026-09-29ac)")
#: Two different pavement faces' vertices this close in plan are welded
#: neighbours (the census family ``pavement_over_road_cap`` reads the same
#: radius, ``check_grade.PAVCAP_WELD_M``).
WELD_M = 1.0


def pavement_road_cap(rows: _t.Sequence[Row], planar: PlanarMap, law: Law
                      ) -> list[Row]:
    """The fallback rows over ``planar``'s pavement pairs (module
    docstring), given the law set ``rows`` already minted."""
    cap = pavement_fallback_cap(law)
    pav = set(pavement_roles(law))
    face_vs: dict[int, tuple[int, ...]] = {}
    rings: list[tuple[int, ...]] = []
    collar_v: set[int] = set()
    for f in planar.faces.values():
        if f.role not in pav:
            continue
        cyc = [planar.ring_vertices(r) for r in (f.ring, *f.holes)]
        if is_collar_ref(f.ref):
            collar_v.update(v for c in cyc for v in c)
            continue
        rings.extend(c for c in cyc if len(c) >= 2)
        face_vs[f.id] = tuple(dict.fromkeys(v for c in cyc for v in c))
    if not face_vs:
        return []
    # already capped at or under the fallback (a hard Diff over the pair)
    capped: set[tuple[int, int]] = set()
    pinned: set[int] = set()
    for r in rows:
        if isinstance(r, Diff) and r.soft is None and r.cap <= cap:
            capped.add((min(r.a, r.b), max(r.a, r.b)))
        elif isinstance(r, Pin):
            pinned.add(r.v)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    src = Source(GEN, RULING, ())
    seen: set[tuple[int, int]] = set()
    out: list[Row] = []

    def _mint(a: int, b: int) -> None:
        if a == b:
            return
        key = (min(a, b), max(a, b))
        if key in seen or key in capped:
            return
        seen.add(key)
        if a in collar_v or b in collar_v or (a in pinned and b in pinned):
            return
        (xa, ya), (xb, yb) = xy[a], xy[b]
        d = math.hypot(xa - xb, ya - yb)
        if d <= 0.0:
            return
        out.append(Diff(key[0], key[1], cap, d, src))

    for c in rings:
        for i, a in enumerate(c):
            _mint(a, c[(i + 1) % len(c)])
    # welded neighbours of two different faces
    owner: dict[int, set[int]] = {}
    for fid, vs in face_vs.items():
        for v in vs:
            owner.setdefault(v, set()).add(fid)
    verts = sorted(owner)
    if len(verts) >= 2:
        from scipy.spatial import cKDTree
        tree = cKDTree([xy[v] for v in verts])
        for i, j in sorted(tree.query_pairs(WELD_M)):
            a, b = verts[i], verts[j]
            if owner[a] == owner[b] and len(owner[a]) == 1:
                continue            # same single face: its ring pairs above
            if not (owner[a] - owner[b] or owner[b] - owner[a]):
                continue
            _mint(a, b)
    return out
