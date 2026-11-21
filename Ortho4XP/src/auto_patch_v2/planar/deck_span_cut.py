"""A PACK DECK LYING AT GRADE ON THE AIRPORT'S PAVEMENT IS CUT TO ITS SPANS
(owner RULINGS 2026-11-18i; #2157 KRDU 2026-11-18T19:04Z: "drop that long
straight object for taxiway E between the two bridges and use real terrain
and taxiway grading instead").

A hard-deck piece (``planar/deck_bridge.deck_bridges``) whose axis holds a
SPAN over lower ground (``geom/deck_spans``: a road, a void or ground more
than a storey, ``[building_pad] low_level_min_step_m``, under the
profile's fill level) AND an AT-GRADE stretch longer than the piece is wide
that lies on the airport's MAPPED airside (along most of it: inside an
apt.dat pavement or a runway, or within half a taxiway's width of an
aircraft taxi route, row 1202 -- the cells under a deck ring are the
deck's, so the classification cannot say) is cut to its spans: each span, abutment to
abutment, is a deck of its own -- seated flat on its own end lines, the
airside graded to weld to them (RULINGS 2026-10-30a, #2112's one zero per
plate) -- and the at-grade parts are no deck at all: the airport's graded
pavement draws there and the object stage drops those bands of the frame
(``airport/deck_plates``).  The abutment is where the bare-earth bank of
the span turns no steeper than twice the taxiway longitudinal cap.

A deck that is all bridge (no such at-grade stretch: KBNA's taxiway-L
plates) is unchanged.  Nothing here names an airport, a pack or a resource.

THE OPENING IS THE WALLS' (#2157 R3, :func:`_wall_spans`): in a deck the
survey cut, a facing pair of the frame's own wall lines standing in an
at-grade stretch, with a mapped road crossing the deck between them and
ground more than a storey under the crest on both flanks of the crossing,
is a span too, abutment to abutment at the two wall lines -- a bridge the
bare-earth survey reads as continuous ground (18f: the pack is a witness;
10-30f: walls set the cut).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..geom.deck_spans import SpanCut, span_cut, span_pieces

__all__ = ["MARK", "span_split", "at_grade_cells"]

#: the station step along a piece's axis, metres
STEP_M = 2.0


def span_split(piece: _t.Any, airport: _t.Any, law: _t.Any, walls: _t.Any = None
               ) -> "tuple[SpanCut, list] | None":
    """``(cut, span pieces)`` of a deck piece the rule cuts (module doc),
    else ``None``.  ``walls(r, n)``: the frame's wall faces across the road
    direction ``r`` (``planar/deck_walls.wall_faces``), read for the wall
    pair spans (:func:`_wall_spans`); ``None`` reads none."""
    dem = getattr(airport, "dem", None)
    storey = float(getattr(law.tables.structures.building_pad, "low_level_min_step_m", 0.0)
                   or 0.0)
    cap = law.ruleset.taxi.longitudinal.value(None, None)
    if dem is None or storey <= 0.0 or cap is None:
        return None

    def z_of(x: float, y: float) -> "float | None":
        z = dem.z(x, y)
        return None if z is None else float(z)
    cut = span_cut(piece, z_of, drop_m=storey, rise_grade=2.0 * float(cap), step_m=STEP_M)
    if cut is None or cut.length <= 0.0:
        return None
    width = piece.area / cut.length
    mapped = _mapped_airside(airport, law, piece)
    if mapped is None or not any(s1 - s0 > width and _on(cut, s0, s1, mapped)
                                 for s0, s1 in cut.at_grade()):
        return None
    if walls is not None:
        extra = _wall_spans(cut, walls, airport, piece, storey)
        if extra:
            cut = _dc.replace(cut, spans=tuple(sorted(cut.spans + extra)))
    parts = span_pieces(piece, cut)
    return (cut, parts) if parts else None


def _wall_spans(cut: SpanCut, walls: _t.Any, airport: _t.Any, piece: _t.Any,
                storey: float) -> "tuple[tuple[float, float], ...]":
    """THE OPENING IS THE WALLS' (module doc): the spans ``(s_a, s_b)`` of
    each facing pair of the frame's wall lines (``geom/wall_lines.
    wall_lines``, read across the axis) standing inside one at-grade
    stretch of ``cut`` with a mapped road crossing the axis between them
    and ground more than ``storey`` under the crest on both of its flanks
    (:func:`_crossing_drops`)."""
    from ..geom.wall_lines import project_span, wall_lines
    ux, uy = cut.unit
    got = walls((-uy, ux), (ux, uy))
    if not got:
        return ()
    rw, nw, faces = got[:3]
    sign = 1.0 if nw[0] * ux + nw[1] * uy > 0.0 else -1.0
    at0 = cut.a[0] * nw[0] + cut.a[1] * nw[1]
    # K2: a pier with the frame's floor on both sides ends no span
    lines = sorted(sign * (u - at0) for u in wall_lines(faces, *project_span(
        piece.exterior.coords, rw), got[3] if len(got) > 3 else None))
    out = []
    for sa, sb in zip(lines, lines[1:], strict=False):
        if not any(s0 <= sa and sb <= s1 for s0, s1 in cut.at_grade()):
            continue
        drops = _crossing_drops(cut, sa, sb, airport, piece)
        if drops and min(drops) > storey:
            out.append((sa, sb))
    return tuple(out)


def _crossing_drops(cut: SpanCut, sa: float, sb: float, airport: _t.Any, piece: _t.Any
                    ) -> "tuple[float, float] | None":
    """Of the first mapped road crossing the axis between stations ``sa``
    and ``sb``, read along its own direction through the crossing: the
    crest (the highest ground inside ``piece``) less the lowest ground
    outside it on each side, within the piece's mean width past its edge;
    ``None`` (no road, no ground read on a side)."""
    from shapely.geometry import LineString, Point
    dem = getattr(airport, "dem", None)
    if dem is None:
        return None
    ux, uy = cut.unit
    axis = LineString([(cut.a[0] + sa * ux, cut.a[1] + sa * uy),
                       (cut.a[0] + sb * ux, cut.a[1] + sb * uy)])
    reach = piece.area / max(cut.length, 1.0)
    far = reach + max(piece.bounds[2] - piece.bounds[0], piece.bounds[3] - piece.bounds[1])
    for w in getattr(airport, "osm_ways", None) or ():
        tags = getattr(w, "tags", None) or {}
        road = tags.get("highway") or tags.get("railway")
        if not road or tags.get("bridge") not in (None, "no"):
            continue
        line = LineString(w.points)
        hit = line.intersection(axis)
        if hit.is_empty or hit.geom_type != "Point":
            continue
        (x0, y0), (x1, y1) = w.points[0], w.points[-1]
        n = math.hypot(x1 - x0, y1 - y0)
        if n <= 0.0:
            continue
        crest, lows = -math.inf, []
        for side in (1.0, -1.0):
            low, out_t = math.inf, None
            for k in range(int(far / STEP_M) + 1):
                t = k * STEP_M
                q = Point(hit.x + side * t * (x1 - x0) / n, hit.y + side * t * (y1 - y0) / n)
                z = dem.z(q.x, q.y)
                if z is None:
                    continue
                if piece.contains(q) and out_t is None:
                    crest = max(crest, float(z))
                    continue
                out_t = t if out_t is None else out_t
                if t - out_t > reach:
                    break
                low = min(low, float(z))
            lows.append(low)
        if math.isfinite(crest) and all(math.isfinite(v) for v in lows):
            return crest - lows[0], crest - lows[1]
    return None


def _mapped_airside(airport: _t.Any, law: _t.Any, piece: _t.Any) -> _t.Any:
    """The airport's mapped airside near ``piece`` (module doc), prepared;
    ``None`` for none."""
    from shapely.prepared import prep
    near = _airside_near(airport, law, piece)
    return None if near is None else prep(near)


def _airside_near(airport: _t.Any, law: _t.Any, piece: _t.Any) -> _t.Any:
    """The airport's mapped airside near ``piece`` (module doc) as one
    geometry; ``None`` for none."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    from ..law.tables import taxi_half_width_m
    box = piece.envelope.buffer(50.0)
    geoms = [Polygon(p.outer, p.holes).buffer(0.0)
             for p in getattr(airport, "pavements", ()) or ()]
    for rw in getattr(airport, "runways", ()) or ():
        if len(rw.ends) == 2:
            geoms.append(LineString([rw.ends[0].xy, rw.ends[1].xy]).buffer(
                0.5 * float(getattr(rw, "width_m", 0.0) or 0.0) or 1.0))
    half = taxi_half_width_m(law, None) or 0.0
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    for e in getattr(airport, "taxi_edges", ()) or ():
        if half > 0.0 and e.a in nodes and e.b in nodes and nodes[e.a].xy != nodes[e.b].xy:
            geoms.append(LineString([nodes[e.a].xy, nodes[e.b].xy]).buffer(half))
    near = [g for g in geoms if g.intersects(box)]
    return unary_union(near) if near else None


def _on(cut: SpanCut, s0: float, s1: float, mapped: _t.Any) -> bool:
    """Does most of the axis stretch ``s0..s1`` stand on ``mapped``?"""
    from shapely.geometry import Point
    ux, uy = cut.unit
    n = max(int((s1 - s0) / STEP_M), 1)
    hits = sum(mapped.contains(Point(cut.a[0] + (s0 + (s1 - s0) * k / n) * ux,
                                     cut.a[1] + (s0 + (s1 - s0) * k / n) * uy))
               for k in range(n + 1))
    return hits * 2 > n + 1


def _on_airside(plan: _t.Any, airport: _t.Any, law: _t.Any, piece: _t.Any) -> _t.Any:
    """THE PAVEMENT IS THE TAXIWAY, NOT THE OBJECT'S PLAN (#2157 R1/R4):
    the share of a cut deck's at-grade ``plan`` on the MAPPED airside near
    ``piece`` (:func:`_airside_near`) widened by the zone-1 lip
    (``zones.adjacent_ground.lip_width_m``).  The rest of the plan is the
    ground beside the taxiway -- its graded strip and the bank to the
    survey (MEASURED KRDU obj140 #2: an 89 m plan over a 50 m crest, graded
    flat as taxiway 1.3-2.2 m under the crest)."""
    near = _airside_near(airport, law, piece)
    if near is None:
        return plan
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    return plan.intersection(near.buffer(lip, join_style="mitre"))


#: the evidence mark of a cell the at-grade deck plan cut
MARK = "deck_at_grade"


def at_grade_cells(classification: _t.Any, airport: _t.Any, law: _t.Any,
                   objects: _t.Any) -> tuple[_t.Any, list[str]]:
    """``classification`` with the AT-GRADE plan of every deck the rule
    cuts (module doc) made airside pavement: the pack drew the carried
    taxiway there only as its deck, so no pavement source holds it, and
    once the deck is dropped the airport's own graded taxiway draws there.
    Each at-grade part not already under a runway, taxiway or apron cell
    becomes a cell of the role (and letter, kind) of the nearest taxi cell;
    the cells it covers are cut away (only on the mapped airside,
    :func:`_on_airside`).  Unchanged where no deck is cut."""
    import dataclasses as dc

    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from ..classify.roles import Cell
    from ..geom.parts import polygon_parts_with_area
    from ..law.tables import role_family
    from .cell_knife import knife_cells
    from .deck_bridge import _frames
    if not objects or classification is None or not classification.cells:
        return classification, []
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    at: list[tuple[str, _t.Any]] = []
    for decks, _frame in _frames(objects, tol):
        u = unary_union([q.hard_deck for q in decks])
        for piece in getattr(u, "geoms", [u]):
            if piece.geom_type != "Polygon" or piece.area < 1.0:
                continue
            got = span_split(piece, airport, law)
            if got is None:
                continue
            at.append((str(decks[0].id), _on_airside(
                piece.difference(unary_union(got[1])), airport, law, piece)))
    if not at:
        return classification, []

    def fam(c) -> str:
        try:
            return role_family(law, c.role)
        except KeyError:
            return "none"
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    paved_i = [i for i, c in enumerate(classification.cells)
               if fam(c) in ("runway", "taxi") or c.role == "apron"]
    paved = unary_union([polys[i] for i in paved_i]) if paved_i else Polygon()
    taxi_i = [i for i in paved_i if fam(classification.cells[i]) == "taxi"]
    new: list = []
    notes: list[str] = []
    for oid, g in at:
        g = g.difference(paved)
        if g.is_empty or not taxi_i:
            continue
        near = classification.cells[min(taxi_i, key=lambda i: polys[i].distance(g))]
        for part in polygon_parts_with_area(g):
            if part.area < 1.0:
                continue
            new.append(Cell(0, near.role, f"{MARK}:{oid}#{len(new)}",
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            near.code_number, near.code_letter, near.side, near.kind,
                            {MARK: 1.0}))
        notes.append(f"{oid}: its at-grade plan {g.area:,.0f} m2 is the airport's "
                     f"{near.role} (RULINGS 2026-11-18i)")
    if not new:
        return classification, notes
    knife = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in new])
    cells, _n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                            mark=MARK, new_cells=new,
                            cuts=lambda c: not (fam(c) in ("runway", "taxi") or c.role == "apron"))
    # the taxi route runs on across it (``planar/route_lines``)
    from .route_lines import with_route_lines
    out, n_lines = with_route_lines(dc.replace(classification, cells=tuple(cells)), airport,
                                    [knife])
    if n_lines:
        notes.append(f"{n_lines} taxi centreline piece(s) across the at-grade plan(s)")
    return out, notes
