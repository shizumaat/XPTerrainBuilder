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
from ..model.constraints import ConstraintSet, Diff, Linear, Offset, Row
from ..model.planar import PlanarMap
from . import (apron, no_step, pads, roads, runway_profile, seams, strips,
               structures, taxi, transverse, zones)

__all__ = ["GENERATORS", "generate", "stack", "seam_exempt"]

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
    ("frontage_near_miss", pads.frontage_near_miss),
    ("seam_pins", seams.seam_pins),
    ("structures", structures.structures),
    ("basins", structures.basins),
)


def stack(rows: _t.Iterable[Row]) -> ConstraintSet:
    """Rows by kind, order preserved within kind (``ConstraintSet.from_rows``)."""
    return ConstraintSet.from_rows(rows)


def generate(planar: PlanarMap, law: Law, airport: Airport,
             only: _t.Container[str] | None = None,
             seam_honoured: _t.Container[int] | None = None
             ) -> tuple[ConstraintSet, dict[str, int], dict[str, float]]:
    """Run every generator (or ``only`` those named); return the set,
    the row count per generator and the wall seconds per generator.
    ``seam_honoured``: the seam vertices whose DEM value the solve could
    honour (the pipeline's second pass) — only pairs among THOSE are
    exempt; ``None`` exempts pairs among every seam candidate."""
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
    rows, n_exempt = seam_exempt(rows, seam_honoured)
    counts["seam_pin_pair_exempt"] = n_exempt
    walls["seam_pin_pair_exempt"] = 0.0
    return stack(rows), counts, walls


def seam_exempt(rows: list[Row], honoured: _t.Container[int] | None = None
                ) -> tuple[list[Row], int]:
    """THE SEAM-PIN PAIR EXEMPTION (user 2026-07-04, the census's own
    reading — ``check_grade`` with sidecar ``seam_pins``: "pin↔pin pairs
    skip, pin↔free pairs check at the body cap"): a grade row whose every
    vertex is a seam DEM pin prices terrain against terrain and is
    dropped; a row with one free vertex stays.  Returns the rows and the
    number dropped."""
    pinned = seams.seam_vertices_pinned(rows)
    if honoured is not None:
        pinned = {v for v in pinned if v in honoured}
    if not pinned:
        return rows, 0
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Linear) and r.source.generator == seams.GEN:
            out.append(r)
            continue
        if isinstance(r, Diff) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        if isinstance(r, Linear) and all(v in pinned for v, _c in r.terms):
            n += 1
            continue
        if isinstance(r, Offset) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        out.append(r)
    return out, n
