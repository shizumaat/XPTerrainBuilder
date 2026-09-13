"""§38 (3) NO BANK ALONG A TILE SEAM — the band as ONE region.

Lives beside ``emit/bank.py`` rather than in it because that module is AT
the 1,000-line cap (``tests/auto_patch_v2/test_model.py``).
"""
from __future__ import annotations

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["seam_band_region"]


def seam_band_region(planar: PlanarMap, law: Law, cov=None):
    """§38 (3) NO BANK ALONG A SEAM (owner RULINGS 2026-09-13ah).

    The tile-seam bands as ONE region in the frame, taken from the map's
    own record (``PlanarMap.seam_band_rings``, written by ``planar/build``
    from ``planar/overlay.seam_bands`` — the SINGLE derivation; this module
    never re-derives the graticule).  ``None`` on a single-tile airport,
    where every reader below is a no-op and the emitted bank is byte-for-
    byte what it was.

    Two things are done with it, and they are NOT the same cut:

    * the derived bank PIECES are cut by it — "the coverage edge at a tile
      seam is a pin line already at the DEM, so the transition there is
      zero by construction" and no bank is DERIVED there;
    * the band is UNIONED into the coverage before the min-width collar,
      so the 10 m slit between the two tile pieces is closed EXPLICITLY.
      It was closed only by ``bank_min_width_m`` (5.0, emit.toml:445)
      happening to equal ``seam.half_width_m`` (5.0, emit.toml:86) — two
      independently typed constants; change either and a 1:3 foot ring
      appears down the middle of the runway (13am (2)).  The twin
      ``test_v2bank.py::test_the_seam_slit_needs_no_constant_coincidence``
      moves one constant and reads no ring.

    They are not interchangeable: differencing the band out of the FINAL
    banked region would re-open the slit it exists to close (the band spans
    the whole coverage plus a margin), so the cut lands on the pieces.

    THE BAND IS CLIPPED TO THE SLIT (measured, arm ``v2seampin-p3``): the
    overlay's bands run the full coverage extent plus a margin, so unioning
    one whole into the coverage extended the coverage a kilometre down the
    meridian and the collar followed it (foot distance mean 5.6 -> 302.9 m,
    max 1042 m, 116 -> 326 foot nodes).  Only the part of the band the
    coverage stands beside is the slit, so it is intersected with the
    coverage grown by its OWN half width — ``law.emit.seam.half_width_m``,
    the band's own constant, never ``bank_min_width_m``.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rings = getattr(planar, "seam_band_rings", ())
    polys = []
    for ring in rings:
        if len(ring) < 4:
            continue
        p = Polygon(ring)
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    g = unary_union(polys)
    if g.is_empty:
        return None
    if cov is not None:
        half = float(law.tables.emit.seam.half_width_m)
        try:
            g = g.intersection(cov.buffer(half + 0.5))
        except Exception:                               # pragma: no cover
            return None
        if g.is_empty:
            return None
    return g
