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
* THE APRON AROUND IT: §30 (4)'s reach / collar rows were measured,
  disarmed (14bk) and DELETED (jetway-strip spec §6 Q3); the apron under
  the jetways is levelled by the JETWAY STRIP projection instead
  (``constraints/jetway_strip.py``, ``solve/project_strip.py``).

It lives apart from ``constraints/pads.py`` only because that file is at
the 1,000-line bar; ``pad_frontage_gs.py`` (§28) stands beside it for
exactly the same reason.  The CLUSTER itself is derived at load
(``planar/cluster.py``) and carried on ``Airport.clusters``: this layer
may not import ``planar``.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..geom import cluster_outlines
from ..law import Law
from ..law.tables import rolled_on_roles
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .pads import _pad_groups, _pad_polys
from .precedence import view

__all__ = ["cluster_polys", "cluster_pad_faces",
           "YIELDED", "TOUCHING_STEPS", "NO_OUTLINE", "pad_cluster_mismatch",
           "plane_groups", "cluster_offsets", "cluster_pairs"]


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
_POLY_MEMO: list[tuple[int, _t.Any, _t.Any, list]] = []


def airside_union(planar: PlanarMap, law: Law):
    """§16g (10) (5): the union of every AIRSIDE face of the emitted map —
    the runway family, the taxi family and the apron, straight off
    ``law.tables.rolled_on_roles`` so a new pavement role joins it with no
    code change.

    This is the design surface's OWN reading of the same region
    ``classify/evidence`` clipped the pads out of at mint time (there, the
    apt.dat runway slabs and 110 pages): the pads were cut from it, so
    pad and airside tile the same ground and the two readings agree where
    it matters.  Memoised per planar map — the census and the offsets
    both ask."""
    key = id(planar)
    for k, pm, got in _AIRSIDE_MEMO:
        if k == key and pm is planar:
            return got
    from shapely.ops import unary_union
    vw = view(planar, law)
    ps: list[Polygon] = []
    for f in vw.faces_of_role(tuple(sorted(rolled_on_roles(law)))):
        ring = vw.rings[f.id]
        if len(ring) < 3:
            continue
        g = Polygon([vw.xy[v] for v in ring],
                    [[vw.xy[v] for v in h] for h in vw.holes[f.id]
                     if len(h) >= 3])
        if not g.is_valid:
            g = g.buffer(0.0)
        if not g.is_empty and g.area > 0.0:
            ps.append(g)
    got = unary_union(ps) if ps else None
    _AIRSIDE_MEMO.append((key, planar, got))
    del _AIRSIDE_MEMO[:-2]
    return got


_AIRSIDE_MEMO: list[tuple[int, _t.Any, _t.Any]] = []


def cluster_polys(airport: Airport | None, min_m2: float = 0.0,
                  law_touch: float | None = None, airside=None
                  ) -> list[tuple[str, _t.Any, Polygon]]:
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
    akey = (id(airside), min_m2)
    for k, ap, t0, cached in _POLY_MEMO:
        if k == id(airport) and ap is airport and t0 == (touch, akey):
            got, counts = cached, {}
            break
    if got is None:
        # §46 (9) census row 5: the same INPUT ring population as
        # ``classify/evidence`` — the ENTRY projection, or the two reads
        # of one derivation would not agree
        to_xy = airport.frame.entry()
        got, counts = cluster_outlines(
            cl, to_xy, touch, airside=airside,
            # §16g (10) (7): the pad population is the WALLED clusters
            # over the threshold — the same one ``classify`` minted from,
            # so the census cannot report a mismatch for a cluster that
            # was never given a pad
            walled_only=True, min_m2=min_m2)
        _POLY_MEMO.append((id(airport), airport, (touch, akey), got))
        del _POLY_MEMO[:-2]
    if counts.get("no_rings"):
        NO_OUTLINE.extend(str(c.id) for c in cl
                          if not (getattr(c, "rings", ()) or ()))
    return list(got)


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
    are derived from the clusters."""
    min_m2 = float(law.tables.structures.placement.cluster_pad_min_m2)
    if min_m2 <= 0.0:                 # 0 disarms the cluster PAD PLANE
        return {}
    YIELDED.clear()
    got, _by_face, yielded = _face_map(planar, law, airport, min_m2)
    YIELDED.update(yielded)
    return got


def _base_ref(ref: object) -> str:
    """THE PAD IS ITS BASE REF (§16g (10) (11), lane ``v2padqp``).

    A pad minted in more than one piece carries the tree's own SPLIT
    SPELLING ``ref#k`` (``classify/roles`` :718, ``classify/evidence``
    :386), and every other consumer joins on ``ref.split("#")[0]``
    (``pipeline/publication`` :597/:672, ``constraints/structures``
    :263/:738, ``verify/structures`` :192/:198).  This reader did not,
    so ``building38`` and ``building38#1`` — ONE pad by everyone else's
    reading — counted as two and made their own cluster a
    ``cluster_spans_pads`` row (LEMD ``unit:25#1581``, measured).  One
    spelling, one join."""
    return str(ref).split("#")[0]


def _face_map(planar: PlanarMap, law: Law, airport: Airport | None,
              min_m2: float
              ) -> "tuple[dict[str, list[int]], dict[str, list[str]], dict[str, tuple[int, ...]]]":
    """THE ONE READING of the cluster<->pad relation: ``(faces per
    cluster, clusters per PAD REF, the clipped faces per cluster)``.

    A PAD IS A REF, NOT A FACE (measured on the round-2 HECA arm).  The
    planar map splits one minted pad into several faces carrying ONE
    ``building`` ref — a hole, a sliver merge, a joint contour — and
    counting FACES read 41 of those as "this cluster spans four pads"
    when all four were ``building32``.  The mismatch family asks whether
    a BUILDING spans two pads, and the pad the owner means is the one the
    design surface names.

    :func:`cluster_pad_faces` asks it of the clusters over
    ``cluster_pad_min_m2``; :func:`pad_cluster_mismatch` asks it of the
    whole population.  One derivation, two readers — never two."""
    got: dict[str, list[int]] = {}
    by_ref: dict[str, list[str]] = {}
    yielded: dict[str, tuple[int, ...]] = {}
    # §16g (10) (11) THE CENSUS CUTS THE CLUSTER WHERE THE MINT DOES.
    # ``classify/evidence._cluster_pads`` no longer pre-splits the outline
    # at an airside union when the ARRANGEMENT clip is armed (14ax), so
    # neither does this reader: two cutters disagreeing about where a
    # cluster ends IS the mismatch family's own false positive (LEMD's T4
    # cluster read as one 94,301 m2 piece here against three minted refs).
    # With the clip disarmed the mint still pre-splits, and so does this.
    pairs = cluster_polys(
        airport, min_m2, _touch_m(law),
        None if bool(law.tables.structures.placement.pad_airside_clip)
        else airside_union(planar, law))
    # §16g (10) (11) A PIECE THE MINT NEVER PADDED IS NOT A PAD.  The
    # mint drops every piece under ``[building_pad] min_area_m2``
    # (``classify/evidence._pads``), so a 7 m2 sliver of a cluster's
    # outline has no pad and cannot be one — judged here it made its own
    # building's ref a ``pad_spans_clusters`` row (LEMD ``unit:25#843/1``
    # and ``/2``, 7 and 3 m2, against a 94,301 m2 ``/0``).  This is the
    # same rule ``walled_only`` / ``min_m2`` already state at cluster
    # level: the census judges the population the mint minted.
    _min_area = float(law.tables.structures.building_pad.min_area_m2)
    if _min_area > 0.0:
        pairs = [p for p in pairs if p[2].area >= _min_area]
    if not pairs:
        return got, by_ref, yielded
    polys = _pad_polys(planar, law)
    if not polys:
        return got, by_ref, yielded
    tree = STRtree([p[3] for p in polys])
    # §16g (10) (11) (b) THE SHARE IS THE REF'S, NOT ONE FACE'S (owner
    # RULINGS 2026-09-15z; r1 named this class and left the lever untried).
    # A PAD IS A REF (the planar map splits one minted pad into several
    # faces), so "is this pad this cluster's" must be asked of the REF's
    # whole area.  Asked per FACE it took one SLIVER face of a big
    # neighbouring pad to list that whole ref: MEASURED at HECA,
    # ``unit:43#204`` holds 94 % of ``building254`` and 2 % of
    # ``building253`` (8 faces, 4,373 m2), ``unit:43#612/0`` 96 % and 8 %,
    # ``unit:43#844`` 100 % and 48 % — nine of the ten survivors.
    ref_area: dict[str, float] = {}
    for _fid, ref, _grp, poly in polys:
        ref_area[_base_ref(ref)] = ref_area.get(_base_ref(ref), 0.0) + poly.area
    seen: set[tuple[str, str]] = set()
    for cid, c, u in pairs:
        keep: list[int] = []
        clipped: list[int] = []
        share: dict[str, float] = {}
        hits: dict[str, list[int]] = {}
        for i in tree.query(u, predicate="intersects"):
            fid, ref, _grp, poly = polys[int(i)]
            if poly.area <= 0.0:
                continue
            base = _base_ref(ref)
            share[base] = share.get(base, 0.0) + poly.intersection(u).area
            hits.setdefault(base, []).append(int(fid))
        for base, inside in share.items():
            tot = ref_area.get(base, 0.0)
            if tot > 0.0 and inside >= _OWN_FACE_SHARE * tot:
                keep.extend(hits[base])
                if (cid, base) not in seen:
                    seen.add((cid, base))
                    by_ref.setdefault(base, []).append(cid)
            else:
                clipped.extend(hits[base])
        if clipped:
            yielded[cid] = tuple(sorted(set(yielded.get(cid, ())) | set(clipped)))
        if keep:
            got[cid] = sorted(set(got.get(cid, ())) | set(keep))
    return got, by_ref, yielded


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
    by_cluster, by_ref, _clipped = _face_map(
        planar, law, airport,
        float(law.tables.structures.placement.cluster_pad_min_m2))
    if not by_cluster:
        return out
    _to_xy, to_ll = (airport.frame.transformers() if airport is not None
                     else (None, None))
    polys = {int(q[0]): (_base_ref(q[1]), q[3]) for q in _pad_polys(planar, law)}

    def _at(fid: int) -> tuple[float | None, float | None]:
        q = polys.get(fid)
        if q is None or to_ll is None:
            return None, None
        p = q[1].representative_point()
        lon, lat = to_ll(p.x, p.y)
        return round(float(lat), 7), round(float(lon), 7)

    first_face: dict[str, int] = {}
    for fid, (ref, _g) in sorted(polys.items()):
        first_face.setdefault(ref, fid)
    for cid, fids in sorted(by_cluster.items()):
        refs = sorted({polys[f][0] for f in fids if f in polys})
        if len(refs) > 1:
            lat, lon = _at(fids[0])
            out.append({"kind": "cluster_spans_pads", "ref": cid,
                        "others": refs, "lat": lat, "lon": lon})
    for ref, cids in sorted(by_ref.items()):
        if len(cids) > 1:
            lat, lon = _at(first_face.get(ref, -1))
            out.append({"kind": "pad_spans_clusters", "ref": ref,
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



# §30 (4)'s APRON REACH — the one-way preference (13cc), the pad-to-collar
# join (14bf) and the collar PLANE as stage-1 rows (14bk) — was built,
# measured and DISARMED (HECA 11,363 airside vertices moved, 2,211 of them
# more than 500 m away), and is DELETED with its law keys (jetway-strip
# spec §6 Q3, default; BUILD ECONOMY: refuted mechanisms are deleted).  Its
# successor is the JETWAY STRIP, a post-stage-1 PROJECTION
# (``constraints/jetway_strip.py`` + ``solve/project_strip.py``), and its
# strike set lives on there as ``jetway_strip.strike_set`` — ONE derivation
# of "apron a pad may move".  The record is the spec and git.


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
    pairs = cluster_polys(
        airport, float(law.tables.structures.placement.cluster_pad_min_m2),
        touch, airside_union(planar, law))
    if len(pairs) < 2:
        return {}
    floor_of: dict[str, float] = {}
    for cid, c, _u in pairs:
        fl = [f for f in (getattr(c, "floors", ()) or ())]
        if not fl:
            continue
        floor_of[cid] = min(fl)
        if split > 0.0 and max(fl) - min(fl) > split:
            OFFSET_SPREAD[cid] = round(max(fl) - min(fl), 3)
    tree = STRtree([u for _i, _c, u in pairs])
    for i, (cid, c, u) in enumerate(pairs):
        if cid not in floor_of:
            continue
        for j in tree.query(u.buffer(touch), predicate="intersects"):
            j = int(j)
            if j <= i:
                continue
            did, _d, v = pairs[j]
            if did not in floor_of or u.distance(v) > touch:
                continue
            step = round(floor_of[did] - floor_of[cid], 3)
            if abs(step) > 0.0:
                TOUCHING_STEPS[(cid, did)] = step
    return {}



def cluster_pairs(planar: PlanarMap,
                  faces: _t.Sequence[_t.Sequence[int]],
                  own: _t.Optional[_t.Set[int]] = None
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
        # §16g (10) (11) (a) (owner RULINGS 2026-09-15z): A CROSS-LINK IS
        # BUILT FROM THE PAD'S OWN VERTICES WHERE IT HAS THEM.  The link
        # is what makes a cluster ONE plane (§30 (4)), and it must not be
        # the channel through which the plate moves the apron: a link
        # between two AIRSIDE-SHARED vertices is a two-sided row on two
        # columns the airside owns.  ``own`` (the non-airside vertices) is
        # preferred per face and the whole face is the fallback — a face
        # wholly inside pavement has no own vertex and keeps its links as
        # before, which is the same clause ``pads._pad_rows`` applies to
        # its plate.  MEASURED without it: the §30 (4) twin's two pads
        # came apart 0.86 m.
        def _pick(vs: list[int]) -> list[int]:
            if not own:
                return vs
            q = [v for v in vs if v in own]
            return q if len(q) >= 2 else vs
        sen_vs = _pick(senior)
        sen = [(v, xy[v]) for v in sen_vs if v in xy]
        for vs in live:
            if vs is senior:
                continue
            vs_l = _pick(vs)
            step = max(1, len(vs_l) // _CROSS_MAX)
            for v in vs_l[::step]:
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
