"""STRUCTURE GEOMETRY (M4): tunnel corridors from the OSM bore + approach
ways, road bridge decks, and how they enter the planar map — as CELLS
that CUT the pavement they run through, plus the records
(``model.structures``) the generator and the verifier read.

THE MODEL (RULINGS 2026-08-07 portal fidelity; 2026-08-30 canonical
mouth; 2026-08-31h dual carriageways; 2026-09-01c/e gap; 2026-09-03b
crest = DEM; law ``structures.toml [tunnel]``):

* a BORE is a chain of mapped ``tunnel=yes`` ways; it is generated only
  where it passes UNDER an airport surface (a classified cell) — a bore
  that touches no cell drapes the DEM like any road v2 does not emit;
* the MOUTH is the mapped end of the bore (08-07 ruling 1: "mapped ends
  are preserved unconditionally"); the bore itself is never emitted —
  the covering surface keeps its own law (08-07 ruling 2: mapped-bore
  interiors are roofed by definition);
* the RAMP descends the approach corridor to the mouth line: its axis
  follows the approach ways outward from the mouth, its width is the
  carriageway's (``width`` tag, else ``lanes × lane_width_m``); two
  bores whose mouths stand within ``dual_carriageway_max_separation_m``
  with parallel approaches are ONE ramp spanning both (31h); the ramp
  ends where a ``ramp_max_grade`` climb from the mouth datum meets the
  DEM (the top edge is DEM);
* ``wall_gap_m`` of UNOWNED ground round the ramp (three sides), then
  the WALL BAND (``wall_band_width_m``) on both sides and an END CAP
  across the mouth — one U-shaped face whose crest is the DEM;
* the structure CUTS every pavement it runs through (08-07 ruling 4)
  except the runway family and building pads (``ramp_cuts_runway_family
  = false``, ``ramp_crosses_pad = false``): a ramp that would need to
  cross either before reaching the DEM is REFUSED loudly, never bent;
  a wall inside the runway strip keep-out is refused likewise
  (``retaining_wall.in_runway_strip = false``);
* a mapped ``bridge=*`` way crossing the corridor is a TERRAIN DECK
  (08-30d: no object ⇒ terrain deck at road level): a road face across
  the corridor that severs the ramp and the walls; the cut stays at bore
  datum from the mouth to the deck and the climb begins beyond it
  (08-30f); the deck's ground is road (08-30m);
* a HARD-DECK OBJECT (``ATTR_hard_deck``, read by ``airport/obj8.py``)
  whose footprint crosses the corridor is an OBJECT BRIDGE (M4b; 08-30d
  "where a classified hard-deck OBJECT bridge exists the object law
  governs and the terrain stays open"): the ramp is NOT severed — the
  cut continues under the deck at bore datum and the climb begins
  beyond it (08-30f's depth clause) — and the deck's TOP (memory
  othh-bridge-deck-datum-r12) must clear the ramp by
  ``bridge.clearance_m`` (a bound the generator states, the IIS reports);
  a mapped bridge way over an object deck mints no terrain deck.

Every length here is a law-table value or an input's own tag; the DEM
samples recorded on the records are the builder's, taken once.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..classify.roles import Cell, Classification
from ..law import Law
from ..law.tables import role_side, zone2_half_width_m
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..airport.deck_signature import is_bridge_way
from ..model.structures import Deck, Tunnel
from .basins import object_decks

__all__ = ["StructureStats", "build_structures", "carriageway_width_m"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
RUNWAY_FAMILY = ("runway", "runway_crossing")
#: Two OSM node coordinates closer than this (frame metres) are one node.
_NODE_TOL = 0.05
#: Approach ways are followed at most this many hops from the mouth.
_MAX_HOPS = 6
#: A deck crossing the axis at less than this angle is along it, not over it.
_DECK_MIN_ANGLE_DEG = 30.0


@_dc.dataclass
class StructureStats:
    """What the structure pass found, made and refused."""

    bores: int = 0
    bores_uncovered: int = 0
    mouths: int = 0
    duals_merged: int = 0
    tunnels: int = 0
    decks: int = 0
    object_decks: int = 0
    promoted_candidates: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    cells_cut: int = 0


# ── tags ─────────────────────────────────────────────────────────────────

def _is_tunnel(w: OsmWay) -> bool:
    t = w.tags.get("tunnel")
    return bool(t) and t != "no" and ("highway" in w.tags or "railway" in w.tags)


def _is_bridge(w: OsmWay) -> bool:
    """One predicate with the deck signature's (``airport/deck_signature``)."""
    return is_bridge_way(w.tags)


def candidate_decks(objects: _t.Sequence) -> list[tuple[str, Polygon, float]]:
    """``(object id, plate footprint, rendered deck top)`` per CANDIDATE
    plate (a deck-shaped plate with no spanning evidence at read time,
    04k): one that crosses a tunnel corridor spans the ramp — THAT is
    its evidence, and it enters the map as an object deck."""
    out = []
    for o in objects:
        pl = getattr(o, "deck_plate", None)
        if getattr(o, "deck_kind", "") != "candidate" or pl is None:
            continue
        for part in shapely.get_parts(pl.footprint):
            if part.geom_type == "Polygon" and part.area > 1.0:
                out.append((o.id, part, float(o.anchor_z + o.agl_m + pl.deck_top_y)))
    return out


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


# ── bores (chains of tunnel ways) ────────────────────────────────────────

def _key(p: XY) -> tuple[int, int]:
    return (int(round(p[0] / _NODE_TOL)), int(round(p[1] / _NODE_TOL)))


@_dc.dataclass
class _Bore:
    ways: list[OsmWay]
    points: list[XY]          # the chain, in order

    @property
    def line(self) -> LineString:
        return LineString(self.points)


def _chains(ways: list[OsmWay]) -> list[_Bore]:
    """Join tunnel ways end to end where exactly two of them meet."""
    ends: dict[tuple[int, int], list[int]] = {}
    for i, w in enumerate(ways):
        ends.setdefault(_key(w.points[0]), []).append(i)
        ends.setdefault(_key(w.points[-1]), []).append(i)
    used = [False] * len(ways)
    out: list[_Bore] = []
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
        out.append(_Bore(members, pts))
    return out


# ── the approach ─────────────────────────────────────────────────────────

def _approach(mouth: XY, inward: XY, ways: list[OsmWay], reach_m: float
              ) -> list[XY]:
    """The centreline OUTWARD from the mouth: non-tunnel ways joined at
    the mouth node, followed up to ``reach_m``; a straight extension of
    the bore's own end direction where no way continues."""
    idx: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, w in enumerate(ways):
        if _is_tunnel(w) or ("highway" not in w.tags and "railway" not in w.tags):
            continue
        idx.setdefault(_key(w.points[0]), []).append((i, True))
        idx.setdefault(_key(w.points[-1]), []).append((i, False))
    path: list[XY] = [mouth]
    cur = mouth
    length = 0.0
    seen: set[int] = set()
    for _hop in range(_MAX_HOPS):
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


def _resample(path: _t.Sequence[XY], ss: _t.Sequence[float]) -> list[XY]:
    ln = LineString(path)
    out = []
    for s in ss:
        p = ln.interpolate(min(s, ln.length))
        out.append((p.x, p.y))
    return out


# ── the mouths ───────────────────────────────────────────────────────────

@_dc.dataclass
class _Mouth:
    bore: _Bore
    xy: XY
    inward: XY               # unit vector INTO the bore
    width_m: float
    approach: list[XY]
    ways: tuple[int, ...]


def _unit(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _mouths(bores: list[_Bore], osm: list[OsmWay], law: Law, reach_m: float
            ) -> list[_Mouth]:
    out: list[_Mouth] = []
    for b in bores:
        width = max(carriageway_width_m(w.tags, law) for w in b.ways)
        wids = tuple(w.id for w in b.ways)
        for end, nxt in ((b.points[0], b.points[1]), (b.points[-1], b.points[-2])):
            inward = _unit(end, nxt)
            out.append(_Mouth(b, end, inward, width,
                              _approach(end, inward, osm, reach_m), wids))
    return out


def _parallel(a: _Mouth, b: _Mouth, sep_max: float) -> bool:
    """31h's test: mouths within the dual separation, approaches parallel
    and holding that separation 50 m out."""
    if b.bore is a.bore:
        return False
    d0 = math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1])
    if d0 > sep_max:
        return False
    if a.inward[0] * b.inward[0] + a.inward[1] * b.inward[1] < math.cos(math.radians(30)):
        return False
    pa, pb = _resample(a.approach, [50.0])[0], _resample(b.approach, [50.0])[0]
    d1 = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    return abs(d1 - d0) <= 0.5 * d0 + 2.0


def _merge_duals(mouths: list[_Mouth], law: Law, stats: StructureStats
                 ) -> list[tuple[list[_Mouth], XY, XY, float, list[XY]]]:
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
    groups: dict[int, list[_Mouth]] = {}
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
        inward = _unit((0.0, 0.0), (sx, sy))
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
        rs = [_resample(m.approach, ss) for m in members]
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


# ── the ramp geometry ────────────────────────────────────────────────────

def _normals(axis: _t.Sequence[XY]) -> list[XY]:
    """Left-hand unit normal per axis point (averaged at joints)."""
    n = len(axis)
    out: list[XY] = []
    for i in range(n):
        a = axis[max(0, i - 1)]
        b = axis[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((-dy / L, dx / L))
    return out


def _offset_line(axis: _t.Sequence[XY], normals: _t.Sequence[XY], off: float) -> list[XY]:
    return [(p[0] + nv[0] * off, p[1] + nv[1] * off) for p, nv in zip(axis, normals)]


def _snap(p: XY, grid: float) -> XY:
    """The nearest identity-grid point."""
    return (round(p[0] / grid) * grid, round(p[1] / grid) * grid)


def _snap_out(p: XY, origin: XY, grid: float) -> XY:
    """``p`` snapped to the identity grid AWAY from ``origin`` on both
    axes, so a designed stand-off (the 0.6 m gap, 09-01e "never ON a
    weld tolerance") survives the arrangement's snap-rounding: two
    points 0.85 m apart both round to ONE 0.5 m grid point (measured
    OTHH: the ramp's mouth corner and the cap's inner corner merged into
    vertex 14058 — an IIS of its two pins)."""
    out = []
    for c, o in zip(p, origin):
        k = c / grid
        if c > o + 1e-9:
            out.append(math.ceil(k - 1e-9) * grid)
        elif c < o - 1e-9:
            out.append(math.floor(k + 1e-9) * grid)
        else:
            out.append(round(k) * grid)
    return (out[0], out[1])


def _offset_out(axis: _t.Sequence[XY], normals: _t.Sequence[XY], off: float,
                base: _t.Sequence[XY], grid: float) -> list[XY]:
    """``axis`` offset by ``off`` along ``normals``, each point snapped
    away from its ``base`` point."""
    return [_snap_out((p[0] + nv[0] * off, p[1] + nv[1] * off), b, grid)
            for p, nv, b in zip(axis, normals, base)]


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _ramp_top(airport: Airport, law: Law, axis_fn, mouth_z: float, climb_from: float,
              spacing: float, half: float) -> tuple[float | None, list[float]]:
    """``(s_top, station s values)`` — the first station where the
    ``ramp_max_grade`` climb from ``mouth_z`` (starting at ``climb_from``)
    is at or above the DEM AND the DIRECT distance from the mouth line
    reaches the climb at the cap (the within-shape law prices ring pairs
    over the chord, so a curved corridor needs more axis than a straight
    one), plus one station of slack; ``None`` when the DEM is not reached
    within ``max_ramp_length_m``."""
    tn = law.tables.structures.tunnel
    ss = [0.0]
    s = 0.0
    m = axis_fn(climb_from)          # the chord is measured from where the climb starts
    while s < tn.max_ramp_length_m:
        s += spacing
        ss.append(s)
        if s <= climb_from:
            continue
        # the ramp meets the DEM where the DEM enters the ±ramp_max_grade
        # CONE from the datum: rising ground is climbed, ground that has
        # fallen below the bore floor (a mouth on a ridge of the smoothed
        # DEM — measured LEMD -15327+-5980: the DEM 8.4 m under the datum
        # 24 m out) is descended to, never stepped down to
        reach = tn.ramp_max_grade * (s - climb_from)
        p = axis_fn(s)
        d = _dem(airport, p)
        if math.isnan(d):
            return None, ss
        chord = math.hypot(p[0] - m[0], p[1] - m[1]) - 2.0 * half
        if abs(d - mouth_z) <= reach and chord * tn.ramp_max_grade >= abs(d - mouth_z):
            ss.append(s + spacing)
            return s + spacing, ss
    return None, ss


def _u_polygon(left_in, left_out, right_in, right_out, cap_in, cap_out) -> Polygon:
    """The wall band as ONE U: outer-left top→mouth, outer cap (left,
    centre, right), outer-right mouth→top, top of the right band, inner-
    right top→mouth, inner cap, inner-left mouth→top, top of the left
    band (closes)."""
    ring = (list(reversed(left_out)) + list(cap_out) + list(right_out)
            + list(reversed(right_in)) + list(reversed(cap_in)) + list(left_in))
    return Polygon(ring)


# ── build ────────────────────────────────────────────────────────────────

def build_structures(airport: Airport, classification: Classification, law: Law,
                     objects: _t.Sequence = ()
                     ) -> tuple[Classification, tuple[Tunnel, ...], StructureStats]:
    """The classification with the structures applied (cells cut, ramp /
    wall / deck cells added, the gaps as keep-outs), the tunnel records,
    and the stats.  ``objects`` are the pack's placed OBJ8 readings
    (``planar.basins.read_objects``): their hard decks are object
    bridges.  A classification with no bores comes back unchanged."""
    stats = StructureStats()
    odecks = object_decks(objects)
    cdecks = candidate_decks(objects)
    tn = law.tables.structures.tunnel
    tunnel_ways = [w for w in airport.osm_ways if _is_tunnel(w) and len(w.points) >= 2]
    if not tunnel_ways or not classification.cells:
        return classification, (), stats
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    cover = unary_union(polys)
    bores = _chains(tunnel_ways)
    stats.bores = len(bores)
    covered = []
    for b in bores:
        if b.line.intersection(cover).length >= 1.0:
            covered.append(b)
        else:
            stats.bores_uncovered += 1
    if not covered:
        return classification, (), stats
    reach = tn.max_ramp_length_m + 2 * (tn.wall_gap_m + tn.wall_band_width_m)
    mouths = _mouths(covered, list(airport.osm_ways), law, reach)
    stats.mouths = len(mouths)
    groups = _merge_duals(mouths, law, stats)

    # what a ramp may not cross
    runway_u = unary_union([p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    pads = [(p, c.ref) for p, c in zip(polys, cells) if c.role == "building"]
    pad_tree = STRtree([p for p, _r in pads]) if pads else None
    strip: list[Polygon] = []
    for p, c in zip(polys, cells):
        if c.role in RUNWAY_FAMILY:
            hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter)
            if hw:
                strip.append(p.buffer(hw, **_MITRE))
    strip_u = unary_union(strip) if strip else None
    bridges = [w for w in airport.osm_ways if _is_bridge(w) and len(w.points) >= 2]
    bridge_lines = [LineString(w.points) for w in bridges]
    bridge_tree = STRtree(bridge_lines) if bridge_lines else None

    spacing = law.tables.emit.chords.station_spacing_m
    gap, bw = tn.wall_gap_m, tn.wall_band_width_m
    grid = law.tables.emit.identity.min_distinct_spacing_m
    tunnels: list[Tunnel] = []
    new_cells: list[tuple[str, str, Polygon, str]] = []
    footprints: list[Polygon] = []
    keepouts: list[Polygon] = []
    seen_ids: dict[str, int] = {}
    for members, mouth, inward, width, axis_path in groups:
        base = "+".join(str(i) for m in members for i in m.ways)
        seen_ids[base] = seen_ids.get(base, -1) + 1
        tid = f"tunnel:{base}@{seen_ids[base]}"
        half = width / 2.0
        axis_ln = LineString(axis_path)

        def axis_fn(s: float, _ln=axis_ln) -> XY:
            p = _ln.interpolate(min(s, _ln.length))
            return (p.x, p.y)

        # THE MOUTH DATUM is the MOUTH WALL NODE's DEM − bore_datum_m
        # (09-03b): the end cap's centre, gap + half the band in front of
        # the mouth line — not the axis point's sample (measured LEMD
        # -15327+-5980: a cutting whose cap stands 2 m above the axis
        # sample; the ramp planned from the axis sample was 0.2 % over cap)
        cap_c = (mouth[0] + inward[0] * (gap + bw / 2), mouth[1] + inward[1] * (gap + bw / 2))
        mouth_dem = _dem(airport, cap_c)
        if math.isnan(mouth_dem):
            stats.refused.append(f"{tid}: no DEM at the mouth")
            continue
        mouth_z = mouth_dem - tn.bore_datum_m
        # decks across the corridor (a first pass over the full reach)
        deck_ivals = _deck_intervals(axis_ln, half + gap + bw, bridges, bridge_lines,
                                     bridge_tree, law)
        obj_ivals = _object_deck_intervals(axis_ln, half + gap + bw, odecks)
        promoted = _object_deck_intervals(axis_ln, half + gap + bw, cdecks)
        if promoted:
            # a candidate plate crossing the corridor spans the ramp: a
            # deck by the signature's below-grade evidence (04k)
            stats.promoted_candidates += len(promoted)
            obj_ivals = sorted(obj_ivals + promoted, key=lambda t: t[1])
        if obj_ivals:
            # the object law governs where an object bridge stands: a
            # mapped bridge way over it mints no terrain deck (08-30d)
            ou = unary_union([dp for _o, _s0, _s1, dp, _z in obj_ivals])
            deck_ivals = [d for d in deck_ivals if not d[3].intersects(ou)]
        climb_from = max([0.0] + [s1 + gap for _w, s0, s1, _p in deck_ivals]
                         + [s1 + gap for _o, s0, s1, _p, _z in obj_ivals])
        s_top, ss = _ramp_top(airport, law, axis_fn, mouth_z, climb_from, spacing, half)
        if s_top is None:
            stats.refused.append(f"{tid}: the {tn.ramp_max_grade:.0%} climb does not reach "
                                 f"the DEM within {tn.max_ramp_length_m:.0f} m")
            continue
        # a building pad across the approach CLIPS the ramp at the pad's
        # edge (08-07 ruling 3: "the ramp stops at the building edge"; the
        # bore continues under the pad, not emitted); the structure is
        # shortened station by station until its whole footprint clears
        # the pad by the gap, so no vertex is ever shared with it
        top_pinned = True
        clipped_by = ""
        ss = [s for s in ss if s <= s_top + 1e-9]
        while True:
            geom = _geometry(axis_fn, ss, half, gap, bw, inward, grid, axis_ln)
            if geom is None:
                stats.refused.append(f"{tid}: the approach bends tighter than the corridor "
                                     f"(ramp or wall ring self-intersects)")
                break
            axis, nrm, left, right, ramp, wall, outer, cap_in, cap_out = geom
            hit = _pad_hit(outer, pads, pad_tree, gap)
            if hit is None:
                break
            clipped_by = hit
            top_pinned = False
            if len(ss) <= 2:
                stats.refused.append(f"{tid}: the mouth stands against building pad {hit}")
                geom = None
                break
            ss = ss[:-1]
            s_top = ss[-1]
        if geom is None:
            continue
        # refusals: a runway-family crossing, the runway strip keep-out
        if runway_u is not None and outer.intersects(runway_u) and \
                outer.intersection(runway_u).area > 1e-6:
            stats.refused.append(f"{tid}: the ramp would cross a runway-family face "
                                 f"before reaching the DEM (ramp_cuts_runway_family = false)")
            continue
        if strip_u is not None and wall.intersects(strip_u) and \
                wall.intersection(strip_u).area > 1e-6:
            stats.refused.append(f"{tid}: the wall would stand inside the runway strip "
                                 f"keep-out (retaining_wall.in_runway_strip = false)")
            continue
        # decks sever the ramp (by the gap) and the walls (exactly)
        decks: list[Deck] = []
        deck_polys: list[Polygon] = []
        for w, s0, s1, dp in deck_ivals:
            if s0 > s_top:
                continue
            dpoly = dp.intersection(outer)
            if dpoly.is_empty or dpoly.area < 1.0:
                continue
            dref = f"bridge_deck:{w.id}"
            decks.append(Deck(dref, w.id, s0, s1, tuple(dpoly.exterior.coords)[:-1]))
            deck_polys.append(dpoly)
            stats.decks += 1
        # OBJECT BRIDGES: recorded, never severing (the terrain stays open
        # under the object; the deck-top clearance is the generator's row)
        for oid, s0, s1, dp, top_z in obj_ivals:
            if s0 > s_top:
                continue
            dpoly = dp.intersection(outer)
            if dpoly.is_empty or dpoly.area < 1.0:
                continue
            if dpoly.geom_type != "Polygon":
                dpoly = max(_parts(dpoly), key=lambda g: g.area, default=None)
                if dpoly is None:
                    continue
            decks.append(Deck(f"object_deck:{oid}", 0, s0, s1,
                              tuple(dpoly.exterior.coords)[:-1], "deck_top", top_z))
            stats.object_decks += 1
        # the ramp's ref is EXACTLY the oracle's population key too
        # (``ref == "tunnel_ramp"`` sorts a corridor surface as a ramp;
        # anything else is "other" and the mouth is not canonical)
        ramp_refs: list[str] = []
        ramp_geom = ramp
        wall_geom = wall
        if deck_polys:
            du = unary_union(deck_polys)
            # the gap plus one grid step: the severed edge's vertices are
            # noded off-grid and must not round onto the deck's
            ramp_geom = ramp.difference(du.buffer(gap + grid, **_MITRE))
            wall_geom = wall.difference(du)
        for part in _parts(ramp_geom):
            ramp_refs.append("tunnel_ramp")
            new_cells.append(("tunnel_ramp", "tunnel_ramp", part, tid))
        # the wall's ref is EXACTLY the oracle's population key
        # (``tools/tunnel_portal_acceptance.py`` reads ``ref == "tunnel_wall"``);
        # the generator joins wall faces to their tunnel by geometry
        wall_ref = "tunnel_wall"
        for part in _parts(wall_geom):
            new_cells.append(("retaining_wall", wall_ref, part, tid))
        for d, dp in zip(decks, deck_polys):
            for k, part in enumerate(_parts(dp)):
                new_cells.append(("service_road", d.ref + (f"#{k}" if k else ""), part, tid))
        cap_mid = [((ci[0] + co[0]) / 2, (ci[1] + co[1]) / 2) for ci, co in zip(cap_in, cap_out)]
        wall_path = (list(reversed(_offset_line(axis, nrm, half + gap + bw / 2)))
                     + cap_mid + _offset_line(axis, nrm, -(half + gap + bw / 2)))
        notes = []
        if len(members) > 1:
            notes.append(f"dual carriageway of {len(members)} bores (2026-08-31h)")
        if promoted:
            notes.append(f"{len(promoted)} candidate plate(s) promoted to object decks: "
                         "they cross the ramp corridor (04k)")
        for d in decks:
            if d.datum == "deck_top":
                notes.append(f"object bridge {d.ref} deck top {d.z:.2f} over s {d.s0:.0f}-{d.s1:.0f}")
        if clipped_by:
            notes.append(f"clipped at building pad {clipped_by} at {s_top:.1f} m "
                         f"(08-07 ruling 3)")
        tunnels.append(Tunnel(tid, tuple(i for m in members for i in m.ways),
                              tuple(axis), half, mouth_dem, mouth_z, s_top, climb_from,
                              tuple(ramp_refs), wall_ref, tuple(wall_path), tuple(decks),
                              tuple(notes), top_pinned, clipped_by,
                              (cap_mid[0], cap_mid[2]), cap_mid[1]))
        if clipped_by:
            # THE PORTAL FACE AT THE PAD EDGE (08-07 ruling 3): the clipped
            # ramp's top edge stands off the ground beyond it by the gap
            # too — an unowned strip the mesh triangulates as the face —
            # never sharing a vertex with the pavement it stops in (a
            # 12 m stub ramp against a terminal pad was an IIS of its 4 %
            # law against the apron's 1 % across a shared top vertex)
            # the strip spans the WHOLE structure's width (ramp + gaps +
            # bands, however far the retry widened them) so the pavement
            # never reaches a ramp corner round the band's end
            dx, dy = right[-1][0] - left[-1][0], right[-1][1] - left[-1][1]
            L = math.hypot(dx, dy) or 1.0
            ext = gap + 3 * grid + bw + grid
            a = (left[-1][0] - dx / L * ext, left[-1][1] - dy / L * ext)
            b = (right[-1][0] + dx / L * ext, right[-1][1] + dy / L * ext)
            top = LineString([a, b]).buffer(gap + grid, cap_style="flat", **_MITRE)
            outer = unary_union([outer, top])
            if outer.geom_type != "Polygon":
                outer = outer.convex_hull
        footprints.append(outer)
        keepouts.append(outer)
    # TWO STRUCTURES MAY NOT OVERLAP: parallel mouths beyond 31h's test
    # (a diverging separation profile, a crossing approach) would be
    # polygonised into crumbs; the narrower one is refused loudly
    keep = [True] * len(tunnels)
    for i in range(len(tunnels)):
        for j in range(i + 1, len(tunnels)):
            if not (keep[i] and keep[j]):
                continue
            if footprints[i].intersects(footprints[j]) and \
                    footprints[i].intersection(footprints[j]).area > 1.0:
                drop = i if footprints[i].area < footprints[j].area else j
                other = j if drop == i else i
                keep[drop] = False
                stats.refused.append(f"{tunnels[drop].id}: its corridor overlaps "
                                     f"{tunnels[other].id} (not a dual under 31h's "
                                     f"separation test)")
    if not all(keep):
        cell_refs = {t.id for t, k in zip(tunnels, keep) if k}
        new_cells = [c for c in new_cells if _owner_kept(c, tunnels, keep)]
        tunnels = [t for t, k in zip(tunnels, keep) if k]
        footprints = [f for f, k in zip(footprints, keep) if k]
        keepouts = [f for f, k in zip(keepouts, keep) if k]
    stats.tunnels = len(tunnels)
    if not tunnels:
        return classification, (), stats

    # cut the pavement the structures run through (never the runway
    # family, never a pad — those refused above)
    knife = unary_union(footprints)
    out_cells: list[Cell] = []
    for c, p in zip(cells, polys):
        if c.role in RUNWAY_FAMILY or c.role == "building" or not p.intersects(knife):
            out_cells.append(c)
            continue
        rest = p.difference(knife)
        stats.cells_cut += 1
        for k, part in enumerate(_parts(rest)):
            if part.area < 0.25:
                continue
            out_cells.append(Cell(len(out_cells), c.role, c.ref if k == 0 else f"{c.ref}#{k}",
                                  tuple(part.exterior.coords)[:-1],
                                  tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                  c.code_number, c.code_letter, c.side, c.kind,
                                  dict(c.evidence, structure_cut=1.0)))
    for role, ref, part, _tid in new_cells:
        out_cells.append(Cell(len(out_cells), role, ref, tuple(part.exterior.coords)[:-1],
                              tuple(tuple(h.coords)[:-1] for h in part.interiors),
                              None, None, role_side(law, role), "structure", {}))
    out_cells = [_dc.replace(c, id=i) for i, c in enumerate(out_cells)]
    cl = _dc.replace(classification, cells=tuple(out_cells),
                     keepouts=tuple(tuple(k.exterior.coords)[:-1] for k in keepouts),
                     stats={**dict(classification.stats), "tunnels": stats.tunnels,
                            "tunnel_decks": stats.decks, "tunnel_object_decks": stats.object_decks,
                            "tunnel_cells_cut": stats.cells_cut,
                            "tunnels_refused": len(stats.refused)})
    return cl, tuple(tunnels), stats


def _owner_kept(cell: tuple, tunnels: list[Tunnel], keep: list[bool]) -> bool:
    ids = {t.id for t, k in zip(tunnels, keep) if k}
    return cell[3] in ids


def _geometry_at(axis_fn, ss: list[float], half: float, gap: float, bw: float, inward: XY,
                 grid: float, axis_ln: LineString):
    """The ramp, the wall U and the outer footprint for stations ``ss``,
    every vertex ON the identity grid, the wall's rounded AWAY from the
    ramp (``_snap_out``) so the gap is ≥ the law's after the arrangement
    snaps, never collapsed by it.  ``None`` when a bend tighter than the
    offsets folds a ring over itself (a buffer would repair it with
    off-grid vertices — the merge class)."""
    axis = [axis_fn(s) for s in ss]
    nrm = _normals(axis)
    left = [_snap(p, grid) for p in _offset_line(axis, nrm, half)]
    right = [_snap(p, grid) for p in _offset_line(axis, nrm, -half)]
    ramp = Polygon(left + list(reversed(right)))
    if not ramp.is_valid or ramp.area < 1.0:
        return None
    # the band's inner points: offset, snapped away, then PUSHED one grid
    # step further along their direction until each clears the ramp by
    # the gap (a component-wise outward snap can shorten a diagonal
    # offset's projection; the law is the plan distance to the ramp)
    left_in = [_clear(p, d, ramp, gap, grid) for p, d in
               zip(_offset_out(left, nrm, gap, left, grid), nrm)]
    right_in = [_clear(p, (-d[0], -d[1]), ramp, gap, grid) for p, d in
                zip(_offset_out(right, nrm, -gap, right, grid), nrm)]
    left_out = _offset_out(left_in, nrm, bw, left_in, grid)
    right_out = _offset_out(right_in, nrm, -bw, right_in, grid)
    # the cap: left corner, CENTRE (the mouth wall node, 09-03b), right corner
    cap_dir = [(inward[0] + nrm[0][0], inward[1] + nrm[0][1]), inward,
               (inward[0] - nrm[0][0], inward[1] - nrm[0][1])]
    m0 = axis[0]
    cap_in = [_clear(_snap_out((left_in[0][0] + inward[0] * gap, left_in[0][1] + inward[1] * gap),
                               left[0], grid), cap_dir[0], ramp, gap, grid),
              _clear(_snap_out((m0[0] + inward[0] * gap, m0[1] + inward[1] * gap), m0, grid),
                     inward, ramp, gap, grid),
              _clear(_snap_out((right_in[0][0] + inward[0] * gap, right_in[0][1] + inward[1] * gap),
                               right[0], grid), cap_dir[2], ramp, gap, grid)]
    cap_out = [_snap_out((c[0] + d[0] * bw, c[1] + d[1] * bw), c, grid)
               for c, d in zip(cap_in, cap_dir)]
    wall = _u_polygon(left_in, left_out, right_in, right_out, cap_in, cap_out)
    outer = Polygon(list(reversed(left_out)) + list(cap_out) + list(right_out))
    if not wall.is_valid or not outer.is_valid:
        return None
    return axis, nrm, left, right, ramp, wall, outer, cap_in, cap_out


def _geometry(axis_fn, ss: list[float], half: float, gap: float, bw: float, inward: XY,
              grid: float, axis_ln: LineString):
    """:func:`_geometry_at` with the gap widened by grid steps (at most
    three) until the ramp and the wall rings clear each other by the
    law's gap everywhere — the snapped rings are jagged by up to half a
    grid step, so an edge can stand closer than its vertices do.  THE GAP
    IS THE LAW: a bend that cannot be cleared this way is refused, never
    welded."""
    for k in range(4):
        g = _geometry_at(axis_fn, ss, half, gap + k * grid, bw, inward, grid, axis_ln)
        if g is None:
            return None
        if g[4].distance(g[5]) >= gap - 1e-6:
            return g
    return None


def _clear(p: XY, direction: XY, ramp: Polygon, gap: float, grid: float) -> XY:
    """``p`` moved along ``direction`` by grid steps (snapped away from
    where it came from) until it stands ≥ ``gap`` off the ramp."""
    L = math.hypot(direction[0], direction[1]) or 1.0
    ux, uy = direction[0] / L, direction[1] / L
    q = p
    for _k in range(6):
        if ramp.distance(Point(q)) >= gap - 1e-9:
            return q
        q = _snap_out((q[0] + ux * grid, q[1] + uy * grid), q, grid)
    return q


def _pad_hit(outer: Polygon, pads: list[tuple[Polygon, str]], tree: STRtree | None,
             gap: float) -> str | None:
    """The ref of a building pad the footprint touches (closer than the
    gap), or ``None``."""
    if tree is None:
        return None
    for j in tree.query(outer.buffer(gap), predicate="intersects"):
        p, ref = pads[int(j)]
        if p.distance(outer) < gap - 1e-9:
            return ref
    return None


def ramp_targets(tunnels: _t.Sequence[Tunnel], law: Law, faces: dict, edges: list,
                 vxy: list[XY], dem_z: _t.Sequence[float]) -> dict[int, float]:
    """THE RAMP'S OBJECTIVE TARGET IS ITS OWN DESIGN, not the DEM: vertex
    id -> the designed profile value ``clamp(DEM, mouth_z − g·Δs, mouth_z
    + g·Δs)`` (``Δs`` from where the climb starts) for every ``tunnel_ramp``
    ring vertex.  With the DEM as target the ramp's pull levered the
    apron sharing its end cap 0.49 m up through the mouth datum
    (measured on the M4 twin) — groundside pulling airside; at its
    design the ramp has nothing to pull with."""
    if not tunnels:
        return {}
    g = law.tables.structures.tunnel.ramp_max_grade
    axes = {tn.id: LineString(tn.axis) for tn in tunnels}
    out: dict[int, float] = {}
    for fid, face in faces.items():
        if face.role != "tunnel_ramp":
            continue
        ids = {edges[e].a for e in face.ring} | {edges[e].b for e in face.ring}
        cx = sum(vxy[v][0] for v in ids) / len(ids)
        cy = sum(vxy[v][1] for v in ids) / len(ids)
        tid = min(axes, key=lambda k: axes[k].distance(Point(cx, cy)))
        tn = tunnels[[t.id for t in tunnels].index(tid)]
        for v in ids:
            s = axes[tid].project(Point(vxy[v]))
            reach = g * max(0.0, s - tn.climb_from_s)
            d = float(dem_z[v])
            if math.isnan(d):
                continue
            out[v] = max(tn.mouth_z - reach, min(tn.mouth_z + reach, d))
    return out


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]


def _deck_intervals(axis_ln: LineString, half_outer: float, bridges: list[OsmWay],
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


def _object_deck_intervals(axis_ln: LineString, half_outer: float,
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
