"""THE CUT BESIDE A GROUPED MOUTH'S WALLS (#2099 R2 / R3; specs
``docs/specs/2099-R2-wing-cut.md``, ``docs/specs/2099-R3.md`` Parts D / E;
the group: ``airport/mouth_group``, spec ``docs/specs/2099-mouth-groups.md``).

A tunnel mouth's WING WALLS are a ramp witness: the pack authored each one
standing on the road it lines.  Per mouth group the load partition forms
(:func:`mouth_wings`: the planar readers' mouths; every hard deck's members
and every piece co-placed with a mouth ``taken`` -- they are the mouth's own
frame, which its own record seats; a wall LINING the mouth's road joins too,
R3 E):

* THE FEET (``airport/wall_lines.wall_line_feet``, R3 D1, re-exported
  here): a wing's WALL LINES, each with its foot and top per station;
* THE REGION (D2): on the ROAD side of each line only -- from the wall's
  road-side face to the facing wall line of the group (within ``[tunnel]
  dual_carriageway_max_separation_m``), else across the mouth's road
  (:func:`mouth_roads`) to its far edge plus the rim stand-off
  (``wall_gap_m`` + ``wall_band_width_m``); less the deck ring and the
  mouth's plan grown by ``wall_gap_m``, every stage-1 airside cell grown by
  ``wall_gap_m``, every structure cell and every building pad;
* THE GROUND (D3, :func:`_cells`): every other cell the region meets is CUT on
  its edge (``planar/structures._cut_part_refs``, the structure pass's knife)
  and the region less the groundside roads becomes ``graded_strip`` cells
  ``wing_cut:<mouth>[#k]`` -- ground, never pavement; the roads keep their
  role and are held by the rows;
* THE BACK (D5): a strip ``entrance_skirt_m`` wide behind each line, free
  ground only and never where airside pavement stands in it, minted as
  ``wing_back:<mouth>[#k]``, held at the wall's top.

The level is ``constraints/wing_cut``'s, off the record
(``model/wing_cut.WingCut``).  A deck mouth's group walls also plan its ramp
(:func:`group_walled`, R3 D6).  Nothing here names a pack, a resource or an
airport; every number is a law value.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import types
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..airport import mouth_group as _mg
from ..airport.wall_lines import Station, wall_line_feet
from ..classify.roles import Cell
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..geom.parts import polygon_parts_with_area
from ..law.tables import airside_stage_roles, is_structure_role, role_side
from ..model.wing_cut import WING_CUT_REF, WallLine, WingCut
from .deck_bridge import co_placed, deck_polygon

__all__ = ["wing_cuts", "wall_line_feet", "mouth_wings", "mouth_roads", "group_walled"]

XY = tuple[float, float]


def _end_line_dir(db) -> "XY | None":
    """The way the road under a hard deck runs: ALONG its two end lines (the
    carried route drives across them), end B's sense turned to end A's."""
    dirs = []
    for st in (db.seats_a, db.seats_b):
        if len(st) < 2:
            return None
        dx, dy = st[-1][0] - st[0][0], st[-1][1] - st[0][1]
        L = math.hypot(dx, dy)
        if L <= 1e-9:
            return None
        dirs.append((dx / L, dy / L))
    (ax, ay), (bx, by) = dirs
    if ax * bx + ay * by < 0.0:
        bx, by = -bx, -by
    L = math.hypot(ax + bx, ay + by) or 1.0
    return (ax + bx) / L, (ay + by) / L


def mouth_roads(airport, law, decks) -> dict[str, tuple[XY, ...]]:
    """THE ROAD THROUGH EACH DECK (R3 E2 / D2), deck id -> polyline: the
    mapped way running farthest under its ring, walked out of both ends the
    way a tunnel's approach is (``structure_approach.approach``: the smallest
    turn, never over ``[tunnel] approach_turn_max_deg``), ``wing_reach_max_m``
    + the separation beyond it -- else a straight line through the ring along
    its end lines.  (A portal's road is its axis, ``mouth_group.mouths_of``.)"""
    tn = law.tables.structures.tunnel
    ext = float(tn.object.wing_reach_max_m) + float(tn.dual_carriageway_max_separation_m)
    out: dict[str, tuple[XY, ...]] = {}
    for db in decks:
        ring = deck_polygon(db)
        line = _deck_road(airport, law, ring, ext)
        r = _end_line_dir(db)
        if line is None and r is not None:
            c = ring.centroid
            line = ((c.x - r[0] * ext, c.y - r[1] * ext), (c.x + r[0] * ext, c.y + r[1] * ext))
        if line is not None:
            out.setdefault(str(db.object_id), line)
    return out


def _deck_road(airport, law, ring, ext: float) -> "tuple[XY, ...] | None":
    """The mapped way under ``ring`` (the longest stretch inside it), walked
    out of both its ends ``ext`` (:func:`mouth_roads`), or ``None``."""
    from .structure_approach import approach, unit
    ways = [w for w in getattr(airport, "osm_ways", None) or ()
            if len(w.points) >= 2 and ((w.tags or {}).get("highway") or
                                       (w.tags or {}).get("railway"))]
    best = None
    for w in ways:
        x = LineString(w.points).intersection(ring).length
        if x > 1.0 and (best is None or x > best[0]):
            best = (x, w)
    if best is None:
        return None
    tn = law.tables.structures.tunnel
    pts = [tuple(p) for p in best[1].points]
    a, b = (approach(e, unit(e, n), ways, ext, tn.admitted_values, tn.approach_turn_max_deg)
            for e, n in ((pts[0], pts[1]), (pts[-1], pts[-2])))
    return tuple(tuple(p) for p in reversed(a)) + tuple(pts[1:-1]) + tuple(tuple(p) for p in b)


def mouth_wings(airport, objects, cache, decks, tunnels, law) -> tuple[list, list[str]]:
    """``(mouth groups, notes)``: the load partition's groups of the mouths
    ``decks`` and ``tunnels`` state (``airport/mouth_group.mouth_groups``), a
    mouth's own frame taken, the walls lining its road (``DeckBridge.road``,
    a portal's axis) joined (R3 E)."""
    partition = getattr(airport, "partition", None)
    mouths = _mg.mouths_of(types.SimpleNamespace(decks=decks, structures=tunnels))
    if partition is None or not mouths:
        return [], []
    taken = {str(i) for db in decks for i in db.members}
    tol = float(law.tables.structures.tunnel.object.cover_placement_tol_m)
    heads = [o for o in objects if str(o.id) in {m.object_id for m in mouths}]
    taken |= {str(o.id) for o in objects for h in heads if o is not h and co_placed(h, o, tol)}
    return _mg.mouth_groups(partition, objects, mouths, cache, law, taken)


def group_walled(decks, airport, objects, cache, law) -> tuple[tuple, list[str]]:
    """``(decks, notes)``: each hard deck carries the road through it
    (``DeckBridge.road``, :func:`mouth_roads`) and, where its mouth group has
    walls, their stations ``(x, y, foot)`` (``DeckBridge.group_feet``, R3 D6)
    -- the walls its ramps are planned on (``deck_bridge.deck_pin``).  Formed
    before the structure pass: the decks exist then."""
    if not decks:
        return tuple(decks), []
    roads = mouth_roads(airport, law, decks)
    decks = tuple(_dc.replace(db, road=roads.get(str(db.object_id), ())) for db in decks)
    groups, notes = mouth_wings(airport, objects, cache, decks, (), law)
    by_id = {str(o.id): o for o in objects}
    feet: dict[str, list] = {}
    for gr in groups:
        mo = by_id.get(gr.mouth.object_id)
        read = None if mo is None else _mg._solids(mo, cache, law)
        if read is None:
            continue
        for wid, _res in gr.wings:
            for _ln, st in wall_line_feet(by_id[wid], cache, law, read[0]):
                feet.setdefault(gr.mouth.object_id, []).extend(
                    (round(s[0], 3), round(s[1], 3), round(s[6], 3)) for s in st)
    out = tuple(_dc.replace(db, group_feet=tuple(feet[str(db.object_id)]))
                if str(db.object_id) in feet else db for db in decks)
    return out, [f"{k}: its group's walls plan its ramps, {len(v)} station(s) (#2099 R3 D6)"
                 for k, v in sorted(feet.items())] + list(notes)


def _mouth_frame(m, decks: _t.Mapping[str, _t.Any], tunnels) -> "tuple | None":
    """``(r, seat kwargs)`` of mouth ``m``: a hard deck's road direction and
    end lines, or a row-seated portal's bore direction and absolute floor."""
    db = decks.get(m.object_id)
    if db is not None:
        r = _end_line_dir(db)
        if r is None:
            return None
        return r, dict(seats=(tuple(db.seats_a), tuple(db.seats_b)),
                       tops=(float(db.top_a), float(db.top_b)))
    for tn in tunnels:
        if str(getattr(tn, "portal", "")) == m.object_id and getattr(tn, "portal_seat", ()) \
                and len(tn.axis) >= 2:
            (x0, y0), (x1, y1) = tn.axis[0], tn.axis[1]
            L = math.hypot(x1 - x0, y1 - y0) or 1.0
            return ((x1 - x0) / L, (y1 - y0) / L), dict(floor_z=float(tn.mouth_z))
    return None


def _road_sense(road: LineString, st: _t.Sequence[Station]) -> float:
    """``+1`` where the road lies on the stations' ``+n`` side (by majority),
    else ``-1``."""
    vote = 0.0
    for x, y, nx, ny, *_r in st:
        q = road.interpolate(road.project(Point(x, y)))
        vote += math.copysign(1.0, (q.x - x) * nx + (q.y - y) * ny)
    return 1.0 if vote >= 0.0 else -1.0


def _wall_line(wid: str, st: _t.Sequence[Station], sense: float) -> WallLine:
    """The record of one wall line, its face the side ``sense`` names."""
    face, back = [], []
    for x, y, nx, ny, lo, hi, _f, _top in st:
        near, far = (hi, lo) if sense > 0 else (lo, hi)
        face.append((x + nx * near, y + ny * near))
        back.append((x + nx * far, y + ny * far))
    return WallLine(wid, tuple(face), tuple(back), tuple(s[6] for s in st),
                    tuple(s[7] for s in st))


def _reach(p: XY, d: XY, road: LineString, half: float, rim: float, sep: float,
           others: _t.Sequence) -> "float | None":
    """How far the region runs from face point ``p`` along ``d`` (R3 D2): to
    the first facing wall in ``others`` within ``sep``, else across ``road``
    to its far edge plus ``rim``; ``None`` where the ray never meets the road."""
    big = sep + half + rim
    ray = LineString([p, (p[0] + d[0] * big, p[1] + d[1] * big)])
    hit = ray.intersection(road)
    if hit.is_empty:
        return None
    tc = float(min((x - p[0]) * d[0] + (y - p[1]) * d[1]
                   for x, y in shapely.get_coordinates(hit)))
    s = road.project(Point(p[0] + d[0] * tc, p[1] + d[1] * tc))
    a, b = road.interpolate(max(0.0, s - 0.5)), road.interpolate(min(road.length, s + 0.5))
    L = math.hypot(b.x - a.x, b.y - a.y) or 1.0
    cos = abs((b.x - a.x) / L * -d[1] + (b.y - a.y) / L * d[0])
    end = tc + (half + rim) / max(cos, 0.3)
    for w in others:
        x = ray.intersection(w)
        if x.is_empty:
            continue
        th = min((qx - p[0]) * d[0] + (qy - p[1]) * d[1] for qx, qy in shapely.get_coordinates(x))
        if 1e-3 < th <= sep:
            end = min(end, float(th))
    return end


def _strip(line: WallLine, ends: _t.Sequence["float | None"], toward: _t.Sequence[XY],
           width: float = 0.0) -> list:
    """The quads between consecutive stations: from each face point along
    ``toward`` by its end (the region), or -- ``width`` given -- from each back
    point away from the road by ``width`` (the back strip)."""
    quads = []
    pts = line.back if width > 0.0 else line.face
    sg = -1.0 if width > 0.0 else 1.0
    for i in range(len(pts) - 1):
        e0, e1 = (width, width) if width > 0.0 else (ends[i], ends[i + 1])
        if e0 is None or e1 is None:
            continue
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        (dax, day), (dbx, dby) = toward[i], toward[i + 1]
        q = Polygon([(ax, ay), (bx, by), (bx + sg * dbx * e1, by + sg * dby * e1),
                     (ax + sg * dax * e0, ay + sg * day * e0)]).buffer(0.0)
        if not q.is_empty:
            quads.append(q)
    return quads


def _section_plan(st: _t.Sequence[Station]) -> Polygon:
    """A wall line's plan from its stations' section extents."""
    ring = ([(x + nx * lo, y + ny * lo) for x, y, nx, ny, lo, _h, _f, _top in st]
            + [(x + nx * hi, y + ny * hi) for x, y, nx, ny, _l, hi, _f, _top in reversed(st)])
    return Polygon(ring).buffer(0.0) if len(ring) >= 3 else Polygon()


def wing_cuts(airport, objects, cache, decks, tunnels, classification, law
              ) -> tuple[_t.Any, tuple[WingCut, ...], list[str]]:
    """``(classification with the wing-cut ground, the cuts, notes)`` (module
    doc)."""
    groups, gnotes = mouth_wings(airport, objects, cache, decks, tunnels, law)
    if not groups:
        return classification, (), []
    tn_law = law.tables.structures.tunnel
    gap, rim = float(tn_law.wall_gap_m), float(tn_law.wall_gap_m + tn_law.wall_band_width_m)
    sep = float(tn_law.dual_carriageway_max_separation_m)
    skirt = float(tn_law.object.entrance_skirt_m)
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    by_id = {str(o.id): o for o in objects}
    deck_of = {str(db.object_id): db for db in decks}
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    stage1 = airside_stage_roles(law)
    air = unary_union([p for p, c in zip(polys, cells, strict=True) if c.role in stage1])
    solid = unary_union([p for p, c in zip(polys, cells, strict=True)
                         if c.role == "building" or (c.role in law.tables.precedence.roles
                                                      and is_structure_role(law, c.role))])
    cuts: list[WingCut] = []
    notes: list[str] = list(gnotes)
    for gr in groups:
        frame = _mouth_frame(gr.mouth, deck_of, tunnels)
        mo = by_id.get(gr.mouth.object_id)
        read = None if mo is None else _mg._solids(mo, cache, law)
        coords = gr.mouth.road
        if frame is None or read is None or len(coords) < 2:
            continue
        seat = frame[1]
        road, mplan = LineString(coords), read[0]
        band = deck_polygon(deck_of[gr.mouth.object_id]) if gr.mouth.object_id in deck_of \
            else mplan
        half = max((float(t.half_width_m) for t in tunnels
                    if str(getattr(t, "deck_bridge", "")) == gr.mouth.object_id
                    or str(getattr(t, "portal", "")) == gr.mouth.object_id), default=0.0)
        read_lines = [(wid, st) for wid, _res in gr.wings
                      for _ln, st in wall_line_feet(by_id[wid], cache, law, mplan)]
        plans = [_section_plan(st) for _w, st in read_lines]
        lines, parts, backs = [], [], []
        for k, (wid, st) in enumerate(read_lines):
            sense = _road_sense(road, st)
            line = _wall_line(wid, st, sense)
            toward = [(sense * s[2], sense * s[3]) for s in st]
            ends = [_reach(p, d, road, half, rim, sep, plans[:k] + plans[k + 1:])
                    for p, d in zip(line.face, toward, strict=True)]
            lines.append(line)
            parts += _strip(line, ends, toward)
            backs += [q for q in _strip(line, ends, toward, skirt)
                      if q.intersection(air).area <= 1e-6]
        if not parts:
            continue
        keep_out = unary_union([band, mplan]).buffer(gap + spacing, join_style="mitre")
        region = unary_union(parts).difference(unary_union([
            keep_out, air.buffer(gap, join_style="mitre"), solid]))
        rings = _rings(region, spacing)
        if not rings:
            continue
        back = unary_union(backs).difference(unary_union([region, keep_out, *plans])) \
            if backs else Polygon()
        cuts.append(WingCut(gr.mouth.object_id, f"{WING_CUT_REF}:{gr.mouth.object_id}", rings,
                            tuple(lines), _rings(back, spacing),
                            floor_y=float(gr.mouth.floor_y), **seat))
        feet = [f for ln in lines for f in ln.foot]
        notes.append(f"{gr.mouth.object_id}: wing cut over {len(gr.wings)} wing(s), "
                     f"{len(lines)} wall line(s), {sum(Polygon(q).area for q in rings):.0f} m2 "
                     f"on the road side, feet {min(feet):+.2f}..{max(feet):+.2f} over its floor "
                     f"(#2099 R3 D)")
    if not cuts:
        return classification, (), notes
    classification, minted = _cells(classification, cuts, law, spacing)
    notes.extend(minted)
    return classification, tuple(cuts), notes


def _rings(geom, spacing: float) -> tuple[tuple[XY, ...], ...]:
    """The polygon parts of ``geom`` (no hairline) as exterior rings."""
    if geom is None or geom.is_empty:
        return ()
    return tuple(tuple((float(x), float(y)) for x, y in q.exterior.coords[:-1])
                 for q in polygon_parts_with_area(geom) if not is_hairline(q, spacing))


def _kept(c: Cell, law, roads: _t.AbstractSet[str]) -> bool:
    """A cell the wing cut never carves (R3 D3): airside, a structure, a
    building pad, a groundside road (held in place by the rows)."""
    if c.role == "building" or c.side == "airside" or c.role in roads:
        return True
    return c.role in law.tables.precedence.roles and is_structure_role(law, c.role)


def _cells(classification, cuts: _t.Sequence[WingCut], law, spacing: float
           ) -> tuple[_t.Any, list[str]]:
    """The cuts' ground as cells (module doc, R3 D3 / D5): the region carves
    every cell it meets but the kept ones and becomes ``wing_cut`` faces; the
    back strip takes free ground only."""
    from ..law.tables import family
    from .structures import _cut_part_refs
    roads = frozenset(family(law, "road_cross_section").roles)
    cells = list(classification.cells)
    notes: list[str] = []
    for cut in cuts:
        polys = [Polygon(c.ring, c.holes) for c in cells]
        kept = canonical_union([p if p.is_valid else p.buffer(0.0)
                                for p, c in zip(polys, cells, strict=True) if _kept(c, law, roads)])
        region = fixed_difference(unary_union([Polygon(q).buffer(0.0) for q in cut.region]),
                                  kept)
        carved: list[Cell] = []
        n_cut = 0
        for c, p in zip(cells, polys, strict=True):
            if _kept(c, law, roads) or p.intersection(region).area <= 0.25:
                carved.append(c)
                continue
            n_cut += 1
            for ref, part in _cut_part_refs(c.ref, False, polygon_parts_with_area(
                    fixed_difference(p, region))):
                carved.append(_dc.replace(c, ref=ref, ring=tuple(part.exterior.coords)[:-1],
                                          holes=tuple(tuple(h.coords)[:-1]
                                                      for h in part.interiors)))
        mine = [q for q in polygon_parts_with_area(region) if not is_hairline(q, spacing)]
        taken = canonical_union([Polygon(c.ring, c.holes) for c in carved] + mine)
        back = unary_union([Polygon(q).buffer(0.0) for q in cut.back]) if cut.back else None
        free = [] if back is None else [q for q in polygon_parts_with_area(
            fixed_difference(back, taken)) if not is_hairline(q, spacing)]
        for ref, parts, what in ((cut.ref, mine, "wing_cut"), (cut.back_ref, free, "wing_back")):
            carved += [Cell(0, "graded_strip", ref + (f"#{k}" if k else ""),
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            None, None, role_side(law, "graded_strip"), "structure",
                            {what: 1.0, "area_m2": part.area}) for k, part in enumerate(parts)]
        cells = carved
        notes.append(f"{cut.mouth}: {len(mine)} wing-cut face(s) "
                     f"{sum(q.area for q in mine):.0f} m2 ({n_cut} cell(s) carved), "
                     f"{len(free)} back face(s) {sum(q.area for q in free):.0f} m2 of free ground")
    merged = [_dc.replace(c, id=i) for i, c in enumerate(cells)]
    return _dc.replace(classification, cells=tuple(merged)), notes
