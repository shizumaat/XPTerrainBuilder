"""THE RUNWAY FAMILY HOLDS NO STEP BETWEEN ITS OWN FACES (§40 (5) (4);
owner RULINGS 2026-09-15az) — the hard rows behind the ``runway_step``
DEFECT family (``verify.runway.runway_step``).

The census gate reads the runway family only because the solve holds that
family's laws as CONSTRAINTS (``verify.census.DEFECT_KEYS``).  Every other
runway DEFECT family has its generator; ``runway_step`` had none, so a
runway-family ribbon whose two long edges belong to different neighbours —
a §40 shoulder wedged between the slab and a pavement that abuts it within
a metre or two — carried no row tying its outer edge to the runway beside
it.  ``runway_transverse`` bounds each vertex against the RIDGE (~0.45 m of
fall at a 60 m runway's edge), so two vertices half a metre apart could sit
0.6 m apart in height while the abutting pavement's own law pulled the
outer one down.  MEASURED (HECA on its WED pack): 05L/23R's stub shoulder
between the slab and taxiway ``dsf:pol184`` read a 0.47 m cliff over
0.62 m on every engine since the pack was installed.

THE ROWS are the reader's own population, stated in the planar frame: each
ring vertex and each ring-edge midpoint of a runway-family face against the
NEAREST ring edge of ANOTHER runway-family face within the step readers'
contact tolerance (``emit.instrument.step_contact_tol_m``), when that edge
is not one the probe already lies on (a welded pair reads zero).  One
two-sided ``Linear`` per pair,

    |probe − foot| ≤ max(floor, cap · d) − margin,

the verify allowance (``materiality.runway_step_m`` floor, the shoulder's
table cap over the separation ``d``) less the solve's held bar
(``design.hard_tol_m``) and the emitted altitude's rounding, so a held row
mints no DEFECT row.  The ruling head is the runway's lateral law
(``rulesets.runway.transverse_max``), which ``[design] hard_rulings`` holds
hard: a step between two runway faces IS a lateral fall over ``d``.
Nothing here names an airport."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import runway_shoulder_cap
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import RUNWAY_FAMILY

__all__ = ["runway_step_rows"]

GEN = "runway_step"
#: the emitted altitude's own quantum (``alt_abs`` is written to 0.01 m)
_ROUNDING_M = 0.01


def _edges(vw, faces) -> list[tuple[int, int, int]]:
    """Every ring edge ``(face, a, b)`` of ``faces`` — outer and hole rings."""
    out = []
    for f in faces:
        for ring in (vw.rings[f.id], *vw.holes[f.id]):
            n = len(ring)
            for i in range(n):
                a, b = ring[i], ring[(i + 1) % n]
                if a != b:
                    out.append((f.id, a, b))
    return out


def _grid(vw, edges, cell: float) -> dict[tuple[int, int], list[int]]:
    g: dict[tuple[int, int], list[int]] = {}
    for k, (_f, a, b) in enumerate(edges):
        (x0, y0), (x1, y1) = vw.xy[a], vw.xy[b]
        for gx in range(int(math.floor(min(x0, x1) / cell)), int(math.floor(max(x0, x1) / cell)) + 1):
            for gy in range(int(math.floor(min(y0, y1) / cell)), int(math.floor(max(y0, y1) / cell)) + 1):
                g.setdefault((gx, gy), []).append(k)
    return g


def _nearest(vw, edges, grid, cell, fid, p, own: frozenset[int]):
    """The nearest edge of another face to point ``p``: ``(d, a, b, t)``,
    or ``None`` when the nearest is one the probe already lies on."""
    cx, cy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
    best = None
    for gx in (cx - 1, cx, cx + 1):
        for gy in (cy - 1, cy, cy + 1):
            for k in grid.get((gx, gy), ()):
                f, a, b = edges[k]
                if f == fid:
                    continue
                (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2))
                d = math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)
                if best is None or d < best[0]:
                    best = (d, a, b, t)
    if best is None or (best[1] in own or best[2] in own) and best[0] < 1e-6:
        return None
    return best


def runway_step_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The ``runway_step`` contact rows (module docstring)."""
    vw = view(planar, law)
    faces = vw.faces_of_role(RUNWAY_FAMILY)
    if len(faces) < 2:
        return []
    ins = law.tables.emit.instrument
    ctol = float(ins.step_contact_tol_m)
    floor = float(law.tables.emit.materiality.runway_step_m)
    margin = float(law.tables.emit.design.hard_tol_m) + _ROUNDING_M
    edges = _edges(vw, faces)
    cell = max(ctol, 1.0)
    grid = _grid(vw, edges, cell)
    rows: list[Row] = []
    for f in faces:
        cap = runway_shoulder_cap(law, f.code_letter, f.code_number) or 0.0
        src = Source(GEN, "rulesets.runway.transverse_max (runway_step contact, §40 (5) (4))",
                     (f"face:{f.id}", f.ref))
        probes = [((v, 1.0),) for v in vw.face_vertices(f.id)]
        probes += [((a, 0.5), (b, 0.5)) for _f, a, b in _edges(vw, (f,))]
        for terms in probes:
            p = (sum(c * vw.xy[v][0] for v, c in terms), sum(c * vw.xy[v][1] for v, c in terms))
            own = frozenset(v for v, _c in terms)
            hit = _nearest(vw, edges, grid, cell, f.id, p, own)
            if hit is None or hit[0] > ctol:
                continue
            d, a, b, t = hit
            bound = max(0.0, max(floor, cap * d) - margin)
            foot = ((a, -(1.0 - t)), (b, -t)) if 0.0 < t < 1.0 else \
                (((a if t <= 0.0 else b), -1.0),)
            merged: dict[int, float] = {}
            for v, c in (*terms, *foot):
                merged[v] = merged.get(v, 0.0) + c
            rows.append(Linear(tuple((v, c) for v, c in merged.items() if c != 0.0),
                               -bound, bound, src))
    return rows
