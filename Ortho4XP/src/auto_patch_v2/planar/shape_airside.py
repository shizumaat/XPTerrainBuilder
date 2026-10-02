"""AN APRON FACE NEVER CARRIES A TERRACE (owner RULINGS 2026-10-02v (2),
issue #189) — the third weld of ``planar/shapes.build_shapes``, split out
of ``shapes.py`` by the planar layer's 1,000-line budget (as the 30bk
mouth weld was)."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import airside_stage_roles, family
from ..model.planar import NO_SHAPE, PlanarMap

__all__ = ["weld_airside_faces", "airside_apron_roles"]


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


def weld_airside_faces(pm: PlanarMap, law: Law, label: dict[int, int],
                       uf: _t.Any, stats: _t.Any) -> None:
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

    THE FIX, AT THE JOINT'S DERIVATION.  An :func:`airside_apron_roles`
    face carries ONE label: the labels on its ring and holes WELD here,
    after 30bk's mouth weld, so AIRSIDE IS KING — a groundside class change
    elsewhere on the pair (30bk's kept verdict) cannot leave a step inside
    an apron.  Nothing downstream is vetoed: the contour admission
    (``len(labs) >= 2``), the gap midlines, :func:`planar.shapes.straddles`
    and every consumer of the joints read the LABELS, so with the face of
    one label there is no joint to declare, no row to withdraw and no
    sidecar ``terrace_joints`` record.  A groundside face (a lot, a road,
    the open boundary) keeps 08k's joint: a terrace there is lawful.  A
    RIGID pad is outside ``airside_stage_roles``, so the 28b pad|apron
    terraces stand.

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
            if uf.union(labs[0], l):
                stats.welded_airside_faces += 1
    for v in label:
        label[v] = uf.find(label[v])
