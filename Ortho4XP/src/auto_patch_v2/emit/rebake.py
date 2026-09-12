"""THE DECK DATUM off the SOLVED surface.

THE SEAT IS RETIRED (owner RULINGS 2026-09-12s over spec
``object-placement-spec.md`` §8): v1's vertex rewrite of a pack's
``.obj`` files to the built mesh — :func:`seat`, the cluster law
(``emit/clusters.py``), the abutment groups (``emit/abutment_group.py``),
the rigid completion (``airport/rigid.py``), ``engine_v2.
_decision_from_seats`` and the ``o4_v2_rebake_result_*`` sidecars — is a
REFUTED mechanism and is DELETED, not gated (BUILD ECONOMY: "refuted
mechanisms are deleted; the refutation record is the spec and git").
The PLACEMENT path (``airport/placement_*.py``, spec §4/§6) is the only
object stage: X-Plane places every object on the terrain under its own
anchor, and nothing rewrites an authored vertex.

What survives here is the one reading the placement path still takes
from this module: the SOLVED surface's value at a deck, which
``airport/rebake_plan.py`` stamps into the plan's deck members
(``Member.deck_datum_z``) and ``pipeline/build.py`` calls.  No
environment is read here, and nothing here writes.
"""
from __future__ import annotations

import statistics
import typing as _t

import numpy as np

from ..model.frame import XY

__all__ = ["deck_datum_from_surface"]


def deck_datum_from_surface(surface, ring_xy: _t.Sequence[XY], to_xy,
                            buffer_m: float = 0.5) -> float | None:
    """The SOLVED surface's value at a deck: the median ``z`` of the
    graded surface's vertices inside the deck ring (buffered by
    ``buffer_m`` so the ring's own vertices count).  ``None`` when the
    surface has no vertex there (the deck founds no solved value)."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    if surface is None or len(ring_xy) < 3 or not surface.vertices:
        return None
    try:
        poly = Polygon(ring_xy).buffer(buffer_m)
    except Exception:
        return None
    xs = []; ys = []; zs = []
    for sv in surface.vertices:
        x, y = to_xy(sv.ll[1], sv.ll[0])
        xs.append(x); ys.append(y); zs.append(sv.z)
    mask = contains_xy(poly, np.asarray(xs), np.asarray(ys))
    inside = [z for z, m in zip(zs, mask) if m]
    return float(statistics.median(inside)) if inside else None
