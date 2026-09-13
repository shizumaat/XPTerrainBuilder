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
from ..law.approach_corridor import ApproachCorridor
from ..law.tables import role_family
from ..model.airport import OsmWay
from ..model.frame import XY
from ..airport.deck_signature import (DEFAULT_TUNNEL_VALUES, is_bridge_way,
                                      is_tunnel_way)
from ..classify.roles import Cell

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]

__all__ = ["PavementDeck", "pavement_deck_intervals", "deck_intervals", "object_deck_intervals", "carriageway_width_m", "pavement_half_widths", "Bore", "Mouth", "chains", "approach",
           "resample",
           "mouths", "FieldRegion", "ApproachCorridor", "approach_corridor_of", "field_region_for", "mouth_reports", "under_cover", "merge_duals", "unit", "is_tunnel", "is_bridge", "MAX_HOPS",
           "PARALLEL_COS", "NODE_TOL"]

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
             admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES) -> list[XY]:
    """The centreline OUTWARD from the mouth: non-tunnel ways joined at
    the mouth node, followed up to ``reach_m``; a straight extension of
    the bore's own end direction where no way continues."""
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
    for _hop in range(MAX_HOPS):
        best = None
        for i, forward in idx.get(_key(cur), ()):
            if i in seen:
                continue
            pts = list(ways[i].points) if forward else list(reversed(ways[i].points))
            # outward: the way must leave the mouth AWAY from the bore
            dx, dy = pts[min(1, len(pts) - 1)][0] - cur[0], pts[min(1, len(pts) - 1)][1] - cur[1]
            if dx * inward[0] + dy * inward[1] > 0.0 and len(path) == 1:
                continue
            best = (i, pts)
            break
        if best is None:
            break
        i, pts = best
        seen.add(i)
        for p in pts[1:]:
            length += math.hypot(p[0] - cur[0], p[1] - cur[1])
            path.append(p)
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
    the approach corridor of §31 (2)."""
    return FieldRegion(list(polys),
                       law.tables.structures.tunnel.mouth_standoff_m,
                       approach_corridor_of(airport, law))


def mouth_reports(on_field: "FieldRegion", mouth_list: _t.Sequence["Mouth"],
                  dropped: _t.Sequence[tuple]) -> tuple[list[str], int, list[str]]:
    """``(off-field lines, on-approach count, on-approach lines)`` for the
    structures line — the nearest drops and every mouth THE CORRIDOR
    kept, each with its true distance off the field, so both findings are
    visible without a rebuild and neither is read as the other."""
    off = [f"mouth off-field {ids} at {xy[0]:.0f},{xy[1]:.0f} — {d:.0f} m off "
           f"the field and outside every approach corridor"
           for ids, xy, d in sorted(dropped, key=lambda t: t[2])[:8]]
    on_approach = [m for m in mouth_list if not on_field.on_cover(Point(m.xy))]
    named = [f"mouth on approach {'+'.join(str(i) for i in m.ways)} at "
             f"{m.xy[0]:.0f},{m.xy[1]:.0f} — "
             f"{on_field.cover_distance_m(Point(m.xy)):.0f} m off the field, "
             f"in view"
             for m in on_approach[:12]]
    return off, len(on_approach), named


def approach_corridor_of(airport, law: Law) -> ApproachCorridor:
    """THE APPROACH CORRIDOR of §31 (2) for one airport, from the model's
    OWN runway ends (apt.dat row 100 thresholds) and the two ``[cockpit]``
    numbers — never a second idea of either.

    The harness reaches the same class from the emitted patch (the
    principal axis of each runway's ring cloud): one derivation, two
    sources for the axis it is derived FROM, which is why
    ``tests/auto_patch_v2/test_v2approachcorridor.py`` pins them against
    one fixture."""
    ck = law.tables.emit.cockpit
    axes = [(r.ends[0].xy, r.ends[1].xy, r.id)
            for r in getattr(airport, "runways", ()) or ()]
    return ApproachCorridor(axes, float(ck.approach_km) * 1000.0,
                            float(ck.approach_half_width_m))


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
                 corridor=None) -> None:
        self.standoff_m = float(standoff_m)
        self._tree = STRtree(list(polys)) if len(polys) else None
        self.corridor = corridor
        rings = list(corridor.rings()) if corridor is not None else []
        self._corridor_tree = (STRtree([Polygon(r) for r in rings])
                               if rings else None)

    def holds(self, geom) -> bool:
        """``geom`` (a mouth point or its ramp reach) stands where a pilot
        would see it: on the field, or in an approach corridor."""
        return self.on_cover(geom) or self.in_corridor(geom)

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
        if self._corridor_tree is not None:
            j = self._corridor_tree.nearest(geom)
            if j is not None:
                d = min(d, float(
                    self._corridor_tree.geometries[int(j)].distance(geom)))
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
        for end, nxt in ((b.points[0], b.points[1]), (b.points[-1], b.points[-2])):
            inward = unit(end, nxt)
            path = approach(end, inward, osm, reach_m,
                            law.tables.structures.tunnel.admitted_values)
            if on_field is not None:
                pt = Point(end)
                reach = LineString(path) if len(path) >= 2 else pt
                if not (on_field.holds(pt) or on_field.holds(reach)):
                    dropped.append(("+".join(str(i) for i in wids), end,
                                    min(on_field.distance_m(pt),
                                        on_field.distance_m(reach))))
                    continue
            out.append(Mouth(b, end, inward, width, path, wids))
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
