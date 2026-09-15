"""THE DECKS OVER A CORRIDOR — the pavement cell that spans it, the
mapped bridge way that crosses it, the hard-deck object above it, and a
terrain deck's two mapped ends (split out of ``planar/structure_approach``
for lane ``v2lemdstruct`` so that file stays inside its 1,000-line budget;
the BORES, MOUTHS and APPROACHES stay there).  No behaviour moved with the
split.

The law these carry, with its rulings:

* A PAVEMENT CELL SPANNING THE CORRIDOR IS A DECK (2026-09-06f):
  :class:`PavementDeck` / :func:`pavement_deck_intervals`.
* A MAPPED BRIDGE WAY'S DECK SPANS THE WAY (spec §33 (4) / §34.5 (6)
  AMENDED, Fable 2026-09-14, RULINGS 2026-09-14bp item 10):
  :func:`deck_intervals`; and decks of PARALLEL bridge ways sharing a
  crossing are ONE group — :func:`deck_groups` / :func:`group_way`.
* A TERRAIN DECK IS TIED TO ITS ENDS (spec §33 (4); owner RULINGS
  2026-09-13d item 9): :func:`deck_ends`.
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
from ..law.tables import role_family
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.structures import Deck
from .structure_approach import PARALLEL_COS, carriageway_width_m, unit

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

__all__ = ["PavementDeck", "pavement_deck_intervals", "deck_intervals",
           "object_deck_intervals", "deck_groups", "group_way", "deck_ends",
           "deck_items", "emit_decks"]


def _dem(airport: Airport, p: XY) -> float:
    """ONE implementation with ``planar/structure_approach._dem``."""
    return float(airport.dem.z(p[0], p[1]))


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]



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
        # §33 (4) / §34.5 (6) AMENDED (Fable 2026-09-14; RULINGS
        # 2026-09-14bp item 10; the owner's words: "that's bridge extent to
        # cover the terrain cutting down to the road running under it").
        # THE DECK SPANS THE WAY.  It was clipped to the tunnel CORRIDOR
        # (⊕ 2 m) — §34.5 (6)'s "beyond the trench the road is ordinary
        # ground" — and the cutting the DEM carries beyond the trench is
        # exactly what a bridge spans: LEMD's two `-6288`/`-6291` decks
        # ended 15–21 m short of the mapped way's own nodes and a 2.2 m
        # deep, 6 m wide notch daylighted into the cutting 16 m past the
        # deck end.  The refusal is WITHDRAWN: the face is the way's own
        # carriageway over its full mapped length.
        dpoly = ln.buffer(wd / 2, cap_style="flat", **_MITRE)
        if dpoly.is_empty:
            continue
        # the covered stretch along the axis — the CROSSING's own part of
        # it (a way spanning the whole corridor may also re-enter the axis
        # far away; min/max over every part would swallow the ramp)
        seg = axis_ln.intersection(dpoly)
        if seg.is_empty:
            continue
        spans = []
        for g in shapely.get_parts(seg):
            ss = [axis_ln.project(Point(q)) for q in g.coords]
            if ss:
                spans.append((min(ss), max(ss)))
        if not spans:
            continue
        inside = [sp for sp in spans if sp[0] - 1e-6 <= s_mid <= sp[1] + 1e-6]
        s_vals = list(inside[0] if inside else
                      min(spans, key=lambda sp: min(abs(sp[0] - s_mid), abs(sp[1] - s_mid))))
        out.append((w, min(s_vals), max(s_vals), dpoly))
    out.sort(key=lambda t: t[1])
    return out


class _GroupWay:
    """The two matched ENDS of a deck group, as the object
    :func:`deck_ends` reads (``.points`` only): the mean of the member
    ways' own mapped ends, so one transverse plane serves both
    carriageways (spec §33 (4) as amended)."""

    __slots__ = ("points", "id", "tags", "ids")

    def __init__(self, points, wid: int, ids: tuple[int, ...]):
        self.points = list(points)
        self.id = wid
        self.ids = ids
        self.tags = {}


def deck_groups(ivals: list[tuple], law: Law) -> list[list[int]]:
    """PARALLEL BRIDGE WAYS SHARING A CROSSING ARE ONE DECK (spec §33 (4)
    / §34.5 (6) AMENDED; Fable 2026-09-14, RULINGS 2026-09-14bp item 10).

    Two mapped bridge ways whose covered stretches along the corridor's
    axis stand within ``[bridge] deck_group_gap_max_m`` of each other and
    whose chords are parallel within ``PARALLEL_COS`` are the two
    carriageways of ONE bridge: they take one transverse plane at
    each end, and one face, so no rim sliver stands between them.
    Measured LEMD ways ``-6288`` / ``-6291``: clipped and end-equalised
    independently, their east levels solved 606.91 against 608.40 with a
    three-node rim sliver in the gap — the owner's "small gap here".
    Returns the member indices per group, in ``s0`` order."""
    n = len(ivals)
    # NOT a strict s-overlap: two PARALLEL carriageways cross the axis at
    # DIFFERENT stations by construction (measured LEMD -6288 / -6291 —
    # their full-way faces meet the axis in two disjoint s-ranges), so a
    # strict overlap test groups nothing.  The median between them is the
    # same gap ``_deck_face`` closes.
    gap_max = float(law.tables.structures.bridge.deck_group_gap_max_m)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        wi, s0i, s1i, _dpi = ivals[i]
        ui = unit(tuple(wi.points[0]), tuple(wi.points[-1]))
        for j in range(i + 1, n):
            wj, s0j, s1j, _dpj = ivals[j]
            if max(s0i, s0j) - min(s1i, s1j) > gap_max:
                continue                     # they do not share the crossing
            uj = unit(tuple(wj.points[0]), tuple(wj.points[-1]))
            if abs(ui[0] * uj[0] + ui[1] * uj[1]) < PARALLEL_COS:
                continue                     # not parallel: two crossings
            a, b = find(i), find(j)
            if a != b:
                parent[a] = b
    seen: dict[int, list[int]] = {}
    for i in range(n):
        seen.setdefault(find(i), []).append(i)
    return sorted(seen.values(), key=lambda g: min(ivals[k][1] for k in g))


def group_way(ways: list) -> _GroupWay:
    """The deck group's own two ends (spec §33 (4) as amended): each
    member's mapped ends matched to the first member's by proximity, and
    averaged — ONE transverse plane per end, read by :func:`deck_ends`
    exactly as a single way's is."""
    a0, a1 = tuple(ways[0].points[0]), tuple(ways[0].points[-1])
    acc = [[a0[0], a0[1]], [a1[0], a1[1]]]
    for w in ways[1:]:
        b0, b1 = tuple(w.points[0]), tuple(w.points[-1])
        straight = math.dist(a0, b0) + math.dist(a1, b1)
        crossed = math.dist(a0, b1) + math.dist(a1, b0)
        if crossed < straight:
            b0, b1 = b1, b0
        acc[0][0] += b0[0]; acc[0][1] += b0[1]
        acc[1][0] += b1[0]; acc[1][1] += b1[1]
    k = float(len(ways))
    return _GroupWay([(acc[0][0] / k, acc[0][1] / k), (acc[1][0] / k, acc[1][1] / k)],
                     ways[0].id, tuple(w.id for w in ways))


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




def _deck_face(polys: list[Polygon], grid: float, law: Law) -> tuple[Polygon | None, float]:
    """ONE FACE FOR A DECK GROUP (spec §33 (4) as amended; owner
    2026-09-14bl item 10 "should be a single smooth bridge, no small gap
    here"): the members' carriageway faces unioned and, where the
    carriageways stand apart, morphologically CLOSED across the gap
    between them — the strip of terrain between two parallel decks is the
    rim sliver the owner read, not ground anyone sees.  Returns
    ``(face, the gap closed in metres)``; the gap is closed only up to
    ``[bridge] deck_group_gap_max_m``, past which the two ways are a
    dual carriageway with real ground between and each keeps its own
    face."""
    u = unary_union(polys)
    if u.is_empty:
        return None, 0.0
    parts = _parts(u)
    if len(parts) <= 1:
        return (max(parts, key=lambda g: g.area) if parts else None), 0.0
    gap = 0.0
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            gap = max(gap, float(parts[i].distance(parts[j])))
    cap = float(law.tables.structures.bridge.deck_group_gap_max_m)
    if gap <= 0.0 or gap > cap:
        return max(parts, key=lambda g: g.area), 0.0
    c = gap / 2.0 + grid
    closed = u.buffer(c, **_MITRE).buffer(-c, **_MITRE)
    cp = _parts(closed)
    if len(cp) != 1:
        return max(parts, key=lambda g: g.area), 0.0
    return cp[0], gap


def deck_items(deck_ivals: list[tuple], pav_ivals: list[tuple], grid: float,
               law: Law) -> list[tuple]:
    """THE DECKS A CORRIDOR EMITS, one entry per FACE (spec §33 (4) as
    amended): ``(way, s0, s1, face, is a pavement deck, the grouped ways,
    the gap closed)``, in ``s0`` order.  The mapped-bridge decks of
    parallel ways sharing the crossing are collapsed to ONE entry by
    :func:`deck_groups`; a PAVEMENT deck is the pavement cell's own
    surface and is never grouped."""
    items: list[tuple] = []
    for grp in deck_groups(deck_ivals, law):
        ms = [deck_ivals[i] for i in grp]
        face, closed = _deck_face([m[3] for m in ms], grid, law)
        if face is None:
            continue
        items.append((ms[0][0], min(m[1] for m in ms), max(m[2] for m in ms),
                      face, False, [m[0] for m in ms], closed))
    items.extend((w, s0, s1, dp, True, (), 0.0) for w, s0, s1, dp in pav_ivals)
    items.sort(key=lambda t: t[1])
    return items


def emit_decks(airport: Airport, law: Law, items: list[tuple], obj_ivals: list[tuple],
               outer: Polygon, s_top: float, cells, polys, cell_tree):
    """THE DECK FACES A CORRIDOR EMITS (spec §33 (4) as amended; moved out
    of ``planar/structures`` with the rest of the deck law, lane
    ``v2lemdstruct`` — that file stands at its 1,000-line budget).
    Returns ``(decks, the mapped/pavement deck faces, their roles, the
    MAPPED-bridge faces alone, the notes, pavement decks, bridge decks,
    object decks)``.  The object bridges come LAST in ``decks`` and carry
    no face or role: they are recorded, never severing, exactly as
    before."""
    decks: list[Deck] = []
    deck_polys: list[Polygon] = []
    deck_roles: list[str] = []
    bridge_faces: list[Polygon] = []
    deck_notes: list[str] = []
    npav = nbr = nobj = 0
    for w, s0, s1, dp, pav, dways, closed in items:
        if s0 > s_top:
            continue
        # THE DECK SPANS THE WAY (spec §33 (4) as amended): a mapped
        # bridge's face is the way's own carriageway over its full
        # length, never clipped to the corridor.  A PAVEMENT deck keeps
        # the clip: it IS a cell that already stands there.
        dpoly = dp.intersection(outer) if pav else dp
        if dpoly.is_empty or dpoly.area < 1.0:
            continue
        if dpoly.geom_type != "Polygon":
            dpoly = max(_parts(dpoly), key=lambda g: g.area, default=None)
            if dpoly is None:
                continue
        dref = f"bridge_deck:{w.id}"
        # A TERRAIN DECK IS TIED TO ITS ENDS (spec §33 (4)): the ground
        # at the mapped way's two ends — the apron on one side, the road
        # on the other — read once here and carried on the record (a
        # pavement deck is the pavement's own surface and needs none).
        ez, eref, exy = ((), (), ()) if pav \
            else deck_ends(airport, group_way(list(dways)) if len(dways) > 1 else w,
                            cells, polys, cell_tree, law)
        decks.append(Deck(dref, 0 if pav else w.id, s0, s1,
                          tuple(dpoly.exterior.coords)[:-1],
                          end_z=ez, end_ref=eref, end_xy=exy))
        if not pav:
            bridge_faces.append(dpoly)
            if len(dways) > 1:
                deck_notes.append(
                    f"{dref}: ONE deck over {len(dways)} parallel bridge ways "
                    f"({', '.join(str(x.id) for x in dways)}) sharing the crossing — one "
                    f"transverse plane at each end" + (f", the {closed:.1f} m gap between "
                    f"the carriageways closed" if closed > 0.0 else "") + " (§33 (4))")
        deck_polys.append(dpoly)
        # a pavement deck keeps the pavement's role (2026-09-06f); a
        # mapped bridge is road ground (08-30m)
        deck_roles.append(w.role if pav else "service_road")
        if pav:
            npav += 1
        else:
            nbr += 1
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
        nobj += 1
    return (decks, deck_polys, deck_roles, bridge_faces, deck_notes, npav, nbr, nobj)
