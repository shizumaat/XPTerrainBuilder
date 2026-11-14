"""THE GROUND UNDER A DECK BETWEEN TWO SURVEYED UNDERPASS MOUTHS IS THE BORE'S
FLOOR (#1939 round 2 R5, spec ``docs/specs/1939-round2-spec.md``; sibling of
``airport/bridge_ground``).

The survey carries an aeroway deck: a road's profile under it reads the
deck's level (or its smeared faces), and a road that passes under the deck
between the two mouths of a class-K underpass (``planar/underpass_mouth``)
is pulled up to it -- measured ESSA taxiway U: -2811's own profile read
the deck, +1.29 m at site 1, +2.32 m 56.8 m south.  Between the two K mouths
of one deck the ground is the bore's floor: the two mouth lines' surveyed
floors (``Tunnel.survey_floor``) interpolated across the deck.

THE VALUE.  For each pair of K tunnels on one deck the region is the quad
between their mouth edges grown by ``[bridge] ground_probe_dem_cells`` DEM
postings; a sample inside reads the lower of its own value and the floor
(LOWER ONLY: a road already down at the floor is untouched).  The floor at
a point is the two edges' floors at its projections, weighted by its
distance from each.

ONE SITE: ``airport/road_profile.core_profiles`` chains
:func:`bore_sampler` after ``bridge_ground.bridge_sampler`` inside the
patch's band only.  It reads ``pm.structures`` and nothing else, and is the
identity where no K tunnel stands."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon

from ..law import Law
from ..model.structures import UNDERPASS_NOTE

__all__ = ["BoreSpan", "bore_spans", "bore_sampler"]


@_dc.dataclass(frozen=True)
class BoreSpan:
    """The covered stretch between two K mouths of one deck: its region and
    the two mouth edges with their floors ``(z0, k, m0, unit along)``."""

    deck: str
    poly: Polygon
    edges: tuple[LineString, LineString]
    floors: tuple[tuple[float, float, tuple, tuple], tuple[float, float, tuple, tuple]]

    def floor(self, p: Point) -> float:
        """The bore's floor at ``p``: across the deck from one edge to the other."""
        zs, ds = [], []
        for ln, (z0, k, m0, d) in zip(self.edges, self.floors, strict=False):
            q = ln.interpolate(ln.project(p))
            zs.append(z0 + k * ((q.x - m0[0]) * d[0] + (q.y - m0[1]) * d[1]))
            ds.append(ln.distance(p))
        den = ds[0] + ds[1]
        return zs[0] if den <= 1e-9 else (ds[1] * zs[0] + ds[0] * zs[1]) / den


def _edge(tn) -> tuple[LineString, tuple]:
    z0, k, a, b = tn.survey_floor
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    return LineString([a, b]), (float(z0), float(k), tuple(tn.axis[0]),
                                ((b[0] - a[0]) / L, (b[1] - a[1]) / L))


def bore_spans(structures: _t.Sequence, law: Law, dem=None) -> tuple[BoreSpan, ...]:
    """Every pair of class-K tunnels (``Tunnel.survey_floor``) on one deck."""
    by_deck: dict[str, list] = {}
    for tn in structures or ():
        if getattr(tn, "survey_floor", None) is None:
            continue
        deck = next((n[len(UNDERPASS_NOTE):] for n in tn.notes if n.startswith(UNDERPASS_NOTE)),
                    None)
        if deck is not None:
            by_deck.setdefault(deck, []).append(tn)
    post = getattr(dem, "posting_m", None)
    cell = post() if callable(post) else None
    grow = float(law.tables.structures.bridge.ground_probe_dem_cells) * float(cell or 0.0)
    out = []
    for deck, tns in sorted(by_deck.items()):
        for i in range(len(tns)):
            for j in range(i + 1, len(tns)):
                (l1, f1), (l2, f2) = _edge(tns[i]), _edge(tns[j])
                quad = MultiPoint(list(l1.coords) + list(l2.coords)).convex_hull
                if quad.geom_type != "Polygon":
                    continue
                out.append(BoreSpan(deck, quad.buffer(grow, join_style="mitre") if grow else quad,
                                    (l1, l2), (f1, f2)))
    return tuple(out)


def bore_sampler(sample: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                 spans: _t.Sequence[BoreSpan],
                 in_band: _t.Callable[[np.ndarray], np.ndarray] | None = None):
    """``sample`` read over the bores: inside a span (and inside the patch's
    band, ``in_band``) the lower of the sample and the bore's floor;
    ``sample`` itself where no span stands."""
    if not spans:
        return sample

    def _sample(xs, ys):
        xs = np.atleast_1d(np.asarray(xs, float))
        ys = np.atleast_1d(np.asarray(ys, float))
        z = np.array(sample(xs, ys), dtype=float)
        band = None if in_band is None else np.asarray(
            in_band(np.column_stack([xs, ys])), bool)
        for i in range(len(xs)):
            if band is not None and not band[i]:
                continue
            p = Point(float(xs[i]), float(ys[i]))
            fs = [sp.floor(p) for sp in spans if sp.poly.covers(p)]
            if fs and np.isfinite(z[i]) and min(fs) < z[i]:
                z[i] = min(fs)
                _sample.lowered += 1
        return z

    #: stations lowered (the report)
    _sample.lowered = 0
    return _sample
