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

__all__ = ["end_road_vertices", "access_road_vertices", "way_of_ref", "sibling_ends",
           "between_siblings", "end_mid"]


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


def end_mid(stations) -> tuple[float, float]:
    """The mean of an end line's stations."""
    return (sum(p[0] for p in stations) / len(stations),
            sum(p[1] for p in stations) / len(stations))


def sibling_ends(stacks, on_road=None, reach: float = 0.0) -> dict[tuple, list]:
    """#2090 B4 THE SIBLING ENDS: per ``DeckStack.access_key`` (a deck join's
    floor, or the line a riding deck rides), the GRADED land ends carrying an
    access road (``StackEnd.access``) as ``[(stack, end)]``, ordered along
    the line through their end lines' middles, keyed ``(member, y_floor,
    k)``.  ``on_road(xy, ways, reach) -> bool`` (given) splits them into
    LINES (``k``): two consecutive ends are on one line only where the access
    road runs between them — an access way of either within the wider end
    line's half width plus ``reach`` of the middle between them (one floor's
    ends on two roads, e.g. both sides of a building, are two lines)."""
    sib: dict[tuple[str, float], list] = {}
    for st in stacks:
        key = getattr(st, "access_key", None)
        if key is None:
            continue
        for e in st.graded_ends():
            if e.access:
                sib.setdefault(key, []).append((st, e))
    out: dict[tuple, list] = {}
    for key, ends in sib.items():
        mids = [end_mid(e.stations) for _st, e in ends]
        ax = (mids[-1][0] - mids[0][0], mids[-1][1] - mids[0][1])
        order = sorted(range(len(ends)), key=lambda k, m=mids: m[k][0] * ax[0] + m[k][1] * ax[1])
        lines = [[ends[order[0]]]]
        for i0, i1 in zip(order, order[1:], strict=False):
            (_s0, e0), (_s1, e1) = ends[i0], ends[i1]
            mid = ((mids[i0][0] + mids[i1][0]) / 2.0, (mids[i0][1] + mids[i1][1]) / 2.0)
            if on_road is not None and not on_road(
                    mid, {int(w) for w in (*e0.access, *e1.access)},
                    max(e0.half_width, e1.half_width) + float(reach)):
                lines.append([])
            lines[-1].append(ends[i1])
        for k, line in enumerate(lines):
            out[(key[0], key[1], k)] = line
    return out


def _road_faces_near(pm):
    """``on_road`` of :func:`sibling_ends` over the planar map: the boundary
    of a road face (``ROAD_ROLES``) of one of the ways within ``reach`` of
    ``xy`` (a ribbon is narrower than any reach asked, so a point on it is
    near its boundary)."""
    from ..geom.end_line import polyline_distance
    from .planar import ROAD_ROLES
    by_way: dict[int, list] = {}
    for f in pm.faces.values():
        w = way_of_ref(f.ref) if f.role in ROAD_ROLES else None
        if w is not None:
            ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
            if len(ring) >= 3:
                by_way.setdefault(w, []).append([*ring, ring[0]])

    def on_road(xy, ways, reach: float) -> bool:
        p = [(float(xy[0]), float(xy[1]))]
        return any(float(polyline_distance(p, ring)[0]) <= reach
                   for w in ways for ring in by_way.get(w, ()))
    return on_road


def between_siblings(ends, xy, reach: float):
    """``(level, nearer (stack, end))`` of plan point ``xy`` standing between
    two consecutive sibling ends of ``ends`` (:func:`sibling_ends`' order):
    its projection on the segment between their end lines' middles inside
    it and within the wider end line's half width plus ``reach`` of it — the
    level on the line between the two ends' levels; ``None`` elsewhere."""
    x, y = float(xy[0]), float(xy[1])
    for (s0, e0), (s1, e1) in zip(ends, ends[1:], strict=False):
        a, b = end_mid(e0.stations), end_mid(e1.stations)
        dx, dy = b[0] - a[0], b[1] - a[1]
        ll = dx * dx + dy * dy
        if ll <= 0.0:
            continue
        t = ((x - a[0]) * dx + (y - a[1]) * dy) / ll
        if not 0.0 < t < 1.0:
            continue
        if abs((x - a[0]) * dy - (y - a[1]) * dx) / ll ** 0.5 > max(e0.half_width,
                                                                     e1.half_width) + reach:
            continue
        z0, z1 = float(s0.zero_z) + float(e0.top), float(s1.zero_z) + float(e1.top)
        return z0 + t * (z1 - z0), ((s0, e0) if t < 0.5 else (s1, e1))
    return None


def access_road_vertices(pm, law, airport) -> dict[int, tuple[float, str, str, str, float]]:
    """#2090 B4 THE ACCESS ROAD BETWEEN SIBLING DECK ENDS: the kept stacks
    whose deck JOINS an AGP follower's floor (``DeckStack.joins``) or rides
    the access road those ends hold (``DeckStack.rides``, B4b), and whose
    end is GRADED on an at-grade road passing its line (``StackEnd.access``);
    ends of one ``DeckStack.access_key`` on one access road are siblings
    (:func:`sibling_ends`, its lines split by :func:`_road_faces_near`).
    Every road vertex of their access ways standing between two consecutive
    siblings (:func:`between_siblings`, reach one ``[bridge]
    abutment_sample_step_m`` — the ribbon's far edge) -> ``(the level on the
    line between the two ends' levels, the nearer end's stack id, deck
    object id, which end, 0.0)`` — the shape of :func:`end_road_vertices`,
    so R1 holds them and the road ramp is seeded at them; the road's own
    ramp then runs from the outermost ends."""
    from .deck_stack import live_stacks
    from .planar import ROAD_ROLES
    reach = float(law.tables.structures.bridge.abutment_sample_step_m) if law is not None else 0.0
    sib = {k: v for k, v in sibling_ends(live_stacks(
        tuple(getattr(airport, "deck_stacks", ()) or ()), pm), _road_faces_near(pm),
        reach).items() if len(v) >= 2}
    if not sib:
        return {}
    ways = {int(w) for ends in sib.values() for _st, e in ends for w in e.access}
    verts: set[int] = set()
    for f in pm.faces.values():
        if f.role in ROAD_ROLES and way_of_ref(f.ref) in ways:
            verts.update(pm.ring_vertices(f.ring))
    out: dict[int, tuple[float, str, str, str, float]] = {}
    for ends in sib.values():
        for v in sorted(verts):
            got = between_siblings(ends, pm.vertices[v].xy, reach)
            if got is None:
                continue
            z, (st, e) = got
            out.setdefault(v, (z, st.id, e.object_id,
                               f"{e.object_id}#0 end {e.side} access road", 0.0))
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
    from ..geom.plate_heights import plate_heights
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
                zs = (plate_heights(d, [rxy[k] for k in ks], float(top), flush, H)
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


