"""Geometry helpers wrapping shapely operations that MISBEHAVE on valid
input — one place for the "GEOS is wrong here, and this is the measured
remedy" knowledge, so no call site invents its own.

``min_rotated_rect``
    ``Polygon.minimum_rotated_rectangle`` (GEOS ``oriented_envelope``)
    emits ``RuntimeWarning: invalid value encountered in
    oriented_envelope`` for some perfectly valid polygons — the
    rotated-rectangle RESULT is correct (verified: a 264 k m²
    148-vertex apron piece yields a clean 810 k m² rectangle), but an
    internal GEOS/numpy step trips the invalid/divide floating-point
    flags.  Wrapping the call in ``numpy.errstate`` silences the
    cosmetic warning without changing the result.  Used by every
    ``minimum_rotated_rectangle`` call site across the pavement builder
    so tile generation doesn't spew the warning.

``safe_difference``
    GEOS's overlay can return an **invalid** polygon for two **valid**
    inputs.  Measured at KDFW 2026-08-25 (GEOS 3.13.1 / shapely 2.1.2):
    a 41-vertex junction ``p`` (8 087.9 m², no holes, valid) and a
    60-vertex neighbour ``c`` (85 700.4 m², valid) that share an edge —
    two exact common vertices, disjoint interiors (``p.touches(c)`` is
    True, Monte-Carlo overlap 0 m²) — made ``p.difference(c)`` return a
    polygon whose shell IS ``p``'s exterior plus a spurious 2 952 m²
    "hole" lying entirely OUTSIDE that shell.  Nothing downstream can
    consume that: ``unary_union`` over the layout threw
    ``TopologyException: side location conflict`` at the shared vertex
    and killed the whole KDFW build in
    ``pavement_scoring._reach_zone``.

    The remedy is GEOS's own documented one for overlay robustness
    failures — recompute the OPERATION on a fixed precision grid — not
    a patch-up of the broken output.  ``make_valid`` on that result
    returns 11 040 m² (BIGGER than the 8 088 m² input: it unions the
    stray hole back in) and ``buffer(0)`` returns the parent unclipped;
    the grid retry returns 8 087.9 m², which is the answer Monte-Carlo
    integration confirms (the two shapes do not overlap, so the
    difference is ``p``).
"""
import numpy as np
import shapely
from shapely.errors import GEOSException

__all__ = ["GeomSafeError", "min_rotated_rect", "safe_difference"]


class GeomSafeError(RuntimeError):
    """A shapely/GEOS operation could not be made to yield a VALID
    result on any attempt.

    Raised rather than returning invalid geometry: an invalid polygon
    written into the layout does not fail where it is minted, it fails
    hundreds of passes later inside somebody else's ``unary_union``
    (the KDFW class this module's ``safe_difference`` exists for).
    """


#: Precision grids retried, FINEST FIRST, when GEOS returns an invalid
#: result for valid inputs.  1e-9 m is a nanometre — eleven orders of
#: magnitude below the builder's smallest real tolerance (the 0.05 m
#: touch tolerance), so a successful retry is geometrically identical
#: to the answer GEOS should have given.  The coarser grids exist only
#: so a pathological pair still gets an answer instead of a build
#: failure; 1e-4 m (0.1 mm) is still far below the 1 mm the geometry
#: guard treats as a real vertex move.
_OVERLAY_RETRY_GRIDS = (1e-9, 1e-7, 1e-4)


def min_rotated_rect(geom):
    """Return ``geom.minimum_rotated_rectangle`` without leaking the
    spurious numpy ``oriented_envelope`` floating-point warning."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return geom.minimum_rotated_rectangle


def safe_difference(a, b):
    """``a.difference(b)``, CERTIFIED VALID.

    The plain overlay is tried first and returned untouched whenever it
    is empty or valid — so on every geometry GEOS handles correctly
    (which is all but a handful) this function is
    ``a.difference(b)`` and nothing else.  Only when GEOS returns an
    invalid result (or raises) is the operation recomputed on the
    ``_OVERLAY_RETRY_GRIDS`` precision grids, finest first.

    Raises :class:`GeomSafeError` when no attempt yields a valid
    result — this function never returns invalid geometry, and never
    silently substitutes one of its arguments for the answer.
    """
    first_exc: GEOSException | None = None
    try:
        d = a.difference(b)
        if d.is_empty or d.is_valid:
            return d
    except GEOSException as exc:
        first_exc = exc
    for grid in _OVERLAY_RETRY_GRIDS:
        try:
            r = shapely.set_precision(a, grid).difference(
                shapely.set_precision(b, grid))
        except GEOSException:
            continue
        if r.is_empty or r.is_valid:
            return r
    raise GeomSafeError(
        "difference() yielded no valid result on any precision grid "
        f"{_OVERLAY_RETRY_GRIDS}: a={a.geom_type} area={a.area:.3f} "
        f"bounds={a.bounds} valid={a.is_valid}; b={b.geom_type} "
        f"area={b.area:.3f} bounds={b.bounds} valid={b.is_valid}"
        + (f"; GEOS raised {first_exc!r}" if first_exc is not None else "")
    ) from first_exc
