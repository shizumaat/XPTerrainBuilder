"""THE RUNWAY SHOULDER THE APT.DAT STATES (spec §40 (6); owner RULINGS
2026-10-20n, 20o, 20p; issue #1103).

Two rules, each at its one derivation site in ``classify/roles``:

1. THE SHOULDER BAND (20n): every runway's graded band reads the row-100
   shoulder width (``Runway.shoulder_m``) as its §40 shoulder — the slab
   widened by that width on each side (:func:`apt_shoulder_band`).  Where
   no pavement already covers the band, :func:`mint_apt_shoulders` mints
   the uncovered ground as runway-shoulder cells, LAST, so the band only
   fills unpaved ground and never crosses pavement (20o, 20p: "only the
   adjacent unpaved ground stays off pavement").

2. THE SHOULDER STOPS AT A TAXIWAY ENTRANCE (20o, 20p): a §40 pavement
   shoulder may lie on pavement, but where a taxiway leaves the runway the
   taxiway is a taxiway and welds to the runway edge.
   :func:`taxiway_entrances` reads the entrance off the shoulder
   candidate itself: a part of it BEYOND the shoulder line (the apt.dat
   band; where the row states no width, the candidate's own mean depth)
   that a taxi centreline runs through into the shoulder, and that reads
   as a corridor of that centreline (``corridor.max_width_m``, the
   corridor ladder's own width test), together with its MOUTH — the
   shoulder pavement between it and the runway edge over the stations it
   meets the shoulder line at.

Nothing here names an airport: the width is the apt.dat's, the tests are
the classifier's own rungs."""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..law import Law
from ..law.tables import snap_margin_m
from ..model.planar import is_late_ref
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["apt_shoulder_band", "taxiway_entrances", "mint_apt_shoulders",
           "APT_SOURCE"]

#: ``shoulder_source`` of a cell the band minted on unpaved ground
APT_SOURCE = "apt.dat"
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _axis(rw) -> tuple[tuple[float, float], tuple[float, float]]:
    """The slab's centreline, physical end to physical end
    (``Runway.slab_corners``, the one slab derivation)."""
    c0, c1, c2, c3 = rw.slab_corners
    return (((c0[0] + c3[0]) / 2, (c0[1] + c3[1]) / 2),
            ((c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2))


def apt_shoulder_band(rw) -> Polygon | None:
    """The runway slab widened by the apt.dat shoulder width on each side
    (20n), flat at the slab's own ends; ``None`` where the row states no
    shoulder width."""
    s = float(getattr(rw, "shoulder_m", 0.0) or 0.0)
    if s <= 0.0:
        return None
    a, b = _axis(rw)
    if a == b:
        return None
    return LineString([a, b]).buffer(rw.width_m / 2.0 + s, cap_style="flat")


def _shoulder_line(rw, depth_m: float) -> tuple[Polygon | None, float]:
    """WHERE THE SHOULDER ENDS, as ``(band, half width off the centreline)``
    — what a taxiway entrance is measured from: the apt.dat shoulder band
    (20n), or, where the row states no width, the shoulder candidate's own
    mean depth off the runway edge (``depth_m``: its band area over its
    shared length, the §40 (1) ribbon evidence).  The depth only LOCATES
    the ribbon's edge; pavement beyond it with no taxiway through it stays
    shoulder (§40 (5))."""
    s = float(getattr(rw, "shoulder_m", 0.0) or 0.0) or max(float(depth_m), 0.0)
    a, b = _axis(rw)
    if a == b:
        return None, 0.0
    half = rw.width_m / 2.0 + s
    return LineString([a, b]).buffer(half, cap_style="flat"), half


def _shoulder_sides(rw):
    """The apt.dat shoulder band's two LONG SIDES (20n) — the shoulder
    line each side of the slab, without the band's flat ends."""
    (ax, ay), (bx, by) = _axis(rw)
    L = math.hypot(bx - ax, by - ay)
    nx, ny = -(by - ay) / L, (bx - ax) / L
    h = rw.width_m / 2.0 + float(rw.shoulder_m)
    return MultiLineString([[(ax + k * h * nx, ay + k * h * ny),
                             (bx + k * h * nx, by + k * h * ny)] for k in (1.0, -1.0)])


def taxiway_entrances(inside, rw, taxi_parts, taxi_tree, rules: Rules,
                      depth_m: float = 0.0) -> list[Polygon]:
    """The TAXIWAY ENTRANCES inside a §40 shoulder candidate's band part
    ``inside`` (20o, 20p).  ``taxi_parts`` are the slice's ``(line, chain)``
    taxi centrelines and ``taxi_tree`` their STRtree; ``depth_m`` the
    candidate's mean depth (:func:`_shoulder_line`).

    An entrance is a connected part of ``inside`` beyond the shoulder line
    (:func:`_shoulder_line`) that (a) a taxi centreline running into the
    shoulder line passes through, and (b) reads as a CORRIDOR of those
    centrelines: its area over their length inside it is at most
    ``corridor.max_width_m`` — the width test ``roles._kind`` gives every
    corridor.  A wide page pressed along the runway (§40 (1)'s ribbon that
    a connector merely crosses) is not an entrance and stays shoulder.
    Each entrance is returned with its MOUTH (:func:`_mouth`)."""
    if taxi_tree is None or inside.is_empty:
        return []
    line, half = _shoulder_line(rw, depth_m)
    if line is None:
        return []
    reach = line.buffer(rules.cells.on_tol_m)
    out: list[Polygon] = []
    tol = rules.cells.on_tol_m
    for comp in polygon_parts(inside.difference(line)):
        if comp.area < rules.cells.min_area_m2:
            continue
        # the centreline length ON the part, within the touch tolerance: the
        # slice cuts along a centreline, so a stub's halves each carry it
        # on their boundary rather than inside
        near = comp.buffer(tol, **_MITRE)
        length = 0.0
        for i in taxi_tree.query(near):
            ln = taxi_parts[int(i)][0]
            if ln.intersects(reach) and ln.intersects(near):
                length += ln.intersection(near).length
        if length <= 0.0 or comp.area > rules.corridor.max_width_m * length:
            continue
        mouth = _mouth(comp, rw, line, half, inside, rules)
        out.extend(polygon_parts(comp.union(mouth) if mouth is not None else comp))
    return [p for p in out if p.area >= rules.cells.min_area_m2]


def _mouth(comp, rw, line, half: float, inside, rules: Rules):
    """THE ENTRANCE'S MOUTH: the part of ``inside`` between the runway's
    centreline and its shoulder line over the stations ``comp`` meets the
    shoulder line at, on ``comp``'s side — the taxiway carried straight
    across the shoulder to the runway edge, so it welds to the runway.

    The touch tolerance FINDS the seam; it never WIDENS it: the stations
    are clamped to ``comp``'s own station extent.  MEASURED (EDTK, #1135):
    the 1 m mitred buffer carried the mouth 0.68 m past the entrance's
    edge where it abuts a parallel runway's end, carving a sliver off the
    shoulder there and minting a vertex 0.68 m from that runway's corner —
    the corner left the shoulder's datum and dropped 1.66 m under it, a
    ``runway_step`` cliff between the two runways."""
    seam = comp.buffer(rules.cells.on_tol_m, **_MITRE).intersection(line)
    if seam.is_empty:
        return None
    (ax, ay), (bx, by) = _axis(rw)
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    pts = [c for g in polygon_parts(seam) for c in g.exterior.coords]
    if not pts:
        return None
    st = [((x - ax) * ux + (y - ay) * uy) for x, y in pts]
    side = sum(-(x - ax) * uy + (y - ay) * ux for x, y in pts)
    t = (1.0 if side >= 0.0 else -1.0) * half
    own = [((x - ax) * ux + (y - ay) * uy) for g in polygon_parts(comp)
           for x, y in g.exterior.coords]
    s0, s1 = max(min(st), min(own)), min(max(st), max(own))
    if s1 <= s0:
        return None
    rect = Polygon([(ax + ux * s - uy * tt, ay + uy * s + ux * tt)
                    for s, tt in ((s0, 0.0), (s1, 0.0), (s1, t), (s0, t))])
    m = rect.intersection(inside)
    return None if m.is_empty else m


def mint_apt_shoulders(airport, cells: list, law: Law, rules: Rules,
                       add: _t.Callable[..., None], kind: str) -> dict:
    """20n: THE UNPAVED PART OF EACH RUNWAY'S SHOULDER BAND as runway
    cells of ``kind`` (§40's shoulder kind), the runway's ref, code number
    and letter.  Called by ``roles.classify`` LAST, after every pavement,
    pad, road and gap cell is standing: the band MINUS every cell (a
    groundside one with the zone bands' own stand-off,
    ``zones.adjacent_ground.groundside_cutback_m`` + the snap margin, so the
    shoulder meets a road or lot the way a zone band does).  A piece is
    kept only when it lies along its runway — within ``cells.on_tol_m`` of
    the slab or of the runway's own shoulder — and is somewhere wider than
    that same tolerance: a strip narrower than the touch tolerance is the
    pavement edge's own noise, not ground.

    AND IT REACHES THE SHOULDER LINE (20n, 20o): a piece of the band is
    the band's ground only when it runs out to the band's own long side
    (:func:`_shoulder_sides`, within the same tolerance).  A piece that
    pavement closes off before the line is the SEAM between the runway and
    a pavement that abuts it (20o: they weld directly), not shoulder
    ground: minted as a runway cell, its outer ring is the abutting
    pavement's edge, which that pavement's own law pulls off the runway's
    level, and the runway family reads a cliff across it.  MEASURED (HECA
    on its WED pack, apron ``dsf:pol198`` 0.4–1.8 m off 05C/23C's edge):
    two such seams minted 15 ``runway_step`` DEFECT rows (0.15–0.63 m over
    0.2–1.0 m); the seam left to the adjacent ground reads none.  Returns
    the stats."""
    bands = [(rw, b) for rw in getattr(airport, "runways", ())
             for b in (apt_shoulder_band(rw),) if b is not None]
    stats = {"apt_shoulders": 0, "apt_shoulder_m2": 0.0}
    if not bands:
        return stats
    cut = law.tables.zones.adjacent_ground.groundside_cutback_m + snap_margin_m(law)
    extent = unary_union([b for _rw, b in bands])
    taken = []
    for c in cells:
        g = Polygon(c.ring, c.holes)
        if not g.intersects(extent.buffer(cut)):
            continue
        groundside = c.side == "groundside" and not is_late_ref(getattr(c, "ref", ""))
        taken.append(g.buffer(cut, **_MITRE) if groundside else g)
    taken_u = canonical_union(taken) if taken else None
    tol = rules.cells.on_tol_m
    for rw, band in bands:
        host = unary_union([Polygon(rw.slab_corners)]
                           + [Polygon(c.ring, c.holes) for c in cells
                              if c.role == "runway" and c.ref == rw.id])
        sides = _shoulder_sides(rw)
        minted = []
        for p in polygon_parts(fixed_difference(band, taken_u)):
            if p.area < rules.cells.min_area_m2 or is_hairline(p, tol) \
                    or p.distance(host) > tol or p.distance(sides) > tol:
                continue
            add("runway", rw.id, p, kind, rw.code_number, rw.code_letter,
                {"area_m2": p.area, "kind": kind, "shoulder_of": rw.id,
                 "shoulder_source": APT_SOURCE,
                 "shoulder_width_m": float(rw.shoulder_m)})
            minted.append(p)
            stats["apt_shoulders"] += 1
            stats["apt_shoulder_m2"] += p.area
        if minted:     # a crossing runway's band never re-claims this ground
            taken_u = canonical_union(([taken_u] if taken_u is not None else []) + minted)
    return stats
