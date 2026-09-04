"""The v2 census: every family as a pure function over ``GradedSurface``
+ ``Law`` (+ the sidecar publication), rows in the v1 ``row_record``
shape so ``tools/harness/census.py --rows-json`` and this diff by
(family, roles, site).

``FAMILIES`` is derived from ``law/families.toml`` — a family in the
tables with no reader here is reported as ``not_implemented``, never
silently absent (the census-wrapper precedent).  Families v2 has no
geometry for (terraces, basins, walls, lattice, drainage spines) return
no rows and are listed as such in the M2/M3b reports.
"""
from __future__ import annotations

import typing as _t

from ..emit.surface import GradedSurface
from ..law import Law
from .frame import Patch, Row
from .no_step import no_step_direct, no_step_rate
from .runway import runway_crown, runway_end_skirt
from .steps import cross_shape, mid_edge_step, stacked_nodes, vertex_to_edge_step
from .strips import (adjacent_ground_tear, raoa, resa_transverse, strip_arc,
                     strip_longitudinal, strip_seam_tear)
from .contiguity import lateral_contiguity
from .frontage import frontage_near_miss
from .transverse import transverse
from .within import plane_gradient, within_shape

__all__ = ["FAMILIES", "READERS", "NOT_IMPLEMENTED", "census", "census_patch"]

#: family key -> reader (one reader may serve two families: within_shape
#: yields the road cross-section rows beside its own).
READERS: dict[str, _t.Callable[[Patch], list[Row]]] = {
    "plane_gradient": plane_gradient,
    "runway_end_skirt": runway_end_skirt,
    "adjacent_ground_tear": adjacent_ground_tear,
    "strip_seam_tear": strip_seam_tear,
    "transverse": transverse,
    "airside_no_step": lambda p: no_step_direct(p) + no_step_rate(p),
    "strip_longitudinal": strip_longitudinal,
    "strip_arc": strip_arc,
    "resa_transverse": resa_transverse,
    "raoa": raoa,
    "runway_crown": runway_crown,
    "stacked_nodes": stacked_nodes,
    "cross_shape": cross_shape,
    "vertex_to_edge_step": vertex_to_edge_step,
    "mid_edge_step": mid_edge_step,
    "lateral_contiguity": lateral_contiguity,
    "frontage_near_miss": frontage_near_miss,
}

#: Families in the tables with no v2 reader (vacuous on v2's product or
#: an M3+ family) — listed, never dropped.
NOT_IMPLEMENTED: tuple[str, ...] = (
    "terrace_joint_route", "terrace_joint_strip", "terrace_actual_step",
    "basin_floor_declaration", "drainage_spine", "apron_lattice_membrane",
    "drainage_minimum", "wall_in_runway_strip",
)


def FAMILIES(law: Law) -> tuple[str, ...]:
    """Every family the tables register, in table order."""
    return tuple(law.tables.families)


def census_patch(p: Patch) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {k: [] for k in FAMILIES(p.law)}
    within, xsec = within_shape(p)
    out["within_shape"] = within
    out["road_cross_section"] = xsec
    for key, fn in READERS.items():
        out[key] = fn(p)
    return out


def census(surface: GradedSurface, law: Law,
           publication: _t.Mapping[str, _t.Any] | None = None,
           law_caps: _t.Mapping[int, float] | None = None
           ) -> dict[str, list[Row]]:
    """Rows per family over the emitted product."""
    return census_patch(Patch.of(surface, law, publication, law_caps))
