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

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..geom import cluster_outlines
from ..law import Law
from ..law.tables import design as design_law, rolled_on_roles
from ..model.airport import Airport
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap
from .pads import GEN_LEVEL, _pad_groups, _pad_polys, _two_sided
from .precedence import view

__all__ = ["cluster_reach_m", "cluster_polys", "cluster_pad_faces",
           "YIELDED", "TOUCHING_STEPS", "NO_OUTLINE", "pad_cluster_mismatch",
           "plane_groups", "cluster_apron_faces", "cluster_apron_level",
           "CLUSTER_REACH_RULING"]


def cluster_reach_m(law: Law) -> float:
    """§30 (4): ``[design] cluster_apron_reach_m`` — the plan distance
    within which an apron vertex takes a CLUSTER pad's plane as its
    target (owner RULINGS 2026-09-13bj item 1).  ONE derivation site; 0
    disables the reach."""
    return float(design_law(law).cluster_apron_reach_m)


#: §16g (10) (2): the clusters :func:`cluster_polys` dropped for carrying
#: no footprint outline (a plan written before §16g (7) (1)'s ring field).
#: Read by the build's say-line so a stale frame is never mistaken for an
#: airport with no terminal.
NO_OUTLINE: list[str] = []

#: The outline derivation is ~7 s over HECA's 2,638 clusters and three
#: readers ask for it per generator pass (the pad faces, the offsets, the
#: mismatch census).  A two-entry memo keyed on the airport object keeps
#: it ONE derivation in fact as well as in law — the same shape
#: ``planar/cluster._MEMO`` uses for the clusters themselves.
_POLY_MEMO: list[tuple[int, _t.Any, float, list]] = []


def cluster_polys(airport: Airport | None, min_m2: float = 0.0,
                  law_touch: float | None = None
                  ) -> list[tuple[_t.Any, Polygon]]:
    """§30 (4): each CLUSTER carried on ``Airport.clusters``
    (``planar/cluster.py``, computed once at load beside the pack
    partition and the groups) with its FOOTPRINT UNION as one plan
    polygon in the PLANAR FRAME's metres.

    §16g (7) (1) / (10) (2) (owner RULINGS 2026-09-14c item 1, 14x): the
    union is of the cluster's OUTLINE RINGS (``PlanCluster.rings``),
    never of its part BOXES.  The box union is what put a pad 66 m
    outside KCLT's terminal inside its cluster and cost §30 (4) (5) a
    whole yield gate (13ci) — a rotated building's lat/lon box is not its
    footprint.  A cluster whose plan predates the ring field carries NO
    outline and is DROPPED, counted in :data:`NO_OUTLINE` — there is no
    box fallback, and that is deliberate: 13ci measured exactly what
    pricing a box union costs (KCLT's `building91`, a separate building
    65.81 m from the terminal, lifted 3.63 m onto the terminal's plane
    and 2,406 taxi-family vertices moved with it, worst 2.07 m).  13ci
    answered that with a touching-component gate; (10) answers it by
    never reading a box as a footprint at all, so a stale plan simply
    gets no cluster pad and the airport keeps the pre-14x derivation.

    ``min_m2`` (``[placement] cluster_pad_min_m2``, §16g (9)'s one
    remaining job for that key) keeps only the clusters big enough for a
    §30 (4) cluster PAD PLANE; 0 takes them all.

    ``constraints`` may not import ``planar`` (the layering twin), which
    is why the derivation travels on the airport and only its GEOMETRY
    is taken here."""
    cl = getattr(airport, "clusters", None) or ()
    NO_OUTLINE.clear()
    if not cl or airport is None:
        return []
    touch = float(law_touch) if law_touch is not None else 0.0
    got = counts = None
    for k, ap, t0, cached in _POLY_MEMO:
        if k == id(airport) and ap is airport and t0 == touch:
            got, counts = cached, {}
            break
    if got is None:
        to_xy, _to_ll = airport.frame.transformers()
        got, counts = cluster_outlines(cl, to_xy, touch)
        _POLY_MEMO.append((id(airport), airport, touch, got))
        del _POLY_MEMO[:-2]
    if counts.get("no_rings"):
        NO_OUTLINE.extend(str(c.id) for c in cl if not (getattr(c, "rings", ()) or ()))
    out: list[tuple[_t.Any, Polygon]] = []
    for c, g in got:
        if min_m2 > 0.0 and float(getattr(c, "area_m2", 0.0)) < min_m2:
            continue
        out.append((c, g))
    return out


def cluster_pad_faces(planar: PlanarMap, law: Law, airport: Airport | None
                      ) -> dict[str, list[int]]:
    """``cluster id -> the rigid FACE ids its footprint union stands on``,
    for the clusters over ``[placement] cluster_pad_min_m2`` (§16g (9):
    that key's ONE remaining job).

    The test is INTERSECTION with the UNION, never with its hull: a
    terminal's hull spans the apron between its concourses and would
    swallow every stand's own structure (measured at KCLT, the hull is
    864,000 m2 against a 379,000 m2 union).

    §16g (10) (2) REPLACES 13ci's YIELD GATE (owner RULINGS 2026-09-14x,
    14z).  The gate kept the touching COMPONENT holding the largest face
    and yielded every other, because the union was a box union that
    reached pads outside the footprint; MEASURED at HECA it kept ONE face
    of 22 and ONE of 73 — 25.6 % and 21.5 % of the intersected pad area —
    and starved ``plane_groups``, ``cluster_pairs`` and
    ``cluster_offsets`` alike.  Under (10) the cluster's pad IS its own
    outline, so the question is no longer "which of these pads is really
    the terminal's" but simply WHICH FACES THIS CLUSTER'S OWN POLYGON IS:
    a face whose area is mostly inside the cluster's outline.  A face the
    outline merely clips keeps its own plane and is still named in
    :data:`YIELDED`, which should now be EMPTY at an airport whose pads
    are derived from the clusters.  The apron reach (13ci, disarmed at
    13ce) keeps the union reading through :func:`cluster_apron_faces`."""
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    if min_m2 <= 0.0:                 # 0 disarms the cluster PAD PLANE
        return {}
    YIELDED.clear()
    got, _by_face, yielded = _face_map(planar, law, airport, min_m2)
    YIELDED.update(yielded)
    return got


def _face_map(planar: PlanarMap, law: Law, airport: Airport | None,
              min_m2: float
              ) -> "tuple[dict[str, list[int]], dict[int, list[str]], dict[str, tuple[int, ...]]]":
    """THE ONE READING of the cluster↔pad relation: ``(faces per cluster,
    clusters per face, the clipped faces per cluster)``.

    :func:`cluster_pad_faces` asks it of the clusters over
    ``cluster_pad_min_m2``; :func:`pad_cluster_mismatch` asks it of the
    whole population.  One derivation, two readers — never two."""
    got: dict[str, list[int]] = {}
    by_face: dict[int, list[str]] = {}
    yielded: dict[str, tuple[int, ...]] = {}
    pairs = cluster_polys(airport, min_m2, _touch_m(law))
    if not pairs:
        return got, by_face, yielded
    polys = _pad_polys(planar, law)
    if not polys:
        return got, by_face, yielded
    tree = STRtree([p[3] for p in polys])
    for c, u in pairs:
        keep: list[int] = []
        clipped: list[int] = []
        for i in tree.query(u, predicate="intersects"):
            fid, _ref, _grp, poly = polys[int(i)]
            if poly.area <= 0.0:
                continue
            if poly.intersection(u).area >= _OWN_FACE_SHARE * poly.area:
                keep.append(int(fid))
                by_face.setdefault(int(fid), []).append(c.id)
            else:
                clipped.append(int(fid))
        if clipped:
            yielded[c.id] = tuple(sorted(clipped))
        if keep:
            got[c.id] = sorted(keep)
    return got, by_face, yielded


def pad_cluster_mismatch(planar: PlanarMap, law: Law,
                         airport: Airport | None) -> list[dict[str, _t.Any]]:
    """§16g (10) (3) `pad_cluster_mismatch` (owner RULINGS 2026-09-14x,
    verbatim: *"no building, or cluster can span multiple pads, if it
    does, it means we didn't identify the building shape or cluster
    correctly"*) — CRITICAL, a misidentified shape, never seated over.

    Two rows, both from :func:`_face_map` over the WHOLE cluster
    population (not the cluster-pad threshold's subset):

    * ``cluster_spans_pads`` — one cluster is more than half of two or
      more emitted ``building`` faces;
    * ``pad_spans_clusters`` — one face is more than half claimed by two
      or more clusters.

    Under §16g (10) (2)'s derivation both are structurally impossible
    (each cluster's outline IS one pad), so a row here says the
    derivation did not hold — classify split one cluster's outline
    (a runway difference, a multipolygon), two clusters' outlines merged
    under the pad law's own union, or the pads came from the footprint
    cache because the plan carries no rings.  The record names the ref,
    the counterparties and a representative point, which is what the
    census needs to place it."""
    out: list[dict[str, _t.Any]] = []
    by_cluster, by_face, _clipped = _face_map(planar, law, airport, 0.0)
    if not by_cluster:
        return out
    _to_xy, to_ll = (airport.frame.transformers() if airport is not None
                     else (None, None))
    polys = {int(q[0]): (str(q[1]), q[3]) for q in _pad_polys(planar, law)}

    def _at(fid: int) -> tuple[float | None, float | None]:
        q = polys.get(fid)
        if q is None or to_ll is None:
            return None, None
        p = q[1].representative_point()
        lon, lat = to_ll(p.x, p.y)
        return round(float(lat), 7), round(float(lon), 7)

    for cid, fids in sorted(by_cluster.items()):
        if len(fids) > 1:
            lat, lon = _at(fids[0])
            out.append({"kind": "cluster_spans_pads", "ref": cid,
                        "others": [polys[f][0] for f in fids if f in polys],
                        "lat": lat, "lon": lon})
    for fid, cids in sorted(by_face.items()):
        if len(cids) > 1:
            lat, lon = _at(fid)
            out.append({"kind": "pad_spans_clusters",
                        "ref": (polys[fid][0] if fid in polys else str(fid)),
                        "others": sorted(cids), "lat": lat, "lon": lon})
    return out


#: §16g (10) (2): the share of a pad face's own area that must lie inside
#: a cluster's outline for the face to BE that cluster's pad.  A half is
#: the only defensible split — a face more than half inside one cluster
#: is inside no other — and it makes ``pad_cluster_mismatch`` decidable
#: by the same reading the census takes.
_OWN_FACE_SHARE = 0.5


#: §30 (4) (5): the member faces the gate turned away, per cluster — read
#: by the publication so the report names them (the ruling's "reported
#: with the pad").
YIELDED: dict[str, tuple[int, ...]] = {}


#: §30 (4) (5) 13ci's TOUCHING-COMPONENT YIELD GATE IS DELETED
#: (owner RULINGS 2026-09-14x/14z).  It kept the connected component
#: of intersected pads holding the largest face and yielded the rest,
#: because a cluster's PART-BOX union reached pads outside its
#: footprint.  Under §16g (7) (1) the union is the true OUTLINE and
#: under (10) (2) the pad IS that outline, so there is nothing left
#: to gate: MEASURED at HECA the gate kept 1 face of 22 and 1 of 73.
#: Refuted mechanisms are deleted, not kept gated.

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
    # CLUSTERS SHARING A FACE ARE ONE PLANE (measured, round 4).  A face
    # belongs to at most one plane, and ``setdefault`` gave it to whichever
    # cluster was enumerated first: KCLT's two terminal rows BOTH stand on
    # `building80`, so `unit:30#0` took it whole and `unit:31#0` was left
    # with `building91`'s 18 vertices alone — a "cluster" of one face with
    # nothing to cross-link to.  That, and not the `_pairs` decimation, is
    # why the PAD-ONLY arm came out byte-identical to DISARM twice.  The
    # clusters are therefore UNIONED over the faces they share.
    root: dict[str, str] = {cid: cid for cid in faces}

    def _find(a: str) -> str:
        while root[a] != a:
            root[a] = root[root[a]]
            a = root[a]
        return a

    owner: dict[int, str] = {}
    for cid in sorted(faces):
        for fid in faces[cid]:
            other = owner.get(fid)
            if other is None:
                owner[fid] = cid
            else:
                ra, rb = _find(cid), _find(other)
                if ra != rb:
                    root[max(ra, rb)] = min(ra, rb)
    of_face: dict[int, str] = {fid: _find(cid)
                               for fid, cid in sorted(owner.items())}
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


#: How many CROSS-LINKS one member face of a cluster contributes at most.
#: A plane has three degrees of freedom, so three would tie it; the cap is
#: ``pads._MAX_PAIRWISE`` for the same reason a rim is decimated to it —
#: a well-spread subset witnesses the plane and the row count stays O(n).
_CROSS_MAX = 40

#: What :func:`cluster_pairs` last counted, for the generator's own stats
#: line (``constraints.generate`` publishes ``pads.<key>``).
STATS: dict[str, int] = {}


#: §16g (8): per cluster, the REFERENCE face its other pads are derived
#: from, and the per-pad authored floor the derivation used — read by the
#: publication so the report names the plane it built.
REFERENCE: dict[str, int] = {}
DERIVED: dict[str, dict[int, float]] = {}
#: §16g (8) (2): pads carrying bodies of DIFFERENT authored floors, with
#: the spread the pad took the lowest of.
OFFSET_SPREAD: dict[_t.Any, float] = {}
#: §16g (10) (owner RULINGS 2026-09-14x): the DECLARED TERRACE STEPS
#: between touching clusters' pads — ``(cluster a, cluster b) -> metres``
#: between their authored ground floors.  (8)'s within-a-unit derived
#: pads are withdrawn into this.
TOUCHING_STEPS: dict[tuple[str, str], float] = {}


def cluster_offsets(planar: PlanarMap, law: Law, airport: Airport | None
                    ) -> dict[int, float]:
    """§16g (8) AS NARROWED BY (10) (owner RULINGS 2026-09-14x): THE
    OFFSETS BETWEEN TOUCHING CLUSTERS' PADS ARE DECLARED TERRACE STEPS.

    14u derived the OTHER pads of one unit from a reference pad, because
    HECA's T3 district chained across 23 pads spanning 29.99 m and one
    datum floated its bodies against their own pads.  14x answers the
    same defect one level up: a touching body at a different authored
    floor is a DIFFERENT BUILDING with its own cluster and its own pad,
    so there is no longer a cluster standing on several pads to derive
    within — and what is left is the STEP between two clusters whose
    outlines touch.  That step is the ground law's (§23, a declared
    terrace joint), not a pad row: each pad is already one plane at its
    own level and pricing the step would be the design surface telling
    the pack author how to terrace.

    So this mints NO row (it returns ``{}`` and always has for the
    ``rel=`` channel's purposes) and PUBLISHES the joints:
    :data:`TOUCHING_STEPS` maps ``(cluster a, cluster b)`` to the metres
    between their authored ground floors, for the sidecar and the
    report.  :data:`REFERENCE` / :data:`DERIVED` stay as keys so the
    publication's shape is unchanged; they are empty under (10).
    :data:`OFFSET_SPREAD` keeps its (8) (2) meaning — a CLUSTER whose own
    member bodies disagree about the ground floor by more than
    ``floor_split_m`` cannot exist under (10) (1), so a non-empty
    reading here is a defect in the split and is named."""
    REFERENCE.clear()
    DERIVED.clear()
    OFFSET_SPREAD.clear()
    TOUCHING_STEPS.clear()
    if airport is None:
        return {}
    touch = float(law.tables.structures.placement.footprint_touch_m)
    split = float(law.tables.structures.placement.floor_split_m)
    pairs = cluster_polys(airport, 0.0, touch)
    if len(pairs) < 2:
        return {}
    floor_of: dict[str, float] = {}
    for c, _u in pairs:
        fl = [f for f in (getattr(c, "floors", ()) or ())]
        if not fl:
            continue
        floor_of[c.id] = min(fl)
        if split > 0.0 and max(fl) - min(fl) > split:
            OFFSET_SPREAD[c.id] = round(max(fl) - min(fl), 3)
    tree = STRtree([u for _c, u in pairs])
    for i, (c, u) in enumerate(pairs):
        if c.id not in floor_of:
            continue
        for j in tree.query(u.buffer(touch), predicate="intersects"):
            j = int(j)
            if j <= i:
                continue
            d, v = pairs[j]
            if d.id not in floor_of or u.distance(v) > touch:
                continue
            step = round(floor_of[d.id] - floor_of[c.id], 3)
            if abs(step) > 0.0:
                TOUCHING_STEPS[(c.id, d.id)] = step
    return {}



def cluster_pairs(planar: PlanarMap,
                  faces: _t.Sequence[_t.Sequence[int]]
                  ) -> "tuple[list[tuple[int, int]], int]":
    """§30 (4): THE PAIRS A CLUSTER'S PLANE IS PRICED OVER — each member
    face's OWN complete set, as if it stood alone, PLUS explicit
    CROSS-LINKS between the faces.  Returns ``(pairs, cross-link count)``.

    THE MERGED READING WAS MEASURED AND REFUTED (RULINGS 2026-09-13cc,
    lane round 3).  Handing ``pads._pairs`` the concatenated rim let its
    decimation over ``_MAX_PAIRWISE`` do both jobs badly: KCLT's 865 + 18
    vertex cluster priced 1,624 pairs of which only **40 crossed between
    the faces**, while ``building91``'s own plate fell from 153 pairwise
    cap-0 rows to **17** consecutive ones — the merge took nine tenths of
    the small pad's rigidity away and gave it 40 weak links back.  The
    arms proved it inert: PAD-ONLY came out BYTE-IDENTICAL to DISARM
    (graded `bde3f0aff32e`, patch `47c91c99b599`).

    So the two jobs are separated.  Each face keeps exactly the pairs it
    would have alone — ``_pairs`` unchanged, per face — and the faces are
    then tied by links from every (decimated) vertex of each junior face
    to its NEAREST vertex in the SENIOR face (the largest rim).  Nearest,
    because a link is a weld in all but name and the shortest one is the
    one the geometry already implies; from every vertex, because a plane
    has three degrees of freedom and a handful of long links leaves a
    small face free to tilt about them."""
    live = [list(vs) for vs in faces if len(vs) >= 2]
    if not live:
        return [], 0
    from .pads import _MAX_PAIRWISE, _pairs
    pairs: set[tuple[int, int]] = set()
    for vs in live:
        for a, b in _pairs(vs):
            if a != b:
                pairs.add((min(a, b), max(a, b)))
    n_cross = 0
    if len(live) > 1:
        senior = max(live, key=len)
        xy = {v: planar.vertices[v].xy for vs in live for v in vs
              if v in planar.vertices}
        sen = [(v, xy[v]) for v in senior if v in xy]
        for vs in live:
            if vs is senior:
                continue
            step = max(1, len(vs) // _CROSS_MAX)
            for v in vs[::step]:
                q = xy.get(v)
                if q is None or not sen:
                    continue
                w = min(sen, key=lambda s: ((s[1][0] - q[0]) ** 2
                                            + (s[1][1] - q[1]) ** 2))[0]
                if w != v:
                    key = (min(v, w), max(v, w))
                    if key not in pairs:
                        pairs.add(key)
                        n_cross += 1
    return sorted(pairs), n_cross


def _touch_m(law: Law) -> float:
    """§16g (7) (1) / (10) (2): ``[placement] footprint_touch_m`` — ONE
    read, the same tolerance the cluster was CHAINED with, used to CLOSE
    its outline (``geom.cluster_outlines`` rule 2)."""
    return float(law.tables.structures.placement.footprint_touch_m)
