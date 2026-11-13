"""A DECK STACK'S GROUND AND THE ROADS AT ITS DECK ENDS (#1971; spec
``docs/specs/interchange-levels-v2-20261113.md`` §3.2-§3.4):

* :func:`ground_footprint` -- the stack's ground (``geom/deck_ground``,
  re-exported here); ``planar/stack_ground`` mints it,
  ``constraints/fill_bank`` pins its toe;
* :func:`end_road_vertices` -- THE ONE selection of a deck end line's road
  vertices (``model/deck_ends``, re-exported here), read by the end-edge
  rows (``constraints/deck_stack``, R1) and by the road ramp's seeds
  (:func:`deck_end_seeds`, ``airport/road_ramp.road_ramp_targets(deck_ends=...)``).

The two derivations live below ``airport`` so ``constraints`` may read them
(test_model.test_dependency_direction); this module keeps the ramp's seeds
and owner question Q1.  Nothing here names an airport.
"""
from __future__ import annotations

from ..geom.deck_ground import GROUND_TO_WALL_TOP, ground_footprint, ring_polygon
from ..model.deck_ends import end_road_vertices

__all__ = ["ground_footprint", "end_road_vertices", "deck_end_seeds", "ring_polygon",
           "DECK_END_RAMP", "GROUND_TO_WALL_TOP"]

#: OWNER QUESTION Q1 (spec ``interchange-levels-v2-20261113.md`` §10), the
#: spec's DEFAULT (yes) until answered: on the approach to a pack deck the
#: road ramps from the deck's end at the design grade and its 0.5 m ceiling
#: is measured from that ramp (:func:`deck_end_seeds`).  A "no" is
#: ``False`` here: no seed, the ceiling is measured from the lidar again.
DECK_END_RAMP = True


def deck_end_seeds(pm, law, airport) -> dict[int, tuple[float, float]]:
    """``{vertex: (zero + top_e, distance to the end line)}`` (v2 §3.4): the
    end-line road vertices (:func:`end_road_vertices`), where the road ramp
    is seeded as at a foot lot (``airport/road_ramp.road_ramp_targets(
    deck_ends=...)``; the hold is the slab left beyond the vertex).  ``{}``
    while owner question Q1 reads "no" (:data:`DECK_END_RAMP`)."""
    if not DECK_END_RAMP:
        return {}
    return {v: (z, off) for v, (z, *_r, off) in end_road_vertices(pm, law, airport).items()}
