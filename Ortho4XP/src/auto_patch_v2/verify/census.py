"""The v2 census: every family as a pure function over ``GradedSurface``
+ ``Law`` (+ the sidecar publication), rows in the v1 ``row_record``
shape so ``tools/harness/census.py --rows-json`` and this diff by
(family, roles, site).

``FAMILIES`` is derived from ``law/families.toml`` — a family in the
tables with no reader here is reported as ``not_implemented``, never
silently absent (the census-wrapper precedent).  Families v2 has no
geometry for (terraces, lattice, drainage spines; basins read the sidecar, M4b) return
no rows and are listed as such in the M2/M3b reports.
"""
from __future__ import annotations

import typing as _t

from ..emit.surface import GradedSurface
from ..law import Law
from .frame import Patch, Row
from .no_step import no_step_direct, no_step_rate
from .pads import pad_flat
from .runway import (FAMILY_TRANSVERSE, FAMILY_VERTICAL_CURVE, runway_crown,
                     runway_end_skirt, runway_transverse, runway_vertical_curve)
from .steps import cross_shape, mid_edge_step, stacked_nodes, vertex_to_edge_step
from .strips import (FAMILY_STRIP_TRANSVERSE, adjacent_ground_tear, raoa,
                     resa_transverse, strip_arc, strip_longitudinal, strip_seam_tear,
                     strip_transverse)
from .contiguity import lateral_contiguity
from .frontage import frontage_near_miss
from .structures import ACCEPTANCE, basin_floor_declaration, wall_in_runway_strip
from .transverse import transverse
from .within import FAMILY_TAXI_BOX, plane_gradient, taxi_box, within_shape

__all__ = ["FAMILIES", "READERS", "NOT_IMPLEMENTED", "RELAXED_KEY", "RELAXED_RULING",
           "DEFECT_KEYS", "FAMILY_PAD_FLAT", "FAMILY_TRANSVERSE", "FAMILY_VERTICAL_CURVE",
           "FAMILY_STRIP_TRANSVERSE", "FAMILY_TAXI_BOX", "mark_relaxed",
           "census", "census_patch"]

#: family key -> reader (one reader may serve two families: within_shape
#: yields the road cross-section rows beside its own).
READERS: dict[str, _t.Callable[[Patch], list[Row]]] = {
    "plane_gradient": plane_gradient,
    FAMILY_TAXI_BOX: taxi_box,
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
    FAMILY_TRANSVERSE: runway_transverse,
    FAMILY_VERTICAL_CURVE: runway_vertical_curve,
    FAMILY_STRIP_TRANSVERSE: strip_transverse,
    "stacked_nodes": stacked_nodes,
    "cross_shape": cross_shape,
    "vertex_to_edge_step": vertex_to_edge_step,
    "mid_edge_step": mid_edge_step,
    "lateral_contiguity": lateral_contiguity,
    "frontage_near_miss": frontage_near_miss,
    "wall_in_runway_strip": wall_in_runway_strip,
    "basin_floor_declaration": basin_floor_declaration,
}

#: Families in the tables with no v2 reader (vacuous on v2's product or
#: an M3+ family) — listed, never dropped.
NOT_IMPLEMENTED: tuple[str, ...] = (
    "terrace_joint_route", "terrace_joint_strip", "terrace_actual_step",
    "drainage_spine", "apron_lattice_membrane", "drainage_minimum",
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
    # the tunnel ACCEPTANCE checks (M4) — not law families, published
    # beside them under their own keys
    for key, fn in ACCEPTANCE.items():
        out[key] = fn(p)
    # THE PAD-FLAT CHECK (verify/pads.py): a rigid pad is one flat value,
    # or one plane under 04t(1) — a row here is a DEFECT, never a census
    # residual (RULINGS 03h; lane v2padflat 2026-09-05)
    out[FAMILY_PAD_FLAT] = pad_flat(p)
    return out


#: Keys of ``census_patch`` whose rows are structural DEFECTS of the
#: emitted product (a solver / emit invariant broken), not law residuals:
#: the pipeline reports them apart, the app driver fails the airport.
#: ``runway_transverse`` (RULINGS 2026-09-05o): the runway transverse
#: maximum is a hard tier-0 row, so a built cross-fall over it is a defect;
#: ``runway_vertical_curve`` (2026-09-06b law 1) likewise.  The strip tie
#: (``strip_transverse``) sits in the strip's tier — the last resort may
#: relax it — so its rows are residuals, never defects.
FAMILY_PAD_FLAT = "pad_flat"
DEFECT_KEYS: tuple[str, ...] = (FAMILY_PAD_FLAT, FAMILY_TRANSVERSE, FAMILY_VERTICAL_CURVE)


#: The key a row carries when it sits on a vertex the last resort relaxed
#: (RULINGS 2026-09-04t(1)); its value names the ruling.
RELAXED_KEY = "relaxed_by"
RELAXED_RULING = "04t(1)"


def mark_relaxed(p: Patch, rows: dict[str, list[Row]]) -> dict[str, list[Row]]:
    """THE "relaxed by 04t(1)" HEADING: a row with an endpoint on a vertex
    of a published relaxed row (sidecar ``relaxed_rows``, identity by the
    census's own proximity knob) is a lawful last-resort row, tagged so
    every reader can count it apart from the rest.  In place; returns
    ``rows``."""
    rel = p.publication.get("relaxed_rows") or []
    if not rel:
        return rows
    pts = [p.to_m(float(la), float(lo)) for r in rel for la, lo in r.get("ll", [])]
    if not pts:
        return rows
    tol = p.law.tables.emit.identity.min_distinct_spacing_m
    cells: set[tuple[int, int]] = set()
    for x, y in pts:
        cells.add((round(x / tol), round(y / tol)))

    def near(xy) -> bool:
        cx, cy = round(xy[0] / tol), round(xy[1] / tol)
        return any((cx + dx, cy + dy) in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    for lst in rows.values():
        for r in lst:
            site = r.get("site_m")
            if site and any(near(pt) for pt in site):
                r[RELAXED_KEY] = RELAXED_RULING
    return rows


def census(surface: GradedSurface, law: Law,
           publication: _t.Mapping[str, _t.Any] | None = None,
           law_caps: _t.Mapping[int, float] | None = None
           ) -> dict[str, list[Row]]:
    """Rows per family over the emitted product; rows on relaxed vertices
    carry :data:`RELAXED_KEY` (:func:`mark_relaxed`)."""
    p = Patch.of(surface, law, publication, law_caps)
    return mark_relaxed(p, census_patch(p))
