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
    out = {v: (z, off) for v, (z, *_r, off) in end_road_vertices(pm, law, airport).items()}
    for v, z in _crossing_vertices(pm, law, airport).items():
        out.setdefault(v, (z, 0.0))             # #2065 A3 rule 6: an at-grade crossing
    return out


def _way_of(ref: str) -> "int | None":
    """The mapped way id a road ribbon face's ref names (``<class>:<way>``)."""
    tail = str(ref).split("#", 1)[0].rsplit(":", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return None


def _crossing_vertices(pm, law, airport) -> dict[int, float]:
    """#2065 A3 rule 6: ``{vertex: P(s)}`` of every road vertex of an AT-GRADE
    way crossing a GRADED end's corridor (``StackEnd.crossings``) inside it —
    seeded at the ramp's height there through the deck ends' map
    (``airport/deck_ends.deck_end_seeds``).  ``{}`` without one."""
    import shapely
    from shapely.geometry import Point

    from ..geom.deck_ground import path_line
    from ..model.deck_stack import live_stacks
    stacks = live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), pm)
    ends = [(st, e) for st in stacks for e in st.graded_ends() if e.crossings]
    if not ends:
        return {}
    from ..model.planar import ROAD_ROLES
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    by_way: dict[int, set[int]] = {}
    for f in pm.faces.values():
        if f.role not in ROAD_ROLES:
            continue
        w = _way_of(f.ref)
        if w is not None:
            by_way.setdefault(w, set()).update(pm.ring_vertices(f.ring))
    out: dict[int, float] = {}
    for st, e in ends:
        line = path_line(e, e.run)
        if line is None:
            continue
        corridor = line.buffer(e.half_width, cap_style="flat")
        for w in e.crossings:
            for v in sorted(by_way.get(int(w), ())):
                xy = pm.vertices[v].xy
                if not shapely.contains_xy(corridor, xy[0], xy[1]):
                    continue
                p = e.profile(st.zero_z, line.project(Point(xy)), step)
                out[v] = max(out.get(v, -1e9), p)
    return out
