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
from ..law.reference_code import runway_code_number, status_of_classes

__all__ = ["published_row", "published_code_number", "published_code_letter",
           "published_end_classes", "published_end_profiles", "published_status"]

#: ``runway_axes`` slots (``pipeline/publication.py``)
_INSTRUMENT = 10
_CODE, _LETTER, _CLASS_A, _CLASS_B = 11, 12, 13, 14
_DISP_A, _DISP_B = 17, 18
_DATUM_A, _DATUM_B = 20, 21


def published_row(rows, ref: str | None) -> list | None:
    """The ``runway_axes`` row of ``ref``, or ``None``."""
    for r in rows or ():
        if str(r[0]) == str(ref):
            return list(r)
    return None


def published_status(rows, ref: str | None) -> int:
    """THE RUNWAY'S INSTRUMENT STATUS as the sidecar publishes it
    (RULINGS 2026-10-15k (3); #811): ``law.reference_code.status_of_classes``
    over the ends' classes (slots 13 / 14) and the instrument flag (slot
    10) — the ONE read verify and the census make, so both price the
    strip's end, its half-width and the RSA by the status the generator
    did.  A crossing piece's ref (``a+b``) reads the stronger of its two
    runways (``reference_code.ref_status``).  Non-instrument (0) for a ref
    the rows do not carry, or a row written before the status."""
    if ref is None:
        return 0
    return max(_one_status(rows, r) for r in str(ref).split("+"))


def _one_status(rows, ref: str) -> int:
    r = published_row(rows, ref)
    if r is None or len(r) <= _INSTRUMENT:
        return 0
    classes = (r[_CLASS_A], r[_CLASS_B]) if len(r) > _CLASS_B else ()
    return status_of_classes(classes, bool(r[_INSTRUMENT]))


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


def published_end_profiles(law: Law, rows, ref: str | None, a, b,
                           to_m: _t.Callable[[float, float], tuple[float, float]],
                           code_number: int | None, code_letter: str | None,
                           instrument: bool) -> tuple:
    """``(profile beyond a, profile beyond b)`` — ``tables.
    runway_end_profile`` for each END with the class and displaced length
    the build published for it (slots 13 / 14, 17 / 18; RULINGS
    2026-10-15m (1)), matched to the caller's axis points like
    :func:`published_end_classes`.  A row without the slots reads the
    profile with no approach surface (the pre-witness reading)."""
    from ..law.tables import runway_end_profile
    cls = published_end_classes(rows, ref, a, b, to_m)
    if cls is None:
        p = runway_end_profile(law, code_number, code_letter, instrument)
        return p, p
    r = published_row(rows, ref)
    disp = ((float(r[_DISP_A] or 0.0), float(r[_DISP_B] or 0.0))
            if r is not None and len(r) > _DISP_B else (0.0, 0.0))
    datum = ((float(r[_DATUM_A] or 0.0), float(r[_DATUM_B] or 0.0))
             if r is not None and len(r) > _DATUM_B else (0.0, 0.0))
    pa, pb = to_m(float(r[1]), float(r[2])), to_m(float(r[3]), float(r[4]))
    if math.dist(pa, a) + math.dist(pb, b) > math.dist(pb, a) + math.dist(pa, b):
        disp, datum = (disp[1], disp[0]), (datum[1], datum[0])
    return tuple(runway_end_profile(law, code_number, code_letter, instrument, c, d, t)
                 for c, d, t in zip(cls, disp, datum))
