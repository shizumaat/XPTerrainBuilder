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

import typing as _t

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

__all__ = ["cluster_outlines", "OUTLINE_SIMPLIFY_M", "airside_vertex_snap",
           "AirsideRim", "ON_BOUNDARY_EPS_M"]

#: How close a pad coordinate must be to the airside boundary to count as
#: lying ON it.  The clip's own output lies on it to float precision; this
#: is a float-noise band, NOT a weld tolerance.
ON_BOUNDARY_EPS_M = 1e-6

#: §16g (10) (2) (a): how far a CLOSED cluster outline is simplified back
#: after the dilate/erode — the emitter's own outline tolerance
#: (``placement_family``'s ``OUTLINE_SIMPLIFY_M``).  A pad the planar map
#: must carry is a real vertex budget.
OUTLINE_SIMPLIFY_M = 0.05


def _parts(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, MultiPolygon):
        return [q for q in g.geoms if isinstance(q, Polygon) and q.area > 0.0]
    return [g] if isinstance(g, Polygon) and g.area > 0.0 else []


def cluster_outlines(clusters: _t.Sequence[_t.Any],
                     to_xy: _t.Callable[[float, float], tuple[float, float]],
                     touch_m: float,
                     simplify_m: float = OUTLINE_SIMPLIFY_M,
                     airside=None,
                     walled_only: bool = False,
                     min_m2: float = 0.0,
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

    ``touch_m <= 0`` disarms the close (rule 2); ``airside=None``
    disarms the clip (rule 4); ``walled_only=False`` and ``min_m2=0``
    disarm (7).
    """
    counts = {"clusters": len(clusters), "no_rings": 0, "over_another": 0,
              "still_in_pieces": 0, "on_airside": 0, "clipped": 0,
              "leaf_dropped": 0, "under_min_m2": 0, "pads": 0}
    if not clusters:
        return [], counts
    order = sorted(
        range(len(clusters)),
        key=lambda i: (min(getattr(clusters[i], "floors", ()) or (0.0,)),
                       -float(getattr(clusters[i], "area_m2", 0.0)),
                       str(getattr(clusters[i], "id", i))))
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
        if u.is_empty:
            counts["no_rings"] += 1
            continue
        if airside is not None and not airside.is_empty and u.intersects(airside):
            before = u.area
            u = u.difference(airside)
            if u.is_empty or u.area <= 0.0:
                counts["on_airside"] += 1        # it seats on the pavement
                continue
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
            continue
        counts["still_in_pieces"] += len(pieces) - 1
        cid = str(getattr(c, "id", i))
        pieces.sort(key=lambda g: (round(g.bounds[1], 3), round(g.bounds[0], 3)))
        for k, piece in enumerate(pieces):
            out.append((cid if len(pieces) == 1 else f"{cid}/{k}", c, piece))
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

    __slots__ = ("airside", "boundary", "_coords", "_pts", "_segs", "band")

    def __init__(self, airside, band_m: float = 0.0):
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
        self._coords = coords
        self._pts = STRtree([Point(c) for c in coords]) if coords else None
        self._segs = STRtree(segs) if segs else None

    def has(self, c) -> bool:
        """Is ``c`` ALREADY an airside boundary vertex?"""
        if self._pts is None:
            return False
        i = self._pts.query_nearest(Point(c), max_distance=ON_BOUNDARY_EPS_M,
                                    return_distance=False)
        return len(i) > 0

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


def _snap_ring(ring, rim: AirsideRim, moved: list[float]):
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
                moved.append(((q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2) ** 0.5)
                c = q
        if not out or out[-1] != c:
            out.append(c)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _snap_once(poly, rim, moved):
    ext = _snap_ring(poly.exterior.coords, rim, moved)
    if len(ext) < 3:
        return None
    ints = []
    for h in poly.interiors:
        r = _snap_ring(h.coords, rim, moved)
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
    g = _snap_once(poly, rim, moved)
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
                r = _snap_once(q, rim, moved)
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
