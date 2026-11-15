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
    ``H`` beyond the end line -> ``(height, stack id, deck object id, which
    end, distance to the end line)``.  On a free or kept stack the height is
    the PLATE'S OWN height at the vertex (#2091 R3: an end edge with a
    cross-fall is no one level): ``zero + geom/lowest_face.floor_z_at(plate,
    edge_m=H)``, ``deck_flush_m`` lower inside that deck's ring -- the
    reading the slab block of ``constraints/deck_stack`` uses -- or the end's
    one top where the plate gives none; on a trench stack the end's top.  A
    vertex two end lines claim at TOPS more than ``deck_flush_m`` apart is
    left out (two road ends meeting in plan, v1 §4).  R1 holds these
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
    claims: dict[int, list[tuple[float, tuple[float, str, str, str, float]]]] = {}
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
                ks = [k for k, hit in enumerate(near_stations(rxy, line, 2.0 * H))
                      if hit and (float(off[k]) if off is not None else 0.0) <= slab]
                zs = (_plate_heights(d, [rxy[k] for k in ks], float(top), flush, H)
                      if st.kind != TRENCH else [float(top)] * len(ks))
                for k, z in zip(ks, zs, strict=True):
                    dk = float(off[k]) if off is not None else 0.0
                    claims.setdefault(roads[k], []).append(
                        (float(top), (float(st.zero_z) + z, st.id, d.object_id,
                                      f"{d.object_id}#{d.piece} end {side}", dk)))
    out = {}
    for v, cl in sorted(claims.items()):
        tops = [c[0] for c in cl]
        if max(tops) - min(tops) <= flush:
            out[v] = cl[0][1]
    return out


def _plate_heights(d, xy, top: float, flush: float, edge_m: float) -> list[float]:
    """#2091 R3: the deck plate's own height (over the stack's zero) at each
    road vertex ``xy`` -- ``floor_z_at(plate, edge_m=H)``, ``flush`` lower
    inside the deck's ring; ``top`` (less the same flush) where the plate
    gives none."""
    if not xy:
        return []
    import numpy as np
    import shapely
    from shapely.geometry import Polygon

    from ..geom.lowest_face import floor_z_at
    pts = np.asarray(xy, float).reshape(-1, 2)
    plate = np.asarray(d.plate, float).reshape(-1, 3, 3)
    ys = (floor_z_at(plate, pts[:, 0], pts[:, 1], edge_m=edge_m) if len(plate)
          else np.full(len(pts), np.nan))
    inside = (shapely.contains_xy(Polygon(d.ring), pts[:, 0], pts[:, 1])
              if len(d.ring) >= 3 else np.zeros(len(pts), bool))
    return [(y if y == y else top) - (flush if ins else 0.0)
            for y, ins in zip(ys.tolist(), inside.tolist(), strict=True)]

