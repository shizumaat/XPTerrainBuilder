"""THE DRAWN ANCHOR: a split body is drawn exactly when its placement is
(#2075).

X-Plane drops an object of a pack when the object's ANCHOR lies inside a
``sim/exclude_obj`` box of a pack drawn above it (``airport/exclusion``):
the anchor point alone decides, for the whole object.  A split gives every
body its own anchor, so a body of a DRAWN placement whose new anchor fell
inside such a box vanished from the sim (KRNT: 26 bodies of the DD pack's
parked B737s, hangars, fence and blast fences under the Renton pack's
boxes, while their placements' own anchors stand outside them), and a body
of an EXCLUDED placement whose new anchor fell outside one would appear
where the sim draws nothing.

THE RULE (:func:`drawn_as_placed`).  Every body's anchor is drawn exactly
when its placement's authored anchor is:

* placement drawn, body anchor in a box: the anchor moves ALONG THE BODY,
  to the point of its own written geometry (``geom_pts``, then its plan
  box corners) nearest its anchor that lies outside every box and on the
  DSF's tile; when the body has no such point it takes its PLACEMENT's
  anchor (drawn, by the premise) -- it is kept with its parent;
* placement excluded, body anchor drawn: the body takes its placement's
  anchor, and is excluded with it.

A moved body keeps its geometry and its seat: its offset is re-read from
the placement's frame at the new anchor (``placement_file.
authored_offset``) and its row is ``OBJECT_MSL`` at the height its old
anchor drew its zero at (``Body.msl_z``; the ground ``surface`` under the
old anchor plus any authored lift, as ``split_guard.on_tile`` seats an
off-tile body), so nothing the sim draws moves.  A body whose seat tilt is
baked is written ``R·(v − offset)`` about its anchor (``obj8_split.
tilt_matrix``): moving the offset by ``D`` moves its geometry by ``−R·D``
where the anchor moved by ``D``, so its row takes ``(R·D)ᵧ`` more and the
drawn model stays put to the cosine of the capped tilt (under 0.04 % of
the move).  A body whose old height cannot be read is left where it is
and counted (``exclusion_unmoved``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .exclusion import Exclusion, excluder_of

__all__ = ["drawn_as_placed", "REASON"]

#: the anchor reason a re-anchored body's reason opens with
REASON = "under a higher pack's exclude box: re-anchored where it is drawn (#2075)"


def _candidates(body: _t.Any) -> list[tuple[float, float]]:
    """``(lat, lon)`` points of the body's own geometry: its sampled
    written geometry, then the corners of its plan and geometry boxes."""
    pts = [(float(p[0]), float(p[1])) for p in getattr(body, "geom_pts", ()) or ()]
    for box in (getattr(body, "plan_box", None), getattr(body, "geom_box", None)):
        if box is not None:
            la0, lo0, la1, lo1 = (float(q) for q in box)
            pts += [(la0, lo0), (la0, lo1), (la1, lo0), (la1, lo1)]
    return pts


def _on(box: _t.Sequence[float] | None, lat: float, lon: float) -> bool:
    if box is None:
        return True
    w, s, e, n = box
    return w <= lon <= e and s <= lat <= n


def _drawn_point(body: _t.Any, record: _t.Any, boxes: _t.Sequence[Exclusion],
                 tile_box: _t.Sequence[float] | None) -> tuple[float, float]:
    """The nearest drawn on-tile point of the body, else the placement's
    own anchor."""
    a = body.anchor
    best, best_d = None, None
    for la, lo in _candidates(body):
        if not _on(tile_box, la, lo) or excluder_of(boxes, lo, la) is not None:
            continue
        d = (la - a.lat) ** 2 + (lo - a.lon) ** 2
        if best_d is None or d < best_d:
            best, best_d = (la, lo), d
    return best if best is not None else (record.lat, record.lon)


def _old_row(body: _t.Any, surface: _t.Callable | None) -> float | None:
    """The height the body's zero is drawn at from its CURRENT anchor:
    its row when the plan seats it by row, else the ground under the
    anchor plus its authored lift (``None``: unknown)."""
    if getattr(body, "msl_z", None) is not None:
        return float(body.msl_z)
    a = body.anchor
    z = surface(a.lat, a.lon) if surface is not None else None
    if z is None:
        z = a.surface_z
    if z is None:
        return None
    return float(z) + float(getattr(body, "lift_m", 0.0) or 0.0)


def drawn_as_placed(record: _t.Any, boxes: _t.Sequence[Exclusion],
                    surface: _t.Callable | None = None,
                    tile_box: _t.Sequence[float] | None = None,
                    counts: dict[str, int] | None = None) -> _t.Any:
    """``record`` (a ``placement_record.Split``) with every body drawn
    exactly when its placement is (module doc).  ``boxes`` are the
    exclusions of the packs above this one (``exclusion.boxes_above``);
    none returns the record unchanged.  Bodies off ``tile_box`` are left
    to ``split_guard`` / ``tile_route``."""
    if not boxes:
        return record
    placed = excluder_of(boxes, record.lon, record.lat) is None
    out, moved = [], False
    for b in record.bodies:
        a = b.anchor
        if not _on(tile_box, a.lat, a.lon) or \
                (excluder_of(boxes, a.lon, a.lat) is None) == placed:
            out.append(b)
            continue
        row = _old_row(b, surface)
        if placed and row is None:
            if counts is not None:
                counts["exclusion_unmoved"] = counts.get("exclusion_unmoved", 0) + 1
            out.append(b)
            continue
        la, lo = (_drawn_point(b, record, boxes, tile_box) if placed
                  else (record.lat, record.lon))
        out.append(_moved(b, record, la, lo, row))
        moved = True
        if counts is not None:
            k = "exclusion_reanchored" if placed else "exclusion_with_placement"
            counts[k] = counts.get(k, 0) + 1
    return _dc.replace(record, bodies=tuple(out)) if moved else record


def _moved(b: _t.Any, record: _t.Any, la: float, lo: float,
           row: float | None) -> _t.Any:
    """``b`` anchored at ``(la, lo)``, its geometry and drawn zero kept."""
    from .placement_file import authored_offset    # lazy, as split_guard
    a = b.anchor
    y0 = float(a.y_zero)
    off = authored_offset(la, lo, y0, record.lat, record.lon, record.heading)
    a2 = _dc.replace(a, lat=la, lon=lo, offset=off,
                     reason=f"{REASON}; was: {a.reason}")
    if row is None:                 # excluded with its placement: not drawn
        return _dc.replace(b, anchor=a2)
    seat = getattr(b, "seat", None)
    if seat is not None and getattr(seat, "applied", False):
        from .obj8_split import tilt_matrix
        d = (off[0] - a.offset[0], 0.0, off[2] - a.offset[2])
        row += float((tilt_matrix(seat.grad) @ d)[1])
    return _dc.replace(b, anchor=_dc.replace(a2, surface_z=row),
                       msl_z=row, lift_m=0.0)
