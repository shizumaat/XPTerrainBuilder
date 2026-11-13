"""THE ROADS AT A DECK STACK'S DECK ENDS (#1971; spec
``docs/specs/interchange-levels-v2-20261113.md`` §3.4):
:func:`end_road_vertices` -- THE ONE selection of a deck end line's road
vertices, read by the end-edge rows (``constraints/deck_stack``, R1) and by
the road ramp's seeds (``airport/deck_ends.deck_end_seeds``,
``airport/road_ramp.road_ramp_targets(deck_ends=...)``).

In ``model`` (it reads only ``geom``, ``law`` and ``model``) so both the
``constraints`` and the ``airport`` layers may import it
(test_model.test_dependency_direction).  Nothing here names an airport.
"""
from __future__ import annotations

__all__ = ["end_road_vertices"]


def _road_vertices(pm, law) -> list[int]:
    """Vertices of a road face standing on no structure face."""
    from ..law.tables import is_structure_role
    from .planar import ROAD_ROLES
    out = []
    for v, vx in pm.vertices.items():
        roles = [pm.faces[f].role for f in vx.incident_faces if f in pm.faces]
        if any(r in ROAD_ROLES for r in roles) and not any(is_structure_role(law, r)
                                                           for r in roles):
            out.append(v)
    return out


def end_road_vertices(pm, law, airport) -> dict[int, tuple[float, str, str, str]]:
    """THE END-LINE ROAD VERTICES, ONE selection (v2 §3.4): every road
    vertex (``ROAD_ROLES``, on no structure face) within two ``[bridge]
    abutment_sample_step_m`` of a deck end line's station (``geom/end_line.
    near_stations``) -> ``(zero + the plate's top there, stack id, deck
    object id, which end)``.  A vertex two end lines claim at heights more
    than ``deck_flush_m`` apart is left out (two road ends meeting in
    plan, v1 §4).  R1 holds these (``constraints/deck_stack``); the road
    ramp is seeded at them (``airport/deck_ends.deck_end_seeds``)."""
    from ..geom.end_line import near_stations
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks:
        return {}
    br = law.tables.structures.bridge
    flush = float(br.deck_flush_m)
    reach = 2.0 * float(br.abutment_sample_step_m)
    roads = _road_vertices(pm, law)
    if not roads:
        return {}
    rxy = [pm.vertices[v].xy for v in roads]
    claims: dict[int, list[tuple[float, str, str, str]]] = {}
    for st in stacks:
        for d in st.decks:
            for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b)):
                if not line:
                    continue
                for k in (k for k, hit in enumerate(near_stations(rxy, line, reach)) if hit):
                    claims.setdefault(roads[k], []).append(
                        (float(st.zero_z) + float(top), st.id, d.object_id,
                         f"{d.object_id}#{d.piece} end {side}"))
    out = {}
    for v, cl in sorted(claims.items()):
        zs = [c[0] for c in cl]
        if max(zs) - min(zs) <= flush:
            out[v] = cl[0]
    return out
