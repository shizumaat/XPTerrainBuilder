"""THE GAP MINT — a pack pavement page admitted as GAP PIECES ONLY (spec
§53; owner RULINGS 2026-10-04o (a), (b), 2026-10-04m (3); master 2026-10-04,
pending owner on the role; issues #292, #358).

ONE derivation site, called by ``roles.classify`` LAST — after the pads,
§27, the pad set-back, the §52 facade cells and the mapped-road ribbons:
each GAP SHEET body (``Airport.gap_sheets``: a draped pavement page the
per-triangle flatness read admitted, ``airport/object_pavement``) MINUS
every cell standing and every pad's set-back.  Each connected remainder
that reaches ``[load] object_pavement_min_m2`` and holds a disc one lane
wide is ONE cell, ref ``gap:<k>``.

THE MINT ONLY APPENDS: no cell standing is re-cut, re-kinded or re-reffed,
and the sheet is never a pavement SOURCE — the airside region, its slice
and the classify ladder never see it.  Every gap piece is a LATE cell
(``model.planar.is_late_ref``): it joins the finished map at
``planar/ribbons``' pass C, welded to the airside rim at the rim's own
nodes, and is absent from the stage-1 map, so the airside and every pad
are the map's without the sheet by construction.

THE ROLE is groundside pavement at the road grade cap (04m (3): no
pavement steeper than the road grade) — EXCEPT a piece that shares at least
``lot.airside_edge_min_m`` (§27's own length) with an APRON cell
(``touches_apron``) and is not a ROAD by road evidence (spec §59, owner
RULINGS 2026-10-08c (6), 08g; ``classify/gap_apron``): it IS the apron — a
stage-1 ``apron`` cell, ref ``gapapron:<j>``, its rim closed onto the apron
rings it runs along.  A piece that runs along a RUNWAY or TAXI face and no
apron is NOT minted (master 2026-10-04): it is listed, and stays raw."""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import gap_standoff_m, snap_margin_m
from ..model.airport import Airport
from ..model.planar import GAP_APRON_PREFIX, GAP_PREFIX, is_osm_ribbon_ref
from .evidence import Evidence, polygon_parts
from .gap_apron import close_rim, judge
from .rules import Rules

__all__ = ["mint_gap_pieces", "standoff_m", "ROLE", "KIND", "APRON_KIND"]

#: every gap piece (04m (3): graded at the road grade cap)
ROLE = "groundside_pavement"
KIND = "gap_piece"
#: a piece classed APRON (spec §59): a stage-1 apron cell
APRON_KIND = "gap_apron"


def standoff_m(law: Law) -> float:
    """THE STAND-OFF of a gap piece from a standing cell it does not weld to
    (spec §53 (12)): the pad set-back + the snap margin + one identity cell
    — the §52 facade strip's own (``facade_mint``'s ``strip_knives``).  The
    value is ``law.tables.gap_standoff_m`` (the follow reach reads it too)."""
    return gap_standoff_m(law)


def _poly(ring, holes=()):
    try:
        p = Polygon(ring, holes)
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0.0)
    return None if p.is_empty else p


def _shared_m(part: Polygon, tree: STRtree, polys: list, weld_m: float) -> float:
    """Metres of ``part``'s boundary within ``weld_m`` of the boundaries of
    ``polys`` (the weld-tolerant read §27 uses), each run counted once."""
    runs = []
    for j in tree.query(part.buffer(weld_m), predicate="intersects"):
        run = part.boundary.intersection(polys[int(j)].boundary.buffer(weld_m))
        if not run.is_empty and run.length > 0.0:
            runs.append(run)
    return float(unary_union(runs).length) if runs else 0.0


def mint_gap_pieces(airport: Airport, ev: Evidence, cells: list, law: Law,
                    rules: Rules, add, notes: list | None = None) -> dict[str, float]:
    """Mint the §53 gap pieces onto ``cells`` through ``add`` (the
    classifier's own cell constructor); returns the counts.  ``ev`` is the
    classifier's evidence: the §59 class of an apron-touching piece reads its
    routes and the mapped roads on the sheet."""
    stats = {"gap_pieces": 0, "gap_piece_m2": 0.0, "gap_pieces_apron": 0,
             "gap_pieces_road": 0,
             "gap_pieces_unminted_airside": 0, "gap_pieces_under_floor": 0}
    sheets = [p for p in (_poly(g.outer, g.holes)
                          for g in getattr(airport, "gap_sheets", ()) or ())
              if p is not None]
    if not sheets:
        return stats
    lw = law.tables.structures.load
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    weld_m = float(law.tables.emit.identity.weld_spacing_m)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    knife_m = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)                 # the pad set-back (``ribbon_mint``'s)
    min_edge = float(rules.lot.airside_edge_min_m)
    grid = rules.cells.snap_grid_m
    p = law.tables.precedence
    rolling = set(p.runway_family.members) | set(p.taxi_family.members)
    polys = [(c, q) for c, q in ((c, _poly(c.ring, c.holes)) for c in cells)
             if q is not None]
    # THE STAND-OFF (spec §53 (12), master 2026-10-04): a piece welds ONLY to
    # the APRON rim (pass C's own rim rule) and shares its rim with the
    # mapped-road ribbons that run through or along it (they are solved WITH
    # it — the last stage's followers).  From every OTHER standing cell — a
    # pad, an apt.dat or pack road, a lot, groundside pavement, a facade
    # cell, a runway / taxi face — it stands one identity cell beyond the pad
    # set-back: the §52 facade strip's own stand-off (``facade_mint``'s
    # ``strip_knives``, 1.45 m), for §52 (8)'s own reason — at the bare
    # set-back a sub-cell sliver is merged across and one shared vertex moves
    # the neighbour.  So no gap ring nodes a standing ring.
    stand = standoff_m(law)

    def off(q):
        return q.buffer(stand, join_style="mitre", mitre_limit=2.0)
    flush = [q for c, q in polys
             if c.role == "apron" or is_osm_ribbon_ref(c.ref)]
    apart = [off(q) for c, q in polys
             if not (c.role == "apron" or is_osm_ribbon_ref(c.ref))]
    # THE ADJACENT-GROUND BANDS ARE THE RUNWAY / TAXI FAMILY'S GROUND (master
    # 2026-10-04: airside is king — a gap piece never claims zone ground).
    # The bands are not CELLS — ``planar/zones`` derives them later, from the
    # cells, so their own rings do not exist here; their UN-TRIMMED extent is
    # ``ribbon_mint.ribbon_extent``'s envelope (the zone table's
    # half-widths), stood off like a standing cell.
    from .ribbon_mint import ribbon_extent
    bands = ribbon_extent(cells, law, Polygon())
    band_knife = off(bands) if not bands.is_empty else Polygon()
    aprons = [q for c, q in polys if c.role == "apron"]
    rolled = [q for c, q in polys if c.role in rolling]
    apron_tree = STRtree(aprons) if aprons else None
    rolled_tree = STRtree(rolled) if rolled else None
    # THE ARCS AND THE TRIANGLE TEETH ARE NOT DATA (the hard plane's rule,
    # ``airport/object_pavement``, issue #20): the sheet's own outline is
    # simplified at half the identity spacing BEFORE the difference, so the
    # runs it shares with a standing cell stay that cell's own boundary
    sheet = unary_union(sheets).simplify(0.5 * ident, preserve_topology=True)
    standing = unary_union(flush + apart)
    before_bands = sheet.difference(standing)
    geom = shapely.set_precision(
        before_bands.difference(band_knife) if not band_knife.is_empty
        else before_bands, grid)
    if not band_knife.is_empty:
        stats["gap_band_trim_m2"] = float(before_bands.intersection(band_knife).area)
    to_ll = airport.frame.transformers()[1]
    parts = sorted(polygon_parts(geom),
                   key=lambda q: (-round(q.area), round(q.bounds[0], 2),
                                  round(q.bounds[1], 2)))
    kept: list[tuple[Polygon, float, bool]] = []
    for part in parts:
        if part.area < lw.object_pavement_min_m2 \
                or part.buffer(-0.5 * lane).is_empty:
            stats["gap_pieces_under_floor"] += 1
            continue
        apron_m = _shared_m(part, apron_tree, aprons, weld_m) if apron_tree else 0.0
        touches = apron_m >= min_edge
        if not touches and rolled_tree is not None:
            # across the stand-off: the piece is never flush on such a face
            rolled_m = _shared_m(part, rolled_tree, rolled, stand + weld_m)
            if rolled_m >= min_edge:
                stats["gap_pieces_unminted_airside"] += 1
                if notes is not None:
                    rp = part.representative_point()
                    lat, lon = to_ll(rp.x, rp.y)
                    notes.append(
                        f"gap piece NOT minted: {part.area:,.0f} m2 at "
                        f"{lat:.7f}, {lon:.7f} runs {rolled_m:,.0f} m along a "
                        f"runway / taxi face and touches no apron (§53)")
                continue
        kept.append((part, apron_m, touches))
    # THE CLASS (spec §59 (2)): the apron-touching pieces, judged ONCE by the
    # standing readers; a piece that touches no apron is not judged (04m (3))
    judged = [i for i, (_p, _m, touches) in enumerate(kept) if touches]
    verdict = dict(zip(judged, judge(
        [kept[i][0] for i in judged], airport, ev, cells, sheet, stand + weld_m,
        law, rules, ROLE, KIND))) if judged else {}
    j = 0
    for k, (part, apron_m, touches) in enumerate(kept):
        v = verdict.get(k)
        lost = (float(part.buffer(stand).intersection(before_bands)
                      .intersection(band_knife).area)
                if not band_knife.is_empty else 0.0)
        ref = f"{GAP_APRON_PREFIX}:{j}" if v is not None and v.apron \
            else f"{GAP_PREFIX}:{k}"
        if notes is not None and lost >= 1.0:
            notes.append(f"gap piece {ref}: {part.area:,.0f} m2; the "
                         f"runway / taxi band envelope took {lost:,.0f} m2 beside it (§53 (12))")
        stats["gap_pieces"] += 1
        if v is not None and v.apron:
            # THE WELD IS MADE HERE (§59 (2) 4): the rim closed onto the apron
            # rings, clear of every standing cell and every other piece
            others = [q for i, (q, _m, _t) in enumerate(kept) if i != k]
            part = close_rim(part, aprons, apron_tree,
                             [standing, band_knife, *others], weld_m, grid)
            edge_m = apron_m if v.airside_edge_m is None else v.airside_edge_m
            add("apron", ref, part, APRON_KIND, None, None,
                {"gap_apron": 1.0, "gap_ref": f"{GAP_PREFIX}:{k}",
                 "area_m2": float(part.area), "apron_shared_m": float(apron_m),
                 "airside_edge_m": float(edge_m),
                 "road_evidence": float(v.road_evidence)})
            if notes is not None:
                rp = part.representative_point()
                lat, lon = to_ll(rp.x, rp.y)
                notes.append(
                    f"gap piece {ref}: {part.area:,.0f} m2 at {lat:.7f}, {lon:.7f}: apron — "
                    + (f"road evidence, {edge_m:,.0f} m of {part.length:,.0f} m "
                       f"lateral airside edge (§37 (2))" if v.road_evidence
                       else "no road evidence"))
            j += 1
            stats["gap_pieces_apron"] += 1
        else:
            evid = {"gap_piece": 1.0, "area_m2": float(part.area),
                    "touches_apron": float(touches), "apron_shared_m": float(apron_m)}
            if v is not None:
                evid["road_evidence"] = 1.0
                stats["gap_pieces_road"] += 1
            add(ROLE, ref, part, KIND, None, None, evid)
        stats["gap_piece_m2"] += float(part.area)
    return stats
