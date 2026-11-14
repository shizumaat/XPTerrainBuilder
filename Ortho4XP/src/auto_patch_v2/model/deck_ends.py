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


def end_road_vertices(pm, law, airport) -> dict[int, tuple[float, str, str, str, float]]:
    """THE END-LINE ROAD VERTICES, ONE selection (v2 §3.4): every road
    vertex (``ROAD_ROLES``, on no structure face) within two ``[bridge]
    abutment_sample_step_m`` of a deck end line's station (``geom/end_line.
    near_stations``) and on the approach slab, at most one sample step
    ``H`` beyond the end line -> ``(zero + the plate's top there, stack id,
    deck object id, which end, distance to the end line)``.  A vertex two
    end lines claim at heights more than ``deck_flush_m`` apart is left out
    (two road ends meeting in plan, v1 §4).  R1 holds these
    (``constraints/deck_stack``); the road ramp is seeded at them
    (``airport/deck_ends.deck_end_seeds``), each with the rest of the slab
    beyond it as its hold.  (The ribbon carries a vertex every ``H`` there,
    ``planar/stack_ground.deck_end_road_zone``: a vertex past the slab is
    on the ramp, never held at the plate.)"""
    from ..geom.end_line import near_stations, polyline_distance
    from .deck_stack import TRENCH, live_stacks
    stacks = live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), pm)
    if not stacks:
        return {}
    br = law.tables.structures.bridge
    flush = float(br.deck_flush_m)
    H = float(br.abutment_sample_step_m)
    slab = H + float(law.tables.emit.identity.min_distinct_spacing_m)
    roads = _road_vertices(pm, law)
    if not roads:
        return {}
    rxy = [pm.vertices[v].xy for v in roads]
    claims: dict[int, list[tuple[float, str, str, str, float]]] = {}
    for st in stacks:
        for d in st.decks:
            for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b)):
                if not line:
                    continue
                if st.kind != TRENCH:
                    # #2065 A3 rule 5: a free / kept stack's ROWED ends only
                    t = st.end_top(d.object_id, side)
                    if t is None:
                        continue
                    top = t
                off = polyline_distance(rxy, line) if len(line) >= 2 else None
                for k in (k for k, hit in enumerate(near_stations(rxy, line, 2.0 * H)) if hit):
                    dk = float(off[k]) if off is not None else 0.0
                    if dk > slab:
                        continue
                    claims.setdefault(roads[k], []).append(
                        (float(st.zero_z) + float(top), st.id, d.object_id,
                         f"{d.object_id}#{d.piece} end {side}", dk))
    out = {}
    for v, cl in sorted(claims.items()):
        zs = [c[0] for c in cl]
        if max(zs) - min(zs) <= flush:
            out[v] = cl[0]
    return out

