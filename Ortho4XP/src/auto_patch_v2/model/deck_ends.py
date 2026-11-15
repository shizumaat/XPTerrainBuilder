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

__all__ = ["end_road_vertices", "access_road_vertices", "way_of_ref"]


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


def way_of_ref(ref: str) -> "int | None":
    """The mapped way id a road ribbon face's ref names (``<class>:<way>``)."""
    tail = str(ref).split("#", 1)[0].rsplit(":", 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return None


def access_road_vertices(pm, law, airport) -> dict[int, tuple[float, str, str, str, float]]:
    """#2090 B4 THE ACCESS ROAD BETWEEN SIBLING DECK ENDS: the kept stacks
    whose deck JOINS an AGP follower's floor (``DeckStack.joins``) and whose
    other end is GRADED on an at-grade road passing its line
    (``StackEnd.access``); ends whose stacks join the SAME floor (same
    member, same ``y``) are siblings, taken in order along the line through
    them.  Every road vertex of their access ways standing between two
    consecutive siblings (its projection on the segment between their end
    lines' middles inside it, within the wider end line's half width of it)
    -> ``(the level on the line between the two ends' levels, the nearer
    end's stack id, deck object id, which end, 0.0)`` — the shape of
    :func:`end_road_vertices`, so R1 holds them and the road ramp is seeded
    at them; the road's own ramp then runs from the outermost ends."""
    from .deck_stack import live_stacks
    from .planar import ROAD_ROLES
    stacks = [st for st in live_stacks(tuple(getattr(airport, "deck_stacks", ()) or ()), pm)
              if getattr(st, "datum_group", "") and getattr(st, "joins", ())]
    sib: dict[tuple[str, float], list] = {}
    for st in stacks:
        j = st.joins[0]
        for e in st.graded_ends():
            if e.access:
                sib.setdefault((j.member, round(float(j.y_floor), 2)), []).append((st, e))
    sib = {k: v for k, v in sib.items() if len(v) >= 2}
    if not sib:
        return {}
    ways = {int(w) for ends in sib.values() for _st, e in ends for w in e.access}
    verts: set[int] = set()
    for f in pm.faces.values():
        if f.role in ROAD_ROLES and way_of_ref(f.ref) in ways:
            verts.update(pm.ring_vertices(f.ring))
    out: dict[int, tuple[float, str, str, str, float]] = {}
    for ends in sib.values():
        mids = [(sum(p[0] for p in e.stations) / len(e.stations),
                 sum(p[1] for p in e.stations) / len(e.stations)) for _st, e in ends]
        ax = (mids[-1][0] - mids[0][0], mids[-1][1] - mids[0][1])
        order = sorted(range(len(ends)), key=lambda k: mids[k][0] * ax[0] + mids[k][1] * ax[1])
        for k0, k1 in zip(order, order[1:], strict=False):
            (s0, e0), (s1, e1) = ends[k0], ends[k1]
            a, b = mids[k0], mids[k1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ll = dx * dx + dy * dy
            if ll <= 0.0:
                continue
            z0, z1 = float(s0.zero_z) + float(e0.top), float(s1.zero_z) + float(e1.top)
            half = max(e0.half_width, e1.half_width)
            for v in sorted(verts):
                x, y = pm.vertices[v].xy
                t = ((x - a[0]) * dx + (y - a[1]) * dy) / ll
                if not 0.0 < t < 1.0:
                    continue
                lat = abs((x - a[0]) * dy - (y - a[1]) * dx) / ll ** 0.5
                if lat > half:
                    continue
                st, e = (s0, e0) if t < 0.5 else (s1, e1)
                out.setdefault(v, (z0 + t * (z1 - z0), st.id, e.object_id,
                                   f"{e.object_id}#0 end {e.side} access road", 0.0))
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

