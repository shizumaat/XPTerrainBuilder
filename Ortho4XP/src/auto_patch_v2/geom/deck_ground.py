"""A DECK STACK'S GROUND (#1971; spec
``docs/specs/interchange-levels-v2-20261113.md`` §3.2-§3.3), read off the
derived record (``model/deck_stack.DeckStack``): :func:`ground_footprint`
-- the stack's ground before any other region cuts it: the caps, each
deck's shadow, the bank to the lidar and its outline (whose edge off the
floor is the TOE); ``planar/stack_ground`` mints it,
``constraints/fill_bank`` and ``constraints/deck_stack`` pin it.

Pure shape on the duck-typed record and law (no v2 import above
``geom``), so the planar and constraint stages share ONE derivation
(test_model.test_dependency_direction); ``airport/deck_ends`` re-exports
it.  Nothing here names an airport.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .rotated_rect import rotated_rectangle

__all__ = ["end_aprons", "ground_footprint", "ring_polygon", "path_line", "GROUND_TO_WALL_TOP"]

#: OWNER QUESTION Q2 (spec ``interchange-levels-v2-20261113.md`` §10),
#: the spec's DEFAULT (yes): the ground is graded to the walls' top along the trench (the caps) with a bank to the
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
    return rotated_rectangle(Polygon(d.ring))


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


def _beyond(line, rect: Polygon, depth: float) -> Polygon:
    """The plate's width beyond an end line, ``depth`` metres outward
    (away from the deck's rectangle)."""
    c = rect.centroid
    mx = sum(p[0] for p in line) / len(line)
    my = sum(p[1] for p in line) / len(line)
    n = math.hypot(mx - c.x, my - c.y) or 1.0
    ox, oy = (mx - c.x) / n * depth, (my - c.y) / n * depth
    (ax, ay), (bx, by) = line[0], line[-1]
    return Polygon([(ax, ay), (bx, by), (bx + ox, by + oy), (ax + ox, ay + oy)])


def _ends(d) -> list:
    """``[(side, end line, top)]`` of a deck piece's end lines."""
    return [(side, line, top) for side, line, top in (("a", d.end_a, d.top_a),
                                                      ("b", d.end_b, d.top_b)) if len(line) >= 2]


def end_aprons(st, law) -> list[Polygon]:
    """Each deck end's APRON before any region cuts it: the plate's width
    beyond the end line for ``L_e`` (v2 §3.2) -- where the road and the
    ground beside it come off the deck (``planar/overlay`` densifies the
    road's ribbon there, v2 §3.4).  A free / kept stack's: each rowed end's
    apron (#2065 A3 rule 4, :func:`_free_footprint`)."""
    if getattr(st, "kind", "trench") != "trench":
        return [a for _d, _s, _t, a, _sl in _free_footprint(st, law)["aprons"]
                if not a.is_empty]
    return [_beyond(line, _deck_rect(d), _end_length(st, d, side, top, law))
            for d in st.decks for side, line, top in _ends(d)]


def path_line(e, length: float):
    """A free / kept stack end's PATH (``StackEnd.path``), its first
    ``length`` metres (``None`` without a path)."""
    from shapely.geometry import LineString
    from shapely.ops import substring
    if len(e.path) < 2:
        return None
    line = LineString(e.path)
    if line.length <= 0.0:
        return None
    return line if line.length <= length else substring(line, 0.0, length)


def _slab(e, depth: float) -> Polygon:
    """The end line swept ``depth`` metres along its outward tangent (an
    end's SLAB, rule 4: its first step)."""
    (ax, ay), (bx, by) = e.stations[0], e.stations[-1]
    if len(e.stations) < 2 or math.dist((ax, ay), (bx, by)) < 1e-6:
        mx, my = e.stations[0]
        nx, ny = -e.out[1], e.out[0]
        ax, ay, bx, by = mx - nx * 0.5, my - ny * 0.5, mx + nx * 0.5, my + ny * 0.5
    ox, oy = e.out[0] * depth, e.out[1] * depth
    p = Polygon([(ax, ay), (bx, by), (bx + ox, by + oy), (ax + ox, ay + oy)])
    return p if p.is_valid else p.buffer(0.0)


def _free_footprint(st, law) -> dict:
    """A FREE / KEPT stack's ground (#2065 A3 rule 4): per rowed end the
    SLAB (its first ``abutment_sample_step_m``) and, at a GRADED end, the
    APRON — the path's first RUN metres buffered half the end line's length,
    flat caps (it follows the road; no length cap, 14e) — and the BANK, the
    apron grown by ``max(bank_min_width_m, gap / bank_slope)``.  No bank
    beside the deck's sides, no caps, no floor; the decks' rings are no
    ground.  ``keep``: the rings and the slabs, whose edges are no toe."""
    de = law.tables.emit.design
    H = float(law.tables.structures.bridge.abutment_sample_step_m)
    rings = unary_union([ring_polygon(d.ring) for d in st.decks
                         if (d.end_a or d.end_b) and ring_polygon(d.ring)])
    deck_of = {d.object_id: d for d in st.decks}
    aprons, banks, slabs = [], [], []
    taken = Polygon()
    for e in st.rowed_ends():
        d = deck_of.get(e.object_id)
        if d is None:
            continue
        slab = _slab(e, H).difference(rings)
        apron = slab
        line = path_line(e, e.run) if e.state == "graded" else None
        if line is not None:
            hw = e.half_width
            apron = unary_union([slab, line.buffer(hw, cap_style="flat")]).difference(rings)
            w = max(float(de.bank_min_width_m), float(e.gap) / float(de.bank_slope))
            banks.append(line.buffer(hw + w, cap_style="flat"))
        apron = apron.difference(taken)
        slabs.append(slab)
        aprons.append((d, e.side, float(e.top), apron, slab))
        taken = taken.union(apron)
    bank = unary_union(banks).difference(taken).difference(rings) if banks else Polygon()
    outline = unary_union([taken, bank])
    keep = unary_union([rings, *slabs])
    return {"caps": Polygon(), "shadows": [], "aprons": aprons, "bank": bank,
            "outline": outline, "keep": keep}


def _deck_zone(st, d, rect: Polygon, law) -> Polygon:
    """The ground a deck piece's bank covers (v2 §3.2): ``ground_margin_m``
    beside its side edges, ``L_e`` and the plate's width beyond each end
    line (the APRON), the corners closed (the hull of the three)."""
    c = rect.centroid
    parts = [rect] + [_beyond(line, rect, _end_length(st, d, side, top, law))
                      for side, line, top in _ends(d)]
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


def ground_footprint(st, law) -> dict:
    """The stack's ground before any other region cuts it (v2 §3.2), in
    the order of precedence: ``caps`` (the crest plates, when
    :data:`GROUND_TO_WALL_TOP`), ``shadows`` ``[(deck, polygon)]`` (each
    deck piece's rectangle less the caps, a cell two rectangles share the
    lower level's), ``aprons`` ``[(deck, side, top, apron, slab)]`` (the
    bank beyond each end line, the plate's width for ``L_e``: its own piece,
    so the ground off a deck's end is triangulated on its own vertices; its
    first ``abutment_sample_step_m``, the SLAB, is held at the plate's top
    with the end edge, R1 -- the road's hold, v2 §3.4), ``bank`` (the rest
    of what joins those to the lidar), ``outline`` (their union: its edge
    off the floor is the TOE) and ``keep`` (the floor and its void band,
    which no piece takes)."""
    import shapely
    if getattr(st, "kind", "trench") != "trench":
        return _free_footprint(st, law)
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
        ends += [(d, side, top, _beyond(line, rect, _end_length(st, d, side, top, law)),
                  _beyond(line, rect, H)) for side, line, top in _ends(d)]
    aprons = []
    for d, side, top, g, slab in ends:      # on a fine grid: an apron shares its end line
        g = shapely.difference(shapely.difference(g, taken, grid_size=1e-6), keep,
                               grid_size=1e-6)
        aprons.append((d, side, top, g, slab))
        taken = shapely.union(taken, g, grid_size=1e-6)
    if GROUND_TO_WALL_TOP and not caps.is_empty and st.ground_margin_m > 0.0:
        zones.append(caps.buffer(float(st.ground_margin_m)))
    outline = unary_union([taken, *zones])
    return {"caps": caps.difference(keep), "shadows": shadows, "aprons": aprons,
            "bank": outline.difference(taken).difference(keep), "outline": outline,
            "keep": keep}
