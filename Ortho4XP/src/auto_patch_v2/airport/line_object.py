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

import math
import typing as _t

import numpy as np

from . import obj8 as _obj8

__all__ = ["component_shape", "is_line_shaped", "is_line_object", "station_delta"]


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
