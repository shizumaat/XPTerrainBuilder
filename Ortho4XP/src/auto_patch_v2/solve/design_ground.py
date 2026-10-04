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
``solve/design.assemble`` mints the rows from it and ``tools/v2_why_solve`` names the
terminal from it; neither re-derives the set.
"""
from __future__ import annotations


from ..law import Law
from ..law.tables import bend_class
from ..model.planar import PlanarMap
from .design_roles import bend_roles, pavement_roles

__all__ = ["ground_roles", "ground_datum_vertices", "ground_rim_vertices",
           "coverage_edge_collar_vertices"]


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
    for fid in outer:
        f = planar.faces[fid]
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                if v in pav or v in out:
                    continue
                if planar.vertices[v].dem_z is None:
                    continue
                out.add(v)
    out.update(coverage_edge_collar_vertices(planar))
    return frozenset(out)


def ground_rim_vertices(planar: PlanarMap) -> frozenset[int]:
    """The members of :func:`ground_datum_vertices` that carry the datum as
    a COLLAR RIM (issue #302) and so anchor no sheet: their datum levels the
    vertex, never the pad's body (``solve.design.assemble`` reads it)."""
    return frozenset(coverage_edge_collar_vertices(planar))


def coverage_edge_collar_vertices(planar: PlanarMap) -> set[int]:
    """THE COLLAR'S COVERAGE EDGE IS GROUND (issue #302; owner RULINGS
    2026-10-02r / 10-02v (5): "within the bank the rim follows the GROUND
    objective"; ``constraints/platform``: "the coverage edge: the DEM's
    level, the collar's SLOPE").

    A platform collar's outer vertex on an edge with NO face beyond it
    stands against the base mesh, which IS the DEM.  Since #223 it carries
    only its ONE-WAY 1:3 bank rows (the plate leads), and those are SLACK
    wherever it stands more than 3x its rise from the nearest platform
    vertex — so nothing gave it a level.  MEASURED (HECA replay of
    ``hecamove/HECA.pkl --from classify``, main 43b7896b): ``building75``'s
    rim v21675 at 30.12086521267, 31.41819005825 carried 2 bending rows of
    Σc² 0.0098 against ~1e6 on the pavement beside it and 6 bank rows, all
    inactive (allowance 7.5 m, 23 m from the plate) — a near-null column.
    Its height was whatever the solve path left: 107.2 m through lag round
    4, 102.7 m from round 6, alternating 103.0 / 107.14 between sweeps
    sw1020 / sw1021 with the nearest change 174 m away.

    Such a vertex is adjacent ground in every sense §23 names: not
    pavement, its law rows one-sided and ONE-WAY (``follows = v``), and the
    natural ground its objective.  It takes the same WEAK datum, so it
    EQUALS the DEM where the bank allows and the bank cuts it TO THE LAW
    LINE where it binds.  A vertex shared with ANOTHER pad's face is not
    this collar's ground (``constraints/platform``'s own exemption) and is
    left out, as is any vertex of a pavement face (an airside contact
    leads): every incident face must be this pad's own collar or platform.
    (``building`` is a pavement role, so the §23 (b) pavement test cannot be
    applied to a collar vertex as written — it would exclude them all.)"""
    from ..model.planar import is_collar_ref, platform_ref_of
    if not any(is_collar_ref(getattr(f, "ref", "")) for f in planar.faces.values()):
        return set()
    edge_v = {v for e in planar.edges.values()
              if e.left_face is None or e.right_face is None
              for v in (e.a, e.b)}
    out: set[int] = set()
    for f in planar.faces.values():
        if not is_collar_ref(f.ref):
            continue
        own = platform_ref_of(f.ref)
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                if v not in edge_v or v in out:
                    continue
                vx = planar.vertices[v]
                if vx.dem_z is None:
                    continue
                if all(platform_ref_of(planar.faces[q].ref) == own
                       for q in vx.incident_faces):
                    out.add(v)
    return out


