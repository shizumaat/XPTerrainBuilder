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
import typing as _t

import numpy as np

from . import obj8 as _obj8

__all__ = ["component_shape", "is_line_shaped", "is_line_object", "station_delta",
           "LineLaw", "Segment", "farthest_point_stations", "segment_by_station"]


def component_shape(geom: _obj8.ObjGeometry, comp: _obj8.Component
                    ) -> tuple[float, float, float]:
    """``(length, width, height)`` of one component in the AUTHORED frame:
    the plan-box diagonal, the plan-projected triangle area over it, and
    the y extent.  ``width`` is 0.0 for a purely vertical sheet (a fence
    panel), which is the strongest line reading there is."""
    t = np.asarray(comp.tris)
    v = geom.vertices
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    plan_area = 0.5 * float(np.abs((b[:, 0] - a[:, 0]) * (c[:, 2] - a[:, 2])
                                   - (c[:, 0] - a[:, 0]) * (b[:, 2] - a[:, 2])).sum())
    pts = v[t.reshape(-1)]
    length = math.hypot(float(pts[:, 0].max() - pts[:, 0].min()),
                        float(pts[:, 2].max() - pts[:, 2].min()))
    width = (plan_area / length) if length > 0.0 else 0.0
    return length, width, float(comp.max_y - comp.min_y)


def is_line_shaped(geom: _obj8.ObjGeometry, comp: _obj8.Component, rb) -> bool:
    """One component's verdict (module doc).  A zero-width sheet is a
    line at any length; a degenerate component (no plan extent) is not."""
    if rb.line_object_ratio <= 0.0:
        return False
    length, width, height = component_shape(geom, comp)
    if length <= 0.0 or height >= rb.line_object_max_h:
        return False
    if width <= 0.0:
        return True
    return length / width > rb.line_object_ratio


def is_line_object(cache: _obj8.ResourceCache, resolved: str, rb) -> bool:
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
    return all(is_line_shaped(geom, c, rb) for c in comps)


def station_delta(stations: _t.Sequence[_t.Sequence[float]], lat: float, lon: float
                  ) -> float | None:
    """THE SEGMENT SEAT's lookup (spec §16.1 rule 3): the delta of the
    station NEAREST ``(lat, lon)`` in plan, over rows ``(lat, lon,
    delta)``.  ``None`` when there is no station.  Plan distance in
    degrees scaled by the local metres per degree is monotone with the
    metric one at this scale, and the caller may pass either."""
    best: float | None = None
    best_d = 0.0
    ml = 111_132.954
    mo = 111_412.84 * math.cos(math.radians(lat))
    for la, lo, d in stations:
        dd = ((la - lat) * ml) ** 2 + ((lo - lon) * mo) ** 2
        if best is None or dd < best_d:
            best, best_d = float(d), dd
    return best


def station_deltas_at(stations: _t.Sequence[_t.Sequence[float]],
                      lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """:func:`station_delta` over arrays — the writer's per-vertex drape."""
    st = np.asarray([[float(a), float(b), float(c)] for a, b, c in stations], dtype=float)
    ml = 111_132.954
    mo = 111_412.84 * math.cos(math.radians(float(st[:, 0].mean())))
    dla = (st[None, :, 0] - lats[:, None]) * ml
    dlo = (st[None, :, 1] - lons[:, None]) * mo
    return st[np.argmin(dla * dla + dlo * dlo, axis=1), 2]


# ── THE SEGMENT CUT (owner RULINGS 2026-09-11f (2); spec §10) ────────────

@_dc.dataclass(frozen=True)
class LineLaw:
    """The two numbers :func:`is_line_shaped` reads, for a caller that
    holds no ``[rebake]`` table (the split half passes them in).  Any
    object carrying the two attributes serves — the law table itself
    does."""

    line_object_ratio: float
    line_object_max_h: float


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
