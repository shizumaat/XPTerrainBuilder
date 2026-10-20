"""THE DOOR-LINE PAD: a building on a sloping apron (owner 2026-10-20
01:15Z / 01:17Z; RULINGS 2026-10-19ak / 19w; issue #798).

Owner: "When you have a hangar on a slope, we're concerned with aircraft
being able to taxi in and out of the hangar door ... the slope of the apron
to the center of the door that the aircraft would follow needs to stay
within grade limits, but laterally either edge of the building away from
that center line can carry the extra slope to blend back into the apron,
so the majority of the apron stays within grade, but with small steeper
ramps at the building high and low side, smoother in the middle."  And the
blend "like a tunnel ramp, let's allow up to 10%, with the goal being the
smallest possible"; the same rule for a building with no aircraft door.

THE WITNESS (:func:`door_pads`).  A building pad (``building`` faces of one
ref) under ``[placement] cluster_pad_min_m2`` whose ring runs at least
``[placement] apron_shelf_min_share`` along the apron (23a welds it there)
and whose seat would float more than ``[placement] slope_pad_float_m`` on
the ground under it (``geom/slope_pad`` — the 19w reading).

THE RULE.
* ONE LEVEL: every vertex of the pad is one ``Flat`` group
  (:func:`door_pad_level`), as §42 (1b)'s hard plane is — the vertices it
  shares with the runway or taxi family are left out, the weld being
  carried by the ordinary rows across that edge.  Its level is the solve's:
  the apron's rows choose it.
* THE DOOR LINE: the door wall is the pad's hull edge nearest the taxi
  family (no open-side reading yet: the pack's wall geometry is not read
  here), among the edges whose door vertex is shared with apron or taxi
  pavement, and the taxi point lies within ``[placement]
  door_blend_reach_m`` of the door's centre — else the pad has NO door
  line and keeps its flat weld (:func:`_door_line`).
  ONE HARD ROW (:data:`DOOR_RULING`, ``[design] hard_rulings``,
  apron tier): the pad at the door's centre within the apron's (yielded)
  cap of the taxi-family vertex nearest it.  The CORRIDOR is the triangle
  of the middle ``[placement] door_corridor_share`` of the door wall and
  that taxi point.
* THE BLEND: every other APRON-generator cap row with one end ON THE PAD
  (:func:`relax_apron_caps`) is raised to ``[tunnel] ramp_max_grade``
  unless its other end lies inside the corridor; a row between two pads'
  vertices is raised too.  Chord geometry, not a vertex list: the §62 (4)
  cross-ring chords from the door vertex to the junction's outer ring held
  KASE's Hangar1 1 m above what the tower pad 8 m away allowed (round 7).
  The apron away from the pad keeps its own cap between its own vertices;
  the apron's preference and trend rows are untouched, so the ramps stay
  as gentle as the levels allow.  Taxi and runway rows are never relaxed.
* THE AIRSIDE GIVE (owner RULINGS 2026-10-19ac, ``[placement]
  door_airside_give_m``): between the stages (:func:`blend_release`) the
  pad's taxi-shared vertices and the far end of every hard row touching
  the pad leave stage 1's levels, each held within the give of its stage-1
  level by a HARD Band (:data:`GIVE_RULING`, taxi tier) and preferring it.
  A door line the give cannot satisfy is relaxed by §5a and NAMED
  (:func:`door_line_failures`).
"""
from __future__ import annotations

import contextlib
import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

from ..geom.slope_pad import seat_float_m
from ..law import Law
from ..law.tables import design as design_law
from ..model.airport import Airport
from ..model.constraints import Band, ConstraintSet, Diff, Flat, Offset, Row, Source
from ..model.planar import PlanarMap

__all__ = ["DoorPad", "door_pads", "stage_one", "blend_release", "door_pad_level",
           "relax_apron_caps", "door_line_failures", "GEN", "DOOR_HEAD", "GIVE_HEAD"]

GEN = "door_pad_level"
RULING = "a sloping building's pad is ONE level (owner 2026-10-20, #798)"
#: the door line's own law: a HARD row (``[design] hard_rulings``, apron tier)
DOOR_HEAD = "door line keeps the apron cap"
DOOR_RULING = DOOR_HEAD + " (owner 2026-10-20, #798)"
#: the airside give's Band: HARD (``[design] hard_rulings``, taxi tier)
GIVE_HEAD = "door airside give"
GIVE_RULING = GIVE_HEAD + " (owner RULINGS 2026-10-19ac, #798)"

STATS: dict[str, _t.Any] = {}
#: the last map's door-line pad refs, for the report
REFS: list[str] = []


@_dc.dataclass(frozen=True)
class DoorPad:
    ref: str
    group: tuple[int, ...]
    #: the door line's corridor: the triangle of the door wall's middle
    #: ``door_corridor_share`` and the taxi point (module docstring)
    corridor: Polygon
    door: tuple[float, float]
    #: the door line: the pad vertex at the door's centre, the taxi-family
    #: vertex it leads to, their distance and the apron cap it keeps
    door_v: int = -1
    taxi_v: int = -1
    door_m: float = 0.0
    door_cap: float = 0.0


_MEMO: list[tuple[int, _t.Any, list]] = []
#: set while stage 1's map is derived (:func:`stage_one`): no door pad there
_SUSPENDED: list[bool] = []


@contextlib.contextmanager
def stage_one():
    """No door-line pad on STAGE 1'S MAP (``pipeline/stage_one_map.
    base_pad_map``): it carries main's pads, and the door line and blend
    are stage 2's, against the solved airside (master 2026-10-20)."""
    _SUSPENDED.append(True)
    try:
        yield
    finally:
        _SUSPENDED.pop()


def _poly(planar: PlanarMap, ring) -> Polygon:
    g = Polygon([planar.vertices[v].xy for v in planar.ring_vertices(ring)])
    return g if g.is_valid else g.buffer(0.0)


def door_pads(planar: PlanarMap, law: Law, airport: Airport) -> list[DoorPad]:
    """The door-line pads of the map (module docstring), memoised per map."""
    for k, pm, got in _MEMO:
        if k == id(planar) and pm is planar:
            return got
    got = [] if _SUSPENDED else _derive(planar, law, airport)
    _MEMO.append((id(planar), planar, got))
    del _MEMO[:-2]
    return got


def _derive(planar: PlanarMap, law: Law, airport: Airport) -> list[DoorPad]:
    st = law.tables.structures.placement
    share_c = float(getattr(st, "door_corridor_share", 0.0) or 0.0)
    t = float(getattr(st, "slope_pad_float_m", 0.0) or 0.0)
    min_m2 = float(st.cluster_pad_min_m2)
    share = float(getattr(st, "apron_shelf_min_share", 0.0) or 0.0)
    dem = getattr(airport, "dem", None) if airport is not None else None
    STATS[GEN] = {"pads": 0}
    if share_c <= 0.0 or t <= 0.0 or min_m2 <= 0.0 or dem is None:
        return []
    reach = float(getattr(st, "door_blend_reach_m", 0.0) or 0.0)
    p = law.tables.precedence
    taxi = set(p.taxi_family.members)
    king = set(p.runway_family.members) | taxi
    pads: dict[str, list] = {}
    apron_v: set[int] = set()
    taxi_vs: set[int] = set()
    apron_g, king_g, king_v = [], [], set()
    for f in planar.faces.values():
        vs = set(planar.ring_vertices(f.ring))
        for h in f.holes:
            vs.update(planar.ring_vertices(h))
        if f.role == "building":
            pads.setdefault(str(f.ref), []).append(f)
        elif f.role == "apron":
            apron_v.update(vs)
            apron_g.append(_poly(planar, f.ring))
        elif f.role in king:
            king_v.update(vs)
            king_g.append(_poly(planar, f.ring))
            if f.role in taxi:
                taxi_vs.update(vs)
    if not pads or not apron_v or not king_g:
        return []
    king_u = unary_union(king_g)
    out: list[DoorPad] = []
    for ref, fs in sorted(pads.items()):
        P = unary_union([_poly(planar, f.ring) for f in fs])
        if P.is_empty or P.area >= min_m2:
            continue
        rim = {v for f in fs for v in planar.ring_vertices(f.ring)}
        on = sum(1 for v in rim if v in apron_v)
        if not rim or on < share * len(rim):
            continue
        if seat_float_m(P, dem.z) <= t:
            continue
        # EVERY vertex of the pad, the ones it shares with a taxiway too:
        # the tower's door wall IS a junction's edge, and a pad left uneven
        # along it is no level pad (measured, KASE replay: 0.39 m)
        group = tuple(sorted(v for f in fs for v in _face_vertices(planar, f)))
        if len(group) < 2:
            continue
        line = _door_line(planar, P, group, apron_v | taxi_vs, king_u, king_v,
                          share_c, reach)
        if line is None:                  # no door: the flat weld alone
            c = P.centroid
            out.append(DoorPad(ref, group, Polygon(), (c.x, c.y)))
            continue
        corridor, mid, door_v, taxi_v, dxy = line
        out.append(DoorPad(ref, group, corridor, (mid.x, mid.y),
                           door_v, taxi_v, dxy, _door_cap(planar, law, mid)))
    STATS[GEN] = {"pads": len(out)}
    REFS[:] = [d.ref for d in out]
    return out


def _door_line(planar: PlanarMap, P, group: tuple[int, ...], pave_v: set[int],
               king_u, king_v: set[int], share: float, reach: float):
    """THE DOOR LINE of one pad, or ``None`` where it has no door
    (master 2026-10-20 on lane m15's HECA reading):

    * the door wall is the hull edge nearest the taxi family AMONG THOSE
      whose door vertex (the pad vertex nearest the wall's centre) is
      shared with pavement an aircraft stands on (apron or taxi family).
      MEASURED (HECA building97): the hull edge nearest the taxi family
      faced a parking lot and its door line read 4.45 m infeasible;
    * the taxi point lies within ``[placement] door_blend_reach_m`` of the
      door's centre.  MEASURED (HECA building116 / building123): a door on
      the apron 209 / 262 m from the nearest taxi point asked an apron-wide
      chord at the apron cap, 9.42 / 8.54 m infeasible — not a door onto a
      taxiway.

    Returns ``(corridor, door centre, door vertex, taxi vertex, the
    line's distance)``."""
    def door_v_of(w):
        m = w.interpolate(0.5, normalized=True)
        return min(group, key=lambda v: m.distance(Point(planar.vertices[v].xy)))
    cs = list(P.convex_hull.exterior.coords)[:-1]
    walls = [w for w in (LineString([cs[i], cs[(i + 1) % len(cs)]]) for i in range(len(cs)))
             if door_v_of(w) in pave_v]
    if not walls:
        return None
    door = min(walls, key=lambda w: w.interpolate(0.5, normalized=True).distance(king_u))
    mid = door.interpolate(0.5, normalized=True)
    tp = nearest_points(mid, king_u)[1]
    if reach > 0.0 and mid.distance(tp) > reach:
        return None
    taxi_v = min(king_v, key=lambda v: tp.distance(Point(planar.vertices[v].xy)))
    # the pad is ONE level, so its value at the door's centre is the door
    # vertex's: the line is priced over the CENTRE's own distance
    return (_corridor(door, tp, share), mid, door_v_of(door), taxi_v,
            float(mid.distance(Point(planar.vertices[taxi_v].xy))))


def _corridor(door: LineString, tp: Point, share: float) -> Polygon:
    """THE DOOR LINE'S CORRIDOR: the triangle of the door wall's middle
    ``share`` and the taxi point ``tp``.  MEASURED (KASE round 7): a strip
    as wide as the door share held rows off the door's far corners at the
    apron cap; the triangle narrows to the one point the aircraft taxis
    from."""
    lo, hi = 0.5 - 0.5 * share, 0.5 + 0.5 * share
    wl = door.interpolate(lo, normalized=True)
    wr = door.interpolate(hi, normalized=True)
    tri = Polygon([(wl.x, wl.y), (wr.x, wr.y), (tp.x, tp.y)])
    if tri.is_valid and tri.area > 0.0:
        return tri
    return door.interpolate(0.5, normalized=True).buffer(0.5 * share * door.length)


def blend_release(planar: PlanarMap, law: Law, airport: Airport | None,
                  levels: _t.MutableMapping[int, float],
                  cs: ConstraintSet | None = None
                  ) -> tuple[dict[str, _t.Any], list[Band], dict[int, float]]:
    """THE BLEND'S ROOM AND THE AIRSIDE GIVE, between the stages (bound with
    ``road_ramp.reach_seed_rewrite``): stage 1 solved the airside without
    the 19w pads (``pipeline/stage_one_map.base_pad_map``).  Leaving
    ``levels`` so stage 2 solves them with the pad:

    * the pad's own vertices and the apron vertices within ``[placement]
      door_blend_reach_m`` of a door-line pad, none of them shared with the
      runway or taxi family (the blend's room);
    * THE GIVE (owner RULINGS 2026-10-19ac, ``[placement]
      door_airside_give_m``; 0 disarms): the pad's taxi-shared vertices
      and the far end of every HARD row of ``cs`` touching a pad vertex,
      within the same reach and never a runway-family vertex.  MEASURED
      (KASE replay, every far end): a long route pair or body chord
      reached 38 vertices up to 404 m off, which drifted up to 0.036 m and
      flipped marginal census rows there; a far end that distant meets
      the pad over a long run, its bound loose.  Each is returned with a HARD
      ``Band`` within the give of its stage-1 level and that level as its
      preferred value, so the airside moves no more than the give and as
      little as the pad allows.  MEASURED (KASE round 7): with the airside
      frozen Hangar1's door line needed the pad >= 2356.558 against a
      tower pad and junction constants allowing <= 2356.347.

    Returns ``(report, bands, preferred_z)``."""
    st = law.tables.structures.placement
    reach = float(getattr(st, "door_blend_reach_m", 0.0) or 0.0)
    give_m = float(getattr(st, "door_airside_give_m", 0.0) or 0.0)
    pads = door_pads(planar, law, airport) if reach > 0.0 else []
    if not pads:
        return {"pads": 0, "released": 0}, [], {}
    p = law.tables.precedence
    king = set(p.runway_family.members) | set(p.taxi_family.members)
    rwy_roles = set(p.runway_family.members)
    held: set[int] = set()
    rwy: set[int] = set()
    for f in planar.faces.values():
        if f.role in king:
            vs = _face_vertices(planar, f)
            held.update(vs)
            if f.role in rwy_roles:
                rwy.update(vs)
    zone = unary_union([Polygon([planar.vertices[v].xy for v in d.group]).convex_hull
                        for d in pads]).buffer(reach)
    # the pad's own vertices too: one the stage-1 map also carries (an apron
    # vertex the 23a weld put on the rim) would hold the whole level there
    # (MEASURED, KASE: Hangar1's door vertex held 0.21 m off its door line)
    own = {v for d in pads for v in d.group}
    out = [v for v in list(levels)
           if v not in held and v in planar.vertices
           and (v in own or (zone.contains(Point(planar.vertices[v].xy))
                             and any(planar.faces[f].role == "apron"
                                     for f in planar.vertices[v].incident_faces)))]
    give = sorted(v for v in _give_set(own, held, cs, law) - rwy
                  if v in levels and (v in own or zone.contains(Point(planar.vertices[v].xy)))) \
        if give_m > 0.0 else []
    bands = [Band(v, levels[v] - give_m, levels[v] + give_m,
                  Source(GEN, GIVE_RULING, (f"vertex:{v}", f"give_m:{give_m:g}")))
             for v in give]
    pref = {v: float(levels[v]) for v in give}
    for v in {*out, *give}:
        del levels[v]
    return ({"pads": len(pads), "released": len(out), "reach_m": reach,
             "give": len(give), "give_m": give_m}, bands, pref)


def _give_set(own: set[int], held: set[int], cs: ConstraintSet | None,
              law: Law) -> set[int]:
    """The pad's taxi-shared vertices and the far end of every HARD row of
    ``cs`` touching a pad vertex (:func:`blend_release`)."""
    got = own & held
    if cs is None:
        return got
    d = design_law(law)
    heads = {*d.hard_rulings, *d.fronting_hard_rulings, *d.apron_hard_rulings}
    for r in (*cs.diffs, *cs.offsets, *cs.linears):
        if r.source.ruling.split(" (")[0].strip() not in heads:
            continue
        vs = (r.a, r.b) if isinstance(r, (Diff, Offset)) else \
            tuple(v for v, _c in r.terms)
        if any(v in own for v in vs):
            got.update(v for v in vs if v not in own)
    return got


def door_line_failures(conflicts: _t.Iterable[dict], give_m: float) -> list[str]:
    """THE NAMED FAILURE (round-3 spec D3): one line per DOOR LINE row §5a
    relaxed (``hard_conflict``, the sidecar's own records)."""
    out = []
    for c in conflicts:
        if c.get("row") != DOOR_HEAD:
            continue
        ref = (c.get("inputs") or ["?"])[0]
        site = c.get("site") or [float("nan"), float("nan")]
        out.append(f"DOOR LINE {ref} at {float(site[0]):.7f},{float(site[1]):.7f} "
                   f"INFEASIBLE by {float(c.get('s_m', 0.0)):.3f} m with "
                   f"{give_m:g} m airside give")
    return out


def _door_cap(planar: PlanarMap, law: Law, at: Point) -> float:
    """The apron cap the door line keeps: the hard longitudinal cap of the
    apron face nearest the door (its yielded cap where its runway yielded,
    §50.1 (4) — ``precedence.view``'s own reading)."""
    from .precedence import view
    vw = view(planar, law)
    best, cap = None, 0.0
    for f in planar.faces.values():
        if f.role != "apron" or vw.caps.get(f.id) is None:
            continue
        d = _poly(planar, f.ring).distance(at)
        if best is None or d < best:
            best, cap = d, float(vw.caps[f.id][0])
    return cap


def _face_vertices(planar: PlanarMap, f) -> set[int]:
    vs = set(planar.ring_vertices(f.ring))
    for h in f.holes:
        vs.update(planar.ring_vertices(h))
    return vs


def door_pad_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ONE ``Flat`` per door-line pad, and its DOOR LINE: the pad at the
    door's centre within the apron cap of the taxi-family vertex the line
    leads to — ONE HARD ROW (:data:`DOOR_RULING`), so the pad's level is
    chosen where an aircraft can still taxi in (module docstring)."""
    rows: list[Row] = []
    for d in door_pads(planar, law, airport):
        rows.append(Flat(d.group, Source(GEN, RULING, (d.ref, f"vertices:{len(d.group)}"))))
        if d.door_v >= 0 and d.taxi_v >= 0 and d.door_v != d.taxi_v \
                and d.door_m > 0.0 and d.door_cap > 0.0:
            rows.append(Diff(d.door_v, d.taxi_v, d.door_cap, d.door_m,
                             Source(GEN, DOOR_RULING,
                                    (d.ref, f"door:{d.door_v}", f"taxi:{d.taxi_v}"))))
    return rows


def relax_apron_caps(rows: list[Row], planar: PlanarMap, law: Law,
                     airport: Airport, counts: dict | None = None) -> list[Row]:
    """The APRON generator's cap rows (``constraints/apron``) with one end
    on a door pad raised to ``[tunnel] ramp_max_grade`` — unless the other
    end lies inside that pad's corridor; a row between two pads' vertices
    is raised either way (module docstring).  Every other row as is."""
    from .apron import GEN as APRON_GEN
    pads = door_pads(planar, law, airport)
    if not pads:
        return rows
    pad_of = {v: d for d in pads for v in d.group}
    # the corridor read with half a metre's tolerance: the taxi point is a
    # projection, the vertex the door line ends on lies beside it
    inside = {d.ref: d.corridor.buffer(0.5) for d in pads}
    top = float(law.tables.structures.tunnel.ramp_max_grade)
    out: list[Row] = []
    n = 0
    for r in rows:
        if (isinstance(r, Diff) and r.soft is None and r.cap < top
                and r.source.generator == APRON_GEN
                and _blends(r, pad_of, inside, planar)):
            out.append(_dc.replace(r, cap=top))
            n += 1
        else:
            out.append(r)
    if counts is not None:
        counts[f"{GEN}.apron_rows_relaxed"] = n
    return out


def _blends(r: Diff, pad_of: dict[int, DoorPad], inside: dict[str, Polygon],
            planar: PlanarMap) -> bool:
    """Whether a cap row is one of the pad's blend ramps
    (:func:`relax_apron_caps`)."""
    pa, pb = pad_of.get(r.a), pad_of.get(r.b)
    if pa is not None and pb is not None:
        return True
    if pa is None and pb is None:
        return False
    pad, other = (pa, r.b) if pa is not None else (pb, r.a)
    return not inside[pad.ref].contains(Point(planar.vertices[other].xy))
