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
                     runway_step,
                     runway_end_skirt, runway_transverse, runway_vertical_curve)
from .steps import cross_shape, mid_edge_step, stacked_nodes, vertex_to_edge_step
from .strips import (FAMILY_STRIP_TRANSVERSE, adjacent_ground_step,
                     adjacent_ground_tear, raoa,
                     resa_transverse, strip_arc, strip_longitudinal, strip_seam_tear,
                     strip_transverse)
from .channel import channel_crest_at_edge, channel_floor_at_declaration
from .contiguity import lateral_contiguity
from .eat import eat_ceiling
from .frontage import frontage_near_miss
from .structures import ACCEPTANCE, basin_floor_declaration, wall_in_runway_strip
from .transverse import transverse
from .within import FAMILY_TAXI_BOX, plane_gradient, taxi_box, within_shape

__all__ = ["FAMILIES", "READERS", "NOT_IMPLEMENTED", "RELAXED_KEY", "RELAXED_RULING",
           "YIELDED_KEY", "YIELDED_RULING", "mark_yielded",
           "DEFECT_KEYS", "defect_excess_m", "defect_gate", "under_floor_text",
           "FAMILY_PAD_FLAT", "FAMILY_TRANSVERSE", "FAMILY_VERTICAL_CURVE",
           "FAMILY_STRIP_TRANSVERSE", "FAMILY_TAXI_BOX", "mark_relaxed",
           "census", "census_patch"]

#: family key -> reader (one reader may serve two families: within_shape
#: yields the road cross-section rows beside its own).
READERS: dict[str, _t.Callable[[Patch], list[Row]]] = {
    "plane_gradient": plane_gradient,
    FAMILY_TAXI_BOX: taxi_box,
    "runway_end_skirt": runway_end_skirt,
    "adjacent_ground_tear": adjacent_ground_tear,
    # spec §34 (4): the WITHIN-FACE welded step (lane v2rampwalk)
    "adjacent_ground_step": adjacent_ground_step,
    "strip_seam_tear": strip_seam_tear,
    "transverse": transverse,
    "airside_no_step": lambda p: no_step_direct(p) + no_step_rate(p),
    "strip_longitudinal": strip_longitudinal,
    "strip_arc": strip_arc,
    "resa_transverse": resa_transverse,
    "raoa": raoa,
    "runway_crown": runway_crown,
    # §40 (5) (4) (owner RULINGS 2026-09-15az): the step between two
    # faces of the runway family that the crown reading cannot see
    "runway_step": runway_step,
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
    # spec §45 C14 (owner RULINGS 2026-09-15i): the OPEN CHANNEL's two
    "channel_floor_at_declaration": channel_floor_at_declaration,
    "channel_crest_at_edge": channel_crest_at_edge,
    # spec §36: the pinned end-around-taxiway rect, read back
    "eat_ceiling": eat_ceiling,
}

#: Families in the tables with no v2 reader (vacuous on v2's product or
#: an M3+ family) — listed, never dropped.
NOT_IMPLEMENTED: tuple[str, ...] = (
    # §16g (10) (3)/(6) (owner RULINGS 2026-09-14x / 14ai): both families
    # are the CENSUS's, not the design surface's — one is declared in the
    # sidecar from the pack's clusters (which no emitted patch carries)
    # and the other is a plane residual read off the patch's own rings.
    # ``verify`` reads the DESIGN SURFACE and has no reader for either,
    # so the lockstep twin must not expect one.
    "pad_cluster_mismatch", "pad_airside_weld",
    "terrace_joint_route", "terrace_joint_strip", "terrace_actual_step",
    "drainage_spine", "apron_lattice_membrane", "drainage_minimum",
    # §39 (2) (owner RULINGS 2026-09-13bk/13bt/13bu): the hairline needs the
    # TILE's foreign constrained edges — the OSM water the mesh constrains,
    # published by the emitter as the ``shore_edges`` sidecar key.  A
    # ``Patch`` carries the emitted surface and nothing outside it, so v2
    # verify has no reader for it and the oracle is the only instrument
    # (with the mesh pre-flight, which reads the assembled ``.poly``).
    "hairline_pair",
)


def FAMILIES(law: Law) -> tuple[str, ...]:
    """Every family the tables register, in table order."""
    return tuple(law.tables.families)


#: THE PER-FAMILY VERIFY CLOCK (lane ``v2cost2``, RULINGS 2026-09-14q:
#: "no per-family verify clock exists", so OTHH's 133 s could only be
#: code-attributed).  Seconds per reader of the LAST :func:`census_patch`
#: run, published under the report's ``verify.wall_s``.
WALL_S: dict[str, float] = {}


def census_patch(p: Patch) -> dict[str, list[Row]]:
    import time as _time
    WALL_S.clear()
    out: dict[str, list[Row]] = {k: [] for k in FAMILIES(p.law)}
    t0 = _time.perf_counter()
    within, xsec = within_shape(p)
    WALL_S["within_shape"] = _time.perf_counter() - t0
    out["within_shape"] = within
    out["road_cross_section"] = xsec
    for key, fn in READERS.items():
        t0 = _time.perf_counter()
        out[key] = fn(p)
        WALL_S[key] = _time.perf_counter() - t0
    # the tunnel ACCEPTANCE checks (M4) — not law families, published
    # beside them under their own keys
    for key, fn in ACCEPTANCE.items():
        t0 = _time.perf_counter()
        out[key] = fn(p)
        WALL_S[key] = _time.perf_counter() - t0
    # THE PAD-FLAT CHECK (verify/pads.py): a rigid pad is one flat value,
    # or one plane under 04t(1) — a row here is a DEFECT, never a census
    # residual (RULINGS 03h; lane v2padflat 2026-09-05)
    t0 = _time.perf_counter()
    out[FAMILY_PAD_FLAT] = pad_flat(p)
    WALL_S[FAMILY_PAD_FLAT] = _time.perf_counter() - t0
    return out


#: Keys of ``census_patch`` whose rows are structural DEFECTS of the
#: emitted product, not law residuals: the pipeline reports them apart, the
#: app driver fails the airport.
#:
#: THE GATE READS THE RUNWAY FAMILY ONLY (owner 05s/06b within 08t, RULINGS
#: 2026-09-08v): under the design surface every law is a TARGET the surface
#: aims for and the census REPORTS — except the runway family's, which the
#: solve holds as CONSTRAINTS (``solve/design.py``, ``[design]
#: hard_rulings``).  A row here therefore means the solve's own constraints
#: were not met, which is a defect of the product.  ``pad_flat`` left this
#: tuple with the hard-law world: a rigid pad's flatness is a target of the
#: same solve as every other law, so a pad standing off its plane is a
#: census row like any other (``verify/pads.py`` still reads and reports it).
FAMILY_PAD_FLAT = "pad_flat"
DEFECT_KEYS: tuple[str, ...] = (FAMILY_TRANSVERSE, FAMILY_VERTICAL_CURVE,
                                "runway_step")


def defect_excess_m(r: Row) -> float:
    """THE EXCESS a DEFECT row carries beyond its OWN cap over its OWN span,
    in metres (owner RULINGS 2026-09-14bx).

    Derived from the row's own fields.  A row that states a grade, a cap and
    a distance is read as ``(|grade_pct| - cap_pct) / 100 * distance_m`` --
    for ``runway_transverse`` that is exactly ``magnitude_m - cap_pct/100 *
    distance_m`` (its ``magnitude_m`` is the raw ``|fall|``), and for
    ``runway_vertical_curve`` it is exactly its ``magnitude_m``, which the
    reader already publishes as ``(|change| - bound) * span``.  Reading the
    grades rather than subtracting the cap from ``magnitude_m`` is what makes
    ONE arithmetic right for both families; subtracting twice would put every
    curve row under any floor.

    A family whose rows state no cap/distance pair, or whose span is zero,
    has nothing to price the excess over, so its ``magnitude_m`` IS the
    excess.

    THE TWIN IS THE v1 HARNESS RULE (``tools/check_grade.py``
    ``MATERIALITY_ACCUMULATION_RULE`` / ``row_excess_m``, over the v1 row
    OBJECT — a different shape this layer may not import): same arithmetic,
    same two guards — floored at 0, and never more than the row's whole
    magnitude, because a row can never be more unlawful than its own
    elevation difference.
    """
    mag = abs(float(r.get("magnitude_m") or 0.0))
    g, c, d = r.get("grade_pct"), r.get("cap_pct"), r.get("distance_m")
    if g is None or c is None or d is None or float(d) <= 0.0:
        return mag
    return max(0.0, min(mag, (abs(float(g)) - float(c)) / 100.0 * float(d)))


def defect_gate(law: Law, rows: dict[str, list[Row]]) -> tuple[dict[str, int],
                                                               dict[str, object]]:
    """THE ONE READING OF THE STRUCTURAL-DEFECT GATE (owner RULINGS
    2026-09-14bx) -- the engine's abort and the report's ``defects`` are the
    same dict, computed here and nowhere else.

    Returns ``(defects, under_floor)``:

    * ``defects`` -- family -> count of MATERIAL rows, the rows whose
      :func:`defect_excess_m` is at or over ``law.tables.emit.verify.
      defect_min_excess_m``.  Non-empty means the airport fails by name,
      exactly as before the floor.
    * ``under_floor`` -- family -> ``{"rows": N, "worst_excess_m": X}`` for
      the rows under the floor.  Those rows stay census VIOLATIONS: they are
      untouched in ``rows``, counted in ``by_family``, read by the cockpit.
      They are only excluded from the ABORT, and named in the log.

    On 1.0.339 the +40-004 tile died on one LEMD ``runway_transverse`` row
    with 0.0458 m of excess -- 4.6 cm of fall over 30 m.
    """
    floor = law.tables.emit.verify.defect_min_excess_m
    defects: dict[str, int] = {}
    under: dict[str, object] = {}
    for k in DEFECT_KEYS:
        fam = rows.get(k) or []
        if not fam:
            continue
        small = [defect_excess_m(r) for r in fam if defect_excess_m(r) < floor]
        n_material = len(fam) - len(small)
        if n_material:
            defects[k] = n_material
        if small:
            under[k] = {"rows": len(small),
                        "worst_excess_m": round(max(small), 4),
                        "floor_m": floor}
    return defects, under


def under_floor_text(under: dict[str, object]) -> str:
    """The engine-log sentence naming the rows the floor spared (14bx)."""
    return "; ".join(
        f"{k} under the materiality floor "
        f"({v['rows']} rows, worst {v['worst_excess_m']} m"  # type: ignore[index]
        f" against a floor of {v['floor_m']} m)"  # type: ignore[index]
        for k, v in sorted(under.items()))


#: The key a row carries when it sits on a vertex the last resort relaxed
#: (RULINGS 2026-09-04t(1)); its value names the ruling.
RELAXED_KEY = "relaxed_by"
RELAXED_RULING = "04t(1)"
#: The key a row carries when it sits on a vertex of a YIELDED row (RULINGS
#: 2026-09-08d (2), sidecar ``yielded_rows``); its value names the ruling.
YIELDED_KEY = "yielded_by"
YIELDED_RULING = "08d"


def mark_relaxed(p: Patch, rows: dict[str, list[Row]], *, key: str = "relaxed_rows",
                 tag: str = RELAXED_KEY, ruling: str = RELAXED_RULING) -> dict[str, list[Row]]:
    """THE "relaxed by 04t(1)" HEADING: a row with an endpoint on a vertex
    of a published relaxed row (sidecar ``relaxed_rows``, identity by the
    census's own proximity knob) is a lawful last-resort row, tagged so
    every reader can count it apart from the rest.  In place; returns
    ``rows``.  With ``key = "yielded_rows"`` / ``tag = YIELDED_KEY`` the
    same reading marks the YIELDED rows (RULINGS 2026-09-08d (2))."""
    rel = p.publication.get(key) or []
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
                r[tag] = ruling
    return rows


def mark_yielded(p: Patch, rows: dict[str, list[Row]]) -> dict[str, list[Row]]:
    """THE "yielded (08d)" HEADING: rows on the vertices of a published
    yielded row carry :data:`YIELDED_KEY` (``mark_relaxed`` over the
    ``yielded_rows`` publication)."""
    return mark_relaxed(p, rows, key="yielded_rows", tag=YIELDED_KEY, ruling=YIELDED_RULING)


def census(surface: GradedSurface, law: Law,
           publication: _t.Mapping[str, _t.Any] | None = None,
           law_caps: _t.Mapping[int, float] | None = None,
           lifted_caps: _t.Mapping[int, float] | None = None
           ) -> dict[str, list[Row]]:
    """Rows per family over the emitted product; rows on relaxed vertices
    carry :data:`RELAXED_KEY` (:func:`mark_relaxed`).

    ``law_caps`` is ``constraints.roads.road_law_caps`` — since §37 (1)
    (RULINGS 2026-09-13q item 5) the TRANSVERSE binding of lateral
    contiguity, read through ``Patch.cap_t``; a road's longitudinal cap is
    its role's own.

    ``lifted_caps`` is ``pipeline.publication.lifted_caps`` — §34 (9)'s
    PINCHED RAMP faces, whose within-shape LONGITUDINAL cap is LIFTED
    (owner RULINGS 2026-09-14ak/14am).  Absent, every shape reads exactly
    as before."""
    return census_frame(surface, law, publication, law_caps, lifted_caps)[1]


def census_frame(surface: GradedSurface, law: Law,
                 publication: _t.Mapping[str, _t.Any] | None = None,
                 law_caps: _t.Mapping[int, float] | None = None,
                 lifted_caps: _t.Mapping[int, float] | None = None
                 ) -> tuple[Patch, dict[str, list[Row]]]:
    """:func:`census` WITH THE FRAME IT READ (lane ``v2cost2``).

    ``Patch.of`` is the whole emitted surface re-projected and indexed; the
    pipeline needed a second one only because ``census`` threw this one
    away, and building it (plus the ``road_law_caps`` it takes) ran
    UNCLOCKED after ``wall["verify"]`` — OTHH's 105 unattributed seconds
    (RULINGS 2026-09-14q).  Same rows, same order; the caller reuses ``p``
    for ``apron_over_preference``."""
    p = Patch.of(surface, law, publication, law_caps, lifted_caps)
    return p, mark_yielded(p, mark_relaxed(p, census_patch(p)))
