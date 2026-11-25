"""A RING THAT WRAPS THE RUNWAY IS ITS SHOULDER ONLY WHERE IT IS NARROW
(owner RULINGS 2026-09-14ba, LERM; owner 2026-11-25 #2281, EKVG).

14ba: a cell sharing more than ``corridor.runway_shoulder_max_wrap`` of
the runway ring ENCLOSES the runway — the ground the strip sits in, not a
shoulder (LERM: a 65,655 m2 cell at 30.7 m mean depth took the runway's
datum while its ground fell 7.5 %, 43 ``runway_transverse`` DEFECT rows).
#2281: "narrow pavement around a runway must become runway SHOULDER"
(EKVG: Faroes4XPlane paints ``dsf:pol33`` round the slab at 4-7 m mean
depth).

Once a hole's only tie is spurred (``classify/island_spurs``) and a taxiway
entrance carved out of the ring (``apt_shoulder.taxiway_entrances``), a
wrapping ring reaches the shoulder test as PIECES, each under the wrap cap;
the cap alone no longer sees the ring.  So the wrap is read on the RING —
the part of the slice region an island spur cut (the caller passes it as
``page``; nowhere else is it read, so a face the spur never split keeps
14ba exactly) — and a piece of a wrapping ring is the runway's shoulder
only when its mean
depth off the runway edge is at most the runway's HALF WIDTH — narrower
than half the slab it borders, the shape of a shoulder (LERM 30.7 m
against 22.5 m: refused; EKVG 4.7 / 7.1 m against 15 m: admitted).

Nothing here names an airport; build-time impact: one boundary clip per
shoulder candidate.
"""
from __future__ import annotations

__all__ = ["wide_on_wrapping_page"]


def wide_on_wrapping_page(face, page, rw, shared_m: float, rw_edges,
                          max_wrap: float, tol: float) -> bool:
    """True when ``face`` (a §40 (1) shoulder candidate of runway ``rw``
    sharing ``shared_m`` with its ring) lies on a ``page`` that wraps the
    runway — covers or borders, within ``tol``, more than ``max_wrap`` of
    its ring — and is deeper than the runway's half width (module doc)."""
    if page is None or max_wrap <= 0.0 or shared_m <= 0.0:
        return False
    for r, poly, _band in rw_edges:
        if r is not rw:
            continue
        # the ring the page COVERS or borders: a page painted over the slab
        # has no hole there, so its boundary never runs along the ring
        ring = poly.exterior
        if ring.length <= 0.0 or ring.intersection(page.buffer(tol)).length \
                <= max_wrap * ring.length:
            return False
        return face.area / shared_m > 0.5 * float(rw.width_m)
    return False
