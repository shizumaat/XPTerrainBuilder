"""THE GROUND'S OWN DATUM — which vertices carry it (owner RULINGS
2026-09-10av; spec ``auto-patch-v2/design-surface-spec.md`` §23).

09b (3) made adjacent ground a pure LAW surface with no DEM term anywhere,
and a surface built only from one-sided rows has no level: CYXY's 14R/32L
end corridor cut 1.9 m into lawful natural ground and a 45 % bank climbed
back to a foot that was correctly on the DEM.  The owner's law: an
adjacent-ground vertex carries a WEAK per-vertex DEM DATUM, while its law
rows stay one-sided and ONE-WAY — so the strip EQUALS the natural ground
wherever the ground satisfies the zone law relative to its pavement, and is
cut or filled only where a law row binds.

THIS IS THE SINGLE DERIVATION SITE of "which vertex is adjacent ground"
(owner 2026-08-30l: trim at the derivation, never per consumer).
``solve/design.assemble`` mints the rows from it and ``solve/why`` names the
terminal from it; neither re-derives the set.
"""
from __future__ import annotations


from ..law import Law
from ..law.tables import bend_class
from ..model.planar import PlanarMap, is_collar_ref
from .design_roles import bend_roles, pavement_roles

__all__ = ["ground_roles", "ground_datum_vertices"]


def ground_roles(law: Law) -> frozenset[str]:
    """The ADJACENT-GROUND roles — the ``graded_strip`` family: every role
    the bending term prices at ``bend_strip`` (a role that carries no value
    of its own and is not a structure's surface), which is exactly zone 1,
    zone 2, the end corridors and the clearance skirts."""
    return frozenset(r for r in bend_roles(law) if bend_class(law, r) == "strip")


def ground_datum_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """The vertices that carry the ground datum (spec §23.2).

    A vertex qualifies when it (a) belongs to a face of :func:`ground_roles`,
    (b) is NOT also a vertex of a pavement face — the designed surface keeps
    no DEM pull (08t (1)), and a shared edge vertex IS pavement, (c) has a
    DEM sample, and (d) lies in a ground region that reaches the patch's
    OUTER BOUNDARY.

    (d) is 09g (1) and it is not optional: interior ground — a strip pocket
    enclosed by pavement — is part of the design sheet with the DEM
    overridden there.  The test is a flood over ground faces through shared
    edges, seeded from the faces carrying an edge with no face on its other
    side (``Edge.left_face``/``right_face`` ``None`` = outside the map).

    (e) A platform COLLAR's own vertex on that coverage edge qualifies too
    (issue #223): the collar's bank rows set its SLOPE against the platform
    and nothing else gave it a level (block (e) below).
    """
    roles = ground_roles(law)
    pav_roles = frozenset(pavement_roles(law))
    ground_fids = [f.id for f in planar.faces.values() if f.role in roles]
    if not ground_fids:
        return frozenset()
    is_ground = set(ground_fids)

    # face adjacency across shared edges, and the faces on the outside
    adj: dict[int, set[int]] = {fid: set() for fid in ground_fids}
    seed: list[int] = []
    for e in planar.edges.values():
        lf, rf = e.left_face, e.right_face
        for a, b in ((lf, rf), (rf, lf)):
            if a is None or a not in is_ground:
                continue
            if b is None:
                seed.append(a)
            elif b in is_ground:
                adj[a].add(b)

    outer: set[int] = set()
    stack = list(seed)
    while stack:
        fid = stack.pop()
        if fid in outer:
            continue
        outer.add(fid)
        stack.extend(adj[fid] - outer)

    pav: set[int] = set()
    for f in planar.faces.values():
        if f.role not in pav_roles:
            continue
        for ring in (f.ring, *f.holes):
            pav.update(planar.ring_vertices(ring))

    out: set[int] = set()
    # (e) THE COLLAR'S COVERAGE EDGE (issue #223): a platform collar's outer
    # vertex on an edge with no face beyond is exempt from the collar's bank
    # rows because "the DEM governs" there (``constraints/platform``) — but
    # nothing fixes the DEM since 09-09b (3), so such a vertex carried NO
    # level term at all and the bending stencil extrapolated it (SPJC
    # building14#collar, -12.02514481, -77.10577155: 46.26 m over a 24.7 m
    # ring and a 30.04 m DEM).  It takes the ground's own datum, exactly as
    # an adjacent-ground vertex on the coverage edge does.
    for e in planar.edges.values():
        if e.left_face is not None and e.right_face is not None:
            continue
        fid = e.left_face if e.left_face is not None else e.right_face
        if fid is None or not is_collar_ref(getattr(planar.faces[fid], "ref", "")):
            continue
        for v in (e.a, e.b):
            vx = planar.vertices[v]
            # the collar's OWN (or the ground's) vertex only — a vertex shared
            # with any other face is that face's value (a welded contact is
            # stage 1's, another pad's rim is its floor)
            if vx.dem_z is None or not all(
                    is_collar_ref(getattr(planar.faces[q], "ref", "")) or q in is_ground
                    for q in vx.incident_faces):
                continue
            out.add(v)
    for fid in outer:
        f = planar.faces[fid]
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                if v in pav or v in out:
                    continue
                if planar.vertices[v].dem_z is None:
                    continue
                out.add(v)
    return frozenset(out)


