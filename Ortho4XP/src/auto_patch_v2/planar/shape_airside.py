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
from ..model.planar import NO_SHAPE, PlanarMap

__all__ = ["weld_airside_faces", "airside_apron_roles", "airside_face_sets",
           "inside_apron_body", "separated_label_pairs"]


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


def airside_face_sets(pm: PlanarMap, law: Law) -> tuple[frozenset[int], frozenset[int]]:
    """``(the apron body faces, the airside pavement faces)`` — the two
    face sets the per-edge law reads (:func:`inside_apron_body`).  The
    first is :func:`airside_apron_roles`, the ruling's SUBJECT ("an apron
    face"); the second is §20b stage 1's roles
    (:func:`law.tables.airside_stage_roles`), the sides that do not VETO —
    every GROUNDSIDE class and the RIGID pad are outside it, so a pair
    with one of those on it keeps its joint."""
    apron = airside_apron_roles(law)
    if not apron:
        return frozenset(), frozenset()
    airside = airside_stage_roles(law)
    return (frozenset(f for f, fa in pm.faces.items() if fa.role in apron),
            frozenset(f for f, fa in pm.faces.items() if fa.role in airside))


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
    and veto."""
    if not pm.no_terrace_faces:
        return False
    common: set[int] | None = None
    for v in ids:
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


def separated_label_pairs(pm: PlanarMap, label: dict[int, int],
                          no_terrace: frozenset[int],
                          airside: frozenset[int]) -> frozenset[tuple[int, int]]:
    """The label pairs a SURVIVING joint edge separates: the pairs carried
    by a planar edge that is NOT :func:`inside_apron_body`.  Those two
    labels are two shapes wherever that edge is, so they are never merged
    (#253: that merge is what lost KCLT's ``parking_lot|parking_lot``
    joint)."""
    out: set[tuple[int, int]] = set()
    for e in pm.edges.values():
        la, lb = label.get(e.a, NO_SHAPE), label.get(e.b, NO_SHAPE)
        if la == NO_SHAPE or lb == NO_SHAPE or la == lb:
            continue
        sides = set(pm.vertices[e.a].incident_faces) & set(pm.vertices[e.b].incident_faces)
        if sides and (sides & no_terrace) and sides <= airside:
            continue                                    # inside the apron body
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
    on_road = {v for f in pm.faces.values() if f.role in roadish
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
