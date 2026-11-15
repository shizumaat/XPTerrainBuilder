"""``structures.toml [agp]`` — AN ``.agp`` GROUP SEATS ON ONE DATUM
(#2090; spec ``docs/specs/2090-agp-group-groundside-spec.md`` C1 V3).

The numbers ``airport/agp_ground`` (the connector floors, the join, the
lift), ``airport/agp_group`` (the record, the provisional governor) and
``constraints/agp_level`` (the datum rewrite) read.  Defaulted so a law
dir without the table still loads — the ``[walled_plate]`` precedent.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["AgpLaw"]


@_dc.dataclass(frozen=True)
class AgpLaw:
    """The AGP group's law (spec C1)."""

    #: a floor this high over its group's ground line is a connector
    #: floor (m): headroom over a road or an apron
    connector_floor_m: float = 2.5
    #: two connector-floor vertices this close in plan meet (m)
    contact_m: float = 1.5
    #: a lift smaller than this writes nothing (the pavement visibility bar)
    lift_tol_m: float = 0.05
    #: a face is a floor when its normal's vertical share is at least this
    flat: float = 0.9
    #: the join's vote bins the datum step at this resolution (m)
    step_bin_m: float = 0.05
    #: V2: a join of ONE level pair stands only when its step is within
    #: this of zero (m); a non-zero step needs two distinct pairs
    flat_step_tol_m: float = 0.10
    #: A2: the provisional governor's ground point stands within this of
    #: the apt.dat airside pavement (m), every other member twice as far
    airside_reach_m: float = 60.0
    #: G2: the stage-2 datum moves the predicted rows by at most this (m)
    datum_slack_m: float = 1.0
    #: B1: a deck end joins a floor within this of its predicted top (m)
    deck_join_reach_m: float = 3.0
    #: B1: the next floor's offset is at least this larger (m)
    deck_join_margin_m: float = 1.0
    #: C1: a ground-floor plate's floors stand within this of the datum (m)
    ground_band_m: float = 0.6
    #: C1: a plate part smaller than this is not built (m²)
    floor_min_area_m2: float = 100.0
    #: C1: a plate whose median level stands further than this from the
    #: DEM is not built (m)
    plate_max_off_m: float = 3.0
