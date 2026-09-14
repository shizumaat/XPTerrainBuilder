"""§30 (4) THE CLUSTER PAD and its APRON REACH (owner RULINGS
2026-09-13bj item 1; §16g's design-surface side, RULINGS 2026-09-13bo).

Owner, on KCLT 1.0.327: *"These large complex structures have to be
seated as a unit.  As long as it remains feasible with grade laws and
taxiways, etc. it's acceptable to flatten large apron areas around big
terminals if needed to accommodate a large terminal cluster."*

Two rows of law, both on the DESIGN surface:

* THE PAD IS ONE PLANE OVER THE WHOLE CLUSTER.  :func:`plane_groups`
  hands ``constraints/pads.py`` the groups a pad PLANE is priced over —
  every pad its own, except that the emitted ``building`` faces a
  TERMINAL CLUSTER's footprint union stands on are ONE entry.  So a
  cluster gets one ``pad_flats`` plate, one hard 1 % ceiling and one
  frontage level fit, while every GEOMETRIC reader keeps reading
  ``pads._pad_groups``'s per-face derivation (the consumer census in the
  spec's §30 (4) MEASURED block rules each one).
* THE APRON AROUND IT TAKES THAT PLANE.  :func:`cluster_apron_level`
  mints one ONE-WAY target per apron vertex within ``[design]
  cluster_apron_reach_m`` of the pad, at the LAW's own weight — so the
  apron's hard caps, the pad's ceiling and every taxi row outrank it and
  the reach yields wherever one plane cannot be had.  The reach never
  reaches a taxiway band's own vertices at all.

It lives apart from ``constraints/pads.py`` only because that file is at
the 1,000-line bar; ``pad_frontage_gs.py`` (§28) stands beside it for
exactly the same reason.  The CLUSTER itself is derived at load
(``planar/cluster.py``) and carried on ``Airport.clusters``: this layer
may not import ``planar``.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point, Polygon, box as _box
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import design as design_law, rolled_on_roles
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .pads import GEN_LEVEL, _pad_groups, _pad_polys, _two_sided
from .precedence import view

__all__ = ["cluster_reach_m", "cluster_polys", "cluster_pad_faces",
           "plane_groups", "cluster_apron_faces", "cluster_apron_level",
           "CLUSTER_REACH_RULING"]


def cluster_reach_m(law: Law) -> float:
    """§30 (4): ``[design] cluster_apron_reach_m`` — the plan distance
    within which an apron vertex takes a CLUSTER pad's plane as its
    target (owner RULINGS 2026-09-13bj item 1).  ONE derivation site; 0
    disables the reach."""
    return float(design_law(law).cluster_apron_reach_m)


def cluster_polys(airport: Airport | None) -> list[tuple[_t.Any, Polygon]]:
    """§30 (4): each CLUSTER carried on ``Airport.clusters``
    (``planar/cluster.py``, computed once at load beside the pack
    partition and the groups) with its FOOTPRINT UNION as one plan
    polygon in the PLANAR FRAME's metres — the union of its part boxes,
    which is exactly what ``placement_family.union_area_m2`` measures.

    ``constraints`` may not import ``planar`` (the layering twin), which
    is why the derivation travels on the airport and only its GEOMETRY
    is taken here."""
    cl = getattr(airport, "clusters", None) or ()
    if not cl or airport is None:
        return []
    from shapely.ops import unary_union
    to_xy, _to_ll = airport.frame.transformers()
    out: list[tuple[_t.Any, Polygon]] = []
    for c in cl:
        rects = []
        for la0, lo0, la1, lo1 in c.boxes:
            x0, y0 = to_xy(lo0, la0)
            x1, y1 = to_xy(lo1, la1)
            if x1 > x0 and y1 > y0:
                rects.append(_box(x0, y0, x1, y1))
        if not rects:
            continue
        u = unary_union(rects)
        if not u.is_empty:
            out.append((c, u))
    return out


def cluster_pad_faces(planar: PlanarMap, law: Law, airport: Airport | None
                      ) -> dict[str, list[int]]:
    """``cluster id -> the rigid FACE ids its footprint union stands on``.

    The test is INTERSECTION with the UNION, never with its hull: a
    terminal's hull spans the apron between its concourses and would
    swallow every stand's own structure (measured at KCLT, the hull is
    864,000 m2 against a 379,000 m2 union)."""
    got: dict[str, list[int]] = {}
    pairs = cluster_polys(airport)
    if not pairs:
        return got
    polys = _pad_polys(planar, law)
    if not polys:
        return got
    tree = STRtree([p[3] for p in polys])
    for c, u in pairs:
        hit = sorted({int(polys[int(i)][0])
                      for i in tree.query(u, predicate="intersects")})
        if hit:
            got[c.id] = hit
    return got


def plane_groups(planar: PlanarMap, law: Law, airport: Airport | None
                  ) -> list[tuple[int, str, list[int], tuple[int, ...]]]:
    """§30 (4): THE GROUPS A PAD *PLANE* IS PRICED OVER — every pad its
    own, except that the faces of ONE TERMINAL CLUSTER are ONE entry.

    ``(id, ref, rim vertices, the FACES it is made of)`` — the shape
    :func:`_pad_groups` returns plus the face list, which is all :func:`_pad_rows` and
    :func:`pad_frontage_level` need — so a cluster is one plate, one hard
    1 % ceiling and one level fit, while every GEOMETRIC reader keeps
    reading :func:`_pad_groups`'s per-face derivation (the consumer census
    in the spec's §30 (4) MEASURED block rules each one).

    The cluster is ``planar.cluster.cluster_pad_faces``, which is
    ``airport.placement_family``'s own ``_clusters`` law asked of the pack
    partition — the same relation the object stage's §16f (7) binds the
    objects with, so the plane the design surface makes and the plane the
    objects seat on are one thing by construction."""
    groups = _pad_groups(planar, law)
    plain = [(fid, ref, group, (fid,)) for fid, ref, group in groups]
    if airport is None:
        return plain
    faces = cluster_pad_faces(planar, law, airport)
    if not faces:
        return plain
    of_face: dict[int, str] = {}
    for cid, fids in faces.items():
        for fid in fids:
            of_face.setdefault(fid, cid)
    merged: dict[str, tuple[int, list[int], set[int], list[int]]] = {}
    out: list[tuple[int, str, list[int], tuple[int, ...]]] = []
    for fid, ref, group in groups:
        cid = of_face.get(fid)
        if cid is None:
            out.append((fid, ref, group, (fid,)))
            continue
        got = merged.get(cid)
        if got is None:
            merged[cid] = (fid, list(group), set(group), [fid])
            continue
        _f0, vs, seen, fids = got
        fids.append(fid)
        for v in group:
            if v not in seen:
                seen.add(v)
                vs.append(v)
    for cid, (fid0, vs, _seen, fids) in merged.items():
        out.append((fid0, f"cluster:{cid}", vs, tuple(sorted(fids))))
    return sorted(out, key=lambda q: q[0])



#: The ruling HEAD of §30 (4)'s apron reach.  Named by ``[design]
#: cluster_reach_rulings`` and by NEITHER ``pad_flat_rulings`` nor
#: ``hard_rulings``: owner RULINGS 2026-09-13cc (ii) prices the row at the
#: APRON TREND's design-target weight (``apron_trend``, 30) — a target the
#: taxi family's own law rows (300) always outrank, so the reach yields
#: wherever one plane cannot be had, which is exactly the owner's "as long
#: as it remains feasible with grade laws and taxiways".  At ``law`` it
#: did not yield: 2,815 taxi vertices moved, worst 1.88 m.
CLUSTER_REACH_RULING = "structures.building_pad cluster_apron_reach"


def cluster_apron_faces(planar: PlanarMap, law: Law, airport: Airport
                        ) -> dict[str, list[int]]:
    """§30 (4): ``cluster id -> the APRON vertices within
    ``cluster_apron_reach_m`` of its pad`` — the population the reach
    rows are minted over, as data (the publication reads the same call).

    THE REACH STOPS AT A TAXIWAY BAND (the ruling's own words).  The
    population is the ``apron`` faces alone, and a vertex any face of the
    TAXI or RUNWAY family also carries is struck: identity is the weld
    (09-01g), so such a vertex IS a taxiway vertex and the taxi family is
    never moved by a pad.  A vertex the pad already SHARES is struck too
    — it is in the pad's own plate (10y) and a row against the plate's
    own mean would only say the plane equals itself.

    AND IT STOPS ONE APRON CELL SHORT OF ANY TAXI FACE (owner RULINGS
    2026-09-13cc (i), the taxi bar).  Striking the band's own vertices is
    not enough and neither is the catchment: MEASURED on the matched KCLT
    pair, the reach lifted apron the taxi family is COUPLED to and 2,815
    of 6,453 taxi/runway vertices moved, worst 1.88 m — through §20's own
    no-step and trend rows, which are senior to the reach.  So an apron
    vertex a taxi-family NO-STEP row pairs with a taxi vertex
    (``no_step.no_step_edges``, the ONE derivation of that coupling) is
    struck as well."""
    reach = cluster_reach_m(law)
    if reach <= 0.0:
        return {}
    faces = cluster_pad_faces(planar, law, airport)
    if not faces:
        return {}
    vw = view(planar, law)
    taxi = tuple(sorted(set(_rolled_on(law)) - {"apron"}))
    struck: set[int] = set()
    tpolys: list[Polygon] = []
    for f in vw.faces_of_role(taxi):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            struck.update(ring)
        ring = vw.rings[f.id]
        if len(ring) >= 3:
            g = Polygon([vw.xy[v] for v in ring])
            if not g.is_empty:
                tpolys.append(g if g.is_valid else g.buffer(0.0))
    ttree = STRtree(tpolys) if tpolys else None
    # §30 (4) (13cc (i)): one apron cell short — an apron vertex the
    # no-step law COUPLES to a taxi vertex is struck with the band itself
    from .no_step import no_step_edges
    coupled: set[int] = set()
    for a, b, _cap, _d in no_step_edges(planar, law, airport):
        if a in struck and b not in struck:
            coupled.add(b)
        elif b in struck and a not in struck:
            coupled.add(a)
    struck |= coupled
    apron_vs: list[int] = []
    for f in vw.faces_of_role(("apron",)):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            apron_vs.extend(ring)
    if not apron_vs:
        return {}
    polys = {fid: poly for fid, _r, _g, poly in _pad_polys(planar, law)}
    xy = {v: vw.xy[v] for v in set(apron_vs)}
    out: dict[str, list[int]] = {}
    for cid, fids in faces.items():
        pad_vs: set[int] = set()
        for q in fids:
            pad_vs.update(_face_vertices(vw, q))
        shapes = [polys[q] for q in fids if q in polys]
        if not shapes:
            continue
        from shapely.ops import unary_union
        u = unary_union(shapes)
        got: list[int] = []
        for v in sorted(set(apron_vs)):
            if v in struck or v in pad_vs:
                continue
            pt = Point(*xy[v])
            d = u.distance(pt)
            if d > reach:
                continue
            # THE REACH STOPS AT A TAXIWAY BAND (owner RULINGS
            # 2026-09-13bj item 1; §30 (4)).  Striking the band's own
            # vertices is not enough: MEASURED on the twin fixture, an
            # apron lifted to the cluster's plane dragged the taxiway
            # welded to it 2.20 m through the apron's own no-step law.
            # The band's CATCHMENT is the boundary — an apron vertex
            # nearer a taxi- or runway-family face than the cluster pad
            # belongs to that band and keeps its own law.
            if ttree is not None:
                near = ttree.query_nearest(pt)
                if len(near):
                    if min(tpolys[int(i)].distance(pt) for i in near) < d:
                        continue
            got.append(v)
        if got:
            out[cid] = got
    return out


def _rolled_on(law: Law) -> tuple[str, ...]:
    return tuple(rolled_on_roles(law))


def _face_vertices(vw, fid: int) -> list[int]:
    out: list[int] = []
    for ring in [vw.rings[fid], *vw.holes[fid]]:
        out.extend(ring)
    return out


def cluster_apron_level(planar: PlanarMap, law: Law, airport: Airport
                        ) -> list[Row]:
    """§30 (4) THE APRON AROUND A BIG TERMINAL TAKES THE CLUSTER'S PLANE
    (owner RULINGS 2026-09-13bj item 1, verbatim: "it's acceptable to
    flatten large apron areas around big terminals if needed to
    accommodate a large terminal cluster ... as long as it remains
    feasible with grade laws and taxiways").

    One ONE-WAY row per apron vertex in :func:`cluster_apron_faces`: the
    vertex against THE CLUSTER PAD'S OWN MEAN (every rim vertex at
    ``1/n``, the same leader shape :func:`pad_frontage_level` uses in the
    other direction), the APRON as the follower.  So the stands at the
    terminal come out flat at the terminal's level, and the pad is never
    pulled by the apron it is flattening — 10l's direction still holds
    for the pad's own level, which is fitted to its frontage first.

    Priced at the LAW's own weight (:data:`CLUSTER_REACH_RULING` is in
    no heavier family), so the apron's hard caps, the pad's 1 % ceiling
    and every taxi row outrank it: where one plane cannot be had the
    apron stays graded and ``verify`` reports the residual, which is
    exactly the feasibility clause of §30 (4)."""
    got = cluster_apron_faces(planar, law, airport)
    if not got:
        return []
    groups = {ref.split("cluster:", 1)[1]: group
              for _f, ref, group, _q in plane_groups(planar, law, airport)
              if ref.startswith("cluster:")}
    rows: list[Row] = []
    for cid, vs in sorted(got.items()):
        group = groups.get(cid)
        if not group:
            continue
        src = Source(GEN_LEVEL, CLUSTER_REACH_RULING
                     + " (owner 2026-09-13bj item 1; spec §30 (4))",
                     (f"cluster:{cid}", f"apron_vertices:{len(vs)}"))
        base = {v: -1.0 / len(group) for v in group}
        for v in vs:
            terms = dict(base)
            terms[v] = terms.get(v, 0.0) + 1.0
            rows.extend(_two_sided(tuple(terms.items()), src, (v,)))
    return rows
