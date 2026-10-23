"""ONE ZERO PER CONNECTED GROUP (owner RULINGS 2026-10-22c/f, 2026-10-22o;
#1214 round 3, R5).

Owner, 2026-10-23T01:10:51Z (22o): "connected objects stay as one group,
even if parts end up under ground ... we only split and seat separately,
objects that are clearly at least a couple meters apart with no above
ground connecting shape, so bridges, road decks, etc. that touch or even
come within a meter of a building must always move together with that
building."

Two passes, both applied to one placement's record after its bodies are
formed and before the lift and the cut:

* :func:`rigid_open` — an OPEN frame (every member a deck or a deck
  candidate: a bridge, a canopy) takes ONE zero per placement: the deck
  datum where a body carries it, else the lowest (10-22c: no support
  floats).  Moved out of ``placement_plan``.
* :func:`group_zero` — every body whose parts belong to one CONNECTED SET
  (a §16g footprint unit's ROOT: the pad-level and block passes cut one
  connected unit into pieces, ``fu:16:6938/p2/b1``, and 22o puts the
  pieces back together) takes that set's one zero — basin rims, line
  segments, viaduct spans, decks, garage connectors alike; no per-pass
  datum for a group member.  The set's zero is the median of its pieces'
  zeros over its parts (:func:`root_zeros`).  The §16g chain is the
  "touch or within a metre" relation (``[placement] touch_m``); a body
  none of whose parts is chained keeps its own seat.

Each re-anchored body's file is renamed for what it now bakes (R1,
``placement_file.named_body``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["OPEN_KINDS", "rigid_open", "unit_root", "root_zeros", "body_root",
           "frame_root_boxes", "merge_frame_roots", "group_zero", "GROUP_REASON",
           "TOUCH_M"]

#: the deck verdicts that make a member an OPEN structure — a deck
#: (``flag`` / ``signature``) or a plate the signature pass could not prove
#: spans anything (``candidate``: a bridge with no mapped way, a canopy)
OPEN_KINDS = frozenset({"flag", "signature", "candidate"})

#: the reason prefix :func:`group_zero` writes
GROUP_REASON = "one connected group"


def rigid_open(record: _t.Any, m: _t.Any, open_frame: bool) -> _t.Any:
    """Owner RULINGS 2026-10-22c (#1214): "prioritize the canopy or bridge
    deck, and that the pillars or supports stay attached, then seating the
    whole unit so no pillars are floating" — and 10-22f: "they should
    always move as a group".  Every body of a placement in an OPEN frame
    takes ONE zero: the deck's datum where a body carries it, else the
    LOWEST of the bodies' own zeros, so no support floats.  A body whose
    seat tilt is baked into its vertices leaves the placement as it was."""
    bodies = record.bodies
    if not open_frame or len(bodies) < 2:
        return record
    if any(getattr(b.seat, "applied", False) for b in bodies if b.seat is not None):
        return record
    zs = [(float(b.anchor.surface_z) - float(b.anchor.y_zero), b) for b in bodies
          if b.anchor.surface_z is not None]
    if len(zs) < 2 or max(z for z, _b in zs) - min(z for z, _b in zs) <= 0.05:
        return record
    dat = [z for z, b in zs if b.anchor.datum]
    target = dat[0] if dat else min(z for z, _b in zs)
    return _at_zero(record, m, target, lambda b: True,
                    f"one rigid open structure at {target:.2f} (RULINGS 2026-10-22c)")


def _at_zero(record: _t.Any, m: _t.Any, target: float,
             take: _t.Callable[[_t.Any], bool], why: str) -> _t.Any:
    from .placement_file import named_body
    out = []
    for b in record.bodies:
        a = b.anchor
        if a.surface_z is None or not take(b):
            out.append(b)
            continue
        y0 = float(a.surface_z) - target
        off = tuple(a.offset)
        a2 = _dc.replace(a, y_zero=y0, offset=(off[0], y0, off[2]),
                         reason=f"{why}; was: {a.reason}")
        out.append(named_body(m, b, anchor=a2))
    return _dc.replace(record, bodies=tuple(out))


def unit_root(uid: str) -> str:
    """The id of the connected unit a pad-level or block piece was cut
    from (``fu:16:6938/p2/b1`` -> ``fu:16:6938``; a seat's family spelling
    ``fu:16:6938/p2/b1@viaduct`` reads the same)."""
    return str(uid).split("/", 1)[0].split("@", 1)[0]


def root_zeros(plan_wide: _t.Mapping[int, tuple], plan: _t.Any = None
               ) -> dict[str, tuple[float, float]]:
    """``root -> (zero, its frame's lift)``: the median of the plan-wide
    unit zeros (``footprint_seats.plan_wide_seats``: part id -> (unit,
    zero, ...)) over every part of each connected unit, and the authored
    ``OBJECT_AGL`` lift of the frame holding most of those parts (0 with
    no ``plan``) — the frame that zero is spelled in."""
    lift_of: dict[int, float] = {}
    if plan is not None:
        lift_of = {p.pid: float(getattr(u, "agl_m", 0.0) or 0.0)
                   for u in plan.units for m in u.members for p in m.parts}
    acc: dict[str, list[float]] = {}
    lifts: dict[str, dict[float, int]] = {}
    for pid, seat in plan_wide.items():
        if not seat or seat[1] is None or not seat[0]:
            continue
        r = unit_root(seat[0])
        acc.setdefault(r, []).append(float(seat[1]))
        lf = lift_of.get(pid, 0.0)
        lifts.setdefault(r, {})[lf] = lifts.setdefault(r, {}).get(lf, 0) + 1
    out = {}
    for r, zs in acc.items():
        zs.sort()
        lf = max(sorted(lifts[r]), key=lambda k: lifts[r][k]) if lifts.get(r) else 0.0
        out[r] = (zs[len(zs) // 2], lf)
    return out


#: 22o: "bridges, road decks, etc. that touch or even come within a meter of
#: a building must always move together with that building"
TOUCH_M = 1.0


def frame_root_boxes(u: _t.Any, plan_wide: _t.Mapping[int, tuple]
                     ) -> dict[str, list[tuple]]:
    """``root -> the plan boxes of its parts`` in ONE frame (plan unit
    ``u``) — what an unchained body of the frame is measured against."""
    out: dict[str, list[tuple]] = {}
    for m in getattr(u, "members", ()) or ():
        for p in getattr(m, "parts", ()) or ():
            seat = plan_wide.get(p.pid)
            if seat and seat[0] and getattr(p, "box", None):
                out.setdefault(unit_root(seat[0]), []).append(tuple(p.box))
    return out


def merge_frame_roots(root_boxes: _t.Mapping[str, _t.Sequence[tuple]],
                      parts: "_t.Mapping[str, int] | None" = None
                      ) -> dict[str, str]:
    """``root -> the root it moves with`` inside ONE frame: connected units
    whose parts touch or come within :data:`TOUCH_M` of each other are one
    group (22o: a thin deck or a viaduct links two halls even where the
    §16g chain, which never links through a thin body, keeps them apart);
    each group moves with its largest unit (``parts``: parts per root, else
    the box count)."""
    roots = sorted(root_boxes)
    size = {r: (parts or {}).get(r, len(root_boxes[r])) for r in roots}
    up = {r: r for r in roots}

    def find(r: str) -> str:
        while up[r] != r:
            up[r] = up[up[r]]
            r = up[r]
        return r
    hull = {r: _hull(root_boxes[r]) for r in roots}
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            if find(a) == find(b) or _gap_m(hull[a], [hull[b]]) > TOUCH_M:
                continue
            small, big = sorted((a, b), key=lambda r: len(root_boxes[r]))
            if any(_gap_m(q, root_boxes[big]) <= TOUCH_M for q in root_boxes[small]):
                ra, rb = find(a), find(b)
                keep, drop = sorted((ra, rb), key=lambda r: (-size[r], r))
                up[drop] = keep
    return {r: find(r) for r in roots}


def _hull(boxes: _t.Sequence[tuple]) -> tuple:
    return (min(q[0] for q in boxes), min(q[1] for q in boxes),
            max(q[2] for q in boxes), max(q[3] for q in boxes))


def body_root(b: _t.Any, plan_wide: _t.Mapping[int, tuple],
              file_root: "_t.Mapping[str, str] | None" = None,
              root_boxes: "_t.Mapping[str, _t.Sequence[tuple]] | None" = None
              ) -> "str | None":
    """The connected unit the body's seat already names (its anchor's
    ``family``, a §16g unit — its own, or its carrier's), else the one most
    of its parts belong to; for a body none of whose parts is chained,
    its CARRIER's (``merged_into``, through
    ``file_root``: the written file -> its unit, filled as the carriers are
    written), else the unit of its own frame whose parts its plan box
    touches or comes within :data:`TOUCH_M` of (``root_boxes``,
    :func:`frame_root_boxes`; the nearest)."""
    fam = str(getattr(getattr(b, "anchor", None), "family", "") or "")
    if fam.startswith("fu:"):
        # seated by a unit already (its own, or its carrier's): that unit
        return unit_root(fam)
    n: dict[str, int] = {}
    for pid in getattr(b, "pids", ()) or ():
        seat = plan_wide.get(pid)
        if seat and seat[0]:
            r = unit_root(seat[0])
            n[r] = n.get(r, 0) + 1
    if n:
        return max(sorted(n), key=lambda r: n[r])
    carrier = getattr(b, "merged_into", "") or ""
    if carrier and file_root and carrier in file_root:
        return file_root[carrier]
    box = getattr(b, "plan_box", None) or getattr(b, "geom_box", None)
    if box and root_boxes:
        best = None
        for r in sorted(root_boxes):
            g = _gap_m(tuple(box), root_boxes[r])
            if g is not None and g <= TOUCH_M and (best is None or g < best[0]):
                best = (g, r)
        if best is not None:
            return best[1]
    return None


def _gap_m(box: tuple, boxes: _t.Any) -> "float | None":
    """The least plan gap in metres between ``box`` and any of ``boxes``
    (``placement_boxes.box_gap_m``'s reading, over an array at once)."""
    import numpy as np

    from . import anchor_rule as _ar
    q = np.asarray(boxes, dtype=float).reshape(-1, 4)
    if not len(q):
        return None
    ml, mo = _ar._m_per_deg(0.5 * (box[0] + box[2]))
    dla = np.maximum(0.0, np.maximum(box[0] - q[:, 2], q[:, 0] - box[2])) * ml
    dlo = np.maximum(0.0, np.maximum(box[1] - q[:, 3], q[:, 1] - box[3])) * mo
    return float(np.sqrt(dla * dla + dlo * dlo).min())


def group_zero(record: _t.Any, m: _t.Any, plan_wide: _t.Mapping[int, tuple],
               zeros: _t.Mapping[str, tuple[float, float]], counts: dict,
               frame_lift: float = 0.0, tol_m: float = 0.05,
               file_root: "_t.Mapping[str, str] | None" = None,
               root_boxes: "_t.Mapping[str, _t.Sequence[tuple]] | None" = None,
               merged: "_t.Mapping[str, str] | None" = None) -> _t.Any:
    """R5 / 22o: every body of ``record`` whose parts belong to a connected
    unit takes that unit's ONE zero (:func:`root_zeros`), whatever pass
    seated it.  A frame chained to the unit with another authored lift
    (``frame_lift``; KMCI's terminal at +8.499 with stairs at +0.7) keeps
    its authored relation to it: its author's ground on the same plane,
    ``zero + frame_lift - the unit's lift``.  A body carried by one of the
    unit's files takes it too (:func:`body_root`).  A body already within
    ``tol_m`` of its target is left as it is."""
    if not plan_wide or not zeros:
        return record
    roots = {id(b): body_root(b, plan_wide, file_root, root_boxes)
             for b in record.bodies}
    if merged:
        roots = {k: (merged.get(r, r) if r else r) for k, r in roots.items()}

    def target(r: str) -> float:
        z, lf = zeros[r]
        return z + float(frame_lift) - lf

    def off(b: _t.Any) -> bool:
        r = roots.get(id(b))
        if r is None or r not in zeros or b.anchor.surface_z is None:
            return False
        z = float(b.anchor.surface_z) - float(b.anchor.y_zero)
        return abs(z - target(r)) > tol_m

    moved = [b for b in record.bodies if off(b)]
    if not moved:
        return record
    counts["group_zero_bodies"] = counts.get("group_zero_bodies", 0) + len(moved)
    out = record
    for r in sorted({roots[id(b)] for b in moved}):
        out = _at_zero(out, m, target(r),
                       lambda b, _r=r: roots.get(id(b)) == _r and off(b),
                       f"{GROUP_REASON} {r} at {target(r):.2f} (RULINGS 2026-10-22o)")
    return out
