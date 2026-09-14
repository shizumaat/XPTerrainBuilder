"""§43 AN APRON ENDS AT ITS MOUTH (owner RULINGS 2026-09-14c item 2;
Fable 2026-09-14; ``rules.apron.neck_width_m`` / ``neck_length_m``).

The owner, verbatim: "Aprons, like parking lots are joined by roads, are
separated by taxiways.  A taxiway can run along an apron edge, but when
the taxiway leaves the apron at a mouth, it's only taxiway until it
widens into another apron … taxiways should carry more of the slope than
aprons."

THE DEFECT (HECA, the owner's 1.0.331 products).  ``shapeID 344`` is ONE
apron cell of 79,919 m² (``dsf:objpav100``, 23 touching taxi chains) that
spans a wide apron, ~300 m of 40 m-wide taxiway, and a second wide apron.
``roles._kind`` read its MEAN width — area over the length of boundary
shared with the touching centrelines — as 44.8 m, called it a corridor,
and §40 (2) then refused the corridor on 50 % mapped apron cover, so the
whole thing came out apron: one tier plane over an apron, a taxiway and
another apron, and the taxiway carries none of the slope.

The mean is the wrong instrument.  A dumbbell's mean width is the mean of
its lobes and its neck; the LOCAL width is what says where the apron ends.

THE READING.  Local width comes from the EROSION, the idiom the terrace
bodies already use (``planar/shapes.py``, owner RULINGS 2026-09-08k: "the
bodies of one component are the connected parts of its erosion by half
the mouth width").  A point of a face has local width ≥ W exactly where an
inscribed disc of radius W/2 covers it, i.e. where it lies within W/2 of
the face's erosion by W/2.  So, per face:

* ``lobes`` — the parts of the erosion by ``neck_width_m`` / 2: the
  pavement wide enough to be an apron;
* ``WIDE`` — those lobes dilated back by the same half width, clipped to
  the face: every point of local width ≥ ``neck_width_m``;
* ``NARROW = face - WIDE`` — every point of local width < it.  Its
  components are the necks, the fringes of the wide pavement's own
  corners, and the dead-end spurs;
* a component adjacent to TWO OR MORE lobes is a NECK: pavement that
  narrows below the apron width between two wide bodies.  A fringe or a
  spur touches one lobe and is not a neck however long; a neck shorter
  than ``neck_length_m`` is a NOTCH and is not cut (§43 (1)'s length).

THE CUT LINES are the neck's MOUTHS — "the shortest chord across the
pavement at the point where the width crosses the neck width" (§43 (2)).
Each mouth is the curve where the neck meets a lobe's dilation; the chord
is the straight segment between that curve's two ends on the face
boundary, extended by ``cells.on_tol_m`` at each end so it cuts cleanly,
and the mouth curve itself where the chord would leave the pavement (a
neck that bends through its own mouth).

§43 (3), WHAT DOES NOT CUT, is enforced by the CALLER
(``roles.classify``), which never offers this pass a face that is a road
STRIP or a parking LOT (§27's roads-join-lots faces are cut at their own
boundary already, owner 2026-09-04j) or a §40 (1) runway shoulder.  "A
taxiway running ALONG an apron edge does not cut" needs no rule here: a
taxiway along an edge is pavement of full width — nothing narrows, the
erosion has ONE part and there is no neck.
"""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from .evidence import polygon_parts
from .rules import Rules

__all__ = ["Neck", "necks_of", "split_at_necks"]


@_dc.dataclass(frozen=True)
class Neck:
    """One detected neck and the numbers the verdict used."""

    #: the neck's own polygon (the stretch below ``neck_width_m``)
    polygon: Polygon
    #: the mouth CUT LINES, one per lobe the neck joins
    cuts: tuple[LineString, ...]
    #: each mouth CUT LINE's own two ends, in the frame — the chord the
    #: cut is made on, which is what the census names and what an owner
    #: cut line is compared against (never the mouth CURVE's midpoint:
    #: the curve is an arc of the lobe's dilation and wraps past the
    #: chord, measured 33 m at HECA's shape-344 north mouth)
    mouth_lines: tuple[tuple[tuple[float, float], tuple[float, float]], ...]
    length_m: float
    width_m: float
    area_m2: float
    n_lobes: int
    #: mouths whose straight chord left the pavement and fell back to the
    #: mouth curve itself
    curved_mouths: int


def necks_of(face: Polygon, rules: Rules) -> list[Neck]:
    """Every §43 neck of ``face``: a stretch of local width below
    ``apron.neck_width_m`` at least ``apron.neck_length_m`` long joining
    two or more wide lobes of the same face."""
    ap = rules.apron
    w, need = ap.neck_width_m, ap.neck_length_m
    if w <= 0.0 or need <= 0.0 or face.area <= 0.0:
        return []
    half = w / 2.0
    lobes = [b for b in polygon_parts(face.buffer(-half)) if b.area > 0.0]
    if len(lobes) < 2:
        return []                      # nothing narrows between two bodies
    reach = [b.buffer(half).intersection(face) for b in lobes]
    wide = unary_union(reach)
    out: list[Neck] = []
    for part in polygon_parts(face.difference(wide)):
        if part.area <= rules.cells.min_area_m2:
            continue
        touching = [(k, r) for k, r in enumerate(reach)
                    if part.boundary.intersection(r.boundary).length > 0.0]
        if len(touching) < 2:
            continue                   # a dead-end spur off ONE lobe
        if not _separates(face, part, [lobes[k] for k, _r in touching],
                          rules):
            continue                   # a FRINGE, not a neck
        touching = [r for _k, r in touching]
        mouths = [part.boundary.intersection(r.boundary) for r in touching]
        mouth_m = sum(m.length for m in mouths)
        # the neck's length: its two side walls' mean run, the corridor
        # mean-width idiom read the other way round (a corridor's
        # perimeter is its two walls plus its two mouths)
        length = (part.exterior.length - mouth_m) / 2.0
        if length < need:
            continue                   # §43 (1): a notch, not a neck
        cuts: list[LineString] = []
        mids: list[tuple[tuple[float, float], tuple[float, float]]] = []
        curved = 0
        for m in mouths:
            chord, raw, is_curve = _mouth_chord(m, face, rules)
            if chord is None:
                continue
            curved += int(is_curve)
            cuts.append(chord)
            mids.append(raw)
        if len(cuts) < 2:
            continue
        out.append(Neck(part, tuple(cuts), tuple(mids), length,
                        part.area / length if length > 0.0 else 0.0,
                        part.area, len(touching), curved))
    return out


def _separates(face: Polygon, part: Polygon, lobes: list[Polygon],
               rules: Rules) -> bool:
    """Does removing ``part`` cut two of its ``lobes`` apart?

    THE FRINGE IS THE TRAP, and it is measured (HECA, 2026-09-14 arm 1).
    ``NARROW`` is not only the necks: it is also the shallow rim of every
    wide body — a point ON the boundary of a 200 m apron has an inscribed
    disc of radius 0 and is narrow by this reading.  That rim is ONE
    connected component running all the way round the face, so it touches
    EVERY lobe and reads as an N-mouth "neck": at HECA it cut a 253,634 m²
    apron (``pav1``) into pieces on a 8.3 m-wide, 19-mouth fringe.

    A NECK SEPARATES; a fringe does not.  So the component is a neck only
    where the face MINUS it falls into parts that hold different lobes —
    the owner's own picture of the rule ("the taxiway LEAVES the apron at
    a mouth ... until it widens into ANOTHER apron")."""
    rest = face.difference(part.buffer(rules.cells.snap_grid_m))
    parts = [p for p in polygon_parts(rest) if p.area > 0.0]
    if len(parts) < 2:
        return False
    seen: set[int] = set()
    for lobe in lobes:
        home = -1
        for k, p in enumerate(parts):
            if p.intersection(lobe).area > 0.5 * lobe.area:
                home = k
                break
        if home >= 0:
            seen.add(home)
    return len(seen) >= 2


def _mouth_chord(mouth, face: Polygon, rules: Rules):
    """The SHORTEST CHORD across the pavement at a mouth (§43 (2)): the
    straight segment between the mouth curve's two extreme ends, extended
    by ``cells.on_tol_m`` at each end so ``polygonize`` cuts through the
    face boundary.  Falls back to the mouth CURVE where the straight
    chord would leave the pavement (second return value ``True``)."""
    parts = [g for g in (mouth.geoms if hasattr(mouth, "geoms") else [mouth])
             if getattr(g, "geom_type", "") == "LineString" and g.length > 0.0]
    if not parts:
        return None, None, False
    ends = [p for g in parts for p in (g.coords[0], g.coords[-1])]
    a, b = max(((p, q) for i, p in enumerate(ends) for q in ends[i + 1:]),
               key=lambda pq: (pq[0][0] - pq[1][0]) ** 2
               + (pq[0][1] - pq[1][1]) ** 2, default=(None, None))
    if a is None or (a[0] == b[0] and a[1] == b[1]):
        g = MultiLineString(parts)
        e = g.bounds
        return _extend(g, rules), ((e[0], e[1]), (e[2], e[3])), True
    chord = LineString([a, b])
    ends = ((a[0], a[1]), (b[0], b[1]))
    if chord.length > 0.0 and \
            chord.difference(face.buffer(rules.cells.snap_grid_m)).length > 0.0:
        return _extend(MultiLineString(parts), rules), ends, True
    return _extend(chord, rules), ends, False


def _extend(line, rules: Rules):
    """Push each open end of ``line`` out by ``cells.on_tol_m`` so the cut
    crosses the face boundary instead of stopping on it."""
    tol = rules.cells.on_tol_m
    parts = [g for g in (line.geoms if hasattr(line, "geoms") else [line])]
    out = []
    for g in parts:
        cs = list(g.coords)
        if len(cs) < 2:
            continue
        cs[0] = _push(cs[1], cs[0], tol)
        cs[-1] = _push(cs[-2], cs[-1], tol)
        out.append(LineString(cs))
    if not out:
        return None
    return out[0] if len(out) == 1 else MultiLineString(out)


def _push(frm, to, d: float):
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    n = (dx * dx + dy * dy) ** 0.5
    if n <= 0.0:
        return to
    return (to[0] + dx / n * d, to[1] + dy / n * d)


def split_at_necks(face: Polygon, necks: list[Neck], rules: Rules
                   ) -> list[tuple[Polygon, bool]]:
    """``face`` cut at every mouth of ``necks``: the pieces, each with
    whether it is a NECK piece (taxi family by §43 (1)) or pavement
    beyond it (a NEW apron cell by §43 (1)).  The cut is polygonized on
    the slice's own grid, exactly as ``roles._slice`` cuts the region."""
    cuts = [c for n in necks for c in (n.cuts or ())]
    if not cuts:
        return [(face, False)]
    grid = rules.cells.snap_grid_m
    lines = [face.exterior, *face.interiors]
    noded = shapely.unary_union(unary_union([LineString(r.coords) for r in lines]
                                            + list(cuts)), grid_size=grid)
    prep = shapely.prepared.prep(shapely.set_precision(face, grid))
    neck_u = unary_union([n.polygon for n in necks])
    out: list[tuple[Polygon, bool]] = []
    for poly in polygon_parts(shapely.polygonize([noded])):
        if poly.area < rules.cells.min_area_m2:
            continue
        if not prep.contains(poly.representative_point()):
            continue
        inter = poly.intersection(neck_u).area
        out.append((poly, inter >= 0.5 * poly.area))
    if len(out) < 2:
        return [(face, False)]         # the cut did not take: leave it whole
    return out
