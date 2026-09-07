"""BUILDING-PAD generator (RULINGS 2026-09-03h "pads yield", 2026-09-03i
"seniority follows from being governed", 2026-09-01g "weld = value";
``law/structures.toml [building_pad]``, ``precedence.toml`` ``rigid``).

A rigid role's face (a pad) is ONE flat value: a ``Flat`` group over
every vertex of its outer ring and holes.  Its LEVEL is set by what it
touches — the shared vertices with the apron carry the apron's own law,
so the group is levelled by its contact and never a pin the apron must
climb to (03h).  A DETACHED pad (no shared governed vertex) is still a
flat group; the objective's DEM term levels it (a DEM-levelled flat
group, never an invented seat).  No seat pin exists in v2.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, role_cap
from ..model.airport import Airport
from ..model.constraints import Diff, Flat, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["pad_flats", "rigid_roles", "frontage_near_miss", "frontage_contacts"]

GEN = "pads"


def rigid_roles(law: Law) -> tuple[str, ...]:
    """Every role the register marks rigid (data, never a list here)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if is_rigid_role(law, r)))


def pad_flats(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One ``Flat`` group per rigid face."""
    vw = view(planar, law)
    rows: list[Row] = []
    for f in vw.faces_of_role(rigid_roles(law)):
        group: list[int] = []
        seen: set[int] = set()
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for v in ring:
                if v not in seen:
                    seen.add(v)
                    group.append(v)
        if len(group) < 2:
            continue
        rows.append(Flat(tuple(group), Source(
            GEN, "structures.building_pad weld_to_touching_pavement (2026-09-01g, 03h)",
            (f"face:{f.id}", f.ref))))
    return rows


def frontage_contacts(planar: PlanarMap, law: Law
                      ) -> list[tuple[int, int, int, float, float, int]]:
    """THE NEAR-MISS FRONTAGE PAIRS as data: ``(soft endpoint, nearest
    pad vertex, pad face, distance to the pad polygon, apron cap, soft
    face)`` per
    fired endpoint (module rule below; :func:`frontage_near_miss` mints
    the rows, ``routes`` the pad's CONTACT edge — RULINGS 2026-09-05ab:
    a pad attaches to the route graph at its contact, the frontage
    row's apron vertex).  A soft endpoint fires once per pad."""
    vw = view(planar, law)
    bp = law.tables.structures.building_pad
    near = bp.frontage_near_miss_m
    cap = role_cap(law, "apron")
    if cap is None or near <= 0.0:
        return []
    budget = cap.longitudinal
    rigid = rigid_roles(law)
    pads: list[tuple[int, Polygon, list[int]]] = []
    pad_vertices: set[int] = set()
    for f in vw.faces_of_role(rigid):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        poly = Polygon([vw.xy[v] for v in ring],
                       [[vw.xy[v] for v in h] for h in vw.holes[f.id] if len(h) >= 3])
        if poly.is_empty:
            continue
        verts = list(ring)
        for h in vw.holes[f.id]:
            verts.extend(h)
        pads.append((f.id, poly, verts))
        pad_vertices.update(verts)
    if not pads:
        return []
    tree = STRtree([p[1] for p in pads])
    # A PAD NEVER FRONTS ACROSS A TERRACE JOINT (RULINGS 2026-09-06n): a pad
    # belongs to its own cell's terrace group (``planar.terrace_group``);
    # a soft face of another group across the joint gap is no frontage
    grp = planar.terrace_group
    out: list[tuple[int, int, int, float, float, int]] = []
    for f in vw.faces_of_role(tuple(bp.frontage_soft_roles)):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            n = len(ring)
            if n < 3:
                continue
            spoly = Polygon([vw.xy[v] for v in ring])
            if spoly.is_empty:
                continue
            cand = tree.query(spoly, predicate="dwithin", distance=near)
            if len(cand) == 0:
                continue
            for pi in cand:
                pid, ppoly, pverts = pads[int(pi)]
                gp, gf = grp.get(pid), grp.get(f.id)
                if gp is not None and gf is not None and gp != gf:
                    continue
                pset = set(pverts)
                fired: set[int] = set()
                for i in range(n):
                    a, b = ring[i], ring[(i + 1) % n]
                    if a in pset or b in pset:
                        continue        # identity reconciles that corner
                    if LineString([vw.xy[a], vw.xy[b]]).distance(ppoly) > near:
                        continue
                    for e in (a, b):
                        if e in pad_vertices or e in fired:
                            continue
                        fired.add(e)
                        x, y = vw.xy[e]
                        d = float(ppoly.distance(Point(x, y)))
                        j = min(pverts, key=lambda v: (vw.xy[v][0] - x) ** 2
                                + (vw.xy[v][1] - y) ** 2)
                        out.append((e, j, pid, d, budget, f.id))
    return out


def frontage_near_miss(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    """THE NEAR-MISS FRONTAGE LAW (Appendix A §1 ``frontage_near_miss``;
    RULINGS 2026-08-08, cycle-5 instrument-fix item 6; v1
    ``near_miss_building_frontage_edges`` / ``check_grade._check_frontage_
    near_miss``, the one reader).  A pad outline and the soft pavement it
    fronts can be offset by a sub-metre SOURCE mismatch (SPJC building29
    vs its SW apron: 0.68 m — a DSF facade against an apt.dat apron),
    leaving a sliver no identity join closes.  The frontage binds ACROSS
    it: for a ``frontage_soft_roles`` ring edge within
    ``frontage_near_miss_m`` of a pad, with BOTH endpoints unshared with
    that pad, each endpoint unshared with ANY pad holds
    ``|z_endpoint − z_pad(nearest pad vertex)| ≤ apron cap · d`` with
    ``d`` its own distance to the pad polygon.  Under 03h the pad is the
    junior side: the row levels the pad by its frontage exactly as a
    shared vertex would, never the apron by the pad."""
    # THE TIERED APRON LAW (RULINGS 2026-09-06w): the budget is the HARD
    # apron cap; the 1 % preference rides beside it (``apron.tiered_rows``)
    from .apron import tiered_rows
    from ..law.tables import role_preferred_cap
    pref = role_preferred_cap(law, "apron")
    pref_l = None if pref is None else pref.longitudinal
    rows: list[Row] = []
    tiers: dict[int, object] = {}
    for e, j, pid, d, budget, fid in frontage_contacts(planar, law):
        f = planar.faces[fid]
        tier = tiers.get(fid)
        if tier is None:
            tier = tiers[fid] = tiered_rows(fid, f.ref, budget, pref_l, GEN)
        rows.extend(tier.rows(e, j, d, Source(
            GEN, "structures.building_pad frontage_near_miss "
            "(2026-08-08; 09-01g weld = value; 03h pads yield)",
            (f"face:{f.id}", f.ref, f"pad:{pid}", planar.faces[pid].ref))))
    return rows
