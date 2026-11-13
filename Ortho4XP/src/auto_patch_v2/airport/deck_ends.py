"""A DECK STACK'S GROUND AND THE ROADS AT ITS DECK ENDS (#1971; spec
``docs/specs/interchange-levels-v2-20261113.md`` §3.2-§3.4), read off the
derived record (``model/deck_stack.DeckStack``, ``airport/deck_stack``):

* :func:`ground_footprint` -- the stack's ground before any other region
  cuts it: the caps, each deck's shadow, the bank to the lidar and its
  outline (whose edge off the floor is the TOE); ``planar/stack_ground``
  mints it, ``constraints/fill_bank`` pins its toe;
* :func:`end_road_vertices` -- THE ONE selection of a deck end line's road
  vertices, read by the end-edge rows (``constraints/deck_stack``, R1) and
  by the road ramp's seeds (:func:`deck_end_seeds`,
  ``airport/road_ramp.road_ramp_targets(deck_ends=...)``).

Kept apart from ``airport/deck_stack`` (the derivation, which reads the
pack's geometry) so the planar, constraint and ramp stages that read the
record do not key on the pack readers.  Nothing here names an airport.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["ground_footprint", "end_road_vertices", "deck_end_seeds", "ring_polygon",
           "DECK_END_RAMP", "GROUND_TO_WALL_TOP"]

#: OWNER QUESTION Q1 (spec ``interchange-levels-v2-20261113.md`` §10), the
#: spec's DEFAULT (yes) until answered: on the approach to a pack deck the
#: road ramps from the deck's end at the design grade and its 0.5 m ceiling
#: is measured from that ramp (:func:`deck_end_seeds`).  A "no" is
#: ``False`` here: no seed, the ceiling is measured from the lidar again.
DECK_END_RAMP = True
#: OWNER QUESTION Q2 (same §10), the spec's DEFAULT (yes): the ground is
#: graded to the walls' top along the trench (the caps) with a bank to the
#: real ground beyond them.  A "no" is ``False`` here: no cap piece and no
#: bank round the caps (the ground under and off the decks' ends stays).
GROUND_TO_WALL_TOP = True


def ring_polygon(ring) -> "Polygon | None":
    """``ring`` as a valid polygon, or ``None`` (under 3 points, empty)."""
    if len(ring) < 3:
        return None
    p = Polygon(ring)
    p = p if p.is_valid else p.buffer(0.0)
    return None if p.is_empty else p


def _deck_rect(d) -> Polygon:
    """A deck piece's plan rectangle (the minimum rotated rectangle its end
    lines are the short sides of, ``deck_carry._edges``)."""
    return Polygon(d.ring).minimum_rotated_rectangle


def _end_length(st, d, side: str, top: float, law) -> float:
    """``L_e`` (v2 §3.2): how far beyond an end line the ground comes off
    the deck as the road does — ``|G_e - (zero + top_e)| / ramp_grade +
    abutment_sample_step_m``, clamped to ``[bank_min_width_m, 2 x
    platform_collar_max_m]``."""
    de = law.tables.emit.design
    lo = float(de.bank_min_width_m)
    hi = 2.0 * float(law.tables.structures.building_pad.platform_collar_max_m)
    g = st.ground_m(d.object_id, d.piece, side)
    if g is None:
        return lo
    run = abs(g - (st.zero_z + top)) / float(law.tables.emit.road_contact.ramp_grade)
    return min(hi, max(lo, run + float(law.tables.structures.bridge.abutment_sample_step_m)))


def _deck_zone(st, d, rect: Polygon, law) -> Polygon:
    """The ground a deck piece's bank covers (v2 §3.2): ``ground_margin_m``
    beside its side edges, ``L_e`` and the plate's width beyond each end
    line, the corners closed (the hull of the three)."""
    c = rect.centroid
    parts = [rect]
    for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b)):
        if len(line) < 2:
            continue
        mx = sum(p[0] for p in line) / len(line)
        my = sum(p[1] for p in line) / len(line)
        n = math.hypot(mx - c.x, my - c.y) or 1.0
        ox, oy = (mx - c.x) / n, (my - c.y) / n
        L = _end_length(st, d, side, top, law)
        (ax, ay), (bx, by) = line[0], line[-1]
        parts.append(Polygon([(ax, ay), (bx, by), (bx + ox * L, by + oy * L),
                              (ax + ox * L, ay + oy * L)]))
    B = float(st.ground_margin_m)
    cs = list(rect.exterior.coords)[:4]
    edges = sorted(((cs[k], cs[(k + 1) % 4]) for k in range(4)),
                   key=lambda e: -math.dist(*e))[:2]            # the side edges
    for (px, py), (qx, qy) in edges if B > 0.0 else ():
        mx, my = (px + qx) / 2.0 - c.x, (py + qy) / 2.0 - c.y
        n = math.hypot(mx, my) or 1.0
        ox, oy = mx / n * B, my / n * B
        parts.append(Polygon([(px, py), (qx, qy), (qx + ox, qy + oy), (px + ox, py + oy)]))
    return unary_union(parts).convex_hull


def _slab(d, line, rect: Polygon, H: float) -> Polygon:
    """The APPROACH SLAB beyond an end line: the plate's width for one
    ``abutment_sample_step_m`` (``H``) outward -- where the road keeps the
    deck's level (the ramp's hold, v2 §3.4) and so does the ground beside
    it."""
    c = rect.centroid
    mx = sum(p[0] for p in line) / len(line)
    my = sum(p[1] for p in line) / len(line)
    n = math.hypot(mx - c.x, my - c.y) or 1.0
    ox, oy = (mx - c.x) / n * H, (my - c.y) / n * H
    (ax, ay), (bx, by) = line[0], line[-1]
    return Polygon([(ax, ay), (bx, by), (bx + ox, by + oy), (ax + ox, ay + oy)])


def ground_footprint(st, law) -> dict:
    """The stack's ground before any other region cuts it (v2 §3.2), in
    the order of precedence: ``caps`` (the crest plates, when
    :data:`GROUND_TO_WALL_TOP`), ``shadows`` ``[(deck, polygon)]`` (each
    deck piece's rectangle less the caps, a cell two rectangles share the
    lower level's), ``slabs`` ``[(deck, side, top, polygon)]`` (the
    approach slab beyond each end line, :func:`_slab`: held at the plate's
    top with the end edge, R1), ``bank`` (what joins those to the lidar),
    ``outline`` (their union: its edge off the floor is the TOE) and
    ``keep`` (the floor and its void band, which no piece takes)."""
    band = 0.5 * float(law.tables.structures.tunnel.object.wall_face_max_thickness_m)
    rings = [st.floor, *(r for r, _a, _b in st.runouts)]
    keep = unary_union([p for p in map(ring_polygon, rings) if p]).buffer(band, join_style="mitre")
    caps = unary_union([p for p in (ring_polygon(c) for c in st.caps) if p]) \
        if GROUND_TO_WALL_TOP and st.caps else Polygon()
    H = float(law.tables.structures.bridge.abutment_sample_step_m)
    shadows, taken, zones, ends = [], caps, [], []
    for d in sorted(st.decks, key=lambda d: (d.level, d.object_id, d.piece)):
        rect = _deck_rect(d)
        shadows.append((d, rect.difference(taken).difference(keep)))
        taken = taken.union(rect)
        zones.append(_deck_zone(st, d, rect, law))
        ends += [(d, side, top, _slab(d, line, rect, H))
                 for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b))
                 if len(line) >= 2]
    import shapely
    slabs = []
    for d, side, top, g in ends:            # on a fine grid: a slab shares its end line
        g = shapely.difference(shapely.difference(g, taken, grid_size=1e-6), keep,
                               grid_size=1e-6)
        slabs.append((d, side, top, g))
        taken = shapely.union(taken, g, grid_size=1e-6)
    if GROUND_TO_WALL_TOP and not caps.is_empty and st.ground_margin_m > 0.0:
        zones.append(caps.buffer(float(st.ground_margin_m)))
    outline = unary_union([taken, *zones])
    return {"caps": caps.difference(keep), "shadows": shadows, "slabs": slabs,
            "bank": outline.difference(taken).difference(keep), "outline": outline,
            "keep": keep}


def _road_vertices(pm, law) -> list[int]:
    """Vertices of a road face standing on no structure face."""
    from ..law.tables import is_structure_role
    from ..model.planar import ROAD_ROLES
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
    ramp is seeded at them (:func:`deck_end_seeds`)."""
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
    rxy = np.array([pm.vertices[v].xy for v in roads], float)
    claims: dict[int, list[tuple[float, str, str, str]]] = {}
    for st in stacks:
        for d in st.decks:
            for side, line, top in (("a", d.end_a, d.top_a), ("b", d.end_b, d.top_b)):
                if not line:
                    continue
                for k in np.flatnonzero(near_stations(rxy, line, reach)).tolist():
                    claims.setdefault(roads[k], []).append(
                        (float(st.zero_z) + float(top), st.id, d.object_id,
                         f"{d.object_id}#{d.piece} end {side}"))
    out = {}
    for v, cl in sorted(claims.items()):
        zs = [c[0] for c in cl]
        if max(zs) - min(zs) <= flush:
            out[v] = cl[0]
    return out


def deck_end_seeds(pm, law, airport) -> dict[int, float]:
    """``{vertex: zero + top_e}`` (v2 §3.4): the end-line road vertices
    (:func:`end_road_vertices`), where the road ramp is seeded as at a foot
    lot (``airport/road_ramp.road_ramp_targets(deck_ends=...)``).  ``{}``
    while owner question Q1 reads "no" (:data:`DECK_END_RAMP`)."""
    if not DECK_END_RAMP:
        return {}
    return {v: z for v, (z, *_r) in end_road_vertices(pm, law, airport).items()}
