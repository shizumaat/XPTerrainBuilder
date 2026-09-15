"""THE WRITTEN GEOMETRY (spec ``object-placement-spec.md`` §16b (1)/(4);
owner RULINGS 2026-09-11ap).

What a body's file will actually contain, and the design surface under
it: the samples §16b's cut is pre-tested on, the terrain group a body
stands in, and the samples the plan publishes for the census to read.
ONE reading, so the cut and the instrument cannot disagree.

This lives apart from ``placement_cut`` for the 1,000-line law and for
nothing else; ``_LineCutter.geom_points`` (the sampling itself, which
needs the member's parsed OBJ8) stays with the cutter.
"""
from __future__ import annotations

import math
import typing as _t

from ..model.rebake import Part
from . import anchor_rule as _ar
from . import line_object as _lo                        # noqa: F401

__all__ = ["GEOM_CELL_M", "GEOM_PTS_MAX", "thin_points", "surface_many",
           "_geom_ground", "_geom_span"]

#: §16b (4): the plan cell the WRITTEN GEOMETRY is sampled on, and how
#: many samples a body publishes.  A sampling resolution, never a law:
#: the census reads the ground under the body's own triangles, and the
#: design surface's faces are metres across.  The cap bounds the plan
#: file (LEMD writes ~1,400 bodies) and the farthest-point walk keeps
#: the EXTREMES, which is what a span reading needs.
GEOM_CELL_M = 10.0
GEOM_PTS_MAX = 32


def thin_points(pts: _t.Sequence[tuple[float, float, float]], cap: int
                ) -> tuple[tuple[float, float, float], ...]:
    """``pts`` thinned to ``cap`` by the farthest-point walk (the ONE
    spreading rule, :func:`line_object.farthest_point_stations`) — the
    EXTREMES survive, which is what a span reading needs."""
    if cap <= 0 or len(pts) <= cap:
        return tuple(pts)
    import numpy as np
    ml, mo = _ar._m_per_deg(pts[0][0])
    plan = np.asarray([[p[0] * ml, p[1] * mo] for p in pts], dtype=float)
    keep = _lo.farthest_point_stations(plan, cap)
    return tuple(pts[i] for i in keep.tolist())


def surface_many(surface: _ar.Surface,
                 pts: _t.Sequence[tuple[float, float, float]]) -> list[float]:
    """The design surface under ``pts``, in ONE call where the sampler
    offers one (``surface.many``, the graded interpolator's own vectorised
    form) and point by point otherwise.

    §16b's cut and census both read a body's whole written geometry, so
    the airport asks the surface hundreds of thousands of times: batching
    is most of what pays for the reading (the per-call overhead of a
    Delaunay interpolator dwarfs the interpolation)."""
    if not pts:
        return []
    many = getattr(surface, "many", None)
    if many is not None:
        return [float(z) for z in many([p[0] for p in pts],
                                       [p[1] for p in pts])
                if z is not None and z == z]
    return [float(z) for z in (surface(p[0], p[1]) for p in pts)
            if z is not None]


def _geom_ground(cutter: "_LineCutter", parts: _t.Sequence[Part],
                 tris: _t.Sequence[_t.Sequence[int]], surface: _ar.Surface
                 ) -> tuple[tuple[tuple[float, float, float], ...], float,
                            "float | None"]:
    """§16b (1): ``(the body's written-geometry samples, the RANGE of the
    design surface under them, its MEDIAN)`` — the terrain group a body
    stands in, read once and used three times: the cut's pre-test, the
    coarsening's "within one terrain group" test, and (through the plan's
    published samples) the census's own bar."""
    pts = cutter.geom_points(parts, tris)
    zs = sorted(surface_many(surface, pts))
    if not zs:
        return pts, 0.0, None
    return pts, zs[-1] - zs[0], zs[len(zs) // 2]


def _geom_span(cutter: "_LineCutter", parts: _t.Sequence[Part],
               tris: _t.Sequence[_t.Sequence[int]], surface: _ar.Surface
               ) -> tuple[tuple[tuple[float, float, float], ...], float]:
    """§16b (1): ``(the body's written-geometry samples, the range of the
    design surface under them)``.

    The pre-test of every terrain cut, and the SAME reading the census
    takes (``placement_census.census_v16b``): a body whose own ground
    spans more than ``split_tol_m`` is wider than the terrain it can
    stand on.  Where the plan-box reading of §16 (2) asked five points
    of a hull — which for a carried body is the patch its carrier covers
    — this asks the triangles themselves, and it is bounded by
    :data:`GEOM_PTS_MAX` reads."""
    pts, span, _g = _geom_ground(cutter, parts, tris, surface)
    return pts, span


# ── §16d (1)'s READINGS (moved from ``placement_cut._LineCutter`` for
# the 1,000-line file law; the cutter's methods delegate here and every
# caller and twin reads them there) ──────────────────────────────────────

def written_components(self) -> "list[tuple[int, tuple, tuple]]":
    """§16d (1): EVERY connected component the WRITER will emit, as
    ``(solid_index, triangles, plan box)``.

    ``solid_index`` is the index into ``obj8.solid_components`` — the
    number a ``Part.comp`` names — or ``-1`` for a DRAPED component,
    which no part can ever name because ``parse_obj8`` keeps the
    draped triangles out of ``geom.solid`` altogether.  Both are
    written into some body's file by ``obj8_split``, so both are
    this law's population: a component is a body's only when it lies
    within reach of that body's parts (§16d (1)).

    The plan box is ``(lat0, lon0, lat1, lon1)`` in the placement's
    own frame, the spelling every other plan box carries.  The
    triangles come back as the NUMPY array the components hold: a
    clutter object publishes thousands of components over tens of
    thousands of triangles, and building a Python triple for every
    one of them costs more than the pass — the caller converts only
    the components it actually places (owner RULINGS 2026-09-13h)."""
    if not self._read():
        return []
    import numpy as np
    _box = self.plan_box_of_tris
    out: list[tuple[int, _t.Any, tuple]] = []
    for ci, comp in enumerate(self._comps):
        if not len(comp.tris):
            continue
        out.append((ci, comp.tris, _box(comp.tris)))
    drp = getattr(self._geom, "draped", None)
    if drp is not None and getattr(drp, "shape", (0,))[0]:
        # A DRAPED triangle whose sorted vertex triple is ALSO a solid
        # triangle's is the SAME FACE authored twice — a double-sided
        # panel, one copy draped.  ``obj8_split`` keys a body's own
        # triangles on that triple, so admitting the draped copy as an
        # orphan would make it SENIOR over the solid component's owner
        # and steal the face: LEMD's `OldTerminal_FSX-DCNEUN` lost
        # every triangle of its 18 components that way and its file
        # was never written.  A duplicate face belongs with the solid
        # it duplicates, which is where the component path puts it.
        sol = (np.concatenate([c.tris for c in self._comps if len(c.tris)])
               if any(len(c.tris) for c in self._comps)
               else np.zeros((0, 3), dtype=np.int64))
        base = np.int64(int(self._geom.vertices.shape[0]) + 1)

        def _keys(t):
            q = np.sort(np.asarray(t, dtype=np.int64).reshape(-1, 3), axis=1)
            return (q[:, 0] * base + q[:, 1]) * base + q[:, 2]

        solk = np.unique(_keys(sol)) if sol.shape[0] else \
            np.zeros(0, dtype=np.int64)
        for t in _draped_components(self, drp):
            if solk.shape[0]:
                t = t[~np.isin(_keys(t), solk)]
            if t.shape[0] == 0:
                continue
            out.append((-1, t, _box(t)))
    return out

def part_tris(self, parts: _t.Sequence[Part]) -> tuple:
    """The authored triangles of ``parts``' own components — what a
    body with no station cut of its own will have written into its
    file (§16d (4) asks the atoms of exactly this set)."""
    if not self._read() or not parts:
        return ()
    import numpy as np
    tl = [self._comps[p.comp].tris for p in parts
          if 0 <= p.comp < len(self._comps)]
    if not tl:
        return ()
    return tuple(tuple(int(q) for q in row)
                 for row in np.concatenate(tl).tolist())

def plan_box_of_tris(self, tris) -> "tuple | None":
    """§16d (1): the PLAN BOX of a set of authored triangles.

    A raw body the cut made carries its triangles, and its ``box`` is
    its FEET's (11f (2): a segment covers its own station span).
    That is the right PLAN footprint and the wrong GEOM box — the
    writer puts the triangles in the file, and 115 of LEMD's line
    segments reached beyond a box drawn round their feet."""
    if not self._read() or tris is None or len(tris) == 0:
        return None
    import numpy as np
    v = self._geom.vertices
    p = v[np.asarray(tris, dtype=np.int64).reshape(-1)]
    ml, mo = _ar._m_per_deg(self.lat)
    h = math.radians(self.m.heading_deg)
    s, c = math.sin(h), math.cos(h)
    e = p[:, 0] * c - p[:, 2] * s
    n = -(p[:, 0] * s + p[:, 2] * c)
    la = self.lat + n / ml
    lo = self.lon + e / mo
    return (float(la.min()), float(lo.min()),
            float(la.max()), float(lo.max()))

def _draped_components(self, drp) -> "list":
    """The DRAPED triangles' own connected components, welded on the
    same millimetre key ``obj8.solid_components`` uses.  An exporter's
    ground paint is not one body because it is one ``TRIS`` range."""
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    keyed = np.round(self._geom.vertices, 3)
    _u, canon = np.unique(keyed, axis=0, return_inverse=True)
    canon = np.asarray(canon).reshape(-1)
    nk = int(canon.max()) + 1 if canon.size else 1
    t = canon[drp]
    g = coo_matrix((np.ones(t.shape[0] * 2, dtype=np.int8),
                    (np.concatenate([t[:, 0], t[:, 1]]),
                     np.concatenate([t[:, 1], t[:, 2]]))), shape=(nk, nk))
    _n, label = connected_components(g, directed=False)
    lab = label[t[:, 0]]
    order = np.argsort(lab, kind="stable")
    cuts = np.flatnonzero(lab[order][1:] != lab[order][:-1]) + 1
    return [drp[idx] for idx in np.split(order, cuts) if idx.size]
