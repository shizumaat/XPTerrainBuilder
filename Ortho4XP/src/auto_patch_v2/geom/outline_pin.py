"""THE PINNED AIRSIDE FRONTAGE of a building outline (spec §56 (11) R-W).

"The frontage is not simplified": where a rule-2 outline stands on the
airside's rim, rule 2b (``geom.cluster_outline.simplified_outline``) leaves
it exactly as rule 2 drew it — the closing fills no re-entrant whose mouth
lies on the frontage, the straightening drops no pinned vertex and lays no
new chord there, and a light well on it stays open.  The owner's straight
chords are for the groundside and road sides of the building (§56 (2) 8).

WHY (measured by intervention, ``docs/briefs/padreview2-summary.md`` A):
the vertices a pad shares with an airside face are its WELD ROWS — the hard
two-way holds of 02ah.  A close or a chord on that face re-populates them
(KCLT welded 1,437 -> 1,220 / 3,678; KASE one pad 33 -> 9), the pad's datum
re-chooses, the apron conforms and the taxiways follow.  Airside is king.

``geom`` reads no law and no classification: the caller hands the airside
ground and the pin distance (``emit.identity.min_distinct_spacing_m``,
through ``law.tables.pad_outline``).
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import (GeometryCollection, LinearRing, LineString,
                              MultiPolygon, Polygon, box)
from shapely.ops import unary_union

from .parts import polygon_parts_with_area

__all__ = ["Frontage", "minted_frontage", "remember_frontage"]

#: the airside ground the LAST mints pinned their outlines against, per
#: owner object (the airport) — the census
#: (``constraints/cluster_pad.cluster_polys``) re-draws the outline and must
#: pin it against the SAME ground, or ``pad_cluster_mismatch`` would measure
#: two outline readings (the census-wrapper defect).  Kept here because
#: ``constraints`` may not import ``classify``.
_MINTED: list[tuple[int, object, object]] = []


def remember_frontage(owner, airside) -> None:
    """Record the frontage the mint drew ``owner``'s outlines with."""
    _MINTED.append((id(owner), owner, airside))
    del _MINTED[:-2]


def minted_frontage(owner, default=None):
    """The airside ground ``owner``'s pads were pinned against at the
    mint; ``default`` when this process did not mint them (a replay from
    a later stage)."""
    for k, o, got in reversed(_MINTED):
        if k == id(owner) and o is owner:
            return got
    return default

#: the straightening is re-run while a new chord enters the frontage, each
#: round pinning the run that laid it; past this many the ring is left as
#: rule 2 drew it (never reached on the registered captures).
_MAX_ROUNDS = 6


class Frontage:
    """The airside ground beside ONE outline and the three questions rule
    2b asks of it.  ``fills_refused`` / ``vertices_pinned`` count what the
    pin kept from the simplification (the cost, published per pad)."""

    __slots__ = ("geom", "pin_m", "fills_refused", "vertices_pinned")

    def __init__(self, geom, pin_m: float):
        self.geom = geom
        self.pin_m = float(pin_m)
        self.fills_refused = 0
        self.vertices_pinned = 0
        shapely.prepare(self.geom)

    @classmethod
    def near(cls, poly, airside, pin_m: float, reach_m: float
             ) -> "Frontage | None":
        """The frontage of ``poly``: ``airside`` within ``reach_m`` (what
        the closing and a chord can reach) of its bounds.  ``None`` when
        the pin is disarmed (``pin_m <= 0``, no airside) or no airside
        stands there — the outline is then simplified whole, as before."""
        if (airside is None or pin_m <= 0.0 or airside.is_empty
                or poly is None or poly.is_empty):
            return None
        x0, y0, x1, y1 = poly.bounds
        r = float(reach_m) + float(pin_m)
        local = airside.intersection(box(x0 - r, y0 - r, x1 + r, y1 + r))
        return None if local.is_empty else cls(local, pin_m)

    def on(self, g) -> bool:
        """Does ``g`` stand within the pin distance of the airside?"""
        return bool(shapely.dwithin(g, self.geom, self.pin_m))

    def closing(self, g, closed):
        """``g`` with the closing's fill — every part of ``closed - g``
        that is NOT on the frontage.  A re-entrant whose mouth (or any of
        it) lies on the airside is not filled, whole."""
        fills = polygon_parts_with_area(closed.difference(g))
        keep = [q for q in fills if not self.on(q)]
        self.fills_refused += len(fills) - len(keep)
        # never ``g | closed``: the close's arcs chamfer every convex
        # corner, and the chamfer's ends would stand ON the frontage as
        # vertices rule 2 never drew
        return unary_union([g, *keep]) if keep else g

    def wells(self, poly: Polygon, hole_min_m2: float) -> list:
        """The interior rings of ``poly`` that STAY: a courtyard at or
        over ``hole_min_m2``, and any well on the frontage."""
        out = []
        for h in poly.interiors:
            w = Polygon(h)
            if w.area >= hole_min_m2:
                out.append(h)
            elif self.on(w):
                self.fills_refused += 1
                out.append(h)
        return out

    def _pins(self, c: np.ndarray) -> np.ndarray:
        """Per vertex of the closed ring ``c`` (its closing point not
        repeated): is an edge it ends within
        the pin distance of the airside?  (A vertex ON the frontage pins
        its two ring neighbours with it, so the edges that cross the rim
        stand as drawn.)"""
        near = shapely.dwithin(
            shapely.linestrings(np.stack([c[:-1], c[1:]], axis=1)),
            self.geom, self.pin_m)
        return near | np.roll(near, 1)

    def straighten(self, g, tol: float):
        """Douglas-Peucker at ``tol``, topology-preserving, dropping no
        pinned vertex: each ring is cut at its pinned vertices into runs
        and the runs are simplified TOGETHER (one GEOS call, so no run
        crosses another).  Where a new chord enters the frontage the
        vertices it passed over there are pinned and the pass repeated."""
        polys = [p for p in shapely.get_parts(g) if p.geom_type == "Polygon"]
        rings = [[np.asarray(r.coords)[:, :2] for r in (p.exterior, *p.interiors)]
                 for p in polys]
        pins = [[self._pins(c) for c in rs] for rs in rings]
        if not any(m.any() for ms in pins for m in ms):
            plain = g.simplify(tol, preserve_topology=True)
            if tol <= 0.0 or not self.on(plain):
                return plain
        for _round in range(_MAX_ROUNDS):
            out, again = self._straighten_once(rings, pins, tol)
            if not again:
                break
        else:
            return g
        self.vertices_pinned = int(sum(m.sum() for ms in pins for m in ms))
        made = [Polygon(rs[0], rs[1:]) for rs in out]
        return made[0] if len(made) == 1 else MultiPolygon(made)

    def _straighten_once(self, rings, pins, tol: float):
        """One pass: ``(the new rings, did any run have to be pinned)``."""
        lines, plan = [], []
        for pi, rs in enumerate(rings):
            for ri, c in enumerate(rs):
                n = len(c) - 1
                idx = np.flatnonzero(pins[pi][ri])
                if len(idx) == 0:
                    plan.append((pi, ri, None))
                    lines.append(LinearRing(c))
                    continue
                if len(idx) == 1:
                    # one pin: cut the ring a second time at the vertex
                    # farthest from it, so both runs are open lines
                    far = int(np.argmax(((c[:n] - c[idx[0]]) ** 2).sum(axis=1)))
                    idx = np.array(sorted({int(idx[0]), far}))
                for a, b in zip(idx, np.roll(idx, -1)):
                    seq = np.arange(a, b + 1 if b > a else b + n + 1) % n
                    plan.append((pi, ri, seq))
                    lines.append(LineString(c[seq]))
        got = shapely.get_parts(shapely.simplify(
            GeometryCollection(lines), tol, preserve_topology=True))
        again = False
        new: dict[tuple[int, int], list] = {}
        for (pi, ri, seq), src, s in zip(plan, lines, got):
            sc = np.asarray(s.coords)[:, :2]
            if len(sc) < len(src.coords) and self.on(s):
                # a NEW chord on the frontage: the vertices it passed
                # over there are pinned (the whole run, if it found none)
                m = pins[pi][ri]
                sel = np.arange(len(m)) if seq is None else seq
                close = sel[shapely.dwithin(
                    shapely.points(rings[pi][ri][sel]), self.geom,
                    self.pin_m + tol)]
                fresh = close[~m[close]]
                m[fresh if len(fresh) else sel] = True
                again = True
            new.setdefault((pi, ri), []).append(sc if seq is None else sc[:-1])
        out = []
        for pi, rs in enumerate(rings):
            row = []
            for ri, c in enumerate(rs):
                r = np.concatenate(new[(pi, ri)])
                row.append(r if len(r) >= 3 else c)
            out.append(row)
        return out, again
