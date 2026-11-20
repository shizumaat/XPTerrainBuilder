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
  area — its rim is where the apron or a bund's crest stands) against the median DEM along its rim within the frontage radius of the
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
under :data:`SUNK_KEY`."""
from __future__ import annotations

import dataclasses as _dc
import statistics
import typing as _t

import numpy as np
from shapely import contains_xy
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..geom.sunk_cluster import closed_outline
from ..law import Law
from ..law.tables import is_value_role
from .pad_touch import _median_dem, is_held_step

__all__ = ["SUNK_KEY", "hold_sunk_cells", "sunk_levels"]

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


def _authored_top_m(pad: Polygon, clusters: _t.Sequence[_t.Any], to_xy) -> float | None:
    """The area-weighted AUTHORED TOP (m over the objects' own grade) of
    the components of every cluster whose outline lies mostly inside
    ``pad``; ``None`` where no such cluster carries measured tops."""
    num = den = 0.0
    for c in clusters or ():
        ev = getattr(c, "evidence", None)
        tops = tuple(getattr(ev, "tops", ()) or ())
        rows = tuple(getattr(ev, "rows", ()) or ())
        if not tops or len(tops) != len(rows):
            continue
        u = closed_outline(c, to_xy, 0.0)
        if u is None or u.is_empty or not u.intersects(pad):
            continue
        if u.intersection(pad).area * 2.0 < u.area:
            continue
        for r, t in zip(rows, tops):
            num += float(r[3]) * float(t)
            den += float(r[3])
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
    return (dem, air_u, air_u.buffer(float(law.tables.emit.design.pad_frontage_m)),
            getattr(airport, "clusters", None) or (), airport.frame.entry())


def _held_parts(P: Polygon, wit, law: Law, min_area: float
                ) -> tuple[list[Polygon], dict] | None:
    """The cut-back parts of pad ``P`` and their evidence when it is a
    HELD terrace (module docstring), else ``None``."""
    dem, air_u, wide, clusters, to_xy = wit
    r = float(law.tables.emit.design.pad_frontage_m)
    if P.distance(air_u) > r:
        return None
    lvl = _median_dem(P.boundary.intersection(wide), dem, r)
    own = _ground_dem_m(P, dem)
    top = _authored_top_m(P, clusters, to_xy)
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


def hold_sunk_cells(cells: list, airport: _t.Any, law: Law, min_area: float = 0.0
                    ) -> tuple[list, int]:
    """THE RULE over a finished classification: each HELD pad's
    ``building`` cell is replaced by its cut-back parts (the first keeps
    the ref and the cell's id, the rest ``ref#s<k>`` appended LAST, so no
    other cell's id moves), its evidence plus :data:`SUNK_KEY`.  Returns
    the cells and how many pads were held.  Run LAST, so every cell was read against the pad as drawn and the
    strip it yields is bare ground."""
    wit = _witness(cells, airport, law)
    if wit is None:
        return cells, 0
    out: list = []
    extra: list = []
    n = 0
    for c in cells:
        got = _held_parts(Polygon(c.ring, c.holes), wit, law, min_area) \
            if c.role == "building" else None
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
