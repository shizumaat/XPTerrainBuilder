"""#1908 A FREE-STANDING COLUMN STANDS ON ITS OWN FOOT.

An approach-light tower (ENTC's ``ALS.obj``: 38 masts over 570 m of
shore and sea) is authored as one placement whose masts begin at the
height the author's terrain had under each: 4.44 m, 5.32 m, 6.03 m over
the placement's zero.  Every mast is therefore ELEVATED (§13 (1): its
lowest vertex is above ``[rebake] elevated_base_m``), nothing of the
placement stands under it to carry it, and §16 (3) wrote each one on
the ground under its own footprint with its AUTHORED y kept — so every
mast stood its authored 4.4-6.1 m over our ground (the owner's 1.0.470
read: "float at the other end").

A mast whose foot is authored in the air over nothing is the author's
terrain profile, not a lift: a tall, thin column touching no surface of
anything below it has its lowest vertex as its foot.  This module names
that population — ONLY where it is certain (owner RULINGS 2026-11-13r:
"if there's any doubt, objects stay with their group where the author
placed them"):

* the column's foot is authored IN THE AIR: above ``[rebake]
  elevated_base_m`` over the placement's zero (a post standing at its
  placement's own zero is its group's, and stays with it);
* the body's LOWEST part is a COLUMN — solid height at least
  ``[placement] free_column_min_h_m``, plan width at most
  ``free_column_max_w_m`` and height at least ``free_column_aspect``
  times that width;
* it is the body's ONLY part reaching down that far (a gantry on two
  legs, a frame, a sign on posts stays as it was);
* NOTHING can host it: no part of its own unit outside the body whose
  plan box comes within ``free_column_clear_m`` of the column and whose
  base is below the column's foot, and no part of any OTHER unit within
  that reach at all (another frame's heights cannot be compared, so any
  overlap is doubt).

* and the carrier search finds NOTHING it stands on: no carrier, or
  only §15's no-evidence fallbacks (the nearest footed body of the unit,
  its largest — ``ALS.obj``'s seven land masts rode the sea masts 30-90 m
  off that way, 9-11 m over their ground).  A carrier the column stands
  over, rests on, touches or is bound to by contact, a unit it is a
  member of, a weld: each is a host, and the column stays with it.

Such a body is seated with the column's foot on the design surface under
the column (``y_zero`` = the column's authored base), anchored at the
column itself; everything else in the body rides it at its authored
offset.  NO LAW CONSTANT LIVES HERE: the four keys are ``[placement]``'s.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .placement_body import _plan_box_span_m

__all__ = ["ColumnLaw", "law_of", "PartIndex", "free_columns",
           "fallback_only", "alone", "FREE_COLUMN"]

#: the anchor reason's stem, read by the census instruments
FREE_COLUMN = "free-standing column"

#: a base this far under the column's own counts as reaching below it
_BELOW_TOL_M = 0.05


@_dc.dataclass(frozen=True)
class ColumnLaw:
    """``[placement] free_column_*`` (module doc)."""

    min_h_m: float
    max_w_m: float
    aspect: float
    clear_m: float


def law_of(placement: _t.Any) -> "ColumnLaw | None":
    """The column law of a ``[placement]`` table, ``None`` (disarmed)
    where ``free_column_min_h_m`` is absent or not positive."""
    h = float(getattr(placement, "free_column_min_h_m", 0.0) or 0.0)
    if h <= 0.0:
        return None
    return ColumnLaw(h, float(placement.free_column_max_w_m),
                     float(placement.free_column_aspect),
                     float(placement.free_column_clear_m))


class PartIndex:
    """Every part of a plan by plan box — the host question's population,
    built once per plan (:func:`free_columns` asks it per column)."""

    def __init__(self, plan: _t.Any):
        rows = [(ui, p.pid, p.base_y, p.box) for ui, u in enumerate(plan.units)
                for m in u.members for p in m.parts if getattr(p, "box", None)]
        self.unit = np.array([r[0] for r in rows], dtype=np.int64)
        self.pid = np.array([r[1] for r in rows], dtype=np.int64)
        self.base = np.array([r[2] for r in rows], dtype=float)
        self.box = np.array([r[3] for r in rows], dtype=float).reshape(-1, 4)

    def hosts(self, col: _t.Any, ui: int, own: _t.AbstractSet[int],
              clear_m: float) -> bool:
        """Can anything outside ``own`` (the body's pids, unit ``ui``)
        hold ``col`` up?  (Module doc, the third test.)"""
        if not self.pid.shape[0]:
            return False
        ml, mo = _ar._m_per_deg(0.5 * (col.box[0] + col.box[2]))
        dla, dlo = clear_m / ml, clear_m / mo
        b = self.box
        near = ((b[:, 0] <= col.box[2] + dla) & (b[:, 2] >= col.box[0] - dla)
                & (b[:, 1] <= col.box[3] + dlo) & (b[:, 3] >= col.box[1] - dlo))
        mine = self.unit == ui
        if own:
            near &= ~(mine & np.isin(self.pid, list(own)))
        below = mine & (self.base < col.base_y - _BELOW_TOL_M)
        return bool((near & (~mine | below)).any())


def _column_of(parts: _t.Sequence[_t.Any], law: ColumnLaw) -> _t.Any:
    """The body's one COLUMN foot, or ``None`` (module doc, the first two
    tests).  A plan written before ``Part.height_m`` reads no column."""
    if not parts:
        return None
    low = min(parts, key=lambda p: (p.base_y, p.pid))
    h = float(getattr(low, "height_m", 0.0) or 0.0)
    if not getattr(low, "box", None) or h < law.min_h_m:
        return None
    w = _plan_box_span_m(low.box)
    if w > law.max_w_m or h < law.aspect * w:
        return None
    if any(p is not low and p.base_y < low.base_y + law.min_h_m for p in parts):
        return None
    return low


def free_columns(st: _t.Any, ui: int, index: PartIndex, law: ColumnLaw,
                 surface: _ar.Surface, elevated_base_m: float) -> dict[int, tuple]:
    """The elevated raw bodies of ``st`` (a ``placement_record.Staged``)
    that are free-standing columns, each with its seat
    ``(lat, lon, y_zero, surface_z, reason)`` for
    ``placement_file._own_ground_file``."""
    out: dict[int, tuple] = {}
    for i in sorted(st.elevated):
        r = st.raw[i]
        if r[5]:                       # a cut segment is a footed line's
            continue
        col = _column_of(r[0], law)
        if col is None or col.base_y <= elevated_base_m:
            continue
        if index.hosts(col, ui, {p.pid for p in r[0]}, law.clear_m):
            continue
        z = _pb.ground_under(surface, (tuple(col.box),), tuple(col.box))
        if z is None:
            continue
        lat, lon = 0.5 * (col.box[0] + col.box[2]), 0.5 * (col.box[1] + col.box[3])
        out[i] = (lat, lon, float(col.base_y), float(z),
                  f"{FREE_COLUMN} (#1908): its foot (authored y "
                  f"{float(col.base_y):+.2f}) on the ground under it")
    return out


#: the carrier search's NO-EVIDENCE answers (``placement_carrier.carriers_for``
#: (c)/(d)): some footed body of the unit, nothing the column stands on
_FALLBACKS = ("nearest footed body of the unit", "the unit's largest footed body")


def fallback_only(over: _t.Sequence[tuple[_t.Any, str]]) -> bool:
    """Did the carrier search answer only with a no-evidence fallback?"""
    return bool(over) and all(str(why).startswith(_FALLBACKS) for _c, why in over)


def alone(targets: _t.Sequence[tuple[list[int], list]], cols: _t.Collection[int],
          part_boxes: _t.Sequence[_t.Sequence[tuple]]) -> list[tuple[list[int], list]]:
    """``targets`` (the carrier search's ``(group, boxes)``, in order) with
    every column of ``cols`` asking alone, right after the group it left;
    a group holding no column is passed through unchanged."""
    out: list[tuple[list[int], list]] = []
    for grp, bx in targets:
        if not any(i in cols for i in grp) or len(grp) == 1:
            out.append((grp, bx))
            continue
        rest = [j for j in grp if j not in cols]
        if rest:
            out.append((rest, [b for j in rest for b in part_boxes[j]]))
        out.extend(([j], list(part_boxes[j])) for j in grp if j in cols)
    return out
