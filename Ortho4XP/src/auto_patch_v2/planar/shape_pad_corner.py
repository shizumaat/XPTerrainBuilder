"""THE GAP JOINT RUNS ALONG THE PAD CORNER (issue #883, owner 2026-11-03
"accept recommendation"; RULINGS 2026-10-20 answer 44 kept the step,
2026-10-27y made a declared gap step lawful in the strip checks) — the
pad-side companion of ``planar/shapes._gap_joints``, split out of
``shapes.py`` by the planar layer's 1,000-line budget.

A rigid pad that faces another shape across a gap stands at its own
level; the 08k gap joint declares that step on the Voronoi midline, but
only over the LENS where the two facing edges come within the contact
horizon.  Past the lens the pad's rim runs on, round its corner, along the
zone strip that belongs to the OTHER shape (a face whose majority label is
the other shape's), and that strip carries the same step down from the pad
— measured KBOI, the hangar ``building55`` by taxiway B / A7: the joint
stopped 3.8 m short of the corner and the strip read the kept step as
``strip_seam_tear`` 1.20 m ×2 and ``adjacent_ground_step`` 0.78 m ×2.

So the declaration runs ON the pad rim over that stretch: each maximal run
of consecutive pad-rim vertices that touch a non-shape face of the other
shape, and that contains a vertex of the pad's facing edges (the joint's
own gap).  Its pairs are every rim vertex against every vertex of the
non-shape faces it touches within the pad frontage horizon
(``design.pad_frontage_m`` + 2 ``identity.weld_spacing_m``, the horizon
``pipeline/publication.pad_terrace_joints`` reads), so the declared step
is the largest step the strip carries off the pad there.  The line is a
declaration only: no row, label or vertex changes (the solve reads no
joint line), and a chord that neither crosses nor starts on it reports as
before."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.frame import XY
from ..model.planar import PlanarMap

__all__ = ["pad_corner_runs"]


def pad_corner_runs(pm: PlanarMap, law: Law, pad_faces: _t.Iterable[int],
                    facing: _t.Collection[int], other: int,
                    shape_faces: _t.Collection[int]
                    ) -> list[tuple[list[XY], list[tuple[int, int]]]]:
    """``[(points, pairs)]`` — one per run of ``pad_faces``' rim (module
    docstring).  ``facing``: the pad's vertices on the gap's facing edges;
    ``other``: the shape across the gap; ``shape_faces``: the faces that
    bear a shape (pavement, pads), never a strip."""
    ident = law.tables.emit.identity
    horizon = float(law.tables.emit.design.pad_frontage_m) + 2.0 * float(ident.weld_spacing_m)
    pads = set(pad_faces)
    skip = pads | set(shape_faces)
    sof = pm.shape_of_face

    def strips(v: int) -> list[int]:
        return [g for g in pm.vertices[v].incident_faces if g not in skip]

    def marked(v: int) -> bool:
        return any(sof.get(g) == other for g in strips(v))

    out: list[tuple[list[XY], list[tuple[int, int]]]] = []
    for fid in sorted(pads):
        f = pm.faces[fid]
        for cyc in (f.ring, *f.holes):
            vs = list(pm.ring_vertices(cyc))
            for run in _cyclic_runs(vs, marked):
                if len(run) < 2 or not set(run) & set(facing):
                    continue
                pairs: set[tuple[int, int]] = set()
                for v in run:
                    xy = pm.vertices[v].xy
                    for g in strips(v):
                        for cg in (pm.faces[g].ring, *pm.faces[g].holes):
                            for w in pm.ring_vertices(cg):
                                if w in run or any(h in pads for h in pm.vertices[w].incident_faces):
                                    continue
                                if math.dist(xy, pm.vertices[w].xy) <= horizon:
                                    pairs.add((min(v, w), max(v, w)))
                if pairs:
                    out.append(([tuple(map(float, pm.vertices[v].xy)) for v in run],
                                sorted(pairs)))
    return out


def _cyclic_runs(vs: list[int], keep: _t.Callable[[int], bool]) -> list[list[int]]:
    """The maximal runs of consecutive ``vs`` (a closed ring) that ``keep``
    holds for; a ring every vertex of which is kept is one run, closed."""
    flags = [keep(v) for v in vs]
    if not any(flags):
        return []
    if all(flags):
        return [vs + vs[:1]]
    k = flags.index(False)              # start just after an unkept vertex
    order = vs[k + 1:] + vs[:k + 1]
    fl = flags[k + 1:] + flags[:k + 1]
    runs: list[list[int]] = []
    cur: list[int] = []
    for v, ok in zip(order, fl, strict=True):
        if ok:
            cur.append(v)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs
