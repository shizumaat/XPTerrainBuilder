"""THE CUT IS THE DECK'S (owner 2026-11-19T23:07Z: "When we insert a
bridge, we know the size and shape of the cut needed to provide the
clearance under it, whether there's OSM or not, if we have the evidence to
insert a bridge then we have to add the cut to the patch"; 23:09Z: "If we
insert a bridge, we need the cut, and the cut needs to grade smoothly away
from the bridge back to the natural terrain"; RULINGS 2026-11-19s (2)-(4)).

Every GENERATED deck of the full map (``planar/deck_generated``) mints its
own cut in the patch, ribbon or not, mapped road or not:

* ITS PATHS (:func:`_deck_paths`): each covered road or rail the deck spans
  (``DeckBridge.covered``), chained on along its own mapped OSM path
  (straight on where the map ends) as far as its ramp can need
  (:func:`_reach_m`); with none mapped, the cut's own axis -- the deck's
  road line, else along its end lines (they run parallel to the road).
* ITS STRETCHES: the stretch of each path under every generated deck it
  passes (the ring grown by the bank's run-on), so two parallel taxiways'
  decks over one road share one cut running straight through the gap
  (19s (3) (b)).
* THE SURVEYED GROUND along each path (``airport.dem``, the lidar road).
* ITS CELLS (:func:`deck_carve`): the floor (the carriageway and its
  shoulders, ``[deck_gen] shoulder_m``), the banks out to the estimated
  daylight line at the deck bank's slope (``model/deck_bank``), and the
  ground under the ring and its opened approaches -- ``graded_strip``
  faces under :data:`~..model.deck_carve.CARVE_REF`, cut out of every
  groundside cell they cross (never airside pavement, a runway, a
  structure, a building pad or a road ribbon, whose vertices stage 2
  levels where they stand).

Stage 2 levels them (``constraints/deck_carve``): the floor at
``min(lidar road floor, underside - clearance)`` under the deck, ramping
back along the path at the grade cap with vertical curves until it meets
the terrain, the banks at 1V:1.5H, each abutment's embankment from the
pavement.  Never on stage 1's map (its generated decks are withheld,
``planar/deck_airside``): the carve never moves airside.

Nothing here names an airport.  Build-time impact: per generated deck a
few hundred DEM samples, one small LP per path and a shapely knife.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union
from shapely.strtree import STRtree

from ..geom.carve_profile import PathFrame, floor_profile, smoothed
from ..geom.exact import hypot
from ..geom.parts import polygon_parts_with_area
from ..model.deck_bank import bank_past_m, deck_bank_slope
from ..model.deck_carve import CARVE_REF, CarvePath, DeckCarve
from ..model.road_clearance import carriageway_width_m, design_clearance_m
from ..model.structures import is_generated

__all__ = ["deck_carve"]

#: the surveyed ground is read along a path this often (m)
STEP_M = 2.0
#: the cut's cells are noded along their edges this often (m)
NODE_M = 4.0
#: a mapped road continues a path when it leaves within this of its end (m)
_JOIN_M = 1.0
#: ... turning no more than this off the path's heading (cosine)
_JOIN_COS = 0.7
#: the ramp's reach is read with this much more depth than the estimate (m)
_DEPTH_MARGIN_M = 2.0
#: ... and runs this much past it (m)
_REACH_MARGIN_M = 20.0
#: a carve piece this thin is a seam of the overlay, not ground (m)
_HAIR_M = 0.3

XY = tuple[float, float]


def _carve_law(law, kind: str) -> tuple[float, float]:
    """``(cap, rate)`` of a ``road`` / ``rail`` / ``axis`` path: the road's
    ramp cap (``[tunnel] ramp_max_grade``) or the rail grade (``[tunnel]
    rail_ramp_grade``, 1.25 %), and its vertical curve's grade change per
    metre (``law.tables.road_steep_law``)."""
    from ..law.tables import road_steep_law
    rs = road_steep_law(law)
    if kind == "rail":
        return float(rs["rail_cap"]), float(rs["rail_grade_change_per_m"])
    return float(law.tables.structures.tunnel.ramp_max_grade), float(rs["grade_change_per_m"])


def _kind(tags: _t.Mapping[str, str]) -> str:
    return "rail" if (tags or {}).get("railway") else "road"


def _road_lines(airport) -> tuple[list, "STRtree | None"]:
    """Every mapped road and railway line of the airport's OSM (never an
    aeroway), with its index."""
    lines = [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
             if len(w.points) >= 2 and any((w.tags or {}).get(k) for k in ("highway", "railway"))
             and not (w.tags or {}).get("aeroway")]
    return lines, (STRtree(lines) if lines else None)


def _onward(end: Point, heading: XY, lines, tree) -> "LineString | None":
    """The mapped line leaving ``end`` most nearly along ``heading``."""
    if tree is None:
        return None
    best, best_cos = None, _JOIN_COS
    for j in tree.query(end.buffer(_JOIN_M)):
        ln = lines[int(j)]
        if ln.distance(end) > _JOIN_M:
            continue
        t = ln.project(end)
        for piece in (substring(ln, t, ln.length), substring(ln, 0.0, t)):
            if piece.geom_type != "LineString" or piece.length < 1.0:
                continue
            c = list(piece.coords)
            if Point(c[-1]).distance(end) < Point(c[0]).distance(end):
                c.reverse()
            far = LineString(c).interpolate(min(5.0, LineString(c).length))
            dx, dy = far.x - end.x, far.y - end.y
            n = hypot(dx, dy)
            if n < 1e-6:
                continue
            cos = (dx * heading[0] + dy * heading[1]) / n
            if cos > best_cos:
                best, best_cos = LineString(c), cos
    return best


def _grow(coords: list[XY], reach: float, lines, tree) -> list[XY]:
    """``coords`` grown from its LAST point along the mapped road for
    ``reach`` metres (straight on past the map's end)."""
    out = list(coords)
    left = reach
    for _ in range(16):
        if left <= 0.0:
            break
        (x0, y0), (x1, y1) = out[-2], out[-1]
        n = max(hypot(x1 - x0, y1 - y0), 1e-9)
        heading = ((x1 - x0) / n, (y1 - y0) / n)
        nxt = _onward(Point(x1, y1), heading, lines, tree)
        if nxt is None:
            out.append((x1 + heading[0] * left, y1 + heading[1] * left))
            return out
        piece = substring(nxt, 0.0, min(left, nxt.length))
        pc = list(piece.coords)[1:]
        if not pc:
            break
        out.extend(pc)
        left -= piece.length
    return out


def _extended(line: LineString, reach: float, lines, tree) -> LineString:
    """``line`` chained on along its mapped road ``reach`` metres past each end."""
    c = [tuple(p) for p in line.coords]
    c = _grow(c, reach, lines, tree)
    c = list(reversed(_grow(list(reversed(c)), reach, lines, tree)))
    return LineString(c).simplify(0.05)


def _axis(db) -> "LineString | None":
    """The cut's own axis with no road mapped: the deck's road line, else
    a line through the ring along its end lines (parallel to the road)."""
    from .deck_bridge import deck_polygon
    ring = deck_polygon(db)
    if len(getattr(db, "road", ()) or ()) >= 2:
        ln = LineString(db.road)
    elif len(db.seats_a) >= 2:
        ln = LineString([db.seats_a[0], db.seats_a[-1]])
    else:
        return None
    (x0, y0), (x1, y1) = ln.coords[0], ln.coords[-1]
    n = max(hypot(x1 - x0, y1 - y0), 1e-9)
    c = ring.centroid
    u = ((x1 - x0) / n, (y1 - y0) / n)
    h = 0.5 * hypot(*(ring.bounds[2] - ring.bounds[0], ring.bounds[3] - ring.bounds[1]))
    return LineString([(c.x - u[0] * h, c.y - u[1] * h), (c.x + u[0] * h, c.y + u[1] * h)])


def _reach_m(db, law, cap: float, rate: float) -> float:
    """How far past the deck a path is chained: the ramp from the deck's
    floor (its estimated top less the slab and clearance, with margin) to
    the top at ``cap``, its two vertical curves, a margin; at most
    ``[tunnel] max_ramp_length_m``."""
    tn = law.tables.structures.tunnel
    depth = float(db.floor_min_m) + _DEPTH_MARGIN_M
    run = depth / max(cap, 1e-6) + cap / max(rate, 1e-9) + _REACH_MARGIN_M
    return min(run, float(tn.max_ramp_length_m))


def _stretches(frame: PathFrame, line: LineString, decks, past: float
               ) -> list[tuple[float, float, str]]:
    """``(s0, s1, deck id)`` of the path under each generated deck's ring
    grown by ``past``."""
    from .deck_bridge import deck_polygon
    out = []
    for d in decks:
        x = line.intersection(deck_polygon(d).buffer(past, join_style="mitre"))
        pts = [p for g in getattr(x, "geoms", [x]) if not g.is_empty
               for p in getattr(g, "coords", [])]
        if len(pts) < 2 or x.length < 1.0:
            continue
        s, _n = frame.project([p[0] for p in pts], [p[1] for p in pts])
        out.append((float(s.min()), float(s.max()), d.object_id))
    return out


def _terrain(frame: PathFrame, dem) -> tuple[tuple[float, float], ...]:
    """``(s, z)`` of the surveyed ground every :data:`STEP_M` along the path."""
    n = max(2, int(frame.length / STEP_M) + 1)
    out = []
    for k in range(n):
        s = frame.length * k / (n - 1)
        (x, y), _u = frame.at(s)
        try:
            z = float(dem.z(x, y))
        except Exception:      # noqa: BLE001 -- off the DEM: no ground read here
            continue
        if z == z:
            out.append((round(s, 3), round(z, 3)))
    return tuple(out)


def _estimate_floor(db, terrain, s0: float, s1: float, clearance: float, law) -> float:
    """The planar estimate of the floor under ``db`` (stage 2 re-reads it
    from the solved top, ``constraints/deck_carve``): the deeper of the
    lidar road -- its lowest survey within ``[deck_gen] level_probe_m`` of
    the stretch, the road open past the bridge -- and the pre-solve top
    less the slab and clearance."""
    probe = float(law.tables.structures.deck_gen.level_probe_m)
    under = [z for s, z in terrain if s0 - probe <= s <= s1 + probe]
    slab = float(law.tables.structures.deck_gen.thickness_m)
    design = float(db.deck_z) - slab - clearance
    return min([design] + under)


def _deck_paths(db, decks, airport, law, lines=None, tree=None) -> DeckCarve:
    """The cut's record for the generated deck ``db`` (module doc);
    ``decks``: every generated deck of the map (the stretches)."""
    from .deck_bridge import deck_polygon
    from .structure_underpass import aeroway_decks
    if lines is None:
        lines, tree = _road_lines(airport)
    past = bank_past_m(law)
    sh = float(law.tables.structures.deck_gen.shoulder_m)
    evidence: list[str] = []
    paths: list[CarvePath] = []
    dirs: list[str] = []
    ring = deck_polygon(db)
    for way, tags_items, coords in getattr(db, "covered", ()) or ():
        tags = dict(tags_items)
        kind = _kind(tags)
        cls = tags.get("railway") if kind == "rail" else tags.get("highway")
        evidence.append(f"OSM {kind} {way} {'railway' if kind == 'rail' else 'highway'}={cls}")
        if len(coords) < 2:
            continue
        cap, rate = _carve_law(law, kind)
        path = _extended(LineString(coords), _reach_m(db, law, cap, rate), lines, tree)
        paths.append(_path(str(way), kind, carriageway_width_m(tags, law) / 2.0 + sh,
                           design_clearance_m(tags, law), cap, rate, path, decks, past,
                           airport))
        dirs.append(f"along OSM {kind} {way} ({cls})")
    if getattr(db, "replaces", ()):
        evidence.append("hidden pack frame")
    if any(LineString(a.points).intersects(ring) for a in aeroway_decks(airport, law)
           if len(a.points) >= 2):
        evidence.append("OSM bridge tag")
    if not paths:
        ax = _axis(db)
        if ax is not None:
            cap, rate = _carve_law(law, "axis")
            path = _extended(ax, _reach_m(db, law, cap, rate), [], None)
            tn = law.tables.structures.tunnel
            paths.append(_path("", "axis", carriageway_width_m({}, law) / 2.0 + sh,
                               float(tn.clearance_m), cap, rate, path, decks, past, airport))
            dirs.append("along the cut's own axis (no mapped road or rail)")
    for p in paths:
        own = [(a, b) for a, b, oid in p.stretches if oid == db.object_id]
        if own and any(_estimate_floor(db, p.terrain, a, b, 0.0, law) <= float(db.deck_z)
                       - float(law.tables.structures.deck_gen.thickness_m) - p.clearance_m
                       for a, b in own):
            evidence.append("lidar trench")
            break
    return DeckCarve(tuple(evidence), "; ".join(dirs), tuple(paths))


def _path(way: str, kind: str, half: float, clearance: float, cap: float, rate: float,
          line: LineString, decks, past: float, airport) -> CarvePath:
    frame = PathFrame(list(line.coords))
    return CarvePath(way, kind, round(half, 3), round(clearance, 3), cap, rate,
                     tuple((round(x, 3), round(y, 3)) for x, y in line.coords),
                     tuple(_stretches(frame, line, decks, past)),
                     _terrain(frame, airport.dem))


def _path_cells(p: CarvePath, decks_by_id, law, dem) -> tuple:
    """``(floor, bank)``: the planar estimate of the path's cut -- its
    floor strip and its banks out to the daylight line plus a metre --
    over the stations where the estimated floor stands under the ground."""
    import numpy as np
    if not p.stretches or len(p.terrain) < 2:
        return None, None
    bank = deck_bank_slope(law)
    frame = PathFrame(p.coords)
    s = np.array([t[0] for t in p.terrain])
    r = smoothed([t[1] for t in p.terrain])
    st = []
    for a, b, oid in p.stretches:
        d = decks_by_id.get(oid)
        if d is not None:
            st.append((a, b, _estimate_floor(d, p.terrain, a, b, p.clearance_m, law)))
    if not st:
        return None, None
    z = floor_profile(s, r, st, p.cap, p.rate)
    left, right, idx = [], [], []
    deep = 0.0
    for k, sk in enumerate(s):
        (x, y), (ux, uy) = frame.at(float(sk))
        nx, ny = -uy, ux
        w0 = p.half_m + 4.0
        side = [r[k]]
        for sg in (1.0, -1.0):
            try:
                side.append(float(dem.z(x + sg * nx * w0, y + sg * ny * w0)))
            except Exception:    # noqa: BLE001 -- off the DEM
                pass
        depth = max(0.0, max(side) - float(z[k]))
        deep = max(deep, depth)
        if depth > 0.05 or any(a - 4.0 <= sk <= b + 4.0 for a, b, _z in st):
            idx.append(k)
        w = p.half_m + depth / bank + 1.0
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    if len(idx) < 2:
        return None, None
    k0, k1 = max(0, idx[0] - 2), min(len(s) - 1, idx[-1] + 2)
    piece = substring(LineString(p.coords), float(s[k0]), float(s[k1]))
    floor = piece.buffer(p.half_m, cap_style="flat", join_style="mitre")
    band = Polygon(left[k0:k1 + 1] + list(reversed(right[k0:k1 + 1]))).buffer(0.0)
    return floor, band.difference(floor)


def _untouched(c, law) -> bool:
    """A cell the cut never takes: airside pavement, the runway family, a
    structure, a building pad, a road ribbon (stage 2 levels its vertices)."""
    from ..law.tables import airside_stage_roles, family
    if c.kind == "structure" or c.role == "building":
        return True
    keep = set(airside_stage_roles(law)) | set(family(law, "road_cross_section").roles)
    return c.role in keep


def deck_carve(classification, decks, airport, law) -> tuple[_t.Any, tuple, list[str]]:
    """``(classification with every generated deck's cut cells, decks with
    their :class:`DeckCarve`, notes)`` (module doc).  Unchanged with no
    generated deck (stage 1's map: withheld)."""
    from ..classify.roles import Cell
    from ..geom.fixed_overlay import is_hairline
    from ..law.tables import role_side
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon
    gen = [d for d in decks if is_generated(d)]
    if not gen or classification is None or getattr(airport, "dem", None) is None:
        return classification, tuple(decks), []
    lines, tree = _road_lines(airport)
    carves = {d.object_id: _deck_paths(d, gen, airport, law, lines, tree) for d in gen}
    by_id = {d.object_id: d for d in gen}
    past = bank_past_m(law)
    regions: list[tuple[str, str, _t.Any]] = []
    notes: list[str] = []
    for d in gen:
        dc = carves[d.object_id]
        floors, banks = [], []
        for p in dc.paths:
            f, b = _path_cells(p, by_id, law, airport.dem)
            if f is not None:
                floors.append(f)
                banks.append(b)
        ground = unary_union([deck_polygon(d)] + [Polygon(q).buffer(0.0) for q in d.approach
                                                  if len(q) >= 3]).buffer(past, join_style="mitre")
        regions += [(d.object_id, "floor", unary_union(floors) if floors else None),
                    (d.object_id, "bank", unary_union(banks) if banks else None),
                    (d.object_id, "ground", ground)]
        notes.append(f"{d.object_id}: its cut is the deck's (owner 2026-11-19T23:07Z): "
                     f"evidence {', '.join(dc.evidence) or 'none'}; ramps {dc.direction}")
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    kept = unary_union([p for c, p in zip(classification.cells, polys, strict=True)
                        if _untouched(c, law) and not p.is_empty])
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    taken = kept
    new: list = []
    for oid, part, geom in regions:
        if geom is None or geom.is_empty:
            continue
        free = geom.difference(taken)
        for k, q in enumerate(q for q in polygon_parts_with_area(free)
                              if q.area > 0.5 and not is_hairline(q, max(spacing, _HAIR_M))):
            q = q.segmentize(NODE_M)
            new.append(Cell(0, "graded_strip", f"{CARVE_REF}:{oid}:{part}" + (f"#{k}" if k else ""),
                            tuple(q.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in q.interiors),
                            None, None, role_side(law, "graded_strip"), "structure",
                            {CARVE_REF: 1.0, "area_m2": q.area}))
        taken = taken.union(free)
    if not new:
        return classification, tuple(_dc.replace(d, carve=carves.get(d.object_id))
                                     if is_generated(d) else d for d in decks), notes
    knife = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in new])
    cells, n = knife_cells(classification.cells, polys, knife, law, (), cut_pads=False,
                           mark=CARVE_REF, new_cells=new,
                           cuts=lambda c: not _untouched(c, law))
    notes.append(f"{len(new)} cut cell(s) minted under {len(gen)} generated deck(s), "
                 f"{n} groundside cell(s) cut (owner 2026-11-19T23:07Z)")
    out = tuple(_dc.replace(d, carve=carves.get(d.object_id)) if is_generated(d) else d
                for d in decks)
    return _dc.replace(classification, cells=tuple(cells)), out, notes
