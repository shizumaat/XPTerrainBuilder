"""NO 3D TREE ON THE MOVEMENT AREA'S STRIPS (issue #1920): the X-Plane 12
tree upgrade (:mod:`.pack_forests`, :mod:`.pack_trees`) never puts a tree
inside a runway strip, its safety area beyond each end, or a taxiway
strip.

Owner (2026-11-06, LGAV): "where we had grass by the runways, we now have
small trees that are much too tall to be allowed there.  We need to be
able to ensure vegetation heights near aircraft movement surfaces do not
exceed regulations."  Annex 14 §3.4.6 / §3.5 and AC 150/5300-13B §3.16
keep the strip, the RESA / RSA and the taxiway strip free of objects; a
tree is one.  Any pack, any airport:

* THE AREAS — :func:`clear_areas`: per airport of the pack's own
  ``apt.dat`` (rows 100 and 1202), the runway rectangle ``axis ± strip
  half-width`` (``law.tables.zone2_half_width_m``, by code number, letter
  and instrument status — the engine's graded-strip table) over the
  runway extended by the safety-area length beyond each end
  (``law.tables.runway_safety_area_length_m``), and each taxi edge's
  rectangle ``± taxi strip half-width`` (the same table, taxi family, by
  the edge's letter).  The ruleset is the airport's (``Law.for_airport``).
  A pack with no ``apt.dat`` has no areas: nothing is cleared.
* THE CLEARING — :func:`clear_trees`: every polygon of a definition the
  upgrade wrote (a 3D tree forest) loses what lies inside the areas — an
  area forest is cut (its rings differenced), a point forest loses the
  trees inside, a line forest whose edges reach an area goes whole.  The upgrade's
  X-Plane 12 shrubs are cleared like trees; its grass (a planter no
  taller than ``pack_trees_map.GRASS_M``) and what it leaves alone stay
  (``pack_forests.clear_strips`` picks the definitions).
"""
from __future__ import annotations

import math
import os
import typing as _t

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from .pack_trees import EARTH_R

__all__ = ["clear_areas", "clear_trees"]

#: a forest polygon parameter at or above this draws trees along its edges
LINE_FOREST = 256
#: ... and at or above this, one tree at each vertex
POINT_FOREST = 512
#: apt.dat row-100 markings code -> instrument status (0 / 1 instrument /
#: 2 precision): 2 and 4 non-precision, 3 and 5 precision
_MARKING_STATUS = {2: 1, 4: 1, 3: 2, 5: 2}


def _frame(lat0: float):
    """(lon, lat) -> metres and back, about latitude ``lat0``."""
    k = math.pi * EARTH_R / 180.0
    c = max(math.cos(math.radians(lat0)), 1e-6)
    return (lambda lon, lat: (lon * k * c, lat * k)), \
        (lambda x, y: (x / (k * c), y / k))


def _rect(a: tuple[float, float], b: tuple[float, float], half: float,
          ext: float) -> list[tuple[float, float]] | None:
    """The rectangle ``a``-``b`` (metres) ± ``half``, ``ext`` beyond each end."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return None
    ux, uy = dx / n, dy / n
    px, py = -uy * half, ux * half
    a2 = (a[0] - ux * ext, a[1] - uy * ext)
    b2 = (b[0] + ux * ext, b[1] + uy * ext)
    return [(a2[0] + px, a2[1] + py), (b2[0] + px, b2[1] + py),
            (b2[0] - px, b2[1] - py), (a2[0] - px, a2[1] - py)]


def _family_role(law, family: str) -> str:
    return next(r for r, v in law.tables.precedence.roles.items()
                if v.family == family)


def _airport_rects(ap, law, to_m) -> list[list[tuple[float, float]]]:
    """The runway strips + safety areas and the taxiway strips, metres."""
    from ..law import reference_code as _rc
    from ..law import tables as _T
    out = []
    from . import approach as _approach
    rw_role, tx_role = _family_role(law, "runway"), _family_role(law, "taxi")
    ramp_class = _approach.airport_ramp_class(ap)
    for rw in ap.runways:
        a, b = (to_m(e[2], e[1]) for e in rw.ends)
        cn = _rc.runway_code_number(law, math.hypot(b[0] - a[0], b[1] - a[1]))
        letter = _approach.design_letter(law, rw, ramp_class)
        status = max(_MARKING_STATUS.get(int(m), 0) for m in rw.markings)
        half = max(_T.zone2_half_width_m(law, rw_role, cn, letter, status) or 0.0,
                   rw.width_m / 2.0)
        out.append(_rect(a, b, half,
                         _T.runway_safety_area_length_m(law, cn, letter, status)))
    for e in ap.taxi_edges:
        na, nb = ap.taxi_nodes.get(e.a), ap.taxi_nodes.get(e.b)
        if na is None or nb is None or not e.kind.startswith("taxiway"):
            continue
        letter = e.kind.rpartition("_")[2].upper() or None
        half = _T.zone2_half_width_m(law, tx_role, None, letter) or 0.0
        out.append(_rect(to_m(na.lon, na.lat), to_m(nb.lon, nb.lat), half, half))
    return [r for r in out if r]


def clear_areas(pack_root: str) -> list[Polygon]:
    """THE AREAS of every airport the pack's own ``apt.dat`` declares, as
    ``(lon, lat)`` polygons; ``[]`` without one."""
    from ..law import Law
    from . import apt_dat as _apt
    path = os.path.join(pack_root, "Earth nav data", "apt.dat")
    out: list[Polygon] = []
    for icao in (_apt.airports_in(path) if os.path.isfile(path) else ()):
        block = _apt.read_airport_block(path, icao)
        if not block:
            continue
        ap = _apt.parse_airport_block(block)
        try:
            to_m, to_deg = _frame(ap.reference_point()[0])
        except ValueError:
            continue
        for r in _airport_rects(ap, Law.for_airport(icao), to_m):
            out.append(Polygon([to_deg(x, y) for x, y in r]))
    return out


def _polygon_blocks(lines: _t.Sequence[str]):
    """``(start, end, def index, param, tail, windings)`` of each
    ``BEGIN_POLYGON`` block; a winding is ``[(lon, lat, rest), ...]``."""
    i = 0
    while i < len(lines):
        tok = lines[i].split()
        if tok[:1] != ["BEGIN_POLYGON"] or len(tok) < 3:
            i += 1
            continue
        start, windings, cur = i, [], None
        i += 1
        while i < len(lines) and not lines[i].startswith("END_POLYGON"):
            t = lines[i].split()
            if t[:1] == ["BEGIN_WINDING"]:
                cur = []
            elif t[:1] == ["END_WINDING"] and cur is not None:
                windings.append(cur)
                cur = None
            elif t[:1] == ["POLYGON_POINT"] and cur is not None:
                cur.append((float(t[1]), float(t[2]), t[3:]))
            i += 1
        yield start, i, int(tok[1]), int(tok[2]), tok[3:], windings
        i += 1


def _block(idx: int, param: int, tail: list[str], windings) -> list[str]:
    out = [" ".join(["BEGIN_POLYGON", str(idx), str(param), *tail]) + "\n"]
    for w in windings:
        out.append("BEGIN_WINDING\n")
        out.extend(" ".join(["POLYGON_POINT", f"{x:.9f}", f"{y:.9f}", *rest])
                   + "\n" for x, y, rest in w)
        out.append("END_WINDING\n")
    out.append("END_POLYGON\n")
    return out


def _cut_area(idx: int, param: int, tail: list[str], windings, area
              ) -> list[str] | None:
    """An area forest minus ``area``; ``None`` when it does not meet it."""
    rings = [[(x, y) for x, y, _ in w] for w in windings if len(w) >= 3]
    if not rings:
        return None
    poly = Polygon(rings[0], rings[1:]).buffer(0)
    if not poly.intersects(area):
        return None
    out: list[str] = []
    rest = poly.difference(area)
    for p in getattr(rest, "geoms", [rest]):
        if p.geom_type != "Polygon" or p.is_empty or p.area <= 0:
            continue
        out.extend(_block(idx, param, tail,
                          [[(x, y, []) for x, y in list(r.coords)[:-1]]
                           for r in [p.exterior, *p.interiors]]))
    return out


def _cut_points(idx: int, param: int, tail: list[str], windings, area
                ) -> list[str] | None:
    """A point forest without its trees (vertices) inside ``area``."""
    kept = [[p for p in w if not area.contains(Point(p[0], p[1]))]
            for w in windings]
    if sum(map(len, kept)) == sum(map(len, windings)):
        return None
    kept = [w for w in kept if w]
    return _block(idx, param, tail, kept) if kept else []


def _cut_line(idx: int, param: int, tail: list[str], windings, area
              ) -> list[str] | None:
    """A line forest (trees along its edges) whose edges reach ``area``
    is removed whole: cutting a chain would redraw its closing edge."""
    for w in windings:
        pts = [(x, y) for x, y, _ in w]
        if len(pts) >= 2 and LineString(pts + pts[:1]).intersects(area):
            return []
        if len(pts) == 1 and area.contains(Point(pts[0])):
            return []
    return None


def clear_trees(text: str, tree_defs: _t.Collection[int],
                areas: _t.Sequence[Polygon]) -> tuple[str, int]:
    """THE CLEARING (pure): ``text`` with every polygon of a definition in
    ``tree_defs`` (``POLYGON_DEF`` indices) cleared of ``areas``.  Returns
    the text and the polygons changed (cut or removed)."""
    if not tree_defs or not areas:
        return text, 0
    area = unary_union(areas)
    env = box(*area.bounds)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    at = changed = 0
    for start, end, idx, param, tail, windings in _polygon_blocks(lines):
        pts = [(x, y) for w in windings for x, y, _ in w]
        if idx not in tree_defs or not pts or not env.intersects(
                box(*_bounds(pts))):
            continue
        cut = (_cut_area if param < LINE_FOREST else
               _cut_line if param < POINT_FOREST else _cut_points)(
            idx, param, tail, windings, area)
        if cut is None:
            continue
        out.extend(lines[at:start])
        out.extend(cut)
        at = end + 1
        changed += 1
    out.extend(lines[at:])
    return "".join(out), changed


def _bounds(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)
