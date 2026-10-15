"""THE APRON-EDGE SHELF — a building standing on an apron that reaches past
the apron's edge (owner RULINGS 2026-10-14n D2, issue #709; lane
``apronedge709``).

Owner, choosing option 4 of the slope-pad question: "Option 4 for the slope
pads, one at a time".  D2 as ruled: *the part of a building that stands on
an apron but reaches past its edge takes the apron's level and banks to the
ground under the adjacent-ground law.*  Found at the KASE Atlantic FBO
(walled cluster ``unit:121#4``, 420 m2, 86 % on apron ``pav7``): seated at
the apron's level, its east end and canopy posts stood up to 15 m past the
apron edge where the ground falls 0.5-1.3 m, and they floated.  It gets no
pad today: it is under ``[placement] cluster_pad_min_m2`` (§16g (9)), and a
derived pad never takes airside ground (14ah) — which this rule keeps.

THE WITNESS (:func:`shelf_regions`).  A WALLED cluster under the cluster-pad
bar whose CLOSED OUTLINE — the one :func:`geom.cluster_outlines` closes,
every admission gate of the pad mint included (evidence, tall-base fill,
deck and base-slab shades, thin pieces) — lies at least ``[placement]
apron_shelf_min_share`` on the pavement a pad fronts
(``law.tables.frontage_roles``) STANDS ON that pavement.  Its EXTENT is the
outline with its posts (``PlanCluster.bridges``) and every FOOTED part of
its members in its unit (they ride the unit's one seat; the FBO's canopy
posts and low walls stood up to 11.9 m off its outline, some with no ring),
inside the hull of them all.  The SHELF is the extent less every region
the arrangement already holds (airside, zones, roads, lots, pads) and less
a STAND-OFF from the airside (``[identity] weld_spacing_m`` plus one
identity cell): ground nobody else grades, never airside, never touching
it.  A piece is kept only where it fronts that pavement (within ``[design]
pad_frontage_m``) — the shelf is the apron's edge carried under the
building, not a pad of its own.

THE LEVEL AND THE BANK (no new row).  A shelf is a BUILDING face, so it is
a §20 pad fronting the apron by PROXIMITY: one plane at the pavement's edge
level, ONE-WAY (the pad follows; the apron never moves for it, 14ai).  It
shares no vertex with the airside, so stage 1 never sees it (MEASURED, KASE
replay: welded to the rim it minted one pav7 vertex through the noding's
snap-rounding and stage 1 moved 63 airside nodes by up to 0.04 m; priced as
a pad over its three apron contacts its 1 % ceiling relaxed 21 hard rows).
It is minted AFTER the conforming-hold register (``platform_split``), so it
is never a held block whose frontage brings the apron to it.  Around it a
``#collar`` face out to ``[building_pad] platform_collar_max_m`` over ground
nobody holds carries the 1:3 bank (``constraints/platform.
platform_collar_rows``, the ramp landing's bank, platform leading) down to
the ground, never within a bank's minimum width of the airside
(``planar/landing``'s own measured reason).  The strip between the apron
and the shelf is no face: the mesh spans it between the two edges, which
stand at one level.

THE CONSUMER CENSUS (owner 2026-08-30l) is in the module's twin
(``tests/auto_patch_v2/test_apron_shelf.py``) and the lane's PR: every
reader of a ``building`` face reads a shelf as a pad of its own ref
(``model.planar.SHELF_PREFIX``) EXCEPT the object stage, which reads the
shelf and its collar as GROUND (``airport/placement_read``,
``model.planar.is_shelf_ref``): the building is seated on the graded
surface the shelf makes, never on the shelf as its unit pad (MEASURED,
KASE replay: read as a pad, the FBO unit re-seated on the shelf's low side
and one of its bodies fell 1.7 m under the rest — the #625 class)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import frontage_roles, role_side
from ..geom.cluster_outline import THIN_PIECE_WIDTH_M
from ..geom.parts import nonempty_polygon_parts as _parts
from ..model.planar import COLLAR_SUFFIX, SHELF_PREFIX

__all__ = ["SHELVES", "shelf_regions"]

#: the last arrangement's shelves: ``{ref: record}`` (published by the
#: arrangement counts; read by the twin)
SHELVES: dict[str, dict[str, _t.Any]] = {}


def _outlines(airport, law: Law, min_m2: float):
    """``(cluster id, cluster, closed outline)`` per WALLED cluster UNDER the
    cluster-pad bar, through the pad mint's own closing and gates
    (``classify/evidence._cluster_pads``) — the ONE outline, never a second."""
    from ..airport.slab_faces import witness_faces
    from ..geom import cluster_building_evidence, cluster_outlines
    from ..geom.base_slab import pad_shades
    from ..law.tables import base_slab_law, pad_admission
    st = law.tables.structures.placement
    small = [c for c in (getattr(airport, "clusters", None) or ())
             if int(getattr(c, "walled", 0) or 0)
             and float(getattr(c, "area_m2", 0.0)) < min_m2]
    if not small:
        return []
    to_xy = airport.frame.entry()
    lw = base_slab_law(law)
    shades = pad_shades(getattr(airport, "partition", None), to_xy, lw,
                        getattr(airport, "sunken_ramps", None),
                        witness_faces(lw))
    got, _counts = cluster_outlines(
        small, to_xy, float(st.footprint_touch_m), airside=None,
        walled_only=True, min_m2=0.0, shades=shades,
        bridge_m=float(getattr(st, "post_bridge_gap_m", 0.0)),
        admission=pad_admission(law),
        osm_evidence=cluster_building_evidence(
            getattr(airport, "buildings", ()) or ()))
    return got


def _clean(g, pitch: float):
    """No two ring vertices of a shelf closer than one identity cell: the
    cut leaves near-duplicate corners that the noding keeps as sub-cell
    edges (MEASURED, KASE replay: three ``hairline_pair`` rows at 0.498 m).
    Simplified at a quarter cell, so no edge moves off a held neighbour by
    more than the noding's own rounding."""
    if pitch <= 0.0 or g.is_empty:
        return g
    s_ = g.simplify(0.25 * pitch, preserve_topology=True)
    out = []
    for q in _parts(s_):
        rings = []
        for ring in (q.exterior, *q.interiors):
            cs = list(ring.coords)[:-1]
            keep = [cs[0]]
            for c in cs[1:]:
                if ((c[0] - keep[-1][0]) ** 2 + (c[1] - keep[-1][1]) ** 2) ** 0.5 >= pitch:
                    keep.append(c)
            while len(keep) > 3 and ((keep[0][0] - keep[-1][0]) ** 2
                                     + (keep[0][1] - keep[-1][1]) ** 2) ** 0.5 < pitch:
                keep.pop()
            rings.append(keep)
        if len(rings[0]) < 3:
            continue
        p = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3])
        out.extend(_parts(p if p.is_valid else p.buffer(0.0)))
    return unary_union(out) if out else Polygon()


def _ring_poly(ring, to_xy):
    q = Polygon([to_xy(lo, la) for la, lo in ring])
    return q if q.is_valid else q.buffer(0.0)


def _part_prints(airport, to_xy) -> dict[tuple[str, str], list[Polygon]]:
    """``(unit id, resource) -> the plan footprints of its parts`` (a part
    ring, else its plan box) over ``Airport.partition``."""
    out: dict[tuple[str, str], list[Polygon]] = {}
    from shapely.geometry import box
    for u in getattr(getattr(airport, "partition", None), "units", ()) or ():
        for m in u.members:
            key = (str(u.id), str(m.resource))
            for q in m.parts:
                if q.rings:
                    gs = [_ring_poly(r, to_xy) for r in q.rings if len(r) >= 3]
                else:
                    (xa, ya), (xb, yb) = (to_xy(q.box[1], q.box[0]),
                                          to_xy(q.box[3], q.box[2]))
                    gs = [box(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb))]
                out.setdefault(key, []).extend(g for g in gs if not g.is_empty)
    return out


def _extent(u, c, to_xy, prints, touch_m: float) -> Polygon:
    """THE BUILDING'S GROUND: the closed outline, its posts
    (``PlanCluster.bridges``) and every part of its members in its unit
    that CHAINS to them — within ``[placement] footprint_touch_m`` of the
    outline or of a part already chained, the cluster's own chaining rule —
    inside the hull of them all.  A canopy roof chains to the building and
    its posts to the roof: they stand on the ground under the unit's one
    seat and draw no outline (the KASE FBO's posts and low walls stood up
    to 17 m off it, some with no ring)."""
    geo = [u]
    geo.extend(_ring_poly(r, to_xy) for r in (getattr(c, "bridges", ()) or ())
               if len(r) >= 3)
    unit = str(getattr(c, "unit", ""))
    cand = [g for res in (getattr(c, "members", ()) or ())
            for g in prints.get((unit, str(res)), ())]
    if cand:
        tree = STRtree(cand)
        seen: set[int] = set()
        todo = [unary_union(geo)]
        while todo:
            g = todo.pop()
            for j in tree.query(g, predicate="dwithin", distance=touch_m):
                j = int(j)
                if j not in seen:
                    seen.add(j)
                    todo.append(cand[j])
        geo.extend(cand[j] for j in sorted(seen))
    g = unary_union([q for q in geo if not q.is_empty])
    return g.convex_hull if len(geo) > 1 else g


def shelf_regions(base_regions: _t.Sequence, pad_regions: _t.Sequence,
                  airport, law: Law, grid: float, counts: dict,
                  late: _t.Sequence = ()) -> list:
    """The shelf + collar pad regions to append to ``pad_regions`` (module
    docstring), each registered in :data:`SHELVES`.  ``late`` — the polygons
    of the cells that join the finished map at pass C (mapped-road ribbons,
    §52 facade cells, §53 gap pieces): they hold their ground too (MEASURED,
    KATL replay: a shelf over a gap piece's ground re-welded the gap to the
    apron rim at four new pav4 vertices)."""
    import dataclasses as _dc
    SHELVES.clear()
    st = law.tables.structures.placement
    share_min = float(getattr(st, "apron_shelf_min_share", 0.0))
    min_m2 = float(st.cluster_pad_min_m2)
    if (share_min <= 0.0 or min_m2 <= 0.0 or airport is None
            or getattr(airport, "frame", None) is None):
        return []
    from ..law.tables import design as design_law
    near = float(design_law(law).pad_frontage_m)
    collar_m = float(law.tables.structures.building_pad.platform_collar_max_m)
    keep_m = float(law.tables.emit.design.bank_min_width_m)
    front = frontage_roles(law)
    pav = [r.polygon for r in base_regions
           if r.role in front and r.polygon is not None and not r.polygon.is_empty]
    if not pav:
        return []
    got = _outlines(airport, law, min_m2)
    if not got:
        return []
    pav_tree = STRtree(pav)
    air = unary_union([r.polygon for r in base_regions
                       if r.polygon is not None and not r.polygon.is_empty
                       and role_side(law, r.role) == "airside"])
    held = unary_union([r.polygon for r in [*base_regions, *pad_regions]
                        if r.polygon is not None and not r.polygon.is_empty]
                       + [g for g in late if g is not None and not g.is_empty])
    to_xy = airport.frame.entry()
    prints = _part_prints(airport, to_xy)
    touch = float(st.footprint_touch_m)
    ident = law.tables.emit.identity
    pitch = float(ident.min_distinct_spacing_m)
    standoff = float(ident.weld_spacing_m) + pitch
    tmpl = next((r for r in pad_regions if r.role == "building"), None)
    side = tmpl.side if tmpl is not None else role_side(law, "building")
    min_piece = max(grid * grid, 1.0)
    n_cand = n_taken = n_spread = 0
    plats: list[tuple[str, list[Polygon], str, float]] = []
    taken = held
    for cid, c, u in got:
        if u.is_empty or u.area <= 0.0:
            continue
        hit = [pav[int(j)] for j in pav_tree.query(u, predicate="intersects")]
        if not hit:
            continue
        on = u.intersection(unary_union(hit)).area / u.area
        if on < share_min:
            continue
        n_cand += 1
        ext = _extent(u, c, to_xy, prints, touch)
        # it STANDS ON the apron by its whole ground too, never only by its
        # walled outline (a member whose chained parts spread far beyond
        # the pavement is not a building on the apron's edge)
        hit = [pav[int(j)] for j in pav_tree.query(ext, predicate="intersects")]
        if ext.intersection(unary_union(hit)).area < share_min * ext.area:
            n_spread += 1
            continue
        if grid > 0.0:
            # simplified BEFORE the cut, so every edge the shelf shares with
            # a held region is that region's own (MEASURED, KASE replay:
            # simplified after it, the corners stood 0.03-0.06 m off the
            # apron rim and the ribbon pass minted an apron vertex there)
            s_ = ext.simplify(0.5 * grid, preserve_topology=True)
            ext = s_ if not s_.is_empty else ext
        S = ext.difference(taken)
        apron = unary_union(hit)
        # THE SHELF NEVER TOUCHES THE AIRSIDE: it stands off the rim by
        # ``standoff`` (beyond the sliver weld and the near-miss horizon,
        # one identity cell more — ``planar/pad_terrace``'s own cut-back
        # rule), so no airside vertex is shared, minted or priced and stage
        # 1 cannot see it; it fronts the apron by §20's proximity contact
        # (``[design] pad_frontage_m``), one-way.  MEASURED, KASE replay:
        # welded to the rim, the snap-rounding of its edge leaving a rim
        # node at a shallow angle minted one pav7 vertex and stage 1 moved
        # 63 airside nodes by up to 0.02 m.
        if standoff > 0.0:
            S = S.difference(air.buffer(standoff, join_style=2))
        S = _clean(S, pitch)
        # a piece narrower than a wall line is no ground under a building
        # (``geom.cluster_outline.THIN_PIECE_WIDTH_M``, rule 6's own test)
        Ls = [q for q in _parts(S) if q.area >= min_piece
              and 2.0 * q.area >= THIN_PIECE_WIDTH_M * q.length
              and q.distance(apron) <= near]
        if not Ls:
            n_taken += 1
            continue
        ref = f"{SHELF_PREFIX}{len(plats) + 1}"
        Lu = unary_union(Ls)
        taken = unary_union([taken, Lu])
        plats.append((ref, Ls, str(cid), round(on, 3)))
    if not plats:
        counts.update(shelf_candidates=n_cand, shelf_none_free=n_taken,
                      shelf_spread=n_spread, shelves=0)
        return []
    # the collars, over what no region, shelf, the airside or a bank's
    # minimum width of it holds (``planar/landing`` PASS 2's own rule)
    no_collar = unary_union([taken, air.buffer(keep_m, join_style=2) if keep_m > 0.0 else air])
    out: list = []

    def _region(ref: str, q: Polygon):
        if tmpl is not None:
            return _dc.replace(tmpl, ref=ref, polygon=q)
        from .overlay import Region
        return Region("building", ref, q, None, None, side, "cell")

    for ref, Ls, cid, on in plats:
        Lu = unary_union(Ls)
        C = (Lu.buffer(collar_m, join_style=2).difference(no_collar)
             if collar_m > 0.0 else Polygon())
        if keep_m > 0.0 and not C.is_empty:
            # no collar narrower than the narrowest bank ([design]
            # bank_min_width_m): a sliver of it beside a shelf corner is a
            # cliff, not a bank (MEASURED, KASE replay: a 0.5 m collar
            # sliver dropped 1.56 m from the shelf to the ground)
            C = C.buffer(-0.5 * keep_m, join_style=2).buffer(
                0.5 * keep_m, join_style=2).intersection(C)
        cparts = [q for q in _parts(_clean(C, pitch)) if q.area >= min_piece
                  and q.distance(Lu) <= 0.5 * max(grid, 0.0) + 1e-6]
        no_collar = unary_union([no_collar, *cparts])
        out.extend(_region(ref, q) for q in Ls)
        out.extend(_region(ref + COLLAR_SUFFIX, q) for q in cparts)
        SHELVES[ref] = {"cluster": cid, "on_share": on,
                        "area_m2": round(Lu.area, 1),
                        "collar_m2": round(sum(q.area for q in cparts), 1)}
    counts.update(shelf_candidates=n_cand, shelf_none_free=n_taken,
                  shelf_spread=n_spread,
                  shelves=len(SHELVES),
                  shelf_m2=round(sum(v["area_m2"] for v in SHELVES.values()), 1),
                  shelf_list="; ".join(
                      f"{r} {v['cluster']} on {v['on_share']:.2f} "
                      f"{v['area_m2']:g} m2 collar {v['collar_m2']:g}"
                      for r, v in sorted(SHELVES.items())[:12]))
    return out
