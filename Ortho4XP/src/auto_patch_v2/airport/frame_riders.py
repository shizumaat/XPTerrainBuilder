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

THE ABSOLUTE HALF (issue #1252; :func:`frame_moves`, :func:`rider_seats`).

The 11d conversion turns every ``OBJECT_MSL`` row into an on-ground row
(owner RULINGS 2026-09-11d, stock library rows included), and the main
pack's frames are re-seated by the placement plan.  A library car an
author parked ON a garage deck (``lib/cars/car_static_invar.obj``
``OBJECT_MSL 191.10`` over a garage authored ``OBJECT_MSL 184.36`` with a
deck 6.5 m up) is neither: converting it drops it 6.5 m under the deck,
and leaving it as authored leaves it where the garage WAS.  It is the
garage's CONTENT, and keeps its authored relation to it: it moves by the
garage's own displacement, ``written zero - authored zero``, and is
written ``OBJECT_MSL`` there.  The same row on the open ground converts
as before and follows the new mesh.

THE WITNESS IS THE GEOMETRY, never a name: a row RIDES a frame when the
frame is an ``OBJECT_MSL`` row of the airport pack (its authored zero is
its elevation column), the row's anchor stands over a static solid
triangle of the frame's AUTHORED geometry, and the row's elevation is that
triangle's height at the anchor (in the authored world, ``zero + y``) to
within ``contact_m`` — the highest such surface under the anchor is the
one it stands on.  A frame the plan leaves where it was (displacement
within ``MOVE_MIN_M``) moves no rider; on a CUT frame the rider takes the
move of the body that holds the very triangle it stands on (the body's
``components``; a component no body holds takes the frame's median).

Name-free and pack-free: :func:`frame_moves` reads the airport pack's
plan, :func:`rider_seats` takes any pack's rows — the airport pack's own
library rows (the plan never sees a stock object) and a sibling pack's
(``sibling_riders``) alike.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np

__all__ = ["frame_rider_seats", "FRAME_RIDER", "MOVE_MIN_M", "DECK_RIDER",
           "frame_moves", "rider_seats", "over_objects"]

#: the ``MslSeat.why`` the lifted half writes
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


# ── the absolute half (#1252): OBJECT_MSL rows on a re-seated MSL frame ──

#: the ``MslSeat.why`` the absolute half writes
DECK_RIDER = "deck_rider"
_M_PER_DEG = 111_320.0


@_dc.dataclass(frozen=True)
class _Deck:
    """A resource's STATIC solid triangles ``(m, 3, 3)`` in its authored
    frame, their plan boxes, the plan reach from its origin, and each
    triangle's CONNECTED COMPONENT (``obj8.solid_components`` order: the
    index a cut body's ``components`` names)."""

    tris: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    reach: float
    component: np.ndarray

    @classmethod
    def read(cls, path: str) -> "_Deck | None":
        """``None`` when the file has no static solid or cannot be read
        (an animated part never witnesses, issue #612)."""
        from . import obj8 as _obj8
        try:
            g = _obj8.parse_obj8(path)
        except (OSError, ValueError):
            return None
        label = np.full(g.solid.shape[0], -1, dtype=np.int64)
        for k, comp in enumerate(_obj8.solid_components(g)):
            label[comp.idx] = k
        keep = (~g.animated if g.animated.shape[0]
                else np.ones(g.solid.shape[0], dtype=bool))
        if not keep.any():
            return None
        t = g.vertices[g.solid[keep]]
        plan = t[:, :, [0, 2]]
        return cls(t, plan.min(1), plan.max(1),
                   float(np.hypot(plan[..., 0], plan[..., 1]).max()), label[keep])

    def heights(self, x: float, z: float) -> tuple[np.ndarray, np.ndarray]:
        """``(authored y, triangle index)`` of every triangle over the plan
        point ``(x, z)`` (barycentric, edges inclusive)."""
        sel = np.flatnonzero((self.lo[:, 0] <= x) & (self.hi[:, 0] >= x)
                             & (self.lo[:, 1] <= z) & (self.hi[:, 1] >= z))
        if not sel.shape[0]:
            return np.zeros(0), sel
        t = self.tris[sel]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        d = ((b[:, 2] - c[:, 2]) * (a[:, 0] - c[:, 0])
             + (c[:, 0] - b[:, 0]) * (a[:, 2] - c[:, 2]))
        ok = np.abs(d) > 1e-12
        d = np.where(ok, d, 1.0)
        l1 = ((b[:, 2] - c[:, 2]) * (x - c[:, 0])
              + (c[:, 0] - b[:, 0]) * (z - c[:, 2])) / d
        l2 = ((c[:, 2] - a[:, 2]) * (x - c[:, 0])
              + (a[:, 0] - c[:, 0]) * (z - c[:, 2])) / d
        l3 = 1.0 - l1 - l2
        inside = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        return (l1 * a[:, 1] + l2 * b[:, 1] + l3 * c[:, 1])[inside], sel[inside]


@_dc.dataclass(frozen=True)
class _FrameMove:
    """One re-seated ``OBJECT_MSL`` frame of the airport pack: where its
    authored ``y = 0`` was (``zero``), its authored deck, and its
    displacement — ``whole``, and per connected component of a CUT frame
    the displacement of the body that holds it (``by_component``)."""

    index: int
    lat: float
    lon: float
    heading_deg: float
    zero: float
    deck: _Deck
    whole: float
    by_component: _t.Mapping[int, float] = _dc.field(default_factory=dict)

    def move_of(self, tri: int) -> float:
        """The displacement of the body holding triangle ``tri``."""
        return self.by_component.get(int(self.deck.component[tri]), self.whole)


def _written_zeros(rows: _t.Sequence[_t.Any], splits: _t.Sequence[_t.Any],
                   msl: _t.Sequence[_t.Any], conversions: _t.Sequence[_t.Any],
                   surface: Surface) -> dict[int, tuple[float, dict]]:
    """``index -> (whole written zero, {component: written zero})`` for
    every airport-pack row the plan MOVES: a cut frame by its bodies
    (``surface_z - y_zero``, the file's zero plane in world height; the
    whole is their median), a row seat by its elevation, an on-ground
    conversion by the drape at its anchor."""
    out: dict[int, tuple[float, dict]] = {}
    for s in splits:
        comps: dict[int, float] = {}
        for b in s.bodies:
            if b.surface_z is None or float(b.lift_m or 0.0):
                continue
            for k in b.components:
                comps[int(k)] = float(b.surface_z) - float(b.y_zero)
        if comps:
            zs = sorted(comps.values())
            out[int(s.placement.index)] = (zs[len(zs) // 2], comps)
    for m in msl:
        out.setdefault(int(m.index), (float(m.elevation), {}))
    for c in conversions:
        if 0 <= c.index < len(rows) and c.index not in out:
            g = surface(float(rows[c.index].lat), float(rows[c.index].lon))
            if g is not None:
                out[int(c.index)] = (float(g), {})
    return out


def frame_moves(dump: _t.Any, pack_root: str, splits: _t.Sequence[_t.Any],
                msl: _t.Sequence[_t.Any], conversions: _t.Sequence[_t.Any],
                surface: Surface) -> list[_FrameMove]:
    """The airport pack's re-seated ``OBJECT_MSL`` frames whose geometry
    a rider could stand on (module doc).  A frame moved by less than
    ``MOVE_MIN_M`` everywhere is left out: it moves nobody."""
    from ..model.placement import KIND_MSL
    from .pack import authored_source
    rows = list(getattr(dump, "placements", ()) or ())
    zeros = _written_zeros(rows, splits, msl, conversions, surface)
    memo: dict[str, "_Deck | None"] = {}
    out = []
    for i, (whole, comps) in sorted(zeros.items()):
        row = rows[i] if 0 <= i < len(rows) else None
        if row is None or row.kind != KIND_MSL or row.elevation is None:
            continue
        zero = float(row.elevation)
        moves = {k: z - zero for k, z in comps.items()}
        if abs(whole - zero) <= MOVE_MIN_M and all(abs(m) <= MOVE_MIN_M
                                                   for m in moves.values()):
            continue
        res = str(row.def_path)
        if res not in memo:
            path, _r = authored_source(os.path.join(pack_root or "", res), pack_root)
            memo[res] = (_Deck.read(path) if pack_root and path
                         and os.path.isfile(path) else None)
        if memo[res] is not None:
            out.append(_FrameMove(i, float(row.lat), float(row.lon),
                                  float(row.heading_deg), zero, memo[res],
                                  whole - zero, moves))
    return out


def _local(f: _FrameMove, lat: float, lon: float) -> tuple[float, float]:
    """``(x, z)`` of ``(lat, lon)`` in the frame's authored plan (the
    inverse of ``obj8._to_frame``)."""
    e = (lon - f.lon) * _M_PER_DEG * math.cos(math.radians(f.lat))
    n = (lat - f.lat) * _M_PER_DEG
    h = math.radians(f.heading_deg)
    s, c = math.sin(h), math.cos(h)
    return e * c - n * s, -(e * s + n * c)


def _stands_on(frames: _t.Sequence[_FrameMove], lat: float, lon: float,
               elevation: float, contact_m: float) -> "tuple[float, float] | None":
    """``(authored deck height, displacement)`` of the highest frame
    surface under the anchor that the row's ``elevation`` stands on within
    ``contact_m`` (module doc) — the displacement of the body holding that
    surface; ``None`` when it stands on none."""
    best = None
    for f in frames:
        x, z = _local(f, lat, lon)
        if x * x + z * z > f.deck.reach ** 2:
            continue
        ys, tri = f.deck.heights(x, z)
        ys = ys + f.zero
        near = np.abs(elevation - ys) <= contact_m
        if near.any():
            k = int(np.argmax(np.where(near, ys, -np.inf)))
            if best is None or float(ys[k]) > best[0]:
                best = (float(ys[k]), f.move_of(int(tri[k])))
    return best


def rider_seats(rows: _t.Sequence[_t.Any], candidates: _t.Iterable[int],
                frames: _t.Sequence[_FrameMove], contact_m: float,
                counts: "dict | None" = None) -> tuple:
    """The ``MslSeat`` of every ``OBJECT_MSL`` row of ``candidates`` (indices
    into ``rows``, any pack's) standing on a re-seated frame's deck, moved
    by that frame's displacement under it."""
    from ..model.placement import KIND_MSL, MslSeat
    out = []
    for i in candidates:
        row = rows[i]
        if row.kind != KIND_MSL or row.elevation is None:
            continue
        la, lo, e = float(row.lat), float(row.lon), float(row.elevation)
        hit = _stands_on(frames, la, lo, e, contact_m)
        if hit is None:
            continue
        out.append(MslSeat(i, str(row.def_path), lo, la,
                           float(getattr(row, "heading_deg", 0.0)),
                           e + hit[1], DECK_RIDER))
    if counts is not None:
        counts["deck_riders_moved"] = counts.get("deck_riders_moved", 0) + len(out)
        counts["deck_rider_frames"] = len(frames)
    return tuple(out)


def over_objects(sources: _t.Iterable[tuple[_t.Hashable, _t.Any, str,
                                            "_t.Mapping[str, str] | None"]],
                 box: "tuple[float, float, float, float] | None" = None
                 ) -> _t.Callable[..., bool]:
    """``over(lat, lon, skip=None) -> bool``: does the point stand over a
    static solid triangle of ANY object the ``sources`` place?  Each source
    is ``(key, dump, pack_root, library index)``: every row kind, its
    authored geometry, a library path resolved through the index
    (``obj8.resolve_resource``).  ``box`` ``(west, south, east, north)``
    keeps only the rows inside it.  ``skip = (key, lat, lon)`` leaves out
    that source's rows at that very origin — the row asking, and the other
    files of its own model (``msl_feet``'s rigid set).  The owner's
    2026-11-04 witness for a sibling row "on top of / overlapping" another
    object (#1252)."""
    from .obj8 import resolve_resource
    from .pack import authored_source
    memo: dict[tuple, "_Deck | None"] = {}
    placed: list[tuple[_t.Hashable, _FrameMove]] = []
    for key, dump, root, index in sources:
        for i, row in enumerate(getattr(dump, "placements", ()) or ()):
            la, lo = float(row.lat), float(row.lon)
            if box is not None and not (box[0] <= lo <= box[2] and box[1] <= la <= box[3]):
                continue
            res = str(row.def_path)
            if (root, res) not in memo:
                phys = (resolve_resource(res, root, index)
                        if res.lower().endswith(".obj") else None)
                path = authored_source(phys, root)[0] if phys else None
                memo[(root, res)] = _Deck.read(path) if path else None
            if memo[(root, res)] is not None:
                placed.append((key, _FrameMove(i, la, lo, float(row.heading_deg),
                                               0.0, memo[(root, res)], 0.0)))
    lat = np.array([f.lat for _k, f in placed])
    lon = np.array([f.lon for _k, f in placed])
    reach = np.array([f.deck.reach for _k, f in placed])

    def over(la: float, lo: float, skip: "tuple | None" = None) -> bool:
        if not placed:
            return False
        e = (lon - lo) * _M_PER_DEG * math.cos(math.radians(la))
        n = (lat - la) * _M_PER_DEG
        for k in np.flatnonzero(e * e + n * n <= reach * reach):
            key, f = placed[int(k)]
            if (skip is not None and key == skip[0]
                    and round(f.lat, 8) == round(skip[1], 8)
                    and round(f.lon, 8) == round(skip[2], 8)):
                continue
            x, z = _local(f, la, lo)
            if f.deck.heights(x, z)[0].shape[0]:
                return True
        return False
    return over
