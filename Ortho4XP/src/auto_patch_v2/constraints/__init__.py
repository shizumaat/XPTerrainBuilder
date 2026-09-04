"""ONE constraint set from the planar map + the law + the airport (plan
§1 row 5).  Every generator is a pure function ``(planar, law, airport)
-> list[Row]`` whose rows name their generator, ruling and inputs; this
module only lists and stacks them (assembly per kind stays in the
generators — plan §1 "the solver only stacks rows").
"""
from __future__ import annotations

import time
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import ConstraintSet, Row
from ..model.planar import PlanarMap
from . import (apron, no_step, pads, roads, runway_profile, seams, strips,
               taxi, transverse, zones)

__all__ = ["GENERATORS", "generate", "stack"]

Generator = _t.Callable[[PlanarMap, Law, Airport], list[Row]]

#: Every generator in run order — the M2 families (plan §3 M2 row).
GENERATORS: tuple[tuple[str, Generator], ...] = (
    ("runway_profile", runway_profile.runway_profile),
    ("runway_crown", runway_profile.runway_crown),
    ("runway_within_shape", runway_profile.runway_within_shape),
    ("taxi_within_shape", taxi.taxi_within_shape),
    ("taxi_centerlines", taxi.taxi_centerlines),
    ("triangle_planes", taxi.triangle_planes),
    ("apron_within_shape", apron.apron_within_shape),
    ("road_within_shape", roads.road_within_shape),
    ("transverse", transverse.transverse),
    ("no_step_pairs", no_step.no_step_pairs),
    ("no_step_rate", no_step.no_step_rate),
    ("zone_bands", zones.zone_bands),
    ("strip_longitudinal", strips.strip_longitudinal),
    ("strip_arc", strips.strip_arc),
    ("resa_transverse", strips.resa_transverse),
    ("end_corridor_longitudinal", strips.end_corridor_longitudinal),
    ("raoa", strips.raoa),
    ("pad_flats", pads.pad_flats),
    ("seam_pins", seams.seam_pins),
)


def stack(rows: _t.Iterable[Row]) -> ConstraintSet:
    """Rows by kind, order preserved within kind (``ConstraintSet.from_rows``)."""
    return ConstraintSet.from_rows(rows)


def generate(planar: PlanarMap, law: Law, airport: Airport,
             only: _t.Container[str] | None = None
             ) -> tuple[ConstraintSet, dict[str, int], dict[str, float]]:
    """Run every generator (or ``only`` those named); return the set,
    the row count per generator and the wall seconds per generator."""
    rows: list[Row] = []
    counts: dict[str, int] = {}
    walls: dict[str, float] = {}
    for name, fn in GENERATORS:
        if only is not None and name not in only:
            continue
        t0 = time.perf_counter()
        got = fn(planar, law, airport)
        walls[name] = time.perf_counter() - t0
        counts[name] = len(got)
        rows.extend(got)
    return stack(rows), counts, walls
