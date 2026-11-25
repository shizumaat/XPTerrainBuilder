"""A GROUNDSIDE FACE TOUCHING A PARTIAL SHELL TAKES ITS GROUND RIM (#2197
round 2; spec ``docs/specs/2197-partial-shell-patch-rim-spec.md``).

A PARTIAL SHELL (``airport/ground_rim``) is one rigid pack frame whose
outer rim is its author's ground; the tile build grades our free raster
to its RIM STATIONS (``airport/rim_grade``) but never moves a patch
posting, so where the shell stands over the airport patch (a landside
lot, a service road) the patch's own level ends at the rim: MEASURED on
ELLX round 1, 79 % of the terminal's rim inside the patch, the worst gap
9.42 m.  The rim is the authority there (one-way: the object never
moves, and airside never moves -- "airside is king").

THE PINS (:func:`rim_pins`), per recognised set, on every vertex of a
GROUNDSIDE value face (``constraints/groundside.groundside_face_roles``:
groundside pavement, service road and junction, parking lot) that no face
of any other role carries (an airside face, a strip, a structure's ramp) and that is on no open edge of the patch (the
seam's and the coverage edge's own pins stand there):

* UNDER THE SHEET (the vertex's plan point on a sheet cell): the author's
  ground there (``_RimSet.sheet_at``) less ``UNDER_M`` -- the lot stands
  just under the shell's own ground, never through it;
* OUTSIDE THE PLAN within the stand-off reach (``gap_follow.reach_m``,
  the distance a groundside face welds to a standing rim across) of a
  rim station: the stations' inverse-distance mean less ``UNDER_M``
  (``rim_grade``'s own target);
* anywhere else -- under the shell's buildings and decks, or beyond the
  reach -- no pin: the face follows its own law from the pinned vertices.

A pin is a GROUNDSIDE pin (``[design] groundside_pin_rulings``: stage 1
is foreign to it, so no row footed on it reaches the airside problem) and
a YIELDING pin (``[design] yielding_pin_rulings``: released to a design
target, and reported, where its own hard rows will not hold it).

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..geom.terrain_deck import UNDER_M
from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap
from .gap_follow import reach_m
from .groundside import groundside_face_roles

__all__ = ["GEN", "RULING", "STATS", "rim_sets", "rim_pins"]

GEN = "rim_pins"
RULING = "#2197 a groundside face meets a partial shell's ground rim"
#: the stations a vertex's rim target is read from (``rim_grade.NEAREST``)
NEAREST = 8
STATS: dict[str, dict[str, int]] = {}


def rim_sets(airport: Airport) -> list:
    """Every recognised partial shell (``ground_rim._RimSet``) of the
    airport's terrain models, once per set."""
    seen: dict[str, _t.Any] = {}
    for _oid, _dpath, m, _lift in getattr(airport, "terrain_models", ()) or ():
        rim = getattr(m, "rim", None)
        if rim is not None and m.id not in seen:
            seen[m.id] = rim
    return [seen[k] for k in sorted(seen)]


def _candidates(planar: PlanarMap, law: Law) -> list[int]:
    """The vertices of a groundside value face that no face of any other
    role carries and that stand on no open edge of the patch."""
    ground = frozenset(groundside_face_roles(law))
    open_v: set[int] = set()
    for e in planar.edges.values():
        if e.left_face is None or e.right_face is None:
            open_v.update((e.a, e.b))
    side: dict[int, bool] = {}
    for f in planar.faces.values():
        mine = f.role in ground
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                side[v] = mine and side.get(v, True)
    return sorted(v for v, ok in side.items() if ok and v not in open_v)


def _targets(rs: _t.Any, xy: np.ndarray, reach: float) -> np.ndarray:
    """THE PINS' heights (module doc) of plan points ``xy`` (airport frame)
    for one set; ``nan`` where none."""
    from scipy.spatial import cKDTree
    e, n = xy[:, 0] - rs.xy[0], xy[:, 1] - rs.xy[1]
    out = rs.sheet_at(e, n) - UNDER_M
    st = np.asarray(rs.stations, float)
    if not len(st):
        return out
    k = min(NEAREST, len(st))
    d, idx = cKDTree(st[:, :2]).query(np.c_[e, n], k=k, distance_upper_bound=reach)
    d, idx = d.reshape(len(e), k), idx.reshape(len(e), k)
    ok = np.isfinite(d)
    w = np.where(ok, 1.0 / np.maximum(np.where(ok, d, 1.0), 0.5) ** 2, 0.0)
    z = np.where(ok, st[np.minimum(idx, len(st) - 1), 2], 0.0)
    ring = (w * z).sum(1) / np.maximum(w.sum(1), 1e-12) - UNDER_M
    outside = ~_inside(rs, e, n) & ok[:, 0]
    return np.where(np.isfinite(out), out, np.where(outside, ring, np.nan))


def _inside(rs: _t.Any, e: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Whether frame ``(e, n)`` lies inside the set's plan outline."""
    import shapely
    from shapely.geometry import Polygon
    polys = [Polygon(r) for r in rs.rings if len(r) >= 4]
    if not polys:
        return np.zeros(len(e), bool)
    return shapely.contains_xy(shapely.union_all(polys), e, n)


def rim_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One yielding groundside ``Pin`` per groundside vertex at a partial
    shell's ground (module doc, THE PINS)."""
    stats = STATS.setdefault("rim_pins", {})
    stats.clear()
    sets = rim_sets(airport)
    if not sets:
        return []
    cand = _candidates(planar, law)
    if not cand:
        return []
    xy = np.array([planar.vertices[v].xy for v in cand], float)
    reach = reach_m(law)
    z = np.full(len(cand), np.nan)
    for rs in sets:
        t = _targets(rs, xy, reach)
        z = np.where(np.isnan(z), t, z)
    rows: list[Row] = []
    for v, zz in zip(cand, z, strict=True):
        if np.isfinite(zz):
            rows.append(Pin(int(v), float(zz), Source(GEN, RULING, (f"vertex:{v}",))))
    stats["sets"] = len(sets)
    stats["pinned"] = len(rows)
    return rows
