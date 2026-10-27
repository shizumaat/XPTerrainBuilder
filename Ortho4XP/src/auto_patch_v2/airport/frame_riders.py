"""AN AUTHORED-LIFT ROW INSIDE A RE-SEATED FRAME MOVES WITH IT (owner
RULINGS 2026-10-22b / 10-22f, #1214).

Owner, KMCI 1.0.415: "The terminal is not floating but it also came
apart, is now below ground leaving interior components floating in the
air."  The terminal frame (148 files, ``OBJECT_AGL +8.5``) is re-seated by
the unit law and drops its lift (10-22b (1)); its 614 seats (``OBJECT_AGL
+4.7``, rows of their own, never split) kept theirs, and stood on the
concourse ROOF, 5.7 m over the carpet they were authored on.

A lifted row whose anchor stands inside the plan box of a re-seated frame
is that frame's CONTENT: its lift was the same author's correction for
the same terrain, so it keeps its AUTHORED RELATION to the frame — it
moves by the frame's own displacement, ``frame zero now - (drape at the
frame's row + its lift)``, and is written ``OBJECT_MSL`` there.  A plain
row (no lift) is the author's own seat on the ground under it and is left
as it is.  Name-free: the witness is the rows and the plan boxes.
"""
from __future__ import annotations

import typing as _t

__all__ = ["frame_rider_seats", "FRAME_RIDER", "MOVE_MIN_M"]

#: the ``MslSeat.why`` this module writes
FRAME_RIDER = "frame_rider"
#: a frame displaced by less than this moves no rider (the 14g (2) reading)
MOVE_MIN_M = 0.05

Surface = _t.Callable[[float, float], "float | None"]


def _lift(row: _t.Any) -> float:
    if getattr(row, "kind", "OBJECT") != "OBJECT_AGL":
        return 0.0
    return float(getattr(row, "elevation", 0.0) or 0.0)


def _frames(splits: _t.Sequence[_t.Any], rows: _t.Sequence[_t.Any],
            surface: Surface) -> list[tuple[float, list[tuple]]]:
    """``(displacement, plan boxes)`` per re-seated frame that DROPPED an
    authored lift — keyed by its row's anchor spelling and lift, the
    shared-datum identity."""
    acc: dict[tuple, tuple[list[float], list[tuple]]] = {}
    for s in splits:
        i = s.placement.index
        if not 0 <= i < len(rows):
            continue
        row = rows[i]
        lift = _lift(row)
        if lift <= 0.0 or any(float(b.lift_m or 0.0) for b in s.bodies):
            continue
        g = surface(float(row.lat), float(row.lon))
        if g is None:
            continue
        key = (round(float(row.lat), 7), round(float(row.lon), 7), round(lift, 3))
        d = acc.setdefault(key, ([], []))
        for b in s.bodies:
            if b.surface_z is None:
                continue
            d[0].append(float(b.surface_z) - float(b.y_zero) - (float(g) + lift))
            if b.plan_box is not None:
                d[1].append(tuple(float(q) for q in b.plan_box))
    out = []
    for moves, boxes in acc.values():
        if moves and boxes:
            moves.sort()
            out.append((moves[len(moves) // 2], boxes))
    return out


def frame_rider_seats(dump: _t.Any, splits: _t.Sequence[_t.Any],
                      surface: Surface, taken: _t.AbstractSet[int],
                      counts: "dict | None" = None) -> tuple:
    """The ``MslSeat`` of every lifted row standing inside a re-seated
    frame, moved by that frame's displacement.  ``taken`` are the rows
    already split, converted or row-seated (never touched here)."""
    from ..model.placement import MslSeat
    rows = list(getattr(dump, "placements", ()) or ())
    frames = [f for f in _frames(splits, rows, surface) if abs(f[0]) > MOVE_MIN_M]
    out = []
    for i, row in enumerate(rows):
        lift = _lift(row)
        if i in taken or lift <= 0.0:
            continue
        la, lo = float(row.lat), float(row.lon)
        for move, boxes in frames:
            if any(b[0] <= la <= b[2] and b[1] <= lo <= b[3] for b in boxes):
                g = surface(la, lo)
                if g is None:
                    break
                out.append(MslSeat(i, str(row.def_path), lo, la,
                                   float(getattr(row, "heading_deg", 0.0)),
                                   max(float(g) + lift + move, float(g)),
                                   FRAME_RIDER))
                break
    if counts is not None:
        counts["frame_riders_moved"] = len(out)
        counts["frame_riders_frames"] = len(frames)
    return tuple(out)
