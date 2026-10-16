"""THE PUBLISHED RUNWAY WITNESSES — a runway's code number and letter and
each end's approach class, read back from the sidecar ``runway_axes`` row
the build published (slots 11–16; regulation-conformance spec §3, owner
RULINGS 2026-10-15m (2) / 15n).

ONE read for both readers: v2 verify and the census price the strip, the
RSA and the RAOA by the witness the generator used, never by a classifier
of their own.  A row written before the slots (a patch predating them)
falls back to the shared classifier (``law.reference_code``) for the code
and reads NO end class (``None``: the caller keeps its pre-witness
reading).
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.reference_code import runway_code_number

__all__ = ["published_row", "published_code_number", "published_code_letter",
           "published_end_classes"]

#: ``runway_axes`` slots (``pipeline/publication.py``)
_CODE, _LETTER, _CLASS_A, _CLASS_B = 11, 12, 13, 14


def published_row(rows, ref: str | None) -> list | None:
    """The ``runway_axes`` row of ``ref``, or ``None``."""
    for r in rows or ():
        if str(r[0]) == str(ref):
            return list(r)
    return None


def published_code_number(rows, ref: str | None, length_m: float, law: Law) -> int:
    """The loader's code number for ``ref``; the shared classifier on
    ``length_m`` where the row does not carry it."""
    r = published_row(rows, ref)
    if r is not None and len(r) > _CODE and r[_CODE] is not None:
        return int(r[_CODE])
    return runway_code_number(law, length_m)


def published_code_letter(rows, ref: str | None, fallback: str | None) -> str | None:
    """The loader's code letter for ``ref``; ``fallback`` (the caller's
    own reading, e.g. the shape's emitted tag) where the row lacks it."""
    r = published_row(rows, ref)
    if r is not None and len(r) > _LETTER and r[_LETTER]:
        return str(r[_LETTER])
    return fallback


def published_end_classes(rows, ref: str | None, a, b,
                          to_m: _t.Callable[[float, float], tuple[float, float]],
                          ) -> tuple[str, str] | None:
    """``(class at a, class at b)`` — the approach classes of ``ref``'s
    two ends, matched to the caller's axis points ``a`` / ``b`` (metres,
    ``to_m(lat, lon)``) by the nearer published end.  ``None`` where the
    row does not carry them."""
    r = published_row(rows, ref)
    if r is None or len(r) <= _CLASS_B:
        return None
    pa, pb = to_m(float(r[1]), float(r[2])), to_m(float(r[3]), float(r[4]))
    same = math.dist(pa, a) + math.dist(pb, b)
    flip = math.dist(pb, a) + math.dist(pa, b)
    ca, cb = str(r[_CLASS_A]), str(r[_CLASS_B])
    return (ca, cb) if same <= flip else (cb, ca)
