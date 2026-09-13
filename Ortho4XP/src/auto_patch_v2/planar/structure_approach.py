"""THE BORES, MOUTHS AND APPROACHES of the OSM tunnel ways (M4; split out
of ``planar/structures.py`` for lane v2tunnelobj2 so that file stays
under its line budget — no behaviour moved with it): the way predicates,
the carriageway width, bore chains, the approach centreline outward
from a mouth, the mouths themselves and 31h's dual-carriageway merge.
Law ``structures.toml [tunnel]``; see ``planar/structures.py``'s module
doc for the model.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.approach_corridor import ApproachCorridor, RunwayViewBand
from ..law.tables import role_family
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..airport.deck_signature import (DEFAULT_TUNNEL_VALUES, is_bridge_way,
                                      is_tunnel_way)
from ..classify.roles import Cell

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _dem(airport: Airport, p: XY) -> float:
    """ONE implementation with ``planar/structures._dem`` (the DEM sample
    at a frame point)."""
    return float(airport.dem.z(p[0], p[1]))


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]

__all__ = ["PavementDeck", "pavement_deck_intervals", "deck_intervals", "object_deck_intervals", "carriageway_width_m", "pavement_half_widths", "Bore", "Mouth", "chains", "approach",
           "resample",
           "mouths", "FieldRegion", "ApproachCorridor", "RunwayViewBand", "approach_corridor_of", "runway_band_of", "field_region_for", "mouth_reports", "under_cover", "merge_duals", "unit", "is_tunnel", "is_bridge", "MAX_HOPS",
           "PARALLEL_COS", "NODE_TOL", "apply_plates", "ramp_top", "approach_ground", "deck_ends"]

#: Two OSM node coordinates closer than this (frame metres) are one node.
NODE_TOL = 0.05
#: Approach ways are followed at most this many hops from the mouth.
MAX_HOPS = 6
#: Two directions within 30° are parallel (31h's dual test; the approach kink test).
PARALLEL_COS = math.cos(math.radians(30))


# ── tags ─────────────────────────────────────────────────────────────────

def is_tunnel(w: OsmWay,
              admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES) -> bool:
    """One predicate with ``airport/deck_signature.is_tunnel_way`` (§26:
    ``admitted`` is ``law.tables.structures.tunnel.admitted_values``)."""
    return is_tunnel_way(w.tags, admitted)


def is_bridge(w: OsmWay) -> bool:
    """One predicate with the deck signature's (``airport/deck_signature``)."""
    return is_bridge_way(w.tags)


def carriageway_width_m(tags: _t.Mapping[str, str], law: Law) -> float:
    """The way's stated ``width``, else ``lanes × lane_width_m`` (a
    railway counts as ``default_lanes``)."""
    tn = law.tables.structures.tunnel
    w = tags.get("width")
    if w:
        try:
            return max(1.0, float(w.replace("m", "").strip()))
        except ValueError:
            pass
    lanes = tags.get("lanes")
    try:
        n = int(lanes) if lanes else tn.default_lanes
    except ValueError:
        n = tn.default_lanes
    return max(1, n) * tn.lane_width_m


def pavement_half_widths(axis_fn, ss: _t.Sequence[float], cells, polys, law: Law,
                         half_default: float) -> "tuple[dict[float, tuple[float, float]], list[str]]":
    """THE RAMP WIDTH FROM THE PAVEMENT (RULINGS 2026-09-06b (2); ``tunnel.
    ramp_width_source``): per station ``s`` the ramp's half widths ``(left,
    right)`` read from the pavement cell that TRACES the road there — a
    value cell (never the runway family, never a pad) containing the
    station whose across-axis centre lies within
    ``ramp_pavement_max_offset_m`` of the axis and which runs ALONG the
    axis (it contains the neighbouring stations too).  Stations no
    pavement traces are absent (the caller's lanes width stands).
    Returns the map and the cells' refs used."""
    from ..law.tables import is_value_role
    tn = law.tables.structures.tunnel
    if not tn.ramp_width_source or tn.ramp_width_source[0] != "pavement":
        return {}, []
    max_off = tn.ramp_pavement_max_offset_m
    cand = [(p, c) for p, c in zip(polys, cells)
            if is_value_role(law, c.role) and c.role not in ("runway", "runway_crossing",
                                                              "building")]
    if not cand:
        return {}, []
    # a station ON the pavement's edge (the mouth where the traced road
    # ends at the bore) counts: containment within one identity-grid step
    grid = law.tables.emit.identity.min_distinct_spacing_m
    hulls = [p.buffer(grid) for p, _c in cand]
    tree = STRtree(hulls)
    out: dict[float, tuple[float, float]] = {}
    refs: list[str] = []
    n = len(ss)
    reach = 10.0 * max(half_default, 1.0)
    for i, s in enumerate(ss):
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        prev_pt = axis_fn(ss[i - 1]) if i > 0 else None
        next_pt = axis_fn(ss[i + 1]) if i + 1 < n else None
        best = None
        for j in tree.query(Point(p), predicate="within"):
            poly, c = cand[int(j)]
            hull = hulls[int(j)]
            along = all(hull.contains(Point(q)) for q in (prev_pt, next_pt) if q is not None)
            if not along:
                continue
            ray_l = LineString([p, (p[0] + nv[0] * reach, p[1] + nv[1] * reach)])
            ray_r = LineString([p, (p[0] - nv[0] * reach, p[1] - nv[1] * reach)])
            hl = _ray_hit(ray_l, poly, p)
            hr = _ray_hit(ray_r, poly, p)
            if hl is None or hr is None:
                continue
            off = abs(hl - hr) / 2.0
            if off > max_off:
                continue
            if best is None or off < best[0]:
                best = (off, hl, hr, c.ref)
        if best is not None:
            out[s] = (best[1], best[2])
            if best[3] not in refs:
                refs.append(best[3])
    return out, refs


def _ray_hit(ray: LineString, poly, p: XY) -> float | None:
    """The distance from ``p`` along ``ray`` to the polygon's boundary."""
    x = ray.intersection(poly.boundary)
    if x.is_empty:
        return None
    pts = [g for g in shapely.get_parts(x) if g.geom_type == "Point"]
    if not pts:
        return None
    return min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts)


# ── bores (chains of tunnel ways) ────────────────────────────────────────

def _key(p: XY) -> tuple[int, int]:
    return (int(round(p[0] / NODE_TOL)), int(round(p[1] / NODE_TOL)))


@_dc.dataclass
class Bore:
    ways: list[OsmWay]
    points: list[XY]          # the chain, in order

    @property
    def line(self) -> LineString:
        return LineString(self.points)


def chains(ways: list[OsmWay]) -> list[Bore]:
    """Join tunnel ways end to end where exactly two of them meet."""
    ends: dict[tuple[int, int], list[int]] = {}
    for i, w in enumerate(ways):
        ends.setdefault(_key(w.points[0]), []).append(i)
        ends.setdefault(_key(w.points[-1]), []).append(i)
    used = [False] * len(ways)
    out: list[Bore] = []
    for i, w in enumerate(ways):
        if used[i]:
            continue
        used[i] = True
        pts = list(w.points)
        members = [w]
        for direction in (1, -1):
            while True:
                end = pts[-1] if direction == 1 else pts[0]
                cands = [j for j in ends.get(_key(end), ()) if not used[j]]
                if len(cands) != 1 or len(ends.get(_key(end), ())) != 2:
                    break
                j = cands[0]
                used[j] = True
                nxt = list(ways[j].points)
                if _key(nxt[-1]) == _key(end):
                    nxt.reverse()
                if direction == 1:
                    pts.extend(nxt[1:])
                else:
                    pts = list(reversed(nxt[1:])) + pts
                members.append(ways[j])
        out.append(Bore(members, pts))
    return out


# ── the approach ─────────────────────────────────────────────────────────

def approach(mouth: XY, inward: XY, ways: list[OsmWay], reach_m: float,
             admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES,
             turn_max_deg: float = 180.0) -> list[XY]:
    """The centreline OUTWARD from the mouth: non-tunnel ways joined at
    the mouth node, followed up to ``reach_m``; a straight extension of
    the bore's own end direction where no way continues.

    THE APPROACH WALK KEEPS ITS HEADING (spec §34 (2); Fable
    2026-09-13i, RULINGS 2026-09-13i item 7a).  At every node the walk
    takes the continuation with the SMALLEST TURN from the heading it
    arrived on, and refuses a turn over ``turn_max_deg``
    (``[tunnel] approach_turn_max_deg``, 60°) — an unrelated road
    meeting the approach at a junction is not the road the ramp is on.
    The route stays on the way it entered until that way ENDS (a way is
    walked whole, so a hairpin's own nodes — which turn gradually — are
    never a hop and are never refused).  Before this the walk tested
    direction on the FIRST hop only and then took the first candidate in
    load order at each node: LEMD −5980's ramp left its hairpin onto
    −15331 (33.3°) with −15328 (2.3°) beside it."""
    idx: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, w in enumerate(ways):
        if is_tunnel(w, admitted) or ("highway" not in w.tags
                                      and "railway" not in w.tags):
            continue
        idx.setdefault(_key(w.points[0]), []).append((i, True))
        idx.setdefault(_key(w.points[-1]), []).append((i, False))
    path: list[XY] = [mouth]
    cur = mouth
    length = 0.0
    seen: set[int] = set()
    heading: XY = (-inward[0], -inward[1])     # OUTWARD from the bore
    cos_max = math.cos(math.radians(max(0.0, min(180.0, turn_max_deg))))
    for _hop in range(MAX_HOPS):
        best = None
        best_cos = cos_max - 1e-12
        for i, forward in idx.get(_key(cur), ()):
            if i in seen:
                continue
            pts = list(ways[i].points) if forward else list(reversed(ways[i].points))
            d = unit(cur, pts[min(1, len(pts) - 1)])
            c = d[0] * heading[0] + d[1] * heading[1]
            if c > best_cos:                   # the smallest turn, inside the cap
                best_cos, best = c, (i, pts)
        if best is None:
            break
        i, pts = best
        seen.add(i)
        for p in pts[1:]:
            length += math.hypot(p[0] - cur[0], p[1] - cur[1])
            path.append(p)
            if p != cur:
                heading = unit(cur, p)
            cur = p
            if length >= reach_m:
                return path
    if length < reach_m:
        # straight on, along the last direction (or away from the bore)
        if len(path) >= 2:
            ax, ay = path[-1][0] - path[-2][0], path[-1][1] - path[-2][1]
        else:
            ax, ay = -inward[0], -inward[1]
        L = math.hypot(ax, ay) or 1.0
        path.append((cur[0] + ax / L * (reach_m - length + 1.0),
                     cur[1] + ay / L * (reach_m - length + 1.0)))
    return path


def resample(path: _t.Sequence[XY], ss: _t.Sequence[float]) -> list[XY]:
    ln = LineString(path)
    out = []
    for s in ss:
        p = ln.interpolate(min(s, ln.length))
        out.append((p.x, p.y))
    return out


# ── the mouths ───────────────────────────────────────────────────────────

@_dc.dataclass
class Mouth:
    bore: Bore
    xy: XY
    inward: XY               # unit vector INTO the bore
    width_m: float
    approach: list[XY]
    ways: tuple[int, ...]


def unit(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def under_cover(line: LineString, polys: _t.Sequence[Polygon], tree) -> bool:
    """The RETIRED admission test (spec §29 (2)) — >= 1 m of the bore under
    the classified cover — kept only to count the bores the mouth-based
    admission and it disagree on (``bores_mouth_only``).  Reads the cell
    tree rather than a union of every cell (same answer, no union to
    build).  Lives here, beside the gate it is compared against, so
    ``structures.py`` stays under its 1,000-line budget."""
    if tree is None:
        return False
    parts = [line.intersection(polys[int(j)])
             for j in tree.query(line, predicate="intersects")]
    parts = [g for g in parts if not g.is_empty]
    return bool(parts) and unary_union(parts).length >= 1.0


def field_region_for(airport, law: Law, polys: _t.Sequence[Polygon]
                     ) -> "FieldRegion":
    """THE REGION A MOUTH MAY STAND IN, assembled in ONE place: the
    classified cover (with the roofed corridors' footprints, which the
    caller passes in ``polys``) ⊕ ``[tunnel] mouth_standoff_m``, union
    the approach corridor of §31 (2), union THE RUNWAY LATERAL BAND of
    §29 (7)."""
    return FieldRegion(list(polys),
                       law.tables.structures.tunnel.mouth_standoff_m,
                       approach_corridor_of(airport, law),
                       runway_band_of(airport, law))


def mouth_reports(on_field: "FieldRegion", mouth_list: _t.Sequence["Mouth"],
                  dropped: _t.Sequence[tuple]) -> tuple[list[str], int, list[str]]:
    """``(off-field lines, on-approach count, on-approach lines)`` for the
    structures line — the nearest drops and every mouth THE CORRIDOR
    kept, each with its true distance off the field, so both findings are
    visible without a rebuild and neither is read as the other."""
    off = [f"mouth off-field {ids} at {xy[0]:.0f},{xy[1]:.0f} — {d:.0f} m off "
           f"the field, outside every approach corridor and outside the "
           f"runway lateral band"
           for ids, xy, d in sorted(dropped, key=lambda t: t[2])[:8]]
    on_approach = [m for m in mouth_list if not on_field.on_cover(Point(m.xy))]
    named = [f"mouth on approach {'+'.join(str(i) for i in m.ways)} at "
             f"{m.xy[0]:.0f},{m.xy[1]:.0f} — "
             f"{on_field.cover_distance_m(Point(m.xy)):.0f} m off the field, "
             f"in view ({_view_reason(on_field, m)})"
             for m in on_approach[:12]]
    return off, len(on_approach), named


def _view_reason(on_field: "FieldRegion", m: "Mouth") -> str:
    """WHICH TERM ADMITTED THIS MOUTH — §31 (2)'s approach corridor, §29
    (7)'s runway lateral band, or the ramp reach reaching one of them.
    The report states its own attribution: "in view" alone let 12al's
    corridor and 13bm's band be read as one region."""
    pt = Point(m.xy)
    reach = LineString(m.approach) if len(m.approach) >= 2 else pt
    for name, geom in (("approach corridor", pt), ("approach corridor", reach)):
        if on_field.in_corridor(geom):
            return name if geom is pt else name + ", by its ramp reach"
    for geom in (pt, reach):
        if on_field.in_band(geom):
            return ("runway lateral band" if geom is pt
                    else "runway lateral band, by its ramp reach")
    return "cover, by its ramp reach"


def approach_corridor_of(airport, law: Law) -> ApproachCorridor:
    """THE APPROACH CORRIDOR of §31 (2) for one airport, from the model's
    OWN runway ends (apt.dat row 100 thresholds) and the two ``[cockpit]``
    numbers — never a second idea of either.

    The harness reaches the same class from the emitted patch (the
    principal axis of each runway's ring cloud): one derivation, two
    sources for the axis it is derived FROM, which is why
    ``tests/auto_patch_v2/test_v2approachcorridor.py`` pins them against
    one fixture."""
    return ApproachCorridor(_runway_axes(airport),
                            float(law.tables.emit.cockpit.approach_km) * 1000.0,
                            float(law.tables.emit.cockpit.approach_half_width_m))


def _runway_axes(airport) -> list[tuple]:
    """The model's OWN runway axes (apt.dat row 100 thresholds) — the ONE
    source both §31 (2)'s corridor and §29 (7)'s band are built from."""
    return [(r.ends[0].xy, r.ends[1].xy, r.id)
            for r in getattr(airport, "runways", ()) or ()]


def runway_band_of(airport, law: Law) -> RunwayViewBand:
    """§29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; owner RULINGS
    2026-09-13bm (ii)) for one airport: each runway's axis ⊕ ``[cockpit]
    runway_view_half_width_m``, from the SAME axes and the SAME
    ``law/approach_corridor`` derivation as the corridor."""
    return RunwayViewBand(
        _runway_axes(airport),
        float(law.tables.emit.cockpit.runway_view_half_width_m))


class FieldRegion:
    """THE REGION A MOUTH MAY STAND IN (spec §29 (1) as amended by owner
    RULINGS 2026-09-12al): the classified cover ⊕ ``[tunnel]
    mouth_standoff_m`` **∪ THE APPROACH CORRIDOR of §31 (2)**.

    The cover carries the ROOFED CORRIDORS' footprints — the object /
    kerb-wall corridors are the owner's EGLL exception (Laws B/C, keyed on
    the pack's geometry, never on OSM) and are the field authority where
    they stand, so a bore mouth an object corridor takes is never gated
    away before the precedence runs.  Held as polygons in an STRtree with
    a ``dwithin`` query rather than a buffered union — the same region,
    exactly, without buffering a thousand-part union.

    THE CORRIDOR IS NOT THIS MODULE'S IDEA of a corridor: it is
    ``law/approach_corridor.ApproachCorridor``, the ONE derivation the
    harness's cockpit block reads too (owner 12al: "if it would be visible
    from an arriving or departing aircraft it should be cut, if not we can
    leave it raw DEM").  A portal 208 m off the classified surfaces but on
    the extended centreline of runway 14R is in plain view; one 4 km west
    of everything may be too, and the answer is the corridor's, not a
    standoff's.  ``corridor`` may be ``None`` (a caller with no runway
    geometry): the cover then decides alone."""

    def __init__(self, polys: _t.Sequence[Polygon], standoff_m: float,
                 corridor=None, band=None) -> None:
        self.standoff_m = float(standoff_m)
        self._tree = STRtree(list(polys)) if len(polys) else None
        self.corridor = corridor
        rings = list(corridor.rings()) if corridor is not None else []
        self._corridor_tree = (STRtree([Polygon(r) for r in rings])
                               if rings else None)
        self.band = band
        brings = list(band.rings()) if band is not None else []
        self._band_tree = (STRtree([Polygon(r) for r in brings])
                           if brings else None)

    def holds(self, geom) -> bool:
        """``geom`` (a mouth point or its ramp reach) stands where a pilot
        would see it: on the field, in an approach corridor, or BESIDE a
        runway inside §29 (7)'s lateral band."""
        return self.on_cover(geom) or self.in_corridor(geom) or \
            self.in_band(geom)

    def in_band(self, geom) -> bool:
        """§29 (7) THE RUNWAY LATERAL BAND alone (Fable 2026-09-13; owner
        RULINGS 2026-09-13bm (ii)) — quoted separately in the report, like
        the corridor, so "beside the runway" is never read as "on the
        field".  The corridor runs BEYOND each threshold and never beside
        the runway; SPJC's trunk-tunnel south mouths stood 191 m off the
        cover, 5 km from every corridor and 192 m from runway 16R/34L at
        mid-length."""
        if self._band_tree is None:
            return False
        return len(self._band_tree.query(geom,
                                         predicate="intersects")) > 0

    def on_cover(self, geom) -> bool:
        """The cover ⊕ ``mouth_standoff_m`` half alone."""
        if self._tree is None:
            return False
        return len(self._tree.query(geom, predicate="dwithin",
                                    distance=self.standoff_m)) > 0

    def in_corridor(self, geom) -> bool:
        """The §31 (2) half alone — quoted separately in the report, so a
        mouth built ON APPROACH is never read as a mouth on the field."""
        if self._corridor_tree is None:
            return False
        return len(self._corridor_tree.query(geom,
                                             predicate="intersects")) > 0

    def cover_distance_m(self, geom) -> float:
        """Distance to the CLASSIFIED COVER alone — how far off the field
        a mouth the corridor admitted actually stands."""
        if self._tree is None:
            return float("inf")
        j = self._tree.nearest(geom)
        if j is None:
            return float("inf")
        return float(self._tree.geometries[int(j)].distance(geom))

    def distance_m(self, geom) -> float:
        """How far off the REGION ``geom`` stands (the dropped-mouth
        report): the lesser of its distance to the cover and to the
        nearest corridor edge; ``inf`` when there is neither."""
        d = self.cover_distance_m(geom)
        for tree in (self._corridor_tree, self._band_tree):
            if tree is None:
                continue
            j = tree.nearest(geom)
            if j is not None:
                d = min(d, float(tree.geometries[int(j)].distance(geom)))
        return d


def mouths(bores: list[Bore], osm: list[OsmWay], law: Law, reach_m: float,
           on_field=None) -> tuple[list[Mouth], int]:
    """The mapped ends of every bore, as mouths — GATED BY THE FIELD (spec
    §29 (1), owner RULINGS 2026-09-12r; Fable 2026-09-12t): "a tunnel
    emits only its mouths and ramps", and a mouth is built only where it
    STANDS ON THE FIELD.  ``on_field`` is the airport's governed region —
    the classified cover with the roofed corridors ⊕ ``[tunnel]
    mouth_standoff_m`` — prepared by the caller.  THE TEST IS THE MOUTH
    POINT *AND ITS RAMP REACH* (§29 (1)): a mapped end whose point stands
    outside the region AND whose approach corridor — the reach the ramp
    would be built along — never enters it is DROPPED here and counted in
    the returned tally, which the structures line names (``mouths
    off-field N``).  A mouth just off the cover whose ramp climbs onto the
    field is what that clause protects; the rail mouths 4.0 km out are
    neither.  ``on_field = None`` gates nothing (a caller with no
    classification).  The second member of the return is the dropped
    mouths — ``(way ids, xy, distance off the field)`` — for the report.

    LEMD's two rail bores are why: 4.9 km ways admitted by 125–162 m of
    cover under the ``building12`` pad whose SOUTH-WEST ends stand 4.0 km
    west of every other feature and 95 m up a hillside — ramps, rims and
    banks (149 vertices) that set the patch's whole western bbox edge and
    carry zero grade rows.
    """
    out: list[Mouth] = []
    dropped: list[tuple[str, XY, float]] = []
    for b in bores:
        width = max(carriageway_width_m(w.tags, law) for w in b.ways)
        wids = tuple(w.id for w in b.ways)
        cand: list[tuple[Mouth, bool, float]] = []
        for end, nxt in ((b.points[0], b.points[1]), (b.points[-1], b.points[-2])):
            inward = unit(end, nxt)
            path = approach(end, inward, osm, reach_m,
                            law.tables.structures.tunnel.admitted_values,
                            law.tables.structures.tunnel.approach_turn_max_deg)
            m = Mouth(b, end, inward, width, path, wids)
            if on_field is None:
                cand.append((m, True, 0.0))
                continue
            pt = Point(end)
            reach = LineString(path) if len(path) >= 2 else pt
            held = on_field.holds(pt) or on_field.holds(reach)
            cand.append((m, held, min(on_field.distance_m(pt),
                                      on_field.distance_m(reach))))
        # §29 (7) THE SIBLING MOUTH — RULED (Fable 2026-09-13; owner
        # RULINGS 2026-09-13bm (ii): "a bore with one mouth built has its
        # sibling admitted under the same test; a tunnel with one mouth is
        # never right") and MEASURED REFUTED at LEMD by lane ``v2spjc``,
        # so it is NOT armed and the clause is deleted rather than gated.
        #
        # THE MEASUREMENT (dry ``--stage structures`` arms on main
        # 0c86fe2c, three-way base / band-only / band+sibling):
        #   * SPJC needs it for NOTHING.  The bar — the −641/−2525 trunk
        #     tunnel's south mouth at −12.0202431, −77.129278 — is built
        #     by §29 (7)'s RUNWAY LATERAL BAND alone (191 m off the
        #     cover, inside the 250 m band of runway 16R/34L); the
        #     band-only arm and the band+sibling arm are identical at
        #     SPJC (mouths 14, tunnels 8, off-field 6).
        #   * LEMD it REGRESSES.  Armed, it rebuilt three mouths the
        #     150 m standoff of RULINGS 2026-09-12r exists to drop —
        #     ``tunnel:-4928@1`` 2,309 m off the field and
        #     ``tunnel:-26708+-22223@0`` / ``tunnel:-26709+-8677@0`` at
        #     40.48100, −3.63953 and 40.48053, −3.63947, ~6.7 km west of
        #     the frame origin: the rail-bore class whose far mouths set
        #     the patch's whole western bbox edge (LEMD tunnels 51 -> 54,
        #     mouths 90 -> 93, off-field 45 -> 42).  A 4.9 km bore
        #     admitted by 125–162 m of cover under ONE pad is exactly the
        #     case where the sibling is nowhere a pilot looks.
        #
        # A narrowing that separates the two needs a law number this lane
        # may not author (a bore length, or a distance from the built
        # mouth).  Routed to the spec's author with the measurement.
        for m, held, d in cand:
            if held:
                out.append(m)
            else:
                dropped.append(("+".join(str(i) for i in wids), m.xy, d))
    return out, dropped


def _parallel(a: Mouth, b: Mouth, sep_max: float) -> bool:
    """31h's test: mouths within the dual separation, approaches parallel
    and holding that separation 50 m out."""
    if b.bore is a.bore:
        return False
    d0 = math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1])
    if d0 > sep_max:
        return False
    if a.inward[0] * b.inward[0] + a.inward[1] * b.inward[1] < PARALLEL_COS:
        return False
    pa, pb = resample(a.approach, [50.0])[0], resample(b.approach, [50.0])[0]
    d1 = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    return abs(d1 - d0) <= 0.5 * d0 + 2.0


def merge_duals(mouths: list[Mouth], law: Law, stats
                 ) -> list[tuple[list[Mouth], XY, XY, float, list[XY]]]:
    """Cluster mouths of DIFFERENT bores that stand within the dual
    separation with parallel approaches (31h — transitively, so a 2+2
    with service lanes is ONE ramp): returns ``(members, mouth_xy,
    inward, full_width, axis_path)`` per ramp.  The mouth line stands at
    the OUTER of the mapped ends (a mapped bore is never cut open, 08-07
    ruling 2); the width spans every carriageway."""
    sep_max = law.tables.structures.tunnel.dual_carriageway_max_separation_m
    n = len(mouths)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _parallel(mouths[i], mouths[j], sep_max):
                parent[find(i)] = find(j)
    groups: dict[int, list[Mouth]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(mouths[i])
    out = []
    for members in groups.values():
        if len(members) == 1:
            a = members[0]
            out.append(([a], a.xy, a.inward, a.width_m, list(a.approach)))
            continue
        stats.duals_merged += 1
        sx = sum(m.inward[0] for m in members)
        sy = sum(m.inward[1] for m in members)
        inward = unit((0.0, 0.0), (sx, sy))
        nx, ny = -inward[1], inward[0]
        # along: outward is -inward; the mouth line at the outermost end
        along = [-(m.xy[0] * inward[0] + m.xy[1] * inward[1]) for m in members]
        s_out = max(along)
        lat = [m.xy[0] * nx + m.xy[1] * ny for m in members]
        lo = min(l - m.width_m / 2 for l, m in zip(lat, members))
        hi = max(l + m.width_m / 2 for l, m in zip(lat, members))
        centre_lat = (lo + hi) / 2
        width = hi - lo
        # the axis: the mean of the approaches, re-based on the centre line
        length = max(LineString(m.approach).length for m in members)
        ss = [5.0 * k for k in range(int(length // 5.0) + 2)]
        rs = [resample(m.approach, ss) for m in members]
        axis = [(sum(r[k][0] for r in rs) / len(rs), sum(r[k][1] for r in rs) / len(rs))
                for k in range(len(ss))]
        a0 = axis[0]
        along0 = -(a0[0] * inward[0] + a0[1] * inward[1])
        lat0 = a0[0] * nx + a0[1] * ny
        dx = (centre_lat - lat0) * nx - (s_out - along0) * inward[0]
        dy = (centre_lat - lat0) * ny - (s_out - along0) * inward[1]
        axis = [(p[0] + dx, p[1] + dy) for p in axis]
        out.append((members, axis[0], inward, width, axis))
    return out


@_dc.dataclass(frozen=True)
class PavementDeck:
    """A pavement cell read as a deck over an object corridor (RULINGS
    2026-09-06f): ``id`` its cell ref (the deck's ref is
    ``bridge_deck:<id>``), ``role`` the cell's own role (the deck piece
    keeps it — the taxiway law governs its surface), ``index`` its cell."""

    id: str
    role: str
    index: int


def pavement_deck_intervals(axis_ln: LineString, half_outer: float, s_end: float,
                             cells: list[Cell], polys: list[Polygon], tree: STRtree | None,
                             law: Law, grid: float
                             ) -> list[tuple[PavementDeck, float, float, Polygon]]:
    """``(deck, s0, s1, cell polygon)`` per pavement cell of a
    ``bridge.pavement_deck_families`` role family that SPANS the corridor
    within ``s_end`` (an object corridor's walls): its polygon crosses
    the axis, the corridor strip continues on both sides of it (the cell
    cuts the strip in two) and neither edge stands at the corridor's
    ends — a cell holding the mouth is what the ramp cuts, not a deck.
    Ordered by ``s0``."""
    if tree is None:
        return []
    fams = set(law.tables.structures.bridge.pavement_deck_families)
    corridor = axis_ln.buffer(half_outer, cap_style="flat", **_MITRE)
    out = []
    for j in tree.query(corridor, predicate="intersects"):
        c, p = cells[int(j)], polys[int(j)]
        if c.kind == "structure" or role_family(law, c.role) not in fams:
            continue
        seg = axis_ln.intersection(p)
        if seg.is_empty:
            continue
        s_vals = [axis_ln.project(Point(q)) for g in shapely.get_parts(seg) for q in g.coords]
        s0, s1 = min(s_vals), max(s_vals)
        if s0 <= grid or s1 >= min(s_end, axis_ln.length) - grid:
            continue
        rest = corridor.difference(p)
        if len(_parts(rest)) < 2:
            continue
        out.append((PavementDeck(c.ref, c.role, int(j)), s0, s1, p))
    out.sort(key=lambda t: t[1])
    return out


#: A deck crossing the axis at less than this angle is along it, not over it.
_DECK_MIN_ANGLE_DEG = 30.0


def deck_intervals(axis_ln: LineString, half_outer: float, bridges: list[OsmWay],
                    lines: list[LineString], tree: STRtree | None, law: Law
                    ) -> list[tuple[OsmWay, float, float, Polygon]]:
    """``(way, s0, s1, deck polygon)`` per mapped bridge way crossing the
    corridor (at ≥ 30° to the axis), ordered by ``s0``."""
    if tree is None:
        return []
    corridor = axis_ln.buffer(half_outer, cap_style="flat", **_MITRE)
    out = []
    for j in tree.query(corridor, predicate="intersects"):
        w, ln = bridges[int(j)], lines[int(j)]
        x = ln.intersection(axis_ln)
        if x.is_empty:
            continue
        pts = [g for g in shapely.get_parts(x) if g.geom_type == "Point"]
        if not pts:
            continue
        s_mid = axis_ln.project(pts[0])
        # crossing angle
        a = axis_ln.interpolate(max(0.0, s_mid - 1.0))
        b = axis_ln.interpolate(min(axis_ln.length, s_mid + 1.0))
        ux, uy = b.x - a.x, b.y - a.y
        sb = ln.project(pts[0])
        c = ln.interpolate(max(0.0, sb - 1.0))
        d = ln.interpolate(min(ln.length, sb + 1.0))
        vx, vy = d.x - c.x, d.y - c.y
        den = (math.hypot(ux, uy) * math.hypot(vx, vy)) or 1.0
        ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(ux * vx + uy * vy) / den))))
        if ang < _DECK_MIN_ANGLE_DEG:
            continue
        wd = carriageway_width_m(w.tags, law)
        dpoly = ln.intersection(corridor.buffer(2.0)).buffer(wd / 2, cap_style="flat", **_MITRE)
        if dpoly.is_empty:
            continue
        # the covered stretch along the axis
        seg = axis_ln.intersection(dpoly)
        if seg.is_empty:
            continue
        s_vals = []
        for g in shapely.get_parts(seg):
            for q in g.coords:
                s_vals.append(axis_ln.project(Point(q)))
        out.append((w, min(s_vals), max(s_vals), dpoly))
    out.sort(key=lambda t: t[1])
    return out


def object_deck_intervals(axis_ln: LineString, half_outer: float,
                           odecks: list[tuple[str, Polygon, float]]
                           ) -> list[tuple[str, float, float, Polygon, float]]:
    """``(object id, s0, s1, deck footprint, deck top)`` per hard-deck
    object footprint crossing the corridor, ordered by ``s0``."""
    if not odecks:
        return []
    corridor = axis_ln.buffer(half_outer, cap_style="flat", **_MITRE)
    out = []
    for oid, dp, top in odecks:
        if not dp.intersects(corridor):
            continue
        seg = axis_ln.intersection(dp)
        if seg.is_empty:
            continue
        s_vals = [axis_ln.project(Point(q)) for g in shapely.get_parts(seg) for q in g.coords]
        if not s_vals:
            continue
        out.append((oid, min(s_vals), max(s_vals), dp, top))
    out.sort(key=lambda t: t[1])
    return out


# ── the ramp's top (moved VERBATIM from planar/structures.py, lane
#    v2wallplate: that file stands at its 1,000-line budget and §33 grows
#    it; no behaviour moved with it) ─────────────────────────────────────
def ramp_top(airport: Airport, law: Law, axis_fn, mouth_z: float, climb_from: float,
              spacing: float, s_min: float = 0.0, grade: float | None = None,
              max_len: float | None = None) -> tuple[float | None, list[float]]:
    """``(s_top, station s values)`` — the first station at or beyond
    ``s_min`` where the ``ramp_max_grade`` climb from ``mouth_z``
    (starting at ``climb_from``) reaches the DEM ALONG THE ROUTE, plus
    one station of slack; ``None`` when the DEM is not reached within
    ``max_ramp_length_m``.

    A RAMP IS PRICED ALONG ITS ROUTE (spec §34 (1); Fable 2026-09-13i,
    RULINGS 2026-09-13i item 7a).  The reach is the AXIS LENGTH WALKED
    — ``s − climb_from`` — never the straight chord from the mouth
    line.  The retired chord term (``chord × grade ≥ rise``, an
    allowance for the within-shape law pricing ring pairs over the
    chord) made a ramp whose DEM condition was met at 271 m of route
    run 420 m of axis whenever the mapped road curved: 12 of LEMD's 59
    ramps carried axis/chord > 1.3, the worst 3.85, and −15327's ramp
    overran its road by 156 m.  A curved road is still a road; the
    grade a driver feels is the one along it.

    ``s_min`` is an object corridor's wall length: INSIDE the walls the
    DEM is not the ground (2026-09-06f: LEMD's Bridge4 stands in a
    cutting the SPAIN5M DEM carries, its axis sample 8 m under the
    walls' ground) — the ramp there is the design.  ``grade`` /
    ``max_len`` are a group's own law (a door ramp: 09-08b/c
    ``cutout.door``), else the tunnel's."""
    tn = law.tables.structures.tunnel
    g = tn.ramp_max_grade if grade is None else grade
    bound = tn.max_ramp_length_m if max_len is None else max_len
    ss = [0.0]
    s = 0.0
    while s < bound:
        s += spacing
        ss.append(s)
        if s <= climb_from or s < s_min - 1e-9:
            continue
        # the ramp meets the DEM where the DEM enters the ±ramp_max_grade
        # CONE from the datum, measured along the route: rising ground is
        # climbed, ground that has fallen below the bore floor (a mouth on
        # a ridge of the smoothed DEM — measured LEMD -15327+-5980: the
        # DEM 8.4 m under the datum 24 m out) is descended to, never
        # stepped down to
        reach = g * (s - climb_from)
        d = _dem(airport, axis_fn(s))
        if math.isnan(d):
            return None, ss
        if abs(d - mouth_z) <= reach:
            ss.append(s + spacing)
            return s + spacing, ss
    return None, ss


# ── §33 (3)/(4): the approach's ground, and a terrain deck's two ends ──
def deck_ends(airport: Airport, w, cells, polys, cell_tree, law: Law | None = None
              ) -> tuple[tuple[float, ...], tuple[str, ...], tuple[XY, ...]]:
    """THE GROUND AT A TERRAIN DECK'S TWO ENDS (spec §33 (4); owner
    RULINGS 2026-09-13d item 9 "it needs to smoothly connect the road on
    either end ... the apron on the east end and the road on the west
    side").  Per mapped end: the DEM there, and the governed cell standing
    at it (``""`` where the end is bare ground) — the constraint generator
    reads that cell's own solved value where it has one, so the deck meets
    the APRON, not the DEM under it.  Measured LEMD way -6288: ends 609.99
    and 606.10 against a trench floor + clearance of 604.12."""
    zs: list[float] = []
    refs: list[str] = []
    pts: list[XY] = [tuple(w.points[0]), tuple(w.points[-1])]
    reach = float(law.tables.structures.bridge.deck_end_reach_m) if law is not None else 0.0
    for e in (w.points[0], w.points[-1]):
        z = _dem(airport, e)
        zs.append(float(z) if not math.isnan(z) else float("nan"))
        ref = ""
        if cell_tree is not None:
            pt = Point(e)
            for j in cell_tree.query(pt, predicate="intersects"):
                c = cells[int(j)]
                if c.kind != "structure" and polys[int(j)].contains(pt):
                    ref = c.ref
                    break
            if not ref and reach > 0.0:
                # THE END'S GROUND IS READ ALONG THE ROAD (spec §34 (6);
                # RULINGS 2026-09-13r, owed to lane v2rampwalk): the mapped
                # way STOPS at the surface it runs onto — OSM does not trace
                # a service road across an apron — so the governed cell the
                # end meets stands a few metres beyond the last node, not
                # under it.  Measured LEMD way -6288: its east end reads the
                # DEM 606.10 with no cell under it while the apron pav92
                # (solved 606.60) starts 13.3 m away, and the deck was tied
                # to neither.  The nearest governed cell within
                # ``bridge.deck_end_reach_m`` IS that end's ground; the
                # constraint generator then takes its own SOLVED value
                # (§33 (4)), never the DEM under it.
                best = None
                for j in cell_tree.query(pt.buffer(reach), predicate="intersects"):
                    c = cells[int(j)]
                    if c.kind == "structure":
                        continue
                    d = polys[int(j)].distance(pt)
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, c.ref)
                if best is not None:
                    ref = best[1]
        refs.append(ref)
    return tuple(zs), tuple(refs), tuple(pts)


def approach_ground(airport: Airport, axis_fn, band_m: float, spacing: float) -> float:
    """THE APPROACH'S GROUND (spec §33 (3)): the MEDIAN DEM along the
    approach's first stations beyond the mouth's own band — the stations
    at ``spacing`` from ``band_m`` out to four times it, which is the
    road the ramp has to meet.  ``nan`` when the DEM carries none of
    them."""
    zs = []
    s = band_m
    while s <= 4.0 * band_m + 1e-9:
        z = _dem(airport, axis_fn(s))
        if not math.isnan(z):
            zs.append(z)
        s += max(spacing, 1.0)
    if not zs:
        return float("nan")
    zs.sort()
    return zs[len(zs) // 2]


# ── the thin-plate wall objects govern the mouth (spec §33 (2)) ──────────

def apply_plates(mouth_list: list[Mouth], plates: _t.Sequence, osm: list[OsmWay],
                 law: Law, reach_m: float) -> tuple[list[Mouth], list[str]]:
    """THE PACK'S WALL OBJECTS GOVERN THE MOUTH (spec §33 (2); owner
    RULINGS 2026-09-13d item 5; Fable 2026-09-13i).  A mouth standing
    INSIDE a thin-plate wall object that spans its bore is the OBJECT's
    (``tunnel.object.source_precedence = ["object", "osm"]``, per mouth as
    05n-3 already applies it): it MOVES to the plate's own end — the plan
    rectangle's short-side midpoint, so the corridor's axis is the
    object's centre — takes the plate's WIDTH, and keeps the mapped road
    beyond as its approach (the leading stretch that ran under the plate
    is dropped; the mouth is the portal, and the bore behind it emits
    nothing, §29).

    Measured LEMD: ``Bridge3.obj`` is 354.2 x 25.1 m and covers all
    223.7 m of bore ``-5931``; its mouths were built 7.0 m wide
    (``lanes x lane_width_m``), 1.08 m off the object's centre and 83 m
    INSIDE its north end.  Returns the mouths and one report line per
    mouth moved."""
    if not plates or not mouth_list:
        return mouth_list, []
    admitted = law.tables.structures.tunnel.admitted_values
    out: list[Mouth] = []
    notes: list[str] = []
    for m in mouth_list:
        p = _plate_for(m, plates)
        if p is None:
            out.append(m)
            continue
        # the plate END this mouth belongs to, and the direction INTO the plate
        ax = LineString(p.ends)
        k = 0 if ax.project(Point(m.xy)) < ax.length / 2.0 else 1
        end, far = p.ends[k], p.ends[1 - k]
        inward = unit(end, far)
        path = _approach_beyond(end, inward, m.approach, p.plan, osm, law, reach_m, admitted)
        moved = math.hypot(end[0] - m.xy[0], end[1] - m.xy[1])
        notes.append(f"mouth of bore {'+'.join(str(i) for i in m.ways)} taken by {p.id} "
                     f"(§33 (2)): moved {moved:.1f} m to the object's end, width "
                     f"{m.width_m:.1f} -> {p.width_m:.1f} m")
        out.append(Mouth(m.bore, end, inward, p.width_m, path, m.ways))
    return out, notes


def _plate_for(m: Mouth, plates: _t.Sequence):
    """The thin plate that governs this mouth: it spans one of the bore's
    own ways and holds the mapped end inside its plan."""
    pt = Point(m.xy)
    for p in plates:
        if not p.bore_ways or not p.plan.contains(pt):
            continue
        if any(wid in m.ways for wid, _L in p.bore_ways):
            return p
    return None


def _approach_beyond(end: XY, inward: XY, path: _t.Sequence[XY], plan: Polygon,
                     osm: list[OsmWay], law: Law, reach_m: float, admitted) -> list[XY]:
    """The approach from the plate's END outward: the mapped approach the
    OSM mouth already walked, with the stretch that runs UNDER the plate
    dropped and the plate's end midpoint prepended, so the ramp follows
    the real road rather than a straight extension (a plate's end stands
    off the mapped node, so ``approach`` alone would find no way there)."""
    keep: list[XY] = []
    if len(path) >= 2:
        rest = LineString(path).difference(plan)
        parts = [g for g in shapely.get_parts(rest) if g.geom_type == "LineString"]
        if parts:
            # the piece that starts nearest the plate's end, in path order
            best = min(parts, key=lambda g: Point(end).distance(g))
            if Point(end).distance(best) <= reach_m:
                cs = list(best.coords)
                if math.hypot(cs[0][0] - path[0][0], cs[0][1] - path[0][1]) \
                        > math.hypot(cs[-1][0] - path[0][0], cs[-1][1] - path[0][1]):
                    cs.reverse()
                keep = [q for q in cs
                        if math.hypot(q[0] - end[0], q[1] - end[1]) > NODE_TOL]
    if not keep:
        return approach(end, inward, osm, reach_m, admitted,
                        law.tables.structures.tunnel.approach_turn_max_deg)
    out = [end] + keep
    ln = LineString(out)
    if ln.length < reach_m:
        a = unit(out[-2], out[-1])
        out.append((out[-1][0] + a[0] * (reach_m - ln.length + 1.0),
                    out[-1][1] + a[1] * (reach_m - ln.length + 1.0)))
    return out
