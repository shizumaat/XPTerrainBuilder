"""AN APRON FACE NEVER CARRIES A TERRACE (owner RULINGS 2026-10-02v (2),
issues #189 and #253) — the per-EDGE law of ``planar/shapes.build_shapes``
and its third weld, split out of ``shapes.py`` by the planar layer's
1,000-line budget (as the 30bk mouth weld was).

Round one (#189) welded the LABELS of an apron face.  A ``uf.union`` is
GLOBAL, so a label pair welded through one apron face lost its joint on
every edge between those labels: at KCLT all five joints went (5 -> 0)
although two of the edges were ``apron|parking_lot`` and
``parking_lot|parking_lot``, against the ruling's "terraces stay lawful
GROUNDSIDE" (#253, RULINGS 2026-10-02y).  The law is carried per EDGE now
(:func:`inside_apron_body`), read by the ONE label reader
(``planar.shapes.straddles``) and by the contour derivation; the weld that
remains consolidates IDENTITY only, never across a pair a surviving joint
edge separates."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import airside_stage_roles, family
from ..model.planar import NO_SHAPE, PlanarMap, is_osm_ribbon_ref, shares_gap_part

__all__ = ["weld_airside_faces", "airside_apron_roles", "airside_face_sets",
           "inside_apron_body", "separated_label_pairs", "declarable_pairs",
           "separator_faces"]

#: A MAPPED-ROAD RIBBON IS UNLABELLED (#100 round 4, lane roadmint100e;
#: RULINGS 2026-09-30aa rules 1-2; moved here from ``shapes._label_others``
#: by the 1,000-line file law): its own vertices carry no shape, as a
#: crossing road's do (08r-2) — its rows all survive the filter and it ramps
#: at its own law (``shapes._label_roads`` skips it).  roadweld100's
#: ``_label_ribbons`` gave them the majority contact shape, and a ribbon
#: running from apron A to apron B then carried A-labelled vertices onto B's
#: rim edges: every such edge is outside the apron body, so
#: ``separated_label_pairs`` read (A, B) as SEPARATED and the airside's own
#: weld through its apron faces was refused — measured HECA: 58 shapes for
#: main's 52.
RIBBON_UNLABELLED = True


def airside_apron_roles(law: Law) -> frozenset[str]:
    """THE AIRSIDE APRON BODY ROLES — the ruling's subject, "an apron
    face", derived from the law tables and never typed here: the APRON BODY
    roles (``emit.toml [terrace] one_shape_roles``, 30bk's "ONE CLASS: the
    apron body roles" — the apron and the junction body, which is apron-like
    pavement no route reaches) that are also AIRSIDE PAVEMENT
    (:func:`law.tables.airside_stage_roles` — §20b stage 1's roles, which
    exclude the rigid pad and every groundside class, and which are exactly
    ``terrace.shape_roles``).

    REPORTED, not decided (lane ``apronjoint189``): the brief's wider
    phrase is "airside pavement roles", which is ``airside_stage_roles``
    whole — the taxi and runway families too.  That reading overturns
    three twins the owner has witnessed and one ruling; see the PR for
    #189.  The scope here is the ruling's own subject."""
    return frozenset(law.tables.emit.terrace.one_shape_roles) & airside_stage_roles(law)


def airside_face_sets(pm: PlanarMap, law: Law) -> dict[str, frozenset[int]]:
    """The ``PlanarMap`` fields this law publishes, ready to
    ``dataclasses.replace`` onto the map — the apron body faces, the
    airside pavement faces and the road vertices
    (:func:`inside_apron_body` reads all three).

    The first is :func:`airside_apron_roles`, the ruling's SUBJECT ("an
    apron face"); the second is §20b stage 1's roles
    (:func:`law.tables.airside_stage_roles`), the sides that do not VETO —
    every GROUNDSIDE class and the RIGID pad are outside it, so a pair with
    one of those on it keeps its joint.  The third is the ROAD SEPARATOR
    (owner RULINGS 2026-09-08r-2, kept from round one's ``on_road``): every
    vertex incident to a ``road_cross_section`` face."""
    apron = airside_apron_roles(law)
    if not apron:
        return {k: frozenset() for k in _FIELDS}
    airside, roadish = airside_stage_roles(law), set(family(law, "road_cross_section").roles)
    return dict(zip(_FIELDS, (
        frozenset(f for f, fa in pm.faces.items() if fa.role in apron),
        frozenset(f for f, fa in pm.faces.items() if fa.role in airside),
        frozenset(v for f in separator_faces(pm, roadish)
                  for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)))))


def separator_faces(pm: PlanarMap, roadish: _t.AbstractSet[str]) -> list:
    """THE ROAD SEPARATORS (owner RULINGS 2026-09-08r-2): the road-family
    faces — WITHOUT the mapped-road RIBBONS (RULINGS 2026-09-30aa rules 1-2,
    owner 30z (1); issue #100 round 4).  A ribbon is a stage-2 face WELDED
    to the airside at the rim's own nodes: it takes the airside's level and
    never gives one, so it is no separator either.  MEASURED (HECA, lane
    roadmint100e, replay vs sw1014): read as separators, 238 ribbons made
    every welded apron rim vertex a road vertex, so apron pairs touching
    one were never "inside the apron body" — 22 joints where main has 0
    (``apron|apron`` 8 edges), 58 shapes for 52, 1,014 of the apron's own
    rows withdrawn across the new joints and the apron pulled 2.03 m at
    30.12313852458, 31.41538836594.  The 1206 corridor faces stay the
    separators they were."""
    return [f for f in pm.faces.values()
            if f.role in roadish and not is_osm_ribbon_ref(getattr(f, "ref", ""))]


#: the ``PlanarMap`` fields :func:`airside_face_sets` fills, in order
_FIELDS = ("no_terrace_faces", "airside_pavement_faces", "road_separator_vertices")


def inside_apron_body(pm: PlanarMap, ids: _t.Iterable[int]) -> bool:
    """THE LAW, PER EDGE (owner RULINGS 2026-10-02v (2), issue #253):
    whether the vertices ``ids`` all lie INSIDE the apron body, where "an
    apron face never carries a terrace" — the faces incident to EVERY one
    of them include an apron face and are ALL airside pavement.

    THE #253 DEFECT this replaces.  Round one (#189) welded the LABELS of
    an apron face through ``uf.union``, and a union is GLOBAL: a label pair
    welded through one apron face lost its joint on every edge between
    those labels.  At KCLT that took all five joints (5 -> 0) although the
    edge census was ``apron|apron`` 8, ``apron|parking_lot`` 1,
    ``parking_lot|parking_lot`` 1 — the groundside joint went with the
    airside one, against the ruling's "terraces stay lawful GROUNDSIDE".

    So the joint is carried per EDGE, not per label pair.  The common-face
    reading is what makes it an edge test: the two SIDES of a planar edge
    are the faces incident to both its endpoints, and a chord across one
    apron's interior has that apron alone.  The OPEN BOUNDARY is not a
    face, so an apron ring edge against it is inside the apron body (#189's
    own pair); a ``parking_lot`` / ``groundside_pavement`` / service-road
    side, and a RIGID pad (28b), are faces outside ``airside_stage_roles``
    and veto.

    THE ROAD'S OWN STEP IS NOT THE APRON'S (owner RULINGS 2026-09-08r-2,
    kept from round one's ``on_road``).  A road running ALONG a boundary
    takes the level of the shape it is welded to and "the step stands at
    the road's FAR edge ... B's faces along it carry two labels and the
    contour hugs their edge inside B".  That second label reaches B only
    through the road weld and the ROAD is the separator, so a pair touching
    a road vertex is not inside the apron body however airside its sides
    are: the step is the road's, declared at the road's edge."""
    if not pm.no_terrace_faces:
        return False
    common: set[int] | None = None
    for v in ids:
        if v in pm.road_separator_vertices:
            return False
        vert = pm.vertices.get(v)
        if vert is None:
            return False
        fs = set(vert.incident_faces)
        common = fs if common is None else (common & fs)
        if not common:
            return False
    if not common or not (common & pm.no_terrace_faces):
        return False
    return common <= pm.airside_pavement_faces


def declarable_pairs(pm: PlanarMap, pairs: _t.Iterable[tuple[int, int]]
                     ) -> list[tuple[int, int]]:
    """``pairs`` without the ones INSIDE THE APRON BODY — the contour
    derivation's filter (``planar.shapes._contour_joints``).  A pair inside
    the apron body is no terrace, so it is not a joint pair, and a contour
    of nothing but such pairs is not declared at all.  The SAME predicate
    :func:`planar.shapes.straddles` reads, so the sidecar record and the
    row withdrawal can never diverge — #189's class is a step with no row
    AND no declaration.  A pair INSIDE ONE GAP PART is no terrace either
    (spec §55 (15) rule A+C: a part is one shape by kind, its knives are its
    only joints — ``model.planar.shares_gap_part``, read by ``straddles``
    too)."""
    return [q for q in pairs
            if not inside_apron_body(pm, q) and not shares_gap_part(pm, q)]


def separated_label_pairs(pm: PlanarMap, label: dict[int, int]
                          ) -> frozenset[tuple[int, int]]:
    """The label pairs a SURVIVING joint edge separates: the pairs carried
    by a planar edge that is NOT :func:`inside_apron_body`.  Those two
    labels are two shapes wherever that edge is, so they are never merged
    (#253: that merge is what lost KCLT's ``parking_lot|parking_lot``
    joint)."""
    # A MAPPED-ROAD RIBBON'S EDGE IS NO WITNESS (#100 round 4, lane
    # roadmint100e; RULINGS 2026-09-30aa rules 1-2): the ribbon is welded to
    # the airside and stage 2's, and its edges are edges the airside does
    # not have without it — measured HECA: a ribbon through a zone pocket
    # inside dsf:objpav399's hole ran from a hole-ring vertex (shape 0) to
    # a pad rim vertex (shape 15) and that one edge kept the two apart
    # (53 shapes for main's 52, a joint [0, 15], the apron pulled 2.89 m).
    ribbon = {fid for fid, f in pm.faces.items()
              if is_osm_ribbon_ref(getattr(f, "ref", ""))}
    out: set[tuple[int, int]] = set()
    for e in pm.edges.values():
        if e.left_face in ribbon or e.right_face in ribbon:
            continue
        la, lb = label.get(e.a, NO_SHAPE), label.get(e.b, NO_SHAPE)
        if la != NO_SHAPE and lb != NO_SHAPE and la != lb \
                and not inside_apron_body(pm, (e.a, e.b)):
            out.add((min(la, lb), max(la, lb)))
    return frozenset(out)


def weld_airside_faces(pm: PlanarMap, law: Law, label: dict[int, int],
                       uf: _t.Any, stats: _t.Any,
                       separated: frozenset[tuple[int, int]] = frozenset()) -> None:
    """APRONS ALWAYS GRADE (owner RULINGS 2026-10-02v (2), issue #189):
    "an apron face never carries a terrace — a contour joint inside one
    apron face does not withdraw the 29ac pavement fallback; terraces stay
    lawful groundside only (KCLT 35.2068281, -80.9422880 becomes a ramp)".

    THE DEFECT.  08k declares a contour joint through every face whose
    vertices carry two shape labels (``planar/shapes._contour_joints``) and
    ``pipeline/shapes.apply_joints`` then drops EVERY row across it — the
    29ac ``road_max_grade pavement fallback`` among them, which is the only
    family left on a bare apron ring edge.  MEASURED (#189, KCLT capture at
    main 52e2e2ae): v11221 (212.26 m) and v11222 (214.85 m) are CONSECUTIVE
    RING VERTICES of one apron face, ``apron#445`` (``dsf:pol43``), with no
    road within reach; shapes 1 and 6 met inside it, the stage declared the
    contour, and the pair carried NO row at all — 2.59 m over 4.47 m
    (57.9 %) against an 8 % cap.  30bk's mouth weld does not reach it: a
    label pair that also meets at a class change somewhere (apron -> road /
    lot / taxiway) is KEPT, and the step then stands inside the apron
    anyway.

    THE FIX, AT THE JOINT'S DERIVATION — AND WHY THIS IS NO LONGER THE
    WELD (owner RULINGS 2026-10-02y, issue #253).  Round one welded the
    LABELS of an apron face, and a ``uf.union`` is GLOBAL: a label pair
    welded through one apron face lost its joint on EVERY edge between
    those labels.  At KCLT that took all five joints (5 -> 0) although two
    joint edges were ``apron|parking_lot`` and ``parking_lot|parking_lot``
    — a groundside terrace, which 10-02v (2) keeps lawful, died with the
    airside one.  So the law is carried PER EDGE now, by
    :func:`inside_apron_body`, which :func:`planar.shapes.straddles` (the
    one reader of the labels: the row filter, the published pair caps and
    the joint-edge census all go through it) and the contour derivation
    (``planar.shapes._contour_joints``) both consult: a pair inside the
    apron body has no joint to declare, no row to withdraw and no sidecar
    ``terrace_joints`` record, while a pair with a GROUNDSIDE side (a lot,
    groundside pavement, a service road, a terrain face) or a RIGID pad
    side (28b) keeps all three.

    WHAT IS LEFT HERE IS IDENTITY, NOT LAW.  Two labels that no surviving
    joint edge separates (``separated``, :func:`separated_label_pairs`)
    are indistinguishable to every consumer of the joints — there is no
    edge anywhere at which they are two shapes — so an apron face carrying
    them records ONE shape, as round one did.  A pair a surviving joint
    edge DOES separate is never merged: that merge is #253.  The weld is
    therefore a no-op for the joint law and cannot lose a groundside
    joint.

    THE ROAD'S OWN STEP IS NOT THE APRON'S (owner RULINGS 2026-09-08r-2,
    kept).  A road running ALONG a boundary takes the level of the shape it
    is welded to and "the step stands at the road's FAR edge ... B's faces
    along it carry two labels and the contour hugs their edge inside B"
    (``planar/shapes._label_roads``).  That second label reaches the apron
    face only through the road weld, and the road is the SEPARATOR, so a
    vertex incident to a road-family face is not read here: the step is the
    road's, declared at the road's edge, not a terrace inside the apron.
    #189's pair has "no road within reach", so the weld reaches it.

    The test reads ROLES only, never the DEM — 29k's earned-drop admission
    governs what is left (a groundside or pad face), not an apron."""
    roles = airside_apron_roles(law)
    if not roles:
        return
    roadish = set(family(law, "road_cross_section").roles)
    on_road = {v for f in separator_faces(pm, roadish)     # never a ribbon (#100)
               for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        labs = sorted({l for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)
                       if v not in on_road and (l := label.get(v, NO_SHAPE)) != NO_SHAPE})
        if len(labs) < 2:
            continue
        for l in labs[1:]:
            if _merges_separated(uf, separated, labs[0], l):
                stats.airside_faces_kept += 1
                continue
            if uf.union(labs[0], l):
                stats.welded_airside_faces += 1
    for v in label:
        label[v] = uf.find(label[v])


def _merges_separated(uf: _t.Any, separated: frozenset[tuple[int, int]],
                      a: int, b: int) -> bool:
    """Whether merging ``a``'s class with ``b``'s would put the two labels
    of a SEPARATED pair in one shape.  Merging classes ``Ca`` and ``Cb``
    makes same-class exactly the pairs whose roots are ``{Ca, Cb}``, so the
    test needs no rollback — and it catches the TRANSITIVE case (``A|B``
    and ``B|C`` welded through two faces while ``A|C`` is separated)."""
    if not separated:
        return False
    ends = {uf.find(a), uf.find(b)}
    return any({uf.find(x), uf.find(y)} == ends for x, y in separated)
