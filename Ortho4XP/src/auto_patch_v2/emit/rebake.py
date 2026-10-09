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

STANDING CELLS ONLY (spec §60 (9) R2; §53 (18) "a gap piece never leads").
A §53 gap piece is minted beside the objects, after them: a datum read off
the solved surface for an object never reads a vertex that only gap pieces
own (:func:`standing_vertex_ids`).  A piece's vertex shared with a standing
cell is that cell's and counts; the after-mesh abutment walk reads the built
ground, pieces included.
"""
from __future__ import annotations

import statistics
import typing as _t

import numpy as np

from ..model.frame import XY
from ..model.planar import is_gap_ref

__all__ = ["deck_datum_from_surface", "standing_vertex_ids"]


def standing_vertex_ids(surface) -> frozenset[int]:
    """The surface's vertices a datum may read (module docstring): every
    vertex but those owned by gap pieces ALONE."""
    late: set[int] = set()
    standing: set[int] = set()
    for f in surface.faces:
        (late if is_gap_ref(f.ref) else standing).update(f.ring, *f.holes)
    late -= standing
    return frozenset(sv.id for sv in surface.vertices if sv.id not in late)


def deck_datum_from_surface(surface, ring_xy: _t.Sequence[XY], to_xy,
                            buffer_m: float = 0.5) -> float | None:
    """The SOLVED surface's value at a deck: the median ``z`` of the
    graded surface's STANDING vertices (:func:`standing_vertex_ids`) inside
    the deck ring (buffered by ``buffer_m`` so the ring's own vertices
    count).  ``None`` when the surface has no such vertex there (the deck
    founds no solved value)."""
    from shapely import contains_xy
    from shapely.geometry import Polygon
    if surface is None or len(ring_xy) < 3 or not surface.vertices:
        return None
    try:
        poly = Polygon(ring_xy).buffer(buffer_m)
    except Exception:
        return None
    xs = []; ys = []; zs = []
    standing = standing_vertex_ids(surface)
    for sv in surface.vertices:
        if sv.id not in standing:
            continue
        x, y = to_xy(sv.ll[1], sv.ll[0])
        xs.append(x); ys.append(y); zs.append(sv.z)
    mask = contains_xy(poly, np.asarray(xs), np.asarray(ys))
    inside = [z for z, m in zip(zs, mask) if m]
    return float(statistics.median(inside)) if inside else None
