"""§16g (10) (2) THE CLUSTER'S PAD POLYGON — the ONE derivation, and it
lives in ``geom`` because two layers that may not import each other need
it (owner RULINGS 2026-09-11x (4), the layering twin):

* ``classify/evidence._pads`` MINTS the pad from it;
* ``constraints/cluster_pad`` reads it to say which emitted face a
  cluster IS, and to census ``pad_cluster_mismatch`` against it.

A second spelling of "the cluster's footprint" is the census-wrapper
defect in geometry (CLAUDE.md, RULINGS 2026-08-30l): the two would drift
and the mismatch family would then be measuring the drift.

Only shape here: the rings, a transformer and two tolerances in, the
polygons out.  No law value is read — the caller passes the law's own.
"""
from __future__ import annotations

import math as _math
import collections
import typing as _t

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from .outline_pin import Frontage
from .rotated_rect import rotated_rectangle

__all__ = ["cluster_outlines", "OUTLINE_SIMPLIFY_M", "airside_vertex_snap",
           "simplified_outline", "CLOSE_QUAD_SEGS",
           "AirsideRim", "ON_BOUNDARY_EPS_M", "deck_shades",
           "osm_building_evidence", "OSM_BUILDING_SOURCE",
           "CACHE_VOUCHED_SOURCE", "CLUSTER_EVIDENCE_SOURCES",
           "cluster_building_evidence"]

#: How close a pad coordinate must be to the airside boundary to count as
#: lying ON it.  The clip's own output lies on it to float precision; this
#: is a float-noise band, NOT a weld tolerance.
ON_BOUNDARY_EPS_M = 1e-6

#: §16g (10) (2) (a): how far a CLOSED cluster outline is simplified back
#: after the dilate/erode — the emitter's own outline tolerance
#: (``placement_family``'s ``OUTLINE_SIMPLIFY_M``).  A pad the planar map
#: must carry is a real vertex budget.
OUTLINE_SIMPLIFY_M = 0.05

#: RULE 6 (lane ``hecabodies``, issues #7 / #8): a cluster PIECE whose mean
#: width — ``2 * area / perimeter``, exact for a strip — is under this is a
#: WALL LINE, not ground a building stands on, and mints no pad.  With the
#: footprint rings bounded (``airport/contact.plan_hull``), HECA's retaining
#: wall along the service road (``Hangar_Tower/metal_strip_2.obj``, 3.1 m
#: tall, ~0.3 m thick) is a ~0.7 m strip of ``building13``'s cluster; minted
#: as a pad it cut a 1 m slot 3.5 m deep into ground the owner says "must be
#: free to terrace".  The wall's body still seats with its unit (§16g's own
#: derivation, not this one).
THIN_PIECE_WIDTH_M = 2.0


def _bridge(u, bridges, to_xy, gap_m: float):
    """§16g (10) (2) AMENDED (issue #73, spec-author rule to lane
    ``courtyards``): A POST STILL CHAINS, SO THE UNIT IS ONE.  ``u`` is a
    cluster's closed outline; where it has fallen into PIECES, a post /
    flat-line ring of ``bridges`` (``PlanCluster.bridges``, ``(lat,
    lon)``) that has a plan point within ``gap_m`` of TWO pieces at once
    closes the gap between those two: the part of the ring within
    ``gap_m`` of both (the post IN the gap) and the facing patches of the
    two pieces within ``gap_m`` of it, hulled.  The ring itself is never
    drawn — a flat line that merely runs from one piece to another
    across open ground draws no outline (HECA ``Plastic.obj`` strips
    between pieces 2.72 m apart redrew the lace: holes 32 -> 84).
    Returns ``(outline, joins)``."""
    pieces = _parts(u)
    if len(pieces) < 2 or not bridges or gap_m <= 0.0:
        return u, 0
    tree = STRtree(pieces)
    grown: dict[int, _t.Any] = {}

    def grow(k):
        if k not in grown:
            grown[k] = pieces[k].buffer(gap_m, join_style=2)
        return grown[k]

    add: list = []
    joins = 0
    for r in bridges:
        if len(r) < 3:
            continue
        b = Polygon([to_xy(lo, la) for la, lo in r])
        if not b.is_valid:
            b = b.buffer(0.0)
        if b.is_empty:
            continue
        near = sorted(int(k) for k in tree.query(b, predicate="dwithin",
                                                  distance=gap_m))
        for x in range(len(near)):
            for y in range(x + 1, len(near)):
                i, j = near[x], near[y]
                gap = b.intersection(grow(i)).intersection(grow(j))
                if gap.is_empty or gap.area <= 0.0:
                    continue
                reach = gap.buffer(gap_m, join_style=2)
                con = unary_union([gap, pieces[i].intersection(reach),
                                   pieces[j].intersection(reach)]).convex_hull
                add.append(con)
                joins += 1
    if not add:
        return u, 0
    g = unary_union([u] + add)
    if not g.is_valid:
        g = g.buffer(0.0)
    return g, joins


def _parts(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, MultiPolygon):
        return [q for q in g.geoms if isinstance(q, Polygon) and q.area > 0.0]
    return [g] if isinstance(g, Polygon) and g.area > 0.0 else []


#: §56 (1) 1: the arc resolution of the round close (segments per quarter
#: circle) — the probe's own; the arc vertices it adds are removed by the
#: straightening, so it buys a true closing, never a vertex budget.
CLOSE_QUAD_SEGS = 8


def simplified_outline(poly, close_m: float, chord_m: float,
                       hole_min_m2: float, front: "Frontage | None" = None):
    """§56 (1) RULE 2b, THE SIMPLIFIED BUILDING OUTLINE (owner RULINGS
    2026-10-07a (6), 07b (4); issue #452): "just the outline of the
    building with straight chords that include jetways and small
    protuberances while following the general outline of the building".
    ONE pure function on one polygon in the planar frame — no DEM, no
    neighbour, no law read (the caller passes the law's three values) —
    so its output is the same at any worker count.

    1. CLOSE: ``buffer(+close_m).buffer(-close_m)`` with ROUND joins — a
       true morphological closing, so it contains its input and fills
       every re-entrant whose mouth is narrower than ``2 * close_m``; a
       wider bay is a real concavity and stays.  Mitred joins were probed
       and REFUTED (they drop sliver pieces off thin wings).
    2. STRAIGHTEN: Douglas-Peucker, topology-preserving, at ``chord_m``
       (removes the arc vertices of 1 as well as the crenelations).
    3. FILL THE LIGHT WELLS: every hole under ``hole_min_m2`` goes; a
       courtyard at or over it stays a hole.

    Close, then straighten, then fill.  There is NO opening step: an
    opening drops thin protuberances (a canopy, a jetway root), which the
    owner asked for INSIDE the outline (probe arm V8, refuted).  ``0``
    disarms each step (the measurement arm, never a shipped value).

    ``front`` (§56 (11) R-W, THE FRONTAGE IS NOT SIMPLIFIED): the airside
    ground beside this outline (:class:`geom.outline_pin.Frontage`).  Where
    the outline stands on it, it stays as rule 2 drew it — no fill, no
    dropped vertex, no new chord, no filled well; the chords are for the
    groundside and road sides.  ``None`` simplifies the whole ring."""
    g = poly
    if g is None or g.is_empty:
        return g
    if front is not None:
        return _simplified_off_frontage(g, close_m, chord_m, hole_min_m2, front)
    if close_m > 0.0:
        # the input is unioned back: the arcs are inscribed polygons, so
        # the buffered close chamfers every convex corner by the arc's
        # sagitta (1.3 cm at 3 m) and the straightening would then keep
        # the chamfer, not the corner — the union makes "contains its
        # input" exact, as the closing it stands for does
        # (and ``simplify(0)`` drops the chamfer's now-collinear vertices,
        # so no ring STARTS on one — Douglas-Peucker always keeps a ring's
        # first vertex, and would drop the true corner beside it)
        g = unary_union([g, g.buffer(close_m, join_style=1,
                                     quad_segs=CLOSE_QUAD_SEGS).buffer(
            -close_m, join_style=1, quad_segs=CLOSE_QUAD_SEGS)]).simplify(0.0)
        if not g.is_valid:
            g = g.buffer(0.0)
    if chord_m > 0.0:
        g = g.simplify(chord_m, preserve_topology=True)
        if not g.is_valid:
            g = g.buffer(0.0)
    if hole_min_m2 > 0.0:
        kept = [Polygon(p.exterior, [h for h in p.interiors
                                     if Polygon(h).area >= hole_min_m2])
                for p in _parts(g)]
        g = unary_union(kept) if kept else g
        if not g.is_valid:
            g = g.buffer(0.0)
    return g


def _simplified_off_frontage(g, close_m: float, chord_m: float,
                             hole_min_m2: float, front: Frontage):
    """Rule 2b's three steps with the airside frontage PINNED (§56 (11)
    R-W) — the same close, chord and well fill, each asked of ``front``."""
    if close_m > 0.0:
        g = front.straighten(front.closing(g, g.buffer(
            close_m, join_style=1, quad_segs=CLOSE_QUAD_SEGS).buffer(
            -close_m, join_style=1, quad_segs=CLOSE_QUAD_SEGS)), 0.0)
        if not g.is_valid:
            g = g.buffer(0.0)
    if chord_m > 0.0:
        g = front.straighten(g, chord_m)
        if not g.is_valid:
            g = g.buffer(0.0)
    if hole_min_m2 > 0.0:
        kept = [Polygon(p.exterior, front.wells(p, hole_min_m2))
                for p in _parts(g)]
        g = unary_union(kept) if kept else g
        if not g.is_valid:
            g = g.buffer(0.0)
    return g


def _outline_vertices(g) -> int:
    """Ring vertices (exterior + holes, closing point not counted)."""
    return sum(len(p.exterior.coords) - 1
               + sum(len(h.coords) - 1 for h in p.interiors)
               for p in _parts(g))


def _outline_growth(piece, pid: str, was: list, frm: list[str], u_in,
                    close_m: float) -> dict[str, float]:
    """§56 (1) 10 THE GROWTH IS NAMED: the m² rule 2b added to the piece
    ``pid`` over its same-id pre-2b piece, split into the five lawful
    classes (they sum to the added area) — ``join`` (over the other
    pre-2b pieces it absorbed), ``thin_kept`` (inside the pre-2b outline
    ``u_in`` but in no pre-2b piece: a remainder rule 6 would have
    dropped), ``well`` (a filled light well), ``close`` (the closing's
    fill) and ``chord`` (the straightening's residue)."""
    by = dict(was)
    base = by.get(pid)
    if base is None and frm:
        base = max((by[q] for q in frm), key=lambda g: g.area)
    added = piece if base is None else piece.difference(base)
    out = dict.fromkeys(("join", "well", "close", "chord", "thin_kept"), 0.0)
    if added.is_empty:
        return out
    others = [by[q] for q in frm if by[q] is not base]
    if others:
        ou = unary_union(others)
        out["join"] = added.intersection(ou).area
        added = added.difference(ou)
    out["thin_kept"] = added.intersection(u_in).area
    added = added.difference(u_in)
    wells = [Polygon(h) for g in _parts(u_in) for h in g.interiors]
    if wells and not added.is_empty:
        wu = unary_union(wells)
        out["well"] = added.intersection(wu).area
        added = added.difference(wu)
    if close_m > 0.0 and not added.is_empty:
        fill = u_in.buffer(close_m).buffer(-close_m).difference(u_in)
        out["close"] = added.intersection(fill).area
        added = added.difference(fill)
    out["chord"] = added.area
    return {k: round(v, 1) for k, v in out.items()}


def deck_shades(partition: _t.Any,
                to_xy: _t.Callable[[float, float], tuple[float, float]]):
    """THE WELDED DECKS' SHADES (issue #14; ``welded-deck-spec.md`` §2 (1))
    — the ONE reading both pad readers pass to :func:`cluster_outlines`
    (``classify/evidence._cluster_pads`` MINTS, ``constraints/cluster_pad
    .cluster_polys`` CENSUSES), so mint and ``pad_cluster_mismatch`` cannot
    disagree about where the ground under a deck is.

    The union, in the planar frame's metres, of every
    ``Member.deck_shade_ring`` of ``partition`` (the load-time pack
    partition, ``Airport.partition``; ``airport/deck_signature
    .welded_deck`` stamped them), or ``None`` where there is none — a
    partition written before plan version 10 carries none and every
    outline stands as it did.  Duck-typed on the partition: ``geom``
    imports nothing of v2.  A handful of deck rings per airport: no memo."""
    if partition is None:
        return None
    ps: list[Polygon] = []
    for u in (getattr(partition, "units", ()) or ()):
        for m in u.members:
            for poly in (getattr(m, "deck_shade_ring", None) or ()):
                if not poly or len(poly[0]) < 3:
                    continue
                g = Polygon([to_xy(lo, la) for la, lo in poly[0]],
                            [[to_xy(lo, la) for la, lo in h] for h in poly[1:]
                             if len(h) >= 3])
                if not g.is_valid:
                    g = g.buffer(0.0)
                ps.extend(_parts(g))
    got = unary_union(ps) if ps else None
    return None if got is None or got.is_empty else got


#: v1's EVIDENCE SOURCE (a) population: which ``model.airport.Building``
#: source spelling is an OSM footprint.  ``airport/load.py`` :339 writes
#: exactly ``"osm"`` for a closed OSM way passing its ``_is_building``
#: predicate — ``building=*`` (not no/none), ``building:part``, or
#: ``aeroway`` in terminal / hangar / tower — which is the SAME vocabulary
#: v1's ``terminals._extract_osm_building_evidence`` collects
#: (``_BUILDING_EVIDENCE_AEROWAY_TAGS`` + any ``building`` tag).  A source
#: LITERAL, so ``blast.py`` reports it; the other two spellings are
#: ``dsf:fac:*`` and ``dsf:object:*``, which are the PACK's own geometry
#: and therefore not independent evidence of a building.
OSM_BUILDING_SOURCE = "osm"

#: v1's OWN VERTICAL VERDICT on the same pack geometry (lane
#: ``padgates101b``, issue #101): the footprint cache's
#: ``OBJECT_BUILDING_ROLE`` ring, carried verbatim in ``Building.source``
#: (``airport/load.py`` writes ``dsf:object:<role>``).  The CLUSTER half
#: of rule 10 reads it beside OSM, because v1 measured its vertical test
#: on ITS weld — no floor split, no walled gate, no connector cut — and a
#: v2 cluster is a smaller structure that can read under the evidence
#: height where v1's read over it.  MEASURED HECA (capture at this
#: branch): ``unit:43#765`` (9,131 m2, T3_26/T3_27, tallest 5.67 m) and
#: ``unit:41#73`` (3,413 m2) stand on 6,711 / 3,087 m2 of rings v1
#: VOUCHED, with no OSM building within 195 m.  Without this the port
#: refuses ground v1 itself padded, which is not the gate the owner read.
#: A role LITERAL crossing the v1/v2 boundary (``blast.py`` reports it).
CACHE_VOUCHED_SOURCE = "dsf:object:object"

#: The evidence sources the CLUSTER half reads (OSM first, so the
#: counter names v1's source (a) where both hold).  The FALLBACK half
#: reads OSM alone: there the ring under test IS a cache ring, and its
#: own role already is the cache's verdict.
CLUSTER_EVIDENCE_SOURCES = (OSM_BUILDING_SOURCE, CACHE_VOUCHED_SOURCE)


def osm_building_evidence(buildings: _t.Iterable[_t.Any],
                          sources: _t.Sequence[str] = (OSM_BUILDING_SOURCE,)):
    """``outline -> bool``: does an OSM building footprint intersect it?
    v1's EVIDENCE SOURCE (a) (R18-2, owner ruling 2026-08-11b;
    ``pipeline._osm_building_evidence_predicate``), ported.

    ONE derivation, and that is the point: the MINT
    (``classify/evidence._cluster_pads``) and the CENSUS
    (``constraints/cluster_pad.cluster_polys``) both call THIS with the
    same ``Airport.buildings``, so neither can admit a cluster the other
    refuses and ``pad_cluster_mismatch`` cannot end up measuring the
    drift.  ``None`` where the airport has no mapped building at all,
    which is the honest answer — v1's clause: no OSM in hand is NOT
    evidence of absence, and the caller then rests on the vertical test
    alone rather than refusing everything.

    ``buildings`` are duck-typed (``.source``, ``.outer``, ``.holes``) and
    ALREADY in the planar frame's metres (``airport/load.py`` projects
    every ring at load), which is the frame ``cluster_outlines`` works
    in — the same discipline :func:`deck_shades` keeps for the partition.

    ``sources`` names the ``Building.source`` spellings that count, in
    priority order — OSM alone by default (the fallback half), and
    :data:`CLUSTER_EVIDENCE_SOURCES` at the cluster half's call sites.
    The predicate returns the SOURCE that vouched (``""`` for none), so
    the gate can count each evidence source under its own name.
    """
    polys: list[Polygon] = []
    srcs: list[str] = []
    rank = {str(k): i for i, k in enumerate(sources)}
    for b in buildings or ():
        src = str(getattr(b, "source", ""))
        if src not in rank:
            continue
        ring = tuple(getattr(b, "outer", ()) or ())
        if len(ring) < 3:
            continue
        g = Polygon(ring, [h for h in (getattr(b, "holes", ()) or ())
                           if len(h) >= 3])
        if not g.is_valid:
            g = g.buffer(0.0)
        got = _parts(g)
        polys.extend(got)
        srcs.extend([src] * len(got))
    if not polys:
        return None
    tree = STRtree(polys)

    def _has_evidence(outline) -> str:
        best = ""
        try:
            if outline is None or outline.is_empty:
                return ""
            for k in tree.query(outline):
                if polys[int(k)].intersects(outline):
                    src = srcs[int(k)]
                    if not best or rank[src] < rank[best]:
                        best = src
                    if rank[best] == 0:
                        break
        except Exception:
            return ""
        return best

    return _has_evidence


def cluster_building_evidence(buildings: _t.Iterable[_t.Any]):
    """THE CLUSTER HALF's evidence predicate — :func:`osm_building_evidence`
    over :data:`CLUSTER_EVIDENCE_SOURCES`.  ONE spelling, so the mint, the
    census and the tools cannot each name the sources differently."""
    return osm_building_evidence(buildings, CLUSTER_EVIDENCE_SOURCES)


def _vertical_evidence(ev, admission) -> tuple[bool, float]:
    """The VERTICAL half of R18-2, re-run off the stamped measurement at
    the GATE's own thresholds — v1
    ``object_footprints.has_vertical_structure_evidence``, which
    ``geom.pad_evidence`` holds as THE definition and this calls.

    It is re-run rather than stamped as a verdict so the law's two numbers
    stay the gate's (``law.tables.pad_admission`` — ONE reading for the
    mint and the census) while only the MEASUREMENT travels on the
    cluster: a cached cluster can then never carry a verdict taken at a
    threshold the law no longer reads."""
    from .pad_evidence import has_vertical_structure_evidence
    return has_vertical_structure_evidence(
        tuple(getattr(ev, "rows", ()) or ()),
        float(getattr(ev, "hull_area_m2", 0.0) or 0.0),
        float(admission.evidence_min_height_m),
        float(admission.evidence_min_coverage),
        bool(getattr(ev, "evidence_name_vouched", False)))


def _rect(g) -> tuple[float, float]:
    """``(length_m, width_m)`` of ``g``'s minimum rotated rectangle, long
    side first — what a rule-9/10 refusal row carries for issue #229."""
    try:
        box = rotated_rectangle(g)
        xy = list(box.exterior.coords)[:-1] if box.geom_type == "Polygon" else []
        if len(xy) < 4:
            return 0.0, 0.0
        sides = sorted(_math.dist(xy[i], xy[(i + 1) % len(xy)])
                       for i in range(len(xy)))
        return float(sides[-1]), float(sides[0])
    except Exception:
        return 0.0, 0.0


def _refuse(refused, counts, key: str, cluster, gate: str, value: float,
            outline=None, ev=None) -> None:
    """Record ONE rule-9/10 refusal (owner RULINGS 2026-10-02v (3): "record
    each refusal with ref + gate + measured value ... so the session can
    list them") and bump its counter.

    The length/width come from the refused OUTLINE where one exists, else
    from the measured hull — issue #229 reads them to decide whether the
    footprint REPRESENTS A ROAD, which is NOT this function's business."""
    counts[key] = counts.get(key, 0) + 1
    if refused is None:
        return
    if outline is not None and not outline.is_empty:
        length_m, width_m = _rect(outline)
        area_m2 = float(outline.area)
    else:
        length_m = float(getattr(ev, "length_m", 0.0) or 0.0)
        width_m = float(getattr(ev, "width_m", 0.0) or 0.0)
        area_m2 = float(getattr(ev, "hull_area_m2", 0.0) or 0.0)
    refused.append({
        "id": str(getattr(cluster, "id", "")),
        "gate": gate,
        "value": round(float(value), 6),
        "area_m2": round(area_m2, 1),
        "hull_area_m2": round(float(getattr(ev, "hull_area_m2", 0.0) or 0.0), 1),
        "length_m": round(length_m, 2),
        "width_m": round(width_m, 2),
        "members": tuple(getattr(cluster, "members", ()) or ())[:8],
    })


def _outline_pieces(u, shades, airside, taken, thin_m: float, counts) -> list:
    """Rules 8, 4, 3 and 6 on ONE closed outline: the deck shades and the
    airside leave it, the ground a lower cluster already took leaves it,
    its thin pieces drop — the pieces left, in the ``(bounds y, bounds
    x)`` order the ``/k`` ids are spelt in.  ``[]`` when nothing is left
    (the reason is counted)."""
    if shades is not None and not shades.is_empty and u.intersects(shades):
        # rule 8: the welded deck's shade leaves the outline
        u = u.difference(shades)
        if not u.is_valid:
            u = u.buffer(0.0)
        if u.is_empty or u.area <= 0.0:
            counts["under_deck"] += 1
            return []
        counts["deck_trimmed"] += 1
    if airside is not None and not airside.is_empty and u.intersects(airside):
        before = u.area
        u = u.difference(airside)
        if u.is_empty or u.area <= 0.0:
            counts["on_airside"] += 1        # it seats on the pavement
            return []
        if u.area < before:
            counts["clipped"] += 1
        if not u.is_valid:
            u = u.buffer(0.0)
    hit = [g for g in taken if g.intersects(u)]
    if hit:
        u = u.difference(unary_union(hit))
    pieces = _parts(u)
    if not pieces:
        counts["over_another"] += 1
        return []
    if thin_m > 0.0:
        wide = [g for g in pieces
                if 2.0 * g.area >= thin_m * max(g.length, 1e-9)]
        counts["thin_dropped"] += len(pieces) - len(wide)
        pieces = wide
    pieces.sort(key=lambda g: (round(g.bounds[1], 3), round(g.bounds[0], 3)))
    return pieces


def _piece_ids(cid: str, pieces: _t.Sequence) -> list[str]:
    """A cluster's piece ids: its own id for one piece, ``id/k`` else."""
    return [cid if len(pieces) == 1 else f"{cid}/{k}"
            for k in range(len(pieces))]


def cluster_outlines(clusters: _t.Sequence[_t.Any],
                     to_xy: _t.Callable[[float, float], tuple[float, float]],
                     touch_m: float,
                     simplify_m: float = OUTLINE_SIMPLIFY_M,
                     airside=None,
                     walled_only: bool = False,
                     min_m2: float = 0.0,
                     thin_m: float = THIN_PIECE_WIDTH_M,
                     shades=None,
                     bridge_m: float = 0.0,
                     admission=None,
                     osm_evidence=None,
                     refused=None,
                     outline=None,
                     stats: "dict[str, dict] | None" = None,
                     frontage=None,
                     ) -> "tuple[list[tuple[str, _t.Any, Polygon]], dict[str, int]]":
    """``([(pad id, cluster, its pad polygon), ...], counts)`` in the
    planar frame's metres — one entry per PIECE, and each PIECE IS ITS
    OWN CLUSTER (§16g (10) (5)): a cluster whose outline falls into more
    than one piece is SPLIT at the pieces and each carries the id
    ``<cluster id>/<k>``.  A cluster in one piece keeps its own id, so
    nothing renames at an airport where the rule does not bite.

    THE RULES, in order, each MEASURED on HECA's closing arm:

    1. A cluster with no ``rings`` (a plan written before §16g (7) (1)'s
       field) yields NOTHING — a part-BOX union is not a footprint, and
       13ci measured what pricing one costs (KCLT's `building91`, 65.81 m
       outside its terminal, 2,406 taxi vertices moved).  Counted as
       ``no_rings``.
    2. THE OUTLINE IS CLOSED AT THE TOUCH TOLERANCE.  The bodies chained
       because their footprints came within ``touch_m``; their SIMPLIFIED
       rings need not overlap, and 107 of HECA's 2,485 clusters came out
       disjoint in plan, the largest in TEN pieces over 259,443 m2.  A
       cluster in ten pieces is not one pad, so the union is dilated and
       eroded by ``touch_m`` (mitred, so the vertex count does not
       explode) and simplified back.  A cluster still in pieces after
       that really is apart in plan; each piece stands as its own pad and
       the surplus is counted (``still_in_pieces``).
    3. THE GROUND FLOOR OWNS THE GROUND.  §16g (10) (1) splits a touching
       chain at a floor, and at HECA **519 pairs** of the resulting
       clusters OVERLAP IN PLAN — because a building's floors stack over
       ONE footprint and two regions cannot occupy the same ground.  Read
       as two pads that is 369 ``pad_cluster_mismatch`` rows; read as
       what it is, it is one building whose upper floors stand ON the
       lower one.  So the clusters are offered the ground LOWEST FLOOR
       FIRST and each one's overlap with what is already taken is
       SUBTRACTED; a cluster left with nothing mints no pad and is
       counted (``over_another``) — it stands on the pad beneath it,
       which is what §13 / §16a already say of an elevated body and its
       carrier.

    4. A DERIVED PAD NEVER TAKES AIRSIDE GROUND (§16g (10) (5), owner
       RULINGS 2026-09-14ah).  ``airside`` — the union of every airside
       face (the runway family, the taxi family and the apron) — is
       SUBTRACTED from every outline, and a cluster whose outline lies
       wholly on airside pavement gets NO pad at all (counted
       ``on_airside``): its bodies seat on the pavement.  MEASURED
       without it (lane round 2): 502,561 m2 of new hard flat pad, of
       which 94,795 m2 came out of the apron, moved 13,637 of 21,534
       airside vertices, the runway itself 1,110 of 3,426 and worst
       4.38 m.  Airside is king, and §30 (4)'s own owner clause is "as
       long as it remains feasible with grade laws and taxiways".

    5. LEAVES GET NO PAD (§16g (10) (7), owner RULINGS 2026-09-14aj).  A
       derived pad is minted for a WALLED cluster only — one holding a
       body whose solid height reaches ``chain_min_height_m`` — and only
       where its footprint union reaches ``min_m2``
       (``cluster_pad_min_m2``).  A LEAF (a slab, a plate, a deck, a
       canopy, a road) seats on its own ground and mints nothing; a
       walled cluster under the threshold keeps the footprint cache's
       pad, which is `cluster_pad_min_m2`'s one remaining job (§16g (9)).
       MEASURED at HECA: of 1,380,739 m2 of outline, **359,152 m2 in
       1,518 pads are LEAVES** and 175,708 m2 in 821 more are walled but
       under the threshold — together 39 % of the new pad area that sat
       beside the apron.  Counted ``leaf_dropped`` / ``under_min_m2``.

    6. A WALL LINE GETS NO PAD (lane ``hecabodies``, #7 / #8): a piece
       whose mean width ``2 A / P`` is under ``thin_m``
       (:data:`THIN_PIECE_WIDTH_M`) is a wall or kerb seen from above and
       mints nothing (counted ``thin_dropped``); the ground either side of
       it terraces as the owner reads it.

    8. THE GROUND UNDER A WELDED DECK IS NEVER A BUILDING'S PAD (issue
       #14; ``welded-deck-spec.md`` §2 (1)).  ``shades`` — the union of
       every deck SHADE of the plan (:func:`deck_shades`) — is SUBTRACTED
       from every outline AFTER rule 2's close (so the dilate/erode does
       not refill it) and before rules 3 and 4.  The outline is the union
       of every part ring of every walled body, elevated storeys included
       (14x), so a terminal road deck welded to the building was read as
       the building's ground: OTHH ``TerminalRoads_01_001`` minted
       ``building7`` (5,659 of 6,042 m2) and 4,921 m2 of ``building4``,
       of which 1,151 m2 has anything standing on the ground.  A cluster
       wholly under a shade mints nothing (``under_deck``); one the shade
       cuts is ``deck_trimmed``, and the pieces it leaves are rule 2's.

    2b. THE SIMPLIFIED BUILDING OUTLINE (spec §56 (1), owner RULINGS
       2026-10-07a (6) / 07b (4), issue #452): right after 2 and 2a, and
       before 10, 8, 4, 3 and 6, the outline is closed (round, at
       ``outline.close_m``), straightened (Douglas-Peucker at
       ``outline.chord_m``) and its light wells under
       ``outline.hole_min_m2`` filled — :func:`simplified_outline`.
       Counted ``outline_simplified``, with the ring vertices in and out
       (``outline_vertices_in`` / ``_out``).  THE AIRSIDE FRONTAGE IS
       PINNED through it (§56 (11) R-W): ``frontage`` is the airside
       ground, ``outline.pin_m`` the distance — an outline standing on it
       keeps rule 2's ring there (``outline_frontage`` clusters,
       ``outline_fills_refused``, ``outline_vertices_pinned``).
       ``frontage=None`` simplifies every ring whole.

    2a. A POST STILL CHAINS, SO THE UNIT IS ONE (issue #73, lane
       ``courtyards``).  Posts and flat lines draw no outline
       (``placement_family.draws_outline``), so a cluster whose pieces
       touched only through one falls apart at rule 2.  Each such ring
       (``PlanCluster.bridges``) with a plan point within ``bridge_m`` of
       two pieces closes the outline across that gap, and only there
       (:func:`_bridge`); counted ``post_bridged``.  MEASURED OTHH (sheetchain capture): cluster
       pads 61 (main) -> 72 without it -> 69 with it; HECA 79 -> 80 -> 80.

    9. A SLAB/MAST WELD GETS NO PAD — v1's TALL-BASE FILL, ported
       (issue #101; owner RULINGS 2026-10-02v (3), verbatim: *"We
       definitely don't want a flat pad under the whole train at HECA"*).
       A building's TALL member covers its OWN footprint; a 0.3 m plate
       welded to a 28 m floodlight mast defeats both the height gate and
       the base-fill gate and is still street furniture on a slab.  The
       cluster's ``evidence.tall_base_fill`` (``geom.pad_evidence``, the
       ONE measurement, stamped at ``placement_family.plan_clusters``)
       under ``admission.min_tall_base_fill`` mints NOTHING — counted
       ``no_tall_base``.  A real terminal reads ~1.0, the weld ~0.002;
       the floor is v1's 0.002 and is DELIBERATELY LOW, because HECA's
       thin-wall terminal shells read ~0.002-0.01 and raising it toward
       0.05 culled ~140 of them (v1 ``config.py`` :3734-3758).  A
       NAME-VOUCHED cluster (v1's shipped wide path match) is exempt, as
       in v1.

    10. NO BUILDING, NO PAD — v1's BUILDING EVIDENCE (R18-2, owner ruling
       2026-08-11b), ported.  A footprint mints a pad only with evidence
       a BUILDING is there, never on solid reach alone: EITHER the
       VERTICAL test on the cluster's own solid geometry (a component
       standing ``admission.evidence_min_height_m`` above grade on its
       own, the tall members covering
       ``admission.evidence_min_coverage`` of the hull — v1's
       ``has_vertical_structure_evidence``, re-read here off the stamped
       measurement) OR ``osm_evidence(outline)``, an intersecting OSM
       building / terminal / hangar footprint.  Neither ⇒ the outline is
       an apron slab, a barrier or a vehicle hull and mints nothing
       (counted ``no_building_evidence``).  It closed four HECA pads
       11-18 m BELOW their own ground.  ``osm_evidence=None`` means the
       caller has no OSM in hand, which is NOT evidence of absence — the
       gate then rests on the vertical test alone (v1's own clause).

    THE REFUSAL IS RECORDED, NEVER SILENT (owner RULINGS 2026-10-02v
    (3)).  ``refused``, when a list, collects one row per rule-9/10
    refusal — ``{"id", "gate", "value", "area_m2", "length_m",
    "width_m", "members"}`` — so the build and the sidecar can LIST what
    each gate caught.  ``length_m``/``width_m`` are the footprint hull's
    minimum rotated rectangle and are carried for issue #229 (a refused
    pack object that REPRESENTS A ROAD grades as a road), which this
    function does not implement.

    A cluster carrying NO measurement (``evidence`` ``None`` — a twin
    that does not ask, a cluster cached before the field) is refused by
    NEITHER new rule and is counted ``unmeasured``: an unmeasured
    population must never be read as a refused one, the same discipline
    ``plan_clusters`` keeps for a plan with no solid heights.

    ``stats``, when a dict, takes one row per emitted piece under rule 2b
    (§56 (1) 9) — ``outline_vertices`` (of the simplified outline it was
    cut from, before the airside clip), ``outline_simplified_from`` (the
    same count before 2b) and ``outline_joined_from`` (the ids the pieces
    it covers had before 2b, when 2b JOINED or renamed them; else empty).

    ``touch_m <= 0`` disarms the close (rule 2); ``bridge_m <= 0``
    disarms (2a); ``outline=None`` (or its three values 0) disarms (2b);
    ``airside=None``
    disarms the clip (rule 4); ``walled_only=False`` and ``min_m2=0``
    disarm (7); ``thin_m <= 0`` disarms (6); ``shades=None`` disarms (8);
    ``admission=None`` disarms (9) and (10), as does
    ``min_tall_base_fill = 0`` / ``building_evidence = false`` in it.
    """
    counts = {"clusters": len(clusters), "no_rings": 0, "over_another": 0,
              "still_in_pieces": 0, "on_airside": 0, "clipped": 0,
              "leaf_dropped": 0, "under_min_m2": 0, "thin_dropped": 0,
              "pads": 0, "under_deck": 0, "deck_trimmed": 0,
              "post_bridged": 0,
              # §56 (1) rule 2b
              "outline_simplified": 0, "outline_vertices_in": 0,
              "outline_vertices_out": 0,
              # §56 (11) R-W: the pinned airside frontage
              "outline_frontage": 0, "outline_fills_refused": 0,
              "outline_vertices_pinned": 0,
              # §16g (10) (12), issue #101: the two ported v1 gates
              "no_tall_base": 0, "no_building_evidence": 0,
              "unmeasured": 0, "osm_vouched": 0, "cache_vouched": 0}
    if not clusters:
        return [], counts
    order = sorted(
        range(len(clusters)),
        key=lambda i: (min(getattr(clusters[i], "floors", ()) or (0.0,)),
                       -float(getattr(clusters[i], "area_m2", 0.0)),
                       str(getattr(clusters[i], "id", i))))
    oc = float(getattr(outline, "close_m", 0.0) or 0.0)
    och = float(getattr(outline, "chord_m", 0.0) or 0.0)
    oh = float(getattr(outline, "hole_min_m2", 0.0) or 0.0)
    pin = float(getattr(outline, "pin_m", 0.0) or 0.0)
    out: list[tuple[str, _t.Any, Polygon]] = []
    taken: list[Polygon] = []
    for i in order:
        c = clusters[i]
        if walled_only and not int(getattr(c, "walled", 0) or 0):
            counts["leaf_dropped"] += 1          # (7): it seats on its ground
            continue
        if min_m2 > 0.0 and float(getattr(c, "area_m2", 0.0)) < min_m2:
            counts["under_min_m2"] += 1          # the cache's pad stands
            continue
        # ── rules 9 / 10: v1's two PAD-ADMISSION gates (issue #101) ──
        ev = getattr(c, "evidence", None)
        if admission is not None and ev is None:
            # NOT MEASURED is not REFUSED (the ``cluster_no_height``
            # discipline): the cluster keeps the pre-#101 reading and the
            # population says so.
            counts["unmeasured"] += 1
        # rule 9 — THE TALL-BASE FILL.  Scalar, so it is asked before the
        # rings are projected: a slab/mast weld never reaches the outline.
        if (admission is not None and ev is not None
                and float(admission.min_tall_base_fill) > 0.0
                and not bool(getattr(ev, "name_vouched", False))
                and float(getattr(ev, "hull_area_m2", 0.0)) > 0.0
                and float(ev.tall_base_fill)
                < float(admission.min_tall_base_fill)):
            _refuse(refused, counts, "no_tall_base", c,
                    "min_tall_base_fill", ev.tall_base_fill, None, ev)
            continue
        ps: list[Polygon] = []
        for r in (getattr(c, "rings", ()) or ()):
            if len(r) < 3:
                continue
            g = Polygon([to_xy(lo, la) for la, lo in r])
            if not g.is_valid:
                g = g.buffer(0.0)
            ps.extend(_parts(g))
        if not ps:
            counts["no_rings"] += 1
            continue
        u = unary_union(ps)
        if touch_m > 0.0:
            u = u.buffer(touch_m, join_style=2).buffer(-touch_m, join_style=2)
            if simplify_m > 0.0:
                u = u.simplify(simplify_m)
            if not u.is_valid:
                u = u.buffer(0.0)
        if bridge_m > 0.0 and getattr(c, "bridges", ()):
            # rule 2a: the posts that still chain close the outline
            u, nj = _bridge(u, c.bridges, to_xy, bridge_m)
            counts["post_bridged"] += nj
        u_in = None
        if oc > 0.0 or och > 0.0 or oh > 0.0:
            # rule 2b: the simplified building outline (§56 (1))
            u_in = u
            counts["outline_vertices_in"] += _outline_vertices(u)
            front = Frontage.near(u, frontage, pin, oc + och)
            u = simplified_outline(u, oc, och, oh, front)
            if front is not None:
                counts["outline_frontage"] += 1
                counts["outline_fills_refused"] += front.fills_refused
                counts["outline_vertices_pinned"] += front.vertices_pinned
            counts["outline_vertices_out"] += _outline_vertices(u)
            counts["outline_simplified"] += 1
            u2b = u
        if u.is_empty:
            counts["no_rings"] += 1
            continue
        # rule 10 — NO BUILDING, NO PAD.  Asked on the CLOSED outline so
        # the OSM half reads the same polygon the pad would have been.
        if (admission is not None and ev is not None
                and bool(admission.building_evidence)):
            vertical, _cov = _vertical_evidence(ev, admission)
            vouch = (osm_evidence(u) if (not vertical
                                         and osm_evidence is not None) else "")
            if not vertical and not vouch:
                _refuse(refused, counts, "no_building_evidence", c,
                        "building_evidence",
                        float(getattr(ev, "tallest_extent_m", 0.0)), u, ev)
                continue
            if not vertical:
                # the OSM half carried it — v1's evidence source (a)
                # (a ``True`` from a caller's own predicate reads as OSM)
                counts["cache_vouched" if vouch == CACHE_VOUCHED_SOURCE
                       else "osm_vouched"] += 1
        pieces = _outline_pieces(u, shades, airside, taken, thin_m, counts)
        if not pieces:
            continue
        counts["still_in_pieces"] += len(pieces) - 1
        cid = str(getattr(c, "id", i))
        ids = _piece_ids(cid, pieces)
        if stats is not None and u_in is not None:
            # §56 (1) 9: what rule 2b did to THIS cluster — the vertices of
            # the outline each piece was cut from, BEFORE the airside clip
            # (which adds the apron's own rim vertices), and the ids the
            # pre-2b outline would have had under the same rules 8/4/3/6
            before = _outline_pieces(u_in, shades, airside, taken, thin_m,
                                     collections.Counter())
            was = list(zip(_piece_ids(cid, before), before))
            for pid, piece in zip(ids, pieces):
                rp = piece.representative_point()
                frm = [q for q, g in was
                       if piece.contains(g.representative_point())]
                stats[pid] = {
                    "outline_vertices": sum(
                        _outline_vertices(g) for g in _parts(u2b)
                        if g.contains(rp)),
                    "outline_simplified_from": sum(
                        _outline_vertices(g) for g in _parts(u_in)
                        if g.intersects(piece)),
                    "outline_joined_from": frm if frm != [pid] else [],
                    "outline_growth_m2": _outline_growth(
                        piece, pid, was, frm, u_in, oc)}
        for pid, piece in zip(ids, pieces):
            out.append((pid, c, piece))
            taken.append(piece)
    counts["pads"] = len(out)
    return out, counts


class AirsideRim:
    """The airside union's BOUNDARY, and its own vertices — built ONCE per
    classify pass and asked per pad (RULINGS 2026-09-14as (i)).

    ``airside`` is the union of every airside face's polygon (the runway
    slabs and every apt.dat pavement page).  ``vertices`` is the coordinate
    set of its rings: the points the planar arrangement will already carry
    for the airside whatever the pads do, because every region ring is
    noded into one ``unary_union`` (``planar/overlay.build_arrangement``).

    Two indexes, both segment/point level so a pad's few hundred
    coordinates cost a tree query each and not a walk of the rim: the
    SEGMENTS answer "does this coordinate lie on the rim", the POINTS
    answer "which rim vertex is nearest".
    """

    __slots__ = ("airside", "boundary", "_coords", "_pts", "_segs", "band",
                 "snap_max", "nodes_ring", "nodes_kept", "node_tol")

    def __init__(self, airside, band_m: float = 0.0, snap_max_m: float = 0.0,
                 nodes=None, node_tol_m: float = ON_BOUNDARY_EPS_M):
        #: §16g (10) (12) (1) THE NODES ARE THE ARRANGEMENT'S OWN, NOT THE
        #: REGION RING'S.  ``nodes``, when given, is the coordinate set of
        #: the AIRSIDE PASS's noded line work
        #: (``planar/overlay.build_arrangement``'s pass A) — which carries
        #: the ring vertices DENSIFIED at the role's chord cap AND every
        #: crossing the runway stations, the zone edges, the road
        #: centrelines and the seam bands mint on the rim.  Built from
        #: ``airside.boundary`` alone (the pre-14ax reading) the rim's
        #: nodes stand up to a full 60 m chord apart, which is why 75 of
        #: HECA's crossing points measured FARTHER than
        #: ``pad_airside_snap_max_m`` from any of them (max 70.76 m) and
        #: minted an airside vertex each.  Only the given nodes lying ON
        #: the boundary are kept: a node in the airside's interior is not
        #: something a pad may snap to.
        #: HOW FAR A PAD MAY BE MOVED TO REACH A RIM NODE
        #: (``[placement] pad_airside_snap_max_m``).  Quantising a
        #: crossing point to the rim's nearest node moves the pad ALONG
        #: the rim by whatever that rim's own vertex spacing is — at HECA
        #: p50 4.3 m but up to 66 m, and on a coarse synthetic rectangle
        #: a 40 m shed's corner travelled 30 m.  Beyond this the pad
        #: keeps its crossing point and is COUNTED: a minted airside
        #: vertex is a smaller defect than a pad dragged across the
        #: apron.  0 disarms the quantisation entirely.
        #: THE IDENTITY GRID's own spacing (``emit.identity.
        #: min_distinct_spacing_m``).  The arrangement snap-ROUNDS the
        #: noded set to it, so a pad coordinate within it of an airside
        #: EDGE lands in a hot pixel that edge passes through and SPLITS
        #: it — an airside vertex minted by the pad without either ring
        #: ever touching.  MEASURED at HECA: the residual 36 minted
        #: vertices after the clip and the on-boundary snap stood 0.05 ..
        #: 0.42 m off the airside boundary, every one inside the 0.5 m
        #: grid.  0 disarms the band and only exact contacts are quantised.
        self.band = float(band_m)
        self.snap_max = float(snap_max_m)
        #: how far off the boundary an arrangement node may stand and still
        #: be the rim's (the grid's half cell when built by ``build_rim``)
        self.node_tol = float(node_tol_m)
        self.airside = airside
        self.boundary = None if airside is None or airside.is_empty \
            else airside.boundary
        coords: list[tuple[float, float]] = []
        segs: list = []
        if self.boundary is not None:
            for g in getattr(self.boundary, "geoms", (self.boundary,)):
                cs = [(float(x), float(y)) for x, y in g.coords]
                coords.extend(cs)
                segs.extend(LineString((cs[i], cs[i + 1]))
                            for i in range(len(cs) - 1)
                            if cs[i] != cs[i + 1])
        self._segs = STRtree(segs) if segs else None
        #: how many of ``nodes`` were kept as rim nodes, and how many the
        #: ring itself carried — the caller PUBLISHES both, so a filter
        #: that silently kept nothing is visible instead of degrading to
        #: the ring (the reading this whole rule exists to fix).
        self.nodes_ring = len(coords)
        self.nodes_kept = 0
        if nodes is not None and self._segs is not None:
            keep: list[tuple[float, float]] = []
            for c in nodes:
                c = (float(c[0]), float(c[1]))
                if len(self._segs.query_nearest(Point(c),
                                                max_distance=node_tol_m,
                                                return_distance=False,
                                                all_matches=False)):
                    keep.append(c)
            self.nodes_kept = len(keep)
            if keep:
                coords = keep
        self._coords = coords
        self._pts = STRtree([Point(c) for c in coords]) if coords else None

    def has(self, c) -> bool:
        """Is ``c`` ALREADY an airside boundary vertex?"""
        if self._pts is None:
            return False
        i = self._pts.query_nearest(Point(c), max_distance=ON_BOUNDARY_EPS_M,
                                    return_distance=False)
        return len(i) > 0

    def nodes_along(self, coords, tol: float):
        """The rim NODES lying within ``tol`` of the polyline ``coords``,
        in order along it (RULINGS 2026-09-30aa rule 9: a ribbon's contact
        run is rebuilt from exactly these)."""
        if self._pts is None or len(coords) < 2:
            return []
        line = LineString(coords)
        hits = self._pts.query(line.buffer(max(tol, 1e-9)))
        got = [(line.project(Point(self._coords[int(i)])), self._coords[int(i)])
               for i in hits
               if line.distance(Point(self._coords[int(i)])) <= max(tol, 1e-9)]
        return [c for _s, c in sorted(got)]

    def nearest_vertex(self, c):
        """The nearest airside boundary vertex to ``c`` (``None`` if none)."""
        if self._pts is None:
            return None
        return self._coords[int(self._pts.nearest(Point(c)))]

    def on_boundary(self, c) -> bool:
        return self.rim_distance(c, ON_BOUNDARY_EPS_M) is not None

    def rim_distance(self, c, within: float):
        """Distance from ``c`` to the airside boundary, or ``None`` when
        it is farther than ``within`` (one indexed query, never a walk)."""
        if self._segs is None or within <= 0.0:
            return None
        p = Point(c)
        i, d = self._segs.query_nearest(p, max_distance=within,
                                        return_distance=True, all_matches=False)
        if len(i) == 0:
            return None
        return float(d[0])

    def push_out(self, c, d: float):
        """``c`` moved AWAY from the airside to ``self.band`` clear of it —
        the pad retreating a few centimetres rather than sliding metres
        along the rim.  ``None`` when the direction is undefined."""
        if self.boundary is None or d <= 0.0:
            return None
        q = _nearest_on(self.boundary, Point(c))
        if q is None:
            return None
        vx, vy = c[0] - q[0], c[1] - q[1]
        n = (vx * vx + vy * vy) ** 0.5
        if n <= 0.0:
            return None
        k = self.band / n
        return (q[0] + vx * k, q[1] + vy * k)


def _nearest_on(geom, p):
    from shapely.ops import nearest_points
    try:
        q = nearest_points(geom, p)[0]
    except Exception:
        return None
    return (float(q.x), float(q.y))


def _snap_ring(ring, rim: AirsideRim, moved: list[float], far: list[float]):
    out: list[tuple[float, float]] = []
    for c in list(ring)[:-1]:
        c = (float(c[0]), float(c[1]))
        d = rim.rim_distance(c, max(rim.band, ON_BOUNDARY_EPS_M))
        if d is not None and not rim.has(c):
            if d <= ON_BOUNDARY_EPS_M:
                # ON the rim and not one of its nodes: the CLIP's own
                # crossing point — quantise it to the rim's nearest node
                q = rim.nearest_vertex(c)
            else:
                # inside the identity grid's hot-pixel reach of an airside
                # EDGE: retreat clear of it, keeping the welded run intact
                q = rim.push_out(c, d)
            if q is not None:
                m = ((q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2) ** 0.5
                if rim.snap_max <= 0.0 or m > rim.snap_max:
                    far.append(m)
                else:
                    moved.append(m)
                    c = q
        if not out or out[-1] != c:
            out.append(c)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _snap_once(poly, rim, moved, far):
    ext = _snap_ring(poly.exterior.coords, rim, moved, far)
    if len(ext) < 3:
        return None
    ints = []
    for h in poly.interiors:
        r = _snap_ring(h.coords, rim, moved, far)
        if len(r) >= 3:
            ints.append(r)
    try:
        g = Polygon(ext, ints)
        if not g.is_valid:
            g = g.buffer(0.0)
    except Exception:
        return None
    return None if g is None or g.is_empty or g.area <= 0.0 else g


def airside_vertex_snap(poly: Polygon, rim: "AirsideRim", counts: dict):
    """RULINGS 2026-09-14as (i): A PAD ADDS NO VERTEX TO ANY AIRSIDE FACE.

    A pad clipped by airside runs ALONG the airside boundary between the
    two points where its own edge CROSSES it, and those crossing points
    are not airside vertices — noded into the arrangement they SPLIT the
    airside edge and mint an airside vertex that exists only because the
    pad does.  MEASURED at HECA (lane ``v2padvert``, classify+planar arm,
    one load two arms): with the clip's first half alone, arming
    ``pad_from_cluster`` still minted 79 airside vertices and took 59
    away, every one of them at an apron/pad contact.

    So every pad coordinate lying ON the airside boundary WITHOUT being
    one of its vertices is moved to the nearest airside boundary VERTEX:
    the pad's contact stretch is QUANTISED to the airside's own nodes.
    THE PAD YIELDS, THE AIRSIDE NEVER DOES.

    A snap can pull a corner along the rim far enough that the pad's own
    side edge crosses back INTO airside; the pad is then re-clipped and
    snapped ONCE more (the second pass has no crossing left to move in
    the common case).  A pad still invalid, empty, or inside airside
    after that keeps the CLIP's own polygon and is counted by reason
    (``snap_refused_overlap`` / ``snap_refused_invalid``) — a refusal is
    reported, never silently taken, and it is the only way a pad can
    still mint an airside vertex.

    Returns a Polygon or MultiPolygon; the caller unions the parts.
    """
    if rim.boundary is None or poly is None or poly.is_empty:
        return poly
    moved: list[float] = []
    far: list[float] = []
    g = _snap_once(poly, rim, moved, far)
    if far:
        counts["snap_too_far"] = counts.get("snap_too_far", 0) + len(far)
        counts["snap_too_far_max_m"] = round(
            max(counts.get("snap_too_far_max_m", 0.0), max(far)), 3)
    if not moved:
        return poly
    if g is not None and g.intersection(rim.airside).area > 1e-6 * max(g.area, 1.0):
        # the snapped corner pulled the pad back over the rim: re-clip,
        # then quantise the ONE new crossing the re-clip made
        g2 = g.difference(rim.airside)
        parts = _parts(g2)
        if parts:
            again: list = []
            for q in parts:
                r = _snap_once(q, rim, moved, far)
                again.append(r if r is not None else q)
            g = unary_union(again)
        else:
            g = None
    ok = (g is not None and not g.is_empty and g.area > 0.0)
    if ok and g.intersection(rim.airside).area > 1e-6 * max(g.area, 1.0):
        counts["snap_refused_overlap"] = counts.get("snap_refused_overlap", 0) + 1
        return poly
    if not ok:
        counts["snap_refused_invalid"] = counts.get("snap_refused_invalid", 0) + 1
        return poly
    counts["snapped_pads"] = counts.get("snapped_pads", 0) + 1
    counts["snapped_vertices"] = counts.get("snapped_vertices", 0) + len(moved)
    counts["snap_max_m"] = round(max(counts.get("snap_max_m", 0.0),
                                     max(moved)), 3)
    return g
