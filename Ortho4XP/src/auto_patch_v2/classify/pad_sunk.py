"""A PAD BELOW THE AIRSIDE IT TOUCHES IS A HELD TERRACE (issue #2188 item 2;
owner 2026-11-19T21:28Z on the ELLX fuel farm: "they are connected but via
pipes, we should also be able to see the authored height as an indicator
that it's seated lower than the apron side building").

A pad whose rim touches airside pavement fronts it (``constraints.pads.
pad_fronts_airside``) and is welded flush at the apron's level.  §28 (6)'s
hillside test (``pad_touch.dem_step_m``) reads the pad's level from its rim
DEM where it meets the airside — the apron's own height — so a pad cut into
the hill below the apron reads no step at all.  Two witnesses of the pad's
OWN level are read here instead, one derivation each:

* (b) THE PAD'S AREA DEM (:func:`_ground_dem_m`, the median over its
  area — its rim is where the apron or a bund's crest stands) against the
  median DEM along its rim within the frontage radius of the
  airside (``pad_touch._median_dem``, the datum ``dem_step_m`` reads);
* (a) THE AUTHORED HEIGHT of the objects the pad carries
  (``PadEvidence.tops``: each component's authored top over its object's
  own grade, ``y = 0``), area-weighted over the clusters standing mostly
  inside the pad — a part authored well below its placement zero is
  seated below the apron-side level it is placed from.

When EITHER shows the pad standing below the airside level by more than
``[design] frontage_step_max_m`` (``pad_touch.is_held_step``'s bound) the
pad is a HELD TERRACE: it yields to the airside by the terrace gap
(``planar.pad_terrace``'s own: the frontage radius plus one identity cell,
so it neither fronts the airside by proximity nor re-welds at the
arrangement) and keeps its own DEM datum (09p (3)); the ground between is
the terrace.  The airside is never cut (airside is king): only the pad
yields.  The verdict and its three numbers ride the pad cell's evidence
under :data:`SUNK_KEY`.

A PAD BELOW THE PADS OF ITS OWN UNIT (#2195, owner 2026-11-20T14:20Z on
the same fuel farm: "Fuel farm tanks are being raised, still locked to the
upper parking area as one pad").  A unit's pads are one plane
(``constraints/cluster_pad``), so a pad no airside comes near is read
against the OTHER pads of its unit (the building pads a footprint piece
of the same ``PlanCluster.unit`` stands on) that it touches: it is HELD
when BOTH witnesses say it stands lower -- (b) its own ground is more
than the step below a touching sibling's own ground, and (a) the objects
standing on it (each cluster weighted by its overlap with the pad,
:func:`_overlap_top_m`) are authored more than the step below the unit's
zero.  It yields by the terrace gap to every such higher sibling and
keeps its own ground, exactly as a pad below the airside does (a pad
the gap would cut to under half its area is a sliver between two
levels, never a terrace, and stays in its unit's plane).  Both
witnesses, never either: a unit laid over a hillside whose author drew
one floor stays one plane (16g (10))."""
from __future__ import annotations

import dataclasses as _dc
import statistics
import typing as _t

import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import nonempty_polygon_parts
from ..geom.sunk_cluster import closed_outline
from ..law import Law
from ..law.tables import is_value_role
from .pad_touch import _median_dem, is_held_step

__all__ = ["SUNK_KEY", "hold_sunk_cells", "sunk_levels"]

#: the unit witness's key in :data:`SUNK_KEY`'s record: the median own
#: ground of the higher sibling pads the pad yields to (#2195)
UNIT_KEY = "unit_m"

#: the pad cell's evidence key: ``{"airside_m", "dem_m", "authored_top_m"}``
SUNK_KEY = "pad_sunk_terrace"


def _ground_dem_m(pad: Polygon, dem, samples: int = 32) -> float | None:
    """(b) THE PAD'S OWN GROUND: the median DEM over its AREA, sampled on
    a grid of about ``samples`` x ``samples`` points inside it — never its
    rim, which is where the apron (or a bund's crest) stands.  ``None``
    for a pad no sample falls in."""
    x0, y0, x1, y1 = pad.bounds
    step = max(1.0, max(x1 - x0, y1 - y0) / float(samples))
    gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step), np.arange(y0 + step / 2, y1, step))
    inside = contains_xy(pad, gx.ravel(), gy.ravel())
    zs = [float(dem.z(float(x), float(y)))
          for x, y in zip(gx.ravel()[inside], gy.ravel()[inside], strict=True)]
    return statistics.median(zs) if zs else None


def _cluster_tops(c: _t.Any) -> tuple[float, float]:
    """``(sum of row area x authored top, sum of row area)`` over a
    cluster's measured components (``(0, 0)`` without them)."""
    ev = getattr(c, "evidence", None)
    tops = tuple(getattr(ev, "tops", ()) or ())
    rows = tuple(getattr(ev, "rows", ()) or ())
    if not tops or len(tops) != len(rows):
        return 0.0, 0.0
    return (sum(float(r[3]) * float(t) for r, t in zip(rows, tops, strict=False)),
            sum(float(r[3]) for r in rows))


class _Tops:
    """The clusters carrying measured tops with their outlines, in cluster
    order, and a tree of the outlines -- built on the first pad that asks
    (#2206: each pad re-read every cluster's outline, 194,000 outlines for
    40 pads at HECA)."""

    def __init__(self, clusters: _t.Sequence[_t.Any], to_xy) -> None:
        self._clusters, self._to_xy = clusters, to_xy
        self._rows: list | None = None
        self._tree: STRtree | None = None

    def rows(self, pad: Polygon) -> list:
        """``[(n, d, outline)]`` of the clusters whose outline's box meets
        ``pad``'s, in cluster order (no other outline can meet ``pad``)."""
        if self._rows is None:
            self._rows = list(_top_rows(self._clusters, self._to_xy))
            self._tree = STRtree([r[2] for r in self._rows]) if self._rows else None
        if self._tree is None:
            return []
        return [self._rows[i] for i in sorted(self._tree.query(pad).tolist())]


def _top_rows(clusters: _t.Sequence[_t.Any], to_xy) -> _t.Iterator[tuple]:
    for c in clusters or ():
        n, d = _cluster_tops(c)
        if d <= 0.0:
            continue
        u = closed_outline(c, to_xy, 0.0)
        if u is not None and not u.is_empty:
            yield n, d, u


def _authored_top_m(pad: Polygon, clusters: _t.Sequence[_t.Any], to_xy,
                    tops: "_Tops | None" = None) -> float | None:
    """The area-weighted AUTHORED TOP (m over the objects' own grade) of
    the components of every cluster whose outline lies mostly inside
    ``pad``; ``None`` where no such cluster carries measured tops.
    ``tops``: the witness's held outlines of ``clusters`` (:class:`_Tops`)."""
    num = den = 0.0
    for n, d, u in (tops.rows(pad) if tops is not None else _top_rows(clusters, to_xy)):
        if not u.intersects(pad):
            continue
        if u.intersection(pad).area * 2.0 < u.area:
            continue
        num += n
        den += d
    return None if den <= 0.0 else num / den


def _overlap_top_m(pad: Polygon, outlines: _t.Sequence[tuple[_t.Any, _t.Any]]
                   ) -> float | None:
    """(a) for the unit witness: each cluster's mean authored top weighted
    by the area its outline covers of ``pad`` (a unit's pit floor spans
    several pads, so no one cluster lies mostly inside any of them);
    ``None`` where no measured cluster covers it."""
    num = den = 0.0
    for c, u in outlines:
        n, d = _cluster_tops(c)
        if d <= 0.0 or not u.intersects(pad):
            continue
        w = u.intersection(pad).area
        num += w * n / d
        den += w
    return None if den <= 0.0 else num / den


def _witness(cells: _t.Sequence[_t.Any], airport: _t.Any, law: Law):
    """What every pad's verdict reads, built once: ``(dem, airside union,
    airside widened by the frontage radius, clusters, to_xy)``; ``None``
    without a DEM or an airside."""
    dem = getattr(airport, "dem", None)
    air = [Polygon(c.ring, c.holes) for c in cells
           if c.side == "airside" and is_value_role(law, c.role) and c.role != "building"]
    if dem is None or not air:
        return None
    air_u = unary_union(air)
    clusters, to_xy = getattr(airport, "clusters", None) or (), airport.frame.entry()
    return (dem, air_u, air_u.buffer(float(law.tables.emit.design.pad_frontage_m)),
            clusters, to_xy, _Tops(clusters, to_xy))


def _held_parts(P: Polygon, wit, law: Law, min_area: float
                ) -> tuple[list[Polygon], dict] | None:
    """The cut-back parts of pad ``P`` and their evidence when it is a
    HELD terrace (module docstring), else ``None``."""
    dem, air_u, wide, clusters, to_xy, tops = wit
    r = float(law.tables.emit.design.pad_frontage_m)
    if P.distance(air_u) > r:
        return None
    lvl = _median_dem(P.boundary.intersection(wide), dem, r)
    own = _ground_dem_m(P, dem)
    top = _authored_top_m(P, clusters, to_xy, tops)
    steps = [s for s in ((None if lvl is None or own is None else lvl - own),
                         (None if top is None else -top)) if s is not None and s > 0.0]
    if not any(is_held_step(law, s) for s in steps):
        return None
    gap = r + float(law.tables.emit.identity.min_distinct_spacing_m)
    kept = sorted((q for q in nonempty_polygon_parts(P.difference(air_u.buffer(gap)))
                   if q.area >= min_area), key=lambda q: -q.area)
    if not kept:
        return None
    return kept, {SUNK_KEY: {"airside_m": None if lvl is None else round(lvl, 3),
                             "dem_m": None if own is None else round(own, 3),
                             "authored_top_m": None if top is None else round(top, 3)}}


def _unit_siblings(cells: _t.Sequence[_t.Any], airport: _t.Any
                   ) -> tuple[dict[str, set[str]], list[tuple[_t.Any, _t.Any]]]:
    """``({pad ref: refs of the other building pads of its units}, the
    clusters with their outlines)``: two pads are siblings when footprint
    pieces of one ``PlanCluster.unit`` stand on both."""
    to_xy = airport.frame.entry()
    pads = {str(c.ref): Polygon(c.ring, c.holes) for c in cells if c.role == "building"}
    outlines, units = [], {}
    for c in getattr(airport, "clusters", None) or ():
        u = closed_outline(c, to_xy, 0.0)
        if u is None or u.is_empty:
            continue
        outlines.append((c, u))
        on = {ref for ref, P in pads.items() if u.intersects(P)
              and u.intersection(P).area > 0.0}
        units.setdefault(str(getattr(c, "unit", "") or getattr(c, "id", id(c))), set()).update(on)
    sib: dict[str, set[str]] = {}
    for refs in units.values():
        for ref in refs:
            sib.setdefault(ref, set()).update(refs - {ref})
    return sib, outlines


def _unit_held_parts(P: Polygon, ref: str, unit, wit, law: Law, min_area: float
                     ) -> tuple[list[Polygon], dict] | None:
    """The cut-back parts of pad ``P`` and their evidence when it is HELD
    below the pads of its own unit (module docstring, #2195), else
    ``None``.  ``unit`` is ``(siblings, outlines, pads, own grounds)``."""
    sib, outlines, pads, own_of = unit
    r = float(law.tables.emit.design.pad_frontage_m)
    own = own_of(ref)
    if own is None:
        return None
    upper = [q for q in sorted(sib.get(ref, ()))
             if P.distance(pads[q]) <= r and own_of(q) is not None
             and own_of(q) - own > 0.0 and is_held_step(law, own_of(q) - own)]
    top = _overlap_top_m(P, outlines) if upper else None
    if not upper or top is None or not is_held_step(law, -top) or top > 0.0:
        return None
    gap = r + float(law.tables.emit.identity.min_distinct_spacing_m)
    hi = unary_union([pads[q] for q in upper]).buffer(gap)
    kept = sorted((q for q in nonempty_polygon_parts(P.difference(hi))
                   if q.area >= min_area), key=lambda q: -q.area)
    if not kept or kept[0].area * 2.0 < P.area:
        return None             # the gap leaves a sliver, not a terrace
    return kept, {SUNK_KEY: {"airside_m": None, "dem_m": round(own, 3),
                             "authored_top_m": round(top, 3),
                             UNIT_KEY: round(statistics.median(own_of(q) for q in upper), 3)}}


def _unit_witness(cells: _t.Sequence[_t.Any], airport: _t.Any, wit):
    """The unit witness's readings, built once (``None`` without
    clusters): siblings, outlines, the pads and a memo of their own
    ground."""
    if not getattr(airport, "clusters", None):
        return None
    sib, outlines = _unit_siblings(cells, airport)
    pads = {str(c.ref): Polygon(c.ring, c.holes) for c in cells if c.role == "building"}
    memo: dict[str, float | None] = {}

    def own_of(ref: str) -> float | None:
        if ref not in memo:
            memo[ref] = _ground_dem_m(pads[ref], wit[0])
        return memo[ref]
    return sib, outlines, pads, own_of


def hold_sunk_cells(cells: list, airport: _t.Any, law: Law, min_area: float = 0.0
                    ) -> tuple[list, int]:
    """THE RULE over a finished classification: each HELD pad's
    ``building`` cell is replaced by its cut-back parts (the first keeps
    the ref and the cell's id, the rest ``ref#s<k>`` appended LAST, so no
    other cell's id moves), its evidence plus :data:`SUNK_KEY`.  Returns
    the cells and how many pads were held.  Run LAST, so every cell was
    read against the pad as drawn and the
    strip it yields is bare ground."""
    wit = _witness(cells, airport, law)
    if wit is None:
        return cells, 0
    unit = _unit_witness(cells, airport, wit)
    out: list = []
    extra: list = []
    n = 0
    for c in cells:
        got = None
        if c.role == "building":
            P = Polygon(c.ring, c.holes)
            got = _held_parts(P, wit, law, min_area)
            if got is None and unit is not None and str(c.ref) in unit[2]:
                got = _unit_held_parts(P, str(c.ref), unit, wit, law, min_area)
        if got is None:
            out.append(c)
            continue
        n += 1
        parts, ev = got
        for k, q in enumerate(parts):
            part = _dc.replace(c, ref=c.ref if k == 0 else f"{c.ref}#s{k}",
                               ring=tuple(q.exterior.coords)[:-1],
                               holes=tuple(tuple(h.coords)[:-1] for h in q.interiors),
                               evidence={**c.evidence, **ev})
            (extra if k else out).append(part)
    # every other cell keeps its id: a split's further parts go LAST
    return out + [_dc.replace(c, id=len(out) + i) for i, c in enumerate(extra)], n


def sunk_levels(cells: _t.Iterable[_t.Any]) -> dict[str, float]:
    """``{pad ref: its own ground}`` over the HELD pads' cells — the
    channel the planar map publishes (``PlanarMap.sunk_pads``)."""
    out: dict[str, float] = {}
    for c in cells:
        v = ((getattr(c, "evidence", None) or {}).get(SUNK_KEY) or {}).get("dem_m")
        if v is not None:
            out[str(c.ref)] = float(v)
    return out
