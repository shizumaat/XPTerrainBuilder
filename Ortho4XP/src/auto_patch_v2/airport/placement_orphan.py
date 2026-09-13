"""§16d (1) THE PLAN BOXES WHAT THE WRITER WRITES (spec
``object-placement-spec.md`` §16d; Fable 2026-09-13, owner
RULINGS 2026-09-13h).

``geom_box`` was the hull of the ADMITTED PARTS while ``obj8_split``
emitted the source object's triangles regardless.  A connected component
no part named — a zero-thickness one-sided quad the thickness gate never
admitted, an exporter's ground paint, a roof plate authored over another
hangar — was handed to the NEAREST body by plan centroid and rode a zero
that body chose somewhere else, while every instrument (§15, §16a, §16b
read the box; §7 reads feet) looked straight past it.  At LEMD 1.0.325
that put the FS2XPlane origin plate 16.37 m over the T4 apron and a cargo
roof plate 3.71 m over the hangar next door.

THE LAW: a component is a body's only when it lies within
``coarsen_reach_m`` of that body's PART HULL in plan.  Beyond every body
of the placement it becomes its OWN body — footless, on its own ground,
at its authored offset (§16 (3)) — so the FS2XPlane plate, authored at
y = −5 under the object origin, is written 5 m under the ground the pack
put it over, buried exactly as authored.

THE POPULATION IS WHAT THE WRITER WRITES, not what ``solid_components``
returns: the DRAPED triangles are outside ``geom.solid`` and so outside
every ``Part.comp``, but ``obj8_split`` writes them, so they are orphans
by construction and are placed by the same rule.

It runs BETWEEN §15's candidates and §15's search: the part hulls the
reach is measured against must exist, and a component beyond every one of
them is a body the search must still place.  It lives apart from
``placement_plan`` for the 1,000-line law only.

NO LAW CONSTANT LIVES HERE: the reach is ``[placement] coarsen_reach_m``,
handed in by the caller.
"""
from __future__ import annotations

import typing as _t

import numpy as _np

from . import anchor_rule as _ar
from . import placement_boxes as _pb

__all__ = ["place_orphans"]


def place_orphans(st: _t.Any, reach_m: float, surface: _t.Any,
                  counts: dict) -> None:
    """§16d (1): give every component the member's bodies do not own a
    body whose box will contain it.

    ``st`` is the :class:`placement_record.Staged` member, with pass 2's
    GROUND GROUPS (and so its carrier candidates) already made — the part
    hulls the reach is measured against — and pass 3's carrier search
    still to come.

    A component within ``reach_m`` of a ground group's PART HULL joins
    that group: its triangles go into that file, ``geom_box`` grows to
    the hull of what the file will contain, and no search is asked (the
    overwhelming majority — LEMD 27.6k of 27.7k).  A component beyond
    every one of them is appended as a FOOTLESS BODY of this member and
    left to §15's search, which places it on what it stands over, or, if
    the law accepts no carrier, on its own ground at its authored offset
    (§16 (3)) — the FS2XPlane origin plate's own answer, 5 m under the
    ground the pack put it over.

    The new raw body carries its triangles in the ``tris`` slot, which
    ``obj8_split.BodyCut`` treats as SENIOR to every vote — so the
    component lands in exactly one file however its vertices are shared.
    It carries NO parts and NO feet: it is footless by construction
    (§16 (1)'s own sentence), never a carrier candidate (pass 2 is over),
    and never senior in its group."""
    cutter = getattr(st, "cutter", None)
    if cutter is None:
        return
    comps = cutter.written_components()
    if not comps:
        return
    owned = {p.comp for r in st.raw for p in r[0]}
    # §16d (1): AND THE OWNED COMPONENTS ARE BOXED BY THEMSELVES.  A
    # ``Part.box`` is the part's own reading of its footprint and is not
    # always the component's plan hull; the file gets the WHOLE
    # component, so the geom box is hulled over the components the body's
    # parts name.  (LEMD's `Munoza-VRDCH`/`LEMD03` bodies reached 1.3 m
    # past a box drawn from their parts.)
    cbox = {ci: box for ci, _tr, box in comps if ci >= 0}
    for i, r in enumerate(st.raw):
        if r[5] or not r[0] or i >= len(st.geom_boxes):
            continue
        h = _pb.hull_of([cbox[p.comp] for p in r[0] if p.comp in cbox]
                        + ([st.geom_boxes[i]] if st.geom_boxes[i] else []))
        if h:
            st.geom_boxes[i] = h
    orphans = [(ci, tris, box) for ci, tris, box in comps
               if ci < 0 or ci not in owned]
    if not orphans:
        return
    # THE BODIES THE REACH IS MEASURED AGAINST.  A FOOTED member's are
    # its pass-2 GROUND GROUPS, and a component joins one by going into
    # that group's list.  A FOOTLESS member has none — every body of it
    # is waiting for §15's search — so its own RAW bodies are the
    # targets, and a component joins one by taking ITS GROUND: that is
    # exactly what ``_footless_targets`` groups the carrier question by,
    # so the component asks nothing and rides the same carrier.  Without
    # this every component of a footless placement asked its own search
    # (LEMD 21,419 of them, and the plan stage doubled).
    if st.groups:
        pairs = [(g, h, None) for g, h in
                 ((g, _pb.hull_of(b for i in g for b in st.part_boxes[i]))
                  for g in st.groups if g) if h]
    else:
        pairs = [(None, _pb.hull_of(st.part_boxes[i]),
                  st.raw[i][7] if len(st.raw[i]) > 7 else None)
                 for i in range(len(st.raw)) if st.part_boxes[i]]
        pairs = [q for q in pairs if q[1]]
    freed: list[int] = []
    # THE JOINED COMPONENTS OF ONE GROUP ARE ONE APPEND.  They all land in
    # the same file, so a raw body each buys nothing and costs a geometry
    # sampling per component — at OTHH that is tens of thousands of them.
    joined: dict[int, list] = {}
    near = _nearest_target(pairs, [b for _c, _t_, b in orphans])
    for (ci, tris, box), (gap, best) in zip(orphans, near):
        # ``reach_m <= 0`` DISARMS the reach, the convention every other
        # plan-contiguity key takes (``coarsen``'s own, ``--coarsen-reach
        # 0``): the component then joins the nearest body, which is what
        # ``obj8_split`` did with it before this law.
        if best is not None and (reach_m <= 0.0 or gap <= reach_m):
            joined.setdefault(best, []).append((tris, box))
            counts["orphan_components_joined"] = \
                counts.get("orphan_components_joined", 0) + 1
            if ci < 0:
                counts["orphan_draped_joined"] = \
                    counts.get("orphan_draped_joined", 0) + 1
            continue
        # beyond every ground group of the placement: its own FOOTLESS
        # body, which §15's search then places
        freed.append(_append(st, _tuples(tris), box, surface))
        counts["orphan_components_own_body"] = \
            counts.get("orphan_components_own_body", 0) + 1
        if ci < 0:
            counts["orphan_draped_own_body"] = \
                counts.get("orphan_draped_own_body", 0) + 1
        if pairs:
            counts["orphan_reach_worst_m"] = max(
                float(counts.get("orphan_reach_worst_m", 0.0)), round(gap, 1))
    for k, rows in joined.items():
        tris = tuple(t for tr, _b in rows for t in _tuples(tr))
        box = _pb.hull_of(b for _tr, b in rows)
        g, _h, ground = pairs[k]
        bi = _append(st, tris, box, None, ground)
        if g is not None:
            g.append(bi)
    if freed:
        # an ELEVATED body of this member is what pass 3 asks the carrier
        # question of; a FOOTLESS member's targets are read off ``raw``
        # and need no register
        st.elevated = st.elevated | frozenset(freed)


#: how many orphan boxes are matched against the target boxes at a time.
#: A MEMORY bound on the gap matrix, not a law: a clutter object offers
#: thousands of each and the full product is tens of millions of floats.
_GAP_CHUNK = 256


def _nearest_target(pairs: _t.Sequence[tuple], boxes: _t.Sequence[tuple]
                    ) -> "list[tuple[float, int | None]]":
    """``(plan gap in metres, target index)`` for each of ``boxes``, the
    nearest target first — :func:`placement_boxes.box_gap_m` read over
    the whole product at once.

    One orphan against every target is a Python double loop over
    thousands by thousands (LEMD's clutter placements, 9 M calls and most
    of this pass's cost); the gap is two clamped differences and a
    hypotenuse, so numpy reads the whole matrix in one pass."""
    if not pairs or not boxes:
        return [(0.0, None)] * len(boxes)
    P = _np.asarray([q[1] for q in pairs], dtype=float)
    B = _np.asarray(boxes, dtype=float)
    ml, mo = _ar._m_per_deg(float(B[:, 0].mean()))
    out: list[tuple[float, int | None]] = []
    for k in range(0, B.shape[0], _GAP_CHUNK):
        b = B[k:k + _GAP_CHUNK]
        dla = _np.maximum(_np.maximum(b[:, None, 0] - P[None, :, 2],
                                      P[None, :, 0] - b[:, None, 2]), 0.0) * ml
        dlo = _np.maximum(_np.maximum(b[:, None, 1] - P[None, :, 3],
                                      P[None, :, 1] - b[:, None, 3]), 0.0) * mo
        d = dla * dla + dlo * dlo
        j = _np.argmin(d, axis=1)
        out.extend((float(d[r, j[r]]) ** 0.5, int(j[r]))
                   for r in range(b.shape[0]))
    return out


def _tuples(tris) -> tuple:
    """A component's triangles as the authored TRIPLES ``BodyCut.tris``
    spells.  Built only for the components this pass actually places —
    ``written_components`` hands back numpy arrays for exactly that
    reason."""
    return tuple(tuple(int(q) for q in row)
                 for row in _np.asarray(tris).reshape(-1, 3).tolist())


def _append(st: _t.Any, tris: tuple, box: tuple, surface: _t.Any,
            ground: _t.Any = None) -> int:
    """One orphan component as a raw body at the end of ``st.raw``, with
    ``st.boxes`` / ``st.part_boxes`` / ``st.part_tops`` / ``st.geom_boxes``
    kept parallel — the lists every later pass reads by index (the same
    append ``placement_body._carrier_pieces`` makes for a carrier piece).

    The anchor is a PLACEHOLDER: this body has no parts, so it is never
    senior in its group, and every file constructor that could reach it
    builds its own anchor.  The GROUND is read only for a body that will
    ask the carrier question (``_footless_targets`` groups by it); a
    component that has already joined a group needs none, and reading it
    is most of this pass's cost."""
    from .placement_cut import _geom_ground
    bi = len(st.raw)
    cls = _ar.OTHER
    a = _ar.Anchor(cls, 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3]),
                   0.0, "§16d (1) component outside every body's reach")
    pts: tuple = ()
    if st.cutter is not None:
        if surface is not None:
            pts, _sp, ground = _geom_ground(st.cutter, (), tris, surface)
        else:
            pts = st.cutter.geom_points((), tris)
    st.raw.append(([], cls, a, (), True, tris, pts, ground))
    st.boxes.append(box)
    st.part_boxes.append([box])
    st.geom_boxes.append(box)
    if st.part_tops:
        st.part_tops.append(list(st.cutter.part_tops(
            [([], "", None, (), True, tris, (), None)])[0]))
    return bi
