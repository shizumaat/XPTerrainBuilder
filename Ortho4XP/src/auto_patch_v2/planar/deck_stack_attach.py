"""THE DECK STACK'S PACK-STAGE CALL (#1971): the thin ``planar`` caller of
``airport/deck_stack`` (spec ``interchange-levels-20261113.md`` §6.1 — the
route walk is ``planar/viaduct_road``'s, which ``airport`` may not import;
the geometry stays in ``airport``).  ``pipeline/build.pack_stage`` and the
replay call :func:`attach_deck_stacks` after the entrance shade.
"""
from __future__ import annotations

from ..airport.deck_stack import attach_stacks
from .viaduct_road import _graph, _route

__all__ = ["attach_deck_stacks"]


def attach_deck_stacks(airport, objects, cache, law, notes_out: "list | None" = None):
    """``airport`` with its deck stacks derived (``airport/deck_stack.
    attach_stacks``), the routes walked as a viaduct's approach is
    (``viaduct_road._route``: the heading-keeping walk through shared
    nodes)."""
    if getattr(airport, "frame", None) is None or law is None or cache is None:
        return airport
    ways = getattr(airport, "osm_ways_mapped", None) or airport.osm_ways
    graph: list = []

    def route_of(w):
        # the node graph is built on the first route asked for: an airport
        # with no floor-datum walls never pays for it
        if not graph:
            graph.append(_graph([q for q in ways if ("highway" in q.tags or "railway" in q.tags)
                                 and len(q.points) >= 2]))
        return _route(w, graph[0], law)

    return attach_stacks(airport, objects, cache, law, route_of, notes_out=notes_out)
