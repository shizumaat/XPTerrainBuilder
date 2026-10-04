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
pavement steeper than the road grade).  A piece sharing at least
``lot.airside_edge_min_m`` (§27's own length) with an APRON cell says so
(``touches_apron``) and takes :data:`APRON_TOUCH_ROLE` — the ONE switch
the owner's "a piece that touches an apron is apron" turns.  A piece that
runs along a RUNWAY or TAXI face and no apron is NOT minted (master
2026-10-04): it is listed, and stays raw."""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import snap_margin_m
from ..model.airport import Airport
from ..model.planar import GAP_PREFIX
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_gap_pieces", "ROLE", "APRON_TOUCH_ROLE", "KIND"]

#: every gap piece (04m (3): graded at the road grade cap)
ROLE = "groundside_pavement"
#: THE SWITCH (spec §53 (3) R1 / R3): the role of a piece that touches an
#: apron.  R1 (master 2026-10-04, pending owner): the same groundside role —
#: the piece takes the apron's LEVEL at the weld, not its role.
APRON_TOUCH_ROLE = ROLE
KIND = "gap_piece"


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


def mint_gap_pieces(airport: Airport, cells: list, law: Law, rules: Rules,
                    add, notes: list | None = None) -> dict[str, float]:
    """Mint the §53 gap pieces onto ``cells`` through ``add`` (the
    classifier's own cell constructor); returns the counts."""
    stats = {"gap_pieces": 0, "gap_piece_m2": 0.0, "gap_pieces_apron": 0,
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
        + snap_margin_m(law)
    min_edge = float(rules.lot.airside_edge_min_m)
    grid = rules.cells.snap_grid_m
    p = law.tables.precedence
    rolling = set(p.runway_family.members) | set(p.taxi_family.members)
    polys = [(c, q) for c, q in ((c, _poly(c.ring, c.holes)) for c in cells)
             if q is not None]
    standing = [q for _c, q in polys]
    if knife_m > 0.0:
        standing += [q.buffer(knife_m, join_style="mitre", mitre_limit=2.0)
                     for c, q in polys if c.role == "building"]
    aprons = [q for c, q in polys if c.role == "apron"]
    rolled = [q for c, q in polys if c.role in rolling]
    apron_tree = STRtree(aprons) if aprons else None
    rolled_tree = STRtree(rolled) if rolled else None
    # THE ARCS AND THE TRIANGLE TEETH ARE NOT DATA (the hard plane's rule,
    # ``airport/object_pavement``, issue #20): the sheet's own outline is
    # simplified at half the identity spacing BEFORE the difference, so the
    # runs it shares with a standing cell stay that cell's own boundary
    sheet = unary_union(sheets).simplify(0.5 * ident, preserve_topology=True)
    geom = shapely.set_precision(sheet.difference(unary_union(standing)), grid)
    to_ll = airport.frame.transformers()[1]
    parts = sorted(polygon_parts(geom),
                   key=lambda q: (-round(q.area), round(q.bounds[0], 2),
                                  round(q.bounds[1], 2)))
    k = 0
    for part in parts:
        if part.area < lw.object_pavement_min_m2 \
                or part.buffer(-0.5 * lane).is_empty:
            stats["gap_pieces_under_floor"] += 1
            continue
        apron_m = _shared_m(part, apron_tree, aprons, weld_m) if apron_tree else 0.0
        touches = apron_m >= min_edge
        if not touches and rolled_tree is not None:
            rolled_m = _shared_m(part, rolled_tree, rolled, weld_m)
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
        add(APRON_TOUCH_ROLE if touches else ROLE, f"{GAP_PREFIX}:{k}", part,
            KIND, None, None,
            {"gap_piece": 1.0, "area_m2": float(part.area),
             "touches_apron": float(touches), "apron_shared_m": float(apron_m)})
        k += 1
        stats["gap_pieces"] += 1
        stats["gap_piece_m2"] += float(part.area)
        stats["gap_pieces_apron"] += int(touches)
    return stats
