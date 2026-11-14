"""A STOCK ``OBJECT_MSL`` ROW ON AN ON-GROUND OR LIFTED FRAME MOVES WITH
IT (issue #1837; the relative sibling of #1252's ``frame_riders.rider_seats``).

KMCI: 716 library rows (``car_static_invar``, ``AreaFlood_Medium``) are
authored ``OBJECT_MSL`` on the decks of the pack's own garages
(``OBJECT``) and terminal (``OBJECT_AGL +8.5``).  #1252's rule reaches a
frame only through its elevation column (an ``OBJECT_MSL`` frame), so the
11d conversion put every one of them on the ground under the deck.

AN ``OBJECT`` / ``OBJECT_AGL`` FRAME HAS NO AUTHORED ZERO OF ITS OWN: it
stood ``y = 0`` on the terrain its author saw, plus its lift.  Its riders
SAY where that was: a row at ``E`` standing on the frame's surface ``y``
puts the author's frame zero at ``E - y``.  The witness is the geometry
and the rows, never a name:

* A row STANDS on a surface ``y`` at a trial zero ``Z`` when its height
  over the zero, ``h = E - Z``, is on it (``y <= h <= y + contact_m``,
  ``ground_rider_under_m`` of slack below) and no other surface of the frame is
  in ``(y, h + contact_m]`` -- a row inside a slab stands on its top.
* The frame's AUTHORED ZERO ``Z_F`` is the trial zero (one ``E - y`` of a
  row over it) that the most of its rows stand at (within ``ground_rider_fit_m``), among
  those within ``ground_rider_tol_m`` of the zero the build reads for it (``adapted_riders.
  frame_zero``: the zero its terrain was adapted for, else the surface at
  its origin plus its lift); ties go to the nearest.  One zero per ANCHOR
  FAMILY (origin and lift): the files of one model share it.
* A row of the family that stands at ``Z_F``, or hangs ENCLOSED by its
  geometry there (a surface under it and one over it under its anchor --
  a ceiling light), is its content and moves by the family's seat delta,
  ``written zero - Z_F`` (per cut body: the body holding the triangle).
* A family whose rows stand at no zero near the build's moves nobody, and
  a row over nothing converts as before.

The three numbers are ``structures.toml [placement] ground_rider_*``,
with their reasons.
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np

from .frame_riders import _M_PER_DEG, MOVE_MIN_M, _Deck, _FrameMove, _local

__all__ = ["ground_rider_seats", "GROUND_RIDER", "Law", "law_of"]

#: the ``MslSeat.why`` this rule writes
GROUND_RIDER = "ground_frame_rider"

class Law(_t.NamedTuple):
    """``structures.toml [placement] ground_rider_*`` (their reasons are
    there): ``tol_m`` the witnessed zero's allowance off the build's (0
    disarms), ``fit_m`` the vote's exact-contact band, ``under_m`` how far
    a row may sit into its surface."""

    tol_m: float = 0.0
    fit_m: float = 0.0
    under_m: float = 0.0


def law_of(placement: _t.Any) -> Law:
    """The rule's :class:`Law` from a ``[placement]`` table."""
    return Law(float(placement.ground_rider_tol_m),
               float(placement.ground_rider_fit_m),
               float(placement.ground_rider_under_m))
_FRAME_KINDS = ("OBJECT", "OBJECT_AGL")


def _lift(row: _t.Any) -> float:
    return float(row.elevation or 0.0) if row.kind == "OBJECT_AGL" else 0.0


def _family_frames(rows: _t.Sequence[_t.Any], pack_root: str,
                   zeros: _t.Mapping[int, tuple[float, dict]],
                   surface: _t.Callable, authored: _t.Sequence[tuple]
                   ) -> dict[tuple, tuple[float, list[_FrameMove]]]:
    """``family key -> (build's zero, [frame])``: every ``OBJECT`` /
    ``OBJECT_AGL`` row of the pack with a static solid, its ``_FrameMove``
    carrying the WRITTEN zero (``zero``, by component on a cut frame); the
    build's zero is ``adapted_riders.frame_zero`` of the family."""
    from .adapted_riders import frame_zero
    from .pack import authored_source
    memo: dict[tuple[str, bool], "_Deck | None"] = {}
    out: dict[tuple, tuple[float, list[_FrameMove]]] = {}
    for i, row in enumerate(rows):
        if row.kind not in _FRAME_KINDS:
            continue
        res = str(row.def_path)
        if not res.lower().endswith(".obj"):
            continue
        whole, comps = zeros.get(i, (None, {}))
        mk = (res, bool(comps))          # a cut frame's riders read its components
        if mk not in memo:
            path, _r = authored_source(os.path.join(pack_root, res.lstrip("/")), pack_root)
            memo[mk] = (_Deck.read(path, components=mk[1])
                        if path and os.path.isfile(path) else None)
        deck = memo[mk]
        if deck is None:
            continue
        la, lo, lift = float(row.lat), float(row.lon), _lift(row)
        key = (round(la, 7), round(lo, 7), round(lift, 3))
        if key not in out:
            ref = frame_zero(surface, (la, lo), lift, authored)
            if ref is None:
                continue
            out[key] = (ref, [])
        if whole is None:
            g = surface(la, lo)
            if g is None:
                continue
            whole = float(g) + lift
        out[key][1].append(_FrameMove(i, la, lo, float(row.heading_deg), whole,
                                      deck, whole, dict(comps)))
    return {k: v for k, v in out.items() if v[1]}


def _surfaces(frames: _t.Sequence[_FrameMove], lat: float, lon: float
              ) -> list[tuple[float, _FrameMove, int]]:
    """``(authored y, frame, triangle)`` of every frame surface over the
    anchor, lowest first."""
    hits = []
    for f in frames:
        x, z = _local(f, lat, lon)
        if x * x + z * z > f.deck.reach ** 2:
            continue
        ys, tri = f.deck.heights(x, z)
        hits.extend((float(y), f, int(t)) for y, t in zip(ys, tri, strict=True))
    hits.sort(key=lambda h: h[0])
    return hits


def _stands(hits: _t.Sequence[tuple], h: float, contact_m: float,
            headroom_m: float, under_m: float) -> "tuple | None":
    """The surface a row at height ``h`` over the zero stands on within
    ``contact_m`` with no other surface up to ``headroom_m`` over it (a
    row inside a slab stands on its top; module doc), or ``None``."""
    under = [s for s in hits if s[0] - under_m <= h]
    if not under:
        return None
    top = under[-1]
    if h - top[0] > contact_m:
        return None
    if any(top[0] < s[0] <= h + headroom_m for s in hits):
        return None
    return top


def _enclosed(hits: _t.Sequence[tuple], h: float) -> "tuple | None":
    """The surface under a row hanging inside the frame at height ``h``
    (one under it and one over it), or ``None``."""
    under = [s for s in hits if s[0] <= h]
    return under[-1] if under and any(s[0] > h for s in hits) else None


def _family_zero(ref: float, rows_hits: _t.Sequence[tuple[float, list]],
                 contact_m: float, law: Law) -> "float | None":
    """THE AUTHORED ZERO ``Z_F`` (module doc), or ``None``."""
    best: "tuple[int, float, float] | None" = None
    trials = sorted({round(e - s[0], 3) for e, hits in rows_hits for s in hits
                     if abs(e - s[0] - ref) <= law.tol_m})
    for z in trials:
        n = sum(1 for e, hits in rows_hits
                if _stands(hits, e - z, law.fit_m, contact_m, law.under_m))
        key = (n, -abs(z - ref), z)
        if n and (best is None or key > best):
            best = key
    return None if best is None else best[2]


def ground_rider_seats(rows: _t.Sequence[_t.Any], candidates: _t.Iterable[int],
                       pack_root: str, zeros: _t.Mapping[int, tuple[float, dict]],
                       surface: _t.Callable, contact_m: float, law: Law,
                       authored: _t.Sequence[tuple] = (),
                       counts: "dict | None" = None) -> tuple:
    """The ``MslSeat`` of every ``OBJECT_MSL`` row of ``candidates`` that
    stands on (or hangs enclosed in) an ``OBJECT`` / ``OBJECT_AGL`` frame of
    the pack at that frame's authored zero, moved by the frame's seat
    delta (module doc).  ``zeros`` is ``frame_riders._written_zeros``."""
    from ..model.placement import KIND_MSL, MslSeat
    cand = [i for i in candidates if 0 <= i < len(rows)
            and rows[i].kind == KIND_MSL and rows[i].elevation is not None]
    if not cand or not pack_root or contact_m <= 0.0 or law.tol_m <= 0.0:
        return ()
    fams = _family_frames(rows, pack_root, zeros, surface, authored)
    keys = list(fams)
    lat = np.array([fams[k][1][0].lat for k in keys])
    lon = np.array([fams[k][1][0].lon for k in keys])
    reach = np.array([max(f.deck.reach for f in fams[k][1]) for k in keys])
    over: dict[tuple, list[tuple[int, float, list]]] = {}
    for i in cand:
        la, lo = float(rows[i].lat), float(rows[i].lon)
        e = (lon - lo) * _M_PER_DEG * math.cos(math.radians(la))
        n = (lat - la) * _M_PER_DEG
        for k in np.flatnonzero(e * e + n * n <= reach * reach):
            hits = _surfaces(fams[keys[int(k)]][1], la, lo)
            if hits:
                over.setdefault(keys[int(k)], []).append(
                    (i, float(rows[i].elevation), hits))
    best: dict[int, tuple[float, float]] = {}        # row -> (height, move)
    n_fams = 0
    for key, members in over.items():
        ref = fams[key][0]
        zf = _family_zero(ref, [(e, h) for _i, e, h in members], contact_m, law)
        if zf is None:
            continue
        n_fams += 1
        for i, e, hits in members:
            s = (_stands(hits, e - zf, contact_m, contact_m, law.under_m)
                 or _enclosed(hits, e - zf))
            if s is None:
                continue
            y, f, tri = s
            move = f.move_of(tri) - zf      # the written zero under it
            if i not in best or zf + y > best[i][0]:
                best[i] = (zf + y, move)
    out = tuple(MslSeat(i, str(rows[i].def_path), float(rows[i].lon),
                        float(rows[i].lat), float(getattr(rows[i], "heading_deg", 0.0)),
                        float(rows[i].elevation) + mv, GROUND_RIDER)
                for i, (_h, mv) in sorted(best.items()))
    if counts is not None:
        counts["ground_riders_moved"] = len(out)
        counts["ground_rider_families"] = n_fams
        counts["ground_riders_still"] = sum(1 for _h, mv in best.values()
                                            if abs(mv) <= MOVE_MIN_M)
    return out
