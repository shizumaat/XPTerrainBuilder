"""ONE constraint set from the planar map + the law + the airport (plan
§1 row 5).  Every generator is a pure function ``(planar, law, airport)
-> list[Row]`` whose rows name their generator, ruling and inputs; this
module only lists and stacks them (assembly per kind stays in the
generators — plan §1 "the solver only stacks rows").
"""
from __future__ import annotations

import sys as _sys
import time
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import ConstraintSet, Diff, Linear, Offset, Pin, Row
from ..model.planar import PlanarMap
from . import (apron, ceiling, cluster_pad, eat, flat_site, foot_rows,
               groundside,
               junction_mesh,
               no_step, pad_frontage_gs, pads,
               proximity, road_ramp, roads, routes, runway_chord, runway_profile, seams, strips,
               structures,
               taxi, transverse, water, zones)

__all__ = ["GENERATORS", "generate", "stack", "seam_exempt", "water_exempt"]

Generator = _t.Callable[[PlanarMap, Law, Airport], list[Row]]

#: Every generator in run order — the M2 families (plan §3 M2 row).
GENERATORS: tuple[tuple[str, Generator], ...] = (
    ("runway_profile", runway_profile.runway_profile),
    ("runway_crown", runway_profile.runway_crown),
    ("runway_transverse", runway_profile.runway_transverse),
    ("runway_vertical_curve", runway_profile.runway_vertical_curve),
    ("runway_within_shape", runway_profile.runway_within_shape),
    # THE NEAREST-THRESHOLD CROSSING ANCHOR (owner RULINGS 2026-09-09z (1),
    # spec §17): the crossing node is a hard Pin on the runway that GRADES
    # to it, at the value the governing runway's chord takes there.
    ("runway_crossing_pin", runway_chord.runway_crossing_pins),
    ("taxi_chain", taxi.taxi_chain),
    ("taxi_centerlines", taxi.taxi_centerlines),
    ("triangle_planes", taxi.triangle_planes),
    ("taxi_box", taxi.taxi_box),
    ("junction_mesh", junction_mesh.junction_mesh),
    ("apron_within_shape", apron.apron_within_shape),
    ("apron_edge_portions", apron.apron_edge_portions),
    ("road_within_shape", roads.road_within_shape),
    # §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM
    # (owner RULINGS 2026-09-13j item 5, ruled 13aj; spec §37 (6)): the road
    # target along its ROUTE is ``max(DEM, z_contact - cap * s)`` — a design
    # target at the law weight, with a HARD ceiling a visual threshold above
    # it, superseding the core's soft road fit (``constraints/road_ramp.py``).
    ("road_ramp", road_ramp.road_ramp_rows),
    # §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be): where a
    # road's way leaves the patch coverage the patch takes the CORE
    # ribbon's altitude just outside — the two are one road.
    ("road_coverage_join", road_ramp.road_join_rows),
    ("groundside_ramp", groundside.groundside_ramps),
    ("transverse", transverse.transverse),
    ("no_step_pairs", no_step.no_step_pairs),
    ("no_step_rate", no_step.no_step_rate),
    ("cross_shape_pairs", proximity.cross_shape_pairs),
    ("reach_bands", no_step.reach_bands),
    ("zone_bands", zones.zone_bands),
    ("strip_transverse", zones.strip_transverse),
    ("strip_longitudinal", strips.strip_longitudinal),
    ("strip_arc", strips.strip_arc),
    ("resa_transverse", strips.resa_transverse),
    ("end_corridor_longitudinal", strips.end_corridor_longitudinal),
    ("raoa", strips.raoa),
    ("pad_flats", pads.pad_flats),
    ("pad_frontage_level", pads.pad_frontage_level),
    ("pad_slope_ceiling", pads.pad_slope_ceiling),
    # §30 (4) THE CLUSTER PAD'S APRON REACH (owner RULINGS 2026-09-13bj
    # item 1): the apron within ``[design] cluster_apron_reach_m`` of a
    # TERMINAL CLUSTER's pad takes the pad's plane as its target, at the
    # law's own weight — the caps and the taxi family still win, and the
    # reach never touches a taxiway band's own vertices.
    ("cluster_apron_level", cluster_pad.cluster_apron_level),
    ("frontage_near_miss", pads.frontage_near_miss),
    # §28 THE GROUNDSIDE FRONTAGE TAKES THE PAD'S EDGE LEVEL (owner RULINGS
    # 2026-09-11ai-1 -> 2026-09-12r "grade frontages only"): §20's frontage
    # rule read the other way — the lot / service road follows the pad.
    ("groundside_frontage_level", pad_frontage_gs.groundside_frontage_level),
    # THE END-AROUND TAXIWAY CEILING (owner RULINGS 2026-09-13j item 2,
    # ruled 13q item 2; spec §36): the rect beyond a departure end is PINNED
    # a tail height below the departure surface, and the taxi rows either
    # side ARE the ramp.  Runs after the taxi / apron families whose
    # pavement it governs and before the senior datums it yields to
    # (:func:`eat.withdraw_against_senior`, the post-pass below).
    ("eat_anchor_rect", eat.eat_pins),
    ("water_pins", water.water_pins),
    ("seam_pins", seams.seam_pins),
    ("flat_datum", flat_site.flat_datum),
    # THE FOOT ROWS (owner RULINGS 2026-09-11q; spec §11b): a rigid body
    # on BARE ground takes no pad — its feet take GROUND targets.
    ("foot_rows", foot_rows.foot_rows),
    ("structures", structures.structures),
    ("rim_level", structures.rim_level),
    ("basins", structures.basins),
)


def stack(rows: _t.Iterable[Row]) -> ConstraintSet:
    """Rows by kind, order preserved within kind (``ConstraintSet.from_rows``)."""
    return ConstraintSet.from_rows(rows)


def generate(planar: PlanarMap, law: Law, airport: Airport,
             only: _t.Container[str] | None = None,
             yielded_out: list[Row] | None = None,
             ) -> tuple[ConstraintSet, dict[str, int], dict[str, float]]:
    """Run every generator (or ``only`` those named); return the set,
    the row count per generator and the wall seconds per generator.

    §38 (1) (owner RULINGS 2026-09-13ah): the seam is a ``Pin``, so there
    is no honoured SET and no second pass — the ``seam_honoured``
    parameter and the pipeline's seam-pass loop are deleted."""
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
        # a generator's own statistics (its module's ``STATS[fn name]``):
        # published beside its count as ``<name>.<stat>`` (apron_within_shape:
        # chords_outside_face, RULINGS 2026-09-05ae(1))
        stats = (getattr(_sys.modules.get(fn.__module__), "STATS", None) or {}).get(fn.__name__)
        for k, v in (stats or {}).items():
            counts[f"{name}.{k}"] = int(v)
    # WATER IS A DATUM (owner RULINGS 2026-09-09m (1)): a ground vertex the
    # water pin fixes is no longer an unknown — every OTHER row that would
    # govern it is withdrawn, BEFORE the seam pass (a seam vertex on water
    # takes the water level, not the DEM's).
    rows, n_water = water_exempt(rows)
    counts["water_pin_row_withdrawn"] = n_water
    walls["water_pin_row_withdrawn"] = 0.0
    rows, n_exempt, n_seam_junior = seam_exempt(rows, yielded_out)
    counts["seam_pin_pair_exempt"] = n_exempt
    walls["seam_pin_pair_exempt"] = 0.0
    counts["seam_pin_withdrawn_senior"] = n_seam_junior
    walls["seam_pin_withdrawn_senior"] = 0.0
    # THE SENIOR STRUCTURE'S DATUM (precedence.toml [structures]): a
    # vertex two structures pin keeps one pin (lane v2hecalemd, LEMD)
    rows, n_junior = structures.reconcile_datums(rows, law)
    counts["structure_datum_withdrawn"] = n_junior
    walls["structure_datum_withdrawn"] = 0.0
    # A NODE THAT IS ALREADY HARD IS NEVER OVERRIDDEN (spec §36; v1's own
    # rule): the EAT rect yields to every other pin family and to a rigid
    # group, rather than winning by generator order in the reduction.
    rows, n_eat = eat.withdraw_against_senior(rows)
    counts["eat_pin_withdrawn_senior"] = n_eat
    walls["eat_pin_withdrawn_senior"] = 0.0
    # THE 5 % CEILING (owner RULINGS 2026-09-09b (4)): a POST-PASS over the
    # law set — one hard twin at the ceiling per pavement DIFFERENCE row
    # (``constraints/ceiling.py``), never a second reading of the geometry.
    if only is None or ceiling.GEN in only:
        t0 = time.perf_counter()
        caps = ceiling.pavement_ceiling(rows, planar, law)
        walls[ceiling.GEN] = time.perf_counter() - t0
        counts[ceiling.GEN] = len(caps)
        rows.extend(caps)
    return stack(rows), counts, walls


def water_exempt(rows: list[Row]) -> tuple[list[Row], int]:
    """THE WATER PIN IS THE VERTEX'S OWN LAW (owner RULINGS 2026-09-09m
    (1); ``constraints/water.py``).

    A ground vertex the water pin fixes "is not an unknown of the sheet",
    so every OTHER row that would GOVERN it is withdrawn:

    * a second ``Pin`` on it (a declared datum) — two equalities on one
      vertex is a contradiction, and water outranks;
    * a one-way row whose governed vertex (``follows``) is pinned — a
      zone band cannot fight the datum it stands in;
    * any row ALL of whose vertices are pinned — it prices water against
      water (the seam-pin precedent, :func:`seam_exempt`).

    A row with ONE pinned vertex and one free one STAYS: that is the
    shoreline, and the shore is a BANK (09m (2)) — the next round's, and
    reported meanwhile, never silently dropped.

    Returns the rows and the number withdrawn.
    """
    pinned = water.water_vertices_pinned(rows)
    if not pinned:
        return rows, 0
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Pin):
            if r.source.generator == water.GEN or r.v not in pinned:
                out.append(r)
            else:
                n += 1
            continue
        follows = getattr(r, "follows", None)
        if isinstance(follows, tuple):
            # a one-way row over a SET of followers (the pad plane's three
            # degrees of freedom, owner RULINGS 2026-09-10y) governs nothing
            # once EVERY follower is pinned
            follows = follows[0] if len(follows) == 1 else (
                next(iter(follows)) if all(v in pinned for v in follows) else None)
        if follows is not None and follows in pinned:
            n += 1
            continue
        if isinstance(r, Linear) and all(v in pinned for v, _c in r.terms):
            n += 1
            continue
        if isinstance(r, (Diff, Offset)) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        out.append(r)
    return out, n


def seam_exempt(rows: list[Row], yielded_out: list[Row] | None = None
                ) -> tuple[list[Row], int, int]:
    """THE SEAM-PIN PAIR EXEMPTION (user 2026-07-04, the census's own
    reading — ``check_grade`` with sidecar ``seam_pins``: "pin↔pin pairs
    skip, pin↔free pairs check at the body cap"): a grade row whose every
    vertex is a seam DEM pin prices terrain against terrain and is
    dropped; a row with one free vertex stays.

    AND THE SENIOR-DATUM WITHDRAWAL (§38 (1); ``constraints/seams.py``
    docstring): the seam pin is a ``Pin`` since 13ah, so a vertex another
    generator ALSO pins would carry two equalities and the reduction's
    row order would decide which one holds.  A CIFP threshold outranks the
    seam (the runway's own regulation value), so the SEAM pin is the one
    withdrawn there — counted, never silent.  (Water is senior to both and
    is settled earlier, in :func:`water_exempt`.)

    AND THE ZONE BAND YIELDS BETWEEN TWO PINS (§38 (2); owner RULINGS
    2026-09-13ah, attributed 13am (6)).  A ONE-WAY row (``follows``) whose
    GOVERNED vertex is a seam pin governs a vertex that has no column: the
    row survives only as a two-way PULL on the pavement it was written to
    follow, which ``one_way_rulings`` exists to forbid ("the adjacent
    ground follows the pavement and never pulls it", 09-09b (2)/(3)).
    Measured at SPLP that pull is exactly what held the seam off its DEM —
    the relax arm ``zone_bands −1,670 rows → z−dem after −0.000`` — and
    with the seam pinned it re-appears as a 2.39 m zone miss and an
    INFEASIBLE runway projection.  So the row YIELDS, on the same clause
    ``water_exempt`` already applies to a water datum ("a zone band cannot
    fight the datum it stands in").  Each yielded row is handed back
    through ``yielded_out`` so the design report can NAME the family, its
    two pins and the demanded-vs-allowed metres (§38 (2), never a silent
    residual).

    Returns the rows, the number of PAIRS dropped and the number of seam
    PINS withdrawn against a senior pin."""
    pinned = seams.seam_vertices_pinned(rows)
    if not pinned:
        return rows, 0, 0
    senior = {r.v for r in rows
              if isinstance(r, Pin) and r.source.generator != seams.GEN}
    n_junior = 0
    if senior & pinned:
        keep: list[Row] = []
        for r in rows:
            if (isinstance(r, Pin) and r.source.generator == seams.GEN
                    and r.v in senior):
                n_junior += 1
                continue
            keep.append(r)
        rows = keep
        pinned = pinned - senior
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Pin):
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
        # §38 (2) THE ZONE BAND YIELDS: a one-way row whose GOVERNED vertex
        # is a seam pin (the ``water_exempt`` clause, applied to the seam)
        fv = getattr(r, "follows", None)
        fvs = ((int(fv),) if isinstance(fv, int)
               else tuple(int(q) for q in fv) if fv is not None else ())
        if fvs and all(q in pinned for q in fvs):
            if yielded_out is not None:
                yielded_out.append(r)
            n += 1
            continue
        out.append(r)
    return out, n, n_junior
