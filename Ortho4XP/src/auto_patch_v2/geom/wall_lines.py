"""THE WALL LINES UNDER A HARD DECK, as plan numbers (owner RULINGS
2026-10-30f (3)): the face lines a frame's vertical faces stand on across
the road, and which of them is the INNER face on each side of the deck's
middle.  ``planar/deck_walls`` reads the faces off the frame's geometry;
this leaf holds the pure arithmetic on them, so ``model/deck_bank`` (read
by ``constraints``, which may not import ``planar``) and the planar cut
(``planar/deck_bridge._walled_trench``) answer "walled or banked" with ONE
derivation.  Pure numbers; nothing here names a pack or an airport.
"""
from __future__ import annotations

import typing as _t

__all__ = ["Face", "inner_faces", "project_span", "wall_lines"]

#: face lines closer than this across the road are one line (metres)
_LINE_BIN_M = 0.5
#: a face line is a wall when it covers this share of the stretch asked
_COVER_MIN = 0.5

#: one wall face: ``(u across the road, s0, s1 along it)`` (frame metres)
Face = tuple[float, float, float]
#: a plan point / direction (metres)
XY = tuple[float, float]


def _covered(faces: _t.Sequence[Face], s0: float, s1: float) -> float:
    """The share of ``[s0, s1]`` the faces' along-road spans cover."""
    iv = sorted((max(s0, a), min(s1, b)) for _u, a, b in faces if b > s0 and a < s1)
    got, end = 0.0, s0
    for a, b in iv:
        if b > end:
            got += b - max(a, end)
            end = b
    return got / (s1 - s0) if s1 > s0 else 0.0


def inner_faces(faces: _t.Sequence[Face], s0: float, s1: float, u_mid: float,
                reach: "tuple[float, float] | None" = None
                ) -> tuple["float | None", "float | None"]:
    """``(u_a, u_b)``: the inner face on each side of ``u_mid`` over the
    stretch ``[s0, s1]`` -- the face line nearest the middle covering
    :data:`_COVER_MIN` of it -- or ``None`` on a side with none.

    #2157 R2 (a deck's floor is under the deck): with ``reach`` (the ring's
    own ``(u_lo, u_hi)``) only faces within :data:`_LINE_BIN_M` of it are
    this deck's walls (a frame's wall under ANOTHER span is not), and the
    cover is measured against the stretch those faces occupy -- the walls'
    own length, never the slopes of the plan past them.  A line that misses
    the cover in its own bin is taken with its neighbour bins (a wall a few
    centimetres out of straight is one wall); a bin that passes alone keeps
    its own line exactly.  Both only ADD walls."""
    if reach is not None:
        lo, hi = reach[0] - _LINE_BIN_M, reach[1] + _LINE_BIN_M
        faces = [f for f in faces if lo <= f[0] <= hi]
        span = _occupied(faces, s0, s1)
        if span is None:
            return None, None
        s0, s1 = span
    walls = _lines(faces, s0, s1, reach is not None)
    a = [u for u in walls if u < u_mid]
    b = [u for u in walls if u > u_mid]
    return (max(a) if a else None), (min(b) if b else None)


def wall_lines(faces: _t.Sequence[Face], s0: float, s1: float) -> list[float]:
    """Every wall line ``u`` of ``faces`` over ``[s0, s1]``, ascending: a
    line (adjacent bins merged, :func:`inner_faces`) covering
    :data:`_COVER_MIN` of the stretch the faces themselves occupy there
    (#2157 R3, ``planar/deck_span_cut``: a frame's facing wall pairs)."""
    span = _occupied(faces, s0, s1)
    return [] if span is None else sorted(_lines(faces, span[0], span[1], True))


def _lines(faces: _t.Sequence[Face], s0: float, s1: float, merge: bool) -> list[float]:
    """The wall lines' ``u`` (:func:`inner_faces`): each bin covering
    :data:`_COVER_MIN` of ``[s0, s1]``, and with ``merge`` each run of weak
    adjacent bins that covers it together."""
    lines: dict[int, list[Face]] = {}
    for f in faces:
        lines.setdefault(int(round(f[0] / _LINE_BIN_M)), []).append(f)
    walls = [_mean_u(fs) for fs in lines.values() if _covered(fs, s0, s1) >= _COVER_MIN]
    if merge:
        walls += [_mean_u(fs) for fs in _merged_runs(lines, s0, s1)
                  if _covered(fs, s0, s1) >= _COVER_MIN]
    return walls


def _mean_u(fs: _t.Sequence[Face]) -> float:
    return sum(f[0] for f in fs) / len(fs)


def _occupied(faces: _t.Sequence[Face], s0: float, s1: float
              ) -> "tuple[float, float] | None":
    """The stretch of ``[s0, s1]`` the faces occupy (least start to
    greatest end, clipped), or ``None`` where none stands on it."""
    iv = [(max(s0, a), min(s1, b)) for _u, a, b in faces if b > s0 and a < s1]
    if not iv:
        return None
    lo, hi = min(a for a, _b in iv), max(b for _a, b in iv)
    return (lo, hi) if hi > lo else None


def _merged_runs(lines: "dict[int, list[Face]]", s0: float, s1: float) -> list:
    """The faces of each run of adjacent bins none of which covers
    :data:`_COVER_MIN` of ``[s0, s1]`` alone (:func:`inner_faces`)."""
    weak = sorted(k for k, fs in lines.items() if _covered(fs, s0, s1) < _COVER_MIN)
    runs: list[list[int]] = []
    for k in weak:
        if runs and k == runs[-1][-1] + 1:
            runs[-1].append(k)
        else:
            runs.append([k])
    return [[f for k in run for f in lines[k]] for run in runs if len(run) > 1]


def project_span(ring, r: XY) -> tuple[float, float]:
    """``(least, greatest)`` of the ring's points projected on ``r``."""
    vals = [q[0] * r[0] + q[1] * r[1] for q in ring]
    return min(vals), max(vals)
