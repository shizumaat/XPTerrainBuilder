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
from ..model.constraints import ConstraintSet, Row
from ..model.planar import PlanarMap
from . import (apron, cluster_pad, eat, flat_site, foot_rows,
               groundside, hard_plane, door_pad,
               junction_mesh,
               no_step, pad_frontage_gs, pad_fronting, pads,
               platform,
               proximity, ramp_runout, road_ramp, roads, routes, runway_chord, runway_mean_slope,
               runway_profile, runway_step,
               seams, strips,
               channel,
               structures,
               taxi, transverse, water, zones)
from .assembly import assemble, seam_exempt, water_exempt

__all__ = ["GENERATORS", "generate", "run_generator", "post_passes", "stack", "seam_exempt",
           "water_exempt"]

Generator = _t.Callable[[PlanarMap, Law, Airport], list[Row]]

#: Every generator in run order — the M2 families (plan §3 M2 row).
GENERATORS: tuple[tuple[str, Generator], ...] = (
    ("runway_profile", runway_profile.runway_profile),
    ("runway_crown", runway_profile.runway_crown),
    ("runway_transverse", runway_profile.runway_transverse),
    ("runway_vertical_curve", runway_profile.runway_vertical_curve),
    # §40 (5) (4): no step between two faces of the runway family — the
    # hard rows behind the ``runway_step`` DEFECT family
    ("runway_step", runway_step.runway_step_rows),
    # THE MEAN RUNWAY SLOPE (Annex 14 §3.1.13; audit §4 M1, RULINGS
    # 2026-10-15l (1)): all-pairs rows over each runway's ridge stations
    ("runway_mean_slope", runway_mean_slope.runway_mean_slope),
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
    # §42 (1b) (owner RULINGS 2026-09-27a (5)): a hard ground plane is ONE
    # level (a Flat), its level the runway-edge frontage's
    ("hard_plane_level", hard_plane.hard_plane_level),
    # owner 2026-10-20 (#798): a sloping building's pad welded into the
    # apron is ONE level; the door line keeps the apron cap
    ("door_pad_level", door_pad.door_pad_level),
    ("apron_edge_portions", apron.apron_edge_portions),
    ("road_within_shape", roads.road_within_shape),
    # §37 (6) A GROUNDSIDE ROAD IS A RAMP FROM ITS AIRSIDE CONTACT TO THE DEM
    # (owner RULINGS 2026-09-13j item 5, ruled 13aj; spec §37 (6)): the road
    # target along its ROUTE is ``max(DEM, z_contact - cap * s)`` — a design
    # target at the law weight, with a HARD ceiling a visual threshold above
    # it, superseding the core's soft road fit (``constraints/road_ramp.py``).
    ("road_ramp", road_ramp.road_ramp_rows),
    # §37 (10) (1) THE AIRSIDE CONTACT SET INCLUDES TAXIWAYS (owner RULINGS
    # 2026-09-13cs item 5): a road that ENDS within ``[road_contact]
    # contact_reach_m`` of an airside face's edge without touching it takes
    # a ONE-WAY ceiling at that edge's own solved level plus its own cap
    # along the route — HECA ``route0``'s 33 % cliff over 4.4 m.
    ("road_contact", road_ramp.road_contact_rows),
    # §37 (9) THE COVERAGE-EDGE JOIN (owner RULINGS 2026-09-13be): where a
    # road's way leaves the patch coverage the patch takes the CORE
    # ribbon's altitude just outside — the two are one road.
    ("road_coverage_join", road_ramp.road_join_rows),
    # OWNER RULINGS 2026-10-03c (#291): the lot at a placed wall's foot is
    # flat to its building's pad (one-way, stage 2); the wall is the step
    ("wall_terrace", road_ramp.wall_terrace_rows),
    ("groundside_ramp", groundside.groundside_ramps),
    ("transverse", transverse.transverse),
    # §34 (13) (3) (Fable 2026-09-15; RULINGS 2026-09-15y): the RAW PAIR
    # across a junction's width — the reading the census and the cockpit
    # use, which a satisfied 4-term cross-corridor row does not discharge
    ("junction_raw_transverse", transverse.junction_raw_transverse),
    ("no_step_pairs", no_step.no_step_pairs),
    ("no_step_rate", no_step.no_step_rate),
    ("cross_shape_pairs", proximity.cross_shape_pairs),
    # owner RULINGS 2026-10-19an (#328): two airside pavements within the
    # weld spacing across a non-pavement gap are one surface
    ("airside_sliver_pairs", proximity.airside_sliver_pairs),
    ("reach_bands", no_step.reach_bands),
    ("zone_bands", zones.zone_bands),
    ("strip_transverse", zones.strip_transverse),
    ("strip_longitudinal", strips.strip_longitudinal),
    ("strip_arc", strips.strip_arc),
    ("resa_transverse", strips.resa_transverse),
    ("end_corridor_longitudinal", strips.end_corridor_longitudinal),
    ("end_corridor_rate", strips.end_corridor_rate),
    ("raoa", strips.raoa),
    ("pad_flats", pads.pad_flats),
    ("pad_frontage_level", pads.pad_frontage_level),
    ("pad_fronting_level", pad_fronting.pad_fronting_level),
    ("pad_slope_ceiling", pads.pad_slope_ceiling),
    # unit-platform spec §1 (3) / §3 P3 (RULINGS 2026-09-28a (1)): the
    # COLLAR between a platform and its welded rim is a 1:3 bank
    ("platform_collar", platform.platform_collar_rows),
    # spec §56 (3): the inter-block terrace strip's own rows (``#strip``)
    ("block_strip", platform.block_strip_rows),
    ("platform_plane", platform.platform_plane_rows),
    # owner RULINGS 2026-10-03e (#290): a viaduct's ramp LANDING held at
    # its block's datum + the deck's y — a stage-2 row
    ("landing_level", platform.landing_rows),
    # issue #711 (RULINGS 2026-10-14c (5) at a landing): the RUN-OUT off
    # a ramp foot on a landing, at road grade from the landing's level
    ("landing_runout", ramp_runout.landing_runout_rows),
    # SPEC-AUTHOR RULINGS 2026-09-29s (A) (#96): the plane is CONTACT-LED —
    # one one-way level row per welded collar contact, at the plane there
    ("platform_level", platform.platform_level_rows),
    # flat-pad spec §1 (2) (RULINGS 2026-09-30f/r, #111): a HELD block's
    # welded frontage at its flat datum, a stage-1 row
    ("frontage_hold", platform.frontage_hold_rows),
    # §30 (4)'s apron reach / collar generators: DELETED (jetway-strip
    # spec §6 Q3) — the JETWAY STRIP projection is their successor.
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
    # THE OPEN CHANNEL (spec §45; owner RULINGS 2026-09-15i): the floor
    # at the record's own profile and the crest at the governed cell's
    # SOLVED surface — after the pavement families whose value the crest
    # takes, and beside the other structure generators whose senior-datum
    # reconciliation it shares.
    ("channels", channel.channels),
)


def stack(rows: _t.Iterable[Row]) -> ConstraintSet:
    """Rows by kind, order preserved within kind (``ConstraintSet.from_rows``)."""
    return ConstraintSet.from_rows(rows)


def run_generator(fn: Generator, planar: PlanarMap, law: Law, airport: Airport
                  ) -> tuple[list[Row], dict[str, int]]:
    """ONE generator: its rows and its own statistics — its module's
    ``STATS[fn name]``, published beside its count as ``<name>.<stat>``
    (apron_within_shape: chords_outside_face, RULINGS 2026-09-05ae(1)); the
    stage cache's per-generator record (spec §4b.1) stores both."""
    got = fn(planar, law, airport)
    stats = (getattr(_sys.modules.get(fn.__module__), "STATS", None) or {}).get(fn.__name__)
    return got, {k: int(v) for k, v in (stats or {}).items()}


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
        got, stats = run_generator(fn, planar, law, airport)
        walls[name] = time.perf_counter() - t0
        counts[name] = len(got)
        rows.extend(got)
        for k, v in stats.items():
            counts[f"{name}.{k}"] = v
    rows = post_passes(rows, counts, walls, planar, law, airport, only, yielded_out)
    return stack(rows), counts, walls


def post_passes(rows: list[Row], counts: dict[str, int], walls: dict[str, float],
                planar: PlanarMap, law: Law, airport: Airport,
                only: _t.Container[str] | None = None,
                yielded_out: list[Row] | None = None) -> list[Row]:
    """The passes over EVERY generator's rows, ONE expression for
    :func:`generate` and the build's per-generator records
    (``pipeline/constraint_records``): the door pads' blend, then
    ``assembly.assemble``.  MEASURED (#798 round 3): the records path ran
    the assembly alone, so the KASE build solved with no blend at all and
    read 337 apron rows in hard conflict where the replay read none."""
    # owner 2026-10-20 (#798): round a sloping building's pad the apron
    # blends at up to the tunnel-ramp cap, except along the door line
    rows = door_pad.relax_apron_caps(rows, planar, law, airport, counts)
    return assemble(rows, counts, walls, planar, law, only, yielded_out)
