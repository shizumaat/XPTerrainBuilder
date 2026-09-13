"""The END-AROUND TAXIWAY schema — ``rulesets.toml``'s ``[common.eat]``
and ``[<ruleset>.eat]`` tables (owner RULINGS 2026-09-13j item 2, ruled
13q item 2; spec ``design-surface-spec.md`` §36).  Kept beside
``model.py`` under the 1,000-line file law, exactly as ``basin_schema`` /
``cutout_schema`` are, and re-exported there.  Values live in the TOML;
no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc

from .model_types import CodeTable

__all__ = ["EatSurface", "EatRecognition"]


@_dc.dataclass(frozen=True)
class EatSurface:
    """THE AUTHORITY'S DEPARTURE SURFACE over an END-AROUND TAXIWAY (spec
    §36; v1 ``config.eat_surface_slope_and_setback``).

    ``slope`` is the surface's rise per metre beyond the departure end and
    ``setback_m`` where its inner edge stands; the values and their
    citations live in ``rulesets.toml``.  An authority with NO
    ``[<ruleset>.eat]`` table states no surface at all and the family is a
    no-op there (the ``[icao.drainage]`` precedent)."""

    slope: float
    setback_m: float


@_dc.dataclass(frozen=True)
class EatRecognition:
    """WHICH PAVEMENT IS AN END-AROUND TAXIWAY — the authority-independent
    half of the EAT law (spec §36; v1 ``config`` EAT scoping guards).

    Aircraft geometry (``tail_height_m``) and the rect's own shape are
    facts about the FEATURE, not about the authority, so they live once
    under ``[common.eat]`` and both rulesets read them."""

    #: maximum aircraft TAIL height by code letter (v1 ``TAIL_HEIGHT_BY_CODE_LETTER``)
    tail_height_m: CodeTable
    #: minimum along-centreline distance beyond the end at which the ceiling binds
    min_crossing_m: float
    #: the RECOGNITION cap (owner 2026-08-25d): a wrap beyond this is the
    #: taxi network crossing a projected line, not a loop built for it
    max_crossing_m: float
    #: governed vertices closer than this along ``s`` are ONE crossing
    segment_gap_m: float
    #: a real EAT CROSSES: a rect longer than this along ``s`` runs ALONG
    #: the corridor and is another facility (refused whole)
    rect_max_along_m: float
    #: end-around taxiways exist at transport-category runways only
    min_runway_code_number: int
