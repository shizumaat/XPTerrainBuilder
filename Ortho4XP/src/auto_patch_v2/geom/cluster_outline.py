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

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

__all__ = ["cluster_outlines", "OUTLINE_SIMPLIFY_M"]

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
