"""THE PLAN BOXES, AND THE GROUND UNDER THEM (spec
``object-placement-spec.md`` §14 (3) / §15 (1) / §16 (2)/(3) / §16b).

The geometry the carrier law and its censuses both measure on: a body's
plan box and its bounded FOOTPRINT, the overlap that says what stands
over what, the FILL that says whether a body is a solid at all, and the
design surface read under a body or under its own feet.  ONE
implementation, because a relation measured on one geometry by the law
and another by the instrument counts the disagreement rather than the
defect (CLAUDE.md, the census-wrapper defect).

This lives apart from ``placement_carrier`` for the 1,000-line law and
for nothing else.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar

__all__ = ["hull_of", "box_of", "overlap", "overlap_m2", "box_area_m2",
           "box_gap_m", "fill_of", "foot_boxes", "parts_overlap",
           "ground_at_box", "ground_samples", "ground_under",
           "anchor_ground_off", "stands_over_rank", "FOOT_BOXES_MAX",
           "GROUND_OFF_FEET_MAX"]


# ── plan boxes ───────────────────────────────────────────────────────────

def hull_of(boxes: _t.Iterable[tuple[float, float, float, float]]
            ) -> tuple[float, float, float, float] | None:
    """The bounding box of ``boxes``, or ``None`` when there are none."""
    bs = list(boxes)
    if not bs:
        return None
    return (min(b[0] for b in bs), min(b[1] for b in bs),
            max(b[2] for b in bs), max(b[3] for b in bs))


def box_of(feet: _t.Sequence[tuple[float, float, float]],
           parts: _t.Sequence[_t.Any]) -> tuple[float, float, float, float]:
    """A body's PLAN box ``(lat0, lon0, lat1, lon1)`` — from its own feet
    when it has them (a SEGMENT's box is its segment's, not its parent
    line's), else from its parts' boxes."""
    if feet:
        las = [f[0] for f in feet]
        los = [f[1] for f in feet]
        return (min(las), min(los), max(las), max(los))
    return (min(p.box[0] for p in parts), min(p.box[1] for p in parts),
            max(p.box[2] for p in parts), max(p.box[3] for p in parts))


def overlap(a: tuple[float, float, float, float],
            b: tuple[float, float, float, float]) -> float:
    """The plan overlap AREA of two boxes in square degrees (a monotone
    stand-in for square metres inside one placement)."""
    dla = min(a[2], b[2]) - max(a[0], b[0])
    dlo = min(a[3], b[3]) - max(a[1], b[1])
    return dla * dlo if dla > 0.0 and dlo > 0.0 else 0.0


def box_gap_m(a: tuple[float, float, float, float] | None,
              b: tuple[float, float, float, float] | None) -> float:
    """§16b (1): the PLAN GAP between two boxes in metres — 0 where they
    touch or overlap.  What "contiguous in plan" is measured with: §9
    joined bodies by zero AGREEMENT alone, and a sign 1,590 m from the
    sign whose zero it took is not one object with it (11ap item 2)."""
    if not a or not b:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (a[0] + a[2]))
    dla = max(0.0, max(a[0] - b[2], b[0] - a[2])) * ml
    dlo = max(0.0, max(a[1] - b[3], b[1] - a[3])) * mo
    return (dla * dla + dlo * dlo) ** 0.5


def box_area_m2(b: tuple[float, float, float, float]) -> float:
    """One plan box's area in square metres."""
    ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
    return max(0.0, (b[2] - b[0]) * ml) * max(0.0, (b[3] - b[1]) * mo)


def fill_of(box: tuple[float, float, float, float] | None,
            part_boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """§16 (3): the FOOTPRINT FILL of a body — the area its PART boxes
    cover over the area of its own plan box, capped at 1.

    This is what separates a SOLID from a line: a wall ring or a building
    fills 0.3-1.0 of its box, while a 2 km fence segment, a grass strip
    and a taxi sign fill a few thousandths of theirs.  Overlapping parts
    are counted twice, which can only push a candidate ABOVE the bar —
    the test is a floor, so the error is on the side of admitting a
    genuine solid, never of admitting a line."""
    if not box or not part_boxes:
        return 0.0
    area = box_area_m2(box)
    if area <= 0.0:
        return 1.0                      # a degenerate box is its own fill
    return min(1.0, sum(box_area_m2(b) for b in part_boxes) / area)


#: §16 (3): how many PART boxes stand for a body's footprint in the
#: stands-over relation — its largest, by area.  The law and the census
#: read the SAME bounded set (the plan publishes it per body), because a
#: relation measured on one geometry by the law and another by the
#: instrument counts the disagreement rather than the defect; and a plan
#: carrying every part box of every body (LEMD: 29,402 parts) doubles its
#: own size for a refinement the tail of the list never changes.
FOOT_BOXES_MAX = 8


def foot_boxes(part_boxes: _t.Sequence[tuple[float, float, float, float]],
               cap: int = FOOT_BOXES_MAX
               ) -> tuple[tuple[float, float, float, float], ...]:
    """The ``cap`` largest of ``part_boxes`` (:data:`FOOT_BOXES_MAX`), in
    the order given — a body's footprint, bounded."""
    bs = list(part_boxes)
    if len(bs) <= cap:
        return tuple(bs)
    keep = sorted(range(len(bs)), key=lambda i: -box_area_m2(bs[i]))[:cap]
    return tuple(bs[i] for i in sorted(keep))


def parts_overlap(a: _t.Sequence[tuple[float, float, float, float]],
                  b: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """§16 (3): STANDS-OVER IS PARTS-HULL OVERLAP, not box overlap — the
    overlap of the two bodies' PART boxes, summed pairwise (square
    degrees, the same monotone unit :func:`overlap` speaks).

    A body's hull box is a crude proxy for its footprint: LEMD's
    ``LEMDzaun__b5``, a fence segment, has a box that CONTAINS the garage
    roof and a footprint that touches none of it (11ai (C)).  Pairwise
    summation double-counts parts that overlap each other, which can only
    raise a candidate that genuinely stands under the body."""
    return sum(overlap(p, q) for p in a for q in b)


def ground_at_box(surface: _t.Callable[[float, float], "float | None"],
                  box: tuple[float, float, float, float] | None) -> float | None:
    """§16 (2)/(3): THE GROUND UNDER A BODY'S OWN GEOMETRY — the design
    surface at the centre of the body's plan box, else at whichever of
    its corners reads.  ONE point, read the same way by the law (which
    refuses a carrier standing far from it) and by the census (which
    prints ``zero - ground_under_geometry``); a second rule here would be
    the census-wrapper defect."""
    if not box or surface is None:
        return None
    pts = [(0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])),
           (box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    for la, lo in pts:
        z = surface(la, lo)
        if z is not None:
            return float(z)
    return None


def ground_samples(surface: _t.Callable[[float, float], "float | None"],
                   boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                   box: tuple[float, float, float, float] | None = None
                   ) -> list[float]:
    """§16 (2): the design surface UNDER A BODY'S OWN GEOMETRY, sampled at
    the centre of each of its FOOTPRINT boxes (``foot_boxes``) — else, for
    a body that publishes none, at the centre and corners of its plan box.

    A body's box centre is not its geometry: an L-shaped terminal's centre
    stands in the yard between its wings, and a re-cut roof's centre can
    fall on the taxiway 8 m below it.  The parts are where the body
    actually is.  ONE sampler, read the same way by the law (which refuses
    a carrier standing far from this ground) and by the census."""
    if surface is None:
        return []
    pts: list[tuple[float, float]] = [(0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]))
                                      for b in boxes]
    if not pts and box:
        pts = [(0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])),
               (box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    out = []
    for la, lo in pts:
        z = surface(la, lo)
        if z is not None:
            out.append(float(z))
    return out


def ground_under(surface: _t.Callable[[float, float], "float | None"],
                 boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                 box: tuple[float, float, float, float] | None = None
                 ) -> float | None:
    """THE ground under a body: the MEDIAN of :func:`ground_samples` (a
    median, because one part hanging over a ditch is not the ground the
    body stands on).  ``None`` where nothing reads."""
    zs = sorted(ground_samples(surface, boxes, box))
    return None if not zs else zs[len(zs) // 2]


#: §16a (2): how many of a body's own FEET the mis-anchoring test reads.
#: A terminal publishes 132 of them and the answer is a MEDIAN; the
#: sampling resolution costs nothing the reading needs (LEMD publishes
#: 82k feet over the airport, and reading every one of them put 0.6 s in
#: the plan stage for a number that did not move).
GROUND_OFF_FEET_MAX = 32


def anchor_ground_off(anchor: _ar.Anchor,
                      feet: _t.Sequence[tuple[float, float, float]],
                      surface: _t.Callable[[float, float], "float | None"]
                      ) -> float | None:
    """§16a (2): IS THIS BODY MIS-ANCHORED — how far its own zero stands
    from the ground under its OWN FEET.

    The ground under a foot is not the surface there: the foot stands at
    its own authored height ``y`` above the body's zero plane, so what
    the ground under it SAYS the body's zero is, is
    ``surface(foot) - y_foot``.  (§7's float per foot is exactly this
    minus the body's zero.)  Reading the raw surface instead makes every
    building on a slope look mis-anchored — measured at LEMD: 313 of the
    airport's footed bodies refused as carriers, and the roofs over them
    then rode whatever came next, 49 of them more than 0.5 m off the
    walls they stand on.

    The MEDIAN over the feet, because one foot hanging over a ditch is
    not the body's anchoring.  ``None`` where nothing reads: no reading
    is no evidence that the body is wrong."""
    if anchor.surface_z is None or not feet:
        return None
    zero = float(anchor.surface_z) - float(anchor.y_zero)
    step = max(1, len(feet) // GROUND_OFF_FEET_MAX)
    zs = []
    for f in feet[::step]:
        z = surface(f[0], f[1])
        if z is not None:
            zs.append(float(z) - float(f[2]))
    if not zs:
        return None
    zs.sort()
    return abs(zs[len(zs) // 2] - zero)


def stands_over_rank(box: tuple[float, float, float, float],
                     other: tuple[float, float, float, float],
                     boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                     other_boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                     ) -> tuple[float, float]:
    """The ranking key for "does this body stand over that one" — the
    plan OVERLAP first, the tighter box second.

    The second half is not decoration.  A body wholly inside several
    large boxes ties on overlap at its own area, and LEMD has plenty of
    them: a 4.5 km grass line segment's station box and a taxi-sign
    body's box both contain the whole T4S roof, so the winner was
    whichever the enumeration reached first — and the law and the census
    enumerate in different orders, which made 11 bodies "float" on
    nothing but that.  Of two bodies that both cover this one, the
    SMALLER is what it stands on.

    §16 (3): where both bodies' PART boxes are given the overlap is
    measured between those (:func:`parts_overlap`) — the hull boxes then
    serve only as the cheap reject, because two hulls that miss cannot
    have a part pair that meets."""
    ov = overlap(box, other)
    if ov <= 0.0:
        return (0.0, 0.0)
    if boxes and other_boxes:
        ov = parts_overlap(boxes, other_boxes)
        if ov <= 0.0:
            return (0.0, 0.0)
    return (ov, -abs((other[2] - other[0]) * (other[3] - other[1])))


def overlap_m2(a: tuple[float, float, float, float],
               b: tuple[float, float, float, float]) -> float:
    """:func:`overlap` in SQUARE METRES — square degrees are a monotone
    stand-in for the comparison, but the REPORT says how much of one
    body stands over the other, and that is read in metres."""
    ov = overlap(a, b)
    if ov <= 0.0:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (a[0] + a[2]))
    return ov * ml * mo


