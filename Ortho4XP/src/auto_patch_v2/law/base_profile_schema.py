"""``structures.toml [base_profile]`` — THE BUILDING BASE PROFILE
(``docs/specs/building-base-profile-spec.md`` §1; owner RULINGS
2026-10-01f and the 10-01k answers to its §8).

The owner's design order, verbatim (10-01f): *"detect building's base
shape and orientation (e.g. a building that has steps where part of it
is at one level and another part is at a higher level, and create two
pads with a cliff to match them)"*.

The four numbers the READ needs and nothing else.  Every other value the
derivation uses is an EXISTING law key read at its own site — the plane's
area floor is ``[building_pad] min_area_m2``, the bin merge and the
sloped rms are ``[placement] split_tol_m``, the roof band is ``[basin]
contact_band_m``, the riser weld floor is ``[terrace]
pad_terrace_floor_m``, the flat ceiling is
``emit.within_shape.pad_slope_max`` and the trim and riser reach are
``[seam] pad_frontage_m`` / ``emit.identity.min_distinct_spacing_m``.
A second copy of any of those here would be the census-wrapper defect
(RULINGS 2026-08-30l) in the law file.

Defaulted so a law dir without the table still loads — the ``[deck]`` /
``[scatter]`` precedent.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["BaseProfileLaw"]


@_dc.dataclass(frozen=True)
class BaseProfileLaw:
    """§1 (1)/(2): what makes a face HORIZONTAL, what makes a plane a
    ROOF rather than a base, and the window a SLOPED base is read in."""

    #: §1 (1): ``|n_y|`` at or above this is a HORIZONTAL FACE.  0.95 is
    #: an 18° cone about vertical — measured on the KASE pack, where it
    #: separates ``FireStation_7``'s lot sheets (|ny| 1.000) from its
    #: 17 % bank sheets (|ny| 0.986 … and the cut-slope faces below
    #: 0.95), and the shelter roof's plates from its column walls.
    #: 0 disarms the read (every plane reads FLAT / FEET).
    horizontal_ny: float = 0.95
    #: §1 (1) THE ROOF TEST: the solid vertices of the composed UNIT
    #: lying ``[basin] contact_band_m`` or more BELOW a plane, strictly
    #: inside its polygon, are DISTRIBUTED under it when their convex
    #: hull covers at least this fraction of the polygon.  Such a plane
    #: is a ROOF / DECK / MEZZANINE and never a base.  Measured on the
    #: KASE pack: ``Shelters.OBJ``'s roof reads 156 % (5,954 column feet
    #: under 6,149 m² of roof) and ``FireStation_7``'s +3.9 lot reads
    #: 0.2 % (157 vertices at one garage threshold under 6,394 m²) — two
    #: orders of magnitude either side of 0.25.
    roof_support_fraction: float = 0.25
    #: §1 (2) SLOPED: a member with no base plane over the area floor
    #: still has a sloped base when its contact set spans at least this
    #: (metres, the larger plan extent).  Below it the member is FEET —
    #: a column-only shelter, not a ramp.
    sloped_min_extent_m: float = 20.0
    #: §1 (2) + 10-01k Q5: THE HARD CEILING on a sloped base's own
    #: gradient (m/m).  The owner ruled the pad carries the object's own
    #: base gradient with no 1.5 % clamp; this is the ceiling past which
    #: the geometry is not a base at all but RISER geometry (§1 (2): the
    #: KASE cut-slope staircase reads 17 %).
    sloped_max: float = 0.08
