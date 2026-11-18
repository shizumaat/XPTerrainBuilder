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

__all__ = ["Face", "inner_faces", "project_span"]

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


def inner_faces(faces: _t.Sequence[Face], s0: float, s1: float, u_mid: float
                ) -> tuple["float | None", "float | None"]:
    """``(u_a, u_b)``: the inner face on each side of ``u_mid`` over the
    stretch ``[s0, s1]`` — the face line nearest the middle covering
    :data:`_COVER_MIN` of it — or ``None`` on a side with none."""
    lines: dict[int, list[Face]] = {}
    for f in faces:
        lines.setdefault(int(round(f[0] / _LINE_BIN_M)), []).append(f)
    walls = [(sum(f[0] for f in fs) / len(fs)) for fs in lines.values()
             if _covered(fs, s0, s1) >= _COVER_MIN]
    a = [u for u in walls if u < u_mid]
    b = [u for u in walls if u > u_mid]
    return (max(a) if a else None), (min(b) if b else None)


def project_span(ring, r: XY) -> tuple[float, float]:
    """``(least, greatest)`` of the ring's points projected on ``r``."""
    vals = [q[0] * r[0] + q[1] * r[1] for q in ring]
    return min(vals), max(vals)
