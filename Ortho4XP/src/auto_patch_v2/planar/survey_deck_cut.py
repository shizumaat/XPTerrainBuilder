"""THE SURVEYED CUT AT A HARD DECK IS KEPT (owner RULINGS 2026-11-17a (1)-(2),
2026-10-28k R1/R2/R4, 2026-11-13h N1; #2128 round 2 R1 / R2 / R5;
``planar/deck_bridge``'s sibling).

A pack hard deck the airport's taxiway drives across (``planar/deck_bridge.
DeckBridge``) whose frame states no road level takes the ladder's floor
(``deck_bridge._road_floor``: ``[tunnel] mouth_depth_m`` under a runway or
taxiway) and a carriageway-wide slot with its rim at grade beside it; the
rest of the deck's reach is held at deck level.  On a CREDIBLE survey
(``law/inset_class.lidar_credible``) the 1 m lidar shows the real cut: the
roads in continuous excavations with sloped banks and plazas (MEASURED
KIAH, #2128: ground held 6-7 m over the survey beside five decks).  The
owner (17a (1)): the floor and the banks follow the lidar.  This module is
the ONE reading, computed once in ``planar/build`` after the decks and
before the structure pass; every consumer reads its record
(:class:`_SurveyDeckCut`):

* APPLIES to a wall-less hard deck (``deck_bridge.is_walled`` false) whose
  floor is the ladder's (``DeckBridge.floor_min_m`` > 0: no object states
  it) and not the airport's level B (a level-B airport's decks keep their
  floor: LFPG's owner-ruled A1 trench), on a credible survey.  Every other
  deck keeps today's path whole.
* THE EDGE READING (:func:`_edge_roads`): every mapped road passing under
  the deck (through its ring across its midline) is read at each SIDE edge
  outward along its own line -- ``lidar_road.surveyed_road``, the least of
  the survey across the carriageway over its first metres -- never under
  the deck, where the survey reads the deck (Q344 a).  The cover is the
  deck's rendered top (``DeckBridge.deck_z``).
* THE VERDICT, per lane: a road read under ``[channel] object_min_depth_m``
  at a side edge crosses at grade (R5: no lane); one clearing ``[tunnel]
  clearance_m`` under the cover at both edges is KEPT (30g (1)).
* THE FLOOR: one level per road under the deck, F = the lower of its two
  edge roads (the rung "credible lidar if it clears 5 m" of 11-03b (5),
  read at the deck's edges).  A mouth under the deck is built as a KEPT
  mouth at its lane's F (:func:`deck_survey_mouth`, ``planar/structures``);
  the B1 pin holds the floor there (``constraints/structures``).  A lane
  clearing less than the clearance at an edge keeps the ladder's floor.
* THE REGION C (:func:`_cut_region`): the survey's cut along each road from
  the deck's side edge out to where the road comes within ``[channel]
  object_min_depth_m`` of the cover, rim to rim (``planar/covered_ground``'s
  sections with ``rise=object_min_depth_m``), never a hard-deck ring, a
  runway-family cell or a pavement part a taxi route crosses.  C is a
  keepout (the zones stop at it: ``planar/structures``' ``survey_cuts``) and
  the deck's ground leaves it (``deck_bridge.deck_ground``): ground in C is
  unowned, the mesh draws the survey.
* R2 (:func:`cut_pavement`, 17a (2), amends 11-03e (6) for this case): every
  pavement cell over C -- apt.dat or pack, airside or groundside, never a
  road ribbon or a building pad -- is cut by it where the survey's median
  under the part stands below the cut's mid-height (``survey_cut.Cutting.
  floor_face``'s rule).  Done before the structure pass reads its stops, so
  a cut piece no longer dead-ends a run-out (#2072 A).

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from ..airport.dem import dem_z_at
from ..classify.roles import Cell
from ..geom.parts import polygon_parts_with_area
from ..law import Law
from ..law.tables import pavement_roles
from ..model.frame import XY
from .covered_ground import _ribbon, _sections, section_runs
from .deck_bores import _midline
from .deck_bridge import DeckBridge, deck_polygon, is_walled
from .lidar_road import _COVER_M, surveyed_road
from .structure_approach import Bore, carriageway_width_m, chains

__all__ = ["survey_deck_cuts", "cut_pavement", "region_union", "survey_under",
           "deck_survey_mouth"]

#: roles R2 never cuts: a road ribbon stays (it follows the survey), a pad
#: is a building
_NEVER_CUT = frozenset({"building", "service_road", "service_junction"})
#: a cut station farther than this from the last kept one ends the run (m)
_GAP_M = 10.0


@_dc.dataclass(frozen=True)
class _SurveyDeckCut:
    """One deck's surveyed cut (module doc): the deck (object, ring), its
    cover, every road under it ``(way id, edge a xy, road there, edge b xy,
    road there, F)``, the deck's floor (the least F) and the region C (frame
    xy; ``None`` for none)."""
    object_id: str
    ring: tuple[XY, ...]
    cover: float
    roads: tuple[tuple[int, XY, float, XY, float, float], ...]
    floor: float
    region: _t.Any = None

    def lane(self, way_ids: _t.Iterable[int], xy: XY) -> "tuple[float, float] | None":
        """``(F, the surveyed road at the edge nearest xy)`` of the lane of
        ``way_ids`` (the least F of its roads); ``None`` where none is one
        of this deck's roads."""
        ids = {int(i) for i in way_ids}
        rows = [r for r in self.roads if int(r[0]) in ids]
        if not rows:
            return None
        f = min(r[5] for r in rows)
        edge = min([(math.dist(xy, r[1]), r[2]) for r in rows]
                   + [(math.dist(xy, r[3]), r[4]) for r in rows])[1]
        return f, edge


def _roads(airport, law: Law) -> list[Bore]:
    """The road chains a deck may stand over: the mapped roads a bore may
    follow (``structure_underpass.bore_roads``) and the mapped tunnel ways."""
    from .structure_approach import is_tunnel
    from .structure_underpass import bore_roads
    tn = law.tables.structures.tunnel
    ways = list(bore_roads(airport, law)) + [
        w for w in getattr(airport, "osm_ways", None) or ()
        if (w.tags or {}).get("highway") and len(w.points) >= 2
        and is_tunnel(w, tn.admitted_values)]
    return chains(ways)


def _crossing(db: DeckBridge, line: LineString) -> "tuple[XY, XY] | None":
    """``(the point where line crosses the deck's midline inside its ring,
    the road's unit direction there)``, or ``None`` where it does not pass
    under the deck."""
    ring = deck_polygon(db)
    if not line.intersects(ring):
        return None
    x = line.intersection(_midline(db))
    pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point" and ring.contains(g)]
    if not pts:
        return None
    s = line.project(pts[0])
    a, b = line.interpolate(max(0.0, s - 2.0)), line.interpolate(min(line.length, s + 2.0))
    n = math.hypot(b.x - a.x, b.y - a.y)
    if n <= 1e-9:
        return None
    return (pts[0].x, pts[0].y), ((b.x - a.x) / n, (b.y - a.y) / n)


def _edges(db: DeckBridge, c: XY, t: XY) -> "tuple[XY, XY]":
    """The two points where the road's straight line through ``c`` leaves
    the deck's ring (backward, forward along ``t``)."""
    ring = deck_polygon(db)
    big = 2.0 * math.sqrt(max(ring.area, 1.0)) + 100.0
    out = []
    for sign in (-1.0, 1.0):
        ray = LineString([c, (c[0] + sign * t[0] * big, c[1] + sign * t[1] * big)])
        x = ray.intersection(ring.exterior)
        hits = [q for g in getattr(x, "geoms", [x]) for q in getattr(g, "coords", [])]
        out.append(min(hits, key=lambda q: math.dist(q, c)) if hits else c)
    return out[0], out[1]


def _ray(p: XY, d: XY):
    """``s -> xy`` straight from ``p`` along ``d``."""
    return lambda s: (p[0] + d[0] * s, p[1] + d[1] * s)


def _edge_roads(db: DeckBridge, line: LineString, width: float, airport
               ) -> "tuple[XY, XY, XY, float, float] | None":
    """``(edge a, edge b, the road's direction a -> b, road at a, road at b)``
    (module doc, THE EDGE READING) of ``line``'s road under ``db``; ``None``
    where it does not pass under the deck or the survey reads nothing at an
    edge.  Read straight out of each side edge over the cover's own reach
    (``lidar_road._COVER_M``): a terrain model keeping a wide deck as ground
    spreads it 16-24 m past the ring (MEASURED KIAH obj24549-51), where the
    portal's 12 m read the deck's slope."""
    got = _crossing(db, line)
    if got is None:
        return None
    c, t = got
    pa, pb = _edges(db, c, t)
    za = surveyed_road(airport, _ray(pa, (-t[0], -t[1])), width, _COVER_M)
    zb = surveyed_road(airport, _ray(pb, t), width, _COVER_M)
    if math.isnan(za) or math.isnan(zb):
        return None
    return pa, pb, t, za, zb


def survey_under(db: DeckBridge, way, airport, law: Law) -> "float | None":
    """R5: how far under the deck's top the survey reads ``way``'s road at
    the shallower of its two side edges -- ``None`` where it is not read (a
    coarse DEM; no survey at an edge): ``deck_bores`` keeps its bank test."""
    from ..law import inset_class
    if airport is None or not inset_class.lidar_credible(airport, law) or len(way.points) < 2:
        return None
    got = _edge_roads(db, LineString(way.points), carriageway_width_m(way.tags, law), airport)
    return None if got is None else float(db.deck_z) - max(got[3], got[4])


def _applies(db: DeckBridge, level_b, inset: float) -> bool:
    return level_b is None and float(db.floor_min_m or 0.0) > 0.0 and not is_walled(db, inset)


def survey_deck_cuts(decks: _t.Sequence[DeckBridge], airport, law: Law, cells=(),
                     level_b: "float | None" = None
                     ) -> tuple[tuple[_SurveyDeckCut, ...], list[str]]:
    """``(one record per deck with a kept lane, notes)`` (module doc).  A
    road read under ``object_min_depth_m`` at an edge crosses at grade (R5)
    and is no lane; a lane clearing less than ``clearance_m`` at an edge
    keeps the ladder's floor and no cut."""
    from ..law import inset_class
    if not decks or airport is None or not inset_class.lidar_credible(airport, law):
        return (), []
    tn = law.tables.structures.tunnel
    clear = float(tn.clearance_m)
    omd = float(law.tables.structures.channel.object_min_depth_m)
    grid = max(float(law.tables.emit.identity.min_distinct_spacing_m), 0.1)
    inset = float(tn.wall_gap_m) + float(tn.wall_band_width_m) + grid
    roads = None
    found: list[tuple[_SurveyDeckCut, list]] = []
    notes: list[str] = []
    for db in decks:
        if not _applies(db, level_b, inset):
            continue
        if roads is None:
            roads = _roads(airport, law)
        cover = float(db.deck_z)
        rows, reads, short = [], [], []
        for b in roads:
            width = max(carriageway_width_m(w.tags, law) for w in b.ways)
            got = _edge_roads(db, b.line, width, airport)
            if got is None:
                continue
            pa, pb, t, za, zb = got
            wid = int(b.ways[0].id)
            if min(cover - za, cover - zb) < omd:
                continue                       # at grade over the deck (R5)
            if min(cover - za, cover - zb) < clear:
                short.append(f"{wid} ({cover - za:.2f} / {cover - zb:.2f} m)")
                continue
            rows.extend((int(w.id), pa, za, pb, zb, min(za, zb)) for w in b.ways)
            reads.append((b, pa, pb, t))
        if short:
            notes.append(f"{db.object_id}: road(s) {', '.join(short)} clear less than "
                         f"clearance_m {clear:.1f} under the cover {cover:.2f} at an edge: "
                         f"their lane keeps the ladder's floor (#2128 R1)")
        if not rows:
            continue
        f_deck = min(r[5] for r in rows)
        found.append((_SurveyDeckCut(db.object_id, tuple(db.ring), cover, tuple(rows), f_deck),
                      reads))
        seen: set = set()
        lanes = []
        for w, _p, a, _q, b, f in rows:
            if (a, b) not in seen:
                seen.add((a, b))
                lanes.append(f"{w} {a:.2f}/{b:.2f} -> {f:.2f}")
        notes.append(f"{db.object_id}: the survey's cut is kept (#2128 R1, RULINGS 2026-11-17a "
                     f"(1)): cover {cover:.2f}; per lane the floor is the lower edge road "
                     f"(not the ladder's {float(db.depth_m):.2f} m under the deck): "
                     + ", ".join(lanes))
    if not found:
        return (), notes
    rings = unary_union([deck_polygon(d) for d in decks])
    keep = _kept_parts(cells, airport, law)
    recs = []
    for rec, reads in found:
        c = _cut_region(rec.cover, reads, airport, law)
        if c is not None:
            c = c.difference(rings)
            if keep is not None:
                c = c.difference(keep)
            c = c if not c.is_empty and c.area > 1.0 else None
        recs.append(_dc.replace(rec, region=c))
        notes.append(f"{rec.object_id}: the survey's cut beside it, "
                     f"{0.0 if c is None else c.area:,.0f} m2 rim to rim (C, #2128 R1): a "
                     f"keepout, no deck ground, the mesh draws the survey")
    return tuple(recs), notes


def _out_line(b: Bore, p: XY, d: XY, length: float) -> LineString:
    """The road out of the deck edge ``p`` along ``d``: the chain's own line
    from ``p`` on where it runs that way, else the straight ray."""
    line = b.line
    s = line.project(Point(p))
    if Point(p).distance(line.interpolate(s)) <= 2.0:
        q = line.interpolate(min(line.length, s + 2.0))
        fwd = (q.x - p[0]) * d[0] + (q.y - p[1]) * d[1] > 0.0
        lo, hi = (s, line.length) if fwd else (0.0, s)
        if hi - lo >= 10.0:
            coords = list(substring(line, lo, hi).coords)
            return LineString(coords if fwd else coords[::-1])
    return LineString([p, (p[0] + d[0] * length, p[1] + d[1] * length)])


def _sections_out(line: LineString, bore: Bore, law: Law, airport, cover: float) -> list:
    """The cut's sections along ``line`` (from the deck edge outward), up to
    where the road comes within ``object_min_depth_m`` of the cover."""
    omd = float(law.tables.structures.channel.object_min_depth_m)
    secs = _sections(airport.dem, Bore(bore.ways, list(line.coords)), law, rise=omd)
    kept: list = []
    for run in section_runs(secs):
        for c in run:
            z = dem_z_at(airport, c.foot)
            if math.isnan(z) or cover - z < omd:
                return kept
            if (kept and c.s - kept[-1].s > _GAP_M) or (not kept and c.s > _GAP_M):
                return kept
            kept.append(c)
    return kept


def _cut_region(cover: float, reads, airport, law: Law):
    """THE REGION C of one deck before its exclusions (module doc): the
    ribbon of the cut's sections out of each side edge of each road
    (``reads``: ``(chain, edge a, edge b, direction a -> b)``)."""
    length = float(law.tables.structures.tunnel.max_ramp_length_m)
    parts = []
    for b, pa, pb, t in reads:
        for p, d in ((pa, (-t[0], -t[1])), (pb, t)):
            line = _out_line(b, p, d, length)
            rib = _ribbon(_sections_out(line, b, law, airport, cover))
            if rib is not None:
                parts.append(rib)
    return unary_union(parts) if parts else None


def _taxi_lines(airport) -> list[LineString]:
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    return [LineString([nodes[e.a].xy, nodes[e.b].xy])
            for e in getattr(airport, "taxi_edges", ()) or ()
            if e.a in nodes and e.b in nodes and nodes[e.a].xy != nodes[e.b].xy]


def _kept_parts(cells, airport, law: Law):
    """What C never takes: every runway-family cell, and every pavement cell
    a taxi route crosses (one geometry; ``None`` for none)."""
    from .basins import RUNWAY_FAMILY
    paved = set(pavement_roles(law))
    lines = _taxi_lines(airport)
    keep = []
    for c in cells or ():
        if len(c.ring) < 3 or c.role not in paved and c.role not in RUNWAY_FAMILY:
            continue
        p = Polygon(c.ring, c.holes)
        if c.role in RUNWAY_FAMILY or any(ln.intersects(p) for ln in lines):
            keep.append(p if p.is_valid else p.buffer(0.0))
    return unary_union(keep) if keep else None


def region_union(recs: _t.Sequence[_SurveyDeckCut]):
    """Every record's C as one geometry (``None`` for none)."""
    parts = [r.region for r in recs or () if r.region is not None]
    return unary_union(parts) if parts else None


def _cut_of(recs: _t.Sequence[_SurveyDeckCut], db) -> "_SurveyDeckCut | None":
    """The record of deck ``db`` (by object and ring), ``None`` for none."""
    for r in recs or ():
        if r.object_id == db.object_id and tuple(r.ring) == tuple(db.ring):
            return r
    return None


def deck_survey_mouth(recs: _t.Sequence[_SurveyDeckCut], db, members, law: Law):
    """The ``lidar_road.SurveyMouth`` a mouth under ``db`` is built as
    (module doc, THE FLOOR): KEPT at its lane's floor F, the cover the deck's
    top, the road the surveyed road at the deck edge nearest the mouth (F
    on the lower side; the ramp closes the rest along the road on the
    other, ``lidar_road.survey_design_grade``).  ``None`` where the deck
    has no record or the mouth's roads are none of its lanes."""
    from .lidar_road import KEPT, SurveyMouth
    rec = _cut_of(recs, db)
    if rec is None or not members:
        return None
    ids = [w.id for m in members for w in (getattr(getattr(m, "bore", None), "ways", None) or ())]
    lane = rec.lane(ids, tuple(members[0].xy))
    if lane is None:
        return None
    f, road = lane
    tol = float(law.tables.structures.placement.split_tol_m)
    return SurveyMouth(rec.cover, road, float(law.tables.structures.tunnel.clearance_m), f,
                       True, False, KEPT if road - f <= tol else "")


def cut_pavement(classification, recs: _t.Sequence[_SurveyDeckCut], airport, law: Law
                 ) -> tuple[_t.Any, list[str]]:
    """R2 (module doc): ``(classification with the pavement over C cut away,
    notes)``.  A part is cut where the survey's median under it stands below
    the cut's mid-height (half way from the floor F to the cover)."""
    c_all = region_union(recs)
    if c_all is None or classification is None or not classification.cells:
        return classification, []
    from .survey_cut import _samples
    paved = set(pavement_roles(law)) - _NEVER_CUT
    out: list[Cell] = []
    notes: list[str] = []
    for c in classification.cells:
        if c.role not in paved or c.kind == "structure" or len(c.ring) < 3:
            out.append(c)
            continue
        p = Polygon(c.ring, c.holes)
        p = p if p.is_valid else p.buffer(0.0)
        blade = []
        for r in recs:
            if r.region is None or not p.intersects(r.region):
                continue
            part = p.intersection(r.region)
            if part.is_empty or part.area <= 0.25:
                continue
            zs = sorted(_samples(airport, part))
            if zs and zs[len(zs) // 2] < 0.5 * (r.floor + r.cover):
                blade.append(r.region)
        if not blade:
            out.append(c)
            continue
        parts = [q for q in polygon_parts_with_area(p.difference(unary_union(blade)))
                 if q.area >= 0.25]
        notes.append(f"{c.ref} ({c.role}): {p.area - sum(q.area for q in parts):,.0f} m2 over "
                     f"the survey's cut cut away (#2128 R2, RULINGS 2026-11-17a (2))")
        out.extend(Cell(0, c.role, c.ref if j == 0 else f"{c.ref}#s{j}",
                        tuple(q.exterior.coords)[:-1],
                        tuple(tuple(h.coords)[:-1] for h in q.interiors),
                        c.code_number, c.code_letter, c.side, c.kind,
                        dict(c.evidence, survey_deck_cut=1.0))
                   for j, q in enumerate(parts))
    if not notes:
        return classification, notes
    return _dc.replace(classification, cells=tuple(_dc.replace(c, id=i)
                                                   for i, c in enumerate(out))), notes
