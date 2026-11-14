"""THE LINE OBJECT (owner RULINGS 2026-09-10bb; spec
``othh-seat-artefacts-spec.md`` §16).

A fence, a kerb, a jet-blast line, a light string is a LINE OBJECT: it
never forms a rigid body with what it touches, never founds a foot for
one, and DRAPES on the design surface — so a fence following the ground
never lifts or lowers a building.  At LEMD one `LEMDzaun` component
chained 38 parts of 5 resources over 1,406 m onto ITS single foot
(`Terminal4_green-LEMD50` came out 6.86 m under its ground).

THE READER, two measured deviations from 10bb's words (spec §16.1):

* a component is LINE-SHAPED when ``length / width`` exceeds
  ``[rebake] line_object_ratio`` and its height is under
  ``line_object_max_h``, where ``length`` is the DIAGONAL of its authored
  plan box and ``width`` its plan-projected triangle area over that
  length.  Length/width off the BOX SIDES is refuted: LEMD's
  ``Munoza-LEMDzaun`` is the airport's whole perimeter in ONE component,
  box 4,463 × 2,583 m — ratio 1.7 by the sides, 3.4 × 10⁶ by this;
* the verdict is per RESOURCE, not per component: a resource is a LINE
  OBJECT when EVERY genuine component of it is line-shaped (a fence file
  is all fence).  Per component the class swallows building walls — at
  LEMD 4,207 of 9,423 ground parts; per file, 54 of 300 resources.

Pure geometry over the resource cache; no I/O of its own, no environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np

from . import obj8 as _obj8

__all__ = ["component_shape", "is_line_shaped", "is_line_object", "LineLaw", "RibbonLaw",
           "line_law", "ribbon_law", "Segment", "farthest_point_stations", "segment_by_station"]


@_dc.dataclass(frozen=True)
class RibbonLaw:
    """The three numbers the GROUND RIBBON reading takes (spec 2068 A3
    R4), each read where it lives (:func:`ribbon_law`): the shortest
    panel (``[rebake] line_ribbon_min_panel_m``), the steepest foot or
    head between two joined columns (``emit.design.bank_slope``) and the
    highest lowest foot over the file's zero (``[rebake]
    elevated_base_m``)."""

    min_panel_m: float
    slope_max: float
    foot_max_m: float


def ribbon_law(law) -> RibbonLaw:
    """The bound law's :class:`RibbonLaw`."""
    rb = law.tables.structures.rebake
    return RibbonLaw(float(rb.line_ribbon_min_panel_m),
                     float(law.tables.emit.design.bank_slope), float(rb.elevated_base_m))


def component_shape(geom: _obj8.ObjGeometry, comp: _obj8.Component,
                    ribbon: "RibbonLaw | None" = None, max_h: float = math.inf
                    ) -> tuple[float, float, float]:
    """``(length, width, height)`` of one component in the AUTHORED frame:
    the plan-box diagonal, the plan-projected triangle area over it, and
    the height.  ``width`` is 0.0 for a purely vertical sheet (a fence
    panel), which is the strongest line reading there is.

    The height is the y extent, except for a zero-width sheet that is a
    GROUND RIBBON (spec 2068 A3 R4, :func:`_ground_ribbon` under
    ``ribbon`` and the line height ``max_h``), whose height is its
    tallest COLUMN: a fence climbing a slope on 3.5 m panels is 3.5 m
    high, not the panel plus the climb.  With no ``ribbon`` law the
    height is the y extent (the pre-A3 reading)."""
    t = np.asarray(comp.tris)
    v = geom.vertices
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    plan_area = 0.5 * float(np.abs((b[:, 0] - a[:, 0]) * (c[:, 2] - a[:, 2])
                                   - (c[:, 0] - a[:, 0]) * (b[:, 2] - a[:, 2])).sum())
    pts = v[t.reshape(-1)]
    length = math.hypot(float(pts[:, 0].max() - pts[:, 0].min()),
                        float(pts[:, 2].max() - pts[:, 2].min()))
    width = (plan_area / length) if length > 0.0 else 0.0
    if width <= 0.0 and ribbon is not None:
        tallest = _ground_ribbon(v, t, ribbon, max_h)
        if tallest is not None:
            return length, width, tallest
    return length, width, float(comp.max_y - comp.min_y)


#: plan positions closer than this are one column (authored sheets share
#: their vertical edges' x/z exactly; the grid only absorbs float noise)
_COLUMN_GRID_M = 0.01


def _ground_ribbon(v: np.ndarray, t: np.ndarray, law: RibbonLaw,
                   max_h: float) -> "float | None":
    """The tallest column of the vertical sheet ``t`` (triangles into
    ``v``) when it is a GROUND RIBBON, else ``None``.  All five (spec 2068
    A3 R4): (1) every column (the vertices at one plan position) carries
    a foot and a head; (2) the tallest column is under ``max_h``; (3) the
    shortest is over ``law.min_panel_m``; (4) between two columns a
    triangle joins, neither foot nor head climbs steeper than
    ``law.slope_max``; (5) the lowest foot is at or under
    ``law.foot_max_m`` over the file's zero."""
    idx = np.unique(t.reshape(-1))
    if idx.size == 0:
        return None
    keys = np.round(v[idx][:, [0, 2]] / _COLUMN_GRID_M).astype(np.int64)
    u, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    lo = np.full(len(u), np.inf)
    hi = np.full(len(u), -np.inf)
    np.minimum.at(lo, inv, v[idx][:, 1])
    np.maximum.at(hi, inv, v[idx][:, 1])
    panel = hi - lo
    if not (float(panel.min()) > law.min_panel_m and float(panel.max()) < max_h   # (1)-(3)
            and float(lo.min()) <= law.foot_max_m):                                # (5)
        return None
    col = np.zeros(int(idx.max()) + 1, dtype=np.int64)
    col[idx] = inv
    c = col[t]
    pairs = np.vstack([c[:, [0, 1]], c[:, [1, 2]], c[:, [0, 2]]])
    pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    if pairs.size:                                                              # (4)
        xy = u.astype(float) * _COLUMN_GRID_M
        d = np.hypot(*(xy[pairs[:, 0]] - xy[pairs[:, 1]]).T)
        rise = np.maximum(np.abs(lo[pairs[:, 0]] - lo[pairs[:, 1]]),
                          np.abs(hi[pairs[:, 0]] - hi[pairs[:, 1]]))
        if bool((rise > law.slope_max * d).any()):
            return None
    return float(panel.max())


def is_line_shaped(geom: _obj8.ObjGeometry, comp: _obj8.Component, rb,
                   ribbon: "RibbonLaw | None" = None) -> bool:
    """One component's verdict (module doc).  A zero-width sheet is a
    line at any length; a degenerate component (no plan extent) is not.
    ``ribbon`` arms the ground-ribbon height (:func:`component_shape`);
    without it, a :class:`LineLaw` ``rb`` carries its own."""
    if rb.line_object_ratio <= 0.0:
        return False
    if ribbon is None:
        ribbon = getattr(rb, "ribbon", None)
    length, width, height = component_shape(geom, comp, ribbon, rb.line_object_max_h)
    if length <= 0.0 or height >= rb.line_object_max_h:
        return False
    if width <= 0.0:
        return True
    return length / width > rb.line_object_ratio


def is_line_object(cache: _obj8.ResourceCache, resolved: str, rb,
                   ribbon: "RibbonLaw | None" = None) -> bool:
    """THE RESOURCE's verdict: every genuine component line-shaped, and
    at least one of them (an empty file is not a line object).  The
    caller excludes the structure-seated members (a deck, a plate, a deck
    family, a basin member): a structure seat governs them, 14.1 rule 4."""
    if rb.line_object_ratio <= 0.0:
        return False
    geom = cache.geometry(resolved)
    comps = cache.genuine(resolved)
    if geom is None or not comps:
        return False
    return all(is_line_shaped(geom, c, rb, ribbon) for c in comps)


# ── THE SEGMENT CUT (owner RULINGS 2026-09-11f (2); spec §10) ────────────

@_dc.dataclass(frozen=True)
class LineLaw:
    """The two numbers :func:`is_line_shaped` reads, for a caller that
    holds no ``[rebake]`` table (the split half passes them in).  Any
    object carrying the two attributes serves — the law table itself
    does."""

    line_object_ratio: float
    line_object_max_h: float
    #: spec 2068 A3 R4: the ground-ribbon law (``None``: the y extent)
    ribbon: "RibbonLaw | None" = None


def line_law(law) -> LineLaw:
    """The bound law's whole line reading — 10bb's two ``[rebake]`` keys
    and the ground-ribbon law (:func:`ribbon_law`)."""
    rb = law.tables.structures.rebake
    return LineLaw(float(rb.line_object_ratio), float(rb.line_object_max_h), ribbon_law(law))


@_dc.dataclass(frozen=True)
class Segment:
    """One STATION's share of a line body: the authored triangles whose
    plan centroid is nearest that station, and the station itself."""

    station: tuple[float, float]
    tris: np.ndarray
    index: int


def farthest_point_stations(plan: np.ndarray, k: int, start: int = 0) -> np.ndarray:
    """``k`` indices into ``plan`` ``(n, 2)`` spread by the FARTHEST-POINT
    walk from ``start`` — the ONE spreading rule this tree has (the drape
    stations of 10bb, ``contact._feet``'s thinning, and §10's segment
    stations are the same walk), so a fence's stations do not depend on
    which caller asked for them.  Returns them sorted, deterministic; the
    walk stops early when every remaining point coincides with one
    already chosen."""
    n = int(plan.shape[0])
    if n == 0 or k <= 0:
        return np.zeros((0,), dtype=np.int64)
    if k >= n:
        return np.arange(n, dtype=np.int64)
    start = int(min(max(start, 0), n - 1))
    chosen = [start]
    d2 = ((plan - plan[start]) ** 2).sum(1)
    while len(chosen) < k:
        nxt = int(np.argmax(d2))
        if d2[nxt] <= 0.0:
            break
        chosen.append(nxt)
        d2 = np.minimum(d2, ((plan - plan[nxt]) ** 2).sum(1))
    return np.asarray(sorted(chosen), dtype=np.int64)


def segment_by_station(geom: _obj8.ObjGeometry, tris: np.ndarray,
                       span_m: float, stations_max: int) -> list[Segment]:
    """A LINE BODY cut into SEGMENTS by triangle station (11f (2)).

    ``tris`` are the body's authored triangles ``(n, 3)`` (vertex indices
    into ``geom.vertices``).  The stations are one per ``span_m`` of the
    body's plan extent, capped at ``stations_max``, spread over the
    triangle CENTROIDS by :func:`farthest_point_stations` — the same walk
    that spreads 10bb's drape stations, so a perimeter fence's stations
    follow the LOOP and never chain its two far sides together the way a
    projection onto one principal axis would.  Each triangle joins the
    station nearest its centroid in plan.

    Fewer than two stations (a body shorter than one span, or a cap of
    one) returns ONE segment holding everything — the caller then leaves
    the body exactly as it was."""
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    if t.shape[0] == 0:
        return []
    v = geom.vertices
    cen = (v[t[:, 0]] + v[t[:, 1]] + v[t[:, 2]]) / 3.0
    plan = cen[:, [0, 2]]
    extent = math.hypot(float(plan[:, 0].max() - plan[:, 0].min()),
                        float(plan[:, 1].max() - plan[:, 1].min()))
    k = 1 if span_m <= 0.0 else int(math.ceil(extent / span_m))
    if stations_max > 0:
        k = min(k, int(stations_max))
    k = max(1, k)
    if k < 2:
        return [Segment((float(plan[:, 0].mean()), float(plan[:, 1].mean())), t, 0)]
    # deterministic start: the plan-lexicographically smallest centroid
    start = int(np.lexsort((plan[:, 1], plan[:, 0]))[0])
    st = farthest_point_stations(plan, k, start)
    sp = plan[st]
    d = ((plan[:, None, 0] - sp[None, :, 0]) ** 2
         + (plan[:, None, 1] - sp[None, :, 1]) ** 2)
    owner = np.argmin(d, axis=1)
    out: list[Segment] = []
    for j in range(sp.shape[0]):
        mask = owner == j
        if not mask.any():
            continue
        out.append(Segment((float(sp[j, 0]), float(sp[j, 1])), t[mask], len(out)))
    return out
